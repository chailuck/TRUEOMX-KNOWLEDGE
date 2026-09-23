# Request_OMX_GET_3CJ_EMAIL_TEMPLATE

## §1 Overview & Purpose

**OMX_GET_3CJ_EMAIL_TEMPLATE** fetches notification templates from the 3CJ service per Subscriber and writes them to Subscriber ExtInfo. Despite the activity name referencing "EMAIL", the JMS event used is `OMX_GET_3CJ_SMS_TEMPLATE` — the same endpoint serves both SMS and email templates, differentiated by `contentType` (from FLOW_ID ExtInfo).

> **Response write-back:** For each returned `omxnNotiTemplate`: if `emailSubject != ""` → `EMAIL_TEMPLATE_CONTENT=templateContent`; else → `SMS_MSG=templateContent`. Consumed by FM35 (OMX_SEND_EMAIL3CJ).

> **Fire-and-forget per Subscriber:** `Event.Ext.sendEventImmediate` + `RequestCount++`. Fan-in: `count("000") == RequestCount`.

> **KNOWN BUG in ChildOU loop:** `ParentOU[iCOU].ChildOU[iCOU]` uses iPOU=iCOU — wrong index for multi-POU orders.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_3CJ_EMAIL_TEMPLATE` |
| Author | TIT_CP-CHAYAT2 |
| Priority | 5 |
| forwardChain | true |
| Backend | 3CJ (notification template service) |
| Event type (Request) | `Events.OMConsumers.OMXFM.Request.OMX_GET_3CJ_SMS_TEMPLATE` |
| Event type (Response) | `Events.OMConsumers.OMXFM.Response.OMX_GET_3CJ_SMS_TEMPLATE` |
| Send pattern | `Event.Ext.sendEventImmediate(reqEvent)` — FIRE-AND-FORGET per Subscriber |
| RequestCount | `if(!isActResub) RequestCount++` |
| Fan-in | `count(Response[ResponseCode suffix "000"]) == RequestCount` |
| Iteration | POU[].Subscriber[] AND ChildOU[].Subscriber[] |
| Key input | `ExtInfo[FLOW_ID].Value` → contentType |
| Write-back | `subscriber.ExtendedInfo[]` ← EMAIL_TEMPLATE_CONTENT or SMS_MSG |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| Event name mismatch | ActivityID=EMAIL_TEMPLATE; event type=SMS_TEMPLATE — intentional reuse |
| contentType from FLOW_ID | `contentType = ExtendedInfo[Name='FLOW_ID'].Value` |
| Template type discrimination | `emailSubject != ""` → EMAIL_TEMPLATE_CONTENT; else → SMS_MSG |
| Multiple templates per subscriber | Multiple `omxnNotiTemplate[]` items each written as separate ExtInfo entry |
| currActivity direct set | Response also sets `currActivity.ResponseCode` and `.ResponseMessage` directly |
| Exception catch in response | Returns `"false"` on any exception — fan-in fails gracefully |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── extId           ← OMXUtils:generateTrackingID()        [Always]
├── JMSPriority/JMSCorrelationID/OrderID/RefID             [Standard fields]
├── UserName        ← OrderData.User                       [Always]
├── PassWord        ← OrderData.Password                   [Always]
├── OrderType       ← OrderData.OrderType                  [Conditional]
└── payload → ns:OMX_Sms3CJTemplateRequest
    ├── ns:orderType   ← OrderData.OrderType               [Conditional]
    └── ns:contentType ← ExtInfo[FLOW_ID].Value            [Always]
```

---

## §15 Function Dependency Tree

```text
Request_OMX_GET_3CJ_EMAIL_TEMPLATE
├── for each POU[iPOU].Subscriber[subs]:
│   ├── [if isActResub] check CompletionStatus==2 skip
│   ├── [if PreExecCheck] GetXMLForSubscriber → chkRes
│   └── if chkRes=="true" AND !reqSuccess:
│       ├── createEvent(OMX_GET_3CJ_SMS_TEMPLATE XSLT) + sendEventImmediate
│       ├── if(!isActResub): RequestCount++
│       └── Logger REQ
├── for each POU[iPOU].ChildOU[iCOU].Subscriber[subs]:
│   └── [same pattern — BUG: index uses iCOU for both POU and ChildOU]
├── if !isSkipped: GetActivityStatusString + SendDataToDB
└── else: SkipActivity("4")

Response_OMX_GET_3CJ_EMAIL_TEMPLATE
├── createInstance(ResponseBase std 4) → currActivity.Response[n]
├── currActivity.ResponseCode/ResponseMessage = eventResponse.*
├── match eventResponse.RefID == subscriber.RefId:
│   └── for each omxnNotiTemplate[i]:
│       └── subscriber.ExtendedInfo ← EMAIL_TEMPLATE_CONTENT or SMS_MSG = templateContent
├── Logger RES
└── count("000") == RequestCount → "true"/"false"
    catch → "false"
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| ChildOU loop index bug: `ParentOU[iCOU].ChildOU[iCOU]` | [HIGH] | Fix to `ParentOU[iPOU].ChildOU[iCOU]` |
| Event name (SMS_TEMPLATE) mismatches activity name (EMAIL_TEMPLATE) | [MEDIUM] | Document intentional reuse; align naming in migration |
| FM35 depends on EMAIL_TEMPLATE_CONTENT being written here | [MEDIUM] | Add PreExecCheck guard in FM35; document dependency |
| emailSubject whitespace treated as non-empty → wrong template type | [LOW] | Trim emailSubject before comparison |

---

## §19 Response Message Rule

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | ResponseBase (std 4) | Always |
| `currActivity.ResponseCode` | `eventResponse.ResponseCode` | Always |
| `subscriber.ExtendedInfo[EMAIL_TEMPLATE_CONTENT]` | `omxnNotiTemplate[i].templateContent` when emailSubject != "" | Conditional |
| `subscriber.ExtendedInfo[SMS_MSG]` | `omxnNotiTemplate[i].templateContent` when emailSubject == "" | Conditional |

Fan-in: `count(Response[ResponseCode suffix "000"]) == RequestCount`. Exception → `"false"`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
