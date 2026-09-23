# OMX_CAL_OFFERS_EFF_DATE

> Internal Effective Date Classifier — No Backend Call — Pure Computation. Annotates all offers with IM/BD/FUT. Prerequisite: CCBS_GOD must have run.

**Rule:** `Rules.OMConsumers.OMXOM.OMX_CAL_OFFERS_EFF_DATE` | **Priority:** 5 | **Pattern:** Internal Computation (OMXOM) — No External Call | **Completion:** NextActivity (self-advancing)

---

## §1 — Overview & Purpose

**OMX_CAL_OFFERS_EFF_DATE** is an **internal calculation rule** (OMXOM, not OMXFM) that classifies each offer's effective date relative to the system's LogicalDate. It adds two ExtendedInfo entries to every qualifying offer: `OfferActivityDate` (IM / BD / FUT) and `OfferOriginalEffectiveDate` (the raw date string). This classification drives which CCBS operations downstream FMs select (Immediate, Billing Date, or Future activation).

**No backend call is made.** The rule is self-completing — it calls `NextActivity` directly at the end rather than waiting for a response. There is no corresponding response rulefunction.

> **Key design notes:**
> - **Prerequisite: CCBS_GOD must have run.** The rule searches for CCBS_GOD in ProcessFlow.Activities; throws `DATA_ISSUE` if not found.
> - **LogicalDate source:** Reads `Concepts.OM.LogicalDate` concept — if blank, uses `DateTime.now()`. Writes the resolved date as `OrderData.ExtendedInfo[LOGICAL_DATE]`.
> - **FUT_TYPE override:** If `OrderData.ExtendedInfo[FUT_TYPE]` is `NXTPP` or `FUTPP` → all offers forced to `OfferActivityDate="IM"` regardless of dates.
> - **ChildOU Agreement filter:** Only processes ChildOU Agreement Offers where `FE_OR_CCBS="FE"` (skips CCBS-sourced offers). ParentOU Agreement Offers have no such filter.
> - **BD/IM + FUT expiry case:** If offer's EffectiveDate is IM or BD but ExpirationDate is FUT → also adds `OfferExpActivityDate="FUT"`.
> - **Wattanachai +1 day adjustment:** If OfferActivityDate="FUT" and the date falls before the logical date's comparison boundary → OfferOriginalEffectiveDate is advanced by +1 day.
> - **Agreement ExtendedInfo mirroring:** For Agreement-level offers, also mirrors OfferActivityDate into `agreement.ExtendedInfo[OfferActivityDate]`.
> - **Audit OPERATION_NAME bug:** Logger emits `"/Rules/OMConsumers/OMXOM/OMX_CAL_OFFERS_EFF_DATE"` and AUDIT_TRACE says "OMX-OM OfferInclusion Completed." — both reference wrong name (copy-pasted from OMX_OFFER_INCLUSION).

| Attribute | Value |
|-----------|-------|
| Rule file | OMX_CAL_OFFERS_EFF_DATE.rule (OMXOM, not OMXFM) |
| Response rulefunction | **None** — self-completing via `NextActivity` |
| Priority | 5 |
| Backend system | **None** — internal computation only |
| Pattern | Internal OMXOM rule (pure in-memory computation) |
| Completion | `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` |
| Output | ExtendedInfo annotations on AgreementOffers, SubscriberOffers, ParameterInfo, and Agreement concepts |
| LogicalDate source | `Concepts.OM.LogicalDate.LogicalDate` or `DateTime.now()` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard |
| forwardChain | true | Standard |
| Rule type | Internal OMXOM computation | No ESB/JMS dispatch; no external call; self-advances via NextActivity |
| Resubmit | N/A — idempotent | Rule re-classifies all offers on every invocation; no RequestCount or fan-in |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context; all Offers and ParameterInfo are read and annotated; OrderData.ExtendedInfo is written |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity status management; NextActivity call target |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId matches |
| 2 | `orderCurrentActivity.ActivityID == "OMX_CAL_OFFERS_EFF_DATE"` | Constrains to this rule |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_OFFERS_EFF_DATE"` | Double-check via NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity ready to process |

> **ProcessConfig PreExecCheck (step 8 gate):** `SubscriberOffers[1]` exists AND `FE_OR_CCBS = FE or BRMS`. Evaluated per Subscriber Offer during the internal loop — not at the rule-when level.

---

## §5 — Execution Flow Diagram

1. **CCBS_GOD prerequisite check** → Search `ProcessFlow.Activities` for `ActivityID=="CCBS_GOD"`. If not found → throw `DATA_ISSUE`.
2. **LogicalDate resolution** → Read `Concepts.OM.LogicalDate.LogicalDate`. If blank → `DateTime.now()`; else parse as `yyyy-MM-dd'T'HH:mm:ssXXX`. Write resolved date as `OrderData.ExtendedInfo[LOGICAL_DATE]`.
3. **FUT_TYPE check** → `isFromOmxFuture = ExtendedInfo[FUT_TYPE] in {NXTPP, FUTPP}`. If true → all OfferActivityDate values forced to "IM".
4. **PP@POU loop** — ParentOU Agreement Offers (no FE_OR_CCBS filter): ADD/REMOVE → OfferActivityDate + OfferOriginalEffectiveDate + BD/IM+FUT expiry case + agreement.ExtendedInfo mirror; CHG_PARAM → per ParameterInfo.
5. **Sub@POU loop** — ParentOU Subscriber SubscriberOffers: FE_OR_CCBS + PreExecCheck filter; ADD/REMOVE/blank → OfferActivityDate + Wattanachai +1 day; CHG_PARAM → per ParameterInfo.
6. **PP@COU loop** — ChildOU Agreement Offers (only FE_OR_CCBS="FE"): same PP logic; skip if CCBS-tagged.
7. **Sub@COU loop** — ChildOU Subscriber SubscriberOffers: same as Sub@POU with child XML helper.
8. **Complete** → `NextActivity(orderRequest, orderCurrentActivity)`; send Logger audit event.

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
// Step 1: CCBS_GOD prerequisite
godAct = search ProcessFlow.Activities for ActivityID=="CCBS_GOD";
if(godAct == null) throw Exception("DATA_ISSUE", "OMX did not find Get Offer Details response.");

// Step 2: LogicalDate
logicalDateRes = Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate");
logicalDate = (String.length(logicalDateRes.LogicalDate) <= 0) ? DateTime.now()
            : DateTime.parseString(logicalDateRes.LogicalDate, "yyyy-MM-dd'T'HH:mm:ssXXX");
OrderData.ExtendedInfo <- createInstance(LOGICAL_DATE, logicalDate);

// Step 3: FUT_TYPE check
boolean isFromOmxFuture = XPath.evalAsBoolean("ExtendedInfo[FUT_TYPE] in {NXTPP|FUTPP}");

// Steps 4-7: Loop all scopes
for(iPOU ...) {
    // PP@POU: Agreement Offers (no FE_OR_CCBS filter)
    for(iPouOffer ...) {
        agOff.Action = ADD|REMOVE -> offerEffectDate = EffectiveDate|ExpirationDate;
        offerActivityDate.Value = isFromOmxFuture ? "IM" : Helpers.GetActivityEffectiveType(offerEffectDate, logicalDate);
        agOff.ExtendedInfo <- [OfferActivityDate, OfferOriginalEffectiveDate];
        // BD/IM+FUT special
        if(ExpirationDate exists && (EffDate=IM||BD) && ExpDate=FUT) agOff.ExtendedInfo <- OfferExpActivityDate="FUT";
        agreement.ExtendedInfo <- AgreementExtendedInfo(OfferActivityDate);

        agOff.Action = CHG_PARAM -> for(iOfferParam) {
            offerParamActivityDate.Value = isFromOmxFuture ? "IM" : GetActivityEffectiveType(ParameterInfo.EffDate);
            ParameterInfo.ExtendedInfo <- [offerParamOriginalEffectiveDate, OfferParamActivityDate];
        }
    }

    // Sub@POU: Subscriber Offers (filtered via PreExecCheck)
    for(iPouSub...; iPouSubOffer...) {
        filter = subOff.ExtendedInfo[FE_OR_CCBS].Value;
        chkRes = XPath.execute(PreExecCheck, GetXMLForSubscriberOfferFilterWithExtendedInfo(...));
        if(chkRes != "true") continue;
        subOff.Action = ADD|REMOVE|blank -> offerActivityDate; OfferOriginalEffectiveDate;
        // Wattanachai: if FUT and CheckOfferDateWillCompareWithLogicalDate -> +1 day
        if(offerActivityDate="FUT" && CheckOfferDate..."B") OriginalEffDate += 1 day;
        subOff.Action = CHG_PARAM -> per ParameterInfo;
    }

    // PP@COU: ChildOU Agreement Offers (FE_OR_CCBS=="FE" only)
    for(iCOU...; iCouOffer...) {
        if(!FE_OR_CCBS=="FE") continue; // isSkip=true for CCBS-tagged offers
        // Same logic as PP@POU, including agreement.ExtendedInfo mirror
    }

    // Sub@COU: same as Sub@POU but uses GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo
}

Helpers.NextActivity(orderRequest, orderCurrentActivity);
// audit Logger — OPERATION_NAME bug: emits full path; AUDIT_TRACE: "OMX-OM OfferInclusion Completed."
```

---

## §7 — Effective Date Classification Logic

### §7.1 — OfferActivityDate Values

| Value | Meaning | When assigned |
|-------|---------|---------------|
| `"IM"` | Immediate — effective now | isFromOmxFuture=true (override); or GetActivityEffectiveType returns "IM" |
| `"BD"` | Billing Date — effective at next billing cycle | GetActivityEffectiveType returns "BD" |
| `"FUT"` | Future — effective at a specified future date | GetActivityEffectiveType returns "FUT" |

### §7.2 — Offer Effective Date Source by Action

| Action | offerEffectDate source |
|--------|----------------------|
| `ADD` (or blank for SubscriberOffers) | `agOff.EffectiveDate` / `subOff.EffectiveDate` |
| `REMOVE` | `agOff.ExpirationDate` / `subOff.ExpirationDate` |
| `CHG_PARAM` | `ParameterInfo[iOfferParam].EffectiveDate` (per-parameter) |

### §7.3 — FUT_TYPE Override

| ExtendedInfo[FUT_TYPE] | Effect |
|------------------------|--------|
| `NXTPP` or `FUTPP` | `isFromOmxFuture=true` → all OfferActivityDate = "IM" (bypasses GetActivityEffectiveType) |
| Any other / absent | Standard date comparison via `GetActivityEffectiveType(offerEffectDate, logicalDate)` |

### §7.4 — OfferExpActivityDate="FUT" Special Case

Applied when: `ExpirationDate exists` AND `(EffDate is IM OR (EffDate is BD AND ExpDate is FUT))`.
Adds `OfferExpActivityDate="FUT"` to the offer's ExtendedInfo. Supports the scenario where an offer is added with immediate/BD activation but has a future expiration.

> **[HIGH] Operator precedence bug:** The code reads `String.equals("IM", effType) || String.equals("BD", effType) && String.equals("FUT", expType)`.
> Due to `&&` having higher precedence than `||`, this evaluates as `IM || (BD && FUT)` — not `(IM || BD) && FUT` as likely intended.
> Result: if EffDate is IM, OfferExpActivityDate="FUT" is added regardless of ExpirationDate type.

### §7.5 — Wattanachai +1 Day Adjustment

When `OfferActivityDate=="FUT"` AND `CheckOfferDateWillCompareWithLogicalDate(offerEffectDate, logicalDate, "B")` returns true → OfferOriginalEffectiveDate is set to `offerEffectDate + 1 day` (formatted as `yyyy-MM-dd'T'HH:mm:ss.SSSXXX`). Applies to Sub@POU and Sub@COU scopes.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in BN_CHANGE_PACKAGE step 8, only when `SubscriberOffers[1]` exists and `FE_OR_CCBS = FE or BRMS`. The classification produced here is consumed by all subsequent CCBS price plan and subscriber change FMs.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Completion audit (unconditional) |

No outbound OMXFM request event. Pure in-memory computation rule.

### §8.3 — BE Working Memory Dependencies (Read)

| Concept path | Access | Purpose |
|-------------|--------|---------|
| `Concepts.OM.LogicalDate` | Read | LogicalDate string for date classification |
| `ProcessFlow.Activities[ActivityID=CCBS_GOD]` | Read | Prerequisite check — throws DATA_ISSUE if absent |
| `OrderData.ExtendedInfo[FUT_TYPE]` | Read | NXTPP/FUTPP override for isFromOmxFuture |
| `ParentOU[*].Agreement.Offers[*].EffectiveDate / ExpirationDate / Action / ParameterInfo` | Read | PP@POU effective date source |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].EffectiveDate / ExpirationDate / Action / ParameterInfo / ExtendedInfo[FE_OR_CCBS]` | Read | Sub@POU effective date source |
| `ParentOU[*].ChildOU[*].Agreement.Offers[*].ExtendedInfo[FE_OR_CCBS]` | Read | PP@COU filter (only FE) |
| `ParentOU[*].ChildOU[*].Subscriber[*].SubscriberOffers[*]` | Read | Sub@COU effective date source |

### §8.4 — BE Working Memory Dependencies (Written)

| Concept path | When | Value |
|-------------|------|-------|
| `OrderData.ExtendedInfo[LOGICAL_DATE]` | Always | Resolved logicalDate string |
| `Agreement.Offers[*].ExtendedInfo[OfferActivityDate]` | ADD/REMOVE | "IM" / "BD" / "FUT" |
| `Agreement.Offers[*].ExtendedInfo[OfferOriginalEffectiveDate]` | ADD/REMOVE | Raw effective/expiration date |
| `Agreement.Offers[*].ExtendedInfo[OfferExpActivityDate]` | BD/IM+FUT case | "FUT" |
| `Agreement.ExtendedInfo[OfferActivityDate]` | Mirrors offer's value | "IM" / "BD" / "FUT" |
| `Agreement.Offers[*].ParameterInfo[*].ExtendedInfo[OfferParamActivityDate]` | CHG_PARAM | "IM" / "BD" / "FUT" |
| `Agreement.Offers[*].ParameterInfo[*].ExtendedInfo[offerParamOriginalEffectiveDate]` | CHG_PARAM | Raw date |
| `SubscriberOffers[*].ExtendedInfo[OfferActivityDate]` | ADD/REMOVE/blank | "IM" / "BD" / "FUT" |
| `SubscriberOffers[*].ExtendedInfo[OfferOriginalEffectiveDate]` | ADD/REMOVE/blank | Raw date (may be +1 day) |
| `SubscriberOffers[*].ExtendedInfo[OfferExpActivityDate]` | BD/IM+FUT case | "FUT" |
| `SubscriberOffers[*].ParameterInfo[*].ExtendedInfo[OfferParamActivityDate]` | CHG_PARAM | "IM" / "BD" / "FUT" |
| `SubscriberOffers[*].ParameterInfo[*].ExtendedInfo[offerParamOriginalEffectiveDate]` | CHG_PARAM | Raw date |

### §8.5 — ChildOU FE_OR_CCBS Filter

PP@COU Agreement Offers are only processed if `ExtendedInfo[FE_OR_CCBS].Value == "FE"`. CCBS-sourced offers (tagged "CCBS" by CCBS_GET_AGREEMENT_INFO) are skipped (`isSkip=true`). ParentOU Agreement Offers have no such filter — all are processed.

---

## §9 — Payload Build

*Not applicable* — this rule makes no external backend call and builds no JMS/ESB payload.

Internal instances created:
- `OrderDataExtendedInfo` — LOGICAL_DATE record
- `AgreementOffersExtendedInfo` — OfferActivityDate, OfferOriginalEffectiveDate, OfferExpActivityDate
- `SubscriberOffersExtendedInfo` — same for SubscriberOffers scope
- `ParameterInfoExtendedInfo` — OfferParamActivityDate, offerParamOriginalEffectiveDate
- `AgreementExtendedInfo` — mirrors OfferActivityDate at Agreement level

---

## §11 — Audit Logging

| Event | Gate | OPERATION_NAME | AUDIT_TRACE | Bug? |
|-------|------|---------------|-------------|------|
| Completion audit | **Unconditional** | `"/Rules/OMConsumers/OMXOM/OMX_CAL_OFFERS_EFF_DATE"` | `"OMX-OM OfferInclusion Completed."` | [MEDIUM] Both wrong — full path; "OfferInclusion" name |

> The Logger audit OPERATION_NAME should be `"OMX_CAL_OFFERS_EFF_DATE"` and AUDIT_TRACE should reference the same activity. Current strings appear copy-pasted from OMX_OFFER_INCLUSION.

---

## §12 — Activity Status Management

| Condition | Action | Notes |
|-----------|--------|-------|
| Success | `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` | Self-advances to next step; no separate SendDataToDB call |
| Exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | Standard error handler |

---

## §13 — Exception / Error Handling

| Exception | Source | Handler |
|-----------|--------|---------|
| `DATA_ISSUE: "OMX did not find Get Offer Details response."` | Explicit throw when godAct == null (CCBS_GOD not in Activities) | Caught by outer try/catch → `HandleActivityException` |
| Any other exception | Date parse failure, XPath error, etc. | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Helpers.GetActivityEffectiveType(offerEffectDate, logicalDate)` | Core classifier: compares offer date to logicalDate → returns "IM", "BD", or "FUT" |
| `Helpers.CheckOfferDateWillCompareWithLogicalDate(offerEffectDate, logicalDate, "B")` | Wattanachai: checks if FUT date falls before logical date boundary → triggers +1 day |
| `Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, subscriberRefId, soc, filter)` | Build PreExecCheck XML for Sub@POU |
| `Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, subscriberRefId, soc, parentRefId, filter)` | Build PreExecCheck XML for Sub@COU |
| `Helpers.NextActivity(orderRequest, orderCurrentActivity)` | Advance flow to next step |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |
| `DateTime.parseString(date, pattern)` | Parse LogicalDate string from concept |
| `DateTime.now()` | Fallback when LogicalDate concept is blank |
| `DateTime.addDay(date, 1)` | Wattanachai +1 day adjustment |
| `DateTime.format(date, pattern)` | Format adjusted date to string |
| `OMXUtils.generateTrackingID()` | Generate extId for new ExtendedInfo concept instances |

---

## §15 — Function Dependency Tree

```text
OMX_CAL_OFFERS_EFF_DATE (rule)
├── try {
│   ├── [CCBS_GOD prerequisite check]
│   │   └── throw DATA_ISSUE if godAct == null
│   ├── Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")
│   ├── DateTime.parseString() OR DateTime.now()                 [LogicalDate resolution]
│   ├── Instance.createInstance()                                [LOGICAL_DATE ExtendedInfo]
│   ├── XPath.evalAsBoolean()                                    [FUT_TYPE check -> isFromOmxFuture]
│   ├── [ParentOU[i] loop]
│   │   ├── [PP@POU: Agreement.Offers loop]
│   │   │   ├── [ADD/REMOVE]
│   │   │   │   ├── isFromOmxFuture ? "IM" : Helpers.GetActivityEffectiveType()
│   │   │   │   ├── Instance.createInstance() [OfferActivityDate, OfferOriginalEffectiveDate]
│   │   │   │   ├── [BD/IM+FUT check] Helpers.GetActivityEffectiveType() x2
│   │   │   │   │   └── Instance.createInstance() [OfferExpActivityDate="FUT"]
│   │   │   │   └── Instance.createInstance() [AgreementExtendedInfo:OfferActivityDate]
│   │   │   └── [CHG_PARAM: per ParameterInfo]
│   │   │       └── Instance.createInstance() [OfferParamActivityDate, offerParamOriginalEffectiveDate]
│   │   ├── [Sub@POU: Subscriber.SubscriberOffers loop]
│   │   │   ├── Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo()
│   │   │   ├── XPath.execute() [PreExecCheck evaluation]
│   │   │   ├── Helpers.GetActivityEffectiveType()
│   │   │   ├── [if FUT] Helpers.CheckOfferDateWillCompareWithLogicalDate()
│   │   │   │   └── [if true] DateTime.addDay() + DateTime.format()
│   │   │   └── [CHG_PARAM: per ParameterInfo, +Wattanachai]
│   │   ├── [PP@COU: ChildOU.Agreement.Offers (FE_OR_CCBS="FE" only)]
│   │   │   └── [same as PP@POU pattern — skip if !FE]
│   │   └── [Sub@COU: ChildOU.Subscriber.SubscriberOffers]
│   │       ├── Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo()
│   │       └── [same as Sub@POU pattern]
│   ├── Helpers.NextActivity()
│   ├── Event.createEvent()  [Logger audit]
│   └── Event.Ext.sendEventImmediate()
└── catch -> Helpers.HandleActivityException()
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | Both | OrderData.ExtendedInfo[FUT_TYPE/LOGICAL_DATE], ParentOU/ChildOU/Subscriber/Agreement/Offers |
| `Concepts.OM.ProcessConfig.Activity` | Both | Status, PreExecCheck (nextAct) |
| `Concepts.OM.LogicalDate` | Read | LogicalDate (string, may be blank) |
| `Concepts.OrderRequest.OrderElements.AgreementOffers` | Read & Write | EffectiveDate, ExpirationDate, Action, ParameterInfo[], ExtendedInfo[] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Read & Write | Same fields; also ExtendedInfo[FE_OR_CCBS] read for filtering |
| `Concepts.OrderRequest.OrderElements.AgreementParameterInfo` | Read & Write | EffectiveDate, ExtendedInfo[] |
| `Concepts.OrderRequest.OrderElements.SubscriberParameterInfo` | Read & Write | EffectiveDate, ExtendedInfo[] |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.*` | Created | OrderDataExtendedInfo, AgreementOffersExtendedInfo, SubscriberOffersExtendedInfo, ParameterInfoExtendedInfo, AgreementExtendedInfo |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Verify CCBS_GOD has run before executing; throw error if absent |
| R2 | Resolve LogicalDate from concept store (DateTime.now() fallback); store as `OrderData.ExtendedInfo[LOGICAL_DATE]` |
| R3 | FUT_TYPE=NXTPP or FUTPP → force all offers to OfferActivityDate="IM" |
| R4 | Classify all Agreement Offers at ParentOU level (no FE_OR_CCBS filter); classify only FE-tagged Agreement Offers at ChildOU level |
| R5 | For Subscriber Offers (both POU and COU): apply PreExecCheck filter before classification |
| R6 | ADD/blank offers use EffectiveDate; REMOVE offers use ExpirationDate; CHG_PARAM uses per-ParameterInfo EffectiveDate |
| R7 | Mirror Agreement-level OfferActivityDate to agreement.ExtendedInfo |
| R8 | Wattanachai +1 day: if FUT and CheckOfferDateWillCompareWithLogicalDate("B")=true → advance OriginalEffectiveDate by 1 day |
| R9 | BD/IM + FUT expiry case: add OfferExpActivityDate="FUT" (note operator precedence bug — see design notes) |

### Design Notes

| Note | Severity | Detail |
|------|----------|--------|
| Operator precedence bug in OfferExpActivityDate: `IM \|\| (BD && FUT)` when intent is `(IM\|\|BD) && FUT` | [HIGH] | IM offers with any expiry type will get OfferExpActivityDate="FUT" annotation. Can cause incorrect FUT handling downstream. |
| Audit OPERATION_NAME/TRACE mismatch: Logger emits path string and "OfferInclusion" text | [MEDIUM] | Monitoring/troubleshooting impact — audit records are misidentified in logs |
| LogicalDate concept dependency: if concept is not loaded, falls back to DateTime.now() silently | [INFO] | Ensure LogicalDate is always populated in production |
| ChildOU Agreement FE_OR_CCBS="FE" filter: CCBS-sourced Agreement Offers in ChildOU are not classified | [INFO] | This asymmetry vs ParentOU must be preserved in migration |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXOM.OMX_CAL_OFFERS_EFF_DATE {
    attribute { priority = 5; forwardChain = true; }
    declare { OrderRequest orderRequest; Activity orderCurrentActivity; }
    when { /* extId / ActivityID / NextActivityID / Status == "WAITING" */ }
    then {
        try {
            nextAct = getByExtIdByUri(...);
            godAct = search Activities for ActivityID=="CCBS_GOD";
            if(godAct == null) throw Exception("DATA_ISSUE", "OMX did not find Get Offer Details response.");

            logicalDate = resolve from LogicalDate concept OR DateTime.now();
            OrderData.ExtendedInfo <- createInstance(LOGICAL_DATE);

            boolean isFromOmxFuture = XPath.evalAsBoolean("FUT_TYPE in {NXTPP,FUTPP}");

            for(iPOU...) {
                // PP@POU: all Agreement Offers -> OfferActivityDate/OfferOriginalEffectiveDate + OfferExpActivityDate
                for(iPouOffer...) {
                    // ADD/REMOVE/CHG_PARAM + agreement.ExtendedInfo mirror — see §7
                }
                // Sub@POU: filtered via FE_OR_CCBS + PreExecCheck, Wattanachai +1 day for FUT
                for(iPouSub...; iPouSubOffer...) { /* same logic */ }
                // PP@COU: only FE_OR_CCBS=="FE" ChildOU Agreement Offers
                for(iCOU...; iCouOffer...) { /* skip if !FE; same PP logic */ }
                // Sub@COU: ChildOU Subscriber Offers — same as Sub@POU with child XML helper
                for(iCouSub...; iCouSubOffer...) { /* same logic */ }
            }

            Helpers.NextActivity(orderRequest, orderCurrentActivity);
            /* Logger audit (OPERATION_NAME/TRACE incorrectly reference OfferInclusion) */
        } catch(Exception ae) { HandleActivityException; }
    }
}
```

---

## §19 — Response Message Rule

*Not applicable.* This is an internal OMXOM rule that calls `NextActivity` directly. There is no corresponding response rulefunction. The activity completes synchronously within the rule itself.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
