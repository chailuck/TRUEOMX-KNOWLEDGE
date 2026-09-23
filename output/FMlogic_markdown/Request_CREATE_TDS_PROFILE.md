# Request_CREATE_TDS_PROFILE

TIBCO BusinessEvents FM Logic — TDS Trade-in Contract Profile Creation (Two-Phase Offer Filtering)

**Priority:** 5 | **ForwardChain:** true | **Backend:** TDS (Trade-in Device Service) | **Dispatch:** sendEventImmediate (parallel) | **Author:** warawich-nb

---

## §1 — Overview & Purpose

This rule creates TDS (Trade-in Device Service) profiles for subscribers that have active trade-in contracts. It applies a **two-phase offer selection algorithm**: first identifying parent offers with valid TR contract data, then expanding to their related offers where `TR_CONTRACT_IND=Y`. One `CREATE_TDS_PROFILE` event is dispatched per subscriber carrying the full array of qualifying offers.

Unlike SBM FMs which process one offer at a time (IntraActivitySequencing), this FM dispatches all subscriber events in parallel via `Event.Ext.sendEventImmediate` and uses `RequestCount++` for fan-in tracking — but the response rulefunction always returns `"true"` unconditionally, breaking the fan-in logic.

> **[HIGH] Critical — Unconditional Response Fan-in:** The response rulefunction always returns `"true"` immediately without checking `currActivity.RequestCount == successResponseCount`. If 3 subscribers trigger 3 dispatches (RequestCount=3), the activity advances to the next step on the FIRST response, ignoring the remaining 2 responses. Fix: Add fan-in check identical to other FMs.

> **[MEDIUM] Dead Variable — bussinessLine (typo):** `String bussinessLine = "MOBILE";` is declared but never used. The XSLT uses `$ouId` (the ParentOU.OUId) as the `businessLine` event field — not "MOBILE".

> **[MEDIUM] Empty COU Loop:** Lines 201–208 iterate ChildOU subscribers but the loop body is empty. COU subscribers receive no TDS profile creation.

> **[LOW] System.debugOut in Production:** Multiple `System.debugOut` calls remain at lines 114, 120, 121, 130, 131 — these produce console output in production.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CREATE_TDS_PROFILE` |
| Author | warawich-nb |
| Priority | 5 |
| ForwardChain | true |
| Target backend | TDS — Trade-in Device Service (TDS Profile API) |
| Request event type | `Events.OMConsumers.OMXFM.Request.CREATE_TDS_PROFILE` |
| Response event type | `Events.OMConsumers.OMXFM.Response.CREATE_TDS_PROFILE` |
| Response concept | `Concepts.FM.Response.CreateTDSProfileRes` (not ResponseBase or SBM_DoServiceRes) |
| Dispatch method | `Event.Ext.sendEventImmediate` (parallel) |
| Fan-out granularity | Per subscriber (one event carrying full qualifying offers array) |
| Fan-in mechanism | Response rulefunction always returns "true" — unconditional **[HIGH BUG]** |
| RequestCount tracking | `orderCurrentActivity.RequestCount++` — only if `!isActResub` |
| Offer selection phase 1 | Parent SubscriberOffers with ORIGINAL_TR_CONTRACT_TERM > 0, valid ORIG_CONTRACT_EXPIRE_DATE, ORIGINAL_TR_CONTRACT_FEE > 0 |
| Offer selection phase 2 | RelatedOffersArray where TR_CONTRACT_IND=Y, not duplicate, TR_CONTRACT_TERM ParameterInfo > 0, expiry future, TR_CONTRACT_FEE > 0 |
| Resubmit skip key | `subscriber.RefId` only (not composite) — may be too broad |
| COU support | Empty loop — no COU subscriber processing |
| Audit log gate | Unconditional |
| Skip trigger | No qualifying subscribers → SkipActivity("4") |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order; subscriber and offer data |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current process step; Response[], Status, RequestCount |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches activity to order's next step |
| 2 | `orderCurrentActivity.ActivityID == "CREATE_TDS_PROFILE"` | FM identity |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CREATE_TDS_PROFILE"` | ProcessFlow routing |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be waiting |

---

## §5 — Execution Flow Diagram

1. Compute `isActResub`; if true → `PurgePendingRequestsBeforeResubmit`; declare dead variable `bussinessLine="MOBILE"`
2. **POU loop**: iterate ParentOU[i]
3. Build `ouName` (dead variable) from CustomerName.FirstName+LastName; read `ouId = ParentOU[i].OUId`
4. **Subscriber loop**: iterate ParentOU[i].Subscriber[j]
5. Read `account_refId = subscriber.AccountRefId`
6. **Phase 1 — Offer loop**: iterate SubscriberOffers[o]
7. Read FE_OR_CCBS filter; compute `chkTR_CONTRACT_TERM`, `chkTR_ORIG_CONTRACT_EXPIRE_DATE`, `TR_CONTRACT_FEE`; parse `expDateCal` from ORIG_CONTRACT_EXPIRE_DATE
8. Resubmit skip: `Response[ReferenceId==subscriber.RefId and CompletionStatus==2]`
9. If `!reqSuccess AND chkTR_CONTRACT_TERM AND logicalDate < expDateCal AND TR_CONTRACT_FEE > 0`: run PreExecCheck; if true → add offer to `addSubOffers`
10. **Phase 2 — Related Offer loop**: for each qualifying parent offer, iterate its RelatedOffersArray
11. Skip if TR_CONTRACT_IND=Y not in SocProperties; skip duplicates via iterator scan of addSubOffers
12. Check `relate_chkTR_CONTRACT_TERM`, `relate_TR_ORIG_CONTRACT_EXPIRE_DATE`, `relate_TR_CONTRACT_FEE` from ParameterInfo
13. If conditions met: map relateOffer to SubscriberOffers concept → add to addSubOffers
14. **Dispatch**: if `addSubOffersArray.length > 0` → create & `sendEventImmediate` CREATE_TDS_PROFILE event; `RequestCount++` (if !isActResub)
15. Emit audit log (unconditional)
16. **COU loop**: iterate ChildOU subscribers — empty body (stub)
17. Status="1", SendDataToDB; or SkipActivity("4")

---

## §6 — Rule Action (THEN) — Two-Phase Offer Filtering Detail

### §6.1 — Phase 1 — Parent SubscriberOffers Filter

| Condition | Source / XPath | Purpose |
|-----------|----------------|---------|
| !reqSuccess | `Response[ReferenceId==subscriber.RefId and CompletionStatus==2]` | Resubmit skip (subscriber-level key) |
| chkTR_CONTRACT_TERM | `exists($subOff/ExtendedInfo[Name="ORIGINAL_TR_CONTRACT_TERM"]) and value > 0` | Has a valid TR contract term |
| logicalDate < expDateCal | `ORIGINAL_TR_ORIG_CONTRACT_EXPIRE_DATE` parsed as `yyyy-MM-dd'T'HH:mm:ss` | Contract not yet expired |
| TR_CONTRACT_FEE > 0 | `$subOff/ExtendedInfo[Name="ORIGINAL_TR_CONTRACT_FEE"]/Value` | Has a positive contract fee |
| PreExecCheck | `GetXMLForSubscriberOfferFilterWithExtendedInfo(..., filter)` | FE_OR_CCBS-gated eligibility check |

> If `ORIGINAL_TR_ORIG_CONTRACT_EXPIRE_DATE` is present but its date string cannot be split, the offer loop hits a `continue` statement (skips the offer silently).

### §6.2 — Phase 2 — RelatedOffersArray Filter

| Condition | Source | Purpose |
|-----------|--------|---------|
| TR_CONTRACT_IND=Y in SocProperties | `contains($relateOffer/SocProperties, 'TR_CONTRACT_IND=Y')` | Related offer is a TR contract offer |
| Not duplicate in addSubOffers | Iterator scan — `itrSubOffer.OfferName == relateOffer.OfferName` | Prevents adding same offer twice |
| relate_chkTR_CONTRACT_TERM | `exists($relateOffer/ParameterInfo[ParamName="TR_CONTRACT_TERM"]) and ValuesArray > 0` | Related offer has TR contract term |
| relate_logicalDate < relate_expDateCal | `TR_ORIG_CONTRACT_EXPIRE_DATE ParameterInfo` parsed | Related contract not expired |
| relate_TR_CONTRACT_FEE > 0 | `TR_CONTRACT_FEE ParameterInfo ValuesArray`; fallback: `CONTRACT_FEE ParameterInfo` | Positive fee — two-key lookup |
| No PreExecCheck (commented out) | Lines 162–165 in source — disabled | Related offer PreExecCheck is commented out |

### §6.3 — RelatedOffer → SubscriberOffers Mapping

| Target field | Source |
|-------------|--------|
| OfferName | `$relateOffer/OfferName` |
| Soc | `$relateOffer/Soc` |
| OfferInstanceId | `$relateOffer/OfferInstanceId` |
| ParameterInfo[] (all) | `$relateOffer/ParameterInfo` — clones each with ParamName, ValuesArray, EffectiveDate, ExpirationDate, OfferInstanceId, ExtendedInfo |
| ExtendedInfo[] (all) | `$relateOffer/ExtendedInfo` |

---

## §7 — Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| bussinessLine (dead) | `"MOBILE"` (static) | Declared but NEVER used — typo in var name [MEDIUM] |
| ouName (dead) | `CustomerName.FirstName + " " + LastName` | Built but NEVER passed to XSLT [LOW] |
| ouId | `orderRequest.OrderData.Customer.ParentOU[i].OUId` | Passed as $ouId → used as `businessLine` in event |
| refId | `subscriber.RefId` | RefID in JMS header; resubmit skip key |
| account_refId | `subscriber.AccountRefId` | Used to look up Account[RefId=$account_refId]/AccountID in XSLT |
| addSubOffersArray | ArrayList built from Phase 1 + Phase 2 qualifying offers | Passed to XSLT as array param; iterated in payload |
| ORIGINAL_TR_CONTRACT_TERM | `subOff/ExtendedInfo[Name="ORIGINAL_TR_CONTRACT_TERM"]/Value` | Phase 1 gate: must exist and > 0 |
| ORIGINAL_TR_ORIG_CONTRACT_EXPIRE_DATE | `subOff/ExtendedInfo[Name="ORIGINAL_TR_ORIG_CONTRACT_EXPIRE_DATE"]/Value` | Phase 1: parsed to DateTime; must be future |
| ORIGINAL_TR_CONTRACT_FEE | `subOff/ExtendedInfo[Name="ORIGINAL_TR_CONTRACT_FEE"]/Value` | Phase 1 gate: > 0; also used in XSLT ns:type |
| relate_TR_CONTRACT_TERM | `relateOffer/ParameterInfo[ParamName="TR_CONTRACT_TERM"]/ValuesArray` | Phase 2 gate: must exist and > 0 |
| relate_TR_ORIG_CONTRACT_EXPIRE_DATE | `relateOffer/ParameterInfo[ParamName="TR_ORIG_CONTRACT_EXPIRE_DATE"]/ValuesArray` | Phase 2: parsed to DateTime; must be future |
| relate_TR_CONTRACT_FEE | `relateOffer/ParameterInfo[ParamName="TR_CONTRACT_FEE"]/ValuesArray` or `CONTRACT_FEE` | Phase 2 gate: > 0; two-key lookup |

---

## §8 — System & Integration Dependencies

### §8.1 — ESB / JMS Channel Dependencies

| Direction | Event Type | Dispatch |
|-----------|------------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CREATE_TDS_PROFILE` | `Event.Ext.sendEventImmediate` (parallel) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `Event.Ext.sendEventImmediate` — unconditional |

### §8.2 — Backend API Details

| System | API | Schema NS |
|--------|-----|-----------|
| TDS (Trade-in Device Service) | getContractDetail / searchList | `http://services.omx.truecorp.co.th/OSBGetOfferReferenceRequest` |

### §8.3 — ExtendedInfo Fields Required

| Name | Level | Required/Optional | Where Used |
|------|-------|-------------------|-----------|
| FE_OR_CCBS | Offer | Optional | Phase 1 filter → passed to PreExecCheck helper |
| ORIGINAL_TR_CONTRACT_TERM | Offer | Required for phase 1 | Phase 1 gate: must exist and value > 0 |
| ORIGINAL_TR_ORIG_CONTRACT_EXPIRE_DATE | Offer | Required for phase 1 | Phase 1 gate: expiry date future check |
| ORIGINAL_TR_CONTRACT_FEE | Offer | Required for phase 1 | Phase 1 gate: > 0; also used in XSLT ns:type field |

### §8.4 — ParameterInfo Fields (Related Offers)

| ParamName | Required/Optional | Where Used |
|-----------|-------------------|-----------|
| TR_CONTRACT_TERM | Required for phase 2 | Phase 2 gate: > 0 |
| TR_ORIG_CONTRACT_EXPIRE_DATE | Required for phase 2 | Phase 2 gate: expiry date future check |
| TR_CONTRACT_FEE | Required for phase 2 (or CONTRACT_FEE fallback) | Phase 2 gate: > 0 |
| CONTRACT_FEE | Fallback for TR_CONTRACT_FEE | Phase 2 gate when TR_CONTRACT_FEE absent |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Notes |
|------------|------------|-------|
| `$orderRequest` | orderRequest concept | Root order |
| `$refId` | subscriber.RefId | RefID in JMS header |
| `$subscriber` | Subscriber concept | MSISDN, ResourceInfo[IMSI/SIM/MSISDN], AccountRefId |
| `$ouId` | ParentOU[i].OUId | Used as `businessLine` event field |
| `$account_refId` | subscriber.AccountRefId | Used to look up accountId in XSLT |
| `$addSubOffersArray` | Array of qualifying SubscriberOffers (Phase 1 + 2) | Iterated in ns:searchList |

### §9.2 — Event Header Fields (Extended — Unique to CREATE_TDS_PROFILE)

| Field | Source | Condition |
|-------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | Conditional |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| OrderID | `$orderRequest/OrderData/OrderID` | Conditional |
| **RefID** | `$refId` (subscriber.RefId) | **Always** |
| OrderType | `$orderRequest/OrderData/OrderType` | Conditional |
| **CES** | `$orderRequest/OrderData/CES` | Conditional — unique to TDS events |
| **primResourceValue** | `$subscriber/MSISDN` | Conditional |
| **businessLine** | `$ouId` (ParentOU.OUId — NOT "MOBILE") | **Always** |
| **IMSI** | `$subscriber/ResourceInfo[ResourceName='IMSI']/ValuesArray` | Conditional |
| **SIM** | `$subscriber/ResourceInfo[ResourceName='SIM']/ValuesArray` | Conditional |
| **MSISDN** | `$subscriber/ResourceInfo[ResourceName='MSISDN']/ValuesArray` | Conditional |
| **OperatorId** | `$orderRequest/OrderData/OperatorId` | Conditional |
| **dealerCode** | `$orderRequest/OrderData/DealerCode` | Conditional |
| **ActvCode** | `$subscriber/SubscriberActivityInfo/ActivityReason` | Conditional |
| **channel** | `$orderRequest/OrderData/Channel` | Conditional |
| **subscriberNumber** | `$subscriber/SubscriberId` | Conditional |
| **customerType** | `$orderRequest/OrderData/Customer/CustomerTypeInfo/Type` | Conditional |
| **accountId** | `$orderRequest/OrderData/Customer/Account[$account_refId=RefId]/AccountID` | **Always** |
| **language** | `$subscriber/SubscriberGeneralInfo/Language` | Conditional |

### §9.3 — Payload: ns:getContractDetail/ns:searchList

Iterates `$addSubOffersArray/elements`. For each offer element:

| Field | Logic |
|-------|-------|
| `ns:type` | If `subscriber/SubscriberOffers[OfferName=current()/OfferName]/ExtendedInfo[ORIGINAL_TR_CONTRACT_FEE]/Value` has length > 0 → `concat(OfferName, ',', that_fee)`; else → `concat(OfferName, ',', RelatedOffersArray[OfferName=current()]/ParameterInfo[TR_CONTRACT_FEE]/ValuesArray)` |
| `ns:value` | `Soc` (conditional: if present) |
| `ns:offerInstanceId` | `OfferInstanceId` (conditional: if present) |

> The `ns:type` field is a composite string: `"OfferName,ContractFee"`. It first tries ORIGINAL_TR_CONTRACT_FEE (from parent offer's ExtendedInfo); if empty, falls back to RelatedOffersArray TR_CONTRACT_FEE (for Phase 2 related offers).

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                    [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId          [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                [Conditional]
    ├── RefID                ← $refId (subscriber.RefId)                      [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType              [Conditional]
    ├── CES                  ← $orderRequest/OrderData/CES                    [Conditional]
    ├── primResourceValue    ← $subscriber/MSISDN                             [Conditional]
    ├── businessLine         ← $ouId (ParentOU.OUId — NOT "MOBILE")           [Always]
    ├── IMSI                 ← $subscriber/ResourceInfo[IMSI]/ValuesArray     [Conditional]
    ├── SIM                  ← $subscriber/ResourceInfo[SIM]/ValuesArray      [Conditional]
    ├── MSISDN               ← $subscriber/ResourceInfo[MSISDN]/ValuesArray   [Conditional]
    ├── OperatorId           ← $orderRequest/OrderData/OperatorId             [Conditional]
    ├── dealerCode           ← $orderRequest/OrderData/DealerCode             [Conditional]
    ├── ActvCode             ← $subscriber/SubscriberActivityInfo/ActivityReason [Conditional]
    ├── channel              ← $orderRequest/OrderData/Channel                [Conditional]
    ├── subscriberNumber     ← $subscriber/SubscriberId                       [Conditional]
    ├── customerType         ← $orderRequest/OrderData/Customer/CustomerTypeInfo/Type [Conditional]
    ├── accountId            ← Customer/Account[$account_refId=RefId]/AccountID [Always]
    ├── language             ← $subscriber/SubscriberGeneralInfo/Language     [Conditional]
    └── payload
        └── ns:getContractDetail
            └── ns:searchList
                └── ns:searchInfoArray  [xsl:for-each $addSubOffersArray/elements]
                    ├── ns:type          ← concat(OfferName, ',', ORIGINAL_TR_CONTRACT_FEE or RelatedOffer TR_CONTRACT_FEE) [Always]
                    ├── ns:value         ← Soc                               [Conditional]
                    └── ns:offerInstanceId ← OfferInstanceId                 [Conditional]
```

**Legend:**
- `[Always]` — unconditional, always emitted
- `[Conditional]` — inside `xsl:if`, only emitted when source value is non-empty
- XPath sources shown after `←`
- Static literals shown in quotes

---

## §11 — Audit Logging

| Phase | Field | Value |
|-------|-------|-------|
| Request | OPERATION_NAME | "CREATE_TDS_PROFILE" |
| Request | AUDIT_TRACE | "Request Sent for CREATE_TDS_PROFILE" |
| Request | payload | Conditional: WritePayload="true" |
| Response | AUDIT_TRACE | "Response received for CREATE_TDS_PROFILE" |

---

## §12 — Activity Status Management

| Transition | Code | Trigger |
|------------|------|---------|
| Running | "1" | At least one subscriber event dispatched |
| Skip | "4" | No qualifying subscribers (isSkipped=true) |
| Error | HandleActivityException | Any uncaught exception |

---

## §13 — Exception / Error Handling

`try { ... } catch (Exception ae) { HandleActivityException(...); }`

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears pending events on resubmission (called even though IntraActivitySequencing is NOT used for dispatch) |
| `BRMS.IsBlank(str)` | Null/blank check for CustomerName |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, soc, filter)` | Builds Phase 1 PreExecCheck XML |
| `Collections.List.createArrayList()` | Creates ArrayList for collecting qualifying offers |
| `Collections.add(list, item)` | Appends offer to ArrayList |
| `Collections.toArray(list)` | Converts ArrayList to array |
| `Collections.size(list)` | Gets ArrayList size for duplicate check |
| `Collections.iterator(list)` | Creates iterator for duplicate scan |
| `Collections.Iterator.hasNext(iter)` | Iterator advancement for duplicate check |
| `Collections.Iterator.next(iter)` | Gets next offer from iterator |
| `DateTime.now()` | Gets current date for expiry comparison |
| `DateTime.before(d1, d2)` | Checks d1 < d2 (logicalDate before expDateCal) |
| `DateTime.parseString(str, pattern)` | Parses ISO date string to DateTime |
| `String.substring(str, start, end)` | Splits date+time from ORIG_CONTRACT_EXPIRE_DATE string |
| `Instance.createInstance(xslt)` | Maps RelatedOffer to SubscriberOffers concept |
| `GetActivityStatusString("1", false)` | Returns "Running" status |
| `SendDataToDB(orderRequest)` | Persists state |
| `SkipActivity(..., "4")` | Skip handler |
| `HandleActivityException(...)` | Central exception handler |

---

## §15 — Function Dependency Tree

```text
Request_CREATE_TDS_PROFILE.rule
├── isActResub check
│   └── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity) [if isActResub]
├── bussinessLine = "MOBILE"  [DEAD VARIABLE — never used]
│
├── [POU loop: ParentOU[i]]
│   ├── ouName = FirstName + " " + LastName  [DEAD VARIABLE — never used]
│   ├── ouId = ParentOU[i].OUId
│   ├── [Subscriber loop: Subscriber[j]]
│   │   ├── account_refId = subscriber.AccountRefId
│   │   ├── addSubOffers = Collections.List.createArrayList()
│   │   │
│   │   ├── [Phase 1 — Offer loop: SubscriberOffers[o]]
│   │   │   ├── filter = XPath(ExtendedInfo[FE_OR_CCBS]/Value)
│   │   │   ├── chkTR_CONTRACT_TERM = XPath(exists + value > 0)
│   │   │   ├── chkTR_ORIG_CONTRACT_EXPIRE_DATE = XPath(count > 0)
│   │   │   ├── TR_ORIG_CONTRACT_EXPIRE_DATE = XPath(ExtendedInfo value)
│   │   │   ├── TR_CONTRACT_FEE = XPath(ExtendedInfo value)
│   │   │   ├── expDateCal = DateTime.parseString(ORIG_CONTRACT_EXPIRE_DATE, "yyyy-MM-dd'T'HH:mm:ss")
│   │   │   ├── reqSuccess check: Response[ReferenceId==subscriber.RefId and CompletionStatus==2]
│   │   │   ├── [if !reqSuccess AND chkTR_CONTRACT_TERM AND logicalDate < expDateCal AND TR_CONTRACT_FEE > 0]
│   │   │   │   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo(...)
│   │   │   │   └── Collections.add(addSubOffers, subOff)  [if chkRes=="true"]
│   │   │   │
│   │   │   └── [Phase 2 — RelatedOffersArray loop: per qualifying parent offer → relateOffer[k]]
│   │   │       ├── if NOT contains(SocProperties, "TR_CONTRACT_IND=Y") → continue
│   │   │       ├── duplicatePropo check via Collections.iterator scan (O(n^2))
│   │   │       ├── relate_chkTR_CONTRACT_TERM = XPath(ParameterInfo[TR_CONTRACT_TERM] > 0)
│   │   │       ├── relate_TR_ORIG_CONTRACT_EXPIRE_DATE = XPath(ParameterInfo[TR_ORIG_CONTRACT_EXPIRE_DATE])
│   │   │       ├── relate_TR_CONTRACT_FEE = XPath(ParameterInfo[TR_CONTRACT_FEE] or CONTRACT_FEE)
│   │   │       ├── relate_expDateCal = DateTime.parseString(...)
│   │   │       ├── relate_reqSuccess check: Response[ReferenceId==subscriber.RefId and CompletionStatus==2]
│   │   │       ├── [if !relate_reqSuccess AND all conditions met]
│   │   │       │   ├── Instance.createInstance(relateOffer → SubscriberOffers XSLT mapping)
│   │   │       │   └── Collections.add(addSubOffers, subOff4RelateOff)
│   │   │
│   │   ├── addSubOffersArray = Collections.toArray(addSubOffers)
│   │   ├── [if addSubOffersArray.length > 0]
│   │   │   ├── Event.createEvent(CREATE_TDS_PROFILE XSLT — see §9)
│   │   │   ├── Event.Ext.sendEventImmediate(reqEvent)
│   │   │   ├── if(!isActResub): orderCurrentActivity.RequestCount++
│   │   │   └── Event.Ext.sendEventImmediate(audit Logger)
│   │
│   └── [COU loop — EMPTY STUB]
│
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(...)
└── HandleActivityException(...)
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Properties Used |
|---------|---------------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.OMXTrackingId, OrderData.OrderID, OrderData.OrderType, OrderData.CES, OrderData.OperatorId, OrderData.DealerCode, OrderData.Channel, OrderData.Customer (CustomerName, CustomerTypeInfo, Account, ParentOU) |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, AccountRefId, SubscriberId, MSISDN, ResourceInfo[IMSI, SIM, MSISDN], SubscriberActivityInfo.ActivityReason, SubscriberGeneralInfo.Language, SubscriberOffers[] |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | Soc, OfferName, OfferInstanceId, ExtendedInfo[FE_OR_CCBS, ORIGINAL_TR_CONTRACT_TERM, ORIGINAL_TR_ORIG_CONTRACT_EXPIRE_DATE, ORIGINAL_TR_CONTRACT_FEE], RelatedOffersArray[] |
| `Concepts.OrderRequest.OrderElements.RelatedOffersArray` | OfferName, Soc, OfferInstanceId, SocProperties (TR_CONTRACT_IND=Y check), ParameterInfo[TR_CONTRACT_TERM, TR_ORIG_CONTRACT_EXPIRE_DATE, TR_CONTRACT_FEE, CONTRACT_FEE] |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck |
| `Concepts.FM.Response.CreateTDSProfileRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId (uses @Id not @extId!) |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Create TDS profiles for POU subscribers that have trade-in contracts with future expiry and positive fee |
| R2 | Phase 1: filter SubscriberOffers by ORIGINAL_TR_CONTRACT_TERM, ORIGINAL_TR_ORIG_CONTRACT_EXPIRE_DATE (future), ORIGINAL_TR_CONTRACT_FEE > 0 |
| R3 | Phase 2: expand to RelatedOffersArray where TR_CONTRACT_IND=Y, not duplicate, TR_CONTRACT_TERM ParameterInfo > 0, expiry future, TR_CONTRACT_FEE (or CONTRACT_FEE) > 0 |
| R4 | Map qualifying related offers to SubscriberOffers concept for inclusion in event payload |
| R5 | Dispatch one event per subscriber (carrying all qualifying offers) via parallel sendEventImmediate |
| R6 | ns:type = concat(OfferName, ',', TR_CONTRACT_FEE); ns:value = Soc; ns:offerInstanceId = OfferInstanceId |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Response fan-in unconditionally returns "true" — activity advances on first subscriber response regardless of RequestCount | [HIGH] | Add RequestCount/successResponseCount fan-in logic identical to MCS_CANCEL_SUBSCRIPTION or SBM FMs |
| Empty COU subscriber loop — no TDS profile created for COU subscribers | [MEDIUM] | Implement COU loop with same two-phase filtering; verify with business if COU TDS is in scope |
| `bussinessLine` dead variable (typo: "bussiness") — businessLine in XSLT actually uses $ouId | [MEDIUM] | Remove dead variable; if "MOBILE" should ever be sent, fix XSLT param binding |
| Resubmit skip keyed by subscriber.RefId only — if one offer succeeds, ALL offers for that subscriber are skipped | [MEDIUM] | Use a more specific composite key if per-offer retry granularity is needed |
| CreateTDSProfileRes uses `@Id` attribute instead of standard `@extId` | [MEDIUM] | Verify if `CreateTDSProfileRes` concept definition maps `Id` as its extId; fix to `@extId` if not intentional |
| Multiple `System.debugOut` left in production code (lines 114, 120, 121, 130, 131) | [LOW] | Remove all System.debugOut calls before production deployment |
| Commented-out related offer PreExecCheck (lines 162–165) | [LOW] | Clarify if this was intentionally disabled; remove dead code |

---

## §18 — Full Source Code (Request Rule — abbreviated)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CREATE_TDS_PROFILE {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CREATE_TDS_PROFILE";
    orderRequest.ProcessFlow.NextActivityID == "CREATE_TDS_PROFILE";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      String bussinessLine = "MOBILE";  // DEAD VARIABLE — typo, never used
      if(isActResub) { IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity); }
      for (POU loop) {
        ouName = FirstName + " " + LastName;  // DEAD VARIABLE — never used
        ouId = ParentOU[i].OUId;
        for (Subscriber loop) {
          addSubOffers = Collections.List.createArrayList();
          // Phase 1: filter parent offers by TR contract data
          for (SubscriberOffers[o]) {
            /* check chkTR_CONTRACT_TERM, expDateCal, TR_CONTRACT_FEE > 0, PreExecCheck */
            if(!reqSuccess && chkTR_CONTRACT_TERM && logicalDate < expDateCal && TR_CONTRACT_FEE > 0) {
              if(chkRes=="true") Collections.add(addSubOffers, subOff);
            }
          }
          // Phase 2: expand to related offers with TR_CONTRACT_IND=Y
          for (qualifying parent offers → RelatedOffersArray[k]) {
            if (!TR_CONTRACT_IND=Y || duplicate) continue;
            if(relate conditions met) {
              subOff4RelateOff = Instance.createInstance(/* relateOffer→SubscriberOffers XSLT */);
              Collections.add(addSubOffers, subOff4RelateOff);
            }
          }
          addSubOffersArray = Collections.toArray(addSubOffers);
          if(addSubOffersArray@length > 0) {
            reqEvent = Event.createEvent(/* CREATE_TDS_PROFILE XSLT — see §9 */);
            Event.Ext.sendEventImmediate(reqEvent);
            if(!isActResub) orderCurrentActivity.RequestCount++;
            // audit log
          }
        }
        // COU loop — empty body [MEDIUM BUG]
      }
      Status="1"; SendDataToDB; // or SkipActivity("4")
    } catch(Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 — Overview

Creates `CreateTDSProfileRes` concept (NOT ResponseBase or SBM_DoServiceRes), appends to `currActivity.Response[]`, logs audit, then **unconditionally returns `"true"`**. There is no fan-in RequestCount check. This means the activity advances immediately on the first subscriber response.

> **[HIGH] Missing Fan-in:** The response rulefunction does not check `currActivity.RequestCount == successResponseCount`. The first response received causes the activity to advance, leaving remaining subscriber responses unprocessed.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Audit log |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CREATE_TDS_PROFILE` | TDS response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended |

### §19.3 — CreateTDSProfileRes Concept Construction

```text
createObject
└── object @Id ← $extId (OMXUtils.generateTrackingID())  NOTE: uses @Id not @extId!  [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode       [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg        [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus   [Conditional]
    └── ReferenceId       ← $eventResponse/RefID              [Conditional]
```

### §19.4 — Response Completion Logic

| Behavior | Return |
|----------|--------|
| Always — no RequestCount check | `"true"` unconditionally **[HIGH BUG — should check RequestCount == successResponseCount]** |

### §19.5 — @Id vs @extId Anomaly

The response XSLT uses `<xsl:attribute name="Id">` (not the standard `extId`). This assigns the concept's identifier as `Id` rather than `extId`. If the `CreateTDSProfileRes` concept definition does not declare `Id` as its primary key attribute, the concept may be created without a proper working memory identifier — potentially causing lookup failures when reading `currActivity.Response[]`. **[MEDIUM]**

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
