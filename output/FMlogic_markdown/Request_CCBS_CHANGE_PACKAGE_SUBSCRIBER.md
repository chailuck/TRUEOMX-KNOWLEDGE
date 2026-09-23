# Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER

> CCBS subscriber offer management — orchestrates ADD, REMOVE, CHG_PARAM and CHG_CHARGE operations on POU/COU subscribers with pooling resolution, IOT/MSIM resource binding, and old-priceplan swap logic

**Author:** Sakrapee-SCM-PC | **Namespace:** Rules.OMConsumers.OMXFM.Request | **Priority:** 5 | **ForwardChain:** true | **Target:** CCBS (Amdocs CSM3G) | **Lines:** 655

---

## §1 Overview & Purpose

`CCBS_CHANGE_PACKAGE_SUBSCRIBER` is the subscriber offer mutation step — it sends `UpdateSubscriber` requests to the Amdocs CCBS system. The FM is reusable across many order types: new subscriber provisioning, offer add/remove, parameter changes, and charge-distribution changes all flow through this same rule. Which operations are dispatched depends on the `Action` field on each SubscriberOffer.

> **Actual JMS event dispatched:** `Events.OMConsumers.OMXFM.Request.CCBS_UPDATE_SUBSCRIBER` — not `CCBS_CHANGE_PACKAGE_SUBSCRIBER`. The FM name is a logical label; the underlying ESB operation is `UpdateSubscriber`.

**Four action types** routed into separate dispatch queues per subscriber:

| Action | Queue | Dispatch variant |
|--------|-------|-----------------|
| ADD | addSubOffers | ChangeSubscriberOffersWithRelatedOffersInputInfo (Variant ①) |
| REMOVE | removeSubOffers | ChangeSubscriberOffersWithRelatedOffersInputInfo (Variant ①) |
| CHG_CHARGE | changeChargeSubOffers | ChangeSubscriberDistributionInputInfo (Variant ②) |
| CHG_PARAM | changeParameterOffers | UpdateParameterInputInfo (Variant ③) |

> **Pre-dispatch pooling resolution:** Before building the dispatch queues, the rule resolves `POOLED_OFFER_INSTANCE_ID` ExtendedInfo for pooling (PLG) SOCs by joining Subscriber `POOLED_SOC_FOR_*` ExtendedInfo with Agreement `POOLED_OFFER_INSTANCE_ID_*` ExtendedInfo. This write-back to working memory happens before the offer categorization loop.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name (full) | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER` |
| File | `Rules/OMConsumers/OMXFM/Request/Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER.rule` |
| Priority | 5 |
| ForwardChain | true |
| Author | Sakrapee-SCM-PC |
| Lines | 655 |
| Response handler | `RuleFunctions.OrderResponse.Response_CCBS_CHANGE_PACKAGE_SUBSCRIBER` |
| Response event type | `Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_SUBSCRIBER` |
| Target system | Amdocs CCBS CSM3G (via OMX_FM ESB adapter) |
| Dispatch pattern | IntraActivitySequencing — throttled sequential fan-out per subscriber |

---

## §3 Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order graph — provides Customer hierarchy, ExtendedInfo, OrderData |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step — RequestCount, Response[], PreExecCheck, Status |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Binds activity to order's active step |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_CHANGE_PACKAGE_SUBSCRIBER"` | Guards this rule to its step |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_CHANGE_PACKAGE_SUBSCRIBER"` | Double-check process pointer |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Fires only when activity is in WAITING state |

---

## §5 Execution Flow

```
1. Setup: LogicalDate (with DateTime.now() fallback), pooling globals (PoolingIndicator="PLG",
   PooledPrefix="POOLED_OFFER_INSTANCE_ID"), activity params (ACTIVITY_REASON, param,
   REMOVE_IMMEDIATE, ALT_CES), compute forceChange from ServiceChangeOnPSUSAllowed global
2. Resubmit guard: if RequestCount > 0 AND IsOrderResubmitted → PurgePendingRequestsBeforeResubmit
3. POU Phase 1 — Pooling resolution:
   a. Build pld_socs_insId_inParent from Agreement.ExtendedInfo[starts-with(Name, sPrefix)]
   b. Build plg_pld_socs from Subscriber.ExtendedInfo[starts-with(Name, "POOLED_SOC_FOR")]
   c. Write POOLED_OFFER_INSTANCE_ID back to PLG SubscriberOffers
4. COU Phase 1 — same pooling resolution; also checks pld_socs_insId_inChild first
5. POU Phase 2 — Offer categorization (per subscriber):
   a. Override subOff.Action from param if set (ADD/REMOVE/CHG_PARAM)
   b. Check reqSuccess (Response[].ReferenceId==sub.RefId AND CompletionStatus==2)
   c. Gate on chkSocLevelSub AND PreExecCheck
   d. Route by Action → addSubOffers / removeSubOffers / changeParameterOffers / changeChargeSubOffers
   e. Capture subPriceplan for ServiceType=80 CCBS offers
6. POU Phase 2 cont. — ExpirationDateNull tagging for each ADD offer:
   - "Yes" if OrderType ∈ {128,121,3,37,44009,44008,44006,44001,11018} AND FUT ExpirationDate
   - "No" otherwise
   - XSLT only emits expirationDate when ExpirationDateNull="No"
7. POU Dispatch ① — ADD+REMOVE: build CCBS_UPDATE_SUBSCRIBER via ChangeSubscriberOffersWithRelatedOffersInputInfo
   Includes: SOC_SEQ_NO request, resource bindings, charge/event distribution, ResourceRangeInfo
   Audit via sendEventImmediate
8. POU Dispatch ② — CHG_CHARGE: build via ChangeSubscriberDistributionInputInfo
   Includes: ChargeDistributionDetailsInfo, default pay channels, logicalDate
   Audit via Event.sendEvent (NOT sendEventImmediate — inconsistency)
9. POU Dispatch ③ — CHG_PARAM (per offer): build via UpdateParameterInputInfo
   Look up offerInstanceId from subscriber.SubscriberOffers; one event per offer with ParameterInfo
   Audit via sendEventImmediate
10. COU loop — mirrors steps 5–9; IoT AfterSale REMOVE conversion is POU-only
11. Fan-out fire: if !isSkipped → SendFirstRequestEvent + Status=1 + SendDataToDB; else SkipActivity("4")
```

---

## §6 Key Logic Details

### SocLevelSub Gate

```xpath
contains($subOff/SocProperties,'level=Subscriber') or
count($subOff/SocProperties)=0 or
contains($subOff/SocProperties,'TR_OFFER_EXCL_GROUP_NAME=')
```

Only offers with subscriber-level SocProperties (or no SocProperties, or with TR_OFFER_EXCL_GROUP_NAME) are categorized. Agreement-level offers are silently skipped.

### ALT_CES Override

```text
altParam = GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")
if altParam="Y" AND ExtendedInfo[ALT_CES]/Value != "" → use ALT_CES value as CES
otherwise → use $orderRequest/OrderData/CES
```

### FCR SOC Filtering in offersToAdd

```text
if (OfferName != FCRSoc) OR (OfferName = FCRSoc AND FE_OR_CCBS = "FE")
  → include in srvAgrInfo
```

### IoT AfterSale REMOVE Conversion (POU only)

For REMOVE on OrderType "11025" when `MaterialInfo/Material[no FE_OR_CCBS] count < RelatedOffersArray[CLOID] count`:
iterates RelatedOffersArray entries where TR_SPECIAL_OFFER_IND=CLOID or RSCTV AND MatSerial matches subscriber MaterialInfo → converts each to a SubscriberOffer concept added to removeSubOffers.

### Old Priceplan Swap

```text
When adding new ServiceType=80 offers AND OldPriceplan exists:
  OldPriceplan = subscriber/SubscriberOffers[ServiceType='80' AND FE_OR_CCBS='CCBS']
  Added to offersToRemove with expirationDate = new priceplan's EffectiveDate
  (NOT included when OrderType = '11002')
```

### SOC Sequence Request

```text
ns1:GetSequenceValueRequest:
  sequenceName = "SOC_SEQ_NO"
  incrementByCount = count(addSubOffersArray) + count(addSubOffersArray/RelatedOffersArray)
```

### ActivityReason Resolution Priority

| Priority | Source | Value |
|----------|--------|-------|
| 1 (highest) | Activity parameter | `actReasonParam` from ACTIVITY_REASON key |
| 2 | Subscriber CAN flag | `"CREQ"` when SubscriberActivityInfo/ActivityReason == "CAN" |
| 3 | Subscriber | `SubscriberActivityInfo/ActivityReason` if non-blank |
| 4 (default) | Hardcoded | `"CREQ"` |

### forceChange userText Injection

```text
if forceChange → userText = concat(UserText, ";isServiceChangeOnPSUSAllowed=true;")
else if removeSubOffers contains FE_OR_CCBS="ATS_REMOVE" → userText = "isServiceChangeOnPSUSAllowed=true;"
else → userText = subscriber.SubscriberActivityInfo.UserText
```

> **Audit method inconsistency:** ADD+REMOVE uses `Event.Ext.sendEventImmediate` for POU but CHG_CHARGE uses `Event.sendEvent`. CHG_PARAM uses `sendEventImmediate` in both POU and COU. This is a design defect — some audit logs may be deferred or lost.

---

## §7 Data Extraction — Pooling Resolution

```
Step 1 — Build Agreement → Pooled SOC → InstanceId map
  Iterate Agreement.ExtendedInfo[starts-with(Name, sPrefix)] where sPrefix="POOLED_OFFER_INSTANCE_ID"
  Key = substringAfter(Name, sPrefix+"_") + "_" + i
  Value = ExtendedInfo.Value (the pooled offer instance ID)
  Result: pld_socs_insId_inParent / pld_socs_insId_inChild

Step 2 — Build Subscriber PLG SOC → Pooled SOC map
  Iterate Subscriber.ExtendedInfo[starts-with(Name, "POOLED_SOC_FOR")]
  Key = substringAfter(Name, "POOLED_SOC_FOR_") + "_j" (pooling SOC)
  Value = ExtendedInfo.Value + "_i" (pooled SOC)
  Result: plg_pld_socs

Step 3 — Write POOLED_OFFER_INSTANCE_ID back to SubscriberOffer
  For each PLG offer (BRMS.AnyIn check):
    find pooled SOC in plg_pld_socs by offer.Soc or offer.OfferName
    → get instance ID from pld_socs_insId map
    → write/update POOLED_OFFER_INSTANCE_ID ExtendedInfo on the SubscriberOffer
  This is then passed to CCBS as ns:ParameterInfo[name="Agreement level offer instance ID"]
```

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

| OrderType | Condition | Effect |
|-----------|-----------|--------|
| 11001, 11002 | In offersToAdd XSLT | dealerCode from `subscriber.SubscriberGeneralInfo.saleId` instead of DealerCode |
| 11025 | REMOVE with IoT device mismatch | Converts RelatedOffersArray items (CLOID/RSCTV) to individual SubscriberOffer removals |
| 11002 | In old priceplan REMOVE | RelatedOffersArray of old priceplan NOT included in offersToRemove |
| 128,121,3,37,44009,44008,44006,44001,11018 | FUT ExpirationDate check | ExpirationDateNull="Yes" → ExpirationDate not sent to CCBS |
| Any in ServiceChangeOnPSUSAllowed GV | forceChange=true | userText includes `;isServiceChangeOnPSUSAllowed=true;` |

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Dispatch | Purpose |
|-----------|-----------|---------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_UPDATE_SUBSCRIBER` | IntraActivitySequencing (throttled) | UpdateSubscriber to Amdocs CCBS |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | sendEventImmediate (POU ADD/CHG_PARAM) / sendEvent (COU CHG_CHARGE) | Request audit trail |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_SUBSCRIBER` | JMS push | UpdateSubscriber result with ClosedAndReopenedOffers / OfferInstanceIds |

### §8.3 Backend API Details

| System | Operations | Schema namespace | Correlation |
|--------|-----------|-----------------|-------------|
| Amdocs CCBS CSM3G | ChangeSubscriberOffersWithRelatedOffersInputInfo, ChangeSubscriberDistributionInputInfo, UpdateParameterInputInfo | `http://services.omx.truecorp.co.th/FMServices/updateSubscriberRequest` | RefID = `subscriber.RefId` |

### §8.4 BE Working Memory — Reads

| Field | Source | Used for |
|-------|--------|---------|
| `subOff.Action` | Set by FE or overridden by param | Routes to ADD/REMOVE/CHG_PARAM/CHG_CHARGE list |
| `subOff.SocProperties` | CCBS SOC metadata | chkSocLevelSub gate; FCR filter; MSIM detection |
| `subOff.RelatedOffersArray[]` | Bundle sub-offers | relatedOffers in XSLT; IoT REMOVE conversion; Cloud ID/CCTV resource binding |
| `subOff.ParameterInfo[]` | Offer-specific parameters | CHG_PARAM UpdateParameterInputInfo; also in ADD srvAgrInfo |
| `subOff.ExtendedInfo[FE_OR_CCBS]` | Channel marker | Filter context; FCR SOC gate; old priceplan detection |
| `sub.ResourceInfo[]` | Subscriber resources | PEID/PMATCHID/EID/MIIMSI/MIIMEI/MISIM bindings |
| `sub.SubscriberActivityInfo` | Activity context | ActivityReason, UserText for ActivityInfo |
| `sub.PayChannelIdPrimary/Secondary` | Payment channels | CHG_SPLIT_TYPE and SPLITS01 charge distribution |
| `sub.EventGroupItem` | Event pooling config | EventDistributionDetailsInfo for EGI SOCs |
| `Agreement.ExtendedInfo[POOLED_OFFER_INSTANCE_ID_*]` | Agreement pooling data | Pooling resolution pre-pass |

### §8.4b BE Working Memory — Writes

| Field | Written value | When |
|-------|--------------|------|
| `subOff.ExtendedInfo[POOLED_OFFER_INSTANCE_ID]` | Resolved pooled offer instance ID | Pre-pass: PLG offers with matching Agreement ExtendedInfo |
| `subOff.ExtendedInfo[ExpirationDateNull]` | "Yes" or "No" | ADD offers before dispatch — controls whether ExpirationDate is forwarded to CCBS |
| `subOff.Action` | From param override (ADD/REMOVE/CHG_PARAM) | If activity param[1] is not ACTIVITY_REASON and is a valid action code |

### §8.5 ExtendedInfo Fields Read

| Key | Scope | Used for |
|-----|-------|---------|
| FE_OR_CCBS | subOff | Filter context; FCR gate; priceplan detection; IoT REMOVE detection |
| POOLED_SOC_FOR_* | Subscriber | Pooling: maps PLG SOC → POOLED SOC |
| POOLED_OFFER_INSTANCE_ID_* | Agreement | Pooling: instance IDs to inject |
| SPECIAL_OFFER_INDICATOR | subOff | EGI SOC detection for EventDistributionDetailsInfo |
| TR_MULTISIM_IND | subOff | REE → EID/MIIMSI/MIIMEI/MISIM; RES → MIIMSI/MISIM binding |
| LOGICAL_RESOURCE | subOff | Additional LogicalResourceInfo entries (tokenize by ",") |
| IMEI_KNOX | subOff | PhysicalResourceInfo for KNOX binding (value ≠ "NONE") |
| CHG_SPLIT_TYPE | subOff | "DR" → PayChannelIdPrimary, "RS" → PayChannelIdSecondary charge split |
| ALT_CES | orderRequest.OrderData | CES override when altParam="Y" |

### §8.6 Global Variable Dependencies

| Path | Default | Used for |
|------|---------|---------|
| `OMX-OM/PoolingPooled/PoolingIndicator` | "PLG" | Identifies PLG SOCs for pooled offer resolution |
| `OMX-OM/PoolingPooled/PooledPrefix` | "POOLED_OFFER_INSTANCE_ID" | Agreement ExtendedInfo key prefix for pooled instance IDs |
| `OMX_OM/OrderTypes/ServiceChangeOnPSUSAllowed` | ",32," | Comma-delimited OrderTypes that force PSUS change |
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | varies | Gates UserName/PassWord inclusion in event header |
| `OMX_OM/Services/CJ/FCRSoc` | varies | FCR SOC name excluded from offersToAdd unless FE channel |
| `OMX_COMMON/Component_Name/OMX_CEP` | — | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | — | TARGET_SYSTEM in audit log |
| `OMX_OM/WritePayload` | — | Gates payload inclusion in audit |

---

## §9 Detailed Payload Build — Three XSLT Dispatch Variants

> All three variants send a `CCBS_UPDATE_SUBSCRIBER` event wrapping an `ns:UpdateSubscriberRequest` payload. They differ in the inner operation element.

### Variant ① — ADD/REMOVE: ChangeSubscriberOffersWithRelatedOffersInputInfo

Used when `addSubOffersArray.length > 0 OR removeSubOffersArray.length > 0`. Most complex variant.

```text
ns:UpdateSubscriberRequest
├── ns1:GetSequenceValueRequest  [if addSubOffersArray non-empty]
│   ├── ns1:sequenceName         ← "SOC_SEQ_NO"
│   └── ns1:incrementByCount     ← count(addSubOffers) + count(addSubOffers/RelatedOffersArray)
└── ns:UpdateSubscriberRequest
    ├── ns:SubscriberIdInfo/ns:subscrNumber  ← $subscriber/SubscriberId
    └── ns:ChangeSubscriberOffersWithRelatedOffersInputInfo
        ├── ns:offersToAdd                   [for each addSubOffer, excl FCRSoc unless FE channel]
        │   └── ns:srvAgrInfo
        │       ├── ns:dealerCode            ← saleId (OrderType 11001/11002) or DealerCode
        │       ├── ns:deployMode            ← DeployMode  [if present]
        │       ├── ns:effectiveDate         ← EffectiveDate  [if present]
        │       ├── ns:expirationDate        ← ExpirationDate  [only when ExpirationDateNull="No"]
        │       ├── ns:name                  ← OfferName
        │       ├── ns:parentOfferInstanceId ← ParentOfferInstanceId  [if > 0]
        │       ├── ns:refId                 ← @Id (offer BE @Id)  [if present]
        │       ├── ns:relatedOffers         [for each RelatedOffersArray]
        │       ├── ns:serviceType           ← ServiceType
        │       └── ns:soc                   ← Soc
        ├── ns:offersToRemove               [for each removeSubOffer (ServiceType≠80)]
        │   └── (+ old priceplan if new ServiceType=80 add, excl OrderType=11002)
        ├── ns:LogicalResourceInfo          [PEID, PMATCHID, EID/MIIMSI (MSIM REE), MIIMSI (RES),
        │                                    LOGICAL_RESOURCE, Cloud ID (CLOID), CCTV (RSCTV)]
        ├── ns:PhysicalResourceInfo         [MIIMEI/MISIM (MSIM REE), MISIM (RES), KNOX (IMEI_KNOX)]
        ├── ns:ParameterInfo                [addSubOffer/ParameterInfo + RelatedOffersArray/ParameterInfo]
        ├── ns:ParameterInfo[Agreement level offer instance ID]
        │                                   [if PLG offer, value = POOLED_OFFER_INSTANCE_ID]
        ├── ns:ChargeDistributionDetailsInfo [RCIndicator=65, CHG_SPLIT_TYPE=DR/RS, OfferName=SPLITS01]
        ├── ns:EventDistributionDetailsInfo  [SPECIAL_OFFER_INDICATOR=EGI SOCs]
        ├── ns:ResourceInfo                 [ResourceRangeInfo[Action=PP] when adding ServiceType=80]
        └── ns:ActivityInfo                 ← activityReason (priority: actReasonParam/CREQ/SubscriberActivityInfo)
                                              userText (forceChange/ATS_REMOVE logic)
```

### Variant ② — CHG_CHARGE: ChangeSubscriberDistributionInputInfo

> Sends charge-distribution changes. All three pay channel IDs (OC, RC, primary event) are set from Account[1].AccountID. logicalDate forwarded in enclosedClientInfo.

```xml
<ns:ChangeSubscriberDistributionInputInfo>
  <ns:ChargeDistributionDetailsInfo>
    <ns:soc>...from CHG_CHARGE offer...</ns:soc>
    <ns:targetPayChannelId>...subscriber.PayChannelIdSecondary...</ns:targetPayChannelId>
  </ns:ChargeDistributionDetailsInfo>
  <ns:defaultOCPayChannelIdInfo><ns:payChannelId>Account[1].AccountID</ns:payChannelId></ns:defaultOCPayChannelIdInfo>
  <ns:defaultRCPayChannelIdInfo><ns:payChannelId>Account[1].AccountID</ns:payChannelId></ns:defaultRCPayChannelIdInfo>
  <ns:primaryEventPayChannelIdInfo><ns:payChannelId>Account[1].AccountID</ns:payChannelId></ns:primaryEventPayChannelIdInfo>
  <ns:ActivityInfo>
    <ns:activityReason>...</ns:activityReason>
    <ns:enclosedClientInfo><ns:logicalDate>logicalDateVal</ns:logicalDate></ns:enclosedClientInfo>
  </ns:ActivityInfo>
</ns:ChangeSubscriberDistributionInputInfo>
```

### Variant ③ — CHG_PARAM: UpdateParameterInputInfo (per offer)

> One event per CHG_PARAM offer with ParameterInfo. OfferInstanceId looked up from subscriber's existing SubscriberOffers by OfferName. Old ArrayList-based implementation is commented out.

```xml
<ns:UpdateParameterInputInfo>
  <ns:ParameterInfo>
    <ns:name>ParamName</ns:name>
    <ns:values>ValuesArray</ns:values>
    <ns:offerInstanceId>offerInstanceId (if > 0)</ns:offerInstanceId>
    <ns:effectiveDate>EffectiveDate</ns:effectiveDate>
    <ns:expirationDate>ExpirationDate</ns:expirationDate>
  </ns:ParameterInfo>
  <ns:ActivityInfo><ns:enclosedClientInfo><ns:logicalDate>logicalDateVal</ns:logicalDate></ns:enclosedClientInfo></ns:ActivityInfo>
</ns:UpdateParameterInputInfo>
```

---

## §11 Audit Logging

| Variant | AUDIT_TRACE | Dispatch method |
|---------|------------|----------------|
| ADD/REMOVE (POU) | "Request Sent for CCBS_CHANGE_PACKAGE_SUBSCRIBER for add/remove offer" | `sendEventImmediate` |
| CHG_CHARGE (POU/COU) | "Request Sent for CCBS_CHANGE_PACKAGE_SUBSCRIBER for add/remove offer" | `Event.sendEvent` (deferred!) |
| CHG_PARAM (POU/COU) | "Request Sent for CCBS_CHANGE_PACKAGE_SUBSCRIBER for change offer parameter" | `sendEventImmediate` |

> **[HIGH Risk]** CHG_CHARGE audit uses `Event.sendEvent` (not immediate) — the log entry may be delayed or lost if the engine is under load.

---

## §12 Activity Status Management

| Condition | Status Call | Result |
|-----------|------------|--------|
| At least one request dispatched | `GetActivityStatusString("1", false)` | Activity in-flight |
| No dispatchable offers/actions | `SkipActivity("4")` | Activity skipped |
| Invalid param value | `Exception.newException("DATA_ISSUE", "Param is missing.")` | Exception → HandleActivityException |

---

## §15 Function Dependency Tree

```text
Request_CCBS_CHANGE_PACKAGE_SUBSCRIBER
├── [setup]
│   ├── Log.getLogger()
│   ├── Instance.getByExtIdByUri("LogicalDate")
│   ├── GetActivityParameterValueFromKey() × 4 (ACTIVITY_REASON, param, REMOVE_IMMEDIATE, ALT_CES)
│   └── System.getGlobalVariableAsString() × 2 (PoolingIndicator, PooledPrefix)
├── [resubmit guard]
│   └── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()
├── [POU/COU Phase 1: Pooling resolution]
│   ├── BRMS.AnyIn(sPooling, propValue)
│   ├── XPath.evalAsBoolean() — POOLED_OFFER_INSTANCE_ID absent check
│   ├── Instance.createInstance() — create SubscriberOffersExtendedInfo (if absent)
│   └── Instance.getByExtId() — get existing ExtendedInfo concept (if present)
├── [POU/COU Phase 2: Categorization]
│   ├── BRMS.IsBlank(param)
│   ├── GetSplOffIndForSoc()
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo() / ...InChildOU...() — PreExecCheck
│   ├── XPath.execute() — PreExecCheck gate
│   ├── XPath.evalAsBoolean() — chkSocLevelSub
│   └── XPath.evalAsBoolean() — ISPriceplanFromCCBS; IoT afterSale; ExpirationDateNull
├── [POU/COU Dispatch 1: ADD/REMOVE]
│   ├── GetActivityEffectiveType() — FUT check for ExpirationDateNull
│   ├── Instance.createInstance() — ExpirationDateNull ExtendedInfo
│   ├── Event.createEvent() — CCBS_UPDATE_SUBSCRIBER (Variant ①)
│   ├── Event.assertEvent()
│   ├── IntraActivitySequencing.ActionRequestEvent()
│   └── Event.Ext.sendEventImmediate() / Event.sendEvent() — Logger
├── [POU/COU Dispatch 2: CHG_CHARGE]
│   ├── Event.createEvent() — CCBS_UPDATE_SUBSCRIBER (Variant ②)
│   ├── Event.assertEvent()
│   ├── IntraActivitySequencing.ActionRequestEvent()
│   └── Event.sendEvent() — Logger
├── [POU/COU Dispatch 3: CHG_PARAM per offer]
│   ├── XPath.evalAsInt() — offerInstanceId lookup
│   ├── Event.createEvent() — CCBS_UPDATE_SUBSCRIBER (Variant ③)
│   ├── Event.assertEvent()
│   ├── IntraActivitySequencing.ActionRequestEvent()
│   ├── Log.log("warn") — if no ParameterInfo on offer
│   └── Event.Ext.sendEventImmediate() — Logger
├── [after loops]
│   ├── IntraActivitySequencing.SendFirstRequestEvent()
│   ├── GetActivityStatusString("1", false)
│   └── SendDataToDB()
├── [skip path]
│   └── SkipActivity("4")
└── [catch]
    └── HandleActivityException()
```

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Resolve POOLED_OFFER_INSTANCE_ID for PLG SOCs before dispatch using Agreement/Subscriber ExtendedInfo join |
| R2 | Classify subscriber offers into ADD/REMOVE/CHG_PARAM/CHG_CHARGE queues based on subOff.Action |
| R3 | Gate classification on chkSocLevelSub (subscriber-level SocProperties only) |
| R4 | For ADD offers: tag ExpirationDateNull based on OrderType + FUT date check; suppress ExpirationDate to CCBS when "Yes" |
| R5 | Old priceplan swap: auto-remove CCBS priceplan when adding new ServiceType=80 offer (excl. OrderType 11002) |
| R6 | SOC sequence request: increment by addOffers + addOffers/RelatedOffers count |
| R7 | Resource binding: PEID, PMATCHID, EID/MIIMSI/MIIMEI/MISIM (MSIM), IMEI_KNOX, Cloud ID (CLOID), CCTV (RSCTV), LOGICAL_RESOURCE |
| R8 | Charge distribution: RCIndicator=65, CHG_SPLIT_TYPE DR/RS, SPLITS01, EventDistributionDetailsInfo (EGI) |
| R9 | IoT AfterSale (OrderType 11025): convert CLOID/RSCTV RelatedOffersArray items to individual removes when device count mismatch |
| R10 | CHG_PARAM: look up OfferInstanceId from subscriber's existing SubscriberOffers; one event per CHG_PARAM offer |
| R11 | Forward LogicalDate to CHG_CHARGE and CHG_PARAM variants in enclosedClientInfo |
| R12 | FCR SOC excluded from offersToAdd unless FE_OR_CCBS="FE" |
| R13 | ALT_CES override: use ExtendedInfo[ALT_CES]/Value as CES when altParam="Y" |
| R14 | forceChange: inject `;isServiceChangeOnPSUSAllowed=true;` in userText when OrderType in ServiceChangeOnPSUSAllowed |
| R15 | Response: map ClosedAndReopenedOffers[NewOfferInstanceId] back to subscriber.SubscriberOffers.OfferInstanceId and RelatedOffersArray.OfferInstanceId |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| CHG_CHARGE audit uses `Event.sendEvent` (deferred) instead of `sendEventImmediate` — logs may be lost under load | [MEDIUM] | Standardize all audit dispatches to sendEventImmediate |
| Commented-out CHG_PARAM ArrayList implementation — old code still in source | [LOW] | Remove commented-out code blocks in migration |
| reqSuccess check is at subscriber granularity (sub.RefId), not offer granularity — prevents ALL offers for that subscriber from re-dispatching on retry | [HIGH] | Evaluate per-offer success tracking in migration; confirm partial retry requirements |
| ExpirationDateNull OrderType list hardcoded in BE rule | [MEDIUM] | Externalize to a global variable or configuration table |
| SocLevelSub gate silently skips agreement-level offers without warning/logging | [LOW] | Add audit log entry when offers are skipped by this gate |
| Pooling resolution writes back to working memory — side effect before dispatch; value update path may overwrite on retry | [MEDIUM] | Guard with existence check for update path (create path is already guarded) |
| IoT AfterSale REMOVE conversion is POU-only; COU does not have the same logic | [LOW] | Confirm with business: are IoT COU subscribers a possibility? |

---

## §19 Response Message Rule — Response_CCBS_CHANGE_PACKAGE_SUBSCRIBER

### §19.1 Overview

The response handler: (1) creates `CCBS_UpdateSubscriberRes` from the incoming response (with `ClosedAndReopenedOffers` → `SocInstance[]` mapping), (2) reverse-looks up the subscriber by RefID, (3) maps returned `NewOfferInstanceId` values back to `subscriber.SubscriberOffers[].OfferInstanceId` and `RelatedOffersArray[].OfferInstanceId`, then (4) drives fan-in via ActionResponseEvent.

> **Critical:** The response event type is `Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_SUBSCRIBER`, not CCBS_CHANGE_PACKAGE_SUBSCRIBER.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Needed for audit logging (OMXTrackingId) |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_SUBSCRIBER` | Inbound CCBS response — ResponseCode, RefID, ClosedAndReopenedOffers |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; drives fan-in |

### §19.3 ResponseBase Concept — CCBS_UpdateSubscriberRes

```text
createObject
└── object  extId=OMXUtils.generateTrackingID()
    ├── ResponseCode        ← $eventResponse/ResponseCode       [Conditional: if present]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg         [Conditional: if present]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus    [Conditional: if present]
    ├── ReferenceId         ← $eventResponse/RefID               [Conditional: if present]
    └── SocInstance[]       [for each ClosedAndReopenedOffers in response]
        ├── OfferInstanceId ← ns1:NewOfferInstanceId             [Conditional: if present]
        └── Soc             ← ns1:Soc                            [Conditional: if present]
```

### §19.4 OfferInstanceId Write-Back

After constructing the response concept:

```java
// Subscriber lookup by RefID (two patterns):
subscriber = Instance.getByExtIdByUri("SUB:" + OMXTrackingId + ":" + eventResponse.RefID, ...);
if(subscriber == null) subscriber = Instance.getByExtIdByUri("CSUB:" + OMXTrackingId + ":" + eventResponse.RefID, ...);
param = GetActivityParameterValueFromKey(currActivity, "REPLACE_NEW_INSTANCE_ID");

// Cross-match activityRes.SocInstance[i] vs subscriber.SubscriberOffers[j] by Soc:
if(Soc match AND (OfferInstanceId == 0 OR param == "Y")) {
    subscriber.SubscriberOffers[j].OfferInstanceId = activityRes.SocInstance[i].OfferInstanceId;
}
// Also check RelatedOffersArray (OfferInstanceId == 0 only, no REPLACE gate):
if(Soc match AND RelatedOffersArray[k].OfferInstanceId == 0) {
    subscriber.SubscriberOffers[j].RelatedOffersArray[k].OfferInstanceId = ...;
}
```

> `REPLACE_NEW_INSTANCE_ID="Y"` allows forced OfferInstanceId overwrite for resubmit scenarios. RelatedOffersArray does not respect this gate — always skips if OfferInstanceId already non-zero.

### §19.5 Completion Logic

`IntraActivitySequencing.ActionResponseEvent(currActivity)` → `"true"` when all enqueued requests have been responded to; `"false"` otherwise.

Fan-in correlation is at **subscriber granularity** (RefId), not per-offer. A single response per subscriber completes that subscriber's fan-in slot.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
