# Request_AA_CHECK_CONFIRMATION

> TIBCO BusinessEvents FM Logic — AA Async Callback Listener & Process State Guard (Unique Pattern — No Outbound JMS)

**Request Author:** mranade-T420 | **Response Author:** mranade-T420 | **Priority:** 5 (both) | **Pattern:** Async Callback — No outbound JMS dispatch | **Lines:** 81 (request) + 344 (response)

---

## §1 — Overview & Purpose

> **Unique pattern — not a dispatcher:** Unlike every other FM in this process, `Request_AA_CONFIRMATION` sends **no JMS events**. It is a process state guard that checks whether a prior AA activation step has already reached `SUCCESS` status. The actual work — receiving AA callbacks from the network — is done entirely by the companion response rule `Response_AA_CONFIRMATION`, which is a reverse-lookup event-driven BE rule (not a rulefunction) with an empty `when` block.

AA (Activation Agent) sends asynchronous push callbacks bearing a `SrvTxnNo` when network provisioning completes. This pair of rules captures those callbacks, resolves the order, updates per-subscriber `NETWORK_STATUS`, and advances the activity when all expected confirmations are received.

| Item | Request Rule | Response Rule |
|------|-------------|---------------|
| File | `Request_AA_CONFIRMATION.rule` | `Response_AA_CONFIRMATION.rule` |
| ActivityID | `AA_CHECK_CONFIRMATION` | n/a (event-driven, empty WHEN) |
| Rule type | Orchestration guard — no outbound JMS | Async callback handler |
| Trigger | Normal process flow (Status=WAITING) | `Events.OMConsumers.OMXFM.Response.AA_CONFIRMATION` — any arriving event |
| Outbound events | None | Audit Logger (conditional) |
| Pattern | Scan ProcessFlow.Activities for prior AA success | SrvTxnNo → OMX_GetSrvTrxNoRes → OMXTrackingId → OrderRequest (reverse lookup) |

---

## §2 — Request Rule Logic (Request_AA_CONFIRMATION)

### §2.1 Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Current process step match |
| 2 | `orderCurrentActivity.ActivityID == "AA_CHECK_CONFIRMATION"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "AA_CHECK_CONFIRMATION"` | Process flow confirmation |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fire once |

### §2.2 Execution Logic

1. **PreExecCheck** (order-level, not subscriber-level): if `PreExecCheck` is set → serialize full orderRequest → evaluate XPath → if false → `SkipActivity("4")`
2. **Scan ProcessFlow.Activities**: iterate all activities, looking for any that:
   - Has an ActivityID in the known AA list (see §2.3)
   - Has `Parameter[0]` matching `orderCurrentActivity.Parameter[0]` (same command key)
   - Has `Status == "SUCCESS"`
   - If found → `isSkipped = false`
3. If `isSkipped`: `SkipActivity("4")`
4. If NOT skipped: set status to `GetOrderStatusString(1)` + `SendDataToDB()`
5. Then check if all responses already received: `RequestCount > 0 AND Response@length == RequestCount`:
   - If "UPDATE_NETWORK_STATUS" in Parameters: NetworkStatus=2 → SaveToDB → NetworkStatus=5
   - Set `ResponseMessage = "Received AA Confirmation for all requests."`
   - Call `SkipActivity("2")` — skipped with reason "2" (already confirmed)

### §2.3 Recognized Prior AA Activities

| ActivityID | Description |
|-----------|-------------|
| `AA_ACTIVATE_SUBS` | Standard AA activation |
| `AA_PREPAID_PROVISIONING` | Prepaid provisioning |
| `AA_ACTIVATE_SUBS_AS` | Activation (AS variant) |
| `SBM_PREPAID_PROVISIONING` | SBM prepaid provisioning |
| `AA_UPDATE_SHARE_PLAN_PROFILE` | Share plan profile update |
| `AA_ACTIVATE_SUBS_MSIM` | MultiSIM activation |
| `AA_OMXN_ACTIVATE_SUBS` | OMXN variant activation |
| `SBM_OTA_PROVISIONING` | OTA provisioning |
| `AA_ACTIVATE_SUBS_MIGRATE_MSIM` | MultiSIM migration activation |

### §2.4 Parameter[0] Matching

The match uses `Parameter[0]` — the first parameter of both activities must be equal (typically the transaction type code, e.g. "NAC"). This ensures that if multiple AA activities exist in the process flow, only the one with the matching command is checked.

---

## §3 — Response Rule Logic (Response_AA_CONFIRMATION) — Async Callback Handler

### §3.1 Trigger

> The response rule has an **empty WHEN block** — it fires whenever an `Events.OMConsumers.OMXFM.Response.AA_CONFIRMATION` event arrives in the engine's working memory, regardless of order state. The event carries a `SrvTxnNo` used to locate the order.

### §3.2 Reverse Lookup Chain

```text
aaConfRes.SrvTxnNo
  → Instance.getByExtIdByUri("OMX_GET_SRV_TRX_NO:"+SrvTxnNo, "/Concepts/FM/Response/OMX_GetSrvTrxNoRes")
       → activityRes.OMXTrackingId  (or srv_trx_tp_cd)
  → [if activityRes==null] Instance.getByExtIdByUri(SrvTxnNo, "/Concepts/FM/Response/AA_ActivateSubscriberRes")
       → activityResAAActSub.OMXTrackingId
  → trxId = OMXTrackingId
  → Instance.getByExtIdByUri(trxId, "/Concepts/OrderRequest/OrderRequest")
       → orderRequest
```

**Fallback reconstruction:** If `dynamicVariable.IsCreateAAOrderFromPayload == true` and `orderRequest == null`, the rule tries to reconstruct the order from `aaConfRes.orderPayload` XML and increments the order count via `SetOrderCount(1)`.

### §3.3 Response Concept (AA_ConfirmationRes)

```text
createObject (AA_ConfirmationRes)
└── @extId           ← ns:generateTrackingID()        [Always]
    SrvTxnNo         ← $aaConfRes/SrvTxnNo            [Conditional]
    authCode         ← $aaConfRes/authCode            [Conditional]
    stsCode          ← $aaConfRes/stsCode             [Conditional]
    stsMsg           ← $aaConfRes/stsMsg              [Conditional]
    completeDatetime ← $aaConfRes/completeDatetime    [Conditional]
```

### §3.4 Three Status Code Paths

| stsCode | Meaning | Actions |
|---------|---------|---------|
| CS — Complete Success | Network provisioning succeeded | Append aaRes to Activities[AA_CHECK_CONFIRMATION].Response[]; fan-in check; if complete → SkipActivity("2"); update NETWORK_STATUS="COMPLETED"; delete activityRes |
| CE — Complete Error | Network provisioning failed | Update NETWORK_STATUS="FAILED" on matching subscriber; no SkipActivity |
| CC — Cancel Confirmed | Order cancelled from network | Append aaRes to Response[]; set OrderStatus=GetOrderStatusString(8); SendDataToDB; delete activityRes |

### §3.5 Subscriber Matching (SrvTrxNo)

| Check | Logic |
|-------|-------|
| Is MultiSIM? | `exists(SubscriberOffers[SocProperties contains "TR_MULTISIM_IND=RES" or "TR_MULTISIM_IND=RCM"]) OR exists(MultiSIMInfo)` |
| Non-MultiSIM match | `pSub.SrvTrxNoInfo[0].SrvTrxNo == activityRes.srvTrxNo` |
| MultiSIM match | `MultiSIMInfo/Master/SrvTrxNoInfo[SrvTrxTp=cmd]/SrvTrxNo == aaRes.SrvTxnNo` OR `.../Minor/...` |

### §3.6 NETWORK_STATUS Enrichment

| Case | Action | Value | extId |
|------|--------|-------|-------|
| CS + NETWORK_STATUS absent | Create new ExtendedInfo | `"COMPLETED"` | `concat(SrvTxnNo, ":NETWORK_STATUS")` |
| CS + NETWORK_STATUS present | Update existing | `GetOrderStatusString(2)` | — |
| CE + NETWORK_STATUS absent | Create new ExtendedInfo | `"FAILED"` | `concat(SrvTxnNo, ":NETWORK_STATUS")` |
| CE + NETWORK_STATUS present | Update existing | `GetOrderStatusString(3)` | — |

> **Inconsistency note:** CS create path uses static `"COMPLETED"` but update path uses `GetOrderStatusString(2)`. These may produce different string values.

---

## §4 — Fan-In / Completion Logic

> Fan-in is managed by the response rule (not a rulefunction call). When a CS callback arrives and is appended to the activity's Response[], the rule checks: `Activities[i].RequestCount > 0 AND Status == "ACTIVE" AND RequestCount == Response@length`. If true → completion sequence runs.

| Completion Condition | Action |
|---------------------|--------|
| `RequestCount > 0 AND Status="ACTIVE" AND RequestCount == Response@length` | 1. If UPDATE_NETWORK_STATUS param: NetworkStatus=2 → SaveToDB → NetworkStatus=5 / 2. Set ResponseMessage = "Received AA Confirmation for all requests." / 3. `SkipActivity("2")` |

**RequestCount source:** Set by the prior AA_ACTIVATE_SUBS (or equivalent) activity — not by this rule. This rule only reads it to check completion.

---

## §5 — Audit Logging

> **Conditional audit (same gate as INTX):** Audit is gated on `RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)`.

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(pid, "-", aaRes/stsCode, "_RES")` — includes status code in process ID |
| OPERATION_NAME | `"AA_CONFIRMATION"` (static) |
| TARGET_SYSTEM | `globalVariables/OMX_COMMON/Component_Name/OMX_ESB` (not OMX_FM) |
| AUDIT_TRACE | `"ESB AA Notify Service received request"` (static) |
| payload | `copy-of $aaConfRes` (always — no WritePayload gate) |

---

## §15 — Function Dependency Tree

```text
Request_AA_CONFIRMATION (BE rule — no outbound JMS)
├── Instance.getByExtIdByUri(NextActivityName, Activity)
├── XPath.execute(PreExecCheck, Instance.serializeUsingDefaults(orderRequest))
├── Loop ProcessFlow.Activities
│   └── Match by ActivityID (9 types), Parameter[0], Status="SUCCESS"
├── GetOrderStatusString(1)
├── SendDataToDB(orderRequest)
├── [if complete] Loop Parameters for "UPDATE_NETWORK_STATUS"
│   ├── GetOrderStatusString(2) / GetOrderStatusString(5)
│   └── SendDataToDB(orderRequest)
├── SkipActivity("2") or SkipActivity("4")
└── HandleActivityException(...)

Response_AA_CONFIRMATION (BE rule — async callback, empty WHEN)
├── Instance.getByExtIdByUri("OMX_GET_SRV_TRX_NO:"+SrvTxnNo, OMX_GetSrvTrxNoRes)
├── [if null] Instance.getByExtIdByUri(SrvTxnNo, AA_ActivateSubscriberRes)
├── [if null + IsCreateAAOrderFromPayload] Instance.createInstanceFromXML(orderPayload)
│   └── EngineManagement.SetOrderCount(1)
├── Instance.getByExtIdByUri(trxId, OrderRequest)
├── Instance.createInstance(AA_ConfirmationRes XSLT)
│
├── [if stsCode="CS"]
│   ├── Loop Activities: find AA_CHECK_CONFIRMATION + matching Parameter + srv_trx_tp_cd
│   │   ├── Append aaRes to Activity.Response[]
│   │   └── [if complete] SkipActivity("2")
│   ├── Loop POU Subscribers: match SrvTrxNo, create/update NETWORK_STATUS ExtendedInfo
│   ├── Loop COU Subscribers: same
│   └── Instance.deleteInstance(activityRes or activityResAAActSub)
│
├── [if stsCode="CE"]
│   ├── Loop POU Subscribers: match SrvTrxNo, create/update NETWORK_STATUS ExtendedInfo
│   └── Loop COU Subscribers: same
│
├── [if stsCode="CC"]
│   ├── Loop Activities: find AA_CHECK_CONFIRMATION + match, append aaRes
│   ├── OrderStatus = GetOrderStatusString(8) [CANCELLED]
│   ├── SendDataToDB(orderRequest)
│   └── Instance.deleteInstance(activityRes or activityResAAActSub)
│
├── AllowWriteLog(OrderType) → Event.Ext.sendEventImmediate(audit Logger)
└── [cleanup] if aaRes!=null and checkActivity="false" → Instance.deleteInstance(aaRes)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Request rule: no outbound calls. Checks if a qualifying prior AA activity reached SUCCESS status with matching Parameter[0]
- **R2** — Response rule is event-driven (empty WHEN) — any arriving AA_CONFIRMATION event triggers it; SrvTxnNo is used to locate the order
- **R3** — Three stsCode paths: CS (success + NETWORK_STATUS=COMPLETED), CE (failure + NETWORK_STATUS=FAILED), CC (cancel + OrderStatus=8)
- **R4** — Fan-in is count-based: RequestCount == Response@length (RequestCount is set by prior AA activity)
- **R5** — If UPDATE_NETWORK_STATUS param present: network status updates to 2 then 5 on completion
- **R6** — MultiSIM subscribers matched via MultiSIMInfo Master/Minor SrvTrxNoInfo chains
- **R7** — Audit conditional on AllowWriteLog(OrderType); TARGET_SYSTEM=OMX_ESB (not OMX_FM)
- **R8** — Order reconstruction from aaConfRes.orderPayload possible when IsCreateAAOrderFromPayload=true

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Response rule has empty WHEN — fires on every AA_CONFIRMATION event globally; relies on SrvTxnNo lookup to find the right order | [HIGH] | Ensure OMX_GetSrvTrxNoRes concepts are always created and deleted correctly; race conditions possible if lookup is slow |
| Order reconstruction from orderPayload XML bypasses normal order loading — state may be stale | [HIGH] | Monitor IsCreateAAOrderFromPayload behavior; ensure this path is tested thoroughly |
| CS create path uses static "COMPLETED" but update path uses GetOrderStatusString(2) — inconsistent values | [MEDIUM] | Standardize NETWORK_STATUS value |
| CE path sets NETWORK_STATUS but does NOT call SkipActivity — activity remains in current state indefinitely on network failure | [MEDIUM] | Add explicit failure handling; document CE recovery path |
| RequestCount set by prior activity — if prior activity count mismatches actual callbacks, completion never fires | [MEDIUM] | Trace and document how RequestCount is set in AA_ACTIVATE_SUBS |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
