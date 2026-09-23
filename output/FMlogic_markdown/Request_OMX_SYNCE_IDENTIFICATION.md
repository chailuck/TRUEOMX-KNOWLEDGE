# Request_OMX_SYNCE_IDENTIFICATION

## §1 Overview & Purpose

A local computation rule with **no outbound ESB/JMS call**. Performs two tasks:

1. **Identification sync**: Copies `CustomerGeneralInfo.Identification` and `CustomerGeneralInfo.IdentificationType` into `CustomerName.Identification` / `CustomerName.IdentificationType` (when both objects exist).
2. **Change-detection flag**: Creates a `CustomerExtendedInfo` with `Name="CHANGE_IDENTIFICATION"`. Sets value to `"Y"` if the customer's current Identification differs from `ExtendedInfo[OLD_IDENTIFICATION]`; otherwise value stays `"N"`.

The `CHANGE_IDENTIFICATION=Y` flag gates both downstream MCS steps: **MCS_GET_PACKCODE** and **MCS_CANCEL_AFTER_SALE**.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_SYNCE_IDENTIFICATION` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | OMX_SYNCE_IDENTIFICATION |
| Backend | OMX Internal — no outbound call |
| Pattern | Local Computation (no IntraActivitySequencing) |
| Author | usuf |
| Response Rulefunction | None — rule calls NextActivity directly |

---

## §3 Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity state |

---

## §4 Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "OMX_SYNCE_IDENTIFICATION"
orderRequest.ProcessFlow.NextActivityID == "OMX_SYNCE_IDENTIFICATION"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 Execution Flow

1. **Identification sync** (if CustomerGeneralInfo != null AND CustomerName != null):
   - Copy `CustomerGeneralInfo.Identification` → `CustomerName.Identification`
   - Copy `CustomerGeneralInfo.IdentificationType` → `CustomerName.IdentificationType`
2. Create `CustomerExtendedInfo` with Name="CHANGE_IDENTIFICATION", Value="N" (default)
3. Read `OLD_IDENTIFICATION` from `Customer.ExtendedInfo` via XPath
4. **Change-detection**: If CustomerGeneralInfo.Identification is not blank AND differs from OLD_IDENTIFICATION → set Value="Y"
5. Append cusExtInf to Customer.ExtendedInfo
6. Call `NextActivity`
7. Fire audit log event

---

## §8 System & Integration Dependencies

### §8.1 No Outbound Backend Call

Purely in-memory operations on the order request concept.

### §8.5 ExtendedInfo Fields

| Key | Level | Direction | Purpose |
|-----|-------|-----------|---------|
| OLD_IDENTIFICATION | Customer | Input (read) | Previous identification number for comparison |
| CHANGE_IDENTIFICATION | Customer | Output (written) | "Y" if ID changed, "N" otherwise; gates MCS steps |

### §8.4 BE Working Memory Fields

| Field Path | Direction | Notes |
|-----------|-----------|-------|
| `Customer.CustomerGeneralInfo.Identification` | Read | New identification number |
| `Customer.CustomerGeneralInfo.IdentificationType` | Read | Identification type code |
| `Customer.CustomerName.Identification` | Written | Synced from CustomerGeneralInfo |
| `Customer.CustomerName.IdentificationType` | Written | Synced from CustomerGeneralInfo |
| `Customer.ExtendedInfo[CHANGE_IDENTIFICATION]` | Written (appended) | Change-detection flag |

---

## §10 XSLT Field Mapping Tree

```text
createObject
└── object
    ├── @extId  ← OMXUtils:generateTrackingID()           [Always]
    ├── Name    ← 'CHANGE_IDENTIFICATION'                  [Always]
    └── Value   ← 'N'                                      [Default]
                ← 'Y'                                      [Conditional: Identification changed vs OLD_IDENTIFICATION]
```

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` [Conditional] |
| PROCESS_ID | `concat($pid, "_RES")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | "/Rules/OMConsumers/OMXOM/OMX_SYNCE_IDENTIFICATION" |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | "OMX_SYNCE_IDENTIFICATION Completed." |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | empty element (always included) |

> Note: PROCESS_ID uses `_RES` suffix (not `_REQ`) — rule advances inline, no async cycle.

---

## §12 Activity Status Management

| Outcome | Call |
|---------|------|
| Always | `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` |

No SkipActivity — rule always advances.

---

## §13 Exception Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 Helper Functions

| Function | Purpose |
|----------|---------|
| `RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(value)` | Returns true if value is null/empty/blank |
| `RuleFunctions.Helpers.NextActivity(req, activity)` | Advance process flow |
| `RuleFunctions.Helpers.HandleActivityException(req, activity, ae, "")` | Standard error handler |

---

## §15 Function Dependency Tree

```text
Request_OMX_SYNCE_IDENTIFICATION
├── (field copy: CustomerGeneralInfo → CustomerName)    [if both non-null]
├── Instance.createInstance(CustomerExtendedInfo XSLT)
├── XPath.evalAsString(OLD_IDENTIFICATION)
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(Identification)
├── (Value = "Y")                                       [if Identification changed]
├── (append cusExtInf to Customer.ExtendedInfo)
├── RuleFunctions.Helpers.NextActivity(req, activity)
├── Event.Ext.sendEventImmediate(Logger)
└── RuleFunctions.Helpers.HandleActivityException(req, activity, ae, "")
```

---

## §17 Migration Notes

| # | Requirement / Risk | Severity |
|---|-------------------|---------|
| R1 | CHANGE_IDENTIFICATION gates MCS_GET_PACKCODE and MCS_CANCEL_AFTER_SALE — sequencing dependency must be preserved | [HIGH] |
| R2 | OLD_IDENTIFICATION must be populated in Customer.ExtendedInfo before this step runs | [MEDIUM] |
| R3 | Identification sync writes to CustomerName — target platform must support both CustomerName and CustomerGeneralInfo paths | [MEDIUM] |
| R4 | IsBlankOrStringNull used for null-safe comparison — verify equivalent in target platform | [LOW] |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
