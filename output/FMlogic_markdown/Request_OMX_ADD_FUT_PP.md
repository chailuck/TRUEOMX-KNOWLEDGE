# Request_OMX_ADD_FUT_PP

## §1 — Overview & Purpose

This rule creates **future price plan (FUTPP)** records in OMX for all qualifying offers in a CHANGE_PP order. It iterates over four distinct node types and sends one `OMX_ADD_FUTURE` event per offer that passes PreExecCheck.

> **Four iteration variants:**
> - **① ParentOU Agreement Offers** — nodeLevel=3, nodeId=OUId, XSLT param: `pOu`
> - **② ParentOU Subscriber Offers** — nodeLevel=5, nodeId=subId, XSLT param: `subscriberPou`
> - **③ ChildOU Agreement Offers** — nodeLevel=3, nodeId=OUId, XSLT param: `cOu`
> - **④ ChildOU Subscriber Offers** — nodeLevel=5, nodeId=subId, XSLT param: `subscriberCou`

> **[NOTE]:** Audit OPERATION_NAME inconsistency: ParentOU Agreement uses `"OMX_ADD_FUTPP"`, Subscriber and ChildOU variants use `"OMX_ADD_FUT_PP"`. This should be standardised during migration.

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule path | `Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_FUT_PP` |
| Priority | 5 |
| ForwardChain | true |
| ActivityID guard | `OMX_ADD_FUT_PP` |
| Response event type | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` |
| Response concept type | `Concepts.FM.Response.OMX_AddFutureRes` |
| Payload schema | `ns3:futureOrderWithSoc` (FutureOrderWithSoc.xsd) |
| Backend | OMX internal future order store |

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Active process step |

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity-order pointer match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_ADD_FUT_PP"` | Guards to specific activity |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_ADD_FUT_PP"` | Flow pointer double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Not yet dispatched |

## §5 — Execution Flow Diagram

1. Check `isActResub`
2. Read computed globals: `customerType` (ASCII→text), `accountSubType`, `requestBy`=Channel; static: `orderType=2`, `type="80"`, `futureType="FUTPP"`
3. Outer loop: `ParentOU[iPOU]`
4. **Variant ①**: ParentOU Agreement Offers — for each offer: PreExecCheck via `GetXMLForAgreementOffer`; if passes, build and send event; audit OPERATION_NAME="OMX_ADD_FUTPP"
5. **Variant ②**: ParentOU Subscriber Offers — for each offer: PreExecCheck via `GetXMLForSubscriberOffer`; if passes, build and send event; audit OPERATION_NAME="OMX_ADD_FUT_PP"
6. Inner loop: `ChildOU[iCOU]`
7. **Variant ③**: ChildOU Agreement Offers — PreExecCheck via `GetXMLForAgreementOfferInChildOU`
8. **Variant ④**: ChildOU Subscriber Offers — PreExecCheck via `GetXMLForSubscriberOfferInChildOU`
9. Post-loop: if any sent → Status="1" + SendDataToDB; else SkipActivity("4")
10. Exception: `HandleActivityException`

## §6 — Rule Action (THEN) — Detailed Logic

### Computed Variables (once, before loops)

| Variable | Source | Notes |
|----------|--------|-------|
| `customerType` | `Customer/CustomerTypeInfo/Type` → ASCII code → `OMXUtils.asciiCodeToText()` | Converts numeric ASCII to text type |
| `accountSubType` | `Customer/Account[1]/AccountManagementInfo/AccountSubType` | XPath evalAsString |
| `requestBy` | `orderRequest.OrderData.Channel` | Direct field access |
| `orderType` | `2` (static int) | |
| `type` | `"80"` (static — price plan service type) | |
| `futureType` | `"FUTPP"` (static) | futureOrder.futureType value |

### Per-offer computed variables

| Variable | Source | Scope |
|----------|--------|-------|
| `currentPricePlan` | Offers[ServiceType='80' and FE_OR_CCBS='CCBS'][1]/OfferName | All variants |
| `inputUserText` | Agreement/AgreementActivityInfo/UserText or SubscriberActivityInfo/UserText | All variants |
| `userText` | POU/COU Agreement: `"%s;FUTPP request by %s on %s;"` / Subscriber: `"%s;request by %s on %s;"` | Formatted with Channel + dateTimeNow |
| `effectiveDate` | `ExtendedInfo[Name='OfferOriginalEffectiveDate']/Value` | Per-offer |
| `remark` | `"$currentPricePlan->$offer.OfferName"` | Per-offer |
| `code` | `offer.Soc` (also used as RefID response match key) | Per-offer |
| `inputFlgSms` | Subscriber `ExtendedInfo[Name="FLG_SMS"]/Value` (else "") | Subscriber variants only |

### OMX-2896 FLG_SMS support

For subscriber variants (② and ④): if `ExtendedInfo[Name="FLG_SMS"]` exists, its value is passed as `FLG_SMS_WELCOME_SUB` extendedInfo in the payload — used for corporate welcome SMS.

### Secondary futureSoc (FE/TR_CONTRACT_NUMBER)

For every variant, after the primary futureSoc, the XSLT adds extra `futureSoc` elements for any offer in the current scope that meets all three conditions:
- `ServiceType = 85`
- `ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']`
- `boolean(ParameterInfo[ParamName = 'TR_CONTRACT_NUMBER'])`

### futureResourceRange (Subscriber variants only)

Subscriber variants (② and ④) append `ns4:futureResourceRange` elements for each `ResourceRangeInfo[Action='PP']` entry.

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Fires in **CHANGE_PP** step 35 for all qualifying OU/Subscriber offer entries that need future price plan records created.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` | Create future PP order record in OMX |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` | Completion acknowledgement |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | Audit log |

### §8.3 Payload Schemas

| Namespace prefix | Schema URI | Root element |
|-----------------|-----------|-------------|
| `ns3` | `FutureOrderWithSoc.xsd` | `ns3:futureOrderWithSoc` (wrapper) |
| `ns` | `FutureOrder.xsd` | `ns:futureOrder` (order metadata) |
| `ns2` | `FutureSoc.xsd` | `ns2:futureSocs/futureSoc` (SOC entries) |
| `ns4` | `FutureResourceRange.xsd` | `ns4:futureResourceRange` (Subscriber only) |

### §8.4 Variant Differences Summary

| Parameter | ① POU Agree | ② POU Sub | ③ COU Agree | ④ COU Sub |
|-----------|------------|-----------|------------|-----------|
| nodeLevel | 3 | 5 | 3 | 5 |
| nodeId | pOuId | subId | cOu.OUId | subId |
| userText format | "FUTPP request by ..." | "request by ..." | "request by ..." | "request by ..." |
| OU_ID extended | — | — | Yes (cOu.OUId) | Yes (cOu.OUId) |
| SUB_ID/MOBILE_NO | — | Yes | — | Yes |
| FLG_SMS_WELCOME_SUB | — | Yes | — | Yes |
| futureResourceRange | — | Yes | — | Yes |
| PreExecCheck helper | GetXMLForAgreementOffer | GetXMLForSubscriberOffer | GetXMLForAgreementOfferInChildOU | GetXMLForSubscriberOfferInChildOU |

### §8.5 ExtendedInfo Fields

| Name | Value checked | Where |
|------|--------------|-------|
| `FE_OR_CCBS` | `"CCBS"` | Current price plan lookup: `Offers[ServiceType='80']` |
| `FE_OR_CCBS` | `"FE"` | Secondary futureSoc: ST=85 FE TR_CONTRACT_NUMBER offers |
| `OfferOriginalEffectiveDate` | date string | effectiveDate for future SOC |
| `FLG_SMS` | any value | Subscriber variant: FLG_SMS_WELCOME_SUB in payload |

## §9 — Detailed Payload Build

### §9.3 Event Header Fields (all variants)

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Conditional (if present) |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Conditional |
| `RefID` | `$contextNode/RefId` (pOu/subscriberPou/cOu/subscriberCou) | Conditional |
| `UserName` | `$orderRequest/OrderData/User` | Conditional |
| `PassWord` | `$orderRequest/OrderData/Password` | Conditional |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Conditional |

### §9.6 Core Payload — futureOrderWithSoc

| Element | Source | Condition |
|---------|--------|-----------|
| `ns:effectiveDate` | `ExtendedInfo[OfferOriginalEffectiveDate]/Value` | Always |
| `ns:orderType` | `2` (static) | Always |
| `ns:nodeLevel` | `3` (OU) or `5` (Sub) | Always |
| `ns:nodeId` | OUId (OU variants) or subId (Sub variants) | Always |
| `ns:requestedDate` | `current-dateTime()` | Always |
| `ns:requestedBy` | `$requestBy` (Channel) | Always |
| `ns:activityReason` | ActivityInfo.ActivityReason | Conditional |
| `ns:extendedInfo POU_ID` | `$pOuId` | if trim>0 |
| `ns:extendedInfo CUS_ID` | `$custId` | if trim>0 |
| `ns:extendedInfo PAGR_ID` | `$pAgreeId` | if trim>0 |
| `ns:extendedInfo SUB_ID` | `$subId` | Subscriber variants only, if trim>0 |
| `ns:extendedInfo MOBILE_NO` | `$msisdn` | Subscriber variants only, if trim>0 |
| `ns:extendedInfo FLG_SMS_WELCOME_SUB` | `$inputFlgSms` | Subscriber variants only, if trim>0 |
| `ns:extendedInfo OU_ID` | `$cOu/OUId` | ChildOU variants only (always) |
| `ns:fromOrderId` | `$orderRequest/OrderData/OrderID` | Conditional |
| `ns:userText` | Formatted with inputUserText + Channel + dateTimeNow | Always |
| `ns:remark` | `currentPricePlan->offerName` | Always |
| `ns:customerType` | `$customerType` (ASCII-decoded) | Always |
| `ns:accountSubtype` | `$accountSubType` | Always |
| `ns:futureType` | `"FUTPP"` (static) | Always |
| `ns2:futureSoc/ns2:code` | `$code` (offer.Soc) | Always |
| `ns2:futureSoc/ns2:effectiveDate` | `$effectiveDate` | Always |
| `ns2:futureSoc/ns2:parameter` | for-each offer.ParameterInfo | Per-item loop |
| `ns2:futureSoc/ns2:childSoc` | for-each offer.RelatedOffersArray | Per-item loop |
| `ns2:futureSoc/ns2:type` | `"80"` (static) | Always |
| `ns2:futureSoc/ns2:subType` | `"FUTPP"` (static) | Always |
| `ns2:futureSoc/ns2:socName` | `$offer/OfferName` | Conditional |
| Extra futureSoc (ST=85 FE) | for-each scope offers where ST=85+FE+TR_CONTRACT_NUMBER | Conditional loop |
| `ns4:futureResourceRange` | for-each ResourceRangeInfo[Action='PP'] | Subscriber variants only |

### §9.7 Complete Generated XML Example (Variant ① — ParentOU Agreement)

```xml
<event>
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-20260914-001</JMSCorrelationID>
  <OrderID>ORD-12345</OrderID>
  <RefID>pou-ref-001</RefID>
  <OrderType>11001</OrderType>
  <payload>
    <ns3:futureOrderWithSoc>
      <ns:futureOrder>
        <ns:effectiveDate>2026-09-01T00:00:00+07:00</ns:effectiveDate>
        <ns:orderType>2</ns:orderType>
        <ns:nodeLevel>3</ns:nodeLevel>
        <ns:nodeId>OU-001</ns:nodeId>
        <ns:requestedDate>2026-09-14T10:00:00+07:00</ns:requestedDate>
        <ns:requestedBy>ONLINE</ns:requestedBy>
        <ns:extendedInfo><ns:name>POU_ID</ns:name><ns:value>OU-001</ns:value></ns:extendedInfo>
        <ns:extendedInfo><ns:name>CUS_ID</ns:name><ns:value>CUST-001</ns:value></ns:extendedInfo>
        <ns:extendedInfo><ns:name>PAGR_ID</ns:name><ns:value>AGR-001</ns:value></ns:extendedInfo>
        <ns:fromOrderId>ORD-12345</ns:fromOrderId>
        <ns:userText>;FUTPP request by ONLINE on 2026-09-14T10:00:00;</ns:userText>
        <ns:remark>OLD_PP->NEW_PP</ns:remark>
        <ns:customerType>P</ns:customerType>
        <ns:accountSubtype>CONSUMER</ns:accountSubtype>
        <ns:futureType>FUTPP</ns:futureType>
      </ns:futureOrder>
      <ns2:futureSocs>
        <ns2:futureSoc>
          <ns2:code>PP-SOC-001</ns2:code>
          <ns2:effectiveDate>2026-09-01T00:00:00+07:00</ns2:effectiveDate>
          <ns2:type>80</ns2:type>
          <ns2:subType>FUTPP</ns2:subType>
          <ns2:socName>NEW_PP</ns2:socName>
        </ns2:futureSoc>
      </ns2:futureSocs>
    </ns3:futureOrderWithSoc>
  </payload>
</event>
```

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent                                                         [Variant ① POU Agreement — representative]
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority            [Conditional: if OrderPriority present]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId  [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID         [Conditional]
    ├── RefID                ← $contextNode/RefId                      [Conditional: if RefId present]
    ├── UserName             ← $orderRequest/OrderData/User            [Conditional]
    ├── PassWord             ← $orderRequest/OrderData/Password        [Conditional]
    ├── OrderType            ← $orderRequest/OrderData/OrderType       [Conditional]
    └── payload
        └── ns3:futureOrderWithSoc
            ├── ns:futureOrder
            │   ├── ns:effectiveDate       ← ExtendedInfo[OfferOriginalEffectiveDate]/Value   [Always]
            │   ├── ns:orderType           ← "2" (static)                                     [Always]
            │   ├── ns:nodeLevel           ← "3" (OU) / "5" (Sub)                             [Always]
            │   ├── ns:nodeId              ← $nodeId (OUId or subId)                          [Always]
            │   ├── ns:requestedDate       ← current-dateTime()                               [Always]
            │   ├── ns:requestedBy         ← $requestBy (Channel)                             [Always]
            │   ├── ns:activityReason      ← ActivityInfo/ActivityReason                      [Conditional]
            │   ├── ns:extendedInfo POU_ID ← $pOuId                                           [Conditional: if trim>0]
            │   ├── ns:extendedInfo CUS_ID ← $custId                                          [Conditional: if trim>0]
            │   ├── ns:extendedInfo PAGR_ID← $pAgreeId                                        [Conditional: if trim>0]
            │   ├── ns:extendedInfo SUB_ID ← $subId                                           [Sub variants only, if trim>0]
            │   ├── ns:extendedInfo MOBILE_NO ← $msisdn                                       [Sub variants only, if trim>0]
            │   ├── ns:extendedInfo FLG_SMS_WELCOME_SUB ← $inputFlgSms                        [Sub variants only, if trim>0]
            │   ├── ns:extendedInfo OU_ID  ← $cOu/OUId                                        [ChildOU variants only, Always]
            │   ├── ns:fromOrderId         ← $orderRequest/OrderData/OrderID                  [Conditional]
            │   ├── ns:userText            ← formatted string                                  [Always]
            │   ├── ns:remark              ← currentPricePlan->offerName                       [Always]
            │   ├── ns:customerType        ← $customerType (ASCII-decoded)                    [Always]
            │   ├── ns:accountSubtype      ← $accountSubType                                   [Always]
            │   └── ns:futureType          ← "FUTPP" (static)                                  [Always]
            └── ns2:futureSocs
                ├── ns2:futureSoc  [primary]
                │   ├── ns2:code          ← $code (offer.Soc)                                 [Always]
                │   ├── ns2:effectiveDate ← $effectiveDate                                    [Always]
                │   ├── ns2:parameter     ← for-each ParameterInfo                            [Conditional loop]
                │   ├── ns2:childSoc      ← for-each RelatedOffersArray                       [Conditional loop]
                │   ├── ns2:type          ← "80" (static)                                     [Always]
                │   ├── ns2:subType       ← "FUTPP" (static)                                  [Always]
                │   └── ns2:socName       ← $offer/OfferName                                  [Conditional]
                ├── ns2:futureSoc  [extra — for-each ST=85+FE+TR_CONTRACT_NUMBER offers]       [Conditional loop]
                └── ns4:futureResourceRange ← for-each ResourceRangeInfo[Action='PP']         [Sub variants only]
```

## §11 — Audit Logging

| Field | Request (POU Agree) | Request (POU Sub / COU) | Response |
|-------|---------------------|------------------------|---------|
| OPERATION_NAME | `"OMX_ADD_FUTPP"` | `"OMX_ADD_FUT_PP"` | `"OMX_ADD_FUTPP"` |
| AUDIT_TRACE | `"Request Sent for OMX_ADD_FUTPP"` | `"Request Sent for OMX_ADD_FUT_PP"` | `"Response received for OMX_ADD_FUTPP"` |

> **Naming inconsistency:** ParentOU Agreement audit uses `"OMX_ADD_FUTPP"`, Subscriber/ChildOU audits use `"OMX_ADD_FUT_PP"`. Standardise during migration.

## §12 — Activity Status Management

| Code | When |
|------|------|
| "1" (PROCESSING) | At least one request sent across all variants |
| "4" (SKIPPED) | No qualifying offers found in any variant, or all PreExecChecks failed |
| ERROR | Exception → `HandleActivityException` |

## §13 — Exception / Error Handling

`try/catch(Exception ae)` wraps all logic. On exception: `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `GetXMLForAgreementOffer(orderRequest, agreeRefId, offerRefId)` | Serialise ParentOU Agreement+offer for PreExecCheck |
| `GetXMLForSubscriberOffer(orderRequest, subRefId, offerRefId)` | Serialise ParentOU Subscriber+offer for PreExecCheck |
| `GetXMLForAgreementOfferInChildOU(orderRequest, agreeRefId, offerRefId, pOuRefId)` | Serialise ChildOU Agreement+offer |
| `GetXMLForSubscriberOfferInChildOU(orderRequest, subRefId, offerRefId, pOuRefId)` | Serialise ChildOU Subscriber+offer |
| `OMXUtils.asciiCodeToText(int)` | Converts ASCII integer to text character (customerType) |
| `GetActivityStatusString` | Maps status code to string |
| `SendDataToDB` | Persists state |
| `SkipActivity` | Advances flow on skip |
| `HandleActivityException` | Handles exceptions |
| `IsAllResponseSuccess(currActivity)` | Fan-in check in response rulefunction |

## §15 — Function Dependency Tree

```text
Request_OMX_ADD_FUT_PP
├── OMXUtils.asciiCodeToText  [once, at start]
├── RuleFunctions.Helpers.GetXMLForAgreementOffer  [per ParentOU Agreement offer]
├── RuleFunctions.Helpers.GetXMLForSubscriberOffer  [per ParentOU Subscriber offer]
├── RuleFunctions.Helpers.GetXMLForAgreementOfferInChildOU  [per ChildOU Agreement offer]
├── RuleFunctions.Helpers.GetXMLForSubscriberOfferInChildOU  [per ChildOU Subscriber offer]
├── Event.Ext.sendEventImmediate (OMX_ADD_FUTURE)  [per qualifying offer, all variants]
├── Event.Ext.sendEventImmediate (Logger)  [per sent event]
├── RuleFunctions.Helpers.GetActivityStatusString
├── RuleFunctions.Helpers.SendDataToDB
├── RuleFunctions.Helpers.SkipActivity  [if no requests sent]
└── RuleFunctions.Helpers.HandleActivityException  [on error]
```

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1:** For every qualifying offer in ParentOU Agreement, ParentOU Subscriber, ChildOU Agreement, and ChildOU Subscriber scopes, create a FUTPP future order record.
- **R2:** customerType must be derived by ASCII-decoding `CustomerTypeInfo/Type` via `OMXUtils.asciiCodeToText()`.
- **R3:** Secondary futureSoc must be added for any ServiceType=85/FE/TR_CONTRACT_NUMBER offer.
- **R4:** Subscriber variants must carry `futureResourceRange` entries for `ResourceRangeInfo[Action='PP']` items.
- **R5:** ChildOU variants must add `OU_ID` extendedInfo; Subscriber variants add `SUB_ID`, `MOBILE_NO`, `FLG_SMS_WELCOME_SUB` (conditional).

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Audit OPERATION_NAME inconsistency between variants | [MEDIUM] | Standardise to single name; check monitoring dashboards |
| Status set inside loop AND again after loop — double-set on multi-offer orders | [LOW] | No functional impact; move to post-loop only |
| FLG_SMS XPath has `subscriberPou` listed twice in variables block | [LOW] | Likely harmless; clean up in migration |

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_FUT_PP {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_ADD_FUT_PP";
    orderRequest.ProcessFlow.NextActivityID == "OMX_ADD_FUT_PP";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      boolean isSkipped = true;
      // Read globals: customerType (ASCII-decoded), accountSubType, requestBy=Channel
      // static: orderType=2, type="80", futureType="FUTPP"
      for (int iPOU = 0; iPOU < orderRequest.OrderData.Customer.ParentOU@length; iPOU++) {
        // --- Variant ①: ParentOU Agreement Offers ---
        // for each offer: GetXMLForAgreementOffer + PreExecCheck + reqSuccess guard
        // Event.createEvent (see §9.8 — futureOrderWithSoc POU variant, OPERATION_NAME="OMX_ADD_FUTPP")
        // --- Variant ②: ParentOU Subscriber Offers ---
        // for each offer: GetXMLForSubscriberOffer + PreExecCheck + reqSuccess guard
        // Event.createEvent (see §9.8 — futureOrderWithSoc Subscriber variant, OPERATION_NAME="OMX_ADD_FUT_PP")
        // --- Variants ③ ④: ChildOU ---
        for (int iCOU = 0; iCOU < orderRequest.OrderData.Customer.ParentOU[iPOU].ChildOU@length; iCOU++) {
          // Variant ③: ChildOU Agreement Offers → GetXMLForAgreementOfferInChildOU
          // Variant ④: ChildOU Subscriber Offers → GetXMLForSubscriberOfferInChildOU
        }
      }
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

## §19 — Response Message Rule

### §19.1 Overview

`Response_OMX_ADD_FUT_PP` creates a `Concepts.FM.Response.OMX_AddFutureRes` concept, appends it to `currActivity.Response[]`, logs the audit event, and returns `RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)` for fan-in.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Context (not mutated) |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` | Backend response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | RequestCount for fan-in |

### §19.3 ResponseBase Concept Construction

```text
createObject  [Concepts.FM.Response.OMX_AddFutureRes]
└── object
    ├── @extId           ← OMXUtils:generateTrackingID()     [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode       [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg        [Conditional]
    └── CompletionStatus ← $eventResponse/CompletionStatus   [Conditional]
```

> **Note:** No ReferenceId in this response concept. Fan-in uses `IsAllResponseSuccess(currActivity)` (RequestCount check), not a RefID+CompletionStatus=2 match.

### §19.4 Response Completion Logic

Returns `RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)` — standard fan-in pattern checking all accumulated responses indicate success.

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
