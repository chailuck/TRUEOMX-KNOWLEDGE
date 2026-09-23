# Request_INTX_GET_MASTER_MINOR_SIM_INFO

> Per-subscriber INTX lookup of Multi-SIM master/minor relationships by MSISDN — creates MultiSIMInfo concept with nested Master + Minor[] children; skips if already populated.

**Author:** SathidP-PC | **forwardChain:** true | **Generated:** 2026-08-04

---

## §1 Overview & Purpose

Queries INTX for the master/minor SIM relationship for a subscriber's MSISDN. Returns the primary (Master) SIM info and all associated secondary (Minor) SIMs. The response creates a `Concepts.MultiSIM.MultiSIMInfo` concept instance with a nested `Master` object and one `Minor[]` per secondary SIM, and assigns it to `subscriber.MultiSIMInfo`. If `MultiSIMInfo` is already populated the subscriber is skipped. One request per subscriber — no multi-SIM fan-out.

> **[DEAD CODE]:** `PurgePendingRequestsBeforeResubmit` commented out — resubmit does not purge pending queue for this FM.

> **POU vs COU Minor source asymmetry:** POU creates `Minor[]` from BOTH `eSimResourceOfferInfoList` AND `mutiSimResourceOfferInfoList`; COU creates `Minor[]` from `mutiSimResourceOfferInfoList` only (no eSIM list). This is a behavioral difference between POU and COU response handling.

> **[TYPO in schema path]:** `ns5:mutiSimResourceOfferInfoList` — "muti" instead of "multi". This is in the INTX schema itself and must be reproduced exactly in any migration.

> **Active debug output:** `System.debugOut("set master from INT_GET_MASTER_MINOR_SIM_INFO")` calls are NOT commented out — live debug logging left in production code.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_INTX_GET_MASTER_MINOR_SIM_INFO.rule` | 123 lines |
| Response file | `Response_INTX_GET_MASTER_MINOR_SIM_INFO.rulefunction` | 71 lines |
| Author | SathidP-PC | |
| forwardChain | true | |
| Schema NS (ns / ns5) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetMasterMinorSIMInfo.xsd` | |
| Request root element | `ns:GetMasterMinorSIMInfoReq` | |
| Response root element | `xsd5:GetMasterMinorSIMInfoRes` | |
| Response concept | `Concepts.FM.Base.ResponseBase` | Standard; fields mapped unconditionally (no xsl:if wrappers) |
| extId generation | `OMXUtils.generateTrackingID()` in BE, passed as XSLT param | |
| Search key | MSISDN (from `currSub.MSISDN`) | type="MSISDN" hardcoded in XSLT |
| reqSuccess dedup key | Subscriber RefId | |
| Fan-out | 1 event per subscriber (POU + COU) | No multi-SIM fan-out within subscriber |
| Fan-in | Standard "000" count == RequestCount | |
| PurgePendingRequestsBeforeResubmit | [COMMENTED OUT] | Dead code |
| Credential gate | `IsEnableUserPass='true'` → UserName/PassWord | |
| Audit gate (request) | `AllowWriteLog(OrderType)` | Conditional |
| Audit gate (response) | `AllowWriteLog(OrderType)` | Conditional |
| PreExecCheck source | `nextAct.PreExecCheck` via live Activity lookup | |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Subscriber data; OMXTrackingId; MSISDN |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | RequestCount++; Response[]; Status |
| `nextAct` | Concepts.OM.ProcessConfig.Activity | Live lookup — PreExecCheck |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "INTX_GET_MASTER_MINOR_SIM_INFO"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "INTX_GET_MASTER_MINOR_SIM_INFO"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 Execution Flow Diagram

1. **Setup:** isActResub; nextAct live lookup; isSkipped=true
2. [DEAD CODE] — PurgePendingRequestsBeforeResubmit commented out
3. **POU Subscribers loop** — for each ParentOU × Subscriber:
   - reqSuccess check (by RefId) → `continue`
   - PreExecCheck via `GetXMLForSubscriber`
   - Extract `currMSISDN = currSub.MSISDN`
   - Skip if `IsBlank(currMSISDN) OR currSub.MultiSIMInfo != null`
   - Send `reqEvent`; RequestCount++; AllowWriteLog audit; isSkipped=false
4. **COU Subscribers loop** — same pattern via `GetXMLForSubscriberInChildOU`
5. **Status:** if !isSkipped → `GetActivityStatusString("1")` + `SendDataToDB`; else → `SkipActivity("4")`
6. **Exception:** catch → `HandleActivityException`

---

## §6 Per-Subscriber Skip Guards

| Guard | Condition | Action |
|-------|-----------|--------|
| reqSuccess | `Response[].ReferenceId==refId AND CompletionStatus==2` | `continue` (outer if block) |
| PreExecCheck | XPath result != "true" | inner if block not entered |
| No MSISDN | `BRMS.IsBlank(currMSISDN)` | `continue` |
| Already has MultiSIMInfo | `currSub.MultiSIMInfo != null` | `continue` — idempotency guard |

> The `MultiSIMInfo != null` guard prevents re-querying INTX if a prior FM or prior invocation already populated the data — important for the resubmit case (since PurgePending is commented out).

---

## §7 System & Integration Dependencies

### §7.1 — ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Purpose |
|-----------|---------|-------------|---------|
| [OUTBOUND] | FM JMS | INTX_GET_MASTER_MINOR_SIM_INFO queue | Multi-SIM relationship query by MSISDN |
| [INBOUND] | FM JMS | INTX_GET_MASTER_MINOR_SIM_INFO response | GetMasterMinorSIMInfoRes |

### §7.2 — Backend API

| Field | Value |
|-------|-------|
| Backend | INTX (Multi-SIM resource management) |
| Operation | GetMasterMinorSIMInfo |
| Request root | `ns:GetMasterMinorSIMInfoReq` |
| Search type | `"MSISDN"` (hardcoded) |
| Search value | `$currMSISDN` (subscriber's MSISDN) |
| Search key | MSISDN (not ICCID — contrast with INTX_GET_SIM_INFO_BY_SIM) |

### §7.3 — BE Working Memory Dependencies

| Concept | Field | Access | Notes |
|---------|-------|--------|-------|
| Subscriber | `MSISDN` | READ | Search key |
| Subscriber | `MultiSIMInfo` | READ (skip check) + WRITTEN | Skip if not null; written on success |
| MultiSIMInfo | Master, Minor[] | WRITTEN | Created by response handler; all Source="PREV_MSIM" |
| Activity | RequestCount / Response[] / Status | READ+WRITTEN | Standard |

### §7.4 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Credential gate |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `OMX_OM/WritePayload` | Audit payload inclusion |

---

## §8 Detailed Payload Build

### §8.1 — XSLT Parameters

| Parameter | Bound From | Notes |
|-----------|-----------|-------|
| `$orderRequest` | orderRequest concept | |
| `$refId` | subscriber.RefId | RefID header |
| `$globalVariables` | Global variable tree | Credential gate |
| `$currMSISDN` | currSub.MSISDN | Search value in payload |

### §8.2 — XSLT Field Mapping Tree

```text
createEvent
└── event
    ├── @extId                    ← OMXUtils:generateTrackingID()
    ├── JMSPriority               ← $orderRequest/OrderPriority
    ├── JMSCorrelationID          ← $orderRequest/OrderData/OMXTrackingId
    ├── OrderID                   ← $orderRequest/OrderData/OrderID
    ├── RefID                     ← $refId
    ├── UserName                  ← $orderRequest/OrderData/User       [Credential-gated: IsEnableUserPass='true']
    ├── PassWord                  ← $orderRequest/OrderData/Password   [Credential-gated: IsEnableUserPass='true']
    ├── OrderType                 ← $orderRequest/OrderData/OrderType
    └── payload
        └── ns:GetMasterMinorSIMInfoReq
            └── ns:searchList
                └── ns:searchInfoArray
                    ├── ns:type   ← "MSISDN"                          [Always — hardcoded]
                    └── ns:value  ← $currMSISDN
```

### §8.3 — Generated XML Example

```xml
<event extId="TRK-001">
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-001</JMSCorrelationID>
  <OrderID>ORD-001</OrderID>
  <RefID>SUB-REF-001</RefID>
  <OrderType>3</OrderType>
  <payload>
    <ns:GetMasterMinorSIMInfoReq
      xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetMasterMinorSIMInfo.xsd">
      <ns:searchList>
        <ns:searchInfoArray>
          <ns:type>MSISDN</ns:type>
          <ns:value>0812345678</ns:value>
        </ns:searchInfoArray>
      </ns:searchList>
    </ns:GetMasterMinorSIMInfoReq>
  </payload>
</event>
```

---

## §9 Response — MultiSIMInfo Concept Construction

### §9.1 — Response Data Gate

```java
if(XPath.evalAsBoolean(
    "exists(xsd5:GetMasterMinorSIMInfoRes/.../xsd5:master)"
    + " and not(contains(.../xsd5:message, 'Data Not Found.'))")
{
    // proceed with write-back
}
```

### §9.2 — ResponseBase XSLT (unconditional field mapping)

```text
createObject (ResponseBase)
└── object
    ├── @extId           ← $extId (from BE)    [Always — no xsl:if]
    ├── ResponseCode     ← $eventResponse/ResponseCode    [Always — no xsl:if]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg     [Always — no xsl:if]
    ├── CompletionStatus ← $eventResponse/CompletionStatus [Always — no xsl:if]
    └── ReferenceId      ← $eventResponse/RefID           [Always — no xsl:if]
```

> Unlike most FMs, ResponseBase fields are mapped unconditionally (no `xsl:if` wrappers) — if INTX returns an empty field the ResponseBase field will be an empty string, not absent.

### §9.3 — MultiSIMInfo Concept Hierarchy

```text
createObject (Concepts.MultiSIM.MultiSIMInfo)
└── object
    ├── @extId                       ← OMXUtils:generateTrackingID()
    ├── Master
    │   ├── @extId                   ← OMXUtils:generateTrackingID()
    │   ├── SIM                      ← ns5:master/ns5:resourceInfo/ns5:ICCID            [xsl:if]
    │   ├── IMSI                     ← ns5:master/ns5:resourceInfo/ns5:IMSI             [xsl:if]
    │   ├── Alias                    ← ns5:master/ns5:resourceInfo/ns5:aliasName        [xsl:if]
    │   ├── RCOfferIn                ← ns5:master/ns5:rcOfferIn/ns5:name               [xsl:if]
    │   ├── RCOfferOut               ← ns5:master/ns5:rcOfferOut/ns5:name              [xsl:if]
    │   ├── SIMStatus                ← ns5:master/ns5:resourceInfo/ns5:simStatus/ns5:code [xsl:if]
    │   └── Source                   ← "PREV_MSIM"                                      [Always — hardcoded]
    ├── Minor[] [POU ONLY — eSIM source]
    │   Source: ns5:minorList/ns5:eSimResourceOfferInfoList/ns5:SIMAndOfferInfoArray
    │   Each Minor:
    │   ├── @extId                   ← OMXUtils:generateTrackingID()
    │   ├── SIM                      ← ns5:resourceInfo/ns5:ICCID                       [xsl:if]
    │   ├── IMSI                     ← ns5:resourceInfo/ns5:IMSI
    │   ├── Alias                    ← ns5:resourceInfo/ns5:aliasName
    │   ├── RCOfferIn                ← ns5:rcOfferIn/ns5:code   [NOTE: code, not name — contrast Master]
    │   ├── RCOfferOut               ← ns5:rcOfferOut/ns5:name
    │   ├── SIMStatus                ← ns5:resourceInfo/ns5:simStatus/ns5:code          [xsl:if]
    │   ├── Source                   ← "PREV_MSIM"                                      [Always]
    │   └── ResourceOffer            ← ns5:resourceOfferInfo/ns5:offer/ns5:name
    └── Minor[] [POU + COU — mutiSIM source]
        Source: ns5:minorList/ns5:mutiSimResourceOfferInfoList/ns5:SIMAndOfferInfoArray
        NOTE: "muti" is a typo in the INTX schema — must be reproduced exactly
        Each Minor: same fields as eSIM Minor above
```

### §9.4 — POU vs COU Minor Source Difference

| Minor source list | POU | COU |
|-------------------|-----|-----|
| `ns5:eSimResourceOfferInfoList` | [Included] | [Excluded] |
| `ns5:mutiSimResourceOfferInfoList` | [Included] | [Included] |

---

## §10 Audit Logging

| Phase | Gate | AUDIT_TRACE |
|-------|------|-------------|
| Request | `AllowWriteLog(OrderType)` [Conditional] | `"Request Sent for INTX_GET_MASTER_MINOR_SIM_INFO"` |
| Response | `AllowWriteLog(OrderType)` [Conditional] | `concat("Response received for RefId ", $eventResponse/RefID)` |

---

## §11 Activity Status Management

| Condition | Call | Code |
|-----------|------|------|
| At least one event sent | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" (RUNNING) |
| No subscribers qualify | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" (SKIPPED) |

---

## §12 Function Dependency Tree

```text
Request_INTX_GET_MASTER_MINOR_SIM_INFO (rule)
├── Instance.getByExtIdByUri(NextActivityName, Activity)  [nextAct]
├── [per POU × Subscriber]:
│   ├── Response[].ReferenceId==refId  [reqSuccess]
│   ├── GetXMLForSubscriber + XPath.execute(PreExecCheck)
│   ├── currSub.MSISDN  [currMSISDN]
│   ├── BRMS.IsBlank(currMSISDN) OR currSub.MultiSIMInfo != null  [skip]
│   ├── Event.createEvent(XSLT: $currMSISDN → ns:value in searchInfoArray)
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   ├── RequestCount++
│   └── AllowWriteLog → sendAudit(reqEvent)
├── [COU loop: mirrors POU with GetXMLForSubscriberInChildOU]
├── GetActivityStatusString("1") + SendDataToDB  [or SkipActivity("4")]
└── HandleActivityException  [catch]

Response_INTX_GET_MASTER_MINOR_SIM_INFO (rulefunction)
├── extId = OMXUtils.generateTrackingID()  [in BE, passed to XSLT]
├── Instance.createInstance("xslt://ResponseBase")
│   └── ResponseCode, ResponseMessage, CompletionStatus, ReferenceId (all unconditional)
├── currActivity.Response[length] = res
├── XPath.evalAsBoolean → exists(xsd5:master) AND !contains(message, "Data Not Found.")
├── if data present: [per POU/COU Subscriber where res.ReferenceId == currRefId]
│   ├── if subscriber.MultiSIMInfo == null:
│   │   ├── Instance.createInstance("xslt://MultiSIMInfo")
│   │   │   ├── Master: SIM/IMSI/Alias/RCOfferIn/RCOfferOut/SIMStatus (conditional) + Source="PREV_MSIM"
│   │   │   ├── [POU only] Minor[] from eSimResourceOfferInfoList (xsl:for-each)
│   │   │   └── Minor[] from mutiSimResourceOfferInfoList (xsl:for-each)
│   │   ├── subscriber.MultiSIMInfo = multiSimInfo
│   │   └── System.debugOut("set master from INT_GET_MASTER_MINOR_SIM_INFO[2]")
├── AllowWriteLog → sendAudit(eventResponse)
└── XPath.evalAsInt("count(Response[tib:right(tib:trim(ResponseCode),3)='000'])") → fan-in
```

---

## §13 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Skip subscriber if `BRMS.IsBlank(MSISDN)` OR `currSub.MultiSIMInfo != null`. |
| R2 | 1 event per subscriber; search by MSISDN (type="MSISDN", hardcoded). |
| R3 | Credential gate on `IsEnableUserPass='true'`. |
| R4 | Audit gated by `AllowWriteLog(OrderType)`; response audit includes RefId in trace. |
| R5 | Response: only create `MultiSIMInfo` if `exists(master)` AND message does NOT contain "Data Not Found." |
| R6 | ResponseBase fields mapped unconditionally (no xsl:if wrappers). |
| R7 | POU `MultiSIMInfo` includes both `eSimResourceOfferInfoList` and `mutiSimResourceOfferInfoList` Minor sources; COU includes only `mutiSimResourceOfferInfoList`. |
| R8 | All Source fields hardcoded to `"PREV_MSIM"` on Master and Minor. |
| R9 | Fan-in: standard "000" count == RequestCount. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Schema path typo: `mutiSimResourceOfferInfoList` ("muti") — must be reproduced exactly | [MEDIUM] | Document the typo; lock to this exact string in migration; do NOT correct it unless INTX schema is fixed simultaneously |
| POU vs COU Minor source asymmetry — COU misses eSIM minors | [MEDIUM] | Verify with INTX team whether eSIM minors can exist on COU subscribers; if yes, add eSIM list to COU handler |
| `System.debugOut` calls not commented out — logs to TIBCO BE console on every response | [LOW] | Remove or gate these in migration |
| `PurgePendingRequestsBeforeResubmit` commented out — resubmit relies solely on `MultiSIMInfo != null` guard | [LOW] | Verify resubmit scenario is correctly handled by the null guard alone |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
