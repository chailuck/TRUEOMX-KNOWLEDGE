# Request_CCBS_GET_SUBS_LIST

> Retrieves subscriber lists for ParentOU and ChildOU nodes via CCBS GetSubscriberList API

**System:** CCBS | **Priority:** 5 | **Author:** awalia-t420 | **Pattern:** Dual-loop POU/COU + isSkipped tracking | **Fan-in:** ActionResponseEvent | **Generated:** 2026-09-15

---

## §1 Overview & Purpose

This rule sends **CCBS_GET_SUBS_LIST** requests to retrieve subscriber header lists for each Organizational Unit (OU) in the order. It iterates over two levels of OU hierarchy: **ParentOU** (outer loop) and **ChildOU within each POU** (inner loop). For each OU not already successfully processed, it builds a `ns:GetSubscriberListRequest` payload with the OU's `OUId` as the `chNodeId`, fixed subtree flag (89 = Yes), and page number 0.

The response handler parses the returned `SubscriberHeaderList`, creates `Subscriber` concept instances for each entry with status=65 (Active), and appends them to the matching POU or COU node. Fan-in completion is managed by `IntraActivitySequencing.ActionResponseEvent`.

| Attribute | Value |
|-----------|-------|
| Rule File | `Request_CCBS_GET_SUBS_LIST.rule` |
| Response File | `Response_CCBS_GET_SUBS_LIST.rulefunction` |
| Author | awalia-t420 |
| Priority | 5 |
| Forward Chain | true |
| Target System | CCBS |
| Loop Structure | Outer: ParentOU; Inner: ChildOU per POU |
| Skip Pattern | CompletionStatus==2 per-OU; isSkipped tracking |
| Fan-in | IntraActivitySequencing.ActionResponseEvent |

---

## §2 Rule Metadata & Attributes

| Field | Value | Notes |
|-------|-------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_SUBS_LIST` | Full qualified name |
| priority | 5 | Standard OMXFM request priority |
| forwardChain | true | Triggers re-evaluation after assertions |
| ActivityID match | `CCBS_GET_SUBS_LIST` | Both extId and ProcessFlow.NextActivityID |
| Status trigger | WAITING | Rule fires only when activity is in WAITING state |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order data including Customer, ParentOU[], ChildOU[] |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity; holds RequestCount, Response[], PreExecCheck, Status |

---

## §4 Rule Conditions (WHEN)

| Condition | Purpose |
|-----------|---------|
| `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches the current activity to the process flow pointer |
| `orderCurrentActivity.ActivityID == "CCBS_GET_SUBS_LIST"` | Ensures this rule handles only this specific FM |
| `orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_SUBS_LIST"` | Double-checks process flow alignment |
| `orderCurrentActivity.Status == "WAITING"` | Prevents re-firing after activity completes |

---

## §5 Execution Flow Diagram

```
1. PurgePendingRequestsBeforeResubmit → if resubmit (RequestCount>0 && IsOrderResubmitted)
2. Init isSkipped=true
3. Outer POU loop (i=0..iPOULen-1)
4.   POU CompletionStatus==2 skip check → skip OU if already succeeded
5.   POU PreExecCheck gate → GetXMLForOU(orderRequest, refId) → skip if gate=false
6.   Build + assertEvent POU variant → ActionRequestEvent → isSkipped=false
7.   Inner COU loop (k=0..iCOULen-1)
8.     COU CompletionStatus==2 skip check
9.     COU PreExecCheck gate → GetXMLForChildOU(orderRequest, refId, pouRefId)
10.    Build + assertEvent COU variant → ActionRequestEvent → isSkipped=false
11. Post-loop: if isSkipped → SkipActivity("4"); else SendFirstRequestEvent + Status="1" + SendDataToDB
12. catch(Exception) → HandleActivityException
```

---

## §6 Rule Action (THEN) — Step-by-step Logic

### Resubmit + Initialization

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
if(isActResub)
    RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
boolean isSkipped = true;
```

### Outer POU Loop

```java
for (int i=0; i < iPOULen; i++) {
    String pouRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;
    // CompletionStatus==2 skip check
    boolean pouReqSuccess = false;
    for(int iResp=0; iResp < orderCurrentActivity.Response@length; iResp++)
        if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, pouRefId)
           && orderCurrentActivity.Response[iResp].CompletionStatus == 2)
            pouReqSuccess = true;
    if(!pouReqSuccess) {
        String chkRes = "true";
        if(String.length(nextAct.PreExecCheck) > 0) {
            String sXML = RuleFunctions.Helpers.GetXMLForOU(orderRequest, pouRefId);
            chkRes = XPath.execute("/" + nextAct.PreExecCheck, sXML, "ns0=...");
        }
        if(String.equals(chkRes, "true")) {
            // Build + send POU event (chNodeId = ParentOU[(i+1)]/OUId)
            Events... reqEvent = Event.createEvent("xslt://..."); /* see §9.8 Variant ① */
            Event.assertEvent(reqEvent);
            RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
            isSkipped = false;
        }
    }
    // Inner COU loop (k=0..iCOULen-1) — same pattern using GetXMLForChildOU
}
```

### Post-loop Decision

```java
if(!isSkipped) {
    RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
    orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
    RuleFunctions.Helpers.SendDataToDB(orderRequest);
} else
    RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
```

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

Fires during any order flow that includes **CHANGE_PP** (or similar flows referencing corporate OU hierarchies). Required to populate Subscriber lists under POU and COU nodes before downstream subscription change activities execute.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event | Purpose |
|-----------|-------|---------|
| [OUTBOUND] | `CCBS_GET_SUBS_LIST` | Request subscriber list from CCBS for one OU |
| [INBOUND] | `CCBS_GET_SUBS_LIST` (response) | Receives SubscriberHeaderList payload |
| [LOG] | `OMXESB Logger` | Audit trail for REQ and RES events |

### §8.3 Backend API Details

| System | Operation | Schema | Correlation |
|--------|-----------|--------|-------------|
| CCBS | GetSubscriberList | `ns:GetSubscriberListRequest` | RefID matches POU.RefId or COU.RefId |

### §8.4 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `Customer.ParentOU[i].RefId` | Read | Correlation ID for POU requests |
| `Customer.ParentOU[i].OUId` | Read | chNodeId for POU payload |
| `ParentOU[i].ChildOU[k].RefId` | Read | Correlation ID for COU requests |
| `ParentOU[i].ChildOU[k].OUId` | Read | chNodeId for COU payload |
| `orderCurrentActivity.Response[]` | Read/Write | Skip check reads; response handler appends |
| `orderCurrentActivity.RequestCount` | Read | Fan-in counter |
| `pou.Subscriber[]` | Write (response) | Active subscribers (Status=65) appended |
| `cou.Subscriber[]` | Write (response) | Active subscribers (Status=65) appended |

### §8.5 ExtendedInfo Fields

None used in this FM.

### §8.6 Global Variable Dependencies

| Global Variable Path | Purpose |
|---------------------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit log level |
| `OMX_OM/WritePayload` | Controls payload inclusion in audit log |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Variant | XSLT Params | Notes |
|---------|-------------|-------|
| POU Variant ① | `orderRequest, refId, globalVariables, i` | `i` = numeric POU array index (0-based) |
| COU Variant ② | `orderRequest, refId, globalVariables, i, k` | `i`=POU index, `k`=COU index (0-based) |

### §9.2 Event Container Construction

| Field | Value |
|-------|-------|
| `event @extId` | `OMXUtils:generateTrackingID()` |
| Event type | `Events.OMConsumers.OMXFM.Request.CCBS_GET_SUBS_LIST` |

### §9.3 JMS / Event Header Fields

| Header | Source | Conditional? |
|--------|--------|-------------|
| `JMSPriority` | `$orderRequest/OrderPriority` | [Conditional] |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | [Conditional] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Conditional] |
| `RefID` | `$refId` (POU or COU RefId) | [Conditional] |
| `UserName` | `$globalVariables/.../UserName` | [Credential-gated: IsEnableUserPass='true'] |
| `PassWord` | `$globalVariables/.../PassWord` | [Credential-gated: IsEnableUserPass='true'] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Always] |
| `CES` | `$orderRequest/OrderData/CES` | [Conditional] |

### §9.4 Payload Root Element

`ns:GetSubscriberListRequest`

### §9.5 Payload Fields

| Element | Value | Notes |
|---------|-------|-------|
| `ns:unitIdInfo/ns:chNodeId` | POU: `ParentOU[(i+1)]/OUId`; COU: `ParentOU[(i+1)]/ChildOU[(k+1)]/OUId` | Positional XPath; 1-based |
| `ns:subTreeFlagInfo/ns:yesNoIndicator` | `89` (static = Yes) | Retrieve full subtree |
| `ns:paginationInfo/ns:pageNumber` | `0` (static) | First page only |

### §9.6 Variant Differences

| Aspect | POU Variant ① | COU Variant ② |
|--------|--------------|--------------|
| XSLT params | `i` | `i` + `k` |
| chNodeId XPath | `ParentOU[(number($i)+1)]/OUId` | `ParentOU[(number($i)+1)]/ChildOU[(number($k)+1)]/OUId` |
| PreExecCheck helper | `GetXMLForOU(orderRequest, refId)` | `GetXMLForChildOU(orderRequest, refId, pouRefId)` |
| AUDIT_TRACE | `"CCBS_GET_SUBS_LIST"` (static) | `"CCBS_GET_SUBS_LIST"` (static) |

### §9.7 Complete Generated XML Example (POU Variant)

```xml
<event extId="OMX-20260915-001-abcdef">
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRACK-001</JMSCorrelationID>
  <OrderID>ORD-123456</OrderID>
  <RefID>POU-001-REF</RefID>
  <OrderType>CHANGE_PP</OrderType>
  <CES>CES-001</CES>
  <payload>
    <ns:GetSubscriberListRequest>
      <ns:unitIdInfo>
        <ns:chNodeId>OU-456789</ns:chNodeId>
      </ns:unitIdInfo>
      <ns:subTreeFlagInfo>
        <ns:yesNoIndicator>89</ns:yesNoIndicator>
      </ns:subTreeFlagInfo>
      <ns:paginationInfo>
        <ns:pageNumber>0</ns:pageNumber>
      </ns:paginationInfo>
    </ns:GetSubscriberListRequest>
  </payload>
</event>
```

### §9.8 XSLT Stylesheet Sources

**Variant ① — ParentOU Request**

```xml
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ns="...GetSubscriberListRequest"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    version="1.0">
  <xsl:param name="orderRequest"/>   <!-- full order XML -->
  <xsl:param name="refId"/>          <!-- POU RefId for JMS correlation -->
  <xsl:param name="globalVariables"/>
  <xsl:param name="i"/>              <!-- POU 0-based index -->
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <!-- JMS headers (all conditional on field presence) -->
        <xsl:if test="$orderRequest/OrderPriority">
          <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
          <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OrderID">
          <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        </xsl:if>
        <xsl:if test="$refId">
          <RefID><xsl:value-of select="$refId"/></RefID>
        </xsl:if>
        <!-- Credential-gated headers -->
        <xsl:if test="$globalVariables/.../IsEnableUserPass='true'">
          <UserName>...</UserName>
          <PassWord>...</PassWord>
        </xsl:if>
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        <xsl:if test="$orderRequest/OrderData/CES">
          <CES><xsl:value-of select="$orderRequest/OrderData/CES"/></CES>
        </xsl:if>
        <payload>
          <ns:GetSubscriberListRequest>
            <ns:unitIdInfo>
              <!-- chNodeId = POU OUId, 1-based position -->
              <ns:chNodeId>
                <xsl:variable name="pouIdx" select="(number($i)+1)"/>
                <xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[$pouIdx]/OUId"/>
              </ns:chNodeId>
            </ns:unitIdInfo>
            <ns:subTreeFlagInfo>
              <ns:yesNoIndicator>89</ns:yesNoIndicator>
            </ns:subTreeFlagInfo>
            <ns:paginationInfo>
              <ns:pageNumber>0</ns:pageNumber>
            </ns:paginationInfo>
          </ns:GetSubscriberListRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**Variant ② — ChildOU Request (difference only):**

```xml
<xsl:param name="k"/>  <!-- COU 0-based index -->
<!-- chNodeId: -->
<xsl:variable name="couIdx" select="(number($k)+1)"/>
<xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[$pouIdx]/ChildOU[$couIdx]/OUId"/>
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

**POU Variant ①** (COU Variant ② differs only in `chNodeId` XPath)

```text
createEvent
└── event @extId ← OMXUtils:generateTrackingID()                               [Always]
    ├── JMSPriority         ← $orderRequest/OrderPriority                      [Conditional]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId             [Conditional]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                   [Conditional]
    ├── RefID               ← $refId                                            [Conditional]
    ├── UserName            ← $globalVariables/.../UserName                     [Credential-gated: IsEnableUserPass='true']
    ├── PassWord            ← $globalVariables/.../PassWord                     [Credential-gated: IsEnableUserPass='true']
    ├── OrderType           ← $orderRequest/OrderData/OrderType                 [Always]
    ├── CES                 ← $orderRequest/OrderData/CES                       [Conditional]
    └── payload
        └── ns:GetSubscriberListRequest
            ├── ns:unitIdInfo
            │   └── ns:chNodeId ← POU: ParentOU[(i+1)]/OUId                   [Always]
            │                     COU: ParentOU[(i+1)]/ChildOU[(k+1)]/OUId
            ├── ns:subTreeFlagInfo
            │   └── ns:yesNoIndicator ← "89" (static = Yes)                   [Always]
            └── ns:paginationInfo
                └── ns:pageNumber ← "0" (static)                               [Always]
```

**Legend:** Green = XPath source | Orange = Static literal | Purple italic = xsl:if condition | `[Always]` `[Conditional]` `[Credential-gated]`

---

## §11 Audit Logging

### Request Audit (per send)

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| PROCESS_ID | `concat(pid, "_REQ")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/.../OMX_CEP` |
| OPERATION_NAME | `"CCBS_GET_SUBS_LIST"` (static) |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/.../OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `concat("Request Sent for CCBS_GET_SUBS_LIST")` |
| payload | Conditional on `WritePayload="true"` |

### Response Audit

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(pid, "_RES")` |
| OPERATION_NAME | `"CCBS_GET_SUBS_LIST"` (static) |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` |

---

## §12 Activity Status Management

| Condition | Status Code | Status String | Action |
|-----------|-------------|---------------|--------|
| At least one send occurred | "1" | IN_PROGRESS | `GetActivityStatusString("1", false)` |
| All OUs skipped (isSkipped=true) | N/A | SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |

---

## §13 Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` | Clears pending requests on resubmit |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Registers event with sequencing manager |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Triggers dispatch of first queued request |
| `IntraActivitySequencing.ActionResponseEvent(activity)` | Fan-in completion check |
| `GetXMLForOU(orderRequest, refId)` | Serializes POU XML for PreExecCheck evaluation |
| `GetXMLForChildOU(orderRequest, refId, pouRefId)` | Serializes COU XML with POU context |
| `GetActivityStatusString("1", false)` | Returns status string for IN_PROGRESS |
| `SkipActivity(orderRequest, activity, "4")` | Marks activity as skipped with code 4 |
| `SendDataToDB(orderRequest)` | Persists order state to database |
| `HandleActivityException(orderRequest, activity, ex, "")` | Central exception handler |

---

## §15 Function Dependency Tree

```text
Request_CCBS_GET_SUBS_LIST
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── GetXMLForOU(orderRequest, refId)                            [POU PreExecCheck]
├── GetXMLForChildOU(orderRequest, refId, pouRefId)             [COU PreExecCheck]
├── Event.assertEvent(reqEvent)                                 [register event]
├── IntraActivitySequencing.ActionRequestEvent(event, activity) [sequencing]
├── IntraActivitySequencing.SendFirstRequestEvent(activity)     [dispatch]
├── GetActivityStatusString("1", false)                         [status]
├── SkipActivity(orderRequest, activity, "4")                   [skip path]
├── SendDataToDB(orderRequest)                                   [persistence]
└── HandleActivityException(...)                                [error path]

Response_CCBS_GET_SUBS_LIST
├── Instance.createInstance(GetSubsListRes XSLT)               [response concept]
├── XPath.evalAsDouble(count SubscriberHeaders)                 [count subs]
├── Instance.createInstance(Subscriber XSLT) × N               [per subscriber]
├── XPath.evalAsBoolean($subscriber/Status=65)                  [active filter]
├── pou.Subscriber[].append / cou.Subscriber[].append           [populate OU]
├── Event.Ext.sendEventImmediate(Logger)                        [audit]
└── IntraActivitySequencing.ActionResponseEvent(currActivity)   [fan-in]
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields |
|---------|-----------|
| `Concepts.OrderRequest.OrderElements.ParentOU` | OUId, RefId, ChildOU[], Subscriber[] |
| `Concepts.OrderRequest.OrderElements.ChildOU` | OUId, RefId, Subscriber[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | extId (SUB:trackingId:SubscrNumber), MSISDN, RefId, SubscriberGeneralInfo, SubscriberType, SubscriberId, Status |
| `Concepts.FM.Response.GetSubsListRes` | extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

- **R1:** Support hierarchical OU iteration — outer POU loop with inner COU loop per POU
- **R2:** Skip OUs already successfully responded (CompletionStatus==2) on resubmit
- **R3:** Support PreExecCheck gate at both POU and COU levels with different XML serialization helpers
- **R4:** All parallel sends managed by IntraActivitySequencing; fan-in completes when all responses received
- **R5:** Filter returned subscribers by Status=65 (Active only); append to the correct OU node
- **R6:** Subscriber extId pattern: `SUB:{OMXTrackingId}:{SubscrNumber}`

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Large OU hierarchies may generate many parallel CCBS calls, potentially exceeding JMS capacity | [MEDIUM] | Add pagination support or throttle OU batch sizes in migration |
| pageNumber=0 static — only first page retrieved; if subscribers exceed one page, data is silently incomplete | [HIGH] | Implement pagination loop in migration; check CCBS page size limits |
| Status=65 filter hardcoded — if CCBS changes status codes, filter silently drops all subscribers | [MEDIUM] | Make status code configurable via global variable or lookup table |
| Subscriber extId collision possible if same subscriber appears in multiple OUs | [LOW] | Verify uniqueness in downstream processing |

---

## §18 Full Source Code

```java
/**
 * @description
 * @author awalia-t420
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_SUBS_LIST {
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
        orderCurrentActivity.ActivityID == "CCBS_GET_SUBS_LIST";
        orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_SUBS_LIST";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0
                              && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct =
                Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName,
                                         "/Concepts/OM/ProcessConfig/Activity");
            int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
            if(isActResub)
                RuleFunctions.Helpers.IntraActivitySequencing
                    .PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
            boolean isSkipped = true;

            for (int i = 0; i < iPOULen; i++) {
                String pouRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;
                // CompletionStatus==2 skip check for POU
                boolean pouReqSuccess = false;
                for(int iResp=0; iResp < orderCurrentActivity.Response@length; iResp++)
                    if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, pouRefId)
                       && orderCurrentActivity.Response[iResp].CompletionStatus == 2)
                        pouReqSuccess = true;
                if(!pouReqSuccess) {
                    String chkRes = "true";
                    if(String.length(nextAct.PreExecCheck) > 0) {
                        String sXML = RuleFunctions.Helpers.GetXMLForOU(orderRequest, pouRefId);
                        chkRes = XPath.execute("/" + nextAct.PreExecCheck, sXML, "ns0=...");
                    }
                    if(String.equals(chkRes, "true")) {
                        /* Build POU event — see §9.8 Variant ①
                           Output: extId, JMS headers, payload/ns:GetSubscriberListRequest
                           with chNodeId=ParentOU[(i+1)]/OUId, yesNoIndicator=89, pageNumber=0 */
                        Events... reqEvent = Event.createEvent("xslt://...");
                        Event.assertEvent(reqEvent);
                        RuleFunctions.Helpers.IntraActivitySequencing
                            .ActionRequestEvent(reqEvent, orderCurrentActivity);
                        /* Audit log REQ */
                        isSkipped = false;
                    }
                }

                // Inner COU loop
                int iCOULen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU@length;
                for (int k = 0; k < iCOULen; k++) {
                    String couRefId = orderRequest.OrderData.Customer.ParentOU[i].ChildOU[k].RefId;
                    // CompletionStatus==2 skip check for COU
                    boolean couReqSuccess = false;
                    for(int iResp=0; iResp < orderCurrentActivity.Response@length; iResp++)
                        if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, couRefId)
                           && orderCurrentActivity.Response[iResp].CompletionStatus == 2)
                            couReqSuccess = true;
                    if(!couReqSuccess) {
                        String chkRes = "true";
                        if(String.length(nextAct.PreExecCheck) > 0) {
                            String sXML = RuleFunctions.Helpers
                                .GetXMLForChildOU(orderRequest, couRefId, pouRefId);
                            chkRes = XPath.execute("/" + nextAct.PreExecCheck, sXML, "ns0=...");
                        }
                        if(String.equals(chkRes, "true")) {
                            /* Build COU event — see §9.8 Variant ②
                               chNodeId=ParentOU[(i+1)]/ChildOU[(k+1)]/OUId */
                            Events... couEvent = Event.createEvent("xslt://...");
                            Event.assertEvent(couEvent);
                            RuleFunctions.Helpers.IntraActivitySequencing
                                .ActionRequestEvent(couEvent, orderCurrentActivity);
                            isSkipped = false;
                        }
                    }
                }
            } // end POU loop

            if(!isSkipped) {
                RuleFunctions.Helpers.IntraActivitySequencing
                    .SendFirstRequestEvent(orderCurrentActivity);
                orderCurrentActivity.Status =
                    RuleFunctions.Helpers.GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
            } else
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
        }
        catch (Exception ae) {
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

The response handler `Response_CCBS_GET_SUBS_LIST.rulefunction` processes the CCBS GetSubscriberList reply. It creates a `GetSubsListRes` response concept and appends it to `currActivity.Response[]`. It then iterates over all `Customer.ParentOU` entries to match the responding OU by RefID. For the matched OU (POU or COU), it parses the returned `SubscriberHeaderList`, creates `Subscriber` concept instances for each entry with `Status=65` (Active), and appends them to the appropriate OU node.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order data; POU/COU arrays modified |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_GET_SUBS_LIST` | Inbound response event with SubscriberHeaderList payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking; Response[] appended |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object @extId ← OMXUtils:generateTrackingID()   [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode      [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg       [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus  [Conditional]
    └── ReferenceId      ← $eventResponse/RefID             [Conditional]
```

### §19.4 Subscriber Population Logic

```java
for(int j=0; j < orderRequest.OrderData.Customer.ParentOU@length; j++) {
    pou = Customer.ParentOU[j];
    if(String.equals(eventResponse.RefID, pou.RefId)) {
        // POU match: count subscribers, create Subscriber concepts
        iSubResCnt = XPath.evalAsDouble("count(.../SubscriberHeader)");
        for(int i=0; i < iSubResCnt; i++) {
            subscriber = Instance.createInstance("xslt://..."); /* see §19.6 */
            if(XPath.evalAsBoolean("$subscriber/Status=65"))
                pou.Subscriber[pou.Subscriber@length] = subscriber;
        }
        break;
    }
    // Check ChildOUs
    for(int m=0; m < pou.ChildOU@length; m++) {
        cou = pou.ChildOU[m];
        if(String.equals(eventResponse.RefID, cou.RefId)) {
            // COU match: same subscriber creation pattern
            if(XPath.evalAsBoolean("$subscriber/Status=65"))
                cou.Subscriber[cou.Subscriber@length] = subscriber;
            break;
        }
    }
}
```

### §19.5 Subscriber Concept Fields (from XSLT)

```text
object @extId ← concat("SUB:", OMXTrackingId, ":", SubscrNumber)        [Always]
├── MSISDN              ← SubscriberGeneralInfo/PrimResourceVal          [Conditional]
├── RefId               ← SubscriberIdInfo/SubscrNumber                  [Always]
├── SubscriberGeneralInfo  (xsl:for-each on SubscriberGeneralInfo)
│   ├── EffectiveDate   ← ns:EffectiveDate                               [Conditional]
│   ├── Language        ← ns:Language                                    [Conditional]
│   ├── ProofDate       ← ns:L9ProofDate                                 [Conditional]
│   ├── ProofDoc        ← ns:L9ProofDoc                                  [Conditional]
│   ├── SplitPeriod     ← ns:L9SplitPeriod                               [Conditional]
│   └── SMSInd          ← ns:L9SmsInd                                    [Conditional]
├── SubscriberType      ← SubscriberTypeInfo/SubscriberType              [Conditional]
├── SubscriberId        ← SubscriberIdInfo/SubscrNumber                  [Always]
└── Status              ← SubscriberStatusInfo/SubStatus                 [Conditional]
```

> Only subscribers where `Status=65` (Active) are appended to the OU's Subscriber array. POU uses loop variable `i`; COU uses `n`. Both compute `iSub = (index+1)` inside the XSLT as a 1-based position.

### §19.6 Response Completion Logic

```java
RuleFunctions.Helpers.IntraActivitySequencing.ActionResponseEvent(currActivity)
    → return "true"   // all pending requests in sequence fulfilled
    → return "false"  // still waiting for more responses
```

### §19.7 Response Audit Log

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(pid, "_RES")` |
| OPERATION_NAME | `"CCBS_GET_SUBS_LIST"` (static) |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` — dynamic |
| payload | Conditional on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
