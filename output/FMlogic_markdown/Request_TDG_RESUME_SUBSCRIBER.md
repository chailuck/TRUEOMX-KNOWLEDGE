# Request_TDG_RESUME_SUBSCRIBER

> Resume a TDG (TRUE Digital) subscriber — iterates MaterialInfo per subscriber, sends ResumeSubscriberRequest with reason RC (CCBS) or RR (non-CCBS).

**Priority:** 5 | **ForwardChain:** true | **Target:** TDG (TRUE Digital) | **Event:** TDG_RESUME_SUBSCRIBER | **Fan-in:** RequestCount == successResponseCount | **Used in RESTORE:** Step 39

---

## §1 — Overview & Purpose

Material-level FM (iterates `MaterialInfo.Material[]` per subscriber). Sends a `ResumeSubscriberRequest` for each material item. Used during RESTORE for IoT/TRUE Digital subscribers with `TR_SPECIAL_OFFER_IND=IOTBU`.

> **Logger OPERATION_NAME anomaly:** Both ParentOU and ChildOU variants use `"TDG_CREATE_SUBSCRIBER"` in the audit logger — not `"TDG_RESUME_SUBSCRIBER"`. This is a copy-paste naming error that will cause incorrect audit traces.

> **reason field:** Channel="CCBS" → `"RC"` (Resume-Collection); else → `"RR"` (Resume-Regular). 2-way xsl:choose.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_TDG_RESUME_SUBSCRIBER` |
| Priority | 5 |
| ForwardChain | true |
| Author | CHAYATORN P. |
| Target system | TDG (TRUE Digital Gateway) |
| JMS event type | `Events.OMConsumers.OMXFM.Request.TDG_RESUME_SUBSCRIBER` |
| Response concept | `Concepts.FM.Base.ResponseBase` |
| Fan-in method | `count(Response[ResponseCode suffix "000"]) == RequestCount` |
| Logger OPERATION_NAME ⚠ | `"TDG_CREATE_SUBSCRIBER"` (should be TDG_RESUME_SUBSCRIBER) |

---

## §3 — Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — ParentOU/ChildOU/Subscriber/MaterialInfo tree |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | PreExecCheck, Response[] |

**Key subscriber fields:**

| Field | Usage |
|-------|-------|
| `Subscriber.MaterialInfo.Material[]` | Primary iteration target — one request per material |
| `Material.MatCode` | RefID component (primary key) |
| `Material.MatSerial` | RefID fallback (when MatCode blank); also in payload |
| `Subscriber.MSISDN` | Payload `ns2:id` |
| `SubscriberOffers.RelatedOffersArray[ServiceType="85" and contains(SocProperties,'TR_CONTRACT_IND=Y')]/OfferName` | Payload `ns2:propositioncode` |
| `OrderData.Channel` | reason: "CCBS" → "RC" else "RR" |

---

## §4 — Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "TDG_RESUME_SUBSCRIBER"
orderRequest.ProcessFlow.NextActivityID == "TDG_RESUME_SUBSCRIBER"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 — Execution Flow

1. Check `isActResub` flag
2. Iterate ParentOU[p] → Subscriber[ps]; skip subscriber if MaterialInfo == null or Material.length == 0
3. For each Material[pmat]: build `pmatchRefId = pSubRefId + ":" + MatCode` (or MatSerial if MatCode blank)
4. Check if already successful (CompletionStatus==2) — skip if so
5. Evaluate PreExecCheck via `GetXMLForSubscriberMaterialInfo` (MatCode or MatSerial)
6. Build and send `TDG_RESUME_SUBSCRIBER` event immediately; increment RequestCount (if not resub)
7. Iterate ParentOU[p] → ChildOU[c] → Subscriber[cs] → Material[pmat]: same using `GetXMLForSubscriberMaterialInChildOU`
8. After all loops: status=PROCESSING + SendDataToDB, or SkipActivity("4")

---

## §7 — reason Field (2-way choose)

| Condition | reason | Meaning |
|-----------|--------|---------|
| `OrderData.Channel = 'CCBS'` | `"RC"` | Resume — Collection |
| Otherwise | `"RR"` | Resume — Regular |

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS

| Direction | Event | Destination | Purpose |
|-----------|-------|-------------|---------|
| `[OUTBOUND]` | `TDG_RESUME_SUBSCRIBER` | TDG service | Resume IoT/TRUE Digital subscriber per material |
| `[LOG]` | `Logger` | OMX audit | Per-material request trace (OPERATION_NAME="TDG_CREATE_SUBSCRIBER" ⚠) |

### §8.3 Backend API

| Field | Value |
|-------|-------|
| System | TDG (TRUE Digital Gateway) |
| Payload root | `ns2:ResumeSubscriberRequest` |
| Schema namespace | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/TDG/ResumeSubscriber.xsd` |

### §8.6 Global Variables

| Path | Usage |
|------|-------|
| `OMX_OM/WritePayload` | Payload flag in audit log |

---

## §9 — ResumeSubscriberRequest Payload

```xml
<ns2:ResumeSubscriberRequest>
  <ns2:serial>$material/MatSerial</ns2:serial>
  <ns2:id>$psub/MSISDN  <!-- or $csub/MSISDN for ChildOU --></ns2:id>
  <ns2:propositioncode>
    SubscriberOffers/RelatedOffersArray[ServiceType="85" and contains(SocProperties,'TR_CONTRACT_IND=Y')]/OfferName
  </ns2:propositioncode>
  <ns2:reason>
    <!-- Channel='CCBS' → "RC"  | else → "RR" -->
  </ns2:reason>
</ns2:ResumeSubscriberRequest>
```

---

## §10 — XSLT Field Mapping Tree

**Variant ① ParentOU Subscriber Material** (params: $orderRequest, $pmatchRefId, $material, $psub)

```text
createEvent
└── event
    ├── @extId           ← OMXUtils:generateTrackingID()                       [Always — unique per event]
    ├── JMSPriority      ← $orderRequest/OrderPriority                         [Always]
    ├── JMSCorrelationID ← $orderRequest/OrderData/OMXTrackingId               [Always]
    ├── OrderID          ← $orderRequest/OrderData/OrderID                     [Always]
    ├── RefID            ← $pmatchRefId                                        [Always]
    ├── OrderType        ← $orderRequest/OrderData/OrderType                   [Always]
    └── payload
        └── ns2:ResumeSubscriberRequest
            ├── ns2:serial          ← $material/MatSerial                     [Always]
            ├── ns2:id              ← $psub/MSISDN                            [Always]
            ├── ns2:propositioncode ← RelatedOffersArray[ServiceType=85, TR_CONTRACT_IND=Y]/OfferName  [Always]
            └── ns2:reason          ← Channel='CCBS'→"RC" | else→"RR"        [Always (2-way choose)]
```

*Variant ② (ChildOU): params use `$csub` instead of `$psub`. Payload structure identical.*

**Legend:** `←` = source XPath | Green = dynamic XPath | Orange = conditional/computed

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Helpers.BRMS.IsBlankOrStringNull(material.MatCode)` | Check if MatCode is blank; use MatSerial for refId and PreExecCheck if so |
| `Helpers.GetXMLForSubscriberMaterialInfo` | Serialise ParentOU subscriber material for PreExecCheck |
| `Helpers.GetXMLForSubscriberMaterialInChildOU` | Serialise ChildOU subscriber material for PreExecCheck |
| `Helpers.GetActivityStatusString` | Status string lookup |
| `Helpers.SendDataToDB` | Persist order state |
| `Helpers.SkipActivity` | Skip + advance |
| `Helpers.HandleActivityException` | Exception handler |

---

## §15 — Function Dependency Tree

```text
Request_TDG_RESUME_SUBSCRIBER
├── Helpers.BRMS.IsBlankOrStringNull(material.MatCode)           [MatCode/MatSerial branch]
├── Helpers.GetXMLForSubscriberMaterialInfo                       [PreExecCheck, ParentOU material]
├── Helpers.GetXMLForSubscriberMaterialInChildOU                  [PreExecCheck, ChildOU material]
├── Event.Ext.sendEventImmediate(TDG_RESUME_SUBSCRIBER)           [per material — parallel]
├── orderCurrentActivity.RequestCount++                           [manual counter]
├── Helpers.GetActivityStatusString("1", false)
├── Helpers.SendDataToDB
├── Helpers.SkipActivity("4")
└── Helpers.HandleActivityException                               [catch]
```

---

## §17 — Migration Notes

| ID | Requirement |
|----|-------------|
| R1 | Iterate Material[] per Subscriber (both ParentOU and ChildOU); skip subscriber with no MaterialInfo |
| R2 | RefID = `SubRefId:MatCode` (or `SubRefId:MatSerial` if MatCode blank) |
| R3 | reason: Channel="CCBS" → "RC"; else → "RR" |
| R4 | propositioncode from RelatedOffersArray[ServiceType=85, TR_CONTRACT_IND=Y] |
| R5 | Event extId set from OMXUtils:generateTrackingID() (unique per event, set on event not via rule) |
| R6 | Parallel fan-out; RequestCount incremented manually; fan-in via ResponseCode suffix "000" |

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Logger OPERATION_NAME = "TDG_CREATE_SUBSCRIBER" — wrong operation name in audit trail | `[HIGH]` | Fix in migration — correct to "TDG_RESUME_SUBSCRIBER" |
| propositioncode XPath may return empty if no matching offer | `[MEDIUM]` | Add guard; confirm TDG accepts empty propositioncode |
| MatCode blank → MatSerial fallback for refId | `[MEDIUM]` | Ensure consistency — both code paths produce valid unique refIds |

---

## §19 — Response Rule: Response_TDG_RESUME_SUBSCRIBER

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `OrderRequest` | Order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.TDG_RESUME_SUBSCRIBER` | Inbound TDG response |
| `currActivity` | `Activity` | Activity for response append |

### §19.3 ResponseBase Concept

```text
ResponseBase
├── @extId           ← OMXUtils.generateTrackingID()    [Always]
├── ResponseCode     ← $eventResponse/ResponseCode       [Conditional]
├── ResponseMessage  ← $eventResponse/ResponseMsg        [Conditional]
├── CompletionStatus ← $eventResponse/CompletionStatus   [Conditional]
└── ReferenceId      ← $eventResponse/RefID              [Conditional]
```

### §19.4 Fan-in Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Completion condition | `currActivity.RequestCount == successResponseCount` |
| Return "true" | All TDG resume calls returned ResponseCode ending in "000" |
| Return "false" | Still waiting for remaining responses |

> **Logger anomaly note:** Response audit log uses `OPERATION_NAME="TDG_RESUME_SUBSCRIBER"` correctly. Request audit log uses `"TDG_CREATE_SUBSCRIBER"`. Request and response log records will have mismatched OPERATION_NAME values in the audit trail.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
