# Request_OMX_SEARCH_FUT_ALL

OMX Future Order Search — Serialized 3-Scope Fan-Out (Subscriber / ParentOU / ChildOU)

**Rule:** OMXFM | **Priority:** 5 | **Backend:** OMX-FM (Future Order Service) | **Dispatch:** IntraActivitySequencing (serialized)

---

## §1 — Overview & Purpose

Searches the OMX Future Order Service for all pending future orders associated with the current order's subscribers and organisational units. Results are loaded into working memory as `OMX_SearchFutureAllRes` and used by subsequent FMs to resolve future offer dates, extract future order IDs, and determine contract expiry status.

> **Serialized multi-scope dispatch (IntraActivitySequencing):** The rule can dispatch up to 3 sequential requests — one per scope that has data present — using the IntraActivitySequencing framework. Requests fire one at a time (not in parallel): each response triggers the next queued request. The final response advances the process flow.

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_SEARCH_FUT_ALL` |
| Backend system | OMX-FM (OMX Future Order / FutureOrder service) |
| Outbound events | `OMX_SEARCH_FUTURE_ALL` (Subscriber and ParentOU); `OMX_SEARCH_FUTURE` (ChildOU) |
| Response event | `Events.OMConsumers.OMXFM.Response.OMX_SEARCH_FUTURE_ALL` |
| Response concept | `Concepts.FM.Response.OMX_SearchFutureAllRes` |
| ProcessConfig parameters | STATUS=1, ORDER_TYPE=4, GET_FUT_ORDER_ID=Y |
| Payload schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd` |

---

## §2 — Rule Metadata & Attributes

| Property | Value |
|----------|-------|
| Namespace | `Rules.OMConsumers.OMXFM.Request` |
| Rule file | `Request_OMX_SEARCH_FUT_ALL.rule` |
| Priority | 5 |
| forwardChain | true |
| Author | usuf-chu |
| Request count increment | Per scope sent (Subscriber, ParentOU, ChildOU — up to 3) |
| @extId on outbound event | None — BE auto-generates |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order request — customer, subscriber, OU data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity (OMX_SEARCH_FUT_ALL) |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Binds activity to this order |
| 2 | `orderCurrentActivity.ActivityID == "OMX_SEARCH_FUT_ALL"` | Restricts to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_SEARCH_FUT_ALL"` | Confirms process flow position |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Prevents re-processing |

---

## §5 — Execution Flow

1. Check resubmit: `isActResub`; if true → purge pending requests (`PurgePendingRequestsBeforeResubmit`)
2. Evaluate PreExecCheck XPath against `Instance.serializeUsingDefaults(orderRequest.OrderData)`
3. Read parameters: `futStatus` ← STATUS, `futOrderType` ← ORDER_TYPE, `useRawSubscriberId` ← USE_RAW_SUBS_ID
4. **Scope A — Subscriber:** if `ParentOU[1]/Subscriber[1]/@extId` exists → build + assert `OMX_SEARCH_FUTURE_ALL` event (nodeLevel=5) → ActionRequestEvent → RequestCount++
5. **Scope B — ParentOU:** if `ParentOU[OUId][1]/@extId` exists → build + assert `OMX_SEARCH_FUTURE_ALL` event (nodeLevel=3, nodeId=OUId) → ActionRequestEvent → RequestCount++
6. **Scope C — ChildOU:** if `ParentOU[1]/ChildOU[OUId][1]/@extId` exists → build + assert `OMX_SEARCH_FUTURE` event (nodeLevel=3, nodeId=OUId) → ActionRequestEvent → RequestCount++
7. If at least one scope found: `SendFirstRequestEvent` → send queue head → set Status=PROCESSING
8. If no scope found: `SkipActivity(..., "4")`
9. On exception: `HandleActivityException()`

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

> **IntraActivitySequencing pattern:** Unlike standard parallel fan-out (`sendEventImmediate`), this FM uses `IntraActivitySequencing.ActionRequestEvent` to queue each request. `SendFirstRequestEvent` fires the first one. Subsequent requests in the queue fire one-at-a-time as each response arrives. This ensures the Future Order Service is queried independently for each scope without concurrency issues.

**Scope selection logic:**

| Scope | Trigger condition | Event type | nodeLevel | nodeId source |
|-------|-------------------|------------|-----------|---------------|
| A — Subscriber | `tib:if-absent(ParentOU[1]/Subscriber[1]/@extId, ParentOU[1]/ChildOU[1]/Subscriber[1]/@extId)` not null | `OMX_SEARCH_FUTURE_ALL` | 5 | `number(subscriber.SubscriberId)` or `subscriber.RawSubscriberId` if USE_RAW_SUBS_ID=Y |
| B — ParentOU | `ParentOU[OUId/text()][1]/@extId` not null | `OMX_SEARCH_FUTURE_ALL` | 3 | `number(pOu.OUId)` |
| C — ChildOU | `ParentOU[1]/ChildOU[OUId/text()][1]/@extId` not null | `OMX_SEARCH_FUTURE` | 3 | `number(cOu.OUId)` |

> **[MEDIUM] Two different outbound event types:** Scopes A and B send `OMX_SEARCH_FUTURE_ALL`; Scope C sends `OMX_SEARCH_FUTURE`. These are distinct event paths in the ESB that may return different response schemas.

**Audit logger:** Fires per scope after each request is asserted (AUDIT_TRACE: "Request Sent for OMX_SEARCH_FUT_ALL"). Gated on `$globalVariables/OMX_OM/WritePayload="true"` for payload inclusion.

---

## §8 — System & Integration Dependencies

### §8.2 — ESB / JMS Channel Dependencies

| Event | Scope | Direction | Backend |
|-------|-------|-----------|---------|
| `OMX_SEARCH_FUTURE_ALL` | Subscriber, ParentOU | [OUTBOUND] | OMX-FM Future Order Service |
| `OMX_SEARCH_FUTURE` | ChildOU | [OUTBOUND] | OMX-FM Future Order Service |
| `OMX_SEARCH_FUTURE_ALL` (response) | All | [INBOUND] | OMX-FM → BE |

### §8.3 — Backend API Details

| System | Operation | Schema namespace | nodeLevel |
|--------|-----------|-----------------|-----------|
| OMX-FM | Search Future Orders (All) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd` | 5 (Subscriber), 3 (ParentOU/ChildOU) |

### §8.5 — ExtendedInfo Fields Written by Response Handler

| Name | Value | Written on | Target |
|------|-------|-----------|--------|
| `FUT_ORDER_ID` | Latest matching future order ID | GET_FUT_ORDER_ID=Y and match found | `SubscriberOffers.ExtendedInfo[]` |
| `CONTRACT_EXPIRED` | Y / N | CHECK_CONTRACT_EXPIRED=Y | `SubscriberOffers.ExtendedInfo[]` |
| `FROM_FUT` | (no value) | USE_NEW_BILL_CYCLE=Y in future order | Synthetic SubscriberOffers ExtendedInfo |
| `FE_OR_CCBS` | `FUT` | USE_NEW_BILL_CYCLE=Y in future order | Synthetic SubscriberOffers ExtendedInfo |
| `FUT_SOC_ID` | futureSocId | USE_NEW_BILL_CYCLE=Y in future order | Synthetic SubscriberOffers ExtendedInfo |

### §8.6 — ProcessConfig Parameters Consumed

| Parameter key | Step 7 value | Variable | Usage |
|--------------|-------------|----------|-------|
| STATUS | 1 | `futStatus` | Filter: future order status to search for |
| ORDER_TYPE | 4 | `futOrderType` | Filter: future order type to search for |
| GET_FUT_ORDER_ID | Y | — | Response handler: inject FUT_ORDER_ID onto SubscriberOffers |
| USE_RAW_SUBS_ID | (not set in step 7) | `useRawSubscriberId` | Subscriber scope: use RawSubscriberId instead of SubscriberId |
| GET_FUT_EXP_DATE | (not set in step 7) | — | Response handler: update offer ExpirationDate from future order |
| CHECK_CONTRACT_EXPIRED | (not set in step 7) | — | Response handler: inject CONTRACT_EXPIRED flag |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameters

| Parameter | Bound from | Variants |
|-----------|-----------|---------|
| `$orderRequest` | BE concept | All |
| `$subscriber` | Subscriber concept instance | Scope A only |
| `$pOu` | ParentOU concept instance | Scope B only |
| `$cOu` | ChildOU concept instance | Scope C only |
| `$futStatus` | `GetActivityParameterValueFromKey(activity, "STATUS")` | All |
| `$futOrderType` | `GetActivityParameterValueFromKey(activity, "ORDER_TYPE")` | All |
| `$useRawSubscriberId` | `GetActivityParameterValueFromKey(activity, "USE_RAW_SUBS_ID")` | Scope A only |

### §9.3 — JMS / Event Header Fields (common to all variants)

| Header | Source | Condition |
|--------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Conditional (xsl:if) |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Conditional (xsl:if) |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Conditional (xsl:if) |
| `RefID` | `$subscriber/RefId` / `$pOu/RefId` / `$cOu/RefId` | Conditional (xsl:if) |
| `UserName` | `$orderRequest/OrderData/User` | Conditional (xsl:if) |
| `PassWord` | `$orderRequest/OrderData/Password` | Conditional (xsl:if) |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Conditional (xsl:if) |

### §9.4 — Payload Root: ns:futureOrder

| Field | Scope A (Subscriber) | Scope B (ParentOU) | Scope C (ChildOU) |
|-------|---------------------|-------------------|------------------|
| `ns:status` | `$futStatus` = "1" (from ProcessConfig) | same | same |
| `ns:orderType` | `$futOrderType` = "4" (from ProcessConfig) | same | same |
| `ns:nodeLevel` | **5** (subscriber) | **3** (OU) | **3** (OU) |
| `ns:nodeId` | `number(subscriber.SubscriberId)` or `subscriber.RawSubscriberId` if USE_RAW_SUBS_ID=Y | `number(pOu.OUId)` | `number(cOu.OUId)` |

### §9.7 — Complete Generated XML Example (Scope A — Subscriber)

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>TRK-2026-0001</JMSCorrelationID>
    <OrderID>ORD-12345</OrderID>
    <RefID>0812345678</RefID>
    <UserName>agent01</UserName>
    <PassWord>***</PassWord>
    <OrderType>5</OrderType>
    <payload>
      <ns:futureOrder xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/.../FutureOrder.xsd">
        <ns:status>1</ns:status>
        <ns:orderType>4</ns:orderType>
        <ns:nodeLevel>5</ns:nodeLevel>
        <ns:nodeId>81234567</ns:nodeId>
      </ns:futureOrder>
    </payload>
  </event>
</createEvent>
```

### §9.8 — XSLT Stylesheet Source

**Variant ① — Scope A: Subscriber (OMX_SEARCH_FUTURE_ALL)**

```xml
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd"
    version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="subscriber"/>
  <xsl:param name="futStatus"/>
  <xsl:param name="futOrderType"/>
  <xsl:param name="useRawSubscriberId"/>
  <xsl:template match="/">
    <createEvent><event>
      <!-- JMS headers: JMSPriority, JMSCorrelationID, OrderID, RefID(subscriber/RefId),
           UserName, PassWord, OrderType — all conditional (xsl:if) -->
      <payload><ns:futureOrder>
        <ns:status><xsl:value-of select="$futStatus"/></ns:status>
        <ns:orderType><xsl:value-of select="$futOrderType"/></ns:orderType>
        <ns:nodeLevel>5</ns:nodeLevel>
        <xsl:choose>
          <xsl:when test="$useRawSubscriberId='Y'">
            <ns:nodeId><xsl:value-of select="$subscriber/RawSubscriberId"/></ns:nodeId>
          </xsl:when>
          <xsl:otherwise>
            <ns:nodeId><xsl:value-of select="number($subscriber/SubscriberId)"/></ns:nodeId>
          </xsl:otherwise>
        </xsl:choose>
      </ns:futureOrder></payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**Variant ② — Scope B: ParentOU (OMX_SEARCH_FUTURE_ALL)**

```xml
<!-- Same headers as Variant ①, RefID from pOu/RefId -->
<ns:futureOrder>
  <ns:status>$futStatus</ns:status>
  <ns:orderType>$futOrderType</ns:orderType>
  <ns:nodeLevel>3</ns:nodeLevel>
  <ns:nodeId>number($pOu/OUId)</ns:nodeId>
</ns:futureOrder>
```

**Variant ③ — Scope C: ChildOU (OMX_SEARCH_FUTURE — different event type)**

```xml
<!-- Same headers as Variant ①, RefID from cOu/RefId -->
<ns:futureOrder>
  <ns:status>$futStatus</ns:status>
  <ns:orderType>$futOrderType</ns:orderType>
  <ns:nodeLevel>3</ns:nodeLevel>
  <ns:nodeId>number($cOu/OUId)</ns:nodeId>
</ns:futureOrder>
```

---

## §10 — XSLT Field Mapping — Output Event Tree Hierarchy

**Scope A (Subscriber) — Scopes B/C differ only in nodeLevel and nodeId source:**

```text
createEvent                        [no @extId — BE auto-generates]
└── event
    ├── JMSPriority                ← $orderRequest/OrderPriority                    [Conditional: xsl:if]
    ├── JMSCorrelationID           ← $orderRequest/OrderData/OMXTrackingId          [Conditional: xsl:if]
    ├── OrderID                    ← $orderRequest/OrderData/OrderID                [Conditional: xsl:if]
    ├── RefID                      ← $subscriber/RefId                              [Conditional: xsl:if]
    ├── UserName                   ← $orderRequest/OrderData/User                   [Conditional: xsl:if]
    ├── PassWord                   ← $orderRequest/OrderData/Password               [Conditional: xsl:if]
    ├── OrderType                  ← $orderRequest/OrderData/OrderType              [Conditional: xsl:if]
    └── payload
        └── ns:futureOrder
            ├── ns:status          ← $futStatus  (= "1" in POSTPAID_UPDATE_PARAMETER) [Always]
            ├── ns:orderType       ← $futOrderType (= "4" in POSTPAID_UPDATE_PARAMETER) [Always]
            ├── ns:nodeLevel       ← 5 (hardcoded for Subscriber scope)             [Always]
            └── ns:nodeId          [Conditional: xsl:choose on USE_RAW_SUBS_ID]     [Always]
                ├── when USE_RAW_SUBS_ID="Y": ← $subscriber/RawSubscriberId
                └── otherwise:               ← number($subscriber/SubscriberId)
```

---

## §11 — Audit Logging

**Request logger** (fires per scope, after each request event is asserted):

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_REQ")` |
| OPERATION_NAME | `"OMX_SEARCH_FUT_ALL"` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `"Request Sent for OMX_SEARCH_FUT_ALL"` |
| payload | Conditional on `WritePayload="true"` — includes full `$reqEvent` |

**Response logger** (fires in response RF after processing):

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"OMX_SEARCH_FUT_ALL"` |
| AUDIT_TRACE | `"Response received for OMX_SEARCH_FUT_ALL"` |
| payload | Conditional on `WritePayload="true"` — includes full `$eventResponse` |

---

## §12 — Activity Status Management

| Scenario | Action | Status |
|----------|--------|--------|
| At least one scope found | `GetActivityStatusString("1", false)` per scope sent | PROCESSING |
| No scope found | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | SKIPPED |
| All responses received (via IntraActivitySequencing) | `NextActivity()` called by sequencer | COMPLETED |
| Exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | ERROR |

---

## §13 — Exception / Error Handling

Single `try/catch(Exception ae)` wraps the entire THEN block. On exception: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `RuleFunctions.Helpers.GetActivityParameterValueFromKey(activity, key)` | Reads STATUS, ORDER_TYPE, USE_RAW_SUBS_ID from ProcessConfig parameters |
| `RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears queued requests on resubmit |
| `RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(event, activity)` | Queues a request event for serialized dispatch |
| `RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(activity)` | Fires the first queued event |
| `RuleFunctions.Helpers.GetActivityStatusString("1", false)` | Returns PROCESSING status string |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | Persists current order state to DB |
| `RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")` | Marks activity SKIPPED |
| `RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ex, "")` | Error handler |
| `RuleFunctions.Helpers.GetNextBillDate(date, billCycleNo)` | Response RF: adjusts effective/expiry dates to next bill cycle |

---

## §15 — Function Dependency Tree

```text
Request_OMX_SEARCH_FUT_ALL (THEN block)
├── XPath.execute(preExecCheck, xml, ns)
├── XPath.evalAsString(xpath://)           [subscriber extId resolution]
├── RuleFunctions.Helpers.GetActivityParameterValueFromKey()
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()  [resubmit only]
├── [Scope A] Event.createEvent(OMX_SEARCH_FUTURE_ALL xslt) → assertEvent → ActionRequestEvent
├── [Scope B] Event.createEvent(OMX_SEARCH_FUTURE_ALL xslt) → assertEvent → ActionRequestEvent
├── [Scope C] Event.createEvent(OMX_SEARCH_FUTURE xslt) → assertEvent → ActionRequestEvent
├── IntraActivitySequencing.SendFirstRequestEvent()
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity("4")                       [no scope found]
└── HandleActivityException()               [on error]

Response_OMX_SEARCH_FUT_ALL (body)
├── Instance.createInstance(OMX_SearchFutureAllRes XSLT)     [maps response → concept]
├── RuleFunctions.Helpers.GetActivityParameterValueFromKey() [GET_FUT_ORDER_ID, etc.]
├── XPath.evalAsBoolean(isMoveSub / chkSoc / countUserNewBillCycle)
├── XPath.evalAsString(nodeId per FutureOrdersWithSoc entry)
├── XPath.evalAsDateTime(futExpDate)
├── XPath.evalAsInt(latestFutOrderId)
├── RuleFunctions.Helpers.GetNextBillDate()                  [USE_NEW_BILL_CYCLE path]
├── Instance.createInstance(SubscriberOffers XSLT)           [USE_NEW_BILL_CYCLE path]
├── Instance.createInstance(SubscriberOffersExtendedInfo XSLT) [FUT_ORDER_ID / CONTRACT_EXPIRED]
└── Event.Ext.sendEventImmediate(Logger event)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Search future orders at up to 3 node scopes: Subscriber (level 5), ParentOU (level 3), ChildOU (level 3) |
| R2 | Requests must be serialized (not parallel) — each scope awaits response before next is sent |
| R3 | Parameters STATUS and ORDER_TYPE must be configurable per ProcessConfig invocation |
| R4 | Response handler must inject FUT_ORDER_ID onto SubscriberOffers when GET_FUT_ORDER_ID=Y |
| R5 | USE_NEW_BILL_CYCLE future orders must generate synthetic SubscriberOffers with FE_OR_CCBS=FUT tag |
| R6 | Match future orders to subscribers by nodeId = SubscriberId |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| Scope C uses a different event type (`OMX_SEARCH_FUTURE`) vs Scopes A & B (`OMX_SEARCH_FUTURE_ALL`) — response schema may differ | [MEDIUM] | Verify ChildOU response is compatible with OMX_SearchFutureAllRes concept mapping |
| No @extId on outbound events — BE auto-generates; correlation may be harder to trace in logs | [LOW] | Ensure JMSCorrelationID (OMXTrackingId) is used for cross-system tracing |
| IntraActivitySequencing couples request and response in a non-obvious way — the RF return value drives the sequencer, not an explicit fan-in count | [MEDIUM] | Document sequencer contract in migration; replace with explicit state machine or saga pattern |
| FUT_ORDER_ID injection matches by SOC code across all future order groups — "latest" is determined by EffectiveDate, not FutureOrderId; ties resolved by loop order | [LOW] | Consider using FutureOrderId as primary sort key in migration |
| isMoveSub check (`OrderType='39'`) is hardcoded — other order types requiring USE_NEW_BILL_CYCLE processing would need code change | [LOW] | Drive via ProcessConfig parameter rather than hardcoded order type check |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author usuf-chu
 */
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_SEARCH_FUT_ALL {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "OMX_SEARCH_FUT_ALL";
        orderRequest.ProcessFlow.NextActivityID == "OMX_SEARCH_FUT_ALL";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        boolean isSkipped = true;
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
            String chkRes = "true";
            if(String.length(nextAct.PreExecCheck) > 0) {
                String sXML = Instance.serializeUsingDefaults(orderRequest.OrderData);
                chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
            }
            if(String.equals(chkRes,"true")) {
                String futStatus = GetActivityParameterValueFromKey(orderCurrentActivity, "STATUS");
                String futOrderType = GetActivityParameterValueFromKey(orderCurrentActivity, "ORDER_TYPE");
                String useRawSubscriberId = GetActivityParameterValueFromKey(orderCurrentActivity, "USE_RAW_SUBS_ID");
                if(isActResub) PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

                /* [Scope A] Subscriber — nodeLevel=5 — OMX_SEARCH_FUTURE_ALL event — see §9.8 Variant ① */
                String subExtId = XPath.evalAsString("xpath://tib:if-absent(ParentOU[1]/Subscriber[1]/@extId, ChildOU[1]/Subscriber[1]/@extId)");
                if(subExtId != null) {
                    Events.OMConsumers.OMXFM.Request.OMX_SEARCH_FUTURE_ALL reqEvent =
                        Event.createEvent(/* xslt → fields: nodeLevel=5, nodeId=subscriber.SubscriberId — see §9.8 Variant ① */);
                    Event.assertEvent(reqEvent);
                    ActionRequestEvent(reqEvent, orderCurrentActivity);
                    if(!isActResub) orderCurrentActivity.RequestCount++;
                    orderCurrentActivity.Status = GetActivityStatusString("1", false);
                    /* Request logger — see §11 */
                    SendDataToDB(orderRequest);
                    isSkipped = false;
                }

                /* [Scope B] ParentOU — nodeLevel=3 — OMX_SEARCH_FUTURE_ALL event — see §9.8 Variant ② */
                String pOuExtId = XPath.evalAsString("xpath://ParentOU[OUId/text()][1]/@extId");
                if(pOuExtId != null) { /* same pattern, nodeId=pOu.OUId */ isSkipped = false; }

                /* [Scope C] ChildOU — nodeLevel=3 — OMX_SEARCH_FUTURE event (different!) — see §9.8 Variant ③ */
                String cOuExtId = XPath.evalAsString("xpath://ParentOU[1]/ChildOU[OUId/text()][1]/@extId");
                if(cOuExtId != null) { /* OMX_SEARCH_FUTURE event — note different event type */ isSkipped = false; }
            }

            if(!isSkipped) {
                SendFirstRequestEvent(orderCurrentActivity);
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

## §19 — Response Message Rule

### §19.1 — Overview

Receives the `OMX_SEARCH_FUTURE_ALL` response event, maps it into an `OMX_SearchFutureAllRes` concept, appends it to `currActivity.Response[]`, then performs extensive post-processing to inject future order metadata onto working-memory `SubscriberOffers`. Returns `"true"` to signal the IntraActivitySequencing framework to send the next queued request (or advance the process if all requests are done).

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order request (modified during post-processing) |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_SEARCH_FUTURE_ALL` | Inbound future order search result event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity being responded to |

### §19.3 — Response Concept: OMX_SearchFutureAllRes

```text
createObject
└── object
    ├── @extId                     ← OMXUtils:generateTrackingID()                 [Always]
    ├── ResponseCode               ← $eventResponse/ResponseCode                   [Conditional]
    ├── ResponseMessage            ← $eventResponse/ResponseMsg                    [Conditional]
    ├── CompletionStatus           ← $eventResponse/CompletionStatus               [Conditional]
    └── FutureOrdersWithSoc[]      ← for-each ns2:futureOrderWithSoc               [Always]
        ├── futureOrder[]          ← for-each ns:futureOrder
        │   ├── FutureOrderId, EffectiveDate, Status, OrderType
        │   ├── NodeLevel, NodeId, RequestedDate, RequestedBy
        │   ├── UpdatedDate, UpdatedBy, DealerCode, ActivityReason
        │   └── fromOrderId, ToOMXId, UserText, Remark, futureType
        ├── futureSocs[]           ← for-each ns3:futureSocs → ns3:futureSoc
        │   ├── futureSocId, code, effectiveDate, expireDate
        │   ├── instanceId, parentInstanceId, type, subType
        │   └── parameter[], childSoc[], extendedInfo[], previousSoc, socPrice
        └── futureResourceRange[]  ← for-each ns4:futureResourceRange
            └── action, name, value, effectiveDate, expirationDate
```

### §19.4 — Post-Processing Logic

Triggered when `isMoveSub` (OrderType='39') OR any of `GET_FUT_ORDER_ID=Y`, `GET_FUT_EXP_DATE=Y`, `CHECK_CONTRACT_EXPIRED=Y`:

| Parameter | Step 7 value | Effect |
|-----------|-------------|--------|
| GET_FUT_ORDER_ID=Y | **Set** | Injects `FUT_ORDER_ID=<latestFutOrderId>` ExtendedInfo on matching SubscriberOffers |
| GET_FUT_EXP_DATE=Y | Not set | Updates `offer.ExpirationDate` to the future order's effective date |
| CHECK_CONTRACT_EXPIRED=Y | Not set | Injects `CONTRACT_EXPIRED=Y/N` based on whether latestExpDate is before now |
| isMoveSub (OrderType='39') | Not POSTPAID_UPDATE_PARAMETER | Generates synthetic SubscriberOffers from future order with FE_OR_CCBS=FUT; adjusts dates to next bill cycle |

**"Latest" future order resolution:** For each SubscriberOffer, the response handler scans all FutureOrdersWithSoc entries whose `futureSoc[].code` matches `offer.Soc`. Among those, the one with the **latest EffectiveDate** wins — its `FutureOrderId` becomes the injected value.

### §19.5 — Response Completion Logic

The response RF returns `"true"` (string). The IntraActivitySequencing framework uses this return value to decide whether to fire the next queued request or call `NextActivity()` once all requests are exhausted. There is no explicit `RequestCount == successResponseCount` fan-in check in this FM.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
