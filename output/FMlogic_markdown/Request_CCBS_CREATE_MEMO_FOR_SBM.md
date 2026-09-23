# Request_CCBS_CREATE_MEMO_FOR_SBM

> Creates a memo in CCBS per subscriber to record an SBM data pack service action. Fan-out is per subscriber (POU + COU). Memo text is composed from subscriber UserText, SOC name (ServiceType=86/FE_OR_CCBS filter), and Channel. memoTypeId from global variable. Uses standard sendEventImmediate dispatch.

**Backend:** CCBS (CreateMemo) | **Pattern:** Per-subscriber / sendEventImmediate | **RefID:** Subscriber RefId | **forwardChain:** true | **Author:** sakarin-radchapunya | **Used in step:** 76

---

## §1 — Overview & Purpose

Creates one **CCBS createMemo** per subscriber (POU and COU) to record the SBM data pack service action on the subscriber's account. The memo text is dynamically composed from the subscriber's UserText, the matched offer name (ServiceType=86 with FE_OR_CCBS indicator BRMS or FE), and the order Channel. The memoTypeId is sourced from a global variable (`SBM_BUY_DATA_PACK/CreateMemoTypeId`) rather than a hardcoded value.

- **Fan-out unit:** Subscriber (POU + COU) — one request per subscriber
- **RefID:** bare subscriber `RefId` — always emitted in XSLT
- **Backend event:** `Events.OMConsumers.OMXFM.Request.CCBS_CREATE_MEMO` (NOT CCBS_CREATE_MEMO_FOR_SBM)
- **entityId:** `SubscriberId` (MSISDN / subscriber number)
- **entityTypeId:** `"6"` — hardcoded subscriber entity type
- **memoText:** composed via XSLT concat of UserText + SOC name + Channel
- **$soc:** `SubscriberOffers[ServiceType="86" and ExtendedInfo[Name="FE_OR_CCBS" and (Value="BRMS" or Value="FE")]]/OfferName`
- **memoTypeId:** `$globalVariables/OMX_OM/BizRules/SBM_BUY_DATA_PACK/CreateMemoTypeId`
- **Dispatch:** `Event.Ext.sendEventImmediate` — standard immediate send
- **Response:** standard ResponseBase; fan-in via `IsAllResponseSuccess` helper

> **[MEDIUM] Event name mismatch:** Rule is `CCBS_CREATE_MEMO_FOR_SBM` but backend event is `CCBS_CREATE_MEMO` and OPERATION_NAME logs as `"CCBS_CREATE_MEMO"`. The "_FOR_SBM" suffix exists only in the rule name — not in the event type, logger, or response handler. Ensure monitoring uses the correct event name.

> **[MEDIUM] memoTypeId from global variable:** `$globalVariables/OMX_OM/BizRules/SBM_BUY_DATA_PACK/CreateMemoTypeId` — if this path is absent from the deployment configuration, memoTypeId will be empty and CCBS may reject the memo request. A commented-out alternative using `XPath.evalAsString` exists in the rule body.

> **[MEDIUM] $soc can be empty:** If no SubscriberOffer matches ServiceType=86 + FE_OR_CCBS=BRMS/FE for the subscriber, `$soc` resolves to empty string. The memoText will be sent with blank SOC — functional but misleading.

> **[LOW] Commented-out typeId XPath.evalAsString (lines 49, 87):** Two commented-out lines in both POU and COU branches — they would have fetched CreateMemoTypeId via `XPath.evalAsString`. The active code reads it directly from `$globalVariables` in XSLT instead.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_CCBS_CREATE_MEMO_FOR_SBM.rule` | 117 lines |
| Author | sakarin-radchapunya | |
| Priority | 5 | |
| forwardChain | true | |
| Backend event | `Events.OMConsumers.OMXFM.Request.CCBS_CREATE_MEMO` | NOT CCBS_CREATE_MEMO_FOR_SBM [MEDIUM] |
| Payload root | `ns1:createMemoRequest / ns2:createMemo` | Two-level wrapper |
| Schema NS (ns1) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/FM/CreateMemo.xsd` | FM wrapper |
| Schema NS (ns2) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/OMX/ESB/CreateMemo.xsd` | ESB content |
| Fan-out unit | Subscriber (POU + COU) | Standard per-subscriber pattern |
| RefID | Subscriber RefId (bare) | Always emitted |
| entityId | SubscriberId | MSISDN / subscriber number |
| entityTypeId | "6" (hardcoded) | Subscriber entity type |
| memoTypeId | $globalVariables/OMX_OM/BizRules/SBM_BUY_DATA_PACK/CreateMemoTypeId | Runtime configuration [MEDIUM] |
| Resub guard | `Response[ReferenceId == refId && CompletionStatus==2]` | Per-subscriber |
| PurgePendingRequestsBeforeResubmit | ABSENT | [LOW] |
| PreExecCheck | Uses `nextAct.PreExecCheck` | POU: GetXMLForSubscriber; COU: GetXMLForSubscriberInChildOU |
| UserName/Password gate | Global variable `IsEnableUserPass='true'` | Same as CCBS_UPDATE_ACCOUNT_NAME_ADDRESS |
| Dispatch | `Event.Ext.sendEventImmediate` | NOT IntraActivitySequencing |
| OPERATION_NAME (request) | `"CCBS_CREATE_MEMO"` | Hardcoded — differs from rule name |
| OPERATION_NAME (response) | `"CCBS_CREATE_MEMO"` | Hardcoded |
| Response concept | `Concepts.FM.Base.ResponseBase` | Standard — not dedicated |
| Fan-in | `RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)` | Standard helper |

---

## §3 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_CREATE_MEMO_FOR_SBM"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_CREATE_MEMO_FOR_SBM"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §7 — SOC Offer Lookup & memoText Construction

### $soc XPath Filter (computed inside XSLT)

| Field | XPath | Notes |
|-------|-------|-------|
| $soc (POU) | `ParentOU[$iPOU]/Subscriber[$iPSUB]/SubscriberOffers[ServiceType="86" and ExtendedInfo[Name="FE_OR_CCBS" and (Value="BRMS" or Value="FE")]]/OfferName` | ServiceType=86=data pack/VAS; FE_OR_CCBS=BRMS/FE identifies eligible offers |
| $soc (COU) | `ParentOU[$iPOU]/ChildOU[$kCOU]/Subscriber[$kCSUB]/SubscriberOffers[ServiceType="86" and ExtendedInfo[Name="FE_OR_CCBS" and (Value="BRMS" or Value="FE")]]/OfferName` | Identical filter on COU path |

### memoText concat Pattern

```text
concat(
  $sub/SubscriberActivityInfo/UserText,
  " [By DatapackService : soc= ",
  $soc,
  " ] ",
  "channel:[ ",
  $orderRequest/OrderData/Channel,
  " ]"
)
```

Example output: `Customer request to add data pack [By DatapackService : soc= DATA_BASIC_5GB ] channel:[ WEB ]`

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

Two XSLT variants: POU (params: i, j → iPOU, iPSUB) and COU (params: i, k, j → iPOU, kCOU, kCSUB). Payload structure is identical; only the subscriber XPath differs.

```text
createEvent
└── event
    ├── JMSPriority             ← $orderRequest/OrderPriority                            [Conditional]
    ├── JMSCorrelationID        ← $orderRequest/OrderData/OMXTrackingId                  [Conditional]
    ├── OrderID                 ← $orderRequest/OrderData/OrderID                        [Conditional]
    ├── RefID                   ← $refId (subscriber RefId)                              [Always]
    ├── UserName                ← $orderRequest/OrderData/User                           [Credential-gated: IsEnableUserPass='true' AND User present]
    ├── PassWord                ← $orderRequest/OrderData/Password                       [Credential-gated]
    ├── OrderType               ← $orderRequest/OrderData/OrderType                      [Conditional]
    ├── CES                     ← $orderRequest/OrderData/CES                            [Conditional]
    └── payload
        └── ns1:createMemoRequest
            └── ns2:createMemo
                ├── ns2:entityId      ← $sub/SubscriberId                                [Always]
                ├── ns2:entityTypeId  ← "6" (subscriber type, hardcoded)                 [Always]
                ├── ns2:memoText      ← concat(UserText, "[By DatapackService:soc= ",
                │                       $soc, "] channel:[", Channel, "]")              [Always — $soc may be empty]
                └── ns2:memoTypeId    ← $globalVariables/OMX_OM/BizRules/
                                        SBM_BUY_DATA_PACK/CreateMemoTypeId              [Global variable — may be empty]
```

---

## §15 — Function Dependency Tree

```text
Request_CCBS_CREATE_MEMO_FOR_SBM (rule)
├── isActResub = (RequestCount > 0 && IsOrderResubmitted)
├── nextAct = Instance.getByExtIdByUri(NextActivityName, Activity)
├── chkXPath = nextAct.PreExecCheck
├── [NOTE: NO Parameter guard / NO PurgePendingRequestsBeforeResubmit]
├── [POU loop i → j]:
│   ├── refId = ParentOU[i].Subscriber[j].RefId
│   ├── [if PreExecCheck length > 0]:
│   │   ├── sXML = GetXMLForSubscriber(orderRequest, refId)
│   │   └── chkRes = XPath.execute("/("+chkXPath+")", sXML, ...)
│   └── [if chkRes == "true"]:
│       ├── [Resub guard]: Response[ReferenceId==refId && CompletionStatus==2] → reqSuccess
│       └── [if !reqSuccess]:
│           ├── // [COMMENTED OUT] typeId = XPath.evalAsString(globalVar XPath)
│           ├── reqEvent = Event.createEvent(CCBS_CREATE_MEMO, XSLT:
│           │   ├── entityId = Subscriber[$iPSUB].SubscriberId
│           │   ├── entityTypeId = "6"
│           │   ├── memoText = concat(UserText, "[By DatapackService:soc=", $soc, "] channel:[", Channel, "]")
│           │   └── memoTypeId = $globalVariables/.../SBM_BUY_DATA_PACK/CreateMemoTypeId
│           ├── Event.Ext.sendEventImmediate(reqEvent)
│           ├── [if AllowWriteLog(OrderType)]: Logger (INFO, OPERATION_NAME="CCBS_CREATE_MEMO")
│           ├── [if !isActResub]: RequestCount++
│           └── isSkipped = false
├── [COU loop i → k → j]:
│   ├── refId = ParentOU[i].ChildOU[k].Subscriber[j].RefId
│   ├── [PreExecCheck via GetXMLForSubscriberInChildOU]
│   └── [same sendEventImmediate pattern, COU XSLT variant]
├── [if !isSkipped]:
│   ├── orderCurrentActivity.Status = GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch]: HandleActivityException

Response_CCBS_CREATE_MEMO_FOR_SBM (rulefunction)
├── extId = OMXUtils.generateTrackingID()
├── activityRes = Instance.createInstance(ResponseBase){extId, ResponseCode, ResponseMessage, CompletionStatus, ReferenceId}
├── currActivity.Response[] ← activityRes
├── Logger: OPERATION_NAME="CCBS_CREATE_MEMO"
└── return RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Per-subscriber fan-out across POU and COU. One CreateMemo per subscriber. |
| R2 | RefID = subscriber RefId (always emitted). |
| R3 | Backend event = CCBS_CREATE_MEMO (not CCBS_CREATE_MEMO_FOR_SBM). |
| R4 | entityId = SubscriberId; entityTypeId = "6" (subscriber type, hardcoded). |
| R5 | $soc = SubscriberOffers[ServiceType="86" and ExtendedInfo[Name="FE_OR_CCBS" and (Value="BRMS" or Value="FE")]]/OfferName. |
| R6 | memoText = concat(UserText, " [By DatapackService : soc= ", $soc, " ] ", "channel:[ ", Channel, " ]"). |
| R7 | memoTypeId = $globalVariables/OMX_OM/BizRules/SBM_BUY_DATA_PACK/CreateMemoTypeId (must be configured in deployment). |
| R8 | UserName/PassWord gated by global variable IsEnableUserPass='true'. |
| R9 | Fan-in via IsAllResponseSuccess (ResponseCode suffix "000"). |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Event name CCBS_CREATE_MEMO diverges from rule name CCBS_CREATE_MEMO_FOR_SBM | [MEDIUM] | Align rule name with event name, or document discrepancy in event catalog |
| memoTypeId from global variable — empty if not configured | [MEDIUM] | Add configuration validation at startup; include SBM_BUY_DATA_PACK/CreateMemoTypeId in deployment checklist |
| $soc can resolve to empty string if no matching offer found | [MEDIUM] | Add XPath guard before send, or document that blank SOC is acceptable |
| No PurgePendingRequestsBeforeResubmit | [LOW] | Verify CCBS createMemo idempotency for duplicate calls |
| Commented-out XPath.evalAsString typeId code (lines 49, 87) — dead code | [LOW] | Remove in modernized code |

---

## §19 — Response Message Rule (Response_CCBS_CREATE_MEMO_FOR_SBM)

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Order context |
| eventResponse | Events.OMConsumers.OMXFM.Response.CCBS_CREATE_MEMO | Backend response event |
| currActivity | Concepts.OM.ProcessConfig.Activity | Activity state & response list |

### §19.3 ResponseBase Construction

```text
createObject
└── object (Concepts.FM.Base.ResponseBase)
    ├── @extId           ← $extId (OMXUtils.generateTrackingID())   [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode               [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg                [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus           [Conditional]
    └── ReferenceId      ← $eventResponse/RefID                      [Conditional]
```

### §19.4 Fan-in Completion Logic

| Field | Value |
|-------|-------|
| Fan-in function | `RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)` |
| Expected logic | Returns "true" when all responses have ResponseCode suffix "000" |
| Write-back | None |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
