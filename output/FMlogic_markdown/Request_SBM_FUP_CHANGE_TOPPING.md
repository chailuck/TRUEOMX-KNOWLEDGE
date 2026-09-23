# Request_SBM_FUP_CHANGE_TOPPING

> Adds or removes FUP topping offers in SBM — OU-level iteration with OrderType-conditional offer scan and dynamic function_id.

**System:** SBM | **Priority:** 5 | **Author:** RS33-BANDIT  
**function_id:** 104300006 (ADD) / 104300007 (REMOVE) | **Pattern:** OU-level dual-loop + FUP offer scan  
**Fan-in:** count(success) == RequestCount | **Loop level:** OU (POU/COU)

> **Key difference from CHANGE_MEMBER:** This FM iterates over **OUs** (not subscribers). The `socElement` payload key carries comma-separated OfferNames built from a FUP offer scan. function_id is from `Parameter[1]` via xsl:choose. Two scan branches: OrderType=="2" (direct XPath) vs OrderType!="2" (full iteration with BRMS.AnyIn filter).

---

## §1 Overview & Purpose

Adds or removes FUP topping offers per OU in SBM using `function_id=104300006` (ADD) or `104300007` (REMOVE) based on `Parameter[1]`. Before sending, scans `Agreement.Offers` to build a comma-separated `fupElement` using an OrderType-conditional algorithm. Throws `OMX_DATA_ERROR` if no qualifying offers found per OU.

| Attribute | Value |
|-----------|-------|
| Rule File | `Request_SBM_FUP_CHANGE_TOPPING.rule` |
| Response File | `Response_SBM_FUP_CHANGE_TOPPING.rulefunction` |
| Author | RS33-BANDIT |
| Priority | 5 |
| Target System | SBM |
| function_id (ADD) | 104300006 |
| function_id (REMOVE) | 104300007 |
| Event name | SBM_FUP_DO_SERVICE (shared) |
| Parameter[1] | param ("ADD" or "REMOVE") |
| Parameter[2] | fe_or_ccbs_param (default "FE") |
| FUP offer scan | Required — OrderType-conditional |
| Send pattern | Event.Ext.sendEventImmediate + manual RequestCount++ |
| Fan-in | count(ResponseCode suffix "000") == RequestCount |
| JMSCorrelationID | OMXTrackingId (conditional) |

---

## §4 Rule Conditions (WHEN)

| Condition | Purpose |
|-----------|---------|
| `ActivityID == "SBM_FUP_CHANGE_TOPPING"` | FM match |
| `orderCurrentActivity.Status == "WAITING"` | Prevents re-firing |

---

## §5 Execution Flow

1. **Init** — If resubmit → PurgePendingRequestsBeforeResubmit. Resolve `param` from Parameter[1], `fe_or_ccbs_param` from Parameter[2] (default "FE"). Validate param: throw DATA_ISSUE if not "ADD" or "REMOVE"
2. **POU loop** — OU-level PreExecCheck (GetXMLForOU). If pass: FUP offer scan → build fupElement. Throw OMX_DATA_ERROR if fupElement=""
3. **POU FUP Offer Scan**:
   - **OrderType=="2"**: XPath → `Agreement/Offers[FE_OR_CCBS=fe_or_ccbs_param and ServiceType="80"]/OfferName`
   - **OrderType!="2"**: Loop Offers — include if: SPECIAL_OFFER_INDICATOR non-empty AND FE_OR_CCBS==fe_or_ccbs_param AND OfferActivityDate=="IM" AND BRMS.AnyIn(FUPAddToppingOfferInd, specialOfferInd). Build comma-separated fupElement
4. **POU Send** — Build SBM_FUP_DO_SERVICE (fupID=pOUId, socElement=fupElement). sendEventImmediate. RequestCount++ (if !resubmit). isSkipped=false. Send audit (always)
5. **COU loop** — Same: GetXMLForChildOU + FUP offer scan + send
6. **Post-loop** — If !isSkipped → Status="1" + SendDataToDB. Else → SkipActivity("4")
7. **Exception** → HandleActivityException

> **⚠ OMX_DATA_ERROR** thrown per-OU if no FUP offer found — partial sends may have occurred.  
> **⚠ Request audit fires on resubmit** (outside `if(!isActResub)` block) — duplicate logs per OU on resubmit.  
> **Note:** `isSkipped=false` set unconditionally (outside `if(!isActResub)`) — same as CHANGE_MEMBER.

---

## §7 FUP Offer Scan Algorithm

### §7.1 OrderType=="2" (Priceplan type)

```xpath
$currPOU/Agreement/Offers[
  ExtendedInfo/Name='FE_OR_CCBS'
  and ExtendedInfo/Value=$fe_or_ccbs_param
  and ServiceType='80'
]/OfferName
```

### §7.2 OrderType!="2" (Standard type)

```java
for(int iOffer=0; iOffer<offerLen; iOffer++) {
    specialOfferInd   = ExtendedInfo[Name="SPECIAL_OFFER_INDICATOR"]/Value
    fe_or_ccbs        = ExtendedInfo[Name="FE_OR_CCBS"]/Value
    OfferActivityDate = if (count(ExtendedInfo[Name="OfferActivityDate"])>0)
                        then ExtendedInfo[Name="OfferActivityDate"]/Value else "IM"

    if(String.length(specialOfferInd) > 0
        && String.equals(fe_or_ccbs, fe_or_ccbs_param)
        && String.equals("IM", OfferActivityDate)
        && BRMS.AnyIn(globalVariables/OMX_OM/FUP/FUPAddToppingOfferInd, specialOfferInd)) {
        // Append offer.OfferName to fupElement (comma-separated)
    }
}
if(fupElement == "") throw Exception.newException("OMX_DATA_ERROR",
    String.format("There is no FUP offer. OU: %s", OUId), null);
```

### §7.3 Offer Inclusion Criteria Summary

| Field | Condition | Applies to |
|-------|-----------|-----------|
| `ExtendedInfo[SPECIAL_OFFER_INDICATOR]/Value` | non-empty | OrderType!="2" only |
| `ExtendedInfo[FE_OR_CCBS]/Value` | == fe_or_ccbs_param (default "FE") | Both OrderType paths |
| `ExtendedInfo[OfferActivityDate]/Value` else "IM" | == "IM" | OrderType!="2" only |
| BRMS.AnyIn(FUPAddToppingOfferInd, specialOfferInd) | specialOfferInd in BRMS rule set | OrderType!="2" only |
| `ServiceType` | == "80" (OrderType=="2" path only) | OrderType=="2" only |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Param | POU Variant | COU Variant |
|-------|-------------|-------------|
| `orderRequest` | OrderRequest concept | same |
| `pOURefId` | `currPOU.RefId` | — |
| `cOURefId` | — | `currCOU.RefId` |
| `param` | "ADD" or "REMOVE" | same |
| `pOUId` | `currPOU.OUId` | — |
| `cOUId` | — | `currCOU.OUId` |
| `fupElement` | comma-separated offer names from scan | same |

### §9.3 JMS / Event Header Fields

| Header | Source | Conditional? |
|--------|--------|-------------|
| `JMSPriority` | `$orderRequest/OrderPriority` | [Conditional] |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | [Conditional] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Conditional] |
| `RefID` | `$pOURefId` or `$cOURefId` | [Always] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Conditional] |

### §9.5 Payload Parameters

| Key | Value | Conditional? |
|-----|-------|-------------|
| `function_id` | "104300006" (ADD) or "104300007" (REMOVE) via xsl:choose | [Always] |
| `fupID` | `$pOUId` or `$cOUId` | [Always] |
| `socElement` | `$fupElement` (comma-separated OfferNames) | [Always — non-empty, validated] |

`ns:service_no` = OUId

### §9.8 XSLT Stylesheet Source

**Variant ① — POU (params: orderRequest, pOURefId, param, pOUId, fupElement)**

```xml
<xsl:stylesheet xmlns:ns="http://services.omx.truecorp.co.th/FMServices/SBMFUPDoserviceRequest" version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="pOURefId"/>       <!-- POU RefId → RefID header -->
  <xsl:param name="param"/>          <!-- "ADD" or "REMOVE" -->
  <xsl:param name="pOUId"/>          <!-- POU OUId -->
  <xsl:param name="fupElement"/>     <!-- comma-separated OfferNames -->
  <xsl:template match="/">
    <createEvent><event>
      <!-- JMSPriority, JMSCorrelationID, OrderID, OrderType: conditional -->
      <RefID><xsl:value-of select="$pOURefId"/></RefID>
      <payload><ns:doServiceRequest><ns:req>
        <xsl:choose>
          <xsl:when test="$param='ADD'">
            <ns:function_id>104300006</ns:function_id>
          </xsl:when>
          <xsl:otherwise>
            <ns:function_id>104300007</ns:function_id>
          </xsl:otherwise>
        </xsl:choose>
        <ns:parameters>
          <ns:item><ns:key>fupID</ns:key><ns:value><xsl:value-of select="$pOUId"/></ns:value></ns:item>
          <ns:item><ns:key>socElement</ns:key><ns:value><xsl:value-of select="$fupElement"/></ns:value></ns:item>
        </ns:parameters>
        <ns:service_no><xsl:value-of select="$pOUId"/></ns:service_no>
      </ns:req></ns:doServiceRequest></payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

COU Variant ②: identical but uses `cOURefId` and `cOUId` params.

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority        ← $orderRequest/OrderPriority               [Conditional]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId     [Conditional]
    ├── OrderID            ← $orderRequest/OrderData/OrderID           [Conditional]
    ├── RefID              ← $pOURefId | $cOURefId                     [Always]
    ├── OrderType          ← $orderRequest/OrderData/OrderType         [Conditional]
    └── payload
        └── ns:doServiceRequest / ns:req
            ├── ns:function_id  ← "104300006"/"104300007" via xsl:choose  [Always]
            ├── ns:parameters
            │   ├── ns:item[fupID]      ← $pOUId | $cOUId             [Always]
            │   └── ns:item[socElement] ← $fupElement (non-empty)     [Always]
            └── ns:service_no           ← $pOUId | $cOUId             [Always]
```

---

## §11 Audit Logging

| Direction | OPERATION_NAME | AUDIT_TRACE | Send Method |
|-----------|---------------|-------------|-------------|
| Request | `"SBM_FUP_CHANGE_TOPPING"` | `"Request Sent for SBM_FUP_CHANGE_TOPPING"` | Event.Ext.sendEventImmediate (always, even resubmit) |
| Response | `"SBM_FUP_CHANGE_TOPPING"` | `"Response received for SBM_FUP_CHANGE_TOPPING"` | Event.Ext.sendEventImmediate |

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one send | "1" IN_PROGRESS | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All OUs skipped | SKIPPED | `SkipActivity("4")` |

---

## §15 Function Dependency Tree

```text
Request_SBM_FUP_CHANGE_TOPPING
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── BRMS.IsBlankOrStringNull(fe_or_ccbs_param)                   [default FE]
├── Exception.newException("DATA_ISSUE"...)                      [if param invalid]
├── GetXMLForOU(orderRequest, pOURefId)                         [POU PreExecCheck]
├── GetXMLForChildOU(orderRequest, cOURefId, pOURefId)          [COU PreExecCheck]
├── BRMS.AnyIn(FUPAddToppingOfferInd, specialOfferInd)           [offer filter]
├── Exception.newException("OMX_DATA_ERROR"...)                  [if fupElement==""]
├── Event.Ext.sendEventImmediate(reqEvent)
├── RequestCount++ (if !resubmit)
├── Event.Ext.sendEventImmediate(Logger)                         [always on send]
├── GetActivityStatusString("1", false)
├── SkipActivity("4") | SendDataToDB
└── HandleActivityException(...)

Response_SBM_FUP_CHANGE_TOPPING
├── Instance.createInstance(SBM_FUP_DoServiceRes)
├── Event.Ext.sendEventImmediate(Logger)
└── count(ResponseCode suffix "000") == RequestCount → "true"/"false"
```

---

## §17 Migration Notes & Recommendations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| OMX_DATA_ERROR thrown per-OU if no FUP offer found — partial send: some OUs may have sent before failure | [HIGH] | Add pre-validation pass across all OUs before any send; or handle partial state in resubmit |
| Request audit fires on resubmit — duplicate logs per OU | [MEDIUM] | Move Logger inside `if(!isActResub)` block |
| OrderType=="2" fast path uses direct XPath (no BRMS filter, no OfferActivityDate check) | [LOW] | Verify that OrderType=="2" context always has correct offers pre-filtered |
| OfferActivityDate defaults to "IM" if ExtendedInfo absent — all offers without OfferActivityDate are included | [MEDIUM] | Consider explicit exclusion if OfferActivityDate is absent vs "IM" |

---

## §18 Full Source Code

```java
/**
 * @author RS33-BANDIT
 */
rule Rules.OMConsumers.OMXFM.Request.Request_SBM_FUP_CHANGE_TOPPING {
    attribute { priority = 5; forwardChain = true; }
    when { ... ActivityID == "SBM_FUP_CHANGE_TOPPING" ... }
    then {
        boolean isActResub = ...;
        try {
            if(isActResub) PurgePendingRequestsBeforeResubmit(...);
            String param = XPath("nextAct/Parameter[1]");    // "ADD" or "REMOVE"
            String fe_or_ccbs_param = XPath("nextAct/Parameter[2]"); // default "FE"
            if(BRMS.IsBlankOrStringNull(fe_or_ccbs_param)) fe_or_ccbs_param = "FE";
            if(!("ADD" || "REMOVE")) throw DATA_ISSUE;

            for(int iPOU=0; iPOU<pOuLen; iPOU++) {
                // OU-level PreExecCheck
                if(chkRes=="true") {
                    String fupElement = "";
                    if(OrderType=="2") {
                        fupElement = XPath("Agreement/Offers[FE_OR_CCBS=fe_or_ccbs_param and ServiceType='80']/OfferName");
                    } else {
                        // Loop Offers: SPECIAL_OFFER_INDICATOR + FE_OR_CCBS + OfferActivityDate=="IM"
                        // + BRMS.AnyIn(FUPAddToppingOfferInd, specialOfferInd)
                        // Build comma-separated fupElement from OfferName
                    }
                    if(fupElement=="") throw OMX_DATA_ERROR("There is no FUP offer. OU: %s");
                    reqEvent = Event.createEvent("xslt://...");
                    /* §9.8 Variant ①: params orderRequest, pOURefId, param, pOUId, fupElement
                       function_id=104300006/104300007; fupID=pOUId; socElement=fupElement */
                    Event.Ext.sendEventImmediate(reqEvent);
                    if(!isActResub) orderCurrentActivity.RequestCount++;
                    isSkipped = false;
                    Event.Ext.sendEventImmediate(Logger); // always
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

Identical to other SBM FUP FMs: creates `SBM_FUP_DoServiceRes` with 7 SBM-specific fields; fan-in by count of successful responses; response audit via `Event.Ext.sendEventImmediate`. OPERATION_NAME="SBM_FUP_CHANGE_TOPPING".

### §19.4 Fan-in Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)='000'])
```

`if(currActivity.RequestCount == successResponseCount)` → "true" else "false"

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
