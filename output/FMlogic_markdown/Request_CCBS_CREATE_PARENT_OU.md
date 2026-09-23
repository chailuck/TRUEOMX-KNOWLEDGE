# Request_CCBS_CREATE_PARENT_OU

## §1 Overview & Purpose

**CCBS_CREATE_PARENT_OU** creates a new Organisational Unit (OU) at the ParentOU level in CCBS during ACTIVATION. CCBS assigns a new OU identifier (`ChNodeId`) which is written back to `ParentOU.OUId`. This OUId is required by subsequent activities (CreateChildOU, CreateAgreement, CreateAccount, etc.).

> Iterates over all POUs; skips POUs that already have a successful response (CompletionStatus==2 check for resubmit safety). Fan-in via `IntraActivitySequencing.ActionResponseEvent`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CREATE_PARENT_OU` |
| Author | sakarin rachapunya |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS |
| Event type | `Events.OMConsumers.OMXFM.Request.CCBS_CREATE_OU` |
| Response event | `Events.OMConsumers.OMXFM.Response.CCBS_CREATE_OU` |
| Send pattern | `Event.assertEvent` + `IntraActivitySequencing` per POU |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Response concept | `Concepts.FM.Response.CCBSCreateOURes` |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority, JMSCorrelationID, OrderID   ← standard order fields   [Conditional]
├── RefID                                    ← ParentOU[$var]/RefId     [Conditional]
├── UserName / PassWord                      ← credential-gated         [IsEnableUserPass='true']
├── OrderType, CES                           ← standard order fields    [Conditional]
└── payload → ns:CreateUnitAndGetIdsRequest
    ├── ns:unitInfo
    │   ├── ns:name            ← ParentOU[$var]/OUName                  [Conditional]
    │   └── ns:description     ← ParentOU[$var]/OUDescription           [Conditional]
    ├── ns:customerIdInfo
    │   └── ns:customerNo      ← Customer.CustomerId                    [Always]
    └── ns:activityInfo
        ├── ns:activityReason  ← POU ActivityReason if present else "CREQ" [Always]
        ├── ns:userText        ← POU OUActivityInfo/UserText            [Conditional]
        └── ns:l3ActivityDate  ← EffectiveDate                         [Conditional: non-empty]
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_CREATE_PARENT_OU
├── [if resubmit] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── Instance.getByExtIdByUri("LogicalDate", ...) [read but unused in XSLT — dead code]
├── for each ParentOU[i]:
│   ├── [skip if Response[ReferenceId==POU.RefId AND CompletionStatus==2] exists]
│   ├── GetXMLForOU(orderRequest, POU.RefId)
│   ├── XPath.execute(PreExecCheck, sXML)
│   ├── Event.createEvent(CCBS_CREATE_OU, XSLT: unitInfo + customerIdInfo + activityInfo)
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│   └── sendEventImmediate(Logger REQ — OPERATION_NAME="CCBS_CREATE_PARENT_OU")
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
└── SendDataToDB(orderRequest)

Response_CCBS_CREATE_PARENT_OU
├── for each POU[i]: if POU.RefId == eventResponse.RefID
│   → POU.OUId ← payload/UnitIdsInfo/ChNodeId/ChNodeId
│   → POU.ResponseCode, POU.ResponseMsg ← eventResponse
│   for each ChildOU[j]: if ChildOU.RefId == eventResponse.RefID
│   → ChildOU.OUId ← payload/UnitIdsInfo/ChNodeId/ChNodeId
│   → ChildOU.ResponseCode, ChildOU.ResponseMsg ← eventResponse
├── Instance.createInstance(CCBSCreateOURes{extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId})
├── currActivity.Response[n] = activityRes
├── sendEventImmediate(Logger RES — OPERATION_NAME="CCBS_CREATE_PARENT_OU")
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → true/false
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Response handler loops ALL POUs+ChildOUs to match RefID — O(n²) per response | [MEDIUM] | In migration, index by RefId for O(1) lookup |
| LogicalDate concept read but never used in XSLT — dead code | [LOW] | Remove in migration |
| Resubmit check uses CompletionStatus==2 to skip completed POUs | [LOW] | Preserve CompletionStatus==2 check in idempotency logic |

---

## §19 Response Message Rule

### §19.1 Overview

Shared response event `CCBS_CREATE_OU` handles both PARENT_OU and CHILD_OU scenarios. Response handler searches all POUs and ChildOUs by RefID and writes back the CCBS-assigned `OUId`.

### §19.3 Response Writes

| Target | Source | Condition |
|--------|--------|-----------|
| `ParentOU[i].OUId` | `payload/UnitIdsInfo/ChNodeId/ChNodeId` | POU.RefId == eventResponse.RefID |
| `ChildOU[j].OUId` | `payload/UnitIdsInfo/ChNodeId/ChNodeId` | ChildOU.RefId == eventResponse.RefID |
| ResponseCode/Msg on matched OU | eventResponse | On match |

### §19.4 Fan-in

`IntraActivitySequencing.ActionResponseEvent(currActivity)` — returns true when all outstanding requests have been answered.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
