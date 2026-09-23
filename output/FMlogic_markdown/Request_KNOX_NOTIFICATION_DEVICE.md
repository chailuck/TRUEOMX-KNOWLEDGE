# Request_KNOX_NOTIFICATION_DEVICE

> Sends a Knox device notification (method="notificationDevice") per qualifying subscriber offer via the shared KNOX_PROXY_SERVICE event. Message body resolved via KnoxNotifyMsgVRF decision table from order type, activity reason, and subscriber language.

**Backend:** Knox (notificationDevice) | **Event:** KNOX_PROXY_SERVICE (shared) | **Pattern:** Per-offer fan-out | **forwardChain:** true | **Author:** DESKTOP-995HR2V | **Used in step:** 68

---

## §1 — Overview & Purpose

Sends one **Knox knoxProxyReq (method=notificationDevice)** per qualifying subscriber offer. Uses the same shared `KNOX_PROXY_SERVICE` event as KNOX_SAVE_DEVICE — distinguished by `ns2:method = "notificationDevice"`. The notification message body is resolved at runtime via the **KnoxNotifyMsgVRF decision table** (inputs: OrderType, activityReason, lang). Phone number comes from ProcessConfig `Parameter[TEL]`.

- **Parameter guard:** throws `DATA_ISSUE` if no Parameter entries — TEL is mandatory
- **tel:** `GetActivityParameterValueFromKey(orderCurrentActivity, "TEL")`
- **KnoxNotifyMsgVRF:** `DecisionTables.KnoxNotifyMsgVRF(OrderType, "NOTIFY", activityReason, lang, msg)`
- **msg appended:** `offer.ExtendedInfo[len] = msg` (Name="KNOX_NOTIFY_MSG") before sending
- **Method discriminator:** `ns2:method = "notificationDevice"` (hardcoded)
- **Response:** standard ResponseBase only — no write-back

> **[HIGH] POU XSLT sends wrong RefID:** The POU XSLT param is named `pSubRefId`, binding to the BE variable `pSubRefId` (bare subscriber RefId, e.g. `"SUB001"`), NOT the computed `offerRefId` (`"SUB001:SOC:FE"`). Knox echoes this RefID back; stored in `ResponseBase.ReferenceId`. The resubmit guard checks `Response[ReferenceId == offerRefId]` — since `pSubRefId ≠ offerRefId`, POU offers are **always treated as not-yet-complete on resubmit**. This is the mirror-opposite of the PSA_UPDATE_KNOX_STATUS bug (where POU was correct, COU wrong).

> **[INFO] COU RefID is CORRECT:** The COU XSLT param is named `offerRefId`, binding to the BE variable `offerRefId` = `cSubRefId:Soc:filter`. Resubmit correlation works for COU offers.

> **[MEDIUM] COU PreExecCheck uses subscriber-level context:** `GetXMLForSubscriberInChildOU` instead of `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo`.

> **[LOW] No PurgePendingRequestsBeforeResubmit:** Duplicate Knox notifications possible on resubmit, compounded by POU resubmit guard failure.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_KNOX_NOTIFICATION_DEVICE.rule` | 187 lines |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_KNOX_NOTIFICATION_DEVICE.rulefunction` | 27 lines — standard, no write-back |
| Author | DESKTOP-995HR2V | Same Knox cluster author |
| Priority | 5 | |
| forwardChain | true | |
| Backend event type | `Events.OMConsumers.OMXFM.Request.KNOX_PROXY_SERVICE` | Shared — same as KNOX_SAVE_DEVICE |
| Response event type | `Events.OMConsumers.OMXFM.Response.KNOX_PROXY_SERVICE` | Shared |
| Payload root | `ns2:knoxProxyReq` | |
| Operation discriminator | `ns2:method = "notificationDevice"` | Hardcoded; distinct from KNOX_SAVE_DEVICE ("saveDevice") |
| Schema NS (ns2) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/Knox/KnoxProxyRequest.xsd` | |
| Parameter guard | `Parameter@length == 0` → DATA_ISSUE | Mandatory |
| tel source | `GetActivityParameterValueFromKey(orderCurrentActivity, "TEL")` | From ProcessConfig |
| Message body | `DecisionTables.KnoxNotifyMsgVRF(OrderType, "NOTIFY", activityReason, lang, msg)` | Runtime-resolved |
| msg ExtendedInfo key | `KNOX_NOTIFY_MSG` | Appended before dispatch |
| lang default | `"TH"` | Overridden by SubscriberGeneralInfo.Language if not blank |
| activityReason default | `""` | Overridden by SubscriberActivityInfo.ActivityReason if not blank |
| POU XSLT RefID | Param `pSubRefId` → sends bare subscriber RefId | `[HIGH]` Bug — should be `offerRefId` |
| COU XSLT RefID | Param `offerRefId` → sends correct 3-part key | `[CORRECT]` |
| POU PreExecCheck builder | `GetXMLForSubscriberOfferFilterWithExtendedInfo` | Correct |
| COU PreExecCheck builder | `GetXMLForSubscriberInChildOU` | `[MEDIUM]` Subscriber-level only |
| Response write-back | None | Simple response handler |
| Resub purge | **ABSENT** | No PurgePendingRequestsBeforeResubmit |
| OPERATION_NAME | `"KNOX_NOTIFICATION_DEVICE"` | Hardcoded in both request and response audit |
| Fan-in | `RequestCount == successResponseCount` | success = ResponseCode suffix "000" |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "KNOX_NOTIFICATION_DEVICE"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "KNOX_NOTIFICATION_DEVICE"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §4 — POU vs COU XSLT Variants

| Field | POU XSLT | COU XSLT | Diff |
|-------|----------|----------|------|
| XSLT param for RefID | `pSubRefId` | `offerRefId` | `[HIGH]` POU uses wrong param name |
| RefID value emitted | Bare `pSubRefId` | `cSubRefId:Soc:filter` | POU missing Soc and filter |
| Resub guard effectiveness | Broken | Correct | POU always re-sent on resubmit |
| ns2:transactionId | `concat(IMEI_KNOX, tib:timestamp())` | `concat(IMEI_KNOX, tib:timestamp())` | Identical |
| ns2:tel | `$tel` (always) | `$tel` (always) | Identical |
| ns2:message | `$msg/Value` (conditional) | `$msg/Value` (conditional) | Identical |
| ns2:brand | BRAND_NAME (conditional) | BRAND_NAME (conditional) | Identical |
| ns2:method | `"notificationDevice"` | `"notificationDevice"` | Identical |
| PreExecCheck builder | `GetXMLForSubscriberOfferFilterWithExtendedInfo` | `GetXMLForSubscriberInChildOU` | `[MEDIUM]` COU different context |

---

## §7 — KnoxNotifyMsgVRF Decision Table

| Step | Action | Detail |
|------|--------|--------|
| 1 | Create msg concept | `Instance.createInstance(SubscriberOffersExtendedInfo)` with `Name="KNOX_NOTIFY_MSG"` |
| 2 | Resolve lang | `sub.SubscriberGeneralInfo.Language` if not blank; else `"TH"` |
| 3 | Resolve activityReason | `sub.SubscriberActivityInfo.ActivityReason` if not blank; else `""` |
| 4 | Call decision table | `DecisionTables.KnoxNotifyMsgVRF(OrderType, "NOTIFY", activityReason, lang, msg)` → populates `msg.Value` |
| 5 | Append to ExtendedInfo | `offer.ExtendedInfo[offer.ExtendedInfo@length] = msg` |
| 6 | Pass to XSLT | `$msg/Value` → `ns2:message` (conditional on non-empty Value) |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

POU and COU share identical payload — only `RefID` differs (§4). Tree shown for COU (correct).

```text
createEvent
└── event
    ├── JMSPriority         ← $orderRequest/OrderPriority                         [Conditional]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId               [Conditional]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                     [Conditional]
    ├── RefID               ← $pSubRefId (POU — [HIGH] BUG) / $offerRefId (COU)  [Always]
    ├── UserName            ← $orderRequest/OrderData/User                        [Credential-gated]
    ├── PassWord            ← $orderRequest/OrderData/Password                    [Credential-gated]
    ├── OrderType           ← $orderRequest/OrderData/OrderType                   [Conditional]
    └── payload
        └── ns2:knoxProxyReq  (ns2=.../Knox/KnoxProxyRequest.xsd)
            ├── ns2:transactionId ← concat(IMEI_KNOX, tib:timestamp())            [Always] timestamp-only if IMEI absent
            ├── ns2:deviceUid     ← ExtendedInfo[IMEI_KNOX]/Value                 [Conditional: xsl:if]
            ├── ns2:tel           ← $tel (ProcessConfig Parameter[TEL])           [Always]
            ├── ns2:message       ← $msg/Value (from KnoxNotifyMsgVRF)            [Conditional: xsl:if on msg/Value]
            ├── ns2:brand         ← ExtendedInfo[BRAND_NAME]/Value                [Conditional: set by PSA_GET_DEVICE_INFO]
            └── ns2:method        ← "notificationDevice" (hardcoded)              [Always]
```

---

## §8 — System & Integration Dependencies

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | Knox (Samsung Knox device management) |
| Operation | knoxProxyReq / method = "notificationDevice" |
| Schema NS (ns2) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/Knox/KnoxProxyRequest.xsd` |
| Event type | KNOX_PROXY_SERVICE (shared — also used by KNOX_SAVE_DEVICE with method="saveDevice") |
| Phone number source | ProcessConfig Parameter[TEL] |
| Message body source | DecisionTables.KnoxNotifyMsgVRF — runtime-resolved |

### §8.5 ExtendedInfo Fields

| Name | Direction | Purpose |
|------|-----------|---------|
| FE_OR_CCBS | INPUT | filter segment in offerRefId |
| IMEI_KNOX | INPUT | ns2:transactionId prefix + ns2:deviceUid |
| BRAND_NAME | INPUT | ns2:brand (written by PSA_GET_DEVICE_INFO upstream) |
| KNOX_NOTIFY_MSG | OUTPUT (append) | Created by KnoxNotifyMsgVRF; appended to offer.ExtendedInfo; Value → ns2:message |

---

## §15 — Function Dependency Tree

```text
Request_KNOX_NOTIFICATION_DEVICE (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── [Parameter guard]: if(Parameter@length == 0) throw DATA_ISSUE
├── tel = GetActivityParameterValueFromKey(orderCurrentActivity, "TEL")
├── [NOTE: NO PurgePendingRequestsBeforeResubmit]
├── [POU loop p → ps → psof]:
│   ├── filter = XPath(offer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── pSubRefId = psub.RefId
│   ├── offerRefId = pSubRefId + ":" + offer.Soc + ":" + filter (computed but NOT passed to POU XSLT)
│   ├── [Resub guard]: Response[ReferenceId == offerRefId && CompletionStatus==2]
│   │   BROKEN: Knox returns pSubRefId → stored as ReferenceId → offerRefId never matches [HIGH]
│   ├── [if PreExecCheck]: GetXMLForSubscriberOfferFilterWithExtendedInfo(pSubRefId, offer.Soc, filter)
│   └── [if "true"]:
│       ├── msg = Instance.createInstance(SubscriberOffersExtendedInfo){Name="KNOX_NOTIFY_MSG"}
│       ├── lang = psub.SubscriberGeneralInfo.Language || "TH"
│       ├── activityReason = psub.SubscriberActivityInfo.ActivityReason || ""
│       ├── DecisionTables.KnoxNotifyMsgVRF(OrderType, "NOTIFY", activityReason, lang, msg)
│       ├── offer.ExtendedInfo[len] = msg         ← APPENDS KNOX_NOTIFY_MSG
│       ├── Event.createEvent(KNOX_PROXY_SERVICE, RefID=$pSubRefId [BUG], method="notificationDevice")
│       ├── Event.Ext.sendEventImmediate(reqEvent)
│       └── [if !isActResub]: RequestCount++
├── [COU loop p → c → cs → csof]:
│   ├── offerRefId = cSubRefId + ":" + offer.Soc + ":" + filter
│   ├── [if PreExecCheck]: GetXMLForSubscriberInChildOU(cSubRefId, pOuRefId) ← [MEDIUM]
│   └── Event.createEvent(KNOX_PROXY_SERVICE, RefID=$offerRefId [CORRECT], method="notificationDevice")
├── [if !isSkipped]:
│   ├── Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch]: HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_KNOX_NOTIFICATION_DEVICE (rulefunction)
├── activityRes = Instance.createInstance(ResponseBase){extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId}
│   └── ReferenceId ← eventResponse.RefID  (POU: pSubRefId; COU: offerRefId)
├── currActivity.Response[] ← activityRes
├── Logger: OPERATION_NAME="KNOX_NOTIFICATION_DEVICE" (hardcoded, not dynamic)
├── successResponseCount = count(Response[tib:right(tib:trim(ResponseCode),3)="000"])
└── return (RequestCount == successResponseCount) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-offer fan-out across POU and COU. One Knox notificationDevice per qualifying offer. |
| R2 | TEL from ProcessConfig Parameter[TEL] — mandatory (DATA_ISSUE if no Parameters). |
| R3 | Message resolved via `KnoxNotifyMsgVRF(OrderType, "NOTIFY", activityReason, lang, msg)`. Inputs: OrderType, activityReason (from SubscriberActivityInfo or ""), lang (from SubscriberGeneralInfo or "TH"). |
| R4 | KNOX_NOTIFY_MSG appended to offer.ExtendedInfo; Value → ns2:message (conditional on non-empty Value). |
| R5 | ns2:method = "notificationDevice" (hardcoded; shared KNOX_PROXY_SERVICE event). |
| R6 | offerRefId = subRefId:Soc:filter — computed correctly in BE for both POU and COU. |
| R7 | **[BUG]** POU XSLT param `pSubRefId` binds to bare `pSubRefId`, not computed `offerRefId`. Fix: rename POU XSLT param to `offerRefId`. |
| R8 | COU RefID = `offerRefId` (correct) — no change needed. |
| R9 | Response: standard ResponseBase — no write-back. Fan-in: RequestCount == successResponseCount. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| POU XSLT RefID = bare pSubRefId — resubmit guard broken; POU offers always re-notified | [HIGH] | Rename POU XSLT param to `offerRefId` to bind the 3-part BE variable |
| COU PreExecCheck uses subscriber-level context (GetXMLForSubscriberInChildOU) | [MEDIUM] | Align to GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo |
| No PurgePendingRequestsBeforeResubmit — compounded by POU resubmit guard failure | [LOW] | Verify Knox idempotency; fix POU RefID bug first |
| BRAND_NAME absent if PSA_GET_DEVICE_INFO skipped or failed | [LOW] | Verify Knox accepts notification without brand |

---

## §19 — Response Message Rule (Response_KNOX_NOTIFICATION_DEVICE)

### §19.3 ResponseBase Construction

```text
createObject
└── object (Concepts.FM.Base.ResponseBase)
    ├── @extId           ← OMXUtils:generateTrackingID()    [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode      [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg       [Conditional] Msg→Message rename
    ├── CompletionStatus ← $eventResponse/CompletionStatus  [Conditional]
    └── ReferenceId      ← $eventResponse/RefID             [Conditional]
                           POU: stores bare pSubRefId (resubmit guard mismatch with offerRefId)
                           COU: stores offerRefId (correct)
```

### §19.4 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Write-back | None |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
