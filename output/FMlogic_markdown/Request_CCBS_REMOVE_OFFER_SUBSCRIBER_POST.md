# Request_CCBS_REMOVE_OFFER_SUBSCRIBER_POST

> Removes offers from source subscribers via CCBS UpdateSubscriberRequest. Pre-builds SOC pooling arrays for all subscribers, then filters per-subscriber offers by FE_OR_CCBS ExtendedInfo.

> **Dead Code:** `logicalDateRes`/`logicalDateVal` loaded but not passed to XSLT — do not replicate.
> **Dead Code:** `ChargeDistributionDetailsInfo` XSLT block has condition `1=0` — never executes.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_REMOVE_OFFER_SUBSCRIBER_POST` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | CCBS_REMOVE_OFFER_SUBSCRIBER_POST |
| Author | RS33-BANDIT |
| Backend | CCBS — UpdateSubscriber endpoint (event: CCBS_UPDATE_SUBSCRIBER) |
| Pattern | IntraActivitySequencing |
| Response Concept | Concepts.FM.Response.CCBS_UpdateSubscriberRes |

---

## §4 — Rule Conditions (WHEN)

1. `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
2. `orderCurrentActivity.ActivityID == "CCBS_REMOVE_OFFER_SUBSCRIBER_POST"`
3. `orderRequest.ProcessFlow.NextActivityID == "CCBS_REMOVE_OFFER_SUBSCRIBER_POST"`
4. `orderCurrentActivity.Status == "WAITING"`

---

## §5 — Execution Flow

1. Purge pending requests if resubmit
2. Load pooling vars: `sPooling` (PoolingIndicator), `sPrefix` (PooledPrefix)
3. Load `logicalDateRes` — **DEAD CODE** (not used in XSLT)
4. Pre-build alSOCs, alPropVal, alInstVal for all subscribers (excl. ServiceType=80)
5. Iterate POU[i] → Subscriber[j]; evaluate PreExecCheck
6. Build `subOffers` list: filter by FE_OR_CCBS + PreExecCheck
7. Skip subscriber if subOffers empty; else build and assert UpdateSubscriberRequest
8. `IntraActivitySequencing.ActionRequestEvent`
9. Repeat for ChildOU (adds extra ParameterInfo from RelatedOffersArray)
10. `IntraActivitySequencing.SendFirstRequestEvent` → IN_PROGRESS

---

## §7 — SOC Arrays Pre-processing

| Array | Source | Purpose |
|-------|--------|---------|
| alSOCs | Distinct SOC codes from all POU+ChildOU offers (excl. ServiceType=80) | SOC lookup keys |
| alPropVal | `GetSplOffIndForSoc.poolingIndicator` | Per-SOC pooling indicator |
| alInstVal | `GetSplOffIndForSoc.poolingInstIndicator` | Per-SOC instance-level indicator |

---

## §9 — Payload Build

```text
createEvent
└── event
    ├── JMSPriority/JMSCorrelationID/OrderID/RefID/OrderType    [Conditional]
    └── payload
        └── ns:UpdateSubscriberRequest
            └── ns:UpdateSubscriberRequest
                ├── SubscriberIdInfo
                ├── ChangeSubscriberOffersWithRelatedOffersInputInfo
                │   └── offersToRemove
                │       ├── dealerCode                           [Always]
                │       ├── deployMode/effectiveDate/expirationDate  [Conditional]
                │       ├── name                 [Cond POU / Always ChildOU]
                │       ├── offerInstanceId      [Conditional if > 0]
                │       ├── relatedOffers
                │       ├── serviceType          [Conditional]
                │       └── soc                  [Always]
                ├── ParameterInfo
                ├── EventDistributionDetailsInfo  [EGI indicator]
                ├── -- ChargeDistributionDetailsInfo DEAD CODE (1=0) --
                └── ActivityInfo
```

---

## §15 — Function Dependency Tree

```text
Request_CCBS_REMOVE_OFFER_SUBSCRIBER_POST
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── System.getGlobalVariableAsString("PoolingPooled/PoolingIndicator")
├── System.getGlobalVariableAsString("PoolingPooled/PooledPrefix")
├── Instance.getByExtIdByUri("LogicalDate", ...)    ← DEAD CODE
├── GetSplOffIndForSoc(soc, sPooling, sPrefix) × N
├── GetXMLForSubscriberOffer(req, subRefId, offerRefId, filter)
├── XPath.evalAsBoolean() × multiple
├── Event.assertEvent(reqEvent)
├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(req, activity, "4")
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 — Migration Notes

| # | Requirement / Risk | Severity |
|---|---|---|
| R1 | Uses CCBS_UPDATE_SUBSCRIBER event — same type as UpdateSubscriber FM; disambiguate routing | [HIGH] |
| R2 | Pre-build SOC arrays before per-subscriber loop | [MEDIUM] |
| [DEAD] | Remove `logicalDateRes`/`logicalDateVal` loading | [LOW] |
| [DEAD] | Remove `ChargeDistributionDetailsInfo` XSLT block (condition `1=0`) | [LOW] |
| R3 | ChildOU variant includes extra ParameterInfo from RelatedOffersArray | [MEDIUM] |
| R4 | Skip subscriber if filtered subOffers list is empty | [MEDIUM] |

---

## §19 — Response Message Rule

### §19.1 Overview

Creates standard `CCBS_UpdateSubscriberRes` with base fields. Fan-in via IntraActivitySequencing.

### §19.4 Fan-in Completion

```text
IntraActivitySequencing.ActionResponseEvent(currActivity)
→ returns "true" when all pending requests have responses
```

Response event type: `Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_SUBSCRIBER`

OPERATION_NAME: `"CCBS_REMOVE_OFFER_SUBSCRIBER_POST"`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
