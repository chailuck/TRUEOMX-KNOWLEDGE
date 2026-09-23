# Request_INTX_GET_SIM_INFO_BY_SIM

> Per-subscriber multi-SIM parallel INTX lookup by ICCID — writes SIM_STATUS, SIM_TYPE, SIM_COMPANY, SIM_PAIR_MSISDN, IMSI, SIM_DEALER to ResourceInfo; BULKESIM and BATCH special modes.

**Author:** awalia-t420 | **forwardChain:** true | **Generated:** 2026-08-04

---

## §1 Overview & Purpose

Queries the INTX backend (`GetSIMInfoByICCID`) for each subscriber's SIM card information. Each subscriber may generate **multiple requests** — one for the primary SIM and additional ones for multi-SIM (MSIM) cards from either a `MSIM_TO_CANCEL` cancel-list or from `TR_MULTISIM_IND=RES` offers. The response writes SIM attributes back to the subscriber as `ResourceInfo` concept instances. Two special modes: **BULKESIM** adds ICC_ID and VENDOR ExtendedInfo, **BATCH** sets SubscriberId/SubscriberType from the response.

> **Non-standard request count:** Each subscriber may generate 1+N requests (primary SIM + MSIM count). Fan-in total accumulates all events from all subscribers.

> **[DEAD CODE]:** `PurgePendingRequestsBeforeResubmit` and `IntraActivitySequencing.ActionRequestEvent` calls are commented out. Not executed on resubmit.

> **Custom response concept:** Uses `Concepts.FM.Response.INT_GetSIMInfoRes` — not ResponseBase. The `extId` is generated in BE code and passed as XSLT param (same unusual pattern as MCS_SUBSCRIPTION_MARKUSED response).

> **isASRMCompanyCode gate:** `String.length(res.SimStatus) > rmStatusLength` (global variable). ALL ResourceInfo write-backs are gated on this boolean.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_INTX_GET_SIM_INFO_BY_SIM.rule` | 241 lines |
| Response file | `Response_INTX_GET_SIM_INFO_BY_SIM.rulefunction` | 214 lines |
| Author | awalia-t420 | |
| forwardChain | true | |
| Schema NS | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetSIMInfoByICCID.xsd` | |
| Request root | `ns:GetSIMInfoByICCIDReq` | |
| Response root | `ns1:GetSIMInfoByICCIDRes` | |
| Response concept | `Concepts.FM.Response.INT_GetSIMInfoRes` | **Custom** — not ResponseBase |
| extId generation | `OMXUtils.generateTrackingID()` in BE, passed as XSLT param | |
| Fan-out | Multi-SIM per-subscriber — 1+N events per subscriber | |
| Fan-in | Standard "000" count == RequestCount | |
| PurgePendingRequestsBeforeResubmit | **[DEAD — commented out]** | |
| Credential gate | `IsEnableUserPass='true'` → UserName/PassWord | |
| Activity param PROJ | `GetActivityParameterValueFromKey("PROJ")` | BULKESIM mode gate |
| Activity param BATCH | `GetActivityParameterValueFromKey("BATCH")` | Response BATCH mode |
| Audit gate (request) | `AllowWriteLog(OrderType)` | Conditional |
| Audit gate (response) | `AllowWriteLog(OrderType)` | Conditional |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Subscriber data; OMXTrackingId; IntegrationMethod |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | RequestCount++; Response[]; PROJ parameter |
| `nextAct` | Concepts.OM.ProcessConfig.Activity | Live lookup — PreExecCheck |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "INTX_GET_SIM_INFO_BY_SIM"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "INTX_GET_SIM_INFO_BY_SIM"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 Execution Flow

1. **Setup** — isActResub; nextAct live lookup; projValue=`GetActivityParameterValueFromKey("PROJ")`; isSkipped=true
2. **[DEAD]** — PurgePendingRequestsBeforeResubmit commented out
3. **POU Subscribers loop** — for each ParentOU × Subscriber:
   - reqSuccess check (by RefId)
   - PreExecCheck via `GetXMLForSubscriber`
   - Extract `currSIM` from `ResourceInfo[ResourceName="SIM"].ValuesArray` — skip if blank
   - `bAlreadyHaveSimInfo` check — skip if SIM_STATUS present AND projValue != "BULKESIM"
   - **Tier A**: send primary reqEvent (currSIM); RequestCount++; audit
   - **Tier B or C**: multi-SIM events (see §6)
4. **COU Subscribers loop** — same 3-tier logic per COU subscriber
5. **Status** — if !isSkipped → `GetActivityStatusString("1")` + `SendDataToDB`; else → `SkipActivity("4")`
6. **Exception** — catch → `HandleActivityException`

---

## §6 Multi-SIM Fan-out Logic

After the primary `reqEvent` (Tier A), one of two additional tiers fires:

**Tier A — Primary SIM (always)**
- Source: `subscriber.ResourceInfo[ResourceName="SIM"].ValuesArray` → `currSIM`
- Event: `reqEvent` with XSLT param `$currSIM` → `ns:iccid`
- RequestCount++; AllowWriteLog audit

**Tier B — MSIM_TO_CANCEL list (if present)**
- Condition: `exists(subscriber/ExtendedInfo[Name="MSIM_TO_CANCEL"])`
- Parse: `String.split(msimToCancelString, "\\|")`
- For each `simValue` → send `reqEvent2` with `$simValue`; RequestCount++; audit

**Tier C — TR_MULTISIM_IND offers (else)**
- Scan `SubscriberOffers[]` for `ExtendedInfo[Name="TR_MULTISIM_IND" and Value="RES"]` AND `ParameterInfo[ParamName="Related SIM"]/ValuesArray`
- For each qualifying offer → send `reqEvent2` with `simValue` (Related SIM ValuesArray[1]); RequestCount++; audit

> Fan-in caveat: RequestCount accumulates ALL events (Tier A + B/C) across ALL subscribers. One subscriber with 3 MSIMs adds 4 to RequestCount.

---

## §7 Per-Subscriber Pre-flight Skip Guards

| Guard | Condition | Action |
|-------|-----------|--------|
| reqSuccess | `Response[].ReferenceId==refId AND CompletionStatus==2` | `continue` |
| PreExecCheck | XPath result != "true" | outer block not entered |
| No SIM card | `BRMS.IsBlank(currSIM)` | `continue` |
| Already has SIM info | `bAlreadyHaveSimInfo AND projValue != "BULKESIM"` | `continue` |

---

## §8 System & Integration Dependencies

### §8.1 — ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Purpose |
|-----------|---------|-------------|---------|
| [OUTBOUND] | FM JMS | INTX_GET_SIM_INFO_BY_SIM | SIM lookup by ICCID (1+N per subscriber) |
| [INBOUND] | FM JMS | INTX_GET_SIM_INFO_BY_SIM response | GetSIMInfoByICCIDRes |

### §8.2 — Backend API

| Field | Value |
|-------|-------|
| Backend | INTX (SIM resource management) |
| Operation | GetSIMInfoByICCID |
| Request root | `ns:GetSIMInfoByICCIDReq` |
| Search key | `ns:iccid` = ICCID |
| Correlation | `ns:correlatedId` = OMXTrackingId |

### §8.3 — BE Working Memory Dependencies

| Concept | Field | Access | Notes |
|---------|-------|--------|-------|
| Subscriber | `ResourceInfo[ResourceName="SIM"].ValuesArray` | READ | ICCID search key |
| Subscriber | `ExtendedInfo[Name="MSIM_TO_CANCEL"].Value` | READ | Pipe-delimited MSIM cancel list |
| SubscriberOffers | `ExtendedInfo[Name="TR_MULTISIM_IND"].Value` | READ | Multisim indicator |
| SubscriberOffers | `ParameterInfo[ParamName="Related SIM"].ValuesArray[1]` | READ | Related SIM ICCID |
| Subscriber | `ResourceInfo[ResourceName="SIM_STATUS"]` | READ | bAlreadyHaveSimInfo check |
| Subscriber | ResourceInfo[] (SIM_COMPANY, SIM_STATUS, SIM_PAIR_MSISDN, SIM_TYPE, IMSI, SIM_DEALER) | WRITTEN | isASRMCompanyCode gated |
| Subscriber | `ExtendedInfo[Name="ICC_ID"]` | WRITTEN | BULKESIM only |
| Subscriber | `ExtendedInfo[Name="VENDOR"]` | WRITTEN | BULKESIM only |
| Subscriber | `SubscriberId`, `SubscriberType` | WRITTEN | BATCH only |
| Subscriber | `ExtendedInfo[Name="simItemId"]` | WRITTEN | BATCH only |

### §8.4 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Credential gate |
| `OMX_OM/BizRules/RMStatusLength` | isASRMCompanyCode threshold |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `OMX_OM/WritePayload` | Audit payload inclusion |

---

## §9 Detailed Payload Build

### §9.1 — XSLT Variants

| Variant | Event var | SIM param | SIM source |
|---------|-----------|-----------|-----------|
| Tier A (primary) | `reqEvent` | `$currSIM` | `ResourceInfo[ResourceName="SIM"].ValuesArray` |
| Tier B (MSIM_TO_CANCEL) | `reqEvent2` | `$simValue` | `String.split(MSIM_TO_CANCEL, "\\|")[iMsim]` |
| Tier C (TR_MULTISIM_IND) | `reqEvent2` | `$simValue` | `SubscriberOffer/ParameterInfo[ParamName="Related SIM"]/ValuesArray[1]` |

All three use identical XSLT structure — only the SIM param name differs.

### §9.2 — XSLT Field Mapping Tree

```text
createEvent
└── event
    ├── @extId              ← OMXUtils:generateTrackingID()                [Always]
    ├── JMSPriority         ← $orderRequest/OrderPriority                  [Always]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId        [Always]
    ├── OrderID             ← $orderRequest/OrderData/OrderID              [Always]
    ├── RefID               ← $refId (subscriber RefId)                   [Always]
    ├── UserName            ← $orderRequest/OrderData/User                 [Credential-gated]
    ├── PassWord            ← $orderRequest/OrderData/Password             [Credential-gated]
    ├── OrderType           ← $orderRequest/OrderData/OrderType            [Always]
    └── payload
        └── ns:GetSIMInfoByICCIDReq
            ├── ns:correlatedId  ← $orderRequest/OrderData/OMXTrackingId  [Always]
            └── ns:iccid         ← $currSIM / $simValue                   [Always — variant-dependent]
```

---

## §10 Custom Response Concept — INT_GetSIMInfoRes

```text
createObject
└── object
    ├── @extId              ← $extId (generated in BE, passed as XSLT param)
    ├── ResponseCode        ← $eventResponse/ResponseCode                 [Conditional xsl:if]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg                  [Conditional xsl:if]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus             [Conditional xsl:if]
    ├── ReferenceId         ← $eventResponse/RefID                        [Conditional xsl:if]
    ├── SearchType          ← 'SERIAL_NO'                                 [Always / Hardcoded]
    ├── SearchKey           ← ns1:simInfo/ns1:serialNo                    [Conditional xsl:if]
    ├── SimType             ← tib:trim(ns1:simInfo/ns1:simType)           [Always]
    ├── SimStatus           ← tib:trim(ns1:simInfo/ns1:resourceStatus)    [Always]
    ├── SimCompany          ← tib:trim(ns1:simInfo/ns1:simCompanyCode)    [Always]
    ├── SimPairWithMobile   ← tib:trim(ns1:ctnInfo/ns1:ctn)              [Always]
    ├── SimImsi             ← tib:trim(ns1:simInfo/ns1:imsi)              [Always]
    └── SimDealer           ← tib:trim(ns1:simInfo/ns1:dealer)            [Always]
```

---

## §11 Response Write-back

### §11.1 — isASRMCompanyCode Gate

```java
int rmStatusLength = XPath("$globalVariables/OMX_OM/BizRules/RMStatusLength");
boolean isASRMCompanyCode = (String.length(res.SimStatus) > rmStatusLength);
// ALL ResourceInfo write-backs require isASRMCompanyCode == true
```

### §11.2 — Standard ResourceInfo Write-backs

| ResourceName | extId (SearchKey==currSIM) | extId (SearchKey!=currSIM) | Value source | Guard |
|-------------|--------------------------|--------------------------|-------------|-------|
| `SIM_COMPANY` | `SUBRI:…:SIM_COMPANY` | `SUBRI:…:SIM_COMPANY_<SearchKey>` | `res.SimCompany` | null AND !IsBlank AND isASRMCompanyCode |
| `SIM_STATUS` | `SUBRI:…:SIM_STATUS` | `SUBRI:…:SIM_STATUS_<SearchKey>` | `res.SimStatus` | same |
| `SIM_PAIR_MSISDN` | `SUBRI:…:SIM_PAIR_MSISDN` | `SUBRI:…:SIM_PAIR_MSISDN_<SearchKey>` | `res.SimPairWithMobile` | same |
| `SIM_TYPE` | `SUBRI:…:SIM_TYPE` | `SUBRI:…:SIM_TYPE_<SearchKey>` | `res.SimType` | same |
| `IMSI` | `SUBRI:…:IMSI` | `SUBRI:…:IMSI_<SearchKey>` | `res.SimImsi` | POU: +SearchKey==currSIM; +!existing IMSI in orderRequest |
| `SIM_DEALER` | `SUBRI:…:SIM_DEALER` | `SUBRI:…:SIM_DEALER_<SearchKey>` | `res.SimDealer` | null AND !IsBlank AND isASRMCompanyCode |

### §11.3 — BULKESIM Mode (projValue=="BULKESIM")

| Target | Name | Value source | Guard |
|--------|------|-------------|-------|
| ExtendedInfo | `ICC_ID` | `$currSIM` | `!exists(ExtendedInfo[Name="ICC_ID"])` |
| ExtendedInfo | `VENDOR` | `simInfo/vendor/vendorName` | `!exists(VENDOR) AND response has vendorName` |

### §11.4 — BATCH Mode (isBatch==true AND isBatchParam=="Y")

| Target | Field/Name | Value source |
|--------|-----------|-------------|
| Subscriber (direct) | `SubscriberId` | `tib:trim(simInfo/dummyMsisdn)` |
| Subscriber (direct) | `SubscriberType` | `tib:trim(simInfo/simCompanyCode)` |
| ExtendedInfo | `simItemId` | `tib:trim(simInfo/itemId)` |

---

## §12 Audit Logging

| Phase | Gate | AUDIT_TRACE | Per |
|-------|------|-------------|-----|
| Request (reqEvent) | [AllowWriteLog] | `"Request Sent for INTX_GET_SIM_INFO_BY_SIM"` | Per primary SIM event |
| Request (reqEvent2) | [AllowWriteLog] | `"Request Sent for INTX_GET_SIM_INFO_BY_SIM"` | Per MSIM event |
| Response | [AllowWriteLog] | `concat("Response received for RefId ", $eventResponse/RefID)` | Once per response |

---

## §13 Activity Status Management

| Condition | Call | Code |
|-----------|------|------|
| At least one event sent | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" (RUNNING) |
| No subscribers qualify | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" (SKIPPED) |

---

## §14 Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §15 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `GetActivityParameterValueFromKey(activity, "PROJ")` | BULKESIM mode gate |
| `GetActivityParameterValueFromKey(currActivity, "BATCH")` | BATCH mode gate (response) |
| `BRMS.IsBlank(currSIM)` | Skip subscriber if no SIM card |
| `AllowWriteLog(OrderType)` | Audit gate — both request and response |
| `GetXMLForSubscriber / GetXMLForSubscriberInChildOU` | PreExecCheck XML |
| `Instance.getByExtIdByUri("SUBRI:…")` | ResourceInfo dedup check |
| `String.split(msimToCancelString, "\\|")` | Parse pipe-delimited MSIM_TO_CANCEL |

---

## §16 Function Dependency Tree

```text
Request_INTX_GET_SIM_INFO_BY_SIM (rule)
├── Instance.getByExtIdByUri(NextActivityName, Activity)  [nextAct]
├── GetActivityParameterValueFromKey(activity, "PROJ")
├── [per POU × Subscriber]:
│   ├── Response[].ReferenceId==refId  [reqSuccess]
│   ├── GetXMLForSubscriber + XPath.execute(PreExecCheck)
│   ├── subscriber.ResourceInfo[r] where ResourceName=="SIM"  [currSIM loop]
│   ├── BRMS.IsBlank(currSIM)  [skip if blank]
│   ├── XPath.evalAsBoolean → bAlreadyHaveSimInfo
│   ├── [Tier A]: Event.createEvent($currSIM) → sendEventImmediate; RequestCount++; audit
│   ├── [Tier B]: XPath → MSIM_TO_CANCEL; String.split(…,"\\|"); per simValue: createEvent+send+count+audit
│   └── [Tier C else]: per SubscriberOffers[TR_MULTISIM_IND=RES]: createEvent+send+count+audit
├── [COU loop: mirrors POU with GetXMLForSubscriberInChildOU]
├── GetActivityStatusString("1") + SendDataToDB  [or SkipActivity("4")]
└── HandleActivityException  [catch]

Response_INTX_GET_SIM_INFO_BY_SIM (rulefunction)
├── extId = OMXUtils.generateTrackingID()  [in BE, passed to XSLT]
├── Instance.createInstance("xslt://INT_GetSIMInfoRes")  [custom concept]
│   └── SearchType="SERIAL_NO"; SearchKey; SimType/Status/Company/PairWithMobile/Imsi/Dealer (tib:trim)
├── currActivity.Response[length] = res
├── rmStatusLength = XPath(globalVariables/RMStatusLength)
├── isBatch + isBatchParam + projValue from GetActivityParameterValueFromKey
├── [per POU × Subscriber where res.SearchKey == currSIM]:
│   ├── isASRMCompanyCode = length(SimStatus) > rmStatusLength
│   ├── SIM_COMPANY / SIM_STATUS / SIM_PAIR_MSISDN / SIM_TYPE / IMSI / SIM_DEALER ResourceInfo writes
│   ├── [BULKESIM]: ICC_ID + VENDOR ExtendedInfo
│   └── [BATCH+Y]: SubscriberId=dummyMsisdn; SubscriberType=simCompanyCode; simItemId
├── [COU loop: same, no IMSI POU guard]
├── AllowWriteLog → sendAudit
└── XPath count("000") → fan-in
```

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Extract `currSIM` from `subscriber.ResourceInfo[ResourceName="SIM"].ValuesArray`; skip if blank. |
| R2 | Skip if SIM_STATUS already populated AND PROJ != "BULKESIM". |
| R3 | Three-tier fan-out: primary SIM, then MSIM_TO_CANCEL pipe-list, else TR_MULTISIM_IND offers. |
| R4 | Payload: `ns:GetSIMInfoByICCIDReq` with `ns:correlatedId`=OMXTrackingId and `ns:iccid`=ICCID. |
| R5 | Credential gate on `IsEnableUserPass='true'`. |
| R6 | Audit gated by `AllowWriteLog(OrderType)` — per event for requests, once for response. |
| R7 | Custom `INT_GetSIMInfoRes` concept; `extId` generated in BE and passed as XSLT param. |
| R8 | Match response to subscriber by `res.SearchKey == currSIM`; all write-backs gated on `isASRMCompanyCode`. |
| R9 | MSIM ResourceInfo names/extIds get `_<SearchKey>` suffix when `res.SearchKey != currSIM`. |
| R10 | BULKESIM mode: ICC_ID and VENDOR ExtendedInfo. |
| R11 | BATCH mode: dummyMsisdn→SubscriberId; simCompanyCode→SubscriberType; itemId→simItemId. |
| R12 | Fan-in: "000" count == RequestCount (total across all SIM events, all subscribers). |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| RequestCount accumulates ALL SIM events — fan-in count varies per subscriber MSIM count | [MEDIUM] | Ensure MSIM counts stable; document variable-count pattern |
| `PurgePendingRequestsBeforeResubmit` commented out — resubmit may produce duplicate counts | [MEDIUM] | Verify resubmit behavior; re-enable or ensure reqSuccess dedup covers multi-SIM |
| COU IMSI write-back lacks `SearchKey==currSIM` guard that POU branch has | [LOW] | Verify COU IMSI write-back for MSIM responses |
| `rmStatusLength` misconfigured → all SIM attributes silently skipped | [LOW] | Alert on rmStatusLength=0; document expected value |
| Three near-identical XSLT variants — maintenance divergence risk | [LOW] | Consolidate to single XSLT with unified `$iccid` param |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
