# Request_INTX_GET_SIM_INFO_BY_MSISDN

> Retrieves SIM and MSISDN pairing information from INTX (Amdocs RM3G) by MSISDN lookup

**Author:** awalia-t420 | **Target:** INTX (Amdocs RM3G) | **Pattern:** Per-subscriber fan-out | **Priority:** 5

---

## §1 Overview & Purpose

This rule fires when the order orchestrator encounters an activity with `ActivityID == "INTX_GET_SIM_INFO_BY_MSISDN"` and the activity is in `WAITING` status. For every subscriber (ParentOU and ChildOU) in the order whose MSISDN is not blank, it constructs and sends a `GetSIMInfoByMSISDNReq` JMS event to the INTX service.

The call retrieves the current state of both the MSISDN (CTN) resource and its paired SIM card, including status codes, company codes, pool membership, SIM type, IMSI, and SUCI SIM indicator. All discovered data is written back as `ResourceInfo` entries on the subscriber concept for downstream rules to consume.

A **PROJ parameter** switch (`RMRF` vs default) changes the payload element from `<ns:msisdn>` to `<ns:simNote>`, supporting the RMRF project variant.

> **Key Gate:** The `isASRMCompanyCode` boolean (`MobileStatus.length > RMStatusLength` global variable) gates all ResourceInfo writes. If INTX returns a short-form status code, no ResourceInfo is persisted.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule class | `Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_SIM_INFO_BY_MSISDN` |
| Priority | 5 |
| forwardChain | true |
| ActivityID trigger | `INTX_GET_SIM_INFO_BY_MSISDN` |
| Author | awalia-t420 |
| Target system | INTX (Amdocs Resource Manager 3G) |
| Event type (outbound) | `Events.OMConsumers.OMXFM.Request.INTX_GET_SIM_INFO_BY_MSISDN` |
| Response concept | `Concepts.FM.Response.INT_GetSIMInfoRes` |
| Payload schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetSIMInfoByMSISDN.xsd` |
| Fan-out pattern | Per-subscriber (one event per subscriber per OU level) |
| Re-submit guard | Checks `Response[RefId==refId].CompletionStatus==2` before re-sending |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order concept containing all subscriber data and order metadata |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process activity configuration (Parameters, PreExecCheck, RequestCount, Response[]) |

---

## §4 Rule Conditions (WHEN)

- **C1** `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` — activity extId matches the order's current next-activity pointer
- **C2** `orderCurrentActivity.ActivityID == "INTX_GET_SIM_INFO_BY_MSISDN"` — FM identity check
- **C3** `orderRequest.ProcessFlow.NextActivityID == "INTX_GET_SIM_INFO_BY_MSISDN"` — process flow ID check (dual guard with C2)
- **C4** `orderCurrentActivity.Status == "WAITING"` — activity must be in waiting state

---

## §5 Execution Flow

1. Get `nextAct` by extId; read PROJ parameter from activity config
2. Set `isSkipped = true`; compute `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
3. Iterate ParentOU[i] → Subscriber[j] loop
   - 3a. Re-submit dedup: scan Response[] for this refId with CompletionStatus==2; if found → skip
   - 3b. PreExecCheck gate: evaluate XPath against subscriber XML; if ≠ "true" → skip
   - 3c. Blank MSISDN guard: if `currMSISDN` is blank → `continue`
   - 3d. Build and send `INTX_GET_SIM_INFO_BY_MSISDN` event via XSLT (PROJ branch: `simNote` vs `msisdn`)
   - 3e. If not resubmit → `RequestCount++`; `isSkipped = false`
   - 3f. AllowWriteLog gate → send audit Logger event
4. Repeat step 3 for ChildOU[k] → Subscriber[j] loops
5. If `!isSkipped` → set activity Status="1" (IN_PROGRESS), call `SendDataToDB`
6. Else → call `SkipActivity(orderRequest, orderCurrentActivity, "4")`
7. Exception catch → `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §6 Rule Action (THEN) — Step-by-Step Logic

**Resubmit detection:** `isActResub = (RequestCount > 0 && IsOrderResubmitted)`. When true, `RequestCount` is not incremented.

**Per-subscriber fan-out:** Two nested loops iterate ParentOU and ChildOU subscribers independently. The XSLT template is identical for both paths; the only difference is the PreExecCheck helper (`GetXMLForSubscriber` vs `GetXMLForSubscriberInChildOU`).

**PROJ branching in payload:** An `xsl:choose` sends `<ns:simNote>{currMSISDN}</ns:simNote>` when PROJ="RMRF", otherwise `<ns:msisdn>{currMSISDN}</ns:msisdn>`.

---

## §7 Data Extraction

No GROUP-encoded or pipe-delimited field parsing in the request rule. The PROJ parameter is read via `RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "PROJ")`.

In the response rulefunction, `rmStatusLength` is read from global variable `$globalVariables/OMX_OM/BizRules/RMStatusLength`:

```java
boolean isASRMCompanyCode = (String.length(res.MobileStatus) > rmStatusLength);
```

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

Used in any order type requiring INTX SIM/MSISDN validation. In `PREPAID_CANCEL`, it verifies SIM-MSISDN pairing before cancellation. RMRF project variant activates when `PROJ=RMRF` is set in activity parameter configuration.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel / Destination | Protocol | Purpose |
|-----------|----------------------|----------|---------|
| [OUTBOUND JMS] | `Events.OMConsumers.OMXFM.Request.INTX_GET_SIM_INFO_BY_MSISDN` | JMS / ESB | Send GetSIMInfoByMSISDN request to INTX |
| [OUTBOUND LOG] | `Events.OMConsumers.OMXESB.Logger` | JMS | Audit trail (gated by AllowWriteLog) |
| [INBOUND JMS] | `Events.OMConsumers.OMXFM.Response.INTX_GET_SIM_INFO_BY_MSISDN` | JMS / ESB | Async response from INTX |

### §8.3 Backend API Details

| System | Operation | Request Schema | Protocol | Correlation |
|--------|-----------|---------------|----------|-------------|
| INTX (Amdocs RM3G) | GetSIMInfoByMSISDN | `ns:GetSIMInfoByMSISDNReq` | JMS / ESB | JMSCorrelationID=OMXTrackingId; RefID=subscriber RefId |

### §8.4 BE Working Memory Dependencies

| Concept Path | Access | Fields Used |
|-------------|--------|------------|
| OrderRequest | Read | OrderData.OrderID, OMXTrackingId, OrderType, User, Password, OrderPriority, IsOrderResubmitted |
| ParentOU[].Subscriber[] | Read/Write | RefId, MSISDN → writes ResourceInfo[], ExtendedInfo[] |
| ChildOU[].Subscriber[] | Read/Write | RefId, MSISDN → writes ResourceInfo[], ExtendedInfo[] |
| ProcessConfig.Activity | Read/Write | ActivityID, Status, RequestCount, Response[], Parameter, PreExecCheck |
| Concepts.FM.Response.INT_GetSIMInfoRes | Write | ResponseCode, ReferenceId, SearchKey, MobileStatus, MobileCompany, MobilePairWithSIM, SimType, SimStatus, SimCompany, MobilePoolName, MobilePoolType, SimImsi, SimSuciInd |

### §8.5 ResourceInfo Fields Written

| ResourceName | Source Field | Condition | extId Pattern |
|-------------|-------------|-----------|--------------|
| `MSISDN_COMPANY` | MobileCompany (ctnCompanyCode) | non-blank + isASRMCompanyCode | `SUBRI:{OMXTrackingId}:{RefID}:MSISDN_COMPANY` |
| `MSISDN_STATUS` | MobileStatus (ctnStatus) | non-blank + isASRMCompanyCode | `SUBRI:{OMXTrackingId}:{RefID}:MSISDN_STATUS` |
| `MSISDN_POOL` | MobilePoolName (ctnPoolCode) | non-blank + isASRMCompanyCode | `SUBRI:{OMXTrackingId}:{RefID}:MSISDN_POOL` |
| `MSISDN_POOL_TYPE` | MobilePoolType (ctnPoolType) | non-blank + isASRMCompanyCode | `SUBRI:{OMXTrackingId}:{RefID}:MSISDN_POOL_TYPE` |
| `MSISDN_PAIR_SIM` | MobilePairWithSIM (iccid) | non-blank + isASRMCompanyCode | `SUBRI:{OMXTrackingId}:{RefID}:MSISDN_PAIR_SIM` |
| `SIM_PAIR_MSISDN` | currMSISDN (subscriber MSISDN) | alongside MSISDN_PAIR_SIM | `SUBRI:{OMXTrackingId}:{RefID}:SIM_PAIR_MSISDN` |
| `SIM_STATUS` | SimStatus (resourceStatus) | non-blank + isASRMCompanyCode | `SUBRI:{OMXTrackingId}:{RefID}:SIM_STATUS` |
| `SIM_COMPANY` | SimCompany (simCompanyCode) | non-blank + isASRMCompanyCode | `SUBRI:{OMXTrackingId}:{RefID}:SIM_COMPANY` |
| `SIM_TYPE` | SimType (simType) | non-blank + isASRMCompanyCode | `SUBRI:{OMXTrackingId}:{RefID}:SIM_TYPE` |
| `IMSI` | SimImsi (imsi) | non-blank + isASRMCompanyCode + no prior IMSI | `SUBRI:{OMXTrackingId}:{RefID}:IMSI` |
| `SIM` (RMRF only) | MobilePairWithSIM (Source="FE") | PROJ=RMRF + non-blank + isASRMCompanyCode | `SUBRI:{OMXTrackingId}:{RefID}:SIM` |
| `SUCI_SIM` (RMRF only) | SimSuciInd (suciSimInd) | PROJ=RMRF + non-blank + isASRMCompanyCode | `SUBRI:{OMXTrackingId}:{RefID}:SUCI_SIM` |

### §8.6 ExtendedInfo Fields Written

| Name | Value | Condition |
|------|-------|-----------|
| `IS_SIM_RESERVED` (RMRF only) | "N" | PROJ=RMRF AND ResponseMessage == "Data Not Found." |

### §8.7 Global Variable Dependencies

| Path | Used for |
|------|---------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Controls UserName/PassWord inclusion |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Controls payload embedding in audit log |
| `$globalVariables/OMX_OM/BizRules/RMStatusLength` | Integer threshold for isASRMCompanyCode gate |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| xsl:param | Bound From (BE) | Type |
|-----------|----------------|------|
| `orderRequest` | `orderRequest` concept | OrderRequest concept |
| `refId` | `Subscriber[j].RefId` | String |
| `globalVariables` | BE global variable store | XML tree |
| `proj` | `GetActivityParameterValueFromKey(orderCurrentActivity, "PROJ")` | String |
| `currMSISDN` | `Subscriber[j].MSISDN` | String |

### §9.2 Event Container

Event type: `Events.OMConsumers.OMXFM.Request.INTX_GET_SIM_INFO_BY_MSISDN`
`@extId` generated via `OMXUtils:generateTrackingID()` — unique UUID per event instance.

### §9.3 JMS / Event Header Fields

| Field | Source | Notes |
|-------|--------|-------|
| JMSPriority | `$orderRequest/OrderPriority` | Propagates order priority to JMS queue |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Used to correlate async response back to order |
| OrderID | `$orderRequest/OrderData/OrderID` | Business order identifier |
| RefID | `$refId` | Subscriber RefId for response matching |
| UserName | `$orderRequest/OrderData/User` | Only if IsEnableUserPass='true' |
| PassWord | `$orderRequest/OrderData/Password` | Only if IsEnableUserPass='true' |
| OrderType | `$orderRequest/OrderData/OrderType` | Order type code |

### §9.4 Payload Root Element

Root: `<ns:GetSIMInfoByMSISDNReq>` where `ns` = `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetSIMInfoByMSISDN.xsd`

### §9.5 Conditional Fields

| Element | Condition | When emitted |
|---------|-----------|-------------|
| UserName, PassWord | `IsEnableUserPass='true'` | Credential-gated environments only |
| ns:simNote | `$proj="RMRF"` | RMRF project variant |
| ns:msisdn | `otherwise` (xsl:choose) | All non-RMRF order types |

### §9.6 Core Payload Block

```xml
<ns:GetSIMInfoByMSISDNReq>
  <ns:correlatedId>{OMXTrackingId}</ns:correlatedId>
  <!-- xsl:choose based on $proj -->
  [RMRF]  <ns:simNote>{currMSISDN}</ns:simNote>
  [OTHER] <ns:msisdn>{currMSISDN}</ns:msisdn>
</ns:GetSIMInfoByMSISDNReq>
```

### §9.7 Complete Generated XML Example (default path)

```xml
<event extId="UUID-abc-1234">
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-001</JMSCorrelationID>
  <OrderID>ORD-2025-001</OrderID>
  <RefID>SUB-REF-001</RefID>
  <OrderType>PREPAID_CANCEL</OrderType>
  <payload>
    <ns:GetSIMInfoByMSISDNReq xmlns:ns="...INTX/GetSIMInfoByMSISDN.xsd">
      <ns:correlatedId>OMX-TRK-001</ns:correlatedId>
      <ns:msisdn>0812345678</ns:msisdn>
    </ns:GetSIMInfoByMSISDNReq>
  </payload>
</event>
```

### §9.8 XSLT Stylesheet Source

Both ParentOU and ChildOU variants use an identical XSLT (only the PreExecCheck helper differs):

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetSIMInfoByMSISDN.xsd"
  version="1.0">
  <xsl:param name="orderRequest"/>   <!-- full OrderRequest concept -->
  <xsl:param name="refId"/>          <!-- subscriber RefId -->
  <xsl:param name="globalVariables"/>
  <xsl:param name="proj"/>           <!-- e.g. "RMRF" or "" -->
  <xsl:param name="currMSISDN"/>     <!-- subscriber MSISDN -->
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <RefID><xsl:value-of select="$refId"/></RefID>
        <xsl:if test="$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass='true'">
          <UserName><xsl:value-of select="$orderRequest/OrderData/User"/></UserName>
          <PassWord><xsl:value-of select="$orderRequest/OrderData/Password"/></PassWord>
        </xsl:if>
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        <payload>
          <ns:GetSIMInfoByMSISDNReq>
            <ns:correlatedId><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></ns:correlatedId>
            <xsl:choose>
              <xsl:when test="$proj=&quot;RMRF&quot;">
                <ns:simNote><xsl:value-of select="$currMSISDN"/></ns:simNote>
              </xsl:when>
              <xsl:otherwise>
                <ns:msisdn><xsl:value-of select="$currMSISDN"/></ns:msisdn>
              </xsl:otherwise>
            </xsl:choose>
          </ns:GetSIMInfoByMSISDNReq>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── @extId              ← OMXUtils:generateTrackingID()                         [Always]
    ├── JMSPriority         ← $orderRequest/OrderPriority                           [Always]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId                 [Always]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                       [Always]
    ├── RefID               ← $refId                                                [Always]
    ├── UserName            ← $orderRequest/OrderData/User                          [Credential-gated: IsEnableUserPass='true']
    ├── PassWord            ← $orderRequest/OrderData/Password                      [Credential-gated: IsEnableUserPass='true']
    ├── OrderType           ← $orderRequest/OrderData/OrderType                     [Always]
    └── payload
        └── ns:GetSIMInfoByMSISDNReq
            ├── ns:correlatedId  ← $orderRequest/OrderData/OMXTrackingId           [Always]
            ├── ns:simNote       ← $currMSISDN                                     [Conditional: $proj="RMRF"]
            └── ns:msisdn        ← $currMSISDN                                     [Conditional: otherwise (not RMRF)]
```

**Legend:** `[Always]` emitted unconditionally | `[Conditional: ...]` emitted under xsl:if/xsl:choose | `[Credential-gated]` gated by IsEnableUserPass global variable

---

## §11 Audit Logging

Gated by `RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)`. A Logger event is sent **after each subscriber's request event**.

| Log Field | Value |
|-----------|-------|
| ESBUUID | OMXTrackingId (conditional: if present) |
| PROCESS_ID | `concat(pid, "_REQ")` where pid = System.nanoTime() |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | "INTX_GET_SIM_INFO_BY_MSISDN" (static) |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | "Request Sent for INTX_GET_SIM_INFO_BY_MSISDN" (static) |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload/ns:ServicePayload | Copy of reqEvent (conditional: WritePayload="true") |

---

## §12 Activity Status Management

| Condition | Status Set | Call |
|-----------|-----------|------|
| At least one event sent (`!isSkipped`) | "1" (IN_PROGRESS) | `GetActivityStatusString("1", false)` → `SendDataToDB` |
| No events sent (`isSkipped`) | "4" (SKIPPED) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception thrown | Error state | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §13 Exception / Error Handling

The entire `then` block is wrapped in `try { ... } catch (Exception ae) { ... }`. On any exception, `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` is called.

---

## §14 Helper Functions Reference

| Function | Signature | Purpose |
|----------|-----------|---------|
| `GetActivityParameterValueFromKey` | (Activity, String key) → String | Reads a named parameter from the activity's Parameter list |
| `GetXMLForSubscriber` | (OrderRequest, String refId) → String | Builds XML for ParentOU subscriber PreExecCheck evaluation |
| `GetXMLForSubscriberInChildOU` | (OrderRequest, String refId, String parentRefId) → String | Builds XML for ChildOU subscriber PreExecCheck evaluation |
| `BRMS.IsBlank` | (String) → boolean | Returns true if null or empty after trimming |
| `AllowWriteLog` | (String orderType) → boolean | Controls audit logging per order type |
| `GetActivityStatusString` | (String code, boolean isError) → String | Converts numeric code to status string constant |
| `SendDataToDB` | (OrderRequest) → void | Persists order state to database |
| `SkipActivity` | (OrderRequest, Activity, String code) → void | Marks activity skipped and advances process flow |
| `HandleActivityException` | (OrderRequest, Activity, Exception, String) → void | Handles exceptions: logs, sets error status, triggers compensation |

---

## §15 Function Dependency Tree

```text
Request_INTX_GET_SIM_INFO_BY_MSISDN (rule)
├── RuleFunctions.Helpers.GetActivityParameterValueFromKey
├── [ParentOU loop]
│   ├── RuleFunctions.Helpers.GetXMLForSubscriber
│   ├── XPath.execute (PreExecCheck evaluation)
│   ├── RuleFunctions.Helpers.BRMS.IsBlank (MSISDN guard)
│   ├── Event.createEvent (XSLT → INTX_GET_SIM_INFO_BY_MSISDN event)
│   │   └── OMXUtils:generateTrackingID
│   ├── Event.Ext.sendEventImmediate
│   └── AllowWriteLog → Event.createEvent (Logger) → sendEventImmediate
├── [ChildOU loop]
│   └── (same as ParentOU, using GetXMLForSubscriberInChildOU)
├── RuleFunctions.Helpers.GetActivityStatusString
├── RuleFunctions.Helpers.SendDataToDB
├── RuleFunctions.Helpers.SkipActivity
└── RuleFunctions.Helpers.HandleActivityException

Response_INTX_GET_SIM_INFO_BY_MSISDN (rulefunction)
├── OMXUtils.generateTrackingID
├── Instance.createInstance (INT_GetSIMInfoRes XSLT)
├── XPath.evalAsInt (rmStatusLength from globalVariables)
├── RuleFunctions.Helpers.GetActivityParameterValueFromKey (PROJ)
├── [ParentOU subscriber match loop]
│   ├── BRMS.IsBlank (MobileStatus, MobileCompany, etc.)
│   ├── Instance.getByExtIdByUri (dedup check per ResourceInfo)
│   ├── Instance.createInstance (ResourceInfo XSLT) ×9-11
│   ├── XPath.evalAsBoolean (IMSI existence check)
│   ├── XPath.evalAsString (existing IMSI lookup)
│   └── [RMRF branch] ExtendedInfo IS_SIM_RESERVED on "Data Not Found."
├── [ChildOU subscriber match loop]
│   └── (same as ParentOU; IMSI without outer boolean guard — see §17 risk)
├── AllowWriteLog → Event.createEvent (Logger) → sendEventImmediate
└── XPath.evalAsInt (successResponseCount fan-in check)
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields |
|---------|-----------|
| `Concepts.FM.Response.INT_GetSIMInfoRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, SearchType, SearchKey, MobileStatus, MobileCompany, MobilePairWithSIM, SimType, SimStatus, SimCompany, MobilePoolName, MobilePoolType, SimImsi, SimSuciInd |
| `Concepts.OrderRequest.OrderElements.ResourceInfo` | extId, ResourceName, ValuesArray, Source |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` | Name, Value |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, ResourceInfo[], ExtendedInfo[] |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], Parameter, PreExecCheck |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|------------|
| R1 | Query INTX GetSIMInfoByMSISDN per subscriber (fan-out) with RefID correlation |
| R2 | Support RMRF variant: send `simNote` instead of `msisdn` in payload |
| R3 | Write MSISDN_COMPANY, MSISDN_STATUS, MSISDN_POOL, MSISDN_POOL_TYPE, MSISDN_PAIR_SIM as ResourceInfo |
| R4 | Write SIM_PAIR_MSISDN cross-reference alongside MSISDN_PAIR_SIM |
| R5 | Write SIM_STATUS, SIM_COMPANY, SIM_TYPE, IMSI (if not already present) as ResourceInfo |
| R6 | Gate all ResourceInfo writes on `isASRMCompanyCode` (MobileStatus.length > RMStatusLength) |
| R7 | RMRF only: write SIM (Source="FE") and SUCI_SIM ResourceInfo; write IS_SIM_RESERVED="N" ExtendedInfo on "Data Not Found." |
| R8 | Standard fan-in: return "true" when `RequestCount == count(Response[ResponseCode ends with "000"])` |
| R9 | Re-submit dedup: skip subscribers already having CompletionStatus==2 in Response[] |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `isASRMCompanyCode` is misleadingly named — checks MobileStatus length against RMStatusLength, not company code | [LOW] | Rename to `isFullStatusResponse` or document intent with a comment |
| RMRF "Data Not Found." sets IS_SIM_RESERVED="N" but no equivalent handling for non-RMRF orders | [MEDIUM] | Document and decide whether non-RMRF also needs IS_SIM_RESERVED when SIM not found |
| IMSI guard for ParentOU uses outer `XPath.evalAsBoolean(not(exists(...IMSI...)))` but ChildOU path omits the outer boolean guard (inconsistency) | [LOW] | Add matching outer guard for ChildOU path |
| `rmStatusLength` has no fallback if GlobalVar absent — `evalAsInt` returns 0, making all statuses pass the gate | [LOW] | Add GlobalVar existence check or provide a safe default |
| Duplicate XSLT template embedded twice (ParentOU and ChildOU) with only helper function difference | [LOW] | Extract to shared rulefunction to reduce maintenance surface |

---

## §18 Full Source Code

```java
/**
 * @description
 * @author awalia-t420
 */
rule Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_SIM_INFO_BY_MSISDN {
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
        orderCurrentActivity.ActivityID == "INTX_GET_SIM_INFO_BY_MSISDN";
        orderRequest.ProcessFlow.NextActivityID == "INTX_GET_SIM_INFO_BY_MSISDN";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        String operationName = orderCurrentActivity.ActivityID;
        boolean isActResub=(orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
                orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
            String proj = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "PROJ");
            boolean isSkipped = true;

            // ── ParentOU loop ───────────────────────────────────────────────
            int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
            for ( int i=0 ; i < iPOULen ; i++ ) {
                int iSubscriberLen = orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length;
                for( int j=0 ; j<iSubscriberLen ; j++ ) {
                    String refId = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].RefId;
                    boolean reqSuccess = false;

                    // Re-submit dedup
                    for(int iResp=0; iResp<orderCurrentActivity.Response@length; iResp++) {
                        if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, refId) &&
                           orderCurrentActivity.Response[iResp].CompletionStatus==2) {
                            reqSuccess = true;
                        }
                    }

                    if(!reqSuccess) {
                        String chkRes = "true";
                        if(String.length(nextAct.PreExecCheck) > 0) {
                            String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId);
                            String chkXPath = nextAct.PreExecCheck;
                            chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=...");
                        }
                        if(String.equals(chkRes,"true")) {
                            String currMSISDN = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].MSISDN;
                            if(RuleFunctions.Helpers.BRMS.IsBlank(currMSISDN)) continue;

                            /* Build INTX_GET_SIM_INFO_BY_MSISDN event via XSLT.
                               Payload: GetSIMInfoByMSISDNReq with correlatedId + msisdn (or simNote for RMRF).
                               Full XSLT in §9.8. */
                            Events.OMConsumers.OMXFM.Request.INTX_GET_SIM_INFO_BY_MSISDN reqEvent =
                                Event.createEvent("xslt://{{...}}");
                            Event.Ext.sendEventImmediate(reqEvent);

                            if(!isActResub) { orderCurrentActivity.RequestCount++; }
                            isSkipped = false;

                            if (RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                                long pid = System.nanoTime();
                                Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{Logger}}"));
                            }
                        }
                    }
                }

                // ── ChildOU loop ─────────────────────────────────────────────
                int iCOULen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU@length;
                for (int k=0 ; k < iCOULen ; k++){
                    iSubscriberLen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU[k].Subscriber@length;
                    for( int j=0 ; j<iSubscriberLen ; j++ ) {
                        // [same logic; uses GetXMLForSubscriberInChildOU for PreExecCheck]
                    }
                }
            }

            if(!isSkipped) {
                orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch ( Exception ae){
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

`RuleFunctions.OrderResponse.Response_INTX_GET_SIM_INFO_BY_MSISDN` receives the async response event, maps the INTX payload into a `Concepts.FM.Response.INT_GetSIMInfoRes` concept, then iterates all subscribers to find the match by MSISDN (`res.SearchKey == subscriber.MSISDN`). For the matched subscriber, up to 12 `ResourceInfo` entries are written (and 1 `ExtendedInfo` for RMRF). It then performs standard fan-in counting.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order concept |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.INTX_GET_SIM_INFO_BY_MSISDN` | Inbound INTX response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity (holds Response[] and RequestCount) |

### §19.3 INT_GetSIMInfoRes Concept Construction

```text
createObject
└── object
    ├── @extId              ← OMXUtils:generateTrackingID()                      [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode                        [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg                         [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus                    [Conditional]
    ├── ReferenceId         ← $eventResponse/RefID                               [Conditional]
    ├── SearchType          ← "MOBILE"                                           [Always (static)]
    ├── SearchKey           ← ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:ctn/ns1:ctn  [Conditional]
    ├── MobileStatus        ← tib:trim(ns1:resource/ns1:ctn/ns1:ctnStatus)      [Always]
    ├── MobileCompany       ← tib:trim(ns1:resource/ns1:ctn/ns1:ctnCompanyCode)  [Always]
    ├── MobilePairWithSIM   ← tib:trim(ns1:resource/ns1:sim/ns1:iccid)           [Always]
    ├── SimType             ← tib:trim(ns1:resource/ns1:sim/ns1:simType)          [Always]
    ├── SimStatus           ← tib:trim(ns1:resource/ns1:sim/ns1:resourceStatus)   [Always]
    ├── SimCompany          ← tib:trim(ns1:resource/ns1:sim/ns1:simCompanyCode)   [Always]
    ├── MobilePoolName      ← tib:trim(ns1:resource/ns1:ctn/ns1:ctnPoolCode)     [Always]
    ├── MobilePoolType      ← tib:trim(ns1:resource/ns1:ctn/ns1:ctnPoolType)     [Always]
    ├── SimImsi             ← tib:trim(ns1:resource/ns1:sim/ns1:imsi)             [Always]
    └── SimSuciInd          ← ns1:resource/ns1:sim/ns1:suciSimInd                [Conditional: if element exists]
```

### §19.4 Response Completion Logic

**isASRMCompanyCode gate:**

```java
int rmStatusLength = XPath.evalAsInt("$globalVariables/OMX_OM/BizRules/RMStatusLength");
boolean isASRMCompanyCode = (String.length(res.MobileStatus) > rmStatusLength);
```

All ResourceInfo blocks are gated on `!IsBlank(fieldValue) && isASRMCompanyCode`.

**Subscriber match:** iterates all subscribers and matches on `res.SearchKey == subscriber.MSISDN`.

**Fan-in success XPath:**

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

**Fan-in condition:** `currActivity.RequestCount == successResponseCount`
- Returns `"true"` → all parallel INTX calls succeeded; activity can advance
- Returns `"false"` → still waiting for more responses

### §19.5 Response Audit Logging

| Log Field | Value |
|-----------|-------|
| ESBUUID | OMXTrackingId (conditional) |
| PROCESS_ID | `concat(pid, "_RES")` |
| OPERATION_NAME | "INTX_GET_SIM_INFO_BY_MSISDN" |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload/ns:ServicePayload | Copy of $eventResponse (conditional: WritePayload="true") |

### §19.6 Response XSLT Source (INT_GetSIMInfoRes)

```xml
<xsl:stylesheet
  xmlns:ns1="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetSIMInfoByMSISDN.xsd"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
  version="1.0">
  <xsl:param name="extId"/>
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject>
      <object>
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
        <SearchType>MOBILE</SearchType>   <!-- static -->
        <xsl:if test="$eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:ctn/ns1:ctn">
          <SearchKey><xsl:value-of select="$eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:ctn/ns1:ctn"/></SearchKey>
        </xsl:if>
        <MobileStatus><xsl:value-of select="tib:trim($eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:ctn/ns1:ctnStatus)"/></MobileStatus>
        <MobileCompany><xsl:value-of select="tib:trim($eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:ctn/ns1:ctnCompanyCode)"/></MobileCompany>
        <MobilePairWithSIM><xsl:value-of select="tib:trim($eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:sim/ns1:iccid)"/></MobilePairWithSIM>
        <SimType><xsl:value-of select="tib:trim($eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:sim/ns1:simType)"/></SimType>
        <SimStatus><xsl:value-of select="tib:trim($eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:sim/ns1:resourceStatus)"/></SimStatus>
        <SimCompany><xsl:value-of select="tib:trim($eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:sim/ns1:simCompanyCode)"/></SimCompany>
        <MobilePoolName><xsl:value-of select="tib:trim($eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:ctn/ns1:ctnPoolCode)"/></MobilePoolName>
        <MobilePoolType><xsl:value-of select="tib:trim($eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:ctn/ns1:ctnPoolType)"/></MobilePoolType>
        <SimImsi><xsl:value-of select="tib:trim($eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:sim/ns1:imsi)"/></SimImsi>
        <xsl:if test="$eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:sim/ns1:suciSimInd">
          <SimSuciInd><xsl:value-of select="$eventResponse/payload/ns1:GetSIMInfoByMSISDNRes/ns1:resource/ns1:sim/ns1:suciSimInd"/></SimSuciInd>
        </xsl:if>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
