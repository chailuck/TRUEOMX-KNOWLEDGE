# Request_OMX_UPDATE_FUT_OFFER_COP_DATE

> Update future offer Change-of-Plan (COP) effective/expiry dates in OMX — 4-scope parallel fan-out: POU Agreement, POU Subscriber, COU Agreement, COU Subscriber

**Author:** sakarin-radchapunya | **Priority:** 5 | **forwardChain:** true | **Pattern:** sendEventImmediate parallel fan-out

---

## §1 — Overview & Purpose

This rule updates the future offer COP (Change-of-Plan/Contract) effective and expiry dates in the OMX FM for all qualifying offers across four entity scopes: POU Agreement, POU Subscriber, COU Agreement, and COU Subscriber. Events are dispatched via `sendEventImmediate` (parallel fan-out — not IntraActivitySequencing). The payload carries a `ns1:futureOrderAll` structure containing both a header `ns:futureOrder` (future order metadata) and a `ns2:futureSoc` (per-SOC date details).

> **CRITICAL BUG — COU Subscriber scope infinite loop:** Line 156: `for(int m=0; j<offerLen; m++)` — the loop termination condition uses `j` (the subscriber index, which does not change inside the loop) instead of `m`. When `j=0` and `offerLen>0`, this is an **infinite loop**. COU Subscriber offers are never correctly processed in any non-trivial order.

> **Used in POSTPAID_UPDATE_PARAMETER step 25** — updates COP effective/expiry dates for future offers after parameter update and CCBS subscriber update.

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_UPDATE_FUT_OFFER_COP_DATE` |
| Outbound event | `Events.OMConsumers.OMXFM.Request.OMX_UPDATE_FUT_OFFER_COP_DATE` |
| Response event | `Events.OMConsumers.OMXFM.Response.OMX_UPDATE_FUT_OFFER_COP_DATE` |
| Payload root | `ns1:futureOrderAll` (FutureSocCop.xsd) — contains ns:futureOrder + ns2:futureSoc |
| Response concept | `Concepts.FM.Response.OMX_UpdateFutureCorpRes` |
| Dispatch pattern | sendEventImmediate — parallel fan-out per qualifying offer |
| Parameters | UPDATE_EXP_DATE (Y/N — controls effectiveDate source in Subscriber scopes) |
| Audit guard | `AllowWriteLog(orderRequest.OrderData.OrderType)` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Note |
|-----------|-------|------|
| priority | 5 | Standard FM request priority |
| forwardChain | true | Allows further rule evaluation after execution |
| debugOut on entry/exit | Yes | Uses wrong rule name: "OMX_FUTURE_OFFER_COP_DATE" instead of "OMX_UPDATE_FUT_OFFER_COP_DATE" [LOW bug] |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order — entity hierarchy, offers, extended info, effective dates |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — Status, RequestCount, Response[], PreExecCheck, Parameter[] |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity position match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_UPDATE_FUT_OFFER_COP_DATE"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_UPDATE_FUT_OFFER_COP_DATE"` | Redundant dual binding |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Fires only when awaiting execution |

---

## §5 — Execution Flow

1. **Resubmit detection** — `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. **Load state** — load `nextAct` Activity concept for PreExecCheck; read `UPDATE_EXP_DATE` parameter
3. **Scope A — POU Agreement** — if Agreement@isSet: loop Agreement.Offers[o]; per-offer PreExecCheck; resubmit guard; build + send event; conditional audit log
4. **Scope B — POU Subscriber** — loop Subscriber[j] → SubscriberOffers[l]; per-offer PreExecCheck; resubmit guard; build + send event; conditional audit log
5. **Scope C — COU Agreement** (per ChildOU) — if Agreement@isSet: loop Agreement.Offers[o]; per-offer PreExecCheck; resubmit guard; build + send event; conditional audit log
6. **Scope D — COU Subscriber** — `[CRITICAL BUG]` loop uses `j<offerLen` (infinite loop) instead of `m<offerLen`
7. **Dispatch or skip** — if any events sent: set INPROGRESS → `SendDataToDB()`; else `SkipActivity("4")`
8. **Exception handling** — catch all → `HandleActivityException()`

---

## §6 — Rule Action (THEN) — Detailed Logic

### Scope A — POU Agreement

| Dimension | Detail |
|-----------|--------|
| Entry condition | `parentOU.Agreement@isSet` — skip if POU has no Agreement |
| Loop | `POU[i] → Agreement.Offers[o]` |
| refId (resubmit key) | `Agreement.RefId` — NOT "RefId:Soc" pattern |
| PreExecCheck helper | `GetXMLForAgreementOfferFilterWithExtendedInfo(orderRequest, pAgRefId, pagof.Soc, filter)` |
| XSLT params | `orderRequest, i, pagof` |
| effectiveDate source | `OrderData.EffectiveDate` (UPDATE_EXP_DATE not used in Agreement scopes) |
| futureSoc effectiveDate | 3-way: `pagof.EffectiveDate` → `pagof.ParameterInfo[1].EffectiveDate` → `pagof.EffectiveDate` (last duplicates first) |
| futureSoc expireDate | 3-way: `pagof.ExpirationDate` → `pagof.ParameterInfo[1].ExpirationDate` → `pagof.ExpirationDate` |
| ExtendedInfo | All `pagof/ExtendedInfo` entries passed through as `ns2:extendedInfo` |

### Scope B — POU Subscriber

| Dimension | Detail |
|-----------|--------|
| Loop | `POU[i] → Subscriber[j] → SubscriberOffers[l]` |
| refId (resubmit key) | `Subscriber[j].RefId` — NOT "RefId:Soc" pattern |
| PreExecCheck helper | `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, subscriber.RefId, subOff.Soc, filterS)` |
| XSLT params | `orderRequest, j, l, i, updateExpParam, subOff` |
| futureOrder effectiveDate | if `UPDATE_EXP_DATE='Y'` → `ExtendedInfo[Name='EXP_DATE_VALUE']/Value`; else → `OrderData.EffectiveDate` |
| futureSoc effectiveDate | 3-way: `subOff.EffectiveDate` → `subOff.ParameterInfo[1].EffectiveDate` → `subOff.EffectiveDate` |
| futureSoc expireDate | 4-way: `subOff.ExpirationDate` → `subOff.ParameterInfo[1].ExpirationDate` → `ExtendedInfo[Name='EXP_DATE_VALUE']/Value` → `subOff.ExpirationDate` |
| ExtendedInfo | All `subOff/ExtendedInfo` entries passed through |

### Scope C — COU Agreement

| Dimension | Detail |
|-----------|--------|
| Entry condition | `parentChildOU.Agreement@isSet` |
| Loop | `POU[i] → ChildOU[k] → Agreement.Offers[o]` |
| refId (resubmit key) | `ChildOU[k].Agreement.RefId` |
| PreExecCheck helper | `GetXMLForAgreementOfferFilterWithExtendedInfo(orderRequest, childOuRefId, pagof.Soc, filter)` |
| XSLT params | `orderRequest, i, pagof` — COU index `k` NOT passed |
| XSLT behavior | Identical to Scope A (UPDATE_EXP_DATE not used) |

### Scope D — COU Subscriber

> **CRITICAL BUG — Infinite loop:**
> `for(int m=0; j<offerLen; m++)` — The loop condition is `j<offerLen`. `j` is the subscriber index from the outer loop and **never changes** inside this loop. When `j=0` and `offerLen>0`, the loop runs forever. When `j>=offerLen`, it never executes — silently skips all COU Subscriber offers. Should be `m<offerLen`.

| Dimension | Detail |
|-----------|--------|
| Loop (intended) | `POU[i] → ChildOU[k] → Subscriber[j] → SubscriberOffers[m]` |
| Actual behavior | Infinite loop or silent skip — NEVER correctly processes COU Subscriber offers |
| refId | `ChildOU[k].Subscriber[j].RefId` |
| XSLT params | `orderRequest, k, j, i, updateExpParam, subOff` |

### effectiveDate Source Priority (Subscriber Scopes B & D)

```text
/* ns:futureOrder effectiveDate — xsl:choose on UPDATE_EXP_DATE parameter */
when  UPDATE_EXP_DATE == "Y": → ExtendedInfo[Name='EXP_DATE_VALUE']/Value
otherwise:                    → orderRequest.OrderData.EffectiveDate

/* ns2:futureSoc effectiveDate — 3-way choose */
when  not(empty(subOff.EffectiveDate)):    → subOff.EffectiveDate
when  not(empty(subOff.ParameterInfo)):   → subOff.ParameterInfo[1].EffectiveDate
otherwise:                                → subOff.EffectiveDate  [bug: same as first branch]

/* ns2:futureSoc expireDate — 4-way choose (Subscriber) */
when  not(empty(subOff.ExpirationDate)):          → subOff.ExpirationDate
when  ParameterInfo count > 0 AND ParameterInfo[1].ExpirationDate exists: → ParameterInfo[1].ExpirationDate
when  ExtendedInfo[Name='EXP_DATE_VALUE']/Value exists: → EXP_DATE_VALUE
otherwise:                                        → subOff.ExpirationDate  [bug: same as first branch]
```

> **[MEDIUM] Duplicate otherwise branches:** The `<xsl:otherwise>` in both effectiveDate and expireDate choose blocks returns the same value as the first `<xsl:when>` branch. Since the first branch fires when the value is non-empty, the otherwise only fires when the value is empty — at which point the inner xsl:if also suppresses output. Dead code.

---

## §8 — System & Integration Dependencies

### §8.1 — Activity Parameters

| Parameter Key | Type | Effect |
|---------------|------|--------|
| UPDATE_EXP_DATE | Optional String (Y/N) | If "Y", futureOrder effectiveDate = ExtendedInfo[EXP_DATE_VALUE]; else = OrderData.EffectiveDate. Only affects Subscriber scopes (B and D). Agreement scopes ignore this parameter. |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_UPDATE_FUT_OFFER_COP_DATE` | Per-offer COP date update (parallel fan-out) |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.OMX_UPDATE_FUT_OFFER_COP_DATE` | FM date update confirmation |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | Audit logging — gated by `AllowWriteLog(orderType)` |

### §8.3 — Backend API Details

| System | Operation | Schema | Protocol |
|--------|-----------|--------|----------|
| OMX FM | OMX_UPDATE_FUT_OFFER_COP_DATE | `ns1:futureOrderAll` (FutureSocCop.xsd) containing `ns:futureOrder` (FutureOrder.xsd) + `ns2:futureSoc` (FutureSoc.xsd) | JMS / TIBCO EMS |

### §8.4 — BE Working Memory Dependencies

| Concept | Access | Fields Used |
|---------|--------|-------------|
| `OrderRequest` | Read | OrderData.{EffectiveDate, OrderType, User, Password, OrderID, OMXTrackingId, ExtendedInfo[FUT_ORDER_ID]}, Customer.{ParentOU[].Agreement, ParentOU[].Subscriber[], ParentOU[].ChildOU[].Agreement, ParentOU[].ChildOU[].Subscriber[]} |
| `Activity` | Read/Write | Status, RequestCount, Response[], Parameter[], PreExecCheck |

### §8.5 — ExtendedInfo Fields Required

| Key | Location | Purpose |
|-----|----------|---------|
| `FUT_ORDER_ID` | OrderData.ExtendedInfo | futureOrderId in ns:futureOrder — identifies the future order to update |
| `EXP_DATE_VALUE` | SubscriberOffers.ExtendedInfo (Subscriber scopes) | Alternative effectiveDate and fallback expireDate when UPDATE_EXP_DATE='Y' |
| `FE_OR_CCBS` | Offer.ExtendedInfo (all scopes) | Passed to PreExecCheck XML builder only — not used as a dispatch gate here |

### §8.6 — Global Variable Dependencies

| Path | Used For |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Gates payload in audit log |

### §8.7 — Scope Summary

| Scope | Entity | Entry Gate | refId Key | UPDATE_EXP_DATE used | Bug |
|-------|--------|-----------|-----------|----------------------|-----|
| A | POU Agreement | Agreement@isSet | Agreement.RefId | No | None |
| B | POU Subscriber | None | Subscriber[j].RefId | Yes | None |
| C | COU Agreement | Agreement@isSet | ChildOU.Agreement.RefId | No | XSLT lacks COU index |
| D | COU Subscriber | None (but bugged) | ChildOU.Subscriber.RefId | Yes | [CRITICAL] j<offerLen |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

### Agreement Variant (Scopes A & C)

```text
createEvent
└── event
    ├── JMSPriority / JMSCorrelationID / OrderID    [Conditional each]
    ├── UserName / PassWord                          [Conditional: User/Password exists]
    ├── OrderType                                    [Conditional]
    └── payload                                      [Always]
        └── ns1:futureOrderAll
            ├── ns:futureOrder
            │   ├── ns:futureOrderId   ← OrderData.ExtendedInfo[Name='FUT_ORDER_ID']/Value   [Conditional]
            │   └── ns:effectiveDate   ← OrderData.EffectiveDate                              [Conditional — UPDATE_EXP_DATE ignored]
            └── ns2:futureSoc
                ├── ns2:code           ← pagof.Soc                                            [Always]
                ├── ns2:effectiveDate  [xsl:choose 3-way: pagof.EffectiveDate → pagof.ParameterInfo[1].EffectiveDate → pagof.EffectiveDate]
                ├── ns2:expireDate     [xsl:choose 3-way: pagof.ExpirationDate → pagof.ParameterInfo[1].ExpirationDate → pagof.ExpirationDate]
                └── ns2:extendedInfo   [xsl:for-each pagof/ExtendedInfo — all entries passthrough]
                    ├── ns2:name       ← Name
                    └── ns2:value      ← Value
```

### Subscriber Variant vs Agreement Variant — Differences

| Field | Agreement Variant | Subscriber Variant |
|-------|------------------|--------------------|
| `ns:futureOrder/ns:effectiveDate` | OrderData.EffectiveDate (always) | if UPDATE_EXP_DATE='Y' → EXP_DATE_VALUE ExtendedInfo; else → OrderData.EffectiveDate |
| `ns2:futureSoc/ns2:code` | pagof.Soc | subOff.Soc |
| `ns2:futureSoc/ns2:effectiveDate` | pagof.EffectiveDate / ParameterInfo[1] | subOff.EffectiveDate / ParameterInfo[1] |
| `ns2:futureSoc/ns2:expireDate` | 3-way (ExpirationDate / ParameterInfo[1] / ExpirationDate) | 4-way (ExpirationDate / ParameterInfo[1] / EXP_DATE_VALUE / ExpirationDate) |
| `ns2:extendedInfo` | from pagof/ExtendedInfo | from subOff/ExtendedInfo |

---

## §11 — Audit Logging

> **AllowWriteLog gate:** Unlike most FMs that always send an audit log, this rule calls `RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)` before logging. Audit events are only emitted for order types where logging is enabled.

| Scope | OPERATION_NAME | AUDIT_TRACE | Note |
|-------|---------------|-------------|------|
| Scope A Request | OMX_UPDATE_COP_DATE | `concat("Request Sent for RefId: ", $pAgRefId)` | Shortened name; dynamic RefId in trace |
| Scope B Request | OMX_UPDATE_COP_DATE | `concat("Request Sent for RefId: ", $refId)` | Same shortened name |
| Scope C Request | OMX_UPDATE_COP_DATE | `concat("Request Sent for RefId: ", $childOuRefId)` | Same |
| Response | OMX_UPDATE_COP_DATE | "Response received for OMX_UPDATE_COP_DATE" | Consistent with request |

> The abbreviated operation name "OMX_UPDATE_COP_DATE" (vs the rule's actual name "OMX_UPDATE_FUT_OFFER_COP_DATE") is consistent across all request and response audit logs — no cross-FM copy-paste bug, but the name mismatch may confuse audit trail searches by FM name.

---

## §12 — Activity Status Management

| Condition | Status | Call |
|-----------|--------|------|
| At least one event dispatched | INPROGRESS | `GetActivityStatusString("1", false)` → `SendDataToDB()` |
| No qualifying offers across all scopes | SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception caught | ERROR | `HandleActivityException()` |

---

## §15 — Function Dependency Tree

```text
Request_OMX_UPDATE_FUT_OFFER_COP_DATE.rule
├── Instance.getByExtIdByUri(NextActivityName, ...)                   [load nextAct]
├── GetActivityParameterValueFromKey(, "UPDATE_EXP_DATE")
├── [Scope A] POU[i] → Agreement@isSet → Agreement.Offers[o]
│   ├── XPath.evalAsString(FE_OR_CCBS ExtendedInfo)
│   ├── GetXMLForAgreementOfferFilterWithExtendedInfo()               [PreExecCheck doc]
│   ├── XPath.execute("/(PreExecCheck)", sXML, ...)
│   ├── [Resubmit guard] Response[].ReferenceId==pAgRefId && CompletionStatus==2
│   ├── Event.createEvent("xslt://OMX_UPDATE_FUT_OFFER_COP_DATE")    [Agreement XSLT A]
│   ├── Event.Ext.sendEventImmediate() → OMX_UPDATE_FUT_OFFER_COP_DATE
│   └── AllowWriteLog(orderType) → Event.Ext.sendEventImmediate() → Logger
├── [Scope B] POU[i] → Subscriber[j] → SubscriberOffers[l]
│   ├── XPath.evalAsString(FE_OR_CCBS ExtendedInfo)
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo()              [PreExecCheck doc]
│   ├── XPath.execute("/(PreExecCheck)", sXML, ...)
│   ├── [Resubmit guard] Response[].ReferenceId==refId && CompletionStatus==2
│   ├── Event.createEvent("xslt://OMX_UPDATE_FUT_OFFER_COP_DATE")    [Subscriber XSLT B]
│   ├── Event.Ext.sendEventImmediate() → OMX_UPDATE_FUT_OFFER_COP_DATE
│   └── AllowWriteLog(orderType) → Event.Ext.sendEventImmediate() → Logger
├── [Scope C] POU[i] → ChildOU[k] → Agreement@isSet → Agreement.Offers[o]
│   ├── XPath.evalAsString(FE_OR_CCBS ExtendedInfo)
│   ├── GetXMLForAgreementOfferFilterWithExtendedInfo()               [PreExecCheck doc]
│   ├── XPath.execute("/(PreExecCheck)", sXML, ...)
│   ├── [Resubmit guard] Response[].ReferenceId==childOuRefId && CompletionStatus==2
│   ├── Event.createEvent("xslt://OMX_UPDATE_FUT_OFFER_COP_DATE")    [Agreement XSLT C]
│   ├── Event.Ext.sendEventImmediate() → OMX_UPDATE_FUT_OFFER_COP_DATE
│   └── AllowWriteLog(orderType) → Event.Ext.sendEventImmediate() → Logger
├── [Scope D] POU[i] → ChildOU[k] → Subscriber[j] → [CRITICAL: j<offerLen infinite loop]
│   └── *** NEVER EXECUTES CORRECTLY ***
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB()
├── RuleFunctions.Helpers.SkipActivity()
└── RuleFunctions.Helpers.HandleActivityException()

Response_OMX_UPDATE_FUT_OFFER_COP_DATE.rulefunction
├── OMXUtils.generateTrackingID()
├── Instance.createInstance("xslt://OMX_UpdateFutureCorpRes")
│   ├── ResponseCode        ← $eventResponse/ResponseCode
│   ├── ResponseMessage     ← $eventResponse/ResponseMsg
│   ├── CompletionStatus    ← $eventResponse/CompletionStatus
│   └── ReferenceId         ← $eventResponse/RefID              [correctly mapped]
├── currActivity.Response[Response@length] = activityRes
├── Event.Ext.sendEventImmediate() → Logger
├── XPath.evalAsInt(count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3)="000"]))
└── if(RequestCount == successResponseCount) → "true" else → "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Update COP effective/expiry dates for POU Agreement offers (one event per offer) |
| R2 | Update COP effective/expiry dates for POU Subscriber offers (one event per offer per subscriber) |
| R3 | Update COP dates for COU Agreement offers (one event per offer per child OU) |
| R4 | Update COP dates for COU Subscriber offers — currently broken by infinite loop bug |
| R5 | Parallel fan-out (sendEventImmediate) — all qualifying events dispatched concurrently |
| R6 | If UPDATE_EXP_DATE='Y', use ExtendedInfo[EXP_DATE_VALUE] as the futureOrder effectiveDate (Subscriber scopes only) |
| R7 | Fan-in: all-success (RequestCount == count of responses with ResponseCode suffix "000") |

### Design Risks

| Risk | Severity | Detail | Mitigation |
|------|----------|--------|-----------|
| COU Subscriber loop condition bug | [CRITICAL] | Line 156: `for(int m=0; j<offerLen; m++)` — `j` instead of `m` in condition. Infinite loop when j=0 and offerLen>0; silent skip when j≥offerLen. | Fix condition to `m<offerLen` |
| xsl:otherwise dead code | [MEDIUM] | Both Agreement and Subscriber XSLT have xsl:choose blocks where otherwise returns same value as first when — unreachable code | Remove dead otherwise branches |
| UPDATE_EXP_DATE not applied to Agreement scopes | [MEDIUM] | Parameter is read but only affects Subscriber scopes. Agreement scopes always use OrderData.EffectiveDate. Undocumented asymmetry. | Document explicitly; apply same logic if intended |
| Audit OPERATION_NAME abbreviated | [MEDIUM] | OPERATION_NAME = "OMX_UPDATE_COP_DATE" not "OMX_UPDATE_FUT_OFFER_COP_DATE" in all audit events | Align with ActivityID naming convention |
| debugOut uses wrong rule name | [LOW] | debugOut messages reference "OMX_FUTURE_OFFER_COP_DATE" instead of "OMX_UPDATE_FUT_OFFER_COP_DATE" | Fix to match actual rule name |
| Inconsistent resubmit refId pattern | [MEDIUM] | Agreement: Agreement.RefId; Subscriber: Subscriber.RefId (not "RefId:Soc"). Multiple offers under same agreement share one resubmit key. | Use "RefId:Soc" pattern consistently for per-offer protection |

---

## §18 — Full Source Code

```java
/**
 * @author sakarin-radchapunya
 */
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_UPDATE_FUT_OFFER_COP_DATE {
    attribute { priority = 5; forwardChain = true; }
    declare { Concepts.OrderRequest.OrderRequest orderRequest; Concepts.OM.ProcessConfig.Activity orderCurrentActivity; }
    when { /* activityId + status WAITING guards */ }
    then {
        System.debugOut("Executing OMX_FUTURE_OFFER_COP_DATE"); // [LOW: wrong name]
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            boolean isSkipped = true;
            String updateExpParam = GetActivityParameterValueFromKey(orderCurrentActivity, "UPDATE_EXP_DATE");

            for(int i=0; i < iPOULen; i++) {
                // ── Scope A: POU Agreement ───────────────────────────────────────────
                if(parentOU.Agreement@isSet) {
                    for(int o=0; o < pagofLen; o++) {
                        // PreExecCheck + resubmit guard
                        // Event built with Agreement XSLT A (see §10)
                        Event.Ext.sendEventImmediate(reqEvent);
                        isSkipped = false;
                        if(!isActResub) orderCurrentActivity.RequestCount++;
                        if(AllowWriteLog(orderType)) Event.Ext.sendEventImmediate(/* Logger: OPERATION_NAME="OMX_UPDATE_COP_DATE" */);
                    }
                }

                // ── Scope B: POU Subscriber ──────────────────────────────────────────
                for(int j=0; j < iSubscriberLen; j++) {
                    for(int l=0; l < offerLen; l++) {
                        // PreExecCheck + resubmit guard
                        // Event built with Subscriber XSLT B (see §10); updateExpParam controls effectiveDate
                        Event.Ext.sendEventImmediate(reqEvent);
                        isSkipped = false;
                        if(!isActResub) orderCurrentActivity.RequestCount++;
                        if(AllowWriteLog(orderType)) Event.Ext.sendEventImmediate(/* Logger */);
                    }
                }

                for(int k=0; k < iCOULen; k++) {
                    // ── Scope C: COU Agreement ────────────────────────────────────────
                    if(parentChildOU.Agreement@isSet) {
                        for(int o=0; o < childLen; o++) {
                            // Event built with Agreement XSLT C (see §10)
                            Event.Ext.sendEventImmediate(reqEvent);
                            isSkipped = false;
                            if(!isActResub) orderCurrentActivity.RequestCount++;
                            if(AllowWriteLog(orderType)) Event.Ext.sendEventImmediate(/* Logger */);
                        }
                    }

                    // ── Scope D: COU Subscriber ───────────────────────────────────────
                    for(int j=0; j < iCSubscriberLen; j++) {
                        for(int m=0; j<offerLen; m++) { // [CRITICAL: j<offerLen should be m<offerLen — INFINITE LOOP]
                            // *** This block never executes correctly ***
                        }
                    }
                }
            }

            if(!isSkipped) {
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

## §19 — Response Message Rule

### §19.1 — Overview

`Response_OMX_UPDATE_FUT_OFFER_COP_DATE.rulefunction` — receives the OMX FM COP date update confirmation, creates an `OMX_UpdateFutureCorpRes` concept, appends to Response[], sends audit log, then evaluates the success-count fan-in condition.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order for audit logging |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_UPDATE_FUT_OFFER_COP_DATE` | Inbound FM COP date confirmation |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] array target |

### §19.3 — ResponseBase Concept Construction (OMX_UpdateFutureCorpRes)

```text
createObject
└── object @extId ← OMXUtils.generateTrackingID()    [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode    [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg     [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId         ← $eventResponse/RefID           [Conditional] [Correctly mapped]
```

### §19.4 — Fan-in Completion Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

```java
if(currActivity.RequestCount == successResponseCount)
    return "true";   // all dispatched requests got success responses
else
    return "false";  // still waiting for success responses
```

Standard all-success fan-in pattern — returns "true" only when every dispatched request has received a response with ResponseCode ending in "000".

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
