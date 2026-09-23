# Request_SBM_CANCEL_PACK_PREPAID

**Backend:** SBM — DoService (function_id=100200052)  
**Priority:** 5 | **ForwardChain:** true | **Event:** SBM_3GPREPAID  
**Dispatch:** IntraActivitySequencing (sequential, not parallel)  
**Fan-out:** Per-offer per-subscriber (POU + COU) | **Fan-in:** ActionResponseEvent  
**Author:** Puttaporn-PC

---

## §1 — Overview & Purpose

This rule fires when `SBM_CANCEL_PACK_PREPAID` becomes the next activity. It sends one **SBM DoService** request per qualifying SubscriberOffer (POU and COU) to cancel a prepaid data pack via SBM's 3G prepaid service endpoint, using function code `100200052`.

Unlike most FMs that use `Event.Ext.sendEventImmediate` for parallel dispatch, this rule uses the **IntraActivitySequencing** pattern — requests are queued and dispatched **sequentially** via `Event.assertEvent + ActionRequestEvent + SendFirstRequestEvent`. The fan-in is also managed by IntraActivitySequencing rather than a manual ResponseCode or count check.

> **Integration method branching:** If `OrderData/IntegrationMethod = 'BATCH'`, credentials are sourced from the BATCH global variable path; otherwise from the ONLINE path.

> **Event type note:** Despite this being a POSTPAID Remove Offer flow, the request event type is `SBM_3GPREPAID`. This is the SBM DoService shared endpoint — the type name reflects the SBM service, not the subscriber type. Commented-out code shows an earlier `SBM_DO_SERVICE` event type was replaced.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_SBM_CANCEL_PACK_PREPAID` |
| Author | Puttaporn-PC |
| Priority | 5 |
| ForwardChain | true |
| Target backend | SBM — 3G Prepaid / DoService endpoint |
| Operation | DoService (function_id = **100200052**) |
| Payload schema (outer) | `http://services.omx.truecorp.co.th/FMServices/SBMDoserviceArrayRequest` (ns1) |
| Payload schema (inner) | `http://services.omx.truecorp.co.th/FMServices/SBMDoserviceRequest` (ns) |
| Request event type | `Events.OMConsumers.OMXFM.Request.SBM_3GPREPAID` |
| Response event type | `Events.OMConsumers.OMXFM.Response.SBM_3GPREPAID` |
| Response concept | `Concepts.FM.Response.SBM_DoServiceRes` (with nested DoServiceResponse) |
| Dispatch method | `Event.assertEvent + IntraActivitySequencing.ActionRequestEvent / SendFirstRequestEvent` (sequential) |
| Fan-out granularity | Per offer per subscriber (POU and COU) |
| Fan-in mechanism | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Batch mode | Credential path switches between BATCH and ONLINE based on IntegrationMethod |
| Skip trigger | No qualifying offers → SkipActivity("4") |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order concept; subscriber, offer, and order metadata |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step; IntraActivitySequencing queue, Response[], Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to order's next step |
| 2 | `orderCurrentActivity.ActivityID == "SBM_CANCEL_PACK_PREPAID"` | Rule fires only for this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SBM_CANCEL_PACK_PREPAID"` | Double-check on ProcessFlow routing |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be in waiting state before dispatch |

---

## §5 — Execution Flow

```
1.  Compute isActResub
2.  If isActResub: PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
3.  Resolve nextAct by extId; read PreExecCheck XPath
4.  Evaluate isBatch: check OrderData/IntegrationMethod = 'BATCH'
5.  Select app_user and app_password from BATCH or ONLINE global variable path
6.  POU loop: iterate ParentOU[i].Subscriber[j].SubscriberOffers[k]
7.  For each offer: compute offerRefId, read FE_OR_CCBS filter
8.  Resubmission skip: check Response[ReferenceId==offerRefId and CompletionStatus==2]
9.  If not already succeeded: evaluate PreExecCheck per-offer
10. If chkRes=="true": get channel via GetSBMServiceChannel(orderRequest, offer)
11. Build SBM_3GPREPAID event via XSLT (see §9); Event.assertEvent(reqEvent)
12. IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity) — queue the request
13. Send audit log via sendEventImmediate
14. COU loop: identical logic over ChildOU[x].Subscriber[y].SubscriberOffers[z]
15. If any requests queued: IntraActivitySequencing.SendFirstRequestEvent → dispatches first; Status="1", SendDataToDB
16. Else: SkipActivity("4")
17. On exception: HandleActivityException
```

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### IntraActivitySequencing pattern

This FM uses **sequential dispatch** via IntraActivitySequencing. All requests are first queued by `ActionRequestEvent`, then `SendFirstRequestEvent` triggers dispatch of the first one. When its response arrives, the response handler calls `ActionResponseEvent` which sends the next queued request. This continues until all are processed, at which point `ActionResponseEvent` returns `true` to signal completion.

This is fundamentally different from the `sendEventImmediate` fan-out pattern: requests are **not** sent in parallel.

### isBatch credential selection

| Condition | app_user path | app_password path |
|-----------|--------------|-------------------|
| `IntegrationMethod = 'BATCH'` | `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/BATCH/app_user` | `.../BATCH/app_password` |
| otherwise (ONLINE) | `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/ONLINE/app_user` | `.../ONLINE/app_password` |

### offerRefId format

| Scope | Format | Note |
|-------|--------|------|
| POU | `pOuRefId + ":" + ":" + refId + ":" + offer.OfferName` | Double colon — COU segment is empty string [MEDIUM] |
| COU | `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.OfferName` | Standard 4-segment format |

> **POU double-colon:** The POU offerRefId is `"pOuRefId::subRefId:offerName"` — the middle segment for cOuRefId is an empty string, creating a double colon. Response matching depends on this exact format for the resubmission skip to work. Likely intentional but surprising.

### billCycleNo dead reference

Variable `billCycleNo` is computed via `RuleFunctions.Helpers.ConvertBillCycleDate(...)` but is never passed to the XSLT. This is a dead reference — the value is unused in the payload. **[MEDIUM]**

### channel helper

`RuleFunctions.Helpers.GetSBMServiceChannel(orderRequest, offer)` resolves the SBM service channel string — passed as `$channel` → `ns:channel`.

### Status transitions

| Scenario | Action | Status |
|----------|--------|--------|
| At least one request queued | SendFirstRequestEvent, Status="1", SendDataToDB | Running |
| No qualifying offers | SkipActivity("4") | Skip |
| Exception | HandleActivityException | Error |

---

## §7 — Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| isBatch | `XPath: $orderRequest/OrderData/IntegrationMethod = 'BATCH'` | Boolean; drives credential path selection |
| app_user | Global variable BATCH or ONLINE path | SBM service credentials |
| app_password | Global variable BATCH or ONLINE path | SBM service credentials |
| offerRefId (POU) | `pOuRefId + ":" + ":" + refId + ":" + offer.OfferName` | Double-colon separator |
| offerRefId (COU) | `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.OfferName` | Standard 4-segment |
| filter | `$offer/ExtendedInfo[Name="FE_OR_CCBS"]/Value` | PreExecCheck filter |
| channel | `RuleFunctions.Helpers.GetSBMServiceChannel(orderRequest, offer)` | SBM service channel → ns:channel |
| billCycleNo | `RuleFunctions.Helpers.ConvertBillCycleDate(BillCycleNo)` | Computed but UNUSED in XSLT |
| Resubmission skip | `Response[ReferenceId==offerRefId and CompletionStatus==2]` | Per-offer skip check |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

No order-type-specific branching in the request logic. Integration method (BATCH vs ONLINE) drives credential selection.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Dispatch | Backend |
|-----------|------------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.SBM_3GPREPAID` | `Event.assertEvent + IntraActivitySequencing` | SBM — DoService (function_id=100200052) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `Event.Ext.sendEventImmediate` | Audit log sink (always logged) |

### §8.3 — Backend API Details

| System | Operation | function_id | Schema (outer) | Key Parameters |
|--------|-----------|-------------|----------------|----------------|
| SBM | DoService — Cancel Pack | `100200052` | `SBMDoserviceArrayRequest` (ns1) | package_code=OfferName, mode="sync", service_no=MSISDN, channel, waiting_mode="result" |

### §8.4 — BE Working Memory Dependencies

| Concept Field | Access | Purpose |
|--------------|--------|---------|
| `orderRequest.OrderData.IntegrationMethod` | READ | BATCH vs ONLINE credential selection |
| `orderRequest.OrderData.Customer.BillCycleNo` | READ | Converted to billCycleNo — but unused in payload |
| `subscriber.MSISDN` | READ | ns:service_no in SBM request |
| `subscriber.RefId` | READ | Used in offerRefId construction |
| `offer.OfferName` | READ | ns:parameters/package_code; offerRefId segment |
| `offer.ExtendedInfo[FE_OR_CCBS]/Value` | READ | PreExecCheck filter |
| `orderRequest.OrderData.OrderID` | READ | ns:req_transaction_id; JMS header OrderID |
| `orderRequest.OrderData.OMXTrackingId` | READ | JMSCorrelationID; audit log ESBUUID |
| `orderRequest.OrderPriority` | READ | JMSPriority (conditional) |
| `orderRequest.OrderData.OrderType` | READ | JMS header OrderType |
| `orderCurrentActivity.Response[]` | READ | Resubmission skip check |
| `orderCurrentActivity.Status` | WRITE | Set to "1" after first dispatch |

### §8.5 — ExtendedInfo Fields Required

| Name | Level | Required/Optional | Where Used |
|------|-------|-------------------|------------|
| FE_OR_CCBS | Offer | Optional | PreExecCheck filter parameter |

### §8.6 — Global Variable Dependencies

| Path | Usage |
|------|-------|
| `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/BATCH/app_user` | SBM credentials for batch mode |
| `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/BATCH/app_password` | SBM credentials for batch mode |
| `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/ONLINE/app_user` | SBM credentials for online mode |
| `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/ONLINE/app_password` | SBM credentials for online mode |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Guards payload in audit log |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Purpose |
|------------|------------|---------|
| `$orderRequest` | orderRequest concept | OrderID, OMXTrackingId, OrderType, OrderPriority |
| `$offerRefId` | computed offerRefId string | Correlation key; RefID in event header |
| `$app_password` | global var BATCH or ONLINE | SBM DoService credentials |
| `$app_user` | global var BATCH or ONLINE | SBM DoService credentials |
| `$channel` | GetSBMServiceChannel(orderRequest, offer) | SBM service channel name |
| `$offer` | current SubscriberOffers concept | OfferName → ns:parameters/package_code |
| `$msisdn` | subscriber.MSISDN | ns:service_no |

### §9.2 — Event Container Construction

No custom extId on the event. `RefID` in the event header carries the `offerRefId` correlation key.

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | If present |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | If present |
| OrderID | `$orderRequest/OrderData/OrderID` | If present |
| RefID | `$offerRefId` | Always — correlation key |
| OrderType | `$orderRequest/OrderData/OrderType` | If present |

### §9.4 — Payload Root Element

Root: `ns1:doServiceArrayRequest/ns1:DoServiceRequest` — wraps a single DoServiceRequest in the array container.

### §9.5 — Conditional Fields

All payload fields inside `ns1:DoServiceRequest` are always emitted. Only JMS header fields (JMSPriority, JMSCorrelationID, OrderID, OrderType) are conditional.

### §9.6 — SBM DoService Parameters

| ns:key | ns:value | Type |
|--------|----------|------|
| `package_code` | `$offer/OfferName` | Dynamic — offer being cancelled |
| `mode` | `"sync"` | Static literal |

| DoServiceRequest Field | Value | Type |
|------------------------|-------|------|
| `ns:app_password` | `$app_password` | From global var (BATCH/ONLINE) |
| `ns:app_user` | `$app_user` | From global var (BATCH/ONLINE) |
| `ns:channel` | `$channel` | From GetSBMServiceChannel helper |
| `ns:function_id` | `"100200052"` | Static — SBM cancel pack operation code |
| `ns:req_transaction_id` | `$orderRequest/OrderData/OrderID` | Order correlation ID |
| `ns:service_no` | `$msisdn` | Subscriber MSISDN |
| `ns:waiting_mode` | `"result"` | Static — synchronous result wait mode |

### §9.7 — Complete Generated XML Example

```xml
<!-- SBM_3GPREPAID event payload — one per qualifying offer -->
<createEvent><event>
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-12345</JMSCorrelationID>
  <OrderID>ORD-9876</OrderID>
  <RefID>POU-001::SUB-001:SOC_DATAPACK</RefID>  <!-- POU double-colon format -->
  <OrderType>1</OrderType>
  <payload>
    <ns1:doServiceArrayRequest
      xmlns:ns1="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceArrayRequest"
      xmlns:ns="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceRequest">
      <ns1:DoServiceRequest>
        <ns:app_password>sbm_pass_online</ns:app_password>
        <ns:app_user>sbm_user_online</ns:app_user>
        <ns:channel>OMX-WEB</ns:channel>
        <ns:function_id>100200052</ns:function_id>
        <ns:parameters>
          <ns:item>
            <ns:key>package_code</ns:key>
            <ns:value>SOC_DATAPACK</ns:value>
          </ns:item>
          <ns:item>
            <ns:key>mode</ns:key>
            <ns:value>sync</ns:value>
          </ns:item>
        </ns:parameters>
        <ns:req_transaction_id>ORD-9876</ns:req_transaction_id>
        <ns:service_no>0812345678</ns:service_no>
        <ns:waiting_mode>result</ns:waiting_mode>
      </ns1:DoServiceRequest>
    </ns1:doServiceArrayRequest>
  </payload>
</event></createEvent>
```

### §9.8 — XSLT Stylesheet Source

```xml
<!-- Request XSLT — SBM_3GPREPAID event; one per qualifying offer -->
<xsl:stylesheet
  xmlns:ns1="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceArrayRequest"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceRequest"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
  version="1.0">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>
  <xsl:param name="offerRefId"/>    <!-- correlation key -->
  <xsl:param name="app_password"/>
  <xsl:param name="app_user"/>
  <xsl:param name="channel"/>
  <xsl:param name="offer"/>         <!-- SubscriberOffers concept -->
  <xsl:param name="msisdn"/>        <!-- subscriber.MSISDN -->
  <xsl:template match="/">
    <createEvent><event>
      <xsl:if test="$orderRequest/OrderPriority">
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderID">
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      </xsl:if>
      <RefID><xsl:value-of select="$offerRefId"/></RefID>  <!-- always present -->
      <xsl:if test="$orderRequest/OrderData/OrderType">
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      </xsl:if>
      <payload>
        <ns1:doServiceArrayRequest><ns1:DoServiceRequest>
          <ns:app_password><xsl:value-of select="$app_password"/></ns:app_password>
          <ns:app_user><xsl:value-of select="$app_user"/></ns:app_user>
          <ns:channel><xsl:value-of select="$channel"/></ns:channel>
          <ns:function_id><xsl:value-of select="&quot;100200052&quot;"/></ns:function_id>
          <ns:parameters>
            <ns:item>
              <ns:key><xsl:value-of select="&quot;package_code&quot;"/></ns:key>
              <ns:value><xsl:value-of select="$offer/OfferName"/></ns:value>
            </ns:item>
            <ns:item>
              <ns:key><xsl:value-of select="&quot;mode&quot;"/></ns:key>
              <ns:value><xsl:value-of select="&quot;sync&quot;"/></ns:value>
            </ns:item>
          </ns:parameters>
          <ns:req_transaction_id><xsl:value-of select="$orderRequest/OrderData/OrderID"/></ns:req_transaction_id>
          <ns:service_no><xsl:value-of select="$msisdn"/></ns:service_no>
          <ns:waiting_mode><xsl:value-of select="&quot;result&quot;"/></ns:waiting_mode>
        </ns1:DoServiceRequest></ns1:doServiceArrayRequest>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent → event
├── JMSPriority         ← $orderRequest/OrderPriority                  [Conditional: if present]
├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId         [Conditional: if present]
├── OrderID             ← $orderRequest/OrderData/OrderID               [Conditional: if present]
├── RefID               ← $offerRefId                                   [Always]
├── OrderType           ← $orderRequest/OrderData/OrderType             [Conditional: if present]
└── payload
    └── ns1:doServiceArrayRequest
        └── ns1:DoServiceRequest
            ├── ns:app_password   ← $app_password (BATCH or ONLINE)    [Always]
            ├── ns:app_user       ← $app_user (BATCH or ONLINE)         [Always]
            ├── ns:channel        ← $channel (GetSBMServiceChannel)     [Always]
            ├── ns:function_id    ← "100200052" (static)                [Always]
            ├── ns:parameters
            │   ├── ns:item[1]: key="package_code" value=$offer/OfferName  [Always]
            │   └── ns:item[2]: key="mode" value="sync" (static)           [Always]
            ├── ns:req_transaction_id ← $orderRequest/OrderData/OrderID [Always]
            ├── ns:service_no     ← $msisdn (subscriber.MSISDN)         [Always]
            └── ns:waiting_mode   ← "result" (static)                   [Always]
```

**Legend:** `[Always]` = unconditional | `[Conditional: <condition>]` = emitted only when condition true

---

## §11 — Audit Logging

Audit log is always emitted (not gated by AllowWriteLog). Uses `Event.Ext.sendEventImmediate` directly (unlike the request dispatch which uses IntraActivitySequencing).

| Phase | Field | Value |
|-------|-------|-------|
| Request | ESBUUID | `$orderRequest/OrderData/OMXTrackingId` |
| Request | PROCESS_ID | `concat($pid, "_REQ")` |
| Request | OPERATION_NAME | "SBM_CANCEL_PACK_PREPAID" |
| Request | AUDIT_TRACE | "Request Sent for SBM_CANCEL_PACK_PREPAID" |
| Request | payload | Conditional: WritePayload="true" → copy of reqEvent |
| Response | PROCESS_ID | `concat($pid, "_RES")` |
| Response | OPERATION_NAME | "SBM_CANCEL_PACK_PREPAID " (note trailing space in source) |
| Response | AUDIT_TRACE | "Response received for SBM_CANCEL_PACK_PREPAID" |

---

## §12 — Activity Status Management

| Transition | Code | Trigger |
|------------|------|---------|
| Running | "1" | At least one offer request queued and first dispatched |
| Skip | "4" | No qualifying offers across all subscribers |
| Error | HandleActivityException | Any uncaught exception |

---

## §13 — Exception / Error Handling

Entire `then` block wrapped in `try { ... } catch (Exception ae) { HandleActivityException(...); }`. No debug output (commented out in source).

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears queued-but-unsent requests before a resubmission run |
| `IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)` | Adds request to the sequential dispatch queue |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Dispatches the first queued request |
| `IntraActivitySequencing.ActionResponseEvent(activity)` | Response handler: dispatches next request; returns true when all done |
| `RuleFunctions.Helpers.GetSBMServiceChannel(orderRequest, offer)` | Resolves SBM channel name based on order and offer context |
| `RuleFunctions.Helpers.ConvertBillCycleDate(BillCycleNo)` | Converts bill cycle number to date string — computed but unused in payload |
| `RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(...)` | POU per-offer PreExecCheck XML builder |
| `RuleFunctions.Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...)` | COU per-offer PreExecCheck XML builder |
| `RuleFunctions.Helpers.GetActivityStatusString("1", false)` | Returns status string for "Running" |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | Persists state to DB |
| `RuleFunctions.Helpers.SkipActivity(..., "4")` | Skip handler |
| `RuleFunctions.Helpers.HandleActivityException(...)` | Central exception handler |

---

## §15 — Function Dependency Tree

```text
Request_SBM_CANCEL_PACK_PREPAID.rule
├── XPath.evalAsBoolean(IntegrationMethod = 'BATCH') → isBatch
├── XPath.evalAsString(BATCH|ONLINE/app_user) → app_user
├── XPath.evalAsString(BATCH|ONLINE/app_password) → app_password
├── [if isActResub] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── [POU loop: ParentOU[i].Subscriber[j].SubscriberOffers[k]]
│   ├── Response[] resubmission skip check (CompletionStatus==2 + RefId match)
│   ├── RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(...)
│   ├── XPath.execute(chkXPath, sXML)  [if PreExecCheck set]
│   ├── [if chkRes=="true"]
│   │   ├── RuleFunctions.Helpers.ConvertBillCycleDate(BillCycleNo) → billCycleNo [unused!]
│   │   ├── RuleFunctions.Helpers.GetSBMServiceChannel(orderRequest, offer) → channel
│   │   ├── Event.createEvent(XSLT → SBM_3GPREPAID)    [see §9.8]
│   │   ├── Event.assertEvent(reqEvent)
│   │   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│   │   └── Event.Ext.sendEventImmediate(audit log)
├── [COU loop: ChildOU[x].Subscriber[y].SubscriberOffers[z]] — identical
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)
└── RuleFunctions.Helpers.HandleActivityException(...)
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Properties Used |
|---------|---------------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.Customer.ParentOU[], ChildOU[], OrderData.OrderID, OMXTrackingId, OrderType, IntegrationMethod, Customer.BillCycleNo, OrderPriority |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, SubscriberOffers[] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | OfferName, ExtendedInfo[FE_OR_CCBS] |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, Response[], PreExecCheck; IntraActivitySequencing queue |
| `Concepts.FM.Response.SBM_DoServiceRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, DoServiceResponse[] (nested) |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Send one SBM DoService (function_id=100200052) request per qualifying offer per subscriber (POU and COU) |
| R2 | Dispatch requests sequentially (not in parallel) — each must complete before the next is sent |
| R3 | Select BATCH or ONLINE credentials based on OrderData.IntegrationMethod |
| R4 | Evaluate PreExecCheck per-offer; skip already-successful offers on resubmission |
| R5 | Purge pending requests before resubmission to prevent duplicate dispatch |
| R6 | Pass package_code (OfferName), mode="sync", service_no (MSISDN), waiting_mode="result" to SBM |
| R7 | Fan-in: all queued requests must complete before activity is considered done |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| billCycleNo computed but never sent — dead reference; BillCycle data silently dropped | [MEDIUM] | Verify with SBM team whether bill cycle is needed; remove dead code or add as a parameter |
| POU offerRefId double-colon ("::") — resubmission skip and response matching depend on this exact format | [MEDIUM] | Verify that SBM response carries the same double-colon RefID; document explicitly in migration |
| Commented-out SBM_DO_SERVICE event type still in code — maintenance confusion | [LOW] | Remove dead commented-out code in migration |
| Sequential dispatch via IntraActivitySequencing increases total processing time (N×RTT vs max RTT for parallel) | [MEDIUM] | Evaluate whether SBM supports parallel DoService calls for the target platform |
| SBM 3GPREPAID event type used for POSTPAID remove flow — naming confusion could mask routing misconfiguration | [LOW] | Rename event type in migration to reflect actual target subscriber type |
| OPERATION_NAME in response audit log has trailing space: "SBM_CANCEL_PACK_PREPAID " | [LOW] | Fix trailing space in migration |

---

## §18 — Full Source Code (Request Rule)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_SBM_CANCEL_PACK_PREPAID {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "SBM_CANCEL_PACK_PREPAID";
    orderRequest.ProcessFlow.NextActivityID == "SBM_CANCEL_PACK_PREPAID";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
      boolean isBatch = XPath.evalAsBoolean(/* IntegrationMethod = 'BATCH' */);
      if (isActResub) {
        RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      }
      String app_user = isBatch ? XPath.evalAsString(/* BATCH/app_user */) : XPath.evalAsString(/* ONLINE/app_user */);
      String app_password = isBatch ? XPath.evalAsString(/* BATCH/app_password */) : XPath.evalAsString(/* ONLINE/app_password */);
      boolean isSkipped = true;
      /* POU loop: ParentOU[i].Subscriber[j].SubscriberOffers[k] */
      for (int i = 0; i < iPOULen; i++) {
        for (int j = 0; j < iSubscriberLen; j++) {
          for (int k = 0; k < qSubOffLen; k++) {
            String offerRefId = pOuRefId + ":" + ":" + refId + ":" + offer.OfferName; // double colon
            /* resubmission skip check */
            if (!reqSuccess) {
              /* PreExecCheck eval per-offer */
              if (String.equals(chkRes, "true")) {
                String billCycleNo = RuleFunctions.Helpers.ConvertBillCycleDate(...); // unused!
                String channel = RuleFunctions.Helpers.GetSBMServiceChannel(orderRequest, offer);
                Events.OMConsumers.OMXFM.Request.SBM_3GPREPAID reqEvent =
                  Event.createEvent(/* XSLT → ns1:doServiceArrayRequest — see §9.8 */);
                Event.assertEvent(reqEvent);
                RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                Event.Ext.sendEventImmediate(Event.createEvent(/* Logger — see §11 */));
                isSkipped = false;
              }
            }
          }
        }
        /* COU loop — identical logic */
      }
      if (!isSkipped) {
        RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
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

The response handler (`Response_SBM_CANCEL_PACK_PREPAID`) receives one `SBM_3GPREPAID` response event for each dispatched request (sequential, driven by IntraActivitySequencing). It creates a `SBM_DoServiceRes` concept (not ResponseBase) with a rich nested `DoServiceResponse` sub-object containing SBM-specific return fields. It returns "true" only after all queued requests have been processed.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order for audit log |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SBM_3GPREPAID` | SBM response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; IntraActivitySequencing controls next dispatch |

### §19.3 — ResponseBase Concept Construction

Response concept: `Concepts.FM.Response.SBM_DoServiceRes`. extId: `String extId = OMXUtils.generateTrackingID();` (Java direct call). Nested DoServiceResponse also has its own extId via `OMXUtils:generateTrackingID()` called in XSLT.

```text
createObject
└── object @extId ← OMXUtils.generateTrackingID() (Java direct call)    [Always]
    ├── ResponseCode          ← $eventResponse/ResponseCode              [Conditional: if present]
    ├── ResponseMessage       ← $eventResponse/ResponseMsg               [Conditional: if present]
    ├── CompletionStatus      ← $eventResponse/CompletionStatus          [Conditional: if present]
    ├── ReferenceId           ← $eventResponse/RefID                     [Conditional: if present]
    ├── DoServiceResponse @extId ← OMXUtils:generateTrackingID() (XSLT) [Conditional: CheckPackAllowReturn exists]
    │   ├── extra_xml         ← ns:CheckPackAllowReturn/ns1:extra_xml    [Conditional]
    │   ├── req_transaction_id ← ns:CheckPackAllowReturn/ns1:req_transaction_id [Conditional]
    │   ├── response_message  ← ns:CheckPackAllowReturn/ns1:response_message   [Conditional]
    │   ├── result_code       ← ns:CheckPackAllowReturn/ns1:result_code        [Conditional]
    │   ├── result_desc       ← ns:CheckPackAllowReturn/ns1:result_desc        [Conditional]
    │   ├── result_namespace  ← ns:CheckPackAllowReturn/ns1:result_namespace   [Conditional]
    │   └── transaction_id    ← ns:CheckPackAllowReturn/ns1:transaction_id     [Conditional]
    └── DoServiceResponse @extId ← OMXUtils:generateTrackingID() (XSLT) [Conditional: DoServiceReturn exists]
        └── (identical fields from ns:DoServiceReturn)
```

### §19.4 — Response Completion Logic (Fan-in)

| Expression | Value |
|------------|-------|
| Fan-in condition | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Returns "true" | All queued requests processed sequentially — no more pending |
| Returns "false" | Still pending requests; ActionResponseEvent dispatches the next one automatically |

> This fan-in is fundamentally different from other FMs: the IntraActivitySequencing framework both manages the request queue and signals completion. There is no explicit RequestCount or ResponseCode suffix check.

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | "SBM_CANCEL_PACK_PREPAID " (note trailing space) |
| AUDIT_TRACE | "Response received for SBM_CANCEL_PACK_PREPAID" |
| payload | Conditional: WritePayload="true" → copy of $eventResponse |

### §19.6 — Response XSLT Source

```xml
<!-- ResponseBase XSLT — Response_SBM_CANCEL_PACK_PREPAID -->
<xsl:stylesheet
  xmlns:ns1="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceResponse"
  xmlns:ns="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceArrayResponse"
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  version="1.0">
  <xsl:param name="extId"/>          <!-- from Java: OMXUtils.generateTrackingID() -->
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject><object>
      <xsl:attribute name="extId"><xsl:value-of select="$extId"/></xsl:attribute>
      <!-- ResponseCode, ResponseMsg→ResponseMessage, CompletionStatus, RefID→ReferenceId (all conditional) -->
      <xsl:if test="exists($eventResponse/payload/ns:doServiceArrayResponse/ns:CheckPackAllowReturn)">
        <DoServiceResponse>
          <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
          <!-- extra_xml, req_transaction_id, response_message, result_code, result_desc, result_namespace, transaction_id -->
        </DoServiceResponse>
      </xsl:if>
      <xsl:if test="exists($eventResponse/payload/ns:doServiceArrayResponse/ns:DoServiceReturn)">
        <DoServiceResponse>
          <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
          <!-- identical fields from ns:DoServiceReturn -->
        </DoServiceResponse>
      </xsl:if>
    </object></createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
