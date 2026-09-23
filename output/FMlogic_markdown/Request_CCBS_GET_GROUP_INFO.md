# Request_CCBS_GET_GROUP_INFO

## §1 Overview & Purpose

**CCBS_GET_GROUP_INFO** retrieves Closed User Group (CUG) information from CCBS for each offer entity in the order that carries a **CUG ID** parameter. Used during ACTIVATION to populate CUG details (GroupId, GroupName, GroupType, GroupDescription) for subscribers or agreement offers requesting group membership.

The rule traverses four nested scopes to find entities with "CUG ID" ParameterInfo:
1. ParentOU → Subscriber → SubscriberOffers with CUG ID
2. ParentOU → ChildOU → Subscriber → SubscriberOffers with CUG ID
3. ParentOU → Agreement → Offers with CUG ID
4. ParentOU → ChildOU → Agreement → Offers with CUG ID

> **Fan-in note:** Response rulefunction uses `RequestCount == Response@length` (total response count), NOT the standard "000" success-count check. A failed response still counts toward completion.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_GROUP_INFO` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS |
| Send pattern | Fan-out — `sendEventImmediate` per CUG-bearing entity |
| Fan-in | `RequestCount == Response@length` (response count, not "000" check) |
| Response concept | `Concepts.FM.Response.CCBS_GetGroupInfoRes` |
| Response rulefunction | `Response_CCBS_GET_GROUP_INFO` |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — all POU/ChildOU subscriber offers and agreement offers scanned for CUG ID |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | PreExecCheck, RequestCount, Response[] (skip check) |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_GET_GROUP_INFO"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_GROUP_INFO"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Check resubmit; capture `chkXPath = orderCurrentActivity.PreExecCheck`
2. **Loop 1** POU Subscriber Offers: if CUG ID count > 0 AND PreExecCheck passes AND not completed → send, `RequestCount++`
3. **Loop 2** ChildOU Subscriber Offers: same pattern, PreExecCheck via `GetXMLForSubscriberInChildOU`
4. **Loop 3** POU Agreement Offers: same pattern, PreExecCheck via `GetXMLForAgreement`
5. **Loop 4** ChildOU Agreement Offers: same pattern, PreExecCheck via `GetXMLForAgreementInChildOU`
6. `SendDataToDB(orderRequest)` after all loops
7. If any sent: `Status = GetActivityStatusString("1", false)` + `SendDataToDB`
8. If none sent: `SkipActivity("4")`

---

## §8 System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event Type | Protocol |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_GET_GROUP_INFO` | JMS / sendEventImmediate (1 per CUG entity) |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_GET_GROUP_INFO` | JMS response per entity |

### §8.3 Backend API

| System | Operation | Schema |
|--------|-----------|--------|
| CCBS | getGroupInfo | `http://www.tibco.com/schemas/ProxyServiceWithEJB/BusinessProcess/CCBS_UserGroupServices/schema/getGroupInfo.xsd` |

### §8.4 PreExecCheck Helpers

| Scope | Helper |
|-------|--------|
| POU Subscriber | `GetXMLForSubscriber(orderRequest, refId)` |
| ChildOU Subscriber | `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` |
| POU Agreement | `GetXMLForAgreement(orderRequest, refId)` |
| ChildOU Agreement | `GetXMLForAgreementInChildOU(orderRequest, refId, pouRefId)` |

---

## §9 Request Payload Tree (all 4 variants share same structure)

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority              [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId    [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID           [Conditional]
    ├── RefID                ← Subscriber/RefId or Agreement/RefId       [Conditional: scope-specific]
    ├── UserName             ← $orderRequest/OrderData/User              [Credential-gated: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password          [Credential-gated: IsEnableUserPass='true']
    ├── OrderType            ← $orderRequest/OrderData/OrderType         [Conditional]
    ├── CES                  ← $orderRequest/OrderData/CES               [Conditional]
    └── payload
        └── ns1:getGroupInfo
            └── ns1:UserGroupIdInfo
                └── ns:GroupId ← ParameterInfo[ParamName="CUG ID"]/ValuesArray  [Conditional: CUG ID exists]
```

---

## §11 Audit Logging

| Loop | OPERATION_NAME | AUDIT_TRACE |
|------|----------------|-------------|
| POU Subscriber | `"CCBS_GET_GROUP_INFO"` (hardcoded) | `concat("Request Sent for RefId ", $refId)` |
| ChildOU Subscriber | `"CCBS_GET_GROUP_INFO"` (hardcoded) | Request Sent for CCBS_GET_GROUP_INFO |
| POU/ChildOU Agreement | `$orderCurrentActivity/ActivityID` (dynamic) | `concat("Request Sent for ", ActivityID)` |
| Response | `$currActivity/ActivityID` (dynamic) | `concat("Response received for ", ActivityID)` |

> **Inconsistency:** POU subscriber loop hardcodes `OPERATION_NAME`; agreement loops use dynamic value.

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → ACTIVE | At least one CUG request sent | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| WAITING → SKIPPED | No CUG ID entities found / all PreExecCheck failed | `SkipActivity("4")` |
| ACTIVE → COMPLETED | `RequestCount == Response@length` | `return "true"` |

> **Non-standard fan-in:** Uses total response count, not success count. A CCBS error still triggers completion.

---

## §13 Exception Handling

| Condition | Action |
|-----------|--------|
| Any exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §15 Function Dependency Tree

```text
Request_CCBS_GET_GROUP_INFO
├── for each POU[i] → Subscriber[j] → SubscriberOffers[k]
│   ├── XPath.evalAsInt(count CUG ID params, i,j,k)
│   ├── GetXMLForSubscriber(orderRequest, refId)
│   ├── XPath.execute(PreExecCheck, sXML)
│   ├── [skip check] Response[].ReferenceId==refId AND CompletionStatus==2
│   └── sendEventImmediate(reqEvent) + Logger REQ
├── for each POU[i] → ChildOU[x] → Subscriber[y] → SubscriberOffers[z]
│   ├── XPath.evalAsInt(count CUG ID params, i,x,y,z)
│   ├── GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)
│   └── sendEventImmediate(reqEvent) + Logger REQ
├── for each POU[i] → Agreement → Offers[m]
│   ├── XPath.evalAsInt(count CUG ID params, i,m)
│   ├── GetXMLForAgreement(orderRequest, refId)
│   └── sendEventImmediate(reqEvent) + Logger REQ
├── for each POU[i] → ChildOU[m] → Agreement → Offers[l]
│   ├── XPath.evalAsInt(count CUG ID params, i,m,l)
│   ├── GetXMLForAgreementInChildOU(orderRequest, refId, pouRefId)
│   └── sendEventImmediate(reqEvent) + Logger REQ
├── SendDataToDB(orderRequest)
├── GetActivityStatusString("1", false)
└── HandleActivityException(...)

Response_CCBS_GET_GROUP_INFO
├── OMXUtils.generateTrackingID()
├── Instance.createInstance("xslt://.../CCBS_GetGroupInfoRes")
│   → ResponseCode, ResponseMessage, CompletionStatus, ReferenceId
│   → GroupDescription, GroupId, GroupName, GroupType from payload
├── currActivity.Response[n] = activityRes
├── sendEventImmediate(Logger RES) — dynamic OPERATION_NAME=$currActivity/ActivityID
└── if(RequestCount == Response@length) return "true"
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Fan-out: one CCBS request per entity with "CUG ID" ParameterInfo |
| R2 | Skip entities with existing CompletionStatus=2 response |
| R3 | Per-entity PreExecCheck via scope-appropriate helper |
| R4 | Traverse all 4 scopes: POU Sub Offers, ChildOU Sub Offers, POU Agree Offers, ChildOU Agree Offers |
| R5 | Response: GroupDescription, GroupId, GroupName, GroupType |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Fan-in uses Response@length not success count — errors trigger completion | [MEDIUM] | Use success-count fan-in in migration target |
| Audit log inconsistency across loop types | [LOW] | Standardise to dynamic ActivityID |
| O(n⁴) nested loop complexity | [MEDIUM] | Profile with realistic order data |
| SendDataToDB called twice (loop start + end) — potential redundancy | [LOW] | Review and remove intermediate call |

---

## §18 Full Source Code (abridged)

```java
// @author awalia-t420
// 188-line rule with 4 nested loop patterns
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_GROUP_INFO {
  attribute { priority = 5; forwardChain = true; }
  then {
    try {
      // Loop 1: POU → Subscriber → SubscriberOffers with "CUG ID"
      for(int i=0; i<iPOULen; i++) {
        for(int j=0; j<iSubscriberLen; j++) {
          for(int k=0; k<iSubOffLen; k++) {
            int iCntCUGParams = XPath.evalAsInt(/* count CUG ID params */);
            if(chkRes=="true" && iCntCUGParams>0 && !reqSuccess) {
              /* XSLT: ns1:getGroupInfo → ns:GroupId = CUG ID ValuesArray — see §9, §10 */
              Event.Ext.sendEventImmediate(reqEvent); RequestCount++; isSkipped=false;
            }
          }
        }
      }
      // Loop 2,3,4: same pattern for ChildOU subscribers, POU/ChildOU Agreement offers
      SendDataToDB(orderRequest);
      if(!isSkipped) { Status = GetActivityStatusString("1", false); SendDataToDB(orderRequest); }
      else { SkipActivity(orderRequest, orderCurrentActivity, "4"); }
    } catch(Exception ae) { HandleActivityException(orderRequest, orderCurrentActivity, ae, ""); }
  }
}
```

## §19 Response Message Rule

### §19.1 Overview
Receives CCBS response per CUG entity, creates `CCBS_GetGroupInfoRes` with CUG details.
Fan-in: `RequestCount == Response@length`.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order (read only) |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_GET_GROUP_INFO` | CCBS response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[] appended |

### §19.3 Response Concept Tree

```text
createObject (CCBS_GetGroupInfoRes)
└── object
    ├── @extId            ← OMXUtils:generateTrackingID()                                   [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode                                     [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg                                      [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus                                 [Conditional]
    ├── ReferenceId       ← $eventResponse/RefID                                            [Conditional]
    ├── GroupDescription  ← payload/ns1:getGroupInfoResponse/ns1:getGroupInfoReturn/ns:GroupDescription [Conditional]
    ├── GroupId           ← payload/.../ns:GroupId                                          [Conditional]
    ├── GroupName         ← payload/.../ns:GroupName                                        [Conditional]
    └── GroupType         ← payload/.../ns:GroupType                                        [Conditional]
```

### §19.4 Response Completion Logic

Fan-in: `currActivity.RequestCount == currActivity.Response@length` → `return "true"`

> Does NOT use `successResponseCount` ("000" check). Any response triggers completion when all received.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
