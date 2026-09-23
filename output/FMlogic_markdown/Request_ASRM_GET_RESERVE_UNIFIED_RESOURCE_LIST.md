# Request_ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST

## §1 Overview & Purpose

**ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST** requests ASRM to reserve a SIM resource for each subscriber in the order. The reserved SIM's ICCID is written back to `Subscriber.ExtendedInfo[ICC_ID]` and, if not an eSIM, to `Subscriber.ResourceInfo[SIM]`. Used during ACTIVATION for both standard SIM allocation and OTA IMSI provisioning for MNP Port In orders (OMX-2718).

Uses `IntraActivitySequencing` to send one ASRM request at a time per subscriber — requests are queued and dispatched sequentially, not in parallel. Covers both ParentOU and ChildOU subscribers.

> **Response event mismatch:** The request rule fires `Events.OMConsumers.OMXFM.Request.ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST` but the rule file name is `Request_ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST`. The event name diverges from the ActivityID — document the mapping carefully in migration.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST` |
| Author | chch |
| Priority | 5 |
| forwardChain | true |
| Backend | ASRM |
| Send pattern | Fan-out — `Event.assertEvent` + `IntraActivitySequencing` per Subscriber |
| Event type sent | `Events.OMConsumers.OMXFM.Request.ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST` |
| Activity param: DEALERCODE | Override dealer code for ASRM DEALER attribute |
| Activity param: COMPANY | Override COMPANY attribute in payload |
| Activity param: ESIM_FLAG | If "Y": skip SIM ResourceInfo creation (eSIM orders) |
| Response rulefunction | `Response_ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST` |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — POU/ChildOU subscribers iterated; Subscriber ExtendedInfo & ResourceInfo written by response |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity params (DEALERCODE, COMPANY, ESIM_FLAG), PreExecCheck, RequestCount, IntraActivitySequencing state |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Extract params: `dealerCodeValue = GetActivityParamValueFromKey("DEALERCODE")`; `company = GetActivityParameterValueFromKey("COMPANY")`
2. If resubmit: `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
3. **POU loop:** for each ParentOU[i] → Subscriber[iSub]:
   — evaluate per-subscriber PreExecCheck via `GetXMLForSubscriber`
   — skip check: Response[].ReferenceId == subRefId AND CompletionStatus=2
   — build ASRM event; `Event.assertEvent(reqEvent)`; `IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)`
   — send audit log; `isSkipped = false`
4. **ChildOU loop:** for each ParentOU[i] → ChildOU[k] → Subscriber[iSub]: same pattern
5. If any sent: `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)` — dispatches first queued request
6. `Status = GetActivityStatusString("1", false)` + `SendDataToDB`
7. If none sent: `SkipActivity("4")`

---

## §7 Data Extraction: COMPANY Resolution Priority

The COMPANY attribute in the ASRM payload follows a 5-way priority chain (POU subscriber scope):

| Priority | Source | Condition |
|----------|--------|-----------|
| 1 | Activity param `COMPANY` | If not empty string |
| 2 | `subscriberPou/ExtendedInfo[Name="COMPANY_OTA"]/Value` — mapped: RM→'06', RF→'02' | If COMPANY_OTA exists (POU only) |
| 3 | `Account[i+1]/AccountManagementInfo/CompanyCode = 'RM'` → `'02'` | POU only |
| 4 | `subscriberPou/ExtendedInfo[Name="COMPANY_CODE"]/Value` | If COMPANY_CODE exists |
| 5 | `'06'` | Default |

> ChildOU subscriber scope uses simplified priority (no COMPANY_OTA check): COMPANY param → CompanyCode=RM→'02' → COMPANY_CODE ExtendedInfo → '06'.

### SIM_TYPE Resolution

| Priority | Source | Condition |
|----------|--------|-----------|
| 1 | `'8'` | OrderType = '11020' (OTA MNP Port In) — OMX-2718 |
| 2 | `subscriberPou/ResourceInfo[ResourceName="SIM_TYPE"]/ValuesArray` | If SIM_TYPE ResourceInfo exists |
| 3 | `'6'` | Default |

### DEALER Resolution

| Priority | Source |
|----------|--------|
| 1 | Activity param `DEALERCODE` (if length > 0) |
| 2 | `'40000001'` (default) |

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Protocol |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST` | JMS / assertEvent + IntraActivitySequencing |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST` | JMS response per subscriber |

### §8.3 Backend API

| System | Operation | Key Schema Types |
|--------|-----------|------------------|
| ASRM | Reserve Unified Resource (SIM) | `ns7:UnifiedResourceListRequest`, `ns3:UnifiedResourceCriteriaInfo`, `ns5:PaginationInfo` |

### §8.4 BE Working Memory Written (response)

| Target | Field/Name | Value | Condition |
|--------|-----------|-------|-----------|
| `Subscriber.ExtendedInfo[]` | Name="ICC_ID", extId={ICCID}:ICC_ID | ICCID from ASRM response | ICC_ID not already present AND ICCID not empty |
| `Subscriber.ResourceInfo[]` | ResourceName="SIM", extId=SUBRI:{trackingId}:{RefID}:SIM | ValuesArray=ICCID | ESIM_FLAG≠Y AND SIM not present AND ICCID not empty |

---

## §10 XSLT Field Mapping — ASRM UnifiedResourceListRequest

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                                  [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId                        [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                              [Conditional]
    ├── RefID                ← $subRefId (Subscriber.RefId)                                 [Always]
    ├── UserName             ← $orderRequest/OrderData/User                                 [Credential-gated: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password                             [Credential-gated: IsEnableUserPass='true']
    ├── OrderType            ← $orderRequest/OrderData/OrderType                            [Conditional]
    └── payload
        └── ns7:UnifiedResourceListRequest
            ├── UnifiedResourceCriteriaInfo
            │   ├── ns3:AttributesValues [COMPANY]
            │   │   ├── ns2:AttrName       ← 'COMPANY'                                     [Always]
            │   │   └── ns2:AttrValue      ← 5-way priority chain (see §7)                 [Conditional chain]
            │   ├── ns3:AttributesValues [SIM_TYPE]
            │   │   ├── ns2:AttrName       ← 'SIM_TYPE'                                    [Always]
            │   │   └── ns2:AttrValue      ← '8'(OT=11020) OR SIM_TYPE ResourceInfo OR '6' [Conditional chain]
            │   ├── ns3:AttributesValues [DEALER]
            │   │   ├── ns2:AttrName       ← 'DEALER'                                      [Always]
            │   │   └── ns2:AttrValue      ← $dealerCodeValue OR '40000001'                [Conditional with default]
            │   ├── ns3:Status             ← 'AVAILABLE'                                   [Always — hardcoded]
            │   └── ns3:Type               ← 'SIM'                                         [Always — hardcoded]
            ├── UnifiedResourceActivityInfo
            │   └── ns6:Activity
            │       └── ns4:ActivityName   ← 'RESERVE'                                     [Always — hardcoded]
            └── PaginationInfo
                ├── ns5:PageNumber         ← 1                                              [Always — hardcoded]
                └── ns5:PageSize           ← 1                                              [Always — hardcoded]
```

---

## §11 Audit Logging

| Log | OPERATION_NAME | AUDIT_TRACE |
|-----|----------------|-------------|
| [REQ] per subscriber (POU + ChildOU) | `ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST` (hardcoded) | Request Sent for ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST |
| [RES] per subscriber | `$currActivity/ActivityID` (dynamic) | `concat("Response received for ", currActivity/ActivityID)` |

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → ACTIVE | At least one subscriber request queued | `SendFirstRequestEvent` + `GetActivityStatusString("1", false)` + `SendDataToDB` |
| WAITING → SKIPPED | No subscribers qualify (PreExecCheck all failed) | `SkipActivity("4")` |
| ACTIVE → COMPLETED | `IntraActivitySequencing.ActionResponseEvent(currActivity)` returns true | `return "true"` |

> **IntraActivitySequencing:** Requests are queued in order and dispatched one at a time. Each response triggers the next queued request (or signals completion when all done).

---

## §13 Exception Handling

| Condition | Action |
|-----------|--------|
| Any exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §15 Function Dependency Tree

```text
Request_ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST
├── GetActivityParamValueFromKey(activity, "DEALERCODE")
├── GetActivityParameterValueFromKey(activity, "COMPANY")
├── [if resubmit] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── for each ParentOU[i] → Subscriber[iSub]
│   ├── GetXMLForSubscriber(orderRequest, subRefId)
│   ├── XPath.execute(PreExecCheck, sXML)
│   ├── [skip check] Response[].ReferenceId==subRefId AND CompletionStatus==2
│   ├── Event.createEvent("xslt://.../ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST", ...)
│   │   [COMPANY 5-way, SIM_TYPE 3-way, DEALER param/'40000001']
│   │   [Status=AVAILABLE, Type=SIM, Activity=RESERVE, PageNumber=1, PageSize=1]
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
│   └── sendEventImmediate(Logger REQ)
├── for each ParentOU[i] → ChildOU[k] → Subscriber[iSub]
│   └── (same pattern, simplified COMPANY priority — no COMPANY_OTA)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
└── HandleActivityException(...)

Response_ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST
├── OMXUtils.generateTrackingID()
├── Instance.createInstance("xslt://.../ASRM_GetURListRes")
│   → ResponseCode, ResponseMessage, CompletionStatus, ReferenceId
│   → ICCID ← payload/ns:UnifiedResourceListInfo/ns:UnifiedResourceInfoArr[1]/ns:UnifiedResourceIdInfo/ns:Value
├── currActivity.Response[n] = activityRes
├── GetActivityParamValueFromKey(currActivity, "ESIM_FLAG")
├── for each POU/ChildOU Subscriber matching activityRes.ReferenceId
│   ├── [if no ICC_ID ExtendedInfo AND ICCID not empty]
│   │   Instance.createInstance(SubscriberExtendedInfo{extId=ICCID:ICC_ID, Name=ICC_ID, Value=ICCID})
│   │   subscriber.ExtendedInfo[n] = iccId
│   └── [if ESIM_FLAG!="Y" AND no SIM ResourceInfo AND ICCID not empty]
│       Instance.createInstance(ResourceInfo{extId=SUBRI:trackingId:RefID:SIM, ResourceName=SIM, ValuesArray=ICCID})
│       subscriber.ResourceInfo[n] = sim
├── sendEventImmediate(Logger RES) — dynamic OPERATION_NAME=$currActivity/ActivityID
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → return "true"/"false"
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Fan-out: one ASRM reserve request per subscriber (POU and ChildOU) via IntraActivitySequencing |
| R2 | COMPANY resolution: 5-way priority (param > COMPANY_OTA > CompanyCode=RM > COMPANY_CODE > '06') |
| R3 | SIM_TYPE: '8' for OrderType=11020 (OTA MNP), else from ResourceInfo or default '6' |
| R4 | DEALER: from activity param DEALERCODE or default '40000001' |
| R5 | Response: write ICC_ID to Subscriber.ExtendedInfo; skip SIM ResourceInfo for eSIM (ESIM_FLAG=Y) |
| R6 | Resubmit: purge pending requests before re-queuing |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Event name (ASRM_GET_NEXT_AVAILABLE) differs from ActivityID (ASRM_GET_RESERVE) — naming divergence | [MEDIUM] | Document the mapping; ensure migration target uses same event routing |
| COMPANY_OTA only available in POU subscriber scope — ChildOU uses simplified priority | [LOW] | Verify ChildOU orders always have COMPANY_CODE or default '06' is acceptable |
| IntraActivitySequencing replaces standard fan-in — sequential not parallel | [MEDIUM] | Document as intentional for ASRM ordering; migration target must preserve sequential dispatch |
| ICCID-based extId for ICC_ID ExtendedInfo — collision risk if ICCID reused | [LOW] | ICCID is unique by design; acceptable pattern |

---

## §18 Full Source Code (abridged)

```java
// @description get SIM information from ASRM; OTA IMSI for MNP Port In OTA order
// @author chch  (OMX-2718: OTA sit type 8)
rule Rules.OMConsumers.OMXFM.Request.Request_ASRM_GET_RESERVE_UNIFIED_RESOURCE_LIST {
  attribute { priority = 5; forwardChain = true; }
  then {
    String operationName = orderCurrentActivity.ActivityID;
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      String dealerCodeValue = GetActivityParamValueFromKey(activity, "DEALERCODE");
      String company = GetActivityParameterValueFromKey(activity, "COMPANY");
      if(isActResub) IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

      // POU Subscriber loop + ChildOU Subscriber loop
      for(int i=0; i<iLen; i++) {
        for(int iSub=0; iSub<iSubCnt; iSub++) {
          // PreExecCheck → skip check → build event
          /* XSLT: ns7:UnifiedResourceListRequest
             COMPANY (5-way), SIM_TYPE (3-way), DEALER (param/'40000001')
             Status='AVAILABLE', Type='SIM', Activity='RESERVE'
             PageNumber=1, PageSize=1  — see §7, §10 */
          Event.assertEvent(reqEvent);
          IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
          isSkipped = false;
        }
      }

      if(!isSkipped) {
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
    } catch(Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
  }
}
```

## §19 Response Message Rule

### §19.1 Overview

Receives ASRM response, creates `ASRM_GetURListRes` with ICCID from first `UnifiedResourceInfoArr`. Finds the matching subscriber by RefId and writes ICC_ID ExtendedInfo (if not present) and SIM ResourceInfo (if not eSIM and not present). Drives sequencing via `IntraActivitySequencing.ActionResponseEvent`.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order — Subscriber ExtendedInfo/ResourceInfo written |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.ASRM_GET_NEXT_AVAILABLE_UNIFIED_RESOURCE_LIST` | ASRM response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[], ESIM_FLAG param read |

### §19.3 Response Concept Tree

```text
createObject (ASRM_GetURListRes)
└── object
    ├── ResponseCode     ← $eventResponse/ResponseCode                                              [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg                                               [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus                                          [Conditional]
    ├── ReferenceId      ← $eventResponse/RefID                                                     [Conditional]
    └── ICCID            ← payload/ns:UnifiedResourceListInfo/ns:UnifiedResourceInfoArr[1]
                           /ns:UnifiedResourceIdInfo/ns:Value                                        [Conditional]
```

### §19.5 Subscriber Write-back Logic

| Write Target | Guard Condition | Value |
|-------------|----------------|-------|
| `Subscriber.ExtendedInfo[ICC_ID]` | ICC_ID not exists AND ICCID not empty | ICCID from activityRes |
| `Subscriber.ResourceInfo[SIM]` | ESIM_FLAG≠"Y" AND SIM not exists AND ICCID not empty | ValuesArray=ICCID |

### §19.4 Response Completion Logic

`IntraActivitySequencing.ActionResponseEvent(currActivity)` — sends next queued request or returns `true` when all done.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
