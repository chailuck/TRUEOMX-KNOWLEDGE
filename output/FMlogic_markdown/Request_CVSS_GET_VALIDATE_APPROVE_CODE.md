# Request_CVSS_GET_VALIDATE_APPROVE_CODE

## §1 Overview & Purpose

**CVSS_GET_VALIDATE_APPROVE_CODE** validates one or more approval codes from the order against CVSS. Used during ACTIVATION to verify that approve codes for max-allow, IR (international roaming), credit limit, and MNP scenarios are valid before proceeding with provisioning.

> **Two execution paths:**
> - **Path A (isApproveList=true):** SharePlan mode — one request per `maxAllowApproveCodeList` entry via `sendEventImmediate` fan-out
> - **Path B (isApproveList=false):** Standard mode — single request containing up to 4 `getValidateApproveCode` blocks (maxallow, maxallow_mnp, ir, ir_mnp, simbundle)
>
> **Response fan-in:** Unconditional `return "true"` — response handler iterates all `getValidateApproveCodeResponse` blocks.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CVSS_GET_VALIDATE_APPROVE_CODE` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | CVSS |
| Path A | `sendEventImmediate` fan-out per `maxAllowApproveCodeList[i]` |
| Path B | `sendEventImmediate` single request, multi-block payload |
| Fan-in | Unconditional `return "true"` |
| Response concept | `Concepts.FM.Response.GetValidateApproveCodeRes` |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — approve codes read from POU/Customer |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | ActivityID, RequestCount, Status, Response[] |

---

## §5 Execution Flow

1. Evaluate PreExecCheck — if fails → `SkipActivity`
2. Evaluate `isApproveList = count(maxAllowApproveCodeList) > 0`
3. **Path A (isApproveList=true):** Find subType from POU[0].Subscriber where SHAREPLAN_PARENT_TYPE exists → SubscriberType
4. **Path A:** For each `maxAllowApproveCodeList[i]`: send one request with approveCode, numberOfRequest, idNumber, companyCode=subType, requestType="maxallow", customerLevel="NON-TOP"
5. **Path B (isApproveList=false):** Send single request with payload containing multiple optional `getValidateApproveCode` blocks based on order data
6. `RequestCount++`; status ACTIVE; `SendDataToDB`

---

## §7 Path B Payload: Conditional Approve Code Blocks

> Path B sends a single request with up to 4 `getValidateApproveCode` blocks. Each block is emitted only if its condition is met.

| Block | Condition | requestType | approveCode source |
|-------|-----------|-------------|-------------------|
| Block 1 | `maxAllowApproveCode` or `APPROVE_CODE ExtendedInfo` present AND Channel≠MNP | `maxallow` | APPROVE_CODE ExtendedInfo or `maxAllowApproveCode` |
| Block 2 | Same codes present AND Channel=MNP | `maxallow_mnp` | Same as Block 1 |
| Block 3 | `irApproveCode` present AND Channel≠MNP | `ir` | `irApproveCode` |
| Block 4 | `irApproveCode` present AND Channel=MNP | `ir_mnp` | `irApproveCode` |
| Block 5 | `creditLimitApproveCode` present | `simbundle` | `creditLimitApproveCode` |

### Common Fields (Path B blocks 1-5)

| Field | Source |
|-------|--------|
| idNumber | `Customer.CustomerGeneralInfo.Identification` |
| companyCode | Account[1].CompanyCode if not blank; else POU or ChildOU SubscriberType |
| numberOfRequest | count(TARGET MSISDN) if TARGET exists; else count(all MSISDN) |
| customerLevel | `Customer.CustomerGeneralInfo.Grading` |
| customerType | `OMXUtils:asciiCodeToText(CustomerTypeInfo.Type)` |
| numberOfRequest (ir blocks) | POU[TARGET].NumberOfIR or POU[1].NumberOfIR |

---

## §15 Function Dependency Tree

```text
Request_CVSS_GET_VALIDATE_APPROVE_CODE
├── XPath.execute(PreExecCheck, serialize(orderRequest))
├── XPath.evalAsBoolean(count(maxAllowApproveCodeList) > 0) → isApproveList
├── Path A (isApproveList=true, SharePlan):
│   ├── for POU[0] Subscriber: XPath.evalAsBoolean(exists SHAREPLAN_PARENT_TYPE) → subType
│   └── for each maxAllowApproveCodeList[i]:
│       ├── Event.createEvent(CVSS_GET_VALIDATE_APPROVE_CODE, i, subType)
│       ├── Event.Ext.sendEventImmediate(reqEvent)
│       ├── RequestCount++
│       └── sendEventImmediate(Logger REQ)
└── Path B (isApproveList=false):
    ├── Event.createEvent(multi-block XSLT: up to 4 getValidateApproveCode blocks)
    ├── Event.Ext.sendEventImmediate(reqEvent)
    ├── RequestCount++
    └── sendEventImmediate(Logger REQ)

Response_CVSS_GET_VALIDATE_APPROVE_CODE
├── iResCnt = count(ns0:getValidateApproveCodeResponse in payload)
├── for i in 0..iResCnt-1:
│   ├── Instance.createInstance(GetValidateApproveCodeRes) [extId from RefId]
│   ├── XPath.execute → ReferenceId, counts, statusCode, statusMessage, approveCode
│   └── currActivity.Response[n] = getValidateApproveCodeRes
├── currActivity.ResponseCode = eventResponse.ResponseCode
├── sendEventImmediate(Logger RES)
└── return "true"  (unconditional)
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Two distinct request modes (shareplan vs standard) based on isApproveList |
| R2 | Path B: variable-length multi-block payload; each block type/condition independent |
| R3 | Response iterates all getValidateApproveCodeResponse elements by count |
| R4 | Unconditional return "true" — downstream rules must check individual block results |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Two completely different execution paths | [MEDIUM] | Test both paths; Path A and Path B have different request/response structures |
| Multi-block payload — CVSS receives one request with N validate blocks | [MEDIUM] | Migration target must support variable-length multi-block payload |
| Unconditional return "true" — no success count check | [MEDIUM] | Downstream rules must check individual block statusCode/approveCode in Response[] |

---

## §19 Response Message Rule

### §19.1 Overview

Receives CVSS response, iterates over `count(getValidateApproveCodeResponse)` blocks. For each block creates `GetValidateApproveCodeRes` concept with result codes. Unconditional return "true".

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CVSS_GET_VALIDATE_APPROVE_CODE` | CVSS response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[] appended |

### §19.3 Response Concept Tree

```text
for each getValidateApproveCodeResponse[i]:
createObject (GetValidateApproveCodeRes)
├── @extId            ← getValidateApproveCodeReturn/RefId                [Always]
├── ResponseCode      ← eventResponse.ResponseCode                        [Conditional]
├── ResponseMessage   ← eventResponse.ResponseMsg                         [Conditional]
├── ReferenceId       ← getValidateApproveCodeReturn/RefId                [Conditional]
├── counts            ← getValidateApproveCodeReturn/count                [Conditional]
├── statusCode        ← getValidateApproveCodeReturn/statusCode           [Conditional]
├── statusMessage     ← getValidateApproveCodeReturn/statusMessage        [Conditional]
└── approveCode       ← getValidateApproveCodeReturn/approveCode          [Conditional]
```

### §19.4 Response Completion Logic

`return "true"` — unconditional. No RequestCount comparison.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
