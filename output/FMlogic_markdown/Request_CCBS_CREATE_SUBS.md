# Request_CCBS_CREATE_SUBS

> CCBS Create Subscriber — Sequential Per-Subscriber Provisioning via IntraActivitySequencing

**Priority:** 5 | **forwardChain:** true | **Backend:** CCBS | **Author:** awalia-t420 | **Generated:** 2026-07-27

---

## §1 — Overview & Purpose

This rule fires when the order reaches `ActivityID = CCBS_CREATE_SUBS` and status `WAITING`. It provisions a new subscriber record in CCBS for each `Subscriber` in the order (across ParentOU and ChildOU levels) by sending a `createSubscriberRequest` per subscriber. The CCBS response returns the permanent `SubscriberId` (subscriber number) and `OfferInstanceId` values that are written back to working memory.

> **Critical architectural difference — IntraActivitySequencing:** Unlike ASRM/CCBS_GOD rules that use `Event.Ext.sendEventImmediate()` for parallel fan-out, this rule uses `Event.assertEvent()` + `IntraActivitySequencing.ActionRequestEvent()` per subscriber, then `IntraActivitySequencing.SendFirstRequestEvent()` at the end. This implements **sequential** subscriber processing — CCBS receives one subscriber at a time, and the next request is sent only after the previous response is received. Fan-in is driven by `IntraActivitySequencing.ActionResponseEvent(currActivity)` in the response handler.

**Per-subscriber context assembled before dispatch:**
- `subPP` — The subscriber's price plan offer (ServiceType='80' offer)
- `imeiExists` — XPath: `exists(ResourceInfo[ResourceName='IMEI'][1]) and not(exists(SubscriberOffers[Soc='55042'][1]))`
- `addDummy` — `Parameter[1]='ADD_DUMMY_IMEI'` flag for dummy IMEI injection
- `addRangeArray` — `ResourceRangeInfo[]` entries with `Action='ADD'` (BN number resource ranges)
- `logicalDateVal` — from `Concepts.OM.LogicalDate.LogicalDate`

**Response writes back two critical identifiers:**
- `subscriber.SubscriberId` — The permanent CCBS subscriber number, extracted from `CreateNewActivateSubscriberResponse/SubscriberIdsInfo/SubscriberId/SubscrNumber`
- `SubscriberOffers[o].OfferInstanceId` and `RelatedOffersArray[k].OfferInstanceId` — Matched by SOC code from the `ReopenedOffers[]` array in the response

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_CCBS_CREATE_SUBS` |
| Full Path | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CREATE_SUBS` |
| Priority | 5 |
| forwardChain | true |
| Rule Type | Sequential fan-out via IntraActivitySequencing — one createSubscriberRequest per subscriber |
| Author | awalia-t420 |
| Backend System | CCBS — Amdocs CSM 3G Subscriber Management |
| Operation | createSubscriberRequest / CreateNewActivateSubscriberResponse |
| Dispatch mechanism | Event.assertEvent + IntraActivitySequencing (sequential, not parallel fan-out) |
| Resubmission guard | Yes — per subscriber, checks CompletionStatus==2 |
| Resubmission purge | Yes — PurgePendingRequestsBeforeResubmit on isActResub |

---

## §3 — Working Memory — Declared Objects

| Variable | Type Path | Role |
|----------|-----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Master order — Subscriber hierarchy iterated; SubscriberId and OfferInstanceId written back |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | PreExecCheck, Parameter[1], IntraActivitySequencing queue, Response[] |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity to order execution point |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_CREATE_SUBS"` | Targets only this activity type |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_CREATE_SUBS"` | Order-level double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires on fresh/ready activity |

---

## §5 — Execution Flow Diagram

1. **Init** — `isActResub = (RequestCount>0 && IsOrderResubmitted)`; init `alSOCs`, `alPropVal` lists; read `LogicalDate`; if resubmit → `PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
2. **ParentOU Subscriber loop** — for each `Subscriber[j]`:
   - Resubmission guard: check `Response[].ReferenceId==refId && CompletionStatus==2`
   - If not already done: run per-subscriber PreExecCheck via `GetXMLForSubscriber(orderRequest, refId)`
   - If PreExecCheck passes: assemble per-subscriber context (subPP, imeiExists, addDummy, addRangeArray)
   - `Event.assertEvent(reqEvent)` + `IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)`
   - Send audit log; `isSkipped=false`
3. **ChildOU Subscriber loop** — same as step 2 using `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)`
4. **After all loops** — if not skipped: `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)` → fires the first queued request; set Status = IN_PROGRESS; SendDataToDB
5. **Skipped path** — if no subscribers dispatched: `SkipActivity(…, "4")` → SKIPPED
6. **Exception** — catch → `HandleActivityException` → ERROR

---

## §6 — Rule Action (THEN) — Key Logic

### IntraActivitySequencing Dispatch Pattern

```java
// For each subscriber that passes PreExecCheck:
Events.OMConsumers.OMXFM.Request.CCBS_CREATE_SUBS reqEvent =
    Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/CCBS_CREATE_SUBS}}" + /* XSLT */);

Event.assertEvent(reqEvent);                                 // queue into IntraActivitySequencing
// (NOT sendEventImmediate — queued for sequential dispatch)
RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);

// After ALL subscriber loops complete:
RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
// → sends ONLY the first queued event; subsequent events fire one-by-one as responses arrive
```

### Per-Subscriber Pre-Processing Checks

```java
// 1. subPP — price plan offer (ServiceType='80')
Concepts.OrderRequest.OrderElements.SubscriberOffers subPP = null;
for(int k=0; k<iSubOffLen; k++) {
    if(String.equals(SubscriberOffers[k].ServiceType, "80"))
        subPP = SubscriberOffers[k];  // last match wins
}

// 2. imeiExists — IMEI present but SOC 55042 (IMEI SOC) not yet on subscriber
boolean imeiExists = XPath.evalAsBoolean(
    "exists($sub/ResourceInfo[ResourceName='IMEI'][1]) and not(exists($sub/SubscriberOffers[Soc='55042'][1]))");

// 3. addDummy — ADD_DUMMY_IMEI parameter
boolean addDummy = XPath.evalAsBoolean(
    "$orderCurrentActivity/Parameter[1]='ADD_DUMMY_IMEI'");

// 4. addRangeArray — BN number resource ranges with Action='ADD'
Object addRangeInfos = Collections.List.createArrayList();
for(int r=0; r<sub.ResourceRangeInfo@length; r++) {
    if(String.equals("ADD", sub.ResourceRangeInfo[r].Action))
        Collections.add(addRangeInfos, sub.ResourceRangeInfo[r]);
}
```

---

## §7 — Data Extraction — Per-Subscriber Context Assembly

| Variable | Source | Purpose / Notes |
|----------|--------|----------------|
| `refId` | `Subscriber[j].RefId` | Correlation key — used in PreExecCheck XML context and as response ReferenceId |
| `subPP` | First `SubscriberOffers[k]` where `ServiceType='80'` | Price Plan offer — passed to XSLT; may be null if no PP offer on subscriber |
| `imeiExists` | XPath on `$sub`: `exists(ResourceInfo[ResourceName='IMEI']) and not(exists(SubscriberOffers[Soc='55042']))` | Controls IMEI field inclusion in payload; false if IMEI SOC already present |
| `addDummy` | `orderCurrentActivity.Parameter[1]='ADD_DUMMY_IMEI'` | If true, XSLT injects a dummy IMEI into the request |
| `addRangeArray` | `sub.ResourceRangeInfo[]` where `Action='ADD'` | BN (number) resource ranges to include in subscriber creation |
| `logicalDateVal` | `Concepts.OM.LogicalDate.LogicalDate` | Used for contract/service start date calculations in XSLT |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

| Scenario | Effect |
|----------|--------|
| isActResub=true (resubmit) | PurgePendingRequestsBeforeResubmit clears queued events; prior successful subscribers (CompletionStatus=2) skipped |
| ServiceType='80' offer on subscriber | `subPP` set → passed to XSLT for price plan context in subscriber creation |
| `ResourceInfo[ResourceName='IMEI']` exists without SOC 55042 | IMEI included in CCBS request payload (`imeiExists=true`) |
| `Parameter[1]='ADD_DUMMY_IMEI'` | Dummy IMEI value injected into request |
| `ResourceRangeInfo[].Action='ADD'` present | Number ranges passed to CCBS for BN subscriber creation |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel URI | Event Type | Purpose |
|-----------|-------------|------------|---------|
| [OUTBOUND (queued)] | `/Channels/OMXFMConnectionRequest` | `Events.OMConsumers.OMXFM.Request.CCBS_CREATE_SUBS` | Create subscriber in CCBS — sequential per-subscriber |
| [OUTBOUND] | `/Channels/LogConnection` | `Events.OMConsumers.OMXESB.Logger` | Request audit per subscriber |

### §8.3 — Backend API Details

| Attribute | Value |
|-----------|-------|
| System | CCBS — Amdocs CSM 3G Subscriber Management |
| Operation | createSubscriberRequest / CreateNewActivateSubscriberResponse |
| Request schema namespace | `http://services.omx.truecorp.co.th/FMServices/createSubscriberRequest` |
| Response schema namespace | `http://services.omx.truecorp.co.th/FMServices/createSubscriberResponse` |
| Key response element | `ns:createSubscriberResponse/ns:CreateNewActivateSubscriberResponse` |
| SubscriberId source | `ns:SubscriberIdsInfo/ns:SubscriberId/ns:SubscrNumber` |
| OfferInstanceId source | `ns:ReopenedOffers[]/ns:NewOfferInstanceId` matched by `ns:Soc` |
| Response concept | `Concepts.FM.Response.CCBSCreateSubsRes` (has SocInstance[] array) |
| Dispatch mechanism | **Sequential** via IntraActivitySequencing (assertEvent, not sendEventImmediate) |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` → true when all queued requests responded |

### §8.4 — BE Working Memory Dependencies

| Field / Path | Direction | Phase | Purpose |
|--------------|-----------|-------|---------|
| `Subscriber[j].RefId` | [READ] | Request | Correlation key; passed to XSLT and used as ReferenceId |
| `Subscriber[j].SubscriberOffers[k].ServiceType` | [READ] | Request | Find price plan (='80') |
| `Subscriber[j].ResourceInfo[ResourceName='IMEI']` | [READ] | Request | imeiExists gate |
| `Subscriber[j].SubscriberOffers[Soc='55042']` | [READ] | Request | IMEI SOC already present check |
| `Subscriber[j].ResourceRangeInfo[].Action` | [READ] | Request | BN number range entries for dispatch |
| `Concepts.OM.LogicalDate.LogicalDate` | [READ] | Request | Logical date for XSLT date fields |
| `orderCurrentActivity.Parameter[1]` | [READ] | Request | ADD_DUMMY_IMEI flag |
| `orderCurrentActivity.Response[].ReferenceId / CompletionStatus` | [READ] | Request | Resubmission guard |
| `Subscriber[j].SubscriberId` | [WRITE] | Response | Permanent CCBS subscriber number |
| `Subscriber[j].ResponseCode` | [WRITE] | Response | CCBS response code for this subscriber |
| `Subscriber[j].ResponseMsg` | [WRITE] | Response | CCBS response message |
| `Subscriber[j].SubscriberOffers[o].OfferInstanceId` | [WRITE] | Response | CCBS offer instance ID, matched by SOC code |
| `SubscriberOffers[o].RelatedOffersArray[k].OfferInstanceId` | [WRITE] | Response | CCBS offer instance ID for related offers, matched by SOC |
| `orderCurrentActivity.Status` | [WRITE] | Request | IN_PROGRESS or SKIPPED |

### §8.5 — XSLT Parameters for createSubscriberRequest

| Parameter | Bound From | Notes |
|-----------|------------|-------|
| `$orderRequest` | Working memory concept | Full order tree |
| `$globalVariables` | BE global variables | Credentials, logging config |
| `$sub` | `Subscriber[j]` | The specific subscriber being created in this call |
| `$subPP` | `SubscriberOffers where ServiceType='80'` | Price plan offer; may be null |
| `$logicalDate` | `Concepts.OM.LogicalDate.LogicalDate` | Logical date string |
| `$imeiExists` | XPath boolean result | Controls IMEI payload inclusion |
| `$addDummy` | XPath boolean on Parameter[1] | Controls dummy IMEI injection |
| `$addRangeArray` | `ResourceRangeInfo[] where Action='ADD'` | BN number ranges for subscriber |
| `$refId` | `Subscriber[j].RefId` | Correlation key for JMS correlation |

### §8.6 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Include User/Password in request |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_OM/WritePayload` | Include payload in audit |

---

## §9 — Detailed Payload Build

### §9.1 — Key JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | If exists |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | If exists |
| `RefId` | `$refId` (= Subscriber.RefId) | Always — subscriber correlation key |
| `OrderID` | `$orderRequest/OrderData/OrderID` | If exists |
| `UserName / PassWord` | `$orderRequest/OrderData/User / Password` | IsEnableUserPass='true' |
| `OrderType` | `$orderRequest/OrderData/OrderType` | If exists |

### §9.2 — Request Payload Structure (createSubscriberRequest)

> **Schema:** `http://services.omx.truecorp.co.th/FMServices/createSubscriberRequest`
> The payload wraps a `ns:createSubscriberRequest` containing:
> - `ns:CreateNewActivateSubscriberRequest` — main subscriber object with MSISDN, IMSI, SIM ICC-ID
> - Subscriber profile fields from orderRequest (MSISDN, plan, IMEI if imeiExists/addDummy)
> - Price plan offer details from `$subPP`
> - Subscriber offers list (all SubscriberOffers)
> - BN resource ranges from `$addRangeArray`
> - LogicalDate-based activation date

### §9.3 — IMEI Handling Logic

```java
// imeiExists = true → sub has ResourceInfo[ResourceName='IMEI'] AND SOC 55042 not present
// addDummy   = true → Parameter[1]='ADD_DUMMY_IMEI'

// In XSLT (inferred):
// If imeiExists=true  → include actual IMEI from ResourceInfo[ResourceName='IMEI']/ValuesArray
// If addDummy=true    → include dummy IMEI placeholder
// If neither          → no IMEI in payload

// SOC '55042' is the IMEI-related SOC; if already present, skip IMEI inclusion
```

---

## §11 — Audit Logging

**Request audit** — sent per-subscriber after `ActionRequestEvent`. `OPERATION_NAME = "CCBS_CREATE_SUBS"` (static). `AUDIT_TRACE` includes the subscriber's `RefId`.

**Response audit** — always sent (no AllowWriteLog gate unlike other rules). `OPERATION_NAME = "CCBS_CREATE_SUBS"`. `AUDIT_TRACE = "Response received for CCBS_CREATE_SUBS"`.

---

## §12 — Activity Status Management

| Trigger | Code | Status | Method |
|---------|------|--------|--------|
| Rule fires | 0 | [WAITING] | Pre-condition |
| At least one subscriber queued and SendFirstRequestEvent called | 1 | [IN_PROGRESS] | `GetActivityStatusString("1", false)` |
| No subscribers dispatched (all skipped/filtered) | 4 | [SKIPPED] | `SkipActivity(…, "4")` |
| Exception caught | 3 | [ERROR] | `HandleActivityException` |
| All sequential responses received | 2 | [COMPLETED] | `IntraActivitySequencing.ActionResponseEvent → "true"` |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_CREATE_SUBS (rule)
├── Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")
├── Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")
├── [if isActResub] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── Per ParentOU.Subscriber[j] loop:
│   ├── Resubmission guard: Response[].ReferenceId==refId && CompletionStatus==2
│   ├── GetXMLForSubscriber(orderRequest, refId)           [PreExecCheck context]
│   ├── XPath.execute("/(PreExecCheck)", sXML, ns)
│   ├── Per-subscriber context assembly:
│   │   ├── Scan SubscriberOffers for ServiceType='80' → subPP
│   │   ├── XPath.evalAsBoolean(imeiExists expression)
│   │   ├── XPath.evalAsBoolean(addDummy expression)
│   │   └── Collect ResourceRangeInfo[Action='ADD'] → addRangeArray
│   ├── Event.createEvent(xslt://CCBS_CREATE_SUBS)        [per subscriber — §9]
│   ├── Event.assertEvent(reqEvent)                        [queue in IntraActivitySequencing]
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   └── Event.createEvent(xslt://Logger)                  [audit log]
├── Per ParentOU.ChildOU.Subscriber[j] loop:
│   └── [same as above, using GetXMLForSubscriberInChildOU]
├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(...)
└── HandleActivityException(...)

Response_CCBS_CREATE_SUBS (rulefunction)
├── Instance.createInstance(xslt://CCBSCreateSubsRes)
│   ├── Base fields: ResponseCode, ResponseMsg, CompletionStatus, ReferenceId
│   └── SocInstance[] ← ns:ReopenedOffers: OfferInstanceId←ns:NewOfferInstanceId, Soc←ns:Soc
├── currActivity.Response[n] = activityRes
├── Match subscriber by eventResponse.RefID:
│   └── For ParentOU.Subscriber[j] where RefId==RefID:
│       ├── subscriber.SubscriberId ← XPath(SubscriberIdsInfo/SubscriberId/SubscrNumber)
│       ├── subscriber.ResponseCode ← eventResponse.ResponseCode
│       ├── subscriber.ResponseMsg  ← eventResponse.ResponseMsg
│       └── OfferInstanceId mapping:
│           ├── For each SocInstance[s] matching SubscriberOffers[o].Soc (OfferInstanceId==0)
│           │   └── SubscriberOffers[o].OfferInstanceId = SocInstance[s].OfferInstanceId
│           └── For each SocInstance[s] matching RelatedOffersArray[k].Soc (OfferInstanceId==0)
│               └── RelatedOffersArray[k].OfferInstanceId = SocInstance[s].OfferInstanceId
├── Same for ChildOU.Subscriber[j]
├── Event.createEvent(xslt://Logger)                       [no AllowWriteLog gate]
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true" / "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Iterate all Subscribers (ParentOU + ChildOU); skip those already successfully created (CompletionStatus=2 on prior response for same RefId).
- **R2** — For each subscriber: evaluate PreExecCheck, assemble subPP (ServiceType='80' offer), imeiExists, addDummy, addRangeArray (Action='ADD' ranges), logicalDate.
- **R3** — IMEI: include in payload if `imeiExists=true`; use dummy if `addDummy=true`; exclude if neither. SOC '55042' presence on subscriber prevents duplicate IMEI inclusion.
- **R4** — Dispatch must be **sequential** (IntraActivitySequencing): only one outstanding CCBS request at a time; next fires after previous response.
- **R5** — On resubmit: purge pending queue first (`PurgePendingRequestsBeforeResubmit`).
- **R6** — Response: write `SubscriberId` from `SubscriberIdsInfo/SubscriberId/SubscrNumber` to matching subscriber.
- **R7** — Response: map `OfferInstanceId` from `ReopenedOffers[]` to all matching SubscriberOffers and RelatedOffersArray entries by SOC code (only if current OfferInstanceId==0).
- **R8** — Fan-in: activity completes when all queued subscribers have received responses (IntraActivitySequencing manages this; not a simple RequestCount comparison).

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| IntraActivitySequencing is a proprietary TIBCO BE sequencing framework — no direct equivalent in most target platforms | [HIGH] | Migration must implement explicit sequential orchestration (e.g., a state machine, or saga pattern) with the same single-in-flight-at-a-time guarantee |
| SubscriberId is the downstream key for all subsequent CCBS operations — loss or mis-routing breaks the entire subscriber lifecycle | [HIGH] | Implement idempotency check: if CCBS returns a subscriber already exists response, retrieve the existing SubscriberId rather than failing |
| OfferInstanceId write-back only fills positions where OfferInstanceId==0 — resubmit scenarios may leave some positions with stale data if SOC matching fails | [MEDIUM] | Add explicit check: log warnings when ReopenedOffers SOC doesn't match any offer on the subscriber |
| imeiExists + addDummy logic involves three-way condition — complex XSLT branching that must be faithfully reproduced | [MEDIUM] | Unit test all three branches: (a) real IMEI present, (b) dummy IMEI, (c) no IMEI. Verify SOC 55042 guard. |
| BN resource ranges (addRangeArray) may be absent on most orders — migration must gracefully handle empty array | [LOW] | Test with and without ResourceRangeInfo entries |

---

## §19 — Response Message Rule

### §19.1 — Overview

`RuleFunctions.OrderResponse.Response_CCBS_CREATE_SUBS`:
1. Creates `CCBSCreateSubsRes` concept with base response fields and `SocInstance[]` from `ReopenedOffers`
2. Matches response to subscriber by `eventResponse.RefID == Subscriber.RefId`
3. Writes `SubscriberId`, `ResponseCode`, `ResponseMsg` to matched subscriber
4. Maps `OfferInstanceId` from `SocInstance[]` to SubscriberOffers and RelatedOffersArray by SOC match
5. Sends response audit log (no AllowWriteLog gate)
6. Returns `"true"` or `"false"` via `IntraActivitySequencing.ActionResponseEvent(currActivity)`

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Written with SubscriberId and OfferInstanceId values |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_CREATE_SUBS` | Contains createSubscriberResponse payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; IntraActivitySequencing state |

### §19.3 — CCBSCreateSubsRes Concept Fields

```text
createObject
└── object
    ├── @extId              ← OMXUtils.generateTrackingID()                     [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode                       [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg                        [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus                   [Conditional]
    ├── ReferenceId         ← $eventResponse/RefID                              [Conditional]
    └── SocInstance[]       (xsl:for-each ns:ReopenedOffers)                   [Repeated]
        ├── @extId          ← OMXUtils:generateTrackingID()                     [Always]
        ├── OfferInstanceId ← ns:NewOfferInstanceId                            [Conditional]
        └── Soc             ← ns:Soc                                           [Conditional]
```

### §19.4 — Response Completion Logic

```java
// IntraActivitySequencing manages sequential fan-in
// (old commented-out logic was: count(Subscriber) == count(Subscriber/SubscriberId[non-blank]))
if(RuleFunctions.Helpers.IntraActivitySequencing.ActionResponseEvent(currActivity))
    return "true";   // all queued subscribers have responded
else
    return "false";  // still waiting; next request will fire automatically
```

> `ActionResponseEvent` handles two things at once: it marks the current request as complete in the sequencing queue AND fires the next queued request event (if any). When the last queued request is processed, it returns `true`.

### §19.5 — Response Audit Logging

- Sent for every response (no `AllowWriteLog` gate)
- `OPERATION_NAME = "CCBS_CREATE_SUBS"`
- `AUDIT_TRACE = "Response received for CCBS_CREATE_SUBS"`
- Payload inclusion: subject to `WritePayload` global variable

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
