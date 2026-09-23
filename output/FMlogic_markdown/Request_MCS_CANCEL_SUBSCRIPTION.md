# Request_MCS_CANCEL_SUBSCRIPTION

TIBCO BusinessEvents FM Logic — MCS Cancel Subscription Request Handler

**Priority:** 5 | **ForwardChain:** true | **Backend:** MCS | **Operation:** CancelSubscription
**Dispatch:** sendEventImmediate (parallel) | **Fan-out:** per-offer (POU+COU) | **Fan-in:** ResponseCode suffix "000"
**Author:** Chayatorn Pan.

> **⚠ CRITICAL BUG — COU variant: `ns:cancel_reason` mapped to `$channel` instead of `$cancelReason`.**
> All COU requests will have the channel name (e.g., "OMX-WEB") as their cancel reason because `cancelReason` is not even declared as an XSLT parameter in the COU variant. **[HIGH]**

---

## §1 — Overview & Purpose

This rule fires when `MCS_CANCEL_SUBSCRIPTION` becomes the next activity. It sends one **MCS CancelSubscription** request per qualifying SubscriberOffer (POU and COU) to cancel a Mobile Content Service subscription — identified by the offer's OfferName as the pack code.

The correlation key `refId` is simply `subOff.OfferName` (not a composite POU/COU/sub key), which means if the same offer name appears on multiple subscribers, their responses share the same correlation key — a potential collision risk on resubmission.

Audit logging (request side) is gated by `AllowWriteLog(orderType)`. Response audit is always emitted. This asymmetry is noted for migration.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_MCS_CANCEL_SUBSCRIPTION` |
| Author | Chayatorn Pan. |
| Priority | 5 |
| ForwardChain | true |
| Target backend | MCS — Mobile Content Service |
| Operation | CancelSubscription |
| Payload schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/CancelSubscription.xsd` |
| Request event type | `Events.OMConsumers.OMXFM.Request.MCS_CANCEL_SUBSCRIPTION` |
| Response event type | `Events.OMConsumers.OMXFM.Response.MCS_CANCEL_SUBSCRIPTION` |
| Response concept | `Concepts.FM.Base.ResponseBase` (standard) |
| Dispatch method | `Event.Ext.sendEventImmediate` (parallel) |
| Fan-out granularity | Per offer per subscriber (POU and COU) — refId = OfferName |
| Fan-in mechanism | `count(Response[tib:right(tib:trim(ResponseCode), 3) = "000"]) == RequestCount` |
| Audit log gate (request) | `AllowWriteLog(orderType)` — conditional |
| Audit log gate (response) | Always logged |
| Activity parameter | `USE_ROWID_CRM` — drives `MapSubscriberIdFromCRM` |
| Skip trigger | No qualifying offers → SkipActivity("4") |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order; subscriber, offer, channel, and date data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step; Response[], RequestCount, Status, Parameters |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to order's next step |
| 2 | `orderCurrentActivity.ActivityID == "MCS_CANCEL_SUBSCRIPTION"` | Rule fires only for this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "MCS_CANCEL_SUBSCRIPTION"` | Double-check on ProcessFlow routing |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be in waiting state |

---

## §5 — Execution Flow Diagram

1. Compute `isActResub`; resolve `nextAct` PreExecCheck
2. **POU loop**: iterate ParentOU[i].Subscriber[j].SubscriberOffers[k]
3. Set `refId = subOff.OfferName` (correlation key — not composite)
4. Resubmission skip: check `Response[ReferenceId==refId and CompletionStatus==2]`
5. If not already succeeded: evaluate PreExecCheck per-offer via `GetXMLForSubscriberOffer`
6. If chkRes=="true": extract channel, cancelReason, pack_code, lang, cancelDate, useRowIdCrmParam
7. Compute `subIdCrm` via `MapSubscriberIdFromCRM(subscriber, useRowIdCrmParam)`
8. Build POU `MCS_CANCEL_SUBSCRIPTION` event (extId in XSLT via OMXUtils); `sendEventImmediate`
9. If AllowWriteLog: send audit log
10. If !isActResub: `RequestCount++`
11. **COU loop**: identical — but COU XSLT lacks `cancelReason` param; `ns:cancel_reason` maps to `$channel` **[BUG]**
12. If any dispatched: Status="1", SendDataToDB; else SkipActivity("4")
13. On exception: HandleActivityException

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### refId = OfferName (not composite key)

`refId = subOff.OfferName` — the correlation key for both resubmission skip and response matching. Unlike other FMs that build a composite key (`pOuRefId:cOuRefId:subRefId:offerName`), MCS_CANCEL_SUBSCRIPTION uses only the offer name.

### POU vs COU XSLT differences

> **COU cancel_reason bug:** The COU XSLT does not include `cancelReason` as a parameter. The `ns:cancel_reason` field is mapped to `$channel` instead. All COU requests will have the service channel name (e.g., "OMX-WEB") as their cancel reason. **[HIGH]**

| Field | POU XSLT | COU XSLT |
|-------|----------|----------|
| XSLT params | orderRequest, refId, msisdn, subIdCrm, channel, pack_code, **cancelReason**, cancelDate, lang, subOff | orderRequest, refId, msisdn, subIdCrm, channel, pack_code, cancelDate, lang, subOff (NO cancelReason) |
| ns:cancel_reason | `$cancelReason` (ActivityReason) | `$channel` **(BUG — channel name sent instead)** |

### Dead references

| Variable | Scope | Value | Issue |
|----------|-------|-------|-------|
| `transaction_id` | POU | `orderRequest.OrderData.OMXTrackingId` | Computed but never passed to XSLT **[MEDIUM]** |
| `method` | COU | `orderRequest.OrderData.OMXTrackingId` | Computed but never passed to XSLT **[MEDIUM]** |

### cancelDate formatting

`DateTime.format(orderRequest.SubmissionDate, "yyyy-MM-dd HH:mm:ss")` — uses the order submission date (not EffectiveDate).

### USE_ROWID_CRM activity parameter

`useRowIdCrmParam = GetActivityParameterValueFromKey(orderCurrentActivity, "USE_ROWID_CRM")` — drives `MapSubscriberIdFromCRM(subscriber, useRowIdCrmParam)`, which determines whether to send the CRM row ID or the default subscriber RefId as `ns:subscriber_id`.

### CANCEL_IMMEDIATE ExtendedInfo

The `ns:extra` block sends the `CANCEL_IMMEDIATE` ExtendedInfo: `key = ExtendedInfo[Name="CANCEL_IMMEDIATE"]/Name`, `value = ExtendedInfo[Name="CANCEL_IMMEDIATE"]/Value`. If absent, both are empty strings.

### Status transitions

| Scenario | Action | Status |
|----------|--------|--------|
| At least one request dispatched | Status="1", SendDataToDB | Running |
| No qualifying offers | SkipActivity("4") | Skip |
| Exception | HandleActivityException | Error |

---

## §7 — Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| refId | `subOff.OfferName` | Correlation key — OfferName only, not composite |
| msisdn | `subscriber.MSISDN` | ns:msisdn |
| channel | `orderRequest.OrderData.Channel` | ns:channel; also incorrectly used as ns:cancel_reason in COU |
| cancelReason | `subscriber.SubscriberActivityInfo.ActivityReason` | POU: ns:cancel_reason; COU: NOT passed to XSLT (bug) |
| pack_code | `subOff.OfferName` | ns:pack_code = same as refId |
| lang | `subscriber.SubscriberGeneralInfo.Language` | ns:lang |
| cancelDate | `DateTime.format(orderRequest.SubmissionDate, "yyyy-MM-dd HH:mm:ss")` | ns:cancel_date — uses submission date, not effective date |
| subIdCrm | `MapSubscriberIdFromCRM(subscriber, useRowIdCrmParam)` | ns:subscriber_id (conditional: if non-empty) |
| useRowIdCrmParam | `GetActivityParameterValueFromKey(activity, "USE_ROWID_CRM")` | From ProcessConfig activity Parameter |
| transaction_id (POU) | `orderRequest.OrderData.OMXTrackingId` | Dead reference — not passed to XSLT |
| method (COU) | `orderRequest.OrderData.OMXTrackingId` | Dead reference — not passed to XSLT |
| CANCEL_IMMEDIATE extra | `subOff.ExtendedInfo[Name="CANCEL_IMMEDIATE"]/Name + /Value` | ns:extra key/value — empty if absent |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Request audit log gated by `AllowWriteLog(orderType)`. No other order-type branching in the request logic.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Dispatch | Backend |
|-----------|-----------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.MCS_CANCEL_SUBSCRIPTION` | `Event.Ext.sendEventImmediate` | MCS — CancelSubscription |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `Event.Ext.sendEventImmediate` | Audit log (request: gated by AllowWriteLog; response: always) |

### §8.3 — Backend API Details

| System | Operation | Schema NS | Key Fields |
|--------|-----------|-----------|-----------|
| MCS | CancelSubscription | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/CancelSubscription.xsd` | transaction_id, method="cancel", msisdn, subscriber_id, channel, pack_code, cancel_reason, cancel_date, lang, extra (CANCEL_IMMEDIATE) |

### §8.4 — BE Working Memory Dependencies

| Concept Field | Access | Purpose |
|--------------|--------|---------|
| `subscriber.MSISDN` | READ | ns:msisdn |
| `subscriber.SubscriberActivityInfo.ActivityReason` | READ | cancelReason → ns:cancel_reason (POU only) |
| `subscriber.SubscriberGeneralInfo.Language` | READ | ns:lang |
| `subscriber.RefId` | READ | Passed to GetXMLForSubscriberOffer and MapSubscriberIdFromCRM |
| `subOff.OfferName` | READ | refId (correlation key) and ns:pack_code |
| `subOff.ExtendedInfo[Name="CANCEL_IMMEDIATE"]/Name+Value` | READ | ns:extra key/value pair |
| `orderRequest.OrderData.Channel` | READ | ns:channel; and (incorrectly) ns:cancel_reason in COU |
| `orderRequest.OrderData.OMXTrackingId` | READ | ns:transaction_id (conditional); JMSCorrelationID; audit ESBUUID |
| `orderRequest.OrderData.OrderID` | READ | JMS header OrderID |
| `orderRequest.OrderData.OrderType` | READ | JMS header OrderType; AllowWriteLog gate |
| `orderRequest.OrderPriority` | READ | JMSPriority |
| `orderRequest.SubmissionDate` | READ | cancelDate (formatted) |
| `orderCurrentActivity.Response[]` | READ | Resubmission skip check |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-in counter |
| `orderCurrentActivity.Status` | WRITE | Set to "1" after dispatch |

### §8.5 — ExtendedInfo Fields Required

| Name | Level | Required/Optional | Where Used |
|------|-------|-------------------|-----------|
| CANCEL_IMMEDIATE | Offer | Optional | ns:extra key/value — empty strings if absent; signals immediate vs deferred cancellation to MCS |

### §8.6 — Global Variable Dependencies

| Path | Usage |
|------|-------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Guards payload in audit log |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding (POU vs COU)

| XSLT Param | POU Bound From | COU Bound From |
|-----------|---------------|---------------|
| `$orderRequest` | orderRequest concept | orderRequest concept |
| `$refId` | subOff.OfferName | subOff.OfferName |
| `$msisdn` | subscriber.MSISDN | subscriber.MSISDN |
| `$subIdCrm` | MapSubscriberIdFromCRM(...) | MapSubscriberIdFromCRM(...) |
| `$channel` | orderRequest.OrderData.Channel | orderRequest.OrderData.Channel |
| `$pack_code` | subOff.OfferName | subOff.OfferName |
| `$cancelReason` | subscriber.SubscriberActivityInfo.ActivityReason | **Not declared (BUG)** |
| `$cancelDate` | formatted SubmissionDate | formatted SubmissionDate |
| `$lang` | subscriber.SubscriberGeneralInfo.Language | subscriber.SubscriberGeneralInfo.Language |
| `$subOff` | current SubscriberOffers concept | current SubscriberOffers concept |

### §9.2 — Event Container Construction

Event `@extId` is generated inside XSLT: `<xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>` — not a Java pre-call.

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| event @extId | `OMXUtils:generateTrackingID()` (XSLT) | Always |
| JMSPriority | `$orderRequest/OrderPriority` | Always (no xsl:if) |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Always (no xsl:if) |
| OrderID | `$orderRequest/OrderData/OrderID` | Always (no xsl:if) |
| RefID | `$refId` (= OfferName) | Always |
| OrderType | `$orderRequest/OrderData/OrderType` | Always (no xsl:if) |

> **Note:** JMSPriority, JMSCorrelationID, OrderID, and OrderType are all emitted unconditionally — they will be empty elements if the order fields are absent.

### §9.4 — Payload Root Element

Root: `ns:CancelSubscriptionRequest`

### §9.5 — Conditional Fields

| Field | Condition | Value |
|-------|-----------|-------|
| ns:transaction_id | OMXTrackingId present | OMXTrackingId |
| ns:subscriber_id | `$subIdCrm != ""` | CRM subscriber ID |

### §9.6 — Core Payload Fields

| Field | POU Value | COU Value | Always/Conditional |
|-------|-----------|-----------|-------------------|
| ns:method | `"cancel"` (static) | `"cancel"` (static) | Always |
| ns:msisdn | `$msisdn` | `$msisdn` | Always |
| ns:channel | `$channel` | `$channel` | Always |
| ns:pack_code | `$pack_code` (= OfferName) | `$pack_code` | Always |
| ns:cancel_reason | `$cancelReason` (ActivityReason) | `$channel` **⚠ BUG** | Always |
| ns:cancel_date | `$cancelDate` (formatted SubmissionDate) | `$cancelDate` | Always |
| ns:lang | `$lang` | `$lang` | Always |
| ns:extra/ns:key | `subOff/ExtendedInfo[Name="CANCEL_IMMEDIATE"]/Name` | same | Always (may be empty) |
| ns:extra/ns:value | `subOff/ExtendedInfo[Name="CANCEL_IMMEDIATE"]/Value` | same | Always (may be empty) |

### §9.7 — Complete Generated XML Example (POU variant)

```xml
<!-- MCS_CANCEL_SUBSCRIPTION event payload — POU variant -->
<createEvent>
  <event extId="OMX-TRK-GEN-001"> <!-- OMXUtils:generateTrackingID() -->
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-12345</JMSCorrelationID>
    <OrderID>ORD-9876</OrderID>
    <RefID>SOC_MCS_PACK1</RefID>  <!-- = OfferName -->
    <OrderType>1</OrderType>
    <payload>
      <ns:CancelSubscriptionRequest
        xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/CancelSubscription.xsd">
        <ns:transaction_id>OMX-TRK-12345</ns:transaction_id>
        <ns:method>cancel</ns:method>
        <ns:msisdn>0812345678</ns:msisdn>
        <ns:subscriber_id>CRM-ROW-001</ns:subscriber_id>  <!-- if subIdCrm non-empty -->
        <ns:channel>OMX-WEB</ns:channel>
        <ns:pack_code>SOC_MCS_PACK1</ns:pack_code>
        <ns:cancel_reason>CUSTOMER_REQUEST</ns:cancel_reason>  <!-- ActivityReason (POU); "OMX-WEB" (COU — BUG) -->
        <ns:cancel_date>2026-08-13 10:30:00</ns:cancel_date>
        <ns:lang>TH</ns:lang>
        <ns:extra>
          <ns:key>CANCEL_IMMEDIATE</ns:key>
          <ns:value>Y</ns:value>
        </ns:extra>
      </ns:CancelSubscriptionRequest>
    </payload>
  </event>
</createEvent>
```

### §9.8 — XSLT Stylesheet Source (POU Variant ①)

```xml
<!-- POU XSLT — MCS_CANCEL_SUBSCRIPTION -->
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/CancelSubscription.xsd"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="refId"/>           <!-- = OfferName (correlation key) -->
  <xsl:param name="msisdn"/>
  <xsl:param name="subIdCrm"/>
  <xsl:param name="channel"/>
  <xsl:param name="pack_code"/>
  <xsl:param name="cancelReason"/>    <!-- POU only; missing in COU XSLT -->
  <xsl:param name="cancelDate"/>
  <xsl:param name="lang"/>
  <xsl:param name="subOff"/>
  <xsl:template match="/">
    <createEvent><event>
      <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
      <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      <RefID><xsl:value-of select="$refId"/></RefID>
      <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      <payload><ns:CancelSubscriptionRequest>
        <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
          <ns:transaction_id><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></ns:transaction_id>
        </xsl:if>
        <ns:method><xsl:value-of select="'cancel'"/></ns:method>
        <ns:msisdn><xsl:value-of select="$msisdn"/></ns:msisdn>
        <xsl:if test="$subIdCrm!=&quot;&quot;">
          <ns:subscriber_id><xsl:value-of select="$subIdCrm"/></ns:subscriber_id>
        </xsl:if>
        <ns:channel><xsl:value-of select="$channel"/></ns:channel>
        <ns:pack_code><xsl:value-of select="$pack_code"/></ns:pack_code>
        <ns:cancel_reason><xsl:value-of select="$cancelReason"/></ns:cancel_reason>
        <!-- COU variant: ns:cancel_reason uses $channel instead of $cancelReason — BUG -->
        <ns:cancel_date><xsl:value-of select="$cancelDate"/></ns:cancel_date>
        <ns:lang><xsl:value-of select="$lang"/></ns:lang>
        <ns:extra>
          <ns:key><xsl:value-of select="$subOff/ExtendedInfo[Name='CANCEL_IMMEDIATE']/Name"/></ns:key>
          <ns:value><xsl:value-of select="$subOff/ExtendedInfo[Name='CANCEL_IMMEDIATE']/Value"/></ns:value>
        </ns:extra>
      </ns:CancelSubscriptionRequest></payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>

/* COU Variant ② differs only: cancelReason param absent; ns:cancel_reason = "$channel" instead */
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event  @extId ← OMXUtils:generateTrackingID() (XSLT)  [Always]
    ├── JMSPriority         ← $orderRequest/OrderPriority                    [Always — no xsl:if guard]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId          [Always — no xsl:if guard]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                [Always — no xsl:if guard]
    ├── RefID               ← $refId (= OfferName)                           [Always]
    ├── OrderType           ← $orderRequest/OrderData/OrderType              [Always — no xsl:if guard]
    └── payload
        └── ns:CancelSubscriptionRequest
            ├── ns:transaction_id   ← $orderRequest/OrderData/OMXTrackingId  [Conditional: if OMXTrackingId present]
            ├── ns:method           ← "cancel" (static literal)              [Always]
            ├── ns:msisdn           ← $msisdn                                [Always]
            ├── ns:subscriber_id    ← $subIdCrm                              [Conditional: if subIdCrm != ""]
            ├── ns:channel          ← $channel                               [Always]
            ├── ns:pack_code        ← $pack_code (= OfferName)               [Always]
            ├── ns:cancel_reason    [POU] ← $cancelReason (ActivityReason)   [Always]
            ├── ns:cancel_reason    [COU] ← $channel ⚠ BUG                  [Always — wrong source!]
            ├── ns:cancel_date      ← $cancelDate (formatted SubmissionDate) [Always]
            ├── ns:lang             ← $lang (SubscriberGeneralInfo.Language)  [Always]
            └── ns:extra
                ├── ns:key          ← $subOff/ExtendedInfo[Name="CANCEL_IMMEDIATE"]/Name   [Always — may be empty]
                └── ns:value        ← $subOff/ExtendedInfo[Name="CANCEL_IMMEDIATE"]/Value  [Always — may be empty]
```

Legend: `[Always]` = unconditional | `[Conditional: ...]` = wrapped in xsl:if | `⚠ BUG` = incorrect source mapping

---

## §11 — Audit Logging

> Request audit gated by `AllowWriteLog(orderType)`. Response audit always emitted (no gate).

| Phase | Field | Value |
|-------|-------|-------|
| Request | ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| Request | PROCESS_ID | `concat($pid, "_REQ")` |
| Request | OPERATION_NAME | "MCS_CANCEL_SUBSCRIPTION" |
| Request | AUDIT_TRACE | "Request Sent for MCS_CANCEL_SUBSCRIPTION" |
| Request | payload | Conditional: WritePayload="true" |
| Response | PROCESS_ID | `concat($pid, "_RES")` |
| Response | AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` (includes RefId in trace) |

---

## §12 — Activity Status Management

| Transition | Code | Trigger |
|-----------|------|---------|
| Running | "1" | At least one offer request dispatched |
| Skip | "4" | No qualifying offers across all subscribers |
| Error | HandleActivityException | Any uncaught exception |

---

## §13 — Exception / Error Handling

Entire `then` block wrapped in `try { ... } catch (Exception ae) { HandleActivityException(...); }`.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `RuleFunctions.Helpers.GetXMLForSubscriberOffer(orderRequest, subRefId, refId)` | Builds PreExecCheck XML for offer (uses OfferName as offer key, not filter/ExtendedInfo variant) |
| `RuleFunctions.Helpers.GetActivityParameterValueFromKey(activity, "USE_ROWID_CRM")` | Reads ProcessConfig activity parameter value by key |
| `RuleFunctions.Helpers.MapSubscriberIdFromCRM(subscriber, useRowIdCrmParam)` | Determines whether to use CRM row ID or default subscriber ID for ns:subscriber_id |
| `RuleFunctions.Helpers.AllowWriteLog(orderType)` | Returns boolean — whether request audit log should be emitted for this order type |
| `DateTime.format(submissionDate, "yyyy-MM-dd HH:mm:ss")` | Formats order submission date as cancel_date string |
| `RuleFunctions.Helpers.GetActivityStatusString("1", false)` | Returns status string for "Running" |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | Persists state to DB |
| `RuleFunctions.Helpers.SkipActivity(..., "4")` | Skip handler |
| `RuleFunctions.Helpers.HandleActivityException(...)` | Central exception handler |

---

## §15 — Function Dependency Tree

```text
Request_MCS_CANCEL_SUBSCRIPTION.rule
├── [POU loop: ParentOU[i].Subscriber[j].SubscriberOffers[k]]
│   ├── refId = subOff.OfferName
│   ├── Response[] resubmission skip check (ReferenceId==refId, CompletionStatus==2)
│   ├── RuleFunctions.Helpers.GetXMLForSubscriberOffer(orderRequest, sub.RefId, refId)
│   ├── XPath.execute(chkXPath, sXML) [if PreExecCheck set]
│   ├── [if chkRes=="true"]
│   │   ├── transaction_id = OMXTrackingId  [computed, unused — dead ref]
│   │   ├── msisdn = subscriber.MSISDN
│   │   ├── channel = orderRequest.OrderData.Channel
│   │   ├── cancelReason = SubscriberActivityInfo.ActivityReason
│   │   ├── pack_code = subOff.OfferName
│   │   ├── lang = SubscriberGeneralInfo.Language
│   │   ├── cancelDate = DateTime.format(SubmissionDate, "yyyy-MM-dd HH:mm:ss")
│   │   ├── RuleFunctions.Helpers.GetActivityParameterValueFromKey(activity, "USE_ROWID_CRM")
│   │   ├── RuleFunctions.Helpers.MapSubscriberIdFromCRM(subscriber, useRowIdCrmParam) → subIdCrm
│   │   ├── Event.createEvent(XSLT → MCS_CANCEL_SUBSCRIPTION POU)  [see §9.8]
│   │   │   └── OMXUtils:generateTrackingID()  [inside XSLT for event @extId]
│   │   ├── Event.Ext.sendEventImmediate(reqEvent)
│   │   ├── RuleFunctions.Helpers.AllowWriteLog(orderType)
│   │   ├── Event.Ext.sendEventImmediate(audit log)  [if AllowWriteLog]
│   │   └── orderCurrentActivity.RequestCount++  [if !isActResub]
├── [COU loop: ChildOU[p].Subscriber[q].SubscriberOffers[k]]
│   ├── method = OMXTrackingId  [computed, unused — dead ref]
│   ├── [same structure as POU but cancelReason NOT declared in XSLT]
│   └── COU reqEvent: ns:cancel_reason ← $channel (BUG — should be cancelReason)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)
└── RuleFunctions.Helpers.HandleActivityException(...)
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Properties Used |
|---------|-------------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.Channel, OrderData.OMXTrackingId, OrderData.OrderID, OrderData.OrderType, OrderPriority, SubmissionDate, Customer.ParentOU[], ChildOU[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, SubscriberActivityInfo.ActivityReason, SubscriberGeneralInfo.Language, SubscriberOffers[] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | OfferName (= refId and pack_code), ExtendedInfo[CANCEL_IMMEDIATE] |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck, Parameter |
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|------------|
| R1 | Send one MCS CancelSubscription request per qualifying SubscriberOffer (POU and COU) |
| R2 | Dispatch in parallel via sendEventImmediate; fan-in by ResponseCode "000" suffix count |
| R3 | Pass pack_code (OfferName), method="cancel", msisdn, channel, cancel_reason (ActivityReason), cancel_date (formatted SubmissionDate), lang to MCS |
| R4 | Include subscriber_id (from MapSubscriberIdFromCRM) if non-empty |
| R5 | Pass CANCEL_IMMEDIATE ExtendedInfo as ns:extra key/value |
| R6 | Evaluate PreExecCheck per-offer; skip already-successful offers on resubmission |
| R7 | Gate request audit log by AllowWriteLog; always log response |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| COU XSLT maps ns:cancel_reason to $channel instead of $cancelReason — all COU requests have channel name as cancel reason | [HIGH] | Fix COU XSLT: add $cancelReason param; map ns:cancel_reason to $cancelReason |
| refId = OfferName only (not composite) — resubmission skip may collide when same offer appears on multiple subscribers | [MEDIUM] | Change correlation key to a composite of POU+COU+sub+offerName in migration |
| JMS header fields emitted unconditionally — empty elements if order fields absent | [MEDIUM] | Add xsl:if guards matching other FMs' patterns |
| transaction_id (POU) and method (COU) computed but never used — dead references | [LOW] | Remove dead variables in migration |
| cancelDate uses SubmissionDate not EffectiveDate — may not reflect intended cancellation time | [LOW] | Verify with MCS team which date should be cancel_date |
| CANCEL_IMMEDIATE ExtendedInfo absence produces empty ns:extra — unclear if MCS handles empty extra gracefully | [LOW] | Add xsl:if guard around ns:extra or confirm MCS accepts empty key/value |

---

## §18 — Full Source Code (Request Rule)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_MCS_CANCEL_SUBSCRIPTION {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "MCS_CANCEL_SUBSCRIPTION";
    orderRequest.ProcessFlow.NextActivityID == "MCS_CANCEL_SUBSCRIPTION";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
      int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
      boolean isSkipped = true;
      /* POU loop: ParentOU[i].Subscriber[j].SubscriberOffers[k] */
      for (int i=0; i < iPOULen; i++) {
        for (int j=0; j < iSubscriberLen; j++) {
          for (int k=0; k < iSubscriberOfferLen; k++) {
            String refId = subOff.OfferName;  // not composite!
            /* resubmission skip check */
            if (!reqSuccess) {
              /* PreExecCheck eval per-offer */
              if (String.equals(chkRes, "true")) {
                String transaction_id = orderRequest.OrderData.OMXTrackingId; // unused dead ref
                String msisdn = subscriber.MSISDN;
                String channel = orderRequest.OrderData.Channel;
                String cancelReason = subscriber.SubscriberActivityInfo.ActivityReason;
                String pack_code = subOff.OfferName;
                String lang = subscriber.SubscriberGeneralInfo.Language;
                String cancelDate = DateTime.format(orderRequest.SubmissionDate, "yyyy-MM-dd HH:mm:ss");
                String useRowIdCrmParam = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "USE_ROWID_CRM");
                String subIdCrm = RuleFunctions.Helpers.MapSubscriberIdFromCRM(subscriber, useRowIdCrmParam);
                Events.OMConsumers.OMXFM.Request.MCS_CANCEL_SUBSCRIPTION reqEvent =
                  Event.createEvent(/* POU XSLT → ns:CancelSubscriptionRequest — see §9.8 */);
                Event.Ext.sendEventImmediate(reqEvent);
                if (RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                  Event.Ext.sendEventImmediate(Event.createEvent(/* Logger — see §11 */));
                }
                if (!isActResub) orderCurrentActivity.RequestCount++;
                isSkipped = false;
              }
            }
          }
        }
        /* COU loop: ChildOU[p].Subscriber[q].SubscriberOffers[k] */
        /* IDENTICAL except: method = OMXTrackingId [unused]; COU XSLT ns:cancel_reason = $channel [BUG] */
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

The response handler (`Response_MCS_CANCEL_SUBSCRIPTION`) receives one `MCS_CANCEL_SUBSCRIPTION` response event per dispatched offer request. It creates a standard `ResponseBase` concept, appends to `currActivity.Response[]`, sends a response audit log (always, not gated by AllowWriteLog), and returns "true" when the count of "000"-suffix responses equals `RequestCount`.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order for audit log |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.MCS_CANCEL_SUBSCRIPTION` | MCS response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; fan-in count checked |

### §19.3 — ResponseBase Concept Construction

```text
createObject
└── object  @extId ← $extId (Java: OMXUtils.generateTrackingID())  [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode       [Conditional: if present]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg        [Conditional: if present]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus   [Conditional: if present]
    └── ReferenceId       ← $eventResponse/RefID              [Conditional: if present]
```

### §19.4 — Response Completion Logic (Fan-in)

| Expression | Value |
|-----------|-------|
| Success count XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Returns "true" | All requests have received "000" success responses |
| Returns "false" | Still waiting for remaining or failed responses |

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | "MCS_CANCEL_SUBSCRIPTION" |
| AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` (includes RefId in trace) |
| payload | Conditional: WritePayload="true" → copy of $eventResponse |

### §19.6 — Response XSLT Source

```xml
<!-- ResponseBase XSLT — Response_MCS_CANCEL_SUBSCRIPTION -->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:param name="extId"/>           <!-- from Java: OMXUtils.generateTrackingID() -->
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject><object>
      <xsl:attribute name="extId"><xsl:value-of select="$extId"/></xsl:attribute>
      <xsl:if test="$eventResponse/ResponseCode"><ResponseCode><xsl:value-of select="$eventResponse/ResponseCode"/></ResponseCode></xsl:if>
      <xsl:if test="$eventResponse/ResponseMsg"><ResponseMessage><xsl:value-of select="$eventResponse/ResponseMsg"/></ResponseMessage></xsl:if>
      <xsl:if test="$eventResponse/CompletionStatus"><CompletionStatus><xsl:value-of select="$eventResponse/CompletionStatus"/></CompletionStatus></xsl:if>
      <xsl:if test="$eventResponse/RefID"><ReferenceId><xsl:value-of select="$eventResponse/RefID"/></ReferenceId></xsl:if>
    </object></createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
