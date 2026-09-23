# Request_CCBS_UPD_CREDIT_LIMIT

## §1 Overview & Purpose

**CCBS_UPD_CREDIT_LIMIT** updates the credit limit on existing CCBS accounts. Sends a compound `UpdateCreditLimitRequest` containing three sub-operations to CCBS in a single message.

> **Standard IntraActivitySequencing pattern** — unlike FM21/FM22/FM23/FM26, this FM uses `Event.assertEvent + IntraActivitySequencing.ActionRequestEvent`. Fan-in uses `IntraActivitySequencing.ActionResponseEvent`.

> **calCRFlag gate:** Checks order ExtInfo for `CAL_CR_FLG=Y` via XPath boolean. If true AND CustomerType=73 → activityReason="G158" (unique to FM25). Normal Type=73 → "CREQ"; else → "G142".

> **Two XSLT variants (OMX-2748):** Old XSLT lacked CES field and had L9CreditLimitWaiverInd condition for Type=66/67. Active XSLT adds CES and changed condition to Type!=73.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPD_CREDIT_LIMIT` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS |
| Send pattern | `Event.assertEvent` + `IntraActivitySequencing.ActionRequestEvent` per Account |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Iteration target | `Customer.Account[]` |
| Response concept | `Concepts.FM.Response.CCBS_UpdateCreditLimitRes` |
| Payload operation | `ns:UpdateCreditLimitRequest` (3 sub-requests) |
| calCRFlag | XPath: order ExtInfo[Name='CAL_CR_FLG' and Value='Y'] |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| calCRFlag | XPath.evalAsBoolean on order ExtInfo[CAL_CR_FLG='Y']. Type=73 + calCRFlag=true → activityReason "G158". |
| L9CreditLimitWaiverInd (OMX-2748) | Active: non-empty → use it; else if Type!=73 AND (TOP/PREMIUM) → "U". Old: Type=66/67. |
| Compound payload | 3 sub-requests: GetAccountHeaderRequest + I9GetAccountCreditHistoryRequest + ChangeAccountingManagementInfoRequest |
| L9PrsnlCreditLimit | Only if PersonalCreditLimit non-empty (string-length > 0) |
| activityReason 3-way | Type=73 + !calCRFlag → "CREQ"; Type=73 + calCRFlag → "G158"; else → "G142" |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority / JMSCorrelationID / OrderID  ← standard fields
├── RefID                                      ← Account[$var]/RefId
├── UserName / PassWord                        ← Conditional: IsEnableUserPass=true
├── OrderType                                  ← OrderData.OrderType
├── CES                                        ← OrderData.CES  [Conditional: active XSLT only]
└── payload → ns:UpdateCreditLimitRequest
    ├── ns4:GetAccountHeaderRequest
    │   └── ns4:accountNo              ← Account[$var]/AccountID         [Always]
    ├── ns1:I9GetAccountCreditHistoryRequest
    │   ├── ns1:accountNo              ← Account[$var]/AccountID         [Always]
    │   └── ns1:PaginationInfo         ← pageSize/pageNumber/numberOfRows=1000/0/1000 [Hardcoded]
    └── ns3:ChangeAccountingManagementInfoRequest
        ├── ns3:accountNo              ← Account[$var]/AccountID         [Always]
        └── [for-each AccountManagementInfo]
            └── ns5:AccountingManagementInfo
                ├── ns5:L9AgreementId  ← Account[$var]/AgreementId       [Conditional: non-empty]
                ├── ns5:L9CreditLimitRsnCode ← AccountManagementInfo.CreditLimitReasonCode [Conditional]
                ├── ns5:L9CreditLimitWaiverInd ← CreditLimitWaiverInd; else Type!=73+TOP/PREMIUM → "U" [Dispatch]
                └── ns5:L9PrsnlCreditLimit ← AccountManagementInfo.PersonalCreditLimit [Conditional: non-empty]
        └── ns3:ActivityInfo
            ├── ns3:activityReason  ← Type=73+!calCRFlag → "CREQ"; Type=73+calCRFlag → "G158"; else → "G142"
            └── ns3:userText        ← AccountActivityInfo.UserText        [Always]
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_UPD_CREDIT_LIMIT
├── [if resubmit] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── Instance.getByExtIdByUri(NextActivityName, Activity)
├── for each Account[i]:
│   ├── [skip if CompletionStatus==2 response exists for RefId]
│   ├── if PreExecCheck: GetXMLForAccount → XPath
│   └── if chkRes == "true":
│       ├── calCRFlag = XPath.evalAsBoolean(order ExtInfo[CAL_CR_FLG='Y'])
│       ├── Event.createEvent(CCBS_UPD_CREDIT_LIMIT, active XSLT, params: i, calCRFlag)
│       ├── Event.assertEvent(reqEvent)
│       ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│       ├── sendEventImmediate(Logger REQ)
│       └── isSkipped = false
├── if !isSkipped:
│   ├── IntraActivitySequencing.SendFirstRequestEvent(activity)
│   ├── GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
└── else: SkipActivity("4")

Response_CCBS_UPD_CREDIT_LIMIT
├── Instance.createInstance(CCBS_UpdateCreditLimitRes: ResponseCode, ResponseMsg, CompletionStatus, ReferenceId)
│   → currActivity.Response[n]
├── [no order data write-backs]
├── sendEventImmediate(Logger RES)
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
    [OLD fan-in commented out]
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Compound 3-sub-request payload — CCBS API changes must keep all 3 in sync | [MEDIUM] | Consider splitting into separate FM calls in migration |
| L9CreditLimitWaiverInd: Type=66/67 → Type!=73 change in OMX-2748 — broader condition | [MEDIUM] | Regression-test CORP account waiver scenarios |
| "G158" ActivityReason unique to FM25 — document separately | [LOW] | Document ActivityReason code registry |
| Pagination hardcoded 1000 — may miss large credit history records | [LOW] | Review CCBS volume; implement pagination if needed |

---

## §19 Response Message Rule

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | CCBS_UpdateCreditLimitRes (4 std fields) | Always |

Fan-in: `IntraActivitySequencing.ActionResponseEvent(currActivity)`. Old fan-in commented out.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
