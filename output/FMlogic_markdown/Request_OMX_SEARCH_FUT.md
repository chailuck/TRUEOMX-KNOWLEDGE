# Request_OMX_SEARCH_FUT

> Tri-level OMX future order search — sequential fan-out to Subscriber (nodeLevel=5), POU (nodeLevel=3), COU (nodeLevel=3) using IntraActivitySequencing; STATUS and ORDER_TYPE driven by activity parameters.

**Author:** usuf-chu | **forwardChain:** true | **Generated:** 2026-08-06

---

## §1 Overview & Purpose

Searches OMX for existing FutureOrder records matching a given status and order type. Sends up to three sequential requests — one per hierarchy level: Subscriber (nodeLevel=5), Parent OU (nodeLevel=3), Child OU (nodeLevel=3). Events are dispatched one at a time via `IntraActivitySequencing`: all events are queued with `ActionRequestEvent`, then `SendFirstRequestEvent` dispatches the first; each response triggers the next. The response aggregates `FutureOrders[]` records into a custom `OMX_SearchFutureRes` concept.

> **[ACTIVE]:** `PurgePendingRequestsBeforeResubmit` is present and NOT commented out — resubmit purges the pending queue before re-queuing events.

> **Tri-level pattern:** Unlike per-subscriber fan-out FMs, OMX_SEARCH_FUT sends to up to three specific hierarchy nodes (first subscriber, first POU with OUId, first COU with OUId). The events are sequential (not parallel).

> **No credential gate:** UserName/PassWord are included in the payload only if non-empty in orderRequest (standard `xsl:if`) — there is no `IsEnableUserPass` global variable check as seen in INTX FMs.

> **Audit unconditional:** No `AllowWriteLog(OrderType)` gate — audit events sent for every request and every response regardless of OrderType.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_OMX_SEARCH_FUT.rule` | 123 lines |
| Response file | `Response_OMX_SEARCH_FUT.rulefunction` | 31 lines |
| Author | usuf-chu | |
| forwardChain | true | |
| Schema NS (ns) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd` | |
| Request payload root | `ns:futureOrder` | |
| Response payload root | `ns:futureOrders/ns:futureOrder[]` | Collection |
| Response event type | `Events.OMConsumers.OMXFM.Response.OMX_SEARCH_FUTURE` | |
| Response concept | `Concepts.FM.Response.OMX_SearchFutureRes` | Custom — NOT ResponseBase; has FutureOrders[] |
| extId generation | Inside XSLT via `ns1:generateTrackingID()` | Not passed from BE |
| Fan-out type | IntraActivitySequencing (sequential) | ActionRequestEvent + SendFirstRequestEvent |
| Max events | 3 (Subscriber + POU + COU) | Each conditional on node existence |
| PurgePendingRequestsBeforeResubmit | [ACTIVE] | Not commented out |
| Credential gate | None (`IsEnableUserPass` not used) | UserName/PassWord included if non-empty in orderRequest |
| Audit gate (request) | [UNCONDITIONAL] | No AllowWriteLog |
| Audit gate (response) | [UNCONDITIONAL] | No AllowWriteLog |
| Logger pattern (response) | `Log.getLogger` + `Log.log` | Not `System.debugOut` |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Subscriber/POU/COU data; OMXTrackingId; OrderID |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Parameter[]; RequestCount; Response[]; Status |
| `nextAct` | Concepts.OM.ProcessConfig.Activity (local) | Live lookup — PreExecCheck |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_SEARCH_FUT"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_SEARCH_FUT"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 Activity Parameter Extraction

Parameters extracted by looping over `orderCurrentActivity.Parameter[]` with `tib:tokenize(param, "=")` — different from `GetActivityParameterValueFromKey` used in other FMs:

```java
for (int iParam=0; iParam<orderCurrentActivity.Parameter@length; iParam++) {
    String param     = XPath.evalAsString("Parameter[(number($iParam)+1)]", ...);
    String paramKey  = XPath.evalAsString("tib:tokenize($param, '=')[1]", ...);
    String paramValue= XPath.evalAsString("tib:tokenize($param, '=')[2]", ...);
    if(String.equals("STATUS", paramKey))     futStatus = paramValue;
    if(String.equals("ORDER_TYPE", paramKey)) futOrderType = paramValue;
}
```

| Activity Parameter Key | Variable | Used in XSLT |
|------------------------|----------|--------------|
| `STATUS` | `futStatus` | `ns:status` in futureOrder payload |
| `ORDER_TYPE` | `futOrderType` | `ns:orderType` in futureOrder payload |

> In the POSTPAID_ADD_OFFER_SUB process step 33, no parameters are listed — both `futStatus` and `futOrderType` will be empty strings.

---

## §6 Execution Flow Diagram

1. **Setup:** isActResub; nextAct live lookup; isSkipped=true; extract futStatus/futOrderType from Parameter[]
2. PreExecCheck gate — if present, evaluate against orderRequest XML
3. If isActResub → `PurgePendingRequestsBeforeResubmit` [ACTIVE]
4. **[Subscriber branch]:** `tib:if-absent(POU[1]/Subscriber[1]/@extId, POU[1]/COU[1]/Subscriber[1]/@extId)`
   - If subExtId != null: create reqEvent (nodeLevel=**5**, nodeId=subscriber.SubscriberId)
   - `Event.assertEvent` → `ActionRequestEvent` → RequestCount++ → audit → isSkipped=false
5. **[ParentOU branch]:** `POU[OUId/text()][1]/@extId`
   - If pOuExtId != null: create reqEvent (nodeLevel=**3**, nodeId=pOu.OUId)
   - `ActionRequestEvent` → RequestCount++ → audit → isSkipped=false
6. **[ChildOU branch]:** `POU[1]/COU[OUId/text()][1]/@extId`
   - If cOuExtId != null: create reqEvent (nodeLevel=**3**, nodeId=cOu.OUId)
   - `ActionRequestEvent` → RequestCount++ → audit → isSkipped=false
7. If !isSkipped → `SendFirstRequestEvent` → Status="1" → `SendDataToDB`
8. If isSkipped → `SkipActivity("4")`
9. Catch → `HandleActivityException`

---

## §7 Node Resolution & nodeLevel Mapping

| Branch | Node extId XPath | Concept type | nodeLevel | nodeId source |
|--------|-----------------|--------------|-----------|---------------|
| **Subscriber** | `tib:if-absent(POU[1]/Subscriber[1]/@extId, POU[1]/COU[1]/Subscriber[1]/@extId)` | Concepts.OrderRequest.OrderElements.Subscriber | 5 (hardcoded) | `number($subscriber/SubscriberId)` |
| **ParentOU** | `POU[OUId/text()][1]/@extId` | Concepts.OrderRequest.OrderElements.ParentOU | 3 (hardcoded) | `number($pOu/OUId)` |
| **ChildOU** | `POU[1]/COU[OUId/text()][1]/@extId` | Concepts.OrderRequest.OrderElements.ChildOU | 3 (hardcoded) | `number($cOu/OUId)` |

---

## §8 System & Integration Dependencies

### §8.1 — ESB / JMS Channel Dependencies

| Direction | Event type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_SEARCH_FUTURE` | FutureOrder search request |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.OMX_SEARCH_FUTURE` | FutureOrder list response |

### §8.2 — Backend API

| Field | Value |
|-------|-------|
| Backend | OMX (internal FutureOrder service) |
| Operation | SearchFuture |
| Schema NS | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd` |
| Request root | `ns:futureOrder` |
| Response root | `ns:futureOrders/ns:futureOrder[]` |

### §8.3 — BE Working Memory Dependencies

| Concept | Field | Access | Notes |
|---------|-------|--------|-------|
| Activity | Parameter[] | READ | futStatus and futOrderType extraction |
| Activity | RequestCount / Response[] / Status | READ+WRITTEN | Standard |
| Subscriber | SubscriberId | READ | nodeId for subscriber branch |
| ParentOU | OUId / RefId | READ | nodeId / RefID for POU branch |
| ChildOU | OUId / RefId | READ | nodeId / RefID for COU branch |
| OMX_SearchFutureRes | FutureOrders[] | WRITTEN | Created by response handler |

### §8.4 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `OMX_OM/WritePayload` | Audit payload inclusion |

---

## §9 Detailed Payload Build

### §9.1 — XSLT Parameters (common to all three variants)

| Parameter | Bound From | Notes |
|-----------|-----------|-------|
| `$orderRequest` | orderRequest concept | |
| `$subscriber` / `$pOu` / `$cOu` | Respective concept instance | One per variant |
| `$futStatus` | Activity Parameter STATUS | XSLT value-of → ns:status |
| `$futOrderType` | Activity Parameter ORDER_TYPE | XSLT value-of → ns:orderType |

### §9.2 — XSLT Field Mapping Tree

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority           [xsl:if]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId [xsl:if]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID       [xsl:if]
    ├── RefID                    ← $subscriber/RefId (or $pOu/RefId / $cOu/RefId) [xsl:if — per variant]
    ├── UserName                 ← $orderRequest/OrderData/User          [xsl:if — no IsEnableUserPass]
    ├── PassWord                 ← $orderRequest/OrderData/Password      [xsl:if — no IsEnableUserPass]
    ├── OrderType                ← $orderRequest/OrderData/OrderType     [xsl:if]
    └── payload
        └── ns:futureOrder
            ├── ns:status        ← $futStatus         (from STATUS parameter)
            ├── ns:orderType     ← $futOrderType      (from ORDER_TYPE parameter)
            ├── ns:nodeLevel     ← 5 (Subscriber) / 3 (POU) / 3 (COU)  [Hardcoded]
            └── ns:nodeId        ← number($subscriber/SubscriberId) / number($pOu/OUId) / number($cOu/OUId)
```

### §9.3 — Variant Comparison Table

| Field | Subscriber variant | POU variant | COU variant |
|-------|-------------------|-------------|-------------|
| XSLT param | `$subscriber` | `$pOu` | `$cOu` |
| `RefID` | `$subscriber/RefId` | `$pOu/RefId` | `$cOu/RefId` |
| `ns:nodeLevel` | `5` (hardcoded) | `3` (hardcoded) | `3` (hardcoded) |
| `ns:nodeId` | `number($subscriber/SubscriberId)` | `number($pOu/OUId)` | `number($cOu/OUId)` |

---

## §10 Response — OMX_SearchFutureRes Concept Construction

### §10.1 — XSLT Mapping Tree

```text
createObject (Concepts.FM.Response.OMX_SearchFutureRes)
└── object
    ├── @extId               ← ns1:generateTrackingID()  [inside XSLT, not from BE]
    ├── ResponseCode         ← $eventResponse/ResponseCode        [xsl:if]
    ├── ResponseMessage      ← $eventResponse/ResponseMsg         [xsl:if]
    ├── CompletionStatus     ← $eventResponse/CompletionStatus    [xsl:if]
    └── FutureOrders[]       [xsl:for-each: $eventResponse/payload/ns:futureOrders/ns:futureOrder]
        └── FutureOrders
            ├── @extId               ← ns1:generateTrackingID()
            ├── FutureOrderId        ← ns:futureOrderId    [xsl:if]
            ├── EffectiveDate        ← ns:effectiveDate    [xsl:if]
            ├── Status               ← ns:status           [xsl:if]
            ├── OrderType            ← ns:orderType        [xsl:if]
            ├── NodeLevel            ← ns:nodeLevel        [xsl:if]
            ├── NodeId               ← ns:nodeId           [xsl:if]
            ├── RequestedDate        ← ns:requestedDate    [xsl:if]
            ├── RequestedBy          ← ns:requestedBy      [xsl:if]
            ├── UpdatedDate          ← ns:updatedDate      [xsl:if]
            ├── UpdatedBy            ← ns:updatedBy        [xsl:if]
            ├── DealerCode           ← ns:dealerCode       [xsl:if]
            ├── ActivityReason       ← ns:activityReason   [xsl:if]
            ├── ExtendedInfos[]      [xsl:for-each: ns:extendedInfo]
            │   ├── Name             ← ns:name
            │   └── Value            ← ns:value
            ├── fromOrderId          ← ns:fromOrderId      [xsl:if]
            ├── ToOMXId              ← ns:toOMXId          [xsl:if]
            ├── UserText             ← ns:userText         [xsl:if]
            ├── Remark               ← ns:remark           [xsl:if]
            └── futureType           ← ns:futureType       [xsl:if]
```

> Unlike most response FMs that store a single summary record, `OMX_SearchFutureRes` stores a **full collection** (`FutureOrders[]`) of matching future order records.

---

## §11 Audit Logging

| Phase | Gate | OPERATION_NAME | AUDIT_TRACE |
|-------|------|----------------|-------------|
| Request (×3 max) | [UNCONDITIONAL] | `"OMX_SEARCH_FUT"` | `"Request Sent for OMX_SEARCH_FUT"` |
| Response | [UNCONDITIONAL] | `"OMX_SEARCH_FUT"` | `"Response received for OMX_SEARCH_FUT"` |

---

## §12 Activity Status Management

| Condition | Call | Code |
|-----------|------|------|
| Each event queued | `GetActivityStatusString("1", false)` (per-branch) | "1" (RUNNING) |
| After all events queued | `SendFirstRequestEvent` + `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" (RUNNING) |
| No nodes found | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" (SKIPPED) |

---

## §13 Function Dependency Tree

```text
Request_OMX_SEARCH_FUT (rule)
├── Instance.getByExtIdByUri(NextActivityName, Activity)  [nextAct]
├── XPath loop: tib:tokenize(Parameter[i], "=") → futStatus, futOrderType
├── [isActResub] PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── [Subscriber branch — tib:if-absent]:
│   ├── Instance.getByExtIdByUri(subExtId, Subscriber)
│   ├── Event.createEvent(XSLT: $subscriber → nodeLevel=5, nodeId=SubscriberId)
│   └── Event.assertEvent + ActionRequestEvent + RequestCount++ + sendAudit + SendDataToDB
├── [POU branch — POU[OUId/text()][1]]:
│   ├── Instance.getByExtIdByUri(pOuExtId, ParentOU)
│   ├── Event.createEvent(XSLT: $pOu → nodeLevel=3, nodeId=OUId)
│   └── Event.assertEvent + ActionRequestEvent + RequestCount++ + sendAudit + SendDataToDB
├── [COU branch — POU[1]/COU[OUId/text()][1]]:
│   ├── Instance.getByExtIdByUri(cOuExtId, ChildOU)
│   ├── Event.createEvent(XSLT: $cOu → nodeLevel=3, nodeId=OUId)
│   └── Event.assertEvent + ActionRequestEvent + RequestCount++ + sendAudit + SendDataToDB
├── SendFirstRequestEvent(orderCurrentActivity)
├── GetActivityStatusString("1", false) + SendDataToDB
├── SkipActivity("4")  [if isSkipped]
└── HandleActivityException  [catch]

Response_OMX_SEARCH_FUT (rulefunction)
├── Log.getLogger + Log.log("debug", orderRequest@extId)
├── Instance.createInstance("xslt://OMX_SearchFutureRes")
│   ├── extId = ns1:generateTrackingID()  [inside XSLT]
│   ├── ResponseCode, ResponseMessage, CompletionStatus  [conditional]
│   └── FutureOrders[] via xsl:for-each ns:futureOrders/ns:futureOrder
├── currActivity.Response[length] = resEvent
├── Log.log("trace", resEvent serialized)
├── sendAudit (unconditional)
├── Log.log("debug", "Completed")
└── return "true"
```

---

## §14 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Extract `STATUS` and `ORDER_TYPE` from Activity Parameters via tokenize loop; pass as query filters. |
| R2 | Send up to 3 sequential requests: Subscriber (nodeLevel=5), POU (nodeLevel=3), COU (nodeLevel=3). Skip any absent node. |
| R3 | `PurgePendingRequestsBeforeResubmit` is ACTIVE — resubmit must purge queue before re-queuing. |
| R4 | Subscriber selection uses `tib:if-absent`: prefer POU[1]/Subscriber[1], fall back to COU[1]/Subscriber[1]. |
| R5 | POU/COU selection filters on `[OUId/text()]` — only nodes with a populated OUId are included. |
| R6 | No `IsEnableUserPass` credential gate — credentials included if non-empty in orderRequest. |
| R7 | Audit is unconditional — no AllowWriteLog gate; log on every request and every response. |
| R8 | Response stores `FutureOrders[]` collection — downstream logic reads this array to check for conflicting/existing future orders. |
| R9 | Response rulefunction returns `"true"`; no explicit count-based fan-in — sequencing handled by IntraActivitySequencing. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Subscriber selection `tib:if-absent` picks FIRST subscriber only — does not iterate all subscribers | [MEDIUM] | Verify with business that searching only the first subscriber is the correct scope |
| Parameter extraction uses XPath tokenize loop — fragile if parameter format changes from `KEY=VALUE` | [LOW] | Replace with `GetActivityParameterValueFromKey` in migration for consistency |
| No credential gate — credentials always included if present | [LOW] | Align with INTX FM pattern (IsEnableUserPass) in migration |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
