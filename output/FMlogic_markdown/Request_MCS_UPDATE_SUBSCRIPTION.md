# Request_MCS_UPDATE_SUBSCRIPTION

> Notify MCS to update mobile subscription on device change — per-Material parallel fan-out across POU and COU Subscriber scopes

**Author:** (not specified) | **Priority:** 5 | **forwardChain:** true | **Pattern:** sendEventImmediate parallel fan-out

---

## §1 — Overview & Purpose

This rule calls MCS (Mobile Content Service) to update a mobile subscription record when a subscriber's physical device (handset Material) changes — typically as part of a device trade-in or parameter update. One `MCS_UPDATE_SUBSCRIPTION` event is dispatched per qualifying subscriber Material (identified by `MatCode`) across two scopes: POU Subscriber and COU Subscriber. Dispatch is via `sendEventImmediate` (parallel fan-out). Subscribers without a `MaterialInfo` record are skipped entirely.

> **Used in POSTPAID_UPDATE_PARAMETER step 30** — MCS subscription update follows PSA device activities (KNOX save, notify Kafka, PSA_UPDATE_DEVICE) in the device trade-in flow.

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_MCS_UPDATE_SUBSCRIPTION` |
| Outbound event | `Events.OMConsumers.OMXFM.Request.MCS_UPDATE_SUBSCRIPTION` |
| Response event | `Events.OMConsumers.OMXFM.Response.MCS_UPDATE_SUBSCRIPTION` |
| Payload root | `ns8:updateSubscriptionReq` (UpdateSubscriptionRequest.xsd) |
| Response concept | `Concepts.FM.Base.ResponseBase` |
| Dispatch pattern | sendEventImmediate — parallel fan-out per Material |
| resubmit refId key | `SubRefId + ":" + material.MatCode` |
| Entry gate | `psub/csub.MaterialInfo != null` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Note |
|-----------|-------|------|
| priority | 5 | Standard FM request priority |
| forwardChain | true | Allows further rule evaluation after execution |
| Author | (none) | Empty @description block — no @author tag |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order — entity hierarchy, subscriber Materials, extended info |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — Status, RequestCount, Response[], PreExecCheck |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity position match |
| 2 | `orderCurrentActivity.ActivityID == "MCS_UPDATE_SUBSCRIPTION"` | Activity type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "MCS_UPDATE_SUBSCRIPTION"` | Redundant dual binding |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Fires only when awaiting execution |

---

## §5 — Execution Flow

1. **Resubmit detection** — `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. **Load PreExecCheck XPath** — load `nextAct` Activity concept; read `nextAct.PreExecCheck` into `chkXPath`
3. **Scope A — POU Subscriber → Material** — loop POU[p] → Subscriber[ps] → (if MaterialInfo!=null) → Material[pmat]; per-Material PreExecCheck; resubmit guard; build + send POU XSLT variant
4. **Scope B — COU Subscriber → Material** — loop POU[p] → ChildOU[c] → Subscriber[cs] → (if MaterialInfo!=null) → Material[cmat]; per-Material PreExecCheck; resubmit guard; build + send COU XSLT variant
5. **Dispatch or skip** — if any events sent: INPROGRESS → `SendDataToDB()`; else `SkipActivity("4")`
6. **Exception handling** — catch all → `HandleActivityException()`

---

## §6 — Rule Action (THEN) — Detailed Logic

### Scope A — POU Subscriber → Material

| Dimension | Detail |
|-----------|--------|
| Loop | `ParentOU[p] → Subscriber[ps] → (if MaterialInfo!=null) → Material[pmat]` |
| refId (resubmit key) | `pMatRefId = pSubRefId + ":" + material.MatCode` |
| Resubmit guard | `Response[iResp].ReferenceId == pMatRefId && CompletionStatus == 2` |
| PreExecCheck XML builder | if MatCode not blank → `GetXMLForSubscriberMaterialInfo(orderRequest, pSubRefId, material.MatCode)` else → `GetXMLForSubscriberMaterialInfo(orderRequest, pSubRefId, material.MatSerial)` |
| XSLT params | `orderRequest, pMatRefId, globalVariables, material, psub` |
| Loaded but unused | `pOuId` — loaded but never used in payload or logic |
| pOuRefId | Loaded here but NOT used in POU scope; used only in COU PreExecCheck helper |

### Scope B — COU Subscriber → Material

| Dimension | Detail |
|-----------|--------|
| Loop | `ParentOU[p] → ChildOU[c] → Subscriber[cs] → (if MaterialInfo!=null) → Material[cmat]` |
| refId (resubmit key) | `cMatRefId = cSubRefId + ":" + material.MatCode` |
| Resubmit guard | `Response[iResp].ReferenceId == cMatRefId && CompletionStatus == 2` |
| PreExecCheck XML builder | if MatCode not blank → `GetXMLForSubscriberMaterialInChildOU(orderRequest, cSubRefId, pOuRefId, material.MatCode)` else → `GetXMLForSubscriberMaterialInChildOU(orderRequest, cSubRefId, pOuRefId, material.MatSerial)` |
| XSLT params | `orderRequest, cMatRefId, globalVariables, material, csub` |
| Loaded but unused | `cOuId`, `cOuRefId` — loaded but never used |

> **[LOW] MatCode vs MatSerial fallback in PreExecCheck builder:** If `material.MatCode` is blank, the helper is called with `material.MatSerial` instead. The same selection does NOT apply to `ns8:handset` — that is always from MatCode.

> **[MEDIUM] Unused variables:** `pOuId` (line 30), `cOuId` (line 91), `cOuRefId` (line 92) are loaded but never referenced. Dead code.

---

## §8 — System & Integration Dependencies

### §8.1 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.MCS_UPDATE_SUBSCRIPTION` | Per-Material MCS subscription update (parallel fan-out) |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.MCS_UPDATE_SUBSCRIPTION` | MCS subscription update confirmation |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | Audit log per dispatched event |

### §8.2 — Backend API Details

| System | Operation | Schema | Protocol |
|--------|-----------|--------|----------|
| MCS | MCS_UPDATE_SUBSCRIPTION | `ns8:updateSubscriptionReq` (UpdateSubscriptionRequest.xsd) | JMS / TIBCO EMS |

### §8.3 — BE Working Memory Dependencies

| Concept | Access | Fields Used |
|---------|--------|-------------|
| `OrderRequest` | Read | OrderData.{OMXTrackingId, OrderID, OrderType, OrderPriority, Channel, SubmissionDate, User, Password, ExtendedInfo[FE_LOGIN_USER, TPC_REFNO]}, Customer.{ParentOU[].Subscriber[].{RefId, MSISDN, MaterialInfo.Material[].{MatCode, MatSerial}, ExtendedInfo[NEW_MAT_SERIAL, PARTNER, SR_TYPE]}} |
| `Activity` | Read/Write | Status, RequestCount, Response[], PreExecCheck |

### §8.4 — ExtendedInfo Fields Required

| Key | Location | Required | Purpose in Payload |
|-----|----------|----------|--------------------|
| `FE_LOGIN_USER` | OrderData.ExtendedInfo | Optional | `ns8:requestor_id` — front-end operator |
| `TPC_REFNO` | OrderData.ExtendedInfo | Optional | `ns8:ref_id` — TPC reference number |
| `NEW_MAT_SERIAL` | Subscriber.ExtendedInfo | Optional | `ns8:imei` — new device IMEI being registered |
| `PARTNER` | Subscriber.ExtendedInfo | Optional | `ns8:channel_code` — partner/dealer code |
| `SR_TYPE` | Subscriber.ExtendedInfo | Optional | `ns8:sr_type` — service request type |

### §8.5 — Global Variable Dependencies

| Path | Used For |
|------|---------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Guards UserName/PassWord in JMS event |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Gates payload copy in audit log |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

> Two XSLT variants — POU Subscriber (params: pMatRefId, material, psub) and COU Subscriber (params: cMatRefId, material, csub). The payload schema is identical; only RefID source and subscriber variable differ.

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                             [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId                  [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                         [Conditional]
    ├── RefID                ← $pMatRefId / $cMatRefId (SubRefId:MatCode)              [Always]
    ├── UserName             ← $orderRequest/OrderData/User                            [Conditional: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password                        [Conditional: IsEnableUserPass='true']
    ├── OrderType            ← $orderRequest/OrderData/OrderType                       [Conditional]
    └── payload                                                                         [Always]
        └── ns8:updateSubscriptionReq
            ├── ns8:transaction_id   ← $orderRequest/OrderData/OMXTrackingId          [Conditional]
            ├── ns8:requestor_id     ← ExtendedInfo[Name='FE_LOGIN_USER']/Value        [Conditional]
            ├── ns8:ref_id           ← ExtendedInfo[Name='TPC_REFNO']/Value            [Conditional]
            ├── ns8:registered_imei  ← $material/MatSerial                             [Conditional — old/existing IMEI]
            ├── ns8:imei             ← $psub/$csub/ExtendedInfo[Name='NEW_MAT_SERIAL'] [Conditional — new IMEI]
            ├── ns8:handset          ← $material/MatCode                               [Conditional]
            ├── ns8:msisdn           ← $psub/$csub/MSISDN                              [Conditional]
            ├── ns8:channel          ← $orderRequest/OrderData/Channel                 [Conditional]
            ├── ns8:channel_code     ← $psub/$csub/ExtendedInfo[Name='PARTNER']        [Conditional]
            ├── ns8:sr_type          ← $psub/$csub/ExtendedInfo[Name='SR_TYPE']        [Conditional]
            └── ns8:sr_creation_date ← tib:format-dateTime("yyyy-MM-dd'T'HH:mm:ssXXX", SubmissionDate) [Always]
```

### POU vs COU XSLT — Field Differences

| Field | POU Variant | COU Variant |
|-------|-------------|-------------|
| Event RefID | `$pMatRefId` = `pSubRefId:MatCode` | `$cMatRefId` = `cSubRefId:MatCode` |
| Subscriber param name | `$psub` | `$csub` |
| ns8:imei source | `$psub/ExtendedInfo[Name='NEW_MAT_SERIAL']` | `$csub/ExtendedInfo[Name='NEW_MAT_SERIAL']` |
| ns8:msisdn source | `$psub/MSISDN` | `$csub/MSISDN` |
| ns8:channel_code source | `$psub/ExtendedInfo[Name='PARTNER']` | `$csub/ExtendedInfo[Name='PARTNER']` |
| ns8:sr_type source | `$psub/ExtendedInfo[Name='SR_TYPE']` | `$csub/ExtendedInfo[Name='SR_TYPE']` |
| All other fields | Identical | Identical |

---

## §11 — Audit Logging

| Scope | OPERATION_NAME | AUDIT_TRACE | Note |
|-------|---------------|-------------|------|
| POU & COU Request | MCS_UPDATE_SUBSCRIPTION | "Request Sent for MCS_UPDATE_SUBSCRIPTION" | Correct — static trace |
| Response | MCS_UPDATE_SUBSCRIPTION | "Response received for MCS_UPDATE_SUBSCRIPTION" | Consistent with request |

> Audit logging is unconditional — no `AllowWriteLog` gate. Every dispatched event generates an audit log entry.

---

## §12 — Activity Status Management

| Condition | Status | Call |
|-----------|--------|------|
| At least one event dispatched | INPROGRESS | `GetActivityStatusString("1", false)` → `SendDataToDB()` |
| No Materials found across all scopes | SKIPPED | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception caught | ERROR | `HandleActivityException()` |

---

## §15 — Function Dependency Tree

```text
Request_MCS_UPDATE_SUBSCRIPTION.rule
├── Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")
├── [Scope A] POU[p] → Subscriber[ps] → (MaterialInfo!=null) → Material[pmat]
│   ├── pMatRefId = pSubRefId + ":" + material.MatCode
│   ├── [Resubmit guard] Response[].ReferenceId==pMatRefId && CompletionStatus==2
│   ├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(material.MatCode)
│   ├── RuleFunctions.Helpers.GetXMLForSubscriberMaterialInfo(orderRequest, pSubRefId, MatCode|MatSerial)
│   ├── XPath.execute("/(" + chkXPath + ")", sXML, ...)
│   ├── Event.createEvent("xslt://MCS_UPDATE_SUBSCRIPTION")    [POU Subscriber XSLT]
│   ├── Event.Ext.sendEventImmediate() → MCS_UPDATE_SUBSCRIPTION
│   └── Event.Ext.sendEventImmediate() → Logger
├── [Scope B] POU[p] → ChildOU[c] → Subscriber[cs] → (MaterialInfo!=null) → Material[cmat]
│   ├── cMatRefId = cSubRefId + ":" + material.MatCode
│   ├── [Resubmit guard] Response[].ReferenceId==cMatRefId && CompletionStatus==2
│   ├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(material.MatCode)
│   ├── RuleFunctions.Helpers.GetXMLForSubscriberMaterialInChildOU(orderRequest, cSubRefId, pOuRefId, MatCode|MatSerial)
│   ├── XPath.execute("/(" + chkXPath + ")", sXML, ...)
│   ├── Event.createEvent("xslt://MCS_UPDATE_SUBSCRIPTION")    [COU Subscriber XSLT]
│   ├── Event.Ext.sendEventImmediate() → MCS_UPDATE_SUBSCRIPTION
│   └── Event.Ext.sendEventImmediate() → Logger
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB()
├── RuleFunctions.Helpers.SkipActivity()
└── RuleFunctions.Helpers.HandleActivityException()

Response_MCS_UPDATE_SUBSCRIPTION.rulefunction
├── OMXUtils.generateTrackingID()
├── Instance.createInstance("xslt://ResponseBase")
│   ├── ResponseCode        ← $eventResponse/ResponseCode
│   ├── ResponseMessage     ← $eventResponse/ResponseMsg
│   ├── CompletionStatus    ← $eventResponse/CompletionStatus
│   └── ReferenceId         ← $eventResponse/RefID              [correctly mapped]
├── currActivity.Response[Response@length] = activityRes
├── Event.Ext.sendEventImmediate() → Logger
├── XPath.evalAsInt(count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3)="000"]))
└── if(RequestCount == successResponseCount) → "true" else → "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Call MCS to update subscription for each POU Subscriber's Material — one event per Material |
| R2 | Call MCS to update subscription for each COU Subscriber's Material — one event per Material |
| R3 | Skip subscribers with no MaterialInfo record entirely |
| R4 | If MatCode is blank, use MatSerial as the PreExecCheck XML key |
| R5 | resubmit refId = SubRefId:MatCode — per-Material idempotency |
| R6 | Carry old IMEI (MatSerial → registered_imei) and new IMEI (NEW_MAT_SERIAL ExtendedInfo → imei) |
| R7 | sr_creation_date is always emitted — formatted from SubmissionDate with timezone offset |
| R8 | Fan-in: all-success (RequestCount == count of responses with ResponseCode suffix "000") |

### Design Risks

| Risk | Severity | Detail | Mitigation |
|------|----------|--------|-----------|
| Unused variables | [LOW] | `pOuId` (line 30), `cOuId` (line 91), `cOuRefId` (line 92) are loaded but never used | Remove dead assignments in migration |
| MatCode/MatSerial mismatch in resubmit key | [MEDIUM] | resubmit refId is always `SubRefId:MatCode`, but when MatCode is blank the PreExecCheck uses MatSerial. Resubmit guard may fail to detect prior attempt for blank-MatCode Materials. | Use consistent key for both resubmit guard and PreExecCheck |
| No author attribution | [LOW] | Empty @description block — no @author tag | Add author tag in migration |
| sr_creation_date always emitted | [LOW] | If SubmissionDate is null/empty, `tib:format-dateTime` may emit empty/invalid ISO string. MCS may reject. | Add xsl:if guard on SubmissionDate |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_MCS_UPDATE_SUBSCRIPTION {
    attribute { priority = 5; forwardChain = true; }
    declare { Concepts.OrderRequest.OrderRequest orderRequest; Concepts.OM.ProcessConfig.Activity orderCurrentActivity; }
    when { /* activityId + status WAITING guards */ }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Activity nextAct = Instance.getByExtIdByUri(...);
            String chkXPath = nextAct.PreExecCheck;
            boolean isSkipped = true;

            for (int p = 0; p < pOuLen; p++) {
                String pOuId = ...;    // [LOW: unused]
                String pOuRefId = ...;  // used in COU PreExecCheck helper only

                // ── Scope A: POU Subscriber → Material ──────────────────────────
                for (int ps = 0; ps < pSubLen; ps++) {
                    Subscriber psub = ...;
                    if (psub.MaterialInfo != null) {
                        for (int pmat = 0; pmat < pMatLen; pmat++) {
                            String pMatRefId = pSubRefId + ":" + material.MatCode;
                            // [Resubmit guard: Response[].ReferenceId==pMatRefId && CompletionStatus==2]
                            if(!reqSuccess) {
                                // [PreExecCheck: IsBlankOrStringNull(MatCode) → GetXMLForSubscriberMaterialInfo(MatCode|MatSerial)]
                                if(chkRes == "true") {
                                    // Event built with POU Subscriber XSLT (see §10)
                                    Event.Ext.sendEventImmediate(reqEvent);
                                    isSkipped = false;
                                    if(!isActResub) orderCurrentActivity.RequestCount++;
                                    Event.Ext.sendEventImmediate(/* Logger: OPERATION_NAME="MCS_UPDATE_SUBSCRIPTION" */);
                                }
                            }
                        }
                    }
                }

                // ── Scope B: COU Subscriber → Material ──────────────────────────
                for (int c = 0; c < cOuLen; c++) {
                    String cOuId = ...;    // [LOW: unused]
                    String cOuRefId = ...;  // [LOW: unused]
                    for (int cs = 0; cs < cSubLen; cs++) {
                        Subscriber csub = ...;
                        if (csub.MaterialInfo != null) {
                            for (int cmat = 0; cmat < cMatLen; cmat++) {
                                String cMatRefId = cSubRefId + ":" + material.MatCode;
                                // [Resubmit guard]
                                if(!reqSuccess) {
                                    // [PreExecCheck: GetXMLForSubscriberMaterialInChildOU(cSubRefId, pOuRefId, MatCode|MatSerial)]
                                    if(chkRes == "true") {
                                        // Event built with COU Subscriber XSLT (see §10)
                                        Event.Ext.sendEventImmediate(reqEvent);
                                        isSkipped = false;
                                        if(!isActResub) orderCurrentActivity.RequestCount++;
                                        Event.Ext.sendEventImmediate(/* Logger */);
                                    }
                                }
                            }
                        }
                    }
                }
            }

            if (!isSkipped) {
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                SendDataToDB(orderRequest);
            } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
        } catch (Exception ae) { HandleActivityException(...); }
    }
}
```

---

## §19 — Response Message Rule

### §19.1 — Overview

`Response_MCS_UPDATE_SUBSCRIPTION.rulefunction` — receives MCS subscription update confirmation, creates a `ResponseBase` concept, appends to Response[], sends audit log, then evaluates all-success fan-in.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order for audit log |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.MCS_UPDATE_SUBSCRIPTION` | Inbound MCS confirmation |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] array target |

### §19.3 — ResponseBase Concept Construction

```text
createObject
└── object @extId ← OMXUtils:generateTrackingID()    [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode    [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg     [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId         ← $eventResponse/RefID           [Conditional] [Correctly mapped]
```

### §19.4 — Fan-in Completion Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

```java
if(currActivity.RequestCount == successResponseCount)
    return "true";   // all dispatched Material updates succeeded
else
    return "false";  // waiting for more success responses
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
