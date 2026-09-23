# Request_OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE

## §1 — Overview & Purpose

Creates child OMX orders for each subscriber (across ParentOU + ChildOU) to change their postpaid package. The `OFFER` parameter is parsed from a comma-separated `key=value` string into: `offerName`, `soc`, `serviceType`, `reasonCode`, `userText`.

> **⚠ Naming anomaly:** ActivityID is `OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE` but JMS event dispatched is `OMX_CREATE_CHILD_ORDER`.
>
> **💡 childIndex:** Global counter incremented across all subscribers (ParentOU + ChildOU combined). Used in `orderId = concat(OrderID, "-", childIndex)` and `channel = concat(Channel, "-OMX")`.

**ExtendedInfo written:** `MAIN_TRACKING_ID=OMXTrackingId`, `SBM_CHANNEL="OMX"`.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE` |
| Activity ID | `OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE` |
| JMS Event type | `OMX_CREATE_CHILD_ORDER` [Naming anomaly] |
| Fan-in | `count(Response[...000]) == RequestCount` |
| Send pattern | `Event.Ext.sendEventImmediate` per subscriber |
| Required parameters | `ORDER_TYPE`, `OFFER` |

---

## §5 — Execution Flow

1. Check resubmit; evaluate PreExecCheck
2. Read `ORDER_TYPE` (required), `OFFER` (required)
3. Validate — throw exception if either is missing
4. Parse OFFER: `String.split(offerParam, ",")` → per token: `String.split(token, "=")` → offerName, soc, serviceType, reasonCode, userText
5. childIndex = 0
6. Outer loop: ParentOU[p].Subscriber[s] → send child order; childIndex++
7. Inner loop: ChildOU[c][under each ParentOU[p]] Subscriber[s] → send child order; childIndex++
8. Set WAITING_RESPONSE; persist to DB

---

## §7 — OFFER Parameter Parsing

Example: `offerName=POSTPAID_BASIC,soc=SOC_001,serviceType=80,reasonCode=CHG,userText=Change Package`

| Key | Variable | Use |
|-----|---------|-----|
| offerName | `$offerName` | Plan name in child order |
| soc | `$soc` | SOC code |
| serviceType | `$serviceType` | Service type |
| reasonCode | `$reasonCode` | Reason code |
| userText | `$userText` | User text |

---

## §10 — XSLT Field Mapping

```text
createEvent / event
├── JMSPriority / JMSCorrelationID         ← $orderRequest/OrderData fields  [Always]
├── OrderID                                ← concat(OrderID, "-", childIndex) [Always]
├── RefID                                  ← subscriber.ServiceNumber         [Always]
└── payload / submitOrderRequest
    ├── ns:channel        ← concat(Channel, "-OMX")                [Always]
    ├── ns:orderId        ← concat(OrderID, "-", childIndex)        [Always]
    ├── ns:msisdn         ← subscriber.ServiceNumber                [Always]
    ├── ns:offerName      ← $offerName (from OFFER param)           [Always]
    ├── ns:soc            ← $soc (from OFFER param)                 [Always]
    ├── ns:serviceType    ← $serviceType (from OFFER param)         [Always]
    ├── ns:reasonCode     ← $reasonCode (from OFFER param)          [Always]
    ├── ns:userText       ← $userText (from OFFER param)            [Conditional]
    ├── ns:orderType      ← ORDER_TYPE param                        [Always]
    ├── ns:ExtendedInfo[MAIN_TRACKING_ID] ← OMXTrackingId          [Always]
    └── ns:ExtendedInfo[SBM_CHANNEL]      ← "OMX"                  [Always, hardcoded]
```

---

## §17 — Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| ActivityID vs JMS event type mismatch | [HIGH] | Align naming |
| OFFER parameter uses custom key=value serialization — no schema | [HIGH] | Replace with structured input; validate each key |
| childIndex global counter — order-dependent subscriber processing | [MEDIUM] | Document counter scope; ensure orderId uniqueness |
| Nested loop: every subscriber = separate child order — high volume risk | [MEDIUM] | Monitor subscriber counts; consider batching |
| SBM_CHANNEL hardcoded to "OMX" | [LOW] | Move to configuration |

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_OMX_SUBMIT_POSTPAID_CHANGE_PACKAGE`: Event scope `OMX_CREATE_CHILD_ORDER`. Creates `OMX_CreateChildOrder`. Captures `childOmxTrackingId` from `submitOrderResponse.OMXTrackingId`.

### §19.3 — Response Concept (OMX_CreateChildOrder)

```text
OMX_CreateChildOrder
├── extId                ← OMXUtils:generateTrackingID()          [Always]
├── ResponseCode         ← $eventResponse/ResponseCode            [Conditional]
├── ResponseMessage      ← $eventResponse/ResponseMsg             [Conditional]
├── CompletionStatus     ← $eventResponse/CompletionStatus        [Conditional]
├── ReferenceId          ← $eventResponse/RefID                   [Conditional]
└── childOmxTrackingId   ← submitOrderResponse/OMXTrackingId      [Conditional]
```

### §19.4 — Fan-in

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"]) == RequestCount
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
