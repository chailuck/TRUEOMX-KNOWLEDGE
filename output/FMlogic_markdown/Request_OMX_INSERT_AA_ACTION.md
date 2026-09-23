# Request_OMX_INSERT_AA_ACTION

## §1 Overview & Purpose

Internal OMX enrichment activity — no external backend call. Pre-populates subscriber `ExtendedInfo` fields needed for AA SMS notification. The activity parameter specifies the action type (e.g., `SMS`). Operates primarily on ChildOU subscribers.

Key data computed: price plan name (`PP`), SOC description (`SOC_PROP`, language-aware TH/EN), contract offer name (`CONTRACT`), action type (`ACTION`), SMS indicator (`SMS_IND`), cycle count (`CYCLE_COUNT`), and PP effective/expiration dates (`EFFECT_DATE`, `EXPIRE_DATE`).

> **Note:** Rule file is unusually large (303KB) due to many inline XSLT `createInstance` calls.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_INSERT_AA_ACTION` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | OMX_INSERT_AA_ACTION |
| Type | Internal OMX working memory enrichment |
| Parameter | Action type string (e.g., `SMS`) |
| Response Concept | `Concepts.FM.Response.OMX_InsertAAActionRes` |
| Completion | `RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)` |

---

## §4 Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "OMX_INSERT_AA_ACTION"
orderRequest.ProcessFlow.NextActivityID == "OMX_INSERT_AA_ACTION"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 Execution Flow

1. Check PreExecCheck at order level
2. If passes: iterate ChildOU subscribers
3. Per-subscriber PreExecCheck (optional)
4. For passing subscribers, create ExtendedInfo entries:
   - `PP` ← `SubscriberOffers[ServiceType=80]/OfferName`
   - `SOC_PROP` ← language-aware description
   - `CONTRACT` ← `SubscriberOffers[ServiceType=85, TR_CONTRACT_IND=Y]/OfferName` or `"-"`
   - `ACTION` ← activity parameter
   - `SMS_IND` ← from SubscriberOffers (FE priority over BRMS)
   - `CYCLE_COUNT` ← from SubscriberOffers[FE_OR_CCBS=BRMS]
5. Calculate PP duration: `GetPPDurationMonth(socProps, propoSocProps)`
6. Get bill cycle: `GetBillCycle(orderRequest)`
7. Effective date: `DateTime.format(now, "dd-MMM-yyyy")`
8. Expiration date: `GetPPExpirationDate(effDate, format, durationMn, billCycle, -1)`
9. If language=TH: convert months via `ConvertMntoThaiMn`
10. Create and append `EFFECT_DATE`, `EXPIRE_DATE` ExtendedInfo

---

## §7 ExtendedInfo Fields Written

| Key | Source | Notes |
|-----|--------|-------|
| `PP` | `SubscriberOffers[ServiceType=80]/OfferName` | Price plan name |
| `SOC_PROP` | Language-dependent SOC description | TH: BILL_DESCRIPTION→thai→description; EN: english→description |
| `CONTRACT` | `SubscriberOffers[ServiceType=85, TR_CONTRACT_IND=Y]/OfferName` | Falls back to `"-"` |
| `ACTION` | `activity.Parameter[1]` | E.g., `"SMS"` |
| `SMS_IND` | `SubscriberOffers[FE_OR_CCBS=FE or BRMS]/ExtendedInfo[SMS_IND]` | FE > BRMS priority |
| `CYCLE_COUNT` | `SubscriberOffers[FE_OR_CCBS=BRMS]/ExtendedInfo[CYCLE_COUNT]` | |
| `EFFECT_DATE` | `DateTime.now()` formatted `dd-MMM-yyyy` | Thai months if language=TH |
| `EXPIRE_DATE` | Calculated from PP duration + bill cycle | Thai months if language=TH |

---

## §15 Function Dependency Tree

```text
Request_OMX_INSERT_AA_ACTION
├── GetXMLForSubscriber (order-level PreExecCheck)
├── XPath.execute("/(preExecCheck)", sXML, ...)
├── Instance.createInstance(PP ExtendedInfo XSLT)
├── Instance.createInstance(SOC_PROP XSLT)         ← language-aware
├── Instance.createInstance(CONTRACT XSLT)
├── Instance.createInstance(ACTION XSLT)
├── Instance.createInstance(SMS_IND XSLT)
├── Instance.createInstance(CYCLE_COUNT XSLT)
├── XPath.evalAsString(socProps)                    ← ServiceType=80 SocProperties
├── XPath.evalAsString(propoSocProps)               ← RMVX00000000001 SocProperties
├── GetPPDurationMonth(socProps, propoSocProps)
├── GetBillCycle(orderRequest)
├── DateTime.format(DateTime.now(), "dd-MMM-yyyy")
├── GetPPExpirationDate(effDate, format, durationMn, billCycle, -1)
├── ConvertMntoThaiMn(date, "-", format)            ← if language=TH
├── Instance.createInstance(EFFECT_DATE XSLT)
├── Instance.createInstance(EXPIRE_DATE XSLT)
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 Migration Notes

| # | Requirement / Risk | Severity |
|---|-------------------|---------|
| R1 | Language-aware SOC description: TH requires 3-level fallback chain | [HIGH] |
| R2 | PP expiration date requires duration from SocProperties + billing cycle | [HIGH] |
| R3 | CONTRACT falls back to `"-"` when no TR_CONTRACT_IND=Y offer exists | [MEDIUM] |
| R4 | SMS_IND: FE source takes precedence over BRMS | [MEDIUM] |
| R5 | EFFECT_DATE/EXPIRE_DATE must convert months to Thai if language=TH | [MEDIUM] |
| R6 | Uses BRMS offer RMVX00000000001 for promoend SOC properties | [LOW] |

---

## §19 Response Message Rule

Creates `OMX_InsertAAActionRes` with standard ResponseCode/ResponseMessage/CompletionStatus/ReferenceId. Completion via `RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
