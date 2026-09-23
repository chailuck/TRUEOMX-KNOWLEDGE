# Request_OMX_SEND_EMAIL3CJ

## §1 Overview & Purpose

**OMX_SEND_EMAIL3CJ** sends a transactional email via the 3CJ email service for each qualifying Subscriber. The email template is identified by `EMAIL_TEMPLATE_CONTENT` ExtInfo written by FM34 — parsed as `templateId.version` (dot-separated). Supports three ACTION modes: PICKUP_SHOP, DEVICE_BUNDLE, and default (SIM/MSISDN).

> **Depends on FM34:** `EMAIL_TEMPLATE_CONTENT` must be present in Subscriber ExtInfo. If FM34 was skipped or failed, template_id and version will be empty strings.

> **Fire-and-forget per Subscriber:** `Event.Ext.sendEventImmediate` + `RequestCount++`. Fan-in: `count("000") == RequestCount`.

> **Two iteration loops:** ChildOU Subscribers first, then POU Subscribers. Both use identical XSLT payload.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_SEND_EMAIL3CJ` |
| Author | Chayatorn P. |
| Priority | 5 |
| forwardChain | true |
| Backend | 3CJ (email send service) |
| Event type (Request) | `Events.OMConsumers.OMXFM.Request.OMX_SEND_EMAIL3CJ` |
| Event type (Response) | `Events.OMConsumers.OMXFM.Response.OMX_SEND_EMAIL3CJ` |
| Send pattern | `Event.Ext.sendEventImmediate(reqEvent)` — FIRE-AND-FORGET per Subscriber |
| RequestCount | `if(!isActResub) RequestCount++` |
| Fan-in | `count(Response[ResponseCode suffix "000"]) == RequestCount` |
| Parameters | ACTION (PICKUP_SHOP \| DEVICE_BUNDLE \| default), CID |
| Resubmit skip | `Response[refId AND CompletionStatus==2]` |
| Key dependency | `EMAIL_TEMPLATE_CONTENT` from FM34 |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| Template ID parsing | `template_id = substring-before(EMAIL_TEMPLATE_CONTENT, ".")` ; `version = substring-after(...)` |
| channel hardcoded | `"EMAIL_ITO"` always |
| sender hardcoded | `"no-reply@truecorp.co.th"` always |
| to field | `Customer.CustomerName.Email` — customer-level |
| PICKUP_SHOP params | PaymentItem_MSISDN, Order_desc, expirydate(dd-MM-yy), targetShopName, barcodecid |
| DEVICE_BUNDLE params | MSISDN, orderid, expirydate(raw), deeplink + list_parameters (PaymentItemInfo or eSim fallback) |
| Default params | MSISDN + SIM (ICC_ID) only |
| dro | Hardcoded `"false"` |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── extId/JMSPriority/JMSCorrelationID/OrderID/RefID/OrderType ← standard
└── payload → ns:OMX_3CJSendEmailRequest
    ├── ns:request_transaction_id ← OMXTrackingId          [Always]
    ├── ns:template_id  ← substring-before(EMAIL_TEMPLATE_CONTENT, ".") [Always]
    ├── ns:version      ← substring-after(EMAIL_TEMPLATE_CONTENT, ".")  [Always]
    ├── ns:channel      ← "EMAIL_ITO"                       [Hardcoded]
    ├── ns:language     ← subscriber.Language               [Conditional]
    ├── ns:sender       ← "no-reply@truecorp.co.th"         [Hardcoded]
    ├── ns:to           ← Customer.CustomerName.Email       [Conditional]
    ├── ns:parameters   [ACTION dispatch]
    │   ├── PICKUP_SHOP: PaymentItem_MSISDN, Order_desc, expirydate(dd-MM-yy), targetShopName, barcodecid
    │   ├── DEVICE_BUNDLE: MSISDN, orderid, expirydate(raw), deeplink
    │   └── default: MSISDN, SIM (ICC_ID)
    ├── ns:list_parameters [DEVICE_BUNDLE only]
    │   └── PaymentItemInfo from Account or fallback eSim entry
    └── ns:dro ← "false"                                   [Hardcoded]
```

---

## §15 Function Dependency Tree

```text
Request_OMX_SEND_EMAIL3CJ
├── actionParam = GetActivityParameterValueFromKey("ACTION")
├── cidParam = GetActivityParameterValueFromKey("CID")
├── for each POU[i].ChildOU[k].Subscriber[j]:
│   ├── [PreExecCheck] GetXMLForSubscriberInChildOU
│   └── if chkRes && !reqSuccess: createEvent + sendEventImmediate + RequestCount++ + Logger
├── for each POU[i].Subscriber[j]:
│   ├── [PreExecCheck] GetXMLForSubscriber
│   └── if chkRes && !reqSuccess: createEvent + sendEventImmediate + RequestCount++ + Logger
├── if !isSkipped: GetActivityStatusString + SendDataToDB
└── else: SkipActivity("4")

Response_OMX_SEND_EMAIL3CJ
├── createInstance(ResponseBase std 4) → currActivity.Response[n]
├── currActivity.ResponseCode/ResponseMessage = eventResponse.*
├── Logger RES
└── count("000") == RequestCount → "true"/"false"
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| EMAIL_TEMPLATE_CONTENT dependency on FM34 — empty if FM34 skipped | [HIGH] | Add guard; document FM34→FM35 chain |
| AUDIT_TRACE typo: "OMX_SEND_SMS_3CJ" in response logger | [LOW] | Fix string in migration |
| Customer-level email (not subscriber-level) | [LOW] | Validate data model with business |
| PICKUP_SHOP expirydate format "dd-MM-yy" inconsistent with DEVICE_BUNDLE raw format | [LOW] | Confirm 3CJ expected date formats per action type |

---

## §19 Response Message Rule

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | ResponseBase (std 4) | Always |
| `currActivity.ResponseCode` | `eventResponse.ResponseCode` | Always |
| `currActivity.ResponseMessage` | `eventResponse.ResponseMsg` | Always |

No write-back to order data. Fan-in: `count(Response[ResponseCode suffix "000"]) == RequestCount`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
