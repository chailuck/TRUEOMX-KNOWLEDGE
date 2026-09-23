# Request_INTX_GET_PRODUCT_PREFERENCE_LIST

## §1 Overview & Purpose

**INTX_GET_PRODUCT_PREFERENCE_LIST** queries the INTX system for an existing product preference list associated with the customer's identification document (certificate). Used during ACTIVATION to discover existing product preferences linked to the customer's ID, enabling pre-population of subscriber data or validation of existing subscriptions.

The response handler can optionally extract the MSISDN list from the preference records and create new Subscriber concepts in the order hierarchy (when `GET_MSISDN_LIST=Y`).

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_PRODUCT_PREFERENCE_LIST` |
| Author | (not set) |
| Priority | 5 |
| forwardChain | true |
| Backend | INTX |
| Send pattern | `sendEventImmediate` — single request |
| Response concept | `Concepts.FM.Response.SearchPreVerifyRes` + `PreVerifiedInfoListBase` |
| Response rulefunction | `Response_INTX_GET_PRODUCT_PREFERENCE_LIST` |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — Identification read; Subscriber hierarchy optionally written |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | PreExecCheck, Parameters, RequestCount |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "INTX_GET_PRODUCT_PREFERENCE_LIST"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "INTX_GET_PRODUCT_PREFERENCE_LIST"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Check resubmit flag: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Evaluate PreExecCheck — if fails, call `SkipActivity("4")` and exit
3. Extract optional parameters: SUBSTATUS, BUSINESSLINE, COMPANYCODE, CUSTOMERSEGMENT
4. Build `INTX_GET_PRODUCT_PREFERENCE_LIST` request event (payload: `ns2:GetProductPreferenceListReq`)
5. `Event.Ext.sendEventImmediate(reqEvent)`
6. Increment `RequestCount` if not resubmit
7. Send REQ audit log
8. Set `orderCurrentActivity.Status = GetActivityStatusString("1", false)`
9. Call `SendDataToDB(orderRequest)`

---

## §7 Parameters

| Key | Required | Description |
|-----|----------|-------------|
| SUBSTATUS | [Optional] | Filter by subscriber status |
| BUSINESSLINE | [Optional] | Filter by business line |
| COMPANYCODE | [Optional] | Filter by company code |
| CUSTOMERSEGMENT | [Optional] | Filter by customer segment |
| GET_MSISDN_LIST | [Optional — response] | If `"Y"`: extract MSISDNs from response and create Subscriber concepts |

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Protocol |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.INTX_GET_PRODUCT_PREFERENCE_LIST` | JMS / sendEventImmediate |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.INTX_GET_PRODUCT_PREFERENCE_LIST` | JMS response |

### §8.3 Backend API

| System | Operation | Namespace |
|--------|-----------|-----------|
| INTX | GetProductPreferenceList (Mini) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetProductPreferenceListMini.xsd` |

### §8.4 BE Working Memory Read

| Field | Purpose |
|-------|---------|
| `OrderData.Customer.CustomerGeneralInfo.Identification` | Certificate number — primary search key |
| `OrderData.OMXTrackingId` | Correlation ID |
| `OrderData.OrderID` | Order reference |
| `OrderData.Customer.RefId` | Customer reference |

---

## §9 Request Payload Tree

```text
createEvent
└── event
    ├── JMSPriority                ← $orderRequest/OrderPriority         [Conditional]
    ├── JMSCorrelationID           ← $orderRequest/OrderData/OMXTrackingId [Conditional]
    ├── OrderID                    ← $orderRequest/OrderData/OrderID      [Conditional]
    ├── RefID                      ← $orderRequest/OrderData/Customer/RefId [Conditional]
    ├── OrderType                  ← $orderRequest/OrderData/OrderType    [Conditional]
    └── payload
        └── ns2:GetProductPreferenceListReq
            ├── ns2:correlatedId   ← $orderRequest/OrderData/OMXTrackingId [Conditional]
            ├── ns2:pageNumber     ← '1'                                  [Always — fixed]
            └── ns2:searchList
                ├── ns2:searchInfoArray  type=CERTIFICATE, value=Identification [Always]
                ├── ns2:searchInfoArray  type=SUBSTATUS   [Conditional: $subStatusParam!=""]
                ├── ns2:searchInfoArray  type=BUSINESSLINE [Conditional: $businessLineParam!=""]
                ├── ns2:searchInfoArray  type=COMPANYCODE  [Conditional: $companyCodeParam!=""]
                └── ns2:searchInfoArray  type=CUSTOMERSEGMENT [Conditional: $customerSegmentParam!=""]
```

---

## §11 Audit Logging

| Log | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE |
|-----|-----------|----------------|-------------|
| [REQ] Outbound | `concat(pid,"_REQ")` | `INTX_GET_PRODUCT_PREFERENCE_LIST` | `Request Sent for INTX_GET_PRODUCT_PREFERENCE_LIST` |
| [RES] Inbound | `concat(pid,"_RES")` | `INTX_GET_PRODUCT_PREFERENCE_LIST` | `Response received for INTX_GET_PRODUCT_PREFERENCE_LIST` |

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → ACTIVE | PreExecCheck passes, request sent | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| WAITING → SKIPPED | PreExecCheck fails | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| ACTIVE → COMPLETED | `RequestCount == successResponseCount` | `return "true"` from response rulefunction |

---

## §13 Exception Handling

| Condition | Action |
|-----------|--------|
| Any exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §15 Function Dependency Tree

```text
Request_INTX_GET_PRODUCT_PREFERENCE_LIST
├── GetActivityParameterValueFromKey(activity, "SUBSTATUS/BUSINESSLINE/COMPANYCODE/CUSTOMERSEGMENT")
├── XPath.execute(PreExecCheck, sXML, ns)
├── Event.createEvent("xslt://.../INTX_GET_PRODUCT_PREFERENCE_LIST", ...)
├── Event.Ext.sendEventImmediate(reqEvent)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
└── HandleActivityException(...)

Response_INTX_GET_PRODUCT_PREFERENCE_LIST
├── Instance.createInstance("xslt://.../SearchPreVerifyRes")
├── Instance.createInstance("xslt://.../PreVerifiedInfoListBase")
├── XPath.evalAsInt(payload/totalSize)
├── [if GET_MSISDN_LIST=Y]
│   ├── collect existing MSISDNs from POU/ChildOU subscribers
│   ├── extract MSISDN from response productPreferenceList
│   ├── [if pOuLen==0] Instance.createInstance ParentOU
│   └── Instance.createInstance Subscriber per new MSISDN
├── sendEventImmediate(Logger — RES)
└── XPath.evalAsInt(count responses with ResponseCode "000") → fan-in
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Search INTX by customer certificate (Identification field) |
| R2 | Support optional filters: SUBSTATUS, BUSINESSLINE, COMPANYCODE, CUSTOMERSEGMENT |
| R3 | Always send pageNumber=1 |
| R4 | If GET_MSISDN_LIST=Y: extract MSISDNs and create Subscriber concepts |
| R5 | If ParentOU empty and MSISDNs found: create new ParentOU |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| pageNumber hardcoded to 1 — no pagination | [MEDIUM] | Add pagination or increase page size |
| GET_MSISDN_LIST dynamically modifies order hierarchy | [MEDIUM] | Document as intentional; ensure migration target supports this |
| Silent ParentOU creation when pOuLen==0 | [LOW] | Add explicit log when creating implicit ParentOU |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_PRODUCT_PREFERENCE_LIST {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when { /* ActivityID == "INTX_GET_PRODUCT_PREFERENCE_LIST", Status == "WAITING" */ }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      // PreExecCheck gate
      // Extract params: SUBSTATUS, BUSINESSLINE, COMPANYCODE, CUSTOMERSEGMENT
      // Build event via XSLT: ns2:GetProductPreferenceListReq [see §9]
      Event.Ext.sendEventImmediate(reqEvent);
      if(!isActResub) orderCurrentActivity.RequestCount++;
      // sendEventImmediate(Logger REQ)
      orderCurrentActivity.Status = GetActivityStatusString("1", false);
      SendDataToDB(orderRequest);
    } catch (Exception ae) { HandleActivityException(...); }
  }
}
```

## §19 Response Message Rule

### §19.1 Overview
Receives INTX response, creates `SearchPreVerifyRes` concept with status fields, extracts total count from payload, optionally builds subscriber hierarchy from MSISDN list.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order — subscriber hierarchy may be written |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.INTX_GET_PRODUCT_PREFERENCE_LIST` | INTX response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[] appended |

### §19.3 Response Concept Tree

```text
createObject (SearchPreVerifyRes)
└── object
    ├── @extId        ← OMXUtils:generateTrackingID()     [Always]
    ├── ResponseCode  ← $eventResponse/ResponseCode       [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg      [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId   ← $eventResponse/RefID              [Conditional]

createObject (PreVerifiedInfoListBase)
└── object
    ├── @extId     ← OMXUtils:generateTrackingID()        [Always]
    └── rowCount   ← XPath on payload/totalSize            [computed]
```

### §19.4 Response Completion Logic

- Success XPath: `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])`
- Fan-in: `currActivity.RequestCount == successResponseCount` → `return "true"`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
