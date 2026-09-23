# Request_CCBS_UPDATE_BILLING_ARRANGEMENT

> Updates billing arrangement for an account — sets L3BillFormat, L9BillLang, and L9SplitParam based on order type and cancel type.

> **Note:** `logicalDateRes`/`logicalDateVal` loaded in THEN block but not used in XSLT — do not replicate in migration. Old RequestCount fan-in code is commented out; uses IntraActivitySequencing fan-in only.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPDATE_BILLING_ARRANGEMENT` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | CCBS_UPDATE_BILLING_ARRANGEMENT |
| Backend | CCBS — UpdateBillingArrangement endpoint |
| Pattern | IntraActivitySequencing |
| Iteration Scope | Account array |
| Activity Parameters | `ALT_CES` (alternative CES routing), `L9SPLITPARAM` (L9 split override) |
| Credentials | Gated by `IsEnableUserPass='true'` |
| Response Concept | Concepts.FM.Response.CCBS_UpdateBillingArrangementRes |

---

## §4 — Rule Conditions (WHEN)

1. `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
2. `orderCurrentActivity.ActivityID == "CCBS_UPDATE_BILLING_ARRANGEMENT"`
3. `orderRequest.ProcessFlow.NextActivityID == "CCBS_UPDATE_BILLING_ARRANGEMENT"`
4. `orderCurrentActivity.Status == "WAITING"`

---

## §5 — Execution Flow

1. Load `logicalDateRes` / `logicalDateVal` — **unused in XSLT** (do not replicate)
2. Load `nextAct` concept for PreExecCheck expression
3. Read activity parameters: `ALT_CES`, `L9SPLITPARAM`
4. If `RequestCount > 0 && IsOrderResubmitted` → `PurgePendingRequestsBeforeResubmit`
5. Detect OrderType=11 → set `isL9ResumeOrder="true"`
6. Iterate `Customer.Account[i]`; evaluate PreExecCheck via `GetXMLForAccount`
7. For passing accounts: build event, `Event.assertEvent`, `ActionRequestEvent`; set `isSkipped=false`
8. After loop: if `!isSkipped` → `SendFirstRequestEvent` + IN_PROGRESS; else → `SkipActivity("4")`

---

## §7 — L9SplitParam Decision Logic

| Condition | L9SplitParam Value |
|-----------|-------------------|
| `isL9ResumeOrder != "true"` AND `CANCEL_TYPE = 'endbill'` | `"FFGB"` (hardcoded) |
| `isL9ResumeOrder != "true"` AND other `CANCEL_TYPE` | `"SIFN"` (hardcoded) |
| `string-length($l9splitparam) > 0` (L9SPLITPARAM activity param) | Value from `L9SPLITPARAM` parameter |
| `isL9ResumeOrder = "true"` AND account `L9SplitParam = 'SIFN'` | `"CLEAR"` (resets split) |
| `isL9ResumeOrder = "true"` AND other L9SplitParam | `$account/ExtendedInfo[Name="L9SplitParam"]/Value` |

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

| OrderType | Description | Effect |
|-----------|-------------|--------|
| "11" | POSTPAID_L9_RESUME | `isL9ResumeOrder="true"` → reads L9SplitParam from account ExtendedInfo; 'SIFN' → 'CLEAR' |
| Other | Standard | L9SplitParam set to "FFGB" or "SIFN" based on `CANCEL_TYPE` |

### §8.5 ExtendedInfo Fields

| Key | Scope | Usage | Required |
|-----|-------|-------|----------|
| `ALT_CES` | OrderData | If activity param ALT_CES=Y → use as CES routing override | Optional |
| `FINAL_BILL` | OrderData | Value='N' → L3BillFormat forced to "PS" | Optional |
| `CANCEL_TYPE` | OrderData | 'endbill' → L9SplitParam="FFGB"; else "SIFN" | Optional |
| `L9SplitParam` | Account | OrderType=11 only — 'SIFN' → 'CLEAR'; else use as-is | Optional (L9Resume only) |

---

## §9 — Payload Build

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                     [Always]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId           [Always]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID                 [Always]
    ├── UserName                 ← $orderRequest/OrderData/User                    [Credential-gated: IsEnableUserPass='true']
    ├── PassWord                 ← $orderRequest/OrderData/Password                [Credential-gated: IsEnableUserPass='true']
    ├── OrderType                ← $orderRequest/OrderData/OrderType               [Conditional: if exists]
    ├── CES                      ← ExtendedInfo[Name='ALT_CES']/Value              [Conditional: altParam='Y' AND ALT_CES !='']
    ├── CES                      ← $orderRequest/OrderData/CES                     [Conditional: otherwise]
    └── payload
        └── ns1:UpdateBillingArrangementRequest
            ├── ns3:BillingArrangementIdInfo
            │   ├── ns3:BillingArrangementId ← $account/BillingArrangementId      [Conditional: exists AND > 0]
            │   └── ns3:BillingArrangementId ← $account/AccountID                 [Conditional: fallback if AccountID exists]
            ├── ns4:BillingArrangementBillInfo
            │   ├── ns4:L3BillFormat         ← "PS"                               [Conditional: FINAL_BILL='N']
            │   ├── ns4:L3BillFormat         ← $account/BillingArrangementBillInfo/BillFormat  [Conditional: otherwise, if exists]
            │   ├── ns4:L9BillLang           ← $account/BillingArrangementBillInfo/BillLanguage [Conditional: if exists]
            │   ├── ns4:L9SplitParam         ← "FFGB"                             [Conditional: !L9Resume AND CANCEL_TYPE='endbill']
            │   ├── ns4:L9SplitParam         ← "SIFN"                             [Conditional: !L9Resume AND other]
            │   ├── ns4:L9SplitParam         ← $l9splitparam                      [Conditional: L9SPLITPARAM param set]
            │   ├── ns4:L9SplitParam         ← "CLEAR"                            [Conditional: L9Resume AND account='SIFN']
            │   └── ns4:L9SplitParam         ← $account/ExtendedInfo[L9SplitParam]/Value [Conditional: L9Resume other]
            └── ns2:ActivityInfo
                ├── ns2:ActivityReason       ← AccountActivityInfo/ActivityReason or "CREQ" [Always]
                └── ns2:UserText             ← $account/AccountActivityInfo/UserText        [Conditional: if exists]
```

---

## §15 — Function Dependency Tree

```text
Request_CCBS_UPDATE_BILLING_ARRANGEMENT
├── Instance.getByExtIdByUri("LogicalDate", ...)         ← UNUSED IN XSLT
├── Instance.getByExtIdByUri(NextActivityName, ...)      ← nextAct
├── GetActivityParameterValueFromKey(activity, "ALT_CES")
├── GetActivityParameterValueFromKey(activity, "L9SPLITPARAM")
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── GetXMLForAccount(orderRequest, account.RefId)
├── XPath.execute("/(preExecCheck)", sXML, ...)
├── Event.assertEvent(reqEvent)
├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(req, activity, "4")
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 — Migration Notes

| # | Requirement / Risk | Severity |
|---|---|---|
| R1 | Implement all L9SplitParam branches (5 cases — see §7) | [HIGH] |
| R2 | BillingArrangementId fallback to AccountID when absent or 0 | [HIGH] |
| R3 | FINAL_BILL=N forces L3BillFormat="PS" | [MEDIUM] |
| R4 | ALT_CES activity parameter overrides CES routing | [MEDIUM] |
| R5 | ActivityReason defaults to "CREQ" when absent | [MEDIUM] |
| [DEAD] | Remove `logicalDateRes`/`logicalDateVal` loading (not used) | [LOW] |
| R6 | Old RequestCount fan-in commented out — use IntraActivitySequencing only | [LOW] |

---

## §19 — Response Message Rule

### §19.1 Overview

Creates `CCBS_UpdateBillingArrangementRes` with standard base fields. Fan-in via `IntraActivitySequencing.ActionResponseEvent`. Old RequestCount-based code is commented out in source.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Order context |
| eventResponse | Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_BILLING_ARRANGEMENT | Backend response |
| currActivity | Concepts.OM.ProcessConfig.Activity | Activity state |

### §19.3 ResponseBase Construction

```text
createObject/object
├── @extId           ← $sysNanoTimeValue       [Always]
├── ResponseCode     ← $eventResponse/ResponseCode       [Always]
├── ResponseMessage  ← $eventResponse/ResponseMsg        [Always]
├── CompletionStatus ← $eventResponse/CompletionStatus   [Always]
└── ReferenceId      ← $eventResponse/RefID              [Always]
```

### §19.4 Fan-in Completion

```text
IntraActivitySequencing.ActionResponseEvent(currActivity)
→ "true" when all pending requests have responded
→ "false" otherwise
(Old RequestCount code COMMENTED OUT)
```

OPERATION_NAME: `"CCBS_UPDATE_BILLING_ARRANGEMENT"`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
