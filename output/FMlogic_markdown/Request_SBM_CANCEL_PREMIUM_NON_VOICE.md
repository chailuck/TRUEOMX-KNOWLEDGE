# Request_SBM_CANCEL_PREMIUM_NON_VOICE

**Rule class:** `Rules.OMConsumers.OMXFM.Request.Request_SBM_CANCEL_PREMIUM_NON_VOICE`
**File:** `Request_SBM_CANCEL_PREMIUM_NON_VOICE.rule`
**Priority:** 5 | **forwardChain:** true
**Type:** External FM (OMXFM) — JMS Request to SBM
**Pattern:** IntraActivitySequencing (single request per order)
**Backend:** SBM — function_id `102500014` (cancel premium non-voice)

---

## §1 — Overview & Purpose

This rule sends a **single** JMS request to SBM's `doServiceRequest` endpoint with `function_id = "102500014"` to cancel a premium non-voice dealer balance entry. Unlike subscriber-level FM rules (CDB, CCP, ASRM), this operates at **order level** — no subscriber loop. The target is dealer account data stored in order-level ExtendedInfo fields.

The rule is triggered during PREPAID_CANCEL to cancel any outstanding dealer premium non-voice balance. It uses the `IntraActivitySequencing` framework for asynchronous request tracking and waits for the SBM response via `Response_SBM_CANCEL_PREMIUM_NON_VOICE`.

| Item | Value |
|------|-------|
| Rule class | `Rules.OMConsumers.OMXFM.Request.Request_SBM_CANCEL_PREMIUM_NON_VOICE` |
| ActivityID | `SBM_CANCEL_PREMIUM_NON_VOICE` |
| Backend system | SBM (Subscriber Management) |
| SBM function_id | `102500014` (cancel premium non-voice) |
| Request schema | `ns3:SBMPremiumNonVoiceRequest / ns3:doServiceRequest` |
| Request event type | `Events.OMConsumers.OMXFM.Request.SBM_PREMIUM_NON_VOICE` |
| Response event type | `Events.OMConsumers.OMXFM.Response.SBM_PREMIUM_NON_VOICE` |
| Fan-out granularity | Single request per order (no subscriber loop) |
| Fan-in completion | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Resubmit support | Yes — `PurgePendingRequestsBeforeResubmit` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule type | `rule` | RETE stateful rule |
| priority | 5 | Standard priority |
| forwardChain | true | Re-evaluates if working memory changes during execution |
| Namespace | OMXFM / Request | External FM — sends JMS to backend |
| Response rulefunction | `Response_SBM_CANCEL_PREMIUM_NON_VOICE` | Handles async SBM reply; see §19 |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Root order — ExtendedInfo fields read for SBM payload |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Current activity — PreExecCheck read from nextAct; Status set to IN_PROGRESS |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Meaning |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity matches current process step |
| 2 | `orderCurrentActivity.ActivityID == "SBM_CANCEL_PREMIUM_NON_VOICE"` | This rule fires for the SBM cancel step |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SBM_CANCEL_PREMIUM_NON_VOICE"` | Process flow confirms this step is next |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity has not yet been processed |

---

## §5 — Execution Flow Diagram

1. **Resubmit check:** `isActResub = (RequestCount > 0 && IsOrderResubmitted)` — if true, calls `PurgePendingRequestsBeforeResubmit`.
2. **PreExecCheck (from nextAct):** Reads `PreExecCheck` from `nextAct = Instance.getByExtIdByUri(NextActivityName, ...)`. If fails → `isSkipped = true`.
3. **Build and assert request event:** Creates `SBM_PREMIUM_NON_VOICE` event via XSLT — builds `ns3:doServiceRequest` payload with dealer ExtendedInfo; asserts into working memory and calls `ActionRequestEvent`.
4. **Audit log:** `sendEventImmediate(Logger)` with `AUDIT_TRACE="Request Sent for SBM_CANCEL_PREMIUM_NON_VOICE"`. Payload gated by `WritePayload` GlobalVar — carries the request event.
5. **Send request / skip:** If not skipped → `SendFirstRequestEvent`, set status IN_PROGRESS, persist to DB. If skipped → `SkipActivity("4")`.
6. **Async wait:** Rule exits; SBM processes and returns response asynchronously to `Response_SBM_CANCEL_PREMIUM_NON_VOICE`.

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### §6.1 Resubmit Handling

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
if(isActResub) {
    RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
}
```

### §6.2 SBM Channel Selection

| Condition | ns3:channel value |
|-----------|-----------------|
| `exists($orderRequest/OrderData/ExtendedInfo[Name="SBM_CHANNEL"]/Value)` | Value from `ExtendedInfo[Name="SBM_CHANNEL"]/Value` |
| (fallback — key absent) | `"OMX"` (static default) |

### §6.3 IntraActivitySequencing Pattern

| Call | Purpose |
|------|---------|
| `ActionRequestEvent(reqEvent, orderCurrentActivity)` | Registers request event with the sequencer |
| `SendFirstRequestEvent(orderCurrentActivity)` | Dispatches the request via JMS |

---

## §7 — Data Extraction

All payload data is sourced from order-level ExtendedInfo keys. No subscriber (ParentOU) iteration occurs.

| ExtendedInfo key | Mapped to | Conditional? |
|-----------------|-----------|-------------|
| `SBM_CHANNEL` | `ns3:channel` | Yes (fallback "OMX") |
| `REF_ID_DEALER_BALANCE` | `ns3:parameters/ns3:item/ns3:value` (key="refId") | Always present (may be empty) |
| `DEALER_MOBILE_NO` | `ns3:service_no` | Yes |

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

SBM_CANCEL_PREMIUM_NON_VOICE cancels a dealer premium non-voice balance during PREPAID_CANCEL. The PreExecCheck on this activity determines whether there is a dealer balance to cancel. If no dealer balance exists, the activity is skipped.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.SBM_PREMIUM_NON_VOICE` | Cancel premium non-voice request to SBM |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.SBM_PREMIUM_NON_VOICE` | SBM response |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit log (always emitted) |

### §8.3 Backend API Details — SBM doServiceRequest

| Field | Value |
|-------|-------|
| Backend system | SBM (Subscriber Management / Service Business Manager) |
| Operation | `doServiceRequest` |
| function_id | `102500014` — cancel premium non-voice |
| Schema namespace | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/SBM/SBMPremiumNonVoiceRequest.xsd` |
| async_url | `"-"` (placeholder) |
| waiting_mode | `0` (async) |
| byPassMode | `0` (normal) |
| Correlation | JMSCorrelationID = OMXTrackingId; RefID = OMXTrackingId |

### §8.4 ExtendedInfo Fields Required

| Key | Required? | Default if absent |
|-----|-----------|-----------------|
| `SBM_CHANNEL` | Optional | `"OMX"` |
| `REF_ID_DEALER_BALANCE` | Required for meaningful call | Empty — always present in params but value may be empty |
| `DEALER_MOBILE_NO` | Optional | Element omitted from payload |

### §8.5 Global Variable Dependencies

| Path | Used for |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Gates UserName/Password headers |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `OMX_OM/WritePayload` | Gates payload in audit log |

---

## §9 — Detailed Payload Build

### §9.2 Event Container

Event type: `Events.OMConsumers.OMXFM.Request.SBM_PREMIUM_NON_VOICE`
Asserted via `Event.assertEvent(reqEvent)` before routing via IntraActivitySequencing.

### §9.3 JMS / Event Header Fields

| Header field | Source | Conditional? |
|-------------|--------|-------------|
| JMSPriority | `$orderRequest/OrderPriority` | Yes |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Yes |
| OrderID | `$orderRequest/OrderData/OrderID` | Yes |
| RefID | `$orderRequest/OrderData/OMXTrackingId` | Yes |
| UserName | `$orderRequest/OrderData/User` | Credential-gated (IsEnableUserPass='true') |
| PassWord | `$orderRequest/OrderData/Password` | Credential-gated (IsEnableUserPass='true') |
| OrderType | `$orderRequest/OrderData/OrderType` | Yes |

### §9.6 Core Payload Fields

| Field | Value | Notes |
|-------|-------|-------|
| `ns3:async_url` | `"-"` | Static placeholder |
| `ns3:byPassMode` | `0` | Normal mode |
| `ns3:channel` | From SBM_CHANNEL or `"OMX"` | xsl:choose |
| `ns3:extra_xml` | `"-"` | Unused |
| `ns3:function_id` | `"102500014"` | Hardcoded SBM function |
| `ns3:host` | `"-"` | Placeholder |
| `ns3:parameters/ns3:item/ns3:key` | `"refId"` | Static |
| `ns3:parameters/ns3:item/ns3:value` | `ExtendedInfo[Name="REF_ID_DEALER_BALANCE"]/Value` | Dynamic |
| `ns3:req_transaction_id` | `$orderRequest/OrderData/OrderID` | Conditional |
| `ns3:service_no` | `ExtendedInfo[Name="DEALER_MOBILE_NO"]/Value` | Conditional |
| `ns3:waiting_mode` | `"0"` | Async mode |

### §9.7 Complete Generated XML Example

```xml
<event>
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-20250819-00001</JMSCorrelationID>
  <OrderID>ORD-12345</OrderID>
  <RefID>OMX-20250819-00001</RefID>
  <OrderType>65</OrderType>
  <payload>
    <ns3:doServiceRequest xmlns:ns3="http://www.tibco.com/schemas/OMX-COMMON/.../SBMPremiumNonVoiceRequest.xsd">
      <ns3:req>
        <ns3:async_url>-</ns3:async_url>
        <ns3:byPassMode>0</ns3:byPassMode>
        <ns3:channel>OMX</ns3:channel>
        <ns3:extra_xml>-</ns3:extra_xml>
        <ns3:function_id>102500014</ns3:function_id>
        <ns3:host>-</ns3:host>
        <ns3:parameters>
          <ns3:item>
            <ns3:key>refId</ns3:key>
            <ns3:value>DLR-BAL-REF-9876</ns3:value>
          </ns3:item>
        </ns3:parameters>
        <ns3:req_transaction_id>ORD-12345</ns3:req_transaction_id>
        <ns3:service_no>0891234567</ns3:service_no>
        <ns3:waiting_mode>0</ns3:waiting_mode>
      </ns3:req>
    </ns3:doServiceRequest>
  </payload>
</event>
```

### §9.8 XSLT Stylesheet Source

```xml
<xsl:stylesheet
    xmlns:ns3="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/SBM/SBMPremiumNonVoiceRequest.xsd"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="globalVariables"/>
  <xsl:template match="/">
    <createEvent><event>
      <xsl:if test="$orderRequest/OrderPriority">
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority></xsl:if>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID></xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderID">
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID></xsl:if>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
        <RefID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></RefID></xsl:if>
      <xsl:if test="$globalVariables/OMX_OM/Rules/.../IsEnableUserPass='true'">
        <xsl:if test="$orderRequest/OrderData/User"><UserName>...</UserName></xsl:if>
        <xsl:if test="$orderRequest/OrderData/Password"><PassWord>...</PassWord></xsl:if>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderType">
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType></xsl:if>
      <payload>
        <ns3:doServiceRequest><ns3:req>
          <ns3:async_url>-</ns3:async_url>
          <ns3:byPassMode>0</ns3:byPassMode>
          <xsl:choose>
            <xsl:when test="exists($orderRequest/OrderData/ExtendedInfo[Name='SBM_CHANNEL']/Value)">
              <xsl:if test="$orderRequest/OrderData/ExtendedInfo[Name='SBM_CHANNEL']/Value">
                <ns3:channel><xsl:value-of select="$orderRequest/OrderData/ExtendedInfo[Name='SBM_CHANNEL']/Value"/></ns3:channel>
              </xsl:if>
            </xsl:when>
            <xsl:otherwise><ns3:channel>OMX</ns3:channel></xsl:otherwise>
          </xsl:choose>
          <ns3:extra_xml>-</ns3:extra_xml>
          <ns3:function_id>102500014</ns3:function_id>
          <ns3:host>-</ns3:host>
          <ns3:parameters><ns3:item>
            <ns3:key>refId</ns3:key>
            <ns3:value><xsl:value-of select="$orderRequest/OrderData/ExtendedInfo[Name='REF_ID_DEALER_BALANCE']/Value"/></ns3:value>
          </ns3:item></ns3:parameters>
          <xsl:if test="$orderRequest/OrderData/OrderID">
            <ns3:req_transaction_id><xsl:value-of select="$orderRequest/OrderData/OrderID"/></ns3:req_transaction_id>
          </xsl:if>
          <xsl:if test="$orderRequest/OrderData/ExtendedInfo[Name='DEALER_MOBILE_NO']/Value">
            <ns3:service_no><xsl:value-of select="$orderRequest/OrderData/ExtendedInfo[Name='DEALER_MOBILE_NO']/Value"/></ns3:service_no>
          </xsl:if>
          <ns3:waiting_mode>0</ns3:waiting_mode>
        </ns3:req></ns3:doServiceRequest>
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
    ├── JMSPriority          ← $orderRequest/OrderPriority                              [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId                   [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                          [Conditional]
    ├── RefID                ← $orderRequest/OrderData/OMXTrackingId                   [Conditional]
    ├── UserName             ← $orderRequest/OrderData/User                             [Credential-gated: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password                         [Credential-gated: IsEnableUserPass='true']
    ├── OrderType            ← $orderRequest/OrderData/OrderType                        [Conditional]
    └── payload                                                                          [Always]
        └── ns3:doServiceRequest                                                         [Always]
            └── ns3:req                                                                  [Always]
                ├── ns3:async_url        ← "-"                                           [Always]
                ├── ns3:byPassMode       ← 0                                             [Always]
                ├── ns3:channel          ← ExtendedInfo[Name="SBM_CHANNEL"]/Value        [Conditional: xsl:choose; else "OMX"]
                ├── ns3:extra_xml        ← "-"                                           [Always]
                ├── ns3:function_id      ← "102500014"                                  [Always]
                ├── ns3:host             ← "-"                                           [Always]
                ├── ns3:parameters                                                       [Always]
                │   └── ns3:item                                                         [Always]
                │       ├── ns3:key      ← "refId"                                       [Always]
                │       └── ns3:value    ← ExtendedInfo[Name="REF_ID_DEALER_BALANCE"]/Value  [Always]
                ├── ns3:req_transaction_id ← $orderRequest/OrderData/OrderID             [Conditional]
                ├── ns3:service_no       ← ExtendedInfo[Name="DEALER_MOBILE_NO"]/Value   [Conditional]
                └── ns3:waiting_mode     ← "0"                                           [Always]
```

---

## §11 — Audit Logging

| Event | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE | Payload | Gated? |
|-------|-----------|----------------|------------|---------|--------|
| Request sent | `pid + "_REQ"` | `"SBM_CANCEL_PREMIUM_NON_VOICE"` | "Request Sent for SBM_CANCEL_PREMIUM_NON_VOICE" | reqEvent (if WritePayload=true) | No |
| Response received | `pid + "_RES"` | `"SBM_CANCEL_PREMIUM_NON_VOICE"` | "Response received for SBM_CANCEL_PREMIUM_NON_VOICE" | eventResponse (if WritePayload=true) | No |

Both logs use `TARGET_SYSTEM = $globalVariables/OMX_COMMON/Component_Name/OMX_FM`. Unlike OMXOM rules, these are NOT gated by `AllowWriteLog`.

---

## §12 — Activity Status Management

| Outcome | Activity status | Mechanism |
|---------|----------------|-----------|
| PreExecCheck false | SKIPPED | `SkipActivity("4")` |
| Request sent | IN_PROGRESS (code "1") | `GetActivityStatusString("1", false)` |
| Response fan-in complete | COMPLETED (via NextActivity in response handler) | `IntraActivitySequencing.ActionResponseEvent` returns true |
| Exception | FAILED | `HandleActivityException` |

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
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(act)` | void | Clears stale pending requests on resubmit |
| `Instance.getByExtIdByUri(extId, uri)` | Concept | Fetches nextAct for PreExecCheck read |
| `Instance.serializeUsingDefaults(orderRequest)` | String (XML) | Serialises order for PreExecCheck |
| `XPath.execute(chkXPath, sXML, ns)` | String | PreExecCheck evaluation |
| `Event.assertEvent(reqEvent)` | void | Asserts SBM request event into working memory |
| `IntraActivitySequencing.ActionRequestEvent(reqEvent, act)` | void | Registers request with sequencer |
| `IntraActivitySequencing.SendFirstRequestEvent(act)` | void | Dispatches first pending request via JMS |
| `RuleFunctions.Helpers.GetActivityStatusString("1", false)` | String | Maps "1" to IN_PROGRESS |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | void | Persists order to DB |
| `RuleFunctions.Helpers.SkipActivity(req, act, "4")` | void | Skips activity if PreExecCheck false |
| `RuleFunctions.Helpers.HandleActivityException(req, act, ae, "")` | void | Generic exception handler |

---

## §15 — Function Dependency Tree

```text
Request_SBM_CANCEL_PREMIUM_NON_VOICE (rule)
├── [RESUBMIT CHECK]
│   └── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(act)  [helper]
├── Instance.getByExtIdByUri(NextActivityName, "/Concepts/...")           [BE built-in]
├── Instance.serializeUsingDefaults(orderRequest)                        [BE built-in]
├── XPath.execute(PreExecCheck, sXML)                                    [BE built-in]
├── [IF chkRes == "true"]
│   ├── Event.createEvent("xslt://SBM_PREMIUM_NON_VOICE")                [BE built-in — §9.8 XSLT]
│   ├── Event.assertEvent(reqEvent)                                      [BE built-in]
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, act)       [helper]
│   ├── Event.Ext.sendEventImmediate(Logger — request audit)             [BE built-in]
│   ├── IntraActivitySequencing.SendFirstRequestEvent(act)              [helper]
│   ├── RuleFunctions.Helpers.GetActivityStatusString("1", false)       [helper]
│   └── RuleFunctions.Helpers.SendDataToDB(orderRequest)                [helper]
├── [ELSE — isSkipped]
│   └── RuleFunctions.Helpers.SkipActivity(req, act, "4")              [helper]
└── RuleFunctions.Helpers.HandleActivityException(...)                  [helper — catch]

Response_SBM_CANCEL_PREMIUM_NON_VOICE (rulefunction — §19)
├── Instance.createInstance("xslt://ResponseBase")                      [BE built-in]
├── currActivity.Response[length] = activityRes                         [array append]
├── Event.Ext.sendEventImmediate(Logger — response audit)               [BE built-in]
└── IntraActivitySequencing.ActionResponseEvent(currActivity)           [helper — fan-in]
    └── returns "true" when all responses received → NextActivity called
```

---

## §16 — Concept Definitions Referenced

| Field | Type | Role |
|-------|------|------|
| `orderRequest.OrderData.ExtendedInfo[Name="SBM_CHANNEL"]` | ExtendedInfo | Optional SBM channel override |
| `orderRequest.OrderData.ExtendedInfo[Name="REF_ID_DEALER_BALANCE"]` | ExtendedInfo | Dealer balance reference ID |
| `orderRequest.OrderData.ExtendedInfo[Name="DEALER_MOBILE_NO"]` | ExtendedInfo | Dealer mobile number (service_no) |
| `orderCurrentActivity.RequestCount` | int | Resubmit detection |
| `currActivity.Response[]` | Array of ResponseBase | SBM response appended by response rulefunction |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | Cancel outstanding premium non-voice dealer balance in SBM during prepaid cancellation |
| R2 | Pass dealer balance reference ID and dealer mobile number to SBM |
| R3 | Support SBM channel override via `SBM_CHANNEL` ExtendedInfo; default to "OMX" |
| R4 | Support order resubmit by purging pending requests before resending |
| R5 | Send audit logs for both request and response (no AllowWriteLog gate) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `function_id = "102500014"` is hardcoded — SBM change requires redeployment | [MEDIUM] | Move to GlobalVar or ProcessConfig Parameter |
| `REF_ID_DEALER_BALANCE` always present in params even if empty — SBM may accept/reject empty refId silently | [MEDIUM] | Add `xsl:if` guard around the item; verify SBM behaviour |
| SBM channel `xsl:choose` has redundant double-check (`exists()` + `xsl:if`) — may omit element if value is empty string despite key existing | [LOW] | Simplify to `xsl:when test="... and Value != ''"` |
| No author in doc comment | [LOW] | Add author attribution |

---

## §18 — Full Source Code

```java
/**
 * @description
 */
rule Rules.OMConsumers.OMXFM.Request.Request_SBM_CANCEL_PREMIUM_NON_VOICE {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "SBM_CANCEL_PREMIUM_NON_VOICE";
        orderRequest.ProcessFlow.NextActivityID == "SBM_CANCEL_PREMIUM_NON_VOICE";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
                orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
            String chkXPath = nextAct.PreExecCheck;
            String chkRes = "true";
            boolean isSkipped = true;

            if(isActResub) {
                RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
            }
            if(String.length(chkXPath) > 0) {
                String sXML = Instance.serializeUsingDefaults(orderRequest);
                chkRes = XPath.execute("/("+chkXPath+")", sXML,
                    "ns0=www.tibco.com/be/ontology/Concepts/OrderRequest/OrderRequest");
            }
            if(String.equals(chkRes, "true")) {
                Events.OMConsumers.OMXFM.Request.SBM_PREMIUM_NON_VOICE reqEvent =
                    Event.createEvent(/* §9.8: ns3:doServiceRequest with function_id=102500014,
                        SBM_CHANNEL (or "OMX"), REF_ID_DEALER_BALANCE refId, DEALER_MOBILE_NO service_no */);
                Event.assertEvent(reqEvent);
                RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                isSkipped = false;
                long pid = System.nanoTime();
                Event.Ext.sendEventImmediate(Event.createEvent(
                    /* Logger: PROCESS_ID=pid+"_REQ", OPERATION_NAME="SBM_CANCEL_PREMIUM_NON_VOICE",
                       AUDIT_TRACE="Request Sent for SBM_CANCEL_PREMIUM_NON_VOICE",
                       payload=reqEvent (if WritePayload=true) */));
            }
            if (!isSkipped) {
                RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
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

`Response_SBM_CANCEL_PREMIUM_NON_VOICE` handles the asynchronous SBM reply. It parses the response event, creates a ResponseBase concept, appends it to the activity's Response array, emits a response audit log, and checks fan-in completion via `IntraActivitySequencing.ActionResponseEvent`.

> Since SBM_CANCEL_PREMIUM_NON_VOICE sends a single request per order, fan-in completes on the first (and only) response.

### §19.2 Scope Variables

| Variable | Type path | Role |
|----------|----------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Root order — correlation and audit log |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.SBM_PREMIUM_NON_VOICE | Inbound SBM response event |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Current activity — Response array appended |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId             ← OMXUtils:generateTrackingID()          [Always]
    ├── ResponseCode       ← $eventResponse/ResponseCode             [Conditional]
    ├── ResponseMessage    ← $eventResponse/ResponseMsg              [Conditional] (source field is "ResponseMsg" not "ResponseMessage")
    ├── CompletionStatus   ← $eventResponse/CompletionStatus         [Conditional]
    └── ReferenceId        ← $eventResponse/RefID                    [Conditional]
```

### §19.4 Response Completion Logic

| Item | Detail |
|------|--------|
| Fan-in method | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Returns "true" when | All expected responses received (one for this FM) |
| On "true" | Rulefunction returns "true"; caller advances to NextActivity |
| Success code check | None — no `tib:right(ResponseCode,3)="000"` check; fan-in by count only |

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(pid, "_RES")` |
| OPERATION_NAME | `"SBM_CANCEL_PREMIUM_NON_VOICE"` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `"Response received for SBM_CANCEL_PREMIUM_NON_VOICE"` |
| payload | `eventResponse` (if WritePayload=true) |

### §19.6 Response XSLT Source — ResponseBase

```xml
<xsl:stylesheet xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject><object>
      <xsl:attribute name="extId">
        <xsl:value-of select="OMXUtils:generateTrackingID()"/>
      </xsl:attribute>
      <xsl:if test="$eventResponse/ResponseCode">
        <ResponseCode><xsl:value-of select="$eventResponse/ResponseCode"/></ResponseCode>
      </xsl:if>
      <xsl:if test="$eventResponse/ResponseMsg">
        <ResponseMessage><xsl:value-of select="$eventResponse/ResponseMsg"/></ResponseMessage>
      </xsl:if>
      <xsl:if test="$eventResponse/CompletionStatus">
        <CompletionStatus><xsl:value-of select="$eventResponse/CompletionStatus"/></CompletionStatus>
      </xsl:if>
      <xsl:if test="$eventResponse/RefID">
        <ReferenceId><xsl:value-of select="$eventResponse/RefID"/></ReferenceId>
      </xsl:if>
    </object></createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
