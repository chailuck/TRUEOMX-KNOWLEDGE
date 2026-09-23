# Request_OMX_BRMS_DB

> TIBCO BusinessEvents FM Logic — OMX Business Rules Engine (BRMS from DB)

**Target System:** BRMS DB | **Fan-out:** Classic Parallel + Resubmit Guard | **forwardChain: true** | **Author:** boony14 | **Generated:** 2026-08-04

---

## §1 — Overview & Purpose

This FM is the **BRMS decision engine** for order processing. It sends each subscriber's contextual data (propositions, offer names, company codes, extended flags) to the Business Rules Management System (BRMS) — formerly implemented as decision tables, now stored in a database. BRMS returns a set of *actions* (AddOffer, RemoveOffer, etc.) that the response handler dynamically executes to modify the `OrderRequest` working memory.

This FM is the most complex in POSTPAID_ADD_OFFER_SUB — 812 lines with 4+ order-type branches, 35+ field extractions, resubmit detection, testBRMS_DB mode, and dynamic action dispatch.

> **forwardChain = true:** Unique among OMXFM rules. After this rule fires, TIBCO BE immediately re-evaluates all rule conditions. This allows downstream rules to respond to BRMS actions without waiting for an external event cycle.

> **Resubmit guard:** If `orderRequest.IsOrderResubmitted == true` AND `orderCurrentActivity.RequestCount > 0`, RequestCount is NOT incremented — preventing duplicate fan-in counting when reprocessing an already-in-flight activity.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_OMX_BRMS_DB` |
| Rule File | `OMX-OM/Rules/OMConsumers/OMXFM/Request/Request_OMX_BRMS_DB.rule` |
| Rule Type | `rule` |
| Priority | 5 |
| Forward Chain | **true** (unusual — most FMs use false) |
| Author | boony14 |
| Description | "Moved brms from decision table to db" |
| Target System | BRMS (via GET_BRMS_ACTIONS JMS event) |
| Integration Pattern | Classic Parallel Fan-out + Resubmit Guard |
| Fan-out Scope | POU Subscribers (per SubscriberOffer) + COU Subscribers (per SubscriberOffer) |
| ALT_CES Support | None |
| IntraActivitySequencing | Not Used |
| Exception Handling | try/catch → HandleActivityException |
| Audit Log Gate | `AllowWriteLog(orderRequest.OrderData.OrderType)` |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | All subscriber/account/offer/extended-info data for BRMS inputs |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | RequestCount, Response[], Status, PreExecCheck, IsOrderResubmitted |

*Note: `globalVariables` is NOT declared in this rule's declare block.*

---

## §4 — Rule Conditions (WHEN)

This FM has **explicit WHEN conditions** (unlike most FMs that rely on working memory presence alone):

```java
when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_BRMS_DB";
    orderRequest.ProcessFlow.NextActivityID == "OMX_BRMS_DB";
    orderCurrentActivity.Status == "WAITING";
}
```

| Condition | Purpose |
|-----------|---------|
| `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Ensures this activity is the next scheduled step |
| `orderCurrentActivity.ActivityID == "OMX_BRMS_DB"` | Guards against wrong activity firing |
| `orderRequest.ProcessFlow.NextActivityID == "OMX_BRMS_DB"` | Cross-validates process flow pointer |
| `orderCurrentActivity.Status == "WAITING"` | Prevents re-firing if already in progress |

---

## §5 — Execution Flow Diagram

```
1. Resubmit detection → isActResub = (RequestCount > 0 && IsOrderResubmitted)
2. PreExecCheck gate → evaluate XPath; if != "true" → SkipActivity("4")
3. Optional audit log start → "OMX-OM BRMS started." (gated by AllowWriteLog)
4. Order type classification:
   - IsChangePricePlanOrderType = OrderType == "2"
   - IsPostpaidAddOfferSubOrderType = OrderType IN ("3","4","69","11018")
   - IsShareplanOrderType = OrderType == "11002"
5. POU Subscriber loop (i=ParentOU, j=Subscriber):
   - Resubmit check: if Response[iResp].ReferenceId == refId && CompletionStatus==2 → skip
   - Find matching Account by AccountRefId
   - Extract 20+ BRMS context fields (see §7)
   - Branch A (PostpaidAddOffer): loop SubscriberOffers[pso]; skip FE_OR_CCBS=CCBS/CRM;
     build listInput (22+ fields); fire GET_BRMS_ACTIONS with mainOffer
   - Branch B (other types): single event per subscriber; different proposition logic;
     build listInput (different field set); fire GET_BRMS_ACTIONS without mainOffer
   - if !isActResub: RequestCount++
6. COU Subscriber loop (i=ParentOU, n=ChildOU, j=Subscriber): identical logic + $n param in XSLT
7. if !isSkipped → GetActivityStatusString("1", false) + SendDataToDB
   else → SkipActivity("4")
8. catch(Exception ae) → HandleActivityException(orderRequest, activity, ae, "")
```

---

## §6 — Rule Action (THEN)

```java
try {
    // PreExecCheck
    String chkXPath = orderCurrentActivity.PreExecCheck;
    String chkRes   = "true";
    boolean isSkipped = true;
    if(String.length(chkXPath) > 0) {
        String sXML = Instance.serializeUsingDefaults(orderRequest);
        chkRes = XPath.execute("/(" + chkXPath + ")", sXML, "ns0=www.tibco.com/be/ontology/...");
    }

    if(String.equals(chkRes, "true")) {
        if(AllowWriteLog(OrderType)) { /* send Logger event: "OMX-OM BRMS started." */ }

        boolean IsChangePricePlanOrderType     = String.equals("2",     OrderType);
        boolean IsPostpaidAddOfferSubOrderType = String.equals("3",     OrderType) || "4" || "69" || "11018";
        boolean IsShareplanOrderType           = String.equals("11002", OrderType);

        for (int i = 0; i < pOuLen; i++) {
            for (int j = 0; j < subLen; j++) {
                // Resubmit guard
                boolean reqSuccess = false;
                for(int iResp ...) if(Response[iResp].ReferenceId==refId && CompletionStatus==2) reqSuccess=true;
                if(!reqSuccess) {
                    // Account lookup + field extraction (see §7)
                    String listInput = "COMPANY_CODE=..." + "|ACC_SUB_TYPE=..." + /* ... */;

                    if (IsPostpaidAddOfferSubOrderType) {
                        for(int pso = 0; pso < subOfferLen; pso++) {
                            if(FE_OR_CCBS == "CCBS" || "CRM") { continue; }
                            Event reqEvent = Event.createEvent(/* XSLT Variant ①, see §9.8 */);
                            Event.Ext.sendEventImmediate(reqEvent);
                            if(!isActResub) orderCurrentActivity.RequestCount++;
                            isSkipped = false;
                        }
                    } else {
                        Event reqEvent = Event.createEvent(/* XSLT Variant ②, see §9.8 */);
                        Event.Ext.sendEventImmediate(reqEvent);
                        if(!isActResub) orderCurrentActivity.RequestCount++;
                        isSkipped = false;
                    }
                }
            }
            // COU loop: identical with (i, n, j) indices, XSLT Variants ③④
        }

        if(!isSkipped) {
            orderCurrentActivity.Status = GetActivityStatusString("1", false);
            SendDataToDB(orderRequest);
        } else {
            SkipActivity(orderRequest, orderCurrentActivity, "4");
        }
    }
} catch (Exception ae) {
    HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §7 — Data Extraction — BRMS ListInput Fields

### Common Fields (all order types)

| Field Key | Source | Method |
|-----------|--------|--------|
| `COMPANY_CODE` | AccountManagementInfo.CompanyCode → fallback: Subscriber.SubscriberType | Direct (CompanyCode commented out) |
| `ACC_SUB_TYPE` | AccountManagementInfo.AccountSubType | Direct field |
| `CUST_INFO_TYPE` | CustomerTypeInfo.Type | `String.valueOfInt(...)` |
| `CHANNEL` | OrderData.Channel | Direct field |
| `IDENTIFICATION` | CustomerGeneralInfo.Identification | Direct field |
| `OLD_PAYMENT_METHOD` | Account[1]/ExtendedInfo[Name='OLD_PAYMENT_METHOD']/Value | XPath |
| `NEW_PAYMENT_METHOD` | Account[1]/PayChannelPaymentMethodInfo/PaymentMethod | XPath |
| `PRICEPLAN_EXT` | GetPriceplan(subscriber, "FE") | Helper |
| `SUB_TYPE_EXT` | Subscriber.SubscriberType | Direct |
| `CALL_VER_STATUS` | Subscriber/ExtendedInfo[Name='CALL_VER_STATUS']/Value | XPath with $i/$j |
| `RELAX_BLACKLIST` | Account[1]/ExtendedInfo[Name='RELAX_BLACKLIST']/Value | XPath |
| `ORG_CHANNEL` | OrderData/ExtendedInfo[Name='ORG_CHANNEL']/Value | XPath |
| `REDZONE` | OrderData/ExtendedInfo[Name='REDZONE']/Value | XPath |
| `VERIFY_RESULT` | OrderData/ExtendedInfo[Name='VERIFY_RESULT']/Value | XPath |
| `FACE_REC` | OrderData/ExtendedInfo[Name='FACE_REC']/Value | XPath |
| `TOPPING_GROUP` | GetTROfferGroup(subscriber, "CCBS", "85") | Helper |

### Branch A Only (PostpaidAddOfferSub — OrderType 3/4/69/11018)

| Field Key | Source | Notes |
|-----------|--------|-------|
| `PROPOSITION` | GetPropositionOffer(sub, "SubscriberOffers.OfferName", "SubscriberOffers.ServiceType", "3") | ServiceType "3" filter |
| `OFFER_NAME` | GetPriceplan(sub, "CCBS") | CCBS priceplan |
| `SOC_NAME` | subOff.OfferName | Current SubscriberOffer |
| `OLD_PROPOSITION` | GetPropositions(sub, "CCBS", true) | |
| `OLD_OFFER_NAME` | GetPriceplan(sub, "CCBS") | Same as OFFER_NAME |
| `DISCOUNT_EXT` | GetDiscount(orderRequest, "CCBS") | |
| `FE_TOPPING_GROUP` | subOff[FE_OR_CCBS=FE]/ExtendedInfo[Name=TR_OFFER_GROUP]/Value | XPath |
| `PP_GROUP` | subscriber/SubscriberOffers[ServiceType="80"]/ExtendedInfo[Name=TR_OFFER_GROUP]/Value | XPath |
| `5G_DEVICE` | subscriber/ExtendedInfo[Name="5G_DEVICE"]/Value | XPath |
| `EXISTING_4G` | if exists(SubscriberOffers[ServiceType="85" and OfferName="RMHSPS10"]) → "RMHSPS10" else "NO_4G" | XPath conditional |
| `DISCOUNT_EMPLOYEE` | GetDiscount(orderRequest, "CCBS") if not blank; else "NO_DISCOUNT" | |
| `RELATED_PROPOSITION` | GetRelatedPropositions(sub, "FE", true) | [Conditional: != "NO_RELATED_PROPOSITION_OFFER"] |
| `FINAL_BILL` | OrderData/ExtendedInfo[Name='FINAL_BILL']/Value | [Conditional: not blank] |
| `CANCEL_TYPE` | OrderData/ExtendedInfo[Name='CANCEL_TYPE']/Value | [Conditional: FINAL_BILL not blank] |

### Branch B Only (Other order types)

| Field Key | Source/Notes |
|-----------|-------------|
| `FE_OFFER_NAME` | GetPriceplan(sub, "FE") — for 5G config |
| `DEALER` | OrderData.DealerCode |
| `SOC_NAME` | OrderType 70/12002: SubscriberOffers[FE_OR_CCBS=FE]/OfferName; else blank |
| `MSIM_IND` | SubscriberGeneralInfo.MultiSimInd [Conditional: not blank] |
| `AGE` | CalculateAgeFromBD(CustomerGeneralInfo.BirthDate) [Conditional: > 0] |
| `IR_FLAG` | Y if exists(SubscriberOffers[contains(SocProperties,"TR_IR_FLAG=Y")]) else N |
| `FE_PROPOSITION` | GetPropositions(sub, "FE", true) [Conditional: not blank] |
| `OLD_SOC_NAME` | GetOldSocName(sub, "CCBS","") [Conditional: not blank] |
| `NEW_PP_RATE` | SubscriberOffers[FE_OR_CCBS=FE and ServiceType=80]/OfferRate [Conditional: ChangePricePlan] |
| `FE_PP_GROUP` | XPath on FE offer TR_OFFER_GROUP [Conditional: != "NO_CONDITION"] |
| `FE_PP_GROUP_CHILD` | subscriber/ExtendedInfo[Name=TR_OFFER_GROUP]/Value [Conditional: not empty] |

> **5G Child Shareplan gate:** If `subscriber/ExtendedInfo[Name="TR_OFFER_GROUP" and tib:index-of(Value,"_CHILD") > 0]`, then `fe_pp_group`, `accSubType`, `discount_employee`, and `ccbs_topping_group` are all set to "NO_CONDITION" and excluded from listInput.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

| OrderType | Flag | BRMS Branch |
|-----------|------|-------------|
| "2" | IsChangePricePlanOrderType | Branch B with FE+CCBS proposition merge |
| "3","4","69","11018" | IsPostpaidAddOfferSubOrderType | Branch A — one event per FE offer |
| "11002" | IsShareplanOrderType | Branch B with offerName from POU priceplan |
| "70","12002" | (none) | Branch B with socName from FE SubscriberOffers |
| all others | (none) | Branch B generic path |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Protocol | Purpose |
|-----------|---------|-------------|----------|---------|
| [OUTBOUND] | OMXFM JMS Channel | GET_BRMS_ACTIONS queue | JMS/ESB | Subscriber context to BRMS |
| [LOG] | OMXESB Logger | Audit log destination | JMS event | Start/response audit (gated) |

### §8.3 — Backend API Details

| System | Operation | Schema NS | Protocol |
|--------|-----------|-----------|----------|
| BRMS DB | `GetBRMSActions` | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd4` | JMS/ESB |

### §8.4 — BE Working Memory Dependencies

| Concept/Field | Direction | Purpose |
|--------------|-----------|---------|
| OrderRequest — all subscriber/account/offer fields | READ | Build BRMS ListInput |
| Activity.RequestCount | READ+WRITE | Resubmit check + fan-out counter |
| Activity.Response[] | READ+WRITE | Read for resubmit check; written by response handler |
| Activity.Status | WRITE | IN_PROGRESS after fan-out |
| Activity.PreExecCheck | READ | XPath skip gate |
| OrderRequest.IsOrderResubmitted | READ | Resubmit detection |
| OrderRequest (modified) | WRITE (response) | BRMS Add/RemoveOffer actions |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Variants (4 total)

| Variant | Scope | XSLT Params |
|---------|-------|-------------|
| ① POU + Offer (Branch A) | PostpaidAddOffer, POU | $i, $j, $orderRequest, $subOff, $effectiveDate, $listInput |
| ② POU only (Branch B) | Other types, POU | $i, $j, $orderRequest, $effectiveDate, $listInput |
| ③ COU + Offer (Branch A) | PostpaidAddOffer, COU | $i, $n, $j, $orderRequest, $subOff, $effectiveDate, $listInput |
| ④ COU only (Branch B) | Other types, COU | $i, $n, $j, $orderRequest, $effectiveDate, $listInput |

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | [Conditional] |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | [Conditional] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Conditional] |
| `RefID` | `ParentOU[$OU]/Subscriber[$Sub]/RefId` | [Always] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Conditional] |
| `mainOffer` | `$subOff/OfferName` | [Conditional: Variants ①③ only] |

### §9.4 — Payload Root Element

| Root Element | Namespace |
|-------------|-----------|
| `ns:GetBRMSActionsRequest` | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd4` |

### §9.6 — Core Payload Fields

| Element | Source | Condition |
|---------|--------|-----------|
| `ns:RefId` | ParentOU[$OU]/Subscriber[$Sub]/RefId | Always |
| `ns:OMXTrackingId` | OrderData/OMXTrackingId | Always |
| `ns:MSISDN` | Subscriber/MSISDN | Conditional |
| `ns:OrderType` | OrderData/OrderType | Always |
| `ns:EffectiveDate` | $effectiveDate (yyyy-MM-dd; Asia/Bangkok; fallback=current-dateTime) | Always |
| `ns:ListInput` | $listInput (pipe-delimited BRMS context, 22–35 fields) | Always |

### §9.7 — Generated XML Example

```xml
<ns:GetBRMSActionsRequest
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd4">
  <ns:RefId>SUB-REF-001</ns:RefId>
  <ns:OMXTrackingId>OMX-2025-TRACK-001</ns:OMXTrackingId>
  <ns:MSISDN>0812345678</ns:MSISDN>
  <ns:OrderType>3</ns:OrderType>
  <ns:EffectiveDate>2026-08-04</ns:EffectiveDate>
  <ns:ListInput>COMPANY_CODE=IND|ACC_SUB_TYPE=PPM|CUST_INFO_TYPE=1|PROPOSITION=PROMO_5G|OFFER_NAME=HAPPY5G99|CHANNEL=DTAC_ONLINE|IDENTIFICATION=1234567890123|OLD_PROPOSITION=PROMO_4G|OLD_OFFER_NAME=HAPPY4G79|OLD_PAYMENT_METHOD=CC|NEW_PAYMENT_METHOD=CC|ACC_SUB_TYPE_EXT=PPM|SUB_TYPE_EXT=IND|PRICEPLAN_EXT=HAPPY5G99|SOC_NAME=5G_ADD_DATA|RELAX_BLACKLIST=N|ORG_CHANNEL=ONLINE|VERIFY_RESULT=PASS|REDZONE=N|DISCOUNT_EXT=|FE_TOPPING_GROUP=TOPPING_5G|PP_GROUP=PP_5G|5G_DEVICE=Y|EXISTING_4G=NO_4G|TOPPING_GROUP=NO_CCBS_TOPPING|DISCOUNT_EMPLOYEE=NO_DISCOUNT|FACE_REC=N</ns:ListInput>
</ns:GetBRMSActionsRequest>
```

### §9.8 — XSLT Tree (Variant ① — POU + Offer, Branch A)

```text
createEvent
└── event
    ├── JMSPriority        ← $orderRequest/OrderPriority              [Conditional]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId    [Conditional]
    ├── OrderID            ← $orderRequest/OrderData/OrderID          [Conditional]
    ├── RefID              ← ParentOU[$OU]/Subscriber[$Sub]/RefId     [Always]
    ├── OrderType          ← $orderRequest/OrderData/OrderType        [Conditional]
    ├── mainOffer          ← $subOff/OfferName                        [Conditional: Branch A only]
    └── payload
        └── ns:GetBRMSActionsRequest
            ├── ns:RefId            ← ParentOU[$OU]/Subscriber[$Sub]/RefId     [Always]
            ├── ns:OMXTrackingId    ← $orderRequest/OrderData/OMXTrackingId    [Always]
            ├── ns:MSISDN           ← Subscriber/MSISDN                        [Conditional]
            ├── ns:OrderType        ← $orderRequest/OrderData/OrderType        [Always]
            ├── ns:EffectiveDate    ← $effectiveDate                           [Always]
            └── ns:ListInput        ← $listInput (pipe-delimited)              [Always]
```

Variants ②③④ are identical except:
- ② (POU Branch B): no mainOffer, no $subOff param
- ③ (COU Branch A): adds $n (ChildOU index), uses `ParentOU[$OU]/ChildOU[$iCOU]/Subscriber[$Sub]` path + mainOffer
- ④ (COU Branch B): adds $n, uses COU path, no mainOffer

---

## §10 — XSLT Field Mapping Tree (condensed)

```text
createEvent
└── event
    ├── JMSPriority        ← $orderRequest/OrderPriority       [Conditional]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId  [Conditional]
    ├── OrderID            ← $orderRequest/OrderData/OrderID   [Conditional]
    ├── RefID              ← ParentOU[$OU]/Subscriber[$Sub]/RefId  [Always]
    ├── OrderType          ← OrderData/OrderType               [Conditional]
    ├── mainOffer          ← $subOff/OfferName                 [Conditional: Branch A variants only]
    └── payload
        └── ns:GetBRMSActionsRequest
            ├── ns:RefId         ← ParentOU path RefId         [Always]
            ├── ns:OMXTrackingId ← OMXTrackingId              [Always]
            ├── ns:MSISDN        ← Subscriber MSISDN           [Conditional]
            ├── ns:OrderType     ← OrderType                   [Always]
            ├── ns:EffectiveDate ← computed date string        [Always]
            └── ns:ListInput     ← pipe-delimited BRMS string  [Always]
```

---

## §11 — Audit Logging

| Event | AUDIT_TRACE | OPERATION_NAME | Gate |
|-------|------------|----------------|------|
| Request start | `"OMX-OM BRMS started."` | `"/Rules/OMConsumers/OMXOM/OMX_BRMS_DB"` | `AllowWriteLog(OrderType)` |
| Response | `"Response received for BRMSActions"` | `"OMX_BRMS_DB"` | `!isTestBRMS && AllowWriteLog(OrderType)` |

> **testBRMS_DB suppression:** If `eventResponse.Actions` contains "testBRMS_DB", the response audit log is suppressed, enabling non-invasive BRMS rule testing.

---

## §12 — Activity Status Management

| Scenario | Action | Status Code |
|----------|--------|-------------|
| At least one event fired | `GetActivityStatusString("1", false)` + `SendDataToDB` | 1 = IN_PROGRESS |
| No events fired | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | 4 = SKIPPED |

---

## §13 — Exception / Error Handling

Entire THEN block is wrapped in `try/catch(Exception ae)`:

```java
RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
```

4th argument is empty string — no additional context passed.

---

## §14 — Helper Functions Reference

| Function | Signature | Purpose |
|----------|----------|---------|
| `AllowWriteLog` | `Boolean(orderType)` | Gates audit logging by order type |
| `GetPriceplan` | `String(subscriber, system)` | Returns priceplan offer name (FE/CCBS) |
| `GetPropositionOffer` | `String(sub, offerField, stField, serviceType)` | Proposition filtered by service type |
| `GetPropositions` | `String(sub, system, bool)` | All propositions for a system |
| `GetRelatedPropositions` | `String(sub, system, bool)` | Related propositions |
| `GetDiscount` | `String(orderRequest, system)` | Discount value from given system |
| `GetTROfferGroup` | `String(sub, system, serviceType)` | TR offer group |
| `GetAttributeValue` | `String(sub, ...)` | Offer attribute value filtered by service type |
| `GetOldSocName` | `String(sub, system, default)` | Existing SOC name |
| `BRMS.IsBlank` | `Boolean(String)` | Null/empty check |
| `BRMS.IsBlankOrStringNull` | `Boolean(String)` | Null/empty/"null" string check |
| `BRMS.CalculateAgeFromBD` | `int(DateTime)` | Age in years from birthdate |
| `GetActivityStatusString` | `String(code, isSkip)` | Activity status label |
| `SendDataToDB` | `void(orderRequest)` | Persist activity state |
| `SkipActivity` | `void(orderRequest, activity, code)` | Mark activity skipped |
| `HandleActivityException` | `void(orderRequest, activity, ex, ctx)` | Standard exception handler |

---

## §15 — Function Dependency Tree

```text
Request_OMX_BRMS_DB.rule
├── RuleFunctions.Helpers.AllowWriteLog(OrderType)
├── RuleFunctions.Helpers.GetPriceplan(subscriber, "FE"/"CCBS")
├── RuleFunctions.Helpers.GetPropositionOffer(sub, ...)
├── RuleFunctions.Helpers.GetPropositions(sub, system, bool)
├── RuleFunctions.Helpers.GetRelatedPropositions(sub, system, bool)
├── RuleFunctions.Helpers.GetDiscount(orderRequest, "CCBS")
├── RuleFunctions.Helpers.GetTROfferGroup(sub, "CCBS", "85")
├── RuleFunctions.Helpers.GetAttributeValue(sub, ...)
├── RuleFunctions.Helpers.GetOldSocName(sub, "CCBS", "")
├── RuleFunctions.Helpers.BRMS.IsBlank(String)
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(String)
├── RuleFunctions.Helpers.BRMS.CalculateAgeFromBD(DateTime)
├── Event.Ext.sendEventImmediate(reqEvent)   ── classic fan-out
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")
└── RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")

Response_OMX_BRMS_DB.rulefunction
├── GetBrmsItems(orderRequest, eventResponse)  → Concepts.OMX.BrmsItems
├── Engine.invokeRuleFunction("/RuleFunctions/Helpers/BRMS/" + item.Action, params)
│   ├── /BRMS/AddOfferToOrderRequest
│   ├── /BRMS/AddOfferWithExtendedToOrderRequest
│   ├── /BRMS/AddOfferWithParamToOrderRequest
│   ├── /BRMS/AddRelatedOfferWithParamToOrderRequest
│   ├── /BRMS/RemoveOfferToOrderRequest
│   ├── /BRMS/AddOfferForOrderRemoveToOrderRequest
│   └── /BRMS/RemoveOfferWithExtendedToOrderRequest
└── Instance.deleteInstance(items)
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Fields Used |
|---------|----------------|
| `Concepts.OrderRequest.OrderRequest` | All subscriber/account/offer fields; IsOrderResubmitted; ProcessFlow |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, SubscriberType, MSISDN, AccountRefId, SubscriberOffers[], ExtendedInfo[] |
| `Concepts.OrderRequest.OrderElements.Account` | RefId, AccountManagementInfo, ExtendedInfo[OLD_PAYMENT_METHOD, RELAX_BLACKLIST] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | OfferName, ServiceType, SocProperties, ExtendedInfo[FE_OR_CCBS, TR_OFFER_GROUP], OfferRate |
| `Concepts.OM.ProcessConfig.Activity` | RequestCount, Response[], Status, PreExecCheck |
| `Concepts.FM.Response.GetBRMSActionsRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |
| `Concepts.OMX.BrmsItems` / `Concepts.OMX.BrmsItem` | Action, DeployMode, EffectiveDate, OfferName, RefIDs, etc. |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Send BRMS query per subscriber with order-type-specific pipe-delimited ListInput |
| R2 | PostpaidAddOfferSub (type 3/4/69/11018): one BRMS request per FE SubscriberOffer (not per subscriber) |
| R3 | Resubmit guard: do not increment RequestCount if activity was previously in-flight |
| R4 | Parse BRMS Actions string; invoke typed Add/RemoveOffer helpers per action item |
| R5 | testBRMS_DB mode: suppress audit log when Actions contains "testBRMS_DB" token |
| R6 | 5G child shareplan gate: exclude specific BRMS input fields for _CHILD TR_OFFER_GROUP subscribers |
| R7 | EffectiveDate: Asia/Bangkok timezone translation, yyyy-MM-dd format; fallback to current-dateTime |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| 812-line rule with 4+ order-type branches and 35+ field extractions | [HIGH] | Decompose into strategy classes per order type |
| Dynamic BRMS action dispatch via string path (`Engine.invokeRuleFunction("path" + action)`) | [HIGH] | Replace with typed polymorphic command pattern |
| Pipe-delimited ListInput is untyped and fragile | [MEDIUM] | Replace with structured JSON/XML BRMS API |
| CompanyCode mapping commented out (OMX-3213) — uses SubscriberType as fallback | [MEDIUM] | Verify CompanyCode source with business team |
| Account-level loop entirely commented out | [LOW] | Confirm if deprecated or needed for future types |
| forwardChain=true may cause unexpected cascades after BRMS actions | [MEDIUM] | Map downstream rules triggered by forwardChain |

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_OMX_BRMS_DB` is the most action-rich response handler in the OMXFM suite. It: (1) detects and strips `testBRMS_DB` test flag; (2) calls `GetBrmsItems` to parse BRMS Actions into typed items; (3) dynamically invokes Add/RemoveOffer helpers per item to modify `OrderRequest` in working memory; (4) constructs a `GetBRMSActionsRes` concept; (5) fires conditional audit log; (6) evaluates fan-in completion.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Modified by BRMS action helpers |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.GET_BRMS_ACTIONS` | Actions string, RefID, ResponseCode |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] written; RequestCount read |

### §19.3 — BRMS Action Dispatch

| Action Name | Additional Parameters |
|------------|----------------------|
| `AddOfferToOrderRequest` | DeployMode, EffectiveDate, ExpirationDate, OfferName, ServiceType, Soc, PouRefID, CouRefID, SubRefID, OfferLevel, IOT |
| `AddOfferWithExtendedToOrderRequest` | + OfferExtendedNameValue, CycleCount |
| `AddOfferWithParamToOrderRequest` | + OfferParamNameValue |
| `AddRelatedOfferWithParamToOrderRequest` | + MainOfferName, OfferParamNameValue |
| `RemoveOfferToOrderRequest` | DeployMode, EffectiveDate, ExpirationDate, OfferName, ServiceType, Soc, PouRefID, CouRefID, SubRefID, OfferLevel, IOT |
| `AddOfferForOrderRemoveToOrderRequest` | Same as RemoveOffer |
| `RemoveOfferWithExtendedToOrderRequest` | + OfferExtendedNameValue |

### §19.3b — GetBRMSActionsRes Construction

```text
createObject
└── object  extId ← $extId (pre-generated OMXUtils.generateTrackingID())  [Always]
    ├── ResponseCode       ← $eventResponse/ResponseCode       [Conditional]
    ├── ResponseMessage    ← $eventResponse/ResponseMsg        [Conditional]
    ├── CompletionStatus   ← $eventResponse/CompletionStatus   [Conditional]
    └── ReferenceId        ← $eventResponse/RefID              [Conditional]
```

> **Not ResponseBase:** Uses `Concepts.FM.Response.GetBRMSActionsRes`, not `Concepts.FM.Base.ResponseBase`. extId is passed as explicit XSLT param.

### §19.4 — Response Completion Logic (Fan-in)

| Component | Value |
|-----------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Return `"true"` | All BRMS requests completed successfully |
| Return `"false"` | Pending responses remain |

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| `AUDIT_TRACE` | `"Response received for BRMSActions"` (static) |
| `OPERATION_NAME` | `"OMX_BRMS_DB"` (static) |
| Gate | `!isTestBRMS && AllowWriteLog(orderRequest.OrderData.OrderType)` |
| Payload | Conditional on `WritePayload="true"` — copy of eventResponse |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
