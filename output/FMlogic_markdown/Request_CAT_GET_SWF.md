# Request_CAT_GET_SWF

FM Logic Documentation — Product Catalog Switch Feature Lookup

---

## §1 — Overview & Purpose

**CAT_GET_SWF** (Get Switch Features) queries the Product Catalog ESB to retrieve switch feature (SWF) metadata for all unique service offering codes (SOCs) present in the order. It builds a deduplicated list of SOC names from every offer — across all ParentOU/ChildOU agreements and subscriber offers — then sends a single `SearchOfferNameListReq` batch request to the CAT backend. The response enriches the order's offer objects (`AgreementOffers`, `SubscriberOffers`, `RelatedOffersArray`) with `SwitchFeature` sub-objects required by downstream provisioning activities.

> **Shared Event Type:** CAT_GET_SWF reuses the `Events.OMConsumers.OMXFM.Request.CAT_GOD` event and the `Concepts.FM.Response.CAT_GOD.CatGodResponse` concept — the same types used by the **CAT_GOD** activity. The rule is distinguished by the `ActivityID == "CAT_GET_SWF"` WHEN condition.

| Attribute | Value |
|-----------|-------|
| Rule file | Request_CAT_GET_SWF.rule |
| Response rulefunction | Response_CAT_GET_SWF.rulefunction |
| Priority | 5 |
| Forward chain | true |
| Backend system | Product Catalog (CAT) via ESB |
| Request event type | `Events.OMConsumers.OMXFM.Request.CAT_GOD` |
| Response concept | `Concepts.FM.Response.CAT_GOD.CatGodResponse` |
| Payload operation | `SearchOfferNameListReq` |
| Schema namespace | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ProductCatalog/SearchOfferNameList.xsd` |
| Activity parameter | `IGNORE_CCP` — if "Y", skips SWF mapping for offers with `FE_OR_CCBS=CCP` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM priority |
| forwardChain | true | Enables forward chaining after execution |
| Rule type | Standard JMS request | Single `Event.Ext.sendEventImmediate` |
| RequestCount increment | Yes (if not resubmit) | `orderCurrentActivity.RequestCount++` |
| Skip mechanism | Yes | Skips if no SOCs found: `SkipActivity(orderRequest, orderCurrentActivity, "4")` |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Main order state — supplies customer/offers data and OrderType |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity instance — matched by ActivityID and Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId matches process flow pointer |
| 2 | `orderCurrentActivity.ActivityID == "CAT_GET_SWF"` | Constrains rule to CAT_GET_SWF activity only |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CAT_GET_SWF"` | Double-check via process flow NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity is ready to be executed |

---

## §5 — Execution Flow Diagram

```
1. Resubmit flag → compute isActResub = (RequestCount > 0 && IsOrderResubmitted)
2. Load activity config → Instance.getByExtIdByUri(NextActivityName) → read PreExecCheck
3. Collect SOCs from ParentOU agreements → apply PreExecCheck if set; deduplicate into arrLstSOCs
4. Collect SOCs from ParentOU subscribers → extract FE_OR_CCBS filter; call GetXMLForSubscriberOfferFilterWithExtendedInfo; apply PreExecCheck; add RelatedOffersArray SOCs
5. Collect SOCs from ChildOU agreements → via GetXMLForAgreementOfferInChildOU; deduplicate
6. Collect SOCs from ChildOU subscribers → via GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo; add RelatedOffersArray SOCs
7. Guard: empty SOC list → if socIDs null or empty → SkipActivity("4") → exit
8. Build & send SearchOfferNameListReq → CAT_GOD event with all SOC names; Event.Ext.sendEventImmediate
9. Audit log request → if AllowWriteLog(OrderType) → Logger event: OPERATION_NAME="CAT_GET_SWF"
10. Increment RequestCount → orderCurrentActivity.RequestCount++ (skipped if resubmit)
11. Status transition → GetActivityStatusString("1", false) + SendDataToDB
```

> **Single-shot batch design:** Unlike per-offer parallel dispatches, CAT_GET_SWF sends ONE request containing all SOC names. RequestCount is always 1 after this rule fires.

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
// 1. Resubmit guard
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);

// 2. Load activity config for PreExecCheck
Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
String chkXPath = nextAct.PreExecCheck;

// 3–6. SOC deduplication across all ParentOU/ChildOU agreements + subscribers
Object arrLstSOCs = Collections.List.createArrayList();
// ... loops described above ...

// 7. Skip guard
Object[] socIDs = Collections.toArray(arrLstSOCs);
if(socIDs != null && Collections.size(arrLstSOCs) > 0) {

    // 8. Build SearchOfferNameListReq with all SOC names + pagination (page=1, perPage=100)
    Events.OMConsumers.OMXFM.Request.CAT_GOD reqEvent = Event.createEvent("xslt://...");
    Event.Ext.sendEventImmediate(reqEvent);

    // 9. Audit log
    if(RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
        // OPERATION_NAME="CAT_GET_SWF", AUDIT_TRACE="Request Sent for CAT_GET_SWF"
        Event.Ext.sendEventImmediate(Event.createEvent("xslt://Logger..."));
    }

    // 10. Increment RequestCount if not resubmit
    if(!isActResub) { orderCurrentActivity.RequestCount++; }
    isSkipped = false;
}

// 11. Status transition or skip
if(!isSkipped) {
    orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
    RuleFunctions.Helpers.SendDataToDB(orderRequest);
} else {
    RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
}
```

---

## §7 — Data Extraction — SOC Collection Logic

| Source path | Helper used | PreExecCheck applied | Notes |
|-------------|-------------|---------------------|-------|
| `ParentOU[i] → Agreement.Offers[j].OfferName` | `GetXMLForAgreementOffer` | Yes (if set) | Standard agreement offer |
| `ParentOU[i] → Subscriber[j] → SubscriberOffers[k].OfferName` | `GetXMLForSubscriberOfferFilterWithExtendedInfo` | Yes (if set) | Filtered by FE_OR_CCBS ExtendedInfo |
| `ParentOU[i] → Subscriber[j] → SubscriberOffers[k] → RelatedOffersArray[l].OfferName` | — | No | Added unconditionally if parent SOC passed |
| `ParentOU[i] → ChildOU[k] → Agreement.Offers[j].OfferName` | `GetXMLForAgreementOfferInChildOU` | Yes (if set) | ChildOU agreement variant |
| `ParentOU[i] → ChildOU[k] → Subscriber[j] → SubscriberOffers[m].OfferName` | `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo` | Yes (if set) | ChildOU subscriber with ExtendedInfo filter |
| `ParentOU[i] → ChildOU[k] → Subscriber[j] → SubscriberOffers[m] → RelatedOffersArray[l].OfferName` | — | Inherits from parent | Added if parent SOC passed check |

> **[BUG — HIGH] ChildOU subscriber RefId mismatch (rule line 122):** The helper call for ChildOU subscriber offers passes `orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].RefId` (the ParentOU subscriber's RefId) instead of `orderRequest.OrderData.Customer.ParentOU[i].ChildOU[k].Subscriber[j].RefId`. This causes incorrect PreExecCheck XML for ChildOU subscribers in orders with nested OU structures.

**Deduplication:** `Collections.contains(arrLstSOCs, currSoc)` ensures each SOC name appears only once in the batch request.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Fires for any order that contains offers (SOC list non-empty). `AllowWriteLog` gates audit per OrderType. The `IGNORE_CCP` activity parameter is configured at the ProcessConfig level per order type to control SWF mapping for CCP-type offers.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Channel | Purpose |
|-----------|-----------|---------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CAT_GOD` | OMXFM Request channel | Send SearchOfferNameListReq to Product Catalog |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Audit log channel | Request audit trace (conditional on AllowWriteLog) |

### §8.3 — Backend API Details

| System | Operation | Protocol | Schema |
|--------|-----------|----------|--------|
| Product Catalog (CAT) | SearchOfferNameList | JMS async | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ProductCatalog/SearchOfferNameList.xsd` |

### §8.4 — BE Working Memory Dependencies

| Concept path | Access | Fields used |
|-------------|--------|-------------|
| `orderRequest.OrderData.Customer.ParentOU[*].Agreement.Offers[*].OfferName` | Read | SOC name for batch |
| `orderRequest.OrderData.Customer.ParentOU[*].Subscriber[*].SubscriberOffers[*].OfferName` | Read | SOC name for batch |
| `orderRequest.OrderData.Customer.ParentOU[*].Subscriber[*].SubscriberOffers[*].RelatedOffersArray[*].OfferName` | Read | Related SOC names |
| `orderRequest.OrderData.Customer.ParentOU[*].ChildOU[*].Agreement.Offers[*].OfferName` | Read | ChildOU SOC names |
| `orderRequest.OrderData.Customer.ParentOU[*].ChildOU[*].Subscriber[*].SubscriberOffers[*].OfferName` | Read | ChildOU subscriber SOC names |
| `orderRequest.OrderData.OMXTrackingId` | Read | Correlation ID (JMSCorrelationID) |
| `orderRequest.OrderData.OrderType` | Read | Audit log gate |
| `orderCurrentActivity.RequestCount` | Read/Write | Fan-in counter |
| `orderCurrentActivity.Status` | Write | Status transition |

### §8.5 — ExtendedInfo Fields Required

| Key | Source concept | Required? | Purpose |
|-----|---------------|-----------|---------|
| `FE_OR_CCBS` | SubscriberOffers.ExtendedInfo | Optional | XPath filter param in `GetXMLForSubscriberOfferFilterWithExtendedInfo`; also used by response RF IGNORE_CCP logic |

### §8.6 — Global Variable Dependencies

| Variable path | Used in |
|--------------|---------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Request XSLT — include UserName/PassWord if "true" |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit log COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit log TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit log LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Conditional payload logging in audit |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT param | Bound from |
|------------|-----------|
| `$orderRequest` | Working memory `orderRequest` concept |
| `$globalVariables` | Global variable store |
| `$socIDs` | `arrLstSOCs` ArrayList converted to array — each element is one SOC name |

### §9.2 — Event Container Construction

Event type: `Events.OMConsumers.OMXFM.Request.CAT_GOD` (shared with CAT_GOD FM)

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | If OrderPriority present |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | If OMXTrackingId present |
| `OrderID` | `$orderRequest/OrderData/OrderID` | If OrderID present |
| `UserName` | `$orderRequest/OrderData/User` | If IsEnableUserPass="true" and User present |
| `PassWord` | `$orderRequest/OrderData/Password` | If IsEnableUserPass="true" and Password present |
| `OrderType` | `$orderRequest/OrderData/OrderType` | If OrderType present |
| `CES` | `$orderRequest/OrderData/CES` | If CES present |

### §9.4 — Payload Root Element

`<ns1:SearchOfferNameListReq>` (namespace: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ProductCatalog/SearchOfferNameList.xsd`)

### §9.5 — Core Payload Fields

| XML element | Source | Notes |
|-------------|--------|-------|
| `ns1:name` (repeated) | Each element in `$socIDs/elements` | One per unique SOC name; `xsl:for-each` |
| `ns1:pagination/ns1:page` | Static: `1` | Always page 1 |
| `ns1:pagination/ns1:perPage` | Static: `100` | Max 100 results; no pagination loop in response |

> **[RISK — MEDIUM] Pagination not handled:** Hard-coded `perPage=100` with no follow-up page requests. Orders with more than 100 unique SOCs will silently lose SWF data for SOCs beyond position 100.

### §9.6 — Complete Generated XML Example

```xml
<ns1:SearchOfferNameListReq
  xmlns:ns1="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ProductCatalog/SearchOfferNameList.xsd">
  <ns1:name>SOC_CODE_01</ns1:name>
  <ns1:name>SOC_CODE_02</ns1:name>
  <ns1:name>SOC_CODE_03</ns1:name>
  <!-- ... one per unique SOC name (max 100) -->
  <ns1:pagination>
    <ns1:page>1</ns1:page>
    <ns1:perPage>100</ns1:perPage>
  </ns1:pagination>
</ns1:SearchOfferNameListReq>
```

### §9.7 — XSLT Stylesheet Source (Request)

```xml
<xsl:stylesheet
  xmlns:ns1="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/ProductCatalog/SearchOfferNameList.xsd"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  version="1.0">
  <!-- params: $orderRequest, $globalVariables, $socIDs -->
  <xsl:template match="/">
    <createEvent><event>
      <!-- JMSPriority: $orderRequest/OrderPriority (if exists) -->
      <!-- JMSCorrelationID: $orderRequest/OrderData/OMXTrackingId -->
      <!-- OrderID, UserName, PassWord, OrderType, CES -->
      <payload>
        <ns1:SearchOfferNameListReq>
          <xsl:for-each select="$socIDs/elements">
            <ns1:name><xsl:value-of select="."/></ns1:name>
          </xsl:for-each>
          <ns1:pagination>
            <ns1:page>1</ns1:page>
            <ns1:perPage>100</ns1:perPage>
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
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                      [Conditional: if OrderPriority]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId             [Conditional: if OMXTrackingId]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID                   [Conditional: if OrderID]
    ├── UserName                 ← $orderRequest/OrderData/User                      [Conditional: IsEnableUserPass="true"]
    ├── PassWord                 ← $orderRequest/OrderData/Password                  [Conditional: IsEnableUserPass="true"]
    ├── OrderType                ← $orderRequest/OrderData/OrderType                 [Conditional: if OrderType]
    ├── CES                      ← $orderRequest/OrderData/CES                       [Conditional: if CES]
    └── payload                                                                       [Always]
        └── ns1:SearchOfferNameListReq                                                [Always]
            ├── ns1:name (×N)    ← $socIDs/elements (xsl:for-each)                  [Always — one per SOC]
            └── ns1:pagination                                                        [Always]
                ├── ns1:page     ← "1" (static)                                      [Always]
                └── ns1:perPage  ← "100" (static)                                    [Always]
```

Legend: `[Always]` = unconditional | `[Conditional: ...]` = inside xsl:if | XPath source = green | static literal = orange

---

## §11 — Audit Logging

| Event | Trigger | Key fields |
|-------|---------|-----------|
| Request audit | `AllowWriteLog(OrderType)` = true | `OPERATION_NAME="CAT_GET_SWF"`, `AUDIT_TRACE="Request Sent for CAT_GET_SWF"`, `PROCESS_ID=concat(pid,"_REQ")` |
| Response audit | `AllowWriteLog(OrderType)` = true | `OPERATION_NAME="CAT_GET_SWF"`, `AUDIT_TRACE="Response received for CAT_GET_SWF"`, `PROCESS_ID=concat(pid,"_RES")` |

> **No trailing space:** Both OPERATION_NAME and AUDIT_TRACE strings are clean (no trailing space), unlike some other FMs in this codebase.

---

## §12 — Activity Status Management

| Condition | Action | Status code |
|-----------|--------|------------|
| SOCs found and event sent | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" = PROCESSING / SENT |
| No SOCs found (empty offer list) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" = SKIPPED |

---

## §13 — Exception / Error Handling

```java
catch(Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

Standard catch-all; delegates to `HandleActivityException` which logs the error and transitions the activity to a failed state.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `RuleFunctions.Helpers.AllowWriteLog(orderType)` | Returns boolean — permits audit logging for the given order type |
| `RuleFunctions.Helpers.GetActivityStatusString(code, flag)` | Translates status code string to activity status string |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | Persists current order state to database |
| `RuleFunctions.Helpers.SkipActivity(orderRequest, activity, code)` | Marks activity as skipped with given code and advances flow |
| `RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Logs exception, transitions activity to error state |
| `RuleFunctions.Helpers.GetXMLForAgreementOffer(orderRequest, refId, soc)` | Builds XML for PreExecCheck against a ParentOU agreement offer |
| `RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, soc, filter)` | Builds XML for PreExecCheck with FE_OR_CCBS ExtendedInfo filter param |
| `RuleFunctions.Helpers.GetXMLForAgreementOfferInChildOU(orderRequest, refId, soc, parentRefId)` | Builds XML for PreExecCheck against ChildOU agreement offer |
| `RuleFunctions.Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, refId, offerName, parentRefId, filter)` | Builds XML for PreExecCheck against ChildOU subscriber offer with filter |
| `RuleFunctions.Helpers.GetActivityParamValueFromKey(activity, key)` | Reads a named parameter from the activity's Parameter array |
| `RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(str)` | Null/blank check for BRMS parameter values |

---

## §15 — Function Dependency Tree

```text
Request_CAT_GET_SWF (rule)
├── Instance.getByExtIdByUri()
├── Collections.List.createArrayList()
├── XPath.execute()                               [PreExecCheck evaluation]
├── Collections.contains()
├── Collections.add()
├── Collections.toArray()
├── Collections.size()
├── Helpers.GetXMLForAgreementOffer()
├── Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo()
├── Helpers.GetXMLForAgreementOfferInChildOU()
├── Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo()
├── XPath.evalAsString()                          [FE_OR_CCBS extraction]
├── Event.createEvent()                           [XSLT-based event build]
├── Event.Ext.sendEventImmediate()
├── Helpers.AllowWriteLog()
├── System.nanoTime()
├── Helpers.GetActivityStatusString()
├── Helpers.SendDataToDB()
├── Helpers.SkipActivity()
└── Helpers.HandleActivityException()

Response_CAT_GET_SWF (rulefunction)
├── Log.getLogger() / Log.log()
├── XPath.evalAsBoolean()                         [guard + IGNORE_CCP checks]
├── XPath.evalAsString()                          [LogicalDate, swCode]
├── XPath.evalAsInt()                             [totalResponse, SWF counts]
├── Helpers.GetActivityParamValueFromKey()        [read IGNORE_CCP]
├── Instance.getByExtIdByUri()                    [LogicalDate concept]
├── Instance.createInstance()                     [CatGodResponse, SwitchFeature, RelatedOffers, etc.]
├── Helpers.AllowWriteLog()
├── Event.createEvent()                           [Logger event]
└── Event.Ext.sendEventImmediate()
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | Request rule, Response RF | OrderData, ProcessFlow, IsOrderResubmitted |
| `Concepts.OM.ProcessConfig.Activity` | Request rule, Response RF | ActivityID, Status, RequestCount, Response[], PreExecCheck, Parameter[] |
| `Concepts.FM.Response.CAT_GOD.CatGodResponse` | Response RF | ResponseCode, ResponseMessage, Name, Code, Description, OfferType, ProductType, SaleContext, SaleEffectiveDate, SaleExpirationDate, SocProperties, SwitchFeature[], RelatedOffers[] |
| `Concepts.OrderRequest.OrderElements.AgreementOffers` | Response RF (write) | OfferName, SwitchFeature[], RelatedOffersArray[] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Response RF (write) | OfferName, SwitchFeature[], RelatedOffersArray[], ExtendedInfo[] |
| `Concepts.OrderRequest.OrderElements.AgreementSwitchFeature` | Response RF (create) | item_cd, swparam, switchcode |
| `Concepts.OrderRequest.OrderElements.SubscriberSwitchFeature` | Response RF (create) | item_cd, swparam, switchcode |
| `Concepts.OrderRequest.OrderElements.RelatedOffresSwitchFeature` | Response RF (create) | item_cd, swparam, switchcode |
| `Concepts.OrderRequest.OrderElements.RelatedOffersArray` | Response RF (read/write) | OfferName, SwitchFeature[] |
| `Concepts.OM.LogicalDate` | Response RF | LogicalDate — effective date for offer mapping |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Collect all unique SOC names from ParentOU and ChildOU agreements and subscriber offers, deduplicated |
| R2 | Apply PreExecCheck XPath filter on each SOC before including in the batch (per-offer evaluation) |
| R3 | Use FE_OR_CCBS ExtendedInfo as an additional filter parameter for subscriber offer PreExecCheck |
| R4 | Send a single batch SearchOfferNameListReq with max 100 SOCs and page=1 |
| R5 | Skip activity if no SOCs found |
| R6 | Enrich all matching AgreementOffers, SubscriberOffers, and RelatedOffersArray with SwitchFeature objects from response |
| R7 | Support IGNORE_CCP activity parameter to bypass SWF mapping for CCP-type offers |
| R8 | Map RelatedOffers children from response, including nested SwitchFeatures |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **BUG: SelectedByDefault ASCII encoding** — `if (ns1:selectedByDefault = 'true') then 89 else 64`. ASCII 64='@' instead of 78='N'. RelatedOffers.SelectedByDefault will contain '@' for non-default offers. | [HIGH] | Fix to `then 89 else 78` or use string literals 'Y'/'N' |
| **BUG: ChildOU subscriber RefId mismatch (rule line 122)** — `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo` passes `ParentOU[i].Subscriber[j].RefId` instead of `ParentOU[i].ChildOU[k].Subscriber[j].RefId`. Wrong PreExecCheck context for ChildOU subscribers. | [HIGH] | Fix to reference ChildOU subscriber RefId |
| **Pagination not handled** — Hard-coded `perPage=100`. Orders with >100 unique SOCs silently lose SWF data. | [MEDIUM] | Add pagination loop or validate max SOC count |
| **Namespace prefix inconsistency in response RF** — Guard uses `xsd4`, totalResponse uses `xsd2` for same schema URI. Not a runtime bug but maintenance confusion. | [LOW] | Standardize to single namespace prefix alias |
| **Shared event type with CAT_GOD** — Same `CAT_GOD` event type; discriminator is only ActivityID condition. Response routing must be verified. | [MEDIUM] | Verify JMS correlation mechanism; consider separate event types in migration |
| **LogicalDate null guard incomplete** — `logicalDateRes.LogicalDate` accessed without null check on the concept instance. | [LOW] | Add null check on `logicalDateRes` before `.LogicalDate` |

---

## §18 — Full Source Code (Request Rule)

```java
/**
 * @description
 * @author LAPTOP-C0A601K3
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CAT_GET_SWF {
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
        orderCurrentActivity.ActivityID == "CAT_GET_SWF";
        orderRequest.ProcessFlow.NextActivityID == "CAT_GET_SWF";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct =
                Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName,
                    "/Concepts/OM/ProcessConfig/Activity");
            String chkXPath = nextAct.PreExecCheck;
            String chkRes = "true";
            boolean isSkipped = true;

            Object arrLstSOCs = Collections.List.createArrayList();
            int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;

            for(int i = 0; i < iPOULen; i++) {
                Concepts.OrderRequest.OrderElements.ParentOU parentOU =
                    orderRequest.OrderData.Customer.ParentOU[i];

                // ParentOU Agreement Offers
                int iAgreeOffersLen = 0;
                if(orderRequest.OrderData.Customer.ParentOU[i].Agreement != null)
                    iAgreeOffersLen = orderRequest.OrderData.Customer.ParentOU[i].Agreement.Offers@length;
                for(int j = 0; j < iAgreeOffersLen; j++) {
                    String currSoc = orderRequest.OrderData.Customer.ParentOU[i].Agreement.Offers[j].OfferName;
                    chkRes = "true";
                    if(String.length(nextAct.PreExecCheck) > 0) {
                        String sXML = RuleFunctions.Helpers.GetXMLForAgreementOffer(
                            orderRequest, orderRequest.OrderData.Customer.ParentOU[i].Agreement.RefId, currSoc);
                        chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=...");
                    }
                    if(!Collections.contains(arrLstSOCs, currSoc) && String.equals(chkRes, "true"))
                        Collections.add(arrLstSOCs, currSoc);
                }

                // ParentOU Subscriber Offers (FE_OR_CCBS filter for PreExecCheck)
                int iSubCnt = orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length;
                for(int j = 0; j < iSubCnt; j++) {
                    int iSubOffCnt = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].SubscriberOffers@length;
                    for(int k = 0; k < iSubOffCnt; k++) {
                        String currSoc = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].SubscriberOffers[k].OfferName;
                        Concepts.OrderRequest.OrderElements.SubscriberOffers subOff =
                            orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].SubscriberOffers[k];
                        String filter = XPath.evalAsString("xpath:// ... FE_OR_CCBS/Value ...");
                        chkRes = "true";
                        if(String.length(nextAct.PreExecCheck) > 0) {
                            String sXML = RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(
                                orderRequest, ..., currSoc, filter);
                            chkRes = XPath.execute(...);
                        }
                        if(!Collections.contains(arrLstSOCs, currSoc) && String.equals(chkRes, "true"))
                            Collections.add(arrLstSOCs, currSoc);
                        // Add RelatedOffersArray SOCs unconditionally if parent passed
                        // ...
                    }
                }

                // ChildOU loop (same pattern)
                // BUG at line 122: ChildOU subscriber uses ParentOU[i].Subscriber[j].RefId
                // instead of ChildOU[k].Subscriber[j].RefId for PreExecCheck XML
                for(int k = 0; k < orderRequest.OrderData.Customer.ParentOU[i].ChildOU@length; k++) {
                    // ... ChildOU Agreement Offers + Subscriber Offers ...
                }
            }

            Object[] socIDs = Collections.toArray(arrLstSOCs);
            if(socIDs != null && Collections.size(arrLstSOCs) > 0) {
                // [XSLT builds SearchOfferNameListReq — see §9.7]
                Events.OMConsumers.OMXFM.Request.CAT_GOD reqEvent = Event.createEvent("xslt://...");
                Event.Ext.sendEventImmediate(reqEvent);

                if(RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                    // [Logger XSLT: OPERATION_NAME="CAT_GET_SWF", AUDIT_TRACE="Request Sent for CAT_GET_SWF"]
                    Event.Ext.sendEventImmediate(Event.createEvent("xslt://..."));
                }
                if(!isActResub) { orderCurrentActivity.RequestCount++; }
                isSkipped = false;
            }

            if(!isSkipped) {
                orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        }
        catch(Exception ae) {
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 — Response Message Rule (Response_CAT_GET_SWF)

### §19.1 — Overview

Processes the `SearchOfferNameListResponse` from the Product Catalog. For each `data` item where `result='true'`, creates a `CatGodResponse` concept and maps switch features back to all matching offers in the order (Agreement, Subscriber, and Related offers across all ParentOU/ChildOU levels). Returns `"true"` (fan-in complete) since RequestCount is always 1 for this FM.

> **[BUG — HIGH] SelectedByDefault ASCII error:** `if (ns1:selectedByDefault = 'true') then 89 else 64` — ASCII 64 is '@' instead of the expected 'N' (ASCII 78). All non-default related offers will have SelectedByDefault='@'.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order state; target for SWF enrichment |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CAT_GOD` | Response event from Product Catalog containing SearchOfferNameListResponse |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity; accumulates Response[] instances |

### §19.3 — CatGodResponse Concept Construction

```text
createObject
└── object
    ├── @extId               ← concat("GETSWF:", OMXTrackingId, ":", activityExtId_suffix, ":", ns1:code)  [Always]
    ├── ResponseCode         ← ../../../ResponseCode                                [Conditional]
    ├── ResponseMessage      ← ../../../ResponseMsg                                 [Conditional]
    ├── CompletionStatus     ← ../../../CompletionStatus                            [Conditional]
    ├── Code                 ← ns1:code                                             [Conditional]
    ├── Description          ← ns1:description                                      [Conditional]
    ├── Name                 ← ns1:name                                             [Conditional]
    ├── OfferType            ← OMXUtils:textToAscii(ns1:type)                      [Conditional: string-length(ns1:type)>0]
    ├── ProductType          ← ns1:productType                                      [Conditional]
    ├── SaleContext          ← OMXUtils:textToAscii(ns1:saleContext)               [Conditional: string-length(ns1:saleContext)>0]
    ├── SaleEffectiveDate    ← ns1:saleEffDate                                      [Conditional]
    ├── SaleExpirationDate   ← ns1:saleExpDate                                      [Conditional]
    ├── SocProperties        ← concat("TR_ACCOUNT_SUB_TYPE=", ..., "TR_IR_FLAG=",..)[Always]
    ├── SwitchFeature (×M)                                                           [Conditional: count(ns1:offerItem)>0]
    │   ├── item_cd          ← ns1:code
    │   ├── swparam          ← ns1:offerItemProperties/ns1:Default_sw_params
    │   └── switchcode       ← ns1:offerItemProperties/ns1:Switch_code
    └── RelatedOffers (×K)                                                           [Conditional: count(ns1:childOffer[name non-empty])>0]
        ├── Code, Description, Name, OfferType, ProductType, RelationType, SaleContext,
        │   SaleEffectiveDate, SaleExpirationDate ← ns1:childOffer/ns1:*
        ├── SelectedByDefault ← 89('Y') if selectedByDefault='true'; else 64('@')   [BUG: should be 78='N']
        ├── SocProperties    ← same TR_* concat pattern as parent                   [Always]
        └── SwitchFeatures (×P)                                                      [Conditional]
            ├── item_cd, swparam, switchcode ← ns1:offerItem/ns1:*
```

### §19.4 — Response Completion Logic

| Attribute | Value |
|-----------|-------|
| Guard (throws) | `not(exists($eventResponse/payload/xsd4:SearchOfferNameListResponse/xsd4:data))` → throws `DATA_ISSUE: No offer detail returned.` |
| Success XPath | None explicit — single request; first valid response is final |
| Fan-in condition | Implicit: RequestCount=1, returns `"true"` unconditionally (no exception) |
| Return value | `"true"` — signals activity completion to orchestrator |

The response RF does not perform the standard `count(Response[...="000"]) == RequestCount` fan-in check because CAT_GET_SWF sends exactly one batch request.

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| `OPERATION_NAME` | `"CAT_GET_SWF"` (no trailing space) |
| `AUDIT_TRACE` | `"Response received for CAT_GET_SWF"` (no trailing space) |
| `PROCESS_ID` | `concat(pid, "_RES")` |
| `payload` | Full `$eventResponse` copy, gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
