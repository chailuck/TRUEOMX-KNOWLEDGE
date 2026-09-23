# Request_ATS_REGISTER_CAMPAIGN

## §1 Overview & Purpose

**ATS_REGISTER_CAMPAIGN** registers the order's campaign in ATS by sending `submitCampaignReq` with `requestName="RegisterCampaign"`. It aggregates ALL subscribers (POU + ChildOU) into a single list and sends them as `productList` entries.

> **Fire-and-forget:** `Event.Ext.sendEventImmediate` + manual `RequestCount++`. Fan-in: `count("000") == RequestCount`.

> **OrderType=12002 branching:** OT=12002 uses subscriber-level name/identification; `convergenceType` from ExtInfo, `state="Installing"`, `paymentType="Prepaid"`, `familyType="MAIN"`. Non-12002: customer-level name, `convergenceType="SpecialBundle"`, `state="Active"`, `paymentType="Postpaid"`.

> **Response write-back:** `OrderData.ExtendedInfo[Name="TRUELIFE_ID"]` ← `submitCampaignRes.truelifeId`. Consumed by FM29 (groupName) and FM30.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_ATS_REGISTER_CAMPAIGN` |
| Author | DESKTOP-995HR2V |
| Priority | 5 |
| forwardChain | true |
| Backend | ATS |
| Event type | `Events.OMConsumers.OMXFM.Request.ATS_SUBMIT_CAMPAIGN` |
| Send pattern | `Event.Ext.sendEventImmediate(reqEvent)` — FIRE-AND-FORGET |
| RequestCount | `if(!isActResub) RequestCount++` |
| Fan-in | `count(Response[ResponseCode suffix "000"]) == RequestCount` |
| Payload operation | `ns2:submitCampaignReq` with `requestName="RegisterCampaign"` |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| Subscriber aggregation | ArrayList collects all Subscribers from POU[].Subscriber[] + ChildOU[].Subscriber[]. One request covers all. |
| OT=12002 dispatch | OT=12002: subscriber-level fields, "Installing" state, "Prepaid" payment. Else: customer-level, "Active" state, "Postpaid". |
| convergenceType | OT=12002 → ExtInfo[CONVERGENCE_TYPE]; else → "SpecialBundle" |
| companyCode | OT=12002 → SubscriberType; else → Account.CompanyCode || fallback "RM" |
| TOL_FAMILY_PLUS | Extra productList if non-empty: productType="TOL", companyCode="TI", paymentType="Internet" |
| GROUP extra entry | Extra productList if non-empty: PRODUCT_ID/COMPANY_CODE/FAMILY_TYPE extracted from pipe-delimited GROUP ExtInfo |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority/JMSCorrelationID/OrderID/RefID ← standard fields
├── UserName/PassWord                           ← [Credential-gated]
├── OrderType                                   ← OrderData.OrderType
└── payload → ns2:submitCampaignReq
    ├── channel         ← "OMX"                 [Hardcoded]
    ├── requestName     ← "RegisterCampaign"    [Hardcoded]
    ├── applyChannel    ← Channel               [Conditional]
    ├── dealerId        ← DealerCode            [Conditional]
    └── campaignInfo
        ├── campaignCode← ExtInfo[CAMPAIGN_CODE].Value
        ├── convergenceType ← OT=12002→ExtInfo[CONVERGENCE_TYPE]; else→"SpecialBundle"
        ├── title/firstName/lastName/identification ← OT=12002→subscribers[1] / else→Customer
        ├── state       ← OT=12002→"Installing"; else→"Active"
        ├── productList [for-each subscribers]
        │   ├── productId   ← MSISDN            [Conditional]
        │   ├── productType ← "TMV"             [Hardcoded]
        │   ├── paymentType ← OT=12002→"Prepaid"; else→"Postpaid"
        │   ├── companyCode ← OT=12002→SubscriberType; else→Account.CompanyCode||"RM"
        │   ├── productState← "Active"          [Hardcoded]
        │   ├── productStateDate ← current-dateTime()
        │   ├── familyType  ← "MAIN"            [Only if OT=12002]
        │   └── productSeq  ← position()
        ├── productList [if TOL_FAMILY_PLUS exists]
        │   productType="TOL", paymentType="Internet", companyCode="TI"
        └── productList [if GROUP exists]
            PRODUCT_ID/COMPANY_CODE/FAMILY_TYPE from pipe-delimited GROUP ExtInfo
```

---

## §15 Function Dependency Tree

```text
Request_ATS_REGISTER_CAMPAIGN
├── createArrayList() → subscriberList
├── for each POU.Subscriber: add(subscriberList, psub)
├── for each POU.ChildOU.Subscriber: add(subscriberList, csub)
├── subscriberArray = toArray(subscriberList); Subscriber[] typed copy
├── createEvent(ATS_SUBMIT_CAMPAIGN, XSLT)
├── sendEventImmediate(reqEvent)  ← FIRE-AND-FORGET
├── if(!isActResub): RequestCount++
├── sendEventImmediate(Logger REQ)
└── SkipActivity("4") if PreExecCheck false

Response_ATS_REGISTER_CAMPAIGN
├── createInstance(ResponseBase std 4) → currActivity.Response[n]
├── createInstance(OrderDataExtendedInfo: TRUELIFE_ID=submitCampaignRes.truelifeId)
│   → orderRequest.OrderData.ExtendedInfo[n]
├── Logger RES
└── count("000") == RequestCount → "true"/"false"
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| GROUP ExtInfo uses nested substring-before/after — brittle format | [MEDIUM] | Replace with structured object |
| TRUELIFE_ID write-back required by FM29/FM30 — implicit FM ordering | [MEDIUM] | Document and validate ProcessConfig sequence |
| subscribers[1] for OT=12002 name fields — assumes non-empty list | [LOW] | Add empty-list guard |
| companyCode fallback "RM" hardcoded | [LOW] | Externalise to global variable |

---

## §19 Response Message Rule

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | ResponseBase (std 4) | Always |
| `OrderData.ExtendedInfo[TRUELIFE_ID].Value` | `submitCampaignRes.truelifeId` | Conditional |

Fan-in: `count(Response[ResponseCode suffix "000"]) == RequestCount`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
