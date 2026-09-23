# Request_OMX_EXP_FUT_PP

> Expire Future Price Plan Orders — reads OMX_SEARCH_FUT_PP results, sets status=4 (expired) on matching future orders via single batch OMX_UPDATE_FUTURE.

**Author:** warawich-nb | **Priority:** 5 | **forwardChain:** true | **Pattern:** Prior-activity-consumer + batch update | **Generated:** 2026-08-20

> **[UNIQUE PATTERN]** Unlike most OMXFM rules that query live order state, this rule reads a cached response from the OMX_SEARCH_FUT_PP activity's `Response[0]`. It dispatches *at most one* batch event regardless of how many FutureOrders are present.

---

## §1 — Overview & Purpose

This rule expires future price-plan orders by setting their status to `4`. It is a **downstream consumer** of the OMX_SEARCH_FUT_PP activity — it reads the first search response from a prior activity rather than building its own entity query. The rule then determines whether the order qualifies as a "future price plan" order (`isFuturePriceplan`) and filters the FutureOrders accordingly before dispatching a single batch `OMX_UPDATE_FUTURE` event.

Used in POSTPAID_UPDATE_PARAMETER step 23 — expires existing future PP orders found in step 22 (OMX_SEARCH_FUT_PP) before the new parameter takes effect.

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_EXP_FUT_PP` |
| Event type (outbound) | `Events.OMConsumers.OMXFM.Request.OMX_UPDATE_FUTURE` |
| Event type (inbound response) | `Events.OMConsumers.OMXFM.Response.OMX_UPDATE_FUTURE` |
| Payload schema | `ns:futureOrders/ns:futureOrder` (FutureOrder.xsd) — batch |
| Response concept | `Concepts.FM.Response.OMX_UpdateFutureRes` |
| Source data | Prior activity `OMX_SEARCH_FUT_PP` → `Response[0].FutureOrders[]` |
| Dispatch pattern | Single batch event (at most 1 per execution) |
| status set | `4` (expired) — hardcoded |
| updatedBy | `"OMX"` — hardcoded |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Note |
|-----------|-------|------|
| priority | 5 | Standard FM request priority |
| forwardChain | true | Allows further rule evaluation after execution |
| Rule type | OMXFM Request | Dispatches to backend via JMS; has response rulefunction |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order — provides entity data for isFuturePriceplan check and ProcessFlow.Activities[] for prior-response lookup |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — tracks Status, RequestCount, Response[] |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity position match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_EXP_FUT_PP"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_EXP_FUT_PP"` | Redundant dual binding |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Fires only when awaiting execution |

---

## §5 — Execution Flow

1. **Resubmit check** → set `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. **Activity-level PreExecCheck** → if configured, serialize `orderRequest.OrderData` and evaluate XPath; if result ≠ "true" → skip all dispatch
3. **Lookup prior search result** → traverse `orderRequest.ProcessFlow.Activities[]` to find extId = `processFlow@extId + ":OMX_SEARCH_FUT_PP"`; take `Response[0]` as `future`
4. **Guard** → if `future == null` or `FutureOrders == null` or `FutureOrders@length == 0` → skip
5. **Determine `isFuturePriceplan`** → evaluate 5-condition XPath OR (LargeCustomerIndicator=89 or any OfferActivityDate=FUT in any offer scope)
6. **Build `OMX_UPDATE_FUTURE` event** → XSLT filters FutureOrders by futureType; sets `status=4, updatedBy='OMX'`
7. **Non-empty guard** → `count(payload/ns:futureOrders/ns:futureOrder) > 0`; only dispatch if at least one order survives filtering
8. **Dispatch** → send single `OMX_UPDATE_FUTURE` event; send audit log; increment RequestCount (if not resub)
9. **Post-dispatch** → if skipped → `SkipActivity("4")`; else → set INPROGRESS + `SendDataToDB()`
10. **Exception handling** → catch all → `HandleActivityException()`

---

## §6 — Rule Action (THEN) — Detailed Logic

### Phase 1 — Prior Activity Response Lookup

> **[MEDIUM]** Only `Response[0]` is used. If OMX_SEARCH_FUT_PP dispatched multiple requests (Subscriber + POU + COU), each produces a separate response appended to `Response[]`. Only the first response's FutureOrders are processed — orders found in the other responses are silently ignored.

```java
String reqActivityExtID = orderRequest.ProcessFlow@extId + ":OMX_SEARCH_FUT_PP";
Concepts.FM.Response.OMX_SearchFutureRes future = null;
for (int i=0; i < orderRequest.ProcessFlow.Activities@length; i++) {
    if (String.equals(orderRequest.ProcessFlow.Activities[i]@extId, reqActivityExtID)) {
        future = orderRequest.ProcessFlow.Activities[i].Response[0]; // [MEDIUM: only [0]]
        break;
    }
}
```

### Phase 2 — isFuturePriceplan Determination

Five OR-joined XPath conditions — true if *any* of the following:

| # | Condition | Description |
|---|-----------|-------------|
| 1 | `CustomerGeneralInfo/LargeCustomerIndicator='89'` | Large customer code 89 |
| 2 | `ParentOU/Agreement/Offers/ExtendedInfo[Name='OfferActivityDate']/Value='FUT'` | POU Agreement offer has FUT activity date |
| 3 | `ParentOU/Subscriber/SubscriberOffers/ExtendedInfo[Name='OfferActivityDate']/Value='FUT'` | POU Subscriber offer has FUT activity date |
| 4 | `ParentOU/ChildOU/Agreement/Offers/ExtendedInfo[Name='OfferActivityDate']/Value='FUT'` | COU Agreement offer has FUT activity date |
| 5 | `ParentOU/ChildOU/Subscriber/SubscriberOffers/ExtendedInfo[Name='OfferActivityDate']/Value='FUT'` | COU Subscriber offer has FUT activity date |

### Phase 3 — XSLT FutureOrder Filtering

| isFuturePriceplan | futureType filter | status set | updatedBy |
|-------------------|-------------------|-----------|-----------|
| `true` | `futureType='FUTPP'` only | 4 | "OMX" |
| `false` | `futureType='FUTPP' OR 'PROV' OR 'NXTPP'` | 4 | "OMX" |

### Phase 4 — Non-Empty Guard Before Dispatch

```xpath
count($reqEvent/payload/xsd2:futureOrders/xsd2:futureOrder) > 0
```

If filtering removed all FutureOrders → no dispatch → `isSkipped=true` → SkipActivity.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

| Parameter | Value | Source |
|-----------|-------|--------|
| status | `4` (expired) | Hardcoded in XSLT |
| updatedBy | `"OMX"` | Hardcoded in XSLT |
| Prior activity data | `OMX_SEARCH_FUT_PP → Response[0].FutureOrders[]` | ProcessFlow.Activities[] traversal |
| ProcessConfig usage | Step 23 — POSTPAID_UPDATE_PARAMETER | ProcessConfig XML |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_UPDATE_FUTURE` | Batch expire future price-plan orders (set status=4) |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.OMX_UPDATE_FUTURE` | FM update confirmation |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | Audit logging |

### §8.3 — Backend API Details

| System | Operation | Schema | Protocol |
|--------|-----------|--------|----------|
| OMX FM | OMX_UPDATE_FUTURE | `ns:futureOrders/ns:futureOrder` (FutureOrder.xsd) | JMS / TIBCO EMS |

### §8.4 — BE Working Memory Dependencies

| Concept | Access | Fields Used |
|---------|--------|-------------|
| `OrderRequest` | Read | ProcessFlow.Activities[] (prior response), OrderData.Customer.{CustomerGeneralInfo.LargeCustomerIndicator, all OfferActivityDate ExtendedInfo} |
| `Activity` | Read/Write | Status, RequestCount, Response[] |
| `OMX_SearchFutureRes` | Read (prior activity) | FutureOrders[]{FutureOrderId, OrderType, NodeLevel, NodeId, UpdatedDate, futureType} |

### §8.5 — ExtendedInfo Fields Required

| Key | Required/Optional | Scope | Purpose |
|-----|-------------------|-------|---------|
| `OfferActivityDate` | Optional | All offer types (Agreement + Subscriber, POU + COU) | Determines isFuturePriceplan flag; Value='FUT' = future-dated offer |

### §8.6 — Global Variable Dependencies

| Path | Used For |
|------|----------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Gates payload in audit log |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| Parameter | Source |
|-----------|--------|
| `orderRequest` | Working memory |
| `isFuturePriceplan` | boolean result of 5-condition XPath OR |
| `future` | `ProcessFlow.Activities[OMX_SEARCH_FUT_PP].Response[0]` — OMX_SearchFutureRes concept |

### §9.7 — Complete Generated XML Example

```xml
<!-- When isFuturePriceplan=false (broader filter: FUTPP + PROV + NXTPP) -->
<ns:futureOrders xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd">
  <ns:futureOrder>
    <ns:futureOrderId>FO-001</ns:futureOrderId>   <!-- conditional -->
    <ns:status>4</ns:status>                       <!-- hardcoded: expired -->
    <ns:orderType>2</ns:orderType>                 <!-- from search result -->
    <ns:nodeLevel>5</ns:nodeLevel>                 <!-- from search result -->
    <ns:nodeId>12345</ns:nodeId>                   <!-- from search result -->
    <ns:updatedDate>2026-08-20</ns:updatedDate>    <!-- conditional -->
    <ns:updatedBy>OMX</ns:updatedBy>               <!-- hardcoded -->
  </ns:futureOrder>
  <!-- additional ns:futureOrder entries for each matching FutureOrder -->
</ns:futureOrders>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority      ← $orderRequest/OrderPriority                [Conditional]
    ├── JMSCorrelationID ← $orderRequest/OrderData/OMXTrackingId      [Conditional]
    ├── OrderID          ← $orderRequest/OrderData/OrderID            [Conditional]
    ├── UserName / PassWord / OrderType                               [Conditional each]
    └── payload                                                        [Always]
        └── ns:futureOrders                                            [Always]
            └── ns:futureOrder [xsl:for-each $future/FutureOrders where futureType matches isFuturePriceplan filter]
                ├── ns:futureOrderId  ← FutureOrderId (from search result)  [Conditional]
                ├── ns:status         ← 4 (expired)                         [Always, static]
                ├── ns:orderType      ← OrderType (from search result)       [Conditional]
                ├── ns:nodeLevel      ← NodeLevel (from search result)       [Conditional]
                ├── ns:nodeId         ← NodeId (from search result)          [Conditional]
                ├── ns:updatedDate    ← UpdatedDate (from search result)     [Conditional]
                └── ns:updatedBy      ← "OMX"                               [Always, static]
```

**Legend:** `← XPath` = dynamic source, `static` = hardcoded literal value, `[Conditional]` = inside xsl:if

---

## §11 — Audit Logging

| Event | OPERATION_NAME | AUDIT_TRACE | Note |
|-------|---------------|------------|------|
| Request | OMX_EXP_FUT_PP | "Request Sent for OMX_EXP_FUT_PP" | OK |
| Response | **OMX_ADD_FUTPP** | **"Response received for OMX_ADD_FUTPP"** | **[HIGH] BUG — copy-paste from OMX_ADD_FUTPP** |

> **[HIGH] Response audit log contains wrong operation name.** The response rulefunction's Logger XSLT has OPERATION_NAME = "OMX_ADD_FUTPP" and AUDIT_TRACE = "Response received for OMX_ADD_FUTPP" — copied from OMX_ADD_FUTPP rulefunction. All OMX_EXP_FUT_PP response events are logged under the wrong operation name, corrupting audit trail correlation.

---

## §12 — Activity Status Management

| Condition | Status | Call |
|-----------|--------|------|
| Event dispatched (non-empty filtered orders) | INPROGRESS | `GetActivityStatusString("1", false)` |
| Nothing dispatched (null/empty FutureOrders, all filtered, or PreExecCheck failed) | SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception caught | ERROR | `HandleActivityException()` |

---

## §13 — Exception / Error Handling

All logic wrapped in `try { ... } catch (Exception ae)` → `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Instance.serializeUsingDefaults(orderRequest.OrderData)` | Activity-level PreExecCheck evaluation document |
| `GetActivityStatusString("1", false)` | Returns INPROGRESS status string |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | Marks activity skipped |
| `SendDataToDB(orderRequest)` | Persists order state |
| `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | Records exception, sets ERROR state |

---

## §15 — Function Dependency Tree

```text
Request_OMX_EXP_FUT_PP.rule
├── Instance.getByExtIdByUri(NextActivityName, ...)         [PreExecCheck load]
├── Instance.serializeUsingDefaults(orderRequest.OrderData)  [PreExecCheck eval]
├── XPath.execute("/(PreExecCheck)", sXML, ...)
├── Loop: orderRequest.ProcessFlow.Activities[]             [find OMX_SEARCH_FUT_PP]
│   └── → future = Activities[i].Response[0]               [OMX_SearchFutureRes]
├── XPath.evalAsBoolean(5-condition isFuturePriceplan OR)
├── Event.createEvent("xslt://{{.../OMX_UPDATE_FUTURE}}")
│   └── XSLT: filters FutureOrders by futureType, sets status=4, updatedBy=OMX
├── XPath.evalAsBoolean(count(payload/futureOrders/futureOrder) > 0)
├── Event.Ext.sendEventImmediate() → OMX_UPDATE_FUTURE      [if non-empty]
├── Event.Ext.sendEventImmediate() → Logger                 [if dispatched]
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB()
├── RuleFunctions.Helpers.SkipActivity()
└── RuleFunctions.Helpers.HandleActivityException()

Response_OMX_EXP_FUT_PP.rulefunction
├── Log.getLogger("RuleFunctions.OrderResponse.Response_OMX_EXP_FUT_PP")
├── Log.log(logger,"debug","Executing %s", ...)
├── Instance.createInstance("xslt://{{/Concepts/FM/Response/OMX_UpdateFutureRes}}")
│   ├── Maps: ResponseCode
│   ├── Maps: ResponseMessage  (← ResponseMsg)
│   ├── Maps: CompletionStatus
│   └── [NOT mapped: ReferenceId]
├── Event.Ext.sendEventImmediate() → Logger
│   └── [BUG: OPERATION_NAME="OMX_ADD_FUTPP", AUDIT_TRACE="Response received for OMX_ADD_FUTPP"]
├── Log.log(logger,"debug","Executing %s", ...)    [BUG: says Executing, should say Completed]
└── return "true"                                   [always — unconditional]
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Expire (set status=4) future price-plan orders discovered by the preceding OMX_SEARCH_FUT_PP activity |
| R2 | If `isFuturePriceplan=true`: expire only `futureType='FUTPP'`; otherwise also include `'PROV'` and `'NXTPP'` |
| R3 | Only dispatch if at least one order survives the futureType filter |
| R4 | Batch all matching expiry orders into a single OMX_UPDATE_FUTURE event |
| R5 | Response RF always returns "true" (single request, no fan-in needed) |

### Design Risks

| Risk | Severity | Detail | Mitigation |
|------|----------|--------|-----------|
| Response OPERATION_NAME / AUDIT_TRACE wrong (copy-paste) | [HIGH] | Response rulefunction Logger uses OPERATION_NAME="OMX_ADD_FUTPP" and AUDIT_TRACE="Response received for OMX_ADD_FUTPP". Audit trail correlation is corrupted. | Fix to OPERATION_NAME="OMX_EXP_FUT_PP" and AUDIT_TRACE="Response received for OMX_EXP_FUT_PP" |
| Only Response[0] used — other entity responses ignored | [MEDIUM] | OMX_SEARCH_FUT_PP may return 1–3 responses (Subscriber, POU, COU). Only Response[0] is used. FutureOrders from other responses are not expired. | Loop over all Response[] entries from OMX_SEARCH_FUT_PP |
| Response RF always returns "true" — no error handling | [MEDIUM] | `return "true"` is unconditional. A failed update (non-"000" ResponseCode) still advances the process. | Add ResponseCode suffix check before returning "true" |
| Response debug log says "Executing" twice | [LOW] | Line 24 of the response RF: `Log.log(logger,"debug","Executing %s", ...)` — should say "Completed". | Change to "Completed %s" |
| Implicit dependency on OMX_SEARCH_FUT_PP activity ordering | [MEDIUM] | Assumes OMX_SEARCH_FUT_PP always precedes it and follows the extId pattern `processFlow@extId + ":OMX_SEARCH_FUT_PP"`. Any rename/reorder breaks lookup silently. | Pass prior activity result as a Parameter reference rather than hard-coding the extId lookup pattern |

---

## §18 — Full Source Code

```java
/**
 * @author warawich-nb
 */
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_EXP_FUT_PP {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "OMX_EXP_FUT_PP";
        orderRequest.ProcessFlow.NextActivityID == "OMX_EXP_FUT_PP";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
            String chkRes = "true";
            if(String.length(nextAct.PreExecCheck) > 0) {
                String sXML = Instance.serializeUsingDefaults(orderRequest.OrderData);
                chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
            }
            boolean isSkipped = true;

            if(String.equals(chkRes,"true")) {
                // ── Phase 1: Lookup OMX_SEARCH_FUT_PP Response[0] ──────────────────
                String reqActivityExtID = orderRequest.ProcessFlow@extId + ":OMX_SEARCH_FUT_PP";
                Concepts.FM.Response.OMX_SearchFutureRes future = null;
                for (int i=0; i < orderRequest.ProcessFlow.Activities@length; i++) {
                    if (String.equals(orderRequest.ProcessFlow.Activities[i]@extId, reqActivityExtID)) {
                        future = orderRequest.ProcessFlow.Activities[i].Response[0]; // [MEDIUM: only [0]]
                        break;
                    }
                }

                if(future != null && future.FutureOrders != null && future.FutureOrders@length > 0) {
                    // ── Phase 2: Determine isFuturePriceplan ───────────────────────────
                    boolean isFuturePriceplan = XPath.evalAsBoolean(
                        "boolean(LargeCustomerIndicator='89') OR"
                        + "boolean(POU/Agreement/Offers/ExtendedInfo[Name='OfferActivityDate']/Value='FUT') OR"
                        + "boolean(POU/Subscriber/SubscriberOffers/ExtendedInfo[Name='OfferActivityDate']/Value='FUT') OR"
                        + "boolean(COU/Agreement/Offers/ExtendedInfo[Name='OfferActivityDate']/Value='FUT') OR"
                        + "boolean(COU/Subscriber/SubscriberOffers/ExtendedInfo[Name='OfferActivityDate']/Value='FUT')");

                    // ── Phase 3: Build batch OMX_UPDATE_FUTURE (see §9 for full XSLT field mapping) ──
                    // XSLT filters FutureOrders by futureType (FUTPP only if isFuturePriceplan=true;
                    // FUTPP+PROV+NXTPP if false); sets status=4 and updatedBy='OMX' for each.
                    Events.OMConsumers.OMXFM.Request.OMX_UPDATE_FUTURE reqEvent = Event.createEvent("xslt://{{...}}");

                    // ── Phase 4: Non-empty guard ───────────────────────────────────────
                    if (XPath.evalAsBoolean("count($reqEvent/payload/xsd2:futureOrders/xsd2:futureOrder) > 0")){
                        Event.Ext.sendEventImmediate(reqEvent);
                        Event.Ext.sendEventImmediate(/* Logger: "Request Sent for OMX_EXP_FUT_PP" */);
                        isSkipped = false;
                        if(!isActResub) orderCurrentActivity.RequestCount++;
                    }
                }
            }

            if(isSkipped){
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            } else {
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
            }
        } catch (Exception ae){
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_OMX_EXP_FUT_PP.rulefunction` — receives the OMX FM update confirmation, creates an `OMX_UpdateFutureRes` concept, appends it to the activity's Response array, sends an audit log (with incorrect operation name — see §19.5), and unconditionally returns "true".

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order for audit logging |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_UPDATE_FUTURE` | Inbound FM update confirmation |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] array target |

### §19.3 — ResponseBase Concept Construction (OMX_UpdateFutureRes)

```text
createObject
└── object
    ├── ResponseCode        ← $eventResponse/ResponseCode     [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg      [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId         ← (not mapped — extId also not generated)  [Note]
```

### §19.4 — Response Completion Logic

> **Unconditional `return "true"`** — the rulefunction always advances the activity regardless of ResponseCode. A failed update (e.g., FM returns error) will not block the process.

| Condition | Return |
|-----------|--------|
| Always | `"true"` — unconditional |

### §19.5 — Response Audit Logging

> **[HIGH] Wrong operation name:** OPERATION_NAME = `"OMX_ADD_FUTPP"` and AUDIT_TRACE = `"Response received for OMX_ADD_FUTPP"` — copied from a different rulefunction. Should be "OMX_EXP_FUT_PP".

| Field | Actual Value | Expected Value |
|-------|-------------|---------------|
| PROCESS_ID | `concat($pid, "_RES")` | OK |
| OPERATION_NAME | **"OMX_ADD_FUTPP"** | "OMX_EXP_FUT_PP" |
| AUDIT_TRACE | **"Response received for OMX_ADD_FUTPP"** | "Response received for OMX_EXP_FUT_PP" |
| payload | Conditional on WritePayload="true" | OK |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
