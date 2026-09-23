# Request_INTX_GET_SPECIAL_OFFER_IND_BY_CUST

## §1 — Overview & Purpose

Fetches special offer indicator records for a customer from INTX using a paginated approach. One JMS request per page is sent; `iteration = ceil(TOTAL_OU / PAGE_SIZE)`. Response handler builds the `ParentOU` list in `orderRequest` — this is the input for the subsequent `SBM_FUP_UPDATE_OU_INFO` step.

> **⚠ Dual usage in CHANGE_CUSTOMER_GENERAL_INFO:** This FM is called twice:
> - **Step 6** (`extId=INTX_GET_TOTAL_OU_BY_CUST`): `PAGE_SIZE=1` — count probe
> - **Step 7** (`extId=INTX_GET_SPECIAL_OFFER_IND_BY_CUST`): `PAGE_SIZE=50` — full fetch
>
> Note: Step 6 has extId=`INTX_GET_TOTAL_OU_BY_CUST` but ActivityID=`INTX_GET_SPECIAL_OFFER_IND_BY_CUST` — naming anomaly.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_SPECIAL_OFFER_IND_BY_CUST` |
| Author | RS33-BANDIT |
| Activity ID | `INTX_GET_SPECIAL_OFFER_IND_BY_CUST` |
| Loop pattern | `iteration = ceil(TOTAL_OU / PAGE_SIZE)` |
| RefID per request | `OMXTrackingId + ":PAGE:" + i` |
| Fan-in | `count(Response[...000]) == RequestCount` |
| Send pattern | `Event.Ext.sendEventImmediate` per page |

---

## §5 — Execution Flow

1. Check resubmit; if so: `PurgePendingRequestsBeforeResubmit`
2. Read `SPECIAL_OFFER_IND` (required), `PAGE_SIZE` (default "50")
3. Validate `SPECIAL_OFFER_IND` — throw DATA_ISSUE if missing
4. Read `TOTAL_OU` ExtendedInfo from orderRequest
5. Compute `iteration = ceil(TOTAL_OU / PAGE_SIZE)`
6. For each page i = 1..iteration: send `GetSpecialOfferIndListByCustomerReq`; increment RequestCount
7. Set WAITING_RESPONSE; persist to DB

---

## §8 — System & Integration Dependencies

### §8.2 — ESB/JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `INTX_GET_SPECIAL_OFFER_IND_BY_CUST` | Paginated special offer query |
| [INBOUND] | `INTX_GET_SPECIAL_OFFER_IND_BY_CUST` (response) | OU special offer arrays |

### §8.3 — Payload Fields

| Field | Source | Notes |
|-------|--------|-------|
| `ns:correlatedId` | `OMXTrackingId` | Always |
| `ns:customerId` | `Customer.CustomerId` | Always |
| `ns:specialOfferIndicator` | `spcIndArr` items | From SPECIAL_OFFER_IND param (comma-separated) |
| `ns:pageSize` | `PAGE_SIZE` param | Default 50 |
| `ns:pageNumber` | Loop variable `i` | 1-based |

---

## §10 — XSLT Field Mapping

```text
createEvent / event
├── JMSPriority              ← $orderRequest/OrderPriority                   [Always]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId         [Always]
├── OrderID                  ← $orderRequest/OrderData/OrderID               [Always]
├── RefID                    ← OMXTrackingId + ":PAGE:" + i                  [Always]
├── UserName / PassWord      ← User / Password                               [Credential-gated]
├── OrderType                ← $orderRequest/OrderData/OrderType             [Always]
└── payload / GetSpecialOfferIndListByCustomerReq
    ├── ns:correlatedId      ← $orderRequest/OrderData/OMXTrackingId         [Always]
    ├── ns:customerId        ← $orderRequest/OrderData/Customer/CustomerId   [Always]
    ├── ns:specialOfferIndicator (×N)  ← for-each spcIndArr/elements         [Always]
    ├── ns:pageSize          ← PAGE_SIZE param                               [Always]
    └── ns:pageNumber        ← $i (loop variable)                            [Always]
```

---

## §17 — Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| extId/ActivityID mismatch at step 6 | [HIGH] | Document dual usage; use distinct activity names in modernized system |
| Pagination depends on TOTAL_OU ExtendedInfo — missing value breaks loop | [HIGH] | Add null/zero guard before computing iterations |
| Response builds ParentOU list — downstream SBM step depends on it | [MEDIUM] | Preserve data contract; validate ParentOU list non-empty |
| SPECIAL_OFFER_IND required — missing throws DATA_ISSUE | [LOW] | Validate at order entry point |

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_INTX_GET_SPECIAL_OFFER_IND_BY_CUST`: For each `ouSpecialOfferArray` entry, creates a **ParentOU** concept and appends to `orderRequest.OrderData.Customer.ParentOU`.

### §19.3 — ParentOU Construction

```text
ParentOU[i] (for each ouSpecialOfferArray)
├── extId      ← concat("OU:", OMXTrackingId, ":", ouId)
├── RefId      ← ouSpecialOfferArray[i]/ou/ouId
└── OUId       ← ouSpecialOfferArray[i]/ou/ouId
```

### §19.4 — Fan-in

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"]) == RequestCount
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
