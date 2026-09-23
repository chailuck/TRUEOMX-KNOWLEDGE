# Request_CCBS_SWAP_SIM_POSTPAID_SUB

> Update postpaid subscriber SIM + IMSI on CCBS via UpdateSubscriberRequest bundled with GetSequenceValueRequest; uses pooling indicator logic; only fires for TARGET subscribers that haven't called MSIM_SWAP_SIM.

> **Bug:** Request-side audit logger OPERATION_NAME reads "CCBS_SPWAP_SIM_POSTPAID_SUB" (typo — "SPWAP" instead of "SWAP"). Response logger is correct. Fix in migration target.
> **Dead code:** `logicalDateRes` and `logicalDateVal` loaded from working memory but never used.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_SWAP_SIM_POSTPAID_SUB` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | CCBS_SWAP_SIM_POSTPAID_SUB |
| Author | TrueOM |
| Backend | CCBS (UpdateSubscriber endpoint) |
| Pattern | IntraActivitySequencing |

---

## §5 — Execution Flow

1. If resubmit: `PurgePendingRequestsBeforeResubmit`
2. Load global vars: `sPooling` (PoolingPooled/PoolingIndicator), `sPrefix` (PoolingPooled/PooledPrefix)
3. Load `logicalDateRes` from working memory **(DEAD CODE — never used)**
4. Collect distinct SOCs from all subscribers (excl. ServiceType=80) → build alSOCs, alPropVal, alInstVal
5. Loop POU[i] → Subscriber[j]; evaluate PreExecCheck; check reqSuccess guard
6. Build `subOffersArray`: filter offers by PreExecCheck (FE_OR_CCBS) — only dispatch if length > 0
7. Build and assert UpdateSubscriberRequest event; ActionRequestEvent
8. Repeat for ChildOU subscribers
9. SendFirstRequestEvent → IN_PROGRESS; or SkipActivity

---

## §7 — SOC Arrays Pre-processing

| Array | Source | Purpose |
|-------|--------|---------|
| alSOCs | Distinct SOC codes from all subscribers | Look up pooling indicator per SOC |
| alPropVal | `GetSplOffIndForSoc.poolingIndicator` | Pooling indicator per SOC |
| alInstVal | `GetSplOffIndForSoc.poolingInstIndicator` | Instance-level pooling indicator |

---

## §9 — Payload Build

```text
createEvent / event
├── JMSPriority / JMSCorrelationID / OrderID / CES / RefID / OrderType  [Conditional/Always]
├── UserName / PassWord                                                   [Credential-gated]
└── payload
    ├── ns1:GetSequenceValueRequest
    │   ├── sequenceName      ← "SOC_SEQ_NO"
    │   └── incrementByCount  ← count(subOffersArray) + count(relatedOffersArray)
    └── ns:UpdateSubscriberRequest
        ├── SubscriberIdInfo/subscrNumber  ← subscriber/SubscriberId
        ├── ChangeLogicalResourceInputInfo (IMSI change)
        │   ├── ResourceName     ← "IMSI"
        │   ├── NewResourceValue ← ResourceInfo[IMSI]/ValuesArray
        │   ├── ActivityReason   ← SubscriberActivityInfo/ActivityReason → else 'CREQ'
        │   └── UserText         ← SubscriberActivityInfo/UserText        [Conditional]
        ├── ReplacePhysicalResourceInputInfo (SIM change)
        │   ├── ResourceName     ← "SIM"
        │   ├── NewResourceValue ← ResourceInfo[SIM]/ValuesArray
        │   └── ActivityReason   ← SubscriberActivityInfo/ActivityReason → else 'CREQ'
        └── ActivityInfo
            ├── activityReason ← SubscriberActivityInfo/ActivityReason → else 'CREQ'
            └── userText       ← SubscriberActivityInfo/UserText          [Conditional]
```

---

## §15 — Function Dependency Tree

```text
Request_CCBS_SWAP_SIM_POSTPAID_SUB
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── System.getGlobalVariableAsString("PoolingPooled/PoolingIndicator")
├── System.getGlobalVariableAsString("PoolingPooled/PooledPrefix")
├── Instance.getByExtIdByUri("LogicalDate", ...)   ← DEAD CODE
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

| # | Requirement / Risk |
|---|-------------------|
| R1 | Bundle GetSequenceValueRequest (SOC_SEQ_NO) with UpdateSubscriberRequest in one call |
| R2 | Support both ChangeLogicalResourceInputInfo (IMSI) and ReplacePhysicalResourceInputInfo (SIM) |
| R3 | ActivityReason defaults to 'CREQ' if not provided |
| R4 | Skip subscriber if filtered subOffersArray is empty |
| [BUG] | Fix OPERATION_NAME typo "CCBS_SPWAP_SIM_POSTPAID_SUB" → "CCBS_SWAP_SIM_POSTPAID_SUB" |
| [DEAD] | Remove logicalDateRes/logicalDateVal loading |

---

## §19 — Response Message Rule

Creates `CCBS_SwapSIMPostpaidSubRes` concept.

Fan-in: `IntraActivitySequencing.ActionResponseEvent(currActivity)`

OPERATION_NAME in response logger: `"CCBS_SWAP_SIM_POSTPAID_SUB"` (correct)

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
