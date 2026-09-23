# Request_SMDP_PLUS_CONFIRM

> TIBCO BusinessEvents FM Logic — SM-DP+ eSIM Profile Download Confirmation (Per-Offer Fan-out)

**Author:** SathidP-PC | **Priority:** 5 | **Forward Chain:** true | **Target:** SM-DP+ Confirm Phase | **Fan-in:** standard "000" (3 chars)

---

## §1 — Overview & Purpose

This rule sends a `ConfirmOrderRequest` to SM-DP+ to confirm a previously initiated eSIM profile download (step 2 of the SMDP+ sequence). Structurally identical to SMDP_PLUS with five key payload differences: `ConfirmOrderRequest` schema, mandatory `releaseFlag="true"`, a `matchingId` field from PMATCHID resources, optional `smdsAddress`, and no "BLANK" suppression.

> **Relationship to SMDP_PLUS:** Same author, same two-branch dispatch structure, same eSIM offer filter, same FE_OR_CCBS pattern, same credentials. The COU Branch A variable bug from SMDP_PLUS is **fixed** here. Fan-in reverts to standard **"000"** (3-char) check.

| Item | Value |
|------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_SMDP_PLUS_CONFIRM` |
| Author | SathidP-PC |
| JMS Event Dispatched | `Events.OMConsumers.OMXFM.Request.SMDP_PLUS_CONFIRM` |
| Payload Schema | `ConfirmOrderRequest` (SM-DP+ GSMA SGP.22 Confirm step) |
| Response Concept | `Concepts.FM.Response.SMDP_PLUS_CONFIRM` |
| Response Event | `Events.OMConsumers.OMXFM.Response.SMDP_PLUS_CONFIRM` |
| Target System | SM-DP+ (eSIM Profile Server — Confirm phase) |
| Parameters Used | ICCID, EID, VENDOR, MATCHING (dead read), PROJ, ORDER |
| Fan-In | `count(Response[tib:right(tib:trim(ResponseCode), 3) = "000"]) == RequestCount` |
| Credentials in payload | YES — UserName and PassWord |

---

## §2 — Key Differences from SMDP_PLUS

| Aspect | SMDP_PLUS (Download) | SMDP_PLUS_CONFIRM (Confirm) |
|--------|----------------------|-----------------------------|
| Payload root element | `DownloadOrderRequest` | `ConfirmOrderRequest` |
| releaseFlag | Absent | `"true"` — static, always emitted |
| matchingId | Absent | From PMATCHID(FE) / NEW_PMATCHID → default `" "` (space) |
| smdsAddress | Absent | Optional — `ExtendedInfo[Name="smdsAddress"]/Value` |
| "BLANK" suppression | Yes | No — no BLANK suppression in any branch |
| EID in Branch A XSLT | Not in XSLT params | Not in Branch A XSLT — resource-only fallback |
| COU Branch A variable | [BUG] reads $subscriberPou for EID | [FIXED] reads $subscriber correctly |
| MATCHING parameter | Absent | Read as matchingValue — [DEAD READ] |
| Fan-in check | `tib:right(..., 2) = "00"` (2 chars) | `tib:right(..., 3) = "000"` (3 chars — standard) |
| Response "true" path | Returns immediately | Calls `SendDataToDB()` with temp status before returning |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Current process step match |
| 2 | `orderCurrentActivity.ActivityID == "SMDP_PLUS_CONFIRM"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SMDP_PLUS_CONFIRM"` | Process flow confirmation |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fire once |

---

## §4 — Activity Parameters

| Parameter | Variable | Effect |
|-----------|----------|--------|
| ICCID | `iccIdValue` | Override ICCID; else fallback to ICC_ID_CHG_SUM+"F". No BLANK suppression. |
| EID | `eIdValue` | Override EID (Branch B only); Branch A uses resource fallback only |
| VENDOR | `vendorValue` | Override vendor; else from ExtendedInfo. No BLANK suppression. |
| MATCHING | `matchingValue` [DEAD READ] | Read but never used — matchingId comes from PMATCHID resources |
| ORDER | `orderValue` | "RESUME" → bypass eSIM serviceType="80" offer filter |
| PROJ | `paramValue` | "RIO_SWAP" or "ESIM" → Branch A; else Branch B |

Dead variables (same 5 as SMDP_PLUS): `logicalDate`, `requestedDate`, `requestedBy`, `requestedByUser`, `futureType`.

---

## §5 — Payload Build (XSLT — ConfirmOrderRequest)

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
        └── ConfirmOrderRequest
            ├── header
            │   ├── functionRequesterIdentifier  ← "1.3.6.1.4.1.30378"      [Always, static OID]
            │   └── functionCallIdentifier       ← $orderRequest/OrderData/OMXTrackingId  [Conditional]
            ├── iccid       ← iccIdValue or concat(ICC_ID_CHG_SUM,"F")       [Always — no BLANK suppression]
            ├── releaseFlag ← "true"                                          [Always, static — new in CONFIRM]
            ├── vendor      ← vendorValue or ExtendedInfo[VENDOR]/Value       [Always — no BLANK suppression]
            ├── eid         ← see §6.1 EID matrix                             [Conditional]
            ├── matchingId  ← see §6.2 matchingId matrix                      [Always — space if not found]
            └── smdsAddress ← ExtendedInfo[Name="smdsAddress"]/Value          [Conditional — only if present]
```

---

## §6 — Field Source Matrix

### §6.1 EID Source

| Branch | Priority | Source |
|--------|----------|--------|
| Branch A — 1st | PEID(FE) not starts-with upper-case "NONE-" | `ResourceInfo[ResourceName="PEID" and Source="FE"]/ValuesArray` |
| Branch A — 2nd | NEW_PEID resource | `ResourceInfo[ResourceName="NEW_PEID"]/ValuesArray` |
| Branch A — 3rd (fallback) | NEW_EID on any POU subscriber | `orderRequest/.../ResourceInfo[ResourceName="NEW_EID" and Source="FE"]/ValuesArray` |
| Branch B — 1st | eIdValue param | `eIdValue` |
| Branch B — 2nd | PEID(FE) not starts-with upper-case "NONE-" | `ResourceInfo[ResourceName="PEID" and Source="FE"]/ValuesArray` |
| Branch B — 3rd (fallback) | EID(FE) resource | `ResourceInfo[ResourceName="EID" and Source="FE"]/ValuesArray` |

Branch A does not accept the EID parameter — resource-only.

### §6.2 matchingId Source

| Branch | Priority | Source | Exclusion |
|--------|----------|--------|-----------|
| Branch A POU — 1st | PMATCHID(FE) | `ResourceInfo[ResourceName="PMATCHID" and Source="FE"]/ValuesArray` | Not starts-with `"NONE_"` (underscore) |
| Branch A POU — 2nd | NEW_PMATCHID | `ResourceInfo[ResourceName="NEW_PMATCHID"]/ValuesArray` | Not starts-with `"NONE_"` |
| Branch A POU — default | None found | `" "` (single space) | — |
| Branch B — 1st | PMATCHID(FE) | Same as above | Not starts-with `"NONE_"` |
| Branch B — default | None found | `" "` (space) | Branch B does NOT check NEW_PMATCHID |

> **NONE_ vs NONE-:** matchingId exclusion uses `starts-with(..., "NONE_")` (underscore). EID exclusion uses `starts-with(upper-case(...), "NONE-")` (dash, case-insensitive). Different sentinel prefixes.

---

## §7 — Dispatch Branch Decision

| Branch | Trigger | Loop Behavior | COU Variable |
|--------|---------|---------------|-------------|
| Branch A (RIO_SWAP/ESIM) | `paramValue == "RIO_SWAP" OR "ESIM"` + OLD_EID/ESIM gate | `break` after first event per subscriber | [FIXED] uses `$subscriber` correctly |
| Branch B (Standard) | All other PROJ | Iterates all qualifying offers | N/A |

> **COU Branch A fix:** SMDP_PLUS incorrectly read `$subscriberPou/ResourceInfo[NEW_EID]` in the COU loop. SMDP_PLUS_CONFIRM correctly uses `$subscriber` throughout COU Branch A. No EID working memory mutation (creation) in CONFIRM — that was SMDP_PLUS only.

---

## §8 — Dead Variables

| Variable | Set | Used | Note |
|----------|-----|------|------|
| `matchingValue` | Line 34: GetActivityParamValueFromKey "MATCHING" | Never used | matchingId comes from PMATCHID resources |
| `logicalDate` | Lines 39-43 | Never used | Future-date scheduling vestigial |
| `requestedDate` | Line 46 | Never used | Dead |
| `requestedBy` | Line 47 | Never used | Dead |
| `requestedByUser` | Line 48 | Never used | Dead |
| `futureType` | Line 49 | Never used | Dead |

---

## §15 — Function Dependency Tree

```text
Request_SMDP_PLUS_CONFIRM (BE rule)
├── GetActivityParamValueFromKey(×6) — ICCID, EID, VENDOR, MATCHING(dead), ORDER, PROJ
│
├── [Loop POU Subscribers → Loop Offers]
│   ├── XPath.evalAsString(FE_OR_CCBS from offer)
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo()
│   ├── XPath.execute(PreExecCheck)
│   ├── reqSuccess: Response[ReferenceId==SubscriberId AND CompletionStatus==2]
│   ├── [Branch A: RIO_SWAP/ESIM]
│   │   ├── XPath.evalAsBoolean(OLD_EID/ESIM gate)
│   │   ├── Event.createEvent("SMDP_PLUS_CONFIRM", subscriberPou-scoped XSLT)
│   │   │   └── ConfirmOrderRequest[iccid, releaseFlag, vendor, eid(resource), matchingId, smdsAddress]
│   │   ├── Event.Ext.sendEventImmediate(reqEvent)
│   │   ├── RequestCount++
│   │   ├── Event.Ext.sendEventImmediate(audit Logger)
│   │   └── break
│   └── [Branch B: Standard]
│       ├── Event.createEvent("SMDP_PLUS_CONFIRM", currSubOffer-scoped XSLT)
│       │   └── ConfirmOrderRequest[iccid, releaseFlag, vendor, eid(param/PEID/EID), matchingId, smdsAddress]
│       ├── Event.Ext.sendEventImmediate(reqEvent)
│       ├── RequestCount++
│       └── Event.Ext.sendEventImmediate(audit Logger)
│
├── [Loop COU Subscribers → Loop Offers]
│   └── Same branches — COU Branch A correctly uses $subscriber (FIXED)
│
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(...)
└── HandleActivityException(...)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Only process eSIM offers (serviceType="80") unless ORDER=RESUME or PROJ=ESIM
- **R2** — PROJ=RIO_SWAP/ESIM: one event per subscriber (break); resource-only EID in Branch A
- **R3** — Standard PROJ: one event per qualifying offer; eIdValue → PEID → EID(FE) chain
- **R4** — `releaseFlag="true"` always emitted — confirms profile release to device
- **R5** — matchingId: PMATCHID(FE, not NONE_) → NEW_PMATCHID (Branch A) → `" "` (space)
- **R6** — smdsAddress optional — only emitted when ExtendedInfo present
- **R7** — No "BLANK" suppression — all fields emitted if value available
- **R8** — Fan-in: last **3** chars "000" (standard — unlike SMDP_PLUS "00")
- **R9** — Response TRUE path also calls `SendDataToDB()` before returning

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| MATCHING param read but silently ignored — ConfigParam "MATCHING" has no effect | [MEDIUM] | Remove dead read; document matchingId source as PMATCHID resources |
| Branch A ignores EID parameter — passing EID param for Branch A has no effect | [MEDIUM] | Document; consider adding eIdValue to Branch A XSLT for consistency |
| Branch B matchingId misses NEW_PMATCHID fallback (Branch A has it, Branch B doesn't) | [MEDIUM] | Add NEW_PMATCHID branch to Branch B matchingId XSLT |
| Credentials in JMS payload | [MEDIUM] | Secure channel; migrate to secret manager |
| Dead variables (6) | [LOW] | Remove in migration |

---

## §19 — Response Message Rule

### §19.1 Overview

`Response_SMDP_PLUS_CONFIRM.rulefunction` (52 lines): Same minimal structure as SMDP_PLUS response. Both TRUE and FALSE fan-in paths call `SendDataToDB()` with temporary status reset (TRUE path also does this, unlike SMDP_PLUS).

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Audit and status management |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SMDP_PLUS_CONFIRM` | SM-DP+ confirm response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; fan-in check |

### §19.3 ResponseBase Concept Fields

```text
createObject (SMDP_PLUS_CONFIRM)
└── object
    ├── @extId           ← OMXUtils:generateTrackingID()   [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode     [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg      [Conditional]
    └── CompletionStatus ← $eventResponse/CompletionStatus [Conditional]
```

### §19.4 Fan-In Completion

| Item | Value |
|------|-------|
| XPath expression | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Character check | Last **3** chars = "000" (standard — different from SMDP_PLUS "00") |
| Returns "true" | All confirms received; calls `SendDataToDB()` with NetworkStatus=GetOrderStatusString(10) |
| Returns "false" | Still waiting; calls `SendDataToDB()` with NetworkStatus=GetOrderStatusString(3) |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
