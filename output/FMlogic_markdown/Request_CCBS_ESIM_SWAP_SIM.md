# Request_CCBS_ESIM_SWAP_SIM

> Execute eSIM swap in CCBS via mSimData API; pre-populates PEID/PMATCHID ResourceInfo with Source=FE; packs PEID/OLD_PEID values with subscriberId; sets IS_CALLED_MSIM_SWAP_SIM=Y.

> **CRITICAL:** Response rulefunction returns `"true"` unconditionally — NO fan-in check is implemented. Engine declares completion after the first response regardless of RequestCount. Must be fixed in migration target.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_ESIM_SWAP_SIM` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | CCBS_ESIM_SWAP_SIM |
| Author | sakarin-radchapunya |
| Backend | CCBS (eSIM endpoint) |
| Pattern | Fire-and-Forget (sendEventImmediate + RequestCount++) |
| Schema | http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/MSim.xsd |

### Used in Steps (SWAPSIM)

| Step # | Step ExtId | PreExecCheck Summary |
|--------|-----------|----------------------|
| 27 | CCBS_ESIM_SWAP_SIM | no FILE_ID + TARGET + NEW/OLD_PMATCHID>0 + no NEW/OLD_EID + not IS_CALLED_MSIM_SWAP_SIM |
| 28 | CCBS_ESIM_SWAP_SIM_BULK | FILE_ID exists + TARGET + NEW/OLD_PMATCHID>0 |

---

## §5 — Execution Flow

1. Loop POU[i] → Subscriber[j]; evaluate PreExecCheck
2. **Pre-populate PEID:** if no PEID ResourceInfo AND NEW_PEID not blank → create PEID with Source='FE'
3. **Pre-populate PMATCHID:** if no PMATCHID ResourceInfo AND NEW_PMATCHID not blank → create PMATCHID with Source='FE'
4. Build mSimData payload; PEID/OLD_PEID → `concat(ValuesArray, '_', subscriberId)` [eSIM packing]
5. Send via `sendEventImmediate`; if not resubmit: `RequestCount++`; set IS_CALLED_MSIM_SWAP_SIM=Y
6. Repeat for ChildOU subscribers
7. If requests sent: set IN_PROGRESS; else SkipActivity

---

## §9 — Payload Build

```text
createEvent / event
├── JMSPriority / JMSCorrelationID / OrderID / CES / OrderType  [Conditional]
├── UserName / PassWord                                           [Credential-gated]
└── payload
    └── ns:mSimData/ns:OUList
        ├── ns:Subscriber/ns:subscriberId  ← subscriber/SubscriberId     [Always]
        ├── ns:MultiSIMInfo/ns:Master      ← (empty)                     [Always]
        ├── ns1:ResourceInfo (for-each)
        │   ├── ns1:Values  ← if Name=NEW_PEID|OLD_PEID: concat(ValuesArray,'_',subscriberId)
        │   │                  else: ValuesArray                          [eSIM-specific packing]
        │   ├── ns1:Name    ← ResourceName
        │   └── ns1:Category ← ResourceCategory
        └── ns:activityInfo
            ├── ns:ActivityReason ← SubscriberActivityInfo/ActivityReason [Conditional]
            └── ns:UserText       ← SubscriberActivityInfo/UserText       [Conditional]
```

---

## §17 — Migration Notes

| # | Requirement / Risk |
|---|-------------------|
| R1 | Pre-populate PEID/PMATCHID (Source='FE') before calling CCBS eSIM endpoint |
| R2 | Pack PEID/OLD_PEID values with `concat(value, '_', subscriberId)` |
| R3 | Set IS_CALLED_MSIM_SWAP_SIM=Y after dispatch |
| [CRITICAL] R4 | Response always returns "true" with NO fan-in count check — implement proper fan-in in target |

---

## §19 — Response Message Rule

### §19.1 Overview

Creates `CCBS_MsimSwapSimRes` concept (same as CCBS_MSIM_SWAP_SIM).

### §19.4 Fan-in Completion — DEFECT

```text
ACTUAL:   return "true";   ← unconditional, no count check
EXPECTED: count("000" ResponseCodes) == RequestCount
```

The `successResponseCount` calculation is entirely absent (not even commented out). The engine declares activity completion after receiving **any single response** regardless of how many requests were dispatched.

OPERATION_NAME: `"CCBS_ESIM_SWAP_SIM"`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
