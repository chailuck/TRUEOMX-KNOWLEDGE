# Request_CCBS_VALIDATE_ACCT_STATUS_ROOT_OU

## §1 Overview & Purpose

**CCBS_VALIDATE_ACCT_STATUS_ROOT_OU** calls CCBS to validate the account status for each root-level Organizational Unit (ParentOU) associated with the customer. Used during ACTIVATION to verify account state before subscriber activation.

The rule fans out one CCBS request per ParentOU using IntraActivitySequencing (sends one at a time). The response returns rich account header data including credit information, collection status, agreement IDs, and billing details.

> Resubmit-aware: purges pending requests on resubmit, skips OUs with existing successful responses (`CompletionStatus==2`).

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_VALIDATE_ACCT_STATUS_ROOT_OU` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS |
| Send pattern | `Event.assertEvent` + `IntraActivitySequencing` — fan-out per POU, sequential |
| Response concept | `Concepts.FM.Response.CCBS_ValidateAcctStatusRootOURes` |
| Response rulefunction | `Response_CCBS_VALIDATE_ACCT_STATUS_ROOT_OU` |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — ParentOU array iterated |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | PreExecCheck, Response array, IntraActivitySequencing state |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_VALIDATE_ACCT_STATUS_ROOT_OU"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_VALIDATE_ACCT_STATUS_ROOT_OU"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Check resubmit: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. If resubmit: call `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
3. Loop over `ParentOU[0..n]`:
   - a. Skip if `Response[].ReferenceId == refId AND CompletionStatus==2`
   - b. Evaluate per-POU PreExecCheck via `GetXMLForOU` + `XPath.execute`
   - c. Build and assert request event for this POU
   - d. Call `IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)` — queue
   - e. Send REQ audit log
4. Call `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)` to trigger first queued request
5. Set status to ACTIVE, call `SendDataToDB`
6. If all POUs skipped: call `SkipActivity("4")`

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Protocol |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_VALIDATE_ACCT_STATUS_ROOT_OU` | JMS / assertEvent (one per POU) |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_VALIDATE_ACCT_STATUS_ROOT_OU` | JMS response |

### §8.3 Backend API

| System | Operation | Namespace |
|--------|-----------|-----------|
| CCBS | validateAccountStatusRootOU | `http://services.omx.truecorp.co.th/FMServices/validateAccountStatusRootOURequest` |

### §8.4 BE Working Memory Read

| Field | Purpose |
|-------|---------|
| `ParentOU[i].RefId` | POU reference — response correlation and skip check |
| `ParentOU[i].OUId` | CCBS OU identifier — sent in payload |
| `OrderData.Customer.CustomerId` | CCBS customer ID |
| `OrderData.User` / `Password` | Credentials — gated by `IsEnableUserPass='true'` |

---

## §9 Request Payload Tree

```text
createEvent
└── event
    ├── iPOU (xsl:variable)  ← number($i) + 1  (1-based index)
    ├── JMSPriority          ← $orderRequest/OrderPriority           [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID       [Conditional]
    ├── RefID                ← ParentOU[$iPOU]/RefId                 [Conditional]
    ├── UserName             ← $orderRequest/OrderData/User          [Credential-gated: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password      [Credential-gated: IsEnableUserPass='true']
    ├── OrderType            ← $orderRequest/OrderData/OrderType     [Conditional]
    ├── CES                  ← $orderRequest/OrderData/CES           [Conditional]
    └── payload
        └── ns:ValidateAccountStatusOURequest
            ├── ns:OUId      ← ParentOU[$iPOU]/OUId                  [Always]
            └── ns:customerId ← OrderData/Customer/CustomerId        [Always]
```

---

## §11 Audit Logging

| Log | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE |
|-----|-----------|----------------|-------------|
| [REQ] per POU | `concat(pid,"_REQ")` | `CCBS_VALIDATE_ACCT_STATUS_ROOT_OU` | `Request Sent for CCBS_VALIDATE_ACCT_STATUS_ROOT_OU` |
| [RES] per POU | `concat(pid,"_RES")` | `CCBS_VALIDATE_ACCT_STATUS_ROOT_OU` | `Response received for CCBS_VALIDATE_ACCT_STATUS_ROOT_OU` |

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → ACTIVE | At least one POU request sent | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| WAITING → SKIPPED | All POUs skipped | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| ACTIVE → COMPLETED | `IntraActivitySequencing.ActionResponseEvent(currActivity)` → true | `return "true"` |

> **IntraActivitySequencing:** Standard `RequestCount == successResponseCount` fan-in is **commented out**. Completion is handled by `IntraActivitySequencing.ActionResponseEvent` which sends the next queued request or signals completion.

---

## §13 Exception Handling

| Condition | Action |
|-----------|--------|
| Any exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §15 Function Dependency Tree

```text
Request_CCBS_VALIDATE_ACCT_STATUS_ROOT_OU
├── [if resubmit] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── for each ParentOU[i]
│   ├── check Response[].CompletionStatus==2 for refId  [skip check]
│   ├── GetXMLForOU(orderRequest, refId)
│   ├── XPath.execute(PreExecCheck, sXML, ns)
│   ├── Event.createEvent("xslt://.../CCBS_VALIDATE_ACCT_STATUS_ROOT_OU", ...)
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│   └── sendEventImmediate(Logger REQ)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
└── HandleActivityException(...)

Response_CCBS_VALIDATE_ACCT_STATUS_ROOT_OU
├── OMXUtils.generateTrackingID()
├── Instance.createInstance("xslt://.../CCBS_ValidateAcctStatusRootOURes")
│   → AccountHeaderArray (AccountBillingInfo, AccountCollectionInfo, AccountGeneralInfo,
│     AccountIdInfo, AccountingManagementInfo[L9* fields], AddressInfo, NameInfo)
│   → AgreementHeaderArray (AgreementId per AgreementNo)
├── currActivity.Response[n] = activityRes
├── sendEventImmediate(Logger RES)
└── IntraActivitySequencing.ActionResponseEvent(currActivity)
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Fan-out: send one CCBS request per ParentOU with OUId and customerId |
| R2 | Skip POUs with existing CompletionStatus=2 response (resubmit safety) |
| R3 | Per-POU PreExecCheck before sending |
| R4 | IntraActivitySequencing — send one at a time, not all in parallel |
| R5 | Response maps AccountHeaderArray with 30+ AccountingManagementInfo L9* fields |
| R6 | Credential gate: include UserName/Password only if IsEnableUserPass='true' |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Standard fan-in commented out — IntraActivitySequencing differs from other CCBS rules | [MEDIUM] | Document and reimplement equivalent sequenced fan-out in migration target |
| Very rich response concept (30+ L9* fields) | [LOW] | Document which downstream steps use specific L9* fields to scope migration |
| Credential gate in global variable — security-sensitive | [MEDIUM] | Verify IsEnableUserPass in all environments; do not default to 'true' |

---

## §18 Full Source Code

```java
// @author awalia-t420
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_VALIDATE_ACCT_STATUS_ROOT_OU {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when { /* ActivityID == "CCBS_VALIDATE_ACCT_STATUS_ROOT_OU", Status == "WAITING" */ }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      if(isActResub) IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      
      for (int i = 0; i < iPOULen; i++) {
        // Skip if Response[].ReferenceId == refId AND CompletionStatus==2
        // Evaluate per-POU PreExecCheck via GetXMLForOU
        // Build event via XSLT: ns:ValidateAccountStatusOURequest {OUId, customerId}
        //   [credential-gated UserName/PassWord — see §9]
        Event.assertEvent(reqEvent);
        IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
        // sendEventImmediate(Logger REQ)
      }
      if(!isSkipped) {
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
    } catch (Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
  }
}
```

## §19 Response Message Rule

### §19.1 Overview
Receives each POU response, creates `CCBS_ValidateAcctStatusRootOURes` with rich account data, appends to activity response array, calls `IntraActivitySequencing.ActionResponseEvent` to continue sequencing.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order (read only) |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_VALIDATE_ACCT_STATUS_ROOT_OU` | CCBS response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[] appended |

### §19.3 Response Concept Key Fields

| Section | Key Fields |
|---------|-----------|
| Base | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |
| AccountBillingInfo | BillingCurrency, TaxExemptionDate |
| AccountCollectionInfo | CollectionStatus, FullSuspensionIndicator, SuspensionType, PunishmentLevels |
| AccountGeneralInfo | LastUpdateDate, OpenDate |
| AccountIdInfo | AccountNo |
| AccountingManagementInfo | L9CreditClass, L9PrsnlCreditLimit, L9TempCreditLimit, L9IDDIndicator, L9IRIndicator, L9CompanyCode, L9LegacyBan, L9AgreementId, and 20+ other L9* fields |
| AgreementHeaderArray | AgreementId (from each AgreementNo) |

### §19.4 Response Completion Logic

> Standard `RequestCount == successResponseCount` fan-in is **commented out**. Uses `IntraActivitySequencing.ActionResponseEvent(currActivity)` — sends next queued request or signals completion.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
