# OMX_CAL_CHK_SUM_SUB_LEVEL

> TIBCO BusinessEvents OMXOM Internal Rule — ICC_ID Luhn Checksum Computation at Subscriber Level

**Author:** RS33-BANDIT | **Priority:** 5 | **Forward Chain:** true | **Namespace:** OMXOM (internal, not OMXFM) | **Pattern:** Pure In-Memory Computation — No JMS | **Lines:** 109

---

## §1 — Overview & Purpose

This rule computes the **Luhn checksum** for each subscriber's ICCID (`ICC_ID` ExtendedInfo field) and stores the result as a new `ICC_ID_CHG_SUM` ExtendedInfo entry on the subscriber concept. It is a **pure in-memory computation rule** — it sends no JMS events to any backend system and has no response rulefunction.

> **Pure Computation — No External Call:** Unlike all FM dispatcher rules, this rule performs all work entirely in BE working memory. It reads ICC_ID from each subscriber, computes Luhn(iccId), creates a new SubscriberExtendedInfo concept with Name="ICC_ID_CHG_SUM" and Value=iccId+checksum, and appends it directly to the subscriber's ExtendedInfo array. Completion is via `NextActivity()`, not `GetActivityStatusString + SendDataToDB`.

> **OMXOM namespace (not OMXFM):** This rule lives in `Rules.OMConsumers.OMXOM` rather than `Rules.OMConsumers.OMXFM.Request`, reflecting its role as an internal orchestration step rather than an FM dispatcher. The rule file also has no `Request_` prefix.

| Item | Value |
|------|-------|
| Rule Name | `Rules.OMConsumers.OMXOM.OMX_CAL_CHK_SUM_SUB_LEVEL` |
| Rule File | `Rules/OMConsumers/OMXOM/OMX_CAL_CHK_SUM_SUB_LEVEL.rule` |
| Author | RS33-BANDIT |
| Priority | 5 |
| Forward Chain | true |
| External System | None — pure in-memory computation |
| JMS Event | None dispatched |
| Response Handler | None — no response expected |
| Algorithm | Luhn checksum (`RuleFunctions.Helpers.Luhn(iccId)`) |
| Input | `subscriber.ExtendedInfo[Name="ICC_ID"]/Value` |
| Output | New `SubscriberExtendedInfo` concept: Name="ICC_ID_CHG_SUM", Value=iccId+checksum |
| Completion | `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard priority |
| forwardChain | true | Rule may re-fire on working memory change |
| Rule type | Internal computation — no external dispatch | Mutates BE working memory; no JMS, no response concept |
| Namespace | OMXOM (not OMXFM) | Internal orchestration rule, not a backend FM dispatcher |
| Resubmit handling | `PurgePendingRequestsBeforeResubmit()` | Called but vestigial — no events are ever queued by this rule |
| Completion call | `NextActivity()` | Directly advances to next step — does NOT call GetActivityStatusString or SendDataToDB |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order: customer → POU/COU → subscribers with ExtendedInfo arrays |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity node; Status, PreExecCheck |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Match current process step |
| 2 | `orderCurrentActivity.ActivityID == "OMX_CAL_CHK_SUM_SUB_LEVEL"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_CHK_SUM_SUB_LEVEL"` | Process flow confirmation |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fire if not already processed |

---

## §5 — Execution Flow Diagram

1. Detect resubmit: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. If resubmit → `PurgePendingRequestsBeforeResubmit()` (vestigial — no queued events exist)
3. Read `PROJ` parameter via `GetActivityParamValueFromKey(orderCurrentActivity, "PROJ")` — read but not used in logic (dead read)
4. **Loop A — POU Subscribers**: for each ParentOU[i] → Subscriber[iSub]:
   - Evaluate PreExecCheck via `GetXMLForSubscriber(orderRequest, subRefId)` if PreExecCheck present
   - If chkRes=="true": read `subscriber.ExtendedInfo[Name="ICC_ID"]/Value`
   - If iccId length > 0:
     - Compute `iccIdCheckSum = RuleFunctions.Helpers.Luhn(iccId)`
     - Create `SubscriberExtendedInfo` concept: Name="ICC_ID_CHG_SUM", Value=iccId+iccIdCheckSum
     - Append to `subscriber.ExtendedInfo[]`
     - Send audit log immediately
     - Set `isSkipped = false`
5. **Loop B — COU Subscribers**: for each ParentOU[i] → ChildOU[k] → Subscriber[iSub]:
   - Same logic via `GetXMLForSubscriberInChildOU(orderRequest, subRefId, pOuRefId)`
6. Post-loop:
   - If any subscriber had ICC_ID → `NextActivity(orderRequest, orderCurrentActivity)`
   - If no subscribers had ICC_ID → `SkipActivity(orderRequest, orderCurrentActivity, "4")`
7. catch → `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

> **No backend call, no waiting:** The rule completes synchronously within a single BE engine evaluation. After appending ICC_ID_CHG_SUM to all subscribers' ExtendedInfo arrays, it immediately advances to the next activity via `NextActivity()`.

---

## §6 — Luhn Checksum Algorithm

> The **Luhn algorithm** (ISO/IEC 7812) is the standard checksum for ICCID (SIM card) numbers. It computes a single check digit that is appended to the ICCID base to form the complete 20-digit ICCID. The formula: double every second digit from right, subtract 9 if > 9, sum all digits, check digit = (10 − (sum mod 10)) mod 10.

| Field | Value/Detail |
|-------|-------------|
| Input | `ICC_ID` value from `subscriber.ExtendedInfo[Name="ICC_ID"]/Value` |
| Checksum function | `RuleFunctions.Helpers.Luhn(iccId)` — returns the check digit string |
| Output value | `iccId + iccIdCheckSum` (base ICCID concatenated with check digit) |
| Stored as | ExtendedInfo Name="ICC_ID_CHG_SUM" on the subscriber concept |
| Skip condition | `String.length(iccId) == 0` — subscriber has no ICC_ID → skip, do not compute |
| Standard | ISO/IEC 7812 — used for SIM card (ICCID) validation worldwide |

---

## §7 — Working Memory Mutation (ExtendedInfo Write)

The rule creates a new `SubscriberExtendedInfo` concept instance and appends it to the subscriber's ExtendedInfo array via `Instance.createInstance()`:

| Field | Value/Source |
|-------|-------------|
| `extId` | `concat($iccId, ':ICC_ID_CHG_SUM', $subscriber/@extId)` — unique per subscriber |
| `Name` | `"ICC_ID_CHG_SUM"` (static) |
| `Value` | `iccId + iccIdCheckSum` — set directly in BE code after concept creation (not in XSLT) |
| Append target | `subscriber.ExtendedInfo[subscriber.ExtendedInfo@length] = iccIdChgSum` |
| Concept type | `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` |

> **In-memory only:** This mutation is written to the BE working memory (`orderRequest` concept graph). It is not persisted to a database by this rule. Downstream FMs must read it within the same order flow.

---

## §8 — System & Integration Dependencies

### §8.1 External System Dependencies

**None.** This rule makes no calls to any external system (NAS, ASRM, CCBS, OMX, etc.).

### §8.2 Audit Log (only outbound event)

| Direction | Event | Channel | Purpose |
|-----------|-------|---------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | ESB Audit Log | Trace that ICC_ID_CHG_SUM was computed for the subscriber |

### §8.3 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `subscriber.ExtendedInfo[Name="ICC_ID"]/Value` | Read | Source ICCID for checksum |
| `subscriber.ExtendedInfo[]` | Write (append) | ICC_ID_CHG_SUM appended here for POU and COU subscribers |
| `orderCurrentActivity.Status` | Read | WAITING gate |

### §8.4 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Gate for payload logging in audit |

---

## §9 — PROJ Parameter: Dead Read

> **Dead read (unused variable):** The rule reads the `PROJ` activity parameter via `GetActivityParamValueFromKey(orderCurrentActivity, "PROJ")` into `String paramValue`, but `paramValue` is never referenced anywhere in the rule body. This is a copy-paste artifact from the offer-level variant (`OMX_CAL_CHK_SUM`) where PROJ="RIO_SWAP" changes the ICC_ID source.

| Parameter | Read? | Used? | Effect |
|-----------|-------|-------|--------|
| PROJ | Yes | **No — dead read** | None. Variable `paramValue` is set but never referenced in the logic. |

---

## §10 — Loop Order: POU Before COU

| Order | Context | PreExecCheck Helper |
|-------|---------|---------------------|
| 1st | POU Subscribers: ParentOU[i] → Subscriber[iSub] | `GetXMLForSubscriber(orderRequest, subRefId)` |
| 2nd | COU Subscribers: ParentOU[i] → ChildOU[k] → Subscriber[iSub] | `GetXMLForSubscriberInChildOU(orderRequest, subRefId, pOuRefId)` |

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| PROCESS_ID | `concat(System.nanoTime(), "_REQ")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `"OMX_CAL_CHK_SUM_SUB_LEVEL"` (static) |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `"Request Sent for OMX_CAL_CHK_SUM_SUB_LEVEL"` (static — no RefId) |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | `<ns:ServicePayload/>` (empty — gated on WritePayload="true") |
| Send method | `Event.Ext.sendEventImmediate()` (synchronous) |

---

## §12 — Activity Status Management

> **Unique completion pattern:** Unlike FM dispatcher rules that call `GetActivityStatusString("1", false) + SendDataToDB()`, this rule calls `NextActivity()` directly. This bypasses the ACTIVE status entirely and advances the process flow immediately.

| State | Trigger | Call |
|-------|---------|------|
| [NEXT] | At least one subscriber had ICC_ID (isSkipped=false) | `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` |
| [SKIPPED] | No subscriber had any ICC_ID (isSkipped=true) | `RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")` |

---

## §13 — Exception / Error Handling

| Exception | Handler |
|-----------|---------|
| `Exception ae` (catch-all) | `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|----------|--------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)` | void | Called on resubmit — vestigial; no events queued by this rule |
| `GetActivityParamValueFromKey(orderCurrentActivity, "PROJ")` | String | Reads PROJ parameter — dead read; result unused |
| `GetXMLForSubscriber(orderRequest, subRefId)` | String XML | Serializes POU subscriber for PreExecCheck XPath evaluation |
| `GetXMLForSubscriberInChildOU(orderRequest, subRefId, pOuRefId)` | String XML | Serializes COU subscriber for PreExecCheck XPath evaluation |
| `Luhn(iccId)` | String | Computes Luhn check digit for the given ICCID string |
| `NextActivity(orderRequest, orderCurrentActivity)` | void | Advances order flow to the next step immediately |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | void | Marks activity as SKIPPED with reason 4 |
| `HandleActivityException(...)` | void | Centralized exception handler |

---

## §15 — Function Dependency Tree

```text
OMX_CAL_CHK_SUM_SUB_LEVEL (BE rule — OMXOM namespace)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)  [if resubmit, vestigial]
├── GetActivityParamValueFromKey(orderCurrentActivity, "PROJ")                        [dead read]
│
├── [Loop A — POU Subscribers]
│   ├── GetXMLForSubscriber(orderRequest, subRefId)
│   ├── XPath.execute("/("+chkXPath+")", sXML, ...)                                  [PreExecCheck]
│   ├── XPath.evalAsString("$subscriber/ExtendedInfo[Name='ICC_ID']/Value")           [read ICC_ID]
│   ├── RuleFunctions.Helpers.Luhn(iccId)                                             [compute checksum]
│   ├── Instance.createInstance("xslt://{{/Concepts/.../SubscriberExtendedInfo}}")
│   │   └── [XSLT: extId=concat(iccId,':ICC_ID_CHG_SUM',subscriber/@extId); Name='ICC_ID_CHG_SUM']
│   ├── iccIdChgSum.Value = iccId + iccIdCheckSum                                     [set value in BE]
│   ├── subscriber.ExtendedInfo[...] = iccIdChgSum                                    [append to array]
│   ├── Event.createEvent("xslt://{{/Events/.../Logger}}...")
│   └── Event.Ext.sendEventImmediate(auditEvent)
│
├── [Loop B — COU Subscribers]
│   ├── GetXMLForSubscriberInChildOU(orderRequest, subRefId, pOuRefId)
│   └── [same Luhn + ExtendedInfo append + audit pattern]
│
├── NextActivity(orderRequest, orderCurrentActivity)                                   [if !isSkipped]
└── SkipActivity(orderRequest, orderCurrentActivity, "4")                             [if isSkipped]
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — For each subscriber (POU then COU): read ICC_ID from ExtendedInfo; if present, compute Luhn checksum and store ICC_ID_CHG_SUM
- **R2** — ICC_ID_CHG_SUM value = full ICCID string with check digit appended (iccId + Luhn(iccId))
- **R3** — Skip subscriber silently if ICC_ID is absent or empty (do not fail)
- **R4** — Skip entire activity if no subscriber has any ICC_ID
- **R5** — PreExecCheck gate applies per subscriber
- **R6** — PROJ parameter: read but ignored — remove this dead read in migration

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| PROJ parameter dead read — may confuse future maintainers | [MEDIUM] | Remove `GetActivityParamValueFromKey("PROJ")` and `paramValue` variable in migration |
| `PurgePendingRequestsBeforeResubmit()` called unnecessarily | [LOW] | Remove vestigial resubmit purge call |
| ICC_ID_CHG_SUM is in-memory only — not persisted by this rule | [LOW] | Ensure migration architecture guarantees working memory persistence |
| Incorrect Luhn implementation would silently produce wrong ICCIDs | [MEDIUM] | Unit-test `Luhn()` against known ICCID examples; verify against ISO 7812 |

### Comparison: OMX_CAL_CHK_SUM vs OMX_CAL_CHK_SUM_SUB_LEVEL

| Aspect | OMX_CAL_CHK_SUM (OMXFM) | OMX_CAL_CHK_SUM_SUB_LEVEL (OMXOM) |
|--------|-------------------------|-------------------------------------|
| Namespace | OMXFM (Request) | OMXOM (internal) |
| Granularity | Subscriber-Offer (SubscriberOffers[].ExtendedInfo) | Subscriber (Subscriber.ExtendedInfo) |
| PROJ parameter | Used: "RIO_SWAP" → read ICC_ID from subscriber | Read but ignored (dead) |
| FE_OR_CCBS filter | Applied per offer | Not applied (subscriber level) |
| Output type | SubscriberExtendedInfo or SubscriberOffersExtendedInfo | SubscriberExtendedInfo only |
| Completion | NextActivity() | NextActivity() |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author RS33-BANDIT
 */
rule Rules.OMConsumers.OMXOM.OMX_CAL_CHK_SUM_SUB_LEVEL {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "OMX_CAL_CHK_SUM_SUB_LEVEL";
        orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_CHK_SUM_SUB_LEVEL";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub=(orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
        try {
            if(isActResub) {
                RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
                // vestigial — no events queued by this rule
            }
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
                orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
            String projName = "PROJ";
            String paramValue = RuleFunctions.Helpers.GetActivityParamValueFromKey(orderCurrentActivity, projName);
            // DEAD READ: paramValue set here but never used below

            boolean isSkipped = true;
            int pOuLen = orderRequest.OrderData.Customer.ParentOU@length;
            String chkXPath = nextAct.PreExecCheck;

            // Loop A: POU Subscribers
            for(int i=0; i<pOuLen; i++) {
                String pOuRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;
                for(int iSub=0; iSub<..ParentOU[i].Subscriber@length; iSub++) {
                    Concepts.OrderRequest.OrderElements.Subscriber subscriber = ..ParentOU[i].Subscriber[iSub];
                    String subRefId = subscriber.RefId;

                    String chkRes = "true";
                    if(String.length(nextAct.PreExecCheck)>0){
                        String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, subRefId);
                        chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=...");
                    }
                    if(String.equals(chkRes,"true")){
                        String iccId = XPath.evalAsString("xpath://$subscriber/ExtendedInfo[Name='ICC_ID']/Value");
                        if(String.length(iccId)>0) {
                            String iccIdCheckSum = RuleFunctions.Helpers.Luhn(iccId);
                            SubscriberExtendedInfo iccIdChgSum = Instance.createInstance(
                                "xslt://{{/Concepts/.../SubscriberExtendedInfo}}");
                                /* XSLT: extId=concat(iccId,':ICC_ID_CHG_SUM',subscriber/@extId); Name='ICC_ID_CHG_SUM' */
                            iccIdChgSum.Value = iccId + iccIdCheckSum;
                            subscriber.ExtendedInfo[subscriber.ExtendedInfo@length] = iccIdChgSum;
                            long pid = System.nanoTime();
                            Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{/Events/.../Logger}}"));
                            /* audit: OPERATION_NAME="OMX_CAL_CHK_SUM_SUB_LEVEL",
                               AUDIT_TRACE="Request Sent for OMX_CAL_CHK_SUM_SUB_LEVEL" */
                            isSkipped = false;
                        }
                    }
                }
                // Loop B: COU Subscribers — same Luhn pattern via GetXMLForSubscriberInChildOU
                int iCOULen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU@length;
                for(int k=0; k<iCOULen; k++) {
                    for(int iSub=0; iSub<..ChildOU[k].Subscriber@length; iSub++) {
                        // same Luhn compute + ExtendedInfo append
                    }
                }
            }
            if(!isSkipped) {
                RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity);
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch (Exception ae) {
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
