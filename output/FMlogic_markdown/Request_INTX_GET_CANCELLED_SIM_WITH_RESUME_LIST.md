# Request_INTX_GET_CANCELLED_SIM_WITH_RESUME_LIST

> Retrieve cancelled SIM list eligible for resume from INTX; for MultiSIM eSIM resume (MSRES) subscribers, populates MIIMEI ResourceInfo from eSimResourceOfferInfoList data.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_CANCELLED_SIM_WITH_RESUME_LIST` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | INTX_GET_CANCELLED_SIM_WITH_RESUME_LIST |
| Author | SathidP-PC |
| Backend | INTX |
| Pattern | Fire-and-Forget (sendEventImmediate + RequestCount++) |

---

## §4 — Rule Conditions (WHEN)

1. `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
2. `orderCurrentActivity.ActivityID == "INTX_GET_CANCELLED_SIM_WITH_RESUME_LIST"`
3. `orderRequest.ProcessFlow.NextActivityID == "INTX_GET_CANCELLED_SIM_WITH_RESUME_LIST"`
4. `orderCurrentActivity.Status == "WAITING"`

---

## §5 — Execution Flow

1. Loop POU[i] → Subscriber[j]; skip if already responded
2. Evaluate PreExecCheck
3. **Guard:** if `IsBlank(currMSISDN) || currSub.MultiSIMInfo != null` → skip subscriber
4. Send `GetCancelledSIMWithResumeListReq` (type=MSISDN, value=currMSISDN)
5. If not resubmit: `RequestCount++`
6. Repeat for ChildOU subscribers
7. If requests sent: set IN_PROGRESS; else SkipActivity

---

## §9 — Payload Build

```text
createEvent
└── event (extId ← OMXUtils:generateTrackingID())
    ├── JMSPriority / JMSCorrelationID / OrderID / RefID  [Conditional / Always]
    ├── UserName / PassWord                                [Credential-gated]
    ├── OrderType                                          [Conditional]
    └── payload
        └── ns:GetCancelledSIMWithResumeListReq
            └── ns:searchList
                └── ns:searchInfoArray
                    ├── ns:type   ← "MSISDN"   [Always]
                    └── ns:value  ← $currMSISDN [Always]
```

---

## §15 — Function Dependency Tree

```text
Request_INTX_GET_CANCELLED_SIM_WITH_RESUME_LIST
├── GetXMLForSubscriber(req, refId)
├── GetXMLForSubscriberInChildOU(req, refId, pouRefId)
├── BRMS.IsBlank(currMSISDN)       ← guard: skip blank MSISDN
├── XPath.execute() — PreExecCheck
├── Event.Ext.sendEventImmediate(reqEvent)
├── AllowWriteLog(orderType)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(req, activity, "4")
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 — Migration Notes

| # | Requirement |
|---|-------------|
| R1 | Query INTX by MSISDN for each subscriber; skip if MSISDN blank or MultiSIMInfo already set |
| R2 | Response: for MSRES subscribers with multiSimList, populate MIIMEI from eSimResourceOfferInfoList matching subscriber's EID |
| R3 | Fan-in: count "000" ResponseCodes == RequestCount |

---

## §19 — Response Message Rule

Creates `INT_GetCancelledSIMWithResumeListRes` concept.

### §19.4 Fan-in Completion

```xpath
successResponseCount = count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)="000"])
if (currActivity.RequestCount == successResponseCount) → return "true"
```

**Post-processing:** if subscriber ActivityReason ends with 'MSRES' AND multiSimList present AND MIIMEI not yet set → populates MIIMEI ResourceInfo from `eSimResourceOfferInfoList.SIMAndOfferInfoArray[EID=$subscriber/EID]/resourceInfo/IMEI`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
