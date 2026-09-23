# Request_BL_LIST_UNINVOICED_CHARGES

> Per-subscriber sequential charge lookup (BL3G Amdocs Billing) — computes uninvoiced charge total; writes UNINVOICED_CHARGE to SubscriberExtendedInfo via IntraActivitySequencing

**Author:** snarayan-t430 | **forwardChain:** true | **Generated:** 2026-08-04

---

## §1 Overview & Purpose

This FM lists uninvoiced charges from the BL3G Amdocs billing system for each subscriber (POU and COU). It uses the **IntraActivitySequencing pattern**: requests are asserted to working memory and queued via `ActionRequestEvent`, then sent one-at-a-time via `SendFirstRequestEvent`. Responses trigger `ActionResponseEvent` to dispatch the next. This guarantees **sequential ordering** of per-subscriber calls — unlike fan-out patterns that send in parallel.

For each subscriber, the FM computes a date window (today minus 1 month to today), filters charge items by absence of `Credit_Extracted_Ind` dynamic attribute, sums the `amount` field, and writes the total as a `SubscriberExtendedInfo` named `UNINVOICED_CHARGE`.

> **IntraActivitySequencing pattern:** Requests queued via `Event.assertEvent + ActionRequestEvent`; dispatched one-at-a-time via `SendFirstRequestEvent`. Response fan-in via `ActionResponseEvent` — NOT the standard "000" RequestCount comparison. There is no explicit `RequestCount++` in this FM; sequencing is managed internally by the helper.

> **[BUG — HIGH]:** Credit_Extracted_Ind exists-check uses namespace `xsd2` (`amdocs.csm3g.datatypes.SubscriberInfo`) for the `ListUninvoicedChargesResponse` path, but the response XML uses `xsd3` (`ListUninvoicedChargesResponse.xsd`). The XPath will never match → `creditExtractInd` always returns `false` → ALL charges are summed including those with `Credit_Extracted_Ind` set, inflating the total.

> **[TYPO — LOW]:** Concept field name is `ChargeAmout` (missing 'n') in both the concept definition and the response XSLT.

> **[DEAD CODE]:** CustomerExtendedInfo block (lines 43–45 in response) is entirely commented out. Original intent was to write a `CHARGE_AMOUNT` ExtendedInfo to the Customer concept. Abandoned.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_BL_LIST_UNINVOICED_CHARGES.rule` | 121 lines |
| Response file | `Response_BL_LIST_UNINVOICED_CHARGES.rulefunction` | 59 lines |
| Author | snarayan-t430 | |
| forwardChain | true | |
| Request event | `Events.OMConsumers.OMXFM.Request.BL_LIST_UNINVOICED_CHARGES` | One per subscriber |
| Response event | `Events.OMConsumers.OMXFM.Response.BL_LIST_UNINVOICED_CHARGES` | |
| Request schema NS | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/ListUninvoicedChargesRequest.xsd` (ns3) | |
| Response schema NS | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/ListUninvoicedChargesResponse.xsd` (xsd3) | |
| Response concept | `Concepts.FM.Response.BL_ListUninvoicedChargesRes` | Standard fields + ChargeAmout (typo) |
| Correlation key (RefID) | Subscriber RefId — **always** set (not conditional) | Used for Subscriber lookup in response |
| Fan-out level | Per-subscriber — POU Subscribers + COU Subscribers | Sequential via IntraActivitySequencing |
| Send pattern | `Event.assertEvent + ActionRequestEvent → SendFirstRequestEvent` | Sequential; one at a time |
| Fan-in pattern | `IntraActivitySequencing.ActionResponseEvent` | NOT standard "000" count |
| Resubmit handler | `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` | Called early in THEN block |
| Credential gate | Yes — OrderData.User/Password → UserName/PassWord (conditional) | Same as MCS pattern |
| CES header | OrderData.CES → CES (conditional) | Extra header not in most FMs |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Source of subscriber lists; CustomerId; credentials |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Activity state; Response[] appended; sequencing managed by IntraActivitySequencing |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "BL_LIST_UNINVOICED_CHARGES"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "BL_LIST_UNINVOICED_CHARGES"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 Execution Flow Diagram

1. **Resubmit flag + purge** — `isActResub`; if true: `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit`
2. **isSkipped = true**
3. **POU Subscribers** — for each POU × each Subscriber:
   - reqSuccess check: `Response[].ReferenceId == subId AND CompletionStatus==2`
   - If !reqSuccess: evaluate PreExecCheck using `GetXMLForSubscriber(orderRequest, refId)`
   - If passes: compute fromDate/toDate; assert+queue event via `ActionRequestEvent`; isSkipped=false
4. **COU Subscribers** — for each POU × each COU × each Subscriber:
   - Same reqSuccess check and PreExecCheck evaluation
   - PreExecCheck helper: `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)`
   - If passes: compute fromDate/toDate; assert+queue event; isSkipped=false
5. **Dispatch:** if !isSkipped → `IntraActivitySequencing.SendFirstRequestEvent` → status "1" + `SendDataToDB`; else → `SkipActivity("4")`
6. **Exception:** try/catch → `HandleActivityException`

---

## §6 Rule Action (THEN) — Key Details

### §6.1 — reqSuccess Dedup Check

```java
boolean reqSuccess = false;
for(int iResp=0; iResp < orderCurrentActivity.Response@length; iResp++)
    if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, subId)
        && orderCurrentActivity.Response[iResp].CompletionStatus==2)
        reqSuccess = true;
if(!reqSuccess) { /* proceed */ }
```

> Dedup key is `subId` (SubscriberId), NOT `refId` (RefId). The `RefID` header uses `refId` for subscriber lookup, but the dedup check uses `SubscriberId`.

### §6.2 — DateTime Window Calculation

```java
String currDate = DateTime.format(DateTime.now(), "yyyy-MM-dd HH:mm:ss");
DateTime toDate = DateTime.parseString(currDate, "yyyy-MM-dd");  // today at 00:00:00
DateTime fromDate = DateTime.addMonth(toDate, -1);               // 1 month back
```

The format/parseString trick strips the time component. Computed independently per subscriber's conditional block.

### §6.3 — IntraActivitySequencing Dispatch Pattern

```java
// Queue the request (one per subscriber):
Events..BL_LIST_UNINVOICED_CHARGES reqEvent = Event.createEvent("xslt://...");
Event.assertEvent(reqEvent);                                     // assert to working memory
RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
long pid = System.nanoTime();
Event.Ext.sendEventImmediate(...audit...);

// After all subscribers queued, dispatch first:
RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
```

> The commented-out `//Event.Ext.sendEventImmediate(reqEvent);` at lines 57 and 97 shows this FM was originally written as a direct send and later converted to IntraActivitySequencing.

### §6.4 — PreExecCheck Helpers

| Subscriber Type | Helper | Parameters |
|-----------------|--------|------------|
| POU Subscriber | `GetXMLForSubscriber(orderRequest, refId)` | Subscriber RefId |
| COU Subscriber | `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` | Subscriber RefId + POU RefId |

---

## §7 Data Extraction

No pipe-delimited or GROUP-field parsing. Two subscriber identifier fields used differently:

| Field | Source | Used For |
|-------|--------|---------|
| `refId` | `Subscriber[j].RefId` | RefID JMS header (correlation); PreExecCheck XML; Subscriber BE lookup in response |
| `subId` | `Subscriber[j].SubscriberId` | reqSuccess dedup check; `ns3:EntityIdInfo/entityId` in payload |

---

## §8 System & Integration Dependencies

### §8.1 — Order Type Dependencies

No GoldenDB routing. Single backend: BL3G (Amdocs Billing). Event fires per-subscriber when PreExecCheck passes and no prior successful response found.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Purpose |
|-----------|---------|-------------|---------|
| [OUTBOUND] | FM JMS (via IntraActivitySequencing) | BL_LIST_UNINVOICED_CHARGES queue | Uninvoiced charge lookup per subscriber (sequential) |
| [INBOUND] | FM JMS | BL_LIST_UNINVOICED_CHARGES response queue | ChargeDetailsListArray per subscriber |
| [LOG] | OMXESB Logger | Audit event | Request+response audit via `sendEventImmediate` |

### §8.3 — Backend API Details

| Field | Value |
|-------|-------|
| Backend | BL3G (Amdocs Billing) |
| Operation | ListUninvoicedCharges |
| Request root | `ns3:ListUninvoicedChargesRequest` |
| Response root | `xsd3:ListUninvoicedChargesResponse` |
| Entity type code | `83` (hardcoded — BL3G entity type for subscriber) |
| billedChargesIsolated | `89` (hardcoded — BL3G charge selection flag) |
| revenueCode | `OC` (hardcoded — One-time Charges) |
| Pagination | pageSize=100, pageNumber=0, numberOfRows=100 (all hardcoded) |

### §8.4 — BE Working Memory Dependencies

| Concept | Field | Access | Notes |
|---------|-------|--------|-------|
| OrderRequest | OrderData.Customer.ParentOU[].Subscriber[].RefId/SubscriberId | READ | Per-subscriber RefId (correlation) and SubscriberId (dedup/payload) |
| OrderRequest | OrderData.Customer.CustomerId | READ | Payload CustomerIdInfo.customerNo |
| OrderRequest | OrderData.User/Password | READ | Credential gate (conditional) |
| OrderRequest | OrderData.CES | READ | CES header (conditional) |
| Activity | Response[] / Status | READ+WRITTEN | Response[] appended; Status set to "1" |
| Subscriber | ExtendedInfo[] | WRITTEN | SubscriberExtendedInfo Name="UNINVOICED_CHARGE" appended |

### §8.5 — ExtendedInfo Fields

| Type | Name | Written By | Value |
|------|------|------------|-------|
| SubscriberExtendedInfo | UNINVOICED_CHARGE | Response rulefunction | Sum of uninvoiced `amount` (Credit_Extracted_Ind filter bugged — see §1) |

### §8.6 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `OMX_OM/WritePayload` | Payload inclusion in audit |

---

## §9 Detailed Payload Build

### §9.1 — XSLT Parameters

| Parameter | Bound From | Notes |
|-----------|------------|-------|
| `$orderRequest` | orderRequest concept serialized | |
| `$refId` | `Subscriber[j].RefId` | Subscriber's RefId — used for RefID header and response lookup |
| `$subId` | `Subscriber[j].SubscriberId` | BL3G entity identifier in payload |
| `$fromDate` | `DateTime.addMonth(today, -1)` | Today minus 1 month |
| `$toDate` | `DateTime.parseString(currDate, "yyyy-MM-dd")` | Today's date at 00:00:00 |

> **Dead variable:** `$accountId` declared inside XSLT as `<xsl:variable name="accountId" select="$orderRequest/OrderData/Customer/Account[1]/AccountID"/>` but never referenced in output.

### §9.2 — POU vs COU XSLT Variants

| Aspect | POU Subscriber | COU Subscriber |
|--------|----------------|----------------|
| `exclude-result-prefixes` order | ns2 ns1 xsl ns4 ns ns3... | ns2 ns1 xsl ns ns4 ns3... (ns4 and ns swapped) |
| Payload structure | Identical | Identical |
| Parameters | Identical | Identical |

### §9.3 — JMS / Event Header Fields

| Header | Source | Condition |
|--------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | Conditional |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| OrderID | `$orderRequest/OrderData/OrderID` | Conditional |
| RefID | `$refId` (subscriber RefId) | **Always** — no xsl:if |
| UserName | `$orderRequest/OrderData/User` | Conditional (credential gate) |
| PassWord | `$orderRequest/OrderData/Password` | Conditional (credential gate) |
| OrderType | `$orderRequest/OrderData/OrderType` | Conditional |
| CES | `$orderRequest/OrderData/CES` | Conditional — extra field |

### §9.4 — Payload Fields

| XML Element | Source | Notes |
|-------------|--------|-------|
| `ns3:ListUninvoicedChargesRequest` | — root | |
| `ns3:CustomerIdInfo/customerNo` | `$orderRequest/OrderData/Customer/CustomerId` | Always |
| `ns3:EntityIdInfo/entityId` | `$subId` (SubscriberId) | Always |
| `ns3:EntityIdInfo/entityType` | `"83"` (literal) | BL3G subscriber entity type code |
| `ns3:ChargeSelectionInfo/billedChargesIsolated` | `89` (literal) | BL3G charge filter flag |
| `ns3:ChargeSelectionInfo/dateRange/fromDate` | `$fromDate` | Today minus 1 month |
| `ns3:ChargeSelectionInfo/dateRange/toDate` | `$toDate` | Today at 00:00:00 |
| `ns3:ChargeSelectionInfo/revenueCode` | `'OC'` (literal) | One-time Charges |
| `ns3:PaginationInfo/ns4:pageSize` | `100` (literal) | |
| `ns3:PaginationInfo/ns4:pageNumber` | `0` (literal) | |
| `ns3:PaginationInfo/ns4:numberOfRows` | `100` (literal) | |

### §9.5 — Generated XML Example

```xml
<event>
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-20250804-001</JMSCorrelationID>
  <OrderID>ORD-001</OrderID>
  <RefID>SUB-REF-001</RefID>  <!-- always set; subscriber RefId -->
  <UserName>apiuser</UserName>
  <PassWord>***</PassWord>
  <OrderType>3</OrderType>
  <CES>false</CES>
  <payload>
    <ns3:ListUninvoicedChargesRequest
      xmlns:ns3="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/ListUninvoicedChargesRequest.xsd"
      xmlns:ns4="www.tibco.com/plugin/java/xmlSchema/amdocs.bl3g.datatypes.PaginationInfo">
      <ns3:CustomerIdInfo>
        <customerNo>CUST-12345</customerNo>
      </ns3:CustomerIdInfo>
      <ns3:EntityIdInfo>
        <entityId>SUB-999</entityId>  <!-- SubscriberId -->
        <entityType>83</entityType>   <!-- hardcoded BL3G subscriber code -->
      </ns3:EntityIdInfo>
      <ns3:ChargeSelectionInfo>
        <billedChargesIsolated>89</billedChargesIsolated>
        <dateRange>
          <fromDate>2026-07-04</fromDate>
          <toDate>2026-08-04</toDate>
        </dateRange>
        <revenueCode>OC</revenueCode>
      </ns3:ChargeSelectionInfo>
      <ns3:PaginationInfo>
        <ns4:pageSize>100</ns4:pageSize>
        <ns4:pageNumber>0</ns4:pageNumber>
        <ns4:numberOfRows>100</ns4:numberOfRows>
      </ns3:PaginationInfo>
    </ns3:ListUninvoicedChargesRequest>
  </payload>
</event>
```

### §9.6 — XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:ns3="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/ListUninvoicedChargesRequest.xsd"
  xmlns:ns4="www.tibco.com/plugin/java/xmlSchema/amdocs.bl3g.datatypes.PaginationInfo"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="refId"/>
  <xsl:param name="subId"/>
  <xsl:param name="fromDate"/>
  <xsl:param name="toDate"/>
  <!-- $accountId declared inside template — dead variable, never used -->
  <xsl:template match="/">
    <createEvent><event>
      [headers — see §9.3]
      <payload>
        <ns3:ListUninvoicedChargesRequest>
          <ns3:CustomerIdInfo><customerNo>← CustomerId</customerNo></ns3:CustomerIdInfo>
          <ns3:EntityIdInfo>
            <entityId>← $subId</entityId>
            <entityType>"83"</entityType>
          </ns3:EntityIdInfo>
          <ns3:ChargeSelectionInfo>
            <billedChargesIsolated>89</billedChargesIsolated>
            <dateRange>
              <fromDate>← $fromDate</fromDate>
              <toDate>← $toDate</toDate>
            </dateRange>
            <revenueCode>'OC'</revenueCode>
          </ns3:ChargeSelectionInfo>
          <ns3:PaginationInfo>
            <ns4:pageSize>100</ns4:pageSize>
            <ns4:pageNumber>0</ns4:pageNumber>
            <ns4:numberOfRows>100</ns4:numberOfRows>
          </ns3:PaginationInfo>
        </ns3:ListUninvoicedChargesRequest>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority         ← $orderRequest/OrderPriority                      [Conditional]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId            [Conditional]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                  [Conditional]
    ├── RefID               ← $refId (subscriber RefId)                        [Always — no xsl:if]
    ├── UserName            ← $orderRequest/OrderData/User                     [Credential-gated]
    ├── PassWord            ← $orderRequest/OrderData/Password                 [Credential-gated]
    ├── OrderType           ← $orderRequest/OrderData/OrderType                [Conditional]
    ├── CES                 ← $orderRequest/OrderData/CES                      [Conditional — extra field]
    └── payload
        └── ns3:ListUninvoicedChargesRequest
            ├── ns3:CustomerIdInfo
            │   └── customerNo  ← $orderRequest/OrderData/Customer/CustomerId  [Always]
            ├── ns3:EntityIdInfo
            │   ├── entityId    ← $subId (SubscriberId)                        [Always]
            │   └── entityType  ← "83" (literal)                               [Always]
            ├── ns3:ChargeSelectionInfo
            │   ├── billedChargesIsolated  ← 89 (literal)
            │   ├── dateRange
            │   │   ├── fromDate  ← $fromDate (today − 1 month)
            │   │   └── toDate    ← $toDate (today 00:00:00)
            │   └── revenueCode   ← 'OC' (literal)
            └── ns3:PaginationInfo
                ├── ns4:pageSize      ← 100 (literal)
                ├── ns4:pageNumber    ← 0 (literal)
                └── ns4:numberOfRows  ← 100 (literal)
```

**Legend:** `[Always]` = no xsl:if | `[Conditional]` = inside xsl:if | `[Credential-gated]` = conditional on credential field presence

---

## §11 Audit Logging

| Direction | Field | Value |
|-----------|-------|-------|
| Request | AUDIT_TRACE | `"Request Sent for BL_LIST_UNINVOICED_CHARGES"` |
| Request | OPERATION_NAME | `"BL_LIST_UNINVOICED_CHARGES"` |
| Request | Send method | `Event.Ext.sendEventImmediate` — `[Immediate]` |
| Response | AUDIT_TRACE | `"Response received for BL_LIST_UNINVOICED_CHARGES"` |
| Response | OPERATION_NAME | `"BL_LIST_UNINVOICED_CHARGES"` |
| Response | Send method | `Event.Ext.sendEventImmediate` — `[Immediate]` |

---

## §12 Activity Status Management

| Condition | Call | Code |
|-----------|------|------|
| At least one subscriber queued and dispatched | `SendFirstRequestEvent` + `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" (RUNNING) |
| No subscribers qualify (isSkipped) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" (SKIPPED) |

---

## §13 Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Resubmit purge — clears previously queued events |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Queue a request event for sequential dispatch |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Dispatch the first queued event |
| `IntraActivitySequencing.ActionResponseEvent(activity)` | Fan-in: dispatches next queued event; returns true when all done |
| `GetXMLForSubscriber(req, refId)` | POU subscriber XML for PreExecCheck evaluation |
| `GetXMLForSubscriberInChildOU(req, refId, pouRefId)` | COU subscriber XML for PreExecCheck evaluation |
| `DateTime.format / parseString / addMonth` | Compute fromDate/toDate window |
| `Event.assertEvent(event)` | Assert event to BE working memory (required for IntraActivitySequencing) |
| `GetActivityStatusString / SendDataToDB / SkipActivity` | Activity lifecycle management |

---

## §15 Function Dependency Tree

```text
Request_BL_LIST_UNINVOICED_CHARGES (rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if isActResub]
├── [per POU × Subscriber]:
│   ├── Response[].ReferenceId == subId AND CompletionStatus==2  [reqSuccess dedup]
│   ├── GetXMLForSubscriber(orderRequest, refId)  [PreExecCheck XML]
│   ├── XPath.execute(preExecCheck, sXML, ns)
│   ├── DateTime.format / DateTime.parseString / DateTime.addMonth  [date window]
│   ├── Event.createEvent("xslt://BL_LIST_UNINVOICED_CHARGES")
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   └── Event.Ext.sendEventImmediate(auditEvent)
├── [per POU × COU × Subscriber]:
│   ├── (same as above)
│   └── GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)
├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)  [if isSkipped]
└── RuleFunctions.Helpers.HandleActivityException(...)  [catch]

Response_BL_LIST_UNINVOICED_CHARGES (rulefunction)
├── XPath.evalAsInt("count(.../xsd3:ChargeDetailsListInfo/chargeDetailsListArray)")
├── [per charge item]:
│   ├── XPath.evalAsBoolean("exists(.../xsd2:ListUninvoicedChargesResponse/...)")
│   │   └── ⚠ BUG: xsd2 NS wrong → always returns false
│   └── XPath.evalAsDouble(".../xsd3:chargeDetailsListArray[$i+1]/amount")
│       └── accumulated into chargeAmout (typo)
├── Instance.createInstance("xslt://BL_ListUninvoicedChargesRes")
│   └── OMXUtils:generateTrackingID()  [extId]
├── currActivity.Response[length] = activityRes
├── Instance.getByExtIdByUri("SUB:"+OMXTrackingId+":"+RefID)
│   └── "CSUB:..." fallback if null
├── Instance.createInstance("xslt://SubscriberExtendedInfo")
│   └── Name="UNINVOICED_CHARGE", Value=chargeAmout
├── subscriber.ExtendedInfo[length] = subExtInf
├── Event.Ext.sendEventImmediate(auditLogEvent)
└── IntraActivitySequencing.ActionResponseEvent(currActivity)  [fan-in]
    └── returns "true" when all sequential responses done
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields | Role |
|---------|-----------|------|
| `Concepts.FM.Response.BL_ListUninvoicedChargesRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, **ChargeAmout** (typo) | Response concept with aggregated charge sum |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` | Name, Value | Written with Name="UNINVOICED_CHARGE" |
| `Concepts.OrderRequest.OrderElements.Subscriber` | ExtendedInfo[] | UNINVOICED_CHARGE appended to ExtendedInfo[] |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Fire per-subscriber (POU + COU) using `SubscriberId` as payload entity key and `RefId` as correlation key (RefID header). |
| R2 | Compute date window at execution time: `fromDate` = today minus 1 month (day precision), `toDate` = today (day precision). |
| R3 | Use IntraActivitySequencing (assert + queue + send-first) for sequential, ordered execution — NOT parallel fan-out. |
| R4 | reqSuccess dedup: skip subscriber if Response[] already contains CompletionStatus==2 with matching ReferenceId (SubscriberId). |
| R5 | Credential gate: include UserName/PassWord headers when OrderData.User/Password present. |
| R6 | Include CES header from OrderData.CES (conditional). |
| R7 | Response: sum `amount` values for charge items where `Credit_Extracted_Ind` dynamic attribute is absent. |
| R7a | **[BUG]** Fix Credit_Extracted_Ind XPath: use `xsd3` (ListUninvoicedChargesResponse.xsd) namespace, not `xsd2`. Migration target must correct this. |
| R8 | Write `SubscriberExtendedInfo` with Name="UNINVOICED_CHARGE", Value=charge sum to `subscriber.ExtendedInfo[]`. |
| R9 | Fan-in via `IntraActivitySequencing.ActionResponseEvent`; complete when all sequential responses processed. |
| R10 | BL3G constants: entityType=83, billedChargesIsolated=89, revenueCode="OC", pageSize=100. Externalize to configuration in migration target. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Credit_Extracted_Ind wrong namespace** — check always returns false → credited charges included in total | [HIGH] | Fix namespace: use `xsd3` for exists-check path, not `xsd2` |
| **Sequential IntraActivitySequencing** — each subscriber waits for previous to complete; slow with many subscribers | [MEDIUM] | Consider parallel fan-out if BL3G supports concurrent calls; increase timeout budgets |
| **Pagination hardcoded to 100 rows** — silent truncation if subscriber has >100 uninvoiced charges | [MEDIUM] | Externalize pageSize; add response count check and pagination loop |
| **ChargeAmout typo** in concept field — breaks downstream code if field name is referenced | [LOW] | Rename to `ChargeAmount` in migration; update all downstream references |
| Dead variable `$accountId` in XSLT | [LOW] | Remove from migration implementation |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_BL_LIST_UNINVOICED_CHARGES {
  attribute { priority=5; forwardChain=true; }
  declare { OrderRequest orderRequest; Activity orderCurrentActivity; }
  when { /* standard 4-condition WHEN */ }
  then {
    boolean isActResub = ...;
    try {
      if(isActResub)
        IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      boolean isSkipped = true;

      /* POU Subscribers */
      for(int i ...) { for(int j ...) {
        // reqSuccess dedup: Response[].ReferenceId==subId && CompletionStatus==2
        if(!reqSuccess) {
          chkRes = PreExecCheck via GetXMLForSubscriber(orderRequest, refId);
          if(chkRes == "true") {
            toDate = today; fromDate = today - 1 month;
            // [BL_LIST_UNINVOICED_CHARGES XSLT — see §9.6]
            Event.assertEvent(reqEvent);
            IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
            // //Event.Ext.sendEventImmediate(reqEvent);  ← commented out (original code)
            Event.Ext.sendEventImmediate(auditEvent);
            isSkipped = false;
          }
        }
      }}

      /* COU Subscribers */
      for(int i ...) { for(int k ...) { for(int j ...) {
        chkRes = PreExecCheck via GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId);
        if(chkRes == "true") {
          // same assert + queue pattern
          isSkipped = false;
        }
      }}}

      if(!isSkipped) {
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        GetActivityStatusString("1"); SendDataToDB();
      } else { SkipActivity("4"); }
    } catch(Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §19 Response Message Rule

### §19.1 — Overview

Aggregates uninvoiced charge amounts from the BL3G response — skipping items where `Credit_Extracted_Ind` attribute is present (intended; bugged by wrong namespace). Writes the total as a `SubscriberExtendedInfo` named `UNINVOICED_CHARGE`. Fan-in via `IntraActivitySequencing.ActionResponseEvent` which dispatches the next queued request event.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | READ — OMXTrackingId for subscriber lookup |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.BL_LIST_UNINVOICED_CHARGES | Backend response |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Response[] appended; fan-in via ActionResponseEvent |

### §19.3 — Charge Aggregation Logic

```java
int chargeDetailsListArray = XPath.evalAsInt(
    "count($eventResponse/payload/xsd3:ListUninvoicedChargesResponse/xsd3:ChargeDetailsListInfo/chargeDetailsListArray)");
// xsd3 = ListUninvoicedChargesResponse.xsd ← CORRECT

double chargeAmout = 0;  // note: "Amout" typo
for(int i=0; i < chargeDetailsListArray; i++) {
    boolean creditExtractInd = XPath.evalAsBoolean(
        "exists($eventResponse/payload/xsd2:ListUninvoicedChargesResponse/xsd2:ChargeDetailsListInfo/...");
    // ⚠ BUG: xsd2 = amdocs.csm3g.datatypes.SubscriberInfo — WRONG namespace!
    // Should be xsd3 = ListUninvoicedChargesResponse.xsd
    // → always returns false → all charges summed (no credit filter)

    if(!creditExtractInd) {  // always true due to bug
        chargeAmout += XPath.evalAsDouble(
            "...xsd3:ChargeDetailsListInfo/chargeDetailsListArray[number($i)+1]/amount");
    }
}
```

### §19.4 — BL_ListUninvoicedChargesRes Concept Construction

```text
createObject
└── object
    ├── @extId          ← OMXUtils:generateTrackingID()    [Always]
    ├── ResponseCode    ← $eventResponse/ResponseCode      [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg       [Conditional]
    ├── CompletionStatus← $eventResponse/CompletionStatus  [Conditional]
    ├── ReferenceId     ← $eventResponse/RefID             [Conditional]
    └── ChargeAmout     ← $chargeAmout (pre-computed sum)  [Always] [Typo: Amout]
```

### §19.5 — Subscriber Lookup & ExtendedInfo Write

```java
subscriber = Instance.getByExtIdByUri("SUB:"+OMXTrackingId+":"+RefID, Subscriber);
if(subscriber == null)
    subscriber = Instance.getByExtIdByUri("CSUB:"+OMXTrackingId+":"+RefID, Subscriber);

if(subscriber != null) {
    subExtInf = Instance.createInstance("xslt://SubscriberExtendedInfo");
    // Name="UNINVOICED_CHARGE", Value=$chargeAmout
    subscriber.ExtendedInfo[length] = subExtInf;
}
// Dead code (lines 43–45): CustomerExtendedInfo block commented out
```

### §19.6 — Fan-in Completion Logic

```java
if(RuleFunctions.Helpers.IntraActivitySequencing.ActionResponseEvent(currActivity)) {
    return "true";   // all sequential requests completed
} else {
    return "false";  // more requests still queued; next dispatched internally
}
```

`ActionResponseEvent` internally dispatches the next queued request event and returns `true` only when the queue is empty and all responses received.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
