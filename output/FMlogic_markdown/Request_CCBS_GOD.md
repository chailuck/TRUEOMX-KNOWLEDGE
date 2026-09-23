# Request_CCBS_GOD

CCBS Get Offer Details (GOD) — Batch Product Catalog Lookup with Full Offer Enrichment

---

## §1 — Overview & Purpose

This rule fires when the order reaches `ActivityID = CCBS_GOD` and status `WAITING`. It queries the CCBS Product Catalog service (**Get Offer Details**) for every unique SOC code found in the current order — Agreement offers, Subscriber offers, and their related offer arrays — across all ParentOU and ChildOU levels.

> **Key architectural distinction:** Unlike the ASRM rules (one request per subscriber), CCBS_GOD sends exactly **one** batch JMS request containing all unique SOC codes. `RequestCount` is always 1. The response handler processes the returned `PCOfferInfoArray` and writes product catalog details (SocProperties, ServiceLevel, OfferType, Name, RelatedOffers) back to every matching position in the working memory concept tree.

> **SOC collection scope:**
> - `Agreement.Offers[j].Soc` — for each ParentOU and ChildOU agreement
> - `Subscriber.SubscriberOffers[k].Soc` — with per-offer PreExecCheck
> - `SubscriberOffers[k].RelatedOffersArray[l].Soc` — added unconditionally when parent offer passes
>
> All SOC codes deduplicated using `Collections.List.createArrayList()` + `Collections.contains()`.

> ⚠ **Response handler is complex:** The rulefunction `Response_CCBS_GOD` always returns `"true"` (no fan-in counting). It performs extensive data enrichment including contract field provisioning for C15 orders (OrderType=48) and inserts ParameterInfo records for TR_CONTRACT_* fields.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_CCBS_GOD` |
| Full Path | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GOD` |
| Priority | 5 |
| forwardChain | true |
| Rule Type | Batch Request Dispatch — collects all unique SOC codes, sends one CCBS GOD call |
| Author | awalia-t420 |
| Backend System | CCBS — Billing/CRM Product Catalog |
| Operation | GetOfferDetails (Product Catalog query) |
| Fan-out pattern | Single batch call (not fan-out per subscriber) |

---

## §3 — Working Memory — Declared Objects

| Variable | Type Path | Role |
|----------|-----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Master order — full customer hierarchy traversed to collect SOC codes |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current step — PreExecCheck, RequestCount, Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity to order execution point |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_GOD"` | Targets only CCBS_GOD activities |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_GOD"` | Order-level double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires on fresh/ready activity |

---

## §5 — Execution Flow

1. **Global PreExecCheck** — if `nextAct.PreExecCheck` exists, serialize full orderRequest via `Instance.serializeUsingDefaults(orderRequest)` and run XPath. If result is not "true", skip entire activity.
2. **SOC Collection — ParentOU Agreement Offers** — for each ParentOU[i].Agreement.Offers[j]: run per-offer PreExecCheck via `GetXMLForAgreementOffer`; if passes + not already in list → `Collections.add(arrLstSOCs, currSoc)`
3. **SOC Collection — ParentOU SubscriberOffers** — for each Subscriber[j].SubscriberOffers[k]: run PreExecCheck via `GetXMLForSubscriberOffer`; if passes → add to list; then unconditionally scan `RelatedOffersArray[l]` → add related Soc (no PreExecCheck on related)
4. **SOC Collection — ChildOU** — same as steps 2–3 for ChildOU Agreement and ChildOU Subscriber offers
5. **Dispatch** — if `socIDs` non-empty: send one `CCBS_GOD` JMS event with all SOC codes in `GetOfferDetailsArray` payload; set `RequestCount=1`
6. **Status Update** — if sent → IN_PROGRESS; if no SOCs → SkipActivity("4") → SKIPPED
7. **Exception** — catch → HandleActivityException → ERROR

---

## §6 — Rule Action (THEN) — Key Logic

### SOC Deduplication

```java
Object arrLstSOCs = Collections.List.createArrayList();
// For each offer source:
if(!Collections.contains(arrLstSOCs, currSoc) && String.equals(chkRes, "true")) {
    Collections.add(arrLstSOCs, currSoc);
}
// RelatedOffers added without PreExecCheck (after parent offer passes):
if(!Collections.contains(arrLstSOCs, currSoc)) {
    Collections.add(arrLstSOCs, currSoc);
}
```

### Dispatch Gate — Non-Empty SOC List

```java
Object[] socIDs = Collections.toArray(arrLstSOCs);
if(socIDs != null && Collections.size(arrLstSOCs) > 0) {
    Events.OMConsumers.OMXFM.Request.CCBS_GOD reqEvent = Event.createEvent(
        "xslt://{{/Events/OMConsumers/OMXFM/Request/CCBS_GOD}}"
        /* XSLT: builds GetOfferDetailsArray with one GetOfferDetailsRequest per SOC — see §9.8 */);
    Event.Ext.sendEventImmediate(reqEvent);
    if(!isActResub) orderCurrentActivity.RequestCount++;  // always = 1
    isSkipped = false;
}
```

---

## §7 — Data Extraction — SOC Collection Sources

### PreExecCheck Helper Used by Source

| Source | PreExecCheck Helper | Adds Related Offers? |
|--------|--------------------|--------------------|
| ParentOU Agreement Offers | `GetXMLForAgreementOffer(orderRequest, agreement.RefId, currSoc)` | No |
| ParentOU SubscriberOffers | `GetXMLForSubscriberOffer(orderRequest, subscriber.RefId, currSoc)` | **Yes — unconditional** |
| ChildOU Agreement Offers | `GetXMLForAgreementOfferInChildOU(orderRequest, agreement.RefId, currSoc, pouRefId)` | No |
| ChildOU SubscriberOffers | `GetXMLForSubscriberOfferInChildOU(orderRequest, subscriber.RefId, currSoc, pouRefId)` | **Yes — unconditional** |

> **RelatedOffersArray inclusion rule:** When a SubscriberOffer passes its PreExecCheck and is added to the SOC list, its `RelatedOffersArray[l].Soc` values are immediately added without re-checking the PreExecCheck. This ensures related offers are always included in the GetOfferDetails batch alongside their parent offer.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

| Scenario | Effect |
|----------|--------|
| Any order with Agreement/SubscriberOffers | SOC codes collected; one CCBS call |
| No qualifying SOCs (all filtered by PreExecCheck) | Activity SKIPPED |
| OrderType=48 (C15) | Response handler creates contract ParameterInfo records (TR_CONTRACT_* fields) |
| `OrderData.CES` present | Included in request JMS header |
| `OrderData.ExtendedInfo[OFFER_INCLUSION]/Value='Y'` | RelatedOffers included in response concept construction |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel URI | Destination | Purpose |
|-----------|-------------|-------------|---------|
| [OUTBOUND] | `/Channels/OMXFMConnectionRequest` | `CCBS_GOD` | GetOfferDetails batch query |
| [OUTBOUND] | `/Channels/LogConnection` | `AuditLog` | Request audit (CCBS_GOD static name) |

### §8.3 — Backend API Details

| Attribute | Value |
|-----------|-------|
| System | CCBS — Amdocs CSM 3G Product Catalog |
| Operation | GetOfferDetails (batch) |
| Request schema | `http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/ProductCatalogServices/Schema.xsd6` |
| Request element | `ns:GetOfferDetailsArray` → N × `ns:GetOfferDetailsRequest` → `ns:code` |
| Response element | `ns:PCOfferInfoArray` → N × `ns:PCOfferInfo` |
| Response concept | `Concepts.FM.Response.GetOfferDetailsRes` |
| Fan-out | None — single batch request; RequestCount always = 1 |

### §8.4 — BE Working Memory Dependencies

| Field / Path | Direction | Phase | Purpose |
|-------------|-----------|-------|---------|
| `ParentOU[i].Agreement.Offers[j].Soc` | READ | Request | SOC code source |
| `Subscriber[j].SubscriberOffers[k].Soc` | READ | Request | SOC code source |
| `SubscriberOffers[k].RelatedOffersArray[l].Soc` | READ | Request | Related SOC source |
| `orderCurrentActivity.Status` | WRITE | Request | Set IN_PROGRESS or SKIPPED |
| `orderCurrentActivity.RequestCount` | WRITE | Request | Always set to 1 |
| `Agreement.Offers[k].SocProperties / RCIndicator / ServiceLevel / ServiceType / OfferName` | WRITE | Response | Written from GOD response per matching SOC |
| `SubscriberOffers[l].SocProperties / RCIndicator / ServiceLevel / ServiceType / OfferName` | WRITE | Response | Written from GOD response per matching SOC |
| `SubscriberOffers[l].ParameterInfo[]` | WRITE | Response | TR_CONTRACT_* fields added for C15 orders |
| `SubscriberOffers[l].ExtendedInfo[]` | WRITE | Response | TR_OFFER_GROUP added for FE/5G offers |
| `RelatedOffersArray[iRelOffer].SocProperties` | WRITE | Response | Written if currently blank |
| `Concepts.OM.LogicalDate.LogicalDate` | READ | Response | Used for TR_ACTUAL_CONTRACT_START_DATE and TR_ORIG_CONTRACT_EXPIRE_DATE computation |

### §8.5 — ExtendedInfo / Special Fields

| Field | Source | Purpose |
|-------|--------|---------|
| `OrderData.ExtendedInfo[Name="OFFER_INCLUSION"]/Value` | orderRequest | If absent or ='Y': include RelatedOffers in GetOfferDetailsRes concept |
| `OrderData.CES` | orderRequest | Forwarded in JMS header if present |
| `offer.ExtendedInfo[Name="FE_OR_CCBS"]/Value` | SubscriberOffer | If ='FE': triggers TR_OFFER_GROUP extraction and write-back |

### §8.6 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Include User/Password in request |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL value |
| `OMX_OM/WritePayload` | Include GetOfferDetailsArray in audit payload |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding (Request)

| Parameter | Bound From | Notes |
|-----------|-----------|-------|
| `$orderRequest` | Working memory concept | Full order request tree |
| `$globalVariables` | BE global variables | Credential gate, logging config |
| `$socIDs` | `Collections.toArray(arrLstSOCs)` | Array of unique SOC strings — iterated in XSLT as `$socIDs/elements` |

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | If OrderPriority exists |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | If OMXTrackingId exists |
| `OrderID` | `$orderRequest/OrderData/OrderID` | If OrderID exists |
| `UserName` | `$orderRequest/OrderData/User` | IsEnableUserPass='true' AND User exists |
| `PassWord` | `$orderRequest/OrderData/Password` | IsEnableUserPass='true' AND Password exists |
| `OrderType` | `$orderRequest/OrderData/OrderType` | If OrderType exists |
| `CES` | `$orderRequest/OrderData/CES` | **New vs ASRM rules:** If CES field exists |

### §9.7 — Complete Generated XML Example

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20260723-001</JMSCorrelationID>
    <OrderID>ORD-12345</OrderID>
    <OrderType>1</OrderType>
    <CES>TH_CES</CES>
    <payload>
      <ns:GetOfferDetailsArray
        xmlns:ns="http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/ProductCatalogServices/Schema.xsd6">
        <ns:GetOfferDetailsRequest>
          <ns:code>PP_TRUE_5G_UNLIMIT</ns:code>
        </ns:GetOfferDetailsRequest>
        <ns:GetOfferDetailsRequest>
          <ns:code>PP_TRUE_DATA_20GB</ns:code>
        </ns:GetOfferDetailsRequest>
        <!-- … one per unique SOC -->
      </ns:GetOfferDetailsArray>
    </payload>
  </event>
</createEvent>
```

### §9.8 — XSLT Stylesheet Source (Request)

```xml
<xsl:stylesheet
  xmlns:ns="http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/ProductCatalogServices/Schema.xsd6"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="globalVariables"/>
  <xsl:param name="socIDs"/>  <!-- Object[] of unique SOC codes, iterable as $socIDs/elements -->

  <xsl:template match="/">
    <createEvent><event>
      <xsl:if test="$orderRequest/OrderPriority">
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderID">
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      </xsl:if>
      <!-- Credential gate: UserName/PassWord if IsEnableUserPass='true' -->
      <xsl:if test="$orderRequest/OrderData/OrderType">
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/CES">
        <CES><xsl:value-of select="$orderRequest/OrderData/CES"/></CES>
      </xsl:if>
      <payload>
        <ns:GetOfferDetailsArray>
          <xsl:for-each select="$socIDs/elements">
            <ns:GetOfferDetailsRequest>
              <ns:code><xsl:value-of select="."/></ns:code>
            </ns:GetOfferDetailsRequest>
          </xsl:for-each>
        </ns:GetOfferDetailsArray>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy (Request)

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                  [Conditional: if OrderPriority exists]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId        [Conditional]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID              [Conditional]
    ├── UserName                 ← $orderRequest/OrderData/User                 [Credential-gated: IsEnableUserPass='true']
    ├── PassWord                 ← $orderRequest/OrderData/Password             [Credential-gated: IsEnableUserPass='true']
    ├── OrderType                ← $orderRequest/OrderData/OrderType            [Conditional]
    ├── CES                      ← $orderRequest/OrderData/CES                  [Conditional — new vs ASRM rules]
    └── payload
        └── ns:GetOfferDetailsArray                                              [Always]
            └── ns:GetOfferDetailsRequest                                        [Repeated: xsl:for-each $socIDs/elements]
                └── ns:code          ← . (current element of $socIDs/elements)  [Always]
```

**Legend:**
- Green = XPath source from working memory
- `[Always]` — unconditional element
- `[Conditional]` — inside `xsl:if`
- `[Repeated]` — inside `xsl:for-each`
- `[Credential-gated]` — behind IsEnableUserPass

---

## §11 — Audit Logging

**Request audit** — `OPERATION_NAME` is the static string `"CCBS_GOD"`. `AUDIT_TRACE` is `"Request Sent for CCBS_GOD"`. Payload includes `copy-of($reqEvent/payload/ns1:GetOfferDetailsArray)` when WritePayload=true.

**Response audit** (in rulefunction) — `PROCESS_ID` uses `_RES` suffix. `AUDIT_TRACE` is `"Response received for CCBS_GOD"`. Payload includes full `copy-of($eventResponse)` when WritePayload=true.

---

## §12 — Activity Status Management

| Trigger | Code | Status | Method |
|---------|------|--------|--------|
| Rule fires | 0 | WAITING | Pre-condition |
| SOC list non-empty — request sent | 1 | IN_PROGRESS | `GetActivityStatusString("1", false)` |
| No SOCs collected or global PreExecCheck fails | 4 | SKIPPED | `SkipActivity(…, "4")` |
| Exception caught in request rule | 3 | ERROR | `HandleActivityException` |
| Response: PCOfferInfoArray absent | 3 | ERROR | `throw Exception("DATA_ISSUE", …)` |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_GOD (rule)
├── Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")
├── Instance.serializeUsingDefaults(orderRequest)              [global PreExecCheck]
├── XPath.execute("/(PreExecCheck)", sXML, ns)
├── Collections.List.createArrayList()
├── SOC collection loop (ParentOU → Agreement + Subscriber + ChildOU):
│   ├── RuleFunctions.Helpers.GetXMLForAgreementOffer(...)
│   ├── RuleFunctions.Helpers.GetXMLForSubscriberOffer(...)
│   ├── RuleFunctions.Helpers.GetXMLForAgreementOfferInChildOU(...)
│   ├── RuleFunctions.Helpers.GetXMLForSubscriberOfferInChildOU(...)
│   ├── XPath.execute("/(PreExecCheck)", sXML, ns)
│   └── Collections.contains(arrLstSOCs, currSoc)
│       └── Collections.add(arrLstSOCs, currSoc)
├── Collections.toArray(arrLstSOCs)
├── Collections.size(arrLstSOCs)
├── Event.createEvent(xslt://CCBS_GOD)
├── Event.Ext.sendEventImmediate(reqEvent)
├── RuleFunctions.Helpers.AllowWriteLog(orderType)
├── Event.createEvent(xslt://Logger)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)
└── RuleFunctions.Helpers.HandleActivityException(...)

Response_CCBS_GOD (rulefunction)
├── XPath.evalAsBoolean("not(exists($eventResponse/payload/PCOfferInfoArray))")
│   └── throw Exception("DATA_ISSUE", "No offer detail returned.")
├── XPath.executeXPathWithEvent("$var//ns0:PCOfferInfo", eventResponse, ns)
├── Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")
├── Per PCOfferInfo:
│   ├── Instance.createInstance(xslt://GetOfferDetailsRes)   [per GOD result entry]
│   ├── currActivity.Response[n] = godRes
│   ├── Write-back loops (ParentOU Agreement / SubscriberOffers / ChildOU Agreement / ChildOU Subscriber):
│   │   ├── offer.SocProperties = godRes.SocProperties
│   │   ├── offer.RCIndicator = godRes.RcIndicator
│   │   ├── offer.ServiceLevel = OMXUtils.asciiCodeToText(godRes.ServiceLevel)
│   │   ├── offer.ServiceType (if blank)
│   │   ├── offer.OfferName (if blank)
│   │   ├── offer.RelatedOffersArray[iRelOffer].SocProperties (if blank)
│   │   └── Contract provisions (OrderType=48 + TR_CONTRACT_IND=Y):
│   │       ├── Instance.createInstance(xslt://SubscriberParameterInfo) × 7
│   │       │   (TR_CONTRACT_NUMBER, TR_ACTUAL_CONTRACT_START_DATE,
│   │       │    TR_GENERATE_CHARGE_YES_NO, TR_CONTRACT_TERM, TR_CONTRACT_FEE,
│   │       │    TR_ORIG_CONTRACT_EXPIRE_DATE, TR_CONTRACT_REMARK)
│   │       └── offer.ParameterInfo[n] = subParam
│   └── TR_OFFER_GROUP write-back (FE or ServiceType 80/86):
│       └── Instance.createInstance(xslt://SubscriberOffersExtendedInfo)
│           └── offer.ExtendedInfo[n] = subsOfferExtended
├── RuleFunctions.Helpers.AllowWriteLog(orderType)
├── Event.createEvent(xslt://Logger)
└── return "true"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Collect unique SOC codes from Agreement.Offers, SubscriberOffers (with per-offer PreExecCheck), and RelatedOffersArray (without PreExecCheck).
- **R2** — Deduplicate SOC codes before sending — one CCBS GetOfferDetails call for the entire order.
- **R3** — Include CES field in request header if present.
- **R4** — Response handler must match GOD response back to ALL positions in the concept tree (Agreement, Subscriber, ChildOU levels) and write SocProperties, ServiceLevel, ServiceType, OfferName, RCIndicator.
- **R5** — For C15 orders (OrderType=48) where TR_CONTRACT_IND=Y in SocProperties, inject 7 ParameterInfo records into the offer with contract field values parsed from SocProperties semicolon-delimited format.
- **R6** — TR_ORIG_CONTRACT_EXPIRE_DATE computed as: LogicalDate + TR_CONTRACT_TERM months; or "2099-01-01 00:00:00" if TR_CONTRACT_TERM=0.
- **R7** — For FE offers or ServiceType 80/86, extract TR_OFFER_GROUP from SocProperties and append to offer.ExtendedInfo[].
- **R8** — Validate response contains PCOfferInfoArray; throw DATA_ISSUE exception if absent.
- **R9** — Always return "true" (no fan-in counting). RequestCount is always 1.
- **R10** — RelatedOffers included in GetOfferDetailsRes concept only when OFFER_INCLUSION=Y or absent (default include).

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Response write-back loops are O(n²) — for each GOD result, re-scans all offers to find matches | [HIGH] | In migration, build a SOC → position index map before the write-back phase |
| Contract field parsing from SocProperties uses fragile substring-before/after on semicolon format | [HIGH] | Use a proper key=value parser; validate that SocProperties always ends with ";" |
| LogicalDate concept must exist in BE working memory before this rule fires | [MEDIUM] | Ensure LogicalDate concept initialized at order start; migration must provide equivalent date injection |
| OMXUtils.asciiCodeToText for ServiceLevel decoding | [MEDIUM] | Port or replicate this ASCII-to-text conversion in the migration service |
| OFFER_INCLUSION default-include behavior (absent = include) | [LOW] | Migration must implement the "absent or Y → include" default rather than "absent → exclude" |

---

## §19 — Response Message Rule

### §19.1 — Overview

`RuleFunctions.OrderResponse.Response_CCBS_GOD` — significantly more complex than ASRM response rules. Instead of a simple fan-in count, it:

1. Validates response contains `PCOfferInfoArray`
2. Iterates each `PCOfferInfo` → creates one `GetOfferDetailsRes` concept per SOC
3. Writes back 5+ fields to every matching position in the order hierarchy
4. Optionally provisions C15 contract ParameterInfo fields (7 params)
5. Optionally writes TR_OFFER_GROUP to ExtendedInfo
6. Sends response audit log
7. Always returns `"true"`

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order hierarchy — written back with GOD data |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_GOD` | CCBS response — contains PCOfferInfoArray |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; extId used for GOD concept naming |

### §19.3 — GetOfferDetailsRes Concept Fields (from XSLT)

| Field | Source XPath | Condition |
|-------|-------------|-----------|
| extId | `concat("GODOF:", OMXTrackingId, ":", activityStepId, ":", ns:Code)` | Always |
| ResponseCode | `../../../ResponseCode` | If exists (3 levels up = event root) |
| ResponseMessage | `../../../ResponseMsg` | If exists |
| CompletionStatus | `../../../CompletionStatus` | If exists |
| ReferenceId | `../../../RefID` | If exists |
| BusinessEntityId | `ns:BusinessEntityId` | If exists |
| Code | `ns:Code` | If exists |
| Currency | `ns:Currency` | If exists |
| Description / Name / OfferType / ProductType / ServiceLevel / SocProperties | `ns:<field>` | If exists |
| DiscountPlans / PunishmentLevels | `xsl:for-each ns:DiscountPlans / ns:PunishmentLevels` | Repeated elements |
| Duration / DurationUom / DurationCalculationLevel | `ns:Duration / ns:DurationUom / …` | If exists |
| RelatedOffers | `xsl:for-each ns:RelatedOffers` | Conditional: `count(OFFER_INCLUSION)=0 OR OFFER_INCLUSION/Value='Y'` |

### §19.4 — Response Completion

```java
// No fan-in count. GOD always sends one request, response always completes immediately.
return "true";  // unconditional
```

**Success criteria:** Always `"true"` — this FM uses a single batch call so there is no fan-in count. The caller moves the activity to COMPLETED unconditionally (assuming no DATA_ISSUE exception).

### §19.5 — C15 Contract Field Provisioning (OrderType=48, TR_CONTRACT_IND=Y)

> **When triggered:** `OrderType=48` AND `SocProperties` contains `TR_CONTRACT_IND=Y;` AND the offer's `FE_OR_CCBS` ExtendedInfo != 'FE' (unless ServiceType is 80 or 86).
>
> **7 ParameterInfo records created and populated from SocProperties:**
> - `TR_CONTRACT_NUMBER` — from SocProperties; defaults to "-" if blank
> - `TR_ACTUAL_CONTRACT_START_DATE` — LogicalDate formatted "yyyy-MM-dd 00:00:00"
> - `TR_GENERATE_CHARGE_YES_NO` — from SocProperties
> - `TR_CONTRACT_TERM` — from SocProperties
> - `TR_CONTRACT_FEE` — from `TR_DEFAULT_CONTRACT_FEE` in SocProperties
> - `TR_ORIG_CONTRACT_EXPIRE_DATE` — LogicalDate + TR_CONTRACT_TERM months; or "2099-01-01 00:00:00" if TR_CONTRACT_TERM=0
> - `TR_CONTRACT_REMARK` — from SocProperties; defaults to "-" if blank

### §19.6 — Response Audit Logging

```text
createEvent
└── event
    ├── ESBUUID          ← $orderRequest/OrderData/OMXTrackingId   [Conditional]
    ├── PROCESS_ID       ← concat($pid, "_RES")                    [Always]
    ├── COMPONENT_NAME   ← $globalVariables/OMX_COMMON/.../OMX_CEP [Always]
    ├── OPERATION_NAME   ← $operatorname (="CCBS_GOD")             [Always]
    ├── TARGET_SYSTEM    ← $globalVariables/OMX_COMMON/.../OMX_FM  [Always]
    ├── LOG_LEVEL        ← $globalVariables/.../MSG_LOG_LEVEL/INFO  [Always]
    ├── AUDIT_TRACE      ← "Response received for RefId " + RefID  [Always]
    ├── AUDIT_TS         ← tib:format-dateTime(current-dateTime()) [Always]
    └── payload                                                     [Conditional: WritePayload="true"]
        └── ns:ServicePayload ← copy-of($eventResponse)
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
