# Request_SMDP_PLUS_DOWNLOAD_PUSH

> Per-subscriber eSIM Download Order request to SM-DP+. Dispatches one `DownloadOrderRequest` per subscriber (POU + COU) carrying ICCID+Luhn checksum, device EID, and vendor. First of two SM-DP+ push operations.

**Backend:** SM-DP+ | **Pattern:** Per-Subscriber Dispatch | **Priority:** 5 | **ForwardChain:** true

---

## §1 — Overview & Purpose

Sends an eSIM **Download Order Request** to the SM-DP+ server for each eSIM subscriber (SIM_TYPE="B"). One request is dispatched per subscriber across POU and COU structures.

The payload includes:
- `iccid` = `ICC_ID_CHG_SUM` (computed by preceding `OMX_CAL_CHK_SUM_SUB_LEVEL`) + "F"
- `eid` (device EID, 3-way priority selection)
- `vendor` (optional)

> **[LOW] No isActResub / PurgePendingRequestsBeforeResubmit:** Unlike many per-subscriber FM rules, this rule does not call `PurgePendingRequestsBeforeResubmit` before resubmit dispatching. The `reqSuccess` check provides partial protection by skipping already-successful subscribers.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_SMDP_PLUS_DOWNLOAD_PUSH` |
| Priority | 5 |
| ForwardChain | true |
| Rule File | `OMXFM/Request/Request_SMDP_PLUS_DOWNLOAD_PUSH.rule` |
| Response Rulefunction | `Response_SMDP_PLUS_DOWNLOAD_PUSH.rulefunction` |
| Backend System | SM-DP+ (eSIM Remote SIM Provisioning Server) |
| Dispatch Pattern | Per-subscriber (POU + COU), one request per subscriber |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context; subscriber ICCID/EID data read |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | RequestCount, Response[], PreExecCheck |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "SMDP_PLUS_DOWNLOAD_PUSH"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SMDP_PLUS_DOWNLOAD_PUSH"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow Diagram

1. Compute `isActResub` (not acted upon — no purge)
2. Read PreExecCheck from activity concept
3. Loop POU subscribers: check `reqSuccess` (skip if already CompletionStatus=2)
4. Evaluate PreExecCheck per subscriber via `GetXMLForSubscriber`
5. If passes: create and send `SMDP_PLUS_DOWNLOAD` request event via XSLT
6. Set `isSkipped=false`; increment `RequestCount` (if not resubmit)
7. Emit audit logger event
8. Repeat steps 3–7 for COU subscribers (uses `GetXMLForSubscriberInChildOU`)
9. After loops: if `!isSkipped` → Status="1" + SendDataToDB; else SkipActivity("4")

---

## §6 — Rule Action (THEN)

### §6.1 reqSuccess Check

```java
for (int iResp = 0; iResp < orderCurrentActivity.Response@length; iResp++) {
  if (String.equals(orderCurrentActivity.Response[iResp].ReferenceId, subRefId)
     && orderCurrentActivity.Response[iResp].CompletionStatus == 2) {
    reqSuccess = true;
  }
}
```

Subscribers with a successful previous response (RefId match + CompletionStatus=2) are skipped on resubmit.

### §6.2 EID Selection Logic (3-way priority)

| Priority | Condition | Source |
|----------|-----------|--------|
| 1st | `exists(ResourceInfo[PEID, Source=FE])` AND not starting "NONE-" | `ResourceInfo[PEID, Source=FE].ValuesArray` |
| 2nd | `exists(ResourceInfo[NEW_PEID])` | `ResourceInfo[NEW_PEID].ValuesArray` |
| 3rd (otherwise) | Fallback | `ResourceInfo[NEW_EID, Source=FE].ValuesArray` (conditional via xsl:if) |

In the `otherwise` branch, both POU and COU use `<xsl:if>` guards — so `<eid>` may be absent if no matching resource exists.

### §6.3 Status Management

| Condition | Action |
|-----------|--------|
| At least one request dispatched | `Status="1"` + `SendDataToDB` |
| All subscribers skipped | `SkipActivity("4")` |
| Exception | `HandleActivityException(…, "")` |

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Used in `PREPAID_PREACTIVATION` step 12 (conditional: SIM_TYPE="B"). Requires prior `OMX_CAL_CHK_SUM_SUB_LEVEL` to have computed `ICC_ID_CHG_SUM`.

### §8.2 ESB / JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.SMDP_PLUS_DOWNLOAD` | Initiate eSIM profile download |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.SMDP_PLUS_DOWNLOAD` | SM-DP+ download response |

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | SM-DP+ (SGP.22 RSP standard) |
| Operation | DownloadOrder (ES2+ API) |
| functionRequesterIdentifier | "1.3.6.1.4.1.30378" (static OID — operator identifier) |

### §8.4 BE Working Memory Dependencies

| Concept | R/W | Fields Read |
|---------|-----|-------------|
| Subscriber (POU/COU) | Read | `ExtendedInfo[ICC_ID_CHG_SUM].Value`, `ExtendedInfo[VENDOR].Value`, `ResourceInfo[PEID/NEW_PEID/NEW_EID]` |
| `orderCurrentActivity.Response[]` | Read | `ReferenceId`, `CompletionStatus` (reqSuccess check) |
| `orderCurrentActivity.RequestCount` | R/W | Incremented per dispatched request |

### §8.5 ExtendedInfo Fields Required

| Name | Required/Optional | Purpose |
|------|------------------|---------|
| `ICC_ID_CHG_SUM` | Required | ICCID+Luhn for SM-DP+ (set by preceding OMX_CAL_CHK_SUM_SUB_LEVEL) |
| `VENDOR` | Optional | eSIM vendor identifier |

### §8.6 Global Variable Dependencies

| Path | Used In |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit |
| `$globalVariables/OMX_OM/WritePayload` | Conditional audit payload |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| XSLT Param | POU Variant | COU Variant |
|-----------|-------------|-------------|
| `$orderRequest` | orderRequest | orderRequest |
| `$pSubRefId` / `$cSubRefId` | POU subscriber RefId | COU subscriber RefId |
| `$psub` / `$csub` | POU subscriber concept | COU subscriber concept |

### §9.4 Payload Root Element

| Element | Source / Value | Condition |
|---------|----------------|-----------|
| `DownloadOrderRequest/header/functionRequesterIdentifier` | "1.3.6.1.4.1.30378" (static OID) | Always |
| `DownloadOrderRequest/header/functionCallIdentifier` | `$orderRequest/OrderData/OMXTrackingId` | if exists |
| `DownloadOrderRequest/iccid` | `concat(ICC_ID_CHG_SUM/Value, "F")` | Always |
| `DownloadOrderRequest/eid` | 3-way: PEID(FE,not-NONE-) → NEW_PEID → NEW_EID(FE) | Conditional (see §6.2) |
| `DownloadOrderRequest/vendor` | `ExtendedInfo[VENDOR]/Value` | if exists |

### §9.7 Generated XML Example

```xml
<event>
  <JMSCorrelationID>OMX-TRK-001</JMSCorrelationID>
  <OrderID>ORD-001</OrderID>
  <RefID>SUB-REF-001</RefID>
  <payload>
    <DownloadOrderRequest>
      <header>
        <functionRequesterIdentifier>1.3.6.1.4.1.30378</functionRequesterIdentifier>
        <functionCallIdentifier>OMX-TRK-001</functionCallIdentifier>
      </header>
      <iccid>89660720000012345678F</iccid>
      <eid>89049032001234567890123456789012</eid>
      <vendor>Giesecke</vendor>
    </DownloadOrderRequest>
  </payload>
</event>
```

### §9.8 XSLT Stylesheet Source (POU Variant)

```xml
<xsl:stylesheet version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="pSubRefId"/>
  <xsl:param name="psub"/>
  <createEvent><event>
    <!-- JMSPriority, JMSCorrelationID, OrderID — conditional -->
    <RefID><xsl:value-of select="$pSubRefId"/></RefID>
    <!-- UserName, PassWord, OrderType — conditional -->
    <payload><DownloadOrderRequest>
      <header>
        <functionRequesterIdentifier>1.3.6.1.4.1.30378</functionRequesterIdentifier>
        <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
          <functionCallIdentifier><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></functionCallIdentifier>
        </xsl:if>
      </header>
      <iccid><xsl:value-of select="concat($psub/ExtendedInfo[Name='ICC_ID_CHG_SUM']/Value, 'F')"/></iccid>
      <!-- eid: 3-way xsl:choose -->
      <xsl:choose>
        <xsl:when test="exists($psub/ResourceInfo[ResourceName='PEID' and Source='FE']/ValuesArray)">
          <xsl:if test="not(starts-with(upper-case(...PEID/FE.ValuesArray),'NONE-'))">
            <xsl:if test="$psub/ResourceInfo[ResourceName='PEID' and Source='FE']/ValuesArray">
              <eid><xsl:value-of select="...PEID/FE/ValuesArray"/></eid>
            </xsl:if>
          </xsl:if>
        </xsl:when>
        <xsl:when test="exists($psub/ResourceInfo[ResourceName='NEW_PEID']/ValuesArray)">
          <xsl:if test="$psub/ResourceInfo[ResourceName='NEW_PEID']/ValuesArray">
            <eid><xsl:value-of select="...NEW_PEID/ValuesArray"/></eid>
          </xsl:if>
        </xsl:when>
        <xsl:otherwise>
          <xsl:if test="$psub/ResourceInfo[ResourceName='NEW_EID' and Source='FE']/ValuesArray">
            <eid><xsl:value-of select="...NEW_EID/FE/ValuesArray"/></eid>
          </xsl:if>
        </xsl:otherwise>
      </xsl:choose>
      <xsl:if test="$psub/ExtendedInfo[Name='VENDOR']/Value">
        <vendor><xsl:value-of select="$psub/ExtendedInfo[Name='VENDOR']/Value"/></vendor>
      </xsl:if>
    </DownloadOrderRequest></payload>
  </event></createEvent>
</xsl:stylesheet>
```

COU variant is identical with `$cSubRefId` and `$csub` parameters substituted.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority           ← $orderRequest/OrderPriority              [Conditional]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId    [Conditional]
    ├── OrderID               ← $orderRequest/OrderData/OrderID          [Conditional]
    ├── RefID                 ← $pSubRefId (POU) / $cSubRefId (COU)      [Always]
    ├── UserName              ← $orderRequest/OrderData/User             [Conditional]
    ├── PassWord              ← $orderRequest/OrderData/Password         [Conditional]
    ├── OrderType             ← $orderRequest/OrderData/OrderType        [Conditional]
    └── payload
        └── DownloadOrderRequest                                          [Always]
            ├── header/functionRequesterIdentifier  "1.3.6.1.4.1.30378" [Always/Static]
            ├── header/functionCallIdentifier  ← OMXTrackingId           [Conditional]
            ├── iccid  ← concat(ICC_ID_CHG_SUM/Value, "F")               [Always]
            ├── eid    ← 3-way: PEID(FE,not NONE-) → NEW_PEID → NEW_EID  [Conditional]
            └── vendor ← ExtendedInfo[VENDOR]/Value                      [Conditional]
```

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| Guard | None — always logged when request dispatched |
| PROCESS_ID | `concat(pid, "_REQ")` |
| OPERATION_NAME | "SMDP_PLUS_DOWNLOAD_PUSH" |
| AUDIT_TRACE | "Request Sent for SMDP_PLUS_DOWNLOAD_PUSH" ✓ |
| Payload | Conditional: `<ns:ServicePayload><xsl:copy-of select="$reqEvent"/></ns:ServicePayload>` |

---

## §12 — Activity Status Management

| Condition | Action |
|-----------|--------|
| At least one request dispatched | Status="1" + SendDataToDB |
| All subscribers skipped | SkipActivity("4") |
| Exception | HandleActivityException(…, "") |

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `GetXMLForSubscriber(orderRequest, subRefId)` | Serializes POU subscriber for PreExecCheck |
| `GetXMLForSubscriberInChildOU(orderRequest, subRefId, pOuRefId)` | Serializes COU subscriber for PreExecCheck |
| `GetActivityStatusString("1", false)` | Status "1" string |
| `SendDataToDB(orderRequest)` | Persists order state |
| `SkipActivity("4")` | Marks activity skipped |

---

## §15 — Function Dependency Tree

```text
Request_SMDP_PLUS_DOWNLOAD_PUSH.rule
├── [POU loop]
│   ├── [reqSuccess check on Response[]]
│   ├── GetXMLForSubscriber(orderRequest, pSubRefId)
│   ├── XPath.execute(chkXPath, sXML, ns)                [PreExecCheck]
│   ├── Event.createEvent(XSLT → SMDP_PLUS_DOWNLOAD)
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   └── Event.Ext.sendEventImmediate(Logger audit)
├── [COU loop — same, uses GetXMLForSubscriberInChildOU]
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | For each eSIM subscriber, send DownloadOrderRequest to SM-DP+ with ICCID+checksum+"F", EID, vendor |
| R2 | Skip already-successful subscribers (reqSuccess check) |
| R3 | EID priority: PEID(FE,not-NONE-) > NEW_PEID > NEW_EID(FE); absent if none found |
| R4 | ICCID must be provided as ICC_ID_CHG_SUM (set by preceding OMX_CAL_CHK_SUM_SUB_LEVEL) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| No PurgePendingRequestsBeforeResubmit | [LOW] | reqSuccess check mitigates; add purge call for full safety |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_SMDP_PLUS_DOWNLOAD_PUSH {
  attribute { priority = 5; forwardChain = true; }
  then {
    boolean isActResub = (...);
    try {
      // NOTE: no PurgePendingRequestsBeforeResubmit
      boolean isSkipped = true;
      // POU loop
      for (int p=0; p<pOuLen; p++) {
        for (int ps=0; ps<pSubLen; ps++) {
          // reqSuccess check
          if (!reqSuccess) {
            // evaluate PreExecCheck
            if (chkRes == "true") {
              Events...SMDP_PLUS_DOWNLOAD reqEvent = Event.createEvent("xslt://...");
              /* XSLT: DownloadOrderRequest with iccid=ICC_ID_CHG_SUM+"F", eid (3-way), vendor — see §9.8 */
              Event.Ext.sendEventImmediate(reqEvent);
              isSkipped = false;
              if (!isActResub) orderCurrentActivity.RequestCount++;
              Event.Ext.sendEventImmediate(logEvent);
            }
          }
        }
      }
      // COU loop — identical
      if (!isSkipped) {
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
    } catch (Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

Creates a `ResponseBase` concept from the SM-DP+ response, appends to `currActivity.Response`, logs the response, and signals fan-in completion using the **success-count** pattern (`ResponseCode` ending "000").

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SMDP_PLUS_DOWNLOAD` | SM-DP+ download response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking |

### §19.3 ResponseBase Concept Construction

Type: `Concepts.FM.Base.ResponseBase` (generic)

```text
createObject
└── object  extId=OMXUtils:generateTrackingID()           [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode   [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg    [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId       ← $eventResponse/RefID          [Conditional]
```

### §19.4 Response Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Return "true" | All dispatched requests received successful ResponseCode ending "000" |

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| Guard | None — always logs |
| PROCESS_ID | `concat(pid, "_RES")` |
| OPERATION_NAME | "SMDP_PLUS_DOWNLOAD_PUSH" ✓ |
| AUDIT_TRACE | "Response received for SMDP_PLUS_DOWNLOAD_PUSH" ✓ |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
