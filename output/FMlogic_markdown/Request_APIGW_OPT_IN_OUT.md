# Request_APIGW_OPT_IN_OUT

> Sends Opt-In/Opt-Out request to API Gateway per subscriber (POU + COU). ACTION and PHONE_NO selection driven by activity parameters.

**Backend:** APIGW (OptInOut) | **Fan-out:** POU + COU subscribers | **Author:** 41HW170580 | **Lines:** 133 | **Step:** 82 | **forwardChain:** true

---

## §1 — Overview & Purpose

Sends an Opt-In/Opt-Out request to the API Gateway for each subscriber (both POU direct subscribers and COU subscribers). The operation type (`ACTION`) and whether to use the original or old MSISDN (`USE_OLD_SUBR`) are driven by activity parameters configured in the ProcessConfig, making this FM reusable for different Opt-In/Out scenarios.

| Attribute | Value | Notes |
|-----------|-------|-------|
| Backend event | `Events.OMConsumers.OMXFM.Request.APIGW_OPT_IN_OUT` | |
| Schema NS (ns) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/APIGW/OptInOut.xsd` | OptInOutReq payload |
| Fan-out | POU direct subscribers first, then COU subscribers | POU→Sub, then POU→COU→Sub |
| RefID | Subscriber RefId (bare) | Always emitted |
| extId | Pre-generated via `OMXUtils:generateTrackingID()` in XSLT attribute | Unique per event |
| ACTION | From activity parameter `ACTION` | e.g., OPT_IN or OPT_OUT |
| USE_OLD_SUBR | From activity parameter `USE_OLD_SUBR` | If 'Y' → use OLD_MSISDN ResourceInfo |
| operator | "1" (hardcoded) | TRUE operator code |
| submissionId | `concat('OPINOUT_TSUBS_', yyyyMMddHHmmss, '_', substr(MSISDN,1,8))` | Unique per subscriber per second |
| PurgePendingRequestsBeforeResubmit | YES | Called when isActResub is true |
| Dispatch | `Event.Ext.sendEventImmediate` | One event per subscriber |
| Response concept | `Concepts.FM.Base.ResponseBase` | Standard (not dedicated) |
| Fan-in | RequestCount == successResponseCount (suffix "000") | Standard count-match |

> **[INFO]** `USE_OLD_SUBR='Y'` switches `ns:PHONE_NO` to read from `ResourceInfo[ResourceName='OLD_MSISDN']/ValuesArray` instead of subscriber MSISDN. This supports MSISDN change/number portability scenarios where Opt-In/Out must be applied to the old number.

> **[LOW]** Audit logger is always sent unconditionally — the `AllowWriteLog(OrderType)` guard seen in other FMs is absent here. Logger fires for every subscriber regardless of order type.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule file | `Request_APIGW_OPT_IN_OUT.rule` (133 lines) |
| Author | 41HW170580 |
| Priority | 5 |
| forwardChain | true |
| ActivityID guard | `APIGW_OPT_IN_OUT` |
| Payload root | `ns:OptInOutReq` |
| Activity params read | `ACTION`, `USE_OLD_SUBR` |
| extId | Pre-generated: `OMXUtils:generateTrackingID()` as XSLT attribute on event element |
| Resub handling | PurgePendingRequestsBeforeResubmit when isActResub=true |
| POU PreExecCheck | `GetXMLForSubscriber(orderRequest, refId)` |
| COU PreExecCheck | `GetXMLForSubscriberInChildOU(orderRequest, refId, ParentOU.RefId)` |
| UserName/PassWord gate | ABSENT — no credential fields in payload |
| OPERATION_NAME (request) | "APIGW_OPT_IN_OUT" |
| OPERATION_NAME (response) | "APIGW_OPT_IN_OUT" |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "APIGW_OPT_IN_OUT"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "APIGW_OPT_IN_OUT"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 — Execution Flow

1. **Init:** `isActResub` = (RequestCount > 0 && IsOrderResubmitted). If true → `PurgePendingRequestsBeforeResubmit`. Read `action` (ACTION param) and `user_old_sub` (USE_OLD_SUBR param). `isSkipped = true`.
2. **POU subscriber loop** (POU p → Sub s): For each POU direct subscriber — resub guard, PreExecCheck, send one APIGW_OPT_IN_OUT event + Logger. RequestCount++ if !isActResub. isSkipped = false.
3. **COU subscriber loop** (POU p → COU c → Sub s): For each COU subscriber — same resub guard + PreExecCheck + send event + Logger.
4. **Completion:** if (!isSkipped) → Status = GetActivityStatusString("1", false); SendDataToDB. Else → SkipActivity("4").
5. **Exception:** catch(Exception ae) → HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

---

## §9 — Detailed Payload Build

### §9.1 Activity Parameters

| Parameter Key | Variable | Effect |
|---------------|----------|--------|
| ACTION | `action` | Emitted as `ns:ACTION` in payload — e.g., "OPT_IN" or "OPT_OUT" |
| USE_OLD_SUBR | `user_old_sub` | If "Y" → PHONE_NO = `ResourceInfo[ResourceName='OLD_MSISDN']/ValuesArray`; else → PHONE_NO = MSISDN |

### §9.2 submissionId Pattern

```text
concat('OPINOUT_TSUBS_', tib:format-dateTime('yyyyMMddHHmmss', current-dateTime()), '_', substring(MSISDN, 1, 8))
```

Example: `OPINOUT_TSUBS_20240115143022_0812345`. Uses first 8 characters of MSISDN — not globally unique if two subscribers share a MSISDN prefix within the same second.

### §9.3 PHONE_NO Selection

| Condition | PHONE_NO Source |
|-----------|-----------------|
| `user_old_sub == 'Y'` | `Subscriber/ResourceInfo[ResourceName='OLD_MSISDN']/ValuesArray` |
| otherwise (and MSISDN exists) | `Subscriber/MSISDN` |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

Two XSLT variants: POU (param: `psub`) and COU (param: `csub`). Structure is identical; only the subscriber reference differs.

```text
createEvent
└── event [@extId = OMXUtils:generateTrackingID()]
    ├── JMSPriority          ← $orderRequest/OrderPriority                    [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId           [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                 [Always]
    ├── RefID                ← $refId (subscriber RefId)                       [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType               [Always]
    └── payload
        └── ns:OptInOutReq
            ├── ns:submissionId  ← concat('OPINOUT_TSUBS_', yyyyMMddHHmmss, '_', substr(MSISDN,1,8))  [Always]
            ├── ns:operator      ← "1"  [Always — hardcoded]
            └── ns:submissionDatas
                ├── ns:PHONE_NO  ← if USE_OLD_SUBR='Y': ResourceInfo[OLD_MSISDN]/ValuesArray; else MSISDN  [Conditional]
                ├── ns:ACTION    ← $action (activity parameter ACTION)         [Always]
                └── ns:DATE_TIME ← tib:format-dateTime('yyyyMMddHHmmss', current-dateTime())  [Always]
```

**Legend:** Green (source) = XPath from order data | Orange (literal) = Static literal | Conditional = `xsl:if` guard applied

---

## §15 — Function Dependency Tree

```text
Request_APIGW_OPT_IN_OUT (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── [if isActResub]: PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── action = GetActivityParamValueFromKey(orderCurrentActivity, "ACTION")
├── user_old_sub = GetActivityParamValueFromKey(orderCurrentActivity, "USE_OLD_SUBR")
├── isSkipped = true
│
├── [POU loop: POU p → Sub s]
│   ├── refId = ParentOU[p].Subscriber[s].RefId
│   ├── resub guard: Response[ReferenceId==refId && CompletionStatus==2] → skip
│   ├── [PreExecCheck if set]: GetXMLForSubscriber(orderRequest, refId) → XPath.execute
│   └── [if chkRes == "true"]:
│       ├── reqEvent = Event.createEvent(APIGW_OPT_IN_OUT, XSLT):
│       │   ├── @extId = OMXUtils:generateTrackingID()
│       │   ├── submissionId = concat('OPINOUT_TSUBS_', yyyyMMddHHmmss, '_', substr(MSISDN,1,8))
│       │   ├── operator = "1"
│       │   ├── PHONE_NO = OLD_MSISDN (USE_OLD_SUBR='Y') or MSISDN
│       │   ├── ACTION = $action
│       │   └── DATE_TIME = yyyyMMddHHmmss
│       ├── Event.Ext.sendEventImmediate(reqEvent)
│       ├── isSkipped = false
│       ├── [if !isActResub]: RequestCount++
│       └── Logger (OPERATION_NAME="APIGW_OPT_IN_OUT") — always, no AllowWriteLog guard
│
├── [COU loop: POU p → COU c → Sub s]
│   ├── refId = ChildOU[c].Subscriber[s].RefId
│   ├── resub guard (same)
│   ├── [PreExecCheck]: GetXMLForSubscriberInChildOU(orderRequest, refId, ParentOU.RefId)
│   └── [same sendEventImmediate + Logger — COU variant uses $csub param]
│
├── [if !isSkipped]:
│   ├── orderCurrentActivity.Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch]: HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_APIGW_OPT_IN_OUT (rulefunction)
├── activityRes = Instance.createInstance(ResponseBase){extId=generateTrackingID(), ResponseCode, ResponseMessage, CompletionStatus, ReferenceId}
├── currActivity.Response[] ← activityRes
├── Logger (PROCESS_ID _RES suffix, OPERATION_NAME="APIGW_OPT_IN_OUT")
├── successResponseCount = count(Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
└── return (RequestCount == successResponseCount) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Fan-out: POU direct subscribers first, then COU subscribers. One request per subscriber. |
| R2 | RefID = subscriber RefId. Always emitted. |
| R3 | extId = OMXUtils:generateTrackingID() — pre-generated in XSLT attribute on the event element. |
| R4 | ACTION = activity parameter "ACTION" (e.g., OPT_IN, OPT_OUT). Must be configured per ProcessConfig step. |
| R5 | USE_OLD_SUBR='Y' → PHONE_NO from ResourceInfo[OLD_MSISDN]; else PHONE_NO from Subscriber.MSISDN. |
| R6 | submissionId = 'OPINOUT_TSUBS_' + yyyyMMddHHmmss + '_' + first-8-chars-of-MSISDN. |
| R7 | operator = "1" (hardcoded). |
| R8 | DATE_TIME = current timestamp in yyyyMMddHHmmss format. |
| R9 | PurgePendingRequestsBeforeResubmit when resubmitting. |
| R10 | Fan-in: RequestCount == successResponseCount (suffix "000"). |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Audit logger always fires — no AllowWriteLog(OrderType) guard | [LOW] | Add AllowWriteLog guard if log volume is a concern for high-frequency orders |
| submissionId uses substr(MSISDN,1,8) — not globally unique if same MSISDN prefix and sub-second timing | [LOW] | Consider using OMXUtils:generateTrackingID() as submissionId or add a counter suffix |
| USE_OLD_SUBR='Y' absent from ResourceInfo → PHONE_NO will be empty; APIGW may reject | [LOW] | Validate ResourceInfo[OLD_MSISDN] presence before sending when USE_OLD_SUBR='Y' |
| operator hardcoded to "1" — may break if deployed for a non-TRUE operator | [LOW] | Move to activity parameter or global variable if multi-operator deployment is needed |

---

## §19 — Response Message Rule (Response_APIGW_OPT_IN_OUT)

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Order context |
| eventResponse | Events.OMConsumers.OMXFM.Response.APIGW_OPT_IN_OUT | APIGW response event |
| currActivity | Concepts.OM.ProcessConfig.Activity | Activity state & response list |

### §19.3 ResponseBase Construction

```text
createObject
└── object (ResponseBase)
    ├── @extId            ← OMXUtils:generateTrackingID()          [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode            [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg             [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus        [Conditional]
    └── ReferenceId       ← $eventResponse/RefID                   [Conditional]
```

### §19.4 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Return "true" | All parallel APIGW calls completed with ResponseCode suffix "000" |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
