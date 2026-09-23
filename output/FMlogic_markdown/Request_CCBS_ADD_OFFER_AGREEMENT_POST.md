# Request_CCBS_ADD_OFFER_AGREEMENT_POST

> Adds offers to CCBS agreements per OU (POST-type) — per-offer CCBS_CREATE_AGREE with SOC deduplication, chargeDistribution, parameterInfo, and LargeCustomer date override.

**System:** CCBS | **Priority:** 5 | **Author:** RS33-BANDIT  
**Event:** CCBS_CREATE_AGREE | **Pattern:** assertEvent+ActionRequestEvent per offer  
**Fan-in:** ActionResponseEvent | **Granularity:** one event per qualifying offer per OU

> **Key features:**
> - Per-offer send granularity (NOT per OU)
> - SOC deduplication pre-pass builds parallel alSOCs/alPropVal arrays for PLG/CAP parameterInfo injection
> - LargeCustomerIndicator=89 → logicalDateVal = tomorrow 00:00:00 (computed but not passed to XSLT — possible dead code)
> - FE_OR_CCBS filter from ExtendedInfo passed to PreExecCheck
> - chargeDistributionDetailsInfos: POU uses Account.AccountID; COU uses offer.TargetPayChannelId
> - **Bug**: COU CompletionStatus==2 check uses POU refId instead of refCOUId

---

## §1 Overview & Purpose

Sends one `CCBS_CREATE_AGREE` event per qualifying Agreement.Offer per OU (POU then COU). Pre-pass collects unique SOC indicators for "Agreement level offer instance ID" parameterInfo injection. Supports `LargeCustomerIndicator=89` date override, `FE_OR_CCBS` filter for PreExecCheck, and `chargeDistributionDetailsInfos` per offer.

| Attribute | Value |
|-----------|-------|
| Rule File | `Request_CCBS_ADD_OFFER_AGREEMENT_POST.rule` |
| Response File | `Response_CCBS_ADD_OFFER_AGREEMENT_POST.rulefunction` |
| Author | RS33-BANDIT |
| Priority | 5 |
| Target System | CCBS |
| Event name | CCBS_CREATE_AGREE |
| Response concept | CCBSCreateAgreementRes (4 standard fields) |
| Send pattern | Event.assertEvent + IntraActivitySequencing.ActionRequestEvent |
| JMSCorrelationID | OMXTrackingId |
| Granularity | Per qualifying offer per OU (one event per offer) |
| Fan-in | IntraActivitySequencing.ActionResponseEvent |
| SendFirstRequestEvent | Yes — called after all sends |

---

## §4 Rule Conditions (WHEN)

| Condition | Purpose |
|-----------|---------|
| `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity pointer |
| `ActivityID == "CCBS_ADD_OFFER_AGREEMENT_POST"` | FM match |
| `orderRequest.ProcessFlow.NextActivityID == "CCBS_ADD_OFFER_AGREEMENT_POST"` | Flow alignment |
| `orderCurrentActivity.Status == "WAITING"` | Prevents re-firing |

---

## §5 Execution Flow

1. **Init** — If resubmit → PurgePendingRequestsBeforeResubmit. Read LogicalDate concept. If `LargeCustomerIndicator==89` → logicalDateVal = tomorrow 00:00:00. Initialize `alSOCs` and `alPropVal` arrays
2. **SOC deduplication pre-pass** — Loop ALL POU+COU → Agreement.Offers → RelatedOffersArray. Collect unique SOCs; for each → `GetSplOffIndForSoc` → propValue (PLG/CAP/other)
3. **POU loop** — Per POU: clear arrays. Per Agreement.Offer: FE_OR_CCBS filter + CompletionStatus==2 check + PreExecCheck. Collect qualifying offers into `agreeOffers`. Send one CCBS_CREATE_AGREE per offer: assertEvent + ActionRequestEvent. isSkipped=false
4. **COU loop** — Same, per COU within POU. ⚠ CompletionStatus check uses POU refId (bug)
5. **Post-loop** — If !isSkipped → SendFirstRequestEvent + Status="1" + SendDataToDB. Else → SkipActivity("4")
6. **Exception** → HandleActivityException

---

## §7 Special Logic

### §7.1 LargeCustomer Date Override

```java
if(XPath.evalAsBoolean("$orderRequest/OrderData/Customer/CustomerGeneralInfo/LargeCustomerIndicator=89")) {
    logicalDateVal = DateTime.format(DateTime.addDay(DateTime.now(), 1), "yyyy-MM-dd'T'00:00:00XXX");
}
// Note: logicalDateVal is computed but not included in XSLT params — may be dead code
```

### §7.2 SOC Deduplication Pre-pass

```java
// Collect unique SOCs across ALL offers' RelatedOffersArray (POU + COU)
for each POU { for each Offer { for each RelatedOffersArray {
    soc = RelatedOffersArray.Soc;
    if(!Collections.contains(alSOCs, soc)) {
        Collections.add(alSOCs, soc);
        propValue = GetSplOffIndForSoc(orderRequest, soc); // returns "PLG", "CAP", or other
        Collections.add(alPropVal, propValue);
    }
}}}
// Result: parallel arrays stralSoc[i] → stralPropVal[i]
// Used: if propValue=="PLG" or "CAP" → add "Agreement level offer instance ID" parameterInfo
```

### §7.3 parameterInfo "Agreement level offer instance ID" Injection

```xml
<!-- For each RelatedOffersArray in agreeOffersArray — inject if propValue=="PLG" or "CAP" -->
<ns:parameterInfos>
  <ns:name>Agreement level offer instance ID</ns:name>
  <ns:values><!-- parent offer Soc (from agreeOffersArray[RelatedOffersArray[Soc=$varSoc]]/Soc) --></ns:values>
  <ns:soc><!-- RelatedOffer Soc --></ns:soc>
</ns:parameterInfos>
```

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding (POU Variant)

| Param | Binding |
|-------|---------|
| `orderRequest` | OrderRequest concept |
| `i` | POU loop index (0-based) |
| `var` | i+1 (1-based XPath index) |
| `globalVariables` | Global variables |
| `agreeOffersArray` | Qualified offers array (concept array) |
| `agrOffer` | Current offer concept (loop variable) |
| `stralSoc` | SOC dedup array (from pre-pass) |
| `stralPropVal` | PropValue array (PLG/CAP/other, from pre-pass) |
| `acctRefId` | `Account[AgreementRefId=POU.Agreement.RefId]/RefId` |

COU Variant also includes: `x` (COU index), `var1` = x+1, `childOuAgreeOffersArray`, `agreeOffersArray` (POU offers for "Agreement level offer instance ID" lookup).

### §9.3 JMS / Event Header Fields

| Header | Source | Conditional? |
|--------|--------|-------------|
| `JMSPriority` | `$orderRequest/OrderPriority` | [Always] |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | [Always] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Always] |
| `RefID` | `POU: ParentOU[$var]/Agreement/RefId` / `COU: ChildOU[$var1]/Agreement/RefId` | [Always] |
| `UserName` / `PassWord` | `$orderRequest/OrderData/User\|Password` | [Credential-gated: IsEnableUserPass='true'] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Conditional] |
| `CES` | `$orderRequest/OrderData/CES` | [Conditional] |

### §9.5 Payload Structure (ns1:CreateAgreementRequest)

- **ns2:GetSequenceValueRequest**: sequenceName=SOC_SEQ_NO; incrementByCount = count(offers) + count(relatedOffers)
- **ns:UpdateAgreementOnUnitRequest**:
  - `customerIdInfo/customerNo` = CustomerId
  - `unitIdInfo/chNodeId` = OUId
  - `agreementTypeInfo/agreementType` = AgreementType (conditional)
  - `offersToAdd/srvAgrInfo` per offer: dealerCode, deployMode, effectiveDate, expirationDate, name, relatedOffers[], serviceType, soc
  - `parameterInfos` (3 sources): offer ParameterInfo, RelatedOffer ParameterInfo, "Agreement level offer instance ID" (PLG/CAP SOCs)
  - `chargeDistributionDetailsInfos`: per offer (RCIndicator≠64): soc + targetPayChannelId (POU: Account.AccountID; COU: offer.TargetPayChannelId)
  - `agreementGeneralInfo`: dealerCode + agreementDescription
  - `activityInfo/activityReason`: AgreementActivityInfo.ActivityReason else default "CREQ"

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority        ← $orderRequest/OrderPriority                 [Always]
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId       [Always]
    ├── OrderID            ← $orderRequest/OrderData/OrderID             [Always]
    ├── RefID              ← Agreement/RefId (POU|COU)                   [Always]
    ├── UserName/PassWord  ← OrderData/User|Password                     [Credential-gated]
    ├── OrderType          ← $orderRequest/OrderData/OrderType           [Conditional]
    ├── CES                ← $orderRequest/OrderData/CES                 [Conditional]
    └── payload
        └── ns1:CreateAgreementRequest
            ├── ns2:GetSequenceValueRequest
            │   ├── ns2:sequenceName    ← "SOC_SEQ_NO"                  [Always]
            │   └── ns2:incrementByCount← count(offers+relatedOffers)   [Always]
            └── ns:UpdateAgreementOnUnitRequest
                ├── ns:customerIdInfo/ns:customerNo ← CustomerId         [Always]
                ├── ns:unitIdInfo/ns:chNodeId        ← OUId              [Always]
                ├── ns:agreementTypeInfo/ns:agreementType ← AgreementType [Conditional]
                ├── ns:offersToAdd/ns:srvAgrInfo (per offer)
                │   ├── ns:dealerCode    ← DealerCode                    [Conditional]
                │   ├── ns:deployMode / effectiveDate / expirationDate   [Conditional]
                │   ├── ns:name          ← OfferName                     [Conditional]
                │   ├── ns:relatedOffers (per RelatedOffer): name, serviceType, soc
                │   ├── ns:serviceType   ← ServiceType                   [Conditional]
                │   └── ns:soc           ← Soc                           [Always]
                ├── ns:parameterInfos (3 sources: offer + relatedOffer + PLG/CAP)
                ├── ns:chargeDistributionDetailsInfos (RCIndicator≠64)
                ├── ns:agreementGeneralInfo: dealerCode + agreementDescription
                └── ns:activityInfo/ns:activityReason ← ActivityReason|"CREQ" [Always]
```

---

## §11 Audit Logging

| Direction | OPERATION_NAME | AUDIT_TRACE | Send Method |
|-----------|---------------|-------------|-------------|
| Request | `"CCBS_ADD_OFFER_AGREEMENT_POST"` | `"Request Sent for CCBS_ADD_OFFER_AGREEMENT_POST"` | Event.Ext.sendEventImmediate (per offer) |
| Response | `"CCBS_ADD_OFFER_AGREEMENT_POST"` | `"Response received for CCBS_ADD_OFFER_AGREEMENT_POST"` | Event.Ext.sendEventImmediate |

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one send | "1" IN_PROGRESS | `SendFirstRequestEvent` + `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All offers skipped | SKIPPED | `SkipActivity("4")` |

---

## §15 Function Dependency Tree

```text
Request_CCBS_ADD_OFFER_AGREEMENT_POST
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── Instance.getByExtIdByUri("LogicalDate", ...)                 [LogicalDate concept]
├── DateTime.addDay / DateTime.format                            [if LargeCustomerIndicator=89]
├── GetSplOffIndForSoc(orderRequest, soc)                        [per unique SOC in pre-pass]
├── GetXMLForAgreementOfferFilterWithExtendedInfo(...)           [POU PreExecCheck per offer]
├── GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo(...)  [COU PreExecCheck per offer]
├── Event.createEvent("xslt://CCBS_CREATE_AGREE")
├── Event.assertEvent(createAgreeEvent)
├── IntraActivitySequencing.ActionRequestEvent(...)
├── Event.Ext.sendEventImmediate(Logger)                         [per offer]
├── IntraActivitySequencing.SendFirstRequestEvent(...)
├── GetActivityStatusString("1", false)
├── SkipActivity("4") | SendDataToDB
└── HandleActivityException(...)

Response_CCBS_ADD_OFFER_AGREEMENT_POST
├── OMXUtils.generateTrackingID()
├── Instance.createInstance(CCBSCreateAgreementRes)
├── Event.Ext.sendEventImmediate(Logger)
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
```

---

## §17 Migration Notes & Recommendations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| COU CompletionStatus==2 check uses POU `refId` instead of `refCOUId` — COU resubmit guard never triggers | [HIGH] | Fix to use `refCOUId` in COU loop |
| `logicalDateVal` computed with LargeCustomer override but not passed to XSLT — dead code | [MEDIUM] | Add logicalDateVal as XSLT param for EffectiveDate if intended |
| One event per offer — large fan-out for OUs with many offers | [MEDIUM] | Monitor RequestCount; ensure ActionResponseEvent handles large fan-out |
| SOC pre-pass alSOCs/alPropVal cleared per POU inside loop — verify pre-pass fills correctly before sends | [LOW] | Review collect/clear pattern; pre-pass is at outer level but clears are inside POU loop |
| parameterInfos PLG/CAP injection only for relatedOffer SOCs — may miss special indicators | [LOW] | Review `GetSplOffIndForSoc` return values vs CCBS requirements |

---

## §18 Full Source Code

```java
/**
 * @author RS33-BANDIT
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_ADD_OFFER_AGREEMENT_POST {
    attribute { priority = 5; forwardChain = true; }
    when { ... ActivityID == "CCBS_ADD_OFFER_AGREEMENT_POST" ... }
    then {
        boolean isActResub = ...;
        try {
            Object alSOCs = Collections.List.createArrayList();
            Object alPropVal = Collections.List.createArrayList();
            logicalDateVal = logicalDateRes.LogicalDate;
            if(LargeCustomerIndicator==89)
                logicalDateVal = DateTime.format(DateTime.addDay(now, 1), "yyyy-MM-dd'T'00:00:00XXX");
            if(isActResub) PurgePendingRequestsBeforeResubmit(...);

            // SOC deduplication pre-pass: collect unique SOCs+propValues across ALL OUs
            for each POU → Agreement.Offers → RelatedOffersArray {
                if(!contains(alSOCs, soc)) { add(alSOCs, soc); add(alPropVal, GetSplOffIndForSoc(...)); }
            }

            for(int i=0; i<iPOULen; i++) {
                Collections.clear(alSOCs); Collections.clear(alPropVal);

                // POU: collect qualifying offers → agreeOffers
                for each POU[i].Agreement.Offer {
                    filter = ExtendedInfo[FE_OR_CCBS]; CompletionStatus check by refId;
                    PreExecCheck via GetXMLForAgreementOfferFilterWithExtendedInfo;
                    if(chkRes=="true") add to agreeOffers;
                }
                for each agreeOffers {
                    createAgreeEvent = Event.createEvent("xslt://CCBS_CREATE_AGREE");
                    /* §9.8 POU: params orderRequest,i,var,globalVariables,agreeOffersArray,agrOffer,
                       stralSoc,stralPropVal,acctRefId — one event per offer */
                    Event.assertEvent(createAgreeEvent);
                    IntraActivitySequencing.ActionRequestEvent(createAgreeEvent, orderCurrentActivity);
                    Event.Ext.sendEventImmediate(Logger);
                    isSkipped = false;
                }

                for each COU[x] {
                    // COU: same but GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo
                    // ⚠ Bug: CompletionStatus check uses refId (POU) instead of refCOUId
                }
            }
            if(!isSkipped) {
                IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
                Status="1"; SendDataToDB();
            } else SkipActivity("4");
        } catch(Exception ae) { HandleActivityException(...); }
    }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

Uses CCBS pattern: creates `CCBSCreateAgreementRes` (4 standard fields: ResponseCode, ResponseMessage, CompletionStatus, ReferenceId). Fan-in via `IntraActivitySequencing.ActionResponseEvent`. OPERATION_NAME="CCBS_ADD_OFFER_AGREEMENT_POST".

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | OrderRequest | Order context |
| `eventResponse` | CCBS_CREATE_AGREE | CCBS response event |
| `currActivity` | Activity | Response array + fan-in |

### §19.4 Fan-in Logic

```java
if(IntraActivitySequencing.ActionResponseEvent(currActivity)) return "true";
else return "false";
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
