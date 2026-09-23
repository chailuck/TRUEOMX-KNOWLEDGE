# Request_CCBS_L9_CANCEL_SUBS

> Cancel an L9 (postpaid) subscriber via CCBS — iterates ParentOU/ChildOU subscribers, uses IntraActivitySequencing sequential fan-out, portOutIndicator set by Channel (MNP=89, else=78).

**Priority:** 5 | **ForwardChain:** true | **Target:** CCBS (L9 Cancel) | **Event:** CCBS_L9_CANCEL_SUBS | **Fan-in:** IntraActivitySequencing | **Used in:** TNP_CANCEL_SUB (step 4)

---

## §1 — Overview & Purpose

Cancels an L9 (postpaid) subscriber in CCBS via the `L9CancelSubscriberRequest` API. Iterates all ParentOU and ChildOU subscribers using IntraActivitySequencing (sequential fan-out).

> **EffectiveDate transformation:** Before the subscriber loop, calls `BN.OrderDataEffectiveDateTransform(ActivityID, EffectiveDate)` to adjust the effective date.

> **IntraActivitySequencing:** Uses `ActionRequestEvent` + `SendFirstRequestEvent` (sequential dispatch). Response uses `IntraActivitySequencing.ActionResponseEvent` — NOT RequestCount-based.

> **portOutIndicator:** Channel="MNP" → `89`; else → `78`

> **preActivityInfo = "OPENPCH"** — hardcoded activity code.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_L9_CANCEL_SUBS` |
| Priority | 5 |
| ForwardChain | true |
| Author | awalia-t420 |
| Target system | CCBS (L9 postpaid cancel) |
| JMS event type | `Events.OMConsumers.OMXFM.Request.CCBS_L9_CANCEL_SUBS` |
| Response concept | `Concepts.FM.Response.CCBSCancelSubsRes` |
| Fan-in method | IntraActivitySequencing.ActionResponseEvent (sequential) |
| Payload schema | `http://services.omx.truecorp.co.th/FMServices/L9CancelSubscriberRequest` |

---

## §3 — Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — ParentOU/ChildOU/Subscriber tree |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | IntraActivitySequencing state, Response[] |

**Key subscriber fields:**

| Field | Usage |
|-------|-------|
| `Subscriber.SubscriberId` | Payload `ns1:subscrNumber` |
| `Subscriber.MSISDN` | Event header `msisdn` + userText when OrderType=48 |
| `Subscriber.SubscriberActivityInfo.ActivityReason` | Payload `ns1:activityReason` (fallback "CREQ") |
| `Subscriber.SubscriberActivityInfo.UserText` | Payload `ns1:userText` (one of 3 sources) |
| `OrderData.EffectiveDate` | Payload `ns1:activityDate` (after transform) |
| `OrderData.Channel` | portOutIndicator: MNP → 89; else → 78 |
| `OrderData.OrderType` | userText branch: OrderType=48 → special message |
| `OrderData.Customer.CustomerActivityInfo.UserText` | userText branch 2 |
| `OrderData.CES` | Event header `CES` |

---

## §4 — Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "CCBS_L9_CANCEL_SUBS"
orderRequest.ProcessFlow.NextActivityID == "CCBS_L9_CANCEL_SUBS"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 — Execution Flow

1. Check isActResub; if resub → PurgePendingRequestsBeforeResubmit
2. Transform EffectiveDate: `BN.OrderDataEffectiveDateTransform(ActivityID, EffectiveDate)`
3. Set `preActivityInfop = "OPENPCH"`
4. Loop ParentOU[i] → Subscriber[j]: build refId; skip if already CompletionStatus==2
5. Evaluate nextAct PreExecCheck via `GetXMLForSubscriber`; if "true" → build + assert CCBS_L9_CANCEL_SUBS event; call `ActionRequestEvent`; send audit log; isSkipped=false
6. Loop ParentOU[i] → ChildOU[k] → Subscriber[j]: same flow using `GetXMLForSubscriberInChildOU`
7. If not skipped: `SendFirstRequestEvent`; status=PROCESSING + SendDataToDB; else SkipActivity("4")

---

## §6 — Business Logic

### portOutIndicator (2-way)

| Condition | portOutIndicator | Meaning |
|-----------|-----------------|---------|
| `OrderData.Channel = "MNP"` | `89` | Mobile Number Portability port-out |
| Otherwise | `78` | Regular cancel |

### activityReason (2-way)

| Condition | activityReason |
|-----------|---------------|
| SubscriberActivityInfo/ActivityReason exists and not blank | SubscriberActivityInfo/ActivityReason |
| Otherwise | `"CREQ"` (hardcoded default) |

### userText (3-way choose)

| Priority | Condition | userText |
|----------|-----------|---------|
| 1 | `OrderData.OrderType = '48'` | `concat("This subscriber is created by ", Subscriber.MSISDN)` |
| 2 | `CustomerActivityInfo.UserText` not blank | CustomerActivityInfo.UserText |
| 3 | Otherwise | SubscriberActivityInfo.UserText |

---

## §10 — XSLT Field Mapping Tree

**Variant ① ParentOU Subscriber** (params: $orderRequest, $refId, $globalVariables, $subscriber, $i, $j, $preActivityInfop)

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority           [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID        [Conditional]
    ├── RefID                ← $refId                                 [Always]
    ├── UserName             ← $orderRequest/OrderData/User           [Credential-gated: IsEnableUserPass]
    ├── PassWord             ← $orderRequest/OrderData/Password       [Credential-gated: IsEnableUserPass]
    ├── OrderType            ← $orderRequest/OrderData/OrderType      [Conditional]
    ├── CES                  ← $orderRequest/OrderData/CES            [Conditional]
    ├── msisdn               ← $subscriber/MSISDN                     [Conditional]
    └── payload
        └── ns1:L9CancelSubscriberRequest
            ├── ns1:subscriberIdInfo
            │   └── ns1:subscrNumber ← ParentOU[i+1]/Subscriber[j+1]/SubscriberId  [Always]
            ├── ns1:preActivityInfo  ← "OPENPCH"                                   [Always, hardcoded]
            ├── ns1:portOutInfo
            │   └── ns1:portOutIndicator ← Channel="MNP"→89 | else→78             [Always (2-way)]
            ├── ns1:actDateInfo
            │   └── ns1:activityDate ← EffectiveDate                               [Conditional: trim(EffectiveDate)!='']
            └── ns1:ActivityInfo
                ├── ns1:activityReason ← SubscriberActivityInfo/ActivityReason or "CREQ"  [Always (2-way)]
                └── ns1:userText       ← OrderType=48→"created by MSISDN" | CustomerUserText | SubscriberUserText  [Always (3-way choose)]
```

*Variant ② (ChildOU): extra param `$k`; references `ParentOU[i+1]/ChildOU[k+1]/Subscriber[j+1]`.*

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Helpers.BN.OrderDataEffectiveDateTransform` | Compute adjusted effective date for BN process type |
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` | Clear queue on resubmit |
| `IntraActivitySequencing.ActionRequestEvent` | Queue request for sequential dispatch |
| `IntraActivitySequencing.SendFirstRequestEvent` | Dispatch first queued request |
| `Helpers.GetXMLForSubscriber` | Serialise ParentOU subscriber for PreExecCheck |
| `Helpers.GetXMLForSubscriberInChildOU` | Serialise ChildOU subscriber for PreExecCheck |
| `Helpers.GetActivityStatusString` | Status string lookup |
| `Helpers.SendDataToDB` | Persist order state |
| `Helpers.SkipActivity` | Skip + advance |
| `Helpers.HandleActivityException` | Exception handler |

---

## §17 — Migration Notes

| ID | Requirement |
|----|-------------|
| R1 | Iterate all ParentOU and ChildOU subscribers; one L9 cancel request per subscriber |
| R2 | EffectiveDate must be transformed via BN.OrderDataEffectiveDateTransform before sending |
| R3 | preActivityInfo = "OPENPCH" (hardcoded) |
| R4 | portOutIndicator: Channel="MNP" → 89; else → 78 |
| R5 | activityReason: SubscriberActivityInfo/ActivityReason or "CREQ" |
| R6 | userText: 3-way (OrderType=48 / CustomerActivityInfo / SubscriberActivityInfo) |
| R7 | Sequential fan-out via IntraActivitySequencing; response fan-in via ActionResponseEvent |

| Risk | Severity | Mitigation |
|------|----------|-----------|
| preActivityInfo "OPENPCH" hardcoded | `[MEDIUM]` | Externalize as config parameter |
| portOutIndicator Channel match "MNP" case-sensitive | `[MEDIUM]` | Validate Channel normalization upstream |
| ChildOU userText bug: references ParentOU subscriber ActivityReason instead of ChildOU path | `[HIGH]` | Fix XPath reference in migration |

---

## §19 — Response Rule: Response_CCBS_L9_CANCEL_SUBS

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `OrderRequest` | Order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_L9_CANCEL_SUBS` | Inbound CCBS response |
| `currActivity` | `Activity` | Activity for response append |

### §19.3 CCBSCancelSubsRes Concept

```text
CCBSCancelSubsRes
├── @extId           ← OMXUtils.generateTrackingID()    [Always]
├── ResponseCode     ← $eventResponse/ResponseCode       [Conditional]
├── ResponseMessage  ← $eventResponse/ResponseMsg        [Conditional]
├── CompletionStatus ← $eventResponse/CompletionStatus   [Conditional]
└── ReferenceId      ← $eventResponse/RefID              [Conditional]
```

### §19.4 Fan-in Logic

| Method | Value |
|--------|-------|
| Fan-in type | IntraActivitySequencing (sequential) |
| Completion check | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Return "true" | All sequential requests have received responses |
| Return "false" | Still processing (sends next queued request) |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
