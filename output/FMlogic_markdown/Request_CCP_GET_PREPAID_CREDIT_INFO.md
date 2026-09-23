# Request_CCP_GET_PREPAID_CREDIT_INFO

> TIBCO BusinessEvents · FM Logic Documentation

---

## §1 — Overview & Purpose

Retrieves prepaid account credit information from **CCP (Charging Control Platform)** for every subscriber in the order. For each subscriber the rule fires a `GetPrepaidCreditInfoRequest` JMS event containing the MSISDN and order channel. The response handler populates financial balance fields, updates the subscriber's price plan offer (unless the order type is in the *PricePlanFromCCBS* exclusion list), sets the subscriber's UI language, and writes eight `ExtendedInfo` keys for downstream activities.

> **Business Purpose:** Before cancelling or modifying a prepaid subscription, OMX must know the subscriber's current credit balance, promotional allowances, price plan, and VAS status so they can be correctly applied to the refund, cancellation, or port-out flow.

| Item | Value |
|------|-------|
| Rule class | `Rules.OMConsumers.OMXFM.Request.Request_CCP_GET_PREPAID_CREDIT_INFO` |
| Author | jninan-t420 |
| Target system | CCP — Charging Control Platform |
| Operation | GetPrepaidCreditInfo |
| Schema namespace | `http://services.omx.truecorp.co.th/FM/GetPrepaidCreditInfoRequest` |
| Response namespace | `http://services.omx.truecorp.co.th/FM/GetPrepaidCreditInfoResponse` |
| Response concept extId prefix | `GPCIR:{OMXTrackingId}:{RefID}` |
| Fan-in condition | `RequestCount == Response@length` (all responses, success or failure) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule type | `rule` | Stateful RETE-based rule; fires when all WHEN conditions match |
| priority | 5 | Standard FM request priority |
| forwardChain | true | Rule re-evaluates if working memory changes during execution |
| Rule file | Request_CCP_GET_PREPAID_CREDIT_INFO.rule | Under Rules/OMConsumers/OMXFM/Request/ |
| Response file | Response_CCP_GET_PREPAID_CREDIT_INFO.rulefunction | Under RuleFunctions/OrderResponse/ |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Root order object — holds customer hierarchy, order type, channel, tracking ID |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Current activity definition — holds Status, RequestCount, Response array, PreExecCheck |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Meaning |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | The activity object matches the order's current scheduled step |
| 2 | `orderCurrentActivity.ActivityID == "CCP_GET_PREPAID_CREDIT_INFO"` | This rule only fires for the CCP credit-info activity |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCP_GET_PREPAID_CREDIT_INFO"` | Process flow pointer confirms this FM is next |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity is in WAITING state — prevents duplicate firing |

All four conditions must be true simultaneously.

---

## §5 — Execution Flow Diagram

1. **Resubmit flag** → compute `isActResub = (RequestCount>0 && IsOrderResubmitted)` — if true, RequestCount will not be incremented again
2. **Load next activity** → fetch Activity concept by extId to read `PreExecCheck`
3. **ParentOU loop** → iterate all ParentOU subscribers: dedup guard → PreExecCheck → send CCP request → audit log → increment RequestCount
4. **ChildOU loop** → identical logic for ChildOU subscribers nested within each ParentOU
5. **Skip / activate** → if no request sent (`isSkipped=true`), call `SkipActivity("4")`; otherwise set "IN_PROGRESS" and persist via `SendDataToDB`
6. **Exception** → any uncaught exception routed to `HandleActivityException`

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

| Step | Code path | Detail |
|------|-----------|--------|
| Resubmit check | `isActResub` | `RequestCount>0 && IsOrderResubmitted` |
| Dedup guard (per subscriber) | `Response[iResp].ReferenceId==refId && CompletionStatus==2` | Skip subscriber if a successful response already exists |
| PreExecCheck | `GetXMLForSubscriber / GetXMLForSubscriberInChildOU` | XPath evaluated against subscriber XML; skip if result != "true" |
| Send CCP event | `Event.Ext.sendEventImmediate(reqEvent)` | XSLT builds `GetPrepaidCreditInfoRequest` with MSISDN + OrderChannel |
| Audit log | `AllowWriteLog gate` | Static AUDIT_TRACE: *"Request Sent for CCP_GET_PREPAID_CREDIT_INFO"* |
| RequestCount | `if(!isActResub) orderCurrentActivity.RequestCount++` | Incremented after audit log |
| Status transition | `GetActivityStatusString("1", false)` | Sets activity to "IN_PROGRESS" |
| Persist | `SendDataToDB(orderRequest)` | Writes updated order state to database |

---

## §7 — Data Extraction

No pipe-delimited or encoded parsing is performed in the request rule. The XSLT reads scalar fields directly:

| Field extracted | Source XPath | Usage |
|----------------|--------------|-------|
| MSISDN | `$orderRequest/OrderData/Customer/ParentOU[i]/Subscriber[j]/MSISDN` | Payload element `<ns:MSISDN>` |
| OrderChannel | `$orderRequest/OrderData/Channel` | Payload element `<ns:OrderChannel>` |
| RefId | `Subscriber[j].RefId` | Event header `<RefID>` and dedup key |
| OrderType | `$orderRequest/OrderData/OrderType` | Event header `<OrderType>` |

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

This FM fires for any order type that includes `CCP_GET_PREPAID_CREDIT_INFO` in its ProcessConfig, including **PREPAID_CANCEL**, prepaid port-out, and prepaid swap flows. The response handler has an additional gate via GlobalVar `OMX_OM/OrderTypes/PricePlanFromCCBS` (default `,53,60,68,`) — for order types **53 (PreToPost)**, **60 (MNPPrepaidPortOut)**, and **68 (SwapSIM)**, the price plan is taken from CCBS instead of CCP.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event type | Purpose |
|-----------|------------|---------|
| [OUTBOUND] | Events.OMConsumers.OMXFM.Request.CCP_GET_PREPAID_CREDIT_INFO | Send GetPrepaidCreditInfoRequest to CCP |
| [LOG] | Events.OMConsumers.OMXESB.Logger | Audit log trail |
| [INBOUND] | Events.OMConsumers.OMXFM.Response.CCP_GET_PREPAID_CREDIT_INFO | Receive GetPrepaidCreditInfoResponse from CCP |

### §8.3 Backend API Details

| System | Operation | Schema | Protocol |
|--------|-----------|--------|----------|
| CCP | GetPrepaidCreditInfo | `http://services.omx.truecorp.co.th/FM/GetPrepaidCreditInfoRequest` | JMS via ESB FM channel |

Correlation: `JMSCorrelationID = OMXTrackingId`; per-subscriber matching via `RefID`.

### §8.4 BE Working Memory Dependencies

| Concept | Access | Fields |
|---------|--------|--------|
| OrderRequest | READ | OrderData.OMXTrackingId, OrderType, Channel, Customer.ParentOU[].Subscriber[], IsOrderResubmitted, OrderPriority |
| Activity (current) | READ/WRITE | Status (WRITE), RequestCount (WRITE), Response[] (READ dedup), PreExecCheck (READ) |
| Activity (next) | READ | PreExecCheck XPath expression |
| Subscriber | READ/WRITE (response) | SubscriberOffers[] (WRITE), SubscriberGeneralInfo.Language (WRITE), ExtendedInfo[] (WRITE) |
| CCP_GET_PREPAID_CREDIT_INFO (response concept) | WRITE | See §19.3 — extId=GPCIR:..., 14 fields |

### §8.5 ExtendedInfo Fields Written (Response Handler)

| Name | Source field | Target subscriber | Notes |
|------|-------------|-------------------|-------|
| `MAIN_CREDIT` | ns:CreditBalance | subscriber + subscriberTarget | Main prepaid balance |
| `PROMO_CREDIT` | ns:ATB | subscriber only | Available Topup Balance (promotional) |
| `BONUS_CREDIT` | ns:CallingBonus | subscriber only | Voice calling bonus |
| `DATA_CREDIT` | ns:DataBonus | subscriber only | Data bonus allowance |
| `MMS_CREDIT` | ns:MMSBonus | subscriber only | MMS bonus allowance |
| `CDB_STATUS` | ns:Status | subscriber only | CCP account status (naming: "CDB_" prefix despite CCP source) |
| `CDB_VAS` | ns:VAS | subscriber + subscriberTarget | VAS flag from CCP |
| `CDB_CONVERGENCE` | ns:Convergence | subscriber + subscriberTarget | Convergence flag from CCP |
| `PRICEPLAN_CCP` | ns:Priceplan | subscriberTarget only | Stored for _src subscriber in swap/port scenarios |

### §8.6 Global Variable Dependencies

| Path | Default | Used for |
|------|---------|---------|
| `OMX_OM/OrderTypes/PricePlanFromCCBS` | `,53,60,68,` | Skip SubscriberOffers update when OrderType in list |
| `OMX_COMMON/Component_Name/OMX_CEP` | — | Audit log COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | — | Audit log TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | — | Audit log LOG_LEVEL |
| `OMX_OM/WritePayload` | "true"/"false" | Gates payload inclusion in audit log |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Parameter | Bound from |
|-----------|------------|
| `$orderRequest` | Rule variable — the root OrderRequest concept |
| `$i` / `$j` | ParentOU loop index / Subscriber loop index |
| `$p` / `$q` | ChildOU loop index / ChildOU-Subscriber loop index (ChildOU variant) |
| `$POUIterator` | `number($i)+1` — 1-based ParentOU index for XPath |
| `$SubscriberIterator` | `number($j)+1` — 1-based Subscriber index for XPath |
| `$COUIterator` | `number($p)+1` — 1-based ChildOU index (ChildOU variant only) |

### §9.2 Event Container Construction

Event created via `Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/CCP_GET_PREPAID_CREDIT_INFO}}...")`. No explicit `extId` set — correlation via `JMSCorrelationID` and `RefID`.

### §9.3 JMS / Event Header Fields

| Header field | Source | Conditional? |
|-------------|--------|-------------|
| `JMSPriority` | `$orderRequest/OrderPriority` | [Conditional: if $orderRequest/OrderPriority] |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | [Conditional] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Conditional] |
| `RefID` | `ParentOU[i]/Subscriber[j]/RefId` | [Conditional] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Conditional] |

### §9.4 Payload Root Element

Namespace: `xmlns:ns="http://services.omx.truecorp.co.th/FM/GetPrepaidCreditInfoRequest"`
Root: `<ns:GetPrepaidCreditInfoRequest>`

### §9.5 Conditional Fields

All header fields are wrapped in `xsl:if` guards — absent values produce no output element (identical to CDB pattern).

### §9.6 Core Payload Block

| XML element | Source | Required? |
|-------------|--------|-----------|
| `<ns:MSISDN>` | `Subscriber[i].MSISDN` (no xsl:if) | [Always] |
| `<ns:OrderChannel>` | `$orderRequest/OrderData/Channel` (no xsl:if) | [Always] |

### §9.7 Complete Generated XML Example

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX20241201120000001</JMSCorrelationID>
    <OrderID>ORD-12345678</OrderID>
    <RefID>REF001</RefID>
    <OrderType>65</OrderType>
    <payload>
      <ns:GetPrepaidCreditInfoRequest
        xmlns:ns="http://services.omx.truecorp.co.th/FM/GetPrepaidCreditInfoRequest">
        <ns:MSISDN>0812345678</ns:MSISDN>
        <ns:OrderChannel>CS</ns:OrderChannel>
      </ns:GetPrepaidCreditInfoRequest>
    </payload>
  </event>
</createEvent>
```

### §9.8 XSLT Stylesheet Source

**ParentOU Variant ①**

```xml
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ns="http://services.omx.truecorp.co.th/FM/GetPrepaidCreditInfoRequest"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    version="1.0" exclude-result-prefixes="xsl ns xsd">
  <xsl:output method="xml"/>
  <!-- i=ParentOU index, j=Subscriber index -->
  <xsl:param name="orderRequest"/>
  <xsl:param name="i"/>
  <xsl:param name="j"/>
  <xsl:param name="POUIterator"/>
  <xsl:param name="SubscriberIterator"/>
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:if test="$orderRequest/OrderPriority">
          <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
          <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OrderID">
          <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        </xsl:if>
        <xsl:variable name="POUIterator" select="number($i)+1"/>
        <xsl:variable name="SubscriberIterator" select="number($j)+1"/>
        <xsl:if test="$orderRequest/OrderData/Customer/ParentOU[$POUIterator]/Subscriber[$SubscriberIterator]/RefId">
          <RefID><xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[$POUIterator]/Subscriber[$SubscriberIterator]/RefId"/></RefID>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OrderType">
          <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        </xsl:if>
        <payload>
          <ns:GetPrepaidCreditInfoRequest>
            <ns:MSISDN><xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[$POUIterator]/Subscriber[$SubscriberIterator]/MSISDN"/></ns:MSISDN>
            <ns:OrderChannel><xsl:value-of select="$orderRequest/OrderData/Channel"/></ns:OrderChannel>
          </ns:GetPrepaidCreditInfoRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**ChildOU Variant ② — differences from ①**

| Difference | ParentOU Variant ① | ChildOU Variant ② |
|-----------|---------------------|-------------------|
| Extra params | `$i, $j, $POUIterator, $SubscriberIterator` | Adds `$p, $q, $COUIterator` |
| MSISDN XPath | `ParentOU[$POUIterator]/Subscriber[$SubscriberIterator]/MSISDN` | `ParentOU[$POUIterator]/ChildOU[$COUIterator]/Subscriber[$SubscriberIterator]/MSISDN` |
| RefID XPath | `ParentOU[$POUIterator]/Subscriber[$SubscriberIterator]/RefId` | `ParentOU[$POUIterator]/ChildOU[$COUIterator]/Subscriber[$SubscriberIterator]/RefId` |
| OrderChannel | Identical — both use `$orderRequest/OrderData/Channel` | |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority       ← $orderRequest/OrderPriority                   [Conditional: if $orderRequest/OrderPriority]
    ├── JMSCorrelationID  ← $orderRequest/OrderData/OMXTrackingId         [Conditional: if OMXTrackingId]
    ├── OrderID           ← $orderRequest/OrderData/OrderID               [Conditional: if OrderID]
    ├── RefID             ← ParentOU[$i+1]/Subscriber[$j+1]/RefId         [Conditional: if RefId node exists]
    ├── OrderType         ← $orderRequest/OrderData/OrderType             [Conditional: if OrderType]
    └── payload                                                           [Always]
        └── ns:GetPrepaidCreditInfoRequest
            ├── ns:MSISDN        ← ParentOU[$i+1]/Subscriber[$j+1]/MSISDN   [Always]
            └── ns:OrderChannel  ← $orderRequest/OrderData/Channel           [Always]
```

**Legend:** `[Always]` = always emitted · `[Conditional: ...]` = inside xsl:if

---

## §11 — Audit Logging

| Log event | Field | Value |
|-----------|-------|-------|
| [REQUEST] Logger event | ESBUUID | OMXTrackingId |
| | PROCESS_ID | `concat(nanoTime, "_REQ")` |
| | COMPONENT_NAME | GlobalVar OMX_COMMON/Component_Name/OMX_CEP |
| | OPERATION_NAME | *"CCP_GET_PREPAID_CREDIT_INFO"* (static) |
| | TARGET_SYSTEM | GlobalVar OMX_COMMON/Component_Name/OMX_FM |
| | AUDIT_TRACE | *"Request Sent for CCP_GET_PREPAID_CREDIT_INFO"* (static — no RefId) |
| | payload | Conditional on `WritePayload="true"` |
| [RESPONSE] Logger event | PROCESS_ID | `concat(nanoTime, "_RES")` |
| | AUDIT_TRACE | *"Response received for CCP_GET_PREPAID_CREDIT_INFO"* |
| | payload | Conditional on WritePayload |

> **Note:** Unlike the CDB request audit log which includes `RefId` in AUDIT_TRACE, the CCP log uses a static string — harder to correlate individual subscriber requests.

---

## §12 — Activity Status Management

| Transition | Function | Code | Meaning |
|-----------|---------|------|---------|
| WAITING → IN_PROGRESS | GetActivityStatusString("1", false) | "1" | At least one request sent successfully |
| WAITING → SKIPPED | SkipActivity(orderRequest, orderCurrentActivity, "4") | "4" | All subscribers skipped (dedup or PreExecCheck) |

---

## §13 — Exception / Error Handling

The entire `try` block wrapping both loops is caught:

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

`HandleActivityException` marks the activity as FAILED, logs the error, and escalates to order-level error handling.

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|---------|--------|---------|
| `RuleFunctions.Helpers.GetXMLForSubscriber` | String (XML) | Serialises subscriber sub-tree for XPath PreExecCheck evaluation (ParentOU) |
| `RuleFunctions.Helpers.GetXMLForSubscriberInChildOU` | String (XML) | Serialises ChildOU subscriber sub-tree for PreExecCheck evaluation |
| `RuleFunctions.Helpers.AllowWriteLog` | boolean | Gates audit logging based on OrderType |
| `RuleFunctions.Helpers.GetActivityStatusString` | String | Maps numeric status code to status string constant |
| `RuleFunctions.Helpers.SendDataToDB` | void | Persists order state to database |
| `RuleFunctions.Helpers.SkipActivity` | void | Marks activity as skipped and advances process flow |
| `RuleFunctions.Helpers.HandleActivityException` | void | Handles uncaught exceptions — marks activity FAILED and escalates |
| `OMXUtils.generateTrackingID` | String | Generates unique extId for new concept instances (used in response) |

---

## §15 — Function Dependency Tree

```text
Request_CCP_GET_PREPAID_CREDIT_INFO (rule)
├── Instance.getByExtIdByUri(nextActivityName)
├── RuleFunctions.Helpers.GetXMLForSubscriber
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU
├── XPath.execute(PreExecCheck, xml)
├── Event.createEvent("xslt://...CCP_GET_PREPAID_CREDIT_INFO")
│   └── XSLT: GetPrepaidCreditInfoRequest builder
├── Event.Ext.sendEventImmediate(reqEvent)
├── RuleFunctions.Helpers.AllowWriteLog(OrderType)
├── Event.createEvent("xslt://...Logger")
├── Event.Ext.sendEventImmediate(logEvent)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(req, act, "4")
└── RuleFunctions.Helpers.HandleActivityException(...)

Response_CCP_GET_PREPAID_CREDIT_INFO (rulefunction)
├── Instance.createInstance("xslt://...CCP_GET_PREPAID_CREDIT_INFO")
│   └── XSLT: ResponseBase concept builder (GPCIR: extId, 14 fields)
├── Instance.getByExtIdByUri("SUB:..." fallback "CSUB:...")
├── String.endsWith(RefID, "_src")
├── Instance.getByExtIdByUri("SUB:..._src stripped" ...)
├── XPath.evalAsBoolean(Priceplan string-length > 0)
├── System.getGlobalVariableAsString("PricePlanFromCCBS")
├── String.contains(usedPPFromCCBS, OrderType)
├── Instance.createInstance("xslt://...SubscriberOffers")
│   └── XSLT: ppOff (SUBOF: extId, ServiceType=80, FE_OR_CCBS=CCP)
├── Instance.createInstance("xslt://...SubscriberExtendedInfo") x 8
│   └── XSLT: ExtendedInfo builders (MAIN_CREDIT, PROMO_CREDIT, BONUS_CREDIT,
│       DATA_CREDIT, MMS_CREDIT, CDB_STATUS, CDB_VAS, CDB_CONVERGENCE)
├── OMXUtils.generateTrackingID()
├── RuleFunctions.Helpers.AllowWriteLog(OrderType)
└── Event.createEvent("xslt://...Logger")
```

---

## §16 — Concept Definitions Referenced

| Concept | Key fields |
|---------|-----------|
| `Concepts.FM.Response.CCP_GET_PREPAID_CREDIT_INFO` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, MSISDN, PricePlan, CreditBalance, ATB, CallingBonus, DataBonus, MMSBonus, Status, VAS, Convergence, DefLang |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | extId (SUBOF:...), OfferName (priceplan), ServiceType="80", ExtendedInfo (FE_OR_CCBS="CCP") |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` | extId (UUID), Name (key), Value |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, SubscriberOffers[], SubscriberGeneralInfo.Language, ExtendedInfo[] |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Retrieve prepaid credit balance, bonus credits, price plan, VAS and convergence flags from CCP for each subscriber |
| R2 | Support fan-out to multiple subscribers (ParentOU and ChildOU) in a single activity |
| R3 | Gate price plan update by GlobalVar exclusion list (PricePlanFromCCBS) to avoid overriding CCBS-sourced price plans |
| R4 | Normalise subscriber UI language from CCP DefLang code (1→TH, 2→EN, else→EN) |
| R5 | Handle `_src` subscriber pattern — propagate select financial fields to source subscriber in swap/port scenarios |
| R6 | Write 8 ExtendedInfo keys (MAIN_CREDIT, PROMO_CREDIT, BONUS_CREDIT, DATA_CREDIT, MMS_CREDIT, CDB_STATUS, CDB_VAS, CDB_CONVERGENCE) for downstream consumption |
| R7 | Idempotent fan-out — deduplicate requests via CompletionStatus==2 guard |
| R8 | Pass OrderChannel to CCP for routing decisions |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| `Status` field in ResponseBase XSLT reads `$activityRes/Status` (self-reference on new concept) — field will always be empty | [MEDIUM] | Fix XSLT to read `$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:Status`; verify if `CDB_STATUS` ExtendedInfo is the workaround downstream |
| ExtendedInfo keys `CDB_STATUS`, `CDB_VAS`, `CDB_CONVERGENCE` use "CDB_" prefix despite being sourced from CCP — naming confusion with CDB_GET_PROFILE data | [MEDIUM] | Audit downstream consumers of these keys; rename to CCP_ prefix in modern system |
| Fan-in uses `Response@length` — failed responses satisfy fan-in and processing continues without error gate | [MEDIUM] | Add ResponseCode success check in modern replacement; implement compensation logic for failed subscribers |
| `_src` subscriber cross-reference lookup: if subscriberTarget lookup fails silently, target subscriber gets no enrichment | [LOW] | Add null-check logging for subscriberTarget; ensure test coverage for swap/port order types (68, 60) |
| PricePlanFromCCBS GlobalVar has hardcoded default `,53,60,68,` — new order types requiring CCBS price plan must be added manually | [LOW] | Document GlobalVar as required configuration; validate at startup |
| Request audit AUDIT_TRACE is static (no RefId) — harder to correlate individual subscriber logs | [LOW] | Add RefId to AUDIT_TRACE in modern system for per-subscriber traceability |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author jninan-t420
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCP_GET_PREPAID_CREDIT_INFO {
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
        orderCurrentActivity.ActivityID == "CCP_GET_PREPAID_CREDIT_INFO";
        orderRequest.ProcessFlow.NextActivityID == "CCP_GET_PREPAID_CREDIT_INFO";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
                orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
            int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
            String pouRefId = "";
            boolean isSkipped = true;

            // *** ParentOU Loop ***
            for (int i=0; i<iPOULen; i++) {
                pouRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;
                int iSubscriberLen = orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length;
                for(int j=0; j<iSubscriberLen; j++) {
                    String refId = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].RefId;
                    boolean reqSuccess = false;
                    for(int iResp=0; iResp<orderCurrentActivity.Response@length; iResp++)
                        if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, refId)
                            && orderCurrentActivity.Response[iResp].CompletionStatus==2)
                            reqSuccess = true;
                    if(!reqSuccess) {
                        String chkRes = "true";
                        if(String.length(nextAct.PreExecCheck) > 0) {
                            String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId);
                            chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML,
                                "ns0=www.tibco.com/be/ontology/Concepts/OrderRequest/OrderRequest");
                        }
                        if(String.equals(chkRes, "true")) {
                            Events.OMConsumers.OMXFM.Request.CCP_GET_PREPAID_CREDIT_INFO reqEvent =
                                Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/CCP_GET_PREPAID_CREDIT_INFO}}"
                                    /* §9.8 ParentOU Variant ①: GetPrepaidCreditInfoRequest with MSISDN + OrderChannel */);
                            Event.Ext.sendEventImmediate(reqEvent);
                            if(RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                                long pid = System.nanoTime();
                                Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{/Events/OMConsumers/OMXESB/Logger}}"
                                    /* AUDIT_TRACE="Request Sent for CCP_GET_PREPAID_CREDIT_INFO" */));
                            }
                            if(!isActResub) orderCurrentActivity.RequestCount++;
                            isSkipped = false;
                        }
                    }
                }
                // *** ChildOU Loop ***
                int iCOULen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU@length;
                for(int p=0; p<iCOULen; p++) {
                    /* identical dedup guard + PreExecCheck + send logic for ChildOU subscriber */
                    /* §9.8 ChildOU Variant ②: adds COUIterator to XPath */
                }
            }
            if(!isSkipped) {
                orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch(Exception ae) {
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

`Response_CCP_GET_PREPAID_CREDIT_INFO` receives the CCP reply for a single subscriber, creates the `CCP_GET_PREPAID_CREDIT_INFO` response concept, enriches the subscriber with financial balance fields and price plan data, normalises the UI language, and returns `"true"` when all parallel subscriber requests are complete. It contains the richest enrichment logic of any FM response handler in the PREPAID_CANCEL flow.

### §19.2 Scope Variables

| Variable | Type | Role |
|---------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Root order; provides OMXTrackingId and subscriber hierarchy |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.CCP_GET_PREPAID_CREDIT_INFO | Inbound CCP response event |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Current activity — receives response concept; drives fan-in counter |

### §19.3 ResponseBase Concept Construction

Concept type: `Concepts.FM.Response.CCP_GET_PREPAID_CREDIT_INFO`
ExtId: `GPCIR:{eventResponse.JMSCorrelationID}:{eventResponse.RefID}`

```text
createObject
└── object
    ├── @extId           ← concat("GPCIR:", JMSCorrelationID, ":", RefID)   [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode                       [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg                        [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus                   [Conditional]
    ├── ReferenceId      ← $eventResponse/RefID                             [Conditional]
    ├── MSISDN           ← ns:GetPrepaidCreditInfoResponse/ns:MSISDN        [Conditional]
    ├── PricePlan        ← ns:GetPrepaidCreditInfoResponse/ns:Priceplan     [Conditional] (source=Priceplan, target=PricePlan)
    ├── CreditBalance    ← ns:GetPrepaidCreditInfoResponse/ns:CreditBalance  [Conditional]
    ├── ATB              ← ns:GetPrepaidCreditInfoResponse/ns:ATB            [Conditional] (Available Topup Balance)
    ├── CallingBonus     ← ns:GetPrepaidCreditInfoResponse/ns:CallingBonus  [Conditional]
    ├── DataBonus        ← ns:GetPrepaidCreditInfoResponse/ns:DataBonus     [Conditional]
    ├── MMSBonus         ← ns:GetPrepaidCreditInfoResponse/ns:MMSBonus      [Conditional]
    ├── Status           ← $activityRes/Status                              [Conditional: ⚠ BUG — self-ref, always empty]
    ├── VAS              ← ns:GetPrepaidCreditInfoResponse/ns:VAS           [Conditional]
    ├── Convergence      ← ns:GetPrepaidCreditInfoResponse/ns:Convergence   [Conditional]
    └── DefLang          ← ns:GetPrepaidCreditInfoResponse/ns:DefLang       [Conditional] ("1"→TH, "2"→EN, else→EN)
```

### §19.4 Post-Construction Enrichment Logic

| Step | Logic | Detail |
|------|-------|--------|
| 1 | Subscriber lookup | `SUB:{OMXTrackingId}:{RefID}` → fallback `CSUB:{OMXTrackingId}:{RefID}` |
| 2 | _src pattern | If `RefID.endsWith("_src")`, look up target subscriber by `SUB:{OMXTrackingId}:{RefID before "_src"}` → fallback CSUB |
| 3 | Priceplan gate | If `ns:Priceplan` length > 0 AND OrderType NOT in PricePlanFromCCBS list → update SubscriberOffers with ServiceType="80", FE_OR_CCBS="CCP" |
| 4 | Language normalisation | DefLang "1"→ Language="TH"; "2" or else → Language="EN" (written to SubscriberGeneralInfo) |
| 5 | ExtendedInfo writes (subscriber) | 8 keys: MAIN_CREDIT, PROMO_CREDIT, BONUS_CREDIT, DATA_CREDIT, MMS_CREDIT, CDB_STATUS, CDB_VAS, CDB_CONVERGENCE |
| 6 | SubscriberTarget writes | 4 keys: MAIN_CREDIT, CDB_VAS, CDB_CONVERGENCE, PRICEPLAN_CCP; also Language normalisation |

### §19.5 Response Completion Logic (Fan-In)

**Fan-in condition:** `currActivity.RequestCount == currActivity.Response@length`

Returns `"true"` when the number of recorded responses equals the number of requests sent — regardless of ResponseCode.

> **Risk:** Unlike ASRM/INTX which only count `tib:right(ResponseCode,3)="000"` successes, this implementation advances the activity even when some subscribers returned errors.

### §19.6 Response XSLT Source

```xml
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ns="http://services.omx.truecorp.co.th/FM/GetPrepaidCreditInfoResponse"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    version="1.0">
  <xsl:param name="extId"/>         <!-- "GPCIR:{JMSCorrelationID}:{RefID}" -->
  <xsl:param name="eventResponse"/> <!-- inbound CCP response event -->
  <xsl:param name="activityRes"/>   <!-- ⚠ self-reference on new concept (Status reads from here) -->
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId"><xsl:value-of select="$extId"/></xsl:attribute>
        <xsl:if test="$eventResponse/ResponseCode"><ResponseCode><xsl:value-of select="$eventResponse/ResponseCode"/></ResponseCode></xsl:if>
        <xsl:if test="$eventResponse/ResponseMsg"><ResponseMessage><xsl:value-of select="$eventResponse/ResponseMsg"/></ResponseMessage></xsl:if>
        <xsl:if test="$eventResponse/CompletionStatus"><CompletionStatus><xsl:value-of select="$eventResponse/CompletionStatus"/></CompletionStatus></xsl:if>
        <xsl:if test="$eventResponse/RefID"><ReferenceId><xsl:value-of select="$eventResponse/RefID"/></ReferenceId></xsl:if>
        <xsl:if test="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:MSISDN">
          <MSISDN><xsl:value-of select="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:MSISDN"/></MSISDN>
        </xsl:if>
        <xsl:if test="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:Priceplan">
          <PricePlan><xsl:value-of select="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:Priceplan"/></PricePlan>
        </xsl:if>
        <xsl:if test="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:CreditBalance">
          <CreditBalance><xsl:value-of select="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:CreditBalance"/></CreditBalance>
        </xsl:if>
        <xsl:if test="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:ATB">
          <ATB><xsl:value-of select="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:ATB"/></ATB>
        </xsl:if>
        <xsl:if test="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:CallingBonus">
          <CallingBonus><xsl:value-of select="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:CallingBonus"/></CallingBonus>
        </xsl:if>
        <xsl:if test="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:DataBonus">
          <DataBonus><xsl:value-of select="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:DataBonus"/></DataBonus>
        </xsl:if>
        <xsl:if test="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:MMSBonus">
          <MMSBonus><xsl:value-of select="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:MMSBonus"/></MMSBonus>
        </xsl:if>
        <!-- ⚠ BUG: reads $activityRes/Status (self-ref, always empty) -->
        <xsl:if test="$activityRes/Status">
          <Status><xsl:value-of select="$activityRes/Status"/></Status>
        </xsl:if>
        <xsl:if test="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:VAS">
          <VAS><xsl:value-of select="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:VAS"/></VAS>
        </xsl:if>
        <xsl:if test="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:Convergence">
          <Convergence><xsl:value-of select="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:Convergence"/></Convergence>
        </xsl:if>
        <xsl:if test="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:DefLang">
          <DefLang><xsl:value-of select="$eventResponse/payload/ns:GetPrepaidCreditInfoResponse/ns:DefLang"/></DefLang>
        </xsl:if>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
