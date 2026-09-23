# Request_OMX_CAL_DISCOUNT_FULL_BILL

> Pure in-memory calculation — propagates FUT_ORDER_ID from discount/related offers to the parent main-SOC offer as RELATED_ORDER ExtendedInfo entries. No external system call; synchronous NextActivity flow.

**Type:** In-memory orchestration (no JMS/backend) | **Pattern:** Synchronous → NextActivity | **forwardChain:** true | **Author:** RS33-BANDIT | **Used in step:** 36

---

## §1 Overview & Purpose

A pure in-memory calculation rule that runs synchronously between the OMX_ADD_FUT_OFFER step and the next activity. Its sole purpose is to collect the `FUT_ORDER_ID` values written back by OMX_ADD_FUT_OFFER responses and link them to the main/parent SOC offer as `RELATED_ORDER` ExtendedInfo entries — enabling the downstream OMX discount calculation to correlate which future orders belong to the same parent package.

> **No external system call:** This rule makes no JMS or REST calls. It manipulates in-memory BE concepts only, then calls `NextActivity` to advance the process flow.

> **Synchronous completion:** No fan-in wait. After the loops and `NextActivity`, an audit Logger event is sent and the rule completes.

> **No response rulefunction:** This FM has no `Response_OMX_CAL_DISCOUNT_FULL_BILL.rulefunction` — response handling is not applicable.

> **Rule namespace:** `Rules.OMConsumers.OMXOM` — not under the OMXFM namespace used by external-call FMs.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `OMX_CAL_DISCOUNT_FULL_BILL.rule` | No `Request_` prefix — internal calculation rule |
| Rule namespace | `Rules.OMConsumers.OMXOM` | Different from OMXFM external-call rules |
| Response rulefunction | None | Not applicable — synchronous, no backend |
| Author | RS33-BANDIT | |
| forwardChain | true | |
| Priority | 5 | |
| External system | None | No JMS / REST calls |
| Completion pattern | Synchronous → `NextActivity()` | No RequestCount; no fan-in |
| Audit gate | [UNCONDITIONAL] | Logger event always sent |
| PurgePendingRequestsBeforeResubmit | N/A | No pending requests to purge |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Full order hierarchy — POU, Subscriber, SubscriberOffers, ExtendedInfo |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | PreExecCheck; status; activity gate |

### Local Variables

| Variable | Type | Scope | Purpose |
|----------|------|-------|---------|
| `logicalDate` | DateTime | rule-level | Business date (from LogicalDate concept or `DateTime.now()`) |
| `logicalDateRes` | Concepts.OM.LogicalDate | rule-level | LogicalDate concept lookup result |
| `isOmxFut` | boolean | rule-level | [Computed but unused] — checks FUT_TYPE=FUTSOC/EXPSOC; never gates any branch |
| `allFutOrderId` | ArrayList | POU-level (reset per POU) | Accumulates FUT_ORDER_ID values from qualifying subscriber offers |
| `mainSocName` | String | Subscriber-level (reset per subscriber) | Captures RELATED_OFFER value (OfferName of the parent/main SOC) |
| `filter` | String | offer-level | FE_OR_CCBS ExtendedInfo value from current offer |
| `chkRes` | String | offer-level | PreExecCheck XPath result ("true"/"false") |
| `futOrderId` | String | offer-level | FUT_ORDER_ID value from offer ExtendedInfo |

> **`allFutOrderId` scope mismatch:** Initialized at POU level but iterated in the second subscriber loop — it accumulates across ALL subscribers of a POU. If two subscribers each have qualifying offers, their FUT_ORDER_IDs are pooled and ALL of them are written to the main offer of EACH subscriber that matches `mainSocName`.

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_CAL_DISCOUNT_FULL_BILL"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_DISCOUNT_FULL_BILL"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 Two-Pass Subscriber Offer Logic

### Pass 1 — Collect FUT_ORDER_IDs and identify main SOC name

For each subscriber offer that passes PreExecCheck:

```java
for (int o = 0; o < psofLen; o++) {
    psof = Subscriber[ps].SubscriberOffers[o];
    filter = XPath("$psof/ExtendedInfo[Name='FE_OR_CCBS']/Value");
    chkRes = "true";

    if (String.length(chkXPath) > 0) {
        sXML = GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, psof.Soc, filter);
        chkRes = XPath.execute("/(" + chkXPath + ")", sXML, ...);
    }
    if (String.equals(chkRes, "true")) {
        futOrderId = XPath("$psof/ExtendedInfo[Name='FUT_ORDER_ID']/Value");
        Collections.add(allFutOrderId, futOrderId);
        mainSocName = XPath("$psof/ExtendedInfo[Name='RELATED_OFFER']/Value");
    }
}
```

### Pass 2 — Write RELATED_ORDER entries to the main SOC offer

```java
for (int index = 0; index < psofLen; index++) {
    psofMain = Subscriber[ps].SubscriberOffers[index];
    if (mainSocName != null && String.equals(mainSocName, psofMain.OfferName)) {
        for (int x = 0; x < allFutOrders.length; x++) {
            futOrderId = allFutOrders[x];
            subOffExtInfo = Instance.createInstance(SubscriberOffersExtendedInfo) {
                extId = concat(psofMain.@extId, "RELATED_ORDER", ps, index, x);
                Name  = "RELATED_ORDER";
                Value = futOrderId;
            };
            psofMain.ExtendedInfo[length] = subOffExtInfo;
        }
    }
}
```

**What this accomplishes:** After OMX_ADD_FUT_OFFER writes `FUT_ORDER_ID` into each discount/related SOC offer's ExtendedInfo, this rule finds all those FUT_ORDER_IDs and attaches them to the **main/parent SOC offer** (identified by `RELATED_OFFER` → `OfferName` match) so that the discount full-bill calculation step can retrieve all relevant future order IDs from a single offer's ExtendedInfo.

---

## §6 Unused Variable — isOmxFut

> **Potential dead code:** `isOmxFut` is computed via XPath but never referenced in any conditional branch.

```java
boolean isOmxFut = XPath.evalAsBoolean(
    "boolean($orderRequest/OrderData/ExtendedInfo[Name='FUT_TYPE' and (Value='FUTSOC' or Value='EXPSOC')])"
);
// ← never referenced again after this line
```

This variable checks whether the order has `FUT_TYPE=FUTSOC` or `FUT_TYPE=EXPSOC` in ExtendedInfo. The original intent may have been to gate the entire two-pass loop — but the gate was either removed or not implemented. The PreExecCheck at the activity level may serve this purpose instead.

---

## §7 ExtendedInfo Keys Read & Written

| Key | Direction | Source | Purpose |
|-----|-----------|--------|---------|
| `FE_OR_CCBS` | Read | SubscriberOffers.ExtendedInfo | Filter for GetXMLForSubscriberOfferFilterWithExtendedInfo (PreExecCheck XML builder) |
| `FUT_ORDER_ID` | Read | SubscriberOffers.ExtendedInfo | Future order ID written by OMX_ADD_FUT_OFFER response; collected into ArrayList |
| `RELATED_OFFER` | Read | SubscriberOffers.ExtendedInfo | OfferName of the parent/main SOC offer; used as join key to find psofMain |
| `RELATED_ORDER` | **Write** | SubscriberOffers.ExtendedInfo (on psofMain) | Written by this rule — maps future order IDs back to the main SOC offer |

---

## §8 Completion — NextActivity & Audit

```text
RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)

Logger event:
├── ESBUUID        ← orderRequest.OrderData.OMXTrackingId  [xsl:if]
├── PROCESS_ID     ← concat($pid, "_RES")
├── COMPONENT_NAME ← $globalVariables/OMX_COMMON/Component_Name/OMX_CEP
├── OPERATION_NAME ← "OMX_CAL_DISCOUNT_FULL_BILL"
├── LOG_LEVEL      ← $globalVariables/OMX_COMMON/.../MSG_LOG_LEVEL/INFO
├── AUDIT_TRACE    ← "OMX-OM CalOfferFutureDate Completed."
├── AUDIT_TS       ← tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())
└── payload/       (empty)
```

---

## §9 Function Dependency Tree

```text
OMX_CAL_DISCOUNT_FULL_BILL (rule)
├── Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")   [logicalDate]
├── XPath.evalAsBoolean(FUT_TYPE=FUTSOC/EXPSOC check)   [isOmxFut — unused]
├── [POU loop]:
│   ├── Collections.List.createArrayList()   [allFutOrderId — reset per POU]
│   └── [Subscriber loop]:
│       ├── [Pass 1 — offer loop]:
│       │   ├── XPath.evalAsString(FE_OR_CCBS filter)
│       │   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, soc, filter)
│       │   ├── XPath.execute("/("+chkXPath+")", sXML, ...)   [PreExecCheck evaluation]
│       │   ├── XPath.evalAsString(FUT_ORDER_ID)   [on qualifying offer]
│       │   ├── Collections.add(allFutOrderId, futOrderId)
│       │   └── XPath.evalAsString(RELATED_OFFER)   [→ mainSocName]
│       └── [Pass 2 — index loop]:
│           ├── Collections.toArray(allFutOrderId)
│           └── [for each x in allFutOrders]:
│               └── Instance.createInstance(SubscriberOffersExtendedInfo)
│                   extId=concat(psofMain.@extId,"RELATED_ORDER",ps,index,x)
│                   Name="RELATED_ORDER", Value=futOrderId
│                   → psofMain.ExtendedInfo[length] = subOffExtInfo
├── RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)
├── Event.Ext.sendEventImmediate(Logger event)
│   └── AUDIT_TRACE="OMX-OM CalOfferFutureDate Completed."
└── [catch] RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
```

---

## §10 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Pure in-memory step — no external system integration required. |
| R2 | Must run AFTER OMX_ADD_FUT_OFFER (which writes FUT_ORDER_ID) and BEFORE the discount calculation step that reads RELATED_ORDER. |
| R3 | Two-pass logic: first pass collects FUT_ORDER_IDs and RELATED_OFFER name; second pass writes RELATED_ORDER entries to the main SOC offer. |
| R4 | `allFutOrderId` is reset per POU — cross-POU FUT_ORDER_IDs are NOT pooled. |
| R5 | ExtendedInfo extId uniqueness key: `concat(psofMain.@extId, "RELATED_ORDER", ps, index, x)` — must preserve this for idempotency. |
| R6 | `isOmxFut` is computed but unused — treat as dead code; safe to remove in modernized implementation. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `allFutOrderId` accumulates across all subscribers of a POU — multi-subscriber pooling may be unintended | [MEDIUM] | Verify with business; if not intended, move `createArrayList()` inside the subscriber loop |
| `isOmxFut` computed but never used — non-future orders execute both passes unnecessarily | [LOW] | Remove the XPath evaluation or add explicit early-exit guard in modernized version |
| Join key is `OfferName` (display name), not a stable SOC code — name changes break the join silently | [MEDIUM] | Verify whether RELATED_OFFER carries OfferName or OfferCode; switch join to SOC code if mutable |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
