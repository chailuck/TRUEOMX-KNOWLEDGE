# Request_CCBS_CREATE_ACCT

## §1 Overview & Purpose

**CCBS_CREATE_ACCT** creates one CCBS Account per `Customer.Account[]` entry. It is the most comprehensive Account-level creation call in the ACTIVATION flow, building a full `CreateNewAccountRequest` payload: AccountNameInfo (CORP/INDY/other dispatch), AccountAddressInfo, AccountingManagementInfo, BillingArrangementInfo, PayChannel details, and ActivityInfo.

> **Iteration scope:** Loops `Customer.Account[]` (not POU/ChildOU). Each Account may correspond to a separate billing cycle. The XSLT resolves the linked Agreement ID via the Account's `AgreementRefId` field.

> **AccountNameInfo dispatch:** 3-way branch on `Account.AccountNames.NameType`: CORP (nameType 66, 69, optional 67), INDY (nameType 73, 69, optional 67), or default (nameType 69 only + optional 67).

> **Response writes:** AccountID, PayChannelId, BillingArrangementId written back per Account. After success, appends `omxCreatedAccountInd="Y"` to `orderRequest.OrderData.ExtendedInfo[]`.

> **OrderType=31 special logic:** On success, writes `ParentOU[0].Subscriber[0].PayChannelIdSecondary = Account[0].AccountID`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CREATE_ACCT` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS |
| Event type | `Events.OMConsumers.OMXFM.Request.CCBS_CREATE_ACCT` |
| Response event | `Events.OMConsumers.OMXFM.Response.CCBS_CREATE_ACCT` |
| Send pattern | `Event.assertEvent` + `IntraActivitySequencing` per Account |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Iteration target | `Customer.Account[]` (one event per Account) |
| Response concept | `Concepts.FM.Response.CCBSCreateAcctRes` |
| Payload operation | `ns:CreateNewAccountRequest` |

---

## §7 Data Extractions & Priority Chains

| Field | Priority Chain | Notes |
|-------|---------------|-------|
| `L9AccSubType` | CUST_SUB_TYPE ExtInfo → AccountSubType | ExtInfo via `count(ExtendedInfo[Name='CUST_SUB_TYPE'])>0` |
| `L9AccountPriority` | OrderType 8/9: AccountPriority → PRIORITY ExtInfo | OrderType-specific path |
| `L9AgreementId` | POU.Agreement[RefId=AgreementRefId].AgreementId → ChildOU.Agreement[...].AgreementId | Resolved via Account.AgreementRefId |
| `L9CompanyCode` | COMPANY_CODE ExtInfo → CompanyCode | ExtInfo takes precedence |
| `L9CreditClass` | AccountManagementInfo.CreditClass | **SUPPRESSED for OrderType=48** |
| `L9CreditLimitWaiverInd` | "U" if AccSubType starts "HY" OR Grading=TOP/PREMIUM → CreditLimitWaiverInd | HY/top-tier forces waiver |
| `L9CustBranchNo / L9CustTaxId` | BranchNumber / TaxId — suppressed if CustomerTypeInfo.Type=73 AND concat(TaxId,BranchNumber)="000000000000000000" | 18-zero sentinel |
| `activityReason` | AccountActivityInfo.ActivityReason → "CREQ" | Standard default |
| `l3BillFormat` | BillingArrangementBillInfo.BillFormat → "P" | Default = paper |
| `l9BillLang` | BillingArrangementBillInfo.BillLanguage → "TH" | Default = Thai |
| `paymentCategory` | Account.PayChannelCategory → "POST" | Default = postpaid |
| `paymentMethod` | PayChannelPaymentMethodInfo.PaymentMethod → "CA" | Default = cash |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority / JMSCorrelationID / OrderID   ← standard order fields    [Conditional]
├── RefID                                       ← Account[i].RefId          [Conditional]
├── UserName / PassWord                         ← User / Password           [Credential-gated: IsEnableUserPass='true']
├── OrderType / CES                             ← standard order fields     [Conditional]
└── payload → ns:CreateNewAccountRequest
    ├── ns:CustomerIdInfo → customerNo          ← Customer.CustomerId       [Always]
    ├── ns:AccountExternalIdInfo → externalId   ← EXTERNAL_ID ExtInfo       [Conditional: exists]
    │
    ├── ns:AccountNameInfo (3-way choice on AccountNames.NameType)
    │   ├── CORP branch:
    │   │   ├── nameType=66: element1-8 ← OrgName/BranchCode/BranchName/StoreId/FaxNumber/Email/IdentificationType/Identification; linkType=65
    │   │   ├── nameType=69: element1-10 ← Language/PrefContactNumber/HomePhone/BizPhone/privatePhone/AuthFirstName/AuthLastName/AuthPersonalId/POAName/POAPersonalId; linkType=70
    │   │   └── nameType=67 (PayChannelFeeInfo, if exists): element1-7 ← CreditCardType/CreditCardNo/CreditCardName/CreditCardExpirationDate/BankCode/BankBranchNo/BankAccountNo; linkType=84
    │   ├── INDY branch:
    │   │   ├── nameType=73: element1-10 ← Title/FirstName/MiddleName/LastName/MaritalStatus/FaxNumber/Email/Gender/IdentificationType/Identification; linkType=65
    │   │   ├── nameType=69: element2 PrefContactNumber (no xsl:if guard in INDY); linkType=70
    │   │   └── nameType=67 (optional, same as CORP)
    │   └── Otherwise branch:
    │       ├── nameType=69: nameElement2 ← PrefContactNumber (no guard); linkType=70
    │       └── nameType=67 (optional)
    │
    ├── ns:AccountAddressInfo (if Account.AccountAddress exists):
    │   ├── addressType ← 66                                                [Always]
    │   ├── addressElement1-15 ← HouseNo/Moo/RoomNo/Floor/BuildingName/Soi/StreetName/Tumbon/Amphur/City/Zip/Country/TimeAtAddress/TypeOfAccomodation/subSoi
    │   │   (fallback to Customer.CustomerAddress for each element)
    │   └── linkType ← 65
    │
    ├── ns1:AccountingManagementInfo (foreach Account.AccountManagementInfo):
    │   ├── L9AccSubType     ← CUST_SUB_TYPE ExtInfo → AccountSubType
    │   ├── L9AccountPriority ← OrderType 8/9: AccountPriority; else PRIORITY ExtInfo  [Conditional]
    │   ├── L9AgreementId    ← POU/ChildOU Agreement lookup                [Conditional: AgreementID non-empty]
    │   ├── L9CompanyCode    ← COMPANY_CODE ExtInfo → CompanyCode          [Conditional]
    │   ├── L9CreditClass    ← CreditClass                                 [Conditional: NOT OrderType=48]
    │   ├── L9CreditLimitRsnCode ← CreditLimitReasonCode                   [Conditional]
    │   ├── L9CreditLimitWaiverExpDate ← CreditLimitWaiverExpDate          [Conditional]
    │   ├── L9CreditLimitWaiverInd ← "U" if HY/TOP/PREMIUM; else CreditLimitWaiverInd
    │   ├── L9CustBranchNo   ← BranchNumber (suppressed by 18-zero sentinel)
    │   ├── L9CustTaxId      ← TaxId (suppressed by 18-zero sentinel)
    │   ├── L9InitiationReason ← INIT_REASON ExtInfo                       [Conditional: exists and count>0]
    │   ├── L9LegacyBan      ← LEGACY_BAN ExtInfo                          [Conditional]
    │   ├── L9PrsnlCreditLimit ← 0.0                                       [Always — HARDCODED]
    │   ├── L9SpecialInstructions ← SPECIAL_INSTRUCTION ExtInfo            [Conditional]
    │   ├── L9WHTCertiNo     ← WHTCertiNo                                  [Conditional: exists]
    │   ├── L9WHTInd         ← whtInd                                      [Conditional: exists and !=0]
    │   └── L9WhtTaxUpDate   ← whtTaxUpDate                                [Conditional: exists]
    │
    ├── ns:BillingArrangementBillInfo:
    │   ├── l3BillFormat     ← BillFormat → "P"
    │   └── l9BillLang       ← BillLanguage → "TH"
    │
    ├── ns:BillingArrangementNameInfo (3-way: CORP 66+69, INDY 73+69)      [Conditional: NameType present]
    ├── ns:BillingArrangementAddressInfo                                    [foreach BillingArrangementAddress]
    │   ├── addressType      ← 66 (CORP) or 73 (INDY/other)
    │   └── linkType         ← 66
    │
    ├── ns:PayChannelPaymentCategoryInfo → paymentCategory ← PayChannelCategory → "POST"
    ├── ns:PayChannelDescriptionInfo → description ← PayChannelDescription → "POSTPAID"
    ├── ns:PayChannelPaymentMethodInfo:
    │   ├── paymentMethod    ← PaymentMethod → "CA"
    │   ├── issueDate / bankCode / bankAccountNo / bankAccountType          [Conditional]
    │   ├── creditCardType / creditCardNo / creditCardExpirationDate        [Conditional]
    │   └── paymentMeansOwnerDetails / l9BankName / l9DDApprovalDate / l9BankBranchName [Conditional]
    │
    ├── ns:ActivityInfo:
    │   ├── activityReason   ← AccountActivityInfo.ActivityReason → "CREQ" [Always]
    │   └── userText         ← AccountActivityInfo.UserText                 [Conditional]
    │
    └── ns:ActivityDateInfo → activityDate ← EffectiveDate                 [Conditional: non-empty]
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_CREATE_ACCT
├── [if resubmit] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── Instance.getByExtIdByUri("LogicalDate", ...) [read but logicalDateVal unused in XSLT — dead code]
├── for each Account[i]:
│   ├── [skip if Response[ReferenceId==Account[i].RefId AND CompletionStatus==2] exists]
│   ├── AccountSubType = XPath.evalAsString(Account[i].AccountManagementInfo.AccountSubType)
│   ├── GetXMLForAccount(orderRequest, Account[i].RefId)
│   ├── XPath.execute(PreExecCheck, sXML)  [if PreExecCheck length > 0]
│   ├── Event.createEvent(CCBS_CREATE_ACCT, full XSLT)
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│   └── sendEventImmediate(Logger REQ — OPERATION_NAME=activityID)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
└── SendDataToDB(orderRequest)

Response_CCBS_CREATE_ACCT
├── for each Account[i]: if Account[i].RefId == eventResponse.RefID:
│   ├── Account[i].AccountID ← AccountBaPcnIdsInfo/AccountIdsInfo/AccountId/AccountNo
│   ├── Account[i].PayChannelId ← AccountBaPcnIdsInfo/PayChannelIdsInfo/PayChannelId/PayChannelId
│   ├── Account[i].BillingArrangementId ← AccountBaPcnIdsInfo/BillingArrangementIdsInfo/.../BillingArrangementId
│   └── Account[i].ResponseCode, ResponseMsg ← eventResponse
├── [if OrderType=31] ParentOU[0].Subscriber[0].PayChannelIdSecondary = Account[0].AccountID
├── Instance.createInstance(OrderDataExtendedInfo: Name="omxCreatedAccountInd", Value="Y")
│   → append to orderRequest.OrderData.ExtendedInfo[]
├── Instance.createInstance(CCBSCreateAcctRes: ResponseCode, ResponseMessage, CompletionStatus, ReferenceId)
│   → currActivity.Response[n] = activityRes
├── sendEventImmediate(Logger RES — OPERATION_NAME="CCBS_CREATE_ACCT")
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
[OLD fan-in commented out: count accounts with empty AccountID==0 → "true"]
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| OrderType=31: PayChannelIdSecondary set from Account[0] — hardcoded array index | [MEDIUM] | Verify multiple-account assumption; document as business rule |
| L9PrsnlCreditLimit hardcoded to 0.0 — always sent as zero | [MEDIUM] | Confirm with CCBS; field may be vestigial |
| 18-zero TaxId+BranchNumber sentinel suppresses L9CustBranchNo and L9CustTaxId | [LOW] | Preserve sentinel detection in migration |
| OrderType=48 silently suppresses L9CreditClass | [LOW] | Document exception; test with CreditClass orders |
| omxCreatedAccountInd="Y" appended per response — may duplicate on multiple accounts | [LOW] | Verify downstream reads first-or-last; deduplicate if needed |
| Old "count pending accounts" fan-in commented out — dead code | [LOW] | Remove in migration target |

---

## §19 Response Message Rule

Matches by `Account[i].RefId == eventResponse.RefID`. Writes three CCBS-assigned IDs from `AccountBaPcnIdsInfo`. Also unconditionally appends `omxCreatedAccountInd="Y"` to order-level ExtendedInfo.

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `Account[i].AccountID` | `AccountBaPcnIdsInfo/AccountIdsInfo/AccountId/AccountNo` | Account[i].RefId == eventResponse.RefID |
| `Account[i].PayChannelId` | `AccountBaPcnIdsInfo/PayChannelIdsInfo/PayChannelId/PayChannelId` | same match |
| `Account[i].BillingArrangementId` | `AccountBaPcnIdsInfo/BillingArrangementIdsInfo/BillingArrangementId/BillingArrangementId` | same match |
| `ParentOU[0].Subscriber[0].PayChannelIdSecondary` | `Account[0].AccountID` | OrderType="31" only |
| `orderRequest.OrderData.ExtendedInfo[]` | Name="omxCreatedAccountInd", Value="Y" | Always (every account response) |

Fan-in: `IntraActivitySequencing.ActionResponseEvent(currActivity)` — returns "true" when all outstanding account requests answered.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
