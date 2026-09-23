# Request_AA_PREPAID_PROVISIONING

> This FM provisions prepaid subscribers on the AA (Activation & Administration) platform. Handles all transaction types: Activate, Deactivate, Suspend, Restore, SoftSuspend, SoftRestore, SwapSIM, SwapMSISDN, GeneralUpdate, FullToSoft, InformationUpdate, and RM-to-RF migration scenarios. Iterates over both ParentOU and ChildOU subscribers.

**Rule:** `Rules.OMConsumers.OMXFM.Request.Request_AA_PREPAID_PROVISIONING`
**Priority:** 5 | **forwardChain:** true | **Author:** snarayan-t430

---

## §1 Overview & Purpose

This FM provisions prepaid subscribers on the **AA (Activation & Administration)** platform. It is a multi-purpose provisioning rule that handles all transaction types for prepaid subscribers. The transaction type is driven by `Parameter[0]` (SRV_TRX_TP_CD).

The rule iterates over both **ParentOU Subscribers** and **ChildOU Subscribers**, processing each independently. For each subscriber it: (1) calls `ProcessSwitchFeatures` to build the AA feature change list, (2) builds a `PrepaidProvisioningRequest` payload via XSLT, (3) routes the event — OrderType 51 (PreActivate) and 56 (Deactivate) are routed to a dedicated `AA_PREPAID_PREACT_DEACT` channel; all other types use the standard send path.

After processing, the rule syncs the `RequestCount` to the companion `AA_CHECK_CONFIRMATION` activity matching the same `Parameter[0]`.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_AA_PREPAID_PROVISIONING` |
| Priority | 5 |
| forwardChain | true |
| Author | snarayan-t430 |
| ActivityID matched | `AA_PREPAID_PROVISIONING` |
| Target event | `/Events/OMConsumers/OMXFM/Request/AA_PREPAID_PROVISIONING` |
| Special routing (OrderType 51/56) | `/Channels/OMXFMConnectionRequest/AA_PREPAID_PREACT_DEACT` |
| Response rulefunction | `Response_AA_PREPAID_PROVISIONING` |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order request context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity node |
| `swfRes` | `Concepts.FM.Response.AA_SwitchFeatureRes` | Switch feature response (cleaned up in finally) |
| `fListRes` | `Concepts.FM.Response.AASwitchFeatureList` | Feature list response (cleaned up in finally) |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Active next step |
| 2 | `orderCurrentActivity.ActivityID == "AA_PREPAID_PROVISIONING"` | FM selector |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "AA_PREPAID_PROVISIONING"` | Process flow confirmation |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Awaiting execution |

---

## §5 Execution Flow Diagram

1. Compute `isActResub`; load `nextAct`
2. **Parameter guard:** throw `DATA_ISSUE` exception if `Parameter@length == 0`
3. Read `paramOperatorIdValue` from `OPERATORID` parameter key
4. **ParentOU Subscriber loop** — for each `ParentOU[i].Subscriber[j]`:
   - Resubmit guard (CompletionStatus=2 + RefId)
   - PreExecCheck gate (XPath on subscriber XML slice)
   - Determine `isPAgreePresent` → get ParentOU Agreement
   - Compute `isCustomerHybrid` (AccountSubType starts-with HY or ==PHI)
   - Resolve PP (price plan from ServiceType=80, FE/CCP/CCBS preference order)
   - Call `ProcessSwitchFeatures(orderRequest, subscriber, agreement, isHybrid, pp, "", Parameter[0])`
   - Build and send `AA_PREPAID_PROVISIONING` event via XSLT (Variant ①)
   - Route: OrderType 51/56 → `AA_PREPAID_PREACT_DEACT` channel; else standard send
   - Conditional audit log (AllowWriteLog)
   - Increment RequestCount
5. **ChildOU Subscriber loop** — for each `ParentOU[i].ChildOU[m].Subscriber[n]`:
   - Same pattern using Variant ② XSLT, with ChildOU indexes `i/m/n`
6. **Post-loop:** status "1" if any sent; SkipActivity("4") otherwise
7. **Sync RequestCount** to matching AA_CHECK_CONFIRMATION activity (same Parameter[0])
8. **Finally:** delete `swfRes` and `fListRes` instances

---

## §6 Rule Action (THEN) — Logic Detail

> **Parameter guard:** throws `Exception.newException("DATA_ISSUE", "OMX could not find Paramater field value for Activation.", null)` if `Parameter@length == 0`

### SRV_TRX_TP_CD Mapping

| Code | Name | Notes |
|------|------|-------|
| NAC | Activate | |
| RCL | Resume | |
| DSD | Deactivate | |
| CCN | SwapMSISDN | |
| SSP | SwapSIM (or "SwapSIM " + OLD_IMSI prefix for types 68/12015-17) | |
| CCD | GeneralUpdate | |
| SSU | SoftSuspend | |
| SRS | SoftRestore | |
| SUS | Suspend | Used in PREPAID_SUSPEND |
| RSP | Restore | |
| FTS | FullToSoft | |
| CCI | InformationUpdate | |
| RM2RFCRPF | Create dummy RF profile | |
| RM2RFMGRT | Migrate RM to RF by OTA | |
| SSPMGRT | Migrate RM to RF by SwapSIM | |

### OPERATOR_ID Resolution Priority (descending)

1. `orderRequest.OrderData.OperatorId` (if non-empty trim)
2. SubscriberType=RM + OrderType 57/58 → `"98391"`
3. SubscriberType=RF + OrderType 57/58 → `"98392"`
4. SRV_TRX_TP_CD=NAC + OrderType 51 → `"70003"`
5. SRV_TRX_TP_CD=DSD + OrderType 56 + Channel=CCP → `"60012"`
6. OrderType 66 → `globalVars/OMX_OM/Rules/OMConsumers/OMXFM/Request/PPRegister_OperatorIdtoAA`
7. `paramOperatorIdValue` (from OPERATORID parameter)
8. Default: `"60001"`

**isCustomerHybrid:** `starts-with(AccountSubType,"HY") or AccountSubType=="PHI"`

**PP (price plan) resolution:** checks ServiceType=80 with FE_OR_CCBS value in order FE → CCP → CCBS. Falls back to Agreement.Offers[ServiceType=80] if available.

**Routing logic:** OrderType 51 or 56 → `Event.Ext.routeToImmediate(reqEvent, "/Channels/OMXFMConnectionRequest/AA_PREPAID_PREACT_DEACT", "")`;  all others → `Event.Ext.sendEventImmediate(reqEvent)`

---

## §7 Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| `paramOperatorIdValue` | `GetActivityParamValueFromKey(activity, "OPERATORID")` | Override for OPERATOR_ID |
| `isPAgreePresent` | XPath: `count(ParentOU[i+1]/Agreement) > 0` | Agreement presence check |
| `isCustomerHybrid` | XPath: `starts-with(AccountSubType,"HY") or AccountSubType=="PHI"` | Hybrid account flag |
| `pp` | XPath: ServiceType=80 FE→CCP→CCBS order from SubscriberOffers | Price plan name |
| `accSubType` | XSLT: Account.AccountManagementInfo.AccountSubType (by AgreementRefId or RefId match), default "PRE" | Account sub-type |
| `IMSI` | XSLT: PREPAID_NEW_IMSI if present, else IMSI from ResourceInfo | Network identity |
| `SRV_TRX_S_NO` | XSLT: `SrvTrxNoInfo[SrvTrxTp=Parameter[0]]/SrvTrxNo` | Service transaction sequence number |

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

| OrderType | Behaviour |
|-----------|-----------|
| 51 (PreActivate) | Route to AA_PREPAID_PREACT_DEACT channel; OPERATOR_ID="70003" for NAC |
| 56 (Deactivate) | Route to AA_PREPAID_PREACT_DEACT channel; OPERATOR_ID="60012" for DSD+CCP |
| 57/58 (Reconnect) | OPERATOR_ID="98391" (RM) or "98392" (RF) |
| 66 (PP Register) | OPERATOR_ID from globalVar PPRegister_OperatorIdtoAA |
| 68/12015/12016/12017 | SwapSIM includes OLD_IMSI prefix; PREV_IMSI included |

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel/Event | Condition |
|-----------|---------------|-----------|
| [OUTBOUND] | `/Events/OMConsumers/OMXFM/Request/AA_PREPAID_PROVISIONING` | OrderType ≠ 51/56 |
| [OUTBOUND] | `/Channels/OMXFMConnectionRequest/AA_PREPAID_PREACT_DEACT` | OrderType = 51 or 56 |
| [OUTBOUND] | `/Events/OMConsumers/OMXESB/Logger` | AllowWriteLog(OrderType) = true |

### §8.3 Backend API Details

| System | Operation | Schema |
|--------|-----------|--------|
| AA (Activation & Administration) | PrepaidProvisioning — Activate/Suspend/Deactivate/etc. | `ns1:PrepaidProvisioningRequest/PrepaidProvisioningOnAARequest` |

### §8.4 BE Working Memory

| Field | Access | Notes |
|-------|--------|-------|
| `orderCurrentActivity.RequestCount` | Read/Write | Incremented per subscriber; synced to AA_CHECK_CONFIRMATION |
| `orderCurrentActivity.Status` | Write | "1" or skipped |
| `orderCurrentActivity.Parameter[0]` | Read | SRV_TRX_TP_CD — required |
| `subscriber.AA_XML_Array` | Read | Feature change list (built by ProcessSwitchFeatures) |
| `subscriber.SrvTrxNoInfo` | Read | Service transaction number lookup |
| `subscriber.ResourceInfo` | Read | IMSI, PREPAID_NEW_IMSI, OLD_MSISDN, OLD_IMSI, CF params, MSISDN_ZONE |

### §8.5 ExtendedInfo Fields Required

No direct ExtendedInfo reads in this rule (handled inside `ProcessSwitchFeatures`).

### §8.6 Global Variable Dependencies

| Path | Used For |
|------|----------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/PPRegister_OperatorIdtoAA` | OPERATOR_ID for OrderType 66 |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_OM/WritePayload` | Payload logging gate |

---

## §9 Detailed Payload Build

Two XSLT variants exist: **Variant ① ParentOU Subscriber** (namespace `ns1`, indexes `$i/$j`) and **Variant ② ChildOU Subscriber** (namespace `ns2`, indexes `$i/$m/$n`). Core field mappings are identical.

### §9.1 XSLT Parameter Binding

| Param | Bound From | Notes |
|-------|------------|-------|
| `orderRequest` | OrderRequest concept | |
| `i` / `j` | Loop indexes POU/Subscriber | Variant ① |
| `i` / `m` / `n` | Loop indexes POU/COU/Subscriber | Variant ② |
| `orderCurrentActivity` | Current activity | |
| `subscriberInstance` | Resolved subscriber concept | |
| `globalVariables` | Global variable tree | |
| `paramOperatorIdValue` | OPERATORID parameter value | |

### §9.2 Event Container

Event type: `Events.OMConsumers.OMXFM.Request.AA_PREPAID_PROVISIONING`

### §9.3 JMS/Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | Always |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Always |
| OrderID | `$orderRequest/OrderData/OrderID` | Always |
| RefID | `Subscriber/RefId` | Always |
| OrderType | `$orderRequest/OrderData/OrderType` | Conditional |

### §9.4 Payload Root Element

`ns1:PrepaidProvisioningRequest/ns1:PrepaidProvisioningOnAARequest/ns1:subscriptioninfo`

### §9.5 Conditional Fields

| Field | Condition |
|-------|-----------|
| `ns1:PREV_SUBSCRIBER_NO` | `ResourceInfo[OLD_MSISDN]` non-empty trim |
| `ns1:PREV_IMSI` | OrderType 68/12015/12016/12017 AND OLD_IMSI non-empty |
| `ns1:BIRTH_DATE` | `CustomerGeneralInfo.BirthDate` exists |
| `ns1:CERTIFICATE_TYPE` | `CustomerGeneralInfo.IdentificationType` exists |
| `ns1:ZONE` | `ResourceInfo[MSISDN_ZONE]` non-empty trim |

### §9.6 Core Payload Fields

| Element | Source | Notes |
|---------|--------|-------|
| `ns1:CFU_NUM` | `ResourceInfo[CFU_NO_PARAM]/ValuesArray` | |
| `ns1:CFNRC_NUM` | `ResourceInfo[CFNRC_NO_PARAM]/ValuesArray` | |
| `ns1:CFB_NUM` | `ResourceInfo[CFW_NO_PARAM]/ValuesArray` | |
| `ns1:CFNRY_NUM` | `ResourceInfo[CFNRY_NO_PARAM]/ValuesArray` | |
| `ns1:MSISDN` | `Subscriber/MSISDN` | |
| `ns1:BAN` | `"111111111"` | Static |
| `ns1:IMSI` | PREPAID_NEW_IMSI or IMSI ResourceInfo | Choose first available |
| `ns1:SRV_TRX_TP_CD` | `Parameter[0]` | e.g. "SUS" for PREPAID_SUSPEND |
| `ns1:SRV_TRX_S_NO` | `SrvTrxNoInfo[SrvTrxTp=Parameter[0]]/SrvTrxNo` | |
| `ns1:SRV_TRX_NM_CD` | Mapped from SRV_TRX_TP_CD (see §6) | "Suspend" for SUS |
| `ns1:PP` | Agreement.Offers[ServiceType=80][1] or SubscriberOffers[ServiceType=80][1] | |
| `ns1:PROVISIONING_DATE` | `tib:format-dateTime("dd/MM/yyyy' 'HH:mm:ss", current-dateTime())` | |
| `ns1:OPERATOR_ID` | Complex priority logic (see §6) | |
| `ns1:ACCOUNT_CATEGORY` | `"I"` | Static |
| `ns1:CERTIFICATE_NUMBER` | `concat(Identification,"|",DealerCode)` | |
| `ns1:ACCOUNT_TYPE` | `$accSubType` | |
| `ns1:BILLING_LANGUAGE` | Language=="EN" → "E", else "T" | |
| `ns1:COMPANY_CODE` | `Subscriber/SubscriberType` | |
| `ns1:BILL_CYCLE` | `"30"` | Static |
| `ns1:SUB_STATUS` | `"A"` | Static |
| `ns1:SUB_STATUS_RSN_CODE` | `''` | Static empty |
| `ns1:SOURCE_ID` | `"AMDOCS"` | Static |
| `ns1:CUST_HYBRID` | starts-with(accSubType,"HY") or ==PHI → true/false | |
| `ns1:AATags/ns1:AAXML` | For-each over AA_XML_Array.AA_XML where NEW_OR_PREV non-empty | NEW_OR_PREVIOUS, FTR_GRP, FTR_PARAM, FTR_VALUE |

### §9.7 Complete Generated XML Example

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-2024-001</JMSCorrelationID>
    <OrderID>ORD-12345</OrderID>
    <RefID>SUB-REF-001</RefID>
    <OrderType>68</OrderType>
    <payload>
      <ns1:PrepaidProvisioningRequest>
        <ns1:PrepaidProvisioningOnAARequest>
          <ns1:subscriptioninfo>
            <ns1:CFU_NUM/>
            <ns1:CFNRC_NUM/>
            <ns1:CFB_NUM/>
            <ns1:CFNRY_NUM/>
            <ns1:MSISDN>0812345678</ns1:MSISDN>
            <ns1:BAN>111111111</ns1:BAN>
            <ns1:IMSI>52001234567890</ns1:IMSI>
            <ns1:SRV_TRX_TP_CD>SUS</ns1:SRV_TRX_TP_CD>
            <ns1:SRV_TRX_S_NO>123456</ns1:SRV_TRX_S_NO>
            <ns1:SRV_TRX_NM_CD>Suspend</ns1:SRV_TRX_NM_CD>
            <ns1:PP>TRUE_MOVE_PREPAID_99</ns1:PP>
            <ns1:PROVISIONING_DATE>15/09/2026 10:30:00</ns1:PROVISIONING_DATE>
            <ns1:OPERATOR_ID>60001</ns1:OPERATOR_ID>
            <ns1:ACCOUNT_CATEGORY>I</ns1:ACCOUNT_CATEGORY>
            <ns1:CERTIFICATE_NUMBER>1234567890123|DLR001</ns1:CERTIFICATE_NUMBER>
            <ns1:ACCOUNT_TYPE>PRE</ns1:ACCOUNT_TYPE>
            <ns1:BILLING_LANGUAGE>T</ns1:BILLING_LANGUAGE>
            <ns1:COMPANY_CODE>RM</ns1:COMPANY_CODE>
            <ns1:BILL_CYCLE>30</ns1:BILL_CYCLE>
            <ns1:SUB_STATUS>A</ns1:SUB_STATUS>
            <ns1:SUB_STATUS_RSN_CODE/>
            <ns1:SOURCE_ID>AMDOCS</ns1:SOURCE_ID>
            <ns1:CUST_HYBRID>false</ns1:CUST_HYBRID>
            <ns1:AATags>
              <ns1:AAXML>
                <ns1:NEW_OR_PREVIOUS>N</ns1:NEW_OR_PREVIOUS>
                <ns1:FTR_GRP>CALLBAR</ns1:FTR_GRP>
                <ns1:FTR_PARAM>BAIC</ns1:FTR_PARAM>
                <ns1:FTR_VALUE>A</ns1:FTR_VALUE>
              </ns1:AAXML>
            </ns1:AATags>
          </ns1:subscriptioninfo>
        </ns1:PrepaidProvisioningOnAARequest>
      </ns1:PrepaidProvisioningRequest>
    </payload>
  </event>
</createEvent>
```

### §9.8 XSLT Stylesheet Source (Variants ① ParentOU / ② ChildOU)

**Variant ①** uses namespace `ns1`, indexes `$i/$j`. **Variant ②** uses namespace `ns2`, indexes `$i/$m/$n`, and adds `$var1`. Core field mappings are identical between variants.

```xml
<!-- AA_PREPAID_PROVISIONING Request XSLT — Variant ① (ParentOU Subscriber) -->
<xsl:stylesheet
  xmlns:ns1="http://services.omx.truecorp.co.th/FMServices/prepaidProvisioningRequest"
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="i"/>  <xsl:param name="j"/>  <!-- ① loop indexes -->
  <xsl:param name="orderCurrentActivity"/>
  <xsl:param name="subscriberInstance"/>
  <xsl:param name="globalVariables"/>
  <xsl:param name="paramOperatorIdValue"/>
  <!-- Key XSLT variables:
    var  = i+1 (1-based POU index)
    var2 = j+1 (1-based Subscriber index)
    accSubType: Account[AgreementRefId=ParentOU[var]/RefId]/AccountManagementInfo/AccountSubType
                or Account[RefId=POU[var]/RefId]/AccountManagementInfo/AccountSubType
                or "PRE"
    varSRV_TRX_TP_CD = $orderCurrentActivity/Parameter[1]
    SRV_TRX_NM_CD: xsl:choose on varSRV_TRX_TP_CD (see §6 table)
    OPERATOR_ID:   xsl:choose in priority order (see §6)
    CUST_HYBRID:   starts-with(accSubType,"HY") or accSubType=="PHI"
    AATags:        for-each subscriberInstance/AA_XML_Array/AA_XML where NEW_OR_PREV non-empty
  -->
</xsl:stylesheet>
<!-- Variant ②: identical structure with ns2 prefix and $i/$m/$n indexes -->
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                            [Always]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId                  [Always]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID                        [Always]
    ├── RefID                    ← Subscriber/RefId                                       [Always]
    ├── OrderType                ← $orderRequest/OrderData/OrderType                      [Conditional: exists]
    └── payload
        └── ns1:PrepaidProvisioningRequest
            └── ns1:PrepaidProvisioningOnAARequest
                └── ns1:subscriptioninfo
                    ├── ns1:CFU_NUM              ← ResourceInfo[CFU_NO_PARAM]/ValuesArray [Always]
                    ├── ns1:CFNRC_NUM            ← ResourceInfo[CFNRC_NO_PARAM]/ValuesArray [Always]
                    ├── ns1:CFB_NUM              ← ResourceInfo[CFW_NO_PARAM]/ValuesArray [Always]
                    ├── ns1:CFNRY_NUM            ← ResourceInfo[CFNRY_NO_PARAM]/ValuesArray [Always]
                    ├── ns1:MSISDN               ← Subscriber/MSISDN                      [Always]
                    ├── ns1:BAN                  ← "111111111"                            [Always]
                    ├── ns1:IMSI                 ← PREPAID_NEW_IMSI or IMSI              [Always (choose)]
                    ├── ns1:SRV_TRX_TP_CD        ← $orderCurrentActivity/Parameter[1]    [Always]
                    ├── ns1:SRV_TRX_S_NO         ← SrvTrxNoInfo[SrvTrxTp=param]/SrvTrxNo [Always]
                    ├── ns1:SRV_TRX_NM_CD        ← xsl:choose on SRV_TRX_TP_CD          [Always]
                    ├── ns1:PP                   ← Agreement/SubscriberOffers[ST=80]     [Always]
                    ├── ns1:PROVISIONING_DATE     ← tib:format-dateTime(current-dateTime()) [Always]
                    ├── ns1:OPERATOR_ID           ← xsl:choose priority logic             [Always]
                    ├── ns1:ACCOUNT_CATEGORY     ← "I"                                   [Always]
                    ├── ns1:CERTIFICATE_NUMBER   ← concat(Identification,"|",DealerCode) [Always]
                    ├── ns1:CERTIFICATE_TYPE     ← IdentificationType                    [Conditional: exists]
                    ├── ns1:ACCOUNT_TYPE         ← $accSubType                           [Always]
                    ├── ns1:BIRTH_DATE           ← CustomerGeneralInfo.BirthDate         [Conditional: exists]
                    ├── ns1:BILLING_LANGUAGE     ← Language=="EN"?"E":"T"               [Always]
                    ├── ns1:COMPANY_CODE         ← Subscriber/SubscriberType             [Always]
                    ├── ns1:BILL_CYCLE           ← "30"                                  [Always]
                    ├── ns1:SUB_STATUS           ← "A"                                   [Always]
                    ├── ns1:SUB_STATUS_RSN_CODE  ← ''                                    [Always]
                    ├── ns1:PREV_SUBSCRIBER_NO   ← ResourceInfo[OLD_MSISDN]/ValuesArray  [Conditional: non-empty]
                    ├── ns1:PREV_IMSI            ← ResourceInfo[OLD_IMSI]/ValuesArray    [Conditional: OrderType 68/12015-17 + OLD_IMSI present]
                    ├── ns1:SOURCE_ID            ← "AMDOCS"                              [Always]
                    ├── ns1:CUST_HYBRID          ← starts-with(accSubType,"HY") or ==PHI [Always]
                    ├── ns1:ZONE                 ← ResourceInfo[MSISDN_ZONE]/ValuesArray [Conditional: non-empty]
                    └── ns1:AATags
                        └── ns1:AAXML (for-each where NEW_OR_PREV non-empty)             [Conditional: for-each]
                            ├── ns1:NEW_OR_PREVIOUS ← AA_XML.NewOrPrevious
                            ├── ns1:FTR_GRP         ← AA_XML.FeatureGroup
                            ├── ns1:FTR_PARAM       ← AA_XML.FeatureParameter
                            └── ns1:FTR_VALUE       ← AA_XML.FeatureValue
```

Legend: `XPath source` = dynamic value | `"static"` = literal constant | `[Conditional: ...]` = xsl:if condition

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| Gate | `RuleFunctions.Helpers.AllowWriteLog(OrderType)` must be true |
| PROCESS_ID | `concat($pid, "_REQ")` |
| OPERATION_NAME | `"AA_PREPAID_PROVISIONING"` |
| TARGET_SYSTEM | `globalVars/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `concat("Request Sent for RefId ", $refId)` |
| payload | `ns:ServicePayload = copy of $reqEvent` (gated on WritePayload=true) |

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one request sent | [IN_PROGRESS "1"] | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All skipped | [SKIPPED "4"] | `SkipActivity(orderRequest, activity, "4")` |

---

## §13 Exception / Error Handling

Outer try/catch catches `Exception ae` → `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

**Finally block:** `Instance.deleteInstance(swfRes)` and `Instance.deleteInstance(fListRes)` — cleans up switch feature working memory regardless of success/failure.

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `GetActivityParamValueFromKey(activity, "OPERATORID")` | Read named parameter value from activity Parameter array |
| `GetXMLForSubscriber(orderRequest, refId)` | Build subscriber-scoped XML for PreExecCheck |
| `GetXMLForSubscriberInChildOU(orderRequest, refId, POURefId)` | Build ChildOU subscriber XML for PreExecCheck |
| `ProcessSwitchFeatures(orderRequest, subscriber, agreement, isHybrid, pp, "", Parameter[0])` | Build AA feature change list into subscriber.AA_XML_Array |
| `AllowWriteLog(OrderType)` | Check if audit logging is enabled for this order type |
| `GetActivityStatusString("1", false)` | Return IN_PROGRESS status string |
| `SendDataToDB(orderRequest)` | Persist state |
| `SkipActivity, HandleActivityException` | Standard lifecycle |

---

## §15 Function Dependency Tree

```text
Request_AA_PREPAID_PROVISIONING (THEN block)
├── RuleFunctions.Helpers.GetActivityParamValueFromKey(...)
├── [POU loop]
│   ├── XPath.evalAsBoolean(isPAgreePresent)
│   ├── XPath.evalAsBoolean(isCustomerHybrid)
│   ├── XPath.evalAsString(pp)
│   ├── RuleFunctions.Helpers.ProcessSwitchFeatures(...)
│   ├── Event.createEvent(xslt://AA_PREPAID_PROVISIONING)  [Variant ①]
│   ├── Event.Ext.routeToImmediate(...)  [OrderType 51/56]
│   ├── Event.Ext.sendEventImmediate(...)  [other OrderTypes]
│   ├── RuleFunctions.Helpers.AllowWriteLog(...)
│   │   └── Event.createEvent(xslt://Logger)
│   │       └── Event.Ext.sendEventImmediate(logEvent)
│   └── (increment RequestCount)
├── [ChildOU loop]
│   ├── XPath.evalAsBoolean(isPaAgreePresent)
│   ├── XPath.evalAsBoolean(isCAgreePresent)
│   ├── XPath.evalAsBoolean(isCustomerHybrid)
│   ├── XPath.evalAsString(pp)
│   ├── RuleFunctions.Helpers.ProcessSwitchFeatures(...)
│   ├── Event.createEvent(xslt://AA_PREPAID_PROVISIONING)  [Variant ②]
│   └── (same send/log/count pattern)
├── [RequestCount sync to AA_CHECK_CONFIRMATION]
├── RuleFunctions.Helpers.GetActivityStatusString("1")
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)
├── RuleFunctions.Helpers.HandleActivityException(...)
└── [finally] Instance.deleteInstance(swfRes, fListRes)
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields |
|---------|------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.*, Customer.ParentOU[].Subscriber[], Customer.ParentOU[].ChildOU[].Subscriber[], Customer.Account[], IsOrderResubmitted |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Parameter[], Response[], Activities[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, SubscriberId, MSISDN, SubscriberType, SubscriberGeneralInfo.Language, SubscriberOffers[], ResourceInfo[], SrvTrxNoInfo[], AA_XML_Array |
| `Concepts.FM.Response.AA_SwitchFeatureRes` | Cleaned up in finally block |
| `Concepts.FM.Response.AASwitchFeatureList` | Cleaned up in finally block |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Support all 15+ SRV_TRX_TP_CD transaction types for prepaid provisioning on AA |
| R2 | Process both ParentOU and ChildOU subscribers in a single activity |
| R3 | Route OrderType 51/56 to a dedicated channel (AA_PREPAID_PREACT_DEACT) |
| R4 | Resolve OPERATOR_ID through an 8-level priority cascade |
| R5 | Call ProcessSwitchFeatures before event build to populate AA feature tags |
| R6 | Sync RequestCount to AA_CHECK_CONFIRMATION after processing |
| R7 | Clean up switch feature working memory instances regardless of outcome |
| R8 | Support resubmit idempotency (skip subscribers with CompletionStatus=2) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Complex OPERATOR_ID resolution with 8 conditions — hard to maintain | [HIGH] | Extract to configurable decision table in target architecture |
| 15+ SRV_TRX_TP_CD codes in a single rule — broad blast radius for any change | [HIGH] | Consider splitting into specialized provisioning service operations |
| BAN hardcoded to "111111111" | [MEDIUM] | Verify AA platform behavior; externalize if needed |
| SUB_STATUS always "A" — may not be accurate for suspend/deactivate flows | [MEDIUM] | Confirm with AA platform team; SRV_TRX_TP_CD drives actual operation |
| ProcessSwitchFeatures side effect on subscriberInstance.AA_XML_Array — implicit coupling | [MEDIUM] | Document explicitly; make state flow explicit in target |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_AA_PREPAID_PROVISIONING {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    Concepts.FM.Response.AA_SwitchFeatureRes swfRes;
    Concepts.FM.Response.AASwitchFeatureList fListRes;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "AA_PREPAID_PROVISIONING";
    orderRequest.ProcessFlow.NextActivityID == "AA_PREPAID_PROVISIONING";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
      // Guard: throw DATA_ISSUE if Parameter@length == 0
      String paramOperatorIdValue = GetActivityParamValueFromKey(activity, "OPERATORID");

      for(int i=0; i < iPOULen; i++) {
        for(int j=0; j < iSubscriberLen; j++) {
          // Resubmit guard: skip if Response[RefId + CompletionStatus=2]
          // PreExecCheck gate
          // Resolve: isPAgreePresent, isCustomerHybrid, pp
          RuleFunctions.Helpers.ProcessSwitchFeatures(orderRequest, subscriberInstance, agreement, isHybrid, pp, "", Parameter[0]);
          /* Build AA_PREPAID_PROVISIONING event via XSLT Variant ① — see §9.8 */
          /* Payload: PrepaidProvisioningOnAARequest with all subscription fields */
          if(OrderType=="51" || OrderType=="56") {
            Event.Ext.routeToImmediate(reqEvent, "/Channels/OMXFMConnectionRequest/AA_PREPAID_PREACT_DEACT", "");
          } else {
            Event.Ext.sendEventImmediate(reqEvent);
          }
          if(AllowWriteLog(OrderType)) { /* Send audit Logger event — see §11 */ }
          if(!isActResub) orderCurrentActivity.RequestCount++;
          isSkipped = false;
        }
      }

      // ChildOU loop — same pattern with Variant ② XSLT, ChildOU indexes i/m/n
      for(int m=0; m < ChildOU@length; m++) {
        for(int n=0; n < iSubscriberLen; n++) {
          // ... resubmit, PreExecCheck, POU/COU Agreement, isHybrid, pp, ProcessSwitchFeatures ...
          /* Build AA_PREPAID_PROVISIONING event Variant ② — see §9.8 */
          // Same routing, log, increment pattern
        }
      }

      if(!isSkipped) {
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else {
        SkipActivity(orderRequest, orderCurrentActivity, "4");
      }

      // Sync RequestCount to AA_CHECK_CONFIRMATION with same Parameter[0]
      for(int i=0; i < iActLen; i++) {
        if(actId=="AA_CHECK_CONFIRMATION" && param==Parameter[0] && RequestCount>0)
          Activities[i].RequestCount = orderCurrentActivity.RequestCount;
      }
    } catch(Exception ae) {
      HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    } finally {
      Instance.deleteInstance(swfRes);
      Instance.deleteInstance(fListRes);
    }
  }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

`Response_AA_PREPAID_PROVISIONING` creates an `AA_PrepaidProvisioningRes` concept (not the generic `ResponseBase`) that includes standard response fields plus AA-specific fields (`ret_description`, `subscriber_no`, `srv_trx_tp_cd`, `srv_trx_s_no`, `ret_code`, `OMXTrackingId`). The `extId` is set to the AA-returned `srv_trx_s_no`, not a generated UUID.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.AA_PREPAID_PROVISIONING` | AA platform response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity for response appending |

### §19.3 AA_PrepaidProvisioningRes Construction

```text
createObject (AA_PrepaidProvisioningRes)
└── object @extId ← $eventResponse/payload/response/srv_trx_s_no  [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode                          [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg                           [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus                      [Conditional]
    ├── ReferenceId         ← $eventResponse/RefID                                 [Conditional]
    ├── ret_description     ← $eventResponse/payload/response/ret_description      [Conditional]
    ├── subscriber_no       ← $eventResponse/payload/response/subscriber_no        [Conditional]
    ├── srv_trx_tp_cd       ← $eventResponse/payload/response/srv_trx_tp_cd        [Conditional]
    ├── srv_trx_s_no        ← $eventResponse/payload/response/srv_trx_s_no         [Conditional]
    ├── ret_code            ← $eventResponse/payload/response/ret_code             [Conditional]
    └── OMXTrackingId       ← $eventResponse/JMSCorrelationID                      [Conditional]
```

### §19.4 Response Completion Logic

**Success XPath:** `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])`

**Fan-in:** `currActivity.RequestCount == successResponseCount` → `"true"` / `"false"`

> Note: an earlier commented-out version used `count(ParentOU/Subscriber)` as the denominator — replaced by the standard RequestCount pattern.

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| Gate | `AllowWriteLog(OrderType)` must be true |
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"AA_PREPAID_PROVISIONING"` |
| AUDIT_TRACE | `"Response received for AA_PREPAID_PROVISIONING"` |
| payload | `ns:ServicePayload = copy of $eventResponse` (gated on WritePayload=true) |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
