# Request_CVSS_CANCEL_SUBS

> Cancels subscribers in CVSS. Iterates at Account level (not POU/ChildOU). OrderType=11002 uses shareplan-specific logic for ban and numberOfCancel. Source field routing: EOC/"EOC", MNP+02/06/10/"MNP_INT", MNP+other/"MNP_EXT", default/"CCBS". No credentials.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CVSS_CANCEL_SUBS` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | CVSS_CANCEL_SUBS |
| Author | awalia-t420 |
| Backend | CVSS — CancelSubscriberCVSS operation |
| Pattern | IntraActivitySequencing |
| Iteration Scope | **Account array** (not POU/ChildOU) |
| Credentials | None — no UserName/PassWord |

---

## §4 — Rule Conditions (WHEN)

1. `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
2. `orderCurrentActivity.ActivityID == "CVSS_CANCEL_SUBS"`
3. `orderRequest.ProcessFlow.NextActivityID == "CVSS_CANCEL_SUBS"`
4. `orderCurrentActivity.Status == "WAITING"`

---

## §5 — Execution Flow

1. Iterate `Customer.Account[$var]` array
2. Evaluate PreExecCheck using `GetXMLForAccount`
3. Determine OrderType branch (11002 vs default)
4. Build `CancelSubscriberCVSSRequest`
5. `Event.assertEvent`; `IntraActivitySequencing.ActionRequestEvent`
6. `IntraActivitySequencing.SendFirstRequestEvent` → IN_PROGRESS

---

## §7 — OrderType-Specific Logic

| OrderType | ban | numberOfCancel |
|-----------|-----|----------------|
| 11002 | Account without `SHAREPLAN_ACTION=BREAK` | Count of SHAREPLAN_PARENT_TYPE subscribers |
| Default | Current Account | Count of POU+ChildOU Subscribers matching AccountRefId |

### Source Field Routing

| Condition | source |
|-----------|--------|
| Channel = "EOC" | `"EOC"` |
| MNP + DonorOperatorCode in {02, 06, 10} | `"MNP_INT"` |
| MNP + other DonorOperatorCode | `"MNP_EXT"` |
| Default | `"CCBS"` |

---

## §9 — Payload Build

```text
createEvent
└── event
    ├── JMSPriority/JMSCorrelationID/OrderID/OrderType   [Conditional]
    ├── RefID                                             [NOT SET]
    ├── UserName/PassWord                                 [NOT PRESENT]
    └── payload
        └── ns:CancelSubscriberCVSSRequest
            ├── ProductCount  ← Account[$var]/ProductCount        [Always]
            └── CancelSubscriber
                ├── ban           ← branch-specific account        [Always]
                ├── numberOfCancel ← branch-specific count         [Always]
                └── source        ← EOC|MNP_INT|MNP_EXT|CCBS      [xsl:choose]
```

---

## §15 — Function Dependency Tree

```text
Request_CVSS_CANCEL_SUBS
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── GetXMLForAccount(req, accountRefId)
├── XPath.execute() — PreExecCheck
├── XPath.evalAsInt() — SHAREPLAN_PARENT_TYPE count (11002)
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
| R1 | Iterate at **Account level**, not POU/ChildOU — common pattern mismatch risk | [HIGH] |
| R2 | OrderType=11002: exclude SHAREPLAN_ACTION=BREAK; count SHAREPLAN_PARENT_TYPE | [HIGH] |
| R3 | Source routing: EOC/MNP+02/06/10/other/default | [MEDIUM] |
| R4 | No credentials; no RefID in event header | [MEDIUM] |
| R5 | Old RequestCount fan-in is commented out — uses IntraActivitySequencing fan-in | [LOW] |

---

## §19 — Response Message Rule

### §19.1 Overview

Creates `CVSSCancelSubsRes` with standard fields plus CVSS-specific: `result`, `statusCode`, `statusMessage`. Fan-in via IntraActivitySequencing.

### §19.3 Response Fields

| Field | Source | Namespace |
|-------|--------|-----------|
| ResponseCode | eventResponse/ResponseCode | — |
| ResponseMessage | eventResponse/ResponseMsg | — |
| CompletionStatus | eventResponse/CompletionStatus | — |
| ReferenceId | eventResponse/RefID | — |
| result | ns:CancelSubscriberResponse/ns:result | CancelSubscriberInCVSSRes |
| statusCode | ns:CancelSubscriberResponse/ns:statusCode | CancelSubscriberInCVSSRes |
| statusMessage | ns:CancelSubscriberResponse/ns:statusMessage | CancelSubscriberInCVSSRes |

### §19.4 Fan-in Completion

```text
IntraActivitySequencing.ActionResponseEvent(currActivity)
Note: Old RequestCount fan-in code is commented out in source
```

OPERATION_NAME: `"CVSS_CANCEL_SUBS"`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
