# Request_GET_PROFILE_FROM_CCP

> FM Logic Documentation — CCP User Profile Query & Dynamic SubscriberOffers Enrichment (Data Pipeline for CCP_REMOVE_OFFER)

**Rule:** `Rules.OMConsumers.OMXFM.Request.Request_GET_PROFILE_FROM_CCP`
**Priority:** 5 | **Backend:** CCP | **Pattern:** Parallel per-Subscriber dispatch

---

## §1 — Overview & Purpose

**GET_PROFILE_FROM_CCP** queries CCP for each subscriber's current price plan profile, then *enriches the order working memory* by dynamically appending new `SubscriberOffers` entries for any active grading-type price plans found. These dynamically-added offers are then consumed by the subsequent **CCP_REMOVE_OFFER** activity — making this FM a *data pipeline step*, not just a lookup.

The response RF filters CCP's `PricePlanDtoList` for plans with names starting with `IPP_000O0_00_GRADING`. For each such plan found, it creates a `SubscriberOffers` concept (Action=Remove, FE_OR_CCBS=CCP) and appends it to the subscriber — effectively "staging" the grading offers for removal in the next activity.

> **Schema / Name mismatch:** Despite the FM name saying `GET_PROFILE_FROM_CCP`, the request payload schema is `ns:GetPrepaidCreditInfoRequest` and CCP's response is `queryUserProfileResponse`. Debug comments in both files reference the old name `CCP_GET_PREPAID_CREDIT_INFO`. The FM was renamed without updating the payload schema namespaces. Functionally correct.

| Attribute | Value |
|-----------|-------|
| Rule file | `Request_GET_PROFILE_FROM_CCP.rule` |
| Response rulefunction | `Response_GET_PROFILE_FROM_CCP.rulefunction` |
| Priority | 5 |
| Backend system | CCP |
| Request event type | `Events.OMConsumers.OMXFM.Request.GET_PROFILE_FROM_CCP` |
| Request payload schema | `ns: http://services.omx.truecorp.co.th/FM/GetPrepaidCreditInfoRequest` |
| Response event type | `Events.OMConsumers.OMXFM.Response.GET_PROFILE_FROM_CCP` |
| Response payload namespace | `xsd2: http://thaitrue.customization.ws.bss.zsmart.ztesoft.com` |
| Response concept | `Concepts.FM.Base.ResponseBase` (standard) |
| Dispatch scope | Per Subscriber — ParentOU and ChildOU (dual nested loop: OU → Subscriber) |
| Dispatch pattern | Parallel direct dispatch (`sendEventImmediate`); fan-in: `RequestCount == Response@length` |
| Idempotency key | `sub.RefId` (per subscriber) |
| Response extId format | `"GPCIR:" + JMSCorrelationID + ":" + RefID` |
| Request audit | Conditional: `AllowWriteLog(OrderType)` |
| Response audit | Conditional: `AllowWriteLog(OrderType)` |
| Side effect | Appends `SubscriberOffers` concepts to subscriber working memory (CCP_REMOVE_OFFER pipeline) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM priority |
| forwardChain | true | Standard |
| Rule type | Parallel direct dispatch | sendEventImmediate per subscriber; fan-in: RequestCount == Response@length |
| Resubmit | Yes (guard) | isActResub flag gates RequestCount increment; no PurgePendingRequests needed |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order; ParentOU/ChildOU/Subscriber iteration; Channel for payload; OrderType for audit gate |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — RequestCount, Response[] for idempotency and fan-in; PreExecCheck XML |
| `nextAct` | `Concepts.OM.ProcessConfig.Activity` | Loaded by extId to access PreExecCheck expression |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId matches |
| 2 | `orderCurrentActivity.ActivityID == "GET_PROFILE_FROM_CCP"` | Constrains to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "GET_PROFILE_FROM_CCP"` | Double-check via NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity ready to process |

---

## §5 — Execution Flow Diagram

1. **Init** → `isActResub = RequestCount > 0 && IsOrderResubmitted`; load `nextAct` by extId; `isSkipped = true`
2. **ParentOU loop** (OU[i] → Subscriber[j]): idempotency check → PreExecCheck → dispatch `GET_PROFILE_FROM_CCP` event (params: $orderRequest, $i, $j) → conditional audit → increment `RequestCount` → `isSkipped = false`
3. **ChildOU loop** (OU[i] → ChildOU[p] → Subscriber[q]) — same pattern with `GetXMLForSubscriberInChildOU`
4. If any dispatched → `GetActivityStatusString("1", false)` + `SendDataToDB`; else → `SkipActivity("4")`

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
try {
    Activity nextAct = Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
    int iPOULen = ParentOU@length;
    boolean isSkipped = true;

    for(int i = 0; i < iPOULen; i++) {
        for(int j = 0; j < iSubscriberLen; j++) {
            String refId = ParentOU[i].Subscriber[j].RefId;
            // Idempotency check on Response[]
            if(!reqSuccess) {
                String chkRes = "true";
                if(nextAct.PreExecCheck.length > 0) {
                    String sXML = GetXMLForSubscriber(orderRequest, refId);
                    chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=...");
                }
                if(chkRes == "true") {
                    /* GET_PROFILE_FROM_CCP XSLT (params: $orderRequest, $i, $j) — see §9 */
                    Event.Ext.sendEventImmediate(reqEvent);
                    if(AllowWriteLog(OrderType)) { /* Logger XSLT audit */ }
                    if(!isActResub) orderCurrentActivity.RequestCount++;
                    isSkipped = false;
                }
            }
        }
        // ChildOU loop (GetXMLForSubscriberInChildOU, params: $i, $p, $q)
    }

    if(!isSkipped) {
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
    } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
} catch(Exception ae) { HandleActivityException(...); }
```

---

## §7 — Data Extraction & Pre-Processing

### §7.1 — Idempotency Check (per Subscriber)

Checks `Response[iResp].ReferenceId == refId && CompletionStatus == 2`. Key: `refId` = subscriber's RefId (per subscriber, not per offer).

### §7.2 — PreExecCheck (dynamic from Activity)

The PreExecCheck XPath expression is read from `nextAct.PreExecCheck` (from the ProcessConfig activity definition), not hardcoded. Helpers `GetXMLForSubscriber` (ParentOU) or `GetXMLForSubscriberInChildOU` (ChildOU) build the XML fragment fed to `XPath.execute`. Empty PreExecCheck = all subscribers pass.

### §7.3 — XSLT Param Design: Index vs. Value

Unlike most other FMs that pass extracted string values, this FM passes subscriber **array indices** (`$i`, `$j`, `$p`, `$q`) as XSLT parameters. The XSLT navigates using `ParentOU[$i+1]/Subscriber[$j+1]` (1-indexed XPath from 0-indexed BE vars).

### §7.4 — Response: PricePlanDtoList Parsing

Reads `$eventResponse/payload/xsd2:queryUserProfileResponse/xsd2:queryUserProfileReturn/xsd2:PricePlanDtoList/xsd2:PricePlanDto` (namespace `xsd2=http://thaitrue.customization.ws.bss.zsmart.ztesoft.com`). Filters:

```java
if (String.startsWith(pp_name, "IPP_000O0_00_GRADING"))
```

Only grading-tier plans trigger SubscriberOffers creation.

### §7.5 — Response: Subscriber Concept Lookup

Dual-lookup pattern (handles both ParentOU and ChildOU subscribers):
1. Try `"SUB:" + OMXTrackingId + ":" + RefID` (ParentOU subscriber)
2. If null, try `"CSUB:" + OMXTrackingId + ":" + RefID` (ChildOU subscriber)

### §7.6 — Response: Dynamic SubscriberOffers Creation

For each matched grading plan, creates `Concepts.OrderRequest.OrderElements.SubscriberOffers`:

| Field | Value |
|-------|-------|
| `@extId` | `OMXUtils:generateTrackingID()` |
| `OfferName` | `$pp_name` (PricePlanName from CCP) |
| `Action` | `"Remove"` (static) |
| `ExtendedInfo/@extId` | `OMXUtils:generateTrackingID()` |
| `ExtendedInfo/Name` | `"FE_OR_CCBS"` (static) |
| `ExtendedInfo/Value` | `"CCP"` (static) |

Appended to `subscriber.SubscriberOffers[]`. The `FE_OR_CCBS=CCP` flag will be read by **CCP_REMOVE_OFFER**'s PreExecCheck.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Triggered for prepaid pack removal orders with subscribers who have active grading-type price plans in CCP. PreExecCheck loaded dynamically from ProcessConfig — no hardcoded order-type gate in the rule.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.GET_PROFILE_FROM_CCP` | CCP GetPrepaidCreditInfo query per subscriber (parallel) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit (conditional: AllowWriteLog) |

### §8.3 — Backend API Details

| System | Request Operation | Response Operation |
|--------|------------------|--------------------|
| CCP | `GetPrepaidCreditInfoRequest` (OMX FM schema) | `queryUserProfileResponse` / `queryUserProfileReturn` (ZSMART BSS schema) |

### §8.4 — BE Working Memory Dependencies

| Concept path | Access | Purpose |
|-------------|--------|---------|
| `ProcessFlow.NextActivityName` | Read | Load nextAct for PreExecCheck |
| `nextAct.PreExecCheck` | Read | Dynamic PreExecCheck XPath expression |
| `ParentOU[*].Subscriber[*].RefId` | Read | Idempotency key; XSLT RefID header |
| `ParentOU[*].Subscriber[*].MSISDN` | Read (via XSLT index) | ns:MSISDN in CCP request payload |
| `OrderData.Channel` | Read (via XSLT) | ns:OrderChannel in CCP request payload |
| `ChildOU[*].Subscriber[*].RefId/MSISDN` | Read | Same as ParentOU equivalents |
| `orderCurrentActivity.Response[]` | Read/Write | Idempotency; fan-in counting |
| `orderCurrentActivity.RequestCount` | Read/Write | Incremented per dispatched request (unless resubmit) |
| `subscriber.SubscriberOffers[]` | **Write** | Dynamically appended grading SubscriberOffers for CCP_REMOVE_OFFER pipeline |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameters

| Param | Source (ParentOU) | Source (ChildOU) |
|-------|------------------|-----------------|
| `$orderRequest` | orderRequest concept | orderRequest concept |
| `$i` | ParentOU index (0-based) | ParentOU index (0-based) |
| `$j` | Subscriber index within ParentOU (0-based) | – |
| `$p` | – | ChildOU index within ParentOU (0-based) |
| `$q` | – | Subscriber index within ChildOU (0-based) |

Note: XSLT uses 1-indexed XPath: `ParentOU[$i+1]/Subscriber[$j+1]`.

### §9.2 — Event Container

No extId attribute on the event container. Event type: `Events.OMConsumers.OMXFM.Request.GET_PROFILE_FROM_CCP`.

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | **Always (no xsl:if)** |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | **Always (no xsl:if)** |
| `OrderID` | `$orderRequest/OrderData/OrderID` | **Always (no xsl:if)** |
| `RefID` | `$orderRequest/OrderData/Customer/ParentOU[$i+1]/Subscriber[$j+1]/RefId` | **Always** |
| `OrderType` | `$orderRequest/OrderData/OrderType` | **Always (no xsl:if)** |

> All JMS headers are unconditional (no xsl:if anywhere). An empty OrderPriority would emit empty `<JMSPriority>` rather than omitting it.

### §9.4 — Payload Root

`ns:GetPrepaidCreditInfoRequest` (namespace: `http://services.omx.truecorp.co.th/FM/GetPrepaidCreditInfoRequest`)

### §9.5 — Payload Fields

| Element | Source | Condition | Notes |
|---------|--------|-----------|-------|
| `ns:MSISDN` | `$orderRequest/OrderData/Customer/ParentOU[$i+1]/Subscriber[$j+1]/MSISDN` | Always | ChildOU variant uses `ChildOU[$p+1]/Subscriber[$q+1]` |
| `ns:OrderChannel` | `$orderRequest/OrderData/Channel` | Always | Order channel (e.g., "web", "mobile") |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event  (no @extId)
    ├── JMSPriority         ← $orderRequest/OrderPriority                                           [Always (no xsl:if)]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId                                 [Always (no xsl:if)]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                                        [Always (no xsl:if)]
    ├── RefID               ← $orderRequest/OrderData/Customer/ParentOU[$i+1]/Subscriber[$j+1]/RefId [Always]
    ├── OrderType           ← $orderRequest/OrderData/OrderType                                      [Always (no xsl:if)]
    └── payload
        └── ns:GetPrepaidCreditInfoRequest
            ├── ns:MSISDN         ← .../ParentOU[$i+1]/Subscriber[$j+1]/MSISDN  [Always]
            └── ns:OrderChannel   ← $orderRequest/OrderData/Channel              [Always]
```

ChildOU variant: params change to ($orderRequest, $i, $p, $q); RefID/MSISDN paths use `ChildOU[$p+1]/Subscriber[$q+1]`. Payload structure identical.

Legend: `[Always]` = unconditional; no xsl:if used anywhere in this XSLT.

---

## §11 — Audit Logging

| Event | Gate | OPERATION_NAME | AUDIT_TRACE | Bug? |
|-------|------|---------------|-------------|------|
| Request audit | `AllowWriteLog(OrderType)` | `"GET_PROFILE_FROM_CCP"` ✓ | `"Request Sent for GET_PROFILE_FROM_CCP"` ✓ | None |
| Response audit | `AllowWriteLog(OrderType)` | `"GET_PROFILE_FROM_CCP"` ✓ | `"Response received for GET_PROFILE_FROM_CCP"` ✓ | None |

Both AUDIT_TRACE values are correct.

---

## §12 — Activity Status Management

| Condition | Action | Status |
|-----------|--------|--------|
| At least one subscriber dispatched | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" = PROCESSING |
| No subscribers pass checks | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" = SKIPPED |

---

## §13 — Exception / Error Handling

**Request rule:** Standard `catch(Exception ae) → HandleActivityException`.

**Response RF:** No try/catch. PricePlanDto parsing, subscriber lookup, and SubscriberOffers creation run without exception handling. A malformed CCP response or null subscriber would propagate uncaught.

> **[HIGH]** The response RF's processing loop has no try/catch. If CCP returns a malformed response or the subscriber concept is null, the exception propagates uncaught to the BE rule engine.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Helpers.GetXMLForSubscriber(orderRequest, refId)` | Builds PreExecCheck XML fragment for ParentOU subscriber |
| `Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` | Builds PreExecCheck XML fragment for ChildOU subscriber |
| `Helpers.AllowWriteLog(orderType)` | Determines whether request/response audit should be written for this order type |
| `Helpers.GetActivityStatusString(code, flag)` | Status code translation |
| `Helpers.SendDataToDB(orderRequest)` | Persist order state |
| `Helpers.SkipActivity(orderRequest, activity, code)` | Mark activity skipped |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |
| `OMXUtils.generateTrackingID()` | Generate unique extId for new SubscriberOffers and ExtendedInfo concepts in response RF |

---

## §15 — Function Dependency Tree

```text
Request_GET_PROFILE_FROM_CCP (rule)
├── Instance.getByExtIdByUri()               [load nextAct for PreExecCheck]
├── [ParentOU/ChildOU/Subscriber loops]
│   ├── [idempotency check on Response[]]
│   ├── Helpers.GetXMLForSubscriber()        [ParentOU PreExecCheck XML]
│   ├── Helpers.GetXMLForSubscriberInChildOU()  [ChildOU PreExecCheck XML]
│   ├── XPath.execute()                      [PreExecCheck evaluation]
│   ├── Event.createEvent()                  [GET_PROFILE_FROM_CCP XSLT — see §9]
│   ├── Event.Ext.sendEventImmediate()       [dispatch request]
│   ├── Helpers.AllowWriteLog()              [audit gate]
│   ├── System.nanoTime()                    [pid for audit]
│   ├── Event.createEvent()                  [Logger XSLT — conditional audit]
│   ├── Event.Ext.sendEventImmediate()       [request audit]
│   └── orderCurrentActivity.RequestCount++ [if not resubmit]
├── Helpers.GetActivityStatusString()
├── Helpers.SendDataToDB()
├── Helpers.SkipActivity()
└── Helpers.HandleActivityException()

Response_GET_PROFILE_FROM_CCP (rulefunction)
├── Instance.createInstance()                [ResponseBase XSLT — standard 4 fields]
├── currActivity.Response[] ← activityRes
├── Instance.getByExtIdByUri("SUB:...")      [subscriber lookup attempt 1: ParentOU]
├── Instance.getByExtIdByUri("CSUB:...")     [subscriber lookup attempt 2: ChildOU — if null]
├── XPath.evalAsInt()                        [count PricePlanDto in response payload]
├── [PricePlanDto loop]
│   ├── XPath.evalAsString()                 [read PricePlanName per PricePlanDto]
│   ├── String.startsWith(pp_name, "IPP_000O0_00_GRADING")  [grading filter]
│   └── Instance.createInstance()            [SubscriberOffers XSLT — OMXUtils:generateTrackingID×2]
│       subscriber.SubscriberOffers[] ← subscriberOfferConcept
├── Helpers.AllowWriteLog()                  [response audit gate]
├── System.nanoTime()                        [pid for audit]
├── Event.createEvent()                      [Logger XSLT — conditional response audit]
├── Event.Ext.sendEventImmediate()           [response audit]
└── return "true" / "false"                  [fan-in: RequestCount == Response@length]
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | Both | OrderData.Channel, ParentOU/ChildOU/Subscriber loops |
| `Concepts.OM.ProcessConfig.Activity` | Both | ActivityID, Status, PreExecCheck, RequestCount, Response[] (fan-in) |
| `Concepts.FM.Base.ResponseBase` | Response RF | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId — all conditional |
| `Concepts.OrderRequest.OrderElements.Subscriber` | Response RF | SubscriberOffers[] — written to with dynamically created grading offers |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Response RF (create) | OfferName (PricePlanName), Action ("Remove"), ExtendedInfo (FE_OR_CCBS="CCP") |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | For each subscriber (ParentOU + ChildOU), query CCP via GetPrepaidCreditInfoRequest with MSISDN and OrderChannel |
| R2 | Per-subscriber idempotency: skip if Response[].ReferenceId == sub.RefId and CompletionStatus == 2 |
| R3 | Dynamic PreExecCheck: read XPath expression from ProcessConfig Activity.PreExecCheck; evaluate against subscriber XML fragment |
| R4 | Parallel dispatch: sendEventImmediate per qualifying subscriber; RequestCount incremented per dispatch (not on resubmit) |
| R5 | Response: parse CCP's queryUserProfileResponse PricePlanDtoList; filter plans with name starting "IPP_000O0_00_GRADING" |
| R6 | For each matched grading plan: create SubscriberOffers concept (OfferName=PricePlanName, Action=Remove, FE_OR_CCBS=CCP) and append to subscriber.SubscriberOffers[] |
| R7 | Fan-in: return "true" when RequestCount == Response@length |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **No try/catch in response RF:** PricePlanDto parsing, subscriber lookup, and SubscriberOffers creation can all throw. A null subscriber or malformed CCP response would propagate uncaught, potentially corrupting BE state. | [HIGH] | Wrap the PricePlanDto processing loop in try/catch; add null-check logging for subscriber lookup failure |
| **Unconditional JMS headers:** All headers (JMSPriority, JMSCorrelationID, OrderID, OrderType) emitted without xsl:if guards. An empty OrderPriority emits empty `<JMSPriority>` which may cause downstream JMS issues. | [MEDIUM] | Add conditional guards consistent with other FMs |
| **Grading filter is a hardcoded string prefix:** `String.startsWith("IPP_000O0_00_GRADING")` — new grading plan codes with different prefixes won't be discovered. | [MEDIUM] | Externalize the grading prefix to a global variable or BRMS rule |
| **Schema/name mismatch:** FM named GET_PROFILE_FROM_CCP but uses GetPrepaidCreditInfoRequest schema. Debug comments reference old name CCP_GET_PREPAID_CREDIT_INFO. | [LOW] | Rename for consistency or update comments to reflect the current name |
| **XSLT index-based navigation:** Passing array indices ($i, $j, $p, $q) as XSLT params ties the XSLT to concept array ordering. If concept structure changes, XSLT breaks silently. | [MEDIUM] | Prefer passing extracted values (MSISDN, RefId) as XSLT params rather than array indices |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_GET_PROFILE_FROM_CCP {
    attribute { priority = 5; forwardChain = true; }
    then {
        boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
        try {
            Activity nextAct = Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
            int iPOULen = ParentOU@length;
            boolean isSkipped = true;

            for(int i = 0; i < iPOULen; i++) {
                for(int j = 0; j < iSubscriberLen; j++) {
                    String refId = ParentOU[i].Subscriber[j].RefId;
                    // Idempotency check on Response[]
                    if(!reqSuccess) {
                        String chkRes = "true";
                        if(nextAct.PreExecCheck.length > 0) {
                            String sXML = GetXMLForSubscriber(orderRequest, refId);
                            chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=...");
                        }
                        if(chkRes == "true") {
                            /* GET_PROFILE_FROM_CCP XSLT (params: $orderRequest, $i, $j) — see §9 */
                            Event.Ext.sendEventImmediate(reqEvent);
                            if(AllowWriteLog(OrderType)) { /* Logger XSLT audit */ }
                            if(!isActResub) orderCurrentActivity.RequestCount++;
                            isSkipped = false;
                        }
                    }
                }
                // ChildOU loop (GetXMLForSubscriberInChildOU, params: $i, $p, $q)
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

## §19 — Response Message Rule (Response_GET_PROFILE_FROM_CCP)

### §19.1 — Overview

The response RF is a **data enrichment step**, not just a response recorder. It: (1) records standard ResponseBase, (2) looks up the Subscriber concept, (3) parses CCP's PricePlanDtoList for grading plans, and (4) dynamically creates SubscriberOffers concepts for CCP_REMOVE_OFFER to consume.

**Event type consumed:** `Events.OMConsumers.OMXFM.Response.GET_PROFILE_FROM_CCP`

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context for subscriber lookup and audit |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.GET_PROFILE_FROM_CCP` | CCP response event; carries ResponseCode, RefID, JMSCorrelationID, queryUserProfileResponse payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity; Response[] written to; RequestCount for fan-in |
| `subscriber` | `Concepts.OrderRequest.OrderElements.Subscriber` | Resolved from working memory by extId; SubscriberOffers[] appended to |

### §19.3 — ResponseBase Construction

**extId:** `"GPCIR:" + eventResponse.JMSCorrelationID + ":" + eventResponse.RefID`

```text
createObject (Concepts.FM.Base.ResponseBase)
└── object
    ├── ResponseCode        ← $eventResponse/ResponseCode       [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg        [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus   [Conditional]
    └── ReferenceId         ← $eventResponse/RefID              [Conditional]
```

### §19.4 — Dynamic SubscriberOffers Creation (Grading Plans)

For each CCP PricePlanDto where `String.startsWith(PricePlanName, "IPP_000O0_00_GRADING")`:

```text
createObject (Concepts.OrderRequest.OrderElements.SubscriberOffers)
└── object
    ├── @extId          ← OMXUtils:generateTrackingID()  [Always]
    ├── OfferName       ← $pp_name (PricePlanName)       [Always]
    ├── Action          ← "Remove"                        [Always (static)]
    └── ExtendedInfo
        ├── @extId      ← OMXUtils:generateTrackingID()  [Always]
        ├── Name        ← "FE_OR_CCBS"                   [Always (static)]
        └── Value       ← "CCP"                          [Always (static)]
```

Appended: `subscriber.SubscriberOffers[subscriber.SubscriberOffers@length] = subscriberOfferConcept`

### §19.5 — Response Completion Logic

| Step | Logic |
|------|-------|
| Fan-in condition | `if(currActivity.RequestCount == currActivity.Response@length)` |
| Return "true" | All parallel requests have received a response — activity complete |
| Return "false" | Still waiting for responses from other subscribers |

### §19.6 — Response Audit Logging

| Field | Value |
|-------|-------|
| `OPERATION_NAME` | `"GET_PROFILE_FROM_CCP"` ✓ |
| `AUDIT_TRACE` | `"Response received for GET_PROFILE_FROM_CCP"` ✓ |
| Gate | `AllowWriteLog(OrderType)` — conditional |
| `PROCESS_ID` | `concat($pid, "_RES")` |
| `payload` | Full `$eventResponse` copy, gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
