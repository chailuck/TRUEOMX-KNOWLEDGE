# Request_CJ_CREATE_SUB_CALL_VERIFICATION

> CJ Create Subscriber Call Verification — Post-Creation FCR Status Notification to Customer Journey System

**Priority:** 5 | **forwardChain:** true | **Backend:** CJ (Customer Journey) | **Author:** TIT_F25-Maline5 | **Generated:** 2026-07-27

---

## §1 — Overview & Purpose

This rule fires after CCBS subscriber creation (`CCBS_CREATE_SUBS`) completes and the order reaches `ActivityID = CJ_CREATE_SUB_CALL_VERIFICATION`. It sends a `CreateSubCallVerification` message to the CJ (Customer Journey) system for each ParentOU Subscriber, reporting the subscriber's First Call Resolution (FCR) status, call verification result, and supporting subscriber profile data.

> **CJ System Role:** Customer Journey is a tracking and audit system that records key lifecycle events for subscribers. The call verification notification is a regulatory/audit record confirming whether the subscriber was subject to FCR call-back verification before activation, and the outcome of that verification.

> **ParentOU only — no ChildOU loop:** Unlike CCBS_CREATE_SUBS, this rule only iterates `ParentOU.Subscriber[]`. ChildOU subscribers are not processed for call verification.

> **FCR SOC-driven logic:** The key driver is whether the subscriber holds the FCR SOC offer (loaded from global variable `OMX_OM/Services/CJ/FCRSoc`, offer type FE_OR_CCBS=BRMS). Subscribers with FCR SOC are subject to call verification; all others default to UNBAR / PASS / BYPASS statuses.

> **No write-back to subscriber fields:** The response only records the CJ system's acknowledgement in `currActivity.Response[]`. No subscriber concept fields are modified by the response handler.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Request_CJ_CREATE_SUB_CALL_VERIFICATION` |
| Full Path | `Rules.OMConsumers.OMXFM.Request.Request_CJ_CREATE_SUB_CALL_VERIFICATION` |
| Priority | 5 |
| forwardChain | true |
| Author | TIT_F25-Maline5 |
| Backend System | CJ — Customer Journey (FCR / call verification audit) |
| Operation | CreateSubCallVerification |
| Request schema namespace | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd8` |
| Dispatch mechanism | IntraActivitySequencing (sequential, ParentOU subscribers only) |
| Subscriber scope | ParentOU only — ChildOU not included |
| Resubmission guard | Yes — per subscriber, checks CompletionStatus==2 |
| Resubmission purge | Yes — PurgePendingRequestsBeforeResubmit on isActResub |
| Write-back to order | None — response recorded in currActivity.Response[] only |

---

## §3 — Working Memory — Declared Objects

| Variable | Type Path | Role |
|----------|-----------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Master order — ParentOU.Subscriber hierarchy iterated; no fields written in response |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | PreExecCheck, IntraActivitySequencing queue, Response[] accumulator |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity to order execution point |
| 2 | `orderCurrentActivity.ActivityID == "CJ_CREATE_SUB_CALL_VERIFICATION"` | Targets only this activity type |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CJ_CREATE_SUB_CALL_VERIFICATION"` | Order-level double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires on fresh/ready activity |

---

## §5 — Execution Flow

1. **Init** — `isActResub = (RequestCount>0 && IsOrderResubmitted)`; if resubmit → `PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`; read `fcrSoc` from global variable `OMX_OM/Services/CJ/FCRSoc` (trimmed)
2. **ParentOU Subscriber loop** — for each `ParentOU[i].Subscriber[j]`:
   - Resubmission guard: check `Response[].ReferenceId==refId && CompletionStatus==2`
   - PreExecCheck via `GetXMLForSubscriber(orderRequest, refId)`
   - If PreExecCheck passes: compute `activityDate`, `subRef`, `prevSubNum` (OrderType-dependent), `proPosition` (contract offer names)
   - `Event.assertEvent(reqEvent)` + `IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)`
   - Send audit log; `isSkipped=false`
3. **After loop** — if not skipped: `IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)`; Status = IN_PROGRESS; SendDataToDB
4. **Skipped path** — if no subscribers dispatched: `SkipActivity(…, "4")` → SKIPPED
5. **Exception** — catch → `HandleActivityException` → ERROR

---

## §6 — Rule Action — Key Logic

### FCR SOC Lookup

```java
// FCR SOC code from global variable (shared config, not per-order)
String fcrSoc = XPath.evalAsString("tib:trim($globalVariables/OMX_OM/Services/CJ/FCRSoc)");
```

### prevSubNum Resolution (Port-In Awareness)

```java
// OrderType=11 → prevSubNum is simply the subscriber's own RefId
if(orderRequest.OrderData.OrderType == "11") {
    prevSubNum = XPath.evalAsString("$subscriber/RefId");
} else {
    // Other types (MNP/change): find the SOURCE subscriber's RefId
    prevSubNum = XPath.evalAsString(
        "$subscriber[ExtendedInfo[Name=\"SOURCE_OR_TARGET\" and Value=\"SOURCE\"]]/RefId");
}
// subRef = concat(RefId, '_src') — built but only used in commented-out block
subRef = XPath.evalAsString("concat($subscriber/RefId,'_src')");
```

### Contract Offer Collection (proPosition)

```java
String proPosition = "";
for(int pso=0; pso<subscriber.SubscriberOffers@length; pso++) {
    String chkContract = subscriber.SubscriberOffers[pso].SocProperties;
    // Only include offers that have the contract indicator flag
    if(XPath.evalAsBoolean("contains($chkContract, \"TR_CONTRACT_IND=Y\")")) {
        offerName = XPath.evalAsString("$subOff/OfferName");
        if(proPosition != "") offerName = "," + offerName;
        proPosition = String.concat(proPosition, offerName);
    }
}
// e.g., proPosition = "OfferA,OfferB" — comma-separated contract offer names
```

---

## §7 — Data Extraction — Per-Subscriber Context Assembly

| Variable | Source | Notes |
|----------|--------|-------|
| `fcrSoc` | `tib:trim($globalVariables/OMX_OM/Services/CJ/FCRSoc)` | Global config — same for all subscribers; identifies the FCR SOC code |
| `refId` | `Subscriber[j].RefId` | Correlation key for JMS and resubmission guard |
| `activityDate` | `current-dateTime()` | Wall-clock time (unlike CCBS_CREATE_SUBS which uses LogicalDate) |
| `subRef` | `concat($subscriber/RefId, '_src')` | Source subscriber reference; built but used only in commented-out lookup block |
| `prevSubNum` | OrderType=11 → `$subscriber/RefId`; else → `$subscriber[ExtendedInfo[SOURCE_OR_TARGET=SOURCE]]/RefId` | Previous subscriber number for port-in/change orders |
| `proPosition` | Comma-join of `SubscriberOffers[SocProperties contains "TR_CONTRACT_IND=Y"].OfferName` | Contract proposition names for CJ audit |

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

| Scenario | Effect |
|----------|--------|
| isActResub=true | PurgePendingRequestsBeforeResubmit; prior CompletionStatus==2 subscribers skipped |
| OrderType == "11" | `prevSubNum` = subscriber's own RefId |
| Other OrderType | `prevSubNum` = RefId of the SOURCE subscriber (port-in / change flows) |
| Subscriber has FCR SOC offer (FE_OR_CCBS=BRMS, OfferName=fcrSoc) | fcrStatus driven by CALL_VER_STATUS ExtendedInfo |
| Subscriber has no FCR SOC offer | fcrStatus=UNBAR, callVerStatus=BYPASS, callVerResult=PASS |
| SubscriberOffers with TR_CONTRACT_IND=Y | `proPosition` built as comma-separated OfferNames for CJ audit |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Channel URI | Event Type | Purpose |
|-----------|-------------|------------|---------|
| [OUTBOUND (queued)] | `/Channels/OMXFMConnectionRequest` | `Events.OMConsumers.OMXFM.Request.CJ_CREATE_SUB_CALL_VERIFICATION` | CJ CreateSubCallVerification — per ParentOU subscriber, sequential |
| [OUTBOUND] | `/Channels/LogConnection` | `Events.OMConsumers.OMXESB.Logger` | Request audit per subscriber |

### §8.3 — Backend API Details

| Attribute | Value |
|-----------|-------|
| System | CJ — Customer Journey |
| Operation | CreateSubCallVerification |
| Request schema namespace | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/FM/Schema.xsd8` |
| Root request element | `ns:CreateSubCallVerification` |
| Dispatch mechanism | Sequential via IntraActivitySequencing |
| Fan-in | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Response write-back | None |

### §8.4 — BE Working Memory Dependencies

| Field / Path | Direction | Purpose |
|--------------|-----------|---------|
| `Subscriber[j].RefId` | [READ] | Correlation key |
| `Subscriber[j].SubscriberId` | [READ] | CCBS subscriber number (required — set by CCBS_CREATE_SUBS) |
| `Subscriber[j].MSISDN` | [READ] | serviceId field |
| `Subscriber[j].SubscriberOffers[].SocProperties` | [READ] | TR_CONTRACT_IND=Y check; FCR SOC check |
| `Subscriber[j].SubscriberOffers[].ExtendedInfo[FE_OR_CCBS]` | [READ] | Identify FCR SOC offer |
| `Subscriber[j].ExtendedInfo[CALL_VER_STATUS]` | [READ] | Call verification result |
| `Subscriber[j].ExtendedInfo[CALL_VER_REASON]` | [READ] | Call verification reason |
| `Subscriber[j].SubscriberGeneralInfo.saleId` | [READ] | Sale ID for CJ |
| `Subscriber[j].SubscriberType` | [READ] | Subscriber type for extra block |
| `Subscriber[j].ResourceInfo[SIM].ValuesArray` | [READ] | SIM serial number |
| `Subscriber[j].AccountRefId` | [READ] | Account lookup key |
| `OrderData.Customer.Account[RefId=AccountRefId].AccountManagementInfo` | [READ] | CompanyCode, AccountSubType |
| `OrderData.Customer.CustomerGeneralInfo.Identification/IdentificationType` | [READ] | ID number and type |
| `OrderData.Customer.CustomerGeneralInfo.contactLang` | [READ] | Contact language |
| `OrderData.Customer.CustomerTypeInfo.Type` | [READ] | Customer type (ASCII-decoded) |
| `currActivity.Response[]` | [WRITE] | CJ response acknowledgement appended |
| `orderCurrentActivity.Status` | [WRITE] | IN_PROGRESS or SKIPPED |

### §8.5 — Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Services/CJ/FCRSoc` | FCR SOC code — identifies which SOC triggers call verification |
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Include credentials in request |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `OMX_OM/WritePayload` | Include payload in audit log |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameters

| Parameter | Bound From |
|-----------|------------|
| `$orderRequest` | Working memory concept |
| `$refId` | `Subscriber[j].RefId` |
| `$globalVariables` | BE global variables |
| `$subscriber` | `ParentOU[i].Subscriber[j]` |
| `$prevSubNum` | OrderType-dependent source subscriber RefId |
| `$fcrSoc` | `tib:trim($globalVariables/OMX_OM/Services/CJ/FCRSoc)` |
| `$activityDate` | `current-dateTime()` |
| `$proPosition` | Comma-joined contract offer names |

### §9.2 — FCR Status Decision Logic

**ns:fcrStatus**

| Condition | Value |
|-----------|-------|
| Has FCR SOC AND CALL_VER_STATUS=BYPASS | UNBAR |
| Has FCR SOC AND CALL_VER_STATUS=NOFCR | BAR |
| Has FCR SOC AND any other status | BAR |
| No FCR SOC | UNBAR |

**ns:callVerReason**

| Condition | Value |
|-----------|-------|
| ExtendedInfo[CALL_VER_REASON] exists | Use `ExtendedInfo[CALL_VER_REASON]/Value` |
| Has FCR SOC (no CALL_VER_REASON) | `concat('New Acquisition - ', OrderType)` |
| No FCR SOC | `'OMX Rule by pass'` |

**ns:callVerStatus**

| Condition | Value |
|-----------|-------|
| ExtendedInfo[CALL_VER_STATUS] exists | Use `ExtendedInfo[CALL_VER_STATUS]/Value` |
| Has FCR SOC (no CALL_VER_STATUS) | `'NOFCR'` |
| No FCR SOC | `'BYPASS'` |

**ns:callVerResult**

| Condition | Value |
|-----------|-------|
| CALL_VER_STATUS in {PASS, OVERFLOW, BYPASS} | `PASS` |
| CALL_VER_STATUS = NOTPASS | `NOTPASS` |
| CALL_VER_STATUS = NOFCR | `NOTCALLVER` |
| Has FCR SOC (no CALL_VER_STATUS) | `NOTCALLVER` |
| No FCR SOC (no CALL_VER_STATUS) | `PASS` |

---

## §10 — XSLT Field Mapping

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                          [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId               [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                      [Conditional]
    ├── RefID                ← $refId                                               [Always]
    ├── UserName             ← $orderRequest/OrderData/User                         [Credential-gated]
    ├── PassWord             ← $orderRequest/OrderData/Password                     [Credential-gated]
    ├── OrderType            ← $orderRequest/OrderData/OrderType                    [Conditional]
    └── payload
        └── ns:CreateSubCallVerification
            ├── ns:trackingId    ← concat(OMXTrackingId, "-", subscriber/SubscriberId)  [Always]
            ├── ns:serviceId     ← $subscriber/MSISDN                              [Always]
            ├── ns:orderId       ← $orderRequest/OrderData/OrderID                 [Always]
            ├── ns:subNumber     ← $subscriber/SubscriberId                        [Always]
            ├── ns:previousSubNum ← $prevSubNum                                   [Conditional: prevSubNum!=""]
            ├── ns:idNum         ← CustomerGeneralInfo/Identification              [Conditional]
            ├── ns:idType        ← CustomerGeneralInfo/IdentificationType          [Conditional]
            ├── ns:channel       ← $orderRequest/OrderData/Channel                 [Always]
            ├── ns:dealerCode    ← $orderRequest/OrderData/DealerCode              [Conditional]
            ├── ns:saleId        ← $subscriber/SubscriberGeneralInfo/saleId        [Conditional]
            ├── ns:fcrStatus     ← FCR decision (UNBAR or BAR)                    [Always]
            ├── ns:callVerReason ← CALL_VER_REASON or 'New Acquisition-{type}' or 'OMX Rule by pass'  [Always]
            ├── ns:callVerStatus ← CALL_VER_STATUS or 'NOFCR' or 'BYPASS'        [Always]
            ├── ns:callVerResult ← PASS/NOTPASS/NOTCALLVER                         [Always]
            ├── ns:datetime      ← $activityDate (current-dateTime())              [Always]
            └── ns:extra
                ├── ns:priceplan       ← SubscriberOffers[ServiceType='80']/OfferName    [Conditional]
                ├── ns:proposition     ← $proPosition                              [Conditional: proPosition!=""]
                ├── ns:orderType       ← $orderRequest/OrderData/OrderType         [Conditional]
                ├── ns:customerName    ← ParentOU[1]/OUName                        [Conditional]
                ├── ns:contactLang     ← CustomerGeneralInfo/contactLang           [Conditional: !=""]
                ├── ns:simSerial       ← ResourceInfo[SIM]/ValuesArray             [Conditional]
                ├── ns:customerType    ← OMXUtils:asciiCodeToText(CustomerTypeInfo/Type)  [Conditional]
                ├── ns:subscriberType  ← $subscriber/SubscriberType                [Conditional]
                ├── ns:companyCode     ← Account[AccountRefId]/CompanyCode         [Conditional]
                └── ns:accountSubType  ← Account[AccountRefId]/AccountSubType      [Conditional]
```

---

## §11 — Audit Logging

| Phase | Field | Value |
|-------|-------|-------|
| Request | PROCESS_ID | `concat(pid, "_REQ")` |
| Request | OPERATION_NAME | `"CJ_CREATE_SUB_CALL_VERIFICATION"` |
| Request | AUDIT_TRACE | `concat("Request Sent for RefId ", $refId)` |
| Response | PROCESS_ID | `concat(pid, "_RES")` |
| Response | OPERATION_NAME | `"CJ_CREATE_SUB_CALL_VERIFICATION"` |
| Response | AUDIT_TRACE | `concat("Response received for RefId ", $eventResponse/RefID)` |

---

## §12 — Activity Status Management

| Trigger | Code | Status | Method |
|---------|------|--------|--------|
| Rule fires | 0 | [WAITING] | Pre-condition |
| At least one subscriber queued | 1 | [IN_PROGRESS] | `GetActivityStatusString("1", false)` |
| No subscribers dispatched | 4 | [SKIPPED] | `SkipActivity(…, "4")` |
| Exception caught | 3 | [ERROR] | `HandleActivityException` |
| All sequential responses received | 2 | [COMPLETED] | `IntraActivitySequencing.ActionResponseEvent → "true"` |

---

## §15 — Function Dependency Tree

```text
Request_CJ_CREATE_SUB_CALL_VERIFICATION (rule)
├── Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity")
├── [if isActResub] IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity)
├── XPath.evalAsString("tib:trim($globalVariables/OMX_OM/Services/CJ/FCRSoc)")   [fcrSoc]
├── Per ParentOU[i].Subscriber[j] loop:
│   ├── Resubmission guard: Response[].ReferenceId==refId && CompletionStatus==2
│   ├── GetXMLForSubscriber(orderRequest, refId)
│   ├── XPath.execute("/(PreExecCheck)", sXML, ns)
│   ├── XPath.evalAsString("current-dateTime()")              [activityDate]
│   ├── XPath.evalAsString("concat($subscriber/RefId,'_src')") [subRef]
│   ├── [OrderType=11] XPath.evalAsString("$subscriber/RefId") [prevSubNum]
│   ├── [else] XPath.evalAsString("$subscriber[ExtendedInfo[SOURCE_OR_TARGET=SOURCE]]/RefId")
│   ├── Scan SubscriberOffers for TR_CONTRACT_IND=Y → proPosition
│   │   ├── XPath.evalAsBoolean("contains($chkContract, 'TR_CONTRACT_IND=Y')")
│   │   └── XPath.evalAsString("$subOff/OfferName")
│   ├── Event.createEvent(xslt://CJ_CREATE_SUB_CALL_VERIFICATION)
│   ├── Event.assertEvent(reqEvent)
│   ├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
│   └── Event.createEvent(xslt://Logger)
├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(...)
└── HandleActivityException(...)

Response_CJ_CREATE_SUB_CALL_VERIFICATION (rulefunction)
├── OMXUtils.generateTrackingID()
├── Instance.createInstance(xslt://ResponseBase)
│   └── ResponseCode, ResponseMessage, CompletionStatus, ReferenceId
├── currActivity.Response[n] = activityRes
├── Event.createEvent(xslt://Logger)
└── IntraActivitySequencing.ActionResponseEvent(currActivity) → "true"/"false"
    [old commented-out: count(Response[ResponseCode ends "000"]) == RequestCount]
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Iterate ParentOU Subscribers only (no ChildOU). Skip previously completed (CompletionStatus=2).
- **R2** — Read FCR SOC from global config at rule-entry time. Apply to all subscriber FCR decisions.
- **R3** — Compute `prevSubNum` based on OrderType: if "11" → own RefId; else → SOURCE_OR_TARGET=SOURCE ExtendedInfo subscriber RefId.
- **R4** — Build `proPosition` as comma-separated contract offer names (SocProperties contains "TR_CONTRACT_IND=Y").
- **R5** — Apply the four-field FCR decision table exactly. Priority: explicit ExtendedInfo values first, then FCR SOC presence inference, then defaults.
- **R6** — Dispatch via sequential IntraActivitySequencing (same as CCBS_CREATE_SUBS).
- **R7** — Response: no subscriber write-back. Record acknowledgement in activity response array only.
- **R8** — `ns:subNumber` = `subscriber.SubscriberId` (CCBS-assigned number). Must be non-empty — set by CCBS_CREATE_SUBS.

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| FCR SOC is read from a global variable — value changes in config silently affect all orders in flight | [MEDIUM] | Snapshot FCR SOC at order intake or activity-start; avoid live global reads mid-order |
| callVerResult logic has 5 branches with overlap — boundary order matters | [MEDIUM] | Unit test all 5 branches; BYPASS appears in PASS group; NOFCR explicit beats FCR SOC inference |
| prevSubNum may be empty string for non-11 orders with no SOURCE subscriber tagged | [LOW] | ns:previousSubNum is conditionally emitted; handle empty gracefully |
| OMXUtils.asciiCodeToText on CustomerTypeInfo.Type — platform-specific function | [LOW] | Implement equivalent ASCII-to-text decode in migration platform |
| subRef (concat RefId + '_src') is computed but only used in a commented-out block | [LOW] | Do not carry subRef into migration unless the commented-out block is intentionally restored |

---

## §19 — Response Message Rule

### §19.1 — Overview

`RuleFunctions.OrderResponse.Response_CJ_CREATE_SUB_CALL_VERIFICATION`:
1. Creates a standard `ResponseBase` concept (ResponseCode, ResponseMessage, CompletionStatus, ReferenceId)
2. Appends it to `currActivity.Response[]`
3. Sends response audit log
4. Returns `"true"` / `"false"` via `IntraActivitySequencing.ActionResponseEvent(currActivity)`

> **Note:** The old fan-in logic (`count(Response[ResponseCode ends "000"]) == RequestCount`) is **fully commented out**. The active path uses IntraActivitySequencing only — there is no "000" success count check in the current live code.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Read-only in response handler — no fields written |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CJ_CREATE_SUB_CALL_VERIFICATION` | CJ system acknowledgement payload |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] appended; IntraActivitySequencing state |

### §19.3 — ResponseBase Concept Fields

```text
createObject
└── object
    ├── @extId           ← OMXUtils.generateTrackingID()   [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode      [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg       [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus  [Conditional]
    └── ReferenceId      ← $eventResponse/RefID             [Conditional]
```

### §19.4 — Response Completion Logic

```java
// Active fan-in — IntraActivitySequencing manages sequential queue
if(RuleFunctions.Helpers.IntraActivitySequencing.ActionResponseEvent(currActivity))
    return "true";   // all subscribers processed
else
    return "false";  // waiting for next subscriber response

/* COMMENTED OUT (old fan-in):
   int successResponseCount = XPath.evalAsInt(
       "count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = \"000\"])");
   if(currActivity.RequestCount == successResponseCount)  return "true";
   else return "false";
*/
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
