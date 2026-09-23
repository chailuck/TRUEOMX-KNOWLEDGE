# Request_ATS_ENQUIRY_CAMPAIGN

> TIBCO BusinessEvents FM Logic — ATS Campaign Enquiry (Order-level, Single Request)

**Rule type:** OMXFM Request | **Backend:** ATS (Campaign Management) | **Priority:** 5 | **Pattern:** Single Order-Level Request

---

## §1 — Overview & Purpose

`Request_ATS_ENQUIRY_CAMPAIGN` sends an `EnquiryCampaignRequest` to the ATS (Campaign Management) system to retrieve active campaigns for a subscriber. Unlike most OMXFM rules, this rule fires a **single order-level request** — the per-subscriber fan-out code is written but entirely commented out.

The request uses `function="All"`, `activeFlag="Y"`, and `productType="TMV"` to fetch all active TMV campaigns. The MSISDN is selected conditionally based on OrderType: for CHANGE_MSISDN orders (types 21 / 12001), the SOURCE subscriber is used; otherwise the first available subscriber in POU[1]/Sub[1] (or COU fallback) is used.

The response handler is the most complex in this FM set — it iterates all returned `campaignInfo` entries and enriches working memory with BundleInfo concepts and subscriber ExtendedInfo (CampaignCode, FamilyType, NUM_MEMBER), supporting both **MobileSoftBundle** and **FindFriend** campaign types with multi-branch debundle action logic.

> **Architecture divergence:** The per-subscriber fan-out code (POU + COU loops) is present in source but entirely commented out. The **active code fires exactly ONE request per order** using `Event.Ext.sendEventImmediate` (not `IntraActivitySequencing`). Fan-in uses ResponseCode suffix "000" count against RequestCount.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_ATS_ENQUIRY_CAMPAIGN` |
| Rule type | OMXFM Request Rule |
| Priority | 5 |
| Forward Chain | true |
| Author | DESKTOP-995HR2V |
| Backend system | ATS — Campaign Management |
| Request event | `Events.OMConsumers.OMXFM.Request.ATS_ENQUIRY_CAMPAIGN` |
| Response event | `Events.OMConsumers.OMXFM.Response.ATS_ENQUIRY_CAMPAIGN` |
| Dispatch method | `Event.Ext.sendEventImmediate` (synchronous, no sequencing) |
| Fan-out pattern | **Single order-level request** (per-subscriber code commented out) |
| Schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ATS/EnquiryCampaign.xsd` |
| ATS operation | `EnquiryCampaign` — function=All, productType=TMV, activeFlag=Y |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order concept; serialised for PreExecCheck |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity; holds RequestCount and Response array |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance matches process flow pointer |
| 2 | `orderCurrentActivity.ActivityID == "ATS_ENQUIRY_CAMPAIGN"` | Must be this activity type |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "ATS_ENQUIRY_CAMPAIGN"` | Process flow points here |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be idle |

---

## §5 — Execution Flow Diagram

```
1. isActResub check → RequestCount > 0 AND IsOrderResubmitted
2. Order-level PreExecCheck → Instance.serializeUsingDefaults(orderRequest) → XPath gate
3. Build EnquiryCampaignRequest XSLT → MSISDN selection based on OrderType
4. Event.Ext.sendEventImmediate(reqEvent) — no IntraActivitySequencing
5. if !isActResub → RequestCount++
6. Send request audit log via Event.Ext.sendEventImmediate(Logger)
7. Set Status="1" (PROCESSING) + SendDataToDB
   OR SkipActivity("4") if gate failed
```

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in `POSTPAID_REMOVE_OFFER_SUB` step 20. The MSISDN selection has a special branch for OrderType `21` (CHANGE_MSISDN) and `12001` — selects the SOURCE-flagged subscriber.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event | Purpose |
|-----------|-------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.ATS_ENQUIRY_CAMPAIGN` | EnquiryCampaign request |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.ATS_ENQUIRY_CAMPAIGN` | ATS response |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Audit trail |

### §8.3 — Backend API Details

| System | Operation | Static fields | Schema |
|--------|-----------|--------------|--------|
| ATS | `EnquiryCampaign` | requestName="EnquiryCampaign", function="All", activeFlag="Y", productType="TMV" | `ESB/ATS/EnquiryCampaign.xsd` |

### §8.4 — BE Working Memory Read/Write

| Concept path | Fields read | Fields written |
|-------------|------------|----------------|
| `OrderRequest` | OMXTrackingId, OrderID, OrderType, Channel, OrderPriority, ExtendedInfo[ACTION, CONVERGENCE_TYPE, CAMPAIGN_CODE] | OrderData.BundleInfo[] |
| `Subscriber` | MSISDN, RefId, ExtendedInfo | ExtendedInfo[CampaignCode, FamilyType, NUM_MEMBER] |
| `Activity` | Status, RequestCount, PreExecCheck, Parameter[1] | Status, RequestCount, Response[] |

### §8.5 — ExtendedInfo Fields Required

| Key | Source | Purpose |
|-----|--------|---------|
| `ACTION` | OrderData.ExtendedInfo | Determines debundle action: BREAK / CANCEL / BREAK_ALL |
| `CONVERGENCE_TYPE` | OrderData.ExtendedInfo | Filters campaignInfo entries (must match ATS response convergenceType) |
| `CAMPAIGN_CODE` | OrderData.ExtendedInfo | Filters campaignInfo entries (must match ATS response campaignCode) |
| `SOURCE_OR_TARGET` | ParentOU/ChildOU.ExtendedInfo | Identifies SOURCE subscriber for CHANGE_MSISDN orders |

### §8.6 — Activity Parameter Dependencies

| Parameter | Source | Purpose |
|-----------|--------|---------|
| `Parameter[1]` | `currActivity.Parameter[1]` | `targetConvergenceParam` — filter for campaign types from ATS response |
| `orderChannelParam` | `GetActivityParamValueFromKey(currActivity, "orderChannelParam")` | If matches `orderRequest.Channel` → suppresses MAIN subscriber for MVC in BREAK_ALL |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| Parameter | Bound from |
|-----------|-----------|
| `$orderRequest` | orderRequest concept (only parameter — MSISDN selected inline) |

### §9.2 — MSISDN Selection Logic

| Condition | MSISDN source |
|-----------|--------------|
| OrderType = '21' or '12001' AND POU SOURCE exists | `ParentOU[SOURCE_OR_TARGET=SOURCE]/Subscriber/MSISDN` |
| OrderType = '21' or '12001', no POU SOURCE | `ParentOU[1]/ChildOU[SOURCE]/Subscriber/MSISDN` |
| Other order types AND POU[1]/Sub[1] exists | `ParentOU[1]/Subscriber[1]/MSISDN` |
| Other order types, no POU subscriber | `ParentOU[1]/ChildOU[1]/Subscriber[1]/MSISDN` |

### §9.3 — Complete Generated XML Example

```xml
<event extId="OMXUtils:generateTrackingID()">
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-2024-001-TRK</JMSCorrelationID>
  <OrderID>ORD-20240813-001</OrderID>
  <RefID>CUST-001</RefID>
  <OrderType>POSTPAID_REMOVE_OFFER_SUB</OrderType>
  <payload>
    <ns:EnquiryCampaignRequest>
      <ns:channel>OMX</ns:channel>
      <ns:requestName>EnquiryCampaign</ns:requestName>
      <ns:function>All</ns:function>
      <ns:activeFlag>Y</ns:activeFlag>
      <ns:product>
        <ns:productType>TMV</ns:productType>
        <ns:accessNumber>0812345678</ns:accessNumber>
      </ns:product>
    </ns:EnquiryCampaignRequest>
  </payload>
</event>
```

### §9.4 — XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ATS/EnquiryCampaign.xsd"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:template match="/">
    <createEvent><event>
      <xsl:attribute name="extId">
        <xsl:value-of select="OMXUtils:generateTrackingID()"/>
      </xsl:attribute>
      <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      <RefID><xsl:value-of select="$orderRequest/OrderData/Customer/RefId"/></RefID>
      <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      <payload><ns:EnquiryCampaignRequest>
        <ns:channel><xsl:value-of select="$orderRequest/OrderData/Channel"/></ns:channel>
        <ns:requestName>EnquiryCampaign</ns:requestName>
        <ns:function>All</ns:function>
        <ns:activeFlag>Y</ns:activeFlag>
        <ns:product>
          <ns:productType>TMV</ns:productType>
          <!-- accessNumber: 4-way conditional MSISDN selection -->
          <xsl:choose>
            <xsl:when test="$orderRequest/OrderData/OrderType='21' or ...='12001'">
              <xsl:choose>
                <xsl:when test="exists(ParentOU[SOURCE_OR_TARGET=SOURCE]/Subscriber/MSISDN)">
                  <ns:accessNumber><xsl:value-of select="ParentOU[SOURCE]/Subscriber/MSISDN"/></ns:accessNumber>
                </xsl:when>
                <xsl:otherwise>
                  <ns:accessNumber><xsl:value-of select="ParentOU[1]/ChildOU[SOURCE]/Subscriber/MSISDN"/></ns:accessNumber>
                </xsl:otherwise>
              </xsl:choose>
            </xsl:when>
            <xsl:otherwise>
              <xsl:choose>
                <xsl:when test="exists(ParentOU[1]/Subscriber[1]/MSISDN)">
                  <ns:accessNumber><xsl:value-of select="ParentOU[1]/Subscriber[1]/MSISDN"/></ns:accessNumber>
                </xsl:when>
                <xsl:otherwise>
                  <ns:accessNumber><xsl:value-of select="ParentOU[1]/ChildOU[1]/Subscriber[1]/MSISDN"/></ns:accessNumber>
                </xsl:otherwise>
              </xsl:choose>
            </xsl:otherwise>
          </xsl:choose>
        </ns:product>
      </ns:EnquiryCampaignRequest></payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event  @extId ← OMXUtils:generateTrackingID()                    [Always]
    ├── JMSPriority        ← $orderRequest/OrderPriority              [Always]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId    [Always]
    ├── OrderID            ← $orderRequest/OrderData/OrderID          [Always]
    ├── RefID              ← $orderRequest/OrderData/Customer/RefId   [Always]  ← customer-level
    ├── OrderType          ← $orderRequest/OrderData/OrderType        [Always]
    └── payload
        └── ns:EnquiryCampaignRequest
            ├── ns:channel      ← $orderRequest/OrderData/Channel     [Always]
            ├── ns:requestName  ← "EnquiryCampaign" (static)          [Always]
            ├── ns:function     ← "All" (static)                      [Always]
            ├── ns:activeFlag   ← "Y" (static)                        [Always]
            └── ns:product
                ├── ns:productType  ← "TMV" (static)                  [Always]
                └── ns:accessNumber  [Always — one of 4 branches]
                    ├── ① ParentOU[SOURCE]/Subscriber/MSISDN          [if OrderType=21|12001, POU SOURCE exists]
                    ├── ② ParentOU[1]/ChildOU[SOURCE]/Subscriber/MSISDN [if OrderType=21|12001, COU SOURCE]
                    ├── ③ ParentOU[1]/Subscriber[1]/MSISDN            [standard order, POU subscriber exists]
                    └── ④ ParentOU[1]/ChildOU[1]/Subscriber[1]/MSISDN [standard order, fallback COU]
```

---

## §11 — Audit Logging

| Phase | PROCESS_ID | AUDIT_TRACE | Payload gated? |
|-------|-----------|-------------|----------------|
| Request sent | `concat($pid, "_REQ")` | `Request Sent for ATS_ENQUIRY_CAMPAIGN` | Yes — WritePayload="true" |
| Response received | `concat($pid, "_RES")` | `Response received for ATS_ENQUIRY_CAMPAIGN` | Yes — WritePayload="true" |

Both use `Event.Ext.sendEventImmediate` (consistent with the immediate dispatch model).

---

## §12 — Activity Status Management

| Transition | Status code | Condition |
|-----------|------------|-----------|
| Request sent | `"1"` PROCESSING | PreExecCheck passes |
| Skipped | `"4"` SKIPPED | PreExecCheck fails |
| Fan-in complete | set by response handler | RequestCount == successResponseCount |

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 — Helper Functions Reference

| Function | Validity | Purpose |
|---------|---------|---------|
| `Instance.serializeUsingDefaults(orderRequest)` | ACTION | Serialises full orderRequest for order-level PreExecCheck |
| `GetActivityParamValueFromKey(currActivity, key)` | QUERY | Retrieves named parameter from activity |
| `BRMS.IsBlankOrStringNull(str)` | QUERY | Null/blank check used in action flag evaluation |
| `GetActivityStatusString(code, flag)` | QUERY | Status code to string |
| `SendDataToDB(orderRequest)` | ACTION | Persist order state |
| `SkipActivity(orderRequest, activity, "4")` | ACTION | Mark skipped and advance flow |
| `HandleActivityException(orderRequest, activity, ex, "")` | ACTION | Generic exception handler |

---

## §15 — Function Dependency Tree

```text
Request_ATS_ENQUIRY_CAMPAIGN (rule)
├── Instance.serializeUsingDefaults(orderRequest)          [order-level PreExecCheck XML]
├── XPath.execute()                                         [PreExecCheck gate]
├── Event.createEvent("xslt://ATS_ENQUIRY_CAMPAIGN")       [XSLT payload build]
├── Event.Ext.sendEventImmediate(reqEvent)                  [immediate dispatch]
├── orderCurrentActivity.RequestCount++                     [only if !isActResub]
├── Event.Ext.sendEventImmediate(Logger)                    [request audit log]
├── GetActivityStatusString("1", false)                     [PROCESSING]
├── SendDataToDB()                                          [persist state]
└── SkipActivity() / HandleActivityException()             [terminal paths]

Response_ATS_ENQUIRY_CAMPAIGN (rulefunction)
├── Instance.createInstance("xslt://ResponseBase")         [basic response concept]
├── currActivity.Response[length] = activityRes            [append response]
├── XPath.evalAsString (×6+)                               [ACTION, CONVERGENCE_TYPE, CAMPAIGN_CODE,
│                                                           targetConvergenceParam, per-entry fields]
├── GetActivityParamValueFromKey(currActivity, "orderChannelParam")
├── BRMS.IsBlankOrStringNull() (×4)                        [action flag null checks]
├── [MobileSoftBundle path]
│   ├── Instance.createInstance("xslt://BundleInfo")
│   ├── orderRequest.OrderData.BundleInfo[n] = bundleInfo
│   └── subscriber.ExtendedInfo[n] = CampaignCode + FamilyType
├── [FindFriend path — multi-variant BundleInfo]
│   ├── Instance.createInstance("xslt://BundleInfo") (×4 variants)
│   ├── Instance.createInstance("xslt://Subscriber") [synthetic sub if not found]
│   └── subscriber.ExtendedInfo[n] = CampaignCode + FamilyType + NUM_MEMBER
├── Event.Ext.sendEventImmediate(Logger)                   [response audit log]
└── XPath.evalAsInt — count ResponseCode "000" == RequestCount  [fan-in]
```

---

## §16 — Concept Definitions Referenced

| Concept | Key fields |
|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.BundleInfo[], ExtendedInfo[ACTION, CONVERGENCE_TYPE, CAMPAIGN_CODE] |
| `Concepts.OrderRequest.OrderElements.BundleInfo` | extId, CampaignCode, ConvergenceType, ConvergenceAction, TruelifeId, GroupId |
| `Concepts.OrderRequest.OrderElements.Subscriber` | MSISDN, RefId, AccountRefId, ExtendedInfo[] |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` | extId, Name, Value |
| `Concepts.FM.Base.ResponseBase` | extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | Send single `EnquiryCampaignRequest` to ATS per order (not per-subscriber) |
| R2 | Select MSISDN based on OrderType: 21/12001 → SOURCE subscriber; others → first available |
| R3 | Evaluate order-level PreExecCheck before dispatch |
| R4 | Do not increment RequestCount on resubmission |
| R5 | Process ATS response: iterate all `campaignInfo` filtered by `targetConvergenceParam` |
| R6 | MobileSoftBundle: create BundleInfo + annotate subscriber with CampaignCode + FamilyType |
| R7 | FindFriend: create BundleInfo with ConvergenceAction based on CountMember + ACTION flag |
| R8 | BREAK_ALL on MVC channel: skip MAIN subscriber BundleInfo creation |
| R9 | If subscriber not found in working memory → create synthetic subscriber (FE_OR_CCBS=ATS) |
| R10 | Fan-in: ResponseCode suffix "000" count == RequestCount |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| Per-subscriber fan-out code commented out — unclear if intentional | [HIGH] | Verify with business team whether single-request design is correct for multi-subscriber orders |
| Response handler mutates working memory with complex side effects | [MEDIUM] | Document all concept writes; ensure downstream rules expect enriched concepts |
| Commented-out audit log contains stale OPERATION_NAME="MCS_REGISTER" | [LOW] | Active code is correct; stale reference is in commented code only |
| Subscriber lookup by MSISDN with complex multi-OU XPath | [MEDIUM] | Validate for edge cases with multiple MSISDNs or multiple POU entries |

---

## §18 — Full Source Code

> NOTE: ~140 lines of per-subscriber fan-out code are commented out in the source. Only active code shown.

```java
rule Rules.OMConsumers.OMXFM.Request.Request_ATS_ENQUIRY_CAMPAIGN {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "ATS_ENQUIRY_CAMPAIGN";
        orderRequest.ProcessFlow.NextActivityID == "ATS_ENQUIRY_CAMPAIGN";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            String chkXPath = nextAct.PreExecCheck;
            String chkRes = "true";
            boolean isSkipped = true;

            if(String.length(nextAct.PreExecCheck) > 0) {
                /* Order-level PreExecCheck — serialise full orderRequest */
                String sXML = Instance.serializeUsingDefaults(orderRequest);
                chkRes = XPath.execute("/(chkXPath)", sXML, "ns0=...");
            }

            if(String.equals(chkRes, "true")) {
                /* Build single ATS_ENQUIRY_CAMPAIGN event — see §9.4 for full XSLT */
                Events.OMConsumers.OMXFM.Request.ATS_ENQUIRY_CAMPAIGN reqEvent =
                    Event.createEvent("xslt://{{/Events/.../ATS_ENQUIRY_CAMPAIGN}}...");
                Event.Ext.sendEventImmediate(reqEvent); // no IntraActivitySequencing

                if(!isActResub) {
                    orderCurrentActivity.RequestCount++;
                }
                /* Send request audit log */
                Event.Ext.sendEventImmediate(Event.createEvent("xslt://Logger..."));
                isSkipped = false;
            }

            /* NOTE: per-subscriber fan-out loops (POU + COU) exist but are commented out */

            if(!isSkipped) {
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
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

`Response_ATS_ENQUIRY_CAMPAIGN` maps the basic ResponseBase, then performs extensive working memory enrichment by processing each `campaignInfo` in the ATS response. It creates BundleInfo concepts and writes campaign data into subscriber ExtendedInfo for downstream processing.

### §19.2 — Scope Variables

| Variable | Type |
|---------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.ATS_ENQUIRY_CAMPAIGN` |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` |

### §19.3 — ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId            ← OMXUtils:generateTrackingID()         [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode           [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg            [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus       [Conditional]
    └── ReferenceId       ← $eventResponse/RefID                  [Conditional]
```

### §19.4 — Campaign Data Enrichment Logic

| Flag | Source | Values | Effect |
|------|--------|--------|--------|
| `targetConvergenceParam` | `currActivity.Parameter[1]` | pipe-delimited filter | Skips non-matching campaignInfo |
| `isActionBreak` | ExtendedInfo[ACTION]="BREAK" | "Y" or "" | ConvergenceAction=DebundleProductNumber (members>1) or DebundleCampaign |
| `isActionCancel` | ExtendedInfo[ACTION]="CANCEL" | "Y" or "" | ConvergenceAction=DebundleCampaign |
| `isActionBreakAll` | ExtendedInfo[ACTION]="BREAK_ALL" | "Y" or "" | ConvergenceAction based on member count |
| `is_order_channel_pomx` | orderChannelParam==Channel | true/false | Suppresses MAIN BundleInfo for MVC channel in BREAK_ALL |

### §19.5 — Working Memory Writes

| Campaign Type | Concept written | Fields set |
|--------------|----------------|-----------|
| MobileSoftBundle | `orderRequest.OrderData.BundleInfo[]` | CampaignCode, ConvergenceType, TruelifeId, GroupId |
| MobileSoftBundle | `subscriber.ExtendedInfo` | CampaignCode, FamilyType (per TMV product) |
| FindFriend (MAIN + BREAK/CANCEL) | `orderRequest.OrderData.BundleInfo[]` | CampaignCode, ConvergenceType, ConvergenceAction, TruelifeId, GroupId |
| FindFriend | `subscriber.ExtendedInfo` | CampaignCode, FamilyType, NUM_MEMBER (MAIN only) |
| All (synthetic subscriber) | New `Subscriber` → POU/COU | MSISDN, RefId=productId+"_src", FE_OR_CCBS=ATS, FamilyType, CampaignCode, NUM_MEMBER |

> SubscriberExtendedInfo extId pattern: `"SUBEXT:" + OMXTrackingId + ":" + RefId + ":" + Name`

### §19.6 — Fan-in Completion Logic

```java
int successResponseCount = XPath.evalAsInt(
    "count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = \"000\"])");
if(currActivity.RequestCount == successResponseCount) {
    return "true";
} else {
    return "false";
}
```

Since there is only 1 request (RequestCount=1), the first successful response (ResponseCode suffix "000") triggers completion.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
