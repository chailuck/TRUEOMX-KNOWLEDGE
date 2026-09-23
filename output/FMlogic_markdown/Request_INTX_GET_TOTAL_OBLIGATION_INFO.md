# Request_INTX_GET_TOTAL_OBLIGATION_INFO

> Per-subscriber parallel INTX obligation query — searches by MSISDN in MOBILE business line; writes CreditLimit, TotalObligation, unbilledUsageAmount directly to Subscriber concept fields.

**Author:** DESKTOP-995HR2V | **forwardChain:** true | **Generated:** 2026-08-04

---

## §1 Overview & Purpose

This FM queries the INTX system for a subscriber's total credit obligation. It sends a search request using the subscriber's MSISDN (type=`PRIMRESOURCEVAL`) within the hardcoded `MOBILE` business line. The response extracts three financial fields — `creditLimit`, `totalObligation`, and `unbilledUsageAmount` — and writes them directly to the subscriber concept's named fields (not ExtendedInfo). Standard parallel fan-out per subscriber (POU + COU).

> **[4 DEAD VARIABLES]:** `pOuId`, `pSubId` (POU) and `cOuId`, `cSubId` (COU) are extracted from the order but never passed to the XSLT or used in any logic. Can be safely removed.

> **Audit unconditional:** Unlike MLDD and MCS which gate audit on `AllowWriteLog(OrderType)`, this FM always emits the request audit event immediately after sending — no gating condition.

> **Direct field write-back with null guard:** The response writes to `subscriber.CreditLimit`, `subscriber.TotalObligation`, `subscriber.unbilledUsageAmount` — direct concept fields, not ExtendedInfo. A proper `if(subscriber != null)` guard is present (no NPE risk).

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_INTX_GET_TOTAL_OBLIGATION_INFO.rule` | 135 lines |
| Response file | `Response_INTX_GET_TOTAL_OBLIGATION_INFO.rulefunction` | 57 lines |
| Author | DESKTOP-995HR2V | Machine name, not person name |
| forwardChain | true | |
| Request event | `Events.OMConsumers.OMXFM.Request.INTX_GET_TOTAL_OBLIGATION_INFO` | One per subscriber |
| Response event | `Events.OMConsumers.OMXFM.Response.INTX_GET_TOTAL_OBLIGATION_INFO` | |
| Schema NS (ns) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetTotalObligationInfo.xsd` | |
| Response concept | `Concepts.FM.Base.ResponseBase` | extId via OMXUtils:generateTrackingID() inside XSLT |
| extId on request event | `OMXUtils:generateTrackingID()` (in XSLT) | Always |
| reqSuccess dedup key | Subscriber RefId (pSubRefId / cSubRefId) | |
| Fan-out | Parallel — `Event.Ext.sendEventImmediate` per subscriber (POU + COU) | |
| Fan-in | Standard "000" count == RequestCount | |
| Resubmit handler | `PurgePendingRequestsBeforeResubmit` present | Clears pending queue on resubmit |
| Credential gate | `IsEnableUserPass='true'` global variable → UserName/PassWord headers | |
| Audit gate (request) | Unconditional — always sends after event | No AllowWriteLog gate |
| Audit gate (response) | Unconditional | |
| PreExecCheck source | `nextAct.PreExecCheck` via live Activity lookup | Same pattern as MCS_SUBSCRIPTION_MARKUSED |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Subscriber data; OMXTrackingId; User/Password for credential gate |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | RequestCount++; Response[]; PurgePending on resubmit |
| `nextAct` | Concepts.OM.ProcessConfig.Activity | Live lookup — provides PreExecCheck XPath string |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "INTX_GET_TOTAL_OBLIGATION_INFO"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "INTX_GET_TOTAL_OBLIGATION_INFO"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 Execution Flow Diagram

1. **Setup** — isActResub; nextAct live lookup; chkXPath from nextAct.PreExecCheck; isSkipped=true
2. **Resubmit purge** — if isActResub → `PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
3. **POU Subscribers loop** — for each ParentOU × Subscriber:
   - Extract pSubRefId, msisdn (`pOuId`, `pSubId` extracted but unused — dead variables)
   - reqSuccess check: Response[].ReferenceId==pSubRefId AND CompletionStatus==2
   - If chkXPath set: PreExecCheck via `GetXMLForSubscriber`
   - Create + send event immediately; unconditional audit; RequestCount++; isSkipped=false
4. **COU Subscribers loop** — for each ParentOU × ChildOU × Subscriber:
   - Extract cSubRefId, msisdn (`cOuId`, `cSubId` extracted but unused — dead variables)
   - Same reqSuccess + PreExecCheck via `GetXMLForSubscriberInChildOU`
   - Same send + audit + count
5. **Status** — if !isSkipped → `GetActivityStatusString("1")` + `SendDataToDB`; else → `SkipActivity("4")`
6. **Exception** — catch → `HandleActivityException`

---

## §6 Rule Action (THEN) — Data Extraction

### §6.1 Variables Extracted Per-Subscriber

| Variable | Source (POU) | Source (COU) | Used In |
|----------|-------------|-------------|---------|
| `pSubRefId / cSubRefId` | `Subscriber[s].RefId` | `Subscriber[s].RefId` | reqSuccess dedup; RefID header |
| `msisdn` | `Subscriber[s].MSISDN` | `Subscriber[s].MSISDN` | `ns:value` in searchInfoArray |
| `pOuId` | `ParentOU[p].OUId` | — | **[DEAD — never used]** |
| `pOuRefId` | `ParentOU[p].RefId` | — | COU PreExecCheck only |
| `pSubId` | `Subscriber[s].SubscriberId` | — | **[DEAD — never used]** |
| `cOuId` | — | `ChildOU[c].OUId` | **[DEAD — never used]** |
| `cSubId` | — | `Subscriber[s].SubscriberId` | **[DEAD — never used]** |

### §6.2 Credential Gate

```xml
<xsl:if test="$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass='true'">
    <UserName><!-- $orderRequest/OrderData/User --></UserName>
    <PassWord><!-- $orderRequest/OrderData/Password --></PassWord>
</xsl:if>
```

`$globalVariables` is passed as an XSLT parameter — required because the credential check reads a global variable from inside the XSLT context.

---

## §7 System & Integration Dependencies

### §7.1 ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Purpose |
|-----------|---------|-------------|---------|
| [OUTBOUND] | FM JMS | INTX_GET_TOTAL_OBLIGATION_INFO queue | Obligation query per subscriber (parallel) |
| [INBOUND] | FM JMS | INTX_GET_TOTAL_OBLIGATION_INFO response | GetTotalObligationInfoRes |
| [LOG] | OMXESB Logger | Audit event | Unconditional — both request and response always audit |

### §7.2 Backend API Details

| Field | Value |
|-------|-------|
| Backend | INTX (Obligation/Credit information system) |
| Operation | GetTotalObligationInfo |
| Request root | `ns:GetTotalObligationInfoReq` |
| Response root | `xsd2:GetTotalObligationInfoRes` |
| Search key 1 | type=`'PRIMRESOURCEVAL'`, value=`$msisdn` |
| Search key 2 | type=`'BUSINESSLINE'`, value=`'MOBILE'` (hardcoded) |
| Correlation in payload | `ns:correlatedId` = OMXTrackingId |
| MSISDN format | Raw — no 0→66 normalisation applied |

### §7.3 BE Working Memory Dependencies

| Concept | Field | Access | Notes |
|---------|-------|--------|-------|
| OrderRequest | OMXTrackingId, OrderPriority, OrderID, OrderType | READ | Standard headers + correlatedId |
| OrderRequest | OrderData.User / Password | READ | Conditional on IsEnableUserPass='true' |
| Subscriber | RefId, MSISDN | READ | Correlation + search key |
| Subscriber | **CreditLimit** | WRITTEN | Direct field — not ExtendedInfo; null-guarded |
| Subscriber | **TotalObligation** | WRITTEN | Direct field — not ExtendedInfo; null-guarded |
| Subscriber | **unbilledUsageAmount** | WRITTEN | Direct field (lowercase 'u') — not ExtendedInfo; null-guarded |
| Activity | RequestCount / Response[] / Status | READ+WRITTEN | Standard |

### §7.4 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Credential gate — enable UserName/PassWord headers |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `OMX_OM/WritePayload` | Payload inclusion in audit |

---

## §8 Detailed Payload Build

### §8.1 XSLT Parameters

| Parameter | Bound From (POU) | Bound From (COU) | Notes |
|-----------|-----------------|-----------------|-------|
| `$orderRequest` | orderRequest concept | orderRequest concept | |
| `$pSubRefId / $cSubRefId` | POU Subscriber RefId | COU Subscriber RefId | RefID header only; param name differs between variants |
| `$globalVariables` | Global variable tree | Global variable tree | Needed for IsEnableUserPass credential check inside XSLT |
| `$msisdn` | Subscriber MSISDN (raw) | Subscriber MSISDN (raw) | No normalisation applied |

### §8.2 XSLT Field Mapping Tree

```text
createEvent
└── event
    ├── @extId              ← OMXUtils:generateTrackingID()                           [Always]
    ├── JMSPriority         ← $orderRequest/OrderPriority                             [Always]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId                  [Always]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                         [Always]
    ├── RefID               ← $pSubRefId / $cSubRefId                                [Always]
    ├── UserName            ← $orderRequest/OrderData/User                            [Credential-gated: IsEnableUserPass='true']
    ├── PassWord            ← $orderRequest/OrderData/Password                        [Credential-gated: IsEnableUserPass='true']
    ├── OrderType           ← $orderRequest/OrderData/OrderType                       [Always]
    └── payload
        └── ns:GetTotalObligationInfoReq
            ├── ns:correlatedId    ← $orderRequest/OrderData/OMXTrackingId           [Always]
            └── ns:searchList
                ├── ns:searchInfoArray
                │   ├── ns:type   ← 'PRIMRESOURCEVAL'                                [Always / Hardcoded]
                │   └── ns:value  ← $msisdn                                          [Always]
                └── ns:searchInfoArray
                    ├── ns:type   ← 'BUSINESSLINE'                                   [Always / Hardcoded]
                    └── ns:value  ← 'MOBILE'                                         [Always / Hardcoded]
```

### §8.3 Generated XML Example

```xml
<event extId="TRK-001">
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-001</JMSCorrelationID>
  <OrderID>ORD-001</OrderID>
  <RefID>SUB-REF-001</RefID>
  <!-- UserName / PassWord only if IsEnableUserPass=true -->
  <OrderType>3</OrderType>
  <payload>
    <ns:GetTotalObligationInfoReq
      xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetTotalObligationInfo.xsd">
      <ns:correlatedId>OMX-TRK-001</ns:correlatedId>
      <ns:searchList>
        <ns:searchInfoArray>
          <ns:type>PRIMRESOURCEVAL</ns:type>
          <ns:value>0812345678</ns:value>
        </ns:searchInfoArray>
        <ns:searchInfoArray>
          <ns:type>BUSINESSLINE</ns:type>
          <ns:value>MOBILE</ns:value>
        </ns:searchInfoArray>
      </ns:searchList>
    </ns:GetTotalObligationInfoReq>
  </payload>
</event>
```

---

## §9 Audit Logging

| Phase | Gate | AUDIT_TRACE | Payload param |
|-------|------|------------|---------------|
| Request | [Unconditional] | `"Request Sent for INTX_GET_TOTAL_OBLIGATION_INFO"` | `$reqEvent` |
| Response | [Unconditional] | `"Response received for INTX_GET_TOTAL_OBLIGATION_INFO"` | `$eventResponse` |

> No `AllowWriteLog(OrderType)` gate — both request and response audits fire for all order types.

---

## §10 Activity Status Management

| Condition | Call | Code |
|-----------|------|------|
| At least one subscriber sent | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" (RUNNING) |
| No subscribers qualify | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" (SKIPPED) |

---

## §11 Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §12 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears pending request queue on resubmit |
| `GetXMLForSubscriber(req, refId)` | POU subscriber XML for PreExecCheck |
| `GetXMLForSubscriberInChildOU(req, refId, pouRefId)` | COU subscriber XML for PreExecCheck |
| `BRMS.IsBlankOrStringNull(str)` | Null/blank string check in response |
| `Number.doubleValue(str)` | String-to-double conversion for financial fields |
| `Log.getLogger / Log.log` | Structured logging in response (vs System.debugOut in other FMs) |

---

## §13 Function Dependency Tree

```text
Request_INTX_GET_TOTAL_OBLIGATION_INFO (rule)
├── Instance.getByExtIdByUri(NextActivityName, Activity)  [nextAct]
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if isActResub]
├── [per POU × Subscriber]:
│   ├── Response[].ReferenceId == pSubRefId  [reqSuccess]
│   ├── GetXMLForSubscriber(req, pSubRefId) + XPath.execute(chkXPath)
│   ├── Event.createEvent("xslt://INTX_GET_TOTAL_OBLIGATION_INFO")
│   │   └── OMXUtils:generateTrackingID()  [extId]
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   ├── Event.Ext.sendEventImmediate(auditEvent)  [unconditional]
│   └── orderCurrentActivity.RequestCount++
├── [per POU × COU × Subscriber]: GetXMLForSubscriberInChildOU + same pattern
├── GetActivityStatusString("1") + SendDataToDB  [or SkipActivity("4")]
└── HandleActivityException  [catch]

Response_INTX_GET_TOTAL_OBLIGATION_INFO (rulefunction)
├── Log.getLogger(...)  [structured logger — not System.debugOut]
├── Instance.createInstance("xslt://ResponseBase")  [extId via OMXUtils in XSLT]
├── currActivity.Response[length] = activityRes
├── XPath.evalAsString → creditLimit
├── XPath.evalAsString → totalObligation
├── XPath.evalAsString → unBilledUsageAmount
├── Instance.getByExtIdByUri("SUB:"+OMXTrackingId+":"+RefID)
│   └── "CSUB:..." fallback if null
├── if(subscriber != null):
│   ├── !IsBlankOrStringNull(creditLimit) → subscriber.CreditLimit = Number.doubleValue(creditLimit)
│   ├── !IsBlankOrStringNull(totalObligation) → subscriber.TotalObligation = Number.doubleValue(totalObligation)
│   └── !IsBlankOrStringNull(unBilledUsageAmount) → subscriber.unbilledUsageAmount = Number.doubleValue(unBilledUsageAmount)
├── Event.Ext.sendEventImmediate(auditEvent)  [unconditional]
└── XPath.evalAsInt("count(Response[tib:right...='000'])") → fan-in
```

---

## §14 Concept Definitions Referenced

| Concept | Key Fields Used | Role |
|---------|----------------|------|
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId | Standard; extId via OMXUtils in XSLT |
| `Concepts.OrderRequest.OrderElements.Subscriber` | CreditLimit, TotalObligation, unbilledUsageAmount | Written via direct field assignment (not ExtendedInfo) |

---

## §15 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Purge pending requests on resubmit (`PurgePendingRequestsBeforeResubmit`). |
| R2 | Per-subscriber parallel fan-out (POU + COU) using RefId for reqSuccess dedup and RefID header. |
| R3 | Pass `$globalVariables` as XSLT param; apply credential gate on `IsEnableUserPass='true'`. |
| R4 | Payload: 2 searchInfoArray entries — PRIMRESOURCEVAL=$msisdn; BUSINESSLINE='MOBILE' (hardcoded). Include `ns:correlatedId`=OMXTrackingId. |
| R5 | No MSISDN normalisation — raw MSISDN sent as-is. |
| R6 | Audit both request and response unconditionally (no AllowWriteLog gate). |
| R7 | Response: extract creditLimit, totalObligation, unbilledUsageAmount from `xsd2:GetTotalObligationInfoRes`; write to Subscriber concept fields directly (not ExtendedInfo); guard all writes with IsBlankOrStringNull check. |
| R8 | Null-guard subscriber lookup before any field write. |
| R9 | Fan-in: standard "000" count == RequestCount. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| 4 dead variables (pOuId, pSubId, cOuId, cSubId) add noise and maintenance cost | [LOW] | Remove in migration target |
| BUSINESSLINE hardcoded to 'MOBILE' — other business lines not queried | [LOW] | Verify INTX always uses MOBILE for this process; externalise to activity parameter if needed |
| POU and COU XSLT identical but param name differs ($pSubRefId vs $cSubRefId) — duplicated code | [LOW] | Refactor to single XSLT with unified $refId param in migration |

---

## §16 Full Source Code (Request Rule — key structure)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_TOTAL_OBLIGATION_INFO {
  attribute { priority=5; forwardChain=true; }
  declare { OrderRequest orderRequest; Activity orderCurrentActivity; }
  when { /* standard 4-condition WHEN */ }
  then {
    boolean isActResub = ...;
    try {
      Activity nextAct = Instance.getByExtIdByUri(NextActivityName, Activity);
      String chkXPath = nextAct.PreExecCheck;
      boolean isSkipped = true;
      if(isActResub) PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

      /* POU Subscribers */
      for(int p ...) {
        String pOuId = ParentOU[p].OUId;        // DEAD — never used
        String pOuRefId = ParentOU[p].RefId;    // used for COU PreExecCheck
        for(int s ...) {
          String pSubId = Subscriber[s].SubscriberId;  // DEAD — never used
          String pSubRefId = Subscriber[s].RefId;
          String msisdn = Subscriber[s].MSISDN;
          // reqSuccess + PreExecCheck
          // [INTX_GET_TOTAL_OBLIGATION_INFO XSLT — see §8.2]
          Event.Ext.sendEventImmediate(reqEvent);
          isSkipped = false;
          if(!isActResub) orderCurrentActivity.RequestCount++;
          sendAudit();  // unconditional
        }
      }

      /* COU Subscribers */
      for(int p ...) { for(int c ...) {
        String cOuId = ChildOU[c].OUId;  // DEAD — never used
        for(int s ...) {
          String cSubId = ChildOU[c].Subscriber[s].SubscriberId;  // DEAD — never used
          String cSubRefId = ChildOU[c].Subscriber[s].RefId;
          String msisdn = ChildOU[c].Subscriber[s].MSISDN;
          // reqSuccess + PreExecCheck via GetXMLForSubscriberInChildOU
          Event.Ext.sendEventImmediate(reqEvent);
          ...
        }
      }}

      if(!isSkipped) { GetActivityStatusString("1"); SendDataToDB(); }
      else { SkipActivity("4"); }
    } catch(Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §17 Response Message Rule

### §17.1 Overview

Extracts three financial fields from the INTX response and writes them directly to the matched Subscriber concept (not ExtendedInfo). Proper null-guard on subscriber lookup. Uses structured logging (`Log.getLogger`) rather than `System.debugOut`. Audit unconditional. Fan-in: standard "000" count.

### §17.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | READ — OMXTrackingId for subscriber lookup |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.INTX_GET_TOTAL_OBLIGATION_INFO | Backend response |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Response[] appended; fan-in |

### §17.3 ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId            ← OMXUtils:generateTrackingID() (in XSLT)   [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode                [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg                 [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus            [Conditional]
    └── ReferenceId       ← $eventResponse/RefID                       [Conditional]
```

### §17.4 Financial Field Extraction & Write-back

```java
// All from xsd2:GetTotalObligationInfoRes:
String creditLimit         = XPath("xsd2:GetTotalObligationInfoRes/xsd2:creditLimit");
String totalObligation     = XPath("xsd2:GetTotalObligationInfoRes/xsd2:totalObligation");
String unBilledUsageAmount = XPath("xsd2:GetTotalObligationInfoRes/xsd2:unbilledUsageAmount");

// Subscriber lookup (with null guard):
subscriber = Instance.getByExtIdByUri("SUB:"+OMXTrackingId+":"+RefID);
if(subscriber == null)
    subscriber = Instance.getByExtIdByUri("CSUB:"+OMXTrackingId+":"+RefID);

if(subscriber != null) {  // proper null guard
    if(!IsBlankOrStringNull(creditLimit))
        subscriber.CreditLimit = Number.doubleValue(creditLimit);
    if(!IsBlankOrStringNull(totalObligation))
        subscriber.TotalObligation = Number.doubleValue(totalObligation);
    if(!IsBlankOrStringNull(unBilledUsageAmount))
        subscriber.unbilledUsageAmount = Number.doubleValue(unBilledUsageAmount);
    // Note: field name is unbilledUsageAmount (lowercase 'u')
}
```

### §17.5 Fan-in Completion Logic

```java
int successResponseCount = XPath.evalAsInt(
    "count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = '000'])");
if(currActivity.RequestCount == successResponseCount) { return "true"; }
else { return "false"; }
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
