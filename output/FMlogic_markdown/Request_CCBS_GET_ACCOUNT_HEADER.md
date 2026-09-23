# Request_CCBS_GET_ACCOUNT_HEADER

> TIBCO BusinessEvents FM Logic — Account Header retrieval with IntraActivitySequencing fan-out; rich response enrichment (AccountManagementInfo, Names, Address, AgreementId, IDD/IR indicators)

**Author:** awalia-t420 | **Priority:** 5 | **forwardChain:** true | **Pattern:** IntraActivitySequencing (per Account)

> **BUG FOUND (response rulefunction, line 306):** Zip ClearField check reads `AccountAddress.City` instead of `AccountAddress.Zip` — HIGH severity. See §17.

---

## §1 Overview & Purpose

**CCBS_GET_ACCOUNT_HEADER** retrieves detailed account header information from CCBS for each Account on the order. It uses **IntraActivitySequencing** to throttle the fan-out — requests are queued and fired one at a time, with each response triggering the next request.

The response handler is one of the most complex in the system (484 lines), enriching the Account concept with:
- **AccountManagementInfo** — credit class, credit limits, convergence/charity codes (bootstrap + IsBlank guards)
- **Name info** — INDY (NameType=73) with NE1-NE10 or CORP with NE1-NE8, all ClearField-safe
- **Extended contact** (LinkType=70) — Language, PrefContactNumber, HomePhone, BizPhone, privatePhone, AuthFirstName, AuthLastName, AuthPersonalId, POAName, POAPersonalId
- **Address** — 15 AddressElements (AE1-AE15), all ClearField-safe
- **AgreementId resolution** — POU and COU loops; NumberOfIDD/IR mapping from ASCII codes
- **PAY_CHANNEL_FEE gate** — PayChannelFeeInfo from NameAddressInfoList[LinkType=84]
- **Raw CCBS_GetAccountHeaderRes concept** — full AccountHeader snapshot

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_ACCOUNT_HEADER` |
| Author | awalia-t420 |
| Priority | 5 |
| Forward chain | true |
| Backend system | CCBS (GetAccountHeader) |
| Request schema | `http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/Schema.xsd13` |
| Response concept | `Concepts.FM.Response.CCBS_GetAccountHeaderRes` |
| Fan-out pattern | IntraActivitySequencing (per Account, throttled sequential) |
| Completion criterion | `IntraActivitySequencing.ActionResponseEvent(currActivity)` → true/false |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Customer.Account[] array iterated; RefId, AccountID, and ExtendedInfo read |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Holds PreExecCheck, RequestCount, Response[], Status; IntraActivitySequencing state |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_GET_ACCOUNT_HEADER"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_ACCOUNT_HEADER"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Resubmit flag: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Fetch `nextAct` via nextAct pattern; read `altParam` via `GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")`
3. Read `iAcctLen = Customer.Account@length`
4. If resubmit: `PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
5. **For each Account[i]** (i = 0..iAcctLen-1):
   - a. Check resubmit skip: if any Response[iResp].ReferenceId==refId && CompletionStatus==2 → skip this account
   - b. Per-account PreExecCheck: `GetXMLForAccount(orderRequest, refId)` → evaluate XPath
   - c. If chkRes="true": build `GetAccountHeaderRequest` event (AccountID indexed as `$iAcc = i+1`)
   - d. `Event.assertEvent(reqEvent)` (not sendEventImmediate — queued)
   - e. `IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)` — enqueues the request
   - f. Send audit Logger event
   - g. Set `isSkipped = false`
6. After loop: if `!isSkipped` → `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)` → fire first in queue
7. If `!isSkipped`: `GetActivityStatusString("1", false)` + `SendDataToDB(orderRequest)`
8. Else: `SkipActivity(orderRequest, orderCurrentActivity, "4")`
9. Exception: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Protocol | Note |
|-----------|-----------|---------|------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_GET_ACCOUNT_HEADER` | JMS (assertEvent + IntraActivitySequencing) | Throttled sequential; uses assertEvent |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_GET_ACCOUNT_HEADER` | JMS | Each response triggers next request |

### §8.3 Backend API Details

| Property | Value |
|----------|-------|
| System | CCBS |
| Operation | GetAccountHeader |
| Request element | `ns1:GetAccountHeaderRequest / ns1:AccountIdInfo / ns1:accountNo` |
| Key input | `Account[iAcc]/AccountID` (1-indexed) |
| CES routing | ALT_CES parameter + OrderData/ExtendedInfo[ALT_CES] override; else OrderData/CES |
| Credential gate | `IsEnableUserPass='true'` → UserName/PassWord headers |

### §8.4 Fields Read / Written

**Read:** `Customer.Account[i].RefId`, `Customer.Account[i].AccountID`, `OrderData/ExtendedInfo[ALT_CES]`, activity parameters `ALT_CES` and `PAY_CHANNEL_FEE`

**Written (per Account):**
- `Account.OpenDate`
- `Account.AccountManagementInfo.*` (bootstrap + partial updates)
- `Account.ExtendedInfo[]` — CHARITY_CODE, CONVERGENT_CODE, COL_STATUS, OLD_PERSONAL_CREDITLIMIT
- `Account.AccountNames.*` (if GET_NAME_ADDRESS gate)
- `Account.AccountAddress.*` (if GET_NAME_ADDRESS gate)
- `Account.PayChannelFeeInfo` (if PAY_CHANNEL_FEE=Y)
- `Customer.CustomerId` (bootstrap if null)
- `ParentOU[i]/ChildOU[j].Agreement.*`
- `ParentOU[i/j].NumberOfIDD/NumberOfIR`

### §8.5 Activity Parameters

| Key | Value checked | Effect |
|-----|---------------|--------|
| `ALT_CES` | "Y" | CES endpoint override from OrderData/ExtendedInfo[ALT_CES] |
| `PAY_CHANNEL_FEE` | "Y" | Map PayChannelFeeInfo from NameAddressInfoList[LinkType=84] |

### §8.6 Global Variable Dependencies

`OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass`, `OMX_OM/OrderTypes/GetNameAddress`, `OMX_COMMON/_SharedResources/Common/ClearField`, `OMX_COMMON/Component_Name/OMX_CEP`, `OMX_COMMON/Component_Name/OMX_FM`, `MSG_LOG_LEVEL/INFO`, `OMX_OM/WritePayload`

---

## §9 Payload Build

```xml
<payload>
  <ns1:GetAccountHeaderRequest>
    <ns1:AccountIdInfo>
      <ns1:accountNo><!-- $orderRequest/OrderData/Customer/Account[$iAcc]/AccountID -->
                     <!-- $iAcc = number($i) + 1  (1-indexed from XSLT) --></ns1:accountNo>
    </ns1:AccountIdInfo>
  </ns1:GetAccountHeaderRequest>
</payload>
```

**JMS headers:** JMSPriority (conditional), JMSCorrelationID (conditional), OrderID (conditional), RefID ← refId (account-level), UserName/PassWord (credential-gated), OrderType (conditional), CES (ALT_CES routing)

---

## §10 XSLT Field Mapping Tree

```text
event
├── JMSPriority          ← $orderRequest/OrderPriority                          [Conditional]
├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId               [Conditional]
├── OrderID              ← $orderRequest/OrderData/OrderID                      [Conditional]
├── RefID                ← $refId (Account[i].RefId)                           [Always]
├── UserName             ← $orderRequest/OrderData/User                         [Credential-gated]
├── PassWord             ← $orderRequest/OrderData/Password                     [Credential-gated]
├── OrderType            ← $orderRequest/OrderData/OrderType                    [Conditional]
├── CES                  ← ExtendedInfo[ALT_CES]/Value (if altParam=Y && not-blank) else OrderData/CES  [Conditional]
└── payload
    └── ns1:GetAccountHeaderRequest
        └── ns1:AccountIdInfo
            └── ns1:accountNo  ← Customer/Account[$iAcc]/AccountID             [Always; $iAcc = i+1]
```

---

## §11 Audit Logging

**Request audit** — inside per-account `if(chkRes="true")` block:

| Field | Value |
|-------|-------|
| OPERATION_NAME | `$orderCurrentActivity/ActivityID` (dynamic) |
| AUDIT_TRACE | `concat("Request Sent for ", $orderCurrentActivity/ActivityID)` |
| PROCESS_ID | `concat(nanoTime(), "_REQ")` |

**Response audit:** same pattern with `_RES` suffix.

---

## §15 Function Dependency Tree

```text
Request_CCBS_GET_ACCOUNT_HEADER (rule)
├── Instance.getByExtIdByUri(NextActivityName, Activity)   [nextAct]
├── GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")
├── [if isActResub]: IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── [for i=0..iAcctLen-1]:
│   ├── Resubmit skip: check Response[iResp].ReferenceId + CompletionStatus==2
│   ├── GetXMLForAccount(orderRequest, refId)   [per-account XML context for PreExecCheck]
│   ├── XPath.execute(PreExecCheck, sXML, ...)
│   ├── [if chkRes="true"]:
│   │   ├── Event.createEvent(CCBS_GET_ACCOUNT_HEADER XSLT)
│   │   │   └── GetAccountHeaderRequest/AccountIdInfo/accountNo ← Account[$iAcc]/AccountID
│   │   ├── Event.assertEvent(reqEvent)   ← queued, NOT fired yet
│   │   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   │   └── Event.Ext.sendEventImmediate(Logger)
├── [if !isSkipped]:
│   ├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)   ← fires first request
│   ├── GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [if isSkipped]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_CCBS_GET_ACCOUNT_HEADER (rulefunction, 484 lines)
├── [for i=0..allAcctLength-1 where Account[i].RefId == eventResponse.RefID]:
│   ├── Instance.getByExtIdByUri("A:"+trackId+":"+RefID, Account)
│   ├── acct.OpenDate ← XPath.evalAsDateTime(AccountGeneralInfo/OpenDate)
│   ├── [if AccountManagementInfo == null]:
│   │   └── Instance.createInstance(AccountManagementInfo XSLT)
│   │       extId = "AMI:"+trackId+":"+RefID
│   │       Fields: CompanyCode, CreditClass, CreditLimitWaiverExpDate, CreditLimitWaiverInd,
│   │               PersonalCreditLimit, AccountSubType, tempCreditLimit, tempCreditLimitExpDate, PersonalClUpdDate
│   ├── [if blank]: CompanyCode, CreditClass, AccountSubType, CreditLimitWaiverInd, PersonalClUpdDate
│   ├── [if 0.0]:   PersonalCreditLimit, tempCreditLimit
│   ├── [if null]:  tempCreditLimitExpDate, CreditLimitWaiverExpDate
│   ├── [always]:   ConvergenceCode, CharityCode, AccountPriority, CompanyCode (overwrite)
│   ├── ExtendedInfo append x4: CHARITY_CODE, CONVERGENT_CODE, COL_STATUS, OLD_PERSONAL_CREDITLIMIT
│   ├── [if GET_NAME_ADDRESS gate]:
│   │   ├── Bootstrap AccountNames if null
│   │   ├── [if NameInfo/NameType==73]: INDY (NE1-NE10 → Title..Identification) [ClearField-safe]
│   │   ├── [else]: CORP (NE1-NE8 → OrgName..Identification) [ClearField-safe]
│   │   ├── Extended contact (LinkType=70): NE1-NE10 [ClearField-safe]
│   │   │   Language, PrefContactNumber, HomePhone, BizPhone, privatePhone,
│   │   │   AuthFirstName, AuthLastName, AuthPersonalId(NE8), POAName(NE9), POAPersonalId(NE10)
│   │   └── AccountAddress (AE1-AE15): HouseNo..subSoi [ClearField-safe]
│   │       *** BUG at AE11(Zip): ClearField check uses City field instead of Zip ***
│   ├── [if PAY_CHANNEL_FEE=Y && LinkType=84 exists && no PayChannelFeeInfo]:
│   │   └── Instance.createInstance(PayChannelFeeInfo XSLT)
│   │       NE7→BankAccountNo, NE6→BankBranchNo, NE5→BankCode, NE4→CreditCardExpirationDate
│   │       NE2→CreditCardNo, NE1→CreditCardType, NE3→CreditCardName
├── [if Customer.CustomerId==null]: ← AccountHeader/CustomerIdInfo/CustomerNo
├── [if ParentOU@length > 0]:
│   ├── Loop POU (i): match by AgreementRefId → set Agreement.AgreementId/AgreementType
│   │   ├── NumberOfIDD: L9IDDIndicator=78(ASCII N)→0; =89(ASCII Y)→1
│   │   └── NumberOfIR: L9IRIndicator=78(ASCII N)→0; =89(ASCII Y)→1
│   └── Loop COU (j): same Agreement + IDD/IR logic
├── [if ParentOU@length == 0]: create ParentOU[0] with AgreementId + Agreement
├── Instance.createInstance(CCBS_GetAccountHeaderRes XSLT)  [large — full AccountHeader snapshot]
├── currActivity.Response[len] = activityRes
├── Event.Ext.sendEventImmediate(Logger)
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
```

---

## §17 Migration Notes & Recommendations

### BUG — HIGH severity (Response rulefunction, line 306): Zip ClearField uses wrong field

```java
// Expected logic:
if(BRMS.IsBlank(AccountAddress.Zip))
    AccountAddress.Zip = AE11;  // sets Zip if blank
else if(String.equals(String.toUpperCase(AccountAddress.Zip), ClearField))  // ← SHOULD be Zip
    AccountAddress.Zip = null;

// Actual code (BUG):
else if(String.equals(String.toUpperCase(AccountAddress.City), ClearField))  // ← reads City (WRONG)
    AccountAddress.Zip = null;  // nulls Zip based on City value
```

**Impact:** If City equals the ClearField sentinel (e.g., "CLEAR"), Zip is incorrectly nulled. If Zip equals ClearField, it is NOT cleared as intended. Downstream processes relying on Zip being null when cleared will receive incorrect data.

**Fix:** Change `AccountAddress.City` to `AccountAddress.Zip` in the else-if branch.

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | IntraActivitySequencing fan-out: one CCBS GetAccountHeader request per Account (throttled sequential) |
| R2 | Per-account PreExecCheck using `GetXMLForAccount()` (account-scoped XML context) |
| R3 | ALT_CES routing via activity parameter + OrderData/ExtendedInfo |
| R4 | Credential gate via `IsEnableUserPass` global variable |
| R5 | AccountManagementInfo bootstrap if null; all fields updated with IsBlank guards |
| R6 | GET_NAME_ADDRESS gate: INDY (NameType=73) or CORP; Extended contact (LinkType=70); AccountAddress (AE1-AE15); all ClearField-safe |
| R7 | PAY_CHANNEL_FEE=Y: map PayChannelFeeInfo from NameAddressInfoList[LinkType=84] |
| R8 | Customer.CustomerId bootstrap if null (from AccountHeader/CustomerIdInfo/CustomerNo) |
| R9 | AgreementId/AgreementType resolution: POU and COU loops; create Agreement concept if missing |
| R10 | NumberOfIDD / NumberOfIR: L9IDDIndicator=78(N)→0; =89(Y)→1; same for IR |
| R11 | ParentOU bootstrap if ParentOU@length==0: create minimal ParentOU + Agreement from L9AgreementId |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| BUG: Zip ClearField check uses City field (response line 306) | [HIGH] | Fix: change `AccountAddress.City` to `AccountAddress.Zip` in the else-if branch |
| IntraActivitySequencing is a TIBCO-proprietary pattern — no direct equivalent in most target platforms | [HIGH] | Replace with explicit per-account parallel fan-out with response aggregation; or sequential async loop |
| Double ClearField re-reads (XPath per field) — high call volume for large Account arrays | [MEDIUM] | Materialise ClearField once per response handler invocation |
| Namespace variants: same field (e.g., L9CompanyCode) accessed via different namespace prefixes in different XPath calls | [MEDIUM] | Normalise to a single namespace resolution strategy in migration |
| LinkType=70 for extended contact (this FM) vs LinkType=69 in CCBS_GET_CUSTOMER_HEADER | [MEDIUM] | Verify correct LinkType per CCBS API; document in migration data dictionary |

### Extended Contact vs CCBS_GET_CUSTOMER_HEADER Comparison

| Field | This FM (LinkType=70) | CCBS_GET_CUSTOMER_HEADER (LinkType=69) |
|-------|-----------------------|----------------------------------------|
| NE8 | AuthPersonalId **(CORRECT)** | AuthLastName **(BUG — should be AuthPersonalId)** |
| LinkType | 70 | 69 |

---

## §18 Full Source Code (Request Rule)

```java
/**
 * Request_CCBS_GET_ACCOUNT_HEADER
 * Author: awalia-t420 | Priority: 5 | forwardChain: true
 * Pattern: IntraActivitySequencing per Account
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_ACCOUNT_HEADER {
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Activity nextAct = Instance.getByExtIdByUri(NextActivityName, ...);
      String altParam = GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES");
      int iAcctLen = orderRequest.OrderData.Customer.Account@length;

      if(isActResub)
        IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

      boolean isSkipped = true;
      for(int i=0; i < iAcctLen; i++) {
        String refId = orderRequest.OrderData.Customer.Account[i].RefId;
        boolean reqSuccess = false;
        for(int iResp=0; ...) if(Response[iResp].ReferenceId==refId && CompletionStatus==2) reqSuccess=true;
        if(!reqSuccess) {
          String chkRes = "true";
          if(String.length(nextAct.PreExecCheck) > 0) {
            String sXML = GetXMLForAccount(orderRequest, refId);
            chkRes = XPath.execute("/("+chkXPath+")", sXML, ...);
          }
          if(String.equals(chkRes, "true")) {
            /* XSLT — see §9 — GetAccountHeaderRequest/AccountIdInfo/accountNo
               ← Account[$iAcc]/AccountID  ($iAcc = i+1)
               Headers: JMSPriority, JMSCorrelationID, OrderID, RefID, UserName(?), PassWord(?), OrderType, CES */
            Event.assertEvent(reqEvent);  // queued — NOT fired yet
            IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
            Event.Ext.sendEventImmediate(Logger);
            isSkipped = false;
          }
        }
      }
      if(!isSkipped) {
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else
        SkipActivity(orderRequest, orderCurrentActivity, "4");
    } catch(Exception ae) {
      HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 Response Message Rule

> This rulefunction is 484 lines — the largest response handler seen so far. The summary below covers all logical sections.

### §19.1 Overview

Parses CCBS AccountHeader response and enriches the Account concept in multiple phases: AccountManagementInfo bootstrap → Name enrichment (INDY/CORP) → Extended contact → Address → PAY_CHANNEL_FEE → Customer.CustomerId bootstrap → AgreementId resolution (POU/COU) → raw CCBS_GetAccountHeaderRes concept creation. Returns via `IntraActivitySequencing.ActionResponseEvent()` (true = all accounts done).

### §19.3 AccountManagementInfo Fields

| BE Field | CCBS Source (L9* field) | Guard |
|----------|------------------------|-------|
| CompanyCode | L9CompanyCode | IsBlank then always overwrite |
| CreditClass | L9CreditClass | IsBlank |
| PersonalCreditLimit | L9PrsnlCreditLimit | == 0.0 |
| AccountSubType | L9AccSubType | IsBlank |
| tempCreditLimit | L9TempCreditLimit | == 0.0 |
| tempCreditLimitExpDate | L9CreditLimitExpDate | == null |
| CreditLimitWaiverInd | L9CreditLimitWaiverInd | IsBlank |
| PersonalClUpdDate | L9PersonalClUpdDate | IsBlank |
| CreditLimitWaiverExpDate | L9CreditLimitWaiverExpDate | == null |
| ConvergenceCode | L9ConvergenceCode | Always overwrite |
| CharityCode | L9AtbCharityCode | Always overwrite |
| AccountPriority | L9AccountPriority | Always overwrite (OMX-980) |

### §19.3b Account ExtendedInfo (always appended)

| Name | Source |
|------|--------|
| CHARITY_CODE | L9AtbCharityCode |
| CONVERGENT_CODE | L9ConvergenceCode |
| COL_STATUS | L9ColStatus |
| OLD_PERSONAL_CREDITLIMIT | L9PrsnlCreditLimit (added 26 Dec 2018) |

### §19.3c Name Mapping (GET_NAME_ADDRESS gate)

| NameElement | INDY (NameType=73) | CORP (other) | Extended Contact (LinkType=70) |
|-------------|-------------------|--------------|-------------------------------|
| NE1 | Title | OrgName | Language |
| NE2 | FirstName | BranchCode | PrefContactNumber |
| NE3 | MiddleName | BranchName | HomePhone |
| NE4 | LastName | StoreId | BizPhone |
| NE5 | MaritalStatus | FaxNumber | privatePhone |
| NE6 | FaxNumber | Email | AuthFirstName |
| NE7 | Email | IdentificationType | AuthLastName |
| NE8 | Gender | Identification | **AuthPersonalId** ✓ (correct) |
| NE9 | IdentificationType | — | POAName |
| NE10 | Identification | — | POAPersonalId |

### §19.3d Address Mapping (GET_NAME_ADDRESS gate)

| AddressElement | BE Field | Note |
|----------------|----------|------|
| AE1 | HouseNo | |
| AE2 | Moo | |
| AE3 | RoomNo | |
| AE4 | Floor | |
| AE5 | BuildingName | |
| AE6 | Soi | |
| AE7 | StreetName | |
| AE8 | Tumbon | |
| AE9 | Amphur | |
| AE10 | City | |
| AE11 | Zip | **BUG: ClearField check uses City instead of Zip** |
| AE12 | Country | |
| AE13 | TimeAtAddress | |
| AE14 | TypeOfAccomodation | |
| AE15 | subSoi | |

### §19.4 Fan-in Completion

`IntraActivitySequencing.ActionResponseEvent(currActivity)` → `"true"` when all accounts have responded; `"false"` while more are pending.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
