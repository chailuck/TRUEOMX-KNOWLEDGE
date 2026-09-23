# Request_CCBS_GET_CUSTOMER_HEADER

> TIBCO BusinessEvents FM Logic — CCBS retrieve Customer Header data (billing cycle, KYC, name/address) for a single Customer ID

**Author:** mranade-T420 | **Priority:** 5 · forwardChain=true | **Pattern:** Single-shot (one Customer → one request) | **Generated:** 2026-08-04

---

## §1 Overview & Purpose

**CCBS_GET_CUSTOMER_HEADER** retrieves the Customer Header record from CCBS for a single Customer ID. Unlike CCBS_GET_SUBSCRIBER_HEADER and CCBS_GET_CUST_ACC_SUB_ID which fan out over multiple subscribers, this FM fires **exactly one request per order** — the Customer is a single entity on the order.

The response is rich: it populates **billing cycle, KYC identity fields, customer type/subtype, customer name/address**, and extended contact details. The name/address block is gated on the order type appearing in the global `GetNameAddress` list OR the activity parameter `GET_NAME_ADDRESS="Y"`.

> **SOURCE param (OMX-990 CR):** When Parameter[1]="SOURCE", the FM targets the source customer in a port-in flow. It reads the CustomerId from `ExtendedInfo["SOURCE_CUSTOMER_ID"]` instead of `Customer.CustomerId`, and stores results into ExtendedInfo fields (`SOURCE_BILL_CYCLE`, `SOURCE_CUSTOMER_TYPE`, `SOURCE_IDENTIFICATION`) rather than overwriting primary Customer fields.

> **OrderType "2" (Change Price Plan):** When OrderType==2, an additional `CustomerExtendedInfo["UPDATE_BILLCYCLE"]` flag is written — "N" if BillCycleNo was null/empty before this FM ran, "Y" if it already had a value (indicates a bill cycle change is requested).

> **Single response = completion:** Because there is only one request, the response rulefunction always returns `"true"` immediately — no fan-in count comparison needed.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_CUSTOMER_HEADER` |
| Author | mranade-T420 |
| Priority | 5 |
| Forward chain | true |
| Backend system | CCBS / AMDOCS L9 |
| Operation | GetCustomerHeader |
| CCBS request schema | `http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/CustomerServices/Schema.xsd7` |
| Response concept | `Concepts.FM.Response.CCBS_GetCustomerHeaderRes` |
| Fan-out pattern | Single-shot (one Customer ID → one request) |
| Resubmit support | Yes — RequestCount > 0 guard on increment |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order including Customer.CustomerId / Customer.RefId |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Holds PreExecCheck, Parameter[1], RequestCount, ALT_CES |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Notes |
|---|-----------|-------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity is next to execute |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_GET_CUSTOMER_HEADER"` | Exact match |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_CUSTOMER_HEADER"` | Process flow agreement |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Not yet dispatched |

---

## §5 Execution Flow

1. Compute `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Read `param = tib:trim(currActivity/Parameter[1])` — switches between SOURCE and primary customer ID
3. Read ALT_CES: `GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")`
4. PreExecCheck: if non-empty → serialize `orderRequest` via `Instance.serializeUsingDefaults()` + evaluate XPath
5. If `chkRes="true"`: build and fire `CCBS_GET_CUSTOMER_HEADER` event with payload `GetCustomerHeaderRequest`
6. Fire Logger audit event
7. `RequestCount++` (if not resubmit)
8. `GetActivityStatusString("1", false)` + `SendDataToDB()`
9. If `chkRes="false"` (SKIP): `SkipActivity(orderRequest, orderCurrentActivity, "4")`
10. Exception: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §6 Rule Action (THEN) — Detailed Logic

### §6.1 SOURCE Parameter — Customer ID Selection

```java
// OMX-990 CR: param="SOURCE" → use SOURCE_CUSTOMER_ID from ExtendedInfo, not CustomerId
customerNo = (param == "SOURCE")
  ? Customer/ExtendedInfo[Name="SOURCE_CUSTOMER_ID"]/Value
  : Customer/CustomerId;
```

### §6.2 RefID Binding

```xml
<RefID>$orderRequest/OrderData/Customer/RefId</RefID>
<!-- Customer-level RefId — NOT per-subscriber -->
```

### §6.3 ALT_CES Routing

```text
when: altParam="Y" AND OrderData/ExtendedInfo[ALT_CES]/Value != ""
  → CES = OrderData/ExtendedInfo["ALT_CES"]/Value
otherwise:
  → CES = OrderData/CES
```

### §6.4 Activity-Level PreExecCheck

This rule uses a single activity-level PreExecCheck — not per-subscriber like CCBS_GET_CUST_ACC_SUB_ID. The full `orderRequest` is serialized once using `Instance.serializeUsingDefaults(orderRequest)`.

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Protocol |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_GET_CUSTOMER_HEADER` | JMS → CCBS SOAP |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_GET_CUSTOMER_HEADER` | JMS |

### §8.3 Backend API Details

| Property | Value |
|----------|-------|
| System | CCBS / AMDOCS L9 |
| Operation | GetCustomerHeader |
| Request schema | `ns:GetCustomerHeaderRequest / ns:CustomerIdInfo / ns:customerNo` |
| Key input | customerNo = Customer.CustomerId (or SOURCE_CUSTOMER_ID) |
| Key outputs | BillCycleNo, CustomerType/Subtype, L9Identification, L9BirthDate, LargeCustomerIndicator, NameInfo (LinkType 67/69), AddressInfo |
| Correlation | RefID = Customer.RefId; response: extId = random generateTrackingID() |

### §8.4 BE Working Memory — Fields Written (Response)

| Concept | Field | Source | Condition |
|---------|-------|--------|-----------|
| Customer | `BillCycleNo` | CustomerBillingCycleInfo/BillCycleNo | NOT SOURCE AND BillCycleNo is blank |
| Customer | `ExtendedInfo["SOURCE_BILL_CYCLE"]` | BillCycleNo | param=="SOURCE" |
| Customer | `ExtendedInfo["UPDATE_BILLCYCLE"]` | "N" or "Y" | OrderType=="2" — "N" if BillCycleNo was blank, "Y" if already set |
| CustomerGeneralInfo | `Identification` | CustomerGeneralInfo/L9Identification | NOT SOURCE AND Identification is null |
| Customer | `ExtendedInfo["SOURCE_IDENTIFICATION"]` | L9Identification | param=="SOURCE" |
| CustomerGeneralInfo | `IdentificationType` | CustomerGeneralInfo/L9IdentificationType | IdentificationType is null |
| CustomerGeneralInfo | `IdentificationExpDate` | CustomerGeneralInfo/L9IdentificationExpDate (DateTime) | IdentificationExpDate is null |
| CustomerGeneralInfo | `BirthDate` | CustomerGeneralInfo/L9BirthDate (DateTime) | BirthDate is null |
| CustomerGeneralInfo | `LargeCustomerIndicator` | CustomerGeneralInfo/LargeCustomerIndicator | CustomerGeneralInfo bootstrapped (was null) |
| CustomerGeneralInfo | `Grading` | CustomerGeneralInfo/L9Grading | BRMS.IsBlankOrStringNull(Grading) |
| CustomerTypeInfo | `Type` | CustomerTypeInfo/CustomerType | NOT SOURCE AND CustomerTypeInfo null AND OrderType!="54" |
| CustomerTypeInfo | `Subtype` | CustomerTypeInfo/CustomerSubtype | same |
| Customer | `ExtendedInfo["SOURCE_CUSTOMER_TYPE"]` | CustomerTypeInfo/CustomerType | param=="SOURCE" AND CustomerTypeInfo null |
| CustomerName | see INDY/CORP/Extended tables below | NameInfo (LinkType 67) | GET_NAME_ADDRESS gate |
| CustomerAddress | HouseNo…subSoi (AE1–AE15) | AddressInfo | GET_NAME_ADDRESS gate |

### §8.5 Activity Parameter Dependencies

| Parameter | Key | Effect |
|-----------|-----|--------|
| Parameter[1] | (raw value) | "SOURCE" → routes all results to ExtendedInfo fields; selects SOURCE_CUSTOMER_ID as the lookup key |
| ALT_CES | Activity parameter | "Y" → override CES endpoint from OrderData/ExtendedInfo |
| GET_NAME_ADDRESS | Activity parameter | "Y" → forces name/address enrichment regardless of global OrderTypes list |

### §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Credential gate |
| `OMX_OM/OrderTypes/GetNameAddress` | Comma-delimited list of OrderTypes that trigger name/address population |
| `OMX_COMMON/_SharedResources/Common/ClearField` | Sentinel value for field erasure (compared as toUpperCase) |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit logger component name |
| `OMX_OM/WritePayload` | Payload capture gate in audit log |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameters

| Param | Bound from |
|-------|-----------|
| `$orderRequest` | Working memory OrderRequest |
| `$globalVariables` | BE global variables |
| `$altParam` | `GetActivityParameterValueFromKey("ALT_CES")` |
| `$param` | `tib:trim(currActivity/Parameter[1])` |

### §9.2 Request Event Fields

```xml
<event>
  <JMSPriority>$orderRequest/OrderPriority</JMSPriority>         <!-- conditional -->
  <JMSCorrelationID>$orderRequest/OrderData/OMXTrackingId</JMSCorrelationID>
  <OrderID>$orderRequest/OrderData/OrderID</OrderID>
  <RefID>$orderRequest/OrderData/Customer/RefId</RefID>  <!-- Customer-level -->
  <UserName>$orderRequest/OrderData/User</UserName>           <!-- credential-gated -->
  <PassWord>$orderRequest/OrderData/Password</PassWord>       <!-- credential-gated -->
  <OrderType>$orderRequest/OrderData/OrderType</OrderType>
  <CES>[ALT_CES or OrderData/CES]</CES>
  <payload>
    <ns:GetCustomerHeaderRequest>
      <ns:CustomerIdInfo>
        <ns:customerNo>
          <!-- if $param="SOURCE" → Customer/ExtendedInfo[SOURCE_CUSTOMER_ID]/Value -->
          <!-- else               → Customer/CustomerId -->
        </ns:customerNo>
      </ns:CustomerIdInfo>
    </ns:GetCustomerHeaderRequest>
  </payload>
</event>
```

---

## §10 XSLT Field Mapping Tree

```text
event
├── JMSPriority              ← $orderRequest/OrderPriority                                    [Conditional]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId                         [Conditional]
├── OrderID                  ← $orderRequest/OrderData/OrderID                                [Conditional]
├── RefID                    ← $orderRequest/OrderData/Customer/RefId (customer-level)        [Conditional]
├── UserName                 ← $orderRequest/OrderData/User                                   [Credential-gated]
├── PassWord                 ← $orderRequest/OrderData/Password                               [Credential-gated]
├── OrderType                ← $orderRequest/OrderData/OrderType                              [Conditional]
├── CES                      ← ExtendedInfo[ALT_CES]/Value OR OrderData/CES                  [Conditional]
└── payload
    └── ns:GetCustomerHeaderRequest
        └── ns:CustomerIdInfo
            └── ns:customerNo  ← if param="SOURCE": SOURCE_CUSTOMER_ID | else: CustomerId    [Always]
```

---

## §11 Audit Logging

**Request audit:**

| Field | Value |
|-------|-------|
| OPERATION_NAME | `CCBS_GET_CUSTOMER_HEADER` (static) |
| AUDIT_TRACE | `Request Sent for CCBS_GET_CUSTOMER_HEADER` |
| PROCESS_ID | `concat(nanoTime(), "_REQ")` |

**Response audit:**

| Field | Value |
|-------|-------|
| OPERATION_NAME | `CCBS_GET_CUSTOMER_HEADER` (static) |
| AUDIT_TRACE | `Response received for CCBS_GET_CUSTOMER_HEADER` |
| PROCESS_ID | `concat(nanoTime(), "_RES")` |

---

## §12 Activity Status Management

| Call | Code | Meaning |
|------|------|---------|
| `GetActivityStatusString("1", false)` | 1 | Active / In-Progress |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | 4 | PreExecCheck failed |

---

## §13 Exception / Error Handling

```java
catch (Exception ae) {
  HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

Standard centralized error handler — no custom recovery logic.

---

## §14 Helper Functions Reference

| Function | Signature | Purpose |
|----------|-----------|---------|
| `GetActivityParameterValueFromKey` | (Activity, String) → String | Read ALT_CES / GET_NAME_ADDRESS activity parameters |
| `GetActivityStatusString` | (String, boolean) → String | Returns activity status string |
| `SendDataToDB` | (orderRequest) → void | Persists activity state |
| `SkipActivity` | (orderRequest, Activity, String) → void | Sets SKIP status |
| `HandleActivityException` | (orderRequest, Activity, Exception, String) → void | Centralized error handling |
| `BRMS.IsBlank` | (String) → boolean | Response: check if field is null or empty |
| `BRMS.IsBlankOrStringNull` | (String) → boolean | Response: check if field is null, empty, or literal "null" string |
| `Instance.getByExtIdByUri` | (extId, uri) → Concept | Response: look up Customer by "C:"+trackId extId |

---

## §15 Function Dependency Tree

```text
Request_CCBS_GET_CUSTOMER_HEADER (rule)
├── XPath.evalAsString(tib:trim($currActivity/Parameter[1]))  [read param]
├── GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")
├── Instance.serializeUsingDefaults(orderRequest)  [PreExecCheck serialization]
├── XPath.execute("/("+chkXPath+")", sXML, ...)   [PreExecCheck eval]
├── Event.createEvent(CCBS_GET_CUSTOMER_HEADER XSLT)
│   └── payload: GetCustomerHeaderRequest/customerNo = Customer.CustomerId or SOURCE_CUSTOMER_ID
├── Event.Ext.sendEventImmediate(gchReq)
├── Event.Ext.sendEventImmediate(Logger)
├── orderCurrentActivity.RequestCount++
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_CCBS_GET_CUSTOMER_HEADER (rulefunction)
├── Instance.createInstance(CCBS_GetCustomerHeaderRes XSLT)  [ResponseCode, ResponseMessage only]
├── XPath.evalAsString(currActivity/Parameter[1])   [param check]
├── [BillCycleNo routing]
│   ├── [SOURCE]: Instance.createInstance(CustomerExtendedInfo["SOURCE_BILL_CYCLE"])
│   └── [non-SOURCE]:
│       ├── Customer.BillCycleNo = CustomerBillingCycleInfo/BillCycleNo
│       └── [OrderType=2]: Instance.createInstance(CustomerExtendedInfo["UPDATE_BILLCYCLE"]) = "N"/"Y"
├── XPath.evalAsString(count(L9BirthDate) > 0)   [chk]
├── [CustomerGeneralInfo bootstrap if null]:
│   └── Instance.createInstance(CustomerGeneralInfo → L9Identification, LargeCustomerIndicator)
├── [BirthDate if null]: XPath.evalAsDateTime(L9BirthDate)
├── [CustomerTypeInfo if null]:
│   ├── [SOURCE]: Instance.createInstance(CustomerExtendedInfo["SOURCE_CUSTOMER_TYPE"])
│   └── [non-SOURCE, OrderType!="54"]: Instance.createInstance(CustomerTypeInfo → Subtype, Type)
├── [Identification routing]:
│   ├── [SOURCE]: Instance.createInstance(CustomerExtendedInfo["SOURCE_IDENTIFICATION"])
│   └── [non-SOURCE, if null]: Customer.CustomerGeneralInfo.Identification = L9Identification
├── [IdentificationType if null]: XPath.evalAsString(L9IdentificationType)
├── [IdentificationExpDate if null]: XPath.evalAsDateTime(L9IdentificationExpDate)
├── [Grading via BRMS.IsBlankOrStringNull]: XPath.evalAsString(L9Grading)
├── [GET_NAME_ADDRESS gate]:
│   ├── GetActivityParameterValueFromKey(currActivity, "GET_NAME_ADDRESS")
│   ├── [CustomerName bootstrap if null]: Instance.createInstance(CustomerName)
│   ├── [INDY — LinkType=67, NameType=73]: NE1→Title, NE2→FirstName, NE3→MiddleName, NE4→LastName,
│   │   NE5→MaritalStatus, NE6→FaxNumber, NE7→Email, NE8→Gender, NE9→IdentificationType, NE10→Identification
│   ├── [CORP — LinkType=67, NameType!=73]: NE1→OrgName, NE2→BranchCode, NE3→BranchName, NE4→StoreId,
│   │   NE5→FaxNumber, NE6→Email, NE7→IdentificationType, NE8→Identification
│   ├── [Extended — LinkType=69]: NE1→Language, NE2→PrefContactNumber, NE3→HomePhone, NE4→BizPhone,
│   │   NE5→privatePhone, NE6→AuthFirstName, NE7→AuthLastName, NE8→⚠AuthLastName(BUG), NE9→POAName, NE10→POAPersonalId
│   └── [CustomerAddress bootstrap if null]: AE1→HouseNo … AE15→subSoi (all ClearField-safe)
├── Event.Ext.sendEventImmediate(Logger)
└── return "true"  (always — single shot, no fan-in count)
```

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Single-shot request — one Customer per order, one CCBS call |
| R2 | SOURCE param routes lookup key and all response fields to ExtendedInfo ("SOURCE_*") variants |
| R3 | BillCycleNo: write only if blank; OrderType=2 must set UPDATE_BILLCYCLE flag (Y/N) |
| R4 | CustomerGeneralInfo bootstrap: create sub-concept if not yet present |
| R5 | CustomerTypeInfo: skip creation if OrderType="54" |
| R6 | Name/address: dual name-type routing (INDY NameType=73 vs CORP) from NameInfo[LinkType=67]; extended contact from LinkType=69 |
| R7 | ClearField erasure for all name/address fields (compare as toUpperCase to global ClearField sentinel) |
| R8 | GET_NAME_ADDRESS activity parameter overrides global OrderType gate |
| R9 | Always returns "true" (no fan-in comparison) — single response signals completion |

### Design Risks

> **⚠ Bug found — line 250:** When `IsBlank(AuthPersonalId)` is true, the code writes to `CustomerName.AuthLastName` (not `AuthPersonalId`). This overwrites AuthLastName twice when AuthPersonalId should be populated. Migration must fix this defect.

```java
// Line 250-252 — DEFECT:
if(BRMS.IsBlank(orderRequest.OrderData.Customer.CustomerName.AuthPersonalId))
    orderRequest.OrderData.Customer.CustomerName.AuthLastName = NameElement8;  // BUG: should be AuthPersonalId
```

| Risk | Severity | Mitigation |
|------|----------|-----------|
| AuthPersonalId bug: NameElement8 is written to AuthLastName instead | [HIGH] | Fix in migration: write to AuthPersonalId |
| Grading uses BRMS.IsBlankOrStringNull (differs from other "if null" checks) — may unexpectedly overwrite Grading="null" | [MEDIUM] | Standardize null-check semantics in migration |
| OrderType="54" excluded from CustomerTypeInfo creation — silent skip, no log | [MEDIUM] | Document explicitly; add audit log for skip |
| ClearField comparison uses `toUpperCase()` — case-sensitive mismatch if ClearField global contains mixed-case | [MEDIUM] | Ensure ClearField global is always uppercase |
| CustomerGeneralInfo bootstrap: two-phase init (create + later BirthDate set) | [LOW] | Consolidate in a single atomic create in migration |

---

## §18 Full Source Code (Request Rule)

```java
/**
 * Request_CCBS_GET_CUSTOMER_HEADER
 * Author: mranade-T420 | Priority: 5 | forwardChain: true
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_CUSTOMER_HEADER {
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CCBS_GET_CUSTOMER_HEADER";
    orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_CUSTOMER_HEADER";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    try {
      boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
      String chkRes = "true";
      // OMX-990 CR
      String param = XPath.evalAsString("tib:trim($orderCurrentActivity/Parameter[1])");
      String altParam = GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES");

      if(String.length(orderCurrentActivity.PreExecCheck) > 0) {
        String sXML = Instance.serializeUsingDefaults(orderRequest);
        chkRes = XPath.execute("/("+orderCurrentActivity.PreExecCheck+")", sXML, ...);
      }

      if(String.equals(chkRes, "true")) {
        /* XSLT payload — see §9.2 for full field list:
           GetCustomerHeaderRequest/CustomerIdInfo/customerNo
           = (param="SOURCE") ? SOURCE_CUSTOMER_ID : Customer.CustomerId */
        Event.Ext.sendEventImmediate(gchReq);
        Event.Ext.sendEventImmediate(Logger);  // OPERATION_NAME="CCBS_GET_CUSTOMER_HEADER"

        if(!isActResub) orderCurrentActivity.RequestCount++;
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else {
        SkipActivity(orderRequest, orderCurrentActivity, "4");
      }
    } catch (Exception ae) {
      HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

The response handler enriches the OMX Customer object with the CCBS Customer Header data — billing cycle, KYC fields, customer type, name (INDY/CORP), extended contact, and address. All writes are guarded with "only write if blank" to preserve data already set by earlier steps.

Because there is exactly one request per order, the rulefunction always returns **`"true"`** immediately — no fan-in count comparison.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order graph — enriched with customer data |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_GET_CUSTOMER_HEADER` | CCBS Customer Header response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — holds Response array and Parameter[1] |

### §19.3 Response Concept Construction

```text
CCBS_GetCustomerHeaderRes
├── extId            ← OMXUtils.generateTrackingID() (random)   [Always]
├── ResponseCode     ← $eventResponse/ResponseCode               [Conditional]
└── ResponseMessage  ← $eventResponse/ResponseMsg                [Conditional]
```

> **Note:** This response concept is minimal — only ResponseCode and ResponseMessage. No CompletionStatus or ReferenceId. Full enrichment happens via direct field writes on Customer sub-concepts.

### §19.4 BillCycleNo Routing Matrix

| param | BillCycleNo pre-state | OrderType | Action |
|-------|----------------------|-----------|--------|
| "SOURCE" | any | any | CustomerExtendedInfo["SOURCE_BILL_CYCLE"] = BillCycleNo |
| other | null or "" | any | Customer.BillCycleNo = BillCycleNo |
| other | null or "" | "2" | + CustomerExtendedInfo["UPDATE_BILLCYCLE"] = "N" |
| other | already set | "2" | CustomerExtendedInfo["UPDATE_BILLCYCLE"] = "Y" |

### §19.5 Name Enrichment — INDY vs CORP (LinkType=67)

| NameType | CCBS NameElement | OMX CustomerName field | ClearField-safe |
|----------|-----------------|----------------------|-----------------|
| INDY (73) | NE1 | Title | Yes |
| INDY (73) | NE2 | FirstName | Yes |
| INDY (73) | NE3 | MiddleName | Yes |
| INDY (73) | NE4 | LastName | Yes |
| INDY (73) | NE5 | MaritalStatus | Yes |
| INDY (73) | NE6 | FaxNumber | Yes |
| INDY (73) | NE7 | Email | Yes |
| INDY (73) | NE8 | Gender | Yes |
| INDY (73) | NE9 | IdentificationType | Yes |
| INDY (73) | NE10 | Identification | Yes |
| CORP (other) | NE1 | OrgName | Yes |
| CORP (other) | NE2 | BranchCode | Yes |
| CORP (other) | NE3 | BranchName | Yes |
| CORP (other) | NE4 | StoreId | Yes |
| CORP (other) | NE5 | FaxNumber | Yes |
| CORP (other) | NE6 | Email | Yes |
| CORP (other) | NE7 | IdentificationType | Yes |
| CORP (other) | NE8 | Identification | Yes |

### §19.6 Extended Contact — LinkType=69

| CCBS NameElement | OMX CustomerName field | Note |
|-----------------|----------------------|------|
| NE1 | Language | ClearField-safe |
| NE2 | PrefContactNumber | ClearField-safe |
| NE3 | HomePhone | ClearField-safe |
| NE4 | BizPhone | ClearField-safe |
| NE5 | privatePhone | ClearField-safe |
| NE6 | AuthFirstName | ClearField-safe |
| NE7 | AuthLastName | ClearField-safe |
| NE8 | **AuthLastName** ⚠ BUG | Guard checks `IsBlank(AuthPersonalId)` but writes to `AuthLastName` — should be `AuthPersonalId` |
| NE9 | POAName | ClearField-safe |
| NE10 | POAPersonalId | ClearField-safe |

### §19.7 Address Enrichment (AE1–AE15)

| AddressElement | CustomerAddress field |
|---------------|----------------------|
| AE1 | HouseNo |
| AE2 | Moo |
| AE3 | RoomNo |
| AE4 | Floor |
| AE5 | BuildingName |
| AE6 | Soi |
| AE7 | StreetName |
| AE8 | Tumbon |
| AE9 | Amphur |
| AE10 | City |
| AE11 | Zip |
| AE12 | Country |
| AE13 | TimeAtAddress |
| AE14 | TypeOfAccomodation |
| AE15 | subSoi |

All 15 address fields: write if blank; set null if field value.toUpperCase() == ClearField sentinel.

### §19.8 Response Completion

| Condition | Return |
|-----------|--------|
| Always (single request) | `"true"` — no RequestCount comparison needed |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
