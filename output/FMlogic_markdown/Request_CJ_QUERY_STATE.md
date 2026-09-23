# Request_CJ_QUERY_STATE

## §1 Overview & Purpose

Queries the Customer Journey (CJ) service for the current call-verification state of each POU subscriber. The response drives downstream PROVISIONING flags and PROFCVBAR offer actions through a 12-case state machine in the response handler.

Trigger: `ActivityID == "CJ_QUERY_STATE"` and `Status == "WAITING"`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CJ_QUERY_STATE` |
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
| 2 | `orderCurrentActivity.ActivityID == "CJ_QUERY_STATE"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CJ_QUERY_STATE"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Resubmit check → `PurgePendingRequestsBeforeResubmit` if needed
2. POU loop: iterate ParentOU → Subscriber
3. Already-succeeded guard: skip if Response has CompletionStatus=2 for this RefId
4. PreExecCheck: evaluate XPath via `GetXMLForSubscriber`
5. Build `CJ_QUERY_STATE` event — payload: `ns:QueryStateRequest/ns:serviceId` = subscriber MSISDN
6. `Event.assertEvent(reqEvent)` + `ActionRequestEvent(reqEvent, activity)`
7. Audit log via `sendEventImmediate(Logger)`
8. `SendFirstRequestEvent` + Status="1" + `SendDataToDB` if any sent; else `SkipActivity("4")`
9. Exception → `HandleActivityException`

---

## §7 Data Extraction

POU-only loop. No ChildOU iteration. CJ query is per-subscriber on ParentOU only.

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CJ_QUERY_STATE` | Query subscriber call-verification state |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit trail |

### §8.3 Backend API

| System | Schema Namespace | Correlation |
|--------|-----------------|-------------|
| CJ | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd8` | IntraActivitySequencing |

### §8.5 ExtendedInfo Fields

| Field | Source | Required? | Usage |
|-------|--------|-----------|-------|
| `CALL_VER_STATUS` | Subscriber | Required (response) | Target status — compared against CJ response callVerStatus |

### §8.6 Global Variables

| Path | Usage |
|------|-------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Conditional credentials |
| `OMX_OM/WritePayload` | Conditional payload logging |

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
    <!-- UserName/PassWord: conditional on IsEnableUserPass='true' -->
    <OrderType>1</OrderType>
    <payload>
      <ns:QueryStateRequest xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/.../Schema.xsd8">
        <ns:serviceId>0812345678</ns:serviceId>
      </ns:QueryStateRequest>
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
        └── ns:QueryStateRequest [ns=Schema.xsd8]
            └── ns:serviceId ← $subscriber/MSISDN                      [Always]
```

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_REQ")` |
| OPERATION_NAME | `"CJ_QUERY_STATE"` |
| AUDIT_TRACE | `concat("Request Sent for RefId ", $refId)` |
| payload | Conditional on WritePayload="true" |

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

## §14 Helper Functions

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` | Clear queue on resubmit |
| `GetXMLForSubscriber(orderRequest, refId)` | Serialise subscriber for XPath |
| `IntraActivitySequencing.ActionRequestEvent` | Register in fan-in tracker |
| `IntraActivitySequencing.SendFirstRequestEvent` | Dispatch first queued event |

---

## §15 Function Dependency Tree

```text
Request_CJ_QUERY_STATE
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── GetXMLForSubscriber(orderRequest, refId)                     [if PreExecCheck]
├── Event.createEvent("xslt://CJ_QUERY_STATE")
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
| R1 | Query CJ service with subscriber MSISDN for each POU subscriber |
| R2 | Skip subscribers with existing successful response (idempotency) |
| R3 | Evaluate PreExecCheck XPath before sending |
| R4 | Support resubmit: purge pending + re-issue |
| R5 | Fan-in: all responses before proceeding |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| CJ schema namespace hardcoded | [MEDIUM] | Externalise as GV |
| POU-only — COU not queried | [MEDIUM] | Verify business requirement |
| Response state machine: 12 cases | [HIGH] | Unit test all cases (see §19.4 truth table) |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CJ_QUERY_STATE {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CJ_QUERY_STATE";
    orderRequest.ProcessFlow.NextActivityID == "CJ_QUERY_STATE";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    // POU subscriber loop + already-succeeded guard + PreExecCheck
    // Build QueryStateRequest event — see §9 for XSLT fields
    // Event.assertEvent + ActionRequestEvent + sendEventImmediate(Logger)
    // SendFirstRequestEvent + Status="1" / SkipActivity("4")
  }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

`Response_CJ_QUERY_STATE` runs a 12-case state machine: compares `callVerStatus` from CJ response against `CALL_VER_STATUS` order ExtendedInfo to set PROVISIONING and PROFCVBAR offer actions.

### §19.2 Scope Variables

| Variable | Type |
|----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CJ_QUERY_STATE` |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` |

### §19.3 ResponseBase Construction

```text
createObject (ResponseBase)
├── extId            ← OMXUtils.generateTrackingID()           [Always]
├── ResponseCode     ← $eventResponse/ResponseCode             [Always]
├── ResponseMessage  ← $eventResponse/ResponseMsg              [Always]
├── CompletionStatus ← $eventResponse/CompletionStatus         [Always]
└── ReferenceId      ← $eventResponse/RefID                    [Always]
```

### §19.4 State Machine Decision Table

| currentStatus (CJ) | newStatus (Order) | PROVISIONING | action | IS_UPDATE_CALLVER |
|---|---|---|---|---|
| NOFCR | PASS | Y | REMOVE | Y |
| NOFCR | OVERFLOW | Y | REMOVE | Y |
| NOFCR | NOTPASS | N | NoSet | Y |
| NOTPASS | PASS | Y | REMOVE | Y |
| NOTPASS | OVERFLOW | Y | REMOVE | Y |
| NOTPASS | NOTPASS | N | NoSet | Y |
| OVERFLOW | PASS | N | NoSet | Y |
| OVERFLOW | OVERFLOW | N | NoSet | Y |
| OVERFLOW | NOTPASS | Y | ADD ★ | Y |
| PASS | PASS | Y | REMOVE | Y |
| PASS | NOTPASS | N | NoSet | **N** |
| PASS | OVERFLOW | N | NoSet | **N** |

> ★ OVERFLOW→NOTPASS: creates new SubscriberOffers(OfferName=PROFCVBAR, ServiceType=85, Action=ADD, FE_OR_CCBS=FE)

> IS_UPDATE_CALLVER=N suppresses the downstream CJ_UPDATE_CALL_VERIFICATION step.

> All PROFCVBAR offers: `subOffer.Action = action` + append `CALL_VER_RESULT` ExtendedInfo.

Fan-in: `IntraActivitySequencing.ActionResponseEvent(currActivity)`

### §19.5 Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"CJ_QUERY_STATE"` |
| AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
