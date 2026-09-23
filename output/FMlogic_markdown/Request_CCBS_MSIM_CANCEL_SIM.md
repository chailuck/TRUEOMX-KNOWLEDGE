# Request_CCBS_MSIM_CANCEL_SIM

**Backend:** CCBS — Multi-SIM (MSim) CancelSIM  
**Priority:** 5 | **ForwardChain:** true | **Dispatch:** sendEventImmediate  
**Fan-out:** Per-subscriber (POU + COU) | **Fan-in:** Response count == RequestCount  
**Author:** sakarin-radchapunya

---

## §1 — Overview & Purpose

This rule fires when `CCBS_MSIM_CANCEL_SIM` becomes the next activity. It sends one **MSim CancelSIM** request to CCBS per subscriber (POU and COU) that has qualifying SubscriberOffers. All qualifying SOC codes for a subscriber are aggregated into a single request — making the fan-out granularity **per-subscriber**, not per-offer.

The SIM list in each request is resolved through a 3-way priority:
1. `MSIM_TO_CANCEL` ExtendedInfo overrides all
2. Subscriber's `MultiSIMInfo.Minor[].SIM` array
3. Related SIM from offer `ParameterInfo` (prepared but effectively unused due to §6 SIM resolution dead code)

> **Fan-in uses Response count == RequestCount** (not ResponseCode suffix "000"). The response concept is the specialised `Concepts.FM.Response.CCBS_MsimCancelSimRes`, not the generic ResponseBase.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_MSIM_CANCEL_SIM` |
| Author | sakarin-radchapunya |
| Priority | 5 |
| ForwardChain | true |
| Target backend | CCBS — Multi-SIM (MSim) service |
| Operation | CancelSIM |
| Payload schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/MSim.xsd` |
| Request event type | `Events.OMConsumers.OMXFM.Request.CCBS_MSIM_CANCEL_SIM` |
| Response event type | `Events.OMConsumers.OMXFM.Response.CCBS_MSIM_CANCEL_SIM` |
| Response concept | `Concepts.FM.Response.CCBS_MsimCancelSimRes` (specialised, not ResponseBase) |
| Dispatch method | `Event.Ext.sendEventImmediate` |
| Fan-out granularity | Per subscriber (one request per subscriber, all qualifying offers aggregated) |
| Fan-in mechanism | `currActivity.RequestCount == currActivity.Response@length` |
| Audit log gate | `RuleFunctions.Helpers.AllowWriteLog(orderType)` — conditional |
| Skip trigger | No qualifying offers for any subscriber → SkipActivity("4") |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order concept; source of subscriber, SIM, and offer data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step; PreExecCheck, Status, RequestCount, Response[] |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to current order's next step |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_MSIM_CANCEL_SIM"` | Rule fires only for this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_MSIM_CANCEL_SIM"` | Double-check on ProcessFlow routing |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be waiting before dispatch |

---

## §5 — Execution Flow

```
1.  Debug log: "[OMXTrackingId] Executing Request_CCBS_MSIM_CANCEL_SIM"
2.  Compute isActResub
3.  Resolve nextAct by extId; read PreExecCheck XPath
4.  POU loop: iterate ParentOU[i].Subscriber[j]
5.  For each subscriber: find main SIM from ResourceInfo[ResourceName="SIM"]
6.  Read MSIM_TO_CANCEL ExtendedInfo value (XPath; empty string if absent)
7.  Initialize alSOCs (ArrayList) and alSIMs (ArrayList)
8.  For each SubscriberOffer: read FE_OR_CCBS filter; evaluate PreExecCheck (per-offer)
9.  If chkRes=="true": check resubmission skip (Response[ReferenceId=refId and CompletionStatus==2])
10. If not already succeeded: collect "Related SIM,Soc" into alSIMs; collect "Soc,OfferInstanceId" into alSOCs
11. Convert alSOCs → socArray[]; resolve simsArray[] (see SIM resolution logic)
12. If offersArray.length > 0: build and send CCBS_MSIM_CANCEL_SIM event via sendEventImmediate
13. If AllowWriteLog: send audit log
14. If !isActResub: increment RequestCount
15. COU loop: identical logic over ChildOU[k].Subscriber[j] (using COU PreExecCheck XML helper)
16. If any request sent: Status = "1", SendDataToDB; else SkipActivity("4")
17. Debug log: "[OMXTrackingId] Completed Request_CCBS_MSIM_CANCEL_SIM"
18. On exception: HandleActivityException
```

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### Per-offer PreExecCheck + resubmission skip

PreExecCheck is evaluated per offer (not per activity), using `GetXMLForSubscriberOfferFilterWithExtendedInfo` (POU) or `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo` (COU). The resubmission skip checks whether a successful response (`CompletionStatus==2`) with a matching RefId already exists in `Response[]` — if so, that offer is excluded from the new request.

### SOC aggregation (per subscriber)

All qualifying offer SOCs for one subscriber are collected into `alSOCs` as `"Soc,OfferInstanceId"` strings. This list is then pipe-joined to form `ns:socRCOut`: `"SOC1,OII1|SOC2,OII2"`. This means **one CCBS request per subscriber**, regardless of how many qualifying offers exist.

### SIM resolution (3-way priority)

| Priority | Condition | SIM Source | ns:sim format |
|----------|-----------|------------|---------------|
| 1 (highest) | `exists($subscriber/ExtendedInfo[Name="MSIM_TO_CANCEL"])` | ExtendedInfo[MSIM_TO_CANCEL]/Value | Single SIM value |
| 2 | MSIM_TO_CANCEL absent + MultiSIMInfo present + msimToCancel empty | MultiSIMInfo.Minor[].SIM | Pipe-joined: "SIM1\|SIM2" |
| 3 | msimToCancel non-empty + MultiSIMInfo present | ParameterInfo[ParamName="Related SIM"]/ValuesArray + Soc | Used as simsArray — but XSLT prefers priority 1 |

> **Note on Priority 3:** When `msimToCancel` is non-empty, `simsArray` is built from "Related SIM" ParameterInfo. However, since `msimToCancel` being non-empty implies `MSIM_TO_CANCEL` ExtendedInfo exists, the XSLT's `xsl:when` for MSIM_TO_CANCEL fires — so the "Related SIM" simsArray is prepared but never used for `ns:sim`. This is effectively dead code. **[MEDIUM]**

### Master SIM

`ns:MultiSIMInfo/ns:Master/ns:Sim`: uses `MultiSIMInfo/Master/SIM` if present; falls back to `mainSim` (from `ResourceInfo[ResourceName="SIM"]`).

### Audit log gate

`RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)` — the audit log is only emitted for certain order types. This differs from other FMs that always log.

### Status transitions

| Scenario | Action | Status |
|----------|--------|--------|
| At least one request dispatched | Status="1", SendDataToDB | Running |
| No qualifying offers for any subscriber | SkipActivity("4") | Skip |
| Exception | HandleActivityException | Error |

---

## §7 — Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| mainSim | `subscriber.ResourceInfo[ResourceName="SIM"].ValuesArray` | Fallback master SIM if MultiSIMInfo.Master.SIM absent |
| msimToCancel | `subscriber.ExtendedInfo[Name="MSIM_TO_CANCEL"]/Value` | XPath conditional; empty string if absent |
| alSOCs entry | `subOff.Soc + "," + subOff.OfferInstanceId` | Pipe-joined as ns:socRCOut |
| alSIMs entry | `ParameterInfo[ParamName="Related SIM"].ValuesArray + "," + subOff.Soc` | Built when Related SIM found; pipe-joined as simsArray (only when MSIM_TO_CANCEL absent) |
| FE_OR_CCBS filter | `$subOff/ExtendedInfo[Name="FE_OR_CCBS"]/Value` | Passed to PreExecCheck XML builder |
| Resubmission skip | `Response[ReferenceId==refId and CompletionStatus==2]` | Excludes already-successful offers from new request |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

The `AllowWriteLog(orderType)` helper controls audit logging. No other order-type-specific branching in the request dispatch logic itself.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Dispatch | Backend |
|-----------|------------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_MSIM_CANCEL_SIM` | `Event.Ext.sendEventImmediate` | CCBS — Multi-SIM CancelSIM |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `Event.Ext.sendEventImmediate` | Audit log sink (gated by AllowWriteLog) |

### §8.3 — Backend API Details

| System | Operation | Schema NS | Key Fields Sent |
|--------|-----------|-----------|-----------------|
| CCBS | MSim CancelSIM | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/MSim.xsd` | subscriberId, sim (pipe-joined SIMs), socRCOut (pipe-joined SOC,OII pairs), MultiSIMInfo.Master.Sim, activityInfo (ActivityReason, L3ActivityDate, UserText) |

### §8.4 — BE Working Memory Dependencies

| Concept Field | Access | Purpose |
|--------------|--------|---------|
| `Subscriber.ResourceInfo[Name="SIM"].ValuesArray` | READ | Main SIM (master fallback) |
| `Subscriber.ExtendedInfo[Name="MSIM_TO_CANCEL"]/Value` | READ | Specific SIM to cancel; overrides MultiSIMInfo |
| `Subscriber.MultiSIMInfo.Minor[].SIM` | READ | Default minor SIM list when MSIM_TO_CANCEL absent |
| `Subscriber.MultiSIMInfo.Master.SIM` | READ | Master SIM for MultiSIMInfo block |
| `Subscriber.SubscriberId` | READ | ns:subscriberId in request |
| `Subscriber.SubscriberActivityInfo.ActivityReason` | READ | ns:ActivityReason (default "CREQ") |
| `Subscriber.SubscriberActivityInfo.UserText` | READ | ns:UserText (conditional) |
| `SubscriberOffers.Soc` | READ | Matched in alSOCs |
| `SubscriberOffers.OfferInstanceId` | READ | Paired with Soc in alSOCs |
| `SubscriberOffers.ParameterInfo[ParamName="Related SIM"].ValuesArray` | READ | Related SIM SIM number |
| `orderRequest.OrderData.EffectiveDate` | READ | ns:L3ActivityDate |
| `orderRequest.OrderData.User / Password` | READ | Conditional on IsEnableUserPass="true" |
| `orderRequest.OrderData.CES` | READ | ns:CES in event header |
| `orderCurrentActivity.Response[]` | READ | Resubmission skip check |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-in counter |
| `orderCurrentActivity.Status` | WRITE | Set to "1" after dispatch |

### §8.5 — ExtendedInfo Fields Required

| Name | Level | Required/Optional | Where Used |
|------|-------|-------------------|------------|
| MSIM_TO_CANCEL | Subscriber | Optional | Priority-1 SIM source for ns:sim; drives simsArray path selection |
| FE_OR_CCBS | Offer | Optional | PreExecCheck filter parameter |

### §8.6 — Global Variable Dependencies

| Path | Usage |
|------|-------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Gates UserName/PassWord inclusion in event header |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Guards payload in audit log |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Purpose |
|------------|------------|---------|
| `$orderRequest` | orderRequest concept | Order metadata, credentials, dates |
| `$globalVariables` | global variables | IsEnableUserPass, WritePayload flags |
| `$subscriber` | current subscriber concept | SubscriberId, MultiSIMInfo, SubscriberActivityInfo |
| `$simsArray` | resolved simsArray[] (Java String[]) | Minor SIM list or Related SIM list (priority-2/3) |
| `$socArray` | socArray[] (Java String[]) | Pipe-joined SOC,OfferInstanceId pairs |
| `$mainSim` | ResourceInfo[SIM].ValuesArray | Master SIM fallback |

### §9.2 — Event Container Construction

No custom extId on the request event container (extId is generated server-side by CCBS, not via OMXUtils).

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | If present |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | If present |
| OrderID | `$orderRequest/OrderData/OrderID` | If present |
| UserName | `$orderRequest/OrderData/User` | If IsEnableUserPass="true" |
| PassWord | `$orderRequest/OrderData/Password` | If IsEnableUserPass="true" |
| OrderType | `$orderRequest/OrderData/OrderType` | If present |
| CES | `$orderRequest/OrderData/CES` | If present |

### §9.4 — Payload Root Element

Root: `ns:mSimData` → `ns:OUList` containing `ns:Subscriber`, `ns:MultiSIMInfo`, `ns:activityInfo`.

### §9.5 — Conditional Fields

| Field | Condition | Value |
|-------|-----------|-------|
| ns:subscriberId | subscriber/SubscriberId present | SubscriberId value |
| ns:sim (priority-1) | ExtendedInfo[MSIM_TO_CANCEL] exists | MSIM_TO_CANCEL/Value |
| ns:sim (priority-2) | MSIM_TO_CANCEL absent AND simsArray has elements | pipe-joined simsArray elements: "SIM1\|SIM2" |
| ns:socRCOut | socArray has elements | pipe-joined: "SOC1,OII1\|SOC2,OII2" |
| ns:Master/ns:Sim | MultiSIMInfo/Master/SIM exists → use it; else use mainSim | Always emitted |
| ns:ActivityReason | SubscriberActivityInfo/ActivityReason string-length > 0 → use it; else "CREQ" | Always emitted |
| ns:L3ActivityDate | orderRequest/OrderData/EffectiveDate present | EffectiveDate value |
| ns:UserText | SubscriberActivityInfo/UserText present | UserText value |

### §9.6 — socRCOut Format

Each entry in `alSOCs` is `"Soc,OfferInstanceId"`. The pipe-joined result sent to CCBS: `"SOC_BAR1,OII-001|SOC_BAR2,OII-002"`. CCBS parses the comma as the SOC/OfferInstanceId delimiter and the pipe as the entry delimiter.

### §9.7 — Complete Generated XML Example

```xml
<!-- CCBS_MSIM_CANCEL_SIM payload — one per subscriber -->
<ns:mSimData>
  <ns:OUList>
    <ns:Subscriber>
      <ns:subscriberId>SUB-0001</ns:subscriberId>
      <ns:sim>8966041000000001234</ns:sim>       <!-- MSIM_TO_CANCEL or piped SIMs -->
      <ns:socRCOut>SOC_BAR1,OII-001|SOC_BAR2,OII-002</ns:socRCOut>
    </ns:Subscriber>
    <ns:MultiSIMInfo>
      <ns:Master>
        <ns:Sim>8966041000000000001</ns:Sim>   <!-- MultiSIMInfo.Master.SIM or mainSim -->
      </ns:Master>
    </ns:MultiSIMInfo>
    <ns:activityInfo>
      <ns:ActivityReason>CREQ</ns:ActivityReason>  <!-- default if SubscriberActivityInfo absent -->
      <ns:L3ActivityDate>2026-08-13</ns:L3ActivityDate>
    </ns:activityInfo>
  </ns:OUList>
</ns:mSimData>
```

### §9.8 — XSLT Stylesheet Source

```xml
<!-- Request XSLT — CCBS_MSIM_CANCEL_SIM event; one per subscriber -->
<xsl:stylesheet
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/MSim.xsd"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
  version="1.0">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>
  <xsl:param name="globalVariables"/>
  <xsl:param name="subscriber"/>  <!-- current subscriber concept -->
  <xsl:param name="simsArray"/>   <!-- resolved minor SIM array -->
  <xsl:param name="socArray"/>    <!-- "SOC,OfferInstanceId" array -->
  <xsl:param name="mainSim"/>     <!-- from ResourceInfo[SIM].ValuesArray -->
  <xsl:template match="/">
    <createEvent><event>
      <xsl:if test="$orderRequest/OrderPriority">
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      </xsl:if>
      <!-- JMSCorrelationID, OrderID, OrderType, CES similarly conditional -->
      <xsl:if test="$globalVariables/.../IsEnableUserPass='true'">
        <!-- UserName, PassWord -->
      </xsl:if>
      <payload><ns:mSimData><ns:OUList>
        <ns:Subscriber>
          <xsl:if test="$subscriber/SubscriberId">
            <ns:subscriberId><xsl:value-of select="$subscriber/SubscriberId"/></ns:subscriberId>
          </xsl:if>
          <xsl:choose>
            <xsl:when test="exists($subscriber/ExtendedInfo[Name='MSIM_TO_CANCEL'])">
              <ns:sim><xsl:value-of select="$subscriber/ExtendedInfo[Name='MSIM_TO_CANCEL']/Value"/></ns:sim>
            </xsl:when>
            <xsl:otherwise>
              <xsl:if test="count($simsArray/elements) > 0">
                <ns:sim><xsl:value-of select="tib:concat-sequence-format($simsArray/elements, '|')"/></ns:sim>
              </xsl:if>
            </xsl:otherwise>
          </xsl:choose>
          <xsl:if test="count($socArray/elements) > 0">
            <ns:socRCOut><xsl:value-of select="tib:concat-sequence-format($socArray/elements, '|')"/></ns:socRCOut>
          </xsl:if>
        </ns:Subscriber>
        <ns:MultiSIMInfo><ns:Master>
          <xsl:choose>
            <xsl:when test="exists($subscriber/MultiSIMInfo/Master/SIM)">
              <ns:Sim><xsl:value-of select="$subscriber/MultiSIMInfo/Master/SIM"/></ns:Sim>
            </xsl:when>
            <xsl:otherwise><ns:Sim><xsl:value-of select="$mainSim"/></ns:Sim></xsl:otherwise>
          </xsl:choose>
        </ns:Master></ns:MultiSIMInfo>
        <ns:activityInfo>
          <xsl:choose>
            <xsl:when test="string-length($subscriber/SubscriberActivityInfo/ActivityReason) > 0">
              <ns:ActivityReason><xsl:value-of select="$subscriber/SubscriberActivityInfo/ActivityReason"/></ns:ActivityReason>
            </xsl:when>
            <xsl:otherwise><ns:ActivityReason>CREQ</ns:ActivityReason></xsl:otherwise>
          </xsl:choose>
          <!-- L3ActivityDate, UserText conditional -->
        </ns:activityInfo>
      </ns:OUList></ns:mSimData></payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority         ← $orderRequest/OrderPriority                       [Conditional: if present]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId              [Conditional: if present]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                    [Conditional: if present]
    ├── UserName            ← $orderRequest/OrderData/User                       [Conditional: IsEnableUserPass="true" AND present]
    ├── PassWord            ← $orderRequest/OrderData/Password                   [Conditional: IsEnableUserPass="true" AND present]
    ├── OrderType           ← $orderRequest/OrderData/OrderType                  [Conditional: if present]
    ├── CES                 ← $orderRequest/OrderData/CES                        [Conditional: if present]
    └── payload
        └── ns:mSimData
            └── ns:OUList
                ├── ns:Subscriber
                │   ├── ns:subscriberId  ← $subscriber/SubscriberId             [Conditional: if present]
                │   ├── ns:sim           ← MSIM_TO_CANCEL/Value (priority-1)    [Conditional: ExtendedInfo[MSIM_TO_CANCEL] exists]
                │   │                    OR tib:concat-sequence-format(simsArray,'|')
                │   │                                                            [Conditional: MSIM_TO_CANCEL absent AND simsArray non-empty]
                │   └── ns:socRCOut      ← tib:concat-sequence-format(socArray,'|')
                │                                                                [Conditional: socArray non-empty]
                ├── ns:MultiSIMInfo
                │   └── ns:Master
                │       └── ns:Sim       ← MultiSIMInfo/Master/SIM (if exists)  [Always: falls back to $mainSim]
                └── ns:activityInfo
                    ├── ns:ActivityReason ← SubscriberActivityInfo/ActivityReason [Always: defaults to "CREQ"]
                    ├── ns:L3ActivityDate ← $orderRequest/OrderData/EffectiveDate [Conditional: if present]
                    └── ns:UserText       ← SubscriberActivityInfo/UserText       [Conditional: if present]
```

**Legend:** `[Always]` = unconditional | `[Conditional: <condition>]` = emitted only when condition true

---

## §11 — Audit Logging

> **Audit log is gated:** `RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)` — only emits audit log for certain order types. Other FMs always log.

| Phase | Field | Value |
|-------|-------|-------|
| Request | ESBUUID | `$orderRequest/OrderData/OMXTrackingId` |
| Request | PROCESS_ID | `concat($pid, "_REQ")` |
| Request | OPERATION_NAME | "CCBS_MSIM_CANCEL_SIM" |
| Request | AUDIT_TRACE | `concat("Request Sent for RefId: ", $refId)` |
| Request | payload | Conditional: WritePayload="true" |
| Response | PROCESS_ID | `concat($pid, "_RES")` |
| Response | AUDIT_TRACE | "Response received for CCBS_MSIM_CANCEL_SIM" |

---

## §12 — Activity Status Management

| Transition | Code | Trigger |
|------------|------|---------|
| Running | "1" | At least one subscriber request dispatched |
| Skip | "4" | No qualifying offers for any subscriber |
| Error | HandleActivityException | Any uncaught exception |

---

## §13 — Exception / Error Handling

Entire `then` block wrapped in `try { ... } catch (Exception ae) { HandleActivityException(...); }`. Debug messages emitted at entry and exit via `System.debugOut`.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, soc, filter)` | POU per-offer PreExecCheck XML builder |
| `RuleFunctions.Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, refId, soc, pouRefId, filter)` | COU per-offer PreExecCheck XML builder |
| `RuleFunctions.Helpers.AllowWriteLog(orderType)` | Returns boolean — whether audit log should be emitted for this order type |
| `RuleFunctions.Helpers.GetActivityStatusString("1", false)` | Returns status string for "Running" |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | Persists state to DB |
| `RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")` | Skip handler |
| `RuleFunctions.Helpers.HandleActivityException(...)` | Central exception handler |
| `Collections.List.createArrayList()` | Creates Java ArrayList for SOC/SIM collection |
| `Collections.add(list, item)` | Adds entry to ArrayList |
| `Collections.toArray(list)` | Converts ArrayList to Object[] |
| `tib:concat-sequence-format(elements, '|')` | TIBCO custom XSLT function — pipe-joins array elements |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_MSIM_CANCEL_SIM.rule
├── [POU loop: ParentOU[i].Subscriber[j]]
│   ├── ResourceInfo scan (ResourceName="SIM") → mainSim
│   ├── XPath.evalAsString(MSIM_TO_CANCEL) → msimToCancel
│   ├── Collections.List.createArrayList() × 2 (alSOCs, alSIMs)
│   ├── [Offer loop]
│   │   ├── XPath.evalAsString(FE_OR_CCBS filter)
│   │   ├── RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(...)
│   │   ├── XPath.execute(chkXPath, sXML)
│   │   ├── Response[] resubmission skip check
│   │   ├── Collections.add(alSIMs, "relatedSim,Soc")    [if Related SIM found]
│   │   └── Collections.add(alSOCs, "Soc,OfferInstanceId")
│   ├── Collections.toArray(alSOCs / alSIMs)
│   ├── simsArray resolution (MultiSIMInfo.Minor[] or simsArrayObj)
│   ├── Event.createEvent(XSLT → CCBS_MSIM_CANCEL_SIM)   [if offersArray > 0]
│   │   └── tib:concat-sequence-format(simsArray, '|')
│   │   └── tib:concat-sequence-format(socArray, '|')
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   ├── RuleFunctions.Helpers.AllowWriteLog(orderType)   [audit gate]
│   ├── Event.createEvent(XSLT → Logger)                 [if AllowWriteLog]
│   ├── Event.Ext.sendEventImmediate(logEvent)
│   └── orderCurrentActivity.RequestCount++              [if !isActResub]
├── [COU loop: ChildOU[k].Subscriber[j]] — identical; uses COU XML helper
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)
└── RuleFunctions.Helpers.HandleActivityException(...)
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Properties Used |
|---------|---------------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.Customer.ParentOU[], ChildOU[], OrderData.OrderID, OMXTrackingId, OrderType, EffectiveDate, User, Password, CES |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, SubscriberId, ResourceInfo[], ExtendedInfo[MSIM_TO_CANCEL], MultiSIMInfo, SubscriberActivityInfo, SubscriberOffers[] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Soc, OfferInstanceId, ParameterInfo[Related SIM], ExtendedInfo[FE_OR_CCBS] |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck |
| `Concepts.FM.Response.CCBS_MsimCancelSimRes` | Specialised response concept (ResponseCode, ResponseMessage, CompletionStatus, ReferenceId) |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Aggregate all qualifying SOC offers for a subscriber into one CCBS MSim CancelSIM request (one request per subscriber) |
| R2 | Resolve SIM list by priority: MSIM_TO_CANCEL ExtendedInfo → MultiSIMInfo.Minor[] → Related SIM ParameterInfo |
| R3 | Encode socRCOut as pipe-delimited "SOC,OfferInstanceId" pairs |
| R4 | Include Master SIM from MultiSIMInfo (or mainSim fallback from ResourceInfo[SIM]) |
| R5 | Evaluate PreExecCheck per offer; skip already-successful offers on resubmission (CompletionStatus==2 + RefId match) |
| R6 | Operate on POU and COU subscribers symmetrically |
| R7 | Gate audit logging by AllowWriteLog(orderType) — not all order types are logged |
| R8 | Fan-in: Response count == RequestCount (not ResponseCode check) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| "Related SIM" simsArray path prepared but never used for ns:sim when MSIM_TO_CANCEL exists — dead code in simsArray resolution | [MEDIUM] | Clarify with business team when Related SIM path should apply; simplify SIM resolution logic in migration |
| `tib:concat-sequence-format` is TIBCO custom XSLT function — not portable | [HIGH] | Replace with standard XPath 2.0 `string-join()` or equivalent in target platform |
| Fan-in by Response count (not ResponseCode) — a failed response (non-000 code) would still satisfy fan-in, potentially advancing with errors | [MEDIUM] | Verify with business whether all CCBS MSim responses should be treated as "done" regardless of ResponseCode |
| IsEnableUserPass global flag gates credential injection — if misconfigured, credentials silently absent | [LOW] | Validate flag configuration in target environment |
| AllowWriteLog gate may suppress audit trail for certain order types — risk for compliance or debugging | [LOW] | Document which order types suppress logging; ensure target platform has equivalent visibility mechanism |

---

## §18 — Full Source Code (Request Rule)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_MSIM_CANCEL_SIM {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CCBS_MSIM_CANCEL_SIM";
    orderRequest.ProcessFlow.NextActivityID == "CCBS_MSIM_CANCEL_SIM";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    System.debugOut("[" + orderRequest.OrderData.OMXTrackingId + "] Executing Request_CCBS_MSIM_CANCEL_SIM");
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      boolean isSkipped = true;
      Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
      String chkXPath = nextAct.PreExecCheck;
      /* POU loop: ParentOU[i].Subscriber[j] */
      for (int i = 0; i < pOuLen; i++) {
        for (int j = 0; j < pSubLen; j++) {
          /* find mainSim from ResourceInfo[ResourceName="SIM"] */
          /* read msimToCancel from ExtendedInfo[MSIM_TO_CANCEL] */
          Object alSOCs = Collections.List.createArrayList();
          Object alSIMs = Collections.List.createArrayList();
          for (int l = 0; l < offersLen; l++) {
            /* read FE_OR_CCBS filter; eval PreExecCheck per-offer */
            if(String.equals(chkRes, "true")) {
              /* resubmission skip check: Response[RefId==refId and CompletionStatus==2] */
              if (!reqSuccess) {
                /* collect Related SIM → alSIMs; collect Soc,OII → alSOCs */
              }
            }
          }
          /* resolve simsArray (MultiSIMInfo.Minor or simsArrayObj) */
          if (offersArray@length > 0) {
            Events.OMConsumers.OMXFM.Request.CCBS_MSIM_CANCEL_SIM reqEvent =
              Event.createEvent(/* XSLT → mSimData — see §9.8 */);
            Event.Ext.sendEventImmediate(reqEvent);
            if (RuleFunctions.Helpers.AllowWriteLog(orderType)) {
              Event.Ext.sendEventImmediate(Event.createEvent(/* Logger XSLT — see §11 */));
            }
            if (!isActResub) { orderCurrentActivity.RequestCount++; }
            isSkipped = false;
          }
        }
        /* COU loop: ChildOU[k].Subscriber[j] — identical logic */
      }
      if (!isSkipped) {
        orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
        RuleFunctions.Helpers.SendDataToDB(orderRequest);
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

## §19 — Response Message Rule

### §19.1 — Overview

The response handler (`Response_CCBS_MSIM_CANCEL_SIM`) receives one `CCBS_MSIM_CANCEL_SIM` response event per dispatched subscriber request. It creates a `CCBS_MsimCancelSimRes` concept (not the generic ResponseBase), appends it to `currActivity.Response[]`, sends a response audit log, and returns "true" when all requests have responded (fan-in by count, not ResponseCode).

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order for audit log |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_MSIM_CANCEL_SIM` | CCBS response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; fan-in count checked |

### §19.3 — ResponseBase Concept Construction

Response type: `Concepts.FM.Response.CCBS_MsimCancelSimRes` (specialised, not generic ResponseBase).

extId is generated via **direct Java call**: `String extId = OMXUtils.generateTrackingID();` — then passed as XSLT parameter `$extId`.

```text
createObject
└── object @extId ← OMXUtils.generateTrackingID() (Java direct call)    [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode                  [Conditional: if present]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg                   [Conditional: if present]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus              [Conditional: if present]
    └── ReferenceId       ← $eventResponse/RefID                        [Conditional: if present]
```

### §19.4 — Response Completion Logic (Fan-in)

| Expression | Value |
|------------|-------|
| Fan-in condition | `currActivity.RequestCount == currActivity.Response@length` |
| Returns "true" | All dispatched requests have received any response — process flow advances |
| Returns "false" | Still waiting for remaining responses |

> **No ResponseCode check** — any response (including failures) satisfies the fan-in. This differs from most other FMs which require ResponseCode suffix "000". This means the process may advance even if CCBS returned an error.

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | "CCBS_MSIM_CANCEL_SIM" |
| AUDIT_TRACE | "Response received for CCBS_MSIM_CANCEL_SIM" |
| payload | Conditional: WritePayload="true" → copy of $eventResponse |

**Note:** Response audit log is always emitted (not gated by AllowWriteLog — unlike the request side).

### §19.6 — Response XSLT Source

```xml
<!-- ResponseBase XSLT — Response_CCBS_MSIM_CANCEL_SIM -->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:param name="extId"/>           <!-- from Java: OMXUtils.generateTrackingID() -->
  <xsl:param name="eventResponse"/>  <!-- CCBS_MSIM_CANCEL_SIM response event -->
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
