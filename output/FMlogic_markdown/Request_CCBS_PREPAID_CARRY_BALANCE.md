# Request_CCBS_PREPAID_CARRY_BALANCE

## §1 Overview & Purpose

Carries the prepaid subscriber's remaining credit balance over to the postpaid account by adding a carry-balance SOC to CCBS via `UpdateSubscriber`. The activity parameter is `socName:socCode` (e.g., `CARRYS01:11213612`).

Three skip conditions abort the activity early:
- **ATB2**: `CDB_CONVERGENCE` does not exist or its first character is not `'0'`
- **IOU**: `CDB_VAS` does not exist or bit 17 is `'1'`
- **L2**: `PRICEPLAN_CCP` does not exist or its value starts with `'R'` and contains `'DL'`

Uses **IntraActivitySequencing** pattern.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_PREPAID_CARRY_BALANCE` |
| Priority | 5 |
| ForwardChain | true |
| Activity ID | CCBS_PREPAID_CARRY_BALANCE |
| Backend | CCBS — UpdateSubscriber |
| Pattern | IntraActivitySequencing |
| Parameter | `socName:socCode` (e.g., `CARRYS01:11213612`) |
| Response Concept | `Concepts.FM.Response.CCBS_UpdateSubscriberRes` |
| Response Event | `Events.OMConsumers.OMXFM.Response.CCBS_PREPAID_CARRY_BALANCE` |

---

## §4 Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "CCBS_PREPAID_CARRY_BALANCE"
orderRequest.ProcessFlow.NextActivityID == "CCBS_PREPAID_CARRY_BALANCE"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 Execution Flow

1. Parse activity Parameter[0] → split by `:` → `param[0]=socName`, `param[1]=socCode`
2. Check ATB2 skip: `CDB_CONVERGENCE` char 1 ≠ `'0'` → skip
3. Check IOU skip: `CDB_VAS` bit 17 = `'1'` → skip
4. Check L2 skip: `PRICEPLAN_CCP` starts with `'R'` and contains `'DL'` → skip
5. If any skip: `SkipActivity("4")`
6. If not resubmit: `PurgePendingRequestsBeforeResubmit`
7. Get `MAIN_CREDIT` from subscriber `ExtendedInfo[Name='MAIN_CREDIT']/Value`
8. Format credit string: if decimal exists → split and zero-pad to 2 dp; else append `.00`
9. Cap: if `mainCreditNum > CAP_MAX` → use `String.valueOfInt(capMax) + ".00"`
10. Substitute USER_TEXT placeholder in offer description
11. Iterate ParentOU Subscribers: build and fire `CCBS_UPDATE_SUBSCRIBER` via `Event.assertEvent` + `ActionRequestEvent`
12. Iterate ChildOU Subscribers: same pattern
13. `IntraActivitySequencing.SendFirstRequestEvent(activity)` + set IN_PROGRESS

---

## §7 Skip Logic

| Skip Condition | XPath | Meaning |
|---------------|-------|---------|
| ATB2 | `not(exists(CDB_CONVERGENCE)) or substring(CDB_CONVERGENCE/Value,1,1) != '0'` | Not a convergence account |
| IOU | `not(exists(CDB_VAS)) or substring(CDB_VAS/Value,17,1) = '1'` | IOU/VAS bit indicates skip |
| L2 | `not(exists(PRICEPLAN_CCP)) or (starts-with(PRICEPLAN_CCP/Value,'R') and contains(PRICEPLAN_CCP/Value,'DL'))` | L2/DL price plan |

---

## §8.5 ExtendedInfo Fields Required

| Key | Required | Description |
|-----|----------|-------------|
| `MAIN_CREDIT` | Yes | Prepaid balance to carry; formatted as decimal |
| `CDB_CONVERGENCE` | Skip check | Convergence flag; bit 1 controls ATB2 skip |
| `CDB_VAS` | Skip check | VAS flags; bit 17 controls IOU skip |
| `PRICEPLAN_CCP` | Skip check | Price plan code; controls L2 skip |

## §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `$globalVariables/OMX_OM/BizRules/PrepaidCarryBalance/CAP_MAX` | Maximum credit cap |
| `$globalVariables/OMX_OM/BizRules/PrepaidCarryBalance/USER_TEXT` | Template for offer description |

---

## §9 Payload Build

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority        [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId  [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID    [Always]
    ├── RefID                ← $subscriberInstance/RefId          [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType  [Always]
    └── payload
        └── ns:UpdateSubscriberRequest
            └── ns:ChangeSubscriberOffersWithRelatedOffersInputInfo
                ├── ns:subscriberIdInfo
                │   └── ns:subscrNumber  ← $subscriberInstance/MSISDN  [Always]
                ├── ns:activityReason    ← ActivityReason or "CREQ"    [Conditional]
                ├── (SOC_SEQ_NO sequence)
                │   └── ns:SOC_SEQ_NO   ← sequence of SOC references
                └── ns:offersToAdd
                    ├── ns:name          ← $socName  (param[0])        [Always]
                    ├── ns:serviceType   ← "85"                        [Hardcoded]
                    ├── ns:soc           ← $socCode  (param[1])        [Always]
                    └── ns:parameterInfo[ns:name="Monetary quota"]
                        └── ns:values    ← $mainCredit (formatted)     [Always]
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_PREPAID_CARRY_BALANCE
├── String.split(Parameter[0], ":")         → param[0]=socName, param[1]=socCode
├── XPath.evalAsString(ExtendedInfo[MAIN_CREDIT])
├── contains($mainCredit, ".")              → decimal check
├── String.split($mainCredit, "\\.")        → integer/decimal parts
├── String.format("%02d", decimal)          → zero-pad
├── XPath.evalAsInt(CAP_MAX)
├── String.valueOfInt(capMax)               → cap override
├── String.replace(USER_TEXT, "{0}", ...)  → user text substitution
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(activity)
├── GetXMLForSubscriber(orderRequest, refId)
├── GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)
├── XPath.execute("/(preExecCheck)", sXML)
├── Event.assertEvent(reqEvent)
├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
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
| R1 | ATB2+IOU+L2 skip logic: all three conditions must be checked before any request is sent | [HIGH] |
| R2 | MAIN_CREDIT formatting: decimal-aware, zero-pad to 2 dp, cap at CAP_MAX global var | [HIGH] |
| R3 | Parameter split: `socName:socCode` at index 0 | [MEDIUM] |
| R4 | USER_TEXT substitution from global variable for offer description | [MEDIUM] |
| R5 | Dual ParentOU+ChildOU iteration with IntraActivitySequencing | [MEDIUM] |
| R6 | ActivityReason conditional: falls back to literal `"CREQ"` | [LOW] |
| R7 | SOC_SEQ_NO sequence must be included in UpdateSubscriberRequest payload | [HIGH] |
| R8 | Old RequestCount fan-in COMMENTED OUT; uses only IntraActivitySequencing.ActionResponseEvent | [LOW] |

---

## §19 Response Message Rule

### §19.1 Overview

Creates `CCBS_UpdateSubscriberRes` from event response fields. Response concept carries ResponseCode/ResponseMessage/CompletionStatus/ReferenceId from CCBS reply. Fan-in via `IntraActivitySequencing.ActionResponseEvent`. Old `RequestCount` code is commented out.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Order context |
| eventResponse | Events.OMConsumers.OMXFM.Response.CCBS_PREPAID_CARRY_BALANCE | Backend response |
| currActivity | Concepts.OM.ProcessConfig.Activity | Activity state |

### §19.4 Completion

```text
IntraActivitySequencing.ActionResponseEvent(currActivity)
→ "true" when all pending requests responded
(Old RequestCount == successResponseCount code COMMENTED OUT)
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
