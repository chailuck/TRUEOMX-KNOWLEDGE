# Request_AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT

## §1 — Overview & Purpose

This FM rule invokes the Amdocs AR **l9MultiCreateChargeLevelCredit** operation to create a charge-level credit for each SubscriberOffer where `BILL=Y`. In the *CREATE_BILL_ADJUSTMENT* flow (step 3), it is the **BILL=Y branch** — mutually exclusive with step 4 (`BL_CREATE_CHARGE` for BILL=N).

One AR credit request is sent per SubscriberOffer, keyed by composite `RefID = subscriberRefId + ":" + offerName`. Uses **IntraActivitySequencing** fan-in.

> **OMX-2755 refactor:** Original implementation sent one request per subscriber with all offers batched. Current implementation sends per-offer individually for independent response tracking. Old code preserved as comment block.

> **CES path:** A `CES_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT` routing branch was designed for `CES='Y'` but is fully commented out. Current live code always uses the standard AR event type and passes CES as a header field.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT` |
| Author | malinee-sririrom |
| Priority | 5 |
| ForwardChain | true |
| Rule type | Request FM — AR credit per SubscriberOffer (BILL=Y) |
| Fan-in pattern | IntraActivitySequencing: `ActionRequestEvent` + `SendFirstRequestEvent` |
| Backend system | AR — Amdocs Accounts Receivable |
| RefID key | Composite: `subscriberRefId + ":" + offerName` |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Full order data |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Activity state |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity matches flow pointer |
| 2 | `orderCurrentActivity.ActivityID == "AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT"` | Fires for this FM only |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT"` | Double-check order pointer |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Prevents double-firing |

---

## §5 — Execution Flow Diagram

1. Resubmit check → `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` if applicable
2. Loop ParentOU → Subscriber → SubscriberOffers
3. Build composite `refId = subsRefId + ":" + offerName` and extract `FE_OR_CCBS` filter
4. Check if already responded (`CompletionStatus==2` for refId) → skip if so
5. Evaluate PreExecCheck via `GetXMLForSubscriberOfferFilterWithExtendedInfo` (BILL=Y gate)
6. Build AR request event via XSLT → `Event.assertEvent` + `IntraActivitySequencing.ActionRequestEvent`
7. Audit log (REQUEST)
8. After all offers: `IntraActivitySequencing.SendFirstRequestEvent` + `Status = "1"` + `SendDataToDB`; or `SkipActivity(..., "4")`

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

CREATE_BILL_ADJUSTMENT step 3, BILL=Y path. PreExecCheck: `boolean(//SubscriberOffers[ExtendedInfo[Name='BILL' and Value='Y']])`. Mutually exclusive with BL_CREATE_CHARGE (BILL=N).

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Schema Namespace | Purpose |
|-----------|-----------|-----------------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT` | `http://ws.api.interfaces.sessions.ar.amdocs` | AR credit per offer |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT` | Same Amdocs namespace | Returns creditId, completeIndicator, errorMessage |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `http://schemas.true.com/AuditLogging/V1_0` | Audit trail |

### §8.3 — Backend API Details

| System | Operation | Protocol | Request Root | Response Root |
|--------|-----------|----------|-------------|--------------|
| AR (Amdocs) | l9MultiCreateChargeLevelCredit | JMS/SOAP via ESB | `ns1:l9MultiCreateChargeLevelCredit` | `ns1:l9MultiCreateChargeLevelCreditResponse` |

### §8.5 — ExtendedInfo Fields

| Key | Direction | Notes |
|-----|-----------|-------|
| `BILL` | Read (gate) | Value must be "Y" to route to AR credit |
| `FE_OR_CCBS` | Read | Filter param for GetXMLForSubscriberOfferFilterWithExtendedInfo |
| `AMOUNT` | Read | Credit amount → `ns:amount` |
| `TAX_INCLUDE` | Read | Tax flag → `OMXUtils:textToAscii()` → `ns:taxInclude` |
| `CRM_COMPLETE_IND` | Write (response) | AR l9CompleteIndicator |
| `CRM_CREDIT_ID` | Write (response) | AR creditId |
| `CRM_CREDIT_NOTE_NUMBER` | Write (response) | AR l9CreditNoteNumber |
| `CRM_ERROR_MESSAGE` | Write (response) | AR l9ErrorMessage |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| Parameter | Bound From |
|-----------|-----------|
| `$orderRequest` | Full OrderRequest concept |
| `$refId` | `subscriberRefId + ":" + subOff.OfferName` |
| `$subOff` | Current SubscriberOffers concept |
| `$sub` | Current Subscriber concept |

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `@extId` | `OMXUtils:generateTrackingID()` | Always |
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$refId` (composite: SubRefId:OfferName) | Always |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Always |
| `CES` | `$orderRequest/OrderData/CES` | [Conditional: if CES present] |

### §9.6 — Core Payload Fields

| XML Element | Source | Notes |
|-------------|--------|-------|
| `ns:accountId` | `$orderRequest/OrderData/Customer/Account[1]/AccountID` | [Conditional: if AccountID present] |
| `ns:chargeId` | `$subOff/OfferName` | [Conditional: if OfferName present] |
| `ns:creditTypeOption` | `"auto"` (literal) | Always hardcoded |
| `ns:l9UserId` | `$orderRequest/OrderData/User` | [Conditional: if User present] |
| `ns:creditReason` | `$sub/SubscriberActivityInfo/ActivityReason` | [Conditional] |
| `ns:amount` | `$subOff/ExtendedInfo[Name="AMOUNT"]/Value` | Always |
| `ns:taxInclude` | `OMXUtils:textToAscii(ExtendedInfo[TAX_INCLUDE]/Value)` | Always |
| `ns:memoText` | `$sub/SubscriberActivityInfo/UserText` | [Conditional] |

### §9.8 — XSLT Stylesheet Source

```xml
<!-- Active request XSLT (post OMX-2755) -->
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:ns1="http://ws.api.interfaces.sessions.ar.amdocs"
  xmlns:ns="http://datatypes.datalayer.ar.amdocs"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="refId"/>     <!-- composite: subscriberRefId:offerName -->
  <xsl:param name="subOff"/>    <!-- current SubscriberOffers -->
  <xsl:param name="sub"/>       <!-- current Subscriber -->
  <xsl:template match="/">
    <createEvent><event>
      <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
      <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      <RefID><xsl:value-of select="$refId"/></RefID>
      <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      <xsl:if test="$orderRequest/OrderData/CES">
        <CES><xsl:value-of select="$orderRequest/OrderData/CES"/></CES>
      </xsl:if>
      <payload>
        <ns1:l9MultiCreateChargeLevelCredit>
          <ns1:l9MultiCreateChargeLevelCreditScreenDt>
            <ns:accountIdInfo>
              <xsl:if test="$orderRequest/OrderData/Customer/Account[1]/AccountID">
                <ns:accountId><xsl:value-of select="$orderRequest/OrderData/Customer/Account[1]/AccountID"/></ns:accountId>
              </xsl:if>
            </ns:accountIdInfo>
            <ns:chargeIdInfo>
              <xsl:if test="$subOff/OfferName">
                <ns:chargeId><xsl:value-of select="$subOff/OfferName"/></ns:chargeId>
              </xsl:if>
            </ns:chargeIdInfo>
            <ns:chargeLevelCreditDetailsScreen>
              <ns:creditTypeOption>auto</ns:creditTypeOption>
              <ns:customerCreditCustDt>
                <xsl:if test="$orderRequest/OrderData/User">
                  <ns:l9UserId><xsl:value-of select="$orderRequest/OrderData/User"/></ns:l9UserId>
                </xsl:if>
              </ns:customerCreditCustDt>
              <xsl:if test="$sub/SubscriberActivityInfo/ActivityReason">
                <ns:creditReason><xsl:value-of select="$sub/SubscriberActivityInfo/ActivityReason"/></ns:creditReason>
              </xsl:if>
              <ns:amount><xsl:value-of select='$subOff/ExtendedInfo[Name="AMOUNT"]/Value'/></ns:amount>
              <ns:taxInclude><xsl:value-of select='OMXUtils:textToAscii($subOff/ExtendedInfo[Name="TAX_INCLUDE"]/Value)'/></ns:taxInclude>
              <xsl:if test="$sub/SubscriberActivityInfo/UserText">
                <ns:memoText><xsl:value-of select="$sub/SubscriberActivityInfo/UserText"/></ns:memoText>
              </xsl:if>
            </ns:chargeLevelCreditDetailsScreen>
          </ns1:l9MultiCreateChargeLevelCreditScreenDt>
        </ns1:l9MultiCreateChargeLevelCredit>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree

```text
createEvent
└── event
    ├── @extId              ← OMXUtils:generateTrackingID()                     [Always]
    ├── JMSPriority         ← $orderRequest/OrderPriority                       [Always]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId             [Always]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                   [Always]
    ├── RefID               ← subscriberRefId + ":" + offerName                 [Always]
    ├── OrderType           ← $orderRequest/OrderData/OrderType                 [Always]
    ├── CES                 ← $orderRequest/OrderData/CES                       [Conditional: if CES present]
    └── payload
        └── ns1:l9MultiCreateChargeLevelCredit
            └── ns1:l9MultiCreateChargeLevelCreditScreenDt
                ├── ns:accountIdInfo
                │   └── ns:accountId  ← Customer/Account[1]/AccountID          [Conditional]
                ├── ns:chargeIdInfo
                │   └── ns:chargeId   ← $subOff/OfferName                      [Conditional]
                └── ns:chargeLevelCreditDetailsScreen
                    ├── ns:creditTypeOption  ← "auto" (literal)                 [Always]
                    ├── ns:customerCreditCustDt
                    │   └── ns:l9UserId  ← $orderRequest/OrderData/User         [Conditional]
                    ├── ns:creditReason  ← SubscriberActivityInfo/ActivityReason [Conditional]
                    ├── ns:amount        ← ExtendedInfo[AMOUNT]/Value           [Always]
                    ├── ns:taxInclude    ← textToAscii(ExtendedInfo[TAX_INCLUDE]) [Always]
                    └── ns:memoText      ← SubscriberActivityInfo/UserText      [Conditional]
```

---

## §11 — Audit Logging

| Direction | AUDIT_TRACE | PROCESS_ID | Condition |
|-----------|------------|-----------|-----------|
| REQUEST | `concat("Request Sent for ", ActivityID)` | `_REQ` | After each offer send |
| RESPONSE | "Response received for AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT" | `_RES` | Only if `!chkError` |

> **Warning:** Response audit log is suppressed when `chkError = true` (l9ErrorMessage != "").

---

## §12 — Activity Status Management

| Status Code | String | Condition |
|-------------|--------|-----------|
| "1" | SENT | At least one offer request sent |
| "4" | SKIP | No BILL=Y offers or all already responded |

---

## §13 — Exception / Error Handling

Wrapped in `try { ... } catch (Exception ae)` → `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

Response-level: `chkError = (l9ErrorMessage != "")` — does not throw, but original code had explicit `"AR_L9_ERROR"` return path (commented out).

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit` | Clean stale tracking on resubmit |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(req, subsId, offerName, filter)` | Serialize offer context for PreExecCheck evaluation |
| `IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)` | Register event in fan-in tracking |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Fire first queued request (fan-in init) |
| `IntraActivitySequencing.ActionResponseEvent(currActivity)` | Fan-in completion check in response handler |
| `GetActivityStatusString("1", false)` | Returns "SENT" status string |
| `SkipActivity(orderRequest, activity, "4")` | Marks SKIP, advances flow |
| `HandleActivityException(orderRequest, activity, ae, "")` | Handles caught exceptions |
| `SendDataToDB(orderRequest)` | Persists order state |
| `OMXUtils:textToAscii(value)` | ASCII-encodes TAX_INCLUDE value |

---

## §15 — Function Dependency Tree

```text
Request_AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT
├── [optional] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit
├── GetXMLForSubscriberOfferFilterWithExtendedInfo (per offer, PreExecCheck eval)
├── Event.createEvent (XSLT → AR request event)
├── Event.assertEvent + IntraActivitySequencing.ActionRequestEvent
├── IntraActivitySequencing.SendFirstRequestEvent (fires first request)
├── GetActivityStatusString("1", false)
├── SendDataToDB
├── SkipActivity (if no requests)
└── HandleActivityException (catch block)

Response_AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT
├── OMXUtils.generateTrackingID
├── Instance.createInstance (AR_CreateImmedieteChargePaymentRes)
├── String.split(eventResponse.RefID, ":")[0]  → strip offerName
├── Instance.getByExtIdByUri (SUB: subscriber lookup)
├── For each SubscriberOffer (chargeId match):
│   ├── CRM_COMPLETE_IND: getByExtId / createInstance
│   ├── CRM_CREDIT_ID: getByExtId / createInstance
│   ├── CRM_CREDIT_NOTE_NUMBER: getByExtId / createInstance
│   └── CRM_ERROR_MESSAGE: getByExtId / createInstance
├── [conditional] Event.createEvent (Logger — only if !chkError)
└── IntraActivitySequencing.ActionResponseEvent → "true"/"false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Send AR l9MultiCreateChargeLevelCredit per SubscriberOffer (BILL=Y) with composite refId |
| R2 | `creditTypeOption` hardcoded "auto" — verify if configurable needed |
| R3 | Response must write CRM_COMPLETE_IND, CRM_CREDIT_ID, CRM_CREDIT_NOTE_NUMBER, CRM_ERROR_MESSAGE per offer |
| R4 | Fan-in via IntraActivitySequencing — all offer requests must complete |
| R5 | Account[1] selection — first account only; clarify for multi-account orders |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Commented-out CES_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT path — dead code for abandoned CES routing | [HIGH] | Confirm CES routing requirement with AR team; remove dead code |
| Response audit log suppressed on chkError=true — failed credits leave no audit trail | [HIGH] | Always emit audit log; use ERROR level for failures |
| l9ErrorMessage != "" check may miss null/whitespace | [MEDIUM] | Normalize to null/blank/empty check |
| Pre-OMX-2755 commented code still in source — risk of accidental revival | [MEDIUM] | Remove in modernized code; document OMX-2755 in commit |
| Typo `AR_CreateImmedieteChargePaymentRes` ("Immediete") | [LOW] | Rename in modernized system |
| Account[1] hardcoded — silent miss on multi-account orders | [MEDIUM] | Validate assumption with AR team |

---

## §18 — Full Source Code

```java
/** @author malinee-sririrom */
rule Rules.OMConsumers.OMXFM.Request.Request_AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT";
    orderRequest.ProcessFlow.NextActivityID == "AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
    try {
      if(isActResub) IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      boolean isSkipped = true;
      // Loop ParentOU → Subscriber → SubscriberOffers
      for(int i=0; i < iPOULen; i++) {
        for(int p=0; p < pSubscriberLen; p++) {
          for(int q=0; q < qSubOffLen; q++) {
            // refId = subsId + ":" + subOff.OfferName
            // filter = XPath on subOff/ExtendedInfo[FE_OR_CCBS]/Value
            // skip if already responded (CompletionStatus==2)
            if(!reqSuccess) {
              // evaluate PreExecCheck via GetXMLForSubscriberOfferFilterWithExtendedInfo
              if(chkRes == "true") {
                /* CES path commented out — see §1 notes */
                Events.OMConsumers.OMXFM.Request.AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT reqEvent =
                  Event.createEvent("xslt://{{...}}");
                  /* XSLT: accountId ← Account[1], chargeId ← OfferName,
                     creditTypeOption="auto", amount ← AMOUNT, taxInclude ← textToAscii(TAX_INCLUDE)
                     — see §9.8 for full XSLT */
                Event.assertEvent(reqEvent);
                IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                // audit log
                isSkipped = false;
              }
            }
          }
        }
      }
      /* start before OMX-2755 commented-out per-subscriber batch code */
      if(!isSkipped) {
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else {
        SkipActivity(orderRequest, orderCurrentActivity, "4");
      }
    } catch(Exception ae) {
      HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 — Overview

Receives AR credit response per offer. Extracts creditId, completeIndicator, creditNoteNumber, errorMessage and writes them to SubscriberOffer ExtendedInfo. IntraActivitySequencing fan-in.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Full order context |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.AR_L9_MULTI_CREATE_CHARGE_LEVEL_CREDIT | Inbound AR response |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Fan-in tracking |

### §19.3 — Response Concept Construction

Response concept: `Concepts.FM.Response.AR_CreateImmedieteChargePaymentRes` (note spelling).

```text
createObject
└── object (AR_CreateImmedieteChargePaymentRes)
    ├── @extId              ← $extId (OMXUtils:generateTrackingID())  [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode              [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg               [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus          [Conditional]
    └── ReferenceId         ← $eventResponse/RefID                     [Conditional]
```

### §19.4 — Per-Offer ExtendedInfo Writes

RefId decomposition: `String.split(eventResponse.RefID, ":")[0]` → strips offerName suffix.

For each SubscriberOffer where `chargeId == offerName`:

| ExtendedInfo Key | Source XPath | Default |
|-----------------|-------------|---------|
| `CRM_COMPLETE_IND` | `l9RequestResponseInfoDt/item[chargeId=offerName]/l9CompleteIndicator` | 0 |
| `CRM_CREDIT_ID` | `l9RequestResponseInfoDt/item[chargeId=offerName]/creditId` | 0 |
| `CRM_CREDIT_NOTE_NUMBER` | `l9RequestResponseInfoDt/item[chargeId=offerName]/l9CreditNoteNumber` | — |
| `CRM_ERROR_MESSAGE` | `l9RequestResponseInfoDt/item[chargeId=offerName]/l9ErrorMessage` | — |

### §19.5 — Fan-in Completion

```java
// Current implementation:
if(IntraActivitySequencing.ActionResponseEvent(currActivity))
    return "true";
else
    return "false";

// Commented-out original:
// if(RequestCount == successResponseCount && !chkError) → "true"
// else if(chkError) → "AR_L9_ERROR"
// else → "false"
```

> **Migration note:** Original "AR_L9_ERROR" return path is dead code. Verify whether chkError should reinstate a distinct error path in the modernized system.

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
