# Request_CCBS_UPD_CREDIT_CLASS

## §1 Overview & Purpose

**CCBS_UPD_CREDIT_CLASS** updates the credit class on each CCBS Account. The credit class value comes from a complex 5-source priority chain: CVSS result, ODS result, existing/source credit class, and CCBS default — gated by account type, customer type, and global exclusion lists.

> **CRITICAL ARCHITECTURE DIFFERENCE — Fire-and-Forget:** This FM does NOT use `IntraActivitySequencing.ActionRequestEvent` or `Event.assertEvent`. Instead it calls `Event.Ext.sendEventImmediate(reqEvent)` directly and manually increments `orderCurrentActivity.RequestCount++`. Fan-in uses `IsAllResponseSuccess(currActivity)` rather than `IntraActivitySequencing.ActionResponseEvent`.

> **5-way credit class priority (L9CreditClass):** carrySource (OT=8) → carryODS → ODS present → CVSS present → CCBS default (no event sent).

> **Global exclusion lists:** Three global variables gate credit class updates: `NoCreditClassChangeCC`, `NoCreditClassChangeSubType`, `NoCreditClassChangeTargetCC`. Any match skips the Account.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPD_CREDIT_CLASS` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS |
| Send pattern | `Event.Ext.sendEventImmediate(reqEvent)` — NO IntraActivitySequencing |
| RequestCount | Manually incremented: `orderCurrentActivity.RequestCount++` |
| Fan-in | `IsAllResponseSuccess(currActivity)` — NOT ActionResponseEvent |
| Iteration target | `Customer.Account[]` |
| Response concept | `Concepts.FM.Response.CCBS_UpdateCreditClassRes` |
| Payload operation | `ns:UpdateCreditClassRequest` |

---

## §7 Credit Class Priority Chain (L9CreditClass)

Priority evaluated top-to-bottom; first match wins. If none match, event is NOT sent.

| Priority | Source | Condition | Action |
|----------|--------|-----------|--------|
| 1 — carrySource | SOURCECreditClass (from source account) | OT=8: postpaid→postpaid OR hybrid→hybrid; non-empty SOURCECreditClass | Use SOURCECreditClass |
| 2 — carryODS | ODS ExtInfo (ODS_CREDIT_CLASS) | ODS present AND Account is active AND account type qualifies | Use ODSCreditClass |
| 3a — ODS new active | ODS ExtInfo | ODS present AND new account AND AccountSubType in active set | Use ODSCreditClass |
| 3b — ODS other | ODS ExtInfo | ODS present AND other conditions | Use ODSCreditClass |
| 4 — CVSS | CVSSCreditClass (post-FM19 Account.CreditClass) | CVSSCreditClass non-empty | Use CVSSCreditClass |
| 5 — CCBS default | (none) | All above failed | Do NOT send event |

**ActivityReason dispatch:**

| Condition | Value |
|-----------|-------|
| ActivityReasonODS global var non-empty | ActivityReasonODS value |
| AccountActivityInfo.ActivityReason non-empty | AccountActivityInfo.ActivityReason |
| else | "CREQ" |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority / JMSCorrelationID / OrderID / RefID / OrderType ← standard fields
└── payload → ns:UpdateCreditClassRequest
    ├── ns:ban               ← Account[$i]/AccountID               [Always]
    ├── ns:creditClass       ← L9CreditClass (5-source priority chain) [Always — resolved]
    ├── ns:activityReason    ← ActivityReasonODS → AccountActivityInfo.ActivityReason → "CREQ" [3-way dispatch]
    ├── ns:companyCode       ← Account[$i]/AccountManagementInfo.CompanyCode [Always]
    ├── ns:grading           ← targetGrading                        [Conditional: account type transition]
    ├── ns:source            ← EOC/MNP_INT/MNP_EXT/CCBS             [3-way dispatch]
    └── ns:userId            ← 60001                                [Hardcoded]
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_UPD_CREDIT_CLASS
├── [if resubmit] Manual purge (RequestCount > 0 AND IsOrderResubmitted)
├── Instance.getByExtIdByUri(NextActivityName, Activity)
├── Read global exclusion lists: NoCreditClassChangeCC, NoCreditClassChangeSubType, NoCreditClassChangeTargetCC
├── for each Account[i]:
│   ├── [skip if CompletionStatus==2 response exists for RefId]
│   ├── Resolve: CVSSCreditClass (Account.AccountManagementInfo.CreditClass after FM19)
│   │         ODSCreditClass (Account.ExtInfo[ODS_CREDIT_CLASS] from FM20)
│   │         SOURCECreditClass (Account.ExtInfo[CURRENT_CREDITCLASS] backup from FM19)
│   │         sourceAccountSubType / targetAccountSubType / sourceCustomerType / targetCustomerType
│   │         targetGrading
│   ├── Check exclusion lists → skip if match
│   ├── Evaluate L9CreditClass (5-priority chain)
│   ├── Evaluate ActivityReason (3-way)
│   ├── if PreExecCheck.length > 0: GetXMLForAccount → XPath
│   └── if chkRes == "true" AND L9CreditClass non-empty:
│       ├── Event.createEvent(CCBS_UPD_CREDIT_CLASS, active XSLT)
│       ├── Event.Ext.sendEventImmediate(reqEvent)  ← FIRE-AND-FORGET
│       ├── orderCurrentActivity.RequestCount++      ← MANUAL
│       ├── isSkipped = false
│       └── sendEventImmediate(Logger REQ)
├── GetActivityStatusString("1", false)
└── SendDataToDB(orderRequest)

Response_CCBS_UPD_CREDIT_CLASS
├── Instance.createInstance(CCBS_UpdateCreditClassRes: ResponseCode, ResponseMsg, CompletionStatus, ReferenceId)
│   → currActivity.Response[n]
├── [no order data write-backs]
├── sendEventImmediate(Logger RES)
└── IsAllResponseSuccess(currActivity) → "true"/"false"
    [NOT IntraActivitySequencing.ActionResponseEvent]
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Fire-and-forget: manual RequestCount++; no IntraActivitySequencing; fan-in via IsAllResponseSuccess — miscounting risk | [HIGH] | Standardise on IntraActivitySequencing; implement idempotent request tracking |
| L9CreditClass depends on FM19→FM20 completing first — implicit ordering dependency | [MEDIUM] | Document and enforce FM19→FM20→FM21 chain in ProcessConfig |
| Three global exclusion lists — behaviour changes silently when lists change | [MEDIUM] | Externalise to config store with audit trail |
| CVSSCreditClass is read from Account.CreditClass which FM19 OVERWROTE with CVSS result — not raw CVSS API response | [MEDIUM] | Document data flow: FM19 writes CVSS to Account.CreditClass; FM21 reads from there |
| Hardcoded userId=60001 in CCBS request | [LOW] | Externalise to configuration |

---

## §19 Response Message Rule

Minimal response — 4 standard fields, no order data write-backs.

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | CCBS_UpdateCreditClassRes (4 std fields) | Always |

**Fan-in:** `IsAllResponseSuccess(currActivity)` — NOT `IntraActivitySequencing.ActionResponseEvent`. Returns "true" when all sent events have successful responses.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
