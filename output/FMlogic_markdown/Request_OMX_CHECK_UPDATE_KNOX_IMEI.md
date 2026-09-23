# Request_OMX_CHECK_UPDATE_KNOX_IMEI

> OMXOM Internal Enrichment Rule — Knox IMEI Update Flag Injection

**Rule type:** OMXOM | **Priority:** 5 | **ForwardChain:** true | **Backend:** None (in-memory) | **Response RF:** N/A

---

## §1 — Overview & Purpose

> **Internal Enrichment Rule** — This rule does NOT dispatch an outbound event to any backend system. It is a pure working-memory enrichment that injects a flag (`UPDATE_KNOX_IMEI=Y`) into qualifying subscribers, enabling downstream Knox-related FMs to gate on that flag.

**Business Function:** Determines whether any subscriber in the order requires a Knox IMEI update by evaluating the ProcessConfig PreExecCheck XPath per individual subscriber. Any subscriber that passes the check receives `ExtendedInfo[Name=UPDATE_KNOX_IMEI, Value=Y]` appended to their working-memory concept. Downstream steps 19–20 in POSTPAID_UPDATE_PARAMETER read this flag to decide whether to send Knox completion events and update Knox device status.

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXOM.OMX_CHECK_UPDATE_KNOX_IMEI` |
| Rule category | OMXOM (OMX Order Management internal logic) |
| Backend system | None — pure TIBCO BE working-memory operation |
| Integration protocol | None |
| Output | `SubscriberExtendedInfo(UPDATE_KNOX_IMEI=Y)` appended to subscriber |
| Consumed by | Steps 19 (OMX_NOTI_TO_KAFKA / knoxEvent=COMPLETED_OLD_IMEI) and 20 (PSA_UPDATE_KNOX_STATUS / KNOX_STATUS=COMPLETE) |

---

## §2 — Rule Metadata & Attributes

| Property | Value |
|----------|-------|
| Namespace | `Rules.OMConsumers.OMXOM` |
| Rule file | `OMX_CHECK_UPDATE_KNOX_IMEI.rule` |
| Priority | 5 |
| forwardChain | true |
| Rule type | OMXOM Enrichment |
| Outbound event | None (only audit logger event) |
| Response rulefunction | None (synchronous — no async backend call) |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order request — all ParentOU/ChildOU/Subscriber data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current ProcessConfig activity (OMX_CHECK_UPDATE_KNOX_IMEI) |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Binds the correct activity instance to this order |
| 2 | `orderCurrentActivity.ActivityID == "OMX_CHECK_UPDATE_KNOX_IMEI"` | Restricts to this specific FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_CHECK_UPDATE_KNOX_IMEI"` | Confirms process flow is pointing to this step |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Prevents re-processing a completed or errored activity |

---

## §5 — Execution Flow Diagram

1. Check resubmit flag: `isActResub = (RequestCount > 0 && IsOrderResubmitted)` *(captured, unused)*
2. Read PreExecCheck XPath from `orderCurrentActivity.PreExecCheck`
3. **Outer loop:** iterate all ParentOU (index `p`)
4. → **Inner loop:** iterate all ParentOU Subscribers (index `ps`)
5. → → If PreExecCheck non-empty → call `GetXMLForSubscriber(orderRequest, sub.RefId)`
6. → → Evaluate PreExecCheck XPath against subscriber XML
7. → → If result == "true" → create `SubscriberExtendedInfo(UPDATE_KNOX_IMEI=Y)` → append to `sub.ExtendedInfo[]` → set `isSkipped=false`
8. **ChildOU loop:** same logic repeated for all ChildOU Subscribers
9. If `!isSkipped` → `NextActivity()` → fire audit log event
10. Else → `SkipActivity(..., "4")`
11. On exception → `HandleActivityException()`

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

> **No outbound backend call.** The THEN block is fully synchronous — it modifies in-memory concept instances and advances the process flow immediately.

**Resubmit flag:** `boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted)` — captured but not used in any conditional branch (dead code / informational).

**Per-subscriber PreExecCheck evaluation:**
- Loads subscriber XML via `RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, sub.RefId)`
- Evaluates PreExecCheck via `XPath.execute("/(" + chkXPath + ")", sXML, ns)`
- If `chkRes == "true"`: injects `UPDATE_KNOX_IMEI=Y` ExtendedInfo; sets `isSkipped = false`

**Flow control:**

| Condition | Action |
|-----------|--------|
| At least one subscriber matched | `NextActivity(orderRequest, orderCurrentActivity)` → advance process |
| No subscriber matched | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception thrown | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §7 — Per-Subscriber PreExecCheck Evaluation

The rule evaluates the `PreExecCheck` XPath from the ProcessConfig **per individual subscriber** (not once for the whole order). This allows selective enrichment — only subscribers that match receive the `UPDATE_KNOX_IMEI=Y` flag.

**ProcessConfig PreExecCheck (step 6):**

```xpath
boolean(//Subscriber/SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and Value='FE'] and ExtendedInfo[Name='IMEI_KNOX' and Value!='']])
```

**Namespace binding:** `ns0=www.tibco.com/be/ontology/Concepts/OrderRequest/OrderRequest`

> **Note:** The XPath is wrapped as `/( <chkXPath> )` before evaluation — the outer parentheses allow the expression to be a predicate rather than requiring it to be a path expression.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Applies to: **POSTPAID_UPDATE_PARAMETER**. Triggered when an FE subscriber has a non-empty `IMEI_KNOX` value (Knox-enrolled device).

### §8.2 — ESB / JMS Channel Dependencies

No outbound ESB/JMS channel. Only the internal audit logger event is fired (see §11).

### §8.4 — BE Working Memory Dependencies

| Concept field | Direction | Purpose |
|---------------|-----------|---------|
| `orderRequest.OrderData.Customer.ParentOU[].Subscriber[]` | READ | Source subscriber list |
| `orderCurrentActivity.PreExecCheck` | READ | XPath to evaluate per subscriber |
| `orderCurrentActivity.RequestCount` | READ | Resubmit detection |
| `orderRequest.IsOrderResubmitted` | READ | Resubmit flag |
| `sub.ExtendedInfo[sub.ExtendedInfo@length]` | WRITE | Appends `UPDATE_KNOX_IMEI=Y` |
| `orderRequest.ProcessFlow.NextActivityName` | WRITE (via NextActivity) | Advances process flow |

### §8.5 — ExtendedInfo Fields

| Name | Value | Written by | Consumed by |
|------|-------|-----------|-------------|
| `UPDATE_KNOX_IMEI` | `Y` | This rule | Steps 19 (OMX_NOTI_TO_KAFKA) and 20 (PSA_UPDATE_KNOX_STATUS) PreExecCheck gates |
| `IMEI_KNOX` | non-empty, non-"NONE" | Upstream | PSA_GET_DEVICE_INFO, KNOX_SAVE_DEVICE |
| `FE_OR_CCBS` | `FE` | Upstream | Many FMs across the process |

### §8.6 — Global Variable Dependencies

| Path | Used in |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit logger COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit logger LOG_LEVEL |

---

## §9 — Detailed Concept Build (Instance.createInstance)

### §9.1 — Concept Type

`Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo`
Extends: `/Concepts/OrderRequest/OrderElements/ExtendedInfo`
Fields: `Name` (string), `Value` (string)

### §9.2 — extId Generation

`OMXUtils:generateTrackingID()` — inline call in XSLT (Pattern C). Each instance gets a unique tracking ID.

### §9.3 — Field Mapping

| Field | Value | Type |
|-------|-------|------|
| `@extId` | `OMXUtils:generateTrackingID()` | Generated |
| `Name` | `"UPDATE_KNOX_IMEI"` | Always · Static |
| `Value` | `"Y"` | Always · Static |

### §9.4 — Generated XML Example

```xml
<createObject>
  <object extId="TID-20260820-143012-0001">
    <Name>UPDATE_KNOX_IMEI</Name>
    <Value>Y</Value>
  </object>
</createObject>
```

### §9.5 — XSLT Source (Instance.createInstance)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet
    xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    version="1.0"
    exclude-result-prefixes="OMXUtils xsl xsd">
  <xsl:output method="xml"/>
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <Name>
          <xsl:value-of select="&quot;UPDATE_KNOX_IMEI&quot;"/>
        </Name>
        <Value>
          <xsl:value-of select="&quot;Y&quot;"/>
        </Value>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — Concept Field Mapping — Output Object Tree Hierarchy

```text
createObject
└── object
    ├── @extId    ← OMXUtils:generateTrackingID()     [Always · Generated]
    ├── Name      ← "UPDATE_KNOX_IMEI"                [Always · Static]
    └── Value     ← "Y"                               [Always · Static]
```

---

## §11 — Audit Logging

Logger event fired via `Event.Ext.sendEventImmediate` after `NextActivity()` (success path only):

| Logger Field | Value |
|-------------|-------|
| `ESBUUID` | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| `PROCESS_ID` | `concat($pid, "_RES")` — nano-time suffix |
| `COMPONENT_NAME` | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| `OPERATION_NAME` | `"CHECK_UPDATE_KNOX_IMEI"` (static) |
| `LOG_LEVEL` | `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` |
| `AUDIT_TRACE` | `"CHECK_UPDATE_KNOX_IMEI Completed."` (static) |
| `AUDIT_TS` | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| `payload` | Empty `<payload/>` — no payload logged |

> **Note:** Logger fires only when at least one subscriber was enriched. No logger fires on the skip path.

---

## §12 — Activity Status Management

| Scenario | Call | Result |
|----------|------|--------|
| At least one subscriber matched | `NextActivity(orderRequest, orderCurrentActivity)` | COMPLETED; process advances |
| No subscriber matched | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | SKIPPED (code "4") |
| Exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | ERROR; order halted |

---

## §13 — Exception / Error Handling

Single `try/catch(Exception ae)` block wraps the entire THEN body. On exception: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`. Empty string fourth parameter = no additional context message.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)` | Serialises subscriber working-memory to XML for XPath evaluation |
| `RuleFunctions.Helpers.NextActivity(orderRequest, activity)` | Marks COMPLETED and advances ProcessFlow.NextActivityName |
| `RuleFunctions.Helpers.SkipActivity(orderRequest, activity, code)` | Marks SKIPPED with reason code "4" |
| `RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Records error and halts order processing |

---

## §15 — Function Dependency Tree

```text
OMX_CHECK_UPDATE_KNOX_IMEI (THEN block)
├── XPath.execute(chkXPath, sXML, ns)                     [built-in BE]
├── RuleFunctions.Helpers.GetXMLForSubscriber()            [helper]
├── Instance.createInstance("xslt://...")                  [built-in BE]
│   └── XSLT → SubscriberExtendedInfo(UPDATE_KNOX_IMEI=Y)
├── RuleFunctions.Helpers.NextActivity()                   [helper, on match]
│   └── Event.Ext.sendEventImmediate(Logger event)
├── RuleFunctions.Helpers.SkipActivity("4")               [helper, on no match]
└── RuleFunctions.Helpers.HandleActivityException()        [helper, on error]
```

---

## §16 — Concept Definitions Referenced

| Concept | Path | Key Fields |
|---------|------|-----------|
| OrderRequest | `Concepts.OrderRequest.OrderRequest` | OrderData, ProcessFlow, IsOrderResubmitted |
| Activity | `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, PreExecCheck, RequestCount |
| SubscriberExtendedInfo | `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` | Extends ExtendedInfo: Name, Value |
| Subscriber | `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, ExtendedInfo[], SubscriberOffers[] |

---

## §17 — Migration Notes & Recommendations

**Functional Requirements:**

| ID | Requirement |
|----|-------------|
| R1 | Evaluate PreExecCheck XPath per individual subscriber (not once per order) |
| R2 | Inject `UPDATE_KNOX_IMEI=Y` on all qualifying subscribers before advancing |
| R3 | Skip (not fail) the step when no subscriber matches |
| R4 | Downstream steps 19 and 20 must read `UPDATE_KNOX_IMEI=Y` as their gate |

**Design Risks:**

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Implicit coupling: steps 19–20 gate on `UPDATE_KNOX_IMEI=Y` written here; removing/skipping this step breaks Knox completion flow | [MEDIUM] | Document dependency chain; add integration test for full Knox IMEI update flow |
| `isActResub` flag computed but never used — dead code, possible incomplete resubmit guard | [LOW] | Evaluate whether resubmit should re-inject flag or skip; clean up in migration |
| Logger fires only on success path — skip path produces no audit trail | [LOW] | Add skip-path log entry for observability |
| In microservices migration: per-subscriber loop must be preserved; single-flag-per-order approach would miss ChildOU subscribers | [MEDIUM] | Preserve per-subscriber granularity in replacement service |

---

## §18 — Full Source Code

```java
/**
 * @description
 */
rule Rules.OMConsumers.OMXOM.OMX_CHECK_UPDATE_KNOX_IMEI {
    attribute {
        priority = 5;
        forwardChain = true;
    }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "OMX_CHECK_UPDATE_KNOX_IMEI";
        orderRequest.ProcessFlow.NextActivityID == "OMX_CHECK_UPDATE_KNOX_IMEI";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub=(orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);

        try {
            boolean isSkipped = true;
            String chkXPath = orderCurrentActivity.PreExecCheck;

            /*** Begin ParentOU ***/
            int pouLen = orderRequest.OrderData.Customer.ParentOU@length;
            for(int p = 0; p < pouLen; p++) {
                int pSubLen = orderRequest.OrderData.Customer.ParentOU[p].Subscriber@length;
                for (int ps = 0; ps < pSubLen; ps++) {
                    Concepts.OrderRequest.OrderElements.Subscriber sub = orderRequest.OrderData.Customer.ParentOU[p].Subscriber[ps];
                    String chkRes = "true";

                    if(String.length(chkXPath) > 0) {
                        String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, sub.RefId);
                        chkRes = XPath.execute("/(" + chkXPath + ")", sXML, "ns0=www.tibco.com/be/ontology/Concepts/OrderRequest/OrderRequest");
                    }

                    if(String.equals(chkRes,"true")) {
                        /* Creates SubscriberExtendedInfo(UPDATE_KNOX_IMEI=Y) — full XSLT in §9.5 */
                        Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo chkUpdateKnox =
                            Instance.createInstance("xslt://{{/Concepts/...}}/* see §9.5 */");
                        sub.ExtendedInfo[sub.ExtendedInfo@length] = chkUpdateKnox;
                        isSkipped = false;
                    }
                }

                /*** ChildOU Subscribers — same pattern ***/
                int couLen = orderRequest.OrderData.Customer.ParentOU[p].ChildOU@length;
                for (int c = 0; c < couLen; c++) {
                    int cSubLen = orderRequest.OrderData.Customer.ParentOU[p].ChildOU[c].Subscriber@length;
                    for (int cs = 0; cs < cSubLen; cs++) {
                        Concepts.OrderRequest.OrderElements.Subscriber sub = orderRequest.OrderData.Customer.ParentOU[p].ChildOU[c].Subscriber[cs];
                        String chkRes = "true";
                        if(String.length(chkXPath) > 0) {
                            String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, sub.RefId);
                            chkRes = XPath.execute("/(" + chkXPath + ")", sXML, "ns0=www.tibco.com/be/ontology/Concepts/OrderRequest/OrderRequest");
                        }
                        if(String.equals(chkRes,"true")) {
                            /* Creates SubscriberExtendedInfo(UPDATE_KNOX_IMEI=Y) — full XSLT in §9.5 */
                            Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo chkUpdateKnox =
                                Instance.createInstance("xslt://{{/Concepts/...}}/* see §9.5 */");
                            sub.ExtendedInfo[sub.ExtendedInfo@length] = chkUpdateKnox;
                            isSkipped = false;
                        }
                    }
                }
            }

            if(!isSkipped) {
                RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity);
                long pid = System.nanoTime();
                /* Logger event — OPERATION_NAME=CHECK_UPDATE_KNOX_IMEI, no payload — see §11 */
                Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{/Events/OMConsumers/OMXESB/Logger}}/* see §11 */"));
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch (Exception ae) {
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
