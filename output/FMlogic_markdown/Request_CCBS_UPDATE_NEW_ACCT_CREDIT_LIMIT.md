# Request_CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT

## §1 Overview & Purpose

**CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT** updates the personal credit limit on new CCBS accounts. A key gate (`isUpdateCredit`) means some orders send NO event at all — if no qualifying credit limit source is found, the FM completes as a no-op.

> **CRITICAL — Same fire-and-forget pattern as FM21:** Uses `Event.Ext.sendEventImmediate(reqEvent)` directly, manual `orderCurrentActivity.RequestCount++`, and `IsAllResponseSuccess(currActivity)` for fan-in. No IntraActivitySequencing.

> **isUpdateCredit gate (3 conditions — any is sufficient):** (1) personalCreditLimit > 0; (2) ODSCreditLimit present; (3) Channel = "7-11". If none true, the account is skipped entirely.

> **Credit limit priority:** INDY (Type=73) + ODS qualifies → ODSCreditLimit; PersonalCreditLimit > 0 → use it; Channel="7-11" → hardcoded 215. OT=8 carry: postpaid→postpaid → carry source credit limit.

> **ActivityReason computed BEFORE credit resolution:** Type=73 → "CREQ"; AccountSubType=TOP/PREMIUM AND Channel ends in "U" → "SUCL"; else → "G142".

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS |
| Send pattern | `Event.Ext.sendEventImmediate(reqEvent)` — NO IntraActivitySequencing |
| RequestCount | Manually incremented: `orderCurrentActivity.RequestCount++` |
| Fan-in | `IsAllResponseSuccess(currActivity)` |
| Iteration target | `Customer.Account[]` |
| Response concept | `Concepts.FM.Response.CCBS_UpdateNewAcctCreditLimitRes` |
| isUseFeCreditLimit | Always false (OMX-2605 code path commented out) |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| isUpdateCredit gate | personalCreditLimit > 0 OR ODSCreditLimit present OR Channel="7-11". Event only sent if true. |
| Credit limit priority | 1. OT=8 + postpaid→postpaid → SOURCECreditLimit; 2. Type=73 + ODS qualifies → ODSCreditLimit; 3. personalCreditLimit > 0 → personalCreditLimit; 4. Channel="7-11" → 215 |
| ActivityReason (computed first) | Type=73 → "CREQ"; AccountSubType in {TOP,PREMIUM} AND Channel ends "U" → "SUCL"; else → "G142" |
| L9CreditLimitWaiverInd | Dispatch based on credit limit waiver flag in account data |
| isUseFeCreditLimit | Always false — OMX-2605 FE credit limit path commented out |
| Hardcoded 215 | Credit limit for Channel="7-11" — embedded constant |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority / JMSCorrelationID / OrderID / RefID / OrderType ← standard fields
└── payload → ns:UpdateNewAcctCreditLimitRequest
    ├── ns:ban               ← Account[$i]/AccountID               [Always]
    ├── ns:creditLimit       ← priority chain: ODSCreditLimit → personalCreditLimit → 215 (7-11) → SOURCECreditLimit (OT=8) [Priority chain]
    ├── ns:activityReason    ← Type=73 → "CREQ"; TOP/PREMIUM+"U" → "SUCL"; else → "G142" [3-way dispatch]
    ├── ns:creditLimitWaiverInd ← L9CreditLimitWaiverInd dispatch   [Conditional]
    ├── ns:companyCode       ← Account[$i]/AccountManagementInfo.CompanyCode [Always]
    ├── ns:source            ← EOC/MNP_INT/MNP_EXT/CCBS             [3-way dispatch]
    └── ns:userId            ← 60001                                [Hardcoded]
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT
├── [if resubmit] Manual purge (RequestCount > 0 AND IsOrderResubmitted)
├── Instance.getByExtIdByUri(NextActivityName, Activity)
├── for each Account[i]:
│   ├── [skip if CompletionStatus==2 response exists for RefId]
│   ├── Compute ActivityReason (BEFORE credit):
│   │   ├── CustomerType=73 → "CREQ"
│   │   ├── AccountSubType in {TOP,PREMIUM} AND Channel ends "U" → "SUCL"
│   │   └── else → "G142"
│   ├── Resolve: ODSCreditLimit (Account.ExtInfo[ODS_CREDIT_LIMIT] from FM20)
│   │         personalCreditLimit (Account.AccountManagementInfo.PersonalCreditLimit)
│   │         SOURCECreditLimit (Account.ExtInfo[CARRY_CREDIT_LIMIT] for OT=8)
│   ├── Evaluate isUpdateCredit:
│   │   ├── personalCreditLimit > 0 → true
│   │   ├── ODSCreditLimit present → true
│   │   └── Channel = "7-11" → true
│   ├── if PreExecCheck.length > 0: GetXMLForAccount → XPath
│   └── if chkRes == "true" AND isUpdateCredit == true:
│       ├── Resolve L9CreditLimit (priority chain)
│       ├── Resolve L9CreditLimitWaiverInd
│       ├── Event.createEvent(CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT, active XSLT)
│       ├── Event.Ext.sendEventImmediate(reqEvent)  ← FIRE-AND-FORGET
│       ├── orderCurrentActivity.RequestCount++      ← MANUAL
│       ├── isSkipped = false
│       └── sendEventImmediate(Logger REQ)
├── GetActivityStatusString("1", false)
└── SendDataToDB(orderRequest)

Response_CCBS_UPDATE_NEW_ACCT_CREDIT_LIMIT
├── Instance.createInstance(CCBS_UpdateNewAcctCreditLimitRes: ResponseCode, ResponseMsg, CompletionStatus, ReferenceId)
│   → currActivity.Response[n]
├── [no order data write-backs]
├── sendEventImmediate(Logger RES)
└── IsAllResponseSuccess(currActivity) → "true"/"false"
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Same fire-and-forget risk as FM21: manual RequestCount++, IsAllResponseSuccess fan-in | [HIGH] | Standardise on IntraActivitySequencing in migration |
| isUpdateCredit gate: if false for all accounts, entire FM is a no-op — downstream cannot rely on credit limit being updated | [MEDIUM] | Document no-op scenario; add status flag if needed |
| Hardcoded 215 for Channel="7-11" | [MEDIUM] | Externalise to channel-credit-limit config table |
| isUseFeCreditLimit always false — OMX-2605 FE path commented out | [LOW] | Remove dead code in migration |
| ActivityReason computed before credit resolution — may be inconsistent if account type changes | [LOW] | Review computation order in migration |
| ODS_CREDIT_LIMIT consumed here depends on FM20 completing first | [MEDIUM] | Document FM18→FM20→FM21→FM22 chain; validate ProcessConfig enforces order |

---

## §19 Response Message Rule

Minimal response — 4 standard fields, no order data write-backs.

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | CCBS_UpdateNewAcctCreditLimitRes (4 std fields) | Always |

**Fan-in:** `IsAllResponseSuccess(currActivity)` — returns "true" when all sent events have successful responses. No write-backs to order data model.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
