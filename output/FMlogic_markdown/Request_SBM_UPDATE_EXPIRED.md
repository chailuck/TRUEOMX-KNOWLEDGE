# Request_SBM_UPDATE_EXPIRED

SBM Update Expiry Date — function_id 100200013 (IntraActivitySequencing, POU+COU Subscriber fan-out, isManual gate, EXP_DATE_VALUE fallback)

---

## §1 — Overview & Purpose

This rule updates (extends) data pack expiry dates via SBM's DoService API (**function_id 100200013**). It iterates POU and COU Subscriber offers, applies a PreExecCheck with FE_OR_CCBS filtering, and dispatches one `SBM_DO_SERVICE` request per qualifying offer using the **IntraActivitySequencing** pattern (sequential).

The expiry date sent to SBM is resolved by a three-tier priority (POU) / two-tier priority (COU):
1. **isManual** (Parameter[1]=="MANUAL"): BE concept mutation +7h → formatted ExpirationDate
2. **EXP_DATE_VALUE** ExtendedInfo (POU only): formatted from the ExtendedInfo value
3. **Fallback**: `current-dateTime()` — uses the current system time as the new expiry date

> **Critical [HIGH] — BE Concept Mutation on Resubmit:** When `isManual=true`, the rule executes `offer.ExpirationDate = DateTime.addHour(offer.ExpirationDate, 7)` to convert UTC→UTC+7. This mutates the BE concept in working memory. On resubmission, the already-adjusted date gets another +7 hours added, drifting cumulatively (+14h, +21h…). Fix: use a local temp variable for the adjusted date and pass it explicitly to the XSLT; do not mutate the concept.

> **COU Missing EXP_DATE_VALUE Check [MEDIUM]:** POU XSLT has a three-way branch (isManual → EXP_DATE_VALUE → current-dateTime). COU XSLT only has two ways (isManual → current-dateTime). COU subscribers never benefit from a pre-set EXP_DATE_VALUE ExtendedInfo.

> **POU offerRefId double-colon [MEDIUM]:** `pOuRefId + ":" + ":" + refId + ":" + offer.Soc` — same pattern as other SBM FMs.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_SBM_UPDATE_EXPIRED` |
| Author | Puttaporn-PC |
| Priority | 5 |
| ForwardChain | true |
| Target backend | SBM — DoService API |
| function_id | `"100200013"` (update expiry date) |
| Request event type | `Events.OMConsumers.OMXFM.Request.SBM_DO_SERVICE` |
| Response event type | `Events.OMConsumers.OMXFM.Response.SBM_DO_SERVICE` |
| Response concept | `Concepts.FM.Response.SBM_DoServiceRes` |
| Dispatch method | `Event.assertEvent` + `IntraActivitySequencing.ActionRequestEvent` (sequential) |
| Fan-out granularity | Per offer per subscriber (POU Subscriber + COU Subscriber) |
| Fan-in mechanism | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| isManual gate | `orderCurrentActivity.Parameter[1] == "MANUAL"` |
| Expiry date priority (POU) | isManual → EXP_DATE_VALUE ExtendedInfo → current-dateTime() |
| Expiry date priority (COU) | isManual → current-dateTime() (no EXP_DATE_VALUE fallback) |
| DMC_TRX_ID fallback | DMC_TRX_ID → IR_DMC_TRX_ID (two-level ExtendedInfo key lookup) |
| isBatch credential path | BATCH vs ONLINE global var path for app_user/app_password |
| Resubmission handling | `PurgePendingRequestsBeforeResubmit`; skip by composite offerRefId |
| Audit log gate | Unconditional (no AllowWriteLog) |
| Skip trigger | No qualifying offers → SkipActivity("4") |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order; subscriber and offer data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step; Parameter[1]; Response[], Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to order's next step |
| 2 | `orderCurrentActivity.ActivityID == "SBM_UPDATE_EXPIRED"` | FM identity |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SBM_UPDATE_EXPIRED"` | ProcessFlow routing |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be waiting |

---

## §5 — Execution Flow Diagram

1. Compute `isActResub`; if true → `PurgePendingRequestsBeforeResubmit`
2. Read `param = orderCurrentActivity.Parameter[1]`; if non-blank AND "MANUAL" → `isManual=true`
3. Evaluate `isBatch` via XPath on `orderRequest.OrderData.IntegrationMethod`
4. Load `app_user` / `app_password` from globalVariables BATCH or ONLINE path
5. **POU Subscriber loop**: iterate ParentOU[i].Subscriber[j].SubscriberOffers[k]
6. Build composite offerRefId: `pOuRefId + ":" + ":" + sub.RefId + ":" + offer.Soc` (POU double-colon)
7. Read `filter = ExtendedInfo[FE_OR_CCBS]/Value`
8. Resubmit skip: `Response[ReferenceId==offerRefId and CompletionStatus==2]`
9. PreExecCheck via `GetXMLForSubscriberOfferFilterWithExtendedInfo`
10. If chkRes=="true" AND isManual AND offer.ExpirationDate != null: **mutate** `offer.ExpirationDate = DateTime.addHour(offer.ExpirationDate, 7)` [BUG: resubmit drift]
11. Build SBM_DO_SERVICE event via XSLT (POU variant with EXP_DATE_VALUE fallback); `Event.assertEvent` + `ActionRequestEvent`
12. Emit audit log (unconditional)
13. **COU Subscriber loop**: identical flow — no ExpirationDate mutation; offerRefId = 4-part; COU XSLT has no EXP_DATE_VALUE check
14. Post-loop: `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)`
15. Status="1", SendDataToDB; or SkipActivity("4")
16. On exception: HandleActivityException

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### isManual Flag

| Step | Logic |
|------|-------|
| Read param | `param = XPath($orderCurrentActivity/Parameter[1])` |
| Check blank | `if (!IsBlank(param))` |
| Check "MANUAL" | `if (String.equals(param, "MANUAL"))` → `isManual = true` |

### BE Concept Mutation (POU only, isManual only)

```java
if(isManual) {
    DateTime newDate = null;
    if(null != offer.ExpirationDate) {
        newDate = offer.ExpirationDate;
    }
    if(null != newDate) {
        newDate = DateTime.addHour(newDate, 7);  // UTC → UTC+7 (Thailand)
        offer.ExpirationDate = newDate;          // MUTATES BE concept in working memory!
    }
}
```

> **[HIGH] Resubmit Date Drift:** This mutation persists in the BE concept. On resubmission, the already-mutated +7h date gets another +7h → total +14h drift per resubmit. **Fix:** Use a local variable (`DateTime adjustedDate = DateTime.addHour(offer.ExpirationDate, 7);`) and pass it as a separate XSLT parameter; never mutate the concept field.

### isBatch Credential Selection

| Condition | app_user path | app_password path |
|-----------|--------------|------------------|
| isBatch (IntegrationMethod=="BATCH") | `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/BATCH/app_user` | `.../BATCH/app_password` |
| else (ONLINE) | `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/ONLINE/app_user` | `.../ONLINE/app_password` |

### offerRefId Composition

| Scope | Formula | Issue |
|-------|---------|-------|
| POU Subscriber | `pOuRefId + ":" + ":" + refId + ":" + offer.Soc` | Double colon — COU segment empty [MEDIUM] |
| COU Subscriber | `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.Soc` | Correct 4-part composite |

### new_expire_date Resolution Logic

| Scope | Priority 1 | Priority 2 | Priority 3 (fallback) |
|-------|-----------|-----------|----------------------|
| POU Subscriber XSLT | `isManual='true'` → format mutated ExpirationDate | `exists(ExtendedInfo[EXP_DATE_VALUE])` → format that date | `tib:format-dateTime(..., current-dateTime())` |
| COU Subscriber XSLT | `isManual='true'` → format ExpirationDate | No EXP_DATE_VALUE check → `tib:format-dateTime(..., current-dateTime())` | [MEDIUM — missing fallback] |

### DMC_TRX_ID Fallback Logic

| Branch | Condition | ExtendedInfo Key Used |
|--------|-----------|----------------------|
| Primary | `exists($offer/ExtendedInfo[Name='DMC_TRX_ID']/Value)` | DMC_TRX_ID |
| Fallback | else AND `exists($offer/ExtendedInfo[Name='IR_DMC_TRX_ID']/Value)` | IR_DMC_TRX_ID |
| Omit | Neither DMC_TRX_ID nor IR_DMC_TRX_ID present | No dmc_transaction_id parameter emitted |

---

## §7 — Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| param | `orderCurrentActivity.Parameter[1]` | Checked for "MANUAL" → sets isManual flag |
| pOuRefId | `orderRequest.OrderData.Customer.ParentOU[i].RefId` | POU reference ID |
| cOuRefId | `orderRequest.OrderData.Customer.ParentOU[i].ChildOU[x].RefId` | COU reference ID |
| sub.RefId | `subscriber.RefId` | Subscriber reference ID |
| msisdn | `sub.MSISDN` | ns:service_no |
| offerRefId | Composite key (see §6) | RefID in JMS; resubmission skip key |
| filter | `XPath: $offer/ExtendedInfo[Name="FE_OR_CCBS"]/Value` | Passed to GetXMLForSubscriberOfferFilterWithExtendedInfo |
| offer.ExpirationDate | `sub.SubscriberOffers[k].ExpirationDate` | Mutated +7h if isManual=true (POU only) |
| EXP_DATE_VALUE | `offer/ExtendedInfo[Name='EXP_DATE_VALUE']/Value` | Alternative expiry date (POU only; fallback if not isManual) |
| OfferName | `offer.OfferName` | ns:parameters/package_code value |
| channel | `GetSBMServiceChannel(orderRequest, offer)` | ns:channel |
| app_user | globalVariables BATCH or ONLINE path | ns:app_user |
| app_password | globalVariables BATCH or ONLINE path | ns:app_password |
| DMC_TRX_ID / IR_DMC_TRX_ID | `offer/ExtendedInfo[Name='DMC_TRX_ID' or 'IR_DMC_TRX_ID']/Value` | ns:parameters/dmc_transaction_id (DMC first, IR fallback) |
| PARENT_TRX_ID | `orderRequest.OrderData.ExtendedInfo[Name='PARENT_TRX_ID']/Value` | ns:parameters/parent_trx_id — if OrderType='3'/'4' AND exists |

---

## §8 — System & Integration Dependencies

### §8.1 — ESB / JMS Channel Dependencies

| Direction | Event Type | Dispatch |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.SBM_DO_SERVICE` | `Event.assertEvent` + IntraActivitySequencing |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `Event.Ext.sendEventImmediate` — unconditional |

### §8.2 — Backend API Details

| System | API | Schema NS | function_id |
|--------|-----|-----------|-------------|
| SBM | doServiceArrayRequest | `http://services.omx.truecorp.co.th/FMServices/SBMDoserviceArrayRequest` | `100200013` |

### §8.3 — ExtendedInfo Fields Required

| Name | Level | Required/Optional | Where Used |
|------|-------|------------------|-----------|
| FE_OR_CCBS | Offer | Optional | filter → passed to PreExecCheck helper for filtering |
| EXP_DATE_VALUE | Offer | Optional | Alternative expiry date source (POU only; if not isManual) |
| DMC_TRX_ID | Offer | Optional | ns:parameters/dmc_transaction_id — primary |
| IR_DMC_TRX_ID | Offer | Optional | ns:parameters/dmc_transaction_id — fallback when DMC_TRX_ID absent |
| PARENT_TRX_ID | Order | Optional | ns:parameters/parent_trx_id — if OrderType='3'/'4' AND exists |

### §8.4 — Global Variable Dependencies

| Path | Usage |
|------|-------|
| `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/BATCH/app_user` | SBM BATCH credential |
| `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/BATCH/app_password` | SBM BATCH credential |
| `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/ONLINE/app_user` | SBM ONLINE credential |
| `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/ONLINE/app_password` | SBM ONLINE credential |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit |
| `$globalVariables/OMX_OM/WritePayload` | Guards payload in audit |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Notes |
|-----------|-----------|-------|
| `$orderRequest` | orderRequest concept | Root order |
| `$offerRefId` | Composite offerRefId | RefID in JMS header |
| `$app_password` | globalVar BATCH or ONLINE | SBM credential |
| `$app_user` | globalVar BATCH or ONLINE | SBM credential |
| `$channel` | GetSBMServiceChannel(...) | ns:channel |
| `$offer` | SubscriberOffers concept (ExpirationDate already mutated if isManual) | ExpirationDate, ExtendedInfo[EXP_DATE_VALUE, DMC_TRX_ID, IR_DMC_TRX_ID], OfferName |
| `$isManual` | Java boolean (serialized as "true"/"false" string) | Controls new_expire_date selection branch |
| `$msisdn` | sub.MSISDN | ns:service_no |

### §9.2 — POU vs COU XSLT Differences

| Aspect | POU Variant | COU Variant |
|--------|------------|-------------|
| new_expire_date branches | 3-way: isManual → EXP_DATE_VALUE → current-dateTime() | 2-way: isManual → current-dateTime() (no EXP_DATE_VALUE) |
| offerRefId format | `pOuRefId + ":" + ":" + refId + ":" + soc` (double-colon) | `pOuRefId + ":" + cOuRefId + ":" + refId + ":" + soc` |
| isManual concept mutation | Yes: addHour(ExpirationDate, 7) before XSLT call | No mutation; ExpirationDate passed as-is |

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | xsl:if present |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | xsl:if present |
| OrderID | `$orderRequest/OrderData/OrderID` | xsl:if present |
| **RefID** | `$offerRefId` (composite) | **Always** (unconditional) |
| OrderType | `$orderRequest/OrderData/OrderType` | xsl:if present |

### §9.4 — POU XSLT new_expire_date Logic

```xml
<!-- POU: 3-way branch for new_expire_date -->
<xsl:choose>
  <xsl:when test="$isManual='true'">
    <ns:item><ns:key>new_expire_date</ns:key>
      <ns:value><xsl:value-of select="tib:format-dateTime('dd/MM/yyyy HH:mm:ss', $offer/ExpirationDate)"/></ns:value></ns:item>
  </xsl:when>
  <xsl:otherwise>
    <xsl:choose>
      <xsl:when test="exists($offer/ExtendedInfo[Name='EXP_DATE_VALUE'])">
        <ns:item><ns:key>new_expire_date</ns:key>
          <ns:value><xsl:value-of select="tib:format-dateTime('dd/MM/yyyy HH:mm:ss', $offer/ExtendedInfo[Name='EXP_DATE_VALUE']/Value)"/></ns:value></ns:item>
      </xsl:when>
      <xsl:otherwise>
        <ns:item><ns:key>new_expire_date</ns:key>
          <ns:value><xsl:value-of select="tib:format-dateTime('dd/MM/yyyy HH:mm:ss', current-dateTime())"/></ns:value></ns:item>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:otherwise>
</xsl:choose>

<!-- DMC_TRX_ID fallback logic -->
<xsl:choose>
  <xsl:when test="exists($offer/ExtendedInfo[Name='DMC_TRX_ID']/Value)">
    <ns:item><ns:key>dmc_transaction_id</ns:key>
      <ns:value><xsl:value-of select="$offer/ExtendedInfo[Name='DMC_TRX_ID']/Value"/></ns:value></ns:item>
  </xsl:when>
  <xsl:otherwise>
    <xsl:if test="exists($offer/ExtendedInfo[Name='IR_DMC_TRX_ID']/Value)">
      <ns:item><ns:key>dmc_transaction_id</ns:key>
        <ns:value><xsl:value-of select="$offer/ExtendedInfo[Name='IR_DMC_TRX_ID']/Value"/></ns:value></ns:item>
    </xsl:if>
  </xsl:otherwise>
</xsl:choose>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority         ← $orderRequest/OrderPriority                   [Conditional: xsl:if present]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId         [Conditional: xsl:if present]
    ├── OrderID             ← $orderRequest/OrderData/OrderID               [Conditional: xsl:if present]
    ├── RefID               ← $offerRefId (composite)                       [Always]
    ├── OrderType           ← $orderRequest/OrderData/OrderType             [Conditional: xsl:if present]
    └── payload
        └── ns1:doServiceArrayRequest
            └── ns1:DoServiceRequest
                ├── ns:app_password   ← $app_password (BATCH/ONLINE)            [Always]
                ├── ns:app_user       ← $app_user (BATCH/ONLINE)                [Always]
                ├── ns:channel        ← $channel (GetSBMServiceChannel)          [Always]
                ├── ns:function_id    ← "100200013" (static)                     [Always]
                ├── ns:parameters
                │   ├── ns:item[package_code]       ← $offer/OfferName           [Always]
                │   ├── ns:item[new_expire_date]                                 [Always - one of three paths]
                │   │   ├── [Conditional: isManual='true'] → format($offer/ExpirationDate) [+7h UTC→UTC+7 for POU]
                │   │   ├── [Conditional: exists(EXP_DATE_VALUE)] POU ONLY → format(ExtendedInfo[EXP_DATE_VALUE]/Value)
                │   │   └── [Fallback] → format(current-dateTime())
                │   ├── ns:item[dmc_transaction_id]                              [Conditional - one of two paths]
                │   │   ├── [Conditional: exists(DMC_TRX_ID)] ← ExtendedInfo[DMC_TRX_ID]/Value
                │   │   └── [Conditional: else AND exists(IR_DMC_TRX_ID)] ← ExtendedInfo[IR_DMC_TRX_ID]/Value
                │   └── ns:item[parent_trx_id]  ← ExtendedInfo[PARENT_TRX_ID]/Value  [Conditional: OrderType='3'/'4' AND exists]
                └── ns:service_no    ← $msisdn                                   [Always]

Legend:
  ← XPath source expression (green in HTML)
  "static" = static literal (orange in HTML)
  [Always]       = unconditional element
  [Conditional]  = guarded by xsl:if or xsl:choose
```

---

## §11 — Audit Logging

| Phase | Field | Value |
|-------|-------|-------|
| Request | ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| Request | PROCESS_ID | `concat($pid, "_REQ")` |
| Request | OPERATION_NAME | "SBM_UPDATE_EXPIRED" |
| Request | AUDIT_TRACE | "Request Sent for SBM_UPDATE_EXPIRED" |
| Request | payload | Conditional: WritePayload="true" |
| Response | PROCESS_ID | `concat($pid, "_RES")` |
| Response | AUDIT_TRACE | "Response received for SBM_UPDATE_EXPIRED" |

---

## §12 — Activity Status Management

| Transition | Code | Trigger |
|-----------|------|---------|
| Running | "1" | At least one offer queued; SendFirstRequestEvent called |
| Skip | "4" | No qualifying offers (isSkipped=true) |
| Error | HandleActivityException | Any uncaught exception |

---

## §13 — Exception / Error Handling

`try { ... } catch (Exception ae) { HandleActivityException(...); }`. Two commented-out `System.debugOut` lines at rule entry and exit.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears queued events on resubmission |
| `BRMS.IsBlank(param)` | Returns true if param is null or empty |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, soc, filter)` | Builds PreExecCheck XML with FE_OR_CCBS filter for POU |
| `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, refId, soc, pOuRefId, filter)` | Builds PreExecCheck XML with FE_OR_CCBS filter for COU |
| `GetSBMServiceChannel(orderRequest, offer)` | Derives SBM channel for the offer |
| `IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)` | Registers event in sequential queue |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Dispatches first queued event after all offers registered |
| `IntraActivitySequencing.ActionResponseEvent(currActivity)` | Response fan-in; returns "true" when all sequential offers processed |
| `DateTime.addHour(date, 7)` | UTC → UTC+7 (Thailand) timezone shift for isManual ExpirationDate |
| `tib:format-dateTime('dd/MM/yyyy HH:mm:ss', dateValue)` | Formats DateTime to SBM expected format (XSLT function) |
| `GetActivityStatusString("1", false)` | Returns "Running" status |
| `SendDataToDB(orderRequest)` | Persists state |
| `SkipActivity(..., "4")` | Skip handler |
| `HandleActivityException(...)` | Central exception handler |

---

## §15 — Function Dependency Tree

```text
Request_SBM_UPDATE_EXPIRED.rule
├── isActResub check
│   └── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity) [if isActResub]
├── param = XPath($orderCurrentActivity/Parameter[1])
├── BRMS.IsBlank(param) → if not blank AND "MANUAL" → isManual=true
├── isBatch = XPath($orderRequest/OrderData/IntegrationMethod == 'BATCH')
├── app_user / app_password from globalVariables (BATCH or ONLINE path)
│
├── [POU Subscriber loop: ParentOU[i].Subscriber[j].SubscriberOffers[k]]
│   ├── offerRefId = pOuRefId + ":" + ":" + refId + ":" + offer.Soc  [DOUBLE COLON]
│   ├── filter = XPath($offer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── Response[ReferenceId==offerRefId and CompletionStatus==2]  [resubmit skip]
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, offer.Soc, filter)
│   ├── GetSBMServiceChannel(orderRequest, offer) → channel
│   ├── [if isManual AND offer.ExpirationDate != null]
│   │   ├── DateTime.addHour(offer.ExpirationDate, 7) → newDate
│   │   └── offer.ExpirationDate = newDate  [CONCEPT MUTATION — RESUBMIT DRIFT BUG HIGH]
│   ├── Event.createEvent(SBM_DO_SERVICE XSLT POU — function_id=100200013 — see §9.4)
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│   └── Event.Ext.sendEventImmediate(audit Logger)
│
├── [COU Subscriber loop: ChildOU[x].Subscriber[y].SubscriberOffers[z]]
│   ├── offerRefId = pOuRefId + ":" + cOuRefId + ":" + refId + ":" + offer.Soc  [correct]
│   ├── [no ExpirationDate mutation]
│   ├── Event.createEvent(SBM_DO_SERVICE XSLT COU — 2-way branch only)
│   └── [same dispatch + audit structure as POU]
│
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(...)
└── HandleActivityException(...)
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Properties Used |
|---------|-------------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.IntegrationMethod, OrderData.OMXTrackingId, OrderData.OrderID, OrderData.OrderType, OrderData.ExtendedInfo[PARENT_TRX_ID], OrderPriority, Customer.ParentOU[], ChildOU[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, SubscriberOffers[] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Soc, OfferName, ExpirationDate (mutated!), ExtendedInfo[FE_OR_CCBS, EXP_DATE_VALUE, DMC_TRX_ID, IR_DMC_TRX_ID] |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, Parameter[1] (MANUAL flag), RequestCount, Response[], PreExecCheck |
| `Concepts.FM.Response.SBM_DoServiceRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, DoServiceResponse (nested) |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Update data pack offer expiry dates via SBM DoService (function_id 100200013) for POU and COU subscribers |
| R2 | Sequential dispatch using IntraActivitySequencing; one offer at a time |
| R3 | isManual mode (Parameter[1]=="MANUAL"): send offer.ExpirationDate adjusted to UTC+7 as new_expire_date |
| R4 | Non-manual POU: if EXP_DATE_VALUE ExtendedInfo present, use that date; else use current-dateTime() |
| R5 | Non-manual COU: use current-dateTime() directly (no EXP_DATE_VALUE check) |
| R6 | dmc_transaction_id: prefer DMC_TRX_ID ExtendedInfo; fall back to IR_DMC_TRX_ID if absent |
| R7 | BATCH vs ONLINE credential selection from global variables |
| R8 | FE_OR_CCBS filter passed to PreExecCheck helper for per-offer eligibility |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| BE concept mutation of ExpirationDate causes +7h drift on each resubmission | [HIGH] | Use a local `DateTime adjustedDate` variable; pass as XSLT param; never mutate the concept field |
| COU XSLT missing EXP_DATE_VALUE check — COU subscribers get current-dateTime() even when EXP_DATE_VALUE is set | [MEDIUM] | Align COU XSLT with POU: add EXP_DATE_VALUE branch as priority 2 fallback |
| POU offerRefId double-colon — COU segment empty | [MEDIUM] | Fix: `pOuRefId + "::" + refId + ":" + offer.Soc` |
| Response has two parallel xsl:if blocks (CheckPackAllowReturn AND DoServiceReturn) — both may match | [LOW] | Clarify with SBM team which return path is authoritative; convert to xsl:choose |

---

## §18 — Full Source Code (Request Rule — abbreviated)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_SBM_UPDATE_EXPIRED {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "SBM_UPDATE_EXPIRED";
    orderRequest.ProcessFlow.NextActivityID == "SBM_UPDATE_EXPIRED";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      if(isActResub) { IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity); }
      /* param = Parameter[1]; if "MANUAL" → isManual=true */
      boolean isBatch = XPath.evalAsBoolean(/* IntegrationMethod == 'BATCH' */);
      /* load app_user / app_password from globalVars BATCH or ONLINE path */
      for (POU loop) {
        offerRefId = pOuRefId + ":" + ":" + refId + ":" + offer.Soc; // DOUBLE COLON
        filter = XPath($offer/ExtendedInfo[FE_OR_CCBS]/Value);
        /* resubmit skip check */
        if(!reqSuccess && chkRes=="true") {
          channel = GetSBMServiceChannel(orderRequest, offer);
          if(isManual && offer.ExpirationDate != null) {
            offer.ExpirationDate = DateTime.addHour(offer.ExpirationDate, 7); // MUTATION — RESUBMIT BUG
          }
          reqEvent = Event.createEvent(/* XSLT POU — function_id=100200013 — see §9.4 */);
          Event.assertEvent(reqEvent);
          IntraActivitySequencing.ActionRequestEvent(reqEvent, activity);
          audit log; // unconditional
        }
      }
      for (COU loop) { /* same; no mutation; offerRefId = full 4-part; COU XSLT = 2-way branch */ }
      IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
      Status="1"; SendDataToDB; // or SkipActivity("4")
    } catch(Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 — Overview

Creates `SBM_DoServiceRes` concept, appends to `currActivity.Response[]`, logs audit unconditionally, returns via `IntraActivitySequencing.ActionResponseEvent`. Unlike SBM_CANCEL_DATA_PACK_IMMEDIATE (which used only `ns:DoServiceReturn`), this response has **two separate `xsl:if` paths** — one for `ns:CheckPackAllowReturn` and one for `ns:DoServiceReturn` — which means both DoServiceResponse sub-objects are created if both return paths exist in the response.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Audit log |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SBM_DO_SERVICE` | SBM response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; sequencing |

### §19.3 — SBM_DoServiceRes Concept Construction

```text
createObject
└── object @extId ← $extId (Java: OMXUtils.generateTrackingID())         [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode                 [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg                  [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus             [Conditional]
    ├── ReferenceId         ← $eventResponse/RefID                        [Conditional]
    ├── DoServiceResponse @extId ← OMXUtils:generateTrackingID() [XSLT call]
    │   [Conditional: if exists(ns:CheckPackAllowReturn)] — PATH 1
    │   ├── extra_xml, req_transaction_id, response_message, result_code, result_desc, result_namespace, transaction_id
    │   └──   ← ns:CheckPackAllowReturn/ns1:*
    └── DoServiceResponse @extId ← OMXUtils:generateTrackingID() [XSLT call]
        [Conditional: if exists(ns:DoServiceReturn)] — PATH 2 (separate xsl:if, not xsl:choose!)
        ├── extra_xml, req_transaction_id, response_message, result_code, result_desc, result_namespace, transaction_id
        └──   ← ns:DoServiceReturn/ns1:*

Note: Both paths can match simultaneously → two DoServiceResponse objects created. [LOW]
```

### §19.4 — Fan-in Completion Logic

| Call | Returns |
|------|---------|
| `IntraActivitySequencing.ActionResponseEvent(currActivity)` | "true" when all sequential offers processed; "false" when more remain |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
