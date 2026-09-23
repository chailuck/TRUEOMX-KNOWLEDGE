# Request_SBM_FUP_DELETE_GROUP

> Deletes FUP (Fair Usage Policy) groups in SBM for each OU that passes the PreExecCheck.  
> Simpler than CREATE_GROUP — no FUP offer scan; only `fupID` parameter sent.

**System:** SBM | **Priority:** 5 | **Author:** SathidP-PC | **function_id:** 104300003  
**Pattern:** Dual-loop POU/COU + direct send | **Fan-in:** count(success) == RequestCount

> **Relationship to SBM_FUP_CREATE_GROUP:** Same dual-loop/direct-send/fan-in structure. Differences: (1) function_id=104300003; (2) No FUP offer scan; (3) Payload has only `fupID`; (4) No `OMX_DATA_ERROR` throw; (5) XSLT params: no `fupElement`.

---

## §1 Overview & Purpose

Deletes FUP groups in SBM by sending `SBM_FUP_DO_SERVICE` requests with `function_id=104300003` for each ParentOU and ChildOU that passes the PreExecCheck. No FUP offer scanning — sends a delete request for each eligible OU with only its `OUId` as the `fupID` parameter.

| Attribute | Value |
|-----------|-------|
| Rule File | `Request_SBM_FUP_DELETE_GROUP.rule` |
| Response File | `Response_SBM_FUP_DELETE_GROUP.rulefunction` |
| Author | SathidP-PC |
| Priority | 5 |
| Target System | SBM |
| SBM function_id | 104300003 (DELETE_GROUP) |
| Event name | SBM_FUP_DO_SERVICE (shared) |
| Send pattern | Event.Ext.sendEventImmediate + manual RequestCount++ |
| Fan-in | count(ResponseCode suffix "000") == RequestCount |
| FUP offer scan | None — only fupID parameter sent |

---

## §4 Rule Conditions (WHEN)

| Condition | Purpose |
|-----------|---------|
| `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity pointer match |
| `orderCurrentActivity.ActivityID == "SBM_FUP_DELETE_GROUP"` | Specific FM match |
| `orderRequest.ProcessFlow.NextActivityID == "SBM_FUP_DELETE_GROUP"` | Process flow alignment |
| `orderCurrentActivity.Status == "WAITING"` | Prevents re-firing |

---

## §5 Execution Flow

1. **Resubmit + Init** — If resubmit, PurgePendingRequestsBeforeResubmit. Set `function_id="104300003"`, `isSkipped=true`
2. **Outer POU Loop** — GetXMLForOU + PreExecCheck gate
3. **POU Send** — Build SBM_FUP_DO_SERVICE event (fupID only). sendEventImmediate. RequestCount++. isSkipped=false
4. **Inner COU Loop** — GetXMLForChildOU + PreExecCheck. Same send pattern
5. **Post-loop** — If !isSkipped → Status="1" + SendDataToDB. Else → SkipActivity("4")
6. **Exception** → HandleActivityException

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Variant | XSLT Params | Notes |
|---------|-------------|-------|
| POU Variant ① | `orderRequest, currPOU, function_id` | No fupElement (vs CREATE_GROUP) |
| COU Variant ② | `orderRequest, currCOU, function_id` | No fupElement |

### §9.3 JMS / Event Header Fields

| Header | Source | Conditional? |
|--------|--------|-------------|
| `JMSPriority` | `$orderRequest/OrderPriority` | [Conditional] |
| `JMSCorrelationID` | `$orderRequest/@extId` | [Conditional — @extId attribute] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Conditional] |
| `RefID` | `$currPOU/RefId` or `$currCOU/RefId` | [Conditional] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Conditional] |

### §9.5 Payload Parameters

| Key | Value |
|-----|-------|
| `fupID` | `$currPOU/OUId` or `$currCOU/OUId` |

`ns:service_no` ← OUId; `ns:function_id` ← `"104300003"` (static)

### §9.7 Complete Generated XML Example (POU Variant)

```xml
<event>
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-EXTID-001</JMSCorrelationID>
  <OrderID>ORD-123456</OrderID>
  <RefID>POU-REF-001</RefID>
  <OrderType>CHANGE_PP</OrderType>
  <payload>
    <ns:doServiceRequest><ns:req>
      <ns:function_id>104300003</ns:function_id>
      <ns:parameters>
        <ns:item><ns:key>fupID</ns:key><ns:value>OU-456789</ns:value></ns:item>
      </ns:parameters>
      <ns:service_no>OU-456789</ns:service_no>
    </ns:req></ns:doServiceRequest>
  </payload>
</event>
```

### §9.8 XSLT Stylesheet Source

**Variant ① — POU (params: orderRequest, currPOU, function_id)**

```xml
<xsl:stylesheet xmlns:ns="http://services.omx.truecorp.co.th/FMServices/SBMFUPDoserviceRequest" version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="currPOU"/>
  <xsl:param name="function_id"/>  <!-- "104300003" -->
  <!-- headers: JMSPriority, JMSCorrelationID(@extId), OrderID, RefID(currPOU/RefId), OrderType -->
  <payload><ns:doServiceRequest><ns:req>
    <ns:function_id><xsl:value-of select="$function_id"/></ns:function_id>
    <ns:parameters>
      <ns:item><ns:key>fupID</ns:key>
        <ns:value><xsl:value-of select="$currPOU/OUId"/></ns:value></ns:item>
    </ns:parameters>
    <ns:service_no><xsl:value-of select="$currPOU/OUId"/></ns:service_no>
  </ns:req></ns:doServiceRequest></payload>
```

COU Variant ②: identical but uses `currCOU` param and `$currCOU/OUId`.

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority        ← $orderRequest/OrderPriority                [Conditional]
    ├── JMSCorrelationID   ← $orderRequest/@extId                       [Conditional — @extId attribute]
    ├── OrderID            ← $orderRequest/OrderData/OrderID            [Conditional]
    ├── RefID              ← $currPOU/RefId | $currCOU/RefId            [Conditional]
    ├── OrderType          ← $orderRequest/OrderData/OrderType          [Conditional]
    └── payload
        └── ns:doServiceRequest / ns:req
            ├── ns:function_id  ← "104300003" (static)                 [Always]
            ├── ns:parameters
            │   └── ns:item[fupID] ← currOU/OUId                       [Always]
            └── ns:service_no  ← currOU/OUId                           [Always]
```

---

## §11 Audit Logging

| Direction | OPERATION_NAME | AUDIT_TRACE | LOG_LEVEL |
|-----------|---------------|-------------|-----------|
| Request (Event.sendEvent async) | `"SBM_FUP_DELETE_GROUP"` | `"Request Sent for SBM_FUP_DELETE_GROUP"` | INFO |
| Response | `"SBM_FUP_DELETE_GROUP"` | `"Response received for SBM_FUP_DELETE_GROUP"` | INFO |

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one send occurred | "1" IN_PROGRESS | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All OUs skipped | SKIPPED | `SkipActivity("4")` |

---

## §15 Function Dependency Tree

```text
Request_SBM_FUP_DELETE_GROUP
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── GetXMLForOU(orderRequest, pOURefId)                         [POU PreExecCheck]
├── GetXMLForChildOU(orderRequest, cOURefId, pOURefId)          [COU PreExecCheck]
├── Event.Ext.sendEventImmediate(reqEvent)                       [direct send]
├── RequestCount++ (manual)                                      [fan-in counter]
├── Event.sendEvent(Logger)                                      [async audit]
├── GetActivityStatusString("1", false)
├── SkipActivity("4") | SendDataToDB
└── HandleActivityException(...)

Response_SBM_FUP_DELETE_GROUP
├── Instance.createInstance(SBM_FUP_DoServiceRes XSLT)
├── Event.Ext.sendEventImmediate(Logger)
└── count(ResponseCode suffix "000") == RequestCount → "true"/"false"
```

---

## §17 Migration Notes & Recommendations

**Key differences from SBM_FUP_CREATE_GROUP:**
- function_id=104300003 (DELETE) vs 104300001 (CREATE)
- No FUP offer scan — only `fupID` parameter sent
- No `OMX_DATA_ERROR` throw
- XSLT params: no `fupElement`

| Risk | Severity | Mitigation |
|------|----------|-----------|
| No CompletionStatus==2 check — on resubmit, duplicate DELETE calls may be sent | [HIGH] | Add CompletionStatus==2 check; verify SBM idempotency for 104300003 |
| Deletes ALL OUs that pass PreExecCheck — if called after CREATE_GROUP, ensure PreExecCheck gates correctly | [MEDIUM] | Review ProcessConfig PreExecCheck conditions for SBM_FUP_DELETE_GROUP step |

---

## §18 Full Source Code

```java
/**
 * @description 
 * @author SathidP-PC
 */
rule Rules.OMConsumers.OMXFM.Request.Request_SBM_FUP_DELETE_GROUP {
    attribute { priority = 5; forwardChain = true; }
    declare { ... }
    when {
        ... ActivityID == "SBM_FUP_DELETE_GROUP" ...
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            String function_id = "104300003";
            if(isActResub) PurgePendingRequestsBeforeResubmit(...);
            boolean isSkipped = true;
            for(int iPOU=0; iPOU < pOULen; iPOU++) {
                // PreExecCheck gate via GetXMLForOU
                if(chkRes == "true") {
                    /* Build POU event — see §9.8 Variant ①
                       function_id=104300003, params: fupID=OUId, service_no=OUId */
                    Event.Ext.sendEventImmediate(reqEvent);
                    if(!isActResub) orderCurrentActivity.RequestCount++;
                    isSkipped = false;
                }
                for(int iCOU=0; iCOU < cOULen; iCOU++) {
                    // COU variant — GetXMLForChildOU, same send pattern
                }
            }
            if(!isSkipped) { Status="1"; SendDataToDB(); }
            else SkipActivity("4");
        }
        catch(Exception ae) { HandleActivityException(...); }
    }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

`Response_SBM_FUP_DELETE_GROUP` handles the SBM reply, creates a `SBM_FUP_DoServiceRes` concept with 7 SBM-specific fields, and drives fan-in completion. Identical structure to `Response_SBM_FUP_CREATE_GROUP`.

### §19.4 Fan-in Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)='000'])
```

```java
if(currActivity.RequestCount == successResponseCount) return "true";
else return "false";
```

All parallel SBM DELETE_GROUP calls must succeed (ResponseCode suffix "000") before the activity completes.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
