# Request_OMX_REMOVE_NXTOFR_FROM_PREV_SOC

TIBCO BusinessEvents FM Logic — Remove Next Offer from Previous SOC (Future Order Cleanup)

**Priority:** 5 | **ForwardChain:** true | **Backend:** OMX Internal FM | **Author:** SathidP-PC
**Dispatch:** sendEventImmediate (parallel) | **Fan-out:** 4 loops (POU/COU × Agreement/Subscriber)
**Fan-in:** ResponseCode suffix "000" | **Audit:** Unconditional (no AllowWriteLog gate)

> **⚠ BUG [HIGH] — Resubmission skip never fires:** `Response[ReferenceId == pOu.OUId/cOu.OUId/subscriberId]` is checked but the response concept (`OMX_RemoveNextOfferFromPrevSocRes`) does NOT map `ReferenceId`. It will always be empty — resubmission always re-dispatches all offers.

> **[MEDIUM] — 5 dead variables** declared and assigned but never passed to any XSLT: `futureType`, `requestedDate`, `requestedBy`, `requestedByUser`, `logicalDate`.

---

## §1 — Overview & Purpose

Clears **future order (NXTOFR)** linkages on a SOC during offer removal. When an offer is being removed from a subscriber or agreement, any scheduled "next offer" pointer on the previous SOC must be cleared. The rule sends one `OMX_REMOVE_NXTOFR_FROM_PREV_SOC` request per qualifying offer across four traversal paths.

The payload carries `futureSoc.code = "-"` (static remove signal) and `futureSoc.previousSoc = $soc` (the SOC whose future link to clear). Node level 3 = Agreement/OU target; node level 5 = Subscriber target.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_REMOVE_NXTOFR_FROM_PREV_SOC` |
| Author | SathidP-PC |
| Priority | 5 |
| ForwardChain | true |
| Backend | OMX Internal FM |
| Payload root | `ns4:futureOrderAll` |
| Request event type | `Events.OMConsumers.OMXFM.Request.OMX_REMOVE_NXTOFR_FROM_PREV_SOC` |
| Response event type | `Events.OMConsumers.OMXFM.Response.OMX_REMOVE_NXTOFR_FROM_PREV_SOC` |
| Response concept | `Concepts.FM.Response.OMX_RemoveNextOfferFromPrevSocRes` (specialized — no ReferenceId) |
| Fan-out granularity | 4 loops: POU Agreement / POU Subscriber / COU Agreement / COU Subscriber |
| Fan-in mechanism | `count(Response[tib:right(tib:trim(ResponseCode), 3) = "000"]) == RequestCount` |
| RefID in JMS header | **Absent** — no RefID in any variant |
| IsEnableUserPass | Feature flag in all XSLTs for credential injection |
| Audit log gate | Unconditional (no AllowWriteLog) |
| Skip trigger | No qualifying offers → SkipActivity("4") |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step |

**Dead variables (never passed to XSLT):**

| Variable | Assigned Value | Issue |
|----------|---------------|-------|
| `futureType` | `"NXTOFR"` | Never used [MEDIUM] |
| `requestedDate` | `DateTime.now()` | Never used [MEDIUM] |
| `requestedBy` | `"OMX"` | Never used [MEDIUM] |
| `requestedByUser` | `orderRequest.OrderData.Channel` | Never used [MEDIUM] |
| `logicalDate` | `DateTime.now()` or parsed from `LogicalDate` concept | Computed, never used [MEDIUM] |

> `Concepts.OM.LogicalDate` is fetched from working memory solely to compute `logicalDate` which is never referenced — the entire concept lookup is wasted work.

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to order |
| 2 | `orderCurrentActivity.ActivityID == "OMX_REMOVE_NXTOFR_FROM_PREV_SOC"` | FM identity check |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_REMOVE_NXTOFR_FROM_PREV_SOC"` | ProcessFlow routing check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be waiting |

---

## §5 — Execution Flow Diagram

1. Compute `isActResub`; read LogicalDate concept (result unused)
2. Set dead vars: futureType, requestedDate, requestedBy, requestedByUser, logicalDate
3. **Loop ①: POU Agreement Offers** — per `pOu.Agreement.Offers[i]`
4. FE_OR_CCBS read but NOT filtered — Agreement offers always eligible
5. PreExecCheck via `GetXMLForAgreementOffer`; resubmit skip (broken); build Variant ①
6. **Loop ②: POU Subscriber Offers** — per `subscriberPou.SubscriberOffers[i]`
7. Filter: `source == "FE"` required; GetNextPricePlan gate; build Variant ②
8. **Loop ③: COU Agreement Offers** — per `cOu.Agreement.Offers[i]`
9. FE_OR_CCBS read but NOT filtered; build Variant ③; no nxtOfferName gate
10. **Loop ④: COU Subscriber Offers** — per `subscriberCou.SubscriberOffers[i]`
11. Filter: `source == "FE"` required; build Variant ④; NO nxtOfferName gate (unlike Loop ②)
12. If any dispatched: Status="1", SendDataToDB; else SkipActivity("4")
13. On exception: HandleActivityException

---

## §6 — Rule Action (THEN) — Key Design Points

### 4-Variant Fan-out Summary

| Variant | Loop target | nodeLevel | nodeId | FE_OR_CCBS filter | GetNextPricePlan gate | OfferInstanceId | PreExecCheck helper |
|---------|------------|-----------|--------|-------------------|----------------------|-----------------|-------------------|
| ① POU Agreement | pOu.Agreement.Offers | 3 | pOuId | None | No | No | GetXMLForAgreementOffer |
| ② POU Subscriber | subscriberPou.SubscriberOffers | 5 | subId (SubscriberId) | source=="FE" | **Yes** | **Yes** (conditional) | GetXMLForSubscriberOffer |
| ③ COU Agreement | cOu.Agreement.Offers | 3 | couId | None | No | No | GetXMLForAgreementOfferInChildOU |
| ④ COU Subscriber | subscriberCou.SubscriberOffers | 5 | subCouId (SubscriberId) | source=="FE" | No | No | GetXMLForSubscriberOfferInChildOU |

> **[MEDIUM]:** POU Subscriber applies `GetNextPricePlan` gate; COU Subscriber does not. This asymmetry may cause spurious removals for COU subscriber offers that don't have a next price plan scheduled.

### FE_OR_CCBS filter behaviour

All four loops read `FE_OR_CCBS` ExtendedInfo into `source` (default "FE"). Only Subscriber loops (② and ④) gate dispatch on `source=="FE"`. Agreement loops (① and ③) read it but never filter — CCBS-sourced agreement offers are always processed.

### futureSoc semantics

| Field | Value | Meaning |
|-------|-------|---------|
| `ns5:futureSoc/ns5:code` | `"-"` (static) | Remove the next-offer link |
| `ns5:futureSoc/ns5:previousSoc` | `$soc` (Offer.Soc) | The SOC whose future link is cleared |
| `ns5:futureSoc/ns5:instanceId` | `$currSubOffer/OfferInstanceId` (conditional) | Variant ② only — specific offer instance |

### Node levels

| nodeLevel | Meaning | Variants |
|-----------|---------|---------|
| 3 | Agreement / OU level | ① (POU Agreement) and ③ (COU Agreement) |
| 5 | Subscriber level | ② (POU Subscriber) and ④ (COU Subscriber) |

---

## §7 — Data Extraction

| Field | Source | Scope | Notes |
|-------|--------|-------|-------|
| pOuId | `pOu.OUId` | Loop ① | ns3:nodeId (level 3); resubmission skip key |
| pAgreeId | `pOu.Agreement.AgreementId` | Loop ① | Computed, never passed to XSLT — dead ref |
| soc | `pOu.Agreement.Offers[i].Soc` | Loop ① | ns5:previousSoc |
| source | `ExtendedInfo[FE_OR_CCBS].Value` | All loops | Default "FE"; gates Subscriber loops only |
| subId | `subscriberPou.SubscriberId` | Loop ② | ns3:nodeId (level 5) |
| socProps | `subscriberPou.SubscriberOffers[i].SocProperties` | Loop ② | GetNextPricePlan gate input |
| nxtOfferName | `GetNextPricePlan(socProps)` | Loop ② | Dispatch gate — must be non-blank |
| currentOffer | `subscriberPou.SubscriberOffers[i].OfferName` | Loops ②④ | Dead ref — never passed to XSLT |
| currentSocCode | same as soc | Loops ②③④ | Duplicate assignment, dead ref |
| couId | `cOu.OUId` | Loop ③ | ns3:nodeId (level 3) |
| subCouId | `subscriberCou.SubscriberId` | Loop ④ | ns3:nodeId (level 5) |

---

## §8 — System & Integration Dependencies

### §8.1 — ESB / JMS Channel Dependencies

| Direction | Event Type | Dispatch |
|-----------|-----------|----------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_REMOVE_NXTOFR_FROM_PREV_SOC` | `Event.Ext.sendEventImmediate` |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Unconditional — no AllowWriteLog gate |

### §8.2 — Backend API Schema

| NS prefix | Schema URI | Element |
|-----------|-----------|---------|
| ns4 | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureSocCop.xsd` | ns4:futureOrderAll (root) |
| ns3 | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd` | ns3:futureOrder, ns3:nodeLevel, ns3:nodeId |
| ns5 | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureSoc.xsd` | ns5:futureSoc, ns5:code, ns5:previousSoc, ns5:instanceId |

### §8.3 — Global Variable Dependencies

| Path | Usage |
|------|-------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Credential injection gate |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit |
| `$globalVariables/OMX_OM/WritePayload` | Payload guard in audit |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding per Variant

| XSLT Param | ① POU Agreement | ② POU Subscriber | ③ COU Agreement | ④ COU Subscriber |
|-----------|----------------|-----------------|----------------|-----------------|
| `$orderRequest` | orderRequest | orderRequest | orderRequest | orderRequest |
| `$globalVariables` | globalVariables | globalVariables | globalVariables | globalVariables |
| `$pOuId` | pOu.OUId | — | — | — |
| `$subId` | — | subscriberPou.SubscriberId | — | — |
| `$currSubOffer` | — | SubscriberOffers concept | — | — |
| `$couId` | — | — | cOu.OUId | — |
| `$subCouId` | — | — | — | subscriberCou.SubscriberId |
| `$soc` | Offer.Soc | SubscriberOffers.Soc | Offer.Soc | SubscriberOffers.Soc |

### §9.2 — JMS Header Fields (all 4 variants identical)

| Field | Source | Condition |
|-------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | xsl:if |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | xsl:if |
| OrderID | `$orderRequest/OrderData/OrderID` | xsl:if |
| UserName | `$orderRequest/OrderData/User` | IsEnableUserPass='true' AND User present |
| PassWord | `$orderRequest/OrderData/Password` | IsEnableUserPass='true' AND Password present |
| OrderType | `$orderRequest/OrderData/OrderType` | xsl:if |
| **RefID** | — | **ABSENT** — not in any variant |

### §9.3 — Payload Differences Between Variants

| Field | ① POU Agreement | ② POU Subscriber | ③ COU Agreement | ④ COU Subscriber |
|-------|----------------|-----------------|----------------|-----------------|
| ns3:nodeLevel | 3 | 5 | 3 | 5 |
| ns3:nodeId | $pOuId | $subId | $couId | $subCouId |
| ns5:code | "-" | "-" | "-" | "-" |
| ns5:instanceId | absent | $currSubOffer/OfferInstanceId (conditional) | absent | absent |
| ns5:previousSoc | $soc | $soc | $soc | $soc |

### §9.4 — Complete Generated XML Example (Variant ② POU Subscriber)

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-12345</JMSCorrelationID>
    <OrderID>ORD-9876</OrderID>
    <!-- NO RefID -->
    <OrderType>1</OrderType>
    <payload>
      <ns4:futureOrderAll
        xmlns:ns4="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureSocCop.xsd"
        xmlns:ns3="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd"
        xmlns:ns5="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureSoc.xsd">
        <ns3:futureOrder>
          <ns3:nodeLevel>5</ns3:nodeLevel>
          <ns3:nodeId>SUB-001</ns3:nodeId>
        </ns3:futureOrder>
        <ns5:futureSoc>
          <ns5:code>-</ns5:code>
          <ns5:instanceId>INST-42</ns5:instanceId>  <!-- if OfferInstanceId present -->
          <ns5:previousSoc>SOC-PP1</ns5:previousSoc>
        </ns5:futureSoc>
      </ns4:futureOrderAll>
    </payload>
  </event>
</createEvent>
```

### §9.5 — XSLT Stylesheet Source

**Variant ① POU Agreement** — params: orderRequest, globalVariables, pOuId, soc

```xml
<ns4:futureOrderAll>
  <ns3:futureOrder>
    <ns3:nodeLevel>3</ns3:nodeLevel>  <!-- Agreement/OU level -->
    <ns3:nodeId><xsl:value-of select="$pOuId"/></ns3:nodeId>
  </ns3:futureOrder>
  <ns5:futureSoc>
    <ns5:code><xsl:value-of select="&quot;-&quot;"/></ns5:code>
    <ns5:previousSoc><xsl:value-of select="$soc"/></ns5:previousSoc>
    <!-- no ns5:instanceId -->
  </ns5:futureSoc>
</ns4:futureOrderAll>
```

**Variant ② POU Subscriber** — params: orderRequest, globalVariables, subId, currSubOffer, soc — differs from ①: nodeLevel=5, nodeId=$subId, adds conditional instanceId

```xml
<ns3:futureOrder>
  <ns3:nodeLevel>5</ns3:nodeLevel>
  <ns3:nodeId><xsl:value-of select="$subId"/></ns3:nodeId>
</ns3:futureOrder>
<ns5:futureSoc>
  <ns5:code><xsl:value-of select="&quot;-&quot;"/></ns5:code>
  <xsl:if test="$currSubOffer/OfferInstanceId">
    <ns5:instanceId><xsl:value-of select="$currSubOffer/OfferInstanceId"/></ns5:instanceId>
  </xsl:if>
  <ns5:previousSoc><xsl:value-of select="$soc"/></ns5:previousSoc>
</ns5:futureSoc>
```

**Variant ③ COU Agreement** — params: orderRequest, globalVariables, couId, soc — nodeLevel=3, nodeId=couId; no instanceId (same structure as ① but couId)

**Variant ④ COU Subscriber** — params: orderRequest, globalVariables, subCouId, soc — nodeLevel=5, nodeId=subCouId; no instanceId (same as ② minus currSubOffer and instanceId)

All variants share identical JMS header block with IsEnableUserPass credential injection.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event  (no @extId generated)
    ├── JMSPriority         ← $orderRequest/OrderPriority                    [Conditional: xsl:if]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId          [Conditional: xsl:if]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                [Conditional: xsl:if]
    ├── UserName            ← $orderRequest/OrderData/User                   [Credential-gated: IsEnableUserPass='true' AND User]
    ├── PassWord            ← $orderRequest/OrderData/Password               [Credential-gated: IsEnableUserPass='true' AND Password]
    ├── OrderType           ← $orderRequest/OrderData/OrderType              [Conditional: xsl:if]
    ├── — RefID ABSENT from all variants —
    └── payload
        └── ns4:futureOrderAll
            ├── ns3:futureOrder
            │   ├── ns3:nodeLevel    ← 3 (Agreement) or 5 (Subscriber)      [Always — static]
            │   └── ns3:nodeId       ← $pOuId / $subId / $couId / $subCouId [Always]
            └── ns5:futureSoc
                ├── ns5:code         ← "-" (remove literal)                  [Always — static]
                ├── ns5:instanceId   ← $currSubOffer/OfferInstanceId         [Conditional: Variant ② only, if present]
                └── ns5:previousSoc  ← $soc (Offer.Soc)                      [Always]
```

Legend: `[Always]` = unconditional | `[Conditional: ...]` = xsl:if guarded | `[Credential-gated]` = IsEnableUserPass flag

---

## §11 — Audit Logging

Audit log emitted unconditionally after every request dispatch (no AllowWriteLog gate).

| Phase | Field | Value |
|-------|-------|-------|
| Request | ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| Request | PROCESS_ID | `concat($pid, "_REQ")` |
| Request | OPERATION_NAME | "OMX_REMOVE_NXTOFR_FROM_PREV_SOC" |
| Request | AUDIT_TRACE | "Request Sent for OMX_REMOVE_NXTOFR_FROM_PREV_SOC" |
| Request | payload | Conditional: WritePayload="true" |
| Response | PROCESS_ID | `concat($pid, "_RES")` |
| Response | AUDIT_TRACE | "Response received for OMX_REMOVE_NXTOFR_FROM_PREV_SOC" |

---

## §12 — Activity Status Management

| Transition | Code | Trigger |
|-----------|------|---------|
| Running | "1" | At least one offer dispatched |
| Skip | "4" | No qualifying offers across all loops |
| Error | HandleActivityException | Uncaught exception |

---

## §13 — Exception / Error Handling

`try { ... } catch (Exception ae) { HandleActivityException(...); }`. One commented-out `Log.log` debug line in COU Subscriber loop.

---

## §14 — Helper Functions Reference

| Function | Scope | Purpose |
|----------|-------|---------|
| `BRMS.IsBlankOrStringNull(logicalDateRes.LogicalDate)` | Init | Guard for logicalDate parse (result unused) |
| `GetXMLForAgreementOffer(orderRequest, agreeRefId, soc)` | Loop ① | PreExecCheck XML for POU Agreement offer |
| `GetXMLForSubscriberOffer(orderRequest, subRefId, soc)` | Loop ② | PreExecCheck XML for POU Subscriber offer |
| `GetNextPricePlan(socProps)` | Loop ② | Parse SocProperties for scheduled next offer; dispatch gate |
| `BRMS.IsBlankOrStringNull(nxtOfferName)` | Loop ② | Check GetNextPricePlan result |
| `GetXMLForAgreementOfferInChildOU(orderRequest, agreeRefId, soc, pOu.RefId)` | Loop ③ | PreExecCheck XML for COU Agreement offer |
| `GetXMLForSubscriberOfferInChildOU(orderRequest, subRefId, soc, pOu.RefId)` | Loop ④ | PreExecCheck XML for COU Subscriber offer |
| `GetActivityStatusString("1", false)` | Post-loop | Returns "Running" status string |
| `SendDataToDB(orderRequest)` | Post-loop | Persists state |
| `SkipActivity(..., "4")` | Post-loop | Skip handler |
| `HandleActivityException(...)` | Catch | Central exception handler |

---

## §15 — Function Dependency Tree

```text
Request_OMX_REMOVE_NXTOFR_FROM_PREV_SOC.rule
├── Instance.getByExtIdByUri("LogicalDate")  [result unused]
├── BRMS.IsBlankOrStringNull(logicalDateRes.LogicalDate)
│
├── [Loop ①: POU Agreement Offers]
│   ├── source = ExtendedInfo[FE_OR_CCBS].Value  [read but NOT filtered]
│   ├── GetXMLForAgreementOffer(orderRequest, agreeRefId, soc)
│   ├── [if chkRes=="true"]
│   │   ├── Response[ReferenceId==pOu.OUId and CompletionStatus==2]  [NEVER MATCHES: BUG]
│   │   ├── Event.createEvent(Variant ①: nodeLevel=3, nodeId=pOuId, soc)
│   │   ├── Event.Ext.sendEventImmediate(reqEvent)
│   │   ├── RequestCount++  [if !isActResub]
│   │   └── Event.Ext.sendEventImmediate(audit Logger)
│
├── [Loop ②: POU Subscriber Offers]
│   ├── source = ExtendedInfo[FE_OR_CCBS].Value
│   ├── [if chkRes=="true" AND source=="FE"]
│   │   ├── Response[ReferenceId==SubscriberId]  [NEVER MATCHES: BUG]
│   │   ├── GetNextPricePlan(socProps) → nxtOfferName  ← DISPATCH GATE
│   │   ├── BRMS.IsBlankOrStringNull(nxtOfferName)
│   │   ├── [if nxtOfferName not blank]
│   │   │   ├── Event.createEvent(Variant ②: nodeLevel=5, nodeId=subId, OfferInstanceId?)
│   │   │   ├── Event.Ext.sendEventImmediate(reqEvent)
│   │   │   ├── RequestCount++  [if !isActResub]
│   │   │   └── Event.Ext.sendEventImmediate(audit Logger)
│
├── [Loop ③: COU Agreement Offers]
│   ├── source = ExtendedInfo[FE_OR_CCBS].Value  [NOT filtered]
│   ├── GetXMLForAgreementOfferInChildOU(orderRequest, agreeRefId, soc, pOu.RefId)
│   ├── Response[ReferenceId==cOu.OUId]  [NEVER MATCHES: BUG]
│   └── Event.createEvent(Variant ③: nodeLevel=3, nodeId=couId)  [no nxtOfferName gate]
│
├── [Loop ④: COU Subscriber Offers]
│   ├── source = ExtendedInfo[FE_OR_CCBS].Value
│   ├── [if source=="FE"]
│   │   ├── GetXMLForSubscriberOfferInChildOU(orderRequest, subRefId, soc, pOu.RefId)
│   │   ├── Response[ReferenceId==SubscriberId]  [NEVER MATCHES: BUG]
│   │   └── Event.createEvent(Variant ④: nodeLevel=5, nodeId=subCouId)  [NO nxtOfferName gate]
│
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(...)
└── HandleActivityException(...)
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Properties Used |
|---------|-------------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.*, OrderPriority, Customer.ParentOU[], ChildOU[] |
| `Concepts.OrderRequest.OrderElements.ParentOU` | OUId, RefId, Agreement.AgreementId, Agreement.RefId, Agreement.Offers[], ChildOU[], Subscriber[] |
| `Concepts.OrderRequest.OrderElements.ChildOU` | OUId, Agreement.Offers[], Subscriber[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | SubscriberId, RefId, SubscriberOffers[] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Soc, SocProperties, OfferInstanceId, OfferName, ExtendedInfo[FE_OR_CCBS] |
| `Concepts.OM.LogicalDate` | LogicalDate (read, result unused) |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck |
| `Concepts.FM.Response.OMX_RemoveNextOfferFromPrevSocRes` | ResponseCode, ResponseMessage, CompletionStatus (no ReferenceId!) |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|------------|
| R1 | Clear NXTOFR link on previous SOC for qualifying offers across all 4 traversal paths |
| R2 | nodeLevel=3 for Agreement/OU targets; nodeLevel=5 for Subscriber targets |
| R3 | futureSoc.code="-" (static remove signal); futureSoc.previousSoc=Offer.Soc |
| R4 | POU Subscriber loop gated by GetNextPricePlan — only dispatch if next price plan present |
| R5 | POU Subscriber XSLT includes conditional ns5:instanceId from OfferInstanceId |
| R6 | Subscriber loops filter by FE_OR_CCBS=="FE"; Agreement loops do not filter |
| R7 | IsEnableUserPass feature flag supports credential injection in all variants |
| R8 | Audit log unconditionally after every dispatch |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| ReferenceId not mapped in response concept — resubmission skip never fires | [HIGH] | Add ReferenceId mapping (= nodeId) to OMX_RemoveNextOfferFromPrevSocRes XSLT |
| POU Subscriber has GetNextPricePlan gate; COU Subscriber does not — asymmetric | [MEDIUM] | Verify business intent; add gate to COU Subscriber if needed |
| 5 dead variables (futureType, requestedDate, requestedBy, requestedByUser, logicalDate) | [MEDIUM] | Remove dead code; remove LogicalDate lookup if not needed |
| No RefID in JMS event header — downstream correlation without RefID | [MEDIUM] | Add RefID = nodeId to event header |
| Agreement loops do not filter on FE_OR_CCBS — CCBS agreement offers always processed | [MEDIUM] | Verify intent; document explicitly |
| currentOffer, currentSocCode, pAgreeId computed but never passed to XSLT | [LOW] | Remove dead variable assignments |

---

## §18 — Full Source Code (Request Rule)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_REMOVE_NXTOFR_FROM_PREV_SOC {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_REMOVE_NXTOFR_FROM_PREV_SOC";
    orderRequest.ProcessFlow.NextActivityID == "OMX_REMOVE_NXTOFR_FROM_PREV_SOC";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      /* logicalDate lookup — result never used */
      Concepts.OM.LogicalDate logicalDateRes = Instance.getByExtIdByUri("LogicalDate", ...);
      DateTime logicalDate = DateTime.now();   // dead var
      DateTime requestedDate = DateTime.now(); // dead var
      String requestedBy = "OMX";             // dead var
      String requestedByUser = orderRequest.OrderData.Channel; // dead var
      String futureType = "NXTOFR";           // dead var

      boolean isSkipped = true;
      /* Loop ①: POU Agreement Offers — Variant ① XSLT (see §9.5) */
      /* Loop ②: POU Subscriber Offers — source=="FE" filter; GetNextPricePlan gate; Variant ② XSLT */
      /* Loop ③: COU Agreement Offers — Variant ③ XSLT; no source filter; no nxtOfferName gate */
      /* Loop ④: COU Subscriber Offers — source=="FE" filter; Variant ④ XSLT; NO nxtOfferName gate */

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

Creates `OMX_RemoveNextOfferFromPrevSocRes` concept, appends to `currActivity.Response[]`, logs audit unconditionally, returns "true" when "000"-suffix count equals RequestCount. **ReferenceId is not mapped — resubmission skip broken.**

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Audit log |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_REMOVE_NXTOFR_FROM_PREV_SOC` | Response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; fan-in |

### §19.3 — Response Concept Construction

```text
createObject
└── object  @extId ← OMXUtils:generateTrackingID() (XSLT)  [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode       [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg        [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus   [Conditional]
    └── — ReferenceId ABSENT — resubmission skip broken [HIGH] —
```

### §19.4 — Fan-in Completion Logic

| Expression | Value |
|-----------|-------|
| Success count | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` → "true" |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
