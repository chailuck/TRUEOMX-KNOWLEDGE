# Request_CAT_GOD

Product Catalog (CAT) — Batch Get Offer Details (GOD) for all unique offer names in the order

**Priority:** 5 | **forwardChain:** true | **Target:** CAT (Product Catalog) | **Pattern:** Batch — 1 event per activity | **PREPAID_CANCEL Steps:** 3 & 11

---

## §1 — Overview & Purpose

> **Different fan-out pattern:** Unlike most OMXFM rules that send one event per subscriber, CAT_GOD aggregates *all unique offer names* from the entire order (Agreement offers + SubscriberOffers + RelatedOffersArray across all ParentOU and ChildOU), then sends a **single batch lookup** to the Product Catalog. RequestCount is always 1.

`Request_CAT_GOD` fires when the order process reaches activity `CAT_GOD`. It queries the Product Catalog (CAT) service for offer metadata — commercial details, SOC codes, service types, switch features, child offers, and contract parameters — for every distinct offer name present in the order. The response enriches every matching Agreement offer and SubscriberOffer with `SocProperties`, `Soc`, `ServiceType`, `SwitchFeature[]`, and `RelatedOffersArray`.

In **PREPAID_CANCEL**, CAT_GOD is called at two steps:
- **Step 3 (CAT_GOD)** — PreExecCheck: `count(//Offers)>0 or count(//SubscriberOffers)>0` — fires if the order has any offers at all; evaluates each offer against the check
- **Step 11 (CAT_GOD_B)** — PreExecCheck includes FE_OR_CCBS in (CCP, BRMS_REMOVE) — more selective; only offers from CCP or BRMS_REMOVE channels qualify

| Property | Value |
|----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CAT_GOD` |
| Author | awalia-t420 |
| Backend system | CAT (Product Catalog) — `SearchOfferNameList` service |
| Fan-out pattern | **Batch** — one single event with all offer names; RequestCount = 1 |
| In PREPAID_CANCEL | Steps 3 (CAT_GOD) and 11 (CAT_GOD_B) |
| Request event | `Events.OMConsumers.OMXFM.Request.CAT_GOD` |
| Response RF | `RuleFunctions.OrderResponse.Response_CAT_GOD` |
| Response concept | `Concepts.FM.Response.CAT_GOD.CatGodResponse` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | `5` | Standard FM request priority |
| forwardChain | `true` | Re-evaluates when working memory changes |
| Rule type | Batch Request | Sends ONE event with all offer names; different from per-subscriber fan-out |
| Source path | `Rules/OMConsumers/OMXFM/Request/Request_CAT_GOD.rule` | |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order object; source of entire offer hierarchy |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process activity; drives rule firing, holds RequestCount |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to process flow position |
| 2 | `orderCurrentActivity.ActivityID == "CAT_GOD"` | Fires only for this specific FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CAT_GOD"` | Double-check from order side |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Prevents double-firing |

---

## §5 — Execution Flow Diagram

1. **Re-submit check** — `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. **Collect unique offer names** — build an ArrayList (`arrLstSOCs`) by scanning the entire order hierarchy:
   - ParentOU[i].Agreement.Offers[j] — if PreExecCheck passes: add OfferName
   - ParentOU[i].Subscriber[j].SubscriberOffers[k] — if PreExecCheck passes and not in list: add OfferName, then add all RelatedOffersArray offer names (dedup only, no PreExecCheck)
   - ParentOU[i].ChildOU[k].Agreement.Offers[j] — same pattern
   - ParentOU[i].ChildOU[k].Subscriber[j].SubscriberOffers[m] — same pattern
3. **Send batch event** — if `socIDs != null && size > 0`: build single `CAT_GOD` event with all offer names as repeated `<ns1:name>` elements; send via `sendEventImmediate`
4. **Audit log** — if AllowWriteLog: send logger event (PROCESS_ID suffix "_REQ")
5. **Increment RequestCount by 1** (not per-offer) — if not re-submit; isSkipped = false
6. **Status update** — if any request sent: `Status="1"` + `SendDataToDB`; else `SkipActivity("4")`
7. **Exception** — catch block → `HandleActivityException`

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

> **Per-offer PreExecCheck:** The PreExecCheck is evaluated per offer item, not per subscriber. For Agreement offers, `GetXMLForAgreementOffer(orderRequest, agreement.RefId, currSoc)` is called. For SubscriberOffers, `GetXMLForSubscriberOffer(orderRequest, subscriber.RefId, currSoc)`. Only offers passing the check are included in the batch.

> **[LOW] Commented-out PreExecCheck approach:** Lines 30-33 show an older approach that evaluated the PreExecCheck against the entire `orderRequest` serialized to XML (not per-offer). This was replaced by the per-offer evaluation. The old code (`Instance.serializeUsingDefaults`) is still present but commented out. Also, the outer `if(chkRes=="true")` block (lines 35, 156) is commented out — the entire offer collection always runs.

```java
// Offer aggregation pseudocode
Object[] socIDs = Collections.toArray(arrLstSOCs); // unique offer names
if (socIDs != null && Collections.size(arrLstSOCs) > 0) {
  Events.OMConsumers.OMXFM.Request.CAT_GOD reqEvent = Event.createEvent("xslt://...");
  // → Payload: SearchOfferNameListReq with all offer names + pagination(page=1,perPage=100)
  Event.Ext.sendEventImmediate(reqEvent);
  isSkipped = false;
  if(!isActResub) orderCurrentActivity.RequestCount++; // always just 1
}
```

---

## §7 — Data Extraction

No activity parameters drive the request payload. The offer name list is built dynamically from order data. Response RF reads three parameters:

| Parameter Key | Helper | Used in | Purpose |
|---------------|--------|---------|---------|
| `IGNORE_CCP` | GetActivityParamValueFromKey | Response RF | If "Y", skips SwitchFeature population for offers tagged FE_OR_CCBS="CCP" |
| `GET_SWITCH_FEATURE` | GetActivityParameterValueFromKey | Response RF | If "N", suppresses SwitchFeature population entirely |
| `SERVICE_TYPE` | GetActivityParamValueFromKey | Response RF | If set and hasGodResult=false: forces all offers to this ServiceType and skips enrichment |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Called for any order type that has offers to look up. In PREPAID_CANCEL:
- **Step 3:** Fire if *any* Offers or SubscriberOffers exist — catches all offer metadata needed for cancellation
- **Step 11:** Fire only for CCP or BRMS_REMOVE-tagged offers — re-queries catalog for the subset of offers that went through CCBS GOD path

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel / Destination | Protocol | Purpose |
|-----------|-----------------------|----------|---------|
| [OUTBOUND] | OMXFM / CAT_GOD | JMS | Batch offer detail lookup to Product Catalog |
| [LOG] | OMXESB / Logger | JMS | Audit trail (REQ gated by AllowWriteLog; RES also gated by AllowWriteLog) |

> Both request and response audit logs are gated by `AllowWriteLog` in this FM — consistent behaviour. This differs from most other FMs where the response always logs.

### §8.3 — Backend API Details

| System | Operation | Schema | Protocol | Correlation |
|--------|-----------|--------|----------|-------------|
| CAT (Product Catalog) | SearchOfferNameList | `SearchOfferNameList.xsd` (ns1) | JMS/ESB | No subscriber RefId — single response per activity |

### §8.4 — BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `ParentOU[].Agreement.Offers[].OfferName` | READ + WRITE | Read for batch; enriched with Soc, ServiceType, SocProperties, SwitchFeature[], RelatedOffersArray |
| `ParentOU[].Subscriber[].SubscriberOffers[].OfferName` | READ + WRITE | Same enrichment pattern |
| `ParentOU[].Subscriber[].SubscriberOffers[].RelatedOffersArray[].OfferName` | READ + WRITE | Also included in batch; enriched with Soc, ServiceType, SocProperties |
| `Concepts.OM.LogicalDate.LogicalDate` | READ | Used as TR_ACTUAL_CONTRACT_START_DATE; falls back to current-dateTime() |
| `currActivity.Response[]` | WRITE | Each parsed `CatGodResponse` concept appended |

### §8.5 — ExtendedInfo Fields

| Key | Where checked | Purpose |
|-----|---------------|---------|
| `OFFER_INCLUSION` | Response RF XSLT — `$orderRequest/OrderData/ExtendedInfo[Name='OFFER_INCLUSION']/Value='Y'` | If missing or "Y": include RelatedOffers in CatGodResponse; if present and != "Y": exclude |
| `FE_OR_CCBS` | Response RF — offer.ExtendedInfo | If IGNORE_CCP="Y": skips SwitchFeature population for offers where FE_OR_CCBS="CCP" |

### §8.6 — Global Variable Dependencies

| Global Variable Path | Used for |
|----------------------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | If "true": includes UserName/PassWord in event header |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `OMX_OM/WritePayload` | Gates payload in audit log |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | BE Source | Notes |
|------------|-----------|-------|
| `$orderRequest` | `orderRequest` | Full order concept |
| `$globalVariables` | BE global variables | Used for IsEnableUserPass, WritePayload |
| `$socIDs` | `socIDs` (Object[] from ArrayList) | Serialised as XML with `<elements>` nodes; iterated as `$socIDs/elements` |

### §9.2 — Event Container

Event extId: not generated via OMXUtils (no `extId` attribute on event in XSLT).

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Only if OrderPriority present |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Only if OMXTrackingId present |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Only if OrderID present |
| `UserName` | `$orderRequest/OrderData/User` | Only if IsEnableUserPass="true" and User present |
| `PassWord` | `$orderRequest/OrderData/Password` | Only if IsEnableUserPass="true" and Password present |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Only if OrderType present |
| `CES` | `$orderRequest/OrderData/CES` | Only if CES present |

### §9.4 — Payload Root

Namespace: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ProductCatalog/SearchOfferNameList.xsd` (prefix: `ns1`)  
Root element: `<ns1:SearchOfferNameListReq>`

### §9.5 — Core Payload Fields

| Element | Source | Cardinality |
|---------|--------|-------------|
| `ns1:name` | `$socIDs/elements` (each unique offer name) | Repeated — one per offer in arrLstSOCs |
| `ns1:pagination/ns1:page` | Static: `1` | Always page 1 |
| `ns1:pagination/ns1:perPage` | Static: `100` | Hard-coded — max 100 offers per request |
| `ns1:pagination/ns1:trackingId` | `$orderRequest/OrderData/OMXTrackingId` | Always |

> **[MEDIUM]** perPage is hard-coded to 100. Orders with more than 100 unique offer names will silently receive incomplete catalog data — the excess offers will not be enriched. No pagination loop exists. Consider making perPage configurable and adding a page-iteration loop in modernisation.

### §9.6 — Complete Generated XML Example

```xml
<event>
  <JMSPriority>4</JMSPriority>
  <JMSCorrelationID>OMX-TRK-20250720-001</JMSCorrelationID>
  <OrderID>1000001</OrderID>
  <OrderType>35041</OrderType>
  <!-- UserName/PassWord omitted: IsEnableUserPass != "true" -->
  <payload>
    <ns1:SearchOfferNameListReq>
      <ns1:name>PREPAID_SOC_001</ns1:name>
      <ns1:name>PREPAID_SOC_002</ns1:name>
      <ns1:pagination>
        <ns1:page>1</ns1:page>
        <ns1:perPage>100</ns1:perPage>
        <ns1:trackingId>OMX-TRK-20250720-001</ns1:trackingId>
      </ns1:pagination>
    </ns1:SearchOfferNameListReq>
  </payload>
</event>
```

### §9.7 — XSLT Stylesheet Source (Request)

```xml
<xsl:stylesheet version="1.0"
  xmlns:ns1="http://www.tibco.com/schemas/.../SearchOfferNameList.xsd">
  <xsl:param name="orderRequest"/>    <!-- bound from BE: full order concept -->
  <xsl:param name="globalVariables"/> <!-- bound from BE: global vars -->
  <xsl:param name="socIDs"/>          <!-- bound from BE: Object[] ArrayList serialised as XML with <elements> children -->
  <xsl:template match="/">
    <createEvent><event>
      <xsl:if test="$orderRequest/OrderPriority"><JMSPriority>...</JMSPriority></xsl:if>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId"><JMSCorrelationID>...</JMSCorrelationID></xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderID"><OrderID>...</OrderID></xsl:if>
      <xsl:if test="$globalVariables/OMX_OM/.../IsEnableUserPass='true'">
        <UserName>...</UserName><PassWord>...</PassWord>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderType"><OrderType>...</OrderType></xsl:if>
      <xsl:if test="$orderRequest/OrderData/CES"><CES>...</CES></xsl:if>
      <payload>
        <ns1:SearchOfferNameListReq>
          <xsl:for-each select="$socIDs/elements">  <!-- each unique offer name -->
            <ns1:name><xsl:value-of select="."/></ns1:name>
          </xsl:for-each>
          <ns1:pagination>
            <ns1:page>1</ns1:page>
            <ns1:perPage>100</ns1:perPage>  <!-- hard-coded: [MEDIUM BUG] no pagination loop -->
            <ns1:trackingId>...</ns1:trackingId>
          </ns1:pagination>
        </ns1:SearchOfferNameListReq>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event  (no extId attribute — unlike other OMXFM events)
    ├── JMSPriority        ← $orderRequest/OrderPriority                    [Conditional]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId          [Conditional]
    ├── OrderID            ← $orderRequest/OrderData/OrderID                 [Conditional]
    ├── UserName           ← $orderRequest/OrderData/User                    [Credential-gated: IsEnableUserPass="true" and User present]
    ├── PassWord           ← $orderRequest/OrderData/Password                [Credential-gated: IsEnableUserPass="true" and Password present]
    ├── OrderType          ← $orderRequest/OrderData/OrderType               [Conditional]
    ├── CES                ← $orderRequest/OrderData/CES                     [Conditional]
    └── payload                                                              [Always]
        └── ns1:SearchOfferNameListReq
            ├── ns1:name ×N  ← $socIDs/elements (each unique offer name)    [Always] (max 100)
            └── ns1:pagination
                ├── ns1:page      ← static: 1                               [Always]
                ├── ns1:perPage   ← static: 100                             [Always] [MEDIUM] hard-coded
                └── ns1:trackingId ← $orderRequest/OrderData/OMXTrackingId  [Always]
```

**Legend:** `[Always]` = unconditionally emitted; `[Conditional]` = inside xsl:if; `[Credential-gated]` = behind IsEnableUserPass global var

---

## §11 — Audit Logging

| Phase | Gate | PROCESS_ID | AUDIT_TRACE | Payload in log |
|-------|------|------------|-------------|----------------|
| Request | `AllowWriteLog(OrderType)` | `concat(pid, "_REQ")` | "Request Sent for CAT_GOD" | `$reqEvent/payload/ns2:SearchOfferNameListReq` (not the full event) |
| Response | `AllowWriteLog(OrderType)` | `concat(pid, "_RES")` | "Response received for CAT_GOD" | copy-of `$eventResponse` |

> Both request and response logs are gated by AllowWriteLog — consistent behaviour, unlike most other FMs where the response always logs unconditionally.

---

## §12 — Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one offer exists, event sent | "1" → PROCESSING | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| No offers qualified (arrLstSOCs empty) | "4" → SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception thrown | ERROR | `HandleActivityException(...)` |

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
  RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

The response RF additionally throws: `Exception.newException("DATA_ISSUE", "No offer detail returned.", null)` if the CRM response contains no `<data>` elements at all.

---

## §14 — Helper Functions Reference

| Function | Purpose | Notes |
|----------|---------|-------|
| `GetXMLForAgreementOffer` | Serialises an agreement offer to XML for per-offer PreExecCheck evaluation | Agreement-scoped |
| `GetXMLForSubscriberOffer` | Serialises a subscriber offer for per-offer PreExecCheck | ParentOU subscriber |
| `GetXMLForAgreementOfferInChildOU` | ChildOU agreement offer serialiser | Includes parent OU RefId |
| `GetXMLForSubscriberOfferInChildOU` | ChildOU subscriber offer serialiser | Includes parent OU RefId |
| `Collections.List.createArrayList` | Creates the offer name accumulator list | BE Java ArrayList |
| `Collections.contains / Collections.add` | Deduplication of offer names | O(n) per offer |
| `Collections.toArray / Collections.size` | Converts ArrayList to array for XSLT binding | |
| `AllowWriteLog` | Gates both request and response audit logging | Both sides gated |
| `GetActivityParamValueFromKey` | Reads IGNORE_CCP, SERVICE_TYPE (response RF) | Short name |
| `GetActivityParameterValueFromKey` | Reads GET_SWITCH_FEATURE (response RF) | Long name with "eter" |
| `BRMS.IsBlank / BRMS.IsBlankOrStringNull` | Null/blank guards on Soc, ServiceType, etc. | Response RF |
| `OMXUtils.textToAscii` | Converts OfferType and SaleContext to ASCII encoding | Response RF XSLT |

---

## §15 — Function Dependency Tree

```text
Request_CAT_GOD (rule)
├── RuleFunctions.Helpers.GetXMLForAgreementOffer [per agreement offer PreExecCheck]
├── RuleFunctions.Helpers.GetXMLForSubscriberOffer [per subscriber offer PreExecCheck]
├── RuleFunctions.Helpers.GetXMLForAgreementOfferInChildOU [ChildOU Agreement]
├── RuleFunctions.Helpers.GetXMLForSubscriberOfferInChildOU [ChildOU Subscriber]
├── Collections.List.createArrayList / Collections.add / Collections.contains / Collections.toArray
├── Event.Ext.sendEventImmediate [CAT_GOD batch event]
├── RuleFunctions.Helpers.AllowWriteLog
│   └── Event.Ext.sendEventImmediate [OMXESB Logger REQ]
├── RuleFunctions.Helpers.GetActivityStatusString("1")
├── RuleFunctions.Helpers.SendDataToDB
└── RuleFunctions.Helpers.HandleActivityException (on error)

Response_CAT_GOD (rulefunction)
├── Log.getLogger / Log.log [debug logging]
├── XPath.evalAsBoolean [DATA_ISSUE guard: no data in response]
├── RuleFunctions.Helpers.GetActivityParamValueFromKey [IGNORE_CCP, SERVICE_TYPE]
├── RuleFunctions.Helpers.GetActivityParameterValueFromKey [GET_SWITCH_FEATURE]
├── Instance.getByExtIdByUri [Concepts.OM.LogicalDate — LogicalDate]
├── XPath.evalAsString [current-dateTime() fallback for logicalDate]
├── XPath.evalAsInt [count(data) → totalResponse]
├── Instance.createInstance [Concepts.FM.Response.CAT_GOD.CatGodResponse] ×N
│   └── XSLT: 2-branch (result=true/false); maps code,name,description,OfferType,SocProperties,SwitchFeature[],RelatedOffers[],ParameterInfo[]
├── XPath.evalAsBoolean [hasGodResult per item]
├── [For each godRes] Match against ParentOU/ChildOU Agreement/Subscriber offers/relatedOffers:
│   ├── Update Soc, ServiceType, SocProperties, OfferName (if blank)
│   ├── Instance.createInstance [AgreementSwitchFeature / SubscriberSwitchFeature / RelatedOffresSwitchFeature] ×M
│   ├── Instance.createInstance [RelatedOffersArray] ×P
│   └── Instance.createInstance [SubscriberParameterInfo] ×Q (if ParameterInfo present)
├── RuleFunctions.Helpers.AllowWriteLog
│   └── Event.Ext.sendEventImmediate [OMXESB Logger RES]
└── return "true"  [always — single request, no fan-in count needed]
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Fields |
|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.OrderID, OrderType, OMXTrackingId, OrderPriority, CES, User, Password; Customer.ParentOU[].Agreement.Offers[]; Customer.ParentOU[].Subscriber[].SubscriberOffers[] |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, PreExecCheck, Parameter[] |
| `Concepts.OM.LogicalDate` | LogicalDate — used as TR_ACTUAL_CONTRACT_START_DATE for offers with contract params |
| `Concepts.FM.Response.CAT_GOD.CatGodResponse` | Code, Name, Description, OfferType, ProductType, SaleContext, SaleEffectiveDate, SaleExpirationDate, SocProperties, SwitchFeature[], RelatedOffers[], ParameterInfo[] |
| `Concepts.OrderRequest.OrderElements.AgreementOffers` | OfferName, Soc, ServiceType, SocProperties, SwitchFeature[], RelatedOffersArray |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | OfferName, Soc, ServiceType, SocProperties, SwitchFeature[], RelatedOffersArray, ParameterInfo[] |
| `Concepts.OrderRequest.OrderElements.RelatedOffersArray` | OfferName, Soc, ServiceType, SocProperties, SwitchFeature[], RcIndicator |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Collect all unique offer names from the entire order hierarchy (Agreement + Subscriber + Related offers, across ParentOU and ChildOU) for batch catalog lookup |
| R2 | Evaluate per-offer PreExecCheck to selectively include only qualifying offers |
| R3 | Send a single batch request to Product Catalog with all qualifying offer names |
| R4 | Map response data.result="true" → full offer metadata (Code, OfferType, SocProperties, SwitchFeature[], RelatedOffers[], ParameterInfo[]) |
| R5 | Map response data.result="false/missing" → minimal entry with Name only |
| R6 | Enrich matching Agreement offers: Soc (if blank), ServiceType (if blank), SocProperties, SwitchFeature[], RelatedOffersArray |
| R7 | Enrich matching SubscriberOffers: same as R6 plus ParameterInfo[] |
| R8 | Enrich matching RelatedOffersArray: Soc (if blank), ServiceType (if blank), SocProperties, SwitchFeature[] |
| R9 | SocProperties concatenated from 12 TR_ property fields using semicolon separator |
| R10 | If IGNORE_CCP="Y": skip SwitchFeature population for offers tagged FE_OR_CCBS="CCP" |
| R11 | If GET_SWITCH_FEATURE="N": suppress all SwitchFeature population |
| R12 | If SERVICE_TYPE param set and hasGodResult=false: set offer.ServiceType to param value and skip further enrichment |
| R13 | ParameterInfo: TR_ACTUAL_CONTRACT_START_DATE ← LogicalDate; TR_ORIG_CONTRACT_EXPIRE_DATE computed from TR_ORIG_CONTRACT_EXPIRE_DATE field or logicalDate+TR_CONTRACT_TERM months or "2099-01-01 00:00:00" |
| R14 | OFFER_INCLUSION ExtendedInfo: if absent or "Y", include RelatedOffers in response; otherwise exclude |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| perPage hard-coded to 100 — orders with >100 unique offers silently lose data; no pagination loop | [MEDIUM] | Make configurable via global variable; implement pagination loop in modernised implementation |
| Two different helper function names: GetActivityParamValueFromKey vs GetActivityParameterValueFromKey | [MEDIUM] | Standardise API in modernisation |
| Commented-out old code: GetOfferDetailsRes concept use, old PreExecCheck serialisation, old surrounding if-block | [LOW] | Remove dead code |
| ChildOU AgreementOffers SwitchFeature count uses a different XPath source (eventResponse) vs godRes in ParentOU — inconsistency | [MEDIUM] | Standardise to use godRes.SwitchFeature for all paths |
| O(n²) enrichment loop: for each response item, iterates all Agreement/Subscriber offers to find matches by OfferName | [MEDIUM] | Use indexed map (HashMap<OfferName, List<Offer>>) in modernised implementation |
| socIDs ArrayList serialisation as XML with `<elements>` nodes — relies on internal TIBCO BE Java ArrayList XML representation; non-portable | [MEDIUM] | Convert to JSON array or explicit XML when migrating to modern platform |
| DATA_ISSUE exception thrown if no data items in response — could fail valid empty responses (e.g. all offers are new and not in catalog yet) | [MEDIUM] | Consider treating empty data as warning rather than exception in modernised design |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author awalia-t420
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CAT_GOD {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CAT_GOD";
    orderRequest.ProcessFlow.NextActivityID == "CAT_GOD";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      // [LOW] Commented-out code: nanoTime ProcessID, old instance-level PreExecCheck, old outer if(chkRes) wrapper

      String strSOCs = "";
      Object arrLstSOCs = Collections.List.createArrayList();

      // Collect unique offer names from entire order hierarchy
      for(int i=0; i<iPOULen; i++) {
        // ParentOU Agreement.Offers — evaluate PreExecCheck per offer
        for(int j=0; j<iAgreeOffersLen; j++) {
          String currSoc = orderRequest.OrderData.Customer.ParentOU[i].Agreement.Offers[j].OfferName;
          // GetXMLForAgreementOffer + XPath.execute(PreExecCheck) → chkRes
          if(!Collections.contains(arrLstSOCs, currSoc) && String.equals(chkRes, "true"))
            Collections.add(arrLstSOCs, currSoc);
        }
        // ParentOU Subscriber.SubscriberOffers
        for(int j=0; j<iSubCnt; j++) {
          for(int k=0; k<iSubOffCnt; k++) {
            String currSoc = /* SubscriberOffers[k].OfferName */"";
            // GetXMLForSubscriberOffer + XPath.execute(PreExecCheck) → chkRes
            if(!Collections.contains(arrLstSOCs, currSoc) && String.equals(chkRes, "true")) {
              Collections.add(arrLstSOCs, currSoc);
              // Add RelatedOffersArray offer names (dedup, no PreExecCheck)
              for(int l=0; l<iSubOffCntRelated; l++) {
                if(!Collections.contains(arrLstSOCs, relatedCurrSoc))
                  Collections.add(arrLstSOCs, relatedCurrSoc);
              }
            }
          }
        }
        // ChildOU Agreement.Offers and ChildOU Subscriber.SubscriberOffers — same pattern
      }

      Object[] socIDs = Collections.toArray(arrLstSOCs);
      if(socIDs != null && Collections.size(arrLstSOCs) > 0) {
        Events.OMConsumers.OMXFM.Request.CAT_GOD reqEvent =
          Event.createEvent("xslt://{{/Events/.../CAT_GOD}}");
          // → See §9.7 for full XSLT (params: orderRequest, globalVariables, socIDs)
          // → Payload: SearchOfferNameListReq(name×N, pagination(page=1,perPage=100,trackingId))
        Event.Ext.sendEventImmediate(reqEvent);
        isSkipped = false;
        if(!isActResub) orderCurrentActivity.RequestCount++;
        if(RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
          Event.Ext.sendEventImmediate(/* Logger REQ event */);
        }
      }

      if(!isSkipped) {
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

`Response_CAT_GOD` parses the Product Catalog response and enriches ALL matching offers in the order with catalog metadata. It processes each `data` item in `SearchOfferNameListResponse`, creates a `CatGodResponse` concept per item, then scans the entire order to find and update every offer whose name matches.

> **Fan-in pattern different:** Unlike other response RFs, this one returns `"true"` unconditionally (line 551). Because CAT_GOD sends only one request (RequestCount=1), there is no fan-in counting needed. The single response is always the final response.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order; entire offer hierarchy to enrich |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CAT_GOD` | Product Catalog reply; contains SearchOfferNameListResponse data[] |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity state; receives CatGodResponse concepts; holds parameters |

### §19.3 — Guard: DATA_ISSUE Exception

```java
if not(exists($eventResponse/payload/SearchOfferNameListResponse/data)) {
  throw Exception.newException("DATA_ISSUE", "No offer detail returned.", null);
}
```

### §19.4 — CatGodResponse Concept Construction

For each `data[i+1]` in the response, `Instance.createInstance(CatGodResponse)` is called. Two branches based on `ns1:result`:

| Field | result="true" | result=false/empty |
|-------|--------------|-------------------|
| extId | concat("GODOF:", OMXTrackingId, ":", activityExtId, ":", code) | concat("GODOF:", OMXTrackingId, ":", activityExtId, ":", name) |
| ResponseCode | ← ../../../ResponseCode | ← ../../../ResponseCode |
| ResponseMessage | ← ../../../ResponseMsg | ← ../../../ResponseMsg |
| CompletionStatus | ← ../../../CompletionStatus | ← ../../../CompletionStatus |
| Code | ← ns1:code | — |
| Name | ← ns1:name | ← ns1:name |
| Description | ← ns1:description | — |
| OfferType | ← OMXUtils.textToAscii(ns1:type) | — |
| ProductType | ← ns1:productType | — |
| SaleContext | ← OMXUtils.textToAscii(ns1:saleContext) | — |
| SaleEffectiveDate | ← ns1:saleEffDate | — |
| SaleExpirationDate | ← ns1:saleExpDate | — |
| SocProperties | Concatenated from 12 TR_ properties (semicolon-separated) | — |
| SwitchFeature[] | ← ns1:offerItem[] (if count>0 AND GET_SWITCH_FEATURE != "N") | — |
| RelatedOffers[] | ← ns1:childOffer[] (if OFFER_INCLUSION absent or "Y"; only childOffer with ns1:name) | — |
| ParameterInfo[] | If offerItem[1]/offerItemParam/TR_ACTUAL_CONTRACT_START_DATE exists: 7 contract params | — |

### §19.5 — SocProperties Concatenation Formula

```text
concat(
  "TR_ACCOUNT_SUB_TYPE=",       properties/TR_ACCOUNT_SUB_TYPE,       ";",
  "TR_CONTRACT_TERM=",          properties/TR_CONTRACT_TERM,          ";",
  "TR_CUSTOMER_TYPE=",          properties/TR_CUSTOMER_TYPE,          ";",
  "TR_DEFAULT_CONTRACT_FEE=",   properties/TR_DEFAULT_CONTRACT_FEE,   ";",
  "TR_GENERATE_CHARGE_YES_NO=", properties/TR_GENERATE_CHARGE_YES_NO, ";",
  "TR_UR_NO=",                  properties/TR_UR_NO,                  ";",
  "TR_SPECIAL_OFFER_IND=",      properties/TR_SPECIAL_OFFER_IND,      ";",
  "TR_OFFER_EXCL_GROUP_NAME=",  properties/TR_OFFER_EXCL_GROUP_NAME,  ";",
  "TR_CONTRACT_IND=",           properties/TR_CONTRACT_IND,           ";",
  "TR_IDD_FLAG=",               properties/TR_IDD_FLAG,               ";",
  "TR_IR_FLAG=",                properties/TR_IR_FLAG,                ";",
  "TR_OFFER_GROUP=",            properties/TR_OFFER_GROUP,            ";"
)
```

### §19.6 — TR_ORIG_CONTRACT_EXPIRE_DATE Computation

| Priority | Condition | Value |
|----------|-----------|-------|
| 1 (preferred) | offerItem[1]/offerItemParam/TR_ORIG_CONTRACT_EXPIRE_DATE has value | Formatted: `tib:format-dateTime("yyyy-MM-dd HH:mm:ss", parsed)` |
| 2 | TR_CONTRACT_TERM has value | `tib:format-dateTime("yyyy-MM-dd HH:mm:ss", logicalDate + TR_CONTRACT_TERM months)` |
| 3 (fallback) | Neither | `"2099-01-01 00:00:00"` |

### §19.7 — Fan-in Completion

| Element | Value |
|---------|-------|
| Fan-in logic | **None** — RF always returns `"true"` |
| Reason | RequestCount = 1 (single batch event); every response is the final response |

### §19.8 — Response Audit Logging

Gated by `AllowWriteLog(OrderType)` (same as request). PROCESS_ID suffix "_RES". OPERATION_NAME = "CAT_GOD".

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
