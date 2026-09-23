# Request_CRM_CREATE_UPDATE_SR

## §1 Overview & Purpose

Creates or updates a Service Request (SR) in CRM. Supports both POU and COU subscribers. Uses fire-and-forget dispatch (`sendEventImmediate` — no `assertEvent`, no IntraSeq). Branches on `OrderType` to set CALL_VER_* vs TRUE_CARD_* fields. Gated by `ACTIVITY_LIST*` parameter prefix match.

Trigger: `ActivityID == "CRM_CREATE_UPDATE_SR"` and `Status == "WAITING"`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CRM_CREATE_UPDATE_SR` |
| Author | CHAYATORN-PC |
| Priority | 5 |
| forwardChain | true |
| Fan-in | **FIRE-AND-FORGET** — `sendEventImmediate`, no IntraSeq |
| Backend | CRM |

> **IMPORTANT:** This FM uses `sendEventImmediate` (fire-and-forget), not `assertEvent`. It does NOT use IntraActivitySequencing. The response handler uses `successResponseCount` XPath to detect fan-in completion.

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — source of all payload data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity tracking — RequestCount |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CRM_CREATE_UPDATE_SR"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CRM_CREATE_UPDATE_SR"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Resubmit check
2. Dual POU+COU subscriber loop
3. Guard: `CustomerTypeInfo == null || Type == 0` → throw `DATA_ISSUE` exception
4. Already-succeeded guard: skip if Response has CompletionStatus=2 for this RefId
5. Generate `RefId = String.valueOfLong(System.nanoTime())` (NOT subscriber RefId)
6. Check `isActResub` → if not resubmit: `RequestCount++`
7. Branch on `OrderType`:
   - OrderType=1 or 11013 → CALL_VER_* fields block
   - All others → TRUE_CARD_* and param-driven fields
8. Build CRM event via XSLT — `Event.Ext.sendEventImmediate(reqEvent)` (fire-and-forget)
9. Audit log via `sendEventImmediate(Logger)`
10. Status="1" + `SendDataToDB`; else `SkipActivity("4")`
11. Exception → `HandleActivityException`

---

## §7 Data Extraction

Dual POU+COU loop. POU uses `saleId` / UserText preference. COU always uses params.

### OrderType Branch

| OrderType | Field set | Notes |
|-----------|-----------|-------|
| 1 or 11013 | CALL_VER_* from ExtendedInfo | status="Open" hardcoded |
| All others | TRUE_CARD_* + param-driven fields | status from param |

### POU vs COU Parameter Handling

| Source | POU | COU |
|--------|-----|-----|
| saleId | From order SaleInfo/SaleId (preferred) | From param (always) |
| UserText | From order UserText fallback | From param |
| Other params | From activity params | From activity params |

### Activity Parameters

| Param | Usage |
|-------|-------|
| `ACTIVITY_LIST*` | Gating: must starts-with match for this FM to be active |
| `FCR_GLAG` | → `fcrFlag` field in CRM SR (**NOTE: typo in source**) |
| `AUTO_CLOSE_SR_FLAG` | → `autoCloseSRFlag` (hardcoded `true()` in source) |
| `TRUE_CARD_NUMBER` | → SR summary field |
| `CALL_VER_STATUS` | → callVerStatus (OrderType 1/11013) |

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CRM_CREATE_UPDATE_SR` | Create/update SR in CRM (fire-and-forget) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit trail |

### §8.3 Backend API

| System | Schema Namespace | Protocol |
|--------|-----------------|---------|
| CRM | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CRM/CRMCreateUpdateSRService.xsd` | JMS fire-and-forget |

### §8.5 ExtendedInfo Fields

| Field | Required? | Usage |
|-------|-----------|-------|
| `CALL_VER_STATUS` | Required (OrderType 1/11013) | → SR payload callVerStatus |
| `CALL_VER_RESULT` | Optional | → SR payload callVerResult |
| `CALL_VER_FCR_STATUS` | Optional | → SR payload fcrStatus |
| `CALL_VER_REASON` | Optional | → SR payload callVerReason |
| `TRUE_CARD_NUMBER` | Required (other OrderTypes) | → SR summary |

### §8.6 Global Variables

| Path | Usage |
|------|-------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Conditional credentials |
| `OMX_OM/WritePayload` | Conditional payload logging |

---

## §9 Payload Build

### §9.1 prospectCustomerAccount Fields

| CRM idType field | Source | Notes |
|------------------|--------|-------|
| `idType` | `"Thai ID"` (static) | Always |
| `title` | `"คุณ"` (default) | Subscriber title or fallback |
| `type` | CustomerTypeInfo.Type | 73→Individual; 66-67→Business |

### §9.7 Complete Generated XML Example (OrderType=1)

```xml
<CRMCreateUpdateSRServiceRequest>
  <integrationId>ORD-12345</integrationId>
  <orderType>1</orderType>
  <fcrFlag>N</fcrFlag>
  <summary>0812345678</summary>
  <status>Open</status>
  <productLine>True Mobile</productLine>
  <productType>Postpay</productType>
  <autoCloseSRFlag>true</autoCloseSRFlag>
  <callVerStatus>PASS</callVerStatus>
  <callVerResult>PASS</callVerResult>
  <fcrStatus>UNBAR</fcrStatus>
  <callVerReason>REASON</callVerReason>
  <prospectCustomerAccount>
    <idType>Thai ID</idType>
    <title>คุณ</title>
    <type>Individual</type>
    <msisdn>0812345678</msisdn>
    <saleId>SALE-001</saleId>
  </prospectCustomerAccount>
</CRMCreateUpdateSRServiceRequest>
```

---

## §10 XSLT Field Mapping

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority              [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId    [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID          [Always]
    ├── RefID                ← String.valueOfLong(System.nanoTime())    [Always — nano-time, NOT subscriber RefId]
    ├── UserName             ← $orderRequest/OrderData/User             [Credential-gated]
    ├── PassWord             ← $orderRequest/OrderData/Password         [Credential-gated]
    ├── OrderType            ← $orderRequest/OrderData/OrderType        [Always]
    └── payload
        └── CRMCreateUpdateSRServiceRequest
            ├── integrationId    ← $orderRequest/OrderData/OrderID      [Always]
            ├── orderType        ← $orderRequest/OrderData/OrderType    [Always]
            ├── fcrFlag          ← param "FCR_GLAG" (typo)              [Always]
            ├── summary          ← TRUE_CARD_NUMBER param               [Always]
            ├── status           ← "Open" (static, OrderType 1/11013)   [Conditional: OrderType=1/11013]
            │                      param "STATUS" (other OrderTypes)    [Conditional: other]
            ├── productLine      ← "True Mobile" (static)               [Always]
            ├── productType      ← "Postpay" (static)                   [Always]
            ├── autoCloseSRFlag  ← true() (static)                      [Always]
            ├── callVerStatus    ← CALL_VER_STATUS ExtendedInfo          [Conditional: OrderType=1/11013]
            ├── callVerResult    ← CALL_VER_RESULT ExtendedInfo          [Conditional: OrderType=1/11013]
            ├── fcrStatus        ← CALL_VER_FCR_STATUS ExtendedInfo      [Conditional: OrderType=1/11013]
            ├── callVerReason    ← CALL_VER_REASON ExtendedInfo          [Conditional: OrderType=1/11013]
            └── prospectCustomerAccount
                ├── idType       ← "Thai ID" (static)                   [Always]
                ├── title        ← subscriber title / "คุณ" (default)   [Always]
                ├── type         ← 73→"Individual"; 66/67→"Business"    [Always]
                ├── msisdn       ← $subscriber/MSISDN                   [Always]
                └── saleId       ← POU: SaleInfo/SaleId (preferred)     [Always]
                                   COU: param saleId
```

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_REQ")` |
| OPERATION_NAME | `"CRM_CREATE_UPDATE_SR"` |
| AUDIT_TRACE | `"Request Sent for CRM_CREATE_UPDATE_SR"` (static) |
| payload | Conditional on WritePayload="true" |

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → IN_PROGRESS | Any event sent | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| WAITING → SKIPPED | No qualifying subscribers | `SkipActivity("4")` |

---

## §13 Exception Handling

| Condition | Exception | Action |
|-----------|-----------|--------|
| `CustomerTypeInfo == null \|\| Type == 0` | `DATA_ISSUE` | Thrown immediately, no event sent |
| All other exceptions | — | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §14 Helper Functions

| Function | Purpose |
|----------|---------|
| `GetActivityParameterValueFromKey(act, "FCR_GLAG")` | Retrieve param — note: "FCR_GLAG" is a typo in source |
| `String.valueOfLong(System.nanoTime())` | Generate RefId (nano-time based) |

---

## §15 Function Dependency Tree

```text
Request_CRM_CREATE_UPDATE_SR
├── CustomerTypeInfo null check → throw DATA_ISSUE             [guard]
│
├── POU loop
│   ├── already-succeeded guard
│   ├── RefId = String.valueOfLong(System.nanoTime())
│   ├── if (!isActResub) RequestCount++
│   ├── OrderType branch
│   │   ├── Type=1/11013 → CALL_VER_* fields
│   │   └── Other → TRUE_CARD_* + param fields
│   ├── Event.createEvent("xslt://CRM_CREATE_UPDATE_SR") [POU XSLT]
│   └── Event.Ext.sendEventImmediate(reqEvent)           [FIRE-AND-FORGET]
│
├── COU loop (same structure as POU, always uses params)
│
├── Event.Ext.sendEventImmediate(Logger event)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(orderRequest, act, "4")                       [if isSkipped]
└── HandleActivityException(...)                               [catch]
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | Fire-and-forget — no fan-in barrier; response handler uses successResponseCount XPath |
| R2 | Manual `RequestCount++` per sent event (since no IntraSeq) |
| R3 | OrderType=1 or 11013: CALL_VER_* fields, status="Open" hardcoded |
| R4 | All other OrderTypes: TRUE_CARD_* and param-driven fields |
| R5 | Guard: CustomerTypeInfo==null or Type==0 → DATA_ISSUE exception |
| R6 | POU: prefer SaleInfo/SaleId; COU: always use params |
| R7 | RefId is nano-time (NOT subscriber RefId) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `"FCR_GLAG"` typo in param key | [HIGH] | Must match ProcessConfig exactly — do not correct in migration without updating ProcessConfig too |
| Fire-and-forget: no delivery guarantee | [HIGH] | Verify CRM accepts at-least-once delivery; add idempotency key on CRM side |
| nano-time RefId: non-deterministic on resubmit | [MEDIUM] | Verify CRM SR deduplication; nano-time breaks idempotent retry |
| `autoCloseSRFlag=true()` hardcoded | [MEDIUM] | No runtime override — make configurable via GV if behaviour needs tuning |
| successResponseCount uses `tib:right(tib:trim(ResponseCode), 3)` | [MEDIUM] | Ensure CRM response codes are always ≥3 chars; verify "000" suffix convention |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CRM_CREATE_UPDATE_SR {
  // author: CHAYATORN-PC
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CRM_CREATE_UPDATE_SR";
    orderRequest.ProcessFlow.NextActivityID == "CRM_CREATE_UPDATE_SR";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    // Guard: CustomerTypeInfo==null || Type==0 → throw DATA_ISSUE
    // POU+COU loop, already-succeeded guard
    // RefId = String.valueOfLong(System.nanoTime())
    // if (!isActResub) RequestCount++
    // OrderType 1/11013: CALL_VER_* fields; others: TRUE_CARD_* + params
    // Build CRM event (see §9 for XSLT fields)
    // Event.Ext.sendEventImmediate(reqEvent)   ← FIRE-AND-FORGET (no assertEvent)
    // sendEventImmediate(Logger)
    // Status="1" / SkipActivity("4")
    //
    // NOTE: param key "FCR_GLAG" is a typo — matches ProcessConfig; do not fix independently
  }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

`Response_CRM_CREATE_UPDATE_SR` uses `successResponseCount` XPath pattern (NOT IntraActivitySequencing). Fan-in is manual: compare `currActivity.RequestCount` against count of responses with ResponseCode ending "000".

### §19.2 Scope Variables

| Variable | Type |
|----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CRM_CREATE_UPDATE_SR` |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` |

> Uses `$activityRes/@extId` as extId — the response handler receives a pre-created activity result object (not generated from scratch).

### §19.3 ResponseBase Construction

```text
currActivity (existing object)
├── ResponseCode     ← $eventResponse/ResponseCode             [Always — set directly]
└── ResponseMessage  ← $eventResponse/ResponseMsg              [Always — set directly]
```

> `ResponseCode` and `ResponseMessage` are set directly on `currActivity` (not on a new ResponseBase object).

### §19.4 Response Completion Logic

```xpath
successResponseCount = count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

Fan-in condition: `currActivity.RequestCount == successResponseCount` → returns `"true"`.

When `"true"`: all parallel CRM SR calls completed successfully; activity proceeds to next step.

### §19.5 Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"CRM_CREATE_UPDATE_SR"` |
| AUDIT_TRACE | `"Response received for CRM_CREATE_UPDATE_SR"` (static) |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
