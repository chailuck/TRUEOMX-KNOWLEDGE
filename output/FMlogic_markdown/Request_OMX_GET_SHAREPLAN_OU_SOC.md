# Request_OMX_GET_SHAREPLAN_OU_SOC

## §1 — Overview & Purpose

This rule fires during the **CHANGE_PP** (Change Price Plan) order flow when a subscriber belongs to a *shareplan* (ParentOU) arrangement and the *new* price-plan SOC needs to be identified for addition. It queries the OMX internal service `OMX_GET_SHAREPLAN_OU_SOC` with the subscriber's current ServiceType-80 offer details to retrieve the new SOC metadata from the OU-level plan configuration.

The **ADD** variant identifies the new SOC that should be applied at the shareplan OU level. The response handler appends `Action=ADD` entries to `Agreement.Offers[]`. It also handles a conflict case: when the same offer already has both a CCBS entry and a pending FE REMOVE entry, it removes the FE REMOVE entry to make way for the new ADD.

> The rule parameter (from `Parameter[1]`) controls which FE_OR_CCBS tag type to match — defaults to `"FE"`. In the CHANGE_PP ProcessConfig step 11 (`OMX_GET_SHAREPLAN_OU_NEWSOC`) this is configured with parameter `FE`.

> **Compared to the REMOVE variant (`OMX_GET_SHAREPLAN_OU_SOC_REMOVE`):** this rule uses the standard **IntraActivitySequencing.ActionRequestEvent** helper (not commented out), and uses **ParentOU OUId** as RefID instead of subscriber RefId.

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule path | `Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_SHAREPLAN_OU_SOC` |
| Priority | 5 |
| ForwardChain | true |
| ActivityID guard | `OMX_GET_SHAREPLAN_OU_SOC` |
| Response event type | `Events.OMConsumers.OMXFM.Response.OMX_GET_SHAREPLAN_OU_SOC` |
| Backend | OMX (internal FM service) |

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context — contains ParentOU, Subscriber, SubscriberOffers, ProcessFlow |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Active process step — tracks Status, RequestCount, Response[], Parameter[] |

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to order's next step |
| 2 | `orderCurrentActivity.ActivityID == "OMX_GET_SHAREPLAN_OU_SOC"` | Guards to specific activity type |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_GET_SHAREPLAN_OU_SOC"` | Double-checks process flow pointer |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires when not yet dispatched |

## §5 — Execution Flow Diagram

1. Read `param` from `Parameter[1]` (default `"FE"`)
2. Check `isActResub`: if resubmit, call `PurgePendingRequestsBeforeResubmit`
3. Outer loop: iterate `ParentOU[p]`
4. Inner loop: iterate `Subscriber[j]` within each ParentOU
5. Check `reqSuccess`: skip if subscriber's RefId already has CompletionStatus==2
6. Evaluate `PreExecCheck` XPath via `GetXMLForSubscriber` + `XPath.execute`
7. Scan `SubscriberOffers[]` for `FE_OR_CCBS=$param AND ServiceType='80'` — extract `ppMainSub` and `ppMainId`
8. If `ppMainSub != ""`: send event + call **ActionRequestEvent** (standard fan-out tracking) + increment RequestCount
9. Send audit log event
10. Post-loop: if requests sent → Status="1" (PROCESSING); else → SkipActivity "4"
11. On exception: `HandleActivityException`

## §6 — Rule Action (THEN) — Key Differences from REMOVE Variant

| Aspect | OMX_GET_SHAREPLAN_OU_SOC (this rule) | OMX_GET_SHAREPLAN_OU_SOC_REMOVE |
|--------|--------------------------------------|----------------------------------|
| ActionRequestEvent | [Active] — standard fan-out tracking | [Commented out] — direct sendEventImmediate only |
| RefID in event | `ParentOU[p].OUId` | `Subscriber[j].RefId` |
| Param default / CHANGE_PP config | "FE" / FE (step 11) | "FE" default / CCBS (step 10) |
| Response Action written | `ADD` | `REMOVE` |

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Fires during **CHANGE_PP** orders for shareplan (ParentOU) subscribers. This is the NEW SOC lookup (ADD path) — runs after the REMOVE variant (step 10) to identify the incoming plan SOC.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_GET_SHAREPLAN_OU_SOC` | Query OMX for shareplan OU SOC info |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.OMX_GET_SHAREPLAN_OU_SOC` | Response with ShareplanOUSocInfoArray |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | Audit log |

### §8.3 Backend API Details

| System | Operation | Schema |
|--------|-----------|--------|
| OMX FM | GetShareplanOUSocInfo | `GetShareplanOUSocInfoRequest.xsd` / `GetShareplanOUSocInfoResponse.xsd` |

### §8.4 BE Working Memory Dependencies

| Field | Read/Write | Purpose |
|-------|-----------|---------|
| `orderRequest.OrderData.Customer.ParentOU[p].Subscriber[j].SubscriberOffers[k]` | READ | Find ServiceType-80 offer matching FE_OR_CCBS=param |
| `orderCurrentActivity.Parameter[1]` | READ | FE_OR_CCBS param (default "FE") |
| `orderCurrentActivity.Response[iResp]` | READ | reqSuccess guard |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Incremented per request; used for fan-in |
| `orderCurrentActivity.Status` | WRITE | Set to "1" or skip |
| `orderRequest.OrderData.Customer.ParentOU[iPOU].Agreement.Offers[]` | WRITE (response) | Appends ADD offer; may delete conflicting FE/REMOVE entry |

### §8.5 ExtendedInfo Fields

| Name | Where | Usage |
|------|-------|-------|
| `FE_OR_CCBS` | SubscriberOffers | Matched against $param to find the PP offer |
| `FE_OR_CCBS = "FE"` | Agreement.Offers (written) | New ADD offer is FE type |
| `OFFER_LEVEL = "PARENT"` | Agreement.Offers (written) | Marks offer as PARENT-level shareplan entry |
| `SOURCE_OR_TARGET = "TARGET"` | Agreement.Offers (written) | Marks new SOC as TARGET (incoming) |
| `SHARE_OFFER_DESC` | Agreement.Offers (written, conditional) | Human-readable description from response |

### §8.6 Global Variable Dependencies

| Variable Path | Used For |
|--------------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Conditional UserName/Password in event |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `OMX_OM/WritePayload` | Conditional payload in audit log |

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Parameter | Bound From |
|-----------|-----------|
| `$orderRequest` | `orderRequest` concept |
| `$p` | Outer loop index (0-based ParentOU position) |
| `$globalVariables` | BE global variables |
| `$ppMainSub` | OfferName of matched ServiceType-80 offer |
| `$ppMainId` | Soc of matched ServiceType-80 offer |

### §9.3 JMS / Event Header Fields

| Field | Source | Note |
|-------|--------|------|
| `JMSPriority` | `$orderRequest/OrderPriority` | |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | |
| `OrderID` | `$orderRequest/OrderData/OrderID` | |
| `RefID` | `$orderRequest/OrderData/Customer/ParentOU[number($p)]/OUId` | **Different from REMOVE variant** — ParentOU OUId |
| `UserName` | `$orderRequest/OrderData/User` | Conditional: IsEnableUserPass='true' |
| `PassWord` | `$orderRequest/OrderData/Password` | Conditional: IsEnableUserPass='true' |
| `OrderType` | `$orderRequest/OrderData/OrderType` | |

### §9.6 Core Payload

| Element | Source |
|---------|--------|
| `payload/ns:GetShareplanOUSocInfoRequest/ns:SocName` | `$ppMainSub` |
| `payload/ns:GetShareplanOUSocInfoRequest/ns:SocId` | `$ppMainId` |

### §9.7 Complete Generated XML Example

```xml
<event>
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-20260914-001</JMSCorrelationID>
  <OrderID>ORD-12345</OrderID>
  <RefID>OU-ID-001</RefID>  <!-- ParentOU OUId -->
  <OrderType>11001</OrderType>
  <payload>
    <ns:GetShareplanOUSocInfoRequest
      xmlns:ns="http://services.omx.truecorp.co.th/GetShareplanOUSocInfoRequest.xsd">
      <ns:SocName>SHAREPLAN_OFFER_BBBB</ns:SocName>
      <ns:SocId>87654321</ns:SocId>
    </ns:GetShareplanOUSocInfoRequest>
  </payload>
</event>
```

### §9.8 XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://services.omx.truecorp.co.th/GetShareplanOUSocInfoRequest.xsd"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="p"/>               <!-- outer loop index (0-based ParentOU position) -->
  <xsl:param name="globalVariables"/>
  <xsl:param name="ppMainSub"/>
  <xsl:param name="ppMainId"/>
  <xsl:template match="/">
    <createEvent>
      <event>
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <!-- RefID uses ParentOU OUId (differs from REMOVE variant which uses subscriber RefId) -->
        <RefID><xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[number($p)]/OUId"/></RefID>
        <xsl:if test="$globalVariables/OMX_OM/.../IsEnableUserPass='true'">
          <UserName><xsl:value-of select="$orderRequest/OrderData/User"/></UserName>
          <PassWord><xsl:value-of select="$orderRequest/OrderData/Password"/></PassWord>
        </xsl:if>
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        <payload>
          <ns:GetShareplanOUSocInfoRequest>
            <ns:SocName><xsl:value-of select="$ppMainSub"/></ns:SocName>
            <ns:SocId><xsl:value-of select="$ppMainId"/></ns:SocId>
          </ns:GetShareplanOUSocInfoRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                              [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId                   [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                          [Always]
    ├── RefID                ← $orderRequest/OrderData/Customer/ParentOU[number($p)]/OUId  [Always]
    │                           [ParentOU OUId — differs from REMOVE variant]
    ├── UserName             ← $orderRequest/OrderData/User                             [Conditional: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password                         [Conditional: IsEnableUserPass='true']
    ├── OrderType            ← $orderRequest/OrderData/OrderType                        [Always]
    └── payload                                                                         [Always]
        └── ns:GetShareplanOUSocInfoRequest  [ns=GetShareplanOUSocInfoRequest.xsd]
            ├── ns:SocName   ← $ppMainSub                                               [Always]
            └── ns:SocId     ← $ppMainId                                                [Always]
```

## §11 — Audit Logging

| Field | Request Value | Response Value |
|-------|--------------|----------------|
| PROCESS_ID | `concat(pid,"_REQ")` | `concat(pid,"_RES")` |
| OPERATION_NAME | `"OMX_GET_SHAREPLAN_OU_SOC"` | `"OMX_GET_SHAREPLAN_OU_SOC"` |
| TARGET_SYSTEM | `OMX_COMMON/.../OMX_FM` | `OMX_COMMON/.../OMX_FM` |
| AUDIT_TRACE | `concat("Request Sent for RefId ", $refId)` | `"Response received for OMX_GET_SHAREPLAN_OU_SOC"` |

## §12 — Activity Status Management

| Code | String | When |
|------|--------|------|
| "1" | PROCESSING | Requests sent; awaiting responses |
| "4" | SKIPPED | No matching offer found |
| Error | ERROR | Exception → `HandleActivityException` |

## §13 — Exception / Error Handling

Top-level `try/catch(Exception ae)` wraps all logic. On exception: `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `PurgePendingRequestsBeforeResubmit` | Clears pending requests on resubmit |
| `GetXMLForSubscriber` | Serialises subscriber XML for PreExecCheck XPath |
| `IntraActivitySequencing.ActionRequestEvent` | Standard fan-out request tracker — **active** in this variant |
| `GetActivityStatusString` | Maps status code to string |
| `SendDataToDB` | Persists state to DB |
| `SkipActivity` | Advances flow on skip |
| `HandleActivityException` | Handles exceptions |

## §15 — Function Dependency Tree

```text
Request_OMX_GET_SHAREPLAN_OU_SOC
├── RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── RuleFunctions.Helpers.GetXMLForSubscriber  [per subscriber, if PreExecCheck present]
├── Event.Ext.sendEventImmediate (OMX_GET_SHAREPLAN_OU_SOC)  [per matching subscriber]
├── RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent  [standard fan-out tracking]
├── Event.Ext.sendEventImmediate (Logger)  [audit]
├── RuleFunctions.Helpers.GetActivityStatusString
├── RuleFunctions.Helpers.SendDataToDB
├── RuleFunctions.Helpers.SkipActivity  [if no requests sent]
└── RuleFunctions.Helpers.HandleActivityException  [on error]
```

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1:** For each ParentOU subscriber with a ServiceType-80 offer matching `FE_OR_CCBS=$param`, query OMX for the new shareplan SOC metadata.
- **R2:** Response handler writes ADD AgreementOffers to ParentOU with FE_OR_CCBS=FE, OFFER_LEVEL=PARENT, SOURCE_OR_TARGET=TARGET.
- **R3:** If existing FE/REMOVE + CCBS entries both exist for same offer name, delete the FE/REMOVE entry (conflict resolution via `Instance.deleteInstance`).
- **R4:** Soc is populated in the ADD offer only when a matching FE/REMOVE offer already exists.

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| debugOut statements in response rulefunction (production noise) | [MEDIUM] | Remove or gate behind log-level check before production |
| `Instance.deleteInstance` in response rulefunction — deletes concept directly from working memory | [MEDIUM] | Ensure no other rule holds a reference; test concurrent order scenarios |
| Param default "FE" / CHANGE_PP uses "FE" — consistent, but verify other order types | [LOW] | Review all ProcessConfigs referencing OMX_GET_SHAREPLAN_OU_SOC for parameter consistency |

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_SHAREPLAN_OU_SOC {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_GET_SHAREPLAN_OU_SOC";
    orderRequest.ProcessFlow.NextActivityID == "OMX_GET_SHAREPLAN_OU_SOC";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    try {
      boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
      boolean isSkipped = true;
      if (isActResub) {
        RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      }
      String param = XPath.evalAsString(/* if Parameter[1] then Parameter[1] else "FE" */);
      int pOuLen = orderRequest.OrderData.Customer.ParentOU@length;
      for (int p = 0; p < pOuLen; p++) {
        int iSubscriberLen = orderRequest.OrderData.Customer.ParentOU[p].Subscriber@length;
        for (int j = 0; j < iSubscriberLen; j++) {
          String refId = orderRequest.OrderData.Customer.ParentOU[p].Subscriber[j].RefId;
          // reqSuccess guard + PreExecCheck evaluation
          if(!reqSuccess && chkRes.equals("true")) {
            // Scan SubscriberOffers for FE_OR_CCBS=$param AND ServiceType='80'
            if(ppMainSub != "") {
              Events.OMConsumers.OMXFM.Request.OMX_GET_SHAREPLAN_OU_SOC reqEvent =
                Event.createEvent(/* XSLT: see §9.8 — RefID=ParentOU[number($p)]/OUId, SocName=$ppMainSub, SocId=$ppMainId */);
              Event.Ext.sendEventImmediate(reqEvent);
              RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
              // NOTE: ActionRequestEvent IS active here (vs REMOVE variant where it was commented out)
              Event.Ext.sendEventImmediate(Event.createEvent(/* Logger: OPERATION_NAME=OMX_GET_SHAREPLAN_OU_SOC, AUDIT_TRACE="Request Sent for RefId $refId" */));
              if(!isActResub) orderCurrentActivity.RequestCount++;
              isSkipped = false;
            }
          }
        }
      }
      if(!isSkipped) {
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

`Response_OMX_GET_SHAREPLAN_OU_SOC` processes the OMX response and appends `Action=ADD` AgreementOffers entries to the ParentOU Agreement. It handles a conflict-resolution case where both CCBS and FE/REMOVE entries exist for the same offer.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Mutated — AgreementOffers appended or deleted |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_GET_SHAREPLAN_OU_SOC` | Backend response with ShareplanOUSocInfoArray |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | RequestCount for fan-in |

### §19.3 ResponseBase Concept Construction

```text
createObject  [Concepts.FM.Base.ResponseBase]
└── object
    ├── @extId           ← $eventResponse/@extId          [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode    [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg     [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId      ← $eventResponse/RefID           [Conditional]
```

### §19.4 Response Completion Logic

**Success XPath:** `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])`

**Fan-in condition:** `currActivity.RequestCount == successResponseCount` → returns `"true"` / `"false"`

### §19.5 Response Processing Logic

For each ParentOU and each `ShareplanOUSocInfo` entry in the response array:

| chkCCBS | chkFERemove | Action |
|---------|-------------|--------|
| false | false | Append ADD offer (Soc empty) |
| false | true | Append ADD offer with Soc from FE/REMOVE entry |
| true | true | Delete FE/REMOVE entry via `Instance.deleteInstance` (conflict resolution) |
| true | false | No action |

**Written AgreementOffers (when not chkCCBS):**

| Field | Value | Condition |
|-------|-------|-----------|
| `@extId` | `concat(generateTrackingID(), ':OMX_GET_SHAREPLAN_OU_SOC')` | Always |
| `OfferName` | `ns:share_offer` | Conditional |
| `ServiceType` | `ns:service_type` | Conditional |
| `Soc` | From existing FE/REMOVE offer's Soc | Only if chkFERemove |
| `Action` | `"ADD"` | Always |
| `ExtendedInfo[FE_OR_CCBS]` | `"FE"` | Always |
| `ExtendedInfo[OFFER_LEVEL]` | `"PARENT"` | Always |
| `ExtendedInfo[SHARE_OFFER_DESC]` | `ns:share_offer_desc` | If non-empty and non-"null" |
| `ExtendedInfo[SOURCE_OR_TARGET]` | `"TARGET"` | Always |

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
