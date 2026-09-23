# Request_OMX_CREATE_SUB_OFFER_BAR_SOC

> TIBCO BusinessEvents Internal OMX Rule — Create FE SubscriberOffer Copies for BAR SOCs

**Priority:** 5 | **ForwardChain:** true | **Type:** Internal (OMXOM) | **Backend:** None (WM enrichment only) | **Fan-out:** POU + COU subscribers | **Dispatch:** NextActivity (no response wait)

---

## §1 — Overview & Purpose

> **Internal OMX Rule (OMXOM)** — This rule makes no outbound backend call. It is a pure working-memory enrichment step that creates **FE (FutureEffective) copies** of BAR SOC offers for each subscriber, then immediately advances the process via `NextActivity`. There is no response rulefunction because no asynchronous backend response is needed.

The rule determines which SOC codes are designated as "BAR SOCs" for each subscriber (via `GetBarSocs`) and — for each such SOC found in the subscriber's `SubscriberOffers` — checks whether a FutureEffective (`FE_OR_CCBS="FE"`) copy already exists. If not, it clones the offer with a new extId and remaps `FE_OR_CCBS`: CCBS → FE (all other values preserved), then appends the new FE offer to the subscriber's `SubscriberOffers` array.

This pattern prepares working memory so that downstream FMs (e.g., CCBS_CHANGE_PACKAGE_SUBSCRIBER) have both the current CCBS offer and its planned FE counterpart available without needing an additional enquiry call.

The rule operates on **POU subscribers** (ParentOU) and **COU subscribers** (ChildOU) with identical logic in separate loops.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXOM.OMX_CREATE_SUB_OFFER_BAR_SOC` |
| Rule location | OMXOM (internal) — NOT under OMXFM (backend dispatch) |
| Author | RS33-BANDIT |
| Priority | 5 |
| ForwardChain | true |
| Rule type | Internal working-memory enrichment |
| Backend | None — no outbound call |
| Completion | `RuleFunctions.Helpers.NextActivity` (immediate; no response wait) |
| Fan-out | Per POU subscriber + per COU subscriber (nested loops) |
| Response rulefunction | None — rule is synchronous |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order concept; source and target for FE offer writes |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step; provides PreExecCheck, Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to current order's next step |
| 2 | `orderCurrentActivity.ActivityID == "OMX_CREATE_SUB_OFFER_BAR_SOC"` | Rule fires only for this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_CREATE_SUB_OFFER_BAR_SOC"` | Double-check on ProcessFlow routing |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be waiting before executing |

---

## §5 — Execution Flow Diagram

```
1.  Determine isOrderPrepaid — XPath against globalVariables/OMX_OM/OrderTypes/PrepaidOrderTypes
2.  Iterate over all POU subscribers (ParentOU[i].Subscriber[j])
3.  For each subscriber → call GetBarSocs(sub, isOrderPrepaid) → list of BAR SOC codes
4.  If barSocs null/empty → skip this subscriber (continue)
5.  For each barSoc[k] → scan subscriber SubscriberOffers[l] for Soc match
6.  On match → read FE_OR_CCBS ExtendedInfo → use as filter variable
7.  If PreExecCheck present → build XML via GetXMLForSubscriberOfferFilterWithExtendedInfo → evaluate XPath
8.  If chkRes=="true" → check if FE copy already exists (SubscriberOffers[Soc=offer.Soc and FE_OR_CCBS="FE"])
9.  If FE copy does NOT exist → clone offer via XSLT with FE_OR_CCBS remapped CCBS→FE; append
10. Mark isSkipped = false
11. Repeat steps 2–10 for COU subscribers (ChildOU[c].Subscriber[j]) using COU variant helper
12. If any FE offer created → call NextActivity; send audit log (Event.sendEvent)
13. If nothing created → call SkipActivity("4")
14. On exception → call HandleActivityException
```

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### Prepaid order detection
`isOrderPrepaid` is determined by checking if OrderType is in the comma-delimited list at `$globalVariables/OMX_OM/OrderTypes/PrepaidOrderTypes`. This flag is passed to `GetBarSocs` so it returns the correct BAR SOC set for prepaid vs. postpaid.

### GetBarSocs helper
`RuleFunctions.BusinessValidation.Suspension.GetBarSocs(sub, isOrderPrepaid)` returns an `Object[]` of SOC code strings designated as BAR SOCs. If null or empty, the subscriber is skipped.

### Per-offer PreExecCheck (offer-level gate)
> **Important:** Unlike most FMs where PreExecCheck is evaluated once at activity level, this rule evaluates PreExecCheck **per BAR SOC offer**. The XML builder is called with subscriber RefId, offer Soc, and FE_OR_CCBS filter — giving the XPath a filtered view of order data for each offer individually.

### FE duplicate guard
Before cloning, the rule checks:
```xpath
exists($sub/SubscriberOffers[Soc=$offer/Soc and ExtendedInfo[Name="FE_OR_CCBS" and Value="FE"]]/Soc)
```
If an FE copy already exists, no duplicate is created.

### FE_OR_CCBS remapping
All ExtendedInfo entries are copied with one transformation:
```xpath
if (current()/Name="FE_OR_CCBS" and current()/Value="CCBS") then "FE" else current()/Value
```
Only `CCBS` is remapped to `FE`. Values like `ATS`, `ATS_REMOVE`, `FE` are left unchanged.

### ServiceType default
If no ServiceType exists in the source offer, the clone defaults to `85`.

### Completion
On success: `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` — immediately advances the process (no DB persist step, no status="1" + SendDataToDB pattern). Audit log sent with `Event.sendEvent` (async).

### Skip and status

| Scenario | Action |
|----------|--------|
| No BAR SOCs found, OR all FE copies already exist, OR PreExecCheck=false | SkipActivity("4") |
| At least one FE offer created | NextActivity (advance immediately) |
| Exception | HandleActivityException |

---

## §7 — Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| isOrderPrepaid | `contains($globalVariables/.../PrepaidOrderTypes, concat(',', OrderType, ','))` | Passed to GetBarSocs |
| barSocs[] | `RuleFunctions.BusinessValidation.Suspension.GetBarSocs(sub, isOrderPrepaid)` | Array of SOC code strings |
| FE_OR_CCBS filter | `$offer/ExtendedInfo[Name="FE_OR_CCBS"]/Value` | PreExecCheck filter parameter |
| FE existence check | `exists($sub/SubscriberOffers[Soc=offer.Soc and FE_OR_CCBS="FE"])` | Duplicate guard |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies
`isOrderPrepaid` is the only order-type-specific branching — it affects which SOC codes `GetBarSocs` returns.

### §8.2 — ESB / JMS Dependencies

| Direction | Event Type | Dispatch | Purpose |
|-----------|-----------|---------|---------|
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `Event.sendEvent` (async) | Completion audit log (payload always empty) |

### §8.3 — Backend API Details
*None — pure in-memory enrichment rule with no outbound backend API call.*

### §8.4 — BE Working Memory Dependencies

| Concept Field | Access | Purpose |
|--------------|--------|---------|
| `orderRequest.OrderData.Customer.ParentOU[*]` | READ | Iterate POU subscribers |
| `orderRequest.OrderData.Customer.ParentOU[*].ChildOU[*]` | READ | Iterate COU subscribers |
| `Subscriber.SubscriberOffers[*]` | READ/WRITE | Source offers (READ); FE clones appended (WRITE) |
| `Subscriber.RefId` | READ | Passed to PreExecCheck XML builder |
| `SubscriberOffers.Soc` | READ | Matched against barSocs[] list |
| `SubscriberOffers.ExtendedInfo[Name='FE_OR_CCBS']/Value` | READ | Filter and FE duplicate check |
| `SubscriberOffers.*` (all fields) | READ | Copied into FE offer clone |
| `orderCurrentActivity.PreExecCheck` | READ | Per-offer gate XPath expression |

### §8.5 — ExtendedInfo Fields Required

| Name | Required/Optional | Where Used |
|------|------------------|-----------|
| FE_OR_CCBS | Optional (offer-level) | PreExecCheck filter; FE duplicate guard; remapped CCBS→FE in clone |

### §8.6 — Global Variable Dependencies

| Path | Usage |
|------|-------|
| `$globalVariables/OMX_OM/OrderTypes/PrepaidOrderTypes` | Prepaid order type detection |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |

---

## §9 — Detailed Payload Build (FE Offer Clone)

No outbound request payload. The "payload" is the **FE SubscriberOffers clone** created in working memory.

### §9.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Purpose |
|-----------|-----------|---------|
| `$offer` | Matching SubscriberOffers concept (BAR SOC CCBS offer) | Source for all cloned fields |

### §9.2 — Clone Construction
Target type: `Concepts.OrderRequest.OrderElements.SubscriberOffers` — new instance with generated extId.

### §9.3 — Copied Fields (Direct)

| Field | Source | Condition |
|-------|--------|-----------|
| EffectiveDate | `$offer/EffectiveDate` | If present |
| ExpirationDate | `$offer/ExpirationDate` | If present |
| OfferName | `$offer/OfferName` | If present |
| ServiceType | `$offer/ServiceType` | If exists; defaults to 85 |
| Soc | `$offer/Soc` | If present |
| OfferInstanceId | `$offer/OfferInstanceId` | If present |

### §9.4 — Deep-Copied Arrays

| Array | Fields Copied |
|-------|--------------|
| RelatedOffersArray[] | OfferName, ServiceType, Soc, ParameterInfo[], SwitchFeature[], RcIndicator |
| ParameterInfo[] | ParamName, ValuesArray, EffectiveDate, ExpirationDate |
| SwitchFeature[] | item_cd, swparam, switchcode |

### §9.5 — ExtendedInfo Remapping
```xpath
if (current()/Name="FE_OR_CCBS" and current()/Value="CCBS") then "FE" else current()/Value
```
Only `CCBS` → `FE`. All other values (ATS, ATS_REMOVE, FE) copied unchanged.

### §9.6 — Working Memory Write Example

```text
Source offer (CCBS):
  SubscriberOffers { Soc:"SOC_BAR_VOICE", ServiceType:85, FE_OR_CCBS:"CCBS" }

Cloned FE offer appended to subscriber:
  SubscriberOffers { Soc:"SOC_BAR_VOICE", ServiceType:85, FE_OR_CCBS:"FE" }  ← CCBS→FE remapped
```

### §9.7 — FE Offer XSLT Source

```xml
<!-- FE offer clone XSLT — same template for POU and COU -->
<xsl:stylesheet xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema" version="1.0">
  <xsl:output method="xml"/>
  <xsl:param name="offer"/>  <!-- the BAR SOC source offer concept -->
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
        <xsl:if test="$offer/EffectiveDate">
          <EffectiveDate><xsl:value-of select="$offer/EffectiveDate"/></EffectiveDate>
        </xsl:if>
        <xsl:if test="$offer/ExpirationDate">
          <ExpirationDate><xsl:value-of select="$offer/ExpirationDate"/></ExpirationDate>
        </xsl:if>
        <xsl:if test="$offer/OfferName">
          <OfferName><xsl:value-of select="$offer/OfferName"/></OfferName>
        </xsl:if>
        <xsl:choose>
          <xsl:when test="exists($offer/ServiceType)">
            <xsl:if test="$offer/ServiceType">
              <ServiceType><xsl:value-of select="$offer/ServiceType"/></ServiceType>
            </xsl:if>
          </xsl:when>
          <xsl:otherwise>
            <ServiceType>85</ServiceType>  <!-- default -->
          </xsl:otherwise>
        </xsl:choose>
        <xsl:if test="$offer/Soc">
          <Soc><xsl:value-of select="$offer/Soc"/></Soc>
        </xsl:if>
        <!-- RelatedOffersArray: full deep copy (OfferName, ServiceType, Soc, ParameterInfo, SwitchFeature, RcIndicator) -->
        <xsl:for-each select="$offer/RelatedOffersArray">
          <RelatedOffersArray>...</RelatedOffersArray>
        </xsl:for-each>
        <xsl:if test="$offer/OfferInstanceId">
          <OfferInstanceId><xsl:value-of select="$offer/OfferInstanceId"/></OfferInstanceId>
        </xsl:if>
        <!-- ParameterInfo: full deep copy -->
        <xsl:for-each select="$offer/ParameterInfo">
          <ParameterInfo>...</ParameterInfo>
        </xsl:for-each>
        <!-- ExtendedInfo: copy with FE_OR_CCBS CCBS→FE remap -->
        <xsl:for-each select="$offer/ExtendedInfo">
          <ExtendedInfo>
            <Name><xsl:value-of select="Name"/></Name>
            <Value>
              <xsl:value-of select="if (current()/Name='FE_OR_CCBS' and current()/Value='CCBS') then 'FE' else current()/Value"/>
            </Value>
          </ExtendedInfo>
        </xsl:for-each>
        <!-- SwitchFeature: full deep copy -->
        <xsl:for-each select="$offer/SwitchFeature">
          <SwitchFeature>...</SwitchFeature>
        </xsl:for-each>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — Working Memory Write — FE Offer Object Hierarchy

```text
createObject
└── object @extId ← OMXUtils:generateTrackingID()   [Always]
    ├── EffectiveDate        ← $offer/EffectiveDate          [Conditional: if present]
    ├── ExpirationDate       ← $offer/ExpirationDate         [Conditional: if present]
    ├── OfferName            ← $offer/OfferName              [Conditional: if present]
    ├── ServiceType          ← $offer/ServiceType            [Always; default 85 if absent]
    ├── Soc                  ← $offer/Soc                    [Conditional: if present]
    ├── RelatedOffersArray[] ← deep copy                     [Conditional: if present]
    │   └── OfferName / ServiceType / Soc / ParameterInfo[] / SwitchFeature[] / RcIndicator
    ├── OfferInstanceId      ← $offer/OfferInstanceId        [Conditional: if present]
    ├── ParameterInfo[]      ← deep copy                     [Conditional: if present]
    │   └── ParamName / ValuesArray / EffectiveDate / ExpirationDate
    ├── ExtendedInfo[]       ← copy with remap               [Conditional: if present]
    │   ├── Name             ← Name (as-is)                  [Always]
    │   └── Value            ← "FE" if FE_OR_CCBS=CCBS, else current()/Value   [Always]
    └── SwitchFeature[]      ← deep copy                     [Conditional: if present]
        └── item_cd / swparam / switchcode
```

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| PROCESS_ID | `concat($pid, "_RES")` — nanoTime |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | "OMX_CREATE_SUB_OFFER_BAR_SOC" |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | "OMX_CREATE_SUB_OFFER_BAR_SOC completed." |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | Always empty (`<payload/>`) |

Dispatch: `Event.sendEvent` (asynchronous).

---

## §12 — Activity Status Management

| Transition | Call | Trigger |
|-----------|------|---------|
| Advance | `NextActivity(orderRequest, orderCurrentActivity)` | At least one FE offer created |
| Skip | `SkipActivity("4")` | No FE offers created |
| Error | `HandleActivityException` | Any uncaught exception |

> **Note:** This rule does NOT call `GetActivityStatusString("1")` + `SendDataToDB`. It calls `NextActivity` directly — the standard pattern for synchronous internal enrichment rules.

---

## §13 — Exception / Error Handling

Entire `then` block wrapped in `try { ... } catch (Exception ae) { RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }`

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `RuleFunctions.BusinessValidation.Suspension.GetBarSocs(sub, isOrderPrepaid)` | Returns Object[] of BAR SOC codes; prepaid-aware |
| `RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, soc, filter)` | Builds XML for POU offer PreExecCheck evaluation |
| `RuleFunctions.Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, refId, soc, pOuRefId, filter)` | Builds XML for COU offer PreExecCheck evaluation |
| `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` | Advances process flow |
| `RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")` | Marks activity skipped |
| `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | Central exception handler |
| `OMXUtils:generateTrackingID()` | Generates unique extId for cloned FE offer |

---

## §15 — Function Dependency Tree

```text
OMX_CREATE_SUB_OFFER_BAR_SOC.rule
├── XPath.evalAsBoolean(isOrderPrepaid check)
├── [POU loop: ParentOU[i].Subscriber[j]]
│   ├── RuleFunctions.BusinessValidation.Suspension.GetBarSocs(sub, isOrderPrepaid)
│   ├── XPath.evalAsString($offer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(...)
│   ├── XPath.execute(chkXPath, sXML)
│   ├── XPath.evalAsBoolean(FE duplicate check)
│   └── Instance.createInstance(XSLT → FE SubscriberOffers clone)
│       └── OMXUtils:generateTrackingID()
├── [COU loop: ChildOU[c].Subscriber[j]]
│   └── RuleFunctions.Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...)
│       └── (same inner logic as POU)
├── RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)
├── Event.createEvent(XSLT → Logger)
├── Event.sendEvent(logEvent)
├── RuleFunctions.Helpers.SkipActivity(...)
└── RuleFunctions.Helpers.HandleActivityException(...)
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Properties Used |
|---------|-------------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.Customer.ParentOU[], ChildOU[], OrderData.OrderType, ProcessFlow |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, SubscriberOffers[] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Soc, ServiceType, OfferName, EffectiveDate, ExpirationDate, OfferInstanceId, RelatedOffersArray[], ParameterInfo[], ExtendedInfo[], SwitchFeature[] |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, PreExecCheck |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Determine BAR SOC codes for each subscriber using business rules (prepaid/postpaid-aware) |
| R2 | For each BAR SOC: check if FE copy (FE_OR_CCBS="FE") already exists |
| R3 | If no FE copy: clone offer with all fields (full deep copy of RelatedOffersArray, ParameterInfo, SwitchFeature, ExtendedInfo) |
| R4 | During clone: remap FE_OR_CCBS CCBS → FE; all other values unchanged |
| R5 | Evaluate PreExecCheck per-offer using subscriber-and-offer-specific XML context |
| R6 | Operate on both POU and COU subscribers |
| R7 | Skip if no FE offers created; advance immediately if any created (no response wait) |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| `GetBarSocs` business logic opaque to this rule — changes require updating only that helper | [LOW] | Document GetBarSocs contract separately |
| Per-offer PreExecCheck XML builder is a custom helper — must be reimplemented in target platform | [MEDIUM] | Extract XPath expression semantics; build equivalent in modern platform |
| FE_OR_CCBS remap hardcoded to CCBS→FE only — non-CCBS BAR SOC offers may have unexpected FE_OR_CCBS values | [LOW] | Verify what FE_OR_CCBS values BAR SOC offers can have with business team |
| All-FE-copies-exist → SkipActivity — silent skip on resubmission; verify this is desired | [LOW] | Confirm resubmission policy with process owner |
| No intermediate persistence (no SendDataToDB) — FE offers lost on crash; retry recreates via duplicate guard | [MEDIUM] | Ensure idempotency of enrichment step in modern platform |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXOM.OMX_CREATE_SUB_OFFER_BAR_SOC {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_CREATE_SUB_OFFER_BAR_SOC";
    orderRequest.ProcessFlow.NextActivityID == "OMX_CREATE_SUB_OFFER_BAR_SOC";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    try {
      boolean isSkipped = true;
      boolean isOrderPrepaid = XPath.evalAsBoolean(
        /* contains($globalVariables/.../PrepaidOrderTypes, concat(',', OrderType, ',')) */);

      int pOuLen = orderRequest.OrderData.Customer.ParentOU@length;
      for (int i = 0; i < pOuLen; i++) {
        String pOuRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;
        int pSubLen = orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length;

        /*** POU iteration Subscriber Start ***/
        for (int j = 0; j < pSubLen; j++) {
          Concepts.OrderRequest.OrderElements.Subscriber sub =
            orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j];
          Object[] barSocs = RuleFunctions.BusinessValidation.Suspension.GetBarSocs(sub, isOrderPrepaid);
          if (barSocs == null || barSocs@length == 0) { continue; }

          for (int k = 0; k < barSocs@length; k++) {
            int pOfferLen = sub.SubscriberOffers@length;
            for (int l = 0; l < pOfferLen; l++) {
              if (!String.equals(barSocs[k], sub.SubscriberOffers[l].Soc)) { continue; }

              Concepts.OrderRequest.OrderElements.SubscriberOffers offer = sub.SubscriberOffers[l];
              String filter = XPath.evalAsString(/* $offer/ExtendedInfo[Name="FE_OR_CCBS"]/Value */);
              String chkRes = "true";

              if (String.length(orderCurrentActivity.PreExecCheck) > 0) {
                String sXML = RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(
                  orderRequest, sub.RefId, offer.Soc, filter);
                chkRes = XPath.execute("/(" + orderCurrentActivity.PreExecCheck + ")", sXML, "ns0=...");
              }

              if (String.equals(chkRes, "true")) {
                boolean existsInFE = XPath.evalAsBoolean(
                  /* exists($sub/SubscriberOffers[Soc=offer.Soc and FE_OR_CCBS="FE"]) */);
                if (!existsInFE) {
                  Concepts.OrderRequest.OrderElements.SubscriberOffers feOffer =
                    Instance.createInstance(/* XSLT — FE offer clone, FE_OR_CCBS CCBS→FE — see §9.7 */);
                  sub.SubscriberOffers[sub.SubscriberOffers@length] = feOffer;
                  isSkipped = false;
                }
              }
            }
          }
        }
        /*** POU iteration Subscriber End ***/

        /*** ChildOU iteration Subscriber Start — identical logic using COU helper ***/
        int cOuLen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU@length;
        for (int c = 0; c < cOuLen; c++) {
          /* same loop structure; uses GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo */
        }
        /*** ChildOU iteration Subscriber End ***/
      }

      if (!isSkipped) {
        RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity);
        long pid = System.nanoTime();
        Event.sendEvent(Event.createEvent(/* Logger XSLT — see §11 */));
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

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
