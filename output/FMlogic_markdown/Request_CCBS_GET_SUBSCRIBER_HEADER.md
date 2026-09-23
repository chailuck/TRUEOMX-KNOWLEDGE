# Request_CCBS_GET_SUBSCRIBER_HEADER

> TIBCO BusinessEvents FM Logic — CCBS GetSubscriberHeader enrichment with IntraActivitySequencing fan-out throttle

**Author:** warawich-nb | **Target System:** CCBS (AMDOCS L9) | **Protocol:** JMS/SOAP | **Pattern:** IntraActivitySequencing (Throttled Fan-Out) | **Generated:** 2026-08-04

---

## §1 Overview & Purpose

`CCBS_GET_SUBSCRIBER_HEADER` retrieves the full subscriber header record from CCBS (AMDOCS L9) and enriches the OMX order graph with name, address, status, and account data.

It uses the **IntraActivitySequencing** pattern (throttled fan-out) rather than standard parallel fan-out, ensuring CCBS requests for the same order are sent one-at-a-time to prevent session contention.

The response handler (551 lines) is among the most complex in the system: it populates up to six subscriber sub-concepts using LinkType/NameType routing across 15 AddressElement slots, with full ClearField erasure support.

> **ALT_CES Routing:** An `ALT_CES` activity parameter enables alternate CES endpoint routing — when present and value != "", the CES host is overridden from the subscriber's ExtendedInfo.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_SUBSCRIBER_HEADER` |
| Author | warawich-nb |
| Validity | ACTION |
| Backend system | CCBS / AMDOCS L9 |
| Operation | GetSubscriberHeader |
| Request schema | `tibco-ccbs-client/Schemas/SubscriberServices/Schema.xsd4` |
| Response concept | `Concepts.FM.Response.CCBS_GetSubscriberHeaderRes` |
| Sequencing pattern | IntraActivitySequencing (throttled fan-out) |
| Corresponding response | `Response_CCBS_GET_SUBSCRIBER_HEADER.rulefunction` |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order object graph |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity — ALT_CES param lookup, IntraActivitySequencing calls |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Notes |
|---|-----------|-------|
| 1 | Order request in working memory | Must have subscriber with matching activity |
| 2 | Current activity = `CCBS_GET_SUBSCRIBER_HEADER` | From ProcessConfig |
| 3 | IntraActivitySequencing gate passes | Throttles; parks if queue busy |

---

## §5 Execution Flow

1. **Resubmit check** → `PurgePendingRequestsBeforeResubmit(orderCurrentActivity)`
2. **ALT_CES resolution** → read `ALT_CES` param; override CES if Y and ExtendedInfo value != ""
3. **Credential gate** → if `IsEnableUserPass='true'` → add UserName/PassWord headers
4. **Payload build** → `GetSubscriberHeaderRequest/SubscriberIdInfo/subscrNumber = SubscriberId`
5. **Throttle** → `ActionRequestEvent(reqEvent, orderCurrentActivity)` — queues; serialises calls
6. **Completion** → `SendFirstRequestEvent()` + `GetActivityStatusString("1", false)` + `SendDataToDB()`
7. **Skip path** → `SkipActivity("4")` if PreExecCheck fails

---

## §6 Rule Action (THEN)

### §6.1 IntraActivitySequencing Fan-Out

| Call | When | Purpose |
|------|------|---------|
| `PurgePendingRequestsBeforeResubmit(orderCurrentActivity)` | On resubmit | Cancel queued-but-unsent requests |
| `ActionRequestEvent(reqEvent, orderCurrentActivity)` | Each subscriber | Adds to throttle queue; serialises |
| `SendFirstRequestEvent(orderCurrentActivity)` | After queuing all | Triggers first release |

### §6.2 ALT_CES Routing Logic

```java
String altParam = GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES");
// xsl:choose inside XSLT:
// when: altParam="Y" AND ExtendedInfo[ALT_CES]/Value != ""
//   → CES = ExtendedInfo["ALT_CES"]/Value
// otherwise:
//   → CES = $orderRequest/OrderData/CES
```

### §6.3 Credential Gate

```java
if (IsEnableUserPass == 'true') {
  header.UserName = OrderData/User;
  header.PassWord = OrderData/Password;
}
```
[Credential-gated] — headers only when global `IsEnableUserPass` = "true"

### §6.4 Namespace Variants

| Context | Prefix | URI |
|---------|--------|-----|
| POU subscriber | `ns1` | `http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/SubscriberServices/Schema.xsd4` |
| COU subscriber | `ns` | (same URI, different prefix) |

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

| Global Variable | Purpose |
|-----------------|---------|
| `OMX_OM/OrderTypes/GetNameAddress` | CSV of OrderTypes enabling full name/address mapping |
| `OMX_OM/OrderTypes/UpdateNameAddress` | CSV of OrderTypes that are update-name-address flows |

Special case: **OrderType=129** (Move Subscriber TOL) delegates to helper rulefunctions.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel | Protocol |
|-----------|---------|----------|
| [OUTBOUND] | OMXFM CCBS channel | JMS → SOAP |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_GET_SUBSCRIBER_HEADER` | JMS |

### §8.3 Backend API Details

| Property | Value |
|----------|-------|
| System | CCBS / AMDOCS L9 |
| Operation | `GetSubscriberHeader` |
| Schema | `amdocs.csm3g.datatypes.SubscriberHeader` (xsd4) |
| Request root | `GetSubscriberHeaderRequest/SubscriberIdInfo/subscrNumber` |
| Correlation | `JMSCorrelationID + ":CCBS_GET_SUBSCRIBER_HEADER_RES:" + RefID` |

### §8.4 BE Working Memory — Fields Written

| Concept | Field | Source |
|---------|-------|--------|
| Subscriber (POU) | `ExtendedInfo["dealerCode"]` | OrderData/DealerCode → fallback: response DealerCode |
| Subscriber (POU) | `MSISDN` | response SubscriberGeneralInfo/PrimResourceVal (only if blank) |
| Account | `AccountID` | response L9AccountId (only if param=ACCOUNT_ID and blank) |
| Subscriber | `SubscriberGeneralInfo.ConvergenceCode` | response L9ConvergenceCode |
| Subscriber | `ExtendedInfo["CONVERGENT_CODE"]` | from SubscriberGeneralInfo.ConvergenceCode |
| Subscriber | `ExtendedInfo["subStatus"]` | `OMXUtils.asciiCodeToText(SubStatus int)` |
| Subscriber | `Status` (int) | response SubscriberStatusInfo/SubStatus |
| Subscriber | `SubscriberGeneralInfo.Language` | response Language (only if param=LANGUAGE) |
| Subscriber | `SubscriberName.*` | NameAddressInfoList (LinkType=83) INDY/CORP |
| Subscriber | `SubscriberName2.*` | via CCBS_GET_SUBSCRIBER_HEADER_EXTEND helper |
| Subscriber | `SubscriberAddress.*` | NameAddressInfoList (LinkType=83, AddressInfo, 15 slots) |
| Subscriber | `SubscriberAddress2.*` | NameAddressInfoList (LinkType=72, AddressInfo, 15 slots) |

### §8.5 ExtendedInfo Fields

| Key | Required | Usage |
|-----|----------|-------|
| `ALT_CES` | Optional | Overrides CES when param ALT_CES=Y and value != "" |

### §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_COMMON/_SharedResources/Common/IsEnableUserPass` | Gate for credential headers |
| `OMX_COMMON/_SharedResources/Common/ClearField` | Sentinel value — field set to null when response equals this |
| `OMX_OM/OrderTypes/GetNameAddress` | Order types enabling name/address backfill |
| `OMX_OM/OrderTypes/UpdateNameAddress` | Order types that are name-address update flows |
| `OMX_COMMON/Component_Name/OMX_CEP` | Logger component name |
| `OMX_OM/WritePayload` | Gate for payload capture in audit log |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| XSLT Param | Bound from |
|------------|-----------|
| `$orderRequest` | Working memory: `Concepts.OrderRequest.OrderRequest` |
| `$orderCurrentActivity` | Working memory: `Concepts.OM.ProcessConfig.Activity` |
| `$globalVariables` | BE global variables store |
| `$altParam` | `GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")` |
| `$subId` | SubscriberId from matched subscriber |

### §9.2 Request Payload (POU variant)

```xml
<ns1:GetSubscriberHeaderRequest
  xmlns:ns1="http://www.tibco.com/schemas/tibco-ccbs-client/Schemas/SubscriberServices/Schema.xsd4">
  <ns1:SubscriberIdInfo>
    <ns1:subscrNumber>$subId</ns1:subscrNumber>
  </ns1:SubscriberIdInfo>
</ns1:GetSubscriberHeaderRequest>
```

### §9.3 JMS Headers

| Header | Value | Condition |
|--------|-------|-----------|
| `CES` | ALT_CES value OR OrderData/CES | ALT_CES routing |
| `UserName` | OrderData/User | `IsEnableUserPass='true'` |
| `PassWord` | OrderData/Password | `IsEnableUserPass='true'` |

---

## §10 XSLT Field Mapping Tree

```text
GetSubscriberHeaderRequest  (ns1: SubscriberServices/Schema.xsd4)
└── SubscriberIdInfo
    └── subscrNumber  ← $subId (SubscriberId)  [Always]

JMS event headers:
└── event
    ├── CES              ← ExtendedInfo[ALT_CES]/Value OR OrderData/CES  [Conditional: ALT_CES routing]
    ├── UserName         ← OrderData/User                                 [Credential-gated: IsEnableUserPass='true']
    └── PassWord         ← OrderData/Password                             [Credential-gated: IsEnableUserPass='true']
```

---

## §11 Audit Logging

Audit log emitted in the response handler (§19.7):

| Field | Value |
|-------|-------|
| OPERATION_NAME | `CCBS_GET_SUBSCRIBER_HEADER` |
| AUDIT_TRACE | `Response received for CCBS_GET_SUBSCRIBER_HEADER` |
| PROCESS_ID | `concat(pid, "_RES")` |
| COMPONENT_NAME | `OMX_CEP` global |
| payload | Included when `WritePayload="true"` |

---

## §12 Activity Status Management

| Call | Code | Meaning |
|------|------|---------|
| `GetActivityStatusString("1", false)` | 1 | Active / In-Progress |
| `SkipActivity("4")` | 4 | Skipped |

---

## §14 Helper Functions Reference

| Function | Signature | Purpose |
|----------|-----------|---------|
| `PurgePendingRequestsBeforeResubmit` | (Activity) → void | Clears throttle queue before resubmit |
| `ActionRequestEvent` | (Event, Activity) → boolean | Throttle-queues request |
| `SendFirstRequestEvent` | (Activity) → void | Dispatches first from queue |
| `GetActivityParameterValueFromKey` | (Activity, String) → String | Reads activity parameter |
| `GetActivityStatusString` | (String, boolean) → String | Returns status string |
| `SkipActivity` | (String) → void | Sets SKIP status |
| `SendDataToDB` | () → void | Persists activity state |
| `BRMS.IsBlank` | (String) → boolean | Null or empty check |
| `BRMS.IsBlankOrStringNull` | (String) → boolean | Null, empty, or "null" check |
| `OMXUtils.asciiCodeToText` | (int) → String | Converts SubStatus int to text |
| `ActionResponseEvent` | (Activity) → boolean | IntraActivitySequencing — release next |
| `CCBS_GET_SUBSCRIBER_HEADER_EXTEND` | (orderRequest, eventResponse, i, j, k) → void | Maps SubscriberName2 |
| `MapSubscriberAddressFromGetSubscriberHeader` | (orderRequest, eventResponse, i, j, k) → void | Maps SubscriberAddress (OrderType=129) |
| `MapSubscriberAddress2FromGetSubscriberHeader` | (orderRequest, eventResponse, i, j, k) → void | Maps SubscriberAddress2 (OrderType=129) |

---

## §15 Function Dependency Tree

```text
Request_CCBS_GET_SUBSCRIBER_HEADER (rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()  [on resubmit]
├── GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES")
├── [XSLT payload build — namespace variant]
├── IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity)
├── IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity)
├── GetActivityStatusString("1", false)
├── SendDataToDB()
└── SkipActivity("4")  [skip path]

Response_CCBS_GET_SUBSCRIBER_HEADER (rulefunction)
├── GetActivityParameterValueFromKey(currActivity, "MAP_VALUE")
├── Instance.createInstance(CCBS_GetSubscriberHeaderRes XSLT)
├── [POU loop] BRMS.IsBlankOrStringNull(sub.MSISDN)
├── [POU loop] BRMS.IsBlankOrStringNull(acct.AccountID)  [if MAP_VALUE="ACCOUNT_ID"]
├── [COU+POU loop] OMXUtils.asciiCodeToText(SubStatus)
├── [NameAddress loop]
│   ├── BRMS.IsBlank(field)  [~40 calls, one per name/address field]
│   ├── CCBS_GET_SUBSCRIBER_HEADER_EXTEND()  [SubscriberName2, LinkType=72]
│   ├── MapSubscriberAddressFromGetSubscriberHeader()  [OrderType=129]
│   └── MapSubscriberAddress2FromGetSubscriberHeader()  [OrderType=129]
├── Event.Ext.sendEventImmediate(Logger)
└── IntraActivitySequencing.ActionResponseEvent(currActivity)
```

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Support ALT_CES routing override per-subscriber via activity parameter |
| R2 | Throttle CCBS requests (IntraActivitySequencing) — serial, never parallel per order |
| R3 | Optional credential headers gated by global IsEnableUserPass flag |
| R4 | Enrich: MSISDN backfill, dealerCode, AccountID, subStatus (ASCII-to-text), ConvergenceCode, Language (param-gated) |
| R5 | Map full name for INDY (NameType=73) and CORP (NameType=66) via LinkType=83 |
| R6 | Map extended contact info (Language, PrefContactNumber, HomePhone, etc.) via LinkType=72 |
| R7 | Map 15 AddressElement slots to SubscriberAddress (LinkType=83) and SubscriberAddress2 (LinkType=72) |
| R8 | Apply ClearField erasure pattern — field == global ClearField sentinel → null |
| R9 | Support OrderType=129 (TOL move indy↔corp) via helper rulefunction delegation |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Serialised CCBS calls slower than parallel fan-out | [MEDIUM] | Accept trade-off for CCBS session safety |
| 551-line response rulefunction — hard to unit-test | [HIGH] | Break into atomic services in migration |
| ClearField sentinel comparison — brittle if global changes | [MEDIUM] | Replace with explicit null/empty-check |
| AddressElement1-15 positional mapping — silent data corruption risk | [HIGH] | Replace with named element mapping |
| Two namespace variants (ns1/ns) for identical payload | [MEDIUM] | Unify in REST/JSON successor |
| OrderType=129 silent delegation — no audit trail | [MEDIUM] | Add explicit event logging in migration |

---

## §18 Full Source Code (Request Rule)

```java
/**
 * Request_CCBS_GET_SUBSCRIBER_HEADER
 * Author: warawich-nb
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_SUBSCRIBER_HEADER {
  attribute { validity = ACTION; }
  scope {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when { /* standard OMXFM activation */ }
  then {
    // On resubmit: purge queued-but-unsent requests
    IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

    // Resolve CES endpoint (ALT_CES routing)
    String altParam = GetActivityParameterValueFromKey(orderCurrentActivity, "ALT_CES");
    // ALT_CES logic in XSLT — see §9.2

    // Build JMS request event (POU variant, ns1 prefix)
    // [See §9: GetSubscriberHeaderRequest/SubscriberIdInfo/subscrNumber = SubscriberId]
    // Credential headers added when IsEnableUserPass='true'
    Event reqEvent = Event.createEvent("xslt://{{CCBS_GET_SUBSCRIBER_HEADER}}"
      /* XSLT output: GetSubscriberHeaderRequest — see §9 */);

    // Throttle via IntraActivitySequencing
    IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
    // COU variant: same payload with ns prefix

    // Completion path:
    IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
    String status = GetActivityStatusString("1", false);
    SendDataToDB();

    // Skip path: SkipActivity("4");
  }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

`Response_CCBS_GET_SUBSCRIBER_HEADER.rulefunction` (551 lines):
1. Creates custom `CCBS_GetSubscriberHeaderRes` concept (deterministic extId)
2. Enriches POU subscriber: dealerCode, MSISDN backfill, AccountID (param-gated)
3. Enriches all subscribers: ConvergenceCode, CONVERGENT_CODE, subStatus (ASCII decode), Language (param-gated)
4. Maps Name/Address using LinkType/NameType routing (40+ fields, ClearField erasure)
5. Delegates SubscriberName2 to `CCBS_GET_SUBSCRIBER_HEADER_EXTEND`
6. Delegates OrderType=129 address mapping to helpers
7. Emits audit log, releases next queued request via `ActionResponseEvent`

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order graph — read and enriched |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_GET_SUBSCRIBER_HEADER` | CCBS response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity |

### §19.3 Response Concept Construction

```text
CCBS_GetSubscriberHeaderRes (Concepts.FM.Response)
├── extId           ← JMSCorrelationID + ":CCBS_GET_SUBSCRIBER_HEADER_RES:" + RefID  [Always — deterministic]
├── ResponseCode    ← $eventResponse/ResponseCode    [Conditional]
├── ResponseMessage ← $eventResponse/ResponseMsg     [Conditional]
├── CompletionStatus← $eventResponse/CompletionStatus[Conditional]
└── ReferenceId     ← $eventResponse/RefID           [Conditional]
```

### §19.4 Name/Address Routing Matrix

| LinkType | Code | NameType | Code | Target | Fields |
|----------|------|----------|------|--------|--------|
| 83 | S (Subscriber) | 73 | I (Individual) | SubscriberName (INDY) | Title, FirstName, MiddleName, LastName, MaritalStatus, FaxNumber, Email, Gender, IdentificationType, Identification |
| 83 | S | 66 | B (Business) | SubscriberName (CORP) | OrgName, BranchCode, BranchName, StoreId, FaxNumber, Email, IdentificationType, Identification |
| 72 | H (Extended) | 73 or 66 | — | SubscriberName2 (via helper) | Delegated to CCBS_GET_SUBSCRIBER_HEADER_EXTEND() |
| 83 | S | — | AddressInfo | SubscriberAddress | HouseNo, Moo, RoomNo, Floor, BuildingName, Soi, StreetName, Tumbon, Amphur, City, Zip, Country, TimeAtAddress, TypeOfAccomodation, subSoi |
| 72 | H | — | AddressInfo | SubscriberAddress2 | Same 15 fields as SubscriberAddress |

**LinkType=72 extended contact (SubscriberName fields):**

| NameElement | Field |
|-------------|-------|
| NameElement1 | Language |
| NameElement2 | PrefContactNumber |
| NameElement3 | HomePhone |
| NameElement4 | BizPhone |
| NameElement5 | privatePhone |
| NameElement6 | AuthFirstName |
| NameElement7 | AuthLastName |
| NameElement8 | AuthPersonalId |
| NameElement9 | POAName |
| NameElement10 | POAPersonalId |

### §19.5 ClearField Erasure Pattern

> For every mapped field: if current value (uppercased) == global `ClearField` sentinel → set to `null`. Applied universally to all 40+ name/address fields.

### §19.6 Response Completion

| Call | Return | Effect |
|------|--------|--------|
| `ActionResponseEvent(currActivity)` | "true" | All queued requests handled; activity proceeds |
| `ActionResponseEvent(currActivity)` | "false" | More requests queued; next released from throttle |

> **Note:** No `RequestCount == successResponseCount` fan-in check — completion is managed entirely by `ActionResponseEvent` (IntraActivitySequencing internal).

### §19.7 Response Audit Log

```text
createEvent (Events/OMConsumers/OMXESB/Logger)
└── event
    ├── ESBUUID          ← $orderRequest/OrderData/OMXTrackingId  [Conditional]
    ├── PROCESS_ID       ← concat(pid, "_RES")                    [Always]
    ├── COMPONENT_NAME   ← $globalVariables/OMX_COMMON/.../OMX_CEP[Always]
    ├── OPERATION_NAME   ← "CCBS_GET_SUBSCRIBER_HEADER"           [Always]
    ├── TARGET_SYSTEM    ← $globalVariables/OMX_COMMON/.../OMX_FM [Always]
    ├── LOG_LEVEL        ← INFO                                    [Always]
    ├── AUDIT_TRACE      ← "Response received for CCBS_GET_SUBSCRIBER_HEADER" [Always]
    ├── AUDIT_TS         ← tib:format-dateTime(current-dateTime()) [Always]
    └── payload/ns:ServicePayload ← copy-of $eventResponse        [Conditional: WritePayload="true"]
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
