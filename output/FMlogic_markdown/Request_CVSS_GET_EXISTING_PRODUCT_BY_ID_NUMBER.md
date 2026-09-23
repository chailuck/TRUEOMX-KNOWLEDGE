# Request_CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER

## §1 Overview & Purpose

**CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER** queries CVSS for existing product subscriptions associated with a customer's national ID number. Used during ACTIVATION to detect how many existing subscriptions the customer already holds, enabling enforcement of subscriber limits.

The response handler extracts the product count and writes it as `TOTAL_SUBS` in `Customer.ExtendedInfo`.

> lastName mapping is type-conditional: Type≠73 (non-individual) → OrgName; Type=73 (individual) → LastName.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER` |
| Author | DESKTOP-995HR2V |
| Priority | 5 |
| forwardChain | true |
| Backend | CVSS |
| Send pattern | `sendEventImmediate` — single request |
| Response concept | `Concepts.FM.Response.CVSS_GetExistingProductRes` |
| Response rulefunction | `Response_CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER` |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — Identification, CustomerName, BirthDate, ExtendedInfo written |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | PreExecCheck, RequestCount, Status |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Set `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Retrieve `nextAct` PreExecCheck via `Instance.getByExtIdByUri`
3. Evaluate PreExecCheck XPath; if fails → `isSkipped=true`
4. Build `CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER` event via XSLT
5. `Event.Ext.sendEventImmediate(reqEvent)`
6. If not resubmit: `RequestCount++`
7. Send REQ audit log
8. Set `isSkipped = false`
9. If not skipped: `Status = GetActivityStatusString("1", false)` + `SendDataToDB`
10. If skipped: `SkipActivity(orderRequest, orderCurrentActivity, "4")`

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Protocol |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER` | JMS / sendEventImmediate |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER` | JMS response |

### §8.3 Backend API

| System | Operation | Namespace |
|--------|-----------|-----------|
| CVSS | getExistingProductByidNumber | `http://services.omx.truecorp.co.th/FMServices/GetExistingProductByidNumberRequest` |

### §8.4 BE Working Memory Read

| Field | Purpose |
|-------|---------|
| `Customer.CustomerGeneralInfo.Identification` | National ID — primary search key |
| `Customer.CustomerName.FirstName` | Customer first name |
| `Customer.CustomerName.OrgName` | Organisation name (Type≠73) |
| `Customer.CustomerName.LastName` | Individual last name (Type=73) |
| `Customer.CustomerTypeInfo.Type` | Drives lastName selection |
| `Customer.CustomerGeneralInfo.BirthDate` | DoB — mapped to yyyyMMdd in +07:00 TZ |
| `Customer.RefId` | RefID in JMS envelope |

### §8.4 BE Working Memory Written (response)

| Target | Field | Value |
|--------|-------|-------|
| `Customer.ExtendedInfo[]` | Name="TOTAL_SUBS" | productcount from response payload |

---

## §9 Request Payload Tree

```text
createEvent
└── event
    ├── JMSPriority             ← $orderRequest/OrderPriority              [Conditional]
    ├── JMSCorrelationID        ← $orderRequest/OrderData/OMXTrackingId    [Conditional]
    ├── OrderID                 ← $orderRequest/OrderData/OrderID           [Conditional]
    ├── RefID                   ← $orderRequest/OrderData/Customer/RefId    [Always]
    ├── OrderType               ← $orderRequest/OrderData/OrderType         [Conditional]
    └── payload
        └── ns1:GetExistingProductByidNumberRequest
            └── ns1:getExistingProductByidNumber
                ├── ns1:idNumber    ← Customer/CustomerGeneralInfo/Identification      [Always]
                ├── ns1:firstName   ← Customer/CustomerName/FirstName                  [Always]
                ├── ns1:lastName    ← if(Type!=73) OrgName; if(Type=73) LastName       [Conditional]
                ├── ns1:dob         ← format-dateTime("yyyyMMdd", BirthDate, +07:00)   [Conditional: BirthDate not blank]
                ├── ns1:productId   ← '1'                                              [Always — hardcoded]
                └── ns1:source      ← 'OMX'                                            [Always — hardcoded]
```

---

## §11 Audit Logging

| Log | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE |
|-----|-----------|----------------|-------------|
| [REQ] | `concat(pid,"_REQ")` | `CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER` | Request Sent for CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER |
| [RES] | `concat(pid,"_RES")` | `CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER` | Response received for CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER |

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → ACTIVE | PreExecCheck passes | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| WAITING → SKIPPED | PreExecCheck fails | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| ACTIVE → COMPLETED | `RequestCount == successResponseCount` (ResponseCode ends "000") | `return "true"` |

---

## §13 Exception Handling

| Condition | Action |
|-----------|--------|
| Any exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §15 Function Dependency Tree

```text
Request_CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER
├── Instance.getByExtIdByUri(NextActivityName, Activity)
├── XPath.execute(PreExecCheck, sXML, ns)
├── Event.createEvent("xslt://.../CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER", ...)
├── Event.Ext.sendEventImmediate(reqEvent)
├── sendEventImmediate(Logger REQ)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
└── HandleActivityException(...)

Response_CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER
├── OMXUtils.generateTrackingID()
├── Instance.createInstance("xslt://.../CVSS_GetExistingProductRes")
│   → ResponseCode, ResponseMessage, CompletionStatus, ReferenceId
│   → result_count, statusCode, statusMessage from payload
├── currActivity.Response[n] = activityRes
├── XPath.evalAsInt(payload count → productcount)
├── Instance.createInstance(CustomerExtendedInfo{Name="TOTAL_SUBS", Value=productcount})
├── orderRequest.Customer.ExtendedInfo[n] = custExtendedInfo
├── sendEventImmediate(Logger RES)
└── XPath.evalAsInt(count ResponseCode "000") → fan-in
    └── if RequestCount == successResponseCount → return "true"
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Search CVSS by customer national ID (Identification field) |
| R2 | lastName must be type-conditional: OrgName for Type≠73, LastName for Type=73 |
| R3 | BirthDate mapped to yyyyMMdd in +07:00 timezone; omit if blank |
| R4 | productId hardcoded to 1; source hardcoded to 'OMX' |
| R5 | Response handler writes TOTAL_SUBS to Customer.ExtendedInfo |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| productId hardcoded to 1 | [MEDIUM] | Parameterize from activity config |
| Type=73 check brittle if type codes change | [MEDIUM] | Centralise type-code lookup |
| Timezone hardcoded to +07:00 in dob mapping | [LOW] | Document for international expansion |

---

## §18 Full Source Code

```java
// @author DESKTOP-995HR2V
rule Rules.OMConsumers.OMXFM.Request.Request_CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when { /* ActivityID == "CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER", Status == "WAITING" */ }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      // Retrieve PreExecCheck, evaluate against serialised order
      String chkRes = "true"; boolean isSkipped = true;
      if(String.equals(chkRes,"true")) {
        /* XSLT: ns1:GetExistingProductByidNumberRequest {idNumber, firstName,
           lastName(type-cond), dob(optional yyyyMMdd +07:00), productId=1, source='OMX'}
           — see §9 & §10 */
        Events.OMConsumers.OMXFM.Request.CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER reqEvent = Event.createEvent("xslt://...");
        Event.Ext.sendEventImmediate(reqEvent);
        if(!isActResub) orderCurrentActivity.RequestCount++;
        // sendEventImmediate(Logger REQ)
        isSkipped = false;
      }
      if(!isSkipped) {
        orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
        RuleFunctions.Helpers.SendDataToDB(orderRequest);
      } else { RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4"); }
    } catch (Exception ae) { RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
  }
}
```

## §19 Response Message Rule

### §19.1 Overview
Receives CVSS response, creates `CVSS_GetExistingProductRes` concept. Extracts product count and writes `TOTAL_SUBS` to `Customer.ExtendedInfo`.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order — ExtendedInfo written |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CVSS_GET_EXISTING_PRODUCT_BY_ID_NUMBER` | CVSS response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[] appended |

### §19.3 Response Concept Tree

```text
createObject (CVSS_GetExistingProductRes)
└── object
    ├── @extId         ← OMXUtils:generateTrackingID()                                  [Always]
    ├── ResponseCode   ← $eventResponse/ResponseCode                                    [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg                                    [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus                              [Conditional]
    ├── ReferenceId    ← $eventResponse/RefID                                           [Conditional]
    ├── result_count   ← payload/ns1:getExistingProductByidNumberReturn/ns1:count       [Conditional]
    ├── statusCode     ← payload/ns1:getExistingProductByidNumberReturn/ns1:statusCode  [Conditional]
    └── statusMessage  ← payload/ns1:getExistingProductByidNumberReturn/ns1:statusMessage [Conditional]

createObject (CustomerExtendedInfo)
└── object
    ├── @extId  ← OMXUtils:generateTrackingID()
    ├── Name    ← "TOTAL_SUBS"
    └── Value   ← $productcount (from XPath.evalAsInt on payload/count)
```

### §19.4 Response Completion Logic

- Success XPath: `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])`
- Fan-in: `currActivity.RequestCount == successResponseCount` → `return "true"`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
