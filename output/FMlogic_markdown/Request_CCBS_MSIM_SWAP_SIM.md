# Request_CCBS_MSIM_SWAP_SIM

> Execute SIM swap in CCBS for Multi-SIM (MSIM) subscribers; pre-populates ResourceInfo (OLD_MIIMEI/MIIMEI/EID/SIM/IMSI) before dispatch; sets IS_CALLED_MSIM_SWAP_SIM=Y.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_MSIM_SWAP_SIM` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | CCBS_MSIM_SWAP_SIM |
| Author | sakarin-radchapunya |
| Backend | CCBS (Multi-SIM endpoint) |
| Pattern | IntraActivitySequencing |
| Schema | http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/MSim.xsd |

---

## §5 — Execution Flow

1. If resubmit: `PurgePendingRequestsBeforeResubmit`
2. Loop POU[i] → Subscriber[j]; evaluate PreExecCheck; check reqSuccess guard
3. **Pre-populate ResourceInfo** (if not already present): OLD_MIIMEI (from OLD_MIIMEI), MIIMEI (from NEW_MIIMEI), EID (from NEW_EID), SIM (from NEW_SIM), IMSI (from NEW_IMSI)
4. Build and assert mSimData event; ActionRequestEvent
5. Set IS_CALLED_MSIM_SWAP_SIM=Y on subscriber (if not resubmit)
6. Repeat for ChildOU subscribers
7. SendFirstRequestEvent → IN_PROGRESS; or SkipActivity

---

## §6 — ResourceInfo Pre-population

| Source | Target | Source Attr | Condition |
|--------|--------|-------------|-----------|
| OLD_MIIMEI | OLD_MIIMEI | — | not(subscriber/ResourceInfo[OLD_IMEI]) AND not blank |
| NEW_MIIMEI | MIIMEI | — | not(subscriber/ResourceInfo[IMEI]) AND not(MIIMEI) AND not blank |
| NEW_EID | EID | — | not(subscriber/ResourceInfo[EID]) AND not blank |
| NEW_SIM | SIM | — | not(subscriber/ResourceInfo[SIM]) AND not blank |
| NEW_IMSI | IMSI | — | not(subscriber/ResourceInfo[IMSI]) AND not blank |

> **Note:** Target ResourceName for OLD_MIIMEI is written as 'OLD_MIIMEI' (not 'OLD_IMEI'). Clarify with data dictionary.

---

## §9 — Payload Build

```text
createEvent / event
├── JMSPriority / JMSCorrelationID / OrderID / CES / RefID / OrderType  [Conditional/Always]
├── UserName / PassWord                                                   [Credential-gated]
└── payload
    └── ns:mSimData/ns:OUList
        ├── ns:Subscriber/ns:subscriberId  ← subscriber/SubscriberId     [Always]
        ├── ns:MultiSIMInfo/ns:Master      ← (empty element)             [Always]
        ├── ns1:ResourceInfo (for-each)
        │   ├── ns1:Name     ← ResourceName
        │   ├── ns1:Category ← ResourceCategory
        │   └── ns1:Values   ← ValuesArray
        └── ns:activityInfo
            ├── ns:ActivityReason ← SubscriberActivityInfo/ActivityReason [Conditional]
            └── ns:UserText       ← SubscriberActivityInfo/UserText       [Conditional]
```

---

## §15 — Function Dependency Tree

```text
Request_CCBS_MSIM_SWAP_SIM
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── GetXMLForSubscriber(req, refId)
├── GetXMLForSubscriberInChildOU(req, refId, pouRefId)
├── XPath.evalAsBoolean() × 5    ← ResourceInfo absence checks
├── Instance.createInstance() × 5 ← Create ResourceInfo concepts
├── Event.assertEvent(reqEvent)
├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
├── Instance.createInstance(SubscriberExtendedInfo)  ← IS_CALLED_MSIM_SWAP_SIM=Y
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(req, activity, "4")
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 — Migration Notes

| # | Requirement |
|---|-------------|
| R1 | Pre-populate missing ResourceInfo from NEW_* before calling CCBS |
| R2 | Build mSimData with subscriber ID, empty MultiSIMInfo/Master, full ResourceInfo array, activityInfo |
| R3 | Set IS_CALLED_MSIM_SWAP_SIM=Y (gates steps 34 and 27/28 downstream) |
| R4 | Fan-in via IntraActivitySequencing |

---

## §19 — Response Message Rule

Creates `CCBS_MsimSwapSimRes` concept (ResponseCode/ResponseMsg/CompletionStatus/ReferenceId).

Fan-in: `IntraActivitySequencing.ActionResponseEvent(currActivity)`.

Note: `successResponseCount` XPath is commented out — fan-in relies entirely on IntraActivitySequencing internal state tracking.

OPERATION_NAME: `"CCBS_MSIM_SWAP_SIM"`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
