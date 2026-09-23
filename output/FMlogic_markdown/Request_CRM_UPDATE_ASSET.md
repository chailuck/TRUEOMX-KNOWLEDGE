# Request_CRM_UPDATE_ASSET

## §1 Overview & Purpose

**CRM_UPDATE_ASSET** registers each subscriber as an asset in the CRM system with KYC/identity verification data. Sends `ns:updateAssetRequest` with customer/subscriber identity, asset details, and optional parentCustomer (guardian) data.

> **IntraActivitySequencing pattern:** `Event.assertEvent(reqEvent)` + `ActionRequestEvent(reqEvent, currActivity)` + `SendFirstRequestEvent(currActivity)`. Fan-in: `ActionResponseEvent(currActivity)` returns true/false.

> **POU Subscribers only** — no ChildOU iteration.

> **OrderType=1 TrueFamily skip:** If OT="1" AND campaignCode=="TrueFamily" AND subscriber has no FE ResourceInfo → subscriber silently skipped.

> **CustomerAccount dispatch by OrderType:** OT=1/66 → customer-level identity; OT=34/52 → subscriber-level identity.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CRM_UPDATE_ASSET` |
| Author | DESKTOP-HINKNF3 |
| Priority | 5 |
| forwardChain | true |
| Backend | CRM |
| Event type (Request) | `Events.OMConsumers.OMXFM.Request.CRM_UPDATE_ASSET` |
| Event type (Response) | `Events.OMConsumers.OMXFM.Response.CRM_UPDATE_ASSET` |
| Send pattern | `Event.assertEvent + ActionRequestEvent + SendFirstRequestEvent` — INTRA-ACTIVITY SEQUENCING |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` → true/false |
| Iteration | POU[].Subscriber[] only (no ChildOU) |
| Resubmit | `PurgePendingRequestsBeforeResubmit` + CompletionStatus==2 skip |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| CustomerType→type | CustomerTypeInfo.Type==80 → `"Prepay"`; else → `"Postpay"` |
| BirthDate formatting | `DateTime.translateTime(BirthDate, "Asia/Bangkok")` → `DateTime.format("yyyy-MM-dd")` |
| OT=1 TrueFamily skip | If OT="1" AND campaignCode=="TrueFamily" AND no FE ResourceInfo → `continue` silently |
| OrderType customerAccount dispatch | OT=1/66: Customer-level. OT=34/52: Subscriber-level (POU[i+1]/Subscriber[j+1]) |
| OT=34 dummyMsisdn | `dummyMsisdn` + `dummyMsisdnFlag="true"` instead of `serviceId` |
| ParentCustomer section | Emitted only if `Customer.OtherAddress` exists; reads PARENT_FIRSTNAME/LASTNAME/ID/CONTACT from ExtInfo |
| title default fallback | If Title empty → `"คุณ"` (Thai honorific) |
| PreExecCheck | `Instance.serializeUsingDefaults(orderRequest)` — full order XML serialisation |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── extId           ← OMXUtils:generateTrackingID()                    [Always]
├── JMSPriority     ← $orderRequest/OrderPriority                      [Always]
├── JMSCorrelationID← $orderRequest/OrderData/OMXTrackingId            [Always]
├── OrderID         ← $orderRequest/OrderData/OrderID                  [Always]
├── RefID           ← $refId (subscriber.RefId)                        [Always]
├── OrderType       ← $orderRequest/OrderData/OrderType                [Always]
└── payload → ns:updateAssetRequest
    ├── ns:transactionId ← OMXTrackingId                              [Always]
    ├── ns:customerAccount [OrderType dispatch]
    │   ├── OT=1 or OT=66:
    │   │   idType/idNumber ← Customer.CustomerGeneralInfo.Identification*
    │   │   title ← Title || "คุณ" (fallback)
    │   │   firstName/lastName/gender ← Customer.CustomerName.*
    │   │   birthDate ← $birthDate (formatted "yyyy-MM-dd")
    │   │   ccbsCustId ← Customer.CustomerId
    │   │   address ← Customer.CustomerAddress.*
    │   └── OT=34 or OT=52:
    │       idType/idNumber ← Subscriber.SubscriberName.Identification*
    │       title/firstName/lastName/gender ← Subscriber.SubscriberName.*
    │       birthDate ← $birthDate; ccbsCustId ← Customer.CustomerId
    │       address ← Subscriber.SubscriberAddress.*
    ├── ns:asset
    │   ├── ns:serviceId        ← Subscriber.MSISDN                   [if OT != "34"]
    │   ├── ns:dummyMsisdn      ← Subscriber.MSISDN                   [if OT == "34"]
    │   ├── ns:dummyMsisdnFlag  ← "true"                              [if OT == "34"]
    │   ├── ns:productType      ← $type (Prepay | Postpay)            [Always]
    │   ├── ns:subscriberNo     ← Subscriber.SubscriberId             [Always]
    │   ├── ns:dealerCode       ← OrderData.DealerCode                [Always]
    │   ├── ns:channelOrder     ← ExtInfo[ORG_CHANNEL].Value          [Always]
    │   ├── ns:verifyMethod     ← ExtInfo[VERIFY_METHOD].Value        [Always]
    │   ├── ns:verifyResult     ← ExtInfo[VERIFY_RESULT].Value        [Always]
    │   ├── ns:kycData          ← ExtInfo[KYC_DATA].Value             [Always]
    │   ├── ns:transDocID       ← ExtInfo[TRANSACTION_DOC_ID].Value   [Always]
    │   ├── ns:issueDate        ← ExtInfo[ID_ISSUE_DATE].Value        [Always]
    │   ├── ns:expireDate       ← ExtInfo[ID_EXPIRE_DATE].Value       [Always]
    │   └── ns:isCardReader     ← ExtInfo[ID_FROM_CARD_READER].Value  [Always]
    └── ns:parentCustomer  [Conditional: Customer.OtherAddress exists]
        ├── firstName/lastName ← ExtInfo[PARENT_FIRSTNAME/PARENT_LASTNAME]
        ├── idType ← "Thai Id" (hardcoded)
        ├── idNumber ← ExtInfo[PARENT_ID]
        ├── contactPhoneType ← "Mobile" (hardcoded)
        ├── contactPhone ← ExtInfo[PARENT_CONTACT]
        └── address ← Customer.OtherAddress.*
```

---

## §15 Function Dependency Tree

```text
Request_CRM_UPDATE_ASSET
├── if isActResub: PurgePendingRequestsBeforeResubmit
├── for each POU[i].Subscriber[j]:
│   ├── check CompletionStatus==2 skip → reqSuccess
│   ├── [PreExecCheck] Instance.serializeUsingDefaults(orderRequest) → chkRes
│   └── if chkRes=="true" AND !reqSuccess:
│       ├── [OT=1 TrueFamily check] if TrueFamily AND no FE ResourceInfo → continue
│       ├── CustomerType==80 → type="Prepay"; else → type="Postpay"
│       ├── BirthDate → translateTime(Asia/Bangkok) → format("yyyy-MM-dd") → birthDate
│       ├── Event.createEvent(CRM_UPDATE_ASSET, XSLT) → reqEvent
│       ├── Event.assertEvent(reqEvent)
│       ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, currActivity)
│       └── Logger REQ
├── if !isSkipped:
│   ├── IntraActivitySequencing.SendFirstRequestEvent(currActivity)
│   ├── GetActivityStatusString("1")
│   └── SendDataToDB
└── else: SkipActivity("4")

Response_CRM_UPDATE_ASSET
├── createInstance(ResponseBase std 4, extId from event@extId) → currActivity.Response[n]
├── currActivity.ResponseCode/ResponseMessage = eventResponse.*
├── assetId = XPath(eventResponse/payload/updateAssetResponse/asset/assetId)
├── dummyMsisdnFlag = XPath(eventResponse/payload/updateAssetResponse/asset/dummyMsisdnFlag)
├── Logger RES
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| OT=1 TrueFamily silent skip — subscribers excluded without warning | [MEDIUM] | Document skip condition; add audit log entry when subscriber is skipped |
| Full order XML serialised for PreExecCheck — expensive for large orders | [MEDIUM] | Review PreExecCheck; consider subscriber-scoped XML if possible |
| assetId/dummyMsisdnFlag extracted but not written back to order data | [LOW] | Clarify whether assetId needs to be persisted; add write-back if required |
| title fallback "คุณ" hardcoded — may be wrong for corporate accounts | [LOW] | Externalise fallback or add OT/customerType conditional |
| ChildOU subscribers NOT processed — CRM asset registration POU only | [LOW] | Verify CRM scope with business; document exclusion of ChildOU |

---

## §19 Response Message Rule

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | ResponseBase (std 4) | Always |
| `currActivity.ResponseCode` | `eventResponse.ResponseCode` | Always |
| `currActivity.ResponseMessage` | `eventResponse.ResponseMsg` | Always |
| `assetId` (local var only) | `eventResponse/payload/updateAssetResponse/asset/assetId` | Read but not written to order |
| `dummyMsisdnFlag` (local var only) | `eventResponse/payload/updateAssetResponse/asset/dummyMsisdnFlag` | Read but not written to order |

Fan-in: `IntraActivitySequencing.ActionResponseEvent(currActivity)` — driven by sequence tracker, not RequestCount comparison.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
