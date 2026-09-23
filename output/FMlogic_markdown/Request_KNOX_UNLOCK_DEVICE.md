# Request_KNOX_UNLOCK_DEVICE

> Send Knox proxy unlock command per subscriber offer — iterates SubscriberOffers, dispatches KNOX_PROXY_SERVICE event with method="unlockDevice".

**Priority:** 5 | **ForwardChain:** true | **Target:** Knox (via proxy) | **Event dispatched:** KNOX_PROXY_SERVICE | **Fan-in:** RequestCount == successResponseCount | **Used in RESTORE:** Step 25

---

## §1 — Overview & Purpose

Iterates ParentOU → Subscriber → SubscriberOffers and ParentOU → ChildOU → Subscriber → SubscriberOffers. For each offer, reads `FE_OR_CCBS` from ExtendedInfo to build a per-offer RefID (`SubRefId:Soc:FE_OR_CCBS`), then sends a `KNOX_PROXY_SERVICE` event with `method="unlockDevice"` and the offer's IMEI_KNOX as deviceUid.

> **Event naming note:** The rule dispatches `KNOX_PROXY_SERVICE` — the ActivityID "KNOX_UNLOCK_DEVICE" is the FM name in ProcessConfig only. The actual JMS event type is the generic Knox proxy endpoint.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_KNOX_UNLOCK_DEVICE` |
| Priority | 5 |
| ForwardChain | true |
| Author | DESKTOP-995HR2V |
| Target system | Knox (via KNOX_PROXY_SERVICE) |
| JMS event dispatched | `KNOX_PROXY_SERVICE` ⚠ (not KNOX_UNLOCK_DEVICE) |
| Response concept | `Concepts.FM.Base.ResponseBase` |
| Fan-in method | `count(Response[ResponseCode suffix "000"]) == RequestCount` |

---

## §3 — Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `OrderRequest` | Full order context |
| `orderCurrentActivity` | `Activity` | PreExecCheck, Response[] |

**ExtendedInfo keys per SubscriberOffers:**

| Key | Required | Usage |
|-----|----------|-------|
| `FE_OR_CCBS` | Required | Part of offerRefId (`SubRefId:Soc:FE_OR_CCBS`) |
| `IMEI_KNOX` | Required | Knox deviceUid + transactionId seed |
| `BRAND_NAME` | Optional | `ns2:brand` field in Knox request |

---

## §4 — Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "KNOX_UNLOCK_DEVICE"
orderRequest.ProcessFlow.NextActivityID == "KNOX_UNLOCK_DEVICE"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 — Execution Flow

1. Check `isActResub` flag
2. Loop ParentOU[p] → Subscriber[ps] → SubscriberOffers[psof]
3. Build `offerRefId = pSubRefId + ":" + offer.Soc + ":" + FE_OR_CCBS`
4. Check if already successful (CompletionStatus==2) — skip if so
5. Evaluate PreExecCheck via `GetXMLForSubscriberOfferFilterWithExtendedInfo`
6. Build + send `KNOX_PROXY_SERVICE` event immediately; increment `RequestCount` (if not resub)
7. Loop ParentOU[p] → ChildOU[c] → Subscriber[cs] → SubscriberOffers[csof]: same using `GetXMLForSubscriberInChildOU`
8. After loops: status=PROCESSING + SendDataToDB, or `SkipActivity("4")`

---

## §9 — Knox Proxy Payload

```xml
<ns2:knoxProxyReq>
  <ns2:transactionId>concat(IMEI_KNOX, tib:timestamp())</ns2:transactionId>
  <ns2:deviceUid>IMEI_KNOX value</ns2:deviceUid>     <!-- Conditional: if IMEI_KNOX present -->
  <ns2:brand>BRAND_NAME value</ns2:brand>             <!-- Conditional: if BRAND_NAME present -->
  <ns2:method>unlockDevice</ns2:method>               <!-- Always / hardcoded -->
</ns2:knoxProxyReq>
```

---

## §10 — XSLT Field Mapping Tree

**Variant ① ParentOU Subscriber Offer** (params: $orderRequest, $offerRefId, $globalVariables, $offer)

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority           [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID        [Conditional]
    ├── RefID                ← $offerRefId                            [Always]
    ├── UserName             ← $orderRequest/OrderData/User           [Credential-gated: IsEnableUserPass]
    ├── PassWord             ← $orderRequest/OrderData/Password       [Credential-gated: IsEnableUserPass]
    ├── OrderType            ← $orderRequest/OrderData/OrderType      [Conditional]
    └── payload
        └── ns2:knoxProxyReq
            ├── ns2:transactionId ← concat(IMEI_KNOX, tib:timestamp())  [Always]
            ├── ns2:deviceUid     ← ExtendedInfo[IMEI_KNOX]/Value        [Conditional]
            ├── ns2:brand         ← ExtendedInfo[BRAND_NAME]/Value       [Conditional]
            └── ns2:method        ← "unlockDevice"                       [Always, hardcoded]
```

*Variant ② (ChildOU): `$cSubRefId` as RefID param instead of `$offerRefId`. Payload identical.*

---

## §17 — Migration Notes

| ID | Requirement |
|----|-------------|
| R1 | Iterate SubscriberOffers (not Subscribers) for both ParentOU and ChildOU |
| R2 | RefID = `SubRefId:Soc:FE_OR_CCBS` — per-offer granularity |
| R3 | Knox method hardcoded `"unlockDevice"` |
| R4 | transactionId = IMEI_KNOX + server timestamp — unique per request |
| R5 | Parallel fan-out; RequestCount incremented manually |

| Risk | Severity | Mitigation |
|------|----------|-----------|
| KNOX_PROXY_SERVICE ≠ KNOX_UNLOCK_DEVICE naming mismatch | `[MEDIUM]` | Document gap; use ActivityID for mapping |
| IMEI_KNOX absent — deviceUid empty, transactionId = timestamp only | `[HIGH]` | Add null guard; skip offer if IMEI_KNOX blank |
| Inconsistent PreExecCheck helper (offer-level vs subscriber-level) | `[MEDIUM]` | Standardise to offer-level check in migration |

---

## §19 — Response Rule: Response_KNOX_UNLOCK_DEVICE

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `OrderRequest` | Order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.KNOX_PROXY_SERVICE` | Inbound response |
| `currActivity` | `Activity` | Activity for response append |

### §19.3 ResponseBase Concept

```text
ResponseBase
├── @extId           ← OMXUtils.generateTrackingID()    [Always]
├── ResponseCode     ← $eventResponse/ResponseCode       [Conditional]
├── ResponseMessage  ← $eventResponse/ResponseMsg        [Conditional]
├── CompletionStatus ← $eventResponse/CompletionStatus   [Conditional]
└── ReferenceId      ← $eventResponse/RefID              [Conditional]
```

### §19.4 Fan-in Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Completion condition | `currActivity.RequestCount == successResponseCount` |
| Return "true" | All Knox calls returned ResponseCode ending in "000" |
| Return "false" | Still waiting |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
