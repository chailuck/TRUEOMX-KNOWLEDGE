# Request_CCBS_GET_BA_HEADER

> TIBCO BusinessEvents FM Logic — Billing Arrangement Header retrieval with IntraActivitySequencing; enriches BillingArrangementName, BillingArrangementAddress, and order-type-gated BillingArrangementBillInfo

**Author:** SathidP-PC | **Priority:** 5 | **forwardChain:** true | **Pattern:** IntraActivitySequencing (per Account)

> **Zip ClearField check is CORRECT** in this FM (response line 255 correctly uses `BillingArrangementAddress.Zip`) — unlike the bug in `Response_CCBS_GET_ACCOUNT_HEADER`.

> **Copy-paste note:** Commented-out debug lines in request and response reference "ACCOUNT_HEADER" — a copy-paste artifact from CCBS_GET_ACCOUNT_HEADER; no functional impact.

---

## §1 Overview & Purpose

**CCBS_GET_BA_HEADER** retrieves the Billing Arrangement Header from CCBS for each Account on the order. It is the billing-tier counterpart to `CCBS_GET_ACCOUNT_HEADER`: instead of enriching AccountNames / AccountAddress / AccountManagementInfo, it enriches `BillingArrangementName`, `BillingArrangementAddress`, and (when applicable) `BillingArrangementBillInfo`.

Two OrderType-gated write paths:
- **L9SplitParam** — appended to ExtendedInfo only for OrderType=11 (L9 Resume orders)
- **BillingArrangementBillInfo** — bootstrapped only for cancel order types 12 and 11002 when not already set

GET_NAME_ADDRESS enrichment can be triggered by the global config OR by activity parameter `GET_NAME_ADDRESS="Y"` (the parameter trigger is an addition not found in CCBS_GET_ACCOUNT_HEADER).

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_BA_HEADER` |
| Author | SathidP-PC |
| Priority | 5 |
| Forward chain | true |
| Backend system | CCBS (GetBillingArrangementHeader) |
| Request schema NS | `http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/BillingArrangementServices/getBillingArrangementHeaderRequest` |
| Response concept | `Concepts.FM.Response.CCBS_GetBillingArrangementHeader` |
| Fan-out pattern | IntraActivitySequencing (per Account, throttled sequential) |
| Completion criterion | `IntraActivitySequencing.ActionResponseEvent(currActivity)` → true/false |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Customer.Account[] iterated; RefId, AccountID, OrderType, OMXTrackingId read |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Holds PreExecCheck, RequestCount, Response[]; IntraActivitySequencing state |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_GET_BA_HEADER"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_BA_HEADER"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Resubmit flag: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Fetch `nextAct` via `Instance.getByExtIdByUri(NextActivityName, Activity)`
3. Read `iAcctLen = Customer.Account@length`
4. If resubmit: `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
5. **For each Account[i]** (i = 0..iAcctLen-1):
   - a. Resubmit skip: Response[iResp].ReferenceId==refId && CompletionStatus==2 → skip
   - b. Per-account PreExecCheck: `GetXMLForAccount(orderRequest, refId)` → XPath evaluate
   - c. If chkRes="true": build `GetBillingArrangementHeaderRequest` event
   - d. `Event.assertEvent(reqEvent)` (queued)
   - e. `IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)`
   - f. Fire Logger audit event
   - g. `isSkipped = false`
6. After loop: if `!isSkipped` → `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)`
7. If `!isSkipped`: `GetActivityStatusString("1", false)` + `SendDataToDB(orderRequest)`
8. Else: `SkipActivity(orderRequest, orderCurrentActivity, "4")`
9. Exception: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Protocol | Note |
|-----------|-----------|---------|------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_GET_BA_HEADER` | JMS (assertEvent + IntraActivitySequencing) | No ALT_CES override |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_GET_BA_HEADER` | JMS | Per-account; triggers next via IntraActivitySequencing |

### §8.3 Backend API Details

| Property | Value |
|----------|-------|
| System | CCBS |
| Operation | GetBillingArrangementHeader |
| Request element | `ns:GetBillingArrangementHeaderRequest / ns:BillingArrangementIdInfo / ns:billingArrangementId` |
| Key input | `Account[$i+1]/AccountID` (1-indexed, **conditional**) |
| CES routing | Direct from `OrderData/CES` — no ALT_CES parameter override |
| Credential gate | `IsEnableUserPass='true'` → UserName/PassWord headers |

### §8.4 Fields Read / Written

**Read:** `Customer.Account[i].RefId`, `Customer.Account[i].AccountID`, `OrderData.OrderType`, `OrderData.CES`

**Written (per Account, response):**
- `Account[i].ExtendedInfo[]` ← L9SplitParam (OrderType=11 only)
- `Account[i].BillingArrangementBillInfo` (cancel orders only, if null)
- `Account[i].BillingArrangementName.*` (GET_NAME_ADDRESS gate)
- `Account[i].BillingArrangementAddress.*` (GET_NAME_ADDRESS gate)

### §8.5 Activity Parameters

| Key | Value checked | Effect |
|-----|---------------|--------|
| `GET_NAME_ADDRESS` | "Y" | Forces name/address enrichment; OR condition with global GetNameAddress config |

### §8.6 Global Variable Dependencies

`OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass`, `OMX_OM/OrderTypes/GetNameAddress`, `OMX_COMMON/_SharedResources/Common/ClearField`, `OMX_COMMON/Component_Name/OMX_CEP`, `OMX_COMMON/Component_Name/OMX_FM`, `MSG_LOG_LEVEL/INFO`, `OMX_OM/WritePayload`

---

## §9 Payload Build

```xml
<payload>
  <ns:GetBillingArrangementHeaderRequest>
    <ns:BillingArrangementIdInfo>
      <!-- conditional xsl:if: only emitted if AccountID non-empty -->
      <ns:billingArrangementId><!-- Account[$i+1]/AccountID --></ns:billingArrangementId>
    </ns:BillingArrangementIdInfo>
  </ns:GetBillingArrangementHeaderRequest>
</payload>
```

**Key difference from CCBS_GET_ACCOUNT_HEADER:** `billingArrangementId` is wrapped in `xsl:if` — conditionally emitted. The CCBS_GET_ACCOUNT_HEADER `accountNo` was always emitted.

**JMS headers:** JMSPriority (conditional), JMSCorrelationID (conditional), OrderID (conditional), RefID ← Account[$i+1]/RefId (conditional), UserName/PassWord (credential-gated), OrderType (conditional), CES ← `OrderData/CES` (conditional, direct — no ALT_CES override)

---

## §10 XSLT Field Mapping Tree

```text
event
├── JMSPriority          ← $orderRequest/OrderPriority                          [Conditional]
├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId               [Conditional]
├── OrderID              ← $orderRequest/OrderData/OrderID                      [Conditional]
├── RefID                ← Account[$i+1]/RefId                                  [Conditional]
├── UserName             ← $orderRequest/OrderData/User                         [Credential-gated]
├── PassWord             ← $orderRequest/OrderData/Password                     [Credential-gated]
├── OrderType            ← $orderRequest/OrderData/OrderType                    [Conditional]
├── CES                  ← $orderRequest/OrderData/CES                          [Conditional — Direct, no ALT_CES]
└── payload
    └── ns:GetBillingArrangementHeaderRequest
        └── ns:BillingArrangementIdInfo
            └── ns:billingArrangementId  ← Account[$i+1]/AccountID             [Conditional (xsl:if)]
```

---

## §11 Audit Logging

**Request audit** — inside `if(chkRes="true")` block (send path only, silent on skip):

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` |
| PROCESS_ID | `concat(nanoTime(), "_REQ")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `$orderCurrentActivity/ActivityID` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `concat("Request Sent for ", $orderCurrentActivity/ActivityID)` |

**Response audit:** same pattern with `_RES` suffix, using `$currActivity/ActivityID`.

---

## §15 Function Dependency Tree

```text
Request_CCBS_GET_BA_HEADER (rule)
├── Instance.getByExtIdByUri(NextActivityName, Activity)   [nextAct]
├── [if isActResub]: IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── [for i=0..iAcctLen-1]:
│   ├── Resubmit skip: Response[iResp].ReferenceId==refId && CompletionStatus==2
│   ├── GetXMLForAccount(orderRequest, refId)
│   ├── XPath.execute(PreExecCheck, sXML, ...)
│   ├── [if chkRes="true"]:
│   │   ├── Event.createEvent(CCBS_GET_BA_HEADER XSLT)
│   │   │   └── GetBillingArrangementHeaderRequest/BillingArrangementIdInfo/billingArrangementId
│   │   │       ← Account[$i+1]/AccountID (conditional)
│   │   ├── Event.assertEvent(reqEvent)   ← queued
│   │   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   │   └── Event.Ext.sendEventImmediate(Logger)
├── [if !isSkipped]:
│   ├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
│   ├── GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [if isSkipped]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_CCBS_GET_BA_HEADER (rulefunction, 301 lines)
├── isL9ResumeOrder = OrderType=="11"
├── isCancel = OrderType=="12" || OrderType=="11002"
├── [for i=0..allAcctLength-1 where Account[i].RefId == eventResponse.RefID]:
│   ├── Instance.getByExtIdByUri("A:"+OMXTrackingId+":"+RefID, Account)
│   ├── [if isL9ResumeOrder]:
│   │   └── AccountExtendedInfo: Name="L9SplitParam", Value←L9SplitParam (conditional)
│   │       → Account[i].ExtendedInfo[len]
│   ├── [if isCancel && BillingArrangementBillInfo==null]:
│   │   └── BillingArrangementBillInfo: BillFormat←L3BillFormat (conditional)
│   │       → Account[i].BillingArrangementBillInfo
│   ├── GET_NAME_ADDRESS gate (global config OR param "GET_NAME_ADDRESS"="Y"):
│   │   ├── Bootstrap BillingArrangementName if null
│   │   ├── [if NameInfo/NameType==73]: INDY (NE1-NE10 → Title..Identification) [ClearField-safe]
│   │   ├── [else]: CORP (NE1-NE8 → OrgName..Identification) [ClearField-safe]
│   │   ├── Extended contact (LinkType=71): NE1-NE10 [ClearField-safe]
│   │   │   Language, PrefContactNumber, HomePhone, BizPhone, privatePhone,
│   │   │   AuthFirstName, AuthLastName, AuthPersonalId(NE8), POAName(NE9), POAPersonalId(NE10)
│   │   └── BillingArrangementAddress (AE1-AE15): HouseNo..subSoi [all ClearField-safe, Zip CORRECT]
├── Instance.createInstance(CCBS_GetBillingArrangementHeader XSLT)
│   extId=OMXUtils:generateTrackingID(), ResponseCode, ResponseMessage, CompletionStatus, ReferenceId
├── currActivity.Response[len] = actResponse
├── Event.Ext.sendEventImmediate(Logger)
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
```

---

## §17 Migration Notes & Differences

### Key Differences from CCBS_GET_ACCOUNT_HEADER

| Aspect | CCBS_GET_ACCOUNT_HEADER | CCBS_GET_BA_HEADER |
|--------|------------------------|--------------------|
| Author | awalia-t420 | SathidP-PC |
| Backend | GetAccountHeader | GetBillingArrangementHeader |
| Request field | `ns1:accountNo` (always emitted) | `ns:billingArrangementId` (conditional xsl:if) |
| CES routing | ALT_CES parameter override | Direct from OrderData/CES only |
| Name concept | AccountNames | BillingArrangementName |
| Address concept | AccountAddress | BillingArrangementAddress |
| Extended contact LinkType | 70 | **71** |
| GET_NAME_ADDRESS trigger | Global config only | Global config OR parameter "GET_NAME_ADDRESS"="Y" |
| AccountManagementInfo | Yes (9+ fields) | Not present |
| AgreementId resolution | POU/COU loops | Not present |
| Order-type gates | None | L9SplitParam (type=11) + BillingArrangementBillInfo (type=12/11002) |
| Zip ClearField check | **BUG** (uses City field) | **CORRECT** (uses Zip field) |
| Response concept | Large full snapshot | Simple 4-field ResponseBase |

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | IntraActivitySequencing per Account (throttled sequential) |
| R2 | Per-account PreExecCheck via GetXMLForAccount() |
| R3 | Credential gate via IsEnableUserPass global variable |
| R4 | L9SplitParam: append to ExtendedInfo ONLY for OrderType=11 (L9 Resume) |
| R5 | BillingArrangementBillInfo: bootstrap ONLY for cancel types (12, 11002) when null |
| R6 | GET_NAME_ADDRESS: triggered by global config OR activity parameter "GET_NAME_ADDRESS"="Y" |
| R7 | INDY / CORP name enrichment (NE1-NE10 / NE1-NE8); all ClearField-safe |
| R8 | Extended contact (LinkType=71): NE1-NE10; all ClearField-safe |
| R9 | BillingArrangementAddress (AE1-AE15); all ClearField-safe |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| IntraActivitySequencing — no direct equivalent in most target platforms | [HIGH] | Replace with explicit per-account parallel or sequential async fan-out |
| No ALT_CES override — BA Header cannot use alternate CES endpoint | [MEDIUM] | Verify if override is needed; add parity with CCBS_GET_ACCOUNT_HEADER if required |
| GET_NAME_ADDRESS parameter trigger inconsistency vs other CCBS FMs | [MEDIUM] | Normalise across all CCBS FMs |
| `billingArrangementId` conditional in XSLT — request could have empty BillingArrangementIdInfo | [MEDIUM] | Confirm CCBS API handles missing billingArrangementId; add validation if required |
| L9SplitParam and BillingArrangementBillInfo tied to hardcoded OrderType values | [MEDIUM] | Externalise OrderType conditions to configuration |

---

## §18 Full Source Code (Request Rule)

```java
/**
 * Request_CCBS_GET_BA_HEADER
 * Author: SathidP-PC | Priority: 5 | forwardChain: true
 * Pattern: IntraActivitySequencing per Account
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_BA_HEADER {
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Activity nextAct = Instance.getByExtIdByUri(NextActivityName, ...);
      int iAcctLen = orderRequest.OrderData.Customer.Account@length;
      if(isActResub)
        IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

      boolean isSkipped = true;
      for (int i=0; i < iAcctLen; i++) {
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
            /* XSLT — see §9 — GetBillingArrangementHeaderRequest/BillingArrangementIdInfo/billingArrangementId
               ← Account[$i+1]/AccountID (conditional)
               Headers: JMSPriority, JMSCorrelationID, OrderID, RefID(?), UserName(?), PassWord(?), OrderType, CES (direct) */
            Event.assertEvent(reqEvent);
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

### §19.1 Overview

Parses CCBS BillingArrangementHeader response and enriches the Account concept. 301 lines covering: L9SplitParam (L9 Resume only), BillingArrangementBillInfo (cancel only), BillingArrangementName (INDY/CORP/extended contact with LinkType=71), BillingArrangementAddress (AE1-AE15), simple ResponseBase concept, IntraActivitySequencing fan-in.

**Historical note:** Lines 288–293 contain a commented-out alternative fan-in using `count(Account[string-length(trim(AccountID))=0]) == 0` — a count-based approach replaced by the current IntraActivitySequencing model.

### §19.3 Order-Type-Gated Writes

| Write Target | Gate | Content |
|---|---|---|
| `Account[i].ExtendedInfo[]` | OrderType == "11" (L9 Resume) | AccountExtendedInfo: Name="L9SplitParam", Value←L9SplitParam |
| `Account[i].BillingArrangementBillInfo` | OrderType == "12" or "11002" (Cancel) AND null | BillingArrangementBillInfo: BillFormat←L3BillFormat |

### §19.3b Name Mapping (GET_NAME_ADDRESS gate)

| NE | INDY (NameType=73) | CORP (other) | Extended Contact (LinkType=71) |
|----|-------------------|--------------|-------------------------------|
| NE1 | Title | OrgName | Language |
| NE2 | FirstName | BranchCode | PrefContactNumber |
| NE3 | MiddleName | BranchName | HomePhone |
| NE4 | LastName | StoreId | BizPhone |
| NE5 | MaritalStatus | FaxNumber | privatePhone |
| NE6 | FaxNumber | Email | AuthFirstName |
| NE7 | Email | IdentificationType | AuthLastName |
| NE8 | Gender | Identification | AuthPersonalId ✓ |
| NE9 | IdentificationType | — | POAName |
| NE10 | Identification | — | POAPersonalId |

### §19.3c Address Mapping (AE1-AE15, all ClearField-safe)

AE1→HouseNo, AE2→Moo, AE3→RoomNo, AE4→Floor, AE5→BuildingName, AE6→Soi, AE7→StreetName, AE8→Tumbon, AE9→Amphur, AE10→City, **AE11→Zip (ClearField check CORRECT — uses Zip field)**, AE12→Country, AE13→TimeAtAddress, AE14→TypeOfAccomodation, AE15→subSoi

### §19.4 Fan-in Completion

`IntraActivitySequencing.ActionResponseEvent(currActivity)` → `"true"` when all accounts complete; `"false"` while more are pending.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
