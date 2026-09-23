# Request_CVSS_GET_EXISTING_PRODUCT

## §1 Overview & Purpose

**CVSS_GET_EXISTING_PRODUCT** retrieves the count of existing CVSS products for each Account. The result updates `Account.ProductCount`, consumed by downstream credit evaluation logic.

> **Fire-and-forget:** Uses `Event.Ext.sendEventImmediate(reqEvent)` + manual `RequestCount++`. Fan-in uses OLD count-based pattern: `count("000" responses) == RequestCount` — NOT IntraActivitySequencing.

> **Minimal payload:** Only `ban` (Account.AccountID) and `productId=1` (hardcoded). No customer details.

> **Response write-back:** Account.ProductCount set from response `count` field, using extId lookup `"A:"+JMSCorrelationID+":"+RefID`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CVSS_GET_EXISTING_PRODUCT` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | CVSS |
| Send pattern | `Event.Ext.sendEventImmediate(reqEvent)` — FIRE-AND-FORGET |
| RequestCount | `if(!isActResub) RequestCount++` |
| Fan-in | OLD: `count(Response[ResponseCode suffix "000"]) == RequestCount` |
| Iteration target | `Customer.Account[]` |
| Response concept | `Concepts.FM.Response.CVSS_GetExistingProductRes` |
| Payload operation | `ns:GetExistingProductRequest / ns:getExistingProduct` |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| productId hardcoded | `ns:productId = 1` always. CVSS product type identifier. |
| Account lookup | `Instance.getByExtIdByUri("A:"+JMSCorrelationID+":"+RefID, Account)` — requires specific extId format. |
| ProductCount write-back | `acct.ProductCount = XPath.evalAsInt(response count field)` — only if acct != null. |
| Response extra fields | CVSS_GetExistingProductRes: std 4 + result_count + statusCode + statusMessage. Only ProductCount written to order. |
| OLD fan-in | count("000" responses) == RequestCount — NOT IntraActivitySequencing (inconsistent with other FMs). |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority         ← $orderRequest/OrderPriority                 [Conditional]
├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId        [Conditional]
├── OrderID             ← $orderRequest/OrderData/OrderID              [Conditional]
├── RefID               ← $refId (Account[i].RefId)                    [Always]
├── OrderType           ← $orderRequest/OrderData/OrderType            [Conditional]
└── payload → ns:GetExistingProductRequest
    └── ns:getExistingProduct
        ├── ns:ban      ← Account[(number($i)+1)]/AccountID            [Always]
        └── ns:productId← 1                                            [Hardcoded]

No CES field. JMSCorrelationID from OMXTrackingId (not @extId as in other FMs).
```

---

## §15 Function Dependency Tree

```text
Request_CVSS_GET_EXISTING_PRODUCT
├── Instance.getByExtIdByUri(NextActivityName, Activity)
├── for each Account[i]:
│   ├── [skip if CompletionStatus==2 response exists for RefId]
│   ├── if PreExecCheck: GetXMLForAccount → XPath
│   └── if chkRes == "true":
│       ├── Event.createEvent(CVSS_GET_EXISTING_PRODUCT, XSLT with refId/i)
│       ├── Event.Ext.sendEventImmediate(reqEvent)  ← FIRE-AND-FORGET
│       ├── sendEventImmediate(Logger REQ)
│       ├── if(!isActResub): RequestCount++
│       └── isSkipped = false
├── if !isSkipped: GetActivityStatusString + SendDataToDB
└── else: SkipActivity("4")

Response_CVSS_GET_EXISTING_PRODUCT
├── Instance.createInstance(CVSS_GetExistingProductRes:
│   ResponseCode, ResponseMsg, CompletionStatus, ReferenceId,
│   result_count, statusCode, statusMessage)
│   → currActivity.Response[n]
├── acct = Instance.getByExtIdByUri("A:"+JMSCorrelationID+":"+RefID, Account)
├── if acct != null: acct.ProductCount = XPath.evalAsInt(response count)
├── sendEventImmediate(Logger RES)
└── OLD fan-in: count(Response[ResponseCode suffix "000"]) == RequestCount
    → "true" if all success; "false" otherwise
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| OLD fan-in (count "000") — inconsistent with other FMs using IntraActivitySequencing | [MEDIUM] | Migrate to IntraActivitySequencing in future refactor |
| Account extId pattern "A:"+JMSCorrelationID+":"+RefID — requires specific format at creation | [MEDIUM] | Document Account extId format; ensure CVSS response correlation works |
| productId hardcoded 1 — undocumented constant | [LOW] | Externalise to global variable |
| result_count, statusCode, statusMessage captured but only ProductCount used | [LOW] | Log statusCode/statusMessage on non-success in migration |

---

## §19 Response Message Rule

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | CVSS_GetExistingProductRes (7 fields) | Always |
| `Account.ProductCount` | `response count` (XPath.evalAsInt) | acct found AND != null |

Fan-in: OLD count-based — `count(Response[ResponseCode suffix "000"]) == RequestCount`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
