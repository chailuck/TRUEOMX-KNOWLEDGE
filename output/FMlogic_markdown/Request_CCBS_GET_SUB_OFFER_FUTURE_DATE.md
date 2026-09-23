# Request_CCBS_GET_SUB_OFFER_FUTURE_DATE

## §1 Overview & Purpose

Queries CCBS for `getFutureRequestOfferDate` per subscriber. The response contains a list of `UpdateService` entries (Soc, OfferInstanceId, EffectiveDate, ExpirationDate). The response handler writes these dates back to matching `SubscriberOffers` in working memory — only if the existing date is empty/blank.

Uses **fire-and-forget pattern** (`Event.Ext.sendEventImmediate` + `RequestCount++`). Response always returns `"true"` — no fan-in check.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_SUB_OFFER_FUTURE_DATE` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | CCBS_GET_SUB_OFFER_FUTURE_DATE |
| Backend | CCBS — getFutureRequestOfferDate |
| Pattern | Fire-and-Forget (`sendEventImmediate` + `RequestCount++`) |
| Iteration Scope | ParentOU.Subscriber + ChildOU.Subscriber |
| Response Concept | `Concepts.FM.Response.CCBS_GetFutureRequestOfferDate` |
| Response Event | `Events.OMConsumers.OMXFM.Response.CCBS_GET_SUB_OFFER_FUTURE_DATE` |

---

## §4 Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "CCBS_GET_SUB_OFFER_FUTURE_DATE"
orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_SUB_OFFER_FUTURE_DATE"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 Execution Flow

1. Evaluate PreExecCheck (if set) per subscriber via `GetXMLForSubscriber`
2. For passing subscribers: skip if `reqSuccess=true`
3. Build and send `CCBS_GET_SUB_OFFER_FUTURE_DATE` event via `Event.Ext.sendEventImmediate`
4. If not resubmit: `RequestCount++`
5. If `AllowWriteLog`: fire audit logger
6. Repeat for ChildOU subscribers (`GetXMLForSubscriberInChildOU`)
7. `SendDataToDB(orderRequest)`
8. If not skipped: set IN_PROGRESS; else: `SkipActivity("4")`

---

## §9 Payload Build

```text
createEvent
└── event
    ├── JMSCorrelationID  ← $orderRequest/OrderData/OMXTrackingId   [Always]
    ├── OrderID           ← $orderRequest/OrderData/OrderID          [Always]
    ├── RefID             ← $refId                                    [Always]
    ├── UserName          ← $orderRequest/OrderData/User              [Always]
    ├── PassWord          ← $orderRequest/OrderData/Password          [Always]
    ├── OrderType         ← $orderRequest/OrderData/OrderType         [Always]
    ├── CES               ← $orderRequest/OrderData/CES               [Conditional: if CES exists]
    └── payload
        └── ns:getFutureRequestOfferDate
            └── ns:SubscriberIdInfo
                └── ns:subscrNumber  ← ParentOU[$iPOU]/Subscriber[$iPSUB]/SubscriberId  [Always]
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_GET_SUB_OFFER_FUTURE_DATE
├── GetXMLForSubscriber(orderRequest, refId)
├── GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)
├── XPath.execute("/(preExecCheck)", sXML, ...)
├── Event.Ext.sendEventImmediate(reqEvent)          ← fire-and-forget
├── AllowWriteLog(orderRequest.OrderData.OrderType)
├── Event.Ext.sendEventImmediate(Logger)
├── SendDataToDB(orderRequest)
├── GetActivityStatusString("1", false)
├── SkipActivity(req, activity, "4")
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 Migration Notes

| # | Requirement / Risk | Severity |
|---|-------------------|---------|
| R1 | Response must write EffectiveDate and ExpirationDate back to SubscriberOffers by Soc match | [HIGH] |
| R2 | Write-back is conditional: only set date if current value is empty/blank | [MEDIUM] |
| R3 | Response always returns "true" — no RequestCount or IntraActivitySequencing fan-in | [MEDIUM] |
| R4 | Dual iteration: ParentOU and ChildOU subscribers both queried | [MEDIUM] |

---

## §19 Response Message Rule

### §19.1 Overview

Creates `CCBS_GetFutureRequestOfferDate` concept with standard fields plus `UpdateService[]` array (Soc, OfferInstanceId, EffectiveDate, ExpirationDate). Iterates to write dates back to matching `SubscriberOffers`. Always returns `"true"`.

### §19.3 Response Write-back Logic

For each `UpdateService[u]` in response: find `SubscriberOffers[Soc == UpdateService.Soc]` and update `EffectiveDate` / `ExpirationDate` only if the current value is blank.

### §19.4 Completion

Returns `"true"` unconditionally — no fan-in check.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
