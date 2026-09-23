# Request_BLACKLIST_CHECK_BLACKLIST

> TIBCO BusinessEvents FM Logic — Blacklist service check by Account RefId and Customer Identification (National ID), single-shot

**Author:** awalia-t420 | **Priority:** 5 · forwardChain=true | **Pattern:** Single-shot (one request per order) | **Generated:** 2026-08-04

---

## §1 Overview & Purpose

**BLACKLIST_CHECK_BLACKLIST** performs a blacklist validation against an external Blacklist Service. It checks whether the customer's ID number (National ID / passport) appears on a blacklist associated with the customer's first account.

This FM is notably simpler than the CCBS FMs: **no CES routing, no credential gate, no subscriber loops, no ALT_CES**. A single request event is fired with three fields — RefId (first account), IdNumber (national ID), and a hardcoded CompanyCode of `'AL'`.

> **Read-only FM:** This FM does not write any enrichment back to the `orderRequest` object graph. The blacklist check result is stored in the `CheckBlacklistRes` response concept and `currActivity.ResponseCode/ResponseMessage`, allowing downstream rules to evaluate the outcome.

> **Audit log positioning:** Unlike CCBS FMs where the audit log fires inside the `if(chkRes=="true")` block, here the audit log is fired **outside** that block — it fires regardless of whether the activity was skipped by PreExecCheck.

> **Single response = completion:** One request per order — the response rulefunction always returns `"true"` immediately.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_BLACKLIST_CHECK_BLACKLIST` |
| Author | awalia-t420 |
| Priority | 5 |
| Forward chain | true |
| Backend system | Blacklist Service |
| Request schema | `http://www.tibco.com/schemas/SharedResources/Schema Definitions/Blacklist/CheckBlacklistRequest.xsd` |
| Response schema | `http://www.tibco.com/schemas/SharedResources/Schema Definitions/Blacklist/BlacklistCommonResponse.xsd` |
| Response concept | `Concepts.FM.Response.CheckBlacklistRes` |
| Fan-out pattern | Single-shot (one request per order) |
| No CES / credential gate | Simpler integration than CCBS FMs |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Customer.Account[1].RefId and CustomerGeneralInfo.Identification are read |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Holds PreExecCheck, RequestCount |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Notes |
|---|-----------|-------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity is next to execute |
| 2 | `orderCurrentActivity.ActivityID == "BLACKLIST_CHECK_BLACKLIST"` | Exact match |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "BLACKLIST_CHECK_BLACKLIST"` | Process flow agreement |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Not yet dispatched |

---

## §5 Execution Flow

1. Compute `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Fetch `nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)` — used for PreExecCheck
3. PreExecCheck: if non-empty → serialize orderRequest, evaluate XPath → set `chkRes`
4. If `chkRes="true"`: build and fire `BLACKLIST_CHECK_BLACKLIST` event
5. `RequestCount++` (if not resubmit)
6. `GetActivityStatusString("1", false)` + `SendDataToDB()`
7. If `chkRes="false"` (SKIP): `SkipActivity(orderRequest, orderCurrentActivity, "4")`
8. **Audit log always fires** (outside the if block — fires on both sent and skip paths)
9. Exception: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §6 Rule Action (THEN) — Detailed Logic

### §6.1 PreExecCheck Pattern (nextAct variant)

Uses `nextAct` (fetched from working memory by extId) rather than reading `orderCurrentActivity.PreExecCheck` directly:

```java
Activity nextAct = Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, ...);
if(String.length(nextAct.PreExecCheck) > 0) {
  chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, ...);
}
```

### §6.2 Payload — Three Fields

| Field | Source | Note |
|-------|--------|------|
| `RefId` | `Customer/Account[1]/RefId` | First account's RefId — no subscriber context |
| `IdNumber` | `Customer/CustomerGeneralInfo/Identification` | National ID / passport number |
| `CompanyCode` | `'AL'` (static) | Hardcoded company code — not configurable |

### §6.3 No JMS Correlation RefID, No CES, No Credentials

The event includes `JMSPriority`, `JMSCorrelationID`, `OrderID`, and `OrderType` for routing/tracking, but **no RefID header field**, no CES field, and no UserName/PassWord headers.

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Protocol |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.BLACKLIST_CHECK_BLACKLIST` | JMS → Blacklist Service |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.BLACKLIST_CHECK_BLACKLIST` | JMS |

### §8.3 Backend API Details

| Property | Value |
|----------|-------|
| System | Blacklist Service |
| Operation | CheckBlacklist |
| Request schema | `ns:CheckBlacklistRequest / ns:CheckBlacklist` |
| Key inputs | RefId (Account[1].RefId), IdNumber (Identification), CompanyCode="AL" |
| Key outputs | Result, StatusCode, StatusMessage, RefId (from BlacklistCommonResponse) |
| Correlation | No explicit RefID correlation — single request/response |

### §8.4 BE Working Memory — Fields Read (Request)

| Field | Path |
|-------|------|
| Account RefId | `orderRequest.OrderData.Customer.Account[1].RefId` |
| National ID | `orderRequest.OrderData.Customer.CustomerGeneralInfo.Identification` |

> **Dependency on prior FM:** This FM requires that `CustomerGeneralInfo.Identification` has already been populated — typically by **CCBS_GET_CUSTOMER_HEADER**. If that FM was skipped, IdNumber will be empty.

### §8.5 BE Working Memory — Fields Written (Response)

| Target | Field | Source |
|--------|-------|--------|
| `currActivity` | `ResponseCode` | `eventResponse.ResponseCode` |
| `currActivity` | `ResponseMessage` | `eventResponse.ResponseMsg` |
| `CheckBlacklistRes` concept | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, result, statusCode, statusMessage, RefID | eventResponse + BlacklistCommonResponse loop |

> The blacklist result is **not written back** to the `orderRequest` Customer object. Downstream rules read from `currActivity.Response` or `currActivity.ResponseCode`.

### §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit logger component name |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit logger target system |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Log level |
| `OMX_OM/WritePayload` | Payload capture gate in audit log |

No `IsEnableUserPass`, no `ClearField`, no `GetNameAddress` — fewest global dependencies of any CCBS/BL FM so far.

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameters

| Param | Bound from |
|-------|-----------|
| `$orderRequest` | Working memory OrderRequest (only parameter — no globals, no altParam) |

### §9.2 Request Event Fields

```xml
<event>
  <JMSPriority>$orderRequest/OrderPriority</JMSPriority>         <!-- conditional -->
  <JMSCorrelationID>$orderRequest/OrderData/OMXTrackingId</JMSCorrelationID>
  <OrderID>$orderRequest/OrderData/OrderID</OrderID>
  <OrderType>$orderRequest/OrderData/OrderType</OrderType>
  <!-- NO RefID header, NO CES, NO UserName/PassWord -->
  <payload>
    <ns:CheckBlacklistRequest>
      <ns:CheckBlacklist>
        <RefId>$orderRequest/OrderData/Customer/Account[1]/RefId</RefId>
        <IdNumber>$orderRequest/OrderData/Customer/CustomerGeneralInfo/Identification</IdNumber>
        <CompanyCode>'AL'</CompanyCode>  <!-- STATIC hardcoded -->
      </ns:CheckBlacklist>
    </ns:CheckBlacklistRequest>
  </payload>
</event>
```

---

## §10 XSLT Field Mapping Tree

```text
event
├── JMSPriority              ← $orderRequest/OrderPriority                                    [Conditional]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId                         [Conditional]
├── OrderID                  ← $orderRequest/OrderData/OrderID                                [Conditional]
├── OrderType                ← $orderRequest/OrderData/OrderType                              [Conditional]
└── payload
    └── ns:CheckBlacklistRequest
        └── ns:CheckBlacklist
            ├── RefId         ← $orderRequest/OrderData/Customer/Account[1]/RefId             [Always]
            ├── IdNumber      ← $orderRequest/OrderData/Customer/CustomerGeneralInfo/Identification  [Always]
            └── CompanyCode   ← 'AL' (hardcoded static literal)                               [Always]
```

---

## §11 Audit Logging

**Request audit** (fires after both send and skip paths — outside the `if` block):

| Field | Value |
|-------|-------|
| OPERATION_NAME | `BLACKLIST_CHECK_BLACKLIST` (static) |
| AUDIT_TRACE | `Request Sent for BLACKLIST_CHECK_BLACKLIST` |
| PROCESS_ID | `concat(nanoTime(), "_REQ")` |
| payload/ServicePayload | Conditional: only if `reqEvent/payload/ns1:CheckBlacklistRequest` exists AND `WritePayload="true"` |

**Response audit:**

| Field | Value |
|-------|-------|
| OPERATION_NAME | `BLACKLIST_CHECK_BLACKLIST` (static) |
| AUDIT_TRACE | `Response received for BLACKLIST_CHECK_BLACKLIST` |
| PROCESS_ID | `concat(nanoTime(), "_RES")` |

---

## §12 Activity Status Management

| Call | Code | Meaning |
|------|------|---------|
| `GetActivityStatusString("1", false)` | 1 | Active / In-Progress |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | 4 | PreExecCheck failed |

---

## §13 Exception / Error Handling

```java
catch (Exception ae) {
  HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

Standard centralized handler. Exception catch wraps the entire try body including the audit log call.

---

## §14 Helper Functions Reference

| Function | Signature | Purpose |
|----------|-----------|---------|
| `Instance.getByExtIdByUri` | (extId, uri) → Activity | Fetch nextAct from working memory for PreExecCheck |
| `Instance.serializeUsingDefaults` | (Concept) → String | Serialize orderRequest to XML for XPath |
| `XPath.execute` | (expr, xml, ns) → String | Evaluate PreExecCheck XPath expression |
| `GetActivityStatusString` | (String, boolean) → String | Returns activity status string |
| `SendDataToDB` | (orderRequest) → void | Persists activity state |
| `SkipActivity` | (orderRequest, Activity, String) → void | Sets SKIP status |
| `HandleActivityException` | (orderRequest, Activity, Exception, String) → void | Centralized error handling |

---

## §15 Function Dependency Tree

```text
Request_BLACKLIST_CHECK_BLACKLIST (rule)
├── Instance.getByExtIdByUri(NextActivityName, Activity)   [get nextAct for PreExecCheck]
├── Instance.serializeUsingDefaults(orderRequest)          [PreExecCheck XML]
├── XPath.execute("/("+chkXPath+")", sXML, ...)           [evaluate PreExecCheck]
├── Event.createEvent(BLACKLIST_CHECK_BLACKLIST XSLT)
│   └── payload: CheckBlacklistRequest
│       ├── RefId ← Customer/Account[1]/RefId
│       ├── IdNumber ← Customer/CustomerGeneralInfo/Identification
│       └── CompanyCode ← 'AL' (static)
├── Event.Ext.sendEventImmediate(reqEvent)
├── orderCurrentActivity.RequestCount++
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(orderRequest, orderCurrentActivity, "4")
├── Event.Ext.sendEventImmediate(Logger)   [ALWAYS — outside if block]
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_BLACKLIST_CHECK_BLACKLIST (rulefunction)
├── Instance.createInstance(CheckBlacklistRes XSLT)
│   ├── ResponseCode, ResponseMessage, CompletionStatus, ReferenceId (standard)
│   └── [for-each BlacklistCommonResponse]: result, statusCode, statusMessage, RefID
├── currActivity.Response[len] = blacklistRes
├── currActivity.ResponseCode = eventResponse.ResponseCode
├── currActivity.ResponseMessage = eventResponse.ResponseMsg
├── Event.Ext.sendEventImmediate(Logger)
└── return "true"  (always — single shot)
```

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Single-shot request — one blacklist check per order |
| R2 | Always uses Customer.Account[1].RefId — first account only |
| R3 | CompanyCode is hardcoded "AL" — must be preserved or made configurable |
| R4 | Result stored in CheckBlacklistRes concept + currActivity.ResponseCode — not in orderRequest graph |
| R5 | Audit log fires regardless of PreExecCheck result (skip or send) |
| R6 | No CES, no credential gate, no ALT_CES — simplest OMXFM integration pattern |
| R7 | Requires CustomerGeneralInfo.Identification populated by a prior FM (CCBS_GET_CUSTOMER_HEADER) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Hardcoded CompanyCode "AL" — not configurable via activity parameter or global variable | [MEDIUM] | Make configurable via activity parameter in migration |
| Uses Account[1] (first account only) — multi-account orders may check wrong account | [MEDIUM] | Validate that first account is always the billing account |
| If Identification is null (prior FM skipped), IdNumber will be empty — blacklist call fires with null ID | [HIGH] | Add null-check on Identification before firing, or enforce ordering constraint |
| Audit log fires on skip path with "Request Sent" message — potentially misleading | [LOW] | Conditionalise audit log or change trace message |

---

## §18 Full Source Code (Request Rule)

```java
/**
 * Request_BLACKLIST_CHECK_BLACKLIST
 * Author: awalia-t420 | Priority: 5 | forwardChain: true
 */
rule Rules.OMConsumers.OMXFM.Request.Request_BLACKLIST_CHECK_BLACKLIST {
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "BLACKLIST_CHECK_BLACKLIST";
    orderRequest.ProcessFlow.NextActivityID == "BLACKLIST_CHECK_BLACKLIST";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Activity nextAct = Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, ...);
      String chkRes = "true";
      Events.OMConsumers.OMXFM.Request.BLACKLIST_CHECK_BLACKLIST reqEvent = null;

      if(String.length(nextAct.PreExecCheck) > 0) {
        String sXML = Instance.serializeUsingDefaults(orderRequest);
        chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, ...);
      }

      if(String.equals(chkRes, "true")) {
        /* XSLT payload — see §9.2:
           CheckBlacklistRequest/CheckBlacklist:
             RefId ← Customer/Account[1]/RefId
             IdNumber ← Customer/CustomerGeneralInfo/Identification
             CompanyCode ← 'AL' (static) */
        Event.Ext.sendEventImmediate(reqEvent);
        if(!isActResub) orderCurrentActivity.RequestCount++;
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else {
        SkipActivity(orderRequest, orderCurrentActivity, "4");
      }
      // Audit log fires regardless of send/skip path
      Event.Ext.sendEventImmediate(Logger);  // OPERATION_NAME="BLACKLIST_CHECK_BLACKLIST"
    } catch (Exception ae) {
      HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

The response handler captures the blacklist check result into a `CheckBlacklistRes` concept and writes `ResponseCode/ResponseMessage` directly to `currActivity`. The result is NOT propagated to the orderRequest graph.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order graph (not modified) |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.BLACKLIST_CHECK_BLACKLIST` | Blacklist service response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Receives ResponseCode, ResponseMessage, and the CheckBlacklistRes concept |

### §19.3 Response Concept Construction (CheckBlacklistRes)

```text
CheckBlacklistRes
├── extId            ← OMXUtils.generateTrackingID() (random)          [Always]
├── ResponseCode     ← $eventResponse/ResponseCode                      [Conditional]
├── ResponseMessage  ← $eventResponse/ResponseMsg                       [Conditional]
├── CompletionStatus ← $eventResponse/CompletionStatus                  [Conditional]
├── ReferenceId      ← $eventResponse/RefID                             [Conditional]
└── [for-each BlacklistCommonResponse]:
    ├── result       ← Result                                            [Conditional]
    ├── statusCode   ← StatusCode                                        [Conditional]
    ├── statusMessage ← StatusMessage                                    [Conditional]
    └── RefID        ← RefId                                             [Always in loop]
```

### §19.4 Direct Activity Writes

```java
// Written directly to currActivity — not through XSLT concept
currActivity.ResponseCode = eventResponse.ResponseCode;
currActivity.ResponseMessage = eventResponse.ResponseMsg;
```

### §19.5 Response Completion

| Condition | Return |
|-----------|--------|
| Always (single request) | `"true"` — no RequestCount comparison needed |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
