# Request_CVSS_UPDATE_SUBSCRIBER_COUNT

> CVSS credit evaluation per Account — sequential IntraActivitySequencing fan-out with multi-approveCode inner loop; sends full EvaluateCreditClassRequest with ~40 customer profile fields.

**Target:** CVSS (EvaluateCreditRequest) | **Pattern:** Sequential IntraActivitySequencing | **forwardChain:** true | **Author:** awalia-t420 | **Used in step:** 37

---

## §1 Overview & Purpose

Sends an `EvaluateCreditClassRequest` to CVSS for each Account in the order. The request carries a comprehensive customer profile (identity, addresses, credit class, approveCode, number-of-subscribers, IDD/IR counts, payment info). Uses `IntraActivitySequencing` for sequential dispatch — events are queued per account × approveCode, then sent one at a time.

> **Sequential fan-out:** Uses `ActionRequestEvent` + `SendFirstRequestEvent` / `ActionResponseEvent` — events are dispatched serially, NOT in parallel.

> **Multi-approveCode inner loop:** When `maxAllowApproveCodeList` is populated, one event is sent per account × approveCode entry. Default iteration count is 1 if list is empty.

> **Active XSLT vs OMX-2748 commented variant:** The prior XSLT (OMX-2748) is commented out. The active variant adds a `<CES>` header field and changes `customerLevel`/`lastname` conditions from Type=66/67 to Type!=73.

> **Fan-in:** `IntraActivitySequencing.ActionResponseEvent` (standard "000" count fan-in is commented out).

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_CVSS_UPDATE_SUBSCRIBER_COUNT.rule` | 127 lines |
| Response file | `Response_CVSS_UPDATE_SUBSCRIBER_COUNT.rulefunction` | 35 lines |
| Author | awalia-t420 | |
| forwardChain | true | |
| Target system | CVSS | Credit Valuation / Subscriber Count |
| Request schema NS | `http://services.omx.truecorp.co.th/FMServices/evaluateCreditRequest` | |
| Request event type | `Events.OMConsumers.OMXFM.Request.CVSS_UPDATE_SUBSCRIBER_COUNT` | Active variant (CES-enabled) |
| Response event type | `Events.OMConsumers.OMXFM.Response.CVSS_UPDATE_SUBSCRIBER_COUNT` | |
| Response concept | `Concepts.FM.Response.CVSS_UpdateSubscriberCountRes` | Custom; ResponseCode + ResponseMessage only (no CompletionStatus) |
| extId generation | `OMXUtils.generateTrackingID()` in BE, passed to XSLT as param | |
| Fan-out type | Sequential (IntraActivitySequencing) | Per Account × approveCode |
| dedup key | `Account[i].RefId` | Per account |
| PurgePendingRequestsBeforeResubmit | Conditional | Only when `isActResub=true` |
| Audit gate | [UNCONDITIONAL] | No AllowWriteLog |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` | Standard "000" count is commented out |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Customer profile; Account[]; maxAllowApproveCodeList; Channel; OrderType; ExtendedInfo |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Parameter[NO_OF_SUB]; RequestCount; Response[]; Status |
| `nextAct` | Concepts.OM.ProcessConfig.Activity (local) | Live lookup — PreExecCheck |

### Key local variables

| Variable | Value derivation |
|----------|-----------------|
| `noOfSub` | `GetActivityParamValueFromKey(orderCurrentActivity, "NO_OF_SUB")` |
| `orderShareplan` | `OrderType == "11001"` |
| `orderMNPShareplan` | `OrderType == "36"` |
| `iMaxAllowApproveCode` | `count(maxAllowApproveCodeList)`; 0 → clamped to 1; >0 → `chkMaxAllowApproveCodeData=true` |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "CVSS_UPDATE_SUBSCRIBER_COUNT"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CVSS_UPDATE_SUBSCRIBER_COUNT"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 approveCode 3-Tier Logic

Resolved inside the `iMaxAllow` inner loop — one approveCode per iteration.

| Priority | Condition | approveCode source | numberOfRequest source |
|----------|-----------|-------------------|----------------------|
| 1 | `chkMaxAllowApproveCodeData = true` (maxAllowApproveCodeList.count > 0) | `maxAllowApproveCodeList[iMaxAllow].approveCode` | `maxAllowApproveCodeList[iMaxAllow].numberOfRequest` |
| 2 | `orderShareplan` (OrderType=11001) OR `orderMNPShareplan` (OrderType=36) | `ParentOU[RefId=$AgreeRefId]/ExtendedInfo[Name='APPROVE_CODE']/Value` | `count(ParentOU[RefId=$AgreeRefId]/Subscriber/ExtendedInfo[Name='SHAREPLAN_MAIN_NUMBER'])` |
| 3 (default) | (other order types) | `orderRequest.OrderData.maxAllowApproveCode` | Not set (0) |

---

## §6 Loop Structure — Account × approveCode

```java
for (int i = 0; i < iAcctLen; i++) {         // Outer: per Account
    refId = Account[i].RefId;
    AgreeRefId = Account[i].AgreementRefId;
    reqSuccess = checkByRefId(Response, refId);

    if (!reqSuccess) {
        chkRes = "true";
        if (nextAct.PreExecCheck) {
            sXML = GetXMLForAccount(orderRequest, refId);
            chkRes = XPath.execute("/(" + chkXPath + ")", sXML, ...);
        }
        if (chkRes == "true") {
            for (int iMaxAllow = 0; iMaxAllow < iMaxAllowApproveCode; iMaxAllow++) { // Inner
                // resolve approveCode + numberOfRequest (3-tier)
                reqEvent = Event.createEvent("xslt://CVSS_UPDATE_SUBSCRIBER_COUNT");
                Event.assertEvent(reqEvent);
                ActionRequestEvent(reqEvent, orderCurrentActivity);
                sendAuditLogger();
                isSkipped = false;
            }
        }
    }
}
if (!isSkipped)
    SendFirstRequestEvent(orderCurrentActivity);  // dispatches first queued event
```

---

## §7 Payload — EvaluateCreditClassRequest

### §7.1 Event header

```text
event
├── JMSPriority     ← orderRequest/OrderPriority
├── JMSCorrelationID ← OrderData/OMXTrackingId
├── OrderID         ← OrderData/OrderID
├── RefID           ← Account[$var]/RefId  (var = i+1)
├── OrderType       ← OrderData/OrderType  [xsl:if]
└── CES             ← OrderData/CES  [xsl:if — ACTIVE variant only]
```

### §7.2 ns:Prerequisiteinfo

```text
ns:EvaluateCreditRequest/ns:EvaluateCreditClassRequest/ns:Prerequisiteinfo
├── ns:accountId           ← Account[$var]/AccountID  [if string-length > 0]
├── ns:custNo              ← Customer/CustomerId  [if string-length > 0]
├── ns:payChannelId        ← Account[$var]/PayChannelId  [if string-length > 0]
├── ns:billingArrangementId ← Account[$var]/BillingArrangementId  [if string-length > 0]
├── ns:INDYIndicator       ← "true" if CustomerTypeInfo/Type=73; else "false"
└── ns:PaginationInfo      ← pageSize=1000, pageNumber=0, numberOfRows=1000  [hardcoded]
```

### §7.3 ns:info block (~40 fields)

| Field | Source | Notes |
|-------|--------|-------|
| `ns:accommodation` | CustomerAddress/TypeOfAccomodation | |
| `ns:acctype` | Account[$var]/AccountManagementInfo/AccountSubType | |
| `ns:approveForIDD` | `""` (empty, hardcoded) | |
| `ns:approveForIR` | OrderData/irApproveCode | |
| `ns:approveForSimBundle` | OrderData/creditLimitApproveCode | |
| `ns:approveForSub` | `$approveCode` — 3-tier (see §5) | |
| `ns:ban` | Account[$var]/AccountID | |
| `ns:billXxx` (7 fields) | Account[$var]/BillingArrangementAddress/* | billcountry="THA" hardcoded |
| `ns:category` | CustomerTypeInfo/Type | |
| `ns:ccheld` | `""` (empty) | |
| `ns:companyCode` | Account[$var]/AccountManagementInfo/CompanyCode | |
| `ns:compregcode` | CustomerGeneralInfo/Identification | |
| `ns:contactlanguage` | CustomerGeneralInfo/contactLang | |
| `ns:creditClass` | Account[$var]/AccountManagementInfo/CreditClass | |
| `ns:customerLevel` | if Type!=73 → Grading; else "" | Active variant; old: only Type=66/67 |
| `ns:dateofact` | `tib:format-dateTime('yyyyMMdd', current-dateTime())` | |
| `ns:dealercode` | OrderData/DealerCode | |
| `ns:debitstatus` | `""` (empty) | |
| `ns:dob` | BirthDate formatted yyyyMMdd (+07:00); `xsi:nil="true"` if blank | |
| `ns:education` | `"ED5"` (hardcoded) | |
| `ns:empstatus` | `""` (empty) | |
| `ns:firstname` | CustomerName/FirstName | |
| `ns:gender` | if Type=73 → CustomerName/Gender; else "" | |
| `ns:homephone` | CustomerName/HomePhone | |
| `ns:idexpdate` | if Type=73 → IdentificationExpDate formatted yyyyMMdd; else "" | |
| `ns:idnumber` | CustomerGeneralInfo/Identification | |
| `ns:idtype` | CustomerGeneralInfo/IdentificationType | |
| `ns:industrytype` | `""` (empty) | |
| `ns:lastname` | if Type!=73 → OrgName; else if Type=73 → LastName; else "" | Active variant; old: Type=66/67 → OrgName |
| `ns:maritalstatus` | if Type=73 → MaritalStatus; else "" | |
| `ns:nationality` | CustomerGeneralInfo/Nationality | |
| `ns:nosofchildren` | `0` (hardcoded) | |
| `ns:nosofemp` | `0` (hardcoded) | |
| `ns:numberOfIDD` | 4-branch POU/COU resolve (see §8) | |
| `ns:numberOfIR` | 4-branch POU/COU resolve (same pattern) | |
| `ns:numberOfSub` | 4-tier logic (see §9) | |
| `ns:officephone` | `""` (empty) | |
| `ns:paymethod` | Account[$var]/PayChannelPaymentMethodInfo/PaymentMethod | |
| `ns:poafname` | CustomerName/POAName | |
| `ns:poaid` | CustomerName/POAPersonalId | |
| `ns:poalname` | `""` (empty) | |
| `ns:profession` | `""` (empty) | |
| `ns:proofdoc` | POU/COU Subscriber.SubscriberGeneralInfo/ProofDoc (AgreementRefId-keyed) | |
| `ns:regXxx` (7 fields) | CustomerAddress/*; regsubdistrict="" hardcoded; regcountry="THA" hardcoded | |
| `ns:roleid` | `1` (hardcoded) | |
| `ns:salrange` | CustomerGeneralInfo/Salary | |
| `ns:sequencenum` | `0` (hardcoded) | |
| `ns:source` | 5-branch choose (see §10) | |
| `ns:timeatcurraddr` | CustomerAddress/TimeAtAddress | |
| `ns:timeinbusiness` | CustomerGeneralInfo/TimeInBusiness | |
| `ns:timeinemp` | CustomerGeneralInfo/TimeInBusiness (same as timeinbusiness) | |
| `ns:title` | CustomerName/Title | |
| `ns:typeofcc` | `""` (empty) | |
| `ns:typeofemp` | if Type=73 → Occupation; else "" | |
| `ns:userid` | `60001` (hardcoded) | |

---

## §8 numberOfIDD / numberOfIR — 4-Branch POU/COU Resolution

| Branch | Condition | Source |
|--------|-----------|--------|
| 1 | `exists(ParentOU[Agreement/RefId = Account[$var]/AgreementRefId])` | POU by AgreementRefId → NumberOfIDD/IR |
| 2 | `exists(ParentOU/ChildOU[Agreement/RefId = Account[$var]/AgreementRefId])` | COU by AgreementRefId → NumberOfIDD/IR |
| 3 | `exists(ParentOU[Account[$var]/RefId = Subscriber/AccountRefId])` | POU by AccountRefId → NumberOfIDD/IR |
| 4 (else) | (fallback) | COU by AccountRefId → NumberOfIDD/IR |

---

## §9 numberOfSub — 4-Tier Logic

| Priority | Condition | Value |
|----------|-----------|-------|
| 1 | `ExtendedInfo[Name='EVAL_CREDIT_FLG']/Value = 'Y'` | `0` |
| 2 | `string-length($noOfSub) > 0` | `$noOfSub` (from NO_OF_SUB activity parameter) |
| 3 | `$numberOfRequest > 0` | `$numberOfRequest` |
| 4 (default) | else | `count(ParentOU[Agreement/RefId=$agreeRefId]/Subscriber)` or COU equivalent |

---

## §10 ns:source — 5-Branch Logic

| Priority | Condition | Value |
|----------|-----------|-------|
| 1 | `exists(ExtendedInfo[Name='EVAL_CREDIT_SOURCE'])` | ExtendedInfo value |
| 2 | `Channel = "EOC"` | `"EOC"` |
| 3 | `Channel = "MNP"` | `"MNP_INT"` if DonorOperator=02/06/10; else `"MNP_EXT"` |
| 4 | `OrderType = "11001" or "11002"` | `"OMX"` |
| 5 (default) | else | `"CCBS"` |

---

## §11 Active vs Commented (OMX-2748) XSLT Differences

| Field | Commented (OMX-2748) | Active (Current) |
|-------|---------------------|-----------------|
| `<CES>` header | Absent | `$orderRequest/OrderData/CES` [xsl:if] |
| `ns:customerLevel` | if Type=66 or 67 → Grading; else "" | if Type **!=73** → Grading; else "" |
| `ns:lastname` | if Type=66 or 67 → OrgName; if Type=73 → LastName; else "" | if Type **!=73** → OrgName; else if Type=73 → LastName; else "" |

---

## §12 Response — CVSS_UpdateSubscriberCountRes & Fan-in

### §12.1 Response concept mapping

```text
createObject (Concepts.FM.Response.CVSS_UpdateSubscriberCountRes)
├── @extId          ← OMXUtils.generateTrackingID()  [in BE, not XSLT]
├── ResponseCode    ← $eventResponse/ResponseCode  [xsl:if]
└── ResponseMessage ← $eventResponse/ResponseMsg  [xsl:if]
```

> **No CompletionStatus field** — CVSS_UpdateSubscriberCountRes maps only ResponseCode and ResponseMessage.

### §12.2 Fan-in via IntraActivitySequencing

```java
/* Standard "000" count COMMENTED OUT:
   int successResponseCount = count(Response[tib:right(tib:trim(ResponseCode), 3) = "000"]);
   if (currActivity.RequestCount == successResponseCount) return "true"; */

// ACTIVE fan-in:
if (RuleFunctions.Helpers.IntraActivitySequencing.ActionResponseEvent(currActivity))
    return "true";
else
    return "false";
```

---

## §13 Audit Logging

| Phase | Gate | AUDIT_TRACE |
|-------|------|-------------|
| Request (per account × approveCode) | [UNCONDITIONAL] | `"Request Sent for CVSS_UPDATE_SUBSCRIBER_COUNT"` |
| Response | [UNCONDITIONAL] | `"Response received for CVSS_UPDATE_SUBSCRIBER_COUNT"` |

---

## §14 Activity Status Management

| Condition | Call | Code |
|-----------|------|------|
| At least one event queued | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" (RUNNING) |
| No accounts qualify (isSkipped=true) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" (SKIPPED) |

---

## §15 Function Dependency Tree

```text
Request_CVSS_UPDATE_SUBSCRIBER_COUNT (rule)
├── Instance.getByExtIdByUri(NextActivityName, Activity)   [nextAct / PreExecCheck]
├── [isActResub] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── GetActivityParamValueFromKey(activity, "NO_OF_SUB")
├── XPath.evalAsInt(count maxAllowApproveCodeList)
├── [Account loop i]:
│   ├── reqSuccess check by Response[ReferenceId==refId AND CompletionStatus==2]
│   ├── GetXMLForAccount(orderRequest, refId) → PreExecCheck sXML
│   ├── XPath.execute("/("+chkXPath+")", sXML)
│   └── [iMaxAllow loop]:
│       ├── resolve approveCode + numberOfRequest (3-tier)
│       ├── Event.createEvent("xslt://CVSS_UPDATE_SUBSCRIBER_COUNT") → reqEvent
│       ├── Event.assertEvent(reqEvent)
│       ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│       └── Event.Ext.sendEventImmediate(Logger: "Request Sent...")
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1") + SendDataToDB   [or SkipActivity("4")]
└── HandleActivityException   [catch]

Response_CVSS_UPDATE_SUBSCRIBER_COUNT (rulefunction)
├── OMXUtils.generateTrackingID()   [extId — in BE code]
├── Instance.createInstance("xslt://CVSS_UpdateSubscriberCountRes")
│   ├── @extId = $extId
│   ├── ResponseCode ← $eventResponse/ResponseCode  [xsl:if]
│   └── ResponseMessage ← $eventResponse/ResponseMsg  [xsl:if]
├── currActivity.Response[length] = activityRes
├── Event.Ext.sendEventImmediate(Logger: "Response received...")
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
```

---

## §16 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Sequential IntraActivitySequencing — events must be dispatched serially per account × approveCode. |
| R2 | Inner approveCode loop iterates up to `count(maxAllowApproveCodeList)` times; if list empty, exactly one event per account. |
| R3 | Fan-in via `ActionResponseEvent` — standard "000" count fan-in is commented out and must NOT be restored. |
| R4 | `numberOfSub` has 4-tier priority: EVAL_CREDIT_FLG=Y→0 / NO_OF_SUB param / numberOfRequest / count subscribers. |
| R5 | `source` has 5-branch priority: EVAL_CREDIT_SOURCE / EOC / MNP (INT/EXT) / OMX / CCBS. |
| R6 | `customerLevel` and `lastname` use Type!=73 logic (active variant) — NOT the old Type=66/67 logic. |
| R7 | `<CES>` header field must be included when `OrderData/CES` is populated. |
| R8 | `dob` must emit `xsi:nil="true"` when BirthDate is blank. |
| R9 | Several static values are hardcoded: `education="ED5"`, `roleid=1`, `sequencenum=0`, `userid=60001`, country="THA". |
| R10 | Audit unconditional — no AllowWriteLog gate. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Sequential dispatch may cause latency with many accounts × approveCodes | [MEDIUM] | Profile cardinality in load testing; consider parallelising if CVSS supports it |
| `timeinbusiness` and `timeinemp` both map to `TimeInBusiness` — potential mis-mapping for employment time | [LOW] | Confirm with CVSS API spec |
| Hardcoded `userid=60001` baked into every request | [LOW] | Move to global variable or activity parameter |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
