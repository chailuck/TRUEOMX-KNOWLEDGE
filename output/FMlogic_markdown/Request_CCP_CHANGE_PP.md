# Request_CCP_CHANGE_PP

FM Logic Documentation — CCP Default Price Plan Change (IntraActivitySequencing, per-offer)

**Rule:** Rules.OMConsumers.OMXFM.Request.Request_CCP_CHANGE_PP | **Priority:** 5 | **Backend:** CCP (ChangeDefaultPricePlan) | **Pattern:** IntraActivitySequencing per-offer

---

## §1 — Overview & Purpose

**CCP_CHANGE_PP** changes the default price plan for each subscriber offer via the CCP `ChangeDefaultPricePlan` API. It follows the same IntraActivitySequencing per-offer sequential dispatch pattern as CCP_ADD_OFFER, with per-offer idempotency check and PreExecCheck filtering. The payload is simpler — only `MSISDN`, `ChargeFlag`, and `PricePlanCode`. Credential gating uses a global variable (`IsEnableUserPass`) rather than per-offer `FE_OR_CCBS`.

> **Correctly wired IntraActivitySequencing:** Properly calls `IntraActivitySequencing.ActionResponseEvent(currActivity)` in the response RF — sequential per-offer dispatch works correctly.

| Attribute | Value |
|-----------|-------|
| Rule file | Request_CCP_CHANGE_PP.rule |
| Response rulefunction | Response_CCP_CHANGE_PP.rulefunction |
| Priority | 5 |
| Backend system | CCP via ESB (`ChangeDefaultPricePlan`) |
| Request event type | `Events.OMConsumers.OMXFM.Request.CCP_CHANGE_PP` |
| Response event type | `Events.OMConsumers.OMXFM.Response.CCP_CHANGE_PP` |
| Response concept | `Concepts.FM.Response.CCP_CHANGE_PP` |
| Payload schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CCP/ChangeDefaultPricePlanRequest.xsd` |
| Dispatch scope | Per SubscriberOffer — both ParentOU and ChildOU subscribers |
| XSLT variants | Two: ParentOU (`$psub`) and ChildOU (`$csub`) |
| refId key | `subOff.OfferName` (offer name — unlike CCP_ADD_OFFER which used subOff.Soc) |
| Credential gating | Global variable `IsEnableUserPass="true"` → includes `UserName`/`PassWord` from `OrderData.User`/`OrderData.Password` |

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
| 2 | `orderCurrentActivity.ActivityID == "CCP_CHANGE_PP"` | Constrains to CCP_CHANGE_PP |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCP_CHANGE_PP"` | Double-check via NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity ready |

---

## §5 — Execution Flow Diagram

1. **Resubmit purge** — if `isActResub`: `PurgePendingRequestsBeforeResubmit`
2. **Load activity config** — read `nextAct.PreExecCheck`
3. **ParentOU subscriber offer loop** — for each ParentOU → Subscriber → SubscriberOffer:
   - Extract `refId = subOff.OfferName` and `filter = FE_OR_CCBS ExtendedInfo value`
   - **Idempotency check**: scan `currActivity.Response[]` for `ReferenceId == refId && CompletionStatus == 2` → skip if found
   - Per-offer **PreExecCheck** via `GetXMLForSubscriberOfferFilterWithExtendedInfo`
   - Build ParentOU XSLT event → `assertEvent` → `ActionRequestEvent`
   - Audit log (gated on `AllowWriteLog`); AUDIT_TRACE includes `refId` (OfferName)
4. **ChildOU subscriber offer loop** — same pattern via `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo` and ChildOU XSLT variant
5. **Dispatch first** — `IntraActivitySequencing.SendFirstRequestEvent`
6. **Status** — `GetActivityStatusString("1", false)` + `SendDataToDB`; or `SkipActivity("4")`

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
if(isActResub)
    IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

try {
    String chkXPath = nextAct.PreExecCheck;
    boolean isSkipped = true;

    // ParentOU Subscriber Offer loop
    for(int p = 0; p < pOuLen; p++) {
        for(int s = 0; s < pSubLen; s++) {
            for(int o = 0; o < pOfferLen; o++) {
                String refId = subOff.OfferName; // OfferName — idempotency key (not Soc!)
                String filter = /* FE_OR_CCBS ExtendedInfo value */;

                // Idempotency: skip if ReferenceId == refId && CompletionStatus == 2
                boolean reqSuccess = false;
                for(int iResp = 0; ...) {
                    if(String.equals(Response[iResp].ReferenceId, refId) && Response[iResp].CompletionStatus == 2)
                        reqSuccess = true;
                }

                if(!reqSuccess) {
                    // PreExecCheck via GetXMLForSubscriberOfferFilterWithExtendedInfo
                    if(String.equals(chkRes, "true")) {
                        // [ParentOU XSLT: ChangeDefaultPricePlanReqDto — see §9]
                        Event.assertEvent(reqEvent);
                        IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                        isSkipped = false;
                        if(AllowWriteLog(OrderType)) { /* audit: AUDIT_TRACE includes refId */ }
                    }
                }
            }
        }

        // ChildOU Subscriber Offer loop
        for(int c = 0; c < cOuLen; c++) {
            // BUG line 86: cou = ParentOU[p].ChildOU[p] — should be ChildOU[c]
            // cOuRefId is assigned but unused — no functional impact
            // Same pattern with GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo
        }
    }

    if(!isSkipped) {
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
    } else {
        SkipActivity(orderRequest, orderCurrentActivity, "4");
    }
} catch(Exception ae) {
    HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §7 — Data Extraction

### §7.1 — Idempotency Key: refId = subOff.OfferName

> **Different from CCP_ADD_OFFER:** CCP_ADD_OFFER uses `subOff.Soc` as the refId/idempotency key. CCP_CHANGE_PP uses `subOff.OfferName`. The JMS `RefID` header and the idempotency check both key on the offer name, not the SOC code.

### §7.2 — ChargeFlag Logic

| Condition | ChargeFlag value |
|-----------|-----------------|
| `ExtendedInfo[CHARGE_FLAG]/Value` exists | Value from ExtendedInfo |
| Otherwise (default) | `0` (xsl:otherwise) |

CCP_ADD_OFFER had a static `chargeFlag=1`. CCP_CHANGE_PP defaults to `0` unless explicitly set.

### §7.3 — Credential Gating: IsEnableUserPass Global Variable

Unlike CCP_ADD_OFFER (which used per-offer `FE_OR_CCBS`), CCP_CHANGE_PP gates credentials via a global variable:

```xpath
$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass = "true"
```

When true:
- `UserName` ← `$orderRequest/OrderData/User`
- `PassWord` ← `$orderRequest/OrderData/Password` (plaintext — see §17 risks)

### §7.4 — FE_OR_CCBS Filter (PreExecCheck only)

The `FE_OR_CCBS` ExtendedInfo value is read and passed to `GetXMLForSubscriberOfferFilterWithExtendedInfo` as a PreExecCheck filter only. It does NOT control credential gating in this FM.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

No OrderType-specific payload branching (unlike CCP_ADD_OFFER's OrderType='45001' special case). `AllowWriteLog(OrderType)` gate still applies to request audit.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|------------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCP_CHANGE_PP` | ChangeDefaultPricePlan per offer (sequential) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit (AllowWriteLog-gated); AUDIT_TRACE includes OfferName |

### §8.3 — Backend API Details

| System | Operation | Protocol | Schema |
|--------|-----------|----------|--------|
| CCP | ChangeDefaultPricePlan | JMS async (IntraActivitySequencing) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CCP/ChangeDefaultPricePlanRequest.xsd` |

### §8.4 — BE Working Memory Dependencies

| Concept path | Access | Purpose |
|-------------|--------|---------|
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].OfferName` | Read | refId (idempotency key) + PricePlanCode payload field |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].ExtendedInfo[FE_OR_CCBS]` | Read | PreExecCheck filter (not credential gating) |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].ExtendedInfo[CHARGE_FLAG]` | Read | ChargeFlag value; default 0 if absent |
| `ParentOU[*].Subscriber[*].MSISDN` | Read | ns:MSISDN in payload |
| `ParentOU[*].ChildOU[*].Subscriber[*].SubscriberOffers[*].*` | Read | Same as above for ChildOU |
| `orderRequest.OrderData.User` | Read | UserName (if IsEnableUserPass="true") |
| `orderRequest.OrderData.Password` | Read | PassWord (if IsEnableUserPass="true") |
| `orderRequest.OrderData.OrderType` | Read | AllowWriteLog audit gate |
| `orderCurrentActivity.Response[]` | Read | Idempotency check per offer |

### §8.5 — ExtendedInfo Fields Used

| Key | Source | Required? | Purpose |
|-----|--------|-----------|---------|
| `FE_OR_CCBS` | SubscriberOffers.ExtendedInfo | Optional | PreExecCheck filter (passed to helper function) |
| `CHARGE_FLAG` | SubscriberOffers.ExtendedInfo | Optional | ChargeFlag value; defaults to 0 |

### §8.6 — Global Variable Dependencies

| Variable path | Used in |
|--------------|---------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Credential gating — gates UserName/PassWord fields in JMS payload |
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
| `$refId` | subOff.OfferName | subOff.OfferName |
| `$globalVariables` | globalVariables | globalVariables |
| `$psub` / `$csub` | ParentOU Subscriber | ChildOU Subscriber |
| `$subOff` | ParentOU subscriber offer | ChildOU subscriber offer |

### §9.2 — Event Container

Event type: `Events.OMConsumers.OMXFM.Request.CCP_CHANGE_PP`. Created once per offer, asserted into working memory, enqueued via `ActionRequestEvent`.

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Conditional (xsl:if) |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Conditional |
| `RefID` | `$refId` (subOff.OfferName) | Always |
| `UserName` | `$orderRequest/OrderData/User` | If `IsEnableUserPass="true"` AND User present |
| `PassWord` | `$orderRequest/OrderData/Password` | If `IsEnableUserPass="true"` AND Password present |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Conditional |

### §9.4 — Payload Root Element

Both variants use: `<ns:ChangeDefaultPricePlanReqDto>` (same namespace prefix `ns` in both ParentOU and ChildOU)

### §9.5 — Core Payload Fields

| XML element | Source | Condition |
|-------------|--------|-----------|
| `ns:MSISDN` | `$psub/MSISDN` or `$csub/MSISDN` | Always (no xsl:if) |
| `ns:ChargeFlag` | `ExtendedInfo[CHARGE_FLAG]/Value` if exists; else `0` | Always (xsl:choose) |
| `ns:PricePlanCode` | `$subOff/OfferName` | Always |

### §9.6 — Complete Generated XML Example

```xml
<ns:ChangeDefaultPricePlanReqDto
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CCP/ChangeDefaultPricePlanRequest.xsd">
  <ns:MSISDN>0812345678</ns:MSISDN>
  <ns:ChargeFlag>0</ns:ChargeFlag>  <!-- or explicit value from ExtendedInfo[CHARGE_FLAG] -->
  <ns:PricePlanCode>PREPAID_OFFER_NAME</ns:PricePlanCode>
</ns:ChangeDefaultPricePlanReqDto>

<!-- JMS headers (with IsEnableUserPass="true") -->
<!-- UserName: system_user -->
<!-- PassWord: plaintext_password  ← SENSITIVE -->
<!-- RefID: PREPAID_OFFER_NAME  ← OfferName, not SOC -->
```

> **Simpler than CCP_ADD_OFFER:** No `effType`, `effDate`, `expDate`, `chargeFlag` (static), `smsSendFlag`, or `ExtParam1–5`. No `cpTransactionId`. Just three fields in the payload body.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority               [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId     [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID            [Conditional]
    ├── RefID                ← $refId (subOff.OfferName)                 [Always]
    ├── UserName             ← $orderRequest/OrderData/User               [Conditional: IsEnableUserPass="true"]
    ├── PassWord             ← $orderRequest/OrderData/Password           [Conditional: IsEnableUserPass="true"] [SENSITIVE]
    ├── OrderType            ← $orderRequest/OrderData/OrderType          [Conditional]
    └── payload
        └── ns:ChangeDefaultPricePlanReqDto
            ├── ns:MSISDN        ← $psub/MSISDN (ParentOU) or $csub/MSISDN (ChildOU)  [Always]
            ├── ns:ChargeFlag    ← ExtendedInfo[CHARGE_FLAG]/Value if exists; else 0   [Always, xsl:choose]
            └── ns:PricePlanCode ← $subOff/OfferName                                  [Always]
```

ChildOU variant is structurally identical — uses `$csub` for MSISDN. Same namespace prefix `ns` in both variants (no ns1/ns2 split like CCP_ADD_OFFER).

---

## §11 — Audit Logging

| Event | Gate | Key fields |
|-------|------|------------|
| Request audit (per offer) | `AllowWriteLog(OrderType)` | `OPERATION_NAME="CCP_CHANGE_PP"`, `AUDIT_TRACE=concat("Request Sent for CCP_CHANGE_PP for ", refId)` — OfferName in trace |
| Response audit | **Unconditional** (no AllowWriteLog check) | `OPERATION_NAME="CCP_CHANGE_PP"`, `AUDIT_TRACE="Response received for CCP_CHANGE_PP"` |

> **Response audit unconditional:** Same asymmetry as CCP_ADD_OFFER — response RF sends audit unconditionally while request is gated by AllowWriteLog.

---

## §12 — Activity Status Management

| Condition | Action | Status |
|-----------|--------|--------|
| At least one offer queued | `SendFirstRequestEvent` + `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" = PROCESSING |
| No offers pass checks | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" = SKIPPED |

---

## §13 — Exception / Error Handling

**Request rule:** Standard `catch(Exception ae) → HandleActivityException`.

**Response RF:** No try/catch and no try/finally — bare body. Any exception propagates directly to the BE rule engine. Activity may be left stuck in PROCESSING state.

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
Request_CCP_CHANGE_PP (rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()  [on resubmit]
├── Instance.getByExtIdByUri()
├── XPath.evalAsString()                                          [FE_OR_CCBS filter extraction]
├── Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo()      [ParentOU PreExecCheck XML]
├── Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo() [ChildOU PreExecCheck XML]
├── XPath.execute()                                               [PreExecCheck per offer]
├── Event.createEvent()                                           [XSLT — ParentOU and ChildOU variants]
├── Event.assertEvent()
├── IntraActivitySequencing.ActionRequestEvent()
├── Helpers.AllowWriteLog()
├── System.nanoTime()
├── Event.Ext.sendEventImmediate()                               [request audit log]
├── IntraActivitySequencing.SendFirstRequestEvent()
├── Helpers.GetActivityStatusString()
├── Helpers.SendDataToDB()
├── Helpers.SkipActivity()
└── Helpers.HandleActivityException()

Response_CCP_CHANGE_PP (rulefunction)
├── Log.getLogger("...Response_CCP_ADD_OFFER")  ← BUG: wrong logger name (copy-paste from ADD_OFFER)
├── Log.log()
├── Instance.createInstance()                   [CCP_CHANGE_PP response concept XSLT]
├── System.nanoTime()
├── Event.createEvent()                         [Logger XSLT — unconditional]
├── Event.Ext.sendEventImmediate()
└── IntraActivitySequencing.ActionResponseEvent(currActivity)
    → returns "true" when queue exhausted, "false" while more pending
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|------------|
| `Concepts.OrderRequest.OrderRequest` | Both | OrderData.User, Password, OrderType, ExtendedInfo[], Customer.ParentOU/ChildOU |
| `Concepts.OM.ProcessConfig.Activity` | Both | ActivityID, Status, RequestCount, Response[], PreExecCheck |
| `Concepts.FM.Response.CCP_CHANGE_PP` | Response RF | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId (OfferName for idempotency) |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Request rule | OfferName (refId + PricePlanCode), ExtendedInfo[FE_OR_CCBS, CHARGE_FLAG] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | Request rule | RefId, MSISDN, SubscriberOffers[] |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Process each SubscriberOffer across all ParentOU/ChildOU subscribers sequentially via CCP ChangeDefaultPricePlan |
| R2 | Per-offer idempotency: skip offers with existing successful response (CompletionStatus=2, ReferenceId=OfferName) |
| R3 | Per-offer PreExecCheck with FE_OR_CCBS filter |
| R4 | Conditional credential inclusion: only when global var `IsEnableUserPass="true"`; uses OrderData.User/Password |
| R5 | ChargeFlag: use CHARGE_FLAG ExtendedInfo if present; default to 0 |
| R6 | PricePlanCode: always from subOff.OfferName (no OrderType special case) |
| R7 | AUDIT_TRACE includes OfferName refId for per-offer traceability |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Bug: Response RF wrong logger name** — Uses `"RuleFunctions.OrderResponse.Response_CCP_ADD_OFFER"` instead of `Response_CCP_CHANGE_PP`. Debug logs appear under ADD_OFFER logger name. | [MEDIUM] | Change logger name to `"RuleFunctions.OrderResponse.Response_CCP_CHANGE_PP"` |
| **Bug: ChildOU loop variable index** — Line 86: `cou = ParentOU[p].ChildOU[p]` (should be `ChildOU[c]`). `cOuRefId` is never used, so no functional impact. | [LOW] | Change `.ChildOU[p]` to `.ChildOU[c]` for correctness and readability |
| **Password plaintext in JMS message** — When `IsEnableUserPass="true"`, `OrderData.Password` is embedded in the JMS payload without masking. | [MEDIUM] | Mask or encrypt credentials before inclusion; or move to a dedicated credential store |
| **No exception handling in response RF** — No try/catch or try/finally. Exceptions propagate unhandled. | [MEDIUM] | Add try-catch calling `HandleActivityException` |
| **Response audit unconditional** — No AllowWriteLog gate in response RF. | [LOW] | Wrap response audit in `AllowWriteLog` check for consistency |
| **refId = OfferName vs Soc inconsistency** — CCP_ADD_OFFER uses Soc as refId; CCP_CHANGE_PP uses OfferName. If an order has multiple offers with same OfferName on different SOCs, idempotency may incorrectly skip a second offer. | [MEDIUM] | Verify OfferName is unique per subscriber in PREPAID_REGISTRATION scenarios |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCP_CHANGE_PP {
    attribute { priority = 5; forwardChain = true; }
    // ... declare / when as standard ...
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        if(isActResub) IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
        try {
            String chkXPath = nextAct.PreExecCheck;
            boolean isSkipped = true;

            // ParentOU subscriber offer loop
            for(int p..; s..; o..) {
                String refId = subOff.OfferName;  // OfferName (not Soc)
                // Idempotency + PreExecCheck + GetXMLForSubscriberOfferFilterWithExtendedInfo
                // [ParentOU XSLT: ChangeDefaultPricePlanReqDto — see §9.5]
                IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                isSkipped = false;
                if(AllowWriteLog(OrderType)) { /* audit: AUDIT_TRACE includes refId (OfferName) */ }
            }

            // ChildOU subscriber offer loop
            // BUG line 86: cou = ParentOU[p].ChildOU[p] (should be ChildOU[c]) — cOuRefId unused, no impact
            for(int c..; s..; o..) {
                // Same pattern with GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo
            }

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

## §19 — Response Message Rule (Response_CCP_CHANGE_PP)

### §19.1 — Overview

Creates a `CCP_CHANGE_PP` response concept, logs it (unconditionally), then calls `IntraActivitySequencing.ActionResponseEvent(currActivity)` to dispatch the next queued offer and determine fan-in completion. Returns `"true"` when the queue is exhausted, `"false"` while more offers remain. **No try/catch or try/finally — bare body.**

> **Bug: Wrong logger name** — `Log.getLogger("RuleFunctions.OrderResponse.Response_CCP_ADD_OFFER")` — copy-paste from CCP_ADD_OFFER RF. Debug logs appear under the ADD_OFFER logger name.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCP_CHANGE_PP` | CCP response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity; Response[] accumulates for idempotency |

### §19.3 — CCP_CHANGE_PP Response Concept Construction

```text
createObject
└── object
    ├── @extId           ← OMXUtils:generateTrackingID()   [Always] (generated)
    ├── ResponseCode     ← $eventResponse/ResponseCode     [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg      [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus [Conditional] (2 = success)
    └── ReferenceId      ← $eventResponse/RefID            [Conditional] (should match subOff.OfferName)
```

### §19.4 — Response Completion Logic

| Attribute | Value |
|-----------|-------|
| Fan-in mechanism | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Return "true" | Queue exhausted — all offers processed |
| Return "false" | More offers queued — dispatches next one |

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| `OPERATION_NAME` | `"CCP_CHANGE_PP"` |
| `AUDIT_TRACE` | `"Response received for CCP_CHANGE_PP"` |
| Gate | **Unconditional** (no AllowWriteLog check) |
| `payload` | Full `$eventResponse` copy, gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
