# Request_OMX_ADD_FUT_OFFERS

> FM Logic Documentation — Future SOC/PP Registration (External OMXFM Call, Per-Offer Dispatch to OMX FM, 4 Scopes: PP@POU / Sub@POU / PP@COU / Sub@COU, Fan-In on Success Count)

**Rule:** `Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_FUT_OFFERS`
**ActivityID:** `OMX_ADD_FUT_OFFERS`
**Priority:** 5
**Pattern:** Per-Offer Parallel Dispatch → OMX FM
**Used in steps:** 12 (OMX_ADD_FUT_OFFERS), 13 (OMX_ADD_FUT_OFFERS_PRICEPLAN), 21 (OMX_ADD_FUT_OFFERS_REMOVE)

---

## §1 — Overview & Purpose

**OMX_ADD_FUT_OFFERS** registers future SOC/price plan orders into the OMX FM future orders system. For each qualifying offer in all 4 scopes (PP@POU, Sub@POU, PP@COU, Sub@COU), it dispatches a separate `OMX_ADD_FUTURE` JMS event. Each offer that passes its individual PreExecCheck AND does not already have a successful response gets its own dispatch. Fan-in completes when `RequestCount == count(success responses)`.

**Key design notes:**
- **Per-offer dispatch** (not per-OU): each AgreementOffer or SubscriberOffer that passes PreExecCheck sends its own JMS event. RequestCount incremented once per event sent.
- **futureType:** Default "FUTSOC". Changes to "FUTPP" when `ServiceType=="80"` (price plan). When FUTPP → remark includes offer name transition (CCBS offer name → FE offer name).
- **orderType override via activity parameter:** `Parameter[1]` from the activity overrides `orderRequest.OrderData.OrderType` if present.
- **isActResub gate:** If `RequestCount>0 AND IsOrderResubmitted` → do not increment RequestCount (idempotent resubmit mode).
- **reqSuccess check:** If a Response already exists with matching ReferenceId AND CompletionStatus==2 → skip that offer (resubmit idempotency).
- **EFF_ORD_DT override:** Sub@POU and Sub@COU check `offer.ExtendedInfo[EFF_ORD_DT]` — if present → use that as `ns:effectiveDate` instead of derived futureOrderEffectiveDate. Agreement scopes do NOT have this override.
- **FUTPP companion futureSoc:** When `futureType="FUTPP"`, additionally emits futureSoc entries for ServiceType=85 FE-tagged offers that have ParameterInfo[TR_CONTRACT_NUMBER] — using OfferOriginalEffectiveDate.
- **futureResourceRange:** Sub@POU and Sub@COU include ResourceRangeInfo[Action='PP'] entries when the subscriber has ServiceType='80' offers.
- **isSkipped flag:** Starts true; becomes false when first event sent. At end: if still skipped → `SkipActivity("4")`; else Status="1" + `SendDataToDB`.
- **PP@COU missing Logger audit:** PP@COU scope does not send a Logger event after dispatch (unlike the other three scopes). Appears to be an omission in the code.
- **AUDIT_TRACE inconsistency:** PP@POU = "Request Sent for OMX_ADD_FUTPP"; Sub@POU = "Request Sent for OMX_ADD_FUT_PP"; Sub@COU = "Request Sent for OMX_ADD_FUT_OFFERS"; PP@COU = (no audit). None match the rule name exactly.

| Attribute | Value |
|-----------|-------|
| Backend system | OMX FM (Future Orders) via `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` |
| Dispatch pattern | Per-offer parallel dispatch — one event per qualifying offer per scope |
| RequestCount gate | isActResub = RequestCount>0 AND IsOrderResubmitted — skip increment if resubmitting |
| Fan-in | `RequestCount == count(Response[tib:right(tib:trim(ResponseCode),3)="000"])` |
| Completion | Status="1" + `SendDataToDB` (if sent) or `SkipActivity("4")` (if all skipped) |
| Steps in BN_CHANGE_PACKAGE | 12, 13, 21 (same ActivityID, different extId/params) |
| Response rulefunction | `Response_OMX_ADD_FUT_OFFERS.rulefunction` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard |
| forwardChain | true | Standard |
| Rule type | OMXFM Request Rule | External dispatch to OMX FM |
| PurgePendingRequestsBeforeResubmit | N/A | Not used; resubmit handled via reqSuccess check + isActResub |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Source of all offer data, customer/OU structure, ExtendedInfo |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | PreExecCheck source; Parameter[1] for orderType; RequestCount; Response array |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_ADD_FUT_OFFERS"` | Constrains to this rule (covers all 3 step instances) |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_ADD_FUT_OFFERS"` | Double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Ready to process |

> **isActResub check (line 21):** Evaluated before the try block — `(RequestCount>0 && IsOrderResubmitted)`. This is NOT a WHEN condition; it is a guard inside THEN. When true → RequestCount is not incremented but events are still dispatched (for previously-failed offers that don't have CompletionStatus==2).

---

## §5 — Execution Flow Diagram

1. **isActResub:** Read `RequestCount>0 && IsOrderResubmitted`.
2. **LogicalDate resolution:** Read `Concepts.OM.LogicalDate`; default to `DateTime.now()`.
3. **Shared context:** Read accountSubType from `Account[1].AccountManagementInfo.AccountSubType`; requestBy from `OrderData.Channel`; orderType from `OrderData.OrderType` (overridden by `Parameter[1]` if present); `nextAct.PreExecCheck`.
4. **PP@POU loop:** For each ParentOU, for each Agreement Offer → per-offer PreExecCheck + reqSuccess check → if not skipped: compute futureType/futureOrderEffectiveDate → dispatch OMX_ADD_FUTURE event → RequestCount++ → Logger audit "Request Sent for OMX_ADD_FUTPP".
5. **Sub@POU loop:** For each ParentOU Subscriber, for each SubscriberOffer → per-offer PreExecCheck (FE_OR_CCBS filter applied) + reqSuccess check → dispatch OMX_ADD_FUTURE event (POU Subscriber variant, EFF_ORD_DT override, futureResourceRange) → RequestCount++ → Logger audit "Request Sent for OMX_ADD_FUT_PP".
6. **PP@COU loop:** For each ChildOU, for each Agreement Offer → per-offer PreExecCheck (GetXMLForAgreementOfferInChildOU) + reqSuccess check → dispatch OMX_ADD_FUTURE event → RequestCount++ → **NO Logger audit**.
7. **Sub@COU loop:** For each ChildOU Subscriber (using toArrayConcept), for each SubscriberOffer → per-offer PreExecCheck + reqSuccess check → dispatch OMX_ADD_FUTURE event (COU Subscriber variant, EFF_ORD_DT override, futureResourceRange) → RequestCount++ → Logger audit "Request Sent for OMX_ADD_FUT_OFFERS".
8. **isSkipped resolution:** If any event was dispatched → `Status="1"` + `SendDataToDB`. Else → `SkipActivity("4")`.

---

## §6 — futureType & futureOrderEffectiveDate Selection Logic

### §6.1 — futureType

| Condition | futureType value | remark value |
|-----------|-----------------|--------------|
| `offer.ServiceType != "80"` | `"FUTSOC"` | `""` (empty) |
| `offer.ServiceType == "80"` | `"FUTPP"` | `concat(CCBS OfferName, '->', FE OfferName)` from siblings with same scope |

### §6.2 — futureOrderEffectiveDate Selection

| Priority | Condition | futureOrderEffectiveDate |
|----------|-----------|--------------------------|
| 1 | `exists(ExpirationDate) AND NOT(exists(EffectiveDate))` | `offer.ExpirationDate` |
| 2 | `(GetEffType(EffectiveDate)=="BD" OR "IM") AND GetEffType(ExpirationDate)=="FUT"` | `offer.ExpirationDate` |
| 3 | `GetEffType(EffectiveDate)=="FUT" AND GetEffType(ExpirationDate)=="FUT"` | `offer.EffectiveDate` |
| 4 (default) | All other cases | `offer.EffectiveDate` |

### §6.3 — isFutEffective & ns2:effectiveDate

`isFutEffective = GetActivityEffectiveType(offer.EffectiveDate, logicalDate) == "FUT"`. When `isFutEffective==true` AND `offer.EffectiveDate` exists → `ns2:effectiveDate` is included in the main futureSoc. When `isFutEffective==false` → `ns2:effectiveDate` is omitted (the effective date comes from futureOrderEffectiveDate in futureOrder.effectiveDate instead).

### §6.4 — EFF_ORD_DT Override (Sub@POU and Sub@COU only)

The subscriber variants use an `xsl:choose` for `ns:effectiveDate` in `ns:futureOrder`:
- If `offer.ExtendedInfo[Name='EFF_ORD_DT']` exists → `ns:effectiveDate = offer.ExtendedInfo[EFF_ORD_DT].Value`.
- Otherwise → `ns:effectiveDate = $futureOrderEffectiveDate`.
- Agreement variants (PP@POU, PP@COU) do NOT have this override.

### §6.5 — FUTPP Companion futureSoc

When `futureType=="FUTPP"`, the XSLT iterates over the scope's offers and adds additional `ns2:futureSoc` entries for offers where: `ServiceType=85` AND `ExtendedInfo[Name='FE_OR_CCBS' and Value='FE']` AND `boolean(ParameterInfo[ParamName='TR_CONTRACT_NUMBER'])`. These companion entries use `ns2:effectiveDate = $OfferOriginalEffectiveDate` (from `offer.ExtendedInfo[OfferOriginalEffectiveDate].Value`).

---

## §7 — PreExecCheck XML Helpers per Scope

| Scope | Helper function | Input arguments |
|-------|----------------|-----------------|
| PP@POU | `GetXMLForAgreementOffer(orderRequest, agreeRefId, refId)` | agreeRefId=POU.Agreement.RefId, refId=offer.Soc |
| Sub@POU | `GetXMLForSubscriberOfferActionFilterWithExtendedInfo(orderRequest, subRefId, refId, filter, action)` | subRefId=Subscriber.RefId, refId=offer.Soc, filter=offer.ExtendedInfo[FE_OR_CCBS].Value, action=offer.Action |
| PP@COU | `GetXMLForAgreementOfferInChildOU(orderRequest, agreeRefId, refId, pOu.RefId)` | agreeRefId=ChildOU.Agreement.RefId, refId=offer.Soc, pOu.RefId=parent OU RefId |
| Sub@COU | `GetXMLForSubscriberOfferInChildOU(orderRequest, subRefId, refId, pOu.RefId)` | subRefId=COU.Subscriber.RefId, refId=offer.Soc, pOu.RefId=parent OU RefId |

> Note: Sub@POU includes `filter` (FE_OR_CCBS value) AND `action` (offer.Action) in the XML helper arguments — Sub@COU does NOT include these; it uses the simpler `GetXMLForSubscriberOfferInChildOU`.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in BN_CHANGE_PACKAGE at steps 12, 13, and 21. The three step instances share the same ActivityID but differ in their extId and likely in their Parameters and PreExecCheck values.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Gate | Purpose |
|-----------|-----------|------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_ADD_FUTURE` | Per offer: PreExecCheck passes AND !reqSuccess | Register future SOC/PP in OMX FM |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Always after each outbound event (PP@COU scope missing) | Request audit trail |

### §8.3 — Backend API Details

| Attribute | Value |
|-----------|-------|
| System | OMX FM (Future Orders management subsystem) |
| Operation | Add Future SOC/PP order (addFutureOrder) |
| Schema | `ns3:futureOrderWithSoc` containing `ns:futureOrder` + `ns2:futureSocs` + optional `ns4:futureResourceRange` |
| Schema namespaces | ns=FutureOrder.xsd, ns2=FutureSoc.xsd, ns3=FutureOrderWithSoc.xsd, ns4=FutureResourceRange.xsd |
| Correlation | JMSCorrelationID = OMXTrackingId; fan-in on RequestCount == successResponseCount |

### §8.4 — BE Working Memory Dependencies (Read)

| Concept path | Purpose |
|-------------|---------|
| `Concepts.OM.LogicalDate.LogicalDate` | Date classification for isFutEffective and futureOrderEffectiveDate |
| `orderCurrentActivity.Parameter[1]` | orderType override |
| `OrderData.Customer.CustomerId` | custId → CUS_ID extendedInfo in payload |
| `OrderData.Customer.Account[1].AccountManagementInfo.AccountSubType` | accountSubType |
| `OrderData.Channel` | requestBy |
| `OrderData.OrderType` | Default orderType (may be overridden by Parameter[1]) |
| `ParentOU[*].Agreement.Offers[*]` | PP@POU: Soc, ServiceType, EffectiveDate, ExpirationDate, OfferName, ParameterInfo, RelatedOffersArray, ExtendedInfo |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*]` | Sub@POU: same + Action, ResourceRangeInfo |
| `ParentOU[*].ChildOU[*].Agreement.Offers[*]` | PP@COU: same as PP@POU |
| `ParentOU[*].ChildOU[*].Subscriber[*].SubscriberOffers[*]` | Sub@COU: same as Sub@POU |
| `orderCurrentActivity.Response[*].ReferenceId / CompletionStatus` | reqSuccess check for each offer |

### §8.5 — ExtendedInfo Fields Required (Read)

| Key | Scope | Purpose |
|-----|-------|---------|
| `OfferOriginalEffectiveDate` | All offers | Used as effectiveDate for FUTPP companion futureSoc entries |
| `FE_OR_CCBS` | Sub@POU, all Agreement offers (FUTPP remark) | Filter for PreExecCheck XML helper; FUTPP remark calculation |
| `EFF_ORD_DT` | Sub@POU, Sub@COU only | Override for ns:effectiveDate in futureOrder (if present) |

### §8.6 — nodeLevel & nodeId per Scope

| Scope | nodeLevel | nodeId | RefID header |
|-------|-----------|--------|--------------|
| PP@POU | 3 (OU) | pOu.OUId | pOu.RefId |
| Sub@POU | 5 (Sub) | subscriberPou.SubscriberId | subscriberPou.RefId |
| PP@COU | 3 (OU) | cOu.OUId | cOu.RefId |
| Sub@COU | 5 (Sub) | subscriberCou.SubscriberId | subscriberCou.RefId |

---

## §9 — Payload Build — OMX_ADD_FUTURE Event (4 Variants)

### §9.1 — JMS / Event Header Fields

| Header | Source | Condition |
|--------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | Conditional: if exists |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Always |
| OrderID | `$orderRequest/OrderData/OrderID` | Conditional: if exists |
| RefID | `$scope/RefId` | Conditional: if exists |
| UserName | `$orderRequest/OrderData/User` | Conditional: if exists |
| PassWord | `$orderRequest/OrderData/Password` | Conditional: if exists |
| OrderType | `$orderRequest/OrderData/OrderType` | Conditional: if exists |

### §9.2 — ns:futureOrder Fields

| Element | PP@POU | Sub@POU | PP@COU | Sub@COU |
|---------|--------|---------|--------|---------|
| `ns:effectiveDate` | Always (direct futureOrderEffectiveDate) | xsl:choose: EFF_ORD_DT if exists, else futureOrderEffectiveDate | Always (direct) | xsl:choose: EFF_ORD_DT if exists, else futureOrderEffectiveDate |
| `ns:orderType` | Always ($orderType) | Always | Always | Always |
| `ns:nodeLevel` | 3 (OU) | 5 (Sub) | 3 (OU) | 5 (Sub) |
| `ns:nodeId` | pOu.OUId | subId | cOu.OUId | subId |
| `ns:requestedDate` | current-dateTime() | current-dateTime() | current-dateTime() | current-dateTime() |
| `ns:requestedBy` | $requestBy | $requestBy | $requestBy | $requestBy |
| `ns:extendedInfo[OU_ID]` | — | — | **Always** (cOu.OUId, no blank guard) | **Always** |
| `ns:extendedInfo[SUB_ID]` | — | Cond: not blank | — | Cond: not blank |
| `ns:extendedInfo[MOBILE_NO]` | — | Cond: not blank | — | Cond: not blank |

### §9.3 — userText Construction

| Scope | Pattern |
|-------|---------|
| PP@POU | `"{inputUserText};FUTSOC request by {channel} on {dateTimeNow};"` |
| Sub@POU, PP@COU, Sub@COU | `"{inputUserText};request by {channel} on {dateTimeNow};"` |

### §9.4 — ns2:futureSocs — Main futureSoc

| Element | Source | Condition |
|---------|--------|-----------|
| `ns2:code` | $code (offer.Soc) | Always |
| `ns2:effectiveDate` | $offer/EffectiveDate | Conditional: isFutEffective=='true' AND offer.EffectiveDate exists |
| `ns2:expireDate` | $offer/ExpirationDate | Conditional: if exists |
| `ns2:instanceId` | $offer/OfferInstanceId | Conditional: if exists |
| `ns2:parentInstanceId` | $offer/ParentOfferInstanceId | Conditional: if exists |
| `ns2:parameter[*]` | for-each $offer/ParameterInfo → paramName/paramValue | Each ParameterInfo entry |
| `ns2:childSoc[*]` | for-each $offer/RelatedOffersArray → code/parameters/type/socName | Each RelatedOffersArray entry |
| `ns2:type` | $offer/ServiceType | Conditional: if exists |
| `ns2:subType` | $futureType | Always |
| `ns2:socName` | $offer/OfferName | Conditional: if exists |

### §9.5 — ns4:futureResourceRange (Sub@POU and Sub@COU only)

Included when `exists(subscriber/SubscriberOffers[ServiceType='80'])`. Iterates `subscriber/ResourceRangeInfo[Action='PP']`:

| Element | Source | Condition |
|---------|--------|-----------|
| `ns4:action` | ResourceRangeInfo.Action | Always |
| `ns4:name` | ResourceRangeInfo.ResourceName | Always |
| `ns4:value` | ResourceRangeInfo.ValuesArray | Always |
| `ns4:effectiveDate` | ResourceRangeInfo.effectiveDate | Conditional: if exists |
| `ns4:expirationDate` | ResourceRangeInfo.expirationDate | Conditional: if exists |

---

## §11 — Audit Logging

| Scope | PROCESS_ID suffix | OPERATION_NAME | AUDIT_TRACE | WritePayload gate |
|-------|------------------|----------------|-------------|------------------|
| PP@POU | _REQ | "OMX_ADD_FUT_OFFERS" | "Request Sent for OMX_ADD_FUTPP" | Yes |
| Sub@POU | _REQ | "OMX_ADD_FUT_OFFERS" | "Request Sent for OMX_ADD_FUT_PP" | Yes |
| PP@COU | — | — | **NO AUDIT LOG** | — |
| Sub@COU | _REQ | "OMX_ADD_FUT_OFFERS" | "Request Sent for OMX_ADD_FUT_OFFERS" | Yes |

> [HIGH] PP@COU scope is missing its Logger audit event. The code dispatches the event and increments RequestCount but sends no Logger event. This is an oversight that would make PP@COU requests invisible in audit logs.

> [MEDIUM] AUDIT_TRACE values are inconsistent: PP@POU says "FUTPP" (not FUTSOC or FUT_OFFERS), Sub@POU says "FUT_PP", only Sub@COU says "FUT_OFFERS" — none exactly match "OMX_ADD_FUT_OFFERS". These appear to be copy-paste artifacts.

---

## §12 — Activity Status Management

| Condition | Action |
|-----------|--------|
| Any event dispatched (isSkipped==false) | `Status = GetActivityStatusString("1", false)`; `SendDataToDB(orderRequest)` |
| No events dispatched (isSkipped==true) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

> [LOW] Status "1" is set inline after each event send at PP@POU and PP@COU. Then it is set again at the end for ALL cases where isSkipped==false. These intermediate status sets are redundant.

---

## §13 — Exception / Error Handling

| Exception | Handler |
|-----------|---------|
| Any exception in try block | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Helpers.GetActivityEffectiveType(date, logicalDate)` | Classify date as IM/BD/FUT relative to logicalDate |
| `Helpers.GetXMLForAgreementOffer(orderRequest, agreeRefId, refId)` | Build PreExecCheck XML for PP@POU |
| `Helpers.GetXMLForSubscriberOfferActionFilterWithExtendedInfo(orderRequest, subRefId, refId, filter, action)` | Build PreExecCheck XML for Sub@POU (with FE_OR_CCBS and Action) |
| `Helpers.GetXMLForAgreementOfferInChildOU(orderRequest, agreeRefId, refId, pOuRefId)` | Build PreExecCheck XML for PP@COU |
| `Helpers.GetXMLForSubscriberOfferInChildOU(orderRequest, subRefId, refId, pOuRefId)` | Build PreExecCheck XML for Sub@COU |
| `Helpers.GetActivityStatusString("1", false)` | Return status string for "IN PROGRESS" state |
| `Helpers.SendDataToDB(orderRequest)` | Persist order state after dispatch |
| `Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")` | Skip all offers (none qualified) |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |
| `Instance.PropertyArray.toArrayConcept(ChildOU.Subscriber)` | Convert Sub@COU property array to concept array for iteration |

---

## §15 — Function Dependency Tree

```text
Request_OMX_ADD_FUT_OFFERS (rule)
├── isActResub = (RequestCount>0 && IsOrderResubmitted)
└── try {
    ├── Instance.getByExtIdByUri("LogicalDate", ...) → logicalDate
    ├── XPath.evalAsString(Account[1].AccountSubType)    → accountSubType
    ├── XPath.evalAsString(Parameter[1])                 → orderType override
    ├── [PP@POU: ParentOU.Agreement.Offers loop]
    │   ├── GetXMLForAgreementOffer()
    │   ├── XPath.execute(PreExecCheck)                  → chkRes
    │   ├── [if chkRes=="true" && !reqSuccess]
    │   │   ├── GetActivityEffectiveType() x3            → isFutEffective, futureOrderEffectiveDate
    │   │   ├── Event.createEvent(xslt://OMX_ADD_FUTURE [PP@POU])
    │   │   ├── Event.Ext.sendEventImmediate(reqEvent)
    │   │   ├── RequestCount++ (if !isActResub)
    │   │   ├── Status = GetActivityStatusString("1", false)
    │   │   └── Event.Ext.sendEventImmediate(Logger audit "...FUTPP")
    ├── [Sub@POU: Subscriber.SubscriberOffers loop]
    │   ├── GetXMLForSubscriberOfferActionFilterWithExtendedInfo()
    │   ├── XPath.execute(PreExecCheck)                  → chkRes
    │   ├── [if chkRes=="true" && !reqSuccess]
    │   │   ├── GetActivityEffectiveType() x3
    │   │   ├── Event.createEvent(xslt://OMX_ADD_FUTURE [Sub@POU+EFF_ORD_DT+ResourceRange])
    │   │   ├── Event.Ext.sendEventImmediate(reqEvent)
    │   │   ├── RequestCount++ (if !isActResub)
    │   │   └── Event.Ext.sendEventImmediate(Logger audit "...FUT_PP")
    ├── [PP@COU: ChildOU.Agreement.Offers loop]
    │   ├── GetXMLForAgreementOfferInChildOU()
    │   ├── XPath.execute(PreExecCheck)
    │   ├── [if chkRes=="true" && !reqSuccess]
    │   │   ├── GetActivityEffectiveType() x3
    │   │   ├── Event.createEvent(xslt://OMX_ADD_FUTURE [PP@COU])
    │   │   ├── Event.Ext.sendEventImmediate(reqEvent)
    │   │   ├── RequestCount++ (if !isActResub)
    │   │   └── Status = GetActivityStatusString("1", false)  [NO Logger audit!]
    ├── [Sub@COU: ChildOU.Subscriber.SubscriberOffers loop (toArrayConcept)]
    │   ├── GetXMLForSubscriberOfferInChildOU()
    │   ├── XPath.execute(PreExecCheck)
    │   ├── [if chkRes=="true" && !reqSuccess]
    │   │   ├── GetActivityEffectiveType() x3
    │   │   ├── Event.createEvent(xslt://OMX_ADD_FUTURE [Sub@COU+EFF_ORD_DT+ResourceRange])
    │   │   ├── Event.Ext.sendEventImmediate(reqEvent)
    │   │   ├── RequestCount++ (if !isActResub)
    │   │   └── Event.Ext.sendEventImmediate(Logger audit "...FUT_OFFERS")
    ├── [if !isSkipped]
    │   ├── Status = GetActivityStatusString("1", false)
    │   └── Helpers.SendDataToDB(orderRequest)
    └── [else] Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")
} catch → Helpers.HandleActivityException()
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-offer PreExecCheck (separate XML helper per scope). Check reqSuccess to skip already-succeeded offers on resubmit. |
| R2 | isActResub detection: skip RequestCount increment during resubmit of previously-dispatched requests. |
| R3 | futureType defaults "FUTSOC"; changes to "FUTPP" when ServiceType=="80". remark set when FUTPP. |
| R4 | futureOrderEffectiveDate uses 4-priority selection algorithm (§6.2). |
| R5 | EFF_ORD_DT ExtendedInfo overrides ns:effectiveDate in futureOrder — subscriber scopes only. |
| R6 | FUTPP companion futureSoc: ServiceType=85, FE-tagged, TR_CONTRACT_NUMBER → effectiveDate from OfferOriginalEffectiveDate. |
| R7 | futureResourceRange: emit when ServiceType='80' offer exists in subscriber; source from ResourceRangeInfo[Action='PP']. |
| R8 | COU scopes: add OU_ID extendedInfo unconditionally (not conditional on blank like other IDs). |
| R9 | Sub@POU: add CLM_* ExtendedInfo from OrderData.ExtendedInfo. Sub@COU: same CLM_* plus OU_ID. |
| R10 | Fan-in: count(Response[ResponseCode ends "000"]) == RequestCount. |

### Design Notes

| Note | Severity | Detail |
|------|----------|--------|
| PP@COU missing Logger audit event | [HIGH] | PP@COU dispatches events but sends no Logger audit. Makes PP@COU requests invisible in audit trail. Likely omission during code development. |
| AUDIT_TRACE inconsistency across scopes | [MEDIUM] | "FUTPP", "FUT_PP", "FUT_OFFERS" across 3 scopes — none exactly match the rule name. Copy-paste artifacts. |
| Redundant Status="1" set inside PP@POU and PP@COU loops | [LOW] | Status is set both inline (per event) and at the end. The final one dominates. Harmless but confusing. |
| Sub@COU uses toArrayConcept; Sub@POU uses direct index iteration | [INFO] | Inconsistency in how COU vs POU subscribers are iterated. Both work but different patterns. |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_FUT_OFFERS {
    attribute { priority = 5; forwardChain = true; }
    declare { OrderRequest orderRequest; Activity orderCurrentActivity; }
    when { /* extId / ActivityID=="OMX_ADD_FUT_OFFERS" / NextActivityID / Status=="WAITING" */ }
    then {
        isActResub = (RequestCount>0 && IsOrderResubmitted);
        try {
            logicalDate = resolve from LogicalDate concept OR DateTime.now();
            accountSubType = XPath.evalAsString(Account[1].AccountSubType);
            orderType = OrderData.OrderType; if(Parameter[1]!="") orderType = Parameter[1];

            for(iPOU...) {
                // PP@POU: Agreement Offers
                for(iPouOffer...) {
                    chkRes = GetXMLForAgreementOffer + XPath.execute(PreExecCheck);
                    if(chkRes=="true" && !reqSuccess) {
                        futureType = offer.ServiceType=="80" ? "FUTPP" : "FUTSOC";
                        futureOrderEffectiveDate = select(see §6.2);
                        isFutEffective = GetEffType(EffDate)=="FUT";
                        reqEvent = Event.createEvent("xslt://OMX_ADD_FUTURE [PP@POU]"); /* see §9 */
                        Event.Ext.sendEventImmediate(reqEvent);
                        RequestCount++; Status="1"; Logger("...FUTPP");
                    }
                }
                // Sub@POU: Subscriber Offers
                for(iPouSub...; iPouSubOffer...) {
                    chkRes = GetXMLForSubscriberOfferActionFilterWithExtendedInfo + XPath.execute(PreExecCheck);
                    if(chkRes=="true" && !reqSuccess) {
                        reqEvent = Event.createEvent("xslt://OMX_ADD_FUTURE [Sub@POU+EFF_ORD_DT+ResourceRange]");
                        Event.Ext.sendEventImmediate(reqEvent); RequestCount++; Logger("...FUT_PP");
                    }
                }
                // PP@COU: ChildOU Agreement Offers
                for(iCOU...; iCouOffer...) {
                    chkRes = GetXMLForAgreementOfferInChildOU + XPath.execute(PreExecCheck);
                    if(chkRes=="true" && !reqSuccess) {
                        reqEvent = Event.createEvent("xslt://OMX_ADD_FUTURE [PP@COU]");
                        Event.Ext.sendEventImmediate(reqEvent); RequestCount++; Status="1";
                        // No Logger event for PP@COU (omission)
                    }
                }
                // Sub@COU: ChildOU Subscriber Offers (toArrayConcept)
                for(iCouSub...; iCouSubOffer...) {
                    chkRes = GetXMLForSubscriberOfferInChildOU + XPath.execute(PreExecCheck);
                    if(chkRes=="true" && !reqSuccess) {
                        reqEvent = Event.createEvent("xslt://OMX_ADD_FUTURE [Sub@COU+EFF_ORD_DT+ResourceRange]");
                        Event.Ext.sendEventImmediate(reqEvent); RequestCount++; Logger("...FUT_OFFERS");
                    }
                }
            }
            if(!isSkipped) { Status="1"; SendDataToDB(orderRequest); }
            else { SkipActivity("4"); }
        } catch(ae) { HandleActivityException; }
    }
}
```

---

## §19 — Response Message Rule (Response_OMX_ADD_FUT_OFFERS)

### §19.1 — Overview

Handles incoming responses from the OMX FM Future Orders system. Creates a `OMX_AddFutureRes` concept from the response, appends it to `currActivity.Response`, sends a Logger audit event, and checks fan-in completion. Returns "true" when all expected successes have been received.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Audit correlation (OMXTrackingId) |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE` | Incoming FM response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response array target; RequestCount source for fan-in |

### §19.3 — ResponseBase Concept Construction

```text
createObject (Concepts.FM.Response.OMX_AddFutureRes)
└── object
    ├── @extId              ← OMXUtils.generateTrackingID()         [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode           [Conditional: if exists]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg            [Conditional: if exists]
    └── CompletionStatus    ← $eventResponse/CompletionStatus       [Conditional: if exists]

NOTE: ReferenceId is NOT mapped (differs from some other FMs).
```

> [MEDIUM] `ReferenceId` is NOT mapped in the response concept. The reqSuccess check in the request rule uses `ReferenceId` for idempotency — but the response rule does not populate it. This means `ReferenceId` will always be null/empty in Response entries, so the reqSuccess check `String.equals(Response[i].ReferenceId, refId)` will never match on resubmit unless ReferenceId comes from elsewhere.

### §19.4 — Response Completion Logic (Fan-In)

| Attribute | Value |
|-----------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Return "true" | All dispatched requests have returned a "000" success code |
| Return "false" | Still waiting for more "000" responses |

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID suffix | _RES |
| OPERATION_NAME | "OMX_ADD_FUT_OFFERS" |
| TARGET_SYSTEM | OMX_FM |
| AUDIT_TRACE | "Response received for OMX_ADD_FUT_OFFERS" |
| payload | $eventResponse (conditional: WritePayload=="true") |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
