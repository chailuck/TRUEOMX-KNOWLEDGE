# Request_ASRM_GET_UR_DETAILS_MSISDN

ASRM — Get Unified Resource Details for MSISDN (NiceLevel, Zone, TRUE_RES, DonorOperator, CompanyCode)

**Priority:** 5 | **forwardChain:** true | **Target:** ASRM (Amdocs RM3G) | **Pattern:** Per-subscriber fan-out | **Author:** chch | **PREPAID_CANCEL Step:** 4

---

## §1 — Overview & Purpose

> **Event type ≠ FM name:** The underlying TIBCO event type is `ASRM_GET_UNIFIED_RESOURCE_DETAILS`, which is a generic ASRM resource lookup event. The FM name `ASRM_GET_UR_DETAILS_MSISDN` specifies that the lookup entity type is always "MSISDN". A separate FM exists for SIM lookups.

`Request_ASRM_GET_UR_DETAILS_MSISDN` queries the ASRM (Amdocs Resource Manager 3G) system for unified resource details about a subscriber's MSISDN. For each subscriber in the order (ParentOU and ChildOU), one `ASRM_GET_UNIFIED_RESOURCE_DETAILS` event is sent containing the MSISDN as the lookup key.

The response enriches each subscriber with:
- **NiceLevel** — premium/vanity number classification from ASRM
- **Zone** — geographic pricing zone (RECIPIENT_ZONE preferred over ZONE for MNP; defaults to "1" if blank)
- **TRUE_RES** — whether the MSISDN belongs to TRUE's own network: "Y" or "N" (defaults to "N" if blank)
- **DonorOperator** — the original operator for MNP Port In/Out Reversal orders
- **CompanyCode** — mapped from RECIPIENT_OPERATOR (preferred) or COMPANY attribute

| Property | Value |
|----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_ASRM_GET_UR_DETAILS_MSISDN` |
| Author | chch |
| Backend system | ASRM (Amdocs Resource Manager 3G) |
| ASRM operation | GetUnifiedResourceDetails (entity type: MSISDN) |
| Underlying event | `Events.OMConsumers.OMXFM.Request.ASRM_GET_UNIFIED_RESOURCE_DETAILS` |
| Fan-out pattern | Per-subscriber (ParentOU + ChildOU) — one event per MSISDN |
| Correlation | `RefID` header field ← subscriber `RefId` |
| In PREPAID_CANCEL | Step 4 (ASRM_GET_UR_DETAILS_MSISDN) |
| Response concept | `Concepts.FM.Response.ASRM_GetURDetailsRes` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | `5` | Standard FM request priority |
| forwardChain | `true` | Re-evaluates when working memory changes |
| Rule type | Per-subscriber fan-out | Sends one event per subscriber with non-blank MSISDN |
| Source path | `Rules/OMConsumers/OMXFM/Request/Request_ASRM_GET_UR_DETAILS_MSISDN.rule` | |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order; source of all subscriber MSISDNs |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process activity; holds RequestCount and collected Response[] concepts |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to process flow |
| 2 | `orderCurrentActivity.ActivityID == "ASRM_GET_UR_DETAILS_MSISDN"` | FM-specific gate |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "ASRM_GET_UR_DETAILS_MSISDN"` | Double-check from order side |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Prevents double-firing |

---

## §5 — Execution Flow Diagram

1. **Re-submit check** — `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. **Load nextAct** — `Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")` for PreExecCheck access
3. **ParentOU subscriber loop** — for each subscriber:
   - Skip if MSISDN is blank
   - Skip if `Response[RefId==refId].CompletionStatus==2` already (re-submit dedup)
   - Evaluate PreExecCheck per subscriber (`GetXMLForSubscriber`)
   - If passes: send `ASRM_GET_UNIFIED_RESOURCE_DETAILS` event; increment RequestCount; audit log
4. **ChildOU subscriber loop** — same logic using `GetXMLForSubscriberInChildOU` for PreExecCheck
5. **Status update** — if any event sent: Status="1" + SendDataToDB; else SkipActivity("4")
6. **Exception** — catch → HandleActivityException

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

> **Re-submit dedup:** Before sending a new event, the rule checks whether a successful response (CompletionStatus==2) already exists in `currActivity.Response[]` for this subscriber's RefId. This prevents duplicate ASRM calls when an order is resubmitted.

> **[LOW] ChildOU XSLT variant:** `UserName` is emitted if `IsEnableUserPass='true'` without an inner null guard on `$orderRequest/OrderData/User`. The ParentOU variant wraps UserName in `<xsl:if test="$orderRequest/OrderData/User">`. If the User field is absent, the ChildOU variant sends an empty `<UserName/>` element.

```java
for(int j=0; j<iSubCnt; j++) {
  String currMSISDN = subscriber[j].MSISDN;
  if(BRMS.IsBlank(currMSISDN)) continue;  // skip missing MSISDN

  String refId = subscriber[j].RefId;
  boolean reqSuccess = false;
  for(iResp ...) // check existing Response[] for CompletionStatus==2 for this refId
    if(Response[iResp].ReferenceId == refId && CompletionStatus==2) reqSuccess = true;
  if(reqSuccess) continue;  // skip if already answered

  // Evaluate PreExecCheck per subscriber
  String chkRes = "true";
  if(nextAct.PreExecCheck.length > 0)
    chkRes = XPath.execute("/("+PreExecCheck+")", GetXMLForSubscriber(orderRequest, refId), ns);

  if(chkRes == "true") {
    reqEvent = Event.createEvent("xslt://...");
    // → payload: RMEntityIdInfo(Type="MSISDN", Value=currMSISDN)
    Event.Ext.sendEventImmediate(reqEvent);
    if(!isActResub) orderCurrentActivity.RequestCount++;
    isSkipped = false;
    if(AllowWriteLog) sendAuditLog(...);
  }
}
```

---

## §7 — Data Extraction

| Source | Field | Purpose |
|--------|-------|---------|
| Subscriber concept | `Subscriber[j].MSISDN` | Lookup key sent as `ns:Value` |
| Subscriber concept | `Subscriber[j].RefId` | Correlation key sent as event header `RefID` |
| Static | "MSISDN" | Entity type sent as `ns:Type` |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in any order that needs MSISDN metadata. In PREPAID_CANCEL (step 4): fires for each subscriber with a non-blank MSISDN, subject to the step's PreExecCheck.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel / Destination | Protocol | Purpose |
|-----------|-----------------------|----------|---------|
| [OUTBOUND] | OMXFM / ASRM_GET_UNIFIED_RESOURCE_DETAILS | JMS | Per-subscriber MSISDN resource detail lookup |
| [LOG] | OMXESB / Logger | JMS | REQ: gated by AllowWriteLog; RES: also gated by AllowWriteLog |

### §8.3 — Backend API Details

| System | Operation | Entity Type | Schema Namespace | Correlation |
|--------|-----------|-------------|-----------------|-------------|
| ASRM (Amdocs RM3G) | GetUnifiedResourceDetails | MSISDN | `amdocs.rm3g.interfaces.datatypes.RMEntityIdInfo` | `RefID` event header ← subscriber RefId |

Response schema: `amdocs.rm3g.interfaces.datatypes.UnifiedResourceDetailsInfo` with `CategoryInfo` and `AttributesInfo` sub-elements.

### §8.4 — BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `ParentOU[i].Subscriber[j].MSISDN` | READ | Lookup key — skipped if blank |
| `ParentOU[i].Subscriber[j].RefId` | READ | Correlation key; also used for re-submit dedup |
| `ChildOU[k].Subscriber[j].MSISDN / RefId` | READ | Same as ParentOU |
| `Subscriber[j].ResourceInfo[]` | WRITE | MSISDN_NICE_LEVEL, MSISDN_ZONE, MSISDN_TRUE_RES appended |
| `Subscriber[j].ExtendedInfo[]` | WRITE | DONOR_OPERATOR, COMPANY_CODE appended conditionally |
| `currActivity.Response[]` | WRITE | `ASRM_GetURDetailsRes` concept appended per response |

### §8.5 — ExtendedInfo Fields

| Key | Source in ASRM Response | Condition |
|-----|------------------------|-----------|
| `DONOR_OPERATOR` | `AttributesInfo[AttrName="DONOR_OPERATOR"]/AttrValue` | Only set if ASRM value non-empty AND subscriber doesn't already have DONOR_OPERATOR |
| `COMPANY_CODE` | RECIPIENT_OPERATOR (preferred) or COMPANY attribute | Set if either RECIPIENT_OPERATOR or COMPANY exists in response |

### §8.6 — Global Variable Dependencies

| Global Variable Path | Used for |
|----------------------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | If "true": include UserName/PassWord in event header |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `OMX_OM/WritePayload` | Gates payload inclusion in audit log |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | BE Source | Notes |
|------------|-----------|-------|
| `$orderRequest` | `orderRequest` | Full order concept |
| `$refId` | `subscriber.RefId` | Subscriber correlation key; put into `<RefID>` header field |
| `$globalVariables` | BE global variables | IsEnableUserPass, WritePayload |
| `$currMSISDN` | `subscriber.MSISDN` | Lookup value for `<ns:Value>` |

### §9.2 — Event Container

Event: `Events.OMConsumers.OMXFM.Request.ASRM_GET_UNIFIED_RESOURCE_DETAILS`. No auto-generated extId on the event element.

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition | Variant diff |
|-------|--------|-----------|-------------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Conditional | Same |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Conditional | Same |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Conditional | Same |
| `RefID` | `$refId` | **Always** — correlation key | Same |
| `UserName` | `$orderRequest/OrderData/User` | If IsEnableUserPass="true" AND User present | **[BUG]** ChildOU omits User-present inner guard |
| `PassWord` | `$orderRequest/OrderData/Password` | If IsEnableUserPass="true" AND Password present | Same (both have inner guard) |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Conditional | Same |

### §9.4 — Payload Root

Namespace: `www.tibco.com/plugin/java/xmlSchema/amdocs.rm3g.interfaces.datatypes.RMEntityIdInfo` (prefix: `ns`)  
Root element: `<ns:RMEntityIdInfo>`

### §9.5 — Core Payload Fields

| Element | Source | Condition |
|---------|--------|-----------|
| `ns:Type` | Static: `"MSISDN"` | Always |
| `ns:Value` | `$currMSISDN` | Always |

### §9.6 — Two XSLT Variants (ParentOU vs ChildOU)

| Element | ParentOU Variant | ChildOU Variant |
|---------|-----------------|----------------|
| `UserName` | Outer IsEnableUserPass guard + inner `if(User)` guard | Outer IsEnableUserPass guard only — missing inner null guard |

### §9.7 — Complete Generated XML Example

```xml
<event>
  <JMSPriority>4</JMSPriority>
  <JMSCorrelationID>OMX-TRK-20250720-001</JMSCorrelationID>
  <OrderID>1000001</OrderID>
  <RefID>SUB-REF-001</RefID>   <!-- always present — correlation key -->
  <OrderType>35041</OrderType>
  <payload>
    <ns:RMEntityIdInfo xmlns:ns="...RMEntityIdInfo">
      <ns:Type>MSISDN</ns:Type>
      <ns:Value>0812345678</ns:Value>
    </ns:RMEntityIdInfo>
  </payload>
</event>
```

### §9.8 — XSLT Stylesheet Source

```xml
<xsl:stylesheet version="1.0"
  xmlns:ns="www.tibco.com/plugin/java/xmlSchema/amdocs.rm3g.interfaces.datatypes.RMEntityIdInfo">
  <xsl:param name="orderRequest"/>   <!-- full order concept -->
  <xsl:param name="refId"/>          <!-- subscriber RefId -->
  <xsl:param name="globalVariables"/>
  <xsl:param name="currMSISDN"/>     <!-- subscriber MSISDN -->
  <xsl:template match="/">
    <createEvent><event>
      <xsl:if test="$orderRequest/OrderPriority"><JMSPriority>...</JMSPriority></xsl:if>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId"><JMSCorrelationID>...</JMSCorrelationID></xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderID"><OrderID>...</OrderID></xsl:if>
      <RefID><xsl:value-of select="$refId"/></RefID>  <!-- always -->
      <!-- ParentOU variant: -->
      <xsl:if test="$globalVariables/IsEnableUserPass='true'">
        <xsl:if test="$orderRequest/OrderData/User"><UserName>...</UserName></xsl:if>
        <xsl:if test="$orderRequest/OrderData/Password"><PassWord>...</PassWord></xsl:if>
      </xsl:if>
      <!-- ChildOU variant: UserName lacks inner User null-guard [BUG] -->
      <xsl:if test="$orderRequest/OrderData/OrderType"><OrderType>...</OrderType></xsl:if>
      <payload>
        <ns:RMEntityIdInfo>
          <ns:Type>MSISDN</ns:Type>   <!-- static -->
          <ns:Value><xsl:value-of select="$currMSISDN"/></ns:Value>
        </ns:RMEntityIdInfo>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority        ← $orderRequest/OrderPriority                   [Conditional]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId         [Conditional]
    ├── OrderID            ← $orderRequest/OrderData/OrderID                [Conditional]
    ├── RefID              ← $refId (subscriber RefId)                      [Always] correlation key for fan-in
    ├── UserName           ← $orderRequest/OrderData/User                   [Credential-gated]
    │                                            ParentOU: outer+inner guard; ChildOU: outer guard only [BUG]
    ├── PassWord           ← $orderRequest/OrderData/Password               [Credential-gated] both variants inner guard
    ├── OrderType          ← $orderRequest/OrderData/OrderType              [Conditional]
    └── payload                                                             [Always]
        └── ns:RMEntityIdInfo
            ├── ns:Type    ← static "MSISDN"                               [Always]
            └── ns:Value   ← $currMSISDN                                   [Always]
```

**Legend:** `[Always]` = unconditionally emitted; `[Conditional]` = inside xsl:if; `[Credential-gated]` = behind IsEnableUserPass global var

---

## §11 — Audit Logging

| Phase | Gate | PROCESS_ID | AUDIT_TRACE | Payload |
|-------|------|------------|-------------|---------|
| Request | `AllowWriteLog(OrderType)` | `concat(pid, "_REQ")` | "Request Sent for ASRM_GET_UR_DETAILS_MSISDN" | `$reqEvent` (if WritePayload="true") |
| Response | `AllowWriteLog(OrderType)` | `concat(pid, "_RES")` | "Response received for ASRM_GET_UR_DETAILS_MSISDN" | `$eventResponse` (if WritePayload="true") |

---

## §12 — Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one event sent | "1" → PROCESSING | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| No qualifying subscribers | "4" → SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception | ERROR | `HandleActivityException(...)` |

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
  RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 — Helper Functions Reference

| Function | Purpose | Notes |
|----------|---------|-------|
| `GetXMLForSubscriber` | Serialise a ParentOU subscriber to XML for PreExecCheck evaluation | Request rule |
| `GetXMLForSubscriberInChildOU` | Serialise a ChildOU subscriber to XML for PreExecCheck | Includes parent OU RefId |
| `BRMS.IsBlank` | Null/empty guard on MSISDN and response fields | Skips blank MSISDNs |
| `AllowWriteLog` | Gates both request and response audit logs | Consistent across both sides |
| `GetActivityStatusString` | Formats status string | |
| `SendDataToDB` | Persists order state to database | |
| `SkipActivity` | Skips with reason code "4" | |
| `HandleActivityException` | Standard exception handler | |
| `OMXUtils.generateTrackingID` | Generates extId for ASRM_GetURDetailsRes concept | Response RF |
| `XPath.evalAsBoolean` | Guards for DonorOperator, CompanyCode creation | Response RF |
| `XPath.evalAsInt` | Fan-in count | Response RF |

---

## §15 — Function Dependency Tree

```text
Request_ASRM_GET_UR_DETAILS_MSISDN (rule)
├── Instance.getByExtIdByUri [load nextAct for PreExecCheck]
├── BRMS.IsBlank [MSISDN null guard]
├── [per subscriber] Response[] scan [re-submit dedup guard]
├── RuleFunctions.Helpers.GetXMLForSubscriber [ParentOU PreExecCheck]
│   └── XPath.execute [evaluate PreExecCheck expression]
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU [ChildOU PreExecCheck]
│   └── XPath.execute [evaluate PreExecCheck expression]
├── Event.Ext.sendEventImmediate [ASRM_GET_UNIFIED_RESOURCE_DETAILS per subscriber]
│   └── XSLT: params(orderRequest, refId, globalVariables, currMSISDN)
│        → event(RefID [always], JMSPriority?, JMSCorrelationID?, OrderID?, UserName?, PassWord?, OrderType?)
│        → payload: ns:RMEntityIdInfo(Type="MSISDN", Value=currMSISDN)
├── RuleFunctions.Helpers.AllowWriteLog
│   └── Event.Ext.sendEventImmediate [OMXESB Logger REQ]
├── RuleFunctions.Helpers.GetActivityStatusString("1")
├── RuleFunctions.Helpers.SendDataToDB
└── RuleFunctions.Helpers.HandleActivityException (on error)

Response_ASRM_GET_UR_DETAILS_MSISDN (rulefunction)
├── OMXUtils.generateTrackingID [extId for ASRM_GetURDetailsRes]
├── Instance.createInstance [Concepts.FM.Response.ASRM_GetURDetailsRes]
│   └── XSLT maps: ResponseCode, ResponseMessage, CompletionStatus, ReferenceId,
│        URType, URValue, NiceLevel, DonorOperator,
│        Zone (RECIPIENT_ZONE preferred → else ZONE) [OMX-2270 fix],
│        TrueResource
├── currActivity.Response[] ← gurRes
├── [for each subscriber matching gurRes.URValue == MSISDN]
│   ├── Instance.getByExtIdByUri("SUBRI:...MSISDN_NICE_LEVEL") → create if null and NiceLevel not blank
│   ├── Instance.getByExtIdByUri("SUBRI:...MSISDN_ZONE") → create if null (default "1")
│   ├── Instance.getByExtIdByUri("SUBRI:...MSISDN_TRUE_RES") → create if null (default "N")
│   ├── XPath.evalAsBoolean [DonorOperator non-empty AND subscriber.ExtendedInfo[DONOR_OPERATOR] empty]
│   │   └── Instance.createInstance [SubscriberExtendedInfo DONOR_OPERATOR]
│   ├── XPath.evalAsBoolean [RECIPIENT_OPERATOR attribute exists in response]
│   │   └── Instance.createInstance [SubscriberExtendedInfo COMPANY_CODE ← RECIPIENT_OPERATOR]
│   └── else XPath.evalAsBoolean [COMPANY attribute exists in response]
│       └── Instance.createInstance [SubscriberExtendedInfo COMPANY_CODE ← COMPANY]
├── RuleFunctions.Helpers.AllowWriteLog
│   └── Event.Ext.sendEventImmediate [OMXESB Logger RES]
├── XPath.evalAsInt [count(Response[tib:right(ResponseCode,3)="000"])]
└── return "true" if RequestCount == successResponseCount; else "false"
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Fields |
|---------|-----------|
| `Concepts.FM.Response.ASRM_GetURDetailsRes` | extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, URType, URValue, NiceLevel, DonorOperator, Zone, TrueResource |
| `Concepts.OrderRequest.OrderElements.Subscriber` | MSISDN, RefId, @extId, ResourceInfo[], ExtendedInfo[] |
| `Concepts.OrderRequest.OrderElements.ResourceInfo` | ResourceName, ValuesArray; extId pattern: `SUBRI:{subExtId}:{eventRefId}:{resourceName}` |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` | Name, Value; extId pattern: `SUBEXT:{subExtId}:{eventRefId}:{infoName}` |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Send one ASRM GetUnifiedResourceDetails request per subscriber (ParentOU + ChildOU) with non-blank MSISDN; evaluate per-subscriber PreExecCheck before sending |
| R2 | Skip subscribers that already have a successful response (CompletionStatus==2) with their RefId — re-submit deduplication |
| R3 | Payload: `RMEntityIdInfo(Type="MSISDN", Value=currMSISDN)`; header: `RefID=subscriber.RefId` |
| R4 | Response: populate MSISDN_NICE_LEVEL ResourceInfo (skip if NiceLevel blank) |
| R5 | Response: populate MSISDN_ZONE ResourceInfo; default to "1" if Zone is blank (OMX-2270: prefer RECIPIENT_ZONE over ZONE) |
| R6 | Response: populate MSISDN_TRUE_RES ResourceInfo; default to "N" if TrueResource is blank |
| R7 | Response: set DONOR_OPERATOR ExtendedInfo only if ASRM returns non-empty DonorOperator AND subscriber does not already have DONOR_OPERATOR |
| R8 | Response: set COMPANY_CODE ExtendedInfo from RECIPIENT_OPERATOR attribute (preferred) or COMPANY attribute (fallback) |
| R9 | Fan-in: all requests done when `count(Response[ResponseCode ends in "000"]) == RequestCount` |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| ChildOU XSLT variant: UserName sent as empty tag when User field absent and IsEnableUserPass="true" | [LOW] | Add inner `if($orderRequest/OrderData/User)` guard to ChildOU variant, matching ParentOU behaviour |
| Three commented-out code blocks: old Zone-only logic (pre-OMX-2270), unused ASRM_DONOR_ZONE ExtendedInfo, old DONOR_OPERATOR extId using OMXTrackingId | [LOW] | Remove dead code; document OMX-2270 change in migration notes |
| ASRM_DONOR_ZONE ExtendedInfo commented out "not use right now" — intended feature never activated | [LOW] | Remove entirely or implement properly with a parameter gate if ever needed |
| COMPANY_CODE priority: RECIPIENT_OPERATOR checked first, then COMPANY — undocumented precedence rule | [LOW] | Document explicitly; verify current ASRM sends only one or the other |
| Zone default "1" and TrueResource default "N" are silent — no log when default is applied | [LOW] | Add debug log when default value is applied for observability |

---

## §18 — Full Source Code

```java
/**
 * @description get MSISDN information from ASRM
 *   Nice number
 *   Donor operator for MNP Port In/Out Reversal order
 *   Zone
 *   True_res=Y/N
 * @author chch
 */
rule Rules.OMConsumers.OMXFM.Request.Request_ASRM_GET_UR_DETAILS_MSISDN {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "ASRM_GET_UR_DETAILS_MSISDN";
    orderRequest.ProcessFlow.NextActivityID == "ASRM_GET_UR_DETAILS_MSISDN";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    String operationName = orderCurrentActivity.ActivityID;
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      boolean isSkipped = true;
      Concepts.OM.ProcessConfig.Activity nextAct =
        Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");

      // ParentOU subscriber loop
      int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
      for(int i=0; i<iPOULen; i++) {
        int iSubCnt = orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length;
        for(int j=0; j<iSubCnt; j++) {
          String currMSISDN = ...ParentOU[i].Subscriber[j].MSISDN;
          if(BRMS.IsBlank(currMSISDN)) continue;
          String refId = ...ParentOU[i].Subscriber[j].RefId;

          // Re-submit dedup
          boolean reqSuccess = false;
          for(int iResp=0; iResp<orderCurrentActivity.Response@length; iResp++)
            if(Response[iResp].ReferenceId==refId && Response[iResp].CompletionStatus==2)
              reqSuccess = true;
          if(reqSuccess) continue;

          // Per-subscriber PreExecCheck
          String chkRes = "true";
          if(nextAct.PreExecCheck.length > 0) {
            String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId);
            chkRes = XPath.execute("/("+PreExecCheck+")", sXML, ns);
          }

          if(chkRes.equals("true")) {
            Events...ASRM_GET_UNIFIED_RESOURCE_DETAILS reqEvent = Event.createEvent("xslt://...");
            // → See §9.8 for XSLT (params: orderRequest, refId, globalVariables, currMSISDN)
            // → payload: ns:RMEntityIdInfo(Type="MSISDN", Value=currMSISDN)
            // → header: RefID=refId [always], JMSPriority/CorrelationID/OrderID [conditional]
            Event.Ext.sendEventImmediate(reqEvent);
            if(!isActResub) orderCurrentActivity.RequestCount++;
            isSkipped = false;
            if(AllowWriteLog) sendAuditLog_REQ(...);
          }
        }

        // ChildOU subscriber loop — same logic; uses GetXMLForSubscriberInChildOU
        // ChildOU XSLT variant has UserName null-guard bug [LOW]
      }

      if(!isSkipped) {
        orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
        RuleFunctions.Helpers.SendDataToDB(orderRequest);
      } else {
        RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
      }
    } catch (Exception ae) {
      RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_ASRM_GET_UR_DETAILS_MSISDN` receives a single ASRM response per subscriber, creates an `ASRM_GetURDetailsRes` concept, then enriches the matching subscriber with up to three ResourceInfo items (MSISDN_NICE_LEVEL, MSISDN_ZONE, MSISDN_TRUE_RES) and up to two ExtendedInfo items (DONOR_OPERATOR, COMPANY_CODE).

> **OMX-2270 Zone fix:** The current code uses an `xsl:choose` to prefer `RECIPIENT_ZONE` over `ZONE`. The original code (commented out) always used `ZONE` directly. The RECIPIENT_ZONE is set for MSISDN numbers that have been ported (MNP), ensuring the zone reflects the port destination.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order; subscriber hierarchy to enrich |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.ASRM_GET_UNIFIED_RESOURCE_DETAILS` | ASRM reply; contains UnifiedResourceDetailsInfo |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity; receives ASRM_GetURDetailsRes concepts; holds RequestCount |

### §19.3 — ResponseBase Concept Construction (ASRM_GetURDetailsRes)

```text
createObject
└── object  extId ← OMXUtils.generateTrackingID()                                      [Always]
    ├── ResponseCode         ← $eventResponse/ResponseCode                              [Conditional]
    ├── ResponseMessage      ← $eventResponse/ResponseMsg                               [Conditional]
    ├── CompletionStatus     ← $eventResponse/CompletionStatus                         [Conditional]
    ├── ReferenceId          ← $eventResponse/RefID                                    [Conditional] matches subscriber.RefId
    ├── URType               ← UnifiedResourceIdInfo/ns1:Type                          [Conditional]
    ├── URValue              ← UnifiedResourceIdInfo/ns1:Value                         [Conditional] matches subscriber.MSISDN
    ├── NiceLevel            ← CategoryInfo[CategoryType="NICE_LEVEL"]/CategoryValueId [Always] string() wrap
    ├── DonorOperator        ← AttributesInfo[AttrName="DONOR_OPERATOR"]/AttrValue     [Conditional]
    ├── Zone                 ← xsl:choose: RECIPIENT_ZONE else ZONE [OMX-2270]         [Always] may be empty
    └── TrueResource         ← AttributesInfo[AttrName="TRUE_RES"]/AttrValue           [Always] may be empty
```

### §19.4 — Subscriber Enrichment

| Item Created | extId Pattern | Name | Value | Condition |
|-------------|---------------|------|-------|-----------|
| ResourceInfo MSISDN_NICE_LEVEL | `SUBRI:{subExtId}:{RefId}:MSISDN_NICE_LEVEL` | MSISDN_NICE_LEVEL | gurRes.NiceLevel | Only if null AND NiceLevel not blank |
| ResourceInfo MSISDN_ZONE | `SUBRI:{subExtId}:{RefId}:MSISDN_ZONE` | MSISDN_ZONE | gurRes.Zone if non-empty; else **"1"** | Only if null (always creates) |
| ResourceInfo MSISDN_TRUE_RES | `SUBRI:{subExtId}:{RefId}:MSISDN_TRUE_RES` | MSISDN_TRUE_RES | gurRes.TrueResource if non-empty; else **"N"** | Only if null (always creates) |
| ExtendedInfo DONOR_OPERATOR | `SUBEXT:{subExtId}:{RefId}:DONOR_OPERATOR` | DONOR_OPERATOR | gurRes.DonorOperator | DonorOperator non-empty AND subscriber not already has it |
| ExtendedInfo COMPANY_CODE (RECIPIENT_OPERATOR) | `SUBEXT:{subExtId}:{RefId}:COMPANY_CODE` | COMPANY_CODE | RECIPIENT_OPERATOR AttrValue | If RECIPIENT_OPERATOR attribute exists |
| ExtendedInfo COMPANY_CODE (COMPANY) | `SUBEXT:{subExtId}:{RefId}:COMPANY_CODE` | COMPANY_CODE | COMPANY AttrValue | Else-if: if COMPANY attribute exists |

### §19.5 — Fan-in Completion Logic

| Element | Value |
|---------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Returns | `"true"` when all subscriber responses succeeded; `"false"` while waiting |

### §19.6 — Response Audit Logging

Gated by `AllowWriteLog(OrderType)`. PROCESS_ID suffix "_RES". OPERATION_NAME = "ASRM_GET_UR_DETAILS_MSISDN". Payload: copy-of `$eventResponse` (if WritePayload="true").

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
