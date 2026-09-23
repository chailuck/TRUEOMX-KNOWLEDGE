# Request_OMX_ADD_FUT_FULL_SUSPEND

## §1 — Overview & Purpose

Creates a future full-suspend order in OMX. The effectiveDate, orderType, and activityReason are determined by the `ActivityReason` parameter:

| ActivityReason | effectiveDate | orderType | activityReason |
|---------------|--------------|-----------|----------------|
| BALOS | today + 3 days | "18" | "SUS1" |
| SUFIC | end-of-bill-cycle | "19" | "RESIC" |
| SCVG | today + SoftToFullDay | SoftToFullOrderType | SoftToFullReason |

> **⚠ Naming anomaly:** ActivityID is `OMX_ADD_FUT_FULL_SUSPEND` but JMS event dispatched is `OMX_ADD_FUTURE`.
>
> **⚠ Hardcoded return:** Response handler always returns "true" — no fan-in check on ResponseCode. Unique among all OMX FMs.

**Subscriber selection:** `tib:if-absent(ParentOU[1].Subscriber[1], ChildOU[1].Subscriber[1])`  
**SOC selection:** offer where ServiceType='80' AND FE_OR_CCBS='FE'

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_FUT_FULL_SUSPEND` |
| Activity ID | `OMX_ADD_FUT_FULL_SUSPEND` |
| JMS Event type | `OMX_ADD_FUTURE` [Naming anomaly] |
| Fan-in | Hardcoded `"true"` — no success count check |
| Send pattern | `Event.Ext.sendEventImmediate` |

---

## §5 — Execution Flow

1. Check resubmit; evaluate PreExecCheck
2. Get first subscriber via `tib:if-absent`
3. Resolve SOC: offer where ServiceType='80' AND FE_OR_CCBS='FE'
4. Branch on ActivityReason (BALOS/SUFIC/SCVG) → set effectiveDate, orderType, activityReason
5. Build `futureOrderWithSoc` payload; send `OMX_ADD_FUTURE` event
6. Increment RequestCount; send audit log
7. Set WAITING_RESPONSE; persist to DB

---

## §8 — System & Integration Dependencies

### §8.2 — ESB/JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `OMX_ADD_FUTURE` | Schedule future full-suspend in OMX |
| [INBOUND] | `OMX_ADD_FUTURE` (response) | Confirmation (ignored — hardcoded true) |

### §8.3 — Global Variables (SCVG branch)

| Global Variable | Used for |
|----------------|---------|
| `SoftToFullDay` | Days added to today for effectiveDate |
| `SoftToFullOrderType` | orderType value |
| `SoftToFullReason` | activityReason value |

---

## §10 — XSLT Field Mapping

```text
createEvent / event
├── JMSPriority / JMSCorrelationID / OrderID / RefID / OrderType  [Always]
└── payload / ns3:futureOrderWithSoc
    ├── ns:futureOrder
    │   ├── ns3:orderId         ← OrderID                         [Always]
    │   ├── ns3:msisdn          ← first subscriber ServiceNumber  [Always]
    │   ├── ns3:effectiveDate   ← computed by ActivityReason branch [Branch-driven]
    │   ├── ns3:orderType       ← "18" / "19" / SoftToFullOrderType [Branch-driven]
    │   ├── ns3:activityReason  ← "SUS1" / "RESIC" / SoftToFullReason [Branch-driven]
    │   └── ns3:channel         ← Channel                         [Conditional]
    └── ns2:futureSocs
        └── ns2:soc             ← $code (SOC from FE offer)       [Always]
```

---

## §17 — Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| ActivityID vs JMS event type mismatch | [HIGH] | Align naming |
| Response handler hardcoded to "true" — never validates ResponseCode | [HIGH] | Implement proper response validation |
| effectiveDate 3 separate code paths — business rule complexity | [HIGH] | Extract to shared utility; document all 3 rules |
| SCVG branch uses 3 global variables — missing/blank = wrong date | [MEDIUM] | Add null/blank guards |
| SOC selection implicit contract (ServiceType=80, FE_OR_CCBS=FE) | [MEDIUM] | Validate FE offer presence before building payload |

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_OMX_ADD_FUT_FULL_SUSPEND`: Event scope `OMX_ADD_FUTURE`. Creates `OMX_AddFutureRes`. **Always returns "true" — no fan-in check.**

### §19.3 — Response Concept (OMX_AddFutureRes)

```text
OMX_AddFutureRes
├── extId               ← OMXUtils:generateTrackingID()          [Always]
├── ResponseCode        ← $eventResponse/ResponseCode            [Conditional]
├── ResponseMessage     ← $eventResponse/ResponseMsg             [Conditional]
├── CompletionStatus    ← $eventResponse/CompletionStatus        [Conditional]
└── [Note: ReferenceId field absent in this concept]
```

### §19.4 — Fan-in (Hardcoded)

```xpath
// ALWAYS returns "true" — no count check
return "true";
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
