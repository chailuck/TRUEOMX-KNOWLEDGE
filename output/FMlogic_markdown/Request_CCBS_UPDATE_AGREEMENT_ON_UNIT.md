# Request_CCBS_UPDATE_AGREEMENT_ON_UNIT

> Updates offers on an agreement unit for both Parent OU and Child OU — batch per-OU dispatch with ADD/REMOVE action support, SOC sequence pre-allocation, and shared-allowance parameterInfo injection.

---

## §1 — Overview & Purpose

This rule dispatches **CCBS UpdateAgreementOnUnit** requests for each OU (Parent OU first, then Child OU) that has qualifying agreement offers. Unlike per-offer dispatching, it **batches all qualifying offers for a given OU into a single request**.

Key behaviours:
- Collects unique SOCs from RelatedOffersArray across POU + all child OUs (per POU context) to build shared-allowance indicator lookup table
- Validates `Parameter[1]`: blank = use offer's existing Action; ADD/REMOVE = override all offer Actions; other = DATA_ISSUE exception
- Checks `LargeCustomerIndicator=89` → computes tomorrow's date for `logicalDateVal` — **never passed to XSLT (dead code)**
- Applies **isActResub** guard: if `RequestCount>0 AND IsOrderResubmitted` → `PurgePendingRequestsBeforeResubmit`
- Per-OU **reqSuccess** check: skips OU if Response with `ReferenceId==ouRefId AND CompletionStatus==2` already exists
- Applies `PreExecCheck` via `GetXMLForAgreementOfferFilterWithExtendedInfo` (POU) / `GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo` (COU)
- SOC_SEQ_NO sequence pre-allocated when any ADD offers present
- Emits `chargeDistributionDetailsInfos` for ADD offers with RCIndicator != 64
- Injects "Agreement level offer instance ID" parameterInfos for PLG/CAP/CSH socs in RelatedOffersArray
- l3ActivityDate logic: EOC channel → ADD[1].EffectiveDate; ADD+BD+notFuture → ADD[1].EffectiveDate; REMOVE+BD+notFuture → REMOVE[1].ExpirationDate

> **[MEDIUM] BUG — COU agreementTypeInfo copies POU value:** The COU XSLT checks `$cou/Agreement/AgreementType != ''` but emits `$ou/Agreement/AgreementType`. COU agreements always receive the POU's agreement type.

> **[MEDIUM] BUG — COU $expType undeclared in XSLT:** The COU XSLT param list omits `$expType` but the activityInfo choose block references it. REMOVE+BD l3ActivityDate will never be set for COU scope.

> **[MEDIUM] Dead code — logicalDateVal:** Computed for LargeCustomerIndicator=89 but not declared as XSLT param in either POU or COU event. Silently discarded.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPDATE_AGREEMENT_ON_UNIT` |
| Priority | 5 |
| forwardChain | true |
| Rule type | External OMXFM dispatcher (batch per-OU) |
| Backend system | CCBS — AgreementServices / UpdateAgreementOnUnit |
| Dispatch pattern | Per-OU: POU first, then each COU (one event per OU with all qualifying offers batched) |
| Parameter[1] usage | Action override (ADD/REMOVE) or no-op if blank |
| Response rulefunction | `Response_CCBS_UPDATE_AGREEMENT_ON_UNIT` |
| Fan-in mechanism | `IntraActivitySequencing.ActionResponseEvent(currActivity)` helper |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order data including Customer, ParentOU, ChildOU, Agreement, Offers |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — matched on extId, ActivityID, Status, NextActivityID |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity matches current order's next step |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_UPDATE_AGREEMENT_ON_UNIT"` | Correct FM type |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_UPDATE_AGREEMENT_ON_UNIT"` | Order flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity is ready to fire |

---

## §5 — Execution Flow Diagram

1. Collect unique SOCs from RelatedOffersArray across POU + all COU offers → build `alSOCs`/`alPropVal` arrays via `GetSplOffIndForSoc`
2. Check `isActResub`: if true → `PurgePendingRequestsBeforeResubmit`
3. Check `LargeCustomerIndicator=89` → override `logicalDateVal` to tomorrow (dead code — not passed to XSLT)
4. Read `Parameter[1]`: if not blank, validate ADD/REMOVE; otherwise DATA_ISSUE exception
5. **POU loop**: for each POU with Agreement → collect qualifying offers (apply param override, FE_OR_CCBS filter, reqSuccess check, PreExecCheck)
6. If POU `agreeOffers` non-empty → create XSLT event with all offers batched → assertEvent → ActionRequestEvent → Logger audit → `isSkipped=false`
7. **COU loop**: for each COU with Agreement → same collect/dispatch pattern with `cOuRefId`
8. After all OUs: if `!isSkipped` → `SendFirstRequestEvent` + Status="1" + `SendDataToDB`; else `SkipActivity("4")`

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

### §6.1 Initialization

| Variable | Value |
|----------|-------|
| `alSOCs` | Empty ArrayList — unique SOC list for shared-allowance lookup |
| `alPropVal` | Empty ArrayList — corresponding GetSplOffIndForSoc result (PLG/CAP/CSH/etc.) |
| `logicalDateVal` | Current LogicalDate concept value; overridden to tomorrow if LargeCustomerIndicator=89 (dead code) |
| `isActResub` | `orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted` |
| `isSkipped` | Starts `true`; set to `false` when any request is dispatched |

### §6.2 SOC Collection Loop (per POU)

For each POU iteration, `alSOCs` and `alPropVal` are **reset** (`Collections.clear`). Then SOCs are collected from:
- `pOu.Agreement.Offers[p].RelatedOffersArray[q].Soc` — for all POU agreement offers
- `pOu.ChildOU[u].Agreement.Offers[v].RelatedOffersArray[w].Soc` — for all COU agreement offers under the same POU

Uniqueness enforced via `Collections.contains(alSOCs, soc)`. `GetSplOffIndForSoc` called for each new SOC → stored parallel in `alPropVal`.

### §6.3 Parameter[1] Validation

| Parameter[1] value | Behaviour |
|--------------------|-----------|
| blank / empty | No-op — offer's existing `Action` used as-is |
| `ADD` | Override all offers' `Action = "ADD"` |
| `REMOVE` | Override all offers' `Action = "REMOVE"` |
| any other value | `throw Exception("DATA_ISSUE", "Param is missing.", null)` |

### §6.4 Per-OU Offer Collection Logic

For each OU, for each offer:
1. Apply param override: `agof.Action = param` if param non-blank
2. Read `FE_OR_CCBS` ExtendedInfo → `filter`
3. Check reqSuccess: scan `Response[]` for matching OU RefId + CompletionStatus==2
4. If not reqSuccess: evaluate `PreExecCheck` via appropriate helper
5. If chkRes=="true": add offer to `agreeOffers`; capture `acction`, `effType`, `expType`

> **effType fallback:** If `EFF_TYPE` ExtendedInfo is blank, falls back to `OfferActivityDate`. Same fallback for `expType`/`EXP_TYPE`. Last qualifying offer's values win (overwritten per loop iteration).

---

## §7 — Data Extraction

### §7.1 reqSuccess Check (Per-OU)

The reqSuccess guard is checked **per OU** (not per offer). If any previous response exists for the OU's RefId with CompletionStatus==2, all offers in that OU are skipped entirely.

### §7.2 SOC/PropVal Parallel Arrays

| Array | Index mapping |
|-------|---------------|
| `strAlSoc[i]` | Unique SOC string |
| `strAlPropVal[i]` | `GetSplOffIndForSoc(orderRequest, soc)` result at same index |

Used in XSLT to emit "Agreement level offer instance ID" parameterInfos for PLG/CAP/CSH indicator socs in RelatedOffersArray.

### §7.3 FE_OR_CCBS Filter

Extracted per-offer via XPath: `$agof/ExtendedInfo[Name="FE_OR_CCBS"]/Value`. Passed to `GetXMLForAgreementOffer...FilterWithExtendedInfo` helper so PreExecCheck XPath can filter on this value.

### §7.4 acctRefId Lookup (in XSLT)

Inside the XSLT: `$var = $ou/Agreement/RefId` → `$acctRefId = $orderRequest/OrderData/Customer/Account[AgreementRefId=$var]/RefId`. Used for `chargeDistributionDetailsInfos.targetPayChannelId = Account[RefId=$acctRefId]/AccountID`.

---

## §8 — System & Integration Dependencies

### §8.1 ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_UPDATE_AGREEMENT_ON_UNIT` | Request to CCBS UpdateAgreementOnUnit (one per qualifying OU) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Audit trail per dispatched request |

### §8.2 Backend API Details

| System | Operation | Schema namespace |
|--------|-----------|-----------------|
| CCBS | UpdateAgreementOnUnit | `http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/AgreementServices/UpdateAgreementOnUnitRequest` |

SOC_SEQ_NO schema: `http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/SubscriberServices/SequenceValue/Schema.xsd`

### §8.3 ExtendedInfo Fields Required

| Key | Required/Optional | Usage |
|-----|------------------|-------|
| `FE_OR_CCBS` | Optional | PreExecCheck filter parameter |
| `EFF_TYPE` | Optional | Effective type (BD → l3ActivityDate from EffectiveDate); falls back to OfferActivityDate |
| `EXP_TYPE` | Optional | Expiration type (BD → l3ActivityDate from ExpirationDate); falls back to OfferActivityDate |

### §8.4 Global Variable Dependencies

| Path | Usage |
|------|-------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Gate for UserName/PassWord in event header |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in Logger |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in Logger |
| `OMX_OM/WritePayload` | Gate for payload in Logger |
| `OMX-OM/PoolingPooled/PooledPrefix` | Default "POOLED_OFFER_INSTANCE_ID" — prefix for pooled ExtendedInfo key in response RF |
| `OMX-OM/PoolingPooled/PooledIndicator` | Default "RPD,CPD" — comma-separated pooled soc indicators in response RF |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| XSLT Param | Bound From (POU) | Bound From (COU) |
|-----------|-----------------|-----------------|
| `$orderRequest` | orderRequest concept | orderRequest concept |
| `$pOuRefId` / `$cOuRefId` | pOuRefId | cOuRefId |
| `$ou` | current POU | current POU (same) |
| `$cou` | — (not in POU XSLT) | current COU |
| `$agreeOffersArray` | qualified POU offers | qualified COU offers |
| `$acction` | last qualifying offer's Action | last qualifying offer's Action |
| `$effType` | last qualifying offer's EFF_TYPE | last qualifying offer's EFF_TYPE |
| `$expType` | last qualifying offer's EXP_TYPE | **[MEDIUM] MISSING — not declared in COU XSLT** |
| `$isFuture` | String.startsWith(Channel,"FUT_") | String.startsWith(Channel,"FUT_") |

### §9.2 SOC_SEQ_NO Pre-allocation

Emitted when: `count(ADD offers) > 0 OR count(ADD offers/RelatedOffersArray) > 0`

```xml
<ns1:GetSequenceValueRequest>
  <ns1:sequenceName>SOC_SEQ_NO</ns1:sequenceName>
  <ns1:incrementByCount>{count(ADD) + count(ADD/RelatedOffersArray)}</ns1:incrementByCount>
</ns1:GetSequenceValueRequest>
```

### §9.3 Core Payload Elements

| Element | Source | Condition |
|---------|--------|-----------|
| `ns:customerIdInfo/ns:customerNo` | `number($orderRequest/OrderData/Customer/CustomerId)` | Always |
| `ns:unitIdInfo/ns:chNodeId` | `$ou/OUId` (POU) / `$cou/OUId` (COU) | if OUId exists |
| `ns:agreementTypeInfo/ns:agreementType` | `$ou/Agreement/AgreementType` (POU) / **`$ou/Agreement/AgreementType` (COU — BUG)** | if exists and non-empty |
| `ns:offersToAdd/ns:srvAgrInfo[*]` | foreach agreeOffersArray[Action='ADD'] | Conditional |
| `ns:offersToRemove/ns:srvAgrInfo[*]` | foreach agreeOffersArray[Action='REMOVE'] | Conditional |
| `ns:parameterInfos` (main) | foreach agreeOffersArray/elements/ParameterInfo | if any |
| `ns:parameterInfos` (related) | foreach agreeOffersArray/elements/RelatedOffersArray/ParameterInfo | if any |
| `ns:parameterInfos` (shared allowance) | "Agreement level offer instance ID" for PLG/CAP/CSH socs | if ADD + propVal matches |
| `ns:chargeDistributionDetailsInfos` | foreach ADD offers with RCIndicator!=64 | Conditional |
| `ns:agreementGeneralInfo` | foreach ou.Agreement.AgreementGeneralInfo | if exists |
| `ns:activityInfo/ns:activityReason` | AgreementActivityInfo.ActivityReason or "CREQ" | Always |
| `ns:activityInfo/ns:userText` | AgreementActivityInfo.UserText | if exists |
| `ns:activityInfo/ns:l3ActivityDate` | 3-way choose (see below) | Conditional |

### §9.4 l3ActivityDate Logic

| Condition | Value | Note |
|-----------|-------|------|
| `Channel='EOC'` | `agreeOffersArray/elements[Action='ADD'][1]/EffectiveDate` | Highest priority |
| `acction='ADD' AND effType='BD' AND isFuture=false` | `agreeOffersArray/elements[Action='ADD'][1]/EffectiveDate` | Business-day activation |
| `acction='REMOVE' AND expType='BD' AND isFuture=false` | `agreeOffersArray/elements[Action='REMOVE'][1]/ExpirationDate` | **[MEDIUM] COU: $expType undeclared → never fires** |
| (none match) | — | No l3ActivityDate emitted |

### §9.5 XSLT Field Mapping Tree (POU Variant)

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                          [Always]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId                [Always]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID                      [Always]
    ├── RefID                    ← $pOuRefId                                            [Always]
    ├── UserName                 ← $orderRequest/OrderData/User                         [Credential-gated: IsEnableUserPass='true']
    ├── PassWord                 ← $orderRequest/OrderData/Password                     [Credential-gated: IsEnableUserPass='true']
    ├── OrderType                ← $orderRequest/OrderData/OrderType                    [Conditional: if exists]
    ├── CES                      ← $orderRequest/OrderData/CES                          [Conditional: if exists]
    └── payload
        └── ns:UpdateAgreementOnUnitRequest
            ├── ns1:GetSequenceValueRequest                                              [Conditional: ADD offers > 0]
            │   ├── ns1:sequenceName     ← "SOC_SEQ_NO"                                [Always]
            │   └── ns1:incrementByCount ← count(ADD) + count(ADD/RelatedOffersArray)  [Always]
            ├── ns:customerIdInfo
            │   └── ns:customerNo        ← number(CustomerId)                          [Always]
            ├── ns:unitIdInfo
            │   └── ns:chNodeId          ← $ou/OUId                                    [Conditional: if OUId exists]
            ├── ns:agreementTypeInfo                                                     [Conditional: AgreementType exists+nonempty]
            │   └── ns:agreementType     ← $ou/Agreement/AgreementType
            ├── ns:offersToAdd
            │   └── ns:srvAgrInfo[*]     ← foreach ADD offers                          [Conditional]
            ├── ns:offersToRemove
            │   └── ns:srvAgrInfo[*]     ← foreach REMOVE offers                       [Conditional]
            ├── ns:parameterInfos[*]     ← foreach offers/ParameterInfo                 [Conditional]
            ├── ns:parameterInfos[*]     ← foreach RelatedOffersArray/ParameterInfo     [Conditional]
            ├── ns:parameterInfos        ← "Agreement level offer instance ID"          [Conditional: PLG/CAP/CSH + ADD]
            ├── ns:chargeDistributionDetailsInfos[*]                                    [Conditional: ADD + RCIndicator!=64]
            │   ├── ns:soc               ← Soc
            │   └── ns:targetPayChannelId ← Account[RefId=$acctRefId]/AccountID
            ├── ns:agreementGeneralInfo  ← AgreementGeneralInfo                         [Conditional]
            └── ns:activityInfo
                ├── ns:activityReason    ← ActivityReason or "CREQ"                    [Always]
                ├── ns:userText          ← AgreementActivityInfo/UserText               [Conditional: if exists]
                └── ns:l3ActivityDate    ← 3-way choose                                 [Conditional]
```

---

## §10 — Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(System.nanoTime(), "_REQ")` |
| OPERATION_NAME | `"CCBS_UPDATE_AGREEMENT_ON_UNIT"` (static) |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `"Request Sent for CCBS_UPDATE_AGREEMENT_ON_UNIT"` (static) |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | copy of `$reqEvent` — gated on `WritePayload=true` |

One Logger event is fired per OU dispatch, after `ActionRequestEvent`.

---

## §11 — Activity Status Management

| Condition | Status call | Result |
|-----------|------------|--------|
| At least one request dispatched | `GetActivityStatusString("1", false)` + `SendDataToDB` | Activity waits for fan-in |
| No request dispatched (isSkipped=true) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | Activity skipped |

Also calls `SendFirstRequestEvent(orderCurrentActivity)` before status assignment when dispatching.

---

## §12 — Exception / Error Handling

| Exception type | Trigger | Handler |
|---------------|---------|---------|
| `DATA_ISSUE` | Parameter[1] is not blank, ADD, or REMOVE | `Exception.newException("DATA_ISSUE", "Param is missing.", null)` |
| Any exception | Any runtime error | `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §13 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `GetSplOffIndForSoc(orderRequest, soc)` | Returns special offer indicator (PLG/CAP/CSH/etc.) for a SOC |
| `GetXMLForAgreementOfferFilterWithExtendedInfo(...)` | Builds XML for POU offer PreExecCheck with FE_OR_CCBS filter |
| `GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo(...)` | Builds XML for COU offer PreExecCheck with FE_OR_CCBS filter |
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clears pending requests for resubmit |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Registers request event; increments RequestCount |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Dispatches first queued request |
| `BRMS.IsBlank(value)` | Returns true if null or empty |
| `SkipActivity(orderRequest, activity, "4")` | Marks activity as skipped |
| `SendDataToDB(orderRequest)` | Persists order state |
| `HandleActivityException(orderRequest, activity, exception, "")` | Exception handler |

---

## §14 — Function Dependency Tree

```text
Request_CCBS_UPDATE_AGREEMENT_ON_UNIT (rule)
├── RuleFunctions.Helpers.GetSplOffIndForSoc(orderRequest, soc)
├── RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── RuleFunctions.Helpers.BRMS.IsBlank(param)
├── RuleFunctions.Helpers.GetXMLForAgreementOfferFilterWithExtendedInfo(...)          [POU]
├── RuleFunctions.Helpers.GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo(...) [COU]
├── Event.createEvent("xslt://CCBS_UPDATE_AGREEMENT_ON_UNIT") × N OUs
├── Event.assertEvent(reqEvent)
├── RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
├── Event.Ext.sendEventImmediate(Logger event) × N OUs
├── RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(activity)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")
└── RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")
```

---

## §15 — Migration Notes & Recommendations

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| COU XSLT agreementTypeInfo emits `$ou/Agreement/AgreementType` instead of `$cou/Agreement/AgreementType` | [MEDIUM] | Fix COU XSLT to reference `$cou/Agreement/AgreementType` consistently |
| COU XSLT missing `$expType` param — REMOVE+BD l3ActivityDate never set for COU | [MEDIUM] | Add `<xsl:param name="expType"/>` to COU XSLT |
| `logicalDateVal` computed for LargeCustomerIndicator=89 but never passed to XSLT | [MEDIUM] | Add as XSLT param or remove dead code |
| reqSuccess checked per-OU — partial OU response cannot retry selectively | [LOW] | Document as design constraint |
| effType/expType overwritten per offer — only last qualifying offer's type determines l3ActivityDate | [LOW] | Review multi-offer scenarios |
| SOC/PropVal arrays reset per POU — shared between POU and its COU children by design | [INFO] | Verify shared-allowance lookup intent |

### Functional Requirements

- **R1:** Update agreement offers on unit (add/remove) for all qualifying POU and COU agreements
- **R2:** Support parameter-driven Action override (ADD/REMOVE/blank)
- **R3:** Pre-allocate SOC_SEQ_NO sequence for add operations
- **R4:** Inject shared-allowance "Agreement level offer instance ID" for PLG/CAP/CSH socs
- **R5:** Handle resubmit safely via PurgePendingRequestsBeforeResubmit and reqSuccess guard
- **R6:** Emit l3ActivityDate based on channel, action type, and offer type (EOC/BD logic)
- **R7:** Write back OfferInstanceId and pooled ExtendedInfo from CCBS response

---

## §16 — Full Source Code

```java
/**
 * @description
 * @author Sakrapee-SCM-PC
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPDATE_AGREEMENT_ON_UNIT {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CCBS_UPDATE_AGREEMENT_ON_UNIT";
    orderRequest.ProcessFlow.NextActivityID == "CCBS_UPDATE_AGREEMENT_ON_UNIT";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    try {
      Object alSOCs = Collections.List.createArrayList();
      Object alPropVal = Collections.List.createArrayList();

      Concepts.OM.LogicalDate logicalDateRes = Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate");
      String logicalDateVal = logicalDateRes.LogicalDate;  // Dead code — never passed to XSLT

      Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
        orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
      boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);

      if(isActResub) {
        RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      }

      if(XPath.evalAsBoolean(/* LargeCustomerIndicator=89 */)) {
        logicalDateVal = DateTime.format(DateTime.addDay(DateTime.now(),1),"yyyy-MM-dd'T'00:00:00XXX");
        // NOTE: logicalDateVal not passed to XSLT — dead code
      }

      boolean isSkipped = true;
      String param = XPath.evalAsString(/* $orderCurrentActivity/Parameter[1] */);

      if(!RuleFunctions.Helpers.BRMS.IsBlank(param)) {
        if(!(String.equals(param,"ADD") || String.equals(param,"REMOVE"))) {
          throw Exception.newException("DATA_ISSUE", "Param is missing.", null);
        }
      }

      int pOuLen = orderRequest.OrderData.Customer.ParentOU@length;
      for (int i = 0; i < pOuLen; i++) {
        ParentOU ou = orderRequest.OrderData.Customer.ParentOU[i];
        Collections.clear(alSOCs);
        Collections.clear(alPropVal);
        /* SOC collection from POU + COU RelatedOffersArray */

        String pOuRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;

        if (ou.Agreement != null) {
          Object agreeOffers = Collections.List.createArrayList();
          for(int of = 0; of < ou.Agreement.Offers@length; of++) {
            /* apply param override, FE_OR_CCBS filter, reqSuccess(pOuRefId), PreExecCheck */
            /* → if qualifies: agreeOffers.add(offer); capture acction/effType/expType */
          }
          if (agreeOffersArray@length > 0) {
            Events.OMConsumers.OMXFM.Request.CCBS_UPDATE_AGREEMENT_ON_UNIT reqEvent =
              Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/CCBS_UPDATE_AGREEMENT_ON_UNIT}}"
              /* XSLT: builds UpdateAgreementOnUnitRequest for POU — see §9 */);
            Event.assertEvent(reqEvent);
            RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
            long pid = System.nanoTime();
            Event.Ext.sendEventImmediate(Event.createEvent(/* Logger XSLT — see §10 */));
            isSkipped = false;
          }
        }

        for (int x = 0; x < cOuLen; x++) {
          ChildOU cou = orderRequest.OrderData.Customer.ParentOU[i].ChildOU[x];
          if (cou.Agreement != null) {
            /* same collect/dispatch pattern — uses cOuRefId */
            /* COU XSLT bugs: agreementType uses $ou not $cou; $expType param missing */
          }
        }
      }

      if(!isSkipped) {
        RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
        RuleFunctions.Helpers.SendDataToDB(orderRequest);
      } else {
        RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
      }
    } catch (Exception ae) {
      RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §17 — Response Message Rule

### §17.1 Overview

`Response_CCBS_UPDATE_AGREEMENT_ON_UNIT` is significantly richer than most response rulefunctions. In addition to standard ResponseBase construction and fan-in, it **extracts offer instance IDs from the CCBS response payload** and writes them back to the order model. It also handles pooled offer indicators by injecting an ExtendedInfo entry into the agreement concept.

### §17.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context for offer writeback |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_AGREEMENT_ON_UNIT` | CCBS response — includes ResponseCode, RefID, payload with offer instances |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity concept for Response[] and fan-in |

### §17.3 ResponseBase Concept Construction

```text
createObject → ResponseBase
├── @extId            ← ns:generateTrackingID()         [Always]
├── ResponseCode      ← $eventResponse/ResponseCode     [Conditional: if exists]
├── ResponseMessage   ← $eventResponse/ResponseMsg      [Conditional: if exists]
├── CompletionStatus  ← $eventResponse/CompletionStatus [Conditional: if exists]
└── ReferenceId       ← $eventResponse/RefID            [Conditional: if exists]
```

Appended to `currActivity.Response[currActivity.Response@length]`.

### §17.4 Offer Instance Writeback (Unique to this FM)

A second XSLT creates a `Concepts.OMX.Offers` concept from the CCBS response payload:

```text
createObject → Offers
├── @extId    ← ns2:generateTrackingID()
└── offer[*]  ← foreach $eventResponse/payload/ns:response/ns:offer
    ├── soc             ← ns:soc
    └── offerInstanceId ← ns:offerInstanceId
```

If `offers.offer@length > 0`, finds matching Agreement by RefID (POU or COU) and for each offer:
1. Finds AgreementOffers concept via `tib:if-absent(Offers[Soc=soc]/@extId[1], RelatedOffersArray[Soc=soc]/@extId[1])`
2. If `OfferInstanceId==0 AND Action==ADD` → sets `aOffer.OfferInstanceId` from response
3. If SOC indicator in pooled list (RPD/CPD) AND `Action==ADD` → creates `AgreementExtendedInfo`:
   - Name = `concat(PooledPrefix, "_", soc)` e.g., "POOLED_OFFER_INSTANCE_ID_XYZABC"
   - Value = `offerInstanceId`
   - Appended to `agreement.ExtendedInfo[]`

The `Concepts.OMX.Offers` concept is deleted in the `finally` block.

### §17.5 Response Completion Logic (Fan-in)

| Attribute | Value |
|-----------|-------|
| Fan-in mechanism | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Return "true" | All dispatched requests have received responses |
| Return "false" | Still waiting for more responses |

Uses the `ActionResponseEvent` helper (same as CCBS_REMOVE_AGREEMENT_PRICE_PLAN) — correct fan-in approach.

### §17.6 Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat(System.nanoTime(), "_RES")` |
| OPERATION_NAME | `"CCBS_UPDATE_AGREEMENT_ON_UNIT"` (static) |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| AUDIT_TRACE | `"Response received for CCBS_UPDATE_AGREEMENT_ON_UNIT"` (static) |
| payload | copy of `$eventResponse` — gated on `WritePayload=true` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
