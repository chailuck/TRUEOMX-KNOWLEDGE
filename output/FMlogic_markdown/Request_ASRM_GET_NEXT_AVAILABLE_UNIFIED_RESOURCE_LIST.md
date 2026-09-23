# Request_ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST

> Find and reserve the next available SIM/eSIM resource from ASRM for swap/portIn operations (RIO, RIO_SWAP, ESIM paths).

---

## §1 — Overview & Purpose

Fires when the order flow reaches `ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST`. Sends `UnifiedResourceListRequest` to ASRM with Status=AVAILABLE, Type=SIM, Activity=RESERVE, page 1 of 1.

Three XSLT variants based on PROJ param:
1. PROJ=RIO/RIO_SWAP/ESIM + OLD_EID/ESIM gate → single call per subscriber, DEALER=70000776; `break` after first order
2. Default (FE offer loop, POU) → per-offer fan-out, DEALER from param or 40000001
3. Default (FE offer loop, ChildOU) → same as above but no RefID in header

Pattern: **IntraActivitySequencing** (assertEvent → ActionRequestEvent → SendFirstRequestEvent).

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST |
| Author | chch |
| Backend | ASRM |
| Pattern | IntraActivitySequencing |

---

## §4 — Rule Conditions (WHEN)

1. `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
2. `orderCurrentActivity.ActivityID == "ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST"`
3. `orderRequest.ProcessFlow.NextActivityID == "ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST"`
4. `orderCurrentActivity.Status == "WAITING"`

---

## §5 — Execution Flow

1. Read PROJ, DEALERCODE, COMPANY params from activity
2. If resubmit: `PurgePendingRequestsBeforeResubmit`
3. Loop POU[i] → Subscriber[j] → SubscriberOffers[k]
4. BRANCH A (PROJ=RIO/RIO_SWAP/ESIM): check OLD_EID or ESIM flag → send single request; `break`
5. BRANCH B (default): evaluate PreExecCheck per offer (FE_OR_CCBS filter); if true → send per-offer request
6. Repeat for ChildOU subscribers
7. If requests sent: `SendFirstRequestEvent` → IN_PROGRESS; else `SkipActivity`
8. Catch → `HandleActivityException`

---

## §8 — System & Integration Dependencies

### §8.2 ESB/JMS Channel

| Direction | Event | Protocol |
|-----------|-------|----------|
| [OUTBOUND] | Events.OMConsumers.OMXFM.Request.ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST | JMS/ESB |
| [INBOUND] | Events.OMConsumers.OMXFM.Response.ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST | JMS/ESB |

### §8.3 Backend API

| System | Operation | Schema |
|--------|-----------|--------|
| ASRM | GetNextAvailableUnifiedResourceList | amdocs.rm3g.interfaces.datatypes.UnifiedResourceListRequest |

### §8.5 ExtendedInfo Fields

| Name | Where | Role |
|------|-------|------|
| FE_OR_CCBS | SubscriberOffers.ExtendedInfo | Controls offer-level branching |
| ICC_ID | Subscriber.ExtendedInfo / SubscriberOffers.ExtendedInfo | Written by response handler |

---

## §9 — Payload Build

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                     [Conditional]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId           [Conditional]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID                 [Conditional]
    ├── RefID                    ← $refId                                          [Always]
    ├── UserName                 ← $orderRequest/OrderData/User                    [Credential-gated]
    ├── PassWord                 ← $orderRequest/OrderData/Password                [Credential-gated]
    ├── OrderType                ← $orderRequest/OrderData/OrderType               [Conditional]
    └── payload
        └── ns7:UnifiedResourceListRequest
            ├── UnifiedResourceCriteriaInfo
            │   ├── AttributesValues[COMPANY]  ← param / 'RM'→'02' / else '06'  [Always]
            │   ├── AttributesValues[SIM_TYPE] ← subscriber/ResourceInfo[SIM_TYPE] / '6' [Always]
            │   ├── AttributesValues[DEALER]   ← dealerCodeValue / default       [Always]
            │   ├── Status                     ← 'AVAILABLE'                     [Always]
            │   └── Type                       ← 'SIM'                           [Always]
            ├── UnifiedResourceActivityInfo/Activity/ActivityName ← 'RESERVE'    [Always]
            ├── PaginationInfo/PageNumber      ← 1                               [Always]
            └── PaginationInfo/PageSize        ← 1                               [Always]
```

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| OPERATION_NAME | "ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST" |
| AUDIT_TRACE | "Request Sent for OMX_ADD_FUT_PP" **[Bug: copy-paste error — wrong operation name]** |

> **Bug:** AUDIT_TRACE hardcoded to "Request Sent for OMX_ADD_FUT_PP". Should read "ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST". Fix in migration target.

---

## §15 — Function Dependency Tree

```text
Request_ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── GetActivityParamValueFromKey(activity, "PROJ")
├── GetActivityParamValueFromKey(activity, "DEALERCODE")
├── GetActivityParameterValueFromKey(activity, "COMPANY")
├── GetXMLForSubscriberOfferFilterWithExtendedInfo(req, subRefId, refId, filter)
├── XPath.execute() — PreExecCheck evaluation
├── XPath.evalAsBoolean() — OLD_EID or ESIM check
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

| # | Requirement |
|---|-------------|
| R1 | Query ASRM with Status=AVAILABLE, Type=SIM, Activity=RESERVE, page 1 of 1 |
| R2 | Support 3 PROJ variants with different DEALER defaults and loop scope |
| R3 | Write ICCID to subscriber.ExtendedInfo[ICC_ID] (ESIM/RIO_SWAP) or offer.ExtendedInfo[ICC_ID] (FE) |
| R4 | ESIM response: also write SIM ResourceInfo from ICCID |
| R5 | Support resubmit (purge pending before retry) |
| [HIGH] | AUDIT_TRACE copy-paste bug — fix "OMX_ADD_FUT_PP" to correct operation name |
| [MEDIUM] | Three near-identical XSLT variants — refactor to single template with parameters |
| [LOW] | Dealer default '40000001' (ChildOU) vs '70000776' (POU) — verify if intentional |

---

## §19 — Response Message Rule

### §19.1 Overview

Creates `ASRM_GetURListRes` concept. Extracts ICCID from `UnifiedResourceListInfo/UnifiedResourceInfoArr[1]/UnifiedResourceIdInfo/Value`. Writes ICCID to order memory per PROJ.

### §19.3 ResponseBase Tree

```text
ASRM_GetURListRes
├── ResponseCode        ← $eventResponse/ResponseCode            [Conditional]
├── ResponseMessage     ← $eventResponse/ResponseMsg             [Conditional]
├── CompletionStatus    ← $eventResponse/CompletionStatus        [Conditional]
├── ReferenceId         ← $eventResponse/RefID                   [Conditional]
└── ICCID               ← UnifiedResourceInfoArr[1]/Value        [Conditional]
```

### §19.4 ICCID Write-back

| PROJ | Action |
|------|--------|
| ESIM | Write ICC_ID to subscriber.ExtendedInfo AND SIM ResourceInfo |
| RIO_SWAP | Write ICC_ID to subscriber.ExtendedInfo |
| Default | Write ICC_ID to offer.ExtendedInfo where Soc==ReferenceId and FE_OR_CCBS=FE |

Fan-in: `IntraActivitySequencing.ActionResponseEvent(currActivity)`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
