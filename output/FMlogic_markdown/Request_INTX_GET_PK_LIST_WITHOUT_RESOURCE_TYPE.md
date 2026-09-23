# Request_INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE

## §1 — Overview & Purpose

This FM rule invokes the INTX **getPrimaryKeyListWithoutResourceType** service for each subscriber MSISDN under each ParentOU. In the *CREATE_BILL_ADJUSTMENT* flow (step 1), its purpose is to resolve the subscriber's **productId** (written as `subscriber.SubscriberId`) and **productStatus** (written as `CRM_SUB_STATUS` ExtendedInfo), enabling downstream routing between AR credit (BILL=Y) and BL charge (BILL=N).

> **OMX-2868:** The response handler explicitly sets `subscriber.SubscriberId` from INTX `productId` and writes `CRM_SUB_STATUS` — canonical subscriber ID resolution for INTX-gated flows.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE` |
| Priority | 5 |
| ForwardChain | true |
| Rule type | Request FM — sends per-subscriber INTX query |
| Fan-in pattern | Simple: `RequestCount++` per send; response uses `count("000") == RequestCount` |
| Backend system | INTX (Interconnect / True primary key service) |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Full order data |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Current activity state |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity matches flow pointer |
| 2 | `orderCurrentActivity.ActivityID == "INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE"` | Fires for this FM only |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE"` | Double-check order pointer |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Prevents double-firing |

---

## §5 — Execution Flow Diagram

1. Resubmit check → `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` if `RequestCount > 0 && IsOrderResubmitted`
2. PreExecCheck gate → read `nextAct.PreExecCheck` XPath (CREATE_BILL_ADJUSTMENT step 1: `boolean(//Subscriber[ExtendedInfo[Name='PRIMARY_RESOURCE_TYPE' and Value='C']]) and exists(//SubscriberOffers/ExtendedInfo[Name='BILL'])`)
3. Loop ParentOU → Subscriber → check if already responded (`CompletionStatus==2`)
4. Evaluate PreExecCheck per subscriber via `GetXMLForSubscriber(orderRequest, pSubRefId)`
5. Build INTX request event via XSLT → `Event.Ext.sendEventImmediate`
6. Increment `RequestCount++` (skip if resubmit) → `isSkipped = false`
7. Send audit log (REQUEST)
8. If `!isSkipped`: `Status = "1"` (SENT) + `SendDataToDB` → else: `SkipActivity(..., "4")`

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in CREATE_BILL_ADJUSTMENT (step 1). PreExecCheck gates on `PRIMARY_RESOURCE_TYPE='C'` AND existence of `BILL` ExtendedInfo on SubscriberOffers.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Schema Namespace | Purpose |
|-----------|-----------|-----------------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE` | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetPrimaryKeyListWithoutResourceType.xsd` | PK lookup by MSISDN |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE` | Same namespace | Returns productId, productStatus |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `http://schemas.true.com/AuditLogging/V1_0` | Audit trail |

### §8.3 — Backend API Details

| System | Operation | Protocol | Request Root | Response Root |
|--------|-----------|----------|-------------|--------------|
| INTX | getPrimaryKeyListWithoutResourceType | JMS/SOAP via ESB | `ns:getPrimaryKeyListWithoutResourceTypeRequest` | `xsd5:getPrimaryKeyListWithoutResourceTypeResponse` |

### §8.4 — BE Working Memory Read/Write

| Field | Access | Notes |
|-------|--------|-------|
| `orderCurrentActivity.Status` | Write | "1" (SENT) or "4" (SKIP) |
| `orderCurrentActivity.RequestCount` | Read+Write | Incremented per subscriber send |
| `orderCurrentActivity.Response[]` | Read | Checked per pSubRefId for CompletionStatus==2 |
| `subscriber.SubscriberId` | Write (response) | Set from INTX productId |
| `subscriber.ExtendedInfo[] (CRM_SUB_STATUS)` | Write (response) | Set from INTX productStatus |

### §8.5 — ExtendedInfo Fields Required

| Key | Required? | Where Used |
|-----|-----------|-----------|
| `PRIMARY_RESOURCE_TYPE` | Required (gate) | Subscriber ExtendedInfo — value must be "C" |
| `BILL` | Required (gate) | SubscriberOffers ExtendedInfo — must exist |
| `CRM_SUB_STATUS` | Written | Subscriber ExtendedInfo — written in response handler |

### §8.6 — Global Variable Dependencies

| Path | Usage |
|------|-------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | If 'true', includes UserName/PassWord in event headers |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit log COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit log TARGET_SYSTEM |
| `$globalVariables/OMX_OM/WritePayload` | If "true", includes payload in audit log |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| Parameter | Bound From |
|-----------|-----------|
| `$orderRequest` | Full OrderRequest concept |
| `$pSubRefId` | Loop variable — subscriber RefId |
| `$globalVariables` | BE global variable store |
| `$msisdn` | Loop variable — subscriber MSISDN |

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `@extId` | `OMXUtils:generateTrackingID()` | Always |
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$pSubRefId` | Always |
| `UserName` | `$orderRequest/OrderData/User` | [Credential-gated: IsEnableUserPass='true'] |
| `PassWord` | `$orderRequest/OrderData/Password` | [Credential-gated: IsEnableUserPass='true'] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Always |

### §9.6 — Core Payload Fields

| XML Element | Source | Notes |
|-------------|--------|-------|
| `ns:correlatedId` | `$orderRequest/OrderData/OMXTrackingId` | Correlation tracking |
| `ns:primResourceValue` | `$msisdn` | Subscriber MSISDN — the primary resource to look up |
| `ns:accountId` | `$orderRequest/OrderData/Customer/Account[1]/AccountID` | First account's ID |

### §9.8 — XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetPrimaryKeyListWithoutResourceType.xsd"
  version="1.0">
  <xsl:param name="orderRequest"/>  <!-- full OrderRequest concept -->
  <xsl:param name="pSubRefId"/>     <!-- current subscriber RefId -->
  <xsl:param name="globalVariables"/>
  <xsl:param name="msisdn"/>        <!-- subscriber MSISDN -->
  <xsl:template match="/">
    <createEvent><event>
      <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
      <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      <RefID><xsl:value-of select="$pSubRefId"/></RefID>
      <xsl:if test="$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass='true'">
        <UserName><xsl:value-of select="$orderRequest/OrderData/User"/></UserName>
        <PassWord><xsl:value-of select="$orderRequest/OrderData/Password"/></PassWord>
      </xsl:if>
      <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      <payload>
        <ns:getPrimaryKeyListWithoutResourceTypeRequest>
          <ns:correlatedId><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></ns:correlatedId>
          <ns:primResourceValue><xsl:value-of select="$msisdn"/></ns:primResourceValue>
          <ns:accountId><xsl:value-of select="$orderRequest/OrderData/Customer/Account[1]/AccountID"/></ns:accountId>
        </ns:getPrimaryKeyListWithoutResourceTypeRequest>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree

```text
createEvent
└── event
    ├── @extId              ← OMXUtils:generateTrackingID()                    [Always]
    ├── JMSPriority         ← $orderRequest/OrderPriority                      [Always]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId            [Always]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                  [Always]
    ├── RefID               ← $pSubRefId                                       [Always]
    ├── UserName            ← $orderRequest/OrderData/User                     [Credential-gated: IsEnableUserPass='true']
    ├── PassWord            ← $orderRequest/OrderData/Password                 [Credential-gated: IsEnableUserPass='true']
    ├── OrderType           ← $orderRequest/OrderData/OrderType                [Always]
    └── payload
        └── ns:getPrimaryKeyListWithoutResourceTypeRequest
            ├── ns:correlatedId       ← $orderRequest/OrderData/OMXTrackingId  [Always]
            ├── ns:primResourceValue  ← $msisdn (subscriber MSISDN)            [Always]
            └── ns:accountId         ← Customer/Account[1]/AccountID           [Always]
```

---

## §11 — Audit Logging

| Direction | AUDIT_TRACE | PROCESS_ID | Trigger |
|-----------|------------|-----------|--------|
| REQUEST | "Request Sent for INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE" | `_REQ` | After each subscriber send |
| RESPONSE | "Response received for INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE" | `_RES` | In response rulefunction |

Payload included in audit log when `$globalVariables/OMX_OM/WritePayload = "true"`.

---

## §12 — Activity Status Management

| Status Code | String | Condition |
|-------------|--------|-----------|
| "1" | SENT | At least one subscriber request was sent |
| "4" | SKIP | All subscribers skipped / PreExecCheck false |

---

## §13 — Exception / Error Handling

Entire `then` block is wrapped in `try { ... } catch (Exception ae)`. On failure: `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clean stale tracking on resubmit |
| `GetXMLForSubscriber(orderRequest, pSubRefId)` | Serializes subscriber as XML for XPath PreExecCheck |
| `GetActivityStatusString("1", false)` | Returns "SENT" status string |
| `SkipActivity(orderRequest, activity, "4")` | Marks SKIP, advances flow |
| `HandleActivityException(orderRequest, activity, ae, "")` | Handles caught exceptions |
| `SendDataToDB(orderRequest)` | Persists order state |

---

## §15 — Function Dependency Tree

```text
Request_INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE
├── [optional] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit
├── GetXMLForSubscriber (per subscriber)
├── Event.createEvent (XSLT → INTX request event)
│   └── Event.Ext.sendEventImmediate
├── GetActivityStatusString("1", false)
├── SendDataToDB
├── SkipActivity (if no requests sent)
└── HandleActivityException (catch block)

Response_INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE
├── OMXUtils.generateTrackingID
├── Instance.createInstance (ResponseBase)
├── XPath.evalAsString → subStatus (productStatus)
├── XPath.evalAsString → subscriberId (productId)
├── Instance.getByExtIdByUri (SUB: or CSUB: subscriber lookup)
│   ├── subscriber.SubscriberId = subscriberId
│   └── Instance.createInstance (SubscriberExtendedInfo → CRM_SUB_STATUS)
├── Event.createEvent (Logger audit response)
└── XPath.evalAsInt (count "000" responses) → fan-in
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Expose INTX getPrimaryKeyListWithoutResourceType as async service call per subscriber MSISDN |
| R2 | Populate `subscriber.SubscriberId` from response `productId` |
| R3 | Write `CRM_SUB_STATUS` ExtendedInfo from response `productStatus` (OMX-2868) |
| R4 | Fan-in: all subscriber requests must succeed before advancing |
| R5 | Skip if no subscribers have `PRIMARY_RESOURCE_TYPE='C'` or no BILL ExtendedInfo |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `primaryKeyInfoArray[1]` — only first item used; multi-SIM may miss alternate productIds | [MEDIUM] | Validate single-SIM assumption with INTX team |
| Subscriber lookup fallback to `CSUB:` prefix on resubmit | [LOW] | Ensure both key formats handled consistently |
| `Account[1]` hardcoded — first account only | [MEDIUM] | Confirm assumption with AR team |
| Credential gating (IsEnableUserPass) — silently omits creds if not set | [LOW] | Verify global variable set in all target environments |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE";
    orderRequest.ProcessFlow.NextActivityID == "INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      // ... get nextAct, PreExecCheck, isSkipped=true ...
      if(isActResub) IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      // Loop ParentOU → Subscriber
      for(int p=0; p < pOuLen; p++) {
        for(int s=0; s < pSubLen; s++) {
          // skip if already responded with CompletionStatus==2
          if(!reqSuccess) {
            // evaluate PreExecCheck via GetXMLForSubscriber
            if(chkRes == "true") {
              Events.OMConsumers.OMXFM.Request.INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE reqEvent =
                Event.createEvent("xslt://{{...}}");
                /* XSLT: correlatedId ← OMXTrackingId, primResourceValue ← msisdn,
                   accountId ← Account[1]/AccountID — see §9.8 for full XSLT */
              Event.Ext.sendEventImmediate(reqEvent);
              isSkipped = false;
              if(!isActResub) orderCurrentActivity.RequestCount++;
              // audit log
            }
          }
        }
      }
      if(!isSkipped) {
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else {
        SkipActivity(orderRequest, orderCurrentActivity, "4");
      }
    } catch(Exception ae) {
      HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 — Overview

Receives INTX response for one subscriber. Extracts `productId` and `productStatus`, updates subscriber working memory, writes `CRM_SUB_STATUS`. Simple fan-in: `count("000") == RequestCount`.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Full order context |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE | INTX response |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Activity state and response array |

### §19.3 — ResponseBase Construction

```text
createObject
└── object (ResponseBase)
    ├── @extId              ← $extId (OMXUtils:generateTrackingID())   [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode              [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg               [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus          [Conditional]
    └── ReferenceId         ← $eventResponse/RefID                     [Conditional]
```

### §19.4 — Response Side Effects & Fan-in

**Data extraction:**
- `subStatus` ← `payload/xsd5:getPrimaryKeyListWithoutResourceTypeResponse/xsd5:return/xsd5:primaryKeyList/xsd5:primaryKeyInfoArray[1]/xsd5:productStatus`
- `subscriberId` ← `payload/.../xsd5:primaryKeyInfoArray[1]/xsd5:productId`

**Working memory writes:**
- `subscriber.SubscriberId = subscriberId`
- Appends `CRM_SUB_STATUS = subStatus` to `subscriber.ExtendedInfo[]`

**Fan-in:**
```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"]) == RequestCount
→ "true" (advance flow) | "false" (wait)
```

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| AUDIT_TRACE | "Response received for INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE" |
| PROCESS_ID | `_RES` suffix |
| OPERATION_NAME | "INTX_GET_PK_LIST_WITHOUT_RESOURCE_TYPE" |

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
