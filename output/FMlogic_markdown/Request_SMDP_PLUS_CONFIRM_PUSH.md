# Request_SMDP_PLUS_CONFIRM_PUSH

> Per-subscriber eSIM Confirm Order request to SM-DP+. Second of two SM-DP+ push operations — confirms the eSIM profile download. Payload includes ICCID+Luhn, releaseFlag="true", EID, 4-way matchingId selection, and smdsAddress. PROJ=BULKESIM activates NONTAG_MATCHINGID path. Response RF writes matchingId back to subscriber PMATCHID ResourceInfo.

**Backend:** SM-DP+ | **Pattern:** Per-Subscriber Dispatch | **Priority:** 5 | **ForwardChain:** true

---

## §1 — Overview & Purpose

Sends an eSIM **Confirm Order Request** to the SM-DP+ server for each eSIM subscriber (SIM_TYPE="B"). This is the second of two SM-DP+ push operations.

Differences from DOWNLOAD_PUSH:
- Adds `releaseFlag="true"` (static)
- Adds 4-way `matchingId` selection (PMATCHID/NEW_PMATCHID/NONTAG_MATCHINGID/space)
- Adds `smdsAddress` (SM-DS address)
- Passes `$projValue` to XSLT for BULKESIM branch

> **[HIGH] Response RF — PMATCHID copy-paste bug:** In `Response_SMDP_PLUS_CONFIRM_PUSH.rulefunction`, when updating an existing PMATCHID ResourceInfo, the code assigns literal string `"matchingId"` instead of the variable `matchingId` (lines 44 and 80). This silently corrupts PMATCHID for any subscriber that already has one.

> **[MEDIUM] COU eid unconditional emission:** In the COU XSLT `otherwise` branch for eid, there is no inner `xsl:if` guard — emits `<eid>` unconditionally even when `NEW_EID(Source=FE)` is absent. POU variant has the correct guard.

> **[LOW] "SMDP_COMFIRMED" typo:** SubscriberExtendedInfo Name is "SMDP_COMFIRMED" (missing "N") instead of "SMDP_CONFIRMED".

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_SMDP_PLUS_CONFIRM_PUSH` |
| Priority | 5 |
| ForwardChain | true |
| Rule File | `OMXFM/Request/Request_SMDP_PLUS_CONFIRM_PUSH.rule` |
| Response Rulefunction | `Response_SMDP_PLUS_CONFIRM_PUSH.rulefunction` |
| Backend System | SM-DP+ (eSIM Remote SIM Provisioning Server) |
| Dispatch Pattern | Per-subscriber (POU + COU), one request per subscriber |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context; subscriber ICCID/EID/MatchingId data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | RequestCount, Response[], PreExecCheck, ActivityParameters |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "SMDP_PLUS_CONFIRM_PUSH"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SMDP_PLUS_CONFIRM_PUSH"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow Diagram

1. Compute `isActResub`
2. Read PROJ parameter via `GetActivityParameterValueFromKey(activity, "PROJ")`
3. Loop POU subscribers: check `reqSuccess` (skip if already CompletionStatus=2)
4. Evaluate PreExecCheck per subscriber via `GetXMLForSubscriber`
5. If passes: create and send `SMDP_PLUS_CONFIRM` request event via XSLT (with `$projValue`)
6. Set `isSkipped=false`; increment `RequestCount` (if not resubmit)
7. Emit audit logger event
8. Repeat steps 3–7 for COU subscribers (uses `GetXMLForSubscriberInChildOU`)
9. After loops: if `!isSkipped` → Status="1" + SendDataToDB; else SkipActivity("4")

---

## §6 — Rule Action (THEN)

### §6.1 PROJ Parameter Read

```java
String projValue = GetActivityParameterValueFromKey(orderCurrentActivity, "PROJ");
```

Note: `GetActivityParameterValueFromKey` (differs from `GetActivityParamValueFromKey` used in OMX_CAL_CHK_SUM_SUB_LEVEL). Result is passed as XSLT param `$projValue`.

### §6.2 matchingId Selection Logic (4-way priority)

| Priority | Condition | Source |
|----------|-----------|--------|
| 1st | `exists(ResourceInfo[PMATCHID, Source=FE])` AND not starting "NONE_" | `ResourceInfo[PMATCHID, Source=FE].ValuesArray` |
| 2nd | `exists(ResourceInfo[NEW_PMATCHID])` AND not starting "NONE_" | `ResourceInfo[NEW_PMATCHID].ValuesArray` |
| 3rd | `$projValue = "BULKESIM"` | `$orderRequest/OrderData/ExtendedInfo[NONTAG_MATCHINGID]/Value` |
| 4th (otherwise) | Fallback | `" "` (space — static, always emits) |

### §6.3 EID Selection Logic (3-way priority)

| Priority | Condition | POU | COU |
|----------|-----------|-----|-----|
| 1st | `exists(PEID, Source=FE)` AND not "NONE-" | ✓ xsl:if guard | ✓ xsl:if guard |
| 2nd | `exists(NEW_PEID)` | ✓ conditional | ✓ conditional |
| 3rd (otherwise) | Fallback NEW_EID(Source=FE) | ✓ xsl:if guard | [MEDIUM BUG] no guard — emits unconditionally |

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Used in `PREPAID_PREACTIVATION` step 13 (conditional: SIM_TYPE="B"). Param `PROJ=BULKESIM` activates NONTAG_MATCHINGID path. Requires preceding SM-DP+ DOWNLOAD step.

### §8.2 ESB / JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.SMDP_PLUS_CONFIRM` | Confirm eSIM profile download |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.SMDP_PLUS_CONFIRM` | SM-DP+ confirm response |

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | SM-DP+ (SGP.22 RSP standard) |
| Operation | ConfirmOrder (ES2+ API) |
| functionRequesterIdentifier | "1.3.6.1.4.1.30378" (static OID) |
| releaseFlag | "true" (static — always releases the profile) |

### §8.5 ExtendedInfo Fields Required

| Name | Required/Optional | Purpose |
|------|------------------|---------|
| `ICC_ID_CHG_SUM` | Required | ICCID+Luhn for SM-DP+ |
| `VENDOR` | Optional | eSIM vendor identifier |
| `smdsAddress` | Optional | SM-DS (Discovery Server) address |
| `NONTAG_MATCHINGID` | Optional (BULKESIM only) | Matching ID for BULKESIM flow |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| XSLT Param | Value |
|-----------|-------|
| `$orderRequest` | orderRequest concept |
| `$pSubRefId` / `$cSubRefId` | POU / COU subscriber RefId |
| `$psub` / `$csub` | POU / COU subscriber concept |
| `$projValue` | From GetActivityParameterValueFromKey(…,"PROJ") |

### §9.4 Payload Root Element

| Element | Source / Value | Condition |
|---------|----------------|-----------|
| `ConfirmOrderRequest/header/functionRequesterIdentifier` | "1.3.6.1.4.1.30378" (static) | Always |
| `ConfirmOrderRequest/header/functionCallIdentifier` | `$orderRequest/OrderData/OMXTrackingId` | if exists |
| `ConfirmOrderRequest/iccid` | `concat(ICC_ID_CHG_SUM/Value, "F")` | Always |
| `ConfirmOrderRequest/releaseFlag` | "true" (static) | Always |
| `ConfirmOrderRequest/eid` | 3-way: PEID(FE,not-NONE-) → NEW_PEID → NEW_EID(FE) | Conditional (COU bug) |
| `ConfirmOrderRequest/matchingId` | 4-way (see §6.2) | Always (space fallback) |
| `ConfirmOrderRequest/vendor` | `ExtendedInfo[VENDOR]/Value` | if exists |
| `ConfirmOrderRequest/smdsAddress` | `ExtendedInfo[smdsAddress]/Value` | if exists |

### §9.7 Generated XML Example

```xml
<event>
  <JMSCorrelationID>OMX-TRK-001</JMSCorrelationID>
  <RefID>SUB-REF-001</RefID>
  <payload>
    <ConfirmOrderRequest>
      <header>
        <functionRequesterIdentifier>1.3.6.1.4.1.30378</functionRequesterIdentifier>
        <functionCallIdentifier>OMX-TRK-001</functionCallIdentifier>
      </header>
      <iccid>89660720000012345678F</iccid>
      <releaseFlag>true</releaseFlag>
      <eid>89049032001234567890123456789012</eid>
      <matchingId>1$SM-DP+ADDR$MATCHING-ID-001</matchingId>
      <vendor>Giesecke</vendor>
      <smdsAddress>lpa.example.com</smdsAddress>
    </ConfirmOrderRequest>
  </payload>
</event>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority / JMSCorrelationID / OrderID / RefID / ...    [Same as DOWNLOAD_PUSH]
    └── payload
        └── ConfirmOrderRequest                                     [Always]
            ├── header/functionRequesterIdentifier  "1.3.6.1.4.1.30378"  [Always/Static]
            ├── header/functionCallIdentifier  ← OMXTrackingId     [Conditional]
            ├── iccid  ← concat(ICC_ID_CHG_SUM/Value, "F")          [Always]
            ├── releaseFlag  "true"                                  [Always/Static]
            ├── eid  ← 3-way: PEID(FE,not NONE-) → NEW_PEID → NEW_EID
            │          POU: guarded / COU: [MEDIUM BUG] unguarded   [Conditional]
            ├── matchingId  ← 4-way: PMATCHID(FE,not-NONE_) →
            │          NEW_PMATCHID(not-NONE_) → NONTAG(BULKESIM) → " "  [Always]
            ├── vendor ← ExtendedInfo[VENDOR]/Value                  [Conditional]
            └── smdsAddress ← ExtendedInfo[smdsAddress]/Value        [Conditional]
```

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| Guard | None — always logged when request dispatched |
| PROCESS_ID | `concat(pid, "_REQ")` |
| OPERATION_NAME | "SMDP_PLUS_CONFIRM_PUSH" |
| AUDIT_TRACE | "Request Sent for SMDP_PLUS_CONFIRM_PUSH" ✓ |

---

## §12 — Activity Status Management

| Condition | Action |
|-----------|--------|
| At least one request dispatched | Status="1" + SendDataToDB |
| All subscribers skipped | SkipActivity("4") |
| Exception | HandleActivityException(…, "") |

---

## §15 — Function Dependency Tree

```text
Request_SMDP_PLUS_CONFIRM_PUSH.rule
├── GetActivityParameterValueFromKey(orderCurrentActivity, "PROJ")
├── [POU loop]
│   ├── [reqSuccess check on Response[]]
│   ├── GetXMLForSubscriber(orderRequest, pSubRefId)
│   ├── XPath.execute(chkXPath, sXML, ns)               [PreExecCheck]
│   ├── Event.createEvent(XSLT → SMDP_PLUS_CONFIRM)     [projValue passed]
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   └── Event.Ext.sendEventImmediate(Logger audit)
├── [COU loop — same, uses GetXMLForSubscriberInChildOU]
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Send ConfirmOrderRequest with ICCID+checksum+"F", releaseFlag="true", eid, matchingId, vendor, smdsAddress |
| R2 | matchingId 4-way: PMATCHID(FE,not-NONE_) > NEW_PMATCHID(not-NONE_) > NONTAG(BULKESIM) > " " |
| R3 | PROJ=BULKESIM activates NONTAG_MATCHINGID branch |
| R4 | Response RF writes SM-DP+ returned matchingId back to subscriber PMATCHID ResourceInfo |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Response RF PMATCHID: assigns literal "matchingId" string instead of variable | [HIGH] | Fix: `psub.ResourceInfo[rs].ValuesArray = matchingId` (remove quotes) — same fix needed on POU line 44 and COU line 80 |
| COU eid otherwise branch emits `<eid>` unconditionally | [MEDIUM] | Add `xsl:if test="$csub/ResourceInfo[ResourceName='NEW_EID' and Source='FE']/ValuesArray"` guard |
| "SMDP_COMFIRMED" typo in SubscriberExtendedInfo Name | [LOW] | Rename to "SMDP_CONFIRMED"; update all downstream lookups that use this key |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_SMDP_PLUS_CONFIRM_PUSH {
  attribute { priority = 5; forwardChain = true; }
  then {
    boolean isActResub = (...);
    String projValue = GetActivityParameterValueFromKey(orderCurrentActivity, "PROJ");
    try {
      boolean isSkipped = true;
      // POU loop
      for (int p=0; p<pOuLen; p++) {
        for (int ps=0; ps<pSubLen; ps++) {
          if (!reqSuccess) {
            if (chkRes == "true") {
              Events...SMDP_PLUS_CONFIRM reqEvent = Event.createEvent("xslt://...");
              /* XSLT: ConfirmOrderRequest with iccid=ICC_ID_CHG_SUM+"F", releaseFlag="true",
                 eid(3-way), matchingId(4-way), vendor, smdsAddress
                 projValue passed as $projValue; COU eid otherwise MISSING xsl:if [MEDIUM BUG]
                 See §9.8 */
              Event.Ext.sendEventImmediate(reqEvent);
              isSkipped = false;
              if (!isActResub) orderCurrentActivity.RequestCount++;
              Event.Ext.sendEventImmediate(logEvent);
            }
          }
        }
      }
      // COU loop — same
      if (!isSkipped) {
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
    } catch (Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

Creates `ResponseBase` from SM-DP+ confirm response. If BULKESIM: extracts `matchingId` from `ConfirmOrderResponse/matchingId` and writes back to subscriber PMATCHID ResourceInfo. Creates `SMDP_COMFIRMED` (sic) SubscriberExtendedInfo. Fan-in is success-code-based.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context; subscriber PMATCHID written back |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SMDP_PLUS_CONFIRM` | SM-DP+ confirm response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking |

### §19.3 ResponseBase Concept Construction

Type: `Concepts.FM.Base.ResponseBase` (generic)

```text
createObject
└── object  extId=OMXUtils:generateTrackingID()             [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode     [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg      [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId       ← $eventResponse/RefID            [Conditional]
```

### §19.4 Post-Processing — PMATCHID Writeback (BULKESIM)

| Step | Logic |
|------|-------|
| 1. Check PROJ | If BULKESIM → enter writeback loop |
| 2. Match subscriber | Find POU/COU subscriber by `RefID == response.ReferenceId` |
| 3. Extract matchingId | `eventResponse/payload/ConfirmOrderResponse/matchingId` |
| 4a. PMATCHID absent | Create new `ResourceInfo` concept; Name="PMATCHID", Source="BE", ValuesArray=matchingId |
| 4b. PMATCHID exists | Set `psub.ResourceInfo[rs].ValuesArray = "matchingId"` **[HIGH BUG]** — literal string; fix: remove quotes |
| 5. SMDP_COMFIRMED | Create `SubscriberExtendedInfo` Name="SMDP_COMFIRMED" (typo), Value="Y" |

### §19.5 Response Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Return "true" | All dispatched requests received successful ResponseCode ending "000" |

### §19.6 Response Audit Logging

| Field | Value |
|-------|-------|
| Guard | None — always logs |
| PROCESS_ID | `concat(pid, "_RES")` |
| OPERATION_NAME | "SMDP_PLUS_CONFIRM_PUSH" ✓ |
| AUDIT_TRACE | "Response received for SMDP_PLUS_CONFIRM_PUSH" ✓ |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
