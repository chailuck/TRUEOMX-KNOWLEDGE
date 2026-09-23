# Request_OMX_NOTI_TO_KAFKA

> Publishes a complete order-status notification to Kafka — a single request per invocation serializing the full OrderRequest snapshot into ns5:orderStatusNotification. Reused at steps 66 and 69 with different ProcessConfig Parameter keys for different Kafka routing headers.

**Backend:** Kafka (Order Status Notification) | **Pattern:** Single request (not per-offer) | **forwardChain:** true | **Used in steps:** 66, 69

---

## §1 — Overview & Purpose

Publishes one **Kafka order-status notification** per invocation. Unlike most OMXFM rules this is **not a per-offer fan-out** — it fires once, serializes the complete `OrderRequest`, and sends it as a single `ns5:orderStatusNotification` message. The same FM is reused at two workflow steps (66 and 69) with different `Parameter[1]` values that control the Kafka message header key/value for routing.

- **Pattern:** Single request — no SubscriberOffer loop; whole OrderRequest serialized once
- **PreExecCheck context:** `Instance.serializeUsingDefaults(orderRequest)` — full serialization
- **Parameter dispatch:** `Parameter[1]` parsed as `key=value` → `headerName`/`value` in event headers
- **Payload:** `ns5:orderStatusNotification` — 250+ fields covering Order, Customer, Account, Subscriber, Agreement, Product, contacts, billing, service, resource, MNP, and extended info
- **Response audit log:** OPERATION_NAME dynamically derived from step extId (different per step)
- **Debug traces:** `System.debugOut` × 5 in production rulefunction
- **Dead code:** Commented-out second `Event.createEvent` on line 39 (makes rule file 656KB)

> **[MEDIUM] 656KB rule file:** Caused by commented-out alternative XSLT blob on line 39. Should be removed.

> **[MEDIUM] Password in Kafka payload:** `ns5:password` field maps OrderData/Password into the notification — plaintext password sent to Kafka consumers. Review data sensitivity requirements.

> **[LOW] System.debugOut traces in production:** 5 debug trace statements remain in response rulefunction.

> **Step reuse pattern:** Steps 66 (OMX_NOTIFY_KNOX_EVENT) and 69 (OMX_NOTIFY_KNOX_EVENT_NOTIFY) use different Parameter[1] values. The audit log OPERATION_NAME is derived from the step extId, so each invocation logs its step identity correctly.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_OMX_NOTI_TO_KAFKA.rule` | 656KB — mainly dead XSLT blob |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_OMX_NOTI_TO_KAFKA.rulefunction` | 34 lines; 5 debug traces |
| Priority | 5 | |
| forwardChain | true | |
| Pattern | **Single request** — no offer loop | One dispatch per activity invocation |
| Backend event | `Events.OMConsumers.OMXFM.Request.OMX_NOTI_TO_KAFKA` | Dedicated Kafka notification event |
| Response event | `Events.OMConsumers.OMXFM.Response.OMX_NOTI_TO_KAFKA` | |
| Payload root | `ns5:orderStatusNotification` | Full order snapshot |
| Schema NS (ns5) | `http://services.omx.truecorp.co.th/OrderStatus` | |
| Schema NS (ns2) | `http://services.omx.truecorp.co.th/OrderStatusNotification` | |
| PreExecCheck context | `Instance.serializeUsingDefaults(orderRequest)` | Full OrderRequest (not offer-level) |
| Parameter dispatch | `Parameter[1]` → `tib:tokenize($param, "=")[1/2]` | headerName + value JMS headers |
| Used in steps | 66 (OMX_NOTIFY_KNOX_EVENT), 69 (OMX_NOTIFY_KNOX_EVENT_NOTIFY) | Same FM, different parameters |
| isActResub | `RequestCount > 0 && IsOrderResubmitted` | Suppresses RequestCount++ only |
| Response concept | `Concepts.FM.Base.ResponseBase` | extId pre-generated before XSLT |
| Fan-in | `RequestCount == successResponseCount` | Always 1 request |
| Dead code | Commented-out Event.createEvent line 39 | Previous XSLT version; causes 656KB file |
| Debug traces | `System.debugOut` × 5 | Should be removed |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_NOTI_TO_KAFKA"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_NOTI_TO_KAFKA"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §4 — Parameter Dispatch (ProcessConfig Parameter[1])

| Variable | XPath | Maps to |
|----------|-------|---------|
| `param` | `$orderCurrentActivity/Parameter[1]` | Raw key=value string from ProcessConfig |
| `paramKey` | `tib:tokenize($param, "=")[1]` | `headerName` in event — Kafka routing header name |
| `paramValue` | `tib:tokenize($param, "=")[2]` | `value` in event — Kafka routing header value |

> Steps 66 and 69 each have a different Parameter[1] in the ProcessConfig XML, routing to different Kafka destinations. `tib:tokenize("=")[2]` truncates if value part contains "=".

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

The payload is a complete order snapshot (250+ fields). Top-level structure shown; full mapping omitted for brevity.

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                     [Always] no xsl:if guard
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId           [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                 [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType               [Always]
    ├── headerName           ← $paramKey (from Parameter[1] key part)          [Always] Kafka routing key
    ├── value                ← $paramValue (from Parameter[1] value part)      [Always] Kafka routing value
    └── payload
        └── ns5:orderStatusNotification  (ns5=http://services.omx.truecorp.co.th/OrderStatus)
            ├── ns5:OMXTrackingID        ← OMXTrackingId                       [Always]
            ├── ns5:Order                ← channel, orderId, orderType, FileID,
            │                              creditLimitApproveCode, irApproveCode, maxAllowApproveCode,
            │                              effectiveDate, operatorId, dealerCode, IntegrationMethod,
            │                              user, password(!), MNPInfo, OrderStatus, ProfileStatus,
            │                              NetworkStatus, saleChannel, saleId, saleName…
            ├── ns5:Customer             ← customerId, customerCrmId, customerType, identification,
            │                              name fields, contacts, credit, billing, address…
            ├── ns5:Account              ← accountId, accountRefId, billingAccount, billingAddress…
            ├── ns5:OU                   ← ouId, ouName, agreements, products, offers…
            ├── ns5:subscriber           ← subscriberId, subscriberNumber, subscriberType,
            │                              subscriberGeneralInfo, subscriberAddress,
            │                              resourceInfo, offers (offerName/soc/offerInstanceId/
            │                              offerParameterInfo/ExtendedInfo)…
            ├── ns5:Agreement            ← agreementId, agreementType, discountList…
            ├── ns5:Product/ProductList  ← productId, productCode, productName, service, attrList…
            ├── ns5:SaleInfo             ← saleId, saleName, storeId, branchCode, branchName…
            ├── ns5:ReasonInfo           ← reasonCode, reasonDesc, activityReason…
            ├── ns5:ExtendedInfo         ← key/value extended info pairs
            ├── ns5:ChangeInfoList       ← change tracking
            ├── ns5:ResponseCode / ns5:ResponseMsg
            └── ns5:activityInfo         ← processing metadata
```

---

## §8 — System & Integration Dependencies

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | Kafka (via OMX ESB) |
| Operation | Order status notification publish |
| Payload schema NS (ns5) | `http://services.omx.truecorp.co.th/OrderStatus` |
| Outer NS (ns2) | `http://services.omx.truecorp.co.th/OrderStatusNotification` |
| Routing | Kafka topic/header controlled by ProcessConfig Parameter[1] key=value |
| Step 66 purpose | Knox event notification (OMX_NOTIFY_KNOX_EVENT) |
| Step 69 purpose | Knox notify event (OMX_NOTIFY_KNOX_EVENT_NOTIFY) |

---

## §15 — Function Dependency Tree

```text
Request_OMX_NOTI_TO_KAFKA (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── [if PreExecCheck]:
│   ├── sXML = Instance.serializeUsingDefaults(orderRequest)   ← full OrderRequest
│   └── chkRes = XPath.execute(PreExecCheck, sXML)
├── [if chkRes == "true"]:
│   ├── param      = XPath(orderCurrentActivity/Parameter[1])
│   ├── paramKey   = tib:tokenize(param, "=")[1]
│   ├── paramValue = tib:tokenize(param, "=")[2]
│   ├── Event.createEvent(OMX_NOTI_TO_KAFKA, XSLT: ns5:orderStatusNotification)
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   ├── [if !isActResub]: RequestCount++
│   ├── Event.Ext.sendEventImmediate(Logger)
│   ├── Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch]: HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_OMX_NOTI_TO_KAFKA (rulefunction)
├── System.debugOut × 5                                        ← [LOW] debug traces
├── extId = OMXUtils.generateTrackingID()                      ← pre-generated, passed to XSLT
├── activityRes = Instance.createInstance(ResponseBase) {extId=$extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId}
├── currActivity.Response[] ← activityRes
├── Event.Ext.sendEventImmediate(Logger:
│       OPERATION_NAME=tib:substring-after-last(currActivity@extId, ":"))
│       ← step 66 → "OMX_NOTIFY_KNOX_EVENT"
│       ← step 69 → "OMX_NOTIFY_KNOX_EVENT_NOTIFY"
├── successResponseCount = count(Response[tib:right(tib:trim(ResponseCode),3)="000"])
└── return (RequestCount == successResponseCount) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Single Kafka notification per invocation (not per offer). Full OrderRequest snapshot sent. |
| R2 | ProcessConfig Parameter[1] parsed as `key=value`; key → `headerName`, value → `value` in event. Controls Kafka routing. |
| R3 | PreExecCheck evaluated against `Instance.serializeUsingDefaults(orderRequest)` — full OrderRequest context. |
| R4 | Payload: `ns5:orderStatusNotification` (250+ fields) — comprehensive order snapshot. |
| R5 | Response OPERATION_NAME dynamic: `tib:substring-after-last(currActivity@extId, ":")` — different per step. |
| R6 | Fan-in: RequestCount == successResponseCount. Always 1 request. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| 656KB rule file due to commented-out dead XSLT (line 39) | [MEDIUM] | Remove commented-out Event.createEvent block |
| Password field in ns5:orderStatusNotification Kafka payload | [MEDIUM] | Review data sensitivity; mask or omit if consumers don't need it |
| System.debugOut × 5 in production rulefunction | [LOW] | Remove all debugOut calls |
| paramValue truncated if value contains "=" character | [LOW] | Use substringAfter("=") instead of tokenize()[2] for paramValue |
| Resubmit re-publishes notification — consumers must be idempotent | [LOW] | Confirm Kafka consumers handle duplicates |

---

## §19 — Response Message Rule (Response_OMX_NOTI_TO_KAFKA)

### §19.1 Notable Differences

- `extId` is pre-generated via `OMXUtils.generateTrackingID()` before the XSLT call (passed as `$extId` param, not via `OMXUtils:generateTrackingID()` inside XSLT)
- OPERATION_NAME in audit log = `tib:substring-after-last(currActivity@extId, ":")` — dynamic per step
- 5 `System.debugOut` debug traces remain in code

### §19.3 ResponseBase Construction

| Field | Source | Note |
|-------|--------|------|
| extId | `$extId` (pre-computed) | Passed as XSLT param — not inline OMXUtils call |
| ResponseCode | `$eventResponse/ResponseCode` | Conditional |
| ResponseMessage | `$eventResponse/ResponseMsg` | Conditional; Msg→Message rename |
| CompletionStatus | `$eventResponse/CompletionStatus` | Conditional |
| ReferenceId | `$eventResponse/RefID` | Conditional |

### §19.4 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` — always 1 vs 1 |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
