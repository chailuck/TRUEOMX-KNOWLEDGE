# Request_SBM_CANCEL_DATA_PACK_IMMEDIATE

SBM Cancel Data Pack Immediate — function_id 100200012 (IntraActivitySequencing, POU+COU Subscriber fan-out)

---

## §1 — Overview & Purpose

This rule cancels data pack offers via SBM's DoService API (**function_id 100200012**). It iterates POU and COU Subscriber offers, evaluating a PreExecCheck with FE_OR_CCBS filtering, and dispatches one `SBM_DO_SERVICE` request per qualifying offer using the **IntraActivitySequencing** pattern (sequential, not parallel).

The cancellation mode is determined by `offer.EffectiveNextBillInd`: if `"Y"`, the offer is scheduled for removal at next bill cycle (`remove_package_code`); otherwise it is cancelled immediately (`remove_immedate_package_code`).

> **Typo in SBM parameter key [LOW]:** `"remove_immedate_package_code"` — the word "immediate" is misspelled as "immedate". This key is sent verbatim to SBM.

> **POU offerRefId double-colon [MEDIUM]:** `pOuRefId + ":" + ":" + sub.RefId + ":" + offer.Soc` produces a double colon (e.g., `POU-REF::SUB-REF:SOC-CODE`) because the COU segment is an empty string. Same issue as SBM_CANCEL_PACK_PREPAID.

> **Note:** billCycleNo IS passed to XSLT in this FM (unlike SBM_CANCEL_PACK_PREPAID where it was a dead variable). Both `billcycle` and `billcycledate` parameters receive the same `$billCycleNo` value — if they should differ, this is a bug.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_SBM_CANCEL_DATA_PACK_IMMEDIATE` |
| Author | Puttaporn-PC |
| Priority | 5 |
| ForwardChain | true |
| Target backend | SBM — DoService API |
| function_id | `"100200012"` (cancel data pack immediate) |
| Request event type | `Events.OMConsumers.OMXFM.Request.SBM_DO_SERVICE` |
| Response event type | `Events.OMConsumers.OMXFM.Response.SBM_DO_SERVICE` |
| Response concept | `Concepts.FM.Response.SBM_DoServiceRes` |
| Dispatch method | `Event.assertEvent` + `IntraActivitySequencing.ActionRequestEvent` (sequential) |
| Fan-out granularity | Per offer per subscriber (POU Subscriber + COU Subscriber) |
| Fan-in mechanism | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Resubmission handling | `PurgePendingRequestsBeforeResubmit` at start; skip by composite offerRefId |
| isBatch credential path | BATCH vs ONLINE global var path for app_user/app_password |
| Cancellation mode gate | `offer.EffectiveNextBillInd=="Y"` → `remove_package_code`; else → `remove_immedate_package_code` |
| Audit log gate | Unconditional (no AllowWriteLog) |
| Skip trigger | No qualifying offers → SkipActivity("4") |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order; subscriber and offer data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step; Response[], Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to order's next step |
| 2 | `orderCurrentActivity.ActivityID == "SBM_CANCEL_DATA_PACK_IMMEDIATE"` | FM identity |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SBM_CANCEL_DATA_PACK_IMMEDIATE"` | ProcessFlow routing |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be waiting |

---

## §5 — Execution Flow Diagram

1. Compute `isActResub`; if true → `PurgePendingRequestsBeforeResubmit`
2. Evaluate `isBatch` via XPath on `orderRequest.OrderData.IntegrationMethod`
3. Load `app_user` / `app_password` from globalVariables BATCH or ONLINE path
4. **POU Subscriber loop**: iterate ParentOU[i].Subscriber[j].SubscriberOffers[k]
5. Build composite offerRefId: `pOuRefId + ":" + ":" + sub.RefId + ":" + offer.Soc` (POU double-colon)
6. Read `filter = ExtendedInfo[FE_OR_CCBS]/Value`
7. Resubmit skip: `Response[ReferenceId==offerRefId and CompletionStatus==2]`
8. PreExecCheck via `GetXMLForSubscriberOfferFilterWithExtendedInfo` (uses filter)
9. If chkRes=="true": compute billCycleNo, channel; build SBM_DO_SERVICE event via XSLT
10. `Event.assertEvent(reqEvent)` + `IntraActivitySequencing.ActionRequestEvent(...)`
11. Emit audit log (unconditional)
12. **COU Subscriber loop**: identical — offerRefId = `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.Soc` (full composite, no double-colon)
13. Post-loop: `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)`
14. Status="1", SendDataToDB; or SkipActivity("4")
15. On exception: HandleActivityException

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### IntraActivitySequencing Pattern

This FM uses sequential (not parallel) dispatch via the IntraActivitySequencing infrastructure. All qualifying offer events are first **asserted** into working memory and registered with `ActionRequestEvent`, then `SendFirstRequestEvent` dispatches only the first one. Each response triggers dispatch of the next.

| Step | Call | Purpose |
|------|------|---------|
| On resubmit (top) | `PurgePendingRequestsBeforeResubmit(orderCurrentActivity)` | Clears queued events from prior attempt |
| Per offer (dispatch) | `Event.assertEvent(reqEvent)` | Adds event to working memory queue |
| Per offer (register) | `IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)` | Registers event in sequencer |
| Post-loop (kick-off) | `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Sends the first queued event |
| On response | `IntraActivitySequencing.ActionResponseEvent(currActivity)` | Returns "true" when all done, sends next if not |

### isBatch Credential Selection

| Condition | app_user path | app_password path |
|-----------|--------------|------------------|
| isBatch (IntegrationMethod=="BATCH") | `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/BATCH/app_user` | `.../BATCH/app_password` |
| else (ONLINE) | `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/ONLINE/app_user` | `.../ONLINE/app_password` |

### offerRefId Composition

| Scope | Formula | Issue |
|-------|---------|-------|
| POU Subscriber | `pOuRefId + ":" + ":" + sub.RefId + ":" + offer.Soc` | Double colon — COU segment is empty string [MEDIUM] |
| COU Subscriber | `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.Soc` | Correct 4-part composite |

### EffectiveNextBillInd Cancellation Mode

| Condition | SBM parameter key | Value | Meaning |
|-----------|------------------|-------|---------|
| `offer/EffectiveNextBillInd == "Y"` | `remove_package_code` | `$offer/OfferName` | Schedule removal at next bill cycle |
| else | `remove_immedate_package_code` | `$offer/OfferName` | Cancel immediately (note: key has typo) |

> **Typo [LOW]:** `"remove_immedate_package_code"` — "immedate" should be "immediate". This exact string is sent to SBM. If SBM validates key names strictly, this may silently fail.

### billCycleNo & Dual Usage

`billCycleNo = ConvertBillCycleDate(orderRequest.OrderData.Customer.BillCycleNo)` — passed to XSLT. Both `billcycle` and `billcycledate` parameters receive the same value:

| SBM Parameter | Value |
|--------------|-------|
| billcycle | `$billCycleNo` |
| billcycledate | `$billCycleNo` (identical — may be a bug if they should differ) [MEDIUM] |

---

## §7 — Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| pOuRefId | `orderRequest.OrderData.Customer.ParentOU[i].RefId` | POU reference ID for offerRefId composition |
| cOuRefId | `orderRequest.OrderData.Customer.ParentOU[i].ChildOU[x].RefId` | COU reference ID |
| sub.RefId | `subscriber.RefId` | Subscriber reference ID |
| msisdn | `sub.MSISDN` | ns:service_no |
| offerRefId | Composite key (see §6) | RefID in JMS; resubmission skip key |
| filter | `XPath: $offer/ExtendedInfo[Name="FE_OR_CCBS"]/Value` | Passed to GetXMLForSubscriberOfferFilterWithExtendedInfo |
| billCycleNo | `ConvertBillCycleDate(orderRequest.OrderData.Customer.BillCycleNo)` | ns:parameters billcycle AND billcycledate (same value) |
| channel | `GetSBMServiceChannel(orderRequest, offer)` | ns:channel |
| app_user | globalVariables BATCH or ONLINE path | ns:app_user |
| app_password | globalVariables BATCH or ONLINE path | ns:app_password |
| EffectiveNextBillInd | `offer.EffectiveNextBillInd` | Gates cancellation mode key selection |
| OfferName | `offer.OfferName` | Value of the remove_package_code parameter |
| IMSI | `sub/ResourceInfo[ResourceName="IMSI"]/ValuesArray` | ns:parameters/imsi |
| DMC_TRX_ID | `offer/ExtendedInfo[Name='DMC_TRX_ID']/Value` | ns:parameters/dmc_transaction_id (conditional: if exists) |
| PARENT_TRX_ID | `orderRequest.OrderData.ExtendedInfo[Name='PARENT_TRX_ID']/Value` | ns:parameters/parent_trx_id (conditional: OrderType='3'/'4' AND exists) |

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
| SBM | doServiceArrayRequest | `http://services.omx.truecorp.co.th/FMServices/SBMDoserviceArrayRequest` | `100200012` |

### §8.3 — ExtendedInfo Fields Required

| Name | Level | Required/Optional | Where Used |
|------|-------|------------------|-----------|
| FE_OR_CCBS | Offer | Optional | filter → passed to PreExecCheck helper for filtering |
| DMC_TRX_ID | Offer | Optional | ns:parameters/dmc_transaction_id — if exists |
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
| `$offer` | SubscriberOffers concept | EffectiveNextBillInd, OfferName, ExtendedInfo |
| `$billCycleNo` | ConvertBillCycleDate(...) | ns:parameters billcycle and billcycledate (same value) |
| `$sub` | Subscriber concept | ResourceInfo[IMSI] |
| `$msisdn` | sub.MSISDN | ns:service_no |

### §9.2 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | xsl:if present |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | xsl:if present |
| OrderID | `$orderRequest/OrderData/OrderID` | xsl:if present |
| **RefID** | `$offerRefId` (composite) | **Always** (unconditional) |
| OrderType | `$orderRequest/OrderData/OrderType` | xsl:if present |

### §9.3 — Conditional Parameters

| Parameter key | Condition | Value |
|--------------|-----------|-------|
| remove_package_code | EffectiveNextBillInd=="Y" | offer.OfferName |
| remove_immedate_package_code | else (immediate cancellation) | offer.OfferName |
| billcycle | Always | $billCycleNo |
| billcycledate | Always | $billCycleNo (same value as billcycle) |
| imsi | Always | sub/ResourceInfo[ResourceName="IMSI"]/ValuesArray |
| dmc_transaction_id | if exists(offer/ExtendedInfo[Name='DMC_TRX_ID']/Value) | DMC_TRX_ID ExtendedInfo value |
| parent_trx_id | OrderType='3' OR '4' AND exists(PARENT_TRX_ID ExtendedInfo) | PARENT_TRX_ID ExtendedInfo value |

### §9.4 — XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:ns1="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceArrayRequest"
  xmlns:ns="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceRequest"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="offerRefId"/>
  <xsl:param name="app_password"/>
  <xsl:param name="app_user"/>
  <xsl:param name="channel"/>
  <xsl:param name="offer"/>
  <xsl:param name="billCycleNo"/>
  <xsl:param name="sub"/>
  <xsl:param name="msisdn"/>
  <!-- JMS headers -->
  <xsl:if test="$orderRequest/OrderPriority">
    <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
  </xsl:if>
  <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
    <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
  </xsl:if>
  <xsl:if test="$orderRequest/OrderData/OrderID">
    <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
  </xsl:if>
  <RefID><xsl:value-of select="$offerRefId"/></RefID>  <!-- Always: unconditional -->
  <xsl:if test="$orderRequest/OrderData/OrderType">
    <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
  </xsl:if>
  <!-- Payload -->
  <ns:app_password><xsl:value-of select="$app_password"/></ns:app_password>
  <ns:app_user><xsl:value-of select="$app_user"/></ns:app_user>
  <ns:channel><xsl:value-of select="$channel"/></ns:channel>
  <ns:function_id><xsl:value-of select="'100200012'"/></ns:function_id>
  <ns:parameters>
    <xsl:choose>
      <xsl:when test="$offer/EffectiveNextBillInd='Y'">
        <ns:item><ns:key>remove_package_code</ns:key>
          <ns:value><xsl:value-of select="$offer/OfferName"/></ns:value></ns:item>
      </xsl:when>
      <xsl:otherwise>
        <ns:item><ns:key>remove_immedate_package_code</ns:key>  <!-- typo: "immedate" -->
          <ns:value><xsl:value-of select="$offer/OfferName"/></ns:value></ns:item>
      </xsl:otherwise>
    </xsl:choose>
    <ns:item><ns:key>billcycle</ns:key>
      <ns:value><xsl:value-of select="$billCycleNo"/></ns:value></ns:item>
    <ns:item><ns:key>billcycledate</ns:key>
      <ns:value><xsl:value-of select="$billCycleNo"/></ns:value></ns:item>
    <ns:item><ns:key>imsi</ns:key>
      <ns:value><xsl:value-of select="$sub/ResourceInfo[ResourceName='IMSI']/ValuesArray"/></ns:value></ns:item>
    <xsl:if test="exists($offer/ExtendedInfo[Name='DMC_TRX_ID']/Value)">
      <ns:item><ns:key>dmc_transaction_id</ns:key>
        <ns:value><xsl:value-of select="$offer/ExtendedInfo[Name='DMC_TRX_ID']/Value"/></ns:value></ns:item>
    </xsl:if>
    <xsl:if test="$orderRequest/OrderData/OrderType='3' or $orderRequest/OrderData/OrderType='4'">
      <xsl:if test="exists($orderRequest/OrderData/ExtendedInfo[Name='PARENT_TRX_ID']/Value)">
        <ns:item><ns:key>parent_trx_id</ns:key>
          <ns:value><xsl:value-of select="$orderRequest/OrderData/ExtendedInfo[Name='PARENT_TRX_ID']/Value"/></ns:value></ns:item>
      </xsl:if>
    </xsl:if>
  </ns:parameters>
  <ns:service_no><xsl:value-of select="$msisdn"/></ns:service_no>
</xsl:stylesheet>
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
                ├── ns:app_password   ← $app_password (BATCH/ONLINE global var)  [Always]
                ├── ns:app_user       ← $app_user (BATCH/ONLINE global var)       [Always]
                ├── ns:channel        ← $channel (GetSBMServiceChannel)           [Always]
                ├── ns:function_id    ← "100200012" (static)                      [Always]
                ├── ns:parameters
                │   ├── ns:item[remove_package_code]        ← $offer/OfferName   [Conditional: EffectiveNextBillInd=="Y"]
                │   ├── ns:item[remove_immedate_package_code] ← $offer/OfferName [Conditional: otherwise (typo in key)]
                │   ├── ns:item[billcycle]                  ← $billCycleNo       [Always]
                │   ├── ns:item[billcycledate]              ← $billCycleNo (same value) [Always]
                │   ├── ns:item[imsi]                       ← sub/ResourceInfo[IMSI]/ValuesArray [Always]
                │   ├── ns:item[dmc_transaction_id]         ← ExtendedInfo[DMC_TRX_ID]/Value [Conditional: if exists]
                │   └── ns:item[parent_trx_id]             ← ExtendedInfo[PARENT_TRX_ID]/Value [Conditional: OrderType='3'/'4' AND exists]
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
| Request | OPERATION_NAME | "SBM_CANCEL_DATA_PACK_IMMEDIATE" |
| Request | AUDIT_TRACE | "Request Sent for SBM_CANCEL_DATA_PACK_IMMEDIATE" |
| Request | payload | Conditional: WritePayload="true" |
| Response | PROCESS_ID | `concat($pid, "_RES")` |
| Response | AUDIT_TRACE | "Response received for SBM_CANCEL_DATA_PACK_IMMEDIATE" |

---

## §12 — Activity Status Management

| Transition | Code | Trigger |
|-----------|------|---------|
| Running | "1" | At least one offer queued; SendFirstRequestEvent called |
| Skip | "4" | No qualifying offers |
| Error | HandleActivityException | Any uncaught exception |

---

## §13 — Exception / Error Handling

`try { ... } catch (Exception ae) { HandleActivityException(...); }`. Two commented-out `System.debugOut` lines at rule entry and exit.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears queued events on resubmission |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, soc, filter)` | Builds PreExecCheck XML with FE_OR_CCBS filter for POU |
| `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, refId, soc, pOuRefId, filter)` | Builds PreExecCheck XML with FE_OR_CCBS filter for COU |
| `ConvertBillCycleDate(billCycleNo)` | Converts bill cycle number; result used as both billcycle and billcycledate |
| `GetSBMServiceChannel(orderRequest, offer)` | Derives SBM channel for the offer |
| `IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)` | Registers event in sequential queue |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Dispatches first queued event after all offers registered |
| `IntraActivitySequencing.ActionResponseEvent(currActivity)` | Response fan-in; returns "true" when all sequential offers processed |
| `GetActivityStatusString("1", false)` | Returns "Running" status |
| `SendDataToDB(orderRequest)` | Persists state |
| `SkipActivity(..., "4")` | Skip handler |
| `HandleActivityException(...)` | Central exception handler |

---

## §15 — Function Dependency Tree

```text
Request_SBM_CANCEL_DATA_PACK_IMMEDIATE.rule
├── isActResub check
│   └── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity) [if isActResub]
├── isBatch = XPath($orderRequest/OrderData/IntegrationMethod == 'BATCH')
├── app_user / app_password from globalVariables (BATCH or ONLINE path)
│
├── [POU Subscriber loop: ParentOU[i].Subscriber[j].SubscriberOffers[k]]
│   ├── offerRefId = pOuRefId + ":" + ":" + sub.RefId + ":" + offer.Soc  [DOUBLE COLON]
│   ├── filter = XPath($offer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── Response[ReferenceId==offerRefId and CompletionStatus==2]  [resubmit skip]
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, sub.RefId, offer.Soc, filter)
│   ├── [if chkRes=="true"]
│   │   ├── ConvertBillCycleDate(BillCycleNo) → billCycleNo
│   │   ├── GetSBMServiceChannel(orderRequest, offer) → channel
│   │   ├── Event.createEvent(SBM_DO_SERVICE XSLT — see §9.4)
│   │   ├── Event.assertEvent(reqEvent)
│   │   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│   │   └── Event.Ext.sendEventImmediate(audit Logger)
│
├── [COU Subscriber loop: ChildOU[x].Subscriber[y].SubscriberOffers[z]]
│   ├── offerRefId = pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.Soc  [correct]
│   └── [same structure as POU Subscriber]
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
| `Concepts.OrderRequest.OrderRequest` | OrderData.IntegrationMethod, OrderData.Customer.BillCycleNo, OrderData.OMXTrackingId, OrderData.OrderID, OrderData.OrderType, OrderData.ExtendedInfo[PARENT_TRX_ID], OrderPriority, Customer.ParentOU[], ChildOU[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, SubscriberOffers[], ResourceInfo[IMSI] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Soc, OfferName, EffectiveNextBillInd, ExtendedInfo[FE_OR_CCBS, DMC_TRX_ID] |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck |
| `Concepts.FM.Response.SBM_DoServiceRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, DoServiceResponse (nested) |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Cancel data pack offers via SBM DoService (function_id 100200012) for POU and COU subscribers |
| R2 | Sequential dispatch using IntraActivitySequencing; one offer at a time |
| R3 | EffectiveNextBillInd=="Y" → remove_package_code (next bill); else → remove_immedate_package_code (immediate) |
| R4 | Pass billcycle, billcycledate, IMSI, app_user/password, channel, service_no |
| R5 | Conditional: DMC_TRX_ID if exists; PARENT_TRX_ID if OrderType='3'/'4' and exists |
| R6 | BATCH vs ONLINE credential selection from global variables |
| R7 | FE_OR_CCBS filter passed to PreExecCheck helper for per-offer eligibility |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| POU offerRefId double-colon — COU segment empty in POU formula | [MEDIUM] | Fix: `pOuRefId + "::" + sub.RefId + ":" + offer.Soc` or use a 4-part separator; align with COU formula |
| billcycle and billcycledate both map to the same `$billCycleNo` — may be incorrect if they represent different units | [MEDIUM] | Verify with SBM team whether billcycle (number) and billcycledate (date string) should differ |
| Typo: "remove_immedate_package_code" — SBM may reject unknown key name | [LOW] | Fix key string to "remove_immediate_package_code"; verify SBM API documentation |

---

## §18 — Full Source Code (Request Rule — abbreviated)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_SBM_CANCEL_DATA_PACK_IMMEDIATE {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "SBM_CANCEL_DATA_PACK_IMMEDIATE";
    orderRequest.ProcessFlow.NextActivityID == "SBM_CANCEL_DATA_PACK_IMMEDIATE";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      if(isActResub) { IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity); }
      boolean isBatch = XPath.evalAsBoolean(/* IntegrationMethod == 'BATCH' */);
      /* load app_user / app_password from globalVars BATCH or ONLINE path */
      for (POU loop) {
        offerRefId = pOuRefId + ":" + ":" + sub.RefId + ":" + offer.Soc; // DOUBLE COLON
        filter = XPath($offer/ExtendedInfo[FE_OR_CCBS]/Value);
        if(!reqSuccess && chkRes=="true") {
          billCycleNo = ConvertBillCycleDate(BillCycleNo);
          channel = GetSBMServiceChannel(orderRequest, offer);
          reqEvent = Event.createEvent(/* XSLT — see §9.4 — function_id=100200012 */);
          Event.assertEvent(reqEvent);
          IntraActivitySequencing.ActionRequestEvent(reqEvent, activity);
          audit log; // unconditional
        }
      }
      for (COU loop) { /* same; offerRefId = full 4-part composite */ }
      IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
      Status="1"; SendDataToDB; // or SkipActivity("4")
    } catch(Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 — Overview

Creates `SBM_DoServiceRes` concept, appends to `currActivity.Response[]`, logs audit unconditionally, returns via `IntraActivitySequencing.ActionResponseEvent` ("true" when all sequential offers done). DoServiceResponse sub-object is mapped from `ns:doServiceArrayResponse/ns:DoServiceReturn` path only (no `xsl:choose` — unlike SBM_CANCEL_PACK_PREPAID which has a CheckPackAllowReturn alternative path).

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
    └── DoServiceResponse @extId ← concat("SBM:CANCEL_IMM:", OMXTrackingId, ":", RefID)
        │                                                          [Conditional: if ns:DoServiceReturn exists]
        ├── extra_xml           ← ns:DoServiceReturn/ns1:extra_xml        [Conditional]
        ├── req_transaction_id  ← ns:DoServiceReturn/ns1:req_transaction_id [Conditional]
        ├── response_message    ← ns:DoServiceReturn/ns1:response_message [Conditional]
        ├── result_code         ← ns:DoServiceReturn/ns1:result_code      [Conditional]
        ├── result_desc         ← ns:DoServiceReturn/ns1:result_desc      [Conditional]
        ├── result_namespace    ← ns:DoServiceReturn/ns1:result_namespace [Conditional]
        └── transaction_id      ← ns:DoServiceReturn/ns1:transaction_id   [Conditional]
```

### §19.4 — Fan-in Completion Logic

| Call | Returns |
|------|---------|
| `IntraActivitySequencing.ActionResponseEvent(currActivity)` | "true" when all sequential offers processed; "false" when more remain |

### §19.5 — Difference from SBM_CANCEL_PACK_PREPAID Response

| Aspect | SBM_CANCEL_DATA_PACK_IMMEDIATE | SBM_CANCEL_PACK_PREPAID |
|--------|-------------------------------|------------------------|
| DoServiceResponse @extId prefix | `"SBM:CANCEL_IMM:"` | `"SBM:CANCEL_PACK:"` |
| Response payload path | `ns:DoServiceReturn` only | `xsl:choose`: CheckPackAllowReturn OR DoServiceReturn |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
