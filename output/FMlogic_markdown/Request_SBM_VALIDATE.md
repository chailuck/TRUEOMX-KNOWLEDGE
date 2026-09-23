# Request_SBM_VALIDATE

> TIBCO BusinessEvents FM Logic — SBM Subscriber Validation Request

**Rule type:** OMXFM Request | **Backend:** SBM (Subscriber Management) | **Priority:** 5 | **Pattern:** Fan-out per Subscriber (POU + COU)

---

## §1 — Overview & Purpose

`Request_SBM_VALIDATE` invokes the SBM (Subscriber Management) system's `doServiceArray` operation to validate subscriber service state. It fires one request per subscriber (both POU and COU) with function_id `100200001`.

The rule implements a smart **channel selection strategy**: for batch orders it uses the dedicated SBM batch channel; for ATS-sourced offers it uses the ATS channel; for POU subscribers it checks for an explicit `SBM_CHANNEL` override in order extended info; otherwise it falls back to the order's standard channel.

Each request is queued via `IntraActivitySequencing` to maintain ordered dispatch. The rule also handles **re-submission** (purges pending requests before re-queuing) and evaluates a per-subscriber `PreExecCheck` gate to conditionally skip ineligible subscribers.

> **Key architectural note:** COU subscribers have a *simplified* channel selection — the `SBM_CHANNEL` override branch is absent in the COU XSLT variant. Only BATCH and ATS paths are checked before defaulting to `OrderData/Channel`.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_SBM_VALIDATE` |
| Rule type | OMXFM Request Rule |
| Priority | 5 |
| Forward Chain | true |
| Author | RS33-BANDIT |
| Backend system | SBM — Subscriber Management |
| Event type | `Events.OMConsumers.OMXFM.Request.SBM_DO_SERVICE` |
| Response type | `Events.OMConsumers.OMXFM.Response.SBM_DO_SERVICE` |
| SBM function_id | `100200001` (validate service) |
| Fan-out pattern | Per subscriber — POU loop + COU nested loop |
| Sequencing | `IntraActivitySequencing` (ordered dispatch) |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order concept; holds all order data, subscriber lists, and extended info |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process activity; holds Response array and RequestCount |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance must match the process flow pointer |
| 2 | `orderCurrentActivity.ActivityID == "SBM_VALIDATE"` | Must be the SBM_VALIDATE activity type |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SBM_VALIDATE"` | Process flow is pointing at SBM_VALIDATE |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be idle before dispatching requests |

---

## §5 — Execution Flow Diagram

```
1. Re-submission check → if RequestCount>0 AND IsOrderResubmitted → PurgePendingRequestsBeforeResubmit
2. Batch detection → XPath eval: OrderData/IntegrationMethod = 'BATCH' → boolean isBatch
3. Read PreExecCheck → chkXPath = nextAct.PreExecCheck
4. POU subscriber loop (ParentOU[i].Subscriber[j])
   4a. Skip if Response already has CompletionStatus==2 for this RefId
   4b. Evaluate PreExecCheck → GetXMLForSubscriber → XPath.execute
   4c. If passes: build SBM_DO_SERVICE event (POU XSLT), assert, queue via ActionRequestEvent
   4d. Send request audit log
5. COU subscriber loop (ParentOU[i].ChildOU[k].Subscriber[j])
   5a. Same skip + gate logic using GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)
   5b. Build SBM_DO_SERVICE event (COU XSLT — no SBM_CHANNEL override)
6. If !isSkipped → SendFirstRequestEvent → Status="1" (PROCESSING) → SendDataToDB
7. If isSkipped → SkipActivity(orderRequest, activity, "4")
8. Exception → HandleActivityException
```

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

**Re-submission guard:**
```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
if(isActResub) {
    RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
}
```

**Batch detection:**
```java
boolean isBatch = XPath.evalAsBoolean("xpath://$orderRequest/OrderData/IntegrationMethod = 'BATCH'");
```

**Per-subscriber dispatch (POU):**
```java
for (int i = 0; i < pOuLen; i++) {
    for(int j = 0; j < pSubLen; j++) {
        // Skip if response already received with CompletionStatus==2
        for(int iResp = 0; iResp < Response@length; iResp++) {
            if(Response[iResp].ReferenceId == pSubRefId && Response[iResp].CompletionStatus == 2)
                reqSuccess = true;
        }
        if(!reqSuccess) {
            // Evaluate PreExecCheck via GetXMLForSubscriber
            String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, pSubRefId);
            String chkRes = XPath.execute("/(chkXPath)", sXML, "ns0=...");
            if(chkRes == "true") {
                // Build & assert SBM_DO_SERVICE event (POU variant)
                Event.assertEvent(reqEvent);
                IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                isSkipped = false;
            }
        }
    }
}
```

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in `POSTPAID_REMOVE_OFFER_SUB` at step 18 (`SBM_VALIDATE`) and step 43 (`SBM_VALIDATE_ATS`). The ATS-step variant uses the same rule but the ATS channel path is triggered by the `FE_OR_CCBS=ATS` extended info flag.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel URI | Event Type | Purpose |
|-----------|-------------|------------|---------|
| [OUTBOUND] | JMS → `/Channels/OMXFMConnectionRequest` | `SBM_DO_SERVICE` | SBM doServiceArray validation request |
| [INBOUND] | JMS ← SBM response channel | `SBM_DO_SERVICE` (response) | SBM validation response |
| [LOG] | `/Events/OMConsumers/OMXESB/Logger` | Logger event | Request & response audit trail |

### §8.3 — Backend API Details

| System | Operation | Function ID | Schema namespace | Protocol |
|--------|-----------|-------------|-----------------|----------|
| SBM | `doServiceArray` | `100200001` | `http://services.omx.truecorp.co.th/FMServices/SBMDoserviceArrayRequest` | JMS/ESB |

| Request wrapper | Response wrapper |
|-----------------|-----------------|
| `ns1:doServiceArrayRequest / ns1:DoServiceRequest` | `ns:doServiceArrayResponse / ns:DoServiceReturn` |

### §8.4 — BE Working Memory Dependencies

| Concept path | Fields read | Fields written |
|-------------|------------|----------------|
| `OrderRequest` | OrderPriority, OMXTrackingId, OrderID, OrderType, Channel, IsOrderResubmitted, IntegrationMethod, ExtendedInfo[SBM_CHANNEL] | — |
| `ParentOU[i].Subscriber[j]` | RefId, MSISDN, SubscriberOffers.ExtendedInfo[FE_OR_CCBS] | — |
| `Activity` | Status, RequestCount, Response[].ReferenceId, Response[].CompletionStatus, PreExecCheck | Status, Response[] (appended by response handler) |

### §8.5 — ExtendedInfo Fields Required

| Key | Required? | Where used |
|-----|-----------|------------|
| `FE_OR_CCBS` | [Conditional] | XSLT: determines if ATS channel used (value = 'ATS' or 'ATS_REMOVE') |
| `SBM_CHANNEL` | [Conditional] | POU XSLT only: overrides default channel when present in `OrderData/ExtendedInfo` |

### §8.6 — Global Variable Dependencies

| Path | Used for |
|------|---------|
| `$globalVariables/OMX_OM/Services/SBM_BATCH_CHANNEL` | SBM channel when IntegrationMethod=BATCH |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit log COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit log TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit log severity level |
| `$globalVariables/OMX_OM/WritePayload` | Gates whether request payload is written to audit log |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| Parameter | POU Variant ① | COU Variant ② |
|-----------|--------------|--------------|
| `$orderRequest` | orderRequest concept | orderRequest concept |
| `$pSubRefId` / `$cSubRefId` | ParentOU subscriber RefId | ChildOU subscriber RefId |
| `$isBatch` | IntegrationMethod='BATCH' boolean | same |
| `$globalVariables` | global variables tree | same |
| `$msisdn` | sub.MSISDN (POU) | sub.MSISDN (COU) |

### §9.2 — Channel Selection Logic (POU vs COU)

| Priority | Condition | Channel used | POU? | COU? |
|----------|-----------|-------------|------|------|
| 1 | `$isBatch = 'true'` | `$globalVariables/OMX_OM/Services/SBM_BATCH_CHANNEL` | Yes | Yes |
| 2 | `FE_OR_CCBS = 'ATS'` or `'ATS_REMOVE'` | `'ATS'` (static) | Yes | Yes |
| 3 | `exists(ExtendedInfo[Name='SBM_CHANNEL']/Value)` | `ExtendedInfo[SBM_CHANNEL]/Value` | Yes | **No** |
| 4 (default) | Otherwise | `$orderRequest/OrderData/Channel` | Yes | Yes |

> **Warning:** The SBM_CHANNEL override (priority 3) is only implemented in the **POU XSLT variant**. COU subscribers always fall through to `OrderData/Channel` when not BATCH and not ATS.

### §9.3 — Complete Generated XML Example

```xml
<!-- POU subscriber — non-batch, non-ATS, SBM_CHANNEL override applied -->
<event>
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-2024-001-TRK</JMSCorrelationID>
  <OrderID>ORD-20240813-001</OrderID>
  <RefID>SUB-001</RefID>
  <OrderType>POSTPAID_REMOVE_OFFER_SUB</OrderType>
  <payload>
    <ns1:doServiceArrayRequest>
      <ns1:DoServiceRequest>
        <ns:channel>SBM-OVERRIDE-CHANNEL</ns:channel>
        <ns:function_id>100200001</ns:function_id>
        <ns:parameters>
          <ns:item><ns:key>omx</ns:key><ns:value>omx</ns:value></ns:item>
        </ns:parameters>
        <ns:service_no>0812345678</ns:service_no>
      </ns1:DoServiceRequest>
    </ns1:doServiceArrayRequest>
  </payload>
</event>
```

### §9.4 — POU XSLT Variant ① Full Source

```xml
<xsl:stylesheet
  xmlns:ns1="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceArrayRequest"
  xmlns:ns="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceRequest"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  version="1.0">
  <xsl:param name="orderRequest"/>   <!-- bound from: orderRequest concept -->
  <xsl:param name="pSubRefId"/>      <!-- bound from: ParentOU subscriber RefId -->
  <xsl:param name="isBatch"/>        <!-- bound from: isBatch boolean -->
  <xsl:param name="globalVariables"/>
  <xsl:param name="msisdn"/>         <!-- bound from: sub.MSISDN -->
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
      <RefID><xsl:value-of select="$pSubRefId"/></RefID>
      <xsl:if test="$orderRequest/OrderData/OrderType">
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      </xsl:if>
      <payload><ns1:doServiceArrayRequest><ns1:DoServiceRequest>
        <!-- Channel selection: 3-way priority (BATCH → ATS → SBM_CHANNEL → default) -->
        <xsl:choose>
          <xsl:when test="$isBatch='true'">
            <ns:channel><xsl:value-of select="$globalVariables/OMX_OM/Services/SBM_BATCH_CHANNEL"/></ns:channel>
          </xsl:when>
          <xsl:otherwise>
            <xsl:choose>
              <xsl:when test="SubscriberOffers/ExtendedInfo[Name='FE_OR_CCBS']/Value='ATS'
                              or .../Value='ATS_REMOVE'">
                <ns:channel>ATS</ns:channel>
              </xsl:when>
              <xsl:when test="exists($orderRequest/OrderData/ExtendedInfo[Name='SBM_CHANNEL']/Value)">
                <ns:channel><xsl:value-of select="$orderRequest/OrderData/ExtendedInfo[Name='SBM_CHANNEL']/Value"/></ns:channel>
              </xsl:when>
              <xsl:otherwise>
                <ns:channel><xsl:value-of select="$orderRequest/OrderData/Channel"/></ns:channel>
              </xsl:otherwise>
            </xsl:choose>
          </xsl:otherwise>
        </xsl:choose>
        <ns:function_id>100200001</ns:function_id>
        <ns:parameters><ns:item>
          <ns:key>omx</ns:key><ns:value>omx</ns:value>
        </ns:item></ns:parameters>
        <ns:service_no><xsl:value-of select="$msisdn"/></ns:service_no>
      </ns1:DoServiceRequest></ns1:doServiceArrayRequest></payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

### §9.5 — COU XSLT Variant ② — Diff from Variant ①

| Element | POU Variant ① | COU Variant ② |
|---------|--------------|--------------|
| RefId parameter | `$pSubRefId` | `$cSubRefId` |
| ATS condition XPath | `.../ParentOU/Subscriber/SubscriberOffers/...` | `.../ParentOU/ChildOU/Subscriber/SubscriberOffers/...` |
| SBM_CHANNEL override branch | Present (3rd priority) | **Absent** — falls through to default |
| Channel fallback | `$orderRequest/OrderData/Channel` | `$orderRequest/OrderData/Channel` (same) |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

POU Variant ① — COU differences annotated. `[Always]` = unconditional. `[Conditional: <test>]` = xsl:if/when. `[POU-only]` = absent in COU XSLT.

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                   [Conditional: $orderRequest/OrderPriority]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId         [Conditional: $orderRequest/OrderData/OMXTrackingId]
    ├── OrderID              ← $orderRequest/OrderData/OrderID               [Conditional: $orderRequest/OrderData/OrderID]
    ├── RefID                ← $pSubRefId (COU: $cSubRefId)                  [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType             [Conditional: $orderRequest/OrderData/OrderType]
    └── payload
        └── ns1:doServiceArrayRequest
            └── ns1:DoServiceRequest
                ├── ns:channel   ← via xsl:choose                            [Always — one of 4 branches]
                │   ├── ①  $globalVariables/OMX_OM/Services/SBM_BATCH_CHANNEL   [if $isBatch='true']
                │   ├── ②  'ATS' (static)                                        [if FE_OR_CCBS='ATS' or 'ATS_REMOVE']
                │   ├── ③  $orderRequest/OrderData/ExtendedInfo[SBM_CHANNEL]     [if exists — POU only]
                │   └── ④  $orderRequest/OrderData/Channel                        [otherwise]
                ├── ns:function_id  ← "100200001" (static)                   [Always]
                ├── ns:parameters
                │   └── ns:item
                │       ├── ns:key   ← "omx" (static)                        [Always]
                │       └── ns:value ← "omx" (static)                        [Always]
                └── ns:service_no   ← $msisdn                                [Always]
```

---

## §11 — Audit Logging

| Phase | PROCESS_ID | AUDIT_TRACE | Payload gated? |
|-------|-----------|-------------|----------------|
| Request sent (per subscriber) | `concat($pid, "_REQ")` | `Request Sent for SBM_VALIDATE` | Yes — `WritePayload="true"` |
| Response received | `concat($pid, "_RES")` | `Response received for SBM_VALIDATE` | Yes — `WritePayload="true"` |

Both request and response audit logs are always sent — no `AllowWriteLog` gate on this FM.

**Common fields:** `ESBUUID` = OMXTrackingId, `COMPONENT_NAME` = OMX_CEP, `TARGET_SYSTEM` = OMX_FM, `LOG_LEVEL` = INFO, `AUDIT_TS` = current dateTime (`yyyy-MM-dd HH:mm:ss.SSS`).

---

## §12 — Activity Status Management

| Transition | Status code | Status text | Condition |
|-----------|------------|-------------|-----------|
| Request dispatched | `"1"` | PROCESSING | `!isSkipped` — at least one subscriber request sent |
| All skipped | `"4"` | SKIPPED | `isSkipped == true` — no eligible subscribers |
| Fan-in complete | Set by IntraActivitySequencing | COMPLETE (`"2"`) | All requests responded |

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

The entire `then` block is wrapped in a single try/catch. Any exception is forwarded to `HandleActivityException`, which marks the activity as failed and propagates the error through the order process.

---

## §14 — Helper Functions Reference

| Function | Validity | Purpose |
|---------|---------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | ACTION | Clears queued events from a previous (failed) attempt |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | ACTION | Registers the request event with the sequencer |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | ACTION | Fires the first queued request |
| `IntraActivitySequencing.ActionResponseEvent(activity)` | ACTION | Fan-in completion check; returns true when all complete |
| `GetXMLForSubscriber(orderRequest, subRefId)` | ACTION | Serialises POU subscriber data to XML for XPath gate evaluation |
| `GetXMLForSubscriberInChildOU(orderRequest, subRefId, pOuRefId)` | ACTION | Serialises COU subscriber data to XML; requires parent OU RefId |
| `SkipActivity(orderRequest, activity, "4")` | ACTION | Marks activity skipped and advances process flow |
| `GetActivityStatusString(code, flag)` | QUERY | Converts numeric status code to string |
| `SendDataToDB(orderRequest)` | ACTION | Persists current order state to database |
| `HandleActivityException(orderRequest, activity, ex, "")` | ACTION | Generic exception handler |

---

## §15 — Function Dependency Tree

```text
Request_SBM_VALIDATE (rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()   [on resubmit]
├── XPath.evalAsBoolean()                                           [isBatch check]
├── GetXMLForSubscriber()                                           [POU PreExecCheck XML]
│   └── [serialises Concepts.OrderRequest subtree to XML string]
├── GetXMLForSubscriberInChildOU()                                  [COU PreExecCheck XML]
│   └── [serialises COU subscriber subtree to XML string]
├── XPath.execute()                                                 [PreExecCheck gate]
├── Event.createEvent("xslt://SBM_DO_SERVICE")                     [XSLT payload build]
├── Event.assertEvent()                                             [assert to working memory]
├── IntraActivitySequencing.ActionRequestEvent()                    [queue for ordered dispatch]
├── Event.createEvent("xslt://Logger")                             [audit log build]
├── Event.sendEvent()                                               [audit log dispatch]
├── IntraActivitySequencing.SendFirstRequestEvent()                 [fire first request]
├── GetActivityStatusString("1", false)                             [PROCESSING]
├── SendDataToDB()                                                  [persist state]
└── SkipActivity() / HandleActivityException()                      [terminal paths]

Response_SBM_VALIDATE (rulefunction)
├── Instance.createInstance("xslt://SBM_DoServiceRes")             [concept mapping]
├── currActivity.Response[length] = activityRes                    [append to array]
├── Event.sendEvent("xslt://Logger")                               [response audit log]
└── IntraActivitySequencing.ActionResponseEvent(currActivity)      [fan-in completion]
```

---

## §16 — Concept Definitions Referenced

| Concept | Key fields |
|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | ProcessFlow, OrderData (OrderID, OMXTrackingId, Channel, IntegrationMethod, ExtendedInfo), IsOrderResubmitted, OrderPriority, OrderType |
| `Concepts.OM.ProcessConfig.Activity` | extId, ActivityID, Status, RequestCount, Response[], PreExecCheck |
| `Concepts.FM.Response.SBM_DoServiceRes` | extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, DoServiceResponse{extId, req_transaction_id, response_message, result_code, result_desc, result_namespace, transaction_id} |
| `Events.OMConsumers.OMXFM.Request.SBM_DO_SERVICE` | JMSPriority, JMSCorrelationID, OrderID, RefID, OrderType, payload (doServiceArrayRequest) |
| `Events.OMConsumers.OMXFM.Response.SBM_DO_SERVICE` | ResponseCode, ResponseMsg, CompletionStatus, RefID, payload (doServiceArrayResponse) |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | Invoke SBM `doServiceArray` with function_id `100200001` for each active subscriber |
| R2 | Support 3-priority channel selection for POU: BATCH > ATS > SBM_CHANNEL override > default |
| R3 | Support 2-priority channel selection for COU: BATCH > ATS > default (no SBM_CHANNEL) |
| R4 | Skip subscribers where a response with CompletionStatus=2 and matching RefId already exists |
| R5 | Evaluate per-subscriber PreExecCheck before sending each request |
| R6 | Purge pending queued events before re-dispatching on order resubmission |
| R7 | Use ordered dispatch via IntraActivitySequencing (not parallel fan-out) |
| R8 | Parse response: map to SBM_DoServiceRes concept including nested DoServiceResponse sub-concept |
| R9 | Log request and response audit events; payload inclusion gated on WritePayload flag |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| COU SBM_CHANNEL asymmetry — COU subscribers cannot receive channel override | [MEDIUM] | Verify whether intentional design or oversight; document in modernisation target |
| IntraActivitySequencing creates sequential bottleneck for large subscriber counts | [MEDIUM] | Evaluate parallel dispatch in target architecture |
| function_id `100200001` hardcoded in XSLT — no configuration path | [LOW] | Expose as configuration property; document as magic number |
| Parameters always `omx=omx` static — unclear purpose | [LOW] | Confirm with SBM team whether required credential or legacy artifact |
| Re-submission logic relies on CompletionStatus==2 check requiring prior response data | [MEDIUM] | Ensure response state persists across BE restart; verify DB serialisation |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author RS33-BANDIT
 */
rule Rules.OMConsumers.OMXFM.Request.Request_SBM_VALIDATE {
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
        orderCurrentActivity.ActivityID == "SBM_VALIDATE";
        orderRequest.ProcessFlow.NextActivityID == "SBM_VALIDATE";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);

        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);

            if(isActResub) {
                IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
            }

            boolean isBatch = XPath.evalAsBoolean("xpath://$orderRequest/OrderData/IntegrationMethod='BATCH'");

            int pOuLen = orderRequest.OrderData.Customer.ParentOU@length;
            boolean isSkipped = true;
            String chkXPath = nextAct.PreExecCheck;

            /* POU subscriber loop */
            for (int i = 0; i < pOuLen; i++) {
                for(int j = 0; j < pSubLen; j++) {
                    /* skip if already responded with CompletionStatus==2 */
                    for(int iResp = 0; iResp < Response@length; iResp++) {
                        if(Response[iResp].ReferenceId == pSubRefId && Response[iResp].CompletionStatus == 2)
                            reqSuccess = true;
                    }
                    if(!reqSuccess) {
                        if(chkXPath.length > 0) {
                            sXML = GetXMLForSubscriber(orderRequest, pSubRefId);
                            chkRes = XPath.execute("/(chkXPath)", sXML, "ns0=...");
                        }
                        if(chkRes == "true") {
                            /* Build POU SBM_DO_SERVICE event — see §9.4 for full XSLT */
                            Events.OMConsumers.OMXFM.Request.SBM_DO_SERVICE reqEvent =
                                Event.createEvent("xslt://{{/Events/.../SBM_DO_SERVICE}}...");
                            Event.assertEvent(reqEvent);
                            IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                            isSkipped = false;
                            /* Send request audit log */
                        }
                    }
                }

                /* COU subscriber loop */
                for (int k = 0; k < cOuLen; k++) {
                    for (int j = 0; j < cSubLen; j++) {
                        /* same skip + gate logic with GetXMLForSubscriberInChildOU */
                        /* Build COU SBM_DO_SERVICE event — see §9.5 for XSLT diff */
                    }
                }
            }

            if(!isSkipped) {
                IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
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

`Response_SBM_VALIDATE` receives a `SBM_DO_SERVICE` response event, maps it to an `SBM_DoServiceRes` concept (including a nested `DoServiceResponse` sub-concept), appends it to the activity's Response array, logs the response, and delegates fan-in completion checking to `IntraActivitySequencing.ActionResponseEvent`.

The sub-concept extId uses the pattern `"SBM:VALIDATE:" + OMXTrackingId + ":" + RefID`, making each response uniquely addressable in working memory.

### §19.2 — Scope Variables

| Variable | Type | Role |
|---------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Source of OMXTrackingId for DoServiceResponse extId |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SBM_DO_SERVICE` | Inbound SBM response with ResponseCode, CompletionStatus, RefID, payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity concept; Response array appended; passed to IntraActivitySequencing |

### §19.3 — ResponseBase Concept Construction (SBM_DoServiceRes)

```text
createObject
└── object
    ├── @extId              ← OMXUtils:generateTrackingID()                             [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode                               [Conditional: exists]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg                                [Conditional: exists]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus                           [Conditional: exists]
    ├── ReferenceId         ← $eventResponse/RefID                                      [Conditional: exists]
    └── DoServiceResponse   ← (nested concept)                                          [Conditional: exists(doServiceArrayResponse/DoServiceReturn)]
        ├── @extId          ← concat("SBM:VALIDATE:", OMXTrackingId, ":", RefID)       [Always when parent exists]
        ├── req_transaction_id  ← ns:DoServiceReturn/ns1:req_transaction_id             [Conditional]
        ├── response_message    ← ns:DoServiceReturn/ns1:response_message               [Conditional]
        ├── result_code         ← ns:DoServiceReturn/ns1:result_code                    [Conditional]
        ├── result_desc         ← ns:DoServiceReturn/ns1:result_desc                    [Conditional]
        ├── result_namespace    ← ns:DoServiceReturn/ns1:result_namespace               [Conditional]
        └── transaction_id      ← ns:DoServiceReturn/ns1:transaction_id                 [Conditional]
```

### §19.4 — Response Completion Logic (Fan-in)

**Fan-in mechanism:** Unlike FMs that use explicit ResponseCode counting, SBM_VALIDATE delegates fan-in to `IntraActivitySequencing.ActionResponseEvent(currActivity)`. This function manages sequencing state internally.

| Return value | Meaning |
|-------------|---------|
| `"true"` | All ordered requests completed — process advances to next activity |
| `"false"` | Awaiting more responses — activity stays in PROCESSING state |

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` |
| PROCESS_ID | `concat($pid, "_RES")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `"SBM_VALIDATE"` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `"Response received for SBM_VALIDATE"` |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload/ns:ServicePayload | Copy of `$eventResponse` — gated on `WritePayload="true"` |

### §19.6 — Response XSLT Source (SBM_DoServiceRes mapping)

```xml
<xsl:stylesheet
  xmlns:ns1="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceResponse"
  xmlns:ns="http://services.omx.truecorp.co.th/FMServices/SBMDoserviceArrayResponse"
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  version="1.0">
  <xsl:param name="eventResponse"/>
  <xsl:param name="orderRequest"/>
  <xsl:template match="/">
    <createObject><object extId="{OMXUtils:generateTrackingID()}">
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
      <xsl:if test="exists($eventResponse/payload/ns:doServiceArrayResponse/ns:DoServiceReturn)">
        <DoServiceResponse
          extId="{concat('SBM:VALIDATE:', $orderRequest/OrderData/OMXTrackingId, ':', $eventResponse/RefID)}">
          <!-- req_transaction_id, response_message, result_code, result_desc,
               result_namespace, transaction_id — same xsl:if pattern -->
        </DoServiceResponse>
      </xsl:if>
    </object></createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
