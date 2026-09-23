# Request_AA_ACTIVATE_SUBS

> AA Activate Subscriber — Per-Subscriber Fan-Out with Rich Provisioning Payload

**Priority:** 5 | **forwardChain:** true | **Author:** awalia-t420 | **Pattern:** IntraActivitySequencing | **Backend:** AA (ActivateSubscriberRequest) | **Generated:** 2026-07-27

---

## §1 — Overview & Purpose

This is the core AA subscriber provisioning rule. It iterates every subscriber (ParentOU and ChildOU) and sends one `AA_ACTIVATE_SUBS` JMS event per subscriber to the AA backend. The event carries a rich `ActivateSubscriberRequest` payload including identity, network command type, SIM/IMSI, billing, operator, subscriber status, call-forwarding numbers, SharePlan AATags, and IoT flags. The response handler uses standard fan-in counting.

> **IntraActivitySequencing pattern:** One request per subscriber. `RequestCount++` per eligible subscriber. Fan-in completes when `RequestCount == count(Response[ResponseCode ends with "000"])`.

> **AA_CHECK_CONFIRMATION pre-wiring:** After all subscriber requests are sent, the rule scans `ProcessFlow.Activities[]` for any `AA_CHECK_CONFIRMATION` activity with the same `Parameter[0]` and pre-seeds its `RequestCount` — same pattern as `OMX_GET_SRV_TRX_NO`.

> **ProcessSwitchFeatures pre-step:** Before dispatching each event, `ProcessSwitchFeatures()` is called to apply switch feature data from AA_GET_SWITCH_FEATURE_OFFER to subscriber offerings before each dispatch.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_AA_ACTIVATE_SUBS` |
| Priority | 5 |
| forwardChain | true |
| Author | awalia-t420 |
| Backend | AA — ActivateSubscriberRequest / ActivateSubscriberOnAARequest |
| Request schema | `http://services.omx.truecorp.co.th/FMServices/activateSubscriberRequest` |
| Dispatch pattern | IntraActivitySequencing — one event per subscriber (ParentOU + ChildOU) |
| Parameter[0] BE / Parameter[1] XPath | Network command type (SRV_TRX_TP_CD): NAC, INAC, DSD, IDSD, RCL, IRCL… |
| Parameter[1] BE / Parameter[2] XPath | SOURCE_OR_TARGET filter — governs bill cycle source selection |
| Named: ALT_CES | If "Y" → use OrderData.ExtendedInfo[ALT_CES] as CES endpoint |
| Named: OPERATORID | Activity-level operator ID override (tier 5 of 6) |
| Audit gate | UNCONDITIONAL — no AllowWriteLog check; LOG_LEVEL=ERROR for request (unusual) |
| finally block | `Instance.deleteInstance(swfRes)` + `Instance.deleteInstance(fListRes)` |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity instance |
| 2 | `orderCurrentActivity.ActivityID == "AA_ACTIVATE_SUBS"` | Targets this FM only |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "AA_ACTIVATE_SUBS"` | Order-level double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Fresh activity only |

---

## §5 — Execution Flow

```text
1. Init: isActResub; guard Parameter@length == 0 → throw DATA_ISSUE
         read param (Parameter[2] XPath = SOURCE_OR_TARGET)
         read altParam (ALT_CES named param)
         read paramOperatorIdValue (OPERATORID named param)
2. For each ParentOU[i].Subscriber[j]:
     - check reqSuccess (skip if CompletionStatus=2 for refId)
     - evaluate PreExecCheck via GetXMLForSubscriber
     - derive isCustomerHybrid (AccountSubType starts-with "HY" OR equals "PHI")
     - derive isNetworkIOT, isSubscriberIOT via BRMS.ValidateIsIOT(subsType)
     - resolve pp (current price plan) and prev_pp (previous price plan)
     - call ProcessSwitchFeatures()
     - resolve BAN (3-branch logic)
     - resolve billCycleNo (SOURCE_BILL_CYCLE or BillCycleNo → ConvertBillCycleDate)
     - build and send AA_ACTIVATE_SUBS event (ParentOU+AATags variant)
     - send Logger audit (unconditional, LOG_LEVEL=ERROR)
     - [!isActResub] RequestCount++
3. For each ParentOU[i].ChildOU[m].Subscriber[n]:
     - same flow using ChildOU XSLT variant
     - no SharePlan MNUM blocks; adds PBX OPERATOR_ID "170033"
4. AA_CHECK_CONFIRMATION pre-wiring (lines 190-196):
     scan Activities[i] where ActivityID="AA_CHECK_CONFIRMATION"
     AND Parameter[0] = currentActivity.Parameter[0]
     AND RequestCount > 0
     → set Activities[i].RequestCount = orderCurrentActivity.RequestCount
5. If subscribers processed → status IN_PROGRESS + SendDataToDB
   else → SkipActivity("4")
6. finally: Instance.deleteInstance(swfRes) + Instance.deleteInstance(fListRes)
7. Exception → HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
```

---

## §8 — System & Integration Dependencies

### §8.1 — JMS / ESB Channel Dependencies

| Direction | Event | Method | Note |
|-----------|-------|--------|------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.AA_ACTIVATE_SUBS` | `sendEventImmediate` | One per subscriber; both ParentOU and ChildOU use same event type |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | `sendEventImmediate` | UNCONDITIONAL, per-subscriber; LOG_LEVEL=ERROR (unusual — most FMs use INFO) |

### §8.2 — Activity Parameter Dependencies

| Parameter | Index | Role |
|-----------|-------|------|
| Network command type | Parameter[0] BE / Parameter[1] XPath | SRV_TRX_TP_CD in payload; drives SRV_TRX_NM_CD, SUB_STATUS, ProcessSwitchFeatures, AA_CHECK_CONFIRMATION match key |
| SOURCE_OR_TARGET filter | Parameter[1] BE / Parameter[2] XPath | Governs bill cycle source and customerNo source selection |
| ALT_CES | Named (GetActivityParameterValueFromKey) | "Y" → use OrderData.ExtendedInfo[ALT_CES] as CES endpoint |
| OPERATORID | Named (GetActivityParamValueFromKey) | Activity-level override at tier 5 of OPERATOR_ID hierarchy |

### §8.3 — Helper Function Dependencies

| Function | Purpose |
|----------|---------|
| `ProcessSwitchFeatures(orderReq, subscriber, agreement, isHybrid, pp, prev_pp, cmdType)` | Applies switch feature data from AA_GET_SWITCH_FEATURE_OFFER; called per-subscriber before dispatch |
| `BRMS.ValidateIsIOT(subsType, isNetwork)` | Returns true if subscriber type indicates IoT |
| `ConvertBillCycleDate(tmpBCN)` | Converts raw bill cycle number to AA-expected format |
| `GetXMLForSubscriber` / `GetXMLForSubscriberInChildOU` | Serialises subscriber context for PreExecCheck XPath evaluation |

### §8.4 — Global Variable Dependencies

| Path | Used For |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/ActivateIndy_OperatorIdtoAA` | OPERATOR_ID for OrderType=1 + CustomerType=73 |
| `OMX_OM/WritePayload` | Controls whether audit payload body is included |

---

## §9 — Request Payload — ActivateSubscriberRequest

> ParentOU and ChildOU variants are structurally identical except: (1) ChildOU omits SharePlan MNUM AATags; (2) ChildOU adds PBX OPERATOR_ID "170033" tier; (3) ChildOU CUST_HYBRID uses inline XPath.

```text
createEvent
+-- JMSPriority          <- OrderPriority                                      [Conditional]
+-- JMSCorrelationID     <- OrderData/OMXTrackingId                            [Conditional]
+-- OrderID              <- OrderData/OrderID                                  [Conditional]
+-- RefID                <- subscriber RefId                                   [Always]
+-- OrderType            <- OrderData/OrderType                                [Conditional]
+-- CES                  <- ALT_CES logic or OrderData/CES                     [Conditional]
+-- payload
    +-- ns:ActivateSubscriberRequest
        +-- ns:ActivateSubscriberOnAARequest
            +-- ns:subscriptioninfo
                +-- ns:customerNo           <- CustomerId (or SOURCE_CUSTOMER_ID) [Always]
                +-- ns:subscriberId         <- Subscriber/SubscriberId            [Conditional]
                +-- ns:payChannelId         <- Account.PayChannelId or Sub.PayChannelIdPrimary [Conditional]
                +-- ns:CFU_NUM              <- ResourceInfo[CFU_NO_PARAM]/ValuesArray  [Conditional]
                +-- ns:CFNRC_NUM            <- ResourceInfo[CFNRC_NO_PARAM]/ValuesArray [Conditional]
                +-- ns:CFB_NUM              <- ResourceInfo[CFW_NO_PARAM]/ValuesArray   [Conditional]
                +-- ns:CFNRY_NUM            <- ResourceInfo[CFNRY_NO_PARAM]/ValuesArray [Conditional]
                +-- ns:SearchPayChannelPaginationInfo pageSize=1000,pageNumber=0,rows=1000 [Always static]
                +-- ns:MSISDN               <- Subscriber/MSISDN                 [Always]
                +-- ns:BAN                  <- BAN selection logic (§10.2)       [Always]
                +-- ns:IMSI                 <- NEW_IMSI preferred over IMSI       [Conditional]
                +-- ns:SRV_TRX_TP_CD       <- Parameter[1] XPath = Parameter[0] BE [Always]
                +-- ns:SRV_TRX_S_NO        <- SrvTrxNoInfo[SrvTrxTp=cmd]/SrvTrxNo [Conditional]
                +-- ns:SRV_TRX_NM_CD       <- command-to-name mapping 15 entries   [Always]
                +-- ns:PP                   <- pp (current price plan)             [Always]
                +-- ns:PROVISIONING_DATE   <- current-dateTime() dd/MM/yyyy HH:mm:ss [Always static-format]
                +-- ns:OPERATOR_ID         <- 6-tier hierarchy (§10.3)             [Always]
                +-- ns:ACCOUNT_CATEGORY    <- CustomerType to I/B/C (§10.4)        [Conditional block]
                +-- ns:FIRST_NAME           <- SubscriberName/FirstName             [Conditional]
                +-- ns:LAST_NAME            <- SubscriberName/LastName              [Conditional]
                +-- ns:CERTIFICATE_NUMBER  <- Identification concat DealerCode      [Always]
                +-- ns:CERTIFICATE_TYPE    <- CustomerGeneralInfo/IdentificationType [Conditional]
                +-- ns:ACCOUNT_TYPE        <- AccountManagementInfo/AccountSubType  [Always]
                +-- ns:BIRTH_DATE          <- CustomerGeneralInfo/BirthDate          [Conditional]
                +-- ns:BILLING_LANGUAGE    <- Language: EN=>E, TH=>T, else empty    [Always]
                +-- ns:GENDER              <- SubscriberName/Gender                  [Conditional]
                +-- ns:HOME_TELNO          <- SubscriberName/HomePhone               [Conditional]
                +-- ns:SIM_NO              <- tib:trim(ResourceInfo[SIM]/ValuesArray) [Always]
                +-- ns:COMPANY_CODE        <- IoT: Account.CompanyCode; else: SubscriberType [Always]
                +-- ns:BILL_CYCLE          <- billCycleNo via ConvertBillCycleDate   [Always]
                +-- ns:SUB_STATUS          <- "S" if suspend-type, else "A" (§10.5) [Always]
                +-- ns:SUB_STATUS_RSN_CODE <- "CREQ" if Indy activation, else empty [Always]
                +-- ns:PREV_SUBSCRIBER_NO  <- ResourceInfo[OLD_MSISDN]/ValuesArray   [Conditional]
                +-- ns:PREV_BAN            <- conditional on OLD_MSISDN presence     [Conditional]
                +-- ns:PREV_IMSI           <- OLD_MSISDN: IMSI; else OLD_IMSI        [Conditional]
                +-- ns:PREV_PP             <- prev_pp (CCBS price plan)              [Always]
                +-- ns:SOURCE_ID           <- "AMDOCS"                               [Always static]
                +-- ns:CUST_HYBRID         <- isCustomerHybrid                       [Always]
                +-- ns:ZONE                <- ResourceInfo[MSISDN_ZONE]/ValuesArray   [Conditional]
                +-- ns:IOT                 <- SubscriberType stripped of leading "I"  [Conditional: isNetworkIOT]
                +-- ns:AATags              <- SharePlan AAXML blocks + AA_XML_Array   [Conditional]
```

---

## §10 — Key Business Logic Details

### §10.1 — SRV_TRX_NM_CD Mapping (Parameter[0] to AA Operation Name)

| Command(s) | ns:SRV_TRX_NM_CD |
|------------|-----------------|
| NAC / INAC | Activate |
| RCL / IRCL | Resume |
| DSD / IDSD | Deactivate |
| CCN / ICCN | SwapMSISDN |
| SSP / ISSP | SwapSIM [first 8 chars of IMSI] |
| CCD / ICCD | GeneralUpdate |
| SSU / ISSU | SoftSuspend |
| SRS / ISRS | SoftRestore |
| SUS / ISUS | Suspend |
| RSP / IRSP | Restore |
| FTS / IFTS | FullToSoft |
| CCI / ICCI | InformationUpdate |
| RM2RFCRPF | Create dummy RF profile |
| RM2RFMGRT | Migrate RM to RF by OTA |
| SSPMGRT | Migrate RM to RF by SwapSIM |
| (other) | (empty string) |

### §10.2 — BAN Selection Logic

```text
if (OrderType IN {1, 11026}) AND CustomerType = 73  then  "999999999"   // Indy activation
else if OrderType = 11001                            then  banParent      // SharePlan add
else                                                       Account[RefId=AccountRefId]/AccountID
```

### §10.3 — OPERATOR_ID Selection Hierarchy (6 Tiers)

| Tier | Condition | Value |
|------|-----------|-------|
| 1 | tib:trim(OrderData/OperatorId) is non-empty | OrderData/OperatorId |
| 2 | SubscriberType=RM AND OrderType IN {7,8} | 98391 |
| 3 | SubscriberType=RF AND OrderType IN {7,8} | 98392 |
| 4 | OrderType=1 AND CustomerType=73 | Global: ActivateIndy_OperatorIdtoAA |
| 4b (ChildOU only) | Media=PBX | 170033 |
| 5 | string-length(paramOperatorIdValue) > 0 | OPERATORID named param value |
| 6 (default) | otherwise | 60001 |

### §10.4 — ACCOUNT_CATEGORY Mapping

| CustomerTypeInfo/Type | AccountSubType | ACCOUNT_CATEGORY |
|-----------------------|----------------|-----------------|
| 73 | any | I (Individual) |
| 66 | any | B (Business) |
| 67 | any | C (Corporate) |
| 70 | PHI | I |
| 70 | other | C |

### §10.5 — SUB_STATUS Logic

```text
SUB_STATUS = "S"  when SRV_TRX_TP_CD in {TRX, SUS, SSU, FTS, ISUS, ISSU, IFTS}
           = "A"  otherwise
```

### §10.6 — PP (Price Plan) Resolution

```text
pp      = first OfferName where ServiceType=80 AND FE_OR_CCBS=FE  (check Subscriber then Agreement)
          OR first OfferName where ServiceType=80 AND FE_OR_CCBS=CCBS
          OR empty string

prev_pp = first OfferName where ServiceType=80 AND FE_OR_CCBS=CCBS only
```

### §10.7 — CES Routing

```text
if altParam = "Y" AND OrderData.ExtendedInfo[ALT_CES]/Value is non-empty:
    event.CES = ExtendedInfo[ALT_CES]/Value
else:
    event.CES = OrderData.CES
```

### §10.8 — SharePlan AATags (ParentOU only)

When `chkChildCancelShareplan=true` (OT 11002 + SHAREPLAN_ACTION=CANCEL) or `chkParentAddShareplan` is non-empty (OT 11001 or 21), emits AAXML feature group blocks with MNUM=Y, MAIN=mainNumber, CHILD=subscriberMSISDN. Additionally iterates `subscriberInstance.AA_XML_Array/AA_XML` and emits AAXML for each entry with non-empty NEW_OR_PREV. ChildOU variant has no SharePlan AATags.

### §10.9 — isCustomerHybrid Logic

```text
isCustomerHybrid = (AccountSubType starts-with "HY") OR (AccountSubType = "PHI")
Note: OMX-2748 added PHI as a hybrid account subtype alongside the HY prefix.
```

---

## §12 — Activity Status Management

| Trigger | Code | Status |
|---------|------|--------|
| Rule fires initially | 0 | WAITING |
| No eligible subscribers | 4 | SKIPPED |
| First request sent | 1 | IN_PROGRESS |
| Exception thrown | 3 | ERROR |
| Fan-in complete (response) | 2 | COMPLETED |

---

## §15 — Function Dependency Tree

```text
Request_AA_ACTIVATE_SUBS (rule)
+-- Guard: Parameter@length == 0 => throw DATA_ISSUE
+-- GetActivityParamValueFromKey(currAct, "OPERATORID")
+-- GetActivityParameterValueFromKey(currAct, "ALT_CES")
+-- XPath.evalAsString(Parameter[2])                          [param = SOURCE_OR_TARGET]
+-- Per subscriber (ParentOU + ChildOU):
|   +-- reqSuccess check: Response[ReferenceId=refId, CompletionStatus=2]
|   +-- [PreExecCheck] GetXMLForSubscriber / GetXMLForSubscriberInChildOU
|   +-- XPath.evalAsBoolean(isCustomerHybrid)                [starts-with HY or =PHI]
|   +-- BRMS.ValidateIsIOT(subsType, true)                   [isNetworkIOT]
|   +-- BRMS.ValidateIsIOT(subsType, false)                  [isSubscriberIOT]
|   +-- XPath.evalAsString(pp XPath)                         [ServiceType=80 FE offer]
|   +-- XPath.evalAsString(prev_pp XPath)                    [ServiceType=80 CCBS offer]
|   +-- ProcessSwitchFeatures(orderRequest, subscriber, agreement,
|   |     isCustomerHybrid, pp, prev_pp, Parameter[0])
|   +-- [chkParentAddShareplan] XPath banParent resolution
|   +-- XPath.evalAsString(billCycleNo source)
|   +-- ConvertBillCycleDate(tmpBCN)
|   +-- Event.createEvent(xslt://AA_ACTIVATE_SUBS)
|   +-- Event.Ext.sendEventImmediate(reqEvent)
|   +-- System.nanoTime()
|   +-- Event.Ext.sendEventImmediate(Logger)                 [unconditional, LOG_LEVEL=ERROR]
|   +-- [!isActResub] RequestCount++
+-- AA_CHECK_CONFIRMATION pre-wiring:
|   +-- Activities[i].RequestCount = RequestCount
|       (where ActivityID="AA_CHECK_CONFIRMATION"
|       AND Parameter[0] == currActivity.Parameter[0]
|       AND Activities[i].RequestCount > 0)
+-- GetActivityStatusString("1", false)
+-- SendDataToDB(orderRequest)
+-- SkipActivity(orderRequest, orderCurrentActivity, "4")    [if isSkipped]
+-- HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
+-- [finally] Instance.deleteInstance(swfRes) + Instance.deleteInstance(fListRes)

Response_AA_ACTIVATE_SUBS (rulefunction)
+-- Instance.createInstance(xslt://AA_ActivateSubscriberRes)
|   +-- extId           = payload/response/srv_trx_s_no    [unique: actual SRV TRX S NO]
|   +-- ResponseCode    = eventResponse/ResponseCode
|   +-- ResponseMessage = eventResponse/ResponseMsg
|   +-- CompletionStatus= eventResponse/CompletionStatus
|   +-- ReferenceId     = eventResponse/RefID
|   +-- ret_description = payload/response/ret_description [Conditional]
|   +-- subscriber_no   = payload/response/subscriber_no   [Conditional]
|   +-- srv_trx_tp_cd   = payload/response/srv_trx_tp_cd   [Conditional]
|   +-- srv_trx_s_no    = payload/response/srv_trx_s_no    [Conditional]
|   +-- ret_code        = payload/response/ret_code        [Conditional]
|   +-- OMXTrackingId   = orderRequest/OrderData/OMXTrackingId [Always]
+-- currActivity.Response[n] = activityRes
+-- System.nanoTime()
+-- Event.Ext.sendEventImmediate(Logger)                    [unconditional, LOG_LEVEL=INFO]
+-- XPath.evalAsInt(count(Response[tib:right(tib:trim(ResponseCode),3)="000"]))
+-- if RequestCount == successResponseCount => return "true"
+-- else => return "false"
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — One request per subscriber (ParentOU + ChildOU). Fan-in completes when all subscribers respond with ResponseCode ending "000".
- **R2** — `ProcessSwitchFeatures()` must be called before each subscriber dispatch — it mutates in-memory offer data populated by AA_GET_SWITCH_FEATURE_OFFER.
- **R3** — AA_CHECK_CONFIRMATION pre-wiring: after all subscriber requests sent, set AA_CHECK_CONFIRMATION.RequestCount = total subscriber count for the same command type.
- **R4** — SRV_TRX_S_NO must be looked up from `SrvTrxNoInfo[SrvTrxTp=Parameter[0]]` — pre-allocated by OMX_GET_SRV_TRX_NO. Must execute after OMX_GET_SRV_TRX_NO.
- **R5** — Parameter[0] may be IoT-prefixed (e.g., NAC=>INAC) by OMX_TRANSFORM_NETWORK_CMD_TO_IOT. All 15 SRV_TRX_NM_CD mappings handle both plain and IoT-prefixed forms.
- **R6** — OPERATOR_ID 6-tier hierarchy must be preserved exactly, including Indy global variable and PBX special case (ChildOU only).
- **R7** — Bill cycle: if param=SOURCE and SOURCE_BILL_CYCLE ExtendedInfo present, use that value instead of Customer.BillCycleNo.
- **R8** — BAN for Indy (OrderType 1 or 11026, CustomerType 73) must always be "999999999".
- **R9** — SharePlan AATags (MNUM/MAIN/CHILD AAXML blocks) apply to ParentOU subscribers only.
- **R10** — Request audit logging uses LOG_LEVEL=ERROR unconditionally — not INFO and not AllowWriteLog-gated.

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| 15-entry SRV_TRX_NM_CD map is hardcoded; new command types silently produce empty string | [MEDIUM] | Externalise to configuration table; alert on empty SRV_TRX_NM_CD |
| Parameter index off-by-one: BE Parameter[0] = XPath Parameter[1] | [MEDIUM] | Use named constants; document and test index mapping |
| ProcessSwitchFeatures mutates in-memory before dispatch — not rolled back on failure | [MEDIUM] | Ensure ProcessSwitchFeatures is idempotent; test resub scenarios |
| AA_CHECK_CONFIRMATION pre-wiring matches by Parameter[0] equality | [LOW] | Verify at most one AA_ACTIVATE_SUBS per command type in process config |
| ChildOU CUST_HYBRID uses inline XPath vs isCustomerHybrid variable — dual maintenance | [LOW] | Consolidate to shared helper in migration |

---

## §19 — Response Message Rule (Response_AA_ACTIVATE_SUBS)

### §19.1 — Overview

Creates one `AA_ActivateSubscriberRes` concept per subscriber response and appends to `currActivity.Response[]`. The concept carries extended fields from the AA response body. Fan-in completes when `RequestCount == count(Response[ResponseCode ends "000"])`.

> **Notable:** `AA_ActivateSubscriberRes.extId` is set from `payload/response/srv_trx_s_no` (the actual service transaction sequence number), NOT from `OMXUtils.generateTrackingID()` as used by all other response concepts in this process. This is unique to AA_ACTIVATE_SUBS.

### §19.2 — AA_ActivateSubscriberRes Fields

| Field | Source | Note |
|-------|--------|------|
| `extId` | `payload/response/srv_trx_s_no` | Uses actual SRV TRX sequence number (not generateTrackingID) |
| `ResponseCode` | `eventResponse/ResponseCode` | Conditional |
| `ResponseMessage` | `eventResponse/ResponseMsg` | Conditional |
| `CompletionStatus` | `eventResponse/CompletionStatus` | Conditional |
| `ReferenceId` | `eventResponse/RefID` | Conditional |
| `ret_description` | `payload/response/ret_description` | Conditional |
| `subscriber_no` | `payload/response/subscriber_no` | Conditional |
| `srv_trx_tp_cd` | `payload/response/srv_trx_tp_cd` | Conditional |
| `srv_trx_s_no` | `payload/response/srv_trx_s_no` | Conditional |
| `ret_code` | `payload/response/ret_code` | Conditional |
| `OMXTrackingId` | `orderRequest/OrderData/OMXTrackingId` | Always |

### §19.3 — Fan-in Completion Logic

```text
successResponseCount = count(currActivity.Response[
    tib:right(tib:trim(ResponseCode), 3) = "000"
])
if currActivity.RequestCount == successResponseCount  =>  return "true"   // all subscribers done
else                                                   =>  return "false"  // still awaiting
```

> Fan-in counts only successful responses (ResponseCode suffix "000"). A failed subscriber response does not increment toward completion.

### §19.4 — Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | concat(pid, "_RES") |
| OPERATION_NAME | AA_ACTIVATE_SUBS |
| LOG_LEVEL | INFO (response uses INFO; request uses ERROR) |
| payload | Conditional on WritePayload global variable |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
