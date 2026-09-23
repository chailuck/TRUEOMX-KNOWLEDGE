# Request_OMX_GET_SRV_TRX_NO

> AA Service Transaction Number — Batch Sequence Fetch with Per-Subscriber Distribution

**Priority:** 5 | **forwardChain:** true | **Author:** mranade-T420 | **Pattern:** Single Batch Request | **Backend:** OMX Sequence Service (AA_TRX_NO_SEQ) | **Generated:** 2026-07-27

---

## §1 — Overview & Purpose

This rule allocates AA service transaction sequence numbers (from sequence `AA_TRX_NO_SEQ`) for downstream AA provisioning. It counts eligible subscribers first, then requests that exact number of sequence values in a single batch call. The response distributes one sequence number per subscriber in iteration order.

> **Single batch request pattern:** Uses `Event.Ext.sendEventImmediate` with `amount = countAllSub`. The response returns all values in a `GetSrvTrxNoResponse/sequenceValue[]` array, distributed by index (`sequenceValue[$countSrvTrxNo+1]`) as the response handler iterates subscribers.

> **AA_CHECK_CONFIRMATION pre-wiring:** The response handler scans `ProcessFlow.Activities[]` for `AA_CHECK_CONFIRMATION` (same Parameter[0] network command type) and sets `RequestCount = countSrvTrxNo` — pre-seeding the downstream fan-in counter.

**Two activity parameters:**
- `Parameter[0]` — network command type (e.g., `NAC`, `DSD`, or `INAC`/`IDSD` after IoT transform). Written as `SrvTrxTp` on each `SrvTrxNoInfo`.
- `Parameter[1]` — SOURCE_OR_TARGET filter. Only subscribers with matching `ExtendedInfo[SOURCE_OR_TARGET]` are counted/assigned. If absent → all subscribers included.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_OMX_GET_SRV_TRX_NO` |
| Priority | 5 |
| forwardChain | true |
| Author | mranade-T420 |
| Backend | OMX Sequence Service — sequence name `AA_TRX_NO_SEQ` |
| Request schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/GetSrvTrxNoRequest.xsd` |
| Response schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/GetSrvTrxNoResponse.xsd` |
| Dispatch pattern | Single batch request — `sendEventImmediate`, NOT IntraActivitySequencing |
| Parameter[0] | Network command type (NAC/DSD/INAC/IDSD) → written as `SrvTrxTp` |
| Parameter[1] | SOURCE_OR_TARGET filter. Empty → all subscribers. |
| Audit log gate | `AllowWriteLog(OrderType)` — different from standard WritePayload gate |
| AA_CHECK_CONFIRMATION pre-wiring | Response sets `AA_CHECK_CONFIRMATION.RequestCount = countSrvTrxNo` |
| Companion rule | `Request_OMX_GET_SRV_TRX_NO_MSIM.rule` — MSIM variant |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity |
| 2 | `orderCurrentActivity.ActivityID == "OMX_GET_SRV_TRX_NO"` | Targets this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_GET_SRV_TRX_NO"` | Order-level double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires on fresh activity |

---

## §5 — Execution Flow

```text
1. Init — isActResub; evaluate orderCurrentActivity.PreExecCheck
          read Parameter[1] → param (SOURCE_OR_TARGET filter)
2. Count eligible ParentOU subscribers:
     if param set → count where ExtendedInfo[SOURCE_OR_TARGET]=param AND PreExecCheck passes
     else         → count all (subPOULen)
3. Count eligible ChildOU subscribers (same logic, GetXMLForSubscriberInChildOU)
4. Build request: ns:sequenceName="AA_TRX_NO_SEQ", ns:amount=countAllSub
5. sendEventImmediate(gchReq)
6. Status → IN_PROGRESS
7. [AllowWriteLog] send Logger event (request audit)
8. [!isActResub] RequestCount++
9. SendDataToDB
10. [PreExecCheck=false] SkipActivity("4")
11. Exception → HandleActivityException
```

---

## §9 — Request Payload (GetSrvTrxNoRequest)

```text
createEvent
└── event
    ├── JMSPriority       ← $orderRequest/OrderPriority             [Conditional]
    ├── JMSCorrelationID  ← OrderData/OMXTrackingId                 [Conditional]
    ├── OrderID           ← OrderData/OrderID                       [Conditional]
    ├── RefID             ← OrderData/Customer/RefId                 [Conditional — Customer-level]
    ├── OrderType         ← OrderData/OrderType                      [Conditional]
    └── payload
        └── ns:GetSrvTrxNoRequest
            ├── ns:sequenceName ← "AA_TRX_NO_SEQ"                   [Always static]
            └── ns:amount       ← $countAllSub                       [Always — pre-computed count]
```

> **No credentials:** Unlike most FMs, this request XSLT does not include `UserName/PassWord`.

---

## §8 — System & Integration Dependencies

### §8.1 — Activity Parameter Dependencies

| Parameter | Index | Example Values | Role |
|-----------|-------|----------------|------|
| Network command type | `Parameter[0]` | NAC, DSD, INAC, IDSD | Written as `SrvTrxTp`; used to match AA_CHECK_CONFIRMATION |
| SOURCE_OR_TARGET filter | `Parameter[1]` | SOURCE, TARGET, (empty) | Filters which subscribers receive SrvTrxNo |

### §8.2 — Subscriber Eligibility Logic

```java
// REQUEST rule — counting:
if (param != null && String.length(param) > 0) {
    // Count only where ExtendedInfo[SOURCE_OR_TARGET].Value == param
    // AND per-subscriber PreExecCheck passes
    countAllSub += matches;
} else {
    countAllSub += subPOULen;  // all subscribers
}

// RESPONSE rulefunction — distribution (same filter):
if (sourceTarget == null || String.length(sourceTarget) == 0
    || String.equals(param2, sourceTarget)) {
    // AND per-subscriber PreExecCheck passes
    // → assign sequenceValue[$countSrvTrxNo+1] to this subscriber
    countSrvTrxNo++;
}
```

### §8.3 — AA_CHECK_CONFIRMATION Pre-Wiring

```java
// After all SrvTrxNo distributed:
for (int i = 0; i < iActLen; i++) {
    if (Activities[i].ActivityID == "AA_CHECK_CONFIRMATION"
        && Activities[i].Parameter[0] == currActivity.Parameter[0]) {
        Activities[i].RequestCount = countSrvTrxNo;  // pre-seed fan-in counter
    }
}
```

### §8.4 — JMS/ESB Channel Dependencies

| Direction | Event | Method | Purpose |
|-----------|-------|--------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_GET_SRV_TRX_NO` | `sendEventImmediate` | Single batch sequence request |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `sendEventImmediate` | Audit — gated by `AllowWriteLog(OrderType)` |

---

## §12 — Activity Status Management

| Trigger | Code | Status |
|---------|------|--------|
| Rule fires | 0 | WAITING |
| PreExecCheck false | 4 | SKIPPED |
| Request sent | 1 | IN_PROGRESS |
| Exception | 3 | ERROR |
| Response handled | 2 | COMPLETED |

---

## §15 — Function Dependency Tree

```text
Request_OMX_GET_SRV_TRX_NO (rule)
├── [if PreExecCheck] Instance.serializeUsingDefaults + XPath.execute
├── XPath.evalAsString(tib:trim(Parameter[$j+1]))         [param = Parameter[1]]
├── Subscriber count loop (ParentOU):
│   ├── [param set] GetXMLForSubscriber + XPath.execute [per-subscriber PreExecCheck]
│   └── Check ExtendedInfo[SOURCE_OR_TARGET].Value == param → countAllSub++
├── Subscriber count loop (ChildOU): [same, GetXMLForSubscriberInChildOU]
├── Event.createEvent(xslt://OMX_GET_SRV_TRX_NO)
│   └── payload: { sequenceName="AA_TRX_NO_SEQ", amount=countAllSub }
├── Event.Ext.sendEventImmediate(gchReq)
├── GetActivityStatusString("1", false)
├── [AllowWriteLog(OrderType)] Logger event
├── [!isActResub] RequestCount++
└── SendDataToDB

Response_OMX_GET_SRV_TRX_NO (rulefunction)
├── currActivity.ProcessID = nanoTime()
├── param1 = Parameter[0]   [network command type]
├── param2 = Parameter[1]   [SOURCE_OR_TARGET filter]
├── Loop ParentOU[k].Subscriber[j]:
│   ├── XPath.evalAsString(ExtendedInfo[SOURCE_OR_TARGET]/Value)
│   ├── [matches param2 or empty + PreExecCheck]:
│   │   ├── Instance.createInstance(xslt://OMX_GetSrvTrxNoRes)
│   │   │   ├── extId = "OMX_GET_SRV_TRX_NO:" + sequenceValue[$countSrvTrxNo+1]
│   │   │   ├── srvTrxNo = sequenceValue[$countSrvTrxNo+1]
│   │   │   └── srv_trx_tp_cd = $param1
│   │   ├── currActivity.Response[n] = seqResBySeq
│   │   ├── Instance.createInstance(xslt://SrvTrxNoInfo)
│   │   │   ├── extId = "AASRV:" + OMXTrackingId + ":" + srvTrxNo
│   │   │   ├── SrvTrxNo = srvTrxNo
│   │   │   └── SrvTrxTp = param1
│   │   ├── subscriber.SrvTrxNoInfo[n] = srvTrxNoInfo
│   │   └── countSrvTrxNo++
├── Loop ChildOU[k][m].Subscriber[n]: [same pattern]
├── AA_CHECK_CONFIRMATION pre-wiring:
│   └── Activities[i].RequestCount = countSrvTrxNo (where ActivityID="AA_CHECK_CONFIRMATION"
│       AND Parameter[0]=currActivity.Parameter[0])
├── [AllowWriteLog(OrderType)] Logger event
└── return "true"
```

---

## §19 — Response Message Rule

### §19.1 — Overview

Single batch response with all sequence values in `GetSrvTrxNoResponse/sequenceValue[]`. Handler iterates subscribers with the same eligibility filter, assigns `sequenceValue[$countSrvTrxNo+1]` per subscriber, creates `OMX_GetSrvTrxNoRes` in `currActivity.Response[]` and `SrvTrxNoInfo` in `subscriber.SrvTrxNoInfo[]`. Returns `"true"` unconditionally.

### §19.2 — Concept Fields Created per Subscriber

| Concept | Field | Source |
|---------|-------|--------|
| `OMX_GetSrvTrxNoRes` | extId | `"OMX_GET_SRV_TRX_NO:" + sequenceValue[$countSrvTrxNo+1]` |
| | ResponseCode | `$eventResponse/ResponseCode` |
| | ResponseMessage | `$eventResponse/ResponseMsg` |
| | CompletionStatus | `$eventResponse/CompletionStatus` |
| | srvTrxNo | `GetSrvTrxNoResponse/sequenceValue[$countSrvTrxNo+1]` |
| | srv_trx_tp_cd | `$param1` (Parameter[0] — network command type) |
| `SrvTrxNoInfo` | extId | `"AASRV:" + OMXTrackingId + ":" + srvTrxNo` |
| | SrvTrxNo | srvTrxNo |
| | SrvTrxTp | srv_trx_tp_cd (same as param1) |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Pre-count (request) and distribution (response) must apply the same eligibility filter; mismatch → index out of bounds on sequenceValue[].
- **R2** — Sequence values assigned by iteration order (ParentOU subscribers before ChildOU); migration must preserve this order.
- **R3** — AA_CHECK_CONFIRMATION.RequestCount pre-wiring is a critical side effect; must happen after all SrvTrxNo values are distributed.
- **R4** — Parameter[0] may have been transformed from NAC→INAC by OMX_TRANSFORM_NETWORK_CMD_TO_IOT; handle both forms.
- **R5** — Audit logging uses `AllowWriteLog(OrderType)` — some order types suppress all audit logging.

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| countAllSub mismatch between request and response → index out of bounds on sequenceValue[] | [HIGH] | Ensure PreExecCheck is deterministic; guard on sequenceValue array length before indexing |
| AA_CHECK_CONFIRMATION pre-wiring by Parameter[0] equality — multiple activities with same type pre-wired | [MEDIUM] | Verify only one AA_CHECK_CONFIRMATION per command type in process flow |
| Sequence values assigned by iteration order — OU structure changes cause different assignment | [MEDIUM] | Test with multi-OU orders; verify AA transaction matching is by value, not position |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
