# Request_OMX_SET_OFFER_CALL_FORWARD

OMXOM Working-Memory Enrichment — Tag Call-Forward SubscriberOffers as DUMMY when OfferName is absent

**Rule:** OMXOM (internal) | **Priority:** 5 | **Backend:** None — in-memory only | **No backend call / No response rulefunction**

---

## §1 — Overview & Purpose

Scans every `SubscriberOffers` entry (across all ParentOU subscribers and ChildOU subscribers) and checks whether any of its `ParameterInfo[*].ParamName` values appears in the configured parameter list (`param`). For offers where a match is found *and* the offer has no `OfferName`, the rule stamps `Soc="0"` and `OfferName="DUMMY"`.

> **Business purpose:** Some orders carry call-forward parameter changes (e.g., CFB, CFNRY, CFU) that are attached to a subscriber's offer slot but without a true SOC code — they are parameter-only entries. Tagging them with `Soc="0" / OfferName="DUMMY"` flags them as non-real offers so downstream FMs (CCBS_CHANGE_PACKAGE_SUBSCRIBER) know to skip them for SOC-level provisioning and only process the parameter update.

> **OMXOM internal rule:** This is a pure working-memory transformation — no JMS events, no backend calls, no response rulefunction. The rule calls `NextActivity()` directly after completing its work.

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXOM.OMX_SET_OFFER_CALL_FORWARD` |
| Rule class | OMXOM (in-memory enrichment) |
| Backend call | None |
| Response rulefunction | None |
| ProcessConfig step | 13 in POSTPAID_UPDATE_PARAMETER |
| PreExecCheck | Commented-out in ProcessConfig XML (always executes) |
| Writes to working memory | `SubscriberOffers.Soc = "0"`; `SubscriberOffers.OfferName = "DUMMY"` |

---

## §2 — Rule Metadata & Attributes

| Property | Value |
|----------|-------|
| Namespace | `Rules.OMConsumers.OMXOM` |
| Rule file | `OMX_SET_OFFER_CALL_FORWARD.rule` |
| Priority | 5 |
| forwardChain | true |
| Author | DESKTOP-KB4BEG4 |
| RequestCount management | None (OMXOM — no backend requests) |
| Activity completion | `NextActivity(orderRequest, orderCurrentActivity)` called inline |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order request — modified in-place (SubscriberOffers.Soc / OfferName) |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — read for Parameter[1] and PreExecCheck |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Binds activity to this order |
| 2 | `orderCurrentActivity.ActivityID == "OMX_SET_OFFER_CALL_FORWARD"` | Restricts to this OMXOM rule |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_SET_OFFER_CALL_FORWARD"` | Confirms process flow position |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Prevents re-processing |

---

## §5 — Execution Flow

1. Read `param` from `orderCurrentActivity.Parameter[1]` via XPath
2. Read `chkXPath` = `orderCurrentActivity.PreExecCheck`
3. Serialize `orderRequest` (not just OrderData) to XML string via `Instance.serializeUsingDefaults(orderRequest)`
4. Fire START audit logger (AUDIT_TRACE: "OMX-OM OMXSetOfferCallForward Started.")
5. If `PreExecCheck.length > 0`: evaluate XPath → `chkRes`; else `chkRes = "true"`
6. If `chkRes == "true"`:
   - a. Loop all ParentOU → Subscriber → SubscriberOffers → ParameterInfo
     - If any `ParameterInfo.ParamName` appears in `param` (comma-contained) → `isThere = true`
     - If `isThere` AND offer has no `OfferName`: set `Soc="0"`, `OfferName="DUMMY"`
   - b. Loop all ParentOU → ChildOU → Subscriber → SubscriberOffers → ParameterInfo
     - Two match conditions: direct equality OR comma-contained XPath check
     - If `isThere` AND offer has no `OfferName`: set `Soc="0"`, `OfferName="DUMMY"`
   - c. Call `NextActivity(orderRequest, orderCurrentActivity)`
   - d. Fire COMPLETED audit logger
7. Else: `SkipActivity(orderRequest, orderCurrentActivity, "4")`
8. On exception: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §6 — Rule Action (THEN) — Detailed Logic

### §6.1 — Parameter Reading

`param` is read from the first Parameter element of the current activity:

```java
String param = XPath.evalAsString("xpath://$orderCurrentActivity/Parameter[1]");
```

Example value: `"CFB,CFNRY,CFNRC,CFU"` — a comma-delimited list of call-forward parameter names.

### §6.2 — PreExecCheck Evaluation

PreExecCheck is evaluated against `Instance.serializeUsingDefaults(orderRequest)` (the full order request, not just OrderData). In POSTPAID_UPDATE_PARAMETER step 13, the PreExecCheck is commented out in the ProcessConfig XML, so `chkRes` always defaults to `"true"`.

### §6.3 — ParentOU Subscriber Loop (Match Logic)

For each `ParentOU[iPOU].Subscriber[iPOUSub].SubscriberOffers[iSubOffer]`:
- Scan `ParameterInfo[iParameter]` entries
- Match condition (XPath): `contains($param, concat(',', paramName))` — the comma-prefix ensures exact name matching
- If match found: `isThere = true` → break
- After inner loops: if `isThere == true`:
  - Check `exists($subOffer/OfferName)`
  - If no OfferName: `subOffer.Soc = "0"`; `subOffer.OfferName = "DUMMY"`

### §6.4 — ChildOU Subscriber Loop (Two Match Conditions)

The ChildOU loop adds an extra direct-equality check before the comma-contained XPath check:

```java
if(ParamName == param) { isThere = true; break; }
// Then falls through to the XPath contains() check if not matched above
```

> **[LOW]** The direct-equality check only fires if `ParamName` equals the full `param` string — only valid when param is a single value. This is effectively dead code for multi-value params and appears to be a legacy condition not removed when the XPath `contains()` check was added.

### §6.5 — Mutation Applied

| Field | Old value | New value | Condition |
|-------|-----------|-----------|-----------|
| `SubscriberOffers.Soc` | (empty / null) | `"0"` | isThere=true AND no OfferName |
| `SubscriberOffers.OfferName` | (empty / null) | `"DUMMY"` | isThere=true AND no OfferName |

---

## §8 — System & Integration Dependencies

### §8.4 — BE Working Memory — Read vs. Written

| Path | Direction | Details |
|------|-----------|---------|
| `orderCurrentActivity.Parameter[1]` | READ | Comma-separated list of call-forward ParamName values |
| `orderCurrentActivity.PreExecCheck` | READ | Optional gate XPath (commented-out in step 13) |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].ParameterInfo[*].ParamName` | READ | Match against param list |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].OfferName` | READ + WRITE | Check if absent → write "DUMMY" |
| `ParentOU[*].Subscriber[*].SubscriberOffers[*].Soc` | WRITE | Write "0" when offer is call-forward placeholder |
| `ParentOU[*].ChildOU[*].Subscriber[*].SubscriberOffers[*].ParameterInfo[*].ParamName` | READ | Match against param list |
| `ParentOU[*].ChildOU[*].Subscriber[*].SubscriberOffers[*].OfferName` | READ + WRITE | Check if absent → write "DUMMY" |
| `ParentOU[*].ChildOU[*].Subscriber[*].SubscriberOffers[*].Soc` | WRITE | Write "0" when offer is call-forward placeholder |

### §8.6 — ProcessConfig Parameters Consumed

| Parameter index | Variable | Expected format | Usage |
|----------------|----------|----------------|-------|
| `Parameter[1]` (first parameter) | `param` | Comma-separated ParamName values, e.g. `CFB,CFNRY,CFNRC,CFU` | Filter: which ParamName values identify call-forward offers |

*Note: `contains($param, concat(',', ParamName))` requires the target ParamName to not be the first entry unless a leading comma is included. Verify the actual ProcessConfig value follows a leading-comma convention.*

---

## §11 — Audit Logging

Two audit logger events — START (before loops) and COMPLETED (after NextActivity):

| Field | START value | COMPLETED value |
|-------|-------------|----------------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) | same |
| PROCESS_ID | `concat($pid, "_REQ")` | `concat($pid, "_RES")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | same |
| OPERATION_NAME | `"/Rules/OMConsumers/OMXOM/OMX_SET_OFFER_CALL_FORWARD"` | `"/Rules/OMConsumers/OMXOM/OMX_SetOfferCallForward"` |
| LOG_LEVEL | `$globalVariables/OMX_COMMON/.../MSG_LOG_LEVEL/INFO` | same |
| AUDIT_TRACE | `"OMX-OM OMXSetOfferCallForward Started."` | `"OMX-OM OMX_SetOfferCallForward Completed."` |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` | same |
| payload | Empty `<payload/>` | same |

> **[LOW]** OPERATION_NAME inconsistency: START uses `OMX_SET_OFFER_CALL_FORWARD` (underscore) while COMPLETED uses `OMX_SetOfferCallForward` (mixed case). This may cause log query discrepancies.

---

## §12 — Activity Status Management

| Scenario | Action | Resulting Status |
|----------|--------|----------------|
| PreExecCheck passes (or absent) | `NextActivity(orderRequest, orderCurrentActivity)` | COMPLETED |
| PreExecCheck fails | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | SKIPPED |
| Exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | ERROR |

---

## §13 — Exception / Error Handling

Single `try/catch(Exception ae)` wraps the entire THEN block. On exception: `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `XPath.evalAsString("xpath://$orderCurrentActivity/Parameter[1]")` | Reads first Parameter value (call-forward param list) |
| `Instance.serializeUsingDefaults(orderRequest)` | Serializes full order request to XML for PreExecCheck evaluation |
| `XPath.execute("/("+chkXPath+")", sXML, "ns0=...")` | Evaluates PreExecCheck gate expression |
| `XPath.evalAsBoolean("xpath://contains($param, concat(',', paramName))")` | Tests if offer's ParamName is in the call-forward list |
| `XPath.evalAsBoolean("xpath://exists($subOffer/OfferName)")` | Checks whether the offer has an OfferName |
| `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` | Marks activity complete and advances process flow |
| `RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")` | Marks activity SKIPPED when PreExecCheck fails |
| `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | Error handler |
| `Event.Ext.sendEventImmediate(Event.createEvent(Logger XSLT))` | Fires START and COMPLETED audit log events |

---

## §15 — Function Dependency Tree

```text
OMX_SET_OFFER_CALL_FORWARD (THEN block)
├── XPath.evalAsString("xpath://$orderCurrentActivity/Parameter[1]")   [read param]
├── Instance.serializeUsingDefaults(orderRequest)                       [serialize for PreExecCheck]
├── XPath.execute("/("+chkXPath+")", sXML, ...)                        [PreExecCheck gate]
├── Event.Ext.sendEventImmediate(Logger START)                          [audit start]
├── [outer loop] ParentOU
│   ├── [inner loop] Subscriber
│   │   └── [inner loop] SubscriberOffers
│   │       ├── [inner loop] ParameterInfo
│   │       │   └── XPath.evalAsBoolean("contains($param, concat(',', paramName))")
│   │       └── XPath.evalAsBoolean("exists($subOffer/OfferName)")
│   │           └── [mutation] subOffer.Soc = "0"; subOffer.OfferName = "DUMMY"
│   └── [inner loop] ChildOU
│       └── [inner loop] Subscriber
│           └── [inner loop] SubscriberOffers
│               ├── [inner loop] ParameterInfo
│               │   ├── direct: ParameterInfo.ParamName == param  (legacy check)
│               │   └── XPath.evalAsBoolean("contains($param, concat(',', paramName))")
│               └── XPath.evalAsBoolean("exists($subOffer/OfferName)")
│                   └── [mutation] subOffer.Soc = "0"; subOffer.OfferName = "DUMMY"
├── RuleFunctions.Helpers.NextActivity()                                [advance process]
├── Event.Ext.sendEventImmediate(Logger COMPLETED)                      [audit done]
├── SkipActivity("4")                                                   [PreExecCheck failed]
└── HandleActivityException()                                           [on error]
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Scan all SubscriberOffers (ParentOU and ChildOU subscribers) for entries whose ParameterInfo includes a call-forward param name from the configured list |
| R2 | Mark matched offers that have no OfferName with Soc="0" and OfferName="DUMMY" |
| R3 | The call-forward param name list must be configurable via ProcessConfig Parameter[1] |
| R4 | Offers that already have an OfferName must NOT be modified |
| R5 | Gate via PreExecCheck when configured; always run in POSTPAID_UPDATE_PARAMETER step 13 |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| `contains($param, concat(',', ParamName))` fails when the target ParamName is the first item in the list (no leading comma) | [MEDIUM] | Verify the actual ProcessConfig param value always starts with a comma, or change the XPath to also check `starts-with($param, $ParamName)` |
| ChildOU loop has legacy direct-equality check (`ParamName == full param string`) — dead code for multi-value params | [LOW] | Simplify to a single consistent match strategy in migration; remove the direct-equality check |
| OPERATION_NAME mismatch between START and COMPLETED logger can cause log correlation failures | [LOW] | Standardize OPERATION_NAME across both loggers in migration |
| Mutation of Soc and OfferName is irreversible within current process flow — failed retries see already-mutated "DUMMY" values | [MEDIUM] | Consider preserving original values in ExtendedInfo before overwriting; restore on retry/resubmit |
| Rule serializes the full `orderRequest` (not just OrderData) for PreExecCheck — more expensive and XPath expressions need to reference correct root path | [LOW] | Document this difference; ensure PreExecCheck expressions are validated against the full concept structure |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author DESKTOP-KB4BEG4
 */
rule Rules.OMConsumers.OMXOM.OMX_SET_OFFER_CALL_FORWARD {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "OMX_SET_OFFER_CALL_FORWARD";
        orderRequest.ProcessFlow.NextActivityID == "OMX_SET_OFFER_CALL_FORWARD";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        try {
            String param = XPath.evalAsString("xpath://$orderCurrentActivity/Parameter[1]");
            boolean isThere = false;
            String chkXPath = orderCurrentActivity.PreExecCheck;
            String chkRes = "true";
            String sXML = Instance.serializeUsingDefaults(orderRequest); // note: full orderRequest, not OrderData

            if(String.length(orderCurrentActivity.PreExecCheck) > 0) {
                chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=www.tibco.com/be/ontology/...");
            }

            if(String.equals(chkRes, "true")) {
                long pid = System.nanoTime();
                Event.Ext.sendEventImmediate(Event.createEvent(/* Logger START — see §11 */));

                // Loop ParentOU → Subscriber → SubscriberOffers → ParameterInfo
                int iPOU = 0;
                for(iPOU = 0; iPOU < orderRequest.OrderData.Customer.ParentOU@length; iPOU++) {
                    for(int iPOUSub = 0; iPOUSub < ...ParentOU[iPOU].Subscriber@length; iPOUSub++) {
                        int psubsOffers = ...Subscriber[iPOUSub].SubscriberOffers@length;
                        for(int iSubOffer = 0; iSubOffer < psubsOffers; iSubOffer++) {
                            isThere = false;
                            int pParameter = ...SubscriberOffers[iSubOffer].ParameterInfo@length;
                            for(int iParameter = 0; iParameter < pParameter; iParameter++) {
                                if(XPath.evalAsBoolean("xpath://contains($param, concat(',', ParameterInfo[$iParameter+1]/ParamName))")) {
                                    isThere = true; break;
                                }
                            }
                            if(isThere == true) {
                                SubscriberOffers subOffer = ...SubscriberOffers[iSubOffer];
                                boolean chkOffer = XPath.evalAsBoolean("xpath://exists($subOffer/OfferName)");
                                if(!chkOffer) {
                                    ...SubscriberOffers[iSubOffer].Soc = "0";
                                    ...SubscriberOffers[iSubOffer].OfferName = "DUMMY";
                                }
                            }
                        }
                    }

                    // ChildOU loop — same pattern with extra direct-equality check first (see §6.4)
                    for(int iCOU = 0; iCOU < ...ParentOU[iPOU].ChildOU@length; iCOU++) {
                        for(int iCOUSub = 0; iCOUSub < ...ChildOU[iCOU].Subscriber@length; iCOUSub++) {
                            int psubsOffers = ...Subscriber[iCOUSub].SubscriberOffers@length;
                            for(int iSubOffer = 0; iSubOffer < psubsOffers; iSubOffer++) {
                                isThere = false;
                                int pParameter = ...SubscriberOffers[iSubOffer].ParameterInfo@length;
                                for(int iParameter = 0; iParameter < pParameter; iParameter++) {
                                    if(...ParameterInfo[iParameter].ParamName == param) { isThere = true; break; } // legacy check
                                    if(XPath.evalAsBoolean("xpath://contains($param, concat(',', ParameterInfo[...]/ParamName))")) {
                                        isThere = true; break;
                                    }
                                }
                                if(isThere == true) {
                                    SubscriberOffers subOffer = ...SubscriberOffers[iSubOffer];
                                    boolean chkOffer = XPath.evalAsBoolean("xpath://exists($subOffer/OfferName)");
                                    if(!chkOffer) {
                                        ...SubscriberOffers[iSubOffer].Soc = "0";
                                        ...SubscriberOffers[iSubOffer].OfferName = "DUMMY";
                                    }
                                }
                            }
                        }
                    }
                } // end ParentOU loop

                RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity);
                Event.Ext.sendEventImmediate(Event.createEvent(/* Logger COMPLETED — see §11 */));
            } else {
                RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch(Exception ae) {
            RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
        }
    }
}
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
