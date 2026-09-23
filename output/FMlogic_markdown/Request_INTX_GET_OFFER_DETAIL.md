# Request_INTX_GET_OFFER_DETAIL

> Fetch offer descriptions from INTX and enrich working-memory offers with ThaiName/EngName/BILL_DESCRIPTION — SOC-deduplication then parallel fan-out, one request per unique SOC

**Author:** (not specified) | **Priority:** 5 | **forwardChain:** true | **Pattern:** SOC deduplicate → sendEventImmediate per unique SOC | **Type:** Enrichment/Lookup FM

---

## §1 — Overview & Purpose

> **Enrichment FM:** This rule does NOT update a backend system — it fetches offer description data from INTX and writes it back into the working-memory `OrderRequest` concept. It is a lookup/enrichment pattern: subsequent order steps (e.g., SMS notifications) can then read `offer.ThaiName`, `offer.EngName`, and `offer.ExtendedInfo[Name="BILL_DESCRIPTION"]` without calling INTX again.

The rule collects a **deduplicated set of unique SOC codes** from all qualifying offers across four entity scopes (POU Agreement, POU Subscriber, COU Agreement, COU Subscriber). It then dispatches one `INTX_GET_OFFER_DETAIL` event per unique SOC (parallel fan-out). The response RF receives each INTX reply, extracts the offer name and multi-line bill description, and writes them back into every matching offer in the working-memory hierarchy.

> **Used in POSTPAID_UPDATE_PARAMETER step 36** — enriches offers with INTX descriptions ahead of the SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE notification step.

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_OFFER_DETAIL` |
| Outbound event | `Events.OMConsumers.OMXFM.Request.INTX_GET_OFFER_DETAIL` |
| Response event | `Events.OMConsumers.OMXFM.Response.INTX_GET_OFFER_DETAIL` |
| Payload root | `ns4:GetOfferDetailReq` (GetOfferDetail.xsd) |
| Response namespace | `xsd2 = http://…/ESB/INTX/GetOfferDetail.xsd` |
| Response concept | `Concepts.FM.Base.ResponseBase` |
| Dispatch pattern | SOC deduplication → sendEventImmediate per unique SOC |
| resubmit refId key | `offer.Soc` (SOC code directly, not SubRefId:Soc) |
| Resubmit purge | `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()` |
| Written back to concept | `offer.ThaiName`, `offer.EngName`, `offer.ExtendedInfo[BILL_DESCRIPTION]` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Note |
|-----------|-------|------|
| priority | 5 | Standard FM request priority |
| forwardChain | true | Allows further rule evaluation after execution |
| Author | (none) | Empty @description block — no @author tag |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order — READ for offer traversal; WRITTEN with ThaiName/EngName/BILL_DESCRIPTION enrichment |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — Status, RequestCount, Response[], PreExecCheck |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity position match |
| 2 | `orderCurrentActivity.ActivityID == "INTX_GET_OFFER_DETAIL"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "INTX_GET_OFFER_DETAIL"` | Redundant dual binding |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Fires only when awaiting execution |

---

## §5 — Execution Flow

1. **Resubmit detection** — `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. **Resubmit purge** — if resubmit: `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
3. **SOC collection phase** — Create empty `ArrayList socList`; traverse POU Agreement → POU Subscriber → COU Agreement → COU Subscriber offers; for each qualifying offer: add `offer.Soc` to socList if not already present
4. **Dispatch phase** — Convert socList to array; loop unique SOCs; for each: build event with classify logic; `sendEventImmediate`; increment RequestCount; audit log
5. **Dispatch or skip** — if any events sent: INPROGRESS → `SendDataToDB()`; else `SkipActivity("4")`
6. **Exception handling** — catch all → `HandleActivityException()`

---

## §6 — Rule Action (THEN) — Detailed Logic

### SOC Collection — Phase 1 (all scopes)

| Scope | Loop | PreExecCheck Helper | SOC Added |
|-------|------|---------------------|-----------|
| POU Agreement | `pagr.Offers[paof]` | `GetXMLForAgreementOfferFilterWithExtendedInfo(orderRequest, pAgrRefId, offer.Soc, filter)` | `offer.Soc` if not already in list |
| POU Subscriber | `psub.SubscriberOffers[psof]` | `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, offer.Soc, filter)` | `offer.Soc` if not already in list |
| COU Agreement | `cagr.Offers[caof]` | `GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo(orderRequest, pAgrRefId, offer.Soc, pOuRefId, filter)` | `offer.Soc` if not already in list |
| COU Subscriber | `csub.SubscriberOffers[csof]` | `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, cSubRefId, offer.Soc, pOuRefId, filter)` | `offer.Soc` if not already in list |

> **Deduplication:** `Collections.contains(socList, offer.Soc)` ensures each SOC code appears at most once in the dispatch list. One INTX request per SOC; one response enriches all matching offers.

> **[MEDIUM] cOuId loaded (line 121) but never used** — assigned but not referenced in logic or XSLT.

> **[MEDIUM] PurgePendingRequestsBeforeResubmit used but dispatch is NOT IntraActivitySequencing** — this helper is designed for sequenced activities. Dispatch here is direct `sendEventImmediate`. Using this helper may cause unexpected behavior on resubmit.

---

## §8 — System & Integration Dependencies

### §8.1 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.INTX_GET_OFFER_DETAIL` | Per-unique-SOC offer detail lookup (parallel fan-out) |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.INTX_GET_OFFER_DETAIL` | INTX offer detail with name/description fields |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | Audit log per dispatched SOC event and per response |

### §8.2 — Backend API Details

| System | Operation | Schema | Protocol |
|--------|-----------|--------|----------|
| INTX | GetOfferDetail | `ns4:GetOfferDetailReq` / `ns4:GetOfferDetailRes` (GetOfferDetail.xsd) | JMS / TIBCO EMS |

### §8.3 — BE Working Memory Write-Back (Enrichment)

| Scope | Field Written | Source (from INTX response) |
|-------|--------------|------------------------------|
| POU Agreement Offers | `offer.ThaiName` | `xsd2:billDescription/xsd2:thaiLine1` |
| POU Agreement Offers | `offer.EngName` | `xsd2:billDescription/xsd2:englishLine1` |
| POU Subscriber Offers | `offer.ThaiName`, `offer.EngName` | Same as above |
| POU Subscriber Offers | `offer.ExtendedInfo[Name="BILL_DESCRIPTION"]` | Language-aware concat of up to 3 billDescription lines |
| COU Agreement Offers | `offer.ThaiName`, `offer.EngName` | Same as POU Agreement |
| COU Subscriber Offers | All 3 fields | Same as POU Subscriber |

### §8.4 — CustomerTypeInfo/Type → ns4:classify mapping

| CustomerTypeInfo/Type | ns4:classify value | Notes |
|-----------------------|--------------------|-------|
| `80` | `PRE` | Prepaid |
| `66`, `67`, `73` | `POST` | Postpaid variants |
| Any other value | *(not emitted)* | Element absent — INTX may default or reject |

### §8.5 — Global Variable Dependencies

| Path | Used For |
|------|---------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Guards UserName/PassWord in JMS event |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Gates payload copy in audit log |

---

## §10 — XSLT Field Mapping — Request Event XML Tree

Single XSLT variant — params: `orderRequest, soc, globalVariables`. No per-entity subscriber variable needed.

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                   [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId         [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                [Conditional]
    ├── RefID                ← $soc                                           [Always — SOC code]
    ├── UserName             ← $orderRequest/OrderData/User                   [Conditional: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password               [Conditional: IsEnableUserPass='true']
    ├── OrderType            ← $orderRequest/OrderData/OrderType              [Conditional]
    └── payload                                                                [Always]
        └── ns4:GetOfferDetailReq
            ├── ns4:correlatedId   ← $orderRequest/OrderData/OMXTrackingId   [Conditional]
            ├── ns4:offerCode      ← $soc                                     [Always]
            └── ns4:classify       [xsl:choose]
                ├── when CustomerTypeInfo/Type='80'       → 'PRE'
                ├── otherwise: if Type='66' OR '67' OR '73' → 'POST'
                └── other types → element not emitted
```

---

## §11 — Audit Logging

| Scope | OPERATION_NAME | AUDIT_TRACE | Note |
|-------|---------------|-------------|------|
| Per-SOC Request | INTX_GET_OFFER_DETAIL | "Request Sent for INTX_GET_OFFER_DETAIL" | Unconditional; static trace |
| Response | INTX_GET_OFFER_DETAIL | "Response received for INTX_GET_OFFER_DETAIL" | Consistent with request |

---

## §12 — Activity Status Management

| Condition | Status | Call |
|-----------|--------|------|
| At least one SOC event dispatched | INPROGRESS | `GetActivityStatusString("1", false)` → `SendDataToDB()` |
| No qualifying SOC codes found | SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception caught | ERROR | `HandleActivityException()` |

---

## §15 — Function Dependency Tree

```text
Request_INTX_GET_OFFER_DETAIL.rule
├── Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()   [if isActResub — MEDIUM: wrong helper for non-sequenced dispatch]
├── Collections.List.createArrayList()                              [socList]
│
├── [SOC Collection — POU Agreement]
│   ├── XPath.evalAsString(FE_OR_CCBS) → filter
│   ├── GetXMLForAgreementOfferFilterWithExtendedInfo(...)
│   ├── XPath.execute("/("+chkXPath+")", sXML, ...)
│   └── Collections.contains/add → socList
│
├── [SOC Collection — POU Subscriber]
│   ├── XPath.evalAsString(FE_OR_CCBS) → filter
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo(...)
│   ├── XPath.execute("/("+chkXPath+")", sXML, ...)
│   └── Collections.contains/add → socList
│
├── [SOC Collection — COU Agreement]
│   ├── XPath.evalAsString(FE_OR_CCBS) → filter
│   ├── GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo(...)
│   ├── XPath.execute("/("+chkXPath+")", sXML, ...)
│   └── Collections.contains/add → socList
│
├── [SOC Collection — COU Subscriber]
│   ├── XPath.evalAsString(FE_OR_CCBS) → filter
│   ├── GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...)
│   ├── XPath.execute("/("+chkXPath+")", sXML, ...)
│   └── Collections.contains/add → socList
│
├── Collections.toArray(socList)
├── [Dispatch loop — per unique SOC]
│   ├── Event.createEvent("xslt://INTX_GET_OFFER_DETAIL")   [single variant]
│   ├── Event.Ext.sendEventImmediate() → INTX_GET_OFFER_DETAIL
│   └── Event.Ext.sendEventImmediate() → Logger
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB()
├── RuleFunctions.Helpers.SkipActivity()
└── RuleFunctions.Helpers.HandleActivityException()

Response_INTX_GET_OFFER_DETAIL.rulefunction
├── OMXUtils.generateTrackingID()
├── Instance.createInstance("xslt://ResponseBase")
│   ├── ResponseCode, ResponseMessage (←ResponseMsg), CompletionStatus, ReferenceId (←RefID)
├── currActivity.Response[Response@length] = activityRes
├── XPath.evalAsString(xsd2:offerDetailInfo/xsd2:code)          → soc
├── XPath.evalAsString(xsd2:billDescription/xsd2:thaiLine1)     → thaiDesc
├── XPath.evalAsString(xsd2:billDescription/xsd2:englishLine1)  → engDesc
├── [Write-back — POU Agreement: offer.ThaiName, offer.EngName]
├── [Write-back — POU Subscriber]
│   ├── offer.ThaiName, offer.EngName
│   ├── if Language="EN": fetch englishLine2+3 → build billDesc
│   ├── else: fetch thaiLine2+3 → build billDesc
│   └── Instance.createInstance("xslt://SubscriberOffersExtendedInfo") {BILL_DESCRIPTION}
│       → offer.ExtendedInfo[offer.ExtendedInfo@length]
├── [Write-back — COU Agreement: ThaiName, EngName]
├── [Write-back — COU Subscriber: ThaiName, EngName, BILL_DESCRIPTION ExtendedInfo]
├── Event.Ext.sendEventImmediate() → Logger
├── XPath.evalAsInt(count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)="000"]))
└── if(RequestCount == successResponseCount) → "true" else → "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Collect unique SOC codes from all qualifying offers across POU Agreement, POU Subscriber, COU Agreement, COU Subscriber |
| R2 | Dispatch one `INTX_GET_OFFER_DETAIL` request per unique SOC (not per entity) — parallel fan-out |
| R3 | Send `ns4:classify = "PRE"` for Type 80; `"POST"` for Types 66/67/73; omit element for other types |
| R4 | On response: write `offer.ThaiName` and `offer.EngName` to ALL matching offers (all scopes) |
| R5 | On response: build language-aware multi-line bill description (up to 3 lines, space-separated) for Subscriber offers |
| R6 | Language: if `Subscriber.SubscriberGeneralInfo.Language == "EN"` → englishLine1+2+3; else → thaiLine1+2+3 |
| R7 | Append BILL_DESCRIPTION as `offer.ExtendedInfo[Name="BILL_DESCRIPTION"]` (Subscriber offers only) |
| R8 | Fan-in: all-success (RequestCount == count of responses with ResponseCode suffix "000") |

### Design Risks

| Risk | Severity | Detail | Mitigation |
|------|----------|--------|-----------|
| PurgePendingRequestsBeforeResubmit on non-sequenced activity | [MEDIUM] | Helper is designed for IntraActivitySequencing patterns; dispatch here is direct `sendEventImmediate`. May produce unexpected behavior on resubmit. | Remove the purge call; rely on SOC-level resubmit guard in collection phase |
| cOuId loaded but never used | [MEDIUM] | Line 121: assigned but not referenced | Remove dead assignment |
| classify not emitted for unlisted CustomerTypeInfo values | [MEDIUM] | Types not in {66, 67, 73, 80} → no `ns4:classify`. INTX may fail to categorize. | Add default or document acceptable omission |
| Write-back races with parallel fan-in | [MEDIUM] | Response RF modifies `OrderRequest` concept in-place. Concurrent writes to same offer from multiple INTX responses may have undefined ordering. | Ensure BE processes response RF events single-threaded per concept, or add locking |
| Comment mismatch in response RF | [LOW] | Line 110-111: `/*** Begin ParentOU Subscriber Offer ***/` should be `End` | Minor comment fix |
| No author attribution | [LOW] | Empty @description block | Add author tag |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_OFFER_DETAIL {
    attribute { priority = 5; forwardChain = true; }
    declare { Concepts.OrderRequest.OrderRequest orderRequest; Concepts.OM.ProcessConfig.Activity orderCurrentActivity; }
    when { /* activityId + status WAITING guards */ }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Activity nextAct = Instance.getByExtIdByUri(...);
            String chkXPath = nextAct.PreExecCheck;
            boolean isSkipped = true;

            if(isActResub) { IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity); }
            // [MEDIUM: inappropriate for non-sequenced dispatch]

            Object socList = Collections.List.createArrayList();

            for (int p = 0; p < pOuLen; p++) {
                // POU Agreement Offers → collect SOC if PreExecCheck passes & not resubmit-done
                // [GetXMLForAgreementOfferFilterWithExtendedInfo → XPath chkXPath → Collections.contains/add]

                // POU Subscriber Offers → collect SOC
                // [GetXMLForSubscriberOfferFilterWithExtendedInfo → XPath chkXPath → Collections.contains/add]

                for (int c = 0; c < cOuLen; c++) {
                    String cOuId = ...;  // [MEDIUM: unused]
                    // COU Agreement Offers → collect SOC
                    // [GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo → XPath chkXPath → Collections.contains/add]
                    // COU Subscriber Offers → collect SOC
                    // [GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo → XPath chkXPath → Collections.contains/add]
                }
            }

            // Dispatch: one event per unique SOC
            Object[] socs = Collections.toArray(socList);
            for(int i = 0; i < socs@length; i++) {
                String soc = socs[i];
                // Event built with single XSLT (see §10): RefID=$soc, ns4:offerCode=$soc, ns4:classify per CustomerTypeInfo/Type
                Event.Ext.sendEventImmediate(reqEvent);
                if(!isActResub) orderCurrentActivity.RequestCount++;
                isSkipped = false;
                Event.Ext.sendEventImmediate(/* Logger: OPERATION_NAME="INTX_GET_OFFER_DETAIL" */);
            }

            if(!isSkipped) { GetActivityStatusString("1", false); SendDataToDB(orderRequest); }
            else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
        } catch (Exception ae) { HandleActivityException(...); }
    }
}
```

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_INTX_GET_OFFER_DETAIL.rulefunction` — unique among OMXFM response RFs: in addition to standard ResponseBase creation and fan-in, it extracts offer descriptions from the INTX payload and **writes them back into every matching offer in the working-memory OrderRequest concept**.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order — READ for offer matching; WRITTEN with enrichment data |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.INTX_GET_OFFER_DETAIL` | Inbound INTX offer detail response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] array target |

### §19.3 — ResponseBase Concept Construction

```text
createObject
└── object @extId ← OMXUtils:generateTrackingID()    [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode    [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg     [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId         ← $eventResponse/RefID           [Conditional] [Correctly mapped]
```

### §19.4 — Response Data Extraction (INTX payload)

| Variable | XPath | Used for |
|----------|-------|---------|
| `soc` | `xsd2:offerDetailInfo/xsd2:code` | Matches against all offer.Soc |
| `thaiDesc` | `xsd2:billDescription/xsd2:thaiLine1` | `offer.ThaiName` + base Thai billDesc |
| `engDesc` | `xsd2:billDescription/xsd2:englishLine1` | `offer.EngName` + base English billDesc |
| `thaiDesc2/3` | `xsd2:thaiLine2` / `xsd2:thaiLine3` | Thai path (Subscriber scopes only) |
| `engDesc2/3` | `xsd2:englishLine2` / `xsd2:englishLine3` | English path (Subscriber scopes only) |

### §19.5 — BILL_DESCRIPTION Build Logic (Subscriber Scopes)

```text
billDesc = ""
if Language == "EN":
    fetch englishLine2, englishLine3
    if not blank(engDesc)  → billDesc += engDesc
    if not blank(engDesc2) → billDesc += " " + engDesc2 (if billDesc not empty)
    if not blank(engDesc3) → billDesc += " " + engDesc3
else:
    fetch thaiLine2, thaiLine3
    if not blank(thaiDesc)  → billDesc += thaiDesc
    if not blank(thaiDesc2) → billDesc += " " + thaiDesc2
    if not blank(thaiDesc3) → billDesc += " " + thaiDesc3

→ Create SubscriberOffersExtendedInfo {Name="BILL_DESCRIPTION", Value=billDesc}
→ offer.ExtendedInfo[offer.ExtendedInfo@length] = subOfferExtended
```

### §19.6 — Fan-in Completion Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

```java
if(currActivity.RequestCount == successResponseCount)
    return "true";
else
    return "false";
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
