# Request_OMX_UPDATE_PENDING_PARTIAL_ORDER

> Update the pending partial order record in OMX per subscriber with MSISDN, orderType, omxTrackingID, channel, and ICCID (prefers ExtendedInfo[ICC_ID], falls back to ResourceInfo[SIM]).

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_UPDATE_PENDING_PARTIAL_ORDER` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | OMX_UPDATE_PENDING_PARTIAL_ORDER |
| Author | (none listed) |
| Backend | OMX Internal |
| Pattern | Fire-and-Forget (sendEventImmediate + RequestCount++) |

---

## §4 — Rule Conditions (WHEN)

1. `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
2. `orderCurrentActivity.ActivityID == "OMX_UPDATE_PENDING_PARTIAL_ORDER"`
3. `orderRequest.ProcessFlow.NextActivityID == "OMX_UPDATE_PENDING_PARTIAL_ORDER"`
4. `orderCurrentActivity.Status == "WAITING"`

---

## §5 — Execution Flow

1. Loop POU[p] → Subscriber[ps]; skip if already responded
2. Evaluate PreExecCheck (TARGET subscribers only — from ProcessConfig)
3. Build UpdatePendingPartialOrderReq
4. Send via `sendEventImmediate`; if not resubmit: `RequestCount++`
5. Repeat for POU[p] → ChildOU[c] → Subscriber[cs]
6. If requests sent: IN_PROGRESS; else SkipActivity

---

## §8 — ICCID Resolution Priority

| Priority | Source | Path |
|----------|--------|------|
| 1st | ExtendedInfo | `subscriber/ExtendedInfo[Name='ICC_ID']/Value` |
| 2nd (fallback) | ResourceInfo | `subscriber/ResourceInfo[ResourceName='SIM']/ValuesArray` |

Note: **No credential gate** (no UserName/PassWord fields). **No CES field** (unlike most other FM events).

---

## §9 — Payload Build

```text
createEvent
└── event
    ├── JMSPriority       ← $orderRequest/OrderPriority            [Conditional]
    ├── JMSCorrelationID  ← $orderRequest/OrderData/OMXTrackingId  [Conditional]
    ├── OrderID           ← $orderRequest/OrderData/OrderID        [Conditional]
    ├── RefID             ← $refId                                  [Always]
    ├── OrderType         ← $orderRequest/OrderData/OrderType      [Conditional]
    └── payload
        └── ns:UpdatePendingPartialOrderReq
            ├── ns:msisdn        ← $subscriber/MSISDN              [Always]
            ├── ns:orderType     ← $orderRequest/OrderData/OrderType [Always]
            ├── ns:omxTrackingID ← $orderRequest/OrderData/OMXTrackingId [Conditional]
            ├── ns:channel       ← $orderRequest/OrderData/Channel  [Conditional]
            └── ns:iccid         xsl:choose
                ├── ExtendedInfo[ICC_ID]/Value                      [1st choice]
                └── ResourceInfo[SIM]/ValuesArray                   [fallback]
```

---

## §15 — Function Dependency Tree

```text
Request_OMX_UPDATE_PENDING_PARTIAL_ORDER
├── GetXMLForSubscriber(req, refId)
├── GetXMLForSubscriberInChildOU(req, refId, pouRefId)
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
| R1 | Send per subscriber (POU and ChildOU), TARGET only |
| R2 | ICCID resolution: ExtendedInfo[ICC_ID] first, then ResourceInfo[SIM] fallback |
| R3 | No credential gate — do not include UserName/PassWord |
| R4 | No CES field in this event |
| R5 | Fan-in: count "000" ResponseCodes == RequestCount |

---

## §19 — Response Message Rule

Creates `ResponseBase` concept (standard base type). extId ← `OMXUtils:generateTrackingID()`.

### §19.4 Fan-in Completion

```xpath
successResponseCount = count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)="000"])
if (currActivity.RequestCount == successResponseCount) → return "true"
```

OPERATION_NAME: `"OMX_UPDATE_PENDING_PARTIAL_ORDER"`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
