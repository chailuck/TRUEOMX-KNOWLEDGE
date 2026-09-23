# Request_CRM_CREATE_ORDER_PREPAID

> TIBCO BusinessEvents FM Logic Documentation — External OMXFM — JMS → CRM

**Author:** CHAYATORN-PC | **Priority:** 5 | **forwardChain:** true | **File:** `Request_CRM_CREATE_ORDER_PREPAID.rule`

---

## §1 — Overview & Purpose

> **External OMXFM Rule — JMS to CRM backend via OMXFMConnectionRequest channel**
>
> Creates a CRM order for each subscriber in the order hierarchy by sending a `CRMCreateOrderRequest` JMS message to the `CRM_CREATE_ORDER_PREPAID` destination. The rule iterates over both ParentOU subscribers and ChildOU subscribers, sending one request per subscriber. Results (CRM order row ID, asset row ID) are written back to each subscriber concept by the response rulefunction.

| Item | Value |
|------|-------|
| Rule class | `Rules.OMConsumers.OMXFM.Request.Request_CRM_CREATE_ORDER_PREPAID` |
| ActivityID | `CRM_CREATE_ORDER_PREPAID` |
| Author | CHAYATORN-PC |
| Backend | CRM (Siebel/CRM system) |
| Channel | `/Channels/OMXFMConnectionRequest` |
| Destination | `CRM_CREATE_ORDER_PREPAID` |
| Event type | `Events.OMConsumers.OMXFM.Request.CRM_CREATE_ORDER` |
| Schema | `CRMCreateOrderRequest` (CRMCreateOrder.xsd) |
| Loop scope | ParentOU/Subscriber + ChildOU/Subscriber (two nested loops) |
| Response rulefunction | `Response_CRM_CREATE_ORDER_PREPAID` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule type | `rule` | RETE stateful rule |
| priority | 5 | Standard priority |
| forwardChain | true | Re-evaluates if working memory changes |
| Namespace | OMXFM | External — JMS to CRM backend |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Root order; provides subscriber hierarchy, dates, MNP info, customer type |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Current activity; parameters read; RequestCount incremented; Response[] checked for re-sends |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Meaning |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity matches current process step |
| 2 | `orderCurrentActivity.ActivityID == "CRM_CREATE_ORDER_PREPAID"` | This rule fires for the CRM create order step |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CRM_CREATE_ORDER_PREPAID"` | Process flow confirms this step is next |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity has not yet been processed |

---

## §5 — Execution Flow Diagram

1. Set `isActResub = (RequestCount > 0 && IsOrderResubmitted)`. Set `isSkipped = true`.
2. Fetch `nextAct` via `Instance.getByExtIdByUri(NextActivityName, ...)`.
3. **ParentOU/Subscriber loop:** For each ParentOU → each Subscriber:
   - a) Skip if `Response[].ReferenceId == pSubRefId && CompletionStatus == 2` (already responded)
   - b) Per-subscriber PreExecCheck via `GetXMLForSubscriber` + `XPath.execute`
   - c) Extract 14 activity parameters; format dates (Bangkok TZ); detect MNP; guard CustomerTypeInfo
   - d) Build + send `CRMCreateOrderRequest` JMS event → `assertEvent` + `ActionRequestEvent` + `SendFirstRequestEvent`
   - e) `isSkipped = false`; if `!isActResub`: `RequestCount++`
   - f) Audit log (AllowWriteLog-gated, PROCESS_ID `_REQ`)
4. **ChildOU/Subscriber loop:** Same as above using `GetXMLForSubscriberInChildOU(req, cSubRefId, cOuRefId)`
5. If `!isSkipped`: `Status = "1"` (IN_PROGRESS) + `SendDataToDB`. Else: `SkipActivity("4")`.
6. `catch` → `HandleActivityException`.

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### §6.1 Resubmit and Skip-Tracking Pattern

| Variable | Value | Effect |
|----------|-------|--------|
| `isActResub` | `RequestCount > 0 && IsOrderResubmitted` | If true, RequestCount NOT incremented — fan-in counter preserved |
| `isSkipped` | Starts `true`; set `false` when any request sent | Determines whether Status=1 or SkipActivity after loops |
| `reqSuccess` | `Response[].ReferenceId == subRefId && CompletionStatus==2` | Skips subscribers already responded — prevents duplicate sends |

### §6.2 Activity Parameters (via `GetActivityParameterValueFromKey`)

| Parameter | Purpose |
|-----------|---------|
| `command` | CRM operation command (e.g., "Activate", "Preactivate", "Cancel") |
| `orderType` | CRM order type override |
| `listOfRootLineItemAction` | Action for root line items |
| `listOfRootLineItemStatus` | Status for root line items |
| `listOfLineItemAction` | Action for child line items |
| `listOfLineItemStatus` | Status for child line items |
| `mappingValueFrom` | Controls which source is used for value mapping |
| `ignoreBRMS` | Bypasses BRMS-derived fields when "true" |
| `ignoreResourceInfo` | Excludes ResourceInfo block when "true" |
| `ignoreLanguage` | Excludes Language field when "true" |
| `ignoreAssetRowId` | Excludes AssetRowId from CRM payload when "true" |
| `PROJ` | Project/campaign identifier injected into CRM order |
| `mnpPortType` | MNP porting direction ("In"/"Out") — fallback: orderType 57→"In", 60→"Out" |
| `USE_ROWID_CRM` | Controls which subscriber ID field is used via `MapSubscriberIdFromCRM` |

> **[LOW]** `ignoreListOfLineItem` parameter extraction is commented out — partial cleanup.

### §6.3 Date Formatting (Bangkok Timezone)

| Field | Source | TZ Conversion | Format |
|-------|--------|---------------|--------|
| `submissionDateFormat` | `orderRequest.SubmissionDate` | Yes — Asia/Bangkok | `yyyy-MM-dd'T'HH:mm:ss.SSSZ` |
| `l9TmvActDateFormat` | `sub.SubscriberGeneralInfo.l9TmvActDate` | Yes — Asia/Bangkok | `yyyy-MM-dd'T'HH:mm:ss.SSSZ` |
| `ProofDateFormat` | `sub.SubscriberGeneralInfo.ProofDate` | **No** (code commented out) | `yyyy-MM-dd'T'HH:mm:ss.SSSZ` |
| `sysDateFormat` | `DateTime.now()` | Yes — Asia/Bangkok | `yyyy-MM-dd'T'HH:mm:ss.SSSZ` |

> **[MEDIUM]** ProofDate is formatted **without** Bangkok TZ conversion — CRM receives UTC time (~7 hours off).

### §6.4 CustomerTypeInfo Guard

```java
if (orderRequest.OrderData.Customer.CustomerTypeInfo == null ||
    orderRequest.OrderData.Customer.CustomerTypeInfo.Type == 0)
    throw Exception.newException("DATA_ISSUE","CustomerTypeInfo.type not found", null);
```

### §6.5 MNP Port Type Logic

`mnpPortType` is determined when:
- Order-level MNP fields (DonorOperator, DonorZoneCode, RCPOperator, RCPZoneCode) are present, **OR**
- Command is "Activate"/"Preactivate" **AND** subscriber ExtendedInfo DONOR_OPERATOR, DONOR_ZONE, REC_OPERATOR, or REC_ZONE contains a non-"64" country code

Fallback when `mnpPortType` parameter is blank: orderType "57" → "In"; orderType "60" → "Out".

---

## §7 — Data Extraction

| Field | Method | Purpose |
|-------|--------|---------|
| `title` | `TitleTransformer2(sub.SubscriberName.Title)` | Normalises salutation to CRM-accepted values |
| MNP ExtendedInfo | `XPath.evalAsBoolean(sub/ExtendedInfo[Name="DONOR_OPERATOR"]...)` ×4 | Detects cross-border MNP scenarios |
| `subIdCrm` | `MapSubscriberIdFromCRM(sub, useRowIdCrmParam)` | Selects correct CRM subscriber ID field |
| Per-subscriber XML | `GetXMLForSubscriber` / `GetXMLForSubscriberInChildOU` | XML context for PreExecCheck evaluation |

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

| Scenario | Effect |
|----------|--------|
| OrderType "57" (MNP-In) — fallback | `mnpPortType` defaults to "In" |
| OrderType "60" (MNP-Out) — fallback | `mnpPortType` defaults to "Out" |
| `IsOrderResubmitted = true` | RequestCount not incremented — fan-in preserved |

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Protocol | Purpose |
|-----------|---------|-------------|----------|---------|
| [OUTBOUND] | `/Channels/OMXFMConnectionRequest` | `CRM_CREATE_ORDER_PREPAID` | JMS | Send CRM order creation request per subscriber |
| [INBOUND] | `/Channels/OMXFMConnectionResponse` | CRM_CREATE_ORDER response queue | JMS | Receive CRM order row ID + asset row ID |

### §8.3 Backend API Details

| Item | Value |
|------|-------|
| Backend system | CRM (Customer Relationship Management) |
| Request schema | `CRMCreateOrderRequest` — CRMCreateOrder.xsd |
| Response schema | `CRMCreateOrderResponse` — CRMCreateOrder.xsd |
| Key response fields | `orderRowId` → `sub.SubscriberCrmId`; `assetRowId` → `sub.AssetCrmId` |

### §8.4 ExtendedInfo Fields Read

| ExtendedInfo Name | Scope | Purpose |
|-------------------|-------|---------|
| `DONOR_OPERATOR` | Subscriber | MNP donor network (non-"64" = cross-border) |
| `DONOR_ZONE` | Subscriber | MNP donor zone |
| `REC_OPERATOR` | Subscriber | MNP recipient network |
| `REC_ZONE` | Subscriber | MNP recipient zone |

---

## §9 — Detailed Payload Build

> The request payload is built via a large XSLT embedded in `Event.createEvent("xslt://{{...}}")`. The file is 286KB due to these embedded strings. Two variants exist (ParentOU and ChildOU) differing in the subscriber XML context variable. The XSLT is documented structurally below.

### §9.1 XSLT Parameters Bound

| Parameter | Source |
|-----------|--------|
| `$orderRequest` | Full order concept |
| `$sub` | Current subscriber concept |
| `$command` | Activity parameter "command" |
| `$orderType` | Activity parameter "orderType" |
| `$listOfRootLineItemAction` / `$listOfRootLineItemStatus` | Activity parameters |
| `$listOfLineItemAction` / `$listOfLineItemStatus` | Activity parameters |
| `$submissionDateFormat` | Formatted SubmissionDate (Bangkok TZ) |
| `$l9TmvActDateFormat` | Formatted l9TmvActDate (Bangkok TZ) |
| `$ProofDateFormat` | Formatted ProofDate (NO TZ conversion — bug) |
| `$sysDateFormat` | Current system datetime (Bangkok TZ) |
| `$mnpPortType` | MNP port direction ("In"/"Out"/"") |
| `$subIdCrm` | Mapped CRM subscriber ID |
| `$runningOrderNumber` | Sequence counter (starts at 1 per subscriber) |
| `$mappingValueFrom`, `$ignoreBRMS`, `$ignoreResourceInfo`, `$ignoreLanguage`, `$ignoreAssetRowId`, `$projValue` | Behaviour flags from Activity parameters |
| `$globalVariables` | Global variable store (JMS headers, CRM credentials) |

### §9.3 JMS / Event Header Fields

| Header | Value |
|--------|-------|
| JMSPriority | From global variable JMSPriority |
| JMSCorrelationID | `orderRequest.OrderData.OMXTrackingId` |
| OrderID | `orderRequest.OrderData.OrderID` |
| RefID | `subRefId` (per-subscriber reference) |
| OrderType | `orderRequest.OrderData.OrderType` |
| UserName / Password | From global variables [Credential-gated: IsEnableUserPass="true"] |

### §9.4 CRMCreateOrderRequest Field Mapping

```text
createEvent
└── event
    ├── JMSPriority        ← $globalVariables/.../JMSPriority              [Always]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId          [Always]
    ├── OrderID            ← $orderRequest/OrderData/OrderID                [Always]
    ├── RefID              ← $subRefId                                       [Always]
    ├── OrderType          ← $orderRequest/OrderData/OrderType              [Always]
    ├── UserName           ← $globalVariables/UserName                      [Credential-gated: IsEnableUserPass="true"]
    ├── Password           ← $globalVariables/Password                      [Credential-gated: IsEnableUserPass="true"]
    └── payload
        └── CRMCreateOrderRequest
            ├── command                ← $command                           [Always]
            ├── orderType              ← $orderType                         [Always]
            ├── submissionDate         ← $submissionDateFormat              [Conditional: non-null]
            ├── subscriberId           ← $subIdCrm                          [Always]
            ├── mnpPortType            ← $mnpPortType                       [Conditional: MNP detected]
            ├── title                  ← TitleTransformer2(SubscriberName.Title) [Conditional: SubscriberName != null]
            ├── l9TmvActDate           ← $l9TmvActDateFormat               [Conditional: non-null]
            ├── proofDate              ← $ProofDateFormat [BUG: no TZ conv] [Conditional]
            ├── PROJ                   ← $projValue                         [Conditional: non-empty]
            ├── listOfRootLineItem                                           [Conditional: param non-empty]
            │   ├── action             ← $listOfRootLineItemAction
            │   └── status             ← $listOfRootLineItemStatus
            └── listOfLineItem                                               [Conditional: param non-empty]
                ├── action             ← $listOfLineItemAction
                └── status             ← $listOfLineItemStatus
```

---

## §10 — (See §9 above for field mapping tree)

---

## §11 — Audit Logging

| When | PROCESS_ID | AUDIT_TRACE | Gated? | Payload |
|------|-----------|-------------|--------|---------|
| Per-subscriber request sent | `pid + "_REQ"` | "Request Sent for CRM_CREATE_ORDER_PREPAID" | AllowWriteLog | reqEvent (WritePayload-gated) |
| Per-subscriber response received | `pid + "_RES"` | "Response received for CRM_CREATE_ORDER_PREPAID" | None | eventResponse (WritePayload-gated) |

---

## §12 — Activity Status Management

| Outcome | Mechanism | Effect |
|---------|-----------|--------|
| At least one request sent | `GetActivityStatusString("1", false)` + `SendDataToDB` | Status = IN_PROGRESS; DB flushed |
| No requests sent | `SkipActivity("4")` | Activity SKIPPED |
| Resubmit mode | `isActResub = true` → RequestCount not incremented | Fan-in counter preserved |
| DATA_ISSUE exception | `HandleActivityException` | Activity FAILED |

---

## §13 — Exception / Error Handling

| Type | Trigger |
|------|---------|
| DATA_ISSUE (`CustomerTypeInfo.type not found`) | CustomerTypeInfo is null or Type == 0 |
| Generic (`HandleActivityException`) | Any other uncaught exception |

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|----------|--------|---------|
| `GetActivityParameterValueFromKey(act, key)` | String | Reads named Parameter from ProcessConfig activity |
| `GetXMLForSubscriber(req, refId)` | String (XML) | Serialises order scoped to ParentOU subscriber for PreExecCheck |
| `GetXMLForSubscriberInChildOU(req, cSubRefId, cOuRefId)` | String (XML) | Serialises order scoped to ChildOU subscriber for PreExecCheck |
| `MapSubscriberIdFromCRM(sub, useRowIdCrmParam)` | String | Selects appropriate CRM subscriber ID based on parameter flag |
| `TitleTransformer2(title)` | String | Maps subscriber title code to CRM salutation |
| `BRMS.IsBlankOrStringNull(s)` | boolean | Null/blank guard |
| `IntraActivitySequencing.ActionRequestEvent(act, refId)` | void | Registers outbound request for fan-in tracking |
| `IntraActivitySequencing.SendFirstRequestEvent(act, "")` | void | Signals first request sent |
| `AllowWriteLog(orderType)` | boolean | Gates request audit log by order type |
| `GetActivityStatusString("1", false)` | String | Returns IN_PROGRESS status string |
| `SendDataToDB(req)` | void | Persists order state to DB |
| `SkipActivity(req, act, "4")` | void | Marks activity as skipped |
| `HandleActivityException(req, act, ae, "")` | void | Generic exception handler |

---

## §15 — Function Dependency Tree

```text
Request_CRM_CREATE_ORDER_PREPAID (rule)
├── Instance.getByExtIdByUri(NextActivityName, ...)                            [BE built-in]
├── [FOR each ParentOU/Subscriber]
│   ├── Response[].CompletionStatus == 2 check                                [skip guard]
│   ├── RuleFunctions.Helpers.GetXMLForSubscriber(req, pSubRefId)             [helper]
│   ├── XPath.execute(PreExecCheck, sXML, ns)                                 [BE built-in]
│   ├── GetActivityParameterValueFromKey(act, key) ×14                        [helper]
│   ├── DateTime.translateTime(date, "Asia/Bangkok") + format(...)            [BE built-in]
│   ├── MapSubscriberIdFromCRM(sub, param)                                     [helper]
│   ├── TitleTransformer2(title)                                               [transformer]
│   ├── BRMS.IsBlankOrStringNull(mnpPortType)                                  [helper]
│   ├── XPath.evalAsBoolean(MNP ExtendedInfo checks) ×4                       [BE built-in]
│   ├── Exception.newException("DATA_ISSUE", ...) [if CustomerTypeInfo null]  [BE built-in]
│   ├── Event.createEvent("xslt://{{CRM_CREATE_ORDER}}...")                   [BE built-in]
│   ├── Event.assertEvent(reqEvent)                                            [BE built-in]
│   ├── IntraActivitySequencing.ActionRequestEvent(act, refId)                [helper]
│   ├── IntraActivitySequencing.SendFirstRequestEvent(act, "")                [helper]
│   ├── Event.Ext.sendEventImmediate(reqEvent)                                [BE built-in]
│   └── [if AllowWriteLog] Event.Ext.sendEventImmediate(Logger _REQ)         [BE built-in]
├── [FOR each ChildOU/Subscriber] — same as above with GetXMLForSubscriberInChildOU
├── [IF !isSkipped]
│   ├── GetActivityStatusString("1", false)                                   [helper]
│   └── SendDataToDB(req)                                                      [helper]
├── [ELSE]
│   └── SkipActivity(req, act, "4")                                           [helper]
└── [CATCH]
    └── HandleActivityException(req, act, ae, "")                             [helper]
```

---

## §16 — Concept Definitions Referenced

| Field | Type | Written / Read |
|-------|------|----------------|
| `orderCurrentActivity.RequestCount` | int | Read (resubmit check); incremented per subscriber (if !isActResub) |
| `orderCurrentActivity.Status` | String | Written: "1" (IN_PROGRESS) or "4" (SKIPPED) |
| `orderCurrentActivity.Response[]` | Array of ResponseBase | Read (reqSuccess check); written in response rulefunction |
| `sub.SubscriberCrmId` | String | Written in response: CRMCreateOrderResponse/orderRowId |
| `sub.AssetCrmId` | String | Written in response (if blank): CRMCreateOrderResponse/assetRowId |
| `currActivity.ResponseCode` | String | Written in response: eventResponse.ResponseCode |
| `currActivity.ResponseMessage` | String | Written in response: eventResponse.ResponseMsg |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | For each subscriber (ParentOU and ChildOU), send a CRM create order request over JMS |
| R2 | Skip subscribers that already have a successful response (CompletionStatus == 2) — idempotency |
| R3 | Extract 14 activity parameters from ProcessConfig to control CRM payload behaviour |
| R4 | Format dates to Bangkok timezone ISO-8601 before including in payload |
| R5 | Detect MNP scenarios and include mnpPortType in request |
| R6 | Guard on CustomerTypeInfo.Type — abort with DATA_ISSUE if missing |
| R7 | On response: write orderRowId to SubscriberCrmId; write assetRowId to AssetCrmId (if blank) |
| R8 | Fan-in: return "true" only when count of responses with ResponseCode suffix "000" equals RequestCount |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| ProofDate sent without Bangkok TZ conversion — CRM receives UTC time (~7 hours off) | [MEDIUM] | Uncomment `proofDate = DateTime.translateTime(proofDate, "Asia/Bangkok")` |
| `reqSuccess` uses `CompletionStatus == 2` only — may not match all success variants | [MEDIUM] | Align with fan-in success check (ResponseCode suffix "000") |
| 286KB file with embedded XSLT — hard to maintain/review | [MEDIUM] | Externalise XSLT to separate template files |
| Two nearly identical loops (ParentOU + ChildOU) — changes must be applied twice | [MEDIUM] | Extract common logic into shared rulefunction |
| Commented-out `ignoreListOfLineItem` parameter | [LOW] | Remove or document |
| Old commented-out ResponseBase variant in response rulefunction | [LOW] | Remove stale code |
| `TitleTransformer2` called when `SubscriberName != null` but Title may still be null | [LOW] | Add null guard on Title |

---

## §18 — Full Source Code (Structural Summary)

> The rule file is 286KB due to large inline XSLT strings. The XSLT content is documented in §9. Below is the rule skeleton with XSLT payloads replaced by structural comments.

```java
/**
 * @description
 * @author CHAYATORN-PC
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CRM_CREATE_ORDER_PREPAID {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "CRM_CREATE_ORDER_PREPAID";
        orderRequest.ProcessFlow.NextActivityID == "CRM_CREATE_ORDER_PREPAID";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Activity nextAct = Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
            boolean isSkipped = true;

            /*** Begin ParentOU ***/
            for (int p = 0; p < pOuLen; p++) {
                /*** Begin ParentOU Subscriber ***/
                for (int ps = 0; ps < pSubLen; ps++) {
                    // reqSuccess check: skip if already responded (CompletionStatus==2)
                    if(!reqSuccess) {
                        // Extract 14 parameters, format dates, determine mnpPortType, check CustomerTypeInfo
                        Events.OMConsumers.OMXFM.Request.CRM_CREATE_ORDER reqEvent =
                            Event.createEvent(/* §9: CRMCreateOrderRequest XSLT — ParentOU variant */);
                        Event.assertEvent(reqEvent);
                        IntraActivitySequencing.ActionRequestEvent(orderCurrentActivity, pSubRefId);
                        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity, "");
                        Event.Ext.sendEventImmediate(reqEvent);
                        runningOrderNumber++;
                        isSkipped = false;
                        if(!isActResub) orderCurrentActivity.RequestCount++;
                        if(AllowWriteLog(OrderType)) {
                            Event.Ext.sendEventImmediate(Event.createEvent(/* §11: Logger _REQ */));
                        }
                    }
                }
                /*** End ParentOU Subscriber ***/

                /*** Begin ChildOU (same logic with GetXMLForSubscriberInChildOU) ***/
                for (int c = 0; c < cOuLen; c++) {
                    for (int cs = 0; cs < cSubLen; cs++) {
                        Events.OMConsumers.OMXFM.Request.CRM_CREATE_ORDER reqEvent =
                            Event.createEvent(/* §9: CRMCreateOrderRequest XSLT — ChildOU variant */);
                        Event.assertEvent(reqEvent);
                        IntraActivitySequencing.ActionRequestEvent(orderCurrentActivity, cSubRefId);
                        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity, "");
                        Event.Ext.sendEventImmediate(reqEvent);
                        isSkipped = false;
                        if(!isActResub) orderCurrentActivity.RequestCount++;
                    }
                }
                /*** End ChildOU ***/
            }
            /*** End ParentOU ***/

            if (!isSkipped) {
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
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

## §19 — Response Message Rule

### §19.1 Overview

Parses the CRM create order response, creates a `ResponseBase` concept, writes CRM row IDs back to subscriber concepts, emits a response audit log, and drives fan-in completion. Returns "true" if all subscriber requests succeeded.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Root order — subscriber hierarchy iterated to match RefID |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.CRM_CREATE_ORDER | CRM response — ResponseCode, ResponseMsg, CompletionStatus, RefID, payload |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Activity — Response[] appended; RequestCount read for fan-in |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object [/Concepts/FM/Base/ResponseBase]
    ├── extId             ← ns:generateTrackingID()                    [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode                [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg  [field: ResponseMsg ≠ ResponseMessage] [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus            [Conditional]
    └── ReferenceId       ← $eventResponse/RefID  [field: RefID ≠ ReferenceId] [Conditional]
```

### §19.4 CRM Row ID Write-Back

After appending ResponseBase, iterates all subscribers to find `RefId == eventResponse.RefID`. On match:

| Field written | Source XPath | Condition |
|---------------|-------------|-----------|
| `sub.SubscriberCrmId` | `$eventResponse/payload/CRMCreateOrderResponse/orderRowId` | Always (on match) |
| `sub.AssetCrmId` | `$eventResponse/payload/CRMCreateOrderResponse/assetRowId` | Only if `sub.AssetCrmId` is blank/null |

> **[LOW]** A commented-out ResponseBase variant uses `$eventResponse/@extId` instead of `generateTrackingID()` — should be removed.

### §19.5 Response Completion Logic (Fan-in)

| Step | Expression | Purpose |
|------|-----------|---------|
| Success count | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` | Counts responses with code suffix "000" |
| Fan-in check | `currActivity.RequestCount == successResponseCount` | All parallel subscriber requests succeeded |
| Return "true" | All matched | Activity fan-in complete — process flow advances |
| Return "false" | Not yet matched | Still waiting for more responses |

### §19.6 Response Audit Log

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"CRM_CREATE_ORDER_PREPAID"` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `"Response received for CRM_CREATE_ORDER_PREPAID"` |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | `eventResponse` (WritePayload-gated) |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
