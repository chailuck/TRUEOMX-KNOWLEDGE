# Request_CCBS_UPDATE_MNP_REVERSAL_CANCEL

## §1 Overview & Purpose

Updates CCBS L9 MNP attributes for a **port-in reversal or MNP rejection** (ActivityReason=MNPHR or RFREOT). Unlike `CCBS_L9_UPDATE_MNP_ATTRIBUTES`, this variant reads MNP fields from the **subscriber's ExtendedInfo** (not order MNPInfo) and hardcodes `L9PortInd=86`.

Used in **CANCEL_SUBSCRIBER** process — Step 59 — gated on `ActivityReason=MNPHR or RFREOT and not ATS`.

> **Note:** Reuses the `CCBS_L9_UPDATE_MNP_ATTRIBUTES` event schema/type — only data sources differ.

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPDATE_MNP_REVERSAL_CANCEL` |
| Priority | 5 |
| ForwardChain | true |
| Author | chch-NB |
| Key diff vs L9_UPDATE | L9PortInd=86 hardcoded; subscriber ExtendedInfo as MNP source |

## §5 Execution Flow

1. Resubmit check → `PurgePendingRequestsBeforeResubmit()`
2. Iterate ParentOU subscribers → PreExecCheck → create event → `sendEventImmediate` + `consumeEvent` + `ActionRequestEvent()`
3. Send audit log
4. Repeat for ChildOU
5. `SendFirstRequestEvent()`, Status="1", SendDataToDB

## §8 Dependencies

### §8.1 Scenario
MNP reversal (MNPHR) or rejected port-out (RFREOT). Subscriber was mid-port process that needs to be reversed.

### §8.5 ExtendedInfo Fields Required (from Subscriber)

| Key | CCBS L9 Field |
|-----|--------------|
| `DONOR_OPERATOR` | ns1:L9DonorOperator |
| `DONOR_ZONE` | ns1:L9DonorZone (number cast) |
| `REC_OPERATOR` | ns1:L9RecOperator |
| `REC_ZONE` | ns1:L9RecZone (number cast) |

## §9 Key Differences vs CCBS_L9_UPDATE_MNP_ATTRIBUTES

| Field | L9_UPDATE | MNP_REVERSAL_CANCEL |
|-------|-----------|---------------------|
| L9DonorOperator | MNPInfo/DonorOperator | **ExtendedInfo[DONOR_OPERATOR]** |
| L9DonorZone | MNPInfo/DonorZoneCode (conditional) | **number(ExtendedInfo[DONOR_ZONE])** |
| L9PortInd | $l9PortInd param (default 79) | **Hardcoded 86** |
| L9RecOperator | MNPInfo/RCPOperator | **ExtendedInfo[REC_OPERATOR]** |
| L9RecZone | MNPInfo/RCPZoneCode | **number(ExtendedInfo[REC_ZONE])** |
| activityType | $activityType param | **Hardcoded "C"** |
| activityDateInfo | xsi:nil="true" | (omitted) |

## §10 XSLT Field Mapping Tree

```text
createEvent → event
├── JMSPriority/JMSCorrelationID/OrderID/RefID/CES/OrderType  [all non-conditional]
└── payload
    └── ns:l9UpdateMNPAttributesRequest
        ├── ns:subscriberIdInfo/ns:subscrNumber    ← SubscriberId           [Always]
        ├── ns1:SubscriberGeneralInfo
        │   ├── ns1:L9DonorOperator  ← ExtendedInfo[DONOR_OPERATOR]/Value  [Always]
        │   ├── ns1:L9DonorZone      ← number(ExtendedInfo[DONOR_ZONE]/Value)  [Always]
        │   ├── ns1:L9PortInd        ← 86 (hardcoded — reversal)           [Always]
        │   ├── ns1:L9RecOperator    ← ExtendedInfo[REC_OPERATOR]/Value    [Always]
        │   └── ns1:L9RecZone        ← number(ExtendedInfo[REC_ZONE]/Value) [Always]
        ├── ns:activityType          ← "C" (hardcoded)                     [Always]
        └── ns:activityInfo
            ├── ns:activityReason    ← ActivityReason or "CREQ"            [Always]
            └── ns:userText          ← SubscriberActivityInfo/UserText     [Always]
```

## §17 Migration Notes

- **R1:** L9PortInd=86 is the MNP reversal/cancel indicator — must not be confused with 79
- **R2:** MNP attributes from subscriber ExtendedInfo — must be populated by INTX_GET_SIM_INFO earlier
- **R3:** Reuses CCBS_L9_UPDATE_MNP_ATTRIBUTES event type — routing by ActivityID
- **Risk:** [HIGH] — Incorrect L9PortInd leaves MNP records inconsistent in CCBS

## §19 Response Message Rule

**Type:** `L9UpdateMNPAttributesRes` | eventResponse = `CCBS_L9_UPDATE_MNP_ATTRIBUTES` (shared schema)
**Fan-in:** `IntraActivitySequencing.ActionResponseEvent(currActivity)`
**Audit:** OPERATION_NAME="CCBS_UPDATE_MNP_REVERSAL_CANCEL"

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
