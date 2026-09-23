# Request_CCBS_UPDATE_ACCOUNT_NAME_ADDRESS

> Updates CCBS account name and address per Account (not per subscriber). Uses a 3-branch NameType dispatch (CORP/INDY/default) to build up to three ns:nameInfo blocks. Uses IntraActivitySequencing + LogicalDate. Fan-out unit is Account[], not OU/subscriber.

**Backend:** CCBS (UpdateNameAddress) | **Pattern:** Per-Account / IntraActivitySequencing | **RefID:** Account RefId | **forwardChain:** true | **Author:** SathidP-PC | **Used in step:** 75

---

## §1 — Overview & Purpose

Sends one **CCBS UpdateNameAddressRequest** per Account in `OrderData.Customer.Account[]`. This is distinct from all other FMs in the POSTPAID_ADD_OFFER_SUB flow: the fan-out unit is the *Account*, not a subscriber or OU. The payload varies by `AccountNames.NameType`: corporate accounts (CORP), individual accounts (INDY), or a contact-number-only default. Each can carry up to three `ns:nameInfo` blocks: the primary name block, an extended info block (conditional on `isExtendedNameInfoExist`), and a payment channel block (conditional on `PayChannelFeeInfo`).

- **Fan-out unit:** `OrderData.Customer.Account[]` — one request per account
- **RefID:** `accRefId` (Account RefId — not subscriber RefId)
- **PreExecCheck builder:** `GetXMLForAccount(orderRequest, accRefId)` — account-level context
- **Dispatch:** IntraActivitySequencing (assertEvent → ActionRequestEvent → SendFirstRequestEvent)
- **LogicalDate:** Read from BE concept and USED in ns:enclosedClientInfo and ns:ActivityDateInfo
- **isExtendedNameInfoExist:** computed in BE rule body before XSLT — "true" if ANY of 10 AccountNames extension fields is non-blank
- **NameType dispatch:** CORP → nameType=66, INDY → nameType=73, default → nameType=69 (contact only)
- **UserName/Password:** gated by global variable `IsEnableUserPass='true'` (not the standard order data guard)
- **Response:** dedicated `CCBS_UpdateAccountNameAddress` concept; fan-in via ActionResponseEvent

> **[INFO] This FM fans out per Account, not per subscriber.** If an order has multiple accounts, one request is sent per account. The PreExecCheck context is account-level (`GetXMLForAccount`) — different from the subscriber-level context used in CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO.

> **[INFO] logicalDateVal is used here (unlike CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO).** It is passed to XSLT and emitted in two places: `ns:activityInfo/ns:enclosedClientInfo/ns:logicalDate` and `ns:ActivityDateInfo/ns:activityDate` — both conditional on non-blank trimmed value.

> **[LOW] UserName/Password gated by global variable IsEnableUserPass:** Unlike other CCBS FMs that gate on `$orderRequest/OrderData/User`, this FM checks `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass='true'`. If this flag is absent/false, credentials are never sent regardless of order data.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_CCBS_UPDATE_ACCOUNT_NAME_ADDRESS.rule` | 92 lines |
| Author | SathidP-PC | |
| Priority | 5 | |
| forwardChain | true | |
| Backend event | `Events.OMConsumers.OMXFM.Request.CCBS_UPDATE_ACCOUNT_NAME_ADDRESS` | Dedicated |
| Payload root | `ns:UpdateNameAddressRequest` | |
| Schema NS (ns) | `http://services.omx.truecorp.co.th/FM/UpdateNameAddressRequest` | Different domain from ESB schemas |
| Fan-out unit | `OrderData.Customer.Account[]` | Per account — NOT per subscriber/OU |
| RefID | `accRefId` (Account RefId) | Always emitted |
| Resub guard | `Response[ReferenceId == accRefId && CompletionStatus==2]` | Account-level |
| PurgePendingRequestsBeforeResubmit | ✓ PRESENT | Called on resubmit |
| PreExecCheck builder | `GetXMLForAccount(orderRequest, accRefId)` | Account-level context |
| isExtendedNameInfoExist | Computed in BE body: "true" if ANY of 10 extension fields non-blank | Controls second nameInfo block |
| LogicalDate usage | READ AND USED in ns:enclosedClientInfo + ns:ActivityDateInfo | Unlike CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO |
| Dispatch method | `Event.assertEvent + IntraActivitySequencing.ActionRequestEvent` | sendEventImmediate commented out |
| Send trigger | `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)` | |
| UserName/Password gate | Global variable `IsEnableUserPass='true'` | Not standard OrderData.User guard [LOW] |
| Response concept | `Concepts.FM.Response.CCBS_UpdateAccountNameAddress` | Dedicated — extId from pre-generated OMXUtils |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` | Standard fan-in commented out |
| OPERATION_NAME (request) | `$orderCurrentActivity/ActivityID` (dynamic) | |
| OPERATION_NAME (response) | `"CCBS_UPDATE_ACCOUNT_NAME_ADDRESS"` | Hardcoded |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_UPDATE_ACCOUNT_NAME_ADDRESS"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_UPDATE_ACCOUNT_NAME_ADDRESS"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §7 — NameType-Based Payload Dispatch Logic

| NameType | Primary nameInfo (nameType) | Name Fields | Extended Info Block | linkType |
|----------|----------------------------|-------------|---------------------|----------|
| `"CORP"` | 66 (Corporate) | OrgName(1), BranchCode(2), BranchName(3), StoreId(4), FaxNumber(5), Email(6), IdentificationType(7), Identification(8) | nameType=69 if isExtendedNameInfoExist='true' (10 fields) | 65 |
| `"INDY"` | 73 (Individual) | Title(1), FirstName(2), MiddleName(3), LastName(4), MaritalStatus(5), FaxNumber(6), Email(7), Gender(8), IdentificationType(9), Identification(10) | nameType=69 if isExtendedNameInfoExist='true' (10 fields) | 65 |
| otherwise | 69 (Extended/Contact) | Only nameElement2=PrefContactNumber | None | 70 |

### Extended nameInfo Block (nameType=69) — when isExtendedNameInfoExist='true' (CORP and INDY only)

| nameElement | Source field |
|-------------|-------------|
| nameElement1 | AccountNames.Language |
| nameElement2 | AccountNames.PrefContactNumber |
| nameElement3 | AccountNames.HomePhone |
| nameElement4 | AccountNames.BizPhone |
| nameElement5 | AccountNames.privatePhone |
| nameElement6 | AccountNames.AuthFirstName |
| nameElement7 | AccountNames.AuthLastName |
| nameElement8 | AccountNames.AuthPersonalId |
| nameElement9 | AccountNames.POAName |
| nameElement10 | AccountNames.POAPersonalId |

### Payment Channel nameInfo Block (nameType=67) — when exists(PayChannelFeeInfo) — all NameType branches

| nameElement | Source field | Guard |
|-------------|-------------|-------|
| nameElement1 | PayChannelFeeInfo.CreditCardType | xsl:if |
| nameElement2 | PayChannelFeeInfo.CreditCardNo | xsl:if |
| nameElement3 | PayChannelFeeInfo.CreditCardName | xsl:if |
| nameElement4 | PayChannelFeeInfo.CreditCardExpirationDate | xsl:if |
| nameElement5 | PayChannelFeeInfo.BankCode | xsl:if |
| nameElement6 | PayChannelFeeInfo.BankBranchNo | xsl:if |
| nameElement7 | PayChannelFeeInfo.BankAccountNo | xsl:if |
| nameUpdateType | 79 (hardcoded) | Always |
| linkType | 84 (hardcoded) | Always |

### CCBS Integer Code Reference

| Code | Field | Meaning |
|------|-------|---------|
| 66 | nameType | Corporate (CORP) name block |
| 67 | nameType | Payment channel / credit card block |
| 69 | nameType | Extended info / contact info block |
| 73 | nameType | Individual (INDY) name block |
| 65 | linkType | Primary link (account-level) |
| 70 | linkType | Extended/secondary link |
| 84 | linkType | Payment channel link |
| 79 | nameUpdateType / addressUpdateType | Override/update mode |
| 66 | addressType | Primary billing address |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

Account indexed as `$orderRequest/OrderData/Customer/Account[$i+1]` (1-based XSLT). Variable `$i` is the 0-based BE loop counter.

```text
createEvent
└── event
    ├── JMSPriority             ← $orderRequest/OrderPriority                            [Conditional]
    ├── JMSCorrelationID        ← $orderRequest/OrderData/OMXTrackingId                  [Conditional]
    ├── OrderID                 ← $orderRequest/OrderData/OrderID                        [Conditional]
    ├── RefID                   ← $accRefId                                              [Always]
    ├── UserName                ← $orderRequest/OrderData/User                           [Credential-gated: IsEnableUserPass='true' AND User present]
    ├── PassWord                ← $orderRequest/OrderData/Password                       [Credential-gated]
    ├── OrderType               ← $orderRequest/OrderData/OrderType                      [Conditional]
    ├── CES                     ← $orderRequest/OrderData/CES                            [Conditional]
    └── payload
        └── ns:UpdateNameAddressRequest  (ns=http://services.omx.truecorp.co.th/FM/UpdateNameAddressRequest)
            ├── ns:entityNo             ← $acccountId (Account.AccountID)                [Always]
            ├── [NameType dispatch — xsl:choose]
            │   ├── [CORP] ns:nameInfo  nameType=66
            │   │   └── OrgName(1), BranchCode(2), BranchName(3), StoreId(4),
            │   │       FaxNumber(5), Email(6), IdentificationType(7), Identification(8)
            │   │       nameUpdateType=79, linkType=65
            │   ├── [INDY] ns:nameInfo  nameType=73
            │   │   └── Title(1), FirstName(2), MiddleName(3), LastName(4), MaritalStatus(5),
            │   │       FaxNumber(6), Email(7), Gender(8), IdentificationType(9), Identification(10)
            │   │       nameUpdateType=79, linkType=65
            │   └── [otherwise] ns:nameInfo  nameType=69
            │       └── nameElement2=PrefContactNumber only; nameUpdateType=79, linkType=70
            ├── [CORP/INDY] ns:nameInfo  nameType=69  [Conditional: isExtendedNameInfoExist='true']
            │   └── Language(1), PrefContact(2), HomePhone(3), BizPhone(4), privatePhone(5),
            │       AuthFirst(6), AuthLast(7), AuthPersonalId(8), POAName(9), POAPersonalId(10)
            │       nameUpdateType=79, linkType=70
            ├── [all types] ns:nameInfo  nameType=67  [Conditional: exists(PayChannelFeeInfo)]
            │   └── CreditCardType(1), CreditCardNo(2), CreditCardName(3), ExpDate(4),
            │       BankCode(5), BranchNo(6), BankAccountNo(7)
            │       nameUpdateType=79, linkType=84
            ├── ns:addressInfo  [Conditional: exists(AccountAddress)]
            │   ├── addressType=66, addressUpdateType=79, linkType=65
            │   └── elements 1–15: HouseNo, Moo, RoomNo, Floor, BuildingName, Soi,
            │       StreetName, Tumbon, Amphur, City, Zip, Country,
            │       TimeAtAddress, TypeOfAccomodation, subSoi
            └── ns:activityInfo  [Always]
                ├── ns:activityReason    ← AccountActivityInfo.ActivityReason (tib:trim check) or "CREQ"  [Always]
                ├── ns:userText          ← AccountActivityInfo.UserText                                    [Conditional]
                ├── ns:enclosedClientInfo/ns:logicalDate ← $logicalDateVal                                [Conditional: tib:trim non-empty]
                └── ns:ActivityDateInfo/ns:activityDate  ← $logicalDateVal                                [Conditional: tib:trim non-empty]
```

---

## §15 — Function Dependency Tree

```text
Request_CCBS_UPDATE_ACCOUNT_NAME_ADDRESS (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── logicalDateRes = Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")
│   └── logicalDateVal = logicalDateRes.LogicalDate  ← USED in XSLT (unlike CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── if isActResub: PurgePendingRequestsBeforeResubmit(orderCurrentActivity)  ✓
├── [Account loop i]:
│   ├── accRefId = OrderData.Customer.Account[i].RefId
│   ├── [Resub guard]: Response[ReferenceId==accRefId && CompletionStatus==2]
│   ├── [PreExecCheck]: GetXMLForAccount(orderRequest, accRefId)  ← Account-level context
│   └── [if chkRes=="true"]:
│       ├── acccountId = Account[i].AccountID   ← [LOW] typo: 3 c's in variable name
│       ├── isExtendedNameInfoExist = "true" if ANY of (Language, PrefContactNumber, HomePhone,
│       │                            BizPhone, privatePhone, AuthFirstName, AuthLastName,
│       │                            AuthPersonalId, POAName, POAPersonalId) is non-blank
│       ├── Event.assertEvent(reqEvent)
│       ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│       ├── Logger (INFO level): OPERATION_NAME=$orderCurrentActivity/ActivityID
│       └── isSkipped = false
├── [if !isSkipped]:
│   ├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
│   ├── orderCurrentActivity.Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch]: HandleActivityException

Response_CCBS_UPDATE_ACCOUNT_NAME_ADDRESS (rulefunction)
├── extId = OMXUtils.generateTrackingID()  ← pre-generated, passed to XSLT as param
├── activityRes = Instance.createInstance(CCBS_UpdateAccountNameAddress)
│   ├── @extId ← $extId
│   ├── ResponseCode, ResponseMessage, CompletionStatus, ReferenceId (conditional)
├── currActivity.Response[] ← activityRes
├── Logger: OPERATION_NAME="CCBS_UPDATE_ACCOUNT_NAME_ADDRESS"
├── [NOTE] Standard RequestCount==successResponseCount block COMMENTED OUT
└── return IntraActivitySequencing.ActionResponseEvent(currActivity) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-Account fan-out: one UpdateNameAddressRequest per Account[]. RefID = Account.RefId. |
| R2 | PurgePendingRequestsBeforeResubmit called on resubmit. |
| R3 | isExtendedNameInfoExist computed in BE body: "true" if ANY of Language/PrefContactNumber/HomePhone/BizPhone/privatePhone/AuthFirstName/AuthLastName/AuthPersonalId/POAName/POAPersonalId is non-blank. |
| R4 | NameType dispatch: CORP → nameType=66, INDY → nameType=73, default → nameType=69 (contact-only). Each branch can add extended (nameType=69) and payment (nameType=67) blocks. |
| R5 | Address block emitted if exists(AccountAddress): 15 address elements, addressType=66, linkType=65. |
| R6 | activityInfo always emitted: activityReason = Account.AccountActivityInfo.ActivityReason or "CREQ". |
| R7 | logicalDateVal read from BE LogicalDate concept and passed to XSLT. Used in enclosedClientInfo and ActivityDateInfo when non-blank. |
| R8 | UserName/PassWord gated by global variable IsEnableUserPass='true' (not standard order data guard). |
| R9 | IntraActivitySequencing dispatch: assertEvent → ActionRequestEvent → SendFirstRequestEvent; fan-in via ActionResponseEvent. |
| R10 | Response uses dedicated CCBS_UpdateAccountNameAddress concept; extId from OMXUtils.generateTrackingID(). |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| UserName/Password gated by IsEnableUserPass global variable — inconsistent with other FMs | [MEDIUM] | Standardize credential gate; verify flag is set in all deployment environments |
| Schema domain is truecorp.co.th/FM/ not tibco.com/schemas — custom endpoint | [INFO] | Document separate schema ownership; confirm endpoint stability |
| CCBS integer codes (nameType, linkType, addressType) are undocumented magic numbers | [LOW] | Catalog in migration runbook: 66=CORP, 73=INDY, 69=EXT, 67=PayCh, 65=AccLink, 70=ExtLink, 84=PayLink, 79=Override |
| Variable name typo `acccountId` (3 c's) in BE body | [LOW] | Correct to `accountId` in modernized code; functional impact is cosmetic |

---

## §19 — Response Message Rule (Response_CCBS_UPDATE_ACCOUNT_NAME_ADDRESS)

### §19.3 CCBS_UpdateAccountNameAddress Construction

```text
createObject
└── object (Concepts.FM.Response.CCBS_UpdateAccountNameAddress)  [dedicated]
    ├── @extId           ← $extId (OMXUtils.generateTrackingID() — pre-generated)  [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode                              [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg                               [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus                          [Conditional]
    └── ReferenceId      ← $eventResponse/RefID                                     [Conditional]
```

### §19.4 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Standard fan-in | COMMENTED OUT |
| Active fan-in | `RuleFunctions.Helpers.IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Write-back | None |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
