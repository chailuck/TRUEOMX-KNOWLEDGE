# Request_CCBS_REMOVE_RESOURCE_RANGES

> Removes resource ranges for each subscriber (POU and COU) via CCBS RemoveResourceRanges — per-subscriber dispatch with Action=REMOVE+ParameterInstanceId filter

**Priority:** 5 | **ForwardChain:** true | **Backend:** CCBS (ResourceRanges) | **Dispatch:** Per-Subscriber (POU → COU)

---

## §1 — Overview & Purpose

This rule dispatches **CCBS RemoveResourceRanges** requests for every subscriber across all Parent OUs and Child OUs. It mirrors the structure of `CCBS_ADD_RESOURCE_RANGES` but filters for REMOVE operations and requires a `ParameterInstanceId`. One key difference: credentials are emitted **unconditionally** (no IsEnableUserPass gate).

- Filters `ResourceRangeInfo` where `Action=="REMOVE" AND ParameterInstanceId.length > 0`
- Same POU/COU dual-loop structure as CCBS_ADD_RESOURCE_RANGES
- `logicalDateVal` read from LogicalDate concept but never used — dead code
- No reqSuccess check before dispatch
- No guard on removeRangeArray@length — may dispatch empty requests

> **BUG [HIGH] — Credentials always emitted:** CCBS_REMOVE_RESOURCE_RANGES XSLT emits `UserName` and `PassWord` unconditionally — no `xsl:if` guard on `IsEnableUserPass`. Credentials sent on every request regardless of configuration. Compare to CCBS_ADD_RESOURCE_RANGES which gates on IsEnableUserPass='true'.

> **BUG [HIGH] — Response RF OPERATION_NAME wrong:** The response rulefunction's Logger event has `OPERATION_NAME = "CCBS_ADD_RESOURCE_RANGES"` and `AUDIT_TRACE = "Response received for CCBS_ADD_RESOURCE_RANGES"` — both reference ADD instead of REMOVE.

> **BUG [MEDIUM] — No empty-array guard:** Dispatches even when `removeRangeArray@length == 0`.

> **AUDIT_TRACE typos:** Both POU and COU traces say "for add resourceRangeInfo" (should be "remove"); COU has "ChidOU" typo.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_REMOVE_RESOURCE_RANGES` |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS — RemoveResourceRanges |
| Dispatch pattern | Per-Subscriber (POU subscribers then COU subscribers) |
| Range filter | `ResourceRangeInfo.Action == "REMOVE" AND ParameterInstanceId.length > 0` |
| Response rulefunction | `Response_CCBS_REMOVE_RESOURCE_RANGES` |
| Fan-in mechanism | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_REMOVE_RESOURCE_RANGES"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_REMOVE_RESOURCE_RANGES"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow

1. Check isActResub → `PurgePendingRequestsBeforeResubmit` if true
2. Read LogicalDate → `logicalDateVal` (dead code — not used)
3. **POU loop**: for each POU → for each Subscriber → PreExecCheck → filter `Action=="REMOVE" AND ParameterInstanceId.length>0` → dispatch
4. **COU loop**: for each COU → for each Subscriber → PreExecCheck → same filter/dispatch
5. If `!isSkipped` → `SendFirstRequestEvent` + Status="1" + `SendDataToDB`; else `SkipActivity("4")`

---

## §6 — Key Differences from CCBS_ADD_RESOURCE_RANGES

| Aspect | ADD_RESOURCE_RANGES | REMOVE_RESOURCE_RANGES |
|--------|---------------------|------------------------|
| Range filter | `Action=="ADD"` | `Action=="REMOVE" AND ParameterInstanceId.length>0` |
| Payload root | `ns1:AddResourceRangesRequest` | `ns5:RemoveResourceRangesRequest` |
| Extra payload field | — | `ns3:ParameterInstanceId` (conditional) |
| Credential guard | Gated on IsEnableUserPass='true' | **UNCONDITIONAL — always emits** [HIGH] |
| COU event type bug | CCBS_CHANGE_RESOURCE_RANGES (wrong) | CCBS_REMOVE_RESOURCE_RANGES (correct) |
| AUDIT_TRACE (POU) | "CCBS_CHANGE_ADD_RANGES for add..." | "CCBS_REMOVE_RESOURCE_RANGES for **add**..." |
| Response RF OPERATION_NAME | CCBS_ADD_RESOURCE_RANGES (correct) | **CCBS_ADD_RESOURCE_RANGES (WRONG)** [HIGH] |

---

## §8 — System & Integration Dependencies

### §8.1 ESB / JMS Channel Dependencies

| Direction | Event | Purpose |
|-----------|-------|---------|
| [OUTBOUND] | `CCBS_REMOVE_RESOURCE_RANGES` | Remove resource ranges per subscriber |
| [LOG] | `Logger` | Audit per dispatch |

### §8.2 Backend API

| System | Operation | Schema |
|--------|-----------|--------|
| CCBS | RemoveResourceRanges | `amdocs.csm3g.datatypes.RemoveResourceRangesRequest.xsd` (ns5), SubscriberIdInfo (ns), ResourceInfo (ns3), ActivityInfo (ns2) |

### §8.3 Fields Used

| Field | Usage |
|-------|-------|
| `ResourceRangeInfo.Action` | Filter: must be "REMOVE" |
| `ResourceRangeInfo.ParameterInstanceId` | Filter: must be non-empty; emitted as `ns3:ParameterInstanceId` |
| `ResourceRangeInfo.effectiveDate/expirationDate` | `ns3:EffectiveDate/ExpirationDate` (conditional) |
| `ResourceRangeInfo.ResourceName` | `ns3:Name` (conditional) |
| `ResourceRangeInfo.ValuesArray` | Tokenized on "-" → `ns3:Values[*]` |
| `Subscriber.SubscriberId` | `ns:SubscrNumber` (no xsl:if guard) |
| `Subscriber.MSISDN` | `ns3:ResrcScopeId` (conditional) |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameters

| Param | Source | Note |
|-------|--------|------|
| `$orderRequest` | orderRequest concept | |
| `$refId` | sub.RefId | |
| `$sub` | current Subscriber | |
| `$removeRangeArray` | typed array of REMOVE ResourceRangeInfo with ParameterInstanceId | |
| `$globalVariables` | — | **NOT declared in XSLT** — credentials emitted unconditionally as a result |

### §9.2 Output XML Tree

```text
createEvent → event
├── JMSPriority              ← $orderRequest/OrderPriority              [Always]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId    [Always]
├── OrderID                  ← $orderRequest/OrderData/OrderID          [Always]
├── RefID                    ← $refId                                   [Always]
├── UserName                 ← $orderRequest/OrderData/User             [UNCONDITIONAL — NO IsEnableUserPass gate] ⚠ BUG
├── PassWord                 ← $orderRequest/OrderData/Password         [UNCONDITIONAL — NO IsEnableUserPass gate] ⚠ BUG
├── OrderType                ← if exists                                [Conditional]
├── CES                      ← if exists                                [Conditional]
└── payload → ns5:RemoveResourceRangesRequest
    ├── ns:SubscriberIdInfo
    │   └── ns:SubscrNumber  ← $sub/SubscriberId                       [Always — no conditional guard]
    ├── ns3:ResourceInfo[*]  (foreach $removeRangeArray/elements)
    │   ├── ns3:EffectiveDate         ← effectiveDate                  [Conditional: if exists]
    │   ├── ns3:ExpirationDate        ← expirationDate                 [Conditional: if exists]
    │   ├── ns3:Name                  ← ResourceName                   [Conditional: if exists]
    │   ├── ns3:ParameterInstanceId   ← ParameterInstanceId            [Conditional: if exists]
    │   ├── ns3:ResrcScopeId          ← $sub/MSISDN                   [Conditional: if exists]
    │   └── ns3:Values[*]             ← tib:tokenize(ValuesArray,"-") [Always — one per token]
    └── ns2:ActivityInfo
        ├── ns2:ActivityReason ← ActivityReason or "CREQ"              [Always]
        └── ns2:UserText       ← SubscriberActivityInfo/UserText       [Conditional: if exists]
```

---

## §11 — Audit Logging

| Scope | AUDIT_TRACE | Issue |
|-------|-------------|-------|
| POU request | "Request Sent for CCBS_REMOVE_RESOURCE_RANGES for **add** resourceRangeInfo" | [LOW] Says "add" — should say "remove" |
| COU request | "Request Sent for CCBS_REMOVE_RESOURCE_RANGES for **add** resourceRangeInfo **ChidOU**" | [LOW] "add" + "ChidOU" typos |
| Response RF | "Response received for **CCBS_ADD_RESOURCE_RANGES**" | [HIGH] Wrong — references ADD not REMOVE |

---

## §12 — Activity Status Management

| Condition | Result |
|-----------|--------|
| At least one subscriber dispatched | `SendFirstRequestEvent` + Status="1" + `SendDataToDB` |
| No subscriber qualified | `SkipActivity("4")` |

---

## §17 — Migration Notes & Recommendations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Credentials emitted unconditionally — always sends UserName/PassWord to CCBS | [HIGH] | Add `<xsl:if test="$globalVariables/OMX_OM/.../IsEnableUserPass='true'">` guard; add $globalVariables XSLT param |
| Response RF OPERATION_NAME and AUDIT_TRACE reference CCBS_ADD_RESOURCE_RANGES instead of CCBS_REMOVE | [HIGH] | Fix Response_CCBS_REMOVE_RESOURCE_RANGES.rulefunction Logger XSLT |
| No guard on removeRangeArray@length — empty request dispatched | [MEDIUM] | Add `if(removeRangeArray@length > 0)` guard |
| AUDIT_TRACE says "add" not "remove"; "ChidOU" typo | [LOW] | Correct AUDIT_TRACE strings |
| logicalDateVal dead code | [MEDIUM] | Remove |
| No reqSuccess check before dispatch | [MEDIUM] | Add per-subscriber reqSuccess guard for resubmit safety |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_REMOVE_RESOURCE_RANGES {
  attribute { priority = 5; forwardChain = true; }
  then {
    try {
      boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
      String logicalDateVal = logicalDateRes.LogicalDate;  // Dead code
      boolean isSkipped = true;

      for(POU) {
        for(Subscriber sub : parentOU.Subscriber) {
          sXML = GetXMLForSubscriber(orderRequest, sub.RefId);
          // PreExecCheck evaluation
          if(chkRes=="true") {
            // Collect ResourceRangeInfo[Action=="REMOVE" AND ParameterInstanceId.length>0]
            // [See §9 for full XSLT payload — builds ns5:RemoveResourceRangesRequest]
            Events.OMConsumers.OMXFM.Request.CCBS_REMOVE_RESOURCE_RANGES reqEvent = Event.createEvent(
              "xslt://{{/Events/OMConsumers/OMXFM/Request/CCBS_REMOVE_RESOURCE_RANGES}}"
              /* Fields: JMSPriority, OrderID, RefID, UserName/PassWord (UNCONDITIONAL — BUG),
                 payload/ns5:RemoveResourceRangesRequest with ParameterInstanceId */);
            Event.assertEvent(reqEvent);
            ActionRequestEvent(reqEvent, orderCurrentActivity);
            /* Logger — AUDIT_TRACE: "...for add..." (wrong word) */
            isSkipped = false;
          }
        }
        for(COU) {
          for(Subscriber sub : childOU.Subscriber) {
            sXML = GetXMLForSubscriberInChildOU(orderRequest, sub.RefId, parentOU.RefId);
            if(chkRes=="true") {
              /* same XSLT, credentials still unconditional */
              /* AUDIT_TRACE: "...add...ChidOU" (double typo) */
              isSkipped = false;
            }
          }
        }
      }
      if(!isSkipped) { SendFirstRequestEvent; Status="1"; SendDataToDB; }
      else { SkipActivity("4"); }
    } catch(Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

Creates `Concepts.FM.Response.CCBS_RemoveResourceRangesRes` (specific type), appends to Response[], logs audit trail, and calls `ActionResponseEvent` for fan-in. The Logger event contains a critical bug: both OPERATION_NAME and AUDIT_TRACE reference CCBS_ADD_RESOURCE_RANGES instead of CCBS_REMOVE_RESOURCE_RANGES.

### §19.2 Scope Variables

| Variable | Type |
|----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_REMOVE_RESOURCE_RANGES` |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` |

### §19.3 ResponseBase Concept

```text
createObject → CCBS_RemoveResourceRangesRes
├── @extId           ← OMXUtils:generateTrackingID()         [Always]
├── ResponseCode     ← $eventResponse/ResponseCode           [Conditional: if exists]
├── ResponseMessage  ← $eventResponse/ResponseMsg            [Conditional: if exists]
├── CompletionStatus ← $eventResponse/CompletionStatus       [Conditional: if exists]
└── ReferenceId      ← $eventResponse/RefID                  [Conditional: if exists]
```

### §19.4 Fan-in

`IntraActivitySequencing.ActionResponseEvent(currActivity)` — returns "true" when all dispatched requests have responded.

### §19.5 Response Audit — Bugs

| Field | Actual value | Expected value |
|-------|-------------|----------------|
| OPERATION_NAME | **CCBS_ADD_RESOURCE_RANGES** [HIGH BUG] | CCBS_REMOVE_RESOURCE_RANGES |
| AUDIT_TRACE | **Response received for CCBS_ADD_RESOURCE_RANGES** [HIGH BUG] | Response received for CCBS_REMOVE_RESOURCE_RANGES |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
