# Request_CCP_ACTIVATE_SIM

FM Logic Documentation — CCP SIM Activation (IntraActivitySequencing)

---

## §1 — Overview & Purpose

**CCP_ACTIVATE_SIM** sends an `ActivateSimRequest` to the CCP (Charging & Control Platform) for each subscriber in the order's ParentOU list. It uses the **IntraActivitySequencing** pattern — requests are queued and dispatched one at a time. CCP credentials (`CCP_USER` / `CCP_PASSWORD`) are sourced from order-level ExtendedInfo. A short `requestId` is generated from the order's Channel field.

> **[CRITICAL BUG] Missing ActionResponseEvent:** The response rulefunction does NOT call `IntraActivitySequencing.ActionResponseEvent` after each response. For multi-subscriber orders, only the first subscriber's SIM activation is ever sent — subsequent queued requests are never dispatched. The response RF uses a plain count-based fan-in (`RequestCount == Response@length`) that will never complete for N>1 subscribers.

| Attribute | Value |
|-----------|-------|
| Rule file | Request_CCP_ACTIVATE_SIM.rule |
| Response rulefunction | Response_CCP_ACTIVATE_SIM.rulefunction |
| Priority | 5 |
| Forward chain | true |
| Backend system | CCP via ESB (TIBCO FM schema) |
| Request event type | `Events.OMConsumers.OMXFM.Request.CCP_ACTIVATE_SIM` |
| Response event type | `Events.OMConsumers.OMXFM.Response.CCP_ACTIVATE_SIM` |
| Response concept | `Concepts.FM.Base.ResponseBase` |
| Payload operation | `ActivateSimRequest` |
| Schema namespace | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd6` |
| Dispatch scope | Per ParentOU Subscriber (no ChildOU support) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM priority |
| forwardChain | true | Enables forward chaining after execution |
| Rule type | IntraActivitySequencing | `assertEvent` + `ActionRequestEvent` + `SendFirstRequestEvent` |
| RequestCount | Not incremented by this rule | IntraActivitySequencing manages count internally |
| Resubmit handling | Yes | `PurgePendingRequestsBeforeResubmit` before re-queueing |
| Skip mechanism | Yes | Skips if PreExecCheck fails OR no subscribers found |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Main order state — subscriber list, credentials, Channel |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — holds IntraActivitySequencing queue |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId matches process flow pointer |
| 2 | `orderCurrentActivity.ActivityID == "CCP_ACTIVATE_SIM"` | Constrains rule to CCP_ACTIVATE_SIM only |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCP_ACTIVATE_SIM"` | Double-check via process flow NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity is ready to execute |

---

## §5 — Execution Flow Diagram

```
1. Resubmit purge → if isActResub: PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
2. Load activity config → Instance.getByExtIdByUri(NextActivityName) → nextAct
3. PreExecCheck (activity-level) → serialize full orderRequest → XPath evaluate
4. Extract CCP credentials → iterate ExtendedInfo[] for CCP_USER and CCP_PASSWORD
5. Compute requestId → "OMX" + Channel + "000000000" → substring(0,12)
6. Per-subscriber loop (ParentOU[i].Subscriber[j]):
   a. Build CCP_ACTIVATE_SIM event (ActivateSimRequest: user, password, msisdn, requestId)
   b. Event.assertEvent(reqEvent)
   c. IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity) — enqueue
   d. Send audit log (unconditional — no AllowWriteLog gate)
   e. isSkipped = false
7. Dispatch first → IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
8. Status → GetActivityStatusString("1", false) + SendDataToDB
   OR: SkipActivity("4") if isSkipped
```

> **Audit log inside subscriber loop:** The audit log fires on each subscriber iteration — N audit events for N subscribers — even though only 1 JMS request is dispatched after the loop.

> **PreExecCheck scope:** Applied once at activity level using the entire serialized `orderRequest`. If it fails, ALL subscriber activations are skipped.

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
if(isActResub)
    RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

try {
    Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
    boolean isSkipped = true;
    String chkRes = "true";

    // Activity-level PreExecCheck using full orderRequest serialization
    if(String.length(nextAct.PreExecCheck) > 0) {
        String sXML = Instance.serializeUsingDefaults(orderRequest);
        chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
    }

    if(String.equals(chkRes, "true")) {
        // Extract CCP credentials from ExtendedInfo
        String ccp_user = "", ccp_password = "";
        for(int i = 0; i < orderRequest.OrderData.ExtendedInfo@length; i++) {
            if(String.equals(exInfo.Name, "CCP_USER"))     ccp_user = exInfo.Value;
            if(String.equals(exInfo.Name, "CCP_PASSWORD")) ccp_password = exInfo.Value;
        }

        // requestId = "OMX" + Channel (truncated to 12 chars)
        String requestId = String.substring("OMX" + orderRequest.OrderData.Channel + "000000000", 0, 12);

        // Per-subscriber dispatch loop
        for(int i = 0; i < pOuLen; i++) {
            String pOuRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;
            for(int j = 0; j < ou.Subscriber@length; j++) {
                Concepts.OrderRequest.OrderElements.Subscriber sub = ou.Subscriber[j];
                // [XSLT builds ActivateSimRequest — see §9.7]
                Events.OMConsumers.OMXFM.Request.CCP_ACTIVATE_SIM reqEvent = Event.createEvent("xslt://...");
                Event.assertEvent(reqEvent);
                RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                // Audit log — NOTE: no AllowWriteLog gate (unlike most FMs)
                long pid = System.nanoTime();
                Event.Ext.sendEventImmediate(Event.createEvent("xslt://Logger..."));
                isSkipped = false;
            }
        }
    }

    if(!isSkipped) {
        RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
        RuleFunctions.Helpers.SendDataToDB(orderRequest);
    } else {
        RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
    }
} catch(Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §7 — Data Extraction

### CCP Credentials from ExtendedInfo

| ExtendedInfo key | Target variable | Notes |
|-----------------|----------------|-------|
| `CCP_USER` | `ccp_user` | CCP username → `<user>` payload field |
| `CCP_PASSWORD` | `ccp_password` | CCP password → `<password>` payload field (plaintext) |

> **[RISK — MEDIUM] Security concern:** CCP credentials stored in plaintext in `orderRequest.OrderData.ExtendedInfo`. If `WritePayload="true"`, the password appears in audit logs verbatim.

### requestId Generation

```java
String requestId = "OMX" + orderRequest.OrderData.Channel + "000000000";
requestId = String.substring(requestId, 0, 12);
// Example: Channel="RETAIL" → "OMXRETAIL000000000" → "OMXRETAIL000"
// Example: Channel="DT"    → "OMXDT000000000"     → "OMXDT0000000"
```

> **[RISK — HIGH] requestId collision:** All orders from the same channel share the same requestId. CCP may use requestId for idempotency, causing silent deduplication failures for concurrent orders.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Fires for any order with PreExecCheck satisfied and at least one ParentOU subscriber. Used in PREPAID_REGISTRATION (step 17) to activate a new prepaid SIM.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCP_ACTIVATE_SIM` | ActivateSimRequest to CCP (first queued request only) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit — **unconditional** (no AllowWriteLog gate) |

### §8.3 — Backend API Details

| System | Operation | Protocol | Schema |
|--------|-----------|----------|--------|
| CCP | ActivateSim | JMS async (IntraActivitySequencing) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd6` |

### §8.4 — BE Working Memory Dependencies

| Concept path | Access | Purpose |
|-------------|--------|---------|
| `orderRequest.OrderData.Channel` | Read | requestId generation |
| `orderRequest.OrderData.ExtendedInfo[Name="CCP_USER"].Value` | Read | CCP username |
| `orderRequest.OrderData.ExtendedInfo[Name="CCP_PASSWORD"].Value` | Read | CCP password |
| `orderRequest.OrderData.Customer.ParentOU[*].RefId` | Read | RefID header in JMS event |
| `orderRequest.OrderData.Customer.ParentOU[*].Subscriber[*].MSISDN` | Read | MSISDN for SIM activation |
| `orderRequest.OrderData.OMXTrackingId` | Read | JMSCorrelationID |
| `orderRequest.OrderData.OrderType` | Read | Response audit gate |
| `orderCurrentActivity.Status` | Write | Status transition |

### §8.5 — ExtendedInfo Fields Required

| Key | Source | Required? | Purpose |
|-----|--------|-----------|---------|
| `CCP_USER` | `orderRequest.OrderData.ExtendedInfo` | Required | CCP authentication username |
| `CCP_PASSWORD` | `orderRequest.OrderData.ExtendedInfo` | Required | CCP authentication password (plaintext) |

### §8.6 — Global Variable Dependencies

| Variable path | Used in |
|--------------|---------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Include UserName/PassWord if "true" |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit log COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit log TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Response audit payload gating |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT param | Bound from |
|------------|-----------|
| `$orderRequest` | Working memory `orderRequest` concept |
| `$pOuRefId` | `orderRequest.OrderData.Customer.ParentOU[i].RefId` |
| `$globalVariables` | Global variable store |
| `$ccp_user` | Extracted from `ExtendedInfo[Name="CCP_USER"].Value` |
| `$ccp_password` | Extracted from `ExtendedInfo[Name="CCP_PASSWORD"].Value` |
| `$sub` | Current subscriber: `ParentOU[i].Subscriber[j]` |
| `$requestId` | Computed: `"OMX" + Channel` truncated to 12 chars |

### §9.2 — Event Container Construction

Event type: `Events.OMConsumers.OMXFM.Request.CCP_ACTIVATE_SIM` (dedicated event type)

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Always (no xsl:if guard) |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Conditional |
| `RefID` | `$pOuRefId` (ParentOU RefId) | Always |
| `UserName` | `$orderRequest/OrderData/User` | If IsEnableUserPass="true" |
| `PassWord` | `$orderRequest/OrderData/Password` | If IsEnableUserPass="true" |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Conditional |

### §9.4 — Payload Root Element

`<ns:ActivateSimRequest>` (namespace: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd6`)

### §9.5 — Core Payload Fields

| XML element | Source | Notes |
|-------------|--------|-------|
| `user` | `$ccp_user` | CCP username |
| `password` | `$ccp_password` | CCP password (plaintext — security risk) |
| `msisdn` | `$sub/MSISDN` | Subscriber MSISDN |
| `requestId` | `$requestId` | Channel-based 12-char ID (non-unique per request) |

### §9.6 — Complete Generated XML Example

```xml
<ns:ActivateSimRequest
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd6">
  <user>ccp_system_user</user>
  <password>ccp_system_pass</password>
  <msisdn>0812345678</msisdn>
  <requestId>OMXRETAIL000</requestId>
</ns:ActivateSimRequest>
```

### §9.7 — XSLT Stylesheet Source (Request)

```xml
<xsl:stylesheet
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd6"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  version="1.0">
  <!-- params: $orderRequest, $pOuRefId, $globalVariables, $ccp_user, $ccp_password, $sub, $requestId -->
  <xsl:template match="/">
    <createEvent><event>
      <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      <!-- JMSCorrelationID: $orderRequest/OrderData/OMXTrackingId (if present) -->
      <!-- OrderID: $orderRequest/OrderData/OrderID (if present) -->
      <RefID><xsl:value-of select="$pOuRefId"/></RefID>
      <!-- UserName, PassWord (if IsEnableUserPass="true") -->
      <!-- OrderType (if present) -->
      <payload>
        <ns:ActivateSimRequest>
          <user><xsl:value-of select="$ccp_user"/></user>
          <password><xsl:value-of select="$ccp_password"/></password>
          <msisdn><xsl:value-of select="$sub/MSISDN"/></msisdn>
          <requestId><xsl:value-of select="$requestId"/></requestId>
        </ns:ActivateSimRequest>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                          [Always — no xsl:if guard]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId                [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                      [Conditional]
    ├── RefID                ← $pOuRefId (ParentOU RefId)                           [Always]
    ├── UserName             ← $orderRequest/OrderData/User                         [Credential-gated: IsEnableUserPass="true"]
    ├── PassWord             ← $orderRequest/OrderData/Password                     [Credential-gated: IsEnableUserPass="true"]
    ├── OrderType            ← $orderRequest/OrderData/OrderType                    [Conditional]
    └── payload                                                                      [Always]
        └── ns:ActivateSimRequest                                                    [Always]
            ├── user         ← $ccp_user (ExtendedInfo[CCP_USER])                  [Always]
            ├── password     ← $ccp_password (ExtendedInfo[CCP_PASSWORD])           [Always] ⚠ PLAINTEXT SENSITIVE
            ├── msisdn       ← $sub/MSISDN                                          [Always]
            └── requestId    ← $requestId ("OMX"+Channel truncated 12)             [Always] ⚠ NON-UNIQUE
```

Legend: `[Always]` = unconditional | `[Conditional]` = inside xsl:if | `[Credential-gated]` = behind IsEnableUserPass flag

---

## §11 — Audit Logging

| Event | Trigger | Key fields |
|-------|---------|-----------|
| Request audit (per subscriber) | **Unconditional** (no AllowWriteLog check) | `OPERATION_NAME="CCP_ACTIVATE_SIM"`, `AUDIT_TRACE="Request Sent for CCP_ACTIVATE_SIM"`, `PROCESS_ID=concat(pid,"_REQ")`; payload = full `$reqEvent` (includes password if WritePayload=true) |
| Response audit | `AllowWriteLog(OrderType)` = true | `OPERATION_NAME="CCP_ACTIVATE_SIM"`, `AUDIT_TRACE="Response received for CCP_ACTIVATE_SIM"`, `PROCESS_ID=concat(pid,"_RES")` |

---

## §12 — Activity Status Management

| Condition | Action | Status code |
|-----------|--------|------------|
| At least one subscriber found and PreExecCheck passes | `SendFirstRequestEvent` + `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" = PROCESSING / SENT |
| PreExecCheck fails OR no subscribers found | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" = SKIPPED |

---

## §13 — Exception / Error Handling

```java
catch(Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears sequential dispatch queue for clean resubmit |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Enqueues an event for sequential dispatch |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Dequeues and dispatches the first queued request |
| `RuleFunctions.Helpers.GetActivityStatusString(code, flag)` | Translates numeric code to activity status string |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | Persists order state to database |
| `RuleFunctions.Helpers.SkipActivity(orderRequest, activity, code)` | Marks activity as skipped and advances flow |
| `RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Logs exception, transitions to error state |
| `RuleFunctions.Helpers.AllowWriteLog(orderType)` | Response RF only — gates response audit log |

---

## §15 — Function Dependency Tree

```text
Request_CCP_ACTIVATE_SIM (rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()  [on resubmit]
├── Instance.getByExtIdByUri()
├── Instance.serializeUsingDefaults()                             [PreExecCheck serialization]
├── XPath.execute()                                               [PreExecCheck]
├── String.equals(), String.length(), String.substring()
├── Event.createEvent()                                           [ActivateSimRequest XSLT]
├── Event.assertEvent()
├── IntraActivitySequencing.ActionRequestEvent()
├── System.nanoTime()
├── Event.Ext.sendEventImmediate()                               [audit — no AllowWriteLog gate]
├── IntraActivitySequencing.SendFirstRequestEvent()
├── Helpers.GetActivityStatusString()
├── Helpers.SendDataToDB()
├── Helpers.SkipActivity()
└── Helpers.HandleActivityException()

Response_CCP_ACTIVATE_SIM (rulefunction)
├── Instance.createInstance()                                     [ResponseBase XSLT]
├── Helpers.AllowWriteLog()
├── System.nanoTime()
├── Event.createEvent()                                          [Logger XSLT]
├── Event.Ext.sendEventImmediate()
└── [fan-in] currActivity.RequestCount == currActivity.Response@length → "true"/"false"
    ← MISSING: IntraActivitySequencing.ActionResponseEvent() to trigger next queued request
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | Request rule, Response RF | OrderData.Channel, ExtendedInfo[], Customer.ParentOU[].Subscriber[] |
| `Concepts.OM.ProcessConfig.Activity` | Request rule, Response RF | ActivityID, Status, RequestCount, Response[] |
| `Concepts.FM.Base.ResponseBase` | Response RF | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |
| `Concepts.OrderRequest.OrderElements.ParentOU` | Request rule | RefId, Subscriber[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | Request rule | MSISDN |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Send ActivateSimRequest to CCP for each ParentOU subscriber |
| R2 | Apply activity-level PreExecCheck using full orderRequest serialization |
| R3 | Retrieve CCP_USER and CCP_PASSWORD from order ExtendedInfo |
| R4 | Generate requestId from Channel field (12-char "OMX" + Channel prefix) |
| R5 | Use IntraActivitySequencing for sequential (non-parallel) dispatch |
| R6 | Support resubmit by purging queue before re-queueing |
| R7 | Fan-in: complete when all responses received (RequestCount == Response count) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **[CRITICAL] Missing ActionResponseEvent** — Response RF does not call `IntraActivitySequencing.ActionResponseEvent`. Only first subscriber's SIM activated; multi-subscriber orders hang. | [CRITICAL] | Add `ActionResponseEvent(currActivity)` in response RF; use its return value for fan-in |
| **requestId not unique per request** — Same Channel yields same requestId for all concurrent orders. CCP idempotency risk. | [HIGH] | Include OMXTrackingId or MSISDN in requestId |
| **No ChildOU subscriber support** — Only ParentOU subscribers are iterated. | [MEDIUM] | Add ChildOU subscriber loop |
| **Plaintext password in audit log** — `WritePayload="true"` exposes CCP_PASSWORD in audit. | [MEDIUM] | Mask password field in Logger XSLT |
| **Unconditional request audit** — No AllowWriteLog gate in request loop; inconsistent with other FMs. | [LOW] | Wrap request audit in `AllowWriteLog` check |

---

## §18 — Full Source Code (Request Rule)

```java
/**
 * @description
 * @author DESKTOP-HINKNF3
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCP_ACTIVATE_SIM {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "CCP_ACTIVATE_SIM";
        orderRequest.ProcessFlow.NextActivityID == "CCP_ACTIVATE_SIM";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        if(isActResub)
            RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
            boolean isSkipped = true;
            String chkRes = "true";
            // Activity-level PreExecCheck
            if(String.length(nextAct.PreExecCheck) > 0) {
                String sXML = Instance.serializeUsingDefaults(orderRequest);
                chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
            }
            if(String.equals(chkRes, "true")) {
                String ccp_user = "", ccp_password = "";
                for(int i = 0; i < orderRequest.OrderData.ExtendedInfo@length; i++) {
                    if(String.equals(exInfo.Name, "CCP_USER"))     ccp_user = exInfo.Value;
                    if(String.equals(exInfo.Name, "CCP_PASSWORD")) ccp_password = exInfo.Value;
                }
                String requestId = String.substring("OMX" + orderRequest.OrderData.Channel + "000000000", 0, 12);
                int pOuLen = orderRequest.OrderData.Customer.ParentOU@length;
                for(int i = 0; i < pOuLen; i++) {
                    Concepts.OrderRequest.OrderElements.ParentOU ou = orderRequest.OrderData.Customer.ParentOU[i];
                    String pOuRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;
                    for(int j = 0; j < ou.Subscriber@length; j++) {
                        Concepts.OrderRequest.OrderElements.Subscriber sub = ou.Subscriber[j];
                        // [XSLT builds ActivateSimRequest — see §9.7]
                        Events.OMConsumers.OMXFM.Request.CCP_ACTIVATE_SIM reqEvent = Event.createEvent("xslt://...");
                        Event.assertEvent(reqEvent);
                        RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                        // NOTE: no AllowWriteLog gate on request audit
                        long pid = System.nanoTime();
                        Event.Ext.sendEventImmediate(Event.createEvent("xslt://Logger..."));
                        isSkipped = false;
                    }
                }
            }
            if(!isSkipped) {
                RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
                orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
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

## §19 — Response Message Rule (Response_CCP_ACTIVATE_SIM)

### §19.1 — Overview

Creates a `ResponseBase` concept from the `CCP_ACTIVATE_SIM` response event, appends to `currActivity.Response[]`, logs the response, then checks fan-in via `RequestCount == Response@length`. Returns `"true"` when all responses received, `"false"` otherwise.

> **[CRITICAL BUG]** Does NOT call `IntraActivitySequencing.ActionResponseEvent(currActivity)`. For multi-subscriber orders only the first subscriber's SIM is activated; this RF will keep returning "false" while the remaining queued requests are never dispatched.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context for audit gate |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCP_ACTIVATE_SIM` | CCP response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity; Response[] and RequestCount for fan-in |

### §19.3 — ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId          ← $eventResponse/@extId                    [Always]
    ├── ResponseCode    ← $eventResponse/ResponseCode              [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg               [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus         [Conditional]
    └── ReferenceId     ← $eventResponse/RefID                     [Conditional]
```

### §19.4 — Response Completion Logic

| Attribute | Value |
|-----------|-------|
| Fan-in condition | `currActivity.RequestCount == currActivity.Response@length` |
| Return "true" | All responses received (equal count) |
| Return "false" | Waiting for more responses |
| Missing piece | No `IntraActivitySequencing.ActionResponseEvent` call — next queued request never dispatched |

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| `OPERATION_NAME` | `"CCP_ACTIVATE_SIM"` (no trailing space) |
| `AUDIT_TRACE` | `"Response received for CCP_ACTIVATE_SIM"` (no trailing space) |
| `PROCESS_ID` | `concat(pid, "_RES")` |
| `payload` | Full `$eventResponse` copy, gated on `WritePayload="true"` |
| Gate | `AllowWriteLog(orderRequest.OrderData.OrderType)` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
