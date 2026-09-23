# Request_BL_CREATE_CHARGE

> Billing system charge creation — iterates all subscriber offers carrying a charge amount and dispatches Amdocs BL3G CreateCharge requests via throttled sequential fan-out.

**Author:** RS33-BANDIT | **Namespace:** Rules.OMConsumers.OMXFM.Request | **Priority:** 5 | **ForwardChain:** true | **Target:** Amdocs BL3G (OMX_FM)

---

## §1 Overview & Purpose

`BL_CREATE_CHARGE` is the billing-charge dispatch step in the ACTIVATION_CREATE_SUBSCRIBER flow. It iterates over all `SubscriberOffers` that carry an `AMOUNT` ExtendedInfo value and sends a `CreateCharge` request to the Amdocs BL3G billing system for each one.

> **Upstream dependency:** The SubscriberOffers with `ServiceType="79"` and AMOUNT ExtendedInfo that trigger this FM are dynamically injected into working memory by the **SBM_BUY_DATA_PACK response handler** when its `featureCode` field is non-blank. BL_CREATE_CHARGE is therefore a downstream billing confirmation for data pack purchases.

**Two dispatch variants** are selected based on the offer's `REVENUE_CODE` ExtendedInfo:
- `REVENUE_CODE = "UC"` → Full charge record: `ChargeOrigin="ML"`, `ChargeType` (DBT/CRD), attribute `"Carry over status" = "N"`
- All other / no `REVENUE_CODE` → Simplified charge: attribute `"Activity code" = "45"`; dispatched only when `amount > 0`

Fan-out uses **IntraActivitySequencing** (throttled sequential dispatch) identical to SBM_BUY_DATA_PACK.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name (full) | `Rules.OMConsumers.OMXFM.Request.Request_BL_CREATE_CHARGE` |
| File | `Rules/OMConsumers/OMXFM/Request/Request_BL_CREATE_CHARGE.rule` |
| Priority | 5 |
| ForwardChain | true |
| Author | RS33-BANDIT |
| Namespace | OMXFM (external FM via JMS) |
| Response handler | `RuleFunctions.OrderResponse.Response_BL_CREATE_CHARGE` |
| Target system | Amdocs BL3G (OMX_FM billing layer) |
| Dispatch pattern | IntraActivitySequencing — throttled sequential fan-out |

---

## §3 Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order graph — Customer hierarchy, ExtendedInfo, OrderData |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step — RequestCount, Response[], PreExecCheck, Status |

> **Note:** `LogicalDate` concept is loaded in the rule body but the value is not used in the charge event payload — vestigial code from a copy-paste template.

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Binds current activity to the order's active step |
| 2 | `orderCurrentActivity.ActivityID == "BL_CREATE_CHARGE"` | Guards this rule to the BL_CREATE_CHARGE step only |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "BL_CREATE_CHARGE"` | Double-check: order process pointer also points to BL_CREATE_CHARGE |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Fires only when the activity is in WAITING state |

---

## §5 Execution Flow Diagram

```text
1. Resubmit guard → PurgePendingRequestsBeforeResubmit if RequestCount>0 AND IsOrderResubmitted
2. LogicalDate load (vestigial — not used in payload)
3. POU iteration: loop Customer.ParentOU[].Subscriber[].SubscriberOffers[]
   3a. Compute refId = sub.RefId + ":" + subOff.OfferName
   3b. Check Response[] for prior success (skip if reqSuccess)
   3c. Run PreExecCheck if defined
   3d. Extract amount / description / revenueCode via XPath
   3e. IF revenueCode == "UC" → dispatch UC charge (any amount, incl ≤0)
       ELSE IF amount > 0 → dispatch standard charge
4. COU iteration: loop Customer.ParentOU[].ChildOU[].Subscriber[].SubscriberOffers[]
   4a. Skip ServiceType == "80" offers
   4b. Reverse amount lookup: sub first → subOff
   4c. IF amount > 0 → dispatch standard charge (no UC path for COU)
5. After loops:
   IF !isSkipped → SendFirstRequestEvent + Status=1 + SendDataToDB
   ELSE → SkipActivity("4")
6. Exception → HandleActivityException
```

---

## §6 Rule Action (THEN) — Key Logic Detail

### RefID Construction

```java
String refId = sub.RefId + ":" + subOff.OfferName;
```

> **Simpler than SBM:** BL_CREATE_CHARGE uses a 2-segment RefID (`subRefId:OfferName`), whereas SBM_BUY_DATA_PACK uses 4-segment (`pOuRefId::subRefId:soc`). These are not interchangeable.

### Amount / Description Resolution — POU vs COU

| Field | POU lookup order | COU lookup order |
|-------|-----------------|-----------------|
| `amount` | subOff/ExtendedInfo[AMOUNT] → sub/ExtendedInfo[AMOUNT] → "0" | sub/ExtendedInfo[AMOUNT] → subOff/ExtendedInfo[AMOUNT] |
| `description` | subOff/ExtendedInfo[DESCRIPTION] → sub/ExtendedInfo[DESCRIPTION] → "" | sub/ExtendedInfo[DESCRIPTION] only |
| `revenueCode` | subOff/ExtendedInfo[REVENUE_CODE] → "" | Not evaluated (no UC branch for COU) |

> **Design inconsistency:** Amount lookup order is reversed between POU and COU. A subscriber with AMOUNT on both sub and offer levels would get different charge amounts depending on OU context.

### REVENUE_CODE == "UC" Branch (POU Only)

Triggered when `subOff/ExtendedInfo[Name='REVENUE_CODE']/Value == "UC"`. Dispatches even when `amount ≤ 0` (credit entries are valid). `ChargeType = if(amount > 0) "DBT" else "CRD"`.

### COU ServiceType="80" Exclusion

```java
if(!String.equals(subOff.ServiceType, "80")) { ... }
```

ServiceType "80" offers under COU are excluded from charge dispatch to prevent double-billing.

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

Triggered by any order type that results in data pack purchases through SBM_BUY_DATA_PACK where the SBM response returns a non-blank `featureCode`. No OrderType filter in this FM.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Protocol | Purpose |
|-----------|-----------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.BL_CREATE_CHARGE` | JMS/XSLT | Send CreateCharge to Amdocs BL3G |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | JMS (immediate) | Request audit trail |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.BL_CREATE_CHARGE` | JMS | CreateCharge result (ChargeId, ResponseCode) |

### §8.3 Backend API Details

| System | Operation | Schema | Correlation |
|--------|-----------|--------|-------------|
| Amdocs BL3G | CreateCharge | `ns:CreateChargeRequest` / `amdocs.bl3g.datatypes` | RefID = `sub.RefId:subOff.OfferName` |

### §8.4 BE Working Memory Dependencies

| Field | Read/Write | Source |
|-------|-----------|--------|
| `orderRequest.OrderData.Customer.ParentOU[].Subscriber[].SubscriberOffers[]` | READ | POU subscriber offers |
| `orderRequest.OrderData.Customer.ParentOU[].ChildOU[].Subscriber[].SubscriberOffers[]` | READ | COU subscriber offers (excl ServiceType=80) |
| `subOff.ExtendedInfo[AMOUNT]/Value` | READ | Charge amount (injected by SBM response) |
| `subOff.ExtendedInfo[DESCRIPTION]/Value` | READ | Charge description |
| `subOff.ExtendedInfo[REVENUE_CODE]/Value` | READ | Routing key: "UC" → full charge path |
| `subOff.ExtendedInfo[FE_OR_CCBS]/Value` | READ | PreExecCheck filter context |
| `subOff.EffectiveDate` | READ | Charge effective date in payload |
| `orderCurrentActivity.Response[]` | READ/WRITE | Fan-in tracking |
| `orderCurrentActivity.Status` | WRITE | Set to "1" after first dispatch |

### §8.5 ExtendedInfo Fields Required

| Key | Required/Optional | Source | Used for |
|-----|------------------|--------|----------|
| AMOUNT | Required (charge skipped if 0) | Injected by SBM_BUY_DATA_PACK response | Charge amount; gates dispatch in standard path |
| DESCRIPTION | Optional | Injected by SBM response | `ns1:Description` in payload |
| REVENUE_CODE | Optional | Offer configuration | Routes to UC vs standard charge path (POU only) |
| FE_OR_CCBS | Optional | SBM response | PreExecCheck XPath filter context |

### §8.6 Global Variable Dependencies

| Path | Used for |
|------|----------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Gates payload inclusion in audit log |

---

## §9 Detailed Payload Build — Two XSLT Variants

### §9.1 Variant Comparison — ChargeInfo Payload Fields

| Field (ns1:) | UC Path (POU) | Standard Path (POU) | Standard Path (COU) |
|-------------|--------------|--------------------|--------------------|
| `Amount` | `$amount` | `$amount` | `$amount` |
| `AmountCurrency` | "THB" (static) | "THB" (static) | "THB" (static) |
| `AttributesList/AttributeName` | **"Carry over status"** | "Activity code" | "Activity code" |
| `AttributesList/Value` | **"N"** | "45" | "45" |
| `BaId` | $accountId | $accountId | $accountId |
| `BusinessEntity` | "0" | "0" | "0" |
| `ChargeCode` | $subOff/OfferName | $subOff/OfferName | $subOff/OfferName |
| `ChargeOrigin` | **"ML"** | — absent | — absent |
| `ChargeType` | **if(amount>0)"DBT" else "CRD"** | — absent | — absent |
| `Description` | $description | $description | — absent |
| `EffectiveDate` | $subOff/EffectiveDate | $subOff/EffectiveDate | $subOff/EffectiveDate |
| `Pcn` | $accountId | $accountId | $accountId |
| `ReciverCustomerId` | Customer/CustomerId | Customer/CustomerId | Customer/CustomerId |
| `ServiceReciverId` | $sub/SubscriberId | $sub/SubscriberId | $sub/SubscriberId |
| `ServiceReciverType` | "83" | "83" | "83" |

### §9.2 Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority            ← $orderRequest/OrderPriority           [Conditional: if OrderPriority]
    ├── JMSCorrelationID       ← $orderRequest/OrderData/OMXTrackingId [Conditional: if OMXTrackingId]
    ├── OrderID                ← $orderRequest/OrderData/OrderID       [Conditional: if OrderID]
    ├── RefID                  ← $subsId (= sub.RefId)                 [Always]
    ├── UserName               ← $orderRequest/OrderData/User          [Conditional: if User]
    ├── PassWord               ← $orderRequest/OrderData/Password      [Conditional: if Password]
    ├── OrderType              ← $orderRequest/OrderData/OrderType     [Conditional: if OrderType]
    ├── CES                    ← $orderRequest/OrderData/CES           [Conditional: if CES]
    └── payload
        └── ns:CreateChargeRequest
            └── ns:ChargeInfo
                ├── ns1:Amount              ← $amount                   [Always]
                ├── ns1:AmountCurrency      ← "THB"                     [Always - static]
                ├── ns1:AttributesList
                │   ├── ns2:AttributeName   ← "Carry over status" (UC) / "Activity code" (std)  [Always]
                │   └── ns2:Value           ← "N" (UC) / "45" (std)    [Always]
                ├── ns1:BaId               ← Customer.Account[1].AccountID  [Conditional: if accountId]
                ├── ns1:BusinessEntity      ← "0"                       [Always - static]
                ├── ns1:ChargeCode         ← $subOff/OfferName          [Conditional: if OfferName]
                ├── ns1:ChargeOrigin       ← "ML"                       [UC path only]
                ├── ns1:ChargeType         ← if($amount>0)"DBT" else "CRD"  [UC path only]
                ├── ns1:Description        ← $description               [Conditional: POU only; COU omits]
                ├── ns1:EffectiveDate      ← $subOff/EffectiveDate      [Conditional: if EffectiveDate]
                ├── ns1:Pcn               ← $accountId                  [Conditional: if accountId]
                ├── ns1:ReciverCustomerId  ← Customer/CustomerId        [Conditional: if CustomerId]
                ├── ns1:ServiceReciverId   ← $sub/SubscriberId          [Conditional: if SubscriberId]
                └── ns1:ServiceReciverType ← "83"                       [Always - static]
```

### §9.3 Complete Generated XML Example (UC path)

```xml
<ns:CreateChargeRequest>
  <ns:ChargeInfo>
    <ns1:Amount>150.00</ns1:Amount>
    <ns1:AmountCurrency>THB</ns1:AmountCurrency>
    <ns1:AttributesList>
      <ns2:AttributeName>Carry over status</ns2:AttributeName>
      <ns2:Value>N</ns2:Value>
    </ns1:AttributesList>
    <ns1:BaId>100012345</ns1:BaId>
    <ns1:BusinessEntity>0</ns1:BusinessEntity>
    <ns1:ChargeCode>DATA_PACK_SOC</ns1:ChargeCode>
    <ns1:ChargeOrigin>ML</ns1:ChargeOrigin>
    <ns1:ChargeType>DBT</ns1:ChargeType>
    <ns1:Description>Data Pack Monthly Fee</ns1:Description>
    <ns1:EffectiveDate>2026-08-03T00:00:00</ns1:EffectiveDate>
    <ns1:Pcn>100012345</ns1:Pcn>
    <ns1:ReciverCustomerId>CUST-99887766</ns1:ReciverCustomerId>
    <ns1:ServiceReciverId>0812345678</ns1:ServiceReciverId>
    <ns1:ServiceReciverType>83</ns1:ServiceReciverType>
  </ns:ChargeInfo>
</ns:CreateChargeRequest>
```

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` |
| PROCESS_ID | `concat(pid, "_REQ")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `"BL_CREATE_CHARGE"` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `"Request Sent for BL_CREATE_CHARGE"` |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | Gated: `WritePayload == "true"` |

One audit log per dispatched charge offer.

---

## §12 Activity Status Management

| Condition | Status Call | Result |
|-----------|------------|--------|
| At least one charge dispatched | `GetActivityStatusString("1", false)` | Activity in-flight |
| No dispatchable offers | `SkipActivity("4")` | Activity skipped |
| Exception | `HandleActivityException(...)` | Error state |

---

## §13 Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

Entire THEN body is wrapped in a single try/catch. All exceptions route to `HandleActivityException` with empty context string.

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears leftover queue entries on resubmit |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, subsId, offerName, filter)` | POU PreExecCheck XML builder |
| `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, subsId, offerName, pOuRefId, filter)` | COU PreExecCheck XML builder |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Enqueues charge event for throttled dispatch |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Fires first queued event |
| `GetActivityStatusString("1", false)` | Returns in-flight status string |
| `SendDataToDB(orderRequest)` | Persists order state to DB |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | Advances process when no charges needed |
| `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | Standard error handler |

---

## §15 Function Dependency Tree

```text
Request_BL_CREATE_CHARGE
├── [resubmit guard]
│   └── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()
├── [POU loop - per offer]
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo()
│   ├── XPath.execute()  ← PreExecCheck
│   ├── XPath.evalAsDouble()  ← AMOUNT
│   ├── XPath.evalAsString()  ← DESCRIPTION
│   ├── XPath.evalAsString()  ← REVENUE_CODE
│   ├── Event.createEvent()  ← BL_CREATE_CHARGE XSLT (UC or std variant)
│   ├── Event.assertEvent()
│   ├── IntraActivitySequencing.ActionRequestEvent()
│   └── Event.Ext.sendEventImmediate()  ← Logger
├── [COU loop - per offer, excl ServiceType=80]
│   ├── GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo()
│   ├── XPath.execute()  ← PreExecCheck
│   ├── XPath.evalAsDouble()  ← AMOUNT (sub first)
│   ├── Event.createEvent()  ← BL_CREATE_CHARGE XSLT (COU variant)
│   ├── Event.assertEvent()
│   ├── IntraActivitySequencing.ActionRequestEvent()
│   └── Event.Ext.sendEventImmediate()  ← Logger
├── [after loops - dispatched]
│   ├── IntraActivitySequencing.SendFirstRequestEvent()
│   ├── GetActivityStatusString("1", false)
│   └── SendDataToDB()
├── [after loops - nothing dispatched]
│   └── SkipActivity("4")
└── [catch]
    └── HandleActivityException()
```

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | Iterate POU and COU subscriber offers; dispatch CreateCharge for each with non-zero AMOUNT |
| R2 | Route to UC billing path (ChargeOrigin="ML", ChargeType=DBT/CRD) when REVENUE_CODE="UC" (POU only) |
| R3 | Route to standard billing path (Activity code=45) when REVENUE_CODE ≠ "UC" and amount > 0 |
| R4 | Exclude COU offers with ServiceType="80" from charge dispatch |
| R5 | Use `sub.RefId + ":" + offer.OfferName` as the correlation RefID |
| R6 | Throttle sequential dispatch via IntraActivitySequencing (not parallel fan-out) |
| R7 | Skip entire activity (SkipActivity "4") when no dispatchable offers found |
| R8 | Support resubmit by purging old pending requests before re-dispatching |
| R9 | Capture ChargeId from BL3G response in currActivity.Response[] |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Amount lookup order differs POU vs COU — asymmetric when AMOUNT exists on both sub and offer levels | [MEDIUM] | Standardize to offer-level priority; test with both-level assignments |
| UC branch dispatches even when amount ≤ 0 (credit); standard branch skips amount = 0 — asymmetric | [LOW] | Confirm intentional: UC creates CRD (credit) entries; document with billing team |
| ChargeId returned from BL3G not written to OrderRequest — lost for downstream tracing | [LOW] | In migration, persist ChargeId as ExtendedInfo on offer or order |
| REVENUE_CODE="UC" unavailable for COU subscribers — hard-coded structural gap | [MEDIUM] | Verify: is "UC" revenue code only possible on POU subscribers? Document constraint. |
| No ResponseCode success check in response handler — any response advances the queue | [HIGH] | Migration should add explicit ResponseCode validation and failure routing |
| LogicalDate loaded but not used — dead code | [LOW] | Remove in migration |

---

## §18 Full Source Code

```java
/**
 * @description
 * @author RS33-BANDIT
 */
rule Rules.OMConsumers.OMXFM.Request.Request_BL_CREATE_CHARGE {
  attribute {
    priority = 5;
    forwardChain = true;
  }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "BL_CREATE_CHARGE";
    orderRequest.ProcessFlow.NextActivityID == "BL_CREATE_CHARGE";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      // LogicalDate loaded but not used in payload (vestigial)
      Concepts.OM.LogicalDate logicalDateRes = Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate");
      Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");

      if(isActResub) {
        RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      }

      boolean isSkipped = true;
      /* ── POU Subscriber loop ── */
      for(int i = 0; i < orderRequest.OrderData.Customer.ParentOU@length; i++) {
        for(int p = 0; p < ...ParentOU[i].Subscriber@length; p++) {
          Subscriber sub = ...ParentOU[i].Subscriber[p];
          for(int q = 0; q < sub.SubscriberOffers@length; q++) {
            SubscriberOffers subOff = ...Subscriber[p].SubscriberOffers[q];
            String refId = sub.RefId + ":" + subOff.OfferName;
            String filter = XPath.evalAsString("$subOff/ExtendedInfo[Name=\"FE_OR_CCBS\"]/Value");
            // reqSuccess check against Response[] ...
            if(!reqSuccess) {
              // PreExecCheck gate ...
              double amount = XPath.evalAsDouble(/* subOff/AMOUNT → sub/AMOUNT → 0 */);
              String description = XPath.evalAsString(/* subOff/DESCRIPTION → sub → "" */);
              String revenueCode = XPath.evalAsString(/* subOff/REVENUE_CODE → "" */);

              if(revenueCode == "UC") {
                // UC path: ChargeOrigin="ML", ChargeType=DBT/CRD, Carry over status="N"
                // → See §9 for full XSLT (UC variant)
                Event createChargeEvent = Event.createEvent(/* UC XSLT */);
                Event.assertEvent(createChargeEvent);
                IntraActivitySequencing.ActionRequestEvent(createChargeEvent, orderCurrentActivity);
                Event.Ext.sendEventImmediate(/* Logger audit */);
                isSkipped = false;
              } else if(amount > 0) {
                // Standard path: Activity code="45"
                // → See §9 for full XSLT (standard POU variant)
                Event createChargeEvent = Event.createEvent(/* Std XSLT */);
                Event.assertEvent(createChargeEvent);
                IntraActivitySequencing.ActionRequestEvent(createChargeEvent, orderCurrentActivity);
                Event.Ext.sendEventImmediate(/* Logger audit */);
                isSkipped = false;
              }
            }
          }
        }
        /* ── COU loop (excl ServiceType="80", amount>0, no UC branch) ── */
        // → See §9 for full XSLT (COU variant)
        // isSkipped = false when dispatched
      }

      if(!isSkipped) {
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
        RuleFunctions.Helpers.SendDataToDB(orderRequest);
      } else {
        RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
      }
    } catch (Exception ae) {
      RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 Response Message Rule — Response_BL_CREATE_CHARGE

### §19.1 Overview

Lean response rulefunction: constructs a `BL_CreateChargeRes` concept from the incoming FM response, appends it to `currActivity.Response[]`, emits a response audit log, and calls `ActionResponseEvent` to advance the IntraActivitySequencing queue.

> Unlike SBM_BUY_DATA_PACK, this response handler has **no fan-in success counting** — it relies entirely on `IntraActivitySequencing.ActionResponseEvent()` to determine when all charges are complete.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order — needed for audit logging |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.BL_CREATE_CHARGE` | Inbound FM response (ResponseCode, RefID, ChargeId) |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — Response[] appended to |

### §19.3 ResponseBase Concept Construction — BL_CreateChargeRes

```text
createObject
└── object  extId ← OMXUtils.generateTrackingID()  [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode    [Conditional: if ResponseCode]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg     [Conditional: if ResponseMsg]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus [Conditional: if CompletionStatus]
    ├── ReferenceId       ← $eventResponse/RefID           [Conditional: if RefID]
    └── ChargeId          ← $eventResponse/payload/ns1:CreateChargeResponse/ns1:ChargeIdInfo/ns:ChargeId
                                                           [Conditional: if path exists]
```

The `ChargeId` returned from Amdocs BL3G is captured but not written back to the OrderRequest — available for audit only in Response[].

### §19.4 Response Completion Logic

| Return value | Meaning |
|-------------|---------|
| `"true"` | All charges complete (IntraActivitySequencing queue exhausted) — activity done |
| `"false"` | More charges pending — wait for further responses |

No explicit ResponseCode success check — any response (including errors) advances the queue.

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(pid, "_RES")` |
| OPERATION_NAME | `"BL_CREATE_CHARGE"` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `"Response received for BL_CREATE_CHARGE"` |
| payload | Gated on `WritePayload == "true"`; contains full `$eventResponse` copy |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
