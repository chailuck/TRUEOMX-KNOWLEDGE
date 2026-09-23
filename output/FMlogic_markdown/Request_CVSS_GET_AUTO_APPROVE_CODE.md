# Request_CVSS_GET_AUTO_APPROVE_CODE

## §1 Overview & Purpose

**CVSS_GET_AUTO_APPROVE_CODE** obtains a CVSS-generated approval code for subscriber activation, based on account category, company code, and subscriber count metrics. Sends one request per ParentOU via `IntraActivitySequencing` (sequential fan-out). The approval code is stored as `APPROVE_CODE` in each POU's `ExtendedInfo` for use by downstream validation activities.

> **Subscriber count logic:** numberOfExisting / numberOfRequest are computed differently per OrderType — SharePlan (11001/11002) vs. standard SOURCE_OR_TARGET-based logic vs. simple subscriber count.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CVSS_GET_AUTO_APPROVE_CODE` |
| Author | TIT_P10-SARUN3 |
| Priority | 5 |
| forwardChain | true |
| Backend | CVSS |
| Send pattern | Fan-out — `Event.assertEvent` + `IntraActivitySequencing` per POU |
| Activity param | `requestType` — override request type (default "M") |
| RefID | `OMXUtils:generateTrackingID()` (generated, NOT Customer.RefId) |
| Fan-in | Standard: `RequestCount == successResponseCount` (ResponseCode ends "000") |
| Response concept | `Concepts.FM.Response.GetAutoApproveCodeRes` |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — CustomerTypeInfo, AccountInfo, POU.ExtendedInfo written |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | ActivityID, RequestCount, Status, Response[] |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CVSS_GET_AUTO_APPROVE_CODE"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CVSS_GET_AUTO_APPROVE_CODE"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Check resubmit; `PurgePendingRequestsBeforeResubmit` if resubmit
2. For each ParentOU[i]: evaluate PreExecCheck via `GetXMLForOU(orderRequest, refId)`
3. Compute `accountCat` from `CustomerTypeInfo.Type` (0 if null)
4. Compute `numberOfExisting` / `numberOfRequest` (see §7)
5. Get `thaiId` from `CustomerGeneralInfo.Identification`
6. Get `companyCode`: Account where AgreementRefId==refId → fallback Account where RefId==refId
7. Get `reqType`: activity param "requestType" or default "M"
8. `Event.assertEvent(reqEvent)` + `IntraActivitySequencing.ActionRequestEvent`
9. Send REQ audit log
10. After all POUs: `IntraActivitySequencing.SendFirstRequestEvent` + set ACTIVE + `SendDataToDB`

---

## §7 Data Extraction: numberOfExisting / numberOfRequest

| OrderType | numberOfExisting | numberOfRequest |
|-----------|-----------------|----------------|
| `11001` (SharePlan Add) | 1 | `count(Subscriber/ExtendedInfo[Name='SHAREPLAN_MAIN_NUMBER'])` |
| `11002` (SharePlan Break) | 1 | `count(ParentOU/ExtendedInfo[Name='NEW_PARENT_OU'])` |
| Other — SOURCE_OR_TARGET exists | `count(Subscriber/ExtendedInfo[Name='SOURCE_OR_TARGET', Value='SOURCE'])` | `count(Subscriber/ExtendedInfo[Name='SOURCE_OR_TARGET', Value='TARGET'])` |
| Other — no SOURCE_OR_TARGET | `Subscriber@length` | 1 |

### companyCode Priority

| Priority | Source |
|----------|--------|
| 1 | `Account[].AccountManagementInfo.CompanyCode` where `AgreementRefId == POU.RefId` |
| 2 | `Account[].AccountManagementInfo.CompanyCode` where `Account.RefId == POU.RefId` |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority          ← $orderRequest/OrderPriority                    [Conditional]
├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId          [Conditional]
├── OrderID              ← $orderRequest/OrderData/OrderID                [Conditional]
├── RefID                ← OMXUtils:generateTrackingID()                  [Always — generated, not customer RefId]
├── OrderType            ← $orderRequest/OrderData/OrderType              [Conditional]
└── payload → ns:getAutoApproveCodeRequest → ns:getAutoApproveCode
    ├── ns:accountCat       ← OMXUtils:asciiCodeToText($accountCat)       [Always]
    ├── ns:requestType      ← $reqType (param or 'M')                     [Always]
    ├── ns:companyCode      ← $companyCode (2-way priority — see §7)      [Always]
    ├── ns:numberOfExisting ← $numberOfExisting (OrderType-conditional)   [Always]
    ├── ns:numberOfRequest  ← $numberOfRequest (OrderType-conditional)    [Always]
    └── ns:thaiId           ← $thaiId (CustomerGeneralInfo.Identification)[Always]
```

---

## §15 Function Dependency Tree

```text
Request_CVSS_GET_AUTO_APPROVE_CODE
├── [if resubmit] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── for each ParentOU[i]
│   ├── GetXMLForOU(orderRequest, refId)
│   ├── XPath.execute(PreExecCheck, sXML, ns)
│   ├── XPath.evalAsInt(numberOfExisting, numberOfRequest) — OrderType-conditional
│   ├── GetActivityParamValueFromKey(activity, "requestType")
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│   └── sendEventImmediate(Logger REQ)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
└── HandleActivityException(...)

Response_CVSS_GET_AUTO_APPROVE_CODE
├── OMXUtils.generateTrackingID()
├── Instance.createInstance("xslt://.../GetAutoApproveCodeRes")
│   → ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, approveCode, statusCode, statusMessage
├── currActivity.Response[n] = getAutoApproveCodeRes
├── [if ResponseCode ends "000"]
│   └── for each POU
│       Instance.createInstance(OUExtendedInfo{Name=APPROVE_CODE, Value=approveCode})
│       pou.ExtendedInfo[n] = ouExtendedInfo
├── XPath.evalAsInt(count(Response[ResponseCode ends "000"])) → successResponseCount
└── if(RequestCount == successResponseCount) return "true" else "false"
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Send CVSS request per POU with order-type-specific numberOfExisting/numberOfRequest |
| R2 | RefID must be generated UUID per request (not Customer.RefId) |
| R3 | companyCode: AgreementRefId match first, fallback to RefId match |
| R4 | On success: write APPROVE_CODE to every POU's ExtendedInfo |
| R5 | Fan-in: standard "000" suffix check — all calls must succeed |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| RefID uses generated UUID — CVSS correlation is by generated ID | [MEDIUM] | Document that CVSS uses its own RefId for response; no subscriber lookup by RefId |
| numberOfExisting/Request computed differently per OrderType | [MEDIUM] | Unit test all 4 OrderType branches separately |
| companyCode lookup uses AgreementRefId first | [LOW] | Document that AgreementRefId matches POU.RefId in the account model |

---

## §19 Response Message Rule

### §19.1 Overview

Receives CVSS response, creates `GetAutoApproveCodeRes` concept per response. If ResponseCode ends "000", appends `APPROVE_CODE` ExtendedInfo to each POU. Fan-in uses standard success-count check.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order — POU.ExtendedInfo written |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CVSS_GET_AUTO_APPROVE_CODE` | CVSS response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[] appended, RequestCount checked |

### §19.3 Response Concept Tree

```text
createObject (GetAutoApproveCodeRes)
├── @extId            ← OMXUtils:generateTrackingID()                                    [Always]
├── ResponseCode      ← $eventResponse/ResponseCode                                      [Conditional]
├── ResponseMessage   ← $eventResponse/ResponseMsg                                       [Conditional]
├── CompletionStatus  ← $eventResponse/CompletionStatus                                  [Conditional]
├── ReferenceId       ← $eventResponse/RefID                                             [Conditional]
├── approveCode       ← payload/.../ns:approveCode                                       [Conditional]
├── statusCode        ← payload/.../ns:statusCode                                        [Conditional]
└── statusMessage     ← payload/.../ns:statusMessage                                     [Conditional]
```

**On ResponseCode success ("000"):** Creates `OUExtendedInfo{Name=APPROVE_CODE, Value=approveCode}` and appends to every POU's `ExtendedInfo[]`.

### §19.4 Response Completion Logic

Fan-in: `count(Response[tib:right(tib:trim(ResponseCode),3)="000"]) == RequestCount`

Returns `"true"` only when **all** parallel CVSS calls returned success codes.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
