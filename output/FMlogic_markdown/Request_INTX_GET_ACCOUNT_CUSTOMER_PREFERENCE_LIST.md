# Request_INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST

> TIBCO BusinessEvents FM Logic — INTX Account Customer Preference List Query

**Target System:** INTX | **Fan-out Pattern:** Classic Parallel | **Author:** RNAPP-PC | **Generated:** 2026-08-04

---

## §1 — Overview & Purpose

This FM retrieves the **account customer preference list** from the INTX system for each subscriber in the order. It queries INTX to obtain the *collection indicator* (COLLECTION_IND), which indicates whether an account is flagged for debt collection, and stores the result as a `SubscriberExtendedInfo` entry on each subscriber concept.

This FM uses a **classic parallel fan-out** pattern — one JMS request event is fired per subscriber immediately via `Event.Ext.sendEventImmediate()`, incrementing `RequestCount` for each.

> **Key distinction from CCBS FMs:** This FM does NOT use IntraActivitySequencing (no `SendFirstRequestEvent`, no `ActionRequestEvent`, no `PurgePendingRequestsBeforeResubmit`). It does NOT have ALT_CES routing. Target system is INTX, not CCBS. The subscriber concept object (`$psub`/`$csub`) is passed directly as an XSLT parameter — a unique pattern not seen in CCBS FMs.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST` |
| Rule File | `OMX-OM/Rules/OMConsumers/OMXFM/Request/Request_INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST.rule` |
| Rule Type | `rule` |
| Priority | 5 |
| Forward Chain | false |
| Author | RNAPP-PC |
| Target System | INTX |
| Integration Pattern | Classic Parallel Fan-out (sendEventImmediate + RequestCount++) |
| Fan-out Scope | POU Subscribers + COU Subscribers (dual nested loop) |
| ALT_CES Support | None |
| IntraActivitySequencing | Not Used |
| CES Header | Not Present |
| Credential Gate (IsEnableUserPass) | Not Present |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Master order context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — RequestCount, Response[], status |
| `globalVariables` | `Concepts.GlobalVariables` | Endpoint URLs, component names, WritePayload flag |

---

## §4 — Rule Conditions (WHEN)

The rule fires when all three declared concepts are simultaneously present in working memory:
- `Concepts.OrderRequest.OrderRequest orderRequest`
- `Concepts.OM.ProcessConfig.Activity orderCurrentActivity` (matching extId)
- `Concepts.GlobalVariables globalVariables`

---

## §5 — Execution Flow Diagram

```
1. Initialize → obtain POU length, begin outer ParentOU loop
2. Loop POU[p] → Loop POU.Subscriber[ps]
   → pSubRefId = psub.RefId; pOuRefId = ParentOU[p].RefId
   → PreExecCheck: GetXMLForSubscriber(orderRequest, pSubRefId)
   → if empty → continue (skip)
   → Build XSLT Variant ① (POU) request event
   → Event.Ext.sendEventImmediate(reqEvent)
   → orderCurrentActivity.RequestCount++
3. Loop POU[p] → Loop COU[c] → Loop COU.Subscriber[cs]
   → cSubRefId = csub.RefId
   → PreExecCheck: GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)
   → if empty → continue (skip)
   → Build XSLT Variant ② (COU) request event
   → Event.Ext.sendEventImmediate(reqEvent)
   → orderCurrentActivity.RequestCount++
4. GetActivityStatusString("1", false) → IN_PROGRESS
5. SendDataToDB(orderRequest, orderCurrentActivity, globalVariables)
```

> **No SendFirstRequestEvent:** Unlike IntraActivitySequencing FMs, all events fire immediately via `sendEventImmediate` within the loop. No throttle, no `PurgePendingRequestsBeforeResubmit`.

---

## §6 — Rule Action (THEN)

```java
int pOuLen = orderRequest.OrderData.Customer.ParentOU@length;
for (int p = 0; p < pOuLen; p++) {

    // POU Subscriber loop
    int pSubLen = orderRequest.OrderData.Customer.ParentOU[p].Subscriber@length;
    for (int ps = 0; ps < pSubLen; ps++) {
        Concepts.OrderRequest.OrderElements.Subscriber psub =
            orderRequest.OrderData.Customer.ParentOU[p].Subscriber[ps];
        String pSubRefId = psub.RefId;
        String pOuRefId  = orderRequest.OrderData.Customer.ParentOU[p].RefId;

        String preExecXML = RuleFunctions.OMConsumers.OMXFM.GetXMLForSubscriber(
                                orderRequest, pSubRefId);
        if (String.equals(preExecXML, "")) { continue; }

        Event reqEvent = Event.createEvent(
            /* XSLT Variant ①: POU — params: $orderRequest, $pSubRefId, $globalVariables, $psub, $pid
               → emits ns12:GetAccountCustomerPreferenceListReq (see §9.8) */
        );
        Event.Ext.sendEventImmediate(reqEvent);
        orderCurrentActivity.RequestCount++;
    }

    // COU loop
    int cOuLen = orderRequest.OrderData.Customer.ParentOU[p].ChildOU@length;
    for (int c = 0; c < cOuLen; c++) {
        int cSubLen = orderRequest.OrderData.Customer.ParentOU[p].ChildOU[c].Subscriber@length;
        for (int cs = 0; cs < cSubLen; cs++) {
            Concepts.OrderRequest.OrderElements.Subscriber csub =
                orderRequest.OrderData.Customer.ParentOU[p].ChildOU[c].Subscriber[cs];
            String cSubRefId = csub.RefId;

            String preExecXML = RuleFunctions.OMConsumers.OMXFM.GetXMLForSubscriberInChildOU(
                                    orderRequest, cSubRefId, pOuRefId);
            if (String.equals(preExecXML, "")) { continue; }

            Event reqEvent = Event.createEvent(
                /* XSLT Variant ②: COU — same as ① but $cSubRefId/$csub (see §9.8) */
            );
            Event.Ext.sendEventImmediate(reqEvent);
            orderCurrentActivity.RequestCount++;
        }
    }
}

String status = RuleFunctions.OM.GetActivityStatusString("1", false);
RuleFunctions.OM.SendDataToDB(orderRequest, orderCurrentActivity, globalVariables);
```

---

## §7 — Data Extraction

No GROUP/pipe-delimited parsing. All subscriber data is read directly from the working memory concept object (`psub.RefId`, `psub.MSISDN`).

| Field | Source | Usage |
|-------|--------|-------|
| `pSubRefId` | `psub.RefId` | PreExecCheck key + XSLT param + JMSCorrelationID |
| `cSubRefId` | `csub.RefId` | PreExecCheck key + XSLT param + JMSCorrelationID |
| `pOuRefId` | `ParentOU[p].RefId` | GetXMLForSubscriberInChildOU 3rd arg |
| `psub.MSISDN` | Subscriber concept field | XSLT payload → searchInfoArray[PRIMRESOURCEVAL].value |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Invoked in POSTPAID_ADD_OFFER_SUB for any order containing POU or COU subscribers. The COLLECTION_IND result influences downstream charge logic — used to gate whether certain fees or offers apply to accounts flagged for debt collection.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Protocol | Purpose |
|-----------|---------|-------------|----------|---------|
| [OUTBOUND] | OMXFM JMS Channel | `INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST` queue | JMS/ESB | Per-subscriber preference list query |
| [LOG] | OMXESB Logger Channel | Audit log destination | JMS event | Request/response audit trail |

### §8.3 — Backend API Details

| System | Operation | Schema NS | Protocol | Correlation Pattern |
|--------|-----------|-----------|----------|---------------------|
| INTX | `getAccountCustomerPreferenceList` | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetAccountCustomerPreferenceList.xsd` (ns12) | JMS/ESB | RefID (Subscriber RefId) per-subscriber |

### §8.4 — BE Working Memory Dependencies

| Concept | Field | Direction | Purpose |
|---------|-------|-----------|---------|
| OrderRequest | `OrderData.OMXTrackingId` | READ | Payload correlatedId + audit ESBUUID |
| OrderRequest | `OrderData.OrderPriority` | READ | JMSPriority (conditional) |
| OrderRequest | `OrderData.Customer.ParentOU[].Subscriber[]` | READ | Subscriber list for fan-out |
| OrderRequest | `Subscriber.RefId` | READ | Request correlation key |
| OrderRequest | `Subscriber.MSISDN` | READ | INTX search key |
| Activity | `RequestCount` | WRITE | Incremented per sent event |
| Activity | `Response[]` | WRITE (response) | ResponseBase appended |
| Subscriber | `ExtendedInfo[]` | WRITE (response) | COLLECTION_IND appended |

### §8.5 — ExtendedInfo Fields Required

| Name | Written By | Condition |
|------|-----------|-----------|
| `COLLECTION_IND` | Response handler (per subscriber) | POU: Y if indicator=Y AND startDate present; COU: raw indicator value (or N) |

### §8.6 — Global Variable Dependencies

| Path | Usage |
|------|-------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Gates payload in audit log |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | Bound From | POU Variant | COU Variant |
|------------|-----------|------------|------------|
| `$orderRequest` | orderRequest concept | same | same |
| `$pSubRefId` / `$cSubRefId` | psub.RefId / csub.RefId | `$pSubRefId` | `$cSubRefId` |
| `$globalVariables` | globalVariables concept | same | same |
| `$psub` / `$csub` | Subscriber concept object directly | `$psub` | `$csub` |
| `$pid` | `System.nanoTime()` | same | same |

> **Unique pattern:** `$psub`/`$csub` passes the entire Subscriber concept object as an XSLT parameter, allowing `$psub/MSISDN` to be read directly inside the stylesheet.

### §9.2 — Event Container Construction

| Element | Source | Condition |
|---------|--------|-----------|
| `createEvent/event/@extId` | `OMXUtils:generateTrackingID()` | Always |

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderData/OrderPriority` | [Conditional] xsl:if on OrderPriority |
| `JMSCorrelationID` | `$pSubRefId` or `$cSubRefId` | [Conditional] |
| `OrderID` | `$orderRequest/OrderData/OrderId` | [Conditional] |
| `ESBUUID` | `$orderRequest/OrderData/OMXTrackingId` | [Conditional] |
| `PROCESS_ID` | `concat($pid, "_REQ")` | [Always] |
| `COMPONENT_NAME` | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | [Always] |
| `OPERATION_NAME` | `"INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST"` (static) | [Always] |
| `TARGET_SYSTEM` | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | [Always] |
| `LOG_LEVEL` | `$globalVariables/.../INFO` | [Always] |
| `AUDIT_TRACE` | `"Request Sent for INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST"` (fully static — no RefId) | [Always] |
| `AUDIT_TS` | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` | [Always] |

> **No CES Header / No ALT_CES:** Unlike all CCBS FMs, there is no CES endpoint header. INTX routing is fixed.

### §9.4 — Payload Root Element

| Root Element | NS Prefix | Namespace URI |
|-------------|-----------|---------------|
| `ns12:GetAccountCustomerPreferenceListReq` | `ns12` | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetAccountCustomerPreferenceList.xsd` |

### §9.5 — Conditional Fields

| Field | Condition | Source |
|-------|-----------|--------|
| `ns12:correlatedId` | `$orderRequest/OrderData/OMXTrackingId` present | `$orderRequest/OrderData/OMXTrackingId` |
| `ns12:searchInfoArray[1]/ns12:value` | `$psub/MSISDN` or `$csub/MSISDN` present | Subscriber MSISDN |

### §9.6 — Core Payload Structure

| Element | Value | Condition |
|---------|-------|-----------|
| `ns12:GetAccountCustomerPreferenceListReq` | Root | Always |
| `ns12:getAccountCustomerPreferenceList` | Operation wrapper | Always |
| `ns12:correlatedId` | OMXTrackingId | Conditional |
| `ns12:pageNumber` | `"1"` (hardcoded static) | Always |
| `ns12:searchList` | Container | Always |
| `ns12:searchInfoArray[1]/ns12:type` | `"PRIMRESOURCEVAL"` (static) | Always |
| `ns12:searchInfoArray[1]/ns12:value` | `$psub/MSISDN` or `$csub/MSISDN` | Conditional |
| `ns12:searchInfoArray[2]/ns12:type` | `"BUSINESSLINE"` (static) | Always |
| `ns12:searchInfoArray[2]/ns12:value` | `"MOBILE"` (static) | Always |
| `ns12:searchInfoArray[3]/ns12:type` | `"SUBSTATUS"` (static) | Always |
| `ns12:searchInfoArray[3]/ns12:value` | `"ACTIVEORSUSPEND"` (static) | Always |

### §9.7 — Complete Generated XML Example

```xml
<ns12:GetAccountCustomerPreferenceListReq
  xmlns:ns12="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetAccountCustomerPreferenceList.xsd">
  <ns12:getAccountCustomerPreferenceList>
    <ns12:correlatedId>OMX-2025-12345-ABCDEF</ns12:correlatedId>  <!-- conditional -->
    <ns12:pageNumber>1</ns12:pageNumber>                           <!-- always static -->
    <ns12:searchList>
      <ns12:searchInfoArray>
        <ns12:type>PRIMRESOURCEVAL</ns12:type>
        <ns12:value>0812345678</ns12:value>                        <!-- MSISDN, conditional -->
      </ns12:searchInfoArray>
      <ns12:searchInfoArray>
        <ns12:type>BUSINESSLINE</ns12:type>
        <ns12:value>MOBILE</ns12:value>
      </ns12:searchInfoArray>
      <ns12:searchInfoArray>
        <ns12:type>SUBSTATUS</ns12:type>
        <ns12:value>ACTIVEORSUSPEND</ns12:value>
      </ns12:searchInfoArray>
    </ns12:searchList>
  </ns12:getAccountCustomerPreferenceList>
</ns12:GetAccountCustomerPreferenceListReq>
```

### §9.8 — XSLT Stylesheet Source

**Variant ① — POU Subscriber** (`$psub`, `$pSubRefId`):

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns12="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/INTX/GetAccountCustomerPreferenceList.xsd"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
  version="1.0"
  exclude-result-prefixes="OMXUtils xsl xsd tib">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>      <!-- full OrderRequest concept -->
  <xsl:param name="pSubRefId"/>         <!-- psub.RefId string -->
  <xsl:param name="globalVariables"/>
  <xsl:param name="psub"/>              <!-- Subscriber concept object (unique pattern) -->
  <xsl:param name="pid"/>               <!-- System.nanoTime() -->
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <xsl:if test="$orderRequest/OrderData/OrderPriority">
          <JMSPriority><xsl:value-of select="$orderRequest/OrderData/OrderPriority"/></JMSPriority>
        </xsl:if>
        <xsl:if test="$pSubRefId">
          <JMSCorrelationID><xsl:value-of select="$pSubRefId"/></JMSCorrelationID>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OrderId">
          <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderId"/></OrderID>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
          <ESBUUID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></ESBUUID>
        </xsl:if>
        <PROCESS_ID><xsl:value-of select="concat($pid,'_REQ')"/></PROCESS_ID>
        <COMPONENT_NAME><xsl:value-of select="$globalVariables/OMX_COMMON/Component_Name/OMX_CEP"/></COMPONENT_NAME>
        <OPERATION_NAME>INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST</OPERATION_NAME>
        <TARGET_SYSTEM><xsl:value-of select="$globalVariables/OMX_COMMON/Component_Name/OMX_FM"/></TARGET_SYSTEM>
        <LOG_LEVEL><xsl:value-of select="$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO"/></LOG_LEVEL>
        <AUDIT_TRACE>Request Sent for INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST</AUDIT_TRACE>
        <AUDIT_TS><xsl:value-of select="tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())"/></AUDIT_TS>
        <xsl:if test="$globalVariables/OMX_OM/WritePayload='true'">
          <payload>
            <ns12:GetAccountCustomerPreferenceListReq>
              <ns12:getAccountCustomerPreferenceList>
                <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
                  <ns12:correlatedId><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></ns12:correlatedId>
                </xsl:if>
                <ns12:pageNumber>1</ns12:pageNumber>
                <ns12:searchList>
                  <ns12:searchInfoArray>
                    <ns12:type>PRIMRESOURCEVAL</ns12:type>
                    <xsl:if test="$psub/MSISDN">
                      <ns12:value><xsl:value-of select="$psub/MSISDN"/></ns12:value>
                    </xsl:if>
                  </ns12:searchInfoArray>
                  <ns12:searchInfoArray>
                    <ns12:type>BUSINESSLINE</ns12:type>
                    <ns12:value>MOBILE</ns12:value>
                  </ns12:searchInfoArray>
                  <ns12:searchInfoArray>
                    <ns12:type>SUBSTATUS</ns12:type>
                    <ns12:value>ACTIVEORSUSPEND</ns12:value>
                  </ns12:searchInfoArray>
                </ns12:searchList>
              </ns12:getAccountCustomerPreferenceList>
            </ns12:GetAccountCustomerPreferenceListReq>
          </payload>
        </xsl:if>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**Variant ② — COU Subscriber**: Identical structure; replace `$pSubRefId` → `$cSubRefId` and `$psub` → `$csub` throughout. No other differences.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event  extId ← OMXUtils:generateTrackingID()  [Always]
    ├── JMSPriority        ← $orderRequest/OrderData/OrderPriority      [Conditional: OrderPriority present]
    ├── JMSCorrelationID   ← $pSubRefId / $cSubRefId                   [Conditional]
    ├── OrderID            ← $orderRequest/OrderData/OrderId            [Conditional]
    ├── ESBUUID            ← $orderRequest/OrderData/OMXTrackingId      [Conditional]
    ├── PROCESS_ID         ← concat($pid, "_REQ")                       [Always]
    ├── COMPONENT_NAME     ← $globalVariables/OMX_COMMON/Component_Name/OMX_CEP  [Always]
    ├── OPERATION_NAME     ← "INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST"  [Always — static literal]
    ├── TARGET_SYSTEM      ← $globalVariables/OMX_COMMON/Component_Name/OMX_FM  [Always]
    ├── LOG_LEVEL          ← $globalVariables/.../MSG_LOG_LEVEL/INFO    [Always]
    ├── AUDIT_TRACE        ← "Request Sent for INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST"  [Always — fully static, no RefId]
    ├── AUDIT_TS           ← tib:format-dateTime(...)                   [Always]
    └── payload                                                          [Conditional: WritePayload="true"]
        └── ns12:GetAccountCustomerPreferenceListReq
            └── ns12:getAccountCustomerPreferenceList
                ├── ns12:correlatedId  ← $orderRequest/OrderData/OMXTrackingId   [Conditional]
                ├── ns12:pageNumber    ← "1"                                      [Always — static]
                └── ns12:searchList
                    ├── ns12:searchInfoArray [1 — PRIMRESOURCEVAL]
                    │   ├── ns12:type   ← "PRIMRESOURCEVAL"                       [Always — static]
                    │   └── ns12:value  ← $psub/MSISDN or $csub/MSISDN           [Conditional]
                    ├── ns12:searchInfoArray [2 — BUSINESSLINE]
                    │   ├── ns12:type   ← "BUSINESSLINE"                          [Always — static]
                    │   └── ns12:value  ← "MOBILE"                                [Always — static]
                    └── ns12:searchInfoArray [3 — SUBSTATUS]
                        ├── ns12:type   ← "SUBSTATUS"                             [Always — static]
                        └── ns12:value  ← "ACTIVEORSUSPEND"                       [Always — static]
```

**Legend:** `←` XPath/dynamic source | static literals in quotes | `[Conditional: ...]` = xsl:if condition | `[Always]` = unconditional output

---

## §11 — Audit Logging

| Field | Request Value | Response Value |
|-------|--------------|----------------|
| `AUDIT_TRACE` | `"Request Sent for INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST"` (fully static) | `"Response received for INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST"` (fully static) |
| `OPERATION_NAME` | `"INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST"` | `"INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST"` |
| `PROCESS_ID` | `concat($pid, "_REQ")` | `concat($pid, "_RES")` |
| `ESBUUID` | OMXTrackingId (conditional) | OMXTrackingId (conditional) |
| `payload` | Gated by `WritePayload="true"` | Gated by `WritePayload="true"` |

> **Note:** AUDIT_TRACE contains NO RefId — it is a fully static string. Per-subscriber correlation from logs alone is not possible without additional context.

---

## §12 — Activity Status Management

| Call | Status Code | Meaning | Timing |
|------|------------|---------|--------|
| `GetActivityStatusString("1", false)` | 1 = IN_PROGRESS | Activity executing — events sent | After all fan-out loops |

If RequestCount remains 0 (all subscribers skipped by PreExecCheck), fan-in (`0 == 0`) returns "true" immediately.

---

## §13 — Exception / Error Handling

Exception handling follows the standard OMXFM pattern via the response rulefunction's fan-in check. If a response arrives with ResponseCode not ending in "000", the fan-in condition is not satisfied. No explicit `try/catch` or `HandleActivityException` calls in the request rule.

---

## §14 — Helper Functions Reference

| Function | Signature | Purpose |
|----------|----------|---------|
| `GetXMLForSubscriber` | `String(OrderRequest, pSubRefId)` | Serialized subscriber XML for PreExecCheck (POU) |
| `GetXMLForSubscriberInChildOU` | `String(OrderRequest, cSubRefId, pOuRefId)` | Serialized subscriber XML for PreExecCheck (COU, includes parent OU ref) |
| `GetActivityStatusString` | `String(String, Boolean)` | Returns status string |
| `SendDataToDB` | `void(OrderRequest, Activity, GlobalVariables)` | Persists activity state to DB |

---

## §15 — Function Dependency Tree

```text
Request_INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST.rule
├── RuleFunctions.OMConsumers.OMXFM.GetXMLForSubscriber(orderRequest, pSubRefId)
│   └── [serializes subscriber concept to XML for PreExecCheck gate]
├── RuleFunctions.OMConsumers.OMXFM.GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)
│   └── [serializes COU subscriber with parentOU ref for PreExecCheck gate]
├── Event.Ext.sendEventImmediate(reqEvent)
│   └── [fires JMS to INTX destination immediately — classic fan-out]
├── RuleFunctions.OM.GetActivityStatusString("1", false)
│   └── [returns IN_PROGRESS status]
└── RuleFunctions.OM.SendDataToDB(orderRequest, orderCurrentActivity, globalVariables)
    └── [persists activity state to OM database]
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Fields Used |
|---------|----------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.OMXTrackingId, OrderData.OrderPriority, OrderData.Customer.ParentOU[].Subscriber[], ChildOU[].Subscriber[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, ExtendedInfo[] (WRITE: COLLECTION_IND) |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` | Name="COLLECTION_IND", Value (Y/N or raw) |
| `Concepts.OM.ProcessConfig.Activity` | RequestCount (WRITE), Response[] (WRITE by response) |
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |
| `Concepts.GlobalVariables` | OMX_COMMON paths, WritePayload, Component_Name |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Query INTX `getAccountCustomerPreferenceList` once per subscriber with MSISDN as search key |
| R2 | Always send `pageNumber=1`, `BUSINESSLINE=MOBILE`, `SUBSTATUS=ACTIVEORSUSPEND` as static parameters |
| R3 | Store POU COLLECTION_IND as binary Y/N (Y only if `collectionIndicator="Y"` AND `startDate` present) |
| R4 | Store COU COLLECTION_IND as raw collectionIndicator value (not binary — raw pass-through; N if absent) |
| R5 | Fan-in: complete only when all RequestCount responses have 000-suffix ResponseCode |
| R6 | Skip subscriber if PreExecCheck returns empty string |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| POU vs COU collection indicator logic divergence — POU binary Y/N, COU raw value | [HIGH] | Document and test both paths; ensure downstream consumers handle both forms |
| Static AUDIT_TRACE — no RefId, making per-subscriber log correlation impossible | [MEDIUM] | Include subscriber RefId in each audit log entry in modernized system |
| Classic fan-out with no throttle — all subscribers fire simultaneously | [MEDIUM] | Implement rate limiting or batching; consider async queue patterns |
| Subscriber object passed as XSLT param — tightly couples BE concept to XSLT | [LOW] | Extract to explicit field parameters in target platform |
| No CES/ALT_CES — fixed endpoint | [LOW] | Modern API gateway provides routing flexibility |

---

## §18 — Full Source Code

```java
/**
 * Request_INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST
 * Author: RNAPP-PC
 * Pattern: Classic parallel fan-out (sendEventImmediate + RequestCount++)
 * Target: INTX
 */
rule Rules.OMConsumers.OMXFM.Request.Request_INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST {
    attribute {
        priority = 5;
        forwardChain = false;
    }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
        Concepts.GlobalVariables globalVariables;
    }
    when {
        /* standard working memory match */
    }
    then {
        int pOuLen = orderRequest.OrderData.Customer.ParentOU@length;
        for (int p = 0; p < pOuLen; p++) {

            int pSubLen = orderRequest.OrderData.Customer.ParentOU[p].Subscriber@length;
            for (int ps = 0; ps < pSubLen; ps++) {
                Concepts.OrderRequest.OrderElements.Subscriber psub =
                    orderRequest.OrderData.Customer.ParentOU[p].Subscriber[ps];
                String pSubRefId = psub.RefId;
                String pOuRefId  = orderRequest.OrderData.Customer.ParentOU[p].RefId;

                String preExecXML = RuleFunctions.OMConsumers.OMXFM.GetXMLForSubscriber(
                                        orderRequest, pSubRefId);
                if (String.equals(preExecXML, "")) { continue; }

                Event reqEvent = Event.createEvent(
                    /* XSLT Variant ①: POU
                       params: $orderRequest, $pSubRefId, $globalVariables, $psub, $pid
                       → emits ns12:GetAccountCustomerPreferenceListReq (see §9.8)
                       Fields: correlatedId(cond), pageNumber=1(static),
                               searchList[PRIMRESOURCEVAL=$psub/MSISDN(cond), BUSINESSLINE=MOBILE, SUBSTATUS=ACTIVEORSUSPEND] */
                );
                Event.Ext.sendEventImmediate(reqEvent);
                orderCurrentActivity.RequestCount++;
            }

            int cOuLen = orderRequest.OrderData.Customer.ParentOU[p].ChildOU@length;
            for (int c = 0; c < cOuLen; c++) {
                int cSubLen = orderRequest.OrderData.Customer.ParentOU[p].ChildOU[c].Subscriber@length;
                for (int cs = 0; cs < cSubLen; cs++) {
                    Concepts.OrderRequest.OrderElements.Subscriber csub =
                        orderRequest.OrderData.Customer.ParentOU[p].ChildOU[c].Subscriber[cs];
                    String cSubRefId = csub.RefId;

                    String preExecXML = RuleFunctions.OMConsumers.OMXFM.GetXMLForSubscriberInChildOU(
                                            orderRequest, cSubRefId, pOuRefId);
                    if (String.equals(preExecXML, "")) { continue; }

                    Event reqEvent = Event.createEvent(
                        /* XSLT Variant ②: COU — same as ① but $cSubRefId/$csub (see §9.8) */
                    );
                    Event.Ext.sendEventImmediate(reqEvent);
                    orderCurrentActivity.RequestCount++;
                }
            }
        }

        String status = RuleFunctions.OM.GetActivityStatusString("1", false);
        RuleFunctions.OM.SendDataToDB(orderRequest, orderCurrentActivity, globalVariables);
    }
}
```

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST` handles each individual subscriber response from INTX. It: (1) builds a `ResponseBase` concept appended to the activity response array; (2) locates the matching subscriber by RefId across POU and COU arrays; (3) creates a `SubscriberExtendedInfo` with `Name="COLLECTION_IND"` and computed value appended to the subscriber's ExtendedInfo; (4) fires an audit log event; (5) evaluates fan-in completion.

> **Critical:** POU and COU collection indicator logic differ — POU applies a strict business rule (Y only if indicator=Y AND startDate present); COU does a raw pass-through. This asymmetry must be preserved exactly in any migration.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Master order — subscriber arrays to search + write ExtendedInfo |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST` | Inbound response from INTX |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] written; RequestCount read for fan-in |

### §19.3 — ResponseBase Concept Construction

```text
createObject
└── object  extId ← OMXUtils:generateTrackingID()  [Always]
    ├── ResponseCode       ← $eventResponse/ResponseCode       [Conditional]
    ├── ResponseMessage    ← $eventResponse/ResponseMsg        [Conditional]
    ├── CompletionStatus   ← $eventResponse/CompletionStatus   [Conditional]
    └── ReferenceId        ← $eventResponse/RefID              [Conditional]
```

Appended to `currActivity.Response[currActivity.Response@length]`.

### §19.3b — SubscriberExtendedInfo COLLECTION_IND Logic

**POU Variant — Binary Y/N:**
```text
if (collectionIndicator = "Y" AND string-length(startDate) > 0):
    Value = "Y"
else:
    Value = "N"
```

Source path: `$eventResponse/payload/ns:GetAccountCustomerPreferenceListRes/ns:getAccountCustomerPreferenceListResponse/ns:return/ns:accountCustomerPreferenceList/ns:accountCustomerPreferenceInfoArray[ns:system="CCBS"]/ns:account/ns:accountCollection/ns:collectionIndicator`

**COU Variant — Raw pass-through:**
```text
if (string-length(collectionIndicator) > 0):
    Value = collectionIndicator  // raw value copy
else:
    Value = "N"
```

Same XPath source. Key difference: COU copies the actual indicator value (any value INTX returns), POU enforces strict Y+startDate gate.

### §19.4 — Response Completion Logic (Fan-in)

| Component | Value |
|-----------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Return `"true"` | All sent requests have received success responses |
| Return `"false"` | Pending responses remain |

Classic fan-in matching classic fan-out. Caller blocks until all RequestCount responses arrive with "000" suffix.

### §19.5 — Response Audit Logging

```text
createEvent (Logger)
└── event
    ├── ESBUUID          ← $orderRequest/OrderData/OMXTrackingId  [Conditional]
    ├── PROCESS_ID       ← concat($pid, "_RES")                   [Always]
    ├── COMPONENT_NAME   ← $globalVariables/OMX_COMMON/Component_Name/OMX_CEP  [Always]
    ├── OPERATION_NAME   ← "INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST"  [Always — static]
    ├── TARGET_SYSTEM    ← $globalVariables/OMX_COMMON/Component_Name/OMX_FM  [Always]
    ├── LOG_LEVEL        ← $globalVariables/.../INFO               [Always]
    ├── AUDIT_TRACE      ← "Response received for INTX_GET_ACCOUNT_CUSTOMER_PREFERENCE_LIST"  [Always — static]
    ├── AUDIT_TS         ← tib:format-dateTime(...)               [Always]
    └── payload                                                    [Conditional: WritePayload="true"]
        └── ns:ServicePayload ← copy-of $eventResponse
```

### §19.6 — Response XSLT Source (ResponseBase)

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  version="1.0"
  exclude-result-prefixes="OMXUtils xsl xsd">
  <xsl:output method="xml"/>
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
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
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
