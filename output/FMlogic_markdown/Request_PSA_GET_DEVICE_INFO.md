# Request_PSA_GET_DEVICE_INFO

> Queries PSA for device information (IMEI lookup returning brand-name and Knox status) per qualifying subscriber offer; writes BRAND_NAME and DEVICE_STATUS back into the matched offer's ExtendedInfo on response.

**Backend:** PSA (GetDeviceInfo) | **Pattern:** Per-offer fan-out | **forwardChain:** true | **Author:** DESKTOP-995HR2V | **Used in step:** 64

---

## §1 — Overview & Purpose

Sends one **PSA getDeviceInfoReq** call per qualifying subscriber offer, searching PSA by IMEI (key-search="IMEI-ID") sourced from `ExtendedInfo[IMEI_KNOX]`. The response handler locates the matching offer and writes two PSA response fields back into the offer's ExtendedInfo: `BRAND_NAME` (device brand) and `DEVICE_STATUS` (current Knox status). These enriched fields are consumed by downstream FMs (KNOX_SAVE_DEVICE, PSA_UPDATE_KNOX_STATUS).

- **Request payload:** minimal — only 3 fields: key-search (hardcoded "IMEI-ID"), key-value (IMEI_KNOX), channel-access (hardcoded "OMX")
- **offerRefId:** `subRefId + ":" + offer.Soc + ":" + filter` — uses Soc (not OfferName)
- **Response write-back:** BRAND_NAME ← brand-name; DEVICE_STATUS ← current-knox-status; both appended to matched offer.ExtendedInfo
- **Offer matching in response:** split RefID by ":" → [subRefId, soc, source]; match subscriber.RefId + offer.Soc + feOrCcbs
- **COU PreExecCheck builder:** `GetXMLForSubscriberInChildOU` (not FilterWithExtendedInfo) — offer-level filter context missing for COU
- **No PurgePendingRequestsBeforeResubmit**

> **[MEDIUM] COU PreExecCheck context mismatch:** POU uses `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, offer.Soc, filter)` (offer-specific context including FE_OR_CCBS filter), but COU uses `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)` (subscriber-level context, no offer or filter). If PreExecCheck references offer-level or FE_OR_CCBS data, COU evaluation will behave differently from POU.

> **[MEDIUM] No PurgePendingRequestsBeforeResubmit:** isActResub suppresses RequestCount++ but pending events from a failed run remain. PSA may receive duplicate getDeviceInfo calls on resubmit.

> **[NOTE] Response write-back not guarded by success code:** BRAND_NAME and DEVICE_STATUS are appended to offer.ExtendedInfo regardless of ResponseCode — even on a failed PSA response, response payload fields are written. Downstream FMs must validate these fields before use.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_PSA_GET_DEVICE_INFO.rule` | 152 lines |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_PSA_GET_DEVICE_INFO.rulefunction` | 114 lines — complex write-back |
| Author | DESKTOP-995HR2V | Machine hostname as author |
| Priority | 5 | |
| forwardChain | true | |
| Backend event | `Events.OMConsumers.OMXFM.Request.PSA_GET_DEVICE_INFO` | |
| Payload root | `ns3:getDeviceInfoReq` | PSA device info request |
| Request schema NS (ns3) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/PSA/GetDeviceInfoRequest.xsd` | |
| Schema NS (ns1) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/PSA/UserInfoType.xsd` | user-info |
| Response schema (xsd2) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/PSA/GetDeviceInfoResponse.xsd` | |
| offerRefId format | `subRefId + ":" + offer.Soc + ":" + filter` | Uses Soc (not OfferName) |
| IMEI source | `offer/ExtendedInfo[IMEI_KNOX]/Value` | Not MaterialInfo |
| Dispatch | `Event.Ext.sendEventImmediate` | Per-offer immediate fan-out |
| isActResub | `RequestCount > 0 && IsOrderResubmitted` | Suppresses RequestCount++ only |
| Resub purge | **ABSENT** | No PurgePendingRequestsBeforeResubmit |
| POU PreExecCheck builder | `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, offer.Soc, filter)` | Offer-level context |
| COU PreExecCheck builder | `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)` | [MEDIUM] Subscriber-level only |
| Response concept | `Concepts.FM.Base.ResponseBase` | Standard 4 fields |
| Response write-back | BRAND_NAME + DEVICE_STATUS → offer.ExtendedInfo[] | Written on every response |
| Fan-in | `RequestCount == successResponseCount` | success = ResponseCode suffix "000" |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "PSA_GET_DEVICE_INFO"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "PSA_GET_DEVICE_INFO"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §4 — Request Payload (getDeviceInfoReq)

| Field | Source | Type |
|-------|--------|------|
| `ns3:key-search` | `"IMEI-ID"` | Hardcoded literal — PSA lookup key type |
| `ns3:key-value` | `offer/ExtendedInfo[Name="IMEI_KNOX"]/Value` | IMEI from offer ExtendedInfo |
| `ns1:channel-access` (inside ns3:user-info) | `"OMX"` | Hardcoded literal — calling system identifier |

> **[LOW] IMEI_KNOX may be absent:** If `ExtendedInfo[IMEI_KNOX]` is not present, `ns3:key-value` will be empty. No guard exists in the rule.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

POU and COU use identical XSLT — only the `$offer` variable differs.

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                      [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId            [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                  [Conditional]
    ├── RefID                ← $offerRefId                                      [Always]
    ├── UserName             ← $orderRequest/OrderData/User                     [Credential-gated: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password                 [Credential-gated: IsEnableUserPass='true']
    ├── OrderType            ← $orderRequest/OrderData/OrderType                [Conditional]
    └── payload
        └── ns3:getDeviceInfoReq  (ns3=.../PSA/GetDeviceInfoRequest.xsd)
            └── ns3:device-info
                ├── ns3:key-search         ← "IMEI-ID"                         [Always] hardcoded literal
                ├── ns3:key-value          ← $offer/ExtendedInfo[IMEI_KNOX]/Value  [Always] empty if absent
                └── ns3:user-info
                    └── ns1:channel-access ← "OMX"                             [Always] hardcoded literal
```

---

## §8 — System & Integration Dependencies

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | PSA (Partner Service Access) |
| Operation | getDeviceInfoReq — device lookup by IMEI |
| Request schema NS (ns3) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/PSA/GetDeviceInfoRequest.xsd` |
| Response schema NS (xsd2) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/PSA/GetDeviceInfoResponse.xsd` |
| Lookup key type | "IMEI-ID" (hardcoded) |
| Lookup key value | offer.ExtendedInfo[IMEI_KNOX].Value |
| Channel identifier | "OMX" (hardcoded) |
| Correlation | RefID = subRefId:Soc:filter |

### §8.5 ExtendedInfo Fields

| Name | Direction | Purpose | Required? |
|------|-----------|---------|-----------|
| FE_OR_CCBS | INPUT — from offer | filter segment in offerRefId | Optional (blank if absent) |
| IMEI_KNOX | INPUT — from offer | ns3:key-value (IMEI to look up) | Optional (empty PSA query if absent) |
| BRAND_NAME | OUTPUT — written to offer | PSA brand-name response | Written on every response |
| DEVICE_STATUS | OUTPUT — written to offer | PSA current-knox-status response | Written on every response |

---

## §15 — Function Dependency Tree

```text
Request_PSA_GET_DEVICE_INFO (rule)
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
│   │       ├── Event.createEvent(PSA_GET_DEVICE_INFO, XSLT: ns3:getDeviceInfoReq)
│   │       ├── Event.Ext.sendEventImmediate(reqEvent)
│   │       ├── isSkipped = false
│   │       ├── [if !isActResub]: RequestCount++
│   │       └── Event.Ext.sendEventImmediate(Logger: "Request Sent for PSA_GET_DEVICE_INFO")
├── [COU loop p → c → cs → csof]:
│   ├── filter = XPath.evalAsString(offer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── offerRefId = cSubRefId + ":" + offer.Soc + ":" + filter
│   ├── [if PreExecCheck]: GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId) ← [MEDIUM] different context
│   └── Event.createEvent(PSA_GET_DEVICE_INFO, XSLT: ns3:getDeviceInfoReq)
├── [if !isSkipped]:
│   ├── Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch]: HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_PSA_GET_DEVICE_INFO (rulefunction)
├── activityRes = Instance.createInstance(ResponseBase) {extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId}
├── currActivity.Response[] ← activityRes
├── refIDs = String.split(eventResponse.RefID, ":")
│   ├── refIDs[0] = subRefId
│   ├── refIDs[1] = soc
│   └── refIDs[2] = source (FE_OR_CCBS value)
├── [POU loop]: find subscriber[RefId==subRefId] → find offer[Soc==soc] → verify feOrCcbs==source
│   ├── band = XPath(xsd2:getDeviceInfoRes/xsd2:response/xsd2:data[1]/xsd2:brand-name)
│   ├── Instance.createInstance(SubscriberOffersExtendedInfo) {Name="BRAND_NAME", Value=$band}
│   ├── offer.ExtendedInfo[] ← bandExtendedInfo
│   ├── status = XPath(.../xsd2:data[1]/xsd2:current-knox-status)
│   ├── Instance.createInstance(SubscriberOffersExtendedInfo) {Name="DEVICE_STATUS", Value=$status}
│   └── offer.ExtendedInfo[] ← statusExtendedInfo
├── [COU loop]: same write-back pattern
├── Event.Ext.sendEventImmediate(Logger: "Response received for PSA_GET_DEVICE_INFO", LOG_LEVEL=INFO)
├── successResponseCount = count(Response[tib:right(tib:trim(ResponseCode),3)="000"])
└── return (RequestCount == successResponseCount) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-offer fan-out across POU and COU subscribers. One PSA getDeviceInfoReq per qualifying offer. |
| R2 | Request payload: key-search = "IMEI-ID" (hardcoded); key-value = IMEI_KNOX from offer ExtendedInfo; channel-access = "OMX" (hardcoded). |
| R3 | offerRefId: `subRefId:offer.Soc:filter` — 3-part key including FE_OR_CCBS value. |
| R4 | Response write-back: extract brand-name and current-knox-status from `xsd2:getDeviceInfoRes/xsd2:response/xsd2:data[1]`; write as BRAND_NAME and DEVICE_STATUS ExtendedInfo entries on matched offer. |
| R5 | Offer matching in response: split RefID by ":" to get [subRefId, soc, source]; match subscriber.RefId + offer.Soc + feOrCcbs == source. |
| R6 | POU PreExecCheck uses offer+filter context; COU uses subscriber-only context. |
| R7 | Response write-back occurs regardless of ResponseCode — not success-gated. |
| R8 | Fan-in: RequestCount == count(Response[ResponseCode suffix "000"]). |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| COU PreExecCheck uses subscriber-level context without offer/filter — inconsistent behavior from POU | [MEDIUM] | Align COU to use GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo |
| No PurgePendingRequestsBeforeResubmit — duplicate PSA calls possible on resubmit | [MEDIUM] | Add purge if PSA cannot deduplicate concurrent IMEI lookups |
| Response write-back not success-gated — BRAND_NAME/DEVICE_STATUS written even on error responses | [MEDIUM] | Add ResponseCode "000" guard before write-back |
| IMEI_KNOX absent → empty key-value to PSA | [LOW] | Add xsl:if guard or validate IMEI_KNOX presence before sending event |
| data[1] access — only first PSA data entry used | [LOW] | Confirm PSA contract: single-device response expected per IMEI |

---

## §19 — Response Message Rule (Response_PSA_GET_DEVICE_INFO)

### §19.1 Overview

Significantly more complex than a standard response handler. Creates ResponseBase concept, then parses PSA payload and writes two device data fields (BRAND_NAME, DEVICE_STATUS) back into the matched offer's ExtendedInfo in working memory.

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

### §19.4 Response Write-back to Offer ExtendedInfo

| ExtendedInfo.Name | Source XPath | Guarded? |
|-------------------|-------------|---------|
| `BRAND_NAME` | `xsd2:getDeviceInfoRes/xsd2:response/xsd2:data[1]/xsd2:brand-name` | No — always appended |
| `DEVICE_STATUS` | `xsd2:getDeviceInfoRes/xsd2:response/xsd2:data[1]/xsd2:current-knox-status` | No — always appended |

Offer match: `subscriber.RefId == refIDs[0] AND offer.Soc == refIDs[1] AND feOrCcbs == refIDs[2]`

### §19.5 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` → "true"/"false" |
| LOG_LEVEL | MSG_LOG_LEVEL/INFO |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
