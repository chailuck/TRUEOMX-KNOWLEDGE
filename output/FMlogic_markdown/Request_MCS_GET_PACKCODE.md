# Request_MCS_GET_PACKCODE

> TIBCO BusinessEvents · FM Logic Documentation · Backend: MCS (Subscription Management)

---

## §1 — Overview & Purpose

**Request_MCS_GET_PACKCODE** queries the MCS (subscription management) system for a subscriber's current active pack code / subscription information. The primary purpose is to determine whether the subscriber holds an active after-sale service subscription (MCS_CANCEL_AFS) that may need to be cancelled during offer removal.

For each eligible subscriber, the rule dispatches a `GetPackCodeRequest` event to MCS. The response handler inspects the returned subscription data and — if a valid subscription record exists — sets an `ExtendedInfo[MCS_CANCEL_AFS]=Y` flag on the subscriber. This flag is typically used as a gate by the subsequent **MCS_CANCEL_AFTER_SALE** FM.

> **Design note:** The rule correctly implements both POU (ParentOU) and COU (ChildOU) subscriber loops. Resubmit-skip logic compares `Response[].ReferenceId` to `subscriber.RefId`, which correctly matches the echoed `RefID` in the response. No fan-in bugs observed — this FM is a clean implementation.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_MCS_GET_PACKCODE` | Full qualified path |
| Priority | `5` | Standard FM priority |
| Forward chain | `true` | Rule re-evaluates after THEN actions |
| Rule type | Request Dispatcher | Sends outbound event to MCS; awaits response via separate rulefunction |
| Author | Chayatorn Pan. | From file header comment |
| Backend system | MCS | Subscription management |
| Dispatch pattern | `Event.Ext.sendEventImmediate` | Parallel fan-out; no IntraActivitySequencing |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order context; contains Customer → ParentOU/ChildOU → Subscriber hierarchy |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity configuration; holds RequestCount, Response array, Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition Expression | Purpose |
|---|---------------------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Binds activity to the current order's next activity slot |
| 2 | `orderCurrentActivity.ActivityID == "MCS_GET_PACKCODE"` | Restricts rule to MCS_GET_PACKCODE activity type |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "MCS_GET_PACKCODE"` | Double-checks order flow pointer matches this FM |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires when activity is in WAITING state |

---

## §5 — Execution Flow Diagram

```
1. Compute isActResub = (RequestCount > 0 && IsOrderResubmitted)
2. Resolve nextAct by extId to access PreExecCheck XPath string
3. ParentOU subscriber loop:
   ├── 3a. Check resubmit-skip (Response[].ReferenceId == refId && CompletionStatus==2)
   ├── 3b. Evaluate PreExecCheck (GetXMLForSubscriber + XPath.execute)
   ├── 3c. Build and dispatch MCS_GET_PACKCODE event (sendEventImmediate)
   ├── 3d. Send audit logger event (_REQ suffix)
   └── 3e. Increment RequestCount if !isActResub
4. ChildOU subscriber loop → identical to step 3 using GetXMLForSubscriberInChildOU
5. If any dispatch occurred: set Status = GetActivityStatusString("1", false); SendDataToDB
   Else: SkipActivity(…, "4")
6. catch: HandleActivityException
```

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

**Resubmit flag computation:**

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
```

**Per-subscriber dispatch logic (POU branch; COU is identical):**

```java
// Resubmit skip: if a successful response already received, skip re-dispatch
boolean reqSuccess = false;
for (int iResp = 0; iResp < orderCurrentActivity.Response@length; iResp++)
    if (String.equals(orderCurrentActivity.Response[iResp].ReferenceId, refId)
        && orderCurrentActivity.Response[iResp].CompletionStatus == 2)
        reqSuccess = true;

if (!reqSuccess) {
    // PreExecCheck gate
    String chkRes = "true";
    if (String.length(nextAct.PreExecCheck) > 0) {
        String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId);
        chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
    }
    if (String.equals(chkRes, "true")) {
        // Build and dispatch MCS_GET_PACKCODE event (XSLT — see §9.8)
        Events.OMConsumers.OMXFM.Request.MCS_GET_PACKCODE reqEvent = Event.createEvent("xslt://...");
        Event.Ext.sendEventImmediate(reqEvent);
        long pid = System.nanoTime();
        Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{/Events/OMConsumers/OMXESB/Logger}}..."));
        if (!isActResub) orderCurrentActivity.RequestCount++;
        isSkipped = false;
    }
}
```

> **Resubmit-skip pattern:** `CompletionStatus==2` is checked (not just ReferenceId). Only a fully-complete response skips re-dispatch.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

This FM is used in **POSTPAID_REMOVE_OFFER_SUB** and similar postpaid offer-removal flows. It runs after TDG_CANCEL_SUBSCRIBER and before MCS_CANCEL_AFTER_SALE.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Channel / Destination | Protocol | Purpose |
|-----------|-----------|----------------------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.MCS_GET_PACKCODE` | MCS JMS channel / MCS_GET_PACKCODE destination | JMS / TIBCO EMS | Dispatch GetPackCode query to MCS per subscriber |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.MCS_GET_PACKCODE` | MCS response channel | JMS / TIBCO EMS | Receive GetPackCode response (subscription data) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Audit log channel | JMS | Request/response audit trail |

### §8.3 — Backend API Details

| System | Operation | Schema | Request Element | Correlation |
|--------|-----------|--------|-----------------|-------------|
| MCS | GetPackCode | `MCS/CancelSubscription.xsd` (shared schema) | `ns:GetPackCodeRequest` | `RefID` ← `subscriber.RefId` |

> **Note:** The schema namespace references `CancelSubscription.xsd` — MCS reuses this schema file for multiple operations including GetPackCode and CancelSubscription endpoints.

### §8.4 — BE Working Memory Dependencies

| Field | Access | Purpose |
|-------|--------|---------|
| `orderRequest.OrderData.OMXTrackingId` | READ | Audit UUID + correlation_id |
| `orderRequest.OrderData.OrderID` | READ | Event header OrderID |
| `orderRequest.OrderData.OrderType` | READ | Event header OrderType |
| `orderRequest.OrderPriority` | READ | JMSPriority |
| `orderRequest.IsOrderResubmitted` | READ | Resubmit flag |
| `subscriber.RefId` | READ | Correlation key; echoed back as RefID |
| `subscriber.MSISDN` | READ | Payload: ns:service_no |
| `subscriber.ExtendedInfo` | WRITE (response) | Append MCS_CANCEL_AFS=Y if subscription found |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-out counter |
| `orderCurrentActivity.Response` | READ/WRITE (response) | Array of ResponseBase results |
| `orderCurrentActivity.Status` | WRITE | Set to SENT after dispatch |

### §8.5 — ExtendedInfo Fields Required (Request)

No ExtendedInfo fields are read from the subscriber as request input. The response handler *writes* `MCS_CANCEL_AFS=Y` to `subscriber.ExtendedInfo` if a subscription is found.

### §8.6 — Global Variable Dependencies

| Variable Path | Used In | Purpose |
|--------------|---------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit logger | COMPONENT_NAME field |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit logger | TARGET_SYSTEM field |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit logger | LOG_LEVEL value |
| `$globalVariables/OMX_OM/WritePayload` | Audit logger | Gates payload inclusion in audit log |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Role |
|-----------|-----------|------|
| `$orderRequest` | BE concept `orderRequest` | Root order data |
| `$refId` | `subscriber.RefId` | Correlation key / RefID |
| `$subscriber` | BE concept `subscriber` | Subscriber data (MSISDN) |

### §9.2 — Event Container Construction

| Field | Source | Notes |
|-------|--------|-------|
| `event @extId` | `OMXUtils:generateTrackingID()` | Unique event correlation ID — correct pattern |

### §9.3 — JMS / Event Header Fields

| Field | Source XPath | Condition |
|-------|-------------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$refId` (= `subscriber.RefId`) | Always — echoed back by MCS for fan-in matching |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Always |

### §9.4 — Payload Root Element

`payload / ns:GetPackCodeRequest` — namespace: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/CancelSubscription.xsd`

### §9.5 — Conditional Fields (xsl:if)

| Field | Condition | Source |
|-------|-----------|--------|
| `ns:correlation_id` | `$orderRequest/OrderData/OMXTrackingId` exists | `$orderRequest/OrderData/OMXTrackingId` |
| `ns:service_no` | `$subscriber/MSISDN` exists | `$subscriber/MSISDN` |

### §9.7 — Complete Generated XML Example

```xml
<createEvent>
  <event extId="OMX-TRK-20240801-001">
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20240801-001</JMSCorrelationID>
    <OrderID>ORD-9001</OrderID>
    <RefID>SUB-REF-001</RefID>
    <OrderType>POSTPAID_REMOVE_OFFER_SUB</OrderType>
    <payload>
      <ns:GetPackCodeRequest
        xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/CancelSubscription.xsd">
        <ns:correlation_id>OMX-TRK-20240801-001</ns:correlation_id>
        <ns:service_no>0812345678</ns:service_no>
      </ns:GetPackCodeRequest>
    </payload>
  </event>
</createEvent>
```

### §9.8 — XSLT Stylesheet Source

**Variant ① — ParentOU & ChildOU (identical XSLT)**

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/CancelSubscription.xsd"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  version="1.0" exclude-result-prefixes="OMXUtils xsl xsd">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>   <!-- BE concept: root order -->
  <xsl:param name="refId"/>          <!-- subscriber.RefId (correlation key) -->
  <xsl:param name="subscriber"/>     <!-- BE concept: subscriber -->
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <JMSPriority>
          <xsl:value-of select="$orderRequest/OrderPriority"/>
        </JMSPriority>
        <JMSCorrelationID>
          <xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/>
        </JMSCorrelationID>
        <OrderID>
          <xsl:value-of select="$orderRequest/OrderData/OrderID"/>
        </OrderID>
        <RefID>
          <xsl:value-of select="$refId"/>
        </RefID>
        <OrderType>
          <xsl:value-of select="$orderRequest/OrderData/OrderType"/>
        </OrderType>
        <payload>
          <ns:GetPackCodeRequest>
            <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
              <ns:correlation_id>
                <xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/>
              </ns:correlation_id>
            </xsl:if>
            <xsl:if test="$subscriber/MSISDN">
              <ns:service_no>
                <xsl:value-of select="$subscriber/MSISDN"/>
              </ns:service_no>
            </xsl:if>
          </ns:GetPackCodeRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

The POU and COU variants use identical XSLT; the only difference is the BE-side loop variable (`GetXMLForSubscriber` vs `GetXMLForSubscriberInChildOU`) used for PreExecCheck.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event @extId ← OMXUtils:generateTrackingID()                           [Always]
    ├── JMSPriority       ← $orderRequest/OrderPriority                    [Always]
    ├── JMSCorrelationID  ← $orderRequest/OrderData/OMXTrackingId          [Always]
    ├── OrderID           ← $orderRequest/OrderData/OrderID                [Always]
    ├── RefID             ← $refId (= subscriber.RefId)                    [Always]
    ├── OrderType         ← $orderRequest/OrderData/OrderType              [Always]
    └── payload
        └── ns:GetPackCodeRequest
            ├── ns:correlation_id ← $orderRequest/OrderData/OMXTrackingId [Conditional: if $orderRequest/OrderData/OMXTrackingId]
            └── ns:service_no     ← $subscriber/MSISDN                    [Conditional: if $subscriber/MSISDN]
```

Legend: `[Always]` = no xsl:if guard · `[Conditional: ...]` = inside xsl:if test

---

## §11 — Audit Logging

| Phase | Event | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE |
|-------|-------|-----------|----------------|-------------|
| [REQUEST] | `Events.OMConsumers.OMXESB.Logger` | `concat(nanoTime(), "_REQ")` | `"MCS_GET_PACKCODE"` | `"Request Sent for MCS_GET_PACKCODE"` |
| [RESPONSE] | `Events.OMConsumers.OMXESB.Logger` | `concat(nanoTime(), "_RES")` | `"MCS_GET_PACKCODE"` | `concat("Response received for RefId ", $eventResponse/RefID)` |

Both POU and COU dispatches emit audit logger events. Payload conditionally included when `WritePayload="true"`. Audit logger operation names correctly say `MCS_GET_PACKCODE` — no copy-paste bug.

---

## §12 — Activity Status Management

| Scenario | Status Code | Function Call | Meaning |
|----------|-------------|--------------|---------|
| At least one dispatch sent | `"1"` | `GetActivityStatusString("1", false)` | SENT / In Progress |
| All subscribers skipped | `"4"` | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | SKIPPED |

After any dispatch, `SendDataToDB(orderRequest)` persists the updated order state.

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

Any exception is caught and delegated to `HandleActivityException`, which logs the error, sets the activity to an error state, and typically halts the order flow.

---

## §14 — Helper Functions Reference

| Function | Return Type | Purpose |
|---------|------------|---------|
| `RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)` | String | Serialises subscriber data to XML for PreExecCheck (POU path) |
| `RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` | String | Serialises COU subscriber data for PreExecCheck |
| `RuleFunctions.Helpers.GetActivityStatusString("1", false)` | String | Returns activity status string for SENT state |
| `RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")` | void | Marks activity as skipped and advances flow |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | void | Persists order state after dispatch |
| `RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")` | void | Handles exception; sets error state |

---

## §15 — Function Dependency Tree

```text
Request_MCS_GET_PACKCODE (rule)
├── RuleFunctions.Helpers.GetXMLForSubscriber          [POU PreExecCheck serialisation]
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU [COU PreExecCheck serialisation]
├── XPath.execute                                       [PreExecCheck evaluation]
├── OMXUtils:generateTrackingID()                      [event @extId — inside XSLT]
├── Event.Ext.sendEventImmediate                       [x2: reqEvent + logger per subscriber]
├── RuleFunctions.Helpers.GetActivityStatusString      [status "1"]
├── RuleFunctions.Helpers.SendDataToDB                 [DB persistence]
├── RuleFunctions.Helpers.SkipActivity                 [skip path]
└── RuleFunctions.Helpers.HandleActivityException      [error handling]

Response_MCS_GET_PACKCODE (rulefunction)
├── OMXUtils.generateTrackingID()                      [ResponseBase extId]
├── Instance.createInstance (ResponseBase XSLT)        [construct response record]
├── XPath.evalAsBoolean                                [existSubscription check]
├── Instance.createInstance (SubscriberExtendedInfo)   [create MCS_CANCEL_AFS flag]
├── OMXUtils:generateTrackingID()                      [ExtendedInfo @extId — inside XSLT]
├── XPath.evalAsInt                                    [fan-in count: successResponseCount]
├── Event.Ext.sendEventImmediate                       [response audit logger]
└── [return "true" / "false"]                          [fan-in completion signal]
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Fields Used | Role |
|---------|----------------|------|
| `Concepts.OrderRequest.OrderRequest` | OrderData, OrderPriority, IsOrderResubmitted, ProcessFlow | Root order context |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck | Current activity state |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, ExtendedInfo[] | Per-subscriber data and output target |
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId | Normalised response record |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` | Name, Value | Key-value flag: MCS_CANCEL_AFS=Y |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement | Source Evidence |
|----|------------|-----------------|
| R1 | Call MCS GetPackCode API per subscriber with MSISDN and correlation_id | XSLT: `ns:GetPackCodeRequest` |
| R2 | Support both POU and COU subscriber structures in fan-out dispatch | Rule: dual ParentOU/ChildOU loops |
| R3 | If MCS returns a subscription record (`subscription_id` non-empty), set `subscriber.ExtendedInfo[MCS_CANCEL_AFS]=Y` | Response: `existSubscription` check |
| R4 | Skip re-dispatch for subscribers already successfully responded (`CompletionStatus==2`) | Rule: `reqSuccess` check |
| R5 | Gate dispatch on activity PreExecCheck XPath if configured | Rule: `chkRes = XPath.execute(...)` |
| R6 | Fan-in: advance only when all dispatched requests return success (ResponseCode ends in "000") | Response: `RequestCount == successResponseCount` |
| R7 | Emit audit log events for both request (`_REQ`) and response (`_RES`) | Rule + Response: Logger XSLT |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Commented-out `SubscriberOffers` injection code in response rulefunction — abandoned feature that would have added ServiceType=69, FE_OR_CCBS=FE | [MEDIUM] | Remove dead code before migration; if needed, design as explicit config |
| MCS `CancelSubscription.xsd` schema namespace shared between GetPackCode and CancelSubscription operations — schema change may have unintended side effects | [LOW] | Use operation-specific schema files in modern API contracts |
| `existSubscription` checks only `subscription[1]/subscription_id` — if MCS returns multiple subscriptions, only the first is evaluated | [LOW] | Clarify with MCS team; extend check if multiple subscriptions are possible |

### Modernisation Recommendations

- Replace JMS fan-out with async REST/gRPC calls with per-subscriber correlation IDs
- Move fan-in completion logic to an orchestration layer (saga pattern)
- Remove commented-out `SubscriberOffers` code or promote to a proper feature flag
- Define operation-specific API schemas for GetPackCode to decouple from CancelSubscription schema

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author Chayatorn Pan.
 */
rule Rules.OMConsumers.OMXFM.Request.Request_MCS_GET_PACKCODE {
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
        orderCurrentActivity.ActivityID == "MCS_GET_PACKCODE";
        orderRequest.ProcessFlow.NextActivityID == "MCS_GET_PACKCODE";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct =
                Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName,
                    "/Concepts/OM/ProcessConfig/Activity");
            int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
            String pouRefId = "";
            boolean isSkipped = true;

            for (int i = 0; i < iPOULen; i++) { // ParentOU loop
                pouRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;
                int iSubscriberLen = orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length;
                for (int j = 0; j < iSubscriberLen; j++) {
                    Concepts.OrderRequest.OrderElements.Subscriber subscriber =
                        orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j];
                    String refId = subscriber.RefId;
                    boolean reqSuccess = false;
                    for (int iResp = 0; iResp < orderCurrentActivity.Response@length; iResp++)
                        if (String.equals(orderCurrentActivity.Response[iResp].ReferenceId, refId)
                            && orderCurrentActivity.Response[iResp].CompletionStatus == 2)
                            reqSuccess = true;
                    if (!reqSuccess) {
                        String chkRes = "true";
                        if (String.length(nextAct.PreExecCheck) > 0) {
                            String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId);
                            String chkXPath = nextAct.PreExecCheck;
                            chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=...");
                        }
                        if (String.equals(chkRes, "true")) {
                            /* Build ns:GetPackCodeRequest event — see §9.8:
                               event @extId, JMSPriority, JMSCorrelationID, OrderID,
                               RefID, OrderType, payload/ns:GetPackCodeRequest
                               [ns:correlation_id, ns:service_no] */
                            Events.OMConsumers.OMXFM.Request.MCS_GET_PACKCODE reqEvent =
                                Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/MCS_GET_PACKCODE}}...");
                            Event.Ext.sendEventImmediate(reqEvent);
                            long pid = System.nanoTime();
                            /* Audit logger: OPERATION_NAME="MCS_GET_PACKCODE", PROCESS_ID=pid+"_REQ" */
                            Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{/Events/OMConsumers/OMXESB/Logger}}..."));
                            if (!isActResub) orderCurrentActivity.RequestCount++;
                            isSkipped = false;
                        }
                    }
                }
                // ChildOU loop — identical logic using GetXMLForSubscriberInChildOU for PreExecCheck
                int iCOULen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU@length;
                for (int p = 0; p < iCOULen; p++) {
                    iSubscriberLen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU[p].Subscriber@length;
                    for (int q = 0; q < iSubscriberLen; q++) {
                        // [identical resubmit-skip, PreExecCheck, dispatch, and audit logic]
                    }
                }
            }
            if (!isSkipped) {
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

## §19 — Response Message Rule

### §19.1 — Overview

**Response_MCS_GET_PACKCODE** is invoked when MCS returns a GetPackCode response event. It constructs a `ResponseBase` record, appends it to the activity's Response array, inspects the response payload to determine if an active subscription exists, conditionally sets `ExtendedInfo[MCS_CANCEL_AFS]=Y` on the matching subscriber, logs the response, and evaluates the fan-in completion condition.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order; provides subscriber hierarchy for RefId matching |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.MCS_GET_PACKCODE` | Inbound response event from MCS; carries RefID, ResponseCode, payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity; Response[] array appended; RequestCount used for fan-in |

### §19.3 — ResponseBase Concept Construction

> **Correct pattern:** `String extId = OMXUtils.generateTrackingID()` is declared as a Java variable and passed as the `$extId` XSLT parameter, which assigns it to `object @extId`. This correctly generates a unique extId before the concept is created. No dead-variable bug (unlike CRM FM).

```text
createObject
└── object @extId ← $extId (= OMXUtils.generateTrackingID())   [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode         [Conditional: if $eventResponse/ResponseCode]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg          [Conditional: if $eventResponse/ResponseMsg]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus     [Conditional: if $eventResponse/CompletionStatus]
    └── ReferenceId       ← $eventResponse/RefID                [Conditional: if $eventResponse/RefID]
```

### §19.4 — Response Completion Logic

**Subscription existence check:**

```xpath
count($eventResponse/payload/xsd2:GetPackCodeResponse/xsd2:subscription) > 0
and string-length($eventResponse/payload/xsd2:GetPackCodeResponse/xsd2:subscription[1]/xsd2:subscription_id) > 0
```

**If subscription exists:** creates `SubscriberExtendedInfo` with `Name='MCS_CANCEL_AFS'`, `Value='Y'` and appends to `subscriber.ExtendedInfo`.

> **[MEDIUM] Dead code:** Commented-out `SubscriberOffers` creation code follows the ExtendedInfo assignment. It would have created an offer with `OfferName = package_id` (undefined variable), `ServiceType = "69"`, `FE_OR_CCBS = "FE"`. Remove before migration.

**Fan-in success XPath:**

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

**Completion condition:**

```java
if (currActivity.RequestCount == successResponseCount) {
    return "true";   // all dispatched requests completed successfully
} else {
    return "false";  // waiting for more responses
}
```

> **Correct standard fan-in pattern.** Return `"true"` signals the BE engine to advance the order flow.

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| `PROCESS_ID` | `concat(nanoTime(), "_RES")` |
| `OPERATION_NAME` | `"MCS_GET_PACKCODE"` |
| `TARGET_SYSTEM` | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| `AUDIT_TRACE` | `concat("Response received for RefId ", $eventResponse/RefID)` |
| `payload` | Copy of `$eventResponse` — gated on `WritePayload="true"` |

### §19.6 — Response XSLT Source (ResponseBase)

```xml
<xsl:stylesheet version="1.0" exclude-result-prefixes="xsl xsd">
  <xsl:output method="xml"/>
  <xsl:param name="extId"/>              <!-- bound from Java: OMXUtils.generateTrackingID() -->
  <xsl:param name="eventResponse"/>      <!-- inbound MCS response event -->
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId">
          <xsl:value-of select="$extId"/>    <!-- correctly uses passed-in tracking ID -->
        </xsl:attribute>
        <xsl:if test="$eventResponse/ResponseCode">
          <ResponseCode>
            <xsl:value-of select="$eventResponse/ResponseCode"/>
          </ResponseCode>
        </xsl:if>
        <xsl:if test="$eventResponse/ResponseMsg">
          <ResponseMessage>
            <xsl:value-of select="$eventResponse/ResponseMsg"/>
          </ResponseMessage>
        </xsl:if>
        <xsl:if test="$eventResponse/CompletionStatus">
          <CompletionStatus>
            <xsl:value-of select="$eventResponse/CompletionStatus"/>
          </CompletionStatus>
        </xsl:if>
        <xsl:if test="$eventResponse/RefID">
          <ReferenceId>
            <xsl:value-of select="$eventResponse/RefID"/>
          </ReferenceId>
        </xsl:if>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
