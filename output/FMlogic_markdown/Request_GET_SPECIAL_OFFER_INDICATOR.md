# Request_GET_SPECIAL_OFFER_INDICATOR

> SOC Property Batch Lookup — Collect All SOC Codes then Query in a Single Call

**Priority:** 5 | **forwardChain:** true | **Author:** smandal-t410 | **Pattern:** Single Batch Request | **Generated:** 2026-07-27

---

## §1 — Overview & Purpose

This rule retrieves SOC property indicators (primarily `TR_SPECIAL_OFFER_IND`) from a backend service for every offer in the order. It uses a **fundamentally different dispatch pattern** from the IntraActivitySequencing FMs: it first **collects all unique SOC codes** across the entire order (all subscribers, agreement offers, and their related offers, ParentOU + ChildOU), then sends a **single batch request** containing all those SOC codes in one call.

> **Different dispatch pattern:** This FM does NOT use IntraActivitySequencing. It sends one `Event.Ext.sendEventImmediate(reqEvent)` with all SOCs batched into a single `GetSpecialOfferIndicatorRequest`, increments `RequestCount` once, and always receives a single response.

> **GoldenDB routing fork:** If `orderRequest.OrderData.GoldenDB == "Y"`, the request is sent via a CES-based channel (`CES_GET_SPECIAL_OFFER_INDICATOR` event). Otherwise, the standard Amdocs RM3G-based channel is used.

**Two activity parameters control runtime behavior:**
- `ADD_PROP` — comma-separated list of additional SOC property names to retrieve alongside `TR_SPECIAL_OFFER_IND`
- `CHECK_LOYALTY_SOC=Y` — triggers loyalty SOC detection: if the returned value starts with "LY", creates `LOYALTY` and `OLD_LOYALTY_SOC` ExtendedInfo

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_GET_SPECIAL_OFFER_INDICATOR` |
| Priority | 5 |
| forwardChain | true |
| Author | smandal-t410 |
| Dispatch pattern | Single batch request — NOT IntraActivitySequencing; one request for all SOCs |
| GoldenDB routing | Yes — two distinct event types depending on `OrderData.GoldenDB == "Y"` |
| Activity parameter: ADD_PROP | Optional comma-separated list of additional SOC property names |
| Activity parameter: CHECK_LOYALTY_SOC | "Y" triggers LOYALTY / OLD_LOYALTY_SOC ExtendedInfo creation |
| Pre-filter guard | Only collects SOC codes where `count(ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR']) = 0` |
| Deduplication | `Collections.createArrayList()` + `Collections.contains()` — unique SOC list |
| Request payload schema | `http://www.tibco.com/schemas/OMX_FM/SharedResources/Schema Definitions/GetSpecialOfferIndicatorRequest.xsd` |
| Response payload schema | `http://www.tibco.com/schemas/OMX_FM/SharedResources/Schema Definitions/GetSpecialOfferIndicatorResponse.xsd` |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity |
| 2 | `orderCurrentActivity.ActivityID == "GET_SPECIAL_OFFER_INDICATOR"` | Targets only this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "GET_SPECIAL_OFFER_INDICATOR"` | Order-level double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires on fresh activity |

---

## §5 — Execution Flow

```text
1.  Init — isActResub, create empty alSOCs ArrayList,
           read ADD_PROP param into paramValue,
           specOfferIndPropName = "TR_SPECIAL_OFFER_IND"
2.  PreExecCheck — evaluate XPath; if false → SkipActivity("4")
3.  SOC Collection: ParentOU.Subscriber offers
    for each ParentOU[i].Subscriber[j].SubscriberOffers[k]:
      if count(ExtendedInfo[SPECIAL_OFFER_INDICATOR])=0:
        add Soc + RelatedOffersArray[l].Soc to alSOCs (deduped)
4.  SOC Collection: ParentOU.Agreement offers
    for each Agreement.Offers[j]: same guard → add Soc + RelatedOffersArray[k].Soc
5.  SOC Collection: ChildOU.Subscriber offers (same pattern)
6.  SOC Collection: ChildOU.Agreement offers (same pattern)
7.  socStrings = Collections.toArray(alSOCs)
8.  GoldenDB fork:
    if GoldenDB=="Y" → sendEventImmediate(CES_GET_SPECIAL_OFFER_INDICATOR event)
    else             → sendEventImmediate(GET_SPECIAL_OFFER_INDICATOR event)
9.  if !isActResub: orderCurrentActivity.RequestCount++
10. Audit log: "Request Sent for GET_SPECIAL_OFFER_INDICATOR"
11. Status = IN_PROGRESS; SendDataToDB
12. Collections.clear(alSOCs)
13. Exception → HandleActivityException
```

---

## §8 — System & Integration Dependencies

### §8.1 — Activity Parameter Dependencies

| Parameter Key | Values | Effect |
|--------------|--------|--------|
| `ADD_PROP` | Comma-separated property names (optional) | Additional `<propertyName>` elements added to request payload after `TR_SPECIAL_OFFER_IND` |
| `CHECK_LOYALTY_SOC` | "Y" or absent | If "Y": detects LY* indicator values and creates LOYALTY + OLD_LOYALTY_SOC ExtendedInfo |

### §8.2 — GoldenDB Routing Fork

**Path A — GoldenDB=Y (CES-based):**

| Attribute | Value |
|-----------|-------|
| Condition | `!IsBlankOrStringNull(OrderData.GoldenDB) AND GoldenDB == "Y"` |
| Event type | `Events.OMConsumers.OMXFM.Request.CES_GET_SPECIAL_OFFER_INDICATOR` |
| extId in event | Yes — `OMXUtils:generateTrackingID()` |
| Request namespace | `http://www.tibco.com/schemas/OMX_FM/SharedResources/Schema Definitions/GetSpecialOfferIndicatorRequest.xsd` (ns) |
| Root payload element | `ns:GetSpecialOfferIndicatorRequest` |
| Send method | `Event.Ext.sendEventImmediate` |

**Path B — Standard / Non-GoldenDB (Amdocs RM3G):**

| Attribute | Value |
|-----------|-------|
| Condition | else (GoldenDB absent or != "Y") |
| Event type | `Events.OMConsumers.OMXFM.Request.GET_SPECIAL_OFFER_INDICATOR` |
| extId in event | No |
| Request namespace (ns4) | Same schema as ns above; also imports Amdocs RM3G datatypes (ns, ns1, ns2, ns3) |
| Root payload element | `ns4:GetSpecialOfferIndicatorRequest` |
| Send method | `Event.Ext.sendEventImmediate` |

### §8.3 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Include credentials in request event |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `OMX_OM/WritePayload` | Include payload in audit log |

---

## §9 — Request Payload Build

### §9.1 — SOC Collection Logic (pre-payload)

```text
alSOCs = new ArrayList()

// 4 scan loops, each guarded by:
//   count(offer/ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR']) = 0

Scan ParentOU → Subscriber[j].SubscriberOffers[k]:
  if !SPECIAL_OFFER_INDICATOR already in offer:
    alSOCs.add(SubscriberOffers[k].Soc) (dedup)
    alSOCs.add(RelatedOffersArray[l].Soc for each l) (dedup)

Scan ParentOU → Agreement.Offers[j]:
  same pattern

Scan ParentOU → ChildOU[p] → Subscriber[q].SubscriberOffers[r]:
  same pattern

Scan ParentOU → ChildOU[p] → Agreement.Offers[q]:
  same pattern

socStrings = Collections.toArray(alSOCs)
```

### §9.2 — Request Payload Tree (both variants)

```text
createEvent
└── event
    ├── extId              ← OMXUtils:generateTrackingID()        [GoldenDB=Y only]
    ├── JMSPriority        ← $orderRequest/OrderPriority          [Conditional]
    ├── JMSCorrelationID   ← OrderData/OMXTrackingId              [Conditional]
    ├── OrderID            ← OrderData/OrderID                    [Conditional]
    ├── UserName/PassWord  ← OrderData/User, Password             [Credential-gated]
    ├── OrderType          ← OrderData/OrderType                  [Conditional]
    └── payload
        └── ns:GetSpecialOfferIndicatorRequest  (ns4: for standard path)
            ├── soc_cd ← $socStrings/elements[1]                 [xsl:for-each — one per unique SOC]
            ├── soc_cd ← $socStrings/elements[2]
            ├── ...    (repeated for all collected SOC codes)
            ├── propertyName ← "TR_SPECIAL_OFFER_IND"            [Always]
            └── propertyName ← tib:tokenize($paramValue,",")     [Conditional: ADD_PROP non-empty]
                               (one element per comma-separated ADD_PROP value)
```

---

## §12 — Activity Status Management

| Trigger | Code | Status |
|---------|------|--------|
| Rule fires | 0 | WAITING |
| PreExecCheck false | 4 | SKIPPED |
| Request sent | 1 | IN_PROGRESS |
| Exception | 3 | ERROR |
| Response handled | 2 | COMPLETED (set by response rulefunction) |

---

## §15 — Function Dependency Tree

```text
Request_GET_SPECIAL_OFFER_INDICATOR (rule)
├── Instance.getByExtIdByUri(NextActivityName, "Activity")       [nextAct for PreExecCheck]
├── GetActivityParamValueFromKey(orderCurrentActivity, "ADD_PROP") [paramValue]
├── Collections.List.createArrayList()                             [alSOCs]
├── XPath.evalAsBoolean("count(ExtendedInfo[SPECIAL_OFFER_INDICATOR])=0")  [guard, 4 variants]
├── Collections.contains(alSOCs, refId)                           [dedup check]
├── Collections.add(alSOCs, refId)
├── Collections.toArray(alSOCs)                                   [socStrings]
├── IsBlankOrStringNull(OrderData.GoldenDB)                       [routing fork]
├── [GoldenDB=Y] Event.createEvent(CES_GET_SPECIAL_OFFER_INDICATOR XSLT)
├── [GoldenDB=Y] Event.Ext.sendEventImmediate(reqEvent)
├── [default] Event.createEvent(GET_SPECIAL_OFFER_INDICATOR XSLT)
├── [default] Event.Ext.sendEventImmediate(reqEvent)
├── [if !isActResub] orderCurrentActivity.RequestCount++
├── Event.createEvent(xslt://Logger)                              [request audit]
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── Collections.clear(alSOCs)
└── HandleActivityException(...)

Response_GET_SPECIAL_OFFER_INDICATOR (rulefunction)
├── Instance.createInstance(xslt://GetSpecialOfferIndicatorRes)
│   ├── ResponseCode, ResponseMessage, CompletionStatus, ReferenceId
│   └── GetSpecialOfferIndicatorList[]: soc_cd + property_value[TR_SPECIAL_OFFER_IND]
├── currActivity.Response[n] = activityRes
├── GetActivityParamValueFromKey(currActivity, "CHECK_LOYALTY_SOC")
├── Loop: ParentOU.Agreement.Offers[]:
│   ├── Guard: count(ExtendedInfo[SPECIAL_OFFER_INDICATOR])=0
│   ├── XPath.evalAsString(response[soc_cd]/TR_SPECIAL_OFFER_IND property_value)
│   ├── [non-blank] createInstance(AgreementOffersExtendedInfo{SPECIAL_OFFER_INDICATOR})
│   └── Loop other properties: create or update AgreementOffersExtendedInfo
├── Loop: ParentOU.Subscriber.SubscriberOffers[]:
│   ├── Guard: count(ExtendedInfo[SPECIAL_OFFER_INDICATOR])=0
│   ├── createInstance(SubscriberOffersExtendedInfo{SPECIAL_OFFER_INDICATOR})
│   ├── [CHECK_LOYALTY_SOC=Y AND value starts with "LY"]:
│   │   ├── XPath.evalAsBoolean: exists(FE offer with SocProperties contains TR_SPECIAL_OFFER_IND=LY)
│   │   ├── [oldLoyaltySoc] createInstance(SubscriberOffersExtendedInfo{OLD_LOYALTY_SOC=Y})
│   │   └── createInstance(SubscriberOffersExtendedInfo{LOYALTY=substring-after(value,"LY")})
│   └── Loop other properties: create or update SubscriberOffersExtendedInfo
├── Loop: ChildOU.Agreement.Offers[]: [same as ParentOU.Agreement, no loyalty]
├── Loop: ChildOU.Subscriber.SubscriberOffers[]: [same as ParentOU.Subscriber, loyalty included]
├── Event.createEvent(xslt://Logger)   [response audit]
└── return "true"   // always — single batch response
```

---

## §19 — Response Message Rule

### §19.1 — Overview

Creates `GetSpecialOfferIndicatorRes` concept, then iterates all 4 offer containers (ParentOU Agreement, ParentOU Subscriber, ChildOU Agreement, ChildOU Subscriber) to write `SPECIAL_OFFER_INDICATOR` and additional property ExtendedInfo back onto each qualifying offer. Returns `"true"` unconditionally (no fan-in counting — single batch response).

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | All offer containers written with ExtendedInfo |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.GET_SPECIAL_OFFER_INDICATOR` | GetSpecialOfferIndicatorResponse payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; CHECK_LOYALTY_SOC param read |

### §19.3 — GetSpecialOfferIndicatorRes Concept Fields

| Field | Source | Notes |
|-------|--------|-------|
| extId | `OMXUtils:generateTrackingID()` | Always |
| ResponseCode | `$eventResponse/ResponseCode` | Conditional |
| ResponseMessage | `$eventResponse/ResponseMsg` | Conditional |
| CompletionStatus | `$eventResponse/CompletionStatus` | Conditional |
| ReferenceId | `$eventResponse/RefID` | Conditional |
| GetSpecialOfferIndicatorList[].soc_cd | `response.GetSpecialOfferIndicatorList/soc_cd` | For each entry |
| GetSpecialOfferIndicatorList[].property_value | `property_list[property_name="TR_SPECIAL_OFFER_IND"]/property_value` | TR_SPECIAL_OFFER_IND only |

### §19.4 — Loyalty SOC Detection Logic

```text
// Fires when CHECK_LOYALTY_SOC param == "Y" AND SPECIAL_OFFER_INDICATOR starts with "LY"
// Applies to both ParentOU and ChildOU SubscriberOffers

if (chkLoyaltySocParam == "Y" AND specialOfferIndExtInfo.Value.startsWith("LY")):

    oldLoyaltySoc = exists(Subscriber.SubscriberOffers[
        ExtendedInfo[Name="FE_OR_CCBS" AND Value="FE"]
        AND contains(SocProperties, "TR_SPECIAL_OFFER_IND=LY")
    ])

    if (oldLoyaltySoc):
        curOffer.ExtendedInfo[n] = {Name="OLD_LOYALTY_SOC", Value="Y"}

    curOffer.ExtendedInfo[n+1] = {
        Name="LOYALTY",
        Value=substring-after(specialOfferIndExtInfo.Value, "LY")
    }
```

### §19.5 — Response Completion

```text
return "true"   // always — single batch request/response, no counter tracking needed
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Cross-entity batch FM: one request for all SOC codes across ALL subscribers, agreements, ParentOU, and ChildOU. Migration must preserve the pre-aggregation and deduplication step.
- **R2** — The SPECIAL_OFFER_INDICATOR guard must be preserved in BOTH the collection phase AND the response write-back phase — each checks independently.
- **R3** — GoldenDB=Y routes to a different backend channel. Externalize this as a configurable routing strategy.
- **R4** — ADD_PROP parameter: additional property names requested dynamically; the response write-back loop handles all returned properties generically.
- **R5** — CHECK_LOYALTY_SOC=Y: LY-prefix detection adds two additional ExtendedInfo per qualifying offer; OLD_LOYALTY_SOC flag only set when subscriber already has a qualifying FE offer.
- **R6** — Fan-in always "true": single request → single response → complete.
- **R7** — Response write-back covers 4 distinct offer containers — all must be covered.

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| No error guard on response — empty response silently no-ops | [MEDIUM] | Add explicit logging when no SOC indicator data returned |
| GoldenDB routing is string equality — missing field silently takes default path | [LOW] | Document GoldenDB as required configuration; add warning when absent |
| Loyalty uses `startsWith("LY")` — any LY-prefix value triggers loyalty logic | [LOW] | Verify "LY" prefix is a stable business convention |
| Other SOC property getByExtId update — null extId lookup silently skipped | [LOW] | Add null guard logging on getByExtId failures |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
