# Request_IOM_CHECK_SEQUENCING

> External OMXFM — IOM Sequencing Gate · Sequencing.xsd

**Priority:** 5 | **forwardChain:** true | **Backend:** IOM (Integration Order Manager) | **Author:** CHAYATORN-PC

---

## §1 — Overview & Purpose

`IOM_CHECK_SEQUENCING` is an External OMXFM rule that acts as an **order sequencing gate**.
Before executing downstream activities, it asks IOM (Integration Order Manager) whether this order is cleared to proceed in sequence with other in-flight orders affecting the same MSISDN. If IOM returns `accept`, the order continues. If IOM returns a non-accept status, the activity remains `IN_PROGRESS` and the order waits.

> **⚡ Unique Architectural Pattern**
> Unlike all other OMXFM rules that evaluate their *own* PreExecCheck, IOM_CHECK_SEQUENCING reads the **next activity's** PreExecCheck (`orderRequest.ProcessFlow.NextActivityName`) to determine whether each subscriber actually needs to be sequenced. If the next activity would be skipped for a subscriber, no sequencing request is sent for that subscriber.

| Property | Value |
|----------|-------|
| Rule class | `Rules.OMConsumers.OMXFM.Request.Request_IOM_CHECK_SEQUENCING` |
| Backend System | IOM — Integration Order Manager (sequencing service) |
| Integration type | JMS / Async via `/Channels/OMXFMConnectionRequest` |
| JMS Destination | `IOM_CHECK_SEQUENCING` |
| Request schema | `SequencingRequest` — `Sequencing.xsd` (ns1 / xsd2) |
| Response schema | `SequencingResponse` — `Sequencing.xsd` |
| Completion trigger | `SequencingResponse/status = "accept"` |
| IntraActivitySequencing | None |
| Send method | `sendEventImmediate` (no `routeToImmediate`) |
| Skip code | `SkipActivity("4")` when no subscribers require sequencing |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule Name | `Request_IOM_CHECK_SEQUENCING` | External OMXFM request rule |
| Namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Priority | 5 | Standard OMXFM priority |
| forwardChain | true | Triggers further rule evaluation on WM changes |
| Author | CHAYATORN-PC | |
| Rule type | OMXFM External | Async JMS; awaits IOM response before completing |
| Dead code | Large commented-out CRM_CREATE_UPDATE_SR XSLT block (~line 109) | Legacy artefact — safe to remove |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Main order payload — ProcessFlow, OrderData, subscriber lists |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity state — ActivityID = IOM_CHECK_SEQUENCING |
| `nextAct` | `Concepts.OM.ProcessConfig.Activity` | Next activity in the flow; read to get its PreExecCheck |
| `globalVariables` | `Concepts.GlobalVariables` | System_Name, WritePayload flag, component names |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderRequest.ProcessFlow.CurrentActivityID == "IOM_CHECK_SEQUENCING"` | Route to this rule only |
| 2 | `currActivity.ActivityID == "IOM_CHECK_SEQUENCING"` | Confirm matching activity object |
| 3 | `currActivity.Status != "IN_PROGRESS"` | Prevent duplicate request sends |
| 4 | `orderRequest exists in WM` | Standard existence guard |

> **Note:** The reqSuccess guard (`Response[].ReferenceId == subRefId && CompletionStatus == 2`) prevents sending duplicate requests per subscriber when the response rulefunction fires in fanout.

---

## §5 — Execution Flow Diagram

```
1. Resolve next activity PreExecCheck
   → Instance.getByExtIdByUri(NextActivityName) → nextAct.PreExecCheck

2. ParentOU subscriber loop
   → For each ParentOU subscriber:
     a. RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, pSubRefId)
     b. XPath.execute("/(" + chkXPath + ")", sXML) → "true"/"false"
     c. If "true" and no prior success: build ns1:SequencingRequest, sendEventImmediate
     d. currActivity.RequestCount++

3. ChildOU subscriber loop
   → Same as step 2 using $cSubRefId / $csub/MSISDN

4. Status branch
   → If RequestCount > 0: set IN_PROGRESS + audit log
   → If RequestCount == 0: SkipActivity("4")

5. Await IOM response
   → Response_IOM_CHECK_SEQUENCING.rulefunction handles reply
   → Checks SequencingResponse/status = "accept"
```

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

| Step | Action | Detail |
|------|--------|--------|
| 1 | Fetch next activity | `Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")` |
| 2 | Extract PreExecCheck XPath | `String chkXPath = nextAct.PreExecCheck` |
| 3 | ParentOU subscriber loop | Iterate orderRequest.ParentOU.Subscriber[] |
| 3a | Get subscriber XML | `RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, pSubRefId)` |
| 3b | Evaluate next activity PreExecCheck | `XPath.execute("/(" + chkXPath + ")", sXML, "ns0=...")` |
| 3c | Guard: reqSuccess check | Skip if subscriber already has a successful response |
| 3d | Build & send SequencingRequest | XSLT with ns1 prefix; sequenceId=concat("MOBILE-",MSISDN) |
| 3e | Increment request count | `currActivity.RequestCount++` |
| 4 | ChildOU subscriber loop | Same as steps 3a–3e using $cSubRefId / $csub/MSISDN |
| 5 | Status branch | If requestCount > 0: set IN_PROGRESS + audit log. Else: SkipActivity("4"). |

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

IOM_CHECK_SEQUENCING is the **entry point** of the PREPAID_ADD_OFFER process (step 1). It applies to all PREPAID_ADD_OFFER order types — the actual gating depends dynamically on the next activity's PreExecCheck XPath evaluated per subscriber.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Protocol | Purpose |
|-----------|---------|-------------|----------|---------|
| [OUTBOUND] | `/Channels/OMXFMConnectionRequest` | `IOM_CHECK_SEQUENCING` | JMS | Send SequencingRequest to IOM |
| [INBOUND] | OMXFMConnectionResponse (implied) | IOM_CHECK_SEQUENCING response | JMS | Receive SequencingResponse from IOM |

### §8.3 Backend API Details

| System | Operation | Schema | Correlation |
|--------|-----------|--------|-------------|
| IOM (Integration Order Manager) | Sequence check (action="sequence") | `SequencingRequest / SequencingResponse` — Sequencing.xsd | RefID matched in response; fan-in on RequestCount == successResponseCount |

### §8.4 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `orderRequest.ProcessFlow.NextActivityName` | READ | Used to look up the next activity's concept |
| `nextAct.PreExecCheck` | READ | XPath string from next activity; evaluated per subscriber |
| `orderRequest.OrderData.OMXTrackingId` | READ | trackingId = substring-after(OMXTrackingId, '-') |
| `orderRequest.OrderData.OrderID` | READ | ns1:info[orderId] |
| `orderRequest.OrderData.OrderType` | READ | ns1:info[orderType] |
| `orderRequest.OrderData.CreateDate` | READ | ns1:info[created] — conditional (if exists) |
| `subscriber.MSISDN` | READ | sequenceId = concat("MOBILE-", MSISDN) |
| `currActivity.RequestCount` | WRITE | Incremented per sequencing request sent |
| `currActivity.Status` | WRITE | Set to IN_PROGRESS |
| `globalVariables/OMX_COMMON/System_Name` | READ | ns1:info[envName] |

### §8.6 Global Variable Dependencies

| Global Variable | Used For |
|-----------------|----------|
| `$globalVariables/OMX_COMMON/System_Name` | envName info element |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit log COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit log TARGET_SYSTEM |
| `$globalVariables/OMX_OM/WritePayload` | Gate for payload logging |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |

---

## §9 — Detailed Payload Build (XSLT Decomposition)

### §9.1 XSLT Parameter Binding

| Parameter | Bound from |
|-----------|-----------|
| `$orderRequest` | OrderRequest WM concept |
| `$psub` | ParentOU subscriber (current loop element) |
| `$csub` | ChildOU subscriber (ChildOU variant) |
| `$pSubRefId` | ParentOU subscriber reference ID |
| `$cSubRefId` | ChildOU subscriber reference ID |
| `$globalVariables` | Global BE variables concept |

### §9.4 Payload Root Element

```xml
<ns1:SequencingRequest xmlns:ns1="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/IOM/Sequencing.xsd">
  <ns1:action>sequence</ns1:action>                      <!-- Static: always "sequence" -->
  <ns1:sequenceId>MOBILE-{MSISDN}</ns1:sequenceId>       <!-- concat("MOBILE-", MSISDN) -->
  <ns1:trackingId>{partial OMXTrackingId}</ns1:trackingId> <!-- substring-after(OMXTrackingId, '-') -->
  <ns1:system>OMX</ns1:system>                            <!-- Static: always "OMX" -->
  <ns1:info name="orderId">{OrderID}</ns1:info>
  <ns1:info name="orderType">{OrderType}</ns1:info>
  <ns1:info name="created">{CreateDate}</ns1:info>        <!-- xsl:if: only if CreateDate exists -->
  <ns1:info name="currentTrackingId">{OMXTrackingId}</ns1:info>
  <ns1:info name="refId">{pSubRefId or cSubRefId}</ns1:info>
  <ns1:info name="envName">{System_Name}</ns1:info>
</ns1:SequencingRequest>
```

### §9.7 Complete Generated XML Example

```xml
<ns1:SequencingRequest xmlns:ns1="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/IOM/Sequencing.xsd">
  <ns1:action>sequence</ns1:action>
  <ns1:sequenceId>MOBILE-0812345678</ns1:sequenceId>
  <ns1:trackingId>20250719100000000</ns1:trackingId>
  <ns1:system>OMX</ns1:system>
  <ns1:info name="orderId">ORD-20250719-001</ns1:info>
  <ns1:info name="orderType">51</ns1:info>
  <ns1:info name="created">2025-07-19T10:00:00</ns1:info>
  <ns1:info name="currentTrackingId">OMX-20250719100000000</ns1:info>
  <ns1:info name="refId">SUB-001-PARENT</ns1:info>
  <ns1:info name="envName">OMX-PROD</ns1:info>
</ns1:SequencingRequest>
```

### §9.8 XSLT Stylesheet Source

Two variants exist: **ParentOU Variant ①** (`$pSubRefId` / `$psub/MSISDN`) and **ChildOU Variant ②** (`$cSubRefId` / `$csub/MSISDN`). Structure is identical; only RefID and MSISDN source differ.

```xml
<!-- ParentOU Variant ① -->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ns1="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/IOM/Sequencing.xsd"
    version="1.0" exclude-result-prefixes="xsl">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>   <!-- OrderRequest WM concept -->
  <xsl:param name="psub"/>           <!-- ParentOU subscriber element -->
  <xsl:param name="pSubRefId"/>      <!-- ParentOU subscriber RefID -->
  <xsl:param name="globalVariables"/>

  <xsl:template match="/">
    <createEvent>
      <event>
        <payload>
          <ns1:SequencingRequest>
            <ns1:action>sequence</ns1:action>
            <ns1:sequenceId>
              <xsl:value-of select="concat('MOBILE-', $psub/MSISDN)"/>
            </ns1:sequenceId>
            <ns1:trackingId>
              <xsl:value-of select="substring-after($orderRequest/OrderData/OMXTrackingId, '-')"/>
            </ns1:trackingId>
            <ns1:system>OMX</ns1:system>
            <ns1:info name="orderId">
              <xsl:value-of select="$orderRequest/OrderData/OrderID"/>
            </ns1:info>
            <ns1:info name="orderType">
              <xsl:value-of select="$orderRequest/OrderData/OrderType"/>
            </ns1:info>
            <xsl:if test="$orderRequest/OrderData/CreateDate">
              <ns1:info name="created">
                <xsl:value-of select="$orderRequest/OrderData/CreateDate"/>
              </ns1:info>
            </xsl:if>
            <ns1:info name="currentTrackingId">
              <xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/>
            </ns1:info>
            <ns1:info name="refId">
              <xsl:value-of select="$pSubRefId"/>
            </ns1:info>
            <ns1:info name="envName">
              <xsl:value-of select="$globalVariables/OMX_COMMON/System_Name"/>
            </ns1:info>
          </ns1:SequencingRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>

<!-- ChildOU Variant ②: replace $psub → $csub, $pSubRefId → $cSubRefId -->
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    └── payload
        └── ns1:SequencingRequest  [xmlns:ns1="…/IOM/Sequencing.xsd"]
            ├── ns1:action              ← "sequence" (static)              [Always]
            ├── ns1:sequenceId          ← concat("MOBILE-", $psub/MSISDN)  [Always]
            ├── ns1:trackingId          ← substring-after(OMXTrackingId, '-')  [Always]
            ├── ns1:system              ← "OMX" (static)                   [Always]
            ├── ns1:info[orderId]       ← $orderRequest/OrderData/OrderID  [Always]
            ├── ns1:info[orderType]     ← $orderRequest/OrderData/OrderType [Always]
            ├── ns1:info[created]       ← $orderRequest/OrderData/CreateDate
            │                           [Conditional: CreateDate exists]
            ├── ns1:info[currentTrackingId] ← $orderRequest/OrderData/OMXTrackingId [Always]
            ├── ns1:info[refId]         ← $pSubRefId (ParentOU) / $cSubRefId (ChildOU) [Always]
            └── ns1:info[envName]       ← $globalVariables/OMX_COMMON/System_Name [Always]
```

**Legend:** `[Always]` = unconditionally emitted · `[Conditional: ...]` = inside xsl:if · green = XPath source · orange = static literal

---

## §11 — Audit Logging

| Phase | AUDIT_TRACE | Condition |
|-------|-------------|-----------|
| Request sent | `Request Sent for IOM_CHECK_SEQUENCING` | When at least one request is emitted (fixed string, not per-subscriber) |
| Response received | `Response received for IOM_CHECK_SEQUENCING` | When RequestCount == successResponseCount (fan-in complete) |
| Waiting (dead code) | `Response received for IOM_CHECK_SEQUENCING` | Commented-out "waiting_sequencing" logger — never emitted |

> **Note:** The request audit log emits once for the entire activity, not once per subscriber.

---

## §12 — Activity Status Management

| Condition | Status | Next Step |
|-----------|--------|-----------|
| One or more sequencing requests sent | `IN_PROGRESS` | Wait for IOM response; fan-in completion drives forward |
| No requests sent (all subscribers skipped) | `SKIPPED` | `SkipActivity("4")` — move to next activity |
| All responses received, status = accept | `COMPLETED` | Return "true" — order proceeds |
| All responses received, status ≠ accept | `WAITING` | Return "false" — IOM sequencing still pending |

---

## §14 — Helper Functions Reference

| Function | Return Type | Purpose |
|----------|-------------|---------|
| `RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, subRefId)` | String (XML) | Returns XML snapshot for a single subscriber — used to evaluate XPath expressions in subscriber scope |
| `Instance.getByExtIdByUri(extId, conceptURI)` | Concept | Retrieves an Activity concept from WM by extId — used to look up the next activity |
| `XPath.execute(expr, xml, nsContext)` | String | Evaluates an XPath expression against a raw XML string — returns "true"/"false" for boolean expressions |
| `OMXUtils.generateTrackingID()` | String | Generates a unique extId for ResponseBase instances |

---

## §15 — Function Dependency Tree

```text
Request_IOM_CHECK_SEQUENCING (rule)
├── Instance.getByExtIdByUri()            [resolve next activity concept]
├── RuleFunctions.Helpers.GetXMLForSubscriber()  [subscriber XML snapshot]
├── XPath.execute()                       [evaluate next activity PreExecCheck]
├── Event.createEvent(xslt://...)         [build SequencingRequest event]
│   └── XSLT: ns1:SequencingRequest
│       ├── concat()                      [MOBILE- + MSISDN]
│       └── substring-after()            [strip OMX- prefix from trackingId]
└── Event.Ext.sendEventImmediate()        [dispatch JMS to IOM]

Response_IOM_CHECK_SEQUENCING (rulefunction)
├── Instance.createInstance(xslt://...)   [create ResponseBase concept]
├── XPath.evalAsInt()                     [count successful responses]
│   └── count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)="000"])
├── XPath.evalAsBoolean()                 [check SequencingResponse/status = "accept"]
└── Event.Ext.sendEventImmediate()        [emit response audit log]
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | Must evaluate the *next activity's* PreExecCheck per subscriber before sending sequencing call | [HIGH] |
| R2 | sequenceId MUST be formatted as `MOBILE-{MSISDN}` — IOM uses this as the sequence key | [HIGH] |
| R3 | trackingId MUST strip "OMX-" prefix from OMXTrackingId (`substring-after(..., '-')`) | [HIGH] |
| R4 | Completion MUST check `SequencingResponse/status = "accept"` — not just a 000 response code | [HIGH] |
| R5 | If no subscribers require sequencing, the activity MUST be skipped with code "4" | [MEDIUM] |
| R6 | Dead commented-out CRM_CREATE_UPDATE_SR XSLT block should be removed during migration | [LOW] |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Dynamic PreExecCheck evaluation — runtime XPath injection risk | [HIGH] | Use static mapping or compile XPath at load time; validate from DB/config |
| IOM sequencing timeout — if IOM never returns "accept", order stuck IN_PROGRESS | [HIGH] | Implement timeout/retry; consider IOM circuit-breaker pattern |
| Single audit log for entire activity — insufficient per-subscriber observability | [MEDIUM] | Emit per-subscriber structured logs in modern service |
| Non-accept path has no visibility (waiting_sequencing logger commented out) | [MEDIUM] | Implement explicit waiting-state monitoring in replacement |

---

## §18 — Full Source Code (Request Rule)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_IOM_CHECK_SEQUENCING {
  attribute {
    priority = 5;
    forwardChain = true;
  }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity currActivity;
  }
  when {
    // orderRequest.ProcessFlow.CurrentActivityID == "IOM_CHECK_SEQUENCING"
    // currActivity.ActivityID == "IOM_CHECK_SEQUENCING"
    // currActivity.Status != "IN_PROGRESS"
  }
  then {
    // 1. Resolve NEXT activity and its PreExecCheck
    Concepts.OM.ProcessConfig.Activity nextAct =
        Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName,
            "/Concepts/OM/ProcessConfig/Activity");
    String chkXPath = nextAct.PreExecCheck;

    // 2. ParentOU subscriber loop
    int pLen = orderRequest.ParentOU.Subscriber@length;
    for(int i = 0; i < pLen; i++) {
        String pSubRefId = orderRequest.ParentOU.Subscriber[i].RefId;
        // reqSuccess guard: skip if response already received
        String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, pSubRefId);
        String chkRes = XPath.execute("/(" + chkXPath + ")", sXML, "ns0=...");
        if(chkRes.equals("true")) {
            Event.Ext.sendEventImmediate(Event.createEvent(
                "xslt://{{/Events/OMConsumers/OMXFM/Request/IOM_CHECK_SEQUENCING}}"
                /* XSLT: ns1:SequencingRequest — see §9.8 ParentOU Variant ①
                   Outputs: action="sequence", sequenceId=concat("MOBILE-",MSISDN),
                   trackingId=substring-after(OMXTrackingId,'-'), system="OMX",
                   info[orderId,orderType,created?,currentTrackingId,refId,envName] */
            ));
            currActivity.RequestCount++;
        }
    }

    // 3. ChildOU subscriber loop (identical; $cSubRefId / $csub — see §9.8 Variant ②)

    // 4. Set activity status
    if(currActivity.RequestCount > 0) {
        currActivity.Status = GetActivityStatusString("IN_PROGRESS");
        // AUDIT_TRACE: "Request Sent for IOM_CHECK_SEQUENCING"
    } else {
        SkipActivity("4");
    }

    /* DEAD CODE (~line 109): Large commented-out CRM_CREATE_UPDATE_SR XSLT block
       — legacy artefact, safe to remove */
  }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

`Response_IOM_CHECK_SEQUENCING.rulefunction` handles the asynchronous JMS reply from IOM.
It parses the `SequencingResponse` payload, updates the activity's response array, and determines whether the sequencing gate has been cleared. It returns `"true"` only when *all* subscribers have received successful responses AND IOM's status is `"accept"`. Non-accept responses cause the activity to remain IN_PROGRESS — the order waits.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Main order object — activities array updated |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.IOM_CHECK_SEQUENCING` | JMS response event from IOM |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity state — Response[] array, RequestCount |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object  @extId ← OMXUtils.generateTrackingID()   [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode    [Conditional: field exists]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg     [Conditional: field exists]
    ├── CompletionStatus ← $eventResponse/CompletionStatus [Conditional: field exists]
    └── ReferenceId      ← $eventResponse/RefID           [Conditional: field exists]
```

After creation: `currActivity.Response[n] = activityRes`, `currActivity.ResponseCode = eventResponse.ResponseCode`, `currActivity.ResponseMessage = eventResponse.ResponseMsg`.

### §19.4 Response Completion Logic

**Step 1 — Update RequestCount sync:**
Loop over `orderRequest.ProcessFlow.Activities[]` where `ActivityID == "IOM_CHECK_SEQUENCING"` and sync `RequestCount = currActivity.Response@length`.

**Step 2 — Count successes:**
```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```
A response is "successful" when the last 3 chars of its ResponseCode are "000".

**Step 3 — Fan-in check:**
```
if (currActivity.RequestCount == successResponseCount)
  → check: $eventResponse/payload/xsd2:SequencingResponse/xsd2:status = "accept"
    → "accept"  → return "true"  (order cleared to proceed)
    → other     → return "false" (IOM sequencing still pending)
else
  → return "false"
```

> **Key difference from other OMXFM rules:** IOM_CHECK_SEQUENCING has a *two-tier* completion check:
> first the normal fan-in (`RequestCount == successResponseCount`), then the IOM-specific semantic check
> (`status = "accept"`). Even with all 000 response codes, a non-accept status keeps the order waiting.

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| PROCESS_ID | `concat($pid, "_RES")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `"IOM_CHECK_SEQUENCING"` (static) |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `"Response received for IOM_CHECK_SEQUENCING"` (static) |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | Copy of $eventResponse — gated on `WritePayload = "true"` |

> **Warning:** The "waiting_sequencing" audit log is fully commented out. Non-accept responses are silently handled — no observability into orders waiting for IOM clearance.

### §19.6 Response XSLT Source (ResponseBase)

```xml
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ns="www.tibco.com/be/custom/OMXUtils"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    version="1.0">
  <xsl:output method="xml"/>
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId">
          <xsl:value-of select="ns:generateTrackingID()"/>
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
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
