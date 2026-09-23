# Request_BDH_GET_DEALER_POOLS_BY_DEALER_CODE

> Retrieves the dealer pool list for the order's DealerCode from BDH (Billing Dealer Hub). Stores result as `CCBS_GetDealerPoolsForDealer` concept and writes a `DEALER_POOLS` CustomerExtendedInfo entry for downstream use.

**Backend:** BDH | **Pattern:** Single Request | **Priority:** 5 | **ForwardChain:** true

---

## §1 — Overview & Purpose

Simple single-request FM — one outbound event dispatched per order (not per-subscriber). PreExecCheck gates on DealerCode non-empty.

> **[LOW] Missing isActResub / PurgePendingRequestsBeforeResubmit:** Unlike most OMXFM rules, this rule does not call `PurgePendingRequestsBeforeResubmit` before redispatch on resubmit. May send duplicate requests.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_BDH_GET_DEALER_POOLS_BY_DEALER_CODE` |
| Priority | 5 |
| ForwardChain | true |
| Rule File | `OMXFM/Request/Request_BDH_GET_DEALER_POOLS_BY_DEALER_CODE.rule` |
| Response Rulefunction | `Response_BDH_GET_DEALER_POOLS_BY_DEALER_CODE.rulefunction` |
| Backend System | BDH (Billing Dealer Hub) |
| Dispatch Pattern | Single request (not per-subscriber) |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity state |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance matches current step |
| 2 | `orderCurrentActivity.ActivityID == "BDH_GET_DEALER_POOLS_BY_DEALER_CODE"` | Exact FM name match |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "BDH_GET_DEALER_POOLS_BY_DEALER_CODE"` | Process flow pointer matches |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity not yet dispatched |

---

## §5 — Execution Flow Diagram

1. Compute `isActResub` (not acted upon — no purge)
2. Fetch activity concept, read PreExecCheck XPath
3. Evaluate PreExecCheck on serialized orderRequest (default "true")
4. If passes: create & send `BDH_GET_DEALER_POOLS_BY_DEALER_CODE` request event
5. Set `isSkipped=false`, increment `RequestCount` (if not resubmit)
6. If `AllowWriteLog`: emit audit logger event
7. If `!isSkipped`: Status="1" + SendDataToDB; else SkipActivity("4")
8. On exception: HandleActivityException

---

## §6 — Rule Action (THEN)

### §6.1 PreExecCheck

```xpath
string-length(/ns0:OrderRequest/OrderData/DealerCode/text())!=0
```

### §6.2 Request Event Dispatch

| Property | Value |
|----------|-------|
| Event type | `Events.OMConsumers.OMXFM.Request.BDH_GET_DEALER_POOLS_BY_DEALER_CODE` |
| Method | `Event.Ext.sendEventImmediate(reqEvent)` |
| isActResub guard | Computed but not used — no purge call |

### §6.3 Status Management

| Condition | Action |
|-----------|--------|
| Request sent | `Status="1"` + `SendDataToDB` |
| PreExecCheck false | `SkipActivity("4")` |

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Used in `PREPAID_PREACTIVATION` step 1. Fires when DealerCode is non-empty.

### §8.2 ESB / JMS Channel

| Direction | Event Type | Schema | Purpose |
|-----------|-----------|--------|---------|
| [OUTBOUND] | `BDH_GET_DEALER_POOLS_BY_DEALER_CODE` | `GetDealerPoolsByDealerCode.xsd` | Fetch dealer pools |
| [INBOUND] | `Response.BDH_GET_DEALER_POOLS_BY_DEALER_CODE` | same | Pool response |

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | BDH (Billing Dealer Hub) |
| Operation | GetDealerPoolsByDealerCode |
| Schema namespace | `http://...ESB/BDH/GetDealerPoolsByDealerCode.xsd` |
| Correlation | JMSCorrelationID ← OMXTrackingId |

### §8.6 Global Variable Dependencies

| Path | Used In |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `$globalVariables/OMX_OM/WritePayload` | Conditional payload |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Param | Bound From |
|-------|-----------|
| `$orderRequest` | orderRequest concept |

### §9.4 Payload Root

```xml
<ns1:GetDealerPoolsByDealerCodeReq>
  <ns1:dealerCodeList><!-- $orderRequest/OrderData/DealerCode --></ns1:dealerCodeList>
</ns1:GetDealerPoolsByDealerCodeReq>
```

### §9.8 XSLT Stylesheet Source

```xml
<xsl:stylesheet xmlns:ns1="...GetDealerPoolsByDealerCode.xsd" version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:template match="/">
    <createEvent><event>
      <!-- JMSPriority, JMSCorrelationID, OrderID, RefID, OrderType — all conditional -->
      <payload>
        <ns1:GetDealerPoolsByDealerCodeReq>
          <xsl:if test="$orderRequest/OrderData/DealerCode">
            <ns1:dealerCodeList><xsl:value-of select="$orderRequest/OrderData/DealerCode"/></ns1:dealerCodeList>
          </xsl:if>
        </ns1:GetDealerPoolsByDealerCodeReq>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority           ← $orderRequest/OrderPriority                [Conditional]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId      [Conditional]
    ├── OrderID               ← $orderRequest/OrderData/OrderID            [Conditional]
    ├── RefID                 ← $orderRequest/OrderData/Customer/RefId     [Conditional]
    ├── OrderType             ← $orderRequest/OrderData/OrderType          [Conditional]
    └── payload
        └── ns1:GetDealerPoolsByDealerCodeReq                              [Always]
            └── ns1:dealerCodeList  ← $orderRequest/OrderData/DealerCode  [Conditional]
```

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| Guard | `AllowWriteLog(orderType)` |
| PROCESS_ID | `concat(pid, "_REQ")` |
| OPERATION_NAME | "BDH_GET_DEALER_POOLS_BY_DEALER_CODE" |
| AUDIT_TRACE | "Request Sent for BDH_GET_DEALER_POOLS_BY_DEALER_CODE" |

---

## §17 — Migration Notes & Recommendations

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Missing PurgePendingRequestsBeforeResubmit | [LOW] | Add isActResub guard + purge call |
| `CCBS_GetDealerPoolsForDealer` type stored in Response array | [LOW] | Fan-in is count-based; document clearly |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_BDH_GET_DEALER_POOLS_BY_DEALER_CODE {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "BDH_GET_DEALER_POOLS_BY_DEALER_CODE";
    orderRequest.ProcessFlow.NextActivityID == "BDH_GET_DEALER_POOLS_BY_DEALER_CODE";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    // NOTE: isActResub computed but PurgePendingRequestsBeforeResubmit NOT called
    try {
      Activity nextAct = Instance.getByExtIdByUri(...);
      String chkXPath = nextAct.PreExecCheck;
      String chkRes = "true";
      boolean isSkipped = true;
      if (String.length(orderCurrentActivity.PreExecCheck) > 0) {
        String sXML = Instance.serializeUsingDefaults(orderRequest);
        chkRes = XPath.execute("/(" + chkXPath + ")", sXML, "ns0=...");
      }
      if (String.equals(chkRes, "true")) {
        Events...BDH_GET_DEALER_POOLS_BY_DEALER_CODE reqEvent = Event.createEvent("xslt://...");
        /* XSLT builds ns1:GetDealerPoolsByDealerCodeReq — see §9.8 */
        Event.Ext.sendEventImmediate(reqEvent);
        isSkipped = false;
        if (!isActResub) orderCurrentActivity.RequestCount++;
        if (AllowWriteLog(...)) { Event.Ext.sendEventImmediate(logEvent); }
      }
      if (!isSkipped) {
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
    } catch (Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

Processes BDH response: creates `CCBS_GetDealerPoolsForDealer`, extracts pool codes, upserts `CustomerExtendedInfo` DEALER_POOLS entry, logs response, signals fan-in (count-based).

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | For DEALER_POOLS storage |
| `eventResponse` | `Events...Response.BDH_GET_DEALER_POOLS_BY_DEALER_CODE` | BDH response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking |

### §19.3 ResponseBase Concept Construction

Type: `Concepts.FM.Response.CCBS_GetDealerPoolsForDealer` (specific type, not generic ResponseBase)

```text
createObject
└── object  extId=concat("GDPFD:", OMXTrackingId)           [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode     [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg      [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus [Conditional]
    ├── ReferenceId       ← $eventResponse/RefID            [Conditional]
    └── PoolName[0..*]    ← ns1:poolCode from results[code=200 and dealerCode=DealerCode]/poolList
```

After creation, poolNames is built: `concat(",", tib:concat-sequence-format($activityRes/PoolName, ","), ",")`

A `CustomerExtendedInfo` concept is looked up or created with extId `"CUSTEXT:" + OMXTrackingId + ":" + RefID + ":DEALER_POOLS"`.

### §19.4 Response Completion Logic

| Field | Value |
|-------|-------|
| Fan-in condition | `currActivity.RequestCount == currActivity.Response@length` |
| Success criteria | Count-based only (no ResponseCode "000" check) |

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| Guard | `AllowWriteLog(orderType)` |
| PROCESS_ID | `concat(pid, "_RES")` |
| OPERATION_NAME | "BDH_GET_DEALER_POOLS_BY_DEALER_CODE" ✓ |
| AUDIT_TRACE | "Response received for BDH_GET_DEALER_POOLS_BY_DEALER_CODE" ✓ |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
