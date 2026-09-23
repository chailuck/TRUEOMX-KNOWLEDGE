# Request_ASRM_INVOKE_SIM

> TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation  
> ASRM Unified Resource Activity — SIM Card Operations (RESERVE / PREACTIVATE / ACTIVATE)

**Priority:** 5 | **forwardChain:** true | **Backend:** ASRM | **Channel:** OMXFMConnectionRequest | **Generated:** 2026-07-23

---

## §1 — Overview & Purpose

This rule fires when the order orchestration engine reaches an activity with `ActivityID = ASRM_INVOKE_SIM` and status `WAITING`. It sends a **UnifiedResourceActivity** request to ASRM for the SIM card resource for every eligible subscriber in the order — both ParentOU and ChildOU levels.

The specific operation is driven by the `ACTIVITY` parameter: typically **RESERVE**, **PREACTIVATE**, or **ACTIVATE**.

> **Key distinction from ASRM_INVOKE_MSISDN:**
> - Resource **Type** is chosen dynamically: `SIM` vs `STARTER PACK` (based on OrderType=51 and SIM_PAIR_MSISDN presence)
> - Resource **Value** uses a 3-tier fallback chain: explicit `RESOURCE_NAME` parameter → `ResourceInfo["SIM"]` → `ExtendedInfo["ICC_ID"]`
> - No ActivityAttributes (DEALER, MNP fields) — SIM operations do not require them
> - Reads additional `RESOURCE_NAME` parameter from activity via `GetActivityParameterValueFromKey`

> ⚠ **Two subscriber scopes:** ParentOU subscribers (ParentOU[i]/Subscriber[j]) and ChildOU subscribers (ParentOU[i]/ChildOU[k]/Subscriber[j]) — each produces its own XSLT variant.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_ASRM_INVOKE_SIM` |
| Full Path | `Rules.OMConsumers.OMXFM.Request.Request_ASRM_INVOKE_SIM` |
| Priority | 5 |
| forwardChain | true |
| Rule Type | Request Dispatch — sends outbound JMS event to ASRM FM |
| Author | chch |
| Backend System | ASRM (Amdocs Resource Manager) |
| Operation | UnifiedResourceActivity (SIM card) |

---

## §3 — Working Memory — Declared Objects

| Variable | Type Path | Role |
|----------|-----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Master order — customer hierarchy, subscriber data, OrderType |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current step — ACTIVITY parameter, RESOURCE_NAME parameter, Response[], RequestCount |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity to the order's current execution point |
| 2 | `orderCurrentActivity.ActivityID == "ASRM_INVOKE_SIM"` | Targets only SIM activities |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "ASRM_INVOKE_SIM"` | Order-level double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires on fresh/ready activity |

---

## §5 — Execution Flow Diagram

1. **Parameter Parsing** — iterate `Parameter[]` with `tib:tokenize(param,"=")` → extract `ACTIVITY` value (RESERVE / PREACTIVATE / ACTIVATE). Also call `GetActivityParameterValueFromKey(orderCurrentActivity, "RESOURCE_NAME")` to get optional override resource name.
2. **ParentOU Loop** — for each `ParentOU[i] → Subscriber[j]`:
   - Skip if already has SUCCESS response for this refId (CompletionStatus=2)
   - Run PreExecCheck XPath via `GetXMLForSubscriber` + `XPath.execute`
   - Read `simPairMsisdn` from `ResourceInfo[ResourceName="SIM_PAIR_MSISDN"]/ValuesArray`
   - Build and send `ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY` event (Variant ①) with dynamic Type and Value
   - Send Logger audit event (if AllowWriteLog)
   - Increment RequestCount (if not resubmit)
3. **ChildOU Loop** — same logic for `ParentOU[i] → ChildOU[k] → Subscriber[j]` using Variant ②
4. **Status Update** — if any request sent → `Status = IN_PROGRESS`, `SendDataToDB`; if all skipped → `SkipActivity("4")` → Status = SKIPPED
5. **Exception Handling** — `catch(Exception ae)` → `HandleActivityException` → Status = ERROR, OrderStatus = FAILED

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### §6.1 — Initialization & Parameter Extraction

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
String activityValue = null;

// Parse ACTIVITY=VALUE from Parameter[]
for (int iParam=0; iParam<orderCurrentActivity.Parameter@length; iParam++) {
    String param      = XPath.evalAsString(/* Parameter[(iParam+1)] */);
    String paramKey   = XPath.evalAsString(/* tib:tokenize(param,"=")[1] */);
    String paramValue = XPath.evalAsString(/* tib:tokenize(param,"=")[2] */);
    if(String.equals("ACTIVITY", paramKey)) activityValue = paramValue;
}

// Fetch optional RESOURCE_NAME override (separate helper, not tokenize loop)
String resourceName = RuleFunctions.Helpers.GetActivityParameterValueFromKey(
    orderCurrentActivity, "RESOURCE_NAME");
```

### §6.2 — simPairMsisdn Read (per subscriber, before XSLT)

```java
// Determines whether SIM resource type is "SIM" or "STARTER PACK"
String simPairMsisdn = XPath.evalAsString(
    "xpath://... $orderRequest/OrderData/Customer/ParentOU[(number($i)+1)]
                /Subscriber[(number($j)+1)]/ResourceInfo[ResourceName=\"SIM_PAIR_MSISDN\"]/ValuesArray");
// Variant ②: navigates through ChildOU[(number($k)+1)]
```

### §6.3 — Status Transition

```java
if(!isSkipped) {
    orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false); // IN_PROGRESS
    RuleFunctions.Helpers.SendDataToDB(orderRequest);
} else {
    RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4"); // SKIPPED
}
```

---

## §7 — Data Extraction

### Parameter Parsing

| Parameter Key | Extraction Method | Variable | Purpose |
|---------------|-------------------|----------|---------|
| `ACTIVITY` | `tib:tokenize(param, "=")[2]` | `activityValue` | SIM operation: RESERVE / PREACTIVATE / ACTIVATE |
| `RESOURCE_NAME` | `GetActivityParameterValueFromKey(…, "RESOURCE_NAME")` | `resourceName` | Optional override for the ResourceInfo key to use as SIM value |

### SIM Pair MSISDN Read

For each subscriber, `ResourceInfo[ResourceName="SIM_PAIR_MSISDN"]/ValuesArray` is read before the XSLT invocation. Its presence determines whether the resource type is `SIM` or `STARTER PACK`.

### Resource Value Fallback Chain

| Priority | Condition | Source XPath |
|----------|-----------|--------------|
| 1 (highest) | `resourceName != ""` | `ResourceInfo[ResourceName=$resourceName]/ValuesArray` |
| 2 | `ResourceInfo["SIM"]/ValuesArray length > 0` | `ResourceInfo[ResourceName="SIM"]/ValuesArray` |
| 3 (fallback) | otherwise | `ExtendedInfo[Name='ICC_ID']/Value` |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

| OrderType | Resource Type Sent | Note |
|-----------|--------------------|------|
| `51` | `STARTER PACK` | Starter pack order — always uses STARTER PACK regardless of SIM pairing |
| Any other + SIM_PAIR_MSISDN is empty | `SIM` | Standard SIM reservation/activation |
| Any other + SIM_PAIR_MSISDN is non-empty | `STARTER PACK` | Paired SIM with MSISDN → treated as starter pack |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel URI | Destination | Event Type | Purpose |
|-----------|-------------|-------------|------------|---------|
| [OUTBOUND] | `/Channels/OMXFMConnectionRequest` | `ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY` | `Events.OMConsumers.OMXFM.Request.ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY` | ASRM SIM resource operation |
| [OUTBOUND] | `/Channels/LogConnection` | `AuditLog` | `Events.OMConsumers.OMXESB.Logger` | Audit trail per subscriber request |

### §8.3 — Backend API Details

| Attribute | Value |
|-----------|-------|
| System | ASRM — Amdocs Resource Manager 3G |
| Operation | UnifiedResourceActivity (SIM) |
| Resource Type | Dynamic: `SIM` or `STARTER PACK` |
| Schema | `amdocs.rm3g.interfaces.datatypes.UnifiedResourceActivityInfo` |
| Correlation | JMSCorrelationID = OMXTrackingId; RefID = subscriber RefId |

### §8.4 — BE Working Memory Dependencies

| Field | Direction | Purpose |
|-------|-----------|---------|
| `orderRequest.OrderData.OMXTrackingId` | [READ] | JMSCorrelationID, audit ESBUUID |
| `orderRequest.OrderData.OrderType` | [READ] | Drives SIM vs STARTER PACK type selection |
| `Subscriber[j].ResourceInfo[ResourceName="SIM_PAIR_MSISDN"]/ValuesArray` | [READ] | Determines SIM vs STARTER PACK for non-51 OrderTypes |
| `Subscriber[j].ResourceInfo[ResourceName=$resourceName]/ValuesArray` | [READ] | SIM card ID (if RESOURCE_NAME param set) |
| `Subscriber[j].ResourceInfo[ResourceName="SIM"]/ValuesArray` | [READ] | SIM card ICCID fallback 1 |
| `Subscriber[j].ExtendedInfo[Name='ICC_ID']/Value` | [READ] | SIM card ICCID fallback 2 |
| `orderCurrentActivity.Status` | [WRITE] | Set to IN_PROGRESS (1) or SKIPPED (4) |
| `orderCurrentActivity.RequestCount` | [WRITE] | Incremented per dispatched request |

### §8.5 — ExtendedInfo / ResourceInfo Fields Required

| Field | Type | Required/Optional | Purpose |
|-------|------|-------------------|---------|
| `ResourceInfo[ResourceName="SIM_PAIR_MSISDN"]/ValuesArray` | ResourceInfo | Optional | Presence switches resource type from SIM → STARTER PACK |
| `ResourceInfo[ResourceName=$resourceName]/ValuesArray` | ResourceInfo | Optional | Explicit SIM identifier override |
| `ResourceInfo[ResourceName="SIM"]/ValuesArray` | ResourceInfo | Optional | Standard SIM ICCID |
| `ExtendedInfo[Name='ICC_ID']/Value` | ExtendedInfo | Fallback | ICC_ID when no SIM ResourceInfo exists |

### §8.6 — Global Variable Dependencies

| Global Variable Path | Purpose |
|----------------------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | If "true", include User/Password in request |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL value |
| `OMX_OM/WritePayload` | If "true", include payload in audit log |
| `OMX_COMMON/_SharedResources/Common/Log/OrderTypeFilter` | Order types to suppress audit logging |

---

## §9 — Detailed Payload Build (XSLT Decomposition)

### §9.1 — XSLT Parameter Binding

| Parameter | Bound From | Notes |
|-----------|------------|-------|
| `$orderRequest` | Working memory concept | Full order request tree |
| `$refId` | `subscriber.RefId` | Per-subscriber iteration variable |
| `$globalVariables` | BE global variables | IsEnableUserPass, logging config |
| `$activityValue` | Parsed from ACTIVITY parameter | RESERVE / PREACTIVATE / ACTIVATE |
| `$simPairMsisdn` | ResourceInfo["SIM_PAIR_MSISDN"]/ValuesArray (read before XSLT) | Drives Type xsl:choose |
| `$resourceName` | `GetActivityParameterValueFromKey(…, "RESOURCE_NAME")` | Optional override for SIM Value source |
| `$i` | ParentOU loop counter (0-based) | XPath: `number($i)+1` |
| `$j` | Subscriber loop counter (0-based) | XPath: `number($j)+1` |
| `$k` | ChildOU loop counter (Variant ② only) | XPath: `number($k)+1` |

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$refId` | Always |
| `UserName` | `$orderRequest/OrderData/User` | `IsEnableUserPass='true'` AND User exists |
| `PassWord` | `$orderRequest/OrderData/Password` | `IsEnableUserPass='true'` AND Password exists |
| `OrderType` | `$orderRequest/OrderData/OrderType` | If OrderType exists |

### §9.5 — Resource Type Selection (xsl:choose)

| Condition | `ns1:Type` Value |
|-----------|-----------------|
| `OrderType = "51"` | `STARTER PACK` |
| `OrderType != "51" AND string-length(tib:trim($simPairMsisdn)) = 0` | `SIM` |
| `OrderType != "51" AND string-length(tib:trim($simPairMsisdn)) > 0` | `STARTER PACK` |

### §9.6 — Resource Value Selection (xsl:choose with 3 tiers)

| Priority | Condition | Source XPath |
|----------|-----------|--------------|
| 1 | `$resourceName != ""` | `ResourceInfo[ResourceName=$resourceName]/ValuesArray` |
| 2 | `string-length(ResourceInfo["SIM"]/ValuesArray) > 0` | `ResourceInfo[ResourceName="SIM"]/ValuesArray` |
| 3 (otherwise) | fallback | `ExtendedInfo[Name='ICC_ID']/Value` |

### §9.7 — Complete Generated XML Example (RESERVE, OrderType=1, standard SIM)

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20260723-001</JMSCorrelationID>
    <OrderID>ORD-12345</OrderID>
    <RefID>SUB-REF-001</RefID>
    <OrderType>1</OrderType>
    <payload>
      <ns2:UnifiedResourceActivityInfo
        xmlns:ns2="www.tibco.com/plugin/java/xmlSchema/amdocs.rm3g.interfaces.datatypes.UnifiedResourceActivityInfo">
        <ns2:Activity>
          <ns:ActivityName>RESERVE</ns:ActivityName>
        </ns2:Activity>
        <ns2:UnifiedResource>
          <ns1:Type>SIM</ns1:Type>     <!-- simPairMsisdn empty AND OrderType!=51 -->
          <ns1:Value>8966011234567890123</ns1:Value>  <!-- from ResourceInfo["SIM"]/ValuesArray -->
        </ns2:UnifiedResource>
      </ns2:UnifiedResourceActivityInfo>
    </payload>
  </event>
</createEvent>
```

### §9.8 — XSLT Stylesheet Source

**Variant ①: ParentOU Subscriber** (params: i, j — no k)

```xml
<xsl:stylesheet
  xmlns:ns2="www.tibco.com/plugin/java/xmlSchema/amdocs.rm3g.interfaces.datatypes.UnifiedResourceActivityInfo"
  xmlns:ns1="www.tibco.com/plugin/java/xmlSchema/amdocs.rm3g.interfaces.datatypes.RMEntityIdInfo"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="www.tibco.com/plugin/java/xmlSchema/amdocs.rm3g.interfaces.datatypes.ActivityInfo"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
  version="1.0">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>
  <xsl:param name="refId"/>
  <xsl:param name="globalVariables"/>
  <xsl:param name="activityValue"/>   <!-- RESERVE / PREACTIVATE / ACTIVATE -->
  <xsl:param name="simPairMsisdn"/>   <!-- read before XSLT from ResourceInfo[SIM_PAIR_MSISDN] -->
  <xsl:param name="resourceName"/>    <!-- optional RESOURCE_NAME param override -->
  <xsl:param name="i"/>               <!-- 0-based ParentOU index -->
  <xsl:param name="j"/>               <!-- 0-based Subscriber index -->

  <xsl:template match="/">
    <createEvent><event>
      <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      <RefID><xsl:value-of select="$refId"/></RefID>

      <!-- Credential gate -->
      <xsl:if test="$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass='true'">
        <xsl:if test="$orderRequest/OrderData/User">
          <UserName><xsl:value-of select="$orderRequest/OrderData/User"/></UserName>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/Password">
          <PassWord><xsl:value-of select="$orderRequest/OrderData/Password"/></PassWord>
        </xsl:if>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderType">
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      </xsl:if>

      <payload>
        <ns2:UnifiedResourceActivityInfo>
          <ns2:Activity>
            <ns:ActivityName><xsl:value-of select="$activityValue"/></ns:ActivityName>
          </ns2:Activity>
          <ns2:UnifiedResource>
            <!-- Type: OrderType=51 → STARTER PACK; else simPairMsisdn drives SIM vs STARTER PACK -->
            <xsl:choose>
              <xsl:when test="$orderRequest/OrderData/OrderType='51'">
                <ns1:Type>STARTER PACK</ns1:Type>
              </xsl:when>
              <xsl:when test="$orderRequest/OrderData/OrderType!='51' and string-length(tib:trim($simPairMsisdn))=0">
                <ns1:Type>SIM</ns1:Type>
              </xsl:when>
              <xsl:when test="$orderRequest/OrderData/OrderType!='51' and string-length(tib:trim($simPairMsisdn))>0">
                <ns1:Type>STARTER PACK</ns1:Type>
              </xsl:when>
            </xsl:choose>
            <!-- Value: 3-tier fallback chain -->
            <xsl:choose>
              <xsl:when test="$resourceName!=''">
                <xsl:if test="$orderRequest/OrderData/Customer/ParentOU[(number($i)+1)]/Subscriber[(number($j)+1)]/ResourceInfo[ResourceName=$resourceName]/ValuesArray">
                  <ns1:Value><xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[(number($i)+1)]/Subscriber[(number($j)+1)]/ResourceInfo[ResourceName=$resourceName]/ValuesArray"/></ns1:Value>
                </xsl:if>
              </xsl:when>
              <xsl:when test="string-length($orderRequest/OrderData/Customer/ParentOU[(number($i)+1)]/Subscriber[(number($j)+1)]/ResourceInfo[ResourceName='SIM']/ValuesArray)>0">
                <ns1:Value><xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[(number($i)+1)]/Subscriber[(number($j)+1)]/ResourceInfo[ResourceName='SIM']/ValuesArray"/></ns1:Value>
              </xsl:when>
              <xsl:otherwise>
                <xsl:if test="$orderRequest/OrderData/Customer/ParentOU[(number($i)+1)]/Subscriber[(number($j)+1)]/ExtendedInfo[Name='ICC_ID']/Value">
                  <ns1:Value><xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[(number($i)+1)]/Subscriber[(number($j)+1)]/ExtendedInfo[Name='ICC_ID']/Value"/></ns1:Value>
                </xsl:if>
              </xsl:otherwise>
            </xsl:choose>
          </ns2:UnifiedResource>
        </ns2:UnifiedResourceActivityInfo>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**Variant ②: ChildOU Subscriber** — identical structure; all subscriber XPaths navigate through `ChildOU[(number($k)+1)]` and adds `$k` parameter.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

*Variant ① (ParentOU) shown. Variant ② differs only in subscriber XPath depth.*

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                          [Always]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId                [Always]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID                      [Always]
    ├── RefID                    ← $refId                                                [Always]
    ├── UserName                 ← $orderRequest/OrderData/User                         [Credential-gated: IsEnableUserPass='true' AND User exists]
    ├── PassWord                 ← $orderRequest/OrderData/Password                     [Credential-gated: IsEnableUserPass='true' AND Password exists]
    ├── OrderType                ← $orderRequest/OrderData/OrderType                    [Conditional: if OrderType exists]
    └── payload
        └── ns2:UnifiedResourceActivityInfo
            ├── ns2:Activity
            │   └── ns:ActivityName    ← $activityValue                                 [Always]
            └── ns2:UnifiedResource
                ├── ns1:Type           [Conditional: xsl:choose on OrderType + simPairMsisdn]
                │   ├── when OrderType='51'                         → "STARTER PACK"    [Static]
                │   ├── when OrderType!='51' AND simPairMsisdn=""  → "SIM"             [Static]
                │   └── when OrderType!='51' AND simPairMsisdn!="" → "STARTER PACK"    [Static]
                └── ns1:Value          [Conditional: 3-tier fallback xsl:choose]
                    ├── 1st: $resourceName!=""                      ← ResourceInfo[$resourceName]/ValuesArray
                    ├── 2nd: ResourceInfo["SIM"]/ValuesArray len>0  ← ResourceInfo["SIM"]/ValuesArray
                    └── 3rd: otherwise                              ← ExtendedInfo["ICC_ID"]/Value
```

**Legend:**
- `←` green XPath source
- `→` orange static literal
- `[Always]` unconditional
- `[Conditional: ...]` inside xsl:if/xsl:choose
- `[Credential-gated]` behind IsEnableUserPass check

---

## §11 — Audit Logging

Identical Logger XSLT to `ASRM_INVOKE_MSISDN`. See §11 of that document for full field table.

| Field | Source | Condition |
|-------|--------|-----------|
| `ESBUUID` | `$orderRequest/OrderData/OMXTrackingId` | If OMXTrackingId exists |
| `PROCESS_ID` | `concat($pid, "_REQ")` | Always |
| `OPERATION_NAME` | `$operatorname` (ASRM_INVOKE_SIM_RESERVE etc.) | Always |
| `AUDIT_TRACE` | `concat("Request Sent for RefId ", $refId)` | Always |
| `payload/ns:ServicePayload` | copy-of($reqEvent) | Only if `OMX_OM/WritePayload = "true"` |

---

## §12 — Activity Status Management

| Trigger | Code | Status | Method |
|---------|------|--------|--------|
| Rule fires | 0 | WAITING | Pre-condition |
| At least one request sent | 1 | IN_PROGRESS | `GetActivityStatusString("1", false)` |
| All skipped by PreExecCheck | 4 | SKIPPED | `SkipActivity(…, "4")` |
| Exception caught | 3 | ERROR | `HandleActivityException` |

---

## §13 — Exception / Error Handling

Identical to `ASRM_INVOKE_MSISDN`: entire THEN block wrapped in try/catch. `HandleActivityException` builds error response code, sets ERROR status, fires error Logger event, optionally routes to ExceptionActivity, calls SendDataToDB.

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|----------|--------|---------|
| `RuleFunctions.Helpers.GetActivityParameterValueFromKey(activity, "RESOURCE_NAME")` | String | **New in this rule:** retrieves the value of a named parameter from the activity's Parameter array |
| `RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)` | String | Serializes subscriber XML for PreExecCheck XPath evaluation |
| `RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` | String | Same for ChildOU context |
| `RuleFunctions.Helpers.AllowWriteLog(orderType)` | boolean | Log filter by order type |
| `RuleFunctions.Helpers.GetActivityStatusString("1", false)` | "IN_PROGRESS" | Status code mapping |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | void | Persist order/activity state |
| `RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")` | void | Set SKIPPED, advance next activity pointer |
| `RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")` | void | Full error handling chain |

---

## §15 — Function Dependency Tree

```text
Request_ASRM_INVOKE_SIM (rule)
├── Instance.getByExtIdByUri(...)
├── XPath.evalAsString(tib:tokenize ...)              [parameter parsing]
├── RuleFunctions.Helpers.GetActivityParameterValueFromKey(activity, "RESOURCE_NAME")
├── XPath.evalAsString(ResourceInfo[SIM_PAIR_MSISDN]) [simPairMsisdn read]
├── RuleFunctions.Helpers.GetXMLForSubscriber(...)
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(...)
├── XPath.execute(preExecCheck, xml, ns)
├── Event.createEvent(xslt://ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY)
├── Event.Ext.sendEventImmediate(reqEvent)
├── RuleFunctions.Helpers.AllowWriteLog(orderType)
│   └── System.getGlobalVariableAsString(OrderTypeFilter)
├── Event.createEvent(xslt://Logger)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)
│   ├── RuleFunctions.Helpers.GetActivityStatusString(...)
│   ├── RuleFunctions.Helpers.GetOrderStatusString(...)
│   └── RuleFunctions.Helpers.SendDataToDB(...)
└── RuleFunctions.Helpers.HandleActivityException(...)
    ├── RuleFunctions.Helpers.GetActivityStatusString("3", false)
    ├── RuleFunctions.Helpers.SetResponseCode(...)
    ├── Event.Ext.routeToImmediate(Logger/ErrorLog)
    └── RuleFunctions.Helpers.SendDataToDB(...)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Support RESERVE, PREACTIVATE, ACTIVATE SIM operations.
- **R2** — Implement 3-tier SIM value resolution: RESOURCE_NAME param → ResourceInfo["SIM"] → ExtendedInfo["ICC_ID"].
- **R3** — Implement OrderType=51 / SIM_PAIR_MSISDN presence logic for resource Type selection.
- **R4** — Read RESOURCE_NAME from activity parameters using key-based lookup (not positional tokenize).
- **R5** — Support both ParentOU and ChildOU subscriber hierarchies.
- **R6** — Skip subscribers with existing SUCCESS responses (idempotent resubmission).

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| RESOURCE_NAME parameter lookup method differs from ACTIVITY parsing | [HIGH] | `GetActivityParameterValueFromKey` must be available in target stack; it searches by key, not by position |
| SIM_PAIR_MSISDN read before XSLT (not inside XSLT) | [MEDIUM] | Value is passed as a pre-computed XSLT parameter — migration must preserve this read-before-invoke pattern |
| OrderType=51 (Starter Pack) special casing | [MEDIUM] | Test with OrderType 51 to verify STARTER PACK is always sent regardless of SIM_PAIR_MSISDN |
| 3-tier Value fallback may silently send wrong ICCID | [LOW] | Validate that when RESOURCE_NAME is blank and ResourceInfo["SIM"] is absent, ICC_ID is the correct fallback |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_ASRM_INVOKE_SIM {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "ASRM_INVOKE_SIM";
        orderRequest.ProcessFlow.NextActivityID == "ASRM_INVOKE_SIM";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
            int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
            String activityValue = null;

            // Parse ACTIVITY=VALUE parameter
            for (int iParam=0; ...) { ... activityValue = paramValue; }

            // Read optional RESOURCE_NAME override
            String resourceName = RuleFunctions.Helpers.GetActivityParameterValueFromKey(
                orderCurrentActivity, "RESOURCE_NAME");

            String operatorname = String.format("%s_%s", orderCurrentActivity.ActivityID, activityValue);
            boolean isSkipped = true;

            // === ParentOU Loop ===
            for (int i=0; i<iPOULen; i++) {
                for(int j=0; j<iSubscriberLen; j++) {
                    String refId = ...Subscriber[j].RefId;
                    // Skip if SUCCESS response exists for this refId
                    // Run PreExecCheck
                    if(String.equals(chkRes, "true")) {
                        // Read SIM_PAIR_MSISDN for type determination
                        String simPairMsisdn = XPath.evalAsString(/* ResourceInfo[SIM_PAIR_MSISDN]/ValuesArray */);
                        Events.OMConsumers.OMXFM.Request.ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY reqEvent =
                            Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY}}"
                            /* Variant ① XSLT — see §9.8:
                               Type: OrderType=51→STARTER PACK; else simPairMsisdn drives SIM/STARTER PACK
                               Value: RESOURCE_NAME→ResourceInfo["SIM"]→ExtendedInfo["ICC_ID"] */);
                        Event.Ext.sendEventImmediate(reqEvent);
                        // Audit log (see §11)
                        if(!isActResub) orderCurrentActivity.RequestCount++;
                        isSkipped = false;
                    }
                }
                // === ChildOU Loop (Variant ② XSLT, adds $k parameter) ===
                for(int k=0; k<iCOULen; k++) { ... }
            }
            if(!isSkipped) {
                orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch(Exception ae) {
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 — Response Message Rule

### §19.1 — Overview

`RuleFunctions.OrderResponse.Response_ASRM_INVOKE_SIM` — identical logic to `Response_ASRM_INVOKE_MSISDN`. Parses ASRM response, creates `ASRM_InvokeUnifiedResourceRes` concept, appends to `currActivity.Response[]`, logs audit (_RES suffix), evaluates fan-in completion.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order tracking, log filtering |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY` | ASRM response — ResponseCode, ResponseMsg, CompletionStatus, RefID |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; fan-in via RequestCount |

### §19.4 — Response Completion Logic (Fan-in)

```java
int successResponseCount = XPath.evalAsInt(
    "count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = \"000\"])");
if(currActivity.RequestCount == successResponseCount) return "true";
else return "false";
```

`PROCESS_ID` uses `_RES` suffix in the response audit log (vs `_REQ` in request).

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
