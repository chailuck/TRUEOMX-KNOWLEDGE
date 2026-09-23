# Request_CCBS_OFFER_EXCLUSION

> Batch SOC exclusion group lookup with dual backend routing (CCBS vs CES/GoldenDB) — collects all unique SOCs across all offer types, fires one aggregated request

**Target System:** CCBS / CES (GoldenDB) | **Pattern:** Batch/aggregate SOC collection | **forwardChain:** true | **Author:** awalia-t420 | **Generated:** 2026-08-04

---

## §1 Overview & Purpose

This FM retrieves offer exclusion group data for all SOC codes involved in the order. It aggregates all unique SOC codes from every offer source (Agreement Offers, Agreement RelatedOffersArray, Subscriber SubscriberOffers, Subscriber SubscriberOffers RelatedOffersArray — across both POU and COU) into a deduplicated list, then fires **a single batch request** to CCBS (or CES for GoldenDB orders). The response writes the exclusion group name (`TR_OFFER_EXCL_GROUP_NAME`) to each matching offer's `SocProperties` field, but only if `SocProperties` is currently blank (idempotent write-back).

> **Dual backend routing:** When `orderRequest.OrderData.GoldenDB == "Y"`, the request is routed to `CES_OFFER_EXCLUSION` (CES backend). Otherwise it goes to `CCBS_OFFER_EXCLUSION`. Both share the same payload schema but differ in event type and the CES variant adds an `extId` attribute using `OMXUtils:generateTrackingID()`.

> **Double SendDataToDB:** `SendDataToDB` is called both inside the success branch (line 136) and unconditionally after the if/else block (line 141). The second call is redundant.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_CCBS_OFFER_EXCLUSION.rule` | 148 lines |
| Response file | `Response_CCBS_OFFER_EXCLUSION.rulefunction` | 157 lines |
| Author | awalia-t420 | |
| forwardChain | true | |
| Request event (CCBS path) | `Events.OMConsumers.OMXFM.Request.CCBS_OFFER_EXCLUSION` | Default backend |
| Request event (CES path) | `Events.OMConsumers.OMXFM.Request.CES_OFFER_EXCLUSION` | GoldenDB==Y only |
| Response event | `Events.OMConsumers.OMXFM.Response.CCBS_OFFER_EXCLUSION` | Single response regardless of routing |
| Request schema NS | `http://www.tibco.com/schemas/OMX_FM/SharedResources/Schema Definitions/OfferExclusionRequest.xsd` (ns) | |
| Response schema NS | `http://www.tibco.com/schemas/OMX_FM/SharedResources/Schema Definitions/OfferExclusionResponse.xsd` (xsd2) | Note: xsd2 prefix in response |
| Response concept | `Concepts.FM.Response.CCBS_OfferExclusionRes` | Custom — has OfferExclusionResponse[] array |
| Fan-out level | Batch — single event regardless of SOC count | |
| Credential gate | IsEnableUserPass (global var) | Credentials from OrderData.User/Password — same as MCS pattern |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Source of all SOC codes; GoldenDB routing flag; offer SocProperties written by response |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Activity state; RequestCount++ once; Response[] appended by response handler |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_OFFER_EXCLUSION"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_OFFER_EXCLUSION"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 Execution Flow Diagram

1. **Resubmit flag** — `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. **PreExecCheck** — if length > 0: evaluate XPath; if != "true" → `SkipActivity("4")` and exit
3. **Collect SOC codes** — build deduplicated `arrLstSOCs` ArrayList:
   - POU Agreement Offers + RelatedOffersArray[].Soc
   - POU Subscriber[].SubscriberOffers[].Soc + RelatedOffersArray[].Soc
   - COU Agreement Offers + RelatedOffersArray[].Soc
   - COU Subscriber[].SubscriberOffers[].Soc + RelatedOffersArray[].Soc
4. **Route by GoldenDB:** GoldenDB=="Y" → CES event; else → CCBS event
5. **Send event + audit** — `sendEventImmediate(reqEvent)`; if !isActResub → `RequestCount++`; send audit
6. **Status update** — `GetActivityStatusString("1", false)` + `SendDataToDB`
7. **Redundant SendDataToDB** (line 141) — unconditionally after if/else `[Bug: redundant]`
8. **Exception** — try/catch → `HandleActivityException`

---

## §6 Rule Action (THEN) — Key Details

### §6.1 — SOC Collection Logic

```java
Object arrLstSOCs = Collections.List.createArrayList();
// For each POU + COU, Agreement + Subscriber, Offer + RelatedOffersArray:
if (currSoc != "" && !Collections.contains(arrLstSOCs, currSoc))
    Collections.add(arrLstSOCs, currSoc);
// Repeat for RelatedOffersArray[k].Soc

Object[] socIDs = Collections.toArray(arrLstSOCs);
```

All 8 offer sources (4 types × POU+COU) are traversed. The final `socIDs` array is passed as XSLT parameter to build the payload.

### §6.2 — GoldenDB Routing Branch

```java
if(!IsBlankOrStringNull(orderRequest.OrderData.GoldenDB) && String.equals("Y", orderRequest.OrderData.GoldenDB)) {
    // CES path — adds extId attribute via OMXUtils:generateTrackingID()
    Events..CES_OFFER_EXCLUSION reqEvent = Event.createEvent("xslt://{{CES_OFFER_EXCLUSION}}...");
} else {
    // CCBS path — standard CCBS backend, no extId
    Events..CCBS_OFFER_EXCLUSION reqEvent = Event.createEvent("xslt://{{CCBS_OFFER_EXCLUSION}}...");
}
```

### §6.3 — Double SendDataToDB (Bug)

> **Line 136 (inside success branch):** `RuleFunctions.Helpers.SendDataToDB(orderRequest);`
> **Line 141 (after if/else, unconditional):** `RuleFunctions.Helpers.SendDataToDB(orderRequest);`
> The second call is always executed. Redundant and may cause unnecessary DB writes.

---

## §7 Data Extraction

No pipe/delimiter parsing in the request. SOC dedup collection is the primary data aggregation step. The response uses `XPath.evalAsString` to extract individual fields from each `OfferExclusionReturn` element by index.

---

## §8 System & Integration Dependencies

### §8.1 — Order Type Dependencies

| GoldenDB | Backend | Event Type |
|----------|---------|------------|
| `"Y"` | CES (GoldenDB) | `CES_OFFER_EXCLUSION` |
| blank / other | CCBS | `CCBS_OFFER_EXCLUSION` |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Purpose |
|-----------|---------|-------------|---------|
| [OUTBOUND] | FM JMS | CCBS_OFFER_EXCLUSION queue | Batch SOC exclusion lookup (CCBS path) |
| [OUTBOUND] | FM JMS | CES_OFFER_EXCLUSION queue | Batch SOC exclusion lookup (GoldenDB path) |
| [INBOUND] | FM JMS | CCBS_OFFER_EXCLUSION response queue | OfferExclusionReturn[] per SOC |
| [LOG] | OMXESB Logger | Audit event (immediate) | Request and response audit trail |

### §8.3 — Backend API Details

| Field | CCBS Path | CES Path |
|-------|-----------|----------|
| System | CCBS | CES (GoldenDB) |
| Request root | `ns:OfferExclusionRequest` | `ns:OfferExclusionRequest` |
| Response root | `xsd2:OfferExclusionResponse` | `xsd2:OfferExclusionResponse` |
| Key request field | `SOCCode` (repeated) | `SOCCode` (repeated) |
| Key response field | `OfferExclusionReturn[].Soc_Code + Exc_Group` | same |
| Correlation pattern | Batch — one response for all SOCs | same |

### §8.4 — BE Working Memory Dependencies

| Concept | Field | Access | Notes |
|---------|-------|--------|-------|
| OrderRequest | OrderData.GoldenDB | READ | Backend routing decision |
| OrderRequest | Customer.ParentOU[].Agreement.Offers[].Soc | READ | SOC collection |
| OrderRequest | Customer.ParentOU[].Agreement.Offers[].RelatedOffersArray[].Soc | READ | SOC collection |
| OrderRequest | Customer.ParentOU[].Subscriber[].SubscriberOffers[].Soc | READ | SOC collection |
| OrderRequest | Customer.ParentOU[].Subscriber[].SubscriberOffers[].RelatedOffersArray[].Soc | READ | SOC collection |
| OrderRequest | (all above repeated for ChildOU) | READ | COU equivalents |
| AgreementOffers / SubscriberOffers / RelatedOffersArray | SocProperties | WRITTEN | Set to `"TR_OFFER_EXCL_GROUP_NAME=<group>;"` if currently blank |
| Activity | RequestCount / Response[] | READ+WRITTEN | RequestCount++ once; Response[] appended |

### §8.5 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Credential gate flag |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `OMX_OM/WritePayload` | Payload inclusion in audit |

> **Credential inconsistency:** Credentials come from `$orderRequest/OrderData/User` and `/Password` — NOT global variables. Same pattern as MCS_GET_CHARGE_INFO.

---

## §9 Detailed Payload Build

### §9.1 — XSLT Parameters

| Parameter | Bound From | Both Variants |
|-----------|-----------|---------------|
| `$orderRequest` | orderRequest concept serialized | Yes |
| `$globalVariables` | System global variables | Yes |
| `$socIDs` | `Collections.toArray(arrLstSOCs)` — deduped SOC array | Yes |

### §9.2 — Variant Differences

| Feature | CCBS variant | CES variant (GoldenDB) |
|---------|-------------|------------------------|
| Event type | `CCBS_OFFER_EXCLUSION` | `CES_OFFER_EXCLUSION` |
| extId on event | Not set | `OMXUtils:generateTrackingID()` |
| OMXUtils import | Not imported | `xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"` |
| Payload structure | Identical | Identical |
| Headers | Identical | Identical |

### §9.3 — JMS / Event Header Fields

| Header | Source | Condition |
|--------|--------|-----------|
| extId (event attr) | `OMXUtils:generateTrackingID()` | CES variant only — Always |
| JMSPriority | `$orderRequest/OrderPriority` | Conditional |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| OrderID | `$orderRequest/OrderData/OrderID` | Conditional |
| UserName | `$orderRequest/OrderData/User` | [Credential-gated: IsEnableUserPass + User present] |
| PassWord | `$orderRequest/OrderData/Password` | [Credential-gated] |
| OrderType | `$orderRequest/OrderData/OrderType` | Conditional |

> No `RefID` header. Response correlation is via JMSCorrelationID. Response concept extId = `concat("OFEXROOT:", JMSCorrelationID)`.

### §9.4 — Payload Fields

| XML Element | Source | Iteration |
|-------------|--------|-----------|
| `ns:OfferExclusionRequest` | — root container | |
| `SOCCode` | `xsl:for-each select="$socIDs/elements"` → `.` | One per unique SOC |

### §9.5 — Generated XML Example

```xml
<event extId="TRK-20250804-001">  <!-- extId only in CES variant -->
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-20250804-001</JMSCorrelationID>
  <OrderID>ORD-001</OrderID>
  <OrderType>3</OrderType>
  <payload>
    <ns:OfferExclusionRequest
      xmlns:ns="http://www.tibco.com/schemas/OMX_FM/SharedResources/Schema Definitions/OfferExclusionRequest.xsd">
      <SOCCode>VOICE_PLAN_A</SOCCode>
      <SOCCode>DATA_PACK_B</SOCCode>
      <SOCCode>SMS_BUNDLE_C</SOCCode>
    </ns:OfferExclusionRequest>
  </payload>
</event>
```

### §9.6 — XSLT Stylesheet Source

```xml
<!-- CES variant (GoldenDB path) — adds extId attribute -->
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX_FM/SharedResources/Schema Definitions/OfferExclusionRequest.xsd"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="globalVariables"/>
  <xsl:param name="socIDs"/>   <!-- deduplicated SOC ArrayList serialized to XML -->
  <xsl:template match="/">
    <createEvent><event>
      <xsl:attribute name="extId">   <!-- CES only -->
        <xsl:value-of select="OMXUtils:generateTrackingID()"/>
      </xsl:attribute>
      <xsl:if test="$orderRequest/OrderPriority">
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderID">
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      </xsl:if>
      <xsl:if test="$globalVariables/OMX_OM/Rules/.../IsEnableUserPass='true'">
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
        <ns:OfferExclusionRequest>
          <xsl:for-each select="$socIDs/elements">
            <SOCCode><xsl:value-of select="."/></SOCCode>
          </xsl:for-each>
        </ns:OfferExclusionRequest>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
<!-- CCBS variant: identical except no xmlns:OMXUtils and no <xsl:attribute name="extId"> block -->
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event @extId ← OMXUtils:generateTrackingID()                              [CES variant only]
    ├── JMSPriority          ← $orderRequest/OrderPriority                    [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId          [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                [Conditional]
    ├── UserName             ← $orderRequest/OrderData/User                   [Credential-gated: IsEnableUserPass]
    ├── PassWord             ← $orderRequest/OrderData/Password               [Credential-gated: IsEnableUserPass]
    ├── OrderType            ← $orderRequest/OrderData/OrderType              [Conditional]
    └── payload
        └── ns:OfferExclusionRequest
            └── SOCCode      ← xsl:for-each $socIDs/elements → .             [Repeated per unique SOC]
```

---

## §11 Audit Logging

| Field | Request Value | Response Value |
|-------|---------------|----------------|
| AUDIT_TRACE | `"Request Sent for CCBS_OFFER_EXCLUSION"` | `"Response received for CCBS_OFFER_EXCLUSION"` |
| OPERATION_NAME | `"CCBS_OFFER_EXCLUSION"` | `"CCBS_OFFER_EXCLUSION"` |
| PROCESS_ID | `concat($pid, "_REQ")` | `concat($pid, "_RES")` |
| Payload | Copy of `$reqEvent` (WritePayload gated) | Copy of `$eventResponse` (WritePayload gated) |

---

## §12 Activity Status Management

| Condition | Call | Code |
|-----------|------|------|
| PreExecCheck passes, event sent | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" (RUNNING) |
| PreExecCheck fails | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" (SKIPPED) |

> **Bug:** `SendDataToDB` also called at line 141 (outside if/else) unconditionally — redundant.

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
| `Collections.List.createArrayList()` | Create deduplicated SOC list |
| `Collections.contains(list, item)` | Dedup check before adding SOC |
| `Collections.add(list, item)` | Add SOC to list |
| `Collections.toArray(list)` | Convert list to Object[] for XSLT param |
| `IsBlankOrStringNull(value)` | Null/blank check on GoldenDB flag |
| `String.equals("Y", GoldenDB)` | GoldenDB routing check |
| `GetActivityStatusString(code, flag)` | Activity status string builder |
| `SendDataToDB(orderRequest)` | Persist to DB (called twice — bug) |
| `SkipActivity(orderRequest, activity, code)` | Mark activity skipped |
| `HandleActivityException(orderRequest, activity, ae, msg)` | Exception handler |
| `XPath.evalAsInt(xpath...)` | **Response:** count OfferExclusionReturn elements |
| `XPath.evalAsString(xpath...)` | **Response:** extract Soc_Code and Exc_Group per element |

---

## §15 Function Dependency Tree

```text
Request_CCBS_OFFER_EXCLUSION (rule)
├── Instance.serializeUsingDefaults(orderRequest)  [if PreExecCheck present]
├── XPath.execute(chkXPath, sXML, ns)  [PreExecCheck evaluation]
├── Collections.List.createArrayList()
├── Collections.contains(arrLstSOCs, currSoc)  [dedup ×8 offer sources]
├── Collections.add(arrLstSOCs, currSoc)
├── Collections.toArray(arrLstSOCs)  → socIDs
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(GoldenDB)
├── String.equals("Y", GoldenDB)
├── Event.createEvent("xslt://CES_OFFER_EXCLUSION...")  [GoldenDB path]
│   └── OMXUtils:generateTrackingID()  [event extId — CES only]
├── Event.createEvent("xslt://CCBS_OFFER_EXCLUSION...")  [default path]
├── Event.Ext.sendEventImmediate(reqEvent)
├── Event.Ext.sendEventImmediate(auditEvent)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)  [×2 — redundant]
├── RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")  [if skip]
└── RuleFunctions.Helpers.HandleActivityException(...)  [catch]

Response_CCBS_OFFER_EXCLUSION (rulefunction)
├── Instance.createInstance("xslt://CCBS_OfferExclusionRes...")
│   └── concat("OFEXROOT:", JMSCorrelationID)  [custom extId — NOT generateTrackingID]
├── currActivity.Response[length] = resEvent
├── XPath.evalAsInt("count(.../OfferExclusionReturn)")
├── XPath.evalAsString("...OfferExclusionReturn[$i]/Soc_Code")  [per item]
├── XPath.evalAsString("...OfferExclusionReturn[$i]/Exc_Group")  [per item]
├── String.equals(offer.Soc, soc_cd)  [match ×8 offer sources]
├── String.length(offer.SocProperties)==0  [idempotent write guard]
│   └── offer.SocProperties = "TR_OFFER_EXCL_GROUP_NAME=" + group_name + ";"
├── Event.Ext.sendEventImmediate(auditLogEvent)
└── return "true"  [always — unconditional fan-in]
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields | Role |
|---------|-----------|------|
| `Concepts.FM.Response.CCBS_OfferExclusionRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, OfferExclusionResponse[] (SOC_CD, GROUP_NAME) | Custom — array of per-SOC exclusion group results |
| `Concepts.OrderRequest.OrderElements.AgreementOffers` | Soc, SocProperties | READ + WRITTEN |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Soc, SocProperties | READ + WRITTEN |
| `Concepts.OrderRequest.OrderElements.RelatedOffersArray` | Soc, SocProperties | READ + WRITTEN |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Collect all unique SOC codes across all 8 offer sources (4 types × POU+COU) before sending. |
| R2 | Dedup SOC codes using contains-check before adding to list. |
| R3 | Route to CES_OFFER_EXCLUSION when `GoldenDB == "Y"`; CCBS_OFFER_EXCLUSION otherwise. |
| R4 | CES variant must generate and set `extId` on the event via `OMXUtils:generateTrackingID()`. |
| R5 | Credential gate: if IsEnableUserPass, include UserName/PassWord from OrderData (not global variables). |
| R6 | Response: write `SocProperties = "TR_OFFER_EXCL_GROUP_NAME=<Exc_Group>;"` to matching offers — only if SocProperties is currently blank. |
| R7 | Fan-in always returns "true" — single batch event. |
| R8 | Response extId = `concat("OFEXROOT:", JMSCorrelationID)` — NOT generateTrackingID. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Double SendDataToDB (lines 136 + 141)** | [MEDIUM] | Remove unconditional line 141 call |
| Credential source inconsistency (OrderData vs global variables) | [MEDIUM] | Document as per-order credential pattern; replicate from OrderData in migration |
| Dual backend (CCBS/CES) — both paths must be tested | [MEDIUM] | Add test cases for GoldenDB=="Y" and blank/other |
| SocProperties idempotency — won't update on resubmit if already set | [LOW] | Verify resubmit intent; may need to clear SocProperties on resubmit |
| Dead code: inner Agreement null check is unreachable (lines 42–44) | [LOW] | Remove in migration for clarity |

---

## §18 Full Source Code

```java
/**
 * Request_CCBS_OFFER_EXCLUSION — Author: awalia-t420
 * Batch SOC exclusion group lookup, dual backend (CCBS/CES)
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_OFFER_EXCLUSION {
  attribute { priority=5; forwardChain=true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CCBS_OFFER_EXCLUSION";
    orderRequest.ProcessFlow.NextActivityID == "CCBS_OFFER_EXCLUSION";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      // PreExecCheck evaluation
      String chkRes = "true";
      if(String.length(nextAct.PreExecCheck) > 0) { ... }

      if(String.equals(chkRes, "true")) {
        // Collect unique SOCs from 8 offer sources
        Object arrLstSOCs = Collections.List.createArrayList();
        // ... POU + COU loops (4 types × 2 = 8 sources)
        Object[] socIDs = Collections.toArray(arrLstSOCs);

        if(!IsBlankOrStringNull(GoldenDB) && String.equals("Y", GoldenDB)) {
          // [CES XSLT — adds extId via OMXUtils:generateTrackingID() — see §9.6]
          Events..CES_OFFER_EXCLUSION reqEvent = Event.createEvent("xslt://{{CES_OFFER_EXCLUSION}}...");
          Event.Ext.sendEventImmediate(reqEvent);
          if(!isActResub) orderCurrentActivity.RequestCount++;
          Event.Ext.sendEventImmediate(auditEvent);
        } else {
          // [CCBS XSLT — no extId — see §9.6]
          Events..CCBS_OFFER_EXCLUSION reqEvent = Event.createEvent("xslt://{{CCBS_OFFER_EXCLUSION}}...");
          Event.Ext.sendEventImmediate(reqEvent);
          if(!isActResub) orderCurrentActivity.RequestCount++;
          Event.Ext.sendEventImmediate(auditEvent);
        }
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);  // line 136
      } else {
        SkipActivity(orderRequest, orderCurrentActivity, "4");
      }
      SendDataToDB(orderRequest);  // line 141 — BUG: redundant
    } catch (Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §19 Response Message Rule

### §19.1 — Overview

Parses the batch OfferExclusionResponse, populates a `CCBS_OfferExclusionRes` concept with per-SOC exclusion group data, then iterates each `OfferExclusionReturn` item and writes `TR_OFFER_EXCL_GROUP_NAME` to the `SocProperties` of every matching offer across all 8 offer sources. Returns "true" unconditionally (batch = single event = always complete).

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | READ/WRITTEN — offer SocProperties written per SOC result |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.CCBS_OFFER_EXCLUSION | Backend response |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Response[] appended |

### §19.3 — Response Concept Construction (CCBS_OfferExclusionRes)

```text
createObject
└── object @extId ← concat("OFEXROOT:", $eventResponse/JMSCorrelationID)    [Always — NOT generateTrackingID]
    ├── ResponseCode               ← $eventResponse/ResponseCode             [Conditional]
    ├── ResponseMessage            ← $eventResponse/ResponseMsg               [Conditional]
    ├── CompletionStatus           ← $eventResponse/CompletionStatus          [Conditional]
    ├── ReferenceId                ← $eventResponse/RefID                     [Conditional]
    └── OfferExclusionResponse[]   ← xsl:for-each .../OfferExclusionReturn   [Repeated per return item]
        ├── @extId  ← concat("OFFEXCL:", ../../../JMSCorrelationID, ":", Soc_Code)
        ├── SOC_CD  ← Soc_Code
        └── GROUP_NAME ← Exc_Group
```

### §19.4 — Write-back to Offers

```java
int respLen = XPath.evalAsInt("count($eventResponse/payload/xsd2:OfferExclusionResponse/OfferExclusionReturn)");
for(int iResp=0; iResp < respLen; iResp++) {
    String soc_cd = XPath.evalAsString("...OfferExclusionReturn[$iResp + 1]/Soc_Code");
    String group_name = XPath.evalAsString("...OfferExclusionReturn[$iResp+1]/Exc_Group");

    if(String.length(group_name) > 0) {
        // Iterate ALL 8 offer sources: POU+COU × Agreement+Subscriber × Offer+RelatedOffer
        if(String.equals(offer.Soc, soc_cd)) {
            if(String.length(offer.SocProperties) == 0) {  // idempotent: only if blank
                offer.SocProperties = "TR_OFFER_EXCL_GROUP_NAME=" + group_name + ";";
            }
        }
    }
}
```

### §19.5 — Fan-in Completion Logic

```java
return "true";  // Always — unconditional fan-in (batch = single event)
```

Unlike most FMs, there is no RequestCount comparison. Only one event is ever fired per activity execution, so the response handler returns "true" unconditionally.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
