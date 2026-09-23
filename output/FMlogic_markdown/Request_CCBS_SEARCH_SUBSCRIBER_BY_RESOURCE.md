# Request_CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE

> FM Logic Documentation — CCBS Subscriber Lookup by Resource (Direct Parallel Dispatch, ALT_CES routing, Data Pipeline — enriches Subscriber & PayChannelCategory)

---

## §1 — Overview & Purpose

**CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE** searches CCBS for subscriber data using a resource identifier (typically MSISDN). It is the **first step** in BN_CHANGE_PACKAGE, executed only when the subscriber does not yet have a SubscriberId in the order (PreExecCheck: MSISDN exists but no SubscriberId). It is a **data pipeline FM** — the response RF enriches working memory with the located subscriber's identity data and derives the account's payment channel category (POST/PRE).

Uses **direct parallel dispatch** — one JMS event per subscriber, sent immediately via `sendEventImmediate`. No IntraActivitySequencing queue. Fan-in is achieved in the response RF by comparing `RequestCount == successResponseCount` (count of responses with ResponseCode ending in "000").

Two dispatch variants exist: ParentOU subscriber (params $i/$j) and ChildOU subscriber (params $i/$x/$y). Both use the same event type but different index params — the XSLT resolves the 1-indexed XPath differently.

> **Key design notes:**
> - **ALT_CES routing:** Activity parameter `ALT_CES=Y` overrides CES from `ExtendedInfo[ALT_CES]`; otherwise uses `OrderData.CES`
> - **Resource type override:** `ns:parameterType` defaults to `'C'` (MSISDN/phone number class) but can be overridden via `PRIMARY_RESOURCE_TYPE` ExtendedInfo
> - **Resource value override:** Activity parameter `MSISDN` can redirect the lookup to a specific `ResourceInfo[ResourceName=$param]/ValuesArray` instead of the subscriber's MSISDN
> - **IsEnableUserPass:** Global variable gates emission of `UserName`/`PassWord` headers
> - **YesNoIndicator = 89:** Static — always 89

| Attribute | Value |
|-----------|-------|
| Rule file | `Request_CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE.rule` |
| Response rulefunction | `Response_CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE.rulefunction` |
| Priority | 5 |
| Backend system | CCBS `SearchSubscriberByResource` |
| Request event type | `Events.OMConsumers.OMXFM.Request.CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE` |
| Response event type | `Events.OMConsumers.OMXFM.Response.CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE` |
| Response concept | `Concepts.FM.Response.CCBS_SearchSubscriberByResource` (custom — has SubscriberSearchResultInfo[] array) |
| Payload schema | `ns: http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/SearchServices/Schema.xsd2` |
| Dispatch scope | Per Subscriber — ParentOU and ChildOU (dual nested loop) |
| Dispatch pattern | Direct parallel — `sendEventImmediate` per subscriber |
| Idempotency key | `subscriber.RefId` |
| Fan-in | `RequestCount == count(Response[tib:right(tib:trim(ResponseCode),3)="000"])` |
| Data pipeline output | sub.Status, sub.SubscriberId, sub.SubscriberType, account.PayChannelCategory |
| CES routing | ALT_CES param gate — activity param or OrderData.CES |
| Audit | Unconditional for both request and response (no AllowWriteLog gate) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM priority |
| forwardChain | true | Standard |
| Rule type | Direct parallel dispatch | sendEventImmediate per subscriber; fan-in via successResponseCount |
| Resubmit | Yes | PurgePendingRequestsBeforeResubmit called INSIDE try block (correct); idempotency via CompletionStatus=2 + RefId; RequestCount++ only if !isActResub |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order; ParentOU/ChildOU/Subscriber loops; CES, ExtendedInfo, OrderType for routing |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[] for idempotency & fan-in; RequestCount management; ALT_CES and MSISDN parameter reading |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId matches |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE"` | Constrains to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE"` | Double-check via NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity ready to process |

> **ProcessConfig PreExecCheck (step 1 gate):**
> `string-length(//Subscriber/MSISDN/text()) > 0 and not(exists(//Subscriber/SubscriberId))`
> Runs only when subscriber has MSISDN but not yet a SubscriberId — classic subscriber lookup scenario (MSISDN known, CCBS subscriber number unknown).

---

## §5 — Execution Flow Diagram

1. **Resubmit check** → `isActResub = RequestCount > 0 && IsOrderResubmitted`
2. **Load nextAct PreExecCheck**; read `ALT_CES` activity param; read `MSISDN` activity param
3. **ParentOU loop** (OU[i] → Subscriber[j]):
   - If isActResub → `PurgePendingRequestsBeforeResubmit` (inside try, correct)
   - `refId = subscriber.RefId`; PreExecCheck XPath evaluation
   - Idempotency: scan Response[] for `ReferenceId==refId && CompletionStatus==2`
   - Build event with XSLT (variant 1: $i, $j, $subscriber, $param); `sendEventImmediate`
   - If !isActResub → `RequestCount++`
   - Unconditional audit Logger event
4. **ChildOU loop** (OU[i] → ChildOU[x] → Subscriber[y]): same pattern with variant 2 XSLT ($i, $x, $y)
5. If !isSkipped → `GetActivityStatusString("1", false)` + `SendDataToDB`; else `SkipActivity("4")`

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
try {
    Activity nextAct = Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
    if(isActResub) PurgePendingRequestsBeforeResubmit(orderCurrentActivity); // INSIDE try — correct

    String altParam = GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES");
    String param    = GetActivityParamValueFromKey(orderCurrentActivity, "MSISDN");
    String chkXPath = nextAct.PreExecCheck;
    boolean isSkipped = true;

    // ParentOU loop
    for(int i=0; i<iPOULen; i++) {
        for(int j=0; j<iSubsLen; j++) {
            Subscriber subscriber = ParentOU[i].Subscriber[j];
            String refId = subscriber.RefId;
            chkRes = PreExecCheck eval via GetXMLForSubscriber(orderRequest, refId);
            if(chkRes=="true") {
                // idempotency check on Response[]
                if(!reqSuccess) {
                    /* XSLT variant 1: params $i,$j,$subscriber,$param,$altParam — see §9 */
                    Event.Ext.sendEventImmediate(reqEvent);
                    if(!isActResub) orderCurrentActivity.RequestCount++;
                    isSkipped = false;
                    /* unconditional Logger audit */
                }
            }
        }
        // ChildOU loop (GetXMLForSubscriberInChildOU, XSLT variant 2: $i,$x,$y)
        for(int x...; y...) { /* same pattern */ }
    }

    if(!isSkipped) {
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
    } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
} catch(Exception ae) { HandleActivityException(...); }
```

---

## §7 — Data Extraction & Pre-Processing

### §7.1 — Activity Parameters

| Parameter key | Read by | Effect |
|---------------|---------|--------|
| `ALT_CES` | `GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")` | If `"Y"` AND `ExtendedInfo[ALT_CES]/Value` not empty → use that for CES header; else use `OrderData.CES` |
| `MSISDN` | `GetActivityParamValueFromKey(orderCurrentActivity, "MSISDN")` | If subscriber has `ResourceInfo[ResourceName=$param]/ValuesArray` → use that as `ns:parameterValue`; else use subscriber MSISDN |

> Note: BN_CHANGE_PACKAGE ProcessConfig does NOT set ALT_CES or MSISDN parameters for this step — defaults apply: CES = OrderData.CES, parameterValue = subscriber.MSISDN. These parameters exist to support reuse in other process configurations.

### §7.2 — CES Routing Logic

| Condition | CES Source |
|-----------|-----------|
| `altParam == "Y" AND ExtendedInfo[ALT_CES]/Value != ""` | `ExtendedInfo[ALT_CES]/Value` (overrides order-level CES) |
| Otherwise | `$orderRequest/OrderData/CES` |

### §7.3 — Resource Type & Value Selection

| Element | Condition | Value |
|---------|-----------|-------|
| `ns:parameterType` | if `ExtendedInfo[Name="PRIMARY_RESOURCE_TYPE"]` exists | That ExtendedInfo Value |
| `ns:parameterType` | otherwise (default) | `'C'` (phone number / MSISDN class) |
| `ns:parameterValue` | if `subscriber/ResourceInfo[ResourceName=$param]/ValuesArray` exists | That ValuesArray value (param = activity MSISDN parameter) |
| `ns:parameterValue` | otherwise (default) | `$subscriber/MSISDN` |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in BN_CHANGE_PACKAGE step 1 — runs only when subscriber MSISDN is known but SubscriberId is absent. The FM populates the SubscriberId and PayChannelCategory before subsequent CCBS account/agreement calls.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE` | CCBS SearchSubscriberByResource request per Subscriber |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request and response audit (unconditional) |

### §8.3 — Backend API Details

| System | Operation | Schema | Key |
|--------|-----------|--------|-----|
| CCBS | `SearchSubscriberByResource` | `tibco-ccbs-client/Schemas/SearchServices/Schema.xsd2` (ns prefix) | ns:SearchSubscriberByResourceRequest |

### §8.4 — BE Working Memory Dependencies

| Concept path | Access | Purpose |
|-------------|--------|---------|
| `ProcessFlow.NextActivityName` | Read | Load nextAct for PreExecCheck |
| `ParentOU[*].Subscriber[*].RefId` | Read | refId (idempotency key) + PreExecCheck |
| `ParentOU[*].Subscriber[*].MSISDN` | Read | Default ns:parameterValue |
| `ParentOU[*].Subscriber[*].ResourceInfo[*]` | Read | Override ns:parameterValue when ResourceName=$param |
| `ParentOU[*].Subscriber[*].ExtendedInfo[PRIMARY_RESOURCE_TYPE]` | Read | ns:parameterType override |
| `ParentOU[*].Subscriber[*].AccountRefId` | Read (response RF) | Link to Account for PayChannelCategory update |
| `ParentOU[*].Subscriber[*].Status` | Write (response RF) | Set from SubStatus |
| `ParentOU[*].Subscriber[*].SubscriberId` | Write (response RF) | Set from SubscrNumber |
| `ParentOU[*].Subscriber[*].SubscriberType` | Write (response RF) | Set from SubscriberType |
| `Customer.Account[*].PayChannelCategory` | Write (response RF) | "POST" if SubStatus=A or OrderType=11; else "PRE" |
| `OrderData.CES` | Read | Default CES header |
| `OrderData.ExtendedInfo[ALT_CES]` | Read | Alt CES header (if ALT_CES param = "Y") |
| `OrderData.User / OrderData.Password` | Read | UserName/PassWord headers (if IsEnableUserPass="true") |
| `OrderData.OrderType` | Read (response RF) | OrderType="11" → POST account category |

### §8.5 — ExtendedInfo Fields

| Name | Source | Required? | Used for |
|------|--------|-----------|---------|
| `PRIMARY_RESOURCE_TYPE` | Subscriber | Optional | Overrides default ns:parameterType 'C' |
| `ALT_CES` | OrderData | Optional | Alt CES routing (only if activity param ALT_CES=Y) |

### §8.6 — Global Variable Dependencies

| Global Variable Path | Purpose |
|---------------------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | If `"true"` → emit UserName/PassWord in event headers |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameters

| Param | Source (ParentOU variant) | Source (ChildOU variant) |
|-------|--------------------------|--------------------------|
| `$orderRequest` | orderRequest concept | orderRequest concept |
| `$i` | ParentOU index | ParentOU index |
| `$j` | Subscriber index | – |
| `$x` | – | ChildOU index |
| `$y` | – | Subscriber index within ChildOU |
| `$subscriber` | ParentOU[i].Subscriber[j] | ParentOU[i].ChildOU[x].Subscriber[y] |
| `$globalVariables` | Global variables root | Global variables root |
| `$altParam` | ALT_CES activity parameter value | ALT_CES activity parameter value |
| `$param` | MSISDN activity parameter value | MSISDN activity parameter value |

### §9.2 — Event Container

Event type: `Events.OMConsumers.OMXFM.Request.CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE`. No extId on event. RefID header always written (from 1-indexed XPath path into ParentOU/ChildOU structure).

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | [Conditional: xsl:if] |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | [Conditional: xsl:if] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Conditional: xsl:if] |
| `RefID` | ParentOU[($i+1)]/Subscriber[($j+1)]/RefId (or ChildOU equivalent) | **Always** (no xsl:if) |
| `UserName` | `$orderRequest/OrderData/User` | IsEnableUserPass="true" AND User exists |
| `PassWord` | `$orderRequest/OrderData/Password` | IsEnableUserPass="true" AND Password exists |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Conditional: xsl:if] |
| `CES` | Alt: `ExtendedInfo[ALT_CES]/Value`; Default: `OrderData/CES` | xsl:choose — ALT_CES logic |

### §9.4 — Payload Root

`ns:SearchSubscriberByResourceRequest`

### §9.5 — Payload Fields

| Element | Source | Condition | Notes |
|---------|--------|-----------|-------|
| `ns:parameterType` | ExtendedInfo[PRIMARY_RESOURCE_TYPE]/Value or `'C'` | xsl:choose | Default 'C' = phone/MSISDN class |
| `ns:parameterValue` | subscriber.ResourceInfo[$param]/ValuesArray or subscriber.MSISDN | xsl:choose | $param = MSISDN activity parameter |
| `ns:yesNoIndicator` | `89` | Always (static) | Hard-coded; meaning unclear from schema name |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

**ParentOU Variant** (params: $orderRequest, $i, $j, $subscriber, $param, $altParam, $globalVariables)

```text
createEvent
└── event  (no @extId)
    ├── JMSPriority          ← $orderRequest/OrderPriority                    [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId          [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                 [Conditional]
    ├── RefID                ← ParentOU[($i+1)]/Subscriber[($j+1)]/RefId      [Always]
    ├── UserName             ← $orderRequest/OrderData/User                    [Credential-gated: IsEnableUserPass="true" + exists]
    ├── PassWord             ← $orderRequest/OrderData/Password                [Credential-gated: IsEnableUserPass="true" + exists]
    ├── OrderType            ← $orderRequest/OrderData/OrderType               [Conditional]
    ├── CES  (xsl:choose — ALT_CES gate)
    │   ├── when altParam="Y" AND ExtendedInfo[ALT_CES]/Value!="":
    │   │   └── CES          ← ExtendedInfo[ALT_CES]/Value
    │   └── otherwise:
    │       └── CES          ← $orderRequest/OrderData/CES                    [Conditional: if CES exists]
    └── payload
        └── ns:SearchSubscriberByResourceRequest
            └── ns:ResourceSearchInputInfo
                ├── ns:parameterType  (xsl:choose)
                │   ├── when PRIMARY_RESOURCE_TYPE exists:
                │   │   └── ExtendedInfo[PRIMARY_RESOURCE_TYPE]/Value
                │   └── otherwise:
                │       └── 'C'                                               [Always default]
                ├── ns:parameterValue  (xsl:choose)
                │   ├── when ResourceInfo[ResourceName=$param]/ValuesArray exists:
                │   │   └── subscriber/ResourceInfo[$param]/ValuesArray
                │   └── otherwise:
                │       └── $subscriber/MSISDN                                [Default]
                └── ns:YesNoIndicatorInfo
                    └── ns:yesNoIndicator  ← 89                               [Always static]
```

> ChildOU variant: params add $x, $y; RefID source changes to `ParentOU[($i+1)]/ChildOU[($x+1)]/Subscriber[($y+1)]/RefId`. Payload structure is identical.

**Legend:**
- `[Always]` — emitted unconditionally
- `[Conditional]` — inside `xsl:if` block
- `[Credential-gated]` — conditional on global variable `IsEnableUserPass="true"`

---

## §11 — Audit Logging

| Event | Gate | OPERATION_NAME | AUDIT_TRACE | Bug? |
|-------|------|----------------|-------------|------|
| Request audit | **Unconditional** (no AllowWriteLog) | `"CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE"` ✓ | `"Request Sent for CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE"` ✓ | None |
| Response audit | **Unconditional** (no AllowWriteLog) | `"CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE"` ✓ | `"Response received for CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE"` ✓ | None |

> Both request and response audits are unconditional — no AllowWriteLog gate. Payload gating via `OMX_OM/WritePayload="true"` global variable.

---

## §12 — Activity Status Management

| Condition | Action | Status |
|-----------|--------|--------|
| At least one subscriber dispatched | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" = PROCESSING |
| No subscribers pass checks | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" = SKIPPED |

---

## §13 — Exception / Error Handling

Standard `try/catch(Exception ae) → HandleActivityException`. PurgePendingRequestsBeforeResubmit is called INSIDE the try block (correct — unlike some other FMs that call it outside).

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clear pending state on resubmit (called inside try block) |
| `Helpers.GetActivityParameterValueFromKey(activity, key)` | Read activity parameter by key (ALT_CES) |
| `Helpers.GetActivityParamValueFromKey(activity, key)` | Read activity param value by key (MSISDN) |
| `Helpers.GetXMLForSubscriber(orderRequest, refId)` | Build PreExecCheck XML for ParentOU subscriber |
| `Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, parentOuRefId)` | Build PreExecCheck XML for ChildOU subscriber |
| `Helpers.GetActivityStatusString(code, flag)` | Status code translation |
| `Helpers.SendDataToDB(orderRequest)` | Persist order state |
| `Helpers.SkipActivity(orderRequest, activity, code)` | Mark activity skipped |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |
| `OMXUtils.asciiCodeToText(code)` | Response RF: convert SubStatus integer to text (e.g., 65→"A") |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE (rule)
├── try {
│   ├── Instance.getByExtIdByUri()                  [load nextAct for PreExecCheck]
│   ├── [isActResub] → IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()
│   ├── Helpers.GetActivityParameterValueFromKey()   [ALT_CES param]
│   ├── Helpers.GetActivityParamValueFromKey()       [MSISDN param]
│   ├── [ParentOU/ChildOU/Subscriber loops]
│   │   ├── Helpers.GetXMLForSubscriber()            [ParentOU PreExecCheck]
│   │   ├── Helpers.GetXMLForSubscriberInChildOU()   [ChildOU PreExecCheck]
│   │   ├── XPath.execute()                          [PreExecCheck evaluation]
│   │   ├── [idempotency scan on Response[]]
│   │   ├── Event.createEvent()                      [CCBS_SEARCH_SUB_BY_RESOURCE XSLT — see §9]
│   │   ├── Event.Ext.sendEventImmediate()           [direct dispatch — no IntraActivitySequencing]
│   │   ├── orderCurrentActivity.RequestCount++      [if !isActResub]
│   │   ├── System.nanoTime()
│   │   ├── Event.createEvent()                      [Logger XSLT — unconditional audit]
│   │   └── Event.Ext.sendEventImmediate()           [request audit]
│   ├── Helpers.GetActivityStatusString()
│   ├── Helpers.SendDataToDB()
│   └── Helpers.SkipActivity()
└── catch → Helpers.HandleActivityException()

Response_CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE (rulefunction)
├── Instance.createInstance()                        [CCBS_SearchSubscriberByResource concept XSLT]
├── currActivity.Response[] ← activityRes
├── [SubscriberSearchResultInfo selection loop]
│   ├── OMXUtils.asciiCodeToText(SubStatus)          [S/A/D/U priority check]
│   └── DateTime.before(latestDate, d)               [fallback: latest SubStatusDate]
├── [Subscriber lookup by eventResponse.RefID in ParentOU and ChildOU]
│   └── sub.Status / sub.SubscriberId / sub.SubscriberType ← selected result
├── [Account lookup by sub.AccountRefId]
│   └── account.PayChannelCategory = "POST" or "PRE"
├── [Empty result fallback: account.PayChannelCategory = "PRE"]
├── System.nanoTime()
├── Event.createEvent()                              [Logger XSLT — unconditional response audit]
├── Event.Ext.sendEventImmediate()                   [response audit]
└── XPath.evalAsInt()                                [count Response[ResponseCode ends "000"]]
    → return "true" if RequestCount == successResponseCount
    → return "false" otherwise
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | Both | OrderData.CES, ExtendedInfo[ALT_CES], ParentOU/ChildOU/Subscriber/Account |
| `Concepts.OM.ProcessConfig.Activity` | Both | RequestCount, Response[], Parameter[] |
| `Concepts.FM.Response.CCBS_SearchSubscriberByResource` | Response RF | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, **SubscriberSearchResultInfo[]** |
| `Concepts.FM.Response.SubscriberSearchResultInfo` | Response RF | SubStatus, SubStatusDate, SubscrNumber, SubscriberType, PricePlan, CustomerNo, … (full subscriber data) |
| `Concepts.OrderRequest.OrderElements.Subscriber` | Response RF (write) | Status, SubscriberId, SubscriberType, AccountRefId |
| `Concepts.OrderRequest.OrderElements.Account` | Response RF (write) | PayChannelCategory ("POST" / "PRE") |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | For each subscriber (ParentOU and ChildOU), call CCBS SearchSubscriberByResource with parameterType and parameterValue (MSISDN or ResourceInfo override) |
| R2 | Per-subscriber idempotency: skip if Response[].ReferenceId == subscriber.RefId and CompletionStatus == 2 |
| R3 | Direct parallel dispatch: sendEventImmediate per subscriber; fan-in via count(Response[code ends "000"]) == RequestCount |
| R4 | ALT_CES routing: if activity param ALT_CES="Y" and ExtendedInfo[ALT_CES] not empty → use that for CES; else OrderData.CES |
| R5 | IsEnableUserPass: if global var = "true" → emit UserName/PassWord in headers |
| R6 | Response enrichment: select best SubscriberSearchResultInfo by SubStatus priority (S/A/D/U first, else latest SubStatusDate); write Status/SubscriberId/SubscriberType to subscriber concept |
| R7 | PayChannelCategory: "POST" if SubStatus=A(65) or OrderType="11"; else "PRE". Empty response → "PRE" |
| R8 | ns:yesNoIndicator = 89 (static) |

### Design Notes

| Note | Severity | Detail |
|------|----------|--------|
| **Two GetActivityParameter variants**: rule calls both `GetActivityParameterValueFromKey` and `GetActivityParamValueFromKey` — possibly two different helper implementations for different parameter storage patterns. Should be verified and consolidated. | [MEDIUM] | Verify that both helpers read from the same underlying Activity parameter structure |
| **PayChannelCategory "POST" gate includes OrderType="11"**: in addition to SubStatus=A, OrderType string "11" forces POST — this is a business rule that must be preserved in any migration | [INFO] | OrderType "11" = likely a specific CCBS order type that implies postpaid |
| **SubscriberSearchResultInfo selection is non-trivial**: priority logic (S/A/D/U first, then latest date) is bespoke matching logic that must be reproduced exactly in any replacement system | [INFO] | The fallback to latestSubStatusDate means results are non-deterministic if multiple entries share same date and none is S/A/D/U |
| **YesNoIndicator=89 is undocumented**: the static value 89 in `ns:yesNoIndicator` is not explained in the rule and requires CCBS API documentation to interpret | [MEDIUM] | Likely a CCBS indicator flag; verify with CCBS integration team before migration |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE {
    attribute { priority = 5; forwardChain = true; }
    declare { OrderRequest orderRequest; Activity orderCurrentActivity; }
    when { /* extId / ActivityID / NextActivityID / Status == "WAITING" */ }
    then {
        boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
        try {
            Activity nextAct = Instance.getByExtIdByUri(...);
            if(isActResub) PurgePendingRequestsBeforeResubmit(orderCurrentActivity); // inside try
            String altParam = GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES");
            String param    = GetActivityParamValueFromKey(orderCurrentActivity, "MSISDN");
            boolean isSkipped = true;

            // ParentOU[i] → Subscriber[j]
            for(int i...; j...) {
                refId = subscriber.RefId;
                // PreExecCheck + idempotency
                if(chkRes == "true" && !reqSuccess) {
                    /* XSLT variant 1 ($i,$j,$subscriber,$param,$altParam) — see §9 */
                    Event.Ext.sendEventImmediate(reqEvent);
                    if(!isActResub) RequestCount++;
                    isSkipped = false;
                    /* unconditional Logger audit */
                }
            }
            // ChildOU[i][x][y] — same pattern with XSLT variant 2

            if(!isSkipped) { status="1"; SendDataToDB; }
            else { SkipActivity("4"); }
        } catch(Exception ae) { HandleActivityException; }
    }
}
```

---

## §19 — Response Message Rule (Response_CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE)

### §19.1 — Overview

Parses CCBS SearchSubscriberByResource response into a `CCBS_SearchSubscriberByResource` concept (with a `SubscriberSearchResultInfo[]` array). Then selects the "best" result and enriches the working memory subscriber and account concepts. Finally performs fan-in check.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context; subscriber/account lookup targets |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE` | CCBS response; carries RefID, ResponseCode, SubscriberSearchResultInfoArray in payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] written to; RequestCount for fan-in |

### §19.3 — CCBS_SearchSubscriberByResource Concept Construction

```text
createObject  (Concepts.FM.Response.CCBS_SearchSubscriberByResource)
└── object
    ├── @extId                        ← OMXUtils:generateTrackingID()              [Always]
    ├── ResponseCode                  ← $eventResponse/ResponseCode                [Conditional]
    ├── ResponseMessage               ← $eventResponse/ResponseMsg                 [Conditional]
    ├── CompletionStatus              ← $eventResponse/CompletionStatus            [Conditional]
    ├── ReferenceId                   ← $eventResponse/RefID                       [Conditional]
    └── SubscriberSearchResultInfo[]  (xsl:for-each ns:SubscriberSearchResultInfo) [0..N]
        ├── @extId                    ← OMXUtils:generateTrackingID()
        └── AddressLine1–3, BusinessEntityId, CustomerNo, CustomerType, LinkType,
            NameLine1–2, NotAssignedAll, PricePlan, PrimaryResourceType,
            PrimaryResourceValue, ResourceEffectiveDate, ResourceExpirationDate,
            ResourceType, ResourceValue, SubStatus, SubStatusDate, SubscrNumber,
            SubscriberType                                                          [All Conditional]
```

### §19.4 — SubscriberSearchResultInfo Selection Logic

| Priority | Condition | Action |
|----------|-----------|--------|
| 1 (highest) | `SubStatus == 'S' OR 'A' OR 'D' OR 'U'` (65='A', etc.) | Use first match; break loop |
| 2 (fallback) | None of S/A/D/U found | Use entry with latest `SubStatusDate` (DateTime comparison) |

> `OMXUtils.asciiCodeToText()` is used to convert integer SubStatus to character for string comparison.

### §19.5 — Working Memory Enrichment

| Target | Source | Condition |
|--------|--------|-----------|
| `sub.Status` | `subscriberSearchResultInfo.SubStatus` | subscriberSearchResultInfo != null (by RefId match) |
| `sub.SubscriberId` | `String.valueOfInt(subscriberSearchResultInfo.SubscrNumber)` | subscriberSearchResultInfo != null |
| `sub.SubscriberType` | `subscriberSearchResultInfo.SubscriberType` | subscriberSearchResultInfo != null |
| `account.PayChannelCategory` | `"POST"` | SubStatus==65 (A) OR OrderType=="11" |
| `account.PayChannelCategory` | `"PRE"` | otherwise; or if SubscriberSearchResultInfo[] is empty |

### §19.6 — Response Completion Logic (Fan-in)

| Step | Logic |
|------|-------|
| Success count | `XPath.evalAsInt("count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)=\"000\"])")` |
| Return "true" | `currActivity.RequestCount == successResponseCount` — all subscribers responded successfully |
| Return "false" | Still waiting for more responses |

### §19.7 — Response Audit Logging

| Field | Value |
|-------|-------|
| `OPERATION_NAME` | `"CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE"` ✓ |
| `AUDIT_TRACE` | `"Response received for CCBS_SEARCH_SUBSCRIBER_BY_RESOURCE"` ✓ |
| Gate | **Unconditional** |
| `PROCESS_ID` | `concat($pid, "_RES")` |
| payload | Full `$eventResponse` copy, gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
