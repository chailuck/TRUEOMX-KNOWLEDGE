# Request_CRM_CREATE_CLOSE_SR_MOBILE

TIBCO BusinessEvents FM Logic — CRM Create & Close Service Request (Mobile)

**Priority:** 5 | **ForwardChain:** true | **Backend:** CRM (Service Request) | **Event:** CRM_CREATE_UPDATE_SR (shared) | **Author:** CHAYATORN-PC

---

## §1 — Overview & Purpose

This FM creates and closes a CRM Service Request (SR) for Mobile subscribers. It sends a `CRM_CREATE_UPDATE_SR` event (shared event type — used for both create and update SR operations) with SR status hardcoded to `"Closed"`, category `"Service"`, and productLine `"True Mobile"`. One event is dispatched per subscriber across both POU and COU subscriber sets.

> **COU support complete:** Unlike some other FMs, both the POU and COU subscriber loops are fully implemented with equivalent logic — all subscribers in the order receive an SR close request.

> **[HIGH] Critical — Resubmit Skip Broken:** `refId = String.valueOfLong(System.nanoTime())` — the event's RefID is a nanosecond timestamp, NOT the subscriber's RefId. The response returns this nanoTime value as `ReferenceId` in the ResponseBase concept, but the resubmit check compares `Response[].ReferenceId == subscriber.RefId`. These will NEVER match → `reqSuccess` is always `false` → duplicate CRM SR creation on every resubmit. Fix: use `refId = subscriber.RefId`.

> **[MEDIUM] ResponseBase extId may be empty:** The XSLT uses `$activityRes/@extId` but `activityRes` is the concept being created — it's null at call time. The Java `extId` variable (line 14) is never passed to the XSLT. Fix: call `OMXUtils:generateTrackingID()` directly inside the XSLT.

> **[MEDIUM] @Id vs @extId:** The event container uses `<xsl:attribute name="Id">` instead of the standard `extId`.

> **[MEDIUM] customerType default missing:** CustomerTypeInfo.Type values 66=Business, 67=Corporate, 73/80=Individual are handled; any other value → empty string. CRM backend may reject an empty customerType.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CRM_CREATE_CLOSE_SR_MOBILE` |
| Author | CHAYATORN-PC |
| Priority | 5 |
| ForwardChain | true |
| Target backend | CRM (Customer Relationship Management) — Create/Close Service Request |
| Request event type | `Events.OMConsumers.OMXFM.Request.CRM_CREATE_UPDATE_SR` (shared — not dedicated) |
| Response event type | `Events.OMConsumers.OMXFM.Response.CRM_CREATE_UPDATE_SR` |
| Response concept | `Concepts.FM.Base.ResponseBase` (standard) |
| Payload schema NS | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CRM/CRMCreateUpdateSRService.xsd` |
| Dispatch method | `Event.Ext.sendEventImmediate` (parallel) |
| Fan-out granularity | Per subscriber — POU and COU both fully implemented |
| RefID in event | `String.valueOfLong(System.nanoTime())` — nanosecond timestamp **[HIGH BUG: should be subscriber.RefId]** |
| Fan-in mechanism | Standard: `currActivity.RequestCount == successResponseCount` where success = ResponseCode ends in "000" |
| RequestCount tracking | `orderCurrentActivity.RequestCount++` only if `!isActResub` |
| Resubmit skip key | `subscriber.RefId` — but broken because RefID in event is nanoTime [HIGH BUG] |
| PreExecCheck helper (POU) | `GetXMLForSubscriber(orderRequest, pSubRefId)` |
| PreExecCheck helper (COU) | `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)` |
| Audit log gate | Only when SR event dispatched (inside dispatch block) |
| Skip trigger | No events dispatched → SkipActivity("4") |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order; subscriber, customer, and ExtendedInfo data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step; Response[], Status, RequestCount, PreExecCheck |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to order's next step |
| 2 | `orderCurrentActivity.ActivityID == "CRM_CREATE_CLOSE_SR_MOBILE"` | FM identity |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CRM_CREATE_CLOSE_SR_MOBILE"` | ProcessFlow routing |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be waiting |

---

## §5 — Execution Flow Diagram

1. Compute `isActResub`; fetch `nextAct` (= current activity) via `Instance.getByExtIdByUri`; read `chkXPath = nextAct.PreExecCheck`; set `isSkipped = true`
2. **POU loop**: iterate `Customer.ParentOU[p]`
3. **POU Subscriber loop**: iterate `ParentOU[p].Subscriber[ps]`
4. Linear scan of `orderCurrentActivity.Response[]` to set `reqSuccess`: check `String.equals(Response[i].ReferenceId, pSubRefId) && CompletionStatus == 2` [broken — see §1]
5. If `!reqSuccess`: run PreExecCheck via `GetXMLForSubscriber`; if passes, compute `productType`, `refId`, `idNumber`, `customerType`
6. Build & dispatch `CRM_CREATE_UPDATE_SR` event via `sendEventImmediate`; `isSkipped=false`; `RequestCount++` if !isActResub
7. Dispatch audit Logger event
8. **COU loop**: iterate `ParentOU[p].ChildOU[c]`
9. **COU Subscriber loop**: identical logic as POU — same PreExecCheck, same payload (subscriber param = `csub`)
10. If `!isSkipped`: Status="1", SendDataToDB; else SkipActivity("4")

---

## §6 — Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| `productType` | `GetActivityParameterValueFromKey(orderCurrentActivity, "PRODUCT_TYPE")` | From ProcessConfig activity Parameter element, key=PRODUCT_TYPE |
| `refId` | `String.valueOfLong(System.nanoTime())` | **[HIGH BUG]** Nanosecond timestamp — should be subscriber.RefId for correct response correlation |
| `idNumber` | `CustomerGeneralInfo.Identification` (if non-null, else "") | National ID or passport number |
| `customerType` | Derived from `CustomerTypeInfo.Type` integer | 66→"Business"; 67→"Corporate"; 73 or 80→"Individual"; else→"" [MEDIUM — no default] |
| `pSubRefId` | `psub.RefId` | POU subscriber RefId — used in resubmit check (but broken) |
| `cSubRefId` | `csub.RefId` | COU subscriber RefId — used in resubmit check (but broken) |

### §6.1 — CustomerType Mapping Table

| CustomerTypeInfo.Type (int) | Mapped customerType String |
|-----------------------------|---------------------------|
| 66 | "Business" |
| 67 | "Corporate" |
| 73 | "Individual" |
| 80 | "Individual" |
| anything else (including null) | "" (empty string) — CRM backend may reject [MEDIUM] |

---

## §7 — System & Integration Dependencies

### §7.1 — ESB / JMS Channel Dependencies

| Direction | Event Type | Dispatch |
|-----------|------------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CRM_CREATE_UPDATE_SR` | `Event.Ext.sendEventImmediate` — one per qualifying subscriber |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `Event.Ext.sendEventImmediate` — only when SR event is dispatched |

### §7.2 — Backend API Details

| System | API / Operation | Payload Root | Schema NS |
|--------|-----------------|--------------|-----------|
| CRM | CRMCreateUpdateSRService — Close SR | `ns:CRMCreateUpdateSRServiceRequest` | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CRM/CRMCreateUpdateSRService.xsd` |

### §7.3 — ExtendedInfo Fields Required (Order-level)

| Name | Required/Optional | Mapped to |
|------|-------------------|-----------|
| SR_RESOLUTION | Optional (always emitted — may be empty) | `ns:resolution` |
| SR_SUBCATEGORY | Optional (always emitted — may be empty) | `ns:subCategory` |
| SR_ISSUE | Optional (always emitted — may be empty) | `ns:issue` |
| SR_SOURCE_DESC | Optional (always emitted — may be empty) | `ns:source` |

> All four SR ExtendedInfo fields are emitted unconditionally (no `xsl:if` guard). CRM receives empty string elements if these are absent from the order. [LOW]

### §7.4 — Activity Parameter Keys

| Key | Usage |
|-----|-------|
| PRODUCT_TYPE | Resolved via `GetActivityParameterValueFromKey(orderCurrentActivity, "PRODUCT_TYPE")` → mapped to `ns:productType` |

---

## §8 — Detailed Payload Build

### §8.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Notes |
|------------|------------|-------|
| `$orderRequest` | orderRequest concept | Root order — Customer, OrderData, ExtendedInfo |
| `$refId` | `String.valueOfLong(System.nanoTime())` | [HIGH BUG] Should be subscriber.RefId |
| `$productType` | From activity parameter key PRODUCT_TYPE | Mapped to `ns:productType` |
| `$psub` (POU) / `$csub` (COU) | Subscriber concept | Source of `MSISDN` → `ns:serviceId` |
| `$idNumber` | `CustomerGeneralInfo.Identification` (or "") | National ID number |
| `$customerType` | Derived from `CustomerTypeInfo.Type` | 66=Business, 67=Corporate, 73/80=Individual, else="" |

### §8.2 — POU vs COU Variant Differences

| Aspect | POU Variant | COU Variant |
|--------|-------------|-------------|
| Subscriber param name | `$psub` | `$csub` |
| serviceId source | `$psub/MSISDN` | `$csub/MSISDN` |
| PreExecCheck helper | `GetXMLForSubscriber(orderRequest, pSubRefId)` | `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)` |
| All payload fields | Identical — both use same static SR fields from order-level ExtendedInfo | ← same |

---

## §9 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event @Id ← OMXUtils:generateTrackingID()  [Always] NOTE: uses @Id not @extId!
    ├── JMSPriority          ← $orderRequest/OrderPriority                    [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId          [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                [Always]
    ├── RefID                ← $refId (System.nanoTime() string — NOT subscriber.RefId!) [Always] [HIGH BUG]
    ├── OrderType            ← $orderRequest/OrderData/OrderType              [Always]
    └── payload
        └── ns:CRMCreateUpdateSRServiceRequest
            ├── ns:integrationId    ← $orderRequest/OrderData/OrderID         [Always]
            ├── ns:resolution       ← $orderRequest/OrderData/ExtendedInfo[SR_RESOLUTION]/Value [Always, no xsl:if]
            ├── ns:status           ← "Closed"  (static)                     [Always]
            ├── ns:category         ← "Service"  (static)                    [Always]
            ├── ns:subCategory      ← $orderRequest/OrderData/ExtendedInfo[SR_SUBCATEGORY]/Value [Always, no xsl:if]
            ├── ns:issue            ← $orderRequest/OrderData/ExtendedInfo[SR_ISSUE]/Value [Always, no xsl:if]
            ├── ns:productLine      ← "True Mobile"  (static)                [Always]
            ├── ns:productType      ← $productType (activity param PRODUCT_TYPE) [Always]
            ├── ns:serviceId        ← $psub/MSISDN (POU) / $csub/MSISDN (COU) [Always]
            ├── ns:idNumber         ← $idNumber (CustomerGeneralInfo.Identification or "") [Always]
            ├── ns:customerType     ← $customerType (66=Business/67=Corporate/73,80=Individual/else="") [Always]
            └── ns:source           ← $orderRequest/OrderData/ExtendedInfo[SR_SOURCE_DESC]/Value [Always, no xsl:if]
```

**Legend:**
- `[Always]` — unconditional, always emitted (even if value is empty)
- `[Conditional]` — inside `xsl:if`
- Note: All SR payload fields lack `xsl:if` guards — empty elements sent to CRM if ExtendedInfo absent

---

## §10 — Audit Logging

| Phase | Field | Value |
|-------|-------|-------|
| Request | OPERATION_NAME | "CRM_CREATE_CLOSE_SR_MOBILE" |
| Request | AUDIT_TRACE | "Request Sent for CRM_CREATE_CLOSE_SR_MOBILE" |
| Request | payload | Conditional: WritePayload="true" → copy of reqEvent |
| Response | OPERATION_NAME | "CRM_CREATE_CLOSE_SR_MOBILE" |
| Response | AUDIT_TRACE | "Response received for CRM_CREATE_CLOSE_SR_MOBILE" |
| Request audit gate | Only emitted when SR event is dispatched (inside dispatch block) |

---

## §11 — Activity Status Management

| Transition | Code | Trigger |
|------------|------|---------|
| Running | "1" | At least one subscriber event dispatched (isSkipped=false) |
| Skip | "4" | No events dispatched (isSkipped still true) |
| Error | HandleActivityException | Any uncaught exception |

---

## §12 — Exception / Error Handling

`try { ... } catch (Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }`

---

## §13 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Instance.getByExtIdByUri(extId, uri)` | Fetches current activity concept by extId to read PreExecCheck |
| `GetXMLForSubscriber(orderRequest, pSubRefId)` | Builds XPath-evaluation XML for POU subscriber PreExecCheck |
| `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)` | Builds XPath-evaluation XML for COU subscriber PreExecCheck |
| `GetActivityParameterValueFromKey(activity, key)` | Reads activity Parameter value for key "PRODUCT_TYPE" |
| `GetActivityStatusString("1", false)` | Returns "Running" status string |
| `SendDataToDB(orderRequest)` | Persists order state |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | Marks activity as skipped |
| `HandleActivityException(...)` | Central exception handler |

---

## §14 — Function Dependency Tree

```text
Request_CRM_CREATE_CLOSE_SR_MOBILE.rule
├── isActResub check
├── Instance.getByExtIdByUri(NextActivityName, "/Concepts/.../Activity") → nextAct
├── nextAct.PreExecCheck → chkXPath
│
├── [POU loop: ParentOU[p]]
│   └── [POU Subscriber loop: Subscriber[ps]]
│       ├── Linear scan: Response[i].ReferenceId == pSubRefId AND CompletionStatus==2 → reqSuccess
│       ├── [if !reqSuccess]
│       │   ├── GetXMLForSubscriber(orderRequest, pSubRefId) → sXML  [if PreExecCheck exists]
│       │   ├── XPath.execute("/(" + chkXPath + ")", sXML) → chkRes
│       │   └── [if chkRes=="true"]
│       │       ├── GetActivityParameterValueFromKey(orderCurrentActivity, "PRODUCT_TYPE") → productType
│       │       ├── String.valueOfLong(System.nanoTime()) → refId  [HIGH BUG]
│       │       ├── CustomerGeneralInfo.Identification → idNumber  [null check]
│       │       ├── CustomerTypeInfo.Type (66/67/73/80) → customerType  [no default for other values]
│       │       ├── Event.createEvent(CRM_CREATE_UPDATE_SR XSLT — $psub variant)
│       │       ├── Event.Ext.sendEventImmediate(reqEvent)
│       │       ├── isSkipped = false
│       │       ├── if(!isActResub): orderCurrentActivity.RequestCount++
│       │       └── Event.Ext.sendEventImmediate(audit Logger)
│
├── [COU loop: ParentOU[p].ChildOU[c]]
│   └── [COU Subscriber loop: ChildOU[c].Subscriber[cs]]
│       ├── Linear scan: Response[i].ReferenceId == cSubRefId AND CompletionStatus==2 → reqSuccess
│       ├── [if !reqSuccess]
│       │   ├── GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId) → sXML
│       │   ├── XPath.execute("/(" + chkXPath + ")", sXML) → chkRes
│       │   └── [if chkRes=="true"]  (same logic as POU with $csub)
│
├── if(!isSkipped): GetActivityStatusString("1") + SendDataToDB
├── else: SkipActivity(..., "4")
└── HandleActivityException(...)
```

---

## §15 — Concept Definitions Referenced

| Concept | Key Properties Used |
|---------|---------------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.OMXTrackingId, OrderData.OrderID, OrderData.OrderType, OrderData.OrderPriority, OrderData.ExtendedInfo[SR_RESOLUTION, SR_SUBCATEGORY, SR_ISSUE, SR_SOURCE_DESC], Customer.CustomerGeneralInfo.Identification, Customer.CustomerTypeInfo.Type, Customer.ParentOU[].ChildOU[].Subscriber[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck, Parameter[] |
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |

---

## §16 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Close a CRM Service Request for each subscriber (POU and COU) in the order where the PreExecCheck passes |
| R2 | SR always closed with status="Closed", category="Service", productLine="True Mobile" |
| R3 | productType from activity parameter key PRODUCT_TYPE |
| R4 | SR fields (resolution, subCategory, issue, source) from order-level ExtendedInfo |
| R5 | customerType derived from CustomerTypeInfo.Type integer mapping: 66=Business, 67=Corporate, 73/80=Individual |
| R6 | serviceId = subscriber MSISDN; idNumber = CustomerGeneralInfo.Identification |
| R7 | Standard fan-in: RequestCount == count(Response[ResponseCode ends in "000"]) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| refId = System.nanoTime() — response correlation and resubmit skip both broken; duplicate SR closed on every resubmit | [HIGH] | Replace with `refId = subscriber.RefId` in both POU and COU variants |
| ResponseBase extId empty — XSLT uses $activityRes/@extId but concept is null at creation time; Java extId variable never passed to XSLT | [MEDIUM] | Generate extId inside XSLT with `OMXUtils:generateTrackingID()` directly; remove dead Java `extId` variable |
| Event container uses @Id not @extId — inconsistent with standard BE pattern | [MEDIUM] | Change to `<xsl:attribute name="extId">` if BE routing/correlation uses extId as the key |
| customerType defaults to "" for unknown CustomerTypeInfo.Type values — CRM backend may reject | [MEDIUM] | Add else branch with a sensible default (e.g., "Individual") or validate upstream |
| SR ExtendedInfo fields (SR_RESOLUTION etc.) always emitted without xsl:if guard — empty elements sent to CRM | [LOW] | Add xsl:if guards around each SR field if CRM rejects empty elements |
| Committed commented-out createInstance block at line 16 — dead code | [LOW] | Remove the commented-out block; note it used $eventResponse/@extId as the extId source |

---

## §17 — Full Source Code (abbreviated)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CRM_CREATE_CLOSE_SR_MOBILE {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CRM_CREATE_CLOSE_SR_MOBILE";
    orderRequest.ProcessFlow.NextActivityID == "CRM_CREATE_CLOSE_SR_MOBILE";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Activity nextAct = Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
      String chkXPath = nextAct.PreExecCheck;
      boolean isSkipped = true;

      // POU Subscriber loop
      for (POU loop) {
        for (psub loop) {
          boolean reqSuccess = false;
          // Linear scan of Response[] for resubmit check (broken — nanoTime vs subscriber.RefId)
          for(Response[] scan) {
            if(String.equals(Response[i].ReferenceId, pSubRefId) && CompletionStatus==2) reqSuccess=true;
          }
          if(!reqSuccess) {
            // PreExecCheck
            if(String.equals(chkRes,"true")) {
              String productType = GetActivityParameterValueFromKey(orderCurrentActivity, "PRODUCT_TYPE");
              String refId = String.valueOfLong(System.nanoTime()); // HIGH BUG
              String idNumber = (CustomerGeneralInfo != null) ? CustomerGeneralInfo.Identification : "";
              String customerType = ""; // 66=Business, 67=Corporate, 73/80=Individual, else=""
              CRM_CREATE_UPDATE_SR reqEvent = Event.createEvent(/* CRM_CREATE_UPDATE_SR XSLT $psub variant — see §9 */);
              Event.Ext.sendEventImmediate(reqEvent);
              isSkipped = false;
              if(!isActResub) orderCurrentActivity.RequestCount++;
              Event.Ext.sendEventImmediate(/* audit Logger */);
            }
          }
        }
      }
      // COU Subscriber loop — identical logic with $csub and GetXMLForSubscriberInChildOU
      for (COU loop) { /* same structure */ }

      if(!isSkipped) { Status="1"; SendDataToDB; }
      else { SkipActivity(..., "4"); }
    } catch(Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §18 — Response Message Rule

### §18.1 — Overview

Creates a `ResponseBase` concept, appends to `currActivity.Response[]`, sets `currActivity.ResponseCode` and `currActivity.ResponseMessage`, logs audit, then evaluates the fan-in condition. Standard fan-in: returns `"true"` when `RequestCount == count(Response[ResponseCode ends in "000"])`.

> **[MEDIUM] Dead extId variable + empty ResponseBase extId:** Line 14 computes `String extId = OMXUtils.generateTrackingID()` but never passes it to the XSLT. The XSLT uses `$activityRes/@extId` but `activityRes` is null at creation time → ResponseBase gets empty extId. Line 16 (commented out) was the original alternative using `$eventResponse/@extId`. Fix: call `OMXUtils:generateTrackingID()` directly inside XSLT.

### §18.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Audit log |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CRM_CREATE_UPDATE_SR` | CRM response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; ResponseCode/Message updated |

### §18.3 — ResponseBase Concept Construction

```text
createObject
└── object @extId ← $activityRes/@extId  [Always] MEDIUM: $activityRes is null → empty extId
    ├── ResponseCode      ← $eventResponse/ResponseCode  [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg   [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId       ← $eventResponse/RefID (= nanoTime echo — NOT subscriber.RefId!) [Conditional]
```

### §18.4 — Fan-in Completion Logic

| Expression | Value |
|------------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` → return "true" |
| Not yet done | return "false" |

Standard correct fan-in — the activity advances only when all dispatched requests have received a successful ("000") response.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
