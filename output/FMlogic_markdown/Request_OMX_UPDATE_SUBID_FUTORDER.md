# Request_OMX_UPDATE_SUBID_FUTORDER

> Updates future order record in OMX after CCBS_MOVE_SUB assigns a new SubscriberId. Loads new subscriber (subExtId) and old subscriber (subExtId+"_src") from working memory. Uses Event.sendEvent (not sendEventImmediate) — rare OMX internal pattern.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_UPDATE_SUBID_FUTORDER` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | OMX_UPDATE_SUBID_FUTORDER |
| Author | warawich-nb |
| Backend | OMX — Future Order update service |
| Pattern | Fire-and-Forget but uses `Event.sendEvent` (NOT sendEventImmediate) |
| Guard | `count(futureOrder) > 0` — no-op if no future orders |
| Credentials | Always included (not gated by IsEnableUserPass) |
| Response Concept | Concepts.FM.Response.OMX_UpdateFutureRes |

---

## §4 — Rule Conditions (WHEN)

1. `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
2. `orderCurrentActivity.ActivityID == "OMX_UPDATE_SUBID_FUTORDER"`
3. `orderRequest.ProcessFlow.NextActivityID == "OMX_UPDATE_SUBID_FUTORDER"`
4. `orderCurrentActivity.Status == "WAITING"`

---

## §5 — Execution Flow

1. Derive `subExtId = tib:if-absent(POU[1]/Sub[1]/@extId, ChildOU[1]/Sub[1]/@extId)`
2. Load `newSub` from working memory by `subExtId`
3. Load `oldSub` from working memory by `subExtId + "_src"`
4. Get `billCycleNo` via `GetBillCycle(orderRequest)`
5. Guard: if `count(futureOrder) == 0` → SkipActivity
6. Build `ns:futureOrders/futureOrder` per future order
7. `Event.sendEvent(reqEvent)` — **NOT sendEventImmediate**
8. Set IN_PROGRESS; audit log via `Event.sendEvent`

---

## §8 — System & Integration Dependencies

### §8.4 BE Working Memory Dependencies

| ExtId Pattern | Concept | Access |
|---------------|---------|--------|
| `{subExtId}` | Subscriber (new — post CCBS_MOVE_SUB) | Read — provides new SubscriberId |
| `{subExtId}_src` | Subscriber (old — source before move) | Read — provides old SubscriberId |

### §8.2 Event Type

Request and response both use `Event.sendEvent`. Event type: `OMX_UPDATE_FUTURE`.

---

## §9 — Payload Build

```text
createEvent
└── event
    ├── JMSPriority/JMSCorrelationID/OrderID/RefID/OrderType   [Conditional]
    ├── UserName/PassWord                                        [Always — not gated]
    └── payload
        └── ns:futureOrders
            └── futureOrder  [for-each; guard: count > 0]
                ├── orderType                       ← futureOrder/orderType
                ├── nodeId                          ← newSub/SubscriberId          [Always]
                ├── updatedDate                     ← current-dateTime()
                ├── updatedBy                       ← "OMX"                        [Always]
                ├── extendedInfo[BC]                ← billCycleNo
                ├── extendedInfo[OLD_SUBID]         ← oldSub/SubscriberId          [Always]
                └── userText
```

---

## §15 — Function Dependency Tree

```text
Request_OMX_UPDATE_SUBID_FUTORDER
├── tib:if-absent(POU[1]/Sub[1]/@extId, ChildOU[1]/Sub[1]/@extId)
├── Instance.getByExtIdByUri(subExtId, ...)           ← newSub
├── Instance.getByExtIdByUri(subExtId+"_src", ...)    ← oldSub
├── GetBillCycle(orderRequest)                         ← billCycleNo
├── XPath.evalAsBoolean() — count(futureOrder) > 0
├── Event.sendEvent(reqEvent)                          ← NOT sendEventImmediate
├── AllowWriteLog(orderType)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(req, activity, "4")
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 — Migration Notes

| # | Requirement / Risk | Severity |
|---|---|---|
| R1 | Uses `Event.sendEvent` NOT `sendEventImmediate` — must preserve engine routing semantics | [HIGH] |
| R2 | Requires both new (subExtId) and old (subExtId+"_src") subscriber in working memory | [HIGH] |
| R3 | Always include credentials — not gated by IsEnableUserPass | [MEDIUM] |
| R4 | Guard: skip if no future orders | [MEDIUM] |
| R5 | Response returns "true" unconditionally | [LOW] |

---

## §19 — Response Message Rule

### §19.1 Overview

Creates `OMX_UpdateFutureRes` with standard fields. Returns `"true"` unconditionally. Both response concept and logger use `Event.sendEvent` (consistent with request side). Debug logging via `Log.log`.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Order context |
| eventResponse | Events.OMConsumers.OMXFM.Response.OMX_UPDATE_FUTURE | Backend response |
| currActivity | Concepts.OM.ProcessConfig.Activity | Activity state |

### §19.4 Fan-in Completion

```text
return "true"  ← unconditional, no RequestCount check
```

OPERATION_NAME: `"OMX_UPDATE_SUBID_FUTORDER"` | Logger uses `Event.sendEvent`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
