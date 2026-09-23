# Request_SBM_FUP_UPDATE_OU_INFO

## §1 — Overview & Purpose

Invokes SBM FUP `doService` (function_id **104300015**) to update billing cycle information per OU. Loops over all `ParentOU` entries and their nested `ChildOU` entries. One request per OU; RefID is the OU's RefId.

> **Note:** JMS event type dispatched is `SBM_FUP_DO_SERVICE` — the rule name uses the logical alias `SBM_FUP_UPDATE_OU_INFO`. The `ParentOU` list must have been populated by the preceding `INTX_GET_SPECIAL_OFFER_IND_BY_CUST` step.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_SBM_FUP_UPDATE_OU_INFO` |
| Author | RS33-BANDIT |
| Activity ID | `SBM_FUP_UPDATE_OU_INFO` |
| JMS Event type | `SBM_FUP_DO_SERVICE` |
| Loop pattern | ParentOU (outer) + ChildOU (inner) |
| Fan-in | `count(Response[...000]) == RequestCount` |
| Send pattern | `Event.Ext.sendEventImmediate` per OU |

---

## §5 — Execution Flow

1. Check resubmit; if so: `PurgePendingRequestsBeforeResubmit`
2. Outer loop: iterate over `Customer.ParentOU[p]`
3. Per ParentOU: check success, evaluate PreExecCheck via `GetXMLForOU`, send if pass
4. Inner loop: iterate over `ParentOU[p].ChildOU[c]`
5. Per ChildOU: check success, evaluate PreExecCheck via `GetXMLForChildOU`, send if pass
6. Set WAITING_RESPONSE; persist to DB

---

## §8 — System & Integration Dependencies

### §8.2 — ESB/JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `SBM_FUP_DO_SERVICE` | Call SBM FUP doService per OU |
| [INBOUND] | `SBM_FUP_DO_SERVICE` (response) | SBM result + transaction IDs |

### §8.3 — Payload Fields

| Field | Value | Notes |
|-------|-------|-------|
| `ns:function_id` | `"104300015"` | Hardcoded |
| `ns:parameters[fupID]` | OUId (Parent or Child) | OU identifier |
| `ns:parameters[bc]` | `Customer.BillCycleNo` | New billing cycle |
| `ns:service_no` | OUId | Same as fupID |

---

## §10 — XSLT Field Mapping (ParentOU variant)

```text
createEvent / event
├── JMSPriority              ← $orderRequest/OrderPriority         [Conditional]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId [Conditional]
├── OrderID                  ← $orderRequest/OrderData/OrderID     [Conditional]
├── RefID                    ← $pOuRefId (ParentOU.RefId)          [Always]
├── OrderType                ← $orderRequest/OrderData/OrderType   [Conditional]
└── payload / doServiceRequest / req
    ├── function_id          ← "104300015"                         [Always, hardcoded]
    ├── parameters / item[fupID]  ← $pOuId                        [Always]
    ├── parameters / item[bc]     ← Customer/BillCycleNo          [Always]
    └── service_no           ← $pOuId                             [Always]
```

ChildOU variant uses `$cOuRefId` / `$cOuId` instead.

---

## §17 — Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| ParentOU list depends on INTX step having run first | [HIGH] | Enforce ordering; validate ParentOU non-empty before loop |
| function_id=104300015 hardcoded | [MEDIUM] | Move to configuration parameter |
| Event type `SBM_FUP_DO_SERVICE` differs from ActivityID | [MEDIUM] | Align naming in modernized system |
| Nested ParentOU+ChildOU loop — potentially high fanout | [MEDIUM] | Monitor OU counts; consider batching |

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_SBM_FUP_UPDATE_OU_INFO`: Parses `SBM_FUP_DO_SERVICE` response. Creates `SBM_FUP_DoServiceRes` concept with SBM-specific result fields.

### §19.3 — Response Concept (SBM_FUP_DoServiceRes)

```text
SBM_FUP_DoServiceRes
├── ResponseCode         ← $eventResponse/ResponseCode              [Conditional]
├── ResponseMessage      ← $eventResponse/ResponseMsg               [Conditional]
├── CompletionStatus     ← $eventResponse/CompletionStatus          [Conditional]
├── ReferenceId          ← $eventResponse/RefID                     [Conditional]
├── extra_xml            ← doServiceReturn/extra_xml                [Conditional]
├── req_transaction_id   ← doServiceReturn/req_transaction_id       [Conditional]
├── response_message     ← doServiceReturn/response_message         [Conditional]
├── result_code          ← doServiceReturn/result_code              [Conditional]
├── result_desc          ← doServiceReturn/result_desc              [Conditional]
└── transaction_id       ← doServiceReturn/transaction_id           [Conditional]
```

### §19.4 — Fan-in

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"]) == RequestCount
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
