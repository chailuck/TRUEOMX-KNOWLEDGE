# Request_OMX_EXP_FUT_RELATED_OFFER

> Creates a future-expire order (EXPSOC) per RelatedOffer within each SubscriberOffer — the most deeply nested fan-out in the process (4 levels: POU→Subscriber→SubscriberOffer→RelatedOffer). RefID is a composite triple key. Uses the shared OMX_ADD_FUTURE event. Contains a HIGH-severity copy-paste bug in the COU relatedFilter variable reference.

**Backend:** OMX (FutureSoc EXPSOC) | **Pattern:** Per-RelatedOffer (4-level nested) | **RefID:** subRefId:soc:relatedFilter | **forwardChain:** true | **Event:** OMX_ADD_FUTURE | **Used in step:** 79

---

## §1 — Overview & Purpose

Creates one **OMX_ADD_FUTURE** request (futureType=EXPSOC) per *related offer* within each subscriber offer — the deepest fan-out pattern in POSTPAID_ADD_OFFER_SUB. Loop hierarchy: ParentOU → Subscriber → SubscriberOffer → RelatedOffer (4 levels for POU; same for COU). The same backend event (`OMX_ADD_FUTURE`) is shared with OMX_EXP_FUT_OFFER but the fan-out key is at the RelatedOffer level.

- **Fan-out unit:** RelatedOffer within SubscriberOffer (4-level nested loop)
- **RefID (composite):** `subRefId + ":" + relatedOffer.Soc + ":" + relatedFilter`
- **filter:** parent offer's `ExtendedInfo[Name="FE_OR_CCBS"]/Value` — read via XPath.evalAsString per offer
- **relatedFilter:** related offer's `ExtendedInfo[Name="FE_OR_CCBS"]/Value` — read per related offer
- **Backend event:** `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` (shared with OMX_EXP_FUT_OFFER)
- **futureType:** `"EXPSOC"` — hardcoded
- **subType dispatch:** CUG_IND→CUG, TR_CONTRACT_IND→CONTRACT, TR_IDD_FLAG→IDD, TR_IR_FLAG→IR, ServiceType=68→DISCOUNT, default→EXPSOC
- **accountSubtype:** cross-referenced from `Account[AgreementRefId = POU Agreement RefId]`
- **Response:** dedicated `OMX_AddFutureRes` concept; fan-in via RequestCount == successResponseCount

> **[HIGH] COU relatedFilter variable bug (line 130):** In the COU branch, the XPath expression for `relatedFilter` references `$psrof` (the POU loop variable) instead of `$csrof` (the current COU loop variable). Result: every COU subscriber gets an incorrect `relatedFilter` value. The composite `relatedRefId` for all COU subscribers is wrong. On resubmit, the dedup guard will never match prior COU responses, causing duplicate requests.

> **[MEDIUM] 4-level nested loop with XPath.evalAsString per offer+relatedOffer:** Each iteration calls `XPath.evalAsString` twice before even reaching the PreExecCheck. In orders with many subscribers and offers, this creates significant CPU overhead in the BE engine.

> **[INFO] Shared event OMX_ADD_FUTURE with OMX_EXP_FUT_OFFER:** The distinction is the composite RefID (relatedOffer-level) vs subscriber/offer-level in OMX_EXP_FUT_OFFER.

> **[INFO] requestedDate captured once before loops:** `DateTime.now()` called once. All related offers in the same BE rule firing share the same timestamp.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_OMX_EXP_FUT_RELATED_OFFER.rule` | 182 lines |
| Author | (not specified) | No @author tag |
| Priority | 5 | |
| forwardChain | true | |
| Backend event | `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` | Shared with OMX_EXP_FUT_OFFER |
| Payload root | `ns3:futureOrderWithSoc → ns:futureOrder + ns2:futureSocs` | |
| Schema NS (ns) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrder.xsd` | futureOrder block |
| Schema NS (ns2) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureSoc.xsd` | futureSoc block |
| Schema NS (ns3) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FutureOrderWithSoc.xsd` | Wrapper |
| Fan-out unit | RelatedOffer per SubscriberOffer per Subscriber (4 levels) | Deepest fan-out in the process |
| RefID | `subRefId + ":" + relatedOffer.Soc + ":" + relatedFilter` | Composite triple key |
| filter | parent offer's ExtendedInfo[FE_OR_CCBS]/Value | Read via XPath.evalAsString per offer |
| relatedFilter | related offer's ExtendedInfo[FE_OR_CCBS]/Value | [HIGH] COU uses wrong variable ($psrof not $csrof) |
| Resub guard | `Response[ReferenceId == relatedRefId && CompletionStatus==2]` | Per related offer |
| PurgePendingRequestsBeforeResubmit | ABSENT | |
| POU PreExecCheck helper | `GetXMLForSubscriberRelatedOfferFilterWithExtendedInfo` | args: orderRequest, pSubRefId, offer.Soc, filter, psrof.Soc, relatedFilter |
| COU PreExecCheck helper | `GetXMLForSubscriberRelatedOfferInChildOUFilterWithExtendedInfo` | adds pOuRefId |
| requestedDate | DateTime.now() — captured before loops | All offers share same timestamp |
| requestedBy | OrderData.Channel | |
| futureType | "EXPSOC" | Hardcoded |
| orderType | 4 | Hardcoded |
| status | 1 | Hardcoded |
| nodeLevel | 5 (subscriber) | Hardcoded |
| UserName/Password | Gated on $orderRequest/OrderData/User | Standard — NOT IsEnableUserPass global var |
| OPERATION_NAME (request) | `"OMX_EXP_FUT_RELATED_OFFER"` | Matches rule name |
| Response concept | `Concepts.FM.Response.OMX_AddFutureRes` | Dedicated; shared with OMX_EXP_FUT_OFFER |
| extId in response | `OMXUtils:generateTrackingID()` called in XSLT | Not pre-generated |
| Fan-in | `RequestCount == successResponseCount` | ResponseCode suffix "000" |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_EXP_FUT_RELATED_OFFER"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_EXP_FUT_RELATED_OFFER"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §6 — ns2:subType Dispatch Logic

| Condition (xsl:when) | ns2:subType | Business meaning |
|---------------------|-------------|-----------------|
| `tib:index-of(SocProperties, 'CUG_IND=Y') > 0` | `"CUG"` | Closed User Group |
| `tib:index-of(SocProperties, 'TR_CONTRACT_IND=Y') > 0` | `"CONTRACT"` | Contract offer |
| `tib:index-of(SocProperties, 'TR_IDD_FLAG=Y') > 0` | `"IDD"` | International Direct Dialling |
| `tib:index-of(SocProperties, 'TR_IR_FLAG=Y') > 0` | `"IR"` | International Roaming |
| `ServiceType = '68'` | `"DISCOUNT"` | Discount offer type |
| otherwise | `"EXPSOC"` | Default — plain expire SOC |

Conditions are evaluated in order — first match wins.

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

Two variants: POU (params: $psrof, $pSubId) and COU (params: $csrof, $cSubId). Payload structure is structurally identical.

```text
createEvent
└── event
    ├── JMSPriority         ← $orderRequest/OrderPriority                      [Conditional]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId             [Conditional]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                   [Conditional]
    ├── RefID               ← $relatedRefId (subRefId:soc:relatedFilter)        [Always]
    ├── UserName            ← $orderRequest/OrderData/User                      [Conditional]
    ├── PassWord            ← $orderRequest/OrderData/Password                  [Conditional]
    ├── OrderType           ← $orderRequest/OrderData/OrderType                 [Conditional]
    └── payload
        └── ns3:futureOrderWithSoc
            ├── ns:futureOrder
            │   ├── ns:effectiveDate    ← psrof/ExtendedInfo[EXP_DATE_VALUE]/Value  [Conditional]
            │   ├── ns:status           ← 1                                          [Always, hardcoded]
            │   ├── ns:orderType        ← 4                                          [Always, hardcoded]
            │   ├── ns:nodeLevel        ← 5 (subscriber)                             [Always, hardcoded]
            │   ├── ns:nodeId           ← $pSubId / $cSubId                          [Always]
            │   ├── ns:requestedDate    ← $requestedDate (DateTime.now() pre-loop)   [Always]
            │   ├── ns:requestedBy      ← $requestedBy (Channel)                     [Always]
            │   ├── ns:dealerCode       ← $orderRequest/OrderData/DealerCode          [Conditional]
            │   ├── ns:activityReason   ← $actReason                                 [Conditional]
            │   ├── ns:extendedInfo[POU_ID]  ← $pOuId                               [Conditional: tib:trim > 0]
            │   ├── ns:extendedInfo[CUS_ID]  ← $custId                              [Conditional: tib:trim > 0]
            │   ├── ns:extendedInfo[SUB_ID]  ← $pSubId / $cSubId                    [Conditional: tib:trim > 0]
            │   ├── ns:extendedInfo[MOBILE_NO] ← $msisdn                            [Conditional: tib:trim > 0]
            │   ├── ns:fromOrderId      ← $orderRequest/OrderData/OrderID            [Conditional]
            │   ├── ns:userText         ← $userText                                  [Conditional]
            │   ├── ns:customerType     ← OMXUtils:asciiCodeToText(CustomerTypeInfo/Type) [Conditional]
            │   ├── ns:accountSubtype   ← Account[AgreementRefId=POU[$p+1]/Agreement/RefId]/
            │   │                         AccountManagementInfo/AccountSubType        [Always]
            │   └── ns:futureType       ← "EXPSOC"                                  [Always, hardcoded]
            └── ns2:futureSocs
                └── ns2:futureSoc  [xsl:for-each select="$psrof" / "$csrof"]
                    ├── ns2:code        ← Soc                                         [Always]
                    ├── ns2:expireDate  ← ExtendedInfo[EXP_DATE_VALUE]/Value          [Conditional]
                    ├── ns2:instanceId  ← OfferInstanceId                             [Conditional]
                    ├── ns2:type        ← ServiceType                                 [Conditional]
                    ├── ns2:subType     ← CUG/CONTRACT/IDD/IR/DISCOUNT/EXPSOC        [Always, dispatch]
                    └── ns2:socName     ← OfferName                                   [Always]
```

---

## §15 — Function Dependency Tree

```text
Request_OMX_EXP_FUT_RELATED_OFFER (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── requestedDate = DateTime.now()              ← captured ONCE before all loops
├── requestedBy = OrderData.Channel
├── custId = OrderData.Customer.CustomerId
├── [POU loop p → ps → psof → r]:
│   ├── filter = XPath.evalAsString($offer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── relatedFilter = XPath.evalAsString($psrof/ExtendedInfo[FE_OR_CCBS]/Value)  ← CORRECT
│   ├── relatedRefId = pSubRefId + ":" + psrof.Soc + ":" + relatedFilter
│   ├── [Resub guard]: Response[ReferenceId==relatedRefId && CompletionStatus==2]
│   └── [if !reqSuccess && chkRes=="true"]:
│       ├── reqEvent = Event.createEvent(OMX_ADD_FUTURE, XSLT POU variant)
│       ├── Event.Ext.sendEventImmediate(reqEvent)
│       └── RequestCount++ / Logger
├── [COU loop p → c → cs → csof → r]:
│   ├── filter = XPath.evalAsString($offer/ExtendedInfo[FE_OR_CCBS]/Value)
│   ├── relatedFilter = XPath.evalAsString($psrof/...)  ← [HIGH BUG] should be $csrof
│   ├── relatedRefId = cSubRefId + ":" + csrof.Soc + ":" + relatedFilter  ← WRONG value
│   └── [same send pattern, COU XSLT variant]
├── [if !isSkipped]: Status = "1"; SendDataToDB
├── [else]: SkipActivity("4")
└── [catch]: HandleActivityException

Response_OMX_EXP_FUT_RELATED_OFFER (rulefunction)
├── resEvent = Instance.createInstance(OMX_AddFutureRes)
│   └── @extId ← OMXUtils:generateTrackingID() (in XSLT)
├── currActivity.Response[] ← resEvent
├── Logger: OPERATION_NAME="OMX_EXP_FUT_RELATED_OFFER"
├── successResponseCount = count(Response[tib:right(tib:trim(ResponseCode),3)="000"])
└── return (RequestCount == successResponseCount) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-RelatedOffer fan-out: 4-level nested loop (POU→Subscriber→SubscriberOffer→RelatedOffer, plus COU branch). |
| R2 | RefID = composite triple key: subRefId + ":" + relatedOffer.Soc + ":" + relatedFilter. |
| R3 | filter = parent offer's ExtendedInfo[FE_OR_CCBS]/Value; relatedFilter = related offer's ExtendedInfo[FE_OR_CCBS]/Value. |
| R4 | PreExecCheck uses dedicated helpers with all 5-6 keys. |
| R5 | futureType="EXPSOC"; orderType=4; status=1; nodeLevel=5 (all hardcoded). |
| R6 | ns2:subType dispatch: CUG_IND=Y→CUG, TR_CONTRACT_IND=Y→CONTRACT, TR_IDD_FLAG=Y→IDD, TR_IR_FLAG=Y→IR, ServiceType=68→DISCOUNT, default→EXPSOC. |
| R7 | accountSubtype cross-referenced: Account[AgreementRefId=ParentOU[$p+1]/Agreement/RefId]/AccountManagementInfo/AccountSubType. |
| R8 | customerType = OMXUtils:asciiCodeToText(CustomerTypeInfo/Type) (conditional). |
| R9 | effectiveDate from RelatedOffer.ExtendedInfo[EXP_DATE_VALUE]/Value (conditional per related offer). |
| R10 | Fan-in: RequestCount == count(Response[tib:right(tib:trim(ResponseCode),3)="000"]). |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| COU relatedFilter reads $psrof (POU var) instead of $csrof — incorrect composite RefID; resubmit dedup fails for all COU subscribers | [HIGH] | Fix line 130: change `$psrof/ExtendedInfo[Name="FE_OR_CCBS"]/Value` to `$csrof/ExtendedInfo[Name="FE_OR_CCBS"]/Value` |
| 4-level nested loop with XPath.evalAsString per iteration — CPU overhead | [MEDIUM] | Cache FE_OR_CCBS values into local BE variables; avoid repeated XPath.evalAsString inside inner loops |
| accountSubtype uses $p (POU index) even in COU XSLT — may resolve to wrong account | [MEDIUM] | Verify COU XSLT uses correct POU index for account cross-reference |
| No PurgePendingRequestsBeforeResubmit — combined with COU RefID bug, duplicate sends on resubmit | [LOW] | Add PurgePendingRequestsBeforeResubmit once COU RefID bug is fixed |

---

## §19 — Response Message Rule (Response_OMX_EXP_FUT_RELATED_OFFER)

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Order context |
| eventResponse | Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE | Backend response |
| currActivity | Concepts.OM.ProcessConfig.Activity | Activity state & response list |

### §19.3 OMX_AddFutureRes Construction

```text
createObject
└── object (Concepts.FM.Response.OMX_AddFutureRes)
    ├── @extId           ← OMXUtils:generateTrackingID() (called in XSLT)   [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode                        [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg                         [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus                    [Conditional]
    └── ReferenceId      ← $eventResponse/RefID                               [Conditional]
```

### §19.4 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Write-back | None |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
