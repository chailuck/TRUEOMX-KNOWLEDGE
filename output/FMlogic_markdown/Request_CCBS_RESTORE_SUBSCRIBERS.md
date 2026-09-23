# Request_CCBS_RESTORE_SUBSCRIBERS

## §1 Overview & Purpose

**CCBS_RESTORE_SUBSCRIBERS** reactivates suspended subscribers in CCBS by sending a `RestoreSubscribersRequest` for each subscriber in the POU and ChildOU hierarchy. The request carries the subscriber number, activity reason, user text, and an optional effective date.

> **Send pattern:** IntraActivitySequencing — `Event.assertEvent` + `ActionRequestEvent` + `SendFirstRequestEvent`. Fan-in: `RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)`.

> **Scope:** POU subscribers AND ChildOU subscribers (full two-level hierarchy).

> **Skip:** If PreExecCheck evaluates to false or no subscribers found → `SkipActivity("4")`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_RESTORE_SUBSCRIBERS` |
| Author | awalia-t420 |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS |
| Event type (Request) | `Events.OMConsumers.OMXFM.Request.CCBS_RESTORE_SUBSCRIBERS` |
| Event type (Response) | `Events.OMConsumers.OMXFM.Response.CCBS_RESTORE_SUBSCRIBERS` |
| Send pattern | `Event.assertEvent + ActionRequestEvent + SendFirstRequestEvent` — INTRA-ACTIVITY SEQUENCING |
| Fan-in | `RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)` |
| Iteration | POU[i].Subscriber[j] AND POU[i].ChildOU[k].Subscriber[j] |
| Resubmit | `PurgePendingRequestsBeforeResubmit` on isActResub |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity state tracker |
| `logicalDateRes` | `Concepts.OM.LogicalDate` | System logical date (loaded, not used in XSLT — dead code) |
| `nextAct` | `Concepts.OM.ProcessConfig.Activity` | Next activity config for PreExecCheck |
| `isActResub` | boolean | `RequestCount > 0 && IsOrderResubmitted` |
| `isSkipped` | boolean | Tracks whether any subscriber request was sent |
| `subNo` | String | `Subscriber.SubscriberId` (loop variable) |
| `actRsn` | String | `Subscriber.SubscriberActivityInfo.ActivityReason` (loop variable) |
| `userText` | String | `Subscriber.SubscriberActivityInfo.UserText` (loop variable) |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_RESTORE_SUBSCRIBERS"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_RESTORE_SUBSCRIBERS"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. **Resubmit check** → if `isActResub`: `PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
2. **PreExecCheck gate** → serialize `orderRequest`; evaluate XPath; if ≠ "true" → skip all
3. **POU loop** → for each `ParentOU[i].Subscriber[j]`: extract subNo/actRsn/userText → create XSLT event → `assertEvent` → `ActionRequestEvent` → fire logger → `isSkipped=false`
4. **ChildOU loop** → for each `ParentOU[i].ChildOU[k].Subscriber[j]`: same as step 3
5. **Fan-out complete** → if `!isSkipped`: `SendFirstRequestEvent` → status "1" → `SendDataToDB`; else `SkipActivity("4")`
6. **Exception** → `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §6 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| IntraActivitySequencing fan-out | Each subscriber gets `assertEvent + ActionRequestEvent` before `SendFirstRequestEvent` dispatches all |
| Two-level iteration | POU subscribers first, then ChildOU subscribers; same XSLT for both |
| subNo source | `Subscriber.SubscriberId` at both POU and ChildOU levels |
| ActivityReason + UserText | From `Subscriber.SubscriberActivityInfo.*` |
| EffectiveDate | Conditional: `OrderData.EffectiveDate` → `ns2:ActivityDate` |
| Credential gate | UserName/PassWord only when `IsEnableUserPass='true'` |
| LogicalDate dead code | Loaded but not passed to XSLT — may have been planned for EffectiveDate defaulting |

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

BN_RESTORE_SUB process — triggered when `COLLECTION_WAIVER` ExtendedInfo is present on a subscriber. No specific OrderType restriction in this FM.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event | Purpose |
|-----------|-------|---------|
| [OUTBOUND] | `CCBS_RESTORE_SUBSCRIBERS` | Restore subscriber request per subscriber |
| [LOG] | `OMXESB/Logger` | Request audit trail |

### §8.3 Backend API

| System | Operation | Schema namespace | Correlation |
|--------|-----------|-----------------|-------------|
| CCBS | RestoreSubscribers | `amdocs.csm3g.datatypes.RestoreSubscribersRequest.xsd2` | JMSCorrelationID = OMXTrackingId |

### §8.4 BE Working Memory

| Field | Access |
|-------|--------|
| `ParentOU[i].Subscriber[j].SubscriberId` | READ |
| `ParentOU[i].Subscriber[j].SubscriberActivityInfo.ActivityReason` | READ |
| `ParentOU[i].Subscriber[j].SubscriberActivityInfo.UserText` | READ |
| `ParentOU[i].ChildOU[k].Subscriber[j].*` | READ (same fields) |
| `OrderData.EffectiveDate` | READ (optional) |
| `orderCurrentActivity.Status` | WRITE → "1" |
| `orderCurrentActivity.Response[]` | WRITE (response handler) |

### §8.5 ExtendedInfo Fields Required

| Name | Required | Usage |
|------|----------|-------|
| `COLLECTION_WAIVER` | [Conditional] | PreExecCheck for downstream steps CCBS_GET_CUST_ACC_SUB_ID and CCBS_UPDATE_ACCOUNT_FIX_INFO |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Parameter | Bound from |
|-----------|-----------|
| `$orderRequest` | BE concept — full order request |
| `$globalVariables` | BE global variables |
| `$subNo` | `Subscriber.SubscriberId` (loop variable) |
| `$actRsn` | `Subscriber.SubscriberActivityInfo.ActivityReason` (loop variable) |
| `$userText` | `Subscriber.SubscriberActivityInfo.UserText` (loop variable) |

### §9.7 Complete Generated XML Example

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-20260922-001</JMSCorrelationID>
    <OrderID>ORD-12345</OrderID>
    <OrderType>BN</OrderType>
    <payload>
      <ns1:RestoreSubscribersRequest>
        <ns1:SubscriberIdInfo>
          <ns1:subscrNumber>0812345678</ns1:subscrNumber>
        </ns1:SubscriberIdInfo>
        <ns:ActivityInfo>
          <ns:ActivityReason>RESTORE</ns:ActivityReason>
          <ns:UserText>Restore after collection waiver</ns:UserText>
        </ns:ActivityInfo>
        <ns2:ActivityDateInfo>
          <ns2:ActivityDate>2026-09-22T00:00:00+07:00</ns2:ActivityDate>
        </ns2:ActivityDateInfo>
      </ns1:RestoreSubscribersRequest>
    </payload>
  </event>
</createEvent>
```

### §9.8 XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:ns1="www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.RestoreSubscribersRequest.xsd2"
  xmlns:ns="www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.ActivityInfo"
  xmlns:ns2="www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.ActivityDateInfo"
  version="1.0">
  <xsl:param name="orderRequest"/>   <!-- full order -->
  <xsl:param name="globalVariables"/>
  <xsl:param name="subNo"/>          <!-- Subscriber.SubscriberId -->
  <xsl:param name="actRsn"/>         <!-- SubscriberActivityInfo.ActivityReason -->
  <xsl:param name="userText"/>       <!-- SubscriberActivityInfo.UserText -->
  <xsl:template match="/">
    <createEvent><event>
      <!-- JMS headers -->
      <xsl:if test="$orderRequest/OrderPriority">
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderID">
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      </xsl:if>
      <!-- Credential gate -->
      <xsl:if test="$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass='true'">
        <xsl:if test="$orderRequest/OrderData/User">
          <UserName><xsl:value-of select="$orderRequest/OrderData/User"/></UserName>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/Password">
          <PassWord><xsl:value-of select="$orderRequest/OrderData/Password"/></PassWord>
        </xsl:if>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/OrderType">
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/CES">
        <CES><xsl:value-of select="$orderRequest/OrderData/CES"/></CES>
      </xsl:if>
      <payload>
        <ns1:RestoreSubscribersRequest>
          <ns1:SubscriberIdInfo>
            <ns1:subscrNumber><xsl:value-of select="$subNo"/></ns1:subscrNumber>
          </ns1:SubscriberIdInfo>
          <ns:ActivityInfo>
            <ns:ActivityReason><xsl:value-of select="$actRsn"/></ns:ActivityReason>
            <ns:UserText><xsl:value-of select="$userText"/></ns:UserText>
          </ns:ActivityInfo>
          <ns2:ActivityDateInfo>
            <!-- EffectiveDate is optional -->
            <xsl:if test="$orderRequest/OrderData/EffectiveDate">
              <ns2:ActivityDate><xsl:value-of select="$orderRequest/OrderData/EffectiveDate"/></ns2:ActivityDate>
            </xsl:if>
          </ns2:ActivityDateInfo>
        </ns1:RestoreSubscribersRequest>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority             ← $orderRequest/OrderPriority                   [Conditional]
    ├── JMSCorrelationID        ← $orderRequest/OrderData/OMXTrackingId          [Conditional]
    ├── OrderID                 ← $orderRequest/OrderData/OrderID                [Conditional]
    ├── UserName                ← $orderRequest/OrderData/User                   [Credential-gated: IsEnableUserPass='true']
    ├── PassWord                ← $orderRequest/OrderData/Password               [Credential-gated: IsEnableUserPass='true']
    ├── OrderType               ← $orderRequest/OrderData/OrderType              [Conditional]
    ├── CES                     ← $orderRequest/OrderData/CES                    [Conditional]
    └── payload
        └── ns1:RestoreSubscribersRequest                                        [Always]
            ├── ns1:SubscriberIdInfo
            │   └── ns1:subscrNumber    ← $subNo (Subscriber.SubscriberId)       [Always]
            ├── ns:ActivityInfo
            │   ├── ns:ActivityReason   ← $actRsn (ActivityReason)               [Always]
            │   └── ns:UserText         ← $userText (UserText)                   [Always]
            └── ns2:ActivityDateInfo
                └── ns2:ActivityDate    ← $orderRequest/OrderData/EffectiveDate  [Conditional]
```

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `OrderData.OMXTrackingId` [Conditional] |
| PROCESS_ID | `concat($pid, "_REQ")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `"CCBS_RESTORE_SUBSCRIBERS"` (static) |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | `MSG_LOG_LEVEL/INFO` |
| AUDIT_TRACE | `"Request Sent for CCBS_RESTORE_SUBSCRIBERS"` (static) |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload/ServicePayload | copy of reqEvent [Conditional: WritePayload="true"] |

---

## §12 Activity Status Management

| Condition | Status | Meaning |
|-----------|--------|---------|
| At least one subscriber request sent | `"1"` | In Progress / Sent |
| No subscribers / PreExecCheck false | `"4"` | Skipped |
| Exception | via `HandleActivityException` | Error |

---

## §13 Exception / Error Handling

All logic wrapped in `try/catch`. On exception: `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §15 Function Dependency Tree

```text
Request_CCBS_RESTORE_SUBSCRIBERS
├── if isActResub: PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")
├── Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")
├── [optional] Instance.serializeUsingDefaults(orderRequest) → chkRes
├── [optional] XPath.execute("/("+chkXPath+")", sXML, ns0=...) → chkRes
├── for each POU[i].Subscriber[j]:
│   ├── Event.createEvent("xslt://CCBS_RESTORE_SUBSCRIBERS", XSLT) → reqEvent
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   └── Event.Ext.sendEventImmediate(Logger event)
├── for each POU[i].ChildOU[k].Subscriber[j]:
│   └── [same as POU subscriber block]
├── if !isSkipped:
│   ├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
│   ├── GetActivityStatusString("1", false)
│   └── SendDataToDB(orderRequest)
└── else: SkipActivity(orderRequest, orderCurrentActivity, "4")

Exception path:
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| IntraActivitySequencing fan-out queues all subscribers before first dispatch — large orders delay first CCBS call | [MEDIUM] | Consider async parallel dispatch in modern runtime; document max subscriber count for BN orders |
| ActivityReason and UserText passed without validation — empty values sent silently to CCBS | [LOW] | Add mandatory-field guards at order intake; CCBS may reject blank ActivityReason |
| EffectiveDate: raw DateTime, no timezone conversion | [LOW] | Confirm CCBS expected format; add timezone normalization if required |
| LogicalDate loaded but not used — dead code | [LOW] | Remove in modern implementation or use for EffectiveDate defaulting |
| Same XSLT for POU and ChildOU — future divergence requires careful refactor | [LOW] | Document; add integration tests for both levels |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_RESTORE_SUBSCRIBERS {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CCBS_RESTORE_SUBSCRIBERS";
    orderRequest.ProcessFlow.NextActivityID == "CCBS_RESTORE_SUBSCRIBERS";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Concepts.OM.LogicalDate logicalDateRes = Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate");
      String logicalDateVal = logicalDateRes.LogicalDate;  // loaded, not used in XSLT
      Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(
          orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");

      if (isActResub)
        RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

      boolean isSkipped = true;
      String chkRes = "true";
      if (String.length(nextAct.PreExecCheck) > 0) {
        String sXML = Instance.serializeUsingDefaults(orderRequest);
        chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML,
            "ns0=www.tibco.com/be/ontology/Concepts/OrderRequest/OrderRequest");
      }

      if (String.equals(chkRes, "true")) {
        int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
        for (int i=0; i < iPOULen; i++) {
          int iSubscriberLen = orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length;
          for (int j=0; j < iSubscriberLen; j++) {
            String subNo    = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].SubscriberId;
            String actRsn   = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].SubscriberActivityInfo.ActivityReason;
            String userText = orderRequest.OrderData.Customer.ParentOU[i].Subscriber[j].SubscriberActivityInfo.UserText;
            /* Request event XSLT builds RestoreSubscribersRequest — see §9.8 */
            Events.OMConsumers.OMXFM.Request.CCBS_RESTORE_SUBSCRIBERS reqEvent = Event.createEvent("xslt://...");
            Event.assertEvent(reqEvent);
            RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
            /* Logger XSLT — see §11 */
            Event.Ext.sendEventImmediate(Event.createEvent("xslt://Logger..."));
            isSkipped = false;
          }
          // ChildOU loop — identical subscriber block per ChildOU[k]
          int iCOULen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU@length;
          for (int k=0; k < iCOULen; k++) {
            iSubscriberLen = orderRequest.OrderData.Customer.ParentOU[i].ChildOU[k].Subscriber@length;
            for (int j=0; j < iSubscriberLen; j++) {
              /* same pattern as POU subscriber block */
              isSkipped = false;
            }
          }
        }
      }

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

## §19 Response Message Rule

### §19.1 Overview

Parses the CCBS RestoreSubscribers response, creates a `CCBS_RestoreSubscribers` ResponseBase concept, appends it to `currActivity.Response[]`, fires the response audit log, and returns the fan-in completion signal.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_RESTORE_SUBSCRIBERS` | CCBS response payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity state |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object @extId ← OMXUtils.generateTrackingID()                [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode         [Always]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg          [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus     [Conditional]
    └── ReferenceId         ← $eventResponse/RefID                [Conditional]
```

### §19.4 Response Completion Logic

| Aspect | Detail |
|--------|--------|
| Fan-in function | `RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)` |
| "true" | All pending responses have ResponseCode suffix "000" — all CCBS restores succeeded |
| "false" | One or more responses still pending or have non-"000" ResponseCode |

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"CCBS_RESTORE_SUBSCRIBERS"` |
| AUDIT_TRACE | `"Response received for CCBS_RESTORE_SUBSCRIBERS"` |
| payload | copy of eventResponse [Conditional: WritePayload="true"] |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
