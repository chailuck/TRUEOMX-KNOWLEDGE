# Request_OMX_REMOVE_FUT_OFFER_COP

OMX Future Offer COP Removal — 4-Scope Parallel Fan-Out (POU Agreement / POU Subscriber / COU Agreement / COU Subscriber)

**Rule:** OMXFM | **Priority:** 5 | **Backend:** OMX-FM (Future Order Service) | **Author:** malinee-sririrom | **Dispatch:** sendEventImmediate (parallel)

---

## §1 — Overview & Purpose

Removes future COP (Call Order Plan) SOC entries from the OMX Future Order Service. Iterates all offers across four entity scopes (ParentOU Agreement, ParentOU Subscriber, ChildOU Agreement, ChildOU Subscriber) and sends one `OMX_REMOVE_FUT_OFFER_COP` event per qualifying offer in parallel. Each event targets a specific future SOC by `code` (SOC code) and optionally by `futureOrderId` and `instanceId`.

> **FE_OR_CCBS filter:** Before each event is sent, the rule reads `offer.ExtendedInfo[Name="FE_OR_CCBS"]/Value` as a filter context, passed into the PreExecCheck XML builder — allowing the PreExecCheck XPath to discriminate between FE and CCBS future offers.

> **Resubmit-safe:** Before sending a request, the rule scans existing `currActivity.Response[]` entries. If a response with matching `ReferenceId` and `CompletionStatus == 2` (success) already exists, the request is skipped (prevents duplicate removal on retry).

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_REMOVE_FUT_OFFER_COP` |
| Backend system | OMX-FM (Future Order / COP Service) |
| Outbound event | `Events.OMConsumers.OMXFM.Request.OMX_REMOVE_FUT_OFFER_COP` |
| Response event | `Events.OMConsumers.OMXFM.Response.OMX_REMOVE_FUT_OFFER_COP` |
| Response concept | `Concepts.FM.Response.OMX_RemoveFutureCopRes` |
| Dispatch pattern | Direct `sendEventImmediate` — parallel fan-out, one event per qualifying offer |
| Fan-in criterion | `RequestCount == count(Response[ResponseCode ends with "000"])` |
| Payload root schema | `ns1:futureOrderAll` — FutureSocCop.xsd |

---

## §2 — Rule Metadata & Attributes

| Property | Value |
|----------|-------|
| Namespace | `Rules.OMConsumers.OMXFM.Request` |
| Rule file | `Request_OMX_REMOVE_FUT_OFFER_COP.rule` |
| Priority | 5 |
| forwardChain | true |
| Author | malinee-sririrom |
| RequestCount increment | Per qualifying offer sent (all scopes combined), only if `!isActResub` |
| @extId on outbound events | None — BE auto-generates |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order request |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — read PreExecCheck, Response[], RequestCount; update Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Binds activity to this order |
| 2 | `orderCurrentActivity.ActivityID == "OMX_REMOVE_FUT_OFFER_COP"` | Restricts to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_REMOVE_FUT_OFFER_COP"` | Confirms process flow position |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Prevents re-processing |

---

## §5 — Execution Flow

1. Check resubmit: `isActResub = RequestCount > 0 && IsOrderResubmitted`
2. Fetch `nextAct = Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")`
3. **Scope 1 — POU Agreement Offers:** for each `ParentOU[i].Agreement.Offers[o]` where `Agreement != null`:
   - Read `filter = offer.ExtendedInfo[Name="FE_OR_CCBS"]/Value`
   - If PreExecCheck: build context via `GetXMLForAgreementOfferFilterWithExtendedInfo` → evaluate
   - If `chkRes == "true"` AND no successful response for `pAgRefId`: send event, `RequestCount++`
4. **Scope 2 — POU Subscriber Offers:** for each `ParentOU[i].Subscriber[j].SubscriberOffers[l]`:
   - Read `filterS = offer.ExtendedInfo[Name="FE_OR_CCBS"]/Value`
   - If PreExecCheck: build context via `GetXMLForSubscriberOfferFilterWithExtendedInfo` → evaluate
   - If `chkRes == "true"` AND no successful response for `refId`: send event, `RequestCount++`
5. **Scope 3 — COU Agreement Offers:** same pattern as Scope 1 with `childOuRefId`
6. **Scope 4 — COU Subscriber Offers:** same pattern as Scope 2 but with `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo`; **see bug note in §6**
7. If at least one event sent (`!isSkipped`): set Status=PROCESSING, `SendDataToDB`
8. Else: `SkipActivity(..., "4")`
9. On exception: `HandleActivityException()`

---

## §6 — Rule Action (THEN) — Key Details

### §6.1 — PreExecCheck Evaluation (per offer)

Unlike most FMs that evaluate PreExecCheck once, this FM re-evaluates it **per offer** using a scope-specific XML context. Four different helper functions build different context XMLs depending on whether the offer belongs to an Agreement or a Subscriber, and whether it is at POU or COU level.

### §6.2 — Resubmit Safety (per RefId)

Before sending each request, the rule scans `orderCurrentActivity.Response[]` for a matching `ReferenceId` with `CompletionStatus == 2`. If found, `reqSuccess = true` and the event is skipped for that scope.

### §6.3 — BUG — COU Subscriber Inner Loop Condition

> **[HIGH]** In the ChildOU Subscriber SubscriberOffers loop (Scope 4):
> ```java
> for(int m=0; j<offerLen; m++) {  // BUG: condition is 'j' not 'm'
> ```
> The loop counter is `m` but the termination condition checks `j` (the outer subscriber loop variable). This causes an `ArrayIndexOutOfBoundsException` when `m >= offerLen`, caught by the outer try/catch and routed to `HandleActivityException`. **COU Subscriber offers are never processed** in this rule as a result.

### §6.4 — Payload Differences Between Scopes

| Field | Scope 1 (POU Agr) | Scope 2 (POU Sub) | Scope 3 (COU Agr) | Scope 4 (COU Sub) |
|-------|-------------------|-------------------|-------------------|-------------------|
| `ns:futureOrderId` | Conditional — from `FUT_ORDER_ID` ExtendedInfo | same | same | same |
| `ns2:code` | `pagof.Soc` | `subOff.Soc` | `pagof.Soc` | `subOff.Soc` |
| `ns2:instanceId` | absent | `subOff.OfferInstanceId` (conditional) | absent | `subOff.OfferInstanceId` (conditional) |
| `ns2:extendedInfo[]` | `pagof.ExtendedInfo[]` (all) | `subOff.ExtendedInfo[]` (all) | same | same |
| Reference ID | `pAgRefId` (POU Agreement.RefId) | `refId` (Subscriber.RefId) | `childOuRefId` | `refId` (COU Subscriber.RefId) |

### §6.5 — Audit Log Gate

The request logger is gated on `RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)` — not the standard WritePayload flag. Some order types will not produce any request audit log.

---

## §8 — System & Integration Dependencies

### §8.2 — ESB / JMS Channel Dependencies

| Event | Direction | Backend | Count |
|-------|-----------|---------|-------|
| `OMX_REMOVE_FUT_OFFER_COP` (request) | [OUTBOUND] | OMX-FM Future COP Service | One per qualifying offer |
| `OMX_REMOVE_FUT_OFFER_COP` (response) | [INBOUND] | OMX-FM → BE | One per sent event |

### §8.3 — Backend API & Schemas

| Prefix | Namespace | Root element |
|--------|-----------|-------------|
| `ns1` | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureSocCop.xsd` | `ns1:futureOrderAll` (payload root) |
| `ns` | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd` | `ns:futureOrder` |
| `ns2` | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureSoc.xsd` | `ns2:futureSoc` |

### §8.5 — ExtendedInfo Fields Read

| Name | Source | Usage |
|------|--------|-------|
| `FE_OR_CCBS` | `offer.ExtendedInfo[Name="FE_OR_CCBS"]/Value` | Passed as `filter`/`filterS` to PreExecCheck XML builder |
| `FUT_ORDER_ID` | `orderRequest.OrderData.ExtendedInfo[Name="FUT_ORDER_ID"]/Value` | Written to `ns:futureOrderId` in payload (conditional) |

---

## §9 — Detailed Payload Build

### §9.3 — JMS / Event Header Fields (common to all scopes)

| Header | Source | Condition |
|--------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Conditional |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Conditional |
| `UserName` | `$orderRequest/OrderData/User` | Conditional |
| `PassWord` | `$orderRequest/OrderData/Password` | Conditional |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Conditional |

*Note: RefID header is NOT included in any scope's XSLT for this FM.*

### §9.7 — Complete Generated XML Example (Scope 2 — POU Subscriber)

```xml
<createEvent><event>
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>TRK-2026-001</JMSCorrelationID>
  <OrderID>ORD-12345</OrderID>
  <UserName>agent01</UserName>
  <PassWord>***</PassWord>
  <OrderType>5</OrderType>
  <payload>
    <ns1:futureOrderAll xmlns:ns1="...FutureSocCop.xsd" xmlns:ns="...FutureOrder.xsd" xmlns:ns2="...FutureSoc.xsd">
      <ns:futureOrder>
        <ns:futureOrderId>1001</ns:futureOrderId>  <!-- from FUT_ORDER_ID ExtendedInfo -->
      </ns:futureOrder>
      <ns2:futureSoc>
        <ns2:code>VOICE_CF</ns2:code>
        <ns2:instanceId>INS-001</ns2:instanceId>  <!-- subOff.OfferInstanceId, conditional -->
        <ns2:extendedInfo><ns2:name>FE_OR_CCBS</ns2:name><ns2:value>FUT</ns2:value></ns2:extendedInfo>
      </ns2:futureSoc>
    </ns1:futureOrderAll>
  </payload>
</event></createEvent>
```

### §9.8 — XSLT Source — Scope 2 (POU Subscriber Offers) — canonical variant

```xml
<xsl:stylesheet
    xmlns:ns2="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureSoc.xsd"
    xmlns:ns1="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureSocCop.xsd"
    xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="i"/>      <!-- POU index -->
  <xsl:param name="j"/>      <!-- Subscriber index -->
  <xsl:param name="subOff"/> <!-- SubscriberOffers concept instance -->
  <xsl:template match="/">
    <createEvent><event>
      <!-- JMS headers: JMSPriority, JMSCorrelationID, OrderID, UserName, PassWord, OrderType (all conditional) -->
      <payload>
        <ns1:futureOrderAll>
          <ns:futureOrder>
            <xsl:if test="$orderRequest/OrderData/ExtendedInfo[Name='FUT_ORDER_ID']/Value">
              <ns:futureOrderId>
                <xsl:value-of select="$orderRequest/OrderData/ExtendedInfo[Name='FUT_ORDER_ID']/Value"/>
              </ns:futureOrderId>
            </xsl:if>
          </ns:futureOrder>
          <ns2:futureSoc>
            <ns2:code><xsl:value-of select="$subOff/Soc"/></ns2:code>
            <xsl:if test="$subOff/OfferInstanceId">
              <ns2:instanceId><xsl:value-of select="$subOff/OfferInstanceId"/></ns2:instanceId>
            </xsl:if>
            <xsl:for-each select="$subOff/ExtendedInfo">
              <ns2:extendedInfo>
                <ns2:name><xsl:value-of select="Name"/></ns2:name>
                <ns2:value><xsl:value-of select="Value"/></ns2:value>
              </ns2:extendedInfo>
            </xsl:for-each>
          </ns2:futureSoc>
        </ns1:futureOrderAll>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

*Scopes 1 and 3 (Agreement offers) differ: `$pagof` instead of `$subOff`, no `ns2:instanceId` element.*

---

## §10 — XSLT Field Mapping — Output Event Tree Hierarchy

```text
createEvent                        [no @extId — BE auto-generates]
└── event
    ├── JMSPriority                ← $orderRequest/OrderPriority                   [Conditional]
    ├── JMSCorrelationID           ← $orderRequest/OrderData/OMXTrackingId         [Conditional]
    ├── OrderID                    ← $orderRequest/OrderData/OrderID               [Conditional]
    ├── UserName                   ← $orderRequest/OrderData/User                  [Conditional]
    ├── PassWord                   ← $orderRequest/OrderData/Password              [Conditional]
    ├── OrderType                  ← $orderRequest/OrderData/OrderType             [Conditional]
    └── payload
        └── ns1:futureOrderAll                                                     [Always]
            ├── ns:futureOrder                                                     [Always]
            │   └── ns:futureOrderId  ← OrderData.ExtendedInfo[FUT_ORDER_ID]/Value [Conditional]
            └── ns2:futureSoc                                                      [Always]
                ├── ns2:code          ← offer.Soc (pagof or subOff)               [Always]
                ├── ns2:instanceId    ← subOff.OfferInstanceId                    [Conditional — Subscriber scopes only]
                └── ns2:extendedInfo[] ← for-each offer.ExtendedInfo              [Conditional — if ExtendedInfo present]
                    ├── ns2:name      ← ExtendedInfo/Name
                    └── ns2:value     ← ExtendedInfo/Value
```

---

## §11 — Audit Logging

**Request logger** (gated on `AllowWriteLog(orderType)` — not WritePayload):

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_REQ")` |
| OPERATION_NAME | `"OMX_REMOVE_FUT_OFFER_COP"` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `concat("Request Sent for RefId: ", $refId)` — varies by scope |
| payload | Conditional on `WritePayload="true"` — includes `$reqEvent` |

**Response logger** (in response RF):

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"OMX_REMOVE_FUT_OFFER_COP"` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `"Response received for OMX_REMOVE_FUT_OFFER_COP_DATE"` ⚠ spurious "_DATE" suffix — copy-paste error |
| payload | Conditional on `WritePayload="true"` — includes `$eventResponse` |

---

## §12 — Activity Status Management

| Scenario | Action | Status |
|----------|--------|--------|
| At least one event sent | `GetActivityStatusString("1", false)`; `SendDataToDB` | PROCESSING |
| All offers filtered/skipped | `SkipActivity(orderRequest, activity, "4")` | SKIPPED |
| All responses received (fan-in) | Response RF returns "true" → next activity | COMPLETED |
| Exception | `HandleActivityException(orderRequest, activity, ae, "")` | ERROR |

---

## §13 — Exception / Error Handling

Single outer `try/catch(Exception ae)` wraps all four scope loops. The loop variable bug in Scope 4 (§6.3) will cause an `ArrayIndexOutOfBoundsException` which is caught here and routes to `HandleActivityException`.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")` | Retrieves current activity concept for PreExecCheck |
| `GetXMLForAgreementOfferFilterWithExtendedInfo(orderRequest, refId, soc, filter)` | Builds PreExecCheck XML context for Agreement offers (POU and COU) |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, soc, filterS)` | Builds PreExecCheck XML context for POU Subscriber offers |
| `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, refId, soc, parentRefId, filterS)` | Builds PreExecCheck XML context for COU Subscriber offers |
| `RuleFunctions.Helpers.AllowWriteLog(orderType)` | Gates whether to fire the request audit logger for this order type |
| `RuleFunctions.Helpers.GetActivityStatusString("1", false)` | Returns PROCESSING status string |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | Persists order state to DB |
| `RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")` | Marks activity SKIPPED |
| `RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")` | Error handler |

---

## §15 — Function Dependency Tree

```text
Request_OMX_REMOVE_FUT_OFFER_COP (THEN block)
├── Instance.getByExtIdByUri(NextActivityName, ...)
├── [Scope 1] POU Agreement.Offers loop
│   ├── XPath.evalAsString("$pagof/ExtendedInfo[Name='FE_OR_CCBS']/Value")
│   ├── GetXMLForAgreementOfferFilterWithExtendedInfo(orderRequest, pAgRefId, soc, filter)
│   ├── XPath.execute("/("+chkXPath+")", sXML, ...)       [PreExecCheck]
│   └── [if chkRes=true && !reqSuccess]
│       ├── Event.createEvent(Scope 1 XSLT) → sendEventImmediate
│       ├── RequestCount++  [if !isActResub]
│       └── AllowWriteLog() → sendEventImmediate(Logger)
├── [Scope 2] POU Subscriber.SubscriberOffers loop
│   ├── XPath.evalAsString("$subOff/ExtendedInfo[Name='FE_OR_CCBS']/Value")
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, soc, filterS)
│   └── ... (same send + log pattern)
├── [Scope 3] COU Agreement.Offers loop (same as Scope 1 with childOuRefId)
├── [Scope 4] COU Subscriber.SubscriberOffers loop
│   ├── [BUG] loop condition uses j not m → exception on m>=offerLen
│   └── GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...)
├── [if !isSkipped] GetActivityStatusString("1", false) + SendDataToDB
├── [if isSkipped] SkipActivity("4")
└── [catch] HandleActivityException()

Response_OMX_REMOVE_FUT_OFFER_COP (body)
├── OMXUtils.generateTrackingID()
├── Instance.createInstance(OMX_RemoveFutureCopRes XSLT)
│   └── maps: ResponseCode, ResponseMessage, CompletionStatus, ReferenceId ← RefID
├── currActivity.Response[length] = activityRes
├── Event.Ext.sendEventImmediate(Logger RES)
├── XPath.evalAsInt("count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)='000'])")
└── return "true" if RequestCount == successResponseCount, else "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Remove future COP SOC entries for all qualifying offers across POU Agreement, POU Subscriber, COU Agreement, and COU Subscriber scopes |
| R2 | Payload must carry futureOrderId (conditional from FUT_ORDER_ID), SOC code, instanceId (Subscriber offers only, conditional), and all ExtendedInfo entries |
| R3 | PreExecCheck must be evaluated per offer using the FE_OR_CCBS filter value from that offer's ExtendedInfo |
| R4 | Requests already successfully completed (CompletionStatus==2 in Response) must not be resent on resubmit |
| R5 | Fan-in: all responses received with ResponseCode ending in "000" must equal RequestCount before advancing |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| **COU Subscriber offers never processed** — loop bug: `for(int m=0; j<offerLen; m++)` uses `j` not `m` in termination condition → ArrayIndexOutOfBoundsException | [HIGH] | Fix loop condition to `m < offerLen` in source code; test with COU Subscriber offers present |
| AUDIT_TRACE in response logger has spurious "_DATE" suffix: `"Response received for OMX_REMOVE_FUT_OFFER_COP_DATE"` | [MEDIUM] | Fix AUDIT_TRACE string in response RF |
| No RefID header in outbound event — backend cannot correlate response to specific entity without scanning all responses | [MEDIUM] | Add RefID header (pAgRefId / subscriber.RefId / childOuRefId) to each event variant's XSLT |
| Per-offer PreExecCheck evaluation is O(n) with XML serialization per offer — slow for large orders | [LOW] | Consider caching PreExecCheck result per RefId or batching future SOC removals |
| Audit log gated on `AllowWriteLog(orderType)` not standard WritePayload — some order types produce no request audit trail | [LOW] | Align logging gate to standard WritePayload flag in migration |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author malinee-sririrom
 */
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_REMOVE_FUT_OFFER_COP {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "OMX_REMOVE_FUT_OFFER_COP";
        orderRequest.ProcessFlow.NextActivityID == "OMX_REMOVE_FUT_OFFER_COP";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            boolean isSkipped = true;
            Activity nextAct = Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, ...);
            String chkXPath = nextAct.PreExecCheck;
            String chkRes = "true";

            // [Scope 1] POU Agreement Offers
            for(int i = 0; i < orderRequest.OrderData.Customer.ParentOU@length; i++) {
                ParentOU parentOU = orderRequest.OrderData.Customer.ParentOU[i];
                if(parentOU.Agreement != null) {
                    for(int o = 0; o < parentOU.Agreement.Offers@length; o++) {
                        String pAgRefId = parentOU.Agreement.RefId;
                        AgreementOffers pagof = parentOU.Agreement.Offers[o];
                        String filter = XPath.evalAsString("$pagof/ExtendedInfo[Name='FE_OR_CCBS']/Value");
                        if(String.length(nextAct.PreExecCheck) > 0) {
                            sXML = GetXMLForAgreementOfferFilterWithExtendedInfo(orderRequest, pAgRefId, pagof.Soc, filter);
                            chkRes = XPath.execute(...);
                        }
                        if(String.equals(chkRes, "true")) {
                            boolean reqSuccess = /* scan Response[] for pAgRefId + CompletionStatus==2 */;
                            if(!reqSuccess) {
                                Events... reqEvent = Event.createEvent(/* Scope 1 XSLT — see §9.8 */);
                                Event.Ext.sendEventImmediate(reqEvent);
                                if(!isActResub) { orderCurrentActivity.RequestCount++; isSkipped = false; }
                                if(AllowWriteLog(orderRequest.OrderData.OrderType)) {
                                    Event.Ext.sendEventImmediate(Event.createEvent(/* Logger — see §11 */));
                                }
                            }
                        }
                    }
                }

                // [Scope 2] POU Subscriber Offers
                for(int j = 0; j < parentOU.Subscriber@length; j++) {
                    String refId = parentOU.Subscriber[j].RefId;
                    for(int l = 0; l < parentOU.Subscriber[j].SubscriberOffers@length; l++) {
                        // same pattern — see §9.8 Scope 2 XSLT; includes ns2:instanceId
                    }
                }

                // [Scope 3] COU Agreement + [Scope 4] COU Subscriber
                for(int k = 0; k < parentOU.ChildOU@length; k++) {
                    // Scope 3: ChildOU.Agreement.Offers — same as Scope 1 with childOuRefId
                    for(int j = 0; j < parentOU.ChildOU[k].Subscriber@length; j++) {
                        int offerLen = parentOU.ChildOU[k].Subscriber[j].SubscriberOffers@length;
                        for(int m = 0; j < offerLen; m++) { // BUG: 'j' should be 'm' — see §6.3
                            // Scope 4: same as Scope 2 with GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo
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

Maps the `OMX_REMOVE_FUT_OFFER_COP` response event to an `OMX_RemoveFutureCopRes` concept, appends it to `currActivity.Response[]`, logs the result, and returns `"true"` when all parallel requests have completed successfully.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order request |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_REMOVE_FUT_OFFER_COP` | Inbound removal result event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity being responded to |

### §19.3 — ResponseBase Concept Construction (OMX_RemoveFutureCopRes)

```text
createObject
└── object
    ├── @extId           ← OMXUtils.generateTrackingID()           [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode             [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg              [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus         [Conditional]
    └── ReferenceId      ← $eventResponse/RefID                    [Conditional]
```

### §19.4 — Response Completion Logic

| Step | Expression | Return |
|------|-----------|--------|
| Count successes | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` | `successResponseCount` |
| Fan-in check | `currActivity.RequestCount == successResponseCount` | `"true"` = all done; `"false"` = still waiting |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
