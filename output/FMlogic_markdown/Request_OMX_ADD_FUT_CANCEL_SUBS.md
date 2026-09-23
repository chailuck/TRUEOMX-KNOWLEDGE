# Request_OMX_ADD_FUT_CANCEL_SUBS

> TIBCO BusinessEvents FM — OMX Add Future Cancel Subscriber (full-to-cancel scheduled cancellation)

**Priority:** 5 | **forwardChain:** true | **Author:** DESKTOP-HINKNF3 | **Backend:** OMX FutureOrder

---

## §1 — Overview & Purpose

Fires when `ActivityID == "OMX_ADD_FUT_CANCEL_SUBS"` and status is WAITING. When activity reason is `FCVG`, schedules a future cancel order (`CANSUB`, nodeLevel=5) in OMX, effective `FullToCancelDay` days from today.

**Single subscriber:** resolves from `ParentOU[0]/Subscriber[0]` with fallback to `ChildOU[0]/Subscriber[0]` via `tib:if-absent`. Throws DATA_ISSUE if subscriber not found.

**Response handler always returns `"true"` unconditionally** — no fan-in count needed.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_FUT_CANCEL_SUBS` |
| Priority / forwardChain | 5 / true |
| Author | DESKTOP-HINKNF3 |
| Loop | Single subscriber (POU[0]/Sub[0] with COU fallback) |
| futureType | `CANSUB` |
| nodeLevel | 5 (Subscriber) |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "OMX_ADD_FUT_CANCEL_SUBS"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_ADD_FUT_CANCEL_SUBS"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow

1. Load LogicalDate; `requestedDate = DateTime.now()`; `requestBy = Channel`
2. Apply PreExecCheck on full OrderData XML
3. If check fails → `SkipActivity("4")`
4. Resolve `subExtId` via tib:if-absent (POU[1]/Sub[1] or COU[1]/Sub[1])
5. If subExtId null → throw DATA_ISSUE
6. Read GVs: `FullToCancelDay`, `FullToCancelOrderType`, `FullToCancelReason`
7. Compute `effectiveDate = DateTime.addDay(now(), plusDay)`
8. Fire `OMX_ADD_FUTURE` event with `futureOrderWithSoc` payload
9. Increment RequestCount; status "1"; persist DB

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS

| Direction | Event | Schema |
|-----------|-------|--------|
| [OUTBOUND] | OMX_ADD_FUTURE | futureOrderWithSoc |
| [LOG] | OMXESB/Logger | AuditLogging/V1_0 |

### §8.6 Global Variables

| Path | Usage |
|------|-------|
| `$globalVariables/OMX_OM/Services/SUSPEND/FullToCancelDay` | Days to add for effectiveDate |
| `$globalVariables/OMX_OM/Services/SUSPEND/FullToCancelOrderType` | orderType for future order |
| `$globalVariables/OMX_OM/Services/SUSPEND/FullToCancelReason` | reasonCode |

---

## §10 — XSLT Field Mapping Tree

```text
createEvent → event → payload → ns3:futureOrderWithSoc
└── ns:futureOrder
    ├── ns:effectiveDate       ← $effectiveDate (today + GV/FullToCancelDay)  [Always]
    ├── ns:orderType           ← $orderType (GV/FullToCancelOrderType)         [Always]
    ├── ns:nodeLevel           ← "5" (Subscriber)                              [Always]
    ├── ns:nodeId              ← $nodeId (SubscriberId)                        [Always]
    ├── ns:requestedDate       ← $requestedDate (now)                          [Always]
    ├── ns:requestedBy         ← $requestBy (Channel)                          [Always]
    ├── ns:activityReason      ← $reasonCode (GV/FullToCancelReason)           [Always]
    ├── ns:extendedInfo[CUS_ID] ← $custId                                      [Conditional]
    ├── ns:extendedInfo[MOBILE_NO] ← $msisdn                                   [Conditional]
    ├── ns:fromOrderId         ← OrderData/OrderID                             [Always]
    └── ns:futureType          ← "CANSUB"                                      [Always]
└── ns2:futureSocs             ← (empty)                                       [Always]
```

---

## §15 — Function Dependency Tree

```text
Request_OMX_ADD_FUT_CANCEL_SUBS
├── RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit
├── Instance.serializeUsingDefaults(orderRequest.OrderData)
├── XPath.execute (PreExecCheck)
├── XPath.evalAsString (subExtId, cusExtId, activityReason)
├── XPath.evalAsInt (plusDay, orderType)
├── DateTime.now / DateTime.addDay
├── Event.createEvent (OMX_ADD_FUTURE XSLT)
├── Event.Ext.sendEventImmediate (audit)
├── RuleFunctions.Helpers.GetActivityStatusString
├── RuleFunctions.Helpers.SendDataToDB
├── RuleFunctions.Helpers.SkipActivity
└── RuleFunctions.Helpers.HandleActivityException
```

---

## §19 — Response Message Rule

### §19.1 Overview

`Response_OMX_ADD_FUT_CANCEL_SUBS` maps `OMX_ADD_FUTURE` response into `OMX_AddFutureRes`. Always returns `"true"` unconditionally.

### §19.3 OMX_AddFutureRes Construction

```text
OMX_AddFutureRes
├── extId            ← OMXUtils.generateTrackingID()   [Always]
├── ResponseCode     ← $eventResponse/ResponseCode     [Conditional]
├── ResponseMessage  ← $eventResponse/ResponseMsg      [Conditional]
└── CompletionStatus ← $eventResponse/CompletionStatus [Conditional]
```

> **Note:** No `ReferenceId` field in this response concept. Fan-in: always `return "true"`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
