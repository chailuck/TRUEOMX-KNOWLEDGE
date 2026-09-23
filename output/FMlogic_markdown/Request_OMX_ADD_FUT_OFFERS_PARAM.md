# Request_OMX_ADD_FUT_OFFERS_PARAM

> Add Future Offer Parameters — parallel fan-out to OMX FM per ParameterInfo entry across 4 entity scopes

**Author:** warawich-nb | **Priority:** 5 | **forwardChain:** true | **Type:** OMXFM Request  
**Backend:** OMX FM (OMX_ADD_FUTURE) | **futureType:** FUTPARAM | **orderType:** 5  
**Generated:** 2026-08-20

---

## §1 — Overview & Purpose

This rule registers future parameter changes (`futureType=FUTPARAM`, `orderType=5`) for offers in the order. It iterates every qualifying offer's `ParameterInfo` array across four entity scopes — POU Agreement, POU Subscriber, COU Agreement, COU Subscriber — and dispatches one `OMX_ADD_FUTURE` JMS event to OMX FM per parameter entry. Events are sent via `sendEventImmediate` (parallel fan-out). A resubmit-safety check guards against double-sending already-completed requests.

> **Context:** Used in POSTPAID_UPDATE_PARAMETER step 21 to add future offer parameter entries to the FM system before the subscriber profile update commits.

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_FUT_OFFERS_PARAM` |
| Event type (outbound) | `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` |
| Event type (inbound) | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` |
| Payload schema | `ns3:futureOrderWithSoc` (FutureOrderWithSoc.xsd) |
| Response concept | `Concepts.FM.Response.OMX_AddFutureRes` |
| Dispatch pattern | Parallel fan-out (`sendEventImmediate`) |
| Granularity | One request **per ParameterInfo entry** per qualifying offer per scope |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Note |
|-----------|-------|------|
| priority | 5 | Standard FM request priority |
| forwardChain | true | Allows further rule evaluation after execution |
| Rule type | OMXFM Request | Dispatches to backend via JMS; has corresponding response rulefunction |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order — contains all entity data (Customer, ParentOU, ChildOU, Subscribers, Offers, ParameterInfo) |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process activity — tracks Status, RequestCount, Response array |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to current process position |
| 2 | `orderCurrentActivity.ActivityID == "OMX_ADD_FUT_OFFERS_PARAM"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_ADD_FUT_OFFERS_PARAM"` | Redundant dual-binding confirmation |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Ensures rule fires only when awaiting execution |

---

## §5 — Execution Flow

1. **Resubmit check** → set `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. **Resolve LogicalDate** → load `LogicalDate` concept from working memory; fall back to `DateTime.now()` if empty
3. **Load PreExecCheck** → read `nextAct.PreExecCheck` XPath string from activity config
4. **Scope A — POU Agreement** → iterate Offers → ParameterInfo; PreExecCheck per offer via `GetXMLForAgreementOffer`; dispatch `OMX_ADD_FUTURE` per param; send audit log (AUDIT_TRACE inconsistency — see bugs)
5. **Scope B — POU Subscriber** → iterate SubscriberOffers → ParameterInfo; read `FE_OR_CCBS` for PreExecCheck filter; dispatch per param; send audit log
6. **Scope C — COU Agreement** → iterate Offers → ParameterInfo; dispatch per param; **no audit log emitted (bug)**
7. **Scope D — COU Subscriber** → iterate SubscriberOffers → ParameterInfo; read `FE_OR_CCBS` for PreExecCheck filter; dispatch per param; send audit log
8. **Post-dispatch** → if `isSkipped=true` → `SkipActivity("4")`; else → set INPROGRESS + `SendDataToDB()`
9. **Exception handling** → catch all → `HandleActivityException()`

---

## §6 — Rule Action (THEN) — Detailed Logic

### Scope A — POU Agreement (nodeLevel=3)

- Iterates `ParentOU[iPOU].Agreement.Offers[iPouOffer].ParameterInfo[iOfferParam]`
- PreExecCheck via `GetXMLForAgreementOffer(orderRequest, agreeRefId, refId)`
- Resubmit guard: `Response[iResp].ReferenceId == offer.Soc && CompletionStatus==2` → skip (broken — see §17)
- effectiveDate: prefer `ExtendedInfo[Name='offerParamOriginalEffectiveDate']/Value`, else `ParameterInfo.EffectiveDate`
- If `GetActivityEffectiveType(EffectiveDate, logicalDate) != "FUT"` → null the EffectiveDate (in-memory mutation)
- `nodeId = pOu.OUId`; `RefID = pOu.RefId`
- userText format: `"%s;FUTPARAM request by %s on %s;"` (note extra "FUTPARAM" prefix)
- AUDIT_TRACE = "Request Sent for OMX_ADD_FUTPP" — **[MEDIUM] inconsistency**
- Payload param: single `$agreementParameterInfo` per request

### Scope B — POU Subscriber (nodeLevel=5)

- Iterates `ParentOU[iPOU].Subscriber[iPouSub].SubscriberOffers[iPouSubOffer].ParameterInfo[iOfferParam]`
- PreExecCheck via `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, subRefId, refId, filter)` where `filter = offer.ExtendedInfo[Name="FE_OR_CCBS"]/Value`
- `nodeId = subscriberPou.SubscriberId`; `RefID = subscriberPou.RefId`
- Payload includes: SUB_ID, MOBILE_NO, PAGR_ID, PRIMARY_RESOURCE_TYPE ExtendedInfo
- Payload param: single `$offerParameterInfo` per request
- AUDIT_TRACE = "Request Sent for OMX_ADD_FUT_OFFERS_PARAM" (correct)

### Scope C — COU Agreement (nodeLevel=3)

- Iterates `ChildOU[iCOU].Agreement.Offers[iCouOffer].ParameterInfo[iOfferParam]`
- PreExecCheck via `GetXMLForAgreementOfferInChildOU(orderRequest, agreeRefId, refId, pOu.RefId)`
- `nodeId = cOu.OUId`; `RefID = cOu.RefId`
- **[MEDIUM] Payload XSLT uses `xsl:for-each select="$offer/ParameterInfo"` — all params per request** (inconsistent with POU scopes)
- Payload includes: OU_ID (always); PAGR_ID (conditional)
- **[MEDIUM] No audit log emitted** — `pid` computed but logger event never sent

### Scope D — COU Subscriber (nodeLevel=5)

- Iterates `ChildOU[iCOU].Subscriber[iCouSub].SubscriberOffers[iCouSubOffer].ParameterInfo[iOfferParam]`
- PreExecCheck via `GetXMLForSubscriberOfferInChildOU(orderRequest, subRefId, refId, pOu.RefId)`
- `nodeId = subscriberCou.SubscriberId`; `RefID = subscriberCou.RefId`
- **[MEDIUM] Payload XSLT uses `xsl:for-each select="$offer/ParameterInfo"` — all params per request**
- Payload includes: SUB_ID, MOBILE_NO, PAGR_ID, PRIMARY_RESOURCE_TYPE, OU_ID (always)
- AUDIT_TRACE = "Request Sent for OMX_ADD_FUT_OFFERS_PARAM" (correct)

### FE Contract Auto-Include (all scopes)

Each payload XSLT appends an additional `ns2:futureSoc` for every offer in the parent entity matching all three:
- `ServiceType = 85`
- `ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']`
- `boolean(ParameterInfo[ParamName='TR_CONTRACT_NUMBER'])`

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

| Parameter | Value | Source |
|-----------|-------|--------|
| futureType | `FUTPARAM` | Hardcoded |
| orderType | `5` | Hardcoded |
| ProcessConfig usage | Step 21 — POSTPAID_UPDATE_PARAMETER | ProcessConfig XML |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` | Dispatch add-future-offer-param request |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` | Receive success/failure from FM |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | Audit trail |

### §8.3 — Backend API Details

| System | Operation | Schema | Protocol |
|--------|-----------|--------|----------|
| OMX FM | OMX_ADD_FUTURE | `ns3:futureOrderWithSoc` (FutureOrderWithSoc.xsd) | JMS / TIBCO EMS |

### §8.4 — BE Working Memory Dependencies

| Concept | Access | Fields Used |
|---------|--------|------------|
| `OrderRequest` | Read | OrderData.Customer.{ParentOU,ChildOU,Subscriber,Agreement,Offers,ParameterInfo}, Channel, OMXTrackingId |
| `Activity` | Read/Write | Status, RequestCount, Response[], PreExecCheck |
| `ParameterInfo` | Read+**Mutate** | EffectiveDate (nulled if not FUT type) |
| `LogicalDate` | Read | LogicalDate string |

### §8.5 — ExtendedInfo Fields Required

| Key | Required/Optional | Scope | Purpose |
|-----|------------------|-------|---------|
| `offerParamOriginalEffectiveDate` | Optional | ParameterInfo | Preferred effectiveDate source |
| `FE_OR_CCBS` | Optional | SubscriberOffers | Filter for Subscriber PreExecCheck; FE contract detection |
| `PRIMARY_RESOURCE_TYPE` | Optional | Subscriber | Included in payload extendedInfo |

### §8.6 — Global Variable Dependencies

| Path | Used For |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Gates payload logging |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding (4 scope variants)

| Parameter | Scope A (POU Agree) | Scope B (POU Sub) | Scope C (COU Agree) | Scope D (COU Sub) |
|-----------|--------------------|--------------------|--------------------|--------------------|
| `nodeLeve` | 3 | 5 | 3 | 5 |
| `nodeId` | `pOu.OUId` | `subscriberPou.SubscriberId` | `cOu.OUId` | `subscriberCou.SubscriberId` |
| param variable | `agreementParameterInfo` (single) | `offerParameterInfo` (single) | `xsl:for-each ParameterInfo` | `xsl:for-each ParameterInfo` |
| `futureType` | FUTPARAM | FUTPARAM | FUTPARAM | FUTPARAM |

### §9.4 — Payload Root Element

| Element | Namespace |
|---------|-----------|
| `ns3:futureOrderWithSoc` | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrderWithSoc.xsd` |
| `ns:futureOrder` | FutureOrder.xsd |
| `ns2:futureSocs/ns2:futureSoc` | FutureSoc.xsd |

### §9.7 — Complete Generated XML Example (Scope B: POU Subscriber)

```xml
<ns3:futureOrderWithSoc xmlns:ns3="...FutureOrderWithSoc.xsd">
  <ns:futureOrder>
    <ns:effectiveDate>2026-08-20T00:00:00+07:00</ns:effectiveDate>
    <ns:orderType>5</ns:orderType>
    <ns:nodeLevel>5</ns:nodeLevel>
    <ns:nodeId>SUB00012345</ns:nodeId>
    <ns:requestedDate>2026-08-20T10:30:00</ns:requestedDate>
    <ns:requestedBy>WEB</ns:requestedBy>
    <ns:activityReason>REASON_X</ns:activityReason>  <!-- conditional -->
    <ns:extendedInfo><ns:name>POU_ID</ns:name><ns:value>POU001</ns:value></ns:extendedInfo>
    <ns:extendedInfo><ns:name>CUS_ID</ns:name><ns:value>CUST001</ns:value></ns:extendedInfo>
    <ns:extendedInfo><ns:name>SUB_ID</ns:name><ns:value>SUB00012345</ns:value></ns:extendedInfo>
    <ns:extendedInfo><ns:name>MOBILE_NO</ns:name><ns:value>0812345678</ns:value></ns:extendedInfo>
    <ns:extendedInfo><ns:name>PAGR_ID</ns:name><ns:value>AGR001</ns:value></ns:extendedInfo>
    <ns:extendedInfo><ns:name>PRIMARY_RESOURCE_TYPE</ns:name><ns:value>MOBILE</ns:value></ns:extendedInfo>
    <ns:fromOrderId>ORD-20260820-001</ns:fromOrderId>
    <ns:userText>;request by WEB on 2026-08-20T10:30:00;</ns:userText>
    <ns:accountSubtype>POSTPAID</ns:accountSubtype>
    <ns:futureType>FUTPARAM</ns:futureType>
  </ns:futureOrder>
  <ns2:futureSocs>
    <ns2:futureSoc>
      <ns2:code>SOC_ABC</ns2:code>
      <ns2:instanceId>INST001</ns2:instanceId>  <!-- conditional -->
      <ns2:parameter>
        <ns2:paramName>PARAM_NAME</ns2:paramName>
        <ns2:paramValue>VALUE</ns2:paramValue>
      </ns2:parameter>
      <ns2:type>1</ns2:type>  <!-- conditional -->
      <ns2:subType>FUTPARAM</ns2:subType>
      <ns2:socName>Offer Display Name</ns2:socName>  <!-- conditional -->
    </ns2:futureSoc>
    <!-- FE contract auto-include (ServiceType=85, FE_OR_CCBS=FE, TR_CONTRACT_NUMBER) -->
    <ns2:futureSoc><ns2:code>FE_SOC</ns2:code>...</ns2:futureSoc>
  </ns2:futureSocs>
</ns3:futureOrderWithSoc>
```

---

## §10 — XSLT Field Mapping — Output XML Tree

```text
createEvent
└── event
    ├── JMSPriority           ← $orderRequest/OrderPriority          [Conditional]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId [Always]
    ├── OrderID               ← $orderRequest/OrderData/OrderID       [Conditional]
    ├── RefID                 ← parent entity RefId (per scope)       [Conditional]
    ├── UserName              ← $orderRequest/OrderData/User          [Conditional]
    ├── PassWord              ← $orderRequest/OrderData/Password      [Conditional]
    ├── OrderType             ← $orderRequest/OrderData/OrderType     [Conditional]
    └── payload
        └── ns3:futureOrderWithSoc
            ├── ns:futureOrder
            │   ├── ns:effectiveDate    ← offerParamOriginalEffectiveDate [Always]
            │   ├── ns:orderType        ← "5"                             [Always]
            │   ├── ns:nodeLevel        ← 3 (OU) or 5 (Sub)              [Always]
            │   ├── ns:nodeId           ← OUId or SubscriberId            [Always]
            │   ├── ns:requestedDate    ← current-dateTime()              [Always]
            │   ├── ns:requestedBy      ← Channel                         [Always]
            │   ├── ns:activityReason   ← ActivityReason                  [Conditional]
            │   ├── ns:extendedInfo     POU_ID ← pOuId                   [Conditional: non-empty]
            │   ├── ns:extendedInfo     CUS_ID ← custId                  [Conditional: non-empty]
            │   ├── ns:extendedInfo     SUB_ID ← subId                   [Scopes B,D; Conditional]
            │   ├── ns:extendedInfo     MOBILE_NO ← msisdn               [Scopes B,D; Conditional]
            │   ├── ns:extendedInfo     PAGR_ID ← pAgreeId               [Scopes A,B,D; Conditional]
            │   ├── ns:extendedInfo     PRIMARY_RESOURCE_TYPE             [Scopes B,D; Conditional]
            │   ├── ns:extendedInfo     OU_ID ← cOu.OUId                 [Scopes C,D; Always]
            │   ├── ns:fromOrderId      ← OrderID                         [Conditional]
            │   ├── ns:userText         ← formatted string                [Always]
            │   ├── ns:accountSubtype   ← AccountSubType                  [Always]
            │   └── ns:futureType       ← "FUTPARAM"                      [Always]
            └── ns2:futureSocs
                ├── ns2:futureSoc  [primary offer]
                │   ├── ns2:code          ← offer.Soc                     [Always]
                │   ├── ns2:instanceId    ← OfferInstanceId               [Conditional]
                │   ├── ns2:parameter     ← single param (Scopes A,B)     [Always when found]
                │   │                       or all ParameterInfo (Scopes C,D)
                │   ├── ns2:childSoc      ← RelatedOffersArray            [Conditional]
                │   ├── ns2:type          ← ServiceType                   [Conditional]
                │   ├── ns2:subType       ← "FUTPARAM"                    [Always]
                │   └── ns2:socName       ← OfferName                     [Conditional]
                └── ns2:futureSoc  [FE contract: ServiceType=85, FE_OR_CCBS=FE, TR_CONTRACT_NUMBER]
```

---

## §11 — Audit Logging

| Scope | OPERATION_NAME | AUDIT_TRACE | Note |
|-------|----------------|-------------|------|
| A — POU Agreement Request | OMX_ADD_FUT_OFFERS_PARAM | "Request Sent for OMX_ADD_FUTPP" | **[MEDIUM] Wrong suffix** |
| B — POU Subscriber Request | OMX_ADD_FUT_OFFERS_PARAM | "Request Sent for OMX_ADD_FUT_OFFERS_PARAM" | OK |
| C — COU Agreement Request | — | — | **[MEDIUM] No audit log** |
| D — COU Subscriber Request | OMX_ADD_FUT_OFFERS_PARAM | "Request Sent for OMX_ADD_FUT_OFFERS_PARAM" | OK |
| Response | OMX_ADD_FUT_OFFERS_PARAM | "Response received for OMX_ADD_FUT_OFFERS_PARAM" | OK |

> **WritePayload gate:** Payload included in audit log only when `$globalVariables/OMX_OM/WritePayload = "true"`.

---

## §12 — Activity Status Management

| Condition | Status | Call |
|-----------|--------|------|
| At least one request dispatched | INPROGRESS | `GetActivityStatusString("1", false)` |
| No requests sent | SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception caught | ERROR | `HandleActivityException()` |

---

## §13 — Exception / Error Handling

All logic is wrapped in `try { ... } catch (Exception ae)`. On exception: `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §14 — Helper Functions Reference

| Function | Purpose | Scope |
|----------|---------|-------|
| `GetXMLForAgreementOffer()` | Builds XML for Agreement offer PreExecCheck | A |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo()` | Builds XML with FE_OR_CCBS filter | B |
| `GetXMLForAgreementOfferInChildOU()` | Builds XML for COU Agreement PreExecCheck | C |
| `GetXMLForSubscriberOfferInChildOU()` | Builds XML for COU Subscriber PreExecCheck | D |
| `GetActivityEffectiveType(EffectiveDate, logicalDate)` | Returns "FUT" if date is future; gates EffectiveDate nulling | All |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | Marks activity skipped | Post-dispatch |
| `SendDataToDB(orderRequest)` | Persists order state | Post-dispatch |
| `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | Records exception, sets ERROR | catch |

---

## §15 — Function Dependency Tree

```text
Request_OMX_ADD_FUT_OFFERS_PARAM.rule
├── Instance.getByExtIdByUri("LogicalDate", ...)
├── Scope A: POU Agreement
│   ├── RuleFunctions.Helpers.GetXMLForAgreementOffer()
│   ├── RuleFunctions.Helpers.GetActivityEffectiveType()
│   ├── Event.Ext.sendEventImmediate() → OMX_ADD_FUTURE (per param)
│   └── Event.Ext.sendEventImmediate() → Logger
├── Scope B: POU Subscriber
│   ├── RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo()
│   ├── RuleFunctions.Helpers.GetActivityEffectiveType()
│   ├── Event.Ext.sendEventImmediate() → OMX_ADD_FUTURE (per param)
│   └── Event.Ext.sendEventImmediate() → Logger
├── Scope C: COU Agreement
│   ├── RuleFunctions.Helpers.GetXMLForAgreementOfferInChildOU()
│   ├── RuleFunctions.Helpers.GetActivityEffectiveType()
│   └── Event.Ext.sendEventImmediate() → OMX_ADD_FUTURE (per param)  [no logger]
├── Scope D: COU Subscriber
│   ├── RuleFunctions.Helpers.GetXMLForSubscriberOfferInChildOU()
│   ├── RuleFunctions.Helpers.GetActivityEffectiveType()
│   ├── Event.Ext.sendEventImmediate() → OMX_ADD_FUTURE (per param)
│   └── Event.Ext.sendEventImmediate() → Logger
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB()
├── RuleFunctions.Helpers.SkipActivity()
└── RuleFunctions.Helpers.HandleActivityException()

Response_OMX_ADD_FUT_OFFERS_PARAM.rulefunction
├── Instance.createInstance("xslt://{{/Concepts/FM/Response/OMX_AddFutureRes}}")
│   └── Maps: ResponseCode, ResponseMessage (←ResponseMsg), CompletionStatus
│   └── [MISSING: ReferenceId — resubmit protection broken]
├── Event.Ext.sendEventImmediate() → Logger (_RES suffix)
└── XPath.evalAsInt(count(Response[tib:right(tib:trim(ResponseCode),3)="000"]))
    └── if RequestCount == successResponseCount → return "true"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | For every qualifying offer's ParameterInfo across POU Agreement, POU Subscriber, COU Agreement, COU Subscriber, dispatch add-future-offer-param with `futureType=FUTPARAM`, `orderType=5` |
| R2 | effectiveDate must prefer `offerParamOriginalEffectiveDate` ExtendedInfo; if not future type (vs LogicalDate), send null |
| R3 | FE contract offers (ServiceType=85, FE_OR_CCBS=FE, TR_CONTRACT_NUMBER param) must be auto-appended as additional futureSoc entries |
| R4 | PreExecCheck XPath gates offer-level dispatch; each scope uses a different helper |
| R5 | Fan-in: declare complete when `count(Response[suffix="000"]) == RequestCount` |

### Design Risks

| Risk | Severity | Detail | Mitigation |
|------|----------|--------|-----------|
| Resubmit protection broken — no ReferenceId in response | [HIGH] | Request rule checks `Response[iResp].ReferenceId == offer.Soc && CompletionStatus==2` to skip re-sending. `OMX_AddFutureRes` XSLT does not map ReferenceId — only ResponseCode, ResponseMessage, CompletionStatus. So ReferenceId is always null, `reqSuccess` is never true, and all requests are re-sent on every resubmit. | Map `ReferenceId ← $eventResponse/RefID` in response XSLT, or redesign resubmit key strategy |
| COU scopes send all ParameterInfo per request | [MEDIUM] | Scopes C and D use `xsl:for-each select="$offer/ParameterInfo"` — each dispatched event carries ALL parameters. N events each containing all N params, vs Scopes A/B which send 1 param per event. Likely over-dispatching. | Align COU scopes to use single-param XSLT like POU scopes |
| COU Agreement scope emits no audit log | [MEDIUM] | After dispatching OMX_ADD_FUTURE for COU Agreement, `pid` is computed but logger event is never sent. COU Agreement requests invisible in audit trail. | Add logger event dispatch after Scope C request send |
| POU Agreement AUDIT_TRACE inconsistency | [MEDIUM] | Scope A AUDIT_TRACE = "Request Sent for OMX_ADD_FUTPP" — incorrect suffix. | Change to "Request Sent for OMX_ADD_FUT_OFFERS_PARAM" |
| EffectiveDate mutation on ParameterInfo | [MEDIUM] | `agreementParameterInfo.EffectiveDate = null` permanently mutates working-memory object. Subsequent rules will see null. | Use local variable for XSLT param instead of mutating original concept |
| POU Agreement userText format difference | [LOW] | Scope A uses `"%s;FUTPARAM request by %s on %s;"` while Scopes B–D use `"%s;request by %s on %s;"`. | Align format across all scopes |

---

## §18 — Full Source Code

```java
/**
 * @author warawich-nb
 */
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_FUT_OFFERS_PARAM {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "OMX_ADD_FUT_OFFERS_PARAM";
        orderRequest.ProcessFlow.NextActivityID == "OMX_ADD_FUT_OFFERS_PARAM";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
        try {
            // Resolve LogicalDate
            DateTime logicalDate;
            Concepts.OM.LogicalDate logicalDateRes = Instance.getByExtIdByUri("LogicalDate", "...");
            if(String.length(String.trim(logicalDateRes.LogicalDate))<=0){
                logicalDate = DateTime.now();
            } else {
                logicalDate = DateTime.parseString(logicalDateRes.LogicalDate, "yyyy-MM-dd'T'HH:mm:ssXXX");
            }
            boolean isSkipped = true;
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
            String chkXPath = nextAct.PreExecCheck;
            String custId = orderRequest.OrderData.Customer.CustomerId;
            String accountSubType = XPath.evalAsString("... Account[1]/AccountSubType ...");
            String requestBy = orderRequest.OrderData.Channel;
            String futureType = "FUTPARAM";
            String orderType = "5";

            // ── Scope A: POU Agreement ───────────────────────────────────────────────
            for(int iPOU=0; iPOU < orderRequest.OrderData.Customer.ParentOU@length; iPOU++){
                ParentOU pOu = ...ParentOU[iPOU];
                if(pOu.Agreement != null){
                    for(int iPouOffer=0; iPouOffer < pOu.Agreement.Offers@length; iPouOffer++){
                        AgreementOffers offer = pOu.Agreement.Offers[iPouOffer];
                        // PreExecCheck via GetXMLForAgreementOffer()
                        if(chkRes == "true"){
                            for(int iOfferParam=0; iOfferParam < offer.ParameterInfo@length; iOfferParam++){
                                // resubmit guard (BROKEN: ReferenceId never set in response)
                                AgreementParameterInfo agreementParameterInfo = offer.ParameterInfo[iOfferParam];
                                // null EffectiveDate if not FUT type (in-memory mutation)
                                Events...OMX_ADD_FUTURE reqEvent = Event.createEvent("xslt://{{...}}");
                                /* XSLT: builds ns3:futureOrderWithSoc with nodeLevel=3, single param
                                   (agreementParameterInfo). POU_ID, CUS_ID, PAGR_ID extendedInfo.
                                   See §9 for full field mapping. */
                                Event.Ext.sendEventImmediate(reqEvent);
                                isSkipped = false;
                                if(!isActResub) orderCurrentActivity.RequestCount++;
                                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                                // [BUG] AUDIT_TRACE = "Request Sent for OMX_ADD_FUTPP"
                                Event.Ext.sendEventImmediate(/* Logger */);
                            }
                        }
                    }
                }

                // ── Scope B: POU Subscriber ──────────────────────────────────────────
                for(int iPouSub=0; iPouSub < Subscriber@length; iPouSub++){
                    for(int iPouSubOffer=0; ...; iPouSubOffer++){
                        // PreExecCheck via GetXMLForSubscriberOfferFilterWithExtendedInfo()
                        for(int iOfferParam=0; ...; iOfferParam++){
                            // dispatch OMX_ADD_FUTURE: nodeLevel=5, single offerParameterInfo
                            // AUDIT_TRACE="Request Sent for OMX_ADD_FUT_OFFERS_PARAM"
                        }
                    }
                }

                // ── Scope C: COU Agreement ───────────────────────────────────────────
                for(int iCOU=0; iCOU < ChildOU@length; iCOU++){
                    for(int iCouOffer=0; ...; iCouOffer++){
                        // PreExecCheck via GetXMLForAgreementOfferInChildOU()
                        // dispatch: XSLT uses xsl:for-each ALL ParameterInfo [design inconsistency]
                        long pid = System.nanoTime();  // [BUG: logger never called]
                    }

                    // ── Scope D: COU Subscriber ─────────────────────────────────────
                    Subscriber[] cSubs = Instance.PropertyArray.toArrayConcept(...Subscriber);
                    for(int iCouSub=0; iCouSub < cSubs@length; iCouSub++){
                        for(int iCouSubOffer=0; ...; iCouSubOffer++){
                            // PreExecCheck via GetXMLForSubscriberOfferInChildOU()
                            // dispatch: XSLT uses xsl:for-each ALL ParameterInfo + OU_ID always
                            // AUDIT_TRACE="Request Sent for OMX_ADD_FUT_OFFERS_PARAM"
                        }
                    }
                }
            } // iPOU

            if(!isSkipped){
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                RuleFunctions.Helpers.SendDataToDB(orderRequest);
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch (Exception ae){
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_OMX_ADD_FUT_OFFERS_PARAM.rulefunction` receives the OMX FM response event, creates an `OMX_AddFutureRes` concept, appends it to the activity's Response array, logs the response, and evaluates the standard fan-in completion condition.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order for audit logging |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` | Inbound response from OMX FM |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response array appended; RequestCount compared |

### §19.3 — ResponseBase Concept Construction (OMX_AddFutureRes)

```text
createObject
└── object
    ├── @extId            ← OMXUtils:generateTrackingID()       [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode         [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg          [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus     [Conditional]
    └── ReferenceId       ← (NOT MAPPED — always null)          [HIGH BUG]
```

> **[HIGH]** `ReferenceId` is not mapped. The request rule's resubmit guard checks `Response[iResp].ReferenceId == offer.Soc` — since ReferenceId is always null, this guard never fires. All requests will be re-dispatched on every resubmit attempt.

### §19.4 — Response Completion Logic

| Metric | Expression |
|--------|-----------|
| Success count XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Return "true" | All dispatched requests returned ResponseCode ending in "000" |
| Return "false" | Still waiting for remaining responses |

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | "OMX_ADD_FUT_OFFERS_PARAM" |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | "Response received for OMX_ADD_FUT_OFFERS_PARAM" |
| payload | Conditional on `WritePayload = "true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
