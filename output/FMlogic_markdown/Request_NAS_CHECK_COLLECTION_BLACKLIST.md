# Request_NAS_CHECK_COLLECTION_BLACKLIST

## §1 Overview & Purpose

Checks the NAS collection blacklist for the customer's ID number. Sends `NasCheckCollectionBlacklistRequest` with `idNumber` from `CustomerGeneralInfo/Identification` and hardcoded `companyCode="AL"`. The response `relaxStatus` is written back to each matched subscriber's `ExtendedInfo` as key `RELAX_STATUS`.

Iteration order: **ChildOU subscribers first**, then ParentOU (reversed from typical). Uses **IntraActivitySequencing** pattern. Old RequestCount fan-in code is commented out.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_NAS_CHECK_COLLECTION_BLACKLIST` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | NAS_CHECK_COLLECTION_BLACKLIST |
| Backend | NAS — CheckCollectionBlacklist |
| Pattern | IntraActivitySequencing |
| Iteration Order | ChildOU subscribers → ParentOU subscribers |
| Response Concept | `Concepts.FM.Response.NAS_ActivateSubscriberRes` (reused) |
| Response Event | `Events.OMConsumers.OMXFM.Response.NAS_CHECK_COLLECTION_BLACKLIST` |

---

## §4 Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "NAS_CHECK_COLLECTION_BLACKLIST"
orderRequest.ProcessFlow.NextActivityID == "NAS_CHECK_COLLECTION_BLACKLIST"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 Execution Flow

1. If resubmit: `PurgePendingRequestsBeforeResubmit`
2. **ChildOU first**: iterate `ParentOU[i].ChildOU[k].Subscriber[j]`
3. Evaluate PreExecCheck via `GetXMLForSubscriberInChildOU`
4. For passing: fire request via IntraActivitySequencing
5. Fire audit logger
6. **Then ParentOU**: iterate `ParentOU[i].Subscriber[j]`
7. Evaluate PreExecCheck via `GetXMLForSubscriber`
8. For passing: fire request via IntraActivitySequencing
9. Fire audit logger
10. If not skipped: `SendFirstRequestEvent` + set IN_PROGRESS; else: `SkipActivity("4")`

---

## §9 Payload Build

```text
createEvent
└── event
    ├── JMSPriority       ← $orderRequest/OrderPriority              [Always]
    ├── JMSCorrelationID  ← $orderRequest/OrderData/OMXTrackingId    [Always]
    ├── OrderID           ← $orderRequest/OrderData/OrderID          [Always]
    ├── RefID             ← Subscriber[index]/RefId                  [Always]
    ├── OrderType         ← $orderRequest/OrderData/OrderType        [Always]
    └── payload
        └── ns:NasCheckCollectionBlacklistRequest
            ├── ns:correlatedId  ← $orderRequest/OrderData/OMXTrackingId  [Always]
            ├── ns:idNumber      ← CustomerGeneralInfo/Identification      [Always]
            └── ns:companyCode   ← "AL"                                    [Hardcoded]
```

---

## §15 Function Dependency Tree

```text
Request_NAS_CHECK_COLLECTION_BLACKLIST
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)
├── GetXMLForSubscriber(orderRequest, refId)
├── XPath.execute("/(preExecCheck)", sXML, ...)
├── Event.assertEvent(reqEvent)
├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
├── Event.Ext.sendEventImmediate(Logger)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(req, activity, "4")
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 Migration Notes

| # | Requirement / Risk | Severity |
|---|-------------------|---------|
| R1 | `idNumber` from `CustomerGeneralInfo/Identification` (account-level, not subscriber) | [HIGH] |
| R2 | `companyCode` hardcoded `"AL"` — not configurable | [MEDIUM] |
| R3 | Response writes `RELAX_STATUS` ExtendedInfo to each subscriber matched by RefId | [MEDIUM] |
| R4 | Iteration order: ChildOU before ParentOU (unusual — document and preserve) | [MEDIUM] |
| R5 | Old RequestCount fan-in commented out; uses `IntraActivitySequencing.ActionResponseEvent` only | [LOW] |

---

## §19 Response Message Rule

### §19.1 Overview

Creates `NAS_ActivateSubscriberRes` (concept reused). Reads `relaxStatus` from `NasCheckCollectionBlacklistResponse/data/relaxStatus`. Writes `RELAX_STATUS` ExtendedInfo to matching subscriber. Fan-in via `IntraActivitySequencing.ActionResponseEvent`.

### §19.2 Response Write-back

```xpath
eventResponse/payload/xsd3:NasCheckCollectionBlacklistResponse/xsd3:data/xsd3:relaxStatus
→ subscriber.ExtendedInfo[Name='RELAX_STATUS']/Value
```

### §19.4 Completion

```text
IntraActivitySequencing.ActionResponseEvent(currActivity)
→ "true" when all pending requests responded
(Old RequestCount code COMMENTED OUT)
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
