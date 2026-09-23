# OMX_OFFER_INCLUSION

> Internal Mandatory Related Offer Injection — No Backend Call. Uses CCBS_GOD response in working memory to auto-inject offers with SelectedByDefault='Y' into each order offer's RelatedOffersArray.

**Rule:** `Rules.OMConsumers.OMXOM.OMX_OfferInclusion` | **ActivityID:** `OMX_OFFER_INCLUSION` | **Priority:** 5 | **Completion:** NextActivity or SkipActivity("4")

---

## §1 — Overview & Purpose

**OMX_OFFER_INCLUSION** is an internal OMXOM rule that auto-injects mandatory related offers into each order offer's `RelatedOffersArray`. It reads the CCBS_GOD (GetOfferDetails) response already in working memory, finds all `RelatedOffer` entries where `SelectedByDefault == 89` (ASCII 'Y'), and ensures each one is present. If absent, it creates a new `RelatedOffersArray` concept and appends it.

**No backend call is made.** Uses CCBS_GOD response data already stored as `GetOfferDetailsRes` concepts.

> **Key design notes:**
> - **Prerequisite: CCBS_GOD response in memory.** Collects all Activity entries where ActivityID=="CCBS_GOD". Throws DATA_ISSUE if none found.
> - **SelectedByDefault=89 ('Y') gate.** Original RelationType==77 logic commented out ("Change in logic by TRUE"). Now uses `SelectedByDefault` field.
> - **FE_OR_CCBS activity parameter filter.** If null → process all offers. If set → only process matching offers.
> - **PreExecCheck gate.** Full order serialized via `serializeUsingDefaults(orderRequest)`, XPath evaluated. If not "true" → `SkipActivity("4")`.
> - **Idempotent add.** Checks for manSoc in RelatedOffersArray before adding — no duplicates.
> - **CUG_ID ParameterInfo.** Subscriber Offer variants include ParameterInfo[CUG_ID] if `CUG_IND=Y` in SocProperties. Agreement variants do not.
> - **Audit Logger conditional on AllowWriteLog(OrderType).** Gated by order type — not unconditional.
> - **Multiple CCBS_GOD acts supported.** Iterates ALL collected CCBS_GOD activity entries.

| Attribute | Value |
|-----------|-------|
| Rule file | OMX_OfferInclusion.rule (OMXOM) |
| ActivityID matched | `OMX_OFFER_INCLUSION` |
| Response rulefunction | **None** |
| Backend system | **None** — reads CCBS_GOD working memory only |
| Completion | `NextActivity` on success; `SkipActivity("4")` if PreExecCheck fails |
| Output | New `RelatedOffersArray` concepts appended to AgreementOffers and SubscriberOffers |
| Activity parameter | `FE_OR_CCBS` — offer filter (null = all) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard |
| forwardChain | true | Standard |
| Rule class | Internal OMXOM | File is OMX_OfferInclusion.rule (not Request_) — no JMS dispatch |
| Skip code | `"4"` | Used when PreExecCheck evaluates to "false" |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order; read for offers; written by appending RelatedOffersArray concepts |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | PreExecCheck source; activity parameter source; NextActivity/SkipActivity target |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_OFFER_INCLUSION"` | Constrains to this rule |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_OFFER_INCLUSION"` | Double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Ready to process |

> **PreExecCheck (within THEN block):** Evaluated via `XPath.execute("/("+chkXPath+")", sXML, namespace)` where `sXML = Instance.serializeUsingDefaults(orderRequest)` (full order XML). If not "true" → `SkipActivity("4")`.

---

## §5 — Execution Flow Diagram

1. **Serialize order** → `Instance.serializeUsingDefaults(orderRequest)` → full XML string for XPath evaluation
2. **PreExecCheck gate** → if expression → false: `SkipActivity("4")` and stop
3. **Read FE_OR_CCBS parameter** → `GetActivityParamValueFromKey(orderCurrentActivity, "FE_OR_CCBS")` → filter string (may be null)
4. **CCBS_GOD prerequisite check** → collect all ProcessFlow.Activities where ActivityID=="CCBS_GOD"; throw DATA_ISSUE if empty
5. **Triple-nested loop** → for each GOD act → for each GOD response offer (godSoc) → for each RelatedOffer where `SelectedByDefault==89`
6. **PP@POU** → for each ParentOU Agreement Offer matching godSoc AND FE_OR_CCBS filter → check/add RelatedOffersArray (Agreement variant)
7. **Sub@POU** → for each ParentOU Subscriber SubscriberOffer → same pattern (Subscriber variant + CUG_ID if CUG_IND=Y)
8. **PP@COU** → for each ChildOU Agreement Offer → same as PP@POU (Agreement variant)
9. **Sub@COU** → for each ChildOU Subscriber SubscriberOffer → same as Sub@POU (ValuesArray conditional)
10. **Complete** → `NextActivity`; conditionally Logger audit if `AllowWriteLog(OrderType)`

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
// Serialize full order for PreExecCheck
String sXML = Instance.serializeUsingDefaults(orderRequest);
if(String.length(PreExecCheck)>0)
    chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=www.tibco.com/...");

if(String.equals(chkRes,"true")) {
    String fe_or_ccbs = Helpers.GetActivityParamValueFromKey(orderCurrentActivity, "FE_OR_CCBS");
    int selByDefInd = 89; // ASCII 'Y'

    // Collect all CCBS_GOD activities
    for(int iActItr; ...) if(ActivityID=="CCBS_GOD") Collections.add(arrLstGODs, act);
    if(Collections.size(arrLstGODs)==0) throw Exception("DATA_ISSUE", "OMX did not find Get Offer Details response.");

    for(int iGOD; iGOD < arrGODs@length; iGOD++) {        // each GOD act
        for(int iGODResOff; ...) {                         // each GOD offer
            godSoc = godRes.Code;
            for(int iRelOff; ...) {                        // each related offer
                if(godRes.RelatedOffers[i].SelectedByDefault == 89) { // 'Y'
                    manSoc = Code; manOffNm = Name; manSrvTyp = OfferType;
                    cugInd = substringBefore(substringAfter(socProp,"CUG_IND="),";");

                    for(iPOU...) {
                        // PP@POU Agreement Offers: FE_OR_CCBS match + Soc match -> check/add
                        //   createInstance(xslt://RelatedOffersArray [Agreement variant]) — see §9
                        // Sub@POU Subscriber Offers: same + CUG_ID ParameterInfo
                        //   createInstance(xslt://RelatedOffersArray [Sub POU variant])  — see §9
                        // PP@COU: same as PP@POU for ChildOU Agreement Offers
                        // Sub@COU: same as Sub@POU, ValuesArray conditional
                    }
                }
            }
        }
    }
    Helpers.NextActivity(orderRequest, orderCurrentActivity);
    if(AllowWriteLog(OrderType)) { /* Logger audit */ }
} else {
    Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
}
```

---

## §7 — FE_OR_CCBS Filter & SelectedByDefault Logic

### §7.1 — FE_OR_CCBS Activity Parameter Filter

| FE_OR_CCBS value | Effect |
|-----------------|--------|
| `null` (parameter absent) | No filter — ALL offers processed |
| `"FE"` | Only offers where `ExtendedInfo[Name='FE_OR_CCBS']/Value == "FE"` |
| `"CCBS"` | Only offers where `ExtendedInfo[Name='FE_OR_CCBS']/Value == "CCBS"` |

### §7.2 — SelectedByDefault Logic

| Field | Value | Meaning |
|-------|-------|---------|
| `godRes.RelatedOffers[i].SelectedByDefault` | `89` (int) | ASCII 'Y' — must be auto-injected |
| Original logic (commented out) | `RelationType == 77` | Legacy — no longer used |

> Per code comment: "Change in logic by TRUE, offer relation type not be used any more, use new field SelectedByDefault". The global variable `OMX_OM/BizRules/MandatoryOfferRelationType=77` is still read but the `if(RelationType==manOffRelType)` block is commented out.

### §7.3 — CUG_IND Handling

`CUG_IND` extracted from `SocProperties` via `String.substringBefore(String.substringAfter(socProperties, "CUG_IND="), ";")`.

| CUG_IND | Agreement POU/COU | Subscriber POU | Subscriber COU |
|---------|------------------|----------------|----------------|
| `"Y"` | No ParameterInfo | ParameterInfo[CUG_ID] + ValuesArray (always) | ParameterInfo[CUG_ID] + ValuesArray (conditional if value exists) |
| Other/absent | No ParameterInfo | No ParameterInfo | No ParameterInfo |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in BN_CHANGE_PACKAGE step 9. PreExecCheck on the activity entry gates whether injection runs. `FE_OR_CCBS` parameter determines which offers to scan.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Gate | Purpose |
|-----------|-----------|------|---------|
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `AllowWriteLog(OrderType)` | Completion audit (conditional) |

### §8.3 — BE Working Memory Dependencies (Read)

| Concept path | Purpose |
|-------------|---------|
| `ProcessFlow.Activities[ActivityID=CCBS_GOD]` | Source of offer details and related offers |
| `CCBS_GOD.Response[*].Code` | godSoc — the offer SOC to match against order offers |
| `CCBS_GOD.Response[*].RelatedOffers[*].SelectedByDefault` | 89 ('Y') gate for mandatory injection |
| `CCBS_GOD.Response[*].RelatedOffers[*].Code/Name/OfferType/SocProperties/RcIndicator` | manSoc, manOffNm, manSrvTyp, CUG_IND, RcIndicator |
| `ParentOU[*].Agreement.Offers[*].Soc, ExtendedInfo[FE_OR_CCBS], RelatedOffersArray` | Match godSoc; filter; duplicate check |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].Soc, ExtendedInfo[FE_OR_CCBS/CUG_ID], RelatedOffersArray` | Match + CUG_ID value |
| `ParentOU[*].ChildOU[*].Agreement.Offers[*] / ChildOU[*].Subscriber[*].SubscriberOffers[*]` | Same for COU scope |
| `orderCurrentActivity.PreExecCheck` | XPath gate expression |

### §8.4 — BE Working Memory Dependencies (Written)

| Concept path | Written when | Value |
|-------------|-------------|-------|
| `ParentOU[*].Agreement.Offers[*].RelatedOffersArray` | manSoc absent | New RelatedOffersArray concept (Agreement variant) |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].RelatedOffersArray` | manSoc absent | New RelatedOffersArray concept (Sub POU variant) |
| `ParentOU[*].ChildOU[*].Agreement.Offers[*].RelatedOffersArray` | manSoc absent | New RelatedOffersArray concept (Agreement variant) |
| `ParentOU[*].ChildOU[*].Subscriber[*].SubscriberOffers[*].RelatedOffersArray` | manSoc absent | New RelatedOffersArray concept (Sub COU variant) |

### §8.5 — Global Variable Dependencies

| Variable path | Default | Usage |
|--------------|---------|-------|
| `OMX_OM/BizRules/MandatoryOfferRelationType` | 77 | **Read but not used** — assigned to `manOffRelType` but the `if(RelationType==...)` block is commented out |

---

## §9 — Concept Construction — RelatedOffersArray Variants

### §9.1 — Agreement Offer Variant (PP@POU and PP@COU)

```text
createObject
└── object @extId ← $manSocExt (OMXUtils.generateTrackingID())    [Always]
    ├── OfferName    ← $manOffNm                                   [Always]
    ├── ServiceType  ← $manSrvTyp                                  [Always]
    ├── Soc          ← $manSoc                                     [Conditional: $manSoc]
    ├── RcIndicator  ← $godRes/RelatedOffers[n]/RcIndicator        [Always]
    └── SocProperties ← $socProperties                             [Always]
```

### §9.2 — Subscriber Offer Variant POU (Sub@POU)

```text
createObject
└── object @extId ← $manSocExt (generateTrackingID())             [Always]
    ├── OfferName    ← $manOffNm                                   [Conditional: $manOffNm]
    ├── ServiceType  ← $manSrvTyp                                  [Conditional: $manSrvTyp]
    ├── Soc          ← $manSoc                                     [Conditional: $manSoc]
    ├── ParameterInfo                                              [Conditional: $cugInd='Y']
    │   ├── ParamName   ← "CUG_ID"                                [Always (when parent present)]
    │   └── ValuesArray ← $subOff/ExtendedInfo[CUG_ID]/Value      [Always (when parent present)]
    ├── RcIndicator  ← $godRes/RelatedOffers[n]/RcIndicator        [Always]
    └── SocProperties ← $socProperties                             [Always]
```

### §9.3 — Subscriber Offer Variant COU (Sub@COU)

Same as Sub@POU except `ValuesArray` inside `ParameterInfo[CUG_ID]` is conditional:

```text
    ├── ParameterInfo                                              [Conditional: $cugInd='Y']
    │   ├── ParamName   ← "CUG_ID"                                [Always (when parent present)]
    │   └── ValuesArray ← $subOff/ExtendedInfo[CUG_ID]/Value      [Conditional: if value exists]
```

### §9.4 — Field Comparison Table

| Field | Agreement POU/COU | Sub POU | Sub COU |
|-------|------------------|---------|---------|
| `@extId` | [Always] | [Always] | [Always] |
| `OfferName` | [Always] | [Conditional: $manOffNm] | [Conditional: $manOffNm] |
| `ServiceType` | [Always] | [Conditional: $manSrvTyp] | [Conditional: $manSrvTyp] |
| `Soc` | [Conditional: $manSoc] | [Conditional: $manSoc] | [Conditional: $manSoc] |
| `ParameterInfo[CUG_ID]` | N/A | [Conditional: cugInd='Y'] | [Conditional: cugInd='Y'] |
| `ValuesArray` (inside CUG) | N/A | [Always when CUG parent] | [Conditional: value exists] |
| `RcIndicator` | [Always] | [Always] | [Always] |
| `SocProperties` | [Always] | [Always] | [Always] |

---

## §11 — Audit Logging

| Event | Gate | OPERATION_NAME | AUDIT_TRACE |
|-------|------|---------------|-------------|
| Completion audit | `AllowWriteLog(OrderType)` | `"/Rules/OMConsumers/OMXOM/OMX_OfferInclusion"` | `"OMX-OM OfferInclusion Completed."` |

> AUDIT_TRACE here is correct for this rule (unlike OMX_CAL_OFFERS_EFF_DATE which incorrectly used the same string). Logger payload is always empty.

---

## §12 — Activity Status Management

| Condition | Action | Notes |
|-----------|--------|-------|
| PreExecCheck passes AND success | `NextActivity(orderRequest, orderCurrentActivity)` | Normal advancement |
| PreExecCheck fails ("false") | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | Skip code "4" |
| Exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | Standard error handler |

---

## §13 — Exception / Error Handling

| Exception | Source | Handler |
|-----------|--------|---------|
| `DATA_ISSUE: "OMX did not find Get Offer Details response."` | Explicit throw when arrLstGODs is empty | Caught by catch → `HandleActivityException` |
| Any other exception | XPath parse, XSLT createInstance, serialization failure | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Helpers.GetActivityParamValueFromKey(orderCurrentActivity, "FE_OR_CCBS")` | Read FE_OR_CCBS activity parameter |
| `Instance.serializeUsingDefaults(orderRequest)` | Serialize full order to XML for PreExecCheck |
| `XPath.execute("/("+chkXPath+")", sXML, namespace)` | Evaluate PreExecCheck XPath |
| `XPath.evalAsBoolean(...FE_OR_CCBS_match...)` | Per-offer FE_OR_CCBS filter check |
| `Collections.List.createArrayList()` / `Collections.add()` / `Collections.toArray()` | Collect and iterate CCBS_GOD activities |
| `Instance.createInstance("xslt://{{/Concepts/.../RelatedOffersArray}}...")` | Create new RelatedOffersArray concept (4 variants) |
| `String.substringBefore(String.substringAfter(socProperties,"CUG_IND="),";")` | Extract CUG_IND from SocProperties |
| `System.getGlobalVariableAsInt("OMX_OM/BizRules/MandatoryOfferRelationType", 77)` | Read legacy global var (assigned but not used) |
| `OMXUtils.generateTrackingID()` | Generate unique extId for each new concept |
| `Helpers.NextActivity(orderRequest, orderCurrentActivity)` | Advance flow on success |
| `Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")` | Skip activity (PreExecCheck failed) |
| `Helpers.AllowWriteLog(OrderType)` | Gate for Logger audit event |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |

---

## §15 — Function Dependency Tree

```text
OMX_OfferInclusion (rule) [ActivityID: OMX_OFFER_INCLUSION]
├── try {
│   ├── Instance.serializeUsingDefaults(orderRequest)
│   ├── [if PreExecCheck present] XPath.execute()
│   ├── [if chkRes == "true"] {
│   │   ├── Helpers.GetActivityParamValueFromKey(act, "FE_OR_CCBS")
│   │   ├── System.getGlobalVariableAsInt(MandatoryOfferRelationType, 77) [unused]
│   │   ├── Collections.List.createArrayList() + Collections.add() [collect CCBS_GOD acts]
│   │   ├── [if empty] throw DATA_ISSUE
│   │   ├── Collections.toArray()
│   │   ├── [for each GOD act]
│   │   │   └── [for each GOD response offer]
│   │   │       └── [for each RelatedOffer where SelectedByDefault==89]
│   │   │           ├── String.substringBefore(substringAfter(socProp,"CUG_IND="),";")
│   │   │           └── [for each POU]
│   │   │               ├── [PP@POU] XPath.evalAsBoolean(FE_OR_CCBS) + scan + OMXUtils.generateTrackingID()
│   │   │               │   └── Instance.createInstance(RelatedOffersArray [Agreement])
│   │   │               ├── [Sub@POU] XPath.evalAsBoolean(FE_OR_CCBS) + scan + OMXUtils.generateTrackingID()
│   │   │               │   └── Instance.createInstance(RelatedOffersArray [Sub POU])
│   │   │               ├── [PP@COU] same as PP@POU
│   │   │               └── [Sub@COU] same as Sub@POU, ValuesArray conditional
│   │   ├── Helpers.NextActivity()
│   │   └── [if AllowWriteLog(OrderType)]
│   │       ├── System.nanoTime()
│   │       ├── Event.createEvent(xslt://Logger)
│   │       └── Event.Ext.sendEventImmediate()
│   } else {
│       └── Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")
│   }
└── catch -> Helpers.HandleActivityException()
```

---

## §16 — Concept Definitions Referenced

| Concept | Key fields |
|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | ProcessFlow.Activities, OrderData.Customer.ParentOU/ChildOU/Subscriber/Agreement/Offers |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, PreExecCheck, Status, Parameters |
| `Concepts.FM.Response.GetOfferDetailsRes` | Code (godSoc), RelatedOffers[].SelectedByDefault/Code/Name/OfferType/SocProperties/RcIndicator |
| `Concepts.OrderRequest.OrderElements.AgreementOffers` | Soc, ExtendedInfo[FE_OR_CCBS], RelatedOffersArray[] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Soc, ExtendedInfo[FE_OR_CCBS/CUG_ID], RelatedOffersArray[] |
| `Concepts.OrderRequest.OrderElements.RelatedOffersArray` | extId, OfferName, ServiceType, Soc, ParameterInfo(CUG_ID/ValuesArray), RcIndicator, SocProperties |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Evaluate PreExecCheck against full serialized order XML. If false → SkipActivity("4") |
| R2 | Read FE_OR_CCBS activity parameter. null = no filter; otherwise match per-offer ExtendedInfo |
| R3 | Require CCBS_GOD in ProcessFlow.Activities. Throw DATA_ISSUE if none found |
| R4 | For each GOD RelatedOffer with SelectedByDefault==89: check and inject if absent (idempotent) |
| R5 | Process all 4 scopes: PP@POU, Sub@POU, PP@COU, Sub@COU |
| R6 | Agreement variant: OfferName/ServiceType always; Soc conditional. No CUG_ID |
| R7 | Subscriber POU variant: OfferName/ServiceType/Soc conditional; CUG_ID ParameterInfo if CUG_IND=Y (ValuesArray always) |
| R8 | Subscriber COU variant: same as POU but ValuesArray also conditional on value existing |
| R9 | Audit log conditional on AllowWriteLog(OrderType) |

### Design Notes

| Note | Severity | Detail |
|------|----------|--------|
| MandatoryOfferRelationType global var read but never used | [MEDIUM] | Variable assigned but `if(RelationType==...)` block is commented out. Can be removed in migration. |
| Sub@POU vs Sub@COU CUG_ID ValuesArray difference | [INFO] | POU: ValuesArray always present inside CUG_ID block. COU: ValuesArray conditional on value existence. Must be preserved. |
| Multiple CCBS_GOD activities supported | [INFO] | Collects ALL Activity entries with ActivityID=="CCBS_GOD" and iterates all. Do not assume only one. |
| PreExecCheck evaluated on full order XML | [INFO] | Full order serialized once; XPath namespace hard-coded to `ns0=www.tibco.com/be/ontology/Concepts/OrderRequest/OrderRequest`. |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXOM.OMX_OfferInclusion {
    attribute { priority = 5; forwardChain = true; }
    declare { OrderRequest orderRequest; Activity orderCurrentActivity; }
    when { /* extId / ActivityID=="OMX_OFFER_INCLUSION" / NextActivityID / Status=="WAITING" */ }
    then {
        try {
            sXML = Instance.serializeUsingDefaults(orderRequest);
            chkRes = XPath.execute(...); // if PreExecCheck present
            if(chkRes == "true") {
                fe_or_ccbs = GetActivityParamValueFromKey("FE_OR_CCBS");
                selByDefInd = 89; // ASCII 'Y'
                // Collect all CCBS_GOD acts; throw DATA_ISSUE if none
                for(iGOD...) { for(iRes...) { godSoc = godRes.Code;
                    for(iRelOff...) {
                        if(SelectedByDefault == 89) {
                            manSoc = Code; manOffNm = Name; manSrvTyp = OfferType;
                            cugInd = extract CUG_IND from SocProperties;
                            for(iPOU...) {
                                // PP@POU: find agOff.Soc==godSoc + filter -> add if !isThere
                                //   createInstance(RelatedOffersArray [Agreement])   — see §9.1
                                // Sub@POU: same + CUG_ID ParameterInfo
                                //   createInstance(RelatedOffersArray [Sub POU])    — see §9.2
                                // PP@COU: same as PP@POU for ChildOU Agreement Offers
                                // Sub@COU: same as Sub@POU, ValuesArray conditional  — see §9.3
                            }
                        }
                    }
                } }
                Helpers.NextActivity(orderRequest, orderCurrentActivity);
                if(AllowWriteLog(OrderType)) { /* Logger audit */ }
            } else {
                Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch(Exception ae) { HandleActivityException; }
    }
}
```

---

## §19 — Response Message Rule

*Not applicable.* Internal OMXOM rule with no backend call. Completes via `NextActivity` or `SkipActivity` synchronously. No response rulefunction.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
