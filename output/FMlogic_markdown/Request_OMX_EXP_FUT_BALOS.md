# Request_OMX_EXP_FUT_BALOS

> Expire future orders from a prior OMX_SEARCH_FUT result — dual usage: FULLSUS/FCVG/CCVG expiry (step 36, no param) and CANCEL expiry (step 38, EXT=_CANCEL).

**Priority:** 5 | **ForwardChain:** true | **Target:** OMX (internal) | **Event:** OMX_UPDATE_FUTURE | **Fan-in:** hardcoded "true" | **Used in RESTORE:** Steps 36, 38

---

## §1 — Overview & Purpose

Order-level FM (no subscriber loop). Reads the results of a prior `OMX_SEARCH_FUT` or `OMX_SEARCH_FUT_CANCEL` activity from `ProcessFlow.Activities[]`, filters matching future orders, and sends `OMX_UPDATE_FUTURE` to set their status to 4 (expired).

> **Fan-in: hardcoded "true"** — Response rulefunction always returns `"true"` regardless of ResponseCode. Failures are silently accepted. `[HIGH]` migration risk.

> **Logger OPERATION_NAME:** Both request and response use `"OMX_EXP_FUT"` — not `"OMX_EXP_FUT_BALOS"`.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_EXP_FUT_BALOS` |
| Priority | 5 |
| ForwardChain | true |
| Author | usuf-chu |
| Target system | OMX (internal) |
| JMS event | `OMX_UPDATE_FUTURE` |
| Response concept | `Concepts.FM.Response.OMX_UpdateFutureRes` |
| Fan-in | Hardcoded "true" — always advances |

---

## §3 — Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `OrderRequest` | Order context; ProcessFlow.Activities[] scanned |
| `orderCurrentActivity` | `Activity` | Parameter[] for EXT key |

**Prior activity read:**

| ExtId | Used when |
|-------|-----------|
| `PROCESS:OMX_SEARCH_FUT` | No EXT param (step 36) |
| `PROCESS:OMX_SEARCH_FUT_CANCEL` | EXT=_CANCEL (step 38) |

---

## §4 — Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "OMX_EXP_FUT_BALOS"
orderRequest.ProcessFlow.NextActivityID == "OMX_EXP_FUT_BALOS"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 — Execution Flow

1. Evaluate PreExecCheck on serialised `orderRequest` (order-level)
2. Build `reqActivityExtID = ProcessFlow@extId + ":OMX_SEARCH_FUT"`; `type = "FULLSUS"`
3. Parse Parameter[] for key `EXT`; if found: append EXT value to reqActivityExtID; `type = "CANCEL"`
4. Scan `ProcessFlow.Activities[]` for matching extId; read `Response[0].FutureOrders[]` as `future`
5. If future != null and FutureOrders.length > 0: build `OMX_UPDATE_FUTURE` event with filter
6. Guard: send only if `count(futureOrder) > 0` in built event; increment RequestCount; send audit log
7. If skipped → `SkipActivity("4")`; else status=PROCESSING + `SendDataToDB`

---

## §7 — Parameter Parsing

Parameters are `key=value` pairs parsed via `tib:tokenize($param, "=")`:

| Key | Value | Effect |
|-----|-------|--------|
| `EXT` | `_CANCEL` | Appends to reqActivityExtID → `...OMX_SEARCH_FUT_CANCEL`; sets type="CANCEL" |

No EXT parameter → default FULLSUS mode targeting `OMX_SEARCH_FUT`.

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS

| Direction | Event | Purpose |
|-----------|-------|---------|
| `[OUTBOUND]` | `OMX_UPDATE_FUTURE` | Set matched future orders to status=4 (expired) |
| `[LOG]` | `Logger` | OPERATION_NAME="OMX_EXP_FUT" |

### §8.3 Backend API

| Field | Value |
|-------|-------|
| System | OMX (internal) |
| Payload root | `ns:futureOrders` |
| Schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd` |

### §8.4 Future Order Filter Criteria

| futureType | ActivityReason | Included |
|------------|----------------|----------|
| `FULLSUS` | `SUS1` | Yes |
| `FULLSUS` | `FCVG` | Yes |
| `CANSUB` | `CCVG` | Yes |
| Anything else | Any | No |

---

## §10 — XSLT Field Mapping Tree

```text
createEvent
└── event
    ├── JMSPriority      ← $orderRequest/OrderPriority              [Conditional]
    ├── JMSCorrelationID ← $orderRequest/OrderData/OMXTrackingId    [Conditional]
    ├── OrderID          ← $orderRequest/OrderData/OrderID           [Conditional]
    ├── UserName         ← $orderRequest/OrderData/User              [Conditional]
    ├── PassWord         ← $orderRequest/OrderData/Password          [Conditional]
    ├── OrderType        ← $orderRequest/OrderData/OrderType         [Conditional]
    └── payload
        └── ns:futureOrders  [xsl:for-each on future.FutureOrders, filtered]
            └── ns:futureOrder  [Conditional: filter criteria]
                ├── ns:futureOrderId ← FutureOrderId              [Conditional]
                ├── ns:status        ← 4                          [Always, hardcoded]
                ├── ns:orderType     ← OrderType                  [Conditional]
                ├── ns:nodeLevel     ← NodeLevel                  [Conditional]
                ├── ns:nodeId        ← NodeId                     [Conditional]
                ├── ns:updatedDate   ← UpdatedDate                [Conditional]
                ├── ns:updatedBy     ← "OMX"                      [Always, hardcoded]
                └── ns:remark        ← concat(Remark + "Remove <type> From restore order : " + OMXTrackingId) [Always]
```

---

## §17 — Migration Notes

| ID | Requirement |
|----|-------------|
| R1 | Two modes via EXT param: FULLSUS (step 36) and CANCEL (step 38) |
| R2 | Source future orders from prior OMX_SEARCH_FUT or OMX_SEARCH_FUT_CANCEL result in ProcessFlow |
| R3 | Filter: FULLSUS/SUS1, FULLSUS/FCVG, CANSUB/CCVG only |
| R4 | status=4 (expire); updatedBy="OMX"; append remark with OMXTrackingId |
| R5 | Response always returns "true" — failures silently accepted |

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Hardcoded "true" return — failures silently ignored | `[HIGH]` | Add ResponseCode check; alert on non-"000" |
| Parameter-driven source lookup — tight coupling to extId naming | `[MEDIUM]` | Explicit source activity ID in service config |
| OPERATION_NAME="OMX_EXP_FUT" — does not match rule name | `[MEDIUM]` | Standardise log names |

---

## §19 — Response Rule: Response_OMX_EXP_FUT_BALOS

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `OrderRequest` | Order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_UPDATE_FUTURE` | Inbound response |
| `currActivity` | `Activity` | Activity for response append |

### §19.3 OMX_UpdateFutureRes Concept

```text
OMX_UpdateFutureRes
├── ResponseCode     ← $eventResponse/ResponseCode     [Conditional]
├── ResponseMessage  ← $eventResponse/ResponseMsg      [Conditional]
└── CompletionStatus ← $eventResponse/CompletionStatus [Conditional]
```

> No `ReferenceId` — order-level response, no subscriber iteration.

### §19.4 Fan-in Logic

> **[HIGH RISK]** Response rulefunction **always returns `"true"`** — no ResponseCode check. Even on error, process advances. Silent failure risk — add explicit check in migration.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
