# Request_CCBS_CHANGE_PP_SUB

## §1 — Overview & Purpose

Sends `CCBS_UPDATE_SUBSCRIBER` requests to CCBS for each subscriber under ParentOU (SUB) and ChildOU (CSUB) scope, performing the core Price-Plan change.

Payload includes:
- **offersToAdd**: new PP (varNewPP), BRMS non-FUT offers (varAddOffer), ST=85 FE propositions (varPropo)
- **offersToRemove**: old PP (varOldPP), BRMS_REMOVE offers (varRemoveOffer)
- **LogicalResourceInfo**: MIIMSI (multi-SIM), Cloud ID, CCTV Serial
- **PhysicalResourceInfo**: MISIM (multi-SIM SIM), KNOX (device lock)
- **ParameterInfo**: offer parameters propagated to CCBS
- **ActivityInfo**: activity reason + Thai-language userText for future-order scenarios (FUTPP/NXTPP)

On resubmit, pending requests are purged before new ones are sent. After sending, `Event.consumeEvent` is called to explicitly release the request event.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule File | Request_CCBS_CHANGE_PP_SUB.rule |
| Response File | Response_CCBS_CHANGE_PP_SUB.rulefunction |
| Rule Type | rule (event-triggered) |
| Target System | CCBS |
| Event Sent | Events.OMConsumers.OMXFM.Request.CCBS_UPDATE_SUBSCRIBER |
| Response Concept | Concepts.FM.Response.CCBS_UpdateSubscriberRes |
| Iteration Scope | ParentOU Subscribers (iPOUSub) + ChildOU Subscribers (iCOUSub) |
| Resubmit Support | Yes — PurgePendingRequestsBeforeResubmit before new sends |
| Fan-in Type | boolean check: at least one Response code ending "000" |

---

## §3 — Working Memory — Declared Objects

| Variable | Type Path | Role |
|----------|-----------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Master order request |
| orderCurrentActivity | Concepts.OM.ProcessConfig.Activity | Current activity in process config |
| logicalDate | Concepts.OrderRequest.LogicalDate | Logical date (declared but NOT passed to XSLT) |

---

## §4 — Rule Conditions (WHEN)

Standard OMXFM rule activation — triggered when the activity scheduler assigns `CCBS_CHANGE_PP_SUB` to the current activity and the order is in the correct state.

---

## §5 — Execution Flow Diagram

1. PreExecCheck gate → `GetXMLForSubscriber(orderRequest, subRefId)`; skip if condition not met
2. Resubmit check → if resubmit: call `PurgePendingRequestsBeforeResubmit`
3. POU loop (iPOUSub = 0 … pOUSubLen-1): for each ParentOU subscriber, build & send CCBS_UPDATE_SUBSCRIBER
4. COU loop (iCOUSub = 0 … cOUSubLen-1 **[bug: was pOUSubLen]**): for each ChildOU subscriber, build & send
5. Per-subscriber: pre-count qualifying offers → build XSLT event → sendEventImmediate → consumeEvent → RequestCount++ → Status="1" → SendDataToDB
6. Post-loop: if isSkipped → SkipActivity("4")

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### Resubmit Handling

```java
if (isResubmit) {
    IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
}
```

### Pre-counts (passed to XSLT as params)

```java
// Qualifying offers: ServiceType != '86' AND FE_OR_CCBS != 'BRMS_REMOVE'
countSubscriberOfers = count(SubscriberOffers[ServiceType!='86' and FE_OR_CCBS!='BRMS_REMOVE'])
countRelatedOffersArray = count of RelatedOffersArray from those same qualifying offers
// Used for SOC_SEQ_NO increment
incrementByCount = countSubscriberOfers + countRelatedOffersArray
```

### XSLT Variables

| Variable | XPath Filter | Purpose |
|----------|-------------|---------|
| varNewPP | `SubscriberOffers[ServiceType='80' and FE_OR_CCBS='FE']` | New PP to ADD |
| varOldPP | `SubscriberOffers[ServiceType='80' and FE_OR_CCBS='CCBS']` | Old PP to REMOVE |
| varRemoveOffer (POU) | `SubscriberOffers[ServiceType!='80' and ServiceType!='88' and FE_OR_CCBS='BRMS_REMOVE']` | BRMS offers to remove (POU) |
| varRemoveOffer (COU) | `SubscriberOffers[ServiceType!='80' and FE_OR_CCBS='BRMS_REMOVE']` | BRMS offers to remove (COU — no !=88 filter) |
| varAddOffer | `SubscriberOffers[ServiceType!='80' and ServiceType!='86' and FE_OR_CCBS='BRMS' and EFF_TYPE!='FUT']` | BRMS non-future offers to add |
| varPropo | `SubscriberOffers[ServiceType='85' and FE_OR_CCBS='FE']` | ST=85 FE propositions |

### Post-Send per Subscriber

```java
Event.consumeEvent(reqEvent)   // explicit event consumption (unusual)
orderCurrentActivity.RequestCount++
subscriber.Status = "1"
OMXDBUtils.SendDataToDB(orderRequest, subscriber, orderCurrentActivity)
```

---

## §7 — Data Extraction

The XSLT partitions subscriber offers into four named variable sets based on `ServiceType` and `FE_OR_CCBS` flags, then uses them independently for offersToAdd, offersToRemove, LogicalResourceInfo, and ParameterInfo sections.

> **Note:** POU varRemoveOffer explicitly excludes ServiceType=88, while COU variant does not — intentional asymmetry or minor inconsistency.

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Triggered for **CHANGE_PP** order type when subscriber-level price plan change is required. Covers both ParentOU and ChildOU subscriber hierarchies. Activated for both immediate and future-order (NXTPP/FUTPP) scenarios.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Purpose |
|-----------|---------|-------------|---------|
| [OUTBOUND] | OMX-FM ESB channel | CCBS_UPDATE_SUBSCRIBER queue | Send UpdateSubscriber request to CCBS |
| [INBOUND] | OMX-FM ESB channel | Response queue | Receive UpdateSubscriber response from CCBS |
| [OUTBOUND] | ESB Logger channel | Audit log destination | Request and response audit logging |

### §8.3 Backend API Details

| System | Operation | Root Element | Namespace |
|--------|-----------|-------------|-----------|
| CCBS | UpdateSubscriber | ns:UpdateSubscriberRequest | www.ccbs.com/subscriber |
| CCBS (Sequence) | GetSequenceValue | ns1:GetSequenceValueRequest | www.ccbs.com/sequence |

### §8.4 BE Working Memory Dependencies

| Concept | Field | Access |
|---------|-------|--------|
| OrderRequest | OrderData.OMXTrackingId, OrderData.CES, OrderData.UserText | Read |
| Subscriber | SubRefId, SubscriberOffers[], SubscriberActivityInfo, ExtendedInfo | Read / Write (Status, ExtendedInfo CHANGE_PP) |
| SubscriberOffers | ServiceType, FE_OR_CCBS, EFF_TYPE, Soc, EffectiveDate, ExpiryDate, RelatedOffersArray, ParameterInfo, OfferInstanceId | Read |
| Activity | RequestCount, Response[] | Write |

### §8.5 ExtendedInfo Fields Required

| Name | Required? | Where Used |
|------|-----------|-----------|
| TR_MULTISIM_IND | Conditional | LogicalResourceInfo MIIMSI, PhysicalResourceInfo MISIM — when value='RES' |
| Related IMSI | Conditional | LogicalResourceInfo MIIMSI values |
| Related SIM | Conditional | PhysicalResourceInfo MISIM values |
| IMEI_KNOX | Conditional | PhysicalResourceInfo KNOX values |
| SocProperties | Conditional | RelatedOffersArray Cloud ID (CLOID) and CCTV (RSCTV) detection |
| TR_CONTRACT_IND | Conditional | varPropo RelatedOffersArray ParameterInfo — when value='Y' |
| FUT_TYPE | Conditional | ActivityInfo userText — NXTPP or FUTPP adds Thai text |

### §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Controls payload inclusion in audit log |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| XSLT Param | Bound From | Notes |
|-----------|-----------|-------|
| orderRequest | orderRequest concept | Full order request XML |
| subscriber | subscriber concept (per iteration) | Current POU/COU subscriber |
| subRefId | subscriber.SubRefId | Subscriber reference ID |
| countSubscriberOfers | computed pre-count | count(ST!='86' and FE_OR_CCBS!='BRMS_REMOVE') |
| countRelatedOffersArray | computed pre-count | count of RelatedOffersArray from qualifying offers |
| logicalDate | logicalDate concept | Declared but NOT used in XSLT payload |

### §9.4 Payload Root Element

```xml
<ns:UpdateSubscriberRequest>
  <ns1:GetSequenceValueRequest>
    <ns1:sequenceName>SOC_SEQ_NO</ns1:sequenceName>
    <ns1:incrementByCount>$countSubscriberOfers + $countRelatedOffersArray</ns1:incrementByCount>
  </ns1:GetSequenceValueRequest>
  <ns:UpdateSubscriberRequest>  <!-- inner element, same tag as outer -->
    <!-- SubscriberIdInfo, ChangeSubscriberOffersWithRelatedOffersInputInfo, ActivityInfo -->
  </ns:UpdateSubscriberRequest>
</ns:UpdateSubscriberRequest>
```

### §9.5 offersToAdd Structure

| Source Variable | Fields Emitted | Notes |
|----------------|---------------|-------|
| varNewPP (ST=80, FE) | effectiveDate, name, refId=position(), RelatedOffersArray, ParameterInfo | New price plan |
| varAddOffer (BRMS, non-FUT) | effectiveDate, expirationDate, name, refId=position() | BRMS addon offers |
| varPropo (ST=85, FE) | effectiveDate, expirationDate, name, refId=@Id, RelatedOffersArray[TR_CONTRACT_IND=Y], ParameterInfo | FE propositions |

### §9.6 offersToRemove / LogicalResourceInfo / PhysicalResourceInfo

| Resource | Trigger | Values Source | ID Field |
|----------|---------|-------------|---------|
| varOldPP | always | Soc, Soc | — |
| varRemoveOffer | BRMS_REMOVE filter | Soc, Soc | — |
| MIIMSI | TR_MULTISIM_IND=RES AND FE | ParameterInfo[Related IMSI]/ValuesArray | offerInstanceId |
| Cloud ID | SocProperties contains CLOID | concat(MSISDN,"-",MatSerialRefId) | offerRefId=@Id |
| CCTV Serial | SocProperties contains RSCTV | MatSerialRefId | offerRefId=@Id |
| MISIM | TR_MULTISIM_IND=RES AND FE | ParameterInfo[Related SIM]/ValuesArray | offerInstanceId |
| KNOX | IMEI_KNOX present AND FE | ExtendedInfo[IMEI_KNOX]/Value | offerInstanceId; baseName=Soc |

### §9.6d ActivityInfo

| Field | Logic |
|-------|-------|
| activityReason | `SubscriberActivityInfo/ActivityReason` if length>0; else "CREQ" |
| userText | if FUT_TYPE='NXTPP' or 'FUTPP' → `concat(UserText, ';เปลี่ยน PP โดย omx future order', ';isServiceChangeOnPSUSAllowed=true;')` else `concat(UserText, ';isServiceChangeOnPSUSAllowed=true;')` |

> ActivityInfo appears TWICE: inside `ChangeSubscriberOffersWithRelatedOffersInputInfo` and at the top level of the inner `UpdateSubscriberRequest`.

### §9.8 XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:ns="www.ccbs.com/subscriber"
  xmlns:ns1="www.ccbs.com/sequence"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="subscriber"/>
  <xsl:param name="subRefId"/>
  <xsl:param name="countSubscriberOfers"/>
  <xsl:param name="countRelatedOffersArray"/>
  <xsl:variable name="varNewPP"
    select="$subscriber/SubscriberOffers[ServiceType='80' and FE_OR_CCBS='FE']"/>
  <xsl:variable name="varOldPP"
    select="$subscriber/SubscriberOffers[ServiceType='80' and FE_OR_CCBS='CCBS']"/>
  <xsl:variable name="varAddOffer"
    select="$subscriber/SubscriberOffers[ServiceType!='80' and ServiceType!='86'
            and FE_OR_CCBS='BRMS' and EFF_TYPE!='FUT']"/>
  <xsl:variable name="varRemoveOffer"
    select="$subscriber/SubscriberOffers[ServiceType!='80' and ServiceType!='88'
            and FE_OR_CCBS='BRMS_REMOVE']"/>
  <!-- COU variant: ServiceType!='80' only (no !=88 exclusion) -->
  <xsl:variable name="varPropo"
    select="$subscriber/SubscriberOffers[ServiceType='85' and FE_OR_CCBS='FE']"/>
  <xsl:template match="/">
    <createEvent>
      <event>
        <!-- Audit headers: ESBUUID, PROCESS_ID, OPERATION_NAME, AUDIT_TRACE, CES -->
        <payload>
          <ns:UpdateSubscriberRequest>
            <ns1:GetSequenceValueRequest>
              <ns1:sequenceName>SOC_SEQ_NO</ns1:sequenceName>
              <ns1:incrementByCount>
                <xsl:value-of select="$countSubscriberOfers + $countRelatedOffersArray"/>
              </ns1:incrementByCount>
            </ns1:GetSequenceValueRequest>
            <ns:UpdateSubscriberRequest>
              <ns:SubscriberIdInfo><!-- MSISDN, SubscriberId from subscriber --></ns:SubscriberIdInfo>
              <ns:ChangeSubscriberOffersWithRelatedOffersInputInfo>
                <ns:offersToAdd>
                  <!-- xsl:for-each varNewPP (with RelatedOffersArray, ParameterInfo) -->
                  <!-- xsl:for-each varAddOffer -->
                  <!-- xsl:for-each varPropo (with RelatedOffersArray[TR_CONTRACT_IND=Y], ParameterInfo) -->
                </ns:offersToAdd>
                <ns:offersToRemove>
                  <!-- varOldPP + xsl:for-each varRemoveOffer -->
                </ns:offersToRemove>
                <ns:LogicalResourceInfo><!-- MIIMSI, CloudID, CCTV --></ns:LogicalResourceInfo>
                <ns:PhysicalResourceInfo><!-- MISIM, KNOX --></ns:PhysicalResourceInfo>
                <ns:ParameterInfo><!-- varNewPP, varAddOffer, varPropo parameters --></ns:ParameterInfo>
                <ns:ActivityInfo>
                  <ns:activityReason><!-- SubscriberActivityInfo/ActivityReason or "CREQ" --></ns:activityReason>
                  <ns:userText><!-- conditional Thai text for FUTPP/NXTPP --></ns:userText>
                </ns:ActivityInfo>
              </ns:ChangeSubscriberOffersWithRelatedOffersInputInfo>
              <ns:ActivityInfo><!-- duplicate at top level --></ns:ActivityInfo>
            </ns:UpdateSubscriberRequest>
          </ns:UpdateSubscriberRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── ESBUUID              ← $orderRequest/OrderData/OMXTrackingId              [Conditional: if OMXTrackingId]
    ├── PROCESS_ID           ← concat($pid,"_REQ")                                [Always]
    ├── OPERATION_NAME       ← "CCBS_CHANGE_PP_SUB"                              [Always]
    ├── AUDIT_TRACE          ← "Request Sent for CCBS_CHANGE_PP_SUB"             [Always]
    ├── CES                  ← $orderRequest/OrderData/CES                        [Conditional: if CES]
    └── payload              ← copy of event (Conditional: WritePayload="true")   [Credential-gated]
        └── ns:UpdateSubscriberRequest
            ├── ns1:GetSequenceValueRequest
            │   ├── ns1:sequenceName          ← "SOC_SEQ_NO"                     [Always]
            │   └── ns1:incrementByCount      ← countSubscriberOfers + countRelatedOffers [Always]
            └── ns:UpdateSubscriberRequest (inner)
                ├── ns:SubscriberIdInfo       ← $subscriber/SubscriberIdInfo     [Always]
                └── ns:ChangeSubscriberOffersWithRelatedOffersInputInfo
                    ├── ns:offersToAdd
                    │   ├── offer [varNewPP] ← Soc, EffectiveDate, position()    [Conditional: if varNewPP]
                    │   │   └── RelatedOffersArray                               [Conditional]
                    │   ├── offer [varAddOffer] ← Soc, EffectiveDate, ExpiryDate [Conditional: if varAddOffer]
                    │   └── offer [varPropo] ← Soc, EffectiveDate, ExpiryDate, @Id [Conditional: if varPropo]
                    │       └── RelatedOffersArray [TR_CONTRACT_IND=Y]           [Conditional]
                    ├── ns:offersToRemove
                    │   ├── offer [varOldPP]     ← Soc, Soc                      [Conditional]
                    │   └── offer [varRemoveOffer] ← Soc, Soc (for-each)         [Conditional]
                    ├── ns:LogicalResourceInfo
                    │   ├── MIIMSI   [TR_MULTISIM_IND=RES AND FE]                [Conditional]
                    │   ├── Cloud ID [SocProperties contains CLOID]              [Conditional]
                    │   └── CCTV    [SocProperties contains RSCTV]               [Conditional]
                    ├── ns:PhysicalResourceInfo
                    │   ├── MISIM  [TR_MULTISIM_IND=RES AND FE]                  [Conditional]
                    │   └── KNOX   [IMEI_KNOX present AND FE]                    [Conditional]
                    ├── ns:ParameterInfo (per offer variable)                     [Conditional]
                    └── ns:ActivityInfo (inside ChangeSubscriberOffers)           [Always]
                        ├── activityReason ← SubscriberActivityInfo or "CREQ"    [Always]
                        └── userText       ← concat(UserText, ...) [+Thai if FUTPP/NXTPP] [Always]
                ns:ActivityInfo (top-level duplicate)                             [Always]
```

**Legend:** `[Always]` = always emitted · `[Conditional: expr]` = xsl:if / xsl:for-each · `[Credential-gated]` = WritePayload="true" guard

---

## §11 — Audit Logging

| Field | Request Value | Response Value |
|-------|--------------|---------------|
| OPERATION_NAME | CCBS_CHANGE_PP_SUB | CCBS_CHANGE_PP_SUB |
| AUDIT_TRACE | Request Sent for CCBS_CHANGE_PP_SUB | Response received for CCBS_CHANGE_PP_SUB |
| PROCESS_ID | concat($pid, "_REQ") | concat($pid, "_RES") |
| payload | Conditional on WritePayload="true" | Conditional on WritePayload="true" |

---

## §12 — Activity Status Management

| Action | Status Value | When |
|--------|-------------|------|
| subscriber.Status = "1" | 1 (Processing) | After each subscriber event sent |
| RequestCount++ | N/A | After each subscriber event sent |
| SkipActivity("4") | 4 (Skipped) | If isSkipped at end of loop |

---

## §13 — Exception / Error Handling

Standard OMXFM exception pattern: `HandleActivityException` called on exception. Response returns `"false"` if no response code ending in "000" found.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| GetXMLForSubscriber(orderRequest, subRefId) | PreExecCheck gate |
| IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity) | Clears pending requests on resubmit |
| OMXDBUtils.SendDataToDB(orderRequest, subscriber, activity) | Persists state to database |
| OMXUtils.generateTrackingID() | Generates unique tracking/extId values |
| SkipActivity(statusCode) | Marks activity as skipped |
| Event.consumeEvent(reqEvent) | Explicitly consumes request event after send (unusual) |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_CHANGE_PP_SUB (rule)
├── GetXMLForSubscriber(orderRequest, subRefId)         [PreExecCheck]
├── IntraActivitySequencing
│   └── PurgePendingRequestsBeforeResubmit(activity)   [resubmit]
├── Event.createEvent(xslt://CCBS_UPDATE_SUBSCRIBER)   [per subscriber]
├── Event.Ext.sendEventImmediate(event)
├── Event.consumeEvent(reqEvent)                        [explicit consume]
├── OMXDBUtils.SendDataToDB(...)
└── SkipActivity("4")

Response_CCBS_CHANGE_PP_SUB (rulefunction)
├── Instance.createInstance(xslt://CCBS_UpdateSubscriberRes)
├── Instance.getByExtIdByUri("SUB:...")                 [POU lookup]
├── Instance.getByExtIdByUri("CSUB:...")                [COU fallback]
├── Instance.createInstance(xslt://SubscriberExtendedInfo)  [CHANGE_PP=Y]
├── Event.Ext.sendEventImmediate(xslt://Logger)
└── XPath.evalAsBoolean(boolean(Response[code "000"]))
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Fields |
|---------|-----------|
| Concepts.FM.Response.CCBS_UpdateSubscriberRes | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, SocInstance[] (OfferInstanceId, Soc) |
| Concepts.OrderRequest.OrderElements.Subscriber | SubRefId, Status, SubscriberOffers[], ExtendedInfo[], SubscriberActivityInfo |
| Concepts.OrderRequest.OrderElements.SubscriberOffers | ServiceType, FE_OR_CCBS, EFF_TYPE, Soc, EffectiveDate, ExpiryDate, RelatedOffersArray[], ParameterInfo[], OfferInstanceId |
| Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo | Name, Value |
| Concepts.OrderRequest.LogicalDate | Date (not passed to XSLT) |

---

## §17 — Migration Notes & Recommendations

**R1**: Must send UpdateSubscriber to CCBS for every active subscriber (POU and COU).
**R2**: Must increment SOC_SEQ_NO by (qualifyingOffers + relatedOffers) per subscriber.
**R3**: Must propagate all LogicalResourceInfo and PhysicalResourceInfo to CCBS.
**R4**: Must add Thai future-order text to ActivityInfo userText for FUTPP/NXTPP scenarios.
**R5**: On resubmit, must purge previous pending requests before sending new ones.
**R6**: Response must map NewOfferInstanceId back to SubscriberOffers and RelatedOffersArray.
**R7**: Response must set ExtendedInfo CHANGE_PP=Y on subscriber after successful update.

| Risk | Severity | Mitigation |
|------|----------|-----------|
| COU loop uses `pOUSubLen` instead of `cOUSubLen` | [HIGH] | Fix loop bound to use correct COU subscriber count |
| POU varRemoveOffer excludes ST=88 but COU does not | [MEDIUM] | Align filters or document intentional difference |
| POU varNewPP ParameterInfo loop appears twice (possible duplicate) | [MEDIUM] | Verify and deduplicate in source XSLT |
| ActivityInfo appears twice in payload | [LOW] | Verify CCBS schema accepts both positions |
| logicalDate declared in scope but not used in XSLT | [INFO] | Remove from scope if truly unused |
| Event.consumeEvent called explicitly after each send | [LOW] | Verify correct event lifecycle pattern for CCBS |

---

## §18 — Full Source Code (Request Rule)

```java
/**
 * Request_CCBS_CHANGE_PP_SUB.rule
 * Sends CCBS_UPDATE_SUBSCRIBER for each POU and COU subscriber to perform PP change
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_CHANGE_PP_SUB {
  attribute {
    priority = 0;
    forwardChain = true;
  }
  scope {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    Concepts.OrderRequest.LogicalDate logicalDate; // declared but not passed to XSLT
  }
  when { /* Standard OMXFM activation conditions */ }
  then {
    // === Resubmit handling ===
    if (isResubmit) {
      IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
    }
    // === POU Subscriber loop ===
    int pOUSubLen = orderRequest.OrderData.ParentOU.Subscriber@length;
    for (int iPOUSub = 0; iPOUSub < pOUSubLen; iPOUSub++) {
      String subRefId = orderRequest.OrderData.ParentOU.Subscriber[iPOUSub].SubRefId;
      Concepts.OrderRequest.OrderElements.Subscriber subscriber =
        Instance.getByExtIdByUri("SUB:" + orderRequest.OrderData.OMXTrackingId + ":" + subRefId,
                                 "/Concepts/OrderRequest/OrderElements/Subscriber");
      // PreExecCheck gate: GetXMLForSubscriber(orderRequest, subRefId)
      int countSubscriberOfers = ...; // count(ST!='86' and FE_OR_CCBS!='BRMS_REMOVE')
      int countRelatedOffersArray = ...;
      Events.OMConsumers.OMXFM.Request.CCBS_UPDATE_SUBSCRIBER reqEvent =
        Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/CCBS_UPDATE_SUBSCRIBER}}"
          /* [XSLT builds full UpdateSubscriberRequest — see §9.8 for payload details] */
          /* offersToAdd: varNewPP + varAddOffer + varPropo                           */
          /* offersToRemove: varOldPP + varRemoveOffer                                */
          /* LogicalResourceInfo: MIIMSI + CloudID + CCTV                            */
          /* PhysicalResourceInfo: MISIM + KNOX                                      */
          /* ParameterInfo + ActivityInfo (Thai text for FUTPP/NXTPP)                */
        );
      Event.Ext.sendEventImmediate(reqEvent);
      Event.consumeEvent(reqEvent); // explicit consume — unusual pattern
      orderCurrentActivity.RequestCount++;
      subscriber.Status = "1";
      OMXDBUtils.SendDataToDB(orderRequest, subscriber, orderCurrentActivity);
    }
    // === COU Subscriber loop ===
    for (int iCOUSub = 0; iCOUSub < pOUSubLen; iCOUSub++) { // BUG: should be cOUSubLen
      String subRefId = orderRequest.OrderData.ChildOU[iCOUSub].Subscriber[0].SubRefId;
      Concepts.OrderRequest.OrderElements.Subscriber subscriber =
        Instance.getByExtIdByUri("CSUB:" + orderRequest.OrderData.OMXTrackingId + ":" + subRefId,
                                 "/Concepts/OrderRequest/OrderElements/Subscriber");
      // Same send pattern as POU — varRemoveOffer filter differs (no !=88 exclusion)
    }
    if (isSkipped) { SkipActivity("4"); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

Handles each incoming `CCBS_UPDATE_SUBSCRIBER` response. Parses the CCBS reply into a `CCBS_UpdateSubscriberRes` concept, maps `NewOfferInstanceId` values back to `SubscriberOffers` and `RelatedOffersArray`, creates a `CHANGE_PP=Y` ExtendedInfo marker on the subscriber, and returns success/failure.

### §19.2 Scope Variables

| Variable | Type Path | Role |
|----------|-----------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Master order request |
| eventResponse | Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_SUBSCRIBER | Raw CCBS response event |
| currActivity | Concepts.OM.ProcessConfig.Activity | Current activity for fan-in tracking |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId           ← ns:generateTrackingID()                 [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode              [Conditional: if ResponseCode]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg               [Conditional: if ResponseMsg]
    ├── CompletionStatus ← $eventResponse/CompletionStatus          [Conditional: if CompletionStatus]
    ├── ReferenceId      ← $eventResponse/RefID                     [Conditional: if RefID]
    └── SocInstance      [xsl:for-each ClosedAndReopenedOffers]     [Conditional: per CCBS offer]
        ├── @extId       ← ns:generateTrackingID()                  [Always]
        ├── OfferInstanceId ← ns1:NewOfferInstanceId                [Conditional: if NewOfferInstanceId]
        └── Soc          ← ns1:Soc                                  [Conditional: if Soc]
```

**SocInstance Mapping Logic (post-construction):**

```java
// Subscriber lookup: primary POU, fallback COU
subscriber = Instance.getByExtIdByUri("SUB:"+OMXTrackingId+":"+eventResponse.RefID, ...)
if (subscriber == null)
    subscriber = Instance.getByExtIdByUri("CSUB:"+OMXTrackingId+":"+eventResponse.RefID, ...)

if (subscriber != null && activityRes.SocInstance != null) {
    for each SocInstance[i] {
        for each SubscriberOffers[j] {
            if (SocInstance[i].Soc == SubscriberOffers[j].Soc && OfferInstanceId==0)
                → set OfferInstanceId = SocInstance[i].OfferInstanceId; break;
            for each RelatedOffersArray[k] {
                if (SocInstance[i].Soc == RelatedOffersArray[k].Soc && OfferInstanceId==0)
                    → set RelatedOffersArray[k].OfferInstanceId; break;
            }
        }
    }
    // Append CHANGE_PP=Y ExtendedInfo to subscriber
    changePPExt = Instance.createInstance(xslt://SubscriberExtendedInfo, Name="CHANGE_PP", Value="Y")
    subscriber.ExtendedInfo[length] = changePPExt;
}
```

### §19.4 Response Completion Logic

| Check | Expression | Result |
|-------|-----------|--------|
| Success check | `boolean($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` | true if ANY response has code ending "000" |
| Return true | isSuccess == true | "true" — at least one successful response |
| Return false | isSuccess == false | "false" — no successful responses yet |

> **Note:** Unlike typical CCBS fan-in patterns (`count(Response[code "000"]) == RequestCount`), this uses `boolean(...)` — returns "true" if ANY response succeeded, not when ALL subscribers are done. Fan-in completion may be handled at a higher orchestration level.

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| OPERATION_NAME | "CCBS_CHANGE_PP_SUB" (static) |
| AUDIT_TRACE | "Response received for CCBS_CHANGE_PP_SUB" (static) |
| PROCESS_ID | concat($pid, "_RES") |
| ESBUUID | $orderRequest/OrderData/OMXTrackingId (conditional) |
| payload/ns:ServicePayload | copy of $eventResponse (conditional on WritePayload="true") |

### §19.6 Response XSLT Source

```xml
<xsl:stylesheet
  xmlns:ns1="http://services.omx.truecorp.co.th/FMServices/updateSubscriberResponse"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="www.tibco.com/be/custom/OMXUtils"
  version="1.0"
  exclude-result-prefixes="ns1 xsl ns xsd">
  <xsl:output method="xml"/>
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId">
          <xsl:value-of select="ns:generateTrackingID()"/>
        </xsl:attribute>
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
        <xsl:for-each select="$eventResponse/payload
          /ns1:UpdateSubscriber/ns1:UpdateSubscriberResponse
          /ns1:SubscriberServicesUpdateSubscriberOutputInfo/ns1:ClosedAndReopenedOffers">
          <SocInstance>
            <xsl:attribute name="extId">
              <xsl:value-of select="ns:generateTrackingID()"/>
            </xsl:attribute>
            <xsl:if test="ns1:NewOfferInstanceId">
              <OfferInstanceId><xsl:value-of select="ns1:NewOfferInstanceId"/></OfferInstanceId>
            </xsl:if>
            <xsl:if test="ns1:Soc">
              <Soc><xsl:value-of select="ns1:Soc"/></Soc>
            </xsl:if>
          </SocInstance>
        </xsl:for-each>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
