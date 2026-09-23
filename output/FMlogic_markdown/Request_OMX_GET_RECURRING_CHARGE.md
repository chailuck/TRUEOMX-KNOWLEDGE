# Request_OMX_GET_RECURRING_CHARGE

## §1 Overview & Purpose

**OMX_GET_RECURRING_CHARGE** retrieves the recurring charge (RC) for each unique product (SOC code) in the order. Scans all SubscriberOffers and AgreementOffers, deduplicates by SOC, and sends one request with the full list of unique SOC codes.

> **Unique iteration:** Builds a deduplicated ArrayList of SOC codes across 4 paths: ChildOU.Subscriber.SubscriberOffers, ChildOU.Agreement.Offers, POU.Subscriber.SubscriberOffers, POU.Agreement.Offers. Only SOCs passing PreExecCheck are added. If list empty → SkipActivity.

> **GoldenDB dispatch:** GoldenDB="Y" → CES_GET_RECURRING_CHARGE; else → OMX_GET_RECURRING_CHARGE. Same payload structure.

> **Response write-backs:** Writes ExtendedInfo Name="RC" Value=RecurringCharges to every matching SubscriberOffer and AgreementOffer across all POU/ChildOU.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_RECURRING_CHARGE` |
| Priority | 5 |
| forwardChain | true |
| Backend | OMX FM / CES (GoldenDB dispatch) |
| Event type (request) | `Events.OMConsumers.OMXFM.Request.OMX_GET_RECURRING_CHARGE` OR `CES_GET_RECURRING_CHARGE` |
| Send pattern | `Event.Ext.sendEventImmediate(reqEvent)` — FIRE-AND-FORGET |
| RequestCount | `if(!isActResub) RequestCount++` |
| Fan-in | Response returns "true" unconditionally (single request per activity) |
| Iteration | Deduplicated SOC list across SubscriberOffers + AgreementOffers |
| Response concept | `Concepts.FM.Response.OMX_GetRecurringChargeRes` |
| Skip condition | offerList.size == 0 → SkipActivity("4") |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| SOC deduplication | ArrayList offerList; add only if !contains(offerList, soc). One `<soc_cd>` per unique product. |
| PreExecCheck per offer | 4 helper variants: GetXMLForSubscriberOfferInChildOU, GetXMLForAgreementOfferInChildOU, GetXMLForSubscriberOffer, GetXMLForAgreementOffer |
| GoldenDB dispatch | GoldenDB="Y" → CES_GET_RECURRING_CHARGE; else → OMX_GET_RECURRING_CHARGE |
| Resubmit guard | `if(!isActResub) RequestCount++` — sends on resubmit, only skips count increment |
| Response write-back scope | All 4 paths searched; RC written to matching offer.ExtendedInfo |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority      ← $orderRequest/OrderPriority               [Conditional]
├── JMSCorrelationID ← $orderRequest/@extId                      [Conditional]
├── OrderID          ← $orderRequest/OrderData/OrderID           [Conditional]
├── UserName         ← $orderRequest/OrderData/User              [Conditional]
├── PassWord         ← $orderRequest/OrderData/Password          [Conditional]
├── OrderType        ← $orderRequest/OrderData/OrderType         [Conditional]
└── payload → ns:GetRecurringChargesRequest
    └── [for each $socIDs/elements]
        └── soc_cd   ← each unique SOC from deduplicated offerList [Always, one per SOC]

CES variant additionally: extId ← OMXUtils:generateTrackingID() on event element
```

---

## §15 Function Dependency Tree

```text
Request_OMX_GET_RECURRING_CHARGE
├── Object offerList = Collections.List.createArrayList()
├── ── SOC ACCUMULATION (4 paths) ──
│   for each POU[i]:
│   ├── ChildOU[k].Subscriber[j].SubscriberOffers[l]:
│   │   if chkRes=="true" AND !contains(offerList, soc): add(offerList, soc)
│   ├── ChildOU[k].Agreement.Offers[l]: same
│   ├── POU[i].Subscriber[j].SubscriberOffers[l]: same
│   └── POU[i].Agreement.Offers[l]: same
├── Object[] socIDs = Collections.toArray(offerList)
├── if socIDs != null AND size > 0:
│   ├── if GoldenDB="Y": sendEventImmediate(CES_GET_RECURRING_CHARGE with socIDs)
│   └── else: sendEventImmediate(OMX_GET_RECURRING_CHARGE with socIDs)
│   ├── if(!isActResub): RequestCount++
│   ├── sendEventImmediate(Logger REQ)
│   └── GetActivityStatusString + SendDataToDB
└── else: SkipActivity("4")

Response_OMX_GET_RECURRING_CHARGE
├── Instance.createInstance(OMX_GetRecurringChargeRes:
│   ResponseCode, ResponseMsg, CompletionStatus, ReferenceId,
│   SocRecurringCharges[]: {soc_cd, RecurringCharges})
│   → currActivity.Response[n]
├── for each SocRecurringCharges[i]:
│   └── for each offer in all 4 paths (ChildOU.Subscriber.SubscriberOffers, etc.):
│       if offer.Soc == soc_cd:
│           offer.ExtendedInfo[] += {Name="RC", Value=soc_rc}
├── sendEvent(Logger RES)
└── return "true"  [ALWAYS — no counting]
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Response always "true" — no per-SOC validation | [MEDIUM] | Add RC response validation per SocRecurringCharges entry |
| GoldenDB dispatch: wrong route if GoldenDB missing | [LOW] | Validate GoldenDB at order submission time |
| SOC list is in-memory only — rebuilt fresh on resubmit | [MEDIUM] | Cache RC in order ExtInfo to survive resubmits |
| Response write-back is O(N×M): SOCs × all offers | [LOW] | Consider offer-by-SOC index at order load time |
| Single batch request for all SOCs — may hit OMX FM size limit | [LOW] | Verify FM batch size limit; add pagination if needed |

---

## §19 Response Message Rule

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | OMX_GetRecurringChargeRes (4 std + SocRecurringCharges[]) | Always |
| SubscriberOffer.ExtendedInfo[] Name="RC" | `SocRecurringCharges[i].RecurringCharges` | offer.Soc == soc_cd |
| AgreementOffer.ExtendedInfo[] Name="RC" | `SocRecurringCharges[i].RecurringCharges` | offer.Soc == soc_cd |

Fan-in: returns "true" unconditionally — single request per activity.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
