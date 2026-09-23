# Request_CCBS_GET_CUSTOMER_INFO

## §1 — Overview & Purpose

Fires when the orchestrator reaches the `CCBS_GET_CUSTOMER_INFO` activity. Retrieves customer header data from CCBS using `GetCustomerHeaderRequest`. The dispatched JMS event type is `CCBS_GET_CUSTOMER_HEADER` — a naming anomaly (same CCBS operation shared between two activity names).

Response handler optionally writes back:
- `OLD_IDENTIFICATION` ExtendedInfo — when parameter `GET_OLD_IDENTIFICATION=Y`
- `CustomerGeneralInfo.Identification` — when parameter `GET_CUST_GENERAL_INFO=Y`

> **⚠ Naming anomaly:** ActivityID is `CCBS_GET_CUSTOMER_INFO` but JMS event dispatched is `CCBS_GET_CUSTOMER_HEADER`. Both use `GetCustomerHeaderRequest`. Modernization must clarify this.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_CUSTOMER_INFO` |
| Priority | 5 |
| forwardChain | true |
| Author | RNAPP-PC |
| Activity ID | `CCBS_GET_CUSTOMER_INFO` |
| JMS Event type | `CCBS_GET_CUSTOMER_HEADER` [Naming anomaly] |
| Fan-in | Simple count: `RequestCount == successResponseCount` |
| Send pattern | `Event.Ext.sendEventImmediate` |

---

## §3 — Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity state & params |

---

## §4 — Rule Conditions

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "CCBS_GET_CUSTOMER_INFO"
orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_CUSTOMER_INFO"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 — Execution Flow

1. Check resubmit flag (`isActResub`)
2. Read PreExecCheck from activity; evaluate against serialized orderRequest
3. If pass: build `GetCustomerHeaderRequest` via XSLT, send immediately
4. Increment `RequestCount` (skip if resubmit)
5. Send audit log
6. Set status WAITING_RESPONSE via `GetActivityStatusString("1", false)`
7. If fail: `SkipActivity(req, act, "4")`

---

## §8 — System & Integration Dependencies

### §8.2 — ESB/JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `CCBS_GET_CUSTOMER_HEADER` | Get customer header from CCBS |
| [INBOUND] | `CCBS_GET_CUSTOMER_HEADER` (response) | Customer header data |

### §8.3 — Backend API

| System | Operation | Schema |
|--------|-----------|--------|
| CCBS | GetCustomerHeaderRequest | `ns:GetCustomerHeaderRequest / ns:CustomerIdInfo / ns:customerNo` |

### §8.5 — Activity Parameters

| Parameter | Value | Effect |
|-----------|-------|--------|
| `GET_OLD_IDENTIFICATION` | Y | Extract OLD_IDENTIFICATION ExtendedInfo |
| `GET_CUST_GENERAL_INFO` | Y | Populate CustomerGeneralInfo.Identification |

---

## §9 — Payload Build

### §9.7 — Generated XML Example

```xml
<GetCustomerHeaderRequest>
  <CustomerIdInfo>
    <customerNo>1234567</customerNo>
  </CustomerIdInfo>
</GetCustomerHeaderRequest>
```

### §9.8 — XSLT Source (summary)

```xml
<!-- Event headers: JMSPriority, JMSCorrelationID, OrderID, RefID, OrderType, CES — all conditional -->
<!-- Payload: single customerNo from Customer.CustomerId -->
<ns:GetCustomerHeaderRequest>
  <ns:CustomerIdInfo>
    <ns:customerNo>← $orderRequest/OrderData/Customer/CustomerId</ns:customerNo>
  </ns:CustomerIdInfo>
</ns:GetCustomerHeaderRequest>
```

---

## §10 — XSLT Field Mapping

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                 [Conditional]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId       [Conditional]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID             [Conditional]
    ├── RefID                    ← $orderRequest/OrderData/Customer/RefId      [Conditional]
    ├── OrderType                ← $orderRequest/OrderData/OrderType           [Conditional]
    ├── CES                      ← $orderRequest/OrderData/CES                 [Conditional]
    └── payload
        └── ns:GetCustomerHeaderRequest
            └── ns:CustomerIdInfo
                └── ns:customerNo  ← Customer/CustomerId                       [Always]
```

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| OPERATION_NAME | `"CCBS_GET_CUSTOMER_INFO"` |
| AUDIT_TRACE (REQ) | `"Request Sent for CCBS_GET_CUSTOMER_INFO"` |
| AUDIT_TRACE (RES) | `"Response received for CCBS_GET_CUSTOMER_INFO"` |

---

## §17 — Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| ActivityID vs JMS event type mismatch | [HIGH] | Align naming; confirm single endpoint |
| Parameter-driven response behavior (GET_OLD_IDENTIFICATION, GET_CUST_GENERAL_INFO) | [MEDIUM] | Make branching explicit |
| Resubmit skips RequestCount++ | [MEDIUM] | Verify fan-in correctness on resubmit |

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_CCBS_GET_CUSTOMER_INFO`: Parses `CCBS_GET_CUSTOMER_HEADER` response. Builds `ResponseBase` and appends to `currActivity.Response`. Conditionally writes identification fields back to orderRequest.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Written back |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_GET_CUSTOMER_HEADER` | Response data |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking |

### §19.3 — ResponseBase

```text
createObject / object
├── extId                 ← OMXUtils:generateTrackingID()    [Always]
├── ResponseCode          ← $eventResponse/ResponseCode      [Conditional]
├── ResponseMessage       ← $eventResponse/ResponseMsg       [Conditional]
├── CompletionStatus      ← $eventResponse/CompletionStatus  [Conditional]
└── ReferenceId           ← $eventResponse/RefID             [Conditional]
```

### §19.4 — Fan-in & Write-back

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"]) == RequestCount
```

| Condition | Write Target | Source |
|-----------|-------------|--------|
| GET_OLD_IDENTIFICATION=Y | `Customer.ExtendedInfo[Name='OLD_IDENTIFICATION']` | `L9Identification` |
| GET_CUST_GENERAL_INFO=Y, CustomerGeneralInfo null | new `CustomerGeneralInfo.Identification` | `L9Identification` |
| GET_CUST_GENERAL_INFO=Y, Identification blank | update `CustomerGeneralInfo.Identification` | XPath on L9Identification |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
