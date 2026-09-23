# Request_ODS_GET_CREDIT_CLASS_CREDIT_LIMIT

## §1 Overview & Purpose

**ODS_GET_CREDIT_CLASS_CREDIT_LIMIT** calls ODS (Offer & Data Service) to retrieve a credit class and credit limit for each Account. Results are written back to Account ExtInfo as `ODS_CREDIT_CLASS` and `ODS_CREDIT_LIMIT` for downstream use by FM21 (CCBS_UPD_CREDIT_CLASS) and FM22 (CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT).

> **Multi-SIM pre-pass (unique pattern):** Before the Account loop, the rule scans ALL subscribers across ALL POU/ChildOU to identify multi-SIM subscribers (`TR_MULTISIM_IND=RCM` AND `FE_OR_CCBS=FE`). The accumulated `sumMinorRC` (sum of OfferRate) is passed as an XSLT parameter to every Account's request.

> **Two XSLT variants (OMX-2605):** Old XSLT omitted `priceplanRC` for DIY offers, included an OrderType=53 creditClass default, and lacked `relaxBlacklist`. Active XSLT adds all three.

> **Response write-backs (2):** Writes `ODS_CREDIT_CLASS` and `ODS_CREDIT_LIMIT` as AccountExtendedInfo using extId pattern `ACCEXT:{trackId}:{RefID}:CREDIT_CLASS/CREDIT_LIMIT`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_ODS_GET_CREDIT_CLASS_CREDIT_LIMIT` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | ODS |
| Event type (request) | `Events.OMConsumers.OMXFM.Request.ODS_GET_CREDIT_CLASS_CREDIT_LIMIT` |
| Event type (response) | `Events.OMConsumers.OMXFM.Response.ODS_GET_CREDIT_CLASS_CREDIT_LIMIT` |
| Send pattern | `Event.assertEvent` + `IntraActivitySequencing.ActionRequestEvent` per Account |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Iteration target | Pre-pass: all subscribers; Main loop: `Customer.Account[]` |
| Response concept | `Concepts.FM.Response.ODS_GetCreditClassCreditLimitRes` |
| Payload operation | `ns:getCreditClassAndCreditLimitRequest` |
| Key XSLT params | i (Account index), isMultiSIM, sumMinorRC, logicalDate, agreeRefId |

---

## §7 Key Logic Patterns & Dispatches

| Pattern | Detail |
|---------|--------|
| Multi-SIM pre-pass | Scans POU[i].ChildOU[k].Subscriber[j].SubscriberOffer[] AND POU[i].Subscriber[j].SubscriberOffer[]. Sets `isMultiSIM=true` when TR_MULTISIM_IND=RCM AND FE_OR_CCBS=FE. Accumulates `sumMinorRC += OfferRate`. |
| LogicalDate | `logicalDate = GetFirstBillDate(orderRequest)` — billing-cycle calculation. |
| agreeRefId | From `Account[i].AgreementRefId` — links Account to POU/Agreement for priceplan lookups. |
| OrderType=11002 paths | `primaryResourceValue`: POU[agreeRefId]/Subscriber[AccountRefId].MSISDN → ChildOU fallback. `priceplanName`: POU.Agreement[agreeRefId].Offer[0].ProductId. |
| DIY priceplanRC (OMX-2605) | Subscriber.SubscriberOffer[isDIYOffer='Y'].OfferRate → `priceplanRC`. Active XSLT only. |
| relaxBlacklist (OMX-2605) | Subscriber.ExtendedInfo[Name='RELAX_STATUS'].Value → `<relaxBlacklist>`. Written by NAS FM18 response. Old XSLT omitted this. |
| OrderType=53 creditClass default removed | Old XSLT sent hardcoded creditClass=3 for OT=53; active XSLT always lets ODS evaluate. |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority / JMSCorrelationID / OrderID  ← standard order fields
├── RefID                                      ← Account[$i]/RefId
├── OrderType                                  ← OrderData.OrderType
└── payload → ns:getCreditClassAndCreditLimitRequest
    ├── ns:accountId         ← Account[$i]/AccountID                   [Always]
    ├── ns:ban               ← Account[$i]/AccountID                   [Always]
    ├── ns:creditClass       ← xsi:nil=true                            [Always nil]
    ├── ns:creditLimit       ← xsi:nil=true                            [Always nil]
    ├── ns:logicalDate       ← GetFirstBillDate(orderRequest)          [Always]
    ├── ns:isMultiSIM        ← pre-pass: TR_MULTISIM_IND=RCM AND FE_OR_CCBS=FE [Always]
    ├── ns:sumMinorRC        ← accumulated OfferRate from pre-pass     [Always]
    ├── ns:accType           ← Account[$i]/AccountManagementInfo.AccountSubType [Always]
    ├── ns:primaryResourceValue ← OT=11002: POU[agreeRefId]/Subscriber[AccountRefId].MSISDN [Conditional: OT=11002]
    ├── ns:priceplanName     ← OT=11002: POU.Agreement[agreeRefId].Offer[0].ProductId [Conditional: OT-driven]
    │                           else: POU.Subscriber[AccountRefId].SubscriberOffer[0].ProductId
    ├── ns:priceplanRC       ← SubscriberOffer[isDIYOffer='Y'].OfferRate [Conditional: DIY offer exists, OMX-2605]
    ├── ns:relaxBlacklist    ← Subscriber.ExtInfo[RELAX_STATUS].Value  [Conditional: exists, OMX-2605]
    ├── ns:custNo            ← Customer.CustomerId                     [Always]
    ├── ns:companyCode       ← Account[$i]/AccountManagementInfo.CompanyCode [Always]
    └── ns:payChannelId      ← Account[$i]/PayChannelId                [Always]
```

---

## §15 Function Dependency Tree

```text
Request_ODS_GET_CREDIT_CLASS_CREDIT_LIMIT
├── [if resubmit] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── Instance.getByExtIdByUri(NextActivityName, Activity) → nextAct
├── GetFirstBillDate(orderRequest) → logicalDate
│
├── ── MULTI-SIM PRE-PASS (across all subscribers before Account loop) ──
│   for each POU[i].ChildOU[k].Subscriber[j].SubscriberOffer[l]:
│       if ExtInfo[TR_MULTISIM_IND]=RCM AND ExtInfo[FE_OR_CCBS]=FE:
│           isMultiSIM = true; sumMinorRC += OfferRate
│   for each POU[i].Subscriber[j].SubscriberOffer[l]:
│       if ExtInfo[TR_MULTISIM_IND]=RCM AND ExtInfo[FE_OR_CCBS]=FE:
│           isMultiSIM = true; sumMinorRC += OfferRate
│
├── ── ACCOUNT LOOP ──
│   for each Account[i]:
│   ├── [skip if CompletionStatus==2 response exists for RefId]
│   ├── agreeRefId = Account[i].AgreementRefId
│   ├── if PreExecCheck.length > 0: GetXMLForAccount(orderRequest, refId) → XPath
│   └── if chkRes == "true":
│       ├── Event.createEvent(active XSLT, params: i/isMultiSIM/sumMinorRC/logicalDate/agreeRefId)
│       ├── Event.assertEvent(reqEvent)
│       ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│       ├── isSkipped = false
│       └── sendEventImmediate(Logger REQ)
│
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
└── SendDataToDB(orderRequest)

Response_ODS_GET_CREDIT_CLASS_CREDIT_LIMIT
├── OMXUtils.generateTrackingID() → trackId
├── Instance.createInstance(ODS_GetCreditClassCreditLimitRes:
│   ResponseCode, ResponseMsg, CompletionStatus, ReferenceId, CreditClass, CreditLimit)
│   → currActivity.Response[n]
├── for each Account[i]: if Account[i].RefId == eventResponse.RefID:
│   ├── Account[i].ExtendedInfo[] += AccountExtendedInfo(
│   │       Name="ODS_CREDIT_CLASS",
│   │       Value=eventResponse.CreditClass,
│   │       extId="ACCEXT:{trackId}:{RefID}:CREDIT_CLASS")
│   └── Account[i].ExtendedInfo[] += AccountExtendedInfo(
│           Name="ODS_CREDIT_LIMIT",
│           Value=eventResponse.CreditLimit,
│           extId="ACCEXT:{trackId}:{RefID}:CREDIT_LIMIT")
├── sendEventImmediate(Logger RES)
└── IntraActivitySequencing.ActionResponseEvent(currActivity)
    [OLD fan-in commented out]
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Multi-SIM pre-pass is O(N×M): accounts × subscribers × offers — may be slow for large orders | [MEDIUM] | Pre-aggregate OfferRate at order construction time; pass as order data |
| relaxBlacklist depends on RELAX_STATUS written by FM18 (NAS_ACTIVATE_NEW_SUBS) — implicit FM18→FM20 ordering dependency | [MEDIUM] | Document and enforce in ProcessConfig sequencing |
| Old XSLT OrderType=53 hardcoded creditClass=3 removed — ODS now evaluates fully | [LOW] | Confirm OT=53 ODS evaluation is correct without default |
| ODS_GetCreditClassCreditLimitRes has 6 fields (adds CreditClass + CreditLimit to standard 4) | [LOW] | Preserve both response concept fields AND ExtInfo write-backs in migration |
| extId "ACCEXT:{trackId}:{RefID}:CREDIT_CLASS" ties result to call-time trackId — may fail on resubmit | [MEDIUM] | FM21/FM22 should search ExtInfo by Name, not extId |

---

## §19 Response Message Rule

Matches by `Account[i].RefId == eventResponse.RefID`. Writes two named ExtInfo keys to the matching Account.

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | ODS_GetCreditClassCreditLimitRes (6 fields: std 4 + CreditClass + CreditLimit) | Always |
| `Account[i].ExtendedInfo[]` Name="ODS_CREDIT_CLASS" extId="ACCEXT:{trackId}:{RefID}:CREDIT_CLASS" | `eventResponse.CreditClass` | Account.RefId == RefID |
| `Account[i].ExtendedInfo[]` Name="ODS_CREDIT_LIMIT" extId="ACCEXT:{trackId}:{RefID}:CREDIT_LIMIT" | `eventResponse.CreditLimit` | Account.RefId == RefID |

**Fan-in:** `IntraActivitySequencing.ActionResponseEvent(currActivity)`.
**Downstream consumers:** FM21 reads `ODS_CREDIT_CLASS`; FM22 reads `ODS_CREDIT_LIMIT` from Account.ExtendedInfo by Name.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
