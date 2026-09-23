# Request_OMX_GET_OFFER_RATE

> Per-offer PreExecCheck-filtered SOC collection then single batch rate lookup — dual backend (OMX / CES GoldenDB); writes RevenueType and OfferRate back to all matching offers

**Author:** RS33-BANDIT | **forwardChain:** true | **Generated:** 2026-08-04

---

## §1 Overview & Purpose

This FM retrieves rate information (RevenueType + Rate) for SOC codes in the order. It uses a **hybrid pattern**: it evaluates PreExecCheck *per offer* (using offer-level XML helpers) to decide which SOC codes to include in the batch, then fires a single aggregated request to the OMX Get Offer Rate service (or CES for GoldenDB orders). The response iterates per-SOC `OfferRate` entries and writes `RevenueType` and `OfferRate` back to matching Agreement Offers and Subscriber Offers. `OfferRate` is written only if the current value is 0 (idempotent); `RevenueType` always overwrites.

> **Hybrid pattern:** PreExecCheck is evaluated per-offer (filtering which SOCs enter the batch), not as a global gate. SOCs that pass are collected into a deduplicated list; SOCs from RelatedOffersArray are also collected if the parent offer passes. One event fires with all qualifying SOCs.

> **COU Subscriber helper mismatch:** POU Subscriber uses `GetXMLForSubscriberOfferFilterWithExtendedInfo` (includes ExtendedInfo/FE_OR_CCBS context), but COU Subscriber uses `GetXMLForSubscriberOfferInChildOU` (no FilterWithExtendedInfo). PreExecCheck XML context may differ between POU and COU subscriber paths.

> **Audit send method:** Request audit uses `Event.sendEvent(...)` — NOT `Event.Ext.sendEventImmediate(...)`. This is different from most other FMs. The audit event is queued rather than sent immediately.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_OMX_GET_OFFER_RATE.rule` | 225 lines |
| Response file | `Response_OMX_GET_OFFER_RATE.rulefunction` | 119 lines |
| Author | RS33-BANDIT | |
| forwardChain | true | |
| Request event (OMX path) | `Events.OMConsumers.OMXFM.Request.OMX_GET_OFFER_RATE` | Default backend |
| Request event (CES path) | `Events.OMConsumers.OMXFM.Request.CES_GET_OFFER_RATE` | GoldenDB==Y only; adds extId |
| Response event | `Events.OMConsumers.OMXFM.Response.OMX_GET_OFFER_RATE` | Single response |
| Request schema NS | `http://services.omx.truecorp.co.th/GetOfferRateRequest.xsd` (ns) | |
| Response schema NS | `http://services.omx.truecorp.co.th/GetOfferRateResponse.xsd` (xsd2) | |
| Response concept | `Concepts.FM.Response.OMX_GetOfferRateRes` | Standard ResponseBase fields + OMXUtils:generateTrackingID() extId |
| Correlation key (RefID) | `$orderRequest/OrderData/Customer/RefId` | Customer RefId — NOT subscriber or SOC level |
| Fan-out level | Batch — single event with all qualifying SOCs | Only if socCodes.length > 0 |
| Resubmit handler | `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` | Same namespace as OMX_GET_FUT_INFO_BY_SUB |
| Credential gate | None | No UserName/PassWord headers |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Source of offers; GoldenDB routing; offer RevenueType+OfferRate written by response |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Activity state; RequestCount++; Response[] appended |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_GET_OFFER_RATE"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_GET_OFFER_RATE"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 Execution Flow Diagram

1. **Resubmit flag + purge** — `isActResub`; if true: `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit`
2. **isSkipped = true**; create empty `arrLstSOCs` ArrayList
3. **Per-offer PreExecCheck-filtered SOC collection** — for each of 4 offer sources (POU Agreement, POU Subscriber, COU Agreement, COU Subscriber):
   - Read `FE_OR_CCBS` ExtendedInfo from offer
   - Evaluate PreExecCheck using offer-specific XML helper
   - If passes: add `offer.Soc` + all `RelatedOffersArray[].Soc` to deduplicated list
4. **Fire only if socCodes.length > 0:**
   - GoldenDB=="Y" → `CES_GET_OFFER_RATE` (adds extId via OMXUtils); audit via `Event.sendEvent` (queued)
   - Default → `OMX_GET_OFFER_RATE`; audit via `Event.sendEvent` (queued)
   - isSkipped=false; if !isActResub → RequestCount++
5. **Status:** if !isSkipped → `GetActivityStatusString("1")` + `SendDataToDB`; else → `SkipActivity("4")`
6. **Cleanup:** `Collections.clear(arrLstSOCs)`
7. **Exception:** try/catch → `HandleActivityException`

---

## §6 Rule Action (THEN) — Key Details

### §6.1 — Per-Offer PreExecCheck-Filtered SOC Collection

Each offer's PreExecCheck is evaluated individually using an offer-level serialized XML. Only SOCs from offers that pass enter the batch. RelatedOffersArray SOCs are included without re-checking PreExecCheck.

| Source | PreExecCheck Helper | Parameters |
|--------|---------------------|------------|
| POU Agreement Offer | `GetXMLForAgreementOfferFilterWithExtendedInfo` | `orderRequest, pAgRefId, socCode, src` |
| POU Subscriber Offer | `GetXMLForSubscriberOfferFilterWithExtendedInfo` | `orderRequest, pSubRefId, socCode, src` |
| COU Agreement Offer | `GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo` | `orderRequest, cAgRefId, socCode, pOuRefId, src` |
| COU Subscriber Offer | `GetXMLForSubscriberOfferInChildOU` | `orderRequest, cSubRefId, socCode, pOuRefId` — `[No FilterWithExtendedInfo]` |

> **COU Subscriber inconsistency:** `GetXMLForSubscriberOfferInChildOU` does not include the `src` (FE_OR_CCBS) parameter. The PreExecCheck XML context for COU Subscriber is structurally different from POU Subscriber, which may cause PreExecCheck expressions that reference ExtendedInfo to evaluate differently for COU subscribers.

### §6.2 — FE_OR_CCBS ExtendedInfo Read

```java
String src = XPath.evalAsString(
    "$offer/ExtendedInfo[Name='FE_OR_CCBS']/Value");
// Read per-offer; passed as 'src' param to PreExecCheck helpers
```

### §6.3 — SOC Collection Dedup

```java
if(!IsBlankOrStringNull(socCode) && !Collections.contains(arrLstSOCs, socCode))
    Collections.add(arrLstSOCs, socCode);
// Then for each RelatedOffersArray (no PreExecCheck re-check):
if(!IsBlankOrStringNull(relateSocCode) && !Collections.contains(arrLstSOCs, relateSocCode))
    Collections.add(arrLstSOCs, relateSocCode);
```

### §6.4 — Audit Send Method Difference

> **[MEDIUM]** Request audit uses `Event.sendEvent(...)` (queued) — NOT `Event.Ext.sendEventImmediate(...)`. This means the audit event may be processed after the request is already in flight. All other FMs in this process use `sendEventImmediate` for audits.

### §6.5 — GoldenDB Routing

```java
Object[] socCodes = Collections.toArray(arrLstSOCs);
if(socCodes != null && socCodes@length > 0) {
    if(!IsBlankOrStringNull(GoldenDB) && String.equals("Y", GoldenDB)) {
        // CES path — extId via OMXUtils:generateTrackingID()
        Events..CES_GET_OFFER_RATE reqEvent = ...;
        Event.Ext.sendEventImmediate(reqEvent);
    } else {
        // OMX path
        Events..OMX_GET_OFFER_RATE reqEvent = ...;
        Event.Ext.sendEventImmediate(reqEvent);
    }
    isSkipped = false;
    if(!isActResub) orderCurrentActivity.RequestCount++;
    Event.sendEvent(auditEvent);  // queued, not immediate
}
Collections.clear(arrLstSOCs);  // cleanup
```

---

## §7 Data Extraction

FE_OR_CCBS ExtendedInfo value is read per-offer and passed to PreExecCheck helper (not used in request payload). No pipe-delimiter parsing. SOC dedup uses ArrayList + `Collections.contains`.

---

## §8 System & Integration Dependencies

### §8.1 — Order Type Dependencies

| GoldenDB | Backend | Event Type |
|----------|---------|------------|
| `"Y"` | CES (GoldenDB) | `CES_GET_OFFER_RATE` |
| blank / other | OMX | `OMX_GET_OFFER_RATE` |

Event fires only if at least one SOC passes all per-offer PreExecChecks (`socCodes.length > 0`). If no SOCs qualify, activity is skipped.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Purpose |
|-----------|---------|-------------|---------|
| [OUTBOUND] | FM JMS | OMX_GET_OFFER_RATE queue | Batch SOC rate lookup (OMX path) |
| [OUTBOUND] | FM JMS | CES_GET_OFFER_RATE queue | Batch SOC rate lookup (GoldenDB path) |
| [INBOUND] | FM JMS | OMX_GET_OFFER_RATE response queue | OfferRate[] per SOC |
| [LOG] | OMXESB Logger | Audit event (queued) | Request audit — `Event.sendEvent` not immediate |

### §8.3 — Backend API Details

| Field | OMX Path | CES Path |
|-------|----------|----------|
| Request root | `ns:GetOfferRateRequest` | `ns:GetOfferRateRequest` |
| Key request field | `ns:SocCode` (repeated) | `ns:SocCode` (repeated) |
| Response root | `xsd2:GetOfferRateResponse` | `xsd2:GetOfferRateResponse` |
| Key response fields | `xsd2:OfferRate/xsd2:SocCode + RevenueType + Rate` | same |
| RefID header | `$orderRequest/OrderData/Customer/RefId` | same |
| extId on event | Not set | `OMXUtils:generateTrackingID()` |

### §8.4 — BE Working Memory Dependencies

| Concept | Field | Access | Notes |
|---------|-------|--------|-------|
| OrderRequest | OrderData.GoldenDB | READ | Backend routing |
| OrderRequest | OrderData.Customer.RefId | READ | RefID header value |
| AgreementOffers / SubscriberOffers | Soc, ExtendedInfo[FE_OR_CCBS] | READ | SOC + filter value |
| AgreementOffers / SubscriberOffers | RelatedOffersArray[].Soc | READ | Related offer SOC collection |
| AgreementOffers / SubscriberOffers | RevenueType | WRITTEN | Always overwritten with response value |
| AgreementOffers / SubscriberOffers | OfferRate | WRITTEN | Written only if current value == 0 (idempotent) |
| Activity | RequestCount / Response[] | READ+WRITTEN | RequestCount++; Response[] appended |

### §8.5 — ExtendedInfo Fields Required

| Name | Source | Required | Purpose |
|------|--------|----------|---------|
| `FE_OR_CCBS` | Offer ExtendedInfo | Optional | Passed as `src` to PreExecCheck helper for context-aware filtering |

### §8.6 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `OMX_OM/WritePayload` | Payload inclusion in audit |

> No credential gate — no IsEnableUserPass / UserName / PassWord headers in either variant.

---

## §9 Detailed Payload Build

### §9.1 — XSLT Parameters

| Parameter | Bound From | Both Variants |
|-----------|------------|---------------|
| `$orderRequest` | orderRequest concept serialized | Yes |
| `$socCodes` | `Collections.toArray(arrLstSOCs)` — PreExecCheck-filtered SOC array | Yes |

> Note: `$globalVariables` is NOT a parameter in the request XSLT — only in the audit logger XSLT.

### §9.2 — Variant Differences

| Feature | OMX variant | CES variant (GoldenDB) |
|---------|-------------|------------------------|
| Event type | `OMX_GET_OFFER_RATE` | `CES_GET_OFFER_RATE` |
| extId on event | Not set | `OMXUtils:generateTrackingID()` |
| OMXUtils import | Not imported | `xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"` |
| Payload structure | Identical | Identical |

### §9.3 — JMS / Event Header Fields

| Header | Source | Condition |
|--------|--------|-----------|
| extId (event attr) | `OMXUtils:generateTrackingID()` | CES variant only |
| JMSPriority | `$orderRequest/OrderPriority` | Conditional |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| OrderID | `$orderRequest/OrderData/OrderID` | Conditional |
| RefID | `$orderRequest/OrderData/Customer/RefId` | Conditional — Customer RefId (not subscriber/SOC) |
| OrderType | `$orderRequest/OrderData/OrderType` | Conditional |

### §9.4 — Payload Fields

| XML Element | Source | Iteration |
|-------------|--------|-----------|
| `ns:GetOfferRateRequest` | — root container | |
| `ns:SocCode` | `xsl:for-each select="$socCodes/elements" → .` | One element per PreExecCheck-passing SOC |

### §9.5 — Generated XML Example

```xml
<event extId="TRK-20250804-001">  <!-- extId in CES variant only -->
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-20250804-001</JMSCorrelationID>
  <OrderID>ORD-001</OrderID>
  <RefID>CUST-REF-999</RefID>  <!-- Customer.RefId — not subscriber/SOC -->
  <OrderType>3</OrderType>
  <payload>
    <ns:GetOfferRateRequest
      xmlns:ns="http://services.omx.truecorp.co.th/GetOfferRateRequest.xsd">
      <ns:SocCode>VOICE_SOC_A</ns:SocCode>
      <ns:SocCode>DATA_SOC_B</ns:SocCode>
    </ns:GetOfferRateRequest>
  </payload>
</event>
```

### §9.6 — XSLT Stylesheet Source (CES variant)

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://services.omx.truecorp.co.th/GetOfferRateRequest.xsd"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="socCodes"/>
  <xsl:template match="/">
    <createEvent><event>
      <xsl:attribute name="extId">
        <xsl:value-of select="OMXUtils:generateTrackingID()"/>
      </xsl:attribute>
      <xsl:if test="$orderRequest/OrderPriority">
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderID">
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/Customer/RefId">
        <RefID><xsl:value-of select="$orderRequest/OrderData/Customer/RefId"/></RefID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderType">
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      </xsl:if>
      <payload>
        <ns:GetOfferRateRequest>
          <xsl:for-each select="$socCodes/elements">
            <ns:SocCode><xsl:value-of select="."/></ns:SocCode>
          </xsl:for-each>
        </ns:GetOfferRateRequest>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── @extId              ← OMXUtils:generateTrackingID()                    [CES variant only]
    ├── JMSPriority         ← $orderRequest/OrderPriority                      [Conditional]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId            [Conditional]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                  [Conditional]
    ├── RefID               ← $orderRequest/OrderData/Customer/RefId           [Conditional — Customer RefId]
    ├── OrderType           ← $orderRequest/OrderData/OrderType                [Conditional]
    └── payload
        └── ns:GetOfferRateRequest
            └── ns:SocCode  ← xsl:for-each $socCodes/elements → .             [Repeated per PreExecCheck-passing SOC]
```

**Legend:**
- `[CES variant only]` — present only in GoldenDB (CES) event path
- `[Conditional]` — wrapped in `<xsl:if>`; emitted only if source value is non-empty
- `[Repeated per ...]` — iterated via `xsl:for-each`

---

## §11 Audit Logging

| Direction | Field | Value |
|-----------|-------|-------|
| Request | AUDIT_TRACE | `"Request Sent for OMX_GET_OFFER_RATE"` |
| Request | OPERATION_NAME | `"OMX_GET_OFFER_RATE"` |
| Request | Send method | `Event.sendEvent(...)` — `[Queued — not immediate]` |
| Response | AUDIT_TRACE | `"Response received for OMX_GET_OFFER_RATE"` |
| Response | OPERATION_NAME | `"OMX_GET_OFFER_RATE"` |
| Response | Send method | `Event.Ext.sendEventImmediate(...)` |

---

## §12 Activity Status Management

| Condition | Call | Code |
|-----------|------|------|
| At least one SOC qualifies and event sent | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" (RUNNING) |
| No SOCs qualify (isSkipped) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" (SKIPPED) |

---

## §13 Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Resubmit purge |
| `GetXMLForAgreementOfferFilterWithExtendedInfo(req, agRefId, soc, src)` | POU Agreement offer XML for PreExecCheck |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(req, subRefId, soc, src)` | POU Subscriber offer XML for PreExecCheck |
| `GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo(req, agRefId, soc, pOuRefId, src)` | COU Agreement offer XML for PreExecCheck |
| `GetXMLForSubscriberOfferInChildOU(req, subRefId, soc, pOuRefId)` | COU Subscriber offer XML for PreExecCheck — `[No FilterWithExtendedInfo]` |
| `IsBlankOrStringNull(value)` | Null/blank check on SOC codes and GoldenDB |
| `Collections.List.createArrayList()` | SOC dedup list creation |
| `Collections.contains / add / toArray / clear` | SOC list management |
| `Number.doubleValue(rate)` | **Response:** parse rate string to double |
| `GetActivityStatusString / SendDataToDB / SkipActivity` | Activity lifecycle management |

---

## §15 Function Dependency Tree

```text
Request_OMX_GET_OFFER_RATE (rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)  [if isActResub]
├── Collections.List.createArrayList()
├── [per offer × 4 sources]:
│   ├── XPath.evalAsString("$offer/ExtendedInfo[Name='FE_OR_CCBS']/Value")
│   ├── GetXMLForAgreementOfferFilterWithExtendedInfo
│   │   / GetXMLForSubscriberOfferFilterWithExtendedInfo
│   │   / GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo
│   │   / GetXMLForSubscriberOfferInChildOU  ← [COU Sub — different helper]
│   ├── XPath.execute(chkXPath, sXML, ns)
│   └── Collections.contains / add  [dedup]
├── Collections.toArray(arrLstSOCs)
├── IsBlankOrStringNull(GoldenDB) + String.equals("Y", GoldenDB)  [routing]
├── Event.createEvent("xslt://CES_GET_OFFER_RATE...")  [GoldenDB path]
│   └── OMXUtils:generateTrackingID()  [extId]
├── Event.createEvent("xslt://OMX_GET_OFFER_RATE...")  [default path]
├── Event.Ext.sendEventImmediate(reqEvent)
├── Event.sendEvent(auditEvent)  ← queued (not immediate)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)  [if isSkipped]
├── Collections.clear(arrLstSOCs)
└── RuleFunctions.Helpers.HandleActivityException(...)  [catch]

Response_OMX_GET_OFFER_RATE (rulefunction)
├── Instance.createInstance("xslt://OMX_GetOfferRateRes...")
│   └── OMXUtils:generateTrackingID()  [extId]
├── currActivity.Response[length] = activityRes
├── XPath.evalAsInt("count(.../xsd2:OfferRate)")
├── [per OfferRate item]:
│   ├── XPath.evalAsString(".../xsd2:SocCode")
│   ├── XPath.evalAsString(".../xsd2:RevenueType")
│   ├── XPath.evalAsString(".../xsd2:Rate")
│   └── [if revenueType not blank]:
│       └── [match offer.Soc across 4 sources]:
│           ├── offer.RevenueType = revenueType  [always overwrite]
│           └── if (offer.OfferRate == 0) offer.OfferRate = Number.doubleValue(rate)  [idempotent]
├── Event.Ext.sendEventImmediate(auditLogEvent)
└── XPath.evalAsInt("count(Response[tib:right...='000'])") → fan-in
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields | Role |
|---------|-----------|------|
| `Concepts.FM.Response.OMX_GetOfferRateRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId | Standard response fields; extId via generateTrackingID() |
| `Concepts.OrderRequest.OrderElements.AgreementOffers` | Soc, ExtendedInfo[], RelatedOffersArray[], RevenueType, OfferRate | READ + WRITTEN |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Soc, ExtendedInfo[], RelatedOffersArray[], RevenueType, OfferRate | READ + WRITTEN |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Evaluate PreExecCheck per-offer (using offer-level XML helpers) before including SOC in batch. |
| R2 | Include `FE_OR_CCBS` ExtendedInfo value as `src` parameter to PreExecCheck helpers (except COU Subscriber which uses a different helper without this parameter). |
| R3 | Collect RelatedOffersArray SOCs for any offer that passes PreExecCheck (without re-checking PreExecCheck for related offers). |
| R4 | Dedup SOC list; fire only if `socCodes.length > 0`; else skip activity. |
| R5 | Route to CES_GET_OFFER_RATE when GoldenDB=="Y" (adds extId via generateTrackingID()); OMX_GET_OFFER_RATE otherwise. |
| R6 | RefID header = Customer.RefId (not subscriber or SOC). |
| R7 | No credential gate — no UserName/PassWord headers. |
| R8 | Response: skip OfferRate items where RevenueType is blank. |
| R9 | Response: always overwrite `offer.RevenueType`; only write `offer.OfferRate` if current value == 0. |
| R10 | Response write-back applies to Agreement Offers and Subscriber Offers only — NOT RelatedOffersArray. |
| R11 | Fan-in: standard count(Response[ResponseCode suffix "000"]) == RequestCount. |
| R12 | Cleanup: clear SOC ArrayList after event fires. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **COU Subscriber uses different helper** (`GetXMLForSubscriberOfferInChildOU` vs `FilterWithExtendedInfo`) — PreExecCheck XML context differs | [MEDIUM] | Verify PreExecCheck expressions work correctly for COU subscribers; check if FE_OR_CCBS context is needed |
| **Request audit uses `Event.sendEvent`** (queued), not `sendEventImmediate` — audit may lag behind request | [MEDIUM] | Determine if queued audit is intentional; migrate accordingly; don't assume audit is synchronous |
| RelatedOffersArray SOCs collected but response rates not written back to RelatedOffersArray items | [MEDIUM] | Verify if RelatedOffersArray items need RevenueType/OfferRate populated; if so, extend response write-back |
| RefID = Customer.RefId — unusual correlation; may conflict if multiple orders share same customer | [LOW] | Verify backend uses JMSCorrelationID (OMXTrackingId) for actual correlation, not RefID |
| OfferRate idempotent (only writes if ==0) but RevenueType always overwrites — inconsistent idempotency | [LOW] | Document intentional asymmetry; test resubmit scenarios to verify correct behavior |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_OFFER_RATE {
  attribute { priority=5; forwardChain=true; }
  declare { OrderRequest orderRequest; Activity orderCurrentActivity; }
  when { /* standard 4-condition WHEN */ }
  then {
    boolean isActResub = (...);
    try {
      nextAct = ...; isSkipped = true;
      Object arrLstSOCs = Collections.List.createArrayList();

      /*** POU Agreement Offers ***/
      for (p ...) { for (o ...) {
        String src = XPath.evalAsString("$offer/ExtendedInfo[Name='FE_OR_CCBS']/Value");
        chkRes = GetXMLForAgreementOfferFilterWithExtendedInfo(..., src);
        if(chkRes == "true") { Collections.add(arrLstSOCs, socCode); // + RelatedOffers }
      }}

      /*** POU Subscriber Offers ***/
      for (s ...) { for (o ...) {
        chkRes = GetXMLForSubscriberOfferFilterWithExtendedInfo(..., src);
        if(chkRes == "true") { ... }
      }}

      /*** COU Agreement Offers ***/
      for (c ...) { for (o ...) {
        chkRes = GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo(..., src);
        if(chkRes == "true") { ... }
      }}

      /*** COU Subscriber Offers — different helper (no FilterWithExtendedInfo) ***/
      for (s ...) { for (o ...) {
        chkRes = GetXMLForSubscriberOfferInChildOU(...);  // ← different!
        if(chkRes == "true") { ... }
      }}

      Object[] socCodes = Collections.toArray(arrLstSOCs);
      if(socCodes != null && socCodes@length > 0) {
        if(GoldenDB == "Y") {
          // CES XSLT — see §9.6 for full XSLT
          Event.Ext.sendEventImmediate(reqEvent);
        } else {
          // OMX XSLT — see §9.6 for full XSLT (no extId)
          Event.Ext.sendEventImmediate(reqEvent);
        }
        isSkipped = false;
        if(!isActResub) orderCurrentActivity.RequestCount++;
        Event.sendEvent(auditEvent);  // queued — not immediate
      }

      if(!isSkipped) { GetActivityStatusString("1"); SendDataToDB(); }
      else { SkipActivity("4"); }
      Collections.clear(arrLstSOCs);
    } catch (Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §19 Response Message Rule

### §19.1 — Overview

Parses the GetOfferRateResponse, iterates per-SOC `xsd2:OfferRate` entries, and writes `RevenueType` (always) and `OfferRate` (only if == 0) back to all matching Agreement Offers and Subscriber Offers across POU and COU. Skips items with blank RevenueType. Standard "000" fan-in.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | WRITTEN — RevenueType + OfferRate per matching offer |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.OMX_GET_OFFER_RATE | Backend response |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Response[] appended; fan-in checked |

### §19.3 — ResponseBase Concept Construction (OMX_GetOfferRateRes)

```text
createObject
└── object
    ├── @extId              ← OMXUtils:generateTrackingID()              [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode                [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg                 [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus            [Conditional]
    └── ReferenceId         ← $eventResponse/RefID                       [Conditional]
```

### §19.4 — Response Completion Logic

```java
int offersCount = XPath.evalAsInt("count($eventResponse/.../xsd2:OfferRate)");
for (int i=0; i < offersCount; i++) {
    String soc = XPath.evalAsString("...xsd2:OfferRate[$i+1]/xsd2:SocCode");
    String revenueType = XPath.evalAsString("...xsd2:OfferRate[$i+1]/xsd2:RevenueType");
    String rate = XPath.evalAsString("...xsd2:OfferRate[$i+1]/xsd2:Rate");

    if (IsBlankOrStringNull(revenueType)) continue;  // skip if no revenue type

    // Match offer.Soc across 4 sources (POU/COU × Agreement/Subscriber):
    if (String.equals(soc, offer.Soc)) {
        offer.RevenueType = revenueType;                    // always overwrite
        if (offer.OfferRate == 0)
            offer.OfferRate = Number.doubleValue(rate);     // idempotent: only if 0
    }
}
```

### §19.5 — Fan-in Completion Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = '000'])
```

```java
if(currActivity.RequestCount == successResponseCount) { return "true"; }
else { return "false"; }
```

Standard "000" success count fan-in. `RequestCount` is set to 1 for single batch event (or left from resubmit). "true" returned only when all responses have "000" suffix.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
