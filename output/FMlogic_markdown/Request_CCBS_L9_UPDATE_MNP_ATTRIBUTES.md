# Request_CCBS_L9_UPDATE_MNP_ATTRIBUTES

## §1 Overview & Purpose

Updates MNP (Mobile Number Portability) L9 attributes in CCBS during port-out cancellation. Sets DonorOperator, DonorZone, RecOperator, RecZone and L9PortInd from `MNPInfo` in the order.

Used in **CANCEL_SUBSCRIBER** process — Step 58 — gated on `OrderType=10 and not ATS`. Configurable via `L9_PORT_IND` (default 79) and `ACTIVITY_TYPE` (default C) parameters.

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_L9_UPDATE_MNP_ATTRIBUTES` |
| Priority | 5 |
| ForwardChain | true |
| Author | awalia-t420 |
| Parameters | L9_PORT_IND (default "79"), ACTIVITY_TYPE (default "C") |

## §4 Conditions (WHEN)

1. `orderCurrentActivity.ActivityID == "CCBS_L9_UPDATE_MNP_ATTRIBUTES"`
2. `orderCurrentActivity.Status == "WAITING"`

## §5 Execution Flow

1. Resubmit: `PurgePendingRequestsBeforeResubmit()`
2. Read L9_PORT_IND and ACTIVITY_TYPE parameters
3. Iterate ParentOU subscribers → PreExecCheck → create & assert event → `ActionRequestEvent()`
4. Repeat for ChildOU
5. `SendFirstRequestEvent()`, Status="1", SendDataToDB

## §8 Dependencies

### §8.1 Scenario
CANCEL_SUBSCRIBER OrderType=10 (MNP port-out): sets subscriber's L9 attributes to reflect portability state.

### §8.3 MNP Info Mapping

| Source | CCBS L9 Field |
|--------|--------------|
| MNPInfo/DonorOperator | ns1:L9DonorOperator |
| MNPInfo/DonorZoneCode | ns1:L9DonorZone (conditional) |
| Parameter L9_PORT_IND (default 79) | ns1:L9PortInd |
| MNPInfo/RCPOperator | ns1:L9RecOperator |
| MNPInfo/RCPZoneCode | ns1:L9RecZone |

## §9 Payload Build

| Field | Source |
|-------|--------|
| `ns:subscrNumber` | SubscriberId |
| `ns1:L9DonorOperator` | MNPInfo/DonorOperator |
| `ns1:L9DonorZone` | MNPInfo/DonorZoneCode (if exists) |
| `ns1:L9PortInd` | $l9PortInd param (default "79") |
| `ns1:L9RecOperator` | MNPInfo/RCPOperator |
| `ns1:L9RecZone` | MNPInfo/RCPZoneCode |
| `ns:activityType` | $activityType param (default "C") |
| `ns:activityDate` | xsi:nil="true" (always null) |
| `ns:activityReason` | ActivityReason or "CREQ" |

## §10 XSLT Field Mapping Tree

```text
createEvent → event
├── JMSPriority/JMSCorrelationID/OrderID/RefID/CES/OrderType  [standard headers]
└── payload
    └── ns:l9UpdateMNPAttributesRequest
        ├── ns:subscriberIdInfo/ns:subscrNumber    ← SubscriberId           [Always]
        ├── ns1:SubscriberGeneralInfo
        │   ├── ns1:L9DonorOperator  ← MNPInfo/DonorOperator               [Always]
        │   ├── ns1:L9DonorZone      ← MNPInfo/DonorZoneCode               [Conditional]
        │   ├── ns1:L9PortInd        ← $l9PortInd (default 79)             [Always]
        │   ├── ns1:L9RecOperator    ← MNPInfo/RCPOperator                  [Always]
        │   └── ns1:L9RecZone        ← MNPInfo/RCPZoneCode                  [Always]
        ├── ns:activityType          ← $activityType (default "C")          [Always]
        ├── ns:activityDateInfo/ns:activityDate  ← xsi:nil="true"           [Always null]
        └── ns:activityInfo
            ├── ns:activityReason    ← ActivityReason or "CREQ"             [Always]
            └── ns:userText          ← SubscriberActivityInfo/UserText      [Conditional]
```

## §17 Migration Notes

- **R1:** L9PortInd=79 standard cancellation — configurable via parameter
- **R2:** activityDate always null — CCBS uses logical date internally
- **R3:** CCBS-specific MNP L9 schema — verify target system compatibility

## §19 Response Message Rule

**Type:** `L9UpdateMNPAttributesRes` (extId=$pid) | **Fan-in:** `IntraActivitySequencing.ActionResponseEvent(currActivity)`
**Audit:** AUDIT_TRACE=concat("Response received for RefId ", RefID)

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
