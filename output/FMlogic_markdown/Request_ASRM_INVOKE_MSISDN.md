# Request_ASRM_INVOKE_MSISDN

> ASRM Unified Resource Activity — MSISDN Operations (LOCK / RESERVE / PREACTIVATE / ACTIVATE / PORT IN / PORT OUT)

**Backend:** ASRM | **Channel:** OMXFMConnectionRequest | **Priority:** 5 | **forwardChain:** true | **Generated:** 2026-07-23

---

## §1 — Overview & Purpose

This rule fires when the order orchestration engine reaches an activity with `ActivityID = ASRM_INVOKE_MSISDN` and status `WAITING`. It sends a **UnifiedResourceActivity** request to ASRM (Amdocs Resource Manager 3G) for every eligible subscriber in the order — both at ParentOU and ChildOU levels.

The specific MSISDN operation is driven by the `ACTIVITY` parameter defined in the ProcessConfig, which can be one of: **LOCK, RESERVE, PREACTIVATE, ACTIVATE, PORT IN, PORT OUT RELEASE, PORT IN REVERSE, PORT OUT REVERSE, ACTIVATED**.

For PORT IN and PORT OUT RELEASE activities, zone codes stored as ASCII integers in the order are decoded to text using `OMXUtils.asciiCodeToText` before being sent to ASRM. Subscribers that already have a SUCCESS response (CompletionStatus=2) are skipped, enabling safe resubmission.

> ⚠ **Two subscriber scopes:** This rule handles both *ParentOU subscribers* (ParentOU[i]/Subscriber[j]) and *ChildOU subscribers* (ParentOU[i]/ChildOU[k]/Subscriber[j]), producing two XSLT variants that differ only in the subscriber XPath navigation path.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_ASRM_INVOKE_MSISDN` |
| Full Path | `Rules.OMConsumers.OMXFM.Request.Request_ASRM_INVOKE_MSISDN` |
| Priority | 5 |
| forwardChain | true |
| Rule Type | Request Dispatch — sends outbound JMS event to ASRM FM |
| Author | chch |
| Backend System | ASRM (Amdocs Resource Manager) |
| Operation | UnifiedResourceActivity (MSISDN) |

---

## §3 — Working Memory — Declared Objects

| Variable | Type Path | Role |
|----------|-----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Master order concept — contains customer hierarchy, subscriber data, order metadata |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current orchestration step — holds status, parameters, response array, RequestCount |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity instance to the current order's next step |
| 2 | `orderCurrentActivity.ActivityID == "ASRM_INVOKE_MSISDN"` | Ensures only ASRM MSISDN activities fire this rule |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "ASRM_INVOKE_MSISDN"` | Double-check at the order level |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires on a fresh/ready activity |

---

## §5 — Execution Flow Diagram

```
1. Parameter Parsing → iterate Parameter[], tib:tokenize(param,"=") → extract ACTIVITY value
2. Zone Code Decode → if PORT IN / PORT OUT RELEASE: OMXUtils.asciiCodeToText(DonorZoneCode, RCPZoneCode)
3. Build operatorname = ActivityID + "_" + activityValue (for audit log)
4. ParentOU Loop → for each ParentOU[i] → Subscriber[j]:
   a. Skip if Response[].ReferenceId == refId && CompletionStatus == 2
   b. Run PreExecCheck via GetXMLForSubscriber + XPath.execute
   c. If passes: send ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY event (Variant ①)
   d. Send Logger audit event (if AllowWriteLog)
   e. Increment RequestCount (if not resubmit)
5. ChildOU Loop → for each ParentOU[i] → ChildOU[k] → Subscriber[j]: same logic (Variant ②)
6. If any request sent → Status = IN_PROGRESS, SendDataToDB
   Else all skipped → SkipActivity("4") → Status = SKIPPED, advance next activity pointer
7. Exception → HandleActivityException → Status = ERROR, OrderStatus = FAILED
```

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### §6.1 Initialization

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
Concepts.OM.ProcessConfig.Activity nextAct =
    Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
```

### §6.2 Parameter Parsing

```java
for (int iParam=0; iParam<orderCurrentActivity.Parameter@length; iParam++) {
    String param      = XPath.evalAsString(/* xpath: Parameter[(iParam+1)] */);
    String paramKey   = XPath.evalAsString(/* xpath: tib:tokenize(param,"=")[1] */);
    String paramValue = XPath.evalAsString(/* xpath: tib:tokenize(param,"=")[2] */);
    if(String.equals("ACTIVITY", paramKey)) activityValue = paramValue;
}
```

### §6.3 Zone Code Decode

```java
if(String.equals(activityValue, "PORT IN") || String.equals(activityValue, "PORT OUT RELEASE")) {
    donorZoneText = OMXUtils.asciiCodeToText(Number.intValue(MNPInfo.DonorZoneCode, 10));
    rcpZoneText   = OMXUtils.asciiCodeToText(Number.intValue(MNPInfo.RCPZoneCode, 10));
}
```

### §6.4 Status Transition

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

### Parameter Parsing — tib:tokenize

Parameters in `orderCurrentActivity.Parameter[]` use `KEY=VALUE` format. Split using `tib:tokenize($param, "=")`:

| Token Index | Extracted | Variable |
|-------------|-----------|----------|
| [1] | Key (e.g., `ACTIVITY`) | `paramKey` |
| [2] | Value (e.g., `LOCK`, `RESERVE`) | `paramValue` → `activityValue` |

### Zone Code ASCII Conversion

`DonorZoneCode` and `RCPZoneCode` are stored as decimal ASCII values. `Number.intValue(code, 10)` converts to integer, then `OMXUtils.asciiCodeToText(int)` produces human-readable zone text.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

| OrderType(s) | Condition | Extra Attributes Sent |
|--------------|-----------|----------------------|
| 7, 57, 12001, 21, 11028, 11029, 12016, 12017, 11030 | Standard PORT IN | DONOR_OPERATOR, DONOR_ZONE, RECIPIENT_OPERATOR, RECIPIENT_ZONE |
| 8, 9, 58, 59 | PORT IN when `MSISDN_TRUE_RES = "N"` | DONOR_OPERATOR, DONOR_ZONE, RECIPIENT_OPERATOR, RECIPIENT_ZONE |
| Any | LOCK | DEALER |
| Any | PORT OUT RELEASE | RECIPIENT_OPERATOR, RECIPIENT_ZONE |
| Any | PORT IN/OUT REVERSE | RECIPIENT_OPERATOR (from ExtendedInfo DONOR_OPERATOR) |
| Any | ACTIVATED | SOURCE_COMPANY (ExtendedInfo COMPANY_CODE), TARGET_COMPANY = "06" |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel URI | Destination | Event Type | Purpose |
|-----------|-------------|-------------|------------|---------|
| [OUTBOUND] | `/Channels/OMXFMConnectionRequest` | `ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY` | `Events.OMConsumers.OMXFM.Request.ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY` | ASRM MSISDN resource operation |
| [OUTBOUND] | `/Channels/LogConnection` | `AuditLog` | `Events.OMConsumers.OMXESB.Logger` | Audit trail per subscriber request |

### §8.3 — Backend API Details

| Attribute | Value |
|-----------|-------|
| System | ASRM — Amdocs Resource Manager 3G |
| Operation | UnifiedResourceActivity |
| Resource Type | MSISDN (static) |
| Schema | `amdocs.rm3g.interfaces.datatypes.UnifiedResourceActivityInfo` |
| Correlation | JMSCorrelationID = OMXTrackingId; RefID = subscriber RefId |
| Event base | Extends `/Events/Base/OMXRequestBaseEvent` |

### §8.4 — BE Working Memory Dependencies

| Field | Direction | Purpose |
|-------|-----------|---------|
| `orderRequest.OrderData.OMXTrackingId` | [READ] | JMSCorrelationID and audit ESBUUID |
| `orderRequest.OrderData.OrderID` | [READ] | Order identifier in request |
| `orderRequest.OrderData.OrderType` | [READ] | Drives PORT IN attribute selection; log filter |
| `orderRequest.OrderData.DealerCode` | [READ] | DEALER attribute for LOCK |
| `orderRequest.OrderData.MNPInfo.*` | [READ] | DonorOperator, DonorZoneCode, RCPOperator, RCPZoneCode |
| `orderCurrentActivity.Status` | [WRITE] | Set to IN_PROGRESS (1) or SKIPPED (4) |
| `orderCurrentActivity.RequestCount` | [WRITE] | Incremented per dispatched request |

### §8.5 — ExtendedInfo Fields Required

| Field Name | Required/Optional | Activity | Usage |
|------------|-------------------|----------|-------|
| `DONOR_OPERATOR` | [Conditional] | PORT IN REVERSE, PORT OUT REVERSE | Sent as RECIPIENT_OPERATOR to ASRM |
| `COMPANY_CODE` | [Conditional] | ACTIVATED | Sent as SOURCE_COMPANY to ASRM |
| `MSISDN_TRUE_RES` | [Conditional] | PORT IN (OrderType 8/9/58/59) | If = "N", triggers PORT IN attribute population |

### §8.6 — Global Variable Dependencies

| Global Variable Path | Purpose |
|---------------------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | If "true", include User/Password in request |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL value |
| `OMX_OM/WritePayload` | If "true", include payload in audit log |
| `OMX_COMMON/_SharedResources/Common/Log/OrderTypeFilter` | Order types that suppress audit logging |

---

## §9 — Detailed Payload Build (XSLT Decomposition)

### §9.1 — XSLT Parameter Binding

| Parameter | Bound From | Notes |
|-----------|------------|-------|
| `$orderRequest` | Working memory concept | Full order request tree |
| `$refId` | `subscriber.RefId` | Per-subscriber iteration variable |
| `$globalVariables` | BE global variables | IsEnableUserPass, logging config |
| `$activityValue` | Parsed from Parameter (ACTIVITY=…) | Drives xsl:choose branching |
| `$i` | Loop counter — ParentOU index | 0-based; XPath uses `number($i)+1` |
| `$j` | Loop counter — Subscriber index | 0-based |
| `$k` | Loop counter — ChildOU index (Variant ② only) | 0-based |
| `$donorZoneText` | `OMXUtils.asciiCodeToText(DonorZoneCode)` | PORT IN / PORT OUT RELEASE only |
| `$rcpZoneText` | `OMXUtils.asciiCodeToText(RCPZoneCode)` | PORT IN / PORT OUT RELEASE only |

### §9.2 — Event Container

Event type: `Events.OMConsumers.OMXFM.Request.ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY`  
Channel: `/Channels/OMXFMConnectionRequest` → destination `ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY`

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$refId` | Always |
| `UserName` | `$orderRequest/OrderData/User` | `IsEnableUserPass='true'` AND User exists |
| `PassWord` | `$orderRequest/OrderData/Password` | `IsEnableUserPass='true'` AND Password exists |
| `OrderType` | `$orderRequest/OrderData/OrderType` | If OrderType element exists |

### §9.5 — Conditional ActivityAttributes (xsl:choose)

| activityValue | Attributes Emitted | Source |
|---------------|--------------------|--------|
| **LOCK** | DEALER | `$orderRequest/OrderData/DealerCode` |
| **PORT IN** (qualifying order types) | DONOR_OPERATOR, DONOR_ZONE, RECIPIENT_OPERATOR, RECIPIENT_ZONE | MNPInfo + decoded zone texts |
| **PORT OUT RELEASE** | RECIPIENT_OPERATOR, RECIPIENT_ZONE | MNPInfo.RCPOperator, rcpZoneText |
| **PORT IN/OUT REVERSE** | RECIPIENT_OPERATOR | `ExtendedInfo[Name="DONOR_OPERATOR"]/Value` |
| **ACTIVATED** | SOURCE_COMPANY, TARGET_COMPANY="06" | `ExtendedInfo[Name="COMPANY_CODE"]/Value`; "06" static |
| **RESERVE, PREACTIVATE, ACTIVATE** | (none) | No ActivityAttributes block |

### §9.7 — Complete Generated XML Example (LOCK)

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20260723-001</JMSCorrelationID>
    <OrderID>ORD-12345</OrderID>
    <RefID>SUB-REF-001</RefID>
    <OrderType>1</OrderType>
    <payload>
      <ns2:UnifiedResourceActivityInfo xmlns:ns2="www.tibco.com/...UnifiedResourceActivityInfo">
        <ns2:Activity>
          <ns:ActivityName>LOCK</ns:ActivityName>
        </ns2:Activity>
        <ns2:ActivityAttributes>
          <ns3:AttrName>DEALER</ns3:AttrName>
          <ns3:AttrValue>DLR-001</ns3:AttrValue>
        </ns2:ActivityAttributes>
        <ns2:UnifiedResource>
          <ns1:Type>MSISDN</ns1:Type>
          <ns1:Value>0812345678</ns1:Value>
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
  xmlns:ns3="www.tibco.com/plugin/java/xmlSchema/amdocs.rm3g.interfaces.datatypes.AttributesData"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions" version="1.0">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>   <!-- full order concept -->
  <xsl:param name="refId"/>          <!-- subscriber RefId -->
  <xsl:param name="globalVariables"/>
  <xsl:param name="activityValue"/>  <!-- LOCK/RESERVE/PORT IN/etc. -->
  <xsl:param name="i"/>              <!-- 0-based ParentOU index -->
  <xsl:param name="j"/>              <!-- 0-based Subscriber index -->
  <xsl:param name="donorZoneText"/>  <!-- ASCII-decoded donor zone -->
  <xsl:param name="rcpZoneText"/>    <!-- ASCII-decoded recipient zone -->
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
          <xsl:choose>
            <xsl:when test="$activityValue='LOCK'">
              <ns2:ActivityAttributes>
                <ns3:AttrName>DEALER</ns3:AttrName>
                <ns3:AttrValue><xsl:value-of select="$orderRequest/OrderData/DealerCode"/></ns3:AttrValue>
              </ns2:ActivityAttributes>
            </xsl:when>
            <xsl:when test="$activityValue='PORT IN' and (
                (OrderType=7|57|12001|21|11028|11029|12016|12017|11030)
                or (MSISDN_TRUE_RES/ValuesArray='N' and OrderType=8|9|58|59))">
              <ns2:ActivityAttributes><ns3:AttrName>DONOR_OPERATOR</ns3:AttrName>
                <ns3:AttrValue><xsl:value-of select="$orderRequest/OrderData/MNPInfo/DonorOperator"/></ns3:AttrValue></ns2:ActivityAttributes>
              <ns2:ActivityAttributes><ns3:AttrName>DONOR_ZONE</ns3:AttrName>
                <ns3:AttrValue><xsl:value-of select="$donorZoneText"/></ns3:AttrValue></ns2:ActivityAttributes>
              <ns2:ActivityAttributes><ns3:AttrName>RECIPIENT_OPERATOR</ns3:AttrName>
                <ns3:AttrValue><xsl:value-of select="$orderRequest/OrderData/MNPInfo/RCPOperator"/></ns3:AttrValue></ns2:ActivityAttributes>
              <ns2:ActivityAttributes><ns3:AttrName>RECIPIENT_ZONE</ns3:AttrName>
                <ns3:AttrValue><xsl:value-of select="$rcpZoneText"/></ns3:AttrValue></ns2:ActivityAttributes>
            </xsl:when>
            <xsl:when test="$activityValue='PORT OUT RELEASE'">
              <ns2:ActivityAttributes><ns3:AttrName>RECIPIENT_OPERATOR</ns3:AttrName>
                <ns3:AttrValue><xsl:value-of select="$orderRequest/OrderData/MNPInfo/RCPOperator"/></ns3:AttrValue></ns2:ActivityAttributes>
              <ns2:ActivityAttributes><ns3:AttrName>RECIPIENT_ZONE</ns3:AttrName>
                <ns3:AttrValue><xsl:value-of select="$rcpZoneText"/></ns3:AttrValue></ns2:ActivityAttributes>
            </xsl:when>
            <xsl:when test="$activityValue='PORT IN REVERSE' or $activityValue='PORT OUT REVERSE'">
              <ns2:ActivityAttributes><ns3:AttrName>RECIPIENT_OPERATOR</ns3:AttrName>
                <ns3:AttrValue><xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[(number($i)+1)]/Subscriber[(number($j)+1)]/ExtendedInfo[Name='DONOR_OPERATOR']/Value"/></ns3:AttrValue></ns2:ActivityAttributes>
            </xsl:when>
            <xsl:when test="$activityValue='ACTIVATED'">
              <ns2:ActivityAttributes><ns3:AttrName>SOURCE_COMPANY</ns3:AttrName>
                <ns3:AttrValue><xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[(number($i)+1)]/Subscriber[(number($j)+1)]/ExtendedInfo[Name='COMPANY_CODE']/Value"/></ns3:AttrValue></ns2:ActivityAttributes>
              <ns2:ActivityAttributes><ns3:AttrName>TARGET_COMPANY</ns3:AttrName>
                <ns3:AttrValue>06</ns3:AttrValue></ns2:ActivityAttributes>
            </xsl:when>
            <!-- RESERVE, PREACTIVATE, ACTIVATE: no ActivityAttributes -->
          </xsl:choose>
          <ns2:UnifiedResource>
            <ns1:Type>MSISDN</ns1:Type>
            <xsl:if test="$orderRequest/OrderData/Customer/ParentOU[(number($i)+1)]/Subscriber[(number($j)+1)]/MSISDN">
              <ns1:Value><xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[(number($i)+1)]/Subscriber[(number($j)+1)]/MSISDN"/></ns1:Value>
            </xsl:if>
          </ns2:UnifiedResource>
        </ns2:UnifiedResourceActivityInfo>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**Variant ②: ChildOU Subscriber** — identical structure; subscriber XPath uses `ParentOU[(number($i)+1)]/ChildOU[(number($k)+1)]/Subscriber[(number($j)+1)]` and adds `$k` parameter.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority           ← $orderRequest/OrderPriority                    [Always]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId          [Always]
    ├── OrderID               ← $orderRequest/OrderData/OrderID                [Always]
    ├── RefID                 ← $refId                                         [Always]
    ├── UserName              ← $orderRequest/OrderData/User                   [Credential-gated: IsEnableUserPass='true' AND User exists]
    ├── PassWord              ← $orderRequest/OrderData/Password               [Credential-gated: IsEnableUserPass='true' AND Password exists]
    ├── OrderType             ← $orderRequest/OrderData/OrderType              [Conditional: if OrderType exists]
    └── payload
        └── ns2:UnifiedResourceActivityInfo
            ├── ns2:Activity
            │   └── ns:ActivityName  ← $activityValue                         [Always]
            ├── ns2:ActivityAttributes                                         [Conditional: xsl:choose by activityValue]
            │   ├── when LOCK:
            │   │   └── DEALER ← $orderRequest/OrderData/DealerCode
            │   ├── when PORT IN (qualifying order types):
            │   │   ├── DONOR_OPERATOR ← MNPInfo/DonorOperator
            │   │   ├── DONOR_ZONE     ← $donorZoneText (ASCII-decoded)
            │   │   ├── RECIPIENT_OPERATOR ← MNPInfo/RCPOperator
            │   │   └── RECIPIENT_ZONE ← $rcpZoneText (ASCII-decoded)
            │   ├── when PORT OUT RELEASE:
            │   │   ├── RECIPIENT_OPERATOR ← MNPInfo/RCPOperator
            │   │   └── RECIPIENT_ZONE     ← $rcpZoneText
            │   ├── when PORT IN/OUT REVERSE:
            │   │   └── RECIPIENT_OPERATOR ← ExtendedInfo[DONOR_OPERATOR]/Value
            │   └── when ACTIVATED:
            │       ├── SOURCE_COMPANY ← ExtendedInfo[COMPANY_CODE]/Value
            │       └── TARGET_COMPANY ← "06"  [Static literal]
            └── ns2:UnifiedResource
                ├── ns1:Type   ← "MSISDN"  [Static literal] [Always]
                └── ns1:Value  ← Subscriber[j]/MSISDN       [Conditional: if MSISDN exists]
```

**Legend:**
- `← xpath` = XPath source (dynamic)
- `← "value"` = Static literal
- `[Always]` = Unconditionally emitted
- `[Conditional: ...]` = Inside `xsl:if` or `xsl:when`
- `[Credential-gated]` = Behind global variable IsEnableUserPass check

---

## §11 — Audit Logging

Logger event: `Events.OMConsumers.OMXESB.Logger` → Channel `/Channels/LogConnection` → Destination `AuditLog`

Guarded by `RuleFunctions.Helpers.AllowWriteLog(orderType)`.

| Field | Source | Condition |
|-------|--------|-----------|
| `ESBUUID` | `$orderRequest/OrderData/OMXTrackingId` | If OMXTrackingId exists |
| `PROCESS_ID` | `concat($pid, "_REQ")` (nanoTime) | Always |
| `COMPONENT_NAME` | `OMX_COMMON/Component_Name/OMX_CEP` | Always |
| `OPERATION_NAME` | `$operatorname` (ActivityID_activityValue) | Always |
| `TARGET_SYSTEM` | `OMX_COMMON/Component_Name/OMX_FM` | Always |
| `LOG_LEVEL` | `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Always |
| `AUDIT_TRACE` | `concat("Request Sent for RefId ", $refId)` | Always |
| `AUDIT_TS` | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` | Always |
| `payload/ns:ServicePayload` | `copy-of($reqEvent)` | Only if `OMX_OM/WritePayload = "true"` |

---

## §12 — Activity Status Management

| Trigger | Status Code | Status String | Method |
|---------|-------------|---------------|--------|
| Rule fires (initial) | 0 | WAITING | Pre-condition |
| At least one request sent | 1 | IN_PROGRESS | `GetActivityStatusString("1", false)` |
| All subscribers skipped | 4 | SKIPPED | `SkipActivity(…, "4")` → advances NextActivity |
| Exception caught | 3 | ERROR | `HandleActivityException` → OrderStatus = FAILED |

---

## §13 — Exception / Error Handling

The entire THEN block is wrapped in `try { ... } catch(Exception ae) { ... }`.

`RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` performs:
- Builds error code: `ComponentName + ServiceCode + OpCode + HighSeverity("03") + GenericError("999")`
- Sets `orderCurrentActivity.Status = ERROR`
- Sets `orderRequest.OrderStatus = FAILED`
- Fires error Logger event to `/Channels/LogConnection/ErrorLog` with ERROR_CODE, ERROR_MSG, ERROR_STACKTRACE
- If `ExceptionActivity` is configured, advances to exception-handling activity
- Calls `SendDataToDB` to persist failure

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|----------|--------|---------|
| `RuleFunctions.Helpers.BRMS.IsBlank(String)` | boolean | Returns true if string is null or empty |
| `RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)` | String | Serializes subscriber XML for PreExecCheck XPath evaluation |
| `RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` | String | Same for ChildOU context |
| `RuleFunctions.Helpers.AllowWriteLog(orderType)` | boolean | Returns false if orderType is in global filter list |
| `RuleFunctions.Helpers.GetActivityStatusString("1", false)` | "IN_PROGRESS" | Maps numeric status code to string |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | void | Persists order/activity state to database |
| `RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")` | void | Sets SKIPPED, advances NextActivityName pointer |
| `RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")` | void | Full error handling: status, logging, exception routing |
| `OMXUtils.asciiCodeToText(int)` | String | Converts ASCII decimal integer to character string |

---

## §15 — Function Dependency Tree

```text
Request_ASRM_INVOKE_MSISDN (rule)
├── Instance.getByExtIdByUri(...)
├── XPath.evalAsString(tib:tokenize ...)          [parameter parsing]
├── RuleFunctions.Helpers.BRMS.IsBlank(String)
├── OMXUtils.asciiCodeToText(int)
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
│   ├── RuleFunctions.Helpers.GetActivityStatusString("4", false)
│   ├── Instance.getByExtIdByUri(nxtAct)
│   ├── RuleFunctions.Helpers.BRMS.IsBlank(...)
│   ├── RuleFunctions.Helpers.GetOrderStatusString(2)
│   └── RuleFunctions.Helpers.SendDataToDB(...)
└── RuleFunctions.Helpers.HandleActivityException(...)
    ├── RuleFunctions.Helpers.GetActivityStatusString("3", false)
    ├── RuleFunctions.Helpers.GetOrderStatusString(3)
    ├── RuleFunctions.Helpers.SetResponseCode(...)
    ├── Event.Ext.routeToImmediate(Logger/ErrorLog)
    └── RuleFunctions.Helpers.SendDataToDB(...)
```

---

## §16 — Concept Definitions Referenced

| Concept | Path | Key Fields Used |
|---------|------|-----------------|
| `OrderRequest` | `Concepts.OrderRequest.OrderRequest` | OrderData.OMXTrackingId, OrderID, OrderType, OrderPriority, DealerCode, MNPInfo, Customer.ParentOU[], IsOrderResubmitted |
| `Activity` | `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, Parameter[], Response[], RequestCount, PreExecCheck, NextActivity, ExceptionActivity |
| `ASRM_InvokeUnifiedResourceRes` | `Concepts.FM.Response.ASRM_InvokeUnifiedResourceRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Support all 8 MSISDN activity types: LOCK, RESERVE, PREACTIVATE, ACTIVATE, PORT IN, PORT OUT RELEASE, PORT IN REVERSE, PORT OUT REVERSE, ACTIVATED.
- **R2** — Iterate over both ParentOU and ChildOU subscriber hierarchies independently.
- **R3** — Evaluate per-subscriber PreExecCheck XPath before dispatching to ASRM.
- **R4** — Skip subscribers with existing SUCCESS responses (idempotent resubmission safety).
- **R5** — Decode zone codes from ASCII decimal before sending (PORT IN / PORT OUT RELEASE only).
- **R6** — PORT IN attribute population depends on OrderType — migrate full condition matrix from §8.1.
- **R7** — RequestCount must only be incremented when `IsOrderResubmitted = false`.

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Fan-out request count mismatch on resubmit | [HIGH] | The `isActResub` guard must be replicated exactly |
| ASCII zone code decoding | [MEDIUM] | `OMXUtils.asciiCodeToText` must be replaced; test with PORT IN orders |
| OrderType matrix for PORT IN attributes | [MEDIUM] | Validate complete list is migrated (7,57,12001,21,11028,11029,12016,12017,11030) |
| ChildOU hierarchy traversal | [MEDIUM] | Handle both flat (POU→Sub) and nested (POU→COU→Sub) structures |
| MSISDN_TRUE_RES conditional | [LOW] | Ensure ResourceInfo XPath navigation is correctly translated |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author chch
 */
rule Rules.OMConsumers.OMXFM.Request.Request_ASRM_INVOKE_MSISDN {
    attribute {
        priority = 5;
        forwardChain = true;
    }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "ASRM_INVOKE_MSISDN";
        orderRequest.ProcessFlow.NextActivityID == "ASRM_INVOKE_MSISDN";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        String donorZoneText, rcpZoneText;
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct =
                Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName,
                                         "/Concepts/OM/ProcessConfig/Activity");
            int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
            String activityValue = null;

            // Parse ACTIVITY=VALUE parameter
            for (int iParam=0; iParam<orderCurrentActivity.Parameter@length; iParam++) {
                String param      = XPath.evalAsString(/* xpath: Parameter[(iParam+1)] */);
                String paramKey   = XPath.evalAsString(/* xpath: tib:tokenize(param,"=")[1] */);
                String paramValue = XPath.evalAsString(/* xpath: tib:tokenize(param,"=")[2] */);
                if(String.equals("ACTIVITY", paramKey)) activityValue = paramValue;
            }

            // Decode zone codes for PORT IN / PORT OUT RELEASE
            if(String.equals(activityValue, "PORT IN") ||
               String.equals(activityValue, "PORT OUT RELEASE")) {
                if(!RuleFunctions.Helpers.BRMS.IsBlank(orderRequest.OrderData.MNPInfo.DonorZoneCode))
                    donorZoneText = OMXUtils.asciiCodeToText(
                        Number.intValue(orderRequest.OrderData.MNPInfo.DonorZoneCode, 10));
                if(!RuleFunctions.Helpers.BRMS.IsBlank(orderRequest.OrderData.MNPInfo.RCPZoneCode))
                    rcpZoneText = OMXUtils.asciiCodeToText(
                        Number.intValue(orderRequest.OrderData.MNPInfo.RCPZoneCode, 10));
            }

            String operatorname = String.format("%s_%s", orderCurrentActivity.ActivityID, activityValue);
            boolean isSkipped = true;

            // === ParentOU Loop ===
            for (int i=0; i<iPOULen; i++) {
                int iSubscriberLen = orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length;
                for (int j=0; j<iSubscriberLen; j++) {
                    String refId = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].RefId;
                    boolean reqSuccess = false;
                    for(int iResp=0; iResp<orderCurrentActivity.Response@length; iResp++)
                        if(Response[iResp].ReferenceId==refId && CompletionStatus==2) reqSuccess = true;
                    if(!reqSuccess) {
                        String chkRes = "true";
                        if(String.length(nextAct.PreExecCheck) > 0) {
                            String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId);
                            chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, ns);
                        }
                        if(String.equals(chkRes, "true")) {
                            Events.OMConsumers.OMXFM.Request.ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY reqEvent =
                                Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY}}"
                                /* Variant ① XSLT — see §9.8: builds UnifiedResourceActivityInfo
                                   for ParentOU[i]/Subscriber[j]. Output: JMSPriority, JMSCorrelationID,
                                   OrderID, RefID, [UserName, PassWord], [OrderType],
                                   payload/UnifiedResourceActivityInfo (ActivityName=$activityValue,
                                   [ActivityAttributes per §9.5], UnifiedResource Type=MSISDN [Value=MSISDN]) */);
                            Event.Ext.sendEventImmediate(reqEvent);
                            if(RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                                long pid = System.nanoTime();
                                Event.Ext.sendEventImmediate(Event.createEvent(
                                    "xslt://{{/Events/OMConsumers/OMXESB/Logger}}"
                                    /* Logger XSLT — see §11 */));
                            }
                            if(!isActResub) orderCurrentActivity.RequestCount++;
                            isSkipped = false;
                        }
                    }
                }
                // === ChildOU Loop (same logic, Variant ② XSLT with $k param) ===
                int iCOULen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU@length;
                for(int k=0; k<iCOULen; k++) {
                    // ... identical logic, navigates ChildOU[(k+1)]/Subscriber[(j+1)] ...
                }
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

`RuleFunctions.OrderResponse.Response_ASRM_INVOKE_MSISDN` is invoked when ASRM returns an `ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY` response event. It parses the response, appends it to the activity's Response array, logs the audit trail, then evaluates fan-in completion (all parallel requests succeeded).

### §19.2 — Scope Variables

| Variable | Type Path | Role |
|----------|-----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Master order — logging and tracking |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY` | ASRM response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] array appended; RequestCount checked |

### §19.3 — ResponseBase Concept Construction

```text
createObject
└── object @extId ← OMXUtils.generateTrackingID()                [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode          [Conditional: if ResponseCode exists]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg           [Conditional: if ResponseMsg exists]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus      [Conditional: if CompletionStatus exists]
    └── ReferenceId       ← $eventResponse/RefID                 [Conditional: if RefID exists]
```

Appended: `currActivity.Response[currActivity.Response@length] = activityRes`

### §19.4 — Response Completion Logic (Fan-in)

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

```java
if(currActivity.RequestCount == successResponseCount)
    return "true";   // all ASRM calls succeeded → advance to next activity
else
    return "false";  // still waiting for more responses
```

### §19.5 — Response Audit Logging

| Field | Source | Condition |
|-------|--------|-----------|
| `ESBUUID` | `$orderRequest/OrderData/OMXTrackingId` | If OMXTrackingId exists |
| `PROCESS_ID` | `concat($pid, "_RES")` | Always (**_RES** suffix) |
| `COMPONENT_NAME` | `OMX_COMMON/Component_Name/OMX_CEP` | Always |
| `OPERATION_NAME` | `$operatorname` (ActivityID_Parameter[0]) | Always |
| `AUDIT_TRACE` | `concat("Response received for RefId ", $eventResponse/RefID)` | Always |
| `AUDIT_TS` | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` | Always |
| `payload/ns:ServicePayload` | `copy-of($eventResponse)` | Only if `OMX_OM/WritePayload = "true"` |

### §19.6 — Response XSLT Source

```xml
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:param name="extId"/>         <!-- OMXUtils.generateTrackingID() -->
  <xsl:param name="eventResponse"/> <!-- ASRM response event -->
  <xsl:template match="/">
    <createObject><object>
      <xsl:attribute name="extId"><xsl:value-of select="$extId"/></xsl:attribute>
      <xsl:if test="$eventResponse/ResponseCode">
        <ResponseCode><xsl:value-of select="$eventResponse/ResponseCode"/></ResponseCode>
      </xsl:if>
      <xsl:if test="$eventResponse/ResponseMsg">
        <ResponseMessage><xsl:value-of select="$eventResponse/ResponseMsg"/></ResponseMessage>
      </xsl:if>
      <xsl:if test="$eventResponse/CompletionStatus">
        <CompletionStatus><xsl:value-of select="$eventResponse/CompletionStatus"/></CompletionStatus>
      </xsl:if>
      <xsl:if test="$eventResponse/RefID">
        <ReferenceId><xsl:value-of select="$eventResponse/RefID"/></ReferenceId>
      </xsl:if>
    </object></createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
