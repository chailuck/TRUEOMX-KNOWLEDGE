# Request_OMX_ADD_NEXT_OFFER

> TIBCO BusinessEvents FM Logic — Next Offer Scheduling (futureType=NXTOFR)

**Author:** SathidP-PC | **Priority:** 5 | **Forward Chain:** true | **Event:** OMX_ADD_FUTURE | **futureType:** NXTOFR | **Lines:** 403

---

## §1 — Overview & Purpose

This rule schedules a **next offer** for subscribers across four node contexts (POU Agreement, POU Subscriber, COU Agreement, COU Subscriber) by dispatching `OMX_ADD_FUTURE` JMS events with `futureType="NXTOFR"`. It shares the same JMS event type as `OMX_ADD_NXT_PP`; the `futureType` field in the payload distinguishes them.

> **Shared Event Pattern:** Both `OMX_ADD_NXT_PP` (futureType=NXTPP) and `OMX_ADD_NEXT_OFFER` (futureType=NXTOFR) dispatch to the same `OMX_ADD_FUTURE` JMS destination. The downstream OMX FM routes based on `futureType`.

| Item | Value |
|------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_NEXT_OFFER` |
| Author | SathidP-PC |
| Priority | 5 |
| Forward Chain | true |
| JMS Event Dispatched | `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` |
| futureType | `NXTOFR` |
| Payload Schema | `ns3:futureOrderWithSoc` (FutureOrderWithSoc.xsd) |
| Response Handler | `Response_OMX_ADD_NEXT_OFFER.rulefunction` |
| Fan-In Criterion | `count(Response[ResponseCode ends "000"]) == RequestCount` |
| Target System | OMX Future Order Service (via FM ESB) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM rule priority |
| forwardChain | true | Rule may re-fire after working memory update |
| Rule type | Request dispatcher | Sends outbound JMS events to OMX FM layer |
| Pattern | IntraActivitySequencing (multi-node fan-out) | One event per eligible node; RequestCount++ per dispatch |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order graph: customer, POU/COU/subscriber hierarchy, offers |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity node; holds RequestCount, Response[], Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Match current process step to this activity instance |
| 2 | `orderCurrentActivity.ActivityID == "OMX_ADD_NEXT_OFFER"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_ADD_NEXT_OFFER"` | Double-check: process flow points here |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fire if not already in progress |

---

## §5 — Execution Flow Diagram

1. Resolve LogicalDate concept (`/Concepts/OM/LogicalDate`) — use simulated date if set, else `DateTime.now()`
2. Set fixed fields: `requestedBy="OMX"`, `requestedByUser=Channel`, `futureType="NXTOFR"`
3. Detect resubmit flag: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
4. Load `nextAct.PreExecCheck` for optional per-offer filtering
5. **Loop A — POU Agreement offers**: skip serviceType null/80 → read FE_OR_CCBS → evaluate PreExecCheck → check reqSuccess → GetNextPricePlan → skip blank → GetSocCodeFromName → skip blank → dispatch OMX_ADD_FUTURE (nodeLevel=3, orderType=37)
6. **Loop B — POU Subscriber offers**: skip serviceType null/80 → filter `source=="FE" OR "BRMS"` → evaluate PreExecCheck → check reqSuccess → GetNextPricePlan → dispatch OMX_ADD_FUTURE (nodeLevel=5, orderType=3)
7. **Loop C — COU Agreement offers**: skip serviceType null/80 → GetNextPricePlan (early) → skip blank → NO FE_OR_CCBS filter → evaluate PreExecCheck → check reqSuccess → dispatch OMX_ADD_FUTURE (nodeLevel=3, orderType=37)
8. **Loop D — COU Subscriber offers**: skip serviceType null/80 → GetNextPricePlan (early) → skip blank → filter `source=="FE"` only → evaluate PreExecCheck → check reqSuccess → dispatch OMX_ADD_FUTURE (nodeLevel=5, orderType=3)
9. Each dispatch: `RequestCount++` (unless isActResub), send audit log event
10. Post-loop: if any events dispatched → `GetActivityStatusString("1", false)` + `SendDataToDB()`; else → `SkipActivity(..., "4")`
11. catch: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §6 — Four Iteration Contexts

| Context | nodeLevel | orderType | nodeId | FE_OR_CCBS Filter | OU_ID emitted |
|---------|-----------|-----------|--------|-------------------|---------------|
| POU Agreement | 3 | 37 | `pOu.OUId` | [None — all] | No |
| POU Subscriber | 5 | 3 | `subscriberPou.SubscriberId` | [FE or BRMS] | No |
| COU Agreement | 3 | 37 | `cOu.OUId` (conditional) | [None — all] | Conditional |
| COU Subscriber | 5 | 3 | `subscriberCou.SubscriberId` | [FE only] | **UNCONDITIONAL** |

> **FE_OR_CCBS Asymmetry:** POU Subscriber accepts `FE` or `BRMS`. COU Subscriber accepts `FE` only. Agreement-level contexts have no source filter.

> **OU_ID Always-emitted in COU Subscriber:** In Context D, `OU_ID` is emitted unconditionally (`cOu.OUId`), unlike COU Agreement where it is conditionally wrapped.

---

## §7 — Key Business Logic

### §7.1 Service Type Filter

All four contexts skip offers where `serviceType == null || serviceType == "80"`. ServiceType 80 is a system-internal type that should not be scheduled as a future offer.

### §7.2 GetNextPricePlan as Next Offer Resolver

The helper `RuleFunctions.Helpers.GetNextPricePlan(socProps)` is reused even though this FM targets "next offers". The `futureType="NXTOFR"` parameter tells OMX FM to treat the result as an offer change rather than a price-plan change.

### §7.3 Offer Lookup Chain

1. `GetNextPricePlan(socProps)` → nxtOfferName
2. Skip if nxtOfferName is blank
3. `GetSocCodeFromName(orderRequest, nxtOfferName)` → nxtOfferCode (SOC code)
4. Skip if nxtOfferCode is blank
5. Build remark: `currentOffer + "->" + nxtOfferName`

### §7.4 Effective Date Calculation

```text
durationMonth = GetNextPricePlanDurationMonth(socProps)
billCycleNo   = GetBillCycle(orderRequest)
effectiveDate = GetNextPricePlanEffectiveDate(logicalDate, billCycleNo, durationMonth)
```

`logicalDate` loaded from `/Concepts/OM/LogicalDate`; fallback to `DateTime.now()` if blank.

### §7.5 activityReason Logic

| Condition | activityReason |
|-----------|----------------|
| `ExtendedInfo[TR_MULTISIM_IND="RCM"]` exists | `MSNEX` (static) |
| Otherwise | From `OUActivityInfo/ActivityReason` or `SubscriberActivityInfo/ActivityReason` |

### §7.6 userText Format per Context

| Context | userText Pattern |
|---------|-----------------|
| POU Agreement | `"{inputUserText};NXTOFR request by {channel} on {dateTimeNow};"` |
| POU Subscriber | `"{inputUserText};request by {channel} on {dateTimeNow};"` |
| COU Agreement | `"{inputUserText};request by {channel} on {dateTimeNow};"` |
| COU Subscriber | `"{inputUserText};request by {channel} on {dateTimeNow};"` |

> Only POU Agreement context prepends "NXTOFR " in userText.

### §7.7 reqSuccess Guard

Before dispatching, checks if `Response[].ReferenceId == nodeId AND CompletionStatus==2`. If yes, the offer is skipped — preventing duplicates on order resubmission.

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Triggered for any order containing offers with non-blank `SocProperties` that resolves a next offer name.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event | Channel | Purpose |
|-----------|-------|---------|---------|
| [OUTBOUND] | `OMX_ADD_FUTURE` | OMX FM JMS | Schedule next offer (futureType=NXTOFR) |
| [OUTBOUND] | `Logger` | ESB Audit Log | Audit trail per dispatch, LOG_LEVEL=INFO |

### §8.3 Backend API Details

| System | Operation | Schema | Protocol | Correlation Pattern |
|--------|-----------|--------|----------|---------------------|
| OMX FM | Add Future Order (NXTOFR) | `ns3:futureOrderWithSoc` | JMS | RefID matches offer's node scope |

### §8.4 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `orderCurrentActivity.RequestCount` | Read + Write | Incremented per dispatch |
| `orderCurrentActivity.Status` | Write | ACTIVE or SKIP |
| `orderCurrentActivity.Response[]` | Read | reqSuccess check before each dispatch |
| `orderRequest.IsOrderResubmitted` | Read | Resubmit guard |
| `LogicalDate concept` | Read | Simulated date for test environments |

### §8.5 ExtendedInfo Fields Required (Input)

| Key | Required/Optional | Purpose |
|-----|-------------------|---------|
| `FE_OR_CCBS` | Optional (defaults "FE") | Source filter for subscriber-level offers |
| `TR_MULTISIM_IND` | Optional | Value="RCM" triggers activityReason="MSNEX" |
| `OfferInstanceId` | Optional | Emitted as PREV_OFFER_INSTANCE_ID if non-blank |

### §8.6 Global Variable Dependencies

| Path | Used In | Purpose |
|------|---------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit log | COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit log | TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit log | LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Audit log | Payload logging gate |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding by Context

| Parameter | POU Agreement | POU Subscriber | COU Agreement | COU Subscriber |
|-----------|--------------|---------------|--------------|---------------|
| nodeId | `$pOuId` | `$subId` | `$cOu/OUId` | `$subId` |
| nodeLevel | 3 | 5 | 3 | 5 |
| orderType | 37 | 3 | 37 | 3 |
| RefID header | `$agreeRefId` | `$subRefId` | `$agreeRefId` | `$subRefId` |

### §9.2 futureOrder Core Fields

| Element | Value / Source | Varies? |
|---------|---------------|---------|
| `ns:effectiveDate` | `$effectiveDate` (computed) | No |
| `ns:status` | `1` (static) | No |
| `ns:orderType` | 3 (sub) / 37 (agree) | Yes |
| `ns:nodeLevel` | 5 (sub) / 3 (agree) | Yes |
| `ns:requestedBy` | `"OMX"` (static) | No |
| `ns:futureType` | `"NXTOFR"` (static) | No |
| `ns:customerType` | `OMXUtils:asciiCodeToText(CustomerTypeInfo/Type)` | No |
| `ns:accountSubtype` | `Account[AgreementRefId=ParentOU[$iPOU+1]/.../RefId]/AccountSubType` | Index varies |

### §9.3 ExtendedInfo Fields by Context

| extendedInfo Key | POU Agree | POU Sub | COU Agree | COU Sub |
|-----------------|-----------|---------|-----------|---------|
| `POU_ID` | Conditional | Conditional | Conditional | Conditional |
| `CUS_ID` | Conditional | Conditional | Conditional | Conditional |
| `PAGR_ID` | Conditional | Conditional | Conditional | Conditional |
| `PREV_OFFER_INSTANCE_ID` | Conditional | Conditional | Conditional | Conditional |
| `SUB_ID` | – | Conditional | – | Conditional |
| `MOBILE_NO` | – | Conditional | – | Conditional |
| `OU_ID` (cOu.OUId) | – | – | Conditional | **UNCONDITIONAL** |
| `AGR_ID` (cOu.Agreement.AgreementId) | – | – | Conditional | – |

### §9.4 futureSoc Block

| Element | Source |
|---------|--------|
| `ns2:code` | `$nxtOfferCode` (SOC code of next offer) |
| `ns2:effectiveDate` | `$effectiveDate` |
| `ns2:parameter[]` | For-each over `ParameterInfo` (ParamName/ValuesArray) |
| `ns2:childSoc[]` | For-each over `RelatedOffersArray` (Soc, ParameterInfo, ServiceType, OfferName) |
| `ns2:type` | `round(number($serviceType))` |
| `ns2:subType` | `"NXTOFR"` (futureType static) |
| `ns2:previousSoc` | `$currentSocCode` |
| `ns2:socName` | `$nxtOfferName` |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                [Conditional]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId      [Conditional]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID             [Conditional]
    ├── RefID                    ← $agreeRefId | $subRefId                     [Always]
    ├── UserName                 ← $orderRequest/OrderData/User                [Conditional]
    ├── PassWord                 ← $orderRequest/OrderData/Password            [Conditional]
    ├── OrderType                ← $orderRequest/OrderData/OrderType           [Conditional]
    └── payload
        └── ns3:futureOrderWithSoc
            ├── ns:futureOrder
            │   ├── ns:effectiveDate         ← $effectiveDate                 [Always]
            │   ├── ns:status                ← 1 (static)                     [Always]
            │   ├── ns:orderType             ← 3|37 (context-dependent)       [Always]
            │   ├── ns:nodeLevel             ← 5|3 (context-dependent)        [Always]
            │   ├── ns:nodeId                ← $subId|$cOu/OUId|$pOuId        [Always (COU Agree: conditional)]
            │   ├── ns:requestedDate         ← DateTime.now()                 [Always]
            │   ├── ns:requestedBy           ← "OMX" (static)                 [Always]
            │   ├── ns:dealerCode            ← DealerCode                     [Conditional]
            │   ├── ns:activityReason        ← MSNEX or ActivityReason        [Conditional: xsl:choose]
            │   ├── ns:extendedInfo[POU_ID]  ← $pOuId                        [Conditional: trim>0]
            │   ├── ns:extendedInfo[CUS_ID]  ← $custId                       [Conditional: trim>0]
            │   ├── ns:extendedInfo[SUB_ID]  ← $subId        (Sub contexts)  [Conditional: trim>0]
            │   ├── ns:extendedInfo[MOBILE_NO] ← $msisdn     (Sub contexts)  [Conditional: trim>0]
            │   ├── ns:extendedInfo[PAGR_ID] ← $pAgreeId                     [Conditional: trim>0]
            │   ├── ns:extendedInfo[OU_ID]   ← $cOu/OUId  (COU Agree: cond) [COU Sub: UNCONDITIONAL]
            │   ├── ns:extendedInfo[AGR_ID]  ← $cOu/Agreement/AgreementId    [COU Agree only, Conditional]
            │   ├── ns:extendedInfo[PREV_OFFER_INSTANCE_ID] ← OfferInstanceId [Conditional: trim>0]
            │   ├── ns:fromOrderId           ← OrderData/OrderID              [Conditional]
            │   ├── ns:userText              ← Formatted string               [Always]
            │   ├── ns:remark                ← currentOffer + "->" + nxtOffer [Always]
            │   ├── ns:customerType          ← asciiCodeToText(Type)          [Always]
            │   ├── ns:accountSubtype        ← Account[...]/AccountSubType    [Always]
            │   └── ns:futureType            ← "NXTOFR" (static)             [Always]
            └── ns2:futureSocs
                └── ns2:futureSoc
                    ├── ns2:code             ← $nxtOfferCode                  [Always]
                    ├── ns2:effectiveDate    ← $effectiveDate                 [Always]
                    ├── ns2:parameter[]      ← ParameterInfo (for-each)       [Conditional]
                    ├── ns2:childSoc[]       ← RelatedOffersArray (for-each)  [Conditional]
                    ├── ns2:type             ← round(serviceType)              [Always]
                    ├── ns2:subType          ← "NXTOFR" (static)              [Always]
                    ├── ns2:previousSoc      ← $currentSocCode                [Always]
                    └── ns2:socName          ← $nxtOfferName                  [Always]
```

Legend: `[Always]` = unconditional | `[Conditional: ...]` = inside xsl:if | **UNCONDITIONAL** = always emitted regardless of length check

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(System.nanoTime(), "_REQ")` |
| OPERATION_NAME | `"OMX_ADD_NEXT_OFFER"` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `"Request Sent for OMX_ADD_NEXT_OFFER"` |
| payload | Conditional on WritePayload="true" |

One audit log event sent per dispatched `OMX_ADD_FUTURE` event.

---

## §12 — Activity Status Management

| State | Trigger | Call |
|-------|---------|------|
| [ACTIVE] | At least one event dispatched | `GetActivityStatusString("1", false)` + `SendDataToDB()` |
| [SKIPPED] | No offers met criteria (`isSkipped==true`) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |

---

## §13 — Exception / Error Handling

| Exception Type | Handler |
|---------------|---------|
| `Exception ae` (catch-all) | `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

No DATA_ISSUE guard. Rule silently skips empty offer sets via `continue` statements.

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|----------|--------|---------|
| `GetNextPricePlan(socProps)` | String | Extracts next offer name from SocProperties |
| `GetNextPricePlanDurationMonth(socProps)` | int | Duration in months until next offer effective |
| `GetBillCycle(orderRequest)` | int | Subscriber's billing cycle number |
| `GetNextPricePlanEffectiveDate(logicalDate, billCycleNo, durationMonth)` | DateTime | Computes effective date |
| `GetSocCodeFromName(orderRequest, nxtOfferName)` | String | Resolves offer name → SOC code |
| `GetXMLForAgreementOffer(orderRequest, agreeRefId, soc)` | String XML | Serializes POU agreement offer for PreExecCheck |
| `GetXMLForSubscriberOffer(orderRequest, subRefId, soc)` | String XML | Serializes POU subscriber offer |
| `GetXMLForAgreementOfferInChildOU(orderRequest, agreeRefId, soc, pOu.RefId)` | String XML | Serializes COU agreement offer |
| `GetXMLForSubscriberOfferInChildOU(orderRequest, subRefId, soc, pOu.RefId)` | String XML | Serializes COU subscriber offer |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | void | Marks activity as SKIPPED |
| `HandleActivityException(...)` | void | Centralized exception handler |
| `BRMS.IsBlankOrStringNull(str)` | boolean | True if string is null or whitespace |
| `OMXUtils:asciiCodeToText(code)` | String | Converts customer type code to text (XSLT) |

---

## §15 — Function Dependency Tree

```text
Request_OMX_ADD_NEXT_OFFER (BE rule)
├── Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(str)
├── RuleFunctions.Helpers.GetNextPricePlan(socProps)
├── RuleFunctions.Helpers.GetNextPricePlanDurationMonth(socProps)
├── RuleFunctions.Helpers.GetBillCycle(orderRequest)
├── RuleFunctions.Helpers.GetNextPricePlanEffectiveDate(logicalDate, billCycleNo, durationMonth)
├── GetSocCodeFromName(orderRequest, nxtOfferName)          [unqualified call]
├── RuleFunctions.Helpers.GetXMLForAgreementOffer(...)      [POU Agreement]
├── RuleFunctions.Helpers.GetXMLForSubscriberOffer(...)     [POU Subscriber]
├── RuleFunctions.Helpers.GetXMLForAgreementOfferInChildOU(...) [COU Agreement]
├── RuleFunctions.Helpers.GetXMLForSubscriberOfferInChildOU(...) [COU Subscriber]
├── XPath.execute("/("+chkXPath+")", sXML, ...)             [PreExecCheck]
├── XPath.evalAsString(...)                                  [UserText / dateTimeNow]
├── Event.createEvent("xslt://{{/Events/.../OMX_ADD_FUTURE}}...") ×N
│   └── OMXUtils:asciiCodeToText(...)                       [XSLT custom function]
├── Event.Ext.sendEventImmediate(reqEvent) ×N
├── Event.createEvent("xslt://{{/Events/.../Logger}}...") ×N [audit per dispatch]
├── Event.Ext.sendEventImmediate(auditEvent) ×N
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)
└── RuleFunctions.Helpers.HandleActivityException(...)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Support four node-level fan-out: POU Agreement, POU Subscriber, COU Agreement, COU Subscriber
- **R2** — Apply FE_OR_CCBS="FE" or "BRMS" filter at POU Subscriber level; FE-only at COU Subscriber; no filter at Agreement levels
- **R3** — Resolve next offer via SocProperties blob; abort per-offer if name or code is blank
- **R4** — Effective date computed from LogicalDate + BillCycle + DurationMonth
- **R5** — futureType="NXTOFR" must be set in both `ns:futureType` and `ns2:subType`
- **R6** — OU_ID must be emitted unconditionally in COU Subscriber context
- **R7** — Idempotent fan-out: skip if CompletionStatus==2 response already exists for the node
- **R8** — Resubmit safety: do not increment RequestCount when isActResub==true

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| GetSocCodeFromName called as unqualified function | [HIGH] | Verify BE resolves correctly; add integration test |
| FE_OR_CCBS asymmetry (POU Sub: FE+BRMS; COU Sub: FE only) | [MEDIUM] | Explicit test for COU Sub with BRMS source — must be skipped |
| LogicalDate concept may not exist in prod | [MEDIUM] | DateTime.now() fallback ensures safety |
| GetNextPricePlan() used for "next offer" — misleading name | [LOW] | Rename to GetNextOfferName() in modern implementation |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author SathidP-PC
 */
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_NEXT_OFFER {
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
        orderCurrentActivity.ActivityID == "OMX_ADD_NEXT_OFFER";
        orderRequest.ProcessFlow.NextActivityID == "OMX_ADD_NEXT_OFFER";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        Object logger = Log.getLogger("Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_NEXT_OFFER");
        Log.log(logger,"debug","Executing %s",orderRequest@extId);

        boolean isActResub=(orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);

        try {
            Concepts.OM.LogicalDate logicalDateRes = Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate");
            DateTime logicalDate = DateTime.now();
            if(!RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(logicalDateRes.LogicalDate)){
                logicalDate = DateTime.parseString(logicalDateRes.LogicalDate, "yyyy-MM-dd'T'HH:mm:ssXXX");
            }

            DateTime requestedDate = DateTime.now();
            String requestedBy = "OMX";
            String requestedByUser = orderRequest.OrderData.Channel;
            String futureType = "NXTOFR";
            boolean isSkipped = true;

            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
                orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
            String chkXPath = nextAct.PreExecCheck;
            String custId = orderRequest.OrderData.Customer.CustomerId;

            for(int iPOU = 0; iPOU < orderRequest.OrderData.Customer.ParentOU@length; iPOU++){
                // ... Loop A: POU Agreement
                // dispatch Event.createEvent("xslt://{{/Events/.../OMX_ADD_FUTURE}}...")
                //   → See §9 for XSLT details (nodeLevel=3, orderType=37, futureType="NXTOFR")
                // FE_OR_CCBS: no filter on agreement-level
                // userText: "{inputUserText};NXTOFR request by {channel} on {dateTimeNow};"

                for(int iPouSub = 0; ...) {
                    // Loop B: POU Subscriber
                    // FE_OR_CCBS filter: source=="FE" || source=="BRMS"
                    // userText: "{inputUserText};request by {channel} on {dateTimeNow};"
                    // dispatch: nodeLevel=5, orderType=3
                }

                for(int iCOU = 0; ...) {
                    // Loop C: COU Agreement
                    // No FE_OR_CCBS filter; OU_ID + AGR_ID as conditional extendedInfo
                    // dispatch: nodeLevel=3, orderType=37

                    for(int iCouSub = 0; ...) {
                        // Loop D: COU Subscriber
                        // FE_OR_CCBS filter: source=="FE" only (no BRMS)
                        // OU_ID emitted UNCONDITIONALLY
                        // dispatch: nodeLevel=5, orderType=3
                    }
                }
            }

            if(!isSkipped) {
                orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
            Log.log(logger,"info","Completed %s",orderRequest@extId);
        } catch ( Exception ae){
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

`Response_OMX_ADD_NEXT_OFFER.rulefunction` parses each `OMX_ADD_FUTURE` response, creates a `OMX_AddFutureRes` concept, appends it to `currActivity.Response[]`, and checks fan-in via `ResponseCode` suffix "000" comparison.

> **Key Difference from OMX_ADD_NXT_PP:** This handler does NOT use `IsAllResponseSuccess()`. It directly evaluates `count(Response[ResponseCode ends "000"]) == RequestCount`. It also does NOT map `ReferenceId` from the response payload (unlike OMX_ADD_NXT_PP which reads `payload/ns1:AddFutureOrderResponse/ns1:nodeId`).

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` | Inbound JMS response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; RequestCount for fan-in |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId               ← OMXUtils:generateTrackingID()           [Always]
    ├── ResponseCode         ← $eventResponse/ResponseCode             [Conditional]
    ├── ResponseMessage      ← $eventResponse/ResponseMsg              [Conditional]
    ├── CompletionStatus     ← $eventResponse/CompletionStatus         [Conditional]
    └── ReferenceId          ← NOT MAPPED [⚠ Absent — unlike OMX_ADD_NXT_PP]
```

### §19.4 Response Completion Logic

| Step | Detail |
|------|--------|
| Append response | `currActivity.Response[currActivity.Response@length] = resEvent` |
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Return "true" | All dispatched requests have "xxx000" ResponseCode |
| Return "false" | Still awaiting responses |

> **Fan-In vs OMX_ADD_NXT_PP:** OMX_ADD_NXT_PP uses `IsAllResponseSuccess()` checking `CompletionStatus==2`. This handler uses `ResponseCode suffix "000"` — a different success criterion.

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(System.nanoTime(), "_RES")` |
| OPERATION_NAME | `"OMX_ADD_NEXT_OFFER"` |
| AUDIT_TRACE | `"Response received for OMX_ADD_NEXT_OFFER"` |
| LOG_LEVEL | INFO |
| payload | `$eventResponse` (conditional on WritePayload="true") |

### §19.6 Response XSLT Source

```xml
<!-- createObject XSLT for OMX_AddFutureRes (no ReferenceId mapped) -->
<xsl:stylesheet
    xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    version="1.0"
    exclude-result-prefixes="OMXUtils xsl xsd">
    <xsl:output method="xml"/>
    <xsl:param name="eventResponse"/>
    <xsl:template match="/">
        <createObject>
            <object>
                <xsl:attribute name="extId">
                    <xsl:value-of select="OMXUtils:generateTrackingID()"/>
                </xsl:attribute>
                <xsl:if test="$eventResponse/ResponseCode">
                    <ResponseCode>
                        <xsl:value-of select="$eventResponse/ResponseCode"/>
                    </ResponseCode>
                </xsl:if>
                <xsl:if test="$eventResponse/ResponseMsg">
                    <ResponseMessage>
                        <xsl:value-of select="$eventResponse/ResponseMsg"/>
                    </ResponseMessage>
                </xsl:if>
                <xsl:if test="$eventResponse/CompletionStatus">
                    <CompletionStatus>
                        <xsl:value-of select="$eventResponse/CompletionStatus"/>
                    </CompletionStatus>
                </xsl:if>
                <!-- NOTE: ReferenceId NOT mapped (unlike Response_OMX_ADD_NXT_PP) -->
            </object>
        </createObject>
    </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
