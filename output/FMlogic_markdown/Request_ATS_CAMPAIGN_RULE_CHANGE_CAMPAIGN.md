# Request_ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN

> TIBCO BusinessEvents FM Logic — ATS Campaign Rule Change Campaign Request Handler

**Priority:** 5 | **ForwardChain:** true | **Backend:** ATS | **Operation:** ChangeCampaign | **Dispatch:** sendEventImmediate | **Fan-out:** per-BundleInfo | **Fan-in:** ResponseCode suffix "000"

---

## §1 — Overview & Purpose

This rule fires when `ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN` becomes the next activity in the order process flow. It sends one **ChangeCampaign** request to ATS per `BundleInfo` entry in the order, instructing ATS to update convergence campaign rules for all subscribers linked to that bundle. The request payload carries the CampaignCode, ConvergenceType, and a product list of matching TMV subscribers with their current SOC offers, price plan, and contract metadata.

If no `BundleInfo` entries exist the step is skipped via `SkipActivity("4")`. The response handler enriches working memory by writing the ATS-resolved `ConvergenceAction` back to the `BundleInfo` concept and updating each subscriber's `SubscriberOffers.Action` and `FE_OR_CCBS` extended-info based on the `benefitCampaignList` returned by ATS.

> **Fan-out pattern:** Operates at **order-level BundleInfo fan-out** — one request per bundle (not per subscriber). Subscribers are aggregated into a single request's `productList` by matching `ExtendedInfo[Name='CampaignCode']/Value` against the bundle's `CampaignCode`.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN` |
| Priority | 5 |
| ForwardChain | true |
| Rule type | Request dispatcher |
| Target backend | ATS — Campaign Management |
| Operation | ChangeCampaign (`ns:requestName = "ChangeCampaign"`) |
| Channel | OMX-Mobile (`ns:channel = "OMX-Mobile"`) |
| Dispatch method | `Event.Ext.sendEventImmediate` |
| Request event type | `Events.OMConsumers.OMXFM.Request.ATS_CAMPAIGN_RULE` |
| Response event type | `Events.OMConsumers.OMXFM.Response.ATS_CAMPAIGN_RULE` |
| Fan-out granularity | Per BundleInfo (order-level) |
| Fan-in mechanism | ResponseCode suffix "000" count vs RequestCount |
| Skip trigger | BundleInfo count = 0 → SkipActivity("4") |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order concept; provides BundleInfo array, subscriber data, order metadata |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step; provides Status, RequestCount, Response[] |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to current order's next step |
| 2 | `orderCurrentActivity.ActivityID == "ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN"` | Ensures this rule fires only for this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN"` | Double-check on ProcessFlow routing state |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be waiting before dispatch |

---

## §5 — Execution Flow Diagram

```
1. Compute isActResub = (RequestCount > 0 && IsOrderResubmitted)
2. Resolve activity by extId; read PreExecCheck XPath
3. If PreExecCheck present → serialize orderRequest and evaluate XPath → store in chkRes
4. If chkRes == "true" → count BundleInfo elements in orderRequest.OrderData
5. For each BundleInfo[i] → build ATS_CAMPAIGN_RULE request event via XSLT
6. Dispatch each request via Event.Ext.sendEventImmediate
7. If !isActResub → increment orderCurrentActivity.RequestCount++
8. Send audit log event (OPERATION_NAME = "ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN")
9. Mark isSkipped = false
10. If any request sent → set activity Status = "1"; call SendDataToDB
11. If no requests sent (skipped) → call SkipActivity(orderRequest, orderCurrentActivity, "4")
12. On exception → call HandleActivityException
```

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### Resubmission flag
`boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);` — prevents double-incrementing RequestCount on retry.

### PreExecCheck gate
If `nextAct.PreExecCheck` is non-empty, the rule serializes `orderRequest` using `Instance.serializeUsingDefaults` and evaluates the XPath string. Only if result is "true" does dispatch proceed.

### BundleInfo fan-out
Counts `orderRequest/OrderData/BundleInfo` elements. For each index `i`, creates one `ATS_CAMPAIGN_RULE` request event and dispatches it immediately. The payload includes:
- channel = "OMX-Mobile", requestName = "ChangeCampaign"
- function = `BundleInfo[$i+1]/ConvergenceType`
- convergenceCode = `BundleInfo[$i+1]/CampaignCode`
- A `productList` per subscriber whose `ExtendedInfo[Name='CampaignCode']/Value` matches the bundle's CampaignCode

### nextRCnextPP (null fallback)
> **[MEDIUM] Risk:** The variable `nextRCnextPP` is declared and initialized to `null` but is never populated. It is used as fallback for `rcRate`, `nextRcRate`, and `nextPricePlan` in the XSLT. Those fields will be empty string when CCBS SubscriberOffers data is absent.

### Skip and status transitions

| Scenario | Action | Status |
|----------|--------|--------|
| BundleInfo count = 0 (after PreExecCheck) | SkipActivity("4") | Skip |
| PreExecCheck returns "false" | SkipActivity("4") | Skip |
| At least 1 request dispatched | Status = "1", SendDataToDB | Running |
| Exception | HandleActivityException | Error |

---

## §7 — Data Extraction

No pipe-delimited or GROUP-format parsing. Data is extracted via XPath directly from in-memory concepts:

| Field | Source XPath | Notes |
|-------|-------------|-------|
| BundleInfo count | `count($orderRequest/OrderData/BundleInfo)` | Drives fan-out loop count |
| ConvergenceType | `$orderRequest/OrderData/BundleInfo[$i+1]/ConvergenceType` | Maps to ns:function |
| CampaignCode | `$orderRequest/OrderData/BundleInfo[$i+1]/CampaignCode` | Maps to ns:convergenceCode; filter for subscriber selection |
| Subscriber filter | `Subscriber[contains(ExtendedInfo[Name='CampaignCode']/Value, CampaignCode)]` | Substring match — see §17 risk note |
| rcRate (CCBS) | `SubscriberOffers[ServiceType='80' and FE_OR_CCBS='CCBS']/OfferRate` | Null fallback if absent |
| nextRcRate (FE) | `SubscriberOffers[ServiceType='80' and FE_OR_CCBS='FE']/OfferRate` | Null fallback if absent |
| pricePlan | `SubscriberOffers[ServiceType='80' and FE_OR_CCBS='CCBS']/OfferName` | Conditional (xsl:if) |
| nextPricePlan | `SubscriberOffers[ServiceType='80' and FE_OR_CCBS='FE']/OfferName` | Null fallback if absent |
| Contract SOCs | `SubscriberOffers[ServiceType='85' and TR_CONTRACT_IND=Y and !expired]` | Date-filtered; non-expired only |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

| OrderType | SOC list (socListInfo) logic |
|-----------|------------------------------|
| 4 + FE_OR_CCBS=ATS | Loops ServiceType=85 with TR_CONTRACT_IND=Y, non-expired; contractNew="Existing" |
| 4 + FE_OR_CCBS != ATS | Loops FE SubscriberOffers; contractNew="New" if FE, else "Existing" |
| Other | Loops ServiceType=85 with TR_CONTRACT_IND=Y, non-expired; contractNew by FE_OR_CCBS |

When OrderType=4 and FE_OR_CCBS != ATS: appends `ns:extendedInfo` with name=REMOVE_CONTRACT value=Y.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Dispatch | Backend |
|-----------|-----------|---------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.ATS_CAMPAIGN_RULE` | `Event.Ext.sendEventImmediate` | ATS — ChangeCampaign |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `Event.Ext.sendEventImmediate` | Audit log sink |

### §8.3 — Backend API Details

| System | Operation | Schema NS | Key Fields Sent |
|--------|-----------|-----------|-----------------|
| ATS | ChangeCampaign | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ATS/CampaignRule.xsd` | channel, requestName, function(ConvergenceType), convergenceCode(CampaignCode), productList[] |

### §8.4 — BE Working Memory Dependencies

| Concept Field | Access | Purpose |
|--------------|--------|---------|
| `orderRequest.OrderData.BundleInfo[*]` | READ | Fan-out source; CampaignCode + ConvergenceType drive request |
| `orderRequest.OrderData.OrderID` | READ | Request correlation |
| `orderRequest.OrderData.OMXTrackingId` | READ | JMSCorrelationID; audit ESBUUID |
| `orderRequest.OrderData.Customer.RefId` | READ | RefID in request |
| `orderRequest.OrderData.OrderType` | READ | Drives SOC list branching and REMOVE_CONTRACT logic |
| `orderRequest.OrderPriority` | READ | JMSPriority |
| `Subscriber.MSISDN` | READ | accessNumber in productList |
| `Subscriber.ExtendedInfo[Name='CampaignCode']/Value` | READ | Filter: subscriber belongs to bundle |
| `Subscriber.ExtendedInfo[Name='FamilyType']/Value` | READ | familyType (conditional) |
| `Subscriber.ExtendedInfo[Name='FE_OR_CCBS']/Value` | READ | isChange logic; OrderType=4 SOC branching |
| `SubscriberOffers[ServiceType='80']` | READ | rcRate/nextRcRate/pricePlan/nextPricePlan |
| `SubscriberOffers[ServiceType='85']` | READ | Contract SOCs (socListInfo) |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-in counter |
| `orderCurrentActivity.Status` | WRITE | Set to "1" after dispatch |

### §8.5 — ExtendedInfo Fields Required

| Name | Required/Optional | Where Used |
|------|------------------|-----------|
| CampaignCode | Required (filter) | Subscriber selection for productList |
| FamilyType | Optional | ns:familyType in productList |
| FE_OR_CCBS | Required | isChange flag; OrderType=4 SOC branching; REMOVE_CONTRACT trigger |

### §8.6 — Global Variable Dependencies

| Path | Usage |
|------|-------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Guards payload in audit log |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Purpose |
|-----------|-----------|---------|
| `$orderRequest` | orderRequest (working memory concept) | Order data source |
| `$i` | Loop index (0-based) | BundleInfo array index |
| `$nextRCnextPP` | `null` (never set) | Fallback for rate/plan fields (always empty) |

### §9.2 — Event Container Construction
Event extId generated via `OMXUtils:generateTrackingID()`.

### §9.3 — JMS / Event Header Fields

| Field | Source |
|-------|--------|
| JMSPriority | `$orderRequest/OrderPriority` |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` |
| OrderID | `$orderRequest/OrderData/OrderID` |
| RefID | `$orderRequest/OrderData/Customer/RefId` |
| OrderType | `$orderRequest/OrderData/OrderType` |

### §9.4 — Payload Root Element
Root: `ns:CampaignRuleRequest` (ns = `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ATS/CampaignRule.xsd`)

### §9.5 — Conditional Fields

| Field | Condition | Value when met |
|-------|-----------|---------------|
| ns:familyType | `ExtendedInfo[Name='FamilyType']/Value` exists | FamilyType value |
| ns:pricePlan | `SubscriberOffers[ServiceType='80' and CCBS]/OfferName` exists | CCBS offer name |
| socListInfo (contract SOC) | ServiceType=85, TR_CONTRACT_IND=Y, non-expired | soc, serviceType, contractInd=Y, contractNew |
| ns:extendedInfo[REMOVE_CONTRACT=Y] | OrderType=4 AND FE_OR_CCBS != ATS | name=REMOVE_CONTRACT, value=Y |

### §9.6 — Core Payload / Product Block

| Element | Value |
|---------|-------|
| ns:productType | "TMV" (static) |
| ns:accessNumber | MSISDN |
| ns:familyType | FamilyType extended-info (if present) |
| ns:isChange | "N" if FE_OR_CCBS=ATS; "Y" otherwise |
| ns:rcRate | CCBS offer rate (ServiceType=80, CCBS); null fallback |
| ns:nextRcRate | FE offer rate (ServiceType=80, FE); null fallback |
| ns:pricePlan | CCBS offer name if present |
| ns:nextPricePlan | FE offer name if present; null fallback |
| ns:socListInfo[*] | Contract SOCs (ServiceType=85, TR_CONTRACT_IND=Y, non-expired) |
| ns:extendedInfo[REMOVE_CONTRACT] | Only when OrderType=4 and not ATS |

### §9.7 — Complete Generated XML Example

```xml
<!-- ATS_CAMPAIGN_RULE request — one per BundleInfo -->
<ns:CampaignRuleRequest>
  <ns:channel>OMX-Mobile</ns:channel>
  <ns:requestName>ChangeCampaign</ns:requestName>
  <ns:function>MobileSoftBundle</ns:function>       <!-- ConvergenceType -->
  <ns:convergenceCode>CAMP001</ns:convergenceCode> <!-- CampaignCode -->
  <ns:productList>
    <ns:productType>TMV</ns:productType>
    <ns:accessNumber>0812345678</ns:accessNumber>
    <ns:familyType>MAIN</ns:familyType>             <!-- if FamilyType present -->
    <ns:isChange>Y</ns:isChange>                   <!-- N if FE_OR_CCBS=ATS -->
    <ns:tmhProductInfo>
      <ns:rcRate>599</ns:rcRate>
      <ns:nextRcRate>699</ns:nextRcRate>
      <ns:pricePlan>TRUE_PP_599</ns:pricePlan>
      <ns:nextPricePlan>TRUE_PP_699</ns:nextPricePlan>
      <ns:socListInfo>
        <ns:soc>SOC_CONTRACT_01</ns:soc>
        <ns:serviceType>85</ns:serviceType>
        <ns:contractInd>Y</ns:contractInd>
        <ns:contractNew>Existing</ns:contractNew>
      </ns:socListInfo>
      <!-- OrderType=4, not ATS: -->
      <ns:extendedInfo>
        <ns:name>REMOVE_CONTRACT</ns:name>
        <ns:value>Y</ns:value>
      </ns:extendedInfo>
    </ns:tmhProductInfo>
  </ns:productList>
</ns:CampaignRuleRequest>
```

### §9.8 — XSLT Stylesheet Source

```xml
<!-- Request XSLT — ATS_CAMPAIGN_RULE event; one per BundleInfo[i] -->
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ATS/CampaignRule.xsd"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
  version="1.0">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>  <!-- bound from orderRequest concept -->
  <xsl:param name="i"/>             <!-- loop index (0-based) -->
  <xsl:param name="nextRCnextPP"/> <!-- always null — empty fallback -->
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <RefID><xsl:value-of select="$orderRequest/OrderData/Customer/RefId"/></RefID>
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        <payload>
          <ns:CampaignRuleRequest>
            <ns:channel>OMX-Mobile</ns:channel>
            <ns:requestName>ChangeCampaign</ns:requestName>
            <ns:function><xsl:value-of select="$orderRequest/OrderData/BundleInfo[$i+1]/ConvergenceType"/></ns:function>
            <ns:convergenceCode><xsl:value-of select="$orderRequest/OrderData/BundleInfo[$i+1]/CampaignCode"/></ns:convergenceCode>
            <!-- Select subscribers whose CampaignCode ExtendedInfo matches this bundle -->
            <xsl:for-each select="$orderRequest/OrderData/Customer/ParentOU/Subscriber[contains(ExtendedInfo[Name='CampaignCode']/Value,$orderRequest/OrderData/BundleInfo[$i+1]/CampaignCode)]">
              <ns:productList>
                <ns:productType>TMV</ns:productType>
                <ns:accessNumber><xsl:value-of select="MSISDN"/></ns:accessNumber>
                <xsl:if test="ExtendedInfo[Name='FamilyType']/Value">
                  <ns:familyType><xsl:value-of select="ExtendedInfo[Name='FamilyType']/Value"/></ns:familyType>
                </xsl:if>
                <xsl:choose>
                  <xsl:when test="ExtendedInfo[Name='FE_OR_CCBS']/Value='ATS'">
                    <ns:isChange>N</ns:isChange>
                  </xsl:when>
                  <xsl:otherwise>
                    <ns:isChange>Y</ns:isChange>
                  </xsl:otherwise>
                </xsl:choose>
                <ns:tmhProductInfo>
                  <!-- rcRate: CCBS offer (ServiceType=80, FE_OR_CCBS=CCBS), else $nextRCnextPP (null) -->
                  <xsl:choose>
                    <xsl:when test="exists(SubscriberOffers[ServiceType='80' and ExtendedInfo[Name='FE_OR_CCBS']/Value='CCBS']/OfferRate)">
                      <xsl:if test="SubscriberOffers[ServiceType='80' and ExtendedInfo[Name='FE_OR_CCBS']/Value='CCBS']/OfferRate">
                        <ns:rcRate><xsl:value-of select="SubscriberOffers[ServiceType='80' and ExtendedInfo[Name='FE_OR_CCBS']/Value='CCBS']/OfferRate"/></ns:rcRate>
                      </xsl:if>
                    </xsl:when>
                    <xsl:otherwise><ns:rcRate><xsl:value-of select="$nextRCnextPP"/></ns:rcRate></xsl:otherwise>
                  </xsl:choose>
                  <!-- nextRcRate: FE offer (ServiceType=80, FE_OR_CCBS=FE), else null -->
                  <xsl:choose>
                    <xsl:when test="exists(SubscriberOffers[ServiceType='80' and ExtendedInfo[Name='FE_OR_CCBS']/Value='FE']/OfferRate)">
                      <ns:nextRcRate><xsl:value-of select="SubscriberOffers[ServiceType='80' and ExtendedInfo[Name='FE_OR_CCBS']/Value='FE']/OfferRate"/></ns:nextRcRate>
                    </xsl:when>
                    <xsl:otherwise><ns:nextRcRate><xsl:value-of select="$nextRCnextPP"/></ns:nextRcRate></xsl:otherwise>
                  </xsl:choose>
                  <!-- pricePlan: CCBS OfferName, conditional -->
                  <xsl:if test="SubscriberOffers[ServiceType='80' and FE_OR_CCBS='CCBS']/OfferName">
                    <ns:pricePlan><xsl:value-of select="SubscriberOffers[ServiceType='80' and FE_OR_CCBS='CCBS']/OfferName"/></ns:pricePlan>
                  </xsl:if>
                  <!-- nextPricePlan: FE OfferName or null -->
                  <xsl:choose>
                    <xsl:when test="exists(SubscriberOffers[ServiceType='80' and FE_OR_CCBS='FE']/OfferName)">
                      <ns:nextPricePlan><xsl:value-of select="SubscriberOffers[ServiceType='80' and FE_OR_CCBS='FE']/OfferName"/></ns:nextPricePlan>
                    </xsl:when>
                    <xsl:otherwise><ns:nextPricePlan><xsl:value-of select="$nextRCnextPP"/></ns:nextPricePlan></xsl:otherwise>
                  </xsl:choose>
                  <!-- socListInfo: contract SOCs (ServiceType=85, TR_CONTRACT_IND=Y, non-expired) -->
                  <!-- OrderType=4 branching: ATS → loop CCBS/ATS SOCs; non-ATS → loop FE SOCs -->
                  <!-- Other OrderType: loop ServiceType=85, TR_CONTRACT_IND=Y, non-expired -->
                  <!-- ns:extendedInfo[REMOVE_CONTRACT=Y]: only if OrderType=4 AND FE_OR_CCBS != ATS -->
                </ns:tmhProductInfo>
              </ns:productList>
            </xsl:for-each>
          </ns:CampaignRuleRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event @extId ← OMXUtils:generateTrackingID()   [Always]
    ├── JMSPriority           ← $orderRequest/OrderPriority                     [Always]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId            [Always]
    ├── OrderID               ← $orderRequest/OrderData/OrderID                  [Always]
    ├── RefID                 ← $orderRequest/OrderData/Customer/RefId           [Always]
    ├── OrderType             ← $orderRequest/OrderData/OrderType                [Always]
    └── payload                                                                   [Always]
        └── ns:CampaignRuleRequest
            ├── ns:channel            ← "OMX-Mobile"                            [Always]
            ├── ns:requestName        ← "ChangeCampaign"                        [Always]
            ├── ns:function           ← BundleInfo[$i+1]/ConvergenceType        [Always]
            ├── ns:convergenceCode    ← BundleInfo[$i+1]/CampaignCode           [Always]
            └── ns:productList        [Conditional: xsl:for-each Subscriber matching CampaignCode]
                ├── ns:productType    ← "TMV"                                   [Always]
                ├── ns:accessNumber   ← MSISDN                                  [Always]
                ├── ns:familyType     ← ExtendedInfo[FamilyType]/Value          [Conditional: if FamilyType present]
                ├── ns:isChange       ← "N" if FE_OR_CCBS=ATS, else "Y"        [Always]
                └── ns:tmhProductInfo
                    ├── ns:rcRate        ← SubscriberOffers[80,CCBS]/OfferRate  [Always; null fallback]
                    ├── ns:nextRcRate    ← SubscriberOffers[80,FE]/OfferRate    [Always; null fallback]
                    ├── ns:pricePlan     ← SubscriberOffers[80,CCBS]/OfferName  [Conditional: if exists]
                    ├── ns:nextPricePlan ← SubscriberOffers[80,FE]/OfferName    [Always; null fallback]
                    ├── ns:socListInfo   [Conditional: ServiceType=85, TR_CONTRACT_IND=Y, non-expired]
                    │   ├── ns:soc           ← OfferName
                    │   ├── ns:serviceType   ← ServiceType
                    │   ├── ns:contractInd   ← "Y"
                    │   └── ns:contractNew   ← "New" if FE_OR_CCBS=FE, else "Existing"
                    └── ns:extendedInfo  [Conditional: OrderType=4 AND FE_OR_CCBS != ATS]
                        ├── ns:name     ← "REMOVE_CONTRACT"
                        └── ns:value    ← "Y"
```

**Legend:**
- `← xpath` = XPath source (dynamic)
- `← "literal"` = Static literal value
- `[Always]` = Emitted unconditionally
- `[Conditional: ...]` = Emitted only when condition met

---

## §11 — Audit Logging

| Phase | Field | Value |
|-------|-------|-------|
| Request | ESBUUID | `$orderRequest/OrderData/OMXTrackingId` |
| Request | PROCESS_ID | `concat($pid, "_REQ")` — nanoTime |
| Request | COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| Request | OPERATION_NAME | "ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN" |
| Request | TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| Request | LOG_LEVEL | INFO |
| Request | AUDIT_TRACE | "Request Sent for ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN" |
| Request | payload | Conditional: `WritePayload="true"` |
| Response | PROCESS_ID | `concat($pid, "_RES")` |
| Response | OPERATION_NAME | "ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN" |
| Response | AUDIT_TRACE | "Response received for ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN" |

---

## §12 — Activity Status Management

| Transition | Code | Trigger |
|-----------|------|---------|
| Running | "1" | At least one BundleInfo request dispatched |
| Skip | "4" | PreExecCheck=false OR BundleInfo count=0 |
| Error | HandleActivityException | Any uncaught exception |

`SendDataToDB` called after status set to "1".

---

## §13 — Exception / Error Handling

The entire `then` block is wrapped in `try { ... } catch (Exception ae) { RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }`

No partial-send recovery — if exception occurs after partial BundleInfo dispatch, the exception handler is called without compensating already-sent requests.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `RuleFunctions.Helpers.GetActivityStatusString("1", false)` | Returns status string for "Running" |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | Persists orderRequest state to DB |
| `RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")` | Marks activity as skipped and advances flow |
| `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | Central exception handler |
| `Instance.serializeUsingDefaults(orderRequest)` | Serializes concept to XML for PreExecCheck evaluation |
| `OMXUtils:generateTrackingID()` | Custom XSLT function for unique tracking IDs |

---

## §15 — Function Dependency Tree

```text
Request_ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN.rule
├── Instance.serializeUsingDefaults(orderRequest)      [PreExecCheck gate]
├── XPath.execute(chkXPath, sXML)                      [PreExecCheck evaluation]
├── XPath.evalAsInt(count BundleInfo)                  [fan-out count]
├── Event.createEvent(XSLT → ATS_CAMPAIGN_RULE)        [build request event per BundleInfo]
│   └── OMXUtils:generateTrackingID()                  [custom: generate extId]
├── Event.Ext.sendEventImmediate(reqEvent)             [immediate dispatch to ATS]
├── orderCurrentActivity.RequestCount++                 [fan-in counter]
├── Event.createEvent(XSLT → Logger)                   [build audit log event]
├── Event.Ext.sendEventImmediate(logEvent)             [dispatch audit log]
├── RuleFunctions.Helpers.GetActivityStatusString(...)  [status string lookup]
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)   [persist to DB]
├── RuleFunctions.Helpers.SkipActivity(...)            [skip handler]
└── RuleFunctions.Helpers.HandleActivityException(...) [error handler]
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Properties Used |
|---------|-------------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.BundleInfo[], OrderID, OMXTrackingId, Customer.RefId, OrderType, OrderPriority, IsOrderResubmitted, ProcessFlow |
| `Concepts.OrderRequest.OrderElements.BundleInfo` | CampaignCode, ConvergenceType |
| `Concepts.OrderRequest.OrderElements.Subscriber` | MSISDN, ExtendedInfo[], SubscriberOffers[] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | ServiceType, OfferRate, OfferName, SocProperties, ParameterInfo[], ExtendedInfo[] |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck |
| `Events.OMConsumers.OMXFM.Request.ATS_CAMPAIGN_RULE` | Request event sent to ATS |
| `Events.OMConsumers.OMXFM.Response.ATS_CAMPAIGN_RULE` | Response event from ATS |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Invoke ATS ChangeCampaign once per BundleInfo entry (fan-out by bundle, not by subscriber) |
| R2 | Aggregate all subscribers matching bundle's CampaignCode into single request's productList |
| R3 | Include tmhProductInfo: rcRate/nextRcRate from CCBS offers (ServiceType=80), price plan names, contract SOC list (ServiceType=85, non-expired) |
| R4 | Apply OrderType=4 branching for socListInfo and REMOVE_CONTRACT extendedInfo |
| R5 | Skip step if no BundleInfo present (SkipActivity) |
| R6 | Treat resubmission correctly — do not double-increment RequestCount |
| R7 | Fan-in: wait for all dispatched requests (count ResponseCode suffix "000" = RequestCount) |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| `nextRCnextPP` always null — rcRate/nextRcRate/nextPricePlan will be empty when CCBS offer data absent | [MEDIUM] | Verify with ATS team if empty rate fields are acceptable; if not, add rate lookup step prior to this FM |
| No partial-send compensation: exception after partial BundleInfo dispatch leaves some bundles sent, others not | [MEDIUM] | Implement transactional fan-out or compensating call pattern in modern platform |
| Contract SOC date filtering uses `tib:compare-date` / `tib:parse-date` TIBCO custom functions — not portable | [HIGH] | Replace with standard Java/platform date comparison in target implementation |
| Subscriber filter uses `contains(...)` substring match on CampaignCode — may inadvertently match partial codes | [LOW] | Verify if substring match is intentional; use equality in migration if codes are exact |
| `sendEventImmediate` — synchronous; high BundleInfo count blocks rule engine thread | [MEDIUM] | Assess maximum BundleInfo cardinality; consider async dispatch for large fan-outs |

---

## §18 — Full Source Code (Request Rule)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN {
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
    orderCurrentActivity.ActivityID == "ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN";
    orderRequest.ProcessFlow.NextActivityID == "ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN";
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
      String nextRCnextPP = null;  // always null — empty fallback for rate/plan fields

      if(String.length(nextAct.PreExecCheck) > 0) {
        String sXML = Instance.serializeUsingDefaults(orderRequest);
        chkRes = XPath.execute("/(" + chkXPath + ")", sXML, "ns0=www.tibco.com/be/ontology/...");
      }

      if(String.equals(chkRes, "true")) {
        int bundleInfoSize = XPath.evalAsInt(/* count($orderRequest/OrderData/BundleInfo) */);
        for (int i=0; i<bundleInfoSize; i++) {
          Events.OMConsumers.OMXFM.Request.ATS_CAMPAIGN_RULE reqEvent =
            Event.createEvent(/* XSLT → CampaignRuleRequest — see §9.8 */);
          Event.Ext.sendEventImmediate(reqEvent);

          if(!isActResub) {
            orderCurrentActivity.RequestCount++;
          }

          long pid = System.nanoTime();
          Event.Ext.sendEventImmediate(Event.createEvent(/* Logger XSLT — see §11 */));
          isSkipped = false;
        }
      }

      if (!isSkipped) {
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

### §19.1 — Overview

The response handler (`Response_ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN`) receives one `ATS_CAMPAIGN_RULE` response event per dispatched BundleInfo request. It appends a `ResponseBase` concept to `currActivity.Response[]`, then enriches working memory by writing the ATS-resolved `ConvergenceAction` to the matching `BundleInfo` and updating each subscriber's `SubscriberOffers` records with `benefitAction` and `FE_OR_CCBS` values. Fan-in completes when all dispatched requests have returned ResponseCode suffix "000".

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order concept — read for matching, written for enrichment |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.ATS_CAMPAIGN_RULE` | ATS response carrying CampaignRuleResponse payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity; Response[] appended; RequestCount compared |

### §19.3 — ResponseBase Concept Construction

```text
createObject
└── object @extId ← OMXUtils:generateTrackingID()   [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode       [Conditional: if ResponseCode present]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg        [Conditional: if ResponseMsg present]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus   [Conditional: if CompletionStatus present]
    └── ReferenceId       ← $eventResponse/RefID              [Conditional: if RefID present]
```

Appended: `currActivity.Response[currActivity.Response@length] = activityRes;`

### §19.4 — Working Memory Enrichment (Response Processing)

| Step | Action | Condition |
|------|--------|-----------|
| 1 | Extract `campaignCode` from `CampaignRuleResponse/productList[1]/existingCampaignList[1]/campaignCode` | Always |
| 2 | Extract `convergenceAction` from `CampaignRuleResponse/convergenceAction` | If campaignCode != null |
| 3 | Write `bundleInfo.ConvergenceAction = convergenceAction` (BundleInfo matched by CampaignCode) | If convergenceAction != null |
| 4 | Iterate `productList`; for productType="TMV": find subscriber by MSISDN | If campaignCode != null |
| 5 | Iterate `benefitCampaignList`; extract benefitCode + benefitAction | If subscriber found |
| 6a | Find SubscriberOffer by OfferName=benefitCode; set `subscriberOffer.Action = benefitAction` | If both non-empty |
| 6b | Update existing FE_OR_CCBS ExtendedInfo: ATS_REMOVE if REMOVE, else ATS — unless blank or "FE" | If ExtendedInfo[FE_OR_CCBS] found |
| 6c | Create new FE_OR_CCBS ExtendedInfo (ATS_REMOVE/ATS) and append | If ExtendedInfo[FE_OR_CCBS] not found |
| 6d | Create new SubscriberOffers with OfferName=benefitCode, Action=ADD, FE_OR_CCBS=ATS | If SubscriberOffer not found AND benefitAction=ADD |

> **Note:** FE_OR_CCBS update guard — the code only changes FE_OR_CCBS if existing value is not blank AND not "FE". This protects FE-tagged offers from being overwritten by ATS response data.

### §19.5 — Response Completion Logic (Fan-in)

| Expression | Value |
|-----------|-------|
| Success count XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Returns "true" | All dispatched requests returned success — caller advances process flow |
| Returns "false" | Still waiting for remaining responses |

### §19.6 — Response XSLT Source (ResponseBase)

```xml
<!-- ResponseBase XSLT — Response_ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN -->
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  version="1.0">
  <xsl:output method="xml"/>
  <xsl:param name="eventResponse"/>  <!-- ATS_CAMPAIGN_RULE response event -->
  <xsl:template match="/">
    <createObject>
      <object>
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
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
