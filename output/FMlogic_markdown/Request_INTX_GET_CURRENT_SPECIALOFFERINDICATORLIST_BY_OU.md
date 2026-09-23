# Request_INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU

> Retrieves special offer indicator lists from INTX per OU with paged requests and Subscriber.SubscriberOffers data enrichment.

**System:** INTX | **Priority:** 5 | **Author:** usuf c  
**Pattern:** Paged dual-loop POU/COU + direct send | **Fan-in:** count(success) == RequestCount  
**JMSCorrelationID:** OMXTrackingId (not @extId) | **Parameters:** PAGE_SIZE, specialOfferIndicatorParam

---

## §1 Overview & Purpose

Retrieves the current special offer indicator list from INTX per OU using a **two-pass paged design**:

| Pass | PAGE_SIZE | Purpose | Response action |
|------|-----------|---------|-----------------|
| Pass 1 (step 64) | `"1"` | Get total offer count | Writes `OFFERS_BY_INDICATION_TOTAL_SIZE` → `pou.ExtendedInfo` |
| Pass 2 (step 65) | Configured | Retrieve actual pages of offer data | Enriches `Subscriber.SubscriberOffers` with SPECIAL_OFFER_INDICATOR + FE_OR_CCBS |

`specialOfferIndicatorParam` (Parameter[2]) defaults to `"FCA"` if blank.

| Attribute | Value |
|-----------|-------|
| Rule File | `Request_INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU.rule` |
| Response File | `Response_INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU.rulefunction` |
| Author | usuf c |
| Priority | 5 |
| Target System | INTX |
| Operation | GetSpecialOfferIndListByOU |
| Send pattern | Event.Ext.sendEventImmediate + manual RequestCount++ (per page per OU) |
| Audit send | Event.Ext.sendEventImmediate (request), Event.sendEvent async (response) |
| Fan-in | count(ResponseCode suffix "000") == RequestCount |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` (not @extId) |

---

## §4 Rule Conditions (WHEN)

| Condition | Purpose |
|-----------|---------|
| `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity pointer match |
| `orderCurrentActivity.ActivityID == "INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU"` | Specific FM match |
| `orderRequest.ProcessFlow.NextActivityID == "INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU"` | Process flow alignment |
| `orderCurrentActivity.Status == "WAITING"` | Prevents re-firing |

---

## §5 Execution Flow

1. **Init** — Get `nextAct`, resolve `specialOfferIndicatorParam` (default "FCA"), `isSkipped=true`. If resubmit → PurgePendingRequestsBeforeResubmit
2. **Outer POU Loop** → PreExecCheck gate. Compute paging: `total` from `OFFERS_BY_INDICATION_TOTAL_SIZE` (default 1), `iteration=ceil(total/size)`
3. **POU Page Loop** `for pageNumber=0..iteration-1` — CompletionStatus==2 check (uses COUrefId="" ⚠). Send + RequestCount++ + audit
4. **Inner COU Loop** — Same paging with GetXMLForChildOU + COUrefId CompletionStatus==2 check
5. **Post-loop** — If !isSkipped → Status="1" + SendDataToDB. Else → SkipActivity("4")
6. **Exception** → HandleActivityException

> **⚠ Bug:** POU CompletionStatus==2 check uses `COUrefId` which is `""` at that point — skip never triggers for POU on resubmit. Should use `POUrefId`.

---

## §7 Data Extraction — Paging Calculation

### §7.1 Paging Parameters

| Variable | Source | Default | Notes |
|----------|--------|---------|-------|
| `pageSize` | `GetActivityParamValueFromKey(nextAct, "PAGE_SIZE")` | `"1"` | Pass 1: always 1 |
| `size` | `Number.doubleValue(pageSize)` | 1.0 | |
| `total` | `parentOU/ExtendedInfo[OFFERS_BY_INDICATION_TOTAL_SIZE]/Value` else `"1"` | 1.0 | Set by Pass 1 response |
| `iteration` | `Math.ceil(total / size)` | 1 | Pages to send per OU |
| `pageNumber` | Loop 0..iteration-1 | — | Sent as `ns:pageNumber+1` (1-based) |

### §7.2 specialOfferIndicatorParam Resolution

```java
specialOfferIndicatorParam = XPath.evalAsString(orderCurrentActivity/Parameter[2]);
if(BRMS.IsBlankOrStringNull(specialOfferIndicatorParam)) specialOfferIndicatorParam = "FCA";
```

---

## §8 System & Integration Dependencies

### §8.3 Backend API Details

| System | Operation | Schema NS | Protocol |
|--------|-----------|-----------|---------|
| INTX | GetSpecialOfferIndListByOU | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetSpecialOfferIndListByOU.xsd` | JMS + XSLT |

### §8.5 ExtendedInfo Fields Required

| Name | Required/Optional | Used In |
|------|-----------------|---------|
| `OFFERS_BY_INDICATION_TOTAL_SIZE` | [Optional] | Request: paging total; Response Pass 1: written to pou.ExtendedInfo |

### §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Gate for UserName/Password in request |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit: COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit: TARGET_SYSTEM |
| `OMX_OM/WritePayload` | Gate for payload logging |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

> Both POU and COU variants share the same XSLT stylesheet. The `parentOU` param receives ParentOU for POU loop and also ParentOU for COU loop (COU XSLT uses `$parentOU/OUId` even in the COU iteration).

| Param | Binding (POU) | Binding (COU) |
|-------|---------------|---------------|
| `orderRequest` | OrderRequest concept | same |
| `parentOU` | current ParentOU | current ParentOU |
| `globalVariables` | global vars | same |
| `specialOfferIndicatorParam` | Parameter[2] default "FCA" | same |
| `pageSize` | from PAGE_SIZE, default "1" | same |
| `pageNumber` | loop 0..iteration-1 | same |

### §9.3 JMS / Event Header Fields

| Header | Source | Conditional? |
|--------|--------|-------------|
| `extId` (attribute) | `OMXUtils:generateTrackingID()` | [Always] |
| `JMSPriority` | `$orderRequest/OrderPriority` | [Always] |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | [Always] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Always] |
| `RefID` | `$parentOU/RefId` | [Always] |
| `UserName` | `$orderRequest/OrderData/User` | [Conditional: IsEnableUserPass='true'] |
| `PassWord` | `$orderRequest/OrderData/Password` | [Conditional: IsEnableUserPass='true'] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Always] |

### §9.5 Payload Parameters

| Element | Source |
|---------|--------|
| `ns:correlatedId` | `$orderRequest/OrderData/OMXTrackingId` |
| `ns:ouId` | `$parentOU/OUId` |
| `ns:specialOfferIndicator` | `$specialOfferIndicatorParam` (default "FCA") |
| `ns:pageSize` | `$pageSize` |
| `ns:pageNumber` | `($pageNumber+1)` — 1-based |

### §9.8 XSLT Stylesheet Source (shared POU/COU Variant)

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetSpecialOfferIndListByOU.xsd"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema" version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="parentOU"/>           <!-- POU or parent of COU -->
  <xsl:param name="globalVariables"/>
  <xsl:param name="specialOfferIndicatorParam"/>  <!-- default "FCA" -->
  <xsl:param name="pageSize"/>
  <xsl:param name="pageNumber"/>         <!-- 0-based; sent as pageNumber+1 -->
  <xsl:template match="/">
    <createEvent><event>
      <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
      <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      <RefID><xsl:value-of select="$parentOU/RefId"/></RefID>
      <xsl:if test="$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass='true'">
        <UserName><xsl:value-of select="$orderRequest/OrderData/User"/></UserName>
        <PassWord><xsl:value-of select="$orderRequest/OrderData/Password"/></PassWord>
      </xsl:if>
      <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      <payload>
        <ns:GetSpecialOfferIndListByOUReq>
          <ns:correlatedId><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></ns:correlatedId>
          <ns:ouId><xsl:value-of select="$parentOU/OUId"/></ns:ouId>
          <ns:specialOfferIndicator><xsl:value-of select="$specialOfferIndicatorParam"/></ns:specialOfferIndicator>
          <ns:pageSize><xsl:value-of select="$pageSize"/></ns:pageSize>
          <ns:pageNumber><xsl:value-of select="($pageNumber+1)"/></ns:pageNumber>
        </ns:GetSpecialOfferIndListByOUReq>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event @extId ← OMXUtils:generateTrackingID()             [Always]
    ├── JMSPriority        ← $orderRequest/OrderPriority      [Always]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId  [Always]
    ├── OrderID            ← $orderRequest/OrderData/OrderID  [Always]
    ├── RefID              ← $parentOU/RefId                  [Always]
    ├── UserName           ← $orderRequest/OrderData/User     [Conditional: IsEnableUserPass='true']
    ├── PassWord           ← $orderRequest/OrderData/Password [Conditional: IsEnableUserPass='true']
    ├── OrderType          ← $orderRequest/OrderData/OrderType [Always]
    └── payload
        └── ns:GetSpecialOfferIndListByOUReq
            ├── ns:correlatedId    ← $orderRequest/OrderData/OMXTrackingId [Always]
            ├── ns:ouId            ← $parentOU/OUId                        [Always]
            ├── ns:specialOfferIndicator ← $specialOfferIndicatorParam (default "FCA") [Always]
            ├── ns:pageSize        ← $pageSize                             [Always]
            └── ns:pageNumber      ← ($pageNumber+1)  1-based              [Always]
```

---

## §11 Audit Logging

| Direction | OPERATION_NAME | AUDIT_TRACE | Send method |
|-----------|---------------|-------------|-------------|
| Request | `"INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU"` | `"Request Sent for INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU"` | Event.Ext.sendEventImmediate |
| Response | `"INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU"` | `"Response received for INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU"` | Event.sendEvent (async) |

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one send | "1" IN_PROGRESS | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All OUs skipped | SKIPPED | `SkipActivity("4")` |

---

## §15 Function Dependency Tree

```text
Request_INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── BRMS.IsBlankOrStringNull(specialOfferIndicatorParam)         [default FCA]
├── GetActivityParamValueFromKey(nextAct, "PAGE_SIZE")           [paging]
├── GetXMLForOU(orderRequest, POUrefId)                          [POU PreExecCheck]
├── GetXMLForChildOU(orderRequest, COUrefId, POUrefId)           [COU PreExecCheck]
├── Event.Ext.sendEventImmediate(reqEvent)                       [direct send per page]
├── RequestCount++ (manual, per page)
├── Event.Ext.sendEventImmediate(Logger)                         [request audit]
├── GetActivityStatusString("1", false)
├── SkipActivity("4") | SendDataToDB
└── HandleActivityException(...)

Response_INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU
├── Instance.createInstance(OSBBaseRes)
├── XPath.evalAsInt(totalSize from GetSpecialOfferIndListByOURes)
├── GetActivityParamValueFromKey(currActivity, "PAGE_SIZE")
├── [Pass 1] Instance.createInstance(OUExtendedInfo) → pou.ExtendedInfo++ (OFFERS_BY_INDICATION_TOTAL_SIZE)
├── [Pass 2] XPath.evalAsString(offer/code) + evalAsBoolean(exists check)
│    ├── [exists] Instance.createInstance(SubscriberOffersExtendedInfo) → add SPECIAL_OFFER_INDICATOR
│    └── [new]    Instance.createInstance(SubscriberOffers) → Soc + FE_OR_CCBS + SPECIAL_OFFER_INDICATOR
├── Event.sendEvent(Logger)                                      [async response audit]
└── count(ResponseCode suffix "000") == RequestCount → "true"/"false"
```

---

## §17 Migration Notes & Recommendations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| POU CompletionStatus==2 check uses `COUrefId=""` — skip never triggers on resubmit | [HIGH] | Replace `COUrefId` with `POUrefId` in POU CompletionStatus check block |
| Two-pass design requires exact ProcessConfig sequencing (step 64 PAGE_SIZE=1 before step 65) | [MEDIUM] | Document and enforce; add guard if OFFERS_BY_INDICATION_TOTAL_SIZE not set |
| Paging race: multiple RequestCount++ per OU — fan-in requires ALL page responses | [MEDIUM] | Monitor partial page responses; ensure INTX pagination stability |
| Request audit uses Ext.sendEventImmediate — adds latency per page | [LOW] | Change to Event.sendEvent for audit if latency is a concern |

---

## §18 Full Source Code

```java
/**
 * @author usuf c
 */
rule Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU {
    attribute { priority = 5; forwardChain = true; }
    when { ... ActivityID == "INTX_GET_CURRENT_SPECIALOFFERINDICATORLIST_BY_OU" ... }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
        try {
            Activity nextAct = Instance.getByExtIdByUri(nextActivityName, ...);
            if(isActResub) PurgePendingRequestsBeforeResubmit(...);

            // Parameter[2] = specialOfferIndicatorParam; default "FCA"
            String specialOfferIndicatorParam = XPath.evalAsString("orderCurrentActivity/Parameter[2]");
            if(BRMS.IsBlankOrStringNull(specialOfferIndicatorParam)) specialOfferIndicatorParam = "FCA";

            for(int i=0; i<iPOULen; i++) {
                ParentOU parentOU = orderRequest.OrderData.Customer.ParentOU[i];
                if(chkRes == "true") {
                    String pageSize = GetActivityParamValueFromKey(nextAct, "PAGE_SIZE"); // default "1"
                    double total = XPath.evalAsDouble("parentOU/ExtendedInfo[OFFERS_BY_INDICATION_TOTAL_SIZE]"); // else 1
                    int iteration = Math.ceil(total / size);
                    for(int pageNumber=0; pageNumber<iteration; pageNumber++) {
                        // CompletionStatus==2 check using COUrefId ⚠ (bug: should use POUrefId)
                        if(!reqSuccess) {
                            reqEvent = Event.createEvent("xslt://...");
                            /* See §9.8: params orderRequest, parentOU, globalVariables,
                               specialOfferIndicatorParam, pageSize, pageNumber */
                            Event.Ext.sendEventImmediate(reqEvent);
                            if(!isActResub) { orderCurrentActivity.RequestCount++; isSkipped=false; }
                            Event.Ext.sendEventImmediate(Event.createEvent("xslt://Logger..."));
                        }
                    }
                }
                // COU loop — same paging, uses COUrefId for CompletionStatus check
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

Two-mode response handler based on `pageSize`:
- **Pass 1** (`pageSize=="1"`): Writes `OFFERS_BY_INDICATION_TOTAL_SIZE = totalSize` into `pou.ExtendedInfo`
- **Pass 2** (`pageSize>1`): Enriches `Subscriber.SubscriberOffers` — updates existing SOC entries with `SPECIAL_OFFER_INDICATOR`, or creates new entries with `FE_OR_CCBS="CCBS"` + `SPECIAL_OFFER_INDICATOR`

### §19.3 OSBBaseRes Construction

```text
OSBBaseRes @extId ← OMXUtils:generateTrackingID()
├── ResponseCode    ← $eventResponse/ResponseCode    [Conditional]
├── ResponseMessage ← $eventResponse/ResponseMsg     [Conditional]
├── CompletionStatus← $eventResponse/CompletionStatus [Conditional]
└── ReferenceId     ← $eventResponse/RefID           [Conditional]
```

### §19.4 Pass 2 — Offer Enrichment Logic

```java
for(int ret=0; ret<totalSize; ret++) {
    socCodeFromResponse = XPath("agreementSpecialOfferArray[$ret+1]/offer/code");
    if(count(subscriberFromOrderRequest.SubscriberOffers[Soc=socCodeFromResponse])>0) {
        // Update existing: add SubscriberOffersExtendedInfo
        // Name=SPECIAL_OFFER_INDICATOR, Value=specialOfferIndicator (conditional)
    } else {
        // Create new SubscriberOffers:
        //   OfferName (conditional), ServiceType (conditional), Soc (conditional)
        //   ExtendedInfo[FE_OR_CCBS="CCBS"] (always)
        //   ExtendedInfo[SPECIAL_OFFER_INDICATOR] (conditional)
        subscriberFromOrderRequest.SubscriberOffers[length] = subOfferConcept;
    }
}
```

### §19.5 Fan-in Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

`if(currActivity.RequestCount == successResponseCount)` → return "true" else "false"

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
