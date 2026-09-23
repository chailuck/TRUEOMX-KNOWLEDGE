# Request_CCBS_CANCEL_SUBS

## §1 Overview & Purpose

Sends a **CancelSubscriber** request to CCBS for each subscriber. This is the core CCBS cancellation operation — terminates the subscriber record in CCBS, setting portOutIndicator (89=MNP, 78=standard) and optional activity date for back-dated cancellations.

Used in **CANCEL_SUBSCRIBER** process — Step 57. Also used in order types 126/127/129/15/16 (move/change) with back-date support. Uses **IntraActivitySequencing** for parallel fan-in.

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CANCEL_SUBS` |
| Priority | 5 |
| ForwardChain | true |
| Author | awalia-t420 |
| Parameters | ALT_CES — alternate CES override |
| Dispatch | Per-subscriber (ParentOU + ChildOU), IntraActivitySequencing |

## §4 Rule Conditions (WHEN)

1. `orderCurrentActivity.ActivityID == "CCBS_CANCEL_SUBS"`
2. `orderCurrentActivity.Status == "WAITING"`
3. ExtId and NextActivityID match

## §5 Execution Flow

1. Resubmit: `PurgePendingRequestsBeforeResubmit()`
2. Fetch LogicalDate; get ALT_CES parameter
3. Compute back-date flag (OrderTypes 126/127/129/15/16)
4. If back-date: `strBackDate = EffectiveDate-1sec` (or LogicalDate-1sec, or today-1sec)
5. Iterate ParentOU subscribers → per-subscriber: PreExecCheck, activityDate computation
6. Create & assert CCBS_CANCEL_SUBS event → `ActionRequestEvent()`
7. Repeat for ChildOU subscribers
8. `SendFirstRequestEvent()`, Status="1", SendDataToDB

## §8 System & Integration Dependencies

### §8.1 Order Types
CANCEL_SUBSCRIBER (step 57, types 10/12/14). Also order types 126/127/129/15/16 with back-date.

### §8.2 ESB / JMS

| Direction | Event | Schema |
|-----------|-------|--------|
| [OUTBOUND] | CCBS_CANCEL_SUBS | ns:CancelSubscriberRequest |
| [OUTBOUND] | Logger | Audit |

### §8.3 Backend
CCBS | CancelSubscriber | portOutIndicator: 89 (MNP) or 78 (standard)

## §9 Payload Build

| Field | Source | Notes |
|-------|--------|-------|
| `ns:subscrNumber` | SubscriberId | Always |
| `ns:portOutIndicator` | 89 (Channel=MNP) / 78 (other) | Always |
| `ns:activityDate` | computed activityDate | If non-empty |
| `ns:activityReason` | ActivityReason or "CREQ" | Always |
| `ns:userText` | OT48 text / CustomerActivityInfo / SubscriberActivityInfo | Conditional priority |
| CES header | ALT_CES or OrderData/CES | Conditional |

**Back-date logic:**
```
activityDate = if isOrderBackDate
    then (strBackDate if >= OLD_BAN_DATE, else "")
    else (EffectiveDate if present, else "")
```

## §10 XSLT Field Mapping Tree

```text
createEvent → event
├── JMSPriority/JMSCorrelationID/OrderID/RefID     [Conditional]
├── UserName/PassWord                               [Conditional: IsEnableUserPass]
├── OrderType                                       [Conditional]
├── CES    ← ALT_CES or OrderData/CES              [Conditional]
├── msisdn ← subscriber/MSISDN                     [Conditional]
└── payload
    └── ns:CancelSubscriberRequest
        ├── ns:subscriberIdInfo/ns:subscrNumber    ← SubscriberId           [Always]
        ├── ns:portOutInfo/ns:portOutIndicator     ← 89(MNP) / 78(other)   [Always]
        ├── ns:actDateInfo/ns:activityDate         ← $activityDate          [Conditional: non-empty]
        └── ns:ActivityInfo
            ├── ns:activityReason  ← ActivityReason or "CREQ"               [Always]
            └── ns:userText        ← priority: OT48/CustomerActivity/SubActivity [Conditional]
```

## §14 Helper Functions

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()` | Clear pending on resubmit |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Send + sequence tracking |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Initiate sequence |
| `GetXMLForSubscriber(orderRequest, refId)` | Serialize subscriber for PreExecCheck |
| `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` | ChildOU PreExecCheck |

## §17 Migration Notes

- **R1:** portOutIndicator 89 (MNP) vs 78 (standard) — must be preserved exactly
- **R2:** Back-date calculation EffectiveDate-1sec — critical for billing correctness
- **R3:** OLD_BAN_DATE guard prevents back-date before account activation
- **Risk:** [HIGH] — Core CCBS cancellation; mismatch in portOutIndicator causes billing errors

## §19 Response Message Rule

**Type:** `CCBSCancelSubsRes` | **Fan-in:** `IntraActivitySequencing.ActionResponseEvent(currActivity)`
**Audit:** AUDIT_TRACE=concat("Response received for RefId ", RefID)

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
