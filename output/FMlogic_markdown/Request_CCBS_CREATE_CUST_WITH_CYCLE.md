# Request_CCBS_CREATE_CUST_WITH_CYCLE

## §1 Overview & Purpose

**CCBS_CREATE_CUST_WITH_CYCLE** creates a new customer record in CCBS, including identity, name (CORP or INDY), address, billing cycle, and general customer info. The response writes the new CCBS-assigned `CustomerNo` back to `Customer.CustomerId` and also populates BirthDate, Identification, CustomerTypeInfo, and (for qualifying order types) full name and address from the CCBS record.

> **LogicalDate concept:** Activity date falls back through 4 levels — OPEN_DATE ExtendedInfo → EffectiveDate → LogicalDate concept → current date.

> **Audit log mismatch:** Response audit log uses OPERATION_NAME = `"CCBS_CREATE_CUSTOMER_WITH_CYCLE"` (WITH_CYCLE, full word), while ActivityID is `"CCBS_CREATE_CUST_WITH_CYCLE"` (CUST). Migration must align these names.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CREATE_CUST_WITH_CYCLE` |
| Author | RS33-BANDIT |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS |
| Send pattern | `sendEventImmediate` — single request |
| LogicalDate | Read from `Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")` |
| Fan-in | Unconditional `return "true"` |
| Response namespace | `www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.CustomerHeader` |
| Response concept | `Concepts.FM.Response.CCBS_CreateCustomerWithCycleRes` |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — Customer written (CustomerId, BillCycleNo, NameInfo, AddressInfo) |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | ActivityID, RequestCount, Status, Parameter[1] |

---

## §7 Business Logic: Priority Chains

### ActivityDateInfo Priority

| Priority | Source | Condition |
|----------|--------|-----------|
| 1 | `Customer.ExtendedInfo[Name='OPEN_DATE']/Value` | OPEN_DATE present and non-empty |
| 2 | `OrderData.EffectiveDate` | EffectiveDate non-empty |
| 3 | `LogicalDate` concept → `concat(left(logicalDate,10), ' 00:00:00')` | LogicalDate non-empty |
| 4 | `current-date()` → `concat(left(current-date(),10), ' 00:00:00')` | Default |

### CustomerType Priority

| Priority | Source |
|----------|--------|
| 1 | `Customer.ExtendedInfo[Name='CUST_TYPE']/Value` |
| 2 | `Customer.CustomerTypeInfo.Type` |
| 3 | `73` (default) |

### CustomerSubtype Priority

| Priority | Source |
|----------|--------|
| 1 | `Customer.ExtendedInfo[Name='CUST_SUB_TYPE']/Value` |
| 2 | `Customer.CustomerTypeInfo.Subtype` |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority, JMSCorrelationID, OrderID  ← standard order fields   [Conditional]
├── RefID                                   ← Customer.RefId           [Conditional]
├── UserName / PassWord                     ← OrderData.User/Password  [Credential-gated: IsEnableUserPass='true']
├── OrderType, CES                          ← standard order fields    [Conditional]
└── payload → ns:CreateNewCustomerRequest
    ├── ns:CustomerTypeInfo
    │   ├── ns:customerType       ← CUST_TYPE Ext > CustomerTypeInfo.Type > 73  [Always]
    │   └── ns:customerSubtype    ← CUST_SUB_TYPE Ext > CustomerTypeInfo.Subtype[Conditional]
    ├── ns:NameInfo (CORP: nameType=66+69) OR (INDY: nameType=73+69)
    │   [CORP nameType=66: OrgName,BranchCode,BranchName,StoreId,FaxNumber,Email,IdentificationType,Identification]
    │   [INDY nameType=73: Title,FirstName,MiddleName,LastName,MaritalStatus,FaxNumber,Email,Gender,IdentificationType,Identification]
    │   [Both: linkType=67 for primary; nameType=69 linkType=67 for extended contact]
    ├── ns:AddressInfo
    │   [elem1=HouseNo, elem2=Moo, elem3=RoomNo, elem4=Floor, elem5=BuildingName,
    │    elem6=Soi, elem7=StreetName, elem8=Tumbon, elem9=Amphur, elem10=City,
    │    elem11=Zip, elem12=Country, elem13=TimeAtAddress(CORP only), elem14=TypeOfAccomodation, elem15=subSoi]
    │   [addressType: CORP=66, INDY=73, else=0; linkType=67]
    ├── ns:customerBillingCycleInfo
    │   └── billCycleNo           ← Customer.BillCycleNo              [Conditional: BillCycleNo present]
    ├── ns1:CustomerGeneralInfo
    │   [DealerCode, BirthDate, contactLang, Grading, Identification,
    │    IdentificationExpDate (order value > globalVar OMX_CreateCust/IdentificationExpDate),
    │    IdentificationType, InitTimeInAddress, Nationality, Occupation, Salary, TimeInBusiness, trueId(always)]
    ├── ns:ActivityInfo
    │   └── activityReason        ← ActivityReason if present else "CREQ"  [Always]
    └── ns:ActivityDateInfo       ← 4-way priority (see §7)              [Always]
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_CREATE_CUST_WITH_CYCLE
├── Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate") → logicalDateVal
├── XPath.execute(PreExecCheck, serialize(orderRequest))
├── Event.createEvent("xslt://.../CCBS_CREATE_CUST_WITH_CYCLE", orderRequest, logicalDateVal)
│   [CORP/INDY NameInfo, AddressInfo (15 elements), CustomerGeneralInfo, ActivityInfo, ActivityDateInfo]
├── Event.Ext.sendEventImmediate(reqEvent)
├── RequestCount++
├── sendEventImmediate(Logger REQ — OPERATION_NAME=CCBS_CREATE_CUST_WITH_CYCLE)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
└── HandleActivityException(...)

Response_CCBS_CREATE_CUST_WITH_CYCLE
├── Instance.createInstance(CCBS_CreateCustomerWithCycleRes) — ResponseCode,Message,Status,RefId
├── customer.CustomerId ← CustomerHeader/CustomerIdInfo/CustomerNo
├── param = tib:trim(currActivity.Parameter[1]); orderTypeChk = (param=="SOURCE")
├── [if SOURCE] CustomerExtendedInfo{SOURCE_BILL_CYCLE=BillCycleNo} → customer.ExtendedInfo
├── [else] if(BillCycleNo null/empty) customer.BillCycleNo ← CustomerHeader/.../BillCycleNo
├── [if CustomerGeneralInfo null] create from CustomerHeader (Identification, LargeCustomerIndicator)
├── [if BirthDate null] customer.CustomerGeneralInfo.BirthDate ← L9BirthDate
├── [if IdentificationExpDate null] ← L9IdentificationExpDate
├── [if IdentificationType null] ← L9IdentificationType
├── [if Grading null] ← L9Grading
├── [if CustomerTypeInfo null AND SOURCE] CustomerExtendedInfo{SOURCE_CUSTOMER_TYPE=CustomerType}
├── [if CustomerTypeInfo null AND not SOURCE AND not OrderType=54] create CustomerTypeInfo
├── [if SOURCE] CustomerExtendedInfo{SOURCE_IDENTIFICATION=L9Identification}
├── [else if Identification null] ← L9Identification
├── [if GetNameAddress globalVar contains OrderType]
│   ├── INDY (NameType=73): Title/FirstName/MiddleName/LastName/MaritalStatus/FaxNumber/Email/Gender/IdentificationType/Identification
│   │   [ClearField pattern: if blank→set from CCBS; if ==ClearField globalVar→null]
│   ├── CORP: OrgName/BranchCode/BranchName/StoreId/FaxNumber/Email/IdentificationType/Identification
│   ├── Extended (both): Language,PrefContactNumber,HomePhone,BizPhone,privatePhone,AuthFirstName,AuthLastName,AuthPersonalId,POAName,POAPersonalId
│   └── Address: HouseNo,Moo,RoomNo,Floor,BuildingName,Soi,StreetName,Tumbon,Amphur,City,Zip,Country,TimeAtAddress,TypeOfAccomodation,subSoi
├── sendEventImmediate(Logger RES — OPERATION_NAME=CCBS_CREATE_CUSTOMER_WITH_CYCLE)
└── return "true"  (unconditional)
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Send CCBS CreateNewCustomerRequest with CORP/INDY NameInfo and AddressInfo variants |
| R2 | ActivityDate: 4-way priority chain (OPEN_DATE > EffectiveDate > LogicalDate concept > current-date) |
| R3 | CustomerType: 3-way priority (CUST_TYPE ExtInfo > CustomerTypeInfo.Type > 73) |
| R4 | SOURCE param: write ExtendedInfo keys (SOURCE_BILL_CYCLE, SOURCE_CUSTOMER_TYPE, SOURCE_IDENTIFICATION) instead of setting fields directly |
| R5 | Response: GetNameAddress globalVar gates full name+address read-back with ClearField pattern |
| R6 | Audit OPERATION_NAME in response = "CCBS_CREATE_CUSTOMER_WITH_CYCLE" (not "CCBS_CREATE_CUST_WITH_CYCLE") |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Audit log OPERATION_NAME mismatch (CUSTOMER vs CUST) | [MEDIUM] | Standardize; update existing audit reports filtering by OPERATION_NAME |
| ClearField globalVar pattern — field == ClearField value → set null | [MEDIUM] | Migration must preserve ClearField behavior; empty string ≠ ClearField sentinel |
| LogicalDate concept read at runtime — missing concept causes null date | [LOW] | Ensure LogicalDate concept always populated in BE working memory |
| SOURCE path writes 3 ExtendedInfo keys instead of setting fields directly | [LOW] | Document that SOURCE path is for ChangeTelNo/BN order types; preserve behavior |

---

## §19 Response Message Rule

### §19.1 Overview

The response is the most write-heavy in ACTIVATION. Populates `Customer.CustomerId` from CCBS-assigned `CustomerNo` and optionally updates BirthDate, Identification, CustomerTypeInfo, and (for GetNameAddress order types) full name and address from the CCBS record. ClearField pattern handles field nullification.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order — Customer written with 15+ fields |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_CREATE_CUST_WITH_CYCLE` | CCBS response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Parameter[1] used for SOURCE check |

### §19.3 Key Response Writes

| Target | Source | Condition |
|--------|--------|-----------|
| `Customer.CustomerId` | `CustomerHeader/CustomerIdInfo/CustomerNo` | Always |
| `Customer.BillCycleNo` | `CustomerHeader/CustomerBillingCycleInfo/BillCycleNo` | param≠SOURCE AND BillCycleNo null/empty |
| `CustomerExtendedInfo[SOURCE_BILL_CYCLE]` | `CustomerHeader/CustomerBillingCycleInfo/BillCycleNo` | param=SOURCE |
| `Customer.CustomerGeneralInfo.BirthDate` | `L9BirthDate` | BirthDate null |
| `Customer.CustomerGeneralInfo.Identification` | `L9Identification` | param≠SOURCE AND Identification null |
| `Customer.CustomerTypeInfo` | `CustomerTypeInfo.CustomerType/Subtype` | CustomerTypeInfo null AND param≠SOURCE AND OrderType≠54 |
| Full name+address fields (15+) | NameInfo/AddressInfo from CustomerHeader | GetNameAddress globalVar contains OrderType |

### §19.4 Response Completion Logic

`return "true"` — unconditional. No RequestCount comparison.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
