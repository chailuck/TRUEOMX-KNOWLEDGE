# Request_MVP_CHECK_DEVICES

> Checks whether each subscriber's device supports 5G via MVP (Mobile Value Platform). Fan-out per subscriber (POU + COU), populates `5G_DEVICE=Y/N` ExtendedInfo flag in working memory.

## §1 — Overview & Purpose

This rule fires when the order orchestrator reaches the `MVP_CHECK_DEVICES` activity. It sends a `MvpCheckDevicesRequest` to the MVP (Mobile Value Platform) system for each subscriber, asking whether the device is 5G-capable.

The response handler reads `MvpCheckDevicesResponse/device` — if it equals `"5G"`, a `SubscriberExtendedInfo` concept with `Name="5G_DEVICE", Value="Y"` is written; otherwise `Value="N"`. Downstream rules use this flag to gate 5G-specific offer provisioning.

> **Business Purpose:** Before removing or adding offers, determine if the subscriber's handset is 5G-capable. Enables conditional offer routing — e.g., skip 5G SA offer provisioning for non-5G devices.

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_MVP_CHECK_DEVICES` |
| Priority | 5 |
| Forward Chain | true |
| Rule Type | Request dispatcher with fan-out loop |
| Author | Chayatorn Pan. |
| Activity ID | MVP_CHECK_DEVICES |
| Backend System | MVP — Mobile Value Platform (`MvpCheckDevices.xsd`) |

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `/Concepts/OrderRequest/OrderRequest` | Master order — customer hierarchy, order metadata |
| `orderCurrentActivity` | `/Concepts/OM/ProcessConfig/Activity` | Tracks RequestCount, Response[], Status |

## §4 — Rule Conditions (WHEN)

| # | Condition | Meaning |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance matches current next activity |
| 2 | `orderCurrentActivity.ActivityID == "MVP_CHECK_DEVICES"` | Activity type is this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "MVP_CHECK_DEVICES"` | Process flow pointer matches (dual-check) |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity is in WAITING state |

## §5 — Execution Flow Diagram

1. Resub check → `isActResub = RequestCount > 0 && IsOrderResubmitted`
2. Load nextAct → `Instance.getByExtIdByUri(NextActivityName, Activity)` for PreExecCheck
3. POU Subscriber loop (i, j) → success-check; PreExecCheck; send `MVP_CHECK_DEVICES` event; log audit; increment RequestCount
4. COU Subscriber loop (i, p, q) → same pattern; identical XSLT with subscriber concept passed directly
5. Status update → REQUESTING ("1") + `SendDataToDB()` or `SkipActivity("4")`
6. Exception → `HandleActivityException()`

> **Key difference:** Both POU and COU loops use the **same XSLT template** — the subscriber concept object is passed as `$subscriber` directly (no index-based path). Event extId is generated via `OMXUtils:generateTrackingID()`.

## §6 — Rule Action (THEN) — Step-by-Step Logic

| Step | Code Action | Detail |
|------|-------------|--------|
| 1 | Resub detection | `isActResub = (RequestCount>0 && IsOrderResubmitted)` |
| 2 | Load nextAct | `Instance.getByExtIdByUri(NextActivityName, Activity)` |
| 3 | POU loop (i, j) | Success-check; PreExecCheck; send Variant (shared XSLT); increment RequestCount |
| 4 | COU loop (i, p, q) | Same; subscriber concept passed as `$subscriber` param |
| 5 | Status → REQUESTING | `GetActivityStatusString("1", false)` + `SendDataToDB()` |
| 6 | Skip path | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| 7 | Exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Fires for postpaid orders with `MVP_CHECK_DEVICES` in the ProcessConfig — including **POSTPAID_REMOVE_OFFER_SUB**. Determines 5G device capability before offer manipulation.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel URI | Destination | Protocol | Purpose |
|-----------|------------|-------------|----------|---------|
| [OUTBOUND] | `/Channels/OMXFMConnectionRequest` | `MVP_CHECK_DEVICES` | JMS | Send MvpCheckDevicesRequest to MVP |
| [INBOUND] | `/Channels/OMXFMConnectionResponse` | `MVP_CHECK_DEVICES` | JMS | Receive MvpCheckDevicesResponse from MVP |
| [OUTBOUND] | Logger channel | OMXESB Logger | JMS | Audit log (request + response) |

### §8.3 Backend API Details

| System | Operation | Request Schema | Response Schema | Namespace |
|--------|-----------|---------------|-----------------|-----------|
| **MVP** | MvpCheckDevices | `CheckDevices.xsd` (`MvpCheckDevicesRequest`) | `MvpCheckDevicesResponse` | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MVP/MvpCheckDevices.xsd` |

### §8.4 BE Working Memory Dependencies

| Field | Access | Purpose |
|-------|--------|---------|
| `orderRequest.OrderData.Customer.ParentOU[].Subscriber[]` | READ | POU subscriber fan-out |
| `orderRequest.OrderData.Customer.ParentOU[].ChildOU[].Subscriber[]` | READ | COU subscriber fan-out |
| `subscriber.MSISDN` | READ | Passed as `$subscriber` XSLT param |
| `subscriber.ExtendedInfo[]` | WRITE (response) | Appended with `5G_DEVICE=Y/N` |
| `orderCurrentActivity.Response[]` | READ/WRITE | Fan-in tracking |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-in counter |
| `orderCurrentActivity.Status` | WRITE | REQUESTING or SKIPPED |

### §8.5 ExtendedInfo Fields Written (Response)

| Concept | Name | Value | Condition |
|---------|------|-------|-----------|
| `SubscriberExtendedInfo` | `5G_DEVICE` | `"Y"` | If `MvpCheckDevicesResponse/device = "5G"` |
| `SubscriberExtendedInfo` | `5G_DEVICE` | `"N"` | Otherwise (default) |

### §8.6 Global Variable Dependencies

| Global Variable Path | Used For |
|---------------------|---------|
| `OMX_COMMON/_SharedResources/Common/Log/OrderTypeFilter` | Suppress logging for filtered order types |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `OMX_OM/WritePayload` | Payload inclusion gate |

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

Both POU and COU variants use the **same XSLT template** with params: `orderRequest`, `refId`, `subscriber`.

| Parameter | Source |
|-----------|--------|
| `$orderRequest` | orderRequest concept |
| `$refId` | `subscriber.RefId` |
| `$subscriber` | Subscriber concept object (resolved in BE loop — POU or COU) |

### §9.2 Event Container Construction

- Event type: `/Events/OMConsumers/OMXFM/Request/MVP_CHECK_DEVICES`
- Extends: `/Events/Base/OMXRequestBaseEvent`
- Channel: `/Channels/OMXFMConnectionRequest` → destination `MVP_CHECK_DEVICES`
- **extId:** generated via `OMXUtils:generateTrackingID()` (unique per event instance)

### §9.3 JMS / Event Header Fields

| Field | Source | Notes |
|-------|--------|-------|
| `extId` (attribute) | `OMXUtils:generateTrackingID()` | Unique event ID |
| `JMSPriority` | `$orderRequest/OrderPriority` | |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Order correlation |
| `OrderID` | `$orderRequest/OrderData/OrderID` | |
| `RefID` | `$refId` (subscriber.RefId) | Fan-in matching key |
| `OrderType` | `$orderRequest/OrderData/OrderType` | |

### §9.6 Core Payload Fields

| XML Element | Source | Notes |
|-------------|--------|-------|
| `ns:MvpCheckDevicesRequest/ns:transaction_id` | `$orderRequest/OrderData/OMXTrackingId` | Transaction correlation in MVP |
| `ns:MvpCheckDevicesRequest/ns:channel` | `"omx"` (static) | Always "omx" |
| `ns:MvpCheckDevicesRequest/ns:msisdn` | `$subscriber/MSISDN` | Subscriber's mobile number |
| `ns:MvpCheckDevicesRequest/ns:check_current_soc` | `"no"` (static) | Device check only — do not check SOC |

### §9.7 Complete Generated XML Example

```xml
<createEvent extId="OMX-GEN-UUID-001">
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20260813-001</JMSCorrelationID>
    <OrderID>ORD-20260813-99001</OrderID>
    <RefID>SUB-REF-001</RefID>
    <OrderType>POSTPAID_REMOVE_OFFER_SUB</OrderType>
    <payload>
      <ns:MvpCheckDevicesRequest xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MVP/MvpCheckDevices.xsd">
        <ns:transaction_id>OMX-TRK-20260813-001</ns:transaction_id>
        <ns:channel>omx</ns:channel>
        <ns:msisdn>0812345678</ns:msisdn>
        <ns:check_current_soc>no</ns:check_current_soc>
      </ns:MvpCheckDevicesRequest>
    </payload>
  </event>
</createEvent>
```

### §9.8 XSLT Stylesheet Source

Both POU and COU variants use the same XSLT:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet
    xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MVP/MvpCheckDevices.xsd"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    version="1.0" exclude-result-prefixes="OMXUtils xsl ns xsd">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>   <!-- bound from orderRequest concept -->
  <xsl:param name="refId"/>          <!-- subscriber.RefId -->
  <xsl:param name="subscriber"/>     <!-- Subscriber concept (POU or COU) -->
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <RefID><xsl:value-of select="$refId"/></RefID>
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        <payload>
          <ns:MvpCheckDevicesRequest>
            <ns:transaction_id><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></ns:transaction_id>
            <ns:channel><xsl:value-of select="'omx'"/></ns:channel>
            <ns:msisdn><xsl:value-of select="$subscriber/MSISDN"/></ns:msisdn>
            <ns:check_current_soc><xsl:value-of select="'no'"/></ns:check_current_soc>
          </ns:MvpCheckDevicesRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent @extId       ← OMXUtils:generateTrackingID()               [Always]
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority              [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId    [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID          [Always]
    ├── RefID                ← $refId (subscriber.RefId)                [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType        [Always]
    └── payload
        └── ns:MvpCheckDevicesRequest
            ├── ns:transaction_id    ← $orderRequest/OrderData/OMXTrackingId  [Always]
            ├── ns:channel           ← "omx"  (static)                        [Always]
            ├── ns:msisdn            ← $subscriber/MSISDN                     [Always]
            └── ns:check_current_soc ← "no"  (static)                        [Always]
```

**Legend:** `[Always]` = unconditionally present

## §11 — Audit Logging

| Field | Request Value | Response Value |
|-------|--------------|----------------|
| `ESBUUID` | OMXTrackingId (conditional) | OMXTrackingId (conditional) |
| `PROCESS_ID` | `concat($pid,"_REQ")` | `concat($pid,"_RES")` |
| `OPERATION_NAME` | `"MVP_CHECK_DEVICES"` | `"MVP_CHECK_DEVICES"` |
| `AUDIT_TRACE` | `"Request Sent for MVP_CHECK_DEVICES"` | `concat("Response received for RefId ", $eventResponse/RefID)` |
| `LOG_LEVEL` | INFO | INFO |
| `payload/ns:ServicePayload` | Gated on `WritePayload="true"` | Gated on `WritePayload="true"` |

> Response audit log is **always written** — no `AllowWriteLog` gate in the response handler.

## §12 — Activity Status Management

| Status Code | Meaning | Trigger |
|-------------|---------|---------|
| `"1"` → REQUESTING | Requests dispatched, awaiting MVP responses | After any request sent |
| `"4"` → SKIPPED | All subscribers skipped | `isSkipped` remains true |

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

## §14 — Helper Functions Reference

| Function | Signature | Purpose |
|----------|-----------|---------|
| `AllowWriteLog` | `boolean(String orderType)` | Suppress log for filtered order types |
| `GetXMLForSubscriber` | `String(orderRequest, refId)` | Serialise POU subscriber for PreExecCheck |
| `GetXMLForSubscriberInChildOU` | `String(orderRequest, refId, pouRefId)` | Serialise COU subscriber for PreExecCheck |
| `GetActivityStatusString` | `String(code, bool)` | Map status code to string |
| `SendDataToDB` | `void(orderRequest)` | Persist order state |
| `SkipActivity` | `void(orderRequest, activity, code)` | Skip and advance |
| `HandleActivityException` | `void(orderRequest, activity, ex, msg)` | Error handling |
| `OMXUtils.generateTrackingID` | `String()` | Generate unique event extId and ResponseBase extId |

## §15 — Function Dependency Tree

```text
Request_MVP_CHECK_DEVICES (rule)
├── RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)              [POU PreExecCheck]
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)  [COU PreExecCheck]
├── XPath.execute(expression, xml, namespace)
├── OMXUtils.generateTrackingID()                                               [event extId]
├── Event.createEvent("xslt://MVP_CHECK_DEVICES")                              [shared POU+COU XSLT]
├── Event.Ext.sendEventImmediate(reqEvent)
├── RuleFunctions.Helpers.AllowWriteLog(orderType)
│   └── System.getGlobalVariableAsString("OMX_COMMON/.../OrderTypeFilter")
├── Event.createEvent("xslt://Logger")
├── Event.Ext.sendEventImmediate(logEvent)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")
└── RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")
```

## §16 — Concept Definitions Referenced

| Concept | Path | Key Properties |
|---------|------|---------------|
| `OrderRequest` | `/Concepts/OrderRequest/OrderRequest` | OrderData, ProcessFlow, IsOrderResubmitted |
| `Activity` | `/Concepts/OM/ProcessConfig/Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck |
| `Subscriber` | `/Concepts/OrderRequest/OrderElements/Subscriber` | MSISDN, RefId, ExtendedInfo[] |
| `SubscriberExtendedInfo` | `/Concepts/OrderRequest/OrderElements/ExtendedInfos/SubscriberExtendedInfo` | Name (`5G_DEVICE`), Value (`Y`/`N`) |
| `ResponseBase` | `/Concepts/FM/Base/ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Query MVP to determine if each subscriber's device supports 5G |
| R2 | Fan-out to ALL subscribers (POU + COU) with identical request |
| R3 | Store result as `SubscriberExtendedInfo[5G_DEVICE=Y/N]` per subscriber |
| R4 | Skip subscribers that already have a successful response |
| R5 | Fan-in: complete when `RequestCount == successResponseCount` (ResponseCode suffix "000") |
| R6 | `channel="omx"` and `check_current_soc="no"` are hardcoded — cannot be configured per-order |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Hardcoded `channel="omx"` | [MEDIUM] | If MVP requires different channel IDs per env, needs parameterisation |
| Hardcoded `check_current_soc="no"` | [LOW] | Intentional — device check only. Document assumption explicitly in migration. |
| Response audit always logs (no AllowWriteLog gate) | [LOW] | Minor performance impact for high-volume order types |
| 5G_DEVICE flag case-sensitive match | [MEDIUM] | `= "5G"` is exact. Any MVP response returning "5g" or "5G SA" sets flag to "N". |

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_MVP_CHECK_DEVICES {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "MVP_CHECK_DEVICES";
    orderRequest.ProcessFlow.NextActivityID == "MVP_CHECK_DEVICES";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
    try {
      Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
      // ParentOU loop
      for (int i=0; i<iPOULen; i++) {
        for (int j=0; j<iSubscriberLen; j++) {
          Concepts.OrderRequest.OrderElements.Subscriber subscriber = ...ParentOU[i].Subscriber[j];
          // [success-check, PreExecCheck omitted for brevity]
          Events.OMConsumers.OMXFM.Request.MVP_CHECK_DEVICES reqEvent = Event.createEvent(
            /* xslt://MVP_CHECK_DEVICES — see §9.8 for full XSLT
               params: orderRequest, refId, subscriber
               Outputs: extId(OMXUtils:generateTrackingID), JMSPriority, JMSCorrelationID,
                        OrderID, RefID, OrderType,
                        payload/ns:MvpCheckDevicesRequest{ns:transaction_id, ns:channel="omx",
                        ns:msisdn=$subscriber/MSISDN, ns:check_current_soc="no"} */);
          Event.Ext.sendEventImmediate(reqEvent);
          if (RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
            Event.Ext.sendEventImmediate(Event.createEvent(/* Logger XSLT */));
          }
          if (!isActResub) orderCurrentActivity.RequestCount++;
          isSkipped = false;
        }
        // COU loop (p, q) — same XSLT, subscriber passed as concept param
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

## §19 — Response Message Rule

### §19.1 Overview

`Response_MVP_CHECK_DEVICES` receives `MvpCheckDevicesResponse` from MVP. Appends ResponseBase; iterates all subscribers to find matching RefID; creates `SubscriberExtendedInfo[5G_DEVICE=Y/N]`; logs audit; returns fan-in completion.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `/Concepts/OrderRequest/OrderRequest` | Master order |
| `eventResponse` | `/Events/OMConsumers/OMXFM/Response/MVP_CHECK_DEVICES` | MVP response — ResponseCode, RefID, payload |
| `currActivity` | `/Concepts/OM/ProcessConfig/Activity` | Fan-in tracking |

### §19.3 ResponseBase Concept Construction

extId = `OMXUtils.generateTrackingID()`

```text
createObject
└── object @extId ← $extId (OMXUtils:generateTrackingID())    [Always]
    ├── ResponseCode       ← $eventResponse/ResponseCode       [Conditional: if $eventResponse/ResponseCode]
    ├── ResponseMessage    ← $eventResponse/ResponseMsg        [Conditional: if $eventResponse/ResponseMsg]
    ├── CompletionStatus   ← $eventResponse/CompletionStatus   [Conditional: if $eventResponse/CompletionStatus]
    └── ReferenceId        ← $eventResponse/RefID             [Conditional: if $eventResponse/RefID]
```

### §19.4 5G Device Flag Population

```java
// Find subscriber matching RefID (searches POU and COU)
if (subscriber.RefId == eventResponse.RefID) {
    // Create SubscriberExtendedInfo:
    //   Name = "5G_DEVICE"
    //   Value = "Y" if MvpCheckDevicesResponse/device = "5G"
    //   Value = "N" otherwise
    subscriber.ExtendedInfo[subscriber.ExtendedInfo@length] = subscriberExtendedInfo;
}
```

### §19.5 Response Completion Logic

| Check | Expression | Meaning |
|-------|-----------|---------|
| Success count | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` | Counts ResponseCode ending "000" |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` | All successful responses received |
| Return "true" | RequestCount == successResponseCount | Advance to next activity |
| Return "false" | Still waiting | Keep activity in REQUESTING state |

### §19.6 Response XSLT Source (SubscriberExtendedInfo)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MVP/MvpCheckDevices.xsd"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    version="1.0" exclude-result-prefixes="OMXUtils xsl ns xsd">
  <xsl:output method="xml"/>
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <Name><xsl:value-of select="'5G_DEVICE'"/></Name>
        <xsl:choose>
          <xsl:when test="$eventResponse/payload/ns:MvpCheckDevicesResponse/ns:device = '5G'">
            <Value><xsl:value-of select="'Y'"/></Value>
          </xsl:when>
          <xsl:otherwise>
            <Value><xsl:value-of select="'N'"/></Value>
          </xsl:otherwise>
        </xsl:choose>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
