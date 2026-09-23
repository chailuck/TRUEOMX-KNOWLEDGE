# Request_TCC_GET_MNP_AUTO_SHAREPLAN

## §1 Overview & Purpose

Queries the TCC **getMnp900** API once per subscriber (in ParentOU and ChildOU) to obtain the MNP auto shareplan assignment. For each subscriber whose porting MSISDN maps to a shared plan, the response returns the `mainNumber` (the shareplan's lucky/main number). This is written as a `SHAREPLAN_MAIN_NUMBER` ExtendedInfo on the subscriber for downstream provisioning.

If all subscribers already have responses, calls `SkipActivity("4")`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_TCC_GET_MNP_AUTO_SHAREPLAN` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | TCC_GET_MNP_AUTO_SHAREPLAN |
| Backend | TCC getMnp900 service |
| Pattern | Subscriber-level fan-out (no IntraActivitySequencing — direct Event.sendEvent) |
| Author | MalineeS. |
| Response Rulefunction | Response_TCC_GET_MNP_AUTO_SHAREPLAN |

---

## §3 Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity state |

---

## §4 Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "TCC_GET_MNP_AUTO_SHAREPLAN"
orderRequest.ProcessFlow.NextActivityID == "TCC_GET_MNP_AUTO_SHAREPLAN"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 Execution Flow

1. Detect resubmit: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Load next activity config for PreExecCheck
3. For each `ParentOU[i].Subscriber[j]`:
   - Skip if subscriber already has successful response (CompletionStatus=2)
   - Evaluate PreExecCheck XPath via `GetXMLForSubscriber` if defined
   - If chkRes="true": build and send `TCC_GET_MNP_AUTO_SHAREPLAN` event
   - Increment `RequestCount` (if not resubmit)
4. For each `ParentOU[i].ChildOU[k].Subscriber[j]` (same logic, uses `GetXMLForSubscriberInChildOU`)
5. If no requests sent (`isSkipped=true`): call `SkipActivity(orderRequest, orderCurrentActivity, "4")`
6. Else: set `Status = GetActivityStatusString("1", false)`, call `SendDataToDB`
7. Send audit log event

> **Note:** A commented-out variant references `TCC_GET_SHAREPLAN_MAIN_NUMBER` event. The active code uses `TCC_GET_MNP_AUTO_SHAREPLAN` exclusively.

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

Used in MNP port-in flows (MNP_PORT_IN_EXT, step 10). Unconditional — all subscribers processed.

### §8.2 ESB / JMS Channel

| Direction | Event Type | Destination | Protocol |
|-----------|-----------|-------------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.TCC_GET_MNP_AUTO_SHAREPLAN` | TCC getMnp900 | JMS/ESB |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.TCC_GET_MNP_AUTO_SHAREPLAN` | Response channel | JMS |

### §8.3 Backend API

| System | Operation | Namespace |
|--------|-----------|-----------|
| TCC | getMnp900 | `http://service.profiles.ads.truecorp.co.th/` |

### §8.4 BE Working Memory Fields

| Field Path | Direction | Notes |
|-----------|-----------|-------|
| `Customer.ParentOU[].Subscriber[].MSISDN` | Read | Porting MSISDN → mnpNumber |
| `Customer.CustomerGeneralInfo.Identification` | Read | Thai ID → thaiId |
| `Customer.ParentOU[].Subscriber[].ExtendedInfo[SHAREPLAN_MAIN_NUMBER]` | Written | Added by response handler when mainNumber non-blank |
| `orderCurrentActivity.Response[]` | Written | TCC_GetSharedPlanMainNumberRes appended per response |
| `orderCurrentActivity.RequestCount` | Written | Incremented once per subscriber request |

---

## §9 Detailed Payload Build

### §9.4 Payload Root

Namespace: `http://service.profiles.ads.truecorp.co.th/` (prefix `ns`)  
Root: `<ns:getMnp900>` → `<MnpRequest>`

### §9.5 Payload Fields

| Field | Condition | Source |
|-------|-----------|--------|
| `JMSPriority` | Always | `$orderRequest/OrderPriority` |
| `JMSCorrelationID` | Always | `$orderRequest/OrderData/OMXTrackingId` |
| `OrderID` | Always | `$orderRequest/OrderData/OrderID` |
| `RefID` | If RefId exists | `$pOuSub/RefId` or `$cOuSub/RefId` |
| `OrderType` | Always | `$orderRequest/OrderData/OrderType` |
| `luckyNumber` | Always | `''` (empty string literal) |
| `mnpNumber` | Always | `$pOuSub/MSISDN` or `$cOuSub/MSISDN` |
| `thaiId` | Always | `$orderRequest/OrderData/Customer/CustomerGeneralInfo/Identification` |

### §9.8 XSLT Tree (abbreviated)

```text
createEvent
└── event
    ├── JMSPriority           ← $orderRequest/OrderPriority             [Always]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId   [Always]
    ├── OrderID               ← $orderRequest/OrderData/OrderID         [Always]
    ├── RefID                 ← $pOuSub/RefId                           [Conditional: if RefId exists]
    ├── OrderType             ← $orderRequest/OrderData/OrderType        [Always]
    └── payload
        └── ns:getMnp900
            └── MnpRequest
                ├── luckyNumber ← '' (empty)                            [Always]
                ├── mnpNumber   ← $pOuSub/MSISDN                        [Always]
                └── thaiId      ← Customer/CustomerGeneralInfo/Identification [Always]
```

> **Two variants:** ParentOU uses `$pOuSub`; ChildOU uses `$cOuSub`.

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` [Conditional] |
| PROCESS_ID | `concat($pid, "_REQ")` |
| OPERATION_NAME | "TCC_GET_MNP_AUTO_SHAREPLAN" |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | "Request Sent for TCC_GET_MNP_AUTO_SHAREPLAN" |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | Conditional on WritePayload="true" |

---

## §12 Activity Status Management

| Outcome | Call |
|---------|------|
| At least one request sent | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All subscribers already responded | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |

**Note:** No IntraActivitySequencing — RequestCount incremented manually.

---

## §13 Exception Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 Helper Functions

| Function | Purpose |
|----------|---------|
| `RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)` | Serialize ParentOU subscriber XML for PreExecCheck |
| `RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, parentRefId)` | Serialize ChildOU subscriber XML for PreExecCheck |
| `RuleFunctions.Helpers.GetActivityStatusString("1", false)` | Returns SENT status string |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | Persist order state to DB |
| `RuleFunctions.Helpers.SkipActivity(req, activity, "4")` | Skip this activity and 3 downstream |
| `RuleFunctions.Helpers.HandleActivityException(req, activity, ae, "")` | Standard error handler |
| `RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(value)` | Null-safe blank check (used in response handler) |

---

## §15 Function Dependency Tree

```text
Request_TCC_GET_MNP_AUTO_SHAREPLAN
├── Instance.getByExtIdByUri(NextActivityName)
├── [For each ParentOU.Subscriber]
│   ├── RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)
│   ├── XPath.execute(PreExecCheck, sXML)
│   ├── Event.createEvent("xslt://TCC_GET_MNP_AUTO_SHAREPLAN") [pOuSub XSLT]
│   ├── Event.sendEvent(reqEvent)
│   └── orderCurrentActivity.RequestCount++
├── [For each ChildOU.Subscriber]
│   ├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, parentRefId)
│   ├── XPath.execute(PreExecCheck, sXML)
│   ├── Event.createEvent("xslt://TCC_GET_MNP_AUTO_SHAREPLAN") [cOuSub XSLT]
│   ├── Event.sendEvent(reqEvent)
│   └── orderCurrentActivity.RequestCount++
├── [if !isSkipped]
│   ├── GetActivityStatusString("1", false)
│   └── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── [if isSkipped]
│   └── RuleFunctions.Helpers.SkipActivity(req, activity, "4")
├── Event.sendEvent(Logger event)
└── RuleFunctions.Helpers.HandleActivityException(req, activity, ae, "")
```

---

## §17 Migration Notes

| # | Requirement / Risk | Severity |
|---|-------------------|---------|
| R1 | Subscriber-level fan-out: one request per subscriber — per-subscriber RefId correlation in response must be preserved | [HIGH] |
| R2 | SHAREPLAN_MAIN_NUMBER ExtendedInfo on subscriber gates downstream shareplan provisioning | [HIGH] |
| R3 | TCC getMnp900: luckyNumber always empty in request; mainNumber in response is the assignable shareplan number | [MEDIUM] |
| R4 | Dual subscriber path (ParentOU vs ChildOU) — both produce same SHAREPLAN_MAIN_NUMBER structure | [MEDIUM] |
| R5 | No IntraActivitySequencing — manual RequestCount; fan-in: count(Response[ResponseCode ends "000"]) == RequestCount | [MEDIUM] |
| R6 | SkipActivity("4") — offset must match target activity chain | [LOW] |
| R7 | Commented-out TCC_GET_SHAREPLAN_MAIN_NUMBER variant — verify TCC API version in target | [LOW] |

---

## §19 Response Message Rule

### §19.1 Overview

Parses TCC getMnp900 response. Extracts `mainNumber` and writes `SHAREPLAN_MAIN_NUMBER` ExtendedInfo to the matching subscriber. Fan-in: returns "true" when all accounts responded with code ending "000".

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.TCC_GET_MNP_AUTO_SHAREPLAN` | TCC response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity tracking |

### §19.3 ResponseBase: TCC_GetSharedPlanMainNumberRes

```text
createObject
└── object
    ├── @extId            ← ns2:generateTrackingID()                          [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode                       [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg                        [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus                   [Conditional]
    ├── ReferenceId       ← $eventResponse/RefID                              [Conditional]
    ├── mnpNumber         ← .../ns4:mnp-auto-shareplan-list/ns4:mnp-number   [Conditional]
    └── mainNumber        ← .../ns4:mnp-auto-shareplan-list/ns4:lucky-number  [Conditional]
```

### §19.4 SHAREPLAN_MAIN_NUMBER ExtendedInfo (if mainNumber not blank)

```text
SubscriberExtendedInfo:
  extId  = concat($eventResponse/RefID, ":SHAREPLAN_MAIN_NUMBER:", $activityRes/mnpNumber)
  Name   = "SHAREPLAN_MAIN_NUMBER"
  Value  = $activityRes/mainNumber
→ appended to pOuSub.ExtendedInfo[]
```

### §19.5 Fan-in Logic

```text
successResponseCount = count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
if (currActivity.RequestCount == successResponseCount) → return "true"
else → return "false"
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
