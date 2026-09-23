# Request_INTX_GET_SIM_INFO_BY_ICCID

> TIBCO BusinessEvents FM Logic — INTX SIM Information Lookup by ICCID (Multi-Event Parallel Fan-out)

**Author:** TIT_P10-SARUN3 | **Priority:** 5 | **Forward Chain:** true | **Target:** INTX | **Pattern:** Parallel Fan-out — Multiple Events per Subscriber

---

## §1 — Overview & Purpose

This rule queries INTX (the SIM/MSISDN registry) for SIM card information by ICCID. It dispatches `GetSIMInfoByICCIDReq` JMS events for each subscriber's SIM(s), including additional events for MultiSIM and RIO scenarios. The response enriches the order's working memory with SIM status, type, company, IMSI, pairing information, and vendor data.

> **Most complex FM in this process:** This rule can dispatch **multiple events per subscriber** — primary SIM + MSIM_TO_CANCEL list, or MultiSIM offer-level ICCIDs, or RIO subscriber/offer-level ICCIDs. Total 381 lines request + 320 lines response rulefunction.

> **Note on event name:** Despite the rule being named `_BY_ICCID`, the JMS event dispatched is `Events.OMConsumers.OMXFM.Request.INTX_GET_SIM_INFO_BY_SIM`. The naming difference is historical.

| Item | Value |
|------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_SIM_INFO_BY_ICCID` |
| Author | TIT_P10-SARUN3 |
| JMS Event Dispatched | `Events.OMConsumers.OMXFM.Request.INTX_GET_SIM_INFO_BY_SIM` |
| Payload Schema | `ns:GetSIMInfoByICCIDReq` (OMX-COMMON INTX/GetSIMInfoByICCID.xsd) |
| Response Concept | `Concepts.FM.Response.OSB_GetSIMInfoByICCIDRes` |
| Target System | INTX (SIM/MSISDN registry) |
| Parameters Used | PROJ (RIO / RIO_SWAP / others), USE_ICC_ID |
| Dispatch Method | `Event.Ext.sendEventImmediate()` — parallel fan-out |
| Fan-In | `count(Response[tib:right(tib:trim(ResponseCode),3)="000"]) == RequestCount` |
| Audit Gate | `AllowWriteLog(orderRequest.OrderData.OrderType)` (unique — not unconditional) |

---

## §2 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Current process step match |
| 2 | `orderCurrentActivity.ActivityID == "INTX_GET_SIM_INFO_BY_ICCID"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "INTX_GET_SIM_INFO_BY_ICCID"` | Process flow confirmation |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fire once per activity |

---

## §3 — Activity Parameters

| Parameter | Key | Effect |
|-----------|-----|--------|
| PROJ | `GetActivityParamValueFromKey(orderCurrentActivity, "PROJ")` | "RIO" or "RIO_SWAP" → different ICCID source + additional events. Else → standard SIM/PEID logic. |
| USE_ICC_ID | `GetActivityParamValueFromKey(orderCurrentActivity, "USE_ICC_ID")` | "Y" → force use of `ExtendedInfo[Name="ICC_ID"]/Value` as ICCID even when no PEID/PMATCHID |

---

## §4 — ICCID Source Selection Matrix

> **The most important business logic in this rule:** The ICCID to query is not always the SIM ResourceInfo. The selection depends on PROJ parameter and the presence of eSIM-related resource fields.

### §4.1 POU Subscriber (primary event)

| Condition | ICCID Source |
|-----------|-------------|
| PROJ == "RIO" or PROJ == "RIO_SWAP" | `ResourceInfo[ResourceName="SIM"]/ValuesArray` |
| PEID+PMATCHID both exist, OR NEW_PEID+NEW_PMATCHID both exist, OR USE_ICC_ID="Y" | `ExtendedInfo[Name="ICC_ID"]/Value` |
| Default (none of above) | `ResourceInfo[ResourceName="SIM"]/ValuesArray` |

If `currSIM` is blank (`BRMS.IsBlank(currSIM)`) → `continue` (skip this subscriber).

### §4.2 COU Subscriber (primary event)

| Condition | ICCID Source |
|-----------|-------------|
| PEID+PMATCHID both exist, OR NEW_PEID+NEW_PMATCHID both exist | `ExtendedInfo[Name="ICC_ID"]/Value` |
| Default | `ResourceInfo[ResourceName="SIM"]/ValuesArray` |

> **COU differences from POU:**
> 1. No RIO-specific branch for ICCID source.
> 2. `bAlreadyHaveSimInfo` check is active in COU (if SIM_STATUS already populated → skip) but **COMMENTED OUT** in POU.
> 3. USE_ICC_ID parameter not applied in COU.

---

## §5 — Multi-Event Dispatch Per Subscriber

After the primary SIM lookup event, additional events (`reqEvent2`) may be dispatched for the same subscriber.

### §5.1 POU & COU — Non-RIO additional events

| Condition | Action | ICCID Source |
|-----------|--------|-------------|
| `ExtendedInfo[Name="MSIM_TO_CANCEL"]` exists | Split value by `\|` → one extra event per ICCID in list | Each element of MSIM_TO_CANCEL pipe-delimited list |
| No MSIM_TO_CANCEL: offer has `TR_MULTISIM_IND=RES` and `ParameterInfo[ParamName="Related SIM"]` | One extra event per qualifying offer | `ParameterInfo[ParamName="Related SIM"]/ValuesArray[1]` |
| No MSIM_TO_CANCEL: offer has `ICC_ID` and `TR_MULTISIM_IND=REE` | One extra event per qualifying offer | `curoffer.ExtendedInfo[Name="ICC_ID"]/Value` |

### §5.2 POU — RIO / RIO_SWAP additional events

| Condition | Action | ICCID Source |
|-----------|--------|-------------|
| `SubscriberOffers.ExtendedInfo[Name="ICC_ID"]` exists AND `TR_MULTISIM_IND=REE` | Extra event | `SubscriberOffers.ExtendedInfo[Name="ICC_ID"]/Value` |
| `ExtendedInfo[Name="ICC_ID"]` (subscriber level) exists | Extra event | `subscriber.ExtendedInfo[Name="ICC_ID"]/Value` |

### §5.3 COU — RIO / RIO_SWAP additional events

Same as POU §5.2 — identical conditions and sources.

> **Maximum events per subscriber:** In the worst case (RIO with MultiSIM): primary SIM event + offer-level ICC_ID event + subscriber-level ICC_ID event. In non-RIO with MSIM_TO_CANCEL: primary + N additional for each ICCID in the cancel list.

---

## §6 — Execution Flow

1. Read PROJ and USE_ICC_ID parameters
2. **Loop POU Subscribers:**
   a. reqSuccess check (CompletionStatus==2 + RefId match)
   b. PreExecCheck via `GetXMLForSubscriber()`
   c. Resolve `currSIM` (§4.1 matrix)
   d. If blank → `continue`
   e. Send primary `reqEvent` (§9.1); `RequestCount++` if !isActResub
   f. Audit if `AllowWriteLog(OrderType)`
   g. If RIO/RIO_SWAP → additional events (§5.2); `RequestCount++` for each
   h. If non-RIO → check MSIM_TO_CANCEL or offer-level MultiSIM events (§5.1); `RequestCount++` for each
3. **Loop COU Subscribers:**
   a. reqSuccess + PreExecCheck via `GetXMLForSubscriberInChildOU()`
   b. Resolve `currSIM` (§4.2 matrix)
   c. If `bAlreadyHaveSimInfo` (SIM_STATUS populated) → `continue`
   d. Send primary event; same additional event logic as POU
4. If !isSkipped: `GetActivityStatusString("1",false)` + `SendDataToDB()`
5. Else: `SkipActivity("4")`
6. catch: `HandleActivityException()`

---

## §7 — Payload Build (XSLT)

All event variants share the same payload structure — only the `iccid` value differs:

| Element | Source | Notes |
|---------|--------|-------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$refId` (subscriber RefId) | Always |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Always |
| `ns:GetSIMInfoByICCIDReq / ns:correlatedId` | `$orderRequest/OrderData/OMXTrackingId` | Correlation key for INTX |
| `ns:GetSIMInfoByICCIDReq / ns:iccid` | `$currSIM` or `$simValue` | The resolved ICCID — varies per §4 |

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority            [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId  [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID         [Always]
    ├── RefID                ← $refId                                  [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType       [Always]
    └── payload
        └── ns:GetSIMInfoByICCIDReq
            ├── ns:correlatedId  ← $orderRequest/OrderData/OMXTrackingId  [Always]
            └── ns:iccid         ← $currSIM (resolved by §4 matrix)        [Always]
```

---

## §8 — System & Integration Dependencies

### §8.1 ESB / JMS Channel

| Direction | Event | Purpose |
|-----------|-------|---------|
| [OUTBOUND] | `INTX_GET_SIM_INFO_BY_SIM` | Query INTX for SIM info by ICCID (primary + additional per subscriber) |
| [OUTBOUND] | `Logger` | Audit — gated on `AllowWriteLog(OrderType)` |

### §8.2 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `$globalVariables/OMX_OM/BizRules/RMStatusLength` | Response: gate for isASRMCompanyCode |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Audit payload gate |

---

## §9 — Audit Logging

> **Conditional audit (unique pattern):** Unlike all other FMs in this process that always log, this rule gates audit logging on `RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)`. If the order type is excluded from logging, no audit events are sent.

| Field | Value |
|-------|-------|
| OPERATION_NAME | `$operationName` (= `orderCurrentActivity.ActivityID` = "INTX_GET_SIM_INFO_BY_ICCID") (dynamic) |
| AUDIT_TRACE | `concat("Request Sent for ", $operationName)` (dynamic) |
| payload | `copy-of $reqEvent` (full event payload — includes ICCID) |
| Send method | `Event.Ext.sendEventImmediate()` |

---

## §10 — Activity Status Management

| State | Trigger | Call |
|-------|---------|------|
| [ACTIVE] | At least one event dispatched | `GetActivityStatusString("1", false)` + `SendDataToDB()` |
| [SKIPPED] | All subscribers had blank currSIM | `SkipActivity("4")` |

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|----------|--------|---------|
| `GetActivityParamValueFromKey(orderCurrentActivity, "PROJ")` | String | RIO/RIO_SWAP/other — controls ICCID source and additional events |
| `GetActivityParamValueFromKey(orderCurrentActivity, "USE_ICC_ID")` | String | "Y" → force ICC_ID usage as ICCID source (POU only) |
| `GetXMLForSubscriber(orderRequest, refId)` | String XML | Serialize POU subscriber for PreExecCheck |
| `GetXMLForSubscriberInChildOU(orderRequest, refId, pOuRefId)` | String XML | Serialize COU subscriber for PreExecCheck |
| `BRMS.IsBlank(currSIM)` | boolean | Guard against blank ICCID |
| `AllowWriteLog(OrderType)` | boolean | Gate for audit log emission (order-type specific) |
| `GetActivityStatusString("1", false)` | String | ACTIVE status |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | void | Mark SKIPPED |
| `SendDataToDB(orderRequest)` | void | Persist order state |
| `HandleActivityException(...)` | void | Exception handler |

---

## §15 — Function Dependency Tree

```text
Request_INTX_GET_SIM_INFO_BY_ICCID (BE rule)
├── GetActivityParamValueFromKey(orderCurrentActivity, "PROJ")
├── GetActivityParamValueFromKey(orderCurrentActivity, "USE_ICC_ID")
│
├── [Loop POU Subscribers]
│   ├── reqSuccess check (CompletionStatus==2 + RefId)
│   ├── GetXMLForSubscriber(orderRequest, refId)         [PreExecCheck]
│   ├── XPath.evalAsString(ICCID selection)               [§4.1 matrix]
│   ├── BRMS.IsBlank(currSIM)                             [skip if blank]
│   ├── Event.createEvent("xslt://../INTX_GET_SIM_INFO_BY_SIM") → primary reqEvent
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   ├── RequestCount++                                     [if !isActResub]
│   ├── AllowWriteLog(OrderType) → Event.Ext.sendEventImmediate(audit)
│   │
│   ├── [if RIO/RIO_SWAP] extra events for:
│   │   ├── SubscriberOffers[ICC_ID + TR_MULTISIM_IND=REE]
│   │   └── subscriber.ExtendedInfo[Name="ICC_ID"]
│   │
│   └── [if non-RIO] extra events for:
│       ├── MSIM_TO_CANCEL pipe-list → one per ICCID
│       └── offers with TR_MULTISIM_IND=RES/REE
│
├── [Loop COU Subscribers] — same pattern + bAlreadyHaveSimInfo skip
│
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(...)
└── HandleActivityException(...)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — ICCID source: RIO/RIO_SWAP → SIM resource; PEID+PMATCHID or USE_ICC_ID=Y → ICC_ID; else SIM resource
- **R2** — MultiSIM (non-RIO): send extra events for MSIM_TO_CANCEL list items and offer-level ICCIDs (RES/REE indicators)
- **R3** — RIO: send extra events for SubscriberOffers ICC_ID (REE) and subscriber-level ICC_ID
- **R4** — COU: skip if SIM_STATUS already populated (INT_GET_SIM_INFO_BY_MSISDN ran first)
- **R5** — Audit is conditional on `AllowWriteLog(OrderType)`
- **R6** — Fan-in: count of "000"-suffix responses must equal RequestCount

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| ICCID source selection is implicit and multi-branched — easy to break in migration | [HIGH] | Document the §4 matrix explicitly in tests; cover all PROJ + resource combinations |
| Multiple events per subscriber with different RequestCount increments — fan-in count must be exact | [HIGH] | Track all RequestCount++ paths; end-to-end test with MultiSIM orders |
| POU bAlreadyHaveSimInfo check commented out; COU has it active — asymmetric behavior | [MEDIUM] | Decide definitively whether POU should also skip when SIM_STATUS populated |
| Commented-out IntraActivitySequencing calls — code shows history of serial-to-parallel migration | [LOW] | Remove dead commented code in migration; the current pattern is parallel |
| Response working-memory enrichment is massive (10+ ResourceInfo/ExtendedInfo appends) — order of operations matters | [MEDIUM] | Preserve exact matching logic: `res.SearchKey==currSIM OR res.MobilePairWithSIM==currSIM` |

---

## §19 — Response Message Rule

### §19.1 Overview

`Response_INTX_GET_SIM_INFO_BY_ICCID.rulefunction` (320 lines): creates an `OSB_GetSIMInfoByICCIDRes` concept from the INTX response, then performs extensive working memory enrichment — matching the response to the correct subscriber and appending ResourceInfo/ExtendedInfo concepts for SIM status, type, company, IMSI, dealer, and vendor data.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — subscribers looped again to match and enrich |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.INTX_GET_SIM_INFO_BY_SIM` | INTX response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; fan-in check |

### §19.3 Error Guard

Before creating the concept: if neither `ctnInfo` nor `simInfo` is present in the response → `throw Exception.newException("DATA_ISSUE", "No SIM Info returned.", null)`

### §19.4 ResponseBase Concept Fields

```text
createObject (OSB_GetSIMInfoByICCIDRes)
└── object
    ├── @extId             ← $eventResponse/@extId          [Conditional — Note: extId=OMXUtils.generateTrackingID() dead read]
    ├── ResponseCode       ← $eventResponse/ResponseCode    [Conditional]
    ├── ResponseMessage    ← $eventResponse/ResponseMsg     [Conditional]
    ├── CompletionStatus   ← $eventResponse/CompletionStatus[Conditional]
    ├── ReferenceId        ← $eventResponse/RefID           [Conditional]
    ├── SearchType         ← "MOBILE"                       [Always, static]
    ├── SearchKey          ← payload/ns5:ctnInfo/ns5:ctn    [Conditional — paired mobile number]
    ├── MobileStatus       ← ns5:ctnInfo/ns5:ctnStatus      [Conditional]
    ├── MobileCompany      ← ns5:ctnInfo/ns5:ctnCompanyCode [Conditional]
    ├── MobilePairWithSIM  ← ns5:simInfo/ns5:serialNo       [Conditional — SIM serial paired with mobile]
    ├── SimType            ← ns5:simInfo/ns5:simType        [Conditional]
    ├── SimStatus          ← ns5:simInfo/ns5:resourceStatus [Conditional]
    ├── SimCompany         ← ns5:simInfo/ns5:simCompanyCode [Conditional]
    ├── MobilePoolName     ← ns5:ctnInfo/ns5:ctnPoolCode    [Conditional]
    ├── MobilePoolType     ← ns5:ctnInfo/ns5:ctnPoolType    [Conditional]
    ├── SimImsi            ← ns5:simInfo/ns5:imsi           [Conditional]
    ├── SimDealer          ← ns5:simInfo/ns5:dealer         [Conditional]
    └── vendorName         ← lower-case(ns5:simInfo/ns5:vendor/ns5:vendorName)  [Conditional]
```

### §19.5 Working Memory Enrichment

After appending the response concept, the handler loops ALL subscribers again and matches by `res.SearchKey == currSIM OR res.MobilePairWithSIM == currSIM`. When matched:

> **isASRMCompanyCode gate:** `isASRMCompanyCode = (String.length(res.SimStatus) > rmStatusLength)` where `rmStatusLength = $globalVariables/OMX_OM/BizRules/RMStatusLength`. Enrichment of SIM_COMPANY, SIM_STATUS, SIM_PAIR_MSISDN, SIM_TYPE, IMSI, SIM_DEALER is only performed when this is true.

| Enrichment | Gate | Source Field |
|-----------|------|-------------|
| VENDOR ExtendedInfo on subscriber | No existing VENDOR + has ICC_ID | `res.vendorName` (lower-case) |
| SIM_COMPANY ResourceInfo | isASRMCompanyCode + not exists | `res.SimCompany` |
| SIM_STATUS ResourceInfo | isASRMCompanyCode + not exists | `res.SimStatus` |
| SIM_PAIR_MSISDN ResourceInfo | isASRMCompanyCode + not exists | `res.SimPairWithMobile` |
| SIM_TYPE ResourceInfo | isASRMCompanyCode + not exists | `res.SimType` |
| IMSI ResourceInfo | isASRMCompanyCode + no existing IMSI + res.SimImsi not blank | `res.SimImsi` |
| SIM_DEALER ResourceInfo | isASRMCompanyCode + not exists | `res.SimDealer` |
| SIM ResourceInfo (eSIM support) | No existing SIM resource + ICC_ID has value | `subscriber.ExtendedInfo[Name="ICC_ID"]/Value` |

**RIO-specific enrichment** (when MobilePairWithSIM matches subscriber's SubscriberOffers ICC_ID or subscriber ICC_ID):

| Enrichment | Gate | Notes |
|-----------|------|-------|
| MIIMSI ResourceInfo | res.SimImsi not blank + no existing MIIMSI | IMSI for the secondary (MI) SIM |
| MISIM ResourceInfo | res.MobilePairWithSIM not blank + no existing MISIM | ICCID of the secondary SIM |
| Related IMSI ParameterInfo on offers | PROJ=RIO + offer has ICC_ID but no Related IMSI | Appended to matching offer ParameterInfo array |
| Related SIM ParameterInfo on offers | PROJ=RIO + offer has ICC_ID but no Related SIM | Appended to matching offer ParameterInfo array |
| NEW_IMSI ResourceInfo | PROJ=RIO_SWAP or MNP_OTA + no existing NEW_IMSI | SimImsi from response |
| NEW_SIM ResourceInfo | PROJ=RIO_SWAP + no existing NEW_SIM | MobilePairWithSIM from response |
| VENDOR ExtendedInfo on subscriber | PROJ=RIO_SWAP + no existing VENDOR + has ICC_ID | vendorName from response |

### §19.6 Fan-In Completion

| Item | Value |
|------|-------|
| XPath expression | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Completion condition | `currActivity.RequestCount == successResponseCount` |
| Returns "true" | All dispatched events received "000" success responses |
| Returns "false" | Still waiting for responses |

**Dead read in response:** `String extId = OMXUtils.generateTrackingID()` is called at line 25 of the response rulefunction but `$extId` is never used as an XSLT param — the response concept extId comes from `$eventResponse/@extId` instead.

### §19.7 Response Audit

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(System.nanoTime(), "_RES")` |
| OPERATION_NAME | `$operationName` (= currActivity.ActivityID = "INTX_GET_SIM_INFO_BY_ICCID") |
| AUDIT_TRACE | `concat("Response received for ", $operationName)` |
| Gate | `AllowWriteLog(OrderType)` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
