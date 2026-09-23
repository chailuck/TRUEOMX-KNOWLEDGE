# Request_MCS_REGISTER

> Registers a device/subscriber offer with MCS per qualifying SubscriberOffer — sends full device, subscriber, address, and channel identity to MCS registerReq; per-offer fan-out across POU and COU.

**Backend:** MCS (Register) | **Pattern:** Per-offer fan-out | **forwardChain:** true | **Author:** BNDT | **Used in step:** 63

---

## §1 — Overview & Purpose

Sends one **MCS registerReq** call per qualifying subscriber offer to register a device and subscriber combination with MCS. Traverses both POU and COU subscribers and their SubscriberOffers. Key data sourced from: offer's `MatSerialRefId` cross-reference to subscriber's `MaterialInfo.Material[]` (device), billing address via `AccountRefId→Account.BillingArrangementAddress`, and customer identity fields.

- **offerRefId:** `subRefId + ":" + OfferName + ":" + filter` — unique key includes FE_OR_CCBS filter value
- **Device lookup:** `MaterialInfo/Material[MatSerial == psubOffer.MatSerialRefId]` → imei, handset, rrp
- **Dates:** both `purchase_date` and `activation_date` = `RawSubmissionDate` (ISO 8601 with timezone)
- **subscriber_type:** CustomerTypeInfo/Type == 73 → "POS"; else → "PRE"
- **Address always sent** (concat with space — produces " " for blank fields)
- **No PurgePendingRequestsBeforeResubmit** — resub guard (CompletionStatus==2) protects already-done offers only
- **ResponseBase** (standard minimal concept) — no MCS-specific response fields

> **[MEDIUM] No PurgePendingRequestsBeforeResubmit:** isActResub suppresses RequestCount++ but does not purge pending requests. On resubmit, any pending (not yet responded) events from the original run remain in the queue alongside new events for unfinished offers.

> **[LOW] Address always emitted as concat:** address_1/2/3 fields use `concat(A, " ", B)` without an exists() guard. If both parts are blank, the field is sent as a single space `" "` rather than being omitted. MCS must tolerate empty address fields.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_MCS_REGISTER.rule` | 146 lines |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_MCS_REGISTER.rulefunction` | 27 lines |
| Author | BNDT | |
| Priority | 5 | |
| forwardChain | true | |
| Traversal unit | POU Subscriber + COU Subscriber → SubscriberOffers | Per-offer fan-out |
| Backend event | `Events.OMConsumers.OMXFM.Request.MCS_REGISTER` | |
| Payload root | `ns7:registerReq` | MCS register request |
| Schema NS (ns7) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/RegisterRequest.xsd` | |
| offerRefId format | `subRefId + ":" + OfferName + ":" + filter` | Unique: includes FE_OR_CCBS value; no OU RefIds |
| Device lookup | `MaterialInfo/Material[MatSerial == MatSerialRefId]` | Offer's MatSerialRefId selects material |
| Dispatch | `Event.Ext.sendEventImmediate` | Per-offer immediate fan-out |
| isActResub | `RequestCount > 0 && IsOrderResubmitted` | Suppresses RequestCount++ only; no purge |
| Resub purge | **ABSENT** | No PurgePendingRequestsBeforeResubmit called |
| Per-offer resub guard | `CompletionStatus==2 && ReferenceId==offerRefId` | Skips already-successful offers |
| PreExecCheck builder | `GetXMLForSubscriberOfferFilterWithExtendedInfo(…, offer.OfferName, filter)` | Uses OfferName (not Soc) |
| Credential gate | `IsEnableUserPass == 'true'` | UserName/PassWord conditional on global variable |
| Response concept | `Concepts.FM.Base.ResponseBase` | Standard minimal — no MCS-specific fields |
| Fan-in | `RequestCount == successResponseCount` | success = ResponseCode suffix "000" |
| Skip condition | `isSkipped == true` after loop | SkipActivity("4") |
| Post-loop | Status="1" + SendDataToDB | Once after full traversal |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "MCS_REGISTER"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "MCS_REGISTER"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §4 — offerRefId Construction (Unique Key Format)

| Scope | Expression | Example |
|-------|-----------|---------|
| POU | `pSubRefId + ":" + psubOffer.OfferName + ":" + filter` | `SUB001:OFFER_NAME:FE` |
| COU | `cSubRefId + ":" + csubOffer.OfferName + ":" + filter` | `SUB002:OFFER_NAME:CCBS` |

> **Key design note:** The offerRefId includes the `FE_OR_CCBS` filter value as its third segment. This means two offers with the same OfferName but different FE_OR_CCBS values produce different offerRefIds — and trigger separate MCS registration calls. Unlike most other FMs, this key does NOT include any OU RefId.

---

## §5 — Device Material Lookup (MatSerialRefId)

The offer's `MatSerialRefId` field is used to look up the device from the subscriber's `MaterialInfo.Material[]` array:

```xpath
MaterialInfo/Material[MatSerial == $psubOffer/MatSerialRefId]
```

| MCS field | Source | Condition |
|-----------|--------|-----------|
| `ns7:imei` | `Material[…].MatSerial` | If match exists |
| `ns7:handset` | `Material[…].MatCode` | If match exists |
| `ns7:rrp` | `Material[…].MatPrice` | If match exists |

> If `MatSerialRefId` does not match any Material entry, all three device fields (imei, handset, rrp) are omitted — the registration proceeds without device information.

---

## §6 — subscriber_type Mapping

| Condition | Value sent |
|-----------|------------|
| `CustomerTypeInfo/Type == 73` | `"POS"` (Point of Sale) |
| else | `"PRE"` |

> Always emitted — no `xsl:if` guard. `subscriber_type` is a mandatory MCS field.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

Both POU and COU XSLTs are structurally identical; only the subscriber/offer parameter names differ.
Address lookup: `Account[$sub/AccountRefId == RefId]/BillingArrangementAddress`

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                              [Conditional]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId                   [Conditional]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID                          [Conditional]
    ├── RefID                    ← $offerRefId                                              [Always]
    ├── UserName                 ← $orderRequest/OrderData/User                             [Credential-gated: IsEnableUserPass='true']
    ├── PassWord                 ← $orderRequest/OrderData/Password                         [Credential-gated: IsEnableUserPass='true']
    ├── OrderType                ← $orderRequest/OrderData/OrderType                        [Conditional]
    └── payload
        └── ns7:registerReq
            ├── ns7:transaction_id          ← $orderRequest/OrderData/OMXTrackingId         [Conditional]
            ├── ns7:requestor_id            ← ExtendedInfo[FE_LOGIN_USER]/Value             [Conditional]
            ├── ns7:channel                 ← $orderRequest/OrderData/Channel               [Conditional]
            ├── ns7:channel_code            ← $orderRequest/OrderData/DealerCode            [Conditional]
            ├── ns7:channel_name            ← ExtendedInfo[DEALER_NAME]/Value               [Conditional]
            ├── ns7:imei                    ← Material[MatSerial==MatSerialRefId]/MatSerial  [Conditional]
            ├── ns7:handset                 ← Material[MatSerial==MatSerialRefId]/MatCode    [Conditional]
            ├── ns7:purchase_date           ← tib:format-dateTime("yyyy-MM-dd'T'HH:mm:ssXXX", RawSubmissionDate)  [Always]
            ├── ns7:rrp                     ← Material[MatSerial==MatSerialRefId]/MatPrice   [Conditional]
            ├── ns7:msisdn                  ← $psub/MSISDN                                  [Conditional]
            ├── ns7:subscriber_type         ← "POS" (Type=73) / "PRE" (else)               [Always]
            ├── ns7:subscriber_contact_lang ← $psub/SubscriberGeneralInfo/Language          [Conditional]
            ├── ns7:activation_date         ← tib:format-dateTime("yyyy-MM-dd'T'HH:mm:ssXXX", RawSubmissionDate)  [Always] same as purchase_date
            ├── ns7:id_type                 ← Customer/CustomerName/IdentificationType       [Conditional]
            ├── ns7:id_number               ← Customer/CustomerName/Identification           [Conditional]
            ├── ns7:first_name              ← Customer/CustomerName/FirstName                [Conditional]
            ├── ns7:last_name               ← Customer/CustomerName/LastName                 [Conditional]
            ├── ns7:address_1               ← concat(HouseNo, " ", Moo)                     [Always] no exists() guard — emits " " if both blank
            ├── ns7:address_2               ← concat(Soi, " ", StreetName)                  [Always]
            ├── ns7:address_3               ← concat(Tumbon, " ", Amphur)                   [Always]
            ├── ns7:address_4               ← BillingArrangementAddress/City                [Always]
            ├── ns7:postal_code             ← BillingArrangementAddress/Zip                 [Conditional]
            ├── ns7:pack_code               ← ExtendedInfo[PROGRAM_CODE]/Value              [Conditional]
            └── ns7:flow_id                 ← ExtendedInfo[FLOW_ID]/Value                   [Conditional]
```

---

## §8 — System & Integration Dependencies

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | MCS (Material/Content System — device registration) |
| Operation | registerReq |
| Schema NS (payload) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/RegisterRequest.xsd` |
| Correlation | RefID = `subRefId:OfferName:filter` |

### §8.5 ExtendedInfo Fields

| Name | Scope | Maps to | Required? |
|------|-------|---------|-----------|
| FE_OR_CCBS | SubscriberOffers | filter (part of offerRefId) | Optional (blank if absent) |
| FE_LOGIN_USER | OrderData | ns7:requestor_id | Optional |
| DEALER_NAME | OrderData | ns7:channel_name | Optional |
| PROGRAM_CODE | SubscriberOffers | ns7:pack_code | Optional |
| FLOW_ID | OrderData | ns7:flow_id | Optional |

---

## §15 — Function Dependency Tree

```text
Request_MCS_REGISTER (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── [NOTE: NO PurgePendingRequestsBeforeResubmit]
├── [POU loop p → ps → psof]:
│   ├── filter = XPath.evalAsString(psubOffer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── offerRefId = pSubRefId + ":" + psubOffer.OfferName + ":" + filter
│   ├── [Resub guard]: scan Response[] for CompletionStatus==2 && ReferenceId==offerRefId
│   ├── [if !reqSuccess]:
│   │   ├── [if PreExecCheck]: GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, psubOffer.OfferName, filter)
│   │   ├── XPath.execute(PreExecCheck)
│   │   └── [if "true"]:
│   │       ├── Event.createEvent(MCS_REGISTER, XSLT: ns7:registerReq, psub/psubOffer)
│   │       ├── Event.Ext.sendEventImmediate(reqEvent)
│   │       ├── isSkipped = false
│   │       ├── [if !isActResub]: RequestCount++
│   │       └── Event.Ext.sendEventImmediate(Logger)
├── [COU loop p → c → cs → csof]:
│   ├── filter = XPath.evalAsString(csubOffer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── offerRefId = cSubRefId + ":" + csubOffer.OfferName + ":" + filter
│   ├── [if PreExecCheck]: GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, cSubRefId, csubOffer.OfferName, pOuRefId, filter)
│   └── Event.createEvent(MCS_REGISTER, XSLT: ns7:registerReq, csub/csubOffer)
├── [if !isSkipped]:
│   ├── Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch]: HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_MCS_REGISTER (rulefunction)
├── activityRes = Instance.createInstance(ResponseBase) {
│       @extId=generateTrackingID(), ResponseCode, ResponseMessage(←ResponseMsg),
│       CompletionStatus, ReferenceId(←RefID) }
├── currActivity.Response[] ← activityRes
├── Event.Ext.sendEventImmediate(Logger: "Response received for MCS_REGISTER", LOG_LEVEL=INFO)
├── successResponseCount = count(Response[tib:right(tib:trim(ResponseCode),3)="000"])
└── return (RequestCount == successResponseCount) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-offer fan-out across POU and COU subscribers. One MCS registerReq per qualifying offer. |
| R2 | offerRefId format: `subRefId:OfferName:filter` — includes FE_OR_CCBS value; no OU RefIds. |
| R3 | Device fields (imei, handset, rrp) resolved by `MaterialInfo/Material[MatSerial==MatSerialRefId]`. Omitted if no match. |
| R4 | purchase_date and activation_date both = `RawSubmissionDate` formatted as ISO 8601 with timezone offset. |
| R5 | subscriber_type: CustomerTypeInfo/Type==73 → "POS"; else → "PRE". Always emitted. |
| R6 | Address fields address_1/2/3 always emitted via concat (may be " " if both parts empty); address_4 always emitted; postal_code conditional. |
| R7 | Address account lookup: `Account[$sub/AccountRefId == RefId]/BillingArrangementAddress`. |
| R8 | No PurgePendingRequestsBeforeResubmit — resub guard (CompletionStatus==2) only. |
| R9 | Response uses standard ResponseBase concept (no MCS-specific fields). Fan-in: RequestCount == count(Response[ResponseCode ends in "000"]). |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| No PurgePendingRequestsBeforeResubmit — pending events from failed run may re-arrive on resubmit | [MEDIUM] | Add PurgePendingRequestsBeforeResubmit if MCS cannot handle duplicate registration attempts |
| address_1/2/3 always emitted as concat — produces " " when both parts blank | [LOW] | Verify MCS tolerates whitespace-only address values; add exists() guard if needed |
| purchase_date == activation_date (both use RawSubmissionDate) — no separate activation date sourcing | [LOW] | Verify MCS intent — if activation_date should differ, source from offer EffectiveDate |
| offerRefId embeds FE_OR_CCBS value — if the same offer is processed with different filter values across resub attempts, correlation may fail | [LOW] | Ensure FE_OR_CCBS is stable across retries for the same offer |

---

## §19 — Response Message Rule (Response_MCS_REGISTER)

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object (Concepts.FM.Base.ResponseBase)
    ├── @extId         ← OMXUtils:generateTrackingID()                    [Always]
    ├── ResponseCode   ← $eventResponse/ResponseCode                      [Conditional]
    ├── ResponseMessage← $eventResponse/ResponseMsg                       [Conditional] field rename Msg→Message
    ├── CompletionStatus ← $eventResponse/CompletionStatus                [Conditional]
    └── ReferenceId    ← $eventResponse/RefID                             [Conditional]
```

### §19.4 Response Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` → "true"/"false" |
| LOG_LEVEL | MSG_LOG_LEVEL/INFO |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
