# Request_NAS_ACTIVATE_NEW_SUBS

## §1 Overview & Purpose

**NAS_ACTIVATE_NEW_SUBS** activates each subscriber's MSISDN in the NAS (Number Assignment System). It is the simplest FM in the ACTIVATION flow — the payload contains only two fields: `correlatedId` (OMXTrackingId) and `msisdn` (Subscriber.MSISDN).

> **Dual iteration paths:** The rule loops *both* ChildOU subscribers (`POU[i].ChildOU[k].Subscriber[j]`) and POU-direct subscribers (`POU[i].Subscriber[j]`), sending one event per subscriber per path. Total request count = ChildOU subs + POU-direct subs.

> **Response write-back:** Extracts `relaxStatus` from `NasActivateNewSubResponse/data/relaxStatus` and appends it as `RELAX_STATUS` ExtendedInfo on the matching subscriber.

> **PreExecCheck per subscriber:** If `nextAct.PreExecCheck` is non-empty, XML is built via `GetXMLForSubscriberInChildOU` or `GetXMLForSubscriber` and the XPath is evaluated before sending. Subscribers that fail the check are skipped.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_NAS_ACTIVATE_NEW_SUBS` |
| Author | Chayatorn P. |
| Priority | 5 |
| forwardChain | true |
| Backend | NAS |
| Event type (request) | `Events.OMConsumers.OMXFM.Request.NAS_ACTIVATE_NEW_SUBS` |
| Event type (response) | `Events.OMConsumers.OMXFM.Response.NAS_ACTIVATE_NEW_SUBS` |
| Send pattern | `Event.assertEvent` + `IntraActivitySequencing.ActionRequestEvent` per subscriber |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Iteration target | `ChildOU.Subscriber[]` + `POU.Subscriber[]` (two separate loops) |
| Response concept | `Concepts.FM.Response.NAS_ActivateSubscriberRes` |
| Payload operation | `ns:NasActivateNewSubRequest` |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| Dual subscriber loop | Pass 1: ChildOU[k].Subscriber[j]; Pass 2: POU[i].Subscriber[j] directly. Both use identical skip logic and event creation. |
| PreExecCheck per subscriber | ChildOU path: `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)`. POU path: `GetXMLForSubscriber(orderRequest, refId)`. |
| reqSuccess skip | Checks `Response[ReferenceId==refId AND CompletionStatus==2]` before sending. |
| Resubmit purge | `PurgePendingRequestsBeforeResubmit` called if `RequestCount>0 AND IsOrderResubmitted`. |
| Minimal payload | Only: `correlatedId` ← OMXTrackingId; `msisdn` ← Subscriber.MSISDN. |
| Commented-out direct send | POU-direct path has `//Event.Ext.sendEventImmediate(reqEvent)` commented out — replaced by IntraActivitySequencing. |

---

## §10 XSLT Field Mapping

Two variants (ChildOU with indices i/k/j; POU-direct with indices i/j). NAS payload is identical between them.

```text
createEvent → event
├── JMSPriority              ← $orderRequest/OrderPriority                    [Conditional]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId          [Conditional]
├── OrderID                  ← $orderRequest/OrderData/OrderID                [Conditional]
├── RefID                    ← Subscriber[$j+1]/RefId                         [Conditional]
├── OrderType                ← $orderRequest/OrderData/OrderType              [Conditional]
└── payload
    └── ns:NasActivateNewSubRequest
        ├── ns:correlatedId  ← $orderRequest/OrderData/OMXTrackingId          [Always]
        └── ns:msisdn        ← Subscriber[$j+1]/MSISDN                        [Always]
            (ChildOU: ParentOU[$i+1]/ChildOU[$k+1]/Subscriber[$j+1]/MSISDN)
            (POU-direct: ParentOU[$i+1]/Subscriber[$j+1]/MSISDN)
```

---

## §15 Function Dependency Tree

```text
Request_NAS_ACTIVATE_NEW_SUBS
├── [if resubmit] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── Instance.getByExtIdByUri(NextActivityName, Activity)
├── for each POU[i]:
│   ├── [ChildOU path] for each ChildOU[k].Subscriber[j]:
│   │   ├── [skip if Response[ReferenceId==refId AND CompletionStatus==2] exists]
│   │   ├── if PreExecCheck.length > 0:
│   │   │   └── GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)
│   │   │       XPath.execute(chkXPath, sXML)
│   │   └── if chkRes == "true":
│   │       ├── Event.createEvent(NAS_ACTIVATE_NEW_SUBS, ChildOU XSLT)
│   │       ├── Event.assertEvent(reqEvent)
│   │       ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│   │       └── sendEventImmediate(Logger REQ)
│   └── [POU-direct path] for each POU[i].Subscriber[j]:
│       ├── [skip if Response[ReferenceId==refId AND CompletionStatus==2] exists]
│       ├── if PreExecCheck.length > 0:
│       │   └── GetXMLForSubscriber(orderRequest, refId)
│       └── if chkRes == "true":
│           ├── Event.createEvent(NAS_ACTIVATE_NEW_SUBS, POU XSLT)
│           ├── Event.assertEvent(reqEvent)
│           ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│           └── sendEventImmediate(Logger REQ)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
└── SendDataToDB(orderRequest)

Response_NAS_ACTIVATE_NEW_SUBS
├── Instance.createInstance(NAS_ActivateSubscriberRes: ResponseCode, ResponseMsg, CompletionStatus, ReferenceId)
│   → currActivity.Response[n] = activityRes
├── XPath.evalAsString(relaxStatus from NasActivateNewSubResponse/data/relaxStatus)
├── for each POU[i]:
│   ├── [ChildOU path]: if subscriber.RefId == eventResponse.RefID:
│   │   → subscriber.ExtendedInfo[] += SubscriberExtendedInfo(Name="RELAX_STATUS", Value=relaxStatus)
│   └── [POU-direct]: if subscriber.RefId == eventResponse.RefID:
│       → subscriber.ExtendedInfo[] += SubscriberExtendedInfo(Name="RELAX_STATUS", Value=relaxStatus)
├── sendEventImmediate(Logger RES — "Response received for NAS_ACTIVATE_NEW_SUBS")
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
    [OLD fan-in commented out: count("000" responses) == RequestCount]
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Commented-out direct send in POU path | [LOW] | Remove dead code in migration |
| Dual loops generate many parallel NAS requests for large subscriber orders | [MEDIUM] | Test NAS capacity; implement rate-limiting if needed |
| `relaxStatus` written even on error responses (value may be empty) | [LOW] | Guard RELAX_STATUS write with CompletionStatus==2 in migration |
| PreExecCheck XML context differs between ChildOU and POU paths | [LOW] | Verify PreExecCheck XPath works with both context helpers |
| Minimal NAS payload — no AccountID or AgreementID correlation | [LOW] | Enrich payload if NAS reconciliation needs richer context |

---

## §19 Response Message Rule

Matches by `subscriber.RefId == eventResponse.RefID` across both ChildOU and POU-direct loops. Writes `RELAX_STATUS` to the matching subscriber.

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | NAS_ActivateSubscriberRes (4 fields) | Always |
| `Subscriber.ExtendedInfo[]` Name="RELAX_STATUS" | `NasActivateNewSubResponse/data/relaxStatus` | subscriber.RefId == eventResponse.RefID |

Fan-in: `IntraActivitySequencing.ActionResponseEvent(currActivity)` — returns "true" when all outstanding subscriber requests answered. Old fan-in (count "000" responses == RequestCount) is commented out.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
