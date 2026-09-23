# Request_TDG_CREATE_SUBSCRIBER

> Registers a subscriber device in TDG (Transaction Data Gateway) per material item. Fan-out is per Material under MaterialInfo — but RefID is subscriber-level (not material-level), creating a multi-material resubmit correlation risk.

**Backend:** TDG (CreateSubscriber) | **Pattern:** Per-material loop / Subscriber-level RefID | **RefID:** bare subRefId | **forwardChain:** true | **Author:** BNDT | **Used in step:** 71

---

## §1 — Overview & Purpose

Sends one **TDG CreateSubscriberRequest** per material item in the subscriber's `MaterialInfo.Material[]` array. Unlike PSA_UPDATE_DEVICE which uses a 2-part material-keyed RefID, this FM uses only the bare **subscriber RefId** as the correlation key. The effective date is computed at call time from the current Bangkok datetime. Package (ServiceType=70) and proposition code (ServiceType=85 with TR_CONTRACT_IND=Y) are cross-referenced from the subscriber's offer array.

- **Fan-out loop:** per `MaterialInfo.Material[]` (guarded: `MaterialInfo != null && Material@length > 0`)
- **RefID:** bare `subRefId` (POU: `pSubRefId`, COU: `cSubRefId`) — NOT material-keyed
- **createDate:** `DateTime.now()` → Bangkok timezone → `"yyyy-MM-dd'T'HH:mm:ssZ"`
- **ns:package:** offer with `ServiceType="70"` matching `MatSerialRefId = material.MatSerial`
- **ns:propositioncode:** offer's RelatedOffersArray with `ServiceType="85" and TR_CONTRACT_IND=Y`
- **Response:** standard ResponseBase only — no write-back

> **[MEDIUM] Subscriber-level RefID with per-material loop:** RefID = bare `subRefId` for every material. If a subscriber has N materials, all N loop iterations check `Response[ReferenceId == subRefId]`. Once the first material's TDG response arrives and is stored, the next material iteration on resubmit finds `reqSuccess=true` and skips. Materials 2..N would never be registered in TDG on resubmit. Fix: RefID should include `MatSerial` or `MatCode` to differentiate per-material (e.g., `subRefId + ":" + material.MatSerial`).

> **[LOW] Header fields emitted unconditionally:** JMSPriority, JMSCorrelationID, OrderID, and OrderType are sent without `xsl:if` guards — empty elements are emitted to TDG if these are blank. Other FMs use `xsl:if` guards on these fields.

> **[LOW] createDate is call-time (Bangkok timezone):** The effective date is generated from `DateTime.now()`, not from any order-submitted date field. Different materials processed in separate BE rule firings may get different effective timestamps; resubmits will produce a later effective date.

> **[INFO] event extId generated in XSLT:** Unlike most FMs that don't set `@extId` on the event, this XSLT sets `event/@extId = OMXUtils:generateTrackingID()`.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_TDG_CREATE_SUBSCRIBER.rule` | 161 lines |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_TDG_CREATE_SUBSCRIBER.rulefunction` | 27 lines — standard, no write-back |
| Author | BNDT | Same as MCS_REGISTER |
| Priority | 5 | |
| forwardChain | true | |
| Backend event | `Events.OMConsumers.OMXFM.Request.TDG_CREATE_SUBSCRIBER` | Dedicated |
| Payload root | `ns:CreateSubscriberRequest` | TDG schema |
| Schema NS (ns) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/TDG/CreateSubscriber.xsd` | |
| Fan-out pattern | Per-material loop (MaterialInfo.Material[]) | Same loop as PSA_UPDATE_DEVICE |
| Material guard | `MaterialInfo != null && Material@length > 0` | Both null and empty-array checked |
| RefID (POU) | `$pSubRefId` — bare subscriber RefId | `[MEDIUM]` Not material-keyed |
| RefID (COU) | `$cSubRefId` — bare subscriber RefId | `[MEDIUM]` Same issue |
| Resub guard | `Response[ReferenceId == subRefId]` | Subscriber-level — all materials share same check |
| createDate source | `DateTime.now()` → Bangkok → `"yyyy-MM-dd'T'HH:mm:ssZ"` | Call-time; not from order data |
| POU PreExecCheck builder | `GetXMLForSubscriber(orderRequest, pSubRefId)` | Subscriber-level |
| COU PreExecCheck builder | `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)` | Subscriber-level in ChildOU |
| JMS header guards | ABSENT — always emitted | `[LOW]` May emit empty elements |
| event/@extId | `OMXUtils:generateTrackingID()` | Set in XSLT — unusual vs other FMs |
| Response write-back | None | Standard ResponseBase |
| Resub purge | ABSENT | No PurgePendingRequestsBeforeResubmit |
| OPERATION_NAME | `"TDG_CREATE_SUBSCRIBER"` | Hardcoded |
| Fan-in | `RequestCount == successResponseCount` | success = ResponseCode suffix "000" |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "TDG_CREATE_SUBSCRIBER"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "TDG_CREATE_SUBSCRIBER"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §8 — System & Integration Dependencies

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | TDG (Transaction Data Gateway) |
| Operation | CreateSubscriberRequest — register subscriber device with TDG |
| Schema NS (ns) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/TDG/CreateSubscriber.xsd` |
| ns:serial | material.MatSerial — device IMEI |
| ns:id | subscriber.MSISDN — mobile number |
| ns:package | OfferName from ServiceType=70 offer matching MatSerialRefId |
| ns:cyclecode | OrderData.Customer.BillCycleNo |
| ns:effective | Call-time datetime in Bangkok timezone |
| ns:propositioncode | RelatedOffersArray[ServiceType=85, TR_CONTRACT_IND=Y]/OfferName |

### §8.4 Offer Cross-Reference Logic

| Field | XPath Filter | Purpose |
|-------|-------------|---------|
| ns:package | `SubscriberOffers[ServiceType="70"][MatSerialRefId=$material/MatSerial]/OfferName` | Primary service offer linked to this specific device serial |
| ns:propositioncode | `SubscriberOffers/RelatedOffersArray[ServiceType="85" and contains(SocProperties,"TR_CONTRACT_IND=Y")]/OfferName` | Contract proposition code from related offers (not filtered by material serial — could match multiple) |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

POU uses `$pSubRefId`/`$psub`; COU uses `$cSubRefId`/`$csub` — payload structure identical.

```text
createEvent
└── event
    ├── @extId              ← OMXUtils:generateTrackingID()                         [Always] Unusual — set in XSLT
    ├── JMSPriority         ← $orderRequest/OrderPriority                           [Always] No xsl:if guard — may emit empty
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId                 [Always] No guard
    ├── OrderID             ← $orderRequest/OrderData/OrderID                       [Always] No guard
    ├── RefID               ← $pSubRefId (POU) / $cSubRefId (COU)                  [Always] [MEDIUM] Bare subscriber RefId — not material-keyed
    ├── OrderType           ← $orderRequest/OrderData/OrderType                     [Always] No guard
    └── payload
        └── ns:CreateSubscriberRequest  (ns=.../TDG/CreateSubscriber.xsd)
            ├── ns:serial           ← $material/MatSerial                           [Always] IMEI / device serial number
            ├── ns:id               ← $psub/MSISDN (or $csub/MSISDN)               [Always] Mobile number
            ├── ns:package          ← SubscriberOffers[ServiceType="70"]
            │                          [MatSerialRefId=$material/MatSerial]/OfferName [Always] ServiceType=70 offer for this material
            ├── ns:cyclecode        ← $orderRequest/OrderData/Customer/BillCycleNo  [Always]
            ├── ns:effective        ← $createDate (DateTime.now() → Bangkok)        [Always] Call-time; not from order data
            └── ns:propositioncode  ← SubscriberOffers/RelatedOffersArray
                                       [ServiceType="85" and TR_CONTRACT_IND=Y]
                                       /OfferName                                   [Always] May be empty if no contract offer
```

---

## §15 — Function Dependency Tree

```text
Request_TDG_CREATE_SUBSCRIBER (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── [NOTE: NO Parameter guard / NO PurgePendingRequestsBeforeResubmit]
├── [POU loop p → ps]:
│   ├── if (psub.MaterialInfo != null && Material@length > 0):
│   │   ├── [Material loop pmat]:
│   │   │   ├── [Resub guard]: Response[ReferenceId == pSubRefId && CompletionStatus==2]
│   │   │   │   ← SUBSCRIBER-LEVEL: all materials share same check [MEDIUM]
│   │   │   ├── [PreExecCheck]: GetXMLForSubscriber(orderRequest, pSubRefId)
│   │   │   └── [if "true"]:
│   │   │       ├── createDate = DateTime.now() → Bangkok → "yyyy-MM-dd'T'HH:mm:ssZ"
│   │   │       ├── Event.createEvent(TDG_CREATE_SUBSCRIBER, XSLT: ns:CreateSubscriberRequest, RefID=$pSubRefId)
│   │   │       ├── Event.Ext.sendEventImmediate(reqEvent)
│   │   │       └── [if !isActResub]: RequestCount++
├── [COU loop p → c → cs]:
│   ├── if (csub.MaterialInfo != null && Material@length > 0):
│   │   ├── [Material loop cmat]:
│   │   │   ├── [Resub guard]: Response[ReferenceId == cSubRefId]   ← same subscriber-level check
│   │   │   ├── [PreExecCheck]: GetXMLForSubscriberInChildOU(cSubRefId, pOuRefId)
│   │   │   └── Event.createEvent(TDG_CREATE_SUBSCRIBER, XSLT: RefID=$cSubRefId)
├── [if !isSkipped]: SendDataToDB / SkipActivity
└── [catch]: HandleActivityException

Response_TDG_CREATE_SUBSCRIBER (rulefunction)
├── activityRes = Instance.createInstance(ResponseBase){extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId}
├── currActivity.Response[] ← activityRes
├── Logger: OPERATION_NAME="TDG_CREATE_SUBSCRIBER"
├── successResponseCount = count(Response[tib:right(tib:trim(ResponseCode),3)="000"])
└── return (RequestCount == successResponseCount) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-material loop across POU and COU. One TDG CreateSubscriberRequest per Material[] entry where MaterialInfo != null && length > 0. |
| R2 | RefID = bare subRefId (as-coded). Review: if TDG is truly per-subscriber, loop should be at subscriber level not material level; if per-material, RefID needs material key. |
| R3 | ns:serial = material.MatSerial (IMEI); ns:id = subscriber.MSISDN (always sent). |
| R4 | ns:package = OfferName from SubscriberOffers[ServiceType="70"][MatSerialRefId=material.MatSerial]. |
| R5 | ns:cyclecode = OrderData.Customer.BillCycleNo. |
| R6 | ns:effective = current datetime in Bangkok timezone (yyyy-MM-dd'T'HH:mm:ssZ) at call time. |
| R7 | ns:propositioncode = RelatedOffersArray[ServiceType="85" and TR_CONTRACT_IND=Y]/OfferName. May be empty/multi-valued if no/multiple contract offers. |
| R8 | PreExecCheck uses subscriber-level context (GetXMLForSubscriber / GetXMLForSubscriberInChildOU). |
| R9 | event/@extId set via OMXUtils:generateTrackingID() in XSLT (unusual for this FM family). |
| R10 | Response: standard ResponseBase — no write-back. Fan-in: RequestCount == successResponseCount. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Subscriber-level RefID with per-material loop — multi-material resubmit skips materials 2..N | [MEDIUM] | Fix: RefID = subRefId + ":" + material.MatSerial (match PSA_UPDATE_DEVICE pattern), or confirm TDG is truly subscriber-level and collapse to per-subscriber loop |
| JMS header fields emitted unconditionally — may send empty elements to TDG | [LOW] | Add xsl:if guards consistent with other FMs; verify TDG accepts empty JMS headers |
| createDate from call-time (not order data) — resubmits produce different effective date | [LOW] | Consider using SubmissionDate or a stable order-level date field; verify TDG idempotency on different effective dates |
| ns:propositioncode may match multiple RelatedOffersArray entries | [LOW] | Verify only one contract offer can match; add specific qualifier if needed |
| No PurgePendingRequestsBeforeResubmit | [LOW] | Verify TDG CreateSubscriber idempotency for same serial+MSISDN |

---

## §19 — Response Message Rule (Response_TDG_CREATE_SUBSCRIBER)

### §19.3 ResponseBase Construction

```text
createObject
└── object (Concepts.FM.Base.ResponseBase)
    ├── @extId           ← OMXUtils:generateTrackingID()    [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode      [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg       [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus  [Conditional]
    └── ReferenceId      ← $eventResponse/RefID             [Conditional]
                            Stores bare subRefId — shared across all materials of subscriber
```

### §19.4 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Write-back | None |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
