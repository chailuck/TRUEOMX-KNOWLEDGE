# Request_CCBS_ADD_RESOURCE_RANGES

> Adds resource ranges for each subscriber (POU and COU) via CCBS AddResourceRanges — per-subscriber dispatch with Action=ADD filter and ValuesArray tokenization

**Priority:** 5 | **ForwardChain:** true | **Backend:** CCBS (ResourceRanges) | **Dispatch:** Per-Subscriber (POU → COU)

---

## §1 — Overview & Purpose

This rule dispatches **CCBS AddResourceRanges** requests for every subscriber across all Parent OUs and Child OUs. Unlike agreement-based FMs, this operates on the **Subscriber** model — one request per subscriber per OU level. ResourceRangeInfo entries with `Action=="ADD"` are batched into a single request per subscriber.

- Iterates POU → POU.Subscriber, then COU → COU.Subscriber
- PreExecCheck evaluated per subscriber using `GetXMLForSubscriber` (POU) or `GetXMLForSubscriberInChildOU` (COU)
- Filters `ResourceRangeInfo` where `Action=="ADD"` → collects into `addRangeArray`
- `ValuesArray` tokenized on `"-"` → emits multiple `ns3:Values` elements per resource
- isActResub guard: `PurgePendingRequestsBeforeResubmit` if applicable
- `logicalDateVal` read from LogicalDate concept but never used in XSLT — dead code

> **BUG [HIGH] — COU event type mismatch (line 113):** The COU request event is typed as `Events.OMConsumers.OMXFM.Request.CCBS_CHANGE_RESOURCE_RANGES` instead of `CCBS_ADD_RESOURCE_RANGES`. The XSLT template still uses the correct CCBS_ADD_RESOURCE_RANGES event, but the BE runtime may route this to the wrong channel.

> **BUG [MEDIUM] — No empty-array guard:** The rule dispatches even when `addRangeArray@length == 0` (no ADD ranges qualify). An empty AddResourceRangesRequest may be sent to CCBS.

> **AUDIT_TRACE inconsistency [LOW]:** POU trace says "CCBS_CHANGE_ADD_RANGES" (wrong name); COU trace has typo "ChidOU" (missing 'l').

> **Dead code [MEDIUM] — logicalDateVal:** Read from LogicalDate concept but never passed to XSLT.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_ADD_RESOURCE_RANGES` |
| Priority | 5 |
| forwardChain | true |
| Backend system | CCBS — AddResourceRanges |
| Dispatch pattern | Per-Subscriber (POU subscribers, then COU subscribers) |
| Range filter | `ResourceRangeInfo.Action == "ADD"` |
| Response rulefunction | `Response_CCBS_ADD_RESOURCE_RANGES` |
| Fan-in mechanism | `IntraActivitySequencing.ActionResponseEvent(currActivity)` helper |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order including ParentOU/ChildOU/Subscriber/ResourceRangeInfo |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — matched by ActivityID, extId, Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_ADD_RESOURCE_RANGES"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_ADD_RESOURCE_RANGES"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow

1. Check isActResub → `PurgePendingRequestsBeforeResubmit` if true
2. Read LogicalDate → `logicalDateVal` (dead code — not used)
3. **POU loop**: for each POU → for each Subscriber → PreExecCheck via `GetXMLForSubscriber` → filter `Action=="ADD"` → dispatch
4. **COU loop**: for each COU → for each Subscriber → PreExecCheck via `GetXMLForSubscriberInChildOU` → same filter/dispatch (with event type bug)
5. If `!isSkipped` → `SendFirstRequestEvent` + Status="1" + `SendDataToDB`; else `SkipActivity("4")`

---

## §6 — Rule Action (THEN) — Key Logic Details

### §6.1 Range Filtering

For each subscriber, iterates `sub.ResourceRangeInfo[]` and collects entries where `rangeInfo.Action == "ADD"` into `addRangeInfos` list → converted to typed `addRangeArray`.

> **Warning:** No guard on `addRangeArray@length > 0` before dispatch — an empty array triggers a CCBS call with no ResourceInfo elements.

### §6.2 XSLT Dispatch (POU vs COU differences)

| Aspect | POU scope | COU scope |
|--------|-----------|-----------|
| PreExecCheck helper | `GetXMLForSubscriber(orderRequest, refId)` | `GetXMLForSubscriberInChildOU(orderRequest, refId, parentOU.RefId)` |
| Event type declared | `CCBS_ADD_RESOURCE_RANGES` | **CCBS_CHANGE_RESOURCE_RANGES** (bug!) |
| XSLT template ref | `CCBS_ADD_RESOURCE_RANGES` | `CCBS_ADD_RESOURCE_RANGES` (correct) |
| Credential guard | Double-guarded: IsEnableUserPass='true' AND User/Password exist | Single-guarded: IsEnableUserPass='true' only |
| AUDIT_TRACE | "Request Sent for **CCBS_CHANGE_ADD_RANGES** for add resourceRangeInfo" | "Request Sent for CCBS_ADD_RESOURCE_RANGES for add resourceRangeInfo **ChidOU**" |

### §6.3 ValuesArray Tokenization

Resource range values are stored as a hyphen-delimited string in `ValuesArray`. The XSLT tokenizes this:
`tib:tokenize(ValuesArray, "-")` → emits one `ns3:Values` element per token.

---

## §8 — System & Integration Dependencies

### §8.1 ESB / JMS Channel Dependencies

| Direction | Event | Purpose |
|-----------|-------|---------|
| [OUTBOUND] | `CCBS_ADD_RESOURCE_RANGES` | Add resource ranges request per subscriber |
| [LOG] | `Logger` | Audit per dispatch |

### §8.2 Backend API

| System | Operation | Schema |
|--------|-----------|--------|
| CCBS | AddResourceRanges | `amdocs.csm3g.datatypes.AddResourceRangesRequest.xsd` (ns1), SubscriberIdInfo (ns), ResourceInfo (ns3), ActivityInfo (ns2) |

### §8.3 Concept Fields Used

| Field | Source | Usage |
|-------|--------|-------|
| `Subscriber.RefId` | `sub.RefId` | Correlation key (RefID in event) |
| `Subscriber.SubscriberId` | `sub.SubscriberId` | `SubscriberIdInfo.SubscrNumber` |
| `Subscriber.MSISDN` | `sub.MSISDN` | `ns3:ResrcScopeId` per resource |
| `ResourceRangeInfo.Action` | `rangeInfo.Action` | Filter condition (=="ADD") |
| `ResourceRangeInfo.effectiveDate` | `rangeInfo.effectiveDate` | `ns3:EffectiveDate` (conditional) |
| `ResourceRangeInfo.expirationDate` | `rangeInfo.expirationDate` | `ns3:ExpirationDate` (conditional) |
| `ResourceRangeInfo.ResourceName` | `rangeInfo.ResourceName` | `ns3:Name` (conditional) |
| `ResourceRangeInfo.ValuesArray` | `rangeInfo.ValuesArray` | Tokenized on "-" → `ns3:Values[*]` |
| `SubscriberActivityInfo.ActivityReason` | `sub.SubscriberActivityInfo.ActivityReason` | `ns2:ActivityReason` or default "CREQ" |
| `SubscriberActivityInfo.UserText` | `sub.SubscriberActivityInfo.UserText` | `ns2:UserText` (conditional) |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameters

| Param | Source |
|-------|--------|
| `$orderRequest` | orderRequest concept |
| `$refId` | sub.RefId (subscriber reference) |
| `$globalVariables` | global variables |
| `$sub` | current Subscriber concept |
| `$addRangeArray` | typed array of ADD ResourceRangeInfo |

### §9.2 Output XML Tree

```text
createEvent → event
├── JMSPriority              ← $orderRequest/OrderPriority              [Always]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId    [Always]
├── OrderID                  ← $orderRequest/OrderData/OrderID          [Always]
├── RefID                    ← $refId (sub.RefId)                       [Always]
├── UserName                 ← $orderRequest/OrderData/User             [Credential-gated: IsEnableUserPass='true' AND User exists]
├── PassWord                 ← $orderRequest/OrderData/Password         [Credential-gated: IsEnableUserPass='true' AND Password exists]
├── OrderType                ← $orderRequest/OrderData/OrderType        [Conditional: if exists]
├── CES                      ← $orderRequest/OrderData/CES              [Conditional: if exists]
└── payload → ns1:AddResourceRangesRequest
    ├── ns:SubscriberIdInfo
    │   └── ns:SubscrNumber  ← $sub/SubscriberId                       [Conditional: if exists]
    ├── ns3:ResourceInfo[*]  (foreach $addRangeArray/elements)
    │   ├── ns3:EffectiveDate  ← effectiveDate                         [Conditional: if exists]
    │   ├── ns3:ExpirationDate ← expirationDate                        [Conditional: if exists]
    │   ├── ns3:Name           ← ResourceName                          [Conditional: if exists]
    │   ├── ns3:ResrcScopeId   ← $sub/MSISDN                          [Conditional: if exists]
    │   └── ns3:Values[*]      ← tib:tokenize(ValuesArray, "-")       [Always — one per token]
    └── ns2:ActivityInfo
        ├── ns2:ActivityReason ← ActivityReason or "CREQ"              [Always]
        └── ns2:UserText       ← SubscriberActivityInfo/UserText       [Conditional: if exists]
```

---

## §11 — Audit Logging

| Scope | AUDIT_TRACE value | Issue |
|-------|-------------------|-------|
| POU request | "Request Sent for **CCBS_CHANGE_ADD_RANGES** for add resourceRangeInfo" | [LOW] Wrong operation name |
| COU request | "Request Sent for CCBS_ADD_RESOURCE_RANGES for add resourceRangeInfo **ChidOU**" | [LOW] Typo "ChidOU" |
| Response (RF) | "Response received for CCBS_ADD_RESOURCE_RANGES" | Correct |

---

## §12 — Activity Status Management

| Condition | Result |
|-----------|--------|
| At least one request dispatched | `SendFirstRequestEvent` + Status="1" + `SendDataToDB` |
| No subscriber qualified | `SkipActivity("4")` |

---

## §13 — Exception Handling

All errors caught by `catch(Exception ae)` → `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `GetXMLForSubscriber(orderRequest, refId)` | Builds XML for POU subscriber PreExecCheck evaluation |
| `GetXMLForSubscriberInChildOU(orderRequest, refId, parentRefId)` | Builds XML for COU subscriber PreExecCheck evaluation |
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears pending requests for resubmit |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Registers request; increments RequestCount |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Dispatches first queued request |
| `SkipActivity(orderRequest, activity, "4")` | Marks activity skipped |
| `SendDataToDB(orderRequest)` | Persists state |
| `HandleActivityException(...)` | Error handler |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_ADD_RESOURCE_RANGES (rule)
├── RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)                        [POU]
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, parentRefId)  [COU]
├── Event.createEvent("xslt://CCBS_ADD_RESOURCE_RANGES") × N subscribers (POU)
├── Event.createEvent("xslt://CCBS_ADD_RESOURCE_RANGES") × N subscribers (COU — type bug)
├── Event.assertEvent(reqEvent)
├── RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
├── Event.Ext.sendEventImmediate(Logger event) × N dispatches
├── RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(activity)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")
└── RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")
```

---

## §17 — Migration Notes & Recommendations

| Risk | Severity | Mitigation |
|------|----------|------------|
| COU event type declared as CCBS_CHANGE_RESOURCE_RANGES instead of CCBS_ADD_RESOURCE_RANGES | [HIGH] | Fix line 113 to use CCBS_ADD_RESOURCE_RANGES event type |
| No guard on addRangeArray@length > 0 — empty request dispatched to CCBS | [MEDIUM] | Add `if(addRangeArray@length > 0)` guard before dispatch |
| logicalDateVal dead code — read but never used | [MEDIUM] | Remove dead code or add logicalDateVal to XSLT if needed |
| AUDIT_TRACE inconsistency (POU wrong name, COU typo) | [LOW] | Standardize AUDIT_TRACE strings |
| Credential guard inconsistency (POU double-guarded, COU single-guarded) | [LOW] | Align credential guard to match POU pattern in COU XSLT |
| No reqSuccess check before dispatch | [MEDIUM] | Add per-subscriber reqSuccess check for resubmit safety |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_ADD_RESOURCE_RANGES {
  attribute { priority = 5; forwardChain = true; }
  declare { Concepts.OrderRequest.OrderRequest orderRequest; Concepts.OM.ProcessConfig.Activity orderCurrentActivity; }
  when { /* ActivityID=="CCBS_ADD_RESOURCE_RANGES", Status=="WAITING" */ }
  then {
    try {
      boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
      if(isActResub) PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      String logicalDateVal = logicalDateRes.LogicalDate;  // Dead code
      boolean isSkipped = true;

      for(int pou = ...) {
        ParentOU parentOU = ...;
        // POU subscribers
        for(int pous = ...) {
          Subscriber sub = parentOU.Subscriber[pous];
          String sXML = GetXMLForSubscriber(orderRequest, sub.RefId);
          if(chkRes == "true") {
            // Collect ResourceRangeInfo[Action=="ADD"] → addRangeArray
            // [See §9 for full XSLT payload — builds ns1:AddResourceRangesRequest]
            Events.OMConsumers.OMXFM.Request.CCBS_ADD_RESOURCE_RANGES reqEvent = Event.createEvent(
              "xslt://{{/Events/OMConsumers/OMXFM/Request/CCBS_ADD_RESOURCE_RANGES}}"
              /* Fields: JMSPriority, OrderID, RefID, UserName/PassWord (double-gated), payload/ns1:AddResourceRangesRequest */);
            Event.assertEvent(reqEvent);
            ActionRequestEvent(reqEvent, orderCurrentActivity);
            /* Logger — AUDIT_TRACE: "CCBS_CHANGE_ADD_RANGES" (wrong name) */
            isSkipped = false;
          }
        }
        // COU subscribers
        for(int cou = ...) {
          for(int cous = ...) {
            Subscriber sub = childOU.Subscriber[cous];
            String sXML = GetXMLForSubscriberInChildOU(orderRequest, sub.RefId, parentOU.RefId);
            if(chkRes == "true") {
              // BUG: wrong event type below!
              Events.OMConsumers.OMXFM.Request.CCBS_CHANGE_RESOURCE_RANGES reqEvent = Event.createEvent(
                "xslt://{{/Events/OMConsumers/OMXFM/Request/CCBS_ADD_RESOURCE_RANGES}}"
                /* Same fields as POU — see §9 */);
              /* Logger — AUDIT_TRACE: "...ChidOU" (typo) */
              isSkipped = false;
            }
          }
        }
      }
      if(!isSkipped) { SendFirstRequestEvent; Status="1"; SendDataToDB; }
      else { SkipActivity("4"); }
    } catch(Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

Standard response handler: constructs a `CCBS_AddResourceRangesRes` concept, appends to `currActivity.Response[]`, logs audit trail, and calls `ActionResponseEvent` for fan-in.

### §19.2 Scope Variables

| Variable | Type |
|----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_ADD_RESOURCE_RANGES` |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` |

### §19.3 ResponseBase Concept Construction

Creates `Concepts.FM.Response.CCBS_AddResourceRangesRes` (specific type, not generic ResponseBase):

```text
createObject → CCBS_AddResourceRangesRes
├── @extId          ← OMXUtils:generateTrackingID()          [Always]
├── ResponseCode    ← $eventResponse/ResponseCode            [Conditional: if exists]
├── ResponseMessage ← $eventResponse/ResponseMsg             [Conditional: if exists]
├── CompletionStatus ← $eventResponse/CompletionStatus       [Conditional: if exists]
└── ReferenceId     ← $eventResponse/RefID                   [Conditional: if exists]
```

### §19.4 Fan-in Completion

| Mechanism | Value |
|-----------|-------|
| Method | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Return "true" | All dispatched requests responded |
| Return "false" | Still waiting |

### §19.5 Response Audit

AUDIT_TRACE: `"Response received for CCBS_ADD_RESOURCE_RANGES"` (static, correct)

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
