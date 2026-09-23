# Request_CCP_REMOVE_OFFER

FM Logic Documentation — CCP Price Plan Removal via processModUserIndiPricePlan (IntraActivitySequencing per-SubscriberOffer, FE/CCP credential gate, Shared CCP_ADD_OFFER event)

---

## §1 — Overview & Purpose

**CCP_REMOVE_OFFER** removes price plan offers from CCP for each subscriber offer in the order, using the `processModUserIndiPricePlan` API with `action=2` (removal). It operates on SubscriberOffers from working memory — both offers originally in the order *and* offers dynamically added by the preceding **GET_PROFILE_FROM_CCP** activity (which appended grading-tier offers with FE_OR_CCBS=CCP).

Uses the **IntraActivitySequencing** pattern to serialize removal requests one-by-one. The CCP API is shared with the add-offer operation — this FM reuses the `CCP_ADD_OFFER` event type (same JMS channel/schema) with `action=2` to indicate removal.

The `authReqM` credentials section is conditionally populated only when `FE_OR_CCBS="FE"`; CCP-routed offers (FE_OR_CCBS="CCP") skip the credential block entirely. The `cpTransactionId` is constructed as a 12-character padded string: `tib:left(tib:pad(concat("OMX", Channel), "12", "0"), 12)`.

> **[HIGH] ChildOU effType operator precedence bug:** The ChildOU XSLT's `xsl:choose` condition lacks parentheses:
> `exists(EffectiveDate) or exists(ExpirationDate) and Channel!='TYC20'`
> XPath evaluates `and` before `or`, so this reads as:
> `exists(EffectiveDate) OR (exists(ExpirationDate) AND Channel!='TYC20')`
> The ParentOU variant has the correct parenthesized form. For ChildOU, if EffectiveDate exists, effType=3 regardless of TYC20 channel — wrong for TYC20 orders.

| Attribute | Value |
|-----------|-------|
| Rule file | Request_CCP_REMOVE_OFFER.rule |
| Response rulefunction | Response_CCP_REMOVE_OFFER.rulefunction |
| Priority | 5 |
| Backend system | CCP via `processModUserIndiPricePlan` API (action=2 = remove) |
| Request event type | `Events.OMConsumers.OMXFM.Request.CCP_ADD_OFFER` (shared — same as CCP_ADD_OFFER FM) |
| Response event type | `Events.OMConsumers.OMXFM.Response.CCP_ADD_OFFER` (shared) |
| Response concept | `Concepts.FM.Response.CCBS_AddAgreeOfferRes` (not ResponseBase — custom concept) |
| Payload schema | `ns2: http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CCP_ModUserIndiPricePlanRequest.xsd` |
| Dispatch scope | Per SubscriberOffer — ParentOU and ChildOU (triple nested loop) |
| Dispatch pattern | IntraActivitySequencing (assertEvent → ActionRequestEvent → SendFirstRequestEvent) |
| Idempotency key | `subOff.Soc` (NOTE: uses Soc field, not OfferName) |
| CCP action code | `2` (static — removal operation) |
| Credential gate | FE credentials only if `FE_OR_CCBS="FE"`; CCP-routed offers skip authReqM credentials |
| Request audit | Conditional: `AllowWriteLog(OrderType)`; AUDIT_TRACE includes refId dynamically |
| Response audit | Unconditional (no AllowWriteLog gate) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM priority |
| forwardChain | true | Standard |
| Rule type | IntraActivitySequencing | PurgePendingRequestsBeforeResubmit → assertEvent → ActionRequestEvent → SendFirstRequestEvent; fan-in via ActionResponseEvent |
| Resubmit | Yes | PurgePendingRequestsBeforeResubmit called OUTSIDE try block (before loop); idempotency via CompletionStatus=2 + subOff.Soc |

> **Note: PurgePendingRequestsBeforeResubmit is outside the try block** — called at the top of the rule THEN before the try/catch. This means if Purge throws, it's an uncaught exception (no HandleActivityException). All other FMs with IntraActivitySequencing call Purge inside try.

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order; ParentOU/ChildOU/Subscriber/SubscriberOffer loops; Channel, ExtendedInfo[CCP_USER/CCP_PASSWORD] for credentials |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[] for idempotency; IntraActivitySequencing queue management |
| `nextAct` | `Concepts.OM.ProcessConfig.Activity` | Loaded by extId; provides PreExecCheck XPath expression |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId matches |
| 2 | `orderCurrentActivity.ActivityID == "CCP_REMOVE_OFFER"` | Constrains to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCP_REMOVE_OFFER"` | Double-check via NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity ready to process |

---

## §5 — Execution Flow Diagram

1. **Resubmit check**: `isActResub = RequestCount > 0 && IsOrderResubmitted`; if true → `PurgePendingRequestsBeforeResubmit` (NOTE: called OUTSIDE try block)
2. **Load nextAct**, read PreExecCheck XPath; `isSkipped = true`
3. **ParentOU loop** (OU[i] → Subscriber[j] → Offer[k]): for each offer:
   - `refId = subOff.Soc`; `filter = subOff/ExtendedInfo[FE_OR_CCBS]/Value`
   - Idempotency: scan Response[] for `ReferenceId == refId && CompletionStatus == 2`
   - PreExecCheck: `GetXMLForSubscriberOfferFilterWithExtendedInfo` → XPath eval
   - Build `CCP_ADD_OFFER` event (action=2); `assertEvent` → `ActionRequestEvent`
   - Conditional audit: `if(AllowWriteLog)`; AUDIT_TRACE includes refId
   - `isSkipped = false`
4. **ChildOU loop** — same pattern with `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo`
5. **SendFirstRequestEvent** if any queued; `GetActivityStatusString("1", false)` + `SendDataToDB`; else `SkipActivity("4")`

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
// PurgePendingRequestsBeforeResubmit is OUTSIDE try block (unique to this FM)
if(isActResub) PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

try {
    Activity nextAct = Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
    String chkXPath = nextAct.PreExecCheck;
    boolean isSkipped = true;

    for(int i...) { // ParentOU
        for(int j...) { // Subscriber
            for(int k...) { // SubscriberOffer
                String refId = subOff.Soc; // idempotency key — Soc not OfferName
                String filter = XPath(subOff/ExtendedInfo[FE_OR_CCBS]/Value);
                // Idempotency check on Response[]
                if(!reqSuccess) {
                    if(chkXPath.length > 0) {
                        sXML = GetXMLForSubscriberOfferFilterWithExtendedInfo(...);
                        chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=...");
                    }
                    if(chkRes == "true") {
                        /* CCP_ADD_OFFER XSLT (action=2) — see §9 */
                        Event.assertEvent(reqEvent);
                        IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                        isSkipped = false;
                        if(AllowWriteLog(OrderType)) { /* Logger — AUDIT_TRACE includes refId */ }
                    }
                }
            }
        }
        // ChildOU loop (GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo)
        // effType condition BUG in ChildOU XSLT — missing parentheses
    }

    if(!isSkipped) {
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
    } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
} catch(Exception ae) { HandleActivityException(...); }
```

---

## §7 — Data Extraction & Pre-Processing

### §7.1 — Idempotency Key: subOff.Soc

`refId = subOff.Soc` — the idempotency key is the offer's **Soc** field, not `OfferName`. This is important: GET_PROFILE_FROM_CCP populates dynamically created SubscriberOffers with `OfferName = PricePlanName`. For those offers to be idempotent in CCP_REMOVE_OFFER, the `Soc` field must also be set (or Soc and OfferName must be the same). If the dynamically created offers have an empty or different Soc, the idempotency check on resubmit will not work for those offers.

### §7.2 — FE_OR_CCBS Filter

`filter = XPath.evalAsString("$subOff/ExtendedInfo[Name=\"FE_OR_CCBS\"]/Value", subOff)` — determines credential behavior and PreExecCheck routing. Possible values: `"FE"` (FE-routed, sends credentials) or `"CCP"` (CCP-routed, dynamically added by GET_PROFILE_FROM_CCP, skips credentials).

### §7.3 — effType Business Logic

| Condition | effType value | Meaning | ParentOU | ChildOU |
|-----------|--------------|---------|---------|---------|
| (EffectiveDate OR ExpirationDate) AND Channel != 'TYC20' | 3 = scheduled/future | Schedule for specific effective/expiry date | ✓ Correct (parenthesized) | **[BUG: missing parens]** |
| Otherwise (incl. TYC20 or no dates) | 2 = immediate | Immediate removal | ✓ Correct | ✓ Correct (unless EffectiveDate exists) |

> **[HIGH] ChildOU effType operator precedence bug:**
> ChildOU condition: `exists($subOff/EffectiveDate) or exists($subOff/ExpirationDate) and ($orderRequest/OrderData/Channel!='TYC20')`
> XPath evaluates `and` before `or`: `exists(EffectiveDate) OR (exists(ExpirationDate) AND Channel!='TYC20')`
> ParentOU (correct): `(exists($subOff/EffectiveDate) or exists($subOff/ExpirationDate)) and ($orderRequest/OrderData/Channel!='TYC20')`
>
> **Impact:** For ChildOU subscribers with an EffectiveDate on TYC20 channel, CCP_REMOVE_OFFER sends effType=3 (scheduled) instead of effType=2 (immediate).

### §7.4 — cpTransactionId Construction

`tib:left(tib:pad(concat("OMX", Channel), "12", "0"), 12)`

- Concatenates `"OMX"` + Channel value (e.g., "OMX" + "web" = "OMXweb")
- Pads to at least 12 chars with "0" fill (e.g., "OMXweb000000")
- Truncates to exactly 12 chars
- Only emitted when both CCP_USER and CCP_PASSWORD exist in order ExtendedInfo

### §7.5 — Shared CCP_ADD_OFFER Event

CCP_REMOVE_OFFER uses the same JMS event type as CCP_ADD_OFFER (`Events.OMConsumers.OMXFM.Request.CCP_ADD_OFFER`). The operation direction is determined solely by the static `ns2:action` field: **2 = remove**. The add operation uses a different action value. This shared-channel pattern means both operations use the same CCP ESB endpoint and response correlation.

### §7.6 — Credential Gate Logic (FE vs. CCP)

| FE_OR_CCBS value | authReqM appid/password | cpTransactionId | Scenario |
|-----------------|------------------------|-----------------|---------|
| `"FE"` | From `ExtendedInfo[CCP_USER]` and `ExtendedInfo[CCP_PASSWORD]` (each conditional) | Emitted if both CCP_USER and CCP_PASSWORD exist | FE-originated offer removal |
| `"CCP"` (or other) | Not emitted (no xsl:if matches) | Still emitted if CCP_USER and CCP_PASSWORD exist | CCP grading offer removal (from GET_PROFILE_FROM_CCP) |

> The `cpTransactionId` is emitted whenever CCP_USER and CCP_PASSWORD exist in the order, regardless of FE_OR_CCBS. Only appid and password are gated on `FE_OR_CCBS="FE"`.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Operates on SubscriberOffers tagged with FE_OR_CCBS extension info. Consumes offers from the original order AND offers dynamically added by GET_PROFILE_FROM_CCP (FE_OR_CCBS=CCP). Used for PREPAID_REMOVE_PACKAGE orders removing CCP price plans.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCP_ADD_OFFER` | CCP processModUserIndiPricePlan action=2 (remove) per SubscriberOffer (IntraActivitySequencing) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit (conditional: AllowWriteLog); AUDIT_TRACE includes refId |

### §8.3 — Backend API Details

| System | Operation | Schema | action |
|--------|-----------|--------|--------|
| CCP | `processModUserIndiPricePlan` | `CCP_ModUserIndiPricePlanRequest.xsd` (ns2) | `2` (remove; contrast: add uses action=1) |

### §8.4 — BE Working Memory Dependencies

| Concept path | Access | Purpose |
|-------------|--------|---------|
| `ProcessFlow.NextActivityName` | Read | Load nextAct for PreExecCheck |
| `nextAct.PreExecCheck` | Read | Dynamic PreExecCheck XPath expression |
| `ParentOU[*].RefId` | Read | pOuRefId — passed to ChildOU PreExecCheck helper |
| `ParentOU[*].Subscriber[*].RefId` | Read | psub.RefId — passed to ParentOU PreExecCheck helper |
| `ParentOU[*].Subscriber[*].MSISDN` | Read (via $psub) | ns2:msisdn in CCP payload |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].Soc` | Read | refId (idempotency key) |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].OfferName` | Read (via $subOff) | ns2:pricePlanCode; also PreExecCheck helper param |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].EffectiveDate` | Read (via $subOff) | ns2:effDate (conditional); effType decision |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].ExpirationDate` | Read (via $subOff) | ns2:expDate (conditional); effType decision |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].ExtendedInfo[]` | Read (via $subOff) | FE_OR_CCBS filter; BAG_ID, BONUS, DURATION_DAYS, BONUS_UNIT, BAG_TYPE for ExtParams |
| `OrderData.Channel` | Read (via $orderRequest) | cpTransactionId construction; effType TYC20 gate |
| `OrderData.ExtendedInfo[CCP_USER]` | Read (via $orderRequest) | ns2:appid (FE gate) |
| `OrderData.ExtendedInfo[CCP_PASSWORD]` | Read (via $orderRequest) | ns2:password (FE gate) |
| `ChildOU[*].OUId/RefId/Subscriber/SubscriberOffers` | Read | Same as ParentOU equivalents |

### §8.5 — ExtendedInfo Fields Required

| Name | Source | Required? | Used for |
|------|--------|-----------|---------|
| `FE_OR_CCBS` | SubscriberOffer | Yes (routing) | FE credential gate in authReqM; PreExecCheck XML construction |
| `CCP_USER` | OrderData | Conditional | ns2:appid (FE-gated) |
| `CCP_PASSWORD` | OrderData | Conditional | ns2:password (FE-gated) |
| `BAG_ID` | SubscriberOffer | Optional | ns2:ExtParam1 |
| `BONUS` | SubscriberOffer | Optional | ns2:ExtParam2 |
| `DURATION_DAYS` | SubscriberOffer | Optional | ns2:ExtParam3 |
| `BONUS_UNIT` | SubscriberOffer | Optional | ns2:ExtParam4 |
| `BAG_TYPE` | SubscriberOffer | Optional | ns2:ExtParam5 |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameters

| Param | Source (ParentOU) | Source (ChildOU) |
|-------|------------------|-----------------|
| `$orderRequest` | orderRequest concept | orderRequest concept |
| `$refId` | `subOff.Soc` | `subOff.Soc` |
| `$subOff` | SubscriberOffers[k] | SubscriberOffers[k] |
| `$psub` | ParentOU[i].Subscriber[j] | – |
| `$csub` | – | ChildOU[p].Subscriber[q] |

### §9.2 — Event Container

No extId attribute on the event. Event type: `Events.OMConsumers.OMXFM.Request.CCP_ADD_OFFER` (reused for removal via action=2).

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Conditional: xsl:if |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Conditional: xsl:if |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Conditional: xsl:if |
| `RefID` | `$refId` (= subOff.Soc) | **Always** |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Conditional: xsl:if |

### §9.4 — Payload Root

`ns2:processModUserIndiPricePlan / ns2:modUserIndiPricePlanReq`

### §9.5 — Payload Fields — authReqM Section

| Element | Source | Condition |
|---------|--------|-----------|
| `ns2:appid` | `ExtendedInfo[Name="CCP_USER"]/Value` | Double gate: FE_OR_CCBS="FE" AND CCP_USER exists |
| `ns2:password` | `ExtendedInfo[Name="CCP_PASSWORD"]/Value` | Double gate: FE_OR_CCBS="FE" AND CCP_PASSWORD exists |
| `ns2:cpTransactionId` | `tib:left(tib:pad(concat("OMX", Channel), "12", "0"), 12)` | Both CCP_USER and CCP_PASSWORD exist (not FE-gated) |

### §9.6 — Payload Fields — modUserIndiPricePlanReqM Section

| Element | Source | Condition | Notes |
|---------|--------|-----------|-------|
| `ns2:msisdn` | `$psub/MSISDN` (or `$csub/MSISDN`) | xsl:if MSISDN exists | Subscriber MSISDN |
| `ns2:pricePlanCode` | `$subOff/OfferName` | xsl:if OfferName exists | Price plan code to remove |
| `ns2:action` | `2` | Always (static) | **2 = remove** operation |
| `ns2:effType` | 3 or 2 | xsl:choose | 3=scheduled (EffectiveDate/ExpirationDate + non-TYC20); 2=immediate. ChildOU has bug. |
| `ns2:effDate` | `tib:format-dateTime('yyyy-MM-dd HH-mm-ss', tib:translate-timezone(EffectiveDate, '+07:00'))` | EffectiveDate exists | ICT (UTC+7); format uses dashes (not colons) for time |
| `ns2:expDate` | Same as effDate but ExpirationDate | ExpirationDate exists | Same ICT conversion |
| `ns2:chargeFlag` | `1` | Always (static) | Charge upon removal |
| `ns2:smsSendFlag` | `0` | Always (static) | Do not send SMS notification |
| `ns2:ExtParam1` | `ExtendedInfo[Name="BAG_ID"]/Value` | Optional | Bag identifier |
| `ns2:ExtParam2` | `ExtendedInfo[Name="BONUS"]/Value` | Optional | Bonus value |
| `ns2:ExtParam3` | `ExtendedInfo[Name="DURATION_DAYS"]/Value` | Optional | Duration in days |
| `ns2:ExtParam4` | `ExtendedInfo[Name="BONUS_UNIT"]/Value` | Optional | Bonus unit |
| `ns2:ExtParam5` | `ExtendedInfo[Name="BAG_TYPE"]/Value` | Optional | Bag type identifier |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent (type: Events.OMConsumers.OMXFM.Request.CCP_ADD_OFFER)
└── event  (no @extId)
    ├── JMSPriority       ← $orderRequest/OrderPriority                    [Conditional: xsl:if]
    ├── JMSCorrelationID  ← $orderRequest/OrderData/OMXTrackingId          [Conditional: xsl:if]
    ├── OrderID           ← $orderRequest/OrderData/OrderID                [Conditional: xsl:if]
    ├── RefID             ← $refId (subOff.Soc)                           [Always]
    ├── OrderType         ← $orderRequest/OrderData/OrderType              [Conditional: xsl:if]
    └── payload
        └── ns2:processModUserIndiPricePlan
            └── ns2:modUserIndiPricePlanReq
                ├── ns2:authReqM
                │   ├── ns2:appid            ← ExtendedInfo[CCP_USER]/Value    [FE_OR_CCBS="FE" AND CCP_USER exists]
                │   ├── ns2:password         ← ExtendedInfo[CCP_PASSWORD]/Value [FE_OR_CCBS="FE" AND CCP_PASSWORD exists]
                │   └── ns2:cpTransactionId  ← tib:left(tib:pad(concat("OMX",Channel),"12","0"),12)  [CCP_USER AND CCP_PASSWORD exist]
                └── ns2:modUserIndiPricePlanReqM
                    ├── ns2:msisdn           ← $psub/MSISDN (ParentOU) or $csub/MSISDN (ChildOU)    [Conditional]
                    └── ns2:pricePlanChgDtoList
                        ├── ns2:pricePlanCode ← $subOff/OfferName            [Conditional]
                        ├── ns2:action        ← 2 (static = remove)          [Always]
                        ├── ns2:effType       ← 3 or 2 (xsl:choose)          [Conditional: ParentOU correct, ChildOU has op-precedence bug]
                        ├── ns2:effDate       ← format-dateTime(EffectiveDate→ICT)   [if EffectiveDate exists]
                        ├── ns2:expDate       ← format-dateTime(ExpirationDate→ICT)  [if ExpirationDate exists]
                        ├── ns2:chargeFlag    ← 1 (static)                   [Always]
                        ├── ns2:smsSendFlag   ← 0 (static)                   [Always]
                        ├── ns2:ExtParam1     ← ExtendedInfo[BAG_ID]/Value   [Optional]
                        ├── ns2:ExtParam2     ← ExtendedInfo[BONUS]/Value    [Optional]
                        ├── ns2:ExtParam3     ← ExtendedInfo[DURATION_DAYS]/Value  [Optional]
                        ├── ns2:ExtParam4     ← ExtendedInfo[BONUS_UNIT]/Value     [Optional]
                        └── ns2:ExtParam5     ← ExtendedInfo[BAG_TYPE]/Value       [Optional]
```

ChildOU variant: params change to ($orderRequest, $refId, $subOff, $csub); msisdn source changes to $csub/MSISDN; namespace prefix changes from ns2 to ns1; effType condition has operator precedence bug.

---

## §11 — Audit Logging

| Event | Gate | OPERATION_NAME | AUDIT_TRACE | Bug? |
|-------|------|---------------|-------------|------|
| Request audit | `AllowWriteLog(OrderType)` | `"CCP_REMOVE_OFFER"` ✓ | `concat("Request Sent for CCP_REMOVE_OFFER for ", $refId)` ✓ | None (refId included dynamically) |
| Response audit | Unconditional (no AllowWriteLog) | `"CCP_REMOVE_OFFER"` ✓ | `"Response received for CCP_REMOVE_OFFER"` ✓ | None |

> Request audit is conditional (AllowWriteLog-gated) while response audit is unconditional — asymmetric gating. The request AUDIT_TRACE is unique among all FMs: it dynamically includes the `refId` (subOff.Soc), making it easy to trace individual offer operations in audit logs.

---

## §12 — Activity Status Management

| Condition | Action | Status |
|-----------|--------|--------|
| At least one offer queued and sent | `SendFirstRequestEvent` → `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" = PROCESSING |
| No offers pass checks | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" = SKIPPED |

---

## §13 — Exception / Error Handling

**Request rule:** Standard `catch(Exception ae) → HandleActivityException`. However, `PurgePendingRequestsBeforeResubmit` is called OUTSIDE the try block — if it throws, it propagates uncaught.

**Response RF:** Uses `try/finally` (no catch). The `finally` block logs completion. If `IntraActivitySequencing.ActionResponseEvent` or concept creation throws, the exception propagates after the finally log. This is the only FM response RF with try/finally instead of no try/catch.

> The `PurgePendingRequestsBeforeResubmit` outside the try block is a defensive design error — it can leave the activity in an inconsistent state if it throws. Compare: SBM_CANCEL_PACK_PREPAID_NEXT calls Purge inside try. The try/finally in the response RF is safer than no try/catch (ensures log completes), but still propagates exceptions upward.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears pending queue on resubmit (called OUTSIDE try block) |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Enqueues request event for sequential dispatch |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Sends the first queued event to start dispatch chain |
| `IntraActivitySequencing.ActionResponseEvent(activity)` | Fan-in: returns true when all queued requests have been responded to |
| `Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, offerName, filter)` | Builds PreExecCheck XML for ParentOU subscriber offer |
| `Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, refId, offerName, pOuRefId, filter)` | Builds PreExecCheck XML for ChildOU subscriber offer |
| `Helpers.AllowWriteLog(orderType)` | Request audit gate (response audit is unconditional) |
| `Helpers.GetActivityStatusString(code, flag)` | Status code translation |
| `Helpers.SendDataToDB(orderRequest)` | Persist order state |
| `Helpers.SkipActivity(orderRequest, activity, code)` | Mark activity skipped |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |

---

## §15 — Function Dependency Tree

```text
Request_CCP_REMOVE_OFFER (rule)
├── [isActResub check]
│   └── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()  [OUTSIDE try — uncaught risk]
├── try {
│   ├── Instance.getByExtIdByUri()               [load nextAct for PreExecCheck]
│   ├── [ParentOU/ChildOU/Offer loops]
│   │   ├── XPath.evalAsString()                 [FE_OR_CCBS filter from subOff]
│   │   ├── [idempotency check on Response[]]
│   │   ├── Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo()   [ParentOU PreExecCheck]
│   │   ├── Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo()  [ChildOU PreExecCheck]
│   │   ├── XPath.execute()                      [PreExecCheck evaluation]
│   │   ├── Event.createEvent()                  [CCP_ADD_OFFER XSLT — action=2, see §9]
│   │   ├── Event.assertEvent()                  [IntraActivitySequencing enqueue]
│   │   ├── IntraActivitySequencing.ActionRequestEvent()
│   │   ├── Helpers.AllowWriteLog()              [request audit gate]
│   │   ├── System.nanoTime()
│   │   ├── Event.createEvent()                  [Logger XSLT — conditional audit, AUDIT_TRACE includes refId]
│   │   └── Event.Ext.sendEventImmediate()       [request audit]
│   ├── IntraActivitySequencing.SendFirstRequestEvent()
│   ├── Helpers.GetActivityStatusString()
│   ├── Helpers.SendDataToDB()
│   └── Helpers.SkipActivity()
└── catch → Helpers.HandleActivityException()

Response_CCP_REMOVE_OFFER (rulefunction)
├── Log.getLogger() / Log.log()                  [Java logger — debug start]
├── try {
│   ├── Instance.createInstance()                [CCBS_AddAgreeOfferRes XSLT — OMXUtils:generateTrackingID()]
│   ├── currActivity.Response[] ← activityRes
│   ├── System.nanoTime()
│   ├── Event.createEvent()                      [Logger XSLT — UNCONDITIONAL response audit]
│   ├── Event.Ext.sendEventImmediate()           [response audit]
│   └── IntraActivitySequencing.ActionResponseEvent(currActivity)
│       → "true" (queue exhausted)
│       → "false" (still waiting)
└── finally {
    └── Log.log()                                [Java logger — debug complete]
    }
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | Both | OrderData.Channel, ExtendedInfo[CCP_USER/CCP_PASSWORD], ParentOU/ChildOU/Subscriber/SubscriberOffers |
| `Concepts.OM.ProcessConfig.Activity` | Both | ActivityID, Status, PreExecCheck, Response[] (idempotency + queue) |
| `Concepts.FM.Response.CCBS_AddAgreeOfferRes` | Response RF | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Request rule | Soc (idempotency key), OfferName (pricePlanCode), EffectiveDate, ExpirationDate, ExtendedInfo[FE_OR_CCBS, BAG_ID, BONUS, DURATION_DAYS, BONUS_UNIT, BAG_TYPE] |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | For each SubscriberOffer (across ParentOU and ChildOU), call CCP processModUserIndiPricePlan with action=2 (remove) |
| R2 | Per-offer idempotency: skip if Response[].ReferenceId == subOff.Soc and CompletionStatus == 2 |
| R3 | IntraActivitySequencing: queue all qualifying offers then SendFirstRequestEvent; response fan-in via ActionResponseEvent returning "true" when queue exhausted |
| R4 | FE credential gate: emit authReqM.appid and authReqM.password only when FE_OR_CCBS="FE"; emit cpTransactionId whenever CCP_USER and CCP_PASSWORD both exist |
| R5 | effType: 3 (scheduled) when (EffectiveDate OR ExpirationDate) AND channel != 'TYC20'; 2 (immediate) otherwise |
| R6 | Date format for effDate/expDate: 'yyyy-MM-dd HH-mm-ss' after ICT (UTC+7) translation via tib:translate-timezone |
| R7 | Static fields: chargeFlag=1, smsSendFlag=0, action=2 |
| R8 | Optional ExtParams 1-5 from offer's BAG_ID, BONUS, DURATION_DAYS, BONUS_UNIT, BAG_TYPE ExtendedInfo |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **ChildOU effType operator precedence bug:** Missing parentheses in xsl:choose. For ChildOU TYC20 channel orders with EffectiveDate, effType=3 instead of effType=2. | [HIGH] | Add parentheses: `(exists($subOff/EffectiveDate) or exists($subOff/ExpirationDate)) and ($orderRequest/OrderData/Channel!='TYC20')` (match ParentOU variant) |
| **Idempotency key is subOff.Soc, not OfferName:** GET_PROFILE_FROM_CCP creates SubscriberOffers with OfferName=PricePlanName. If Soc is empty for dynamically-created offers, resubmit idempotency fails. | [HIGH] | Verify GET_PROFILE_FROM_CCP also sets Soc=PricePlanName; or change idempotency key to OfferName |
| **PurgePendingRequestsBeforeResubmit outside try block:** If Purge throws, uncaught exception leaves activity in inconsistent state. | [MEDIUM] | Move Purge call inside the try block (match SBM_CANCEL_PACK_PREPAID_NEXT pattern) |
| **Response RF try/finally — no catch:** If concept creation or ActionResponseEvent throws, exception propagates uncaught after finally log. | [MEDIUM] | Add catch block to call HandleActivityException |
| **Asymmetric audit gating:** Request audit conditional; response audit unconditional. | [LOW] | Decide on consistent gating strategy |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCP_REMOVE_OFFER {
    attribute { priority = 5; forwardChain = true; }
    then {
        boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
        // OUTSIDE try block — uncaught if throws
        if(isActResub) PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
        try {
            Activity nextAct = Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
            String chkXPath = nextAct.PreExecCheck;
            boolean isSkipped = true;

            for(int i...) { // ParentOU
                for(int j...) { // Subscriber
                    for(int k...) { // SubscriberOffer
                        String refId = subOff.Soc; // idempotency key
                        String filter = XPath(subOff/ExtendedInfo[FE_OR_CCBS]/Value);
                        if(!reqSuccess) {
                            if(chkXPath.length > 0) {
                                sXML = GetXMLForSubscriberOfferFilterWithExtendedInfo(...);
                                chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=...");
                            }
                            if(chkRes == "true") {
                                /* CCP_ADD_OFFER XSLT action=2 — see §9 */
                                Event.assertEvent(reqEvent);
                                IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                                isSkipped = false;
                                if(AllowWriteLog(OrderType)) { /* Logger — AUDIT_TRACE includes refId */ }
                            }
                        }
                    }
                }
                // ChildOU loop (GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo)
                // effType condition BUG in ChildOU XSLT — missing parentheses
            }

            if(!isSkipped) {
                IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                SendDataToDB(orderRequest);
            } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
        } catch(Exception ae) { HandleActivityException(...); }
    }
}
```

---

## §19 — Response Message Rule (Response_CCP_REMOVE_OFFER)

### §19.1 — Overview

Standard IntraActivitySequencing response handler. Creates a `CCBS_AddAgreeOfferRes` concept (same fields as ResponseBase but a different concept type — likely reused from the CCP_ADD_OFFER FM). Logs unconditionally. Delegates fan-in to `ActionResponseEvent`.

**Event type consumed:** `Events.OMConsumers.OMXFM.Response.CCP_ADD_OFFER` (shared with CCP_ADD_OFFER).

**Uses try/finally (no catch)** — unique among all documented response RFs. Java logger used in addition to audit event.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context for audit logging |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCP_ADD_OFFER` | CCP response event; carries ResponseCode, RefID, CompletionStatus |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity; Response[] written to; fan-in managed by ActionResponseEvent |

### §19.3 — CCBS_AddAgreeOfferRes Construction

```text
createObject  (Concepts.FM.Response.CCBS_AddAgreeOfferRes)
└── object
    ├── @extId            ← OMXUtils:generateTrackingID()          [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode            [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg             [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus        [Conditional]
    └── ReferenceId       ← $eventResponse/RefID                   [Conditional]
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
| `OPERATION_NAME` | `"CCP_REMOVE_OFFER"` ✓ |
| `AUDIT_TRACE` | `"Response received for CCP_REMOVE_OFFER"` ✓ |
| Gate | **Unconditional** (no AllowWriteLog — unlike request audit) |
| `PROCESS_ID` | `concat($pid, "_RES")` |
| `payload` | Full `$eventResponse` copy, gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
