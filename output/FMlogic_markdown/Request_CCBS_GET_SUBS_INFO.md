# Request_CCBS_GET_SUBS_INFO

> CCBS Get Subscriber Info — Post-Creation Subscriber Master Data Sync and Resource Enrichment

**Priority:** 5 | **forwardChain:** true | **Backend:** CCBS | **Author:** awalia-t420 | **Response:** 698 lines | **Generated:** 2026-07-27

---

## §1 — Overview & Purpose

This rule fires after CCBS subscriber creation and sends a `GetSubscriberInfoRequest` per subscriber (ParentOU and ChildOU) to retrieve the full current subscriber state from CCBS. The response handler (**698 lines**) is the most complex in the ACTIVATION_CREATE_SUBSCRIBER flow — it performs a comprehensive **subscriber master data sync**, populating nearly every subscriber concept field needed for downstream provisioning steps.

> **Purpose:** After CCBS creates the subscriber record, this step reads back what CCBS actually provisioned — verifying the SubscriberId, synchronizing IMSI/SIM/IMEI/PEID resource assignments, enriching SubscriberGeneralInfo, and confirming OfferInstanceIds for downstream systems (AA, NAS, etc.).

**Response enriches 6 major data domains on the subscriber concept:**

1. **SubscriberGeneralInfo** — Language, MultiSimInd (89→Y), saleId, L9InstallationType, L9RelatedSubscriber
2. **ResourceInfo[]** — IMSI, SIM, IMEI, PEID, PMATCHID, logicalResource(R), CFW/CFNRY/CFNRC/CFU_NO_PARAM; plus OLD_* variants for SIM-swap orders
3. **SubscriberType / PayChannelIdPrimary** — subscriber classification and billing channel
4. **OfferInstanceId sync** — for FE (ServiceType 86/87) and CHG_PARAM offers on OrderTypes 4/5/128/126/11016
5. **CUG ID injection** — adds CUG ID ParameterInfo to qualifying offers
6. **IoT/Cloud serial mapping** — Cloud ID and CCTV Serial No written to RelatedOffersArray.MatSerialRefId and MaterialInfo

> **ALT_CES parameter:** The request rule reads `GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")`. If the activity has `ALT_CES=Y` AND the order has `ExtendedInfo[Name='ALT_CES']/Value`, the CES header uses the alternate CES node instead of the default `OrderData/CES`.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_CCBS_GET_SUBS_INFO` |
| Priority | 5 |
| forwardChain | true |
| Author | awalia-t420 |
| Backend System | CCBS — Amdocs CSM 3G Subscriber Management |
| Operation | GetSubscriberInfoRequest / GetSubscriberInfoResponse |
| Request schema namespace | `http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/SubscriberServices/Schema.xsd5` |
| Response payload namespace (xsd2) | `www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.SubscriberInfo` |
| SubscriberGeneralInfo namespace (ns/ns1) | `www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.SubscriberGeneralInfo` |
| Dispatch mechanism | IntraActivitySequencing (sequential, ParentOU + ChildOU) |
| Subscriber scope | ParentOU + ChildOU |
| ALT_CES support | Yes — alternate CES routing via activity parameter |
| Response handler size | **698 lines** — most complex response rulefunction in this flow |
| Mandatory guard | Throws `DATA_ISSUE` if `SubscriberInfo` absent in response |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_GET_SUBS_INFO"` | Targets only this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_SUBS_INFO"` | Order-level double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires on fresh activity |

---

## §5 — Execution Flow

```text
1. Init — isActResub; if resubmit → PurgePendingRequestsBeforeResubmit;
         read altParam = GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")
2. ParentOU Subscriber loop — for each ParentOU[i].Subscriber[j]:
   resubmission guard → PreExecCheck → assemble event (subId=Subscriber.SubscriberId)
   → Event.assertEvent + ActionRequestEvent + audit log
3. ChildOU Subscriber loop — same pattern using GetXMLForSubscriberInChildOU
4. After loops — SendFirstRequestEvent; Status = IN_PROGRESS; SendDataToDB
5. Skipped — SkipActivity(…, "4")
6. Exception — HandleActivityException
```

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

| Order Type(s) | Effect in Response Handler |
|--------------|---------------------------|
| All types with `ALT_CES=Y` activity parameter | CES header sourced from `OrderData/ExtendedInfo[ALT_CES]/Value` |
| In `NotKeepSubInfoResponse` list | SubscriberStatusInfo, SubscriberGeneralInfo, BasicParameters[], Services[] NOT stored |
| 3, 12002 | `saleId` NOT written to SubscriberGeneralInfo |
| 11003 | Full SubscriberGeneralInfo replacement — merge response Language and saleId |
| 20, 81, 11027, 11029 | OLD_IMSI, OLD_SIM, OLD_PEID, OLD_PMATCHID ResourceInfo created (SIM-swap orders) |
| 126 | ResourceRangeInfo[] from `BasicParameters[RangeInd=89]`; also OfferInstanceId sync |
| 4, 128, 5, 11016 | OfferInstanceId sync from CCBS Services[] for FE/CHG_PARAM offers |
| 5 | Additional OfferInstanceId fill for SubscriberOffers (OMX-1578) |
| 4 | KNOX IMEI ExtendedInfo injection (OMX-2613) |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel | Event | Purpose |
|-----------|---------|-------|---------|
| [OUTBOUND] | `/Channels/OMXFMConnectionRequest` | `Events.OMConsumers.OMXFM.Request.CCBS_GET_SUBS_INFO` | CCBS GetSubscriberInfoRequest — sequential per subscriber |
| [LOG] | `/Channels/LogConnection` | `Events.OMConsumers.OMXESB.Logger` | Request + Response audit |

### §8.3 — CES Routing Logic

```text
if (altParam = "Y") AND (OrderData/ExtendedInfo[Name="ALT_CES"]/Value != ""):
    CES ← ExtendedInfo["ALT_CES"]/Value   // use alternate CES node
else:
    CES ← orderRequest/OrderData/CES      // use default CES node
```

### §8.4 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/OrderTypes/NotKeepSubInfoResponse` | Comma-delimited list of OrderTypes that skip storing full subscriber status |
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Include credentials in request event |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_OM/WritePayload` | Include payload in audit log |

---

## §9 — Request Payload (GetSubscriberInfoRequest)

The request payload is intentionally minimal — just the subscriber number:

```text
createEvent
└── event
    ├── JMSCorrelationID   ← OrderData/OMXTrackingId     [Conditional]
    ├── OrderID            ← OrderData/OrderID             [Conditional]
    ├── RefID              ← $refId (Subscriber.RefId)     [Always]
    ├── UserName/PassWord  ← OrderData/User, Password      [Credential-gated]
    ├── OrderType          ← OrderData/OrderType           [Conditional]
    ├── CES                ← ALT_CES or OrderData/CES      [Always, see §8.3]
    └── payload
        └── ns:GetSubscriberInfoRequest
            └── ns:SubscriberIdInfo
                └── ns:subscrNumber ← $subId (Subscriber.SubscriberId)  [Always]
                                      // set by CCBS_CREATE_SUBS preceding step
```

---

## §12 — Activity Status Management

| Trigger | Code | Status |
|---------|------|--------|
| Rule fires | 0 | WAITING |
| At least one subscriber queued | 1 | IN_PROGRESS |
| No subscribers dispatched | 4 | SKIPPED |
| Exception | 3 | ERROR |
| DATA_ISSUE (no SubscriberInfo in response) | — | ERROR via thrown exception |
| All subscribers responded | 2 | COMPLETED |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_GET_SUBS_INFO (rule)
├── GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")
├── [if isActResub] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── Per ParentOU[i].Subscriber[j] loop:
│   ├── GetXMLForSubscriber(orderRequest, refId)
│   ├── XPath.execute("/(PreExecCheck)", ...)
│   ├── Event.createEvent(xslt://CCBS_GET_SUBS_INFO)   [payload: ns:subscrNumber = subId]
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   └── Event.createEvent(xslt://Logger)
├── Per ParentOU[i].ChildOU[k].Subscriber[j] loop:
│   └── [same, using GetXMLForSubscriberInChildOU]
├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
├── GetActivityStatusString("1", false)
└── SendDataToDB(orderRequest)

Response_CCBS_GET_SUBS_INFO (rulefunction)
├── Guard: not(exists(SubscriberInfo)) → throw DATA_ISSUE
├── OMXUtils.generateTrackingID()
├── Instance.createInstance(xslt://CCBSGetSubsInfoRes)
│   └── [gated by NotKeepSubInfoResponse] StatusInfo, GeneralInfo, BasicParameters[], Services[]
├── currActivity.Response[n] = activityRes
├── Instance.getByExtIdByUri("SUB:...:RefID") or "CSUB:...:RefID"
├── SubscriberGeneralInfo write-back (3 code paths)
│   ├── [null] createInstance → assign
│   ├── [exists] fill blanks: Language, MultiSimInd
│   └── [OrderType=11003] full replacement
├── subscriber.SubscriberType ← SubscriberTypeInfo/SubscriberType
├── subscriber.PayChannelIdPrimary ← SubscriberDefaultDistributionInfo[1]/PayChannelId
├── IMSI ResourceInfo: getByExtIdByUri or createInstance
├── OLD_IMSI: createInstance [OrderTypes 20/81/11027/11029]
├── SIM ResourceInfo: getByExtIdByUri or createInstance
├── OLD_SIM: createInstance [OrderTypes 20/81/11027/11029]
├── IMEI ResourceInfo: getByExtIdByUri("SUBRI:...:IMEI") or createInstance, Source='CCBS'
├── eSIM check: exists(PEID) and exists(PMATCHID)
│   ├── PEID: createInstance [eSIM and !peid]
│   ├── OLD_PEID: createInstance [eSIM + SIM-swap + !existsOldPeid]
│   ├── PMATCHID: createInstance [eSIM and !pmatchId]
│   └── OLD_PMATCHID: createInstance [eSIM + SIM-swap]
├── [OrderType=126] ResourceRangeInfo: for BasicParameters[RangeInd=89]
├── logicalResourceR: createInstance (BasicParameters[Type=PrimResourceTp AND Type!='C'])
├── CFW_NO_PARAM, CFNRY_NO_PARAM, CFNRC_NO_PARAM, CFU_NO_PARAM: createInstance
├── [OrderTypes 4/128/126/5/11016] OfferInstanceId sync:
│   ├── [ServiceType 86/87] match by OfferName → assign or DMC_REMOVE concept
│   └── [CHG_PARAM or OT=5] match → assign OfferInstanceId + ParameterInfo[].OfferInstanceId
├── [OT=5] Secondary OfferInstanceId fill (OMX-1578)
├── [OT=4] KNOX IMEI ExtendedInfo (OMX-2613)
├── [ADD_RELATED param] Merge RelatedOffers from CCBS Services[]
├── Build arrLstSOCs: "socId:socName:offerInstanceId" per Services entry
├── CUG ID: → AddCugIDParameter(offer, cugSocName, ccbsCugId)
├── [IoT] Cloud ID / CCTV Serial No → MatSerialRefId, MaterialInfo
├── subscriber.MSISDN fallback from BasicParameters[MSISDN] (if blank)
├── subscriber.Status fallback from SubscriberStatusInfo/SubStatus (if ==0)
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
```

---

## §19 — Response Message Rule (698 lines — Subscriber Master Data Sync)

### §19.1 — Overview

`RuleFunctions.OrderResponse.Response_CCBS_GET_SUBS_INFO` is the most complex response handler in the ACTIVATION_CREATE_SUBSCRIBER flow. It performs a comprehensive master data sync across 14 distinct write-back paths.

**Response extId:** `"GSIR:" + JMSCorrelationID + ":" + RefID`

**Mandatory guard:** `if not(exists($eventResponse/payload/xsd2:SubscriberInfo))` → throws `Exception.newException("DATA_ISSUE", "No subscriberInfo returned.", null)`

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Subscriber concepts written extensively |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_GET_SUBS_INFO` | CCBS GetSubscriberInfoResponse payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; IntraActivitySequencing state |

### §19.3 — CCBSGetSubsInfoRes Concept Fields

Created with extId = `"GSIR:" + JMSCorrelationID + ":" + RefID`

**Gating rule:** SubscriberStatusInfo, SubscriberGeneralInfo, BasicParameters[], and Services[] are only stored when `NOT contains(NotKeepSubInfoResponse, "," + OrderType + ",")`

| Field Group | Source in SubscriberInfo |
|-------------|--------------------------|
| ResponseCode, ResponseMessage, CompletionStatus, ReferenceId | Standard event response fields |
| SubscriberStatusInfo.SubStatus / SubStatusDate / SubStsIssueDate / SubStsLastAct / SubStsRsnCd | `ns:SubscriberStatusInfo/ns:*` |
| SubscriberGeneralInfo.L9InstallationType / L9RelatedSubscriber / L9SaleId | `ns:SubscriberGeneralInfo/ns1:*` |
| BasicParameters[] (all fields: Category, DisplayInd, EffectiveDate, ExpirationDate, IsChangeable, MandatoryInd, Name, OfferInstanceId, ParamInstanceLevel, ParameterInstanceId, ParameterInstanceIdLong, Properties, Services[], Type, Values[], rangeInd) | `ns:BasicParameters` (xsl:for-each) |
| Services[] (Soc, OfferInstanceId, ExpirationDate, EffectiveDate, Status) | `ns:Services` (xsl:for-each) |

### §19.4 — SubscriberGeneralInfo Write-Back (3 Code Paths)

| Condition | Action | Fields Written |
|-----------|--------|----------------|
| `subscriber.SubscriberGeneralInfo == null` | Create new concept | Language, saleId (not OT 3/12002), MultiSimInd (89→Y else N), L9InstallationType, L9RelatedSubscriber |
| Exists and `OrderType != 11003` | Fill blanks only | Language (if blank), MultiSimInd (if blank) |
| `OrderType == 11003` | Full concept replacement | EffectiveDate, Language, ProofDate, ProofDoc, SplitPeriod, SMSInd, ProductSubtype, InitActDate, ConvergenceCode, l9TmvServiceLevel, saleId, smsLang, IMSIAlias, MultiSimInd, L9InstallationType, L9RelatedSubscriber |

### §19.5 — ResourceInfo Write-Back Summary

| ResourceName | extId Pattern | ValuesArray Source | Condition |
|-------------|--------------|-------------------|-----------|
| IMSI | `SUBRI:TrackingId:RefID:IMSI` | `BasicParameters[Name='IMSI'][1]/Values[1]` | Create if null |
| OLD_IMSI | `SUBRI:...:OLD_IMSI`, Source='CCBS' | Same IMSI value | OT 20/81/11027/11029 when IMSI present and OLD_IMSI null |
| SIM | `SUBRI:TrackingId:RefID:SIM` | `BasicParameters[Name='SIM'][1]/Values[1]` | Create if null |
| OLD_SIM | `SUBRI:...:OLD_SIM`, Source='CCBS' | Same SIM value | OT 20/81/11027/11029 |
| IMEI | `SUBRI:TrackingId:RefID:IMEI`, Source='CCBS' | `BasicParameters[Name='IMEI'][1]/Values[1]` | Always create if not found |
| PEID | `SUBRI:...:PEID`, Source='CCBS' | `BasicParameters[Name='PEID'][1]/Values[1]` | eSIM only: PEID + PMATCHID both in BasicParameters AND !subscriber.peid |
| OLD_PEID | `SUBRI:...:OLD_PEID` | Same PEID value | eSIM + OT 20/81/11027/11029 + !existsOldPeid |
| PMATCHID | `SUBRI:...:PMATCHID`, Source='CCBS' | `BasicParameters[Name='PMATCHID'][1]/Values[1]` | eSIM, if !subscriber.pmatchId |
| OLD_PMATCHID | `SUBRI:...:OLD_PMATCHID` | Same PMATCHID value | eSIM + OT 20/81/11027/11029 |
| logicalResource (BN) | Generated UUID | `BasicParameters[Type=PrimResourceTp AND Type!='C']/Values` | Always; ResourceCategory='R', Source='CCBS' |
| CFW_NO_PARAM | `SUBRI:...:CFW_NO_PARAM` | `BasicParameters[Name='CFW_NO_PARAM'][1]/Values[1]` | Always (may be empty) |
| CFNRY_NO_PARAM | `SUBRI:...:CFNRY_NO_PARAM` | Same pattern | Always |
| CFNRC_NO_PARAM | `SUBRI:...:CFNRC_NO_PARAM` | Same pattern | Always |
| CFU_NO_PARAM | `SUBRI:...:CFU_NO_PARAM` | Same pattern | Always |

### §19.6 — OfferInstanceId Sync (OrderTypes 4/5/128/126/11016)

```text
for each SubscriberOffer on subscriber:
  if (ServiceType == "86" OR ServiceType == "87"):           // FE offers
    find CCBS Services[] by OfferName
    if (count matches == 1):
      subscriber.SubscriberOffers[i].OfferInstanceId = CCBSOfferInstanceId  // direct
    else if (multiple matches):
      // isFirst logic: first match → assign if FEOfferInstanceId==0
      // subsequent matches with FEOfferInstanceId==0 → create dmcOfferToRemove SubscriberOffers
      // (ExtendedInfo[FE_OR_CCBS='DMC_REMOVE'] — marks for downstream DMC cleanup)
  else if (Action == "CHG_PARAM" OR OrderType == "5"):
    if (unique Services[] match by OfferName):
      set OfferInstanceId AND all ParameterInfo[j].OfferInstanceId = CCBSOfferInstanceId
```

### §19.7 — Additional Write-Backs

| Field | Source | Condition |
|-------|--------|-----------|
| `subscriber.SubscriberType` | `SubscriberTypeInfo/SubscriberType` | Always |
| `subscriber.PayChannelIdPrimary` | `SubscriberDefaultDistributionInfo[1]/PayChannelIdInfo/PayChannelId` | Always |
| `subscriber.MSISDN` | `BasicParameters[Name='MSISDN'][1]/Values[1]` | Only if currently blank |
| `subscriber.Status` | `SubscriberStatusInfo/SubStatus` | Only if currently ==0 |
| `SubscriberOffers[i].ExtendedInfo[IMEI_KNOX]` | `BasicParameters[Name='KNOX' AND OfferInstanceId=match]/Values` | OrderType=4 (OMX-2613) |
| `RelatedOffersArray[k].MatSerialRefId` | Cloud ID: `substring-after(Values,'-')`; CCTV: `Values[1]` | IoT: if BasicParameters[Cloud ID/CCTV Serial No] |
| `MaterialInfo.Material[].MatSerial` | CCTV Serial No Values[1] | IoT/CCTV only; creates MaterialInfo if null |
| `ResourceRangeInfo[]` | `BasicParameters[RangeInd=89]` — Values joined by '-', Action='ADD' | OrderType=126 only |

### §19.8 — Response Completion

```text
if (IntraActivitySequencing.ActionResponseEvent(currActivity)):
    return "true"   // all subscribers processed — activity can advance
else:
    return "false"  // waiting for next queued subscriber in sequence
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Dispatch is sequential (IntraActivitySequencing), ParentOU + ChildOU. Request payload is minimal: only the CCBS subscriber number.
- **R2** — ALT_CES routing: if activity parameter ALT_CES=Y and order has ExtendedInfo[ALT_CES], use that CES node. Implement as configurable routing at activity level.
- **R3** — Mandatory guard: if CCBS returns a response without SubscriberInfo, throw a DATA_ISSUE exception.
- **R4** — SubscriberGeneralInfo has three merge modes: create-new, fill-blanks, and full-replace (OrderType 11003).
- **R5** — MultiSimInd mapping: CCBS sends numeric value 89 — map to string "Y"; any other value maps to "N".
- **R6** — ResourceInfo set: IMSI, SIM, IMEI always populated; PEID/PMATCHID only for eSIM; OLD_* variants for SIM-swap order types.
- **R7** — CFW/CFNRY/CFNRC/CFU_NO_PARAM ResourceInfo concepts always created (may have empty ValuesArray).
- **R8** — OfferInstanceId sync only for specific order types and ServiceTypes. DMC_REMOVE concept creation for multiple-match FE offers.
- **R9** — NotKeepSubInfoResponse global config provides an escape hatch for specific order types.

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| 698-line response handler with 14+ distinct write-back paths | [HIGH] | Decompose into separate mapping services per data domain |
| Subscriber lookup by extId pattern (SUB: then CSUB:) — if extId differs, subscriber not found | [HIGH] | Verify extId generation matches exactly; add error logging when subscriber lookup returns null |
| eSIM detection by BasicParameters presence is implicit | [MEDIUM] | Add explicit eSIM flag or pre-check; log when eSIM expected but parameters absent |
| NotKeepSubInfoResponse is a comma-delimited string — substring match can fail with padding | [MEDIUM] | Use exact list comparison (Set.contains) in migration |
| Partially commented-out DMC_REMOVE code — active logic interleaved with commented blocks | [MEDIUM] | Review git blame carefully; only the uncommented DMC_REMOVE block is active |
| logicalResourceR selects by PrimResourceTp AND Type!='C' — may create blank concept | [LOW] | Handle empty ResourceName gracefully in downstream consumers |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
