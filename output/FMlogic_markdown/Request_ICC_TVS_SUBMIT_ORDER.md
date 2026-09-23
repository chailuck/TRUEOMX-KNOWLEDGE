# Request_ICC_TVS_SUBMIT_ORDER

> TIBCO BusinessEvents FM — ICC TVS Submit Order (trueID TV, 3 variants in FULL_SUSPEND)

**Priority:** 5 | **forwardChain:** true | **No author** | **Backend:** ICC (trueID TV service)

---

## §1 — Overview & Purpose

Fires when `ActivityID == "ICC_TVS_SUBMIT_ORDER"`. Dual-loop per subscriber. Submits TV service order to ICC. Appears **3 times** in FULL_SUSPEND with different REASON values.

| Step Instance | REASON | PreExecCheck gate |
|---------------|--------|-------------------|
| ICC_TVS_SUBMIT_ORDER_CVG (step 31) | TFULL | `TVS_NO present` |
| ICC_TVS_SUBMIT_ORDER_BY_REQ (step 32) | TDISCOTT | `Channel!="CCBS" and trueIDTV ParameterInfo non-empty` |
| ICC_TVS_SUBMIT_ORDER_BY_COLLECTION (step 33) | TFULLOTT | `Channel="CCBS" and trueIDTV ParameterInfo non-empty` |

**tvs_customer_id logic:** REASON=`TFULL` AND `TVS_NO` ExtendedInfo present → use TVS_NO; else `"0"`.
**Required parameters:** ORDER_TYPE, ACTION_CODE, REASON — throws DATA_ISSUE if any missing.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_ICC_TVS_SUBMIT_ORDER` |
| Priority / forwardChain | 5 / true |
| Loop | Dual-loop: ParentOU.Subscriber + ChildOU.Subscriber |
| Required parameters | ORDER_TYPE, ACTION_CODE, REASON |
| Fan-in type | Classic count |

---

## §5 — Execution Flow

1. Load ORDER_TYPE, ACTION_CODE, REASON — throw DATA_ISSUE if null
2. Load SubmissionDate (`DateTime.now()`)
3. Dual-loop POU + COU subscribers
4. Per subscriber: apply PreExecCheck
5. Resolve `tvsCustomerId`: REASON="TFULL" and TVS_NO present → TVS_NO, else "0"
6. Build and fire `ICC_TVS_SUBMIT_ORDER` event
7. On dispatch → status "1"; On all skip → `SkipActivity("4")`

---

## §10 — XSLT Field Mapping Tree

```text
TvsSubmitOrderReq
├── ns:request_date       ← tib:format-dateTime("dd/MM/yyyy HH:mm:ss", SubmissionDate)  [Always]
├── ns:request_trans_id   ← OMXTrackingId                                               [Always]
├── ns:tvs_customer_id    ← TVS_NO if REASON="TFULL" and TVS_NO exists, else "0"       [Always]
├── ns:tvs_reference_id   ← MSISDN                                                      [Always]
├── ns:order_type         ← ORDER_TYPE param                                             [Always]
├── ns:by_channel         ← "OMX"                                                       [Always]
├── ns:by_user            ← "OMX"                                                       [Always]
└── ns:payload
    ├── ns:tvscustomer      ← same as tvs_customer_id                                   [Always]
    ├── ns:tmvno            ← MSISDN                                                    [Always]
    ├── ns:actioncode       ← ACTION_CODE param                                         [Always]
    └── ns:activityreasoncode ← REASON param                                            [Always]
```

---

## §15 — Function Dependency Tree

```text
Request_ICC_TVS_SUBMIT_ORDER
├── RuleFunctions.Helpers.GetActivityParameterValueFromKey (ORDER_TYPE, ACTION_CODE, REASON)
├── RuleFunctions.Helpers.GetXMLForSubscriber / GetXMLForSubscriberInChildOU
├── XPath.execute (PreExecCheck)
├── XPath.evalAsString (TVS_NO ExtendedInfo)
├── DateTime.now; tib:format-dateTime
├── Event.createEvent (ICC_TVS_SUBMIT_ORDER XSLT)
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

`Response_ICC_TVS_SUBMIT_ORDER` maps `ICC_TVS_SUBMIT_ORDER` response into `ResponseBase`. Classic fan-in count: `count(Response[tib:right(tib:trim(ResponseCode),3)="000"]) == RequestCount`.

No side effects in response handler.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
