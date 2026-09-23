# Request_SBM_FUP_CHANGE_MEMBER

> Adds or removes Subscribers from FUP groups in SBM — subscriber-level iteration with dual function_id dispatch.

**System:** SBM | **Priority:** 5 | **Author:** DESKTOP-995HR2V  
**function_id:** 104300004 (ADD) / 104300005 (REMOVE) | **Pattern:** Subscriber-loop POU/COU  
**Fan-in:** count(success) == RequestCount | **Loop level:** Subscriber within each OU

> **Key difference from CREATE/DELETE_GROUP:** This FM iterates over **Subscribers** within each OU (not just OUs). Sends one SBM request per subscriber. function_id is from `Parameter[0]` ("ADD"=104300004 / "REMOVE"=104300005). Payload has 3 params: `fupID`, `msisdn`, optional `socCapmax` (ADD+FCA offer only).

---

## §1 Overview & Purpose

Adds or removes individual Subscribers from FUP groups by sending `SBM_FUP_DO_SERVICE` per subscriber. function_id is determined dynamically from `Parameter[0]`. On ADD, includes optional `socCapmax` from the subscriber's FCA-type special offer indicator.

| Attribute | Value |
|-----------|-------|
| Rule File | `Request_SBM_FUP_CHANGE_MEMBER.rule` |
| Response File | `Response_SBM_FUP_CHANGE_MEMBER.rulefunction` |
| Author | DESKTOP-995HR2V |
| Priority | 5 |
| Target System | SBM |
| function_id (ADD) | 104300004 |
| function_id (REMOVE) | 104300005 |
| Event name | SBM_FUP_DO_SERVICE (shared) |
| Loop level | Subscriber within POU/COU |
| Send pattern | Event.Ext.sendEventImmediate + manual RequestCount++ |
| CompletionStatus check | Per subscriber refId (correct) |
| Fan-in | count(ResponseCode suffix "000") == RequestCount |
| JMSCorrelationID | OMXTrackingId (conditional test) |

---

## §4 Rule Conditions (WHEN)

| Condition | Purpose |
|-----------|---------|
| `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity pointer |
| `orderCurrentActivity.ActivityID == "SBM_FUP_CHANGE_MEMBER"` | FM match |
| `orderRequest.ProcessFlow.NextActivityID == "SBM_FUP_CHANGE_MEMBER"` | Flow alignment |
| `orderCurrentActivity.Status == "WAITING"` | Prevents re-firing |

---

## §5 Execution Flow

1. **Init** — If resubmit → PurgePendingRequestsBeforeResubmit. Get `param = Parameter[0]`. **Validate**: throw `DATA_ISSUE` if not "ADD" or "REMOVE"
2. **POU loop** — OU-level PreExecCheck via GetXMLForOU → `chkRes_OU`
3. **POU Subscriber loop** — CompletionStatus==2 check (by sub.RefId). If not complete: Subscriber-level PreExecCheck via GetXMLForSubscriber → `chkRes`
4. **Send** — If `chkRes_OU==true` OR `chkRes==true`: build SBM_FUP_DO_SERVICE event. sendEventImmediate. RequestCount++ (if !resubmit). isSkipped=false. Send audit (always)
5. **COU loop** — Same with GetXMLForChildOU + GetXMLForSubscriberInChildOU; fupID=cOuId
6. **Post-loop** — If !isSkipped → Status="1" + SendDataToDB. Else → SkipActivity("4")
7. **Exception** → HandleActivityException

> **Note:** OR-logic gate: fires if either OU-level OR subscriber-level PreExecCheck passes.  
> **⚠ Audit logger fires on resubmit** (outside `if(!isActResub)` block) — duplicate logs per subscriber on resubmit.

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Param | POU Variant | COU Variant |
|-------|-------------|-------------|
| `orderRequest` | OrderRequest concept | same |
| `refId` | `sub.RefId` | same |
| `param` | `"ADD"` or `"REMOVE"` | same |
| `pOuId` | `parentOU[p].OUId` | — |
| `cOuId` | — | `childOU[c].OUId` |
| `msisdn` | `FormatMSISDNPrefix(sub.MSISDN, true)` | same |
| `sub` | current Subscriber concept | same |

### §9.3 JMS / Event Header Fields

| Header | Source | Conditional? |
|--------|--------|-------------|
| `JMSPriority` | `$orderRequest/OrderPriority` | [Conditional: if test] |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | [Conditional: if test] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Conditional: if test] |
| `RefID` | `$refId` (Subscriber RefId) | [Always] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Conditional: if test] |

### §9.5 Payload Parameters

| Key | Value | Conditional? |
|-----|-------|-------------|
| `function_id` | `"104300004"` (ADD) / `"104300005"` (REMOVE) via xsl:choose | [Always] |
| `fupID` | `$pOuId` or `$cOuId` | [Always] |
| `msisdn` | `$msisdn` (formatted) | [Always] |
| `socCapmax` | `$sub/SubscriberOffers[ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and Value='FCA']]/OfferName` | [Conditional: param="ADD" AND FCA offer exists] |

`ns:service_no` = `$msisdn`

### §9.8 XSLT Stylesheet Source

**Variant ① — POU (params: orderRequest, refId, param, pOuId, msisdn, sub)**

```xml
<xsl:stylesheet xmlns:ns="http://services.omx.truecorp.co.th/FMServices/SBMFUPDoserviceRequest" version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="refId"/>        <!-- sub.RefId -->
  <xsl:param name="param"/>        <!-- "ADD" or "REMOVE" -->
  <xsl:param name="pOuId"/>        <!-- ParentOU.OUId -->
  <xsl:param name="msisdn"/>       <!-- FormatMSISDNPrefix(sub.MSISDN, true) -->
  <xsl:param name="sub"/>          <!-- Subscriber concept -->
  <payload><ns:doServiceRequest><ns:req>
    <xsl:choose>
      <xsl:when test="$param='ADD'">
        <ns:function_id>104300004</ns:function_id>
      </xsl:when>
      <xsl:otherwise>
        <ns:function_id>104300005</ns:function_id>
      </xsl:otherwise>
    </xsl:choose>
    <ns:parameters>
      <ns:item><ns:key>fupID</ns:key><ns:value><xsl:value-of select="$pOuId"/></ns:value></ns:item>
      <ns:item><ns:key>msisdn</ns:key><ns:value><xsl:value-of select="$msisdn"/></ns:value></ns:item>
      <xsl:if test="$param='ADD' and exists($sub/SubscriberOffers[ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and Value='FCA']])">
        <ns:item><ns:key>socCapmax</ns:key>
          <ns:value><xsl:value-of select="$sub/SubscriberOffers[ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR' and Value='FCA']]/OfferName"/></ns:value>
        </ns:item>
      </xsl:if>
    </ns:parameters>
    <ns:service_no><xsl:value-of select="$msisdn"/></ns:service_no>
  </ns:req></ns:doServiceRequest></payload>
```

COU Variant ②: identical but uses `cOuId` param instead of `pOuId`.

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority        ← $orderRequest/OrderPriority               [Conditional]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId     [Conditional]
    ├── OrderID            ← $orderRequest/OrderData/OrderID           [Conditional]
    ├── RefID              ← $refId (Subscriber RefId)                 [Always]
    ├── OrderType          ← $orderRequest/OrderData/OrderType         [Conditional]
    └── payload
        └── ns:doServiceRequest / ns:req
            ├── ns:function_id  ← "104300004"/"104300005" via xsl:choose  [Always]
            ├── ns:parameters
            │   ├── ns:item[fupID]    ← $pOuId | $cOuId               [Always]
            │   ├── ns:item[msisdn]   ← $msisdn                        [Always]
            │   └── ns:item[socCapmax]← $sub/.../OfferName             [Conditional: ADD+FCA]
            └── ns:service_no    ← $msisdn                             [Always]
```

---

## §11 Audit Logging

| Direction | OPERATION_NAME | AUDIT_TRACE | Send Method |
|-----------|---------------|-------------|-------------|
| Request | `"SBM_FUP_CHANGE_MEMBER"` | `"Request Sent for SBM_FUP_CHANGE_MEMBER"` | Event.Ext.sendEventImmediate (always, even resubmit) |
| Response | `"SBM_FUP_CHANGE_MEMBER"` | `"Response received for SBM_FUP_CHANGE_MEMBER"` | Event.Ext.sendEventImmediate |

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one send | "1" IN_PROGRESS | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All subscribers skipped | SKIPPED | `SkipActivity("4")` |

---

## §13 Exception / Error Handling

| Exception | When | Handler |
|-----------|------|---------|
| `Exception("DATA_ISSUE", "Param is missing.", null)` | Parameter[0] is not "ADD" or "REMOVE" | Caught by outer try/catch → HandleActivityException |
| Runtime exception | Any other error | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §15 Function Dependency Tree

```text
Request_SBM_FUP_CHANGE_MEMBER
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── Exception.newException("DATA_ISSUE"...)                      [if param invalid]
├── GetXMLForOU(orderRequest, pOuRefId)                          [POU OU-level PreExecCheck]
├── GetXMLForSubscriber(orderRequest, subRefId)                  [POU Sub-level PreExecCheck]
├── FormatMSISDNPrefix(sub.MSISDN, true)                         [per subscriber]
├── GetXMLForChildOU(orderRequest, cOuRefId, pOuRefId)           [COU OU-level PreExecCheck]
├── GetXMLForSubscriberInChildOU(orderRequest, subRefId, pOuRefId) [COU Sub-level PreExecCheck]
├── Event.Ext.sendEventImmediate(reqEvent)                       [per subscriber]
├── RequestCount++ (manual, if !resubmit)
├── Event.Ext.sendEventImmediate(Logger)                         [always on send]
├── GetActivityStatusString("1", false)
├── SkipActivity("4") | SendDataToDB
└── HandleActivityException(...)

Response_SBM_FUP_CHANGE_MEMBER
├── Instance.createInstance(SBM_FUP_DoServiceRes)
├── Event.Ext.sendEventImmediate(Logger)
└── count(ResponseCode suffix "000") == RequestCount → "true"/"false"
```

---

## §17 Migration Notes & Recommendations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Request audit fires on resubmit — duplicate audit logs per subscriber | [MEDIUM] | Move Logger inside `if(!isActResub)` block |
| DATA_ISSUE if Parameter[0] invalid — fails all subscribers | [MEDIUM] | Validate in ProcessConfig; add circuit-breaker |
| OR-logic PreExecCheck: sends if OU OR subscriber check passes | [LOW] | Review intent; AND logic may be expected |
| socCapmax relies on INTX offer enrichment (must run after step 65) | [MEDIUM] | Verify ProcessConfig step ordering |

---

## §18 Full Source Code

```java
/**
 * @author DESKTOP-995HR2V
 */
rule Rules.OMConsumers.OMXFM.Request.Request_SBM_FUP_CHANGE_MEMBER {
    attribute { priority = 5; forwardChain = true; }
    when { ... ActivityID == "SBM_FUP_CHANGE_MEMBER" ... }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
        try {
            if(isActResub) PurgePendingRequestsBeforeResubmit(...);
            String param = nextAct.Parameter[0];  // "ADD" or "REMOVE"
            if(!String.equals(param,"ADD") && !String.equals(param,"REMOVE"))
                throw Exception.newException("DATA_ISSUE", "Param is missing.", null);

            for(int p=0; p<pOuLen; p++) {
                // OU-level PreExecCheck → chkRes_OU
                for(int s=0; s<pSubLen; s++) {
                    sub = ParentOU[p].Subscriber[s];
                    // CompletionStatus==2 check by sub.RefId
                    if(!reqSuccess) {
                        // Subscriber-level PreExecCheck → chkRes
                        if(chkRes=="true" || chkRes_OU=="true") {
                            reqEvent = Event.createEvent("xslt://...");
                            /* §9.8 Variant ①: params orderRequest, refId, param, pOuId, msisdn, sub
                               function_id from xsl:choose (104300004/104300005)
                               params: fupID=pOuId, msisdn, optional socCapmax if ADD+FCA */
                            Event.Ext.sendEventImmediate(reqEvent);
                            if(!isActResub) orderCurrentActivity.RequestCount++;
                            isSkipped = false;
                            Event.Ext.sendEventImmediate(Logger); // always, even on resubmit
                        }
                    }
                }
                // COU subscriber loop — same with GetXMLForChildOU + GetXMLForSubscriberInChildOU
            }
            if(!isSkipped) { Status="1"; SendDataToDB(); }
            else SkipActivity("4");
        } catch(Exception ae) { HandleActivityException(...); }
    }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

Identical to `Response_SBM_FUP_CREATE_GROUP`: creates `SBM_FUP_DoServiceRes` with 7 SBM-specific fields; fan-in by count of successful responses; response audit via `Event.Ext.sendEventImmediate`. OPERATION_NAME="SBM_FUP_CHANGE_MEMBER".

### §19.4 Fan-in Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

`if(currActivity.RequestCount == successResponseCount)` → "true" else "false"

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
