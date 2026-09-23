# Request_CRM_GET_ASSET_COMPONENT_LIST

> CRM — Fetch active asset components (SIM, IMSI, offers) per subscriber from Siebel CRM.
> TIBCO BusinessEvents FM Logic Documentation · TRUE Corporation OMX

**Priority:** 5 | **forwardChain:** true | **Target:** CRM (Siebel) | **Fan-out:** ParentOU + ChildOU | **PREPAID_CANCEL Step:** 2

---

## §1 — Overview & Purpose

`Request_CRM_GET_ASSET_COMPONENT_LIST` fires when the order process reaches activity `CRM_GET_ASSET_COMPONENT_LIST`. It queries CRM (Siebel) for every asset component attached to each subscriber — physical resources (SIM card, IMSI, MSISDN, PMATCHID, Equipment, PEID) and commercial offers (Price Plan, SOC/OFFER, Additional Offer, SOC/OFFER(TOPPING)).

In the **PREPAID_CANCEL** flow (step 2), this FM is called with `STATUS=Active` immediately after `CRM_GET_LAST_ASSET_ROOT` has confirmed the subscriber is Mobile Prepaid and populated their `AssetCrmId`. The response RF enriches each subscriber's `ResourceInfo[]` and `SubscriberOffers[]` arrays, building the complete asset picture needed by downstream cancellation activities.

| Property | Value |
|----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CRM_GET_ASSET_COMPONENT_LIST` |
| Author | CHAYATORN-PC |
| Backend system | CRM (Siebel) — `CRMGetAssetComponentList` service |
| Fan-out scope | ParentOU Subscribers + ChildOU Subscribers |
| In PREPAID_CANCEL | Step 2, Parameter: STATUS=Active |
| Request event | `Events.OMConsumers.OMXFM.Request.CRM_GET_ASSET_COMPONENT_LIST` |
| Response RF | `RuleFunctions.OrderResponse.Response_CRM_GET_ASSET_COMPONENT_LIST` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | `5` | Standard FM request priority |
| forwardChain | `true` | Re-evaluates when working memory changes |
| Rule type | Fan-out Request | Sends one event per subscriber (ParentOU + ChildOU) |
| Source path | `Rules/OMConsumers/OMXFM/Request/Request_CRM_GET_ASSET_COMPONENT_LIST.rule` | |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order object; source of Customer hierarchy and order metadata |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process activity; drives rule firing and holds RequestCount |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to current process flow position |
| 2 | `orderCurrentActivity.ActivityID == "CRM_GET_ASSET_COMPONENT_LIST"` | Fires only for this specific FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CRM_GET_ASSET_COMPONENT_LIST"` | Double-check from order side |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Prevents double-firing |

---

## §5 — Execution Flow Diagram

```
1. Re-submit check → isActResub = (RequestCount > 0 && IsOrderResubmitted)
2. Load parameters: STATUS (GetActivityParameterValueFromKey), GET_FROM_CCBS, OLPRD_DB_FLAG (GetActivityParamValueFromKey)
3. Loop ParentOU[p] → Subscriber[ps]
   3a. Skip if already responded (CompletionStatus==2 for this refId)
   3b. Evaluate PreExecCheck XPath (if present)
   3c. Build CRM_GET_ASSET_COMPONENT_LIST event via XSLT
   3d. sendEventImmediate
   3e. Increment RequestCount (unless re-submit)
   3f. Log audit event (if AllowWriteLog)
4. Loop ChildOU[c] → Subscriber[cs] — same pattern; uses cSubRefId
5. Status update: if any sent → Status="1" + SendDataToDB; else SkipActivity("4")
6. Exception catch → HandleActivityException
```

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

The THEN block executes inside a try/catch and follows the standard OMXFM fan-out pattern.

> **Note:** Two different helper function names are used: `GetActivityParameterValueFromKey` (for STATUS) and `GetActivityParamValueFromKey` (for GET_FROM_CCBS, OLPRD_DB_FLAG). These are separate functions.

```java
String status = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "STATUS");
String getFromCCBS = RuleFunctions.Helpers.GetActivityParamValueFromKey(orderCurrentActivity, "GET_FROM_CCBS");
String olprdDbFlag = RuleFunctions.Helpers.GetActivityParamValueFromKey(orderCurrentActivity, "OLPRD_DB_FLAG");
```

---

## §7 — Data Extraction

| Parameter Key | Helper Function | Default | Usage |
|--------------|----------------|---------|-------|
| `STATUS` | GetActivityParameterValueFromKey | "Active" | Filter for asset components — in PREPAID_CANCEL: "Active" |
| `GET_FROM_CCBS` | GetActivityParamValueFromKey | (empty) | If "Y", adds `<GetFromCCBS>Y</GetFromCCBS>` to event header |
| `OLPRD_DB_FLAG` | GetActivityParamValueFromKey | "Y" | Passed to CRM as `olprdDBFlag` |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Called by all order types requiring CRM asset enrichment. In PREPAID_CANCEL fires at step 2 for all Mobile Prepaid subscribers. Response RF branches on STATUS:
- **STATUS=Active** (PREPAID_CANCEL) — enriches ResourceInfo and SubscriberOffers
- **STATUS=Inactive** — used by SIM renewal flows to find the most recent inactive SIM

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel / Destination | Protocol | Purpose |
|-----------|----------------------|----------|---------|
| [OUTBOUND] | OMXFM / CRM_GET_ASSET_COMPONENT_LIST | JMS | CRM asset component query per subscriber |
| [LOG] | OMXESB / Logger | JMS | Audit trail (REQ gated by AllowWriteLog; RES always) |

### §8.3 — Backend API Details

| System | Operation | Schema | Protocol | Correlation |
|--------|-----------|--------|----------|-------------|
| CRM (Siebel) | CRMGetAssetComponentList | `CRMGetAssetComponentList.xsd` | JMS/ESB | RefID ← subscriber RefId |

### §8.4 — BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `orderRequest.OrderData.Customer.ParentOU[].Subscriber[].AssetCrmId` | READ | Sent as `assetRowID` to CRM (only if not empty) |
| `orderRequest.OrderData.Customer.ParentOU[].Subscriber[].MSISDN` | READ | Used as `serviceId` variable (not sent in payload) |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Incremented per fan-out message sent |
| `sub.ResourceInfo[]` | WRITE (Response RF) | Populated with SIM/IMSI/MSISDN/PMATCHID/Equipment/PEID entries |
| `sub.SubscriberOffers[]` | WRITE (Response RF) | Populated with Price Plan/SOC/OFFER/Additional Offer entries |

### §8.5 — ExtendedInfo Fields

No ExtendedInfo fields are read in the request rule. The response RF creates `FE_OR_CCBS = "CRM"` on each SubscriberOffers entry it creates.

### §8.6 — Global Variable Dependencies

| Global Variable Path | Used for |
|---------------------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `OMX_OM/WritePayload` | Gates payload inclusion in audit log (both REQ and RES) |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | BE Source | Notes |
|-----------|----------|-------|
| `$orderRequest` | `orderRequest` | Full order concept |
| `$pSubRefId` | `pSubRefId` (ParentOU variant) | Subscriber RefId used as correlation ID |
| `$cSubRefId` | `cSubRefId` (ChildOU variant) | ChildOU Subscriber RefId |
| `$psub` / `$csub` | Subscriber concept instance | Source of AssetCrmId |
| `$getFromCCBS` | `getFromCCBS` param variable | Controls optional header field |
| `$status` | `status` param variable | Asset filter status |
| `$olprdDbFlag` | `olprdDbFlag` param variable | OLPRD DB flag |

### §9.2 — Event Container

Event extId: generated via `OMXUtils:generateTrackingID()`.

### §9.3 — JMS / Event Header Fields

| Field | Source |
|-------|--------|
| `JMSPriority` | `$orderRequest/OrderPriority` |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` |
| `OrderID` | `$orderRequest/OrderData/OrderID` |
| `RefID` | `$pSubRefId` or `$cSubRefId` — subscriber RefId |
| `OrderType` | `$orderRequest/OrderData/OrderType` |
| `GetFromCCBS` (optional) | `$getFromCCBS` — only emitted if value = "Y" |

### §9.4 — Payload Root

Namespace: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CRM/CRMGetAssetComponentList.xsd`
Root element: `<ns:CRMGetAssetComponentListRequest>`

### §9.5 — Conditional Fields

| Field | Condition | Value |
|-------|-----------|-------|
| `ns:assetRowID` | `$psub/AssetCrmId` exists | `$psub/AssetCrmId` |
| `GetFromCCBS` (header) | `$getFromCCBS = 'Y'` | `$getFromCCBS` |

### §9.6 — Core Payload Fields

| Element | Source / Logic | Default |
|---------|---------------|---------|
| `ns:assetRowID` | `sub.AssetCrmId` (from previous CRM_GET_LAST_ASSET_ROOT) | Omitted if blank |
| `ns:status` | STATUS activity parameter | "Active" |
| `ns:olprdDBFlag` | OLPRD_DB_FLAG activity parameter | "Y" |

### §9.7 — Complete Generated XML Example

```xml
<!-- ParentOU Variant -->
<event extId="OMX-20250720-001">
  <JMSPriority>4</JMSPriority>
  <JMSCorrelationID>OMX-TRK-20250720-001</JMSCorrelationID>
  <OrderID>1000001</OrderID>
  <RefID>SUB-REF-001</RefID>
  <OrderType>35041</OrderType>
  <!-- GetFromCCBS omitted: not "Y" in PREPAID_CANCEL -->
  <payload>
    <ns:CRMGetAssetComponentListRequest>
      <ns:assetRowID>1-ABCD1234</ns:assetRowID>
      <ns:status>Active</ns:status>
      <ns:olprdDBFlag>Y</ns:olprdDBFlag>
    </ns:CRMGetAssetComponentListRequest>
  </payload>
</event>
```

### §9.8 — XSLT Stylesheet Source

**Variant ①: ParentOU** — params: `$orderRequest`, `$pSubRefId`, `$getFromCCBS`, `$psub`, `$status`, `$olprdDbFlag`

```xml
<xsl:stylesheet version="1.0"
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/.../CRMGetAssetComponentList.xsd">
  <xsl:param name="orderRequest"/>    <!-- bound from BE: orderRequest concept -->
  <xsl:param name="pSubRefId"/>       <!-- bound from BE: ParentOU subscriber RefId -->
  <xsl:param name="getFromCCBS"/>     <!-- "Y" or empty -->
  <xsl:param name="psub"/>            <!-- bound from BE: ParentOU Subscriber instance -->
  <xsl:param name="status"/>          <!-- "Active" in PREPAID_CANCEL -->
  <xsl:param name="olprdDbFlag"/>     <!-- default "Y" if empty -->
  <xsl:template match="/">
    <createEvent><event>
      <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
      <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      <RefID><xsl:value-of select="$pSubRefId"/></RefID>  <!-- correlation key -->
      <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      <xsl:if test="$getFromCCBS = 'Y'">
        <GetFromCCBS><xsl:value-of select="$getFromCCBS"/></GetFromCCBS>
      </xsl:if>
      <payload>
        <ns:CRMGetAssetComponentListRequest>
          <xsl:if test="$psub/AssetCrmId">
            <ns:assetRowID><xsl:value-of select="$psub/AssetCrmId"/></ns:assetRowID>
          </xsl:if>
          <xsl:choose>
            <xsl:when test="string-length($status)>0">
              <ns:status><xsl:value-of select="$status"/></ns:status>
            </xsl:when>
            <xsl:otherwise>
              <ns:status>Active</ns:status>  <!-- default -->
            </xsl:otherwise>
          </xsl:choose>
          <xsl:choose>
            <xsl:when test="$olprdDbFlag != ''">
              <ns:olprdDBFlag><xsl:value-of select="$olprdDbFlag"/></ns:olprdDBFlag>
            </xsl:when>
            <xsl:otherwise>
              <ns:olprdDBFlag>Y</ns:olprdDBFlag>  <!-- default -->
            </xsl:otherwise>
          </xsl:choose>
        </ns:CRMGetAssetComponentListRequest>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**Variant ②: ChildOU** — identical structure; differs only in parameter name: `$cSubRefId` replaces `$pSubRefId` and `$csub` replaces `$psub`.

> Unlike CRM_GET_LAST_ASSET_ROOT (which had a nanoTime bug for ChildOU RefID), this rule correctly uses `cSubRefId` in both the BE variable (line 112) and the XSLT param. The ParentOU variant declares a `refId = nanoTime()` variable (line 62) but this is dead code — the XSLT uses `$pSubRefId` directly.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event @extId ← OMXUtils:generateTrackingID()                         [Always]
    ├── JMSPriority         ← $orderRequest/OrderPriority                 [Always]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId       [Always]
    ├── OrderID             ← $orderRequest/OrderData/OrderID             [Always]
    ├── RefID               ← $pSubRefId / $cSubRefId (correlation key)  [Always]
    ├── OrderType           ← $orderRequest/OrderData/OrderType           [Always]
    ├── GetFromCCBS         ← $getFromCCBS                               [Conditional: $getFromCCBS = 'Y']
    └── payload                                                           [Always]
        └── ns:CRMGetAssetComponentListRequest
            ├── ns:assetRowID   ← $psub/AssetCrmId                       [Conditional: AssetCrmId exists]
            ├── ns:status       ← $status                                 [Always, default: "Active"]
            └── ns:olprdDBFlag  ← $olprdDbFlag                           [Always, default: "Y"]
```

**Legend:** `[Always]` = unconditionally emitted; `[Conditional]` = inside xsl:if or xsl:choose; green/XPath = runtime value; orange/static = hardcoded default

---

## §11 — Audit Logging

| Phase | Gate | PROCESS_ID | AUDIT_TRACE |
|-------|------|-----------|-------------|
| Request | `AllowWriteLog(OrderType)` — conditional | `concat(pid, "_REQ")` | "Request Sent for CRM_GET_ASSET_COMPONENT_LIST" |
| Response | Always logged (no gate) | `concat(pid, "_RES")` | "Response received for CRM_GET_ASSET_COMPONENT_LIST" |

> **[LOW]** Response audit logging is unconditional while request logging uses `AllowWriteLog`. Asymmetry with request side.

---

## §12 — Activity Status Management

| Condition | Status Code | Action |
|-----------|-------------|--------|
| At least one request sent | "1" → PROCESSING | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All subscribers already responded | "4" → SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception thrown | ERROR | `HandleActivityException(...)` |

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
  RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 — Helper Functions Reference

| Function | Purpose | Notes |
|----------|---------|-------|
| `GetActivityParameterValueFromKey` | Reads STATUS parameter | Full name with "eter" |
| `GetActivityParamValueFromKey` | Reads GET_FROM_CCBS, OLPRD_DB_FLAG | Shorter name — different function! |
| `AllowWriteLog(OrderType)` | Gates request audit logging | Returns true for specific order types |
| `GetXMLForSubscriber` | Serializes subscriber to XML for PreExecCheck | ParentOU variant |
| `GetXMLForSubscriberInChildOU` | Serializes ChildOU subscriber to XML | Includes parent OU RefId |
| `SkipActivity` | Marks activity as skipped, advances process | Called with "4" → skip status |
| `HandleActivityException` | Sets activity error state | Last param "" = no extra message |
| `SendDataToDB` | Persists order state to database | Called after status "1" |
| `GetActivityStatusString` | Maps status code to string | Called with "1" → PROCESSING |
| `BRMS.IsBlankOrStringNull` | Null/blank check (Response RF) | Used to guard assetRowID checks |

---

## §15 — Function Dependency Tree

```text
Request_CRM_GET_ASSET_COMPONENT_LIST (rule)
├── RuleFunctions.Helpers.GetActivityParameterValueFromKey [STATUS]
├── RuleFunctions.Helpers.GetActivityParamValueFromKey [GET_FROM_CCBS, OLPRD_DB_FLAG]
├── RuleFunctions.Helpers.GetXMLForSubscriber (ParentOU)
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU (ChildOU)
├── Event.Ext.sendEventImmediate [CRM_GET_ASSET_COMPONENT_LIST event]
├── RuleFunctions.Helpers.AllowWriteLog
│   └── Event.Ext.sendEventImmediate [OMXESB Logger REQ]
├── RuleFunctions.Helpers.GetActivityStatusString("1")
├── RuleFunctions.Helpers.SendDataToDB
└── RuleFunctions.Helpers.HandleActivityException (on error)

Response_CRM_GET_ASSET_COMPONENT_LIST (rulefunction)
├── Instance.createInstance [Concepts.FM.Base.ResponseBase]
├── XPath.evalAsInt [count assetComponentList]
├── XPath.evalAsString [assetRowID, productType, serialNo, effectiveDate, etc.]
├── XPath.evalAsBoolean [FE source guard, PEID serialNo format check]
├── Instance.createInstance [Concepts.OrderRequest.OrderElements.ResourceInfo] (×multiple)
├── Instance.createInstance [Concepts.OrderRequest.OrderElements.SubscriberOffers] (×multiple)
├── DateTime.parseString [effectiveDate, expiryDate]
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull
├── Event.Ext.sendEventImmediate [OMXESB Logger RES]
└── XPath.evalAsInt [count successResponseCount for fan-in]
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Fields |
|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.OrderID, OrderData.OrderType, OrderData.OMXTrackingId, OrderPriority, ProcessFlow.NextActivityName, OrderData.Customer.ParentOU[].Subscriber[], IsOrderResubmitted |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], Parameter[], PreExecCheck |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, AssetCrmId, ResourceInfo[], SubscriberOffers[] |
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |
| `Concepts.OrderRequest.OrderElements.ResourceInfo` | ResourceName, ValuesArray, Source |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | EffectiveDate, ExpirationDate, OfferName, ServiceType, AssetCompCrmId, ExtendedInfo[] |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Retrieve all CRM asset components for a subscriber filtered by status (Active / Inactive) |
| R2 | Map CRM productType to OMX ResourceName: SIM Card→SIM, Equipment→IMEI, IMSI→IMSI, MSISDN→MSISDN, PMATCHID→PMATCHID, PEID→PEID |
| R3 | Strip "MSISDN-" prefix from serialNo when productType=MSISDN |
| R4 | When POPULATE_OLD_RESOURCE="Y", also create OLD_SIM, OLD_IMSI, OLD_PMATCHID, OLD_PEID entries |
| R5 | Map Price Plan/SOC/OFFER/Additional Offer/SOC/OFFER(TOPPING) to SubscriberOffers with ServiceType codes 80/85/85/90 |
| R6 | Mark all CRM-sourced offers with ExtendedInfo FE_OR_CCBS="CRM" |
| R7 | Back-populate AssetCompCrmId and EffectiveDate onto existing FE/BRMS_REMOVE offers with matching OfferName |
| R8 | For Inactive status calls: find most recently effective SIM Card and add as ResourceInfo.Source="CRM" |
| R9 | PEID serialNo: preserve as-is if contains underscore; else concat(serialNo+"_"+assetRowID) |
| R10 | Skip adding resources that already exist with Source="FE" (FE data takes precedence over CRM) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Dead code variable `refId = nanoTime()` in ParentOU block (line 62) — unused; XSLT uses `$pSubRefId` directly | [LOW] | Remove unused variable |
| Large commented-out `CRM_CREATE_UPDATE_SR` event block in ChildOU section — copy-paste dead code | [LOW] | Remove to reduce maintenance risk |
| Two different parameter helper functions: `GetActivityParameterValueFromKey` vs `GetActivityParamValueFromKey` — inconsistent API | [MEDIUM] | Standardise on one helper function name |
| Response audit always logs (no AllowWriteLog gate) — asymmetric with request logging | [LOW] | Apply consistent log gating |
| Commented-out MSISDN ResourceInfo block (lines 98-100, 188-191) — removed feature still in code | [LOW] | Remove dead code in migration |
| Complex SubscriberOffers back-population loop (O(n²)) — iterates all offers to find FE/BRMS matches | [MEDIUM] | Use indexed lookup (map by OfferName) in modernised implementation |
| No FE source guard for MSISDN resource in ParentOU (strips "MSISDN-" prefix) — ChildOU has no prefix stripping | [MEDIUM] | Verify MSISDN serialNo format consistency in CRM; apply uniform stripping |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author CHAYATORN-PC
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CRM_GET_ASSET_COMPONENT_LIST {
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
    orderCurrentActivity.ActivityID == "CRM_GET_ASSET_COMPONENT_LIST";
    orderRequest.ProcessFlow.NextActivityID == "CRM_GET_ASSET_COMPONENT_LIST";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
      String chkXPath = nextAct.PreExecCheck;
      boolean isSkipped = true;
      String status = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "STATUS");
      String getFromCCBS = RuleFunctions.Helpers.GetActivityParamValueFromKey(orderCurrentActivity, "GET_FROM_CCBS");
      String olprdDbFlag = RuleFunctions.Helpers.GetActivityParamValueFromKey(orderCurrentActivity, "OLPRD_DB_FLAG");

      /*** Begin ParentOU ***/
      for (int p = 0; p < pOuLen; p++) {
        /*** Begin ParentOU Subscriber ***/
        for (int ps = 0; ps < pSubLen; ps++) {
          // reqSuccess guard and PreExecCheck gate omitted for brevity
          String serviceId = psub.MSISDN;
          String refId = String.valueOfLong(System.nanoTime()); // [LOW] unused variable — XSLT uses $pSubRefId
          Events.OMConsumers.OMXFM.Request.CRM_GET_ASSET_COMPONENT_LIST reqEvent =
            Event.createEvent("xslt://{{/Events/.../CRM_GET_ASSET_COMPONENT_LIST}}");
            // → See §9.8 Variant ① (params: orderRequest, pSubRefId, getFromCCBS, psub, status, olprdDbFlag)
            // → Payload: CRMGetAssetComponentListRequest(assetRowID?, status, olprdDBFlag)
          Event.Ext.sendEventImmediate(reqEvent);
          isSkipped = false;
          if (!isActResub) orderCurrentActivity.RequestCount++;
          if (RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
            Event.Ext.sendEventImmediate(/* OMXESB Logger REQ event */);
          }
        }
        /*** Begin ChildOU ***/
        for (int c = 0; c < cOuLen; c++) {
          for (int cs = 0; cs < cSubLen; cs++) {
            String serviceId = csub.MSISDN;
            String refId = cSubRefId; // ChildOU correctly uses cSubRefId
            // [Note] Large commented-out CRM_CREATE_UPDATE_SR block omitted (dead code from copy-paste)
            Events.OMConsumers.OMXFM.Request.CRM_GET_ASSET_COMPONENT_LIST reqEvent =
              Event.createEvent("xslt://{{/Events/.../CRM_GET_ASSET_COMPONENT_LIST}}");
              // → See §9.8 Variant ② (params: orderRequest, cSubRefId, getFromCCBS, csub, status, olprdDbFlag)
            Event.Ext.sendEventImmediate(reqEvent);
            isSkipped = false;
            if (!isActResub) orderCurrentActivity.RequestCount++;
            if (RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
              Event.Ext.sendEventImmediate(/* OMXESB Logger REQ event */);
            }
          }
        }
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

`Response_CRM_GET_ASSET_COMPONENT_LIST` processes each CRM response event, identifies the matching subscriber by `RefID`, and enriches their concept with every asset component returned. The enrichment branches on the `STATUS` parameter:

- **STATUS ≠ "Inactive"** (normal path, PREPAID_CANCEL) — populates `ResourceInfo[]` with physical resources and `SubscriberOffers[]` with commercial offers
- **STATUS = "Inactive"** (SIM renewal path) — finds the most recently effective SIM Card

The RF handles both ParentOU and ChildOU subscribers identically.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order; subscriber hierarchy to enrich |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CRM_GET_ASSET_COMPONENT_LIST` | CRM reply event; contains assetComponentList in payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity state; receives ResponseBase; drives fan-in completion |

### §19.3 — ResponseBase Concept Construction

```text
createObject (ResponseBase)
└── object @extId ← OMXUtils:generateTrackingID()          [Always]
    ├── ResponseCode    ← $eventResponse/ResponseCode       [Conditional: if ResponseCode present]
    ├── ResponseMessage ← $eventResponse/ResponseMsg        [Conditional: if ResponseMsg present]
    ├── CompletionStatus← $eventResponse/CompletionStatus   [Conditional: if CompletionStatus present]
    └── ReferenceId     ← $eventResponse/RefID             [Conditional: if RefID present, used for subscriber match]
```

### §19.4 — Subscriber Enrichment Logic (STATUS ≠ Inactive)

For each `assetComponentList` item where `assetRowID` is not blank:

| productType | ResourceName | ValuesArray (serialNo) | OLD_ created if POPULATE_OLD_RESOURCE=Y |
|-------------|-------------|----------------------|----------------------------------------|
| SIM Card | SIM | serialNo (strip "MSISDN-" prefix if present) | OLD_SIM |
| IMSI | IMSI | serialNo | OLD_IMSI |
| MSISDN | MSISDN | serialNo (strip "MSISDN-" prefix) | — |
| PMATCHID | PMATCHID | serialNo | OLD_PMATCHID |
| Equipment | IMEI | serialNo | — |
| PEID | PEID | if serialNo contains "_": as-is; else concat(serialNo+"_"+assetRowID) | OLD_PEID (same logic) |
| Price Plan | — (SubscriberOffers) | ServiceType="80", OfferName←partNum, FE_OR_CCBS="CRM" | — |
| SOC/OFFER, Additional Offer | — (SubscriberOffers) | ServiceType="85", OfferName←partNum, FE_OR_CCBS="CRM" | — |
| SOC/OFFER(TOPPING) | — (SubscriberOffers) | ServiceType="90", OfferName←partNum, FE_OR_CCBS="CRM" | — |

> **FE/BRMS cross-population:** After creating each SubscriberOffers entry, the RF loops all existing offers to find any with `FE_OR_CCBS="FE"` or `="BRMS_REMOVE"` and the same OfferName, then updates their `AssetCompCrmId` and `EffectiveDate` (if null).

**Inactive SIM handling (STATUS = Inactive):** Scans all asset components for `productType="SIM Card"`, tracks the most recently effective one by comparing parsed `effectiveDate` values. If no FE SIM exists, adds a ResourceInfo entry for the most recent inactive SIM with `Source="CRM"`.

### §19.5 — Fan-in Completion

| Element | Value |
|---------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Return "true" | All parallel CRM calls returned a "000"-suffix response code |
| Return "false" | Waiting for remaining responses |

### §19.6 — Response Audit Logging

```text
createEvent (Logger)
└── event
    ├── ESBUUID          ← $orderRequest/OrderData/OMXTrackingId          [Conditional: if OMXTrackingId present]
    ├── PROCESS_ID       ← concat($pid, "_RES")                           [Always]
    ├── COMPONENT_NAME   ← $globalVariables/OMX_COMMON/Component_Name/OMX_CEP   [Always]
    ├── OPERATION_NAME   ← "CRM_GET_ASSET_COMPONENT_LIST" (static)        [Always]
    ├── TARGET_SYSTEM    ← $globalVariables/OMX_COMMON/Component_Name/OMX_FM    [Always]
    ├── LOG_LEVEL        ← $globalVariables/.../MSG_LOG_LEVEL/INFO         [Always]
    ├── AUDIT_TRACE      ← "Response received for CRM_GET_ASSET_COMPONENT_LIST" [Always]
    ├── AUDIT_TS         ← tib:format-dateTime(current-dateTime())         [Always]
    └── payload/ns:ServicePayload ← copy-of $eventResponse                [Conditional: WritePayload="true"]
```

### §19.7 — Response XSLT Source (ResponseBase)

```xml
<xsl:stylesheet version="1.0">
  <xsl:param name="eventResponse"/>  <!-- bound from BE: CRM response event -->
  <xsl:template match="/">
    <createObject><object>
      <xsl:attribute name="extId"><xsl:value-of select="ns:generateTrackingID()"/></xsl:attribute>
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

> A commented-out alternative ResponseBase XSLT variant (using `$eventResponse/@extId` as the object extId) is present at line 16 of the rulefunction but inactive. The active variant uses `ns:generateTrackingID()`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
