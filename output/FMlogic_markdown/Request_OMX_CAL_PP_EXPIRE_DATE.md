# OMX_CAL_PP_EXPIRE_DATE

## §1 Overview & Purpose

**OMX_CAL_PP_EXPIRE_DATE** is a pure in-memory calculation rule (no external backend call). It iterates over all Subscriber Offers with ServiceType="80" (PostPaid Plan) across both ParentOU and ChildOU subscribers, and populates contract date/remark parameters within each offer's `ParameterInfo[]` array.

> **No response rulefunction.** Computation completes within this rule. On success: calls `NextActivity` and sends audit log. If no qualifying offer found: calls `SkipActivity("4")`.

> **Bug — TR_CONTRACT_REMARK in ChildOU:** The ChildOU branch uses `$psub` (ParentOU subscriber variable) instead of `$csub` for the TR_CONTRACT_REMARK XPath lookup. The PP offer name written for ChildOU subscribers will be sourced from the ParentOU subscriber's offers. Fix in migration target.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXOM.OMX_CAL_PP_EXPIRE_DATE` |
| Rule type | OMXOM — internal OMX calculation (no ESB/backend call) |
| Priority | 5 |
| forwardChain | true |
| Backend | None — writes to BE working memory only |
| Target | `SubscriberOffers[ServiceType="80"].ParameterInfo[]` |

---

## §5 Execution Flow

1. Get `nextAct.PreExecCheck` from ProcessConfig
2. Loop: ParentOU[p] → Subscriber[ps] → SubscriberOffers[psof]:
   - Get `filter = offer.ExtendedInfo[FE_OR_CCBS]/Value`
   - If PreExecCheck present: evaluate against subscriber+offer XML
   - If `chkRes=="true"`: compute effDate (see §7) and write ParameterInfo
3. Same loop for ChildOU[c].Subscriber[cs].SubscriberOffers (TR_CONTRACT_REMARK has $psub bug)
4. If any offer processed (`!isSkipped`): call `NextActivity` + send audit log
5. Else: call `SkipActivity("4")`

---

## §7 Business Logic: ppEffeDate Priority Chain

| Priority | Source | Condition |
|----------|--------|-----------|
| 1 | `SubscriberOffers[ServiceType="80" AND FE_OR_CCBS="CCBS"]/ExtendedInfo[Name="PPOriginalEffectiveDate"]/Value` | CCBS offer with PPOriginalEffectiveDate |
| 2 | `SubscriberOffers[ServiceType="80" AND FE_OR_CCBS="FE"]/ExtendedInfo[Name="OfferOriginalEffectiveDate"]/Value` | FE offer with OfferOriginalEffectiveDate |
| 3 | `SubscriberOffers[ServiceType="80" AND FE_OR_CCBS="FE"]/EffectiveDate` | FE offer EffectiveDate (fallback) |
| Default | `DateTime.now()` | If all three null |

### ParameterInfo Writes

| ParamName | Value |
|-----------|-------|
| `TR_ACTUAL_CONTRACT_START_DATE` | `effDate + " 00:00:00"` |
| `TR_CONTRACT_REMARK` | FE OfferName > CCBS OfferName > `"-"` |
| `TR_ORIG_CONTRACT_EXPIRE_DATE` | `GetPPExpirationDate(effDate, durationMn, billCycle, 0) + " 00:00:00"` |
| `TR_CONTRACT_TERM` | `"0"` (static) |

---

## §15 Function Dependency Tree

```text
OMX_CAL_PP_EXPIRE_DATE
├── [for each qualifying offer]
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, psub.RefId, offer.Soc, filter)
│   ├── GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, csub.RefId, offer.Soc, pOuRefId, filter)
│   ├── XPath.execute(PreExecCheck, sXML, ns0=OrderRequest) → chkRes
│   ├── XPath.evalAsDateTime(ppEffeDate — 3-way priority CCBS/FE date)
│   ├── XPath.evalAsString(TR_CONTRACT_REMARK — FE/CCBS OfferName)
│   └── [for TR_ORIG_CONTRACT_EXPIRE_DATE]
│       ├── RuleFunctions.Helpers.GetPPDurationMonth(ppProps, offer.SocProperties) → durationMn
│       ├── RuleFunctions.Helpers.GetBillCycle(orderRequest) → billCycle
│       └── RuleFunctions.Helpers.GetPPExpirationDate(effDate, dateFormat, durationMn, billCycle, 0) → ppExpDate
├── [if !isSkipped]
│   ├── RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)
│   └── Event.Ext.sendEventImmediate(Logger{OPERATION_NAME="OMX_CAL_PP_EXPIRE_DATE"})
└── [if isSkipped]
    └── RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Bug: TR_CONTRACT_REMARK for ChildOU uses `$psub` instead of `$csub` | [MEDIUM] | Fix in migration target: use `$csub` for ChildOU TR_CONTRACT_REMARK lookup |
| No response rulefunction — activity completes within rule | [LOW] | Document that this is a synchronous internal rule — no JMS round-trip |
| ServiceType="80" filter is implicit in XPath | [LOW] | Verify all PP offers have ServiceType="80"; add explicit loop condition in migration |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
