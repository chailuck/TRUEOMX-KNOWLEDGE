# Request_KNOX_SAVE_DEVICE

> Registers a device with Knox via the shared KNOX_PROXY_SERVICE event (method="saveDevice") per qualifying subscriber offer; sends IMEI and brand-name sourced from offer ExtendedInfo populated by upstream PSA_GET_DEVICE_INFO.

**Backend:** Knox (saveDevice) | **Event:** KNOX_PROXY_SERVICE | **Pattern:** Per-offer fan-out | **forwardChain:** true | **Author:** DESKTOP-995HR2V | **Used in step:** 65

---

## §1 — Overview & Purpose

Sends one **Knox knoxProxyReq** (method=saveDevice) per qualifying subscriber offer. Uses the **shared** `KNOX_PROXY_SERVICE` event type — the operation is distinguished by the hardcoded `ns2:method = "saveDevice"` field, not the event type name. Device data (IMEI, brand) is sourced from the offer's ExtendedInfo fields written by the upstream **PSA_GET_DEVICE_INFO** response handler.

- **Event type (shared):** `Events.OMConsumers.OMXFM.Request.KNOX_PROXY_SERVICE` — not a dedicated KNOX_SAVE_DEVICE event
- **Method discriminator:** `ns2:method = "saveDevice"` (hardcoded in payload)
- **transactionId:** `concat(IMEI_KNOX, tib:timestamp())` — always sent; timestamp-only if IMEI_KNOX absent
- **IMEI (ns2:deviceUid):** `ExtendedInfo[IMEI_KNOX]/Value` — conditional on presence
- **Brand (ns2:brand):** `ExtendedInfo[BRAND_NAME]/Value` — conditional; set by PSA_GET_DEVICE_INFO
- **COU PreExecCheck:** `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo` — correct offer-level context
- **Response:** standard ResponseBase only — no write-back

> **Upstream dependency on PSA_GET_DEVICE_INFO:** `ns2:brand` is sourced from `ExtendedInfo[BRAND_NAME]`, written by the PSA_GET_DEVICE_INFO response handler. If PSA_GET_DEVICE_INFO was skipped or failed, BRAND_NAME will be absent and `ns2:brand` will not be sent to Knox.

> **[LOW] transactionId always sent even when IMEI_KNOX absent:** `concat(IMEI_KNOX_value, tib:timestamp())` always emits — produces just a timestamp string if IMEI_KNOX has no value.

> **[LOW] No PurgePendingRequestsBeforeResubmit:** Pending KNOX_PROXY_SERVICE events from a failed run remain in queue on resubmit.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_KNOX_SAVE_DEVICE.rule` | 151 lines |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_KNOX_SAVE_DEVICE.rulefunction` | 27 lines — standard, no write-back |
| Author | DESKTOP-995HR2V | Same author as PSA_GET_DEVICE_INFO |
| Priority | 5 | |
| forwardChain | true | |
| Backend event type | `Events.OMConsumers.OMXFM.Request.KNOX_PROXY_SERVICE` | Shared event — not KNOX_SAVE_DEVICE |
| Response event type | `Events.OMConsumers.OMXFM.Response.KNOX_PROXY_SERVICE` | Shared |
| Payload root | `ns2:knoxProxyReq` | Knox proxy request |
| Schema NS (ns2) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/Knox/KnoxProxyRequest.xsd` | |
| Operation discriminator | `ns2:method = "saveDevice"` | Hardcoded in payload |
| offerRefId format | `subRefId + ":" + offer.Soc + ":" + filter` | Same 3-part as PSA_GET_DEVICE_INFO |
| IMEI source | `ExtendedInfo[IMEI_KNOX]/Value` | |
| Brand source | `ExtendedInfo[BRAND_NAME]/Value` | Written by PSA_GET_DEVICE_INFO upstream |
| Dispatch | `Event.Ext.sendEventImmediate` | Per-offer fan-out |
| isActResub | `RequestCount > 0 && IsOrderResubmitted` | Suppresses RequestCount++ only |
| Resub purge | **ABSENT** | No PurgePendingRequestsBeforeResubmit |
| POU PreExecCheck builder | `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, offer.Soc, filter)` | Correct |
| COU PreExecCheck builder | `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, cSubRefId, offer.Soc, pOuRefId, filter)` | [CORRECT] unlike PSA_GET_DEVICE_INFO |
| Response concept | `Concepts.FM.Base.ResponseBase` | Standard 4 fields |
| Response write-back | None | Simple response handler |
| Fan-in | `RequestCount == successResponseCount` | success = ResponseCode suffix "000" |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "KNOX_SAVE_DEVICE"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "KNOX_SAVE_DEVICE"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

POU and COU XSLTs are identical — only `$offer` differs.

```text
createEvent
└── event
    ├── JMSPriority         ← $orderRequest/OrderPriority                     [Conditional]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId           [Conditional]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                 [Conditional]
    ├── RefID               ← $offerRefId                                     [Always]
    ├── UserName            ← $orderRequest/OrderData/User                    [Credential-gated: IsEnableUserPass='true']
    ├── PassWord            ← $orderRequest/OrderData/Password                [Credential-gated: IsEnableUserPass='true']
    ├── OrderType           ← $orderRequest/OrderData/OrderType               [Conditional]
    └── payload
        └── ns2:knoxProxyReq  (ns2=.../Knox/KnoxProxyRequest.xsd)
            ├── ns2:transactionId ← concat(ExtendedInfo[IMEI_KNOX]/Value, tib:timestamp())  [Always] timestamp-only if IMEI absent
            ├── ns2:deviceUid     ← ExtendedInfo[IMEI_KNOX]/Value                           [Conditional: xsl:if on IMEI_KNOX]
            ├── ns2:brand         ← ExtendedInfo[BRAND_NAME]/Value                          [Conditional: xsl:if on BRAND_NAME; set by PSA_GET_DEVICE_INFO]
            └── ns2:method        ← "saveDevice"                                             [Always] hardcoded operation discriminator
```

---

## §8 — System & Integration Dependencies

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | Knox (Samsung Knox device management) |
| Operation | knoxProxyReq / method = "saveDevice" |
| Schema NS (ns2) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/Knox/KnoxProxyRequest.xsd` |
| Event type | `KNOX_PROXY_SERVICE` (shared — used by multiple Knox FMs) |
| transactionId | `concat(IMEI_KNOX, tib:timestamp())` — unique per request |
| Correlation | RefID = subRefId:Soc:filter |

### §8.5 ExtendedInfo Fields

| Name | Direction | Source | Maps to |
|------|-----------|--------|---------|
| FE_OR_CCBS | INPUT | Offer | filter segment in offerRefId |
| IMEI_KNOX | INPUT | Offer (original order data) | ns2:transactionId prefix + ns2:deviceUid |
| BRAND_NAME | INPUT | Written by PSA_GET_DEVICE_INFO upstream | ns2:brand (conditional) |

---

## §15 — Function Dependency Tree

```text
Request_KNOX_SAVE_DEVICE (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── [NOTE: NO PurgePendingRequestsBeforeResubmit]
├── [POU loop p → ps → psof]:
│   ├── filter = XPath.evalAsString(offer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── offerRefId = pSubRefId + ":" + offer.Soc + ":" + filter
│   ├── [Resub guard]: scan Response[] for CompletionStatus==2 && ReferenceId==offerRefId
│   ├── [if !reqSuccess]:
│   │   ├── [if PreExecCheck]: GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, offer.Soc, filter)
│   │   ├── XPath.execute(PreExecCheck)
│   │   └── [if "true"]:
│   │       ├── Event.createEvent(KNOX_PROXY_SERVICE, XSLT: ns2:knoxProxyReq, method="saveDevice")
│   │       ├── Event.Ext.sendEventImmediate(reqEvent)
│   │       ├── isSkipped = false
│   │       ├── [if !isActResub]: RequestCount++
│   │       └── Event.Ext.sendEventImmediate(Logger: "Request Sent for KNOX_SAVE_DEVICE")
├── [COU loop p → c → cs → csof]:
│   ├── filter = XPath.evalAsString(offer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── offerRefId = cSubRefId + ":" + offer.Soc + ":" + filter
│   ├── [if PreExecCheck]: GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, cSubRefId, offer.Soc, pOuRefId, filter)
│   └── Event.createEvent(KNOX_PROXY_SERVICE, XSLT: ns2:knoxProxyReq, method="saveDevice")
├── [if !isSkipped]:
│   ├── Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch]: HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_KNOX_SAVE_DEVICE (rulefunction)
├── activityRes = Instance.createInstance(ResponseBase) {extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId}
├── currActivity.Response[] ← activityRes
├── Event.Ext.sendEventImmediate(Logger: "Response received for KNOX_SAVE_DEVICE", LOG_LEVEL=INFO)
├── successResponseCount = count(Response[tib:right(tib:trim(ResponseCode),3)="000"])
└── return (RequestCount == successResponseCount) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-offer fan-out across POU and COU. One KNOX_PROXY_SERVICE(saveDevice) per qualifying offer. |
| R2 | Operation identified by `ns2:method = "saveDevice"` in payload (shared KNOX_PROXY_SERVICE event type). |
| R3 | transactionId = concat(IMEI_KNOX, tib:timestamp()) — always sent; unique per invocation. |
| R4 | deviceUid = IMEI_KNOX value — conditional on IMEI_KNOX presence. |
| R5 | brand = BRAND_NAME value — conditional; BRAND_NAME populated by PSA_GET_DEVICE_INFO upstream. |
| R6 | offerRefId: `subRefId:offer.Soc:filter` — same format as PSA_GET_DEVICE_INFO. |
| R7 | COU PreExecCheck uses correct offer+filter context (GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo). |
| R8 | Response is standard ResponseBase — no write-back to working memory. |
| R9 | Fan-in: RequestCount == count(Response[ResponseCode suffix "000"]). |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Upstream dependency on BRAND_NAME from PSA_GET_DEVICE_INFO — absent if PSA step skipped or failed | [MEDIUM] | Verify Knox accepts absent brand; document PSA dependency in order flow |
| No PurgePendingRequestsBeforeResubmit — duplicate saveDevice calls possible on resubmit | [LOW] | Verify Knox idempotency for duplicate saveDevice with same deviceUid |
| transactionId produced as timestamp-only when IMEI_KNOX absent | [LOW] | Add guard if Knox requires IMEI prefix in transactionId |
| Shared KNOX_PROXY_SERVICE event — parallel Knox FMs could have response routing ambiguity | [LOW] | Confirm only one Knox FM active per order at a time |

---

## §19 — Response Message Rule (Response_KNOX_SAVE_DEVICE)

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object (Concepts.FM.Base.ResponseBase)
    ├── @extId          ← OMXUtils:generateTrackingID()           [Always]
    ├── ResponseCode    ← $eventResponse/ResponseCode             [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg              [Conditional] Msg→Message rename
    ├── CompletionStatus← $eventResponse/CompletionStatus         [Conditional]
    └── ReferenceId     ← $eventResponse/RefID                    [Conditional]
```

### §19.4 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` → "true"/"false" |
| LOG_LEVEL | MSG_LOG_LEVEL/INFO |
| No write-back | Response handler only creates ResponseBase — no offer.ExtendedInfo modifications |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
