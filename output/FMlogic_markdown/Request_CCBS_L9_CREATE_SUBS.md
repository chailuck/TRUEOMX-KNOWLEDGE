# Request_CCBS_L9_CREATE_SUBS

## §1 Overview & Purpose

Creates a new postpaid subscriber in CCBS via the TNP L9 API: **L9CreateNewActivateSubscriber**. This is a richer variant of `CCBS_CREATE_SUBS` that sends subscriber name, address, all resource types (MSISDN, IMSI, SIM, IMEI, BN ranges), SOC offers (contract + PP + dummy IMEI), payment channels, and MNP porting fields in a single request.

Iterates ParentOU.Subscriber[j], then ChildOU[m].Subscriber[j]. Uses **IntraActivitySequencing** pattern. Resubmit-safe.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_L9_CREATE_SUBS` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | CCBS_L9_CREATE_SUBS |
| Backend | CCBS — L9CreateNewActivateSubscriber |
| Request Schema | `http://services.omx.truecorp.co.th/FMServices/L9CreateSubscriberRequest` |
| Response Schema | `http://services.omx.truecorp.co.th/FMServices/L9CreateSubscriberResponse` |
| Pattern | IntraActivitySequencing |
| Iteration Scope | ParentOU.Subscriber[j] → ChildOU[m].Subscriber[j] |
| Response Concept | `Concepts.FM.Response.CCBSCreateSubsRes` |

---

## §4 Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "CCBS_L9_CREATE_SUBS"
orderRequest.ProcessFlow.NextActivityID == "CCBS_L9_CREATE_SUBS"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 Execution Flow

1. If resubmit: `PurgePendingRequestsBeforeResubmit`
2. Read `LogicalDate` singleton
3. Loop ParentOU[i].Subscriber[j]:
   - Skip if RefId already has CompletionStatus=2
   - Evaluate PreExecCheck via `GetXMLForSubscriber`
   - Find PP offer (ServiceType=80), compute `imeiExists`, `dummySocCount`, `contractSocCount`, `addRangeArray`
   - Assert event, call `IntraActivitySequencing.ActionRequestEvent`
   - Fire audit logger
4. Loop ChildOU[m].Subscriber[j]: same via `GetXMLForSubscriberInChildOU`
5. If not isSkipped: `SendFirstRequestEvent` + IN_PROGRESS; else: `SkipActivity("4")`

---

## §8.5 ExtendedInfo Fields

| Key | Required? | Usage |
|-----|-----------|-------|
| DEALER_APP | Optional | L9DealerApp in SubscriberGeneralInfo |
| DONOR_OPERATOR | Optional | L9DonorOperator (non-MNP channel) |
| DONOR_ZONE | Optional | L9DonorZone (non-MNP channel) |
| PORT_IND | Optional | L9PortInd (non-MNP channel) |
| PROJECT_CODE | Optional | L9ProjectCode |
| OLD_BAN_DATE | Optional | L9RFActDate (OrderType 126/127/129) |
| OLD_BAN | Optional | L9RFBan (when non-empty) |
| REC_OPERATOR | Optional | L9RecOperator (non-MNP channel) |
| REC_ZONE | Optional | L9RecZone (non-MNP channel) |
| DONOR_ACCOUNT_ID | Optional | L9TMVBan (OrderType 8/9/15/16) |
| CHG_SPLIT_TYPE | Optional | ChargeDistribution DR→Primary / RS→Secondary |

## §8.6 Global Variables

| Path | Purpose |
|------|---------|
| `$globalVariables/OMX_OM/Rules/.../IsEnableUserPass` | Gate UserName/PassWord inclusion |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `$globalVariables/OMX_OM/WritePayload` | Gate audit payload |

---

## §9.4 GetSequenceValueRequest

| Field | Value |
|-------|-------|
| sequenceName | `"SOC_SEQ_NO"` (hardcoded) |
| incrementByCount | `count($subPP) + count($subPP/RelatedOffersArray) + $dummySocCount + $contractSocCount` |

---

## §10 XSLT Field Mapping Tree

```text
createEvent
└── event
    ├── JMSPriority           ← $orderRequest/OrderPriority                     [Conditional]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId            [Conditional]
    ├── OrderID               ← $orderRequest/OrderData/OrderID                  [Conditional]
    ├── RefID                 ← ParentOU[$iOU]/Subscriber[$iSubscriber]/RefId    [Conditional]
    ├── UserName              ← $orderRequest/OrderData/User                     [Conditional: IsEnableUserPass='true']
    ├── PassWord              ← $orderRequest/OrderData/Password                 [Conditional: IsEnableUserPass='true']
    ├── OrderType             ← $orderRequest/OrderData/OrderType                [Conditional]
    ├── CES                   ← $orderRequest/OrderData/CES                      [Conditional]
    └── payload
        └── ns:L9CreateSubscriber
            ├── ns2:GetSequenceValueRequest
            │   ├── ns2:sequenceName     ← "SOC_SEQ_NO"                          [Always]
            │   └── ns2:incrementByCount ← count(subPP+RelatedOffers)+dummy+contract
            └── ns:L9CreateNewActivateSubscriberRequest
                ├── CustomerIdInfo/customerNo     ← Customer/CustomerId          [Always]
                ├── ExternalIdInfo/externalId     ← Subscriber/MSISDN             [Always]
                ├── UnitIdInfo/chNodeId           ← ParentOU/OUId                 [Always]
                ├── SubscriberTypeInfo/subscriberType ← Subscriber/SubscriberType [Always]
                ├── ns4:SubscriberGeneralInfo
                │   ├── DealerCode       ← OrderData/DealerCode                   [Conditional]
                │   ├── EffectiveDate    ← SubscriberGeneralInfo/EffectiveDate    [Conditional: trim!='']
                │   ├── L9DealerApp      ← ExtendedInfo[DEALER_APP]               [Conditional]
                │   ├── L9DonorOperator  ← MNPInfo/DonorOperator OR ExtInfo       [Conditional: MNP or exists]
                │   ├── L9DonorZone      ← MNPInfo/DonorZoneCode OR ExtInfo       [Conditional]
                │   ├── L9IMSIAlias      ← SubscriberGeneralInfo/IMSIAlias        [Conditional]
                │   ├── L9PortInd        ← 73 (MNP) OR ExtendedInfo[PORT_IND]     [Conditional]
                │   ├── L9ProjectCode    ← ExtendedInfo[PROJECT_CODE]             [Conditional]
                │   ├── L9ProofDate      ← SubscriberGeneralInfo/ProofDate        [Conditional: trim!='']
                │   ├── L9ProofDoc       ← SubscriberGeneralInfo/ProofDoc         [Conditional]
                │   ├── L9RFActDate      ← ExtendedInfo[OLD_BAN_DATE]             [Conditional: OT 126/127/129]
                │   ├── L9RFBan          ← ExtendedInfo[OLD_BAN]                  [Conditional: trim!='']
                │   ├── L9RecOperator    ← MNPInfo/RCPOperator OR ExtInfo         [Conditional]
                │   ├── L9RecZone        ← MNPInfo/RCPZoneCode OR ExtInfo         [Conditional]
                │   ├── L9SaleId         ← SubscriberGeneralInfo/saleId           [Conditional]
                │   ├── L9SmsInd         ← 89 (SMSInd=Y) / 78 (SMSInd=N)         [Conditional]
                │   ├── L9SmsLanguage    ← SubscriberGeneralInfo/smsLang          [Conditional]
                │   ├── L9SplitPeriod    ← SubscriberGeneralInfo/SplitPeriod      [Conditional]
                │   ├── L9TMVActDate     ← SubscriberGeneralInfo/InitActDate      [Conditional: OT 8/9/15/16/53/54]
                │   ├── L9TMVBan         ← ExtendedInfo[DONOR_ACCOUNT_ID]         [Conditional: OT 8/9/15/16]
                │   ├── Language         ← SubscriberGeneralInfo/Language         [Conditional]
                │   ├── PrimResourceTp   ← "MS"                                   [Conditional: Compensation Number]
                │   └── PrimResourceVal  ← ResourceInfo[CompensationNumber]       [Conditional]
                ├── NameInfo (linkType=83) — INDY/CORP name (nameElement1-10)
                ├── NameInfo (linkType=72) — contact info
                ├── NameInfo (linkType=72) — SubscriberName2
                ├── AddressInfo (linkType=83) — addressElement1-15              [Conditional: Tumbon/Amphur/City/Zip]
                ├── AddressInfo (linkType=72) — SubscriberAddress2
                ├── offer
                │   ├── srvAgrInfo (for each contract SOC TR_CONTRACT_IND=Y)
                │   ├── srvAgrInfo (for $subPP ServiceType=80)
                │   └── srvAgrInfo (dummy IMEI SOC 55042, serviceType=85)        [Conditional: imeiExists]
                ├── LogicalResourceInfo (Compensation Number, Category=R, MSISDN, IMSI)
                ├── PhysicalResourceInfo (Category=E, IMEI, SIM)
                ├── ParameterInfo (ServiceType=80, contract SOCs)
                ├── DefaultRCPayChannelInfo/payChannelId   ← PayChannelIdPrimary OR AccountID
                ├── DefaultOCPayChannelInfo/payChannelId   ← same fallback
                ├── PrimaryEventPayChannelIdInfo           ← same fallback
                ├── ChargeDistributionDetailsInfo          [Conditional: subPP exists]
                │   └── CHG_SPLIT_TYPE: DR→Primary / RS→Secondary / default→Primary
                ├── ResourceRangeList (addRangeArray BN ranges, tokenize by "-") [Conditional]
                ├── ActivityInfo
                │   ├── activityReason ← SubscriberActivityInfo/ActivityReason OR "CREQ"
                │   └── userText       ← SubscriberActivityInfo/UserText          [Conditional]
                └── ActivityDateInfo/activityDate ← $orderRequest/OrderData/EffectiveDate [Conditional: trim!='']
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_L9_CREATE_SUBS
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)  [if resubmit]
├── GetXMLForSubscriber(orderRequest, refId)
├── GetXMLForSubscriberInChildOU(orderRequest, refId, POURefId)
├── XPath.execute("/(preExecCheck)", sXML, ...)
├── XPath.evalAsBoolean(imeiExists check)
├── Event.assertEvent(reqEvent)
├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
├── Event.Ext.sendEventImmediate(Logger)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(req, activity, "4")
└── HandleActivityException(req, activity, ae, "")
```

---

## §17 Migration Notes

| # | Requirement / Risk | Severity |
|---|-------------------|---------|
| R1 | L9 API is TNP-specific; verify availability on target platform vs standard createSubscriber | [HIGH] |
| R2 | SOC_SEQ_NO GetSequenceValueRequest — must replicate sequence allocation logic | [HIGH] |
| R3 | Dummy IMEI SOC (55042) injection — hardcoded business rule | [MEDIUM] |
| R4 | MNP dual-source: Channel=MNP (MNPInfo.*) OR ExtendedInfo — both paths must be preserved | [MEDIUM] |
| R5 | CHG_SPLIT_TYPE DR/RS charge distribution — requires both PayChannelIdPrimary and Secondary | [MEDIUM] |
| R6 | activityReason defaults to "CREQ" when SubscriberActivityInfo absent | [LOW] |
| R7 | OrderType-specific fields (L9RFActDate for 126/127/129; L9TMVActDate/L9TMVBan for 8/9/15/16) | [MEDIUM] |
| R8 | BN Resource ranges tokenized by "-" — business number range format | [LOW] |

---

## §19 Response Message Rule

### §19.1 Overview

Parses `L9CreateSubscriberResponse`, writes new `SubscriberId` back to each subscriber matched by RefId, creates `CCBSCreateSubsRes` concept, logs audit, drives fan-in completion.

### §19.2 Write-back

| Target Field | Source XPath |
|-------------|-------------|
| Subscriber.SubscriberId | `payload/xsd3:L9CreateSubscriberResponse/.../SubscriberId/SubscrNumber` |
| Subscriber.ResponseCode | `eventResponse.ResponseCode` |
| Subscriber.ResponseMsg | `eventResponse.ResponseMsg` |

Match by `Subscriber.RefId == eventResponse.RefID` for both ParentOU and ChildOU.

### §19.3 ResponseBase Concept (CCBSCreateSubsRes)

```text
createObject
└── object [extId ← OMXUtils.generateTrackingID()]
    ├── ResponseCode    ← $eventResponse/ResponseCode    [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg     [Conditional]
    ├── CompletionStatus← $eventResponse/CompletionStatus[Conditional]
    └── ReferenceId     ← $eventResponse/RefID           [Conditional]
```

### §19.4 Completion Logic

```text
successResponseCount = count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
if(currActivity.RequestCount == successResponseCount) → "true"
else → "false"
```

### §19.5 Response Audit Log

| Field | Value |
|-------|-------|
| PROCESS_ID | concat(pid, "_RES") |
| OPERATION_NAME | "CCBS_L9_CREATE_SUBS" |
| AUDIT_TRACE | "Response received for CCBS_L9_CREATE_SUBS" |
| LOG_LEVEL | INFO |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
