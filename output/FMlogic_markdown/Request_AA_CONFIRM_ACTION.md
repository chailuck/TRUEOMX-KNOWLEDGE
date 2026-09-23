# Request_AA_CONFIRM_ACTION

## §1 Overview & Purpose

Sends `AAConfirmAction` to the AA system for each subscriber (MSISDN + SrvTrxNo). After iterating all subscribers, copies its own `RequestCount` to the `AA_CHECK_CONFIRMATION` activity so the downstream check knows how many responses to await.

Uses **fire-and-forget pattern** (`sendEventImmediate` + `RequestCount++`). Response always returns `"true"`.

> **[BUG]** Audit logger `OPERATION_NAME` is hardcoded as `"CCBS_CANCEL_SUBS"` — copy-paste error. Must be corrected in migration.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_AA_CONFIRM_ACTION` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | AA_CONFIRM_ACTION |
| Backend | AA — AAConfirmAction endpoint |
| Pattern | Fire-and-Forget (`sendEventImmediate` + `RequestCount++`) |
| Iteration Scope | ParentOU.Subscriber + ChildOU.Subscriber |
| Response Concept | `Concepts.FM.Response.AA_ConfirmActionRes` |
| Response Event | `Events.OMConsumers.OMXFM.Response.AA_CONFIRM_ACTION` |

---

## §4 Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "AA_CONFIRM_ACTION"
orderRequest.ProcessFlow.NextActivityID == "AA_CONFIRM_ACTION"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 Execution Flow

1. Iterate `ParentOU[i].Subscriber[j]`
2. Skip if already successfully responded
3. Evaluate PreExecCheck via `GetXMLForSubscriber`
4. Build and send `AA_CONFIRM_ACTION` event (`sendEventImmediate`)
5. Fire audit logger (LOG_LEVEL=ERROR — unusual)
6. If not resubmit: `RequestCount++`
7. Repeat for `ChildOU[m].Subscriber[n]`
8. **Post-loop**: find `AA_CHECK_CONFIRMATION` activity → set `RequestCount = currentActivity.RequestCount`
9. If not skipped: set IN_PROGRESS; else: `SkipActivity("4")`

---

## §9 Payload Build

```text
createEvent
└── event
    ├── JMSPriority       ← $orderRequest/OrderPriority              [Conditional]
    ├── JMSCorrelationID  ← $orderRequest/OrderData/OMXTrackingId    [Conditional]
    ├── OrderID           ← $orderRequest/OrderData/OrderID          [Conditional]
    ├── OrderType         ← $orderRequest/OrderData/OrderType        [Conditional]
    └── payload
        └── ns2:AAConfirmAction                   (ParentOU: ns2:; ChildOU: ns3:)
            ├── ns2:msisdn     ← $subscriberInstance/MSISDN          [Always]
            └── ns2:srvTrxNo   ← SrvTrxNoInfo[1]/SrvTrxNo           [Conditional: != '']
```

> ChildOU uses `ns3:AAConfirmAction` and `if test="$subscriberInstance/SrvTrxNoInfo[1]/SrvTrxNo"` (no `!= ''`).

---

## §15 Function Dependency Tree

```text
Request_AA_CONFIRM_ACTION
├── GetXMLForSubscriber(orderRequest, refId)
├── GetXMLForSubscriberInChildOU(orderRequest, refId, POURefId)
├── XPath.execute("/(preExecCheck)", sXML, ...)
├── Event.Ext.sendEventImmediate(reqEvent)          ← fire-and-forget
├── Event.Ext.sendEventImmediate(Logger)
├── [Post-loop] Find AA_CHECK_CONFIRMATION, set RequestCount
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(req, activity, "4")
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 Migration Notes

| # | Requirement / Risk | Severity |
|---|-------------------|---------|
| R1 | Must copy `RequestCount` to `AA_CHECK_CONFIRMATION` activity post-loop | [HIGH] |
| R2 | Both ParentOU and ChildOU subscribers sent to AA | [MEDIUM] |
| R3 | SrvTrxNo condition differs: ParentOU uses `!= ''`; ChildOU uses `exists` | [MEDIUM] |
| [BUG] | Audit OPERATION_NAME hardcoded `"CCBS_CANCEL_SUBS"` — fix in migration | [MEDIUM] |
| R4 | Response always returns "true" — no fan-in check | [LOW] |

---

## §19 Response Message Rule

Creates `AA_ConfirmActionRes` from eventResponse fields. Response audit OPERATION_NAME = `"CCBS_CANCEL_SUBS"` (same copy-paste error). Always returns `"true"`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
