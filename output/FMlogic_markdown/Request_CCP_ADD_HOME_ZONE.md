# Request_CCP_ADD_HOME_ZONE

> External OMXFM Rule — Adds a Home Zone to a subscriber in CCP (ZTE/zSmart BSS) using IntraActivitySequencing for sequential per-subscriber dispatch.

**Rule:** `Rules.OMConsumers.OMXFM.Request.Request_CCP_ADD_HOME_ZONE`
**Priority:** 5 | **forwardChain:** true | **Target:** CCP (ZTE/zSmart BSS) | **Transport:** JMS Sequential (IntraActivitySequencing)

---

## §1 — Overview & Purpose

Adds a Home Zone assignment to a subscriber in the **CCP (ZTE/zSmart BSS)** system. Sends a `modSubsHomeZone` request via the `CCP_MOD_SUBS_HOME_ZONE` JMS event with Action code "1" (Add), using the `igoHomeZoneCode` value from order ExtendedInfo.

Used in **PREPAID_REGISTRATION** step 7.

> **Key trait — IntraActivitySequencing:** Unlike most OMXFM rules that send subscriber requests in parallel, this FM queues requests and sends them sequentially — one at a time. On resubmit, pending requests are purged before restarting.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCP_ADD_HOME_ZONE` |
| Priority | 5 |
| forwardChain | true |
| Rule Type | External OMXFM — async JMS with IntraActivitySequencing |
| Activity ID | `CCP_ADD_HOME_ZONE` |
| Event Type Sent | `Events.OMConsumers.OMXFM.Request.CCP_MOD_SUBS_HOME_ZONE` (differs from ActivityID) |
| Target Backend | CCP — ZTE/zSmart BSS (`http://thaitrue.customization.ws.bss.zsmart.ztesoft.com`) |
| Response RF | `Response_CCP_ADD_HOME_ZONE.rulefunction` |
| Response Event | `Events.OMConsumers.OMXFM.Response.CCP_MOD_SUBS_HOME_ZONE` |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context; `ExtendedInfo[igoHomeZoneCode]` read for payload |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity state; managed by IntraActivitySequencing |

---

## §4 — Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "CCP_ADD_HOME_ZONE"
orderRequest.ProcessFlow.NextActivityID == "CCP_ADD_HOME_ZONE"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 — Execution Flow Diagram

1. Set `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. If resubmit: `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
3. Loop ParentOU → loop Subscriber[ps]
4. Check Response[] for RefId==pSubRefId + CompletionStatus==2 → skip if found
5. Evaluate PreExecCheck XPath if present → skip if "false"
6. Build `CCP_MOD_SUBS_HOME_ZONE` event via XSLT; Action="1", HomeZoneCode from `igoHomeZoneCode`
7. `Event.assertEvent(reqEvent)` (add to BE working memory)
8. `IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)` (queue)
9. If `AllowWriteLog(OrderType)`: send audit Logger event
10. Loop ChildOU → same logic
11. `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)` (dispatch first in queue)
12. Status = "1" IN_PROGRESS + `SendDataToDB`; or `SkipActivity("4")`
13. Exception → `HandleActivityException`

---

## §6 — Rule Action Detail

**IntraActivitySequencing pattern:** All subscriber requests are queued, then only the first is dispatched. Each subsequent request fires only after the prior response is processed by `ActionResponseEvent` in the response RF.

**Resubmit:** `PurgePendingRequestsBeforeResubmit` clears stale queued events before re-queuing.

**Audit:** Correctly gated by `AllowWriteLog(OrderType)` — consistent with standard OMXFM pattern.

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Used in **PREPAID_REGISTRATION** step 7. No order type filter in rule. ProcessConfig PreExecCheck gates on home zone data availability.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel/Destination | Purpose |
|-----------|--------------------|---------| 
| [OUTBOUND JMS] | `/Events/OMConsumers/OMXFM/Request/CCP_MOD_SUBS_HOME_ZONE` | Send modSubsHomeZone to CCP |
| [INBOUND JMS] | `/Events/OMConsumers/OMXFM/Response/CCP_MOD_SUBS_HOME_ZONE` | Receive CCP response |
| [LOG] | `/Events/OMConsumers/OMXESB/Logger` | Audit (AllowWriteLog gated) |

### §8.3 Backend API Details

| System | Operation | Namespace | Protocol |
|--------|-----------|-----------|---------|
| CCP (ZTE/zSmart BSS) | `modSubsHomeZone` | `http://thaitrue.customization.ws.bss.zsmart.ztesoft.com` | JMS async (sequential) |

### §8.4 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `orderCurrentActivity.Status` | WRITE | IN_PROGRESS or SKIP |
| `orderCurrentActivity.Response[]` | READ/WRITE | Prior success check; ResponseBase appended |
| `orderRequest.OrderData.ExtendedInfo[igoHomeZoneCode]` | READ | Home zone code for CCP |
| `psub.MSISDN` / `csub.MSISDN` | READ | Subscriber MSISDN for payload |
| `psub.RefId` / `csub.RefId` | READ | RefId for response correlation |

### §8.5 ExtendedInfo Fields Required

| Name | Required | Usage |
|------|----------|-------|
| `igoHomeZoneCode` | [Required] | Mapped to `ns10:HomeZoneCode` in CCP request |

### §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | If "true", include UserName/PassWord |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `OMX_OM/WritePayload` | If "true", include payload in audit |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Parameter | ParentOU | ChildOU | Bound From |
|-----------|----------|---------|------------|
| `orderRequest` | ✓ | ✓ | Working memory |
| `pSubRefId` | ✓ | — | `psub.RefId` |
| `cSubRefId` | — | ✓ | `csub.RefId` |
| `psub` | ✓ | — | ParentOU.Subscriber[ps] |
| `csub` | — | ✓ | ChildOU.Subscriber[cs] |
| `globalVariables` | ✓ | ✓ | BE Global Variables |

### §9.3 JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | If present |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | If present |
| `OrderID` | `$orderRequest/OrderData/OrderID` | If present |
| `RefID` | `$pSubRefId` / `$cSubRefId` | Always (= psub/csub.RefId) |
| `UserName` | `$orderRequest/OrderData/User` | IsEnableUserPass="true" AND User present |
| `PassWord` | `$orderRequest/OrderData/Password` | IsEnableUserPass="true" AND Password present |
| `OrderType` | `$orderRequest/OrderData/OrderType` | If present |

### §9.4 Payload Root

Namespace: `ns10 = http://thaitrue.customization.ws.bss.zsmart.ztesoft.com`

```xml
<ns10:modSubsHomeZone>
  <ns10:ModSubsHomeZoneReqDto>
    <ns10:MSISDN>0812345678</ns10:MSISDN>
    <ns10:UserPwd/>                        <!-- always empty -->
    <ns10:SubsHomeZoneChgDtoList>
      <ns10:SubsHomeZoneChgDto>
        <ns10:Action>1</ns10:Action>       <!-- static: Add -->
        <ns10:EffDate/>                    <!-- always empty -->
        <ns10:ExpDate/>                    <!-- always empty -->
        <ns10:HomeZoneCode>BKK001</ns10:HomeZoneCode>  <!-- from igoHomeZoneCode -->
      </ns10:SubsHomeZoneChgDto>
    </ns10:SubsHomeZoneChgDtoList>
    <ns10:RequestID/>                      <!-- always empty -->
  </ns10:ModSubsHomeZoneReqDto>
</ns10:modSubsHomeZone>
```

### §9.8 XSLT Stylesheet Source

**Variant ① — ParentOU Subscriber** (params: `orderRequest`, `pSubRefId`, `globalVariables`, `psub`):

```xml
<xsl:stylesheet xmlns:ns10="http://thaitrue.customization.ws.bss.zsmart.ztesoft.com" version="1.0">
  <xsl:template match="/">
    <createEvent><event>
      <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      <RefID><xsl:value-of select="$pSubRefId"/></RefID>
      <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      <payload>
        <ns10:modSubsHomeZone>
          <ns10:ModSubsHomeZoneReqDto>
            <ns10:MSISDN><xsl:value-of select="$psub/MSISDN"/></ns10:MSISDN>
            <ns10:UserPwd><xsl:value-of select='""'/></ns10:UserPwd>
            <ns10:SubsHomeZoneChgDtoList>
              <ns10:SubsHomeZoneChgDto>
                <ns10:Action><xsl:value-of select='"1"'/></ns10:Action>
                <ns10:EffDate><xsl:value-of select='""'/></ns10:EffDate>
                <ns10:ExpDate><xsl:value-of select='""'/></ns10:ExpDate>
                <ns10:HomeZoneCode>
                  <xsl:value-of select='$orderRequest/OrderData/ExtendedInfo[Name="igoHomeZoneCode"]/Value'/>
                </ns10:HomeZoneCode>
              </ns10:SubsHomeZoneChgDto>
            </ns10:SubsHomeZoneChgDtoList>
            <ns10:RequestID><xsl:value-of select='""'/></ns10:RequestID>
          </ns10:ModSubsHomeZoneReqDto>
        </ns10:modSubsHomeZone>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**Variant ② — ChildOU Subscriber**: Identical; `pSubRefId` → `cSubRefId`, `psub` → `csub`.

---

## §10 — XSLT Field Mapping — Output XML Tree

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                  [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId        [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID              [Conditional]
    ├── RefID                ← $pSubRefId (= psub.RefId)                   [Always]
    ├── UserName             ← $orderRequest/OrderData/User                 [Credential-gated]
    ├── PassWord             ← $orderRequest/OrderData/Password             [Credential-gated]
    ├── OrderType            ← $orderRequest/OrderData/OrderType            [Conditional]
    └── payload                                                             [Always]
        └── ns10:modSubsHomeZone
            └── ns10:ModSubsHomeZoneReqDto
                ├── ns10:MSISDN        ← $psub/MSISDN                      [Always]
                ├── ns10:UserPwd       ← ""                                [Always (empty)]
                ├── ns10:SubsHomeZoneChgDtoList
                │   └── ns10:SubsHomeZoneChgDto
                │       ├── ns10:Action       ← "1"                        [Always (static: Add)]
                │       ├── ns10:EffDate      ← ""                         [Always (empty)]
                │       ├── ns10:ExpDate      ← ""                         [Always (empty)]
                │       └── ns10:HomeZoneCode ← ExtendedInfo[igoHomeZoneCode]/Value [Always]
                └── ns10:RequestID     ← ""                                [Always (empty)]
```

---

## §11 — Audit Logging

| Field | Request | Response |
|-------|---------|---------|
| Gate | `AllowWriteLog(OrderType)` | `AllowWriteLog(OrderType)` |
| `PROCESS_ID` | `concat($pid,"_REQ")` | `concat($pid,"_RES")` |
| `OPERATION_NAME` | `"CCP_ADD_HOME_ZONE"` | `"CCP_ADD_HOME_ZONE "` ← trailing space bug |
| `AUDIT_TRACE` | `"Request Sent for CCP_ADD_HOME_ZONE"` | `"Response received for CCP_ADD_HOME_ZONE "` ← trailing space bug |
| `payload` | Copy of `$reqEvent` if WritePayload="true" | Copy of `$eventResponse` if WritePayload="true" |

---

## §12 — Activity Status Management

| Condition | Status | Helper Call |
|-----------|--------|-------------|
| At least one subscriber queued | "1" IN_PROGRESS | `SendFirstRequestEvent` + `GetActivityStatusString("1",false)` + `SendDataToDB` |
| All skipped | "4" SKIP | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception | ERROR | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §14 — Helper Functions Reference

| Function | Scope | Purpose |
|----------|-------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | ACTION | Clear queue on resubmit |
| `IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)` | ACTION | Queue for sequential dispatch |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | ACTION | Dispatch first queued request |
| `IntraActivitySequencing.ActionResponseEvent(activity)` | ACTION | Response: dispatch next, return true when all done |
| `AllowWriteLog(orderType)` | ACTION | Gate for audit logging |
| `GetXMLForSubscriber(orderRequest, refId)` | ACTION | Serialize subscriber for XPath evaluation |
| `GetXMLForSubscriberInChildOU(orderRequest, refId, ouRefId)` | ACTION | Same for ChildOU |
| `GetActivityStatusString(code, flag)` | ACTION | "1" → IN_PROGRESS |
| `SendDataToDB(orderRequest)` | ACTION | Persist state |
| `SkipActivity(orderRequest, activity, code)` | ACTION | Mark skipped |
| `HandleActivityException(orderRequest, activity, ex, ctx)` | ACTION | Error handling |

---

## §15 — Function Dependency Tree

```text
Request_CCP_ADD_HOME_ZONE (rule)
├── Instance.getByExtIdByUri()
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()  [resubmit]
├── RuleFunctions.Helpers.GetXMLForSubscriber()
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU()
├── XPath.execute()                            [PreExecCheck]
├── Event.createEvent("xslt://...")            [Build CCP_MOD_SUBS_HOME_ZONE event]
├── Event.assertEvent()
├── IntraActivitySequencing.ActionRequestEvent()
├── AllowWriteLog() → Event.Ext.sendEventImmediate(Logger)
├── IntraActivitySequencing.SendFirstRequestEvent()
├── RuleFunctions.Helpers.GetActivityStatusString()
├── RuleFunctions.Helpers.SendDataToDB()
├── RuleFunctions.Helpers.SkipActivity()
└── RuleFunctions.Helpers.HandleActivityException()

Response_CCP_ADD_HOME_ZONE (rulefunction)
├── Instance.createInstance("xslt://...")     [Build ResponseBase]
├── AllowWriteLog() → Event.Ext.sendEventImmediate(Logger)
└── IntraActivitySequencing.ActionResponseEvent()  [Fan-in / dispatch next]
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Send CCP `modSubsHomeZone` with Action="1" (Add) for each subscriber |
| R2 | Map `ExtendedInfo[igoHomeZoneCode]` to `ns10:HomeZoneCode` |
| R3 | Process subscribers sequentially via IntraActivitySequencing |
| R4 | On resubmit: purge queue before re-queuing |
| R5 | Gate audit on `AllowWriteLog(OrderType)` |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Sequential processing — queue stops on first failure | [MEDIUM] | Verify if per-subscriber failure isolation needed |
| ZTE/zSmart BSS namespace — tight CCP coupling | [MEDIUM] | Abstract via service layer in modernization |
| `igoHomeZoneCode` must be in ExtendedInfo — no fallback | [MEDIUM] | Add validation or default |
| Trailing space in response audit OPERATION_NAME/AUDIT_TRACE | [LOW] | Fix string literals in response RF |

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCP_ADD_HOME_ZONE {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CCP_ADD_HOME_ZONE";
    orderRequest.ProcessFlow.NextActivityID == "CCP_ADD_HOME_ZONE";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      if(isActResub) {
        RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      }
      // ParentOU + ChildOU loop: build CCP_MOD_SUBS_HOME_ZONE event (§9.8)
      // Event.assertEvent(reqEvent) → ActionRequestEvent(reqEvent, orderCurrentActivity)
      // AllowWriteLog gate → audit Logger event
      if (!isSkipped) {
        RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
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

### §19.1 Overview

Standard ResponseBase handler using **IntraActivitySequencing** for fan-in. `ActionResponseEvent` marks the response processed, dispatches the next queued request if any, and returns `true` when all subscribers are done.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | For audit log |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCP_MOD_SUBS_HOME_ZONE` | CCP response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; sequencing state |

### §19.3 ResponseBase Construction

```text
createObject
└── object
    ├── extId           ← OMXUtils:generateTrackingID()     [Always]
    ├── ResponseCode    ← $eventResponse/ResponseCode        [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg         [Conditional]
    ├── CompletionStatus← $eventResponse/CompletionStatus    [Conditional]
    └── ReferenceId     ← $eventResponse/RefID               [Conditional]
```

### §19.4 Response Completion Logic

| Expression | Value |
|------------|-------|
| Fan-in mechanism | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Returns "true" | All queued subscriber requests completed |
| Returns "false" | More remain; next dispatched automatically |

> Unlike standard OMXFM RFs, does **not** use `count(Response[...="000"]) == RequestCount`. Completion is managed entirely by IntraActivitySequencing.

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| Gate | `AllowWriteLog(orderRequest.OrderData.OrderType)` |
| `PROCESS_ID` | `concat($pid,"_RES")` |
| `OPERATION_NAME` | `"CCP_ADD_HOME_ZONE "` ← trailing space |
| `AUDIT_TRACE` | `"Response received for CCP_ADD_HOME_ZONE "` ← trailing space |
| `payload` | Copy of `$eventResponse` if WritePayload="true" |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
