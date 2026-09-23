# Request_OMX_RESOLVE_SOC_DATA

> Batch SOC data resolution — aggregate all unique offer names across the entire order, fire a single request, then enrich the orderRequest with resolved package metadata.

**Target:** OMX FM Service | **Pattern:** Batch/Aggregate + Data Enrichment | **forwardChain:** true | **Author:** RS33-BANDIT

---

## §1 Overview & Purpose

This FM resolves detailed SOC (Service Offer Code) package metadata for every unique offer name referenced in the order. It collects all unique SOC names from Agreement Offers, SubscriberOffers, and RelatedOffersArrays for all POU and COU levels, deduplicates them using a Java ArrayList, and fires **one single batch request event**. The response handler then writes resolved metadata (ServiceType, RevenueType, OfferRate, DataInfo, IR flag) back into every matching offer entry in the orderRequest.

> **Architectural pattern:** Unlike per-subscriber fan-out FMs, this FM uses a **batch/aggregate pattern** — one request covers all SOC names simultaneously. RequestCount is always 1 (unless resubmit). Fan-in checks `RequestCount == Response.length` rather than counting "000" successes.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_OMX_RESOLVE_SOC_DATA.rule` | Rules/OMConsumers/OMXFM/Request/ |
| Response file | `Response_OMX_RESOLVE_SOC_DATA.rulefunction` | RuleFunctions/OrderResponse/ |
| Author | RS33-BANDIT | |
| forwardChain | `true` | BE re-evaluates all rule conditions after firing |
| Request event | `Events.OMConsumers.OMXFM.Request.OMX_RESOLVE_SOC_DATA` | |
| Response event | `Events.OMConsumers.OMXFM.Response.OMX_RESOLVE_SOC_DATA` | |
| Request schema NS | `http://services.omx.truecorp.co.th/ResolveSocDataRequest` | |
| Response schema NS | `http://services.omx.truecorp.co.th/ResolveSocDataResponse` | |
| Response concept | `Concepts.FM.Response.OMX_ResolveSocDataRes` | NOT ResponseBase — custom with SocData[] array |
| RefID level | Customer-level | `$orderRequest/OrderData/Customer/RefId` |
| Credential gate | IsEnableUserPass | Adds UserName/PassWord headers when enabled |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Read for offer lists; written with SOC metadata by response |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Activity tracking state |

> No `globalVariables` in declare block — accessed dynamically via `System.getGlobalVariableAsString()`.

---

## §4 Rule Conditions (WHEN)

> **Explicit WHEN block** (same 4-condition pattern as OMX_BRMS_DB). Combined with `forwardChain=true`, prevents re-entry after firing.

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity instance to process position |
| 2 | `orderCurrentActivity.ActivityID == "OMX_RESOLVE_SOC_DATA"` | Type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_RESOLVE_SOC_DATA"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be in WAITING state |

---

## §5 Execution Flow Diagram

```
1. PreExecCheck gate → skip if isSkipped (SkipActivity("4"))
2. Resubmit check → PurgePendingRequestsBeforeResubmit if isActResub
3. Obtain nextAct → Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")
4. Initialize collection → Collections.List.createArrayList()
5. 4-pass SOC name aggregation (POU Agreement / POU Subscriber / COU Agreement / COU Subscriber)
   └── For each offer: PreExecCheck per-offer helper + Collections.contains dedup + Collections.List.add
   └── Also loop RelatedOffersArray for each offer
6. Build single batch request event via XSLT (xsl:for-each over $socNames/elements → ns:SocName[])
7. Event.Ext.sendEventImmediate(reqEvent) → fire one event with all SOC names
8. if !isActResub → RequestCount++ (always results in RequestCount=1)
9. Queued audit log via Event.sendEvent() (NOT sendEventImmediate)
10. if !isSkipped → GetActivityStatusString("1", false) + SendDataToDB(orderRequest)
11. Collections.clear(arrLstSOCs)
[catch] → HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
```

---

## §6 Rule Action (THEN)

### §6.1 — SOC Name Collection (4-Pass Deduplication)

| Pass | Source Path | PreExecCheck Helper | Also Collects |
|------|-------------|---------------------|---------------|
| ① | `ParentOU[i].Agreement.Offers[j].OfferName` | `GetXMLForAgreementOffer(orderRequest, pAgreeRefId, socName)` | `RelatedOffersArray[].OfferName` |
| ② | `ParentOU[i].Subscriber[j].SubscriberOffers[k].OfferName` | `GetXMLForSubscriberOffer(orderRequest, pSubRefId, socName)` | `RelatedOffersArray[].OfferName` |
| ③ | `ParentOU[i].ChildOU[ci].Agreement.Offers[j].OfferName` | `GetXMLForAgreementOfferInChildOU(orderRequest, cAgreeRefId, socName, pOuRefId)` | `RelatedOffersArray[].OfferName` |
| ④ | `ParentOU[i].ChildOU[ci].Subscriber[j].SubscriberOffers[k].OfferName` | `GetXMLForSubscriberOfferInChildOU(orderRequest, cSubRefId, socName, pOuRefId)` | `RelatedOffersArray[].OfferName` |

Deduplication: `if (!Collections.contains(arrLstSOCs, socName)) { Collections.List.add(arrLstSOCs, socName); }`

### §6.2 — Single Batch Event Dispatch

| Element | Value |
|---------|-------|
| Event type | `Events.OMConsumers.OMXFM.Request.OMX_RESOLVE_SOC_DATA` |
| Send method | `Event.Ext.sendEventImmediate(reqEvent)` — synchronous immediate |
| RequestCount | Incremented once (if !isActResub) — always results in RequestCount = 1 |
| RefID header | `$orderRequest/OrderData/Customer/RefId` — customer-level |
| SOC names | `xsl:for-each select="$socNames/elements"` → multiple `<ns:SocName>` elements |

### §6.3 — Resubmit Guard

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
if (isActResub) {
    PurgePendingRequestsBeforeResubmit(orderCurrentActivity); // clear stale responses
    // RequestCount NOT incremented
}
```

---

## §7 Data Extraction

```java
Collections.List arrLstSOCs = Collections.List.createArrayList();

// For each offer source loop:
String socName = offer.OfferName;
if (!Collections.contains(arrLstSOCs, socName)) {
    preExecCheckXML = GetXMLForSubscriberOffer(orderRequest, pSubRefId, socName);
    Collections.List.add(arrLstSOCs, socName);
}
// Also loop RelatedOffersArray and add unique names

// Cleanup:
Collections.clear(arrLstSOCs);
```

---

## §8 System & Integration Dependencies

### §8.1 — Order Type Dependencies

Fires for **all order types** — no order-type branching. The batch event carries an `OrderType` header for backend use.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Purpose |
|-----------|---------|-------------|---------|
| [OUTBOUND] | OMX FM JMS | OMX_RESOLVE_SOC_DATA queue | Batch SOC name resolution request |
| [INBOUND] | OMX FM JMS | OMX_RESOLVE_SOC_DATA response queue | Resolved SOC data (SocData[] array) |
| [LOG] | OMXESB Logger | Audit log event (queued) | Request and response audit trail |

### §8.3 — Backend API Details

| Field | Value |
|-------|-------|
| System | OMX FM (internal service) |
| Request schema | `http://services.omx.truecorp.co.th/ResolveSocDataRequest` |
| Response schema | `http://services.omx.truecorp.co.th/ResolveSocDataResponse` |
| Request root | `ns:ResolveSocDataRequest` |
| Response root | `ns:ResolveSocDataResponse / ns:ResolveSocData[]` |
| Correlation | RefID (customer-level) echoed in response `RefID` field |
| Send pattern | Single batch — ONE request for ALL SOC names |

### §8.4 — BE Working Memory Dependencies

| Concept | Field Path | Access | Notes |
|---------|-----------|--------|-------|
| OrderRequest | `Customer.ParentOU[].Agreement.Offers[].OfferName` | READ | SOC name collection |
| OrderRequest | `Customer.ParentOU[].Subscriber[].SubscriberOffers[].OfferName` | READ | SOC name collection |
| OrderRequest | `Customer.ParentOU[].ChildOU[].Agreement.Offers[].OfferName` | READ | SOC name collection |
| OrderRequest | `Customer.ParentOU[].ChildOU[].Subscriber[].SubscriberOffers[].OfferName` | READ | SOC name collection |
| OrderRequest | `[All above].RelatedOffersArray[].OfferName` | READ | Related SOC names also collected |
| OrderRequest | `[All Offers].ServiceType / RevenueType / OfferRate / DataInfo` | WRITTEN | Populated by response handler |
| OrderRequest | `[SubscriberOffers].ExtendedInfo[] (IR_DATA)` | WRITTEN | Added when ServiceType == "87" |
| Activity | `RequestCount / Response[] / Status` | READ+WRITTEN | Fan-out/fan-in tracking |

### §8.5 — ExtendedInfo Fields Required

| Name | Value | Set Where | Condition |
|------|-------|-----------|-----------|
| `IR_DATA` | "Y" | SubscriberOffers.ExtendedInfo[] | ServiceType == "87" (IR service) |

### §8.6 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | If "true" → add UserName/PassWord headers |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit log COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit log TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit log LOG_LEVEL |
| `OMX_OM/WritePayload` | If "true" → include payload in response audit log |

---

## §9 Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| Parameter | Bound From |
|-----------|-----------|
| `$orderRequest` | Working memory: full OrderRequest concept |
| `$socNames` | Serialized ArrayList of unique SOC name strings |
| `$globalVariables` | BE global variables tree |

### §9.2 — Event Container Fields

| Field | Source | Condition |
|-------|--------|-----------|
| extId | `OMXUtils:generateTrackingID()` | Always |
| RefID header | `$orderRequest/OrderData/Customer/RefId` | Always |
| OrderType header | `$orderRequest/OrderData/OrderType` | Conditional |
| UserName header | global UserName | IsEnableUserPass == "true" |
| PassWord header | global PassWord | IsEnableUserPass == "true" |

### §9.3 — Request Payload Fields

| XML Element | Source | Notes |
|-------------|--------|-------|
| `ns:RefId` | `$orderRequest/OrderData/Customer/RefId` | Customer-level correlation ID |
| `ns:OMXTrackingId` | `$orderRequest/OrderData/OMXTrackingId` | End-to-end tracking |
| `ns:MSISDN` | orderRequest MSISDN | Conditional |
| `ns:OrderType` | `$orderRequest/OrderData/OrderType` | Conditional |
| `ns:SocName` (×N) | `$socNames/elements` via xsl:for-each | One per unique SOC name |

### §9.4 — Complete Generated XML Example

```xml
<ns:ResolveSocDataRequest xmlns:ns="http://services.omx.truecorp.co.th/ResolveSocDataRequest">
  <ns:RefId>CUST-12345</ns:RefId>
  <ns:OMXTrackingId>OMX-TRK-20250804-001</ns:OMXTrackingId>
  <ns:OrderType>3</ns:OrderType>
  <ns:SocName>SOC_PACKAGE_A</ns:SocName>
  <ns:SocName>SOC_PACKAGE_B</ns:SocName>
  <ns:SocName>SOC_RELATED_X</ns:SocName>
</ns:ResolveSocDataRequest>
```

### §9.5 — XSLT Output Tree

```text
createEvent
└── event @extId ← OMXUtils:generateTrackingID()                     [Always]
    ├── RefID         ← $orderRequest/OrderData/Customer/RefId        [Always]
    ├── UserName      ← global UserName                               [Credential-gated: IsEnableUserPass="true"]
    ├── PassWord      ← global PassWord                               [Credential-gated: IsEnableUserPass="true"]
    └── payload
        └── ns:ResolveSocDataRequest
            ├── ns:RefId         ← $orderRequest/OrderData/Customer/RefId   [Always]
            ├── ns:OMXTrackingId ← $orderRequest/OrderData/OMXTrackingId    [Always]
            ├── ns:MSISDN        ← $orderRequest/OrderData/MSISDN           [Conditional]
            ├── ns:OrderType     ← $orderRequest/OrderData/OrderType        [Conditional]
            └── ns:SocName (×N)  ← $socNames/elements (xsl:for-each)       [Repeated: one per SOC name]
```

---

## §10 XSLT Field Mapping

See §9.5 above for full output tree hierarchy.

---

## §11 Audit Logging

### Request Audit

| Field | Value |
|-------|-------|
| AUDIT_TRACE | `"Request Sent for OMX_RESOLVE_SOC_DATA"` (static) |
| OPERATION_NAME | `"OMX_RESOLVE_SOC_DATA"` |
| Send method | `Event.sendEvent()` — queued (NOT immediate) |
| Audit payload | `xsl:copy-of select="$reqEvent"` — copies request event |

> Audit uses `Event.sendEvent()` (queued), while the business event uses `Event.Ext.sendEventImmediate()`. Audit delivery is asynchronous.

### Response Audit

| Field | Value |
|-------|-------|
| AUDIT_TRACE | `concat("Response received for OMX_RESOLVE_SOC_DATA, RefId: ", $eventResponse/RefID)` — DYNAMIC |
| OPERATION_NAME | `"OMX_RESOLVE_SOC_DATA"` |
| PROCESS_ID | `concat($pid, "_RES")` |
| Send method | `Event.Ext.sendEventImmediate()` — immediate |
| AllowWriteLog gate | None — response audit always fires |
| payload | copy of `$eventResponse` (gated by `WritePayload="true"`) |

---

## §12 Activity Status Management

| Condition | Call | Status Code | Effect |
|-----------|------|-------------|--------|
| Normal send (not skipped) | `GetActivityStatusString("1", false)` + `SendDataToDB(orderRequest)` | "1" | Activity RUNNING; persisted to DB |
| isSkipped == true | `SkipActivity("4")` | "4" | Activity bypassed |

---

## §13 Exception / Error Handling

```java
try {
    // ... entire rule body ...
} catch (Exception ae) {
    HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 Helper Functions Reference

| Function | Return Type | Purpose |
|----------|-------------|---------|
| `GetXMLForAgreementOffer(orderRequest, refId, socName)` | String (XML) | Serializes POU Agreement offer for PreExecCheck |
| `GetXMLForSubscriberOffer(orderRequest, refId, socName)` | String (XML) | Serializes POU Subscriber offer for PreExecCheck |
| `GetXMLForAgreementOfferInChildOU(orderRequest, refId, socName, pOuRefId)` | String (XML) | Serializes COU Agreement offer for PreExecCheck |
| `GetXMLForSubscriberOfferInChildOU(orderRequest, refId, socName, pOuRefId)` | String (XML) | Serializes COU Subscriber offer for PreExecCheck |
| `PurgePendingRequestsBeforeResubmit(activity)` | void | Clears stale pending requests before resubmit |
| `GetActivityStatusString(code, flag)` | String | Returns status string for activity state update |
| `SendDataToDB(orderRequest)` | void | Persists current order state to database |
| `SkipActivity(code)` | void | Marks activity as skipped |
| `HandleActivityException(orderRequest, activity, ae, msg)` | void | Standard exception handler |
| `IndentifySocDataServiceType(packageCat, dataType)` | String | **Response-side:** derives serviceType code from packageCat + dataType |
| `IsBlankOrStringNull(value)` | boolean | **Response-side:** null/blank guard (in RuleFunctions.Helpers.BRMS) |

---

## §15 Function Dependency Tree

```text
Request_OMX_RESOLVE_SOC_DATA (rule)
├── Collections.List.createArrayList()
├── Collections.contains(arrLstSOCs, socName)
├── Collections.List.add(arrLstSOCs, socName)
├── GetXMLForAgreementOffer(orderRequest, pAgreeRefId, socName)
├── GetXMLForSubscriberOffer(orderRequest, pSubRefId, socName)
├── GetXMLForAgreementOfferInChildOU(orderRequest, cAgreeRefId, socName, pOuRefId)
├── GetXMLForSubscriberOfferInChildOU(orderRequest, cSubRefId, socName, pOuRefId)
├── Instance.getByExtIdByUri(extId, conceptPath)
├── PurgePendingRequestsBeforeResubmit(orderCurrentActivity)  [if isActResub]
├── Event.Ext.sendEventImmediate(reqEvent)
├── Event.sendEvent(auditEvent)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity("4")                                          [if isSkipped]
├── Collections.clear(arrLstSOCs)
└── HandleActivityException(orderRequest, activity, ae, "")   [catch]

Response_OMX_RESOLVE_SOC_DATA (rulefunction)
├── Instance.createInstance("xslt://{{/Concepts/FM/Response/OMX_ResolveSocDataRes}}")
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(value)
├── RuleFunctions.Helpers.IndentifySocDataServiceType(packageCat, dataType)
├── Number.doubleValue(price)
├── String.equals(a, b)
├── Instance.createInstance("xslt://{{AgreementDataInfo}}")    [if DataInfo==null, Agreement]
├── Instance.createInstance("xslt://{{SubscriberDataInfo}}")   [if DataInfo==null, Subscriber]
├── Instance.createInstance("xslt://{{SubscriberOffersExtendedInfo}}")  [if ServiceType=="87"]
├── System.nanoTime()
└── Event.Ext.sendEventImmediate(auditLogEvent)
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields | Role |
|---------|-----------|------|
| `Concepts.FM.Response.OMX_ResolveSocDataRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, SocData[] | Response holder with SOC data array |
| `OMX_ResolveSocDataRes.SocData` | PackageCode, PackageCat, PackageType, ChargeType, Company, Price, DataType, TssDisplayType | Per-SOC resolved metadata |
| `Concepts.OrderRequest.OrderElements.AgreementDataInfo` | Package, ChargeType, PackType | Created/updated on Agreement Offers |
| `Concepts.OrderRequest.OrderElements.SubscriberDataInfo` | Package, ChargeType, PackType | Created/updated on SubscriberOffers |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberOffersExtendedInfo` | Name, Value | IR_DATA flag |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Collect all unique SOC names (Agreement Offers + SubscriberOffers + RelatedOffersArrays) across all POU and COU levels before any backend call. |
| R2 | Fire exactly ONE batch request per FM execution. |
| R3 | Evaluate PreExecCheck per individual offer using the 4 helper serialization functions. |
| R4 | Response handler must distribute resolved metadata back to every matching offer in all 4 sources by PackageCode match. |
| R5 | Apply `IndentifySocDataServiceType(packageCat, dataType)` for serviceType — not a direct field copy. |
| R6 | OMX-2771 fix: if serviceType == "88" AND TssDisplayType == "ROAM" → override serviceType to "91". |
| R7 | Add IR_DATA=Y ExtendedInfo to SubscriberOffers when ServiceType resolves to "87". |
| R8 | Support IsEnableUserPass credential gate for UserName/PassWord headers. |
| R9 | Use customer-level RefId (not subscriber RefId) for correlation. |
| R10 | Fan-in: `RequestCount == Response.length` (always 1 vs 1). |
| R11 | Resubmit path must call PurgePendingRequestsBeforeResubmit and skip RequestCount increment. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Batch payload size — 50+ unique SOC names in one XML | [MEDIUM] | Add pagination/chunking for large orders in modern impl |
| Response enrichment O(S × O) loop complexity | [MEDIUM] | Modern impl: build HashMap\<socName, SocData\> from response, single pass over offers |
| TssDisplayType not populated by response XSLT — silently null | [MEDIUM] | Verify OMX-2771 fix ever triggers in practice; add test coverage |
| DataInfo null-check/create dual code path | [LOW] | Modern impl: merge into upsert operation |
| RelatedOffersArray ServiceType-only enrichment (not full metadata) | [LOW] | Confirm intentional; document in data contract |
| `forwardChain=true` + response-side orderRequest mutation | [HIGH] | Modern design: avoid in-place mutation; use immutable event flow |

---

## §18 Full Source Code

### Request_OMX_RESOLVE_SOC_DATA.rule

```java
/**
 * Request_OMX_RESOLVE_SOC_DATA
 * Author: RS33-BANDIT
 * Batch SOC data resolution — collect unique SOC names, fire single request
 */
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_RESOLVE_SOC_DATA {
  attribute {
    priority = 5;
    forwardChain = true;
  }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_RESOLVE_SOC_DATA";
    orderRequest.ProcessFlow.NextActivityID == "OMX_RESOLVE_SOC_DATA";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    try {
      Activity nextAct = Instance.getByExtIdByUri(
        orderRequest.ProcessFlow.NextActivityName,
        "/Concepts/OM/ProcessConfig/Activity");

      boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
      if (isActResub) { PurgePendingRequestsBeforeResubmit(orderCurrentActivity); }

      Collections.List arrLstSOCs = Collections.List.createArrayList();

      // Pass 1: POU Agreement Offers (+ RelatedOffersArray)
      // Pass 2: POU Subscriber SubscriberOffers (+ RelatedOffersArray)
      // Pass 3: COU Agreement Offers (+ RelatedOffersArray)
      // Pass 4: COU Subscriber SubscriberOffers (+ RelatedOffersArray)
      // [For each: PreExecCheck per-offer helper + Collections.contains dedup + Collections.List.add]
      // See §6 for full detail of each pass

      // Build and fire single batch event
      // [XSLT: ns:ResolveSocDataRequest with xsl:for-each over $socNames/elements → ns:SocName[]]
      // See §9.5 for full XSLT
      Event reqEvent = Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/OMX_RESOLVE_SOC_DATA}}...");
      Event.Ext.sendEventImmediate(reqEvent);

      if (!isActResub) { orderCurrentActivity.RequestCount++; }

      // Queued audit log (NOT sendEventImmediate)
      Event auditEvent = Event.createEvent("xslt://{{/Events/OMConsumers/OMXESB/Logger}}...");
      Event.sendEvent(auditEvent);

      if (!isSkipped) {
        GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else {
        SkipActivity("4");
      }

      Collections.clear(arrLstSOCs);

    } catch (Exception ae) {
      HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 Response Message Rule

### §19.1 — Overview

The response handler for OMX_RESOLVE_SOC_DATA performs two distinct functions:
1. **Parse response** — map `ResolveSocDataResponse` into `OMX_ResolveSocDataRes` concept with `SocData[]` array.
2. **Enrich orderRequest** — for each resolved SocData record, walk all 4 offer sources and write ServiceType, RevenueType, OfferRate, DataInfo, and IR flag back to every matching offer by PackageCode.

> **Most complex response handler in this FM set** — performs O(S × O) enrichment pass across the entire order structure.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | WRITTEN with enriched SOC metadata |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.OMX_RESOLVE_SOC_DATA | Backend response event |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Response[] appended; fan-in checked |

### §19.3 — ResponseBase Concept Construction (OMX_ResolveSocDataRes)

```text
createObject
└── object @extId ← OMXUtils:generateTrackingID()                          [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode                    [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg                     [Conditional] (source=ResponseMsg)
    ├── CompletionStatus  ← $eventResponse/CompletionStatus                [Conditional]
    ├── ReferenceId       ← $eventResponse/RefID                           [Conditional] (source=RefID)
    └── SocData (×N) @extId ← OMXUtils:generateTrackingID()               [xsl:for-each over ns:ResolveSocData]
        ├── PackageCode   ← ns:PackageCode                                 [Always]
        ├── PackageCat    ← ns:PackageCat                                  [Conditional]
        ├── PackageType   ← ns:PackageType                                 [Conditional]
        ├── ChargeType    ← ns:ChargeType                                  [Conditional]
        ├── Company       ← ns:Company                                     [Conditional]
        ├── Price         ← ns:Price                                       [Conditional]
        └── DataType      ← ns:DataType                                    [Conditional]
```

> **Field name asymmetries:** Source `ResponseMsg` → target `ResponseMessage`; source `RefID` → target `ReferenceId`. `TssDisplayType` is in the concept but NOT populated by response XSLT — defaults null.

### §19.4 — SOC Data Enrichment Logic

| Step | Logic |
|------|-------|
| 1. Filter | Skip SocData entries where PackageCat is blank/null |
| 2. Compute serviceType | `RuleFunctions.Helpers.IndentifySocDataServiceType(packageCat, dataType)` |
| 3. OMX-2771 override | If serviceType=="88" AND SocData.TssDisplayType=="ROAM" → serviceType="91" |
| 4. Compute rate | `rate = Number.doubleValue(SocData.Price)` if not blank; else 0.0 |
| 5. Match offers | 4-pass loop: POU Agreement → POU Subscriber → COU Agreement → COU Subscriber; match by `packageCode == offer.OfferName` |
| 6. Write metadata | ServiceType, RevenueType=packageType, OfferRate=rate; create or update DataInfo (Package, ChargeType, PackType) |
| 7. IR flag | If `offer.ServiceType == "87"` (SubscriberOffers only): append ExtendedInfo(Name="IR_DATA", Value="Y") |
| 8. RelatedOffers | Loop RelatedOffersArray; match by packageCode; write ServiceType ONLY (not full metadata) |

### §19.5 — Fan-in Completion Logic

```java
// Append response concept to activity response array:
currActivity.Response[currActivity.Response@length] = activityRes;

// Fan-in check:
if (currActivity.RequestCount == currActivity.Response@length) {
    return "true";  // all responses received
} else {
    return "false"; // still waiting
}
```

> **Different from other FMs:** Uses `currActivity.Response@length` (total response count) NOT a count of ResponseCode "000" entries. Since only ONE event is sent (RequestCount=1), returns "true" immediately on first response regardless of ResponseCode.

### §19.6 — Response Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| PROCESS_ID | `concat($pid, "_RES")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `"OMX_RESOLVE_SOC_DATA"` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` |
| AUDIT_TRACE | `concat("Response received for OMX_RESOLVE_SOC_DATA, RefId: ", $eventResponse/RefID)` — includes RefID |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload/ns:ServicePayload | copy of `$eventResponse` — gated by `WritePayload="true"` |

### §19.7 — Response XSLT Source

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://services.omx.truecorp.co.th/ResolveSocDataResponse"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  version="1.0">
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <xsl:if test="$eventResponse/ResponseCode">
          <ResponseCode><xsl:value-of select="$eventResponse/ResponseCode"/></ResponseCode>
        </xsl:if>
        <xsl:if test="$eventResponse/ResponseMsg">
          <!-- source=ResponseMsg, target=ResponseMessage -->
          <ResponseMessage><xsl:value-of select="$eventResponse/ResponseMsg"/></ResponseMessage>
        </xsl:if>
        <xsl:if test="$eventResponse/CompletionStatus">
          <CompletionStatus><xsl:value-of select="$eventResponse/CompletionStatus"/></CompletionStatus>
        </xsl:if>
        <xsl:if test="$eventResponse/RefID">
          <!-- source=RefID, target=ReferenceId -->
          <ReferenceId><xsl:value-of select="$eventResponse/RefID"/></ReferenceId>
        </xsl:if>
        <!-- SocData array — one per ns:ResolveSocData element in response -->
        <xsl:for-each select="$eventResponse/payload/ns:ResolveSocDataResponse/ns:ResolveSocData">
          <SocData>
            <xsl:attribute name="extId">
              <xsl:value-of select="OMXUtils:generateTrackingID()"/>
            </xsl:attribute>
            <PackageCode><xsl:value-of select="ns:PackageCode"/></PackageCode>
            <xsl:if test="ns:PackageCat"><PackageCat><xsl:value-of select="ns:PackageCat"/></PackageCat></xsl:if>
            <xsl:if test="ns:PackageType"><PackageType><xsl:value-of select="ns:PackageType"/></PackageType></xsl:if>
            <xsl:if test="ns:ChargeType"><ChargeType><xsl:value-of select="ns:ChargeType"/></ChargeType></xsl:if>
            <xsl:if test="ns:Company"><Company><xsl:value-of select="ns:Company"/></Company></xsl:if>
            <xsl:if test="ns:Price"><Price><xsl:value-of select="ns:Price"/></Price></xsl:if>
            <xsl:if test="ns:DataType"><DataType><xsl:value-of select="ns:DataType"/></DataType></xsl:if>
          </SocData>
        </xsl:for-each>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
