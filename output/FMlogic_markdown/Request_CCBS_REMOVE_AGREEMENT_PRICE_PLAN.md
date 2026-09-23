# Request_CCBS_REMOVE_AGREEMENT_PRICE_PLAN

> FM Logic Documentation — Remove Agreement Price Plan (Per-Offer Dispatch; POU→COU Order; Parameter ADD/REMOVE Validation; LargeCustomer; FE_OR_CCBS Filter; OMXFM external dispatch)

**Rule:** `Rules.OMConsumers.OMXFM.Request.Request_CCBS_REMOVE_AGREEMENT_PRICE_PLAN`
**ActivityID:** `CCBS_REMOVE_AGREEMENT_PRICE_PLAN`
**Priority:** 5
**Pattern:** Per-offer dispatch (POU first, then COU)
**Used in step:** 18

---

## §1 — Overview & Purpose

**CCBS_REMOVE_AGREEMENT_PRICE_PLAN** removes an existing price plan from an agreement. For each ParentOU's Agreement Offers (POU scope first), then for each ChildOU's Agreement Offers (COU scope), per-offer PreExecCheck and reqSuccess check determine dispatch.

> **[CRITICAL BUG] COU loop iterates wrong offer array (line 102):** The COU inner loop uses `parentOU.Agreement.Offers` (not `childOU.Agreement.Offers`). The offer variable `cagof` is drawn from parentOU's offers but dispatched with the childOU's RefId and AgreementId. This is a copy-paste error.

**Key design notes:**
- **POU→COU order:** POU scope processed first (lines 47–92), then COU scope (lines 96–146). Opposite of CCBS_CHANGE_PP_OU.
- **Per-offer dispatch:** One event per qualifying Agreement Offer (not per OU).
- **Parameter[1] validation:** If non-blank → must be "ADD" or "REMOVE" (DATA_ISSUE exception otherwise). If non-blank → `agof.Action = param` for each offer.
- **FE_OR_CCBS filter:** Read per offer and passed to PreExecCheck helper. NOT used as a dispatch gate.
- **reqSuccess check:** Per-OU (not per-offer): `Response[ReferenceId==OU.RefId && CompletionStatus==2]` → skip all offers in that OU on resubmit.
- **logicalDateVal computed but unused:** Loaded from BE concept + LargeCustomerIndicator=89 override, but never passed to XSLT. Dead code.
- **JMS headers not conditional:** JMSPriority/JMSCorrelationID/OrderID/RefID/UserName/PassWord always emitted (no xsl:if guards).
- **PurgePendingRequestsBeforeResubmit:** Called when isActResub==true.
- **Fan-in:** Delegated to `IsAllResponseSuccess(currActivity)` helper.

| Attribute | Value |
|-----------|-------|
| Backend system | OMX FM via `Events.OMConsumers.OMXFM.Request.CCBS_REMOVE_AGREEMENT_PRICE_PLAN` |
| Dispatch pattern | Per Agreement Offer; POU scope first, then COU |
| reqSuccess check | Per-OU RefId (not per-offer Soc) |
| Fan-in | `RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)` |
| Completion | Status="1" + SendDataToDB (if sent) or SkipActivity("4") |
| Steps in BN_CHANGE_PACKAGE | 18 |
| Response rulefunction | `Response_CCBS_REMOVE_AGREEMENT_PRICE_PLAN.rulefunction` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| priority | 5 |
| forwardChain | true |
| PurgePendingRequestsBeforeResubmit | Yes |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_REMOVE_AGREEMENT_PRICE_PLAN"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_REMOVE_AGREEMENT_PRICE_PLAN"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow Diagram

1. **LogicalDate:** Load from BE concept; if LargeCustomerIndicator=89 → override with tomorrow midnight (unused).
2. **isActResub + PurgePending:** If `RequestCount>0 && IsOrderResubmitted` → Purge pending requests.
3. **Parameter[1] validation:** If non-blank: validate in {"ADD","REMOVE"} or throw DATA_ISSUE.
4. **POU scope:** For each ParentOU → if Agreement.Offers > 0 → for each Offer: if param non-blank → `agof.Action = param`; read FE_OR_CCBS filter; reqSuccess check (by pOuRefId); if !reqSuccess → PreExecCheck via `GetXMLForAgreementOfferFilterWithExtendedInfo` → if "true" → dispatch → RequestCount++ → Logger.
5. **COU scope:** For each ChildOU → if childOU.Agreement.Offers > 0 → for each **parentOU**.Agreement.Offers (BUG): same per-offer loop with cOuRefId and `GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo`.
6. **isSkipped resolution:** If any event sent → Status="1" + `SendDataToDB`. Else → `SkipActivity("4")`.

---

## §6 — Parameter[1] Handling & Action Override

| Parameter[1] value | Behavior |
|-------------------|---------|
| Empty / blank | No validation. Offer.Action NOT overridden. |
| "ADD" | Validated OK. `agof.Action = "ADD"` for each offer. |
| "REMOVE" | Validated OK. `agof.Action = "REMOVE"` for each offer. |
| Any other value | Throws `Exception.newException("DATA_ISSUE", "Param is missing.", null)`. |

> Note: The Action value mutates the concept in working memory. The XSLT payload does NOT include Action — only EffectiveDate, ExpirationDate, OfferName, OfferInstanceId, RelatedOffers, ServiceType, Soc.

---

## §7 — reqSuccess Check & COU Bug

### §7.1 — reqSuccess Check (per-OU)

```java
for(iResp...) {
    if(String.equals(Response[iResp].ReferenceId, pOuRefId /* or cOuRefId */)
       && Response[iResp].CompletionStatus == 2) {
        reqSuccess = true;
    }
}
```

Matches on OU RefId (not offer Soc). If any response exists with that OU's RefId and CompletionStatus==2 → ALL offers in that OU are skipped on resubmit.

### §7.2 — COU Loop Bug

> [CRITICAL] Line 102: `for(int cof = 0; cof < parentOU.Agreement.Offers@length; cof++)`
> Should be: `cof < childOU.Agreement.Offers@length`
>
> Line 103: `Concepts.OrderRequest.OrderElements.AgreementOffers cagof = parentOU.Agreement.Offers[cof];`
> Should be: `childOU.Agreement.Offers[cof]`
>
> **Impact:** COU scope dispatches parentOU's Agreement Offers (not childOU's) tagged with cOuRefId and cAgId (childOU's AgreementId). Results in mismatch: childOU AgreementId + parentOU SOC data + childOU RefId.

---

## §8 — System & Integration Dependencies

### §8.1 — ESB / JMS Channel Dependencies

| Direction | Event Type | Gate | Purpose |
|-----------|-----------|------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_REMOVE_AGREEMENT_PRICE_PLAN` | Per offer: Agreement.Offers > 0, PreExecCheck, !reqSuccess | Remove price plan from agreement |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Always after each event | Request audit |

### §8.2 — Backend API Details

| Attribute | Value |
|-----------|-------|
| System | OMX FM / CCBS |
| Operation | removePricePlanFromAgreement |
| Payload schema | `ns:RemovePricePlanRequest` (RemovePricePlanRequest.xsd) |
| Key elements | AgreementIdInfo (AgreementNo), SrvAgrInfo (EffectiveDate, ExpirationDate, Name, OfferInstanceId, RelatedOffers, ServiceType, Soc), ActivityInfo (ActivityReason, UserText) |

### §8.3 — PreExecCheck Helpers per Scope

| Scope | Helper | Arguments |
|-------|--------|-----------|
| POU | `GetXMLForAgreementOfferFilterWithExtendedInfo(orderRequest, pOuRefId, agof.Soc, filter)` | pOuRefId, agof.Soc, FE_OR_CCBS value |
| COU (bug: uses parentOU offers) | `GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo(orderRequest, cOuRefId, cagof.Soc, pOuRefId, filter)` | cOuRefId, cagof.Soc (from parentOU!), pOuRefId |

---

## §9 — Payload Build — CCBS_REMOVE_AGREEMENT_PRICE_PLAN Event

### §9.1 — JMS / Event Header Fields (NOT conditional — always emitted)

| Header | Source | Condition |
|--------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | **Always** (no xsl:if) |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | **Always** |
| OrderID | `$orderRequest/OrderData/OrderID` | **Always** |
| RefID | `$pOuRefId` or `$cOuRefId` | **Always** |
| UserName | `$orderRequest/OrderData/User` | **Always** |
| PassWord | `$orderRequest/OrderData/Password` | **Always** |
| OrderType | `$orderRequest/OrderData/OrderType` | Conditional: if exists |
| CES | `$orderRequest/OrderData/CES` | Conditional: if exists |

### §9.2 — Payload Structure: ns:RemovePricePlanRequest

```text
ns:RemovePricePlanRequest
├── ns1:AgreementIdInfo
│   └── ns1:AgreementNo ← $pAgId / $cAgId                 [Always]
├── ns2:SrvAgrInfo
│   ├── ns2:EffectiveDate  ← $agof/EffectiveDate           [Conditional]
│   ├── ns2:ExpirationDate ← $agof/ExpirationDate          [Conditional]
│   ├── ns2:Name           ← $agof/OfferName               [Conditional]
│   ├── ns2:OfferInstanceId ← $agof/OfferInstanceId        [Conditional]
│   ├── ns2:RelatedOffers[*] ← for-each $agof/RelatedOffersArray
│   │   ├── ns2:Name        ← OfferName                    [Conditional]
│   │   ├── ns2:ServiceType ← ServiceType                  [Conditional]
│   │   └── ns2:Soc         ← Soc                          [Conditional]
│   ├── ns2:ServiceType    ← $agof/ServiceType             [Conditional]
│   └── ns2:Soc            ← $agof/Soc                     [Conditional]
└── ns3:ActivityInfo
    ├── ns3:ActivityReason ← $activityReason (or "CREQ")   [Always]
    └── ns3:UserText       ← $userText                     [Always]

NOTE: logicalDateVal/EnclosedClientInfo NOT included in payload (dead code in rule).
```

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID suffix | _REQ |
| OPERATION_NAME | "CCBS_REMOVE_AGREEMENT_PRICE_PLAN" |
| TARGET_SYSTEM | OMX_FM |
| AUDIT_TRACE | "Request Sent for CCBS_REMOVE_AGREEMENT_PRICE_PLAN" |

---

## §12 — Activity Status Management

| Condition | Action |
|-----------|--------|
| Any event dispatched (isSkipped==false) | `Status = GetActivityStatusString("1", false)`; `SendDataToDB(orderRequest)` |
| No events dispatched (isSkipped==true) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_REMOVE_AGREEMENT_PRICE_PLAN (rule)
├── Instance.getByExtIdByUri("LogicalDate") → logicalDateVal [computed, unused]
├── isActResub = (RequestCount>0 && IsOrderResubmitted)
├── [if isActResub] PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── [if LargeCustomerIndicator=89] tomorrowLogicalDate = DateTime.addDay(now,1) [unused]
├── XPath.evalAsString(Parameter[1]) → param
├── [if param not blank] validate in {"ADD","REMOVE"} or throw DATA_ISSUE
└── try {
    ├── [POU: for each ParentOU.Agreement.Offers]
    │   ├── [if param not blank] agof.Action = param
    │   ├── XPath.evalAsString(agof.ExtendedInfo[FE_OR_CCBS]/Value) → filter
    │   ├── [reqSuccess: Response[ReferenceId==pOuRefId && CompletionStatus==2]]
    │   ├── [if !reqSuccess]
    │   │   ├── GetXMLForAgreementOfferFilterWithExtendedInfo(...)
    │   │   ├── XPath.execute(PreExecCheck) → chkRes
    │   │   ├── [if "true"] dispatch + RequestCount++ + Logger
    ├── [COU: for each ChildOU]
    │   ├── [BUG: iterates parentOU.Agreement.Offers, not childOU!]
    │   ├── [reqSuccess: Response[ReferenceId==cOuRefId && CompletionStatus==2]]
    │   ├── [if !reqSuccess]
    │   │   ├── GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo(...)
    │   │   ├── XPath.execute(PreExecCheck) → chkRes
    │   │   ├── [if "true"] dispatch + RequestCount++ + Logger
    ├── [if !isSkipped] Status="1"; SendDataToDB(orderRequest)
    └── [else] SkipActivity("4")
} catch → HandleActivityException()
```

---

## §17 — Migration Notes & Recommendations

| Note | Severity | Detail |
|------|----------|--------|
| COU loop iterates parentOU offers | [CRITICAL] | Line 102 uses parentOU.Agreement.Offers for COU scope. Should be childOU.Agreement.Offers. Copy-paste error creates data mismatch for COU dispatches. |
| logicalDateVal computed but unused | [MEDIUM] | LargeCustomerIndicator=89 check and tomorrowLogicalDate computation are dead code for this FM. No LogicalDate/EnclosedClientInfo in payload. Appears to be an incomplete port from CCBS_CHANGE_PP_OU. |
| JMS headers emitted unconditionally | [LOW] | No xsl:if guards on JMSPriority/JMSCorrelationID etc. Empty XML elements if source null. Backend tolerance for empty headers should be verified. |
| reqSuccess check is per-OU, not per-offer | [MEDIUM] | On resubmit, if any one offer in the OU was successfully processed, ALL offers in that OU are skipped. |
| Fan-in via IsAllResponseSuccess helper | [INFO] | Unlike most FMs, uses a helper instead of inline XPath. Verify helper implementation. |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_REMOVE_AGREEMENT_PRICE_PLAN {
    attribute { priority = 5; forwardChain = true; }
    declare { OrderRequest orderRequest; Activity orderCurrentActivity; }
    when { /* extId / ActivityID=="CCBS_REMOVE_AGREEMENT_PRICE_PLAN" / Status=="WAITING" */ }
    then {
        try {
            logicalDateVal = LogicalDate.LogicalDate; // [unused]
            if(LargeCustomerIndicator==89)
                logicalDateVal = DateTime.format(DateTime.addDay(now,1),...); // [unused]

            isActResub = (RequestCount>0 && IsOrderResubmitted);
            if(isActResub) PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

            param = XPath.evalAsString(Parameter[1]);
            if(!IsBlank(param) && !(param=="ADD" || param=="REMOVE"))
                throw Exception("DATA_ISSUE", "Param is missing.", null);

            for(p: ParentOU) {
                // POU scope
                for(of: parentOU.Agreement.Offers) {
                    if(!IsBlank(param)) agof.Action = param;
                    filter = agof.ExtendedInfo[FE_OR_CCBS].Value;
                    reqSuccess = any(Response[ReferenceId==pOuRefId && CompletionStatus==2]);
                    if(!reqSuccess) {
                        chkRes = GetXMLForAgreementOfferFilterWithExtendedInfo + XPath.execute(PreExecCheck);
                        if(chkRes=="true") {
                            reqEvent = Event.createEvent("xslt://CCBS_REMOVE_AGREEMENT_PRICE_PLAN [POU]"); /* §9 */
                            Event.Ext.sendEventImmediate(reqEvent); RequestCount++; isSkipped=false;
                            Logger("Request Sent for CCBS_REMOVE_AGREEMENT_PRICE_PLAN");
                        }
                    }
                }
                // COU scope [BUG: iterates parentOU.Agreement.Offers, not childOU!]
                for(c: ChildOU) {
                    for(cof: parentOU.Agreement.Offers /* should be childOU */) {
                        reqSuccess = any(Response[ReferenceId==cOuRefId && CompletionStatus==2]);
                        if(!reqSuccess) {
                            chkRes = GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo + XPath.execute(PreExecCheck);
                            if(chkRes=="true") {
                                reqEvent = Event.createEvent("xslt://CCBS_REMOVE_AGREEMENT_PRICE_PLAN [COU]"); /* §9 */
                                Event.Ext.sendEventImmediate(reqEvent); RequestCount++; isSkipped=false;
                                Logger("Request Sent for CCBS_REMOVE_AGREEMENT_PRICE_PLAN");
                            }
                        }
                    }
                }
            }
            if(!isSkipped) { Status="1"; SendDataToDB(orderRequest); }
            else { SkipActivity("4"); }
        } catch(ae) { HandleActivityException; }
    }
}
```

---

## §19 — Response Message Rule (Response_CCBS_REMOVE_AGREEMENT_PRICE_PLAN)

### §19.1 — Overview

Creates a `CCBS_RemoveAgreementPricePlanRes` concept (specific type, NOT generic ResponseBase) with `@Id = sysNanoTimeValue` (not extId), appends to `currActivity.Response`, sends Logger with dynamic AUDIT_TRACE, and calls `IsAllResponseSuccess(currActivity)` for fan-in.

### §19.2 — Scope Variables

| Variable | Type |
|----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_REMOVE_AGREEMENT_PRICE_PLAN` |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` |

### §19.3 — Response Concept Construction

```text
createObject (Concepts.FM.Response.CCBS_RemoveAgreementPricePlanRes)
└── object
    ├── @Id              ← $sysNanoTimeValue (System.nanoTime())   [Always — NOT extId!]
    ├── ResponseCode     ← $eventResponse/ResponseCode             [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg              [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus         [Conditional]
    └── ReferenceId      ← $eventResponse/RefID                    [Conditional]

Key differences from other FMs:
- Concept type: CCBS_RemoveAgreementPricePlanRes (specific, not generic ResponseBase)
- @Id = sysNanoTimeValue (not extId via generateTrackingID)
```

### §19.4 — Response Completion Logic

| Attribute | Value |
|-----------|-------|
| Fan-in method | `return RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)` |
| Inline XPath | None — fully delegated to helper |

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID suffix | _RES |
| OPERATION_NAME | "CCBS_REMOVE_AGREEMENT_PRICE_PLAN" |
| AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` — **dynamic** (includes RefID) |

> AUDIT_TRACE is dynamic (includes response RefID) — unlike most other FMs which use a static string.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
