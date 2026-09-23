# Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO

> Updates CCBS Account Accounting Management Info per-account sequentially via IntraActivitySequencing; optionally recalculates PersonalCreditLimit before sending (CAL_CREDITLIMIT parameter); activityReason selected by 4-tier priority; ClearField passthrough for CHARITY_CODE and CONVERGENCE_CODE.

**Backend:** CCBS | **Pattern:** IntraActivitySequencing (per-account sequential) | **forwardChain:** true | **Used in steps:** 48, 49

---

## §1 Overview & Purpose

Updates the CCBS Accounting Management Info for each Account in the order. Uses **IntraActivitySequencing** to dispatch calls sequentially (not fan-out). Per-account loop: each account's event is queued via `ActionRequestEvent`, then the first is dispatched via `SendFirstRequestEvent`. Each response advances the queue via `ActionResponseEvent`.

- **CAL_CREDITLIMIT parameter**: if "Y", recalculates `PersonalCreditLimit = existing + sum(FE offers AMOUNT_IN_VAT)` before event construction
- **calCRFlag**: `CAL_CR_FLG=Y` in order ExtendedInfo → forces `activityReason="G158"`
- **activityReason 4-tier**: calCRFlag→G158 / AccountActivityInfo.ActivityReason / tpc_reasonCode param / "CREQ"
- **ClearField passthrough**: CHARITY_CODE and CONVERGENCE_CODE pass sentinel value to CCBS to clear those fields
- **LogicalDate read but unused** — dead variable in current implementation

> **Active vs old XSLT:** A large commented-out old XSLT block exists in the source. The active version adds: (1) `CES` header field; (2) `tpc_reasonCode` branch in activityReason priority chain.

> **[HIGH] Response LOG_LEVEL = ERROR:** The response audit logger hardcodes `MSG_LOG_LEVEL/ERROR` instead of INFO — all response logs are emitted at ERROR level regardless of outcome.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO.rule` | 99 lines + large commented-out old XSLT |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO.rulefunction` | 24 lines |
| Priority | 5 | |
| forwardChain | true | |
| Backend | CCBS | `Events.OMConsumers.OMXFM.Request.CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO` |
| Schema NS (payload) | `http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/Schema5.xsd` | `ns:` prefix |
| Schema NS (body) | `www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.AccountingManagementInfo` | `ns1:` prefix |
| Dispatch pattern | IntraActivitySequencing | assertEvent + ActionRequestEvent per account; SendFirstRequestEvent after loop |
| isActResub | `RequestCount > 0 && IsOrderResubmitted` | → PurgePendingRequestsBeforeResubmit |
| Per-account resub guard | `CompletionStatus==2 && ReferenceId==refId` | Skips already-successful accounts |
| param tpc_reasonCode | `GetActivityParamValueFromKey(…, "reasonCode")` | Comment: True prompt care [Music add charge] |
| param cal_creditlimit | `GetActivityParameterValueFromKey(…, "CAL_CREDITLIMIT")` | Note: different helper function from tpc_reasonCode |
| LogicalDate | Read into `logicalDateVal` | [UNUSED] never referenced in XSLT or logic |
| Request logger | `Event.sendEvent` | Different from `Event.Ext.sendEventImmediate` used elsewhere |
| Response logger | `Event.Ext.sendEventImmediate` | LOG_LEVEL = ERROR (hardcoded — bug) |
| Skip condition | `isSkipped == true` after loop | SkipActivity("4") |
| Post-loop | SendFirstRequestEvent + Status="1" + SendDataToDB | |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` | Returns "true"/"false" |

---

## §3 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §4 CAL_CREDITLIMIT Pre-Calculation (per Account)

When activity parameter `CAL_CREDITLIMIT="Y"`:

```text
Step 1: personalCreditLimit =
    if (PersonalCreditLimit > 0)        → PersonalCreditLimit
    else if (ODS_CREDIT_LIMIT > 0)      → ExtendedInfo[ODS_CREDIT_LIMIT]/Value
    else                                → 0

Step 2: amountIntVat =
    sum(ParentOU/Subscriber[AccountRefId==refId]
        /SubscriberOffers[FE_OR_CCBS="FE"]
        /ExtendedInfo[AMOUNT_IN_VAT]/Value)

Step 3: account.AccountManagementInfo.PersonalCreditLimit = personalCreditLimit + amountIntVat
```

The updated `PersonalCreditLimit` is then sent as `ns1:L9PrsnlCreditLimit` in the CCBS payload.

> The commented-out old condition was `OrderType == "22"`. The `CAL_CREDITLIMIT` activity parameter replaced the hardcoded order type check.

---

## §5 activityReason 4-Tier Priority

| Priority | Condition | Value |
|----------|-----------|-------|
| 1 | `calCRFlag == "true"` (CAL_CR_FLG=Y in order ExtendedInfo) | `"G158"` |
| 2 | `exists(AccountActivityInfo/ActivityReason) AND length > 0` | `AccountActivityInfo/ActivityReason` |
| 3 | `length(tpc_reasonCode) > 0` | `tpc_reasonCode` (activity param "reasonCode") |
| 4 (default) | else | `"CREQ"` |

---

## §6 Request Payload Field Mapping

```text
createEvent / event
├── JMSPriority      ← $orderRequest/OrderPriority                     [Always — no conditional]
├── JMSCorrelationID ← $orderRequest/OrderData/OMXTrackingId           [Always]
├── OrderID          ← $orderRequest/OrderData/OrderID                  [Always]
├── RefID            ← $refId  (Account.RefId)                          [Always]
├── UserName/PassWord                                                   [Credential-gated: IsEnableUserPass="true"]
├── OrderType        ← $orderRequest/OrderData/OrderType                [Conditional]
├── CES              ← $orderRequest/OrderData/CES                      [Conditional — NEW vs old XSLT]
└── payload / ns:ChangeAccountingManagementInfoRequest
    ├── ns:AccountIdInfo
    │   └── ns:accountNo         ← number($account/AccountID)           [Always — numeric conversion]
    ├── ns1:AccountingManagementInfo
    │   ├── ns1:L9AccSubType     ← AccountManagementInfo/AccountSubType  [Conditional]
    │   ├── ns1:L9AccountPriority← ExtendedInfo[PRIORITY]/Value          [Conditional]
    │   ├── ns1:L9AtbCharityCode ← ExtendedInfo[CHARITY_CODE]/Value      [exists-cond; ClearField passthrough]
    │   ├── ns1:L9CompanyCode    ← AccountManagementInfo/CompanyCode     [Conditional]
    │   ├── ns1:L9ConvergenceCode← ExtendedInfo[CONVERGENCE_CODE]/Value  [exists-cond; ClearField passthrough]
    │   ├── ns1:L9CreditClass    ← AccountManagementInfo/CreditClass     [Conditional]
    │   ├── ns1:L9CreditLimitExpDate ← AccountManagementInfo/tempCreditLimitExpDate [Conditional]
    │   ├── ns1:L9CreditLimitRsnCode ← AccountManagementInfo/CreditLimitReasonCode  [Conditional]
    │   ├── ns1:L9CreditLimitWaiverExpDate ← AccountManagementInfo/CreditLimitWaiverExpDate [Conditional]
    │   ├── ns1:L9CreditLimitWaiverInd ← AccountManagementInfo/CreditLimitWaiverInd [Conditional]
    │   ├── ns1:L9CustBranchNo   ← AccountManagementInfo/BranchNumber    [Conditional]
    │   ├── ns1:L9CustTaxId      ← AccountManagementInfo/TaxId           [Conditional]
    │   ├── ns1:L9InitiationReason ← ExtendedInfo[INIT_REASON]/Value     [Double-exists-conditional]
    │   ├── ns1:L9LegacyBan      ← number(ExtendedInfo[LEGACY_BAN]/Value)[Conditional: tib:trim length>0]
    │   ├── ns1:L9ManualBlacklistInd ← AccountManagementInfo/manualBlacklistInd [Conditional]
    │   ├── ns1:L9ManualBlacklistRsnCd ← AccountManagementInfo/manualBlacklistRsnCd [Conditional]
    │   ├── ns1:L9ManualBlacklistUpDate ← AccountManagementInfo/manualBlacklistUpDate [Conditional]
    │   ├── ns1:L9PrsnlCreditLimit ← AccountManagementInfo/PersonalCreditLimit [Conditional; may be updated by §4]
    │   ├── ns1:L9SpecialInstructions ← ExtendedInfo[SPECIAL_INSTRUCTION]/Value [exists-conditional]
    │   ├── ns1:L9TempCreditLimit ← AccountManagementInfo/tempCreditLimit [Conditional]
    │   ├── ns1:L9WHTCertiNo     ← AccountManagementInfo/WHTCertiNo      [Double-exists-conditional]
    │   ├── ns1:L9WHTInd         ← AccountManagementInfo/whtInd          [Double-gate: exists() AND whtInd!=0]
    │   └── ns1:L9WhtTaxUpDate   ← AccountManagementInfo/whtTaxUpDate    [Double-exists-conditional]
    └── ns:ActivityInfo
        ├── ns:activityReason    ← 4-tier priority (§5)                  [Always]
        └── ns:userText          ← AccountActivityInfo/UserText           [Conditional]
```

---

## §7 Response Concept — CCBS_ChangeAccountingManagementInfoRes

```text
createObject / object
├── @extId          ← OMXUtils:generateTrackingID()   [Always]
├── ResponseCode    ← $eventResponse/ResponseCode      [Conditional]
├── ResponseMessage ← $eventResponse/ResponseMsg       [Conditional]
├── CompletionStatus← $eventResponse/CompletionStatus  [Conditional]
└── ReferenceId     ← $eventResponse/RefID             [Conditional]
```

> **Response OPERATION_NAME is dynamic:** `$currActivity/ActivityID` (not hardcoded) — enables this handler to serve both steps 48 and 49 since both share `activityId="CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO"`.

> **[HIGH BUG] Response LOG_LEVEL = ERROR:** Hardcoded `MSG_LOG_LEVEL/ERROR` — all responses logged at ERROR regardless of success/failure. Should be `MSG_LOG_LEVEL/INFO`.

---

## §8 Function Dependency Tree

```text
Request_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── logicalDateRes = Instance.getByExtIdByUri("LogicalDate", ...)   [UNUSED — dead variable]
├── [if isActResub]: PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── tpc_reasonCode = GetActivityParamValueFromKey(…, "reasonCode")
├── calCRFlag = XPath.evalAsBoolean(exists(CAL_CR_FLG=Y))
├── cal_creditlimit = GetActivityParameterValueFromKey(…, "CAL_CREDITLIMIT")
├── [Account loop i]:
│   ├── [Resub guard]: scan Response[] for CompletionStatus==2 && ReferenceId==refId
│   ├── [if !reqSuccess]:
│   │   ├── GetXMLForAccount(orderRequest, refId)
│   │   ├── XPath.execute(PreExecCheck)
│   │   └── [if "true"]:
│   │       ├── [if cal_creditlimit=="Y"]:
│   │       │   ├── personalCreditLimit = XPath.evalAsDouble(PersonalCreditLimit or ODS_CREDIT_LIMIT or 0)
│   │       │   ├── amountIntVat = XPath.evalAsDouble(sum FE AMOUNT_IN_VAT)
│   │       │   └── account.PersonalCreditLimit = personalCreditLimit + amountIntVat
│   │       ├── Event.createEvent(CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO, XSLT: all fields)
│   │       ├── Event.assertEvent(reqEvent)
│   │       ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   │       ├── Event.sendEvent(Logger)
│   │       └── isSkipped = false
├── [if !isSkipped]:
│   ├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
│   ├── Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch] HandleActivityException

Response_CCBS_CHANGE_ACCOUNTING_MANAGEMENT_INFO (rulefunction)
├── Instance.createInstance(CCBS_ChangeAccountingManagementInfoRes) { extId, ResponseCode, ReferenceId }
├── currActivity.Response[] ← res
├── Event.Ext.sendEventImmediate(Logger: OPERATION_NAME=$currActivity/ActivityID, LOG_LEVEL=ERROR)
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
```

---

## §9 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-account sequential dispatch via IntraActivitySequencing (not parallel fan-out). |
| R2 | CAL_CREDITLIMIT="Y" → recalculate PersonalCreditLimit before sending: max(PersonalCreditLimit, ODS_CREDIT_LIMIT) + sum(FE AMOUNT_IN_VAT). |
| R3 | calCRFlag (CAL_CR_FLG=Y in order) → forces activityReason="G158" regardless of other parameters. |
| R4 | activityReason 4-tier priority: G158 / AccountActivityInfo.ActivityReason / tpc_reasonCode / "CREQ". |
| R5 | CHARITY_CODE and CONVERGENCE_CODE: pass ClearField sentinel as-is (field-clearing pattern for CCBS). |
| R6 | L9LegacyBan: `number()` conversion; only sent when trimmed value has length > 0. |
| R7 | L9WHTInd: gated by `exists() AND whtInd != 0` — zero value suppressed. |
| R8 | Response OPERATION_NAME is dynamic (`currActivity/ActivityID`), enabling reuse across steps 48 and 49. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Response LOG_LEVEL hardcoded to ERROR — all responses logged as errors regardless of outcome | [HIGH] | Change to `MSG_LOG_LEVEL/INFO` in response audit XSLT |
| logicalDateVal read from LogicalDate but never used — dead variable | [LOW] | Remove or implement intended usage |
| Two different helper functions: `GetActivityParamValueFromKey` vs `GetActivityParameterValueFromKey` | [MEDIUM] | Verify both return same data; consolidate to single helper |
| Commented-out old XSLT block left in source | [LOW] | Remove dead code after confirming requirements are permanent |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
