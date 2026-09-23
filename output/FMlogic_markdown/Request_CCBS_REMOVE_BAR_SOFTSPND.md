# Request_CCBS_REMOVE_BAR_SOFTSPND

> Remove soft-suspend SOC bar (soc=50412) from CCBS for every subscriber in the order. Used during RESTORE at steps 20 and 22 with different PreExecCheck conditions.

**Priority:** 5 | **ForwardChain:** true | **Target:** CCBS | **Fan-in:** IntraActivitySequencing | **Used in RESTORE:** Steps 20, 22

---

## §1 — Overview & Purpose

Iterates ParentOU → Subscriber and ParentOU → ChildOU → Subscriber. For each subscriber, reads a cached `CCBSGetSubsInfoRes` concept from BE working memory (extId = `GSIR:<OMXTrackingId>:<refId>`) to find SOC 50412. Sends a `CCBS_REMOVE_BAR_SOFTSPND` event per subscriber. Uses IntraActivitySequencing fan-in (sequential, not parallel).

> **Usage context:** Step 20 = non-CCBS channel, FE_OR_CCBS='CCBS', Soc=50412, SocStatus=65/83. Step 22 = CCBS channel, Status=85, SocStatus=84.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_REMOVE_BAR_SOFTSPND` |
| Priority | 5 |
| ForwardChain | true |
| Author | awalia-t420 |
| Target system | CCBS |
| JMS event type | `Events.OMConsumers.OMXFM.Request.CCBS_REMOVE_BAR_SOFTSPND` |
| Response concept | `Concepts.FM.Response.CCBSRemoveBarSoftSpndRes` |

---

## §3 — Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity |
| `CCBSGetSubsInfoRes` | read from WM | extId = `GSIR:<OMXTrackingId>:<refId>` — supplies SOC 50412 |

---

## §4 — Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "CCBS_REMOVE_BAR_SOFTSPND"
orderRequest.ProcessFlow.NextActivityID == "CCBS_REMOVE_BAR_SOFTSPND"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 — Execution Flow

1. Check `isActResub`; if true → `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit`
2. Loop ParentOU[i] → Subscriber[j]: evaluate PreExecCheck via `GetXMLForSubscriber`
3. Read `CCBSGetSubsInfoRes` from WM; extract soc=50412; set soc="0" if absent
4. Build + assert `CCBS_REMOVE_BAR_SOFTSPND` event; call `IntraActivitySequencing.ActionRequestEvent`; send audit log
5. Loop ParentOU[i] → ChildOU[k] → Subscriber[j]: same flow using `GetXMLForSubscriberInChildOU`
6. After loop: if any sent → `SendFirstRequestEvent`, status=PROCESSING, `SendDataToDB`; else `SkipActivity("4")`

---

## §6 — activityReason 3-Way xsl:choose

| Priority | Condition | Value |
|----------|-----------|-------|
| 1 | `$orderCurrentActivity/Parameter[1]` present | Parameter[1] (e.g. `"SYSREQ"`) |
| 2 | `SubscriberActivityInfo/ActivityReason != ""` | ActivityReason from subscriber |
| 3 | Otherwise | `"DDSC"` (hardcoded fallback) |

> **In RESTORE:** Both steps 20 and 22 set `Parameter[1] = "SYSREQ"`, so Priority 1 always triggers.

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS

| Direction | Event | Destination | Purpose |
|-----------|-------|-------------|---------|
| `[OUTBOUND]` | `CCBS_REMOVE_BAR_SOFTSPND` | CCBS FM | Remove soc bar per subscriber |
| `[LOG]` | `Logger` | OMX audit | Per-subscriber request trace |

### §8.3 Backend API

| Field | Value |
|-------|-------|
| System | CCBS |
| Payload root | `ns2:RemoveOfferForSoftSuspend` |
| Schema (GetSubscriberInfo) | `http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/SubscriberServices/Schema.xsd5` |
| Schema (UpdateSubscriberRequest) | `http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/SubscriberServices/UpdateSubscriberRequest.xsd` |

### §8.6 Global Variables

| Path | Usage |
|------|-------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | UserName/PassWord gate |
| `OMX_OM/WritePayload` | Payload in audit log |

---

## §10 — XSLT Field Mapping Tree

**Variant ① ParentOU Subscriber** (params: $orderRequest, $i, $j, $refId, $subNo, $soc, $orderCurrentActivity)

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                    [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId           [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                 [Conditional]
    ├── RefID                ← $refId                                          [Always]
    ├── UserName             ← $orderRequest/OrderData/User                    [Credential-gated: IsEnableUserPass]
    ├── PassWord             ← $orderRequest/OrderData/Password                [Credential-gated: IsEnableUserPass]
    ├── OrderType            ← $orderRequest/OrderData/OrderType               [Conditional]
    ├── CES                  ← $orderRequest/OrderData/CES                     [Conditional]
    └── payload
        └── ns2:RemoveOfferForSoftSuspend
            ├── ns:GetSubscriberInfoRequest/ns:SubscriberIdInfo/ns:subscrNumber ← $subNo [Always]
            └── ns1:UpdateSubscriberRequest
                ├── ns1:SubscriberIdInfo/ns1:subscrNumber ← $subNo             [Always]
                └── ns1:ChangeSubscriberOffersWithRelatedOffersInputInfo
                    ├── ns1:offersToRemove/ns1:srvAgrInfo/ns1:soc ← $soc      [Conditional: string-length($soc)>0]
                    ├── ns1:ActivityInfo (in ChangeSubscriberOffers)
                    │   ├── ns1:activityReason ← 3-way: Param[1]|ActivityReason|"DDSC" [Always]
                    │   └── ns1:userText ← SubscriberActivityInfo/UserText     [Conditional: UserText non-blank]
                    └── ns1:ActivityInfo (in UpdateSubscriberRequest)          [duplicate block]
                        ├── ns1:activityReason ← (same 3-way)
                        └── ns1:userText ← (same conditional)
```

*Variant ② ChildOU Subscriber adds `$k` index for ChildOU; otherwise identical structure.*

---

## §14 — Helper Functions

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` | Clear pending requests on resubmit |
| `IntraActivitySequencing.ActionRequestEvent` | Queue request for sequential dispatch |
| `IntraActivitySequencing.SendFirstRequestEvent` | Kick off first sequenced request |
| `Helpers.GetXMLForSubscriber` | Serialise subscriber for PreExecCheck |
| `Helpers.GetXMLForSubscriberInChildOU` | Serialise ChildOU subscriber for PreExecCheck |
| `Helpers.GetActivityStatusString` | Status string lookup |
| `Helpers.SendDataToDB` | Persist order state |
| `Helpers.SkipActivity` | Skip + advance |
| `Helpers.HandleActivityException` | Exception handler |

---

## §17 — Migration Notes

| ID | Requirement |
|----|-------------|
| R1 | Iterate all ParentOU and ChildOU subscribers — per-subscriber CCBS calls |
| R2 | Read prior CCBSGetSubsInfoRes from working memory for SOC 50412 |
| R3 | activityReason: Parameter[1] > ActivityReason > "DDSC" |
| R4 | Sequential fan-out via IntraActivitySequencing — not parallel |
| R5 | Skip activity if no subscriber passes PreExecCheck |

| Risk | Severity | Mitigation |
|------|----------|-----------|
| IntraActivitySequencing — complex sequential state machine | `[HIGH]` | Replace with async tracking in migration |
| soc="0" edge case — still emitted in offersToRemove | `[MEDIUM]` | Guard soc value before sending |
| Duplicate ActivityInfo block in UpdateSubscriberRequest | `[MEDIUM]` | Verify CCBS schema; deduplicate if possible |

---

## §19 — Response Rule: Response_CCBS_REMOVE_BAR_SOFTSPND

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `OrderRequest` | Order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_REMOVE_BAR_SOFTSPND` | Inbound response |
| `currActivity` | `Activity` | Activity for response append |

### §19.3 CCBSRemoveBarSoftSpndRes Concept

```text
CCBSRemoveBarSoftSpndRes
├── @extId           ← OMXUtils.generateTrackingID()           [Always]
├── ResponseCode     ← $eventResponse/ResponseCode             [Conditional]
├── ResponseMessage  ← $eventResponse/ResponseMsg              [Conditional]
├── CompletionStatus ← $eventResponse/CompletionStatus         [Conditional]
└── ReferenceId      ← $eventResponse/RefID                    [Conditional]
```

### §19.4 Fan-in Logic

> **Fan-in: IntraActivitySequencing** — delegates to `IntraActivitySequencing.ActionResponseEvent(currActivity)`. Returns `"true"` when IntraActivitySequencing signals completion, `"false"` otherwise. Does NOT use the standard `RequestCount == successResponseCount` check.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
