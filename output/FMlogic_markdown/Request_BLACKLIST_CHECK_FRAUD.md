# Request_BLACKLIST_CHECK_FRAUD

> TIBCO BusinessEvents FM Logic — Fraud blacklist check with Customer Category Type (third of three BL FMs; adds CategoryType vs other BL FMs)

**Author:** awalia-t420 | **Priority:** 5 | **forwardChain:** true | **Pattern:** Single-shot

---

## §1 Overview & Purpose

**BLACKLIST_CHECK_FRAUD** checks whether a customer's ID number appears on the *fraud* blacklist. This is the third of three Blacklist FMs in this order flow (BLACKLIST_CHECK_BLACKLIST → BLACKLIST_CHECK_COLL_BY_ID_NUM → BLACKLIST_CHECK_FRAUD).

This FM shares the same structural template as the other two Blacklist FMs, with one meaningful addition: a `CategoryType` field that classifies the customer type by converting an ASCII code from `CustomerTypeInfo/Type` via `OMXUtils:asciiCodeToText()`.

> **New payload field:** `CategoryType` ← `OMXUtils:asciiCodeToText(Customer/CustomerTypeInfo/Type)` — not present in BLACKLIST_CHECK_BLACKLIST or BLACKLIST_CHECK_COLL_BY_ID_NUM.

> **Read-only FM:** Does not write any enrichment to the orderRequest graph. Results stored in `CheckFraudRes` and `currActivity.ResponseCode/ResponseMessage`.

---

## §Δ Differences from Other Blacklist FMs

| Aspect | BLACKLIST_CHECK_BLACKLIST | BLACKLIST_CHECK_COLL_BY_ID_NUM | BLACKLIST_CHECK_FRAUD |
|--------|--------------------------|-------------------------------|----------------------|
| ActivityID | `BLACKLIST_CHECK_BLACKLIST` | `BLACKLIST_CHECK_COLL_BY_ID_NUM` | `BLACKLIST_CHECK_FRAUD` |
| Request schema | `CheckBlacklistRequest.xsd` | `CheckCollectionByIdNumberRequest.xsd` | `CheckFraudRequest.xsd` |
| Request wrapper | `CheckBlacklistRequest/CheckBlacklist` | `CheckCollectionByIdNumberRequest/CheckCollectionByIdNumber` | `CheckFraudRequest/CheckFraud` |
| **Extra payload field** | — | — | **`CategoryType` ← `OMXUtils:asciiCodeToText(CustomerTypeInfo/Type)`** |
| Response concept | `CheckBlacklistRes` | `CheckCollByIDNumberRes` | `CheckFraudRes` |
| Audit log position | OUTSIDE if block (fires on skip) | INSIDE if block (send path only) | INSIDE if block (send path only) |

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_BLACKLIST_CHECK_FRAUD` |
| Author | awalia-t420 |
| Priority | 5 |
| Forward chain | true |
| Backend system | Blacklist Service (Fraud endpoint) |
| Request schema | `http://www.tibco.com/schemas/SharedResources/Schema Definitions/Blacklist/CheckFraudRequest.xsd` |
| Response schema | `http://www.tibco.com/schemas/SharedResources/Schema Definitions/Blacklist/BlacklistCommonResponse.xsd` |
| Response concept | `Concepts.FM.Response.CheckFraudRes` |
| Fan-out pattern | Single-shot (one request per order) |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | `Customer.Account[1].RefId`, `CustomerGeneralInfo.Identification`, and `CustomerTypeInfo.Type` are read |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Holds PreExecCheck, RequestCount, Status |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "BLACKLIST_CHECK_FRAUD"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "BLACKLIST_CHECK_FRAUD"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Resubmit flag: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Fetch `nextAct` via `Instance.getByExtIdByUri(NextActivityName, Activity)` (nextAct pattern)
3. PreExecCheck: serialize orderRequest → evaluate XPath → set `chkRes`
4. **[if chkRes="true"]** Build `CheckFraudRequest` event with 4 payload fields (RefId, IdNumber, CategoryType, CompanyCode)
5. **[if chkRes="true"]** `sendEventImmediate(reqEvent)`
6. **[if chkRes="true"]** `RequestCount++` (if not resubmit)
7. **[if chkRes="true"] Audit log fired here** (inside block — send path only)
8. **[if chkRes="true"]** `GetActivityStatusString("1", false)` + `SendDataToDB()`
9. **[if chkRes="false"]** `SkipActivity(orderRequest, orderCurrentActivity, "4")`
10. Exception: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Protocol |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.BLACKLIST_CHECK_FRAUD` | JMS → Blacklist Service (Fraud) |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.BLACKLIST_CHECK_FRAUD` | JMS |

### §8.3 Backend API Details

| Property | Value |
|----------|-------|
| System | Blacklist Service (Fraud endpoint) |
| Operation | CheckFraud |
| Request schema | `ns:CheckFraudRequest / ns:CheckFraud` |
| Key inputs | RefId, IdNumber, CategoryType (NEW), CompanyCode="AL" |
| Key outputs | Result, StatusCode, StatusMessage, RefId (BlacklistCommonResponse shared schema) |

### §8.4 Fields Read / Written

**Read:** `Customer.Account[1].RefId`, `Customer.CustomerGeneralInfo.Identification`, `Customer.CustomerTypeInfo.Type` (new)

**Written:** `currActivity.ResponseCode`, `currActivity.ResponseMessage`, `CheckFraudRes` concept appended to `currActivity.Response[]`

No writes to `orderRequest` object graph.

### §8.6 Global Variable Dependencies

Same as other BL FMs: `OMX_COMMON/Component_Name/OMX_CEP`, `OMX_COMMON/Component_Name/OMX_FM`, `MSG_LOG_LEVEL/INFO`, `OMX_OM/WritePayload`.

---

## §9 Payload Build

Same as BLACKLIST_CHECK_COLL_BY_ID_NUM with the addition of `CategoryType`:

```xml
<payload>
  <ns:CheckFraudRequest>
    <ns:CheckFraud>
      <RefId><!-- Customer/Account[1]/RefId --></RefId>
      <IdNumber><!-- Customer/CustomerGeneralInfo/Identification --></IdNumber>
      <CategoryType><!-- OMXUtils:asciiCodeToText(Customer/CustomerTypeInfo/Type) --></CategoryType>
      <CompanyCode>AL</CompanyCode>  <!-- static -->
    </ns:CheckFraud>
  </ns:CheckFraudRequest>
</payload>
```

> **OMXUtils:asciiCodeToText():** Custom TIBCO XSLT extension that converts an ASCII numeric code to its text representation (e.g., 73 → "I" for Individual, 67 → "C" for Corporate). Must be ported or replaced in migration.

---

## §10 XSLT Field Mapping Tree

```text
event
├── JMSPriority         ← $orderRequest/OrderPriority                              [Conditional]
├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId                    [Conditional]
├── OrderID             ← $orderRequest/OrderData/OrderID                          [Conditional]
├── OrderType           ← $orderRequest/OrderData/OrderType                        [Conditional]
└── payload
    └── ns:CheckFraudRequest
        └── ns:CheckFraud
            ├── RefId         ← Customer/Account[1]/RefId                          [Always]
            ├── IdNumber      ← Customer/CustomerGeneralInfo/Identification         [Always]
            ├── CategoryType  ← OMXUtils:asciiCodeToText(CustomerTypeInfo/Type)    [Always; null-safety depends on util]
            └── CompanyCode   ← 'AL' (static)                                      [Always]
```

---

## §11 Audit Logging

**Request audit** — fires *inside* the `if(chkRes=="true")` block (same as BLACKLIST_CHECK_COLL_BY_ID_NUM — silent on skip):

| Field | Value |
|-------|-------|
| OPERATION_NAME | `BLACKLIST_CHECK_FRAUD` |
| AUDIT_TRACE | `Request Sent for BLACKLIST_CHECK_FRAUD` |
| PROCESS_ID | `concat(nanoTime(), "_REQ")` |

**Response audit:**

| Field | Value |
|-------|-------|
| OPERATION_NAME | `BLACKLIST_CHECK_FRAUD` |
| AUDIT_TRACE | `Response received for BLACKLIST_CHECK_FRAUD` |
| PROCESS_ID | `concat(nanoTime(), "_RES")` |

---

## §15 Function Dependency Tree

```text
Request_BLACKLIST_CHECK_FRAUD (rule)
├── Instance.getByExtIdByUri(NextActivityName, Activity)
├── Instance.serializeUsingDefaults(orderRequest)
├── XPath.execute("/("+chkXPath+")", sXML, ...)
├── [if chkRes="true"]:
│   ├── Event.createEvent(BLACKLIST_CHECK_FRAUD XSLT)
│   │   └── CheckFraudRequest/CheckFraud
│   │       ├── RefId         ← Customer/Account[1]/RefId
│   │       ├── IdNumber      ← Customer/CustomerGeneralInfo/Identification
│   │       ├── CategoryType  ← OMXUtils:asciiCodeToText(CustomerTypeInfo/Type)  ★ NEW
│   │       └── CompanyCode   ← 'AL'
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   ├── orderCurrentActivity.RequestCount++
│   ├── Event.Ext.sendEventImmediate(Logger)   ← INSIDE if block
│   ├── GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [if chkRes="false"]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_BLACKLIST_CHECK_FRAUD (rulefunction)
├── Instance.createInstance(CheckFraudRes XSLT)
│   ├── ResponseCode, ResponseMessage, CompletionStatus, ReferenceId
│   └── [for-each BlacklistCommonResponse]: result, statusCode, statusMessage, RefID
├── currActivity.Response[len] = checkFraudRes
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
| R1 | Fraud blacklist check — separate endpoint from standard and collections checks |
| R2 | Must include `CategoryType` in request — derived from `CustomerTypeInfo/Type` ASCII code via `OMXUtils:asciiCodeToText()` |
| R3 | Audit log fires only on send path (not on skip) — consistent with BLACKLIST_CHECK_COLL_BY_ID_NUM |
| R4 | All other requirements same as BLACKLIST_CHECK_BLACKLIST R1–R7 |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `OMXUtils:asciiCodeToText()` is a custom TIBCO XSLT extension — not portable | [HIGH] | Port or replace with equivalent logic; document expected ASCII → text mappings |
| `CustomerTypeInfo/Type` may be null — CategoryType would be empty string | [MEDIUM] | Confirm fraud API accepts empty CategoryType; add null check if needed |
| Inconsistent audit log position across 3 BL FMs | [MEDIUM] | Standardise in migration |
| CompanyCode="AL" hardcoded; Account[1] assumption; null Identification | [HIGH] / [MEDIUM] | See BLACKLIST_CHECK_BLACKLIST §17 |

---

## §18 Full Source Code (Request Rule)

```java
/**
 * Request_BLACKLIST_CHECK_FRAUD
 * Author: awalia-t420 | Priority: 5 | forwardChain: true
 */
rule Rules.OMConsumers.OMXFM.Request.Request_BLACKLIST_CHECK_FRAUD {
  // when: identical to other BL FMs with ActivityID="BLACKLIST_CHECK_FRAUD"
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Activity nextAct = Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName,
                           "/Concepts/OM/ProcessConfig/Activity");
      String chkRes = "true";
      if(String.length(nextAct.PreExecCheck) > 0) {
        String sXML = Instance.serializeUsingDefaults(orderRequest);
        chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, ...);
      }

      if(String.equals(chkRes, "true")) {
        /* XSLT — see §9 — CheckFraudRequest/CheckFraud
           RefId ← Customer/Account[1]/RefId
           IdNumber ← Customer/CustomerGeneralInfo/Identification
           CategoryType ← OMXUtils:asciiCodeToText(Customer/CustomerTypeInfo/Type)  ★ NEW
           CompanyCode ← 'AL' */
        Event.Ext.sendEventImmediate(reqEvent);
        if(!isActResub) orderCurrentActivity.RequestCount++;
        Event.Ext.sendEventImmediate(Logger);  // ← INSIDE if block
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else {
        SkipActivity(orderRequest, orderCurrentActivity, "4");
      }
    } catch (Exception ae) {
      HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 Response Message Rule

Structurally identical to `Response_BLACKLIST_CHECK_COLL_BY_ID_NUM` except response concept type (`CheckFraudRes`) and operation name (`BLACKLIST_CHECK_FRAUD`). All three BL FMs share the same `BlacklistCommonResponse.xsd` response schema.

### §19.3 Response Concept Construction (CheckFraudRes)

```text
CheckFraudRes
├── extId              ← OMXUtils.generateTrackingID() (random)            [Always]
├── ResponseCode       ← $eventResponse/ResponseCode                       [Conditional]
├── ResponseMessage    ← $eventResponse/ResponseMsg                        [Conditional]
├── CompletionStatus   ← $eventResponse/CompletionStatus                   [Conditional]
├── ReferenceId        ← $eventResponse/RefID                              [Conditional]
└── [for-each ns:BlacklistCommonResponse] (same schema as other BL FMs)
    ├── result         ← Result                                            [Conditional]
    ├── statusCode     ← StatusCode                                        [Conditional]
    ├── statusMessage  ← StatusMessage                                     [Conditional]
    └── RefID          ← RefId                                             [Always in loop]
```

**Direct writes:** `currActivity.ResponseCode = eventResponse.ResponseCode` · `currActivity.ResponseMessage = eventResponse.ResponseMsg` · return `"true"`

### §19.4 Response Completion Logic

- Always returns `"true"` (single-shot FM — no fan-in count)

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
