# Request_OMX_SAVE_PARTIAL_ORDER

## §1 Overview & Purpose

**OMX_SAVE_PARTIAL_ORDER** persists the full subscriber order snapshot to the OMX partial order store. It is the richest payload in the ACTIVATION flow — serialising customer info, subscriber offers, resources, and all ExtendedInfo collections from five different order scopes.

> **Mandatory parameter guard:** `Parameter@length == 0` → throw `DATA_ISSUE`. Both ACTION and STATUS must be present in ProcessConfig.

> **Dual operation:** `ACTION="SAVE"` creates a new partial order; other values (e.g. `"UPDATE"`) update an existing one. OPERATION_NAME in audit log switches accordingly.

> **Fire-and-forget per Subscriber:** `Event.Ext.sendEventImmediate` + `RequestCount++`. Iterates POU and ChildOU Subscribers. Fan-in: `count("000") == RequestCount`.

> **Five ExtInfo scopes:** order, customer, account (subscriber's AccountRefId), agreement (POU or ChildOU agreement), subscriber.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_SAVE_PARTIAL_ORDER` |
| Author | Chayatorn P. |
| Priority | 5 |
| forwardChain | true |
| Backend | OMX Partial Order Service |
| Event type (Request) | `Events.OMConsumers.OMXFM.Request.OMX_SAVE_PARTIAL_ORDER` |
| Event type (Response) | `Events.OMConsumers.OMXFM.Response.OMX_SAVE_PARTIAL_ORDER` |
| Send pattern | `Event.Ext.sendEventImmediate(reqEvent)` — FIRE-AND-FORGET per Subscriber |
| RequestCount | Manually: `if(!isActResub) RequestCount++` |
| Fan-in | `count(Response[ResponseCode suffix "000"]) == RequestCount` |
| Parameters | ACTION (SAVE \| UPDATE), STATUS (optional) |
| Mandatory guard | `Parameter@length == 0` → throw DATA_ISSUE |
| Iteration | POU[].Subscriber[] AND ChildOU[].Subscriber[] |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| SAVE vs UPDATE action | Same XSLT for both; OPERATION_NAME in Logger switches on actionParam |
| status conditional | `ns:status` emitted only if `statusParam != ""` |
| Five ExtInfo scopes | orderExtendedInfo, customerExtendedInfo, accountExtendedInfo, agreementExtendedInfo, subscriberExtendedInfo |
| Account ExtInfo filter | `Account[RefId=$subscriber/AccountRefId]/ExtendedInfo` |
| Agreement index offset | XSLT uses `ParentOU[number($i) + 1]` (1-indexed) to match 0-indexed BE loop variable |
| SubscriberOffer deep serialisation | RelatedOffersArray (Soc, ParameterInfo, MatSerialRefId), ParameterInfo, ExtendedInfo per offer |
| identificationExpDate commented out | Two date-formatting blocks commented out — raw BE DateTime value is included instead |
| PreExecCheck scoped | POU: `GetXMLForSubscriber`; ChildOU: `GetXMLForSubscriberInChildOU` |

---

## §10 XSLT Field Mapping (summary — richest payload)

```text
createEvent → event
├── extId/JMSPriority/JMSCorrelationID/OrderID/RefID/OrderType ← standard
└── payload → ns:SubmitOrderRequest
    ├── ns:partialOrderId   ← ExtInfo[PARTIAL_ORDER_ID].Value         [Always]
    ├── ns:status           ← $statusParam                            [Conditional: statusParam != ""]
    ├── ns:orderId          ← OrderData.OrderID                       [Conditional]
    ├── ns:channel          ← OrderData.Channel                       [Always]
    ├── ns:serviceId        ← subscriber.MSISDN                       [Always]
    ├── ns:identification   ← Customer.CustomerName.Identification     [Conditional]
    ├── ns:identificationType ← Customer.CustomerName.IdentificationType [Conditional]
    ├── ns:dealerCode       ← OrderData.DealerCode                    [Conditional]
    ├── ns:saleId           ← subscriber.SubscriberGeneralInfo.saleId [Conditional]
    ├── ns:language         ← subscriber.SubscriberGeneralInfo.Language [Conditional]
    ├── ns:customerInfo
    │   └── email/title/firstname/lastname/customerType/birthdate/identificationExpDate
    │       prefContactNumber/gender/subscriberType (all conditional)
    ├── ns:subscriberOffer [for-each subscriber.SubscriberOffers]
    │   ├── offerName/serviceType
    │   ├── relatedOffersArray [for-each RelatedOffersArray]
    │   │   ├── offerName/serviceType/soc/matSerialRefId
    │   │   └── parameterInfo [for-each ParameterInfo]: paramName + valuesArray
    │   ├── offerParameterInfo [for-each ParameterInfo]: paramName + valuesArray
    │   └── extendedInfo [for-each ExtendedInfo]: name + value
    ├── ns:subscriberResource [for-each ResourceInfo]: resourceName + valuesArray
    ├── ns:orderExtendedInfo [for-each OrderData.ExtendedInfo]: name + value
    ├── ns:customerExtendedInfo [for-each Customer.ExtendedInfo]: name + value
    ├── ns:accountExtendedInfo [Account[RefId=subscriber.AccountRefId].ExtendedInfo]: name + value
    ├── ns:agreementExtendedInfo [POU or ChildOU Agreement.ExtendedInfo]: name + value
    ├── ns:subscriberExtendedInfo [subscriber.ExtendedInfo]: name + value
    └── ns:action           ← $actionParam (SAVE | UPDATE)            [Always]
```

---

## §15 Function Dependency Tree

```text
Request_OMX_SAVE_PARTIAL_ORDER
├── if Parameter@length == 0: throw DATA_ISSUE
├── actionParam = GetActivityParameterValueFromKey("ACTION")
├── statusParam = GetActivityParameterValueFromKey("STATUS")
├── for each POU[i].Subscriber[j]:
│   ├── [PreExecCheck] GetXMLForSubscriber → chkRes
│   └── if chkRes=="true":
│       ├── check Response[refId AND CompletionStatus==2] → reqSuccess
│       └── if !reqSuccess:
│           ├── createEvent(OMX_SAVE_PARTIAL_ORDER, POU XSLT) + sendEventImmediate
│           ├── isSkipped = false
│           ├── if(!isActResub): RequestCount++
│           └── Logger REQ
├── for each POU[i].ChildOU[k].Subscriber[j]:
│   └── [same pattern — ChildOU Agreement ExtInfo path]
├── if !isSkipped: GetActivityStatusString("1") + SendDataToDB
└── else: SkipActivity("4")

Response_OMX_SAVE_PARTIAL_ORDER
├── createInstance(ResponseBase std 4) → currActivity.Response[n]
├── currActivity.ResponseCode/ResponseMessage = eventResponse.*
├── actionParam = GetActivityParameterValueFromKey(currActivity, "ACTION")
├── Logger RES (OPERATION_NAME: SAVE→OMX_SAVE_PARTIAL_ORDER; else→OMX_UPDATE_PARTIAL_ORDER)
└── count("000") == RequestCount → "true"/"false"
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| All five ExtInfo collections serialised per subscriber — large payloads | [MEDIUM] | Filter ExtInfo by relevance; evaluate partial order service payload size limits |
| identificationExpDate included as raw BE DateTime — format may differ from service expectation | [MEDIUM] | Restore commented-out formatting; confirm OMX service date format |
| Agreement ExtInfo index uses `number($i)+1` XSLT offset — mismatch risk if loop bounds change | [LOW] | Document 0-to-1 index conversion; add integration test for multi-POU orders |
| Last FM in ACTIVATION flow — missing subscriber coverage undetected until downstream | [LOW] | Add post-completion validation for partial order coverage |

---

## §19 Response Message Rule

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | ResponseBase (std 4) | Always |
| `currActivity.ResponseCode` | `eventResponse.ResponseCode` | Always |
| `currActivity.ResponseMessage` | `eventResponse.ResponseMsg` | Always |

No write-back to order data. Fan-in: `count(Response[ResponseCode suffix "000"]) == RequestCount`.

Response logger OPERATION_NAME: `actionParam=="SAVE"` → `"OMX_SAVE_PARTIAL_ORDER"`; else → `"OMX_UPDATE_PARTIAL_ORDER"`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
