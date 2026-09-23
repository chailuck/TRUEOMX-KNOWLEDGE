# Request_NAS_ACTIVATE_SUBS

> TIBCO BusinessEvents FM Logic — NAS Number Activation (Serial IntraActivitySequencing)

**Author:** awalia-t420 | **Priority:** 5 | **Forward Chain:** true | **Target:** NAS (Number Activation System) | **Pattern:** IntraActivitySequencing (Serial Queue) | **Lines:** 104

---

## §1 — Overview & Purpose

This rule activates subscriber MSISDNs in the **NAS (Number Activation System)** by sending one `NAS_ACTIVATE_SUBS` JMS event per subscriber. Unlike most FM rules that use `Event.Ext.sendEventImmediate()` for parallel fan-out, this rule uses the **IntraActivitySequencing serial queue** — events are asserted and queued, then dispatched one-at-a-time via `ActionRequestEvent()` and started with `SendFirstRequestEvent()`.

> **Serial Dispatch Pattern:** This FM uses `Event.assertEvent()` + `IntraActivitySequencing.ActionRequestEvent()` instead of `Event.Ext.sendEventImmediate()`. All subscriber events are queued first, then `SendFirstRequestEvent()` initiates the serial chain. NAS must process one MSISDN at a time.

> **Loop Order — COU before POU:** Unusually, COU subscribers are processed in the outer loop before POU subscribers. This differs from ASRM_UPDATE_ATTRIBUTE_SIM which processes POU first.

| Item | Value |
|------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_NAS_ACTIVATE_SUBS` |
| Author | awalia-t420 |
| Priority | 5 |
| Forward Chain | true |
| JMS Event Dispatched | `Events.OMConsumers.OMXFM.Request.NAS_ACTIVATE_SUBS` |
| Payload Schema | `ns:ActivateNumber` (OMX_ESBBW_NAS_ActivateNum Schema.xsd) |
| Response Concept | `Concepts.FM.Response.NAS_ActivateSubscriberRes` |
| Response Handler | `Response_NAS_ACTIVATE_SUBS.rulefunction` |
| Dispatch Method | `Event.assertEvent()` + `IntraActivitySequencing.ActionRequestEvent()` |
| Fan-In Method | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Target System | NAS (Number Activation System) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM rule priority |
| forwardChain | true | Rule may re-fire after working memory update |
| Rule type | Request dispatcher — serial queue | Events queued and sent one at a time, not parallel |
| Resubmit handling | PurgePendingRequestsBeforeResubmit | Clears all pending events before re-queuing; more aggressive than skip-only |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order: customer, POU/COU/subscriber hierarchy, MSISDNs |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity node; holds event queue (via IntraActivitySequencing), Response[], Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Match current process step |
| 2 | `orderCurrentActivity.ActivityID == "NAS_ACTIVATE_SUBS"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "NAS_ACTIVATE_SUBS"` | Process flow confirmation |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fire if not already in progress |

---

## §5 — Execution Flow Diagram

1. Detect resubmit: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. If resubmit → `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)` — clears existing queued events
3. Load `nextAct.PreExecCheck` XPath string
4. **Loop A — COU Subscribers** (processed first): for each ParentOU[i] → ChildOU[k] → Subscriber[j]:
   - Evaluate PreExecCheck via `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)`
   - If chkRes=="true": check reqSuccess (CompletionStatus==2 + RefId match) → skip if done
   - Build `NAS_ACTIVATE_SUBS` event with subscriber MSISDN
   - `Event.assertEvent(reqEvent)` — adds to working memory event queue
   - `IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)` — registers in serial queue
   - Send audit log immediately
5. **Loop B — POU Subscribers** (processed second): same pattern via `GetXMLForSubscriber(orderRequest, refId)`
6. Post-loop (if any events queued):
   - `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)` — fires first event from queue, starting the serial chain
   - `GetActivityStatusString("1", false)` + `SendDataToDB()`
7. If no events queued: `SkipActivity(orderRequest, orderCurrentActivity, "4")`
8. catch: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

> **Serial vs Parallel:** `Event.assertEvent()` places the event in the BE working memory. `ActionRequestEvent()` registers it in the IntraActivitySequencing queue. No event is sent to NAS until `SendFirstRequestEvent()` is called. Subsequent events are sent one-by-one as each response arrives (driven by the response handler calling `ActionResponseEvent()`).

---

## §6 — IntraActivitySequencing Serial Queue Pattern

This rule implements the **full serial IntraActivitySequencing pattern**, distinct from the parallel fan-out used by most other FMs in this process:

| Step | Call | Purpose |
|------|------|---------|
| Resubmit cleanup | `PurgePendingRequestsBeforeResubmit(orderCurrentActivity)` | Clears any previously queued but unprocessed events before re-queueing |
| Queue event | `Event.assertEvent(reqEvent)` | Places event into BE working memory (not yet sent to NAS) |
| Register in queue | `ActionRequestEvent(reqEvent, orderCurrentActivity)` | Adds event reference to the activity's serial dispatch queue; increments RequestCount |
| Start chain | `SendFirstRequestEvent(orderCurrentActivity)` | Sends only the first event to NAS; subsequent events wait for responses |
| Advance queue | `ActionResponseEvent(currActivity)` (in response handler) | On each response: removes from queue, sends next event, returns true when all done |

> **Why serial?** NAS number activation may have ordering constraints or system-level rate limits. The serial pattern ensures each MSISDN is fully activated before the next is sent, preventing race conditions in the number assignment system.

### Comparison: Parallel vs Serial

| Comparison | Parallel Fan-out (e.g., ASRM_UPDATE_ATTRIBUTE_SIM) | Serial Queue (NAS_ACTIVATE_SUBS) |
|------------|-----------------------------------------------------|----------------------------------|
| Dispatch method | `Event.Ext.sendEventImmediate()` | `Event.assertEvent()` + `ActionRequestEvent()` |
| Events in flight | All at once | One at a time |
| RequestCount mgmt | Manual `RequestCount++` | Managed by `ActionRequestEvent()` |
| Fan-in check | XPath "000" suffix or `IsAllResponseSuccess()` | `ActionResponseEvent()` return value |
| Resubmit purge | No explicit purge (skip-by-CompletionStatus) | `PurgePendingRequestsBeforeResubmit()` |

---

## §7 — Loop Order: COU Before POU

> **Non-standard loop order:** This rule processes COU subscribers in the outer loop before POU subscribers. Most other multi-subscriber FMs (e.g., ASRM_UPDATE_ATTRIBUTE_SIM) process POU first. The serial nature of NAS dispatch means this order determines the actual activation sequence.

| Order | Context | PreExecCheck Helper | XSLT Params |
|-------|---------|---------------------|-------------|
| 1st | COU Subscribers: ParentOU[i] → ChildOU[k] → Subscriber[j] | `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` | i, k, j |
| 2nd | POU Subscribers: ParentOU[i] → Subscriber[j] | `GetXMLForSubscriber(orderRequest, refId)` | i, j |

---

## §8 — System & Integration Dependencies

### §8.1 ESB / JMS Channel Dependencies

| Direction | Event | Channel | Purpose |
|-----------|-------|---------|---------|
| [OUTBOUND] | `NAS_ACTIVATE_SUBS` | NAS FM JMS (serial) | Activate MSISDN in Number Activation System |
| [OUTBOUND] | `Logger` | ESB Audit Log | Per-subscriber audit (sent immediately after queue, before dispatch) |

### §8.2 Backend API Details

| System | Operation | Schema | Protocol |
|--------|-----------|--------|----------|
| NAS | ActivateNumber | `ns:ActivateNumber / MSISDNList` | JMS (serial) |

### §8.3 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `orderCurrentActivity.RequestCount` | Managed by IntraActivitySequencing | Not manually incremented — ActionRequestEvent() handles this |
| `orderCurrentActivity.Status` | Write | Set to ACTIVE or SKIP |
| `orderCurrentActivity.Response[]` | Read | reqSuccess check: CompletionStatus==2 + RefId match |
| `orderRequest.IsOrderResubmitted` | Read | Triggers PurgePendingRequestsBeforeResubmit if true |

### §8.4 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Gate for payload logging |

---

## §9 — Detailed Payload Build (XSLT Decomposition)

Two XSLT variants — COU subscriber (params: i, k, j) and POU subscriber (params: i, j). The payload is identical; only the XPath to the subscriber node differs.

### §9.1 Payload — ActivateNumber

| Element | Source | Notes |
|---------|--------|-------|
| `ns:ActivateNumber / MSISDNList` | `ParentOU[$i+1]/ChildOU[$k+1]/Subscriber[$j+1]/MSISDN` (COU) or `ParentOU[$i+1]/Subscriber[$j+1]/MSISDN` (POU) | Always — the subscriber's mobile number |

> This is the simplest payload of any FM in this process — a single MSISDN string. No credentials, no extended info, no order type. Just activate this number.

### §9.2 Event Container Fields

| Field | Source | Notes |
|-------|--------|-------|
| JMSPriority | `$orderRequest/OrderPriority` | Conditional |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| OrderID | `$orderRequest/OrderData/OrderID` | Conditional |
| RefID | `ParentOU[i+1]/.../Subscriber[j+1]/RefId` | Conditional (XPath from subscriber node) |
| OrderType | `$orderRequest/OrderData/OrderType` | Conditional |
| UserName / PassWord | — | **Not included** — no credentials in NAS payload |

### §9.3 Complete Generated XML Example

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20250727-001</JMSCorrelationID>
    <OrderID>ORD-12345</OrderID>
    <RefID>SUB-REF-COU-001</RefID>
    <OrderType>CREATE_SUBSCRIBER</OrderType>
    <payload>
      <ns:ActivateNumber>
        <MSISDNList>0812345678</MSISDNList>
      </ns:ActivateNumber>
    </payload>
  </event>
</createEvent>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                             [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId                  [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                         [Conditional]
    ├── RefID                ← ParentOU[$i+1]/[ChildOU[$k+1]/]Subscriber[$j+1]/RefId  [Conditional: xsl:if]
    ├── OrderType            ← $orderRequest/OrderData/OrderType                       [Conditional]
    └── payload                                                                        [Always]
        └── ns:ActivateNumber
            └── MSISDNList   ← ParentOU[$i+1]/[ChildOU[$k+1]/]Subscriber[$j+1]/MSISDN [Always — no xsl:if guard]
```

Legend: Green XPath = source from working memory | Orange = static literal | Purple = xsl:if condition

---

## §11 — Audit Logging

> **Timing note:** The audit log is sent via `Event.Ext.sendEventImmediate()` right after `ActionRequestEvent()` — i.e., after the event is queued but *before* `SendFirstRequestEvent()` is called. So the audit fires before NAS actually receives the request for non-first events.

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` |
| PROCESS_ID | `concat(System.nanoTime(), "_REQ")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `"NAS_ACTIVATE_SUBS"` (static) |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `concat("Request Sent for RefId ", $refId)` |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | Copy of reqEvent (gated on WritePayload="true") |

---

## §12 — Activity Status Management

| State | Trigger | Call |
|-------|---------|------|
| [ACTIVE] | At least one event queued | `SendFirstRequestEvent()` → `GetActivityStatusString("1", false)` + `SendDataToDB()` |
| [SKIPPED] | No eligible subscribers | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |

---

## §13 — Exception / Error Handling

| Exception | Handler |
|-----------|---------|
| `Exception ae` (catch-all) | `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|----------|--------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)` | void | Clears queued events before resubmit re-queues them |
| `IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)` | void | Registers event in serial queue; manages RequestCount |
| `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)` | void | Fires first queued event to NAS; starts serial chain |
| `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` | String XML | Serializes COU subscriber for PreExecCheck XPath |
| `GetXMLForSubscriber(orderRequest, refId)` | String XML | Serializes POU subscriber for PreExecCheck XPath |
| `GetActivityStatusString("1", false)` | String | Maps "1" → ACTIVE status |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | void | Marks SKIPPED with reason 4 |
| `SendDataToDB(orderRequest)` | void | Persists order state |
| `HandleActivityException(...)` | void | Centralized exception handler |

---

## §15 — Function Dependency Tree

```text
Request_NAS_ACTIVATE_SUBS (BE rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)  [if resubmit]
├── Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")
│
├── [Loop A — COU Subscribers (processed FIRST)]
│   ├── GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)
│   ├── XPath.execute("/("+chkXPath+")", sXML, ...)           [PreExecCheck]
│   ├── Event.createEvent("xslt://{{.../NAS_ACTIVATE_SUBS}}...")
│   │   └── [XSLT: ActivateNumber/MSISDNList = COU subscriber MSISDN]
│   ├── Event.assertEvent(reqEvent)                            [queue to working memory]
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   ├── Event.createEvent("xslt://{{.../Logger}}...")
│   └── Event.Ext.sendEventImmediate(auditEvent)
│
├── [Loop B — POU Subscribers (processed SECOND)]
│   ├── GetXMLForSubscriber(orderRequest, refId)
│   ├── XPath.execute(...)                                     [PreExecCheck]
│   ├── Event.createEvent("xslt://{{.../NAS_ACTIVATE_SUBS}}...")
│   │   └── [XSLT: ActivateNumber/MSISDNList = POU subscriber MSISDN]
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   └── Event.Ext.sendEventImmediate(auditEvent)
│
├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)   [start serial chain]
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(...)
└── HandleActivityException(...)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Activate MSISDNs for all COU subscribers first, then all POU subscribers (serial order)
- **R2** — Serial dispatch: one NAS request in flight at a time
- **R3** — On resubmit: purge queued requests before re-queuing to prevent duplicate sends
- **R4** — Payload contains only MSISDN; no credentials, no extended attributes
- **R5** — reqSuccess gate: skip subscriber if CompletionStatus==2 response already exists for its RefId

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Serial queue bottleneck — large subscriber counts slow overall order completion | [MEDIUM] | Profile NAS throughput; consider batching MSISDNList if NAS supports multi-MSISDN per call |
| Audit log fires before event is sent to NAS (for non-first items in queue) | [LOW] | Acceptable for tracing; note in migration that audit timestamp ≠ NAS send time |
| COU-before-POU loop order not documented in config — implicit ordering dependency | [LOW] | Document explicit ordering requirement; add comment in migration code |
| `PurgePendingRequestsBeforeResubmit` removes all pending events including partially-processed — resubmit restarts from first unconfirmed | [MEDIUM] | Verify reqSuccess check prevents re-sending to already-confirmed subscribers |

### Modernisation Note

The NAS `ActivateNumber` API could potentially accept a list of MSISDNs (the field is named `MSISDNList`, suggesting it may support multiple values). A modern implementation should investigate batching to replace the serial single-MSISDN pattern and eliminate the IntraActivitySequencing queue overhead.

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author awalia-t420
 */
rule Rules.OMConsumers.OMXFM.Request.Request_NAS_ACTIVATE_SUBS {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "NAS_ACTIVATE_SUBS";
        orderRequest.ProcessFlow.NextActivityID == "NAS_ACTIVATE_SUBS";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub=(orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
        try {
            boolean isSkipped = true;
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
                orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");

            if(isActResub) {
                RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
            }

            // Loop A: COU Subscribers FIRST
            for (int i=0; i < iPOULen; i++) {
                for (int k=0; k < iCOULen; k++) {
                    for(int j=0; j < iCOUSubscriberLen; j++) {
                        // PreExecCheck via GetXMLForSubscriberInChildOU()
                        // reqSuccess: CompletionStatus==2 + RefId match
                        // XSLT (see §9): ActivateNumber/MSISDNList = COU subscriber MSISDN (params i,k,j)
                        Event.assertEvent(reqEvent);
                        RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                        // audit: "Request Sent for RefId " + refId
                    }
                }
                // Loop B: POU Subscribers SECOND
                for(int j=0; j < iSubscriberLen; j++) {
                    // PreExecCheck via GetXMLForSubscriber()
                    // XSLT (see §9): ActivateNumber/MSISDNList = POU subscriber MSISDN (params i,j)
                    Event.assertEvent(reqEvent);
                    RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                }
            }

            if(!isSkipped) {
                RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
                orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
            } else
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
        } catch (Exception ae) {
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

`Response_NAS_ACTIVATE_SUBS.rulefunction` creates a `NAS_ActivateSubscriberRes` concept and calls `IntraActivitySequencing.ActionResponseEvent(currActivity)` to advance the serial queue and determine fan-in completion. The old XPath "000" check is present but commented out entirely.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.NAS_ACTIVATE_SUBS` | Inbound JMS response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Serial queue owner; Response[] appended |

### §19.3 ResponseBase Concept Construction

```text
createObject (NAS_ActivateSubscriberRes)
└── object
    ├── @extId          ← $extId (OMXUtils.generateTrackingID() called in BE, passed as param)  [Always]
    ├── ResponseCode    ← $eventResponse/ResponseCode                                           [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg                                            [Conditional]
    ├── CompletionStatus← $eventResponse/CompletionStatus                                       [Conditional]
    └── ReferenceId     ← $eventResponse/RefID                                                  [Conditional]
```

### §19.4 Response Completion Logic

| Step | Detail |
|------|--------|
| Append response | `currActivity.Response[currActivity.Response@length] = activityRes` |
| Advance queue | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Return "true" | All serial events complete — queue exhausted |
| Return "false" | More events remain in queue; next event dispatched by ActionResponseEvent |

> **Commented-out XPath fan-in:** The original "000" suffix XPath check is present in the source as a comment block (`/* ... */`). It was replaced by `ActionResponseEvent()`. The commented code should be removed in migration to avoid confusion.

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(System.nanoTime(), "_RES")` |
| OPERATION_NAME | `"NAS_ACTIVATE_SUBS"` (static) |
| AUDIT_TRACE | `"Response received for NAS_ACTIVATE_SUBS"` (static — no RefId) |
| Send method | `Event.Ext.sendEventImmediate()` (synchronous) |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
