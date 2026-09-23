# Request_CJ_UPDATE_CALL_VERIFICATION

## §1 Overview & Purpose

Updates the call-verification state in the Customer Journey (CJ) service. Only executed when `IS_UPDATE_CALLVER=Y` (set by Response_CJ_QUERY_STATE). Sends fcrStatus, callVerStatus, callVerResult, and related CALL_VER_* fields per POU subscriber.

Trigger: `ActivityID == "CJ_UPDATE_CALL_VERIFICATION"` and `Status == "WAITING"`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CJ_UPDATE_CALL_VERIFICATION` |
| Author | TIT_F25-Maline5 |
| Priority | 5 |
| forwardChain | true |
| Fan-in | IntraActivitySequencing (assertEvent + SendFirstRequestEvent) |
| Backend | CJ |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — source of all payload data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity tracking — RequestCount |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CJ_UPDATE_CALL_VERIFICATION"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CJ_UPDATE_CALL_VERIFICATION"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Resubmit check → `PurgePendingRequestsBeforeResubmit` if needed
2. POU loop: iterate ParentOU → Subscriber
3. Already-succeeded guard: skip if Response has CompletionStatus=2 for this RefId
4. PreExecCheck: evaluate XPath via `GetXMLForSubscriber`
5. Extract CALL_VER_* fields from subscriber ExtendedInfo
6. Compute `activityDate` = EffectiveDate if non-empty, else `""`
7. Build `CJ_UPDATE_CALL_VERIFICATION` event via XSLT
8. `Event.assertEvent(reqEvent)` + `ActionRequestEvent(reqEvent, activity)`
9. Audit log via `sendEventImmediate(Logger)`
10. `SendFirstRequestEvent` + Status="1" + `SendDataToDB` if any sent; else `SkipActivity("4")`
11. Exception → `HandleActivityException`

> **Dead code warning:** An entire `CCBS_CANCEL_SUBS` event creation block is fully commented out in the source. It was never removed. Migration: delete it.

---

## §7 Data Extraction

POU-only loop. No ChildOU iteration.

### Field Derivation Table

| Payload Field | Source | Notes |
|---------------|--------|-------|
| `fcrStatus` | `CALL_VER_FCR_STATUS` ExtendedInfo | Maps to UNBAR/BAR; conditional |
| `callVerReason` | `CALL_VER_REASON` ExtendedInfo | Optional |
| `callVerStatus` | `CALL_VER_STATUS` ExtendedInfo | PASS/NOTPASS/OVERFLOW/NOFCR |
| `callVerResult` | `CALL_VER_RESULT` ExtendedInfo | PASS/NOTPASS/NOTCALLVER or empty |
| `cntIn` | `CALL_VER_CNT_IN` ExtendedInfo | Optional |
| `cntOut` | `CALL_VER_CNT_OUT` ExtendedInfo | Optional |
| `srNumber` | `CALL_VER_SR_NUMBER` ExtendedInfo | Optional |
| `agentId` | `CALL_VER_AGENT_ID` ExtendedInfo | Optional |
| `updateDate` | Derived / `activityDate` | EffectiveDate or "" |
| `serviceId` | Subscriber MSISDN | Always |
| `trackingId` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `channel` | `$orderRequest/OrderData/Channel` | Always |

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CJ_UPDATE_CALL_VERIFICATION` | Update subscriber call-ver state in CJ |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit trail |

### §8.3 Backend API

| System | Schema Namespace | Correlation |
|--------|-----------------|-------------|
| CJ | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd8` | IntraActivitySequencing |

### §8.5 ExtendedInfo Fields

| Field | Required? | Usage |
|-------|-----------|-------|
| `CALL_VER_FCR_STATUS` | Optional | → fcrStatus (UNBAR/BAR) |
| `CALL_VER_REASON` | Optional | → callVerReason |
| `CALL_VER_STATUS` | Required | → callVerStatus |
| `CALL_VER_RESULT` | Optional | → callVerResult |
| `CALL_VER_CNT_IN` | Optional | → cntIn |
| `CALL_VER_CNT_OUT` | Optional | → cntOut |
| `CALL_VER_SR_NUMBER` | Optional | → srNumber |
| `CALL_VER_AGENT_ID` | Optional | → agentId |
| `IS_UPDATE_CALLVER` | Required (gate) | OrderData ExtendedInfo; Y/N — this FM runs only when Y |

---

## §9 Payload Build

### §9.7 Complete Generated XML Example

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20260101-001</JMSCorrelationID>
    <OrderID>ORD-12345</OrderID>
    <RefID>SUB-REF-001</RefID>
    <OrderType>1</OrderType>
    <payload>
      <ns:UpdateCallVerification xmlns:ns="http://www.tibco.com/schemas/.../Schema.xsd8">
        <ns:trackingId>OMX-TRK-20260101-001</ns:trackingId>
        <ns:serviceId>0812345678</ns:serviceId>
        <ns:channel>CS</ns:channel>
        <ns:fcrStatus>UNBAR</ns:fcrStatus>
        <ns:callVerReason>PASS_VERIFY</ns:callVerReason>
        <ns:callVerStatus>PASS</ns:callVerStatus>
        <ns:callVerResult>PASS</ns:callVerResult>
        <ns:cntIn>3</ns:cntIn>
        <ns:cntOut>2</ns:cntOut>
        <ns:srNumber>SR-20260101-123</ns:srNumber>
        <ns:agentId>AGENT001</ns:agentId>
        <ns:updateDate>2026-01-01</ns:updateDate>
      </ns:UpdateCallVerification>
    </payload>
  </event>
</createEvent>
```

---

## §10 XSLT Field Mapping

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority              [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId    [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID          [Always]
    ├── RefID                ← $refId                                   [Always]
    ├── UserName             ← $orderRequest/OrderData/User             [Credential-gated: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password         [Credential-gated]
    ├── OrderType            ← $orderRequest/OrderData/OrderType        [Always]
    └── payload
        └── ns:UpdateCallVerification [ns=Schema.xsd8]
            ├── ns:trackingId    ← $orderRequest/OrderData/OMXTrackingId      [Always]
            ├── ns:serviceId     ← $subscriber/MSISDN                         [Always]
            ├── ns:channel       ← $orderRequest/OrderData/Channel            [Always]
            ├── ns:fcrStatus     ← CALL_VER_FCR_STATUS ExtendedInfo           [Conditional]
            ├── ns:callVerReason ← CALL_VER_REASON ExtendedInfo               [Conditional]
            ├── ns:callVerStatus ← CALL_VER_STATUS ExtendedInfo               [Always]
            ├── ns:callVerResult ← CALL_VER_RESULT ExtendedInfo               [Conditional]
            ├── ns:cntIn         ← CALL_VER_CNT_IN ExtendedInfo               [Conditional]
            ├── ns:cntOut        ← CALL_VER_CNT_OUT ExtendedInfo              [Conditional]
            ├── ns:srNumber      ← CALL_VER_SR_NUMBER ExtendedInfo            [Conditional]
            ├── ns:agentId       ← CALL_VER_AGENT_ID ExtendedInfo             [Conditional]
            └── ns:updateDate    ← activityDate (EffectiveDate or "")         [Always]
```

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_REQ")` |
| OPERATION_NAME | `"CJ_UPDATE_CALL_VERIFICATION"` |
| AUDIT_TRACE | `concat("Request Sent for RefId ", $refId)` |
| payload | Conditional on WritePayload="true" |

> **Debug code note:** The source contains `System.debugOut(...)` calls at steps 001–006. These are active debug statements — not commented out. Remove them before production deployment.

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → IN_PROGRESS | `!isSkipped` | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| WAITING → SKIPPED | `isSkipped` | `SkipActivity("4")` |

---

## §13 Exception Handling

All exceptions → `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §15 Function Dependency Tree

```text
Request_CJ_UPDATE_CALL_VERIFICATION
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── GetXMLForSubscriber(orderRequest, refId)                     [if PreExecCheck]
├── Event.createEvent("xslt://CJ_UPDATE_CALL_VERIFICATION")
├── Event.assertEvent(reqEvent)
├── IntraActivitySequencing.ActionRequestEvent(reqEvent, act)
├── Event.Ext.sendEventImmediate(Logger event)
├── IntraActivitySequencing.SendFirstRequestEvent(act)           [if !isSkipped]
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(orderRequest, act, "4")                         [if isSkipped]
└── HandleActivityException(...)                                  [catch]
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | Only execute when `IS_UPDATE_CALLVER=Y` (set by upstream CJ_QUERY_STATE response) |
| R2 | Send all CALL_VER_* fields from subscriber ExtendedInfo |
| R3 | EffectiveDate drives updateDate; falls back to empty string |
| R4 | POU-only loop — no COU |
| R5 | Fan-in: all responses before proceeding |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Commented-out CCBS_CANCEL_SUBS block (dead code) | [MEDIUM] | Remove entirely during migration — dead code creates confusion |
| Active `System.debugOut` calls | [HIGH] | Remove all debug output calls before production |
| IS_UPDATE_CALLVER gate relies on upstream rule setting it correctly | [HIGH] | Unit test state machine in Response_CJ_QUERY_STATE |
| Schema namespace hardcoded | [MEDIUM] | Externalise as GV |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CJ_UPDATE_CALL_VERIFICATION {
  // author: TIT_F25-Maline5
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CJ_UPDATE_CALL_VERIFICATION";
    orderRequest.ProcessFlow.NextActivityID == "CJ_UPDATE_CALL_VERIFICATION";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    // POU loop, already-succeeded guard, PreExecCheck
    // Extract CALL_VER_* fields from subscriber ExtendedInfo
    // activityDate = EffectiveDate if non-empty, else ""
    // Build UpdateCallVerification event (see §9 for XSLT fields)
    // Event.assertEvent + ActionRequestEvent + sendEventImmediate(Logger)
    // SendFirstRequestEvent + Status="1" / SkipActivity("4")
    //
    // DEAD CODE: entire CCBS_CANCEL_SUBS block is commented out — remove during migration
    // DEBUG: System.debugOut calls at 001-006 must be removed before production
  }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

`Response_CJ_UPDATE_CALL_VERIFICATION` parses the CJ response, builds a ResponseBase, and completes fan-in via IntraActivitySequencing. Includes active debug output calls.

### §19.2 Scope Variables

| Variable | Type |
|----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CJ_UPDATE_CALL_VERIFICATION` |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` |

### §19.3 ResponseBase Construction

```text
createObject (ResponseBase)
├── extId            ← OMXUtils.generateTrackingID()           [Always]
├── ResponseCode     ← $eventResponse/ResponseCode             [Conditional: xsl:if]
├── ResponseMessage  ← $eventResponse/ResponseMsg              [Conditional: xsl:if]
├── CompletionStatus ← $eventResponse/CompletionStatus         [Conditional: xsl:if]
└── ReferenceId      ← $eventResponse/RefID                    [Conditional: xsl:if]
```

> All 4 response fields use `xsl:if` — they are absent from the ResponseBase object when the CJ response does not include them.

### §19.4 Response Completion Logic

Fan-in: `IntraActivitySequencing.ActionResponseEvent(currActivity)`

The old `successResponseCount` pattern is commented out. ActionResponseEvent handles the fan-in counter internally.

### §19.5 Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"CJ_UPDATE_CALL_VERIFICATION"` |
| AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` |

> Active `System.debugOut` calls at response steps 001–006 must be removed before production.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
