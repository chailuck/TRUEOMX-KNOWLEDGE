# Request_ASRM_INVOKE_MINOR_SIM

> TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation  
> ASRM Unified Resource Activity — Minor/Secondary SIM Operations (Multi-SIM Cancellation, RIO Old-EID, SubscriberOffer-based)

**Priority:** 5 | **forwardChain:** true | **Backend:** ASRM | **Author:** SathidP-PC | **Generated:** 2026-07-23

---

## §1 — Overview & Purpose

This rule fires when the order orchestration engine reaches an activity with `ActivityID = ASRM_INVOKE_MINOR_SIM` and status `WAITING`. Unlike `ASRM_INVOKE_SIM` (which targets the primary SIM), this rule handles **secondary and additional SIM card operations** via three mutually exclusive dispatch paths chosen per subscriber.

> **Three subscriber dispatch paths — evaluated in priority order:**
> 1. **Path A — Multi-SIM (MSIM_TO_CANCEL):** If `ExtendedInfo[Name="MSIM_TO_CANCEL"]` exists → loop over pipe-delimited SIM ICC IDs, send one request **per SIM**.
> 2. **Path B — RIO / Old EID:** Else if `ResourceInfo[ResourceName="OLD_EID"]` exists → single request from `ResourceInfo["OLD_SIM"]`.
> 3. **Path C — SubscriberOffers:** Else → iterate `SubscriberOffers[]`, dispatch one request per qualifying offer with `ParameterInfo["Related SIM"]`.

> ⚠ **MSRES special skip:** For any subscriber with `SubscriberActivityInfo/ActivityReason='MSRES'`, if ACTIVITY is **RESERVE**, the subscriber is auto-skipped (no request sent).

> ⚠ **Per-SIM paired MSISDN key:** Resource Type is determined by `ResourceInfo[ResourceName=concat("SIM_PAIR_MSISDN_", $simValue)]` — a dynamic key per SIM value. This differs from ASRM_INVOKE_SIM which uses the fixed key `SIM_PAIR_MSISDN`.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_ASRM_INVOKE_MINOR_SIM` |
| Full Path | `Rules.OMConsumers.OMXFM.Request.Request_ASRM_INVOKE_MINOR_SIM` |
| Priority | 5 |
| forwardChain | true |
| Rule Type | Request Dispatch — three-path secondary SIM dispatch to ASRM FM |
| Author | SathidP-PC |
| Backend System | ASRM (Amdocs Resource Manager) |
| Operation | UnifiedResourceActivity (secondary/minor SIM card) |

---

## §3 — Working Memory — Declared Objects

| Variable | Type Path | Role |
|----------|-----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Master order — customer hierarchy, subscriber data, SubscriberOffers |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current step — ACTIVITY parameter, Response[], RequestCount, PreExecCheck |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity to order execution point |
| 2 | `orderCurrentActivity.ActivityID == "ASRM_INVOKE_MINOR_SIM"` | Targets only minor SIM activities |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "ASRM_INVOKE_MINOR_SIM"` | Order-level double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires on fresh/ready activity |

---

## §5 — Execution Flow Diagram

1. **Parameter Parsing** — iterate `Parameter[]` with `tib:tokenize(param,"=")` → extract `ACTIVITY` value (RESERVE / PREACTIVATE / ACTIVATE)
2. **ParentOU Subscriber Loop** — for each `ParentOU[i] → Subscriber[j]`:
   - If already has SUCCESS response → skip
   - If `ActivityReason='MSRES'` AND `activityValue='RESERVE'` → skip (reqSuccess=true)
   - → select dispatch path below
3. **PATH A — Multi-SIM (MSIM_TO_CANCEL)** [condition: `exists(ExtendedInfo["MSIM_TO_CANCEL"])`]:
   - Run PreExecCheck via `GetXMLForSubscriber` + `XPath.execute`
   - Read `simValues = ExtendedInfo["MSIM_TO_CANCEL"]/Value`
   - Split by `"|"` → simValueArray[] → for each: split by `","` → take `[0]` as `simValue`
   - Send one `ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY` event **per SIM** (XSLT with `$currSub`, `$simValue`)
   - Increment RequestCount per SIM sent
4. **PATH B — RIO / Old EID** [else condition: `count(ResourceInfo["OLD_EID"]) > 0`]:
   - Run PreExecCheck via `GetXMLForSubscriber`
   - Read `simValue = ResourceInfo["OLD_SIM"]/ValuesArray`
   - Send ONE request
   - Increment RequestCount once
5. **PATH C — SubscriberOffers** [else]:
   - Iterate `currSub.SubscriberOffers[]` → for each `curoffer`:
   - Read `filter = curoffer.ExtendedInfo["FE_OR_CCBS"]/Value`
   - Run PreExecCheck via `GetXMLForSubscriberOfferFilterWithExtendedInfo(…, curoffer.Soc, filter)`
   - Read `simValue = curoffer.ParameterInfo["Related SIM"]/ValuesArray[1]`
   - Send request per qualifying offer
   - Increment RequestCount per offer sent
6. **ChildOU Loop** — same tri-path logic via `GetXMLForSubscriberInChildOU` / `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo`
7. **Status Update** — if any request sent → `IN_PROGRESS`; if all skipped → `SkipActivity("4")`
8. **Exception Handling** — `catch(Exception ae)` → `HandleActivityException` → `ERROR`

---

## §6 — Rule Action (THEN) — Path Details

### MSRES Skip Logic

```java
if(XPath.evalAsBoolean("$currSub/SubscriberActivityInfo/ActivityReason='MSRES'")){
    if(String.equals(activityValue, "RESERVE")){
        reqSuccess = true;  // skip this subscriber
    }
}
```

### Path A — Multi-SIM Key Logic

```java
if(XPath.evalAsBoolean("exists($currSub/ExtendedInfo[Name=\"MSIM_TO_CANCEL\"])")) {
    // PreExecCheck via GetXMLForSubscriber
    String simValues = XPath.evalAsString("$currSub/ExtendedInfo[Name=\"MSIM_TO_CANCEL\"]/Value");
    String[] simValueArray = String.split(simValues, "\\|");
    for(int iSim=0; iSim<simValueArray@length; iSim++){
        String simValue = String.split(simValueArray[iSim], ",")[0];
        // send reqEvent2 (XSLT with $currSub, $simValue) — see §9.8
        orderCurrentActivity.RequestCount++;
    }
}
```

### Path B — RIO / Old EID Key Logic

```java
else if(XPath.evalAsBoolean("count($currSub/ResourceInfo[ResourceName='OLD_EID'])>0")) {
    // PreExecCheck via GetXMLForSubscriber
    String simValue = XPath.evalAsString("$currSub/ResourceInfo[ResourceName='OLD_SIM']/ValuesArray");
    // send reqEvent2 (XSLT with $currSub, $simValue) — see §9.8
    orderCurrentActivity.RequestCount++;
}
```

### Path C — SubscriberOffers Key Logic

```java
else {
    for(int iSubOffer=0; iSubOffer<subOfferLen; iSubOffer++) {
        SubscriberOffers curoffer = currSub.SubscriberOffers[iSubOffer];
        String filter = XPath.evalAsString("$curoffer/ExtendedInfo[Name=\"FE_OR_CCBS\"]/Value");
        // PreExecCheck: GetXMLForSubscriberOfferFilterWithExtendedInfo(…, curoffer.Soc, filter)
        String simValue = XPath.evalAsString(
            "$curoffer/ParameterInfo[ParamName=\"Related SIM\"]/ValuesArray[1]");
        // send reqEvent2 (XSLT with $currSub, $simValue) — see §9.8
        orderCurrentActivity.RequestCount++;
    }
}
```

---

## §7 — Data Extraction — Path-Specific SIM Value Sources

### Activity Parameter

| Key | Method | Variable | Values |
|-----|--------|----------|--------|
| `ACTIVITY` | `tib:tokenize(param,"=")[2]` | `activityValue` | RESERVE / PREACTIVATE / ACTIVATE |

### SIM Value Resolution by Path

| Path | Trigger Condition | SIM Value Source | Multiplicity |
|------|-------------------|-----------------|--------------|
| [A — MSIM] | `exists(ExtendedInfo["MSIM_TO_CANCEL"])` | `ExtendedInfo["MSIM_TO_CANCEL"]/Value` → split `"\|"` → split `","[0]` | One request **per SIM in list** |
| [B — RIO] | `count(ResourceInfo["OLD_EID"]) > 0` | `ResourceInfo["OLD_SIM"]/ValuesArray` | One per subscriber |
| [C — Offers] | else (no MSIM, no OLD_EID) | `curoffer.ParameterInfo["Related SIM"]/ValuesArray[1]` | One per qualifying offer |

### Path A — Pipe-Delimited Parsing

> **MSIM_TO_CANCEL format:** `"ICCID_1|ICCID_2,EXTRA|ICCID_3"`  
> `String.split(simValues, "\\|")` → array of tokens  
> `String.split(token, ",")[0]` → takes first field only (the ICCID); remainder is discarded

### Path C — Offer-Level Filter

The `filter` variable (`curoffer.ExtendedInfo["FE_OR_CCBS"]/Value`) is passed to `GetXMLForSubscriberOfferFilterWithExtendedInfo`, which scopes the XML view of the offer for the PreExecCheck XPath evaluation.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type / Path Dependencies

| Condition | Path | Requests Sent |
|-----------|------|---------------|
| Subscriber has `MSIM_TO_CANCEL` | A | N × number of SIMs in pipe list |
| Subscriber has `OLD_EID` ResourceInfo | B | 1 per subscriber |
| Standard SubscriberOffers subscriber | C | 1 per qualifying offer |
| ActivityReason=MSRES + RESERVE operation | All | 0 (auto-skipped) |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel URI | Destination | Purpose |
|-----------|-------------|-------------|---------|
| [OUTBOUND] | `/Channels/OMXFMConnectionRequest` | `ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY` | Minor SIM resource operation |
| [OUTBOUND] | `/Channels/LogConnection` | `AuditLog` | Audit trail per request |

### §8.3 — Backend API Details

| Attribute | Value |
|-----------|-------|
| System | ASRM — Amdocs Resource Manager 3G |
| Operation | UnifiedResourceActivity (minor/secondary SIM) |
| Resource Type | Dynamic: `SIM` or `STARTER PACK` (per-SIM dynamic key) |
| Per-SIM paired MSISDN key | `concat("SIM_PAIR_MSISDN_", $simValue)` |

### §8.4 — BE Working Memory Dependencies

| Field | Direction | Path | Purpose |
|-------|-----------|------|---------|
| `currSub.SubscriberActivityInfo/ActivityReason` | [READ] | All | MSRES skip guard |
| `currSub.ExtendedInfo["MSIM_TO_CANCEL"]/Value` | [READ] | A | Pipe-delimited multi-SIM list |
| `currSub.ResourceInfo["OLD_EID"]` | [READ] | B | Path B trigger check |
| `currSub.ResourceInfo["OLD_SIM"]/ValuesArray` | [READ] | B | RIO SIM value |
| `currSub.SubscriberOffers[].ExtendedInfo["FE_OR_CCBS"]/Value` | [READ] | C | Offer filter |
| `curoffer.ParameterInfo["Related SIM"]/ValuesArray[1]` | [READ] | C | Offer-linked SIM ICCID |
| `currSub.ResourceInfo[concat("SIM_PAIR_MSISDN_", $simValue)]/ValuesArray` | [READ] | All (XSLT) | Per-SIM type selection |
| `orderCurrentActivity.Status` | [WRITE] | All | IN_PROGRESS or SKIPPED |
| `orderCurrentActivity.RequestCount` | [WRITE] | All | Incremented per individual request sent |

### §8.5 — ExtendedInfo / ResourceInfo Fields Required

| Field | Type | Required/Optional | Purpose | Path |
|-------|------|-------------------|---------|------|
| `ExtendedInfo[Name="MSIM_TO_CANCEL"]/Value` | ExtendedInfo | Path selector | Presence routes to Path A | A |
| `ResourceInfo[ResourceName="OLD_EID"]` | ResourceInfo | Path selector | Presence routes to Path B | B |
| `ResourceInfo[ResourceName="OLD_SIM"]/ValuesArray` | ResourceInfo | Required | SIM value for RIO path | B |
| `ExtendedInfo[Name="FE_OR_CCBS"]/Value` | ExtendedInfo on offer | Optional | Offer filter for PreExecCheck | C |
| `ParameterInfo[ParamName="Related SIM"]/ValuesArray[1]` | ParameterInfo on offer | Required | Offer-linked SIM ICCID | C |
| `ResourceInfo[ResourceName=concat("SIM_PAIR_MSISDN_", $simValue)]/ValuesArray` | ResourceInfo | Optional | Per-SIM paired MSISDN → STARTER PACK type | All |
| `SubscriberActivityInfo/ActivityReason` | SubscriberActivityInfo | Optional | 'MSRES' triggers RESERVE skip | All |

### §8.6 — Global Variable Dependencies

| Global Variable Path | Purpose |
|----------------------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Include credentials in request |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL value |
| `OMX_OM/WritePayload` | Include payload in audit log |

---

## §9 — Detailed Payload Build (XSLT Decomposition)

### §9.1 — XSLT Parameter Binding

The same XSLT template is used for all three paths. The difference is in how `$simValue` and `$currSub` are derived before the call.

| Parameter | Bound From | Notes |
|-----------|------------|-------|
| `$orderRequest` | Working memory concept | Full order request tree |
| `$refId` | `subscriber.RefId` | Per-subscriber correlation key |
| `$globalVariables` | BE global variables | Credential gate, logging config |
| `$activityValue` | Parsed ACTIVITY parameter | RESERVE / PREACTIVATE / ACTIVATE |
| `$currSub` | Concept reference: `currSub` | **New vs ASRM_INVOKE_SIM** — passed for per-SIM MSISDN lookup |
| `$simValue` | Path-specific (see §7) | **New vs ASRM_INVOKE_SIM** — the specific SIM ICCID/EID |

### §9.5 — Resource Type Selection (xsl:choose)

> ⚠ The Type lookup key is **dynamic per SIM**: `concat("SIM_PAIR_MSISDN_", $simValue)` — not the fixed `SIM_PAIR_MSISDN` used by ASRM_INVOKE_SIM.

| Condition | `ns1:Type` Value |
|-----------|-----------------|
| `OrderType = "51"` | `STARTER PACK` |
| `OrderType != "51" AND ResourceInfo[concat("SIM_PAIR_MSISDN_",$simValue)]/ValuesArray is empty` | `SIM` |
| `OrderType != "51" AND ResourceInfo[concat("SIM_PAIR_MSISDN_",$simValue)]/ValuesArray is non-empty` | `STARTER PACK` |

### §9.6 — Resource Value

Always directly uses `$simValue` (no fallback chain):

```xml
<ns1:Value><xsl:value-of select="$simValue"/></ns1:Value>
```

### §9.8 — XSLT Stylesheet Source (all paths share same template)

```xml
<xsl:stylesheet
  xmlns:ns2="www.tibco.com/plugin/java/xmlSchema/amdocs.rm3g.interfaces.datatypes.UnifiedResourceActivityInfo"
  xmlns:ns1="www.tibco.com/plugin/java/xmlSchema/amdocs.rm3g.interfaces.datatypes.RMEntityIdInfo"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="www.tibco.com/plugin/java/xmlSchema/amdocs.rm3g.interfaces.datatypes.ActivityInfo"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="refId"/>
  <xsl:param name="globalVariables"/>
  <xsl:param name="activityValue"/>    <!-- RESERVE / PREACTIVATE / ACTIVATE -->
  <xsl:param name="currSub"/>          <!-- subscriber concept — for per-SIM pair key lookup -->
  <xsl:param name="simValue"/>         <!-- the specific SIM ICCID/EID for this request -->

  <xsl:template match="/">
    <createEvent><event>
      <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      <RefID><xsl:value-of select="$refId"/></RefID>
      <!-- Credential gate identical to ASRM_INVOKE_SIM -->
      <xsl:if test="$orderRequest/OrderData/OrderType">
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      </xsl:if>
      <payload>
        <ns2:UnifiedResourceActivityInfo>
          <ns2:Activity>
            <ns:ActivityName><xsl:value-of select="$activityValue"/></ns:ActivityName>
          </ns2:Activity>
          <ns2:UnifiedResource>
            <!-- Type: per-SIM dynamic key: concat("SIM_PAIR_MSISDN_", $simValue) -->
            <xsl:choose>
              <xsl:when test="$orderRequest/OrderData/OrderType='51'">
                <ns1:Type>STARTER PACK</ns1:Type>
              </xsl:when>
              <xsl:when test="$orderRequest/OrderData/OrderType!='51' and
                string-length(tib:trim($currSub/ResourceInfo[
                  ResourceName=concat('SIM_PAIR_MSISDN_', $simValue)]/ValuesArray)) = 0">
                <ns1:Type>SIM</ns1:Type>
              </xsl:when>
              <xsl:when test="$orderRequest/OrderData/OrderType!='51' and
                string-length(tib:trim($currSub/ResourceInfo[
                  ResourceName=concat('SIM_PAIR_MSISDN_', $simValue)]/ValuesArray)) > 0">
                <ns1:Type>STARTER PACK</ns1:Type>
              </xsl:when>
            </xsl:choose>
            <!-- Value: always the pre-resolved simValue (no fallback chain) -->
            <ns1:Value><xsl:value-of select="$simValue"/></ns1:Value>
          </ns2:UnifiedResource>
        </ns2:UnifiedResourceActivityInfo>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

*Same XSLT for all three paths — only $simValue and $currSub differ between paths.*

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                          [Always]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId                [Always]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID                      [Always]
    ├── RefID                    ← $refId                                                [Always]
    ├── UserName                 ← $orderRequest/OrderData/User                         [Credential-gated]
    ├── PassWord                 ← $orderRequest/OrderData/Password                     [Credential-gated]
    ├── OrderType                ← $orderRequest/OrderData/OrderType                    [Conditional: if exists]
    └── payload
        └── ns2:UnifiedResourceActivityInfo
            ├── ns2:Activity
            │   └── ns:ActivityName    ← $activityValue                                 [Always]
            └── ns2:UnifiedResource
                ├── ns1:Type           [Conditional: xsl:choose on OrderType + per-SIM pair key]
                │   ├── when OrderType='51'                                   → "STARTER PACK" [Static]
                │   ├── when OrderType!='51' AND SIM_PAIR_MSISDN_<simValue>="" → "SIM"          [Static]
                │   └── when OrderType!='51' AND SIM_PAIR_MSISDN_<simValue>!="" → "STARTER PACK" [Static]
                └── ns1:Value          ← $simValue                                      [Always]
                    ├── Path A source: ExtendedInfo["MSIM_TO_CANCEL"]/Value → split "|" → split ","[0]
                    ├── Path B source: ResourceInfo["OLD_SIM"]/ValuesArray
                    └── Path C source: curoffer.ParameterInfo["Related SIM"]/ValuesArray[1]
```

**Legend:**
- `←` XPath source (green)
- `→` static literal (orange)
- `[Always]` unconditional
- `[Conditional: ...]` inside xsl:if/xsl:choose
- `[Credential-gated]` behind IsEnableUserPass check

---

## §11 — Audit Logging

Logger event uses variable `reqEvent2`. All three paths and their ChildOU counterparts use identical logger XSLT.

| Field | Source | Condition |
|-------|--------|-----------|
| `ESBUUID` | `$orderRequest/OrderData/OMXTrackingId` | If exists |
| `PROCESS_ID` | `concat($pid, "_REQ")` | Always |
| `OPERATION_NAME` | `$operatorname` (ASRM_INVOKE_MINOR_SIM_RESERVE etc.) | Always |
| `AUDIT_TRACE` | `concat("Request Sent for RefId ", $refId)` | Always |
| `payload/ns:ServicePayload` | copy-of($reqEvent2) | Only if `OMX_OM/WritePayload = "true"` |

---

## §12 — Activity Status Management

| Trigger | Code | Status | Method |
|---------|------|--------|--------|
| Rule fires | 0 | WAITING | Pre-condition |
| At least one request sent (any path) | 1 | IN_PROGRESS | `GetActivityStatusString("1", false)` |
| All skipped (no qualifying SIMs/offers, or all MSRES) | 4 | SKIPPED | `SkipActivity(…, "4")` |
| Exception caught | 3 | ERROR | `HandleActivityException` |

---

## §14 — Helper Functions Reference

| Function | Return | Path | Purpose |
|----------|--------|------|---------|
| `GetXMLForSubscriber(orderRequest, refId)` | String | A, B | Subscriber XML for PreExecCheck |
| `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` | String | A, B (ChildOU) | ChildOU subscriber XML |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, soc, filter)` | String | C | **New:** offer-scoped XML with FE_OR_CCBS filter |
| `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, refId, soc, pouRefId, filter)` | String | C (ChildOU) | **New:** ChildOU offer-scoped XML |
| `AllowWriteLog(orderType)` | boolean | All | Log filter by order type |
| `GetActivityStatusString("1", false)` | "IN_PROGRESS" | All | Status mapping |
| `SendDataToDB(orderRequest)` | void | All | Persist state |
| `SkipActivity(orderRequest, activity, "4")` | void | All | Set SKIPPED |
| `HandleActivityException(orderRequest, activity, ae, "")` | void | All | Error handling chain |

---

## §15 — Function Dependency Tree

```text
Request_ASRM_INVOKE_MINOR_SIM (rule)
├── XPath.evalAsString(tib:tokenize ...)                    [ACTIVITY param parsing]
├── Per subscriber:
│   ├── XPath.evalAsBoolean("ActivityReason='MSRES'")       [MSRES skip guard]
│   ├── XPath.evalAsBoolean("exists(MSIM_TO_CANCEL)")       [Path A selector]
│   │   ├── RuleFunctions.Helpers.GetXMLForSubscriber(...)
│   │   ├── XPath.execute(preExecCheck, xml, ns)
│   │   ├── XPath.evalAsString("MSIM_TO_CANCEL/Value")
│   │   ├── String.split(simValues, "\\|")
│   │   ├── String.split(token, ",")[0]
│   │   ├── Event.createEvent(xslt://ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY) [per SIM]
│   │   └── Event.Ext.sendEventImmediate(reqEvent2)
│   ├── XPath.evalAsBoolean("count(OLD_EID)>0")             [Path B selector]
│   │   ├── RuleFunctions.Helpers.GetXMLForSubscriber(...)
│   │   ├── XPath.execute(preExecCheck, xml, ns)
│   │   ├── XPath.evalAsString("OLD_SIM/ValuesArray")
│   │   ├── Event.createEvent(xslt://ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY)
│   │   └── Event.Ext.sendEventImmediate(reqEvent2)
│   └── else [Path C — SubscriberOffers loop]
│       ├── XPath.evalAsString("FE_OR_CCBS/Value")
│       ├── RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(...)
│       ├── XPath.execute(preExecCheck, xml, ns)
│       ├── XPath.evalAsString("ParameterInfo[Related SIM]/ValuesArray[1]")
│       ├── Event.createEvent(xslt://ASRM_INVOKE_UNIFIED_RESOURCE_ACTIVITY) [per offer]
│       └── Event.Ext.sendEventImmediate(reqEvent2)
├── RuleFunctions.Helpers.AllowWriteLog(orderType)
│   └── System.getGlobalVariableAsString(OrderTypeFilter)
├── Event.createEvent(xslt://Logger)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)
└── RuleFunctions.Helpers.HandleActivityException(...)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Implement three-path dispatch: MSIM_TO_CANCEL → OLD_EID/OLD_SIM → SubscriberOffers.
- **R2** — Path A must loop over pipe-delimited SIM values, splitting each by comma and taking `[0]`.
- **R3** — Path B sources the SIM value from `ResourceInfo["OLD_SIM"]`, not from ExtendedInfo.
- **R4** — Path C must iterate SubscriberOffers with per-offer PreExecCheck using FE_OR_CCBS filter.
- **R5** — Resource Type lookup key must be `concat("SIM_PAIR_MSISDN_", $simValue)` — per-SIM, not fixed.
- **R6** — MSRES + RESERVE subscribers must be auto-skipped before path evaluation.
- **R7** — RequestCount increments per individual request (multiple per subscriber in Path A and C).
- **R8** — Both ParentOU and ChildOU subscriber hierarchies must be supported.

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| RequestCount can grow > subscriber count (Path A fan-out per SIM) | [HIGH] | Fan-in response rule must handle high counts; ensure `Response_ASRM_INVOKE_MINOR_SIM` waits for all SIMs |
| Three-path logic creates complex branching | [HIGH] | Create three separate service operations in target architecture; do not merge into one service |
| Path C SubscriberOffers loop with per-offer filter XML construction is expensive | [MEDIUM] | Consider batch/bulk ASRM API if available |
| MSIM_TO_CANCEL pipe-split format may change | [MEDIUM] | Document the delimiter contract; add validation in the migration service |
| MSRES skip only applies to RESERVE — not PREACTIVATE or ACTIVATE | [LOW] | Intentional but easy to miss; document clearly in migration tests |

---

## §19 — Response Message Rule

### §19.1 — Overview

`RuleFunctions.OrderResponse.Response_ASRM_INVOKE_MINOR_SIM` — identical structure to `Response_ASRM_INVOKE_MSISDN` and `Response_ASRM_INVOKE_SIM`. Creates `ASRM_InvokeUnifiedResourceRes`, appends to `currActivity.Response[]`, logs audit (_RES), evaluates fan-in.

### §19.4 — Fan-in Completion Logic

```java
int successResponseCount = XPath.evalAsInt(
    "count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = \"000\"])");
if(currActivity.RequestCount == successResponseCount) return "true";
else return "false";
```

> ⚠ **Important:** Because Path A can send multiple requests per subscriber (one per SIM in MSIM_TO_CANCEL), `RequestCount` can be much larger than the subscriber count. The fan-in only completes when ALL individual SIM operations return ResponseCode ending in "000".

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
