# Request_CCBS_CHANGE_PP_OU

> FM Logic Documentation — Change Price Plan at OU Level (COU + POU Scopes; Shared Allowance; LargeCustomer LogicalDate; SOC Sequence Pre-allocation; OMXFM external dispatch)

**Rule:** `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CHANGE_PP_OU`
**ActivityID:** `CCBS_CHANGE_PP_OU`
**Priority:** 5
**Pattern:** Per-OU dispatch (COU first, then POU)
**Used in step:** 17

---

## §1 — Overview & Purpose

**CCBS_CHANGE_PP_OU** registers a price plan change at the OU level in the OMX FM system. For each ParentOU, it first checks ChildOUs (COU scope), then the ParentOU's own Agreement (POU scope). Each qualifying scope dispatches one `CCBS_CHANGE_PP_OU` JMS event.

**Key design notes:**
- **COU before POU:** For each ParentOU, ChildOUs are processed first (inner loop), then the ParentOU Agreement.
- **PurgePendingRequestsBeforeResubmit:** Called at start when `isActResub==true`. Clears pending/incomplete requests before resubmitting.
- **varPP selection:** XSLT selects the FE price plan offer via `Offers[ServiceType='80' and ExtendedInfo/Name='FE_OR_CCBS' and ExtendedInfo/Value='FE'][1]`.
- **isSharedAllowance + capSoc:** If the FE PP offer has `SPECIAL_OFFER_INDICATOR=CSH`, iterates RelatedOffersArray to find the one where `GetSplOffIndForSoc == "CAP"`. If found → adds a special `ns9:parameterInfoWithSoc` with static name="Agreement level offer instance ID".
- **LargeCustomerIndicator=89:** Computes `tomorrowLogicalDate` (+1 day midnight) at the top. Inside XSLT → adds `ns6:EnclosedClientInfo/ns6:LogicalDate`: uses varPP.EffectiveDate if exists, else tomorrowDate.
- **FUT_TYPE UserText append:** If `ExtendedInfo[FUT_TYPE]` is 'NXTPP' or 'FUTPP' → appends Thai text ';เปลี่ยน PP โดย omx future order;' to UserText.
- **SOC sequence pre-allocation:** `countOfers + countRelatedOffersArray` sent in `ns3:GetSequenceValueRequest.ns3:incrementByCount`.
- **ChargeDistributionDetailsInfo:** If `varPP.RCIndicator=65` → adds `ns8:ChargeDistributionDetailsInfo` pointing to accountId.
- **Fan-in CRITICAL NOTE:** Response RF uses `boolean(Response["000"])` — returns "true" if ANY response is "000", NOT compared to RequestCount. See §19.4 for analysis.

| Attribute | Value |
|-----------|-------|
| Backend system | OMX FM via `Events.OMConsumers.OMXFM.Request.CCBS_CHANGE_PP_OU` |
| Dispatch pattern | Per-OU (COU first, then POU); max 2 events per POU iteration |
| Scope gate | Agreement != null AND Agreement.Offers@length > 0 AND PreExecCheck passes |
| Fan-in | `boolean($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` — ANY "000" |
| Completion | Status="1" + SendDataToDB (if sent) or SkipActivity("4") |
| Steps in BN_CHANGE_PACKAGE | 17 |
| Response rulefunction | `Response_CCBS_CHANGE_PP_OU.rulefunction` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard |
| forwardChain | true | Standard |
| Rule type | OMXFM Request Rule | External dispatch to OMX FM |
| PurgePendingRequestsBeforeResubmit | Yes | Called when isActResub==true (line 29) |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | All OU, Agreement, Offer data; ExtendedInfo (FUT_TYPE, LargeCustomerIndicator) |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | PreExecCheck; RequestCount; Response array |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity match |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_CHANGE_PP_OU"` | Rule constraint |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_CHANGE_PP_OU"` | ProcessFlow check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Ready to process |

---

## §5 — Execution Flow Diagram

1. **isActResub:** `RequestCount>0 && IsOrderResubmitted`.
2. **PurgePendingRequestsBeforeResubmit:** If isActResub → call `PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`.
3. **tomorrowLogicalDate:** If `CustomerGeneralInfo.LargeCustomerIndicator=89` → compute tomorrow midnight via `DateTime.addDay(DateTime.now(),1)`.
4. **COU loop:** For each ChildOU → if Agreement.Offers > 0 → PreExecCheck via `GetXMLForAgreementInChildOU` → if "true": compute counts/agreementNo/activityReason/userText/accountId/isSharedAllowance → dispatch `CCBS_CHANGE_PP_OU` event → RequestCount++ → Logger.
5. **POU loop:** After COU iteration — if ParentOU.Agreement.Offers > 0 → PreExecCheck via `GetXMLForAgreement` → same compute steps → dispatch → RequestCount++ → Logger.
6. **isSkipped resolution:** If any event sent → Status="1" + `SendDataToDB`. Else → `SkipActivity("4")`.

---

## §6 — isSharedAllowance / capSoc Detection

For each qualifying OU (COU and POU), before dispatching:

1. Scan Agreement.Offers for ServiceType=="80" AND FE_OR_CCBS==FE.
2. If `exists(ExtendedInfo[SPECIAL_OFFER_INDICATOR=CSH])`: iterate RelatedOffersArray.
3. For each RelatedOffers entry: call `GetSplOffIndForSoc(orderRequest, relSoc.Soc)`.
4. If result == "CAP" → `capSoc = relSoc.Soc`, `isSharedAllowance = true`.

When `isSharedAllowance==true`, the XSLT adds:
```xml
<ns9:parameterInfoWithSoc>
    <ns9:name>Agreement level offer instance ID</ns9:name>
    <ns9:values>Agreement level offer instance ID</ns9:values>
    <ns9:soc>{$capSoc}</ns9:soc>
</ns9:parameterInfoWithSoc>
```

---

## §7 — LargeCustomerIndicator=89 & EnclosedClientInfo

When `LargeCustomerIndicator=89`:
- BE computes: `tomorrowLogicalDate = DateTime.format(DateTime.addDay(DateTime.now(),1),"yyyy-MM-dd'T'00:00:00XXX")`
- XSLT adds `ns6:EnclosedClientInfo/ns6:LogicalDate`:
  - `xsl:when exists($varPP/EffectiveDate)` → use `varPP/EffectiveDate`
  - `xsl:otherwise` → compute tomorrow inline via `tib:add-to-dateTime`

> [LOW] The BE-computed `tomorrowLogicalDate` param is effectively unused in the XSLT (XSLT recalculates in its else branch). Minor redundancy.

---

## §8 — System & Integration Dependencies

### §8.1 — ESB / JMS Channel Dependencies

| Direction | Event Type | Gate | Purpose |
|-----------|-----------|------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_CHANGE_PP_OU` | Agreement.Offers > 0 AND PreExecCheck passes | Register PP change at OU level |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Always after each outbound event | Request audit trail |

### §8.2 — Backend API Details

| Attribute | Value |
|-----------|-------|
| System | OMX FM / CCBS |
| Operation | changePricePlanOu |
| Schema | `ns2:changePricePlanOuRequest` (ChangePricePlanOu.xsd) |
| Key sub-elements | GetSequenceValueRequest (SOC_SEQ_NO), changePricePlanOu (AgreementIdInfo + parameterInfoWithSoc + SrvAgrInfo + ChargeDistributionDetailsInfo + ActivityInfo) |

### §8.3 — PreExecCheck Helpers per Scope

| Scope | Helper | Arguments |
|-------|--------|-----------|
| COU | `GetXMLForAgreementInChildOU(orderRequest, childOu.Agreement.RefId, parentOu.RefId)` | childOu.Agreement.RefId, parentOu.RefId |
| POU | `GetXMLForAgreement(orderRequest, parentOu.Agreement.RefId)` | parentOu.Agreement.RefId |

### §8.4 — ExtendedInfo / Fields Required (Read)

| Path | Purpose |
|------|---------|
| `CustomerGeneralInfo.LargeCustomerIndicator` | Gate for tomorrowLogicalDate and EnclosedClientInfo |
| `Agreement.Offers[ServiceType=80 and FE_OR_CCBS=FE]` | varPP — all payload data comes from this offer |
| `Offer.ExtendedInfo[SPECIAL_OFFER_INDICATOR=CSH]` | isSharedAllowance detection |
| `Account[AgreementId=...][1].AccountID` | accountId for ChargeDistributionDetailsInfo |
| `AgreementActivityInfo.ActivityReason / UserText` | ns6:ActivityInfo payload |
| `OrderData.ExtendedInfo[FUT_TYPE].Value` | Gate for Thai UserText append |

---

## §9 — Payload Build — CCBS_CHANGE_PP_OU Event

### §9.1 — JMS / Event Header Fields

| Header | Source | Condition |
|--------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | Conditional: if exists |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Conditional: if exists |
| OrderID | `$orderRequest/OrderData/OrderID` | Conditional: if exists |
| RefID | `$childOu/RefId` or `$parentOu/RefId` | Conditional: if exists |
| UserName | `$orderRequest/OrderData/User` | Conditional: IsEnableUserPass='true' |
| PassWord | `$orderRequest/OrderData/Password` | Conditional: IsEnableUserPass='true' |
| OrderType | `$orderRequest/OrderData/OrderType` | Conditional: if exists |
| CES | `$orderRequest/OrderData/CES` | Conditional: if exists |

### §9.2 — Payload Structure: ns2:changePricePlanOuRequest

```text
ns2:changePricePlanOuRequest
├── ns3:GetSequenceValueRequest                   [Always]
│   ├── ns3:sequenceName  ← "SOC_SEQ_NO"         [Static]
│   └── ns3:incrementByCount ← $countOfers + $countRelatedOffersArray
├── ns2:changePricePlanOu
│   ├── ns4:AgreementIdInfo/ns4:AgreementNo ← $agreementNo  [Always]
│   ├── ns9:parameterInfoWithSoc[*]  ← for-each $varPP/ParameterInfo
│   │   ├── ns9:name   ← ParamName
│   │   ├── ns9:values ← ValuesArray[1]
│   │   └── ns9:soc    ← $varPP/Soc
│   ├── ns9:parameterInfoWithSoc[*]  ← for-each $varPP/RelatedOffersArray/ParameterInfo
│   │   └── ns9:soc    ← ../Soc (parent RelatedOffers.Soc)
│   ├── ns9:parameterInfoWithSoc     [Conditional: isSharedAllowance='true']
│   │   ├── ns9:name   ← "Agreement level offer instance ID" [Static]
│   │   ├── ns9:values ← "Agreement level offer instance ID" [Static]
│   │   └── ns9:soc    ← $capSoc
│   ├── ns5:SrvAgrInfo ← for-each $varPP
│   │   ├── ns5:Name   ← OfferName
│   │   ├── ns5:RelatedOffers[*] ← for-each $varPP/RelatedOffersArray
│   │   │   ├── ns5:Name ← OfferName   [Conditional]
│   │   │   └── ns5:Soc  ← Soc         [Conditional]
│   │   └── ns5:Soc    ← Soc           [Conditional]
│   ├── ns8:ChargeDistributionDetailsInfo  [Conditional: $varPP/RCIndicator=65]
│   │   ├── ns8:Soc    ← $varPP/Soc    [Conditional]
│   │   └── ns8:TargetPayChannelId ← $accountId
│   ├── ns8:ChargeDistributionDetailsInfo[*] ← for-each $varPP/RelatedOffersArray[RcIndicator=65]
│   └── ns6:ActivityInfo                        [Always]
│       ├── ns6:ActivityReason ← $activityReason (or "CREQ")
│       ├── ns6:EnclosedClientInfo              [Conditional: LargeCustomerIndicator=89]
│       │   └── ns6:LogicalDate ← varPP.EffectiveDate if exists, else tomorrowDate
│       └── ns6:UserText ← if FUT_TYPE=NXTPP/FUTPP: concat(userText, ';เปลี่ยน PP...;'); else: userText
```

### §9.3 — COU vs POU Variant Differences

| Attribute | COU variant | POU variant |
|-----------|------------|------------|
| XSLT scope param | `$childOu` | `$parentOu` |
| RefID | `$childOu/RefId` | `$parentOu/RefId` |
| varPP source | `$childOu/Agreement/Offers[...]` | `$parentOu/Agreement/Offers[...]` |
| PreExecCheck helper | `GetXMLForAgreementInChildOU` | `GetXMLForAgreement` |
| Payload structure | Identical | Identical |

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID suffix | _REQ |
| OPERATION_NAME | "CCBS_CHANGE_PP_OU" |
| TARGET_SYSTEM | OMX_FM |
| AUDIT_TRACE | "Request Sent for CCBS_CHANGE_PP_OU" |
| WritePayload gate | `$globalVariables/OMX_OM/WritePayload=="true"` |

Both COU and POU scopes send the Logger event (same Logger XSLT).

---

## §12 — Activity Status Management

| Condition | Action |
|-----------|--------|
| Any event dispatched (isSkipped==false) | `Status = GetActivityStatusString("1", false)`; `SendDataToDB(orderRequest)` |
| No events dispatched (isSkipped==true) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)` | Clear pending requests on resubmit |
| `Helpers.GetXMLForAgreementInChildOU(orderRequest, childOu.Agreement.RefId, parentOu.RefId)` | Build PreExecCheck XML for COU scope |
| `Helpers.GetXMLForAgreement(orderRequest, parentOu.Agreement.RefId)` | Build PreExecCheck XML for POU scope |
| `Helpers.GetSplOffIndForSoc(orderRequest, soc)` | Lookup SPECIAL_OFFER_INDICATOR for a SOC code |
| `Helpers.GetActivityStatusString("1", false)` | Return "IN PROGRESS" status string |
| `Helpers.SendDataToDB(orderRequest)` | Persist order state |
| `Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")` | Skip this activity |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |
| `XPath.evalAsInt(count(Agreement/Offers))` | countOfers for sequence increment |
| `XPath.evalAsInt(count(Agreement/*/RelatedOffersArray))` | countRelatedOffersArray |
| `XPath.evalAsInt(Agreement/AgreementId)` | agreementNo |
| `XPath.evalAsString(ActivityReason or "CREQ")` | activityReason |
| `XPath.evalAsString(tib:if-absent(Account[AgreementId=...]/AccountID,...))` | accountId |
| `DateTime.addDay(DateTime.now(),1)` | Compute tomorrow for LargeCustomer LogicalDate |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_CHANGE_PP_OU (rule)
├── isActResub = (RequestCount>0 && IsOrderResubmitted)
├── [if isActResub] PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── [if LargeCustomerIndicator=89] DateTime.addDay(now,1) → tomorrowLogicalDate
└── try {
    ├── [COU loop: for each ChildOU]
    │   ├── [if ChildOU.Agreement.Offers@length > 0]
    │   │   ├── GetXMLForAgreementInChildOU(...)  → sXML
    │   │   ├── XPath.execute(PreExecCheck)        → chkRes
    │   │   ├── [if chkRes=="true"]
    │   │   │   ├── XPath.evalAsInt(count(Offers))
    │   │   │   ├── XPath.evalAsInt(count(*/RelatedOffersArray))
    │   │   │   ├── XPath.evalAsInt(AgreementId)
    │   │   │   ├── XPath.evalAsString(ActivityReason or "CREQ")
    │   │   │   ├── XPath.evalAsString(UserText)
    │   │   │   ├── XPath.evalAsString(tib:if-absent(Account[...]/AccountID,...))
    │   │   │   ├── [isSharedAllowance detection loop]
    │   │   │   │   └── GetSplOffIndForSoc() → "CAP"? → capSoc=true
    │   │   │   ├── Event.createEvent(CCBS_CHANGE_PP_OU [COU variant])
    │   │   │   ├── Event.Ext.sendEventImmediate(reqEvent)
    │   │   │   ├── RequestCount++ (if !isActResub)
    │   │   │   ├── isSkipped = false
    │   │   │   └── Event.Ext.sendEventImmediate(Logger)
    ├── [POU: same flow with parentOu and GetXMLForAgreement]
    ├── [if !isSkipped] Status="1"; SendDataToDB(orderRequest)
    └── [else] SkipActivity("4")
} catch → HandleActivityException()
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Process COU before POU within each ParentOU iteration. |
| R2 | PurgePendingRequestsBeforeResubmit on isActResub — critical for idempotency. |
| R3 | varPP = Offers[ServiceType=80 and FE_OR_CCBS=FE][1] — always the FE price plan offer. |
| R4 | Shared allowance: SPECIAL_OFFER_INDICATOR=CSH + RelatedOffers where GetSplOffIndForSoc=="CAP" → add static "Agreement level offer instance ID" parameterInfoWithSoc with capSoc. |
| R5 | LargeCustomerIndicator=89 → EnclosedClientInfo. LogicalDate = varPP.EffectiveDate if exists, else tomorrow midnight. |
| R6 | FUT_TYPE NXTPP/FUTPP → append Thai future order text to UserText. |
| R7 | SOC_SEQ_NO sequence pre-allocation: incrementByCount = countOfers + countRelatedOffersArray. |
| R8 | ChargeDistributionDetailsInfo for RCIndicator=65 PP offer and RelatedOffersArray[RcIndicator=65]. |

### Design Notes

| Note | Severity | Detail |
|------|----------|--------|
| Fan-in: boolean vs RequestCount comparison | [HIGH] | Response RF uses `boolean(Response["000"])` not `count(...)==RequestCount`. If both COU and POU dispatch (RequestCount=2), activity completes after the FIRST "000" response. The second may be lost or processed after state advanced. Architecturally fragile. |
| tomorrowLogicalDate computed in BE but XSLT uses its own calculation | [LOW] | The BE-computed var is effectively unused in XSLT (XSLT recalculates in else branch). |
| varPP uses [1] index | [INFO] | Only the first FE PP offer drives the payload. Multiple PP offers per Agreement not expected but should be validated. |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_CHANGE_PP_OU {
    attribute { priority = 5; forwardChain = true; }
    declare { OrderRequest orderRequest; Activity orderCurrentActivity; }
    when { /* extId / ActivityID=="CCBS_CHANGE_PP_OU" / NextActivityID / Status=="WAITING" */ }
    then {
        isActResub = (RequestCount>0 && IsOrderResubmitted);
        try {
            if(isActResub) PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
            if(LargeCustomerIndicator==89)
                tomorrowLogicalDate = DateTime.format(DateTime.addDay(now,1),"yyyy-MM-dd'T'00:00:00XXX");

            for(iPou...) {
                // COU loop: ChildOU.Agreement.Offers
                for(iCou...) {
                    if(childOu.Agreement.Offers@length > 0) {
                        chkRes = GetXMLForAgreementInChildOU + XPath.execute(PreExecCheck);
                        if(chkRes=="true") {
                            countOfers = XPath.evalAsInt(count(Agreement.Offers));
                            countRelatedOffersArray = XPath.evalAsInt(count(Agreement/*/RelatedOffersArray));
                            agreementNo = childOu.Agreement.AgreementId;
                            activityReason = XPath ... "CREQ";
                            userText = childOu.Agreement.AgreementActivityInfo.UserText;
                            accountId = tib:if-absent(Account[AgreementId]/AccountID, Account[AgreementRefId]/AccountID);
                            // isSharedAllowance detection
                            for(iOUSoc: ServiceType=80 && FE_OR_CCBS=FE) {
                                if(SPECIAL_OFFER_INDICATOR=CSH) {
                                    for(iRelSoc: GetSplOffIndForSoc=="CAP") capSoc=soc; isSharedAllowance=true;
                                }
                            }
                            reqEvent = Event.createEvent("xslt://CCBS_CHANGE_PP_OU [COU variant]"); /* see §9 */
                            Event.Ext.sendEventImmediate(reqEvent); RequestCount++; isSkipped=false;
                            Logger("Request Sent for CCBS_CHANGE_PP_OU");
                        }
                    }
                }
                // POU loop: ParentOU.Agreement.Offers (same pattern)
                if(parentOu.Agreement.Offers@length > 0) {
                    chkRes = GetXMLForAgreement + XPath.execute(PreExecCheck);
                    if(chkRes=="true") {
                        // same compute + isSharedAllowance
                        reqEvent = Event.createEvent("xslt://CCBS_CHANGE_PP_OU [POU variant]"); /* see §9 */
                        Event.Ext.sendEventImmediate(reqEvent); RequestCount++; isSkipped=false;
                        Logger("Request Sent for CCBS_CHANGE_PP_OU");
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

## §19 — Response Message Rule (Response_CCBS_CHANGE_PP_OU)

### §19.1 — Overview

Handles incoming responses from the CCBS FM Price Plan change. Creates a `ResponseBase` concept (with **ReferenceId** mapped from `RefID`), appends to `currActivity.Response`, sends Logger audit, and checks if ANY "000" response exists. Returns "true" as soon as any success response arrives (not compared to RequestCount).

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Audit correlation |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_CHANGE_PP_OU` | Incoming response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response array target |

### §19.3 — ResponseBase Concept Construction

```text
createObject (Concepts.FM.Base.ResponseBase)
└── object
    ├── @extId             ← OMXUtils.generateTrackingID()          [Always]
    ├── ResponseCode       ← $eventResponse/ResponseCode            [Conditional: if exists]
    ├── ResponseMessage    ← $eventResponse/ResponseMsg             [Conditional: if exists]
    ├── CompletionStatus   ← $eventResponse/CompletionStatus        [Conditional: if exists]
    └── ReferenceId        ← $eventResponse/RefID                   [Conditional: if exists]

NOTE: ReferenceId IS populated (from eventResponse.RefID) — unlike OMX_ADD_FUT_OFFERS.
```

### §19.4 — Response Completion Logic

| Attribute | Value |
|-----------|-------|
| Success XPath | `boolean($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | **ANY** response with "000" suffix → return "true" |
| RequestCount comparison | **None** — does NOT check RequestCount |

> [HIGH] Fan-in design defect: returns "true" as soon as ANY response has "000" code, regardless of how many events were dispatched (RequestCount). If both COU and POU dispatch (RequestCount=2), activity completes after the FIRST "000" — the second response may be lost. This contrasts with the standard fan-in pattern (`count("000") == RequestCount`) used in most other FMs. Should be investigated during migration. If in production only one scope qualifies per run, this may not manifest in practice — but it is architecturally fragile.

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID suffix | _RES |
| OPERATION_NAME | "CCBS_CHANGE_PP_OU" |
| TARGET_SYSTEM | OMX_FM |
| AUDIT_TRACE | "Response received for CCBS_CHANGE_PP_OU" |
| payload | $eventResponse (conditional: WritePayload=="true") |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
