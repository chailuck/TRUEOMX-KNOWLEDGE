# Request_CCBS_SUSPEND_SUBS

> TIBCO BusinessEvents FM — CCBS Suspend Subscriber per-subscriber dual-loop request

**Priority:** 5 | **forwardChain:** true | **Author:** awalia-t420 | **Backend:** CCBS

---

## §1 — Overview & Purpose

Fires when `orderCurrentActivity.ActivityID == "CCBS_SUSPEND_SUBS"` and status is WAITING. Loops over all ParentOU and ChildOU subscribers, applies the PreExecCheck XPath against each subscriber's XML, and fires an individual `CCBS_SUSPEND_SUBS` JMS event to the CCBS back-end for each qualifying subscriber.

The request carries the subscriber number, an optional effective date, and an activity reason (defaulting to `"CREQ"`). Completion uses `IntraActivitySequencing.ActionResponseEvent` fan-in (the manual `count(Response[suffix"000"]) == RequestCount` block is commented out in source).

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_SUSPEND_SUBS` |
| Rule file | `Request_CCBS_SUSPEND_SUBS.rule` |
| Priority | 5 |
| forwardChain | true |
| Author | awalia-t420 |
| Resubmit support | Yes — `PurgePendingRequestsBeforeResubmit` when `isActResub=true` |
| Loop strategy | Dual-loop: ParentOU.Subscriber + ParentOU.ChildOU.Subscriber |
| RefId granularity | Per subscriber (`Subscriber[j].RefId`) |

---

## §3 — Working Memory

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Order context — subscribers, channel, tracking ID, EffectiveDate |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Current FM activity |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_SUSPEND_SUBS"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_SUSPEND_SUBS"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow

1. Detect resubmit flag (`isActResub`)
2. Load `logicalDateRes`
3. Outer loop: ParentOU[i]
4. Inner loop: Subscriber[j] → check already-completed response; apply PreExecCheck; fire CCBS event
5. Inner loop: ChildOU[k] → Subscriber[j] → same via ChildOU XML helper
6. If any request fired: `SendFirstRequestEvent` → status "1" → persist DB
7. If all skipped: `SkipActivity("4")`
8. Catch block → `HandleActivityException`

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS Channel

| Direction | Event | Destination | Schema |
|-----------|-------|-------------|--------|
| [OUTBOUND] | CCBS_SUSPEND_SUBS | CCBS SuspendSubscriber JMS | SuspendSubscriberRequest (ns1: tibco.com/schemas/OMX-COMMON) |
| [LOG] | OMXESB/Logger | Audit log | AuditLogging/V1_0 |

### §8.4 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `orderRequest.OrderData.OMXTrackingId` | READ | JMSCorrelationID |
| `Subscriber.SubscriberId` | READ | subscrNumber in payload |
| `OrderData.EffectiveDate` | READ | activityDate (conditional) |
| `SubscriberActivityInfo.ActivityReason` | READ | defaults to "CREQ" if absent/blank |
| `SubscriberActivityInfo.UserText` | READ | userText in payload |
| `orderCurrentActivity.Status` | WRITE | Set to "1" on dispatch |

### §8.6 Global Variables

| Path | Usage |
|------|-------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Gate for UserName/PassWord |
| `$globalVariables/OMX_OM/WritePayload` | Gate for audit payload copy |

---

## §9 — Detailed Payload Build

### §9.7 Generated XML Example

```xml
<createEvent>
  <event>
    <JMSCorrelationID>TRK-20250101-001</JMSCorrelationID>
    <OrderID>ORD-12345</OrderID>
    <RefID>REF-SUB-001</RefID>
    <payload>
      <ns1:SuspendSubscriberRequest>
        <ns1:subscriberIdInfo>
          <ns1:subscrNumber>0812345678</ns1:subscrNumber>
        </ns1:subscriberIdInfo>
        <ns1:activityDateInfo>                            <!-- if EffectiveDate present -->
          <ns1:activityDate>2025-10-01T00:00:00+07:00</ns1:activityDate>
        </ns1:activityDateInfo>
        <ns1:ActivityInfo>
          <ns1:activityReason>MANSU</ns1:activityReason> <!-- or "CREQ" default -->
          <ns1:userText>Manual suspension</ns1:userText>
        </ns1:ActivityInfo>
      </ns1:SuspendSubscriberRequest>
    </payload>
  </event>
</createEvent>
```

---

## §10 — XSLT Field Mapping Tree

```text
createEvent
└── event
    ├── JMSPriority              ← $orderRequest/OrderPriority        [Conditional]
    ├── JMSCorrelationID         ← OMXTrackingId                      [Conditional]
    ├── OrderID                  ← OrderData/OrderID                   [Conditional]
    ├── RefID                    ← $refId (Subscriber[j].RefId)        [Always]
    ├── UserName                 ← OrderData/User                      [Conditional: IsEnableUserPass='true']
    ├── PassWord                 ← OrderData/Password                  [Conditional: IsEnableUserPass='true']
    ├── OrderType                ← OrderData/OrderType                 [Conditional]
    └── payload
        └── ns1:SuspendSubscriberRequest
            ├── ns1:subscriberIdInfo
            │   └── ns1:subscrNumber ← ParentOU[i+1]/Subscriber[j+1]/SubscriberId  [Always]
            ├── ns1:activityDateInfo [Conditional: string-length(tib:trim(EffectiveDate))>0]
            │   └── ns1:activityDate ← OrderData/EffectiveDate
            └── ns1:ActivityInfo
                ├── ns1:activityReason ← SubscriberActivityInfo/ActivityReason  [Always; default "CREQ"]
                └── ns1:userText       ← SubscriberActivityInfo/UserText        [Always]
```

Legend: `← XPath source` | static literal (orange in HTML) | *Conditional* (purple italic)

---

## §12 — Activity Status Management

| Condition | Status |
|-----------|--------|
| At least one request sent | `GetActivityStatusString("1", false)` → WAITING_RESPONSE |
| All subscribers skipped | `SkipActivity(reason="4")` → SKIPPED |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_SUSPEND_SUBS
├── RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit
├── RuleFunctions.Helpers.GetXMLForSubscriber
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU
├── XPath.execute (PreExecCheck)
├── Event.createEvent (CCBS_SUSPEND_SUBS XSLT × 2 variants)
├── RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent
├── Event.Ext.sendEventImmediate (audit logger)
├── RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent
├── RuleFunctions.Helpers.GetActivityStatusString
├── RuleFunctions.Helpers.SendDataToDB
├── RuleFunctions.Helpers.SkipActivity
└── RuleFunctions.Helpers.HandleActivityException
```

---

## §19 — Response Message Rule

### §19.1 Overview

`Response_CCBS_SUSPEND_SUBS` receives `CCBS_SUSPEND_SUBS` response, builds `CCBSSuspendSubsRes` concept, appends to `currActivity.Response[]`, sends audit, and calls `IntraActivitySequencing.ActionResponseEvent` for fan-in.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Order context |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.CCBS_SUSPEND_SUBS | Inbound response |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Fan-in target |

### §19.3 ResponseBase Concept (CCBSSuspendSubsRes)

```text
CCBSSuspendSubsRes
├── extId            ← OMXUtils.generateTrackingID()      [Always]
├── ResponseCode     ← $eventResponse/ResponseCode        [Conditional]
├── ResponseMessage  ← $eventResponse/ResponseMsg         [Conditional]
├── CompletionStatus ← $eventResponse/CompletionStatus    [Conditional]
└── ReferenceId      ← $eventResponse/RefID               [Conditional]
```

### §19.4 Fan-in Completion

Uses `IntraActivitySequencing.ActionResponseEvent(currActivity)`. The explicit `count(Response[tib:right(tib:trim(ResponseCode),3)="000"]) == RequestCount` block is **commented out** in source.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
