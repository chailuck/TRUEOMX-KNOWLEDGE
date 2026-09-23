# Request_OMX_CREATE_SUB_OFFER_PREPAID_REFUND

> TIBCO BusinessEvents · FM Logic Documentation

---

## §1 — Overview & Purpose

> **Internal OMX Rule (OMXOM) — No External Backend Call**
> This rule does *not* send any JMS/ESB event to a backend system. It performs pure in-memory computation: reads VAS and Convergence flags previously populated by CCP_GET_PREPAID_CREDIT_INFO, decodes bit-patterns to determine refund offer eligibility, and creates `SubscriberOffers` concepts directly in working memory. It then advances to the next activity synchronously using `NextActivity` — no fan-in wait required.

The rule determines which prepaid refund offers each subscriber is entitled to based on their VAS subscription and convergence status. Three offer codes are conditionally created:

| Offer Code | Constant name | Meaning | Eligibility gate |
|------------|---------------|---------|-----------------|
| `PRERFS02` | atb2 | ATB2 — Available Topup Balance 2 refund | `convergence[0] != "0"` |
| `PRERFS03` | iou | IOU — Internet On Us refund | `vas[16] ∈ {"1","3","5","7"}` (bit 0 set) |
| `PRERFS01` | daa | DDA — Data Allowance Advanced refund | `vas[16] ∈ {"4","5","6","7"}` (bit 2 set) |

| Item | Value |
|------|-------|
| Rule class | `Rules.OMConsumers.OMXOM.OMX_CREATE_SUB_OFFER_PREPAID_REFUND` |
| Rule file location | Rules/OMConsumers/OMXOM/ (not OMXFM) |
| Author | SathidP-PC |
| Backend call | None — pure in-memory computation |
| Completion mechanism | `RuleFunctions.Helpers.NextActivity` (synchronous — no fan-in) |
| Inputs consumed | `CDB_VAS` and `CDB_CONVERGENCE` ExtendedInfo from subscriber (set by CCP_GET_PREPAID_CREDIT_INFO) |
| Output | Up to 3 `SubscriberOffers` concepts per subscriber (ServiceType="85", FE_OR_CCBS="FE") |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule type | `rule` | Stateful RETE rule |
| priority | 5 | Standard priority |
| forwardChain | true | Re-evaluates on working memory changes |
| Namespace | OMXOM | Internal OMX logic — distinct from OMXFM (external feature manager) rules |
| Response rulefunction | None | Synchronous — no async backend; no response handler needed |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Root order — provides customer hierarchy and process flow pointer |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Current activity — provides PreExecCheck and Status |

Within the rule body, per-subscriber references are obtained directly:

| Variable | Type | How obtained |
|---------|------|-------------|
| `sub` | Concepts.OrderRequest.OrderElements.Subscriber | Direct array access: `ParentOU[i].Subscriber[j]` and `ChildOU[c].Subscriber[d]` |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Meaning |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity concept matches the current process step |
| 2 | `orderCurrentActivity.ActivityID == "OMX_CREATE_SUB_OFFER_PREPAID_REFUND"` | This rule fires only for this specific activity |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_CREATE_SUB_OFFER_PREPAID_REFUND"` | Process flow pointer confirms this step is next |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity has not yet been processed |

---

## §5 — Execution Flow Diagram

1. **Initialise offer codes** → set static constants `atb2="PRERFS02"`, `iou="PRERFS03"`, `daa="PRERFS01"`
2. **ParentOU Subscriber loop** → for each subscriber: PreExecCheck → read `CDB_VAS` + `CDB_CONVERGENCE` → decode bit-pattern → conditionally create PRERFS02/03/01 SubscriberOffers
3. **ChildOU Subscriber loop** → identical logic for ChildOU subscribers
4. **Skip / advance** → if any offer was created (`isSkipped=false`), call `NextActivity` (synchronous advance); otherwise `SkipActivity("4")`
5. **Audit log (always)** → `Event.sendEvent` logs completion — no `AllowWriteLog` gate
6. **Exception** → `HandleActivityException`

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

| Step | Logic | Detail |
|------|-------|--------|
| PreExecCheck | `orderCurrentActivity.PreExecCheck` | Read from current activity (not next activity — unlike OMXFM rules) |
| Read VAS | `XPath.evalAsString($sub/ExtendedInfo[Name="CDB_VAS"]/Value)` | Multi-character encoded string set by CCP response |
| Read Convergence | `XPath.evalAsString($sub/ExtendedInfo[Name="CDB_CONVERGENCE"]/Value)` | Convergence flag string set by CCP response |
| Guard check | `len(vasFromCDB) > 0 && len(convergenceFromCDB) > 0` | If either empty, skip subscriber |
| isATB2 | `convergence[0] != "0"` | `!String.equals(String.substring(convergenceFromCDB, 0, 1), "0")` |
| isIOU | `vas[16] ∈ {"1","3","5","7"}` | Bit 0 of position 16 in VAS string is set |
| isDDA | `vas[16] ∈ {"4","5","6","7"}` | Bit 2 of position 16 in VAS string is set |
| Dedup guard (per offer) | `not(exists($sub/SubscriberOffers[OfferName=...]))` | XPath check prevents duplicate offer creation |
| Create offer | `Instance.createInstance("xslt://...SubscriberOffers")` | OfferName=PRERFS0x, ServiceType="85", FE_OR_CCBS="FE" |
| Advance | `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` | Synchronous advance — no async fan-in |
| Audit | `Event.sendEvent(Logger)` | Always logged — no AllowWriteLog gate |

---

## §7 — Data Extraction — VAS String Bit Decoding

> The VAS string (from CCP `CDB_VAS` ExtendedInfo) encodes multiple service flags in a positional character format. Position 16 (0-indexed) is a single-character digit representing a 3-bit bitmask for IOU and DDA eligibility.

### VAS String Position 16 Decode Table

| Character at position 16 | isIOU (bit 0) | isDDA (bit 2) | Offers created |
|--------------------------|---------------|---------------|----------------|
| "0" | false | false | None |
| "1" | true  | false | PRERFS03 |
| "2" | false | false | None |
| "3" | true  | false | PRERFS03 |
| "4" | false | true  | PRERFS01 |
| "5" | true  | true  | PRERFS03 + PRERFS01 |
| "6" | false | true  | PRERFS01 |
| "7" | true  | true  | PRERFS03 + PRERFS01 |

### Convergence String Decode

| Condition | Meaning | Result |
|-----------|---------|--------|
| `convergence[0] != "0"` | Subscriber has convergence service active | isATB2 = true → create PRERFS02 |
| `convergence[0] == "0"` | No convergence service | isATB2 = false → no ATB2 offer |

> **[MEDIUM] Fragile position-based decode:** Uses `String.substring(vasFromCDB, 16, 17)` (returns one character at index 16). If the CCP VAS string format ever changes, the bit decode silently produces wrong results. The VAS string structure is undocumented in the rule.

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Fires for order types that include this activity in their ProcessConfig (e.g., PREPAID_CANCEL). No per-order-type branching — all eligible subscribers get the same offer-creation logic.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event type | Purpose | Notes |
|-----------|------------|---------|-------|
| [LOG] | Events.OMConsumers.OMXESB.Logger | Completion audit log | Via `Event.sendEvent` (not `sendEventImmediate`); always logged — no AllowWriteLog gate |

No outbound request to any backend system.

### §8.3 Upstream Data Dependencies

| Required data | Source activity | Field path | Used for |
|--------------|----------------|------------|---------|
| CDB_VAS | CCP_GET_PREPAID_CREDIT_INFO | `sub/ExtendedInfo[Name="CDB_VAS"]/Value` | IOU and DDA eligibility (position 16 decode) |
| CDB_CONVERGENCE | CCP_GET_PREPAID_CREDIT_INFO | `sub/ExtendedInfo[Name="CDB_CONVERGENCE"]/Value` | ATB2 eligibility (position 0 check) |

> **Note:** These keys use a "CDB_" prefix but were set by the CCP response handler. If either is absent, `isSkipped` stays true and the activity is skipped entirely.

### §8.4 BE Working Memory Written

| Concept | Field | Value |
|---------|-------|-------|
| SubscriberOffers (PRERFS02) | extId, OfferName, ServiceType, ExtendedInfo[FE_OR_CCBS] | UUID, "PRERFS02", "85", "FE" |
| SubscriberOffers (PRERFS03) | extId, OfferName, ServiceType, ExtendedInfo[FE_OR_CCBS] | UUID, "PRERFS03", "85", "FE" |
| SubscriberOffers (PRERFS01) | extId, OfferName, ServiceType, ExtendedInfo[FE_OR_CCBS] | UUID, "PRERFS01", "85", "FE" |

All offers: **ServiceType="85"** (prepaid refund offer type), **FE_OR_CCBS="FE"** (Front-End sourced).

### §8.5 Global Variable Dependencies

| Path | Used for |
|------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit log COMPONENT_NAME |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit log LOG_LEVEL |

---

## §9 — Offer Creation Logic (XSLT Concept Builders)

### §9.1 Common Structure (all three offers)

| Field | Value | Notes |
|-------|-------|-------|
| extId | `OMXUtils:generateTrackingID()` | UUID generated at creation |
| OfferName | PRERFS02 / PRERFS03 / PRERFS01 | Passed as XSLT param |
| ServiceType | "85" | Static literal — prepaid refund service type |
| ExtendedInfo.extId | `OMXUtils:generateTrackingID()` | UUID for the ExtendedInfo child |
| ExtendedInfo.Name | "FE_OR_CCBS" | Static tag indicating offer origin |
| ExtendedInfo.Value | "FE" | Front-End sourced |

### §9.2 Working Memory Enrichment Tree

```text
Subscriber.SubscriberOffers[]
└── SubscriberOffers[PRERFS02]   [Conditional: isATB2=true AND not(exists(OfferName="PRERFS02"))]
    ├── OfferName   ← "PRERFS02"   [Always]
    ├── ServiceType ← "85"          [Always]
    └── ExtendedInfo
        ├── Name    ← "FE_OR_CCBS" [Always]
        └── Value   ← "FE"          [Always]
└── SubscriberOffers[PRERFS03]   [Conditional: isIOU=true AND not(exists(OfferName="PRERFS03"))]
    ├── OfferName   ← "PRERFS03"   [Always]
    ├── ServiceType ← "85"          [Always]
    └── ExtendedInfo
        ├── Name    ← "FE_OR_CCBS" [Always]
        └── Value   ← "FE"          [Always]
└── SubscriberOffers[PRERFS01]   [Conditional: isDDA=true AND not(exists(OfferName="PRERFS01"))]
    ├── OfferName   ← "PRERFS01"   [Always]
    ├── ServiceType ← "85"          [Always]
    └── ExtendedInfo
        ├── Name    ← "FE_OR_CCBS" [Always]
        └── Value   ← "FE"          [Always]
```

### §9.3 Offer XSLT Source (ATB2 — IOU and DDA identical except param name)

```xml
<xsl:stylesheet xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    version="1.0">
  <xsl:param name="atb2"/>  <!-- "PRERFS02" (or $iou="PRERFS03" / $daa="PRERFS01") -->
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
        <OfferName><xsl:value-of select="$atb2"/></OfferName>
        <ServiceType>85</ServiceType>
        <ExtendedInfo>
          <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
          <Name>FE_OR_CCBS</Name>
          <Value>FE</Value>
        </ExtendedInfo>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — Working Memory Enrichment Map

No outbound XML payload. See §9.2 above for the in-memory enrichment tree.

---

## §11 — Audit Logging

> **No AllowWriteLog gate:** Unlike OMXFM rules, this rule always writes an audit log. Uses `Event.sendEvent` (not `sendEventImmediate`) — fire-and-forget on the standard event bus.

| Field | Value |
|-------|-------|
| ESBUUID | OMXTrackingId |
| PROCESS_ID | `concat(nanoTime, "_RES")` |
| COMPONENT_NAME | GlobalVar OMX_COMMON/Component_Name/OMX_CEP |
| OPERATION_NAME | *"OMX_CREATE_SUB_OFFER_PREPAID_REFUND"* |
| LOG_LEVEL | GlobalVar INFO level |
| AUDIT_TRACE | *"OMX_CREATE_SUB_OFFER_PREPAID_REFUND completed."* |
| payload | Empty `<payload/>` element (always present, always empty) |

No TARGET_SYSTEM field (no backend system called). PROCESS_ID uses "_RES" suffix despite being a completion event.

---

## §12 — Activity Status Management

| Path | Mechanism | Result |
|------|-----------|--------|
| Offers created | `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` | Activity completed — process flow advanced synchronously |
| No offers (skipped) | `RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")` | Activity marked SKIPPED |

> **Key difference from OMXFM rules:** `NextActivity` advances synchronously — no Status="IN_PROGRESS" intermediate state, no waiting for async response. Activity goes WAITING → COMPLETED directly.

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|---------|--------|---------|
| `RuleFunctions.Helpers.GetXMLForSubscriber` | String (XML) | Serialises subscriber sub-tree for XPath PreExecCheck (ParentOU) |
| `RuleFunctions.Helpers.GetXMLForSubscriberInChildOU` | String (XML) | Serialises ChildOU subscriber sub-tree for PreExecCheck |
| `XPath.evalAsString` | String | Reads ExtendedInfo fields from subscriber |
| `XPath.evalAsBoolean` | boolean | Offer dedup check: `not(exists(SubscriberOffers[OfferName=...]))` |
| `XPath.execute` | String | Evaluates PreExecCheck expression |
| `OMXUtils.generateTrackingID` | String | Generates UUID extId for new SubscriberOffers concepts |
| `RuleFunctions.Helpers.NextActivity` | void | Advances process flow synchronously (completion) |
| `RuleFunctions.Helpers.SkipActivity` | void | Marks activity as skipped and advances via skip path |
| `RuleFunctions.Helpers.HandleActivityException` | void | Marks activity FAILED and escalates |

---

## §15 — Function Dependency Tree

```text
OMX_CREATE_SUB_OFFER_PREPAID_REFUND (rule)
├── RuleFunctions.Helpers.GetXMLForSubscriber
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU
├── XPath.execute(PreExecCheck, xml)
├── XPath.evalAsString($sub/ExtendedInfo[Name="CDB_VAS"]/Value)
├── XPath.evalAsString($sub/ExtendedInfo[Name="CDB_CONVERGENCE"]/Value)
├── String.substring(convergenceFromCDB, 0, 1)        [ATB2 gate]
├── String.substring(vasFromCDB, 16, 17)              [IOU/DDA gate]
├── XPath.evalAsBoolean(not(exists(SubscriberOffers[OfferName=$atb2])))
├── XPath.evalAsBoolean(not(exists(SubscriberOffers[OfferName=$iou])))
├── XPath.evalAsBoolean(not(exists(SubscriberOffers[OfferName=$daa])))
├── Instance.createInstance("xslt://...SubscriberOffers") x up to 3
│   └── XSLT: SubscriberOffers concept (PRERFS02/03/01, ServiceType=85, FE_OR_CCBS=FE)
├── OMXUtils.generateTrackingID()
├── RuleFunctions.Helpers.NextActivity(req, act)      [synchronous advance]
├── Event.sendEvent(Logger)                           [always logs — no AllowWriteLog gate]
├── RuleFunctions.Helpers.SkipActivity(req, act, "4")
└── RuleFunctions.Helpers.HandleActivityException(...)
```

---

## §16 — Concept Definitions Referenced

| Concept | Key fields |
|---------|-----------|
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | extId (UUID), OfferName (PRERFS01/02/03), ServiceType ("85"), ExtendedInfo[FE_OR_CCBS="FE"] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, ExtendedInfo[CDB_VAS] (READ), ExtendedInfo[CDB_CONVERGENCE] (READ), SubscriberOffers[] (WRITE) |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Determine prepaid refund offer eligibility (ATB2, IOU, DDA) from VAS and Convergence flags per subscriber |
| R2 | Create SubscriberOffers concepts for eligible offers (ServiceType="85", FE_OR_CCBS="FE") |
| R3 | Idempotent offer creation — do not duplicate an offer already present |
| R4 | Support ParentOU and ChildOU subscriber hierarchies |
| R5 | Skip activity gracefully if VAS or Convergence data is absent |
| R6 | Log completion audit event regardless of order type |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| VAS string position 16 decode is undocumented and fragile — silent corruption if CCP changes string format | [MEDIUM] | Document VAS string schema; add length guard; replace with named fields in modern API |
| Depends on "CDB_VAS" / "CDB_CONVERGENCE" keys that are misleadingly named (sourced from CCP, not CDB) | [MEDIUM] | Rename keys in modern system; add source tagging to ExtendedInfo |
| If CDB_VAS or CDB_CONVERGENCE absent for all subscribers, entire step silently skipped — no error raised | [LOW] | Add warning log when skipped due to missing data |
| No AllowWriteLog gate — audit always written even for order types that suppress logging elsewhere | [LOW] | Add AllowWriteLog gate consistent with OMXFM rules |
| ChildOU comment typo "ChildOUOU iteration" — cosmetic copy-paste origin indicator | [INFO] | Fix comment |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author SathidP-PC
 */
rule Rules.OMConsumers.OMXOM.OMX_CREATE_SUB_OFFER_PREPAID_REFUND {
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
        orderCurrentActivity.ActivityID == "OMX_CREATE_SUB_OFFER_PREPAID_REFUND";
        orderRequest.ProcessFlow.NextActivityID == "OMX_CREATE_SUB_OFFER_PREPAID_REFUND";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        try {
            boolean isSkipped = true;
            int pOuLen = orderRequest.OrderData.Customer.ParentOU@length;
            String atb2 = "PRERFS02";
            String iou  = "PRERFS03";
            String daa  = "PRERFS01";

            for (int i = 0; i < pOuLen; i++) {
                int pSubLen = orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length;
                /*** POU Subscriber Loop ***/
                for (int j = 0; j < pSubLen; j++) {
                    Concepts.OrderRequest.OrderElements.Subscriber sub =
                        orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j];
                    String chkRes = "true";
                    if (String.length(orderCurrentActivity.PreExecCheck) > 0) {
                        String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, sub.RefId);
                        chkRes = XPath.execute("/("+orderCurrentActivity.PreExecCheck+")", sXML,
                            "ns0=www.tibco.com/be/ontology/Concepts/OrderRequest/OrderRequest");
                    }
                    if (String.equals(chkRes, "true")) {
                        String vasFromCDB = XPath.evalAsString(/* $sub/ExtendedInfo[Name="CDB_VAS"]/Value */);
                        String convergenceFromCDB = XPath.evalAsString(/* $sub/ExtendedInfo[Name="CDB_CONVERGENCE"]/Value */);
                        if (String.length(vasFromCDB) > 0 && String.length(convergenceFromCDB) > 0) {
                            // Decode convergence: first char != "0" → ATB2 eligible
                            Boolean isATB2 = !String.equals(String.substring(convergenceFromCDB, 0, 1), "0");
                            // Decode VAS position 16: bit 0 → IOU, bit 2 → DDA
                            Boolean isIOU = (String.equals(String.substring(vasFromCDB, 16, 17), "1")
                                || String.equals(String.substring(vasFromCDB, 16, 17), "3")
                                || String.equals(String.substring(vasFromCDB, 16, 17), "5")
                                || String.equals(String.substring(vasFromCDB, 16, 17), "7"));
                            Boolean isDDA = (String.equals(String.substring(vasFromCDB, 16, 17), "4")
                                || String.equals(String.substring(vasFromCDB, 16, 17), "5")
                                || String.equals(String.substring(vasFromCDB, 16, 17), "6")
                                || String.equals(String.substring(vasFromCDB, 16, 17), "7"));

                            if (isATB2 && XPath.evalAsBoolean(/* not(exists(SubscriberOffers[OfferName=$atb2])) */)) {
                                Concepts.OrderRequest.OrderElements.SubscriberOffers socATB2 =
                                    Instance.createInstance(/* §9.3: OfferName=$atb2="PRERFS02", ServiceType=85, FE_OR_CCBS=FE */);
                                sub.SubscriberOffers[sub.SubscriberOffers@length] = socATB2;
                            }
                            if (isIOU && XPath.evalAsBoolean(/* not(exists(SubscriberOffers[OfferName=$iou])) */)) {
                                Concepts.OrderRequest.OrderElements.SubscriberOffers socIOU =
                                    Instance.createInstance(/* §9.3: OfferName=$iou="PRERFS03", ServiceType=85, FE_OR_CCBS=FE */);
                                sub.SubscriberOffers[sub.SubscriberOffers@length] = socIOU;
                            }
                            if (isDDA && XPath.evalAsBoolean(/* not(exists(SubscriberOffers[OfferName=$daa])) */)) {
                                Concepts.OrderRequest.OrderElements.SubscriberOffers socDAA =
                                    Instance.createInstance(/* §9.3: OfferName=$daa="PRERFS01", ServiceType=85, FE_OR_CCBS=FE */);
                                sub.SubscriberOffers[sub.SubscriberOffers@length] = socDAA;
                            }
                            isSkipped = false;
                        }
                    }
                }
                /*** ChildOU Subscriber Loop (identical logic — GetXMLForSubscriberInChildOU for PreExecCheck) ***/
            }

            if (!isSkipped) {
                RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity);
                long pid = System.nanoTime();
                Event.sendEvent(Event.createEvent(/* Logger: AUDIT_TRACE="OMX_CREATE_SUB_OFFER_PREPAID_REFUND completed." */));
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
