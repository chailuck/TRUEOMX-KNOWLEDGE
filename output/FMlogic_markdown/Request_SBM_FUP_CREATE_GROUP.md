# Request_SBM_FUP_CREATE_GROUP

> Creates FUP (Fair Usage Policy) groups in SBM for each OU with qualifying FE special offer indicators

**System:** SBM | **Priority:** 5 | **Author:** SathidP-PC | **function_id:** 104300001 | **Pattern:** Dual-loop POU/COU + direct send | **Fan-in:** RequestCount == successResponseCount | **Generated:** 2026-09-15

---

## §1 Overview & Purpose

This rule creates FUP (Fair Usage Policy) groups in SBM by sending `SBM_FUP_DO_SERVICE` requests with `function_id=104300001` for each ParentOU and ChildOU that passes the PreExecCheck. Before sending, it scans the OU's Agreement.Offers to find eligible FUP offers — those with a non-empty `SPECIAL_OFFER_INDICATOR` ExtendedInfo value, `FE_OR_CCBS="FE"`, and whose indicator value matches any entry in the global `FUPCreateGroupOfferInd` list. Matching OfferNames are concatenated into a comma-separated `fupElement` string passed to SBM.

Unlike CCBS FMs, this rule uses **direct send** (`Event.Ext.sendEventImmediate`) with manual `RequestCount++` rather than the IntraActivitySequencing pattern. There is no CompletionStatus==2 skip check. If no eligible FUP offer is found, an `OMX_DATA_ERROR` exception is thrown.

| Attribute | Value |
|-----------|-------|
| Rule File | `Request_SBM_FUP_CREATE_GROUP.rule` |
| Response File | `Response_SBM_FUP_CREATE_GROUP.rulefunction` |
| Author | SathidP-PC |
| Priority | 5 |
| Target System | SBM |
| SBM function_id | 104300001 (CREATE_GROUP) |
| Event name | `SBM_FUP_DO_SERVICE` (shared with other SBM_FUP FMs) |
| Send pattern | `Event.Ext.sendEventImmediate` + manual `RequestCount++` |
| Fan-in | `count(ResponseCode suffix "000") == RequestCount` |
| No CompletionStatus skip | No per-OU CompletionStatus==2 check |

---

## §2 Rule Metadata & Attributes

| Field | Value | Notes |
|-------|-------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_SBM_FUP_CREATE_GROUP` | Full qualified name |
| priority | 5 | Standard OMXFM request priority |
| forwardChain | true | Triggers re-evaluation after assertions |
| ActivityID match | `SBM_FUP_CREATE_GROUP` | Both extId and ProcessFlow.NextActivityID |
| Status trigger | WAITING | Rule fires only when activity is in WAITING state |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order data including Agreement.Offers |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | RequestCount manually incremented, Status set |

---

## §4 Rule Conditions (WHEN)

| Condition | Purpose |
|-----------|---------|
| `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches the current activity |
| `orderCurrentActivity.ActivityID == "SBM_FUP_CREATE_GROUP"` | Specific FM match |
| `orderRequest.ProcessFlow.NextActivityID == "SBM_FUP_CREATE_GROUP"` | Process flow alignment |
| `orderCurrentActivity.Status == "WAITING"` | Prevents re-firing |

---

## §5 Execution Flow Diagram

```
1. PurgePendingRequestsBeforeResubmit → if resubmit; init function_id="104300001", isSkipped=true
2. Outer POU loop (iPOU=0..pOULen-1)
3.   POU PreExecCheck gate → GetXMLForOU → skip if gate=false
4.   Scan Agreement.Offers for eligible FUP offers:
     - SPECIAL_OFFER_INDICATOR non-empty
     - FE_OR_CCBS == "FE"
     - BRMS.AnyIn(FUPCreateGroupOfferInd, specialOfferInd)
     - Build comma-separated fupElement from OfferName
5.   If fupElement == "" → throw OMX_DATA_ERROR
6.   Build SBM_FUP_DO_SERVICE event (POU variant) → sendEventImmediate → RequestCount++ → isSkipped=false
7.   Inner COU loop (iCOU=0..cOULen-1) → same pattern with GetXMLForChildOU + COU variant
8. Post-loop: if !isSkipped → Status="1" + SendDataToDB; else SkipActivity("4")
9. catch(Exception) → HandleActivityException
```

---

## §6 Rule Action (THEN) — Step-by-step Logic

### Initialization

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
String function_id = "104300001";
int pOULen = orderRequest.OrderData.Customer.ParentOU@length;
boolean isSkipped = true;
if(isActResub)
    IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
```

### POU FUP Offer Scan

```java
String fupElement = "";
for(int iOffer=0; iOffer < offerLen; iOffer++) {
    String specialOfferInd = XPath.evalAsString("$currOffer/ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR']/Value");
    String fe_or_ccbs      = XPath.evalAsString("$currOffer/ExtendedInfo[Name='FE_OR_CCBS']/Value");
    if(String.length(specialOfferInd) > 0
       && String.equals(fe_or_ccbs, "FE")
       && BRMS.AnyIn(FUPCreateGroupOfferInd, specialOfferInd))
        fupElement = fupElement.isEmpty() ? OfferName : fupElement + "," + OfferName;
}
if(fupElement == "")
    throw Exception.newException("OMX_DATA_ERROR", "There is no FUP offer. OU: " + OUId, null);
```

### Send (POU)

```java
Events.SBM_FUP_DO_SERVICE reqEvent = Event.createEvent("xslt://..."); /* see §9.8 Variant ① */
Event.Ext.sendEventImmediate(reqEvent);
if(!isActResub) orderCurrentActivity.RequestCount++;
/* Audit via Event.sendEvent */
isSkipped = false;
```

---

## §7 FUP Offer Selection Logic

For each `Agreement.Offers` entry in the OU:

| Condition | Source |
|-----------|--------|
| SPECIAL_OFFER_INDICATOR is non-empty | `ExtendedInfo[Name="SPECIAL_OFFER_INDICATOR"]/Value` |
| FE_OR_CCBS equals "FE" | `ExtendedInfo[Name="FE_OR_CCBS"]/Value` |
| BRMS.AnyIn match | `BRMS.AnyIn($globalVariables/OMX_OM/FUP/FUPCreateGroupOfferInd, specialOfferInd)` |

> **Guard:** If no eligible FUP offer found → `throw Exception.newException("OMX_DATA_ERROR", "There is no FUP offer. OU: " + OUId, null)` — activity fails immediately.

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

Fires in CHANGE_PP flows for corporate accounts with OU hierarchies. Requires Agreement.Offers with eligible FUP special offer indicators (FE=true, SPECIAL_OFFER_INDICATOR matches global FUPCreateGroupOfferInd list).

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event | Purpose |
|-----------|-------|---------|
| [OUTBOUND] | `SBM_FUP_DO_SERVICE` | Create FUP group in SBM (function_id=104300001) |
| [INBOUND] | `SBM_FUP_DO_SERVICE` (response) | SBM doServiceResponse with result_code, transaction_id |
| [LOG] | `OMXESB Logger` | Audit trail (via `Event.sendEvent` async) |

> Note: Audit log uses `Event.sendEvent` (asynchronous), while the request uses `Event.Ext.sendEventImmediate` (synchronous).

### §8.3 Backend API Details

| System | Operation | function_id | Namespace |
|--------|-----------|-------------|-----------|
| SBM | doService (CREATE_GROUP) | 104300001 | `http://services.omx.truecorp.co.th/FMServices/SBMFUPDoserviceRequest` |

### §8.4 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `Customer.ParentOU[i].RefId` | Read | JMS RefID |
| `Customer.ParentOU[i].OUId` | Read | fupID and service_no |
| `ParentOU[i].Agreement.Offers[j].ExtendedInfo` | Read | SPECIAL_OFFER_INDICATOR, FE_OR_CCBS |
| `ParentOU[i].Agreement.Offers[j].OfferName` | Read | Appended to fupElement |
| `ParentOU[i].Agreement.RefId` | Read | Matches Account for CompanyCode |
| `Customer.Account[AgreementRefId=...].AccountManagementInfo.CompanyCode` | Read | company parameter |
| `Customer.BillCycleNo` | Read | bc parameter |
| `orderCurrentActivity.RequestCount` | Read/Write | Manually incremented |

### §8.5 ExtendedInfo Fields Required

| ExtendedInfo Name | Required/Optional | Purpose |
|------------------|-------------------|---------|
| `SPECIAL_OFFER_INDICATOR` | [Required for FUP eligibility] | Identifies FUP offer tier |
| `FE_OR_CCBS` | [Required for FUP eligibility] | Must equal "FE" to qualify |

### §8.6 Global Variable Dependencies

| Global Variable Path | Purpose |
|---------------------|---------|
| `OMX_OM/FUP/FUPCreateGroupOfferInd` | Allowlist of qualifying SPECIAL_OFFER_INDICATOR values |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit log level |
| `OMX_OM/WritePayload` | Controls payload inclusion in audit log |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Variant | XSLT Params | Notes |
|---------|-------------|-------|
| POU Variant ① | `orderRequest, currPOU, function_id, fupElement` | POU concept passed directly |
| COU Variant ② | `orderRequest, currCOU, function_id, fupElement` | COU concept passed directly |

### §9.2 Event Container Construction

No explicit extId set. Event type: `Events.OMConsumers.OMXFM.Request.SBM_FUP_DO_SERVICE` (shared event type across all SBM_FUP FMs).

### §9.3 JMS / Event Header Fields

| Header | Source | Conditional? |
|--------|--------|-------------|
| `JMSPriority` | `$orderRequest/OrderPriority` | [Conditional] |
| `JMSCorrelationID` | `$orderRequest/@extId` — **@extId attribute, NOT OMXTrackingId** | [Conditional] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Conditional] |
| `RefID` | `$currPOU/RefId` or `$currCOU/RefId` | [Conditional] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Conditional] |

> No UserName/PassWord credential-gated headers in this FM.

### §9.4 Payload Root Element

`ns:doServiceRequest/ns:req` (namespace: `http://services.omx.truecorp.co.th/FMServices/SBMFUPDoserviceRequest`)

### §9.5 Payload Parameters (ns:parameters/ns:item key-value pairs)

| Key | Value | Source |
|-----|-------|--------|
| `fupID` | OUId of current OU | `$currPOU/OUId` or `$currCOU/OUId` |
| `bc` | Bill Cycle Number | `$orderRequest/OrderData/Customer/BillCycleNo` |
| `company` | CompanyCode of matching Account | `Account[AgreementRefId=currOU/Agreement/RefId]/AccountManagementInfo/CompanyCode` |
| `fupElement` | Comma-separated eligible OfferNames | Built in pre-send scan loop |

`ns:service_no` ← OUId (same as `fupID`)
`ns:function_id` ← `"104300001"` (static)

### §9.7 Complete Generated XML Example (POU Variant)

```xml
<event>
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-EXTID-001</JMSCorrelationID>
  <OrderID>ORD-123456</OrderID>
  <RefID>POU-REF-001</RefID>
  <OrderType>CHANGE_PP</OrderType>
  <payload>
    <ns:doServiceRequest>
      <ns:req>
        <ns:function_id>104300001</ns:function_id>
        <ns:parameters>
          <ns:item><ns:key>fupID</ns:key><ns:value>OU-456789</ns:value></ns:item>
          <ns:item><ns:key>bc</ns:key><ns:value>15</ns:value></ns:item>
          <ns:item><ns:key>company</ns:key><ns:value>TDT</ns:value></ns:item>
          <ns:item><ns:key>fupElement</ns:key><ns:value>FUP_PP_500,FUP_PP_999</ns:value></ns:item>
        </ns:parameters>
        <ns:service_no>OU-456789</ns:service_no>
      </ns:req>
    </ns:doServiceRequest>
  </payload>
</event>
```

### §9.8 XSLT Stylesheet Sources

**Variant ① — POU (params: orderRequest, currPOU, function_id, fupElement)**

```xml
<xsl:stylesheet xmlns:ns="http://services.omx.truecorp.co.th/FMServices/SBMFUPDoserviceRequest" version="1.0">
  <xsl:param name="orderRequest"/>    <!-- full order XML -->
  <xsl:param name="currPOU"/>         <!-- ParentOU concept XML -->
  <xsl:param name="function_id"/>     <!-- "104300001" -->
  <xsl:param name="fupElement"/>      <!-- comma-separated eligible OfferNames -->
  <xsl:template match="/">
    <createEvent><event>
      <!-- JMS headers (all conditional) -->
      <xsl:if test="$orderRequest/OrderPriority">
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      </xsl:if>
      <xsl:if test="$orderRequest/@extId">
        <JMSCorrelationID><xsl:value-of select="$orderRequest/@extId"/></JMSCorrelationID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderID">
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      </xsl:if>
      <xsl:if test="$currPOU/RefId">
        <RefID><xsl:value-of select="$currPOU/RefId"/></RefID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderType">
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      </xsl:if>
      <payload><ns:doServiceRequest><ns:req>
        <ns:function_id><xsl:value-of select="$function_id"/></ns:function_id>
        <ns:parameters>
          <ns:item><ns:key>fupID</ns:key>
            <ns:value><xsl:value-of select="$currPOU/OUId"/></ns:value></ns:item>
          <ns:item><ns:key>bc</ns:key>
            <ns:value><xsl:value-of select="$orderRequest/OrderData/Customer/BillCycleNo"/></ns:value></ns:item>
          <ns:item><ns:key>company</ns:key>
            <ns:value><xsl:value-of select="$orderRequest/OrderData/Customer/Account[AgreementRefId=$currPOU/Agreement/RefId]/AccountManagementInfo/CompanyCode"/></ns:value></ns:item>
          <ns:item><ns:key>fupElement</ns:key>
            <ns:value><xsl:value-of select="$fupElement"/></ns:value></ns:item>
        </ns:parameters>
        <ns:service_no><xsl:value-of select="$currPOU/OUId"/></ns:service_no>
      </ns:req></ns:doServiceRequest></payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**Variant ② — COU (only differences from Variant ①):**
```xml
<xsl:param name="currCOU"/>  <!-- replaces currPOU -->
<!-- RefID: $currCOU/RefId; fupID: $currCOU/OUId; service_no: $currCOU/OUId -->
<!-- company: Account[AgreementRefId=$currCOU/Agreement/RefId]/.../CompanyCode -->
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event                                                                     [Always]
    ├── JMSPriority       ← $orderRequest/OrderPriority                       [Conditional]
    ├── JMSCorrelationID  ← $orderRequest/@extId  (attribute, NOT OMXTrackingId) [Conditional]
    ├── OrderID           ← $orderRequest/OrderData/OrderID                   [Conditional]
    ├── RefID             ← $currPOU/RefId | $currCOU/RefId                   [Conditional]
    ├── OrderType         ← $orderRequest/OrderData/OrderType                 [Conditional]
    └── payload
        └── ns:doServiceRequest
            └── ns:req
                ├── ns:function_id ← "104300001" (static)                    [Always]
                ├── ns:parameters
                │   ├── ns:item[fupID]      ← currOU/OUId                    [Always]
                │   ├── ns:item[bc]         ← Customer/BillCycleNo           [Always]
                │   ├── ns:item[company]    ← Account[AgreementRefId match]/CompanyCode [Always]
                │   └── ns:item[fupElement] ← $fupElement (pre-built)        [Always]
                └── ns:service_no ← currOU/OUId                              [Always]
```

---

## §11 Audit Logging

### Request Audit (via `Event.sendEvent` — asynchronous)

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(pid, "_REQ")` |
| OPERATION_NAME | `"SBM_FUP_CREATE_GROUP"` (static) |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `"Request Sent for SBM_FUP_CREATE_GROUP"` (static) |

### Response Audit (via `Event.Ext.sendEventImmediate`)

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(pid, "_RES")` |
| OPERATION_NAME | `"SBM_FUP_CREATE_GROUP"` (static) |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `"Response received for SBM_FUP_CREATE_GROUP"` (static) |

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one send occurred | "1" (IN_PROGRESS) | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| No eligible OUs (isSkipped=true) | SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |

> No `SendFirstRequestEvent` — this FM does not use ActionRequestEvent sequencing.

---

## §13 Exception / Error Handling

| Exception | Trigger | Handling |
|-----------|---------|---------|
| `OMX_DATA_ERROR` | No FUP offer found for qualifying OU | Thrown explicitly → caught → `HandleActivityException` |
| Any other Exception | Runtime error | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` | Clears pending requests on resubmit |
| `GetXMLForOU(orderRequest, refId)` | Serializes POU XML for PreExecCheck |
| `GetXMLForChildOU(orderRequest, refId, pouRefId)` | Serializes COU XML for PreExecCheck |
| `BRMS.AnyIn(FUPCreateGroupOfferInd, specialOfferInd)` | Checks if value matches allowlist |
| `GetActivityStatusString("1", false)` | Returns IN_PROGRESS status string |
| `SkipActivity(orderRequest, activity, "4")` | Marks activity as skipped |
| `SendDataToDB(orderRequest)` | Persists order state |
| `HandleActivityException(orderRequest, activity, ex, "")` | Central exception handler |

---

## §15 Function Dependency Tree

```text
Request_SBM_FUP_CREATE_GROUP
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── GetXMLForOU(orderRequest, pOURefId)                         [POU PreExecCheck]
├── GetXMLForChildOU(orderRequest, cOURefId, pOURefId)          [COU PreExecCheck]
├── XPath.evalAsString("...SPECIAL_OFFER_INDICATOR...")          [per-offer]
├── XPath.evalAsString("...FE_OR_CCBS...")                       [per-offer]
├── BRMS.AnyIn(FUPCreateGroupOfferInd, specialOfferInd)          [FUP eligibility]
├── Exception.newException("OMX_DATA_ERROR", ...)                [no FUP offer]
├── Event.Ext.sendEventImmediate(reqEvent)                        [direct send]
├── RequestCount++ (manual)                                       [fan-in counter]
├── Event.sendEvent(Logger)                                       [async audit]
├── GetActivityStatusString("1", false)                           [status]
├── SkipActivity(orderRequest, activity, "4")                     [skip path]
├── SendDataToDB(orderRequest)                                    [persistence]
└── HandleActivityException(...)                                  [error path]

Response_SBM_FUP_CREATE_GROUP
├── Instance.createInstance(SBM_FUP_DoServiceRes XSLT)           [response concept]
├── Event.Ext.sendEventImmediate(Logger)                          [audit]
└── XPath.evalAsInt(count Response[tib:right(tib:trim(ResponseCode),3)="000"])
    → currActivity.RequestCount == successResponseCount           [fan-in]
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields Used |
|---------|----------------|
| `Concepts.OrderRequest.OrderElements.ParentOU` | OUId, RefId, Agreement.Offers[], Agreement.RefId, ChildOU[] |
| `Concepts.OrderRequest.OrderElements.ChildOU` | OUId, RefId, Agreement.Offers[], Agreement.RefId |
| `Concepts.OrderRequest.OrderElements.AgreementOffers` | OfferName, ExtendedInfo[SPECIAL_OFFER_INDICATOR], ExtendedInfo[FE_OR_CCBS] |
| `Concepts.FM.Response.SBM_FUP_DoServiceRes` | extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, extra_xml, req_transaction_id, response_message, result_code, result_desc, result_namespace, transaction_id |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

- **R1:** Dual-loop POU/COU with PreExecCheck gate at each level
- **R2:** FUP offer eligibility: SPECIAL_OFFER_INDICATOR non-empty, FE_OR_CCBS="FE", matches FUPCreateGroupOfferInd allowlist
- **R3:** function_id=104300001 static; fupElement is comma-separated eligible OfferNames
- **R4:** JMSCorrelationID = `orderRequest/@extId` attribute (NOT OMXTrackingId)
- **R5:** Manual `RequestCount++` instead of ActionRequestEvent sequencing
- **R6:** Throw OMX_DATA_ERROR if no FUP offer found for an eligible OU

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| No CompletionStatus==2 skip — on resubmit, duplicate CREATE_GROUP calls may be sent | [HIGH] | Add CompletionStatus==2 check; or verify SBM idempotency for 104300001 |
| FUPCreateGroupOfferInd misconfigured → all OUs fail with OMX_DATA_ERROR | [MEDIUM] | Monitor for OMX_DATA_ERROR "There is no FUP offer"; validate allowlist at startup |
| Exception thrown in loop stops ALL subsequent OU processing | [MEDIUM] | Consider per-OU skip (log + continue) instead of throw |
| company lookup via Account[AgreementRefId] may return multiple accounts | [LOW] | Verify AgreementRefId uniqueness |

---

## §18 Full Source Code

```java
/**
 * @description 
 * @author SathidP-PC
 */
rule Rules.OMConsumers.OMXFM.Request.Request_SBM_FUP_CREATE_GROUP {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "SBM_FUP_CREATE_GROUP";
        orderRequest.ProcessFlow.NextActivityID == "SBM_FUP_CREATE_GROUP";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
            if(isActResub) IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

            String function_id = "104300001";
            int pOULen = orderRequest.OrderData.Customer.ParentOU@length;
            boolean isSkipped = true;

            for(int iPOU=0; iPOU < pOULen; iPOU++) {
                String pOURefId = orderRequest.OrderData.Customer.ParentOU[iPOU].RefId;
                String sXML = GetXMLForOU(orderRequest, pOURefId);
                String chkRes = (PreExecCheck.length > 0) ? XPath.execute(...) : "true";

                if(chkRes == "true") {
                    // Scan Agreement.Offers for eligible FUP offers
                    String fupElement = "";
                    for(int iOffer=0; iOffer < offerLen; iOffer++) {
                        specialOfferInd = evalAsString("ExtendedInfo[Name='SPECIAL_OFFER_INDICATOR']/Value");
                        fe_or_ccbs      = evalAsString("ExtendedInfo[Name='FE_OR_CCBS']/Value");
                        if(specialOfferInd.length > 0 && fe_or_ccbs == "FE"
                           && BRMS.AnyIn(FUPCreateGroupOfferInd, specialOfferInd))
                            fupElement = empty ? OfferName : fupElement + "," + OfferName;
                    }
                    if(fupElement == "")
                        throw Exception.newException("OMX_DATA_ERROR", ...);

                    /* Build POU event — see §9.8 Variant ①
                       Output: JMS headers + payload/ns:doServiceRequest/ns:req
                       function_id=104300001, params: fupID, bc, company, fupElement, service_no */
                    Events.SBM_FUP_DO_SERVICE reqEvent = Event.createEvent("xslt://...");
                    Event.Ext.sendEventImmediate(reqEvent);
                    if(!isActResub) orderCurrentActivity.RequestCount++;
                    /* Audit via Event.sendEvent */
                    isSkipped = false;
                }
                // COU loop — same pattern with currCOU, GetXMLForChildOU, COU variant
                for(int iCOU=0; iCOU < cOULen; iCOU++) { ... }
            }

            if(!isSkipped) {
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                SendDataToDB(orderRequest);
            } else
                SkipActivity(orderRequest, orderCurrentActivity, "4");
        }
        catch (Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
    }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

`Response_SBM_FUP_CREATE_GROUP.rulefunction` processes the SBM doService reply. Creates `SBM_FUP_DoServiceRes` with standard fields plus SBM-specific payload fields. Fan-in by comparing `RequestCount` to count of responses with ResponseCode suffix "000".

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order data |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SBM_FUP_DO_SERVICE` | Shared response event type |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object @extId ← OMXUtils:generateTrackingID()                             [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode                       [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg                        [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus                   [Conditional]
    ├── ReferenceId       ← $eventResponse/RefID                              [Conditional]
    ├── extra_xml         ← payload/.../ns:extra_xml                          [Conditional]
    ├── req_transaction_id ← payload/.../ns:req_transaction_id                [Conditional]
    ├── response_message  ← payload/.../ns:response_message                   [Conditional]
    ├── result_code       ← payload/.../ns:result_code                        [Conditional]
    ├── result_desc       ← payload/.../ns:result_desc                        [Conditional]
    ├── result_namespace  ← payload/.../ns:result_namespace                   [Conditional]
    └── transaction_id    ← payload/.../ns:transaction_id                     [Conditional]
```

### §19.4 Response Completion Logic

```java
successResponseCount = XPath.evalAsInt("count($currActivity/Response[tib:right(tib:trim(ResponseCode),3)='000'])");
if(currActivity.RequestCount == successResponseCount) return "true";
else return "false";
```

Fan-in completes when ALL SBM CREATE_GROUP calls have returned with ResponseCode suffix "000".

### §19.5 Response Audit Log

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(pid, "_RES")` |
| OPERATION_NAME | `"SBM_FUP_CREATE_GROUP"` (static) |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `"Response received for SBM_FUP_CREATE_GROUP"` (static) |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
