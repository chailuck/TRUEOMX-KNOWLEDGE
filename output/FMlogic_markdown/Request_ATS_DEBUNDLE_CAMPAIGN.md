# Request_ATS_DEBUNDLE_CAMPAIGN

TIBCO BusinessEvents · FM Logic Documentation · Backend: ATS · Operation: SubmitCampaign (Debundle)

---

## §1 — Overview & Purpose

**Request_ATS_DEBUNDLE_CAMPAIGN** submits campaign debundle requests to the ATS (campaign system) for each convergence bundle associated with the order. Unlike most FMs which iterate over subscribers, this FM iterates over `OrderData.BundleInfo` entries — one dispatch per BundleInfo item whose `ConvergenceAction` is not null.

Two `ConvergenceAction` modes are supported, each producing a different payload shape:

- **DebundleCampaign** — emits activityCode="Debundle", disconnectedBy="OMX-Mobile", reasonCode="DB02", cancelReasonCode="DB02"
- **DebundleProductNumber** — emits `ns:productList` with a productId selected via three-way fallback logic; no activity/reason codes

The FM reuses the `ATS_SUBMIT_CAMPAIGN` JMS event type (shared with ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN).

> **[HIGH] No resubmit-skip for BundleInfo items:** The BundleInfo loop has no per-item skip check equivalent to the subscriber `reqSuccess` pattern. On order resubmit (`isActResub=true`), all BundleInfo items with non-null `ConvergenceAction` are re-dispatched unconditionally — even items that already received a successful ATS response. Fix: track per-BundleInfo completion in a side structure or use the BundleInfo index + customer RefId as a composite RefID.

> **[MEDIUM] Customer-level RefID:** All BundleInfo dispatches use `$orderRequest/OrderData/Customer/RefId` as RefID — the same value for all items. There is no per-BundleInfo correlation key, making it impossible to distinguish which BundleInfo item a given response corresponds to.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_ATS_DEBUNDLE_CAMPAIGN` | Full qualified path |
| Priority | `5` | Standard FM priority |
| Forward chain | `true` | Rule re-evaluates after THEN actions |
| Rule type | Request Dispatcher | BundleInfo fan-out via ATS_SUBMIT_CAMPAIGN event |
| Author | `DESKTOP-995HR2V` | Machine hostname — no developer name recorded |
| Backend system | ATS | Campaign management — SubmitCampaign (Debundle) |
| Event type | `Events.OMConsumers.OMXFM.Request.ATS_SUBMIT_CAMPAIGN` | Shared event type reused from ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN |
| Dispatch pattern | `Event.Ext.sendEventImmediate` | Fan-out per BundleInfo; no IntraActivitySequencing |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order context; BundleInfo array and Customer data are primary sources |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity; holds RequestCount, Response array, Status, PreExecCheck |

---

## §4 — Rule Conditions (WHEN)

| # | Condition Expression | Purpose |
|---|---------------------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Binds activity to current order's next slot |
| 2 | `orderCurrentActivity.ActivityID == "ATS_DEBUNDLE_CAMPAIGN"` | Restricts rule to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "ATS_DEBUNDLE_CAMPAIGN"` | Double-checks order flow pointer |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires when activity is in WAITING state |

---

## §5 — Execution Flow Diagram

1. Compute `isActResub = (RequestCount > 0 && IsOrderResubmitted)`.
2. Global PreExecCheck: if configured, serialise entire `orderRequest` via `Instance.serializeUsingDefaults` and evaluate XPath. If result is not "true", skip all dispatches.
3. Count BundleInfo entries: XPath `count($orderRequest/OrderData/BundleInfo)` → `bundleInfoSize`.
4. BundleInfo fan-out loop: for `i = 0` to `bundleInfoSize-1`: if `BundleInfo[i].ConvergenceAction != null`, dispatch `ATS_SUBMIT_CAMPAIGN` event and audit logger. Increment `RequestCount` if `!isActResub`. **[HIGH] No resubmit-skip.**
5. If any dispatch: Status → `GetActivityStatusString("1", false)` + DB persist. Else: `SkipActivity(…, "4")`.
6. Exception handling: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

> **Key architectural difference from subscriber-loop FMs:** This FM does not loop over ParentOU/ChildOU/Subscriber. It iterates `OrderData.BundleInfo` — the convergence bundle catalogue attached to the order. There is no per-subscriber fan-out.

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

**Global PreExecCheck (whole order, not per-subscriber):**

```java
if(String.length(nextAct.PreExecCheck) > 0) {
    // Note: uses Instance.serializeUsingDefaults — serialises full orderRequest concept
    // Not GetXMLForSubscriber — this is an order-level check, not subscriber-level
    String sXML = Instance.serializeUsingDefaults(orderRequest);
    chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=www.tibco.com/be/ontology/Concepts/OrderRequest/OrderRequest");
}
```

**BundleInfo fan-out loop:**

```java
int bundleInfoSize = XPath.evalAsInt("count($orderRequest/OrderData/BundleInfo)");
for (int i=0; i<bundleInfoSize; i++) {
    if (orderRequest.OrderData.BundleInfo[i].ConvergenceAction != null) {
        // [HIGH] No resubmit-skip check here — always dispatches on resubmit
        Events.OMConsumers.OMXFM.Request.ATS_SUBMIT_CAMPAIGN reqEvent =
            Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/ATS_SUBMIT_CAMPAIGN}}...");
        Event.Ext.sendEventImmediate(reqEvent);

        if(!isActResub) {
            orderCurrentActivity.RequestCount++;
        }

        long pid = System.nanoTime();
        Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{/Events/OMConsumers/OMXESB/Logger}}..."));
        isSkipped = false;
    }
}
```

> **[HIGH] Missing resubmit-skip:** On resubmit (`isActResub=true`), `RequestCount` is not incremented (correct), but the dispatch still fires for every BundleInfo item. There is no equivalent of the subscriber `reqSuccess` check. ATS receives duplicate debundle calls on every resubmit.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in **POSTPAID_REMOVE_OFFER_SUB** and other convergence offer-removal flows where the order carries one or more `BundleInfo` entries representing ATS campaign bundles that need to be debundled.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Channel / Destination | Protocol | Purpose |
|-----------|-----------|----------------------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.ATS_SUBMIT_CAMPAIGN` | ATS JMS channel / SubmitCampaign destination | JMS / TIBCO EMS | Dispatch debundle campaign request per BundleInfo |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.ATS_SUBMIT_CAMPAIGN` | ATS response channel | JMS / TIBCO EMS | Receive campaign submit response |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Audit log channel | JMS | Request/response audit trail |

> The outbound event is `ATS_SUBMIT_CAMPAIGN` — the same type used by **ATS_CAMPAIGN_RULE_CHANGE_CAMPAIGN**. The response rulefunction for this FM also listens on `ATS_SUBMIT_CAMPAIGN` response events.

### §8.3 — Backend API Details

| System | Operation | Schema | Request Element | Correlation |
|--------|-----------|--------|----------------|-------------|
| ATS | SubmitCampaign (Debundle) | `ATS/SubmitCampaignRequest.xsd` | `ns:submitCampaignReq` | `RefID` ← `$orderRequest/OrderData/Customer/RefId` (customer-level) |

### §8.4 — BE Working Memory Dependencies

| Field | Access | Purpose |
|-------|--------|---------|
| `orderRequest.OrderData.BundleInfo[i].ConvergenceAction` | READ | Gate: dispatch only if not null; also determines payload mode |
| `orderRequest.OrderData.BundleInfo[i].CampaignCode` | READ | ns:campaignInfo/ns:campaignCode |
| `orderRequest.OrderData.BundleInfo[i].ConvergenceType` | READ | ns:campaignInfo/ns:convergenceType |
| `orderRequest.OrderData.BundleInfo[i].TruelifeId` | READ | ns:campaignInfo/ns:truelifeId |
| `orderRequest.OrderData.Customer.RefId` | READ | Event RefID (customer-level, same for all dispatches) |
| `orderRequest.OrderData.OMXTrackingId` | READ | JMSCorrelationID + audit UUID |
| `orderRequest.OrderData.OrderID` | READ | Event header OrderID |
| `orderRequest.OrderData.OrderType` | READ | Event header OrderType |
| `orderRequest.OrderData.ExtendedInfo[Name='ACTION']/Value` | READ | productId source: "BREAK" → use GROUP ExtendedInfo |
| `orderRequest.OrderData.ExtendedInfo[Name='GROUP']/Value` | READ | productId source when ACTION=BREAK: `substring-after(…, "PRODUCT_ID=")` |
| `orderRequest.OrderData.Customer.ParentOU[1].Subscriber[*]` | READ | productId fallback: subscriber MSISDN with matching CampaignCode |
| `orderRequest.OrderPriority` | READ | JMSPriority |
| `orderRequest.IsOrderResubmitted` | READ | Resubmit flag |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-out counter |
| `orderCurrentActivity.Response` | WRITE (response) | Append ResponseBase records |
| `orderCurrentActivity.Status` | WRITE | Set to SENT after dispatch |

### §8.5 — ConvergenceAction Modes

| ConvergenceAction value | Emits | Additional Fields |
|------------------------|-------|-------------------|
| `DebundleCampaign` | requestName, activityCode="Debundle", disconnectedBy="OMX-Mobile", reasonCode="DB02", cancelReasonCode="DB02", campaignInfo | No productList |
| `DebundleProductNumber` | requestName, campaignInfo + productList (with productId + productType="TMV") | No activityCode/reasonCode fields |
| Any other non-null value | requestName only + campaignInfo (no product list, no activity codes) | Partial payload — ATS may reject |

### §8.6 — Global Variable Dependencies

| Variable Path | Used In | Purpose |
|--------------|---------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit logger | COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit logger | TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit logger | LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Audit logger | Gates payload inclusion |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Role |
|-----------|-----------|------|
| `$orderRequest` | BE concept `orderRequest` | Root order data including BundleInfo |
| `$i` | Loop variable `i` | 0-based BundleInfo index; used as `$i+1` in XSLT for 1-based XPath |

> Only 2 XSLT params (vs 10 in MCS_CANCEL_AFTER_SALE). The XSLT relies heavily on BundleInfo XPath expressions using the 1-based index `$i+1`.

### §9.2 — Event Container

| Field | Source | Notes |
|-------|--------|-------|
| `event @extId` | `OMXUtils:generateTrackingID()` | Correct — generated inside XSLT |
| `RefID` | `$orderRequest/OrderData/Customer/RefId` | Customer-level — same for all BundleInfo dispatches [MEDIUM] |

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$orderRequest/OrderData/Customer/RefId` | Always (customer-level) |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Always |

### §9.4 — Payload Root Element

`payload / ns:submitCampaignReq` — namespace: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ATS/SubmitCampaignRequest.xsd`

### §9.5 — Conditional Fields

| Field | Condition | Source / Value |
|-------|-----------|----------------|
| `ns:channel` | Always | `"OMX-Mobile"` (static) |
| `ns:requestName` | if `BundleInfo[$i+1]/ConvergenceAction` | `BundleInfo[$i+1]/ConvergenceAction` |
| `ns:activityCode` | if ConvergenceAction="DebundleCampaign" | `"Debundle"` (static) |
| `ns:disconnectedBy` | if ConvergenceAction="DebundleCampaign" | `"OMX-Mobile"` (static) |
| `ns:reasonCode` | if ConvergenceAction="DebundleCampaign" | `"DB02"` (static) |
| `ns:cancelReasonCode` | if ConvergenceAction="DebundleCampaign" | `"DB02"` (static) |
| `ns:campaignInfo/ns:campaignCode` | if `BundleInfo[$i+1]/CampaignCode` | `BundleInfo[$i+1]/CampaignCode` |
| `ns:campaignInfo/ns:convergenceType` | if `BundleInfo[$i+1]/ConvergenceType` | `BundleInfo[$i+1]/ConvergenceType` |
| `ns:campaignInfo/ns:truelifeId` | if `BundleInfo[$i+1]/TruelifeId` | `BundleInfo[$i+1]/TruelifeId` |
| `ns:campaignInfo/ns:productList` | if ConvergenceAction="DebundleProductNumber" | See §9.6 productId three-way logic |

### §9.6 — productId Three-Way Fallback Logic

Only emitted when `ConvergenceAction="DebundleProductNumber"`. productId selection:

| Priority | Condition | productId Source |
|----------|-----------|----------------|
| 1 (BREAK action) | `ExtendedInfo[Name='ACTION']/Value = "BREAK"` | `substring-after(ExtendedInfo[Name='GROUP']/Value, "PRODUCT_ID=")` |
| 2 (Matching subscriber) | `ParentOU[1]/Subscriber[FE_OR_CCBS!='ATS' or no FE_OR_CCBS, and CampaignCode matches BundleInfo]` exists | That subscriber's `MSISDN` |
| 3a (First POU subscriber) | `ParentOU[1]/Subscriber[1]/MSISDN` exists | `ParentOU[1]/Subscriber[1]/MSISDN` |
| 3b (First COU subscriber) | Otherwise | `ParentOU[1]/ChildOU[1]/Subscriber[1]/MSISDN` |

`ns:productType` ← `"TMV"` (static) always accompanies the productId.

> The subscriber matching in Priority 2 uses a complex XPath predicate combining `ExtendedInfo[Name="FE_OR_CCBS"]/Value!="ATS"` with an `or not(ExtendedInfo[Name="FE_OR_CCBS"])`. The `or` operator may have precedence issues — verify predicate intent against actual data.

### §9.7 — Complete Generated XML Example

**DebundleCampaign mode:**

```xml
<createEvent>
  <event extId="OMX-TRK-20240801-010">
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20240801-001</JMSCorrelationID>
    <OrderID>ORD-9001</OrderID>
    <RefID>CUST-REF-001</RefID>
    <OrderType>POSTPAID_REMOVE_OFFER_SUB</OrderType>
    <payload>
      <ns:submitCampaignReq xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ATS/SubmitCampaignRequest.xsd">
        <ns:channel>OMX-Mobile</ns:channel>
        <ns:requestName>DebundleCampaign</ns:requestName>
        <ns:activityCode>Debundle</ns:activityCode>
        <ns:disconnectedBy>OMX-Mobile</ns:disconnectedBy>
        <ns:reasonCode>DB02</ns:reasonCode>
        <ns:cancelReasonCode>DB02</ns:cancelReasonCode>
        <ns:campaignInfo>
          <ns:campaignCode>CAMP-001</ns:campaignCode>
          <ns:convergenceType>MOBILE_FIXED</ns:convergenceType>
          <ns:truelifeId>TL-12345</ns:truelifeId>
        </ns:campaignInfo>
      </ns:submitCampaignReq>
    </payload>
  </event>
</createEvent>
```

### §9.8 — XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ATS/SubmitCampaignRequest.xsd"
  version="1.0">
  <xsl:param name="orderRequest"/>   <!-- root order concept -->
  <xsl:param name="i"/>              <!-- 0-based BundleInfo index; used as $i+1 in XPath -->
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <RefID><xsl:value-of select="$orderRequest/OrderData/Customer/RefId"/></RefID>  <!-- customer-level [MEDIUM] -->
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        <payload>
          <ns:submitCampaignReq>
            <ns:channel><xsl:value-of select="'OMX-Mobile'"/></ns:channel>
            <xsl:if test="$orderRequest/OrderData/BundleInfo[$i+1]/ConvergenceAction">
              <ns:requestName><xsl:value-of select="$orderRequest/OrderData/BundleInfo[$i+1]/ConvergenceAction"/></ns:requestName>
            </xsl:if>
            <!-- Fields only for DebundleCampaign -->
            <xsl:if test="$orderRequest/OrderData/BundleInfo[$i+1]/ConvergenceAction='DebundleCampaign'">
              <ns:activityCode>Debundle</ns:activityCode>
            </xsl:if>
            <xsl:if test="$orderRequest/OrderData/BundleInfo[$i+1]/ConvergenceAction='DebundleCampaign'">
              <ns:disconnectedBy>OMX-Mobile</ns:disconnectedBy>
            </xsl:if>
            <xsl:if test="$orderRequest/OrderData/BundleInfo[$i+1]/ConvergenceAction='DebundleCampaign'">
              <ns:reasonCode>DB02</ns:reasonCode>
            </xsl:if>
            <xsl:if test="$orderRequest/OrderData/BundleInfo[$i+1]/ConvergenceAction='DebundleCampaign'">
              <ns:cancelReasonCode>DB02</ns:cancelReasonCode>
            </xsl:if>
            <ns:campaignInfo>
              <xsl:if test="$orderRequest/OrderData/BundleInfo[$i+1]/CampaignCode">
                <ns:campaignCode><xsl:value-of select="$orderRequest/OrderData/BundleInfo[$i+1]/CampaignCode"/></ns:campaignCode>
              </xsl:if>
              <xsl:if test="$orderRequest/OrderData/BundleInfo[$i+1]/ConvergenceType">
                <ns:convergenceType><xsl:value-of select="$orderRequest/OrderData/BundleInfo[$i+1]/ConvergenceType"/></ns:convergenceType>
              </xsl:if>
              <xsl:if test="$orderRequest/OrderData/BundleInfo[$i+1]/TruelifeId">
                <ns:truelifeId><xsl:value-of select="$orderRequest/OrderData/BundleInfo[$i+1]/TruelifeId"/></ns:truelifeId>
              </xsl:if>
              <!-- productList: only for DebundleProductNumber -->
              <xsl:if test="$orderRequest/OrderData/BundleInfo[$i+1]/ConvergenceAction='DebundleProductNumber'">
                <ns:productList>
                  <xsl:choose>
                    <xsl:when test="$orderRequest/OrderData/ExtendedInfo[Name='ACTION']/Value='BREAK'">
                      <ns:productId><xsl:value-of select="substring-after(ExtendedInfo[Name='GROUP']/Value,'PRODUCT_ID=')"/></ns:productId>
                    </xsl:when>
                    <xsl:otherwise>
                      <!-- Priority 2: find subscriber with matching CampaignCode and non-ATS FE_OR_CCBS -->
                      <xsl:choose>
                        <xsl:when test="[matching subscriber with CampaignCode and FE_OR_CCBS!='ATS' exists]">
                          <!-- use that subscriber's MSISDN -->
                        </xsl:when>
                        <xsl:otherwise>
                          <!-- Priority 3a/3b: first subscriber MSISDN fallback -->
                          <xsl:choose>
                            <xsl:when test="$orderRequest/OrderData/Customer/ParentOU[1]/Subscriber[1]/MSISDN">
                              <!-- use ParentOU[1]/Subscriber[1]/MSISDN -->
                            </xsl:when>
                            <xsl:otherwise>
                              <!-- use ParentOU[1]/ChildOU[1]/Subscriber[1]/MSISDN -->
                            </xsl:otherwise>
                          </xsl:choose>
                        </xsl:otherwise>
                      </xsl:choose>
                    </xsl:otherwise>
                  </xsl:choose>
                  <ns:productType>TMV</ns:productType>
                </ns:productList>
              </xsl:if>
            </ns:campaignInfo>
          </ns:submitCampaignReq>
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
└── event
    ├── @extId              ← OMXUtils:generateTrackingID() (inside XSLT)          [Always]
    ├── JMSPriority         ← $orderRequest/OrderPriority                           [Always]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId                 [Always]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                       [Always]
    ├── RefID               ← $orderRequest/OrderData/Customer/RefId                [Always] [MEDIUM: customer-level]
    ├── OrderType           ← $orderRequest/OrderData/OrderType                     [Always]
    └── payload
        └── ns:submitCampaignReq
            ├── ns:channel              ← "OMX-Mobile" (static)                    [Always]
            ├── ns:requestName          ← BundleInfo[$i+1]/ConvergenceAction        [Conditional: if ConvergenceAction exists]
            ├── ns:activityCode         ← "Debundle" (static)                      [Conditional: if ConvergenceAction="DebundleCampaign"]
            ├── ns:disconnectedBy       ← "OMX-Mobile" (static)                    [Conditional: if ConvergenceAction="DebundleCampaign"]
            ├── ns:reasonCode           ← "DB02" (static)                          [Conditional: if ConvergenceAction="DebundleCampaign"]
            ├── ns:cancelReasonCode     ← "DB02" (static)                          [Conditional: if ConvergenceAction="DebundleCampaign"]
            └── ns:campaignInfo
                ├── ns:campaignCode     ← BundleInfo[$i+1]/CampaignCode            [Conditional]
                ├── ns:convergenceType  ← BundleInfo[$i+1]/ConvergenceType         [Conditional]
                ├── ns:truelifeId       ← BundleInfo[$i+1]/TruelifeId             [Conditional]
                └── ns:productList                                                  [Conditional: only if ConvergenceAction="DebundleProductNumber"]
                    ├── ns:productId    ← 3-way fallback:
                    │   ├── P1 (ACTION=BREAK): substring-after(ExtendedInfo[GROUP]/Value, "PRODUCT_ID=")
                    │   ├── P2 (matching subscriber): ParentOU[1]/Subscriber[FE_OR_CCBS!='ATS', CampaignCode match]/MSISDN
                    │   ├── P3a (first POU sub): ParentOU[1]/Subscriber[1]/MSISDN
                    │   └── P3b (first COU sub): ParentOU[1]/ChildOU[1]/Subscriber[1]/MSISDN
                    └── ns:productType  ← "TMV" (static)                          [Always inside productList]
```

Legend: `[Always]` = no xsl:if guard · `[Conditional: ...]` = inside xsl:if or xsl:choose · XPath in plain text = working memory source · `"quoted"` = static literal

---

## §11 — Audit Logging

| Phase | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE |
|-------|-----------|----------------|-------------|
| REQUEST | `concat(nanoTime(), "_REQ")` | `"ATS_DEBUNDLE_CAMPAIGN"` | `"Request Sent for ATS_DEBUNDLE_CAMPAIGN"` |
| RESPONSE | `concat(nanoTime(), "_RES")` | `"ATS_DEBUNDLE_CAMPAIGN"` | `"Response received for ATS_DEBUNDLE_CAMPAIGN"` |

> Response audit `AUDIT_TRACE` is a static string — does not include RefID. This differs from most other FMs which include RefID in the response trace.

---

## §12 — Activity Status Management

| Scenario | Status Code | Function | Meaning |
|----------|------------|---------|---------|
| At least one BundleInfo dispatch sent | `"1"` | `GetActivityStatusString("1", false)` | SENT |
| No dispatches (PreExecCheck failed or all null) | `"4"` | `SkipActivity(…, "4")` | SKIPPED |

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 — Helper Functions Reference

| Function | Return Type | Purpose |
|----------|------------|---------|
| `Instance.serializeUsingDefaults(orderRequest)` | String | Serialise full order concept to XML for PreExecCheck (order-level, not subscriber-level) |
| `XPath.evalAsInt("count($orderRequest/OrderData/BundleInfo)")` | int | Count BundleInfo entries |
| `GetActivityStatusString("1", false)` | String | Status SENT |
| `SkipActivity(orderRequest, activity, "4")` | void | Skip activity |
| `SendDataToDB(orderRequest)` | void | Persist order state |
| `HandleActivityException(orderRequest, activity, ae, "")` | void | Error handler |

---

## §15 — Function Dependency Tree

```text
Request_ATS_DEBUNDLE_CAMPAIGN (rule)
├── Instance.serializeUsingDefaults                     [PreExecCheck serialisation — order-level]
├── XPath.execute                                        [PreExecCheck evaluation]
├── XPath.evalAsInt                                      [count BundleInfo entries]
├── OMXUtils:generateTrackingID()                       [event @extId — inside XSLT]
├── Event.Ext.sendEventImmediate                        [x2: reqEvent + logger per BundleInfo]
├── RuleFunctions.Helpers.GetActivityStatusString       [status "1"]
├── RuleFunctions.Helpers.SendDataToDB                  [DB persistence]
├── RuleFunctions.Helpers.SkipActivity                  [skip path]
└── RuleFunctions.Helpers.HandleActivityException       [error handling]

Response_ATS_DEBUNDLE_CAMPAIGN (rulefunction)
├── OMXUtils:generateTrackingID()                       [ResponseBase @extId — inside XSLT directly]
├── Instance.createInstance (ResponseBase XSLT)         [construct response record]
├── XPath.evalAsInt                                     [fan-in count]
├── Event.Ext.sendEventImmediate                        [response audit logger]
└── [return "true" / "false"]                           [fan-in completion signal]
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Fields Used | Role |
|---------|----------------|------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.BundleInfo[], OrderData.Customer.RefId, OrderData.OMXTrackingId, OrderData.ExtendedInfo, OrderPriority | Root order + BundleInfo catalogue |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck | Activity tracking |
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId | Normalised response record |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement | Evidence |
|----|------------|---------|
| R1 | Call ATS SubmitCampaign API for each BundleInfo entry with non-null ConvergenceAction | Rule: BundleInfo loop with null gate |
| R2 | Support DebundleCampaign mode: send fixed codes activityCode="Debundle", reasonCode="DB02", cancelReasonCode="DB02" | XSLT: four xsl:if blocks on ConvergenceAction="DebundleCampaign" |
| R3 | Support DebundleProductNumber mode: compute productId via three-way fallback (BREAK action / matching subscriber / first subscriber) | XSLT: nested xsl:choose |
| R4 | Order-level PreExecCheck (not subscriber-level) gating entire FM | Rule: `Instance.serializeUsingDefaults(orderRequest)` |
| R5 | Standard fan-in: all BundleInfo dispatches must complete before advancing | Response: `RequestCount == successResponseCount` |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| No resubmit-skip for BundleInfo items — all items re-dispatched on every resubmit, causing duplicate ATS debundle calls | [HIGH] | Add per-BundleInfo completion tracking: use composite key `Customer/RefId + ":" + i` as RefID, check against Response array before re-dispatch |
| Customer-level RefID shared across all BundleInfo dispatches — response correlation impossible per item | [MEDIUM] | Use per-BundleInfo composite RefID (e.g., `Customer/RefId + ":" + CampaignCode`) in modernised service |
| Author field is machine hostname `DESKTOP-995HR2V` — no developer attribution; suggests rushed development | [MEDIUM] | Source control attribution; enforce developer name in templates |
| XPath predicate for Priority 2 subscriber match may have `or` precedence issue — selects subscribers without CampaignCode match if FE_OR_CCBS is absent | [MEDIUM] | Add explicit parentheses: `(FE_OR_CCBS!='ATS' or not(FE_OR_CCBS)) and contains(CampaignCode, ...)` |
| Four separate xsl:if blocks all testing the same `ConvergenceAction="DebundleCampaign"` condition | [LOW] | Consolidate into one xsl:if block or xsl:choose in modernised service |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author DESKTOP-995HR2V
 */
rule Rules.OMConsumers.OMXFM.Request.Request_ATS_DEBUNDLE_CAMPAIGN {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "ATS_DEBUNDLE_CAMPAIGN";
        orderRequest.ProcessFlow.NextActivityID == "ATS_DEBUNDLE_CAMPAIGN";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
            String chkXPath = nextAct.PreExecCheck;
            String chkRes = "true";
            boolean isSkipped = true;

            if(String.length(nextAct.PreExecCheck) > 0) {
                // Order-level serialisation — NOT GetXMLForSubscriber
                String sXML = Instance.serializeUsingDefaults(orderRequest);
                chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=www.tibco.com/be/ontology/...");
            }

            if(String.equals(chkRes, "true")) {
                int bundleInfoSize = XPath.evalAsInt("count($orderRequest/OrderData/BundleInfo)");
                for (int i=0; i<bundleInfoSize; i++) {
                    if (orderRequest.OrderData.BundleInfo[i].ConvergenceAction != null) {
                        // [HIGH] No resubmit-skip check — always dispatches on resubmit
                        /* Build ns:submitCampaignReq event — see §9.8 for full XSLT:
                           params: orderRequest, i
                           DebundleCampaign mode: channel, requestName, activityCode="Debundle",
                             disconnectedBy="OMX-Mobile", reasonCode="DB02", cancelReasonCode="DB02",
                             campaignCode, convergenceType, truelifeId
                           DebundleProductNumber mode: channel, requestName, campaignCode,
                             convergenceType, truelifeId, productList (3-way productId + "TMV") */
                        Events.OMConsumers.OMXFM.Request.ATS_SUBMIT_CAMPAIGN reqEvent =
                            Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/ATS_SUBMIT_CAMPAIGN}}...");
                        Event.Ext.sendEventImmediate(reqEvent);

                        if(!isActResub) orderCurrentActivity.RequestCount++;

                        long pid = System.nanoTime();
                        /* Audit logger: OPERATION_NAME="ATS_DEBUNDLE_CAMPAIGN", PROCESS_ID=pid+"_REQ" */
                        Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{/Events/OMConsumers/OMXESB/Logger}}..."));
                        isSkipped = false;
                    }
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

**Response_ATS_DEBUNDLE_CAMPAIGN** handles ATS SubmitCampaign response events for the debundle operation. It creates a `ResponseBase` record, emits response audit log, and drives fan-in completion. The response rulefunction listens on the shared `ATS_SUBMIT_CAMPAIGN` response event type.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.ATS_SUBMIT_CAMPAIGN` | Inbound ATS response (shared event type) |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking |

### §19.3 — ResponseBase Concept Construction

> **Correct pattern:** `OMXUtils:generateTrackingID()` is called directly inside the XSLT `<xsl:value-of select="OMXUtils:generateTrackingID()"/>` — no Java variable needed. This is an alternative correct pattern to the Java-variable approach used in MCS_GET_PACKCODE.

```text
createObject
└── object
    ├── @extId              ← OMXUtils:generateTrackingID() (inside XSLT)   [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode                    [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg                     [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus                [Conditional]
    └── ReferenceId         ← $eventResponse/RefID                          [Conditional]
```

### §19.4 — Response Completion Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

```java
if (currActivity.RequestCount == successResponseCount) { return "true"; }
else { return "false"; }
```

> Standard correct fan-in. Because the request uses a customer-level RefID (same for all dispatches), the response matching relies solely on the count of successful ResponseCodes rather than RefID correlation — acceptable for this pattern.

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| `PROCESS_ID` | `concat(nanoTime(), "_RES")` |
| `OPERATION_NAME` | `"ATS_DEBUNDLE_CAMPAIGN"` |
| `AUDIT_TRACE` | `"Response received for ATS_DEBUNDLE_CAMPAIGN"` (static — no RefID) |
| `payload` | Copy of `$eventResponse` — gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
