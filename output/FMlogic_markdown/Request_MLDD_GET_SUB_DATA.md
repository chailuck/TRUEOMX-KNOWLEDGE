# Request_MLDD_GET_SUB_DATA

Per-subscriber parallel device data lookup (MLDD) — retrieves IMEI and device attributes; writes IMEI_MLDD to SubscriberExtendedInfo; POU path normalises MSISDN 0→66.

**Target:** MLDD (Device Data Store) | **Pattern:** Per-subscriber parallel fan-out | **forwardChain:** true | **Author:** Chayatorn Pan.

---

## §1 Overview & Purpose

This FM retrieves device/handset data from the MLDD system for each subscriber (POU and COU) in parallel. It requests a fixed column set — MSISDN, IMSI, IMEI, TAC, PHONE_VENDOR, PHONE_TYPE, GPRS, UMTS, OS_NAME, LTE, WLAN, NFC, FORM — and extracts the `IMEI` field from the response, writing it as a `SubscriberExtendedInfo` named `IMEI_MLDD`. Standard parallel fan-out (not IntraActivitySequencing). Audit logging is conditionally gated by `AllowWriteLog(OrderType)`.

> **POU-only MSISDN normalisation:** POU subscriber path replaces a leading "0" with "66" (Thai local → international format) before sending. The COU subscriber path does **not** apply this transformation — COU MSISDN is sent as-is. This asymmetry may cause MLDD lookups to fail for COU subscribers whose MSISDN is in local format.

> **[BUG — MEDIUM]:** Response rulefunction accesses `subscriber.ExtendedInfo[subscriber.ExtendedInfo@length]` (line 26) without a null check on `subscriber`. If both SUB and CSUB lookups return null, this causes a NullPointerException.

> **[DEAD VARIABLE]:** `String extId = eventResponse.JMSCorrelationID+":"+eventResponse.RefID` (response line 17) is computed but never used.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_MLDD_GET_SUB_DATA.rule` | 117 lines |
| Response file | `Response_MLDD_GET_SUB_DATA.rulefunction` | 41 lines |
| Author | Chayatorn Pan. | |
| forwardChain | true | |
| Request event | `Events.OMConsumers.OMXFM.Request.MLDD_GET_SUB_DATA` | One per subscriber |
| Response event | `Events.OMConsumers.OMXFM.Response.MLDD_GET_SUB_DATA` | |
| Request schema NS | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MLDD/GetSubData.xsd` (ns) | |
| Response schema NS | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MLDD/GetSubData.xsd` (xsd2) | Same schema; different prefix |
| Response concept | `Concepts.FM.Base.ResponseBase` | Standard base — no extId on object |
| extId on request event | `OMXUtils:generateTrackingID()` | Always |
| reqSuccess dedup key | `refId` (RefId) — NOT SubscriberId | Differs from BL_LIST_UNINVOICED_CHARGES |
| Fan-out | Parallel — `Event.Ext.sendEventImmediate` per subscriber | No IntraActivitySequencing |
| Fan-in | Standard "000" success count == RequestCount | |
| Resubmit handler | None — no `PurgePendingRequestsBeforeResubmit` | isActResub only gates RequestCount++ |
| Credential gate | None | No UserName/PassWord headers |
| Audit gate | `AllowWriteLog(OrderData.OrderType)` | Conditional — not all order types produce audit logs |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Source of subscribers; OrderType for audit gate |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Activity state; RequestCount++; Response[] appended |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "MLDD_GET_SUB_DATA"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "MLDD_GET_SUB_DATA"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 Execution Flow

1. isActResub flag (no purge — isActResub only gates RequestCount++)
2. isSkipped = true
3. **POU Subscribers** — for each POU × each Subscriber:
   - reqSuccess check: `Response[].ReferenceId == refId AND CompletionStatus==2`
   - PreExecCheck: `GetXMLForSubscriber(orderRequest, refId)`
   - If passes: normalise MSISDN (0→66 if starts with "0"); send event immediately; conditional audit; RequestCount++; isSkipped=false
4. **COU Subscribers** — for each POU × each COU × each Subscriber:
   - Same reqSuccess check and PreExecCheck (`GetXMLForSubscriberInChildOU`)
   - If passes: use MSISDN as-is (**no 0→66 conversion**); send event immediately; conditional audit; RequestCount++; isSkipped=false
5. **Status:** if !isSkipped → `GetActivityStatusString("1")` + `SendDataToDB`; else → `SkipActivity("4")`
6. **Exception:** try/catch → `HandleActivityException`

---

## §6 Rule Action (THEN) — Key Details

### §6.1 MSISDN Normalisation (POU only)

```java
// POU subscriber only:
String msisdn = orderRequest...ParentOU[i].Subscriber[j].MSISDN;
if (String.startsWith(msisdn, "0")) {
    msisdn = String.replaceFirst(msisdn, "0", "66");  // local → international
}

// COU subscriber: NO conversion — raw MSISDN sent directly
String msisdn = orderRequest...ChildOU[p].Subscriber[q].MSISDN;
```

> Thai mobile MSISDNs starting with "0" (e.g. 0812345678) are converted to international format "66812345678" for POU subscribers. COU subscribers bypass this — if their MSISDN is stored in local format, MLDD may fail to look them up.

### §6.2 reqSuccess Dedup (uses RefId, not SubscriberId)

```java
for(int iResp=0; iResp < orderCurrentActivity.Response@length; iResp++)
    if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, refId)
        && orderCurrentActivity.Response[iResp].CompletionStatus==2)
        reqSuccess = true;
```

### §6.3 Conditional Audit Logging

```java
if (RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
    long pid = System.nanoTime();
    Event.Ext.sendEventImmediate(auditEvent);
}
```

`AllowWriteLog` returns a boolean controlling whether audit events are written for a given order type.

---

## §7 Data Extraction

| Field | Source | Transform | Used For |
|-------|--------|-----------|----------|
| `refId` | `Subscriber[j].RefId` | None | reqSuccess dedup; RefID header; subscriber lookup |
| `msisdn` (POU) | `Subscriber[j].MSISDN` | 0→66 if starts with "0" | `ns:MSISDN` payload field |
| `msisdn` (COU) | `Subscriber[q].MSISDN` | None | `ns:MSISDN` payload field |
| GETCOLUMN | Hardcoded literal | None | Column selection for MLDD |

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

Single MLDD backend; no GoldenDB routing. Audit logging suppressed for some order types (controlled by `AllowWriteLog`).

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Purpose |
|-----------|---------|-------------|---------|
| [OUTBOUND] | FM JMS | MLDD_GET_SUB_DATA queue | Device data lookup per subscriber (parallel) |
| [INBOUND] | FM JMS | MLDD_GET_SUB_DATA response queue | GetSubDataResponse with device attributes |
| [LOG] | OMXESB Logger | Audit event | Conditional — only if AllowWriteLog(OrderType) = true |

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| Backend | MLDD (Mobile Line Device Data) |
| Operation | GetSubData |
| Request root | `ns:GetSubDataRequest` |
| Response root | `xsd2:GetSubDataResponse/xsd2:User` |
| MSISDN format | International (66XXXXXXXXX) for POU; raw for COU |
| GETCOLUMN | `MSISDN&IMSI&IMEI&TAC&PHONE_VENDOR&PHONE_TYPE&GPRS&UMTS&OS_NAME&LTE&WLAN&NFC&FORM` (hardcoded) |
| Field extracted | `xsd2:IMEI` only (other columns available but not extracted) |

### §8.4 BE Working Memory Dependencies

| Concept | Field | Access | Notes |
|---------|-------|--------|-------|
| OrderRequest | OrderData.Customer.ParentOU[].Subscriber[].RefId / MSISDN | READ | RefId for correlation/dedup; MSISDN normalised for POU |
| OrderRequest | OrderData.OrderType | READ | Passed to AllowWriteLog |
| Activity | RequestCount / Response[] / Status | READ+WRITTEN | Standard |
| Subscriber | ExtendedInfo[] | WRITTEN | SubscriberExtendedInfo Name="IMEI_MLDD" appended — no null guard |

### §8.5 ExtendedInfo Fields Written

| Type | Name | Value | Notes |
|------|------|-------|-------|
| SubscriberExtendedInfo | IMEI_MLDD | `xsd2:GetSubDataResponse/xsd2:User/xsd2:IMEI` | No null guard if IMEI blank; extId not set on object |

### §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `OMX_OM/WritePayload` | Payload inclusion in audit |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameters

| Parameter | Bound From | Notes |
|-----------|-----------|-------|
| `$orderRequest` | orderRequest concept serialized | |
| `$refId` | `Subscriber[j/q].RefId` | Correlation key |
| `$msisdn` | POU: MSISDN with 0→66; COU: MSISDN as-is | Main lookup key |

### §9.2 POU vs COU XSLT Variants

Both variants produce **identical XSLT**. The only difference is the `$msisdn` parameter value passed from the BE rule (POU applies 0→66 before binding; COU does not). The XSLT stylesheet is character-for-character identical in both variants.

### §9.3 JMS / Event Header Fields

| Header | Source | Condition |
|--------|--------|-----------|
| extId (event attr) | `OMXUtils:generateTrackingID()` | **Always** |
| JMSPriority | `$orderRequest/OrderPriority` | **Always** — no xsl:if |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | **Always** — no xsl:if |
| OrderID | `$orderRequest/OrderData/OrderID` | **Always** — no xsl:if |
| RefID | `$refId` | **Always** — no xsl:if |
| OrderType | `$orderRequest/OrderData/OrderType` | **Always** — no xsl:if |

> All headers are unconditional — no `xsl:if` wrappers. Even if source values are blank/null, empty XML elements will be emitted. This differs from most other FMs which use conditional headers.

### §9.4 Payload Fields

| XML Element | Source | Notes |
|-------------|--------|-------|
| `ns:GetSubDataRequest` | — root | |
| `ns:MSISDN` | `$msisdn` | International format for POU; raw for COU |
| `ns:GETCOLUMN` | `'MSISDN&IMSI&IMEI&TAC&PHONE_VENDOR&PHONE_TYPE&GPRS&UMTS&OS_NAME&LTE&WLAN&NFC&FORM'` | Hardcoded — 13 columns; only IMEI extracted |

### §9.5 Generated XML Example

```xml
<event extId="TRK-20250804-001">
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-20250804-001</JMSCorrelationID>
  <OrderID>ORD-001</OrderID>
  <RefID>SUB-REF-001</RefID>
  <OrderType>3</OrderType>
  <payload>
    <ns:GetSubDataRequest
      xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MLDD/GetSubData.xsd">
      <ns:MSISDN>66812345678</ns:MSISDN>  <!-- POU: 0→66 normalised -->
      <ns:GETCOLUMN>MSISDN&amp;IMSI&amp;IMEI&amp;TAC&amp;PHONE_VENDOR&amp;PHONE_TYPE&amp;GPRS&amp;UMTS&amp;OS_NAME&amp;LTE&amp;WLAN&amp;NFC&amp;FORM</ns:GETCOLUMN>
    </ns:GetSubDataRequest>
  </payload>
</event>
```

### §9.6 XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MLDD/GetSubData.xsd"
  version="1.0"
  exclude-result-prefixes="OMXUtils xsl xsd">
  <xsl:param name="orderRequest"/>
  <xsl:param name="refId"/>
  <xsl:param name="msisdn"/>
  <xsl:template match="/">
    <createEvent><event>
      <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
      <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      <RefID><xsl:value-of select="$refId"/></RefID>
      <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      <payload>
        <ns:GetSubDataRequest>
          <ns:MSISDN><xsl:value-of select="$msisdn"/></ns:MSISDN>
          <ns:GETCOLUMN><xsl:value-of select="'MSISDN&amp;IMSI&amp;IMEI&amp;TAC&amp;PHONE_VENDOR&amp;PHONE_TYPE&amp;GPRS&amp;UMTS&amp;OS_NAME&amp;LTE&amp;WLAN&amp;NFC&amp;FORM'"/></ns:GETCOLUMN>
        </ns:GetSubDataRequest>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── @extId                ← OMXUtils:generateTrackingID()                        [Always]
    ├── JMSPriority           ← $orderRequest/OrderPriority                          [Always — no xsl:if]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId               [Always — no xsl:if]
    ├── OrderID               ← $orderRequest/OrderData/OrderID                     [Always — no xsl:if]
    ├── RefID                 ← $refId (subscriber RefId)                            [Always — no xsl:if]
    ├── OrderType             ← $orderRequest/OrderData/OrderType                   [Always — no xsl:if]
    └── payload
        └── ns:GetSubDataRequest
            ├── ns:MSISDN     ← $msisdn [POU: 0→66 normalised | COU: raw]          [Always]
            └── ns:GETCOLUMN  ← 'MSISDN&IMSI&IMEI&TAC&PHONE_VENDOR&PHONE_TYPE&
                                 GPRS&UMTS&OS_NAME&LTE&WLAN&NFC&FORM'               [Hardcoded literal]
```

Legend:
- `[Always]` — emitted unconditionally; no xsl:if
- `[Hardcoded literal]` — static value; not driven from order data

---

## §11 Audit Logging

Both request and response audit events are gated by `AllowWriteLog(OrderType)`. If this returns false, no audit event is sent.

| Phase | AUDIT_TRACE | OPERATION_NAME | Gate |
|-------|-------------|----------------|------|
| Request | `"Request Sent for MLDD_GET_SUB_DATA"` | `"MLDD_GET_SUB_DATA"` | `AllowWriteLog(OrderType)` |
| Response | `"Response received for MLDD_GET_SUB_DATA"` | `"MLDD_GET_SUB_DATA"` | `AllowWriteLog(OrderType)` |

---

## §12 Activity Status Management

| Condition | Call | Code |
|-----------|------|------|
| At least one subscriber sent | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" (RUNNING) |
| No subscribers qualify | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" (SKIPPED) |

---

## §13 Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `AllowWriteLog(orderType)` | Returns boolean — controls whether audit events are sent for this order type |
| `GetXMLForSubscriber(req, refId)` | POU subscriber XML for PreExecCheck |
| `GetXMLForSubscriberInChildOU(req, refId, pouRefId)` | COU subscriber XML for PreExecCheck |
| `String.startsWith / String.replaceFirst` | MSISDN 0→66 normalisation (POU only) |
| `OMXUtils:generateTrackingID()` | Event extId generation (in XSLT) |
| `GetActivityStatusString / SendDataToDB / SkipActivity` | Activity lifecycle |

---

## §15 Function Dependency Tree

```text
Request_MLDD_GET_SUB_DATA (rule)
├── [per POU × Subscriber]:
│   ├── Response[].ReferenceId == refId AND CompletionStatus==2  [reqSuccess]
│   ├── GetXMLForSubscriber(orderRequest, refId)  [PreExecCheck]
│   ├── XPath.execute(preExecCheck, sXML, ns)
│   ├── String.startsWith(msisdn, "0") + String.replaceFirst → 0→66
│   ├── Event.createEvent("xslt://MLDD_GET_SUB_DATA")
│   │   └── OMXUtils:generateTrackingID()  [extId]
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   ├── AllowWriteLog(OrderType)
│   │   └── Event.Ext.sendEventImmediate(auditEvent)  [conditional]
│   └── orderCurrentActivity.RequestCount++  [if !isActResub]
├── [per POU × COU × Subscriber]:
│   ├── GetXMLForSubscriberInChildOU(req, refId, pouRefId)
│   ├── (no MSISDN normalisation)
│   └── (same send + audit pattern)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)  [if isSkipped]
└── RuleFunctions.Helpers.HandleActivityException(...)  [catch]

Response_MLDD_GET_SUB_DATA (rulefunction)
├── String extId = JMSCorrelationID+":"+RefID  ← DEAD VARIABLE (never used)
├── Instance.createInstance("xslt://ResponseBase")  [no extId on object]
├── currActivity.Response[length] = activityRes
├── Instance.getByExtIdByUri("SUB:"+OMXTrackingId+":"+RefID)
│   └── "CSUB:..." fallback if null
├── XPath.evalAsString(".../xsd2:GetSubDataResponse/xsd2:User/xsd2:IMEI")
├── subscriber.ExtendedInfo[length] = SubscriberExtendedInfo  ← NO null guard on subscriber!
│   └── Name="IMEI_MLDD", Value=imei
├── AllowWriteLog(OrderType)
│   └── Event.Ext.sendEventImmediate(auditLogEvent)  [conditional]
└── XPath.evalAsInt("count(Response[tib:right...='000'])") → fan-in
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields | Role |
|---------|-----------|------|
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId | Standard response; no extId set on instance |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` | Name, Value | Written with Name="IMEI_MLDD" |
| `Concepts.OrderRequest.OrderElements.Subscriber` | ExtendedInfo[] | IMEI_MLDD appended — null-unguarded access |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Fire per-subscriber (POU + COU) in parallel using subscriber RefId for both correlation (RefID header) and reqSuccess dedup. |
| R2 | POU: normalise MSISDN by replacing leading "0" with "66" before sending. COU: send MSISDN as-is. |
| R2a | **[RISK]** Evaluate whether COU subscribers should also receive the 0→66 normalisation. If MLDD expects international format, COU lookups will fail for local-format MSISDNs. |
| R3 | Send fixed GETCOLUMN string: `MSISDN&IMSI&IMEI&TAC&PHONE_VENDOR&PHONE_TYPE&GPRS&UMTS&OS_NAME&LTE&WLAN&NFC&FORM`. |
| R4 | Request event headers all unconditional — emit even if source value is blank. |
| R5 | No credential gate — no UserName/PassWord. |
| R6 | Audit logging conditional on `AllowWriteLog(OrderType)` — not all order types produce logs. |
| R7 | Response: extract `xsd2:IMEI` from `xsd2:GetSubDataResponse/xsd2:User`; write as SubscriberExtendedInfo Name="IMEI_MLDD". |
| R7a | **[BUG FIX]** Add null guard before accessing `subscriber.ExtendedInfo` — currently throws NPE if subscriber not found in working memory. |
| R8 | Fan-in: standard "000" count == RequestCount. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| NPE on subscriber.ExtendedInfo access when SUB/CSUB lookup returns null | [MEDIUM] | Add `if(subscriber != null)` guard before line 26 in response rulefunction |
| COU MSISDN not normalised — MLDD lookup may fail for local-format COU MSISDNs | [MEDIUM] | Determine if COU subscribers can have 0-prefixed MSISDNs; apply same 0→66 transform if so |
| All headers unconditional — blank values emitted as empty XML elements | [LOW] | Verify MLDD tolerates empty JMSPriority / OrderID elements; add xsl:if guards if not |
| GETCOLUMN hardcoded — adding/removing columns requires code change | [LOW] | Externalize to global variable or config in migration target |
| Dead variable `extId` in response; ResponseBase has no extId | [LOW] | Remove dead variable; if extId needed on ResponseBase, add OMXUtils:generateTrackingID() |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_MLDD_GET_SUB_DATA {
  attribute { priority=5; forwardChain=true; }
  declare { OrderRequest orderRequest; Activity orderCurrentActivity; }
  when { /* standard 4-condition WHEN with ActivityID=="MLDD_GET_SUB_DATA" */ }
  then {
    boolean isActResub = ...;  // no PurgePendingRequestsBeforeResubmit
    try {
      boolean isSkipped = true;

      /* POU Subscribers */
      for(int i ...) { for(int j ...) {
        // reqSuccess: Response[].ReferenceId == refId && CompletionStatus==2
        if(!reqSuccess) {
          chkRes = PreExecCheck via GetXMLForSubscriber(orderRequest, refId);
          if(chkRes == "true") {
            msisdn = Subscriber[j].MSISDN;
            if(String.startsWith(msisdn, "0"))
              msisdn = String.replaceFirst(msisdn, "0", "66");  // 0→66
            // [MLDD_GET_SUB_DATA XSLT — see §9.6]
            Event.Ext.sendEventImmediate(reqEvent);
            if(AllowWriteLog(OrderType)) { sendAudit(); }
            if(!isActResub) orderCurrentActivity.RequestCount++;
            isSkipped = false;
          }
        }
      }}

      /* COU Subscribers — NO 0→66 conversion */
      for(int i ...) { for(int p ...) { for(int q ...) {
        chkRes = PreExecCheck via GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId);
        if(chkRes == "true") {
          msisdn = ChildOU[p].Subscriber[q].MSISDN;  // raw — no normalisation
          Event.Ext.sendEventImmediate(reqEvent);
          if(!isActResub) orderCurrentActivity.RequestCount++;
          isSkipped = false;
        }
      }}}

      if(!isSkipped) { GetActivityStatusString("1"); SendDataToDB(); }
      else { SkipActivity("4"); }
    } catch(Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

Looks up the subscriber by RefID, extracts `xsd2:IMEI` from the GetSubDataResponse, and appends a `SubscriberExtendedInfo` with Name="IMEI_MLDD". Audit is gated by `AllowWriteLog`. Standard "000" fan-in.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | READ — OMXTrackingId + OrderType |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.MLDD_GET_SUB_DATA | Backend response |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Response[] appended; fan-in |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object  [No @extId — differs from other FMs using OMXUtils:generateTrackingID()]
    ├── ResponseCode          ← $eventResponse/ResponseCode      [Conditional]
    ├── ResponseMessage       ← $eventResponse/ResponseMsg       [Conditional]
    ├── CompletionStatus      ← $eventResponse/CompletionStatus  [Conditional]
    └── ReferenceId           ← $eventResponse/RefID             [Conditional]
```

### §19.4 IMEI Extraction & Write-back

```java
// Dead variable (line 17):
String extId = eventResponse.JMSCorrelationID+":"+eventResponse.RefID;  // NEVER USED

// Subscriber lookup:
subscriber = Instance.getByExtIdByUri("SUB:"+OMXTrackingId+":"+RefID, Subscriber);
if(subscriber == null)
    subscriber = Instance.getByExtIdByUri("CSUB:"+OMXTrackingId+":"+RefID, Subscriber);

// IMEI extraction:
String imei = XPath.evalAsString("$eventResponse/payload/xsd2:GetSubDataResponse/xsd2:User/xsd2:IMEI");

// ⚠ NO null check on subscriber — NPE if null:
subscriber.ExtendedInfo[subscriber.ExtendedInfo@length] =
    Instance.createInstance("xslt://SubscriberExtendedInfo");
// Name="IMEI_MLDD", Value=$imei
```

### §19.5 Fan-in Completion Logic

```java
int successResponseCount = XPath.evalAsInt(
    "count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = '000'])");
if(currActivity.RequestCount == successResponseCount) { return "true"; }
else { return "false"; }
```

Standard "000" suffix count fan-in.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
