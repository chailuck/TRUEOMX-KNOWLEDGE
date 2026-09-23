# Request_KNOX_LOCK_DEVICE

> TIBCO BusinessEvents FM — Samsung Knox Device Lock (per-offer iteration, 3-level loop)

**Priority:** 5 | **forwardChain:** true | **Author:** DESKTOP-995HR2V | **Backend:** Samsung Knox Proxy Service

---

## §1 — Overview & Purpose

Fires when `ActivityID == "KNOX_LOCK_DEVICE"`. Unique iteration strategy: loops **per offer** (SubscriberOffers), not per subscriber. For each qualifying offer, sends a `KNOX_PROXY_SERVICE` lockDevice request to Samsung Knox.

**3-Level nesting:** ParentOU → Subscriber → SubscriberOffers.
**RefId:** `concat(subRefId, ":", offer.Soc, ":", filter)` where `filter` = FE_OR_CCBS ExtendedInfo value on that offer.
**TEL required:** from `GetActivityParameterValueFromKey("TEL")` — throws DATA_ISSUE if missing.
**Notification message:** resolved via `DecisionTables.KnoxNotifyMsgVRF(orderType, "LOCK", activityReason, lang, msg)`.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_KNOX_LOCK_DEVICE` |
| Priority / forwardChain | 5 / true |
| Author | DESKTOP-995HR2V |
| Loop strategy | 3-level: ParentOU[i] → Subscriber[j] → SubscriberOffers[k] |
| RefId granularity | Per offer: `concat(subRefId, ":", offer.Soc, ":", filter)` |
| Required parameter | TEL |
| Fan-in type | Classic count: `count(Response[suffix"000"]) == RequestCount` |

---

## §5 — Execution Flow

1. Load TEL from `GetActivityParameterValueFromKey("TEL")` — throws DATA_ISSUE if null
2. Outer: ParentOU[i]; Middle: Subscriber[j]; Inner: SubscriberOffers[k]
3. Per offer: compute RefId = `subRefId:offer.Soc:filter`
4. Skip if existing completed response
5. Lookup notification message via `KnoxNotifyMsgVRF` decision table
6. Fire `KNOX_PROXY_SERVICE` event: transactionId, deviceUid, tel, message, brand, method="lockDevice"
7. On dispatch → status "1"; DB persist; On all skip → `SkipActivity("4")`

---

## §8 — System & Integration Dependencies

| Direction | Event | Schema |
|-----------|-------|--------|
| [OUTBOUND] | KNOX_PROXY_SERVICE | knoxProxyReq (Samsung Knox) |
| [LOG] | OMXESB/Logger | AuditLogging/V1_0 |

### ExtendedInfo Fields

| Key | Required | Purpose |
|-----|----------|---------|
| IMEI_KNOX | [Required] | Device UID; transactionId prefix |
| FE_OR_CCBS (on SubscriberOffers) | [Conditional] | filter component of RefId |
| BRAND_NAME | [Required] | Device brand sent to Knox |

---

## §10 — XSLT Field Mapping Tree

```text
createEvent → event → payload → ns:knoxProxyReq
├── ns:transactionId  ← concat(IMEI_KNOX, tib:timestamp())   [Always]
├── ns:deviceUid      ← IMEI_KNOX ExtendedInfo               [Always]
├── ns:tel            ← $tel (TEL parameter)                  [Always]
├── ns:message        ← msg/Value (KnoxNotifyMsgVRF result)   [Always]
├── ns:brand          ← BRAND_NAME ExtendedInfo               [Always]
└── ns:method         ← "lockDevice"                          [Always]
```

---

## §15 — Function Dependency Tree

```text
Request_KNOX_LOCK_DEVICE
├── RuleFunctions.Helpers.GetActivityParameterValueFromKey("TEL")
├── RuleFunctions.Helpers.GetXMLForSubscriber
├── XPath.execute (PreExecCheck)
├── XPath.evalAsString (IMEI_KNOX, FE_OR_CCBS, BRAND_NAME)
├── DecisionTables.KnoxNotifyMsgVRF(orderType, "LOCK", activityReason, lang, msg)
├── Event.createEvent (KNOX_PROXY_SERVICE XSLT)
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

`Response_KNOX_LOCK_DEVICE` maps `KNOX_PROXY_SERVICE` response into `ResponseBase`. Classic fan-in: `count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)="000"]) == currActivity.RequestCount`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
