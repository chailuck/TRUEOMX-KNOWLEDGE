# Request_TDG_CANCEL_SUBSCRIBER

TIBCO BusinessEvents FM Logic — TDG TRUE Digital: Cancel Subscriber (Per-Material Fan-out)

**Priority:** 5 | **ForwardChain:** true | **Backend:** TDG (TRUE Digital) | **Author:** CHAYATORN P.

---

## §1 — Overview & Purpose

This FM sends a device cancellation request to TDG (TRUE Digital) for each **Material** (physical device/hardware) attached to each subscriber. Unlike most FMs that fan out per subscriber or per offer, this rule fans out per **subscriber×material**, using a composite key `subscriberRefId + ":" + MatCode` for both the event RefID and the resubmit skip check.

The `ns:propositioncode` is derived from a RelatedOffersArray XPath that finds a trade-in offer (ServiceType="85" and TR_CONTRACT_IND=Y in SocProperties). Both POU and COU subscriber sets are processed in parallel.

> **COU and POU both implemented:** Full coverage — both loops have equivalent material-level fan-out logic.

> **[HIGH] Critical — COU Audit Log Name Wrong:** The COU dispatch block logs `OPERATION_NAME="TDG_CREATE_SUBSCRIBER"` and `AUDIT_TRACE="Request Sent for TDG_CREATE_SUBSCRIBER"` — copy-paste bug from a create FM. The POU audit correctly says `"TDG_CANCEL_SUBSCRIBER"`. Fix: update the COU Logger XSLT strings.

> **[MEDIUM] ns:propositioncode always emitted (no xsl:if):** The XPath over `SubscriberOffers/RelatedOffersArray[ServiceType="85" and contains(SocProperties,'TR_CONTRACT_IND=Y')]` is emitted unconditionally. TDG receives empty `<ns:propositioncode/>` if no matching offer exists.

> **[MEDIUM] MatCode vs MatSerial composite key inconsistency:** `pmatchRefId = subscriberRefId + ":" + MatCode` always uses MatCode. When MatCode is blank, PreExecCheck uses MatSerial for the lookup but the composite key becomes `"subRefId:"` — the two keys diverge.

> **Response rulefunction is clean:** `OMXUtils:generateTrackingID()` called inside XSLT (correct), standard fan-in, no dead variables.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_TDG_CANCEL_SUBSCRIBER` |
| Author | CHAYATORN P. |
| Priority | 5 |
| ForwardChain | true |
| Target backend | TDG — TRUE Digital (CancelSubscriber) |
| Request event type | `Events.OMConsumers.OMXFM.Request.TDG_CANCEL_SUBSCRIBER` (dedicated) |
| Response event type | `Events.OMConsumers.OMXFM.Response.TDG_CANCEL_SUBSCRIBER` |
| Response concept | `Concepts.FM.Base.ResponseBase` (standard, extId generated inside XSLT — correct) |
| Payload schema NS | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/TDG/CancelSubscriber.xsd` |
| Dispatch method | `Event.Ext.sendEventImmediate` (parallel) |
| Fan-out granularity | Per subscriber×material — one event per Material entry |
| Fan-out gate | `MaterialInfo != null && Material@length > 0` |
| RefID / resubmit key | Composite: `subscriberRefId + ":" + MatCode` |
| Fan-in mechanism | Standard: `currActivity.RequestCount == successResponseCount` where success = ResponseCode ends in "000" |
| RequestCount tracking | `orderCurrentActivity.RequestCount++` only if `!isActResub` |
| PreExecCheck helper (POU) | `GetXMLForSubscriberMaterialInfo(orderRequest, pSubRefId, matCode/matSerial)` |
| PreExecCheck helper (COU) | `GetXMLForSubscriberMaterialInChildOU(orderRequest, cSubRefId, pOuRefId, matCode/matSerial)` |
| POU audit OPERATION_NAME | "TDG_CANCEL_SUBSCRIBER" (correct) |
| COU audit OPERATION_NAME | "TDG_CREATE_SUBSCRIBER" **[HIGH BUG — copy-paste error]** |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order; subscriber, material, and offer data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step; Response[], Status, RequestCount |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to order's next step |
| 2 | `orderCurrentActivity.ActivityID == "TDG_CANCEL_SUBSCRIBER"` | FM identity |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "TDG_CANCEL_SUBSCRIBER"` | ProcessFlow routing |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be waiting |

---

## §5 — Execution Flow Diagram

1. Compute `isActResub`; fetch current activity; read `chkXPath`; set `isSkipped=true`
2. **POU loop**: iterate `ParentOU[p]`; capture `pOuId` (dead), `pOuRefId`
3. **POU Subscriber loop**: iterate `Subscriber[ps]`; capture `psub`, `pSubRefId`
4. Gate: `MaterialInfo != null && Material@length > 0` — skip if no materials
5. **POU Material loop**: iterate `Material[pmat]`; build `pmatchRefId = pSubRefId + ":" + MatCode`
6. Resubmit skip: linear scan `Response[]` for `ReferenceId == pmatchRefId AND CompletionStatus == 2`
7. If `!reqSuccess`: PreExecCheck via `GetXMLForSubscriberMaterialInfo` (MatCode preferred; MatSerial fallback)
8. If passes: dispatch `TDG_CANCEL_SUBSCRIBER` event; `isSkipped=false`; `RequestCount++`; POU audit log (correct)
9. **COU loop**: same Material-level fan-out; dispatch TDG event; COU audit log **[HIGH BUG: says "TDG_CREATE_SUBSCRIBER"]**
10. If `!isSkipped`: Status="1", SendDataToDB; else SkipActivity("4")

---

## §6 — Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| `pOuId` / `cOuId` | `ParentOU[p].OUId` / `ChildOU[c].OUId` | [LOW] Extracted but never used in XSLT or elsewhere |
| `pOuRefId` | `ParentOU[p].RefId` | Used in COU PreExecCheck helper call |
| `material` | `Subscriber[ps].MaterialInfo.Material[pmat]` | Device record; MatCode, MatSerial are key fields |
| `pmatchRefId` | `pSubRefId + ":" + MatCode` (POU) / `cSubRefId + ":" + MatCode` (COU) | Composite resubmit key AND event RefID. Always uses MatCode — if blank, becomes `"subRefId:"` [MEDIUM] |
| PreExecCheck material arg | MatCode preferred; `MatSerial` if `BRMS.IsBlankOrStringNull(MatCode)` | MatCode/MatSerial inconsistency with composite key [MEDIUM] |
| `ns:propositioncode` | `SubscriberOffers/RelatedOffersArray[ServiceType="85" and contains(SocProperties,'TR_CONTRACT_IND=Y')]/OfferName` | TR contract offer name; emitted unconditionally [MEDIUM] |
| `ns:reason` | `Channel='CCBS'` → `'C'`; else → `'R'` | Always one value via xsl:choose |

---

## §7 — System & Integration Dependencies

### §7.1 — ESB / JMS Channel Dependencies

| Direction | Event Type | Dispatch |
|-----------|------------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.TDG_CANCEL_SUBSCRIBER` | `sendEventImmediate` — one per qualifying subscriber×material |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `sendEventImmediate` — POU: correct name; COU: wrong name [HIGH BUG] |

### §7.2 — Backend API Details

| System | API / Operation | Payload Root | Schema NS |
|--------|-----------------|--------------|-----------|
| TDG (TRUE Digital) | CancelSubscriber | `ns:CancelSubscriberRequest` | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/TDG/CancelSubscriber.xsd` |

### §7.3 — Material Concept Fields Referenced

| Field | Usage | Notes |
|-------|-------|-------|
| `MatCode` | Composite key (`pmatchRefId`); PreExecCheck primary arg | Preferred over MatSerial |
| `MatSerial` | PreExecCheck fallback when MatCode blank; `ns:serial` in payload | Conditional (`xsl:if test="$material/MatSerial"`) |

### §7.4 — RelatedOffersArray Filter (ns:propositioncode)

| Predicate | Value / Purpose |
|-----------|----------------|
| `ServiceType` | `"85"` — TDG service type identifier |
| `SocProperties` | `contains(SocProperties, 'TR_CONTRACT_IND=Y')` — TR contract indicator |
| Result field | `OfferName` of first matching RelatedOffersArray → `ns:propositioncode` |

---

## §8 — Detailed Payload Build

### §8.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Notes |
|------------|------------|-------|
| `$orderRequest` | orderRequest concept | Root order — OrderData, Channel |
| `$pmatchRefId` | `subscriberRefId + ":" + MatCode` | Event RefID; resubmit composite key |
| `$material` | Material concept | MatSerial → ns:serial |
| `$psub` (POU) / `$csub` (COU) | Subscriber concept | MSISDN → ns:id; SubscriberOffers/RelatedOffersArray → ns:propositioncode |

### §8.2 — POU vs COU Variant Differences

| Aspect | POU Variant | COU Variant |
|--------|-------------|-------------|
| Subscriber param | `$psub` | `$csub` |
| compositeRefId base | `pSubRefId` | `cSubRefId` |
| PreExecCheck helper | `GetXMLForSubscriberMaterialInfo(req, pSubRefId, matArg)` | `GetXMLForSubscriberMaterialInChildOU(req, cSubRefId, pOuRefId, matArg)` |
| ns:id source | `$psub/MSISDN` | `$csub/MSISDN` |
| ns:propositioncode XPath | `$psub/SubscriberOffers/RelatedOffersArray[...]` | `$csub/SubscriberOffers/RelatedOffersArray[...]` |
| Audit OPERATION_NAME | "TDG_CANCEL_SUBSCRIBER" ✓ | "TDG_CREATE_SUBSCRIBER" [HIGH BUG] |

---

## §9 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event @extId ← OMXUtils:generateTrackingID()  [Always] Correct — uses @extId not @Id
    ├── JMSPriority          ← $orderRequest/OrderPriority                    [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId          [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                [Always]
    ├── RefID                ← $pmatchRefId (subscriberRefId + ":" + MatCode) [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType              [Always]
    └── payload
        └── ns:CancelSubscriberRequest
            ├── ns:serial           ← $material/MatSerial            [Conditional: xsl:if $material/MatSerial]
            ├── ns:id               ← $psub/MSISDN (POU) / $csub/MSISDN (COU) [Conditional: xsl:if MSISDN]
            ├── ns:propositioncode  ← SubscriberOffers/RelatedOffersArray[ServiceType="85" and TR_CONTRACT_IND=Y]/OfferName [Always — no xsl:if, may be empty] [MEDIUM]
            └── ns:reason           [xsl:choose]
                ├── when Channel='CCBS' → 'C'
                └── otherwise       → 'R'
```

**Legend:**
- `[Always]` — unconditional
- `[Conditional: ...]` — inside `xsl:if` with the given predicate

---

## §10 — Audit Logging

| Phase | Variant | OPERATION_NAME | AUDIT_TRACE |
|-------|---------|----------------|-------------|
| Request | POU (correct) | "TDG_CANCEL_SUBSCRIBER" | "Request Sent for TDG_CANCEL_SUBSCRIBER" |
| Request | COU **[HIGH BUG]** | "TDG_CREATE_SUBSCRIBER" | "Request Sent for TDG_CREATE_SUBSCRIBER" |
| Response | Both | "TDG_CANCEL_SUBSCRIBER" | "Response received for TDG_CANCEL_SUBSCRIBER" |
| Audit gate | Both | Only when event is dispatched | — |

---

## §11 — Activity Status Management

| Transition | Code | Trigger |
|------------|------|---------|
| Running | "1" | At least one event dispatched |
| Skip | "4" | No events dispatched (all subscribers have no materials, or all failed PreExecCheck) |
| Error | HandleActivityException | Any uncaught exception |

---

## §12 — Exception / Error Handling

`try { ... } catch (Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }`

---

## §13 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Instance.getByExtIdByUri(extId, uri)` | Fetches current activity to read PreExecCheck |
| `BRMS.IsBlankOrStringNull(value)` | Null/blank check for MatCode to decide PreExecCheck helper arg |
| `GetXMLForSubscriberMaterialInfo(orderRequest, subRefId, matArg)` | Builds PreExecCheck XML for POU subscriber with material key |
| `GetXMLForSubscriberMaterialInChildOU(orderRequest, cSubRefId, pOuRefId, matArg)` | Builds PreExecCheck XML for COU subscriber with material key |
| `GetActivityStatusString("1", false)` | Returns "Running" status |
| `SendDataToDB(orderRequest)` | Persists order state |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | Marks activity as skipped |
| `HandleActivityException(...)` | Central exception handler |

---

## §14 — Function Dependency Tree

```text
Request_TDG_CANCEL_SUBSCRIBER.rule
├── isActResub check
├── Instance.getByExtIdByUri(NextActivityName, ".../Activity") → nextAct
├── nextAct.PreExecCheck → chkXPath
│
├── [POU loop: ParentOU[p]]
│   ├── pOuId = ParentOU[p].OUId  [DEAD — never used]
│   ├── pOuRefId = ParentOU[p].RefId
│   └── [POU Subscriber loop: Subscriber[ps]]
│       ├── psub, pSubRefId
│       └── [Gate: MaterialInfo != null AND Material@length > 0]
│           └── [POU Material loop: Material[pmat]]
│               ├── pmatchRefId = pSubRefId + ":" + material.MatCode
│               ├── Linear scan: Response[i].ReferenceId == pmatchRefId AND CompletionStatus==2 → reqSuccess
│               └── [if !reqSuccess]
│                   ├── BRMS.IsBlankOrStringNull(material.MatCode)
│                   │   ├── if false: GetXMLForSubscriberMaterialInfo(req, pSubRefId, MatCode)
│                   │   └── if true:  GetXMLForSubscriberMaterialInfo(req, pSubRefId, MatSerial)
│                   ├── XPath.execute("/(" + chkXPath + ")", sXML) → chkRes
│                   └── [if chkRes=="true"]
│                       ├── Event.createEvent(TDG_CANCEL_SUBSCRIBER XSLT — $psub variant)
│                       ├── Event.Ext.sendEventImmediate(reqEvent)
│                       ├── isSkipped = false
│                       ├── if(!isActResub): orderCurrentActivity.RequestCount++
│                       └── Event.Ext.sendEventImmediate(Logger — "TDG_CANCEL_SUBSCRIBER") ✓
│
├── [COU loop: ParentOU[p].ChildOU[c]]
│   ├── cOuId = ChildOU[c].OUId  [DEAD — never used]
│   ├── cOuRefId = ChildOU[c].RefId
│   └── [COU Subscriber loop: Subscriber[cs]]
│       ├── csub, cSubRefId
│       └── [Gate: MaterialInfo != null AND Material@length > 0]
│           └── [COU Material loop: Material[pmat]]
│               ├── pmatchRefId = cSubRefId + ":" + material.MatCode
│               ├── Linear scan: Response[i].ReferenceId == pmatchRefId AND CompletionStatus==2 → reqSuccess
│               └── [if !reqSuccess]
│                   ├── BRMS.IsBlankOrStringNull(material.MatCode)
│                   │   ├── if false: GetXMLForSubscriberMaterialInChildOU(req, cSubRefId, pOuRefId, MatCode)
│                   │   └── if true:  GetXMLForSubscriberMaterialInChildOU(req, cSubRefId, pOuRefId, MatSerial)
│                   ├── XPath.execute("/(" + chkXPath + ")", sXML) → chkRes
│                   └── [if chkRes=="true"]
│                       ├── Event.createEvent(TDG_CANCEL_SUBSCRIBER XSLT — $csub variant)
│                       ├── Event.Ext.sendEventImmediate(reqEvent)
│                       ├── isSkipped = false
│                       ├── if(!isActResub): orderCurrentActivity.RequestCount++
│                       └── Event.Ext.sendEventImmediate(Logger — "TDG_CREATE_SUBSCRIBER") [HIGH BUG]
│
├── if(!isSkipped): GetActivityStatusString("1") + SendDataToDB
├── else: SkipActivity(..., "4")
└── HandleActivityException(...)
```

---

## §15 — Concept Definitions Referenced

| Concept | Key Properties Used |
|---------|---------------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.OMXTrackingId, OrderData.OrderID, OrderData.OrderType, OrderData.OrderPriority, OrderData.Channel, Customer.ParentOU[].RefId/OUId, Customer.ParentOU[].Subscriber[], Customer.ParentOU[].ChildOU[].Subscriber[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, MaterialInfo.Material[], SubscriberOffers[].RelatedOffersArray[] |
| `Concepts.OrderRequest.OrderElements.Material` | MatCode, MatSerial |
| `Concepts.OrderRequest.OrderElements.RelatedOffersArray` | ServiceType, SocProperties, OfferName |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck |
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId (= composite pmatchRefId) |

---

## §16 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Cancel TDG subscriber entry for each Material (device) attached to each POU and COU subscriber that passes PreExecCheck |
| R2 | Fan-out key: composite `subscriberRefId + ":" + MatCode` — one event per material per subscriber |
| R3 | Skip subscriber if MaterialInfo is null or has no Material entries |
| R4 | ns:serial = MatSerial (conditional); ns:id = subscriber MSISDN (conditional) |
| R5 | ns:propositioncode = OfferName from RelatedOffersArray[ServiceType="85" and TR_CONTRACT_IND=Y] |
| R6 | ns:reason = 'C' if Channel=CCBS; else 'R' |
| R7 | Standard fan-in: RequestCount == count(Response[ResponseCode ends in "000"]) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| COU audit Logger OPERATION_NAME/AUDIT_TRACE says "TDG_CREATE_SUBSCRIBER" instead of "TDG_CANCEL_SUBSCRIBER" — copy-paste bug from create FM | [HIGH] | Fix COU Logger XSLT: change both OPERATION_NAME and AUDIT_TRACE to "TDG_CANCEL_SUBSCRIBER" |
| ns:propositioncode always emitted without xsl:if — empty element sent to TDG if no matching RelatedOffersArray[ServiceType="85" and TR_CONTRACT_IND=Y] | [MEDIUM] | Wrap in xsl:if; verify TDG accepts absent propositioncode |
| pmatchRefId always uses MatCode but PreExecCheck may use MatSerial — composite key inconsistency when MatCode blank | [MEDIUM] | Align: if MatCode blank, use MatSerial in pmatchRefId too; or always require MatCode |
| pOuId and cOuId extracted but never used in XSLT or logic | [LOW] | Remove unused variable assignments |
| Multiple RelatedOffersArray matches for ServiceType="85" and TR_CONTRACT_IND=Y — xsl:value-of selects first | [LOW] | Verify if only one match per subscriber is expected; document assumption |

---

## §17 — Full Source Code (abbreviated)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_TDG_CANCEL_SUBSCRIBER {
  attribute { priority = 5; forwardChain = true; }
  declare { /* orderRequest, orderCurrentActivity */ }
  when { /* activityId == "TDG_CANCEL_SUBSCRIBER" AND Status == "WAITING" */ }
  then {
    boolean isActResub = ...;
    try {
      Activity nextAct = Instance.getByExtIdByUri(...);
      boolean isSkipped = true;
      for (POU loop) {
        pOuId = ParentOU[p].OUId;  // DEAD VARIABLE [LOW]
        pOuRefId = ParentOU[p].RefId;
        for (psub loop) {
          if (MaterialInfo != null && Material@length > 0) {
            for (Material[pmat]) {
              pmatchRefId = pSubRefId + ":" + material.MatCode;
              // resubmit check against pmatchRefId
              if(!reqSuccess) {
                // PreExecCheck: MatCode preferred, MatSerial fallback
                if(chkRes=="true") {
                  reqEvent = Event.createEvent(/* TDG_CANCEL_SUBSCRIBER XSLT $psub — see §9 */);
                  Event.Ext.sendEventImmediate(reqEvent);
                  isSkipped = false; RequestCount++;
                  Event.Ext.sendEventImmediate(/* Logger "TDG_CANCEL_SUBSCRIBER" ✓ */);
                }
              }
            }
          }
        }
      }
      for (COU loop) {
        cOuId = ChildOU[c].OUId;  // DEAD VARIABLE [LOW]
        for (csub loop) {
          if (MaterialInfo != null && Material@length > 0) {
            for (Material[pmat]) {
              pmatchRefId = cSubRefId + ":" + material.MatCode;
              if(!reqSuccess) {
                // PreExecCheck: uses GetXMLForSubscriberMaterialInChildOU
                if(chkRes=="true") {
                  reqEvent = Event.createEvent(/* TDG_CANCEL_SUBSCRIBER XSLT $csub */);
                  Event.Ext.sendEventImmediate(reqEvent);
                  isSkipped = false; RequestCount++;
                  Event.Ext.sendEventImmediate(/* Logger "TDG_CREATE_SUBSCRIBER" [HIGH BUG] */);
                }
              }
            }
          }
        }
      }
      if(!isSkipped) { Status="1"; SendDataToDB; }
      else { SkipActivity("4"); }
    } catch(Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §18 — Response Message Rule

### §18.1 — Overview

Clean, correct implementation. Creates `ResponseBase` with `OMXUtils:generateTrackingID()` inside XSLT, appends to `currActivity.Response[]`, logs audit, evaluates standard fan-in.

### §18.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Audit log |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.TDG_CANCEL_SUBSCRIBER` | TDG response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended |

### §18.3 — ResponseBase Concept Construction

```text
createObject
└── object @extId ← OMXUtils:generateTrackingID()  [Always] Correct — inside XSLT
    ├── ResponseCode      ← $eventResponse/ResponseCode  [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg   [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId       ← $eventResponse/RefID (= pmatchRefId composite key) [Conditional]
```

### §18.4 — Fan-in Completion Logic

| Expression | Value |
|------------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` → return "true" |
| Not yet done | return "false" |

Standard correct fan-in — no anomalies in the response rulefunction.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
