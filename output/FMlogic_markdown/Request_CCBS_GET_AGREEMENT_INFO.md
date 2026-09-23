# Request_CCBS_GET_AGREEMENT_INFO

> FM Logic Documentation — CCBS Agreement Data Retrieval (Direct Parallel Dispatch per OU, Data Pipeline — enriches Agreement, Offers, Account, CustomerId)

---

## §1 — Overview & Purpose

**CCBS_GET_AGREEMENT_INFO** retrieves full agreement details from CCBS for each OU in the order. It is step 5 in BN_CHANGE_PACKAGE, running only when an Agreement exists and Offers have action CHG_PARAM or ADD. It is a **rich data pipeline FM** that populates Agreement fields (AgreementType, AgreementDescription, AgreementId), enumerates all active service offers from CCBS (creating `AgreementOffers` concepts tagged with `FE_OR_CCBS="CCBS"`), enriches the Customer with `CustomerId`, and creates or links an Account concept with the agreement's AccountID.

Uses **direct parallel dispatch** per OU — one event per ChildOU[k] plus one event per ParentOU[i] itself, all sent immediately via `sendEventImmediate`. Fan-in uses `RequestCount == Response@length` (total responses, not just "000" — any response completes fan-in).

> **Key design notes:**
> - **BN special path (OrderType="128"):** Uses `Instance.serializeUsingDefaults(orderRequest.OrderData)` for PreExecCheck XML — full OrderData needed to evaluate offer actions across all OUs
> - **RefID priority:** Agreement/RefId takes precedence over OU/RefId in the JMS RefID header (`xsl:choose`)
> - **OuID required:** Throws `OMX_DATA_ISSUE` if OUId is blank
> - **FE_OR_CCBS tagging:** Every `AgreementOffers` concept gets `ExtendedInfo[FE_OR_CCBS]="CCBS"` — downstream FMs use this to distinguish CCBS-sourced vs FE/Catalog-sourced offers
> - **ChildOU OfferInstanceId:** Uses `ns:OldOfferInstanceId`; ParentOU uses `ns:OfferInstanceId`
> - **Account AccountID priority:** "Account ID" parameter > "EB Account ID" parameter
> - **No PurgePendingRequestsBeforeResubmit:** Resubmit safety relies on idempotency check only
> - **Fan-in counts ALL responses** (not just "000")

| Attribute | Value |
|-----------|-------|
| Rule file | `Request_CCBS_GET_AGREEMENT_INFO.rule` |
| Response rulefunction | `Response_CCBS_GET_AGREEMENT_INFO.rulefunction` |
| Priority | 5 |
| Backend system | CCBS `GetAgreementInfo` |
| Request event type | `Events.OMConsumers.OMXFM.Request.CCBS_GET_AGREEMENT_INFO` |
| Response event type | `Events.OMConsumers.OMXFM.Response.CCBS_GET_AGREEMENT_INFO` |
| Response concept | `Concepts.FM.Response.CCBS_GetAgreementInfo` (standard ResponseBase fields only) |
| Payload schema | `xsd2: amdocs.csm3g.datatypes.AgreementInfo` |
| Dispatch scope | Per OU — ChildOU[k] and ParentOU[i] (dual dispatch within same loop) |
| Dispatch pattern | Direct parallel — `sendEventImmediate` per OU |
| Idempotency key | `ChildOU.RefId` / `ParentOU.RefId` |
| Fan-in | `currActivity.RequestCount == currActivity.Response@length` (ALL responses) |
| Data pipeline output | Agreement.AgreementType, Agreement.AgreementDescription, Agreement.AgreementId, Agreement.Offers[], customer.CustomerId, Account.AccountID, Account.AgreementRefId, Account.AgreementId |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM priority |
| forwardChain | true | Standard |
| Rule type | Direct parallel dispatch per OU | ChildOU then ParentOU; sendEventImmediate; fan-in via Response@length |
| Resubmit | Idempotency only | No PurgePendingRequestsBeforeResubmit; skip if Response[ReferenceId==refId && CompletionStatus==2]; RequestCount++ only if !isActResub |
| Activity parameters | None | No ALT_CES, no MSISDN, no other activity params read |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order; ParentOU/ChildOU loops; Agreement lookup; OuID; PreExecCheck serialization |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — Response[] for idempotency; RequestCount management; Status |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId matches |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_GET_AGREEMENT_INFO"` | Constrains to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_GET_AGREEMENT_INFO"` | Double-check via NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity ready to process |

> **ProcessConfig PreExecCheck (step 5 gate):** Agreement exists AND Offers.Action = CHG_PARAM or ADD. Evaluated per-OU using either `GetXMLForChildOU`/`GetXMLForOU` (standard) or `Instance.serializeUsingDefaults(OrderData)` (BN OrderType=128).

---

## §5 — Execution Flow Diagram

1. **Resubmit flag** → `isActResub = RequestCount > 0 && IsOrderResubmitted`
2. **Load nextAct** for PreExecCheck text; set `isSkipped = true`
3. **ParentOU[i] loop:**
   - **ChildOU[k] sub-loop:** refId = ChildOU[k].RefId; idempotency check; BN PreExecCheck path; OUId validation; build & send ChildOU variant event; RequestCount++ (if !isActResub); audit Logger
   - **ParentOU[i] self-dispatch:** refId = ParentOU[i].RefId; idempotency check; BN PreExecCheck path; OUId validation; build & send ParentOU variant event; RequestCount++ (if !isActResub)
4. If !isSkipped → `GetActivityStatusString("1", false)` + `SendDataToDB`; else `SkipActivity("4")`

> **BN special path:** When `OrderType=="128"`, PreExecCheck XML is `Instance.serializeUsingDefaults(orderRequest.OrderData)` instead of per-OU helpers.

> **OUId validation:** If OUId is blank, throws `Exception.newException("OMX_DATA_ISSUE", "OUID missing for OU with RefID "+refId, null)` — caught by outer try/catch.

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
try {
    Activity nextAct = Instance.getByExtIdByUri(NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
    boolean isSkipped = true;
    int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
    for(int i=0; i<iPOULen; i++) {
        // ChildOU loop
        int iCOULen = ParentOU[i].ChildOU@length;
        for(int k=0; k<iCOULen; k++) {
            String refId = ParentOU[i].ChildOU[k].RefId;
            // idempotency check on Response[]
            boolean reqSuccess = false;
            if(!reqSuccess) {
                // BN special: OrderType=="128" uses serializeUsingDefaults
                sXML = (OrderType=="128") ? Instance.serializeUsingDefaults(OrderData)
                                          : Helpers.GetXMLForChildOU(orderRequest, refId, POU.RefId);
                // PreExecCheck evaluation
                String OUId = ChildOU[k].OUId;
                if(chkRes=="true") {
                    if(BRMS.IsBlank(OUId)) throw Exception.newException("OMX_DATA_ISSUE", ...);
                    /* XSLT variant 1 (ChildOU): $orderRequest,$i,$k,$POU,$COU,$globalVariables — see §9 */
                    Event.Ext.sendEventImmediate(reqEvent);
                    if(!isActResub) RequestCount++;
                    isSkipped = false;
                    /* unconditional Logger audit */
                }
            }
        }
        // ParentOU self-dispatch
        String refId = ParentOU[i].RefId;
        if(!reqSuccess) {
            sXML = (OrderType=="128") ? Instance.serializeUsingDefaults(OrderData)
                                      : Helpers.GetXMLForOU(orderRequest, refId);
            String OUId = ParentOU[i].OUId;
            if(chkRes=="true") {
                if(BRMS.IsBlank(OUId)) throw Exception.newException("OMX_DATA_ISSUE", ...);
                /* XSLT variant 2 (ParentOU): $orderRequest,$i,$OU,$globalVariables — see §9 */
                Event.Ext.sendEventImmediate(reqEvent);
                if(!isActResub) RequestCount++;
                isSkipped = false;
            }
        }
    }
    if(!isSkipped) { status="1"; SendDataToDB; }
    else { SkipActivity("4"); }
} catch(Exception ae) { HandleActivityException; }
```

---

## §7 — Data Extraction & Pre-Processing

### §7.1 — BN vs Standard PreExecCheck Path

| OrderType | PreExecCheck XML source | Why |
|-----------|------------------------|-----|
| `"128"` (BN) | `Instance.serializeUsingDefaults(orderRequest.OrderData)` | BN PreExecCheck must evaluate offer actions across all OUs — full OrderData XML needed |
| Any other | `GetXMLForChildOU(orderRequest, refId, POU.RefId)` or `GetXMLForOU(orderRequest, refId)` | Standard per-OU XML with namespace for XPath evaluation |

### §7.2 — RefID Header Selection (xsl:choose)

| Condition | RefID source |
|-----------|-------------|
| `string-length(ChildOU[$COU]/Agreement/RefId) > 0` | `ChildOU[$COU]/Agreement/RefId` |
| otherwise | `ChildOU[$COU]/RefId` |
| `string-length(ParentOU[$OU]/Agreement/RefId) > 0` | `ParentOU[$OU]/Agreement/RefId` |
| otherwise | `ParentOU[$OU]/RefId` |

> Note: Idempotency key in the request rule uses the OU's own RefId, but the event's RefID header may be the Agreement RefId. The response RF uses `eventResponse.RefID` to locate the matching OU/Agreement.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in BN_CHANGE_PACKAGE step 5 — critical pipeline step. Agreement data populated here is consumed by CCBS_RESOLVE_SOC_CODE, CCBS_GOD, and all price plan change FMs.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_GET_AGREEMENT_INFO` | CCBS GetAgreementInfo request per OU |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request and response audit (unconditional) |

### §8.3 — Backend API Details

| System | Operation | Schema | Key request field |
|--------|-----------|--------|------------------|
| CCBS | `GetAgreementInfo` | `amdocs.csm3g.datatypes.AgreementInfo` (xsd2 prefix) | `<OuID>` — the OU identifier |

### §8.4 — BE Working Memory Dependencies

| Concept path | Access | Purpose |
|-------------|--------|---------|
| `ParentOU[*].ChildOU[*].RefId` | Read | Idempotency key & RefID fallback |
| `ParentOU[*].ChildOU[*].Agreement.RefId` | Read | Priority RefID header source |
| `ParentOU[*].ChildOU[*].OUId` | Read (required) | OuID payload field — throws OMX_DATA_ISSUE if blank |
| `ParentOU[*].RefId` | Read | Idempotency key & RefID fallback |
| `ParentOU[*].Agreement.RefId` | Read | Priority RefID header source |
| `ParentOU[*].OUId` | Read (required) | OuID payload field |
| `customer.CustomerId` | Write (response RF) | From AgreementInfo/CustomerIdInfo/CustomerNo (if blank) |
| `Agreement.AgreementType` | Write (response RF) | From AgreementTypeInfo/AgreementType (if blank) |
| `Agreement.AgreementGeneralInfo.agreementDescription` | Write (response RF) | From AgreementGeneralInfo/AgreementDescription (if empty) |
| `Agreement.AgreementId` | Write (response RF) | From AgreementIdInfo/AgreementNo (if blank) |
| `Agreement.Offers[]` | Write (response RF) | AgreementOffers concepts created per ns:Services element |
| `Customer.Account[]` | Write (response RF) | Account concept created if not found; AccountID, AgreementRefId, AgreementId set |

### §8.5 — ExtendedInfo Fields

No ExtendedInfo from order input is read. Every created `AgreementOffers` concept receives `ExtendedInfo[FE_OR_CCBS]="CCBS"` injected by the response RF.

### §8.6 — Global Variable Dependencies

| Global Variable Path | Purpose |
|---------------------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | If `"true"` → emit UserName/PassWord in event headers |
| `OMX_OM/WritePayload` | If `"true"` → include full payload in Logger events |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameters

| Param | Variant 1 — ChildOU | Variant 2 — ParentOU |
|-------|--------------------|--------------------|
| `$orderRequest` | orderRequest concept | orderRequest concept |
| `$i` | ParentOU index | ParentOU index |
| `$k` | ChildOU index | – |
| `$POU` | computed: $i+1 (1-indexed) | – |
| `$COU` | computed: $k+1 (1-indexed) | – |
| `$OU` | – | computed: $i+1 (1-indexed) |
| `$globalVariables` | Global variables root | Global variables root |

### §9.2 — Event Container

Event type: `Events.OMConsumers.OMXFM.Request.CCBS_GET_AGREEMENT_INFO`. No `@extId` on event. `OuID` is a top-level field within `<event>` — not inside a namespace-prefixed payload.

### §9.3 — JMS / Event Header & Body Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | [Conditional] |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | [Conditional] |
| `OrderID` | `$orderRequest/OrderData/OrderID` | [Conditional] |
| `RefID` | Agreement/RefId (priority) else OU/RefId — see §7.2 | xsl:choose |
| `UserName` | `$orderRequest/OrderData/User` | [Credential-gated: IsEnableUserPass="true" + exists] |
| `PassWord` | `$orderRequest/OrderData/Password` | [Credential-gated: IsEnableUserPass="true" + exists] |
| `OrderType` | `$orderRequest/OrderData/OrderType` | [Conditional] |
| `CES` | `$orderRequest/OrderData/CES` | [Conditional] (no ALT_CES override) |
| `OuID` | `ChildOU[$COU]/OUId` or `ParentOU[$OU]/OUId` | **Always** |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

**Variant 1 — ChildOU** (params: $orderRequest, $i, $k; $POU=$i+1, $COU=$k+1)

```text
createEvent
└── event  (no @extId)
    ├── JMSPriority          ← $orderRequest/OrderPriority                          [Conditional]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId                [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                       [Conditional]
    ├── RefID  (xsl:choose — Agreement/RefId priority)
    │   ├── when string-length(ChildOU[$COU]/Agreement/RefId)>0:
    │   │   └── ChildOU[$COU]/Agreement/RefId
    │   └── otherwise:
    │       └── ChildOU[$COU]/RefId                                                  [Conditional]
    ├── UserName             ← $orderRequest/OrderData/User                          [Credential-gated]
    ├── PassWord             ← $orderRequest/OrderData/Password                      [Credential-gated]
    ├── OrderType            ← $orderRequest/OrderData/OrderType                     [Conditional]
    ├── CES                  ← $orderRequest/OrderData/CES                           [Conditional]
    └── OuID                 ← ChildOU[$COU]/OUId                                    [Always]
```

> Variant 2 (ParentOU): RefID source changes to `ParentOU[$OU]/Agreement/RefId` or `ParentOU[$OU]/RefId`; OuID from `ParentOU[$OU]/OUId`. All other header fields identical.

**Legend:**
- `[Always]` — emitted unconditionally
- `[Conditional]` — inside `xsl:if` block
- `[Credential-gated]` — conditional on `IsEnableUserPass="true"`

---

## §11 — Audit Logging

| Event | Gate | OPERATION_NAME | AUDIT_TRACE |
|-------|------|----------------|-------------|
| Request audit | **Unconditional** | `"CCBS_GET_AGREEMENT_INFO"` ✓ | `concat("Request Sent for CCBS_GET_AGREEMENT_INFO:", $refId)` |
| Response audit | **Unconditional** | `"CCBS_GET_AGREEMENT_INFO"` ✓ | `concat("Response received for CCBS_GET_AGREEMENT_INFO:", $eventResponse/RefID)` |

> Payload gating via `OMX_OM/WritePayload="true"`. Response audit PROCESS_ID uses `concat($eventResponse/OrderID, "_RES")`.

---

## §12 — Activity Status Management

| Condition | Action | Status |
|-----------|--------|--------|
| At least one OU dispatched | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" = PROCESSING |
| No OUs pass checks | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" = SKIPPED |

---

## §13 — Exception / Error Handling

| Exception | Source | Handler |
|-----------|--------|---------|
| `OMX_DATA_ISSUE: "OUID missing for OU with RefID "+refId` | Explicit throw inside try block when OUId IsBlank | Caught by outer try/catch → `HandleActivityException` |
| Any other exception | CCBS call failure or runtime error | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

> **No PurgePendingRequestsBeforeResubmit.** Resubmit safety relies entirely on idempotency check. If a response was received but CompletionStatus was not set to 2, a resubmit will re-send the event.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `Helpers.GetXMLForChildOU(orderRequest, refId, parentRefId)` | Build PreExecCheck XML for ChildOU (standard path, non-BN) |
| `Helpers.GetXMLForOU(orderRequest, refId)` | Build PreExecCheck XML for ParentOU (standard path, non-BN) |
| `Instance.serializeUsingDefaults(orderRequest.OrderData)` | Full OrderData serialization for BN PreExecCheck (OrderType=128) |
| `Helpers.BRMS.IsBlank(OUId)` | Guard: throw OMX_DATA_ISSUE if OUId missing |
| `Helpers.BRMS.IsBlankOrStringNull(value)` | Null/empty check for enrichment fields (response RF) |
| `Helpers.GetActivityStatusString(code, flag)` | Status code translation |
| `Helpers.SendDataToDB(orderRequest)` | Persist order state |
| `Helpers.SkipActivity(orderRequest, activity, code)` | Mark activity skipped |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |
| `OMXUtils.generateTrackingID()` | Response RF: generate extId for concepts |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_GET_AGREEMENT_INFO (rule)
├── try {
│   ├── Instance.getByExtIdByUri()                   [load nextAct for PreExecCheck]
│   ├── [ParentOU[i] loop]
│   │   ├── [ChildOU[k] inner loop]
│   │   │   ├── [idempotency scan on Response[]]
│   │   │   ├── OrderType=="128" ?
│   │   │   │   ├── YES: Instance.serializeUsingDefaults(orderRequest.OrderData)
│   │   │   │   └── NO:  Helpers.GetXMLForChildOU(orderRequest, refId, POU.RefId)
│   │   │   ├── XPath.execute()                      [PreExecCheck evaluation]
│   │   │   ├── Helpers.BRMS.IsBlank(OUId)           [data guard — throw OMX_DATA_ISSUE]
│   │   │   ├── Event.createEvent()                  [ChildOU XSLT variant — see §9]
│   │   │   ├── Event.Ext.sendEventImmediate()       [direct dispatch]
│   │   │   ├── orderCurrentActivity.RequestCount++  [if !isActResub]
│   │   │   ├── System.nanoTime()
│   │   │   ├── Event.createEvent()                  [Logger XSLT — request audit]
│   │   │   └── Event.Ext.sendEventImmediate()       [audit dispatch]
│   │   └── [ParentOU self-dispatch — same pattern with ParentOU XSLT variant]
│   ├── Helpers.GetActivityStatusString()
│   ├── Helpers.SendDataToDB()
│   └── Helpers.SkipActivity()
└── catch → Helpers.HandleActivityException()

Response_CCBS_GET_AGREEMENT_INFO (rulefunction)
├── OMXUtils.generateTrackingID()                    [extId for CCBS_GetAgreementInfo concept]
├── Instance.createInstance()                        [CCBS_GetAgreementInfo concept XSLT]
├── currActivity.Response[] ← activityRes
├── Helpers.BRMS.IsBlankOrStringNull(customer.CustomerId)
│   └── [if blank] XPath.evalAsString() → customer.CustomerId ← CustomerIdInfo/CustomerNo
├── [ParentOU/ChildOU match loop by responseRefId]
│   ├── [ParentOU match]
│   │   ├── [if AgreementType blank] XPath.evalAsString() → AgreementType
│   │   ├── [if agreementDescription empty] XPath.evalAsString() → agreementDescription
│   │   ├── XPath.evalAsInt() → count(Services)
│   │   ├── [for each Service] Instance.createInstance() [AgreementOffers XSLT]
│   │   │   └── AgreementOffers with FE_OR_CCBS="CCBS" tag injected
│   │   ├── [if AgreementId blank] XPath.evalAsString() → AgreementId
│   │   └── [Account resolution chain]
│   │       ├── XPath.evalAsString() → accountId lookup by AgreementRefId
│   │       ├── Instance.getByExtIdByUri()           [try find existing Account]
│   │       ├── [if null] Instance.createInstance()  [create new Account concept]
│   │       ├── XPath.evalAsString() → indy_accountId ("Account ID" parameter)
│   │       ├── XPath.evalAsString() → eb_AccountId ("EB Account ID" parameter)
│   │       └── account.AccountID ← indy_accountId (priority) else eb_AccountId
│   └── [ChildOU match — same pattern; OfferInstanceId from OldOfferInstanceId]
├── Event.createEvent()                              [Logger XSLT — response audit]
├── Event.Ext.sendEventImmediate()                   [response audit]
└── currActivity.RequestCount == currActivity.Response@length
    → return "true" / "false"
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | Both | OrderData.Customer.ParentOU[]/ChildOU[]/Agreement, OrderData.OrderType, OrderData.CES |
| `Concepts.OM.ProcessConfig.Activity` | Both | RequestCount, Response[], Status |
| `Concepts.FM.Response.CCBS_GetAgreementInfo` | Response RF | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |
| `Concepts.OrderRequest.OrderElements.AgreementOffers` | Response RF (created) | OfferName, ServiceType, Soc, RelatedOffersArray[], SocProperties, OfferInstanceId, ParentOfferInstanceId, ServiceLevel, ExtendedInfo[FE_OR_CCBS] |
| `Concepts.OrderRequest.OrderElements.Agreement` | Response RF (write) | AgreementType, AgreementId, AgreementGeneralInfo.agreementDescription, Offers[] |
| `Concepts.OrderRequest.OrderElements.Customer` | Response RF (write) | CustomerId, Account[] |
| `Concepts.OrderRequest.OrderElements.Account` | Response RF (created/write) | RefId, AccountID, AgreementRefId, AgreementId |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Dispatch one CCBS GetAgreementInfo call per ChildOU and per ParentOU; send `OuID` as the request identifier |
| R2 | BN path (OrderType=128): evaluate PreExecCheck against full OrderData XML, not per-OU XML |
| R3 | RefID header priority: Agreement/RefId > OU/RefId |
| R4 | Guard: throw OMX_DATA_ISSUE if OUId is blank — do not send event without OU identifier |
| R5 | Fan-in: `RequestCount == Response@length` (all responses, not just "000") |
| R6 | Enrich Agreement: AgreementType, AgreementDescription, AgreementId (all only if currently blank) |
| R7 | Create AgreementOffers per ns:Services entry; each must be tagged `ExtendedInfo[FE_OR_CCBS]="CCBS"` |
| R8 | ChildOU AgreementOffers: OfferInstanceId from `ns:OldOfferInstanceId`; ParentOU: from `ns:OfferInstanceId` |
| R9 | AccountID resolution: "Account ID" parameter takes precedence over "EB Account ID"; both must be non-blank and non-"0" |
| R10 | Enrich `customer.CustomerId` from `AgreementInfo/CustomerIdInfo/CustomerNo` if currently blank |

### Design Notes

| Note | Severity | Detail |
|------|----------|--------|
| **Fan-in uses Response@length (not "000" count):** Any response — success or failure — advances the fan-in counter. An error response from CCBS still allows the RF to return "true" once RequestCount is met. | [MEDIUM] | Contrast with other FMs using `count(Response[code ends "000"])` — this FM completes fan-in regardless of response status |
| **No PurgePendingRequestsBeforeResubmit:** Relies only on idempotency check. If CompletionStatus was not set to 2 for a response, resubmit will re-send the request. | [MEDIUM] | Should verify whether CCBS GetAgreementInfo is idempotent at the CCBS level |
| **FE_OR_CCBS="CCBS" tag is critical:** Downstream FMs check this tag to determine which offers to process. Missing this tag would cause offers to be treated as FE-sourced. | [HIGH] | Must be preserved in any migration or re-implementation |
| **ChildOU OfferInstanceId uses OldOfferInstanceId:** CCBS API returns different field names per agreement level. The "old" suffix may refer to the original offer instance before a pending change. | [INFO] | Verify with CCBS team whether this distinction is intentional |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_GET_AGREEMENT_INFO {
    attribute { priority = 5; forwardChain = true; }
    declare { OrderRequest orderRequest; Activity orderCurrentActivity; }
    when { /* extId / ActivityID / NextActivityID / Status == "WAITING" */ }
    then {
        boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
        try {
            Activity nextAct = Instance.getByExtIdByUri(...);
            boolean isSkipped = true;
            for(int i...) {
                // ChildOU loop
                for(int k...) {
                    refId = ChildOU[k].RefId;
                    // idempotency check
                    if(!reqSuccess) {
                        sXML = (OrderType=="128") ? Instance.serializeUsingDefaults(OrderData)
                                                  : Helpers.GetXMLForChildOU(...);
                        // PreExecCheck; OUId guard
                        if(chkRes=="true") {
                            if(BRMS.IsBlank(OUId)) throw Exception.newException("OMX_DATA_ISSUE", ...);
                            /* XSLT ChildOU variant ($i,$k,$POU,$COU) — see §9 */
                            Event.Ext.sendEventImmediate(reqEvent);
                            if(!isActResub) RequestCount++;
                            isSkipped = false;
                            /* Logger audit (unconditional) */
                        }
                    }
                }
                // ParentOU self-dispatch
                refId = ParentOU[i].RefId;
                if(!reqSuccess) {
                    sXML = (OrderType=="128") ? Instance.serializeUsingDefaults(OrderData)
                                              : Helpers.GetXMLForOU(...);
                    if(chkRes=="true") {
                        if(BRMS.IsBlank(OUId)) throw Exception.newException("OMX_DATA_ISSUE", ...);
                        /* XSLT ParentOU variant ($i,$OU) — see §9 */
                        Event.Ext.sendEventImmediate(reqEvent);
                        if(!isActResub) RequestCount++;
                        isSkipped = false;
                    }
                }
            }
            if(!isSkipped) { status="1"; SendDataToDB; }
            else { SkipActivity("4"); }
        } catch(Exception ae) { HandleActivityException; }
    }
}
```

---

## §19 — Response Message Rule (Response_CCBS_GET_AGREEMENT_INFO)

### §19.1 — Overview

Parses CCBS GetAgreementInfo response, enriches working memory Agreement and Customer concepts, creates AgreementOffers per CCBS service (each tagged `FE_OR_CCBS="CCBS"`), creates or links Account concepts with AccountID, and performs fan-in completion check.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context; OU/Agreement/Account lookup & enrichment targets |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_GET_AGREEMENT_INFO` | CCBS response; carries RefID, ResponseCode, payload with xsd2:AgreementInfo |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] written to; RequestCount for fan-in |

### §19.3 — CCBS_GetAgreementInfo Concept Construction

```text
createObject  (Concepts.FM.Response.CCBS_GetAgreementInfo)
└── object
    ├── @extId         ← OMXUtils:generateTrackingID()          [Always]
    ├── ResponseCode   ← $eventResponse/ResponseCode            [Conditional]
    ├── ResponseMessage ← $eventResponse/ResponseMsg            [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus      [Conditional]
    └── ReferenceId    ← $eventResponse/RefID                   [Conditional]
```

### §19.4 — AgreementOffers Concept Construction (per ns:Services entry)

```text
createObject  (Concepts.OrderRequest.OrderElements.AgreementOffers)
└── object
    ├── @extId                ← OMXUtils:generateTrackingID()              [Always]
    ├── OfferName             ← ns:Name                                     [Conditional]
    ├── ServiceType           ← ns:ServiceType                              [Conditional]
    ├── Soc                   ← ns:Soc                                      [Conditional]
    ├── RelatedOffersArray[]  (xsl:for-each ns:RelatedOffers)
    │   ├── OfferName         ← ns:Name
    │   ├── ServiceType       ← ns:ServiceType
    │   └── Soc               ← ns:Soc
    ├── SocProperties         ← ns:SocProperties                            [Conditional]
    ├── OfferInstanceId       ← ParentOU: ns:OfferInstanceId
    │                            ChildOU:  ns:OldOfferInstanceId             [Conditional]
    ├── ParentOfferInstanceId ← ns:ParentOfferInstanceId                    [Conditional]
    ├── ServiceLevel          ← ns:ServiceLevel                              [Conditional]
    └── ExtendedInfo (injected — always)
        ├── Name              ← "FE_OR_CCBS"                                [Always]
        └── Value             ← "CCBS"                                      [Always]
```

### §19.5 — Working Memory Enrichment Summary

| Target | Source | Condition |
|--------|--------|-----------|
| `customer.CustomerId` | `AgreementInfo/CustomerIdInfo/CustomerNo` | IsBlankOrStringNull(CustomerId) |
| `agreement.AgreementType` | `AgreementInfo/AgreementTypeInfo/AgreementType` | IsBlankOrStringNull(AgreementType) |
| `agreement.AgreementGeneralInfo.agreementDescription` | `AgreementInfo/AgreementGeneralInfo/AgreementDescription` | AgreementGeneralInfo != null && description == "" |
| `agreement.Offers[]` | count(AgreementInfo/Services) → creates AgreementOffers per item | Always (0..N) |
| `agreement.AgreementId` | `AgreementInfo/AgreementIdInfo/AgreementNo` | IsBlankOrStringNull(AgreementId) |
| `account.AccountID` | Parameters["Account ID"]/Values (priority) else Parameters["EB Account ID"]/Values | Both values must be non-blank and != "0" |
| `account.AgreementRefId` | `responseRefId` | Always (when account resolved) |
| `account.AgreementId` | `agreement.AgreementId` | Always (when account resolved) |

### §19.6 — Response Completion Logic (Fan-in)

| Step | Logic |
|------|-------|
| Fan-in check | `currActivity.RequestCount == currActivity.Response@length` |
| Return "true" | All OU requests have responded (any status — success or failure) |
| Return "false" | Still waiting for more OU responses |

> **Fan-in counts ALL responses** (not just ResponseCode ending in "000"). This differs from most other FMs. Error handling relies on the response RF processing the ResponseCode and CompletionStatus appropriately.

### §19.7 — Response Audit Logging

| Field | Value |
|-------|-------|
| `OPERATION_NAME` | `"CCBS_GET_AGREEMENT_INFO"` ✓ |
| `AUDIT_TRACE` | `concat("Response received for CCBS_GET_AGREEMENT_INFO:", $eventResponse/RefID)` ✓ |
| Gate | **Unconditional** |
| `PROCESS_ID` | `concat($eventResponse/OrderID, "_RES")` |
| payload | Full `$eventResponse` copy, gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
