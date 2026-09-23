# Request_INTX_GET_SUBSCRIBER_INFO

> Retrieves subscriber info (InitActDate, MinActivationDate) from INTX for each POU and ChildOU subscriber. Response populates SubscriberGeneralInfo in working memory; also writes OLD_BAN_DATE for backdate order types (126/127/129/15/16).

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_SUBSCRIBER_INFO` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | INTX_GET_SUBSCRIBER_INFO |
| Author | awalia-t420 |
| Backend | INTX — GetSubscriberInfo operation |
| Pattern | IntraActivitySequencing (assertEvent + ActionRequestEvent + SendFirstRequestEvent) |
| Activity Parameter | SOURCE — filters to SOURCE_OR_TARGET subscribers |
| Response Concept | Concepts.FM.Response.INT_GetActivateDate |

---

## §4 — Rule Conditions (WHEN)

1. `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
2. `orderCurrentActivity.ActivityID == "INTX_GET_SUBSCRIBER_INFO"`
3. `orderRequest.ProcessFlow.NextActivityID == "INTX_GET_SUBSCRIBER_INFO"`
4. `orderCurrentActivity.Status == "WAITING"`

---

## §5 — Execution Flow

1. Purge pending requests if resubmit
2. Iterate POU[i] → Subscriber[j]; evaluate PreExecCheck; skip if responded
3. Build `GetSubscriberInfoReq`: `correlatedId = OMXTrackingId`, `subscriberNo = SubscriberId`
4. POU variant: subscriberNo unconditional; ChildOU: guarded by `xsl:if test="SubscriberId"`
5. Include UserName/PassWord if `IsEnableUserPass`
6. `Event.assertEvent(reqEvent)`; `ActionRequestEvent(reqEvent, currActivity)`
7. Repeat for ChildOU subscribers
8. `SendFirstRequestEvent(currActivity)` → IN_PROGRESS

---

## §8 — System & Integration Dependencies

### §8.2 Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | INTX_GET_SUBSCRIBER_INFO | GetSubscriberInfo to INTX |
| [AUDIT] | OMXESB Logger | Audit trail |

### §8.6 Global Variables

| Variable | Purpose |
|----------|---------|
| IsEnableUserPass | Gates UserName/PassWord inclusion |

---

## §9 — Payload Build

```text
createEvent
└── event
    ├── JMSPriority/JMSCorrelationID/OrderID/RefID/OrderType   [Conditional]
    ├── UserName/PassWord                                        [Credential-gated: IsEnableUserPass]
    └── payload
        └── ns1:GetSubscriberInfoReq
            ├── ns1:correlatedId  ← $orderRequest/OrderData/OMXTrackingId  [Always]
            └── ns1:subscriberNo  ← $subscriber/SubscriberId               [Always POU; Conditional ChildOU]
```

---

## §15 — Function Dependency Tree

```text
Request_INTX_GET_SUBSCRIBER_INFO
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── GetXMLForSubscriber(req, refId)
├── GetXMLForSubscriberInChildOU(req, refId, pouRefId)
├── XPath.execute() — PreExecCheck
├── Event.assertEvent(reqEvent)
├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(req, activity, "4")
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 — Migration Notes

| # | Requirement / Risk | Severity |
|---|---|---|
| R1 | Send per subscriber for both POU and ChildOU; IntraActivitySequencing fan-in | [HIGH] |
| R2 | Response must populate SubscriberGeneralInfo.InitActDate and l9TmvActDate (min of init vs min) | [HIGH] |
| R3 | Backdate orders (126/127/129/15/16): write OLD_BAN_DATE ExtendedInfo if absent | [MEDIUM] |
| R4 | Credential gate via IsEnableUserPass | [MEDIUM] |
| R5 | Subscriber lookup by RefID uses two prefix patterns: `SUB:` and `CSUB:` | [MEDIUM] |

---

## §19 — Response Message Rule

### §19.1 Overview

Rich post-processing: creates `INT_GetActivateDate` concept, looks up subscriber by RefID, creates/updates `SubscriberGeneralInfo` with activation dates, and adds OLD_BAN_DATE for backdate orders.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Order context |
| eventResponse | Events.OMConsumers.OMXFM.Response.INTX_GET_SUBSCRIBER_INFO | Backend response |
| currActivity | Concepts.OM.ProcessConfig.Activity | Activity state |

### §19.3 Post-processing Logic

1. Lookup subscriber: `SUB:{OMXTrackingId}:{RefID}` → if null try `CSUB:...`
2. Get/create `SubscriberGeneralInfo` at extId `SUBGI:{trackingId}:{subscriber.RefId}`
3. If `initActDate` non-empty: parse and set `subsGenInfo.InitActDate`
4. If `minActivationDate` non-empty: `l9TmvActDate = minActivationDate`; else `l9TmvActDate = initActDate`
5. Link `subscriber.SubscriberGeneralInfo = subsGenInfo`
6. For backdate orders: create `OLD_BAN_DATE` ExtendedInfo with value = InitActDate (if absent)

### §19.4 Fan-in Completion

```text
IntraActivitySequencing.ActionResponseEvent(currActivity)
→ returns "true" when all pending requests have responses
```

OPERATION_NAME: `"INTX_GET_SUBSCRIBER_INFO"`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
