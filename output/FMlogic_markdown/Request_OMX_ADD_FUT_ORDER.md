# Request_OMX_ADD_FUT_ORDER

> Creates a future order record in OMX for each POU subscriber (no ChildOU). Uses EffectiveDate from order request; empty futureSoc placeholder. Credentials always included regardless of IsEnableUserPass.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_FUT_ORDER` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | OMX_ADD_FUT_ORDER |
| Author | warawich-nb |
| Backend | OMX Future Order service |
| Pattern | Fire-and-Forget (sendEventImmediate + RequestCount++) |
| Activity Parameter | FINALLY=Y — signals final order; can override orderType |
| Response Concept | Concepts.FM.Response.OMX_AddFutureRes |

---

## §4 — Rule Conditions (WHEN)

1. `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
2. `orderCurrentActivity.ActivityID == "OMX_ADD_FUT_ORDER"`
3. `orderRequest.ProcessFlow.NextActivityID == "OMX_ADD_FUT_ORDER"`
4. `orderCurrentActivity.Status == "WAITING"`

---

## §5 — Execution Flow

1. Read `LogicalDate` concept from working memory
2. Check if `Parameter[1]` provides override orderType
3. Iterate POU[i] → Subscriber[j] only (no ChildOU)
4. Evaluate PreExecCheck per subscriber
5. Build `ns3:futureOrderWithSoc` payload
6. `Event.Ext.sendEventImmediate(reqEvent)`; `RequestCount++`
7. Set activity IN_PROGRESS; send audit log

---

## §8 — System & Integration Dependencies

### §8.4 BE Working Memory Dependencies

| Concept | ExtId | Access |
|---------|-------|--------|
| LogicalDate | "LogicalDate" | Read — logical date context |

### §8.6 Global Variables

- `IsEnableUserPass` — Note: credentials are included **unconditionally** in this FM

---

## §9 — Payload Build

```text
createEvent
└── event
    ├── JMSPriority/JMSCorrelationID/OrderID/RefID/OrderType   [Conditional]
    ├── UserName/PassWord                                        [Always — not gated]
    └── payload
        └── ns3:futureOrderWithSoc
            ├── ns:futureOrder
            │   ├── effectiveDate  ← $orderRequest/EffectiveDate          [Always]
            │   ├── status         ← "1"                                   [Always]
            │   ├── orderType      ← Parameter[1] override OR OrderType   [Always]
            │   ├── nodeLevel      ← "5"                                   [Always, subscriber]
            │   ├── nodeId         ← subscriber/SubscriberId              [Always]
            │   ├── userText       ← "request by {channel} on {now}"      [Always]
            │   ├── futureType     ← "FUT"                                 [Always]
            │   ├── activityReason/extendedInfo/fromOrderId/remark        [Conditional]
            └── ns2:futureSocs
                └── futureSoc
                    └── code       ← (empty placeholder)                  [Always]
```

---

## §15 — Function Dependency Tree

```text
Request_OMX_ADD_FUT_ORDER
├── Instance.getByExtIdByUri("LogicalDate", ...)
├── GetActivityParamValueFromKey(activity, "FINALLY")
├── GetXMLForSubscriber(req, refId)
├── XPath.execute() — PreExecCheck evaluation
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
| R1 | POU subscribers only — do NOT iterate ChildOU | [HIGH] |
| R2 | Always include credentials — not gated by IsEnableUserPass | [MEDIUM] |
| R3 | `nodeLevel=5`, `status=1`, `futureType="FUT"` — always these constants | [MEDIUM] |
| R4 | `futureSoc/code` is always empty — placeholder for later population | [LOW] |
| R5 | Parameter[1]="FINALLY=Y" can override orderType | [MEDIUM] |

---

## §19 — Response Message Rule

### §19.1 Overview

Parses `OMX_ADD_FUTURE` response into `OMX_AddFutureRes` concept. Fan-in via `RequestCount == successResponseCount`.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Order context |
| eventResponse | Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE | Backend response |
| currActivity | Concepts.OM.ProcessConfig.Activity | Activity state |

### §19.4 Fan-in Completion

```xpath
successResponseCount = count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)="000"])
if (currActivity.RequestCount == successResponseCount) → return "true"
else → return "false"
```

OPERATION_NAME: `"OMX_ADD_FUT_ORDER"`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
