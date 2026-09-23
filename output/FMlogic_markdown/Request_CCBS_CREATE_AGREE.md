# Request_CCBS_CREATE_AGREE

## §1 Overview & Purpose

**CCBS_CREATE_AGREE** creates agreements on both ParentOU and ChildOU hierarchies in CCBS. Covers two iteration paths: POU loop (if POU.Agreement != null) and ChildOU loop (if ChildOU.Agreement != null). CCBS returns a new `AgreementNo` written back to `Agreement.AgreementId`.

> **Bug — ChildOU audit log:** AUDIT_TRACE = `"Request Sent for CES_CREATE_AGREE"` (typo: "CES" instead of "CCBS"). POU audit log is correct.

> **reqSuccess correlation mismatch:** For POU, reqSuccess checks `Response[ReferenceId == pOURefId]` but the event sends `RefID = Agreement.RefId`. If POU.RefId ≠ Agreement.RefId, the resubmit skip logic may fail.

> **agreementType source:** POU path: AGREEMENT_TYPE ExtendedInfo if present, else Agreement.AgreementType. ChildOU path: always Agreement.AgreementType (no ExtendedInfo check).

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CREATE_AGREE` |
| Author | awalia-t420 |
| Priority | 5 |
| Backend | CCBS |
| Event type | `Events.OMConsumers.OMXFM.Request.CCBS_CREATE_AGREE` |
| Response event | `Events.OMConsumers.OMXFM.Response.CCBS_CREATE_AGREE` |
| Send pattern | `Event.assertEvent` + `IntraActivitySequencing` per Agreement (POU+ChildOU) |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Response concept | `Concepts.FM.Response.CCBSCreateAgreementRes` |

---

## §10 XSLT Field Mapping

```text
createEvent → event (POU path)
├── RefID    ← ParentOU[$var]/Agreement/RefId                          [Conditional]
└── payload → ns2:CreateAgreementRequest → ns1:UpdateAgreementOnUnitRequest
    ├── ns1:customerIdInfo → customerNo  ← Customer.CustomerId         [Always]
    ├── ns1:unitIdInfo → chNodeId        ← ParentOU[$var]/OUId         [Always]
    ├── ns1:agreementTypeInfo → agreementType
    │   ← AGREEMENT_TYPE ExtendedInfo if exists, else Agreement.AgreementType  [Always]
    ├── ns1:agreementGeneralInfo
    │   ├── dealerCode          ← Customer.DealerCode                  [Conditional]
    │   └── agreementDescription ← AgreementGeneralInfo.agreementDescription [Conditional]
    └── ns1:activityInfo
        ├── activityReason   ← AgreementActivityInfo.ActivityReason or "CREQ"  [Always]
        ├── userText         ← AgreementActivityInfo.UserText          [Always (empty if missing)]
        └── l3ActivityDate   ← EffectiveDate                          [Conditional: non-empty]

createEvent → event (ChildOU path)
├── RefID    ← ChildOU/Agreement/RefId                                 [Conditional]
└── payload → (same structure but unitIdInfo.chNodeId = ChildOU.OUId; agreementType = AgreementType only)
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_CREATE_AGREE
├── [if resubmit] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── for each POU[i] where Agreement != null:
│   ├── [skip if Response[ReferenceId==pOURefId AND CompletionStatus==2] exists]
│   ├── GetXMLForAgreement(orderRequest, Agreement.RefId)
│   ├── XPath.execute(PreExecCheck, sXML)
│   ├── Event.createEvent(CCBS_CREATE_AGREE, POU XSLT)
│   ├── Event.assertEvent(reqEvent); ActionRequestEvent(reqEvent, activity)
│   └── sendEventImmediate(Logger REQ — "Request Sent for CCBS_CREATE_AGREE")
│   └── for each ChildOU[x] where Agreement != null:
│       ├── [skip if Response[ReferenceId==ChildOU.RefId AND CompletionStatus==2] exists]
│       ├── GetXMLForAgreementInChildOU(orderRequest, Agreement.RefId, POU.RefId)
│       ├── XPath.execute(PreExecCheck, sXML)
│       ├── Event.createEvent(CCBS_CREATE_AGREE, ChildOU XSLT)
│       ├── Event.assertEvent(reqEvent); ActionRequestEvent(reqEvent, activity)
│       └── sendEventImmediate(Logger REQ — "Request Sent for CES_CREATE_AGREE" [typo])
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
└── SendDataToDB(orderRequest)

Response_CCBS_CREATE_AGREE
├── for each POU[i]: if Agreement.RefId == eventResponse.RefID
│   → Agreement.AgreementId ← payload/.../NewAgreementResultInfo/AgreementNo
│   → Agreement.ResponseCode, ResponseMsg ← eventResponse
│   for each ChildOU[j]: same match+write
├── createInstance(CCBSCreateAgreementRes)
├── sendEventImmediate(Logger RES — OPERATION_NAME="CCBS_CREATE_AGREE")
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → true/false
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| reqSuccess uses pOURefId but event sends Agreement.RefId — resubmit skip may fail | [MEDIUM] | Fix: use Agreement.RefId for reqSuccess check |
| Audit log typo "CES_CREATE_AGREE" in ChildOU path | [LOW] | Fix: standardize to "CCBS_CREATE_AGREE" |
| AGREEMENT_TYPE ExtInfo check only in POU path | [LOW] | Document intentional difference; verify ChildOU Agreement type requirements |

---

## §19 Response Message Rule

Matches POU and ChildOU agreements by `Agreement.RefId == eventResponse.RefID`. Writes `AgreementId = NewAgreementResultInfo/AgreementNo`. Old fan-in logic (count empty ResponseCodes) is commented out; active logic uses `IntraActivitySequencing.ActionResponseEvent`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
