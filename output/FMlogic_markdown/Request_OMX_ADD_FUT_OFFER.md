# Request_OMX_ADD_FUT_OFFER

> External OMXFM — Add Future SOC Order · FutureOrderWithSoc schema

**Rule class:** `Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_FUT_OFFER`
**Backend:** OMX FM (Future Order component) | **Integration:** JMS / Async | **Author:** RS33-BANDIT

---

## §1 — Overview & Purpose

`OMX_ADD_FUT_OFFER` submits future-dated SOC (Service Order Code) offers to the OMX Future Order component.
For each offer (Agreement or Subscriber level, across ParentOU and ChildOU) whose date type was classified as FUT
by `OMX_CAL_OFFER_FUT_DATE`, this rule sends a `futureOrderWithSoc` JMS request to register the offer as a
scheduled future provisioning action in the OMX FM layer.

| Property | Value |
|----------|-------|
| Rule class | `Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_FUT_OFFER` |
| Backend System | OMX FM — Future Order component |
| Integration type | JMS / Async |
| Request event | `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` |
| Response event | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` |
| Request schema | `ns3:futureOrderWithSoc` (FutureOrderWithSoc.xsd + FutureSoc.xsd + FutureOrder.xsd) |
| Response schema | `xsd4:AddFutureOrderResponse` (FUT_ORDER_ID, nodeId, soc) |
| RefID pattern | `{agreementRefId}:{soc}` (Agreement) / `{subRefId}:{soc}` (Subscriber) |
| Resubmit support | Yes — purges pending requests; does not increment RequestCount on resubmit |
| Also reads next activity PreExecCheck | Yes — same pattern as IOM_CHECK_SEQUENCING |
| Skip code | `SkipActivity(orderRequest, orderCurrentActivity, "4")` when no offers sent |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule Name | `Request_OMX_ADD_FUT_OFFER` | External OMXFM request rule |
| Namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Priority | 5 | |
| forwardChain | true | |
| Author | RS33-BANDIT | Malinee (Feb 2018 prepaid param) + Wattanachai (futOrderDate +1 day) |
| WHEN trigger | Status == "WAITING" | |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — Customer hierarchy, IsOrderResubmitted flag |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — Parameter list, Response[], RequestCount |
| `nextAct` | `Concepts.OM.ProcessConfig.Activity` | Next activity — PreExecCheck XPath evaluated per offer |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Bind to current step |
| 2 | `orderCurrentActivity.ActivityID == "OMX_ADD_FUT_OFFER"` | Route to this rule |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_ADD_FUT_OFFER"` | Cross-check ProcessFlow state |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Ready to execute |

---

## §5 — Execution Flow

1. **Resubmit check** — `isActResub = (RequestCount > 0 && IsOrderResubmitted)`. If true: call `PurgePendingRequestsBeforeResubmit()`. RequestCount will NOT be incremented during resubmit iteration.
2. **Read exclusion list & next activity PreExecCheck** — Read `globalVariables/.../FutureSocExtended_Exclude_Record` (comma-delimited ExtendedInfo names to exclude). Fetch next activity PreExecCheck. Read ORDERTYPE parameter.
3. **ParentOU Agreement Offers loop** — RefID = `{pAgreeRefId}:{soc}`. Check reqSuccess guard. Evaluate PreExecCheck. Build `futureOrderWithSoc` (nodeLevel=3, orderType default=37, nodeId=pOuId). Send JMS.
4. **ParentOU Subscriber Offers loop** — RefID = `{pSubRefId}:{soc}`. Wattanachai: `futOrderDate = DateTime.addDay(psof.EffectiveDate, 1)` when LOGICALDATE_PROV=B. nodeLevel=5, orderType default=3, nodeId=pSubId.
5. **ChildOU Agreement & Subscriber Offers** — Same logic as steps 3–4 for ChildOU context (cOuId, cAgreeRefId, cSubId).
6. **Status branch** — Any sent: `GetActivityStatusString("1", false)` + `SendDataToDB(orderRequest)`. All skipped: `SkipActivity("4")`.
7. **Exception** — `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §7 — Data Extraction & Key Variables

| Variable | Source | Notes |
|----------|--------|-------|
| `isActResub` | `RequestCount > 0 && IsOrderResubmitted` | Controls purge and RequestCount increment |
| `exclusionExtendedInfo` | `globalVariables/.../FutureSocExtended_Exclude_Record` | Comma-delimited ExtendedInfo names excluded from futureSoc payload |
| `paramOrderType` | `orderCurrentActivity.Parameter["ORDERTYPE"]` | Overrides default orderType (37/3); Malinee prepaid extension |
| `futOrderDate` | `DateTime.addDay(offer.EffectiveDate, 1)` | Wattanachai: used for effectiveDate when LOGICALDATE_PROV=B |
| `pSubId` | `MapSubscriberIdFromCRM(psub, USE_ROWID_CRM)` | Maps subscriber ID based on CRM row ID parameter |

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event | Protocol | Purpose |
|-----------|-------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` | JMS | Submit futureOrderWithSoc to OMX FM |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` | JMS | Receive FUT_ORDER_ID from OMX FM |

### §8.3 Backend API Details

| System | Operation | Schema | Correlation |
|--------|-----------|--------|-------------|
| OMX FM (Future Order) | AddFutureOrder | `ns3:futureOrderWithSoc` / `xsd4:AddFutureOrderResponse` | RefID = `{agreementRefId|subRefId}:{soc}`; fan-in on RequestCount == successResponseCount |

### §8.4 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `orderRequest.IsOrderResubmitted` | READ | Resubmit mode flag |
| `orderCurrentActivity.Response[].ReferenceId / CompletionStatus` | READ | reqSuccess guard |
| `offer.EffectiveDate`, `offer.Soc`, `offer.ParameterInfo[]` | READ | Payload construction |
| `offer.ExtendedInfo[EXP_DATE_VALUE]` | READ | Used as ns2:expireDate in futureSoc |
| `offer.ExtendedInfo[LOGICALDATE_PROV]` | READ | Controls effectiveDate override (futOrderDate when B) |
| `offer.ExtendedInfo[SBM_NO_PROVISIONING]` | READ | Triggers SBM_PROVISIONING=N in futureOrder extendedInfo |
| `offer.SocProperties` | READ | Drives subType: CUG_IND, TR_CONTRACT_IND, TR_IDD_FLAG, TR_IR_FLAG |
| `offer.RelatedOffersArray[]` | READ | Built as ns2:childSoc elements |
| `orderCurrentActivity.RequestCount` | WRITE | Incremented per request (not on resubmit) |
| `orderCurrentActivity.Status` | WRITE | Set to "1" (IN_PROGRESS equivalent) |

### §8.5 Activity Parameters

| Parameter | Effect |
|-----------|--------|
| `ORDERTYPE` | Overrides ns:orderType in futureOrder (default 37 for Agreement, 3 for Subscriber) |
| `USE_ROWID_CRM` | Drives `MapSubscriberIdFromCRM` — whether to use CRM row ID as subscriber ID |

---

## §9 — Detailed Payload Build

### §9.4 Payload Structure

```xml
<ns3:futureOrderWithSoc
  xmlns:ns3="http://...FutureOrderWithSoc.xsd"
  xmlns:ns="http://...FutureOrder.xsd"
  xmlns:ns2="http://...FutureSoc.xsd">

  <ns:futureOrder>
    <ns:effectiveDate>offer.EffectiveDate [or futOrderDate+1 when LOGICALDATE_PROV=B; Agreement always uses EffectiveDate]</ns:effectiveDate>
    <ns:status>1</ns:status>                        <!-- Static -->
    <ns:orderType>37 or 3 [or paramOrderType]</ns:orderType>   <!-- 37=Agreement, 3=Subscriber -->
    <ns:nodeLevel>3 or 5</ns:nodeLevel>             <!-- 3=Agreement, 5=Subscriber -->
    <ns:nodeId>pOuId/pSubId/cOuId/cSubId</ns:nodeId>
    <ns:requestedDate>DateTime.now()</ns:requestedDate>
    <ns:requestedBy>orderRequest.OrderData.Channel</ns:requestedBy>
    <ns:futureType>FUTSOC</ns:futureType>           <!-- Static -->
    <!-- ExtendedInfo elements (see §8.4) -->
  </ns:futureOrder>

  <ns2:futureSocs>
    <ns2:futureSoc>
      <ns2:code>offer.Soc</ns2:code>
      <ns2:expireDate>EXP_DATE_VALUE</ns2:expireDate>
      <!-- ns2:parameter[]: ParameterInfo elements -->
      <!-- ns2:childSoc[]: RelatedOffersArray elements -->
      <ns2:type>ServiceType</ns2:type>
      <ns2:subType>[CUG|CONTRACT|IDD|IR|DISCOUNT|FUTSOC]</ns2:subType>
      <!-- ns2:extendedInfo[]: filtered by FutureSocExtended_Exclude_Record -->
      <ns2:socPrice>OfferRate</ns2:socPrice>  <!-- Subscriber only -->
      <ns2:socName>OfferName</ns2:socName>
    </ns2:futureSoc>
  </ns2:futureSocs>
</ns3:futureOrderWithSoc>
```

### subType Classification (xsl:choose — priority order)

| Condition | subType |
|-----------|---------|
| `CUG_IND=Y` in SocProperties | `CUG` |
| `TR_CONTRACT_IND=Y` in SocProperties | `CONTRACT` |
| `TR_IDD_FLAG=Y` in SocProperties | `IDD` |
| `TR_IR_FLAG=Y` in SocProperties | `IR` |
| `ServiceType = '68'` | `DISCOUNT` |
| otherwise | `FUTSOC` |

### ExtendedInfo in ns:futureOrder — Subscriber Variant

| ns:name | ns:value source | Condition |
|---------|----------------|-----------|
| POU_ID | pOuId | string-length(pOuId) > 0 |
| CUS_ID | custId | string-length(custId) > 0 |
| SUB_ID | pSubId | string-length(pSubId) > 0 |
| MOBILE_NO | msisdn | string-length(msisdn) > 0 |
| PROVISIONING | "N" | LOGICALDATE_PROV ExtendedInfo exists on offer |
| SBM_PROVISIONING | "N" | SBM_NO_PROVISIONING ExtendedInfo exists on offer |
| USE_NEW_BILL_CYCLE | offer.ExtendedInfo[USE_NEW_BILL_CYCLE]/Value | Exists |
| DMC_TRX_ID | offer.ExtendedInfo[DMC_TRX_ID]/Value | Exists |
| RELATED_ORDER | ExtendedInfo[RELATED_ORDER] values | for-each loop |
| SBM_CHANNEL | orderRequest.ExtendedInfo[SBM_CHANNEL]/Value | Exists |
| PAY_CHANNEL_ID_SECONDARY | psub.PayChannelIdSecondary | Exists |
| CLM_CampaignID | orderRequest.ExtendedInfo[CLM_CampaignID]/Value | Exists |
| CLM_CampTransID | orderRequest.ExtendedInfo[CLM_CampTransID]/Value | Exists |
| CLM_Current_CampaignID | orderRequest.ExtendedInfo[CLM_Current_CampaignID]/Value | Exists |
| CLM_Source | orderRequest.ExtendedInfo[CLM_Source]/Value | Exists |
| ASSET_ID | psub.AssetCrmId | string-length > 0 |

---

## §10 — XSLT Field Mapping — Output XML Tree (Subscriber Variant)

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                     [Conditional]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId           [Conditional]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID                 [Conditional]
    ├── RefID                    ← concat(subRefId, ":", psof.Soc)                 [Always]
    ├── UserName / PassWord / OrderType ← $orderRequest/OrderData/...              [Conditional]
    └── payload
        └── ns3:futureOrderWithSoc
            ├── ns:futureOrder
            │   ├── ns:effectiveDate   ← futOrderDate (LOGICALDATE_PROV=B) or psof.EffectiveDate  [Conditional]
            │   ├── ns:status          ← "1"                                       [Always]
            │   ├── ns:orderType       ← paramOrderType or "3" (Subscriber default) [Always]
            │   ├── ns:nodeLevel       ← "5" (Subscriber)                          [Always]
            │   ├── ns:nodeId          ← pSubId (MapSubscriberIdFromCRM)            [Conditional]
            │   ├── ns:requestedDate   ← DateTime.now()                            [Always]
            │   ├── ns:requestedBy     ← orderRequest.OrderData.Channel            [Always]
            │   ├── ns:futureType      ← "FUTSOC"                                  [Always]
            │   └── ns:extendedInfo[]  ← see §9 ExtendedInfo table                [Conditional each]
            └── ns2:futureSocs
                └── ns2:futureSoc
                    ├── ns2:code          ← psof.Soc                               [Always]
                    ├── ns2:effectiveDate  ← psof.EffectiveDate                    [Conditional]
                    ├── ns2:expireDate     ← ExtendedInfo[EXP_DATE_VALUE]/Value    [Conditional]
                    ├── ns2:parameter[]*  ← ParameterInfo (ParamName/ValuesArray)  [Conditional]
                    ├── ns2:childSoc[]*   ← RelatedOffersArray (Soc, params, type, name) [Conditional]
                    ├── ns2:type          ← psof.ServiceType                       [Conditional]
                    ├── ns2:subType       ← SocProperties → CUG/CONTRACT/IDD/IR/DISCOUNT/FUTSOC [Always]
                    ├── ns2:extendedInfo[]* ← ExtendedInfo (excluding Exclude_Record list) [Conditional]
                    ├── ns2:socPrice      ← psof.OfferRate                         [Conditional: Subscriber only]
                    └── ns2:socName       ← psof.OfferName                         [Conditional]
```

---

## §11 — Audit Logging

| Phase | AUDIT_TRACE | PROCESS_ID |
|-------|-------------|------------|
| Request sent (per offer) | `Request Sent for OMX_ADD_FUT_OFFER` | `concat($pid, "_REQ")` |
| Response received | `Response received for OMX_ADD_FUT_OFFER` | `concat($pid, "_RES")` |

> Audit log is emitted per offer, not once for the whole activity. Each send has its own `pid = System.nanoTime()`.

---

## §12 — Activity Status Management

| Condition | Status | Additional action |
|-----------|--------|------------------|
| At least one request sent | `GetActivityStatusString("1", false)` | `SendDataToDB(orderRequest)` — persists order state |
| No offers sent | [SKIPPED] | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception | Error state | `HandleActivityException(...)` |

> **Note:** This rule calls `SendDataToDB(orderRequest)` on success — unlike most OMXFM rules which do not persist to DB. This ensures the future order IDs written back by the response rulefunction are durable.

---

## §15 — Function Dependency Tree

```text
Request_OMX_ADD_FUT_OFFER (rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()  [resubmit purge]
├── Instance.getByExtIdByUri(NextActivityName)                     [next activity PreExecCheck]
├── GetActivityParamValueFromKey(orderCurrentActivity, "ORDERTYPE") [Malinee: prepaid param]
├── GetActivityParameterValueFromKey(..., "USE_ROWID_CRM")         [subscriber ID mapping]
├── MapSubscriberIdFromCRM(psub, useRowIdCrmParam)                 [get nodeId for subscriber]
├── (per offer loop)
│   ├── XPath.evalAsString()                                       [read FE_OR_CCBS filter]
│   ├── GetXMLForAgreementOfferFilterWithExtendedInfo()            [XML for PreExecCheck]
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo()           [XML for PreExecCheck]
│   ├── XPath.execute()                                            [evaluate PreExecCheck]
│   ├── DateTime.addDay(offer.EffectiveDate, 1)                    [Wattanachai futOrderDate]
│   ├── Event.createEvent(xslt://OMX_ADD_FUTURE)                   [build futureOrderWithSoc]
│   └── Event.Ext.sendEventImmediate()                             [dispatch JMS]
├── GetActivityStatusString("1", false)                            [set IN_PROGRESS]
├── SendDataToDB(orderRequest)                                     [persist order state]
├── SkipActivity(orderRequest, orderCurrentActivity, "4")          [skip path]
└── HandleActivityException()                                      [error path]

Response_OMX_ADD_FUT_OFFER (rulefunction)
├── Instance.createInstance(xslt://OMX_AddFutureRes)               [create response concept]
├── XPath.evalAsString() × 3                                        [FUT_ORDER_ID, nodeId, soc]
├── (subscriber loop)
│   └── Instance.createInstance(xslt://SubscriberOffersExtendedInfo) [write FUT_ORDER_ID back]
│       → subOffer.ExtendedInfo[FUT_ORDER_ID] = futOrderId
├── Event.Ext.sendEventImmediate()                                  [response audit log]
└── XPath.evalAsInt()                                               [count 000 responses → fan-in]
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | Must submit one JMS request per eligible offer (per RefID); fan-in on all 000 responses | [HIGH] |
| R2 | RefID = `{agreementRefId|subRefId}:{soc}` must be preserved for correlation | [HIGH] |
| R3 | FUT_ORDER_ID from response must be written back as SubscriberOffer ExtendedInfo | [HIGH] |
| R4 | subType classification (CUG/CONTRACT/IDD/IR/DISCOUNT/FUTSOC) must match SocProperties | [HIGH] |
| R5 | Resubmit path: purge pending requests and suppress RequestCount increment | [MEDIUM] |
| R6 | Wattanachai futOrderDate=EffectiveDate+1 when LOGICALDATE_PROV=B | [MEDIUM] |
| R7 | FutureSocExtended_Exclude_Record exclusion list must be configurable from global variables | [MEDIUM] |
| R8 | `SendDataToDB` call must be preserved — future order IDs must be persisted | [MEDIUM] |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| 4 XSLT variants (ParentOU/ChildOU × Agreement/Subscriber) with subtle differences — divergence risk | [HIGH] | Generate from a single parameterized template; test all 4 paths |
| nodeId mapping via USE_ROWID_CRM parameter — CRM data dependency | [MEDIUM] | Document CRM row ID vs subscriber ID mapping in migration |
| Also reads NEXT activity PreExecCheck — runtime XPath evaluation | [MEDIUM] | Compile and validate XPath at load time in modern platform |

---

## §19 — Response Message Rule

### §19.1 Overview

`Response_OMX_ADD_FUT_OFFER.rulefunction` handles the asynchronous reply from OMX FM.
It creates an `OMX_AddFutureRes` concept (not the generic ResponseBase), extracts the assigned
`FUT_ORDER_ID` from the response, writes it back as ExtendedInfo on the matching SubscriberOffer,
then drives fan-in completion.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order data — subscriber offers updated with FUT_ORDER_ID |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` | JMS response from OMX FM |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] array, RequestCount |

### §19.3 Response Concept Construction (OMX_AddFutureRes)

```text
createObject                          ← extId = OMXUtils.generateTrackingID()   [Always]
└── OMX_AddFutureRes
    ├── @Id                           ← $eventResponse/RefID                    [Conditional]
    ├── ResponseCode                  ← $eventResponse/ResponseCode             [Conditional]
    ├── ResponseMessage               ← $eventResponse/ResponseMsg              [Conditional]
    └── CompletionStatus              ← $eventResponse/CompletionStatus         [Conditional]
```

> Uses `Concepts.FM.Response.OMX_AddFutureRes` (not the generic `ResponseBase`). The `@Id` attribute (set to RefID) enables the per-offer correlation lookup.

### §19.4 FUT_ORDER_ID Writeback

| Extracted field | XPath | Action |
|----------------|-------|--------|
| futOrderId | `xsd4:AddFutureOrderResponse/xsd4:FUT_ORDER_ID` | Written back as `SubscriberOffers.ExtendedInfo[FUT_ORDER_ID]` |
| nodeId | `xsd4:AddFutureOrderResponse/xsd4:nodeId` | Used to find matching subscriber (SubscriberId == nodeId) |
| soc | `xsd4:AddFutureOrderResponse/xsd4:soc` | Used to find matching offer (Soc == soc) |

> **Warning:** Writeback only searches ParentOU subscribers — ChildOU subscribers are not searched. If future orders are placed for ChildOU subscriber offers, their FUT_ORDER_ID will not be written back.

### §19.5 Response Completion Logic

```java
int successResponseCount = XPath.evalAsInt(
  "count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = '000'])"
);
if (currActivity.RequestCount == successResponseCount) {
    return "true";   // All parallel future-order requests succeeded → advance
} else {
    return "false";  // Still waiting for more responses
}
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
