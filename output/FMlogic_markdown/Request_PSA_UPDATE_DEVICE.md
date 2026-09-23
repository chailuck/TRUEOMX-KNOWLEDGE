# Request_PSA_UPDATE_DEVICE

> Updates device registration record in PSA per material item (IMEI-ID + MAT_CODE). Fan-out is per Material under MaterialInfo — not per offer. Param-name resolved by priority: PARTNER ExtendedInfo → IoT (CLOUD-SERVICE) → Knox (KNOX) → TPC-ASURION.

**Backend:** PSA (UpdateDevice) | **Pattern:** Per-material fan-out | **RefID:** subRefId:MatCode (2-part) | **forwardChain:** true | **Used in step:** 70

---

## §1 — Overview & Purpose

Sends one **PSA UpdateDeviceReq** per material item in the subscriber's `MaterialInfo.Material[]` array. This is the only FM in the Knox/PSA cluster that fans out **per material** rather than per offer. The 2-part RefID (`subRefId:MatCode`) is used for request correlation and resubmit guard. `deviceStatus` and `srType` are read from ProcessConfig Parameters inside the loop.

- **Fan-out:** per `psub.MaterialInfo.Material[]` (guarded: `if (psub.MaterialInfo != null)`)
- **RefID:** `subRefId + ":" + material.MatCode` (2-part — no filter/SOC segment)
- **Payload root:** `ns8:UpdateDeviceReq` — PSA UpdateDevice schema
- **Key identifiers:** IMEI-ID = MatSerial, MAT_CODE = MatCode
- **param-name priority:** PARTNER > CLOUD-SERVICE > KNOX > TPC-ASURION (see §7)
- **SR-TYPE priority:** sub.ExtendedInfo[SR_TYPE] > ProcessConfig srType Parameter
- **Response:** standard ResponseBase only — no write-back

> **[MEDIUM] param-name may be empty:** If none of the four priority conditions match (no PARTNER, no IOTBU offer, no IMEI_KNOX, no TPC_REFNO), `ns8:param-name` is omitted entirely — the fallback `xsl:otherwise` contains only the inner `xsl:choose` with no final default.

> **[LOW] No explicit Parameter guard:** Unlike Knox FMs, there is no upfront `Parameter@length == 0` check. `deviceStatus`/`srType` will be empty strings if ProcessConfig has no Parameters.

> **[INFO] Both POU and COU RefIDs are correct:** POU sends `$pMatRefId`, COU sends `$cMatRefId` — both match the resub guard. No RefID bug.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_PSA_UPDATE_DEVICE.rule` | 170 lines |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_PSA_UPDATE_DEVICE.rulefunction` | 27 lines — standard, no write-back |
| Priority | 5 | |
| forwardChain | true | |
| Backend event | `Events.OMConsumers.OMXFM.Request.PSA_UPDATE_DEVICE` | Dedicated |
| Payload root | `ns8:UpdateDeviceReq` | PSA UpdateDevice |
| Schema NS (ns8) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/PSA/UpdateDevice.xsd` | |
| **Fan-out pattern** | **Per-Material** — `MaterialInfo.Material[]` | Unique — NOT per-offer |
| Material guard | `if (psub.MaterialInfo != null)` | Skips subscribers without MaterialInfo |
| RefID format | `subRefId + ":" + material.MatCode` | 2-part |
| POU RefID | `$pMatRefId` | `[CORRECT]` |
| COU RefID | `$cMatRefId` | `[CORRECT]` |
| deviceStatus source | `GetActivityParameterValueFromKey(orderCurrentActivity, "deviceStatus")` | After PreExecCheck |
| srType source | `GetActivityParameterValueFromKey(orderCurrentActivity, "srType")` | Overridden by ExtendedInfo[SR_TYPE] |
| Parameter guard | ABSENT | `[LOW]` No explicit check |
| POU PreExecCheck builder | `GetXMLForSubscriberMaterialInfo(orderRequest, pSubRefId, MatCode\|MatSerial)` | Material-level |
| COU PreExecCheck builder | `GetXMLForSubscriberMaterialInChildOU(orderRequest, cSubRefId, pOuRefId, MatCode\|MatSerial)` | Material-level in ChildOU |
| Response write-back | None | Standard ResponseBase |
| Resub purge | ABSENT | No PurgePendingRequestsBeforeResubmit |
| OPERATION_NAME | `"PSA_UPDATE_DEVICE"` | Hardcoded |
| Fan-in | `RequestCount == successResponseCount` | success = ResponseCode suffix "000" |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "PSA_UPDATE_DEVICE"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "PSA_UPDATE_DEVICE"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §7 — param-name Priority Logic (ns8:param-name)

| Priority | Condition | param-name value |
|----------|-----------|-----------------|
| 1 (highest) | `string-length(sub.ExtendedInfo[PARTNER]/Value) > 0` | PARTNER value (subscriber-level) |
| 2 | `SubscriberOffers[SocProperties contains "TR_SPECIAL_OFFER_IND=IOTBU"]/RelatedOffersArray[MatSerialRefId == material.MatSerial]` | `"CLOUD-SERVICE"` |
| 3 | `string-length(SubscriberOffers/ExtendedInfo[IMEI_KNOX]/Value) > 0` | `"KNOX"` |
| 4 | `string-length(OrderData/ExtendedInfo[TPC_REFNO]/Value) > 0` | `"TPC-ASURION"` |
| 5 (default) | None of the above | *ns8:param-name omitted* `[MEDIUM]` |

The IOTBU check (priority 2) cross-references both the offer's `SocProperties` and the offer's `RelatedOffersArray[MatSerialRefId == material.MatSerial]`.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

POU uses `$pMatRefId`/`$psub`; COU uses `$cMatRefId`/`$csub` — payload structure identical.

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                         [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId               [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                     [Conditional]
    ├── RefID                ← $pMatRefId / $cMatRefId (subRefId:MatCode)          [Always] Both correct
    ├── UserName / PassWord  ← OrderData/User, Password                            [Credential-gated]
    ├── OrderType            ← $orderRequest/OrderData/OrderType                   [Conditional]
    └── payload
        └── ns8:UpdateDeviceReq  (ns8=.../PSA/UpdateDevice.xsd)
            ├── ns8:req-trx-id   ← OMXTrackingId                                  [Always]
            ├── ns8:user-info
            │   ├── ns8:app-user      ← "OMX" (hardcoded)                         [Always]
            │   ├── ns8:channel-access← if DealerCode: "OMX-"||Channel; else "OMX"[Always]
            │   ├── ns8:channel-code  ← DealerCode                                [Always]
            │   ├── ns8:user-code     ← sub.SubscriberGeneralInfo.saleId          [Conditional]
            │   └── ns8:user-login    ← "ESD_OMXMOBI" (hardcoded)                 [Always]
            ├── ns8:key-info [1]
            │   ├── ns8:name  ← "IMEI-ID" (hardcoded)                             [Always]
            │   └── ns8:value ← $material/MatSerial                               [Always]
            ├── ns8:key-info [2]
            │   ├── ns8:name  ← "MAT_CODE" (hardcoded)                            [Always]
            │   └── ns8:value ← $material/MatCode                                 [Always]
            └── ns8:params
                ├── ns8:param-name  ← PARTNER OR "CLOUD-SERVICE" OR "KNOX" OR "TPC-ASURION" [Conditional: priority cascade]
                └── ns8:param-info
                    ├── ns8:REF-NUMBER       ← TPC_REFNO OR OMXTrackingId         [Conditional]
                    ├── ns8:SR-TYPE          ← ExtendedInfo[SR_TYPE] OR $srType   [Conditional]
                    ├── ns8:SR-COMPLETION-DATE← format-dateTime("dd/MM/yyyy HH:mm:ss", SubmissionDate) [Always]
                    ├── ns8:DEVICE-STATUS    ← $deviceStatus param                [Conditional: xsl:if]
                    ├── ns8:MOBILE-NUMBER    ← sub.MSISDN                         [Conditional]
                    └── ns8:NEW-IMEI-ID      ← ExtendedInfo[NEW_MAT_SERIAL]/Value [Conditional: string-length>0]
```

---

## §8 — System & Integration Dependencies

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | PSA (Partner Service Access) |
| Operation | UpdateDeviceReq — update device service/partner registration |
| Schema NS (ns8) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/PSA/UpdateDevice.xsd` |
| Key 1 | IMEI-ID = material.MatSerial |
| Key 2 | MAT_CODE = material.MatCode |
| app-user | "OMX" (hardcoded) |
| user-login | "ESD_OMXMOBI" (hardcoded) |

### §8.4 Working Memory / ExtendedInfo Fields

| Name | Level | Direction | Purpose |
|------|-------|-----------|---------|
| PARTNER | Subscriber | INPUT | Explicit partner name (highest priority for ns8:param-name) |
| IMEI_KNOX | Offer | INPUT | Determines "KNOX" param-name if present on any offer |
| SR_TYPE | Subscriber | INPUT | Overrides ProcessConfig srType for ns8:SR-TYPE |
| NEW_MAT_SERIAL | Subscriber | INPUT | ns8:NEW-IMEI-ID (device swap scenario) |
| TPC_REFNO | OrderData | INPUT | Determines "TPC-ASURION" param-name; ns8:REF-NUMBER source |

---

## §15 — Function Dependency Tree

```text
Request_PSA_UPDATE_DEVICE (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── [NOTE: NO Parameter guard / NO PurgePendingRequestsBeforeResubmit]
├── [POU loop p → ps]:
│   ├── if (psub.MaterialInfo != null):
│   │   ├── [Material loop pmat]:
│   │   │   ├── pMatRefId = pSubRefId + ":" + material.MatCode
│   │   │   ├── [Resub guard]: Response[ReferenceId == pMatRefId && CompletionStatus==2]
│   │   │   ├── [PreExecCheck]:
│   │   │   │   ├── if MatCode not blank: GetXMLForSubscriberMaterialInfo(pSubRefId, MatCode)
│   │   │   │   └── else: GetXMLForSubscriberMaterialInfo(pSubRefId, MatSerial)
│   │   │   └── [if "true"]:
│   │   │       ├── deviceStatus = GetActivityParameterValueFromKey(..."deviceStatus")
│   │   │       ├── srType      = GetActivityParameterValueFromKey(..."srType")
│   │   │       ├── Event.createEvent(PSA_UPDATE_DEVICE, XSLT: ns8:UpdateDeviceReq, RefID=$pMatRefId)
│   │   │       ├── Event.Ext.sendEventImmediate(reqEvent)
│   │   │       └── [if !isActResub]: RequestCount++
├── [COU loop p → c → cs]:
│   ├── if (csub.MaterialInfo != null):
│   │   ├── [Material loop cmat]:
│   │   │   ├── cMatRefId = cSubRefId + ":" + material.MatCode
│   │   │   ├── [PreExecCheck]:
│   │   │   │   ├── if MatCode: GetXMLForSubscriberMaterialInChildOU(cSubRefId, pOuRefId, MatCode)
│   │   │   │   └── else: GetXMLForSubscriberMaterialInChildOU(cSubRefId, pOuRefId, MatSerial)
│   │   │   └── Event.createEvent(PSA_UPDATE_DEVICE, XSLT: ns8:UpdateDeviceReq, RefID=$cMatRefId)
├── [if !isSkipped]: SendDataToDB / SkipActivity
└── [catch]: HandleActivityException

Response_PSA_UPDATE_DEVICE (rulefunction)
├── activityRes = Instance.createInstance(ResponseBase){...}
├── currActivity.Response[] ← activityRes
├── Logger: OPERATION_NAME="PSA_UPDATE_DEVICE"
├── successResponseCount = count(Response[tib:right(tib:trim(ResponseCode),3)="000"])
└── return (RequestCount == successResponseCount) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-material fan-out across POU and COU. One PSA UpdateDeviceReq per Material[] entry where MaterialInfo != null. |
| R2 | RefID = `subRefId + ":" + material.MatCode` (2-part). Both POU and COU correct. |
| R3 | Key identifiers: IMEI-ID = material.MatSerial; MAT_CODE = material.MatCode (always sent). |
| R4 | param-name priority: PARTNER (1) → "CLOUD-SERVICE" if IOTBU offer match (2) → "KNOX" if any IMEI_KNOX (3) → "TPC-ASURION" if TPC_REFNO (4) → omitted. |
| R5 | SR-TYPE priority: sub.ExtendedInfo[SR_TYPE] if not blank; else ProcessConfig srType Parameter. |
| R6 | REF-NUMBER priority: TPC_REFNO if present; else OMXTrackingId. |
| R7 | SR-COMPLETION-DATE = SubmissionDate formatted "dd/MM/yyyy HH:mm:ss" (always sent). |
| R8 | DEVICE-STATUS from ProcessConfig Parameter[deviceStatus] (conditional on non-empty). |
| R9 | NEW-IMEI-ID from sub.ExtendedInfo[NEW_MAT_SERIAL] (device swap scenario). |
| R10 | PreExecCheck uses material-level context: MatCode preferred, MatSerial if MatCode blank. |
| R11 | Response: standard ResponseBase — no write-back. Fan-in: RequestCount == successResponseCount. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| param-name omitted if no priority condition matches | [MEDIUM] | Add explicit default param-name or document PSA tolerance for absent param-name |
| No Parameter guard — deviceStatus/srType empty if ProcessConfig has no Parameters | [LOW] | PSA should handle absent DEVICE-STATUS (conditional); confirm SR-TYPE optionality |
| No PurgePendingRequestsBeforeResubmit | [LOW] | Verify PSA UpdateDevice idempotency for same IMEI-ID + MAT_CODE |

---

## §19 — Response Message Rule (Response_PSA_UPDATE_DEVICE)

### §19.3 ResponseBase Construction

```text
createObject
└── object (Concepts.FM.Base.ResponseBase)
    ├── @extId           ← OMXUtils:generateTrackingID()    [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode      [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg       [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus  [Conditional]
    └── ReferenceId      ← $eventResponse/RefID             [Conditional]
```

### §19.4 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Write-back | None |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
