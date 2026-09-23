# Request_OMX_EXP_FUT_OFFER

> External OMXFM — OMX Expire Future SOC Offer · futureOrderWithSoc schema (futureType=EXPSOC)

**Rule class:** `Rules.OMConsumers.OMXFM.Request.Request_OMX_EXP_FUT_OFFER`  
**Priority:** 5 | **forwardChain:** true | **Author:** RS33-BANDIT  
**Backend:** OMX FM (Internal) | **Integration:** JMS / Async | **Variants:** 4

---

## §1 — Overview & Purpose

`OMX_EXP_FUT_OFFER` records the *expiry* of future SOC offers in the OMX FM system. It sends a `futureOrderWithSoc` message (schema identical to OMX_ADD_FUT_OFFER) using `futureType='EXPSOC'` to mark existing future SOCs as expiring. It processes four contexts in order: ParentOU Agreement → ParentOU Subscriber → ChildOU Agreement → ChildOU Subscriber. Offers where `TR_NEXT_OFFER` or `TR_NEXT_PP` is defined are skipped (the offer is being *replaced*, not expired).

> Both request and response reuse the same `OMX_ADD_FUTURE` event/schema as `OMX_ADD_FUT_OFFER`. OMX FM distinguishes them by `ns:futureType` ('EXPSOC' vs 'FUTSOC').

| Property | Value |
|----------|-------|
| Rule class | `Rules.OMConsumers.OMXFM.Request.Request_OMX_EXP_FUT_OFFER` |
| Backend System | OMX FM (Future Management, internal OMX subsystem) |
| Integration type | JMS / Async |
| Request event | `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` |
| Response event | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` |
| Schema | `ns3:futureOrderWithSoc` (FutureOrderWithSoc.xsd); futureType='EXPSOC' |
| Response concept | `Concepts.FM.Response.OMX_AddFutureRes` (NOT standard ResponseBase) |
| RefID | `<agreementRefId|subscriberRefId> + ":" + <Soc>` |
| Dispatch | `Event.Ext.sendEventImmediate(reqEvent)`; manual RequestCount++ |
| TR_NEXT_OFFER guard | Skip offer if TR_NEXT_OFFER non-blank (ParentOU only — bug: missing for ChildOU) |
| Resubmit | Yes — `PurgePendingRequestsBeforeResubmit` called; RequestCount not re-incremented |
| Fan-in | `count(Response[last3ofResponseCode="000"]) == RequestCount` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule Name | `Request_OMX_EXP_FUT_OFFER` | External OMXFM request rule |
| Namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Priority | 5 | |
| forwardChain | true | |
| Author | RS33-BANDIT | |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — Customer hierarchy, agreement offers, subscriber offers, SocProperties |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — Response[], RequestCount, Status, Parameters |

> `logicalDateRes` (LogicalDate concept), `nextAct` (next Activity concept) fetched dynamically.

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Bind to current step |
| 2 | `orderCurrentActivity.ActivityID == "OMX_EXP_FUT_OFFER"` | Route to this rule |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_EXP_FUT_OFFER"` | Cross-check ProcessFlow |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Ready to execute |

---

## §5 — Execution Flow

1. **Setup** — Read LogicalDate singleton (parsed but unused — dead variable). `requestedDate = DateTime.now()`. If isActResub: `PurgePendingRequestsBeforeResubmit`. Fetch `nextAct`. Read `ORDERTYPE` parameter.
2. **ParentOU Agreement loop** — RefID = `pAgreeRefId + ":" + pagof.Soc`. Check reqSuccess. Evaluate PreExecCheck. If `TR_NEXT_OFFER` non-blank → `continue`. Compute isImmediateDate. Build event (Agreement XSLT); send; audit log; `RequestCount++` if !isActResub.
3. **ParentOU Subscriber loop** — RefID = `pSubRefId + ":" + psof.Soc`. Parse EXP_DATE_VALUE → `futOrderDate = expDate`. If TR_NEXT_OFFER non-blank OR (TR_NEXT_PP non-blank AND ≠ "null") → `continue`. Build event (Subscriber XSLT); send; log; RequestCount++.
4. **ChildOU Agreement loop** — RefID = `cAgreeRefId + ":" + cagof.Soc`. **⚠ No TR_NEXT_OFFER/TR_NEXT_PP skip check.** Build event (ChildOU Agreement XSLT); send; log; RequestCount++.
5. **ChildOU Subscriber loop** — RefID = `cSubRefId + ":" + csof.Soc`. **⚠ No TR_NEXT_OFFER/TR_NEXT_PP skip check.** Build event (ChildOU Subscriber XSLT); send; log; RequestCount++.
6. **Status** — if any sent: `GetActivityStatusString("1", false)` + `SendDataToDB`; else `SkipActivity(..., "4")`.
7. **Exception** — `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §7 — Data Extraction & Key Variables

| Variable | Source | Notes |
|----------|--------|-------|
| `paramOrderType` | `GetActivityParamValueFromKey(..., "ORDERTYPE")` | Overrides default orderType (38=Agreement, 4=Subscriber) |
| `requestedDate` | `DateTime.now()` | Always current time — LogicalDate parsed but unused |
| `requestedBy` | `orderRequest.OrderData.Channel` | ns:requestedBy field |
| `custId` | `orderRequest.OrderData.Customer.CustomerId` | CUS_ID extendedInfo |
| `logicalDate` | `logicalDateRes.LogicalDate` (parsed) | **Dead variable — never passed to XSLT** |
| `expDateValue` | `offer.ExtendedInfo[EXP_DATE_VALUE]/Value` | Subscriber variants only |
| `futOrderDate` | `expDate` (same as EXP_DATE_VALUE parsed) | Note: was `expDate+1` — `addDay(expDate,1)` commented out at line 185 |
| `isImmediateDate` | CustomerType==73 ∧ PackType=OC ∧ trOfferGroup=NET|RED ∧ specialOfferInd≠ROAM | Adds SEND_DATE_IMMEDIATE=Y |
| `trNextOffer` | `SocProperties substringAfter("TR_NEXT_OFFER=")` | If non-blank → skip (ParentOU Agreement; Subscriber) |
| `trNextpp` | `SocProperties substringAfter("TR_NEXT_PP=")` | If non-blank and ≠"null" → skip (Subscriber only) |

### effectiveDate Resolution (Subscriber variants — 3-way priority)

```xpath
1. if MCS_EXP_DATE_VALUE present         → effectiveDate = MCS_EXP_DATE_VALUE
2. else if LOGICALDATE_PROV='B' OR DataInfo/ExpDate present
                                          → effectiveDate = futOrderDate (= expDate)
3. else if EXP_DATE_VALUE present         → effectiveDate = EXP_DATE_VALUE

// Agreement variants: only 2 branches (no LOGICALDATE_PROV/DataInfo check)
1. if MCS_EXP_DATE_VALUE                  → effectiveDate = MCS_EXP_DATE_VALUE
2. else EXP_DATE_VALUE if present
```

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event | Protocol | Purpose |
|-----------|-------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` | JMS | Send futureOrderWithSoc (EXPSOC) to OMX FM |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` | JMS | Receive expiry confirmation from OMX FM |

### §8.3 Backend API Details

| System | Operation | Schema | Correlation |
|--------|-----------|--------|-------------|
| OMX FM | ExpireFutureSOC | `ns3:futureOrderWithSoc`; futureType='EXPSOC' | RefID = `<refId>:<Soc>`; fan-in: RequestCount == count(000 responses) |

### §8.4 Variant Comparison Table

| Property | ① POU Agreement | ② POU Subscriber | ③ COU Agreement | ④ COU Subscriber |
|----------|-----------------|------------------|-----------------|------------------|
| `nodeLevel` | 3 (OU) | 5 (Subscriber) | 3 (OU) | 5 (Subscriber) |
| `nodeId` | pOuId | pSubId (CRM) | cOuId | cSubId (CRM) |
| `orderType` | param or 38 | param or 4 | param or 38 | param or 4 |
| TR_NEXT_OFFER guard | ✓ | ✓ | **⚠ Missing** | **⚠ Missing** |
| ASSET_ID extendedInfo | — | ✓ (psub.AssetCrmId) | — | — |
| OU_ID extendedInfo | — | — | — | ✓ (cOuId) |
| RELATED_ORDER forwarded | ✓ | — | — | — |
| SBM_CHANNEL / SBM_PROVISIONING / PROVISIONING | — | ✓ | — | ✓ |
| MCS_EXP_DATE_VALUE bug | — | — | — | ✓ (typo 'VALU') |

### §8.5 Activity Parameters

| Parameter | Effect |
|-----------|--------|
| `ORDERTYPE` | Overrides default ns:orderType (38=Agreement level, 4=Subscriber level) |
| `USE_ROWID_CRM` | Controls MapSubscriberIdFromCRM for subscriber nodeId |

---

## §9 — SBM_CHANNEL / SBM_PROVISIONING Logic (Subscriber variants)

```xpath
// SBM_CHANNEL: order-level overrides auto-detect
if not(exists(orderRequest.ExtendedInfo[SBM_CHANNEL]))
    if offer.FE_OR_CCBS='BRMS' AND offer.ServiceType IN ('86','87')
        → SBM_CHANNEL = 'OMX'
if exists(orderRequest.ExtendedInfo[SBM_CHANNEL])
    → SBM_CHANNEL = order-level value  // always written if present

// SBM_PROVISIONING=N: two independent paths
if exists(offer.ExtendedInfo[SBM_NO_PROVISIONING])
    → SBM_PROVISIONING = 'N'
else if exists(offer.DataInfo[PackType='OC']) AND offer.ExtendedInfo[EXP_TYPE]='FUT'
    → SBM_PROVISIONING = 'N'

// PROVISIONING=N
if exists(offer.ExtendedInfo[LOGICALDATE_PROV])
    → PROVISIONING = 'N'
```

---

## §10 — XSLT Field Mapping — Output XML Tree (Subscriber variant)

```text
createEvent
└── event
    ├── JMSPriority            ← $orderRequest/OrderPriority                      [Conditional]
    ├── JMSCorrelationID       ← $orderRequest/OrderData/OMXTrackingId            [Always]
    ├── OrderID                ← $orderRequest/OrderData/OrderID                  [Always]
    ├── RefID                  ← $refId (= subRefId + ":" + Soc)                  [Always]
    ├── UserName               ← $orderRequest/OrderData/User                     [Conditional]
    ├── PassWord               ← $orderRequest/OrderData/Password                 [Conditional]
    ├── OrderType              ← $orderRequest/OrderData/OrderType                [Always]
    └── payload
        └── ns3:futureOrderWithSoc
            ├── ns:futureOrder
            │   ├── ns:effectiveDate  ← MCS_EXP_DATE_VALUE → futOrderDate → EXP_DATE_VALUE [Conditional]
            │   ├── ns:status         ← 1 (static)                               [Always]
            │   ├── ns:orderType      ← paramOrderType or 4/38                   [Always]
            │   ├── ns:nodeLevel      ← 5 (Subscriber) / 3 (Agreement)           [Always]
            │   ├── ns:nodeId         ← subId (CRM mapped)                       [Conditional: subId != ""]
            │   ├── ns:requestedDate  ← $requestedDate (DateTime.now())          [Always]
            │   ├── ns:requestedBy    ← $requestedBy (= Channel)                 [Always]
            │   ├── ns:dealerCode     ← $orderRequest/OrderData/DealerCode       [Conditional]
            │   ├── ns:activityReason ← $actReason                               [Conditional]
            │   ├── ns:extendedInfo POU_ID     ← $pOuId                          [Conditional: string-length > 0]
            │   ├── ns:extendedInfo CUS_ID     ← $custId                         [Conditional: string-length > 0]
            │   ├── ns:extendedInfo SUB_ID     ← $subId                          [Conditional: string-length > 0]
            │   ├── ns:extendedInfo MOBILE_NO  ← $msisdn                         [Conditional: string-length > 0]
            │   ├── ns:extendedInfo PROVISIONING=N                                [Conditional: LOGICALDATE_PROV exists]
            │   ├── ns:extendedInfo DMC_TRX_ID ← offer.ExtendedInfo[DMC_TRX_ID] [Conditional: exists]
            │   ├── ns:extendedInfo SBM_CHANNEL ← 'OMX' or order-level           [Conditional: complex 2-path]
            │   ├── ns:extendedInfo SBM_PROVISIONING=N                           [Conditional: SBM_NO_PROV or OC+FUT]
            │   ├── ns:extendedInfo SEND_DATE_IMMEDIATE=Y                         [Conditional: isImmediateDate]
            │   ├── ns:extendedInfo ASSET_ID ← $psub/AssetCrmId                  [ParentOU Subscriber only]
            │   ├── ns:fromOrderId    ← $orderRequest/OrderData/OrderID           [Conditional]
            │   ├── ns:userText       ← $userText                                 [Conditional]
            │   ├── ns:customerType   ← OMXUtils:asciiCodeToText(Type)            [Conditional]
            │   ├── ns:accountSubtype ← Account[Agreement.RefId]/AccountSubType  [Always]
            │   └── ns:futureType     ← 'EXPSOC' (static)                        [Always]
            └── ns2:futureSocs
                └── ns2:futureSoc (xsl:for-each over current offer)
                    ├── ns2:code         ← Soc                                    [Always]
                    ├── ns2:expireDate   ← MCS_EXP_DATE_VALUE or EXP_DATE_VALUE   [Conditional]
                    ├── ns2:instanceId   ← OfferInstanceId                         [Conditional]
                    ├── ns2:type         ← ServiceType                             [Conditional]
                    ├── ns2:subType      ← CUG|CONTRACT|IDD|IR|DISCOUNT|EXPSOC    [Always]
                    ├── ns2:socPrice     ← OfferRate                               [Conditional]
                    └── ns2:socName      ← OfferName                               [Conditional]
```

> **subType cascade:** CUG_IND=Y → 'CUG'; TR_CONTRACT_IND=Y → 'CONTRACT'; TR_IDD_FLAG=Y → 'IDD'; TR_IR_FLAG=Y → 'IR'; ServiceType='68' → 'DISCOUNT'; else → **'EXPSOC'** (vs 'FUTSOC' in ADD rule).

---

## §11 — Audit Logging

| Phase | AUDIT_TRACE | Gate |
|-------|-------------|------|
| Request sent | `Request Sent for OMX_EXP_FUT_OFFER` | Unconditional |
| Response received | `Response received for OMX_EXP_FUT_OFFER` | Unconditional |

---

## §12 — Activity Status Management

| Condition | Status | Additional action |
|-----------|--------|-------------------|
| At least one request sent | `GetActivityStatusString("1", false)` | `SendDataToDB(orderRequest)` |
| All offers skipped | [SKIPPED] | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception | Error state | `HandleActivityException` |

---

## §15 — Function Dependency Tree

```text
Request_OMX_EXP_FUT_OFFER (rule)
├── Instance.getByExtIdByUri("LogicalDate", ...)                        [read but unused — dead variable]
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(logicalDateRes.LogicalDate)
├── RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()  [if isActResub]
├── Instance.getByExtIdByUri(NextActivityName, ...)                     [nextAct for PreExecCheck]
├── GetActivityParamValueFromKey(..., "ORDERTYPE")
├── (ParentOU Agreement loop — per pagof)
│   ├── XPath.evalAsString() — FE_OR_CCBS filter
│   ├── GetXMLForAgreementOfferFilterWithExtendedInfo()
│   ├── XPath.execute() — PreExecCheck
│   ├── BRMS.IsBlank(trNextOffer)                                       [skip guard]
│   ├── Event.createEvent(xslt://OMX_ADD_FUTURE) [variant ①]
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   └── Event.Ext.sendEventImmediate(Logger)
├── (ParentOU Subscriber loop — per psof)
│   ├── GetActivityParameterValueFromKey("USE_ROWID_CRM")
│   ├── MapSubscriberIdFromCRM(psub, ...)
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo()
│   ├── XPath.evalAsString() — EXP_DATE_VALUE
│   ├── DateTime.parseString(expDateValue) → futOrderDate = expDate
│   ├── BRMS.IsBlank(trNextOffer|trNextpp)                              [skip guard]
│   ├── XPath.evalAsBoolean() — exists CustomerType AND PackType
│   ├── Event.createEvent(xslt://OMX_ADD_FUTURE) [variant ②]
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   └── Event.Ext.sendEventImmediate(Logger)
├── (ChildOU Agreement loop)    [same as POU Agreement; NO TR_NEXT_OFFER check]
├── (ChildOU Subscriber loop)   [same as POU Subscriber; NO TR_NEXT_OFFER/TR_NEXT_PP check]
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException()

Response_OMX_EXP_FUT_OFFER (rulefunction)
├── Instance.createInstance(xslt://Concepts/FM/Response/OMX_AddFutureRes)
│   → ResponseCode, ResponseMessage, CompletionStatus  (no ReferenceId)
├── currActivity.Response[length] = resEvent
├── Event.Ext.sendEventImmediate(Logger)
└── XPath.evalAsInt("count(Response[last3='000'])")
    → RequestCount == successResponseCount → "true" else "false"
```

---

## §17 — Migration Notes, Bugs & Recommendations

> **Bug #1 — ChildOU Subscriber MCS_EXP_DATE_VALUE effectiveDate typo:**  
> The `xsl:when test` checks `MCS_EXP_DATE_VALUE` but `xsl:value-of` reads `MCS_EXP_DATE_VALU` (missing 'E'). For ChildOU Subscriber offers with MCS_EXP_DATE_VALUE, `ns:effectiveDate` will be blank. Falls through to LOGICALDATE_PROV/EXP_DATE_VALUE fallback.

> **Bug #2 — TR_NEXT_OFFER / TR_NEXT_PP skip check absent for ChildOU:**  
> ParentOU loops skip offers where TR_NEXT_OFFER (or TR_NEXT_PP) is non-blank. ChildOU Agreement and ChildOU Subscriber loops do NOT perform this check — offers being replaced will still receive EXP_FUT_OFFER processing.

> **Dead variable — logicalDate (lines 26–31):**  
> `logicalDate` is parsed but `requestedDate = DateTime.now()` is set separately and sent. `logicalDate` is never used.

> **futOrderDate = expDate (not +1 day):**  
> `DateTime.addDay(expDate, 1)` is commented out at line 185. Current code uses `futOrderDate = expDate`. Intentionally changed; preserve.

> **RELATED_ORDER forwarded in Agreement variants only:**  
> `RELATED_ORDER` is forwarded via `xsl:for-each` in Agreement variants (①) but not in Subscriber variants (②③④). Appears intentional but should be verified.

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | futureType MUST be 'EXPSOC' for all 4 variants | [HIGH] |
| R2 | TR_NEXT_OFFER skip logic: apply consistently to all 4 variants (fix ChildOU) | [HIGH] |
| R3 | Fix ChildOU Subscriber XSLT: `MCS_EXP_DATE_VALU` → `MCS_EXP_DATE_VALUE` | [HIGH] |
| R4 | effectiveDate 3-way priority: MCS_EXP_DATE_VALUE → futOrderDate(LOGICALDATE_PROV) → EXP_DATE_VALUE | [HIGH] |
| R5 | SBM_CHANNEL / SBM_PROVISIONING logic: order-level override + BRMS/86/87 auto-detect | [MEDIUM] |
| R6 | ASSET_ID only for ParentOU Subscriber; OU_ID only for ChildOU | [MEDIUM] |
| R7 | futOrderDate = expDate (not +1) — preserve current behavior | [MEDIUM] |
| R8 | Remove dead logicalDate variable | [LOW] |

---

## §19 — Response Message Rule

### §19.1 Overview

Maps `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` into `Concepts.FM.Response.OMX_AddFutureRes`. Fan-in: `count(Response[last3 of ResponseCode == "000"]) == currActivity.RequestCount`. Note: OMX_AddFutureRes does NOT have a ReferenceId field (unlike standard ResponseBase).

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Audit log context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` | JMS response from OMX FM |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] array, RequestCount |

### §19.3 OMX_AddFutureRes Concept Construction

```text
createObject @extId ← OMXUtils.generateTrackingID()                [Always]
└── OMX_AddFutureRes concept
    ├── ResponseCode         ← $eventResponse/ResponseCode          [Conditional]
    ├── ResponseMessage      ← $eventResponse/ResponseMsg           [Conditional]
    ├── CompletionStatus     ← $eventResponse/CompletionStatus      [Conditional]
    └── (no ReferenceId field — OMX_AddFutureRes lacks this property)
```

### §19.4 Response Completion Logic

```java
int successResponseCount = XPath.evalAsInt(
  "count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = '000'])"
);
if(currActivity.RequestCount == successResponseCount) {
    return "true";   // All future SOC expirations confirmed → advance
} else {
    return "false";  // Still awaiting responses
}
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
