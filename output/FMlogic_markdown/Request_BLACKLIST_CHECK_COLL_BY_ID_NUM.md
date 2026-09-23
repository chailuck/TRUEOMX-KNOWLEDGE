# Request_BLACKLIST_CHECK_COLL_BY_ID_NUM

> TIBCO BusinessEvents FM Logic — Collections blacklist check by Customer Identification number (near-twin of BLACKLIST_CHECK_BLACKLIST)

**Author:** awalia-t420 | **Priority:** 5 | **forwardChain:** true | **Pattern:** Single-shot

---

## §1 Overview & Purpose

**BLACKLIST_CHECK_COLL_BY_ID_NUM** checks whether a customer's ID number appears on the *collections* blacklist — a separate list from the general blacklist checked by `BLACKLIST_CHECK_BLACKLIST`. The collections blacklist typically flags customers with outstanding debts or delinquency.

This FM is a structural near-twin of `BLACKLIST_CHECK_BLACKLIST`. The request payload, response concept structure, and result storage pattern are identical. The key differences are the **operation name**, **request schema/element**, **response concept type**, and the **position of the audit log** within the execution flow.

> **Read-only FM:** Like BLACKLIST_CHECK_BLACKLIST, this FM does not write any enrichment to the orderRequest graph. Results are stored in `CheckCollByIDNumberRes` and `currActivity.ResponseCode/ResponseMessage`.

---

## §Δ Differences from BLACKLIST_CHECK_BLACKLIST

This section covers all meaningful differences. Everything not listed here is identical to `Request_BLACKLIST_CHECK_BLACKLIST` — see that document for full context.

| Aspect | BLACKLIST_CHECK_BLACKLIST | BLACKLIST_CHECK_COLL_BY_ID_NUM |
|--------|--------------------------|-------------------------------|
| ActivityID | `BLACKLIST_CHECK_BLACKLIST` | `BLACKLIST_CHECK_COLL_BY_ID_NUM` |
| Request schema | `CheckBlacklistRequest.xsd` | `CheckCollectionByIdNumberRequest.xsd` |
| Request wrapper | `ns:CheckBlacklistRequest / ns:CheckBlacklist` | `ns:CheckCollectionByIdNumberRequest / ns:CheckCollectionByIdNumber` |
| Response concept type | `CheckBlacklistRes` | `CheckCollByIDNumberRes` |
| Response schema | `BlacklistCommonResponse.xsd` (shared) | `BlacklistCommonResponse.xsd` (same shared schema) |
| **Audit log position** | OUTSIDE the `if(chkRes=="true")` block — fires on both send AND skip paths | **INSIDE** the `if(chkRes=="true")` block — fires only when request is sent; silent on skip |
| Audit execution order | send → RequestCount++ → status → DB → [exit if] → audit | send → RequestCount++ → **audit** → status → DB |

> **Audit log behaviour difference:** In BLACKLIST_CHECK_BLACKLIST the audit logger fires unconditionally (even on skip). In this FM, the audit logger fires only when `chkRes="true"` — skipped activities produce no audit log entry. Migration should standardise this behaviour across both BL FMs.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_BLACKLIST_CHECK_COLL_BY_ID_NUM` |
| Author | awalia-t420 |
| Priority | 5 |
| Forward chain | true |
| Backend system | Blacklist Service (Collections endpoint) |
| Request schema | `http://www.tibco.com/schemas/SharedResources/Schema Definitions/Blacklist/CheckCollectionByIdNumberRequest.xsd` |
| Response schema | `http://www.tibco.com/schemas/SharedResources/Schema Definitions/Blacklist/BlacklistCommonResponse.xsd` |
| Response concept | `Concepts.FM.Response.CheckCollByIDNumberRes` |
| Fan-out pattern | Single-shot (one request per order) |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | `Customer.Account[1].RefId` and `CustomerGeneralInfo.Identification` are read |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Holds PreExecCheck, RequestCount |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "BLACKLIST_CHECK_COLL_BY_ID_NUM"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "BLACKLIST_CHECK_COLL_BY_ID_NUM"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Resubmit flag: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Fetch `nextAct` from working memory (PreExecCheck source)
3. PreExecCheck: serialize orderRequest → evaluate XPath → set `chkRes`
4. **[if chkRes="true"]** Build and fire `BLACKLIST_CHECK_COLL_BY_ID_NUM` event
5. **[if chkRes="true"]** `RequestCount++` (if not resubmit)
6. **[if chkRes="true"] Audit log fired here** — inside the if block
7. **[if chkRes="true"]** `GetActivityStatusString("1", false)` + `SendDataToDB()`
8. **[if chkRes="false"]** `SkipActivity(orderRequest, orderCurrentActivity, "4")` — no audit log
9. Exception: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Protocol |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.BLACKLIST_CHECK_COLL_BY_ID_NUM` | JMS → Blacklist Service |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.BLACKLIST_CHECK_COLL_BY_ID_NUM` | JMS |

### §8.3 Backend API Details

| Property | Value |
|----------|-------|
| System | Blacklist Service (Collections endpoint) |
| Operation | CheckCollectionByIdNumber |
| Request schema | `ns:CheckCollectionByIdNumberRequest / ns:CheckCollectionByIdNumber` |
| Key inputs | RefId (Account[1].RefId), IdNumber (Identification), CompanyCode="AL" |
| Key outputs | Result, StatusCode, StatusMessage, RefId (from BlacklistCommonResponse — same schema as standard BL) |

### §8.4 Fields Read / Written

**Read:** `Customer.Account[1].RefId`, `Customer.CustomerGeneralInfo.Identification`

**Written:** `currActivity.ResponseCode`, `currActivity.ResponseMessage`, `CheckCollByIDNumberRes` concept appended to `currActivity.Response[]`

No writes to `orderRequest` object graph.

### §8.6 Global Variable Dependencies

Same as BLACKLIST_CHECK_BLACKLIST: `OMX_COMMON/Component_Name/OMX_CEP`, `OMX_COMMON/Component_Name/OMX_FM`, `MSG_LOG_LEVEL/INFO`, `OMX_OM/WritePayload`.

---

## §9 Payload Build

Identical to BLACKLIST_CHECK_BLACKLIST except the wrapper elements:

```xml
<payload>
  <ns:CheckCollectionByIdNumberRequest>
    <ns:CheckCollectionByIdNumber>
      <RefId><!-- Customer/Account[1]/RefId --></RefId>
      <IdNumber><!-- Customer/CustomerGeneralInfo/Identification --></IdNumber>
      <CompanyCode>AL</CompanyCode>  <!-- static -->
    </ns:CheckCollectionByIdNumber>
  </ns:CheckCollectionByIdNumberRequest>
</payload>
```

JMS headers (JMSPriority, JMSCorrelationID, OrderID, OrderType) same as BLACKLIST_CHECK_BLACKLIST. No RefID header, no CES, no credential fields.

---

## §10 XSLT Field Mapping Tree

```text
event
└── JMSPriority         ← $orderRequest/OrderPriority          [Conditional]
└── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId [Conditional]
└── OrderID             ← $orderRequest/OrderData/OrderID       [Conditional]
└── OrderType           ← $orderRequest/OrderData/OrderType     [Conditional]
└── payload
    └── ns:CheckCollectionByIdNumberRequest
        └── ns:CheckCollectionByIdNumber
            ├── RefId         ← Customer/Account[1]/RefId                           [Always]
            ├── IdNumber      ← Customer/CustomerGeneralInfo/Identification          [Always]
            └── CompanyCode   ← 'AL' (static hardcoded)                             [Always]
```

---

## §11 Audit Logging

**Request audit** — fires *inside* the `if(chkRes=="true")` block (only when request is sent; silent on skip):

| Field | Value |
|-------|-------|
| OPERATION_NAME | `BLACKLIST_CHECK_COLL_BY_ID_NUM` |
| AUDIT_TRACE | `Request Sent for BLACKLIST_CHECK_COLL_BY_ID_NUM` |
| PROCESS_ID | `concat(nanoTime(), "_REQ")` |

**Response audit:**

| Field | Value |
|-------|-------|
| OPERATION_NAME | `BLACKLIST_CHECK_COLL_BY_ID_NUM` |
| AUDIT_TRACE | `Response received for BLACKLIST_CHECK_COLL_BY_ID_NUM` |
| PROCESS_ID | `concat(nanoTime(), "_RES")` |

---

## §15 Function Dependency Tree

```text
Request_BLACKLIST_CHECK_COLL_BY_ID_NUM (rule)
├── Instance.getByExtIdByUri(NextActivityName, Activity)   [nextAct for PreExecCheck]
├── Instance.serializeUsingDefaults(orderRequest)
├── XPath.execute("/("+chkXPath+")", sXML, ...)
├── [if chkRes="true"]:
│   ├── Event.createEvent(BLACKLIST_CHECK_COLL_BY_ID_NUM XSLT)
│   │   └── CheckCollectionByIdNumberRequest/CheckCollectionByIdNumber
│   │       ├── RefId ← Customer/Account[1]/RefId
│   │       ├── IdNumber ← Customer/CustomerGeneralInfo/Identification
│   │       └── CompanyCode ← 'AL'
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   ├── orderCurrentActivity.RequestCount++
│   ├── Event.Ext.sendEventImmediate(Logger)   ← INSIDE if block (differs from BL_CHECK_BLACKLIST)
│   ├── GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [if chkRes="false"]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_BLACKLIST_CHECK_COLL_BY_ID_NUM (rulefunction)
├── Instance.createInstance(CheckCollByIDNumberRes XSLT)
│   ├── ResponseCode, ResponseMessage, CompletionStatus, ReferenceId (standard)
│   └── [for-each BlacklistCommonResponse]: result, statusCode, statusMessage, RefID
├── currActivity.Response[len] = checkCollRes
├── currActivity.ResponseCode = eventResponse.ResponseCode
├── currActivity.ResponseMessage = eventResponse.ResponseMsg
├── Event.Ext.sendEventImmediate(Logger)
└── return "true"
```

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Collections blacklist check (separate from standard BLACKLIST_CHECK_BLACKLIST) — different operation, same payload structure |
| R2 | Audit log fires only on send path (not on skip) — unlike BLACKLIST_CHECK_BLACKLIST |
| R3 | All other requirements identical to BLACKLIST_CHECK_BLACKLIST (R1–R7) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Inconsistent audit log placement vs BLACKLIST_CHECK_BLACKLIST — one fires on skip, one doesn't | [MEDIUM] | Standardise audit log behaviour across all BL FMs in migration |
| Same risks as BLACKLIST_CHECK_BLACKLIST: hardcoded CompanyCode="AL", Account[1] assumption, null Identification | [HIGH] / [MEDIUM] | See BLACKLIST_CHECK_BLACKLIST §17 for mitigations |

---

## §18 Full Source Code (Request Rule)

```java
/**
 * Request_BLACKLIST_CHECK_COLL_BY_ID_NUM
 * Author: awalia-t420 | Priority: 5 | forwardChain: true
 */
rule Rules.OMConsumers.OMXFM.Request.Request_BLACKLIST_CHECK_COLL_BY_ID_NUM {
  // when block: identical to BLACKLIST_CHECK_BLACKLIST with ActivityID="BLACKLIST_CHECK_COLL_BY_ID_NUM"
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Activity nextAct = Instance.getByExtIdByUri(...);
      String chkRes = "true";
      // PreExecCheck eval via nextAct.PreExecCheck

      if(String.equals(chkRes, "true")) {
        /* XSLT — see §9 — generates CheckCollectionByIdNumberRequest/CheckCollectionByIdNumber
           RefId ← Customer/Account[1]/RefId
           IdNumber ← Customer/CustomerGeneralInfo/Identification
           CompanyCode ← 'AL' */
        Event.Ext.sendEventImmediate(reqEvent);
        if(!isActResub) orderCurrentActivity.RequestCount++;
        Event.Ext.sendEventImmediate(Logger);  // ← INSIDE if block (key diff from BL_CHECK_BLACKLIST)
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else {
        SkipActivity(orderRequest, orderCurrentActivity, "4");
        // No audit log on skip path
      }
    } catch (Exception ae) {
      HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 Response Message Rule

Structurally identical to `Response_BLACKLIST_CHECK_BLACKLIST` except:

- Response concept type: `CheckCollByIDNumberRes` (vs `CheckBlacklistRes`)
- Operation name in audit: `BLACKLIST_CHECK_COLL_BY_ID_NUM`

Response schema, for-each structure, `currActivity` direct writes, and `return "true"` are all identical.

### §19.3 Response Concept Construction (CheckCollByIDNumberRes)

```text
CheckCollByIDNumberRes
├── extId              ← OMXUtils.generateTrackingID() (random)            [Always]
├── ResponseCode       ← $eventResponse/ResponseCode                       [Conditional]
├── ResponseMessage    ← $eventResponse/ResponseMsg                        [Conditional]
├── CompletionStatus   ← $eventResponse/CompletionStatus                   [Conditional]
├── ReferenceId        ← $eventResponse/RefID                              [Conditional]
└── [for-each ns:BlacklistCommonResponse]
    ├── result         ← Result                                            [Conditional]
    ├── statusCode     ← StatusCode                                        [Conditional]
    ├── statusMessage  ← StatusMessage                                     [Conditional]
    └── RefID          ← RefId                                             [Always in loop]
```

**Direct writes:** `currActivity.ResponseCode = eventResponse.ResponseCode` · `currActivity.ResponseMessage = eventResponse.ResponseMsg` · return `"true"`

### §19.4 Response Completion Logic

- Always returns `"true"` (single-shot FM — no fan-in count)
- `"true"` signals the orchestrator that the collections check reply has been received

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
