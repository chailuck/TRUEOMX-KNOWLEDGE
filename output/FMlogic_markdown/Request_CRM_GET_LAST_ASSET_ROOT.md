# Request_CRM_GET_LAST_ASSET_ROOT

> TIBCO BusinessEvents FM Logic Documentation — OMXFM Request Rule

**Priority:** 5 | **forwardChain:** true | **Backend:** CRM | **Fan-out:** Per Subscriber (POU + COU) | **Process:** PREPAID_CANCEL Step 1

---

## §1 Overview & Purpose

Retrieves the latest CRM asset root record for each prepaid subscriber in the order. This is the **entry-point FM** in `PREPAID_CANCEL` and serves as the primary data-enrichment step: it calls the CRM `CRMGetLatestAssetRoot` service to load subscriber asset identity, name, address, language, activation date, MNP data, and account type into the OMX working memory.

> **Critical Guard:** The response RF throws a `DATA_ISSUE` exception if the CRM response `productName` ≠ *"Mobile Prepay"* — ensuring the process only continues for genuine prepaid subscribers.

| Phase | What happens |
|-------|-------------|
| Request | Fan-out one JMS event per subscriber (ParentOU + ChildOU) with MSISDN as service identifier. Parameters `customerAddressFlag` and `OLPRD_DB_FLAG` are read from ProcessConfig activity parameters (defaulting to "Y"). |
| Response | Validates prepaid product type, then enriches 15+ subscriber fields and 5+ customer fields in working memory from the CRM asset bean response. |

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CRM_GET_LAST_ASSET_ROOT` |
| Priority | 5 |
| forwardChain | true |
| Rule type | Fan-out request rule |
| Scope | ParentOU Subscribers + ChildOU Subscribers |
| Event type (req) | `Events.OMConsumers.OMXFM.Request.CRM_GET_LAST_ASSET_ROOT` |
| Event type (res) | `Events.OMConsumers.OMXFM.Response.CRM_GET_LAST_ASSET_ROOT` |
| Payload schema | `ns:CRMGetLatestAssetRootRequest / CRMGetLatestAssetRootResponse` (http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CRM/CRMGetLatestAssetRoot.xsd) |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context — customer, subscribers, flow state |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity node — parameters, status, response list |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity matches the order's next step |
| 2 | `orderCurrentActivity.ActivityID == "CRM_GET_LAST_ASSET_ROOT"` | FM identity guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CRM_GET_LAST_ASSET_ROOT"` | Double-check on ProcessFlow |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity is in awaiting-execution state |

---

## §5 Execution Flow Diagram

1. **Resubmit check** — `isActResub = (RequestCount > 0 && IsOrderResubmitted)`; if true, skip RequestCount increment later.
2. **Read PreExecCheck** — load `nextAct.PreExecCheck` XPath from the activity concept in working memory.
3. **Loop ParentOU Subscribers** — resubmit guard → eval PreExecCheck → build and send CRM event → log if allowed → RequestCount++.
4. **Loop ChildOU Subscribers** — same pattern. **[HIGH BUG: refId uses nanoTime() not subscriber RefId]**
5. **Status update** — if any event sent: `Status="1"` (Processing) + `SendDataToDB`; else `SkipActivity("4")`.
6. **Exception** — outer `try/catch`; on exception: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §6 Rule Action (THEN)

### ParentOU Subscriber Loop

```java
for(p: ParentOU) {
  for(ps: Subscriber) {
    psub = ParentOU[p].Subscriber[ps]; pSubRefId = psub.RefId;
    // resubmit guard: check Response[].ReferenceId + CompletionStatus==2
    if(!reqSuccess) {
      chkRes = PreExecCheck ? XPath.execute(chkXPath, GetXMLForSubscriber(pSubRefId)) : "true";
      if(chkRes == "true") {
        customerAddressFlag = GetActivityParamValueFromKey("customerAddressFlag");
        olprdDbFlag = GetActivityParamValueFromKey("OLPRD_DB_FLAG");
        serviceId = psub.MSISDN;
        refId = pSubRefId;  // correct
        Event.Ext.sendEventImmediate(CRM_GET_LAST_ASSET_ROOT event);
        if(!isActResub) RequestCount++;
        if(AllowWriteLog) { /* send Logger */ }
      }
    }
  }
}
```

### ChildOU Subscriber Loop

```java
for(c: ChildOU) {
  for(cs: Subscriber) {
    // same resubmit guard, PreExecCheck eval
    if(chkRes == "true") {
      serviceId = csub.MSISDN;
      refId = String.valueOfLong(System.nanoTime()); // ⚠️ BUG: should be cSubRefId
      Event.Ext.sendEventImmediate(CRM_GET_LAST_ASSET_ROOT event); // identical XSLT
    }
  }
}
```

> **[HIGH BUG] ChildOU RefId**: `refId = String.valueOfLong(System.nanoTime())` generates a random nanotime value instead of using `cSubRefId`. The Response RF matches by `eventResponse.RefID == sub.RefId` — since no subscriber has RefId matching a nanotime, no ChildOU subscriber data will ever be enriched. Fan-in may also stall.

---

## §7 Parameter Extraction

| Parameter Key | Helper Call | Default (if blank) | PREPAID_CANCEL Value | Purpose |
|--------------|-------------|-------------------|---------------------|---------|
| `customerAddressFlag` | `GetActivityParamValueFromKey(activity,"customerAddressFlag")` | `"Y"` (XSLT otherwise) | `Y` | Instructs CRM whether to return address data |
| `OLPRD_DB_FLAG` | `GetActivityParamValueFromKey(activity,"OLPRD_DB_FLAG")` | `"Y"` (XSLT otherwise) | (not set → "Y") | Instructs CRM whether to query OLPRD DB |

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

| Process | Step | Notes |
|---------|------|-------|
| PREPAID_CANCEL | 1 (Entry) | Called unconditionally as first FM; validates subscriber is prepaid |

Response RF has OrderType-specific logic: OrderType `"35"` also enriches `CustomerName` and `CustomerAddress`; OrderType `"12011"` suppresses `SubscriberAddress` population.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Protocol | Purpose |
|-----------|-----------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CRM_GET_LAST_ASSET_ROOT` | JMS / sendEventImmediate | Send CRM asset root lookup request per subscriber |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CRM_GET_LAST_ASSET_ROOT` | JMS / correlation | Receive CRM asset data; enriches working memory |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | JMS / sendEventImmediate | Audit trail (request + response) |

### §8.3 Backend API Details

| System | Operation | Schema | Correlation |
|--------|-----------|--------|-------------|
| CRM | CRMGetLatestAssetRoot | `ns:CRMGetLatestAssetRootRequest / CRMGetLatestAssetRootResponse` | JMSCorrelationID = OMXTrackingId; RefID = subscriber RefId |

Response payload prefix: `xsd2:CRMGetLatestAssetRootResponse/xsd2:assetBeanList[1]`

### §8.4 BE Working Memory — Read vs. Written

| Field | Access | Source/Destination |
|-------|--------|-------------------|
| `orderRequest.ProcessFlow.NextActivityName/ID` | Read | Rule condition matching |
| `orderCurrentActivity.RequestCount` | Read/Write | Incremented per subscriber sent |
| `orderCurrentActivity.Status` | Write | "1" or SkipActivity("4") |
| `orderCurrentActivity.Response[]` | Write | ResponseBase appended in response RF |
| `sub.MSISDN` | Read | Used as serviceId in request payload |
| `sub.RefId` | Read | Used as refId in ParentOU path; NOT used in ChildOU |
| `sub.Status` | Write (RF) | Mapped from CRM status string (65/67/0) |
| `sub.AssetCrmId` | Write (RF) | ← assetRowID (if blank) |
| `sub.IntergrationCrmId` [typo] | Write (RF) | ← assetNo (if blank) |
| `sub.SubscriberId` | Write (RF) | ← ccbsSubscriberID or assetRowID per globalVar |
| `sub.SubscriberType` | Write (RF) | ← companyCode (if blank) |
| `sub.SubscriberGeneralInfo.Language` | Write (RF) | THA→TH, ENU→EN |
| `sub.SubscriberGeneralInfo.InitActDate` | Write (RF) | ← xStartDate (parsed) |
| `sub.SubscriberGeneralInfo.l9TmvServiceLevel` | Write (RF) | ← grading |
| `sub.SubscriberGeneralInfo.l9TmvActDate` | Write (RF) | ← originalStartDate (parsed) |
| `sub.SubscriberName.{Title,FirstName,LastName}` | Write (RF) | ← individual.title/firstName/lastName |
| `sub.SubscriberAddress` | Write (RF) | Full address from CRM addressList[1]; suppressed for OrderType "12011" |
| `sub.AccountManagementInfo.AccountSubType` | Write (RF) | "PRE" if productName=="Mobile Prepay" |
| `sub.ExtendedInfo[]` | Write (RF) | DONOR_OPERATOR, DONOR_ZONE, REC_OPERATOR, REC_ZONE (MNP info) |
| `sub.SubscriberOffers[CARRYS01].ParameterInfo` | Write (RF) | "Monetary quota" ← lastMainBalance |
| `orderRequest.OrderData.Customer.CustomerCrmId` | Write (RF) | ← assetBeanList[1].customerRowID |
| `orderRequest.OrderData.DealerCode` | Write (RF) | ← prepaidDealerCode (if blank) |
| `orderRequest.OrderData.Customer.CustomerTypeInfo.Type` | Write (RF) | = 80 for "Mobile Prepay" |
| `orderRequest.OrderData.Customer.CustomerGeneralInfo` | Write (RF) | Identification, IdentificationType (mapped), BirthDate |

### §8.5 ExtendedInfo Fields Written

| Key | Container | Source (Response) |
|-----|-----------|------------------|
| DONOR_OPERATOR | sub.ExtendedInfo[] | assetBeanList/mnpInfo/mnpDonorOper |
| DONOR_ZONE | sub.ExtendedInfo[] | assetBeanList/mnpInfo/mnpDonorZone |
| REC_OPERATOR | sub.ExtendedInfo[] | assetBeanList/mnpInfo/mnpRecOper |
| REC_ZONE | sub.ExtendedInfo[] | assetBeanList/mnpInfo/mnpRecZone |

### §8.6 Global Variable Dependencies

| Path | Used in | Purpose |
|------|---------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit log | COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit log | TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit log | LOG_LEVEL |
| `OMX_OM/WritePayload` | Audit log | Gates payload inclusion |
| `OMX_OM/Rules/OMConsumers/OMXFM/Response/CRM_GetLatestAssetRoot/DefaultSubIdBy` | Response RF | "CCBS"→ccbsSubscriberID, "CRM"→assetRowID, else→ccbsSubscriberID if blank |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| XSLT Param | Bound from (BE rule) | Purpose |
|------------|---------------------|---------|
| `$orderRequest` | `orderRequest` concept | Full order context for JMS headers |
| `$refId` | `pSubRefId` (ParentOU) / `nanoTime()` **[BUG]** (ChildOU) | Subscriber correlation reference |
| `$serviceId` | `psub.MSISDN` / `csub.MSISDN` | Subscriber MSISDN for CRM lookup |
| `$customerAddressFlag` | `GetActivityParamValueFromKey("customerAddressFlag")` | Whether CRM returns address data |
| `$olprdDbFlag` | `GetActivityParamValueFromKey("OLPRD_DB_FLAG")` | Whether CRM queries OLPRD DB |

### §9.2 Event Container

Event type: `Events.OMConsumers.OMXFM.Request.CRM_GET_LAST_ASSET_ROOT`
Event `extId`: `OMXUtils:generateTrackingID()` (unique per call)

### §9.3 JMS / Event Header Fields

| Field | Source XPath |
|-------|-------------|
| `JMSPriority` | `$orderRequest/OrderPriority` |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` |
| `OrderID` | `$orderRequest/OrderData/OrderID` |
| `RefID` | `$refId` |
| `OrderType` | `$orderRequest/OrderData/OrderType` |

### §9.4 Payload Root Element

`<ns:CRMGetLatestAssetRootRequest xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CRM/CRMGetLatestAssetRoot.xsd">`

### §9.5 Conditional Fields

| Element | Condition | Value (true) | Value (false) |
|---------|-----------|-------------|---------------|
| `ns:customerAddressFlag` | `string-length($customerAddressFlag) > 0` | `$customerAddressFlag` | `"Y"` |
| `ns:olprdDBFlag` | `$olprdDbFlag != ""` | `$olprdDbFlag` | `"Y"` |

### §9.6 Core Payload

| Element | Source | Notes |
|---------|--------|-------|
| `ns:serviceID` | `$serviceId` (subscriber MSISDN) | Always present |

### §9.7 Complete Generated XML Example

```xml
<createEvent>
  <event extId="OMX-TRK-001-20260820-001">
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-2026082012345</JMSCorrelationID>
    <OrderID>ORD-2026082099001</OrderID>
    <RefID>SUB-REF-001</RefID>
    <OrderType>35</OrderType>
    <payload>
      <ns:CRMGetLatestAssetRootRequest xmlns:ns="...CRMGetLatestAssetRoot.xsd">
        <ns:serviceID>0812345678</ns:serviceID>
        <ns:customerAddressFlag>Y</ns:customerAddressFlag>
        <ns:olprdDBFlag>Y</ns:olprdDBFlag>
      </ns:CRMGetLatestAssetRootRequest>
    </payload>
  </event>
</createEvent>
```

### §9.8 XSLT Stylesheet Source

Both ParentOU and ChildOU variants use **identical XSLT**. The only difference is how `$refId` is bound in the calling BE rule (see §9.1).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet
    xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CRM/CRMGetLatestAssetRoot.xsd"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    version="1.0"
    exclude-result-prefixes="OMXUtils xsl ns xsd">
  <xsl:output method="xml"/>
  <!-- Parameters bound from BE rule -->
  <xsl:param name="orderRequest"/>        <!-- full order concept -->
  <xsl:param name="refId"/>              <!-- pSubRefId (POU) / nanoTime() BUG (COU) -->
  <xsl:param name="serviceId"/>           <!-- subscriber MSISDN -->
  <xsl:param name="customerAddressFlag"/> <!-- from activity param -->
  <xsl:param name="olprdDbFlag"/>         <!-- from activity param -->
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <RefID><xsl:value-of select="$refId"/></RefID>
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        <payload>
          <ns:CRMGetLatestAssetRootRequest>
            <ns:serviceID><xsl:value-of select="$serviceId"/></ns:serviceID>
            <xsl:choose>
              <xsl:when test="string-length($customerAddressFlag) > 0">
                <ns:customerAddressFlag><xsl:value-of select="$customerAddressFlag"/></ns:customerAddressFlag>
              </xsl:when>
              <xsl:otherwise>
                <ns:customerAddressFlag><xsl:value-of select="'Y'"/></ns:customerAddressFlag>
              </xsl:otherwise>
            </xsl:choose>
            <xsl:choose>
              <xsl:when test="$olprdDbFlag!=''">
                <ns:olprdDBFlag><xsl:value-of select="$olprdDbFlag"/></ns:olprdDBFlag>
              </xsl:when>
              <xsl:otherwise>
                <ns:olprdDBFlag><xsl:value-of select="'Y'"/></ns:olprdDBFlag>
              </xsl:otherwise>
            </xsl:choose>
          </ns:CRMGetLatestAssetRootRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event @extId ← OMXUtils:generateTrackingID()                  [Always]
    ├── JMSPriority        ← $orderRequest/OrderPriority            [Always]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId  [Always]
    ├── OrderID            ← $orderRequest/OrderData/OrderID        [Always]
    ├── RefID              ← $refId                                 [Always] POU: pSubRefId | COU: ⚠️ nanoTime()
    ├── OrderType          ← $orderRequest/OrderData/OrderType      [Always]
    └── payload                                                     [Always]
        └── ns:CRMGetLatestAssetRootRequest
            ├── ns:serviceID          ← $serviceId (MSISDN)         [Always]
            ├── ns:customerAddressFlag ← $customerAddressFlag        [Conditional: string-length>0; else "Y"]
            └── ns:olprdDBFlag        ← $olprdDbFlag               [Conditional: !=""; else "Y"]
```

Legend: `[Always]` = unconditional | `[Conditional: ...]` = inside xsl:choose

---

## §11 Audit Logging

| Log Phase | Gate | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE |
|-----------|------|-----------|---------------|------------|
| Request | `AllowWriteLog(orderType)` | `<pid>_REQ` | CRM_GET_LAST_ASSET_ROOT | "Request Sent for CRM_GET_LAST_ASSET_ROOT" |
| Response | **No gate** (always logs) | `<pid>_RES` | CRM_GET_LAST_ASSET_ROOT | "Response received for CRM_GET_LAST_ASSET_ROOT" |

> The response RF does NOT apply the `AllowWriteLog` gate — it always logs regardless of order type. Payload body included only when `globalVariables/OMX_OM/WritePayload = "true"`.

---

## §12 Activity Status Management

| Condition | Status Set | Action |
|-----------|-----------|--------|
| At least one subscriber event sent | `"1"` (Processing) | `SendDataToDB(orderRequest)` |
| All subscribers already complete (isSkipped=true) | `"4"` (Skipped) | `SkipActivity(orderRequest, activity, "4")` |
| Exception caught | Set by HandleActivityException | `HandleActivityException(orderRequest, activity, ae, "")` |

Fan-in (response RF): `RequestCount == successResponseCount` → returns "true" (all parallel CRM calls complete).

---

## §13 Exception / Error Handling

| Location | Exception | Handler |
|----------|-----------|---------|
| Request rule — outer try/catch | Any `Exception ae` | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |
| Response RF — productName check | `Exception.newException("DATA_ISSUE", "subscriber not prepaid", null)` | Thrown when `productName != "Mobile Prepay"`; propagates up |

> **DATA_ISSUE Guard:** If CRM returns any product type other than "Mobile Prepay", the response RF throws a `DATA_ISSUE` exception. This protects against cancelling postpaid subscribers through the prepaid cancel flow.

---

## §14 Helper Functions Reference

| Function | Used in | Purpose |
|----------|---------|---------|
| `GetActivityParamValueFromKey(activity, key)` | Request rule | Reads activity parameter by key name |
| `GetXMLForSubscriber(orderRequest, refId)` | Request rule (POU) | Builds XML snapshot for PreExecCheck eval |
| `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)` | Request rule (COU) | Builds XML snapshot for ChildOU PreExecCheck eval |
| `AllowWriteLog(orderType)` | Request rule | Gates audit logging by order type |
| `SendDataToDB(orderRequest)` | Request rule | Persists order state to DB |
| `SkipActivity(orderRequest, activity, status)` | Request rule | Marks activity as skipped (status "4") |
| `HandleActivityException(orderRequest, activity, ae, "")` | Request rule | Standard exception handler |
| `BRMS.IsBlankOrStringNull(str)` | Response RF (extensive) | Null/empty guard for conditional field population |

---

## §15 Function Dependency Tree

```text
Request_CRM_GET_LAST_ASSET_ROOT (rule)
├── RuleFunctions.Helpers.GetActivityParamValueFromKey(activity, "customerAddressFlag")
├── RuleFunctions.Helpers.GetActivityParamValueFromKey(activity, "OLPRD_DB_FLAG")
├── RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, pSubRefId)
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)
├── XPath.execute(chkXPath, sXML, ns)
├── Event.createEvent("xslt://CRM_GET_LAST_ASSET_ROOT", ...)
├── Event.Ext.sendEventImmediate(reqEvent)
├── RuleFunctions.Helpers.AllowWriteLog(orderType)
│   └── Event.Ext.sendEventImmediate(Logger event)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")
└── RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")

Response_CRM_GET_LAST_ASSET_ROOT (rulefunction)
├── OMXUtils.generateTrackingID()
├── Instance.createInstance("xslt://ResponseBase", ...)
├── XPath.evalAsString(...) — customerRowID, prepaidDealerCode, productName,
│                             ccbsSubscriberID, assetRowID, assetNo, companyCode,
│                             preferLanguage, grading, title, firstName, lastName,
│                             address fields (12), MNP fields (4), idType, idNumber
├── XPath.evalAsInt(...) — sub.Status mapping
├── XPath.evalAsBoolean(...) — existXxx guards
├── XPath.evalAsDateTime(...) — xStartDate, originalStartDate, birthDate
├── Instance.createInstance(...) — CustomerTypeInfo, Account, AccountManagementInfo,
│                                  SubscriberGeneralInfo, SubscriberName,
│                                  SubscriberAddress, CustomerGeneralInfo,
│                                  ExtendedInfo (MNP x4), SubscriberParameterInfo
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(str) — multiple calls
├── Event.Ext.sendEventImmediate(Logger event)   — always (no gate)
└── XPath.evalAsInt(...) — successResponseCount (fan-in)
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields Used |
|---------|----------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.Customer.{CustomerCrmId,DealerCode,CustomerTypeInfo,CustomerGeneralInfo,CustomerName,CustomerAddress,ParentOU[],Account[]}, ProcessFlow.{NextActivityName,NextActivityID}, IsOrderResubmitted |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck, Parameter[] |
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |
| `Concepts.OrderRequest.OrderElements.Subscriber` | MSISDN, RefId, Status, AssetCrmId, IntergrationCrmId, SubscriberId, SubscriberType, SubscriberGeneralInfo, SubscriberName, SubscriberAddress, AccountManagementInfo, SubscriberOffers[], ExtendedInfo[] |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | Call CRM CRMGetLatestAssetRoot with subscriber MSISDN per-subscriber in the order |
| R2 | Support `customerAddressFlag` and `OLPRD_DB_FLAG` parameters from ProcessConfig |
| R3 | Validate product type is "Mobile Prepay"; throw DATA_ISSUE if not |
| R4 | Enrich subscriber working memory: status, IDs, name, address, language, dates, MNP info |
| R5 | Enrich customer working memory: CustomerCrmId, DealerCode, CustomerTypeInfo, identity fields |
| R6 | Apply GlobalVar `DefaultSubIdBy` to determine SubscriberId source (CCBS/CRM) |
| R7 | For CARRYS01 offers: populate lastMainBalance as ParameterInfo "Monetary quota" |
| R8 | Fan-out per subscriber; fan-in when all CRM responses received with success code |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| ChildOU `refId = nanoTime()` — response RF cannot match ChildOU subscriber by RefId; data enrichment and fan-in broken for ChildOU | [HIGH] | Fix to use `cSubRefId` in both Request rule and Response RF matching loop |
| Response RF only loops `ParentOU[j].Subscriber[i]` — ChildOU subscriber enrichment never happens | [HIGH] | Add ChildOU loop in response RF |
| Typo: `sub.IntergrationCrmId` (missing 'e' in Integration) | [MEDIUM] | Verify concept field name; fix typo in migration |
| Duplicate `idType` mapping: both "Government ID" → "G" and "Government ID" → "D"; second branch is dead code | [MEDIUM] | Clarify intended mapping — "D" likely meant a different ID type |
| Response RF does not apply `AllowWriteLog` gate — always logs | [LOW] | Add AllowWriteLog gate if consistent behavior desired |
| Large commented-out FaceRecognition block (faceRecVerifyMethod, KYC_DATA, VERIFY_RESULT, etc.) | [LOW] | Remove commented-out code in migration |
| Commented-out MNP working memory write (`orderRequest.OrderData.MNPInfo`) — MNP info only in sub.ExtendedInfo[] | [LOW] | Verify whether downstream steps consume MNP from ExtendedInfo or MNPInfo concept |

---

## §18 Full Source Code

```java
/**
 * @description
 * @author CHAYATORN-PC
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CRM_GET_LAST_ASSET_ROOT {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "CRM_GET_LAST_ASSET_ROOT";
        orderRequest.ProcessFlow.NextActivityID == "CRM_GET_LAST_ASSET_ROOT";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Activity nextAct = Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
            String chkXPath = nextAct.PreExecCheck;
            boolean isSkipped = true;

            /*** Begin ParentOU ***/
            for(int p=0; p<pOuLen; p++) {
                for(int ps=0; ps<pSubLen; ps++) {
                    psub = ParentOU[p].Subscriber[ps]; pSubRefId = psub.RefId;
                    /* resubmit guard: check Response[].ReferenceId + CompletionStatus==2 */
                    if(!reqSuccess) {
                        /* eval PreExecCheck if set */
                        if(chkRes == "true") {
                            customerAddressFlag = GetActivityParamValueFromKey(activity, "customerAddressFlag");
                            olprdDbFlag = GetActivityParamValueFromKey(activity, "OLPRD_DB_FLAG");
                            serviceId = psub.MSISDN;
                            refId = pSubRefId; // correct
                            /* [XSLT replaced — see §9.8] output: CRMGetLatestAssetRootRequest(serviceID, customerAddressFlag, olprdDBFlag) */
                            Event.Ext.sendEventImmediate(reqEvent);
                            isSkipped = false;
                            if(!isActResub) orderCurrentActivity.RequestCount++;
                            if(AllowWriteLog(orderType)) { /* send Logger */ }
                        }
                    }
                }
            }

            /*** Begin ChildOU ***/
            for(int c=0; c<cOuLen; c++) {
                for(int cs=0; cs<cSubLen; cs++) {
                    csub = ChildOU[c].Subscriber[cs]; cSubRefId = csub.RefId;
                    /* resubmit guard, PreExecCheck eval — same as ParentOU */
                    if(chkRes == "true") {
                        serviceId = csub.MSISDN;
                        refId = String.valueOfLong(System.nanoTime()); // ⚠️ BUG: should be cSubRefId
                        /* [XSLT identical to ParentOU — see §9.8] */
                        Event.Ext.sendEventImmediate(reqEvent);
                        isSkipped = false;
                        if(!isActResub) orderCurrentActivity.RequestCount++;
                        if(AllowWriteLog(orderType)) { /* send Logger */ }
                    }
                }
            }

            if(!isSkipped) {
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                SendDataToDB(orderRequest);
            } else {
                SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch(Exception ae) {
            HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

`Response_CRM_GET_LAST_ASSET_ROOT` is the most data-rich response handler in the PREPAID_CANCEL flow. Beyond the standard ResponseBase construction and fan-in completion check, it performs extensive enrichment of the OMX working memory from the CRM asset bean response — populating 15+ subscriber fields and 5+ customer fields.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order working memory to enrich |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CRM_GET_LAST_ASSET_ROOT` | Inbound CRM response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity for fan-in tracking |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object @extId ← ns:generateTrackingID()                         [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode               [Conditional: if exists]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg                [Conditional: if exists]
    ├── CompletionStatus ← $eventResponse/CompletionStatus           [Conditional: if exists]
    └── ReferenceId      ← $eventResponse/RefID                     [Conditional: if exists]
```

After construction: `currActivity.ResponseCode = eventResponse.ResponseCode`; `currActivity.ResponseMessage = eventResponse.ResponseMsg`.

### §19.4 Working Memory Enrichment

| Target Field | Source XPath | Condition |
|-------------|-------------|-----------|
| `CustomerCrmId` | `assetBeanList[1]/customerRowID` | Always |
| `DealerCode` | `assetBeanList[1]/prepaidDealerCode` | If blank |
| `CustomerTypeInfo.Type` | 80 (literal) | If productName=="Mobile Prepay" and blank |
| `CustomerGeneralInfo.Identification` | `individual/idNumber` | If blank |
| `CustomerGeneralInfo.IdentificationType` | `individual/idType` (mapped: Thai ID→I, Personal Identity→P, Alien ID→A, Government ID→G, Monk ID→M, Driver License→E, Others→H) | If blank |
| `CustomerGeneralInfo.BirthDate` | `individual/birthDate` (parsed DateTime) | If blank |
| `sub.Status` | status: Active/Preactive/Dummy→65, Inactive→67, else→0 | Per RefId-matched subscriber |
| `sub.AssetCrmId` | `assetBeanList[1]/assetRowID` | If blank |
| `sub.IntergrationCrmId` | `assetBeanList[1]/assetNo` | If blank |
| `sub.SubscriberId` | `ccbsSubscriberID`/`assetRowID` per DefaultSubIdBy | Per globalVar |
| `sub.SubscriberType` | `assetBeanList[1]/companyCode` | If blank |
| `sub.SubscriberGeneralInfo.Language` | `preferLanguage`: THA→TH, ENU→EN | If blank |
| `sub.SubscriberGeneralInfo.InitActDate` | `xStartDate` (parsed DateTime) | If null and length>0 |
| `sub.SubscriberGeneralInfo.l9TmvServiceLevel` | `customerAccountBean/grading` | If blank |
| `sub.SubscriberGeneralInfo.l9TmvActDate` | `originalStartDate` (parsed DateTime) | If null and length>0 |
| `sub.SubscriberName.{Title,FirstName,LastName}` | `individual.{title,firstName,lastName}` | If blank |
| `sub.SubscriberAddress` | `addressList[1]` (12 fields) | If null AND OrderType ≠ "12011" |
| `sub.AccountManagementInfo.AccountSubType` | "PRE" (literal) | If productName=="Mobile Prepay" |
| `sub.SubscriberOffers[CARRYS01].ParameterInfo` | `lastMainBalance` → "Monetary quota" | If OfferName=="CARRYS01" |
| `sub.ExtendedInfo[DONOR_OPERATOR/DONOR_ZONE/REC_OPERATOR/REC_ZONE]` | MNP info fields | If non-blank and not already set |

> For `OrderType=="35"` (PREPAID cancel path), response RF also enriches `CustomerName` and `CustomerAddress` at the customer level.

### §19.5 Response Completion Logic

| Expression | Purpose |
|-----------|---------|
| `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` | Count successful responses |
| `currActivity.RequestCount == successResponseCount` | Fan-in: all parallel CRM calls returned success |
| Returns `"true"` | All subscribers processed; activity can complete |
| Returns `"false"` | Still waiting for remaining subscriber responses |

### §19.6 Response Audit Log

Event: `Events.OMConsumers.OMXESB.Logger` — **always sent (no AllowWriteLog gate)**

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"CRM_GET_LAST_ASSET_ROOT"` |
| AUDIT_TRACE | `"Response received for CRM_GET_LAST_ASSET_ROOT"` |
| payload | `$eventResponse` (if WritePayload="true") |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
