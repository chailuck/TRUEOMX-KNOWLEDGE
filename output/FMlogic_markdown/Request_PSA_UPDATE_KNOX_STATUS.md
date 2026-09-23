# Request_PSA_UPDATE_KNOX_STATUS

> Updates device Knox enrollment status in PSA per qualifying subscriber offer (IMEI from ExtendedInfo, status from ProcessConfig KNOX_STATUS parameter); response handler overwrites DEVICE_STATUS ExtendedInfo on the matched offer.

**Backend:** PSA (updateKnoxStatus) | **Pattern:** Per-offer fan-out | **forwardChain:** true | **Author:** DESKTOP-995HR2V | **Used in step:** 67

---

## §1 — Overview & Purpose

Sends one **PSA updateKnoxStatusReq** per qualifying subscriber offer, updating the device's Knox enrollment status. The target Knox status is read from the ProcessConfig `Parameter[KNOX_STATUS]` key. The response handler writes the new status back into the matched offer's `ExtendedInfo[DEVICE_STATUS]`, *overwriting* the value previously set by PSA_GET_DEVICE_INFO.

- **Parameter guard:** throws `DATA_ISSUE` if no Parameter entries — KNOX_STATUS is mandatory
- **knoxStatus:** `GetActivityParameterValueFromKey(orderCurrentActivity, "KNOX_STATUS")`
- **Payload:** IMEI from `ExtendedInfo[IMEI_KNOX]` + status from `$knoxStatus` + channel-access="OMX"
- **Audit OPERATION_NAME:** `concat("PSA_UPDATE_KNOX_STATUS_", $knoxStatus)` — includes Knox status value
- **Response write-back:** overwrites existing `ExtendedInfo[DEVICE_STATUS].Value = knoxStatus`

> **[HIGH] COU XSLT sends wrong RefID:** The COU variant passes `$cSubRefId` as the XSLT parameter name (`RefID = $cSubRefId`) instead of the correctly computed `offerRefId`. This means COU events carry only the bare subscriber RefId (e.g., `"SUB002"`) with no `Soc` or `filter` segments. The response handler's `String.split(RefID, ":")` then produces empty `soc` and `source` parts, so no offer is ever matched and **DEVICE_STATUS is never updated for any COU subscriber offer**. PSA still receives and processes the request, but the working-memory write-back silently fails.

> **[MEDIUM] COU PreExecCheck context mismatch:** COU uses `GetXMLForSubscriberInChildOU` (subscriber-level context, no offer or filter) while POU uses `GetXMLForSubscriberOfferFilterWithExtendedInfo` (offer-level). PreExecCheck referencing offer data or FE_OR_CCBS will behave inconsistently.

> **[LOW] No PurgePendingRequestsBeforeResubmit:** Duplicate PSA update calls possible on resubmit.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_PSA_UPDATE_KNOX_STATUS.rule` | 157 lines |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_PSA_UPDATE_KNOX_STATUS.rulefunction` | 117 lines — write-back logic |
| Author | DESKTOP-995HR2V | |
| Priority | 5 | |
| forwardChain | true | |
| Backend event | `Events.OMConsumers.OMXFM.Request.PSA_UPDATE_KNOX_STATUS` | Dedicated event type |
| Payload root | `ns:updateKnoxStatusReq` | PSA Knox status update |
| Schema NS (ns) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/PSA/UpdateKnoxStatusRequest.xsd` | Request |
| Schema NS (ns1) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/PSA/UserInfoType.xsd` | user-info |
| Parameter guard | `Parameter@length == 0` → DATA_ISSUE exception | Mandatory parameter enforcement |
| knoxStatus source | `GetActivityParameterValueFromKey(orderCurrentActivity, "KNOX_STATUS")` | From ProcessConfig Parameter |
| Audit OPERATION_NAME | `concat("PSA_UPDATE_KNOX_STATUS_", $knoxStatus)` | Includes Knox status value for traceability |
| offerRefId (POU) | `pSubRefId + ":" + offer.Soc + ":" + filter` | Correct 3-part key |
| offerRefId (COU) | COU XSLT sends `$cSubRefId` as RefID param | `[HIGH]` Bug: should be `$offerRefId` |
| IMEI source | `ExtendedInfo[IMEI_KNOX]/Value` | Same as PSA_GET_DEVICE_INFO |
| channel-access | `"OMX"` | Hardcoded |
| Resub purge | **ABSENT** | No PurgePendingRequestsBeforeResubmit |
| POU PreExecCheck builder | `GetXMLForSubscriberOfferFilterWithExtendedInfo` | Correct |
| COU PreExecCheck builder | `GetXMLForSubscriberInChildOU` | `[MEDIUM]` Subscriber-level only |
| Response write-back | `ExtendedInfo[DEVICE_STATUS].Value = knoxStatus` | Overwrites existing entry (not append) |
| Fan-in | `RequestCount == successResponseCount` | success = ResponseCode suffix "000" |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "PSA_UPDATE_KNOX_STATUS"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "PSA_UPDATE_KNOX_STATUS"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §4 — POU vs COU XSLT Variants

| Field | POU XSLT | COU XSLT | Diff |
|-------|----------|----------|------|
| XSLT param name for correlation | `offerRefId` | `cSubRefId` | `[HIGH]` COU uses wrong param name |
| RefID value emitted | `$offerRefId` = `subRefId:Soc:filter` | `$cSubRefId` = bare subscriber RefId | COU RefID missing Soc and filter segments |
| ns:imei | `ExtendedInfo[IMEI_KNOX]/Value` | `ExtendedInfo[IMEI_KNOX]/Value` | Identical |
| ns:status-knox | `$knoxStatus` | `$knoxStatus` | Identical |
| ns1:channel-access | `"OMX"` | `"OMX"` | Identical |
| PreExecCheck builder | `GetXMLForSubscriberOfferFilterWithExtendedInfo` | `GetXMLForSubscriberInChildOU` | `[MEDIUM]` Different context |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

POU and COU XSLTs share identical payload structure — only `RefID` differs (see §4).

```text
createEvent
└── event
    ├── JMSPriority         ← $orderRequest/OrderPriority                                [Conditional]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId                      [Conditional]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                            [Conditional]
    ├── RefID               ← $offerRefId (POU) / $cSubRefId (COU — [HIGH] BUG)          [Always]
    ├── UserName            ← $orderRequest/OrderData/User                               [Credential-gated]
    ├── PassWord            ← $orderRequest/OrderData/Password                           [Credential-gated]
    ├── OrderType           ← $orderRequest/OrderData/OrderType                          [Conditional]
    └── payload
        └── ns:updateKnoxStatusReq  (ns=http://…/PSA/UpdateKnoxStatusRequest.xsd)
            └── ns:order
                ├── ns:data
                │   ├── ns:imei            ← $offer/ExtendedInfo[IMEI_KNOX]/Value         [Always]
                │   └── ns:status-knox     ← $knoxStatus (ProcessConfig KNOX_STATUS param) [Always]
                └── ns:user-info
                    └── ns1:channel-access ← "OMX" (hardcoded)                           [Always]
```

---

## §8 — System & Integration Dependencies

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | PSA (Partner Service Access) |
| Operation | updateKnoxStatusReq — update device Knox enrollment status |
| Request schema NS (ns) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/PSA/UpdateKnoxStatusRequest.xsd` |
| IMEI source | `ExtendedInfo[IMEI_KNOX]/Value` |
| Knox status source | `ProcessConfig Parameter[KNOX_STATUS]` — varies per workflow step |

### §8.5 ExtendedInfo Fields

| Name | Direction | Purpose |
|------|-----------|---------|
| FE_OR_CCBS | INPUT | filter segment in offerRefId |
| IMEI_KNOX | INPUT | ns:imei in PSA request |
| DEVICE_STATUS | OUTPUT (overwrite) | Overwritten with knoxStatus on successful response match |

---

## §15 — Function Dependency Tree

```text
Request_PSA_UPDATE_KNOX_STATUS (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── [Parameter guard]: if(Parameter@length == 0) throw DATA_ISSUE
├── knoxStatus = GetActivityParameterValueFromKey(orderCurrentActivity, "KNOX_STATUS")
├── [NOTE: NO PurgePendingRequestsBeforeResubmit]
├── [POU loop p → ps → psof]:
│   ├── filter = XPath.evalAsString(offer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── offerRefId = pSubRefId + ":" + offer.Soc + ":" + filter
│   ├── [Resub guard]: scan Response[] for CompletionStatus==2 && ReferenceId==offerRefId
│   ├── [if !reqSuccess]:
│   │   ├── [if PreExecCheck]: GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, offer.Soc, filter)
│   │   └── [if "true"]:
│   │       ├── Event.createEvent(PSA_UPDATE_KNOX_STATUS, XSLT: ns:updateKnoxStatusReq, RefID=$offerRefId)
│   │       ├── Event.Ext.sendEventImmediate(reqEvent)
│   │       ├── isSkipped = false; [if !isActResub]: RequestCount++
│   │       └── Logger: OPERATION_NAME=concat("PSA_UPDATE_KNOX_STATUS_", knoxStatus)
├── [COU loop p → c → cs → csof]:
│   ├── offerRefId = cSubRefId + ":" + offer.Soc + ":" + filter (computed correctly in BE)
│   ├── [if PreExecCheck]: GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId) ← [MEDIUM]
│   └── Event.createEvent(PSA_UPDATE_KNOX_STATUS, XSLT: RefID=$cSubRefId) ← [HIGH] BUG
├── [if !isSkipped]:
│   ├── Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch]: HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_PSA_UPDATE_KNOX_STATUS (rulefunction)
├── activityRes = Instance.createInstance(ResponseBase) {extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId}
├── currActivity.Response[] ← activityRes
├── refIDs = String.split(eventResponse.RefID, ":")
│   ├── refIDs[0] = subRefId  (empty soc/source for COU due to [HIGH] bug)
│   ├── refIDs[1] = soc
│   └── refIDs[2] = source
├── knoxStatus = GetActivityParameterValueFromKey(currActivity, "KNOX_STATUS")
├── [POU loop]: find subscriber[RefId==subRefId] → find offer[Soc==soc] → verify feOrCcbs==source
│   └── for each ExtendedInfo: if Name=="DEVICE_STATUS" → Value = knoxStatus; break
├── [COU loop]: same pattern — BUT RefID has no ":" → soc="" → no offer match → write-back NEVER occurs [HIGH]
├── Event.Ext.sendEventImmediate(Logger: OPERATION_NAME=concat("PSA_UPDATE_KNOX_STATUS_", knoxStatus))
├── successResponseCount = count(Response[tib:right(tib:trim(ResponseCode),3)="000"])
└── return (RequestCount == successResponseCount) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-offer fan-out across POU and COU. One PSA updateKnoxStatusReq per qualifying offer. |
| R2 | KNOX_STATUS from ProcessConfig Parameter[KNOX_STATUS] key — mandatory (DATA_ISSUE thrown if no Parameters). |
| R3 | Payload: IMEI = IMEI_KNOX ExtendedInfo; status-knox = knoxStatus; channel-access = "OMX". |
| R4 | Audit OPERATION_NAME includes Knox status value: `concat("PSA_UPDATE_KNOX_STATUS_", knoxStatus)`. |
| R5 | Response write-back: overwrites (not appends) existing ExtendedInfo[DEVICE_STATUS].Value with knoxStatus. |
| R6 | POU RefID = `subRefId:Soc:filter` (correct). COU RefID = bare `cSubRefId` (bug — see R7). |
| R7 | **[BUG]** COU XSLT passes `$cSubRefId` as RefID instead of computed `offerRefId`. Fix: change COU XSLT `<RefID>$cSubRefId</RefID>` to `<RefID>$offerRefId</RefID>` and align XSLT param name. |
| R8 | Fan-in: RequestCount == count(Response[ResponseCode suffix "000"]). |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| COU XSLT sends RefID = bare cSubRefId — response correlation fails; DEVICE_STATUS never updated for COU offers | [HIGH] | Fix COU XSLT: pass `$offerRefId` as RefID (same as POU). Align XSLT param name to `offerRefId`. |
| COU PreExecCheck uses subscriber-level context (GetXMLForSubscriberInChildOU) instead of offer-level | [MEDIUM] | Align to GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo for consistent PreExecCheck behavior |
| No PurgePendingRequestsBeforeResubmit | [LOW] | Verify PSA idempotency for duplicate updateKnoxStatus with same IMEI |

---

## §19 — Response Message Rule (Response_PSA_UPDATE_KNOX_STATUS)

### §19.3 ResponseBase Construction

```text
createObject
└── object (Concepts.FM.Base.ResponseBase)
    ├── @extId           ← OMXUtils:generateTrackingID()    [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode      [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg       [Conditional] Msg→Message rename
    ├── CompletionStatus ← $eventResponse/CompletionStatus  [Conditional]
    └── ReferenceId      ← $eventResponse/RefID             [Conditional]
```

### §19.4 Response Write-back Logic

After creating ResponseBase, matches the offer and overwrites `ExtendedInfo[DEVICE_STATUS]`:

```text
refIDs = String.split(eventResponse.RefID, ":")  // POU: ["subRefId","soc","filter"] / COU: ["subRefId"] — BUG
subRefId = refIDs[0]; soc = refIDs[1]; source = refIDs[2]
knoxStatus = GetActivityParameterValueFromKey(currActivity, "KNOX_STATUS")

for each subscriber[RefId == subRefId]:
  for each offer[Soc == soc]:
    if feOrCcbs == source:
      for each ExtendedInfo[Name == "DEVICE_STATUS"]:
        ExtendedInfo[l].Value = knoxStatus   // OVERWRITE (not append)
        break
```

> **[HIGH] COU write-back never executes:** `refIDs[1]` (soc) will be empty/null when RefID has no ":" — no offer matches, write-back loop body never runs.

### §19.5 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
