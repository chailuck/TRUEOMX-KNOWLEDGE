# Request_CCBS_ADD_AGREEOFFER

## §1 Overview & Purpose

**CCBS_ADD_AGREEOFFER** adds service offers to existing CCBS Agreements for both POU and ChildOU paths. Unlike other ACTIVATION FMs which send one event per OU/account, this rule sends one event **per offer** within each Agreement — a POU with 3 qualifying offers generates 3 separate JMS requests.

> **Three-pass logic per POU iteration:**
> 1. **Pass 1 (SOC deduplication):** Collects unique SOCs from ALL offers (POU+ChildOU RelatedOffersArray) + BRMS-derived `GetSplOffIndForSoc` values (PLG/CAP/RPD/CPD etc.) into `alSOCs`/`alPropVal` arrays.
> 2. **Pass 2 (POU offers):** Filters POU.Agreement.Offers via PreExecCheck → sends one event per qualifying offer.
> 3. **Pass 3 (ChildOU offers):** Same for ChildOU.Agreement.Offers.

> **Sequence number allocation:** Each event requests a SOC_SEQ_NO increment = count(offers) + count(offers/RelatedOffersArray) via `GetSequenceValueRequest`.

> **Pooled offer write-back (response):** For each OfferDetail where SOC is RPD/CPD (pooled), appends `AgreementExtendedInfo` Name=`POOLED_OFFER_INSTANCE_ID_{soc}` / Value=`OfferInstanceCode` to the matched Agreement's ExtendedInfo.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_ADD_AGREEOFFER` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS |
| Event type | `Events.OMConsumers.OMXFM.Request.CCBS_ADD_AGREEOFFER` |
| Response event | `Events.OMConsumers.OMXFM.Response.CCBS_ADD_AGREEOFFER` |
| Send pattern | `Event.assertEvent` + `IntraActivitySequencing` per Offer (not per Agreement) |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Iteration target | `Customer.ParentOU[] → Agreement.Offers[] + ChildOU.Agreement.Offers[]` |
| Response concept | `Concepts.FM.Response.CCBS_AddAgreeOfferRes` |
| Payload operation | `ns:addOfferRequest` (includes `GetSequenceValueRequest`) |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| SOC deduplication (alSOCs/alPropVal) | Pre-pass collects unique SOCs + propValue. Used to inject "Agreement level offer instance ID" parameterInfo for PLG/CAP SOCs only. |
| Per-offer event send | One event per qualifying offer. High-volume orders generate many parallel requests. |
| Sequence pre-allocation | `incrementByCount = count(offers/elements) + count(offers/elements/RelatedOffersArray)` |
| chargeDistributionDetailsInfo | For each offer where `RCIndicator != 64`: `targetPayChannelId = Account[RefId=$acctRefId].PayChannelId` |
| LargeCustomerIndicator=89 gate | `enclosedClientInfo.logicalDate` included only when indicator=89; logicalDate = offer EffectiveDate or tomorrow |
| reqSuccess correlation | Checks `Response[ReferenceId == Agreement.RefId AND CompletionStatus==2]` — correct (by Agreement.RefId) |

---

## §10 XSLT Field Mapping (POU path; ChildOU path identical with ChildOU indices)

```text
createEvent → event
├── JMSPriority / JMSCorrelationID / OrderID   ← standard order fields     [Conditional]
├── RefID                                       ← POU[i].Agreement.RefId    [Conditional]
├── UserName / PassWord                         ← User / Password           [Credential-gated: IsEnableUserPass='true']
├── OrderType / CES                             ← standard order fields     [Conditional]
└── payload → ns:addOfferRequest
    ├── ns2:GetSequenceValueRequest
    │   ├── sequenceName ← "SOC_SEQ_NO"                                      [Always]
    │   └── incrementByCount ← count(offers/elements) + count(offers/elements/RelatedOffersArray)  [Always]
    │
    └── ns:AddOfferRequest
        ├── ns:AgreementIdInfo → agreementNo ← POU[i].Agreement.AgreementId  [Always]
        │
        ├── ns:services (foreach agrOffer)
        │   └── ns:srvAgrInfo
        │       ├── dealerCode          ← OrderData.DealerCode                [Always]
        │       ├── deployMode          ← agrOffer.DeployMode                 [Conditional]
        │       ├── effectiveDate       ← agrOffer.EffectiveDate              [Conditional]
        │       ├── expirationDate      ← agrOffer.ExpirationDate             [Conditional]
        │       ├── relatedOffers (foreach RelatedOffersArray):
        │       │   dealerCode, name=OfferName, serviceType [cond], soc
        │       ├── serviceType         ← agrOffer.ServiceType                [Conditional]
        │       └── soc                 ← agrOffer.Soc                        [Always]
        │
        ├── ns:parameterInfo (foreach agrOffer.ParameterInfo):
        │   name ← ParamName; values ← ValuesArray [cond]; soc ← parent Soc; effectiveDate/expirationDate [cond]
        │
        ├── ns:parameterInfo (foreach agrOffer.RelatedOffersArray.ParameterInfo):
        │   name ← ParamName; values ← ValuesArray [cond]; soc ← RelatedOffer.Soc; effectiveDate/expirationDate [cond]
        │
        ├── ns:parameterInfo (special "Agreement level offer instance ID")     [Conditional: SOC in stralSoc AND propValue=PLG/CAP]
        │   name ← "Agreement level offer instance ID"; soc ← matching RelatedOffer SOC
        │
        ├── ns:chargeDistributionDetailsInfo (foreach offers where RCIndicator != 64):
        │   soc ← offer.Soc [cond]; targetPayChannelId ← Account[RefId=$acctRefId].PayChannelId
        │   (acctRefId = Account[AgreementRefId == POU.Agreement.RefId].RefId)
        │
        └── ns:activityInfo
            ├── activityReason ← AgreementActivityInfo.ActivityReason → "CREQ"  [Always]
            ├── userText       ← AgreementActivityInfo.UserText                 [Always (empty if missing)]
            └── enclosedClientInfo → logicalDate ← agrOffer.EffectiveDate → tomorrow  [Conditional: LargeCustomerIndicator=89]
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_ADD_AGREEOFFER
├── [if resubmit] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── for each POU[i]:
│   ├── clear(alSOCs); clear(alPropVal)
│   │
│   ├── [Pass 1: SOC deduplication]
│   │   ├── for each POU.Agreement.Offers[p] where PreExecCheck passes (GetXMLForAgreementOffer):
│   │   │   └── for each RelatedOffersArray[q]: if SOC not in alSOCs:
│   │   │       alSOCs.add(soc); alPropVal.add(GetSplOffIndForSoc(orderRequest, soc))
│   │   └── for each ChildOU[u].Agreement.Offers[v] where PreExecCheck passes (GetXMLForAgreementOfferInChildOU):
│   │       └── for each RelatedOffersArray[w]: if SOC not in alSOCs:
│   │           alSOCs.add(soc); alPropVal.add(GetSplOffIndForSoc(orderRequest, soc))
│   ├── stralSoc = alSOCs.toArray(); stralPropVal = alPropVal.toArray()
│   │
│   ├── [Pass 2: POU offers]
│   │   ├── if POU.Agreement != null:
│   │   ├── [skip if Response[ReferenceId==Agreement.RefId AND CompletionStatus==2] exists]
│   │   ├── filter POU.Agreement.Offers → offersToAdd via PreExecCheck (GetXMLForAgreementOffer)
│   │   └── for each qualifying offer[iOffer]:
│   │       ├── Event.createEvent(CCBS_ADD_AGREEOFFER, POU XSLT)
│   │       ├── Event.assertEvent(agreeEvt)
│   │       ├── IntraActivitySequencing.ActionRequestEvent(agreeEvt, activity)
│   │       └── sendEventImmediate(Logger REQ — OPERATION_NAME="CCBS_ADD_AGREEOFFER")
│   │
│   └── [Pass 3: ChildOU offers]
│       └── for each ChildOU[x] where Agreement != null:
│           ├── [skip if Response[ReferenceId==ChildOU.Agreement.RefId AND CompletionStatus==2] exists]
│           ├── filter ChildOU.Agreement.Offers → offersToAdd via PreExecCheck
│           └── for each qualifying offer[iOffer]:
│               ├── Event.createEvent(CCBS_ADD_AGREEOFFER, ChildOU XSLT)
│               ├── Event.assertEvent(agreeEvt)
│               ├── IntraActivitySequencing.ActionRequestEvent(agreeEvt, activity)
│               └── sendEventImmediate(Logger REQ — OPERATION_NAME="CCBS_ADD_AGREEOFFER")
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
└── SendDataToDB(orderRequest)

Response_CCBS_ADD_AGREEOFFER
├── Instance.createInstance(CCBS_AddAgreeOfferRes: ResponseCode, ResponseMessage, CompletionStatus, ReferenceId)
│   → currActivity.Response[n] = activityRes
├── agree = Instance.getByExtIdByUri("AG:"+OMXTrackingId+":"+RefID, Agreement)
│   (fallback: "CAG:"+OMXTrackingId+":"+RefID)
├── iOffDetLen = count(eventResponse/payload/addOfferResponse/OfferDetails)
├── sPrefix = global OMX-OM/PoolingPooled/PooledPrefix (default "POOLED_OFFER_INSTANCE_ID")
├── sPooled = global OMX-OM/PoolingPooled/PooledIndicator (default "RPD,CPD")
├── for each OfferDetail[i]:
│   └── if BRMS.AnyIn(GetSplOffIndForSoc(orderRequest, soc), sPooled):
│       → agree.ExtendedInfo[] += AgreementExtendedInfo(Name="{sPrefix}_{soc}", Value=OfferInstanceCode)
├── sendEventImmediate(Logger RES — OPERATION_NAME="CCBS_ADD_AGREEOFFER")
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Per-offer fan-out: fan-in count depends on offer count, not OU count — high-volume orders generate many parallel requests | [MEDIUM] | Track per-offer responses; test with 10+ offers |
| Pooled offer write-back: Agreement lookup by "AG:/CAG:+OMXTrackingId+:+RefID" — tightly coupled to BE Working Memory key scheme | [MEDIUM] | Replace with explicit lookup in migration target storage |
| SOC deduplication in pass 1 may use different PreExecCheck context than pass 2 send | [MEDIUM] | Verify PreExecCheck context objects are consistent across both passes |
| LargeCustomerIndicator=89 hardcoded threshold for enclosedClientInfo | [LOW] | Make configurable in migration |
| chargeDistributionDetailsInfo: RCIndicator != 64 filter — meaning undocumented | [LOW] | Investigate CCBS constant; document in data dictionary |
| Tomorrow date calculation using tib:add-to-dateTime — timezone-sensitive | [LOW] | Use explicit timezone-aware date arithmetic in migration |

---

## §19 Response Message Rule

No per-offer field write-back to Agreement/Offer structures. Primary action is pooled offer instance ID write-back for RPD/CPD-type SOCs.

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | CCBS_AddAgreeOfferRes (ResponseCode, ResponseMsg, CompletionStatus, RefID) | Always |
| `agree.ExtendedInfo[]` | Name=`POOLED_OFFER_INSTANCE_ID_{soc}`, Value=`OfferDetails[i].OfferInstanceCode` | Only if SOC propValue in sPooled (RPD/CPD) |

Agreement lookup: `Instance.getByExtIdByUri("AG:"+OMXTrackingId+":"+RefID, ...)` or `"CAG:..."` fallback.

Global variables:
- `OMX-OM/PoolingPooled/PooledPrefix` (default: "POOLED_OFFER_INSTANCE_ID")
- `OMX-OM/PoolingPooled/PooledIndicator` (default: "RPD,CPD")

Fan-in: `IntraActivitySequencing.ActionResponseEvent(currActivity)` — returns "true" when all per-offer requests answered.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
