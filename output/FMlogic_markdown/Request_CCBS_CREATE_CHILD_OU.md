# Request_CCBS_CREATE_CHILD_OU

## §1 Overview & Purpose

**CCBS_CREATE_CHILD_OU** creates Child Organisational Units under existing ParentOUs in CCBS. The key difference from CCBS_CREATE_PARENT_OU is the addition of `ns:chArcInfo/ns:parentId` (POU.OUId) which establishes the parent-child relationship in the CCBS hierarchy.

> Loops ParentOU → ChildOU (two nested loops). Uses the same event type `CCBS_CREATE_OU` as CCBS_CREATE_PARENT_OU. The response handler matches by ChildOU.RefId and writes back `ChildOU.OUId`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CREATE_CHILD_OU` |
| Author | sakarin-pc |
| Priority | 5 |
| Event type | `Events.OMConsumers.OMXFM.Request.CCBS_CREATE_OU` (shared with PARENT_OU) |
| Response event | `Events.OMConsumers.OMXFM.Response.CCBS_CREATE_OU` |
| Send pattern | `Event.assertEvent` + `IntraActivitySequencing` per ChildOU |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Key difference vs PARENT_OU | Adds `ns:chArcInfo/ns:parentId = POU.OUId` |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── RefID        ← ParentOU[$var]/ChildOU[$iCOU]/RefId   [Conditional]
└── payload → ns:CreateUnitAndGetIdsRequest
    ├── ns:unitInfo
    │   ├── ns:name             ← ChildOU/OUName          [Conditional]
    │   └── ns:description      ← ChildOU/OUDescription   [Conditional]
    ├── ns:chArcInfo
    │   └── ns:parentId         ← $OUId (POU.OUId)        [Always — CHILD_OU only]
    ├── ns:customerIdInfo → ns:customerNo ← Customer.CustomerId  [Always]
    └── ns:activityInfo
        ├── ns:activityReason   ← ChildOU ActivityReason or "CREQ"  [Always]
        ├── ns:userText         ← ChildOU OUActivityInfo/UserText   [Conditional]
        └── ns:l3ActivityDate   ← EffectiveDate                     [Conditional: non-empty]
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_CREATE_CHILD_OU
├── [if resubmit] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── for each ParentOU[i]:
│   ├── OUId = ParentOU[i].OUId (passed to XSLT for chArcInfo.parentId)
│   └── for each ChildOU[j]:
│       ├── [skip if Response[ReferenceId==ChildOU.RefId AND CompletionStatus==2] exists]
│       ├── GetXMLForChildOU(orderRequest, ChildOU.RefId, POU.RefId)
│       ├── XPath.execute(PreExecCheck, sXML)
│       ├── Event.createEvent(CCBS_CREATE_OU, XSLT with chArcInfo.parentId=$OUId)
│       ├── Event.assertEvent(reqEvent); IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│       └── sendEventImmediate(Logger REQ — OPERATION_NAME="CCBS_CREATE_CHILD_OU")
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
└── SendDataToDB(orderRequest)

Response_CCBS_CREATE_CHILD_OU (identical logic to Response_CCBS_CREATE_PARENT_OU)
├── for each POU[i]: if POU.RefId == eventResponse.RefID → POU.OUId ← ChNodeId
│   for each ChildOU[j]: if ChildOU.RefId == eventResponse.RefID → ChildOU.OUId ← ChNodeId
├── createInstance(CCBSCreateOURes)
├── sendEventImmediate(Logger RES — OPERATION_NAME="CCBS_CREATE_CHILD_OU")
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → true/false
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `chArcInfo.parentId = POU.OUId` — requires CCBS_CREATE_PARENT_OU completed first | [MEDIUM] | Enforce activity ordering; POU.OUId must be populated before ChildOU creation |
| Shared event type CCBS_CREATE_OU — response serves both PARENT and CHILD | [LOW] | Migration must route responses to correct handler by ActivityID |

---

## §19 Response Message Rule

Same logic as `Response_CCBS_CREATE_PARENT_OU`: loops all POUs+ChildOUs, matches by RefID, writes `OUId = UnitIdsInfo/ChNodeId/ChNodeId`. Fan-in: `IntraActivitySequencing.ActionResponseEvent`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
