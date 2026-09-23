# Request_CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO

## §1 — Overview & Purpose

Sends a `CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO` request to CCBS to update the billing cycle for a customer. The payload contains the customer ID, new billing cycle number, and activity reason/user text. This is a single-shot FM (one request per activity, no subscriber loop).

Uses the **ActionRequestEvent + SendFirstRequestEvent** pattern. On resubmit, pending requests are purged first.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule File | Request_CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO.rule |
| Response File | Response_CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO.rulefunction |
| Priority | 5 |
| ForwardChain | true |
| Author | Sakrapee-SCM-PC |
| Target System | CCBS |
| Event Sent | Events.OMConsumers.OMXFM.Request.CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO |
| Response Concept | Concepts.FM.Response.CCBS_ChangeCustomerBillingCycleInfoRes |
| Send Pattern | assertEvent + ActionRequestEvent + SendFirstRequestEvent |
| Iteration | Single-shot (no loop) |
| Fan-in Type | count(Response[code ends "000"]) == RequestCount |

---

## §3 — Working Memory — Declared Objects

| Variable | Type Path | Role |
|----------|-----------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Master order request |
| orderCurrentActivity | Concepts.OM.ProcessConfig.Activity | Current activity |
| logicalDateRes | Concepts.OM.LogicalDate | Logical date (read but not passed to XSLT) |

---

## §4 — Rule Conditions (WHEN)

| Condition | Expression |
|-----------|-----------|
| Activity match | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| ActivityID check | `orderCurrentActivity.ActivityID == "CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO"` |
| NextActivity check | `orderRequest.ProcessFlow.NextActivityID == "CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO"` |
| Status check | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow Diagram

1. Read logicalDate (unused in XSLT)
2. Get nextAct from working memory by extId
3. PreExecCheck gate: if `nextAct.PreExecCheck` length > 0 → serialize OrderData → XPath.execute
4. If chkRes == "true": proceed; else SkipActivity("4")
5. Check isActResub: if resubmit → PurgePendingRequestsBeforeResubmit
6. Build `CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO` event via XSLT
7. assertEvent(reqEvent) → ActionRequestEvent(reqEvent, orderCurrentActivity)
8. Send audit log event
9. SendFirstRequestEvent(orderCurrentActivity)
10. Status = GetActivityStatusString("1", false); SendDataToDB

---

## §6 — Rule Action (THEN)

```java
// 1. Read logical date (unused in payload)
Concepts.OM.LogicalDate logicalDateRes = Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate");
String logicalDateVal = logicalDateRes.LogicalDate;

// 2. PreExecCheck
Concepts.OM.ProcessConfig.Activity nextAct =
    Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, "...");
String chkRes = "true";
if (String.length(nextAct.PreExecCheck) > 0) {
    String sXML = Instance.serializeUsingDefaults(orderRequest.OrderData);
    chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
}

if (String.equals(chkRes, "true")) {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    if (isActResub) {
        IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
    }
    reqEvent = Event.createEvent("xslt://{{CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO}}...");
    Event.assertEvent(reqEvent);
    IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
    Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{Logger}}...")); // audit
    IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
    orderCurrentActivity.Status = GetActivityStatusString("1", false);
    RuleFunctions.Helpers.SendDataToDB(orderRequest);
} else {
    RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
}
```

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Triggered for **CHANGE_PP** order type when billing cycle must be updated. Conditional on PreExecCheck gate.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Destination | Purpose |
|-----------|------------|---------|
| [OUTBOUND] | CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO queue | Change billing cycle request |
| [INBOUND] | Response queue | Billing cycle change confirmation |

### §8.3 Backend API Details

| System | Operation | Root Element | Namespace |
|--------|-----------|-------------|-----------|
| CCBS | ChangeCustomerBillingCycleInfo | ns3:ChangeCustomerBillingCycleInfoRequest | amdocs.csm3g.datatypes.ChangeCustomerBillingCycleInfoRequest.xsd |

### §8.4 BE Working Memory

| Concept | Fields Read |
|---------|-----------|
| OrderRequest | OrderPriority, OrderData.OMXTrackingId, OrderData.OrderID, OrderData.OrderType, OrderData.CES, OrderData.User, OrderData.Password, OrderData.Customer.CustomerId, OrderData.Customer.BillCycleNo, OrderData.Customer.CustomerActivityInfo.* |
| Activity | RequestCount, Status (written) |

### §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Controls UserName/PassWord in event headers |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Controls payload in audit log |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| XSLT Param | Bound From |
|-----------|-----------|
| orderRequest | orderRequest concept |
| globalVariables | system global variables |

### §9.4 Payload Root Element

```xml
<ns3:ChangeCustomerBillingCycleInfoRequest>
  <ns2:CustomerIdInfo>
    <ns2:CustomerNo>...</ns2:CustomerNo>     <!-- conditional -->
  </ns2:CustomerIdInfo>
  <ns1:CustomerBillingCycleInfo>
    <ns1:BillCycleNo>...</ns1:BillCycleNo>  <!-- conditional -->
  </ns1:CustomerBillingCycleInfo>
  <ns:ActivityInfo>
    <ns:ActivityReason>CREQ</ns:ActivityReason>  <!-- or actual reason -->
    <ns:UserText>...</ns:UserText>               <!-- conditional -->
  </ns:ActivityInfo>
</ns3:ChangeCustomerBillingCycleInfoRequest>
```

### §9.8 XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:ns3="...ChangeCustomerBillingCycleInfoRequest.xsd"
  xmlns:ns2="...CustomerIdInfo"
  xmlns:ns1="...CustomerBillingCycleInfo"
  xmlns:ns="...ActivityInfo"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="globalVariables"/>
  <xsl:template match="/">
    <createEvent>
      <event>
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <xsl:if test="$globalVariables/.../IsEnableUserPass='true'">
          <xsl:if test="$orderRequest/OrderData/User">
            <UserName><xsl:value-of select="$orderRequest/OrderData/User"/></UserName>
          </xsl:if>
          <xsl:if test="$orderRequest/OrderData/Password">
            <PassWord><xsl:value-of select="$orderRequest/OrderData/Password"/></PassWord>
          </xsl:if>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OrderType">
          <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/CES">
          <CES><xsl:value-of select="$orderRequest/OrderData/CES"/></CES>
        </xsl:if>
        <payload>
          <ns3:ChangeCustomerBillingCycleInfoRequest>
            <ns2:CustomerIdInfo>
              <xsl:if test="$orderRequest/OrderData/Customer/CustomerId">
                <ns2:CustomerNo>
                  <xsl:value-of select="$orderRequest/OrderData/Customer/CustomerId"/>
                </ns2:CustomerNo>
              </xsl:if>
            </ns2:CustomerIdInfo>
            <ns1:CustomerBillingCycleInfo>
              <xsl:if test="$orderRequest/OrderData/Customer/BillCycleNo">
                <ns1:BillCycleNo>
                  <xsl:value-of select="$orderRequest/OrderData/Customer/BillCycleNo"/>
                </ns1:BillCycleNo>
              </xsl:if>
            </ns1:CustomerBillingCycleInfo>
            <ns:ActivityInfo>
              <ns:ActivityReason>
                <xsl:value-of select="if (exists(.../ActivityReason) and string-length(tib:trim(...))>0)
                  then .../ActivityReason else 'CREQ'"/>
              </ns:ActivityReason>
              <xsl:if test="$orderRequest/OrderData/Customer/CustomerActivityInfo/UserText">
                <ns:UserText>
                  <xsl:value-of select="$orderRequest/OrderData/Customer/CustomerActivityInfo/UserText"/>
                </ns:UserText>
              </xsl:if>
            </ns:ActivityInfo>
          </ns3:ChangeCustomerBillingCycleInfoRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                       [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId             [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                   [Always]
    ├── UserName             ← $orderRequest/OrderData/User                      [Conditional: IsEnableUserPass='true' AND User]
    ├── PassWord             ← $orderRequest/OrderData/Password                  [Conditional: IsEnableUserPass='true' AND Password]
    ├── OrderType            ← $orderRequest/OrderData/OrderType                 [Conditional: if OrderType]
    ├── CES                  ← $orderRequest/OrderData/CES                       [Conditional: if CES]
    └── payload                                                                  [Always]
        └── ns3:ChangeCustomerBillingCycleInfoRequest
            ├── ns2:CustomerIdInfo
            │   └── ns2:CustomerNo      ← Customer/CustomerId                   [Conditional: if CustomerId]
            ├── ns1:CustomerBillingCycleInfo
            │   └── ns1:BillCycleNo     ← Customer/BillCycleNo                  [Conditional: if BillCycleNo]
            └── ns:ActivityInfo
                ├── ns:ActivityReason   ← CustomerActivityInfo/ActivityReason or "CREQ" [Always]
                └── ns:UserText         ← CustomerActivityInfo/UserText          [Conditional: if UserText]
```

**Legend:** `[Always]` = always emitted · `[Conditional: expr]` = xsl:if

---

## §11 — Audit Logging

| Field | Request Value | Response Value |
|-------|--------------|---------------|
| OPERATION_NAME | CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO | CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO |
| AUDIT_TRACE | "Request Sent for CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO" | concat("Response received for RefId ", $eventResponse/RefID) |
| PROCESS_ID | concat($pid, "_REQ") | concat($sysNanoTimeValue, "_RES") |

> Response AUDIT_TRACE includes the RefId value dynamically — differs from the typical static string pattern used in other FMs.

---

## §12 — Activity Status Management

| Action | Value | When |
|--------|-------|------|
| Status = GetActivityStatusString("1", false) | 1 (Processing) | After send |
| SkipActivity("4") | 4 (Skipped) | PreExecCheck returns false |

---

## §13 — Exception / Error Handling

Standard try/catch: `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| Instance.serializeUsingDefaults(orderRequest.OrderData) | Serialize OrderData to XML for PreExecCheck |
| XPath.execute(expr, xml, ns) | Evaluate PreExecCheck XPath expression |
| IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity) | Clear pending requests on resubmit |
| IntraActivitySequencing.ActionRequestEvent(reqEvent, activity) | Register request in intra-activity sequencing |
| IntraActivitySequencing.SendFirstRequestEvent(activity) | Trigger sending of first queued request |
| RuleFunctions.Helpers.GetActivityStatusString("1", false) | Get processing status string |
| RuleFunctions.Helpers.SendDataToDB(orderRequest) | Persist activity state to database |
| RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4") | Mark activity as skipped |
| RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "") | Handle exceptions |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO (rule)
├── Instance.serializeUsingDefaults(orderRequest.OrderData)   [PreExecCheck]
├── XPath.execute(PreExecCheck, sXML, ns)                    [PreExecCheck]
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit [resubmit]
├── Event.createEvent(xslt://CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO)
├── Event.assertEvent(reqEvent)
├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
├── Event.Ext.sendEventImmediate(xslt://Logger)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)                   [skip path]
└── RuleFunctions.Helpers.HandleActivityException(...)        [catch]

Response_CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO (rulefunction)
├── Instance.createInstance(xslt://CCBS_ChangeCustomerBillingCycleInfoRes)
├── Event.Ext.sendEventImmediate(xslt://Logger)
└── XPath.evalAsInt(count(Response[code "000"]))
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Fields |
|---------|-----------|
| Concepts.FM.Response.CCBS_ChangeCustomerBillingCycleInfoRes | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId (all always-emitted, no xsl:if) |
| Concepts.OM.LogicalDate | LogicalDate (read but not used in XSLT) |

---

## §17 — Migration Notes & Recommendations

**R1**: Must send ChangeCustomerBillingCycleInfo to CCBS when BillCycleNo changes as part of PP change.
**R2**: Must respect PreExecCheck gate — activity is conditional.
**R3**: ActivityReason defaults to "CREQ" if not provided.

| Risk | Severity | Mitigation |
|------|----------|-----------|
| logicalDate declared and read but never used in XSLT | [LOW] | Remove or pass to XSLT if needed |
| Response fields mapped without xsl:if guards — may emit empty elements | [MEDIUM] | Add xsl:if guards or verify CCBS always returns these fields |

---

## §18 — Full Source Code (Request Rule)

```java
/**
 * Request_CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO.rule
 * @author Sakrapee-SCM-PC
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO";
    orderRequest.ProcessFlow.NextActivityID == "CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    try {
      Concepts.OM.LogicalDate logicalDateRes = Instance.getByExtIdByUri("LogicalDate", ".../LogicalDate");
      String logicalDateVal = logicalDateRes.LogicalDate; // read but not used in XSLT
      Concepts.OM.ProcessConfig.Activity nextAct =
          Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, ".../Activity");
      String chkRes = "true";
      if (String.length(nextAct.PreExecCheck) > 0) {
          String sXML = Instance.serializeUsingDefaults(orderRequest.OrderData);
          chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
      }
      if (String.equals(chkRes, "true")) {
          boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
          if (isActResub) {
              IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
          }
          Events.OMConsumers.OMXFM.Request.CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO reqEvent =
              Event.createEvent("xslt://{{.../CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO}}"
                /* [XSLT builds ChangeCustomerBillingCycleInfoRequest — see §9.8 for payload] */
              );
          Event.assertEvent(reqEvent);
          IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
          Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{Logger}}...")); // audit
          IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
          orderCurrentActivity.Status = GetActivityStatusString("1", false);
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

## §19 — Response Message Rule

### §19.1 Overview

Parses CCBS response into `CCBS_ChangeCustomerBillingCycleInfoRes`, performs fan-in check, returns "true" if all requests succeeded.

### §19.2 Scope Variables

| Variable | Type Path | Role |
|----------|-----------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Master order request |
| eventResponse | Events.OMConsumers.OMXFM.Response.CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO | Raw CCBS response |
| currActivity | Concepts.OM.ProcessConfig.Activity | Current activity |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId           ← $sysNanoTimeValue                         [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode               [Always — no xsl:if]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg                [Always — no xsl:if]
    ├── CompletionStatus ← $eventResponse/CompletionStatus           [Always — no xsl:if]
    └── ReferenceId      ← $eventResponse/RefID                      [Always — no xsl:if]
```

### §19.4 Response Completion Logic

| Expression | Result |
|-----------|--------|
| `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` | Count of successful responses |
| `currActivity.RequestCount == successResponseCount` | "true" = ALL done; "false" = still waiting |

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| OPERATION_NAME | "CCBS_CHANGE_CUSTOMER_BILLING_CYCLE_INFO" |
| AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` |
| PROCESS_ID | concat($sysNanoTimeValue, "_RES") |

### §19.6 Response XSLT Source

```xml
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:param name="sysNanoTimeValue"/>
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId"><xsl:value-of select="$sysNanoTimeValue"/></xsl:attribute>
        <ResponseCode><xsl:value-of select="$eventResponse/ResponseCode"/></ResponseCode>
        <ResponseMessage><xsl:value-of select="$eventResponse/ResponseMsg"/></ResponseMessage>
        <CompletionStatus><xsl:value-of select="$eventResponse/CompletionStatus"/></CompletionStatus>
        <ReferenceId><xsl:value-of select="$eventResponse/RefID"/></ReferenceId>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
