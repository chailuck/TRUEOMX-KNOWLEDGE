# Request_AA_GET_SWITCH_FEATURE_PP

> Collects all unique SOC IDs across the entire order (all OUs, agreements, subscribers) and fetches their switch-feature metadata in a single batch call to AA (or CES for GoldenDB orders), then enriches the order working memory with the returned feature data.

**System:** AA / CES (GoldenDB) | **Priority:** 5 | **Author:** TOON  
**Pattern:** SOC aggregation + single batch send | **IGNORE_CCP parameter**  
**Response:** data enrichment (unconditional "true" return)

---

## §1 Overview & Purpose

A **data-lookup FM** — not a transactional order step. Collects all unique, non-blank SOC IDs from every Agreement.Offers, SubscriberOffers, and their RelatedOffersArray across the entire customer hierarchy (POU + COU). Sends them in one batch call to AA's `GetSwitchFeatureValueRequest`. The response handler injects the returned switch-feature data (`item_cd`, `swparam`, `switchcode`) back into the matching Offer/SubscriberOffer/RelatedOffer concepts in working memory.

> **Key pattern distinction:** Unlike most OMXFM rules that loop per-OU and send multiple requests, this FM aggregates ALL SOC IDs into one ArrayList and sends exactly *one* request (RequestCount = 1). The response always returns "true" unconditionally.

| Attribute | Value |
|-----------|-------|
| Rule File | `Request_AA_GET_SWITCH_FEATURE_PP.rule` |
| Response File | `Response_AA_GET_SWITCH_FEATURE_PP.rulefunction` → delegates to `Response_AA_GET_SWITCH_FEATURE_OFFER` |
| Author | TOON |
| Priority | 5 |
| Target System | AA (standard) / CES (if GoldenDB=Y) |
| Event (standard) | AA_GET_SWITCH_FEATURE_OFFER |
| Event (GoldenDB) | CES_GET_SWITCH_FEATURE_OFFER |
| Send pattern | Single batch: one request with all SOC IDs |
| RequestCount | 1 (if send occurs) |
| IGNORE_CCP param | If "Y" → skip SubscriberOffers with FE_OR_CCBS='CCP' or ServiceType='88' |
| Fan-in | Returns "true" unconditionally (no count check) |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |

---

## §4 Rule Conditions (WHEN)

| Condition | Purpose |
|-----------|---------|
| `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity pointer |
| `ActivityID == "AA_GET_SWITCH_FEATURE_PP"` | FM match |
| `orderRequest.ProcessFlow.NextActivityID == "AA_GET_SWITCH_FEATURE_PP"` | Flow alignment |
| `orderCurrentActivity.Status == "WAITING"` | Prevents re-firing |

---

## §5 Execution Flow

1. **Init** — Read `IGNORE_CCP` param. Check resubmit flag. Evaluate PreExecCheck XPath (if present). If false → skip SOC collection.
2. **SOC Collection** — Build `socArrayList` (dedup via `Collections.contains`):
   - POU Agreement.Offers[*].Soc + RelatedOffersArray[*].Soc
   - POU Subscriber[*].SubscriberOffers[*].Soc — filtered by IGNORE_CCP (skip if FE_OR_CCBS='CCP' OR ServiceType='88')
   - POU Subscriber[*].SubscriberOffers[*].RelatedOffersArray[*].Soc
   - COU Agreement.Offers and COU Subscriber.SubscriberOffers — same pattern (no IGNORE_CCP on COU)
3. **GoldenDB Branch** — If `GoldenDB == "Y"` → use `CES_GET_SWITCH_FEATURE_OFFER`. Else → `AA_GET_SWITCH_FEATURE_OFFER`. Both have identical XSLT.
4. **Send** — If socArrayList non-empty: build event, `sendEventImmediate`, `RequestCount++` (if !resubmit), `isSkipped=false`.
5. **Post-send** — If `!isSkipped` → `Status="1"` + `SendDataToDB`. Else → `SkipActivity("4")`.
6. **Exception** → `HandleActivityException`

> **IGNORE_CCP filter asymmetry:** Filter applied to POU SubscriberOffers only during SOC collection. COU SubscriberOffers added unconditionally. May be intentional but worth verifying.

---

## §7 Data Extraction

### §7.1 SOC Aggregation Algorithm

```java
Object socArrayList = Collections.List.createArrayList();

// POU Agreement SOCs
for(int iPou=0; iPou < pOULen; iPou++) {
    if(parentOu.Agreement != null) {
        for offer in parentOu.Agreement.Offers {
            addUnique(offer.Soc);
            for relOffer in offer.RelatedOffersArray { addUnique(relOffer.Soc); }
        }
    }
    // POU Subscriber SOCs (with IGNORE_CCP filter)
    for sub in parentOu.Subscriber {
        for offer in sub.SubscriberOffers {
            if(IGNORE_CCP=="Y" && (FE_OR_CCBS='CCP' || ServiceType='88')) continue;
            addUnique(offer.Soc);
            for relOffer in offer.RelatedOffersArray { addUnique(relOffer.Soc); }
        }
    }
    // COU Agreement + COU SubscriberOffers (no IGNORE_CCP)
    for(int iCou=0; iCou < cOULen; iCou++) {
        // Same pattern, no IGNORE_CCP filter
    }
}
// addUnique = !Collections.contains(list, soc) && !IsBlankOrStringNull(soc)
```

### §7.2 IGNORE_CCP Filter

| XPath Condition | Action | Scope |
|----------------|--------|-------|
| `exists($offer/ExtendedInfo[Name='FE_OR_CCBS' and Value='CCP']) or ($offer/ServiceType='88')` | Skip SOC | POU SubscriberOffers only |

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

| Trigger | ProcessConfig | Purpose |
|---------|--------------|---------|
| CHANGE_PP flow, step 80 | CHANGE_PP.xml | Fetch switch-feature metadata for all SOCs in order |

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event | Condition | Purpose |
|-----------|-------|-----------|---------|
| [OUTBOUND] | AA_GET_SWITCH_FEATURE_OFFER | GoldenDB != "Y" | Standard AA switch-feature lookup |
| [OUTBOUND] | CES_GET_SWITCH_FEATURE_OFFER | GoldenDB == "Y" | GoldenDB CES lookup |
| [OUTBOUND] | Logger (OMXESB) | Always (request) | Request audit |
| [OUTBOUND] | Logger (OMXESB) | `AllowWriteLog(OrderType)` | Response audit |

### §8.4 BE Working Memory — Read & Written Fields

| Path | Operation | Purpose |
|------|-----------|---------|
| ParentOU[*].Agreement.Offers[*].Soc | READ | SOC collection |
| ParentOU[*].Subscriber[*].SubscriberOffers[*].Soc | READ | SOC collection |
| ParentOU[*].Agreement.Offers[*].SwitchFeature[] | WRITE (append) | AgreementSwitchFeature enrichment |
| ParentOU[*].Agreement.Offers[*].RelatedOffersArray[*].SwitchFeature[] | WRITE (append) | RelatedOffresSwitchFeature enrichment |
| ParentOU[*].Subscriber[*].SubscriberOffers[*].SwitchFeature[] | WRITE (append) | SubscriberSwitchFeature enrichment |
| ParentOU[*].Subscriber[*].SubscriberOffers[*].RelatedOffersArray[*].SwitchFeature[] | WRITE (append) | RelatedOffresSwitchFeature enrichment |
| Same paths for ChildOU[*] | READ + WRITE | COU hierarchy |

### §8.6 Activity Parameters

| Parameter Key | Values | Purpose |
|--------------|--------|---------|
| IGNORE_CCP | "Y" / blank | If "Y" → skip CCP/ServiceType=88 SubscriberOffers during SOC collection and response mapping |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Param | Binding | Both Variants? |
|-------|---------|---------------|
| `orderRequest` | OrderRequest concept | Yes |
| `socIDs` | Collections.toArray(socArrayList) — Object[] with `<elements>` nodes | Yes |

### §9.3 JMS / Event Header Fields

| Header | Source | Conditional? |
|--------|--------|-------------|
| `JMSPriority` | `$orderRequest/OrderPriority` | [Conditional: if OrderPriority] |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | [Conditional: if OMXTrackingId] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Conditional: if OrderID] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Conditional: if OrderType] |

### §9.8 XSLT Stylesheet Source

Both AA and CES variants use identical XSLT (only the event type differs):

```xml
<xsl:stylesheet xmlns:ns="http://services.omx.truecorp.co.th/FM/getSwitchFeatureValueRequest"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="socIDs"/>     <!-- Object[] from Collections.toArray(socArrayList) -->
  <xsl:template match="/">
    <createEvent><event>
      <xsl:if test="$orderRequest/OrderPriority">
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderID">
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderType">
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      </xsl:if>
      <payload>
        <ns:GetSwitchFeatureValueRequest>
          <xsl:for-each select="$socIDs/elements">
            <ns:socid><xsl:value-of select="."/></ns:socid>
          </xsl:for-each>
        </ns:GetSwitchFeatureValueRequest>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**GoldenDB vs Standard difference:**

| Variant | Event type | XSLT |
|---------|-----------|------|
| Standard (GoldenDB != "Y") | AA_GET_SWITCH_FEATURE_OFFER | Identical |
| GoldenDB (GoldenDB == "Y") | CES_GET_SWITCH_FEATURE_OFFER | Identical |

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority           ← $orderRequest/OrderPriority                [Conditional: if OrderPriority]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId      [Conditional: if OMXTrackingId]
    ├── OrderID               ← $orderRequest/OrderData/OrderID            [Conditional: if OrderID]
    ├── OrderType             ← $orderRequest/OrderData/OrderType          [Conditional: if OrderType]
    └── payload
        └── ns:GetSwitchFeatureValueRequest                                [Always]
            └── ns:socid × N  ← element value (for-each $socIDs/elements) [Repeats per SOC]
```

---

## §11 Audit Logging

| Direction | OPERATION_NAME | AUDIT_TRACE | Send Method | Condition |
|-----------|---------------|-------------|-------------|-----------|
| Request (GoldenDB) | `"AA_GET_SWITCH_FEATURE_PP"` | `"Request Sent for Request_AA_GET_SWITCH_FEATURE_PP"` | sendEventImmediate | Always |
| Request (standard) | `"Request_AA_GET_SWITCH_FEATURE_PP"` | `"Request Sent for Request_AA_GET_SWITCH_FEATURE_PP"` | sendEventImmediate | Always |
| Response | `"AA_GET_SWITCH_FEATURE_OFFER"` | `"Response received for AA_GET_SWITCH_FEATURE_OFFER"` | sendEventImmediate | `AllowWriteLog(OrderType)` |

> Response audit gated on `AllowWriteLog(OrderType)` — not standard WritePayload global. Some order types may suppress response audit entirely.

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| socArrayList non-empty AND send completed | "1" IN_PROGRESS | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| socArrayList empty OR PreExecCheck false | SKIPPED | `SkipActivity("4")` |

---

## §15 Function Dependency Tree

```text
Request_AA_GET_SWITCH_FEATURE_PP
├── GetActivityParamValueFromKey(activity, "IGNORE_CCP")
├── Instance.getByExtIdByUri(...)                            [get nextAct for PreExecCheck]
├── Instance.serializeUsingDefaults(orderRequest.OrderData)  [if PreExecCheck present]
├── XPath.execute("/(PreExecCheck)", sXML, ns)               [evaluate PreExecCheck]
├── Collections.List.createArrayList()
├── Collections.contains / Collections.add / BRMS.IsBlankOrStringNull  [SOC dedup]
├── XPath.evalAsBoolean(IGNORE_CCP/CCP filter)               [POU SubscriberOffers]
├── Collections.size / Collections.toArray                   [pre-send check]
├── if GoldenDB=="Y":
│   └── Event.createEvent("xslt://CES_GET_SWITCH_FEATURE_OFFER") [§9.8]
│       + Event.Ext.sendEventImmediate + RequestCount++ + Logger
└── else:
    └── Event.createEvent("xslt://AA_GET_SWITCH_FEATURE_OFFER") [§9.8]
        + Event.Ext.sendEventImmediate + RequestCount++ + Logger

Response_AA_GET_SWITCH_FEATURE_PP
└── Response_AA_GET_SWITCH_FEATURE_OFFER(orderRequest, eventResponse, currActivity)
    ├── Instance.createInstance(AA_SwitchFeatureRes XSLT)    [§19.3]
    ├── currActivity.Response[length] = sfResActivity
    ├── GetActivityParamValueFromKey(currActivity, "IGNORE_CCP")
    ├── XPath.evalAsInt(count featurelist)                   [outer loop bound]
    ├── for each featurelist[z]:
    │   ├── XPath.evalAsString(featurelist[z+1]/soc_cd)
    │   ├── Match POU/COU Agreement.Offers → AgreementSwitchFeature + SetCugID
    │   ├── Match POU/COU Agreement RelatedOffersArray → RelatedOffresSwitchFeature + SetCugID
    │   ├── Match POU Subscriber.SubscriberOffers (IGNORE_CCP filter) → SubscriberSwitchFeature + SetCugID
    │   └── Match POU/COU SubscriberOffers.RelatedOffersArray → RelatedOffresSwitchFeature + SetCugID
    ├── if AllowWriteLog(OrderType): Event.Ext.sendEventImmediate(Logger)
    └── return "true" (unconditional)
```

---

## §17 Migration Notes & Recommendations

### §17.1 Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Collect all unique, non-blank SOC IDs from all OUs, agreements, subscribers, and related offers |
| R2 | Filter out CCP/ServiceType=88 SubscriberOffers when IGNORE_CCP="Y" (POU only) |
| R3 | Route to CES (not AA) when orderRequest.OrderData.GoldenDB="Y" |
| R4 | Enrich each matched Offer/SubscriberOffer/RelatedOffer with SwitchFeature data (item_cd, swparam, switchcode) |
| R5 | Inject CUG ID from ParameterInfo into each SwitchFeature concept via SetCugID |
| R6 | Skip activity if no SOCs collected or PreExecCheck false |

### §17.2 Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| IGNORE_CCP filter only applied to POU SubscriberOffers — COU not filtered | [MEDIUM] | Verify COU CCP scenario; apply filter symmetrically if needed |
| Response audit gated on AllowWriteLog(OrderType) — silently suppressed for some order types | [LOW] | Document which order types suppress; confirm intentional |
| PreExecCheck uses full OrderData serialization — performance impact on large orders | [MEDIUM] | Profile; consider targeted XPath without full serialization |
| Response OPERATION_NAME is "AA_GET_SWITCH_FEATURE_OFFER" not "AA_GET_SWITCH_FEATURE_PP" | [LOW] | Align OPERATION_NAME in migration if audit trace consistency required |
| Response returns "true" unconditionally — AA backend errors don't fail the flow | [HIGH] | Add CompletionStatus check before returning "true" |

---

## §18 Full Source Code

```java
/**
 * @author TOON
 */
rule Rules.OMConsumers.OMXFM.Request.Request_AA_GET_SWITCH_FEATURE_PP {
    attribute { priority = 5; forwardChain = true; }
    when {
        // ActivityID == "AA_GET_SWITCH_FEATURE_PP" + WAITING + flow alignment
    }
    then {
        String ignoreCCP = GetActivityParamValueFromKey(orderCurrentActivity, "IGNORE_CCP");
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            boolean isSkipped = true;
            // PreExecCheck evaluation (if present on nextAct)
            String chkRes = "true";
            if(String.length(nextAct.PreExecCheck) > 0) {
                sXML = Instance.serializeUsingDefaults(orderRequest.OrderData);
                chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, ns);
            }

            Object socArrayList = Collections.List.createArrayList();
            if(String.equals(chkRes,"true")) {
                /* §7.1: POU Agreement SOCs + POU SubscriberOffers SOCs (IGNORE_CCP filter)
                   + COU Agreement SOCs + COU SubscriberOffers SOCs (no IGNORE_CCP) */
            }

            if(Collections.size(socArrayList) > 0) {
                Object[] socIDs = Collections.toArray(socArrayList);
                if(!IsBlankOrStringNull(GoldenDB) && String.equals("Y", GoldenDB)) {
                    /* §9.8 CES_GET_SWITCH_FEATURE_OFFER — payload: ns:GetSwitchFeatureValueRequest { ns:socid × n } */
                    Event.Ext.sendEventImmediate(reqEvent_CES);
                } else {
                    /* §9.8 AA_GET_SWITCH_FEATURE_OFFER — identical payload */
                    Event.Ext.sendEventImmediate(reqEvent_AA);
                }
                if(!isActResub) orderCurrentActivity.RequestCount++;
                isSkipped = false;
            }

            if(!isSkipped) { Status = "1"; SendDataToDB(); }
            else SkipActivity("4");
        } catch(Exception ae) { HandleActivityException(..., ""); }
    }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

`Response_AA_GET_SWITCH_FEATURE_PP` is a thin wrapper that delegates to `Response_AA_GET_SWITCH_FEATURE_OFFER`. The shared rulefunction maps response fields into `AA_SwitchFeatureRes`, then iterates the returned featurelist and injects SwitchFeature sub-concepts into every matching Offer/SubscriberOffer/RelatedOffer in working memory. Returns "true" unconditionally.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Root order data — target for SwitchFeature enrichment |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.AA_GET_SWITCH_FEATURE_OFFER | Inbound response with featurelist |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Activity state — holds IGNORE_CCP parameter |

### §19.3 AA_SwitchFeatureRes Concept Construction

```text
createObject
└── object
    ├── @extId            ← OMXUtils:generateTrackingID()              [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode                [Conditional: if ResponseCode]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg                 [Conditional: if ResponseMsg]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus            [Conditional: if CompletionStatus]
    └── ReferenceId       ← $eventResponse/RefID                      [Conditional: if RefID]
```

**SwitchFeature Enrichment Concepts (per featurelist match):**

| Concept Type | Target Path | Fields |
|-------------|-------------|--------|
| AgreementSwitchFeature | Agreement.Offers[p].SwitchFeature[] | item_cd, swparam, switchcode + CugID |
| RelatedOffresSwitchFeature | Agreement.Offers[p].RelatedOffersArray[q].SwitchFeature[] | item_cd, swparam, switchcode + CugID |
| SubscriberSwitchFeature | Subscriber[j].SubscriberOffers[k].SwitchFeature[] | item_cd, swparam, switchcode + CugID |
| RelatedOffresSwitchFeature | Subscriber[j].SubscriberOffers[k].RelatedOffersArray[l].SwitchFeature[] | item_cd, swparam, switchcode + CugID |

### §19.4 Response Completion Logic

| Return value | Condition | Meaning |
|-------------|-----------|---------|
| `"true"` | Unconditional | Activity advances regardless of response content |

> Response returns "true" unconditionally — AA backend errors do not prevent flow advancement. Add CompletionStatus check if error-handling is needed.

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` |
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"AA_GET_SWITCH_FEATURE_OFFER"` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `"Response received for AA_GET_SWITCH_FEATURE_OFFER"` |
| Condition | `AllowWriteLog(orderRequest.OrderData.OrderType)` |
| payload/ns:ServicePayload | [Conditional: if WritePayload="true"] — copy of $eventResponse |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
