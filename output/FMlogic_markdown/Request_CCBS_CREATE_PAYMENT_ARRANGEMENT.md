# Request_CCBS_CREATE_PAYMENT_ARRANGEMENT

> Creates a payment arrangement in CCBS per Account using PAST_DUE_AMOUNT. Per-account loop with reqSuccess guard. All business constants hardcoded. Final step in PROMISE_TO_PAY.

---

## §1 — Overview & Purpose

Creates a payment arrangement in CCBS for each Account using a rich static business configuration combined with dynamic data from the order (past-due amount, account ID, installment details).

Uses **IntraActivitySequencing** with a **per-account loop WITH reqSuccess check** — if the previous CCBS response for this account was already successful (CompletionStatus==2), the iteration is skipped to prevent duplicates.

> **[MEDIUM] Account[1]/AccountID inside per-account loop:** Multiple places reference `Account[1]/AccountID` inside the per-account loop. For multi-account orders, every iteration may use the first account's ID. Should be `$account/AccountID`.

> **[LOW] All business constants hardcoded:** AgreedPolicyCode="PTPPA", BrokenTreatmentType="RESUME", PayMentMethod="CA", IntervalType=68, PaymentArrangementIndicator=78 — not configurable without changing the rule file.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CREATE_PAYMENT_ARRANGEMENT` |
| Priority | 5 |
| ForwardChain | true |
| Rule File | `OMXFM/Request/Request_CCBS_CREATE_PAYMENT_ARRANGEMENT.rule` |
| Response Rulefunction | `Response_CCBS_CREATE_PAYMENT_ARRANGEMENT.rulefunction` |
| Backend System | CCBS (Customer Care & Billing System) |
| Dispatch Pattern | Per-account loop with reqSuccess guard, IntraActivitySequencing |
| Loop Variable | `orderRequest.OrderData.Customer.Account@length` |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order data including Account.ExtendedInfo[PAST_DUE_AMOUNT] |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity state, RequestCount, Response[] for reqSuccess |
| `$account` | `Concepts.OrderRequest.Account` | Per-iteration loop variable |
| `$refId` | String | Per-account reference ID for audit trace and correlation |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_CREATE_PAYMENT_ARRANGEMENT"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_CREATE_PAYMENT_ARRANGEMENT"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow

1. Compute `isActResub`
2. Call `PurgePendingRequestsBeforeResubmit` if `isActResub==true`
3. Loop `i = 0 to Account@length - 1`
4. Per iteration: check reqSuccess — if already succeeded → skip
5. Evaluate PreExecCheck via `GetXMLForAccount(orderRequest, refId)`
6. If PreExecCheck fails: skip this account
7. Build XSLT request (all static constants + dynamic account/amount data)
8. Assert event, `ActionRequestEvent`, emit per-account audit log
9. After loop: `SendFirstRequestEvent`
10. Status="1" + SendDataToDB

---

## §6 — Business Constants — All Hardcoded

| XSLT Parameter | Hardcoded Value | Business Meaning |
|----------------|----------------|-----------------|
| `AgreedPolicyCode` | "PTPPA" | Promise-to-Pay policy agreement code |
| `BrokenTreatmentType` | "RESUME" | Action when PTP is broken |
| `EntityType` | "ACCOUNT" | Entity scope |
| `PayMentMethod` | "CA" (Cash) | Payment method |
| `IntervalFactor` | 1 | Interval repetition factor |
| `InstallmentIntervalFactor` | 1 | Installment interval repetition factor |
| `IntervalType` | 68 | CCBS interval type code |
| `InstallmentIntervalType` | 68 | CCBS installment interval type code |
| `PaymentArrangementIndicator` | 78 | CCBS payment arrangement indicator code |
| `RemainingDueAmount` | 0.0 | Remaining amount after arrangement |
| `ExistingDueAmount` | 0.0 | Existing amount on account |
| `CollectorGroupCode` | " " (space) | Collector group (always space) |

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_CREATE_PAYMENT_ARRANGEMENT` | Create payment arrangement |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_CREATE_PAYMENT_ARRANGEMENT` | Confirmation / success flag |

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | CCBS (Amdocs) |
| Operation | CreatePaymentArrangement |
| Request Schema | `ns1:CreatePaymentArrangementRequest` |

### §8.5 ExtendedInfo Fields Required

| Name | Required/Optional | Purpose |
|------|------------------|---------|
| `PAST_DUE_AMOUNT` | Required | AgreedDueAmount in payload |
| `ActivityReasonCode` | Optional | ActivityReasonCode; defaults to "CREQ" |
| `Memo / UserText` | Optional | Memo in ns4:ActivityInformation |

---

## §9 — Detailed Payload Build

### §9.4 Payload Root Element (key fields)

| Element | Source / Value | Condition |
|---------|---------------|-----------|
| `ns2:PaymentArrangementInfo/AgreedDueAmount` | `ExtendedInfo[PAST_DUE_AMOUNT]/Value` | Always |
| `ns2:PaymentArrangementInfo/AgreedPolicyCode` | "PTPPA" (static) | Always |
| `ns2:PaymentArrangementInfo/BrokenTreatmentType` | "RESUME" (static) | Always |
| `ns2:PaymentArrangementInfo/EntityId` | `$account/AccountID` ⚠ | Always |
| `ns5:CollectorGroupCodeInfo/CollectorGroupCode` | " " (space, static) | Always |
| `ns4:ActivityInformation/ActivityReasonCode` | ExtendedInfo or "CREQ" | 2-way choose |
| `ns4:ActivityInformation/PaymentArrangementIndicator` | 78 (static) | Always |

### §9.7 Generated XML Example

```xml
<ns1:CreatePaymentArrangementRequest>
  <ns2:PaymentArrangementInfo>
    <AgreedDueAmount>1500.00</AgreedDueAmount>
    <AgreedPolicyCode>PTPPA</AgreedPolicyCode>
    <BrokenTreatmentType>RESUME</BrokenTreatmentType>
    <EntityId>100012345</EntityId>
    <EntityType>ACCOUNT</EntityType>
    <ExistingDueAmount>0.0</ExistingDueAmount>
    <InstallmentPlan>
      <IntervalFactor>1</IntervalFactor>
      <IntervalType>68</IntervalType>
    </InstallmentPlan>
    <Installments>
      <DueAmount>1500.00</DueAmount>
      <DueDate>2026-10-01</DueDate>
      <EntityId>100012345</EntityId>
      <EntityType>ACCOUNT</EntityType>
    </Installments>
    <IntervalFactor>1</IntervalFactor>
    <IntervalType>68</IntervalType>
    <PaymentMethodDetails><PaymentMethod>CA</PaymentMethod></PaymentMethodDetails>
    <RemainingDueAmount>0.0</RemainingDueAmount>
  </ns2:PaymentArrangementInfo>
  <ns5:CollectorGroupCodeInfo>
    <CollectorGroupCode> </CollectorGroupCode>
  </ns5:CollectorGroupCodeInfo>
  <ns4:ActivityInformation>
    <ActivityReasonCode>CREQ</ActivityReasonCode>
    <Memo>Payment arrangement memo</Memo>
    <PaymentArrangementIndicator>78</PaymentArrangementIndicator>
  </ns4:ActivityInformation>
  <ns3:ClEntityIdInfo>
    <EntityId>100012345</EntityId>
    <EntityType>ACCOUNT</EntityType>
  </ns3:ClEntityIdInfo>
</ns1:CreatePaymentArrangementRequest>
```

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| Guard | None — always logs (payload conditional) |
| PROCESS_ID | `concat(pid, "_REQ")` |
| OPERATION_NAME | "CCBS_CREATE_PAYMENT_ARRANGEMENT" |
| AUDIT_TRACE | `concat("Request Sent for RefId ", $refId)` (per-account) |
| Payload | `<ns:ServicePayload>` always present; WritePayload conditional inside |
| Timing | Per loop iteration (per Account) |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_CREATE_PAYMENT_ARRANGEMENT.rule
├── PurgePendingRequestsBeforeResubmit(...)           [conditional]
├── [Loop: i=0 → Account@length-1]
│   ├── XPath.evalAsInt(Response[RefId=$refId and CompletionStatus=2])  [reqSuccess check]
│   ├── GetXMLForAccount(orderRequest, refId)                           [account-scoped XML]
│   ├── XPath.execute(chkXPath, accountXML, ns)                        [PreExecCheck per account]
│   ├── Event.createEvent(XSLT → CCBS_CREATE_PAYMENT_ARRANGEMENT)
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   └── Event.Ext.sendEventImmediate(logger, "Request Sent for RefId "+refId)
├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
└── HandleActivityException(...)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Create payment arrangement in CCBS per Account using PAST_DUE_AMOUNT |
| R2 | Apply fixed policy: AgreedPolicyCode="PTPPA", BrokenTreatmentType="RESUME", PaymentMethod="CA" |
| R3 | Set CollectorGroupCode=" " (space, always) |
| R4 | ActivityReasonCode from ExtendedInfo or "CREQ" default |
| R5 | Skip account if previous attempt already succeeded (reqSuccess guard) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `Account[1]/AccountID` inside per-account loop — may always use first account | [MEDIUM] | Change to `$account/AccountID` in all loop references |
| All business constants hardcoded | [LOW] | Move to ProcessConfig params or Global Variables |
| CollectorGroupCode always " " (space) | [LOW] | Verify CCBS accepts single-space as valid empty group code |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_CREATE_PAYMENT_ARRANGEMENT {
  attribute { priority = 5; forwardChain = true; }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
    if (isActResub) { PurgePendingRequestsBeforeResubmit(orderRequest, orderCurrentActivity); }
    try {
      for (int i = 0; i < orderRequest.OrderData.Customer.Account@length; i++) {
        Account account = orderRequest.OrderData.Customer.Account[i];
        String refId = ...; // per-account refId
        int reqSuccess = XPath.evalAsInt("count(Response[RefId=refId and CompletionStatus=2])", ...);
        if (reqSuccess > 0) { continue; }
        String accountXML = GetXMLForAccount(orderRequest, refId);
        /* PreExecCheck evaluated per-account; if fails → skip account */
        Events...CCBS_CREATE_PAYMENT_ARRANGEMENT reqEvent = Event.createEvent("xslt://...");
        /* XSLT: ns1:CreatePaymentArrangementRequest — see §9 and §10 */
        /* Static: AgreedPolicyCode=PTPPA, BrokenTreatmentType=RESUME, PayMentMethod=CA */
        /* Static: IntervalType=68, PaymentArrangementIndicator=78, CollectorGroupCode=" " */
        /* Dynamic: AgreedDueAmount=PAST_DUE_AMOUNT, EntityId=$account/AccountID */
        /* NOTE: some references use Account[1]/AccountID inside loop */
        Event.assertEvent(reqEvent);
        IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
        Event.Ext.sendEventImmediate(logEvent); // AUDIT_TRACE = "Request Sent for RefId " + refId
      }
      IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
      orderCurrentActivity.Status = GetActivityStatusString("1", false);
      SendDataToDB(orderRequest);
    } catch (Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

Creates a `CCBSCreatePaymentArrangement` response concept, performs no additional post-processing, logs, and advances fan-in. Response is purely a confirmation record.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | No fields written back |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_CREATE_PAYMENT_ARRANGEMENT` | CCBS confirmation |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking |

### §19.3 Response Concept

Type: `Concepts.FM.Response.CCBSCreatePaymentArrangement` (specific)

extId: `OMXUtils.generateTrackingID()` (direct call)

### §19.4 Post-Processing

None — no order data updated by response handler.

### §19.5 Fan-in & Completion

| Field | Value |
|-------|-------|
| Pattern | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Returns "true" | When all per-account payment arrangement requests have responded |
| AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` |
| Audit | Conditional WritePayload |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
