# Request_CALCULATE_MNP_CREDIT_LIMIT

## §1 Overview & Purpose

Calculates the MNP (Mobile Number Portability) credit limit per account. Factors in IR SOC presence (41601 or 41606) by adding `CalcIR=15000` to the limit request. Uses **IntraActivitySequencing** for per-account sequential delivery.

**Two backend paths:**
- `GoldenDB=Y` → `CES_CALCULATE_MNP_CREDIT_LIMIT` event (CES service)
- `GoldenDB≠Y` → `CALCULATE_MNP_CREDIT_LIMIT` event (standard OMX credit limit service)

Response handler writes `PersonalCreditLimit` (rounded up to nearest 100) and `CreditLimitWaiverInd` ("U" or "N") to `Account.AccountManagementInfo`.

PreExecCheck in ProcessConfig: `Type!=73 and OrderType=7` (non-corporate MNP only).

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CALCULATE_MNP_CREDIT_LIMIT` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | CALCULATE_MNP_CREDIT_LIMIT |
| Backend | CES (GoldenDB path) or OMX Credit Limit Service |
| Pattern | Account-level fan-out with IntraActivitySequencing |
| Author | mbausaka-t430 |
| Response Rulefunction | Response_CALCULATE_MNP_CREDIT_LIMIT |

---

## §3 Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity state |

---

## §4 Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "CALCULATE_MNP_CREDIT_LIMIT"
orderRequest.ProcessFlow.NextActivityID == "CALCULATE_MNP_CREDIT_LIMIT"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 Execution Flow

1. Detect resubmit: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. If resubmit: call `IAS.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
3. For each `Account[i]` not yet responded:
   - Evaluate per-account PreExecCheck via `GetXMLForAccount(orderRequest, refId)`
   - Compute `SubCount` (XPath: count SubscriberOffers by AccountRefId)
   - Compute `CheckIR`: true if any SOC = 41601 or 41606 → `CalcIR=15000`
   - If `GoldenDB=Y`: assert `CES_CALCULATE_MNP_CREDIT_LIMIT`, call `IAS.ActionRequestEvent`
   - Else: assert `CALCULATE_MNP_CREDIT_LIMIT`, call `IAS.ActionRequestEvent`
4. If at least one request: call `IAS.SendFirstRequestEvent`, set status "1", `SendDataToDB`
5. If all skipped: call `SkipActivity(orderRequest, orderCurrentActivity, "4")`

---

## §7 Data Extraction & XPath Computations

### SubCount (subscriber offer count per account)

```xpath
if(count($orderRequest/OrderData/Customer/ParentOU/Subscriber[AccountRefId=$refId]/SubscriberOffers)>0)
then count($orderRequest/OrderData/Customer/ParentOU/Subscriber[AccountRefId=$refId]/SubscriberOffers)
else count($orderRequest/OrderData/Customer/ParentOU/ChildOU/Subscriber[AccountRefId=$refId]/SubscriberOffers)
```

### CheckIR (IR SOC 41601 / 41606)

```xpath
if(
  ($orderRequest/.../ParentOU/Subscriber[AccountRefId=$refId]/SubscriberOffers/Soc='41601')
  or (...RelatedOffersArray/Soc='41606')
  or ChildOU equivalents
) then true() else false()
```

→ `CalcIR = 15000` when CheckIR=true

### CreditLimitWaiverInd (response handler)

```xpath
"U" if (no RawAccountID AND (Type=70 OR SubType starts "HY" OR Grading != 'NON-TOP'))
else "N"
```

### PersonalCreditLimit (response handler)

```xpath
0.00 if (no RawAccountID AND (Type=70 OR SubType starts "HY")) OR Grading != 'NON-TOP'
else ceiling(CalCreditLimit/100)*100
```

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

MNP port-in orders only (Type!=73, OrderType=7). Both GoldenDB and non-GoldenDB customer paths handled.

### §8.2 ESB / JMS Channel

| Path | Event | Condition |
|------|-------|-----------|
| GoldenDB | `Events.OMConsumers.OMXFM.Request.CES_CALCULATE_MNP_CREDIT_LIMIT` | GoldenDB=Y |
| Standard | `Events.OMConsumers.OMXFM.Request.CALCULATE_MNP_CREDIT_LIMIT` | GoldenDB≠Y |
| Response | `Events.OMConsumers.OMXFM.Response.CALCULATE_MNP_CREDIT_LIMIT` | Both paths |

### §8.3 Backend API

| System | Operation | Namespace |
|--------|-----------|-----------|
| CES / OMX | CalculateMNPCreditLimit | `http://services.omx.truecorp.co.th/FM/CalculateMNPCreditLimitRequest` |

### §8.4 BE Working Memory Fields

| Field Path | Direction | Notes |
|-----------|-----------|-------|
| `Customer.CustomerTypeInfo.Type` | Read | Sent as customerType |
| `Customer.CustomerGeneralInfo.Grading` | Read | Sent as grading; used in WaiverInd/PersonalCreditLimit |
| `Customer.Account[i].AccountID` | Read | Conditional — sent if non-empty |
| `Customer.Account[i].AccountManagementInfo.AccountSubType` | Read | HY prefix triggers WaiverInd="U" |
| `Customer.ParentOU/ChildOU.Subscriber.SubscriberOffers[ServiceType=80]` | Read | SOC codes; IR check (41601/41606) |
| `Customer.Account[i].AccountManagementInfo.CreditLimitWaiverInd` | Written | Set in response: "U" or "N" |
| `Customer.Account[i].AccountManagementInfo.PersonalCreditLimit` | Written | Set in response: ceiling(CalCreditLimit/100)*100 |

---

## §9 Payload Build

### §9.6 Payload — CalculateMNPCreditLimitRequest

Namespace: `http://services.omx.truecorp.co.th/FM/CalculateMNPCreditLimitRequest` (prefix `ns1`)

```text
createEvent
└── event
    ├── JMSPriority           ← $orderRequest/OrderPriority             [Conditional]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId   [Conditional]
    ├── OrderID               ← $orderRequest/OrderData/OrderID         [Conditional]
    ├── RefID                 ← Account[$var]/RefId                     [Conditional: if RefId]
    ├── OrderType             ← $orderRequest/OrderData/OrderType        [Conditional]
    └── payload
        └── ns1:CalculateMNPCreditLimitRequest
            └── ns1:MNPCreditLimitAcc
                ├── ns1:customerType   ← Customer/CustomerTypeInfo/Type           [Always]
                ├── ns1:grading        ← Customer/CustomerGeneralInfo/Grading     [Always]
                ├── ns1:accountId      ← Account[$var]/AccountID                  [Conditional: tib:trim≠'']
                ├── ns1:accountSubType ← Account[$var]/AccountManagementInfo/...  [Always]
                ├── ns1:soc            ← SubscriberOffers[ServiceType='80']/Soc   [for-each, Conditional]
                ├── ns1:CalCreditLimit ← 0                                         [Always, static]
                └── ns1:CalcIR         ← 15000 (if IR SOC) or 0                  [Always]
```

> **Note:** `$var = number($i) + 1` — XPath is 1-based, Java loop is 0-based.

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` [Conditional] |
| PROCESS_ID | `concat($pid, "_REQ")` |
| OPERATION_NAME | "CALCULATE_MNP_CREDIT_LIMIT" |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | "Request Sent for CALCULATE_MNP_CREDIT_LIMIT" |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload | Conditional on WritePayload="true" |

Sent via `Event.Ext.sendEventImmediate` (synchronous flush).

---

## §12 Activity Status Management

| Outcome | Call |
|---------|------|
| At least one request sent | `IAS.SendFirstRequestEvent` → `GetActivityStatusString("1", false)` → `SendDataToDB` |
| All accounts already responded | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |

**IntraActivitySequencing:** uses `ActionRequestEvent` + `SendFirstRequestEvent` for sequential delivery.

---

## §13 Exception Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 Helper Functions

| Function | Purpose |
|----------|---------|
| `RuleFunctions.Helpers.IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)` | Clear pending queue on resubmit |
| `RuleFunctions.Helpers.GetXMLForAccount(orderRequest, refId)` | Serialize account XML for PreExecCheck |
| `RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(value)` | Null-safe blank check on GoldenDB flag |
| `RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)` | Enqueue request in IAS sequence |
| `RuleFunctions.Helpers.IntraActivitySequencing.SendFirstRequestEvent(activity)` | Trigger first IAS request |
| `RuleFunctions.Helpers.GetActivityStatusString("1", false)` | Returns SENT status string |
| `RuleFunctions.Helpers.SendDataToDB(orderRequest)` | Persist order state |
| `RuleFunctions.Helpers.SkipActivity(req, activity, "4")` | Skip this and 3 downstream activities |
| `RuleFunctions.Helpers.HandleActivityException(req, activity, ae, "")` | Standard error handler |
| `RuleFunctions.Helpers.IntraActivitySequencing.ActionResponseEvent(currActivity)` | Fan-in in response handler |

---

## §15 Function Dependency Tree

```text
Request_CALCULATE_MNP_CREDIT_LIMIT
├── [if isActResub] IAS.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── [For each Account[i] not responded]
│   ├── RuleFunctions.Helpers.GetXMLForAccount(orderRequest, refId)
│   ├── XPath.execute(PreExecCheck, sXML)
│   ├── XPath.evalAsInt(SubCount expression)
│   ├── XPath.evalAsBoolean(CheckIR: SOC 41601/41606)
│   ├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(GoldenDB)
│   ├── [GoldenDB=Y path]
│   │   ├── Event.createEvent("xslt://CES_CALCULATE_MNP_CREDIT_LIMIT")
│   │   ├── Event.assertEvent(reqEvent)
│   │   └── IAS.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   └── [Standard path]
│       ├── Event.createEvent("xslt://CALCULATE_MNP_CREDIT_LIMIT")
│       ├── Event.assertEvent(reqEvent)
│       └── IAS.ActionRequestEvent(reqEvent, orderCurrentActivity)
├── [if !isSkipped]
│   ├── IAS.SendFirstRequestEvent(orderCurrentActivity)
│   ├── GetActivityStatusString("1", false)
│   └── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── [if isSkipped]
│   └── RuleFunctions.Helpers.SkipActivity(req, activity, "4")
└── RuleFunctions.Helpers.HandleActivityException(req, activity, ae, "")
```

---

## §17 Migration Notes

| # | Requirement / Risk | Severity |
|---|-------------------|---------|
| R1 | Dual backend: GoldenDB=Y → CES, otherwise standard — target must route on GoldenDB flag | [HIGH] |
| R2 | IR SOC detection (41601/41606) adds CalcIR=15000 — hardcoded SOCs must be parameterized | [HIGH] |
| R3 | PersonalCreditLimit: ceiling(x/100)*100 rounding; CreditLimitWaiverInd logic (Type=70, SubType=HY, Grading) — exact replication required | [MEDIUM] |
| R4 | Account-level fan-out with IAS sequential delivery — must preserve per-account ordering | [MEDIUM] |
| R5 | $var = $i + 1 (XPath 1-based vs Java 0-based) — off-by-one in Account reference must be handled | [MEDIUM] |
| R6 | SkipActivity("4") — offset must match target activity chain | [LOW] |

---

## §19 Response Message Rule

### §19.1 Overview

Parses credit limit response, writes `CreditLimitWaiverInd` and `PersonalCreditLimit` to matching account. Fan-in via `IAS.ActionResponseEvent`.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CALCULATE_MNP_CREDIT_LIMIT` | Credit limit response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity tracking |

### §19.3 ResponseBase: CalMNPCreditLimitRes

```text
createObject
└── object
    ├── @extId              ← OMXUtils.generateTrackingID()                             [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode                               [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg                                [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus                           [Conditional]
    ├── ReferenceId         ← $eventResponse/RefID                                      [Conditional]
    ├── CalCreditLimit      ← .../ns:CalculateMNPCreditLimitResponse/ns:CalCreditLimit  [Conditional]
    └── CreditLimitWaiverInd ← .../ns:CalculateMNPCreditLimitResponse/ns:CreditLimitWaiverInd [Conditional]
```

### §19.4 Fan-in Completion

Uses `RuleFunctions.Helpers.IntraActivitySequencing.ActionResponseEvent(currActivity)` — returns "true" when all accounts have responded (managed by IAS internal counter).

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
