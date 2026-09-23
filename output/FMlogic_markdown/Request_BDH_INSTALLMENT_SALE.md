# Request_BDH_INSTALLMENT_SALE

> Registers an installment sale contract with BDH per subscriber. Sends one InstallmentSaleReq per POU/COU subscriber containing the contract offer (TR_CONTRACT_IND=Y) and its CT_INST related offer details.

**Backend:** BDH (InstallmentSale) | **Pattern:** Per-subscriber fan-out | **RefID:** bare subRefId (conditional) | **forwardChain:** true | **Author:** CHAYATORN-PC | **Used in step:** 73

---

## §1 — Overview & Purpose

Sends one **BDH InstallmentSaleReq** per subscriber (POU and COU). The payload registers a device installment sale contract with BDH, linking the subscriber's MSISDN/SubscriberId to their contract offer (`TR_CONTRACT_IND=Y`) and its CT_INST installment-type related offer.

- **Fan-out:** per subscriber — one request per POU subscriber, one per COU subscriber
- **RefID:** bare `subRefId` (POU: `$psub/RefId`, COU: `$csub/RefId`) — conditionally emitted via `xsl:if`
- **Offer filter:** `SubscriberOffers[TR_CONTRACT_IND=Y]` → `RelatedOffersArray[TR_OFFER_GROUP=CT_INST]`
- **AccountNo:** cross-referenced via `Account[RefId=$sub/AccountRefId]/AccountID`
- **Response:** standard ResponseBase — no write-back; also updates `currActivity.ResponseCode/ResponseMessage`

> **[INFO] Commented-out batch design (lines 123–136):** The original implementation (commented out) would have batched all subscribers from an OU into a single `InstallmentSaleReq` with a `for-each` loop, using `pOuRefId` as RefID. The active code sends one request per subscriber instead. The dead code references the `arrLstSubs` ArrayList that is still constructed (but never populated) at the top of the rule body.

> **[LOW] No Parameter guard:** No upfront `if(Parameter@length == 0)` check. This FM uses no ProcessConfig Parameters, so this has no functional impact.

> **[LOW] No PurgePendingRequestsBeforeResubmit:** Verify BDH idempotency for duplicate InstallmentSale registrations on the same subscriber.

> **[LOW] arrLstSubs created but never used:** `Object arrLstSubs = Collections.List.createArrayList()` at line 30 — a holdover from the batch design. Safe to remove.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_BDH_INSTALLMENT_SALE.rule` | 150 lines (incl. commented-out batch block) |
| Rule namespace | `Rules.OMConsumers.OMXFM.Request` | |
| Response rulefunction | `Response_BDH_INSTALLMENT_SALE.rulefunction` | 32 lines — standard + activity-level ResponseCode update |
| Author | CHAYATORN-PC | |
| Priority | 5 | |
| forwardChain | true | |
| Backend event | `Events.OMConsumers.OMXFM.Request.BDH_INSTALLMENT_SALE` | Dedicated |
| Payload root | `ns1:InstallmentSaleReq` | BDH InstallmentSale schema |
| Schema NS (ns1) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/BDH/InstallmentSale.xsd` | |
| Fan-out pattern | Per-subscriber (POU + COU) | Standard per-sub pattern |
| RefID (POU) | `$psub/RefId` (conditional) | Emitted only if RefId is non-empty |
| RefID (COU) | `$csub/RefId` (conditional) | Same guard |
| Resub guard | `Response[ReferenceId == subRefId && CompletionStatus==2]` | Subscriber-level |
| event/@extId | `OMXUtils:generateTrackingID()` | Set in XSLT |
| Parameter guard | ABSENT | [LOW] Not needed — FM uses no Parameters |
| POU PreExecCheck builder | `GetXMLForSubscriber(orderRequest, pSubRefId)` | Subscriber-level |
| COU PreExecCheck builder | `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)` | Subscriber-level in ChildOU |
| Response write-back | None (ResponseBase only) | Also sets `currActivity.ResponseCode/ResponseMessage` |
| Resub purge | ABSENT | [LOW] No PurgePendingRequestsBeforeResubmit |
| OPERATION_NAME | `"BDH_INSTALLMENT_SALE"` | Hardcoded |
| Fan-in | `RequestCount == successResponseCount` | success = ResponseCode suffix "000" |
| Dead code | Lines 123–136 (commented-out batch design) | [INFO] Safe to remove |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "BDH_INSTALLMENT_SALE"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "BDH_INSTALLMENT_SALE"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §8 — System & Integration Dependencies

### §8.3 Backend API Details

| Field | Value |
|-------|-------|
| System | BDH (Bundled Device/Hardware) |
| Operation | InstallmentSaleReq — register installment sale contract |
| Schema NS (ns1) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/BDH/InstallmentSale.xsd` |

### §8.5 ExtendedInfo Fields

| Name | Level | Direction | Purpose |
|------|-------|-----------|---------|
| TSM_ORDER_NO | OrderData | INPUT | `ns1:saleOrderId` — external TSM order reference (conditional) |
| devicePaymentType | Subscriber | INPUT | `ns1:saleDetails/ns1:devicePaymentType` (conditional) |

### §8.4 Offer Cross-Reference Logic

| Target Field | XPath Filter | Purpose |
|-------------|-------------|---------|
| ns1:productOfferingId/Name/Seq | `SubscriberOffers[TR_CONTRACT_IND=Y]/RelatedOffersArray[TR_OFFER_GROUP=CT_INST]` | CT_INST installment offer under the contract offer |
| ns1:mainProductOfferingId/Name/Seq | `SubscriberOffers[TR_CONTRACT_IND=Y]` | Contract offer itself (parent) |
| ns1:accountNo | `OrderData/Customer/Account[RefId=$sub/AccountRefId]/AccountID` | AccountID cross-referenced via subscriber's AccountRefId |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

POU uses `$psub`; COU uses `$csub` — payload structure identical. All offer XPath filters use `contains(SocProperties,"TR_CONTRACT_IND=Y")` and `contains(SocProperties,"TR_OFFER_GROUP=CT_INST")`.

```text
createEvent
└── event
    ├── @extId                  ← OMXUtils:generateTrackingID()                          [Always]
    ├── JMSPriority             ← $orderRequest/OrderPriority                            [Always]
    ├── JMSCorrelationID        ← $orderRequest/OrderData/OMXTrackingId                  [Always]
    ├── OrderID                 ← $orderRequest/OrderData/OrderID                        [Always]
    ├── RefID                   ← $psub/RefId (or $csub/RefId)                           [Conditional: xsl:if test="$psub/RefId"]
    ├── OrderType               ← $orderRequest/OrderData/OrderType                      [Always]
    └── payload
        └── ns1:InstallmentSaleReq  (ns1=.../BDH/InstallmentSale.xsd)
            └── ns1:saleInfoList
                ├── ns1:saleOrderId       ← OrderData/ExtendedInfo[TSM_ORDER_NO]/Value  [Conditional]
                ├── ns1:omxOrderId        ← OrderData/OMXTrackingId                     [Conditional]
                ├── ns1:accountNo         ← Account[RefId=$sub/AccountRefId]/AccountID  [Conditional]
                ├── ns1:subscriberNo      ← $sub/SubscriberId                           [Conditional]
                ├── ns1:productOfferingId ← SubscriberOffers[TR_CONTRACT_IND=Y]
                │                            /RelatedOffersArray[TR_OFFER_GROUP=CT_INST]/Soc [Conditional]
                ├── ns1:productOfferName  ← ...RelatedOffersArray[CT_INST]/OfferName    [Conditional]
                ├── ns1:productOfferingSeq← ...RelatedOffersArray[CT_INST]/OfferInstanceId [Conditional]
                └── ns1:saleDetails
                    ├── ns1:mainProductOfferingId  ← SubscriberOffers[TR_CONTRACT_IND=Y]/Soc  [Conditional]
                    ├── ns1:mainProductOfferingName← SubscriberOffers[TR_CONTRACT_IND=Y]/OfferName [Conditional]
                    ├── ns1:mainProductOfferingSeq ← SubscriberOffers[TR_CONTRACT_IND=Y]/OfferInstanceId [Conditional]
                    └── ns1:devicePaymentType      ← $sub/ExtendedInfo[devicePaymentType]/Value [Conditional]
```

---

## §15 — Function Dependency Tree

```text
Request_BDH_INSTALLMENT_SALE (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── arrLstSubs = Collections.List.createArrayList()   ← UNUSED (dead code from batch design)
├── [NOTE: NO Parameter guard / NO PurgePendingRequestsBeforeResubmit]
├── [POU loop p → ps]:
│   ├── [Resub guard]: Response[ReferenceId == pSubRefId && CompletionStatus==2]
│   ├── [PreExecCheck]: GetXMLForSubscriber(orderRequest, pSubRefId)
│   └── [if chkRes=="true"]:
│       ├── Event.createEvent(BDH_INSTALLMENT_SALE, XSLT: ns1:InstallmentSaleReq, RefID=$psub/RefId)
│       ├── Event.Ext.sendEventImmediate(reqEvent)
│       ├── isSkipped = false
│       ├── [if !isActResub]: RequestCount++
│       └── Logger: OPERATION_NAME="BDH_INSTALLMENT_SALE"
├── [COU loop p → c → cs]:
│   ├── [Resub guard]: Response[ReferenceId == cSubRefId && CompletionStatus==2]
│   ├── [PreExecCheck]: GetXMLForSubscriberInChildOU(cSubRefId, pOuRefId)
│   └── Event.createEvent(BDH_INSTALLMENT_SALE, XSLT: RefID=$csub/RefId)
├── [NOTE: Dead code block (commented-out): lines 123–136]
│   └── Original batch design: one request per OU with for-each over arrLstSubs
├── [if !isSkipped]: SendDataToDB / SkipActivity
└── [catch]: HandleActivityException

Response_BDH_INSTALLMENT_SALE (rulefunction)
├── activityRes = Instance.createInstance(ResponseBase){extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId}
├── currActivity.Response[] ← activityRes
├── currActivity.ResponseCode ← eventResponse.ResponseCode   ← activity-level update
├── currActivity.ResponseMessage ← eventResponse.ResponseMsg ← activity-level update
├── Logger: OPERATION_NAME="BDH_INSTALLMENT_SALE"
├── successResponseCount = count(Response[tib:right(tib:trim(ResponseCode),3)="000"])
└── return (RequestCount == successResponseCount) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-subscriber fan-out across POU and COU. One InstallmentSaleReq per subscriber. |
| R2 | RefID = bare subRefId (conditional via xsl:if — omitted if subscriber RefId is empty). |
| R3 | Offer lookup: `SubscriberOffers[TR_CONTRACT_IND=Y]` for main contract; `RelatedOffersArray[TR_OFFER_GROUP=CT_INST]` for installment offer. |
| R4 | AccountNo cross-referenced: `Account[RefId=$sub/AccountRefId]/AccountID`. |
| R5 | ns1:saleOrderId = OrderData/ExtendedInfo[TSM_ORDER_NO]/Value (conditional). |
| R6 | ns1:devicePaymentType = sub.ExtendedInfo[devicePaymentType]/Value (conditional). |
| R7 | Response handler also sets currActivity.ResponseCode and currActivity.ResponseMessage. |
| R8 | Fan-in: RequestCount == successResponseCount (ResponseCode suffix "000"). |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Dead code block (batch design, lines 123–136) still in source | [LOW] | Remove commented-out batch XSLT block and arrLstSubs declaration |
| No PurgePendingRequestsBeforeResubmit | [LOW] | Verify BDH InstallmentSale idempotency for duplicate calls on same subscriber |
| CT_INST/TR_CONTRACT_IND XPath may match multiple offers | [LOW] | Confirm only one TR_CONTRACT_IND=Y offer per subscriber; add qualifier if multiple possible |

---

## §19 — Response Message Rule (Response_BDH_INSTALLMENT_SALE)

### §19.3 ResponseBase Construction

```text
createObject
└── object (Concepts.FM.Base.ResponseBase)
    ├── @extId           ← activityRes/@extId (pre-generated)   [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode           [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg            [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus       [Conditional]
    └── ReferenceId      ← $eventResponse/RefID                  [Conditional]

Additional (outside ResponseBase):
    currActivity.ResponseCode    ← eventResponse.ResponseCode
    currActivity.ResponseMessage ← eventResponse.ResponseMsg
```

### §19.4 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Write-back | None |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
