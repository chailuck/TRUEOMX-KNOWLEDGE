# Request_CCBS_SEARCH_ACCOUNT_BY_RESOURCE

> Searches CCBS for the account associated with a subscriber MSISDN (or explicit resource type). Returns CustomerNo and AccountNo, written back to the order for downstream CCBS steps. Opening step in PROMISE_TO_PAY.

---

## §1 — Overview & Purpose

Searches CCBS for the account associated with a subscriber's MSISDN (or explicit resource type). Returns the `CustomerNo` and `AccountNo`, which are written back to the order's Customer and Account structures for use by downstream steps.

Uses the **IntraActivitySequencing** dispatch pattern — single request per order (not per account/subscriber).

> **[LOW] isActResub computed but not acted upon:** The rule computes `isActResub` but never calls `PurgePendingRequestsBeforeResubmit`. For a single-request FM this is low risk but inconsistent with the pattern.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_SEARCH_ACCOUNT_BY_RESOURCE` |
| Priority | 5 |
| ForwardChain | true |
| Rule File | `OMXFM/Request/Request_CCBS_SEARCH_ACCOUNT_BY_RESOURCE.rule` |
| Response Rulefunction | `Response_CCBS_SEARCH_ACCOUNT_BY_RESOURCE.rulefunction` |
| Backend System | CCBS (Customer Care & Billing System) |
| Dispatch Pattern | Single request, IntraActivitySequencing |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context; MSISDN / AccountID written back |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity state, PreExecCheck |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_SEARCH_ACCOUNT_BY_RESOURCE"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_SEARCH_ACCOUNT_BY_RESOURCE"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow

1. Compute `isActResub` (not acted upon — no purge)
2. Read PreExecCheck from activity concept
3. Serialize `orderRequest` and evaluate PreExecCheck XPath
4. If passes: create CCBS_SEARCH_ACCOUNT_BY_RESOURCE event via XSLT
5. `Event.assertEvent(reqEvent)`
6. `IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)`
7. Emit audit logger event
8. `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)`
9. Status="1" + SendDataToDB
10. Else (PreExecCheck false): `SkipActivity("4")`

---

## §6 — ParameterType 2-way Selection

| Priority | Condition | Value |
|----------|-----------|-------|
| 1st | `count(ExtendedInfo[Name="PRIMARY_RESOURCE_TYPE"])>0` | `ExtendedInfo[PRIMARY_RESOURCE_TYPE]/Value` |
| 2nd (otherwise) | Default | `"C"` (static — Cell/MSISDN type) |

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_SEARCH_ACCOUNT_BY_RESOURCE` | Search CCBS account by MSISDN/resource |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_SEARCH_ACCOUNT_BY_RESOURCE` | AccountNo / CustomerNo response |

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | CCBS (Amdocs) |
| Operation | SearchAccountByResource |
| Schema | `amdocs.csm3g.datatypes.ResourceSearchInputInfo` |

### §8.5 ExtendedInfo Fields

| Name | Required/Optional | Purpose |
|------|------------------|---------|
| `PRIMARY_RESOURCE_TYPE` | Optional | Override ParameterType; defaults to "C" if absent |

---

## §9 — Detailed Payload Build

### §9.4 Payload Root Element

| Element | Source / Value | Condition |
|---------|---------------|-----------|
| `ns1:ResourceSearchInputInfo/ns1:ParameterType` | PRIMARY_RESOURCE_TYPE (if present) else "C" | Always (2-way choose) |
| `ns1:ResourceSearchInputInfo/ns1:ParameterValue` | `$orderRequest/OrderData/Customer/ParentOU[1]/Subscriber[1]/MSISDN` | if exists |

### §9.7 Generated XML Example

```xml
<event>
  <JMSCorrelationID>OMX-TRK-001</JMSCorrelationID>
  <payload>
    <ns1:ResourceSearchInputInfo>
      <ns1:ParameterType>C</ns1:ParameterType>
      <ns1:ParameterValue>0812345678</ns1:ParameterValue>
    </ns1:ResourceSearchInputInfo>
  </payload>
</event>
```

---

## §10 — XSLT Field Mapping

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority              [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId    [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID          [Conditional]
    ├── UserName/PassWord    ← (gated: IsEnableUserPass="true")         [Conditional]
    ├── OrderType            ← $orderRequest/OrderData/OrderType        [Conditional]
    ├── CES                  ← $orderRequest/OrderData/CES              [Conditional]
    └── payload
        └── ns1:ResourceSearchInputInfo                                  [Always]
            ├── ns1:ParameterType  ← 2-way: PRIMARY_RESOURCE_TYPE → "C" [Always]
            └── ns1:ParameterValue ← ParentOU[1]/Subscriber[1]/MSISDN   [Conditional]
```

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| Guard | None — always logs |
| PROCESS_ID | `concat(pid, "_REQ")` |
| OPERATION_NAME | "CCBS_SEARCH_ACCOUNT_BY_RESOURCE" |
| AUDIT_TRACE | "Request Sent for CCBS_SEARCH_ACCOUNT_BY_RESOURCE" |
| Payload | Conditional: `WritePayload="true"` |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_SEARCH_ACCOUNT_BY_RESOURCE.rule
├── Instance.getByExtIdByUri(nextActivityName, "/Concepts/OM/ProcessConfig/Activity")
├── Instance.serializeUsingDefaults(orderRequest)
├── XPath.execute(chkXPath, sXML, ns)                [PreExecCheck]
├── Event.createEvent(XSLT → CCBS_SEARCH_ACCOUNT_BY_RESOURCE)
├── Event.assertEvent(reqEvent)
├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
├── Event.Ext.sendEventImmediate(Logger audit)
├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Search CCBS for account by MSISDN (ParameterType="C" default, or PRIMARY_RESOURCE_TYPE if set) |
| R2 | Write CustomerNo to `orderRequest.OrderData.Customer.CustomerId` |
| R3 | Write AccountNo to `orderRequest.OrderData.Customer.Account[0].AccountID` |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| isActResub computed but PurgePending not called | [LOW] | Single-request FM; low risk but add purge for consistency |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_SEARCH_ACCOUNT_BY_RESOURCE {
  attribute { priority = 5; forwardChain = true; }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
    // NOTE: isActResub computed but PurgePendingRequestsBeforeResubmit NOT called
    try {
      Activity nextAct = Instance.getByExtIdByUri(...);
      String chkRes = "true";
      if (String.length(nextAct.PreExecCheck) > 0) {
        String sXML = Instance.serializeUsingDefaults(orderRequest);
        chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=...");
      }
      if (String.equals(chkRes, "true")) {
        Events...CCBS_SEARCH_ACCOUNT_BY_RESOURCE reqEvent = Event.createEvent("xslt://...");
        /* XSLT: ns1:ResourceSearchInputInfo with ParameterType (2-way choose) — see §9 */
        Event.assertEvent(reqEvent);
        IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
        Event.Ext.sendEventImmediate(logEvent);
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
    } catch (Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

Creates a `CCBS_SearchAccountByResource` response concept, extracts `CustomerNo` and `AccountNo` from the CCBS search result, writes them back to the order request, logs, and advances fan-in via IntraActivitySequencing.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | CustomerId and Account[0].AccountID written back |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_SEARCH_ACCOUNT_BY_RESOURCE` | CCBS search result |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking |

### §19.3 Response Concept Construction

Type: `Concepts.FM.Response.CCBS_SearchAccountByResource` (specific — not generic ResponseBase)

```text
createObject
└── object extId=JMSCorrelationID + ":CCBS_SEARCH_ACCOUNT_BY_RESOURCE_RES:" + RefID
    ├── ResponseCode      ← $eventResponse/ResponseCode    [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg     [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId       ← $eventResponse/RefID           [Conditional]
```

### §19.4 Post-Processing — Account/Customer Writeback

| Field Written | Source XPath |
|---------------|-------------|
| `orderRequest.OrderData.Customer.CustomerId` | `xsd2:AccountSearchResultInfoArray/xsd2:AccountSearchResultInfo[1]/xsd2:CustomerNo` |
| `orderRequest.OrderData.Customer.Account[0].AccountID` | `xsd2:AccountSearchResultInfoArray/xsd2:AccountSearchResultInfo/xsd2:AccountNo` |

### §19.5 Fan-in & Completion

| Field | Value |
|-------|-------|
| Pattern | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Returns "true" | When sequencing is complete (all requests responded) |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
