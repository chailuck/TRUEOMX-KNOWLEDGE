# Request_CCBS_APPLY_COLL_ACTIVITIES

> TIBCO BusinessEvents FM — CCBS Apply Collection Activities (multi-service-type, dual-loop)

**Priority:** 5 | **forwardChain:** true | **Author:** awalia-t420 | **Backend:** CCBS

---

## §1 — Overview & Purpose

Fires when `ActivityID == "CCBS_APPLY_COLL_ACTIVITIES"`. Loops over all ParentOU and ChildOU subscribers, applies PreExecCheck per subscriber, and fires `CCBS_APPLY_COLL_ACTIVITIES` JMS event for each qualifying subscriber. The payload varies based on `serviceType` parameter (from `Parameter[0]`).

**In FULL_SUSPEND context:** serviceType=`FULL_SUSPEND` → `collectionAct=83`, removes SOC `50412`. Triggered only when `Channel="CCBS"`.

Fan-in uses `IntraActivitySequencing.ActionResponseEvent` (manual count commented out).

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_APPLY_COLL_ACTIVITIES` |
| Priority / forwardChain | 5 / true |
| Author | awalia-t420 |
| serviceType source | `orderCurrentActivity.Parameter[0]` |
| Loop | Dual: ParentOU.Subscriber + ChildOU.Subscriber |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_APPLY_COLL_ACTIVITIES"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_APPLY_COLL_ACTIVITIES"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §7 — serviceType Routing Table

| serviceType (Parameter[0]) | collectionAct | SOC Operation | SOC Code |
|---------------------------|---------------|---------------|----------|
| `FULL_SUSPEND` | 83 | offersToRemove | 50412 |
| `SOFT_SUSPEND` | 71 | offersToAdd | 50412 |
| `RESTORE` | 82 | offersToRemove | 50412 |
| `CANCEL` | 67 | (none) | — |
| default (OrderType=13) | 67 | (none) | — |
| default (OrderType=18) | 83 | offersToRemove | 50412 |
| default (other) | 83 | offersToRemove | 50412 |

---

## §9 — Payload (FULL_SUSPEND variant)

```xml
<ns:applyCollectionActivitiesRequest>
  <ns:basicAgreementCollectionInfo>
    <ns:entityIdInfo>
      <ns:entityId>SUB-ID-001</ns:entityId>
      <ns:entityType>SUBSCRIBER</ns:entityType>
    </ns:entityIdInfo>
    <ns:collectionActivityInfo>
      <ns:collectionAct>83</ns:collectionAct>
    </ns:collectionActivityInfo>
    <ns:offersToRemove>
      <ns:soc>50412</ns:soc>
    </ns:offersToRemove>
  </ns:basicAgreementCollectionInfo>
  <ns:activityInfo>
    <ns:activityReason>COLL</ns:activityReason>
    <ns:logicalDate>2025-12-01</ns:logicalDate>  <!-- if logicalDateVal present -->
  </ns:activityInfo>
</ns:applyCollectionActivitiesRequest>
```

---

## §10 — XSLT Field Mapping Tree (FULL_SUSPEND)

```text
applyCollectionActivitiesRequest
└── basicAgreementCollectionInfo
│   ├── entityIdInfo
│   │   ├── entityId    ← Subscriber[$iSubs]/SubscriberId   [Conditional]
│   │   └── entityType  ← "SUBSCRIBER"                      [Always]
│   ├── collectionActivityInfo
│   │   └── collectionAct ← 83/71/82/67 (serviceType→xsl:choose) [Always]
│   ├── offersToRemove → soc ← "50412"  [FULL_SUSPEND / RESTORE only]
│   └── offersToAdd → soc   ← "50412"  [SOFT_SUSPEND only]
└── activityInfo
    ├── activityReason ← SubscriberActivityInfo/ActivityReason  [Always]
    ├── userText       ← SubscriberActivityInfo/UserText        [Conditional]
    └── logicalDate    ← logicalDateVal  [Conditional: string-length(tib:trim(.))>0]
```

---

## §15 — Function Dependency Tree

```text
Request_CCBS_APPLY_COLL_ACTIVITIES
├── RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit
├── RuleFunctions.Helpers.GetXMLForSubscriber / GetXMLForSubscriberInChildOU
├── XPath.execute (PreExecCheck)
├── Event.createEvent (CCBS_APPLY_COLL_ACTIVITIES XSLT)
├── RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent
├── Event.Ext.sendEventImmediate (audit)
├── RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent
├── RuleFunctions.Helpers.GetActivityStatusString
├── RuleFunctions.Helpers.SendDataToDB
├── RuleFunctions.Helpers.SkipActivity
└── RuleFunctions.Helpers.HandleActivityException
```

---

## §19 — Response Message Rule

`Response_CCBS_APPLY_COLL_ACTIVITIES` maps `CCBS_APPLY_COLL_ACTIVITIES` response into `ApplyCollActivitiesRes` (ResponseCode, ResponseMessage, CompletionStatus, ReferenceId). Fan-in via `IntraActivitySequencing.ActionResponseEvent(currActivity)`. Manual count XPath is commented out.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
