# Request_CCBS_UPDATE_SUBSCRIBER

## §1 Overview & Purpose

Updates subscriber offers in the CCBS system. Loops over each subscriber's qualifying offers and sends per-offer update requests. Handles PLG/pooling offer resolution, SOC sequence number assignment, and both POU and COU subscriber types. Used in the SUSWC (soft-suspend) path when `FE_OR_CCBS=OMX`.

Trigger: `ActivityID == "CCBS_UPDATE_SUBSCRIBER"` and `Status == "WAITING"`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPDATE_SUBSCRIBER` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Fan-in | IntraActivitySequencing (per-offer, assertEvent + SendFirstRequestEvent) |
| Backend | CCBS |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — source of all payload data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity tracking — RequestCount |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_UPDATE_SUBSCRIBER"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_UPDATE_SUBSCRIBER"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

### Phase 1 — SOC Pre-build (runs once before outer subscriber loop)

1. Resubmit check → `PurgePendingRequestsBeforeResubmit` if needed
2. Loop POU+COU: build `alSOCs` ArrayList (SOC/PropVal pairs)
3. Process `POOLED_SOC_FOR_*` ExtendedInfo into `plg_pld_socs` HashMap
4. Resolve `POOLED_OFFER_INSTANCE_ID` from `Agreement.ExtendedInfo` using GVs `PoolingIndicator` and `PooledPrefix`
5. If not PLG, set offer instance id to `"NA"`

### Phase 2 — Per-subscriber Event Send

6. Loop POU subscribers + COU subscribers
7. Collect qualifying offers into `subOffersArray` via `GetXMLForSubscriberOfferFilterWithExtendedInfo`
8. Apply offer-level PreExecCheck — skip offers with `ServiceType="80"`
9. If `subOffersArray.length > 0` → build event + `Event.assertEvent` + `ActionRequestEvent`
10. Audit log via `sendEventImmediate(Logger)`
11. `SendFirstRequestEvent` + Status="1" + `SendDataToDB` if any sent; else `SkipActivity("4")`
12. Exception → `HandleActivityException`

> **Dead code note:** `logicalDate` assignment is commented out: `// logicalDateVal = logicalDateRes.LogicalDate`. The field is always sent as `""`.

---

## §7 Data Extraction

Dual POU+COU loop. Per-offer iteration — one CCBS event per qualifying offer per subscriber.

### SOC Resolution

| Step | Logic |
|------|-------|
| Build `alSOCs` | Loop POU+COU; collect SOC/PropVal pairs |
| PLG pooling check | `BRMS.AnyIn(sPooling, propValue)` matches against GV PoolingIndicator |
| POOLED_SOC_FOR_* | Parsed into `plg_pld_socs` HashMap; keyed by SOC name suffix |
| POOLED_OFFER_INSTANCE_ID | Resolved from `Agreement.ExtendedInfo` where prefix matches PooledPrefix GV |
| Non-PLG | `POOLED_OFFER_INSTANCE_ID = "NA"` |
| Split indicator | `GetSplOffIndForSoc(soc)` → `SOC_SEQ_NO` in payload |

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_UPDATE_SUBSCRIBER` | Update subscriber offer state in CCBS |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Per-offer request audit trail |

### §8.3 Backend API

| System | Schema Namespace | Correlation |
|--------|-----------------|-------------|
| CCBS | `http://services.omx.truecorp.co.th/FMServices/updateSubscriberRequest` | IntraActivitySequencing (per-offer) |
| CCBS SequenceValue | `http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/SubscriberServices/SequenceValue/Schema.xsd` | Nested in payload |

### §8.5 ExtendedInfo Fields

| Field | Source | Required? | Usage |
|-------|--------|-----------|-------|
| `FE_OR_CCBS` | Order | Gate | Must be `"OMX"` for this FM to be relevant |
| `POOLED_SOC_FOR_*` | Subscriber offer | Optional | PLG pooling SOC resolution |
| `POOLED_OFFER_INSTANCE_ID` | Agreement | Optional | Resolved from Agreement.ExtendedInfo |
| `ServiceType` | Subscriber offer | Optional | Offers with ServiceType=80 are excluded |

### §8.6 Global Variables

| Path | Usage |
|------|-------|
| `OMX_OM/.../PoolingIndicator` | PLG pooling check via BRMS.AnyIn |
| `OMX_OM/.../PooledPrefix` | POOLED_OFFER_INSTANCE_ID prefix lookup |
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Conditional credentials |
| `OMX_OM/WritePayload` | Conditional payload logging |

---

## §9 Payload Build

### §9.7 Complete Generated XML Example (POU Variant)

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20260101-001</JMSCorrelationID>
    <OrderID>ORD-12345</OrderID>
    <RefID>SUB-REF-001</RefID>
    <OrderType>1</OrderType>
    <payload>
      <ns:updateSubscriberRequest xmlns:ns="http://services.omx.truecorp.co.th/FMServices/updateSubscriberRequest">
        <ns:ChangeSubscriberOffersWithRelatedOffersInputInfo>
          <ns:subscriberReferenceNumber>0812345678</ns:subscriberReferenceNumber>
          <ns:offerName>PROFCVBAR</ns:offerName>
          <ns:action>ADD</ns:action>
          <ns:startDate></ns:startDate>
          <ns:endDate></ns:endDate>
          <ns:logicalDate></ns:logicalDate>
          <ns:ChargeDistribution>
            <ns:shareOwnerNumber>0812345678</ns:shareOwnerNumber>
          </ns:ChargeDistribution>
          <ns:EventDistribution>
            <ns:shareOwnerNumber>0812345678</ns:shareOwnerNumber>
          </ns:EventDistribution>
          <ns:ActivityInfo>
            <ns:activityDate>2026-01-01</ns:activityDate>
            <ns:activityType>OrderManagement</ns:activityType>
          </ns:ActivityInfo>
          <ns:ParameterInfo>
            <ns:SOC_SEQ_NO>1</ns:SOC_SEQ_NO>
            <ns:POOLED_OFFER_INSTANCE_ID>NA</ns:POOLED_OFFER_INSTANCE_ID>
          </ns:ParameterInfo>
        </ns:ChangeSubscriberOffersWithRelatedOffersInputInfo>
      </ns:updateSubscriberRequest>
    </payload>
  </event>
</createEvent>
```

> **Note:** logicalDate is always `""` — the assignment `logicalDateVal = logicalDateRes.LogicalDate` is commented out in source code.

---

## §10 XSLT Field Mapping

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority              [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId    [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID          [Always]
    ├── RefID                ← $refId (per-offer)                       [Always]
    ├── UserName             ← $orderRequest/OrderData/User             [Credential-gated]
    ├── PassWord             ← $orderRequest/OrderData/Password         [Credential-gated]
    ├── OrderType            ← $orderRequest/OrderData/OrderType        [Always]
    └── payload
        └── ns:updateSubscriberRequest
            └── ns:ChangeSubscriberOffersWithRelatedOffersInputInfo
                ├── ns:subscriberReferenceNumber ← $subscriber/MSISDN                  [Always]
                ├── ns:offerName                 ← $offer/OfferName                   [Always]
                ├── ns:action                    ← $offer/Action                      [Always]
                ├── ns:startDate                 ← $offer/StartDate                   [Conditional]
                ├── ns:endDate                   ← $offer/EndDate                     [Conditional]
                ├── ns:logicalDate               ← "" (disabled — see dead code note) [Always: ""]
                ├── ns:ChargeDistribution
                │   └── ns:shareOwnerNumber      ← $OU/ChargeOwner/MSISDN             [Conditional]
                ├── ns:EventDistribution
                │   └── ns:shareOwnerNumber      ← $OU/EventOwner/MSISDN              [Conditional]
                ├── ns:ActivityInfo
                │   ├── ns:activityDate          ← activityDate / EffectiveDate       [Conditional]
                │   └── ns:activityType          ← "OrderManagement"                  [Always: static]
                └── ns:ParameterInfo
                    ├── ns:SOC_SEQ_NO            ← GetSplOffIndForSoc(offerName)      [Always]
                    └── ns:POOLED_OFFER_INSTANCE_ID ← resolved from Agreement        [Always]
```

**Two XSLT variants:**
- **POU variant**: parameters `($OU, $sub)` — uses ParentOU charge/event owner
- **COU variant**: parameters `($OU, $iCOU, $sub)` — uses ChildOU charge/event owner

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_REQ")` |
| OPERATION_NAME | `"CCBS_UPDATE_SUBS"` (abbreviated — not full FM name) |
| AUDIT_TRACE | `concat("Request Sent for RefId ", $refId)` |
| payload | Conditional on WritePayload="true" |

> **Note:** OPERATION_NAME in audit log is `"CCBS_UPDATE_SUBS"` (abbreviated), not `"CCBS_UPDATE_SUBSCRIBER"`.

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → IN_PROGRESS | `subOffersArray.length > 0` for any subscriber | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| WAITING → SKIPPED | No qualifying offers for any subscriber | `SkipActivity("4")` |

---

## §13 Exception Handling

All exceptions → `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §14 Helper Functions

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` | Clear queue on resubmit |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(...)` | Serialize + filter subscriber offers by PreExecCheck |
| `GetSplOffIndForSoc(offerName)` | Returns split-offer indicator → SOC_SEQ_NO |
| `BRMS.AnyIn(sPooling, propValue)` | Checks if offer matches PLG pooling indicator |
| `IntraActivitySequencing.ActionRequestEvent` | Register per-offer request in fan-in tracker |
| `IntraActivitySequencing.SendFirstRequestEvent` | Dispatch first queued event |

---

## §15 Function Dependency Tree

```text
Request_CCBS_UPDATE_SUBSCRIBER
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
│
├── Phase 1 — SOC Pre-build
│   ├── loop POU+COU offers
│   │   └── BRMS.AnyIn(sPooling, propValue)                     [PLG check]
│   └── resolve POOLED_OFFER_INSTANCE_ID from Agreement
│
└── Phase 2 — Per-subscriber send
    ├── GetXMLForSubscriberOfferFilterWithExtendedInfo(...)      [offer filter]
    ├── GetSplOffIndForSoc(offerName)                            [SOC_SEQ_NO]
    ├── Event.createEvent("xslt://CCBS_UPDATE_SUBSCRIBER")       [POU or COU variant]
    ├── Event.assertEvent(reqEvent)
    ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, act)
    ├── Event.Ext.sendEventImmediate(Logger event)
    ├── IntraActivitySequencing.SendFirstRequestEvent(act)       [if !isSkipped]
    ├── GetActivityStatusString("1", false)
    ├── SendDataToDB(orderRequest)
    ├── SkipActivity(orderRequest, act, "4")                     [if isSkipped]
    └── HandleActivityException(...)                             [catch]
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | Two-phase: pre-build SOC list, then per-subscriber send |
| R2 | Dual POU+COU support with separate XSLT variants |
| R3 | PLG pooling resolution from Agreement.ExtendedInfo |
| R4 | Skip offers with ServiceType=80 |
| R5 | Per-offer fan-in — each offer counts as one request |
| R6 | SOC_SEQ_NO from GetSplOffIndForSoc |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| logicalDate always "" (commented-out assignment) | [MEDIUM] | Verify with CCBS if empty logicalDate is acceptable; re-enable if needed |
| PLG pooling resolution depends on GV format matching | [HIGH] | Validate GV PoolingIndicator and PooledPrefix values in target env |
| OPERATION_NAME="CCBS_UPDATE_SUBS" (abbreviated) | [LOW] | Update audit monitoring queries to use the abbreviated name |
| Per-offer fan-in — high cardinality possible | [MEDIUM] | Capacity-test CCBS for burst of parallel offer updates |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPDATE_SUBSCRIBER {
  // author: awalia-t420
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CCBS_UPDATE_SUBSCRIBER";
    orderRequest.ProcessFlow.NextActivityID == "CCBS_UPDATE_SUBSCRIBER";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    // Phase 1: SOC pre-build — build alSOCs/alPropVal ArrayLists,
    //   plg_pld_socs HashMap, resolve POOLED_OFFER_INSTANCE_ID from Agreement
    // Phase 2: POU+COU subscriber loop, per-offer subOffersArray filter
    //   GetXMLForSubscriberOfferFilterWithExtendedInfo (skips ServiceType=80)
    //   Event.createEvent (POU or COU XSLT variant) — see §9 for fields
    //   Event.assertEvent + ActionRequestEvent + sendEventImmediate(Logger)
    // SendFirstRequestEvent + Status="1" / SkipActivity("4")
    //
    // DEAD CODE: logicalDateVal = logicalDateRes.LogicalDate — commented out
  }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

`Response_CCBS_UPDATE_SUBSCRIBER` uses `Concepts.FM.Response.CCBS_UpdateSubscriberRes` (not generic ResponseBase). All 4 response fields use `xsl:if` (conditional). Fan-in via IntraActivitySequencing.

### §19.2 Scope Variables

| Variable | Type |
|----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_SUBSCRIBER` |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` |

> Uses `Concepts.FM.Response.CCBS_UpdateSubscriberRes` — not the generic `ResponseBase`.

### §19.3 ResponseBase Construction

```text
createObject (CCBS_UpdateSubscriberRes)
├── extId            ← OMXUtils.generateTrackingID()           [Always]
├── ResponseCode     ← $eventResponse/ResponseCode             [Conditional: xsl:if]
├── ResponseMessage  ← $eventResponse/ResponseMsg              [Conditional: xsl:if]
├── CompletionStatus ← $eventResponse/CompletionStatus         [Conditional: xsl:if]
└── ReferenceId      ← $eventResponse/RefID                    [Conditional: xsl:if]
```

### §19.4 Response Completion Logic

Fan-in: `IntraActivitySequencing.ActionResponseEvent(currActivity)`

The old `successResponseCount` pattern is commented out. ActionResponseEvent handles per-offer fan-in counting internally.

### §19.5 Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"CCBS_UPDATE_SUBSCRIBER"` |
| AUDIT_TRACE | `"Response received for CCBS_UPDATE_SUBSCRIBER"` (static — no RefId) |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
