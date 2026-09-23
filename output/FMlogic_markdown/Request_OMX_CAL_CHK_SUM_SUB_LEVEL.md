# Request_OMX_CAL_CHK_SUM_SUB_LEVEL

> Internal computation rule — no external backend call. Computes the Luhn check digit for each eSIM subscriber's ICC_ID and stores the result as `ICC_ID_CHG_SUM` ExtendedInfo, preparing the ICCID for SM-DP+ operations.

**Backend:** Internal (OMX) | **Pattern:** Per-Subscriber Computation | **Priority:** 5 | **ForwardChain:** true

---

## §1 — Overview & Purpose

An **internal computation rule** — no outbound JMS event. For each eSIM subscriber (SIM_TYPE="B"):
1. Extracts `ICC_ID` from `subscriber.ExtendedInfo[Name="ICC_ID"]/Value`
2. Computes Luhn check digit via `RuleFunctions.Helpers.Luhn(iccId)`
3. Creates `ICC_ID_CHG_SUM` ExtendedInfo with value = `iccId + luhnDigit`
4. Appends to `subscriber.ExtendedInfo`

Rule is in `OMXOM/` folder (internal orchestration), not the standard `OMXFM/Request/` folder.

> **[MEDIUM] Dead code:** `paramValue` (PROJ) is read via `GetActivityParamValueFromKey` but never used. Remove in migration.

> **[LOW] Misleading AUDIT_TRACE:** "Request Sent for OMX_CAL_CHK_SUM_SUB_LEVEL" — no external request is sent.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXOM.OMX_CAL_CHK_SUM_SUB_LEVEL` |
| Priority | 5 |
| ForwardChain | true |
| Rule File | `OMXOM/OMX_CAL_CHK_SUM_SUB_LEVEL.rule` |
| Response Rulefunction | None — no external call |
| Backend System | Internal OMX (in-memory) |
| Dispatch Pattern | Per-subscriber loop (POU + COU), computation only |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Subscribers read and written |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity state |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "OMX_CAL_CHK_SUM_SUB_LEVEL"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_CHK_SUM_SUB_LEVEL"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow Diagram

1. If `isActResub` → `PurgePendingRequestsBeforeResubmit`
2. Read PROJ parameter (dead code — value unused)
3. Loop POU subscribers: evaluate PreExecCheck (SIM_TYPE="B"), extract ICC_ID, compute Luhn
4. Create ICC_ID_CHG_SUM concept, append to subscriber.ExtendedInfo, emit audit
5. Repeat for COU subscribers
6. If any checksum created → `NextActivity()`; else `SkipActivity("4")`

---

## §6 — Rule Action (THEN)

### §6.1 PreExecCheck Per Subscriber

```xpath
count(//Subscriber/ResourceInfo[ResourceName='SIM_TYPE' and ValuesArray="B"]) > 0
```

Evaluated via `GetXMLForSubscriber` (POU) / `GetXMLForSubscriberInChildOU` (COU).

### §6.2 Luhn Checksum Computation

| Step | Detail |
|------|--------|
| Read | `XPath.evalAsString("$subscriber/ExtendedInfo[Name=\"ICC_ID\"]/Value")` |
| Guard | `String.length(iccId) > 0` |
| Compute | `iccIdCheckSum = RuleFunctions.Helpers.Luhn(iccId)` |
| Result | `iccIdChgSum.Value = iccId + iccIdCheckSum` |

### §6.3 ICC_ID_CHG_SUM Concept

| Field | Value |
|-------|-------|
| Type | `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` |
| extId | `concat(iccId, ":ICC_ID_CHG_SUM", subscriber/@extId)` |
| Name | "ICC_ID_CHG_SUM" (static) |
| Value | `iccId + iccIdCheckSum` (set after creation) |

### §6.4 Completion

| Condition | Action |
|-----------|--------|
| At least one checksum computed | `NextActivity(orderRequest, orderCurrentActivity)` |
| No ICC_ID found | `SkipActivity("4")` |

**Note:** No `RequestCount++`, no `Status="1"`, no `SendDataToDB` — uses `NextActivity()` directly.

---

## §8 — System & Integration Dependencies

### §8.4 BE Working Memory

| Concept | R/W | Fields |
|---------|-----|--------|
| Subscriber | R/W | `ExtendedInfo[ICC_ID]` (read), `ExtendedInfo[ICC_ID_CHG_SUM]` (written) |
| `orderCurrentActivity` | Read | PreExecCheck, ActivityParameters |

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| Guard | None — logs whenever ICC_ID found |
| PROCESS_ID | `concat(pid, "_REQ")` |
| OPERATION_NAME | "OMX_CAL_CHK_SUM_SUB_LEVEL" |
| AUDIT_TRACE | "Request Sent for OMX_CAL_CHK_SUM_SUB_LEVEL" [LOW: misleading] |
| Payload | `<ns:ServicePayload/>` empty element |

---

## §15 — Function Dependency Tree

```text
OMX_CAL_CHK_SUM_SUB_LEVEL.rule
├── [if isActResub] PurgePendingRequestsBeforeResubmit(activity)
├── GetActivityParamValueFromKey(activity, "PROJ")   [dead code]
├── [POU loop]
│   ├── GetXMLForSubscriber(orderRequest, subRefId)
│   ├── XPath.execute(chkXPath, sXML, ns)
│   ├── XPath.evalAsString(ICC_ID extract)
│   ├── Helpers.Luhn(iccId)
│   ├── Instance.createInstance(ICC_ID_CHG_SUM concept)
│   └── Event.Ext.sendEventImmediate(Logger audit)
├── [COU loop — identical, uses GetXMLForSubscriberInChildOU]
├── NextActivity(orderRequest, orderCurrentActivity)
├── SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
```

---

## §17 — Migration Notes & Recommendations

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Dead code: paramValue (PROJ) never used | [MEDIUM] | Remove `GetActivityParamValueFromKey` call |
| Misleading AUDIT_TRACE "Request Sent" | [LOW] | Update to reflect internal computation |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXOM.OMX_CAL_CHK_SUM_SUB_LEVEL {
  attribute { priority = 5; forwardChain = true; }
  then {
    boolean isActResub = (...);
    try {
      if (isActResub) PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      String paramValue = GetActivityParamValueFromKey(orderCurrentActivity, "PROJ"); // DEAD CODE
      boolean isSkipped = true;
      // POU + COU subscriber loops
      for (int i=0; i<pOuLen; i++) {
        for (int iSub=0; iSub<subLen; iSub++) {
          // PreExecCheck per subscriber
          if (chkRes == "true") {
            String iccId = XPath.evalAsString("$subscriber/ExtendedInfo[Name=\"ICC_ID\"]/Value");
            if (String.length(iccId) > 0) {
              String iccIdCheckSum = RuleFunctions.Helpers.Luhn(iccId);
              SubscriberExtendedInfo iccIdChgSum = Instance.createInstance("xslt://...");
              /* XSLT: extId=concat(iccId,":ICC_ID_CHG_SUM",subscriber/@extId), Name="ICC_ID_CHG_SUM" */
              iccIdChgSum.Value = iccId + iccIdCheckSum;
              subscriber.ExtendedInfo[subscriber.ExtendedInfo@length] = iccIdChgSum;
              Event.Ext.sendEventImmediate(logEvent);
              isSkipped = false;
            }
          }
        }
      }
      if (!isSkipped) { NextActivity(orderRequest, orderCurrentActivity); }
      else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
    } catch (Exception ae) { HandleActivityException(...); }
  }
}
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
