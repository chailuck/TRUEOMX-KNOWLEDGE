# Request_GPS_INSERT_INFORMATION

> FM Logic Documentation — GPS Prepaid Birthdate Registration (Direct parallel dispatch, per-subscriber, single-field payload)

**Rule:** `Rules.OMConsumers.OMXFM.Request.Request_GPS_INSERT_INFORMATION` | **Priority:** 5 | **Backend:** GPS (InsertInformation) | **Pattern:** Direct parallel dispatch per-subscriber

---

## §1 — Overview & Purpose

**GPS_INSERT_INFORMATION** registers the subscriber's birthdate into the GPS system during prepaid registration. It sends one GPS InsertInformation request per subscriber (ParentOU and ChildOU), dispatching each immediately and in parallel — this is **not IntraActivitySequencing**. The operation type is hardcoded to `"birthdateprepaid"`; the key is the subscriber MSISDN; the value is the pre-formatted birthdate in Asia/Bangkok timezone.

The payload is extremely minimal: only three fields. This FM exists solely to write the subscriber's birthdate into GPS during the prepaid SIM registration journey.

> **Direct parallel dispatch — not IntraActivitySequencing:** Unlike CCP/CRM FMs, each subscriber event is sent immediately via `sendEventImmediate`. The `RequestCount` is incremented per subscriber. Fan-in uses `RequestCount == successResponseCount` (count of responses with ResponseCode ending in "000").

> **Copy-paste bugs present (see §13 & §19):**
> - Response RF `AUDIT_TRACE = "Response received for CCBS_UPDATE_SUBSCRIBER"` — wrong FM name
> - ParentOU has a dead `String refId = nanoTime()` declaration (never used)
> - ChildOU has a dead `String refId = cSubRefId` declaration (never used)
> - Entire commented-out CRM_CREATE_UPDATE_SR XSLT block in ChildOU section (dead code)

| Attribute | Value |
|-----------|-------|
| Rule file | `Request_GPS_INSERT_INFORMATION.rule` |
| Response rulefunction | `Response_GPS_INSERT_INFORMATION.rulefunction` |
| Priority | 5 |
| Backend system | GPS via ESB (`InsertInformation`) |
| Request event type | `Events.OMConsumers.OMXFM.Request.GPS_INSERT_INFORMATION` |
| Response event type | `Events.OMConsumers.OMXFM.Response.GPS_INSERT_INFORMATION` |
| Response concept | `Concepts.FM.Base.ResponseBase` |
| Payload schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/GPS/InsertInformation.xsd` |
| Dispatch scope | Per Subscriber — both ParentOU and ChildOU |
| Dispatch pattern | Direct parallel (sendEventImmediate per subscriber, RequestCount++) |
| refId for idempotency | `pSubRefId` / `cSubRefId` (subscriber RefId) |
| Payload type field | Hardcoded `"birthdateprepaid"` — always static |
| Payload value field | Subscriber's birthdate formatted in Asia/Bangkok TZ |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM priority |
| forwardChain | true | Enables forward chaining |
| Rule type | Direct parallel dispatch | NOT IntraActivitySequencing — immediate sendEventImmediate per subscriber |
| Resubmit | Yes | Idempotency check; RequestCount not incremented on resubmit |
| Author | CHAYATORN-PC | |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order; birthdate sourced from CustomerGeneralInfo |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — RequestCount tracker, Response[] for idempotency fan-in |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId matches |
| 2 | `orderCurrentActivity.ActivityID == "GPS_INSERT_INFORMATION"` | Constrains to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "GPS_INSERT_INFORMATION"` | Double-check via NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity ready |

---

## §5 — Execution Flow Diagram

1. **Check resubmit flag** — `isActResub = RequestCount > 0 && IsOrderResubmitted`
2. **Get activity config** — `Instance.getByExtIdByUri` → `nextAct.PreExecCheck`
3. **ParentOU subscriber loop** — for each ParentOU → Subscriber:
   - `pSubRefId = psub.RefId` — idempotency key
   - **Idempotency check**: scan `Response[]` for `ReferenceId == pSubRefId && CompletionStatus == 2`
   - **PreExecCheck**: `GetXMLForSubscriber(orderRequest, pSubRefId)` → XPath check
   - **BirthDate pre-processing**: null-check → translate to Asia/Bangkok → format `yyyy-MM-dd'T'HH:mm:ss.SSSXXX`
   - `[DEAD]` `String refId = nanoTime()` — never used
   - Build XSLT event → **`sendEventImmediate`** (NOT assertEvent/ActionRequestEvent)
   - `isSkipped = false`; if not resubmit: `RequestCount++`
   - Audit log (gated on `AllowWriteLog`)
4. **ChildOU subscriber loop** — same pattern but:
   - PreExecCheck via `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)`
   - `[DEAD]` `String refId = cSubRefId` — never used
   - `[DEAD]` Entire commented-out CRM_CREATE_UPDATE_SR XSLT block (120 lines)
5. **Final status**: if any sent → `GetActivityStatusString("1", false)` + `SendDataToDB`; else → `SkipActivity("4")`

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
try {
    // ParentOU Subscriber loop
    for(int p=0; p<pOuLen; p++) {
        for(int ps=0; ps<pSubLen; ps++) {
            String pSubRefId = psub.RefId;
            // Idempotency check: CompletionStatus==2 + ReferenceId==pSubRefId
            if(!reqSuccess) {
                // PreExecCheck via GetXMLForSubscriber
                if(String.equals(chkRes, "true")) {
                    // BirthDate: translateTime→Asia/Bangkok → format SSSXXX
                    String refId = String.valueOfLong(System.nanoTime()); // DEAD — never used
                    // [XSLT: InsertInformationReq — see §9]
                    Event.Ext.sendEventImmediate(reqEvent);  // Direct send (not assertEvent)
                    isSkipped = false;
                    if(!isActResub) orderCurrentActivity.RequestCount++;  // Increment per subscriber
                    if(AllowWriteLog(OrderType)) { /* audit */ }
                }
            }
        }
    }

    // ChildOU Subscriber loop
    for(int c=0; c<cOuLen; c++) {
        for(int cs=0; cs<cSubLen; cs++) {
            String cSubRefId = csub.RefId;
            if(!reqSuccess) {
                // PreExecCheck via GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)
                if(String.equals(chkRes, "true")) {
                    String refId = cSubRefId; // DEAD — never used
                    /* DEAD: 120-line commented-out CRM_CREATE_UPDATE_SR XSLT block */
                    // [XSLT: InsertInformationReq ChildOU variant — see §9]
                    Event.Ext.sendEventImmediate(reqEvent);
                    isSkipped = false;
                    if(!isActResub) orderCurrentActivity.RequestCount++;
                    if(AllowWriteLog(OrderType)) { /* audit */ }
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
```

---

## §7 — Data Extraction & Pre-Processing

### §7.1 — BirthDate Pre-Processing

| Field | Source | Processing | Format |
|-------|--------|-----------|--------|
| `birthDateFormat` | `orderRequest.OrderData.Customer.CustomerGeneralInfo.BirthDate` | Null-check → translate to Asia/Bangkok | `yyyy-MM-dd'T'HH:mm:ss.SSSXXX` |

> **Timezone format difference vs CRM_UPSERT_CUSTOMER_ACCOUNT:** This FM uses `SSSXXX` (ISO 8601 offset e.g. +07:00) rather than `SSSZ` (RFC 822 e.g. +0700). Both represent Bangkok time but in different offset formats. GPS format is XSD-compliant; CRM format may not be.

> **Null-guarded:** If `BirthDate` is null, `birthDateFormat` remains an empty string. The XSLT emits `<ns1:value></ns1:value>` with no content — GPS receives an empty birthdate value.

### §7.2 — Dead Code Variables

| Location | Code | Issue |
|----------|------|-------|
| ParentOU block, line 64 | `String refId = String.valueOfLong(System.nanoTime());` | Declared but never used. XSLT uses `$pSubRefId` for RefID, not this. |
| ChildOU block, line 112 | `String refId = cSubRefId;` | Declared but never used. Copy-paste remnant from another FM. |
| ChildOU block, ~line 119 | Entire commented-out CRM_CREATE_UPDATE_SR XSLT | 120-line dead block from a different FM entirely. |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

No order type conditional logic in this FM. The GPS InsertInformation request is the same for all order types (subject to PreExecCheck gate and subscriber presence).

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.GPS_INSERT_INFORMATION` | GPS prepaid birthdate insert per subscriber (direct parallel) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit (AllowWriteLog-gated) |

### §8.3 — Backend API Details

| System | Operation | Protocol | Schema |
|--------|-----------|---------|--------|
| GPS | InsertInformation | JMS async (direct parallel) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/GPS/InsertInformation.xsd` |

### §8.4 — BE Working Memory Dependencies

| Concept path | Access | Purpose |
|-------------|--------|---------|
| `ParentOU[*].Subscriber[*].RefId` | Read | pSubRefId — idempotency key + JMS RefID header |
| `ParentOU[*].Subscriber[*].MSISDN` | Read | GPS `ns1:key` field (conditional) |
| `ChildOU[*].Subscriber[*].RefId` | Read | cSubRefId — idempotency key + JMS RefID header |
| `ChildOU[*].Subscriber[*].MSISDN` | Read | GPS `ns1:key` field (conditional) |
| `Customer.CustomerGeneralInfo.BirthDate` | Read | Source for `ns1:value` — birthdate formatted in Bangkok TZ |
| `orderRequest.OrderData.OrderType` | Read | AllowWriteLog gate for audit |
| `orderCurrentActivity.RequestCount` | Read/Write | Incremented per subscriber dispatched (non-resubmit); used by response RF for fan-in |
| `orderCurrentActivity.Response[]` | Read | Idempotency check per subscriber |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameters

| Variant | Param | Source |
|---------|-------|--------|
| ParentOU | `$orderRequest` | orderRequest concept |
| ParentOU | `$pSubRefId` | psub.RefId |
| ParentOU | `$psub` | ParentOU Subscriber concept |
| ParentOU | `$birthDateFormat` | Pre-computed: Bangkok-TZ BirthDate |
| ChildOU | `$orderRequest` | orderRequest concept |
| ChildOU | `$cSubRefId` | csub.RefId |
| ChildOU | `$csub` | ChildOU Subscriber concept |
| ChildOU | `$birthDateFormat` | Pre-computed: Bangkok-TZ BirthDate |

The two variants differ only in the RefID param name (`$pSubRefId` vs `$cSubRefId`) and subscriber param (`$psub` vs `$csub`). Payload structure is identical.

### §9.2 — Event Container

Event `extId` set via `OMXUtils:generateTrackingID()` in XSLT — unique per subscriber request.

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$pSubRefId` / `$cSubRefId` | Always |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Always |

### §9.4 — Payload Root Element

`ns1:InsertInformationReq` — namespace: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/GPS/InsertInformation.xsd`

### §9.5 — Payload Fields

| Element | Source | Condition | Notes |
|---------|--------|-----------|-------|
| `ns1:type` | `"birthdateprepaid"` | Always | Hardcoded static string |
| `ns1:key` | `$psub/MSISDN` or `$csub/MSISDN` | `xsl:if test="$psub/MSISDN"` | The subscriber's MSISDN |
| `ns1:value` | `$birthDateFormat` | Always (may be empty if BirthDate null) | BirthDate in Bangkok TZ, ISO 8601 +HH:MM |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── @extId              ← OMXUtils:generateTrackingID()                  [Always]
    ├── JMSPriority         ← $orderRequest/OrderPriority                    [Always]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId          [Always]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                [Always]
    ├── RefID               ← $pSubRefId / $cSubRefId (subscriber RefId)     [Always]
    ├── OrderType           ← $orderRequest/OrderData/OrderType              [Always]
    └── payload
        └── ns1:InsertInformationReq
            ├── ns1:type    ← "birthdateprepaid"                             [Always - HARDCODED]
            ├── ns1:key     ← $psub/MSISDN or $csub/MSISDN                  [Conditional: if MSISDN exists]
            └── ns1:value   ← $birthDateFormat (Bangkok TZ, SSSXXX)         [Always - empty string if BirthDate null]
```

---

## §11 — Audit Logging

| Event | Gate | Key fields |
|-------|------|-----------|
| Request audit (per subscriber) | `AllowWriteLog(OrderType)` | `OPERATION_NAME="GPS_INSERT_INFORMATION"`, `AUDIT_TRACE="Request Sent for GPS_INSERT_INFORMATION"` |
| Response audit | Unconditional (no AllowWriteLog) | `OPERATION_NAME="GPS_INSERT_INFORMATION"`, `AUDIT_TRACE="Response received for CCBS_UPDATE_SUBSCRIBER"` ← **[BUG: wrong FM name]** |

> **Response AUDIT_TRACE bug:** Copy-pasted from CCBS_UPDATE_SUBSCRIBER FM, wrong name not updated. Audit trail searches for GPS responses will fail; false CCBS entries will pollute logs.

> **Request/Response asymmetry:** Request audit is `AllowWriteLog`-gated. Response audit is unconditional — inconsistent with CRM_UPSERT_CUSTOMER_ACCOUNT (which correctly gates both).

---

## §12 — Activity Status Management

| Condition | Action | Status |
|-----------|--------|--------|
| At least one subscriber dispatched | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" = PROCESSING |
| No subscribers pass checks | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" = SKIPPED |

> **Fan-in is in the response RF, not the request rule.** All subscribers are sent immediately. The response RF determines completion via `RequestCount == successResponseCount`.

---

## §13 — Exception / Error Handling

**Request rule:** Standard `catch(Exception ae) → HandleActivityException`.

**Response RF:** No try/catch — bare body.

> **Dead code cleanup needed:** The 120-line commented-out CRM_CREATE_UPDATE_SR XSLT block in the ChildOU section should be removed. It creates maintenance confusion.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Helpers.GetXMLForSubscriber(orderRequest, refId)` | Builds PreExecCheck XML for a ParentOU subscriber |
| `Helpers.GetXMLForSubscriberInChildOU(orderRequest, subRefId, ouRefId)` | Builds PreExecCheck XML for a ChildOU subscriber (requires parent OURefId) |
| `Helpers.AllowWriteLog(orderType)` | Request audit gate (response audit is unconditional) |
| `Helpers.GetActivityStatusString(code, flag)` | Status code translation |
| `Helpers.SendDataToDB(orderRequest)` | Persist order state |
| `Helpers.SkipActivity(orderRequest, activity, code)` | Mark activity skipped |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |

---

## §15 — Function Dependency Tree

```text
Request_GPS_INSERT_INFORMATION (rule)
├── Instance.getByExtIdByUri()
├── Helpers.GetXMLForSubscriber()                  [PreExecCheck, ParentOU subscriber]
├── Helpers.GetXMLForSubscriberInChildOU()         [PreExecCheck, ChildOU subscriber]
├── XPath.execute()                                [PreExecCheck evaluation]
├── DateTime.translateTime()                       [birthDate → Asia/Bangkok]
├── DateTime.format()                              [format as SSSXXX ISO string]
├── Event.createEvent()                            [GPS InsertInformationReq XSLT]
│   ├── ParentOU variant: $pSubRefId, $psub
│   └── ChildOU variant:  $cSubRefId, $csub
├── Event.Ext.sendEventImmediate()                 [direct per-subscriber dispatch]
├── [if !isActResub] orderCurrentActivity.RequestCount++
├── Helpers.AllowWriteLog()
├── System.nanoTime()
├── Event.createEvent()                            [Logger XSLT]
├── Event.Ext.sendEventImmediate()                 [audit log]
├── Helpers.GetActivityStatusString()
├── Helpers.SendDataToDB()
├── Helpers.SkipActivity()
└── Helpers.HandleActivityException()

Response_GPS_INSERT_INFORMATION (rulefunction)
├── OMXUtils.generateTrackingID()                  [extId — USED: passed as $extId to ResponseBase XSLT]
├── Instance.createInstance()                      [ResponseBase XSLT]
├── currActivity.Response[] ← activityRes
├── System.nanoTime()
├── Event.createEvent()                            [Logger XSLT — AUDIT_TRACE BUG: says CCBS_UPDATE_SUBSCRIBER]
├── Event.Ext.sendEventImmediate()                 [unconditional response audit]
├── XPath.evalAsInt()                              [count(Response[ResponseCode ends with "000"])]
└── [currActivity.RequestCount == successResponseCount]
    → return "true"  (all responses succeeded)
    → return "false" (still waiting)
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | Both | OrderData.Customer.CustomerGeneralInfo.BirthDate; ParentOU[]/ChildOU[]/Subscriber[] |
| `Concepts.OM.ProcessConfig.Activity` | Both | ActivityID, Status, RequestCount (written), Response[] (read) |
| `Concepts.FM.Base.ResponseBase` | Response RF | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |
| `Concepts.OrderRequest.OrderElements.Subscriber` | Request rule | RefId (idempotency key), MSISDN (GPS key field) |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | For each subscriber (ParentOU and ChildOU), register the customer's birthdate in GPS with type="birthdateprepaid" and key=MSISDN |
| R2 | Per-subscriber idempotency: skip if CompletionStatus=2 and ReferenceId=subscriber RefId in Response[] |
| R3 | BirthDate null-guarded — empty string sent if BirthDate is null |
| R4 | BirthDate formatted in Asia/Bangkok timezone as ISO 8601 with +HH:MM offset (SSSXXX) |
| R5 | RequestCount incremented per subscriber dispatched (not on resubmit) |
| R6 | Fan-in: activity complete when all subscribers return ResponseCode ending in "000" |
| R7 | PreExecCheck evaluated per subscriber (ParentOU: GetXMLForSubscriber; ChildOU: GetXMLForSubscriberInChildOU) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Response AUDIT_TRACE bug:** `"Response received for CCBS_UPDATE_SUBSCRIBER"` — wrong FM name. GPS response audit entries mislabeled as CCBS. | [HIGH] | Fix: change to `"Response received for GPS_INSERT_INFORMATION"` in response RF Logger XSLT |
| **Empty birthdate value:** If `CustomerGeneralInfo.BirthDate` is null, GPS receives empty `<ns1:value>`. No validation or skip logic for null birthdate. | [MEDIUM] | Add null birthdate check to PreExecCheck or explicit skip when birthDateFormat is empty |
| **Dead code — 3 items:** (1) `String refId = nanoTime()` in ParentOU; (2) `String refId = cSubRefId` in ChildOU; (3) 120-line commented-out CRM_CREATE_UPDATE_SR XSLT block. | [LOW] | Remove all three; the XSLT block is especially confusing |
| **Timezone format inconsistency:** GPS uses `SSSXXX` (+07:00 style, XSD-correct), CRM uses `SSSZ` (+0700 style). | [LOW] | GPS format is correct. Verify CRM service accepts +0700 format without colon. |
| **Response audit not AllowWriteLog-gated:** Response RF sends audit log unconditionally — asymmetric with request audit and inconsistent with CRM RF. | [LOW] | Wrap response audit in `if(AllowWriteLog(...))` for consistency |
| **Success-only fan-in deadlock:** If any subscriber's GPS call fails (non-"000"), `successResponseCount` never equals `RequestCount` — activity waits indefinitely. | [MEDIUM] | Add timeout/error handling, or change fan-in to use CompletionStatus like other FMs |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_GPS_INSERT_INFORMATION {
    attribute { priority = 5; forwardChain = true; }
    // ... declare / when as standard ...
    then {
        boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
        try {
            // ParentOU Subscriber loop
            for(int p=0; p<pOuLen; p++) {
                for(int ps=0; ps<pSubLen; ps++) {
                    String pSubRefId = psub.RefId;
                    // Idempotency check
                    if(!reqSuccess) {
                        // PreExecCheck via GetXMLForSubscriber
                        if(String.equals(chkRes, "true")) {
                            // BirthDate: translateTime→Asia/Bangkok → format SSSXXX
                            String refId = nanoTime(); // DEAD
                            // [XSLT: InsertInformationReq — see §9]
                            // type="birthdateprepaid", key=$psub/MSISDN, value=$birthDateFormat
                            Event.Ext.sendEventImmediate(reqEvent);
                            isSkipped = false;
                            if(!isActResub) orderCurrentActivity.RequestCount++;
                            if(AllowWriteLog(OrderType)) { /* audit */ }
                        }
                    }
                }
            }
            // ChildOU Subscriber loop
            for(int c=0; c<cOuLen; c++) {
                for(int cs=0; cs<cSubLen; cs++) {
                    String cSubRefId = csub.RefId;
                    if(!reqSuccess) {
                        // PreExecCheck via GetXMLForSubscriberInChildOU
                        if(String.equals(chkRes, "true")) {
                            String refId = cSubRefId; // DEAD
                            /* DEAD: 120-line CRM_CREATE_UPDATE_SR XSLT block */
                            // [XSLT: InsertInformationReq ChildOU — see §9]
                            Event.Ext.sendEventImmediate(reqEvent);
                            isSkipped = false;
                            if(!isActResub) orderCurrentActivity.RequestCount++;
                            if(AllowWriteLog(OrderType)) { /* audit */ }
                        }
                    }
                }
            }
            if(!isSkipped) {
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                SendDataToDB(orderRequest);
            } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
        } catch(Exception ae) { HandleActivityException(...); }
    }
}
```

---

## §19 — Response Message Rule (Response_GPS_INSERT_INFORMATION)

### §19.1 — Overview

Builds a `ResponseBase` concept from the GPS response, logs unconditionally (no `AllowWriteLog` gate — and with **wrong FM name in AUDIT_TRACE**), then evaluates fan-in: activity complete when all subscribers returned ResponseCode ending in `"000"`.

> **Copy-paste origin confirmed:** Line 14 has a commented-out debug log saying `"Executing RuleFunctions.OrderResponse.Response_CCBS_UPDATE_SUBSCRIBER"` — the entire response RF was adapted from CCBS_UPDATE_SUBSCRIBER without updating the audit trace.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context (passed to audit logger) |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.GPS_INSERT_INFORMATION` | GPS response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity; `RequestCount` read for fan-in comparison |

### §19.3 — ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId          ← $extId (OMXUtils.generateTrackingID() from BE — IS used here)  [Always]
    ├── ResponseCode    ← $eventResponse/ResponseCode                                    [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg                                     [Conditional]
    ├── CompletionStatus← $eventResponse/CompletionStatus                                [Conditional]
    └── ReferenceId     ← $eventResponse/RefID  (matches pSubRefId/cSubRefId)           [Conditional]
```

### §19.4 — Response Completion Logic

| Step | Logic |
|------|-------|
| Success count | `XPath.evalAsInt("count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = '000'])")` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Return "true" | All dispatched subscribers returned a "000"-suffix ResponseCode |
| Return "false" | Still waiting for more subscribers to respond |

> **Success-only fan-in:** Fan-in requires ALL responses to have ResponseCode ending in "000". A single GPS failure means the activity will never complete — it waits indefinitely.

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| `OPERATION_NAME` | `"GPS_INSERT_INFORMATION"` ✓ |
| `AUDIT_TRACE` | `"Response received for CCBS_UPDATE_SUBSCRIBER"` ← **[BUG: wrong FM name]** |
| Gate | Unconditional (no AllowWriteLog — unlike request audit) |
| `PROCESS_ID` | `concat($pid, "_RES")` |
| `payload` | Full `$eventResponse` copy, gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
