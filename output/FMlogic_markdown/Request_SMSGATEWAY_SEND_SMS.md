# Request_SMSGATEWAY_SEND_SMS

> TIBCO BusinessEvents · OMXFM External Rule — SMS Gateway  
> Sends SMS notifications to subscribers; dual-loop (ChildOU + ParentOU); three XSLT variants; subscriber concept writeback in response.

**Author:** awalia-t420 | **Backend:** SMS Gateway | **Schema:** `ns:SMSRequest` | **Protocol:** Async JMS

---

## §1 Overview & Purpose

Constructs and dispatches `ns:SMSRequest` JMS events to the SMS Gateway to notify subscribers of order-related changes (price plan adds/changes, IDD/IR roaming activation, discount and topping additions/removals).

| Attribute | Value |
|-----------|-------|
| Rule class | `Rules.OMConsumers.OMXFM.Request.Request_SMSGATEWAY_SEND_SMS` |
| Target backend | SMS Gateway |
| Protocol | Async JMS via `/Channels/OMXFMConnectionRequest` |
| Destination | `SMSGATEWAY_SEND_SMS` |
| Event type | `Events.OMConsumers.OMXFM.Request.SMSGATEWAY_SEND_SMS` |
| Payload schema | `ns:SMSRequest` (SMSRequest.xsd; `http://www.tibco.com/schemas/SMSService/Resources/Schema.xsd`) |
| RefID source | `subscriber.RefId` — one per subscriber context |
| Dispatch method | `Event.Ext.sendEventImmediate` (direct, no IntraActivitySequencing) |
| Fan-in | `successResponseCount == RequestCount` |
| Response concept | `Concepts.FM.Response.SMSGATEWAY_SendSMSRes` |

---

## §2 Rule Metadata & Attributes

| Field | Value |
|-------|-------|
| Rule name | `Request_SMSGATEWAY_SEND_SMS` |
| Namespace | `Rules.OMConsumers.OMXFM.Request` |
| Author | awalia-t420 |
| Priority | 5 (default) |
| Forward-chain | false |
| Rule category | OMXFM External — Async JMS request |
| File size | ~288.7 KB (three XSLT variants inline) |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order context |
| `orderCurrentActivity` | `Concepts.OrderCurrentActivity` | Tracks RequestCount and Response array |
| `nextAct` | `Concepts.ProcessActivity` | Supplies PreExecCheck |
| `globalVariables` | `Concepts.GlobalVariables` | System config: component names, WritePayload |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity.ActivityID == "SMSGATEWAY_SEND_SMS"` | Rule scope |
| 2 | `orderCurrentActivity.Status == "IN_PROGRESS"` | Active activity |
| 3 | `orderRequest != null` | Order context exists |

---

## §5 Execution Flow Diagram

```
1. Outer loop — ChildOU path (ParentOU[i] → ChildOU[k] → Subscriber[j])
2. ResSuccess check → skip subscriber if CompletionStatus=2 already received for RefId
3. GetXMLForSubscriber → extract subscriber XML for PreExecCheck
4. PreExecCheck gate → skip subscriber if gate returns false
5. Offer classification → pp / contract / rmvx / iddOffL / irOffL / discOffL / toppOffL
6. Date/duration calculations → ppEffDT, GetPPDurationMonth, GetBillCycle, GetPPExpirationDate
7. Per-offer SMS dispatch (ChildOU Offer variant ①) → one SMS per qualifying offer
   → RequestCount++ (if !isActResub) → audit if AllowWriteLog
8. Outer loop — ParentOU path (ParentOU[i] → Subscriber[j])
9. Same classification logic
10. Branch by OrderType:
    → OrderType ∈ {3,69,70,11018} + qualifying offers → ParentOU Offer variant ②
      (audit unconditional — BUG)
    → Otherwise → Generic PP-only variant ③ (audit gated by AllowWriteLog)
11. Fan-in: successResponseCount == RequestCount → activity completes
```

---

## §6 Rule Action (THEN) — Step-by-Step Logic

### Loop 1 — ChildOU Subscriber (lines 27–507)

Triple-nested loop: `for i in ParentOU → for k in ChildOU → for j in Subscriber`

| Sub-step | Logic |
|----------|-------|
| Get RefId | `String refId = subscriber.RefId;` |
| Skip check | Scan Response[]: if ReferenceId==refId && CompletionStatus==2 → skip |
| XML extraction | `GetXMLForSubscriber(orderRequest, refId)` |
| PreExecCheck | If length>0: XPath eval against subscriber XML; skip if not "true" |
| Language | From `SubscriberGeneralInfo.Language`; default "TH" |
| PP classification | ServiceType='80' AND FE/blank → `pp` offer name, `subscriberPP` object |
| Contract | TR_CONTRACT_IND=Y AND FE/BRMS/blank → `contract`, `contractDesc` |
| RMVX | OfferName='RMVX00000000001' → `rmvxProps` for duration calculation |
| IDD/IR/Discount/Topping | See §7 for classification rules |
| Date calculations | ppEffDT = EffectiveDate ?? OfferOriginalEffectiveDate; GetPPDurationMonth; GetBillCycle; GetPPExpirationDate |
| Per-offer send | For each offer: offerSMSType → dispatch variant ①; RequestCount++ (if !isActResub); isSkipped=false; audit if AllowWriteLog |

### Loop 2 — ParentOU Subscriber (lines 508–~1050)

Double-nested loop: `for i in ParentOU → for j in Subscriber`

Same ResSuccess / PreExecCheck / offer-classification logic. Branch at dispatch:

| Branch | Condition | Variant | Audit |
|--------|-----------|---------|-------|
| Offer SMS | OrderType ∈ {3,69,70,11018} AND qualifying offers | XSLT variant ② | Unconditional — **Bug** |
| Generic PP SMS | Otherwise | XSLT variant ③ | Gated by `AllowWriteLog(OrderType)` |

> **Bug:** XSLT variant ② (lines 474–485) sends the audit log unconditionally — no `AllowWriteLog(OrderType)` guard. Variants ① and ③ correctly gate the audit. OrderType 3/69/70/11018 always generates audit entries.

---

## §7 Offer Classification & offerSMSType Encoding

### Offer classification rules

| Class | Inclusion criteria | List variable |
|-------|-------------------|---------------|
| Price Plan | `ServiceType='80'` AND (FE_OR_CCBS=FE or blank) | `pp`, `subscriberPP` |
| Contract | `TR_CONTRACT_IND=Y` AND (FE_OR_CCBS=FE/BRMS/blank) | `contract`, `contractDesc` |
| RMVX | `OfferName='RMVX00000000001'` | `rmvxProps` |
| IDD | `TR_IDD_FLAG=Y` OR (OrderType=11018 AND OfferName='PROINTL1') | `iddOffL` |
| IR (Int'l Roaming) | `TR_IR_FLAG=Y` OR (OrderType=11018 AND OfferName='PROROAM2S') | `irOffL` |
| Discount | `ServiceType='68'` | `discOffL` |
| Topping | Offer has `ExtendedInfo[SMS_IND]` | `toppOffL` |

Guard for IDD/IR/Discount/Topping: `FE_OR_CCBS ∈ {FE, BRMS, BRMS_REMOVE}` OR (`OrderType=11018` AND `ExtendedInfo[INJECT_OFFER]`)

### offerSMSType string encoding (variant ①)

| Offer type | Condition | offerSMSType value |
|-----------|-----------|-------------------|
| IDD | EXP_TYPE=IM | `REMOVE_IDD_IM` |
| IDD | EXP_TYPE=FUT | `REMOVE_IDD_FUT` |
| IDD | EFF_TYPE=IM | `ADD_IDD_IM` |
| IDD | EFF_TYPE=FUT | `ADD_IDD_FUT` |
| IR | EXP_TYPE=IM | `REMOVE_IR_IM` |
| IR | EXP_TYPE=FUT | `REMOVE_IR_FUT` |
| IR | EFF_TYPE=IM | `ADD_IR_IM` |
| IR | EFF_TYPE=FUT | `ADD_IR_FUT` |
| Discount | Has expiry date | `ADD_DISCOUNT_EXPIRE` |
| Discount | No expiry | `ADD_DISCOUNT` |
| Topping | ADD + RC | `ADD_{TOPPING_TYPE}_RC` |
| Topping | ADD + OC | `ADD_{TOPPING_TYPE}_OC` |
| Topping | REMOVE + RC | `REMOVE_{TOPPING_TYPE}_RC` |
| Topping | REMOVE + OC | `REMOVE_{TOPPING_TYPE}_OC` |

`{TOPPING_TYPE}` = value of `ExtendedInfo[SMS_IND]/Value` from the offer.

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

| OrderType | SMS behavior |
|-----------|-------------|
| 3, 69, 70 | IDD/IR/Discount/Topping offer SMS (ParentOU variant ②) |
| 11018 | Same + INJECT_OFFER and special IDD/IR (PROINTL1 / PROROAM2S) |
| All others | Generic PP-only SMS (variant ③) |

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Protocol |
|-----------|---------|-------------|----------|
| [OUTBOUND] | `/Channels/OMXFMConnectionRequest` | `SMSGATEWAY_SEND_SMS` | JMS async |
| [INBOUND] | Response channel | `SMSGATEWAY_SendSMSRes` | JMS async reply |
| [LOG] | `/Events/OMConsumers/OMXESB/Logger` | Audit logger | Async event |

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | SMS Gateway |
| Operation | Send SMS notification |
| Request schema | `ns:SMSRequest` from `_SharedResources/Schemas/ESB/SMSRequest.xsd` |
| Namespace URI | `http://www.tibco.com/schemas/SMSService/Resources/Schema.xsd` |
| Super event | `/Events/Base/OMXRequestBaseEvent` |
| Correlation | `JMSCorrelationID = OMXTrackingId`; `RefID = subscriber.RefId` |
| Response concept | `Concepts.FM.Response.SMSGATEWAY_SendSMSRes` |

### §8.4 BE Working Memory Dependencies

| Concept field | Access | Description |
|--------------|--------|-------------|
| `subscriber.RefId` | READ | RefID for correlation |
| `subscriber.SubscriberOffers[]` | READ | Offer classification |
| `subscriber.ResponseCode` | WRITE | Written back from response RF |
| `subscriber.ResponseMsg` | WRITE | Written back from response RF |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-in counter |
| `orderCurrentActivity.Response[]` | READ | Prior response skip check |

### §8.5 ExtendedInfo Fields Required

| Key name | Required? | Used for |
|----------|-----------|---------|
| `FE_OR_CCBS` | Optional | Offer eligibility gate |
| `TR_IDD_FLAG` | Optional | Classify as IDD |
| `TR_IR_FLAG` | Optional | Classify as IR |
| `TR_CONTRACT_IND` | Optional | Identify contract offer |
| `SMS_IND` | Optional | Classify as topping; value = TOPPING_TYPE |
| `EFF_TYPE` | Optional | ADD SMS type (IM/FUT) |
| `EXP_TYPE` | Optional | REMOVE SMS type (IM/FUT) |
| `INJECT_OFFER` | Optional | OrderType=11018 special flag |
| `OfferActivityDate` | Optional | FUT flag → PricePlan "FUTPP" |
| `BILL_DESCRIPTION` | Optional | Preferred PP description (variant ③ Param #2) |

### §8.6 Global Variable Dependencies

| Path | Used for |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/.../MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Conditional payload in audit |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding — Three Variants

| Parameter | Variant ① ChildOU Offer | Variant ② ParentOU Offer | Variant ③ Generic PP |
|-----------|------------------------|--------------------------|---------------------|
| `i, k, j` | POU/COU/Sub indices | i/j only | i/j only |
| `refId` | ✓ | ✓ | ✓ |
| `pp`, `contract`, `socDesc`, `address`, `contractDesc` | ✓ | ✓ | ✓ |
| `currentDate`, `ppExpDate`, `ppEffDate` | ✓ | ✓ | ✓ |
| `durationMn` | ✓ | ✓ | — |
| `offerSMSType` | ✓ | — | — |
| `offerEffDate`, `offerExpDate` | ✓ | — | — |
| `rcPrice`, `permanentCreditLimit` | ✓ | — | — |
| `subscriberPP` | — | — | ✓ (FUTPP detection) |
| `currPPDesc`, `currPPExp` | — | — | ✓ |

### §9.2 ns:SMSRequest Payload Fields

| XML element | Source / Logic | Variants |
|-------------|---------------|---------|
| `ns:MSISDN` | if starts-with "0" → `concat("66", substring-after(MSISDN, "0"))` else as-is | All |
| `ns:CustomerType` | `Customer/CustomerTypeInfo/Type` | All |
| `ns:Language` | `SubscriberGeneralInfo/Language` ?? "TH" | All |
| `ns:OrderType` | `$orderRequest/OrderData/OrderType` | All |
| `ns:PricePlan` | ①②: durationMn>0 → "NXTPP" else pp; ③: subscriberPP/EI[OfferActivityDate=FUT] → "FUTPP" else pp | All (logic differs) |
| `ns:CompanyCode` | `subscriber.SubscriberType` | All |
| `ns:ProductType` | `""` (empty) | All |
| `ns:Proposition` | `$contract` | All |
| `ns:MessageType` | `""` (empty) | All |
| `ns:Channel` | `$orderRequest/OrderData/Channel` | All; if Channel present |

### §9.3 ns:ParamList — Named Parameters

| Param name | Value / Logic | Variants |
|------------|--------------|---------|
| `"1"` — CustomerName | CustomerType=73: FirstName+" "+LastName (if LastName non-empty) else FirstName; else OrgName | All |
| `"2"` — socDesc | ①②: `$socDesc`; ③: PP BILL_DESCRIPTION ExtendedInfo ?? `$socDesc` | All (③ differs) |
| `"3"` — BillCycleNo | `Customer/BillCycleNo` | All |
| `"4"` — address | `$address` | All |
| `"5"` — MSISDN | Raw MSISDN (no 0→66 conversion here) | All |
| `"6"` — contract | `$contract` | All |
| `"7"` — contractDesc | `$contractDesc` | All |
| `"8"` — Identification | `CustomerGeneralInfo/Identification` | All |
| `"9"` — currentDate | `$currentDate` | All |
| `"10"` — ppExpDate | `$ppExpDate` | All |
| `"ppEffDate"` | `$ppEffDate` | All |
| `"offer"` | `$offerSMSType` | ① only |
| `"offerEffDate"` | `$offerEffDate` | ① only |
| `"offerExpDate"` | `$offerExpDate` | ① only |
| `"rcPrice"` | `$rcPrice` | ① only |
| `"permanentCreditLimit"` | `$permanentCreditLimit` | ① only |
| `"currPPDesc"` | `$currPPDesc` | ③ only |
| `"currPPExp"` | `$currPPExp` | ③ only |

> **Note:** Param #5 uses the raw MSISDN (not the 0→66 converted form). Only `ns:MSISDN` at the top of the payload receives the conversion. This is intentional — the SMS Gateway needs E.164 for routing while Param #5 is a display value.

---

## §10 XSLT Field Mapping — Output XML Tree

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                   [Conditional: if OrderPriority present]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId          [Conditional: if OMXTrackingId present]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                [Conditional: if OrderID present]
    ├── RefID                ← $refId                                         [Always ①; Conditional ②③]
    ├── OrderType            ← $orderRequest/OrderData/OrderType              [Conditional: if OrderType present]
    └── payload
        └── ns:SMSRequest
            ├── ns:MSISDN        ← concat("66", substr(MSISDN)) OR MSISDN as-is  [Always]
            ├── ns:CustomerType  ← Customer/CustomerTypeInfo/Type             [Always]
            ├── ns:Language      ← SubscriberGeneralInfo/Language ?? "TH"    [Always]
            ├── ns:OrderType     ← $orderRequest/OrderData/OrderType         [Always]
            ├── ns:PricePlan     ← ①②: durationMn>0→"NXTPP" else $pp        [Always]
            │                      ③: EI[OfferActivityDate=FUT]→"FUTPP" else $pp
            ├── ns:CompanyCode   ← subscriber.SubscriberType                 [Always]
            ├── ns:ProductType   ← ""                                        [Always]
            ├── ns:Proposition   ← $contract                                 [Always]
            ├── ns:MessageType   ← ""                                        [Always]
            ├── ns:ParamList
            │   ├── Param[1]     ← CustomerType=73→Sub name; else OrgName   [Always]
            │   ├── Param[2]     ← $socDesc (①②) / BILL_DESC??socDesc (③)  [Always]
            │   ├── Param[3]     ← Customer/BillCycleNo                     [Always]
            │   ├── Param[4]     ← $address                                 [Always]
            │   ├── Param[5]     ← subscriber.MSISDN (raw — NOT converted)  [Always]
            │   ├── Param[6]     ← $contract                                [Always]
            │   ├── Param[7]     ← $contractDesc                            [Always]
            │   ├── Param[8]     ← CustomerGeneralInfo/Identification       [Always]
            │   ├── Param[9]     ← $currentDate                             [Always]
            │   ├── Param[10]    ← $ppExpDate                               [Always]
            │   ├── Param[ppEffDate] ← $ppEffDate                           [Always]
            │   ├── Param[offer]       ← $offerSMSType                      [Variant ① only]
            │   ├── Param[offerEffDate] ← $offerEffDate                     [Variant ① only]
            │   ├── Param[offerExpDate] ← $offerExpDate                     [Variant ① only]
            │   ├── Param[rcPrice]     ← $rcPrice                           [Variant ① only]
            │   ├── Param[permanentCreditLimit] ← $permanentCreditLimit      [Variant ① only]
            │   ├── Param[currPPDesc]  ← $currPPDesc                        [Variant ③ only]
            │   └── Param[currPPExp]   ← $currPPExp                         [Variant ③ only]
            └── ns:Channel       ← $orderRequest/OrderData/Channel          [Conditional: if Channel present]
```

---

## §11 Audit Logging

| Audit point | Gate condition | AUDIT_TRACE value | Note |
|------------|---------------|-------------------|------|
| Request variant ① | `AllowWriteLog(OrderType)` | `concat("Request Sent for RefId", $refId)` | [Bug: missing space before $refId] |
| Request variant ② | **Unconditional** | `concat("Request Sent for RefId", $refId)` | [Bug: no AllowWriteLog gate] |
| Request variant ③ | `AllowWriteLog(OrderType)` | `concat("Request Sent for RefId", $refId)` | Consistent with ① |
| Response RF | `AllowWriteLog(OrderType)` | `concat("Response received for RefId ", eventResponse/RefID)` | Space present in response trace |

**Two bugs:**
1. All three request AUDIT_TRACE values use `"Request Sent for RefId"` + refId (no space). Log reads "Request Sent for RefId123456".
2. Variant ② always logs regardless of `AllowWriteLog` policy.

| Audit field | Value |
|------------|-------|
| ESBUUID | OMXTrackingId |
| PROCESS_ID | `concat(pid, "_REQ")` / `concat(pid, "_RES")` |
| COMPONENT_NAME | `globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `"SMSGATEWAY_SEND_SMS"` |
| TARGET_SYSTEM | `globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| payload | Conditional on `WritePayload="true"` |

---

## §12 Activity Status Management

This rule does not directly modify activity status. Status transitions managed by response RF (fan-in → COMPLETED).

| Flag | Set when | Purpose |
|------|----------|---------|
| `isSkipped` | Set `false` after each dispatch | Tracks whether any requests were sent |
| `isActResub` | Checked before RequestCount++ | Prevents double-count on retry |

---

## §13 Exception / Error Handling

Standard OMXFM pattern: `HandleActivityException` called in catch block. The `reqSuccess` skip check (CompletionStatus==2) guards against duplicate SMS sends on resubmission.

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `RuleFunctions.Helpers.AllowWriteLog(OrderType)` | OrderType-dependent audit gate; applies to BOTH request and response audit |
| `RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)` | Extracts subscriber XML for PreExecCheck evaluation |
| `RuleFunctions.Helpers.GetPPDurationMonth(rmvxProps, subscriberPP)` | Calculates remaining PP duration in months |
| `RuleFunctions.Helpers.GetBillCycle(orderRequest)` | Retrieves billing cycle number |
| `RuleFunctions.Helpers.GetPPExpirationDate(subscriberPP, durationMn)` | Calculates PP expiration date |
| `RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(str)` | Null/blank string check |
| `OMXUtils.generateTrackingID()` | Used in response RF to generate extId |

---

## §15 Function Dependency Tree

```text
Request_SMSGATEWAY_SEND_SMS (rule)
├── RuleFunctions.Helpers.AllowWriteLog(OrderType)
│   └── [OrderType whitelist check]
├── RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)
├── RuleFunctions.Helpers.GetPPDurationMonth(rmvxProps, subscriberPP)
├── RuleFunctions.Helpers.GetBillCycle(orderRequest)
├── RuleFunctions.Helpers.GetPPExpirationDate(subscriberPP, durationMn)
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(str)
├── XPath.execute(preExecCheck, sXML, ns0=...)
└── Event.Ext.sendEventImmediate(reqEvent) × N

Response_SMSGATEWAY_SEND_SMS (rulefunction)
├── RuleFunctions.Helpers.AllowWriteLog(OrderType)    ← response also gated
├── OMXUtils.generateTrackingID()                     ← response extId
├── Instance.createInstance("xslt://{{ResponseBase}}...")
├── Instance.getByExtIdByUri("SUB:"+JMSCorrelationID+":"+RefID)
│   └── fallback: "CSUB:"+JMSCorrelationID+":"+RefID
├── sub.ResponseCode = eventResponse.ResponseCode      ← writeback
├── sub.ResponseMsg = eventResponse.ResponseMsg        ← writeback
└── XPath.evalAsInt(count(Response[right(trim(ResponseCode),3)="000"]))
```

---

## §16 Concept Definitions Referenced

| Concept | Key fields used |
|---------|----------------|
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, SubscriberType, SubscriberGeneralInfo.Language, SubscriberOffers[], SubscriberName, ResponseCode (WRITE), ResponseMsg (WRITE) |
| `Concepts.FM.Response.SMSGATEWAY_SendSMSRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |
| `Concepts.OrderCurrentActivity` | ActivityID, Status, RequestCount, Response[] |
| `Concepts.ProcessActivity` | PreExecCheck |
| `Concepts.GlobalVariables` | OMX_COMMON.*, OMX_OM.WritePayload |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | SMS must be sent once per qualifying offer per subscriber (not once per order) |
| R2 | `ns:MSISDN` must use E.164 format (66-prefix); Param #5 retains raw format |
| R3 | Fan-in completes when all dispatched requests receive ResponseCode ending in "000" |
| R4 | `AllowWriteLog(OrderType)` must gate BOTH request and response audit logging |
| R5 | ResponseCode and ResponseMsg must be written back to the Subscriber concept |
| R6 | Resubmission (isActResub=true) must not increment RequestCount |
| R7 | Thai date formatting (month conversion) must apply when Language="TH" |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Variant ② audit always logs (no AllowWriteLog gate) | [MEDIUM] | Add AllowWriteLog gate consistently across all three variants |
| Missing space in AUDIT_TRACE "Request Sent for RefId" | [LOW] | Use `concat("Request Sent for RefId ", $refId)` in rewrite |
| Param #5 raw MSISDN vs ns:MSISDN E.164 — easy to confuse | [MEDIUM] | Document clearly in API contract; verify gateway expectation per field |
| Three XSLT variants for essentially same structure — drift risk | [MEDIUM] | Consolidate into single configurable builder; variant differences are parameterizable |
| 288.7 KB rule file — maintenance risk | [HIGH] | Break into composable units: offer-classifier, date-calculator, SMS-dispatcher |
| Subscriber concept writeback creates tight coupling | [MEDIUM] | Use dedicated SMS result concept in migration rather than writing back to Subscriber |
| Language="TH" hardcoded default | [LOW] | Verify SMS Gateway supports other language codes |

---

## §18 Full Source Code

```java
// Rule: Rules.OMConsumers.OMXFM.Request.Request_SMSGATEWAY_SEND_SMS
// Author: awalia-t420 | ~1050 lines | 288.7 KB

declare:
  orderRequest : Concepts.OrderRequest.OrderRequest
  orderCurrentActivity : Concepts.OrderCurrentActivity
  nextAct : Concepts.ProcessActivity

when:
  orderCurrentActivity.ActivityID == "SMSGATEWAY_SEND_SMS"

then:
  // ─── Loop 1: ChildOU Subscriber (lines 27–507) ───
  for( int i=0 ; i<ParentOU@length ; i++ ) {
    for( int k=0 ; k<ChildOU@length ; k++ ) {
      for( int j=0 ; j<Subscriber@length ; j++ ) {
        String refId = subscriber.RefId;
        // ResSuccess check, GetXMLForSubscriber, PreExecCheck, offer classification...
        // For each qualifying offer → offerSMSType → send Variant ①
        /* XSLT Variant ①: see §9.8 — builds ns:SMSRequest with offerSMSType,
           offerEffDate, offerExpDate, rcPrice, permanentCreditLimit params */
        Event.Ext.sendEventImmediate(reqEvent);
        if(!isActResub) { orderCurrentActivity.RequestCount++; }
        isSkipped = false;
        if(RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
          /* Audit log event (gated). AUDIT_TRACE = "Request Sent for RefId" + refId */
          Event.Ext.sendEventImmediate(/* audit */);
        }
      }
    }
  }

  // ─── Loop 2: ParentOU Subscriber (lines 508–~1050) ───
  for( int i=0 ; i<ParentOU@length ; i++ ) {
    for( int j=0 ; j<Subscriber@length ; j++ ) {
      String refId = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].RefId;
      // Same ResSuccess / PreExecCheck / offer-classification logic
      if(orderType ∈ {3,69,70,11018} && qualifyingOffers) {
        /* XSLT Variant ②: ParentOU/Subscriber path; no offer-specific params */
        Event.Ext.sendEventImmediate(reqEvent);
        if(!isActResub) { orderCurrentActivity.RequestCount++; }
        /* Audit log — BUG: no AllowWriteLog gate here (always logs) */
        Event.Ext.sendEventImmediate(/* audit (unconditional) */);
      } else {
        /* XSLT Variant ③: PP-only; adds currPPDesc, currPPExp; PricePlan uses FUTPP */
        Event.Ext.sendEventImmediate(reqEvent);
        if(!isActResub) { orderCurrentActivity.RequestCount++; }
        if(RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
          Event.Ext.sendEventImmediate(/* audit (gated) */);
        }
      }
    }
  }
```

---

## §19 Response Message Rule

### §19.1 Overview

Parses SMS Gateway reply, creates `SMSGATEWAY_SendSMSRes` concept instance, gates audit logging via `AllowWriteLog`, writes response data back to the originating Subscriber concept, and drives fan-in completion.

**Unique features:** Both request AND response audit gated by `AllowWriteLog(OrderType)`. Response RF uniquely writes `ResponseCode`/`ResponseMsg` back to the Subscriber concept.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context for audit and Subscriber lookup |
| `eventResponse` | `Concepts.FM.Response.SMSGATEWAY_SendSMSRes` | Inbound response from SMS Gateway |
| `currActivity` | `Concepts.OrderCurrentActivity` | Provides RequestCount and Response array |
| `JMSCorrelationID` | String | Used to build Subscriber concept extId for writeback lookup |

### §19.3 ResponseBase Concept Construction

```text
createObject (Instance.createInstance("xslt://{{/Concepts/FM/Response/SMSGATEWAY_SendSMSRes}}"))
└── object
    ├── extId           ← OMXUtils.generateTrackingID()     [Always — explicit extId]
    ├── ResponseCode    ← $eventResponse/ResponseCode        [Always]
    ├── ResponseMessage ← $eventResponse/ResponseMessage     [Always]
    ├── CompletionStatus ← $eventResponse/CompletionStatus  [Always]
    └── ReferenceId     ← $eventResponse/ReferenceId        [Always]
```

### §19.4 Subscriber Concept Writeback

```java
Concepts.OrderRequest.OrderElements.Subscriber sub =
  Instance.getByExtIdByUri("SUB:" + JMSCorrelationID + ":" + RefID);
if(sub == null) {
  sub = Instance.getByExtIdByUri("CSUB:" + JMSCorrelationID + ":" + RefID);
}
if(sub != null) {
  sub.ResponseCode = eventResponse.ResponseCode;
  sub.ResponseMsg  = eventResponse.ResponseMsg;
}
```

The `CSUB:` fallback handles ChildOU Subscriber scenarios. Primary lookup uses `SUB:` (ParentOU Subscriber path).

### §19.5 Response Completion Logic

| Expression | Purpose |
|-----------|---------|
| `successResponseCount = XPath.evalAsInt("count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = '000'])")` | Count successful responses |
| `currActivity.RequestCount == successResponseCount` | Fan-in complete |

When fan-in condition met → orchestrator moves activity to COMPLETED.

### §19.6 Response Audit Logging

> **Unique:** Response audit is gated by `AllowWriteLog(OrderType)`. No other OMXFM response RF applies this gate.

| Audit field | Value |
|------------|-------|
| PROCESS_ID | `concat(pid, "_RES")` |
| OPERATION_NAME | `"SMSGATEWAY_SEND_SMS"` |
| AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` — space present |
| payload | Conditional on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
