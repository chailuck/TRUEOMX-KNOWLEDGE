# Request_OMX_GET_SHAREPLAN_OU_SOC_REMOVE

## §1 — Overview & Purpose

This rule fires during the **CHANGE_PP** (Change Price Plan) order flow when a subscriber belongs to a *shareplan* (ParentOU) arrangement and the *old* price-plan SOC needs to be identified for removal. It queries the OMX internal service `OMX_GET_SHAREPLAN_OU_SOC` with the subscriber's current ServiceType-80 offer details to retrieve the associated SOC metadata from the OU-level plan configuration.

The **REMOVE** variant specifically looks up which SOC is currently configured on the ParentOU agreement so that the response handler can append `Action=REMOVE` entries to the order's `Agreement.Offers[]` array, driving the downstream CCBS offer-removal steps.

> The rule parameter (from `Parameter[1]`) controls which FE_OR_CCBS tag type to match when finding the relevant SubscriberOffer — defaults to `"FE"` if no parameter is provided. In the CHANGE_PP ProcessConfig this step is configured with parameter `CCBS`.

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule path | `Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_SHAREPLAN_OU_SOC_REMOVE` |
| Priority | 5 |
| ForwardChain | true |
| ActivityID guard | `OMX_GET_SHAREPLAN_OU_SOC_REMOVE` |
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
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches the activity instance to the order's next step pointer |
| 2 | `orderCurrentActivity.ActivityID == "OMX_GET_SHAREPLAN_OU_SOC_REMOVE"` | Guards this rule to the specific activity type |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_GET_SHAREPLAN_OU_SOC_REMOVE"` | Double-checks the process flow pointer matches |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires when the activity has not yet been dispatched |

## §5 — Execution Flow Diagram

1. Read `param` from `Parameter[1]` (default `"FE"`) — controls FE_OR_CCBS value to match
2. Check `isActResub`: if resubmit, call `PurgePendingRequestsBeforeResubmit`
3. Outer loop: iterate `ParentOU[p]` (all parent OUs in order)
4. Inner loop: iterate `Subscriber[j]` within each ParentOU
5. Check `reqSuccess`: if this subscriber's RefId already has a successful response (CompletionStatus==2), skip
6. Evaluate `PreExecCheck` XPath against subscriber XML — skip if false
7. Scan `SubscriberOffers[]` for offers matching `FE_OR_CCBS=$param` AND `ServiceType='80'` — extract `ppMainSub` (OfferName) and `ppMainId` (Soc)
8. If matching offer found (`ppMainSub != ""`): build and send `OMX_GET_SHAREPLAN_OU_SOC` JMS event
9. Send audit log event; increment `RequestCount` (if not resubmit); set `isSkipped = false`
10. Post-loop: if any request sent → set Status="1" (PROCESSING), persist to DB; else → `SkipActivity` with code "4"
11. On exception: `HandleActivityException`

## §6 — Rule Action (THEN) — Detailed Logic

### Resubmit handling

If `isActResub` is true (RequestCount > 0 and order was resubmitted), `PurgePendingRequestsBeforeResubmit` is called to clear pending requests before re-sending.

### Offer matching

For each Subscriber, the rule iterates all `SubscriberOffers` and evaluates an XPath condition:

```xpath
($currSubOffer/ExtendedInfo[Name='FE_OR_CCBS']/Value = $param)
and ($currSubOffer/ServiceType = '80')
```

If matched, it extracts `OfferName → ppMainSub` and `Soc → ppMainId`.

### Request dispatch

Only when `ppMainSub != ""` does the rule build and dispatch the request event using `Event.Ext.sendEventImmediate(reqEvent)`.

> **[MEDIUM] IntraActivitySequencing bypass:** The `ActionRequestEvent` helper call is commented out, and direct `sendEventImmediate` is used instead. This bypasses the standard fan-out tracking mechanism. The RequestCount is still incremented manually, but the response correlation may behave differently from other FM rules that use the standard IntraActivitySequencing pattern.

### Status assignment

| Condition | Status code | Meaning |
|-----------|-------------|---------|
| At least one request sent | `"1"` → PROCESSING | Awaiting async response(s) |
| No subscriber matched / all already complete | `"4"` → SKIPPED | Activity skipped, advance to next |
| Exception thrown | Error handling path | `HandleActivityException` |

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

This rule fires during **CHANGE_PP** orders where the subscriber participates in a shareplan (ParentOU arrangement). The response handler has specialised logic for `OrderType == "11002"` (share-plan main subscriber path).

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_GET_SHAREPLAN_OU_SOC` | Query OMX for shareplan OU SOC info given SocName & SocId |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.OMX_GET_SHAREPLAN_OU_SOC` | Response containing ShareplanOUSocInfoArray |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | Audit log for request and response |

### §8.3 Backend API Details

| System | Operation | Schema | Notes |
|--------|-----------|--------|-------|
| OMX FM | GetShareplanOUSocInfo | `GetShareplanOUSocInfoRequest.xsd` / `GetShareplanOUSocInfoResponse.xsd` | Internal OMX service; returns array of ShareplanOUSocInfo with share_offer, service_type, price_plan fields |

### §8.4 BE Working Memory Dependencies

| Field | Read/Write | Purpose |
|-------|-----------|---------|
| `orderRequest.OrderData.Customer.ParentOU[p].Subscriber[j].SubscriberOffers[k]` | READ | Find ServiceType-80 offer with matching FE_OR_CCBS value |
| `orderCurrentActivity.Parameter[1]` | READ | FE_OR_CCBS param (default "FE"; ProcessConfig sets "CCBS") |
| `orderCurrentActivity.Response[iResp]` | READ | Check for prior successful response (reqSuccess guard) |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Incremented per request sent |
| `orderCurrentActivity.Status` | WRITE | Set to "1" (PROCESSING) or skip |
| `orderRequest.OrderData.Customer.ParentOU[iPOU].Agreement.Offers[]` | WRITE (response) | Response appends AgreementOffers with Action=REMOVE |

### §8.5 ExtendedInfo Fields

| Name | Required | Where |
|------|----------|-------|
| `FE_OR_CCBS` | Required (match) | SubscriberOffers — matched against `$param` to find the PP offer |
| `SHAREPLAN_MAIN_NUMBER` | Optional (response) | OrderType 11002 path: absence identifies main subscriber |
| `SHAREPLAN_ACTION` | Optional (response) | OrderType 11002 path: presence identifies main subscriber |

### §8.6 Global Variable Dependencies

| Variable Path | Used For |
|--------------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Conditional: include UserName/Password in request event |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `OMX_OM/WritePayload` | Conditional: include full payload in audit log |

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Parameter | Bound From |
|-----------|-----------|
| `$orderRequest` | `orderRequest` concept |
| `$refId` | `orderRequest.OrderData.Customer.ParentOU[p].Subscriber[j].RefId` |
| `$globalVariables` | BE global variables |
| `$ppMainSub` | Extracted OfferName of the ServiceType-80 offer matching `FE_OR_CCBS=$param` |
| `$ppMainId` | Extracted Soc of the same offer |

### §9.2 Event Container

Event type: `Events.OMConsumers.OMXFM.Request.OMX_GET_SHAREPLAN_OU_SOC`

### §9.3 JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$refId` | Always |
| `UserName` | `$orderRequest/OrderData/User` | If `IsEnableUserPass='true'` |
| `PassWord` | `$orderRequest/OrderData/Password` | If `IsEnableUserPass='true'` |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Always |

### §9.6 Core Payload

| Element | Source |
|---------|--------|
| `payload/ns:GetShareplanOUSocInfoRequest/ns:SocName` | `$ppMainSub` — OfferName of the matched ServiceType-80 offer |
| `payload/ns:GetShareplanOUSocInfoRequest/ns:SocId` | `$ppMainId` — Soc of the matched ServiceType-80 offer |

### §9.7 Complete Generated XML Example

```xml
<event>
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-20260914-001</JMSCorrelationID>
  <OrderID>ORD-12345</OrderID>
  <RefID>SUB-REF-001</RefID>
  <OrderType>11001</OrderType>
  <payload>
    <ns:GetShareplanOUSocInfoRequest
      xmlns:ns="http://services.omx.truecorp.co.th/GetShareplanOUSocInfoRequest.xsd">
      <ns:SocName>SHAREPLAN_OFFER_AAAA</ns:SocName>
      <ns:SocId>12345678</ns:SocId>
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
  <xsl:param name="orderRequest"/>    <!-- full order request concept -->
  <xsl:param name="refId"/>           <!-- Subscriber[j].RefId -->
  <xsl:param name="globalVariables"/>
  <xsl:param name="ppMainSub"/>       <!-- OfferName of matched ServiceType-80 offer -->
  <xsl:param name="ppMainId"/>        <!-- Soc of matched ServiceType-80 offer -->
  <xsl:template match="/">
    <createEvent>
      <event>
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <RefID><xsl:value-of select="$refId"/></RefID>
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
    ├── JMSPriority          ← $orderRequest/OrderPriority                [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId      [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID             [Always]
    ├── RefID                ← $refId                                      [Always]
    ├── UserName             ← $orderRequest/OrderData/User                [Conditional: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password            [Conditional: IsEnableUserPass='true']
    ├── OrderType            ← $orderRequest/OrderData/OrderType           [Always]
    └── payload                                                            [Always]
        └── ns:GetShareplanOUSocInfoRequest  [ns=GetShareplanOUSocInfoRequest.xsd]
            ├── ns:SocName   ← $ppMainSub  (OfferName of ServiceType-80 offer)  [Always]
            └── ns:SocId     ← $ppMainId   (Soc of ServiceType-80 offer)        [Always]
```

**Legend:** `[Always]` = emitted unconditionally · `[Conditional: ...]` = inside xsl:if · Green source = XPath expression · Orange source = static/literal value

## §11 — Audit Logging

### Request Audit Log

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(System.nanoTime(), "_REQ")` |
| OPERATION_NAME | `"OMX_GET_SHAREPLAN_OU_SOC_REMOVE"` (static) |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `concat("Request Sent for RefId ", $refId)` |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | Conditional: copy of `$reqEvent` if `WritePayload="true"` |

### Response Audit Log

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(System.nanoTime(), "_RES")` |
| OPERATION_NAME | `"OMX_GET_SHAREPLAN_OU_SOC_REMOVE"` (static) |
| AUDIT_TRACE | `"Response received for OMX_GET_SHAREPLAN_OU_SOC"` (static) |
| AUDIT_TS | `tib:format-dateTime(...)` |
| payload | Conditional: copy of `$eventResponse` if `WritePayload="true"` |

## §12 — Activity Status Management

| Code | String | When |
|------|--------|------|
| "1" | PROCESSING | At least one request sent; awaiting responses |
| "4" | SKIPPED | No matching offer found for any subscriber — activity skipped |
| Error | ERROR | Exception caught → `HandleActivityException` |

## §13 — Exception / Error Handling

A top-level `try/catch(Exception ae)` block wraps all logic. On exception: `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` is called with an empty detail string.

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` | Clears pending requests from prior run when order is resubmitted |
| `RuleFunctions.Helpers.GetXMLForSubscriber` | Serialises a subscriber's data as XML string for XPath PreExecCheck evaluation |
| `RuleFunctions.Helpers.GetActivityStatusString` | Maps numeric status code to string ("1" → PROCESSING, "4" → SKIPPED) |
| `RuleFunctions.Helpers.SendDataToDB` | Persists order state to DB |
| `RuleFunctions.Helpers.SkipActivity` | Marks activity as skipped and advances flow |
| `RuleFunctions.Helpers.HandleActivityException` | Handles exceptions — logs error, sets ERROR status |

## §15 — Function Dependency Tree

```text
Request_OMX_GET_SHAREPLAN_OU_SOC_REMOVE
├── RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── RuleFunctions.Helpers.GetXMLForSubscriber  [per subscriber, if PreExecCheck present]
├── Event.Ext.sendEventImmediate (OMX_GET_SHAREPLAN_OU_SOC)  [per matching subscriber]
├── Event.Ext.sendEventImmediate (Logger)  [audit]
├── RuleFunctions.Helpers.GetActivityStatusString
├── RuleFunctions.Helpers.SendDataToDB
├── RuleFunctions.Helpers.SkipActivity  [if no requests sent]
└── RuleFunctions.Helpers.HandleActivityException  [on error]
```

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1:** For each ParentOU subscriber with an active ServiceType-80 offer matching the configured FE_OR_CCBS parameter, query OMX for that offer's shareplan SOC metadata.
- **R2:** Skip subscribers already having a successful prior response (reqSuccess guard).
- **R3:** If no eligible subscriber is found, skip the activity.
- **R4:** Response handler must write REMOVE AgreementOffers back to ParentOU with FE_OR_CCBS=FE and OFFER_LEVEL=PARENT for OrderType != 11002.
- **R5:** For OrderType 11002 (share-plan main subscriber), write AgreementOffers with FE_OR_CCBS=FE and CONFIG_FROM_PP (conditional on price_plan presence).

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| IntraActivitySequencing.ActionRequestEvent is commented out; direct sendEventImmediate used instead | [MEDIUM] | Verify response correlation is handled correctly without the fan-out tracking helper; test multi-subscriber scenarios |
| Param defaults to "FE" if Parameter[1] is absent — CHANGE_PP configures "CCBS"; mismatched parameter would silently fail to find offers | [MEDIUM] | Validate that ProcessConfig always provides the correct parameter value |
| Response: SubscriberOffers write-back is fully commented out — only AgreementOffers are updated | [LOW] | Intentional for CHANGE_PP; confirm this is not needed for other order types using this FM |
| debugOut statements left in response rulefunction (production noise) | [LOW] | Remove before production or gate behind log-level check |

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_SHAREPLAN_OU_SOC_REMOVE {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_GET_SHAREPLAN_OU_SOC_REMOVE";
    orderRequest.ProcessFlow.NextActivityID == "OMX_GET_SHAREPLAN_OU_SOC_REMOVE";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    try {
      boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
      boolean isSkipped = true;
      if (isActResub) {
        RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      }
      // Read param from Parameter[1], default "FE"
      String param = XPath.evalAsString("xpath://...if($orderCurrentActivity/Parameter[1]) then ($orderCurrentActivity/Parameter[1]) else ('FE')...");
      int pOuLen = orderRequest.OrderData.Customer.ParentOU@length;
      for (int p = 0; p < pOuLen; p++) {
        int iSubscriberLen = orderRequest.OrderData.Customer.ParentOU[p].Subscriber@length;
        for (int j = 0; j < iSubscriberLen; j++) {
          String refId = orderRequest.OrderData.Customer.ParentOU[p].Subscriber[j].RefId;
          // reqSuccess guard: skip if already successful response exists for this RefId
          boolean reqSuccess = false;
          for(int iResp=0; iResp<orderCurrentActivity.Response@length; iResp++) {
            if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, refId)
              && orderCurrentActivity.Response[iResp].CompletionStatus==2)
              reqSuccess = true;
          }
          if(!reqSuccess) {
            // Evaluate PreExecCheck and find ServiceType-80 offer matching FE_OR_CCBS=$param
            String ppMainSub = "";
            String ppMainId = "";
            for(int k=0; k<iSubOffCnt; k++) {
              // XPath: FE_OR_CCBS=$param AND ServiceType='80'
              if(XPath match) { ppMainSub = OfferName; ppMainId = Soc; }
            }
            if(ppMainSub != "") {
              Events.OMConsumers.OMXFM.Request.OMX_GET_SHAREPLAN_OU_SOC reqEvent =
                Event.createEvent(/* XSLT: see §9.8 — GetShareplanOUSocInfoRequest with SocName=$ppMainSub, SocId=$ppMainId */);
              Event.Ext.sendEventImmediate(reqEvent);
              // RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity); // commented out
              Event.Ext.sendEventImmediate(Event.createEvent(/* Logger XSLT: OPERATION_NAME=OMX_GET_SHAREPLAN_OU_SOC_REMOVE, AUDIT_TRACE="Request Sent for RefId $refId" */));
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

The response rulefunction `Response_OMX_GET_SHAREPLAN_OU_SOC_REMOVE` processes the `OMX_GET_SHAREPLAN_OU_SOC` response event. It iterates through the returned `ShareplanOUSocInfoArray` and appends `AgreementOffers` entries (Action=REMOVE) back to the order's ParentOU Agreement, setting up the data needed by downstream CCBS offer-removal steps.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context — mutated by appending Agreement.Offers |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_GET_SHAREPLAN_OU_SOC` | Backend response with ShareplanOUSocInfoArray |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Tracks RequestCount vs successResponseCount for fan-in |

### §19.3 ResponseBase Concept Construction

```text
createObject  [Concepts.FM.Base.ResponseBase]
└── object
    ├── @extId           ← $eventResponse/@extId                      [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode                [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg                 [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus            [Conditional]
    └── ReferenceId      ← $eventResponse/RefID                       [Conditional]
```

### §19.4 Response Completion Logic

**Success XPath:**

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

**Fan-in condition:** `currActivity.RequestCount == successResponseCount`

- Returns `"true"` when all sent requests have received a "000"-suffix success response
- Returns `"false"` while still awaiting responses (partial fan-in)

### §19.5 Response Data Write-back

**OrderType 11002 (main subscriber path):**

| Field | Value |
|-------|-------|
| `OfferName` | `ns:share_offer` from response |
| `ServiceType` | `ns:service_type` from response |
| `Soc` | Looked up from existing Agreement.Offers by OfferName |
| `Action` | `"REMOVE"` (static) |
| `ExtendedInfo[FE_OR_CCBS]` | `"FE"` (static) |
| `ExtendedInfo[CONFIG_FROM_PP]` | `ns:price_plan` (conditional) |

**Other OrderTypes:**

| Field | Value |
|-------|-------|
| `OfferName` | `ns:share_offer` (conditional) |
| `ServiceType` | `ns:service_type` (conditional) |
| `Soc` | From existing Agreement.Offers matching by OfferName with FE_OR_CCBS=CCBS |
| `Action` | `"REMOVE"` (static) |
| `ExtendedInfo[FE_OR_CCBS]` | `"FE"` (static) |
| `ExtendedInfo[OFFER_LEVEL]` | `"PARENT"` (static) |
| `ExtendedInfo[SHARE_OFFER_DESC]` | `ns:share_offer_desc` (conditional: non-empty and non-"null") |

> **[NOTE]:** Only writes to `Agreement.Offers[]`; the commented-out SubscriberOffers write-back block is intentionally disabled for the CHANGE_PP flow.

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
