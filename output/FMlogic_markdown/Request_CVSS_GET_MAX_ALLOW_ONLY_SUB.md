# Request_CVSS_GET_MAX_ALLOW_ONLY_SUB

## §1 Overview & Purpose

**CVSS_GET_MAX_ALLOW_ONLY_SUB** queries CVSS for the maximum number of allowed-only subscribers for a given customer, based on their Thai ID, customer category type, and company code. Used during ACTIVATION to enforce subscriber count limits.

The response handler writes `MAX_ALLOW_ONLY_SUB` into both the Subscriber's `ExtendedInfo` and `Customer.ExtendedInfo`, enabling downstream rules to compare existing subscriber counts against the allowed maximum.

> Channel mapping: Channel='EOC' → 'SHOP'; DealerCode starts-with '8' → 'SHOP'; otherwise → 'DEALER'.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CVSS_GET_MAX_ALLOW_ONLY_SUB` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | CVSS |
| Send pattern | `sendEventImmediate` — single request |
| Response concept | `Concepts.FM.Response.GetMaxAllowOnlySubRes` |
| Response rulefunction | `Response_CVSS_GET_MAX_ALLOW_ONLY_SUB` |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — Identification, CustomerTypeInfo.Type, CompanyCode, SubscriberType; ExtendedInfo written |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | PreExecCheck, RequestCount, Status, ResponseCode, ResponseMessage |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CVSS_GET_MAX_ALLOW_ONLY_SUB"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CVSS_GET_MAX_ALLOW_ONLY_SUB"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Set `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Extract: `thaiId = Identification`; `refId = Customer.CustomerId`
3. Evaluate PreExecCheck; if fails → `SkipActivity("4")`
4. Build `CVSS_GET_MAX_ALLOW_ONLY_SUB` event: thaiId, categoryType, companyCode, channel, RefId
5. `Event.Ext.sendEventImmediate(reqEvent)`
6. If not resubmit: `RequestCount++`
7. Send REQ audit log
8. `Status = GetActivityStatusString("1", false)` + `SendDataToDB`

---

## §7 Data Extraction & Business Logic

### companyCode Priority

| Priority | Source | Condition |
|----------|--------|-----------|
| 1 | `Account[1]/AccountManagementInfo/CompanyCode` | If not blank |
| 2a | `ParentOU/Subscriber[SubscriberType!=""]/SubscriberType` | POU subscriber |
| 2b | `ParentOU/ChildOU/Subscriber[SubscriberType!=""]/SubscriberType` | ChildOU subscriber |

### channel Mapping

| Condition | Channel |
|-----------|---------|
| `OrderData.Channel = 'EOC'` | `'SHOP'` |
| `DealerCode starts-with '8'` | `'SHOP'` |
| Otherwise | `'DEALER'` |

### categoryType
`OMXUtils:asciiCodeToText(CustomerTypeInfo.Type)` — converts numeric type code to text.

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Protocol |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CVSS_GET_MAX_ALLOW_ONLY_SUB` | JMS / sendEventImmediate |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CVSS_GET_MAX_ALLOW_ONLY_SUB` | JMS response |

### §8.3 Backend API

| System | Operation | Namespace |
|--------|-----------|-----------|
| CVSS | getMaxAllowOnlySub | `http://services.omx.truecorp.co.th/FM/getMaxAllowOnlySub` |

### §8.4 BE Working Memory Written (response)

| Target | ExtendedInfo Name | Value |
|--------|-------------------|-------|
| `Subscriber.ExtendedInfo[]` (by RefID) | `MAX_ALLOW_ONLY_SUB` | `getMaxAllowRes.maxAllow` |
| `Customer.ExtendedInfo[]` | `MAX_ALLOW_ONLY_SUB` | `getMaxAllowRes.maxAllow` |

---

## §9 Request Payload Tree

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                    [Conditional]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId          [Conditional]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID                [Conditional]
    ├── RefID                    ← $refId (Customer.CustomerId)                   [Always]
    ├── OrderType                ← $orderRequest/OrderData/OrderType              [Conditional]
    └── payload
        └── ns:getMaxAllowOnlySubRequest
            └── ns:getMaxAllowOnlySub
                ├── ns:thaiId        ← $thaiId (Identification)                  [Always]
                ├── ns:categoryType  ← OMXUtils:asciiCodeToText(CustomerType)    [Always]
                ├── ns:companyCode   ← Account[1]/CompanyCode OR SubscriberType  [Conditional chain — see §7]
                ├── ns:channel       ← 'SHOP' or 'DEALER'                        [Conditional — see §7]
                └── ns:RefId         ← Customer/Account[1]/RefId                 [Always]
```

---

## §11 Audit Logging

| Log | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE |
|-----|-----------|----------------|-------------|
| [REQ] | `concat(pid,"_REQ")` | `CVSS_GET_MAX_ALLOW_ONLY_SUB` | Request Sent for CVSS_GET_MAX_ALLOW_ONLY_SUB |
| [RES] | `concat(pid,"_RES")` | `CVSS_GET_MAX_ALLOW_ONLY_SUB` | Response received for CVSS_GET_MAX_ALLOW_ONLY_SUB |

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → ACTIVE | PreExecCheck passes | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| WAITING → SKIPPED | PreExecCheck fails | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| ACTIVE → COMPLETED | Unconditional | `return "true"` — always |

> Fan-in is unconditional. Downstream rules must check ResponseCode if needed.

---

## §13 Exception Handling

| Condition | Action |
|-----------|--------|
| Any exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §15 Function Dependency Tree

```text
Request_CVSS_GET_MAX_ALLOW_ONLY_SUB
├── XPath.execute(PreExecCheck, sXML, ns)
├── Event.createEvent("xslt://.../CVSS_GET_MAX_ALLOW_ONLY_SUB", ...)
├── Event.Ext.sendEventImmediate(reqEvent)
├── sendEventImmediate(Logger REQ)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
└── HandleActivityException(...)

Response_CVSS_GET_MAX_ALLOW_ONLY_SUB
├── OMXUtils.generateTrackingID()
├── Instance.createInstance("xslt://.../GetMaxAllowOnlySubRes")  [empty object]
├── XPath.execute → getMaxAllowRes.Reference, creditClass, maxAllow, statusCode, statusMessage
├── getMaxAllowRes.ResponseCode = eventResponse.ResponseCode
├── currActivity.Response[n] = getMaxAllowRes
├── currActivity.ResponseCode = eventResponse.ResponseCode
├── Instance.getByExtIdByUri("A:"+trackingId+":"+RefID, Subscriber)
│   └── [if found] acc.ExtendedInfo[n] = AccountExtendedInfo{MAX_ALLOW_ONLY_SUB}
├── Instance.createInstance(CustomerExtendedInfo{MAX_ALLOW_ONLY_SUB, maxAllow})
├── orderRequest.Customer.ExtendedInfo[n] = custExtendedInfo
├── sendEventImmediate(Logger RES)
└── return "true"  (unconditional)
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Send thaiId, categoryType (asciiCodeToText), companyCode (priority chain), channel |
| R2 | companyCode: Account CompanyCode first, then SubscriberType from POU or ChildOU |
| R3 | channel: EOC→SHOP, DealerCode starts-with-8→SHOP, else→DEALER |
| R4 | Write MAX_ALLOW_ONLY_SUB to both Subscriber.ExtendedInfo and Customer.ExtendedInfo |
| R5 | Also store creditClass, statusCode, statusMessage in response concept |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Unconditional return "true" — no ResponseCode success check | [MEDIUM] | Downstream rules must handle CVSS errors via ResponseCode |
| Subscriber lookup by extId "A:trackingId:RefID" — brittle | [MEDIUM] | If extId construction changes, MAX_ALLOW_ONLY_SUB won't write to Subscriber |
| companyCode fallback non-deterministic if multiple Subscribers with SubscriberType | [LOW] | Document single-SubscriberType assumption per POU/ChildOU |

---

## §18 Full Source Code

```java
// @author awalia-t420
rule Rules.OMConsumers.OMXFM.Request.Request_CVSS_GET_MAX_ALLOW_ONLY_SUB {
  attribute { priority = 5; forwardChain = true; }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      String thaiId = orderRequest.OrderData.Customer.CustomerGeneralInfo.Identification;
      String refId  = orderRequest.OrderData.Customer.CustomerId;
      // PreExecCheck gate — see §5
      if(String.equals(chkRes,"true")) {
        /* XSLT: ns:getMaxAllowOnlySubRequest {thaiId, categoryType(asciiCodeToText),
           companyCode(priority chain), channel(EOC/dealer logic), RefId=Account[1]/RefId}
           — see §7, §9, §10 */
        Event.Ext.sendEventImmediate(reqEvent);
        if(!isActResub) orderCurrentActivity.RequestCount++;
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
    } catch (Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
  }
}
```

## §19 Response Message Rule

### §19.1 Overview
Receives CVSS response, populates `GetMaxAllowOnlySubRes` via `XPath.execute` field extraction. Writes `MAX_ALLOW_ONLY_SUB` to Subscriber and Customer ExtendedInfo. Always returns `"true"`.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order — ExtendedInfo written |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CVSS_GET_MAX_ALLOW_ONLY_SUB` | CVSS response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[], ResponseCode updated |

### §19.3 Response Concept Fields

| Field | Source |
|-------|--------|
| Reference | XPath on `ns0:getMaxAllowOnlySubReturn/ns0:RefId` |
| creditClass | XPath on `ns0:getMaxAllowOnlySubReturn/ns0:creditClass` |
| maxAllow | XPath on `ns0:getMaxAllowOnlySubReturn/ns0:maxAllow` |
| statusCode | XPath on `ns0:getMaxAllowOnlySubReturn/ns0:statusCode` |
| statusMessage | XPath on `ns0:getMaxAllowOnlySubReturn/ns0:statusMessage` |
| ResponseCode | `eventResponse.ResponseCode` |
| ResponseMessage | `eventResponse.ResponseMsg` |

### §19.4 Response Completion Logic

`return "true"` — unconditional. No RequestCount/successResponseCount comparison.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
