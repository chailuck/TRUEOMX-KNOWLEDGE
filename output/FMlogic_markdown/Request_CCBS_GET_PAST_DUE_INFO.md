# Request_CCBS_GET_PAST_DUE_INFO

> Fetches past-due amount per Account from CCBS. Writes PAST_DUE_AMOUNT to all accounts' ExtendedInfo. Per-account loop with IntraActivitySequencing. Step 3 in PROMISE_TO_PAY.

---

## §1 — Overview & Purpose

Fetches the past-due amount for each Account on the order from CCBS. The retrieved `DueAmount` is written back as `AccountExtendedInfo.PAST_DUE_AMOUNT` on every account. Gated by a PreExecCheck that skips it if PAST_DUE_AMOUNT is already populated.

Uses **IntraActivitySequencing** with a **per-account loop** — one request sent per `Account` in `orderRequest.OrderData.Customer.Account`.

> **[MEDIUM] Double-prefix event name:** The event type is `Events.OMConsumers.OMXFM.Request.CCBS_CCBS_GET_PAST_DUE_INFO` — the "CCBS_" prefix is duplicated. Verify against ESB channel configuration.

> **[LOW] LogicalDate concept read but not used:** Read into scope but never referenced in XSLT — likely dead code or TODO for date-anchored past-due queries.

> **[NOTE] PreExecCheck scope:** Evaluated against `orderRequest.OrderData` (not full `orderRequest`). XPath `//Account/ExtendedInfo` searches under OrderData only.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_PAST_DUE_INFO` |
| Priority | 5 |
| ForwardChain | true |
| Rule File | `OMXFM/Request/Request_CCBS_GET_PAST_DUE_INFO.rule` |
| Response Rulefunction | `Response_CCBS_GET_PAST_DUE_INFO.rulefunction` |
| Backend System | CCBS (Customer Care & Billing System) |
| Dispatch Pattern | Per-account loop, IntraActivitySequencing |
| Loop Variable | `orderRequest.OrderData.Customer.Account@length` |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order; PAST_DUE_AMOUNT written back to all Accounts |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity state, RequestCount fan-in counter |
| `$account` | `Concepts.OrderRequest.Account` | Per-iteration loop variable |
| `logicalDate` | `Concepts.LogicalDate` | Read into scope but NOT used (dead code/TODO) |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_GET_PAST_DUE_INFO"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_PAST_DUE_INFO"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow

1. Compute `isActResub`
2. Call `PurgePendingRequestsBeforeResubmit` if `isActResub==true`
3. Read PreExecCheck (evaluated against `orderRequest.OrderData`)
4. Evaluate PreExecCheck XPath on OrderData XML
5. If fails: `SkipActivity("4")` (PAST_DUE_AMOUNT already populated)
6. If passes: loop `i = 0 to Account@length - 1`
7. Per iteration: serialize `$account`, build XSLT request
8. Assert event, `ActionRequestEvent`, emit per-account audit log
9. After loop: `SendFirstRequestEvent`
10. Status="1" + SendDataToDB

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_CCBS_GET_PAST_DUE_INFO` ⚠ double prefix | Fetch past-due amount per Account |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_GET_PAST_DUE_INFO` | DueAmount per Account |

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | CCBS (Amdocs) |
| Operation | GetPastDueInfo |
| Request Schema | `ns5:GetPastDueInfoRequest/ns4:ClEntityIdInfo` |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameters

| Param | Bound From |
|-------|-----------|
| `$orderRequest` | Full order request concept |
| `$globalVariables` | Global configuration |
| `$account` | Per-iteration Account concept |

### §9.4 Payload Root Element

| Element | Source / Value | Condition |
|---------|---------------|-----------|
| `ns5:GetPastDueInfoRequest/ns4:ClEntityIdInfo/EntityId` | `$account/AccountID` | Always |
| `ns5:GetPastDueInfoRequest/ns4:ClEntityIdInfo/EntityType` | "ACCOUNT" (static) | Always |

### §9.7 Generated XML Example

```xml
<event>
  <JMSCorrelationID>OMX-TRK-001</JMSCorrelationID>
  <payload>
    <ns5:GetPastDueInfoRequest>
      <ns4:ClEntityIdInfo>
        <EntityId>100012345</EntityId>
        <EntityType>ACCOUNT</EntityType>
      </ns4:ClEntityIdInfo>
    </ns5:GetPastDueInfoRequest>
  </payload>
</event>
```

---

## §10 — XSLT Field Mapping

```text
createEvent
└── event
    ├── JMSPriority / JMSCorrelationID / OrderID / OrderType / CES  [Conditional]
    └── payload
        └── ns5:GetPastDueInfoRequest                               [Always]
            └── ns4:ClEntityIdInfo
                ├── EntityId    ← $account/AccountID               [Always]
                └── EntityType  ← "ACCOUNT" (static)               [Always]
```

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| Guard | Conditional — `AllowWriteLog` |
| PROCESS_ID | `concat(pid, "_REQ")` |
| OPERATION_NAME | "CCBS_GET_PAST_DUE_INFO" |
| AUDIT_TRACE | "Request Sent for CCBS_GET_PAST_DUE_INFO" |
| Payload | Conditional: `WritePayload="true"` |
| Timing | Per loop iteration (per Account) |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_GET_PAST_DUE_INFO.rule
├── PurgePendingRequestsBeforeResubmit(...)           [conditional on isActResub]
├── Instance.getByExtIdByUri(nextActivityName, ...)
├── Instance.serializeUsingDefaults(orderRequest.OrderData)   [NOTE: OrderData scope]
├── XPath.execute(chkXPath, sXML_OrderData, ns)               [PreExecCheck]
├── SkipActivity("4")                                          [if PreExecCheck false]
├── [Loop: i=0 → Account@length-1]
│   ├── Instance.serializeUsingDefaults($account)
│   ├── Event.createEvent(XSLT → CCBS_CCBS_GET_PAST_DUE_INFO) [NOTE: double prefix]
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   └── Event.Ext.sendEventImmediate(logger audit)
├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
└── HandleActivityException(...)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Fetch past-due amount per Account from CCBS (EntityType="ACCOUNT") |
| R2 | Skip if PAST_DUE_AMOUNT ExtendedInfo already populated on any account |
| R3 | Write PAST_DUE_AMOUNT to every account's ExtendedInfo |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Event type double-prefix `CCBS_CCBS_GET_PAST_DUE_INFO` | [MEDIUM] | Verify ESB destination channel |
| LogicalDate read but not used | [LOW] | Remove dead variable or implement |
| PreExecCheck on OrderData not full orderRequest | [NOTE] | Ensure XPath refs are OrderData-relative |
| Response writes PAST_DUE_AMOUNT to ALL accounts | [LOW] | Verify intent for multi-account orders |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_PAST_DUE_INFO {
  attribute { priority = 5; forwardChain = true; }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
    if (isActResub) { PurgePendingRequestsBeforeResubmit(orderRequest, orderCurrentActivity); }
    try {
      // NOTE: LogicalDate read but never used in payload
      boolean isSkipped = true;
      String chkRes = "true";
      if (String.length(nextAct.PreExecCheck) > 0) {
        String sXML = Instance.serializeUsingDefaults(orderRequest.OrderData); // NOTE: OrderData scope
        chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=...");
      }
      if (String.equals(chkRes, "true")) {
        isSkipped = false;
        for (int i = 0; i < orderRequest.OrderData.Customer.Account@length; i++) {
          Account account = orderRequest.OrderData.Customer.Account[i];
          Events...CCBS_CCBS_GET_PAST_DUE_INFO reqEvent = Event.createEvent("xslt://...");
          /* XSLT: ns5:GetPastDueInfoRequest / ns4:ClEntityIdInfo — see §9 */
          Event.assertEvent(reqEvent);
          IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
          Event.Ext.sendEventImmediate(logEvent);
        }
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

Creates a `CCBS_GetPastDueInfoRes` response concept, extracts `DueAmount`, writes it as `AccountExtendedInfo.PAST_DUE_AMOUNT` on **all accounts**, logs, and advances fan-in.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | PAST_DUE_AMOUNT written to all Account ExtendedInfo |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_GET_PAST_DUE_INFO` | Raw CCBS response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking |

### §19.3 Response Concept

Type: `Concepts.FM.Response.CCBS_GetPastDueInfoRes` (specific)

extId: `OMXUtils:generateTrackingID()`

### §19.4 Post-Processing — PAST_DUE_AMOUNT Writeback

| Operation | Detail |
|-----------|--------|
| Read | `xsd2:CalculateDebtInfo/xsd2:DueAmount` → `pastDueAmount` (double) |
| Loop | `for i in 0..Account@length-1` |
| Create | `AccountExtendedInfo { Name="PAST_DUE_AMOUNT", Value=pastDueAmount }` |
| Append | `Account[i].ExtendedInfo += newExtInfo` |

### §19.5 Fan-in & Completion

| Field | Value |
|-------|-------|
| Pattern | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Audit | OPERATION_NAME="CCBS_GET_PAST_DUE_INFO"; conditional WritePayload |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
