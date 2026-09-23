# OMX_NOTIFY_CHILD_ORDER_COMPLETED

> Terminal step — sends OMX_CHILD_ORDERS_CONFIRMATION back to parent order to signal that the child subscriber order has completed

**Author:** DESKTOP-995HR2V (machine hostname) | **Namespace:** Rules.OMConsumers.OMXOM | **Priority:** 5 | **ForwardChain:** true | **Target:** Parent Order Orchestrator | **Lines:** 119

---

## §1 Overview & Purpose

`OMX_NOTIFY_CHILD_ORDER_COMPLETED` is the final activity in the ACTIVATION_CREATE_SUBSCRIBER process (step 36 of 36). Unlike all preceding FM steps that send requests to backend systems and wait for responses, this rule sends a **response event** — `Events.OMConsumers.OMXFM.Response.OMX_CHILD_ORDERS_CONFIRMATION` — back to the parent order orchestrator to signal that the subscriber-level child order has finished all its processing.

> **Architecture pattern — Child Order Notification:** In OMX, a subscriber-level child order is orchestrated independently. When all its activities complete, it sends `OMX_CHILD_ORDERS_CONFIRMATION` carrying the `mainOmxTrackingId` (parent order's tracking ID) and this child order's own `childOmxTrackingId`. The parent order listens for these events and counts how many child orders have reported success.

> **No backend request / no fan-in wait:** This rule does NOT send a JMS request to a backend system. It dispatches the confirmation event and immediately advances to `NextActivity()` — which terminates the process. There is no response rulefunction.

> **Non-standard file location & naming:** This rule lives under `Rules/OMConsumers/OMXOM/` (not OMXFM) and has no `Request_` prefix. It is an internal OMX orchestration rule, not a conventional FM dispatcher.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name (full) | `Rules.OMConsumers.OMXOM.OMX_NOTIFY_CHILD_ORDER_COMPLETED` |
| File | `Rules/OMConsumers/OMXOM/OMX_NOTIFY_CHILD_ORDER_COMPLETED.rule` |
| Priority | 5 |
| ForwardChain | true |
| Author | DESKTOP-995HR2V (machine hostname — person unknown) |
| Lines | 119 |
| Event dispatched (OUTBOUND) | `Events.OMConsumers.OMXFM.Response.OMX_CHILD_ORDERS_CONFIRMATION` |
| Response rulefunction | *None — fire-and-forget notification* |
| Target | Parent order orchestrator (via OMX_CHILD_ORDERS_CONFIRMATION response event) |
| Correlation | MAIN_TRACKING_ID (parent order) + OMXTrackingId (child order) |
| Completion action | `NextActivity()` — advances process to END immediately |

---

## §3 Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order graph — Customer, POU, ChildOU, Subscriber, OrderData (incl. MAIN_TRACKING_ID) |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity state — Response[], PreExecCheck, Status |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Binds activity to active step |
| 2 | `orderCurrentActivity.ActivityID == "OMX_NOTIFY_CHILD_ORDER_COMPLETED"` | Guards this rule |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_NOTIFY_CHILD_ORDER_COMPLETED"` | Double-check process pointer |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Fires only in WAITING state |

---

## §5 Execution Flow

1. **Setup** — isSkipped=true; read chkXPath from PreExecCheck
2. **POU Subscriber loop** — for each POU[p] → Subscriber[ps]; reqSuccess check (Response[].ReferenceId==psub.RefId AND CompletionStatus==2); PreExecCheck via GetXMLForSubscriber; read MAIN_TRACKING_ID; dispatch OMX_CHILD_ORDERS_CONFIRMATION (POU variant); audit log; isSkipped=false
3. **COU Subscriber loop** — for each POU[p] → ChildOU[c] → Subscriber[cs]; reqSuccess check (Response[].ReferenceId==csub.RefId AND CompletionStatus==2); PreExecCheck via GetXMLForSubscriberInChildOU; read MAIN_TRACKING_ID; dispatch OMX_CHILD_ORDERS_CONFIRMATION (COU variant); audit log; isSkipped=false
4. **Completion** — if(!isSkipped) → `NextActivity(orderRequest, orderCurrentActivity)` → process advances to END; else → `SkipActivity("4")`; catch → HandleActivityException

> **NextActivity() vs SetStatus(1)+SendDataToDB:** All earlier FM steps set Status=1 and call SendDataToDB to remain in-flight while waiting for backend responses. This final step calls `NextActivity()` directly because there is no backend response to wait for — the confirmation event is fire-and-forget.

---

## §6 Key Logic Details

### MAIN_TRACKING_ID Extraction

```java
String mainOmxTrackingId = XPath.evalAsString(
    "$orderRequest/OrderData/ExtendedInfo[Name='MAIN_TRACKING_ID']/Value"
);
// This is the tracking ID of the parent order that spawned this child order.
// It is set by the parent orchestrator before launching this child process.
```

### Two Dispatch Paths

| Path | Loop | Subscriber Var | RefId | PreExecCheck Helper |
|------|------|---------------|-------|---------------------|
| POU Subscriber | POU[p] → Subscriber[ps] | `psub` | `psub.RefId` | `GetXMLForSubscriber(orderRequest, pSubRefId)` |
| COU Subscriber | POU[p] → ChildOU[c] → Subscriber[cs] | `csub` | `csub.RefId` | `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)` |

### Subscriber Fields Read from Concept

| Field | Source | Purpose in Notification |
|-------|--------|------------------------|
| `psub/csub.RefId` | Subscriber concept | subRefId — correlates to subscriber in parent order |
| `psub/csub.SubscriberId` | Subscriber concept | subscriberId — the CCBS subscriber entity ID |
| `psub/csub.ResponseCode` | Subscriber concept (aggregate) | subResponseCode — this subscriber's aggregate completion code |
| `psub/csub.ResponseMsg` | Subscriber concept (aggregate) | subResponseMsg — this subscriber's completion message |

### JMSCorrelationID Behaviour

> The event's `JMSCorrelationID` is set to `OMXUtils:generateTrackingID()` — a fresh random ID, **not** the mainOmxTrackingId or the child's OMXTrackingId. The parent order identifies child completions via topic subscription + the `mainOmxTrackingId` field in the payload (not via JMS correlation). This is a design pattern to note for migration.

---

## §8 System & Integration Dependencies

### §8.1 Event Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Response.OMX_CHILD_ORDERS_CONFIRMATION` | Child order completion notification to parent order — per subscriber |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | Audit log (sendEventImmediate) |

There is no inbound response event. This activity does not wait for a backend reply.

### §8.2 BE Working Memory — Reads

| Field | Source | Used for |
|-------|--------|---------|
| `orderRequest.OrderData.ExtendedInfo[MAIN_TRACKING_ID]` | ExtendedInfo | mainOmxTrackingId — parent order's tracking ID |
| `orderRequest.OrderData.OMXTrackingId` | OrderData | childOmxTrackingId (payload); ESBUUID (audit) |
| `subscriber.RefId` | Subscriber concept | subRefId in confirmation payload |
| `subscriber.SubscriberId` | Subscriber concept | subscriberId in confirmation payload |
| `subscriber.ResponseCode` | Subscriber concept | subResponseCode in confirmation payload |
| `subscriber.ResponseMsg` | Subscriber concept | subResponseMsg in confirmation payload |

### §8.3 Global Variable Dependencies

| Path | Used for |
|------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_OM/WritePayload` | Gates payload in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit |

---

## §9 Detailed Payload Build — OMX_CHILD_ORDERS_CONFIRMATION

Both POU and COU paths produce the same schema — the only difference is the subscriber variable name (`$psub` vs `$csub`).

### §9.1 Confirmation Event Fields

```text
createEvent → event
├── CompletionStatus   ← 2                                      [Always — hardcoded]
├── JMSCorrelationID   ← OMXUtils:generateTrackingID()          [Always — fresh random ID]
├── ResponseCode       ← "000"                                   [Always — hardcoded]
├── ResponseMsg        ← "SUCCESS"                               [Always — hardcoded]
├── mainOmxTrackingId  ← ExtendedInfo[MAIN_TRACKING_ID].Value   [Always]
├── childOmxTrackingId ← OrderData.OMXTrackingId                [Conditional: if present]
├── subRefId           ← subscriber.RefId                        [Conditional: if present]
├── subscriberId       ← subscriber.SubscriberId                 [Conditional: if present]
├── subResponseCode    ← subscriber.ResponseCode                 [Conditional: if present]
└── subResponseMsg     ← subscriber.ResponseMsg                  [Conditional: if present]
```

### §9.2 Illustrative Generated XML

```xml
<event>
  <CompletionStatus>2</CompletionStatus>
  <JMSCorrelationID>a8f3b921-4c7d-...</JMSCorrelationID>  <!-- random UUID -->
  <ResponseCode>000</ResponseCode>
  <ResponseMsg>SUCCESS</ResponseMsg>
  <mainOmxTrackingId>TRK-PARENT-20260103-001</mainOmxTrackingId>
  <childOmxTrackingId>TRK-CHILD-20260103-007</childOmxTrackingId>
  <subRefId>REF-SUB-001</subRefId>
  <subscriberId>9876543</subscriberId>
  <subResponseCode>000</subResponseCode>
  <subResponseMsg>Activation complete</subResponseMsg>
</event>
```

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| OPERATION_NAME | "OMX_NOTIFY_CHILD_ORDER_COMPLETED" |
| AUDIT_TRACE | `concat("Notify Sent for OmxTrackingID ", $mainOmxTrackingId)` — includes parent order tracking ID |
| PROCESS_ID | concat(nanoTime, "_REQ") |
| Dispatch | sendEventImmediate (always) |
| Payload in audit | Gated by `OMX_OM/WritePayload="true"` |

The AUDIT_TRACE includes `mainOmxTrackingId` (parent's ID) — use this to correlate child notifications with parent order log entries.

---

## §12 Activity Status Management

| Condition | Call | Result |
|-----------|------|--------|
| At least one subscriber notified (isSkipped=false) | `NextActivity(orderRequest, orderCurrentActivity)` | Process advances to END — no in-flight wait |
| No subscribers dispatched (isSkipped=true) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | Activity skipped |

> **Difference from all earlier steps:** This step calls `NextActivity()` rather than `GetActivityStatusString("1")+SendDataToDB()`. It does not remain in-flight waiting for a backend response — the process completes immediately after dispatching the notification.

---

## §13 Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

Standard exception wrapper — sets activity to error status and propagates to process error handler.

---

## §15 Function Dependency Tree

```text
OMX_NOTIFY_CHILD_ORDER_COMPLETED
├── [POU Subscriber loop]
│   ├── GetXMLForSubscriber(orderRequest, pSubRefId)           — PreExecCheck
│   ├── XPath.execute() — chkRes
│   ├── XPath.evalAsString() — mainOmxTrackingId (MAIN_TRACKING_ID)
│   ├── Event.createEvent() — OMX_CHILD_ORDERS_CONFIRMATION (POU variant)
│   ├── Event.Ext.sendEventImmediate() — confirmation event
│   ├── System.nanoTime() — pid
│   ├── Event.createEvent() — Logger
│   └── Event.Ext.sendEventImmediate() — audit logger
├── [COU Subscriber loop]
│   ├── GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)  — PreExecCheck
│   ├── XPath.execute() — chkRes
│   ├── XPath.evalAsString() — mainOmxTrackingId
│   ├── Event.createEvent() — OMX_CHILD_ORDERS_CONFIRMATION (COU variant)
│   ├── Event.Ext.sendEventImmediate() — confirmation event
│   ├── System.nanoTime() — pid
│   ├── Event.createEvent() — Logger
│   └── Event.Ext.sendEventImmediate() — audit logger
├── [completion — immediate, no wait]
│   └── NextActivity(orderRequest, orderCurrentActivity)
├── [skip path]
│   └── SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch]
    └── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
```

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Send OMX_CHILD_ORDERS_CONFIRMATION per subscriber (POU and COU) when child order completes |
| R2 | Payload must include mainOmxTrackingId (parent), childOmxTrackingId (self), subRefId, subscriberId, subResponseCode, subResponseMsg |
| R3 | ResponseCode and CompletionStatus are hardcoded "000" and 2 — this rule always reports success regardless of individual activity outcomes |
| R4 | Process terminates immediately after dispatch — no backend response waiting |
| R5 | MAIN_TRACKING_ID must be present in OrderData.ExtendedInfo before this step |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Hardcoded ResponseCode="000"/SUCCESS — always reports success regardless of earlier activity failures; subResponseCode may show actual status but top-level code is always "000" | [HIGH] | In migration, drive ResponseCode from subscriber.ResponseCode aggregate; fail fast if subscriber is in error state |
| JMSCorrelationID is a fresh random ID — parent cannot route by JMS correlation; must match by mainOmxTrackingId in payload | [MEDIUM] | Verify parent order's subscription mechanism; document routing pattern before migration |
| Author is machine hostname — no human owner identified for this rule | [MEDIUM] | Establish code ownership for change management |
| No RequestCount — resubmit could send duplicate notifications if reqSuccess check (CompletionStatus==2) is not satisfied | [LOW] | Test resubmit scenarios to verify idempotency |
| MAIN_TRACKING_ID absent for standalone orders — mainOmxTrackingId will be empty; audit TRACE will be incomplete | [LOW] | Add guard/warning log when MAIN_TRACKING_ID is empty |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
