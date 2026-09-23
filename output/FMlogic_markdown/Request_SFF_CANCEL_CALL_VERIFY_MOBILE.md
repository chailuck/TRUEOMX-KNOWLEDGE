# Request_SFF_CANCEL_CALL_VERIFY_MOBILE

## §1 Overview & Purpose

Cancels a Call Verify feature on a mobile number via **SFF (Soft Feature Function)** system. Invoked when a subscriber's call verification is active but `CALL_VER_RESULT != "PASS"`.

Used in **CANCEL_SUBSCRIBER** process — Step 75 — gated on `CALL_VER_RESULT != "PASS" and not ATS`. Sends per-subscriber requests to SFF. Only iterates **ParentOU subscribers** (no ChildOU loop).

**Payload is minimal:** only MSISDN (`productIdNumber`) and OMXTrackingId (`refId`) required.

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule | `Rules.OMConsumers.OMXFM.Request.Request_SFF_CANCEL_CALL_VERIFY_MOBILE` |
| Priority | 5 |
| ForwardChain | true |
| Dispatch | ParentOU only (no ChildOU) |
| Uses IntraActivitySequencing | Yes |

## §4 Conditions (WHEN)

1. `orderCurrentActivity.ActivityID == "SFF_CANCEL_CALL_VERIFY_MOBILE"`
2. `orderCurrentActivity.Status == "WAITING"`

## §5 Execution Flow

1. Resubmit: `PurgePendingRequestsBeforeResubmit()`
2. Iterate ParentOU subscribers only
3. Per-subscriber: check response not already received → evaluate PreExecCheck
4. Create & assert `SFF_CANCEL_CALL_VERIFY_MOBILE` event → `ActionRequestEvent()`
5. Send audit log
6. `SendFirstRequestEvent()`, Status="1", SendDataToDB (or SkipActivity if none)

## §8 System & Integration Dependencies

### §8.1 Scenario
CANCEL_SUBSCRIBER (types 10/12/14) with active call verification (`CALL_VER_RESULT != "PASS"`).

### §8.2 ESB / JMS

| Direction | Event | Schema |
|-----------|-------|--------|
| [OUTBOUND] | SFF_CANCEL_CALL_VERIFY_MOBILE | ns:SFFCancelCallVerifyMobileRequest |
| [OUTBOUND] | Logger | Audit |

### §8.3 Backend
System: **SFF** | Operation: **CancelCallVerifyMobile** | Schema: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd8`

## §9 Payload Build

> **Simplest payload in CANCEL_SUBSCRIBER flow** — no complex mapping, no conditional payload fields.

| Field | Source |
|-------|--------|
| `ns:productIdNumber` | subscriber/MSISDN |
| `ns:refId` | OrderData/OMXTrackingId |

Event headers: JMSPriority, JMSCorrelationID (OMXTrackingId), OrderID, RefID, UserName/PassWord (if IsEnableUserPass), OrderType.

## §10 XSLT Field Mapping Tree

```text
createEvent → event
├── JMSPriority        ← OrderPriority         [Always]
├── JMSCorrelationID   ← OMXTrackingId         [Always]
├── OrderID            ← OrderData/OrderID     [Always]
├── RefID              ← $refId                [Always]
├── UserName/PassWord                          [Conditional: IsEnableUserPass=true]
├── OrderType          ← OrderData/OrderType   [Always]
└── payload
    └── ns:SFFCancelCallVerifyMobileRequest
        ├── ns:productIdNumber  ← $subscriber/MSISDN          [Always]
        └── ns:refId            ← OrderData/OMXTrackingId     [Always]
```

## §11 Audit Logging

| Field | Value |
|-------|-------|
| OPERATION_NAME | SFF_CANCEL_CALL_VERIFY_MOBILE |
| AUDIT_TRACE | concat("Request Sent for RefId ", refId) |
| PROCESS_ID | concat(pid, "_REQ") |

## §12 Activity Status

| Condition | Action |
|-----------|--------|
| Requests sent | SendFirstRequestEvent(), Status="1" |
| All skipped | SkipActivity("4") |
| Exception | HandleActivityException |

## §17 Migration Notes

- **R1:** SFF is a legacy call-feature system — verify survival after TRUE-DTAC network integration
- **R2:** `CALL_VER_RESULT` populated by upstream step — ensure field is still available
- **R3:** Only ParentOU subscribers — verify if intentional for SFF service scope
- **Risk:** [MEDIUM] — If SFF decommissioned, need equivalent cancel-call-verify in new platform

## §19 Response Message Rule

**Type:** `ResponseBase` (extId=generateTrackingID())
**Fan-in:** `IntraActivitySequencing.ActionResponseEvent(currActivity)`
**Audit:** OPERATION_NAME="SFF_CANCEL_CALL_VERIFY_MOBILE", AUDIT_TRACE=concat("Response received for RefId ", RefID), PROCESS_ID=concat(pid,"_RES")

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
