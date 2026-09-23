# Request_CRM_UPSERT_CUSTOMER_ACCOUNT

> FM Logic Documentation — CRM Customer Account Upsert (IntraActivitySequencing, per-subscriber, with CRM ID writeback)

**Rule:** `Rules.OMConsumers.OMXFM.Request.Request_CRM_UPSERT_CUSTOMER_ACCOUNT` | **Priority:** 5 | **Backend:** CRM (CRMUpsertCustomerAccount) | **Pattern:** IntraActivitySequencing per-subscriber

---

## §1 — Overview & Purpose

**CRM_UPSERT_CUSTOMER_ACCOUNT** creates or updates a customer account record in the CRM system. Unlike CCP FMs which iterate per offer, this FM iterates per **subscriber** (both ParentOU and ChildOU). It builds a rich customer payload including personal details, identity documents, address, and contact information, then dispatches each subscriber sequentially via IntraActivitySequencing.

The response RF has two critical side effects beyond fan-in: it **extracts and writes back the CRM customer row ID** (`CustomerCrmId`) from the response into the order concept, enabling downstream activities to reference the CRM record.

> **Correctly wired IntraActivitySequencing** with `ActionResponseEvent`. Response audit correctly gated by `AllowWriteLog` — unlike CCP FMs which had unconditional response audits.

| Attribute | Value |
|-----------|-------|
| Rule file | `Request_CRM_UPSERT_CUSTOMER_ACCOUNT.rule` |
| Response rulefunction | `Response_CRM_UPSERT_CUSTOMER_ACCOUNT.rulefunction` |
| Priority | 5 |
| Backend system | CRM via ESB (`CRMUpsertCustomerAccount`) |
| Request event type | `Events.OMConsumers.OMXFM.Request.CRM_UPSERT_CUSTOMER_ACCOUNT` |
| Response event type | `Events.OMConsumers.OMXFM.Response.CRM_UPSERT_CUSTOMER_ACCOUNT` |
| Response concept | `Concepts.FM.Base.ResponseBase` |
| Payload schema | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/CRM/CRMUpsertCustomerAccount.xsd` |
| Dispatch scope | Per Subscriber — both ParentOU and ChildOU |
| refId key | `sub.RefId` (subscriber RefId — not offer-based) |
| Activity parameters | `mode` (upsert mode) and `upsertAccountStatus` from ProcessConfig |
| Response side effect | Writes `customerRowId` from CRM response back to `orderRequest.OrderData.Customer.CustomerCrmId` |

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| priority | 5 | Standard FM priority |
| forwardChain | true | Enables forward chaining |
| Rule type | IntraActivitySequencing | Per-subscriber sequential dispatch |
| Resubmit | Yes | `PurgePendingRequestsBeforeResubmit` + idempotency skip |
| Skip mechanism | Yes | Skips if no subscribers pass checks; individual subscribers skipped if CompletionStatus=2 |
| Author | CHAYATORN-PC | Different from other FMs in this flow |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order, including customer info, subscribers, dates; `CustomerCrmId` written back by response RF |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity — IntraActivitySequencing queue, Response[] for idempotency |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity extId matches |
| 2 | `orderCurrentActivity.ActivityID == "CRM_UPSERT_CUSTOMER_ACCOUNT"` | Constrains to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CRM_UPSERT_CUSTOMER_ACCOUNT"` | Double-check via NextActivityID |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity ready |

---

## §5 — Execution Flow Diagram

1. **Resubmit purge** — if `isActResub`: `PurgePendingRequestsBeforeResubmit`
2. **Load activity config** — read `nextAct.PreExecCheck`
3. **ParentOU subscriber loop** — for each ParentOU → Subscriber:
   - `refId = sub.RefId`
   - **Idempotency check**: scan `currActivity.Response[]` for `ReferenceId == refId && CompletionStatus == 2`
   - Per-subscriber **PreExecCheck** via `GetXMLForSubscriber(orderRequest, refId)`
   - **Activity parameters**: read `mode` and `upsertAccountStatus` from ProcessConfig
   - **Date pre-processing**: compute `submissionDateFormat`, `identificationExpDateFormat` (with auto-extend), `birthDateFormat`
   - **Title transformation**: `TitleTransformer2(sub.SubscriberName.Title)` → fallback to CustomerName.Title
   - Build XSLT event → `assertEvent` → `ActionRequestEvent`
   - Audit log (gated on `AllowWriteLog`)
4. **ChildOU subscriber loop** — same pattern (no ChildOU index bug)
5. **Dispatch first** — `IntraActivitySequencing.SendFirstRequestEvent`
6. **Status** — `GetActivityStatusString("1", false)` + `SendDataToDB`; or `SkipActivity("4")`

> **Per-subscriber (not per-offer):** This FM dispatches one CRM request per subscriber, not per offer. The refId is the subscriber's RefId, and there is no inner offer loop.

---

## §6 — Rule Action (THEN) — Annotated Logic

```java
boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
try {
    if(isActResub) IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);

    for(int i=0; i < iPOULen; i++) {
        for(int j=0; j < iSubscriberLen; j++) {
            Subscriber sub = ParentOU[i].Subscriber[j];
            String refId = sub.RefId; // subscriber RefId — not offer

            // Idempotency: skip if Response[ReferenceId==refId && CompletionStatus==2]
            for(int iResp=0; ...) { ... }

            if(!reqSuccess) {
                // PreExecCheck via GetXMLForSubscriber (not offer-based helper)
                if(String.equals(chkRes, "true")) {
                    String mode = GetActivityParameterValueFromKey(orderCurrentActivity, "mode");
                    String upsertAccountStatus = GetActivityParameterValueFromKey(orderCurrentActivity, "upsertAccountStatus");

                    // === Date pre-processing (BE code, not XSLT) ===
                    DateTime submissionDate = orderRequest.SubmissionDate;
                    // → translate to Asia/Bangkok → format "yyyy-MM-dd'T'HH:mm:ss.SSSZ"

                    DateTime identificationExpDate = CustomerGeneralInfo.IdentificationExpDate;
                    // → if expired (≤ RawSubmissionDate): addYear(identificationExpDate, 10)
                    // → translate to Asia/Bangkok → format "yyyy-MM-dd'T'HH:mm:ss.SSSZ"

                    DateTime birthDate = CustomerGeneralInfo.BirthDate;
                    // → translate to Asia/Bangkok → format "yyyy-MM-dd'T'HH:mm:ss.SSSZ"

                    // === Title transformation (BE code) ===
                    String title = "";
                    if(sub.SubscriberName != null)
                        title = Transformers.TitleTransformer2(sub.SubscriberName.Title);
                    else if(CustomerName != null && CustomerName.Title != "")
                        title = Transformers.TitleTransformer2(CustomerName.Title);

                    // [XSLT: CRMUpsertCustomerAccountRequest — see §9]
                    Event.assertEvent(reqEvent);
                    IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                    isSkipped = false;
                    if(AllowWriteLog(OrderType)) { /* audit (no refId in AUDIT_TRACE) */ }
                }
            }
        }
    }

    // ChildOU Subscriber loop — same pattern (correct index usage, no bug)

    if(!isSkipped) {
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
    } else {
        SkipActivity(orderRequest, orderCurrentActivity, "4");
    }
} catch(Exception ae) {
    HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §7 — Data Extraction & Pre-Processing

### §7.1 — Activity Parameters (ProcessConfig-driven)

| Parameter key | Target field | Notes |
|---------------|-------------|-------|
| `mode` | `ns:mode` | CRM upsert mode (e.g. "CREATE", "UPDATE") — from ProcessConfig, not order data |
| `upsertAccountStatus` | `ns:status` | Account status to set in CRM — from ProcessConfig |

### §7.2 — Date Pre-Processing (BE code, before XSLT)

| Field | Source | Processing | Format |
|-------|--------|-----------|--------|
| `submissionDateFormat` | `orderRequest.SubmissionDate` | Translate to Asia/Bangkok | `yyyy-MM-dd'T'HH:mm:ss.SSSZ` |
| `identificationExpDateFormat` | `CustomerGeneralInfo.IdentificationExpDate` | If expired (≤ RawSubmissionDate): **auto-extend by 10 years**; then translate to Asia/Bangkok | `yyyy-MM-dd'T'HH:mm:ss.SSSZ` |
| `birthDateFormat` | `CustomerGeneralInfo.BirthDate` | Translate to Asia/Bangkok | `yyyy-MM-dd'T'HH:mm:ss.SSSZ` |

> **ID Expiry Auto-Extension:** If `IdentificationExpDate <= RawSubmissionDate` (expired at order submission time), the date is automatically extended by 10 years before sending to CRM. This is a hidden business rule — CRM may receive an ID expiry date that differs from the original data.

### §7.3 — Title Transformation

Title is resolved by priority: **subscriber-level** (`sub.SubscriberName.Title`) → **customer-level** (`CustomerName.Title`) → empty string. The raw title is then passed through `RuleFunctions.Transformers.TitleTransformer2()` to normalize/map title codes.

### §7.4 — Name Resolution Priority Chains

| Field | OrderType '51'/'74' | Otherwise (priority chain) |
|-------|---------------------|--------------------------|
| `ns:firstName` | `sub/MSISDN` | sub.SubscriberName.FirstName → CustomerName.FirstName → `OrderData.Channel` (fallback) |
| `ns:lastName` | `sub/MSISDN` | sub.SubscriberName.LastName → CustomerName.LastName → `"Prepaid"` (hardcoded!) |

> **Hardcoded "Prepaid" lastName:** The final fallback for `ns:lastName` is the literal string `"Prepaid"` (xsl:otherwise). In PREPAID_REGISTRATION flows where no name data is present, CRM will receive lastName="Prepaid". This is likely intentional for anonymous prepaid registrations but masks the lack of data.

### §7.5 — Address Priority Fallback

| Priority | Source | Condition |
|----------|--------|-----------|
| 1 (primary) | Subscriber-level: `sub/SubscriberAddress` | If any address field has non-zero length |
| 2 (fallback) | Customer-level: `CustomerAddress` | If subscriber address absent/empty |

Address fields sent: type='Customer', houseNo, moo, roomNo, floor, building, soi, street, province (City→province), district (Amphur→district), subDistrict (Tumbon→subDistrict), postalCode (Zip→postalCode), typeOfAccommodation (source field is spelled `TypeOfAccomodation` — single 'm')

### §7.6 — AccountSubType Cross-Reference

`ns:accountSubType` is resolved by XPath cross-reference: `$orderRequest/OrderData/Customer/Account[RefId=$sub/AccountRefId]/AccountManagementInfo/AccountSubType`

### §7.7 — ID Number Space Stripping

`ns:idNumber` uses `translate(Identification, " ", "")` — removes all spaces from the ID number string before sending to CRM.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

| OrderType | Effect |
|-----------|--------|
| '51' or '74' | Use `sub/MSISDN` as both `firstName` and `lastName` (identity masking) |
| All others | Normal name resolution chain (sub → customer → fallback) |

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CRM_UPSERT_CUSTOMER_ACCOUNT` | CRM customer upsert per subscriber (sequential) |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Request audit (AllowWriteLog-gated); static AUDIT_TRACE (no refId) |

### §8.3 — Backend API Details

| System | Operation | Protocol | Response schema |
|--------|-----------|---------|----------------|
| CRM | CRMUpsertCustomerAccount | JMS async (IntraActivitySequencing) | `CRMUpsertCustomerAccount.xsd` |

### §8.4 — BE Working Memory Dependencies

| Concept path | Access | Purpose |
|-------------|--------|---------|
| `ParentOU[*].Subscriber[*].RefId` | Read | refId — idempotency key and JMS RefID header |
| `ParentOU[*].Subscriber[*].AccountRefId` | Read | Cross-references Account for accountSubType lookup |
| `ParentOU[*].Subscriber[*].MSISDN` | Read | Name override for OrderType '51'/'74' |
| `ParentOU[*].Subscriber[*].SubscriberName.*` | Read | Title, FirstName, LastName, Email, Gender, MaritalStatus, BizPhone, HomePhone, OrgName |
| `ParentOU[*].Subscriber[*].SubscriberAddress.*` | Read | Subscriber-level address (primary over CustomerAddress) |
| `Customer.CustomerName.*` | Read | Fallback for name, email, phone fields |
| `Customer.CustomerTypeInfo.Type` | Read | accountType: '80'=Individual (else Business) |
| `Customer.CustomerGeneralInfo.IdentificationExpDate` | Read/Write | ID expiry — auto-extended 10 years if expired at submission |
| `Customer.CustomerAddress.*` | Read | Fallback address; Country for identification block |
| `Customer.Account[RefId=...].AccountManagementInfo.AccountSubType` | Read | Cross-referenced via sub.AccountRefId |
| `orderRequest.OrderData.Customer.CustomerCrmId` | **WRITE** | Response RF writes the CRM-returned customerRowId here |
| `orderRequest.OrderData.OrderType` | Read | Name masking (51/74) + AllowWriteLog gate |
| `orderRequest.OrderData.Channel` | Read | firstName fallback when no name data |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameters

| Param | Source |
|-------|--------|
| `$orderRequest` | orderRequest concept |
| `$refId` | sub.RefId |
| `$mode` | Activity parameter "mode" |
| `$upsertAccountStatus` | Activity parameter "upsertAccountStatus" |
| `$submissionDateFormat` | Pre-computed string: Bangkok-TZ SubmissionDate |
| `$sub` | ParentOU or ChildOU Subscriber concept |
| `$identificationExpDateFormat` | Pre-computed string: Bangkok-TZ IdentificationExpDate (auto-extended) |
| `$title` | Pre-computed: TitleTransformer2 result |
| `$birthDateFormat` | Pre-computed string: Bangkok-TZ BirthDate |

### §9.2 — Event Container

Event extId set via `<xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/>` — unique per request, not from orderRequest.

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$refId` (sub.RefId) | Always |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Always |

### §9.4 — Payload Root Element

`ns:CRMUpsertCustomerAccountRequest` — same namespace and structure for both ParentOU and ChildOU (only `$sub` param differs).

### §9.5 — Core ns:customer Fields

| XML element | Source | Condition |
|-------------|--------|-----------|
| `ns:mode` | `$mode` (activity parameter) | Always |
| `ns:status` | `$upsertAccountStatus` (activity parameter) | Always |
| `ns:transID` | `$orderRequest/OrderData/OMXTrackingId` | Conditional |
| `ns:statusDate` | `$submissionDateFormat` | Always |
| `ns:accountType` | `"Individual"` if Type='80', else `"Business"` | Always |
| `ns:accountSubType` | `Account[RefId=$sub/AccountRefId]/AccountManagementInfo/AccountSubType` | Always |
| `ns:customerSince` | `$submissionDateFormat` | Always |

### §9.6 — ns:identification Block

Entire block conditional: emitted only if any of Identification, IdentificationType, or identificationExpDateFormat is non-empty.

| Element | Source | Notes |
|---------|--------|-------|
| `ns:idNumber` | `translate(Identification, " ", "")` | Spaces stripped |
| `ns:idType` | `IdentificationType` | Conditional |
| `ns:expiryDate` | `$identificationExpDateFormat` | May be 10 years beyond original if auto-extended |
| `ns:country` | `CustomerAddress/Country` | Conditional |

### §9.7 — ns:individual Block (CustomerTypeInfo/Type='80')

| Element | Source | Notes |
|---------|--------|-------|
| `ns:title` | `$title` (TitleTransformer2 result) | Conditional |
| `ns:firstName` | MSISDN if OrderType 51/74; else sub.FirstName → CustomerName.FirstName → `Channel` | Cascading fallback |
| `ns:lastName` | MSISDN if OrderType 51/74; else sub.LastName → CustomerName.LastName → `"Prepaid"` | Hardcoded fallback |
| `ns:birthDate` | `$birthDateFormat` | Conditional |
| `ns:emailAddress` | sub.Email → CustomerName.Email | Conditional |
| `ns:occupation` | `CustomerGeneralInfo.Occupation` | Conditional |
| `ns:gender` | sub.Gender → CustomerName.Gender | Conditional |
| `ns:maritalStatus` | sub.MaritalStatus (skip 'N/A') → CustomerName.MaritalStatus (skip 'N/A') | 'N/A' filtered out |
| `ns:workPhoneNo` | sub.BizPhone → CustomerName.BizPhone | Conditional |
| `ns:homePhoneNo` | sub.HomePhone → CustomerName.HomePhone | Conditional |
| `ns:nationality` | `CustomerGeneralInfo.Nationality` | Conditional |

### §9.8 — ns:business Block (CustomerTypeInfo/Type≠'80')

| Element | Source | Notes |
|---------|--------|-------|
| `ns:organizationName` | sub.OrgName → CustomerName.OrgName | Conditional |
| `ns:phoneNumber` | sub.BizPhone → CustomerName.BizPhone | Conditional |
| `ns:emailAddress` | sub.Email → CustomerName.Email | Conditional |

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── @extId                ← OMXUtils:generateTrackingID()                                  [Always]
    ├── JMSPriority           ← $orderRequest/OrderPriority                                    [Always]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId                          [Always]
    ├── OrderID               ← $orderRequest/OrderData/OrderID                                [Always]
    ├── RefID                 ← $refId (sub.RefId)                                             [Always]
    ├── OrderType             ← $orderRequest/OrderData/OrderType                              [Always]
    └── payload
        └── ns:CRMUpsertCustomerAccountRequest
            └── ns:customer
                ├── ns:mode               ← $mode (activity param)                            [Always]
                ├── ns:status             ← $upsertAccountStatus (activity param)             [Always]
                ├── ns:transID            ← $orderRequest/OrderData/OMXTrackingId             [Conditional]
                ├── ns:statusDate         ← $submissionDateFormat (Bangkok TZ)                [Always]
                ├── ns:accountType        ← "Individual" if Type='80'; else "Business"        [Always]
                ├── ns:accountSubType     ← Account[RefId=$sub/AccountRefId]/...SubType       [Always]
                ├── ns:customerSince      ← $submissionDateFormat                             [Always]
                ├── ns:identification     [Conditional: if any of Identification/idType/expiryDate non-empty]
                │   ├── ns:idNumber       ← translate(Identification, " ", "")  [Spaces stripped]
                │   ├── ns:idType         ← IdentificationType                               [Conditional]
                │   ├── ns:expiryDate     ← $identificationExpDateFormat                     [Conditional: AUTO-EXTENDED]
                │   └── ns:country        ← CustomerAddress/Country                          [Conditional]
                ├── ns:address            [xsl:choose: subscriber addr if present; else CustomerAddress]
                │   ├── ns:type           ← "Customer"                                       [Always - static]
                │   ├── ns:houseNo, ns:moo, ns:roomNo, ns:floor, ns:building, ns:soi, ns:street  [Conditional]
                │   ├── ns:province       ← City                                             [Conditional]
                │   ├── ns:district       ← Amphur                                           [Conditional]
                │   ├── ns:subDistrict    ← Tumbon                                           [Conditional]
                │   ├── ns:postalCode     ← Zip                                              [Conditional]
                │   └── ns:typeOfAccommodation ← TypeOfAccomodation (single-m in source)    [Conditional]
                ├── ns:individual         [Conditional: if CustomerTypeInfo/Type = '80']
                │   ├── ns:title          ← $title (TitleTransformer2)                       [Conditional]
                │   ├── ns:firstName      ← MSISDN (51/74) or sub.FirstName → CustomerName.FirstName → Channel  [xsl:choose]
                │   ├── ns:lastName       ← MSISDN (51/74) or sub.LastName → CustomerName.LastName → "Prepaid"  [HARDCODED FALLBACK]
                │   ├── ns:birthDate      ← $birthDateFormat                                 [Conditional]
                │   ├── ns:emailAddress   ← sub.Email → CustomerName.Email                  [Conditional]
                │   ├── ns:occupation     ← CustomerGeneralInfo.Occupation                  [Conditional]
                │   ├── ns:gender         ← sub.Gender → CustomerName.Gender                [Conditional]
                │   ├── ns:maritalStatus  ← sub/CustomerName.MaritalStatus (skip N/A)       [Conditional]
                │   ├── ns:workPhoneNo    ← sub.BizPhone → CustomerName.BizPhone            [Conditional]
                │   ├── ns:homePhoneNo    ← sub.HomePhone → CustomerName.HomePhone          [Conditional]
                │   └── ns:nationality    ← CustomerGeneralInfo.Nationality                 [Conditional]
                └── ns:business           [Conditional: if CustomerTypeInfo/Type ≠ '80']
                    ├── ns:organizationName ← sub.OrgName → CustomerName.OrgName            [Conditional]
                    ├── ns:phoneNumber    ← sub.BizPhone → CustomerName.BizPhone            [Conditional]
                    └── ns:emailAddress   ← sub.Email → CustomerName.Email                  [Conditional]
```

---

## §11 — Audit Logging

| Event | Gate | Key fields |
|-------|------|-----------|
| Request audit (per subscriber) | `AllowWriteLog(OrderType)` | `OPERATION_NAME="CRM_UPSERT_CUSTOMER_ACCOUNT"`, `AUDIT_TRACE="Request Sent for CRM_UPSERT_CUSTOMER_ACCOUNT"` — static, no refId in trace |
| Response audit | `AllowWriteLog(OrderType)` | `OPERATION_NAME="CRM_UPSERT_CUSTOMER_ACCOUNT"`, `AUDIT_TRACE="Response received for CRM_UPSERT_CUSTOMER_ACCOUNT"` |

> **Response audit correctly gated:** Unlike CCP FMs, the response RF also gates its audit on `AllowWriteLog(OrderType)`. Consistent behavior between request and response.

---

## §12 — Activity Status Management

| Condition | Action | Status |
|-----------|--------|--------|
| At least one subscriber queued | `SendFirstRequestEvent` + `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" = PROCESSING |
| No subscribers pass checks | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" = SKIPPED |

---

## §13 — Exception / Error Handling

**Request rule:** Standard `catch(Exception ae) → HandleActivityException`.

**Response RF:** No try/catch or try/finally — bare body. Any exception propagates to the BE rule engine. Given that the response RF writes back to the order concept (`CustomerCrmId`), an exception before that write would leave the order without the CRM ID even if the CRM call succeeded.

> **Write-back risk:** If `ActionResponseEvent` throws after writing `CustomerCrmId`, or if the XPath extraction fails, the activity fan-in may not complete correctly. Add try-catch to protect state consistency.

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()` | Clears queue for clean resubmit |
| `IntraActivitySequencing.ActionRequestEvent(event, activity)` | Enqueues subscriber event for sequential dispatch |
| `IntraActivitySequencing.SendFirstRequestEvent(activity)` | Dispatches first queued subscriber |
| `IntraActivitySequencing.ActionResponseEvent(currActivity)` | Dispatches next queued subscriber; returns true when queue exhausted |
| `Helpers.GetXMLForSubscriber(orderRequest, refId)` | Builds PreExecCheck XML for a specific subscriber (per-subscriber, not per-offer) |
| `Helpers.GetActivityParameterValueFromKey(activity, key)` | Reads ProcessConfig activity parameter by key |
| `Transformers.TitleTransformer2(title)` | Normalizes/maps title code to CRM-compatible value |
| `Helpers.AllowWriteLog(orderType)` | Both request and response audit gate |
| `Helpers.GetActivityStatusString(code, flag)` | Status code translation |
| `Helpers.SendDataToDB(orderRequest)` | Persist order state |
| `Helpers.SkipActivity(orderRequest, activity, code)` | Mark activity skipped |
| `Helpers.HandleActivityException(orderRequest, activity, ex, msg)` | Error state transition |

---

## §15 — Function Dependency Tree

```text
Request_CRM_UPSERT_CUSTOMER_ACCOUNT (rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit()  [on resubmit]
├── Instance.getByExtIdByUri()
├── Helpers.GetXMLForSubscriber()                                 [PreExecCheck per subscriber]
├── XPath.execute()                                               [PreExecCheck evaluation]
├── Helpers.GetActivityParameterValueFromKey()                    [mode, upsertAccountStatus params]
├── DateTime.translateTime() × 3                                  [submissionDate, expDate, birthDate]
├── DateTime.format() × 3
├── XPath.evalAsString()                                          [RawSubmissionDate for expiry check]
├── DateTime.parseString()
├── DateTime.before() / DateTime.equals()
├── DateTime.addYear()                                            [10-year ID expiry extension]
├── Transformers.TitleTransformer2()                              [title normalization]
├── Event.createEvent()                                           [XSLT — same template for ParentOU/ChildOU]
├── Event.assertEvent()
├── IntraActivitySequencing.ActionRequestEvent()
├── Helpers.AllowWriteLog()
├── System.nanoTime()
├── Event.Ext.sendEventImmediate()                               [request audit log]
├── IntraActivitySequencing.SendFirstRequestEvent()
├── Helpers.GetActivityStatusString()
├── Helpers.SendDataToDB()
├── Helpers.SkipActivity()
└── Helpers.HandleActivityException()

Response_CRM_UPSERT_CUSTOMER_ACCOUNT (rulefunction)
├── OMXUtils.generateTrackingID()                                [declared as String extId — UNUSED: XSLT generates its own]
├── Instance.createInstance()                                    [ResponseBase XSLT]
├── currActivity.Response[] ← activityRes                        [append response]
├── currActivity.ResponseCode ← eventResponse.ResponseCode       [direct write to activity]
├── currActivity.ResponseMessage ← eventResponse.ResponseMsg     [direct write to activity]
├── System.nanoTime()
├── XPath.evalAsString()                                         [extract customerRowId from response]
├── orderRequest.OrderData.Customer.CustomerCrmId ← customerRowId  ← CRITICAL WRITEBACK
├── Helpers.AllowWriteLog()                                      [correctly gates response audit]
├── Event.createEvent()                                          [Logger XSLT]
├── Event.Ext.sendEventImmediate()
└── IntraActivitySequencing.ActionResponseEvent(currActivity)
    → returns "true" when queue exhausted, "false" while more pending
```

---

## §16 — Concept Definitions Referenced

| Concept | Used in | Key fields |
|---------|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | Both | SubmissionDate, RawSubmissionDate, OrderData.*, Customer.*; `CustomerCrmId` written by response RF |
| `Concepts.OM.ProcessConfig.Activity` | Both | ActivityID, Status, RequestCount, Response[], PreExecCheck, Parameter[]; ResponseCode/ResponseMessage written by response RF |
| `Concepts.FM.Base.ResponseBase` | Response RF | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId (sub.RefId for idempotency) |
| `Concepts.OrderRequest.OrderElements.Subscriber` | Request rule | RefId, AccountRefId, MSISDN, SubscriberName.*, SubscriberAddress.* |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Process each subscriber (ParentOU and ChildOU) sequentially via CRM CRMUpsertCustomerAccount |
| R2 | Per-subscriber idempotency: skip if CompletionStatus=2 and ReferenceId=sub.RefId |
| R3 | Activity parameter-driven mode and upsertAccountStatus (not from order data) |
| R4 | IdentificationExpDate auto-extend by 10 years if expired at RawSubmissionDate |
| R5 | ID number spaces stripped via translate() |
| R6 | All dates translated to Asia/Bangkok timezone before formatting |
| R7 | OrderType '51'/'74': use MSISDN as both firstName and lastName |
| R8 | Name fallback chain: subscriber → customer → Channel/hardcoded |
| R9 | Address priority: subscriber-level overrides customer-level |
| R10 | Response RF extracts and writes back `customerRowId` to `CustomerCrmId` |
| R11 | Response audit correctly gated by AllowWriteLog (consistent with request) |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **ID expiry silently modified:** Auto-extending IdentificationExpDate by 10 years when expired means CRM receives a date different from the actual document. May cause compliance/audit issues. | [HIGH] | Document this business rule; add audit log entry when extension occurs; confirm with compliance team |
| **Hardcoded lastName="Prepaid":** When no name data is available, CRM receives `lastName="Prepaid"`. Customer records will be polluted with this placeholder. | [MEDIUM] | Confirm intentional for PREPAID_REGISTRATION; consider configurable placeholder or validation |
| **Dead code — unused `extId` variable:** Line 14 declares `String extId = OMXUtils.generateTrackingID()` but the XSLT generates its own. The BE-side variable is never used. | [LOW] | Remove the unused BE-side `extId` declaration |
| **No exception handling in response RF:** CustomerCrmId write-back and `ActionResponseEvent` run without try-catch. Exception mid-process could leave activity in inconsistent state. | [MEDIUM] | Add try-catch calling HandleActivityException; ensure CustomerCrmId writeback is atomic |
| **TypeOfAccomodation spelling:** Source uses single-m spelling; target XML uses double-m `typeOfAccommodation`. Silent XPath break if source field renamed. | [LOW] | Document source-field spelling; test both variants in mapping layer |
| **firstName fallback = Channel:** Channel code (e.g., "TYC20") becomes CRM firstName when no name data present. Produces invalid customer records. | [MEDIUM] | Add validation in PreExecCheck to require minimum name data before CRM upsert |

---

## §18 — Full Source Code (Condensed)

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CRM_UPSERT_CUSTOMER_ACCOUNT {
    attribute { priority = 5; forwardChain = true; }
    // ... declare / when as standard ...
    then {
        boolean isActResub = (RequestCount > 0 && IsOrderResubmitted);
        try {
            if(isActResub) IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(...);

            // ParentOU Subscriber loop
            for(int i..; j..) {
                String refId = sub.RefId;
                // Idempotency check (CompletionStatus==2 + ReferenceId==refId)
                if(!reqSuccess) {
                    // PreExecCheck via GetXMLForSubscriber
                    // mode + upsertAccountStatus from GetActivityParameterValueFromKey
                    // Date pre-processing: submissionDate, identificationExpDate (auto-extend), birthDate
                    // Title: TitleTransformer2(sub.SubscriberName.Title || CustomerName.Title)
                    // [XSLT: CRMUpsertCustomerAccountRequest — see §9 for full field mapping]
                    Event.assertEvent(reqEvent);
                    IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
                    isSkipped = false;
                    if(AllowWriteLog(OrderType)) { /* static AUDIT_TRACE */ }
                }
            }

            // ChildOU Subscriber loop (correct index — no ChildOU[p] bug)
            for(int c..; j..) { /* same date/title/XSLT pattern */ }

            if(!isSkipped) {
                IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
                orderCurrentActivity.Status = GetActivityStatusString("1", false);
                SendDataToDB(orderRequest);
            } else {
                SkipActivity(orderRequest, orderCurrentActivity, "4");
            }
        } catch(Exception ae) { HandleActivityException(...); }
    }
}
```

---

## §19 — Response Message Rule (Response_CRM_UPSERT_CUSTOMER_ACCOUNT)

### §19.1 — Overview

Creates a `ResponseBase` concept, **extracts the CRM-returned customerRowId and writes it back to the order concept** (`CustomerCrmId`), logs the response (AllowWriteLog-gated), then calls `ActionResponseEvent` for fan-in. Also writes `ResponseCode` and `ResponseMessage` directly to `currActivity` properties.

> **Commented-out alternative:** A second `Instance.createInstance` call is commented out — it used `$eventResponse/@extId` instead of `OMXUtils:generateTrackingID()`. The developer chose the tracking ID approach but left the old code in place.

> **Dead variable:** Line 14 declares `String extId = OMXUtils.generateTrackingID()` but this variable is never used — the XSLT generates its own via `ns:generateTrackingID()`.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context; `CustomerCrmId` is written to this concept by this RF |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CRM_UPSERT_CUSTOMER_ACCOUNT` | CRM response event; contains `payload/CRMUpsertCustomerAccountResponse/customerRowId` |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity; `ResponseCode` and `ResponseMessage` also written directly |

### §19.3 — ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId         ← ns:generateTrackingID() (OMXUtils inside XSLT)    [Always]
    ├── ResponseCode   ← $eventResponse/ResponseCode                        [Conditional]
    ├── ResponseMessage← $eventResponse/ResponseMsg                         [Conditional]
    ├── CompletionStatus← $eventResponse/CompletionStatus                   [Conditional]
    └── ReferenceId    ← $eventResponse/RefID  (should match sub.RefId)    [Conditional]
```

### §19.4 — CRM ID Writeback (Critical)

```java
// Extract customerRowId from CRM response payload
orderRequest.OrderData.Customer.CustomerCrmId =
    XPath.evalAsString("$eventResponse/payload/xsd3:CRMUpsertCustomerAccountResponse/xsd3:customerRowId");
// Namespace: xsd3 = CRMUpsertCustomerAccount.xsd
// This value is used by downstream activities that need the CRM customer row ID
```

Additionally: `currActivity.ResponseCode` and `currActivity.ResponseMessage` are set directly on the activity concept.

### §19.5 — Response Completion Logic

| Attribute | Value |
|-----------|-------|
| Fan-in mechanism | `IntraActivitySequencing.ActionResponseEvent(currActivity)` |
| Return "true" | Queue exhausted — all subscribers processed |
| Return "false" | More subscribers queued — dispatches next one |

### §19.6 — Response Audit Logging

| Field | Value |
|-------|-------|
| `OPERATION_NAME` | `"CRM_UPSERT_CUSTOMER_ACCOUNT"` |
| `AUDIT_TRACE` | `"Response received for CRM_UPSERT_CUSTOMER_ACCOUNT"` |
| Gate | `AllowWriteLog(OrderType)` — **correctly gated** (unlike CCP FMs) |
| `payload` | Full `$eventResponse` copy, gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
