# Request_CCBS_GET_DEALER_POOLS_FOR_DEALER

## §1 Overview & Purpose

**CCBS_GET_DEALER_POOLS_FOR_DEALER** retrieves the dealer pool memberships from CCBS for the dealer code associated with the order. Used during ACTIVATION to determine which pools a dealer can access, enabling downstream pool-based resource allocation.

Unlike most OMXFM rules, this request sends **no business payload element** — only envelope fields (including `dealerCode`). Audit logging is gated by `AllowWriteLog(OrderType)` rather than unconditional.

> Response writes dealer pool names as `DEALER_POOLS` in `Customer.ExtendedInfo` as a comma-delimited string (e.g., `,POOL1,POOL2,`). The extId is deterministic: `"CUSTEXT:"+trackingId+":"+RefID+":DEALER_POOLS"` — enables idempotent lookup.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_DEALER_POOLS_FOR_DEALER` |
| Author | chch |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS |
| Send pattern | `sendEventImmediate` — single request |
| Log gate | `AllowWriteLog(OrderType)` — log only for qualifying order types |
| Response concept | `Concepts.FM.Response.CCBS_GetDealerPoolsForDealer` |
| Response rulefunction | `Response_CCBS_GET_DEALER_POOLS_FOR_DEALER` |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — DealerCode sent; Customer.ExtendedInfo written with DEALER_POOLS |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | ActivityID (operationName), PreExecCheck, RequestCount, Status |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_GET_DEALER_POOLS_FOR_DEALER"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_DEALER_POOLS_FOR_DEALER"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Set `operationName = orderCurrentActivity.ActivityID`
2. Set `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
3. Evaluate PreExecCheck if present; if fails → `SkipActivity("4")`
4. Build request event via XSLT — envelope only, no payload element
5. `Event.Ext.sendEventImmediate(reqEvent)`
6. `Status = GetActivityStatusString("1", false)`
7. **If `AllowWriteLog(OrderType)`:** generate and send REQ audit log
8. If not resubmit: `RequestCount++`
9. `SendDataToDB(orderRequest)`

> **Log gate:** Audit log is only sent if `AllowWriteLog(OrderType)` returns true. Both request and response logs are gated on order type. Most other OMXFM rules log unconditionally.

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Protocol |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_GET_DEALER_POOLS_FOR_DEALER` | JMS / sendEventImmediate |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_GET_DEALER_POOLS_FOR_DEALER` | JMS response |

### §8.3 Backend API

| System | Operation | Notes |
|--------|-----------|-------|
| CCBS | getDealerPoolsForDealer | Envelope-only request — no SOAP payload wrapper; CCBS EJB receives dealerCode as envelope field |

### §8.4 BE Working Memory Written (response)

| Target | extId Pattern | Name | Value |
|--------|---------------|------|-------|
| `Customer.ExtendedInfo[]` | `CUSTEXT:{trackingId}:{RefID}:DEALER_POOLS` | DEALER_POOLS | Comma-delimited pool names (e.g., `,POOL1,POOL2,`) |

---

## §10 XSLT Field Mapping — Envelope Only (No Payload Element)

> This is the only OMXFM request rule in ACTIVATION that sends **no `<payload>` element**. The dealerCode is sent as a top-level envelope field.

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                         [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId               [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                     [Conditional]
    ├── RefID                ← $orderRequest/OrderData/Customer/RefId              [Conditional]
    ├── UserName             ← $orderRequest/OrderData/User                        [Credential-gated: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password                    [Credential-gated: IsEnableUserPass='true']
    ├── OrderType            ← $orderRequest/OrderData/OrderType                   [Conditional]
    ├── CES                  ← $orderRequest/OrderData/CES                         [Conditional]
    └── dealerCode           ← $orderRequest/OrderData/DealerCode                  [Conditional]
```

*No `<payload>` element — CCBS EJB consumes dealerCode directly from envelope.*

---

## §11 Audit Logging

| Log | Gate | OPERATION_NAME | AUDIT_TRACE |
|-----|------|----------------|-------------|
| [REQ] Outbound | `AllowWriteLog(OrderType)` | `$operationName` (dynamic from ActivityID) | `concat("Request Sent for ", operationName)` |
| [RES] Inbound | `AllowWriteLog(OrderType)` | `$operationName` (dynamic from ActivityID) | `concat("Response received for ", operationName)` |

Both REQ and RES logs use dynamic OPERATION_NAME from ActivityID — consistent with each other.

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → ACTIVE | PreExecCheck passes, request sent | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| WAITING → SKIPPED | PreExecCheck fails | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| ACTIVE → COMPLETED | Unconditional (`return "true"`) | Always returns true regardless of response content |

---

## §13 Exception Handling

| Condition | Action |
|-----------|--------|
| Any exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §15 Function Dependency Tree

```text
Request_CCBS_GET_DEALER_POOLS_FOR_DEALER
├── XPath.execute(PreExecCheck, sXML, ns)
├── Event.createEvent("xslt://.../CCBS_GET_DEALER_POOLS_FOR_DEALER", ...)
│   [envelope only: JMSPriority, JMSCorrelationID, OrderID, RefID, UserName,
│    PassWord, OrderType, CES, dealerCode — no payload element]
├── Event.Ext.sendEventImmediate(reqEvent)
├── GetActivityStatusString("1", false)
├── AllowWriteLog(OrderType)
│   └── [if true] sendEventImmediate(Logger REQ)
├── SendDataToDB(orderRequest)
└── HandleActivityException(...)

Response_CCBS_GET_DEALER_POOLS_FOR_DEALER
├── Instance.createInstance("xslt://.../CCBS_GetDealerPoolsForDealer")
│   → extId = "GDPFD:"+trackingId
│   → ResponseCode, ResponseMessage, CompletionStatus, ReferenceId
│   → PoolName[] ← xsl:for-each on ResultTableArray/ResultTable/Code
├── currActivity.Response[n] = activityRes
├── XPath.evalAsString(tib:concat-sequence-format(PoolName, ",")) → poolNames
│   → poolNames = concat(",", sequence, ",")
├── Instance.getByExtIdByUri("CUSTEXT:trackingId:RefID:DEALER_POOLS", CustomerExtendedInfo)
│   [if null] Instance.createInstance(CustomerExtendedInfo{DEALER_POOLS, poolNames})
│              orderRequest.Customer.ExtendedInfo[n] = custExtInfo
├── AllowWriteLog(OrderType)
│   └── [if true] sendEventImmediate(Logger RES)
└── return "true"  (unconditional)
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Send CCBS request with dealerCode as top-level envelope field (no payload wrapper) |
| R2 | Credential gate: include UserName/Password only if IsEnableUserPass='true' |
| R3 | Audit logs gated on AllowWriteLog(OrderType) — not unconditional |
| R4 | Response: extract all pool names from ResultTableArray; concatenate to comma-delimited string |
| R5 | Write DEALER_POOLS to Customer.ExtendedInfo with deterministic extId (idempotent) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Unconditional return "true" — no success check on pool response | [MEDIUM] | Document that missing DEALER_POOLS should be treated as empty pool list |
| Log gated by AllowWriteLog — unusual pattern for OMXFM rules | [LOW] | Document which order types suppress logging; verify in all environments |
| Envelope-only request — no payload namespace wrapper; CCBS EJB protocol implicit | [MEDIUM] | Confirm CCBS EJB API contract; migration target must preserve this envelope structure |

---

## §18 Full Source Code

```java
// @author chch
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_DEALER_POOLS_FOR_DEALER {
  attribute { priority = 5; forwardChain = true; }
  then {
    try {
      String operationName = orderCurrentActivity.ActivityID;
      boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
      // PreExecCheck gate
      if(String.equals(chkRes,"true")) {
        /* XSLT: envelope only (no <payload>) — JMSPriority, JMSCorrelationID, OrderID,
           RefID, UserName/PassWord (credential-gated), OrderType, CES, dealerCode
           — see §10 */
        Event.Ext.sendEventImmediate(reqEvent);
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        if(AllowWriteLog(orderRequest.OrderData.OrderType)) {
          // sendEventImmediate(Logger REQ) — dynamic operationName
        }
        if(!isActResub) orderCurrentActivity.RequestCount++;
        SendDataToDB(orderRequest);
      } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
    } catch(Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
  }
}
```

## §19 Response Message Rule

### §19.1 Overview

Receives CCBS response, creates `CCBS_GetDealerPoolsForDealer` concept via `xsl:for-each` on `ResultTableArray` pool codes. Builds comma-delimited pool name string and writes to `Customer.ExtendedInfo` as `DEALER_POOLS`. Always returns `"true"`.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order — Customer.ExtendedInfo written |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_GET_DEALER_POOLS_FOR_DEALER` | CCBS response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[] appended |

### §19.3 Response Concept Tree

```text
createObject (CCBS_GetDealerPoolsForDealer)
└── object
    ├── @extId            ← concat("GDPFD:", trackingId)                                    [Always — deterministic]
    ├── ResponseCode      ← $eventResponse/ResponseCode                                     [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg                                      [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus                                 [Conditional]
    ├── ReferenceId       ← $eventResponse/RefID                                            [Conditional]
    └── PoolName[]        ← xsl:for-each on payload/ns:ResultTableArray/ns:ResultTable/ns:Code  [Repeated per pool]
```

**DEALER_POOLS string:** `concat(",", tib:concat-sequence-format(PoolName, ","), ",")` — produces leading/trailing commas for easy substring matching (e.g., `contains(DEALER_POOLS, ",POOL1,")`).

### §19.4 Response Completion Logic

`return "true"` — unconditional. No RequestCount comparison.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
