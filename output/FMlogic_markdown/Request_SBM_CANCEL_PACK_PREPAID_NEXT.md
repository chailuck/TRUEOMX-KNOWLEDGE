# Request_SBM_CANCEL_PACK_PREPAID_NEXT

> FM Logic Documentation — SBM Deferred Pack Cancellation (Next Bill Cycle, IntraActivitySequencing, Batch/Online credential switching)

**Rule:** `Rules.OMConsumers.OMXFM.Request.Request_SBM_CANCEL_PACK_PREPAID_NEXT`
**Priority:** 5 | **Backend:** SBM (function_id `100200005`) | **Pattern:** IntraActivitySequencing per-SubscriberOffer

---

## §1 — Overview & Purpose

**SBM_CANCEL_PACK_PREPAID_NEXT** cancels prepaid data/content packs on the *next bill cycle* (deferred cancellation) via SBM. It is the deferred companion to `SBM_CANCEL_PACK_PREPAID` which handles immediate cancellation. It targets FE-routed SubscriberOffers with ServiceType 88 (prepaid data) or 91, where `EffectiveNextBillInd = 'Y'` — meaning the customer requested removal to take effect at the next billing date rather than immediately.

Uses the **IntraActivitySequencing** pattern: requests are queued and dispatched one-by-one, with response fan-in managed by `ActionResponseEvent(currActivity)` returning "true" when the queue is exhausted.

Unlike most FMs, this rule supports two credential modes — **BATCH** and **ONLINE** — selected at runtime from `IntegrationMethod='BATCH'` in the order. This allows nightly batch removal jobs to use dedicated service credentials separate from interactive ONLINE orders.

> **Copy-paste bugs:** Both the request and response AUDIT_TRACE say `"SBM_CANCEL_PACK_PREPAID"` instead of `"SBM_CANCEL_PACK_PREPAID_NEXT"`. The FM was clearly copied from SBM_CANCEL_PACK_PREPAID. The debug comments also reference `SBM_CANCEL_DATA_PACK`, showing a chain of copies. Neither bug affects functional correctness.

| Attribute | Value |
|-----------|-------|
| Rule file | `Request_SBM_CANCEL_PACK_PREPAID_NEXT.rule` |
| Response rulefunction | `Response_SBM_CANCEL_PACK_PREPAID_NEXT.rulefunction` |
| Priority | 5 |
| Backend system | SBM via `SBM_3GPREPAID` event (function_id `100200005` — deferred/next-cycle cancel) |
| Request event type | `Events.OMConsumers.OMXFM.Request.SBM_3GPREPAID` |
| Response event type | `Events.OMConsumers.OMXFM.Response.SBM_3GPREPAID` |
| Response concept | `Concepts.FM.Response.SBM_DoServiceRes` (richer than ResponseBase — includes nested DoServiceResponse) |
| Dispatch scope | Per SubscriberOffer — ParentOU and ChildOU (triple nested loop: OU → Subscriber → Offer) |
| Dispatch pattern | IntraActivitySequencing (assertEvent → ActionRequestEvent → SendFirstRequestEvent) |
| offerRefId (ParentOU) | `pOuRefId + ":" + ":" + sub.RefId + ":" + offer.OfferName` |
| offerRefId (ChildOU) | `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.OfferName` |
| SBM function_id | `100200005` (next-cycle deferred cancellation) |
| Credential mode | Batch: `SBM_DO_SERVICE/BATCH` | Online: `SBM_DO_SERVICE/ONLINE` |
| Request audit | Unconditional (no AllowWriteLog gate) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM priority |
| forwardChain | true | Standard |
| Rule type | IntraActivitySequencing | assertEvent → ActionRequestEvent → SendFirstRequestEvent; fan-in via ActionResponseEvent |
| Resubmit | Yes | PurgePendingRequestsBeforeResubmit called first; idempotency via CompletionStatus=2 + offerRefId |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order; IntegrationMethod, BillCycleNo, ParentOU/ChildOU subscriber offer loops |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[] for idempotency, IntraActivitySequencing queue management |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId matches |
| 2 | `orderCurrentActivity.ActivityID == "SBM_CANCEL_PACK_PREPAID_NEXT"` | Constrains to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SBM_CANCEL_PACK_PREPAID_NEXT"` | Double-check via NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity ready to process |

---

## §5 — Execution Flow Diagram

1. **Check resubmit** → `isActResub = RequestCount > 0 && IsOrderResubmitted`; if true → `PurgePendingRequestsBeforeResubmit`
2. **Determine Batch/Online mode** → `isBatch = IntegrationMethod='BATCH'`; fetch `app_user`/`app_password` from corresponding global variable branch
3. **ParentOU loop** (OU → Subscriber → Offer): compute `offerRefId`; check idempotency; PreExecCheck; compute `billCycleNo` (dead); get `channel`; build SBM_3GPREPAID event; `assertEvent` → `ActionRequestEvent`; unconditional request audit
4. **ChildOU loop** — same pattern with ChildOU-specific helpers
5. **SendFirstRequestEvent** if any queued; `GetActivityStatusString("1", false)` + `SendDataToDB`
6. If all skipped → `SkipActivity("4")`

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
try {
    // Batch/Online credential selection
    boolean isBatch = OrderData.IntegrationMethod == 'BATCH';
    String app_user = globalVariables/OMX_OM/Services/SBM_DO_SERVICE/{BATCH|ONLINE}/app_user;
    String app_password = globalVariables/OMX_OM/Services/SBM_DO_SERVICE/{BATCH|ONLINE}/app_password;

    if(isActResub) PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

    // ParentOU → Subscriber → Offer triple loop
    for(int i...) { for(int j...) { for(int k...) {
        String offerRefId = pOuRefId + ":" + ":" + refId + ":" + offer.OfferName; // BUG: double-colon
        String filter = XPath(offer/ExtendedInfo[Name="FE_OR_CCBS"]/Value);
        // Idempotency check on Response[]
        if(!reqSuccess) {
            // PreExecCheck via GetXMLForSubscriberOfferFilterWithExtendedInfo
            if(chkRes == "true") {
                String billCycleNo = ConvertBillCycleDate(BillCycleNo); // DEAD — not used in XSLT
                String channel = GetSBMServiceChannel(orderRequest, offer);

                /* COMMENTED OUT: SBM_DO_SERVICE event (function_id=100200052) */
                /* ACTIVE: SBM_3GPREPAID event (function_id=100200005) */
                Event.assertEvent(reqEvent);
                IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                isSkipped = false;
                /* UNCONDITIONAL audit log */
            }
        }
    }}}
    // ChildOU loop (same, GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo)

    if(!isSkipped) {
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
    } else { SkipActivity(..., "4"); }
} catch(Exception ae) { HandleActivityException(...); }
```

---

## §7 — Data Extraction & Pre-Processing

### §7.1 — Batch vs Online Credential Selection

| Condition | app_user source | app_password source |
|-----------|-----------------|---------------------|
| `IntegrationMethod = 'BATCH'` | `globalVariables/.../SBM_DO_SERVICE/BATCH/app_user` | `globalVariables/.../SBM_DO_SERVICE/BATCH/app_password` |
| Any other value (ONLINE) | `globalVariables/.../SBM_DO_SERVICE/ONLINE/app_user` | `globalVariables/.../SBM_DO_SERVICE/ONLINE/app_password` |

### §7.2 — offerRefId Construction

| Scope | offerRefId formula | Note |
|-------|-------------------|------|
| ParentOU | `pOuRefId + ":" + ":" + sub.RefId + ":" + offer.OfferName` | **[BUG: double colon]** — extra separator vs. ChildOU pattern |
| ChildOU | `pOuRefId + ":" + cOuRefId + ":" + sub.RefId + ":" + offer.OfferName` | Correct 3-segment separator |

> **[HIGH]** The ParentOU `offerRefId` has a double-colon: `"pOuRef::subRef:offerName"` vs the ChildOU's `"pOuRef:cOuRef:subRef:offerName"`. If the response `RefID` comes back without the double-colon, the idempotency check for ParentOU offers will never find a match, potentially causing re-dispatch on resubmit.

### §7.3 — Dead billCycleNo Variable

`String billCycleNo = RuleFunctions.Helpers.ConvertBillCycleDate(orderRequest.OrderData.Customer.BillCycleNo)` is computed inside each offer iteration but never appears in the XSLT parameters. Dead code — likely a copy artifact.

### §7.4 — SBM Channel Selection

`GetSBMServiceChannel(orderRequest, offer)` — selects the correct SBM channel string from the offer context. Result passed to XSLT as `$channel` → `ns:channel` in payload.

### §7.5 — FE_OR_CCBS Filter

`filter = XPath.evalAsString("$offer/ExtendedInfo[Name=\"FE_OR_CCBS\"]/Value", offer)` — reads the routing flag from the offer's extended info, passed to `GetXMLForSubscriberOfferFilterWithExtendedInfo` for PreExecCheck XML construction.

### §7.6 — Commented-Out SBM_DO_SERVICE Event

Lines 94/152 contain a fully developed but fully commented-out XSLT block using event type `Events.OMConsumers.OMXFM.Request.SBM_DO_SERVICE` (function_id `100200052`). The active code uses `SBM_3GPREPAID` (function_id `100200005`). The SBM_DO_SERVICE variant had a conditional `xsl:if` on `req_transaction_id`; the active variant emits it unconditionally.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Triggered for FE-routed SubscriberOffers with `ServiceType='88'` (prepaid 3G data pack) or `ServiceType='91'` AND `EffectiveNextBillInd='Y'`. ProcessConfig PreExecCheck gates this at the activity level. Only runs for deferred-removal requests.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.SBM_3GPREPAID` | Next-cycle pack cancellation per SubscriberOffer (IntraActivitySequencing queue) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit (unconditional) |

### §8.3 — Backend API Details

| System | Operation | function_id | Semantics |
|--------|-----------|-------------|-----------|
| SBM | `doServiceArrayRequest` | `100200005` | Next-bill-cycle deferred pack cancellation |

### §8.4 — BE Working Memory Dependencies

| Concept path | Access | Purpose |
|-------------|--------|---------|
| `OrderData.IntegrationMethod` | Read | Determines BATCH vs ONLINE credential selection |
| `Customer.BillCycleNo` | Read | ConvertBillCycleDate (result unused — dead variable) |
| `ParentOU[*].RefId` | Read | pOuRefId — part of offerRefId key |
| `ParentOU[*].Subscriber[*].RefId` | Read | sub.RefId — part of offerRefId key |
| `ParentOU[*].Subscriber[*].MSISDN` | Read | ns:service_no in SBM payload |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].OfferName` | Read | ns:parameters/package_code + part of offerRefId key |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].ExtendedInfo[]` | Read | FE_OR_CCBS filter value for PreExecCheck XML |
| `ChildOU[*].RefId` | Read | cOuRefId — part of ChildOU offerRefId key |
| `ChildOU[*].Subscriber[*].RefId/MSISDN/SubscriberOffers` | Read | Same as ParentOU equivalents |
| `orderCurrentActivity.Response[]` | Read | Idempotency check per offer |

### §8.5 — Global Variable Dependencies

| Global variable path | Condition | Used for |
|---------------------|-----------|---------|
| `OMX_OM/Services/SBM_DO_SERVICE/BATCH/app_user` | IntegrationMethod='BATCH' | SBM authentication username (batch mode) |
| `OMX_OM/Services/SBM_DO_SERVICE/BATCH/app_password` | IntegrationMethod='BATCH' | SBM authentication password (batch mode) |
| `OMX_OM/Services/SBM_DO_SERVICE/ONLINE/app_user` | Not BATCH | SBM authentication username (online mode) |
| `OMX_OM/Services/SBM_DO_SERVICE/ONLINE/app_password` | Not BATCH | SBM authentication password (online mode) |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameters (SBM_3GPREPAID event)

| Param | Source |
|-------|--------|
| `$orderRequest` | orderRequest concept |
| `$offerRefId` | Composite key (pOuRefId + separators + sub.RefId + offer.OfferName) |
| `$app_password` | Global var — BATCH or ONLINE branch |
| `$app_user` | Global var — BATCH or ONLINE branch |
| `$channel` | `GetSBMServiceChannel(orderRequest, offer)` |
| `$offer` | SubscriberOffers concept |
| `$msisdn` | sub.MSISDN |

Note: `$billCycleNo` is NOT a parameter despite being computed. Dead variable.

### §9.2 — Event Container

No extId attribute on the event. Response uses `OMXUtils.generateTrackingID()` on the BE side.

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Conditional: xsl:if |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Conditional: xsl:if |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Conditional: xsl:if |
| `RefID` | `$offerRefId` | **Always** |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Conditional: xsl:if |

### §9.4 — Payload Root

`ns1:doServiceArrayRequest / ns1:DoServiceRequest`

### §9.5 — Payload Fields

| Element | Source | Condition | Notes |
|---------|--------|-----------|-------|
| `ns:app_password` | `$app_password` | Always | BATCH or ONLINE credential |
| `ns:app_user` | `$app_user` | Always | BATCH or ONLINE credential |
| `ns:channel` | `$channel` | Always | From GetSBMServiceChannel helper |
| `ns:function_id` | `"100200005"` | Always (static) | Next-cycle deferred cancellation SBM function |
| `ns:parameters/ns:item[1]/ns:key` | `"package_code"` | Always (static) | Parameter key |
| `ns:parameters/ns:item[1]/ns:value` | `$offer/OfferName` | Always | Pack/offer code to cancel |
| `ns:parameters/ns:item[2]/ns:key` | `"mode"` | Always (static) | Parameter key |
| `ns:parameters/ns:item[2]/ns:value` | `"sync"` | Always (static) | Synchronous execution mode |
| `ns:req_transaction_id` | `$orderRequest/OrderData/OrderID` | **Always** (no xsl:if) | Unconditional — differs from commented-out SBM_DO_SERVICE which had conditional |
| `ns:service_no` | `$msisdn` | Always | Subscriber MSISDN |
| `ns:waiting_mode` | `"result"` | Always (static) | Wait for execution result before returning |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event  (no @extId)
    ├── JMSPriority         ← $orderRequest/OrderPriority            [Conditional: xsl:if]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId  [Conditional: xsl:if]
    ├── OrderID             ← $orderRequest/OrderData/OrderID        [Conditional: xsl:if]
    ├── RefID               ← $offerRefId                            [Always]
    ├── OrderType           ← $orderRequest/OrderData/OrderType      [Conditional: xsl:if]
    └── payload
        └── ns1:doServiceArrayRequest
            └── ns1:DoServiceRequest
                ├── ns:app_password       ← $app_password           [Always] BATCH or ONLINE branch
                ├── ns:app_user           ← $app_user               [Always] BATCH or ONLINE branch
                ├── ns:channel            ← $channel                [Always]
                ├── ns:function_id        ← "100200005"             [Always (static)] deferred/next-cycle cancel
                ├── ns:parameters
                │   ├── ns:item[1]
                │   │   ├── ns:key        ← "package_code"          [Always]
                │   │   └── ns:value      ← $offer/OfferName        [Always]
                │   └── ns:item[2]
                │       ├── ns:key        ← "mode"                  [Always]
                │       └── ns:value      ← "sync"                  [Always (static)]
                ├── ns:req_transaction_id ← $orderRequest/OrderData/OrderID  [Always (no xsl:if)]
                ├── ns:service_no         ← $msisdn                 [Always]
                └── ns:waiting_mode       ← "result"                [Always (static)]
```

Legend: `[Always]` = unconditional; `[Conditional: ...]` = inside xsl:if; `(static)` = hardcoded literal value.

---

## §11 — Audit Logging

| Event | Gate | OPERATION_NAME | AUDIT_TRACE | Bug? |
|-------|------|---------------|-------------|------|
| Request audit | Unconditional | `"SBM_CANCEL_PACK_PREPAID_NEXT"` ✓ | `"Request Sent for SBM_CANCEL_PACK_PREPAID"` | **[BUG: Missing "_NEXT"]** |
| Response audit | Unconditional | `"SBM_CANCEL_PACK_PREPAID_NEXT"` ✓ | `"Response received for SBM_CANCEL_PACK_PREPAID"` | **[BUG: Missing "_NEXT"]** |

> Both AUDIT_TRACE values say `SBM_CANCEL_PACK_PREPAID` (not `SBM_CANCEL_PACK_PREPAID_NEXT`). OPERATION_NAME is correct in both. Cosmetic/audit labeling bug only — does not affect routing or functionality.

---

## §12 — Activity Status Management

| Condition | Action | Status |
|-----------|--------|--------|
| At least one offer queued and sent | `SendFirstRequestEvent` → `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" = PROCESSING |
| No offers pass checks | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" = SKIPPED |

---

## §13 — Exception / Error Handling

**Request rule:** Standard `catch(Exception ae) → HandleActivityException`.

**Response RF:** No try/catch — delegates entirely to `IntraActivitySequencing.ActionResponseEvent(currActivity)`.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears pending queue on resubmit |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Enqueues request event for sequential dispatch |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Sends the first queued event to start dispatch chain |
| `IntraActivitySequencing.ActionResponseEvent(activity)` | Fan-in: returns true when all queued requests have been responded to |
| `Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, offerName, filter)` | Builds PreExecCheck XML for ParentOU subscriber offer |
| `Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, refId, offerName, ouRefId, filter)` | Builds PreExecCheck XML for ChildOU subscriber offer |
| `Helpers.ConvertBillCycleDate(billCycleNo)` | Converts bill cycle number to date string (result unused — dead call) |
| `Helpers.GetSBMServiceChannel(orderRequest, offer)` | Determines SBM channel string for the offer context |
| `Helpers.GetActivityStatusString(code, flag)` | Status code translation |
| `Helpers.SendDataToDB(orderRequest)` | Persist order state |
| `Helpers.SkipActivity(orderRequest, activity, code)` | Mark activity skipped |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |

---

## §15 — Function Dependency Tree

```text
Request_SBM_CANCEL_PACK_PREPAID_NEXT (rule)
├── XPath.evalAsBoolean()                    [IntegrationMethod='BATCH' check]
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()  [if resubmit]
├── XPath.evalAsString()                     [app_user, app_password from globalVars × 2]
├── [ParentOU/ChildOU/Offer loops]
│   ├── XPath.evalAsString()                 [FE_OR_CCBS filter from offer]
│   ├── [idempotency check on Response[]]
│   ├── Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo()   [ParentOU PreExecCheck]
│   ├── Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo()  [ChildOU PreExecCheck]
│   ├── XPath.execute()                      [PreExecCheck evaluation]
│   ├── Helpers.ConvertBillCycleDate()       [DEAD — result unused]
│   ├── Helpers.GetSBMServiceChannel()       [channel selection]
│   ├── Event.createEvent()                  [SBM_3GPREPAID XSLT — function_id=100200005]
│   ├── Event.assertEvent()                  [IntraActivitySequencing enqueue]
│   ├── IntraActivitySequencing.ActionRequestEvent()
│   ├── System.nanoTime()
│   ├── Event.createEvent()                  [Logger XSLT — unconditional audit]
│   └── Event.Ext.sendEventImmediate()       [request audit]
├── IntraActivitySequencing.SendFirstRequestEvent()
├── Helpers.GetActivityStatusString()
├── Helpers.SendDataToDB()
├── Helpers.SkipActivity()
└── Helpers.HandleActivityException()

Response_SBM_CANCEL_PACK_PREPAID_NEXT (rulefunction)
├── OMXUtils.generateTrackingID()            [extId for SBM_DoServiceRes]
├── Instance.createInstance()                [SBM_DoServiceRes XSLT — ResponseCode, ResponseMessage,
│                                             CompletionStatus, ReferenceId, DoServiceResponse×2 variants]
├── currActivity.Response[] ← activityRes
├── System.nanoTime()
├── Event.createEvent()                      [Logger XSLT — unconditional, AUDIT_TRACE has "_NEXT" missing bug]
├── Event.Ext.sendEventImmediate()           [response audit]
└── IntraActivitySequencing.ActionResponseEvent(currActivity)
    → "true"  (queue exhausted — all offers responded)
    → "false" (still waiting)
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | Both | OrderData.IntegrationMethod; Customer.BillCycleNo; ParentOU/ChildOU/Subscriber/SubscriberOffers |
| `Concepts.OM.ProcessConfig.Activity` | Both | ActivityID, Status, PreExecCheck, Response[] (idempotency + queue) |
| `Concepts.FM.Response.SBM_DoServiceRes` | Response RF | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId; nested **DoServiceResponse[]**: extra_xml, req_transaction_id, response_message, result_code, result_desc, result_namespace, transaction_id |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Request rule | OfferName (package_code), ExtendedInfo[FE_OR_CCBS] (filter) |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | For each FE-routed SubscriberOffer (ServiceType 88/91, EffectiveNextBillInd=Y) across ParentOU and ChildOU, call SBM function_id 100200005 (next-cycle deferred cancellation) |
| R2 | Credential selection: use BATCH global vars when IntegrationMethod='BATCH', ONLINE global vars otherwise |
| R3 | Per-offer idempotency: skip if Response[].ReferenceId == offerRefId and CompletionStatus == 2 |
| R4 | IntraActivitySequencing: queue all offers then SendFirstRequestEvent; response fan-in via ActionResponseEvent returning "true" when queue exhausted |
| R5 | SBM payload: package_code=offer.OfferName, mode="sync", waiting_mode="result", service_no=MSISDN, channel from GetSBMServiceChannel |
| R6 | req_transaction_id always emitted (OrderID — no conditional xsl:if) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Double-colon in ParentOU offerRefId:** `pOuRefId + ":" + ":" + sub.RefId + ":" + offer.OfferName` — extra colon means idempotency key format differs from ChildOU. If SBM response RefID matches the ChildOU format, ParentOU offer re-checks will never find the match and the offer will be re-dispatched on resubmit. | [HIGH] | Fix ParentOU offerRefId to use single colon: remove the empty ChildOU segment — whichever matches the response RefID format |
| **Dead billCycleNo variable:** ConvertBillCycleDate is called per offer but result is never used. Wasted CPU on every offer iteration. | [MEDIUM] | Remove the ConvertBillCycleDate call or add billCycleNo to XSLT params if SBM needs it |
| **Commented-out SBM_DO_SERVICE event:** 60+ lines of dead code for an alternative SBM event type with function_id 100200052. Maintenance burden. | [LOW] | Remove the commented-out block entirely, or document why it was retained |
| **AUDIT_TRACE copy-paste bug:** Both request and response say "SBM_CANCEL_PACK_PREPAID" instead of "SBM_CANCEL_PACK_PREPAID_NEXT". Makes audit log queries unreliable. | [MEDIUM] | Fix both AUDIT_TRACE values to include "_NEXT" |
| **Batch/Online credential scope:** A single boolean at order level determines all offer credentials. Mixed batch/online orders not supported. | [LOW] | Document that IntegrationMethod is an order-level flag and mixed-mode orders are not supported |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_SBM_CANCEL_PACK_PREPAID_NEXT {
    attribute { priority = 5; forwardChain = true; }
    then {
        boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
        try {
            boolean isBatch = XPath(OrderData.IntegrationMethod == 'BATCH');
            if(isActResub) PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

            String app_user = globalVars/SBM_DO_SERVICE/{BATCH|ONLINE}/app_user;
            String app_password = globalVars/SBM_DO_SERVICE/{BATCH|ONLINE}/app_password;

            // ParentOU → Subscriber → Offer triple loop
            for(...) { for(...) { for(...) {
                String offerRefId = pOuRefId + ":" + ":" + refId + ":" + offer.OfferName; // BUG: double-colon
                String filter = XPath(offer/ExtendedInfo[Name="FE_OR_CCBS"]/Value);
                // Idempotency check on Response[]
                if(!reqSuccess) {
                    // PreExecCheck via GetXMLForSubscriberOfferFilterWithExtendedInfo
                    if(chkRes == "true") {
                        String billCycleNo = ConvertBillCycleDate(BillCycleNo); // DEAD
                        String channel = GetSBMServiceChannel(orderRequest, offer);
                        /* COMMENTED OUT: SBM_DO_SERVICE event, function_id=100200052 */
                        /* ACTIVE: SBM_3GPREPAID XSLT (see §9); function_id=100200005 */
                        Event.assertEvent(reqEvent);
                        IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                        isSkipped = false;
                        /* UNCONDITIONAL audit — AUDIT_TRACE bug: says SBM_CANCEL_PACK_PREPAID */
                    }
                }
            }}}
            // ChildOU loop (GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo)

            if(!isSkipped) {
                IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                SendDataToDB(orderRequest);
            } else { SkipActivity(..., "4"); }
        } catch(Exception ae) { HandleActivityException(...); }
    }
}
```

---

## §19 — Response Message Rule (Response_SBM_CANCEL_PACK_PREPAID_NEXT)

### §19.1 — Overview

Builds a `Concepts.FM.Response.SBM_DoServiceRes` concept (richer than standard ResponseBase — includes nested `DoServiceResponse` objects with SBM-specific result fields). Appends to `currActivity.Response[]`. Logs unconditionally. Delegates fan-in to `IntraActivitySequencing.ActionResponseEvent(currActivity)`.

**Event type consumed:** `Events.OMConsumers.OMXFM.Response.SBM_3GPREPAID`

> **Response AUDIT_TRACE:** `"Response received for SBM_CANCEL_PACK_PREPAID"` — missing "_NEXT". Same copy-paste bug as the request rule.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context for audit logging |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SBM_3GPREPAID` | SBM response event; carries ResponseCode, RefID, and nested doServiceArrayResponse payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity; Response[] written to; fan-in managed by ActionResponseEvent |

### §19.3 — SBM_DoServiceRes Concept Construction

```text
createObject
└── object
    ├── @extId              ← $extId (OMXUtils.generateTrackingID() from BE)  [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode                       [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg                        [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus                   [Conditional]
    ├── ReferenceId         ← $eventResponse/RefID                              [Conditional]
    ├── DoServiceResponse   [if doServiceArrayResponse/CheckPackAllowReturn exists — Variant 1]
    │   ├── extra_xml           [Conditional]
    │   ├── req_transaction_id  [Conditional]
    │   ├── response_message    [Conditional]
    │   ├── result_code         [Conditional]
    │   ├── result_desc         [Conditional]
    │   ├── result_namespace    [Conditional]
    │   └── transaction_id      [Conditional]
    └── DoServiceResponse   [if doServiceArrayResponse/DoServiceReturn exists — Variant 2]
        ├── extra_xml           [Conditional]
        ├── req_transaction_id  [Conditional]
        ├── response_message    [Conditional]
        ├── result_code         [Conditional]
        ├── result_desc         [Conditional]
        ├── result_namespace    [Conditional]
        └── transaction_id      [Conditional]
```

### §19.4 — Response Completion Logic

| Step | Logic |
|------|-------|
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Return "true" | Queue exhausted — all enqueued offers have been responded to |
| Return "false" | Still pending responses in the IntraActivitySequencing queue |

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| `OPERATION_NAME` | `"SBM_CANCEL_PACK_PREPAID_NEXT"` ✓ |
| `AUDIT_TRACE` | `"Response received for SBM_CANCEL_PACK_PREPAID"` **[BUG: Missing "_NEXT"]** |
| Gate | Unconditional (no AllowWriteLog) |
| `PROCESS_ID` | `concat($pid, "_RES")` |
| `payload` | Full `$eventResponse` copy, gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
