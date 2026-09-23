# Request_TDG_SUSPEND_SUBSCRIBER

> TIBCO BusinessEvents FM — TRUE Digital (TDG) Suspend Subscriber per-material-info loop

**Priority:** 5 | **forwardChain:** true | **Author:** CHAYATORN P. | **Backend:** TDG (TRUE Digital)

---

## §1 — Overview & Purpose

Fires when `ActivityID == "TDG_SUSPEND_SUBSCRIBER"`. Iterates over **MaterialInfo.Material entries** (IoT/device materials), not subscribers. For each material, sends a `TDG_SUSPEND_SUBSCRIBER` JMS event to TRUE Digital.

**PreExecCheck gate:** Subscriber must have `TR_SPECIAL_OFFER_IND=IOTBU` — IoT Business Unit only.
**Reason mapping:** Channel=`CCBS` → `"C"` (Collection); else → `"R"` (Regular).
**propositioncode:** from `SubscriberOffers/RelatedOffersArray[ServiceType=85, TR_CONTRACT_IND=Y]/OfferName`.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_TDG_SUSPEND_SUBSCRIBER` |
| Priority / forwardChain | 5 / true |
| Author | CHAYATORN P. |
| Loop strategy | Per MaterialInfo.Material |
| RefId | `concat(pSubRefId, ":", material.MatCode)` |
| Helper | `GetXMLForSubscriberMaterialInfo` |
| Fan-in type | Classic count |

---

## §5 — Execution Flow

1. Get subscriber XML via `GetXMLForSubscriberMaterialInfo`
2. Apply PreExecCheck: `TR_SPECIAL_OFFER_IND=IOTBU`
3. Loop over `MaterialInfo.Material[m]`; compute `pmatchRefId = pSubRefId:MatCode`
4. Skip if existing completed response for this refId
5. Resolve `propositioncode` from RelatedOffersArray (ServiceType=85 + TR_CONTRACT_IND=Y)
6. Determine `reason`: Channel=CCBS → "C", else "R"
7. Fire TDG_SUSPEND_SUBSCRIBER event
8. On dispatch → status "1"; On all skip → `SkipActivity("4")`

---

## §10 — XSLT Field Mapping Tree

```text
SuspendSubscriberRequest
├── ns:serial          ← MaterialInfo.Material[$m]/MatSerial   [Always]
├── ns:id              ← Subscriber/MSISDN                     [Always]
├── ns:propositioncode ← RelatedOffersArray[ST=85,TR_CONTRACT_IND=Y]/OfferName [Conditional]
└── ns:reason          ← "C" if Channel=CCBS, else "R"         [Always]
```

---

## §15 — Function Dependency Tree

```text
Request_TDG_SUSPEND_SUBSCRIBER
├── RuleFunctions.Helpers.GetXMLForSubscriberMaterialInfo
├── XPath.execute (PreExecCheck)
├── XPath.evalAsString (MatSerial, MSISDN, propositioncode, Channel)
├── Event.createEvent (TDG_SUSPEND_SUBSCRIBER XSLT)
├── RuleFunctions.Helpers.ActionRequestEvent
├── Event.Ext.sendEventImmediate (audit)
├── RuleFunctions.Helpers.SendFirstRequestEvent
├── RuleFunctions.Helpers.GetActivityStatusString
├── RuleFunctions.Helpers.SendDataToDB
├── RuleFunctions.Helpers.SkipActivity
└── RuleFunctions.Helpers.HandleActivityException
```

---

## §19 — Response Message Rule

`Response_TDG_SUSPEND_SUBSCRIBER` maps `TDG_SUSPEND_SUBSCRIBER` response into `ResponseBase`. Classic fan-in count.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
