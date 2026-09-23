# Request_CCBS_GET_CUST_ACC_SUB_ID

> TIBCO BusinessEvents FM Logic — CCBS resolve Customer ID, Account ID and Subscriber ID from MSISDN (dual-loop COU+POU fan-out)

**Author:** snarayan-t430 | **Priority:** 5 · forwardChain=true | **Pattern:** Standard Parallel Fan-Out (dual-loop) | **Generated:** 2026-08-04

---

## §1 Overview & Purpose

**CCBS_GET_CUST_ACC_SUB_ID** resolves three key CCBS internal identifiers — `CustomerId`, `AccountId`, and `SubscriberId` — from a subscriber's MSISDN. It is called once per subscriber across both ChildOU and ParentOU subscriber lists.

Unlike most OMXFM rules that use a single loop, this rule employs a **dual-loop fan-out**: it first iterates all ChildOU subscribers, then all ParentOU subscribers within each POU. Each eligible subscriber gets its own independent request event.

The rule supports **resubmit handling**: on retry, subscribers whose responses already have `CompletionStatus==2` (success) are skipped — avoiding duplicate CCBS calls.

> **ParameterType Hint:** If the subscriber has an ExtendedInfo entry `PRIMARY_RESOURCE_TYPE`, its value is sent as a `ParameterType` field in the request — allowing CCBS to resolve the resource by a non-MSISDN type (e.g., data SIM ICCID).

> **SOURCE param:** When the activity's first Parameter = "SOURCE", the resolved CustomerId is stored as `ExtendedInfo["SOURCE_CUSTOMER_ID"]` on the Customer (the originating customer in a port-in scenario) rather than overwriting `Customer.CustomerId`.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_CUST_ACC_SUB_ID` |
| Author | snarayan-t430 |
| Priority | 5 |
| Forward chain | true |
| Backend system | CCBS / AMDOCS L9 |
| Operation | GetCustAccSubID (resolve IDs from MSISDN) |
| Response concept | `Concepts.FM.Response.CCBS_GetCustAccSubID` |
| Fan-out pattern | Standard parallel fan-out (dual COU+POU loop) |
| Resubmit support | Yes — skips subscribers with CompletionStatus==2 |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — contains all subscribers (POU and COU) |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — holds PreExecCheck, Parameter[1], RequestCount, Response array |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Notes |
|---|-----------|-------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity is the next to execute |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_GET_CUST_ACC_SUB_ID"` | Exact match |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_CUST_ACC_SUB_ID"` | Process flow agreement |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Not yet dispatched |

---

## §5 Execution Flow

1. Compute `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Resolve `nextAct` via `Instance.getByExtIdByUri(NextActivityName, Activity)` (needed for PreExecCheck)
3. Read ALT_CES param: `GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")`
4. **COU loop:** For each POU → each ChildOU → each ChildOU Subscriber: skip if already successful (resubmit); evaluate per-subscriber PreExecCheck; fire request event
5. **POU loop:** For each POU → each POU Subscriber: same skip / PreExecCheck / fire logic
6. Per-eligible subscriber: Create and fire `CCBS_GET_CUST_ACC_SUB_ID` event; emit audit log; increment `RequestCount` (if not resubmit)
7. If at least one request was sent (`!isSkipped`): `GetActivityStatusString("1", false)` + `SendDataToDB()`
8. If all subscribers were skipped: `SkipActivity(orderRequest, orderCurrentActivity, "4")`
9. Any error → `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §6 Rule Action (THEN) — Detailed Logic

### §6.1 Resubmit Skip Gate

On resubmit, a subscriber is skipped if a response already exists with matching `RefId` AND `CompletionStatus == 2`:

```java
for(iResp = 0; iResp < Response@length; iResp++) {
  if (Response[iResp].ReferenceId == refId && Response[iResp].CompletionStatus == 2) {
    reqSuccess = true;   // skip this subscriber
  }
}
```

### §6.2 Per-Subscriber Runtime PreExecCheck

If the activity has a `PreExecCheck` expression, it is evaluated **per subscriber** at runtime:

| Subscriber type | XML Builder | XPath Evaluator |
|-----------------|-------------|-----------------|
| ChildOU subscriber | `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` | `XPath.execute("/("+chkXPath+")", sXML, ...)` |
| POU subscriber | `GetXMLForSubscriber(orderRequest, refId)` | `XPath.execute("/("+chkXPath+")", sXML, ...)` |

Only if `chkRes == "true"` is the request event fired for that subscriber.

### §6.3 ALT_CES Routing

```text
when: altParam="Y" AND OrderData/ExtendedInfo[Name="ALT_CES"]/Value != ""
  → CES = OrderData/ExtendedInfo["ALT_CES"]/Value
otherwise:
  → CES = OrderData/CES
```

> Note: ALT_CES for this FM reads from **OrderData/ExtendedInfo** (not SubscriberExtendedInfo).

### §6.4 Request Count Increment

```java
if(!isActResub) {
  orderCurrentActivity.RequestCount++;   // only on first execution, not on resubmit
}
```

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Protocol |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_GET_CUST_ACC_SUB_ID` | JMS → CCBS SOAP |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_GET_CUST_ACC_SUB_ID` | JMS |

### §8.3 Backend API Details

| Property | Value |
|----------|-------|
| System | CCBS / AMDOCS L9 |
| Operation | GetCustAccSubID |
| Key input | SubNumber (subscriber MSISDN) |
| Optional input | ParameterType (from ExtendedInfo["PRIMARY_RESOURCE_TYPE"]) |
| Key outputs | CustomerId, AccountId, SubscriberId, CustomerType |
| Correlation | RefID = subscriber RefId; response lookup via extId "SUB:…:RefId" / "CSUB:…:RefId" |

### §8.4 BE Working Memory — Fields Written (Response)

| Concept | Field | Source | Condition |
|---------|-------|--------|-----------|
| Subscriber | `SubscriberId` | activityRes.SubscriberId | activityRes.SubscriberId != null |
| Customer | `ExtendedInfo["SOURCE_CUSTOMER_TYPE"]` | activityRes.CustomerType | activityRes.CustomerType != null |
| Customer | `ExtendedInfo["SOURCE_CUSTOMER_ID"]` | activityRes.CustomerId | param=="SOURCE" AND CustomerId != null |
| Customer | `CustomerId` | activityRes.CustomerId | param!="SOURCE" AND CustomerId != null |
| Account | `AccountID` | activityRes.AccountId | AccountId != null AND subscriber.AccountRefId != null |
| Account | `PayChannelId` | = AccountID (copy) | Always when AccountID set |
| Account | `AgreementRefId` | pOU.RefId or pOU.Agreement.RefId (or cOU variant) | Only if AgreementRefId currently blank |
| Subscriber | `ExtendedInfo["DONOR_ACCOUNT_ID"]` | activityRes.AccountId | AccountId != null AND subscriber.AccountRefId != null |

> **Account creation:** If no Account concept exists for the subscriber's AccountRefId, a new Account concept is created and appended to Customer.Account. This means the Account concept may not exist before this FM runs — it is the *bootstrapper* for the account graph node.

### §8.5 ExtendedInfo Fields Required

| Key | Required | Usage |
|-----|----------|-------|
| `PRIMARY_RESOURCE_TYPE` | Optional (subscriber) | Sent as ParameterType in request — tells CCBS the resource type for lookup |
| `ALT_CES` | Optional (order) | CES endpoint override — read from OrderData/ExtendedInfo |

### §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Gate for credential headers |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit logger component name |
| `OMX_OM/WritePayload` | Gate for payload capture in audit log |

> **Note:** IsEnableUserPass path differs from CCBS_GET_SUBSCRIBER_HEADER — here it is under `OMX_OM/Rules/OMConsumers/OMXFM/Request/` not `OMX_COMMON/_SharedResources/Common/`.

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameters

| Param | Bound from |
|-------|-----------|
| `$orderRequest` | Working memory OrderRequest |
| `$refId` | Subscriber.RefId (loop variable) |
| `$globalVariables` | BE global variables |
| `$altParam` | `GetActivityParameterValueFromKey("ALT_CES")` |
| `$i` / `$k` / `$l` | Loop indices (POU, COU, COU Subscriber) — COU variant |
| `$i` / `$j` | Loop indices (POU, POU Subscriber) — POU variant |

### §9.2 Request Event Fields — COU Variant

```xml
<event>
  <JMSPriority>$orderRequest/OrderPriority</JMSPriority>  <!-- conditional -->
  <JMSCorrelationID>$orderRequest/OrderData/OMXTrackingId</JMSCorrelationID>
  <OrderID>$orderRequest/OrderData/OrderID</OrderID>
  <RefID>$refId</RefID>
  <UserName>$orderRequest/OrderData/User</UserName>  <!-- credential-gated -->
  <PassWord>$orderRequest/OrderData/Password</PassWord>  <!-- credential-gated -->
  <OrderType>$orderRequest/OrderData/OrderType</OrderType>
  <CES>[ALT_CES or OrderData/CES]</CES>
  <SubNumber>ParentOU[i+1]/ChildOU[k+1]/Subscriber[l+1]/MSISDN</SubNumber>
  <ParameterType>ExtendedInfo[PRIMARY_RESOURCE_TYPE]/Value</ParameterType>  <!-- conditional -->
</event>
```

POU variant is identical except `SubNumber` uses `ParentOU[i+1]/Subscriber[j+1]/MSISDN` (no ChildOU nesting).

---

## §10 XSLT Field Mapping Tree

*COU Variant (Variant ①)*

```text
event
├── JMSPriority              ← $orderRequest/OrderPriority                               [Conditional]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId                    [Conditional]
├── OrderID                  ← $orderRequest/OrderData/OrderID                           [Conditional]
├── RefID                    ← $refId (subscriber loop variable)                         [Always]
├── UserName                 ← $orderRequest/OrderData/User                              [Credential-gated: IsEnableUserPass='true']
├── PassWord                 ← $orderRequest/OrderData/Password                          [Credential-gated: IsEnableUserPass='true']
├── OrderType                ← $orderRequest/OrderData/OrderType                         [Conditional]
├── CES                      ← ExtendedInfo[ALT_CES]/Value OR OrderData/CES             [Conditional: ALT_CES routing]
├── SubNumber                ← ParentOU[i+1]/ChildOU[k+1]/Subscriber[l+1]/MSISDN        [Always]
└── ParameterType            ← Subscriber/ExtendedInfo[PRIMARY_RESOURCE_TYPE]/Value     [Conditional: exists(ExtendedInfo)]
```

Legend: `← XPath source` · `[Always]` = unconditional · `[Conditional]` = inside xsl:if · `[Credential-gated]` = gated on global IsEnableUserPass

---

## §11 Audit Logging

**Request audit** (fired per subscriber, after each request event):

| Field | Value |
|-------|-------|
| OPERATION_NAME | `CCBS_GET_CUST_ACC_SUB_ID` (static) |
| AUDIT_TRACE | `Request Sent for CCBS_GET_CUST_ACC_SUB_ID` |
| PROCESS_ID | `concat(pid, "_REQ")` |

**Response audit** (fired in response rulefunction):

| Field | Value |
|-------|-------|
| OPERATION_NAME | `$currActivity/ActivityID` (dynamic — reads from activity) |
| AUDIT_TRACE | `concat("Response received for ", $currActivity/ActivityID)` |
| PROCESS_ID | `concat(pid, "_RES")` |

---

## §12 Activity Status Management

| Call | Code | Meaning |
|------|------|---------|
| `GetActivityStatusString("1", false)` | 1 | Active / In-Progress |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | 4 | All subscribers skipped |

---

## §13 Exception / Error Handling

```java
catch (Exception ae) {
  RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

All exceptions are delegated to the standard `HandleActivityException` helper — no custom recovery logic in this rule.

---

## §14 Helper Functions Reference

| Function | Signature | Purpose |
|----------|-----------|---------|
| `GetActivityParameterValueFromKey` | (Activity, String) → String | Read ALT_CES activity parameter |
| `GetXMLForSubscriberInChildOU` | (orderRequest, refId, pouRefId) → String | Serialize COU subscriber context XML for XPath evaluation |
| `GetXMLForSubscriber` | (orderRequest, refId) → String | Serialize POU subscriber context XML for XPath evaluation |
| `GetActivityStatusString` | (String, boolean) → String | Returns activity status string |
| `SendDataToDB` | (orderRequest) → void | Persists activity state |
| `SkipActivity` | (orderRequest, Activity, String) → void | Sets SKIP status |
| `HandleActivityException` | (orderRequest, Activity, Exception, String) → void | Centralized error handling |
| `Instance.getByExtIdByUri` | (extId, uri) → Concept | Response: looks up subscriber by "SUB:" or "CSUB:" prefix extId |

---

## §15 Function Dependency Tree

```text
Request_CCBS_GET_CUST_ACC_SUB_ID (rule)
├── GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")
├── Instance.getByExtIdByUri(NextActivityName, Activity)  [get nextAct for PreExecCheck]
├── [COU loop]
│   ├── GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)
│   ├── XPath.execute(chkXPath, sXML, ...)   [per-subscriber PreExecCheck]
│   ├── Event.createEvent(CCBS_GET_CUST_ACC_SUB_ID XSLT)  [per subscriber]
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   ├── Event.Ext.sendEventImmediate(Logger)
│   └── orderCurrentActivity.RequestCount++
├── [POU loop]  (same structure, GetXMLForSubscriber instead of COU variant)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_CCBS_GET_CUST_ACC_SUB_ID (rulefunction)
├── Instance.createInstance(CCBS_GetCustAccSubID XSLT)
├── Instance.getByExtIdByUri("SUB:"+trackId+":"+RefID, Subscriber)
│   └── fallback: Instance.getByExtIdByUri("CSUB:…", Subscriber)
├── XPath.evalAsString(currActivity/Parameter[1])   [param="SOURCE" check]
├── [if SubscriberId]: subscriber.SubscriberId = activityRes.SubscriberId
├── [if CustomerType]: Instance.createInstance(CustomerExtendedInfo)
│   └── customer.ExtendedInfo["SOURCE_CUSTOMER_TYPE"] = CustomerType
├── [if CustomerId]:
│   ├── [if SOURCE param]: customer.ExtendedInfo["SOURCE_CUSTOMER_ID"] = CustomerId
│   └── [otherwise]: customer.CustomerId = CustomerId
├── [if AccountId && AccountRefId]:
│   ├── Instance.getByExtIdByUri("A:…:AccountRefId", Account)
│   │   ├── [if null]: Instance.createInstance(Account) → customer.Account.append
│   │   └── [if found]: account.AccountID = AccountId
│   ├── subscriber.ExtendedInfo["DONOR_ACCOUNT_ID"] = AccountId
│   ├── account.PayChannelId = account.AccountID
│   └── [if AgreementRefId blank]:
│       ├── Instance.getByExtId(pOUExtId)  → pOU.Agreement.RefId or pOU.RefId
│       └── Instance.getByExtId(cOUExtId)  → cOU.Agreement.RefId or cOU.RefId
├── Event.Ext.sendEventImmediate(Logger)
└── XPath.evalAsInt(count(Response[tib:right(ResponseCode,3)="000"]))
    └── if == RequestCount → return "true" else "false"
```

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Fan-out across both COU and POU subscribers — dual-loop required |
| R2 | Resubmit safety: skip subscribers with CompletionStatus==2 on retry |
| R3 | Per-subscriber runtime PreExecCheck evaluation (not activity-level only) |
| R4 | Optional ParameterType hint from ExtendedInfo["PRIMARY_RESOURCE_TYPE"] |
| R5 | ALT_CES routing from OrderData/ExtendedInfo (not SubscriberExtendedInfo) |
| R6 | SOURCE param branch: CustomerId stored as ExtendedInfo vs Customer.CustomerId |
| R7 | Account bootstrapping: create Account node if it doesn't exist yet |
| R8 | AgreementRefId resolution: POU then COU fallback |
| R9 | DONOR_ACCOUNT_ID written to Subscriber.ExtendedInfo alongside Account.AccountID |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Per-subscriber XML serialization for PreExecCheck is expensive — serializes order graph per subscriber | [MEDIUM] | Evaluate using native graph traversal in new system |
| Subscriber lookup via string-prefix extId ("SUB:" / "CSUB:") is fragile — breaks if extId convention changes | [HIGH] | Replace with explicit subscriber reference in modern data model |
| Account bootstrapping in response — account may be created or pre-existing; dual code paths | [MEDIUM] | Ensure idempotent account lookup in migration |
| AgreementRefId resolution traverses POU then COU with XPath over in-memory object graph — implicit graph traversal | [MEDIUM] | Make agreement-ref explicit in new subscriber model |
| IsEnableUserPass global path differs from other CCBS FMs — inconsistency risk | [MEDIUM] | Standardise credential gate path across all FMs |

---

## §18 Full Source Code (Request Rule — condensed)

```java
/**
 * Request_CCBS_GET_CUST_ACC_SUB_ID
 * Author: snarayan-t430 | Priority: 5 | forwardChain: true
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_CUST_ACC_SUB_ID {
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CCBS_GET_CUST_ACC_SUB_ID";
    orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_CUST_ACC_SUB_ID";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Activity nextAct = Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
      String altParam = GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES");
      boolean isSkipped = true;

      // COU loop: POU → ChildOU → COU Subscriber
      for (i → COU → l) {
        refId = Subscriber[l].RefId;
        // skip if already succeeded on resubmit
        // evaluate per-subscriber PreExecCheck via GetXMLForSubscriberInChildOU
        // if passes: fire reqEvent, audit log, RequestCount++
        // (see §9.2 for event fields: JMSPriority, JMSCorrelationID, OrderID, RefID,
        //   UserName, PassWord, OrderType, CES, SubNumber, ParameterType)
      }
      // POU loop: POU → POU Subscriber (same pattern via GetXMLForSubscriber)
      for (i → j) { ... }

      if(!isSkipped) {
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

The response handler resolves CCBS IDs back into the OMX order graph:

1. Creates `CCBS_GetCustAccSubID` concept (random extId) — captures CustomerId, AccountId, SubscriberId, CustomerType alongside standard ResponseBase fields
2. Looks up subscriber in working memory by extId prefix ("SUB:" POU, "CSUB:" COU fallback)
3. Writes `subscriber.SubscriberId`
4. Writes `customer.ExtendedInfo["SOURCE_CUSTOMER_TYPE"]`
5. Branches on `param=="SOURCE"` for CustomerId routing
6. Bootstraps or updates Account concept with AccountID + AgreementRefId
7. Writes `subscriber.ExtendedInfo["DONOR_ACCOUNT_ID"]` and `account.PayChannelId`
8. Emits audit log; fan-in via `RequestCount == successResponseCount`

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order graph — enriched |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_GET_CUST_ACC_SUB_ID` | CCBS response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Holds Response array, RequestCount |

### §19.3 Response Concept Construction

```text
CCBS_GetCustAccSubID
├── extId            ← OMXUtils.generateTrackingID() (random)                      [Always]
├── ResponseCode     ← $eventResponse/ResponseCode                                  [Conditional]
├── ResponseMessage  ← $eventResponse/ResponseMsg                                   [Conditional]
├── CompletionStatus ← $eventResponse/CompletionStatus                              [Conditional]
├── ReferenceId      ← $eventResponse/RefID                                         [Conditional]
├── CustomerId       ← $eventResponse/CustomerId                   [Conditional: string-length > 0]
├── AccountId        ← $eventResponse/AccountId                    [Conditional: string-length > 0]
├── SubscriberId     ← $eventResponse/SubscriberId                 [Conditional: string-length > 0]
└── CustomerType     ← $eventResponse/CustomerType                 [Conditional: string-length > 0]
```

### §19.4 Response Completion Logic

| Expression | Value | Meaning |
|------------|-------|---------|
| `successResponseCount` | `count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)="000"])` | Number of "000" suffix responses |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` | All expected subscriber calls returned success → "true" |
| Return "false" | Otherwise | More responses expected; order waits |

### §19.5 CustomerId Routing (SOURCE param)

| Condition | Action |
|-----------|--------|
| `param == "SOURCE"` | CustomerId → `Customer.ExtendedInfo["SOURCE_CUSTOMER_ID"]` (source customer for port-in, not the target) |
| `param != "SOURCE"` | CustomerId → `Customer.CustomerId` (direct assignment) |

### §19.6 Account Bootstrap Logic

```java
if(activityRes.AccountId != null && subscriber.AccountRefId != null) {
  account = getByExtId("A:"+trackId+":"+subscriber.AccountRefId);
  if(account == null) {
    account = createAccount(AccountID=activityRes.AccountId, RefId=subscriber.AccountRefId);
    customer.Account.append(account);
  } else {
    account.AccountID = activityRes.AccountId;
  }
  subscriber.ExtendedInfo["DONOR_ACCOUNT_ID"] = activityRes.AccountId;
  account.PayChannelId = account.AccountID;

  if(AgreementRefId is blank) {
    pOU = find POU containing this subscriber;
    account.AgreementRefId = (pOU.Agreement != null) ? pOU.Agreement.RefId : pOU.RefId;
    // fallback: check cOU if pOU not found
  }
}
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
