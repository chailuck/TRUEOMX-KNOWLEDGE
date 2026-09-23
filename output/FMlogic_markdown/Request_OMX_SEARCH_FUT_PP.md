# Request_OMX_SEARCH_FUT_PP

> Search Future Price Plan Orders — targeted 3-scope fan-out gated on ServiceType=80 (price plan)

**Author:** warawich-nb | **Priority:** 5 | **forwardChain:** true | **Type:** OMXFM Request  
**Backend:** OMX FM (OMX_SEARCH_FUTURE) | **ServiceType gate:** 80 | **Generated:** 2026-08-20

---

## §1 — Overview & Purpose

This rule searches the FM system for existing future orders related to price plans (`ServiceType=80`). It dispatches up to three `OMX_SEARCH_FUTURE` JMS events — one each for the first qualifying Subscriber, the first qualifying POU Agreement, and the first qualifying COU Agreement — each only if that entity has an offer with `ServiceType=80`. An activity-level PreExecCheck is evaluated first against the full `OrderData`; if it fails, nothing is dispatched. The `orderType` parameter is read from `Parameter[1]`, defaulting to `2` if empty.

> **Context:** Used in POSTPAID_UPDATE_PARAMETER step 22 to discover existing future price-plan orders before expiry/update operations proceed.

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_SEARCH_FUT_PP` |
| Event type (outbound) | `Events.OMConsumers.OMXFM.Request.OMX_SEARCH_FUTURE` |
| Event type (inbound) | `Events.OMConsumers.OMXFM.Response.OMX_SEARCH_FUTURE` |
| Payload schema | `ns:futureOrder` (FutureOrder.xsd) |
| Response concept | `Concepts.FM.Response.OMX_SearchFutureRes` |
| Dispatch pattern | Parallel fan-out (`sendEventImmediate`) — up to 3 events |
| ServiceType gate | `ServiceType=80` (price plan) per scope |
| Entity selection | First qualifying entity per scope type (not all entities) |
| orderType source | `Parameter[1]`; default `2` if empty |
| status | `1` (hardcoded — active/pending) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Note |
|-----------|-------|------|
| priority | 5 | Standard FM request priority |
| forwardChain | true | Allows further rule evaluation after execution |
| Rule type | OMXFM Request | Dispatches to backend via JMS; has corresponding response rulefunction |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order — provides entity hierarchy and order metadata |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Provides `Parameter[1]` (orderType); tracks Status, RequestCount, Response[] |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to current process position |
| 2 | `orderCurrentActivity.ActivityID == "OMX_SEARCH_FUT_PP"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_SEARCH_FUT_PP"` | Redundant dual binding |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Fires only when awaiting execution |

---

## §5 — Execution Flow

1. **Resubmit check** → set `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. **Load LogicalDate** → read from working memory (held, not passed in payload)
3. **Activity-level PreExecCheck** → serialize full `orderRequest.OrderData`; evaluate XPath; if result ≠ "true" → skip all dispatch
4. **Read orderType** → `XPath.evalAsString($orderCurrentActivity/Parameter[1])`; used in payload (default 2 if empty)
5. **Scope A — Subscriber** → resolve first subscriber (POU[1]/Sub[1] or COU[1]/Sub[1]); check `ServiceType=80`; dispatch `OMX_SEARCH_FUTURE` (nodeLevel=5); send audit log
6. **Scope B — POU** → first POU with OUId; check `Agreement.Offers/ServiceType=80`; dispatch (nodeLevel=3); send audit log
7. **Scope C — COU** → first COU of POU[1] with OUId; check `Agreement.Offers/ServiceType=80`; dispatch (nodeLevel=3); send audit log
8. **Post-dispatch** → if `isSkipped=true` → `SkipActivity("4")`; else → INPROGRESS + `SendDataToDB()`
9. **Exception handling** → catch all → `HandleActivityException()`

---

## §6 — Rule Action (THEN) — Detailed Logic

### Activity-Level PreExecCheck

> Unlike FMs that apply PreExecCheck per offer, this rule applies it once at the activity level using serialized `OrderData`.

```java
if(String.length(nextAct.PreExecCheck) > 0) {
    String sXML = Instance.serializeUsingDefaults(orderRequest.OrderData);
    chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
}
```

> **Note:** Evaluation document is `orderRequest.OrderData` (not the full `orderRequest`). PreExecCheck XPath must reference only OrderData fields.

### Scope A — Subscriber (nodeLevel=5)

- Subject: `tib:if-absent($orderRequest/OrderData/Customer/ParentOU[1]/Subscriber[1]/@extId, ParentOU[1]/ChildOU[1]/Subscriber[1]/@extId)`
- If `subExtId == null` → scope skipped
- Gate: `$subscriber/SubscriberOffers/ServiceType=80`
- `nodeId = number($subscriber/SubscriberId)`; `RefID = $subscriber/RefId`
- No resubmit guard — request always re-sent (only `RequestCount` not incremented on resub)

### Scope B — POU Agreement (nodeLevel=3)

- Subject: `ParentOU[OUId/text()][1]/@extId` — first POU with non-empty OUId
- Gate: `$pOu/Agreement/Offers/ServiceType=80`
- `nodeId = number($pOu/OUId)`; `RefID = $pOu/RefId`

### Scope C — COU Agreement (nodeLevel=3)

- Subject: `ParentOU[1]/ChildOU[OUId/text()][1]/@extId` — first COU of POU[1] with non-empty OUId
- Gate: `$cOu/Agreement/Offers/ServiceType=80`
- `nodeId = number($cOu/OUId)`; `RefID = $cOu/RefId`

### orderType Resolution

| Source | Value | Condition |
|--------|-------|-----------|
| `$orderCurrentActivity/Parameter[1]` | As configured in ProcessConfig | `string-length($orderType) > 0` |
| Hardcoded default | `2` | `xsl:otherwise` — Parameter[1] empty |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

| Parameter | Value | Source |
|-----------|-------|--------|
| status | `1` (active/pending) | Hardcoded |
| orderType | From `Parameter[1]` or default `2` | ProcessConfig activity parameter |
| ProcessConfig usage | Step 22 — POSTPAID_UPDATE_PARAMETER | ProcessConfig XML |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_SEARCH_FUTURE` | Search future price-plan orders |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.OMX_SEARCH_FUTURE` | FM response with FutureOrders array |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | Audit logging |

### §8.3 — Backend API Details

| System | Operation | Schema | Protocol |
|--------|-----------|--------|----------|
| OMX FM | OMX_SEARCH_FUTURE | `ns:futureOrder` (FutureOrder.xsd) | JMS / TIBCO EMS |

### §8.4 — BE Working Memory Dependencies

| Concept | Access | Fields Used |
|---------|--------|------------|
| `OrderRequest` | Read | OrderData.Customer.{ParentOU,ChildOU,Subscriber,Agreement,Offers}, OMXTrackingId, OrderID |
| `Activity` | Read/Write | Parameter[1] (orderType), Status, RequestCount, Response[] |
| `LogicalDate` | Read | LogicalDate string (loaded but not used in payload) |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding (3 scope variants)

| Parameter | Scope A (Subscriber) | Scope B (POU) | Scope C (COU) |
|-----------|--------------------|---------------|---------------|
| entity param | `subscriber` | `pOu` | `cOu` |
| RefID source | `$subscriber/RefId` | `$pOu/RefId` | `$cOu/RefId` |
| nodeLevel | 5 | 3 | 3 |
| nodeId | `number($subscriber/SubscriberId)` | `number($pOu/OUId)` | `number($cOu/OUId)` |

### §9.7 — Complete Generated XML Example (Scope A: Subscriber)

```xml
<!-- Event headers -->
<JMSCorrelationID>OMX-TRACKING-001</JMSCorrelationID>  <!-- conditional -->
<OrderID>ORD-20260820-001</OrderID>                      <!-- conditional -->
<RefID>REF-SUB-001</RefID>                               <!-- conditional -->

<!-- Payload -->
<ns:futureOrder xmlns:ns="...FutureOrder.xsd">
  <ns:status>1</ns:status>
  <ns:orderType>5</ns:orderType>   <!-- from Parameter[1], or 2 if empty -->
  <ns:nodeLevel>5</ns:nodeLevel>   <!-- Subscriber -->
  <ns:nodeId>12345</ns:nodeId>     <!-- number(SubscriberId) -->
</ns:futureOrder>
```

---

## §10 — XSLT Field Mapping — Output XML Tree

```text
createEvent
└── event
    ├── JMSPriority           ← $orderRequest/OrderPriority          [Conditional]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId [Conditional]
    ├── OrderID               ← $orderRequest/OrderData/OrderID       [Conditional]
    ├── RefID                 ← entity.RefId                          [Conditional]
    ├── UserName              ← $orderRequest/OrderData/User          [Conditional]
    ├── PassWord              ← $orderRequest/OrderData/Password      [Conditional]
    ├── OrderType             ← $orderRequest/OrderData/OrderType     [Conditional]
    └── payload
        └── ns:futureOrder
            ├── ns:status     ← 1                                      [Always, static]
            ├── ns:orderType  ← Parameter[1] or "2"                   [Always, xsl:choose]
            ├── ns:nodeLevel  ← 5 (Sub) or 3 (POU/COU)               [Always, static]
            └── ns:nodeId     ← number(SubscriberId or OUId)          [Always]
```

---

## §11 — Audit Logging

| Scope | OPERATION_NAME | AUDIT_TRACE |
|-------|----------------|-------------|
| A — Subscriber Request | OMX_SEARCH_FUT_PP | "Request Sent for OMX_SEARCH_FUT_PP" |
| B — POU Request | OMX_SEARCH_FUT_PP | "Request Sent for OMX_SEARCH_FUT_PP" |
| C — COU Request | OMX_SEARCH_FUT_PP | "Request Sent for OMX_SEARCH_FUT_PP" |
| Response | OMX_SEARCH_FUT_PP | "Response received for OMX_SEARCH_FUT_PP" |

> All 3 request scopes use consistent AUDIT_TRACE. WritePayload gate applies.

---

## §12 — Activity Status Management

| Condition | Status | Call |
|-----------|--------|------|
| At least one request dispatched | INPROGRESS | `GetActivityStatusString("1", false)` |
| Nothing dispatched (all skipped) | SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception caught | ERROR | `HandleActivityException()` |

---

## §13 — Exception / Error Handling

All logic wrapped in `try { ... } catch (Exception ae)`. On exception: `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Instance.serializeUsingDefaults(orderRequest.OrderData)` | Serialize OrderData for activity-level PreExecCheck |
| `Instance.getByExtIdByUri(extId, uri)` | Load concept from working memory |
| `XPath.evalAsBoolean($entity/Offers/ServiceType=80)` | ServiceType=80 gate check |
| `GetActivityStatusString("1", false)` | Returns INPROGRESS status |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | Mark activity skipped |
| `SendDataToDB(orderRequest)` | Persist order state |
| `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | Record exception, set ERROR |

---

## §15 — Function Dependency Tree

```text
Request_OMX_SEARCH_FUT_PP.rule
├── Instance.getByExtIdByUri("LogicalDate", ...)
├── Instance.getByExtIdByUri(NextActivityName, ...)    [PreExecCheck]
├── Instance.serializeUsingDefaults(orderRequest.OrderData)
├── XPath.execute("/(PreExecCheck)", sXML, ...)
├── XPath.evalAsString(tib:if-absent(POU[1]/Sub[1]/@extId, COU[1]/Sub[1]/@extId))
├── XPath.evalAsString($orderCurrentActivity/Parameter[1])
├── Scope A: Subscriber
│   ├── Instance.getByExtIdByUri(subExtId, ...)
│   ├── XPath.evalAsBoolean($subscriber/SubscriberOffers/ServiceType=80)
│   ├── Event.Ext.sendEventImmediate() → OMX_SEARCH_FUTURE
│   └── Event.Ext.sendEventImmediate() → Logger
├── Scope B: POU
│   ├── XPath.evalAsString(ParentOU[OUId/text()][1]/@extId)
│   ├── Instance.getByExtIdByUri(pOuExtId, ...)
│   ├── XPath.evalAsBoolean($pOu/Agreement/Offers/ServiceType=80)
│   ├── Event.Ext.sendEventImmediate() → OMX_SEARCH_FUTURE
│   └── Event.Ext.sendEventImmediate() → Logger
├── Scope C: COU
│   ├── XPath.evalAsString(ParentOU[1]/ChildOU[OUId/text()][1]/@extId)
│   ├── Instance.getByExtIdByUri(cOuExtId, ...)
│   ├── XPath.evalAsBoolean($cOu/Agreement/Offers/ServiceType=80)
│   ├── Event.Ext.sendEventImmediate() → OMX_SEARCH_FUTURE
│   └── Event.Ext.sendEventImmediate() → Logger
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB()
├── RuleFunctions.Helpers.SkipActivity()
└── RuleFunctions.Helpers.HandleActivityException()

Response_OMX_SEARCH_FUT_PP.rulefunction
├── Log.getLogger("RuleFunctions.OrderResponse.Response_OMX_SEARCH_FUT_PP")
├── Instance.createInstance("xslt://{{/Concepts/FM/Response/OMX_SearchFutureRes}}")
│   ├── Maps: ResponseCode, ResponseMessage (←ResponseMsg), CompletionStatus, ReferenceId (←RefID)
│   └── FutureOrders[] array ← xsl:for-each payload/ns:futureOrders/ns:futureOrder
│       └── Per entry: FutureOrderId, EffectiveDate, Status, OrderType, NodeLevel, NodeId,
│                      RequestedDate, RequestedBy, UpdatedDate, UpdatedBy, DealerCode,
│                      ActivityReason, ExtendedInfos[], fromOrderId, ToOMXId, UserText,
│                      Remark, futureType
├── Log.log(logger,"trace","resEvent=%s", Instance.serializeUsingDefaults(resEvent))
├── Event.Ext.sendEventImmediate() → Logger (_RES suffix)
└── [NON-STANDARD] if(currActivity.RequestCount == currActivity.Response@length) → "true"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Search OMX FM for future price-plan orders for the first qualifying Subscriber, POU, and COU — each only if it has an offer with `ServiceType=80` |
| R2 | Activity-level PreExecCheck gates all dispatch; evaluated against serialized `OrderData` |
| R3 | orderType from `Parameter[1]`, default `2`; status always `1` |
| R4 | Response captures full `FutureOrders[]` array for downstream expiry/update operations |
| R5 | Fan-in: complete when total response count equals RequestCount (not success-only) |

### Design Risks

| Risk | Severity | Detail | Mitigation |
|------|----------|--------|-----------|
| Non-standard fan-in — all responses vs success responses | [MEDIUM] | `currActivity.RequestCount == currActivity.Response@length` — returns "true" when all responses arrive regardless of ResponseCode. Failed search still counts. | Evaluate downstream dependency; add success check if FutureOrders data is required |
| First-entity-only — may miss other entities | [MEDIUM] | Only searches the first Subscriber, first POU (by OUId), first COU of POU[1]. Orders for other subscribers/OUs not searched. | Verify intended scope for POSTPAID_UPDATE_PARAMETER |
| No resubmit guard | [MEDIUM] | Requests always re-dispatched on resubmit. For a read-only operation this is benign, but duplicate responses could break fan-in count on resub. | Acceptable for search operations; document expected behavior on resubmit |
| PreExecCheck uses OrderData, not full OrderRequest | [LOW] | PreExecCheck XPath must reference only OrderData fields. Fields in ProcessFlow or at OrderRequest root are inaccessible. | Document this constraint in activity configuration |
| `number()` on nodeId — NaN risk | [LOW] | `number($subscriber/SubscriberId)` returns NaN if SubscriberId is empty or non-numeric. | Add `string-length() > 0` guard or use raw string |

---

## §18 — Full Source Code

```java
/**
 * @author warawich-nb
 */
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_SEARCH_FUT_PP {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "OMX_SEARCH_FUT_PP";
        orderRequest.ProcessFlow.NextActivityID == "OMX_SEARCH_FUT_PP";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
        boolean isSkipped = true;
        try {
            Concepts.OM.LogicalDate logicalDateRes = Instance.getByExtIdByUri("LogicalDate", "...");
            String logicalDateVal = logicalDateRes.LogicalDate;

            // Activity-level PreExecCheck (evaluates against serialized OrderData)
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
            String chkRes = "true";
            if(String.length(nextAct.PreExecCheck) > 0) {
                String sXML = Instance.serializeUsingDefaults(orderRequest.OrderData);
                chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
            }

            if(String.equals(chkRes,"true")) {
                String subExtId = XPath.evalAsString("tib:if-absent(POU[1]/Sub[1]/@extId, COU[1]/Sub[1]/@extId)");
                String orderType = XPath.evalAsString("$orderCurrentActivity/Parameter[1]");

                // ── Scope A: Subscriber (nodeLevel=5) ───────────────────────────────
                if(subExtId != null){
                    Subscriber subscriber = Instance.getByExtIdByUri(subExtId, ...);
                    boolean hasPricePlan = XPath.evalAsBoolean("$subscriber/SubscriberOffers/ServiceType=80");
                    if(hasPricePlan){
                        Events...OMX_SEARCH_FUTURE reqEvent = Event.createEvent("xslt://{{...}}");
                        /* XSLT: ns:futureOrder { status=1, orderType=Parameter[1]|2,
                           nodeLevel=5, nodeId=number(SubscriberId) }. See §9 for field mapping. */
                        Event.Ext.sendEventImmediate(reqEvent);
                        if(!isActResub) orderCurrentActivity.RequestCount++;
                        Event.Ext.sendEventImmediate(/* Logger: "Request Sent for OMX_SEARCH_FUT_PP" */);
                        isSkipped = false;
                    }
                }

                // ── Scope B: POU Agreement (nodeLevel=3) ────────────────────────────
                String pOuExtId = XPath.evalAsString("ParentOU[OUId/text()][1]/@extId");
                if(pOuExtId != null){
                    ParentOU pOu = Instance.getByExtIdByUri(pOuExtId, ...);
                    if(XPath.evalAsBoolean("$pOu/Agreement/Offers/ServiceType=80")){
                        /* dispatch: nodeLevel=3, nodeId=number(OUId) */
                        isSkipped = false;
                    }
                }

                // ── Scope C: COU Agreement (nodeLevel=3) ────────────────────────────
                String cOuExtId = XPath.evalAsString("ParentOU[1]/ChildOU[OUId/text()][1]/@extId");
                if(cOuExtId != null){
                    ChildOU cOu = Instance.getByExtIdByUri(cOuExtId, ...);
                    if(XPath.evalAsBoolean("$cOu/Agreement/Offers/ServiceType=80")){
                        /* dispatch: nodeLevel=3, nodeId=number(OUId) */
                        isSkipped = false;
                    }
                }
            }

            if (!isSkipped) {
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
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

`Response_OMX_SEARCH_FUT_PP.rulefunction` receives the FM search response, creates an `OMX_SearchFutureRes` concept including a full `FutureOrders[]` array from the response payload, appends it to the activity's Response array, logs the response, and returns "true" when all expected responses have arrived.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order for context and logging |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_SEARCH_FUTURE` | Inbound FM search response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] array and RequestCount for fan-in |

### §19.3 — ResponseBase Concept Construction (OMX_SearchFutureRes)

```text
createObject
└── object
    ├── @extId              ← ns1:generateTrackingID()                [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode             [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg              [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus         [Conditional]
    ├── ReferenceId         ← $eventResponse/RefID                    [Conditional]
    └── FutureOrders[]      ← xsl:for-each payload/ns:futureOrders/ns:futureOrder   [Array]
        ├── @extId            ← ns1:generateTrackingID()              [Always per entry]
        ├── FutureOrderId     ← ns:futureOrderId                      [Conditional]
        ├── EffectiveDate     ← ns:effectiveDate                      [Conditional]
        ├── Status            ← ns:status                             [Conditional]
        ├── OrderType         ← ns:orderType                          [Conditional]
        ├── NodeLevel         ← ns:nodeLevel                          [Conditional]
        ├── NodeId            ← ns:nodeId                             [Conditional]
        ├── RequestedDate     ← ns:requestedDate                      [Conditional]
        ├── RequestedBy       ← ns:requestedBy                        [Conditional]
        ├── UpdatedDate       ← ns:updatedDate                        [Conditional]
        ├── UpdatedBy         ← ns:updatedBy                          [Conditional]
        ├── DealerCode        ← ns:dealerCode                         [Conditional]
        ├── ActivityReason    ← ns:activityReason                     [Conditional]
        ├── ExtendedInfos[]   ← xsl:for-each ns:extendedInfo          [Array]
        │   ├── Name          ← ns:name
        │   └── Value         ← ns:value
        ├── fromOrderId       ← ns:fromOrderId                        [Conditional]
        ├── ToOMXId           ← ns:toOMXId                            [Conditional]
        ├── UserText          ← ns:userText                           [Conditional]
        ├── Remark            ← ns:remark                             [Conditional]
        └── futureType        ← ns:futureType                         [Conditional]
```

### §19.4 — Response Completion Logic

> **[MEDIUM] Non-standard fan-in:** Uses `currActivity.RequestCount == currActivity.Response@length` — checks total response count (not success-only). A failed search still satisfies the condition.

| Metric | Expression |
|--------|-----------|
| Fan-in condition | `currActivity.RequestCount == currActivity.Response@length` |
| Return "true" | All expected responses received (success OR failure) |
| Return "false" | Still waiting for some responses |

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | "OMX_SEARCH_FUT_PP" |
| AUDIT_TRACE | "Response received for OMX_SEARCH_FUT_PP" |
| payload | Conditional on `WritePayload = "true"` |

> **Note:** Response rulefunction includes `Log.log(logger,"trace","resEvent=%s", Instance.serializeUsingDefaults(resEvent))` — serializes full response concept to trace log. May generate large entries in trace mode.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
