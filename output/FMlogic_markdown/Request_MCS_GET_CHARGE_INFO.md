# Request_MCS_GET_CHARGE_INFO

> Per-offer charge information retrieval from MCS — fan-out per SubscriberOffer with 3-part compound RefID (`subRefId:Soc:FE_OR_CCBS`), idempotent ExtendedInfo enrichment, ExpirationDate write.

**Target:** MCS (Subscription Management) | **Pattern:** Per-offer fan-out | **forwardChain:** true | **Author:** DESKTOP-995HR2V

---

## §1 Overview & Purpose

This FM retrieves charge information (price, VAT amount, charge flag, expiration date) from MCS for each SubscriberOffer across POU and COU subscribers. One event is fired **per offer per subscriber** using a 3-part compound correlation key (`subRefId:Soc:FE_OR_CCBS`) that enables per-offer deduplication on resubmit. The response enriches the matching offer with `AMOUNT`, `IS_CHARGE`, and `AMOUNT_IN_VAT` ExtendedInfo entries and optionally sets `offer.ExpirationDate`.

> **Key differentiator:** The compound RefID enables offer-level resubmit dedup — before firing, the rule checks existing responses for a matching RefID with CompletionStatus == 2. This is distinct from standard RequestCount-based resubmit guards.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_MCS_GET_CHARGE_INFO.rule` | 150 lines |
| Response file | `Response_MCS_GET_CHARGE_INFO.rulefunction` | 133 lines |
| Author | DESKTOP-995HR2V | |
| forwardChain | `true` | |
| Request event | `Events.OMConsumers.OMXFM.Request.MCS_GET_CHARGE_INFO` | |
| Response event | `Events.OMConsumers.OMXFM.Response.MCS_GET_CHARGE_INFO` | |
| Request schema NS | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/GetChargeInfoRequest.xsd` (ns9) | |
| Response schema NS | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/GetChargeInfoResponse.xsd` (ns / xsd2) | Two prefixes for same schema |
| Response concept | `Concepts.FM.Base.ResponseBase` | Standard |
| Correlation key | `subRefId + ":" + offer.Soc + ":" + FE_OR_CCBS` | 3-part compound key |
| Fan-out level | Per SubscriberOffer (POU + COU subscribers) | No Agreement offer processing |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Offer iteration source; written with charge enrichment |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Response[] checked for per-offer dedup |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "MCS_GET_CHARGE_INFO"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "MCS_GET_CHARGE_INFO"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 Execution Flow Diagram

```
1. isActResub = (RequestCount > 0 && IsOrderResubmitted)
2. nextAct = Instance.getByExtIdByUri(NextActivityName, ...)
3. chkXPath = nextAct.PreExecCheck
4. isSkipped = true  (default; set false when first event fires)
5. Loop POU Subscriber × SubscriberOffers:
   ├── filter = XPath.evalAsString("$offer/ExtendedInfo[Name='FE_OR_CCBS']/Value")
   ├── offerRefId = pSubRefId + ":" + offer.Soc + ":" + filter
   ├── reqSuccess dedup: loop Response[] → if ReferenceId==offerRefId AND CompletionStatus==2 → skip
   ├── if !reqSuccess AND PreExecCheck passes (GetXMLForSubscriberOfferFilterWithExtendedInfo):
   │   ├── fire Event.Ext.sendEventImmediate(reqEvent)
   │   ├── isSkipped = false
   │   ├── if !isActResub → RequestCount++
   │   └── fire audit log (sendEventImmediate)
6. Loop COU Subscriber × SubscriberOffers (same pattern, GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo)
7. if !isSkipped → GetActivityStatusString("1", false) + SendDataToDB
   else → SkipActivity("4")
[catch] → HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
```

---

## §6 Rule Action (THEN)

### §6.1 — 3-Part Compound Correlation Key

```
offerRefId = pSubRefId + ":" + offer.Soc + ":" + filter
```
where `filter = offer/ExtendedInfo[Name="FE_OR_CCBS"]/Value` (e.g., "FE", "CCBS", "CRM")

This allows the response handler to locate the exact offer, including distinguishing FE vs CCBS variants of the same SOC.

### §6.2 — Per-Offer Resubmit Dedup Check

```java
boolean reqSuccess = false;
for(int iResp = 0; iResp < orderCurrentActivity.Response@length; iResp++) {
    if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, offerRefId)
        && orderCurrentActivity.Response[iResp].CompletionStatus == 2) {
        reqSuccess = true;
    }
}
if (!reqSuccess) {
    // proceed with PreExecCheck + fire event
}
```

### §6.3 — PreExecCheck Helper Variants

| Context | Helper Function |
|---------|----------------|
| POU Subscriber offer | `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, offer.Soc, filter)` |
| COU Subscriber offer | `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, cSubRefId, offer.Soc, pOuRefId, filter)` |

> These are **FilterWithExtendedInfo** variants — extended forms that include FE_OR_CCBS in the serialized XML context.

### §6.4 — isSkipped Logic

`isSkipped` starts `true`. Set to `false` when first event fires. If no events fired (all offers failed PreExecCheck or were already deduped), `SkipActivity("4")` is called.

---

## §7 Data Extraction

```java
// FE_OR_CCBS extracted per-offer via inline XPath:
String filter = XPath.evalAsString("xpath://<expr>$offer/ExtendedInfo[Name='FE_OR_CCBS']/Value</expr>...");
```

---

## §8 System & Integration Dependencies

### §8.1 — Order Type Dependencies

No order-type branching. Fires for all orders with SubscriberOffers containing a PROGRAM_CODE ExtendedInfo entry.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Purpose |
|-----------|---------|-------------|---------|
| [OUTBOUND] | OMX FM JMS | MCS_GET_CHARGE_INFO queue | Per-offer charge info request |
| [INBOUND] | OMX FM JMS | MCS_GET_CHARGE_INFO response queue | Charge price, IS_CHARGE flag, VAT amount, expire date |
| [LOG] | OMXESB Logger | Audit event (immediate) | Per-offer request and response audit trail |

### §8.3 — Backend API Details

| Field | Value |
|-------|-------|
| System | MCS (Subscription Management / Charge Information) |
| Request root element | `ns9:getChargeInfoReq` |
| Response root element | `ns:getChargeInfoRes` / `xsd2:getChargeInfoRes` |
| Correlation | 3-part RefID: `subRefId:Soc:FE_OR_CCBS` |
| Send pattern | Fan-out — one event per SubscriberOffer (POU + COU) |

### §8.4 — BE Working Memory Dependencies

| Concept | Field | Access | Notes |
|---------|-------|--------|-------|
| OrderRequest | `ParentOU[].Subscriber[].SubscriberOffers[]` | READ | Offer iteration source |
| OrderRequest | `ParentOU[].ChildOU[].Subscriber[].SubscriberOffers[]` | READ | COU offer iteration |
| SubscriberOffers | `ExtendedInfo[Name="FE_OR_CCBS"].Value` | READ | Correlation key 3rd segment |
| SubscriberOffers | `ExtendedInfo[Name="PROGRAM_CODE"].Value` | READ | Sent as ns9:pack_code |
| SubscriberOffers | `ExtendedInfo[Name="AMOUNT"].Value` | WRITTEN | From ns:charge_price (idempotent) |
| SubscriberOffers | `ExtendedInfo[Name="IS_CHARGE"].Value` | WRITTEN | Y/N from ns:isCharge (idempotent) |
| SubscriberOffers | `ExtendedInfo[Name="AMOUNT_IN_VAT"].Value` | WRITTEN | From ns:charge_price_vat_roundup (idempotent) |
| SubscriberOffers | `ExpirationDate` | WRITTEN | From xsd2:date_info/xsd2:expire_date (conditional) |
| Activity | `Response[].ReferenceId + CompletionStatus` | READ | Per-offer dedup check |
| Activity | `RequestCount / Response[]` | READ+WRITTEN | Fan-out count + fan-in |

### §8.5 — ExtendedInfo Fields Required (Request-side)

| Name | Usage | Required? |
|------|-------|-----------|
| `FE_OR_CCBS` | 3rd segment of RefID; used in response matching | Required for correlation |
| `PROGRAM_CODE` | Sent as `ns9:pack_code` in request payload | Optional |

### §8.6 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Credential gate |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `OMX_OM/WritePayload` | Payload inclusion gate |

> **Credential source difference:** This FM reads UserName/Password from `$orderRequest/OrderData/User` and `$orderRequest/OrderData/Password` — NOT from global variables (unlike other FMs).

---

## §9 Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| Parameter | Bound From |
|-----------|-----------|
| `$orderRequest` | Full OrderRequest concept |
| `$offerRefId` | Computed 3-part key: `subRefId:Soc:FE_OR_CCBS` |
| `$globalVariables` | BE global variables tree |
| `$offer` | Current SubscriberOffers concept |

### §9.2 — JMS / Event Header Fields

| Header | Source | Condition |
|--------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | Conditional [unique: JMS priority from order] |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| OrderID | `$orderRequest/OrderData/OrderID` | Conditional |
| RefID | `$offerRefId` (3-part compound key) | Always |
| UserName | `$orderRequest/OrderData/User` | Credential-gated: IsEnableUserPass + User exists |
| PassWord | `$orderRequest/OrderData/Password` | Credential-gated: IsEnableUserPass + Password exists |
| OrderType | `$orderRequest/OrderData/OrderType` | Conditional |

### §9.3 — Payload Fields

| XML Element | Source | Condition |
|-------------|--------|-----------|
| `ns9:transaction_id` | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| `ns9:pack_code` | `$offer/ExtendedInfo[Name="PROGRAM_CODE"]/Value` | Conditional |

### §9.4 — Complete Generated XML Example

```xml
<!-- JMS Headers -->
<JMSPriority>5</JMSPriority>
<JMSCorrelationID>OMX-TRK-20250804-001</JMSCorrelationID>
<OrderID>ORD-12345</OrderID>
<RefID>SUB-REF-001:SOC_PKG_A:FE</RefID>
<OrderType>3</OrderType>

<!-- Payload -->
<ns9:getChargeInfoReq xmlns:ns9="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/GetChargeInfoRequest.xsd">
  <ns9:transaction_id>OMX-TRK-20250804-001</ns9:transaction_id>
  <ns9:pack_code>PROG-001</ns9:pack_code>
</ns9:getChargeInfoReq>
```

### §9.5 — XSLT Output Tree

```text
createEvent
└── event
    ├── JMSPriority         ← $orderRequest/OrderPriority                          [Conditional]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId                [Conditional]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                      [Conditional]
    ├── RefID               ← $offerRefId (subRefId:Soc:FE_OR_CCBS)               [Always]
    ├── UserName            ← $orderRequest/OrderData/User                         [Credential-gated]
    ├── PassWord            ← $orderRequest/OrderData/Password                     [Credential-gated]
    ├── OrderType           ← $orderRequest/OrderData/OrderType                    [Conditional]
    └── payload
        └── ns9:getChargeInfoReq
            ├── ns9:transaction_id ← $orderRequest/OrderData/OMXTrackingId        [Conditional]
            └── ns9:pack_code      ← $offer/ExtendedInfo[Name="PROGRAM_CODE"]/Value [Conditional]
```

---

## §11 Audit Logging

### Request Audit

| Field | Value |
|-------|-------|
| AUDIT_TRACE | `"Request Sent for MCS_GET_CHARGE_INFO"` (static) |
| OPERATION_NAME | `"MCS_GET_CHARGE_INFO"` |
| Send method | `Event.Ext.sendEventImmediate()` — immediate |

### Response Audit

| Field | Value |
|-------|-------|
| AUDIT_TRACE | `"Response received for MCS_MCS_GET_CHARGE_INFO"` ⚠️ **TYPO: double MCS_ prefix** |
| OPERATION_NAME | `"MCS_GET_CHARGE_INFO"` |
| Send method | `Event.Ext.sendEventImmediate()` |

> **Bug:** Response AUDIT_TRACE has double "MCS_" prefix — log searches must account for this.

---

## §12 Activity Status Management

| Condition | Call | Status Code |
|-----------|------|-------------|
| At least one event sent | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" (RUNNING) |
| No events sent (isSkipped) | `SkipActivity("4")` | "4" (SKIPPED) |

---

## §13 Exception / Error Handling

```java
try {
    // ... entire rule body ...
} catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, soc, filter)` | POU offer PreExecCheck serialization with FE_OR_CCBS |
| `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, cSubRefId, soc, pOuRefId, filter)` | COU offer PreExecCheck serialization with FE_OR_CCBS |
| `GetActivityStatusString(code, flag)` | Activity status string builder |
| `SendDataToDB(orderRequest)` | Persist order state to DB |
| `SkipActivity(orderRequest, activity, code)` | Mark activity as skipped |
| `HandleActivityException(orderRequest, activity, ae, msg)` | Standard exception handler |
| `XPath.evalAsString(xpath)` | Extract FE_OR_CCBS / expire_date values |
| `XPath.evalAsBoolean(xpath)` | Idempotent ExtendedInfo existence checks |
| `DateTime.parseString(str, format)` | Parse MCS expire_date to DateTime |

---

## §15 Function Dependency Tree

```text
Request_MCS_GET_CHARGE_INFO (rule)
├── Instance.getByExtIdByUri(NextActivityName, conceptPath)
├── XPath.evalAsString(...)  [FE_OR_CCBS per offer]
├── String.equals(Response[i].ReferenceId, offerRefId)  [resubmit dedup]
├── GetXMLForSubscriberOfferFilterWithExtendedInfo(...)  [POU PreExecCheck]
├── GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...)  [COU PreExecCheck]
├── XPath.execute(chkXPath, sXML, ns)  [evaluate PreExecCheck]
├── Event.Ext.sendEventImmediate(reqEvent)  [per-offer request]
├── Event.Ext.sendEventImmediate(auditEvent)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")
└── RuleFunctions.Helpers.HandleActivityException(...)  [catch]

Response_MCS_GET_CHARGE_INFO (rulefunction)
├── Instance.createInstance("xslt://{{ResponseBase}}")
├── String.split(eventResponse.RefID, ":")  [parse 3-part key]
├── XPath.evalAsString(FE_OR_CCBS per offer)
├── String.equals(subscriber.RefId, subRefId)
├── String.equals(offer.Soc, soc)
├── String.equals(feOrCcbs, source)
├── XPath.evalAsBoolean("exists(AMOUNT)")  [idempotent check]
├── Instance.createInstance("xslt://{{SubscriberOffersExtendedInfo}}")  [AMOUNT]
├── XPath.evalAsBoolean("exists(IS_CHARGE)")
├── Instance.createInstance("xslt://{{SubscriberOffersExtendedInfo}}")  [IS_CHARGE: xsl:choose]
├── XPath.evalAsBoolean("exists(AMOUNT_IN_VAT)")
├── Instance.createInstance("xslt://{{SubscriberOffersExtendedInfo}}")  [AMOUNT_IN_VAT]
├── XPath.evalAsBoolean("exists(xsd2:expire_date)")
├── XPath.evalAsString(xsd2:expire_date)
├── DateTime.parseString(mcs_expire_date, "yyyy-MM-dd HH:mm:ss")
├── Event.Ext.sendEventImmediate(auditLogEvent)
└── XPath.evalAsInt("count(Response[tib:right(tib:trim(ResponseCode),3)='000'])")
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields | Role |
|---------|-----------|------|
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId | Standard response holder |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Soc, ExtendedInfo[], ExpirationDate | Source and enrichment target |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberOffersExtendedInfo` | Name, Value | AMOUNT / IS_CHARGE / AMOUNT_IN_VAT |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Fire one MCS request per SubscriberOffer across POU and COU subscribers. |
| R2 | Correlation key must be 3-part: `subRefId + ":" + offer.Soc + ":" + FE_OR_CCBS`. |
| R3 | Before firing per offer: check existing responses for matching RefID + CompletionStatus==2. |
| R4 | PreExecCheck uses FilterWithExtendedInfo helper variants (include FE_OR_CCBS in XML context). |
| R5 | Send `ns9:pack_code` from `offer/ExtendedInfo[Name="PROGRAM_CODE"]/Value`. |
| R6 | Credential gate reads from `OrderData.User` / `OrderData.Password` — NOT global variables. |
| R7 | Set JMSPriority from `$orderRequest/OrderPriority`. |
| R8 | Response: parse RefID as 3-part split; match subscriber by RefId, offer by Soc, validate filter. |
| R9 | Idempotent ExtendedInfo — only create AMOUNT/IS_CHARGE/AMOUNT_IN_VAT if not already exists. |
| R10 | IS_CHARGE: "Y" if `ns:isCharge="true"` else "N". |
| R11 | ExpirationDate: set from `xsd2:date_info/xsd2:expire_date` format `"yyyy-MM-dd HH:mm:ss"`. |
| R12 | Fan-in: `RequestCount == count(Response[tib:right(tib:trim(ResponseCode), 3) = "000"])`. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| AUDIT_TRACE typo: `"Response received for MCS_MCS_GET_CHARGE_INFO"` | [MEDIUM] | Fix in migration; update log search queries |
| Two NS prefixes (`ns:` and `xsd2:`) for same response schema | [LOW] | Standardize to one prefix; verify both paths work |
| Credential source reads from OrderData (not global) — inconsistent with other FMs | [MEDIUM] | Standardize credential source in migration |
| Per-offer dedup O(Responses × Offers) linear scan | [MEDIUM] | Modern impl: use Set/Map for O(1) lookup |
| Silent skip if all offers fail PreExecCheck — no warning logged | [LOW] | Add debug logging when SkipActivity fires |

---

## §18 Full Source Code

### Request_MCS_GET_CHARGE_INFO.rule

```java
/**
 * Request_MCS_GET_CHARGE_INFO — Author: DESKTOP-995HR2V
 * Per-offer MCS charge info retrieval
 */
rule Rules.OMConsumers.OMXFM.Request.Request_MCS_GET_CHARGE_INFO {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "MCS_GET_CHARGE_INFO";
    orderRequest.ProcessFlow.NextActivityID == "MCS_GET_CHARGE_INFO";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Activity nextAct = Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, ...);
      String chkXPath = nextAct.PreExecCheck;
      boolean isSkipped = true;

      // POU Subscriber × SubscriberOffers loop
      for (int p...; ps...; psof...) {
        String filter = XPath.evalAsString("$offer/ExtendedInfo[Name='FE_OR_CCBS']/Value");
        String offerRefId = pSubRefId + ":" + offer.Soc + ":" + filter;

        // Per-offer resubmit dedup
        boolean reqSuccess = false;
        for (int iResp...) {
          if (String.equals(Response[iResp].ReferenceId, offerRefId) && Response[iResp].CompletionStatus == 2)
            reqSuccess = true;
        }
        if (!reqSuccess) {
          String chkRes = "true";
          if (String.length(nextAct.PreExecCheck) > 0) {
            String sXML = GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, offer.Soc, filter);
            chkRes = XPath.execute("/(" + chkXPath + ")", sXML, ns);
          }
          if (String.equals(chkRes, "true")) {
            // [XSLT: ns9:getChargeInfoReq with transaction_id + pack_code from PROGRAM_CODE — see §9.5]
            Event reqEvent = Event.createEvent("xslt://{{MCS_GET_CHARGE_INFO}}...");
            Event.Ext.sendEventImmediate(reqEvent);
            isSkipped = false;
            if (!isActResub) orderCurrentActivity.RequestCount++;
            Event.Ext.sendEventImmediate(auditEvent);
          }
        }
      }

      // COU Subscriber × SubscriberOffers loop (same pattern, GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo)

      if (!isSkipped) {
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else {
        SkipActivity(orderRequest, orderCurrentActivity, "4");
      }
    } catch (Exception ae) {
      HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 Response Message Rule

### §19.1 — Overview

Parses the 3-part RefID to locate target subscriber/offer. Idempotently appends `AMOUNT`, `IS_CHARGE`, `AMOUNT_IN_VAT` ExtendedInfo entries and sets `offer.ExpirationDate`. Triple before-write checks prevent duplicate entries on retry.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | WRITTEN — offer ExtendedInfo + ExpirationDate |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.MCS_GET_CHARGE_INFO | Backend response event |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Response[] appended; fan-in checked |

### §19.3 — ResponseBase Construction

```text
createObject
└── object @extId ← OMXUtils:generateTrackingID()                    [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode               [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg                [Conditional] (source=ResponseMsg)
    ├── CompletionStatus  ← $eventResponse/CompletionStatus           [Conditional]
    └── ReferenceId       ← $eventResponse/RefID                      [Conditional] (3-part key echoed)
```

### §19.4 — RefID Parsing & Offer Matching

```java
String[] refIDs = String.split(eventResponse.RefID, ":");
String subRefId = refIDs[0]; // subscriber RefId
String soc      = refIDs[1]; // offer.Soc
String source   = refIDs[2]; // FE_OR_CCBS filter value

// Match: subscriber.RefId == subRefId → offer.Soc == soc → feOrCcbs == source
```

### §19.5 — ExtendedInfo Enrichment (Idempotent)

| ExtendedInfo Name | Value Source | Logic |
|-------------------|-------------|-------|
| `AMOUNT` | `ns:getChargeInfoRes/ns:charge_price` | Create only if not exists; conditional on charge_price present |
| `IS_CHARGE` | `ns:getChargeInfoRes/ns:isCharge` | Create only if not exists; xsl:choose: "Y" if isCharge="true" else "N" |
| `AMOUNT_IN_VAT` | `ns:getChargeInfoRes/ns:charge_price_vat_roundup` | Create only if not exists; conditional on value present |

### §19.6 — ExpirationDate

```java
// expire_date uses xsd2: prefix (same schema as ns: above)
if (XPath.evalAsBoolean("exists($eventResponse/payload/xsd2:getChargeInfoRes/xsd2:date_info/xsd2:expire_date)")) {
    String mcs_expire_date = XPath.evalAsString("$eventResponse/payload/xsd2:getChargeInfoRes/xsd2:date_info/xsd2:expire_date");
    offer.ExpirationDate = DateTime.parseString(mcs_expire_date, "yyyy-MM-dd HH:mm:ss");
}
```

> Note: `ns:` used for charge_price/isCharge, `xsd2:` used for date_info/expire_date — both refer to `GetChargeInfoResponse.xsd`.

### §19.7 — Fan-in Completion Logic

```java
int successResponseCount = XPath.evalAsInt(
    "count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = '000'])");
if(currActivity.RequestCount == successResponseCount) {
    return "true";
} else {
    return "false";
}
```

Standard "000" success count fan-in — returns "true" only when all per-offer requests received a "000" response.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
