# Request_CCBS_UPDATE_ACCOUNT_FIX_INFO

> TIBCO BusinessEvents FM — CCBS Update Account Collection Waiver (account-level, CollectionPermanentWaiveInd)

**Priority:** 5 | **forwardChain:** true | **Author:** SathidP-PC | **Backend:** CCBS

---

## §1 — Overview & Purpose

Fires when `ActivityID == "CCBS_UPDATE_ACCOUNT_FIX_INFO"` and status is WAITING. Updates the account-level Collection Permanent Waiver indicator (`CollectionPermanentWaiveInd`) in CCBS for BN (Business Network) suspension flows.

> **⚠ Account-Level Operation:** Unlike most subscriber FMs, this FM operates at **account level**. The event `RefID` carries the **account's RefId** (`accountRefId = currSub.AccountRefId`), and the payload contains the `AccountId` resolved from the Order's Account array — not a subscriber ID.

> **⚡ Break After First Match:** The inner subscriber loop contains a `break;` statement — the FM fires **at most once per ParentOU** (on the first qualifying subscriber found). It does not iterate all subscribers.

**COLLECTION_WAIVER routing:**
- `'Y'` → `CollectionPermanentWaiveInd=89` (grant waiver) + optional `L9CollWaiverExpDate`; activityReason=`SYSREQ`
- `'N'` → `CollectionPermanentWaiveInd=78` (remove waiver); activityReason=`RW`
- other → `CollectionPermanentWaiveInd` omitted; activityReason=`CREQ`

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPDATE_ACCOUNT_FIX_INFO` |
| Rule file | `Request_CCBS_UPDATE_ACCOUNT_FIX_INFO.rule` |
| Priority | 5 |
| forwardChain | true |
| Author | SathidP-PC |
| Resubmit support | Yes — `PurgePendingRequestsBeforeResubmit` |
| Loop strategy | Dual-loop (POU + COU) with `break;` — fires at most once per POU |
| RefId granularity | **Account-level**: `currSub.AccountRefId` |
| Fan-in type | IntraActivitySequencing (`ActionResponseEvent`) |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Order context — subscribers, accounts, ExtendedInfo |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | Current FM activity |

---

## §4 — Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_UPDATE_ACCOUNT_FIX_INFO"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_UPDATE_ACCOUNT_FIX_INFO"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 — Execution Flow

1. Detect resubmit (`isActResub`); load `logicalDateRes`
2. Outer loop: ParentOU[i]
3. → Inner loop: Subscriber[j]
4. → → Skip if existing completed response for this refId (resubmit idempotency)
5. → → Apply PreExecCheck via `GetXMLForSubscriber`
6. → → If passes: resolve `accountRefId = currSub.AccountRefId`
7. → → Resolve `accountId` via XPath: `Account[RefId=$accountRefId]/AccountID`
8. → → Resolve `collectionWaiverValue`: `currSub/ExtendedInfo[Name="COLLECTION_WAIVER"]/Value`
9. → → Create and assert `CCBS_UPDATE_ACCOUNT_FIX_INFO` event; `ActionRequestEvent`; audit log
10. → → `break;` — exit inner loop (one event per POU max)
11. ChildOU.Subscriber loop: same with `GetXMLForSubscriberInChildOU` + `break;`
12. If any dispatch → `SendFirstRequestEvent`; status "1"; DB persist
13. If all skipped → `SkipActivity("4")`

---

## §7 — Business Logic: COLLECTION_WAIVER Routing

| COLLECTION_WAIVER value | CollectionPermanentWaiveInd | L9CollWaiverExpDate | activityReason |
|-------------------------|-----------------------------|---------------------|----------------|
| `'Y'` | 89 | From `ExtendedInfo[COLLECTION_WAIVER_EXPIRE_DATE]/Value` if string-length > 0 | `SYSREQ` |
| `'N'` | 78 | (not included) | `RW` |
| other / empty | (not included) | (not included) | `CREQ` |

---

## §8 — System & Integration Dependencies

### §8.2 ESB / JMS

| Direction | Event | Schema |
|-----------|-------|--------|
| `[OUTBOUND]` | CCBS_UPDATE_ACCOUNT_FIX_INFO | UpdateAccountFixInfoRequest (ns2: http://services.omx.truecorp.co.th/FMServices/UpdateAccountFixInfoRequest) |
| `[LOG]` | OMXESB/Logger | AuditLogging/V1_0 |

### §8.5 ExtendedInfo Fields Required

| Key | Required | Purpose |
|-----|----------|---------|
| COLLECTION_WAIVER | `[Required]` | Drives CollectionPermanentWaiveInd and activityReason routing |
| COLLECTION_WAIVER_EXPIRE_DATE | `[Conditional]` | L9CollWaiverExpDate — only when COLLECTION_WAIVER='Y' |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameters

| Parameter | Source |
|-----------|--------|
| orderRequest | Full order context |
| accountRefId | `currSub.AccountRefId` |
| globalVariables | Global variables tree |
| accountId | XPath: `Account[RefId=$accountRefId]/AccountID` |
| collectionWaiverValue | XPath: `currSub/ExtendedInfo[Name="COLLECTION_WAIVER"]/Value` |
| currSub | Current subscriber concept |

### §9.7 Generated XML Example (COLLECTION_WAIVER='Y')

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>TRK-20250101-001</JMSCorrelationID>
    <OrderID>ORD-12345</OrderID>
    <RefID>ACC-REF-001</RefID>              <!-- accountRefId (NOT subscriber RefId) -->
    <OrderType>18</OrderType>
    <payload>
      <ns2:UpdateAccountFixInfoRequest>
        <ns2:AccountIdInfo>
          <ns2:AccountId>ACC-ID-001</ns2:AccountId>
        </ns2:AccountIdInfo>
        <ns2:AccountCollectionFixInfo>
          <ns2:CollectionPermanentWaiveInd>89</ns2:CollectionPermanentWaiveInd>
          <ns2:L9CollWaiverExpDate>2026-12-31</ns2:L9CollWaiverExpDate>
        </ns2:AccountCollectionFixInfo>
        <ns2:ActivityInfo>
          <ns2:activityReason>SYSREQ</ns2:activityReason>
          <ns2:userText>Update CollectionPermanentWaiveInd</ns2:userText>
        </ns2:ActivityInfo>
      </ns2:UpdateAccountFixInfoRequest>
    </payload>
  </event>
</createEvent>
```

---

## §10 — XSLT Field Mapping Tree

```text
createEvent → event
├── JMSPriority              ← $orderRequest/OrderPriority                    [Conditional]
├── JMSCorrelationID         ← OMXTrackingId                                  [Conditional]
├── OrderID                  ← OrderData/OrderID                              [Conditional]
├── RefID                    ← $accountRefId (= currSub.AccountRefId)         [Always] ⚠ Account-level
├── UserName                 ← OrderData/User   [if IsEnableUserPass='true']  [Conditional]
├── OrderType                ← OrderData/OrderType                            [Conditional]
└── payload → ns2:UpdateAccountFixInfoRequest
    ├── ns2:AccountIdInfo
    │   └── ns2:AccountId    ← $accountId                                     [Always]
    ├── ns2:AccountCollectionFixInfo  [xsl:choose on $collectionWaiverValue]
    │   ├── ns2:CollectionPermanentWaiveInd ← 89  [if value='Y']              [Conditional]
    │   ├── ns2:L9CollWaiverExpDate  ← ExtendedInfo[COLLECTION_WAIVER_EXPIRE_DATE]/Value
    │   │                              [if value='Y' and string-length > 0]   [Conditional]
    │   └── ns2:CollectionPermanentWaiveInd ← 78  [if value='N']              [Conditional]
    └── ns2:ActivityInfo
        ├── ns2:activityReason ← "SYSREQ" / "RW" / "CREQ"  [xsl:choose Y/N/other]
        └── ns2:userText       ← "Update CollectionPermanentWaiveInd"         [Always]
```

Legend: XPath source (green) | Static literal (orange) | Conditional (condition in brackets)

---

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| OPERATION_NAME | `CCBS_UPDATE_ACCOUNT_FIX_INFO` |
| PROCESS_ID | `concat(pid, "_REQ")` |
| AUDIT_TRACE | `concat("Request Sent for ", ActivityID)` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |

---

## §12 — Activity Status Management

| Condition | Status |
|-----------|--------|
| Request sent | `GetActivityStatusString("1", false)` → WAITING_RESPONSE |
| All skipped | `SkipActivity("4")` |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_UPDATE_ACCOUNT_FIX_INFO
├── RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit
├── RuleFunctions.Helpers.GetXMLForSubscriber
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU
├── XPath.execute (PreExecCheck)
├── XPath.evalAsString (accountId from Account[RefId=$accountRefId]/AccountID)
├── XPath.evalAsString (collectionWaiverValue from ExtendedInfo[COLLECTION_WAIVER]/Value)
├── Event.createEvent (CCBS_UPDATE_ACCOUNT_FIX_INFO XSLT × 2 variants)
├── Event.assertEvent
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

`Response_CCBS_UPDATE_ACCOUNT_FIX_INFO`: receives CCBS response event, builds `CCBS_UpdateAccountFixInfoRes` concept, appends to `currActivity.Response[]`, sends audit log, calls `IntraActivitySequencing.ActionResponseEvent(currActivity)` for fan-in.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Order context |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_ACCOUNT_FIX_INFO | Inbound response |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Fan-in target |

### §19.3 CCBS_UpdateAccountFixInfoRes Construction

```text
CCBS_UpdateAccountFixInfoRes
├── extId             ← OMXUtils.generateTrackingID()          [Always]
├── ResponseCode      ← $eventResponse/ResponseCode            [Conditional]
├── ResponseMessage   ← $eventResponse/ResponseMsg             [Conditional]
├── CompletionStatus  ← $eventResponse/CompletionStatus        [Conditional]
└── ReferenceId       ← $eventResponse/RefID                   [Conditional]
```

### §19.4 Fan-in Completion

Uses `IntraActivitySequencing.ActionResponseEvent(currActivity)` → returns `"true"` when all dispatched requests have responses (managed by sequencing framework). No explicit count XPath.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
