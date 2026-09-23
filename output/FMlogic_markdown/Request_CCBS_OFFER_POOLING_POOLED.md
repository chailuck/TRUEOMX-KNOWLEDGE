# Request_CCBS_OFFER_POOLING_POOLED

> Collects poolable SOC codes from Agreement Offers (SPECIAL_OFFER_INDICATOR = RPD/CPD) and RelatedOffers, then submits to CCBS or CES based on GoldenDB routing flag. Skips if no eligible SOCs found.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_OFFER_POOLING_POOLED` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | CCBS_OFFER_POOLING_POOLED |
| Author | SathidP-PC |
| Backend (default) | CCBS — OfferPoolingPooled endpoint |
| Backend (GoldenDB) | CES — OfferPoolingPooled endpoint |
| Pattern | Fire-and-Forget (sendEventImmediate + RequestCount++) |
| Response Concept | Concepts.FM.Response.CCBS_OfferPoolingpooledRes |

---

## §4 — Rule Conditions (WHEN)

1. `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
2. `orderCurrentActivity.ActivityID == "CCBS_OFFER_POOLING_POOLED"`
3. `orderRequest.ProcessFlow.NextActivityID == "CCBS_OFFER_POOLING_POOLED"`
4. `orderCurrentActivity.Status == "WAITING"`

---

## §5 — Execution Flow

1. Read `GoldenDB` flag from `OrderData.GoldenDB`
2. Collect SOC IDs from POU/ChildOU Agreement Offers where `SPECIAL_OFFER_INDICATOR == "RPD"` or `"CPD"`
3. Append SOC IDs from RelatedOffers (unconditionally)
4. Guard: if `socIDs@length == 0` → SkipActivity; else proceed
5. Determine event type: GoldenDB == "Y" → `CES_OFFER_POOLING_POOLED` (with CES extId); else → `CCBS_OFFER_POOLING_POOLED`
6. Build `ns:OfferPoolingPooledRequest` with one `<SOCCode>` per item
7. `Event.Ext.sendEventImmediate(reqEvent)`; `RequestCount++`
8. Set activity to IN_PROGRESS; send audit log

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Condition |
|-----------|-----------|-----------|
| [OUTBOUND] | CCBS_OFFER_POOLING_POOLED | GoldenDB ≠ "Y" |
| [OUTBOUND] | CES_OFFER_POOLING_POOLED | GoldenDB == "Y" |
| [AUDIT] | OMXESB Logger | Always |

### §8.5 ExtendedInfo Fields

| Field | Source | Required |
|-------|--------|----------|
| GoldenDB (OrderData) | orderRequest.OrderData.GoldenDB | Optional — controls routing |
| SPECIAL_OFFER_INDICATOR | Agreement Offer ExtendedInfo | Required for SOC filtering |

---

## §9 — Payload Build

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority            [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId  [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID        [Conditional]
    ├── CES                  ← OMXUtils:generateTrackingID()          [CES variant only]
    ├── RefID                ← OMXTrackingId                          [Conditional]
    ├── OrderType            ← $orderRequest/OrderData/OrderType      [Conditional]
    └── payload
        └── ns:OfferPoolingPooledRequest
            └── SOCCode      ← socIDs[i]                             [for-each array]
```

---

## §15 — Function Dependency Tree

```text
Request_CCBS_OFFER_POOLING_POOLED
├── GetXMLForAgreementOffer(req, offerRefId)     ← filter by SPECIAL_OFFER_INDICATOR
├── GetXMLForRelatedOffer(req, offerRefId)        ← unconditional
├── OMXUtils.generateTrackingID()                 ← CES extId only
├── Event.Ext.sendEventImmediate(reqEvent)
├── AllowWriteLog(orderType)
├── GetActivityStatusString("1", false)           ← IN_PROGRESS
├── SendDataToDB(orderRequest)
├── SkipActivity(req, activity, "4")              ← if socIDs empty
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 — Migration Notes

| # | Requirement / Risk | Severity |
|---|---|---|
| R1 | Implement GoldenDB routing: GoldenDB=="Y" → CES; else → CCBS | [HIGH] |
| R2 | Filter: SPECIAL_OFFER_INDICATOR = RPD/CPD; always include RelatedOffers | [HIGH] |
| R3 | Skip if socIDs empty | [MEDIUM] |
| R4 | CES variant needs extra `CES` extId field via generateTrackingID() | [MEDIUM] |
| R5 | Response returns "true" unconditionally — no fan-in count | [LOW] |

---

## §19 — Response Message Rule

### §19.1 Overview

Parses `CCBS_OFFER_POOLING_POOLED` response into `CCBS_OfferPoolingpooledRes` concept. Extracts pooled SOC mappings. Returns `"true"` unconditionally.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Order context |
| eventResponse | Events.OMConsumers.OMXFM.Response.CCBS_OFFER_POOLING_POOLED | Backend response |
| currActivity | Concepts.OM.ProcessConfig.Activity | Activity state |

### §19.3 ResponseBase Concept

```text
createObject/object (CCBS_OfferPoolingpooledRes)
├── @extId              ← OMXUtils:generateTrackingID()    [Always]
├── ResponseCode        ← $eventResponse/ResponseCode      [Conditional]
├── ResponseMessage     ← $eventResponse/ResponseMsg       [Conditional]
├── CompletionStatus    ← $eventResponse/CompletionStatus  [Conditional]
├── ReferenceId         ← $eventResponse/RefID             [Conditional]
└── OfferPoolingpooledRes  [for-each PoolingPooledSocsReturn]
    ├── @extId          ← OMXUtils:generateTrackingID()
    ├── PooledSOCCode   ← PooledSoc
    └── PoolingSocCode  ← PoolingSocs/PoolingSoc  [for-each]
```

### §19.4 Fan-in Completion

Returns `"true"` unconditionally — no RequestCount check. Single pooling request advances activity on first response.

OPERATION_NAME: `"CCBS_OFFER_POOLING_POOLED"`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
