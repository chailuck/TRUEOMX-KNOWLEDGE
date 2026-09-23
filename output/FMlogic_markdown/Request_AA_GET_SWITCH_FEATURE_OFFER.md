# Request_AA_GET_SWITCH_FEATURE_OFFER

> AA Switch Feature Offer — Global SOC Batch Lookup with Multi-Container Write-Back

**Priority:** 5 | **forwardChain:** true | **Author:** awalia-t420 | **Pattern:** Single Batch Request | **Backend:** AA / CES (GoldenDB fork) | **Generated:** 2026-07-27

---

## §1 — Overview & Purpose

This rule queries the **AA Switch Feature** service to retrieve switching feature values (`item_cd`, `swparam`, `switchcode`) for every unique SOC code present in the order's offer containers. It scans all four offer containers — ParentOU Agreement, ParentOU SubscriberOffers, ChildOU Agreement, and ChildOU SubscriberOffers — collecting every unique SOC code into a deduplicated list, then sends a single batch request. The response handler writes feature data back to each matching offer entry across all containers.

> **Single batch request pattern:** Uses `Event.Ext.sendEventImmediate` with all unique SOC IDs in one `ns:GetSwitchFeatureValueRequest`. No IntraActivitySequencing — RequestCount is incremented once.

> **GoldenDB routing fork:** If `OrderData.GoldenDB == "Y"`, dispatches to `CES_GET_SWITCH_FEATURE_OFFER` event; otherwise dispatches to `AA_GET_SWITCH_FEATURE_OFFER` event.

> **Skip condition:** If no SOC codes are collected (`socLength == 0`), the activity is skipped via `SkipActivity("4")` — no backend call.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_AA_GET_SWITCH_FEATURE_OFFER` |
| Priority | 5 |
| forwardChain | true |
| Author | awalia-t420 |
| Backend (standard) | AA — GetSwitchFeatureValue service |
| Backend (GoldenDB) | CES — CES_GET_SWITCH_FEATURE_OFFER |
| Request schema | `http://services.omx.truecorp.co.th/FM/getSwitchFeatureValueRequest` |
| Response schema | `http://services.omx.truecorp.co.th/FM/getSwitchFeatureValueResponse` |
| Dispatch pattern | Single batch request — `sendEventImmediate`, NOT IntraActivitySequencing |
| Audit log gate | `AllowWriteLog(OrderType)` — same non-standard gate as OMX_GET_SRV_TRX_NO |
| Skip condition | No unique SOC codes found across all offer containers → `SkipActivity("4")` |
| Activity parameter | `IGNORE_CCP` — if "Y", skips SubscriberOffers with `ExtendedInfo[FE_OR_CCBS='CCP']` |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order graph (read + write) |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current FM activity (read + write) |
| `arrLstSOCs` | `ArrayList` (local) | Deduplicated unique SOC codes from all offer containers |
| `nextAct` | `Concepts.OM.ProcessConfig.Activity` (local) | Current activity instance (for PreExecCheck access) |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity to order |
| 2 | `orderCurrentActivity.ActivityID == "AA_GET_SWITCH_FEATURE_OFFER"` | Targets this FM only |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "AA_GET_SWITCH_FEATURE_OFFER"` | Order-level double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires on fresh activity |

---

## §5 — Execution Flow

```text
1. Init: isActResub = (RequestCount > 0 && IsOrderResubmitted); arrLstSOCs = ArrayList()
2. Scan ParentOU Agreement.Offers[]:
     XPath isPAgreePresent; for each Offer.Soc + RelatedOffersArray[q].Soc:
     check reqSuccess (already completed for refId)
     apply PreExecCheck via GetXMLForAgreementOffer / GetXMLForAgreementRelatedOffer
     → add to arrLstSOCs if not duplicate (Collections.contains)
3. Scan ParentOU Subscriber[j].SubscriberOffers[] and RelatedOffersArray:
     same reqSuccess + PreExecCheck via GetXMLForSubscriberOffer / GetXMLForSubscriberRelatedOffer
4. Scan ChildOU[m].Agreement.Offers[]:
     XPath isCAgreePresent; PreExecCheck via GetXMLForAgreementOfferInChildOU / GetXMLForAgreementRelatedOfferInChildOU
5. Scan ChildOU[m].Subscriber[n].SubscriberOffers[] and RelatedOffersArray:
     PreExecCheck via GetXMLForSubscriberOfferInChildOU / GetXMLForSubscriberRelatedOfferInChildOU
6. socIDs = Collections.toArray(arrLstSOCs); socLength = socIDs@length
7. if (socLength > 0):
     GoldenDB fork:
       GoldenDB == "Y" → create and send CES_GET_SWITCH_FEATURE_OFFER event
       else            → create and send AA_GET_SWITCH_FEATURE_OFFER event
     (identical payload: ns:GetSwitchFeatureValueRequest with ns:socid[] per unique SOC)
8. orderCurrentActivity.ProcessID = String.valueOfLong(System.nanoTime())
9. [AllowWriteLog(OrderType)] Send Logger audit event (request)
10. [!isActResub] RequestCount++
11. Status → IN_PROGRESS; SendDataToDB
12. if (socLength == 0) → SkipActivity(orderRequest, orderCurrentActivity, "4")
13. Exception → HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
```

---

## §8 — System & Integration Dependencies

### §8.1 — SOC Collection Strategy (8 Container Paths)

All four offer containers scanned in a single pass. Deduplication via `Collections.contains`. SOCs with completed response for subscriber refId are skipped (`reqSuccess` guard).

| Container | Scope | PreExecCheck Helper |
|-----------|-------|---------------------|
| Agreement.Offers[p].Soc | ParentOU[i] | `GetXMLForAgreementOffer(orderRequest, Agreement.RefId, socid)` |
| Agreement.Offers[p].RelatedOffersArray[q].Soc | ParentOU[i] | `GetXMLForAgreementRelatedOffer(...)` |
| Subscriber[j].SubscriberOffers[k].Soc | ParentOU[i] | `GetXMLForSubscriberOffer(orderRequest, Subscriber.RefId, socid)` |
| Subscriber[j].SubscriberOffers[k].RelatedOffersArray[l].Soc | ParentOU[i] | `GetXMLForSubscriberRelatedOffer(...)` |
| ChildOU[m].Agreement.Offers[p].Soc | ChildOU[m] | `GetXMLForAgreementOfferInChildOU(orderRequest, ChildOU.RefId, socid, ParentOU.RefId)` |
| ChildOU[m].Agreement.Offers[p].RelatedOffersArray[q].Soc | ChildOU[m] | `GetXMLForAgreementRelatedOfferInChildOU(...)` |
| ChildOU[m].Subscriber[n].SubscriberOffers[k].Soc | ChildOU[m] | `GetXMLForSubscriberOfferInChildOU(orderRequest, Subscriber.RefId, socid, ParentOU.RefId)` |
| ChildOU[m].Subscriber[n].SubscriberOffers[k].RelatedOffersArray[l].Soc | ChildOU[m] | `GetXMLForSubscriberRelatedOfferInChildOU(...)` |

### §8.2 — JMS / ESB Channel Dependencies

| Direction | Event | Condition | Method |
|-----------|-------|-----------|--------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.AA_GET_SWITCH_FEATURE_OFFER` | `GoldenDB != "Y"` | `sendEventImmediate` |
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CES_GET_SWITCH_FEATURE_OFFER` | `GoldenDB == "Y"` | `sendEventImmediate` |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `AllowWriteLog(OrderType)` | `sendEventImmediate` |

### §8.3 — Activity Parameter Dependencies

| Parameter Key | Source | Effect |
|---------------|--------|--------|
| `IGNORE_CCP` | Activity parameter (read in response handler) | If "Y" — skip SubscriberOffers where `ExtendedInfo[FE_OR_CCBS='CCP']` exists |

> **Null SOC Guard (OMX-1161):** Every SOC code check guards `if (socid != null)` — explicitly noted as OMX-1161 fix.

---

## §9 — Request Payload (GetSwitchFeatureValueRequest)

Both AA and CES events carry identical payload. CES variant adds `extId = OMXUtils:generateTrackingID()` on the event element.

```text
createEvent
└── event
    ├── JMSPriority       ← $orderRequest/OrderPriority           [Conditional]
    ├── JMSCorrelationID  ← OrderData/OMXTrackingId               [Conditional]
    ├── OrderID           ← OrderData/OrderID                     [Conditional]
    ├── OrderType         ← OrderData/OrderType                   [Conditional]
    └── payload
        └── ns:GetSwitchFeatureValueRequest
            └── ns:socid[*] ← . (current $socIDs/elements)       [xsl:for-each — one per unique SOC]
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── [CES only] @extId   ← OMXUtils:generateTrackingID()         [Always — CES variant only]
    ├── JMSPriority         ← $orderRequest/OrderPriority           [Conditional: if $orderRequest/OrderPriority]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId [Conditional]
    ├── OrderID             ← $orderRequest/OrderData/OrderID       [Conditional]
    ├── OrderType           ← $orderRequest/OrderData/OrderType     [Conditional]
    └── payload
        └── ns:GetSwitchFeatureValueRequest
            └── ns:socid    ← . (current $socIDs/elements)         [xsl:for-each — repeated per unique SOC code]
```

Legend: `[Always]` = emitted unconditionally | `[Conditional: <cond>]` = inside `xsl:if` | `[xsl:for-each]` = repeated element

---

## §12 — Activity Status Management

| Trigger | Code | Status |
|---------|------|--------|
| Rule fires (initial) | 0 | WAITING |
| socLength == 0 (no SOCs found) | 4 | [SKIP] SKIPPED |
| Request sent | 1 | IN_PROGRESS |
| Exception | 3 | [ERROR] ERROR |
| Response received | 2 | [SUCCESS] COMPLETED |

---

## §15 — Function Dependency Tree

```text
Request_AA_GET_SWITCH_FEATURE_OFFER (rule)
├── Collections.List.createArrayList()
├── Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")
├── XPath.evalAsBoolean(...)                  [isPAgreePresent / isCAgreePresent]
├── [PreExecCheck non-empty per SOC]:
│   ├── GetXMLForAgreementOffer(orderRequest, Agreement.RefId, socid)
│   ├── GetXMLForAgreementRelatedOffer(orderRequest, Agreement.RefId, socid, relSocid)
│   ├── GetXMLForSubscriberOffer(orderRequest, Subscriber.RefId, socid)
│   ├── GetXMLForSubscriberRelatedOffer(orderRequest, Subscriber.RefId, socid, relSocid)
│   ├── GetXMLForAgreementOfferInChildOU(orderRequest, ChildOU.RefId, socid, ParentOU.RefId)
│   ├── GetXMLForAgreementRelatedOfferInChildOU(...)
│   ├── GetXMLForSubscriberOfferInChildOU(...)
│   └── GetXMLForSubscriberRelatedOfferInChildOU(...)
│       └── XPath.execute("/(" + chkXPath + ")", sXML, ...)
├── Collections.contains(arrLstSOCs, socid)
├── Collections.add(arrLstSOCs, socid)
├── Collections.toArray(arrLstSOCs)
├── [GoldenDB == "Y"] Event.createEvent(xslt://CES_GET_SWITCH_FEATURE_OFFER)
├── [GoldenDB != "Y"] Event.createEvent(xslt://AA_GET_SWITCH_FEATURE_OFFER)
├── Event.Ext.sendEventImmediate(reqEvent)
├── System.nanoTime()
├── [AllowWriteLog(OrderType)] Logger event
├── [!isActResub] RequestCount++
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── [isSkipped] SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_AA_GET_SWITCH_FEATURE_OFFER (rulefunction)
├── Instance.createInstance(xslt://AA_SwitchFeatureRes)
│   └── currActivity.Response[n] = sfResActivity
├── GetActivityParamValueFromKey(currActivity, "IGNORE_CCP")
├── XPath.evalAsInt(count featurelist/soc_cd)
├── for z in featurelist[]:
│   ├── XPath.evalAsString(featurelist[z+1]/soc_cd)
│   └── for each matching SOC across all containers:
│       ├── Instance.createInstance(xslt://AgreementSwitchFeature)
│       │   → Offers[p].SwitchFeature[] = agreeSwf
│       ├── Instance.createInstance(xslt://RelatedOffresSwitchFeature) [agreement related]
│       ├── [IGNORE_CCP=Y] XPath.evalAsBoolean(exists(ExtendedInfo[FE_OR_CCBS='CCP']))
│       ├── Instance.createInstance(xslt://SubscriberSwitchFeature)
│       │   → SubscriberOffers[k].SwitchFeature[] = subswf
│       ├── Instance.createInstance(xslt://RelatedOffresSwitchFeature) [subscriber related]
│       └── SetCugID(paramBaseArray, switchFeatureConcept)    [all types]
├── [AllowWriteLog(OrderType)] Logger event (response audit)
└── return "true"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — SOC deduplication must be preserved: one `ns:socid` per unique SOC regardless of container count.
- **R2** — All 8 offer container paths must be scanned; omitting any causes missing SwitchFeature data downstream.
- **R3** — GoldenDB routing fork must be configurable: CES endpoint for GoldenDB orders.
- **R4** — Response write-back uses SOC code as join key across ALL containers (not just the source container).
- **R5** — IGNORE_CCP=Y must skip SubscriberOffers with `ExtendedInfo[FE_OR_CCBS='CCP']`.
- **R6** — SetCugID must be applied to every SwitchFeature concept created (all 3 concept types).
- **R7** — Audit uses `AllowWriteLog(OrderType)` — not the standard WritePayload gate.
- **R8** — Null SOC guard (OMX-1161): null SOC codes silently skipped.

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| featurelist soc_cd case mismatch vs stored Offers[p].Soc → silent no write-back | [HIGH] | Ensure consistent SOC code casing; add reconciliation check |
| Typo: `RelatedOffresSwitchFeature` (double "f") — concept rename risk | [MEDIUM] | Rename consistently or keep typo; do not mix names |
| IGNORE_CCP=Y applied to SubscriberOffers only, not Agreement.Offers — asymmetry | [MEDIUM] | Verify business requirement; document explicitly |
| reqSuccess check per refId — partial resub scenarios need testing | [LOW] | Test with partial-completion resubmission scenarios |
| Per-SOC PreExecCheck via XPath helpers — performance concern with large SOC lists | [LOW] | Cache PreExecCheck result at activity level in migration |

---

## §19 — Response Message Rule

### §19.1 — Overview

Parses `GetSwitchFeatureValueResponse` and writes switch feature data (`item_cd`, `swparam`, `switchcode`) back to every offer entry whose SOC matches a response `featurelist` entry. Returns `"true"` unconditionally — single batch, no fan-in counter.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order graph (written) |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.AA_GET_SWITCH_FEATURE_OFFER` | Backend response payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity (Response[] written) |

### §19.3 — AA_SwitchFeatureRes Concept Construction

```text
createObject
└── object
    ├── @extId          ← OMXUtils:generateTrackingID()     [Always]
    ├── ResponseCode    ← $eventResponse/ResponseCode       [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg        [Conditional]
    ├── CompletionStatus← $eventResponse/CompletionStatus   [Conditional]
    └── ReferenceId     ← $eventResponse/RefID              [Conditional]
→ appended to currActivity.Response[]
```

### §19.4 — SwitchFeature Write-Back per featurelist Entry

For each `featurelist[z]` in response, match `featurelist[z]/soc_cd` against all offer containers:

| Target Concept | Container(s) | Fields Written |
|----------------|-------------|----------------|
| `AgreementSwitchFeature` | Agreement.Offers[p], ChildOU.Agreement.Offers[p] | item_cd, swparam, switchcode, SetCugID() |
| `RelatedOffresSwitchFeature` | Agreement.RelatedOffersArray[q], ChildOU.Agreement.RelatedOffersArray[q], SubscriberOffers.RelatedOffersArray[l], ChildOU.Subscriber.SubscriberOffers.RelatedOffersArray[l] | item_cd, swparam, switchcode, SetCugID() |
| `SubscriberSwitchFeature` | Subscriber[j].SubscriberOffers[k], ChildOU.Subscriber[n].SubscriberOffers[k] | item_cd, swparam, switchcode, SetCugID() *(IGNORE_CCP gate)* |

### §19.5 — IGNORE_CCP Gate

```java
if (!BRMS.IsBlankOrStringNull(ignoreCCP) && String.equals(ignoreCCP, "Y")) {
    if (XPath.evalAsBoolean("exists($offer/ExtendedInfo[Name='FE_OR_CCBS' and Value='CCP'])")) {
        continue;   // skip CCP-type subscriber offer
    }
}
```

Applied to `SubscriberOffers[k]` and `SubscriberOffers[k].RelatedOffersArray[l]`. NOT applied to Agreement.Offers.

### §19.6 — Completion Condition

Returns `"true"` unconditionally. Single-shot batch request — no fan-in counter comparison. Activity completes on first (only) response.

### §19.7 — Response Audit Logging

| Field | Value |
|-------|-------|
| `ESBUUID` | `OrderData/OMXTrackingId` |
| `PROCESS_ID` | `concat($pid, "_RES")` where `pid = System.nanoTime()` |
| `OPERATION_NAME` | `"AA_GET_SWITCH_FEATURE_OFFER"` |
| `AUDIT_TRACE` | `"Response received for AA_GET_SWITCH_FEATURE_OFFER"` |
| `payload` | Conditional: `$globalVariables/OMX_OM/WritePayload = "true"` |

> **Gate:** `AllowWriteLog(OrderType)` — same gate as request audit.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
