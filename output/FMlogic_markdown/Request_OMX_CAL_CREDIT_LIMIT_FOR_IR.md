# Request_OMX_CAL_CREDIT_LIMIT_FOR_IR

> Calculates and updates IR credit limit per Account — two backend variants (CES/GoldenDB or standard OMX FM); response applies a 3-way credit limit business rule using the IRCreditLimit/CreditGroupAmount global variable, then writes IS_CHANGE_CREDIT_LIMIT to Account.ExtendedInfo.

**Backend:** OMX FM or CES (GoldenDB gate) | **Pattern:** Per-Account fan-out | **forwardChain:** true | **Author:** RS33-BANDIT | **Used in step:** 47

---

## §1 Overview & Purpose

Fetches the IR credit limit from the backend (OMX FM or CES based on `GoldenDB` flag), then applies a business rule to calculate the new `PersonalCreditLimit` for each Account using a tier table loaded from a global variable. Writes `IS_CHANGE_CREDIT_LIMIT` (Y/N) to `Account.ExtendedInfo` to signal downstream steps whether a credit limit change is required.

- Traverses `Account[]` (not Subscriber[]) — per-account fan-out
- Per-account resub guard: skips accounts where `CompletionStatus==2 && ReferenceId==refId` already in Response[]
- GoldenDB gate selects event type: `CES_CAL_CREDIT_LIMIT` vs `OMX_CAL_CREDIT_LIMIT_FOR_IR`
- Fan-in: `RequestCount == Response@length`
- `SendDataToDB` called once after the request loop

> **Response audit unconditional:** Unlike the request audit, the response audit logger fires for every order type (no AllowWriteLog gate).

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_OMX_CAL_CREDIT_LIMIT_FOR_IR.rule` | 88 lines |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_OMX_CAL_CREDIT_LIMIT_FOR_IR.rulefunction` | 84 lines |
| Author | RS33-BANDIT | |
| Priority | 5 | |
| forwardChain | true | |
| Traversal unit | Account[] | Not Subscriber — per-account fan-out |
| Backend (GoldenDB=Y) | `CES_CAL_CREDIT_LIMIT` event | Has `@extId` + `CES` header field |
| Backend (GoldenDB≠Y) | `OMX_CAL_CREDIT_LIMIT_FOR_IR` event | Standard OMX FM event |
| isActResub | `RequestCount > 0 && IsOrderResubmitted` | → PurgePendingRequestsBeforeResubmit; suppresses RequestCount++ |
| Per-account resub guard | `CompletionStatus==2 && ReferenceId==refId` in Response[] | Skips already-successful accounts |
| PreExecCheck builder | `GetXMLForAccount(orderRequest, refId)` | |
| Skip condition | `isSkipped == true` after loop | SkipActivity("4") |
| Post-loop call | `SendDataToDB(orderRequest)` | Once after all events sent |
| Request audit gate | [CONDITIONAL] | Per-event (no AllowWriteLog gate but fires only when event sent) |
| Response audit gate | [UNCONDITIONAL] | Always fires |
| AUDIT_TRACE (request) | `concat("Request Sent for OMX_CAL_CREDIT_LIMIT_FOR_IR:", $refId)` | Per-account refId included |
| AUDIT_TRACE (response) | "Response received for OMX_CAL_CREDIT_LIMIT_FOR_IR" | |
| Fan-in | `RequestCount == Response@length` | Returns "true"/"false" |

---

## §3 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_CAL_CREDIT_LIMIT_FOR_IR"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_CREDIT_LIMIT_FOR_IR"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §4 GoldenDB Gate — Two Backend Variants

**Variant ① GoldenDB="Y" → CES_CAL_CREDIT_LIMIT**
- Condition: `!IsBlankOrStringNull(GoldenDB) && GoldenDB == "Y"`
- Event has `@extId = OMXUtils:generateTrackingID()`
- Adds `<CES>` header ← `OrderData/CES`
- Otherwise same payload fields as Variant ②

**Variant ② GoldenDB≠"Y" → OMX_CAL_CREDIT_LIMIT_FOR_IR**
- Condition: else (blank, null, or not "Y")
- No `@extId`, no `CES` header

---

## §5 Request Payload Field Mapping

```text
createEvent / event
├── @extId           ← OMXUtils:generateTrackingID()                            [CES variant only]
├── JMSPriority      ← $orderRequest/OrderPriority                              [Conditional]
├── JMSCorrelationID ← $orderRequest/OrderData/OMXTrackingId                   [Conditional]
├── OrderID          ← $orderRequest/OrderData/OrderID                          [Conditional]
├── RefID            ← $refId  (Account.RefId)                                  [Always]
├── UserName         ← $orderRequest/OrderData/User                             [Credential-gated: IsEnableUserPass="true"]
├── PassWord         ← $orderRequest/OrderData/Password                         [Credential-gated: IsEnableUserPass="true"]
├── OrderType        ← $orderRequest/OrderData/OrderType                        [Conditional]
├── CES              ← $orderRequest/OrderData/CES                              [CES variant only — Conditional]
├── AccountNo        ← $acct/AccountID                                          [Conditional]
├── CustomerType     ← $orderRequest/OrderData/Customer/CustomerTypeInfo/Type   [Conditional]
├── AccSubType       ← $acct/AccountManagementInfo/AccountSubType               [Conditional]
├── CreditClass      ← $acct/AccountManagementInfo/CreditClass                  [Conditional]
└── CompanyCode      ← $acct/AccountManagementInfo/CompanyCode                  [Conditional]
```

---

## §6 Response — IR Credit Limit 3-Way Calculation

### Step 1 — CreditGroupAmount Global Variable

Global variable: `OMX_OM/BizRules/IRCreditLimit/CreditGroupAmount`

Default value (pipe-delimited):
```text
,A,B,D,E,X,=3000:10000|,C,S,W,=1000:4000|,GA,GB,GC,GD,GE,=3000:10000|
,LA,LB,LC,LD,LE,=3000:10000|,MA,MB,MC,MD,ME,=3000:10000|
,NA,NB,NC,ND,NE,=3000:10000|,RA,RB,RC,RD,RE,=3000:10000
```

Format: `,class1,class2,...,=incAmount:maxAmount` — first matching group wins (break on match).
Match: `String.contains(group, "," + CreditClass + ",")`

### Step 2 — Base Credit Limit

```text
creditLimit = max(acct.AccountManagementInfo.PersonalCreditLimit, activityRes.CreditLimit)
```

### Step 3 — 3-Way Update Rule

| Case | Condition | Action on PersonalCreditLimit | IS_CHANGE_CREDIT_LIMIT |
|------|-----------|-------------------------------|------------------------|
| 1 — At/above max | `maxAmt <= creditLimit` | Set to `creditLimit` (no increase) | N |
| 2 — Increment hits cap | `maxAmt <= creditLimit + incAmt` | Set to `maxAmt` (capped) | Y* |
| 3 — Room to increment | else | Set to `creditLimit + incAmt` | Y |

> **[MEDIUM] Dead branch in Case 2:** The inner `if(maxAmt == creditLimit)` → IS_CHANGE=N inside Case 2 is unreachable. Case 2 only fires when Case 1 (`maxAmt <= creditLimit`) is false, so `maxAmt > creditLimit` is guaranteed in Case 2. The IS_CHANGE=N sub-branch can never execute.

### Step 4 — IS_CHANGE_CREDIT_LIMIT Write (idempotent)

```text
if not(exists(acct/ExtendedInfo[Name="IS_CHANGE_CREDIT_LIMIT"])):
    acct.ExtendedInfo[] ← AccountExtendedInfo { Name="IS_CHANGE_CREDIT_LIMIT", Value="Y"/"N" }
```

---

## §7 Response Concept — OMX_CalCreditLimitForIrRes

```text
createObject / object
├── @extId          ← OMXUtils:generateTrackingID()   [Always]
├── ResponseCode    ← $eventResponse/ResponseCode      [Conditional]
├── ResponseMessage ← $eventResponse/ResponseMsg       [Conditional]
├── CompletionStatus← $eventResponse/CompletionStatus  [Conditional]
├── ReferenceId     ← $eventResponse/RefID             [Conditional]
└── CreditLimit     ← $eventResponse/CreditLimit       [Conditional — backend-returned IR credit limit]
```

---

## §8 Function Dependency Tree

```text
Request_OMX_CAL_CREDIT_LIMIT_FOR_IR (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── [if isActResub]: PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── [Account loop i]:
│   ├── acct = Account[i]; refId = acct.RefId
│   ├── [Resub guard]: scan Response[] for CompletionStatus==2 && ReferenceId==refId → reqSuccess
│   ├── [if !reqSuccess]:
│   │   ├── GetXMLForAccount(orderRequest, refId)   [if PreExecCheck set]
│   │   ├── XPath.execute("/("+PreExecCheck+")", sXML, ...)
│   │   └── [if "true"]:
│   │       ├── [if GoldenDB=="Y"]:
│   │       │   └── Event.createEvent(CES_CAL_CREDIT_LIMIT, XSLT: @extId+CES+AccountNo+...)
│   │       └── [else]:
│   │           └── Event.createEvent(OMX_CAL_CREDIT_LIMIT_FOR_IR, XSLT: AccountNo+...)
│   │       ├── Event.Ext.sendEventImmediate(reqEvent)
│   │       ├── Logger(concat("Request Sent for OMX_CAL_CREDIT_LIMIT_FOR_IR:", refId))
│   │       ├── [if !isActResub]: RequestCount++
│   │       └── isSkipped = false
├── [if !isSkipped]:
│   ├── Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch] HandleActivityException

Response_OMX_CAL_CREDIT_LIMIT_FOR_IR (rulefunction)
├── Instance.createInstance(OMX_CalCreditLimitForIrRes) { extId, ResponseCode, ReferenceId, CreditLimit }
├── currActivity.Response[] ← activityRes
├── acct = Instance.getByExtIdByUri("A:" + OMXTrackingId + ":" + RefID, Account)
├── [if acct != null && AccountManagementInfo != null]:
│   ├── creditGroupAmt = System.getGlobalVariableAsString("IRCreditLimit/CreditGroupAmount", default)
│   ├── tokenize by "|"; for each entry → parse group and incAmt:maxAmt
│   └── [on CreditClass match]:
│       ├── creditLimit = max(PersonalCreditLimit, activityRes.CreditLimit)
│       ├── [Case 1]: PersonalCreditLimit=creditLimit; IS_CHANGE=N
│       ├── [Case 2]: PersonalCreditLimit=maxAmt; IS_CHANGE=Y (dead N branch inside)
│       ├── [Case 3]: PersonalCreditLimit=creditLimit+incAmt; IS_CHANGE=Y
│       ├── [if not exists IS_CHANGE_CREDIT_LIMIT]: acct.ExtendedInfo[] ← AccountExtendedInfo
│       └── break
├── Logger("Response received for OMX_CAL_CREDIT_LIMIT_FOR_IR")   [UNCONDITIONAL]
└── return (RequestCount == Response@length) ? "true" : "false"
```

---

## §9 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-account fan-out (not per-subscriber). Loops `Account[]`. |
| R2 | GoldenDB gate: `OrderData.GoldenDB == "Y"` → CES backend with `@extId` + `CES` header; else OMX FM backend. |
| R3 | Per-account resub guard: skip accounts where `Response[].CompletionStatus==2 && ReferenceId==refId`. |
| R4 | Credit limit rule: load `IRCreditLimit/CreditGroupAmount` global variable. Find group by `CreditClass`. Apply 3-way capping logic. |
| R5 | Write `IS_CHANGE_CREDIT_LIMIT` to `Account.ExtendedInfo` only if not already present (idempotent). |
| R6 | Account lookup in response: `"A:" + OMXTrackingId + ":" + RefID` extId pattern. |
| R7 | `SendDataToDB` called once after the full account loop — not per-account. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Dead branch: `if(maxAmt == creditLimit)` in Case 2 is unreachable — IS_CHANGE=N inside Case 2 never fires | [MEDIUM] | Remove dead branch; document Case 2 intent clearly |
| CreditGroupAmount global variable default is hardcoded in BE source | [MEDIUM] | Externalize to configurable data store; preserve fallback |
| Response audit unconditional — fires for all order types regardless of log suppression setting | [LOW] | Align with AllowWriteLog gating if log volume is a concern |
| AUDIT_TRACE in request includes refId but response audit does not — asymmetric traceability | [LOW] | Add refId to response audit for consistent per-account tracing |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
