# Request_OMX_CALC_ACTIVITY_REASON

**Rule class:** `Rules.OMConsumers.OMXOM.OMX_CalcActivityReason`
**File:** `OMX_CalcActivityReason.rule`
**Author:** RRAWAT-t420 | **Priority:** 5 | **forwardChain:** true
**Type:** Internal OMX Calculation Rule (OMXOM) — No External Backend Call
**Pattern:** Per-ParentOU VRF Fan-Out (`invokeAllVRFImpls`)

---

## §1 — Overview & Purpose

This rule computes the "activity reason" for each ParentOU (subscriber account) in the order before provisioning activities begin. It iterates all ParentOUs and invokes **ALL** registered `CalcActivityReasonVRF` decision tables, passing contextual attributes per subscriber so each DT can compute and write an activity reason code onto the ParentOU concept.

The computed activity reason drives downstream routing and provisioning decisions (e.g., which AA provisioning path to take). Unlike `OMX_BIZ_VAL` which uses `invokeVRFImplByName` to select a single DT, this rule uses `invokeAllVRFImpls` — all matching CalcActivityReason DTs fire for each ParentOU iteration.

| Item | Value |
|------|-------|
| Rule class | `Rules.OMConsumers.OMXOM.OMX_CalcActivityReason` |
| ActivityID | `OMX_CALC_ACTIVITY_REASON` |
| Author | RRAWAT-t420 |
| Backend call | None — invokes local VRF decision tables |
| VRF path | `/DecisionTables/CalcActivityReasonVRF` |
| VRF invocation style | `invokeAllVRFImpls` (ALL registered DTs fire per OU) |
| Loop granularity | Per-ParentOU (one VRF call per ParentOU) |
| Completion | `NextActivity` (synchronous, after loop) |
| Audit logs | Two: START (triggered) + END (completed), both gated by AllowWriteLog |
| Source ticket | OMX-1053 (Parameter guard fix) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule type | `rule` | RETE stateful rule |
| priority | 5 | Standard priority |
| forwardChain | true | Re-evaluates if working memory changes during execution |
| Namespace | OMXOM | Internal OMX — no external FM/ESB call |
| Response rulefunction | None | Synchronous — no async backend call |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Root order — serialised for PreExecCheck; all XPath queries; ParentOU array iterated |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Current activity — Parameter[0] read for VRF arg; Status advanced via NextActivity |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Meaning |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity matches current process step |
| 2 | `orderCurrentActivity.ActivityID == "OMX_CALC_ACTIVITY_REASON"` | This rule fires only for the activity reason calculation step |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_CALC_ACTIVITY_REASON"` | Process flow confirms this step is next |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity has not yet been processed |

---

## §5 — Execution Flow Diagram

1. **Serialise order:** `sXML = Instance.serializeUsingDefaults(orderRequest)` — for PreExecCheck evaluation.
2. **PreExecCheck:** If set, evaluate XPath against full order XML. If not "true", skip via `SkipActivity("4")`.
3. **START audit log:** If AllowWriteLog → `sendEventImmediate(Logger)` with `AUDIT_TRACE="OMX-OM Rule OMX_CalcActivityReason triggered."` and PROCESS_ID `_REQ`.
4. **Parameter guard (OMX-1053):** If `Parameter@length == 0`, insert `Parameter[0] = ""` to prevent array-out-of-bounds.
5. **Per-ParentOU loop:** For each ParentOU index `i` in `0..iPOULen-1`:
   - XPath-extract 5 scalar attributes + read 2 direct fields
   - Build 10-element `Object[] args`
   - Call `VRF.invokeAllVRFImpls("/DecisionTables/CalcActivityReasonVRF", args)`
6. **Advance flow:** `NextActivity(orderRequest, orderCurrentActivity)` — synchronous after loop.
7. **END audit log:** If AllowWriteLog → `sendEventImmediate(Logger)` with `AUDIT_TRACE="OMX-OM Rule OMX_CalcActivityReason completed."` and PROCESS_ID `_RES`.

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### §6.1 VRF Arguments Extracted Per-ParentOU

| Arg index | Name | Source | XPath / field access |
|-----------|------|--------|---------------------|
| args[0] | ParentOU[i] | Direct concept ref | `orderRequest.OrderData.Customer.ParentOU[i]` |
| args[1] | Parameter[0] | Activity config | `orderCurrentActivity.Parameter[0]` |
| args[2] | MNPInfo | Direct concept ref | `orderRequest.OrderData.MNPInfo` |
| args[3] | orderType | XPath | `$orderRequest/OrderData/OrderType` |
| args[4] | payChanCatg | XPath | `Account[AgreementRefId=../ParentOU[i+1]/RefId]/PayChannelCategory` |
| args[5] | source | XPath | `Account[AgreementRefId=../ParentOU[i+1]/RefId]/ExtendedInfo[Name="SOURCE_OR_TARGET"]/Value` |
| args[6] | channel | XPath | `$orderRequest/OrderData/Channel` |
| args[7] | DealerCode | Direct field | `orderRequest.OrderData.DealerCode` |
| args[8] | sourcePayChannel | XPath | `Account[AgreementRefId=ParentOU[ExtendedInfo[Name="SOURCE_OR_TARGET" and Value="SOURCE"]]/RefId]/PayChannelCategory` |
| args[9] | cdbStatus | XPath | `ParentOU[i+1]/Subscriber[exists(CdbProfile)]/CdbProfile/Status` |

> **[MEDIUM]** `donorZoneCode` is read from `orderRequest.OrderData.MNPInfo.DonorZoneCode` and printed in `System.debugOut`, but is **not** included in the `args` array. Since `MNPInfo` (args[2]) is the full concept, VRF DTs can still access it from there — but the explicit extraction implies it was intended as a separate arg that was accidentally omitted.

### §6.2 VRF Invocation Style — invokeAllVRFImpls

> **invokeAllVRFImpls** fires ALL registered implementations of the `CalcActivityReasonVRF` interface that match their internal conditions. This differs from `invokeVRFImplByName` — here, multiple DTs can modify the same ParentOU in sequence. The order of DT execution depends on their priority in the VRF registry.

| Element | Value |
|---------|-------|
| VRF interface path | `/DecisionTables/CalcActivityReasonVRF` |
| Invocation style | `invokeAllVRFImpls` — all matching DTs fire |
| Loop | Once per ParentOU; VRF invoked `iPOULen` times total |
| DT output | Written directly onto ParentOU concept (activity reason fields) |

### §6.3 Parameter Guard — OMX-1053

```java
int arrLength = orderCurrentActivity.Parameter@length;
if(arrLength == 0)
    orderCurrentActivity.Parameter[orderCurrentActivity.Parameter@length] = "";
```

If no `<ns0:Parameter>` was configured in the ProcessConfig XML, the array is empty and `Parameter[0]` would throw an array-out-of-bounds exception. This guard inserts a dummy empty string at index 0. Fix applied for ticket OMX-1053.

### §6.4 Key XPath Queries Detail

| Variable | Query purpose | Notable predicate |
|----------|--------------|-------------------|
| `payChanCatg` | Payment channel for current ParentOU's account | `AgreementRefId = ../ParentOU[i+1]/RefId` — 1-based XPath while loop is 0-based |
| `sourcePayChannel` | Payment channel for SOURCE subscriber's account | `ParentOU[ExtendedInfo[Name="SOURCE_OR_TARGET" and Value="SOURCE"]]` |
| `source` | SOURCE_OR_TARGET flag for current OU | `ExtendedInfo[Name="SOURCE_OR_TARGET"]/Value` — "SOURCE" or "TARGET" |
| `cdbStatus` | CDB profile status for first subscriber with CdbProfile | `Subscriber[exists(CdbProfile)]` — empty string if none has CdbProfile |

---

## §7 — Data Extraction

All data extraction uses `XPath.evalAsString()` with the `xpath://<xpath><expr>...</expr>` format with explicit namespace and variable bindings.

> **[LOW]** `System.debugOut` on line 55 is active (not commented out) and prints to the BE engine log for every ParentOU on every order. The similar `debugOut` at the top of the rule is correctly commented out.

| Variable | Scope | Read via |
|----------|-------|---------|
| `payChanCatg` | Per-OU | `XPath.evalAsString` |
| `sourcePayChannel` | Order-wide (SOURCE OU) | `XPath.evalAsString` |
| `source` | Per-OU | `XPath.evalAsString` |
| `orderType` | Order-wide | `XPath.evalAsString` |
| `channel` | Order-wide | `XPath.evalAsString` |
| `donorOperator` | Order-wide (MNP) | Direct field: `orderRequest.OrderData.MNPInfo.DonorOperator` |
| `donorZoneCode` | Order-wide (MNP) | Direct field — **read but NOT passed to VRF** |
| `cdbStatus` | Per-OU | `XPath.evalAsString` |

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

All registered CalcActivityReasonVRF DTs are tried for each ParentOU — no DT name is derived from OrderType. For PREPAID_CANCEL, the relevant DTs will evaluate `orderType` (args[3]) to select applicable rules and set an activity reason code on the ParentOU.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel / Event | Used when | PROCESS_ID |
|-----------|-----------------|-----------|-----------|
| [LOG START] | Events.OMConsumers.OMXESB.Logger | Before loop (AllowWriteLog) | `_REQ` |
| [LOG END] | Events.OMConsumers.OMXESB.Logger | After NextActivity (AllowWriteLog) | `_RES` |

> Both log events include the full `orderRequest` in `payload/ns1:ServicePayload` — potentially large log entries.

### §8.3 Working Memory Read/Written

| Field | Read/Written | Notes |
|-------|-------------|-------|
| `orderRequest.OrderData.Customer.ParentOU[i]` | READ (ref), WRITTEN by VRF DTs | VRF DTs write activity reason onto each ParentOU |
| `orderCurrentActivity.Parameter[0]` | READ | Passed to VRF as second arg; OMX-1053 guard ensures it exists |
| `orderRequest.OrderData.MNPInfo` | READ | Passed to VRF; donorOperator/donorZoneCode accessible from it |
| `orderRequest.OrderData.DealerCode` | READ | Passed to VRF as args[7] |

### §8.4 Global Variable Dependencies

| Path | Used for |
|------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in both audit log events |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in both audit log events |

---

## §9 — Payload Build (Audit Log Events Only)

No outbound JMS message is built for a backend system. Two audit log events are emitted sharing the same XSLT structure — only `PROCESS_ID` suffix and `AUDIT_TRACE` text differ.

### §9.1 Shared Logger XSLT Parameters

| Parameter | Bound from |
|-----------|-----------|
| `$orderRequest` | Serialised orderRequest concept |
| `$pid` | `System.nanoTime()` — same value for both events in a run |
| `$globalVariables` | BE global variables tree |

### §9.2 Logger XSLT Field Output

| Field | Source | Start event | End event |
|-------|--------|------------|----------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` | Conditional | Conditional |
| PROCESS_ID | `concat($pid, "_REQ")` / `"_RES"` | `_REQ` | `_RES` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Always | Always |
| OPERATION_NAME | `"/Rules/OMConsumers/OMXOM/OMX_CalcActivityReason"` | Always | Always |
| LOG_LEVEL | `$globalVariables/.../MSG_LOG_LEVEL/INFO` | Always | Always |
| AUDIT_TRACE | Static string | "triggered." | "completed." |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` | Always | Always |
| payload | `<ns1:ServicePayload><xsl:copy-of select="$orderRequest"/>` | Always | Always |

### §9.8 XSLT Stylesheet Source (START event; END differs in PROCESS_ID suffix and AUDIT_TRACE text)

```xml
<xsl:stylesheet xmlns:ns1="http://schemas.true.com/AuditLogging/V1_0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
    version="1.0">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>
  <xsl:param name="pid"/>
  <xsl:param name="globalVariables"/>
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
          <ESBUUID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></ESBUUID>
        </xsl:if>
        <PROCESS_ID><xsl:value-of select="concat($pid,'_REQ')"/></PROCESS_ID>  <!-- "_RES" in END event -->
        <COMPONENT_NAME><xsl:value-of select="$globalVariables/OMX_COMMON/Component_Name/OMX_CEP"/></COMPONENT_NAME>
        <OPERATION_NAME><xsl:value-of select="'/Rules/OMConsumers/OMXOM/OMX_CalcActivityReason'"/></OPERATION_NAME>
        <LOG_LEVEL><xsl:value-of select="$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO"/></LOG_LEVEL>
        <AUDIT_TRACE><xsl:value-of select="'OMX-OM Rule OMX_CalcActivityReason triggered.'"/></AUDIT_TRACE>  <!-- "completed." in END -->
        <AUDIT_TS><xsl:value-of select="tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())"/></AUDIT_TS>
        <payload>
          <ns1:ServicePayload>
            <xsl:copy-of select="$orderRequest"/>
          </ns1:ServicePayload>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Audit Log Output Tree

```text
createEvent
└── event
    ├── ESBUUID              ← $orderRequest/OrderData/OMXTrackingId        [Conditional: xsl:if test="$orderRequest/OrderData/OMXTrackingId"]
    ├── PROCESS_ID           ← concat($pid, "_REQ")                         [Always] ("_RES" in END event)
    ├── COMPONENT_NAME       ← $globalVariables/OMX_COMMON/Component_Name/OMX_CEP  [Always]
    ├── OPERATION_NAME       ← "/Rules/OMConsumers/OMXOM/OMX_CalcActivityReason"   [Always]
    ├── LOG_LEVEL            ← $globalVariables/.../MSG_LOG_LEVEL/INFO      [Always]
    ├── AUDIT_TRACE          ← "OMX-OM Rule OMX_CalcActivityReason triggered."     [Always] ("completed." in END)
    ├── AUDIT_TS             ← tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())  [Always]
    └── payload                                                               [Always]
        └── ns1:ServicePayload ← xsl:copy-of $orderRequest                  [Always]
```

Legend: Green=XPath from source | Orange=static literal | `[Always]`=always emitted | `[Conditional: ...]`=inside xsl:if

---

## §11 — Audit Logging

| Event | When | PROCESS_ID | AUDIT_TRACE | Gated? |
|-------|------|-----------|------------|--------|
| START | Before Parameter guard and VRF loop | `pid + "_REQ"` | "OMX-OM Rule OMX_CalcActivityReason triggered." | Yes — AllowWriteLog |
| END | After NextActivity | `pid + "_RES"` | "OMX-OM Rule OMX_CalcActivityReason completed." | Yes — AllowWriteLog |

Both events include the full `orderRequest` in the payload. The same `pid` is used for both, enabling duration measurement of the VRF loop.

---

## §12 — Activity Status Management

| Outcome | Mechanism | Activity status |
|---------|-----------|----------------|
| PreExecCheck false | `SkipActivity("4")` | SKIPPED |
| Loop completed successfully | `NextActivity(orderRequest, orderCurrentActivity)` | COMPLETED (via NextActivity) |
| Exception | `HandleActivityException(...)` | FAILED (set by handler) |

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

Any exception from the loop or VRF invocation is caught generically. The loop is not transactional — if a VRF call fails on ParentOU[2] after successfully modifying ParentOU[0] and [1], those writes are not rolled back.

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|----------|--------|---------|
| `Instance.serializeUsingDefaults(orderRequest)` | String (XML) | Serialises full order for PreExecCheck |
| `XPath.execute(chkXPath, sXML, ns)` | String | PreExecCheck expression evaluation |
| `XPath.evalAsString("xpath://...")` | String | Per-OU attribute extraction (5 calls per loop iteration) |
| `VRF.invokeAllVRFImpls(path, args)` | void | Fires ALL registered CalcActivityReason DTs per OU |
| `RuleFunctions.Helpers.AllowWriteLog(orderType)` | boolean | Gates audit log emission by order type |
| `RuleFunctions.Helpers.NextActivity(req, act)` | void | Advances process flow after loop |
| `RuleFunctions.Helpers.SkipActivity(req, act, "4")` | void | Skips activity if PreExecCheck false |
| `RuleFunctions.Helpers.HandleActivityException(req, act, ae, "")` | void | Generic exception handler |
| `System.nanoTime()` | long | PROCESS_ID base; captured once, shared by both audit events |

---

## §15 — Function Dependency Tree

```text
OMX_CalcActivityReason / OMX_CALC_ACTIVITY_REASON (rule)
├── Instance.serializeUsingDefaults(orderRequest)              [BE built-in]
├── XPath.execute(PreExecCheck, sXML)                          [BE built-in]
├── RuleFunctions.Helpers.AllowWriteLog(OrderType)            [helper — START log gate]
├── Event.Ext.sendEventImmediate(Logger — START, _REQ)         [BE built-in]
├── [PARAMETER GUARD — OMX-1053]
│   └── orderCurrentActivity.Parameter[0] = ""               [if array empty]
├── [PER-PARENTOU LOOP: i = 0..iPOULen-1]
│   ├── XPath.evalAsString(payChanCatg)                       [BE built-in]
│   ├── XPath.evalAsString(sourcePayChannel)                  [BE built-in]
│   ├── XPath.evalAsString(source)                            [BE built-in]
│   ├── XPath.evalAsString(orderType)                         [BE built-in]
│   ├── XPath.evalAsString(channel)                           [BE built-in]
│   ├── orderRequest.OrderData.MNPInfo.DonorOperator           [direct field]
│   ├── orderRequest.OrderData.MNPInfo.DonorZoneCode           [direct field — NOT in args!]
│   ├── XPath.evalAsString(cdbStatus)                         [BE built-in]
│   └── VRF.invokeAllVRFImpls("/DecisionTables/CalcActivityReasonVRF", args[10])
│       └── [All matching CalcActivityReason DTs]
│           └── Writes: ParentOU[i].ActivityReason (or equivalent field)
├── RuleFunctions.Helpers.NextActivity(req, act)              [helper]
├── RuleFunctions.Helpers.AllowWriteLog(OrderType)            [helper — END log gate]
├── Event.Ext.sendEventImmediate(Logger — END, _RES)           [BE built-in]
├── RuleFunctions.Helpers.SkipActivity(req, act, "4")        [helper — PreExecCheck=false]
└── RuleFunctions.Helpers.HandleActivityException(...)       [helper — catch]
```

---

## §16 — Concept Definitions Referenced

| Field / Concept | Type | Role |
|----------------|------|------|
| `orderRequest.OrderData.Customer.ParentOU[]` | Array of ParentOU | Iterated; each ParentOU passed to VRF; DTs write activity reason onto it |
| `orderRequest.OrderData.Customer.Account[]` | Array of Account | XPath-queried for PayChannelCategory per OU |
| `orderRequest.OrderData.MNPInfo` | MNPInfo concept | DonorOperator, DonorZoneCode read; entire concept passed to VRF as args[2] |
| `orderRequest.OrderData.OrderType` | String | Passed to VRF and used for AllowWriteLog gate |
| `orderRequest.OrderData.Channel` | String | Passed to VRF as args[6] |
| `orderRequest.OrderData.DealerCode` | String | Passed to VRF as args[7] |
| `orderCurrentActivity.Parameter[0]` | String | Passed to VRF as args[1]; OMX-1053 guard ensures it exists |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | For each subscriber (ParentOU), compute an activity reason code before provisioning begins |
| R2 | Activity reason must consider: payment channel, MNP donor operator, SOURCE/TARGET role, CDB status, order type, channel, dealer code |
| R3 | Support processing of multiple subscribers in the same order (loop) |
| R4 | Activity reason logic must be externalised per-DT (VRF) to allow independent update without redeploying the orchestration rule |
| R5 | Handle missing Parameter configuration gracefully (empty default — OMX-1053) |
| R6 | Emit bracketing audit log events (triggered / completed) to enable duration measurement of the VRF loop |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `donorZoneCode` extracted but not passed to VRF — may be missing from DT decisions | [MEDIUM] | Confirm whether DTs access DonorZoneCode via args[2] (MNPInfo) or expected it as a separate arg; add as args[10] if needed |
| VRF loop is not transactional — partial OU writes if exception on later iteration | [MEDIUM] | Add compensating logic or validate all OUs before writing; or wrap each OU in its own try/catch |
| Large payloads in both audit log events (full orderRequest copied twice) | [LOW] | Log only orderRequest metadata (TrackingId, OrderType) for performance |
| `System.debugOut` active on line 55 — debug output in production for every OU on every order | [LOW] | Comment out or remove before production deployment |
| OPERATION_NAME uses rule path not ActivityID — inconsistent with "OMX_CALC_ACTIVITY_REASON" | [LOW] | Use ActivityID in OPERATION_NAME for log consistency |
| ProcessID assignment commented out — no correlation ID on activity | [LOW] | Decide whether ProcessID is needed; if so, uncomment |
| XPath uses 1-based indexing (`ParentOU[i+1]`) while loop uses 0-based `i` | [LOW] | Add comment explaining the convention to prevent maintenance errors |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author RRAWAT-t420
 */
rule Rules.OMConsumers.OMXOM.OMX_CalcActivityReason {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "OMX_CALC_ACTIVITY_REASON";
        orderRequest.ProcessFlow.NextActivityID == "OMX_CALC_ACTIVITY_REASON";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        // [commented out] System.debugOut("["+OMXTrackingId+"] Executing OMX_CalcActivityReason...")
        try {
            String chkXPath = orderCurrentActivity.PreExecCheck;
            String chkRes = "true";
            String sXML = Instance.serializeUsingDefaults(orderRequest);
            if (String.length(orderCurrentActivity.PreExecCheck) > 0) {
                chkRes = XPath.execute("/("+chkXPath+")", sXML,
                    "ns0=www.tibco.com/be/ontology/Concepts/OrderRequest/OrderRequest");
            }

            if (String.equals(chkRes, "true")) {
                //orderCurrentActivity.ProcessID = String.valueOfLong(System.nanoTime());
                long pid = System.nanoTime();

                // START audit log — "triggered."
                if (RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                    Event.Ext.sendEventImmediate(Event.createEvent(
                        /* §9.8 Logger START: PROCESS_ID=pid+"_REQ", AUDIT_TRACE="triggered.", payload=orderRequest */));
                }

                // OMX-1053: Parameter guard — ensure Parameter[0] exists
                int arrLength = orderCurrentActivity.Parameter@length;
                if(arrLength == 0)
                    orderCurrentActivity.Parameter[orderCurrentActivity.Parameter@length] = "";

                // Per-ParentOU loop
                int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
                for (int i=0; i < iPOULen; i++) {
                    String payChanCatg = XPath.evalAsString(
                        /* Account[AgreementRefId=../ParentOU[i+1]/RefId]/PayChannelCategory */);
                    String sourcePayChannel = XPath.evalAsString(
                        /* Account[AgreementRefId=ParentOU[ExtendedInfo[Name="SOURCE_OR_TARGET" and Value="SOURCE"]]/RefId]/PayChannelCategory */);
                    String source = XPath.evalAsString(
                        /* Account[AgreementRefId=../ParentOU[i+1]/RefId]/ExtendedInfo[Name="SOURCE_OR_TARGET"]/Value */);
                    String orderType = XPath.evalAsString(/* $orderRequest/OrderData/OrderType */);
                    String channel = XPath.evalAsString(/* $orderRequest/OrderData/Channel */);
                    String donorOperator = orderRequest.OrderData.MNPInfo.DonorOperator;
                    String donorZoneCode = orderRequest.OrderData.MNPInfo.DonorZoneCode;  // read but NOT in args
                    String cdbStatus = XPath.evalAsString(
                        /* ParentOU[i+1]/Subscriber[exists(CdbProfile)]/CdbProfile/Status */);

                    System.debugOut("invokeAllVRFImpls\t:" + orderType + "|" + channel + "|"
                        + source + "|" + payChanCatg + "|" + donorOperator
                        + "|" + donorZoneCode + "|" + cdbStatus);  // NOT commented out!

                    Object[] args = {
                        orderRequest.OrderData.Customer.ParentOU[i],  // [0] current ParentOU
                        orderCurrentActivity.Parameter[0],             // [1] activity parameter
                        orderRequest.OrderData.MNPInfo,                // [2] MNP info (incl. donorZoneCode)
                        orderType,                                      // [3]
                        payChanCatg,                                    // [4]
                        source,                                         // [5] SOURCE_OR_TARGET flag
                        channel,                                        // [6]
                        orderRequest.OrderData.DealerCode,             // [7]
                        sourcePayChannel,                               // [8] SOURCE OU's PayChannelCategory
                        cdbStatus                                       // [9]
                    };
                    VRF.invokeAllVRFImpls("/DecisionTables/CalcActivityReasonVRF", args);
                }

                RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity);

                // END audit log — "completed."
                if (RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                    Event.Ext.sendEventImmediate(Event.createEvent(
                        /* §9.8 Logger END: PROCESS_ID=pid+"_RES", AUDIT_TRACE="completed.", payload=orderRequest */));
                }
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch (Exception ae) {
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 — Response Message Rule (Not Applicable)

This is an internal synchronous OMXOM rule. There is no corresponding response rulefunction — process flow advancement is handled directly via `NextActivity` within the rule itself.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
