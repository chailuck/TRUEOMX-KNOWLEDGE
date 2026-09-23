# Request_CCP_ADD_OFFER

FM Logic Documentation — CCP Price Plan Add / Offer Provisioning (IntraActivitySequencing, per-offer)

**Rule:** Rules.OMConsumers.OMXFM.Request.Request_CCP_ADD_OFFER | **Priority:** 5 | **Backend:** CCP (ModUserIndiPricePlan) | **Pattern:** IntraActivitySequencing per-offer

---

## §1 — Overview & Purpose

**CCP_ADD_OFFER** provisions each subscriber offer to the CCP system by calling `processModUserIndiPricePlan`. It iterates every subscriber offer across all ParentOU and ChildOU subscribers, applies per-offer PreExecCheck filtering, skips offers already successfully processed (idempotency check via `CompletionStatus=2`), and dispatches each as a sequential JMS request via **IntraActivitySequencing**. The response RF correctly wires `ActionResponseEvent` to trigger each subsequent queued offer after a response arrives.

> **Correctly wired IntraActivitySequencing:** Unlike CCP_ACTIVATE_SIM, this FM properly calls `IntraActivitySequencing.ActionResponseEvent(currActivity)` in the response RF, enabling sequential per-offer dispatch.

| Attribute | Value |
|-----------|-------|
| Rule file | Request_CCP_ADD_OFFER.rule |
| Response rulefunction | Response_CCP_ADD_OFFER.rulefunction |
| Priority | 5 |
| Backend system | CCP via ESB (`processModUserIndiPricePlan`) |
| Request event type | `Events.OMConsumers.OMXFM.Request.CCP_ADD_OFFER` |
| Response event type | `Events.OMConsumers.OMXFM.Response.CCP_ADD_OFFER` |
| Response concept | `Concepts.FM.Response.CCBS_AddAgreeOfferRes` |
| Payload schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CCP_ModUserIndiPricePlanRequest.xsd` |
| Dispatch scope | Per SubscriberOffer — both ParentOU and ChildOU subscribers |
| XSLT variants | Two: ParentOU variant (params: `$psub`) and ChildOU variant (params: `$csub`) |
| refId key | `subOff.Soc` (SOC code, used for idempotency check and JMS RefID header) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM priority |
| forwardChain | true | Enables forward chaining |
| Rule type | IntraActivitySequencing | Per-offer sequential dispatch via `assertEvent` + `ActionRequestEvent` + `SendFirstRequestEvent` |
| Resubmit | Yes | `PurgePendingRequestsBeforeResubmit` + partial idempotency skip |
| Skip mechanism | Yes | Skips if no offers pass checks; individual offers skipped if already successful (CompletionStatus=2) |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — ParentOU/ChildOU, subscribers, offers, ExtendedInfo |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — IntraActivitySequencing queue, Response[] for idempotency |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId matches |
| 2 | `orderCurrentActivity.ActivityID == "CCP_ADD_OFFER"` | Constrains to CCP_ADD_OFFER |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCP_ADD_OFFER"` | Double-check via NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity ready |

---

## §5 — Execution Flow Diagram

1. **Resubmit purge** — if `isActResub`: `PurgePendingRequestsBeforeResubmit`
2. **Load activity config** — read `nextAct.PreExecCheck`
3. **ParentOU subscriber loop** — for each ParentOU → Subscriber → SubscriberOffer:
   - Extract `refId = subOff.Soc` and `filter = FE_OR_CCBS ExtendedInfo value`
   - **Idempotency check**: scan `currActivity.Response[]` for `ReferenceId == refId && CompletionStatus == 2` → skip if found
   - Per-offer **PreExecCheck** via `GetXMLForSubscriberOfferFilterWithExtendedInfo`
   - Build ParentOU variant XSLT event → `assertEvent` → `ActionRequestEvent`
   - Audit log (gated on `AllowWriteLog`); AUDIT_TRACE includes `refId`
4. **ChildOU subscriber loop** — same pattern via `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo` and ChildOU XSLT variant
5. **Dispatch first** — `IntraActivitySequencing.SendFirstRequestEvent`
6. **Status** — `GetActivityStatusString("1", false)` + `SendDataToDB`; or `SkipActivity("4")`

> **Sequential per-offer dispatch:** All offers are queued first, then `SendFirstRequestEvent` dispatches the first one. Each response triggers `ActionResponseEvent` in the response RF, which dispatches the next queued offer. This continues until the queue is exhausted.

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
if(isActResub)
    RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

try {
    Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
    String chkXPath = nextAct.PreExecCheck;
    boolean isSkipped = true;

    // ===== ParentOU Subscriber Offer loop =====
    for(int i = 0; i < iPOULen; i++) {
        for(int j = 0; j < iSubscriberLen; j++) {
            for(int k = 0; k < iSubscriberOfferLen; k++) {
                String refId = subOff.Soc; // SOC code used as correlation key
                String filter = /* FE_OR_CCBS ExtendedInfo value */;

                // Idempotency: skip if already successful (CompletionStatus == 2)
                boolean reqSuccess = false;
                for(int iResp = 0; iResp < orderCurrentActivity.Response@length; iResp++) {
                    if(String.equals(Response[iResp].ReferenceId, refId) && Response[iResp].CompletionStatus == 2)
                        reqSuccess = true;
                }

                if(!reqSuccess) {
                    // Per-offer PreExecCheck
                    String chkRes = "true";
                    if(String.length(nextAct.PreExecCheck) > 0) {
                        String sXML = RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(
                            orderRequest, psub.RefId, subOff.OfferName, filter);
                        chkRes = XPath.execute("/("+chkXPath+")", sXML, ...);
                    }
                    if(String.equals(chkRes, "true")) {
                        // [ParentOU XSLT: processModUserIndiPricePlan — see §9.7]
                        Events.OMConsumers.OMXFM.Request.CCP_ADD_OFFER reqEvent = Event.createEvent("xslt://...");
                        Event.assertEvent(reqEvent);
                        RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                        isSkipped = false;
                        if(RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                            // AUDIT_TRACE = "Request Sent for CCP_ADD_OFFER for " + refId
                            Event.Ext.sendEventImmediate(...);
                        }
                    }
                }
            }
        }

        // ===== ChildOU Subscriber Offer loop (same pattern) =====
        // NOTE: ChildOU effType xsl:when has operator precedence bug (missing parentheses)
    }

    if(!isSkipped) {
        RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
        RuleFunctions.Helpers.SendDataToDB(orderRequest);
    } else {
        RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
    }
} catch(Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §7 — Data Extraction

### §7.1 — Idempotency Check

Before queuing an offer, the rule scans existing responses for a match on `ReferenceId == refId (subOff.Soc)` AND `CompletionStatus == 2`. If found, the offer is skipped — supports safe resubmit without re-provisioning already-completed offers.

### §7.2 — FE_OR_CCBS Filter

| ExtendedInfo value | Effect |
|--------------------|--------|
| `FE` | Frontend system — CCP_USER/CCP_PASSWORD included in `authReqM` |
| `CCP` | CCP native — authReqM left empty (no credentials) |
| `BRMS` | BRMS-driven offer — authReqM left empty; also used as filter in PreExecCheck |

### §7.3 — cpTransactionId Generation

```xpath
tib:left(tib:pad(concat("OMX", $orderRequest/OrderData/Channel), "12", "0"), 12)
```

Pads "OMX" + Channel to exactly 12 chars (right-pad with "0"). More robust than CCP_ACTIVATE_SIM's string-concat approach — always exactly 12 chars.

### §7.4 — pricePlanCode — OrderType 45001 Special Case

| Condition | pricePlanCode source |
|-----------|---------------------|
| `OrderType = '45001'` | `ParentOU[1]/Subscriber[1]/SubscriberOffers[FE_OR_CCBS=BRMS]/OfferName` — always from the BRMS offer of first subscriber, regardless of current offer |
| All other OrderTypes | `$subOff/OfferName` — current offer's name |

### §7.5 — ExtendedInfo Fields Mapped to ExtParams

| ExtendedInfo key | Payload field |
|-----------------|---------------|
| `BAG_ID` | `ns2:ExtParam1` |
| `BONUS` | `ns2:ExtParam2` |
| `DURATION_DAYS` | `ns2:ExtParam3` |
| `BONUS_UNIT` | `ns2:ExtParam4` |
| `BAG_TYPE` | `ns2:ExtParam5` |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

OrderType **'45001'** triggers a special pricePlanCode override — uses the BRMS offer name from the first subscriber's offers. All other order types use the current subscriber offer's OfferName. Channel **'TYC20'** forces `effType=2` (immediate) even when EffectiveDate/ExpirationDate are present.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|------------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCP_ADD_OFFER` | processModUserIndiPricePlan per offer (sequential) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit (AllowWriteLog-gated); AUDIT_TRACE includes SOC refId |

### §8.3 — Backend API Details

| System | Operation | Protocol | Schema |
|--------|-----------|----------|--------|
| CCP | processModUserIndiPricePlan | JMS async (IntraActivitySequencing) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CCP_ModUserIndiPricePlanRequest.xsd` |

### §8.4 — BE Working Memory Dependencies

| Concept path | Access | Purpose |
|-------------|--------|---------|
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].Soc` | Read | refId — correlation key and idempotency |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].OfferName` | Read | pricePlanCode (most order types) |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].ExtendedInfo[FE_OR_CCBS]` | Read | Credential gating and PreExecCheck filter |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].EffectiveDate/ExpirationDate` | Read | effType / effDate / expDate |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].ExtendedInfo[BAG_ID/BONUS/etc.]` | Read | ExtParam1–5 |
| `ParentOU[*].Subscriber[*].MSISDN` | Read | msisdn in payload |
| `ParentOU[*].ChildOU[*].Subscriber[*].SubscriberOffers[*].*` | Read | Same as above for ChildOU |
| `orderRequest.OrderData.Channel` | Read | cpTransactionId + effType TYC20 gate |
| `orderRequest.OrderData.OrderType` | Read | pricePlanCode override (45001) + audit log gate |
| `orderRequest.OrderData.ExtendedInfo[CCP_USER/CCP_PASSWORD]` | Read | authReqM credentials (FE-type offers only) |
| `orderCurrentActivity.Response[]` | Read | Idempotency check per offer |

### §8.5 — ExtendedInfo Fields Used

| Key | Source | Required? | Purpose |
|-----|--------|-----------|---------|
| `FE_OR_CCBS` | SubscriberOffers.ExtendedInfo | Optional | Determines credential gating ("FE" → include appid/password) and PreExecCheck filter |
| `CCP_USER` | OrderData.ExtendedInfo | Conditional | CCP appid (only for FE-type offers) |
| `CCP_PASSWORD` | OrderData.ExtendedInfo | Conditional | CCP password (only for FE-type offers) |
| `BAG_ID` | SubscriberOffers.ExtendedInfo | Optional | ExtParam1 |
| `BONUS` | SubscriberOffers.ExtendedInfo | Optional | ExtParam2 |
| `DURATION_DAYS` | SubscriberOffers.ExtendedInfo | Optional | ExtParam3 |
| `BONUS_UNIT` | SubscriberOffers.ExtendedInfo | Optional | ExtParam4 |
| `BAG_TYPE` | SubscriberOffers.ExtendedInfo | Optional | ExtParam5 |

### §8.6 — Global Variable Dependencies

| Variable path | Used in |
|--------------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Response audit payload gating |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding (Two Variants)

| Param | ParentOU variant | ChildOU variant |
|-------|-----------------|-----------------|
| `$orderRequest` | orderRequest | orderRequest |
| `$refId` | subOff.Soc | subOff.Soc |
| `$subOff` | ParentOU subscriber offer | ChildOU subscriber offer |
| `$psub` / `$csub` | ParentOU Subscriber | ChildOU Subscriber |

### §9.2 — Event Container

Event type: `Events.OMConsumers.OMXFM.Request.CCP_ADD_OFFER`. Created once per offer, asserted into working memory, enqueued via `ActionRequestEvent`.

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Conditional (xsl:if) |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Conditional |
| `RefID` | `$refId` (subOff.Soc) | Always |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Conditional |

### §9.4 — Payload Root Element

- ParentOU: `<ns2:processModUserIndiPricePlan>`
- ChildOU: `<ns1:processModUserIndiPricePlan>`
- Both bind to: `CCP_ModUserIndiPricePlanRequest.xsd`

### §9.5 — Core Payload Fields

| XML element | Source | Condition |
|-------------|--------|-----------|
| `ns2:appid` | `ExtendedInfo[CCP_USER]/Value` | Only if `FE_OR_CCBS = "FE"` and CCP_USER present |
| `ns2:password` | `ExtendedInfo[CCP_PASSWORD]/Value` | Only if `FE_OR_CCBS = "FE"` and CCP_PASSWORD present |
| `ns2:cpTransactionId` | `tib:left(tib:pad(concat("OMX",Channel),"12","0"),12)` | If CCP_USER and CCP_PASSWORD both exist |
| `ns2:msisdn` | `$psub/MSISDN` or `$csub/MSISDN` | Conditional |
| `ns2:pricePlanCode` | OrderType=45001 → BRMS OfferName; else `$subOff/OfferName` | Conditional (xsl:choose) |
| `ns2:action` | `1` (static — add action) | Always |
| `ns2:effType` | `3` if future dated and Channel≠TYC20; else `2` | xsl:choose |
| `ns2:effDate` | `tib:format-dateTime('yyyy-MM-dd HH-mm-ss', tib:translate-timezone(EffectiveDate,'+07:00'))` | If EffectiveDate present |
| `ns2:expDate` | `tib:format-dateTime('yyyy-MM-dd HH-mm-ss', tib:translate-timezone(ExpirationDate,'+07:00'))` | If ExpirationDate present |
| `ns2:chargeFlag` | `1` (static) | Always |
| `ns2:smsSendFlag` | `0` (static — suppress SMS) | Always |
| `ns2:ExtParam1–5` | BAG_ID, BONUS, DURATION_DAYS, BONUS_UNIT, BAG_TYPE | Conditional per key |

### §9.6 — Complete Generated XML Example

```xml
<ns2:processModUserIndiPricePlan
  xmlns:ns2="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CCP_ModUserIndiPricePlanRequest.xsd">
  <ns2:modUserIndiPricePlanReq>
    <ns2:authReqM>
      <!-- Only when FE_OR_CCBS = "FE" -->
      <ns2:appid>ccp_user</ns2:appid>
      <ns2:password>ccp_pass</ns2:password>
      <ns2:cpTransactionId>OMXRETAIL000</ns2:cpTransactionId>
    </ns2:authReqM>
    <ns2:modUserIndiPricePlanReqM>
      <ns2:msisdn>0812345678</ns2:msisdn>
      <ns2:pricePlanChgDtoList>
        <ns2:pricePlanCode>PREPAID_SOC_NAME</ns2:pricePlanCode>
        <ns2:action>1</ns2:action>
        <ns2:effType>2</ns2:effType>
        <!-- Note: effDate/expDate use hyphens in time part (not colons) -->
        <ns2:effDate>2026-09-09 07-00-00</ns2:effDate>
        <ns2:chargeFlag>1</ns2:chargeFlag>
        <ns2:smsSendFlag>0</ns2:smsSendFlag>
        <ns2:ExtParam1>BAG123</ns2:ExtParam1>
      </ns2:pricePlanChgDtoList>
    </ns2:modUserIndiPricePlanReqM>
  </ns2:modUserIndiPricePlanReq>
</ns2:processModUserIndiPricePlan>
```

> **Date format note:** `effDate`/`expDate` use format `'yyyy-MM-dd HH-mm-ss'` — hyphens in the time part (not colons). This appears intentional for the CCP API but is non-standard ISO format.

### §9.7 — XSLT Stylesheet Variants

**Variant ① — ParentOU:** namespace prefix `ns2`, param `$psub` for subscriber MSISDN.
**Variant ② — ChildOU:** namespace prefix `ns1`, param `$csub` for subscriber MSISDN. Structurally identical otherwise.

> **Bug — ChildOU effType XPath operator precedence:**
> ChildOU variant uses:
> `exists($subOff/EffectiveDate) or exists($subOff/ExpirationDate) and ($orderRequest/OrderData/Channel!='TYC20')`
> XPath `and` has higher precedence than `or`, so this evaluates as:
> `exists(EffectiveDate) or (exists(ExpirationDate) and Channel!='TYC20')`
> The ParentOU variant correctly uses `(exists(EffectiveDate) or exists(ExpirationDate)) and Channel!='TYC20'`.
> ChildOU offers with only EffectiveDate (no ExpirationDate) and Channel=TYC20 will incorrectly receive effType=3 instead of 2.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy (ParentOU Variant)

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                              [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId                   [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                          [Conditional]
    ├── RefID                ← $refId (subOff.Soc)                                      [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType                        [Conditional]
    └── payload
        └── ns2:processModUserIndiPricePlan
            └── ns2:modUserIndiPricePlanReq
                ├── ns2:authReqM                                 [Conditional: FE_OR_CCBS = "FE"]
                │   ├── ns2:appid      ← ExtendedInfo[CCP_USER]/Value    [Credential-gated]
                │   ├── ns2:password   ← ExtendedInfo[CCP_PASSWORD]/Value [Credential-gated] [SENSITIVE]
                │   └── ns2:cpTransactionId ← tib:left(tib:pad("OMX"+Channel,"12","0"),12) [Conditional]
                └── ns2:modUserIndiPricePlanReqM
                    ├── ns2:msisdn     ← $psub/MSISDN                                 [Conditional]
                    └── ns2:pricePlanChgDtoList
                        ├── ns2:pricePlanCode  ← OrderType=45001→BRMS OfferName; else $subOff/OfferName [Conditional xsl:choose]
                        ├── ns2:action         ← 1 (add)                              [Always]
                        ├── ns2:effType        ← 3 if future-dated & Channel≠TYC20; else 2 [xsl:choose]
                        ├── ns2:effDate        ← tib:format-dateTime('yyyy-MM-dd HH-mm-ss', translate-timezone(EffectiveDate,+07:00)) [Conditional]
                        ├── ns2:expDate        ← tib:format-dateTime('yyyy-MM-dd HH-mm-ss', translate-timezone(ExpirationDate,+07:00)) [Conditional]
                        ├── ns2:chargeFlag     ← 1                                    [Always]
                        ├── ns2:smsSendFlag    ← 0                                    [Always]
                        ├── ns2:ExtParam1      ← ExtendedInfo[BAG_ID]/Value           [Conditional]
                        ├── ns2:ExtParam2      ← ExtendedInfo[BONUS]/Value            [Conditional]
                        ├── ns2:ExtParam3      ← ExtendedInfo[DURATION_DAYS]/Value    [Conditional]
                        ├── ns2:ExtParam4      ← ExtendedInfo[BONUS_UNIT]/Value       [Conditional]
                        └── ns2:ExtParam5      ← ExtendedInfo[BAG_TYPE]/Value         [Conditional]
```

**ChildOU variant** is identical but uses prefix `ns1`, param `$csub`, and has the effType operator-precedence bug described in §9.7.

---

## §11 — Audit Logging

| Event | Gate | Key fields |
|-------|------|------------|
| Request audit (per offer) | `AllowWriteLog(OrderType)` | `OPERATION_NAME="CCP_ADD_OFFER"`, `AUDIT_TRACE=concat("Request Sent for CCP_ADD_OFFER for ", refId)` — dynamic SOC in trace |
| Response audit | **Unconditional** (no AllowWriteLog check in response RF) | `OPERATION_NAME="CCP_ADD_OFFER"`, `AUDIT_TRACE="Response received for CCP_ADD_OFFER"` |

> **Response audit unconditional:** The response RF sends the audit log unconditionally (no `AllowWriteLog` gate), while the request audit is gated. Asymmetry may produce unexpected audit log volume for order types that do not normally log.

---

## §12 — Activity Status Management

| Condition | Action | Status |
|-----------|--------|--------|
| At least one offer queued | `SendFirstRequestEvent` + `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" = PROCESSING |
| No offers pass checks (all skipped/idempotent) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" = SKIPPED |

---

## §13 — Exception / Error Handling

**Request rule:** Standard `catch(Exception ae) → HandleActivityException`.

**Response RF:** No catch block — exceptions propagate. Uses `try-finally` only for debug logging. This means an exception during response processing is unhandled at the RF level.

```java
// Response RF — try-finally (no catch!)
try {
    // ... create response, log, ActionResponseEvent ...
} finally {
    Log.log(logger, "debug", "Completed %s", orderRequest@extId);
}
```

> **No catch in response RF:** If `Instance.createInstance` or `ActionResponseEvent` throws, the exception propagates to the BE rule engine. This may cause the activity to be stuck in PROCESSING state without transitioning to error.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()` | Clears queue for clean resubmit |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Enqueues offer event for sequential dispatch |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Dispatches first queued offer |
| `IntraActivitySequencing.ActionResponseEvent(currActivity)` | Dispatches next queued offer; returns true when queue exhausted |
| `Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo()` | Builds PreExecCheck XML for ParentOU subscriber offer |
| `Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo()` | Builds PreExecCheck XML for ChildOU subscriber offer |
| `Helpers.AllowWriteLog(orderType)` | Request audit gate |
| `Helpers.GetActivityStatusString(code, flag)` | Status code translation |
| `Helpers.SendDataToDB(orderRequest)` | Persist order state |
| `Helpers.SkipActivity(orderRequest, activity, code)` | Mark activity skipped |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |

---

## §15 — Function Dependency Tree

```text
Request_CCP_ADD_OFFER (rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()  [on resubmit]
├── Instance.getByExtIdByUri()
├── XPath.evalAsString()                                          [FE_OR_CCBS extraction per offer]
├── Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo()      [ParentOU PreExecCheck XML]
├── Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo() [ChildOU PreExecCheck XML]
├── XPath.execute()                                               [PreExecCheck per offer]
├── Event.createEvent()                                           [XSLT — two variants]
├── Event.assertEvent()
├── IntraActivitySequencing.ActionRequestEvent()
├── Helpers.AllowWriteLog()
├── System.nanoTime()
├── Event.Ext.sendEventImmediate()                               [audit log]
├── IntraActivitySequencing.SendFirstRequestEvent()
├── Helpers.GetActivityStatusString()
├── Helpers.SendDataToDB()
├── Helpers.SkipActivity()
└── Helpers.HandleActivityException()

Response_CCP_ADD_OFFER (rulefunction)
├── Log.getLogger() / Log.log()
├── Instance.createInstance()                                     [CCBS_AddAgreeOfferRes XSLT]
├── System.nanoTime()
├── Event.createEvent()                                          [Logger XSLT — unconditional]
├── Event.Ext.sendEventImmediate()
└── IntraActivitySequencing.ActionResponseEvent(currActivity)    [fan-in + dispatch next]
    → returns "true" when queue exhausted, "false" while more pending
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|------------|
| `Concepts.OrderRequest.OrderRequest` | Both | OrderData.Channel, OrderType, ExtendedInfo[], Customer.ParentOU/ChildOU |
| `Concepts.OM.ProcessConfig.Activity` | Both | ActivityID, Status, RequestCount, Response[], PreExecCheck |
| `Concepts.FM.Response.CCBS_AddAgreeOfferRes` | Response RF | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId; used for idempotency (CompletionStatus==2) |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Request rule | Soc, OfferName, EffectiveDate, ExpirationDate, ExtendedInfo[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | Request rule | RefId, MSISDN, SubscriberOffers[] |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Process each SubscriberOffer across all ParentOU/ChildOU subscribers sequentially via CCP ModUserIndiPricePlan |
| R2 | Per-offer idempotency: skip offers with existing successful response (CompletionStatus=2, ReferenceId=SOC) |
| R3 | Per-offer PreExecCheck with FE_OR_CCBS filter |
| R4 | Conditional credential inclusion: only for FE-type offers (FE_OR_CCBS="FE") |
| R5 | cpTransactionId: 12-char right-padded with zeros using tib:pad |
| R6 | OrderType '45001' special case: pricePlanCode from BRMS offer of first subscriber |
| R7 | effType=3 (future-dated) when EffectiveDate/ExpirationDate present and Channel≠TYC20; else effType=2 |
| R8 | ExtendedInfo BAG_ID/BONUS/DURATION_DAYS/BONUS_UNIT/BAG_TYPE → ExtParam1–5 |
| R9 | AUDIT_TRACE includes SOC refId for per-offer traceability |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Bug: ChildOU effType XPath precedence** — `exists(EffectiveDate) or exists(ExpirationDate) and Channel!='TYC20'` evaluates incorrectly. ChildOU offers with only EffectiveDate on Channel=TYC20 get effType=3 instead of 2. | [HIGH] | Add parentheses: `(exists(EffectiveDate) or exists(ExpirationDate)) and Channel!='TYC20'` |
| **Response RF has no catch block** — Exceptions during response handling propagate unhandled, potentially leaving the activity stuck in PROCESSING state. | [MEDIUM] | Add try-catch calling `HandleActivityException`, consistent with request rule |
| **Response audit unconditional** — Response RF sends audit log regardless of `AllowWriteLog(OrderType)`. Inconsistent with request RF and may cause unexpected log volume. | [LOW] | Wrap response audit in `AllowWriteLog` check |
| **OrderType 45001 hardcode** — pricePlanCode logic for OrderType='45001' uses a fixed XPath to `ParentOU[1]/Subscriber[1]` regardless of context. Multi-subscriber or multi-OU orders may get the wrong plan code. | [MEDIUM] | Externalize the special-case logic or validate that 45001 always has exactly one subscriber |
| **Date format 'HH-mm-ss' uses hyphens** — Non-standard time format in effDate/expDate. If the CCP API changes format expectations, this will silently produce malformed dates. | [LOW] | Document as intentional CCP API requirement; add test coverage for date format validation |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCP_ADD_OFFER {
    attribute { priority = 5; forwardChain = true; }
    // ... declare / when as standard ...
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        if(isActResub) IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
        try {
            // Load PreExecCheck
            String chkXPath = nextAct.PreExecCheck;
            boolean isSkipped = true;

            // ParentOU subscriber offer loop
            for(int i..) { for(int j..) { for(int k..) {
                String refId = subOff.Soc;
                String filter = /* FE_OR_CCBS */;
                // Idempotency check: skip if Response[ReferenceId==refId && CompletionStatus==2]
                if(!reqSuccess) {
                    // PreExecCheck via GetXMLForSubscriberOfferFilterWithExtendedInfo
                    if(chkRes == "true") {
                        // [ParentOU XSLT: processModUserIndiPricePlan — see §9.7]
                        Event.assertEvent(reqEvent);
                        IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                        isSkipped = false;
                        if(AllowWriteLog(...)) { /* audit log with refId in AUDIT_TRACE */ }
                    }
                }
            }}}

            // ChildOU subscriber offer loop (same pattern, ChildOU XSLT variant)
            // NOTE: ChildOU effType xsl:when has operator precedence bug (missing parentheses)

            if(!isSkipped) {
                IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                SendDataToDB(orderRequest);
            } else {
                SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch(Exception ae) { HandleActivityException(...); }
    }
}
```

---

## §19 — Response Message Rule (Response_CCP_ADD_OFFER)

### §19.1 — Overview

Creates a `CCBS_AddAgreeOfferRes` response concept, logs it (unconditionally), then calls `IntraActivitySequencing.ActionResponseEvent(currActivity)` to both dispatch the next queued offer and determine fan-in completion. Returns `"true"` when the queue is exhausted (all offers processed), `"false"` while more offers remain.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCP_ADD_OFFER` | CCP response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity; Response[] accumulates for idempotency (next request rule invocation) |

### §19.3 — CCBS_AddAgreeOfferRes Concept Construction

```text
createObject
└── object
    ├── @extId           ← OMXUtils:generateTrackingID()   [Always] (generated — not from eventResponse)
    ├── ResponseCode     ← $eventResponse/ResponseCode     [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg      [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus [Conditional] (2 = success, used by request rule idempotency)
    └── ReferenceId      ← $eventResponse/RefID            [Conditional] (should match subOff.Soc)
```

### §19.4 — Response Completion Logic

| Attribute | Value |
|-----------|-------|
| Fan-in mechanism | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Return "true" | Queue exhausted — all offers processed |
| Return "false" | More offers queued — dispatches next one |
| Idempotency integration | `ReferenceId` in response concept feeds back into request rule's idempotency check on resubmit |

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| `OPERATION_NAME` | `"CCP_ADD_OFFER"` |
| `AUDIT_TRACE` | `"Response received for CCP_ADD_OFFER"` |
| Gate | **Unconditional** (no AllowWriteLog check) |
| `payload` | Full `$eventResponse` copy, gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
