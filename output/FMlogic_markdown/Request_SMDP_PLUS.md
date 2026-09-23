# Request_SMDP_PLUS

> TIBCO BusinessEvents FM Logic — SM-DP+ eSIM Profile Download (Per-Offer Parallel Fan-out)

**Author:** SathidP-PC | **Priority:** 5 | **Forward Chain:** true | **Target:** SM-DP+ (eSIM Profile Server) | **Pattern:** Per-Offer Fan-out — Two XSLT Variants

---

## §1 — Overview & Purpose

This rule initiates eSIM profile download by dispatching `DownloadOrderRequest` events to SM-DP+ (the eSIM Profile Server — GSMA SGP.22). It processes subscriber offers at the offer level — filtering to eSIM offers (serviceType="80") by default — and dispatches one or more `SMDP_PLUS_DOWNLOAD` JMS events depending on the PROJ parameter and offer configuration.

> **Two distinct dispatch branches:** Branch A (PROJ=RIO_SWAP or PROJ=ESIM) dispatches one event per subscriber and then breaks the offer loop. Branch B (standard) iterates all qualifying offers. The ICCID, EID, and VENDOR field sources differ significantly between branches. Parameters with value **"BLANK"** suppress the corresponding payload element entirely (Branch B only).

> **Fan-in difference:** Success check uses `tib:right(tib:trim(ResponseCode), 2) = "00"` (last **2** chars) rather than the standard "000" (3 chars) used everywhere else in this process.

| Item | Value |
|------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_SMDP_PLUS` |
| Author | SathidP-PC |
| JMS Event Dispatched | `Events.OMConsumers.OMXFM.Request.SMDP_PLUS_DOWNLOAD` |
| Payload Schema | `DownloadOrderRequest` (SM-DP+ GSMA SGP.22) |
| Response Concept | `Concepts.FM.Response.SMDP_PLUS_DOWNLOAD` |
| Response Event | `Events.OMConsumers.OMXFM.Response.SMDP_PLUS_DOWNLOAD` |
| Target System | SM-DP+ (eSIM Profile Server) |
| Parameters Used | ICCID, EID, VENDOR, PROJ (read twice — also as swapValue), ORDER |
| Dispatch Method | `Event.Ext.sendEventImmediate()` — parallel fan-out per offer/subscriber |
| Fan-In [UNIQUE] | `count(Response[tib:right(tib:trim(ResponseCode), 2) = "00"]) == RequestCount` — last **2** chars |
| Credentials in payload | YES — UserName and PassWord from orderRequest |

---

## §2 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Current process step match |
| 2 | `orderCurrentActivity.ActivityID == "SMDP_PLUS"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SMDP_PLUS"` | Process flow confirmation |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fire once |

---

## §3 — Activity Parameters

> **PROJ is read twice** into `paramValue` and `swapValue` (same key "PROJ"). Only `paramValue` is used. `swapValue` is a dead read.

| Parameter | Variable | Effect |
|-----------|----------|--------|
| ICCID | `iccIdValue` | Override ICCID. "BLANK" → suppress iccid element (Branch B only). |
| EID | `eIdValue` | Override EID. "BLANK" → suppress eid element (Branch B only). |
| VENDOR | `vendorValue` | Override vendor name. "BLANK" → suppress vendor element (Branch B only). |
| PROJ | `paramValue` (active) | "RIO_SWAP" or "ESIM" → Branch A; else Branch B. |
| PROJ | `swapValue` [DEAD READ] | Same key "PROJ" — value never used. |
| ORDER | `orderValue` | "RESUME" → bypass eSIM serviceType="80" filter. |

---

## §4 — eSIM Offer Pre-Filter

This FM iterates at the **offer level** (SubscriberOffers). Each offer is pre-filtered:

```text
if ((serviceType == null || serviceType == "80") AND (orderValue != "RESUME" AND paramValue != "ESIM")) → continue (skip offer)
```

Skip non-eSIM offers unless order is in RESUME mode or PROJ=ESIM. This makes SMDP_PLUS an eSIM-exclusive FM in normal execution.

Additionally, `ExtendedInfo[Name="FE_OR_CCBS"]/Value` from the offer is read as a filter flag passed to the PreExecCheck XML helper.

---

## §5 — Dispatch Branch Decision

| Branch | Trigger | Scope | Loop Behavior |
|--------|---------|-------|---------------|
| **Branch A** (RIO_SWAP/ESIM) | `paramValue == "RIO_SWAP" OR paramValue == "ESIM"` | Per subscriber (1 event); subscriber-level ICCID/EID/VENDOR | `break` after first event |
| **Branch B** (Standard) | All other PROJ values | Per offer (N events); offer-level ICCID/VENDOR | Continues — can send multiple events per subscriber |

### §5.1 Branch A — RIO_SWAP / ESIM Logic

Additional gate: `count(subscriber.ResourceInfo[ResourceName="OLD_EID" and Source="FE"]) > 0 OR paramValue="ESIM"`

**EID working memory mutation** (before dispatch): If subscriber has no EID resource and NEW_EID exists → create EID ResourceInfo with Source="FE" → append to subscriber.

> **COU Branch A Bug (line 174):** The EID lookup reads `$subscriberPou/ResourceInfo[ResourceName='NEW_EID']` inside the COU loop where the correct variable is `$subscriber` (the COU subscriber). COU Branch A inherits the parent OU subscriber's NEW_EID instead of its own.

### §5.2 Branch B — Standard Logic

- No OLD_EID gate
- No EID working memory mutation
- "BLANK" suppression for all three fields
- VENDOR and ICCID sourced from offer-level (`currSubOffer.ExtendedInfo`)
- No `break` — all offers are processed

---

## §6 — ICCID / EID / VENDOR Source Matrix

### §6.1 ICCID Source

| Branch | Condition | Source |
|--------|-----------|--------|
| Branch A | iccIdValue has value | iccIdValue (param override) |
| Branch A (fallback) | No param | `concat(subscriber.ExtendedInfo[Name="ICC_ID_CHG_SUM"]/Value, "F")` |
| Branch B | iccIdValue == "BLANK" | Omit iccid element entirely |
| Branch B | iccIdValue has value (not "BLANK") | iccIdValue (param override) |
| Branch B (fallback) | No param / not "BLANK" | `concat(currSubOffer.ExtendedInfo[Name="ICC_ID_CHG_SUM"]/Value, "F")` — offer-level |

### §6.2 EID Source

| Branch | Priority | Source |
|--------|----------|--------|
| Branch A — 1st | param override | eIdValue |
| Branch A — 2nd | PEID(FE) not starting with "NONE-" | `ResourceInfo[ResourceName="PEID" and Source="FE"]/ValuesArray` |
| Branch A — 3rd | NEW_PEID resource | `ResourceInfo[ResourceName="NEW_PEID"]/ValuesArray` |
| Branch A — 4th | NEW_EID on any POU subscriber | `orderRequest/.../ResourceInfo[ResourceName="NEW_EID" and Source="FE"]/ValuesArray` |
| Branch B | eIdValue == "BLANK" | Omit eid element |
| Branch B — 1st | param override | eIdValue |
| Branch B — 2nd | PEID(FE) not starts-with upper-case "NONE-" | `ResourceInfo[ResourceName="PEID" and Source="FE"]/ValuesArray` |
| Branch B — 3rd | EID(FE) | `ResourceInfo[ResourceName="EID" and Source="FE"]/ValuesArray` |

### §6.3 VENDOR Source

| Branch | Condition | Source |
|--------|-----------|--------|
| Branch A | vendorValue has value | vendorValue |
| Branch A (fallback) | No param | `subscriber.ExtendedInfo[Name="VENDOR"]/Value` (subscriber-level) |
| Branch B | vendorValue == "BLANK" | Omit vendor element |
| Branch B | vendorValue has value | vendorValue |
| Branch B (fallback) | No param / not "BLANK" | `currSubOffer.ExtendedInfo[Name="VENDOR"]/Value` (offer-level) |

---

## §7 — Payload Build (XSLT — DownloadOrderRequest)

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                    [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId          [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                 [Conditional]
    ├── RefID                ← $subRefId (subscriber.RefId)                   [Always]
    ├── UserName             ← $orderRequest/OrderData/User                   [Conditional — CREDENTIAL]
    ├── PassWord             ← $orderRequest/OrderData/Password               [Conditional — CREDENTIAL]
    ├── OrderType            ← $orderRequest/OrderData/OrderType              [Conditional]
    └── payload
        └── DownloadOrderRequest
            ├── header
            │   ├── functionRequesterIdentifier  ← "1.3.6.1.4.1.30378"      [Always, static OID]
            │   └── functionCallIdentifier       ← $orderRequest/OrderData/OMXTrackingId  [Conditional]
            ├── iccid   ← see §6.1 matrix                                     [Conditional — omitted if BLANK]
            ├── eid     ← see §6.2 matrix                                     [Conditional — omitted if BLANK or NONE-]
            └── vendor  ← see §6.3 matrix                                     [Conditional — omitted if BLANK]
```

> `functionRequesterIdentifier = "1.3.6.1.4.1.30378"` is a hardcoded OID identifying the requesting entity to the SM-DP+ server (GSMA SGP.22 protocol requirement).

---

## §8 — Working Memory Mutation (Branch A Only)

| Gate | Action | extId |
|------|--------|-------|
| No existing EID resource AND NEW_EID value not blank | Create `ResourceInfo{ResourceName="EID", ValuesArray=$eid, Source="FE"}` | `concat(subscriber/@extId, "EID", $eid)` |

---

## §9 — Execution Flow

1. Read all parameters: ICCID, EID, VENDOR, PROJ (×2 — dead duplicate), ORDER
2. Read LogicalDate concept [dead — never used in payload]
3. Initialize dead variables: requestedDate, requestedBy, requestedByUser, futureType
4. **Loop POU Subscribers → Loop POU Subscriber Offers:**
   a. ServiceType + ORDER/PROJ pre-filter (skip non-eSIM unless RESUME/ESIM)
   b. Read FE_OR_CCBS filter from offer
   c. Execute PreExecCheck if present
   d. reqSuccess check: `Response[ReferenceId == SubscriberId AND CompletionStatus==2]` (uses SubscriberId, not RefId)
   e. If PROJ=RIO_SWAP or ESIM → Branch A: OLD_EID/ESIM gate → EID mutation → send event → break
   f. Else → Branch B: send offer-level event (no break)
5. **Loop COU Subscribers (same offer-level logic)**
6. If !isSkipped: `GetActivityStatusString("1", false)` + `SendDataToDB()`
7. Else: `SkipActivity("4")`
8. catch: status reset (NetworkStatus=10, OrderStatus=1, ProfileStatus=1) + `HandleActivityException()` + restore

> **reqSuccess uses SubscriberId, not RefId:** `Response[ReferenceId == subscriberPou.SubscriberId]`. The outbound RefID carries `subscriber.RefId`, but the response match is by `SubscriberId`. Inconsistent with most other FMs.

---

## §10 — Dead Variables

| Variable / Code | Set | Used | Note |
|-----------------|-----|------|------|
| `logicalDate` | Line 43-47: from LogicalDate concept | Never used in XSLT | Future-date scheduling feature (unused) |
| `requestedDate` | Line 49: `DateTime.now()` | Never used | Dead |
| `requestedBy` | Line 50: `"OMX"` | Never used | Dead |
| `requestedByUser` | Line 51: `orderRequest.OrderData.Channel` | Never used | Dead |
| `futureType` | Line 52: `"NXTOFR"` | Never used | Dead |
| `swapValue` | Line 37: `GetActivityParamValueFromKey("PROJ")` | Never used | Duplicate of paramValue |

---

## §11 — System & Integration Dependencies

| Direction | Event | Purpose |
|-----------|-------|---------|
| [OUTBOUND] | `SMDP_PLUS_DOWNLOAD` | eSIM profile download request to SM-DP+ |
| [OUTBOUND] | `Logger` | Audit log for each dispatched event |

---

## §12 — Audit Logging

| Field | Value |
|-------|-------|
| OPERATION_NAME | `"SMDP_PLUS"` (static) |
| AUDIT_TRACE | `"Request Sent for SMDP_PLUS"` (static) |
| payload | `copy-of $reqEvent` gated on `WritePayload=true` |
| Send method | `Event.Ext.sendEventImmediate()` |

---

## §13 — Activity Status Management

| State | Trigger | Call |
|-------|---------|------|
| [ACTIVE] | At least one event dispatched | `GetActivityStatusString("1", false)` + `SendDataToDB()` |
| [SKIPPED] | No qualifying eSIM offer found | `SkipActivity("4")` |

> **Exception handler does status reset:** Temporarily sets NetworkStatus=GetOrderStatusString(10), then restores original after HandleActivityException. Same pattern used in response "false" path.

---

## §15 — Function Dependency Tree

```text
Request_SMDP_PLUS (BE rule)
├── GetActivityParamValueFromKey(×5) — ICCID, EID, VENDOR, PROJ (×2), ORDER
├── Instance.getByExtIdByUri("LogicalDate", ...)  [dead — value unused]
│
├── [Loop POU Subscribers → Loop Offers]
│   ├── XPath.evalAsString(FE_OR_CCBS from offer)
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo()
│   ├── XPath.execute(PreExecCheck)
│   ├── reqSuccess: Response[ReferenceId==SubscriberId AND CompletionStatus==2]
│   │
│   ├── [Branch A: RIO_SWAP/ESIM]
│   │   ├── XPath.evalAsBoolean(OLD_EID/ESIM gate)
│   │   ├── XPath.evalAsBoolean(no-EID check)
│   │   ├── XPath.evalAsString(NEW_EID lookup)
│   │   ├── Instance.createInstance(EID ResourceInfo)  [working memory mutation]
│   │   ├── Event.createEvent("SMDP_PLUS_DOWNLOAD", subscriber-scoped XSLT)
│   │   ├── Event.Ext.sendEventImmediate(reqEvent)
│   │   ├── RequestCount++
│   │   ├── Event.Ext.sendEventImmediate(audit Logger)
│   │   └── break
│   │
│   └── [Branch B: Standard]
│       ├── Event.createEvent("SMDP_PLUS_DOWNLOAD", currSubOffer-scoped XSLT)
│       ├── Event.Ext.sendEventImmediate(reqEvent)
│       ├── RequestCount++
│       └── Event.Ext.sendEventImmediate(audit Logger)
│
├── [Loop COU Subscribers → Loop Offers] — same; COU Branch A has NEW_EID bug
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(...)
├── GetOrderStatusString(N)   [exception path]
└── HandleActivityException(...)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Only process eSIM offers (serviceType="80") unless ORDER=RESUME or PROJ=ESIM
- **R2** — PROJ=RIO_SWAP/ESIM: one event per subscriber (break), subscriber-level ICCID/EID/VENDOR
- **R3** — Standard PROJ: one event per qualifying offer, offer-level ICCID/VENDOR
- **R4** — "BLANK" parameter value suppresses the corresponding payload element (Branch B only)
- **R5** — EID precedence: param → PEID(FE, not NONE-) → NEW_PEID (Branch A) / EID(FE) (Branch B)
- **R6** — ICCID fallback: `ICC_ID_CHG_SUM + "F"` suffix (Luhn checksum from OMX_CAL_CHK_SUM_SUB_LEVEL)
- **R7** — Fan-in: last **2** chars "00" (NOT 3-char "000")
- **R8** — Credentials (UserName/PassWord) in every SMDP_PLUS_DOWNLOAD payload
- **R9** — EID working memory mutation (Branch A): create EID ResourceInfo from NEW_EID if absent

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Fan-in uses "00" (2 chars) not "000" — a migrated system expecting "000" will never complete | [CRITICAL] | Use `tib:right(tib:trim(ResponseCode), 2) = "00"` specifically for SMDP_PLUS |
| COU Branch A reads $subscriberPou NEW_EID instead of $subscriber NEW_EID — COU gets wrong EID | [HIGH] | Fix in migration: use COU subscriber variable for EID lookup |
| reqSuccess matches by SubscriberId (not RefId) — inconsistent with other FMs | [MEDIUM] | Verify SM-DP+ returns SubscriberId as ReferenceId; document the match key |
| "BLANK" parameter suppression undocumented — null vs "BLANK" has very different behavior | [MEDIUM] | Document "BLANK" as a special sentinel value in the parameter catalog |
| Credentials in JMS payload — UserName/PassWord transmitted over JMS | [MEDIUM] | Ensure JMS channel is secured (TLS); migrate to secret manager if possible |
| Dead variables (6 unused) clutter rule | [LOW] | Remove all dead code in migration |

---

## §19 — Response Message Rule

### §19.1 Overview

`Response_SMDP_PLUS.rulefunction` (42 lines): One of the simplest response handlers — creates a `SMDP_PLUS_DOWNLOAD` concept with only ResponseCode, ResponseMessage, and CompletionStatus. No ReferenceId, no subscriber-level enrichment.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Audit logging and status management |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SMDP_PLUS_DOWNLOAD` | SM-DP+ response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; fan-in check |

### §19.3 ResponseBase Concept Fields

```text
createObject (SMDP_PLUS_DOWNLOAD)
└── object
    ├── @extId          ← OMXUtils:generateTrackingID()        [Always]
    ├── ResponseCode    ← $eventResponse/ResponseCode          [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg           [Conditional]
    └── CompletionStatus← $eventResponse/CompletionStatus      [Conditional]
```

**Not mapped:** ReferenceId (absent — fan-in relies only on ResponseCode). No SearchKey, no enrichment.

### §19.4 Fan-In Completion [UNIQUE]

| Item | Value |
|------|-------|
| XPath expression | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 2) = "00"])` |
| Character check | Last **2** chars = "00" (NOT "000") |
| Completion condition | `currActivity.RequestCount == successResponseCount` |
| Returns "true" | All SM-DP+ download requests succeeded |
| Returns "false" | Still waiting; calls `SendDataToDB()` with temporary NetworkStatus=GetOrderStatusString(3) |

### §19.5 Response Audit

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(System.nanoTime(), "_RES")` |
| OPERATION_NAME | `"SMDP_PLUS"` (static) |
| AUDIT_TRACE | `"Response received for SMDP_PLUS"` (static) |
| payload gate | `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
