# Request_CVSS_CREDIT_CHECK

## §1 Overview & Purpose

**CVSS_CREDIT_CHECK** evaluates credit class for each Account by submitting a full customer profile to CVSS (Credit Validation & Scoring System). The response updates `Account.AccountManagementInfo.CreditClass` with the CVSS-evaluated value.

> **Account-level iteration:** Loops `Customer.Account[]`, sending one `EvaluateCreditRequest` per Account. Skips accounts where CompletionStatus==2 already exists (resubmit protection).

> **Response write-backs (3):** (1) Saves existing CreditClass as `CURRENT_CREDITCLASS` ExtInfo (backup). (2) Overwrites `Account.AccountManagementInfo.CreditClass` with CVSS value. (3) Appends `CVSS_CREDIT_CHECK_COMPLETE` ExtInfo marker.

> **Two XSLT variants:** Old XSLT (commented out, OMX-2748) had no CES field. Active XSLT adds `<CES>`. OrderType=11002 extracts `approveCode` in the BE rule but this variable is NOT forwarded to the XSLT — dead code after refactor.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CVSS_CREDIT_CHECK` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | CVSS |
| Event type (request) | `Events.OMConsumers.OMXFM.Request.CVSS_CREDIT_CHECK` |
| Event type (response) | `Events.OMConsumers.OMXFM.Response.CVSS_CREDIT_CHECK` |
| Send pattern | `Event.assertEvent` + `IntraActivitySequencing.ActionRequestEvent` per Account |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Iteration target | `Customer.Account[]` (one event per Account) |
| Response concept | `Concepts.FM.Response.CVSS_CreditCheckRes` |
| Payload operation | `ns:EvaluateCreditRequest / EvaluateCreditClassRequest` |

---

## §7 Key Logic Patterns & Dispatches

| Field | Dispatch Logic |
|-------|---------------|
| `ns:source` | EOC → "EOC"; MNP + DonorOperator in {02,06,10} → "MNP_INT"; MNP else → "MNP_EXT"; else → "CCBS" |
| `ns:customerLevel` | CustomerTypeInfo.Type ≠ 73 → Grading; else "" |
| `ns:lastname` | Type ≠ 73 → OrgName; Type = 73 → LastName; else "" |
| `ns:gender` | Type = 73 → CustomerName.Gender; else "" |
| `ns:maritalstatus` | Type = 73 → CustomerName.MaritalStatus; else "" |
| `ns:typeofemp` | Type = 73 → CustomerGeneralInfo.Occupation; else "" |
| `ns:idexpdate` | Type = 73 → format(IdentificationExpDate, "yyyyMMdd", +07:00); else "" |
| `ns:dob` | BirthDate non-empty → format(BirthDate, "yyyyMMdd", +07:00); else xsi:nil |
| `ns:approveForSub` | maxAllowApproveCode exists → use it; else POU.ExtInfo[APPROVE_CODE].Value |
| `ns:INDYIndicator` | Type = 73 → "true"; else "false" |
| `ns:numberOfIDD/IR/Sub` | POU[agreeRefId] exists → from POU; else from ChildOU |
| `ns:proofdoc` | POU[AgreementRefId]/Subscriber[AccountRefId=refId].ProofDoc → ChildOU fallback |
| Hardcoded | education="ED5", billcountry/regcountry="THA", roleid=1, sequencenum=0, userid=60001 |
| OrderType=11002 | approveCode extracted in BE but NOT passed to XSLT — dead code after OMX-2748 |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority / JMSCorrelationID / OrderID  ← standard order fields        [Conditional]
├── RefID                                      ← Account[$var]/RefId          [Conditional]
├── OrderType                                  ← OrderData.OrderType          [Conditional]
├── CES                                        ← OrderData.CES                [Conditional: exists] (added OMX-2748)
└── payload → ns:EvaluateCreditRequest
    └── ns:EvaluateCreditClassRequest
        ├── ns:Prerequisiteinfo
        │   ├── ns:accountId               ← Account[$var]/AccountID         [if non-empty]
        │   ├── ns:custNo                  ← Customer.CustomerId             [if non-empty]
        │   ├── ns:payChannelId            ← Account[$var]/PayChannelId      [if non-empty]
        │   ├── ns:billingArrangementId    ← Account[$var]/BillingArrangementId [if non-empty]
        │   ├── ns:INDYIndicator           ← Type=73 → "true" else "false"   [Always]
        │   └── ns:PaginationInfo          ← pageSize/pageNumber/numberOfRows=1000/0/1000 [Hardcoded]
        └── ns:info (40+ fields)
            ├── ns:accommodation           ← CustomerAddress.TypeOfAccomodation [Always]
            ├── ns:acctype                 ← Account[$var]/AccountManagementInfo.AccountSubType [Always]
            ├── ns:approveForIDD           ← ""                              [Hardcoded empty]
            ├── ns:approveForIR            ← OrderData.irApproveCode         [Always]
            ├── ns:approveForSimBundle     ← OrderData.creditLimitApproveCode [Always]
            ├── ns:approveForSub           ← maxAllowApproveCode → POU.ExtInfo[APPROVE_CODE] [Priority chain]
            ├── ns:ban                     ← Account[$var]/AccountID         [Always]
            ├── ns:billadressnum/district/province/soi/street/subdistrict/zipcode ← BillingArrangementAddress [Always]
            ├── ns:billcountry             ← "THA"                           [Hardcoded]
            ├── ns:category                ← CustomerTypeInfo.Type           [Always]
            ├── ns:companyCode             ← AccountManagementInfo.CompanyCode [Always]
            ├── ns:compregcode             ← CustomerGeneralInfo.Identification [Always]
            ├── ns:creditClass             ← xsi:nil=true                    [Always nil]
            ├── ns:customerLevel           ← Type≠73 → Grading; else ""     [Dispatch]
            ├── ns:dob                     ← format(BirthDate, +07:00)       [Conditional: xsi:nil if empty]
            ├── ns:education               ← "ED5"                           [Hardcoded]
            ├── ns:firstname               ← CustomerName.FirstName          [Always]
            ├── ns:gender                  ← Type=73 → Gender; else ""       [Dispatch]
            ├── ns:idexpdate               ← Type=73 → format(IdentificationExpDate) [Dispatch]
            ├── ns:idnumber                ← CustomerGeneralInfo.Identification [Always]
            ├── ns:idtype                  ← CustomerGeneralInfo.IdentificationType [Always]
            ├── ns:lastname                ← Type≠73 → OrgName; Type=73 → LastName [3-way dispatch]
            ├── ns:maritalstatus           ← Type=73 → MaritalStatus; else "" [Dispatch]
            ├── ns:nationality             ← CustomerGeneralInfo.Nationality [Always]
            ├── ns:nosofchildren/nosofemp  ← 0                               [Hardcoded]
            ├── ns:numberOfIDD/IR          ← POU[agreeRefId] → ChildOU fallback [Agreement lookup]
            ├── ns:numberOfSub             ← count(POU[agreeRefId]/Subscriber) [Agreement lookup]
            ├── ns:paymethod               ← Account[$var]/PayChannelPaymentMethodInfo.PaymentMethod [Always]
            ├── ns:poafname/poaid          ← CustomerName.POAName/POAPersonalId [Always]
            ├── ns:proofdoc                ← POU/ChildOU Subscriber.ProofDoc  [Account↔POU lookup]
            ├── ns:regaddressnum/district/province/soi/street/zipcode ← CustomerAddress [Always]
            ├── ns:regcountry              ← "THA"                           [Hardcoded]
            ├── ns:roleid                  ← 1                               [Hardcoded]
            ├── ns:salrange                ← CustomerGeneralInfo.Salary      [Always]
            ├── ns:sequencenum             ← 0                               [Hardcoded]
            ├── ns:source                  ← EOC/MNP_INT/MNP_EXT/CCBS       [3-way dispatch]
            ├── ns:timeatcurraddr          ← CustomerAddress.TimeAtAddress   [Always]
            ├── ns:timeinbusiness          ← CustomerGeneralInfo.TimeInBusiness [Always]
            ├── ns:timeinemp               ← CustomerGeneralInfo.TimeInBusiness [Same field]
            ├── ns:title                   ← CustomerName.Title              [Always]
            ├── ns:typeofemp               ← Type=73 → Occupation; else ""  [Dispatch]
            └── ns:userid                  ← 60001                           [Hardcoded]
```

---

## §15 Function Dependency Tree

```text
Request_CVSS_CREDIT_CHECK
├── [if resubmit] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── Instance.getByExtIdByUri(NextActivityName, Activity)
├── [OrderType=11002] approveCode = XPath(POU.ExtInfo[APPROVE_CODE]) ← NOT used in XSLT (dead code)
├── for each Account[i]:
│   ├── [skip if Response[ReferenceId==refId AND CompletionStatus==2] exists]
│   ├── if PreExecCheck.length > 0:
│   │   └── GetXMLForAccount(orderRequest, refId) → XPath.execute(chkXPath)
│   └── if chkRes == "true":
│       ├── Event.createEvent(CVSS_CREDIT_CHECK, active XSLT)
│       ├── Event.assertEvent(reqEvent)
│       ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│       ├── isSkipped = false
│       └── sendEventImmediate(Logger REQ)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
└── SendDataToDB(orderRequest)

Response_CVSS_CREDIT_CHECK
├── Instance.createInstance(CVSS_CreditCheckRes: ResponseCode, ResponseMsg, CompletionStatus, ReferenceId)
│   → currActivity.Response[n] = activityRes
├── for each Account[i]: if Account[i].RefId == eventResponse.RefID:
│   ├── if CreditClass.length > 0:
│   │   → Account[i].ExtendedInfo[] += AccountExtendedInfo(Name="CURRENT_CREDITCLASS",
│   │       Value=Account[i].AccountManagementInfo.CreditClass)
│   ├── Account[i].AccountManagementInfo.CreditClass ←
│   │       EvaluateCreditClassResponse/evaluateCreditClassReturn/creditClass
│   └── Account[i].ExtendedInfo[] += AccountExtendedInfo(Name="CVSS_CREDIT_CHECK_COMPLETE")
├── sendEventImmediate(Logger RES)
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
    [OLD fan-in commented out]
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| OrderType=11002 approveCode extracted but NOT forwarded to XSLT — dead code after OMX-2748 | [MEDIUM] | Remove BE-level extraction; verify active XSLT handles 11002 correctly |
| `creditClass` in Prerequisiteinfo always xsi:nil — CVSS receives no hint | [LOW] | Document as intentional; CVSS evaluates independently |
| Hardcoded userid=60001 and education="ED5" | [LOW] | Externalize to global variables in migration |
| `timeinbusiness` and `timeinemp` both from same field | [LOW] | Verify with CVSS schema |
| CURRENT_CREDITCLASS backup not created if CreditClass empty | [LOW] | Acceptable behavior; backup only needed when value exists |
| 40+ field payload with many hardcoded empty strings | [LOW] | Review CVSS schema; omit nil/empty fields if not required |

---

## §19 Response Message Rule

Matches by `Account[i].RefId == eventResponse.RefID`. Three write-backs: backs up existing CreditClass, overwrites it, and appends completion marker.

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | CVSS_CreditCheckRes (4 fields) | Always |
| `Account[i].ExtendedInfo[]` Name="CURRENT_CREDITCLASS" | `Account[i].AccountManagementInfo.CreditClass` (backup) | RefId match AND CreditClass non-empty |
| `Account[i].AccountManagementInfo.CreditClass` | `EvaluateCreditClassResponse/evaluateCreditClassReturn/creditClass` | RefId match |
| `Account[i].ExtendedInfo[]` Name="CVSS_CREDIT_CHECK_COMPLETE" | (name only, no value — presence flag) | RefId match |

Fan-in: `IntraActivitySequencing.ActionResponseEvent(currActivity)` — returns "true" when all outstanding Account requests answered. Old fan-in commented out.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
