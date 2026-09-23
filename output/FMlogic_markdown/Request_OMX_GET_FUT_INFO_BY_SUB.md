# Request_OMX_GET_FUT_INFO_BY_SUB

> Per-subscriber future order info retrieval — fan-out by subscriber, IntraActivitySequencing resubmit guard, BE working-memory subscriber lookup on response

**Target System:** OMX Future Info Service | **Pattern:** Per-subscriber fan-out | **forwardChain:** true | **Author:** DESKTOP-995HR2V | **Generated:** 2026-08-04

---

## §1 Overview & Purpose

This FM retrieves future order information for each subscriber across POU and COU levels. It fires one event per subscriber (not per offer), using the subscriber's RefId as the 1-part correlation key. The response writes `TotalFuturePrice` directly to the subscriber concept. The response-side lookup uses BE working-memory `Instance.getByExtIdByUri` with a "SUB:"/"CSUB:" extId prefix convention instead of nested iteration.

> **Notable design:** Resubmit uses `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` (not the standard Helpers namespace). Response handler locates the subscriber via BE concept extId lookup ("SUB:" for POU, "CSUB:" for COU) rather than iterating the order structure.

> **Bug — COU loop variable:** The COU subscriber loop at line 81 uses `for (int s = 0; s < pSubLen; s++)` but should be `s < cSubLen`. This copy-paste error iterates using the POU subscriber count for COU subscribers, which may cause an ArrayIndexOutOfBoundsException or silently process the wrong number of COU subscribers.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_OMX_GET_FUT_INFO_BY_SUB.rule` | 131 lines |
| Response file | `Response_OMX_GET_FUT_INFO_BY_SUB.rulefunction` | 41 lines |
| Author | DESKTOP-995HR2V | |
| forwardChain | true | |
| Request event | `Events.OMConsumers.OMXFM.Request.OMX_GET_FUT_INFO_BY_SUB` | |
| Response event | `Events.OMConsumers.OMXFM.Response.OMX_GET_FUT_INFO_BY_SUB` | |
| Request schema NS | `http://services.omx.truecorp.co.th/GetFutureInfoRequest.xsd` (ns) | |
| Response schema NS | `http://services.omx.truecorp.co.th/GetFutureInfoResponse.xsd` (ns) | |
| Response concept | `Concepts.FM.Response.OMX_GetFutureInfoBySubRes` | Custom — NOT ResponseBase; has TotalFuturePrice field |
| Correlation key | Subscriber RefId (1-part) | RefID = pSubRefId or cSubRefId |
| Fan-out level | Per subscriber (POU + COU) | Not per-offer |
| Resubmit handler | `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` | Different namespace than standard Helpers |
| Credential gate | None | No UserName/PassWord headers |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Order data source; Subscriber.TotalFuturePrice written by response |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Activity state; Response[] checked for per-subscriber dedup |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_GET_FUT_INFO_BY_SUB"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_GET_FUT_INFO_BY_SUB"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 Execution Flow Diagram

1. **Resubmit flag** — `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. **Resubmit purge** — if isActResub: `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
3. **Obtain nextAct** and extract `chkXPath = nextAct.PreExecCheck`
4. **isSkipped = true** (default)
5. **Loop POU Subscriber:**
   - Per-subscriber dedup: check Response[].ReferenceId == pSubRefId AND CompletionStatus==2
   - If !reqSuccess: evaluate PreExecCheck via `GetXMLForSubscriber(orderRequest, pSubRefId)`
   - If chkRes=="true": fire event, audit log, isSkipped=false, if !isActResub then RequestCount++
6. **Loop COU Subscriber** (same pattern; `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)`)
   - `[BUG: loop uses pSubLen instead of cSubLen]`
7. **Status update:** if !isSkipped → `GetActivityStatusString("1", false)` + `SendDataToDB`; else `SkipActivity("4")`
8. **Exception:** try/catch → `HandleActivityException`

---

## §6 Rule Action (THEN) — Key Details

### §6.1 — IntraActivitySequencing Resubmit

> **Namespace difference:** This FM calls `RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)` — the `IntraActivitySequencing` sub-namespace, while most FMs call the flat `RuleFunctions.Helpers.PurgePendingRequestsBeforeResubmit`. This may implement throttled resubmit sequencing rather than a simple clear.

### §6.2 — Per-Subscriber Dedup Check

```java
boolean reqSuccess = false;
for(int iResp=0; iResp<orderCurrentActivity.Response@length; iResp++) {
    if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, pSubRefId)
        && orderCurrentActivity.Response[iResp].CompletionStatus == 2) {
        reqSuccess = true;
    }
}
if(!reqSuccess) {
    // proceed with PreExecCheck + fire event
}
```

Correlation is per-subscriber (1-part RefId). Same pattern as MCS_GET_CHARGE_INFO but at subscriber granularity.

### §6.3 — COU Loop Bug

> **Bug at line 81:**

```java
int cSubLen = orderRequest.OrderData.Customer.ParentOU[p].ChildOU[c].Subscriber@length;
for (int s = 0; s < pSubLen; s++) {  // ← BUG: should be cSubLen
    String cSubRefId = orderRequest.OrderData.Customer.ParentOU[p].ChildOU[c].Subscriber[s].RefId;
```

`pSubLen` is the POU subscriber count. If POU has more subscribers than COU, an ArrayIndexOutOfBoundsException will be thrown. If POU has fewer, some COU subscribers will be silently skipped.

---

## §7 Data Extraction

No pipe/delimiter parsing in this FM. Subscriber ID and RefId accessed directly from working memory. PreExecCheck helper serializes subscriber-level context only (no offer-level fields needed).

---

## §8 System & Integration Dependencies

### §8.1 — Order Type Dependencies

No order-type branching. Fires for all orders with POU and/or COU subscribers.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Purpose |
|-----------|---------|-------------|---------|
| [OUTBOUND] | OMX FM JMS | OMX_GET_FUT_INFO_BY_SUB queue | Per-subscriber future info request |
| [INBOUND] | OMX FM JMS | OMX_GET_FUT_INFO_BY_SUB response queue | TotalFuturePrice per subscriber |
| [LOG] | OMXESB Logger | Audit event (immediate) | Request and response audit trail |

### §8.3 — Backend API Details

| Field | Value |
|-------|-------|
| System | OMX Future Info Service |
| Request root element | `ns:GetFutureInfoRequest` |
| Response root element | `ns:GetFutureInfoResponse` |
| Correlation | Subscriber RefId (1-part) |
| Key request field | `ns:SubscriberId` — subscriber's system ID |
| Key response field | `ns:TotalFuturePrice` |

### §8.4 — BE Working Memory Dependencies

| Concept | Field | Access | Notes |
|---------|-------|--------|-------|
| OrderRequest | Customer.ParentOU[].Subscriber[] | READ | SubscriberId + RefId for fan-out |
| OrderRequest | Customer.ParentOU[].ChildOU[].Subscriber[] | READ | COU subscriber fan-out |
| Subscriber | TotalFuturePrice | WRITTEN | Set from response TotalFuturePrice (or 0) |
| Activity | Response[].ReferenceId + CompletionStatus | READ | Per-subscriber dedup check |
| Activity | RequestCount / Response[] | READ+WRITTEN | Fan-out + fan-in |

### §8.5 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `OMX_OM/WritePayload` | Payload inclusion in audit |

> **No credential gate** (`IsEnableUserPass`) — this FM sends no UserName/PassWord headers.

---

## §9 Detailed Payload Build

### §9.1 — XSLT Variants (POU vs COU)

Two XSLT variants are used — structurally identical except for the parameter name binding the subscriber RefId and SubscriberId:

| Variant | Parameters | RefID | SubscriberId |
|---------|-----------|-------|--------------|
| POU | `$orderRequest`, `$pSubRefId`, `$pSubId` | `$pSubRefId` | `$pSubId` |
| COU | `$orderRequest`, `$cSubRefId`, `$cSubId` | `$cSubRefId` | `$cSubId` |

### §9.2 — JMS / Event Header Fields

| Header | Source | Condition |
|--------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | Conditional |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| OrderID | `$orderRequest/OrderData/OrderID` | Conditional |
| RefID | `$pSubRefId` / `$cSubRefId` | Always — subscriber RefId |
| OrderType | `$orderRequest/OrderData/OrderType` | Conditional |

### §9.3 — Payload Fields

| XML Element | Source | Notes |
|-------------|--------|-------|
| `ns:SubscriberId` | `$pSubId` / `$cSubId` | Subscriber's system ID (not RefId) — always present |

### §9.4 — Generated XML Example

```xml
<JMSPriority>5</JMSPriority>
<JMSCorrelationID>OMX-TRK-20250804-001</JMSCorrelationID>
<RefID>SUB-REF-001</RefID>
<OrderType>3</OrderType>
<payload>
  <ns:GetFutureInfoRequest xmlns:ns="http://services.omx.truecorp.co.th/GetFutureInfoRequest.xsd">
    <ns:SubscriberId>0812345678</ns:SubscriberId>
  </ns:GetFutureInfoRequest>
</payload>
```

### §9.5 — XSLT Stylesheet Source (POU variant; COU is identical with $cSubRefId/$cSubId)

```xml
<xsl:stylesheet
  xmlns:ns="http://services.omx.truecorp.co.th/GetFutureInfoRequest.xsd"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="pSubRefId"/>   <!-- subscriber RefId — used as RefID header -->
  <xsl:param name="pSubId"/>      <!-- subscriber system ID — sent as ns:SubscriberId -->
  <xsl:template match="/">
    <createEvent><event>
      <xsl:if test="$orderRequest/OrderPriority">
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderID">
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      </xsl:if>
      <RefID><xsl:value-of select="$pSubRefId"/></RefID>
      <xsl:if test="$orderRequest/OrderData/OrderType">
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      </xsl:if>
      <payload>
        <ns:GetFutureInfoRequest>
          <ns:SubscriberId><xsl:value-of select="$pSubId"/></ns:SubscriberId>
        </ns:GetFutureInfoRequest>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                   [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId          [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                [Conditional]
    ├── RefID                ← $pSubRefId / $cSubRefId (subscriber RefId)     [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType              [Conditional]
    └── payload
        └── ns:GetFutureInfoRequest
            └── ns:SubscriberId  ← $pSubId / $cSubId (subscriber system ID)  [Always]
```

> No credential headers. Minimal payload — only SubscriberId. The RefID (subscriber RefId) is the only correlation identifier.

---

## §11 Audit Logging

| Field | Request Value | Response Value |
|-------|---------------|----------------|
| AUDIT_TRACE | `"Request Sent for OMX_GET_FUT_INFO_BY_SUB"` | `"Response received for OMX_GET_FUT_INFO_BY_SUB"` |
| OPERATION_NAME | `"OMX_GET_FUT_INFO_BY_SUB"` | `"OMX_GET_FUT_INFO_BY_SUB"` |
| Send method | `Event.Ext.sendEventImmediate()` | `Event.Ext.sendEventImmediate()` |
| Payload | Copy of `$reqEvent` (gated by WritePayload) | Copy of `$eventResponse` (gated by WritePayload) |

> Note: Request audit is sent BEFORE RequestCount++, so pid is captured before incrementing.

---

## §12 Activity Status Management

| Condition | Call | Code |
|-----------|------|------|
| At least one event sent | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" (RUNNING) |
| No events sent (isSkipped) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" (SKIPPED) |

---

## §13 Exception / Error Handling

```java
try { /* entire rule body */ }
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Resubmit purge — IntraActivitySequencing namespace variant |
| `GetXMLForSubscriber(orderRequest, pSubRefId)` | Serialize POU subscriber for PreExecCheck evaluation |
| `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)` | Serialize COU subscriber for PreExecCheck evaluation |
| `IsBlankOrStringNull(value)` | **Response:** null/blank check on TotalFuturePrice |
| `Number.doubleValue(str)` | **Response:** parse TotalFuturePrice string to double |
| `Instance.getByExtIdByUri(extId, conceptPath)` | **Response:** BE working-memory subscriber lookup |
| `GetActivityStatusString(code, flag)` | Activity status string builder |
| `SendDataToDB(orderRequest)` | Persist to DB |
| `SkipActivity(orderRequest, activity, code)` | Mark activity skipped |
| `HandleActivityException(orderRequest, activity, ae, msg)` | Exception handler |

---

## §15 Function Dependency Tree

```text
Request_OMX_GET_FUT_INFO_BY_SUB (rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)  [if isActResub]
├── Instance.getByExtIdByUri(NextActivityName, conceptPath)
├── String.equals(Response[i].ReferenceId, subRefId)  [per-subscriber dedup]
├── GetXMLForSubscriber(orderRequest, pSubRefId)  [POU PreExecCheck]
├── GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)  [COU PreExecCheck]
├── XPath.execute(chkXPath, sXML, ns)
├── Event.createEvent("xslt://OMX_GET_FUT_INFO_BY_SUB...")
├── Event.Ext.sendEventImmediate(reqEvent)
├── Event.Ext.sendEventImmediate(auditEvent)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")
└── RuleFunctions.Helpers.HandleActivityException(...)  [catch]

Response_OMX_GET_FUT_INFO_BY_SUB (rulefunction)
├── Instance.createInstance("xslt://{{OMX_GetFutureInfoBySubRes}}")
├── Instance.getByExtIdByUri("SUB:" + OMXTrackingId + ":" + RefID, Subscriber)
├── Instance.getByExtIdByUri("CSUB:" + OMXTrackingId + ":" + RefID, Subscriber)  [if POU null]
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(TotalFuturePrice)
├── Number.doubleValue(TotalFuturePrice)
├── Event.Ext.sendEventImmediate(auditLogEvent)
└── XPath.evalAsInt("count(Response[tib:right(tib:trim(ResponseCode),3)='000'])")
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields | Role |
|---------|-----------|------|
| `Concepts.FM.Response.OMX_GetFutureInfoBySubRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, TotalFuturePrice | Custom response concept — extends base with TotalFuturePrice |
| `Concepts.OrderRequest.OrderElements.Subscriber` | SubscriberId, RefId, TotalFuturePrice | WRITTEN — TotalFuturePrice populated from response |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Fire one request per subscriber (POU + COU), using subscriber RefId as the 1-part correlation key. |
| R2 | Per-subscriber dedup: check Response[].ReferenceId == subRefId AND CompletionStatus == 2 before firing. |
| R3 | Resubmit: call IntraActivitySequencing.PurgePendingRequestsBeforeResubmit (not standard Helpers variant). |
| R4 | Send only `ns:SubscriberId` in payload — no offer-level fields. |
| R5 | Response: locate subscriber via BE extId lookup "SUB:\<OMXTrackingId\>:\<RefID\>" (POU) then "CSUB:…" (COU). |
| R6 | Write TotalFuturePrice as double to subscriber; default to 0 if blank/null. |
| R7 | Fan-in: RequestCount == count(Response[tib:right(tib:trim(ResponseCode), 3) = "000"]). |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **COU loop bug (line 81): `pSubLen` used instead of `cSubLen`** | [HIGH] | Fix immediately: change `s < pSubLen` to `s < cSubLen`. Test orders with COU subscribers where POU and COU subscriber counts differ. |
| Subscriber extId convention ("SUB:" / "CSUB:") — implicit contract; not documented in code | [MEDIUM] | Document extId convention; verify subscriber concept creation code uses matching prefix |
| IntraActivitySequencing.PurgePendingRequestsBeforeResubmit — different behavior than standard Helpers variant | [MEDIUM] | Verify functional difference between the two variants before migrating |
| If subscriber == null in response (extId lookup fails), TotalFuturePrice is silently not written | [MEDIUM] | Add warning log when subscriber is null; investigate extId mismatch root cause |

---

## §18 Full Source Code

```java
/**
 * Request_OMX_GET_FUT_INFO_BY_SUB — Author: DESKTOP-995HR2V
 * Per-subscriber future info retrieval
 */
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_FUT_INFO_BY_SUB {
  attribute { priority=5; forwardChain=true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_GET_FUT_INFO_BY_SUB";
    orderRequest.ProcessFlow.NextActivityID == "OMX_GET_FUT_INFO_BY_SUB";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      if(isActResub) {
        IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      }
      Activity nextAct = Instance.getByExtIdByUri(...);
      boolean isSkipped = true;

      /*** POU Subscriber loop ***/
      for (int p...; s...) {
        String pSubRefId = Subscriber[s].RefId;
        String pSubId = Subscriber[s].SubscriberId;
        // reqSuccess dedup check (same pattern as MCS_GET_CHARGE_INFO)
        if(!reqSuccess) {
          // PreExecCheck via GetXMLForSubscriber
          if(chkRes == "true") {
            // [XSLT: ns:GetFutureInfoRequest with ns:SubscriberId — see §9.5]
            Event reqEvent = Event.createEvent("xslt://{{OMX_GET_FUT_INFO_BY_SUB}}...");
            Event.Ext.sendEventImmediate(reqEvent);
            Event.Ext.sendEventImmediate(auditEvent);
            if(!isActResub) orderCurrentActivity.RequestCount++;
            isSkipped = false;
          }
        }
      }

      /*** COU Subscriber loop — BUG: uses pSubLen instead of cSubLen ***/
      for (int c...; s = 0; s < pSubLen; s++) {  // ← should be cSubLen
        // same pattern using GetXMLForSubscriberInChildOU
      }

      if(!isSkipped) {
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
    } catch (Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
  }
}
```

---

## §19 Response Message Rule

### §19.1 — Overview

Maps the GetFutureInfo response into a custom concept (`OMX_GetFutureInfoBySubRes`), locates the target subscriber via BE working-memory extId lookup ("SUB:"/"CSUB:" prefix), writes TotalFuturePrice (or 0 if blank), then signals fan-in completion.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | READ — OMXTrackingId for extId construction |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.OMX_GET_FUT_INFO_BY_SUB | Backend response |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Response[] appended; fan-in checked |

### §19.3 — Response Concept Construction (OMX_GetFutureInfoBySubRes)

```text
createObject
└── object @extId ← OMXUtils:generateTrackingID()                                              [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode                                      [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg  (source=ResponseMsg)                 [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus                                  [Conditional]
    ├── ReferenceId         ← $eventResponse/RefID  (source=RefID)                             [Conditional]
    └── TotalFuturePrice    ← $eventResponse/payload/ns:GetFutureInfoResponse/ns:TotalFuturePrice   [Conditional: element exists]
```

### §19.4 — Subscriber Lookup via BE ExtId

```java
// Try POU subscriber first:
Subscriber subscriber = Instance.getByExtIdByUri(
    "SUB:" + orderRequest.OrderData.OMXTrackingId + ":" + eventResponse.RefID,
    "/Concepts/OrderRequest/OrderElements/Subscriber");

// Fall back to COU subscriber prefix:
if(subscriber == null) {
    subscriber = Instance.getByExtIdByUri(
        "CSUB:" + orderRequest.OrderData.OMXTrackingId + ":" + eventResponse.RefID,
        "/Concepts/OrderRequest/OrderElements/Subscriber");
}
```

> **ExtId convention:** Subscriber concepts in BE working memory use the pattern `SUB:<OMXTrackingId>:<RefId>` (POU) and `CSUB:<OMXTrackingId>:<RefId>` (COU). This convention must be consistent with subscriber concept creation code elsewhere in the system.

### §19.5 — TotalFuturePrice Write

```java
if (subscriber != null) {
    if (!IsBlankOrStringNull(activityRes.TotalFuturePrice)) {
        subscriber.TotalFuturePrice = Number.doubleValue(activityRes.TotalFuturePrice);
    } else {
        subscriber.TotalFuturePrice = 0;  // explicit 0 if blank
    }
} // if subscriber is null — silently no-op (no error logged)
```

### §19.6 — Fan-in Completion Logic

```java
int successResponseCount = XPath.evalAsInt(
    "count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = '000'])");
if(currActivity.RequestCount == successResponseCount) { return "true"; }
else { return "false"; }
```

Standard "000" success count fan-in.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
