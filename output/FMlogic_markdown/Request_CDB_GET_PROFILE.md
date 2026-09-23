# Request_CDB_GET_PROFILE

> Retrieves subscriber profile from CDB (Customer Database) by MSISDN

**Author:** RS33-BANDIT | **Target:** CDB (Customer Database) | **Pattern:** Per-subscriber fan-out | **Priority:** 5

---

## §1 Overview & Purpose

This rule fires when the order orchestrator encounters an activity with `ActivityID == "CDB_GET_PROFILE"` and the activity is in `WAITING` status. For every subscriber (ParentOU and ChildOU) in the order, it constructs and sends an `ns:Request` JMS event to the CDB service.

CDB returns the subscriber's current profile: subscription status, sub-type, price plan, in-chain flag, provisioning date, and IMSI. The response is stored as a `CdbProfile` sub-concept directly on the subscriber, making the data immediately available to downstream rules.

> **Resubmit Purge:** On resubmit, this FM uniquely calls `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)` before re-sending — clearing pending responses from a previous attempt.

> **Channel in Payload:** Unlike most other FMs, the CDB request includes `<ns:OrderChannel>` from `OrderData.Channel` — the sales channel for the order.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule class | `Rules.OMConsumers.OMXFM.Request.Request_CDB_GET_PROFILE` |
| Priority | 5 |
| forwardChain | true |
| ActivityID trigger | `CDB_GET_PROFILE` |
| Author | RS33-BANDIT |
| Target system | CDB (Customer Database) |
| Event type (outbound) | `Events.OMConsumers.OMXFM.Request.CDB_GET_PROFILE` |
| Response concept | `Concepts.FM.Response.CDB_GetProfileRes` |
| Request payload schema | `http://www.tibco.com/schemas/OMX-CDB/Schemas/Schema.xsd` |
| Response payload schema | `http://www.tibco.com/schemas/OMX-CDB/Schemas/Schema.xsd2` |
| Fan-out pattern | Per-subscriber (one event per subscriber per OU level) |
| Re-submit guard | Checks `Response[RefId==refId].CompletionStatus==2` + purges pending requests |
| Fan-in condition | `currActivity.RequestCount == currActivity.Response@length` (all responses, not only successes) |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order concept |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process activity |

---

## §4 Rule Conditions (WHEN)

- **C1** `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
- **C2** `orderCurrentActivity.ActivityID == "CDB_GET_PROFILE"`
- **C3** `orderRequest.ProcessFlow.NextActivityID == "CDB_GET_PROFILE"`
- **C4** `orderCurrentActivity.Status == "WAITING"`

---

## §5 Execution Flow

1. Compute `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. **[Resubmit only]** Call `PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
3. Get `nextAct` by extId; set `isSkipped = true`
4. Iterate ParentOU[i] → Subscriber[j] loop
   - 4a. Re-submit dedup: scan Response[] for this refId with CompletionStatus==2; if found → skip
   - 4b. PreExecCheck gate: evaluate XPath; if ≠ "true" → skip
   - 4c. Build and send `CDB_GET_PROFILE` event with MSISDN + OrderChannel payload
   - 4d. AllowWriteLog gate → send audit Logger event
   - 4e. If not resubmit → `RequestCount++`; `isSkipped = false`
5. Repeat step 4 for ChildOU[c] → Subscriber[j] loops
6. If `!isSkipped` → Status="1" (IN_PROGRESS), call `SendDataToDB`
7. Else → `SkipActivity(orderRequest, orderCurrentActivity, "4")`
8. Exception catch → `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §6 Rule Action (THEN) — Step-by-Step Logic

**Resubmit purge (unique to CDB_GET_PROFILE):** `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` clears Response entries that were submitted but not yet completed, preventing stale partial results from affecting the fan-in count.

**Payload includes OrderChannel:** The CDB request sends `<ns:OrderChannel>` from `orderRequest.OrderData.Channel`. This is distinct from ASRM/INTX FMs which do not send channel information.

**Header fields are conditional:** JMSPriority, JMSCorrelationID, and OrderID are each wrapped in `xsl:if` (emitted only if present), whereas RefID is always emitted unconditionally.

**Audit trace includes RefId:** `concat("Request Sent for RefId ", $refId)` — per-subscriber traceability in the log.

---

## §7 Data Extraction

No GROUP-encoded or pipe-delimited parsing. `msisdn` is extracted directly from the subscriber loop variable. No PROJ or other parameter is read from the activity config.

Response data is extracted from the nested `ns:Profile` element:

```text
$eventResponse/payload/ns:Profile/ns:Status     → res.Status
$eventResponse/payload/ns:Profile/ns:SubType    → res.SubType
$eventResponse/payload/ns:Profile/ns:PricePlan  → res.Priceplan
$eventResponse/payload/ns:Profile/ns:InChain    → res.InChain
$eventResponse/payload/ns:Profile/ns:ProdDate   → res.ProvDate
$eventResponse/payload/ns:Profile/ns:IMSI       → res.IMSI
```

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

Used in any order type requiring current CDB profile state before provisioning decisions. In `PREPAID_CANCEL`, it retrieves the profile to validate status and sub-type prior to cancellation.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel / Destination | Protocol | Purpose |
|-----------|----------------------|----------|---------|
| [OUTBOUND JMS] | `Events.OMConsumers.OMXFM.Request.CDB_GET_PROFILE` | JMS / ESB | Send GetProfile request to CDB |
| [OUTBOUND LOG] | `Events.OMConsumers.OMXESB.Logger` | JMS | Audit trail (gated by AllowWriteLog) |
| [INBOUND JMS] | `Events.OMConsumers.OMXFM.Response.CDB_GET_PROFILE` | JMS / ESB | Async response from CDB |

### §8.3 Backend API Details

| System | Operation | Request Schema | Response Schema | Correlation |
|--------|-----------|---------------|----------------|-------------|
| CDB (Customer Database) | GetProfile | `ns:Request` (Schema.xsd) | `ns:Profile` (Schema.xsd2) | JMSCorrelationID=OMXTrackingId; RefID=subscriber RefId |

### §8.4 BE Working Memory Dependencies

| Concept Path | Access | Fields Used |
|-------------|--------|------------|
| OrderRequest | Read | OrderData.OrderID, OMXTrackingId, OrderType, OrderPriority, Channel, IsOrderResubmitted |
| ParentOU[].Subscriber[] | Read | RefId, MSISDN |
| ChildOU[].Subscriber[] | Read | RefId, MSISDN |
| ProcessConfig.Activity | Read/Write | ActivityID, Status, RequestCount, Response[], PreExecCheck |
| Subscriber (by extId lookup) | Write | CdbProfile ← new CdbProfile concept |
| Concepts.FM.Response.CDB_GetProfileRes | Write | ResponseCode, ReferenceId, Status, SubType, Priceplan, InChain, ProvDate, IMSI |

### §8.5 CdbProfile Fields Written

| CdbProfile Field | Source (CDB_GetProfileRes) | XPath in Response | Condition |
|-----------------|---------------------------|-------------------|-----------|
| Status | activityRes.Status | `ns:Profile/ns:Status` | != null |
| SubType | activityRes.SubType | `ns:Profile/ns:SubType` | != null |
| Priceplan | activityRes.Priceplan | `ns:Profile/ns:PricePlan` | != null |
| InChain | activityRes.InChain | `ns:Profile/ns:InChain` | != null |
| ProvDate | activityRes.ProvDate | `ns:Profile/ns:ProdDate` | != null |
| IMSI | activityRes.IMSI | `ns:Profile/ns:IMSI` | != null |

CdbProfile extId pattern: `CDB:{OMXTrackingId}:{RefID}`

### §8.6 Global Variable Dependencies

| Path | Used for |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Controls payload embedding in audit log |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| xsl:param | Bound From (BE) | Type |
|-----------|----------------|------|
| `orderRequest` | `orderRequest` concept | OrderRequest concept |
| `refId` | `Subscriber[j].RefId` | String |
| `msisdn` | `Subscriber[j].MSISDN` | String |

### §9.2 Event Container

Event type: `Events.OMConsumers.OMXFM.Request.CDB_GET_PROFILE`. No explicit `@extId` generated in XSLT (relies on BE default).

### §9.3 JMS / Event Header Fields

| Field | Source | Notes |
|-------|--------|-------|
| JMSPriority | `$orderRequest/OrderPriority` | [Conditional: if OrderPriority present] |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | [Conditional: if OMXTrackingId present] |
| OrderID | `$orderRequest/OrderData/OrderID` | [Conditional: if OrderID present] |
| RefID | `$refId` | [Always] |
| OrderType | `$orderRequest/OrderData/OrderType` | [Conditional: if OrderType present] |

### §9.4 Payload Root Element

Root: `<ns:Request>` where `ns` = `http://www.tibco.com/schemas/OMX-CDB/Schemas/Schema.xsd`

### §9.5 Core Payload Block

```xml
<ns:Request>
  <ns:MSISDN>{msisdn}</ns:MSISDN>
  <ns:OrderChannel>{orderRequest/OrderData/Channel}</ns:OrderChannel>
</ns:Request>
```

### §9.6 Complete Generated XML Example

```xml
<event>
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-001</JMSCorrelationID>
  <OrderID>ORD-2025-001</OrderID>
  <RefID>SUB-REF-001</RefID>
  <OrderType>PREPAID_CANCEL</OrderType>
  <payload>
    <ns:Request xmlns:ns="http://www.tibco.com/schemas/OMX-CDB/Schemas/Schema.xsd">
      <ns:MSISDN>0812345678</ns:MSISDN>
      <ns:OrderChannel>IVR</ns:OrderChannel>
    </ns:Request>
  </payload>
</event>
```

### §9.7 XSLT Stylesheet Source (Request)

Both ParentOU and ChildOU variants use an identical XSLT:

```xml
<xsl:stylesheet
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-CDB/Schemas/Schema.xsd"
  version="1.0">
  <xsl:param name="orderRequest"/>   <!-- full OrderRequest concept -->
  <xsl:param name="refId"/>          <!-- subscriber RefId -->
  <xsl:param name="msisdn"/>         <!-- subscriber MSISDN -->
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:if test="$orderRequest/OrderPriority">
          <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
          <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OrderID">
          <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        </xsl:if>
        <RefID><xsl:value-of select="$refId"/></RefID>
        <xsl:if test="$orderRequest/OrderData/OrderType">
          <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        </xsl:if>
        <payload>
          <ns:Request>
            <ns:MSISDN><xsl:value-of select="$msisdn"/></ns:MSISDN>
            <ns:OrderChannel><xsl:value-of select="$orderRequest/OrderData/Channel"/></ns:OrderChannel>
          </ns:Request>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority        ← $orderRequest/OrderPriority               [Conditional: if OrderPriority present]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId     [Conditional: if OMXTrackingId present]
    ├── OrderID            ← $orderRequest/OrderData/OrderID            [Conditional: if OrderID present]
    ├── RefID              ← $refId                                     [Always]
    ├── OrderType          ← $orderRequest/OrderData/OrderType          [Conditional: if OrderType present]
    └── payload
        └── ns:Request  [ns = .../OMX-CDB/Schemas/Schema.xsd]
            ├── ns:MSISDN        ← $msisdn                             [Always]
            └── ns:OrderChannel  ← $orderRequest/OrderData/Channel     [Always]
```

**Legend:** `[Always]` emitted unconditionally | `[Conditional: ...]` emitted under xsl:if

---

## §11 Audit Logging

| Log Field | Value |
|-----------|-------|
| ESBUUID | OMXTrackingId (conditional) |
| PROCESS_ID | `concat(pid, "_REQ")` where pid = System.nanoTime() |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | "CDB_GET_PROFILE" (static) |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `concat("Request Sent for RefId ", $refId)` — includes subscriber RefId |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload/ns:ServicePayload | Copy of reqEvent (conditional: WritePayload="true") |

---

## §12 Activity Status Management

| Condition | Status Set | Call |
|-----------|-----------|------|
| At least one event sent | "1" (IN_PROGRESS) | `GetActivityStatusString("1", false)` → `SendDataToDB` |
| No events sent (isSkipped) | "4" (SKIPPED) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception thrown | Error state | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §13 Exception / Error Handling

The entire `then` block is wrapped in `try { ... } catch (Exception ae) { ... }`. On any exception, `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` is called.

---

## §14 Helper Functions Reference

| Function | Signature | Purpose |
|----------|-----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` | (Activity) → void | Clears pending Response entries before resubmitting |
| `GetXMLForSubscriber` | (OrderRequest, String refId) → String | Builds XML for ParentOU subscriber PreExecCheck |
| `GetXMLForSubscriberInChildOU` | (OrderRequest, String refId, String parentRefId) → String | Builds XML for ChildOU subscriber PreExecCheck |
| `AllowWriteLog` | (String orderType) → boolean | Controls audit logging per order type |
| `GetActivityStatusString` | (String code, boolean isError) → String | Converts numeric code to status string |
| `SendDataToDB` | (OrderRequest) → void | Persists order state to database |
| `SkipActivity` | (OrderRequest, Activity, String code) → void | Marks activity skipped, advances flow |
| `HandleActivityException` | (OrderRequest, Activity, Exception, String) → void | Handles exceptions |

---

## §15 Function Dependency Tree

```text
Request_CDB_GET_PROFILE (rule)
├── [Resubmit only] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit
├── [ParentOU loop]
│   ├── RuleFunctions.Helpers.GetXMLForSubscriber (PreExecCheck)
│   ├── XPath.execute (PreExecCheck evaluation)
│   ├── Event.createEvent (XSLT → CDB_GET_PROFILE event)
│   ├── Event.Ext.sendEventImmediate
│   └── AllowWriteLog → Event.createEvent (Logger) → sendEventImmediate
├── [ChildOU loop]
│   └── (same; uses GetXMLForSubscriberInChildOU)
├── RuleFunctions.Helpers.GetActivityStatusString
├── RuleFunctions.Helpers.SendDataToDB
├── RuleFunctions.Helpers.SkipActivity
└── RuleFunctions.Helpers.HandleActivityException

Response_CDB_GET_PROFILE (rulefunction)
├── OMXUtils.generateTrackingID
├── Instance.createInstance (CDB_GetProfileRes XSLT)
├── Instance.getByExtIdByUri ("SUB:{trackingId}:{refId}") → subscriber lookup
├── [fallback] Instance.getByExtIdByUri ("CSUB:{trackingId}:{refId}")
├── [if subscriber found and CdbProfile null]
│   └── Instance.createInstance (CdbProfile XSLT — extId="CDB:{trackingId}:{refId}")
│       └── Field assignments: Status, SubType, Priceplan, InChain, ProvDate, IMSI
├── AllowWriteLog → Event.createEvent (Logger) → sendEventImmediate
└── Fan-in check: currActivity.RequestCount == currActivity.Response@length
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields |
|---------|-----------|
| `Concepts.FM.Response.CDB_GetProfileRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, Status, SubType, Priceplan, InChain, ProvDate, IMSI |
| `Concepts.OrderRequest.OrderElements.CdbProfile` | Status, SubType, Priceplan, InChain, ProvDate, IMSI; extId = `CDB:{OMXTrackingId}:{RefID}` |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, CdbProfile (reference to CdbProfile) |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|------------|
| R1 | Query CDB GetProfile per subscriber (fan-out) with MSISDN + OrderChannel payload |
| R2 | On resubmit, call `PurgePendingRequestsBeforeResubmit` before re-sending |
| R3 | Map response to `CdbProfile` concept (Status, SubType, Priceplan, InChain, ProvDate, IMSI) |
| R4 | Attach CdbProfile to subscriber via extId `CDB:{OMXTrackingId}:{RefID}` |
| R5 | Subscriber lookup: try `SUB:` prefix first, fallback to `CSUB:` for ChildOU subscribers |
| R6 | Fan-in: return "true" when `RequestCount == Response@length` (all responses, success or failure) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Response schema uses `Schema.xsd2` but request uses `Schema.xsd` — potential namespace confusion | [MEDIUM] | Verify schemas are intentionally distinct; document the namespace split |
| Fan-in uses `Response@length` not success-code count — failed CDB responses silently satisfy fan-in | [MEDIUM] | Consider checking ResponseCode suffix or document intentional error-tolerance |
| Double `xsl:if` wrapping: `string-length(field) > 0` contains redundant inner `xsl:if test="field"` | [LOW] | Simplify to one condition per field |
| `ns:PricePlan` maps to `Priceplan`; `ns:ProdDate` maps to `ProvDate` — renamed without comments | [LOW] | Document in data dictionary; standardise naming in migration target |
| No MSISDN blank-guard in request (unlike INTX which calls `BRMS.IsBlank`) | [LOW] | Add guard or confirm CDB handles empty MSISDN gracefully |

---

## §18 Full Source Code

```java
/**
 * @description
 * @author RS33-BANDIT
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CDB_GET_PROFILE {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "CDB_GET_PROFILE";
        orderRequest.ProcessFlow.NextActivityID == "CDB_GET_PROFILE";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
                orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");

            if(isActResub)
                RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

            boolean isSkipped = true;

            // ── ParentOU loop ──────────────────────────────────────────────
            int parentOuLen = orderRequest.OrderData.Customer.ParentOU@length;
            for (int i = 0; i < parentOuLen; i++) {
                int subscriberLen = orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length;
                for (int j = 0; j < subscriberLen; j++) {
                    String refId = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].RefId;
                    String msisdn = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].MSISDN;

                    boolean reqSuccess = false;
                    for(int iResp = 0; iResp<orderCurrentActivity.Response@length; iResp++) {
                        if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, refId) &&
                           orderCurrentActivity.Response[iResp].CompletionStatus == 2) { reqSuccess = true; }
                    }

                    if(!reqSuccess) {
                        String chkRes = "true";
                        if(String.length(nextAct.PreExecCheck) > 0) {
                            String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId);
                            chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
                        }
                        if(String.equals(chkRes,"true")) {
                            /* Build CDB_GET_PROFILE event via XSLT.
                               Payload: ns:Request with ns:MSISDN + ns:OrderChannel.
                               Full XSLT in §9.7. */
                            Events.OMConsumers.OMXFM.Request.CDB_GET_PROFILE reqEvent =
                                Event.createEvent("xslt://{{...}}");
                            Event.Ext.sendEventImmediate(reqEvent);
                            if (RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                                long pid = System.nanoTime();
                                Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{Logger}}"));
                            }
                            if(!isActResub) { orderCurrentActivity.RequestCount++; }
                            isSkipped = false;
                        }
                    }
                }

                // ── ChildOU loop ──────────────────────────────────────────────
                String parentOuRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;
                int childOuLen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU@length;
                for (int c = 0; c < childOuLen; c++) {
                    int childSubLen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU[c].Subscriber@length;
                    for (int j = 0; j < childSubLen; j++) {
                        // [same logic; uses GetXMLForSubscriberInChildOU for PreExecCheck]
                    }
                }
            }

            if(!isSkipped) {
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

## §19 Response Message Rule

### §19.1 Overview

`RuleFunctions.OrderResponse.Response_CDB_GET_PROFILE` receives the async CDB response, creates a `CDB_GetProfileRes` concept, then looks up the matching subscriber by `RefID` (trying `SUB:` then `CSUB:` prefix) and attaches a `CdbProfile` concept with the profile data. Fan-in completes when all sent requests have received any response.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order concept |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CDB_GET_PROFILE` | Inbound CDB response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity |

### §19.3 CDB_GetProfileRes Concept Construction

```text
createObject
└── object
    ├── @extId           ← OMXUtils:generateTrackingID()               [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode                  [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg                   [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus              [Conditional]
    ├── ReferenceId      ← $eventResponse/RefID                        [Conditional]
    ├── Status           ← ns:Profile/ns:Status                        [Conditional: string-length > 0]
    ├── SubType          ← ns:Profile/ns:SubType                       [Conditional: string-length > 0]
    ├── Priceplan        ← ns:Profile/ns:PricePlan                     [Conditional: string-length > 0] (note: PricePlan→Priceplan rename)
    ├── InChain          ← ns:Profile/ns:InChain                       [Conditional: string-length > 0]
    ├── ProvDate         ← ns:Profile/ns:ProdDate                      [Conditional: string-length > 0] (note: ProdDate→ProvDate rename)
    └── IMSI             ← ns:Profile/ns:IMSI                          [Conditional: string-length > 0]
```

### §19.4 Subscriber Lookup & CdbProfile Assignment

1. Look up: `Instance.getByExtIdByUri("SUB:{OMXTrackingId}:{RefID}")`
2. If null → fallback: `Instance.getByExtIdByUri("CSUB:{OMXTrackingId}:{RefID}")` (ChildOU subscriber prefix)
3. If subscriber found and `subscriber.CdbProfile == null`: create `CdbProfile` with extId `CDB:{OMXTrackingId}:{RefID}`
4. Assign fields: Status, SubType, Priceplan, InChain, ProvDate, IMSI (each guarded by `!= null`)
5. Set `subscriber.CdbProfile = profile`

### §19.5 Response Completion Logic

**Fan-in condition:** `currActivity.RequestCount == currActivity.Response@length`

> **Important:** This fan-in counts **all** responses (not only successful ones). This differs from ASRM/INTX FMs which count only responses where `ResponseCode` ends in "000". A CDB error response will satisfy the fan-in and advance the process flow. Downstream rules must check `subscriber.CdbProfile` for null to detect lookup failures.

### §19.6 Response Audit Logging

| Log Field | Value |
|-----------|-------|
| PROCESS_ID | `concat(pid, "_RES")` |
| OPERATION_NAME | "CDB_GET_PROFILE" |
| AUDIT_TRACE | "Response received for CDB_GET_PROFILE" (static — no RefId in response trace) |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload/ns:ServicePayload | Copy of $eventResponse (conditional: WritePayload="true") |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
