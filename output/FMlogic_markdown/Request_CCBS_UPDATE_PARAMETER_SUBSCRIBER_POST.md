# Request_CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST

> Update subscriber offer parameters in CCBS — serialized per-offer dispatch (IntraActivitySequencing) across POU and COU subscribers.

**Author:** RS33-BANDIT | **Priority:** 5 | **forwardChain:** true | **Pattern:** IntraActivitySequencing (serialized) | **Generated:** 2026-08-20

---

## §1 — Overview & Purpose

This rule updates subscriber offer parameters in CCBS for each qualifying `SubscriberOffers` entry across POU and COU subscribers. Each offer generates one serialized `CCBS_UPDATE_SUBSCRIBER` event via the **IntraActivitySequencing** pattern — requests are queued and dispatched one at a time (not in parallel), preserving CCBS ordering guarantees.

Used in POSTPAID_UPDATE_PARAMETER step 24 — runs after OMX_EXP_FUT_PP expires future PP orders; updates subscriber offer parameters for the new configuration post-update.

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST` |
| Event type (outbound) | `Events.OMConsumers.OMXFM.Request.CCBS_UPDATE_SUBSCRIBER` |
| Event type (inbound response) | `Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_SUBSCRIBER` |
| Payload schema | `ns:UpdateSubscriberRequest` — per-offer serialized |
| Response concept | `Concepts.FM.Response.CCBS_UpdateSubscriberRes` |
| Dispatch pattern | IntraActivitySequencing — serialized one-at-a-time |
| Scope A (POU Subscriber) | All POU Subscribers, all SubscriberOffers — FE_OR_CCBS gate for OrderType=5 |
| Scope B (COU Subscriber) | All COU Subscribers, all SubscriberOffers — ServiceType ≠ "80" gate |
| refId (resubmit key) | `Subscriber.RefId + ":" + offer.Soc` |
| Parameters | ACTIVITY_REASON (optional override), MAP_EFF_EXP (Y/N — gate for dates) |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Note |
|-----------|-------|------|
| priority | 5 | Standard FM request priority |
| forwardChain | true | Allows further rule evaluation after execution |
| Rule type | OMXFM Request | Dispatches to CCBS via JMS; has response rulefunction |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order — entity hierarchy, subscriber offers, activity parameters |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — Status, RequestCount, Response[], IntraActivitySequencing queue |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity position match |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST"` | Redundant dual binding |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Fires only when awaiting execution |

---

## §5 — Execution Flow

1. **Resubmit detection** → `isActResub = (RequestCount > 0 && IsOrderResubmitted)`; if resub → `PurgePendingRequestsBeforeResubmit()`
2. **Load shared state** → LogicalDate, nextAct (PreExecCheck), ACTIVITY_REASON, MAP_EFF_EXP parameters
3. **Scope A — POU Subscriber** → 3-level loop POU[i] → Subscriber[p] → SubscriberOffers[q]; FE_OR_CCBS gate; resubmit guard; per-offer PreExecCheck; build/queue CCBS_UPDATE_SUBSCRIBER event; audit log
4. **Scope B — COU Subscriber** → 4-level loop POU[i] → ChildOU[u] → Subscriber[v] → SubscriberOffers[w]; ServiceType≠80 gate; resubmit guard; per-offer PreExecCheck; build/queue event; audit log
5. **Dispatch or skip** → if any events queued: `SendFirstRequestEvent()` → INPROGRESS → `SendDataToDB()`; else `SkipActivity("4")`
6. **Exception handling** → catch all → `HandleActivityException()`

---

## §6 — Rule Action (THEN) — Detailed Logic

### Scope A — POU Subscriber (3-level nested loop)

| Dimension | Detail |
|-----------|--------|
| Loop structure | `POU[i]` → `Subscriber[p]` → `SubscriberOffers[q]` |
| refId | `ParentOU[i].Subscriber[p].RefId + ":" + subOff.Soc` |
| FE_OR_CCBS gate | XPath: `(FE_OR_CCBS='FE' AND OrderType='5') OR OrderType != '5'` |
| ServiceType filter | None — all service types processed |
| PreExecCheck helper | `GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, soc, filter)` |
| instanceId priority | 1st: `ExtendedInfo[Name='instanceid']/Value`; 2nd: `OfferInstanceId > 0` |
| instanceId exclusions | CFNRC_NO_PARAM, CFNRY_NO_PARAM, CFW_NO_PARAM, CFU_NO_PARAM |
| KNOX support | `ExtendedInfo[Name='IMEI_KNOX']` → `ns:ReplacePhysicalResourceInputInfo` with name="KNOX" |

### Scope B — COU Subscriber (4-level nested loop)

| Dimension | Detail |
|-----------|--------|
| Loop structure | `POU[i]` → `ChildOU[u]` → `Subscriber[v]` → `SubscriberOffers[w]` |
| refId | `ParentOU[i].ChildOU[u].Subscriber[v].RefId + ":" + subOff.Soc` |
| ServiceType filter | `ServiceType != "80"` — skips price plan offers |
| FE_OR_CCBS gate | None — all offers that pass ServiceType filter are sent |
| PreExecCheck helper | `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(orderRequest, refId, soc, parentRefId, filter)` |
| instanceId | Directly uses `OfferInstanceId > 0` — no `instanceid` ExtendedInfo check |
| KNOX support | Yes — same pattern as POU scope |

> **[MEDIUM] COU XSLT root ns:SubscriberIdInfo bug:** References `ParentOU[$OU]/Subscriber[$sub]/SubscriberId` but `$sub = v+1` indexes the COU subscriber (not POU). Correct path: `ParentOU[$OU]/ChildOU[$child]/Subscriber[$sub]/SubscriberId`.

> **[MEDIUM] COU XSLT root ActivityInfo else-clause bug:** Fallback `ns:activityReason` references POU path instead of `ParentOU[$OU]/ChildOU[$child]/Subscriber[$sub]/SubscriberActivityInfo/ActivityReason`.

### Scope Comparison

| Dimension | POU Subscriber (Scope A) | COU Subscriber (Scope B) |
|-----------|--------------------------|--------------------------|
| ServiceType filter | None | ServiceType ≠ "80" |
| FE_OR_CCBS gate | Yes — OrderType=5 gate | None |
| instanceid ExtendedInfo | Checked first (priority) | Not checked |
| PreExecCheck helper | `GetXMLForSubscriberOfferFilterWithExtendedInfo` | `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo` |
| Root SubscriberIdInfo | Correct POU path | **Bug: Wrong path** |

### ActivityReason Priority Logic (both scopes)

```
1. if actReasonParam != ""   → use actReasonParam  (ACTIVITY_REASON parameter)
2. else if SubscriberActivityInfo/ActivityReason exists and non-empty
                             → use SubscriberActivityInfo/ActivityReason
3. else                      → "CREQ"  (default)
```

### OfferInstanceId Resolution (POU scope — per ParameterInfo)

```
Unless ParamName ∈ { CFNRC_NO_PARAM, CFNRY_NO_PARAM, CFW_NO_PARAM, CFU_NO_PARAM }:
  if   ExtendedInfo[Name='instanceid'] exists → use ExtendedInfo[Name='instanceid']/Value
  elif OfferInstanceId > 0                    → use OfferInstanceId
```

---

## §8 — System & Integration Dependencies

### §8.1 — Activity Parameters

| Parameter Key | Type | Effect |
|--------------|------|--------|
| ACTIVITY_REASON | Optional String | Overrides all `ns:activityReason` values when non-empty |
| MAP_EFF_EXP | Optional String (Y/N) | If "Y", maps EffectiveDate and ExpirationDate from ParameterInfo |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_UPDATE_SUBSCRIBER` | Serialized per-offer subscriber parameter update |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_SUBSCRIBER` | CCBS update confirmation |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | Audit logging (one per dispatched event) |

### §8.3 — Backend API Details

| System | Operation | Schema | Protocol |
|--------|-----------|--------|----------|
| CCBS | UpdateSubscriber | `ns:UpdateSubscriberRequest` (UpdateSubscriberRequest.xsd) | JMS / TIBCO EMS |

### §8.4 — BE Working Memory Dependencies

| Concept | Access | Fields Used |
|---------|--------|-------------|
| `OrderRequest` | Read | OrderData.Customer.ParentOU[].Subscriber[].SubscriberOffers[], OrderData.Customer.ParentOU[].ChildOU[].Subscriber[].SubscriberOffers[], OrderPriority, OMXTrackingId, OrderID, OrderType, User, Password, CES |
| `Activity` | Read/Write | Status, RequestCount, Response[], IntraActivitySequencing queue, Parameter[], PreExecCheck |
| `LogicalDate` | Read | LogicalDate (loaded but not used in XSLT payloads) |

### §8.5 — ExtendedInfo Fields Required

| Key | Scope | Purpose |
|-----|-------|---------|
| `FE_OR_CCBS` | SubscriberOffers (POU) | Gate for FE/CCBS routing; Value='FE' required when OrderType=5 |
| `instanceid` | ParameterInfo (POU) | Override for offerInstanceId; priority over OfferInstanceId field |
| `IMEI_KNOX` | SubscriberOffers (both) | Triggers ReplacePhysicalResourceInputInfo block with resource "KNOX" |

### §8.6 — Global Variable Dependencies

| Path | Used For |
|------|----------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Gates UserName/PassWord in event header |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Gates payload in audit log |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

### Scope A (POU) — CCBS_UPDATE_SUBSCRIBER

```text
createEvent
└── event
    ├── JMSPriority         ← $orderRequest/OrderPriority                   [Conditional]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId         [Conditional]
    ├── OrderID             ← $orderRequest/OrderData/OrderID               [Conditional]
    ├── RefID               ← $refId (Subscriber.RefId + ":" + Soc)         [Always]
    ├── UserName            ← $orderRequest/OrderData/User                  [Conditional: IsEnableUserPass='true']
    ├── PassWord            ← $orderRequest/OrderData/Password              [Conditional: IsEnableUserPass='true']
    ├── OrderType           ← $orderRequest/OrderData/OrderType             [Conditional]
    ├── CES                 ← $orderRequest/OrderData/CES                   [Conditional]
    └── payload                                                              [Always]
        └── ns:UpdateSubscriberRequest
            └── ns:UpdateSubscriberRequest
                ├── ns:SubscriberIdInfo
                │   └── ns:subscrNumber ← ParentOU[$OU]/Subscriber[$sub]/SubscriberId
                ├── ns:UpdateParameterInputInfo [xsl:for-each $subOff/ParameterInfo]
                │   ├── ns:SubscriberIdInfo/ns:subscrNumber ← $subsId
                │   ├── ns:ParameterInfo
                │   │   ├── ns:name          ← ParamName                   [Always]
                │   │   ├── ns:values        ← ValuesArray                 [Conditional: ValuesArray exists]
                │   │   ├── ns:offerInstanceId [xsl:choose — unless ParamName ∈ CF exclusion list]
                │   │   │   ├── when: ExtendedInfo[Name='instanceid'] exists → ExtendedInfo[Name='instanceid']/Value
                │   │   │   └── otherwise: OfferInstanceId > 0 → OfferInstanceId
                │   │   ├── ns:effectiveDate ← EffectiveDate              [Conditional: mapEffExp='Y']
                │   │   └── ns:expirationDate ← ExpirationDate            [Conditional: mapEffExp='Y']
                │   └── ns:ActivityInfo
                │       ├── ns:activityReason [Priority: actReasonParam → ActivityReason → "CREQ"]
                │       └── ns:userText      ← SubscriberActivityInfo/UserText  [Conditional]
                ├── ns:ReplacePhysicalResourceInputInfo [xsl:for-each ExtendedInfo[Name='IMEI_KNOX']]
                │   ├── ns:SubscriberIdInfo/ns:subscrNumber ← $subsId
                │   ├── ns:PhysicalResourceInfo
                │   │   ├── ns:name   ← "KNOX"                            [Always, static]
                │   │   ├── ns:values ← Value (IMEI)                      [Always]
                │   │   └── ns:offerInstanceId ← OfferInstanceId          [Conditional]
                │   └── ns:ActivityInfo/ns:activityReason ← "CREQ"        [Always, static]
                └── ns:ActivityInfo (root-level)
                    ├── ns:activityReason [Priority: actReasonParam → ActivityReason → "CREQ"]
                    └── ns:userText      ← SubscriberActivityInfo/UserText  [Conditional]
```

**Scope B (COU):** Identical structure except: root `ns:SubscriberIdInfo` should use `ChildOU[$child]/Subscriber[$sub]` (bug: currently uses `Subscriber[$sub]` under POU); no `instanceid` ExtendedInfo check; ActivityInfo uses COU paths (except root else-clause bug).

**Legend:** `← XPath` = dynamic source, `static` = hardcoded literal, `[Conditional]` = inside xsl:if

---

## §11 — Audit Logging

| Event | OPERATION_NAME | AUDIT_TRACE | Note |
|-------|---------------|------------|------|
| Request (both scopes) | CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST | "Request Sent for CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST" | OK |
| Response | CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST | "Response received for CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST" | OK |

Audit logging is correctly named in both request and response — no copy-paste bugs.

---

## §12 — Activity Status Management

| Condition | Status | Call |
|-----------|--------|------|
| At least one event queued and dispatched | INPROGRESS | `SendFirstRequestEvent()` → `GetActivityStatusString("1", false)` |
| No qualifying offers in either scope | SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception caught | ERROR | `HandleActivityException()` |

---

## §13 — Exception / Error Handling

All logic wrapped in `try { ... } catch (Exception ae)` → `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)` | Clears pending serialized queue on resubmit |
| `GetActivityParameterValueFromKey(orderCurrentActivity, key)` | Reads ACTIVITY_REASON and MAP_EFF_EXP |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo(...)` | PreExecCheck XML document — POU scope |
| `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...)` | PreExecCheck XML document — COU scope (includes parent OU RefId) |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Queues event for serialized dispatch |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Dispatches first queued event |
| `GetActivityStatusString("1", false)` | Returns INPROGRESS status string |
| `SendDataToDB(orderRequest)` | Persists order state |
| `SkipActivity(orderRequest, orderCurrentActivity, "4")` | Marks activity skipped |
| `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` | Records exception, sets ERROR state |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST.rule
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()   [if resub]
├── Instance.getByExtIdByUri("LogicalDate", ...)
├── Instance.getByExtIdByUri(NextActivityName, ...)                 [load nextAct]
├── GetActivityParameterValueFromKey(, "ACTIVITY_REASON")
├── GetActivityParameterValueFromKey(, "MAP_EFF_EXP")
├── [Scope A] Loop: POU[i] → Subscriber[p] → SubscriberOffers[q]
│   ├── XPath.evalAsString(FE_OR_CCBS ExtendedInfo value)
│   ├── [Resubmit guard] Loop Response[] → ReferenceId==refId && CompletionStatus==2
│   ├── XPath.evalAsBoolean(FE_OR_CCBS gate)
│   ├── GetXMLForSubscriberOfferFilterWithExtendedInfo()
│   ├── XPath.execute("/(PreExecCheck)", sXML, ...)
│   ├── Event.createEvent("xslt://CCBS_UPDATE_SUBSCRIBER")         [POU XSLT]
│   ├── Event.assertEvent()
│   ├── IntraActivitySequencing.ActionRequestEvent()               [queue]
│   └── Event.Ext.sendEventImmediate() → Logger
├── [Scope B] Loop: POU[i] → ChildOU[u] → Subscriber[v] → SubscriberOffers[w]
│   ├── [ServiceType != "80" gate]
│   ├── [Resubmit guard] Loop Response[]
│   ├── GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo()
│   ├── XPath.execute("/(PreExecCheck)", sXML, ...)
│   ├── Event.createEvent("xslt://CCBS_UPDATE_SUBSCRIBER")         [COU XSLT — bugs noted]
│   ├── Event.assertEvent()
│   ├── IntraActivitySequencing.ActionRequestEvent()               [queue]
│   └── Event.Ext.sendEventImmediate() → Logger
├── IntraActivitySequencing.SendFirstRequestEvent()                 [trigger dispatch]
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB()
├── RuleFunctions.Helpers.SkipActivity()
└── RuleFunctions.Helpers.HandleActivityException()

Response_CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST.rulefunction
├── OMXUtils.generateTrackingID()
├── Instance.createInstance("xslt://CCBS_UpdateSubscriberRes")
│   ├── ResponseCode        ← $eventResponse/ResponseCode
│   ├── ResponseMessage     ← $eventResponse/ResponseMsg
│   ├── CompletionStatus    ← $eventResponse/CompletionStatus
│   └── ReferenceId         ← $eventResponse/RefID              [correctly mapped]
├── currActivity.Response[Response@length] = activityRes
├── Event.Ext.sendEventImmediate() → Logger
└── IntraActivitySequencing.ActionResponseEvent(currActivity)
    ├── → "true"  (all queued requests completed)
    └── → "false" (more responses pending — next queued event dispatched)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Update POU subscriber offer parameters in CCBS for all SubscriberOffers (FE_OR_CCBS gate when OrderType=5) |
| R2 | Update COU subscriber offer parameters — skip ServiceType="80" (price plan) offers |
| R3 | Serialize dispatch — one request at a time via IntraActivitySequencing |
| R4 | Resubmit guard: skip offers already confirmed complete (ReferenceId + CompletionStatus=2) |
| R5 | Per-offer PreExecCheck before dispatch |
| R6 | Conditional offerInstanceId: prefer `ExtendedInfo[Name='instanceid']` over `OfferInstanceId`; exclude from CFNRC/CFNRY/CFW/CFU params |
| R7 | KNOX device update: if `ExtendedInfo[Name='IMEI_KNOX']` → include ReplacePhysicalResourceInputInfo with name="KNOX" |
| R8 | MAP_EFF_EXP='Y' → map EffectiveDate and ExpirationDate from ParameterInfo |
| R9 | ACTIVITY_REASON overrides all activityReason values when set |

### Design Risks

| Risk | Severity | Detail | Mitigation |
|------|----------|--------|-----------|
| COU XSLT root ns:SubscriberIdInfo wrong XPath | [MEDIUM] | References `ParentOU[$OU]/Subscriber[$sub]` — `$sub` is COU index; CCBS gets empty/wrong subscriber number when COU index > POU subscriber count | Fix to `ParentOU[$OU]/ChildOU[$child]/Subscriber[$sub]/SubscriberId` |
| COU XSLT root ActivityInfo else-clause wrong path | [MEDIUM] | Fallback `ns:activityReason` references POU subscriber path | Fix to COU path |
| LogicalDate loaded but not used | [LOW] | Dead code — loaded but never referenced in XSLT | Remove or document intended use |
| Asymmetric scope behaviour (POU vs COU) | [MEDIUM] | Different ServiceType and FE_OR_CCBS filters per scope, different instanceId logic — undocumented; regression risk | Document intentional divergence; add per-scope tests |
| Per-offer serialization performance | [MEDIUM] | Linear latency scaling with many offers across many entities | Consider parallel dispatch if CCBS supports concurrent updates |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author RS33-BANDIT
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST";
        orderRequest.ProcessFlow.NextActivityID == "CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.LogicalDate logicalDateRes = Instance.getByExtIdByUri("LogicalDate", ...);
            String logicalDateVal = logicalDateRes.LogicalDate; // [LOW: loaded but unused]
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(NextActivityName, ...);

            if(isActResub) {
                IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
            }

            String actReasonParam = GetActivityParameterValueFromKey(orderCurrentActivity, "ACTIVITY_REASON");
            String mapEffExp = GetActivityParameterValueFromKey(orderCurrentActivity, "MAP_EFF_EXP");
            boolean isSkipped = true;

            // ── Scope A: POU Subscriber ────────────────────────────────────────
            for(int i=0; i < POU@length; i++) {
                for(int p=0; p < Subscriber@length; p++) {
                    String subsId = ParentOU[i].Subscriber[p].SubscriberId;
                    for(int q=0; q < SubscriberOffers@length; q++) {
                        Concepts...SubscriberOffers subOff = SubscriberOffers[q];
                        String refId = RefId + ":" + subOff.Soc;
                        String filter = XPath.evalAsString(/* FE_OR_CCBS ExtendedInfo */);
                        boolean reqSuccess = false;
                        for(...) { if(ReferenceId==refId && CompletionStatus==2) reqSuccess = true; }
                        if(!reqSuccess) {
                            if(XPath.evalAsBoolean("(FE_OR_CCBS='FE' AND OrderType='5') OR OrderType!='5'")) {
                                String sXML = GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, refId, soc, filter);
                                String chkRes = XPath.execute("/("+chkXPath+")", sXML, ...);
                                if(String.equals(chkRes,"true")) {
                                    Events...CCBS_UPDATE_SUBSCRIBER updateParamEvent = Event.createEvent(/* see §10 — POU XSLT */);
                                    Event.assertEvent(updateParamEvent);
                                    IntraActivitySequencing.ActionRequestEvent(updateParamEvent, orderCurrentActivity);
                                    isSkipped = false;
                                    Event.Ext.sendEventImmediate(/* Logger: Request Sent for CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST */);
                                }
                            }
                        }
                    }
                }
            }

            // ── Scope B: COU Subscriber ────────────────────────────────────────
            for(int i=0; i < POU@length; i++) {
                for(int u=0; u < ChildOU@length; u++) {
                    for(int v=0; v < Subscriber@length; v++) {
                        String subsId = ChildOU[u].Subscriber[v].SubscriberId;
                        for(int w=0; w < SubscriberOffers@length; w++) {
                            if(!String.equals(ServiceType, "80")) { // skip PP offers
                                Concepts...SubscriberOffers subOff = SubscriberOffers[w];
                                String refId = ChildOU[u].Subscriber[v].RefId + ":" + subOff.Soc;
                                boolean reqSuccess = false;
                                for(...) { if(ReferenceId==refId && CompletionStatus==2) reqSuccess = true; }
                                if(!reqSuccess) {
                                    String sXML = GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...);
                                    String chkRes = XPath.execute(...);
                                    if(String.equals(chkRes,"true")) {
                                        Events...CCBS_UPDATE_SUBSCRIBER updateParamEvent = Event.createEvent(/* see §10 — COU XSLT [MEDIUM: wrong SubscriberIdInfo path] */);
                                        Event.assertEvent(updateParamEvent);
                                        IntraActivitySequencing.ActionRequestEvent(updateParamEvent, orderCurrentActivity);
                                        Event.Ext.sendEventImmediate(/* Logger */);
                                        isSkipped = false;
                                    }
                                }
                            }
                        }
                    }
                }
            }

            if(!isSkipped) {
                IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
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

## §19 — Response Message Rule

### §19.1 — Overview

`Response_CCBS_UPDATE_PARAMETER_SUBSCRIBER_POST.rulefunction` — receives CCBS update confirmation for each serialized request, creates a `CCBS_UpdateSubscriberRes` concept (including ReferenceId for resubmit correlation), appends to Response[], sends audit log, and delegates fan-in control to `IntraActivitySequencing.ActionResponseEvent`.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order for audit logging |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_SUBSCRIBER` | Inbound CCBS update confirmation |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] target; IntraActivitySequencing queue controller |

### §19.3 — ResponseBase Concept Construction (CCBS_UpdateSubscriberRes)

```text
createObject
└── object @extId ← OMXUtils.generateTrackingID()                [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode         [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg          [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus     [Conditional]
    └── ReferenceId         ← $eventResponse/RefID               [Conditional — correctly mapped]
```

`ReferenceId` is correctly mapped from `RefID` — enables the per-offer resubmit guard (`ReferenceId == refId && CompletionStatus == 2`) to function correctly.

### §19.4 — Response Completion Logic (IntraActivitySequencing)

| Return value | Meaning | Action |
|-------------|---------|--------|
| `"true"` | All queued requests completed | Activity fan-in satisfied; process continues |
| `"false"` | More responses expected | IntraActivitySequencing dispatches next queued event |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
