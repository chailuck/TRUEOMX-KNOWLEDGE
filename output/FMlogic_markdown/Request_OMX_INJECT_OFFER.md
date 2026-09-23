# Request_OMX_INJECT_OFFER

## §1 Overview & Purpose

**OMX_INJECT_OFFER** is a pure in-memory enrichment rule. It reads offer specifications from `Activity.Parameter` fields (comma-separated key=value pairs), evaluates the runtime PreExecCheck, then creates and appends `SubscriberOffers` or `AgreementOffers` concept instances to the live order model in BE working memory. No ESB call, no JMS event, no response handler.

Allows ProcessConfig designers to declaratively inject offers at any point in a flow without writing a new rule per offer. Supports both subscriber-level (`level=SUB`) and OU-agreement-level (`level=OU`) injection across POU and COU hierarchies.

> Found in `Rules/OMConsumers/OMXOM/` (not OMXFM) — OMX orchestration rule, not a functional module calling an external system.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXOM.OMX_INJECT_OFFER` |
| Author | DESKTOP-KB4BEG4 |
| Priority | 5 |
| forwardChain | true |
| Backend | None — in-memory only |
| Fan-in | None — calls `NextActivity()` directly |
| Response handler | None |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — read for PreExecCheck + mutated by offer injection |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Source of Parameter strings and PreExecCheck XPath |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "OMX_INJECT_OFFER"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_INJECT_OFFER"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Evaluate runtime PreExecCheck from `orderCurrentActivity.PreExecCheck` via `XPath.execute()`
2. If PreExecCheck fails → `SkipActivity("4")` and exit
3. Log "InjectOffer Started" via `sendEventImmediate(Logger)`
4. If `orderRequest.OrderData.Customer.ParentOU@length == 0` → create default ParentOU + Subscriber
5. Loop `iParam` over all `orderCurrentActivity.Parameter` entries
6. Parse each Parameter csv string → extract: `soc`, `serviceType`, `action`, `offerName`, `level`, `checkDup`, `source`, `accOpenDate`, `mapCugId`, `checkExistingOu`
7. Validate required params (soc, serviceType, action, level) — throw `DATA_ISSUE` if missing
8. Loop POU (`iPOU`):
   - If `level=OU`: dedup check → checkExistingOu guard → create AgreementOffers → append to `POU.Agreement.Offers`
   - Loop POU Subscriber (`ps`): if `level=SUB` → dedup check → create SubscriberOffers → append
   - Loop ChildOU (`iPCOU`): same OU/SUB logic for child hierarchy
9. Call `NextActivity(orderRequest, orderCurrentActivity)`
10. Log "InjectOffer Completed"
11. Exception → `HandleActivityException(...)`

---

## §7 Data Extraction — Parameter String Parsing

Each `Parameter` value is a comma-delimited `key=value` string. Multiple Parameter elements = multiple offers to inject.

| Parameter Key | Required? | Description | Example |
|---------------|-----------|-------------|---------|
| `soc` | [Required] | SOC code | `105645` |
| `serviceType` | [Required] | Service type code | `85` |
| `action` | [Required] | ADD or REMOVE | `ADD` |
| `offerName` | [Required] | Offer name | `PROROAM2S` |
| `level` | [Required] | `SUB` = SubscriberOffers; `OU` = AgreementOffers | `SUB` |
| `checkDup` | [Optional] | 1 = skip if CCBS/CRM offer already exists | `1` |
| `source` | [Optional] | FE_OR_CCBS value; defaults to `"INJECT_OFFER"` | `BRMS` |
| `accOpenDate` | [Optional] | Y = derive EffectiveDate from Account.OpenDate | `Y` |
| `mapCugId` | [Optional] | Y = inject CUG ID ParameterInfo from GROUP_ID | `Y` |
| `checkExistingOu` | [Optional] | Y = skip OU injection if EXISTING_OU=Y | `Y` |

### Examples from POSTPAID_BUY_IR_DATA_PACK

| Step | Parameter | Injects |
|------|-----------|---------|
| 9 (OMX_INJECT_OFFER_IR) | `soc=105645,serviceType=85,action=ADD,offerName=PROROAM2S,level=SUB,source=BRMS` | PROROAM2S IR roaming offer at SUB level |
| 10 (OMX_INJECT_OFFER_IDD) | `soc=41581,serviceType=85,action=ADD,offerName=PROINTL1,level=SUB,source=BRMS` | PROINTL1 IDD offer at SUB level |

---

## §8 System & Integration Dependencies

**No external system call.** OMX_INJECT_OFFER modifies BE working memory only.

### §8.2 Logging Events

| Direction | AUDIT_TRACE |
|-----------|------------|
| [LOG] Logger start | `"OMX-OM InjectOffer Started."` |
| [LOG] Logger complete | `"OMX-OM InjectOffer Completed."` |

> OPERATION_NAME = `/Rules/OMConsumers/OMXOM/OMX_InjectOffer` (camelCase — not the ActivityID)

### §8.4 BE Working Memory Written

| Object | Written |
|--------|---------|
| `POU.Subscriber[].SubscriberOffers[]` | Appended: OfferName, ServiceType, Soc, Action, EffectiveDate, FE_OR_CCBS, optional CUG ID |
| `POU.Agreement.Offers[] / COU.Agreement.Offers[]` | Appended: OfferName, ServiceType, Soc, Action, EffectiveDate, FE_OR_CCBS, optional ACC_OPEN_DATE |
| `orderRequest.OrderData.Customer.ParentOU[0]` | Created if absent (default with RefId from Customer.RefId) |

---

## §9 Object Construction

### §9.1 SubscriberOffers (level=SUB)

```text
SubscriberOffers
├── @extId                ← concat(OMXUtils:generateTrackingID(), ':INJECT_OFFER')   [Always]
├── EffectiveDate         ← $orderRequest/OrderData/EffectiveDate                    [Conditional: string-length > 0]
├── OfferName             ← param offerName                                          [Always]
├── ServiceType           ← param serviceType                                        [Always]
├── Soc                   ← param soc                                                [Always]
├── Action                ← param action (ADD/REMOVE)                                [Always]
├── ParameterInfo/CUG ID  ← OrderData/ExtendedInfo[GROUP_ID]/Value                  [Conditional: mapCugId=Y and GROUP_ID exists]
└── ExtendedInfo/FE_OR_CCBS ← param source (or "INJECT_OFFER" if blank)             [Always]
```

### §9.2 AgreementOffers (level=OU)

```text
AgreementOffers
├── @extId                    ← concat(OMXUtils:generateTrackingID(), ':INJECT_OFFER')  [Always]
├── EffectiveDate             ← Account.OpenDate (compare-date logic)                   [Conditional: accOpenDate=Y]
├── EffectiveDate             ← $orderRequest/OrderData/EffectiveDate                   [Conditional: accOpenDate≠Y and non-empty]
├── OfferName / ServiceType / Soc / Action ← params                                    [Always]
├── ExtendedInfo/FE_OR_CCBS   ← param source (or "INJECT_OFFER")                       [Always]
└── ExtendedInfo/ACC_OPEN_DATE ← "Y" (static)                                          [Conditional: accOpenDate=Y]
```

### §9.3 accOpenDate EffectiveDate Logic (level=OU)

| Condition | EffectiveDate |
|-----------|--------------|
| accOpenDate=Y and Account.OpenDate == today | Account.OpenDate as-is |
| accOpenDate=Y and Account.OpenDate < today | `today + 'T00:00:00+07:00'` |
| accOpenDate≠Y and EffectiveDate non-empty | `$orderRequest/OrderData/EffectiveDate` |
| accOpenDate≠Y and EffectiveDate empty | Field omitted |

---

## §11 Audit Logging

| Log | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE |
|-----|-----------|----------------|------------|
| Start | `concat($pid, "_REQ")` | `/Rules/OMConsumers/OMXOM/OMX_InjectOffer` | `OMX-OM InjectOffer Started.` |
| Complete | `concat($pid, "_RES")` | `/Rules/OMConsumers/OMXOM/OMX_InjectOffer` | `OMX-OM InjectOffer Completed.` |

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → COMPLETED | PreExecCheck passes | `NextActivity(orderRequest, orderCurrentActivity)` |
| WAITING → SKIPPED | PreExecCheck fails | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |

---

## §13 Exception Handling

| Condition | Exception | Action |
|-----------|-----------|--------|
| Missing soc, serviceType, action, or level | `DATA_ISSUE` | `Exception.newException("DATA_ISSUE", ...)` |
| All other errors | Any | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §15 Function Dependency Tree

```text
OMX_INJECT_OFFER
├── XPath.execute(PreExecCheck, sXML, ns)              [PreExecCheck eval]
├── sendEventImmediate(Logger — Start)
├── [if ParentOU.length==0]
│   ├── Instance.createInstance(ParentOU XSLT)
│   └── Instance.createInstance(Subscriber XSLT)
├── for iParam over Activity.Parameter
│   ├── XPath.evalAsString(Parameter[iParam+1])
│   ├── BRMS.IsBlankOrStringNull(paramString)
│   └── String.split(paramString, ",") → tib:tokenize(param, "=")
├── for iPOU over ParentOU
│   ├── [level=OU] dedup + checkExistingOu + Instance.createInstance(AgreementOffers)
│   ├── for ps over POU.Subscriber → [level=SUB] dedup + Instance.createInstance(SubscriberOffers)
│   └── for iPCOU over ChildOU → same OU/SUB logic
├── NextActivity(orderRequest, orderCurrentActivity)
├── sendEventImmediate(Logger — Complete)
└── HandleActivityException(...)                       [catch]
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | Parse Activity.Parameter csv — support multiple Parameter elements |
| R2 | Evaluate runtime PreExecCheck from activity config |
| R3 | Inject at SUB or OU level based on `level` param |
| R4 | Dedup guard: skip if CCBS/CRM offer exists (checkDup=1) |
| R5 | Support POU + COU full hierarchy |
| R6 | accOpenDate logic: compare account open date vs today → choose EffectiveDate |
| R7 | Auto-create ParentOU + Subscriber if absent |
| R8 | No backend call — pure working memory mutation |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Runtime PreExecCheck from activity config — XPath injection possible | [MEDIUM] | Validate at ProcessConfig deployment time |
| Silent skip on dedup (no warning log) | [LOW] | Add debug audit log for skipped injections |
| accOpenDate date comparison is timezone-dependent | [MEDIUM] | Standardise timezone handling in target platform |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXOM.OMX_INJECT_OFFER {
  // author: DESKTOP-KB4BEG4
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_INJECT_OFFER";
    orderRequest.ProcessFlow.NextActivityID == "OMX_INJECT_OFFER";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    // 1. Evaluate PreExecCheck; skip if false
    // 2. Log "InjectOffer Started"
    // 3. Auto-create ParentOU/Subscriber if absent
    // 4. Loop iParam over Activity.Parameter (csv parse: soc,serviceType,action,offerName,level,...)
    // 5. Validate required params (DATA_ISSUE if missing)
    // 6. Loop POU → Subscriber → ChildOU → ChildOU.Subscriber
    //    level=OU: create AgreementOffers (see §9.2 for object fields)
    //    level=SUB: create SubscriberOffers (see §9.1 for object fields)
    //    dedup check via XPath.evalAsBoolean
    // 7. NextActivity() + Log "InjectOffer Completed"
    // — No backend call, no fan-in, no response handler —
  }
}
```

## §19 Response Message Rule

No response rulefunction exists for `OMX_INJECT_OFFER`. The rule completes synchronously within the same rule firing — it mutates working memory, calls `NextActivity()`, and logs completion — all in the `then` block. No JMS response to wait for.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
