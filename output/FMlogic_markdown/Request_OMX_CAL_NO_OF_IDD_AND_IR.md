# Request_OMX_CAL_NO_OF_IDD_AND_IR

## §1 Overview & Purpose

**OMX_CAL_NO_OF_IDD_AND_IR** is a pure in-memory calculation rule. It iterates over every subscriber in the POU hierarchy and counts how many subscribers do **not** yet have an active IDD flag or an active IR/roaming offer. It writes the counts `NumberOfIDD` and `NumberOfIR` back onto each POU concept in BE working memory.

No ESB call, no JMS event, no response handler. Downstream rules use `NumberOfIDD` and `NumberOfIR` to decide whether credit-limit adjustments or SBM provisioning steps are required.

> Found in `Rules/OMConsumers/OMXOM/` (not OMXFM) — OMX orchestration rule; counts are used by validation and pricing steps later in the flow.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXOM.OMX_CAL_NO_OF_IDD_AND_IR` |
| Author | CHAYATORN.P |
| Priority | 5 |
| forwardChain | true |
| Backend | None — in-memory only |
| Fan-in | None — calls `NextActivity()` directly |
| Response handler | None |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — read for subscriber tree; POU fields written |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Provides PreExecCheck and activity progression |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "OMX_CAL_NO_OF_IDD_AND_IR"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_NO_OF_IDD_AND_IR"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Evaluate runtime PreExecCheck via `XPath.execute()`
2. If PreExecCheck fails → `SkipActivity("4")` and exit
3. Log "OmxCalNoOfIddAndIR Started" via `sendEventImmediate(Logger)`
4. Loop `iPOU` over `orderRequest.OrderData.Customer.ParentOU`:
   - Initialise local counters: `noOfIdd = 0`, `noOfIR = 0`
   - Loop `iSub` over `pOu.Subscriber`:
     - Evaluate IDD flag for subscriber → increment `noOfIdd` (or += 0 if already has IDD)
     - Evaluate IR flag for subscriber → increment `noOfIR` (or += 0 if already has IR)
   - Write `pOu.NumberOfIDD = noOfIdd`; write `pOu.NumberOfIR = noOfIR`
5. Call `NextActivity(orderRequest, orderCurrentActivity)`
6. Exception → `HandleActivityException(...)`

> **Design note:** The dead inner loop (commented-out `for (int subOffer ...)` on `SubscriberOffers`) is never executed. It was likely an earlier iteration of the counting logic, replaced by the outer subscriber loop.

---

## §7 IDD / IR Count Logic

### §7.1 IDD Counting

For each `subscriber` in `pOu.Subscriber`:

```text
IDD_HAS_FLAG = boolean(
  $subscriber/SubscriberOffers[
    ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']
    and contains(SocProperties, 'TR_IDD_FLAG=Y')
  ]
)
```

| IDD_HAS_FLAG | Effect |
|---|---|
| `true` — subscriber already has CCBS IDD flag | `noOfIdd += 0` (no change; += 0 is not a no-op — it re-evaluates `noOfIdd` but adds nothing) |
| `false` — subscriber does NOT have IDD flag | `noOfIdd += 1` |

The result `noOfIdd` is the **count of subscribers who need IDD provisioned**.

### §7.2 IR Counting

For each `subscriber` in `pOu.Subscriber`:

```text
IR_HAS_FLAG = boolean(
  $subscriber/SubscriberOffers[
    ExtendedInfo[Name='FE_OR_CCBS' and Value='CCBS']
    and contains(SocProperties, 'TR_IR_FLAG=Y')
  ]
)
OR
IR_HAS_FE_OFFER = boolean(
  $subscriber/SubscriberOffers[
    ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']
    and ExtendedInfo[Name='OFFER_TYPE' and Value='IDD']
  ]
)
```

| IR_HAS_FLAG or IR_HAS_FE_OFFER | Effect |
|---|---|
| `true` — subscriber already has IR (CCBS flag or FE IDD offer) | `noOfIR += 0` |
| `false` — subscriber does NOT have IR | `noOfIR += 1` |

> **FE IDD = IR:** An FE offer with `OFFER_TYPE=IDD` is treated as an IR-equivalent offer. The IR counter counts subscribers needing *both* IDD-type and explicit IR provisioning in the same pass.

The result `noOfIR` is the **count of subscribers who need IR provisioned**.

---

## §8 System & Integration Dependencies

**No external system call.** OMX_CAL_NO_OF_IDD_AND_IR modifies BE working memory only.

### §8.2 Logging Events

| Direction | AUDIT_TRACE |
|-----------|------------|
| [LOG] Logger start | `"OMX-OM OmxCalNoOfIddAndIR Started."` |

> **Note:** There is NO completion log event. The rule fires, writes counters, calls NextActivity(), but does not log completion. This makes it impossible to distinguish "started and completed" from "started and failed" from audit logs alone.

> OPERATION_NAME = `/Rules/OMConsumers/OMXOM/OMX_CAL_NO_OF_IDD_AND_IR` (matches ActivityID — unlike OMX_INJECT_OFFER which uses camelCase)

### §8.4 BE Working Memory Written

| Object | Field Written | Type |
|--------|---------------|------|
| `orderRequest.OrderData.Customer.ParentOU[i]` | `NumberOfIDD` | int — count of subscribers needing IDD |
| `orderRequest.OrderData.Customer.ParentOU[i]` | `NumberOfIR` | int — count of subscribers needing IR |

---

## §9 Object Construction

No objects constructed. Rule writes scalar integer fields to existing POU concepts only.

---

## §11 Audit Logging

| Log | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE |
|-----|-----------|----------------|------------|
| Start | `concat($pid, "_REQ")` | `/Rules/OMConsumers/OMXOM/OMX_CAL_NO_OF_IDD_AND_IR` | `OMX-OM OmxCalNoOfIddAndIR Started.` |
| ~~Complete~~ | — | — | **Missing — no completion log** |

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → COMPLETED | PreExecCheck passes | `NextActivity(orderRequest, orderCurrentActivity)` |
| WAITING → SKIPPED | PreExecCheck fails | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |

---

## §13 Exception Handling

| Condition | Action |
|-----------|--------|
| Any exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §15 Function Dependency Tree

```text
OMX_CAL_NO_OF_IDD_AND_IR
├── XPath.execute(PreExecCheck, sXML, ns)                [PreExecCheck eval]
├── sendEventImmediate(Logger — Start)
├── for iPOU over ParentOU
│   ├── int noOfIdd = 0; int noOfIR = 0
│   └── for iSub over pOu.Subscriber
│       ├── XPath.evalAsBoolean(IDD_FLAG check, sXML, ns)
│       │   └── noOfIdd += (flag ? 0 : 1)
│       ├── XPath.evalAsBoolean(IR_FLAG check, sXML, ns)
│       │   └── noOfIR += (flag ? 0 : 1)
│       └── [DEAD CODE: inner for (int subOffer ...) — commented out]
│   pOu.NumberOfIDD = noOfIdd
│   pOu.NumberOfIR = noOfIR
├── NextActivity(orderRequest, orderCurrentActivity)
└── HandleActivityException(...)                         [catch]
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | For each POU, count subscribers without a CCBS IDD flag → `NumberOfIDD` |
| R2 | For each POU, count subscribers without IR (CCBS flag or FE IDD offer) → `NumberOfIR` |
| R3 | Write both counters to the POU concept in working memory |
| R4 | Evaluate runtime PreExecCheck before executing |
| R5 | No backend call — pure working memory calculation |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Missing completion audit log — cannot confirm success from logs | [MEDIUM] | Add completion log event in migration target |
| `noOfIdd += 0` and `noOfIR += 0` patterns — confusing double-negative logic; "has flag → add 0" | [LOW] | Rewrite as `if (!hasFlag) noOfIdd++` for clarity |
| Dead inner loop (`for subOffer`) — commented-out code increases maintenance confusion | [LOW] | Remove dead code block entirely in migration |
| FE IDD offer counted as IR equivalent — business rule embedded in code, not configuration | [MEDIUM] | Externalise to a rules table or configuration |
| No explicit handling when `pOu.Subscriber` is empty — counters default to 0 (likely correct but unverified) | [LOW] | Add test cases for empty subscriber list |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXOM.OMX_CAL_NO_OF_IDD_AND_IR {
  // author: CHAYATORN.P
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_CAL_NO_OF_IDD_AND_IR";
    orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_NO_OF_IDD_AND_IR";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    // 1. Evaluate PreExecCheck; skip if false
    // 2. Log "OmxCalNoOfIddAndIR Started"
    // 3. Loop iPOU over ParentOU
    //    noOfIdd = 0; noOfIR = 0
    //    Loop iSub over pOu.Subscriber:
    //      IDD check: SubscriberOffers[FE_OR_CCBS='CCBS' and TR_IDD_FLAG=Y]
    //        noOfIdd += (hasIdd ? 0 : 1)   ← double-negative pattern
    //      IR check:  SubscriberOffers[FE_OR_CCBS='CCBS' and TR_IR_FLAG=Y]
    //               OR SubscriberOffers[FE_OR_CCBS='FE' and OFFER_TYPE=IDD]
    //        noOfIR += (hasIr ? 0 : 1)
    //      [DEAD CODE: inner for (int subOffer ...) — fully commented out]
    //    pOu.NumberOfIDD = noOfIdd
    //    pOu.NumberOfIR = noOfIR
    // 4. NextActivity()
    // — No backend call, no fan-in, no response handler —
    // — NO completion log event —
  }
}
```

## §19 Response Message Rule

No response rulefunction exists for `OMX_CAL_NO_OF_IDD_AND_IR`. The rule completes synchronously — it writes IDD/IR counters to POU concepts, calls `NextActivity()`, and returns. No JMS response to wait for.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
