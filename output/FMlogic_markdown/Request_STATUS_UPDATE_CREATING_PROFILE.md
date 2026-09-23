# Request_STATUS_UPDATE_CREATING_PROFILE

> TIBCO BusinessEvents FM Logic Documentation — Internal OMX Status Bookmark (OMXOM)

**Author:** suppaad c. | **Priority:** 5 | **forwardChain:** true | **File:** `OMX_UpdateCreatingProfileStatus.rule`

---

## §1 — Overview & Purpose

> **Internal OMX Status Bookmark Rule (OMXOM) — No External Backend Call**
>
> This rule marks the transition of the order into the "creating profile" phase by updating `orderRequest.ProfileStatus` twice: once *before* advancing the flow (to signal the phase is starting) and once *after* (to signal the phase is active). It is a pure status-bookmarking step with no subscriber iteration and no backend communication.

The double-write pattern creates a bracket around the `NextActivity` call. Status code 2 signals "entering creating-profile phase", and status code 5 signals "creating-profile phase active".

| Item | Value |
|------|-------|
| Rule class | `Rules.OMConsumers.OMXOM.OMX_UpdateCreatingProfileStatus` |
| ActivityID | `STATUS_UPDATE_CREATING_PROFILE` |
| Author | suppaad c. |
| Backend call | None |
| ProfileStatus before NextActivity | `GetOrderStatusString(2)` |
| ProfileStatus after NextActivity | `GetOrderStatusString(5)` |
| Completion | `NextActivity` (synchronous) |
| Response rulefunction | None |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule type | `rule` | RETE stateful rule |
| priority | 5 | Standard priority |
| forwardChain | true | Re-evaluates if working memory changes |
| Namespace | OMXOM | Internal — no ESB/JMS call |
| Response rulefunction | None | Synchronous completion via NextActivity |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Root order — ProfileStatus written twice; serialised for PreExecCheck |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Current activity — PreExecCheck read from nextAct; Status advanced via NextActivity |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Meaning |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity matches current process step |
| 2 | `orderCurrentActivity.ActivityID == "STATUS_UPDATE_CREATING_PROFILE"` | This rule fires for the status-update step |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "STATUS_UPDATE_CREATING_PROFILE"` | Process flow confirms this step is next |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity has not yet been processed |

---

## §5 — Execution Flow Diagram

1. Serialise order + read `PreExecCheck` from `nextAct` via `Instance.getByExtIdByUri(NextActivityName, ...)`
2. If PreExecCheck fails → `SkipActivity("4")`
3. **ProfileStatus = GetOrderStatusString(2)** — entering creating-profile phase
4. **NextActivity(orderRequest, orderCurrentActivity)** — advance process flow
5. **ProfileStatus = GetOrderStatusString(5)** — creating-profile phase active
6. `AllowWriteLog` gate → emit audit log with `AUDIT_TRACE="STATUS_UPDATE_CREATING_PROFILE completed."`, `PROCESS_ID = pid + "_RES"`

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### §6.1 Double ProfileStatus Update — The Bracket Pattern

> **Design note:** This rule uses a bracket pattern. ProfileStatus is set to code 2 immediately before `NextActivity` and to code 5 immediately after. In a RETE engine with `forwardChain=true`, the intermediate value (code 2) is observable to other rules that react to `ProfileStatus` changes. This allows a brief monitoring window to detect that the order is transitioning into the provisioning phase.

| Sequence | Action | ProfileStatus value |
|----------|--------|---------------------|
| 1 | `orderRequest.ProfileStatus = GetOrderStatusString(2)` | Code 2 — "Entering creating-profile" |
| 2 | `NextActivity(orderRequest, orderCurrentActivity)` | Unchanged (still code 2) |
| 3 | `orderRequest.ProfileStatus = GetOrderStatusString(5)` | Code 5 — "Creating-profile active" |

### §6.2 Audit Log Event Fields

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| PROCESS_ID | `concat(pid, "_RES")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `"/Rules/OMConsumers/OMXOM/STATUS_UPDATE_CREATING_PROFILE"` |
| LOG_LEVEL | `$globalVariables/OMX_COMMON/.../MSG_LOG_LEVEL/INFO` |
| AUDIT_TRACE | `"STATUS_UPDATE_CREATING_PROFILE completed."` |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | `ns1:ServicePayload / xsl:copy-of $orderRequest` — always |

---

## §7–9 — Data Extraction / Payload Build

No data extraction or outbound payload. The only output is two writes to `orderRequest.ProfileStatus` and one optional audit log event carrying the full `orderRequest`.

---

## §10 — XSLT Field Mapping — Audit Log Output Tree

```text
createEvent
└── event
    ├── ESBUUID              ← $orderRequest/OrderData/OMXTrackingId              [Conditional]
    ├── PROCESS_ID           ← concat($pid, "_RES")                               [Always]
    ├── COMPONENT_NAME       ← $globalVariables/OMX_COMMON/Component_Name/OMX_CEP [Always]
    ├── OPERATION_NAME       ← "/Rules/OMConsumers/OMXOM/STATUS_UPDATE_CREATING_PROFILE" [Always]
    ├── LOG_LEVEL            ← $globalVariables/OMX_COMMON/.../MSG_LOG_LEVEL/INFO [Always]
    ├── AUDIT_TRACE          ← "STATUS_UPDATE_CREATING_PROFILE completed."        [Always]
    ├── AUDIT_TS             ← tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS',    [Always]
    │                           current-dateTime())
    └── payload                                                                    [Always]
        └── ns1:ServicePayload ← xsl:copy-of $orderRequest
```

> **Legend:** `[Always]` = always emitted | `[Conditional]` = inside `xsl:if`

---

## §11 — Audit Logging

| When | PROCESS_ID | AUDIT_TRACE | Gated? |
|------|-----------|-------------|--------|
| After NextActivity and ProfileStatus=5 | `pid + "_RES"` | "STATUS_UPDATE_CREATING_PROFILE completed." | Yes — `AllowWriteLog` |

The audit log is emitted *after* both ProfileStatus writes and NextActivity — it captures the final state. The payload is always the full `orderRequest` (no WritePayload gate).

---

## §12 — Activity Status Management

| Outcome | Mechanism | Effect |
|---------|-----------|--------|
| PreExecCheck false | `SkipActivity("4")` | Activity SKIPPED; ProfileStatus not changed |
| Normal execution | `NextActivity(orderRequest, orderCurrentActivity)` | Activity COMPLETED; ProfileStatus transitions 2→5 |
| Exception | `HandleActivityException` | Activity FAILED; ProfileStatus may be stuck at code 2 |

> **[LOW]** If an exception occurs after `ProfileStatus = GetOrderStatusString(2)` but before `NextActivity` (or before the second assignment), `ProfileStatus` remains at code 2. This intermediate status may be visible to monitoring/reporting systems.

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|----------|--------|---------|
| `Instance.getByExtIdByUri(extId, uri)` | Concept | Fetches nextAct for PreExecCheck read |
| `Instance.serializeUsingDefaults(orderRequest)` | String (XML) | Full order XML for PreExecCheck evaluation |
| `XPath.execute(chkXPath, sXML, ns)` | String | PreExecCheck evaluation |
| `RuleFunctions.Helpers.GetOrderStatusString(2)` | String | Maps code 2 to ProfileStatus string |
| `RuleFunctions.Helpers.NextActivity(req, act)` | void | Advances process flow |
| `RuleFunctions.Helpers.GetOrderStatusString(5)` | String | Maps code 5 to ProfileStatus string |
| `RuleFunctions.Helpers.AllowWriteLog(orderType)` | boolean | Gates audit log by order type |
| `RuleFunctions.Helpers.SkipActivity(req, act, "4")` | void | Skips activity if PreExecCheck false |
| `RuleFunctions.Helpers.HandleActivityException(req, act, ae, "")` | void | Generic exception handler |

---

## §15 — Function Dependency Tree

```text
OMX_UpdateCreatingProfileStatus / STATUS_UPDATE_CREATING_PROFILE (rule)
├── Instance.getByExtIdByUri(NextActivityName, "/Concepts/...")       [BE built-in]
├── Instance.serializeUsingDefaults(orderRequest)                     [BE built-in]
├── XPath.execute(PreExecCheck, sXML)                                 [BE built-in]
├── [IF chkRes == "true"]
│   ├── RuleFunctions.Helpers.GetOrderStatusString(2)                [helper → ProfileStatus = code 2]
│   ├── RuleFunctions.Helpers.NextActivity(req, act)                 [helper]
│   ├── RuleFunctions.Helpers.GetOrderStatusString(5)                [helper → ProfileStatus = code 5]
│   ├── RuleFunctions.Helpers.AllowWriteLog(OrderType)               [helper — log gate]
│   └── Event.Ext.sendEventImmediate(Logger — audit)                  [BE built-in]
├── [ELSE]
│   └── RuleFunctions.Helpers.SkipActivity(req, act, "4")           [helper]
└── RuleFunctions.Helpers.HandleActivityException(...)               [helper — catch]
```

---

## §16 — Concept Definitions Referenced

| Field | Type | Written / Read |
|-------|------|----------------|
| `orderRequest.ProfileStatus` | String | Written twice: GetOrderStatusString(2) then GetOrderStatusString(5) |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Mark the order's ProfileStatus as "entering creating-profile phase" (code 2) before advancing the flow |
| R2 | Advance the process flow via NextActivity |
| R3 | Mark the order's ProfileStatus as "creating-profile active" (code 5) after advancing |
| R4 | Emit a completion audit log after both status updates |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Exception after ProfileStatus=2 but before ProfileStatus=5 leaves order stuck at code 2 | [MEDIUM] | Move ProfileStatus=2 write after a non-failing operation; or add ProfileStatus cleanup to exception handler |
| Payload in audit log is always full orderRequest (no WritePayload gate) — large log entries | [LOW] | Add WritePayload gate consistent with other rules |
| OPERATION_NAME uses ActivityID suffix (`STATUS_UPDATE_CREATING_PROFILE`), not rule class name — inconsistent with some OMXOM rules | [LOW] | Standardise on one convention |
| ProfileStatus semantics for codes 2 and 5 are not documented in the rule | [LOW] | Document in `GetOrderStatusString` helper or in a shared constant definition |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author suppaad c.
 */
rule Rules.OMConsumers.OMXOM.OMX_UpdateCreatingProfileStatus {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "STATUS_UPDATE_CREATING_PROFILE";
        orderRequest.ProcessFlow.NextActivityID == "STATUS_UPDATE_CREATING_PROFILE";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        // [commented out] System.debugOut("["+OMXTrackingId+"] Executing OMX_UpdateCreatingProfileStatus")
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
                orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
            String chkXPath = nextAct.PreExecCheck;
            String chkRes = "true";
            String sXML = Instance.serializeUsingDefaults(orderRequest);

            if(String.length(nextAct.PreExecCheck) > 0)
                chkRes = XPath.execute("/("+chkXPath+")", sXML,
                    "ns0=www.tibco.com/be/ontology/Concepts/OrderRequest/OrderRequest");

            if(String.equals(chkRes, "true")) {
                // Bracket pattern: status 2 → NextActivity → status 5
                orderRequest.ProfileStatus = RuleFunctions.Helpers.GetOrderStatusString(2);
                RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity);
                orderRequest.ProfileStatus = RuleFunctions.Helpers.GetOrderStatusString(5);

                if(RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                    long pid = System.nanoTime();
                    Event.Ext.sendEventImmediate(Event.createEvent(
                        /* Logger event: PROCESS_ID=pid+"_RES",
                           AUDIT_TRACE="STATUS_UPDATE_CREATING_PROFILE completed.",
                           payload=full orderRequest — see §10 */));
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

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
