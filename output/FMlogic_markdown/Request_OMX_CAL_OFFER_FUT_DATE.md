# Request_OMX_CAL_OFFER_FUT_DATE

> Internal OMXOM Rule — Calculate Offer Future/Immediate Date Enrichment

**Priority:** 5 | **forwardChain:** true | **Type:** OMXOM Internal (Synchronous) | **Author:** RS33-BANDIT

---

## §1 — Overview & Purpose

`OMX_CAL_OFFER_FUT_DATE` is an internal OMXOM computation rule. It enriches every offer in the order (Agreement Offers, Subscriber Offers, Related Offers) with date-type annotations — determining whether each offer's EffectiveDate and ExpirationDate are *immediate* (IM), *future* (FUT), or absent — relative to a logical reference date. The rule writes `EFF_TYPE` and `EXP_TYPE` ExtendedInfo fields onto each offer and clears or preserves the actual date fields accordingly.

> **⚙️ OMXOM Internal Pattern**
> Synchronous — no JMS or external backend call. Completes by calling `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)`. No response rulefunction exists.

| Property | Value |
|----------|-------|
| Rule class | `Rules.OMConsumers.OMXOM.OMX_CAL_OFFER_FUT_DATE` |
| Rule type | OMXOM Internal — synchronous computation |
| Completion | `RuleFunctions.Helpers.NextActivity()` |
| Backend integration | None — purely in-memory WM mutation |
| Scope | All ParentOU/ChildOU Agreement Offers, Subscriber Offers, and Related Offers |
| Activity Parameters | `CAL_PARAM_EXP`, `EXCLUDE_OFFER` |
| FUT_TYPE gate | Reads `orderRequest/OrderData/ExtendedInfo[FUT_TYPE]` (FUTSOC or EXPSOC) |
| Reference date | `Concepts.OM.LogicalDate` WM concept (falls back to `DateTime.now()`) |
| Author contribution | RS33-BANDIT (core logic) + Wattanachai (LogicalDate type A/B provisioning) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule Name | `OMX_CAL_OFFER_FUT_DATE` | Internal OMXOM computation rule |
| Namespace | `Rules.OMConsumers.OMXOM` | |
| Priority | 5 | |
| forwardChain | true | |
| Author | RS33-BANDIT | Additional Wattanachai section for LogicalDate type A/B |
| Commented-out code | `GetExpiredDateByDuration` calls on lines ~64, 111, 241, 288 | Legacy duration-based expiry calculation — replaced by parameter-based approach |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — Customer hierarchy (ParentOU/ChildOU) with offers |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — reads PreExecCheck; NextActivity called on it |
| `logicalDateRes` | `Concepts.OM.LogicalDate` | WM concept holding system logical date (extId="LogicalDate") |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Bind activity to current process position |
| 2 | `orderCurrentActivity.ActivityID == "OMX_CAL_OFFER_FUT_DATE"` | Route to this rule only |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_OFFER_FUT_DATE"` | Cross-check on ProcessFlow state |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Trigger only when activity is ready to execute |

---

## §5 — Execution Flow Diagram

```
1. Resolve logical date
   → Instance.getByExtIdByUri("LogicalDate") → logicalDateRes.LogicalDate
   → If blank: DateTime.now(); else: parse "yyyy-MM-dd'T'HH:mm:ssXXX"

2. Determine FUT_TYPE flag
   → XPath: boolean(ExtendedInfo[Name='FUT_TYPE' and (Value='FUTSOC' or Value='EXPSOC')])
   → isOmxFut = true/false

3. Read activity parameters
   → CAL_PARAM_EXP ("Y" enables OMX-2623 expiry-from-param logic)
   → EXCLUDE_OFFER (offer name excluded from CAL_PARAM_EXP)

4. ParentOU Agreement Offers loop
   → Evaluate FE_OR_CCBS filter → PreExecCheck per offer
   → Write EFF_TYPE, EXP_TYPE, EXP_DATE_VALUE ExtendedInfo
   → Clear dates per classification rules

5. ParentOU Subscriber Offers loop (+ Related Offers nested)
   → Same as step 4 + LOGICALDATE_PROV A/B (Wattanachai)
   → OMX-2623: TR_ORIG_CONTRACT_EXPIRE_DATE fallback
   → ServiceType=87 + FUT → SBM_NO_PROVISIONING=Y

6. ChildOU Agreement Offers + ChildOU Subscriber Offers (+ Related Offers)
   → Same logic as steps 4–5

7. Complete
   → RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)
   → Audit: "OMX-OM CalOfferFutureDate Completed."
```

---

## §6 — Rule Action (THEN) — Detail

### Date Type Classification Logic

`RuleFunctions.Helpers.GetActivityEffectiveType(date, logicalDate)` returns:

| Return Value | Meaning | Subsequent Action |
|-------------|---------|------------------|
| `IM` | Immediate — date is null or in the past relative to logicalDate | Clear date field (if !isOmxFut) |
| `FUT` | Future — date is after logicalDate | Save original as EXP_DATE_VALUE; clear ExpirationDate |
| (other) | Present or other classification | Preserve as-is |

### Offer Iteration Scope

| Offer Type | Path | Filter Helper |
|-----------|------|---------------|
| ParentOU Agreement Offers | `orderRequest.OrderData.Customer.ParentOU[p].Agreement.Offers[o]` | `GetXMLForAgreementOfferFilterWithExtendedInfo` |
| ParentOU Subscriber Offers | `...ParentOU[p].Subscriber[ps].SubscriberOffers[o]` | `GetXMLForSubscriberOfferFilterWithExtendedInfo` |
| ParentOU Related Offers | `...SubscriberOffers[o].RelatedOffersArray[r]` | `GetXMLForSubscriberRelatedOfferFilterWithExtendedInfo` |
| ChildOU Agreement Offers | `...ChildOU[c].Agreement.Offers[o]` | `GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo` |
| ChildOU Subscriber Offers | `...ChildOU[c].Subscriber[cs].SubscriberOffers[o]` | `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo` |
| ChildOU Related Offers | `...SubscriberOffers[o].RelatedOffersArray[r]` | `GetXMLForSubscriberRelatedOfferFilterWithExtendedInfo` |

### ExtendedInfo Written Per Offer

| ExtendedInfo Name | Value Source | Condition |
|------------------|-------------|-----------|
| `EFF_TYPE` | `GetActivityEffectiveType(offer.EffectiveDate, logicalDate)` | Always (if PreExecCheck passes) |
| `EXP_TYPE` | `GetActivityEffectiveType(offer.ExpirationDate, logicalDate)` | Always (if PreExecCheck passes) |
| `EXP_DATE_VALUE` | Original `offer.ExpirationDate` | Only when EXP_TYPE="FUT" |
| `LOGICALDATE_PROV` | "A" or "B" | When `CheckOfferDateWillCompareWithLogicalDate` returns type A or B |
| `SBM_NO_PROVISIONING` | "Y" | ServiceType="87" AND (EFF_TYPE="FUT" OR EXP_TYPE="FUT") — Subscriber Offers only |

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Used in PREPAID_ADD_OFFER (step 9) and any process needing offer date enrichment. The `FUT_TYPE` ExtendedInfo on the order controls whether IM dates are cleared — orders with FUT_TYPE=FUTSOC or EXPSOC preserve IM dates.

### §8.2 No ESB/JMS Integration

Pure in-memory computation. No JMS channel, no external system call. All data read from and written back to the OrderRequest WM concept.

### §8.4 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `Concepts.OM.LogicalDate[extId="LogicalDate"].LogicalDate` | READ | Reference date for classification |
| `orderRequest/OrderData/ExtendedInfo[Name="FUT_TYPE"]` | READ | Controls IM date clearing |
| `orderCurrentActivity.PreExecCheck` | READ | Per-offer XPath filter |
| `orderCurrentActivity.Parameter[CAL_PARAM_EXP]` | READ | "Y" enables OMX-2623 expiry logic |
| `orderCurrentActivity.Parameter[EXCLUDE_OFFER]` | READ | Offer name excluded from CAL_PARAM_EXP |
| `offer.EffectiveDate`, `offer.ExpirationDate` | READ/WRITE | Read for classification; may be cleared |
| `offer.ExtendedInfo[]` | WRITE (append) | EFF_TYPE, EXP_TYPE, EXP_DATE_VALUE, LOGICALDATE_PROV, SBM_NO_PROVISIONING |
| `offer.ServiceType` | READ | Checked for "87" to set SBM_NO_PROVISIONING |

### §8.5 Activity Parameters

| Parameter Key | Values | Effect |
|--------------|--------|--------|
| `CAL_PARAM_EXP` | "Y" / absent | If "Y": populate ExpirationDate from `TR_ORIG_CONTRACT_EXPIRE_DATE` offer parameter when null |
| `EXCLUDE_OFFER` | Offer name string | Named offer is excluded from the CAL_PARAM_EXP population |

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| PROCESS_ID | `concat($pid, "_RES")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `"OMX_CAL_OFFER_FUT_DATE"` (static) |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `"OMX-OM CalOfferFutureDate Completed."` (static) |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | Empty `<payload/>` — no payload logged |

---

## §12 — Activity Status Management

| Condition | Result |
|-----------|--------|
| Successful computation | `NextActivity()` called — advances to next step |
| Exception thrown | `HandleActivityException()` called — order enters error path |

> OMXOM rules do not set IN_PROGRESS status. They run synchronously, mutate WM, and advance via NextActivity or halt via HandleActivityException.

---

## §13 — Exception / Error Handling

```java
try {
    // ... entire computation ...
} catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

Empty string fourth parameter — no additional context passed. Handler sets order to error state and fires error events.

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|----------|--------|---------|
| `GetActivityEffectiveType(date, logicalDate)` | String ("IM"/"FUT"/other) | Classifies a date as immediate, future, or other |
| `GetActivityParameterValueFromKey(activity, key)` | String | Reads a named parameter from the activity |
| `GetXMLForAgreementOfferFilterWithExtendedInfo(...)` | String (XML) | XML context for PreExecCheck on ParentOU agreement offer |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(...)` | String (XML) | XML context for subscriber offer |
| `GetXMLForSubscriberRelatedOfferFilterWithExtendedInfo(...)` | String (XML) | XML context for subscriber related offer |
| `GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo(...)` | String (XML) | XML context for ChildOU agreement offer |
| `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...)` | String (XML) | XML context for ChildOU subscriber offer |
| `GetDateFromOfferParamName(offer, paramName)` | DateTime | Reads a date from offer parameter (e.g., TR_ORIG_CONTRACT_EXPIRE_DATE) |
| `GetDateFromRelatedOfferParamName(offer, paramName)` | DateTime | Same but for related offer |
| `CheckOfferDateWillCompareWithLogicalDate(date, logicalDate, type)` | boolean | Wattanachai: A/B provisioning bracket check |
| `NextActivity(orderRequest, activity)` | void | Advances process flow |
| `HandleActivityException(orderRequest, activity, ex, ctx)` | void | Sets order error state |

---

## §15 — Function Dependency Tree

```text
OMX_CAL_OFFER_FUT_DATE (rule)
├── Instance.getByExtIdByUri("LogicalDate")         [resolve logical date WM concept]
├── XPath.evalAsBoolean()                            [FUT_TYPE check: FUTSOC or EXPSOC]
├── RuleFunctions.Helpers
│   ├── GetActivityParameterValueFromKey()           [read CAL_PARAM_EXP, EXCLUDE_OFFER]
│   ├── (per offer iteration)
│   │   ├── XPath.evalAsString()                    [read FE_OR_CCBS filter]
│   │   ├── GetXMLFor*FilterWithExtendedInfo()      [XML context for PreExecCheck]
│   │   ├── XPath.execute()                         [evaluate PreExecCheck per offer]
│   │   ├── GetActivityEffectiveType()              [classify EFF_TYPE, EXP_TYPE]
│   │   ├── CheckOfferDateWillCompareWithLogicalDate()  [Wattanachai A/B type check]
│   │   ├── GetDateFromOfferParamName()             [OMX-2623: TR_ORIG_CONTRACT_EXPIRE_DATE]
│   │   └── Instance.createInstance(xslt://...)    [create ExtendedInfo concepts]
│   ├── NextActivity()                              [advance process flow]
│   └── HandleActivityException()                  [error path]
└── Event.Ext.sendEventImmediate()                 [emit audit log]
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | Must classify EffectiveDate and ExpirationDate per offer relative to configurable logical date | [HIGH] |
| R2 | FUT_TYPE=FUTSOC or EXPSOC must suppress IM date clearing | [HIGH] |
| R3 | When EXP_TYPE=FUT, original ExpirationDate must be saved as EXP_DATE_VALUE before clearing | [HIGH] |
| R4 | CAL_PARAM_EXP=Y must populate ExpirationDate from TR_ORIG_CONTRACT_EXPIRE_DATE (excluding EXCLUDE_OFFER) | [MEDIUM] |
| R5 | ServiceType 87 offers with FUT dates must have SBM_NO_PROVISIONING=Y | [MEDIUM] |
| R6 | LogicalDate type A/B provisioning bracket detection must be preserved | [MEDIUM] |
| R7 | Remove commented-out GetExpiredDateByDuration calls during migration | [LOW] |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| O(n³) iteration — nested loops over OU, Subscriber, Offer, RelatedOffer | [MEDIUM] | Profile for large orders; consider bulk enrichment in modern platform |
| LogicalDate WM concept: silently falls back to system clock if not seeded | [MEDIUM] | Always initialise LogicalDate; add alarm if absent |
| PreExecCheck XPath evaluated per offer — runtime string from config | [LOW] | Sanitise XPath strings from ProcessConfig at load time |
| Commented-out GetExpiredDateByDuration risk of accidental reactivation | [LOW] | Remove permanently during migration |

---

## §18 — Full Source Code (condensed)

```java
rule Rules.OMConsumers.OMXOM.OMX_CAL_OFFER_FUT_DATE {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_CAL_OFFER_FUT_DATE";
    orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_OFFER_FUT_DATE";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    try {
      // 1. Resolve logical date
      DateTime logicalDate;
      Concepts.OM.LogicalDate logicalDateRes =
          Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate");
      if(String.length(String.trim(logicalDateRes.LogicalDate)) <= 0) {
          logicalDate = DateTime.now();
      } else {
          logicalDate = DateTime.parseString(logicalDateRes.LogicalDate, "yyyy-MM-dd'T'HH:mm:ssXXX");
      }

      // 2. FUT_TYPE: FUTSOC or EXPSOC → preserve IM dates
      boolean isOmxFut = XPath.evalAsBoolean("xpath://...FUT_TYPE=FUTSOC or EXPSOC...");

      String logicalDateTypeA = "A";  // Wattanachai
      String logicalDateTypeB = "B";

      // 3. Activity parameters
      String calParamExp = GetActivityParameterValueFromKey(orderCurrentActivity, "CAL_PARAM_EXP");
      String excludeOffer = GetActivityParameterValueFromKey(orderCurrentActivity, "EXCLUDE_OFFER");

      // 4-6. Iterate ParentOU → Agreement Offers, Subscriber Offers (+ Related), ChildOU → same
      // Per offer: read FE_OR_CCBS filter, evaluate PreExecCheck, then:
      //   - EFF_TYPE = GetActivityEffectiveType(offer.EffectiveDate, logicalDate)
      //   - If EFF_TYPE="IM" && !isOmxFut: clear EffectiveDate
      //   - LOGICALDATE_PROV: CheckOfferDateWillCompareWithLogicalDate() → A or B (Wattanachai)
      //   - OMX-2623: if ExpirationDate=null && calParamExp="Y": GetDateFromOfferParamName(offer,"TR_ORIG_CONTRACT_EXPIRE_DATE")
      //   - EXP_TYPE = GetActivityEffectiveType(offer.ExpirationDate, logicalDate)
      //   - If EXP_TYPE="FUT": save as EXP_DATE_VALUE, clear ExpirationDate
      //   - If EXP_TYPE="IM" && !isOmxFut: clear ExpirationDate
      //   - If ServiceType="87" && (EFF_TYPE="FUT"||EXP_TYPE="FUT"): SBM_NO_PROVISIONING=Y

      // 7. Complete
      RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity);
      // Audit: "OMX-OM CalOfferFutureDate Completed."

    } catch (Exception ae) {
      RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
