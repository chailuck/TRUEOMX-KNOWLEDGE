# Request_GET_PROFILE_FROM_CCP_ALL

> Retrieves subscriber profile and active price plan information from CCP (ZTE BSS SmartBSS) for all subscribers in the order — iterates ParentOU and ChildOU hierarchy (fan-out per subscriber).

## §1 — Overview & Purpose

This rule fires when the order orchestrator reaches the `GET_PROFILE_FROM_CCP_ALL` activity. It iterates over **every subscriber** in the order — both direct subscribers of ParentOU and subscribers nested under ChildOU — and dispatches a `GetPrepaidCreditInfoRequest` to the CCP (ZTE BSS SmartBSS) system via JMS for each one that has not already responded successfully.

The response handler (`Response_GET_PROFILE_FROM_CCP_ALL`) receives the `queryUserProfileResponse` from CCP, extracts the subscriber's active price plans (`PricePlanDtoList`), and populates `SubscriberOffers` concepts in working memory — tagged with `FE_OR_CCBS=CCP` to mark them as CCP-sourced. This data is used downstream for offer validation and billing decisions.

> **Business Purpose:** Determine what offers/price plans a subscriber currently has in CCP before executing a remove-offer or add-offer order. Ensures downstream activities have accurate offer state.

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_GET_PROFILE_FROM_CCP_ALL` |
| Priority | 5 |
| Forward Chain | true |
| Rule Type | Request dispatcher with fan-out loop |
| Author | Chayatorn Pan. |
| Activity ID | GET_PROFILE_FROM_CCP_ALL |
| Backend System | CCP — ZTE BSS SmartBSS (`http://thaitrue.customization.ws.bss.zsmart.ztesoft.com`) |

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `/Concepts/OrderRequest/OrderRequest` | Master order object — contains all customer, subscriber and order metadata |
| `orderCurrentActivity` | `/Concepts/OM/ProcessConfig/Activity` | Current process config activity; tracks RequestCount, Response[], Status |

## §4 — Rule Conditions (WHEN)

| # | Condition | Meaning |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance must be the current next activity for this order |
| 2 | `orderCurrentActivity.ActivityID == "GET_PROFILE_FROM_CCP_ALL"` | Activity type must be exactly this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "GET_PROFILE_FROM_CCP_ALL"` | Order's process flow pointer must also match (dual-check) |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be in WAITING state (not already in-flight or complete) |

## §5 — Execution Flow Diagram

1. Resub check → `isActResub = RequestCount > 0 && IsOrderResubmitted` — avoid double-counting
2. Load nextAct → `Instance.getByExtIdByUri(NextActivityName, Activity)` for PreExecCheck
3. ParentOU loop (i) → iterate all ParentOU entries
4. POU Subscriber loop (j) → check if already succeeded (CompletionStatus==2); skip if yes
5. PreExecCheck eval → `GetXMLForSubscriber()` + `XPath.execute()` — skip if result ≠ "true"
6. Send request Variant ① → `GET_PROFILE_FROM_CCP` event (POU path); log audit; increment RequestCount
7. ChildOU loop (p) → for each ChildOU under ParentOU
8. COU Subscriber loop (q) → same check + PreExecCheck + send Variant ②
9. Status update → `GetActivityStatusString("1")` (REQUESTING) + `SendDataToDB()`; or `SkipActivity("4")` if all skipped
10. Exception → `HandleActivityException(orderRequest, activity, ae, "")`

## §6 — Rule Action (THEN) — Step-by-Step Logic

| Step | Code Action | Detail |
|------|-------------|--------|
| 1 | Resub detection | `isActResub = (RequestCount>0 && IsOrderResubmitted)` |
| 2 | Load activity | `Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")` |
| 3 | POU subscriber loop | Check Response[] for existing success; evaluate PreExecCheck; send event Variant ① |
| 4 | COU subscriber loop | Same pattern with 3-index path (i, p, q); send event Variant ② |
| 5 | Status REQUESTING | `orderCurrentActivity.Status = GetActivityStatusString("1", false)` |
| 6 | Persist | `SendDataToDB(orderRequest)` |
| 7 | Skip path | `SkipActivity(orderRequest, orderCurrentActivity, "4")` if all skipped |
| 8 | Exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

This FM fires for any order type that includes `GET_PROFILE_FROM_CCP_ALL` in its ProcessConfig — primarily **POSTPAID_REMOVE_OFFER_SUB** and similar postpaid offer management orders that need to inspect the subscriber's current CCP offer state before making changes.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel URI | Destination | Protocol | Purpose |
|-----------|------------|-------------|----------|---------|
| [OUTBOUND] | `/Channels/OMXFMConnectionRequest` | `GET_PROFILE_FROM_CCP` | JMS | Send GetPrepaidCreditInfoRequest to CCP |
| [INBOUND] | `/Channels/OMXFMConnectionResponse` | `GET_PROFILE_FROM_CCP` | JMS | Receive queryUserProfileResponse from CCP |
| [OUTBOUND] | Logger channel | OMXESB Logger | JMS | Audit log for each request sent |

### §8.3 Backend API Details

| System | Operation | Request Schema | Response Schema | Namespace |
|--------|-----------|---------------|-----------------|-----------|
| **CCP (ZTE BSS SmartBSS)** | queryUserProfile / GetPrepaidCreditInfo | `GetPrepaidCreditInfoRequest.xsd` | `queryUserProfileResponse` | `http://thaitrue.customization.ws.bss.zsmart.ztesoft.com` |

The request schema namespace is `http://services.omx.truecorp.co.th/FM/GetPrepaidCreditInfoRequest`. The response comes back under the ZTE BSS namespace (`xsd2`). CCP here refers to the ZTE BSS online charging/profile system — not CCBS.

### §8.4 BE Working Memory Dependencies

| Field | Access | Purpose |
|-------|--------|---------|
| `orderRequest.OrderData.Customer.ParentOU[].Subscriber[]` | READ | Subscriber list for fan-out |
| `orderRequest.OrderData.Customer.ParentOU[].ChildOU[].Subscriber[]` | READ | ChildOU subscriber list |
| `orderCurrentActivity.Response[]` | READ/WRITE | Check prior successes; response handler appends ResponseBase |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-in counter; incremented per outbound request |
| `orderCurrentActivity.Status` | WRITE | Set to REQUESTING(1) or SKIPPED(4) |
| `subscriber.SubscriberOffers[]` | WRITE (response) | Populated with CCP price plan data in response handler |

### §8.5 ExtendedInfo Fields

| Name | Value | Set Where | Required |
|------|-------|-----------|----------|
| `FE_OR_CCBS` | `CCP` | SubscriberOffers.ExtendedInfo (response handler) | Always |

### §8.6 Global Variable Dependencies

| Global Variable Path | Used For |
|---------------------|---------|
| `OMX_COMMON/_SharedResources/Common/Log/OrderTypeFilter` | Suppress logging for specific order types |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `OMX_OM/WritePayload` | Controls whether full payload is included in audit log |

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Variant | Parameters | Subscriber Path |
|---------|-----------|-----------------|
| Variant ① — ParentOU | `orderRequest, i, j` | `ParentOU[$i+1]/Subscriber[$j+1]/` |
| Variant ② — ChildOU | `orderRequest, i, p, q` | `ParentOU[$i+1]/ChildOU[$p+1]/Subscriber[$q+1]/` |

### §9.2 Event Container Construction

- Event type: `/Events/OMConsumers/OMXFM/Request/GET_PROFILE_FROM_CCP`
- Extends: `/Events/Base/OMXRequestBaseEvent`
- Channel: `/Channels/OMXFMConnectionRequest` → destination `GET_PROFILE_FROM_CCP`

### §9.3 JMS / Event Header Fields

| Field | Source |
|-------|--------|
| `JMSPriority` | `$orderRequest/OrderPriority` |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` |
| `OrderID` | `$orderRequest/OrderData/OrderID` |
| `RefID` | Subscriber RefId (variant-specific path) |
| `OrderType` | `$orderRequest/OrderData/OrderType` |

### §9.6 Core Payload Fields

| XML Element | Source | Notes |
|-------------|--------|-------|
| `ns:GetPrepaidCreditInfoRequest/ns:MSISDN` | Subscriber MSISDN (variant path) | Primary key for CCP lookup |
| `ns:GetPrepaidCreditInfoRequest/ns:OrderChannel` | `$orderRequest/OrderData/Channel` | Request origination channel |

### §9.7 Complete Generated XML Example

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20260813-001</JMSCorrelationID>
    <OrderID>ORD-20260813-99001</OrderID>
    <RefID>SUB-REF-001</RefID>
    <OrderType>POSTPAID_REMOVE_OFFER_SUB</OrderType>
    <payload>
      <ns:GetPrepaidCreditInfoRequest xmlns:ns="http://services.omx.truecorp.co.th/FM/GetPrepaidCreditInfoRequest">
        <ns:MSISDN>0812345678</ns:MSISDN>
        <ns:OrderChannel>API</ns:OrderChannel>
      </ns:GetPrepaidCreditInfoRequest>
    </payload>
  </event>
</createEvent>
```

### §9.8 XSLT Stylesheet Source

**Variant ① — ParentOU Subscriber (params: orderRequest, i, j)**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ns="http://services.omx.truecorp.co.th/FM/GetPrepaidCreditInfoRequest"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    version="1.0" exclude-result-prefixes="xsl ns xsd">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>   <!-- bound from orderRequest concept -->
  <xsl:param name="i"/>              <!-- ParentOU index (0-based from BE loop) -->
  <xsl:param name="j"/>              <!-- Subscriber index under ParentOU -->
  <xsl:template match="/">
    <createEvent>
      <event>
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <RefID><xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[$i+1]/Subscriber[$j+1]/RefId"/></RefID>
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        <payload>
          <ns:GetPrepaidCreditInfoRequest>
            <ns:MSISDN><xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[$i+1]/Subscriber[$j+1]/MSISDN"/></ns:MSISDN>
            <ns:OrderChannel><xsl:value-of select="$orderRequest/OrderData/Channel"/></ns:OrderChannel>
          </ns:GetPrepaidCreditInfoRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**Variant ② — ChildOU Subscriber (params: orderRequest, i, p, q) — diff vs Variant ①**

| Element | Variant ① (POU) | Variant ② (COU) |
|---------|----------------|----------------|
| Parameters | `orderRequest, i, j` | `orderRequest, i, p, q` |
| `RefID` source | `ParentOU[$i+1]/Subscriber[$j+1]/RefId` | `ParentOU[$i+1]/ChildOU[$p+1]/Subscriber[$q+1]/RefId` |
| `ns:MSISDN` source | `ParentOU[$i+1]/Subscriber[$j+1]/MSISDN` | `ParentOU[$i+1]/ChildOU[$p+1]/Subscriber[$q+1]/MSISDN` |

All other fields are identical.

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                          [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId                [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                      [Always]
    ├── RefID                ← ParentOU[$i+1]/Subscriber[$j+1]/RefId                [Always]
    │                           (Variant ②: ChildOU[$p+1]/Subscriber[$q+1]/RefId)
    ├── OrderType            ← $orderRequest/OrderData/OrderType                    [Always]
    └── payload
        └── ns:GetPrepaidCreditInfoRequest
            ├── ns:MSISDN        ← Subscriber[$j+1]/MSISDN (or ChildOU variant)    [Always]
            └── ns:OrderChannel  ← $orderRequest/OrderData/Channel                 [Always]
```

**Legend:** `[Always]` = unconditionally present | `[Conditional: ...]` = inside xsl:if

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| `ESBUUID` | `$orderRequest/OrderData/OMXTrackingId` [Conditional: if non-empty] |
| `PROCESS_ID` | `concat($pid, "_REQ")` / `concat($pid, "_RES")` |
| `COMPONENT_NAME` | `OMX_COMMON/Component_Name/OMX_CEP` |
| `OPERATION_NAME` | `"GET_PROFILE_FROM_CCP_ALL"` (static) |
| `TARGET_SYSTEM` | `OMX_COMMON/Component_Name/OMX_FM` |
| `LOG_LEVEL` | `INFO` |
| `AUDIT_TRACE` | `"Request Sent for GET_PROFILE_FROM_CCP_ALL"` / `"Response received for GET_PROFILE_FROM_CCP_ALL"` |
| `AUDIT_TS` | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| `payload/ns:ServicePayload` | Full event copy — gated on `OMX_OM/WritePayload = "true"` |

## §12 — Activity Status Management

| Status Code | Meaning | Trigger |
|-------------|---------|---------|
| `"1"` → REQUESTING | At least one request dispatched, awaiting responses | After any subscriber request sent |
| `"4"` → SKIPPED | All subscribers already succeeded or failed PreExecCheck | `isSkipped` remains true after all loops |

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

`HandleActivityException` marks the activity as ERROR, persists state to DB, and propagates the fault through the order orchestration.

## §14 — Helper Functions Reference

| Function | Signature | Purpose |
|----------|-----------|---------|
| `AllowWriteLog` | `boolean(String orderType)` | Returns false if orderType is in the global no-log filter |
| `GetXMLForSubscriber` | `String(orderRequest, refId)` | Serialises a POU subscriber to XML for PreExecCheck evaluation |
| `GetXMLForSubscriberInChildOU` | `String(orderRequest, refId, pouRefId)` | Serialises a COU subscriber to XML for PreExecCheck evaluation |
| `GetActivityStatusString` | `String(String code, boolean ...)` | Maps numeric code to status string ("1"→REQUESTING) |
| `SendDataToDB` | `void(orderRequest)` | Persists current order state to DB |
| `SkipActivity` | `void(orderRequest, activity, code)` | Marks activity skipped and advances orchestration |
| `HandleActivityException` | `void(orderRequest, activity, exception, msg)` | Error handling — marks ERROR, persists, escalates |

## §15 — Function Dependency Tree

```text
Request_GET_PROFILE_FROM_CCP_ALL (rule)
├── RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)              [POU PreExecCheck]
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)  [COU PreExecCheck]
├── XPath.execute(expression, xml, namespace)
├── Event.createEvent("xslt://GET_PROFILE_FROM_CCP ①")                         [POU send]
├── Event.Ext.sendEventImmediate(reqEvent)
├── RuleFunctions.Helpers.AllowWriteLog(orderType)
│   └── System.getGlobalVariableAsString("OMX_COMMON/.../OrderTypeFilter")
├── Event.createEvent("xslt://Logger")                                          [audit]
├── Event.Ext.sendEventImmediate(logEvent)
├── Event.createEvent("xslt://GET_PROFILE_FROM_CCP ②")                         [COU send]
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")
└── RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")
```

## §16 — Concept Definitions Referenced

| Concept | Path | Key Properties |
|---------|------|---------------|
| `OrderRequest` | `/Concepts/OrderRequest/OrderRequest` | OrderData, ProcessFlow, OrderPriority, IsOrderResubmitted |
| `Activity` | `/Concepts/OM/ProcessConfig/Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck |
| `Subscriber` | `/Concepts/OrderRequest/OrderElements/Subscriber` | MSISDN, RefId, SubscriberOffers[] |
| `SubscriberOffers` | `/Concepts/OrderRequest/OrderElements/SubscriberOffers` | OfferName, ExtendedInfo[], ParameterInfo[], SwitchFeature[], DataInfo, BenefitInfo |
| `ResponseBase` | `/Concepts/FM/Base/ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Query CCP (ZTE BSS) for each subscriber's active price plans using MSISDN and channel |
| R2 | Fan-out to ALL subscribers — both direct (POU) and nested (COU) hierarchy |
| R3 | Skip subscribers that already have a successful response in the current activity |
| R4 | Evaluate per-subscriber PreExecCheck before sending (conditional execution) |
| R5 | Populate SubscriberOffers from PricePlanDtoList with `FE_OR_CCBS=CCP` marker |
| R6 | Fan-in: only signal completion when all sent requests have responded |
| R7 | Support order resubmission without double-counting RequestCount |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| CCP (ZTE BSS) namespace coupling | [HIGH] | Response handler hardcodes ZTE BSS namespace — any schema change breaks parsing. Add namespace version header. |
| PricePlanDto loop — namespace mismatch silently returns 0 | [MEDIUM] | Add response validation to detect empty results that may indicate a schema mismatch. |
| Subscriber dual lookup (SUB:/CSUB:) | [MEDIUM] | Two sequential getByExtIdByUri calls. Consider a unified lookup helper. |
| Fan-out without timeout | [MEDIUM] | If CCP does not respond, the activity hangs. Ensure expiry action is configured on the event. |
| XSLT index arithmetic ($i+1) | [LOW] | XPath 1.0 is 1-based; BE loop is 0-based. Correct, but validate when migrating to modern frameworks. |

## §18 — Full Source Code

```java
/**
 * @description
 * @author Chayatorn Pan.
 */
rule Rules.OMConsumers.OMXFM.Request.Request_GET_PROFILE_FROM_CCP_ALL {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "GET_PROFILE_FROM_CCP_ALL";
    orderRequest.ProcessFlow.NextActivityID == "GET_PROFILE_FROM_CCP_ALL";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
    try {
      Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
          orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
      int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
      String pouRefId = "";
      boolean isSkipped = true;
      for (int i=0; i < iPOULen; i++) {                  // ParentOU Loop
        pouRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;
        int iSubscriberLen = orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length;
        for (int j=0; j<iSubscriberLen; j++) {            // POU Subscriber Loop
          String refId = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].RefId;
          boolean reqSuccess = false;
          for (int iResp=0; iResp<orderCurrentActivity.Response@length; iResp++)
            if (String.equals(orderCurrentActivity.Response[iResp].ReferenceId, refId)
                && orderCurrentActivity.Response[iResp].CompletionStatus==2)
              reqSuccess = true;
          if (!reqSuccess) {
            String chkRes = "true";
            if (String.length(nextAct.PreExecCheck) > 0) {
              String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId);
              chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
            }
            if (String.equals(chkRes,"true")) {
              Events.OMConsumers.OMXFM.Request.GET_PROFILE_FROM_CCP reqEvent =
                  Event.createEvent(/* xslt://GET_PROFILE_FROM_CCP Variant ① — see §9.8
                                      Outputs: JMSPriority, JMSCorrelationID, OrderID, RefID,
                                               OrderType, payload/ns:GetPrepaidCreditInfoRequest{ns:MSISDN, ns:OrderChannel} */);
              Event.Ext.sendEventImmediate(reqEvent);
              if (RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                long pid = System.nanoTime();
                Event.Ext.sendEventImmediate(Event.createEvent(/* Logger XSLT — OPERATION_NAME=GET_PROFILE_FROM_CCP_ALL */));
              }
              if (!isActResub) orderCurrentActivity.RequestCount++;
              isSkipped = false;
            }
          }
        }
        // ChildOU loop (p, q) — same pattern with Variant ② XSLT, path: ChildOU[$p+1]/Subscriber[$q+1]
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

`Response_GET_PROFILE_FROM_CCP_ALL` receives the `queryUserProfileResponse` from CCP. It: (1) appends a ResponseBase to the activity's Response array; (2) looks up the Subscriber concept and populates `SubscriberOffers` from CCP price plan data; (3) logs the audit response; (4) returns "true" when all fan-in requests are complete.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `/Concepts/OrderRequest/OrderRequest` | Master order — provides OMXTrackingId for subscriber lookup |
| `eventResponse` | `/Events/OMConsumers/OMXFM/Response/GET_PROFILE_FROM_CCP` | Inbound CCP response — carries ResponseCode, ResponseMsg, CompletionStatus, RefID, payload |
| `currActivity` | `/Concepts/OM/ProcessConfig/Activity` | Current activity — RequestCount tracked for fan-in; Response[] appended |

### §19.3 ResponseBase Concept Construction

extId = `"GPCIR:" + eventResponse.JMSCorrelationID + ":" + eventResponse.RefID`

```text
createObject
└── object (ResponseBase)
    ├── ResponseCode       ← $eventResponse/ResponseCode     [Conditional: if $eventResponse/ResponseCode]
    ├── ResponseMessage    ← $eventResponse/ResponseMsg      [Conditional: if $eventResponse/ResponseMsg]
    ├── CompletionStatus   ← $eventResponse/CompletionStatus [Conditional: if $eventResponse/CompletionStatus]
    └── ReferenceId        ← $eventResponse/RefID            [Conditional: if $eventResponse/RefID]
```

### §19.4 SubscriberOffers Population (CCP Price Plans)

After appending ResponseBase, the handler queries the response payload for CCP price plan entries:

```java
// Count PricePlanDto entries in ZTE BSS namespace (xsd2)
int priceplanDtoLength = XPath.evalAsInt(
    "count($eventResponse/payload/xsd2:queryUserProfileResponse"
    + "/xsd2:queryUserProfileReturn/xsd2:PricePlanDtoList/xsd2:PricePlanDto)");

for (int i=0; i<priceplanDtoLength; i++) {
    String pp_name = XPath.evalAsString("$eventResponse/.../xsd2:PricePlanDto[$i+1]/xsd2:PricePlanName");
    // Create SubscriberOffers with: OfferName=pp_name, ExtendedInfo{Name="FE_OR_CCBS", Value="CCP"}
    subscriber.SubscriberOffers[subscriber.SubscriberOffers@length] = subscriberOfferConcept;
}
```

> **Key:** The `FE_OR_CCBS=CCP` ExtendedInfo marker distinguishes CCP-sourced offers from CCBS-sourced offers (`FE_OR_CCBS=CCBS`). Downstream rules use this to route offer processing.

### §19.5 Subscriber Lookup

```java
// Lookup by POU extId first, then COU extId
subscriber = Instance.getByExtIdByUri("SUB:"+OMXTrackingId+":"+RefID, "/Concepts/.../Subscriber");
if (subscriber == null)
    subscriber = Instance.getByExtIdByUri("CSUB:"+OMXTrackingId+":"+RefID, "/Concepts/.../Subscriber");
```

### §19.6 Response Completion Logic

| Check | Expression | Meaning |
|-------|-----------|---------|
| Fan-in condition | `currActivity.RequestCount == currActivity.Response@length` | All dispatched requests have returned |
| Return "true" | All responses received | Signals orchestrator to advance to next activity |
| Return "false" | Still waiting for responses | Orchestrator keeps activity in REQUESTING state |

> **Note:** Unlike other FMs, this response handler does NOT use `tib:right(tib:trim(ResponseCode), 3) = "000"` for success counting. It uses a simple count of all Response entries vs RequestCount — all responses (including errors) contribute to fan-in completion.

### §19.7 Response Audit Logging

| Field | Value |
|-------|-------|
| `PROCESS_ID` | `concat($pid, "_RES")` |
| `OPERATION_NAME` | `"GET_PROFILE_FROM_CCP_ALL"` |
| `AUDIT_TRACE` | `"Response received for GET_PROFILE_FROM_CCP_ALL"` |
| `payload/ns:ServicePayload` | Full `$eventResponse` copy — gated on `WritePayload=true` |

### §19.8 Response XSLT Source

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema" version="1.0"
    exclude-result-prefixes="xsl xsd">
  <xsl:output method="xml"/>
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:if test="$eventResponse/ResponseCode">
          <ResponseCode><xsl:value-of select="$eventResponse/ResponseCode"/></ResponseCode>
        </xsl:if>
        <xsl:if test="$eventResponse/ResponseMsg">
          <ResponseMessage><xsl:value-of select="$eventResponse/ResponseMsg"/></ResponseMessage>
        </xsl:if>
        <xsl:if test="$eventResponse/CompletionStatus">
          <CompletionStatus><xsl:value-of select="$eventResponse/CompletionStatus"/></CompletionStatus>
        </xsl:if>
        <xsl:if test="$eventResponse/RefID">
          <ReferenceId><xsl:value-of select="$eventResponse/RefID"/></ReferenceId>
        </xsl:if>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
