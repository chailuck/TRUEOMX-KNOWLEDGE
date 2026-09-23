# Request_CCBS_MOVE_SUB

> Moves subscribers to a new OU in CCBS. Contains 4 OrderType branches (36, 11001, 11002+countNewPou, default). Activity parameter MOVE_TO_OU specifies the destination OU. Response updates subscriber.SubscriberId from CCBS response.

> **Bug:** ChildOU audit logger OPERATION_NAME = "CCBS_MOVE_SUBS" (extra 'S') vs POU logger "CCBS_MOVE_SUB" — inconsistent audit trail. Fix in migration target.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_MOVE_SUB` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | CCBS_MOVE_SUB |
| Author | awalia-t420 |
| Backend | CCBS — MoveSubscriber endpoint |
| Pattern | Fire-and-Forget (sendEventImmediate + RequestCount++) |
| Activity Parameter | MOVE_TO_OU — SOURCE_OR_TARGET value for destination OU |
| Response Concept | Concepts.FM.Response.CCBS_MoveSubscriberRes |
| Post-processing | Updates subscriber.SubscriberId from response SubscrNumber |

---

## §4 — Rule Conditions (WHEN)

1. `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
2. `orderCurrentActivity.ActivityID == "CCBS_MOVE_SUB"`
3. `orderRequest.ProcessFlow.NextActivityID == "CCBS_MOVE_SUB"`
4. `orderCurrentActivity.Status == "WAITING"`

---

## §5 — Execution Flow

1. Get `MOVE_TO_OU` parameter via `GetActivityParamValueFromKey(activity, "MOVE_TO_OU")`
2. Iterate POU[i] → Subscriber[j]; evaluate PreExecCheck
3. Determine OrderType branch (36, 11001, 11002+countNewPou, default)
4. Build MoveSubscriberRequest with branch-specific fields
5. `Event.Ext.sendEventImmediate(reqEvent)`; `RequestCount++`
6. Repeat for ChildOU
7. Set IN_PROGRESS; audit log (POU: "CCBS_MOVE_SUB"; ChildOU: "CCBS_MOVE_SUBS" **[BUG]**)

---

## §7 — OrderType Branch Logic

| OrderType | Subscriber Selection | MoveToUnitId | ActivityReason | GroupResourcesPolicy |
|-----------|---------------------|--------------|----------------|---------------------|
| 36 | ExtendedInfo[OLD_SHAREPLAN_CHILD_ID]/Value | ParentOU[SOURCE_OR_TARGET=MOVE_TO_OU]/OUId | `'SHIN'` (hardcoded) | 89 |
| 11001 | SubscriberId | pOu/OUId | `'SHIN'` (hardcoded) | 89 |
| 11002 (no NEW_PARENT_OU) | SOURCE subscriber | pOu/OUId | SubscriberActivityInfo or 'CREQ' | 89 if CUG_IND=Y else 78 |
| Default | SOURCE subscriber | pOu/OUId | SubscriberActivityInfo or 'CREQ' | 89 if CUG_IND=Y else 78 |

DistributionPolicy is always **78**.  
PricePlan: from `SubscriberOffers[ServiceType=80][FE_OR_CCBS=FE]`

---

## §9 — Payload Build

```text
createEvent
└── event (MoveSubscriberRequest)
    ├── JMSPriority/JMSCorrelationID/OrderID/CES/RefID/OrderType   [Conditional]
    ├── UserName/PassWord                                            [Always — not gated]
    └── payload
        └── MoveSubscriberRequest
            ├── subscriberIdInfo/subscrNumber  ← branch-specific subId
            ├── MoveToUnitId                   ← branch-specific OUId
            ├── DistributionPolicy             ← 78                  [Always]
            ├── GroupResourcesPolicy           ← 89 (36/11001) or conditional
            ├── ActivityReason                 ← 'SHIN' or ActivityInfo or 'CREQ'
            ├── PricePlan                      ← SubscriberOffers[ST=80][FE]
            └── NameAddressPolicy/OffersPolicy [11002+countNewPou only]
```

---

## §15 — Function Dependency Tree

```text
Request_CCBS_MOVE_SUB
├── GetActivityParamValueFromKey(activity, "MOVE_TO_OU")
├── GetXMLForSubscriber(req, refId)
├── GetXMLForSubscriberInChildOU(req, refId, pouRefId)
├── XPath.execute() — PreExecCheck
├── XPath.evalAsInt() — countNewPou (has NEW_PARENT_OU ExtInfo)
├── XPath.evalAsBoolean() — CUG_IND check
├── Event.Ext.sendEventImmediate(reqEvent)
├── AllowWriteLog(orderType)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(req, activity, "4")
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 — Migration Notes

| # | Requirement / Risk | Severity |
|---|---|---|
| [BUG] | Fix ChildOU logger OPERATION_NAME "CCBS_MOVE_SUBS" → "CCBS_MOVE_SUB" | [HIGH] |
| R1 | Implement all 4 OrderType branches with distinct logic | [HIGH] |
| R2 | Response must update subscriber.SubscriberId from SubscriberIdsInfo/SubscriberId/SubscrNumber | [HIGH] |
| R3 | ActivityReason defaults to 'CREQ'; OrderType 36/11001 always 'SHIN' | [MEDIUM] |
| R4 | GroupResourcesPolicy: 89 if CUG_IND=Y else 78 (for 11002/default) | [MEDIUM] |
| R5 | Fan-in: count "000" == RequestCount | [LOW] |

---

## §19 — Response Message Rule

### §19.1 Overview

Creates `CCBS_MoveSubscriberRes`. Updates each subscriber's `SubscriberId` in working memory from CCBS response `SubscriberIdsInfo/SubscriberId/SubscrNumber`, matched by RefID. Fan-in via count "000" == RequestCount. Wrapped in try/finally with debug logger.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Order context |
| eventResponse | Events.OMConsumers.OMXFM.Response.CCBS_MOVE_SUB | Backend response |
| currActivity | Concepts.OM.ProcessConfig.Activity | Activity state |

### §19.3 Key Post-processing

```java
// For each POU[i].Subscriber[j] and ChildOU[k].Subscriber[j] where RefId == eventResponse.RefID:
subscriber.SubscriberId = eventResponse.payload/SubscriberIdsInfo/SubscriberId/SubscrNumber
subscriber.ResponseCode = eventResponse.ResponseCode
subscriber.ResponseMsg = eventResponse.ResponseMsg
```

### §19.4 Fan-in Completion

```xpath
successResponseCount = count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)="000"])
if (currActivity.RequestCount == successResponseCount) → return "true"
else → return "false"
```

OPERATION_NAME: `"CCBS_MOVE_SUB"`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
