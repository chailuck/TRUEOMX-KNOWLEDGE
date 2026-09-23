# Request_OMX_EXP_FUT_REMOVE

> Cancels future orders matching SubscriberOffers with expiring SOCs — per-subscriber-offer dispatch via OMX_UPDATE_FUTURE_OFT (status=4), cross-referencing OMX_SEARCH_FUT_ALL results

**Priority:** 5 | **ForwardChain:** true | **Backend:** OMX Future Orders (SBM_DO_SERVICE) | **Dispatch:** Per-SubscriberOffer (POU → COU)

---

## §1 — Overview & Purpose

This rule removes (cancels/expires) future orders associated with SubscriberOffers being removed in the current order. It cross-references the `OMX_SearchFutureAllRes` from the preceding `OMX_SEARCH_FUT_ALL` activity and dispatches `OMX_UPDATE_FUTURE_OFT` events with `ns:status=4` (cancel) for each matching future order.

- Iterates POU → Subscriber → SubscriberOffers, then COU → Subscriber → SubscriberOffers
- For each offer, cross-references `OMX_SearchFutureAllRes.FutureOrdersWithSoc[]`
- Match conditions: `futureOrder.NodeId == sub.SubscriberId` AND `futureOrderSoc.expireDate != null` AND ExpirationDate type is "IM" or "BD" AND `futureOrderSoc.effectiveDate == null` AND not same order
- Two identity modes: `OfferInstanceId==0` → SOC code match; `OfferInstanceId!=0` → instanceId match
- `break` after first match per offer (one dispatch per offer)
- reqSuccess check (CompletionStatus==2) prevents re-dispatch on resubmit
- IntegrationMethod (BATCH/ONLINE) selects credential path from global variables (not used in XSLT)

> **BUG [LOW] — POU offerRefId double colon:** POU builds `pOuRefId + ":" + ":" + refId + ":" + offer.OfferName` — two consecutive colons. COU correctly builds `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.OfferName`. This may cause reqSuccess mismatches on resubmit.

> **Note — Unused variables:** `functionId` ("100200004"), `reqTransactionId` (Channel+"_"+OMXTrackingId), and `app_user`/`app_password` are computed/read but never passed to the dispatch XSLT.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_EXP_FUT_REMOVE` |
| Author | usuf-chu |
| Priority | 5 |
| forwardChain | true |
| Backend | OMX Future Orders via `OMX_UPDATE_FUTURE_OFT`; target: SBM_DO_SERVICE |
| Dispatch pattern | Per-SubscriberOffer (POU → Subscriber → SubscriberOffers, then COU) |
| Action | Cancel future order (status=4) |
| Response rulefunction | `Response_OMX_EXP_FUT_REMOVE` |
| Cross-reference activity | `OMX_SEARCH_FUT_ALL` (reads prior `OMX_SearchFutureAllRes`) |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order data including SubscriberOffers |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "OMX_EXP_FUT_REMOVE"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_EXP_FUT_REMOVE"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow

1. Determine `logicalDate` from LogicalDate concept (or `DateTime.now()`)
2. Check isActResub → `PurgePendingRequestsBeforeResubmit` if true
3. Read `IntegrationMethod` (BATCH/ONLINE) → select `app_user`/`app_password` (unused in XSLT)
4. Read `checkPackAllowFlg` from ExtendedInfo (default "Y")
5. **POU loop**: POU → Subscriber → SubscriberOffers → reqSuccess check → PreExecCheck → lookup OMX_SEARCH_FUT_ALL → match conditions → dispatch → `break`
6. **COU loop**: same structure with `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo`
7. If `!isSkipped` → `SendFirstRequestEvent` + Status="1" + `SendDataToDB`; else `SkipActivity("4")`

---

## §6 — Rule Action — Key Logic Details

### §6.1 Future Order Lookup

Locates `OMX_SEARCH_FUT_ALL` activity in `orderRequest.ProcessFlow.Activities[]` by matching `extId == processFlow@extId + ":OMX_SEARCH_FUT_ALL"`. Takes `Response[0]` as `OMX_SearchFutureAllRes`.

### §6.2 Future Order Match Conditions

| Condition | Meaning |
|-----------|---------|
| `futureOrder.NodeId == sub.SubscriberId` | Future order belongs to this subscriber |
| `futureOrderSoc.expireDate != null` | SOC has expiration date in future order |
| `GetActivityEffectiveType(offer.ExpirationDate, logicalDate) ∈ {"IM","BD"}` | Offer expiring immediately or at bill date |
| `futureOrderSoc.effectiveDate == null` | SOC not yet activated |
| `orderRequest.OrderData.OrderID != futureOrder.fromOrderId` | Not same order |

### §6.3 Identity Matching Branches

| Branch | Condition | Match logic |
|--------|-----------|-------------|
| POU instance 0 | `offer.OfferInstanceId == 0` | `offer.Soc == futureOrderSoc.code` |
| POU instance non-0 | `offer.OfferInstanceId != 0` | `futureOrderSoc.instanceId == offer.OfferInstanceId` |
| COU instance 0 | `futureOrderSoc.instanceId == 0` | `offer.Soc == futureOrderSoc.code` |
| COU instance non-0 | `futureOrderSoc.instanceId != 0` | `futureOrderSoc.instanceId == offer.OfferInstanceId` |

> Note: POU checks `offer.OfferInstanceId==0`; COU checks `futureOrderSoc.instanceId==0` — subtle asymmetry in the variable checked.

### §6.4 offerRefId Construction

| Scope | Formula | Issue |
|-------|---------|-------|
| POU | `pOuRefId + ":" + ":" + refId + ":" + offer.OfferName` | [LOW] Double colon |
| COU | `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.OfferName` | Correct |

---

## §8 — System & Integration Dependencies

### §8.1 ESB / JMS

| Direction | Event | Purpose |
|-----------|-------|---------|
| [OUTBOUND] | `OMX_UPDATE_FUTURE_OFT` | Cancel future order (status=4) |
| [LOG] | `Logger` | Audit per dispatch |

### §8.2 Cross-Activity Data Dependency

| Source activity | Concept | Fields used |
|-----------------|---------|-------------|
| `OMX_SEARCH_FUT_ALL` | `Concepts.FM.Response.OMX_SearchFutureAllRes` | `FutureOrdersWithSoc[n].futureOrder[0]`, `FutureOrdersWithSoc[n].futureSocs.futureSocs[0]` |

### §8.3 FutureOrder Fields Used

| Field | Usage |
|-------|-------|
| `futureOrder.NodeId` | Match against sub.SubscriberId |
| `futureOrder.fromOrderId` | Exclude same-order futures |
| `futureOrder.FutureOrderId` | `ns:futureOrderId` in payload |
| `futureOrder.OrderType` | `ns:orderType` in payload |
| `futureOrder.NodeLevel` | `ns:nodeLevel` in payload |
| `futureOrder.NodeId` | `ns:nodeId` in payload |
| `futureOrder.UpdatedDate` | `ns:updatedDate` in payload |
| `futureOrder.Remark` | Prepended to `ns:remark` string |
| `futureOrderSoc.expireDate` | Must be non-null (gate) |
| `futureOrderSoc.effectiveDate` | Must be null (gate) |
| `futureOrderSoc.code` | SOC identity match (instanceId==0) |
| `futureOrderSoc.instanceId` | Instance identity match (instanceId!=0) |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameters

| Param | Source |
|-------|--------|
| `$orderRequest` | orderRequest concept |
| `$futureOrder` | matched `Concepts.OMX.FutureOrder` from OMX_SEARCH_FUT_ALL |

### §9.2 Output XML Tree

```text
createEvent → event
├── JMSPriority              ← $orderRequest/OrderPriority              [Conditional: if exists]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId    [Conditional: if exists]
├── OrderID                  ← $orderRequest/OrderData/OrderID          [Conditional: if exists]
├── UserName                 ← $orderRequest/OrderData/User             [Conditional: if exists]
├── PassWord                 ← $orderRequest/OrderData/Password         [Conditional: if exists]
├── OrderType                ← $orderRequest/OrderData/OrderType        [Conditional: if exists]
└── payload
    └── ns:futureOrders
        └── ns:futureOrder
            ├── ns:futureOrderId  ← $futureOrder/FutureOrderId         [Conditional: if exists]
            ├── ns:status         ← 4 (static — CANCEL)                [Always]
            ├── ns:orderType      ← $futureOrder/OrderType              [Conditional: if exists]
            ├── ns:nodeLevel      ← $futureOrder/NodeLevel              [Conditional: if exists]
            ├── ns:nodeId         ← $futureOrder/NodeId                 [Conditional: if exists]
            ├── ns:updatedDate    ← $futureOrder/UpdatedDate            [Conditional: if exists]
            ├── ns:updatedBy      ← 'OMX' (static)                     [Always]
            └── ns:remark         ← concat($futureOrder/Remark,
                                   "Remove Future from remove offer order : ",
                                   $orderRequest/OrderData/OMXTrackingId)  [Always]
```

Schema: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd` (ns)

---

## §11 — Audit Logging

| Event | AUDIT_TRACE | OPERATION_NAME | Issue |
|-------|-------------|----------------|-------|
| Request dispatch | "Request Sent for OMX_EXP_FUT_REMOVE" | OMX_EXP_FUT_REMOVE | Correct |
| Response (RF) | "Response received for OMX_EXP_FUT_REMOVE" | OMX_EXP_FUT_REMOVE | Correct |

---

## §12 — Activity Status Management

| Condition | Result |
|-----------|--------|
| At least one future order cancelled | `SendFirstRequestEvent` + Status="1" + `SendDataToDB` |
| No qualifying future orders found | `SkipActivity("4")` |

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, offerName, filter)` | POU SubscriberOffer PreExecCheck XML builder |
| `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, refId, offerName, pOuRefId, filter)` | COU SubscriberOffer PreExecCheck XML builder |
| `GetActivityEffectiveType(expirationDate, logicalDate)` | Returns "IM"/"BD"/other for expiration date classification |
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears pending on resubmit |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Registers request |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Dispatches first queued request |
| `SkipActivity(orderRequest, activity, "4")` | Skip marker |
| `SendDataToDB(orderRequest)` | Persists state |

---

## §15 — Function Dependency Tree

```text
Request_OMX_EXP_FUT_REMOVE (rule)
├── DateTime.parseString / DateTime.now()
├── RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── [POU per-offer loop]
│   ├── RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(...)
│   ├── XPath.execute(preExecCheck)
│   ├── [OMX_SEARCH_FUT_ALL lookup in processFlow.Activities]
│   ├── RuleFunctions.Helpers.GetActivityEffectiveType(offer.ExpirationDate, logicalDate)
│   ├── Event.createEvent("xslt://OMX_UPDATE_FUTURE_OFT") × matching offers
│   ├── Event.assertEvent(reqEvent)
│   ├── RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│   └── Event.Ext.sendEventImmediate(Logger)
├── [COU per-offer loop — same structure]
│   └── RuleFunctions.Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...)
├── RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(activity)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")
└── RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")
```

---

## §17 — Migration Notes & Recommendations

| Risk | Severity | Mitigation |
|------|----------|------------|
| POU offerRefId double colon — reqSuccess key mismatch on resubmit | [LOW] | Fix POU formula to match COU pattern (empty string for cOuRefId) |
| app_user/app_password read but never passed to dispatch XSLT | [MEDIUM] | Wire into XSLT params or remove dead reads |
| functionId and reqTransactionId computed but unused | [LOW] | Remove or implement for SBM_DO_SERVICE integration |
| POU vs COU identity branch asymmetry (offer.OfferInstanceId==0 vs futureOrderSoc.instanceId==0) | [MEDIUM] | Verify and align to intended semantics |
| OMX_SEARCH_FUT_ALL lookup takes only Response[0] | [LOW] | Verify single-response expectation |
| checkPackAllowFlg read but not used in dispatch conditions | [LOW] | Document intent or remove |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_EXP_FUT_REMOVE {
  attribute { priority = 5; forwardChain = true; }
  then {
    // logicalDate from LogicalDate concept or DateTime.now()
    boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
    if(isActResub) PurgePendingRequestsBeforeResubmit(activity);
    String functionId = "100200004";                                // Unused
    String reqTransactionId = Channel + "_" + OMXTrackingId;       // Unused
    boolean isBatch = (IntegrationMethod == "BATCH");
    String app_user = globalVars.SBM_DO_SERVICE/(isBatch?BATCH:ONLINE)/app_user;  // Unused in XSLT
    String checkPackAllowFlg = ExtendedInfo["CHECK_PACK_ALLOW_FLG"] ?: "Y";
    boolean isSkipped = true;

    for(POU) {
      for(Subscriber sub : POU.Subscriber) {
        for(SubscriberOffers offer : sub.SubscriberOffers) {
          String offerRefId = pOuRefId + ":" + ":" + refId + ":" + offer.OfferName;  // BUG: double ":"
          String filter = offer.ExtendedInfo["FE_OR_CCBS"]/Value;
          if(reqSuccess(offerRefId)) continue;
          sXML = GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, offerName, filter);
          if(preExecCheck passes) {
            OMX_SearchFutureAllRes futureResponse = lookupOMX_SEARCH_FUT_ALL();
            for(FutureOrdersWithSoc fows : futureResponse) {
              if(nodeId==sub.SubscriberId && expireDate!=null
                 && effectiveType∈{IM,BD} && effectiveDate==null && !sameOrder) {
                if(offer.OfferInstanceId == 0 && offer.Soc == futureOrderSoc.code) {
                  // [See §9 — builds ns:futureOrders/futureOrder, status=4, updatedBy='OMX']
                  OMX_UPDATE_FUTURE_OFT reqEvent = Event.createEvent("xslt://{{OMX_UPDATE_FUTURE_OFT}}");
                  ActionRequestEvent; isSkipped = false; break;
                } else if(futureOrderSoc.instanceId == offer.OfferInstanceId) {
                  // Same XSLT
                  ActionRequestEvent; isSkipped = false;
                }
              }
            }
          }
        }
      }
      // COU loop: same structure, GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo
    }
    if(!isSkipped) { SendFirstRequestEvent; Status="1"; SendDataToDB; }
    else { SkipActivity("4"); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

Creates a `OMX_UpdateFutureRes` concept (generic shared type for future order updates), appends to Response[], logs audit, and calls `ActionResponseEvent` for fan-in. No ReferenceId — fan-in is pure count-based.

### §19.2 Scope Variables

| Variable | Type | Note |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_UPDATE_FUTURE` | Generic shared event type |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | |

### §19.3 ResponseBase Concept

```text
createObject → OMX_UpdateFutureRes
├── @extId           ← OMXUtils:generateTrackingID()         [Always]
├── ResponseCode     ← $eventResponse/ResponseCode           [Conditional: if exists]
├── ResponseMessage  ← $eventResponse/ResponseMsg            [Conditional: if exists]
└── CompletionStatus ← $eventResponse/CompletionStatus       [Conditional: if exists]
```

Note: No ReferenceId field — fan-in is count-based.

### §19.4 Fan-in

`IntraActivitySequencing.ActionResponseEvent(currActivity)` → "true" (all responded) / "false" (still waiting)

### §19.5 Response Audit

Both AUDIT_TRACE and OPERATION_NAME correctly say `OMX_EXP_FUT_REMOVE` — no copy-paste issues.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
