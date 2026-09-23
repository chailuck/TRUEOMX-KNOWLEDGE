# Request_SBM_FUP_CHANGE_PP

> Updates FUP priceplan in SBM per OU — extracts old/new priceplan from Agreement.Offers and sends with fixed function_id 104300002.

**System:** SBM | **Priority:** 5 | **Author:** SathidP-PC  
**function_id:** 104300002 (fixed) | **Pattern:** OU-level dual-loop + Offer extraction  
**Fan-in:** count(success) == RequestCount | **JMSCorrelationID:** `$orderRequest/@extId` (NOT OMXTrackingId)

> **Key differences from other SBM FUP FMs:**
> 1. **JMSCorrelationID** = `$orderRequest/@extId` (not OMXTrackingId)
> 2. **Audit logger** uses `Event.sendEvent` (async) not `Event.Ext.sendEventImmediate`
> 3. **No OMX_DATA_ERROR** if oldPP/newPP not found — empty strings are sent
> 4. **isSkipped=false** set inside `if(chkRes=="true")` block (not unconditionally)

---

## §1 Overview & Purpose

Notifies SBM of a priceplan change per OU using `function_id=104300002` (hardcoded). Extracts the old priceplan (`FE_OR_CCBS="CCBS"`, ServiceType=80) and new priceplan (`FE_OR_CCBS="FE"`, ServiceType=80) from `Agreement.Offers`. No validation error if offers not found — empty strings are sent.

| Attribute | Value |
|-----------|-------|
| Rule File | `Request_SBM_FUP_CHANGE_PP.rule` |
| Response File | `Response_SBM_FUP_CHANGE_PP.rulefunction` |
| Author | SathidP-PC |
| Priority | 5 |
| Target System | SBM |
| function_id | 104300002 (hardcoded) |
| Event name | SBM_FUP_DO_SERVICE (shared) |
| Loop level | OU (POU then COU) |
| Priceplan extraction | From Agreement.Offers by FE_OR_CCBS value + ServiceType=80 |
| Send pattern | Event.Ext.sendEventImmediate + manual RequestCount++ |
| Audit pattern | Event.sendEvent (async) — different from most SBM FUP FMs |
| JMSCorrelationID | `$orderRequest/@extId` (NOT OMXTrackingId) |
| Fan-in | count(ResponseCode suffix "000") == RequestCount |

---

## §4 Rule Conditions (WHEN)

| Condition | Purpose |
|-----------|---------|
| `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity pointer |
| `ActivityID == "SBM_FUP_CHANGE_PP"` | FM match |
| `orderRequest.ProcessFlow.NextActivityID == "SBM_FUP_CHANGE_PP"` | Flow alignment |
| `orderCurrentActivity.Status == "WAITING"` | Prevents re-firing |

---

## §5 Execution Flow

1. **Init** — If resubmit → PurgePendingRequestsBeforeResubmit. function_id="104300002" (fixed). isSkipped=true
2. **POU loop** — OU-level PreExecCheck (GetXMLForOU, default chkRes="true")
3. **POU Priceplan extraction** — Loop Agreement.Offers:
   - **oldPP**: Offer where `ServiceType=80 AND FE_OR_CCBS="CCBS"` → OfferName
   - **newPP**: Offer where `ServiceType=80 AND FE_OR_CCBS="FE"` → OfferName
   - No error if not found — remains empty string
4. **POU Send** — Build SBM_FUP_DO_SERVICE (fupID=OUId, newPriceplan=newPP, previousPriceplan=oldPP). sendEventImmediate. RequestCount++ (if !resubmit). Audit via Event.sendEvent (async). isSkipped=false
5. **COU loop** — Same: GetXMLForChildOU + priceplan extraction + send
6. **Post-loop** — If !isSkipped → Status="1" + SendDataToDB. Else → SkipActivity("4")
7. **Exception** → HandleActivityException

---

## §7 Priceplan Extraction Algorithm

```java
for(int iOffer=0; iOffer<offerLen; iOffer++) {
    currOffer = ParentOU[iPOU].Agreement.Offers[iOffer];

    if(XPath.evalAsBoolean("$currOffer/ServiceType=80 and $currOffer/ExtendedInfo[Name='FE_OR_CCBS']/Value='CCBS'")) {
        oldPP = currOffer.OfferName;
        continue;
    }
    if(XPath.evalAsBoolean("$currOffer/ServiceType=80 and $currOffer/ExtendedInfo[Name='FE_OR_CCBS']/Value='FE'")) {
        newPP = currOffer.OfferName;
        continue;
    }
}
// No error thrown if either oldPP or newPP remains ""
```

### §7.1 Offer Match Criteria

| Variable | ServiceType | FE_OR_CCBS Value | Default if not found |
|----------|-------------|------------------|---------------------|
| `oldPP` (previous priceplan) | 80 | "CCBS" | `""` (no error) |
| `newPP` (new priceplan) | 80 | "FE" | `""` (no error) |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Param | POU Binding | COU Binding |
|-------|-------------|-------------|
| `orderRequest` | OrderRequest concept | same |
| `currPOU` | ParentOU[iPOU] concept | ChildOU[iCOU] concept |
| `function_id` | "104300002" (hardcoded) | same |
| `newPP` | FE_OR_CCBS="FE" OfferName | same (from COU offers) |
| `oldPP` | FE_OR_CCBS="CCBS" OfferName | same (from COU offers) |

### §9.3 JMS / Event Header Fields

| Header | Source | Conditional? |
|--------|--------|-------------|
| `JMSPriority` | `$orderRequest/OrderPriority` | [Conditional] |
| `JMSCorrelationID` | `$orderRequest/@extId` ⚠ NOT OMXTrackingId | [Conditional] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Conditional] |
| `RefID` | `$currPOU/RefId` | [Conditional: if $currPOU/RefId] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Conditional] |

### §9.5 Payload Parameters

| Key | Value | Conditional? |
|-----|-------|-------------|
| `function_id` | "104300002" (static) | [Always] |
| `fupID` | `$currPOU/OUId` | [Always] |
| `newPriceplan` | `$newPP` (may be "") | [Always] |
| `previousPriceplan` | `$oldPP` (may be "") | [Always] |

`ns:service_no` = `$currPOU/OUId`

### §9.8 XSLT Stylesheet Source

```xml
<xsl:stylesheet xmlns:ns="http://services.omx.truecorp.co.th/FMServices/SBMFUPDoserviceRequest" version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="currPOU"/>       <!-- ParentOU or ChildOU concept -->
  <xsl:param name="function_id"/>   <!-- "104300002" -->
  <xsl:param name="newPP"/>         <!-- new priceplan OfferName (FE_OR_CCBS="FE") -->
  <xsl:param name="oldPP"/>         <!-- old priceplan OfferName (FE_OR_CCBS="CCBS") -->
  <xsl:template match="/">
    <createEvent><event>
      <xsl:if test="$orderRequest/OrderPriority">
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      </xsl:if>
      <xsl:if test="$orderRequest/@extId">   <!-- @extId, NOT OrderData/OMXTrackingId -->
        <JMSCorrelationID><xsl:value-of select="$orderRequest/@extId"/></JMSCorrelationID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderID">
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      </xsl:if>
      <xsl:if test="$currPOU/RefId">
        <RefID><xsl:value-of select="$currPOU/RefId"/></RefID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderType">
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      </xsl:if>
      <payload><ns:doServiceRequest><ns:req>
        <ns:function_id><xsl:value-of select="$function_id"/></ns:function_id>
        <ns:parameters>
          <ns:item><ns:key>fupID</ns:key><ns:value><xsl:value-of select="$currPOU/OUId"/></ns:value></ns:item>
          <ns:item><ns:key>newPriceplan</ns:key><ns:value><xsl:value-of select="$newPP"/></ns:value></ns:item>
          <ns:item><ns:key>previousPriceplan</ns:key><ns:value><xsl:value-of select="$oldPP"/></ns:value></ns:item>
        </ns:parameters>
        <ns:service_no><xsl:value-of select="$currPOU/OUId"/></ns:service_no>
      </ns:req></ns:doServiceRequest></payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

COU and POU use the same stylesheet — `currPOU` parameter is bound to either `ParentOU[iPOU]` or `ChildOU[iCOU]`.

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority        ← $orderRequest/OrderPriority               [Conditional]
    ├── JMSCorrelationID   ← $orderRequest/@extId  ⚠NOT OMXTrackingId  [Conditional]
    ├── OrderID            ← $orderRequest/OrderData/OrderID           [Conditional]
    ├── RefID              ← $currPOU/RefId                            [Conditional: if $currPOU/RefId]
    ├── OrderType          ← $orderRequest/OrderData/OrderType         [Conditional]
    └── payload
        └── ns:doServiceRequest / ns:req
            ├── ns:function_id           ← $function_id ("104300002") [Always]
            ├── ns:parameters
            │   ├── ns:item[fupID]          ← $currPOU/OUId           [Always]
            │   ├── ns:item[newPriceplan]   ← $newPP (may be "")      [Always]
            │   └── ns:item[previousPriceplan] ← $oldPP (may be "")   [Always]
            └── ns:service_no            ← $currPOU/OUId              [Always]
```

---

## §11 Audit Logging

| Direction | OPERATION_NAME | AUDIT_TRACE | Send Method |
|-----------|---------------|-------------|-------------|
| Request | `"SBM_FUP_CHANGE_PP"` | `"Request Sent for SBM_FUP_CHANGE_PP"` | Event.sendEvent (ASYNC — inside chkRes block) |
| Response | `"SBM_FUP_CHANGE_PP"` | `"Response received for SBM_FUP_CHANGE_PP"` | Event.Ext.sendEventImmediate |

> Request audit uses `Event.sendEvent` (async) — fires only inside `if(chkRes=="true")` block, not unconditionally.

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one send | "1" IN_PROGRESS | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All OUs skipped | SKIPPED | `SkipActivity("4")` |

---

## §15 Function Dependency Tree

```text
Request_SBM_FUP_CHANGE_PP
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── GetXMLForOU(orderRequest, pOURefId)                         [POU PreExecCheck]
├── GetXMLForChildOU(orderRequest, cOURefId, pOURefId)          [COU PreExecCheck]
├── XPath.evalAsBoolean(ServiceType=80 + FE_OR_CCBS)            [offer extraction x2]
├── Event.Ext.sendEventImmediate(reqEvent)
├── RequestCount++ (if !resubmit)
├── Event.sendEvent(Logger)                                      [async, inside chkRes block]
├── GetActivityStatusString("1", false)
├── SkipActivity("4") | SendDataToDB
└── HandleActivityException(...)

Response_SBM_FUP_CHANGE_PP
├── Instance.createInstance(SBM_FUP_DoServiceRes)
├── Event.Ext.sendEventImmediate(Logger)
└── count(ResponseCode suffix "000") == RequestCount → "true"/"false"
```

---

## §17 Migration Notes & Recommendations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| JMSCorrelationID uses `@extId` not `OMXTrackingId` — response correlation may differ | [HIGH] | Verify SBM response routing; confirm @extId is unique per activity invocation |
| No OMX_DATA_ERROR if oldPP or newPP not found — empty string sent to SBM | [MEDIUM] | Add validation to throw DATA_ISSUE if either priceplan is empty |
| Async audit logger — may arrive out of order relative to the request | [LOW] | Switch to Event.Ext.sendEventImmediate if audit ordering required |
| Same XSLT for POU and COU via currPOU param | [LOW] | Verify COU loop correctly passes ChildOU as currPOU |

---

## §18 Full Source Code

```java
/**
 * @author SathidP-PC
 */
rule Rules.OMConsumers.OMXFM.Request.Request_SBM_FUP_CHANGE_PP {
    attribute { priority = 5; forwardChain = true; }
    when { ... ActivityID == "SBM_FUP_CHANGE_PP" ... }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            if(isActResub) PurgePendingRequestsBeforeResubmit(...);
            String function_id = "104300002";
            boolean isSkipped = true;

            for(int iPOU=0; iPOU<pOULen; iPOU++) {
                // OU-level PreExecCheck (default chkRes="true")
                if(String.equals(chkRes,"true")) {
                    String newPP = "", oldPP = "";
                    for(int iOffer=0; iOffer<offerLen; iOffer++) {
                        // oldPP: ServiceType=80 AND FE_OR_CCBS='CCBS'
                        // newPP: ServiceType=80 AND FE_OR_CCBS='FE'
                    }
                    reqEvent = Event.createEvent("xslt://...");
                    /* §9.8: params orderRequest, currPOU, function_id, newPP, oldPP
                       fupID=OUId; newPriceplan=newPP; previousPriceplan=oldPP
                       JMSCorrelationID=$orderRequest/@extId (NOT OMXTrackingId) */
                    Event.Ext.sendEventImmediate(reqEvent);
                    if(!isActResub) orderCurrentActivity.RequestCount++;
                    Event.sendEvent(Logger); // async, inside chkRes block
                    isSkipped = false;
                }
                // COU loop — same
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

Identical to other SBM FUP FMs: creates `SBM_FUP_DoServiceRes` with 7 SBM-specific fields; fan-in by count of successful responses; response audit via `Event.Ext.sendEventImmediate`. OPERATION_NAME="SBM_FUP_CHANGE_PP".

### §19.4 Fan-in Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

`if(currActivity.RequestCount == successResponseCount)` → "true" else "false"

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
