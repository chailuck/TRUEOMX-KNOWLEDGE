# Request_OMX_GET_SRV_TRX_NO_MSIM

> Fetches service transaction sequence numbers for MultiSIM — counts qualifying MASTER + MINOR SIM entries, sends one OMX request for all, then distributes individual sequence numbers back to each SIM's SrvTrxNoInfo array. Also writes the total count to AA_CHECK_CONFIRMATION.RequestCount for downstream fan-in.

**Backend:** OMX FM (OMX_GET_SRV_TRX_NO) | **Pattern:** Single-shot JMS (count=N, array response) | **forwardChain:** true | **Author:** mranade-T420 | **Used in steps:** 40, 42

---

## §1 Overview & Purpose

Fetches service transaction sequence numbers (SrvTrxNo) for MultiSIM activation. The rule counts all qualifying MASTER and MINOR SIM entries across all POU subscribers, sends a single `OMX_GET_SRV_TRX_NO` request with `amount=countSrvTrxNo`, and receives an array of sequence numbers back. The response handler then distributes one sequence number per SIM into each SIM's `SrvTrxNoInfo[]` concept array.

- Subscribers without `MultiSIMInfo` are silently skipped (no error)
- PreExecCheck uses `GetXMLForSubscriberFilterWithMultiSIMInfo` — a MSIM-specific helper that passes role ("MASTER"/"MINOR"), Source filter, and IMSI
- If `countSrvTrxNo == 0` → SkipActivity("4"); no JMS event sent
- Resubmit guard: `isActResub` prevents double-counting of RequestCount
- AA_CHECK_CONFIRMATION write-back: response sets `RequestCount = countSrvTrxNo` on the matching downstream activity (matched by `Parameter[0]`)

> **Single backend call:** Unlike per-SIM fan-out, this FM sends one call with `ns:amount=N` and the OMX sequence service returns N values as `ns:sequenceValue[1..N]`. The response handler indexes into this array using `countSrvTrxNo` as a running pointer.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_OMX_GET_SRV_TRX_NO_MSIM.rule` | 112 lines |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_OMX_GET_SRV_TRX_NO_MSIM.rulefunction` | 111 lines |
| Author | mranade-T420 | |
| Priority | 5 | |
| forwardChain | true | |
| param1 | Activity parameter (comment: NAC,DSD) | Service transaction type → SrvTrxTp; also matched to AA_CHECK_CONFIRMATION.Parameter[0] |
| param2 | Activity parameter (comment: SOURCE,TARGET) | Read but not used in current code |
| Backend event type | `Events.OMConsumers.OMXFM.Request.OMX_GET_SRV_TRX_NO` | |
| Response event type | `Events.OMConsumers.OMXFM.Response.OMX_GET_SRV_TRX_NO` | Shared with non-MSIM OMX_GET_SRV_TRX_NO |
| Schema NS | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/GetSrvTrxNoRequest.xsd` | |
| Sequence name | `"AA_TRX_NO_SEQ"` (hardcoded) | |
| isActResub | `RequestCount > 0 && IsOrderResubmitted` | Suppresses RequestCount++ on resub; no PurgePending call |
| Skip condition | `countSrvTrxNo == 0` | SkipActivity("4") |
| Audit gate | [CONDITIONAL] | AllowWriteLog(OrderType) |
| AUDIT_TRACE (request) | "Request Sent for OMX_GET_SRV_TRX_NO_MSIM" | |
| AUDIT_TRACE (response) | "Response received for OMX_GET_SRV_TRX_NO_MSIM" | |

---

## §3 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_GET_SRV_TRX_NO_MSIM"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_GET_SRV_TRX_NO_MSIM"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §4 SIM Counting Logic (Request THEN)

| SIM slot | Condition to qualify | PreExecCheck XML builder | Filter param |
|----------|----------------------|--------------------------|--------------|
| **MASTER** | `sub.MultiSIMInfo != null` (null → skip subscriber) | `GetXMLForSubscriberFilterWithMultiSIMInfo(orderRequest, refId, "MASTER", Master.Source, "")` | `Master.Source` ("FE"/"PREV_MSIM") |
| **MINOR[k]** | Inner loop after MASTER; relies on outer skip for null guard | `GetXMLForSubscriberFilterWithMultiSIMInfo(orderRequest, refId, "MINOR", Minor[k].Source, Minor[k].IMSI)` | `Minor[k].Source` + `Minor[k].IMSI` |

> **COU note:** The request rule only traverses `ParentOU[i].Subscriber[j]` — there is NO COU (ChildOU) traversal in this FM.

---

## §5 Request Payload

```text
createEvent / event
├── JMSPriority              ← $orderRequest/OrderPriority             [Conditional]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId   [Conditional]
├── OrderID                  ← $orderRequest/OrderData/OrderID          [Conditional]
├── RefID                    ← $orderRequest/OrderData/Customer/RefId   [Conditional]
├── OrderType                ← $orderRequest/OrderData/OrderType        [Conditional]
└── payload
    └── ns:GetSrvTrxNoRequest
        ├── ns:sequenceName  ← "AA_TRX_NO_SEQ"                        [Always, hardcoded]
        └── ns:amount        ← $countSrvTrxNo                          [Always]
```

---

## §6 Response Handler — SrvTrxNo Distribution

The response traverses the same POU → Subscriber structure, using `countSrvTrxNo` (starts at 0) as an index into the backend's `ns:sequenceValue[]` array.

### For each qualifying MASTER SIM:

1. Re-runs PreExecCheck via `GetXMLForSubscriberFilterWithMultiSIMInfo(…, "MASTER", filter, "")`
2. Creates `OMX_GetSrvTrxNoRes`:
   - extId = `concat("OMX_GET_SRV_TRX_NO:", eventResponse/ns:sequenceValue[countSrvTrxNo+1])`
   - srvTrxNo ← `eventResponse/payload/ns:GetSrvTrxNoResponse/ns:sequenceValue[countSrvTrxNo+1]`
   - srv_trx_tp_cd ← param1
3. Appends to `currActivity.Response[]`
4. Creates `SrvTrxNoMSIMInfo` → appends to `master.SrvTrxNoInfo[]`:
   - SrvTrxNo ← srvTrxNo; SrvTrxTp ← param1; SrvStatus ← `master.Source`
5. `countSrvTrxNo++`

### For each qualifying MINOR[k] SIM:

Same logic, using `minor.Source` and `minor.IMSI` for PreExecCheck, writing to `minor.SrvTrxNoInfo[]`, `SrvStatus ← minor.Source`.

> **[HIGH RISK] Index alignment:** Request and response must traverse SIMs in the same order with the same PreExecCheck outcome to correctly pair `sequenceValue[k]` with each SIM.

---

## §7 AA_CHECK_CONFIRMATION Write-Back

After all SIM processing, the response handler scans all Process Flow activities:

```java
for(int i=0; i<iActLen; i++) {
    if(String.equals(activities[i].ActivityID, "AA_CHECK_CONFIRMATION")
       && String.equals(activities[i].Parameter[0], currActivity.Parameter[0])) {
        activities[i].RequestCount = countSrvTrxNo;
    }
}
```

Sets `AA_CHECK_CONFIRMATION.RequestCount` to the actual SIM count — this is the fan-in threshold for downstream activation confirmation.

| param1 value | Meaning | AA_CHECK_CONFIRMATION matched by |
|-------------|---------|----------------------------------|
| `NAC` | Network Activation Confirmation | Parameter[0]="NAC" |
| `DSD` | Deactivation/Status Dispatch | Parameter[0]="DSD" |

---

## §8 Response Concepts — Field Mapping

### OMX_GetSrvTrxNoRes (per qualifying SIM)

```text
createObject / object
├── @extId           ← concat("OMX_GET_SRV_TRX_NO:", ns:sequenceValue[k+1])  [Always]
├── ResponseCode     ← $eventResponse/ResponseCode                             [Conditional]
├── ResponseMessage  ← $eventResponse/ResponseMsg                              [Conditional]
├── CompletionStatus ← $eventResponse/CompletionStatus                         [Conditional]
├── srvTrxNo         ← ns:GetSrvTrxNoResponse/ns:sequenceValue[k+1]           [Always]
├── OMXTrackingId    ← $eventResponse/JMSCorrelationID                         [Conditional]
└── srv_trx_tp_cd    ← $param1  (activity Parameter[0])                        [Always]
```

### SrvTrxNoMSIMInfo (appended to SrvTrxNoInfo[])

```text
createObject / object
├── @extId     ← ns:generateTrackingID()                [Always]
├── SrvTrxNo   ← $seqResBySeq/srvTrxNo                 [Conditional]
├── SrvTrxTp   ← $seqResBySeq/srv_trx_tp_cd (=param1)  [Conditional]
└── SrvStatus  ← $master/Source or $minor/Source        [Conditional — "FE"/"PREV_MSIM"]
```

---

## §9 Function Dependency Tree

```text
Request_OMX_GET_SRV_TRX_NO_MSIM (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── param1, param2 ← Parameter[0], Parameter[1]
├── [POU loop i]:
│   └── [Subscriber loop j]:
│       ├── [if MultiSIMInfo == null]: continue
│       ├── MASTER check:
│       │   ├── GetXMLForSubscriberFilterWithMultiSIMInfo(…, "MASTER", Master.Source, "")
│       │   ├── XPath.execute(PreExecCheck)
│       │   └── [if "true"]: countSrvTrxNo++
│       └── MINOR loop k:
│           ├── GetXMLForSubscriberFilterWithMultiSIMInfo(…, "MINOR", Minor[k].Source, IMSI)
│           ├── XPath.execute(PreExecCheck)
│           └── [if "true"]: countSrvTrxNo++
├── [if countSrvTrxNo == 0]: SkipActivity(…, "4")
├── [else]:
│   ├── Event.createEvent(OMX_GET_SRV_TRX_NO, XSLT: sequenceName="AA_TRX_NO_SEQ", amount=$countSrvTrxNo)
│   ├── Event.Ext.sendEventImmediate(gchReq)
│   ├── Status = GetActivityStatusString("1", false)
│   ├── [if AllowWriteLog]: Logger("Request Sent for OMX_GET_SRV_TRX_NO_MSIM")
│   └── [if !isActResub]: RequestCount++
└── [catch] HandleActivityException

Response_OMX_GET_SRV_TRX_NO_MSIM (rulefunction)
├── currActivity.ProcessID = nanoTime()
├── param1, param2 ← currActivity.Parameter[0], [1]
├── countSrvTrxNo = 0
├── [POU loop i]:
│   └── [Subscriber loop j]:
│       ├── filter = Master.Source (if MultiSIMInfo && Master not null; else "")
│       ├── GetXMLForSubscriberFilterWithMultiSIMInfo(…, "MASTER", filter, "")
│       ├── XPath.execute(PreExecCheck)
│       ├── [if "true"]:
│       │   ├── Instance.createInstance(OMX_GetSrvTrxNoRes) { extId, srvTrxNo[k+1], srv_trx_tp_cd=param1 }
│       │   ├── currActivity.Response[] ← seqResBySeq
│       │   ├── Instance.createInstance(SrvTrxNoMSIMInfo) { SrvTrxTp=param1, SrvStatus=master.Source }
│       │   ├── master.SrvTrxNoInfo[] ← SrvTrxNoMSIMInfo
│       │   └── countSrvTrxNo++
│       └── MINOR loop k:
│           ├── GetXMLForSubscriberFilterWithMultiSIMInfo(…, "MINOR", minor.Source, minor.IMSI)
│           ├── [if "true"]:
│           │   ├── Instance.createInstance(OMX_GetSrvTrxNoRes) { same, countSrvTrxNo index }
│           │   ├── Instance.createInstance(SrvTrxNoMSIMInfo) { SrvStatus=minor.Source }
│           │   ├── minor.SrvTrxNoInfo[] ← SrvTrxNoMSIMInfo
│           │   └── countSrvTrxNo++
├── scan Activities → AA_CHECK_CONFIRMATION with Parameter[0]==param1 → RequestCount = countSrvTrxNo
├── [if AllowWriteLog]: Logger("Response received for OMX_GET_SRV_TRX_NO_MSIM")
└── return "true"
```

---

## §10 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Only POU subscribers are traversed — no COU traversal in this FM. |
| R2 | Subscribers without MultiSIMInfo are skipped (both request and response). |
| R3 | Single OMX call with `sequenceName="AA_TRX_NO_SEQ"` and `amount=N` — one call regardless of SIM count. |
| R4 | Response must distribute `sequenceValue[k+1]` per SIM in traversal order — index alignment is critical. |
| R5 | `SrvTrxTp` comes from param1 (activity parameter); `SrvStatus` comes from `Master.Source` / `Minor.Source`. |
| R6 | After response: update `AA_CHECK_CONFIRMATION.RequestCount = countSrvTrxNo` for matching activity (matched by Parameter[0] == param1). |
| R7 | Resubmit: suppress RequestCount++ when `isActResub`; no PurgePendingRequestsBeforeResubmit. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Index alignment — request/response must traverse SIMs in same order with same PreExecCheck outcome | [HIGH] | Verify no concurrent state mutation can alter PreExecCheck results between request and response |
| param2 is read but never used — dead parameter | [LOW] | Remove or document future intent |
| AA_CHECK_CONFIRMATION write-back will overwrite ALL matching activities if param1 is not unique per process | [MEDIUM] | Verify param1 values are unique per process config; add first-match-only guard if needed |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
