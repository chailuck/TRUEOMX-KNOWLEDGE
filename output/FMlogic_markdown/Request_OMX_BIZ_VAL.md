# Request_OMX_BIZ_VAL

**Rule class:** `Rules.OMConsumers.OMXOM.OMX_BusinessValidations`
**File:** `OMX_BusinessValidations.rule`
**Author:** mranade-T420 | **Priority:** 5 | **forwardChain:** true
**Type:** Internal OMX Validation Gate (OMXOM) — No External Backend Call
**Pattern:** VRF Decision Table Invocation

---

## §1 — Overview & Purpose

This rule is a **business validation checkpoint** that invokes an order-type-specific VRF (Virtual Rule Function) decision table before the order proceeds to provisioning activities. If the validation fails, the order is immediately terminated with a structured error code. **No JMS or ESB event is sent to any backend system.**

The rule serialises the entire order request to XML and invokes the decision table `BusinessValidations_<OrderType>DT` (e.g., `BusinessValidations_65DT` for PREPAID_CANCEL) via the VRF framework. The decision table evaluates all business constraints for that order type and writes its verdict into `orderRequest.BusinessValidationResult` and `orderRequest.BusinessValidationMsg`.

| Item | Value |
|------|-------|
| Rule class | `Rules.OMConsumers.OMXOM.OMX_BusinessValidations` |
| ActivityID | `OMX_BIZ_VAL` |
| Author | mranade-T420 |
| Backend call | None — invokes local VRF decision table |
| VRF path | `/DecisionTables/BusinessValidationsVRF` |
| DT naming pattern | `BusinessValidations_<OrderType>DT` |
| Completion on pass | `NextActivity` (synchronous) |
| Completion on fail | Activity FAILED + Order FAILED or DELETED |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule type | `rule` | RETE stateful rule |
| priority | 5 | Standard priority |
| forwardChain | true | Re-evaluates if working memory changes during execution |
| Namespace | OMXOM | Internal OMX — not an external FM rule |
| Response rulefunction | None | Synchronous — no async backend call |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Root order — serialised for VRF input; BusinessValidationResult/Msg written by VRF |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Current activity — Status and ResponseCode written on failure |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Meaning |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity matches current process step |
| 2 | `orderCurrentActivity.ActivityID == "OMX_BIZ_VAL"` | This rule fires only for the business validation step |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_BIZ_VAL"` | Process flow confirms this step is next |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity has not yet been processed |

---

## §5 — Execution Flow Diagram

1. **Serialise order:** `sXML = Instance.serializeUsingDefaults(orderRequest)` — serialises the full order object graph to XML for XPath-based PreExecCheck.
2. **PreExecCheck (order-level):** If `PreExecCheck` is set on the activity, evaluate XPath against the full order XML. If result != "true", skip via `SkipActivity("4")`.
3. **Reset validation state:** `orderRequest.BusinessValidationResult = true` and `BusinessValidationMsg = ""` — default to passing before DT is invoked.
4. **Extract process name:** Split `ProcessFlow@extId` on ":" → use last token as first VRF arg (process name).
5. **Invoke VRF decision table:** `VRF.invokeVRFImplByName("/DecisionTables/BusinessValidationsVRF", "BusinessValidations_"+OrderType+"DT", args)` — DT writes result into `BusinessValidationResult` / `BusinessValidationMsg`.
6. **Pass path:** If `BusinessValidationResult == true` → `NextActivity` + success audit log.
7. **Fail path — soft:** If `BusinessValidationResult == false` and `DeleteOrderFromCache == false` → set status FAILED, build error code, persist to DB, log to ErrorLog channel.
8. **Fail path — hard:** If `BusinessValidationResult == false` and `DeleteOrderFromCache == true` → set order status 8, persist to DB, `Instance.deleteInstance(orderRequest)`, decrement engine count.

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### §6.1 Validation Invocation

| Step | Code | Detail |
|------|------|--------|
| Serialise | `Instance.serializeUsingDefaults(orderRequest)` | Full order XML (order-level, not per-subscriber) |
| PreExecCheck | `XPath.execute("/("+chkXPath+")", sXML, "ns0=...")` | Uses full order XML, not subscriber XML |
| Reset result | `BusinessValidationResult=true; BusinessValidationMsg=""` | VRF will override on failure |
| Extract process name | `String.split(ProcessFlow@extId, ":")[last]` | e.g., "PREPAID_CANCEL" |
| VRF args | `{processName, orderRequest}` | Two-element Object array |
| Invoke DT | `VRF.invokeVRFImplByName("/DecisionTables/BusinessValidationsVRF", "BusinessValidations_"+OrderType+"DT", args)` | Order-type-specific DT |

### §6.2 Failure Path — Error Code Construction

| Segment | GlobalVar path | Default | Example |
|---------|---------------|---------|---------|
| compNm | `OMX_OM/ComponentName` | "OM" | OM |
| svcCode | `OMX_OM/Services/OMServices` | "01" | 01 |
| opCode | `OMX_OM/Operations/SubmitOrder` | "01" | 01 |
| sev | `OMX_COMMON/Severity/High` | "03" | 03 |
| errCode | `OMX_OM/ResponseCodes/BusinessValidationsFailed` | "004" | 004 or "-CUST01" |

Composed: `respCode = compNm+svcCode+opCode+sev+errCode` → e.g., `"OM010103004"` or `"OM010103-CUST01"`

If `BusinessValidationCode` is non-empty, errCode = `"-"+BusinessValidationCode` (overrides the GlobalVar default).

### §6.3 Failure Path — DeleteOrderFromCache Branching

| DeleteOrderFromCache | Actions |
|---------------------|---------|
| `true` | Set orderStatus=8, `SendDataToDB`, `Instance.deleteInstance(orderRequest)`, `EngineManagement.SetOrderCount(-1)` — hard eviction from working memory |
| `false` | Set activity Status="3" (FAILED), orderStatus=3 (FAILED), `SendDataToDB`, log error to ErrorLog channel (if AllowWriteLog) |

> **Hard eviction path:** When `DeleteOrderFromCache=true`, the orderRequest concept is permanently removed from the BE working memory. No audit log is written in this path. Any RETE rules holding references to `orderRequest` will retract immediately.

---

## §7 — VRF Decision Table Architecture

> **VRF (Virtual Rule Function)** is a TIBCO BE mechanism for polymorphic rule function dispatch. `invokeVRFImplByName` selects a specific implementation of the VRF interface by its registered name — here, the implementation name is derived from the order type, enabling per-order-type validation logic without code branching.

| Element | Value | Notes |
|---------|-------|-------|
| VRF interface path | `/DecisionTables/BusinessValidationsVRF` | Parent VRF definition |
| DT name pattern | `BusinessValidations_<OrderType>DT` | One DT per order type (e.g., BusinessValidations_65DT) |
| Args[0] | Process name (last segment of ProcessFlow extId) | e.g., "PREPAID_CANCEL" |
| Args[1] | `orderRequest` | Full order concept graph |
| Output written | `orderRequest.BusinessValidationResult` (boolean) | true = pass, false = fail |
| Output written | `orderRequest.BusinessValidationMsg` (String) | Human-readable failure reason |
| Output written | `orderRequest.BusinessValidationCode` (String) | Machine-readable code for error code suffix (optional) |

> **[MEDIUM]** If the DT named `BusinessValidations_<OrderType>DT` does not exist in the VRF registry, `invokeVRFImplByName` throws a runtime exception. This is caught by the outer `catch` and routes to `HandleActivityException` — the order fails with a generic exception error rather than a meaningful validation error code. New order types must have a matching DT registered.

The commented-out line `VRF.invokeAllVRFImpls(...)` shows the original approach was to invoke ALL registered implementations; this was replaced with the targeted `invokeVRFImplByName` pattern to allow per-order-type validation rules.

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

A unique decision table must exist for each order type: `BusinessValidations_<OrderType>DT`. For PREPAID_CANCEL this would be `BusinessValidations_65DT` (assuming OrderType=65). The DT contains all business rules applicable to that order type — subscriber status requirements, pre-conditions, conflict checks, etc.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel / Event | Used when | Routing |
|-----------|-----------------|-----------|---------|
| [LOG SUCCESS] | Events.OMConsumers.OMXESB.Logger | Validation passed (AllowWriteLog gate) | `Event.Ext.sendEventImmediate` |
| [LOG FAILURE] | Events.OMConsumers.OMXESB.Logger → ErrorLog channel | Validation failed (AllowWriteLog gate) | `Event.Ext.routeToImmediate(..., "/Channels/LogConnection/ErrorLog", "")` |

> Two different routing mechanisms are used for success vs failure logs. Success uses `sendEventImmediate`; failure uses `routeToImmediate` with explicit ErrorLog channel. Both are gated by `AllowWriteLog` — validation failures for certain order types may never be logged to ErrorLog.

### §8.3 Working Memory Written

| Field | Written when | Value |
|-------|-------------|-------|
| `orderRequest.BusinessValidationResult` | Always (before VRF) | true (reset); VRF may set false |
| `orderRequest.BusinessValidationMsg` | Always (before VRF) | "" (reset); VRF may set message |
| `orderRequest.ResponseCode` | Validation failed | Composed error code (see §6) |
| `orderRequest.ResponseMessage` | Validation failed | `BusinessValidationMsg` from VRF |
| `orderRequest.OrderStatus` | Fail (soft=3, hard=8) | Status code 3 or 8 |
| `orderCurrentActivity.Status` | Validation failed (soft) | GetActivityStatusString("3",false) → FAILED |
| `orderCurrentActivity.ResponseCode` | Validation failed | Same as orderRequest.ResponseCode |
| `orderCurrentActivity.ResponseMessage` | Validation failed | `BusinessValidationMsg` |

### §8.4 Global Variable Dependencies

| Path | Default | Used for |
|------|---------|---------|
| `OMX_OM/ComponentName` | "OM" | Error code prefix: component identifier |
| `OMX_OM/Services/OMServices` | "01" | Error code: service segment |
| `OMX_OM/Operations/SubmitOrder` | "01" | Error code: operation segment |
| `OMX_COMMON/Severity/High` | "03" | Error code: severity segment |
| `OMX_OM/ResponseCodes/BusinessValidationsFailed` | "004" | Error code: error type segment (overridden by BusinessValidationCode) |
| `OMX_COMMON/Component_Name/OMX_CEP` | — | Audit log COMPONENT_NAME |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | — | Audit log LOG_LEVEL |

---

## §9 — Payload Build (Not Applicable)

This rule performs no outbound messaging. The "payload" is the order request object serialised via `Instance.serializeUsingDefaults` and passed to the VRF. The VRF decision table processes this internally — no XML is sent over JMS.

---

## §10 — XSLT Field Mapping (Not Applicable)

No XSLT payload mapping. The two audit log events share the following structure:

```text
event (success)
├── ESBUUID              ← $orderRequest/OrderData/OMXTrackingId    [Conditional]
├── PROCESS_ID           ← concat(nanoTime, "_RES")                 [Always]
├── OPERATION_NAME       ← "/Rules/OMConsumers/OMXOM/OMX_BusinessValidations"  [Always]
├── AUDIT_TRACE          ← "OMX-OM business validations passed."    [Always]
└── payload              ← <payload/> (empty)                        [Always]

event (failure)
├── ESBUUID              ← $orderRequest/OrderData/OMXTrackingId    [Conditional]
├── PROCESS_ID           ← concat(nanoTime, "_REQ")                 [Always — uses "_REQ", unusual for failure log]
├── OPERATION_NAME       ← "/Rules/OMConsumers/OMXOM/OMX_BusinessValidations"  [Always]
├── ERROR_CODE           ← $respCode                                 [Always]
├── ERROR_MSG            ← $orderRequest/BusinessValidationMsg       [Conditional]
└── payload              ← <payload/> (empty)                        [Always]
```

---

## §11 — Audit Logging

| Path | Event type | Routing | Gated? |
|------|-----------|---------|--------|
| Validation passed | Logger (success) | `Event.Ext.sendEventImmediate` | Yes — `AllowWriteLog` |
| Validation failed (soft) | Logger (failure) → ErrorLog | `Event.Ext.routeToImmediate(..., "/Channels/LogConnection/ErrorLog", "")` | Yes — `AllowWriteLog` |
| Validation failed (hard delete) | None | N/A — orderRequest deleted before log | N/A |

> The failure log event uses `PROCESS_ID` with `"_REQ"` suffix (not `"_RES"`) — inconsistent with most other OMX rules. The failure log routes to the ErrorLog channel rather than the standard Logger. Both paths are gated by `AllowWriteLog` — validation failures for certain order types may never be logged.

---

## §12 — Activity Status Management

| Outcome | Activity status | Order status | Mechanism |
|---------|----------------|-------------|-----------|
| PreExecCheck false | SKIPPED | unchanged | `SkipActivity("4")` |
| Validation passed | COMPLETED (via NextActivity) | unchanged | `NextActivity(orderRequest, orderCurrentActivity)` |
| Validation failed (soft) | FAILED (code "3") | FAILED (code 3) | `GetActivityStatusString("3", false)` + `GetOrderStatusString(3)` |
| Validation failed (hard delete) | N/A (order deleted) | 8 (deleted) | `GetOrderStatusString(8)` + `Instance.deleteInstance` |

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

Any exception — including a missing VRF decision table — is caught and handled generically. The order fails without the structured validation error code that would normally be built in the failure path.

> **[MEDIUM]:** A missing `BusinessValidations_<OrderType>DT` causes a runtime exception, not a clean validation failure. The error is indistinguishable from a code bug unless the exception message is checked in the audit log.

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|----------|--------|---------|
| `Instance.serializeUsingDefaults(orderRequest)` | String (XML) | Serialises full order object graph for XPath evaluation |
| `VRF.invokeVRFImplByName(path, name, args)` | void | Dispatches to named VRF implementation (decision table) |
| `System.getGlobalVariableAsString(path, default)` | String | Reads error code segments from GlobalVars |
| `RuleFunctions.Helpers.GetActivityStatusString("3", false)` | String | Maps code "3" to FAILED status string |
| `RuleFunctions.Helpers.GetOrderStatusString(3)` | String | Maps 3 to FAILED order status; 8 to DELETED |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | void | Persists order to database |
| `Instance.deleteInstance(orderRequest)` | void | Evicts order concept from BE working memory (hard delete) |
| `RuleFunctions.Helpers.EngineManagement.SetOrderCount(-1)` | void | Decrements engine's active order counter after hard delete |
| `RuleFunctions.Helpers.AllowWriteLog(orderType)` | boolean | Gates audit logging by order type |
| `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` | void | Advances process flow on validation pass |
| `RuleFunctions.Helpers.SkipActivity(req, act, "4")` | void | Skips activity if PreExecCheck is false |
| `RuleFunctions.Helpers.HandleActivityException(req, act, ae, "")` | void | Generic exception handler |

---

## §15 — Function Dependency Tree

```text
OMX_BusinessValidations / OMX_BIZ_VAL (rule)
├── Instance.serializeUsingDefaults(orderRequest)              [BE built-in]
├── XPath.execute(PreExecCheck, sXML)                          [BE built-in]
├── VRF.invokeVRFImplByName("/DecisionTables/BusinessValidationsVRF",
│       "BusinessValidations_"+OrderType+"DT", {processName, orderRequest})
│   └── [Decision Table]: BusinessValidations_<OrderType>DT
│       ├── Reads: all fields of orderRequest
│       └── Writes: BusinessValidationResult, BusinessValidationMsg, BusinessValidationCode
├── [PASS PATH]
│   ├── RuleFunctions.Helpers.NextActivity(req, act)          [helper]
│   ├── RuleFunctions.Helpers.AllowWriteLog(OrderType)        [helper]
│   └── Event.Ext.sendEventImmediate(Logger — success)        [BE built-in]
├── [FAIL PATH — soft]
│   ├── RuleFunctions.Helpers.GetActivityStatusString("3",false) [helper]
│   ├── RuleFunctions.Helpers.GetOrderStatusString(3)         [helper]
│   ├── System.getGlobalVariableAsString × 5                  [BE built-in — error code segments]
│   ├── RuleFunctions.Helpers.SendDataToDB(orderRequest)      [helper]
│   ├── RuleFunctions.Helpers.AllowWriteLog(OrderType)        [helper]
│   └── Event.Ext.routeToImmediate(Logger — failure, ErrorLog) [BE built-in]
├── [FAIL PATH — hard delete]
│   ├── RuleFunctions.Helpers.GetOrderStatusString(8)         [helper]
│   ├── RuleFunctions.Helpers.SendDataToDB(orderRequest)      [helper]
│   ├── Instance.deleteInstance(orderRequest)                 [BE built-in]
│   └── RuleFunctions.Helpers.EngineManagement.SetOrderCount(-1) [helper]
├── RuleFunctions.Helpers.SkipActivity(req, act, "4")        [helper — PreExecCheck=false]
└── RuleFunctions.Helpers.HandleActivityException(...)       [helper]
```

---

## §16 — Concept Definitions Referenced

| Field | Type | Written by |
|-------|------|-----------|
| `orderRequest.BusinessValidationResult` | boolean | Reset to true in rule; set false by VRF DT on failure |
| `orderRequest.BusinessValidationMsg` | String | Reset to "" in rule; set by VRF DT on failure |
| `orderRequest.BusinessValidationCode` | String | Set by VRF DT — optional custom error suffix code |
| `orderRequest.ResponseCode` | String | Set on failure — composed error code |
| `orderRequest.ResponseMessage` | String | Set on failure — BusinessValidationMsg |
| `orderRequest.OrderStatus` | String | Set on failure: 3 (FAILED) or 8 (DELETED) |
| `orderRequest.DeleteOrderFromCache` | boolean | READ — determines hard vs soft failure path |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | Invoke order-type-specific business validation rules before provisioning activities begin |
| R2 | Support graceful pass (advance) and structured fail (error code + status update) outcomes |
| R3 | Support two failure modes: soft (order persisted as FAILED) and hard (order evicted from working memory) |
| R4 | Construct structured error response code from configurable GlobalVar segments |
| R5 | Allow per-order-type custom error suffix via BusinessValidationCode field |
| R6 | Log failure to dedicated ErrorLog channel with ERROR_CODE and ERROR_MSG fields |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Missing DT for order type causes runtime exception instead of clean validation failure | [MEDIUM] | Add startup validation that all active order types have a registered DT; or use `invokeAllVRFImpls` as fallback |
| Hard-delete path writes no audit log before evicting order | [MEDIUM] | Always write an audit log before hard delete, regardless of AllowWriteLog |
| AllowWriteLog gate on failure path — validation failures may not be logged for some order types | [MEDIUM] | Failure logging should bypass AllowWriteLog; use it only for success path |
| Failure log uses PROCESS_ID "_REQ" suffix — inconsistent with failure-as-response semantic | [LOW] | Change to "_RES" for consistency; update log correlation queries |
| Commented-out `invokeAllVRFImpls` and `processID` lines — stale code creates confusion | [LOW] | Remove commented code; document the design decision |
| Decision table names must exactly match `BusinessValidations_<OrderType>DT` — manual naming convention is error-prone | [LOW] | Enforce naming convention via CI validation or catalog check |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author mranade-T420
 */
rule Rules.OMConsumers.OMXOM.OMX_BusinessValidations {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "OMX_BIZ_VAL";
        orderRequest.ProcessFlow.NextActivityID == "OMX_BIZ_VAL";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        try {
            String chkXPath = orderCurrentActivity.PreExecCheck;
            String chkRes = "true";
            // Serialise full order for XPath PreExecCheck evaluation
            String sXML = Instance.serializeUsingDefaults(orderRequest);
            if(String.length(orderCurrentActivity.PreExecCheck) > 0)
                chkRes = XPath.execute("/("+chkXPath+")", sXML,
                    "ns0=www.tibco.com/be/ontology/Concepts/OrderRequest/OrderRequest");

            if(String.equals(chkRes, "true")) {
                // Reset validation state before invoking DT
                orderRequest.BusinessValidationResult = true;
                orderRequest.BusinessValidationMsg = "";

                // Extract process name from ProcessFlow extId (last ":" segment)
                String[] prcNm = String.split(orderRequest.ProcessFlow@extId, ":");
                Object[] args = {prcNm[(prcNm@length-1)], orderRequest};

                // Invoke order-type-specific decision table
                // [commented out] VRF.invokeAllVRFImpls("/DecisionTables/BusinessValidationsVRF", args);
                VRF.invokeVRFImplByName("/DecisionTables/BusinessValidationsVRF",
                    "BusinessValidations_"+orderRequest.OrderData.OrderType+"DT", args);

                if(!orderRequest.BusinessValidationResult) {
                    // === VALIDATION FAILED ===
                    orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("3", false);
                    orderRequest.OrderStatus = RuleFunctions.Helpers.GetOrderStatusString(3);
                    // Build structured error code from GlobalVars
                    String compNm = System.getGlobalVariableAsString("OMX_OM/ComponentName", "OM");
                    String svcCode = System.getGlobalVariableAsString("OMX_OM/Services/OMServices", "01");
                    String opCode = System.getGlobalVariableAsString("OMX_OM/Operations/SubmitOrder", "01");
                    String sev = System.getGlobalVariableAsString("OMX_COMMON/Severity/High", "03");
                    String errCode = System.getGlobalVariableAsString("OMX_OM/ResponseCodes/BusinessValidationsFailed", "004");
                    if(String.length(orderRequest.BusinessValidationCode) > 0)
                        errCode = "-"+orderRequest.BusinessValidationCode;
                    String respCode = compNm+svcCode+opCode+sev+errCode;
                    orderRequest.ResponseCode = respCode;
                    orderRequest.ResponseMessage = orderRequest.BusinessValidationMsg;
                    orderCurrentActivity.ResponseCode = respCode;
                    orderCurrentActivity.ResponseMessage = orderRequest.BusinessValidationMsg;

                    if(orderRequest.DeleteOrderFromCache) {
                        // HARD DELETE — evict from working memory
                        orderRequest.OrderStatus = RuleFunctions.Helpers.GetOrderStatusString(8);
                        RuleFunctions.Helpers.SendDataToDB(orderRequest);
                        Instance.deleteInstance(orderRequest);
                        RuleFunctions.Helpers.EngineManagement.SetOrderCount(-1);
                    } else {
                        // SOFT FAIL — persist as FAILED
                        RuleFunctions.Helpers.SendDataToDB(orderRequest);
                        if(RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                            long pid = System.nanoTime();
                            Event.Ext.routeToImmediate(
                                Event.createEvent(/* Logger event — §10: PROCESS_ID "_REQ", ERROR_CODE=respCode, ERROR_MSG=BusinessValidationMsg */),
                                "/Channels/LogConnection/ErrorLog", "");
                        }
                    }
                } else {
                    // === VALIDATION PASSED ===
                    RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity);
                    if(RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                        long pid = System.nanoTime();
                        Event.Ext.sendEventImmediate(
                            Event.createEvent(/* Logger event — §10: PROCESS_ID "_RES", AUDIT_TRACE="OMX-OM business validations passed." */));
                    }
                }
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch(Exception ae) {
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 — Response Message Rule (Not Applicable)

This is an internal synchronous OMXOM rule. There is no corresponding response rulefunction — process flow advancement is handled directly via `NextActivity` within the rule itself.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
