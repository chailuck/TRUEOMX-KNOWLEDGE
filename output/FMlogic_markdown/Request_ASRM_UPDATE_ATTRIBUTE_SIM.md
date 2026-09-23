# Request_ASRM_UPDATE_ATTRIBUTE_SIM

> TIBCO BusinessEvents FM Logic — SIM Attribute Update (EXPIRE_SELF / MATCHING_ID / SIM_NOTE)

**Author:** SathidP-PC | **Priority:** 5 | **Forward Chain:** true | **Target:** ASRM (Amdocs RM) | **Lines:** 134

---

## §1 — Overview & Purpose

Updates a SIM card attribute in ASRM (Amdocs Resource Manager) for every subscriber in the order — across both POU subscribers and COU subscribers. The attribute to update is determined by the `PROJ` parameter from the ProcessConfig activity; the value for the default case is calculated from the `EXPIRE_SELF` parameter.

> **Three attribute modes driven by PROJ parameter:**
> - `PROJ=BULKESIM` → sets `MATCHING_ID` = subscriber's PMATCHID resource
> - `PROJ=RMRF` → sets `SIM_NOTE` = subscriber's MSISDN
> - Otherwise (default) → sets `EXPIRE_SELF` = date calculated from EXPIRE_SELF parameter

| Item | Value |
|------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_ASRM_UPDATE_ATTRIBUTE_SIM` |
| Author | SathidP-PC |
| Priority | 5 |
| JMS Event | `Events.OMConsumers.OMXFM.Request.ASRM_UPDATE_ATTRIBUTE_SIM` |
| Payload Schema | `ns1:UnifiedResourceAttributesInfo` (amdocs.rm3g.interfaces.datatypes) |
| Response Concept | `Concepts.FM.Response.ASRM_InvokeUnifiedResourceRes` |
| Fan-In Criterion | `count(Response[ResponseCode ends "000"]) == RequestCount` |
| Target System | ASRM (Amdocs Resource Manager) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM rule priority |
| forwardChain | true | Rule may re-fire after working memory update |
| Pattern | IntraActivitySequencing (multi-subscriber fan-out) | One event per eligible subscriber |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order graph |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Parameters, RequestCount, Response[], Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Match current process step |
| 2 | `orderCurrentActivity.ActivityID == "ASRM_UPDATE_ATTRIBUTE_SIM"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "ASRM_UPDATE_ATTRIBUTE_SIM"` | Process flow confirmation |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fire if not already in progress |

---

## §5 — Execution Flow Diagram

1. Detect resubmit: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Read `EXPIRE_SELF` parameter → compute expire_self date string
3. Read `PROJ` parameter → paramValue (drives attribute mode)
4. **Loop A — POU Subscribers**: reqSuccess check → PreExecCheck (`GetXMLForSubscriber`) → dispatch ASRM_UPDATE_ATTRIBUTE_SIM → audit log → `RequestCount++`
5. **Loop B — COU Subscribers**: same pattern → PreExecCheck (`GetXMLForSubscriberInChildOU`) → dispatch (always SIM resource)
6. Post-loop: dispatched → `GetActivityStatusString("1",false)` + `SendDataToDB()`; else → `SkipActivity(...,"4")`
7. catch: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §6 — Parameter-Driven Logic

### §6.1 EXPIRE_SELF Parameter

| attrValue | expire_self Result |
|-----------|-------------------|
| null | `" "` (space — blank) |
| `"-1"` | `" "` (space — blank) |
| Numeric string (e.g., "30") | `DateTime.format(DateTime.addDay(Date.today(), 30), "dd/MM/yyyy")` → e.g., `"26/08/2026"` |

> A value of `" "` effectively clears the EXPIRE_SELF attribute in ASRM.

### §6.2 PROJ Parameter — Attribute Mode Selection

| paramValue | AttrName | AttrValue Source | Purpose |
|------------|----------|-----------------|---------|
| `BULKESIM` | `MATCHING_ID` | `psub/ResourceInfo[ResourceName="PMATCHID"]/ValuesArray` | eSIM bulk matching |
| `RMRF` | `SIM_NOTE` | `psub/MSISDN` | SIM note = mobile number |
| anything else | `EXPIRE_SELF` | `$expire_self` (computed) | Set/clear SIM expiry date |

### §6.3 SIM Resource Resolution — POU Subscriber

| Condition | ns:Value Source |
|-----------|----------------|
| `paramValue` contains "RIO" AND `ResourceInfo[ResourceName="MISIM"]` count > 0 | `ResourceInfo[MISIM]/ValuesArray` |
| `paramValue` contains "RIO" AND no MISIM resource | `ResourceInfo[SIM]/ValuesArray` |
| Otherwise | `ResourceInfo[SIM]/ValuesArray` |

### §6.4 SIM Resource Resolution — COU Subscriber

Always uses `ResourceInfo[ResourceName="SIM"]/ValuesArray`. No MISIM/RIO logic.

> **MISIM/RIO asymmetry:** POU subscribers may use MISIM resource for RIO project orders; COU subscribers always use SIM.

---

## §7 — Conditional UserName/Password

Both XSLT variants wrap UserName and PassWord in:

```xml
<xsl:if test="$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass='true'">
```

Unlike most FM rules that conditionally include credentials based on the order data. ASRM may not require credentials in all environments.

---

## §8 — System & Integration Dependencies

### §8.1 ESB / JMS Channel Dependencies

| Direction | Event | Channel | Purpose |
|-----------|-------|---------|---------|
| [OUTBOUND] | `ASRM_UPDATE_ATTRIBUTE_SIM` | ASRM FM JMS | Set SIM attribute |
| [OUTBOUND] | `Logger` | ESB Audit Log | Audit trail (LOG_LEVEL=INFO) |

### §8.2 Backend API Details

| System | Operation | Schema | Protocol |
|--------|-----------|--------|---------|
| ASRM | UpdateAttribute on SIM | `ns1:UnifiedResourceAttributesInfo` | JMS |

### §8.3 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `orderCurrentActivity.RequestCount` | Read + Write | Incremented per dispatch |
| `orderCurrentActivity.Status` | Write | ACTIVE or SKIP |
| `orderCurrentActivity.Response[]` | Read | reqSuccess check per subscriber |
| `orderCurrentActivity.Parameter[]` | Read | EXPIRE_SELF and PROJ keys |
| `orderRequest.IsOrderResubmitted` | Read | Resubmit guard |

### §8.4 ResourceInfo Keys Required

| ResourceName | Context | Purpose |
|-------------|---------|---------|
| `SIM` | All subscribers | SIM ICCID for RMEntityIdInfo |
| `MISIM` | POU Sub when PROJ contains "RIO" | MI-SIM ICCID (alternate) |
| `PMATCHID` | Subscriber when PROJ=="BULKESIM" | eSIM profile matching ID |

### §8.5 Activity Parameters (from ProcessConfig)

| Key | Type | Values | Effect |
|-----|------|--------|--------|
| `EXPIRE_SELF` | String (numeric or "-1") | "-1" / null / days count | Drives expiry date; "-1" or null → blank |
| `PROJ` | String | "BULKESIM", "RMRF", or others (may contain "RIO") | Selects attribute mode and SIM resolution |

### §8.6 Global Variable Dependencies

| Path | Used In | Purpose |
|------|---------|---------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Request XSLT | Gate for credentials |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit log | COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit log | TARGET_SYSTEM |
| `$globalVariables/OMX_OM/WritePayload` | Audit log | Payload logging gate |

---

## §9 — Detailed Payload Build

### §9.1 Event Container Fields

| Field | Source | Notes |
|-------|--------|-------|
| JMSPriority | `$orderRequest/OrderPriority` | Conditional |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| RefID | `$refId` (subscriber RefId) | Always |
| UserName | `$orderRequest/OrderData/User` | Conditional on IsEnableUserPass='true' |
| PassWord | `$orderRequest/OrderData/Password` | Conditional on IsEnableUserPass='true' |

### §9.2 Payload — UnifiedResourceAttributesInfo

| Element | Value / Source |
|---------|---------------|
| `ns1:RMEntityIdInfo / ns:Type` | `"SIM"` (static) |
| `ns1:RMEntityIdInfo / ns:Value` | MISIM or SIM from ResourceInfo (context-dependent) |
| `ns1:AttributesData / ns2:AttrName` | MATCHING_ID / SIM_NOTE / EXPIRE_SELF (PROJ-driven) |
| `ns1:AttributesData / ns2:AttrValue` | PMATCHID / MSISDN / expire_self (PROJ-driven) |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority        [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID    [Conditional]
    ├── RefID                ← $refId (subscriber RefId)          [Always]
    ├── UserName             ← $orderRequest/OrderData/User       [Conditional: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password   [Conditional: IsEnableUserPass='true']
    ├── OrderType            ← $orderRequest/OrderData/OrderType  [Conditional]
    └── payload
        └── ns1:UnifiedResourceAttributesInfo
            ├── ns1:RMEntityIdInfo
            │   ├── ns:Type    ← "SIM" (static)                  [Always]
            │   └── ns:Value   [xsl:choose — POU only]
            │       ├── when contains(paramValue,'RIO') AND MISIM exists
            │       │     → ResourceInfo[MISIM]/ValuesArray       [Conditional]
            │       ├── when contains(paramValue,'RIO') AND no MISIM
            │       │     → ResourceInfo[SIM]/ValuesArray         [Conditional]
            │       └── otherwise → ResourceInfo[SIM]/ValuesArray [Conditional]
            │       (COU: always ResourceInfo[SIM]/ValuesArray — no choose)
            └── ns1:AttributesData  [xsl:choose on paramValue]
                ├── when "BULKESIM"
                │   ├── ns2:AttrName ← "MATCHING_ID" (static)   [Always]
                │   └── ns2:AttrValue ← ResourceInfo[PMATCHID]/ValuesArray [Conditional]
                ├── when "RMRF"
                │   ├── ns2:AttrName ← "SIM_NOTE" (static)      [Always]
                │   └── ns2:AttrValue ← $psub/MSISDN             [Conditional]
                └── otherwise (default)
                    ├── ns2:AttrName ← "EXPIRE_SELF" (static)   [Always]
                    └── ns2:AttrValue ← $expire_self             [Always]
```

---

## §11 — Audit Logging

| Field | Value | Notes |
|-------|-------|-------|
| PROCESS_ID | `concat(System.nanoTime(), "_REQ")` | |
| OPERATION_NAME | `$orderCurrentActivity/ActivityID` | **Dynamic** — not hardcoded |
| LOG_LEVEL | INFO | |
| AUDIT_TRACE | `concat("Request Sent for RefId ", $refId)` | Per-subscriber trace |
| payload | Conditional on WritePayload="true" | |

---

## §12 — Activity Status Management

| State | Trigger | Call |
|-------|---------|------|
| [ACTIVE] | At least one event dispatched | `GetActivityStatusString("1", false)` + `SendDataToDB()` |
| [SKIPPED] | No eligible subscribers | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |

---

## §13 — Exception / Error Handling

| Exception Type | Handler |
|---------------|---------|
| `Exception ae` (catch-all) | `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|----------|--------|---------|
| `GetActivityParamValueFromKey(orderCurrentActivity, "EXPIRE_SELF")` | String | Read EXPIRE_SELF param |
| `GetActivityParamValueFromKey(orderCurrentActivity, "PROJ")` | String | Read PROJ param for attribute mode |
| `DateTime.addDay(Date.today(), n)` | DateTime | Compute expiry date |
| `DateTime.format(dt, "dd/MM/yyyy")` | String | Format date for ASRM |
| `GetXMLForSubscriber(orderRequest, refId)` | String XML | POU subscriber PreExecCheck |
| `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` | String XML | COU subscriber PreExecCheck |
| `GetActivityStatusString("1", false)` | String | Maps "1" → ACTIVE status |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | void | Marks SKIPPED |
| `SendDataToDB(orderRequest)` | void | Persists order state |
| `HandleActivityException(...)` | void | Exception handler |

---

## §15 — Function Dependency Tree

```text
Request_ASRM_UPDATE_ATTRIBUTE_SIM (BE rule)
├── GetActivityParamValueFromKey(orderCurrentActivity, "EXPIRE_SELF")
├── XPath.evalAsInt("number($attrValue)")              [string → int for addDay]
├── DateTime.addDay(Date.today(), n)
├── DateTime.format(dt, "dd/MM/yyyy")
├── GetActivityParamValueFromKey(orderCurrentActivity, "PROJ")
├── Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")
├── [Loop A — POU Subscribers]
│   ├── GetXMLForSubscriber(orderRequest, refId)
│   ├── XPath.execute(...)                             [PreExecCheck]
│   ├── Event.createEvent("xslt://{{.../ASRM_UPDATE_ATTRIBUTE_SIM}}...")
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   ├── Event.createEvent("xslt://{{.../Logger}}...")
│   └── Event.Ext.sendEventImmediate(auditEvent)
├── [Loop B — COU Subscribers]
│   ├── GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)
│   ├── XPath.execute(...)                             [PreExecCheck]
│   ├── Event.createEvent("xslt://{{.../ASRM_UPDATE_ATTRIBUTE_SIM}}...")  [COU variant]
│   └── Event.Ext.sendEventImmediate(reqEvent + auditEvent)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(...)
└── HandleActivityException(...)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Fan-out to all POU and COU subscribers
- **R2** — Attribute mode from PROJ: BULKESIM→MATCHING_ID; RMRF→SIM_NOTE; default→EXPIRE_SELF
- **R3** — EXPIRE_SELF date: today + n days; "-1" or null → blank space
- **R4** — POU subscribers with RIO project use MISIM if available; fallback to SIM
- **R5** — COU subscribers always use SIM resource
- **R6** — UserName/PassWord gated on `IsEnableUserPass='true'` global variable
- **R7** — Resubmit safety: skip subscriber if CompletionStatus==2 response exists

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| PROJ "RIO" check is substring — matches "RIOPILOT", "XRIO" etc. | [MEDIUM] | Test all PROJ variants used in prod |
| expire_self=" " (space) vs empty string — ASRM behavior may differ | [MEDIUM] | Verify ASRM API contract |
| BULKESIM: PMATCHID absent → empty AttrValue | [LOW] | Confirm ASRM accepts missing AttrValue |
| Dynamic OPERATION_NAME in audit log — harder to filter | [LOW] | Use ActivityID pattern match in log analytics |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author SathidP-PC
 */
rule Rules.OMConsumers.OMXFM.Request.Request_ASRM_UPDATE_ATTRIBUTE_SIM {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "ASRM_UPDATE_ATTRIBUTE_SIM";
        orderRequest.ProcessFlow.NextActivityID == "ASRM_UPDATE_ATTRIBUTE_SIM";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub=(orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
                orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");

            String attrValue = RuleFunctions.Helpers.GetActivityParamValueFromKey(orderCurrentActivity, "EXPIRE_SELF");
            String expire_self = " ";
            if (attrValue != null) {
                if(String.equals(attrValue, "-1")) {
                    expire_self = " ";
                } else {
                    expire_self = DateTime.format(DateTime.addDay(Date.today(),
                        XPath.evalAsInt(/* "number($attrValue)" */)), "dd/MM/yyyy");
                }
            }
            String paramValue = RuleFunctions.Helpers.GetActivityParamValueFromKey(orderCurrentActivity, "PROJ");
            boolean isSkipped = true;

            // Loop A: POU Subscribers
            for (int i=0; i < orderRequest.OrderData.Customer.ParentOU@length; i++) {
                for(int j=0; j < orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length; j++) {
                    // reqSuccess, PreExecCheck, then:
                    // dispatch Event.createEvent("xslt://{{.../ASRM_UPDATE_ATTRIBUTE_SIM}}...")
                    //   → §9 for XSLT (MISIM/RIO logic + PROJ-driven attribute)
                    // audit: concat("Request Sent for RefId ", $refId)
                }
                // Loop B: COU Subscribers
                for(int k=0; k < orderRequest.OrderData.Customer.ParentOU[i].ChildOU@length; k++) {
                    for(int j=0; j < ...[k].Subscriber@length; j++) {
                        // COU variant: always SIM resource
                    }
                }
            }

            if(!isSkipped) {
                orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
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

## §19 — Response Message Rule

### §19.1 Overview

`Response_ASRM_UPDATE_ATTRIBUTE_SIM.rulefunction` creates `ASRM_InvokeUnifiedResourceRes`, appends to `currActivity.Response[]`, and fan-in checks ResponseCode "000" suffix.

> **Event.sendEvent() vs Immediate:** Response audit log uses `Event.sendEvent()` (asynchronous), not `Event.Ext.sendEventImmediate()`.

> **extId outside XSLT:** `String extId = OMXUtils.generateTrackingID()` called in BE code and passed as XSLT parameter — unlike most FMs that call `generateTrackingID()` inside the XSLT.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.ASRM_UPDATE_ATTRIBUTE_SIM` | Inbound response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; RequestCount for fan-in |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId           ← $extId (OMXUtils.generateTrackingID() called in BE, not XSLT) [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode                                    [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg                                     [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus                                [Conditional]
    └── ReferenceId      ← $eventResponse/RefID                                           [Conditional]
```

### §19.4 Response Completion Logic

| Step | Detail |
|------|--------|
| Append | `currActivity.Response[currActivity.Response@length] = activityRes` |
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in | `currActivity.RequestCount == successResponseCount` → return "true" |

### §19.5 Response Audit Fields

| Field | Value | Notes |
|-------|-------|-------|
| PROCESS_ID | `concat(System.nanoTime(), "_RES")` | |
| OPERATION_NAME | `$actId` = `currActivity.ActivityID` | Dynamic |
| AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` | Per-subscriber |
| Send method | `Event.sendEvent()` | Asynchronous |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
