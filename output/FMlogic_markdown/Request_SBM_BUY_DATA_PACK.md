# Request_SBM_BUY_DATA_PACK

> TIBCO BusinessEvents FM Logic — SBM Data Pack Purchase (IntraActivitySequencing / Dual Payload / Dynamic Offer Injection)

**Author:** Puttaporn-PC | **Priority:** 5 | **JMS Event:** SBM_DO_SERVICE | **Pattern:** IntraActivitySequencing throttled dispatch | **Lines:** 191 (request) + 440 (response)

---

## §1 — Overview & Purpose

> **Unique dispatch pattern — IntraActivitySequencing:** Unlike most OMXFM rules that use `Event.Ext.sendEventImmediate()` to fan out all requests simultaneously, SBM_BUY_DATA_PACK uses `IntraActivitySequencing.ActionRequestEvent()` to queue events for throttled, sequential dispatch — `SendFirstRequestEvent()` fires only the first queued event. Subsequent events are released as each response arrives via `ActionResponseEvent()`. This serializes SBM calls to avoid flooding the SBM backend.

This FM invokes the SBM `doServiceArrayRequest` API to purchase a data pack for each qualifying subscriber offer. The payload is a composite: an optional `CheckPackAllowRequest` (validates pack eligibility) followed by a required `DoServiceRequest` (triggers the purchase). The response parses a HTML-entity-encoded `extra_xml` field and dynamically injects `pack_cancel`, `pack_expire`, and `BL_CREATE_CHARGE` sub-offers into working memory.

| Item | Value |
|------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_SBM_BUY_DATA_PACK` |
| Author | Puttaporn-PC |
| JMS Event Dispatched | `Events.OMConsumers.OMXFM.Request.SBM_DO_SERVICE` |
| Payload Schema | `ns1:doServiceArrayRequest` (SBMDoserviceArrayRequest) |
| Response Concept | `Concepts.FM.Response.SBM_DoServiceRes` (not standard ResponseBase) |
| Target System | SBM (doService API) |
| Dispatch Mode | IntraActivitySequencing (throttled, sequential) |
| Fan-out scope | POU and COU Subscriber SubscriberOffers only |
| RefId (POU) | `pOuRefId + ":" + ":" + sub.RefId + ":" + offer.Soc` (double colon) |
| RefId (COU) | `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.Soc` |
| Credential source | BATCH: `SBM_DO_SERVICE/BATCH/app_user`; ONLINE: `.../ONLINE/app_user` |

---

## §2 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Current process step match |
| 2 | `orderCurrentActivity.ActivityID == "SBM_BUY_DATA_PACK"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SBM_BUY_DATA_PACK"` | Process flow confirmation |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fire once |

---

## §3 — Initialization & Pre-Processing

### §3.1 Resubmit Detection

```text
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted)
if (isActResub):
    IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
    // Clears previously queued but unresolved requests before re-queuing
```

### §3.2 IntegrationMethod → Credential Selection

| IntegrationMethod | Credential Source |
|-------------------|------------------|
| `== "BATCH"` | `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/BATCH/app_user + app_password` |
| Else (ONLINE) | `$globalVariables/OMX_OM/Services/SBM_DO_SERVICE/ONLINE/app_user + app_password` |

> **Credentials in JMS payload** — app_user and app_password are embedded in the SBM_DO_SERVICE event. Secure channel must be enforced.

### §3.3 checkPackAllowFlg

Read from `orderRequest.OrderData.ExtendedInfo[Name="CHECK_PACK_ALLOW_FLG"]/Value`. Default `"Y"` if null or empty. When "Y", the `CheckPackAllowRequest` block is included. When "N", it is omitted.

---

## §4 — Fan-Out Logic (IntraActivitySequencing)

```text
for POU[i] → Subscriber[j] → SubscriberOffers[k]:
    offerRefId = pOuRefId + ":" + ":" + sub.RefId + ":" + offer.Soc   ← NOTE: double colon
    reqSuccess = check Response[].ReferenceId==offerRefId AND CompletionStatus==2
    if !reqSuccess:
        chkRes = evaluate PreExecCheck XPath (if set)
        if chkRes=="true":
            channel = GetSBMServiceChannel(orderRequest, offer)
            billCycleNo = ConvertBillCycleDate(BillCycleNo)
            event = createEvent(SBM_DO_SERVICE, XSLT...)
            Event.assertEvent(event)
            IntraActivitySequencing.ActionRequestEvent(event, orderCurrentActivity)
            isSkipped = false
            [audit LOG]

for POU[i] → ChildOU[x] → Subscriber[y] → SubscriberOffers[z]:
    offerRefId = pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.Soc
    [same logic]

if !isSkipped:
    IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
    orderCurrentActivity.Status = GetActivityStatusString("1", false)
    SendDataToDB(orderRequest)
else:
    SkipActivity(orderRequest, orderCurrentActivity, "4")
```

> **IntraActivitySequencing key difference:** Standard OMXFM uses `Event.Ext.sendEventImmediate() + RequestCount++` (all parallel). SBM_BUY_DATA_PACK uses `Event.assertEvent() + ActionRequestEvent()` — events are queued; only the FIRST fires via `SendFirstRequestEvent()`; each response triggers the next via `ActionResponseEvent()`. RequestCount is managed internally.

> **POU RefId double colon:** POU produces `"POU123::SUB456:SOC789"` (blank cOuRefId). COU produces `"POU123:COU456:SUB789:SOC012"`. Response splits on ":" → positions [0]=POU, [1]=COU (blank), [2]=Sub, [3]=SOC.

---

## §5 — Payload (doServiceArrayRequest)

### §5.1 CheckPackAllowRequest

Emitted only when `checkPackAllowFlg='Y'` OR `isActResub="true"`.

| Field | Value |
|-------|-------|
| `ns:function_id` | `"100200024"` (static) |
| `ns:app_user` / `ns:app_password` | From globalVariables (BATCH or ONLINE) |
| `ns:channel` | From `GetSBMServiceChannel()` |
| `ns:service_no` | `$msisdn` |
| `package_code` | `$offer/OfferName` |
| `get_error_flag` | `"Y"` (static) |
| `country1` | `ExtendedInfo[DESTINATION_COUNTRY]/Value` (conditional) |
| `effective_date` | `EffectiveDate` formatted `dd/MM/yyyy HH:mm:ss +07:00` (if DESTINATION_COUNTRY AND EffectiveDate) |

### §5.2 DoServiceRequest

| Field | Value |
|-------|-------|
| `ns:function_id` | `"100200012"` (static) |
| `ccr_login` | `concat(saleId, ";", DealerCode)` |
| `add_package_code` | `$offer/OfferName` |
| `billcycle` | `$billCycleNo` |
| `billcycledate` | `$billCycleNo` (same as billcycle) |
| `imsi` | `$sub/ResourceInfo[ResourceName="IMSI"]/ValuesArray` |
| `add_start_date` | EffectiveDate (+07:00) OR `current-dateTime()` if absent |
| `omx_tracking_id` | `$orderRequest/OrderData/OMXTrackingId` |
| `country` | `ExtendedInfo[DESTINATION_COUNTRY]/Value` (conditional) |
| `price_in_vat` / `price_ex_vat` | From ExtendedInfo (if OrderType=3 or 11018, lower-cased) |
| `channel_tx_id` | `$orderRequest/OrderData/OrderID` (if OrderType=3 or 11018) |
| `parent_trx_id` | `ExtendedInfo[PARENT_TRX_ID]/Value` (if OrderType=3 or 4 AND present) |
| `ns:service_no` | `$msisdn` |

> **POU vs COU XSLT field order:** POU emits `ccr_login` before `add_package_code`. COU reverses this order. Functionally equivalent if SBM is key-based.

---

## §19 — Response Message Rulefunction

### §19.1 Overview

Significantly more complex than a standard fan-in handler. Parses HTML-entity-encoded `extra_xml`, populates offer `DataInfo`, injects `pack_cancel` / `pack_expire` sub-offers, and optionally creates `BL_CREATE_CHARGE` sub-offers (ServiceType="79") for downstream billing.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order state |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SBM_DO_SERVICE` | SBM response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in sequencing |

### §19.3 SBM_DoServiceRes Concept Fields

```text
createObject (SBM_DoServiceRes)
├── @extId              ← OMXUtils:generateTrackingID()          [Always]
├── ResponseCode        ← $eventResponse/ResponseCode            [Conditional]
├── ResponseMessage     ← $eventResponse/ResponseMsg             [Conditional]
├── CompletionStatus    ← $eventResponse/CompletionStatus        [Conditional]
├── ReferenceId         ← $eventResponse/RefID                   [Conditional]
├── DoServiceResponse[] (CheckPackAllow) ← CheckPackAllowReturn:
│   extra_xml, req_transaction_id, response_message, result_code, result_desc, result_namespace, transaction_id
└── DoServiceResponse[] (DoService) ← DoServiceReturn: same 7 fields
```

### §19.4 extra_xml Parsing

> Parsed via `String.replaceAll("&lt;","<")` entity decode then `substringBefore(substringAfter(...))` for each tag — fragile string parsing, not XML parsing.

| Field | XML Tag | Used For |
|-------|---------|----------|
| chargeAmt | `<charge_amount>` | DataInfo.ChargeAmount; BL sub-offer AMOUNT |
| featureCode | `<feature_code>` | DataInfo.FeatureCode; BL sub-offer OfferName |
| packageCode | `<package>` | DataInfo.Package |
| effDate | `<effdate>` | DataInfo.EffDate |
| expDate | `<expdate>` | DataInfo.ExpDate; ExpirationDate (Wattanachai) |
| speed | `<speed>` | DataInfo.Speed |
| chargeType | `<charge_type>` | DataInfo create only (commented out on update) |
| packType / packCode | `<pack_type>` / `<pack_code>` | DataInfo.PackType / DataInfo.PackCode |
| pack_cancel | `<pack_cancel>` | → inject immediate-cancel sub-offer(s) |
| pack_expire | `<pack_expire>` | → inject future-expiry sub-offer |
| dmc_transaction_id | `<dmc_transaction_id>` | DMC_TRX_ID ExtendedInfo |
| transaction_id | `<transaction_id>` | SBM_TRX_ID ExtendedInfo (OMX-2970, FE only) |

### §19.5 pack_cancel → Immediate Cancel Injection

If `pack_cancel` non-blank (comma-separated): create `SubscriberOffers` per code: OfferName=code, ServiceType="86", Action="REMOVE", ExtendedInfo: FE_OR_CCBS="SBM", EXP_TYPE="IM". Append to `subscriber.SubscriberOffers[]`. `areadyAddPackCancel=true` prevents re-injection.

### §19.6 pack_expire → Future Expiry Injection

If `pack_expire` non-blank: compute `nextBillDate = GetNextBillDate(logicalDate, BillCycleNo)`. Create `SubscriberOffers`: ExpirationDate=nextBillDate, OfferName=pack_expire, ServiceType="86", Action="REMOVE". ExtendedInfo: FE_OR_CCBS="SBM", EXP_TYPE="FUT", EXP_DATE_VALUE=nextBillDate.

### §19.7 BL_CREATE_CHARGE Injection

If `featureCode` non-blank: create `SubscriberOffers`: OfferName=featureCode, ServiceType="79", Soc="-1". ExtendedInfo: AMOUNT=chargeAmt, FE_OR_CCBS=source. Append to subscriber.

### §19.8 expDate / omxFut Handling (Wattanachai / OMX-1720)

| Case | Condition | Action |
|------|-----------|--------|
| IM + standard | expDate non-blank AND `omxFut==false` | Re-classify EXP_TYPE; SBM_NO_PROVISIONING="Y"; EXP_DATE_VALUE; DMC_TRX_ID; `offer.ExpirationDate = expDateCal` |
| FUT + omxFut | expDate non-blank AND `omxFut==true` | If ServiceType 86/87 AND SBM expDate ≤ expFromFe: SBM_NO_PROVISIONING="Y"; DMC_TRX_ID; no ExpirationDate mutation |

`omxFut = exists($offer/ExtendedInfo[Name='EXP_TYPE' and Value='FUT'])` — set by OMX_CAL_OFFER_FUT_DATE (step 29).

### §19.9 Fan-In

`IntraActivitySequencing.ActionResponseEvent(currActivity)` → "true" (all done) or "false" (still waiting). Also triggers dispatch of next queued request event.

---

## §15 — Function Dependency Tree

```text
Request_SBM_BUY_DATA_PACK (BE rule)
├── [if isActResub] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()
├── XPath.evalAsBoolean(IntegrationMethod="BATCH")
├── XPath.evalAsString(CHECK_PACK_ALLOW_FLG)
├── XPath.evalAsString(SBM_DO_SERVICE/BATCH or ONLINE credentials)
├── [Loop POU → Subscriber → SubscriberOffers]
│   ├── reqSuccess check
│   ├── [PreExecCheck] GetXMLForSubscriberOfferFilterWithExtendedInfo() → XPath.execute()
│   ├── GetSBMServiceChannel(orderRequest, offer)
│   ├── ConvertBillCycleDate(BillCycleNo)
│   ├── Event.createEvent(SBM_DO_SERVICE, POU XSLT)
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   └── Event.Ext.sendEventImmediate(audit Logger)
├── [Loop POU → COU → Subscriber → SubscriberOffers] [same, COU XSLT]
├── [if !isSkipped] IntraActivitySequencing.SendFirstRequestEvent()
│   GetActivityStatusString("1", false); SendDataToDB()
├── [if isSkipped] SkipActivity("4")
└── HandleActivityException(...)

Response_SBM_BUY_DATA_PACK (rulefunction)
├── Instance.createInstance(SBM_DoServiceRes XSLT)
├── String.split(RefID, ":") → [pOuRefID, cOuRefID, subRefID, soc]
├── [Find matching POU/COU subscriber + offer]
│   ├── entity-decode extra_xml → substring extraction (×13 fields)
│   ├── [OMX-2970] SBM_TRX_ID ExtendedInfo if transaction_id + source=="FE"
│   ├── [pack_cancel] tokenize + inject SubscriberOffers (EXP_TYPE="IM", REMOVE)
│   ├── [pack_expire] GetNextBillDate() + inject SubscriberOffers (EXP_TYPE="FUT", REMOVE)
│   ├── offer.DataInfo create or update
│   ├── [if expDate + !omxFut] re-classify EXP_TYPE; SBM_NO_PROVISIONING; EXP_DATE_VALUE; DMC_TRX_ID; offer.ExpirationDate
│   ├── [if expDate + omxFut] SBM_NO_PROVISIONING if expDate ≤ expFromFe; DMC_TRX_ID
│   └── [if featureCode] inject BL sub-offer (ServiceType="79", AMOUNT, FE_OR_CCBS)
├── Event.Ext.sendEventImmediate(audit Logger)
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Throttled sequential dispatch via IntraActivitySequencing; not parallel fan-out
- **R2** — On resubmit: purge pending requests before re-queuing
- **R3** — Credentials vary by IntegrationMethod: BATCH vs ONLINE endpoints
- **R4** — checkPackAllowFlg: "Y" (default) → include CheckPackAllowRequest; "N" → omit; isActResub → always include
- **R5** — RefId: POU double colon `pOu::sub:soc`; COU full 4-segment `pOu:cOu:sub:soc`
- **R6** — Response parses HTML-entity-encoded extra_xml via string manipulation
- **R7** — pack_cancel → inject IM-cancel sub-offers (ServiceType="86", Action="REMOVE", EXP_TYPE="IM")
- **R8** — pack_expire → inject FUT-expiry sub-offer (next bill date as ExpirationDate)
- **R9** — BL_CREATE_CHARGE injection if featureCode from SBM → ServiceType="79" sub-offer with AMOUNT ExtendedInfo
- **R10** — expDate handling depends on omxFut (EXP_TYPE from OMX_CAL_OFFER_FUT_DATE): IM path sets offer.ExpirationDate; FUT path only adds SBM_NO_PROVISIONING
- **R11** — OMX-2970: SBM_TRX_ID ExtendedInfo when transaction_id present AND source=="FE"
- **R12** — Fan-in: ActionResponseEvent() returns "true" when all queued requests complete; also triggers next queued dispatch

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| extra_xml parsed via string manipulation — breaks if XML format changes | [HIGH] | Replace with proper XML parser in migration |
| Credentials in JMS event payload | [HIGH] | Migrate to secrets manager |
| POU and COU XSLT have different parameter ordering — strict parsers may behave differently | [MEDIUM] | Normalize to single XSLT template |
| billcycle and billcycledate set to same value — may be intentional or copy-paste error | [MEDIUM] | Confirm with SBM documentation |
| areadyAddPackCancel/Expire typo — minor readability | [LOW] | Rename to alreadyAdd* |
| ChargeType commented out in DataInfo update path — inconsistent with create path | [LOW] | Restore or document intentional exclusion |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
