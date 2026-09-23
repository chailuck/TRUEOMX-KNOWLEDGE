# Request_OMX_CAL_CHK_SUM

## §1 Overview & Purpose

A local computation rule with **no outbound ESB/JMS call**. Iterates every Subscriber and their SubscriberOffers, locates ICC_ID (SIM card ICCID), computes a Luhn checksum via `RuleFunctions.Helpers.Luhn(iccId)`, then writes a new `ICC_ID_CHG_SUM` ExtendedInfo on the subscriber or offer for downstream eSIM provisioning (SMDP+).

Two ICC_ID source paths:
- **RIO_SWAP path** (PROJ=RIO_SWAP or `subscriber.ExtendedInfo[ICC_ID]` present): reads ICC_ID from subscriber-level → writes `SubscriberExtendedInfo` ICC_ID_CHG_SUM on subscriber.
- **Standard path**: reads ICC_ID from offer-level ExtendedInfo → writes `SubscriberOffersExtendedInfo` ICC_ID_CHG_SUM on offer.

The resulting ICC_ID_CHG_SUM value gates the `SMDP_PLUS` activity's PreExecCheck (`ICC_ID_CHG_SUM present and not SMDP_COMFIRMED=Y`).

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_CAL_CHK_SUM` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | OMX_CAL_CHK_SUM |
| Backend | OMX Internal — no outbound call |
| Pattern | Local Computation (no IntraActivitySequencing) |
| Author | RS33-BANDIT |
| Response Rulefunction | None — rule calls NextActivity/SkipActivity directly |

---

## §3 Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity state |

---

## §4 Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "OMX_CAL_CHK_SUM"
orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_CHK_SUM"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 Execution Flow

1. If resubmit: `PurgePendingRequestsBeforeResubmit`
2. Read next activity to get its `PreExecCheck` expression
3. Get PROJ parameter from current activity
4. Loop ParentOU[p].Subscriber[s].SubscriberOffers[o]:
   - Skip if already CompletionStatus=2
   - Evaluate next-activity PreExecCheck
   - If passes: check `iccidInSub` = subscriber has `ExtendedInfo[ICC_ID]`
   - If RIO_SWAP or iccidInSub: get ICC_ID from subscriber, compute Luhn, write `SubscriberExtendedInfo(ICC_ID_CHG_SUM)`, fire audit log, break
   - Else: get ICC_ID from offer, compute Luhn, write `SubscriberOffersExtendedInfo(ICC_ID_CHG_SUM)`, fire audit log
5. Loop ParentOU[p].ChildOU[cou].Subscriber[cs]: same with ChildOU helper variants
6. If not isSkipped: `NextActivity`; else: `SkipActivity("4")`

---

## §8 System & Integration Dependencies

### §8.1 No Outbound Backend Call

This rule performs purely in-memory operations. No JMS/ESB event to external system.

### §8.5 ExtendedInfo Fields

| Key | Level | Direction | Purpose |
|-----|-------|-----------|---------|
| ICC_ID | Subscriber or Offer | Input (read) | Source ICCID for checksum |
| ICC_ID_CHG_SUM | Subscriber or Offer | Output (written) | ICC_ID + Luhn checksum; gates SMDP+ |
| FE_OR_CCBS | Offer | Input (filter) | Used in XML generation for PreExecCheck |

### §8.6 Global Variables

| Path | Purpose |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `$globalVariables/OMX_OM/WritePayload` | Gate audit payload |

---

## §9 Computation Logic — ICC_ID_CHG_SUM Generation

```java
String iccIdCheckSum = RuleFunctions.Helpers.Luhn(iccId);
iccIdChgSum.Value = iccId + iccIdCheckSum;
```

ICC_ID_CHG_SUM extId pattern:
```text
concat($iccId, ':ICC_ID_CHG_SUM', $psof/@extId)   // ParentOU offer
concat($iccId, ':ICC_ID_CHG_SUM', $csof/@extId)   // ChildOU offer
```

Source-path decision:

| Condition | ICC_ID Source | Write Target |
|-----------|--------------|--------------|
| PROJ=RIO_SWAP OR subscriber.ExtendedInfo[ICC_ID] exists | Subscriber ExtendedInfo | `SubscriberExtendedInfo` on subscriber |
| Otherwise | Offer ExtendedInfo | `SubscriberOffersExtendedInfo` on offer |

---

## §10 XSLT Field Mapping Tree

```text
createObject
└── object
    ├── @extId  ← concat($iccId, ':ICC_ID_CHG_SUM', $psof/@extId)  [Conditional: ICC_ID present]
    ├── Name    ← 'ICC_ID_CHG_SUM'                                  [Always]
    └── Value   ← iccId + iccIdCheckSum                             [Set after createInstance]
```

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` [Conditional] |
| PROCESS_ID | `concat($pid, "_REQ")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | "OMX_CAL_CHK_SUM" |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | "Request Sent for OMX_CAL_CHK_SUM" |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload/ns:ServicePayload | empty [Conditional: WritePayload=true] |

---

## §12 Activity Status Management

| Outcome | Call | Status |
|---------|------|--------|
| ICC_ID found and written | `NextActivity(req, activity)` | Advance |
| No ICC_ID found | `SkipActivity(req, activity, "4")` | Skipped |

---

## §13 Exception Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 Helper Functions

| Function | Purpose |
|----------|---------|
| `Luhn(iccId)` | Computes Luhn checksum string |
| `GetActivityParamValueFromKey(activity, "PROJ")` | Returns PROJ parameter value |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(...)` | Serialise subscriber+offer for XPath (ParentOU) |
| `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...)` | Same for ChildOU |
| `NextActivity(req, activity)` | Advance process flow |
| `SkipActivity(req, activity, "4")` | Mark as skipped |
| `PurgePendingRequestsBeforeResubmit(activity)` | Clean state on resubmit |
| `HandleActivityException(req, activity, ae, "")` | Standard error handler |

---

## §15 Function Dependency Tree

```text
Request_OMX_CAL_CHK_SUM
├── PurgePendingRequestsBeforeResubmit(activity)         [if resubmit]
├── GetActivityParamValueFromKey(activity, "PROJ")
├── GetXMLForSubscriberOfferFilterWithExtendedInfo(...)   [ParentOU]
├── GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...)  [ChildOU]
├── XPath.evalAsBoolean(iccidInSub check)
├── XPath.evalAsString(ICC_ID extraction)
├── Helpers.Luhn(iccId)
├── Instance.createInstance(SubscriberExtendedInfo XSLT)
├── Instance.createInstance(SubscriberOffersExtendedInfo XSLT)
├── Event.Ext.sendEventImmediate(Logger)
├── NextActivity(req, activity)
├── SkipActivity(req, activity, "4")
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 Migration Notes

| # | Requirement / Risk | Severity |
|---|-------------------|---------|
| R1 | Luhn algorithm must match RuleFunctions.Helpers.Luhn exactly — mismatch invalidates ICC_ID_CHG_SUM and breaks SMDP+ | [HIGH] |
| R2 | RIO_SWAP path reads ICC_ID from subscriber-level; standard path from offer-level — both paths must be preserved | [HIGH] |
| R3 | ICC_ID_CHG_SUM must be written in-memory before SMDP_PLUS runs; downstream eSIM flow depends on correct object (subscriber vs offer) | [MEDIUM] |
| R4 | SMDP_PLUS PreExecCheck tests ICC_ID_CHG_SUM presence — if this rule skips, SMDP+ also skips | [MEDIUM] |
| R5 | Rule evaluates next activity's PreExecCheck for each offer — cross-activity dependency must be modelled explicitly | [MEDIUM] |
| R6 | SkipActivity code "4" — ensure downstream orchestration handles it | [LOW] |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
