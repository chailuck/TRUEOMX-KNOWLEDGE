# Request_PSA_UPDATE_WARRANTY_DEVICE

## §1 Overview & Purpose

**PSA_UPDATE_WARRANTY_DEVICE** registers warranty information for each device material (IMEI/MatCode) in PSA. Unlike most FMs, it iterates `Subscriber.MaterialInfo.Material` — one PSA call per material item.

> **Fire-and-forget per material:** `Event.Ext.sendEventImmediate` + manual `RequestCount++` inside material loop.

> **RefId composite key:** `SubRefId + ":" + material.MatCode` — used for CompletionStatus==2 skip and as event ReferenceId.

> **Two XSLT variants:** ParentOU uses `$pMatRefId`/`$psub`; ChildOU uses `$cMatRefId`/`$csub`. Payload structure identical between variants.

> **SALE_CHANNEL dispatch:** "SHOP"→"1"; "DEALER"→"2"; other→element omitted (no default).

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_PSA_UPDATE_WARRANTY_DEVICE` |
| Author | (not specified) |
| Priority | 5 |
| forwardChain | true |
| Backend | PSA |
| Event type | `Events.OMConsumers.OMXFM.Request.PSA_UPDATE_WARRANTY_DEVICE` |
| Send pattern | `Event.Ext.sendEventImmediate(reqEvent)` — FIRE-AND-FORGET per material |
| RequestCount | `if(!isActResub) RequestCount++` inside material loop |
| Fan-in | `count(Response[ResponseCode suffix "000"]) == RequestCount` |
| Iteration | POU[].Subscriber[].MaterialInfo.Material[] AND ChildOU[].Subscriber[].MaterialInfo.Material[] |
| RefId pattern | `SubRefId + ":" + material.MatCode` (composite) |
| Skip guard | `psub.MaterialInfo != null` check |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| Material-level iteration | Unique: loops over Material[], not Subscriber/Account. One PSA request per material. |
| MaterialInfo null check | `if (psub.MaterialInfo != null)` — skips subscribers without devices |
| RefId composite key | `pSubRefId + ":" + material.MatCode` — per-material resubmit tracking |
| SALE_CHANNEL dispatch | SHOP→"1"; DEALER→"2"; else element omitted (no xsl:otherwise) |
| SALE-DATE format | `tib:format-dateTime("dd/MM/yyyy HH:mm:ss", RawSubmissionDate)` |
| Two key-info entries | IMEI-ID (MatSerial) + MAT-CODE (MatCode) — hardcoded names |

---

## §10 XSLT Field Mapping (ParentOU; ChildOU identical except $cMatRefId/$csub)

```text
createEvent → event
├── JMSPriority/JMSCorrelationID/OrderID        ← standard fields   [Conditional]
├── RefID               ← $pMatRefId (SubRefId+":"+MatCode)          [Always]
├── UserName/PassWord   ← [Credential-gated]
├── OrderType           ← OrderData.OrderType                        [Conditional]
└── payload → ns7:UpdateWarrantyDeviceReq
    ├── req-trx-id  ← OMXTrackingId                                 [Conditional]
    ├── user-info
    │   ├── channel-access ← "OMX"                                  [Hardcoded]
    │   ├── channel-code   ← DealerCode                             [Conditional]
    │   └── user-code      ← psub.SubscriberGeneralInfo.saleId      [Conditional]
    ├── key-info [1]: name="IMEI-ID", value=material.MatSerial       [Conditional]
    ├── key-info [2]: name="MAT-CODE", value=material.MatCode        [Conditional]
    └── params
        ├── param-name ← "ONLINE"                                   [Hardcoded]
        └── param-info
            ├── SALE-DATE    ← formatDateTime("dd/MM/yyyy HH:mm:ss", RawSubmissionDate) [Always]
            ├── SALE-CHANNEL ← SHOP→"1"; DEALER→"2"; else omitted   [Dispatch]
            ├── SALE-ORDER-ID← ExtInfo[SALE_ORDER_ID].Value          [Conditional]
            └── CAMPAIGN-CODE← ExtInfo[PRIVILEGE_CODE].Value         [Conditional]

NOTE: No CES field. RefID is composite matRefId, not Customer.RefId.
```

---

## §15 Function Dependency Tree

```text
Request_PSA_UPDATE_WARRANTY_DEVICE
├── for each ParentOU[p]:
│   ├── for each Subscriber[ps]:
│   │   └── if psub.MaterialInfo != null:
│   │       for each Material[pmat]:
│   │       ├── pMatRefId = pSubRefId + ":" + MatCode
│   │       ├── [skip if Response[pMatRefId AND CompletionStatus==2]]
│   │       └── if !reqSuccess AND PreExecCheck(GetXMLForSubscriberMaterialInfo):
│   │           ├── createEvent(PSA_UPDATE_WARRANTY_DEVICE, pMatRefId XSLT)
│   │           ├── sendEventImmediate(reqEvent)
│   │           ├── isSkipped = false
│   │           ├── if(!isActResub): RequestCount++
│   │           └── Logger REQ
│   └── for each ChildOU[c].Subscriber[cs]:
│       [same with cMatRefId/csub; GetXMLForSubscriberMaterialInChildOU]
├── if !isSkipped: GetActivityStatusString + SendDataToDB
└── else: SkipActivity("4")

Response_PSA_UPDATE_WARRANTY_DEVICE
├── createInstance(ResponseBase std 4) → currActivity.Response[n]
├── [NO write-back to order]
├── Logger RES
└── count("000") == RequestCount → "true"/"false"
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| No SALE-CHANNEL element for non-SHOP/DEALER — PSA may default silently | [MEDIUM] | Clarify PSA requirement; add default or document absence |
| SALE-DATE format "dd/MM/yyyy HH:mm:ss" — timezone not specified | [LOW] | Confirm PSA expected format; document timezone |
| Composite RefId must match response correlation | [LOW] | Document construction rule; add integration test |
| PRIVILEGE_CODE → CAMPAIGN-CODE naming mismatch | [LOW] | Document mapping; align with PSA team |

---

## §19 Response Message Rule

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | ResponseBase (std 4 fields) | Always |

No write-back to order data. Fan-in: `count(Response[ResponseCode suffix "000"]) == RequestCount`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
