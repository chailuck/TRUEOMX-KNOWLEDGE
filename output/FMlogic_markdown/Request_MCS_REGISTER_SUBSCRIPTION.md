# Request_MCS_REGISTER_SUBSCRIPTION

> External OMXFM — MCS Media Content Subscription Registration · RegisterSubscriptionRequest schema

**Rule class:** `Rules.OMConsumers.OMXFM.Request.Request_MCS_REGISTER_SUBSCRIPTION`  
**Priority:** 5 | **forwardChain:** true | **Author:** Chayatorn Pan.  
**Backend:** MCS (Media Content Service) | **Integration:** JMS / Async

---

## §1 — Overview & Purpose

`MCS_REGISTER_SUBSCRIPTION` registers prepaid subscribers into the MCS (Media Content Service / MarketPlace) system. For each SubscriberOffer across ParentOU and ChildOU subscribers, it sends a `RegisterSubscriptionRequest` to MCS, carrying the pack code, subscriber identity (msisdn, subscriber_id, certificate_number), channel, language, and up to 8 optional `ns:extra` key-value pairs (tokens, promotion IDs, recurring SOC, MCS pack code, OTT discount).

| Property | Value |
|----------|-------|
| Rule class | `Rules.OMConsumers.OMXFM.Request.Request_MCS_REGISTER_SUBSCRIPTION` |
| Backend System | MCS (Media Content Service) |
| Integration type | JMS / Async |
| Request event | `Events.OMConsumers.OMXFM.Request.MCS_REGISTER_SUBSCRIPTION` |
| Response event | `Events.OMConsumers.OMXFM.Response.MCS_REGISTER_SUBSCRIPTION` |
| Schema | `ns:RegisterSubscriptionRequest` (RegisterSubscription.xsd) |
| Destination | `MCS_REGISTER_SUBSCRIPTION` on channel `/Channels/OMXFMConnectionRequest` |
| RefID | `subOff.OfferName` (offer name only — not a composite key) |
| Dispatch pattern | `Event.Ext.sendEventImmediate(reqEvent)` direct; RequestCount manually incremented |
| Audit log gate | `AllowWriteLog(orderRequest.OrderData.OrderType)` — order-type-dependent |
| Fan-in completion | `count(Response[last3ofResponseCode="000"]) == RequestCount` |
| Resubmit support | Yes — RequestCount not incremented when `isActResub=true` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule Name | `Request_MCS_REGISTER_SUBSCRIPTION` | External OMXFM request rule |
| Namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Priority | 5 | |
| forwardChain | true | |
| Author | Chayatorn Pan. | |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — Customer hierarchy, order-level ExtendedInfo (tokens, MCS correlation) |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — Response[], RequestCount, Status, Parameters |

> `nextAct` is fetched dynamically via `Instance.getByExtIdByUri` for PreExecCheck evaluation.

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Bind to current step |
| 2 | `orderCurrentActivity.ActivityID == "MCS_REGISTER_SUBSCRIPTION"` | Route to this rule |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "MCS_REGISTER_SUBSCRIPTION"` | Cross-check ProcessFlow state |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Ready to execute |

---

## §5 — Execution Flow Diagram

1. **Setup** — `isActResub = (RequestCount > 0 && IsOrderResubmitted)`. Fetch `nextAct` (for PreExecCheck). Read `USE_FE_RECURRING` parameter from current activity.
2. **ParentOU Subscriber Offers loop** — RefID = `subOff.OfferName`. Check reqSuccess guard (`ReferenceId == refId && CompletionStatus == 2`). Evaluate PreExecCheck via `GetXMLForSubscriberOfferFilterWithExtendedInfo`. If passed: collect all variables, build and `sendEventImmediate`; if `AllowWriteLog(OrderType)`: emit audit event. If `!isActResub`: `orderCurrentActivity.RequestCount++`.
3. **ChildOU Subscriber Offers loop** — Same logic for ChildOU subscribers (uses `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo`). Same RequestCount increment logic.
4. **Status branch** — If any sent: `GetActivityStatusString("1", false)` + `SendDataToDB(orderRequest)`. All skipped: `SkipActivity(orderRequest, orderCurrentActivity, "4")`.
5. **Exception** — `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §7 — Data Extraction & Key Variables

| Variable | Source | Notes |
|----------|--------|-------|
| `refId` | `subOff.OfferName` | Used as RefID for correlation — offer name only |
| `transaction_id` | `orderRequest.OrderData.OMXTrackingId` | Sent as `ns:transaction_id` |
| `method` | `orderRequest.OrderData.OMXTrackingId` | **Dead variable** — assigned but never passed; `ns:method` hardcoded "register" |
| `msisdn` | `subscriber.MSISDN` | Sent as `ns:msisdn` |
| `channel` | `orderRequest.OrderData.Channel` | Sent as `ns:channel` |
| `pack_code` | `subOff.OfferName` | Sent as `ns:pack_code` |
| `lang` | `subscriber.SubscriberGeneralInfo.Language` | Sent as `ns:lang` |
| `recurringSoc` | Conditional: USE_FE_RECURRING="Y" → any FE offer's RECURRING_SOC; else → current offer's RECURRING_SOC | Sent as extra[RECURRING_SOC] if non-empty |
| `mcsCorrelationId` | `orderRequest.OrderData.ExtendedInfo[MCS_CORRELATION_ID]/Value` | extra[MCS_CORRELATION_ID] |
| `flowId` | `subOff.ExtendedInfo[FLOW_ID]/Value` | extra[FLOW_ID] |
| `accessToken` | `orderRequest.OrderData.ExtendedInfo[AccessToken]/Value` | extra[ACCESS_TOKEN] |
| `refreshToken` | `orderRequest.OrderData.ExtendedInfo[RefreshToken]/Value` | extra[REFRESH_TOKEN] |
| `promotionId` | `orderRequest.OrderData.ExtendedInfo[PromotionID]/Value` | extra[PROMOTION_ID] |
| `mcs_packcode` | `subOff.ExtendedInfo[MCS_PACKCODE]/Value` | extra[MCS_PACKCODE] AND serviceType='69' only |
| `ott_discount_amount` | `subOff.ExtendedInfo[OTT_DISCOUNT_AMOUNT]/Value` | extra[OTT_DISCOUNT_AMOUNT] AND serviceType='80' only |
| `subIdCrm` | `MapSubscriberIdFromCRM(subscriber, USE_ROWID_CRM)` | Sent as `ns:subscriber_id` if non-empty |

### USE_FE_RECURRING — recurringSoc resolution logic

```xpath
if (USE_FE_RECURRING = "Y")
    // Read RECURRING_SOC from any FE offer on this subscriber (FE_OR_CCBS="FE")
    $subscriber/SubscriberOffers[ExtendedInfo[Name="FE_OR_CCBS" and Value="FE"]]/ExtendedInfo[Name="RECURRING_SOC"]/Value
else
    // Read RECURRING_SOC from the current offer being processed
    $subOff/ExtendedInfo[Name="RECURRING_SOC"]/Value
```

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event | Protocol | Purpose |
|-----------|-------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.MCS_REGISTER_SUBSCRIPTION` | JMS | Send RegisterSubscriptionRequest to MCS |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.MCS_REGISTER_SUBSCRIPTION` | JMS | Receive subscription registration result from MCS |

### §8.3 Backend API Details

| System | Operation | Schema | Correlation |
|--------|-----------|--------|-------------|
| MCS | RegisterSubscription | `ns:RegisterSubscriptionRequest` (RegisterSubscription.xsd) | RefID = `subOff.OfferName`; fan-in: RequestCount == count(000 responses) |

### §8.4 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `orderRequest.OrderData.Channel` | READ | ns:channel |
| `orderRequest.OrderData.OMXTrackingId` | READ | ns:transaction_id |
| `orderRequest.OrderData.ExtendedInfo[MCS_CORRELATION_ID, AccessToken, RefreshToken, PromotionID]` | READ | extra[] elements |
| `subscriber.MSISDN` | READ | ns:msisdn |
| `subscriber.SubscriberGeneralInfo.Language` | READ | ns:lang |
| `subscriber.SubscriberName.NameType / Identification` | READ | ns:certificate_number (INDY subscribers) |
| `subscriber.AccountRefId` | READ | Joined to Customer.Account[] for ns:account_id |
| `subscriber.SubscriberOffers[ServiceType='80']` | READ | ns:pp_code (existing prepaid plan) |
| `subscriber.SubscriberOffers[OfferName='RMVX00000000001']` | READ | ns:pp_expire_date from TR_ORIG_CONTRACT_EXPIRE_DATE parameter |
| `subOff.ExtendedInfo[FE_OR_CCBS, FLOW_ID, RECURRING_SOC, MCS_PACKCODE, OTT_DISCOUNT_AMOUNT]` | READ | Payload construction |
| `orderCurrentActivity.Response[]` | READ/WRITE | reqSuccess guard + appended by response RF |
| `orderCurrentActivity.RequestCount` | WRITE | Manually incremented (if !isActResub) |

### §8.5 Activity Parameters

| Parameter | Effect |
|-----------|--------|
| `USE_FE_RECURRING` | If "Y": read RECURRING_SOC from FE offer; else read from current offer |
| `USE_ROWID_CRM` | Controls `MapSubscriberIdFromCRM` — CRM row ID vs subscriber ID |

---

## §9 — Detailed Payload Build

### §9.4 Payload Structure — RegisterSubscriptionRequest

```xml
<ns:RegisterSubscriptionRequest
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/.../MCS/RegisterSubscription.xsd">

  <ns:transaction_id>OMXTrackingId</ns:transaction_id>
  <ns:method>register</ns:method>               <!-- Static — "register" -->
  <ns:msisdn>subscriber.MSISDN</ns:msisdn>
  <ns:subscriber_id>subIdCrm</ns:subscriber_id>   <!-- if subIdCrm != "" -->
  <ns:channel>orderData.Channel</ns:channel>
  <ns:pack_code>subOff.OfferName</ns:pack_code>
  <ns:lang>subscriber.Language</ns:lang>

  <!-- if NameType='INDY' AND Identification present -->
  <ns:certificate_number>SubscriberName.Identification</ns:certificate_number>

  <!-- if Account[AccountRefId]/AccountID present -->
  <ns:account_id>Customer.Account[AccountRefId].AccountID</ns:account_id>

  <!-- if subscriber has an offer with ServiceType='80' -->
  <ns:pp_code>SubscriberOffers[ServiceType='80'].OfferName</ns:pp_code>

  <!-- if subscriber has offer OfferName="RMVX00000000001" with TR_ORIG_CONTRACT_EXPIRE_DATE param -->
  <ns:pp_expire_date>SubscriberOffers["RMVX00000000001"].ParameterInfo[TR_ORIG_CONTRACT_EXPIRE_DATE].ValuesArray</ns:pp_expire_date>

  <!-- Extra key-value pairs (each conditional) -->
  <ns:extra><ns:key>RECURRING_SOC</ns:key><ns:value>recurringSoc</ns:value></ns:extra>
  <ns:extra><ns:key>MCS_CORRELATION_ID</ns:key><ns:value>mcsCorrelationId</ns:value></ns:extra>
  <ns:extra><ns:key>FLOW_ID</ns:key><ns:value>flowId</ns:value></ns:extra>
  <ns:extra><ns:key>ACCESS_TOKEN</ns:key><ns:value>accessToken</ns:value></ns:extra>
  <ns:extra><ns:key>REFRESH_TOKEN</ns:key><ns:value>refreshToken</ns:value></ns:extra>
  <ns:extra><ns:key>PROMOTION_ID</ns:key><ns:value>promotionId</ns:value></ns:extra>
  <ns:extra><ns:key>MCS_PACKCODE</ns:key><ns:value>mcs_packcode</ns:value></ns:extra>       <!-- AND serviceType='69' -->
  <ns:extra><ns:key>OTT_DISCOUNT_AMOUNT</ns:key><ns:value>ott_discount_amount</ns:value></ns:extra>  <!-- AND serviceType='80' -->
</ns:RegisterSubscriptionRequest>
```

---

## §10 — XSLT Field Mapping — Output XML Tree

```text
createEvent @extId ← OMXUtils:generateTrackingID() [inside XSLT]  [Always]
└── event
    ├── JMSPriority            ← $orderRequest/OrderPriority                      [Always]
    ├── JMSCorrelationID       ← $orderRequest/OrderData/OMXTrackingId            [Always]
    ├── OrderID                ← $orderRequest/OrderData/OrderID                  [Always]
    ├── RefID                  ← $refId (= subOff.OfferName)                      [Always]
    ├── OrderType              ← $orderRequest/OrderData/OrderType                [Always]
    └── payload
        └── ns:RegisterSubscriptionRequest
            ├── ns:transaction_id   ← $transaction_id (= OMXTrackingId)          [Always]
            ├── ns:method           ← "register"  (static literal)                [Always]
            ├── ns:msisdn           ← $msisdn                                    [Always]
            ├── ns:subscriber_id    ← $subIdCrm                                  [Conditional: subIdCrm != ""]
            ├── ns:channel          ← $channel (= orderData.Channel)             [Always]
            ├── ns:pack_code        ← $pack_code (= subOff.OfferName)            [Always]
            ├── ns:lang             ← $lang (subscriber.Language)                [Always]
            ├── ns:certificate_number ← SubscriberName/Identification            [Conditional: NameType='INDY' AND Identification present]
            ├── ns:account_id       ← Customer/Account[AccountRefId]/AccountID   [Conditional: AccountID present]
            ├── ns:pp_code          ← SubscriberOffers[ServiceType='80']/OfferName [Conditional: present]
            ├── ns:pp_expire_date   ← SubscriberOffers["RMVX00000000001"]/
            │                         ParameterInfo[TR_ORIG_CONTRACT_EXPIRE_DATE]/ValuesArray [Conditional: present]
            ├── ns:extra[RECURRING_SOC]        ← recurringSoc                   [Conditional: string-length > 0]
            ├── ns:extra[MCS_CORRELATION_ID]   ← mcsCorrelationId               [Conditional: string-length > 0]
            ├── ns:extra[FLOW_ID]              ← flowId                          [Conditional: string-length > 0]
            ├── ns:extra[ACCESS_TOKEN]         ← accessToken                     [Conditional: string-length > 0]
            ├── ns:extra[REFRESH_TOKEN]        ← refreshToken                    [Conditional: string-length > 0]
            ├── ns:extra[PROMOTION_ID]         ← promotionId                     [Conditional: string-length > 0]
            ├── ns:extra[MCS_PACKCODE]         ← mcs_packcode                   [Conditional: string-length > 0 AND serviceType='69']
            └── ns:extra[OTT_DISCOUNT_AMOUNT]  ← ott_discount_amount             [Conditional: string-length > 0 AND serviceType='80']
```

> **Note:** Unlike most OMXFM rules, the event `@extId` is set inside the XSLT via `OMXUtils:generateTrackingID()`, not assigned by the outer BE rule scope.

---

## §11 — Audit Logging

| Phase | AUDIT_TRACE | Gate |
|-------|-------------|------|
| Request sent (per offer) | `Request Sent for MCS_REGISTER_SUBSCRIPTION` | `AllowWriteLog(orderRequest.OrderData.OrderType)` — conditional by order type |
| Response received | `Response received for RefId <RefID>` (includes actual RefID) | Unconditional |

> Request audit logging is gated by `AllowWriteLog(OrderType)` — certain order types suppress request-side audit trails. This is distinct from other OMXFM rules which log unconditionally. The response audit trace uniquely includes the actual RefID value in the message text.

---

## §12 — Activity Status Management

| Condition | Status | Additional action |
|-----------|--------|-------------------|
| At least one request sent | `GetActivityStatusString("1", false)` | `SendDataToDB(orderRequest)` |
| No offers sent | [SKIPPED] | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception | Error state | `HandleActivityException` |

> **RequestCount increment:** This rule manually increments `orderCurrentActivity.RequestCount++` per offer, but only when `!isActResub`. Unlike rules using IntraActivitySequencing (SBM_ADD_3GPREPAID), there is no `SendFirstRequestEvent` call — each event is dispatched immediately via `sendEventImmediate`.

---

## §15 — Function Dependency Tree

```text
Request_MCS_REGISTER_SUBSCRIPTION (rule)
├── Instance.getByExtIdByUri(NextActivityName)                      [next activity PreExecCheck]
├── GetActivityParameterValueFromKey(..., "USE_FE_RECURRING")       [parameter read]
├── GetActivityParameterValueFromKey(..., "USE_ROWID_CRM")          [per offer]
├── (per offer loop — ParentOU)
│   ├── XPath.evalAsString()                                        [FE_OR_CCBS filter]
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo()            [PreExecCheck XML]
│   ├── XPath.execute()                                             [evaluate PreExecCheck]
│   ├── XPath.evalAsString() × 8                                   [recurringSoc, mcsCorrelationId, flowId, accessToken, refreshToken, promotionId, mcs_packcode, ott_discount_amount]
│   ├── MapSubscriberIdFromCRM(subscriber, USE_ROWID_CRM)           [subIdCrm]
│   ├── Event.createEvent(xslt://MCS_REGISTER_SUBSCRIPTION)         [build RegisterSubscriptionRequest]
│   ├── Event.Ext.sendEventImmediate(reqEvent)                      [dispatch JMS directly]
│   ├── AllowWriteLog(orderRequest.OrderData.OrderType)             [gate for audit log]
│   └── [if AllowWriteLog] Event.Ext.sendEventImmediate(Logger)    [audit event]
├── (per offer loop — ChildOU)  [same as ParentOU]
├── GetActivityStatusString("1", false)                             [IN_PROGRESS]
├── SendDataToDB(orderRequest)                                      [persist]
├── SkipActivity(orderRequest, orderCurrentActivity, "4")           [skip path]
└── HandleActivityException()                                       [error path]

Response_MCS_REGISTER_SUBSCRIPTION (rulefunction)
├── OMXUtils.generateTrackingID()                                   [extId]
├── Instance.createInstance(xslt://ResponseBase)                    [standard ResponseBase]
│   → ResponseCode, ResponseMessage, CompletionStatus, ReferenceId
├── currActivity.Response[length] = activityRes                     [append response]
├── Event.Ext.sendEventImmediate(Logger)                            [response audit (unconditional)]
└── XPath.evalAsInt("count(Response[last3='000'])")                 [fan-in count]
    → if RequestCount == successResponseCount → "true" else "false"
```

---

## §17 — Migration Notes & Recommendations

> **Dead variable — method (lines 65, 135):**  
> `String method = orderRequest.OrderData.OMXTrackingId` — assigned but never passed to XSLT;  
> `ns:method` is hardcoded as the static literal `'register'` in the XSLT.

> **Hardcoded offer name for pp_expire_date — "RMVX00000000001":**  
> The offer name is a magic string inside the XSLT template. If this contract SOC changes, the code must be updated.

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | One RegisterSubscriptionRequest per SubscriberOffer (ParentOU + ChildOU) | [HIGH] |
| R2 | RefID = subOff.OfferName (not composite) — preserve for response correlation | [HIGH] |
| R3 | 8 conditional ns:extra fields — all conditions must be evaluated per offer | [HIGH] |
| R4 | ns:certificate_number only for INDY NameType subscribers | [HIGH] |
| R5 | USE_FE_RECURRING="Y" → read RECURRING_SOC from FE offer, not current offer | [MEDIUM] |
| R6 | MCS_PACKCODE extra only when serviceType='69'; OTT_DISCOUNT_AMOUNT only when serviceType='80' | [MEDIUM] |
| R7 | Request audit log gated by AllowWriteLog(OrderType) — preserve this filter | [MEDIUM] |
| R8 | pp_expire_date from SubscriberOffers["RMVX00000000001"]/TR_ORIG_CONTRACT_EXPIRE_DATE — externalise magic SOC name | [LOW] |

---

## §19 — Response Message Rule

### §19.1 Overview

Standard `ResponseBase` concept mapped from the MCS response. Fan-in via `count(Response[last3 of ResponseCode == "000"]) == currActivity.RequestCount`. Response AUDIT_TRACE uniquely includes the actual RefID: `"Response received for RefId <RefID>"`.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order data (audit log context) |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.MCS_REGISTER_SUBSCRIPTION` | JMS response from MCS |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] array, RequestCount |

### §19.3 ResponseBase Concept Construction

```text
createObject @extId ← OMXUtils.generateTrackingID()                [Always]
└── ResponseBase concept
    ├── ResponseCode         ← $eventResponse/ResponseCode          [Conditional]
    ├── ResponseMessage      ← $eventResponse/ResponseMsg           [Conditional]
    ├── CompletionStatus     ← $eventResponse/CompletionStatus      [Conditional]
    └── ReferenceId          ← $eventResponse/RefID                 [Conditional]
```

### §19.4 Response Completion Logic

```java
int successResponseCount = XPath.evalAsInt(
  "count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = '000'])"
);
if(currActivity.RequestCount == successResponseCount) {
    return "true";   // All parallel MCS subscriptions registered → advance
} else {
    return "false";  // Still waiting
}
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
