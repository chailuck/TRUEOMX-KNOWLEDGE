# Request_OMX_ADD_NXT_PP

> OMX Add Next Price Plan — Schedule Future SOC Change Across All Offer Contexts

**Priority:** 5 | **forwardChain:** true | **Author:** warawich-nb | **Pattern:** IntraActivitySequencing (per-offer) | **Event dispatched:** OMX_ADD_FUTURE | **futureType:** NXTPP | **Generated:** 2026-07-27

---

## §1 — Overview & Purpose

This rule schedules a "Next Price Plan" (NXTPP) future SOC change for each offer in the order that has a `SocProperties`-encoded next price plan. It iterates across four contexts — POU Agreement, POU Subscriber, COU Agreement, and COU Subscriber — and sends one `OMX_ADD_FUTURE` JMS event per qualifying offer. The effective date is computed from the logical date, bill cycle, and a duration extracted from SocProperties.

> **Event type note:** The JMS request event is `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE`, not OMX_ADD_NXT_PP. The same event type is shared with `OMX_ADD_NEXT_OFFER` (distinguished by `futureType` field: "NXTPP" here vs "NXTOFFER" there).

> **LogicalDate concept:** Before iterating, reads `/Concepts/OM/LogicalDate` to support simulated date testing. If `LogicalDate.LogicalDate` is non-blank, uses that date; otherwise falls back to `DateTime.now()`.

> **FE_OR_CCBS filter:** Subscriber-level offers (POU Sub, COU Sub) are only processed when `FE_OR_CCBS = "FE"`. Agreement-level offers (POU Agreement, COU Agreement) are processed regardless of FE_OR_CCBS value.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_OMX_ADD_NXT_PP` |
| Priority | 5 |
| forwardChain | true |
| Author | warawich-nb |
| JMS Event dispatched | `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` (shared with OMX_ADD_NEXT_OFFER) |
| Request schema root | `ns3:futureOrderWithSoc` (FutureOrderWithSoc.xsd) |
| futureType | "NXTPP" (hardcoded static) |
| requestedBy | "OMX" (hardcoded static) |
| requestedByUser | `OrderData.Channel` |
| Audit gate | LOG_LEVEL=INFO; payload conditional on WritePayload global |
| Fan-in helper | `IsAllResponseSuccess(currActivity)` — shared helper, not inline XPath |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity instance |
| 2 | `orderCurrentActivity.ActivityID == "OMX_ADD_NXT_PP"` | Targets this FM only |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_ADD_NXT_PP"` | Order-level double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Fresh activity only |

---

## §5 — Execution Flow

```text
1. Init: isActResub; read LogicalDate concept (fall back to DateTime.now() if blank)
         init requestedDate=now, requestedBy="OMX", requestedByUser=Channel
         futureType="NXTPP", isSkipped=true
2. For each POU Agreement Offer:
     - read FE_OR_CCBS (no filter applied)
     - evaluate PreExecCheck via GetXMLForAgreementOffer
     - check reqSuccess by pOu.OUId
     - GetNextPricePlan(socProps)  => blank: continue
     - build userText with "NXTPP " prefix in middle segment
     - GetNextPricePlanDurationMonth, GetBillCycle, GetNextPricePlanEffectiveDate
     - GetSocCodeFromName => blank: continue
     - send OMX_ADD_FUTURE (nodeLevel=3, nodeId=pOuId); RequestCount++
3. For each POU Subscriber Offer:
     - FE_OR_CCBS="FE" filter enforced
     - PreExecCheck via GetXMLForSubscriberOffer
     - reqSuccess by subscriberPou.SubscriberId
     - read FLG_SMS for FLG_SMS_WELCOME_SUB (OMX-2896)
     - nodeLevel=5, nodeId=subId; RequestCount++
4. For each COU Agreement Offer:
     - only enters if nxtPPName non-empty (checked before PreExecCheck)
     - PreExecCheck via GetXMLForAgreementOfferInChildOU
     - adds OU_ID and AGR_ID extendedInfo
     - nodeLevel=3, nodeId=cOu.OUId; RequestCount++
5. For each COU Subscriber Offer:
     - FE_OR_CCBS="FE" filter enforced
     - PreExecCheck via GetXMLForSubscriberOfferInChildOU
     - adds OU_ID extendedInfo (always, not conditional)
     - nodeLevel=5, nodeId=subId; RequestCount++
6. If any event sent => status IN_PROGRESS + SendDataToDB
   else => SkipActivity("4")
7. Exception => HandleActivityException
```

---

## §8 — System & Integration Dependencies

### §8.1 — JMS / ESB Channel Dependencies

| Direction | Event | Method | Note |
|-----------|-------|--------|------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` | `sendEventImmediate` | One per qualifying offer; shared with OMX_ADD_NEXT_OFFER; distinguished by futureType="NXTPP" |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `sendEventImmediate` | Per-offer after each send; LOG_LEVEL=INFO; payload conditional on WritePayload |

### §8.2 — Helper Function Dependencies

| Function | Purpose |
|----------|---------|
| `GetNextPricePlan(socProps)` | Parses SocProperties to extract next PP offer name; blank = no NXTPP scheduled |
| `GetNextPricePlanDurationMonth(socProps)` | Parses SocProperties for duration in months until next PP |
| `GetNextPricePlanEffectiveDate(logicalDate, billCycleNo, durationMonth)` | Computes future effective date |
| `GetSocCodeFromName(orderRequest, nxtPPName)` | Looks up SOC code for next PP name from order catalog |
| `GetBillCycle(orderRequest)` | Returns customer's bill cycle number |
| `GetXMLForAgreementOffer` / `GetXMLForAgreementOfferInChildOU` | Serialises agreement offer for PreExecCheck |
| `GetXMLForSubscriberOffer` / `GetXMLForSubscriberOfferInChildOU` | Serialises subscriber offer for PreExecCheck |
| `IsAllResponseSuccess(currActivity)` | Fan-in: returns "true" when all responses have CompletionStatus=2 |
| `BRMS.IsBlankOrStringNull(str)` | Null/blank guard used before each continue skip |

### §8.3 — Concept Dependency

| Concept | Path | Purpose |
|---------|------|---------|
| `LogicalDate` | `/Concepts/OM/LogicalDate` | Simulated date for effective date calculation; falls back to `DateTime.now()` if blank |

---

## §9 — Request Payload — futureOrderWithSoc

> Four XSLT variants (POU-Agreement, POU-Subscriber, COU-Agreement, COU-Subscriber). All share the same root structure; differences are in RefID, nodeLevel, nodeId, and extendedInfo entries.

```text
createEvent
+-- JMSPriority          <- OrderPriority                                    [Conditional]
+-- JMSCorrelationID     <- OrderData/OMXTrackingId                          [Conditional]
+-- OrderID              <- OrderData/OrderID                                [Conditional]
+-- RefID                <- agreeRefId (Agreement) OR subRefId (Subscriber)  [Always]
+-- UserName             <- OrderData/User                                   [Conditional]
+-- PassWord             <- OrderData/Password                               [Conditional]
+-- OrderType            <- OrderData/OrderType                              [Conditional]
+-- payload
    +-- ns3:futureOrderWithSoc
        +-- ns:futureOrder
        |   +-- ns:effectiveDate   <- effectiveDate (computed)               [Always]
        |   +-- ns:status          <- 1                                      [Always static]
        |   +-- ns:orderType       <- 2                                      [Always static]
        |   +-- ns:nodeLevel       <- 3 (Agreement) OR 5 (Subscriber)       [Always]
        |   +-- ns:nodeId          <- pOuId/cOu.OUId (Agreement) OR subId   [Always]
        |   +-- ns:requestedDate   <- DateTime.now()                        [Always]
        |   +-- ns:requestedBy     <- "OMX"                                  [Always static]
        |   +-- ns:dealerCode      <- OrderData/DealerCode                  [Conditional]
        |   +-- ns:activityReason  <- OUActivityInfo/ActivityReason         [Conditional]
        |   +-- ns:extendedInfo POU_ID     <- pOuId                         [Conditional: non-empty]
        |   +-- ns:extendedInfo CUS_ID     <- custId                        [Conditional: non-empty]
        |   +-- ns:extendedInfo PAGR_ID    <- pAgreeId                      [Conditional: non-empty]
        |   +-- ns:extendedInfo SUB_ID     <- subId         (Sub variants)  [Conditional: non-empty]
        |   +-- ns:extendedInfo MOBILE_NO  <- msisdn        (Sub variants)  [Conditional: non-empty]
        |   +-- ns:extendedInfo FLG_SMS_WELCOME_SUB (Sub variants, OMX-2896) [Conditional: non-empty]
        |   +-- ns:extendedInfo OU_ID      <- cOu.OUId     (COU variants)   [Conditional (COU Agree) / Always (COU Sub)]
        |   +-- ns:extendedInfo AGR_ID     <- cOu.Agreement.AgreementId (COU-Agree only) [Conditional]
        |   +-- ns:fromOrderId     <- OrderData/OrderID                     [Conditional]
        |   +-- ns:userText        <- formatted userText string             [Always]
        |   +-- ns:remark          <- currentPP + "->" + nxtPPName          [Always]
        |   +-- ns:customerType    <- OMXUtils:asciiCodeToText(CustomerTypeInfo/Type) [Always]
        |   +-- ns:accountSubtype  <- Account[AgreementRefId=ParentOU[n]/Agreement/RefId]/AccountSubType [Always]
        |   +-- ns:futureType      <- "NXTPP"                               [Always static]
        +-- ns2:futureSocs
            +-- ns2:futureSoc
                +-- ns2:code       <- nxtPPCode                              [Always]
                +-- ns2:effectiveDate <- effectiveDate                       [Always]
                +-- [for-each RelatedOffersArray] ns2:childSoc
                |   +-- ns2:code, ns2:parameter[], ns2:type, ns2:socName
                +-- ns2:type       <- 80                                     [Always static]
                +-- ns2:subType    <- "NXTPP"                               [Always static]
                +-- ns2:socName    <- nxtPPName                              [Always]
```

---

## §10 — Key Business Logic Details

### §10.1 — Four Iteration Contexts

| Context | RefID | nodeLevel | nodeId | FE_OR_CCBS Filter | PreExecCheck Helper |
|---------|-------|-----------|--------|-------------------|---------------------|
| POU Agreement | pOu.Agreement.RefId | 3 | pOuId | None (any source) | GetXMLForAgreementOffer |
| POU Subscriber | subscriberPou.RefId | 5 | SubscriberId | FE only | GetXMLForSubscriberOffer |
| COU Agreement | cOu.Agreement.RefId | 3 | cOu.OUId | None (any source) | GetXMLForAgreementOfferInChildOU |
| COU Subscriber | subscriberCou.RefId | 5 | SubscriberId | FE only | GetXMLForSubscriberOfferInChildOU |

### §10.2 — SocProperties-Driven Logic

```text
nxtPPName     = GetNextPricePlan(socProps)
durationMonth = GetNextPricePlanDurationMonth(socProps)
effectiveDate = GetNextPricePlanEffectiveDate(logicalDate, billCycleNo, durationMonth)
nxtPPCode     = GetSocCodeFromName(orderRequest, nxtPPName)

Skip (continue) if: nxtPPName is blank OR nxtPPCode is blank
```

### §10.3 — userText Construction

```text
POU Agreement:
  "{AgreementActivityInfo/UserText};NXTPP request by {Channel} on {dateTimeNow};"

Subscriber and COU contexts:
  "{SubscriberActivityInfo/UserText};request by {Channel} on {dateTimeNow};"

Note: POU Agreement includes "NXTPP " prefix; subscriber/COU levels do not.
```

### §10.4 — LogicalDate Override

```text
if (LogicalDate.LogicalDate is non-blank)
    logicalDate = DateTime.parseString(value, "yyyy-MM-dd'T'HH:mm:ssXXX")
else
    logicalDate = DateTime.now()
Purpose: allows test environments to simulate future dates.
```

### §10.5 — remark Format

```text
remark = currentPP + "->" + nxtPPName
Example: "PP_4G_299->PP_4G_399"
```

---

## §12 — Activity Status Management

| Trigger | Code | Status |
|---------|------|--------|
| Rule fires initially | 0 | WAITING |
| No qualifying offers found | 4 | SKIPPED |
| First event sent | 1 | IN_PROGRESS |
| Exception thrown | 3 | ERROR |
| All responses complete | 2 | COMPLETED |

---

## §15 — Function Dependency Tree

```text
Request_OMX_ADD_NXT_PP (rule)
+-- Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")
+-- [if non-blank] DateTime.parseString(LogicalDate.LogicalDate, ...)
+-- For each POU Agreement Offer[i]:
|   +-- ExtendedInfo scan for FE_OR_CCBS (no filter)
|   +-- GetXMLForAgreementOffer + XPath.execute PreExecCheck
|   +-- reqSuccess check: Response[ReferenceId=pOu.OUId, CompletionStatus=2]
|   +-- GetNextPricePlan(socProps)               [blank => continue]
|   +-- XPath.evalAsString(AgreementActivityInfo/UserText + current-dateTime())
|   +-- GetNextPricePlanDurationMonth + GetBillCycle + GetNextPricePlanEffectiveDate
|   +-- GetSocCodeFromName(orderRequest, nxtPPName) [blank => continue]
|   +-- Event.createEvent(xslt://OMX_ADD_FUTURE [POU-Agreement])
|   +-- Event.Ext.sendEventImmediate + [!isActResub] RequestCount++
|   +-- System.nanoTime() + sendEventImmediate(Logger)
+-- For each POU Subscriber Offer[j]:
|   +-- FE_OR_CCBS check: skip if != "FE"
|   +-- GetXMLForSubscriberOffer + PreExecCheck
|   +-- reqSuccess check: Response[ReferenceId=SubscriberId, CompletionStatus=2]
|   +-- GetNextPricePlan [blank => skip offer block]
|   +-- XPath.evalAsString(ExtendedInfo[FLG_SMS]/Value)   [OMX-2896]
|   +-- [same date helpers] + GetSocCodeFromName [blank => continue]
|   +-- Event.createEvent (POU-Subscriber variant) + send + Logger
+-- For each COU Agreement Offer[k]:
|   +-- [if nxtPPName non-empty] GetXMLForAgreementOfferInChildOU + PreExecCheck
|   +-- reqSuccess check: Response[ReferenceId=cOu.OUId, CompletionStatus=2]
|   +-- [same PP/code/date helpers] + Event.createEvent (COU-Agreement) + send + Logger
+-- For each COU Subscriber Offer[m]:
|   +-- FE_OR_CCBS filter + GetXMLForSubscriberOfferInChildOU + PreExecCheck
|   +-- [same helpers] + Event.createEvent (COU-Subscriber) + send + Logger
+-- GetActivityStatusString("1", false) + SendDataToDB   [if !isSkipped]
+-- SkipActivity("4")                                     [if isSkipped]
+-- HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_OMX_ADD_NXT_PP (rulefunction)
+-- Instance.createInstance(xslt://OMX_AddFutureRes)
|   +-- extId           = OMXUtils.generateTrackingID()
|   +-- ResponseCode    = eventResponse/ResponseCode        [Conditional]
|   +-- ResponseMessage = eventResponse/ResponseMsg         [Conditional]
|   +-- CompletionStatus= eventResponse/CompletionStatus    [Conditional]
|   +-- ReferenceId     = payload/AddFutureOrderResponse/nodeId [from payload body, unusual]
+-- currActivity.Response[n] = resEvent
+-- System.nanoTime()
+-- Event.Ext.sendEventImmediate(Logger)                    [LOG_LEVEL=INFO]
+-- return IsAllResponseSuccess(currActivity)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Four iteration contexts (POU-Agreement, POU-Subscriber, COU-Agreement, COU-Subscriber) each producing one `OMX_ADD_FUTURE` event per qualifying offer. All four must be preserved.
- **R2** — FE_OR_CCBS filter applied only at subscriber level (FE only); Agreement-level offers process regardless of FE_OR_CCBS value.
- **R3** — Skip (continue) when either `GetNextPricePlan` returns blank OR `GetSocCodeFromName` returns blank. Both guards required.
- **R4** — LogicalDate concept support required for test/simulation environments.
- **R5** — Fan-in via `IsAllResponseSuccess`: checks CompletionStatus=2, NOT ResponseCode "000" suffix. Verify helper contract before migration.
- **R6** — `ReferenceId` sourced from `payload/AddFutureOrderResponse/nodeId` (payload body), not event header RefID — unique among this process's response concepts.
- **R7** — OMX-2896: FLG_SMS_WELCOME_SUB extendedInfo required for subscriber-level offers when FLG_SMS ExtendedInfo present.
- **R8** — futureType="NXTPP", ns2:type=80, ns2:subType="NXTPP" are all static and must not vary at runtime (distinguish from OMX_ADD_NEXT_OFFER which uses "NXTOFFER").

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| OMX_ADD_FUTURE event shared with OMX_ADD_NEXT_OFFER — response routing must correlate by activityId | [MEDIUM] | Verify response handler routing; ensure activityId is in correlation key |
| ReferenceId from payload nodeId vs event header RefID — fan-in correlation differs from other FMs | [MEDIUM] | Verify IsAllResponseSuccess checks CompletionStatus, not ResponseCode suffix |
| LogicalDate is shared working memory — changing it affects all concurrent orders | [MEDIUM] | Externalise to request-scoped parameter in migration |
| POU Agreement userText has "NXTPP " prefix; subscriber levels do not — inconsistency | [LOW] | Document for downstream; normalise in migration if unintentional |
| COU Subscriber always emits OU_ID (unconditional); COU Agreement emits it conditionally — asymmetry | [LOW] | Preserve as-is; verify downstream expects unconditional OU_ID for COU subscriber |

---

## §19 — Response Message Rule (Response_OMX_ADD_NXT_PP)

### §19.1 — Overview

Creates one `OMX_AddFutureRes` concept per response and appends to `currActivity.Response[]`. Fan-in uses shared helper `IsAllResponseSuccess(currActivity)`. The `ReferenceId` is sourced from `payload/AddFutureOrderResponse/nodeId` (payload body), not the event header.

### §19.2 — OMX_AddFutureRes Fields

| Field | Source | Note |
|-------|--------|------|
| `extId` | `OMXUtils.generateTrackingID()` | Standard tracking ID |
| `ResponseCode` | `eventResponse/ResponseCode` | Conditional |
| `ResponseMessage` | `eventResponse/ResponseMsg` | Conditional |
| `CompletionStatus` | `eventResponse/CompletionStatus` | Conditional |
| `ReferenceId` | `payload/ns1:AddFutureOrderResponse/ns1:nodeId` | Sourced from payload body (unusual) |

### §19.3 — Fan-in Logic

```text
return IsAllResponseSuccess(currActivity)
// Checks: all Response entries have CompletionStatus = 2
// NOT the "000" suffix pattern used by most FMs in this process
```

> This is the only FM in this process using `IsAllResponseSuccess` for fan-in rather than inline `count(Response[tib:right(tib:trim(ResponseCode),3)="000"])`. Verify helper contract before migration.

### §19.4 — Response Audit

| Field | Value |
|-------|-------|
| PROCESS_ID | concat(pid, "_RES") |
| OPERATION_NAME | OMX_ADD_NXT_PP |
| LOG_LEVEL | INFO |
| payload | Conditional on WritePayload global |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
