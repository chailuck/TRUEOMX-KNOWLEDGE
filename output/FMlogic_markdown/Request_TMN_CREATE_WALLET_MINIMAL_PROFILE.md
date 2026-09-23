# Request_TMN_CREATE_WALLET_MINIMAL_PROFILE

> TrueMoney Wallet Minimal Profile Creation — Direct parallel dispatch, Thai ID validation, subscriber ExtendedInfo writeback

---

## §1 — Overview & Purpose

**TMN_CREATE_WALLET_MINIMAL_PROFILE** creates a minimal TrueMoney wallet profile for each prepaid subscriber. It sends one `CreateWalletMinimalProfile` request per subscriber (ParentOU and ChildOU) in parallel via direct dispatch. The payload carries the subscriber's MSISDN and, conditionally, their Thai national ID number — but only if the ID passes a BRMS validity check (`IsValidThaiIDCheck`).

The response RF is the most complex in this journey: beyond the standard fan-in, it locates each responding subscriber by RefID match and writes **three SubscriberExtendedInfo entries** back onto the subscriber concept — including `AUTO_CLOSELOOP="Y"` which signals downstream error handling that the activity has been attempted, and `IGNORED_ERR_MSG` which explicitly labels the wallet creation error as intentionally suppressed. This design means TMN wallet creation failures do not block the order.

> **Intentional error suppression:** The `IGNORED_ERR_MSG` key (always written: `"TMN:" + message`) and `AUTO_CLOSELOOP="Y"` pattern indicate TMN wallet creation is a best-effort step — failures are captured for audit but do not stop the order flow. This is distinct from mandatory steps like CCP_ACTIVATE_SIM or SBM_ADD_3GPREPAID.

| Attribute | Value |
|-----------|-------|
| Rule file | Request_TMN_CREATE_WALLET_MINIMAL_PROFILE.rule |
| Response rulefunction | Response_TMN_CREATE_WALLET_MINIMAL_PROFILE.rulefunction |
| Priority | 5 |
| Backend system | TMN (TrueMoney) via ESB (`CreateWalletMinimalProfile`) |
| Request event type | `Events.OMConsumers.OMXFM.Request.TMN_CREATE_WALLET_MINIMAL_PROFILE` |
| Response event type | `Events.OMConsumers.OMXFM.Response.TMN_CREATE_WALLET_MINIMAL_PROFILE` |
| Response concept | `Concepts.FM.Base.ResponseBase` + 3× `SubscriberExtendedInfo` |
| Payload schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/TMN/CreateWalletMinimalProfile.xsd` (ns11) |
| Dispatch scope | Per Subscriber — both ParentOU and ChildOU |
| Dispatch pattern | Direct parallel (sendEventImmediate per subscriber, RequestCount++) |
| refId for idempotency | `pSubRefId` / `cSubRefId` (subscriber RefId) |
| Thai ID validation | `BRMS.IsBlankOrStringNull` + `BRMS.IsValidThaiIDCheck` before dispatch; gates `ns11:thai_id` |
| Credential headers | `IsEnableUserPass` global var gates UserName/PassWord in JMS headers |
| Response writeback | 3× SubscriberExtendedInfo per subscriber: TMN_MESSAGE, IGNORED_ERR_MSG, AUTO_CLOSELOOP |
| Request audit | Unconditional (no AllowWriteLog gate) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM priority |
| forwardChain | true | Enables forward chaining |
| Rule type | Direct parallel dispatch | NOT IntraActivitySequencing — immediate sendEventImmediate per subscriber |
| Resubmit | Yes | Idempotency check; RequestCount not incremented on resubmit |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order; Identification read for Thai ID validation; Subscriber ExtendedInfo[] written by response RF |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — RequestCount tracker, Response[] for idempotency fan-in |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId matches |
| 2 | `orderCurrentActivity.ActivityID == "TMN_CREATE_WALLET_MINIMAL_PROFILE"` | Constrains to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "TMN_CREATE_WALLET_MINIMAL_PROFILE"` | Double-check via NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity ready |

---

## §5 — Execution Flow Diagram

1. **Check resubmit flag** → `isActResub = RequestCount > 0 && IsOrderResubmitted`
2. **Get activity config** → `Instance.getByExtIdByUri` → `nextAct.PreExecCheck`
3. **Extract Identification** → null-guard: `if(CustomerGeneralInfo != null): identification = CustomerGeneralInfo.Identification`
4. **ParentOU subscriber loop** — for each ParentOU → Subscriber:
   - `pSubRefId = psub.RefId` — idempotency key
   - **Idempotency check**: scan `Response[]` for `ReferenceId == pSubRefId && CompletionStatus == 2`
   - **PreExecCheck**: `GetXMLForSubscriber(orderRequest, pSubRefId)` → XPath check
   - **Thai ID validation**: `validThaiID = !IsBlankOrStringNull(identification) && IsValidThaiIDCheck(identification)`
   - Build XSLT event → **`sendEventImmediate`**
   - `isSkipped = false`; if not resubmit: `RequestCount++`
   - Request audit — **unconditional** (no AllowWriteLog gate)
5. **ChildOU subscriber loop** — same pattern (PreExecCheck via `GetXMLForSubscriberInChildOU`)
6. **Final status**: if any sent → `GetActivityStatusString("1", false)` + `SendDataToDB`; else → `SkipActivity("4")`

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
try {
    // Pre-extract Identification (null-guarded)
    String identification = "";
    if(CustomerGeneralInfo != null) {
        identification = CustomerGeneralInfo.Identification;
    }

    // ParentOU Subscriber loop
    for(int p=0; p<pOuLen; p++) {
        for(int ps=0; ps<pSubLen; ps++) {
            String pSubRefId = psub.RefId;
            // Idempotency check: CompletionStatus==2 + ReferenceId==pSubRefId
            if(!reqSuccess) {
                // PreExecCheck via GetXMLForSubscriber
                if(String.equals(chkRes, "true")) {
                    boolean validThaiID =
                        !BRMS.IsBlankOrStringNull(identification)
                        && BRMS.IsValidThaiIDCheck(identification);

                    // [XSLT: CreateWalletMinimalProfileRequest — see §9]
                    // Params: orderRequest, pSubRefId, globalVariables, psub, validThaiID
                    Event.Ext.sendEventImmediate(reqEvent);
                    isSkipped = false;
                    if(!isActResub) orderCurrentActivity.RequestCount++;
                    /* UNCONDITIONAL audit log (no AllowWriteLog check) */
                }
            }
        }
    }
    // ChildOU Subscriber loop (GetXMLForSubscriberInChildOU, same XSLT variant)

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

### §7.1 — Thai ID Pre-Validation (BE code)

```java
String identification = "";
if(orderRequest.OrderData.Customer.CustomerGeneralInfo != null) {
    identification = CustomerGeneralInfo.Identification;
}
// Per subscriber (inside the subscriber loop):
boolean validThaiID =
    !RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(identification)
    && RuleFunctions.Helpers.BRMS.IsValidThaiIDCheck(identification);
```

`validThaiID` is then passed to the XSLT as a parameter. Inside the XSLT: `xsl:if test="$validThaiID='true'"` controls emission of `ns11:thai_id`.

> **BRMS validation inline:** Unlike CRM_UPSERT_CUSTOMER_ACCOUNT which used activity parameters, this FM uses two BRMS helper functions to validate the Thai ID format at runtime. If the ID is blank or fails the Luhn/format check, the `ns11:thai_id` field is simply omitted — the wallet is created with MSISDN only.

### §7.2 — Credential Gating (Global Variable)

| Global variable | Effect when 'true' |
|----------------|-------------------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Emits `UserName` from `OrderData/User` and `PassWord` from `OrderData/Password` in JMS headers |

### §7.3 — Redundant Namespace Declarations

The XSLT declares 12 namespace prefixes (ns, ns1–ns11, ns9, xsd, tib) but only `ns11` is used in the actual payload output. All others are declared in `exclude-result-prefixes` and appear to be copy-paste residue from a larger shared XSLT template.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

No order type conditional logic in this FM. The same request is sent for all order types (subject to PreExecCheck gate).

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.TMN_CREATE_WALLET_MINIMAL_PROFILE` | TrueMoney wallet creation per subscriber (direct parallel) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit (unconditional — no AllowWriteLog gate) |

### §8.3 — Backend API Details

| System | Operation | Protocol | Schema |
|--------|-----------|----------|--------|
| TMN | CreateWalletMinimalProfile | JMS async (direct parallel) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/TMN/CreateWalletMinimalProfile.xsd` |

### §8.4 — BE Working Memory Dependencies

| Concept path | Access | Purpose |
|-------------|--------|---------|
| `Customer.CustomerGeneralInfo.Identification` | Read | Thai ID — validated via BRMS, conditionally included in payload |
| `ParentOU[*].Subscriber[*].RefId` | Read | pSubRefId — idempotency key + JMS RefID header |
| `ParentOU[*].Subscriber[*].MSISDN` | Read | TMN `ns11:mobile_no` field |
| `ParentOU[*].Subscriber[*].ExtendedInfo[]` | **WRITE** | Response RF appends 3× SubscriberExtendedInfo per matched subscriber |
| `ChildOU[*].Subscriber[*].RefId` | Read | cSubRefId — idempotency key + JMS RefID header |
| `ChildOU[*].Subscriber[*].MSISDN` | Read | TMN `ns11:mobile_no` field |
| `ChildOU[*].Subscriber[*].ExtendedInfo[]` | **WRITE** | Response RF appends 3× SubscriberExtendedInfo per matched subscriber |
| `orderRequest.OrderData.User` | Read | UserName JMS header (IsEnableUserPass-gated) |
| `orderRequest.OrderData.Password` | Read | PassWord JMS header (IsEnableUserPass-gated) |
| `orderCurrentActivity.RequestCount` | Read/Write | Incremented per subscriber dispatched (non-resubmit) |
| `orderCurrentActivity.Response[]` | Read | Idempotency check per subscriber |

### §8.5 — Global Variable Dependencies

| Global variable path | Used for |
|---------------------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Gates UserName/PassWord emission in JMS headers |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameters

| Variant | Param | Source |
|---------|-------|--------|
| ParentOU | `$orderRequest` | orderRequest concept |
| ParentOU | `$pSubRefId` | psub.RefId |
| ParentOU | `$globalVariables` | BE global variables (for IsEnableUserPass) |
| ParentOU | `$psub` | ParentOU Subscriber concept |
| ParentOU | `$validThaiID` | Boolean string ("true"/"false") from BRMS validation |
| ChildOU | `$orderRequest` | orderRequest concept |
| ChildOU | `$cSubRefId` | csub.RefId |
| ChildOU | `$globalVariables` | BE global variables |
| ChildOU | `$csub` | ChildOU Subscriber concept |
| ChildOU | `$validThaiID` | Boolean string from BRMS validation |

### §9.2 — Event Container

No explicit `extId` attribute set on the event element (unique among all documented FMs in this journey).

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition | Notes |
|-------|--------|-----------|-------|
| `JMSPriority` | `$orderRequest/OrderPriority` | `xsl:if test="$orderRequest/OrderPriority"` | Conditional — different from most FMs |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | `xsl:if test="$orderRequest/OrderData/OMXTrackingId"` | Conditional |
| `OrderID` | `$orderRequest/OrderData/OrderID` | `xsl:if test="$orderRequest/OrderData/OrderID"` | Conditional |
| `RefID` | `$pSubRefId` / `$cSubRefId` | **Always** (no xsl:if) | Only header emitted unconditionally |
| `UserName` | `$orderRequest/OrderData/User` | `IsEnableUserPass='true' AND User exists` | Credential gated |
| `PassWord` | `$orderRequest/OrderData/Password` | `IsEnableUserPass='true' AND Password exists` | Credential gated |
| `OrderType` | `$orderRequest/OrderData/OrderType` | `xsl:if test="$orderRequest/OrderData/OrderType"` | Conditional |

> **Conditional JMS headers:** This FM wraps JMSPriority, JMSCorrelationID, OrderID, and OrderType in `xsl:if` tests, unlike most other FMs that emit them unconditionally.

### §9.4 — Payload Root Element

`ns11:CreateWalletMinimalProfileRequest` — namespace: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/TMN/CreateWalletMinimalProfile.xsd`

### §9.5 — Payload Fields

| Element | Source | Condition | Notes |
|---------|--------|-----------|-------|
| `ns11:mobile_no` | `$psub/MSISDN` or `$csub/MSISDN` | `xsl:if test="$psub/MSISDN"` | Subscriber's MSISDN — wallet identifier |
| `ns11:thai_id` | `Customer/CustomerGeneralInfo/Identification` | `$validThaiID="true" AND Identification exists` | Thai national ID — only included if BRMS validation passes |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event (no @extId attribute set)
    ├── JMSPriority        ← $orderRequest/OrderPriority              [Conditional: if OrderPriority exists]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId    [Conditional: if OMXTrackingId exists]
    ├── OrderID            ← $orderRequest/OrderData/OrderID          [Conditional: if OrderID exists]
    ├── RefID              ← $pSubRefId / $cSubRefId                  [Always]
    ├── UserName           ← $orderRequest/OrderData/User             [Conditional: IsEnableUserPass='true' AND User exists]
    ├── PassWord           ← $orderRequest/OrderData/Password         [Conditional: IsEnableUserPass='true' AND Password exists]
    ├── OrderType          ← $orderRequest/OrderData/OrderType        [Conditional: if OrderType exists]
    └── payload
        └── ns11:CreateWalletMinimalProfileRequest
            ├── ns11:mobile_no  ← $psub/MSISDN or $csub/MSISDN      [Conditional: if MSISDN exists]
            └── ns11:thai_id    ← CustomerGeneralInfo/Identification  [Conditional: $validThaiID="true" AND Identification non-empty] [BRMS-validated]
```

---

## §11 — Audit Logging

| Event | Gate | Key fields |
|-------|------|-----------|
| Request audit (per subscriber) | **Unconditional** (no AllowWriteLog) | `OPERATION_NAME="TMN_CREATE_WALLET_MINIMAL_PROFILE"`, `AUDIT_TRACE="Request Sent for TMN_CREATE_WALLET_MINIMAL_PROFILE"` |
| Response audit | **Unconditional** (no AllowWriteLog) | `OPERATION_NAME="TMN_CREATE_WALLET_MINIMAL_PROFILE"`, `AUDIT_TRACE="Response received for TMN_CREATE_WALLET_MINIMAL_PROFILE"` ✓ correct |

> Both request and response audits are unconditional — unlike GPS (request gated, response ungated) and CRM (both gated). TMN always logs regardless of order type.

---

## §12 — Activity Status Management

| Condition | Action | Status |
|-----------|--------|--------|
| At least one subscriber dispatched | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" = PROCESSING |
| No subscribers pass checks | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" = SKIPPED |

---

## §13 — Exception / Error Handling

**Request rule:** Standard `catch(Exception ae) → HandleActivityException`.

**Response RF:** No try/catch — bare body. An exception propagates to the BE rule engine. Note that the response RF modifies subscriber concepts (writes ExtendedInfo entries) without exception protection.

> **Business-level error suppression:** The `IGNORED_ERR_MSG` and `AUTO_CLOSELOOP` keys written in the response RF are the error handling mechanism at the business level. TMN wallet failures are expected and suppressed — this FM represents a best-effort enrichment step, not a critical provisioning gate.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Helpers.GetXMLForSubscriber(orderRequest, refId)` | Builds PreExecCheck XML for a ParentOU subscriber |
| `Helpers.GetXMLForSubscriberInChildOU(orderRequest, subRefId, ouRefId)` | Builds PreExecCheck XML for a ChildOU subscriber |
| `Helpers.BRMS.IsBlankOrStringNull(str)` | Returns true if the string is null or whitespace-only |
| `Helpers.BRMS.IsValidThaiIDCheck(identification)` | Validates Thai national ID format/checksum via BRMS |
| `Helpers.GetActivityStatusString(code, flag)` | Status code translation |
| `Helpers.SendDataToDB(orderRequest)` | Persist order state |
| `Helpers.SkipActivity(orderRequest, activity, code)` | Mark activity skipped |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |

---

## §15 — Function Dependency Tree

```text
Request_TMN_CREATE_WALLET_MINIMAL_PROFILE (rule)
├── Instance.getByExtIdByUri()
├── Helpers.GetXMLForSubscriber()                  [PreExecCheck, ParentOU subscriber]
├── Helpers.GetXMLForSubscriberInChildOU()         [PreExecCheck, ChildOU subscriber]
├── XPath.execute()                                [PreExecCheck evaluation]
├── Helpers.BRMS.IsBlankOrStringNull(identification) [Thai ID blank check]
├── Helpers.BRMS.IsValidThaiIDCheck(identification)  [Thai ID Luhn/format validation]
├── Event.createEvent()                            [TMN CreateWalletMinimalProfileRequest XSLT]
│   ├── ParentOU variant: $pSubRefId, $psub, $validThaiID
│   └── ChildOU variant:  $cSubRefId, $csub, $validThaiID
├── Event.Ext.sendEventImmediate()                 [direct per-subscriber dispatch]
├── [if !isActResub] orderCurrentActivity.RequestCount++
├── System.nanoTime()
├── Event.createEvent()                            [Logger XSLT — unconditional audit]
├── Event.Ext.sendEventImmediate()                 [request audit]
├── Helpers.GetActivityStatusString()
├── Helpers.SendDataToDB()
├── Helpers.SkipActivity()
└── Helpers.HandleActivityException()

Response_TMN_CREATE_WALLET_MINIMAL_PROFILE (rulefunction)
├── Instance.createInstance()                      [ResponseBase XSLT — extId generated INSIDE XSLT]
├── currActivity.Response[] ← activityRes
│
├── ParentOU/ChildOU loop — match subscriber by eventResponse.RefID:
│   ├── [if psub.RefId == eventResponse.RefID] → process this subscriber
│   ├── Instance.createInstance()                  [SubscriberExtendedInfo: TMN_MESSAGE]
│   │   └── Name="TMN_MESSAGE", Value=ns:message  (conditional Value)
│   ├── psub.ExtendedInfo[] ← subExt
│   ├── Instance.createInstance()                  [SubscriberExtendedInfo: IGNORED_ERR_MSG]
│   │   └── Name="IGNORED_ERR_MSG", Value="TMN:"+ns:message  (always)
│   ├── psub.ExtendedInfo[] ← ignoredErrMsg
│   ├── Instance.createInstance()                  [SubscriberExtendedInfo: AUTO_CLOSELOOP]
│   │   └── Name="AUTO_CLOSELOOP", Value="Y"  (always static)
│   └── psub.ExtendedInfo[] ← extAutoCloseLoop
│
├── System.nanoTime()
├── Event.createEvent()                            [Logger XSLT — unconditional, correct AUDIT_TRACE]
├── Event.Ext.sendEventImmediate()                 [response audit]
├── XPath.evalAsInt()                              [count(Response[ResponseCode ends with "000"])]
└── [currActivity.RequestCount == successResponseCount]
    → return "true"  (all subscribers returned success response)
    → return "false" (still waiting)
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | Both | Customer.CustomerGeneralInfo.Identification; ParentOU[]/ChildOU[]/Subscriber[]; OrderData.User/Password |
| `Concepts.OM.ProcessConfig.Activity` | Both | ActivityID, Status, RequestCount (written), Response[] (read) |
| `Concepts.FM.Base.ResponseBase` | Response RF | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId (sub.RefId) |
| `Concepts.OrderRequest.OrderElements.Subscriber` | Both | RefId (idempotency + matching), MSISDN (ns11:mobile_no); ExtendedInfo[] written by response RF |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` | Response RF | Name (key), Value — 3 entries written per matched subscriber: TMN_MESSAGE, IGNORED_ERR_MSG, AUTO_CLOSELOOP |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|------------|
| R1 | For each subscriber (ParentOU and ChildOU), call TMN CreateWalletMinimalProfile with MSISDN and optionally the Thai national ID |
| R2 | Include Thai national ID only if BRMS validation passes: non-blank + IsValidThaiIDCheck |
| R3 | Include UserName/PassWord in JMS headers only if IsEnableUserPass global variable is 'true' |
| R4 | Per-subscriber idempotency: skip if CompletionStatus=2 and ReferenceId=subscriber RefId in Response[] |
| R5 | RequestCount incremented per subscriber dispatched (not on resubmit) |
| R6 | For each response, locate the matching subscriber by RefID and write back 3 ExtendedInfo entries: TMN_MESSAGE, IGNORED_ERR_MSG, AUTO_CLOSELOOP="Y" |
| R7 | Fan-in: activity complete when all dispatched subscribers have a response with ResponseCode ending in "000" |
| R8 | TMN wallet creation is best-effort: the IGNORED_ERR_MSG and AUTO_CLOSELOOP keys signal downstream handlers that errors are suppressed |
| R9 | Both request and response audits are unconditional (no AllowWriteLog gate) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Success-only fan-in deadlock:** Fan-in requires ALL responses to have ResponseCode ending in "000". If TMN returns a non-"000" code (even for intentionally suppressed errors), `successResponseCount` never equals `RequestCount` — activity waits indefinitely. The error-suppression intent (IGNORED_ERR_MSG) conflicts with the fan-in logic. | [HIGH] | Verify TMN always returns a "000" code even for "soft" errors, or change fan-in to use CompletionStatus-based logic; alternatively use total response count instead of success count |
| **IGNORED_ERR_MSG always written with empty prefix:** `concat("TMN:", message)` is always written — even if `ns:message` is null/empty, the subscriber gets an entry with Value="TMN:". Downstream handlers reading this key may misinterpret an empty message as an error. | [MEDIUM] | Add conditional: only write IGNORED_ERR_MSG if message is non-empty; or document that "TMN:" alone means no error message returned |
| **Conditional JMS standard headers:** JMSPriority, JMSCorrelationID, OrderID, OrderType are all wrapped in xsl:if. If the orderRequest is missing any of these, the JMS message header will be absent. Most ESB consumers expect these headers. | [MEDIUM] | Remove the xsl:if wrappers from standard JMS headers (matching pattern from other FMs). |
| **10 unused namespace declarations:** The XSLT declares ns, ns1–ns4, ns5–ns10, ns9, tib, xsd — only ns11 is used in payload output. Dead code bloats the XSLT. | [LOW] | Remove unused namespace declarations; retain only ns11 and OMXUtils |
| **No exception handling in response RF:** The subscriber loop and ExtendedInfo writes run without try/catch. A BE exception during writeback could leave ExtendedInfo partially written. | [LOW] | Add try/catch around the writeback loop in the response RF |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_TMN_CREATE_WALLET_MINIMAL_PROFILE {
    attribute { priority = 5; forwardChain = true; }
    then {
        boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
        try {
            // Pre-extract Identification (null-guard on CustomerGeneralInfo)
            String identification = "";
            if(CustomerGeneralInfo != null) identification = CustomerGeneralInfo.Identification;

            // ParentOU Subscriber loop
            for(int p=0; p<pOuLen; p++) {
                for(int ps=0; ps<pSubLen; ps++) {
                    String pSubRefId = psub.RefId;
                    // Idempotency check (CompletionStatus==2 + ReferenceId==pSubRefId)
                    if(!reqSuccess) {
                        // PreExecCheck via GetXMLForSubscriber
                        if(String.equals(chkRes, "true")) {
                            boolean validThaiID =
                                !BRMS.IsBlankOrStringNull(identification)
                                && BRMS.IsValidThaiIDCheck(identification);

                            // [XSLT: CreateWalletMinimalProfileRequest — see §9]
                            // Params: orderRequest, pSubRefId, globalVariables, psub, validThaiID
                            // ns11:mobile_no=psub/MSISDN (cond); ns11:thai_id (cond: validThaiID=true)
                            // JMS headers: conditional (xsl:if on each); RefID always; credentials: IsEnableUserPass-gated
                            Event.Ext.sendEventImmediate(reqEvent);
                            isSkipped = false;
                            if(!isActResub) orderCurrentActivity.RequestCount++;
                            /* UNCONDITIONAL audit log (no AllowWriteLog check) */
                        }
                    }
                }
            }
            // ChildOU Subscriber loop (GetXMLForSubscriberInChildOU, same XSLT variant)

            if(!isSkipped) {
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                SendDataToDB(orderRequest);
            } else {
                SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch(Exception ae) { HandleActivityException(...); }
    }
}
```

---

## §19 — Response Message Rule (Response_TMN_CREATE_WALLET_MINIMAL_PROFILE)

### §19.1 — Overview

The most complex response RF in the PREPAID_REGISTRATION journey. After building and appending the standard `ResponseBase`, it iterates all subscribers (ParentOU and ChildOU) to find the one matching `eventResponse.RefID`. For the matched subscriber, it writes **three SubscriberExtendedInfo entries** back onto the subscriber concept, then logs unconditionally and evaluates fan-in.

No BE-side `extId` variable — the ResponseBase XSLT generates its own tracking ID internally via `OMXUtils:generateTrackingID()` in the XSLT template, not from a BE parameter.

> **Response AUDIT_TRACE is correct:** `"Response received for TMN_CREATE_WALLET_MINIMAL_PROFILE"` — no copy-paste bug (unlike GPS_INSERT_INFORMATION).

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context; subscriber ExtendedInfo[] written back to matching subscribers |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.TMN_CREATE_WALLET_MINIMAL_PROFILE` | TMN response; RefID used to find matching subscriber; `ns:status/ns:message` written to ExtendedInfo |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity; `RequestCount` read for fan-in comparison |

### §19.3 — ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId         ← OMXUtils:generateTrackingID() (inside XSLT — no BE-side extId param)   [Always]
    ├── ResponseCode   ← $eventResponse/ResponseCode                                             [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg                                             [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus                                       [Conditional]
    └── ReferenceId    ← $eventResponse/RefID                                                    [Conditional]
```

### §19.4 — Subscriber ExtendedInfo Writeback (3 entries per matched subscriber)

After building ResponseBase, the RF iterates all subscribers to find the one matching `eventResponse.RefID`. For the match, three `SubscriberExtendedInfo` objects are created and appended to `sub.ExtendedInfo[]`:

```text
SubscriberExtendedInfo #1 — TMN_MESSAGE
├── Name   ← "TMN_MESSAGE"                                                    [Always]
└── Value  ← ns:CreateWalletMinimalProfileResponse/ns:status/ns:message       [Conditional: if ns:message exists]

SubscriberExtendedInfo #2 — IGNORED_ERR_MSG
├── Name   ← "IGNORED_ERR_MSG"                                                [Always]
└── Value  ← concat("TMN:", ns:status/ns:message)                             [Always — even if message empty → "TMN:"]

SubscriberExtendedInfo #3 — AUTO_CLOSELOOP
├── Name   ← "AUTO_CLOSELOOP"                                                 [Always]
└── Value  ← "Y"                                                              [Always hardcoded — signals downstream: wallet creation attempted]
```

### §19.5 — Response Completion Logic

| Step | Logic |
|------|-------|
| Success count | `XPath.evalAsInt("count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = '000'])")` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Return "true" | All dispatched subscribers returned a "000"-suffix ResponseCode |
| Return "false" | Still waiting for more subscribers to respond |

### §19.6 — Response Audit Logging

| Field | Value |
|-------|-------|
| `OPERATION_NAME` | `"TMN_CREATE_WALLET_MINIMAL_PROFILE"` ✓ |
| `AUDIT_TRACE` | `"Response received for TMN_CREATE_WALLET_MINIMAL_PROFILE"` ✓ correct (no copy-paste bug) |
| Gate | Unconditional (no AllowWriteLog) — consistent with request audit |
| `PROCESS_ID` | `concat($pid, "_RES")` |
| `payload` | Full `$eventResponse` copy, gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
