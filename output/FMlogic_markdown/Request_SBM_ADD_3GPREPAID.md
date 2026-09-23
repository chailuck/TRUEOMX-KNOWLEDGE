# Request_SBM_ADD_3GPREPAID

> External OMXFM — SBM 3G Prepaid Package Provisioning · doServiceArrayRequest schema

**Rule class:** `Rules.OMConsumers.OMXFM.Request.Request_SBM_ADD_3GPREPAID`
**Backend:** SBM (Service Billing Manager) | **Integration:** JMS / Async | **Author:** Usuf C.

---

## §1 — Overview & Purpose

`SBM_ADD_3GPREPAID` provisions a 3G prepaid package (SOC/offer) through the SBM (Service Billing Manager) system.
For each SubscriberOffer on both ParentOU and ChildOU subscribers, it sends a `doServiceArrayRequest` that bundles
two sub-calls: an optional `CheckPackAllowRequest` (to validate whether the package is allowed, functionId=100200024)
followed by a mandatory `DoServiceRequest` (functionId=100200004). Credentials (app_user/app_password) are selected
between BATCH and ONLINE modes based on the order's IntegrationMethod.

| Property | Value |
|----------|-------|
| Rule class | `Rules.OMConsumers.OMXFM.Request.Request_SBM_ADD_3GPREPAID` |
| Backend System | SBM (Service Billing Manager) |
| Integration type | JMS / Async |
| Request event | `Events.OMConsumers.OMXFM.Request.SBM_3GPREPAID` |
| Response event | `Events.OMConsumers.OMXFM.Response.SBM_3GPREPAID` |
| Schema | `ns1:doServiceArrayRequest` (SBMDoServiceArrayRequest.xsd) |
| Destination | `SBM_3GPREPAID` on channel `/Channels/OMXFMConnectionRequest` |
| functionId (DoService) | `100200004` (hardcoded) |
| functionId (CheckPackAllow) | `100200024` (hardcoded) |
| RefID (ParentOU) | `{pOuRefId}::{sub.RefId}:{offer.OfferName}` (double-colon — see §17 bug) |
| RefID (ChildOU) | `{pOuRefId}:{cOuRefId}:{sub.RefId}:{offer.OfferName}` |
| Completion pattern | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Resubmit support | Yes — `PurgePendingRequestsBeforeResubmit` |
| Also reads next activity PreExecCheck | Yes |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule Name | `Request_SBM_ADD_3GPREPAID` | External OMXFM request rule |
| Namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Priority | 5 | |
| forwardChain | true | |
| Author | Usuf C. | |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — Customer hierarchy, IntegrationMethod, credentials mode |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — Response[], RequestCount, Status |

> `nextAct` is fetched dynamically via `Instance.getByExtIdByUri` for PreExecCheck evaluation.

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Bind to current step |
| 2 | `orderCurrentActivity.ActivityID == "SBM_ADD_3GPREPAID"` | Route to this rule |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SBM_ADD_3GPREPAID"` | Cross-check ProcessFlow state |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Ready to execute |

---

## §5 — Execution Flow

1. **Setup variables** — `functionId = "100200004"` (hardcoded). `reqTransactionId = concat(Channel, "_", OMXTrackingId)`. `isActResub = (RequestCount > 0 && IsOrderResubmitted)`. If isActResub: `PurgePendingRequestsBeforeResubmit()`.
2. **Read mode-dependent credentials** — `isBatch = (IntegrationMethod == 'BATCH')`. If BATCH: read `globalVariables/.../SBM_DO_SERVICE/BATCH/app_user+app_password`. If ONLINE: read ONLINE equivalents.
3. **Read checkPackAllowFlg** — from `orderRequest.OrderData.ExtendedInfo[CHECK_PACK_ALLOW_FLG]/Value`. Default to "Y" if null or blank.
4. **Read next activity PreExecCheck** — `nextAct = Instance.getByExtIdByUri(NextActivityName)` → `chkXPath = nextAct.PreExecCheck`.
5. **ParentOU Subscriber Offers loop** — RefID = `{pOuRefId}::{sub.RefId}:{offer.OfferName}`. Per offer: read FE_OR_CCBS filter, check reqSuccess guard, evaluate PreExecCheck (`GetXMLForSubscriberOfferFilterWithExtendedInfo`). If passed: compute `channel`, build doServiceArrayRequest event, assert and `ActionRequestEvent`.
6. **ChildOU Subscriber Offers loop** — Same logic. RefID = 4-part: `{pOuRefId}:{cOuRefId}:{sub.RefId}:{offer.OfferName}`. Uses `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo`.
7. **Status branch** — Any sent: `SendFirstRequestEvent` + `GetActivityStatusString("1", false)` + `SendDataToDB`. All skipped: `SkipActivity("4")`.
8. **Exception** — `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §7 — Data Extraction & Key Variables

| Variable | Source | Notes |
|----------|--------|-------|
| `functionId` | Hardcoded `"100200004"` | SBM DoService function ID for prepaid package add |
| `reqTransactionId` | `concat(Channel, "_", OMXTrackingId)` | SBM req_transaction_id correlation |
| `isBatch` | `orderRequest.OrderData.IntegrationMethod == 'BATCH'` | Selects credential set |
| `checkPackAllowFlg` | `orderRequest.OrderData.ExtendedInfo[CHECK_PACK_ALLOW_FLG]/Value` | Default "Y" — controls CheckPackAllow sub-call |
| `app_user / app_password` | `globalVariables/.../SBM_DO_SERVICE/BATCH|ONLINE` | Mode-dependent credentials |
| `channel` | `GetSBMServiceChannel(orderRequest, offer)` | SBM channel value |
| `billCycleNo` | `ConvertBillCycleDate(BillCycleNo)` | **Dead variable — computed but NOT used in XSLT payload** |
| `offerRefId` (ParentOU) | `pOuRefId + ":" + ":" + sub.RefId + ":" + offer.OfferName` | **Double colon — likely a bug (see §17)** |
| `offerRefId` (ChildOU) | `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.OfferName` | 4-part format |

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event | Protocol | Purpose |
|-----------|-------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.SBM_3GPREPAID` | JMS | Submit doServiceArrayRequest to SBM via OMXFM channel |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.SBM_3GPREPAID` | JMS | Receive doServiceArrayResponse from SBM |

### §8.3 Backend API Details

| System | Operation | functionId | Condition |
|--------|-----------|------------|-----------|
| SBM | CheckPackAllow | 100200024 | Only when `checkPackAllowFlg='Y'` OR `isActResub=true` |
| SBM | DoService (Add 3G Prepaid) | 100200004 | Always present in every request |

> Both sub-calls are wrapped inside a single `ns1:doServiceArrayRequest` dispatched as one JMS message.

### §8.4 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `orderRequest.OrderData.IntegrationMethod` | READ | BATCH vs ONLINE credential selection |
| `orderRequest.OrderData.ExtendedInfo[CHECK_PACK_ALLOW_FLG]` | READ | Skip CheckPackAllow if "N" |
| `offer.OfferName` | READ | SBM package_code |
| `offer.ExtendedInfo[FE_OR_CCBS]` | READ | Filter (FE vs CCBS) |
| `offer.ExtendedInfo[DESTINATION_COUNTRY]` | READ | Conditional CheckPackAllow country1 param |
| `offer.ExtendedInfo[PRICE_EX_VAT, PRICE_IN_VAT, QUOTA_BUNDLE]` | READ | Optional DoService parameters |
| `offer.EffectiveDate` | READ | CheckPackAllow effective_date (if DESTINATION_COUNTRY present) |
| `sub.SubscriberGeneralInfo.saleId` | READ | ccr_login prefix |
| `orderCurrentActivity.Response[]` | READ/WRITE | reqSuccess guard + response appended |
| `orderCurrentActivity.RequestCount` | WRITE | Managed by IntraActivitySequencing |

### §8.5 Global Variable Dependencies

| Path | Used for |
|------|----------|
| `globalVariables/OMX_OM/Services/SBM_DO_SERVICE/BATCH/app_user` | Batch mode SBM username |
| `globalVariables/OMX_OM/Services/SBM_DO_SERVICE/BATCH/app_password` | Batch mode SBM password |
| `globalVariables/OMX_OM/Services/SBM_DO_SERVICE/ONLINE/app_user` | Online mode SBM username |
| `globalVariables/OMX_OM/Services/SBM_DO_SERVICE/ONLINE/app_password` | Online mode SBM password |
| `globalVariables/OMX_OM/WritePayload` | Controls audit log payload capture |

---

## §9 — Detailed Payload Build

```xml
<ns1:doServiceArrayRequest
  xmlns:ns1="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceArrayRequest"
  xmlns:ns="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceRequest">

  <!-- CheckPackAllowRequest: conditional — only when checkPackAllowFlg='Y' OR isActResub=true -->
  <ns1:CheckPackAllowRequest>
    <ns:app_password>app_password</ns:app_password>
    <ns:app_user>app_user</ns:app_user>
    <ns:channel>channel</ns:channel>
    <ns:function_id>100200024</ns:function_id>  <!-- static -->
    <ns:parameters>
      <ns:item><ns:key>package_code</ns:key><ns:value>offer.OfferName</ns:value></ns:item>
      <ns:item><ns:key>get_error_flag</ns:key><ns:value>Y</ns:value></ns:item>
      <!-- if DESTINATION_COUNTRY present -->
      <ns:item><ns:key>country1</ns:key><ns:value>ExtendedInfo[DESTINATION_COUNTRY]/Value</ns:value></ns:item>
      <!-- if also EffectiveDate present -->
      <ns:item><ns:key>effective_date</ns:key><ns:value>format(EffectiveDate,'dd/MM/yyyy HH:mm:ss',+07:00)</ns:value></ns:item>
    </ns:parameters>
    <ns:service_no>msisdn</ns:service_no>
  </ns1:CheckPackAllowRequest>

  <!-- DoServiceRequest: always present -->
  <ns1:DoServiceRequest>
    <ns:app_password>app_password</ns:app_password>
    <ns:app_user>app_user</ns:app_user>
    <ns:channel>channel</ns:channel>
    <ns:function_id>100200004</ns:function_id>  <!-- $functionId param -->
    <ns:parameters>
      <ns:item><ns:key>package_code</ns:key><ns:value>offer.OfferName</ns:value></ns:item>
      <ns:item><ns:key>mode</ns:key><ns:value>sync</ns:value></ns:item>  <!-- static -->
      <ns:item><ns:key>ccr_login</ns:key><ns:value>concat(saleId,';',DealerCode)</ns:value></ns:item>
      <ns:item><ns:key>channel_tx_id</ns:key><ns:value>orderRequest.OrderData.OrderID</ns:value></ns:item>
      <!-- conditional -->
      <ns:item><ns:key>price_ex_vat</ns:key><ns:value>ExtendedInfo[PRICE_EX_VAT]/Value</ns:value></ns:item>
      <ns:item><ns:key>price_in_vat</ns:key><ns:value>ExtendedInfo[PRICE_IN_VAT]/Value</ns:value></ns:item>
      <ns:item><ns:key>bundle_level</ns:key><ns:value>ExtendedInfo[QUOTA_BUNDLE]/Value</ns:value></ns:item>
    </ns:parameters>
    <ns:req_transaction_id>reqTransactionId</ns:req_transaction_id>
    <ns:service_no>msisdn</ns:service_no>
  </ns1:DoServiceRequest>
</ns1:doServiceArrayRequest>
```

---

## §10 — XSLT Field Mapping — Output XML Tree

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                            [Conditional]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId                 [Conditional]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID                        [Conditional]
    ├── RefID                    ← $offerRefId                                            [Always]
    ├── OrderType                ← $orderRequest/OrderData/OrderType                      [Conditional]
    └── payload
        └── ns1:doServiceArrayRequest
            ├── ns1:CheckPackAllowRequest    [Conditional: checkPackAllowFlg='Y' OR isActResub]
            │   ├── ns:app_password          ← $app_password (globalVars BATCH|ONLINE)    [Always]
            │   ├── ns:app_user              ← $app_user (globalVars BATCH|ONLINE)        [Always]
            │   ├── ns:channel               ← GetSBMServiceChannel(orderRequest, offer)  [Always]
            │   ├── ns:function_id           ← "100200024"                                [Always]
            │   ├── ns:item[package_code]    ← $offer/OfferName                          [Always]
            │   ├── ns:item[get_error_flag]  ← "Y"                                       [Always]
            │   ├── ns:item[country1]        ← ExtendedInfo[DESTINATION_COUNTRY]/Value   [Conditional]
            │   ├── ns:item[effective_date]  ← format(EffectiveDate, dd/MM/yyyy, +07:00) [Conditional: DESTINATION_COUNTRY AND EffectiveDate]
            │   └── ns:service_no            ← $msisdn                                   [Always]
            └── ns1:DoServiceRequest                                                       [Always]
                ├── ns:app_password / ns:app_user / ns:channel  ← same as above           [Always]
                ├── ns:function_id           ← "100200004" ($functionId param)            [Always]
                ├── ns:item[package_code]    ← $offer/OfferName                          [Always]
                ├── ns:item[mode]            ← "sync"                                     [Always]
                ├── ns:item[ccr_login]       ← concat(saleId,';',DealerCode)             [Always]
                ├── ns:item[channel_tx_id]   ← $orderRequest/OrderData/OrderID            [Always]
                ├── ns:item[price_ex_vat]    ← ExtendedInfo[PRICE_EX_VAT]/Value          [Conditional]
                ├── ns:item[price_in_vat]    ← ExtendedInfo[PRICE_IN_VAT]/Value          [Conditional]
                ├── ns:item[bundle_level]    ← ExtendedInfo[QUOTA_BUNDLE]/Value          [Conditional]
                ├── ns:req_transaction_id    ← $reqTransactionId (Channel_OMXTrackingId) [Always]
                └── ns:service_no            ← $msisdn                                   [Always]
```

---

## §11 — Audit Logging

| Phase | AUDIT_TRACE | PROCESS_ID |
|-------|-------------|------------|
| Request sent (per offer) | `Request Sent for SBM_ADD_3GPREPAID` | `concat($pid, "_REQ")` |
| Response received | `Response received for SBM_ADD_3GPREPAID` | `concat($pid, "_RES")` |

---

## §12 — Activity Status Management

| Condition | Status | Additional action |
|-----------|--------|------------------|
| At least one request sent | `GetActivityStatusString("1", false)` | `SendFirstRequestEvent` + `SendDataToDB` |
| No offers sent | [SKIPPED] | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception | Error state | `HandleActivityException` |

---

## §15 — Function Dependency Tree

```text
Request_SBM_ADD_3GPREPAID (rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()   [resubmit purge]
├── Instance.getByExtIdByUri(NextActivityName)                      [next activity PreExecCheck]
├── XPath.evalAsBoolean()                                           [isBatch: IntegrationMethod='BATCH']
├── XPath.evalAsString() × 2                                        [app_user, app_password from globalVars]
├── XPath.evalAsString()                                            [checkPackAllowFlg from order ExtendedInfo]
├── (per offer loop — ParentOU)
│   ├── XPath.evalAsString()                                        [FE_OR_CCBS filter]
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo()            [PreExecCheck XML]
│   ├── XPath.execute()                                             [evaluate PreExecCheck]
│   ├── ConvertBillCycleDate(BillCycleNo)                           [dead variable — result not used]
│   ├── GetSBMServiceChannel(orderRequest, offer)                    [channel value]
│   ├── Event.createEvent(xslt://SBM_3GPREPAID)                     [build doServiceArrayRequest]
│   ├── Event.assertEvent(reqEvent)                                 [assert into WM]
│   └── IntraActivitySequencing.ActionRequestEvent(reqEvent, ...)   [register request]
├── (per offer loop — ChildOU)
│   ├── GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo()   [PreExecCheck XML]
│   └── ... (same as ParentOU)
├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)  [dispatch first JMS]
├── GetActivityStatusString("1", false)                             [IN_PROGRESS]
├── SendDataToDB(orderRequest)                                      [persist]
├── SkipActivity(orderRequest, orderCurrentActivity, "4")           [skip path]
└── HandleActivityException()                                       [error path]

Response_SBM_ADD_3GPREPAID (rulefunction)
├── OMXUtils.generateTrackingID()                                   [extId]
├── Instance.createInstance(xslt://SBM_DoServiceRes)                [create response concept]
│   → maps ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, DoServiceResponse[]
├── (OMX-3001 FE writeback loop — ParentOU + ChildOU)
│   ├── XPath.evalAsBoolean()                                       [isSubOfferFromFE: FE_OR_CCBS="FE"]
│   └── Instance.createInstance(xslt://SubscriberOffersExtendedInfo)
│       → Name="SBM_TRX_ID", Value=DoServiceReturn/ns:transaction_id
├── Event.Ext.sendEventImmediate()                                   [audit log]
└── IntraActivitySequencing.ActionResponseEvent(currActivity)        [fan-in → "true"/"false"]
```

---

## §17 — Migration Notes & Recommendations

### Known Issues

> **[HIGH] Bug — Double colon in ParentOU RefID (rule line 78):**
> `offerRefId = pOuRefId + ":" + ":" + refId + ":" + offer.OfferName`
> Produces `PAGR1::SUB1:PKG` with a double-colon separator. ChildOU uses a correct 4-part format.
> This inconsistency means the RefID format differs between ParentOU and ChildOU, which may break
> response correlation if anything parses the RefID by splitting on `:`.

> **[HIGH] Bug — QUOTA_BUNDLE XPath typo in ChildOU variant (rule line 164):**
> `ExtendedInfo[Name="QUOTA_BUNDLE]"]/Value` — the closing `]` is inside the string literal,
> so the predicate `[Name="QUOTA_BUNDLE]"]` will never match any ExtendedInfo element.
> The `bundle_level` parameter is silently dropped for all ChildOU subscriber offers.
> ParentOU variant (line 106) is correct.

> **[MEDIUM] Dead variable — billCycleNo:**
> `billCycleNo = ConvertBillCycleDate(BillCycleNo)` is computed per-offer but never passed
> as an XSLT parameter and has no effect on the payload.

> **[LOW] TODO placeholder — query_trans_id:**
> `String query_trans_id = ""; //TODO` — declared but never implemented.

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | doServiceArrayRequest must bundle CheckPackAllow + DoService in one JMS message per offer | [HIGH] |
| R2 | CheckPackAllow conditionally omitted when checkPackAllowFlg="N" AND not resubmitting | [HIGH] |
| R3 | BATCH vs ONLINE credential selection via IntegrationMethod | [HIGH] |
| R4 | SBM_TRX_ID writeback to FE offers only (OMX-3001 markused flow) | [HIGH] |
| R5 | DESTINATION_COUNTRY + effective_date conditional in CheckPackAllow (roaming/IDD use case) | [MEDIUM] |
| R6 | IntraActivitySequencing fan-in (not count(000)) — preserve ActionResponseEvent pattern | [MEDIUM] |
| R7 | Fix double-colon RefID bug in ParentOU before migration | [MEDIUM] |
| R8 | Fix QUOTA_BUNDLE XPath bug in ChildOU variant | [MEDIUM] |

---

## §19 — Response Message Rule

### §19.1 Overview

`Response_SBM_ADD_3GPREPAID.rulefunction` handles the async reply from SBM FM. It creates an `SBM_DoServiceRes`
concept (including DoServiceReturn detail elements), then — as part of OMX-3001 (TrueID+ markused flow) — writes
back `SBM_TRX_ID` onto every FE-origin offer. Fan-in is driven by `IntraActivitySequencing.ActionResponseEvent`
(not a manual count).

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order — offer ExtendedInfo updated with SBM_TRX_ID |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SBM_3GPREPAID` | JMS response from SBM |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] array |

### §19.3 Response Concept Construction (SBM_DoServiceRes)

```text
createObject                          ← extId = OMXUtils.generateTrackingID()                        [Always]
└── SBM_DoServiceRes
    ├── ResponseCode                  ← $eventResponse/ResponseCode                                   [Conditional]
    ├── ResponseMessage               ← $eventResponse/ResponseMsg                                    [Conditional]
    ├── CompletionStatus              ← $eventResponse/CompletionStatus                              [Conditional]
    ├── ReferenceId                   ← $eventResponse/RefID                                         [Conditional]
    └── DoServiceResponse[]* (for-each ns1:doServiceArrayResponse/ns1:DoServiceReturn)               [Conditional]
        ├── extra_xml                 ← ns2:extra_xml
        ├── req_transaction_id        ← ns2:req_transaction_id
        ├── response_message          ← ns2:response_message
        ├── result_code               ← ns2:result_code
        ├── result_desc               ← ns2:result_desc
        ├── result_namespace          ← ns2:result_namespace
        └── transaction_id            ← ns2:transaction_id
```

### §19.4 SBM_TRX_ID Writeback (OMX-3001)

| ExtendedInfo Name | Value source | Condition |
|-------------------|--------------|-----------|
| `SBM_TRX_ID` | `$eventResponse/payload/ns1:doServiceArrayResponse/ns1:DoServiceReturn/ns:transaction_id` | `FE_OR_CCBS="FE"` on offer |

> **Note:** Transaction ID is written from the first DoServiceReturn element — if multiple exist, all FE offers receive the same first one's transaction_id.

### §19.5 Response Completion Logic

```java
if (RuleFunctions.Helpers.IntraActivitySequencing.ActionResponseEvent(currActivity)) {
    return "true";   // All parallel SBM requests matched — activity complete
} else {
    return "false";  // Still waiting for more responses
}
```

> Uses `IntraActivitySequencing.ActionResponseEvent` for fan-in — NOT the manual `count(Response[000])` XPath pattern.
> Consistent with the request side's `ActionRequestEvent`/`SendFirstRequestEvent` sequencing.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
