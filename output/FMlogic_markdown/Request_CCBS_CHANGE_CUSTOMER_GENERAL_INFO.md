# Request_CCBS_CHANGE_CUSTOMER_GENERAL_INFO

## §1 — Overview & Purpose

Invokes CCBS `ChangeCustomerGeneralRequest` to update customer personal information. Conditional fields include BirthDate, contactLang, Grading, Identification, IdentificationExpDate, IdentificationType, and trueId. Uses **IntraActivitySequencing** (ActionRequestEvent + SendFirstRequestEvent).

> **⚠ Dead code risk:** The original `ActionResponseEvent` completion check in the response handler is commented out. Current fan-in uses simple `RequestCount == successResponseCount`. If the activity ever issues multiple requests, this will break.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CHANGE_CUSTOMER_GENERAL_INFO` |
| Priority | 5 |
| forwardChain | true |
| Activity ID | `CCBS_CHANGE_CUSTOMER_GENERAL_INFO` |
| Fan-in | IntraActivitySequencing (ActionRequestEvent + SendFirstRequestEvent) |
| Send pattern | `Event.assertEvent` + `SendFirstRequestEvent` |

---

## §3 — Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order & customer data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity state |
| `logicalDateRes` | `Concepts.OM.LogicalDate` | Logical date singleton |

---

## §5 — Execution Flow

1. Read `LogicalDate` singleton
2. Evaluate `PreExecCheck` against `orderRequest.OrderData`
3. If resubmit: `PurgePendingRequestsBeforeResubmit`
4. Build `ChangeCustomerGeneralRequest` via XSLT
5. `Event.assertEvent(reqEvent)` — add to working memory
6. `IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)`
7. Send audit log
8. `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)`
9. Set WAITING_RESPONSE; persist to DB

---

## §8 — System & Integration Dependencies

### §8.2 — ESB/JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `CCBS_CHANGE_CUSTOMER_GENERAL_INFO` | Update customer general info |
| [INBOUND] | `CCBS_CHANGE_CUSTOMER_GENERAL_INFO` (response) | Confirmation |

### §8.5 — Payload Fields

| Source | CCBS Target | Condition |
|--------|-------------|-----------|
| `CustomerGeneralInfo.BirthDate` | `ns:L9BirthDate` | field exists |
| `CustomerGeneralInfo.contactLang` | `ns:L9ContactLang` | non-empty |
| `CustomerGeneralInfo.Grading` | `ns:L9Grading` | non-empty |
| `CustomerGeneralInfo.Identification` | `ns:L9Identification` | non-empty |
| `CustomerGeneralInfo.IdentificationExpDate` | `ns:L9IdentificationExpDate` | non-empty |
| `CustomerGeneralInfo.IdentificationType` | `ns:L9IdentificationType` | non-empty |
| `CustomerGeneralInfo.trueId` | `ns:L9TrueId` | != '' |
| `ActivityReason` (or "CREQ") | `ns3:ActivityReason` | Always |

### §8.6 — Global Variables

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Credential gate |

---

## §10 — XSLT Field Mapping

```text
createEvent / event
├── JMSPriority              ← $orderRequest/OrderPriority          [Always]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId [Always]
├── OrderID                  ← $orderRequest/OrderData/OrderID       [Always]
├── UserName                 ← OrderData/User       [Conditional: IsEnableUserPass='true']
├── PassWord                 ← OrderData/Password   [Conditional: IsEnableUserPass='true']
├── OrderType                ← OrderData/OrderType  [Conditional]
├── CES                      ← OrderData/CES        [Conditional]
└── payload / ChangeCustomerGeneralRequest
    ├── CustomerIdInfo / CustomerNo  ← Customer/CustomerId  [Conditional]
    ├── CustomerGeneralInfo
    │   ├── L9BirthDate              ← BirthDate             [Conditional]
    │   ├── L9ContactLang            ← contactLang           [Conditional: non-empty]
    │   ├── L9Grading                ← Grading               [Conditional: non-empty]
    │   ├── L9Identification         ← Identification        [Conditional: non-empty]
    │   ├── L9IdentificationExpDate  ← IdentificationExpDate [Conditional: non-empty]
    │   ├── L9IdentificationType     ← IdentificationType    [Conditional: non-empty]
    │   └── L9TrueId                 ← trueId               [Conditional: != '']
    └── ActivityInfo
        ├── ActivityReason  ← ActivityReason or "CREQ"  [Always]
        └── UserText        ← CustomerActivityInfo/UserText [Conditional]
```

---

## §17 — Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Commented-out `ActionResponseEvent` in response handler | [HIGH] | Confirm single-request assumption; restore if multi-request ever needed |
| All customer fields conditionally mapped | [MEDIUM] | Document CCBS partial update policy |
| Credential gate via global variable | [MEDIUM] | Use secure credential provider in modernized system |

---

## §19 — Response Message Rule

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_CHANGE_CUSTOMER_GENERAL_INFO` | Response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in |

### §19.3 — ResponseBase (`CCBS_ChangeCustomerGeneralInfoRes`)

```text
createObject / object
├── extId               ← sysNanoTimeValue                [Always]
├── ResponseCode        ← $eventResponse/ResponseCode     [Always]
├── ResponseMessage     ← $eventResponse/ResponseMsg      [Always]
├── CompletionStatus    ← $eventResponse/CompletionStatus [Always]
└── ReferenceId         ← $eventResponse/RefID            [Always]
```

### §19.4 — Fan-in

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"]) == currActivity.RequestCount
// Note: IntraActivitySequencing.ActionResponseEvent commented out
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
