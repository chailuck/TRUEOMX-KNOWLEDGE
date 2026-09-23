# Request_CCBS_GET_AGREEMENT_HEADER

> Agreement Header retrieval with dual POU+COU IntraActivitySequencing fan-out; enriches OUId and AgreementType for each organizational unit

**Author:** Sakrapee-SCM-PC | **Priority:** 5 | **forwardChain:** true | **Target:** CCBS GetAgreementHeader | **Generated:** 2026-08-04

---

## §1 Overview & Purpose

**CCBS_GET_AGREEMENT_HEADER** retrieves Agreement Header details from CCBS for each organizational unit — both Parent OUs (POU) and Child OUs (COU) — and enriches them with `OUId` (from `ChNodeId`) and `AgreementType` (from `AgreementTypeInfo/AgreementType`).

This FM is structurally unique: it does **not** loop over `Customer.Account[]` like CCBS_GET_ACCOUNT_HEADER and CCBS_GET_BA_HEADER. Instead it uses a **nested dual loop** — outer loop over `ParentOU[]`, inner loop over each POU's `ChildOU[]`. All requests from both loops are queued into one IntraActivitySequencing channel and fired sequentially.

> **Migration risk:** The AgreementNo payload field applies `number($agreementId)` — an XSLT numeric cast. If AgreementId contains non-numeric characters or is null/empty, XSLT returns NaN which maps to a zero or empty element. The receiving CCBS API may reject or silently mishandle this.

> **Notable differences from other CCBS FMs:** JMSPriority/JMSCorrelationID/OrderID headers are always emitted (no xsl:if guards). AUDIT_TRACE includes the RefId in the message. OPERATION_NAME is hardcoded as a literal string. extId for the response concept uses sysNanoTime (not OMXUtils:generateTrackingID()).

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_AGREEMENT_HEADER` |
| Author | Sakrapee-SCM-PC |
| Priority | 5 |
| Forward chain | true |
| Backend system | CCBS — GetAgreementHeader |
| Request schema NS | `www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.AgreementIdInfo` |
| Response concept | `Concepts.FM.Response.CCBS_GetAgreementHeaderRes` |
| Fan-out pattern | IntraActivitySequencing — POU outer loop + COU inner loop (nested) |
| Completion criterion | `IntraActivitySequencing.ActionResponseEvent(currActivity)` → true/false |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | ParentOU[] and each POU's ChildOU[] iterated; Agreement.AgreementId and RefId read; OUId and AgreementType written by response |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Holds PreExecCheck, RequestCount, Response[]; IntraActivitySequencing state |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_GET_AGREEMENT_HEADER"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_AGREEMENT_HEADER"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Resubmit flag: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Fetch `nextAct` via `Instance.getByExtIdByUri(NextActivityName, Activity)`
3. Read `altParam` via `GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")`
4. If resubmit: `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
5. **Outer loop over ParentOU[i]** (i = 0..iPOULen-1)
   - a. Resubmit skip: Response[iResp].ReferenceId==parentRefId && CompletionStatus==2 → skip POU
   - b. Per-POU PreExecCheck: `GetXMLForOU(orderRequest, refId)` → XPath evaluate
   - c. If chkRes="true": read `agreementId = ParentOU[i].Agreement.AgreementId`
   - d. Build and assertEvent POU request; queue via `ActionRequestEvent`; isSkipped = false
   - e. **Inner loop over ChildOU[j]** (j = 0..iCOULen-1) — always runs for each POU
     - i. Resubmit skip: Response[iResp].ReferenceId==COU refId && CompletionStatus==2 → skip COU
     - ii. Per-COU PreExecCheck: `GetXMLForChildOU(orderRequest, refId, parentRefId)` → XPath evaluate
     - iii. If chkRes="true": read `agreementId = ParentOU[i].ChildOU[j].Agreement.AgreementId`
     - iv. Build and assertEvent COU request; queue via `ActionRequestEvent`; isSkipped = false
6. After all loops: if `!isSkipped` → `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)`
7. If `!isSkipped`: `GetActivityStatusString("1", false)` + `SendDataToDB(orderRequest)`
8. Else: `SkipActivity(orderRequest, orderCurrentActivity, "4")`
9. Exception: `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

> **Queue ordering:** For POU[0] the sequence is: POU[0] request → COU[0][0] → COU[0][1] → ... → POU[1] → COU[1][0] → ... — all assertEvent'd and enqueued before SendFirstRequestEvent fires. Responses arrive in any order but the fan-in waits for all.

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Protocol | Note |
|-----------|-----------|----------|------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_GET_AGREEMENT_HEADER` | JMS (assertEvent + IntraActivitySequencing) | Same XSLT variant for both POU and COU requests |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_GET_AGREEMENT_HEADER` | JMS | RefID used to match response to POU or COU |

### §8.3 Backend API Details

| Property | Value |
|----------|-------|
| System | CCBS |
| Operation | GetAgreementHeader |
| Request element | `ns:AgreementIdInfo / ns:AgreementNo` |
| Key input | `number($agreementId)` — numeric cast of POU or COU Agreement.AgreementId |
| ALT_CES routing | altParam="Y" + OrderData/ExtendedInfo[ALT_CES]/Value != "" → override CES; else OrderData/CES |
| Credential gate | `IsEnableUserPass='true'` → UserName/PassWord |

### §8.4 Fields Read / Written

**Read (per OU):** `ParentOU[i].RefId`, `ParentOU[i].Agreement.AgreementId`, `ParentOU[i].ChildOU[j].RefId`, `ParentOU[i].ChildOU[j].Agreement.AgreementId`

**Written (response, per OU):** `ParentOU[i].OUId` ← AgreementHeader/UnitIdInfo/ChNodeId · `ParentOU[i].Agreement.AgreementType` ← AgreementHeader/AgreementTypeInfo/AgreementType (same fields for matching COU)

### §8.5 PreExecCheck Serialisation Variants

| Entity | Serialisation Function | Parameters |
|--------|----------------------|------------|
| ParentOU | `GetXMLForOU(orderRequest, refId)` | OU RefId only |
| ChildOU | `GetXMLForChildOU(orderRequest, refId, parentRefId)` | COU RefId + parent POU RefId |

### §8.6 Global Variable Dependencies

`OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass`, `OMX_COMMON/_SharedResources/Common/ClearField`, `OMX_COMMON/Component_Name/OMX_CEP`, `OMX_COMMON/Component_Name/OMX_FM`, `MSG_LOG_LEVEL/INFO`, `OMX_OM/WritePayload`

---

## §9 Payload Build

```xml
<payload>
  <ns:AgreementIdInfo>
    <!-- ns = www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.AgreementIdInfo -->
    <ns:AgreementNo>number($agreementId)</ns:AgreementNo>
    <!-- $agreementId = ParentOU[i].Agreement.AgreementId  (POU variant) -->
    <!-- $agreementId = ParentOU[i].ChildOU[j].Agreement.AgreementId  (COU variant) -->
    <!-- ⚠ XSLT number() cast — non-numeric AgreementId → NaN/empty -->
  </ns:AgreementIdInfo>
</payload>
```

**JMS headers:** JMSPriority (always), JMSCorrelationID (always), OrderID (always), RefID ← parentRefId/COU refId (always), UserName/PassWord (credential-gated), OrderType (conditional), CES (ALT_CES routing)

> **Note:** JMSPriority/JMSCorrelationID/OrderID are always emitted with no `xsl:if` guard — unlike all other CCBS FMs. If OrderPriority or OrderID is null, these headers will emit empty values.

---

## §10 XSLT Field Mapping Tree (identical for POU and COU variants)

```text
event
├── JMSPriority              ← $orderRequest/OrderPriority                               [Always — no xsl:if]
├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId                     [Always — no xsl:if]
├── OrderID                  ← $orderRequest/OrderData/OrderID                           [Always — no xsl:if]
├── RefID                    ← $refId (ParentOU[i].RefId or COU RefId)                  [Always]
├── UserName                 ← $orderRequest/OrderData/User                              [Credential-gated: IsEnableUserPass='true']
├── PassWord                 ← $orderRequest/OrderData/Password                          [Credential-gated: IsEnableUserPass='true']
├── OrderType                ← $orderRequest/OrderData/OrderType                         [Conditional]
├── CES                      ← ExtendedInfo[ALT_CES]/Value  (if altParam=Y && not-blank) [xsl:choose / Conditional]
│                               else $orderRequest/OrderData/CES
└── payload
    └── ns:AgreementIdInfo
        └── ns:AgreementNo   ← number($agreementId)                                      [Always]
                                ⚠ number() cast — NaN if non-numeric AgreementId
```

**Legend:** `[Always]` = always emitted · `[Conditional]` = inside xsl:if · `[Credential-gated]` = gated on IsEnableUserPass global

---

## §11 Audit Logging

**Request audit** — inside each `if(chkRes="true")` block (POU and COU separately):

| Field | Value | Note |
|-------|-------|------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` | |
| PROCESS_ID | `concat(nanoTime(), "_REQ")` | |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | |
| OPERATION_NAME | `"CCBS_GET_AGREEMENT_HEADER"` | [Hardcoded literal — not dynamic from activityId] |
| AUDIT_TRACE | `concat("Request Sent for RefId ", $refId)` | [Unique — includes RefId per OU entity] |

**Response audit:** uses dynamic `$currActivity/ActivityID` and `_RES` suffix (standard pattern)

---

## §15 Function Dependency Tree

```text
Request_CCBS_GET_AGREEMENT_HEADER (rule)
├── Instance.getByExtIdByUri(NextActivityName, Activity)   [nextAct]
├── GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")
├── [if isActResub]: IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── [outer: for i=0..iPOULen-1]:   <- ParentOU loop
│   ├── Resubmit skip: Response[iResp].ReferenceId==parentRefId && CompletionStatus==2
│   ├── GetXMLForOU(orderRequest, parentRefId)   [OU-scoped XML context]
│   ├── XPath.execute(PreExecCheck, sXML, ...)
│   ├── [if chkRes="true"]:
│   │   ├── agreementId = ParentOU[i].Agreement.AgreementId
│   │   ├── Event.createEvent(CCBS_GET_AGREEMENT_HEADER XSLT — POU variant)
│   │   │   └── AgreementIdInfo/AgreementNo <- number(agreementId)
│   │   ├── Event.assertEvent(reqEvent)   <- queued
│   │   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   │   ├── Event.Ext.sendEventImmediate(Logger)
│   │   └── isSkipped = false
│   └── [inner: for j=0..iCOULen-1]:   <- ChildOU loop (always runs for each POU)
│       ├── Resubmit skip: Response[iResp].ReferenceId==COU refId && CompletionStatus==2
│       ├── GetXMLForChildOU(orderRequest, refId, parentRefId)   [COU with parent context]
│       ├── XPath.execute(PreExecCheck, sXML, ...)
│       └── [if chkRes="true"]:
│           ├── agreementId = ParentOU[i].ChildOU[j].Agreement.AgreementId
│           ├── Event.createEvent(CCBS_GET_AGREEMENT_HEADER XSLT — COU variant, same XSLT)
│           ├── Event.assertEvent(reqEvent)   <- queued
│           ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│           ├── Event.Ext.sendEventImmediate(Logger)
│           └── isSkipped = false
├── [if !isSkipped]:
│   ├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
│   ├── GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [if isSkipped]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")

Response_CCBS_GET_AGREEMENT_HEADER (rulefunction, 59 lines)
├── [outer: for i=0..iPOULen-1]:
│   ├── [if ParentOU[i].RefId == eventResponse.RefID]:
│   │   ├── ParentOU[i].OUId <- AgreementHeader/UnitIdInfo/ChNodeId (XPath.evalAsString)
│   │   ├── ParentOU[i].Agreement.AgreementType <- AgreementHeader/AgreementTypeInfo/AgreementType
│   │   └── isBreak = true
│   ├── [else]: inner loop over ChildOU[j]:
│   │   └── [if ChildOU[j].RefId == eventResponse.RefID]:
│   │       ├── ChildOU[j].OUId <- AgreementHeader/UnitIdInfo/ChNodeId
│   │       ├── ChildOU[j].Agreement.AgreementType <- AgreementHeader/AgreementTypeInfo/AgreementType
│   │       ├── isBreak = true; break   <- exits COU inner loop
│   └── [if isBreak]: break   <- exits POU outer loop
├── Instance.createInstance(CCBS_GetAgreementHeaderRes XSLT)
│   extId=sysNanoTimeValue, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId
├── currActivity.Response[len] = activityRes
├── Event.Ext.sendEventImmediate(Logger)
└── IntraActivitySequencing.ActionResponseEvent(currActivity) -> "true"/"false"
```

---

## §17 Migration Notes, Risks & Recommendations

### Unique Design Characteristics

| Characteristic | Detail | Other FMs |
|----------------|--------|-----------|
| Fan-out scope | ParentOU[] + each POU's ChildOU[] — nested two-level structure | All other CCBS FMs fan-out over Account[] |
| PreExecCheck serialisers | Two different helpers: GetXMLForOU (POU) and GetXMLForChildOU (COU, needs parentRefId) | Others use GetXMLForAccount or Instance.serializeUsingDefaults |
| JMS header guards | JMSPriority/JMSCorrelationID/OrderID always emitted (no xsl:if) | All other CCBS FMs use conditional guards |
| AUDIT_TRACE content | Includes RefId: `"Request Sent for RefId " + refId` | Others use `"Request Sent for " + activityId` |
| OPERATION_NAME in audit | Hardcoded literal `"CCBS_GET_AGREEMENT_HEADER"` | Others use dynamic `$orderCurrentActivity/ActivityID` |
| Response concept extId | sysNanoTimeValue (long) | Others use OMXUtils:generateTrackingID() |
| Response break pattern | Uses isBreak + nested break to exit POU loop on first match | Others iterate all accounts |

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Dual-level fan-out: request for every POU AND every COU under each POU; queued via IntraActivitySequencing |
| R2 | Per-entity PreExecCheck using OU-appropriate serialisation (GetXMLForOU / GetXMLForChildOU) |
| R3 | AgreementNo = numeric cast of AgreementId (`number()`) in XSLT |
| R4 | ALT_CES routing via activity parameter + OrderData/ExtendedInfo |
| R5 | Credential gate via IsEnableUserPass global variable |
| R6 | Response: match RefID to POU or COU; write OUId ← ChNodeId and AgreementType; break on first match |
| R7 | Both POU and COU responses must complete for fan-in to return "true" |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `number($agreementId)` cast — non-numeric or null AgreementId produces NaN/empty AgreementNo | [HIGH] | Add null/format guard before XSLT; confirm CCBS API can receive empty AgreementNo; document valid format |
| IntraActivitySequencing — TIBCO-proprietary pattern | [HIGH] | Replace with explicit parallel fan-out over all OU entities; or sequential async loop |
| JMSPriority/JMSCorrelationID/OrderID always emitted without xsl:if — empty headers if source fields are null | [MEDIUM] | Add conditional guards for parity with other CCBS FMs; verify CCBS accepts empty JMS headers |
| COU inner loop always runs for each POU, even if POU was resubmit-skipped | [MEDIUM] | Verify intended behaviour: should COU loop also be skipped when POU is skipped? |
| Response isBreak pattern — fragile if two entities share a RefId | [MEDIUM] | Verify RefId uniqueness across POU and COU; consider explicit match-all in migration |
| OPERATION_NAME hardcoded in audit log | [LOW] | Use dynamic `$orderCurrentActivity/ActivityID` in migration for consistency |

---

## §18 Full Source Code

```java
/**
 * Request_CCBS_GET_AGREEMENT_HEADER
 * Author: Sakrapee-SCM-PC | Priority: 5 | forwardChain: true
 * Pattern: IntraActivitySequencing — POU outer loop + COU inner loop
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_AGREEMENT_HEADER {
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Activity nextAct = Instance.getByExtIdByUri(NextActivityName, ...);
      if(isActResub)
        IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

      String altParam = GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES");
      boolean isSkipped = true;
      int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;

      for (int i=0; i < iPOULen; i++) {    // ParentOU outer loop
        String parentRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;
        boolean reqSuccess = false;
        // resubmit skip check...
        if(!reqSuccess) {
          String chkRes = "true";
          if(String.length(nextAct.PreExecCheck) > 0) {
            String sXML = GetXMLForOU(orderRequest, parentRefId);
            chkRes = XPath.execute(...);
          }
          if(String.equals(chkRes, "true")) {
            String agreementId = orderRequest.OrderData.Customer.ParentOU[i].Agreement.AgreementId;
            /* XSLT (see §9): AgreementIdInfo/AgreementNo <- number(agreementId)
               Headers: JMSPriority(always), JMSCorrelationID(always), OrderID(always), RefID(always),
                        UserName(?), PassWord(?), OrderType(?), CES(ALT_CES routing) */
            Event.assertEvent(reqEvent);
            IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
            Event.Ext.sendEventImmediate(Logger);
            isSkipped = false;
          }
        }

        int iCOULen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU@length;
        for (int j=0; j < iCOULen; j++) {    // ChildOU inner loop
          String refId = orderRequest.OrderData.Customer.ParentOU[i].ChildOU[j].RefId;
          reqSuccess = false;
          // resubmit skip check...
          if(!reqSuccess) {
            String chkRes = "true";
            if(String.length(nextAct.PreExecCheck) > 0) {
              String sXML = GetXMLForChildOU(orderRequest, refId, parentRefId);
              chkRes = XPath.execute(...);
            }
            if(String.equals(chkRes, "true")) {
              String agreementId = orderRequest.OrderData.Customer.ParentOU[i].ChildOU[j].Agreement.AgreementId;
              /* Same XSLT as POU variant */
              Event.assertEvent(reqEvent);
              IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
              Event.Ext.sendEventImmediate(Logger);
              isSkipped = false;
            }
          }
        }
      }

      if(!isSkipped) {
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else
        SkipActivity(orderRequest, orderCurrentActivity, "4");
    } catch(Exception ae) {
      HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

59-line response handler. Matches `eventResponse.RefID` against POU RefIds first; on miss, searches each POU's COU list. Writes `OUId` and `AgreementType` to the matched OU entity. Uses `isBreak` + nested `break` pattern to exit on first match. Appends a simple 4-field `CCBS_GetAgreementHeaderRes` concept, then calls IntraActivitySequencing fan-in.

> **Unique logging:** Uses `Log.getLogger()` + `Log.log()` for debug logging — not found in any other CCBS FM response handler.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Source of ParentOU/ChildOU to match and write |
| `eventResponse` | Response event | Carries RefID, AgreementHeader XML |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | IntraActivitySequencing fan-in target |

### §19.3 Field Enrichment (per matched OU)

```text
Per-OU enrichment (POU or COU)
├── OUId              <- AgreementHeader/UnitIdInfo/ChNodeId          [Always on match]
└── Agreement.AgreementType <- AgreementHeader/AgreementTypeInfo/AgreementType [Always on match]
```

### §19.3b Response Concept (CCBS_GetAgreementHeaderRes)

```text
CCBS_GetAgreementHeaderRes
├── extId             <- sysNanoTimeValue  (System.nanoTime())        [Always — NOT OMXUtils:generateTrackingID()]
├── ResponseCode      <- eventResponse/ResponseCode                   [Always — no xsl:if]
├── ResponseMessage   <- eventResponse/ResponseMessage                [Always — no xsl:if]
├── CompletionStatus  <- eventResponse/CompletionStatus               [Always — no xsl:if]
└── ReferenceId       <- eventResponse/ReferenceId                    [Always — no xsl:if]
```

### §19.4 Fan-in Completion

`IntraActivitySequencing.ActionResponseEvent(currActivity)` → `"true"` when all POU + COU requests have responded; `"false"` while more are pending.

All response fields always emitted (no xsl:if guards — different from most other CCBS response concepts).

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
