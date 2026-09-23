# Request_CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO

> Updates CCBS subscriber general info (convergence code, IMSI alias, L9 fields, SMSInd, ActivityReason etc.) per subscriber using IntraActivitySequencing for ordered/queued dispatch. Two POU/COU divergence bugs documented.

**Backend:** CCBS (ChangeSubscriberGeneralInfo) | **Pattern:** Per-subscriber / IntraActivitySequencing | **RefID:** bare subRefId | **forwardChain:** true | **Author:** mranade-T420 | **Used in step:** 74

---

## §1 — Overview & Purpose

Updates the CCBS subscriber record with L9 convergence and general profile fields. Unlike most FMs which use `Event.Ext.sendEventImmediate`, this FM uses the **IntraActivitySequencing** dispatch pattern: events are first *asserted* via `Event.assertEvent`, registered via `ActionRequestEvent`, and only dispatched after all are queued via `SendFirstRequestEvent`. Completion is determined by `ActionResponseEvent` rather than the standard RequestCount/successResponseCount comparison.

- **Fan-out:** per POU subscriber + per COU subscriber (standard nested index loops `iPOUItr`/`iSubItr`)
- **RefID:** bare `refId` (always emitted)
- **Dispatch:** IntraActivitySequencing — `assertEvent` → `ActionRequestEvent` → `SendFirstRequestEvent`
- **OLD_BAN_DATE:** two-step parse from string ExtendedInfo → DateTime, passed to XSLT as typed parameter
- **LogicalDate:** read from BE working memory concept (but value unused in XSLT)
- **Response concept:** dedicated `CCBS_ChangeSubscriberGeneralInfoRes` (not generic ResponseBase)
- **Fan-in:** `IntraActivitySequencing.ActionResponseEvent` (not RequestCount==successResponseCount)

> **[HIGH] COU L9RelatedSubscriber bug (wrong condition + wrong value):** POU correctly reads `ExtendedInfo[RELATED_SUBSCRIBER]/Value`. COU XSLT checks `INSTALLATION_TYPE` as condition guard and emits hardcoded `0` as value. Any COU subscriber with an INSTALLATION_TYPE will send `L9RelatedSubscriber=0` to CCBS regardless of the actual RELATED_SUBSCRIBER value. Fix: COU should check `RELATED_SUBSCRIBER!=""` and emit that value.

> **[MEDIUM] COU ActivityReason missing CAN→SHOT translation:** POU XSLT: `if ActivityReason=='CAN' → 'SHOT'; else ActivityReason or 'CREQ'`. COU XSLT: only `ActivityReason or 'CREQ'` — no CAN→SHOT branch. COU subscribers with ActivityReason='CAN' send 'CAN' to CCBS instead of the required 'SHOT'.

> **[LOW] logicalDateVal read but never used:** `logicalDateRes.LogicalDate` is extracted into `logicalDateVal` but never passed to the XSLT or used anywhere. Dead assignment.

> **[LOW] Request logger uses ERROR log level:** `MSG_LOG_LEVEL/ERROR` instead of the typical `MSG_LOG_LEVEL/INFO` — likely a development artifact.

> **[INFO] POU vs COU OLD_BAN_DATE parse method differs:** POU uses `XPath.evalAsDateTime($OLD_BAN_DATE_PARAM)`; COU uses `DateTime.parseString(L9RFActStr, "yyyy-MM-dd'T'HH:mm:ssZ")`. Same net result but different APIs.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO.rule` | 129 lines |
| Author | mranade-T420 | Older style: index loops, debugOut, IntraActivitySequencing |
| Priority | 5 | |
| forwardChain | true | |
| Backend event | `Events.OMConsumers.OMXFM.Request.CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO` | Dedicated |
| Schema (ns3) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/ESB/ChangeSubscriberGeneralInfo.xsd` | |
| ns1 | `www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.SubscriberGeneralInfo` | |
| ns2 | `www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.ActivityInfo` | |
| ns4 | `www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.SubscriberIdInfo` | |
| Fan-out pattern | Per-subscriber (POU + COU), integer index iterators | Not variable-binding style |
| RefID | bare `refId` (always) | Emitted unconditionally |
| Resub guard | `Response[ReferenceId==refId && CompletionStatus==2]` | |
| PurgePendingRequestsBeforeResubmit | PRESENT ✓ | Called on resubmit |
| LogicalDate | `Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")` | Read but unused [LOW] |
| OLD_BAN_DATE parse (POU) | `XPath.evalAsDateTime($OLD_BAN_DATE_PARAM)` | Two-step: evalAsString first |
| OLD_BAN_DATE parse (COU) | `DateTime.parseString(str, "yyyy-MM-dd'T'HH:mm:ssZ")` | Different API |
| Dispatch method | `Event.assertEvent + IntraActivitySequencing.ActionRequestEvent` | NOT sendEventImmediate |
| Send trigger | `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)` | After all events queued |
| Response concept | `Concepts.FM.Response.CCBS_ChangeSubscriberGeneralInfoRes` | Dedicated — not generic ResponseBase |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` | NOT RequestCount==successResponseCount |
| Request LOG_LEVEL | ERROR | [LOW] Should be INFO |
| OPERATION_NAME (request) | `$orderCurrentActivity/ActivityID` (dynamic) | Not hardcoded |
| OPERATION_NAME (response) | `"CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO"` | Hardcoded |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §7 — POU vs COU XSLT Differences

| Field | POU XSLT | COU XSLT | Finding |
|-------|----------|----------|---------|
| L9RelatedSubscriber | `if RELATED_SUBSCRIBER!='' → emit RELATED_SUBSCRIBER value` | `if INSTALLATION_TYPE!='' → emit literal 0` | **[HIGH]** Wrong condition and wrong value in COU |
| ns2:ActivityReason | `if=='CAN'→'SHOT'; else ActivityReason or 'CREQ'` | `ActivityReason or 'CREQ'` (no CAN→SHOT) | **[MEDIUM]** COU misses CAN→SHOT translation |
| OLD_BAN_DATE parse | `XPath.evalAsDateTime($OLD_BAN_DATE_PARAM)` | `DateTime.parseString(str, "yyyy-MM-dd'T'HH:mm:ssZ")` | **[INFO]** Different API, same result |
| L9ConvergenceCode guard | `!=''` | `string-length() > 0` | **[INFO]** Equivalent |
| L9ProofDate guard | `string-length() > 0` | `exists()` | **[INFO]** Different guard style, same effect |

---

## §8 — ExtendedInfo Fields Referenced

| Name | Level | Direction | XSLT Target |
|------|-------|-----------|------------|
| INSTALLATION_TYPE | Subscriber | INPUT | `ns1:L9InstallationType` |
| MARKET_CODE | Subscriber | INPUT | `ns1:L9MarketingCode` |
| PHASE_CODE | Subscriber | INPUT | `ns1:L9PhaseCode` |
| PROJECT_CODE | Subscriber | INPUT | `ns1:L9ProjectCode` |
| OLD_BAN_DATE | Subscriber | INPUT | `ns1:L9RFActDate` — parsed to DateTime |
| OLD_BAN | Subscriber | INPUT | `ns1:L9RFBan` |
| RELATED_SUBSCRIBER | Subscriber | INPUT | `ns1:L9RelatedSubscriber` (POU only — COU has bug) |
| SALE_CHANNEL | Subscriber | INPUT | `ns1:L9SaleChannel` |
| TRUELIFE_ID | Subscriber | INPUT | `ns1:L9TrueLifeId` |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

POU indexed: `$orderRequest/.../ParentOU[$iOUItr]/Subscriber[$iSub]/`. COU adds `ChildOU[$iCOUItr]`. Divergences noted inline.

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority                [Conditional: xsl:if]
    ├── JMSCorrelationID         ← $orderRequest/OrderData/OMXTrackingId      [Conditional]
    ├── OrderID                  ← $orderRequest/OrderData/OrderID             [Conditional]
    ├── RefID                    ← $refId (bare subRefId)                      [Always]
    ├── UserName                 ← $orderRequest/OrderData/User                [Conditional]
    ├── PassWord                 ← $orderRequest/OrderData/Password            [Conditional]
    ├── OrderType                ← $orderRequest/OrderData/OrderType           [Conditional]
    ├── CES                      ← $orderRequest/OrderData/CES                 [Conditional]
    └── payload
        └── ns3:ChangeSubscriberGeneralInfo
            ├── ns4:SubscriberIdInfo
            │   └── ns4:SubscrNumber    ← sub.SubscriberId                    [Always]
            ├── ns1:SubscriberGeneralInfo
            │   ├── ns1:EffectiveDate       ← sub.SubscriberGeneralInfo.EffectiveDate        [Conditional: exists()]
            │   ├── ns1:L9ConvergenceCode   ← sub.SubscriberGeneralInfo.ConvergenceCode      [Conditional: !=""]
            │   ├── ns1:L9IMSIAlias         ← sub.SubscriberGeneralInfo.IMSIAlias            [Conditional: string-length>0]
            │   ├── ns1:L9InstallationType  ← sub.ExtendedInfo[INSTALLATION_TYPE].Value      [Conditional: !=""]
            │   ├── ns1:L9MarketingCode     ← sub.ExtendedInfo[MARKET_CODE].Value            [Conditional: !=""]
            │   ├── ns1:L9PhaseCode         ← sub.ExtendedInfo[PHASE_CODE].Value             [Conditional: !=""]
            │   ├── ns1:L9ProjectCode       ← sub.ExtendedInfo[PROJECT_CODE].Value           [Conditional: !=""]
            │   ├── ns1:L9ProofDate         ← sub.SubscriberGeneralInfo.ProofDate            [Conditional: string-length>0]
            │   ├── ns1:L9ProofDoc          ← sub.SubscriberGeneralInfo.ProofDoc             [Conditional: string-length>0]
            │   ├── ns1:L9RFActDate         ← $L9RFActDateFormat (parsed from OLD_BAN_DATE)  [Conditional: exists(OLD_BAN_DATE)]
            │   ├── ns1:L9RFBan             ← sub.ExtendedInfo[OLD_BAN].Value                [Conditional: !=""]
            │   ├── ns1:L9RelatedSubscriber
            │   │   ├── POU [CORRECT]       ← sub.ExtendedInfo[RELATED_SUBSCRIBER].Value     [Conditional: RELATED_SUBSCRIBER!=""]
            │   │   └── COU [HIGH BUG]      ← hardcoded 0                                    [Conditional: INSTALLATION_TYPE!="" (WRONG)]
            │   ├── ns1:L9SaleChannel       ← sub.ExtendedInfo[SALE_CHANNEL].Value           [Conditional: !=""]
            │   ├── ns1:L9SaleId            ← sub.SubscriberGeneralInfo.saleId               [Conditional: !=""]
            │   ├── ns1:L9SmsInd            ← 89 (Y) or 78 (N)                              [Conditional: exists(SMSInd)]
            │   ├── ns1:L9SmsLanguage       ← sub.SubscriberGeneralInfo.smsLang              [Conditional: !=""]
            │   ├── ns1:L9SplitPeriod       ← sub.SubscriberGeneralInfo.SplitPeriod          [Conditional: string-length>0]
            │   ├── ns1:L9TMVSrvsLvl        ← sub.SubscriberGeneralInfo.l9TmvServiceLevel    [Conditional: string-length>0]
            │   ├── ns1:L9TrueLifeId        ← sub.ExtendedInfo[TRUELIFE_ID].Value            [Conditional: count>0]
            │   └── ns1:Language            ← sub.SubscriberGeneralInfo.Language             [Conditional: string-length>0]
            └── ns2:ActivityInfo
                └── ns2:ActivityReason
                    ├── POU: if=='CAN'→'SHOT'; else ActivityReason or 'CREQ'
                    └── COU [MEDIUM BUG]: ActivityReason or 'CREQ'  (no CAN→SHOT)
```

---

## §15 — Function Dependency Tree

```text
Request_CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── if isActResub: PurgePendingRequestsBeforeResubmit(orderCurrentActivity)  ✓
├── logicalDateRes = Instance.getByExtIdByUri("LogicalDate", LogicalDate concept)
│   └── logicalDateVal = logicalDateRes.LogicalDate   ← UNUSED [LOW]
├── [POU loop iPOUItr → iSubItr]:
│   ├── refId = POU[iPOUItr].Subscriber[iSubItr].RefId
│   ├── [Resub guard]: Response[ReferenceId==refId && CompletionStatus==2]
│   ├── [PreExecCheck]: GetXMLForSubscriber(orderRequest, refId)
│   ├── [if chkRes=="true"]:
│   │   ├── OLD_BAN_DATE_PARAM = XPath.evalAsString(sub.ExtendedInfo[OLD_BAN_DATE])
│   │   ├── [if not blank]: L9RFActDateFormat = XPath.evalAsDateTime($OLD_BAN_DATE_PARAM)
│   │   ├── reqEvent = Event.createEvent(CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO, XSLT_POU)
│   │   ├── Event.assertEvent(reqEvent)
│   │   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   │   └── Logger (ERROR level): OPERATION_NAME=$orderCurrentActivity/ActivityID
├── [COU loop iPOUItr → iCOUItr → iSubItr]:
│   ├── L9RFActStr = XPath.evalAsString(ChildOU sub.ExtendedInfo[OLD_BAN_DATE])
│   ├── [if not null/empty]: L9RFActDateFormat = DateTime.parseString(L9RFActStr, "yyyy-MM-dd'T'HH:mm:ssZ")
│   ├── reqEvent = Event.createEvent(CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO, XSLT_COU)
│   ├── Event.assertEvent(reqEvent)
│   └── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
├── [if !isSkipped]:
│   ├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
│   ├── orderCurrentActivity.Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch]: HandleActivityException

Response_CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO (rulefunction)
├── activityRes = Instance.createInstance(CCBS_ChangeSubscriberGeneralInfoRes)
│   ← extId from $eventResponse/@extId (NOT pre-generated)
│   ← ResponseCode, ResponseMessage, CompletionStatus, ReferenceId (conditional)
├── currActivity.Response[] ← activityRes
├── Logger: OPERATION_NAME="CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO"
├── [NOTE] Standard RequestCount==successResponseCount block is COMMENTED OUT
└── return IntraActivitySequencing.ActionResponseEvent(currActivity) ? "true" : "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-subscriber fan-out (POU + COU). Standard nested index loops. |
| R2 | PurgePendingRequestsBeforeResubmit called on resubmit. |
| R3 | OLD_BAN_DATE from sub.ExtendedInfo parsed to DateTime and emitted as ns1:L9RFActDate. |
| R4 | SMSInd 'Y' → 89, else → 78 (CCBS integer encoding). |
| R5 | ActivityReason 'CAN' → 'SHOT' for POU. This translation MUST be applied to COU as well (currently missing). |
| R6 | ns1:L9RelatedSubscriber = sub.ExtendedInfo[RELATED_SUBSCRIBER].Value. COU bug must be fixed (currently emits 0 when INSTALLATION_TYPE present). |
| R7 | IntraActivitySequencing dispatch: assertEvent → ActionRequestEvent → SendFirstRequestEvent; fan-in via ActionResponseEvent. |
| R8 | Response uses dedicated CCBS_ChangeSubscriberGeneralInfoRes concept (not generic ResponseBase). |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| COU sends L9RelatedSubscriber=0 when INSTALLATION_TYPE present, ignoring actual RELATED_SUBSCRIBER value | [HIGH] | Fix COU XSLT: check RELATED_SUBSCRIBER value and emit it (mirror POU logic) |
| COU missing ActivityReason CAN→SHOT translation | [MEDIUM] | Add CAN→SHOT branch to COU XSLT ActivityInfo/ActivityReason xsl:choose |
| logicalDateVal read from LogicalDate concept but never used | [LOW] | Remove dead assignment or confirm intended future use |
| Request logger LOG_LEVEL=ERROR instead of INFO | [LOW] | Change to MSG_LOG_LEVEL/INFO for consistency |
| OLD_BAN_DATE parse method differs between POU and COU | [INFO] | Standardize on one approach in modernized implementation |

---

## §19 — Response Message Rule (Response_CCBS_CHANGE_SUBSCRIBER_GENERAL_INFO)

### §19.3 CCBS_ChangeSubscriberGeneralInfoRes Construction

```text
createObject
└── object (Concepts.FM.Response.CCBS_ChangeSubscriberGeneralInfoRes — dedicated concept)
    ├── @extId           ← $eventResponse/@extId     [Conditional] From event, not pre-generated
    ├── ResponseCode     ← $eventResponse/ResponseCode [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg  [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId      ← $eventResponse/RefID        [Conditional]
```

### §19.4 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Standard fan-in | **COMMENTED OUT** — RequestCount==successResponseCount block disabled |
| Active fan-in | `RuleFunctions.Helpers.IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Write-back | None |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
