# Request_SBM_FUP_CHANGE_CAP_MAX

> Changes FUP (Fair Usage Policy) CAP MAX on SBM per qualifying subscriber offer — ADD or REMOVE mode; per-offer fan-out across POU and COU subscribers in FUP groups.

**Backend:** SBM (FUP doService) | **Pattern:** Per-offer fan-out | **forwardChain:** true | **Author:** RS33-BANDIT | **Used in step:** 50

---

## §1 Overview & Purpose

Sends a **SBM FUP DoService** call per qualifying subscriber offer to add or remove a CAP MAX SOC on the SBM Fair Usage Policy system. The operation mode (ADD or REMOVE) is controlled by the activity's `Parameter[0]` value.

- Traverses **POU Subscribers + COU Subscribers → SubscriberOffers** — per-offer fan-out
- **FUP group gate:** subscriber skipped entirely unless at least one offer has `SPECIAL_OFFER_INDICATOR = FSH or FPL` on the subscriber OR on the OU `Agreement.Offers`
- **param gate:** `Parameter[0]` must be "ADD" or "REMOVE" — throws `DATA_ISSUE` if missing
- **filter:** `FE_OR_CCBS` ExtendedInfo value passed to PreExecCheck helper
- **Underlying event:** `SBM_FUP_DO_SERVICE` (generic SBM service call, not named after the activity)
- **fupID:** OU account ID (`pOuId` / `cOuId`), not subscriber MSISDN

> **[HIGH] POU offerRefId double colon bug:** POU RefID constructed as `pOuRefId + ":" + ":" + refId + ":" + offer.Soc` — produces a double colon `::` in the middle (empty ChildOU segment). COU correctly uses `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.Soc`. The POU resub guard and response correlation use this same offerRefId, so they are self-consistent but the format is non-standard.

> **[MEDIUM] socCapmax vs socCapMax key casing mismatch:** POU sends key `socCapmax` (lowercase m); COU sends key `socCapMax` (uppercase M). If SBM treats parameter keys case-sensitively, one variant may be silently ignored.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_SBM_FUP_CHANGE_CAP_MAX.rule` | 172 lines |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_SBM_FUP_CHANGE_CAP_MAX.rulefunction` | 28 lines |
| Author | RS33-BANDIT | |
| Priority | 5 | |
| forwardChain | true | |
| Traversal unit | POU Subscriber + COU Subscriber → SubscriberOffers | Per-offer fan-out |
| Backend event | `Events.OMConsumers.OMXFM.Request.SBM_FUP_DO_SERVICE` | Generic SBM FUP service event |
| Schema NS | `http://services.omx.truecorp.co.th/FMServices/SBMFUPDoserviceRequest` | `ns:` prefix |
| Parameter[0] | ADD or REMOVE | Mandatory — throws DATA_ISSUE if absent |
| FUP gate | `SPECIAL_OFFER_INDICATOR = FSH or FPL` | On sub SubscriberOffers OR OU Agreement.Offers |
| PreExecCheck builder (POU) | `GetXMLForSubscriberOfferFilterWithExtendedInfo` | filter = FE_OR_CCBS value |
| PreExecCheck builder (COU) | `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo` | filter = FE_OR_CCBS value |
| isActResub | `RequestCount > 0 && IsOrderResubmitted` | → PurgePendingRequestsBeforeResubmit; suppresses RequestCount++ |
| Per-offer resub guard | `CompletionStatus==2 && ReferenceId==offerRefId` | Skips already-successful offers |
| Skip condition | `isSkipped == true` after loop | SkipActivity("4") |
| Post-loop | Status="1" + SendDataToDB | Called once after full traversal |
| Dispatch | `Event.Ext.sendEventImmediate` | Per-offer immediate send |
| Fan-in | `RequestCount == successResponseCount` | success = ResponseCode ends in "000" |

---

## §3 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "SBM_FUP_CHANGE_CAP_MAX"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SBM_FUP_CHANGE_CAP_MAX"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §4 FUP Group Gate (SPECIAL_OFFER_INDICATOR)

Before iterating any offer, each subscriber is checked to confirm they belong to a FUP group:

```xpath
exists($sub/SubscriberOffers[ExtendedInfo[Name = "SPECIAL_OFFER_INDICATOR"
    and (Value="FSH" or Value="FPL")]])
OR
exists($currPOU/Agreement/Offers[ExtendedInfo[Name = "SPECIAL_OFFER_INDICATOR"
    and (Value="FSH" or Value="FPL")]])
```

For COU, `$currCOU` replaces `$currPOU`. If neither condition is true the entire subscriber's offer loop is skipped.

> **Two sources of FUP membership:** (1) subscriber's own SubscriberOffers contain a FUP indicator SOC; or (2) the parent OU's Agreement-level Offers contain a FUP indicator. The Agreement.Offers path means a subscriber can be in a FUP group even without subscriber-level FUP offers.

---

## §5 Execution Flow

1. Validate `Parameter[0]` = "ADD" or "REMOVE" — throw `DATA_ISSUE` if neither
2. If `isActResub` → `PurgePendingRequestsBeforeResubmit`
3. Read `nextAct.PreExecCheck` and `nextAct.Parameter[0]`; set `isSkipped = true`
4. Loop POU: for each ParentOU → for each Subscriber → FUP gate → for each SubscriberOffers:
   - Build `offerRefId = pOuRefId + ":" + ":" + refId + ":" + offer.Soc` [**double colon BUG**]
   - Read `filter = offer/ExtendedInfo[FE_OR_CCBS]/Value`
   - Resub guard: skip if `Response[ReferenceId==offerRefId && CompletionStatus==2]`
   - Run PreExecCheck via `GetXMLForSubscriberOfferFilterWithExtendedInfo`
   - If "true": `FormatMSISDNPrefix` → build `SBM_FUP_DO_SERVICE` event (fupID=pOuId, socCapmax=offer.OfferName) → `sendEventImmediate`
   - If `!isActResub`: `RequestCount++`; `isSkipped=false`; send audit logger
5. Loop COU: same pattern; `offerRefId` is 4-part correct; `fupID=cOuId`; key = `socCapMax` (capital M)
6. After all loops: if `!isSkipped` → Status="1" + `SendDataToDB`; else → `SkipActivity("4")`

---

## §6 offerRefId Construction

| Scope | Expression | Example | Notes |
|-------|------------|---------|-------|
| POU | `pOuRefId + ":" + ":" + refId + ":" + offer.Soc` | `POU1::SUB1:SOC123` | [HIGH] Double colon — empty ChildOU segment |
| COU | `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.Soc` | `POU1:COU1:SUB1:SOC123` | Correct 4-part key |

---

## §7 function_id Mapping

| Parameter[0] | function_id | Purpose |
|-------------|-------------|---------|
| ADD | `104300011` | Add CAP MAX SOC to FUP subscriber |
| REMOVE | `104300013` | Remove CAP MAX SOC from FUP subscriber |

> If `Parameter[0]` is any other value, exception `DATA_ISSUE: "Param is missing."` is thrown before any loop begins.

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

Any order containing POU or COU subscribers with FUP group membership (`SPECIAL_OFFER_INDICATOR = FSH or FPL`) and a qualifying PreExecCheck. Not order-type specific.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event | Destination | Protocol |
|-----------|-------|-------------|----------|
| [OUTBOUND] | `SBM_FUP_DO_SERVICE` | SBM FUP doService queue | JMS |
| [INBOUND] | `SBM_FUP_DO_SERVICE` response | Response correlation queue | JMS |

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | SBM (Subscriber Base Management — FUP module) |
| Operation | doService (generic SBM service invocation) |
| Schema NS | `http://services.omx.truecorp.co.th/FMServices/SBMFUPDoserviceRequest` |
| Response schema NS | `http://services.omx.truecorp.co.th/FMServices/SBMFUPDoserviceResponse` |
| Correlation | RefID = offerRefId (per-offer unique key) |

### §8.4 BE Working Memory Dependencies

| Concept | Read | Written |
|---------|------|---------|
| OrderRequest | OrderPriority, OMXTrackingId, OrderID, OrderType, Customer | — |
| Activity (nextAct) | PreExecCheck, Parameter[0] | Status, RequestCount, Response[] |
| ParentOU | RefId, OUId, Subscriber[], Agreement.Offers | — |
| ChildOU | RefId, OUId, Subscriber[], Agreement.Offers | — |
| Subscriber | RefId, MSISDN, SubscriberOffers[] | — |
| SubscriberOffers | Soc, OfferName, ExtendedInfo[SPECIAL_OFFER_INDICATOR, FE_OR_CCBS] | — |

### §8.5 ExtendedInfo Fields Required

| Name | Scope | Used for | Required? |
|------|-------|----------|-----------|
| SPECIAL_OFFER_INDICATOR | SubscriberOffers, Agreement.Offers | FUP group gate (FSH or FPL) | Optional (subscriber skipped if absent) |
| FE_OR_CCBS | SubscriberOffers | PreExecCheck filter value | Optional (blank filter if absent) |

---

## §9 Detailed Payload Build (SBM_FUP_DO_SERVICE)

### §9.1 XSLT Parameter Binding

| XSLT param | Bound from (POU) | Bound from (COU) |
|-----------|-----------------|-----------------|
| orderRequest | orderRequest concept | same |
| offerRefId | `pOuRefId+":"+":"+refId+":"+offer.Soc` | `pOuRefId+":"+cOuRefId+":"+sub.RefId+":"+offer.Soc` |
| param | `nextAct.Parameter[0]` ("ADD" or "REMOVE") | same |
| pOuId / cOuId | `pOuId` (ParentOU.OUId) | `cOuId` (ChildOU.OUId) |
| formatMsisdn | `FormatMSISDNPrefix(msisdn, true)` | same |
| offer | SubscriberOffers concept | same |

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                    [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId          [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                 [Conditional]
    ├── RefID                ← $offerRefId                                     [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType               [Conditional]
    └── payload
        └── ns:doServiceRequest
            └── ns:req
                ├── ns:function_id    ← xsl:choose: "104300011" (ADD) | "104300013" (REMOVE)  [Always]
                ├── ns:parameters
                │   ├── ns:item[fupID]
                │   │   ├── ns:key    ← "fupID"                               [Always]
                │   │   └── ns:value  ← $pOuId (POU) / $cOuId (COU)          [Always]
                │   ├── ns:item[msisdn]
                │   │   ├── ns:key    ← "msisdn"                              [Always]
                │   │   └── ns:value  ← $formatMsisdn                         [Always]
                │   └── ns:item[socCapmax/socCapMax]  ← [MEDIUM] casing mismatch
                │       ├── ns:key    ← "socCapmax" (POU) / "socCapMax" (COU) [Always — inconsistent]
                │       └── ns:value  ← $offer/OfferName                      [Always]
                └── ns:service_no     ← $formatMsisdn                         [Always]
```

---

## §11 Audit Logging

| Field | Request | Response |
|-------|---------|---------|
| ESBUUID | OMXTrackingId | OMXTrackingId |
| PROCESS_ID | `concat(pid, "_REQ")` | `concat(pid, "_RES")` |
| OPERATION_NAME | `"SBM_FUP_CHANGE_CAP_MAX"` (hardcoded) | `"SBM_FUP_CHANGE_CAP_MAX"` (hardcoded) |
| TARGET_SYSTEM | OMX_COMMON/Component_Name/OMX_FM | same |
| LOG_LEVEL | MSG_LOG_LEVEL/INFO | MSG_LOG_LEVEL/INFO [Correct] |
| AUDIT_TRACE | `"Request Sent for SBM_FUP_CHANGE_CAP_MAX"` | `"Response received for SBM_FUP_CHANGE_CAP_MAX"` |
| payload | Conditional: WritePayload=true | Conditional: WritePayload=true |

---

## §12 Activity Status Management

| Condition | Status | How set |
|-----------|--------|---------|
| Any offer sent | PROCESSING (1) | `GetActivityStatusString("1", false)` |
| No offers qualify | SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception | ERROR | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §13 Exception Handling

| Exception path | Handler | When triggered |
|---------------|---------|---------------|
| Explicit throw | `Exception.newException("DATA_ISSUE", "Param is missing.", null)` | Parameter[0] not "ADD" or "REMOVE" |
| catch block | `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | Any other exception in try block |

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `PurgePendingRequestsBeforeResubmit(orderCurrentActivity)` | Clears pending requests before resubmit replay |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, soc, filter)` | Builds PreExecCheck XML for POU offer |
| `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, refId, soc, pOuRefId, filter)` | Builds PreExecCheck XML for COU offer |
| `FormatMSISDNPrefix(msisdn, true)` | Normalizes MSISDN with international prefix |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | Marks activity as skipped with code 4 |
| `SendDataToDB(orderRequest)` | Persists order state to database |
| `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | Centralized exception handler |
| `GetActivityStatusString("1", false)` | Resolves "1" to PROCESSING status string |

---

## §15 Function Dependency Tree

```text
Request_SBM_FUP_CHANGE_CAP_MAX (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── param = nextAct.Parameter[0]
├── [if !(param=="ADD" || param=="REMOVE")]: throw DATA_ISSUE
├── [if isActResub]: PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── [POU loop p → s → FUP gate → o]:
│   ├── [FUP gate]: XPath.evalAsBoolean(SPECIAL_OFFER_INDICATOR FSH/FPL on sub or currPOU.Agreement)
│   ├── offerRefId = pOuRefId + ":" + ":" + refId + ":" + offer.Soc  [double colon BUG]
│   ├── filter = XPath.evalAsString(offer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── [Resub guard]: scan Response[] for CompletionStatus==2 && ReferenceId==offerRefId
│   ├── [if !reqSuccess]:
│   │   ├── [if PreExecCheck]: GetXMLForSubscriberOfferFilterWithExtendedInfo(...)
│   │   ├── XPath.execute("/("+chkXPath+")", sXML, ...)
│   │   └── [if "true"]:
│   │       ├── FormatMSISDNPrefix(msisdn, true)
│   │       ├── Event.createEvent(SBM_FUP_DO_SERVICE, XSLT: fupID=pOuId, socCapmax=offer.OfferName)
│   │       ├── Event.Ext.sendEventImmediate(reqEvent)
│   │       ├── [if !isActResub]: RequestCount++
│   │       ├── isSkipped = false
│   │       └── Event.Ext.sendEventImmediate(Logger)
├── [COU loop p → c → s → FUP gate → o]:
│   ├── [Same pattern as POU]
│   ├── offerRefId = pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.Soc  [correct]
│   ├── GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...)
│   └── Event.createEvent(SBM_FUP_DO_SERVICE, XSLT: fupID=cOuId, socCapMax=offer.OfferName)
├── [if !isSkipped]:
│   ├── Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch]: HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_SBM_FUP_CHANGE_CAP_MAX (rulefunction)
├── extId = OMXUtils.generateTrackingID()
├── activityRes = Instance.createInstance(SBM_FUP_DoServiceRes) {
│       extId, ResponseCode, ResponseMessage(←ResponseMsg), CompletionStatus, ReferenceId(←RefID),
│       extra_xml, req_transaction_id, response_message, result_code,
│       result_desc, result_namespace, transaction_id
│   }
├── currActivity.Response[] ← activityRes
├── Event.Ext.sendEventImmediate(Logger: "Response received for SBM_FUP_CHANGE_CAP_MAX")
├── successResponseCount = XPath.evalAsInt(count(Response[tib:right(tib:trim(ResponseCode),3)="000"]))
└── return (RequestCount == successResponseCount) ? "true" : "false"
```

---

## §16 Concept Definitions Referenced

| Concept | Key fields used |
|---------|----------------|
| `Concepts.OrderRequest.OrderRequest` | OrderPriority, OrderData |
| `Concepts.OM.ProcessConfig.Activity` | extId, ActivityID, Status, Parameter[], PreExecCheck, RequestCount, Response[] |
| `Concepts.OrderRequest.OrderElements.ParentOU` | RefId, OUId, Subscriber[], Agreement.Offers |
| `Concepts.OrderRequest.OrderElements.ChildOU` | RefId, OUId, Subscriber[], Agreement.Offers |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, SubscriberOffers[] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Soc, OfferName, ExtendedInfo[SPECIAL_OFFER_INDICATOR, FE_OR_CCBS] |
| `Concepts.FM.Response.SBM_FUP_DoServiceRes` | extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, extra_xml, req_transaction_id, response_message, result_code, result_desc, result_namespace, transaction_id |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | `Parameter[0]` must be "ADD" or "REMOVE" — validated before any processing; failure throws DATA_ISSUE exception. |
| R2 | FUP group gate: skip subscriber entirely unless `SPECIAL_OFFER_INDICATOR = FSH or FPL` on sub's SubscriberOffers OR on OU `Agreement.Offers`. |
| R3 | Per-offer fan-out across POU and COU subscribers; each qualifying offer produces one SBM doService call. |
| R4 | ADD → function_id="104300011"; REMOVE → function_id="104300013". |
| R5 | fupID is the OU account ID (OUId), not the subscriber MSISDN. |
| R6 | MSISDN formatted with international prefix via `FormatMSISDNPrefix(msisdn, true)` for both `msisdn` and `service_no` fields. |
| R7 | Per-offer resub guard: skip offers where `Response[ReferenceId==offerRefId && CompletionStatus==2]`. |
| R8 | Fan-in: all successful responses must equal `RequestCount` (using ResponseCode suffix "000"). |
| R9 | SBM response carries 7 SBM-specific result fields: extra_xml, req_transaction_id, response_message, result_code, result_desc, result_namespace, transaction_id. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| POU offerRefId has double colon: `pOuRefId + ":" + ":" + refId + ":" + offer.Soc` — empty ChildOU segment | [HIGH] | Fix to `pOuRefId + ":" + refId + ":" + offer.Soc` — update response correlation consistently |
| Parameter key casing mismatch: POU sends `socCapmax`, COU sends `socCapMax` — case-sensitive SBM may ignore one | [MEDIUM] | Standardize to single casing; verify SBM parameter key case-sensitivity |
| No SendDataToDB inside the loop — DB persisted only after full traversal | [MEDIUM] | Acceptable if isActResub + resub guard covers replay; consistent with other OMXFM rules |
| FUP gate checks Agreement.Offers at OU level — if Agreement structure absent, all subscribers fail the gate | [LOW] | Ensure Agreement.Offers populated by upstream steps |

---

## §18 Full Source Code

```java
/**
 * @description
 * @author RS33-BANDIT
 */
rule Rules.OMConsumers.OMXFM.Request.Request_SBM_FUP_CHANGE_CAP_MAX {
    attribute {
        priority = 5;
        forwardChain = true;
    }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "SBM_FUP_CHANGE_CAP_MAX";
        orderRequest.ProcessFlow.NextActivityID == "SBM_FUP_CHANGE_CAP_MAX";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);

        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
                orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");

            if(isActResub) {
                RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
            }

            String chkXPath = nextAct.PreExecCheck;
            String param = nextAct.Parameter[0];
            boolean isSkipped = true;

            if (!(String.equals(param,"ADD") || String.equals(param,"REMOVE"))){
                throw Exception.newException("DATA_ISSUE", "Param is missing.", null);
            }

            /***  ParentOU iteration Start ***/
            int pOuLen = orderRequest.OrderData.Customer.ParentOU@length;
            for (int p = 0; p < pOuLen; p++) {
                String pOuRefId = orderRequest.OrderData.Customer.ParentOU[p].RefId;
                String pOuId = orderRequest.OrderData.Customer.ParentOU[p].OUId;
                Concepts.OrderRequest.OrderElements.ParentOU currPOU = ...;
                int pSubLen = ...Subscriber@length;
                for (int s = 0; s < pSubLen; s++) {
                    // Check if SUB in FUP group
                    if(XPath.evalAsBoolean(/* SPECIAL_OFFER_INDICATOR FSH/FPL on sub or currPOU.Agreement */)) {
                        for (int o = 0; o < pSofLen; o++) {
                            String offerRefId = pOuRefId + ":" + ":" + refId + ":" + offer.Soc; // BUG: double colon
                            String filter = XPath.evalAsString(/* offer/ExtendedInfo[FE_OR_CCBS]/Value */);
                            /* resub guard */
                            if(!reqSuccess) {
                                /* PreExecCheck */
                                if(String.equals(chkRes,"true")) {
                                    String formatMsisdn = RuleFunctions.Helpers.FormatMSISDNPrefix(msisdn, true);
                                    /* Event.createEvent(SBM_FUP_DO_SERVICE — see §9 for full XSLT)
                                       fupID=pOuId, msisdn=formatMsisdn, socCapmax=offer.OfferName,
                                       function_id=104300011(ADD)/104300013(REMOVE) */
                                    Event.Ext.sendEventImmediate(reqEvent);
                                    if(!isActResub) { orderCurrentActivity.RequestCount++; }
                                    isSkipped = false;
                                    /* Logger */
                                }
                            }
                        }
                    }
                }
            }
            /***  ChildOU iteration — same pattern; fupID=cOuId; key=socCapMax (capital M) ***/

            if (!isSkipped) {
                orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch (Exception ae) {
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 Response Message Rule (Response_SBM_FUP_CHANGE_CAP_MAX)

### §19.1 Overview

Handles SBM FUP doService responses. Creates `SBM_FUP_DoServiceRes` concept with standard completion fields plus 7 SBM-specific result fields. Fan-in: all responses with ResponseCode suffix "000" must equal RequestCount.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| orderRequest | `Concepts.OrderRequest.OrderRequest` | Order context for logging |
| eventResponse | `Events.OMConsumers.OMXFM.Response.SBM_FUP_DO_SERVICE` | Inbound SBM response event |
| currActivity | `Concepts.OM.ProcessConfig.Activity` | Activity to append response and check fan-in |

### §19.3 SBM_FUP_DoServiceRes Concept Construction

```text
createObject / object
├── @extId          ← OMXUtils.generateTrackingID()                              [Always]
├── ResponseCode    ← $eventResponse/ResponseCode                                [Conditional]
├── ResponseMessage ← $eventResponse/ResponseMsg                                 [Conditional: field rename Msg→Message]
├── CompletionStatus← $eventResponse/CompletionStatus                            [Conditional]
├── ReferenceId     ← $eventResponse/RefID                                       [Conditional]
├── extra_xml       ← .../ns:doServiceReturn/ns:extra_xml                        [Conditional]
├── req_transaction_id ← .../ns:req_transaction_id                               [Conditional]
├── response_message   ← .../ns:response_message                                 [Conditional]
├── result_code        ← .../ns:result_code                                      [Conditional]
├── result_desc        ← .../ns:result_desc                                      [Conditional]
├── result_namespace   ← .../ns:result_namespace                                 [Conditional]
└── transaction_id     ← .../ns:transaction_id                                   [Conditional]
```

### §19.4 Response Completion Logic

| Step | Detail |
|------|--------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` → return "true" (complete) or "false" (pending) |
| Completion signal | "true" = all parallel SBM offers have returned successful response; orchestrator can advance |

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| OPERATION_NAME | `"SBM_FUP_CHANGE_CAP_MAX"` (hardcoded) |
| LOG_LEVEL | MSG_LOG_LEVEL/INFO [Correct] |
| AUDIT_TRACE | `"Response received for SBM_FUP_CHANGE_CAP_MAX"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
