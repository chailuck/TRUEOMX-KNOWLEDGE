# Request_OMX_GET_PARTIAL_ORDER_DATA

> External OMXFM Rule — Retrieves partial order data (customer ID, extended info) from OMX internal service and merges it into the OrderRequest working memory at multiple entity levels.

**Rule:** `Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_PARTIAL_ORDER_DATA`
**Priority:** 5 | **forwardChain:** true | **Target:** OMX Internal (OMX_FM) | **Transport:** JMS Async

---

## §1 — Overview & Purpose

Retrieves partial order data from the OMX internal ESB service. Used in **PREPAID_REGISTRATION** (step 3) to recover customer identification, a prior partial order ID, and multi-level extended info attributes (order, customer, account, subscriber, agreement) from a partially completed prior order.

The response RF merges the retrieved data into the in-memory `OrderRequest` concept at six entity levels, enabling downstream activities to work with enriched data.

> **Key trait:** Uses subscriber `MSISDN` as the correlation `RefId` (not `psub.RefId` as most other FMs do). This means the JMS response is correlated by phone number.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_PARTIAL_ORDER_DATA` |
| Priority | 5 |
| forwardChain | true |
| Rule Type | External OMXFM — async JMS request/response |
| Activity ID | `OMX_GET_PARTIAL_ORDER_DATA` |
| Target Backend | OMX Internal Service (OMX_FM) |
| Request Event | `/Events/OMConsumers/OMXFM/Request/OMX_GET_PARTIAL_ORDER_DATA` |
| Response RF | `Response_OMX_GET_PARTIAL_ORDER_DATA.rulefunction` |
| Payload Schema | `http://...OMX/ESB/OMX_GetPartialOrderData.xsd` |

---

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context; read for payload; written by response RF at multiple levels |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity state; RequestCount, Response[], Status |

---

## §4 — Rule Conditions (WHEN)

```xpath
orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName
orderCurrentActivity.ActivityID == "OMX_GET_PARTIAL_ORDER_DATA"
orderRequest.ProcessFlow.NextActivityID == "OMX_GET_PARTIAL_ORDER_DATA"
orderCurrentActivity.Status == "WAITING"
```

---

## §5 — Execution Flow Diagram

1. Set `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Load `nextAct` by ExtId; read `PreExecCheck` XPath
3. Loop ParentOU → loop Subscriber[ps]
4. Check Response[] for prior success (CompletionStatus==2, RefId==MSISDN) → skip if found
5. Evaluate PreExecCheck XPath if present → skip if "false"
6. Build `GetPartialOrderDataReq` event via XSLT; RefId = `psub.MSISDN`
7. `Event.Ext.sendEventImmediate(reqEvent)`
8. Increment `RequestCount` unless resubmit
9. Send unconditional audit Logger event ("Request Sent for OMX_GET_PARTIAL_ORDER_DATA")
10. Loop ChildOU → same logic; RefId = `csub.MSISDN`
11. If not skipped: Status="1" (IN_PROGRESS) + `SendDataToDB`; else `SkipActivity("4")`
12. Exception → `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`

---

## §6 — Rule Action (THEN) — Logic Detail

**Resubmit:** `isActResub = (RequestCount > 0 && IsOrderResubmitted)` — if true, `RequestCount` not re-incremented.

**Prior success check:** Scans `Response[]` for `ReferenceId == MSISDN` with `CompletionStatus == 2`. If found, skips that subscriber.

**RefId = MSISDN:** Unlike most OMXFM rules (which use `psub.RefId`), this FM uses `psub.MSISDN` as the correlation key.

> **⚠ No AllowWriteLog gate:** Audit log fires unconditionally. Other OMXFM rules wrap the Logger event in `AllowWriteLog(OrderType)`. This FM does not.

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Used in **PREPAID_REGISTRATION** step 3. No order type filter in the rule. ProcessConfig PreExecCheck: `boolean(//Subscriber/MSISDN!="")`.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel/Destination | Purpose |
|-----------|--------------------|---------| 
| [OUTBOUND JMS] | `/Events/OMConsumers/OMXFM/Request/OMX_GET_PARTIAL_ORDER_DATA` | Send GetPartialOrderDataReq |
| [INBOUND JMS] | `/Events/OMConsumers/OMXFM/Response/OMX_GET_PARTIAL_ORDER_DATA` | Receive response |
| [LOG] | `/Events/OMConsumers/OMXESB/Logger` | Audit logging |

### §8.3 Backend API Details

| System | Operation | Schema | Protocol |
|--------|-----------|--------|---------|
| OMX Internal | GetPartialOrderData | `OMX_GetPartialOrderData.xsd` / `ns13:GetPartialOrderDataReq` | JMS async |

### §8.4 BE Working Memory Dependencies

| Field | Access | Notes |
|-------|--------|-------|
| `orderCurrentActivity.Status` | WRITE | "1"=IN_PROGRESS or SKIP |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Incremented per subscriber |
| `orderCurrentActivity.Response[]` | READ/WRITE | Checked; ResponseBase appended by response RF |
| `orderRequest.OrderData.Customer.*` | READ/WRITE | CustomerName, ExtendedInfo, Account, ParentOU, ChildOU |
| `orderRequest.OrderData.ExtendedInfo[]` | WRITE | PartialOrderId + OrderExtendedInfo entries |

### §8.5 ExtendedInfo Fields

| Name | Direction | Notes |
|------|-----------|-------|
| `PARTIAL_ORDER_ID` | WRITE | From `GetPartialOrderDataRes/Order/PartialOrderId` |
| `OrderExtendedInfo[*].Name` | WRITE | Dynamic keys from response |
| `CustomerExtendedInfo[*].Name` | WRITE | Dynamic keys added to Customer.ExtendedInfo[] |
| `AccountExtendedInfo[*].Name` | WRITE | [BUG: infinite loop in response RF] |
| `AgreementExtendedInfo[*].Name` | WRITE | Added to ParentOU/ChildOU Agreement |
| `SubscriberExtendedInfo[*].Name` | WRITE | Added to each Subscriber |

### §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | If "true", include UserName/PassWord in header |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `OMX_OM/WritePayload` | If "true", include payload in audit event |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Parameter | ParentOU | ChildOU | Bound From |
|-----------|----------|---------|------------|
| `orderRequest` | ✓ | ✓ | Working memory |
| `pSubRefId` | ✓ | — | `psub.MSISDN` |
| `cSubRefId` | — | ✓ | `csub.MSISDN` |
| `psub` | ✓ | — | ParentOU.Subscriber[ps] |
| `csub` | — | ✓ | ChildOU.Subscriber[cs] |
| `globalVariables` | ✓ | ✓ | BE Global Variables |

### §9.3 JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | If present |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | If present |
| `OrderID` | `$orderRequest/OrderData/OrderID` | If present |
| `RefID` | `$pSubRefId` / `$cSubRefId` | Always (= subscriber MSISDN) |
| `UserName` | `$orderRequest/OrderData/User` | IsEnableUserPass="true" AND User present |
| `PassWord` | `$orderRequest/OrderData/Password` | IsEnableUserPass="true" AND Password present |
| `OrderType` | `$orderRequest/OrderData/OrderType` | If present |

### §9.4 Payload Root

```xml
<ns13:GetPartialOrderDataReq>
  <ns13:Msisdn>0812345678</ns13:Msisdn>
  <ns13:Identification>1100200300400</ns13:Identification>
  <ns13:IdentificationType>T</ns13:IdentificationType>
</ns13:GetPartialOrderDataReq>
```

### §9.8 XSLT Stylesheet Source

**Variant ① — ParentOU Subscriber** (params: `orderRequest`, `pSubRefId`=MSISDN, `globalVariables`, `psub`):

```xml
<xsl:stylesheet xmlns:ns13="http://...OMX/ESB/OMX_GetPartialOrderData.xsd" version="1.0">
  <xsl:template match="/">
    <createEvent><event>
      <xsl:if test="$orderRequest/OrderPriority">
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      </xsl:if>
      <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      <RefID><xsl:value-of select="$pSubRefId"/></RefID>   <!-- = psub.MSISDN -->
      <xsl:if test="$globalVariables/.../IsEnableUserPass='true'">
        <UserName><xsl:value-of select="$orderRequest/OrderData/User"/></UserName>
        <PassWord><xsl:value-of select="$orderRequest/OrderData/Password"/></PassWord>
      </xsl:if>
      <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      <payload>
        <ns13:GetPartialOrderDataReq>
          <ns13:Msisdn><xsl:value-of select="$psub/MSISDN"/></ns13:Msisdn>
          <ns13:Identification><xsl:value-of select="$orderRequest/OrderData/Customer/CustomerGeneralInfo/Identification"/></ns13:Identification>
          <ns13:IdentificationType><xsl:value-of select="$orderRequest/OrderData/Customer/CustomerGeneralInfo/IdentificationType"/></ns13:IdentificationType>
        </ns13:GetPartialOrderDataReq>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**Variant ② — ChildOU Subscriber**: Identical; `pSubRefId` → `cSubRefId`, `psub` → `csub`.

---

## §10 — XSLT Field Mapping — Output XML Tree

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                      [Conditional: if OrderPriority]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId            [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                  [Conditional]
    ├── RefID                ← $pSubRefId (= psub.MSISDN)                       [Always]
    ├── UserName             ← $orderRequest/OrderData/User                     [Credential-gated: IsEnableUserPass="true"]
    ├── PassWord             ← $orderRequest/OrderData/Password                 [Credential-gated: IsEnableUserPass="true"]
    ├── OrderType            ← $orderRequest/OrderData/OrderType                [Conditional]
    └── payload                                                                 [Always]
        └── ns13:GetPartialOrderDataReq
            ├── ns13:Msisdn              ← $psub/MSISDN                         [Conditional]
            ├── ns13:Identification      ← .../CustomerGeneralInfo/Identification [Conditional]
            └── ns13:IdentificationType  ← .../CustomerGeneralInfo/IdentificationType [Conditional]
```

Legend: `[Always]` = always emitted | `[Conditional: <condition>]` = xsl:if guard | `[Credential-gated]` = global variable flag required

---

## §11 — Audit Logging

| Field | Request | Response |
|-------|---------|---------|
| `ESBUUID` | `$orderRequest/OrderData/OMXTrackingId` | same |
| `PROCESS_ID` | `concat($pid,"_REQ")` | `concat($pid,"_RES")` |
| `OPERATION_NAME` | `"OMX_GET_PARTIAL_ORDER_DATA"` | same |
| `AUDIT_TRACE` | `"Request Sent for OMX_GET_PARTIAL_ORDER_DATA"` | `"Response received for OMX_GET_PARTIAL_ORDER_DATA"` |
| `payload` | Copy of `$reqEvent` (if WritePayload="true") | Copy of `$eventResponse` (if WritePayload="true") |

> **⚠ No AllowWriteLog gate** — audit logs fire unconditionally for both request and response.

---

## §12 — Activity Status Management

| Condition | Status | Helper Call |
|-----------|--------|-------------|
| At least one subscriber sent | "1" IN_PROGRESS | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All subscribers skipped | "4" SKIP | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception | ERROR | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 — Helper Functions Reference

| Function | Scope | Purpose |
|----------|-------|---------|
| `GetXMLForSubscriber(orderRequest, pSubRefId)` | ACTION | Serialize ParentOU subscriber for XPath evaluation |
| `GetXMLForSubscriberInChildOU(orderRequest, cSubRefId, pOuRefId)` | ACTION | Same for ChildOU subscriber |
| `GetActivityStatusString(code, flag)` | ACTION | "1" → IN_PROGRESS string |
| `SendDataToDB(orderRequest)` | ACTION | Persist state to DB |
| `SkipActivity(orderRequest, activity, code)` | ACTION | Mark activity skipped with reason "4" |
| `HandleActivityException(orderRequest, activity, ex, ctx)` | ACTION | Error handling |
| `BRMS.IsBlankOrStringNull(value)` | ACTION | Null/blank guard (used in response RF) |

---

## §15 — Function Dependency Tree

```text
Request_OMX_GET_PARTIAL_ORDER_DATA (rule)
├── Instance.getByExtIdByUri()
├── RuleFunctions.Helpers.GetXMLForSubscriber()
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU()
├── XPath.execute()
├── Event.createEvent("xslt://...")
├── Event.Ext.sendEventImmediate()
├── RuleFunctions.Helpers.GetActivityStatusString()
├── RuleFunctions.Helpers.SendDataToDB()
├── RuleFunctions.Helpers.SkipActivity()
└── RuleFunctions.Helpers.HandleActivityException()

Response_OMX_GET_PARTIAL_ORDER_DATA (rulefunction)
├── XPath.evalAsBoolean()       [existsPartialData + field existence checks]
├── XPath.evalAsString()        [field extraction from response]
├── XPath.evalAsInt()           [count extended info items + fan-in]
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull()
├── Instance.createInstance("xslt://...")   [ResponseBase, ExtendedInfo concepts]
└── Event.Ext.sendEventImmediate()          [response audit log]
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| # | Requirement |
|---|-------------|
| R1 | Query OMX internal service with subscriber MSISDN as correlation key |
| R2 | Populate `CustomerName.Identification` and `IdentificationType` only if currently blank |
| R3 | Add `PARTIAL_ORDER_ID` to order ExtendedInfo if not present |
| R4 | Merge dynamic extended info at order, customer, account, subscriber, and agreement levels (de-dup by Name) |
| R5 | Create `Agreement` for ParentOU/ChildOU if null, then populate AgreementExtendedInfo |
| R6 | Support resubmit — do not double-increment RequestCount |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| RefId = MSISDN — ambiguous correlation if multiple orders share MSISDN | [HIGH] | Use generated UUID as correlation key in modernization |
| Audit log unconditional — no AllowWriteLog gate | [MEDIUM] | Add AllowWriteLog gate to match other FMs |
| AgreementExtendedInfo applied from single response to all ParentOU/ChildOU Agreements | [MEDIUM] | Verify this is expected; if not, request must be per-OU |

> **🐛 BUG — Account ExtendedInfo Infinite Loop (Response RF)**
>
> Inner loop for AccountExtendedInfo increments `i` (outer loop variable) instead of `a`:
> ```java
> for (int a = 0; a < acctExtLen; i++) {  // ← BUG: should be a++
> ```
> When `acctExtLen > 0`, `a` never advances → infinite loop until outer `i` overflows → ArrayIndexOutOfBounds.
> **Fix:** Change `i++` to `a++`.

---

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_PARTIAL_ORDER_DATA {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_GET_PARTIAL_ORDER_DATA";
    orderRequest.ProcessFlow.NextActivityID == "OMX_GET_PARTIAL_ORDER_DATA";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      // ... PreExecCheck + ParentOU/ChildOU subscriber loop ...
      // For each subscriber: build GetPartialOrderDataReq event (§9.8)
      // RefId = psub.MSISDN / csub.MSISDN (NOT psub.RefId)
      // Audit log fires unconditionally (no AllowWriteLog gate)
      if (!isSkipped) {
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

## §19 — Response Message Rule

### §19.1 Overview

Far more than a typical fan-in completion handler. Performs extensive **data enrichment** of `OrderRequest` working memory: merges partial order data at six entity levels (order, customer, account, subscriber, agreement × parent/child).

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Target of all data writeback |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_GET_PARTIAL_ORDER_DATA` | OMX service response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity state; Response[] appended |

### §19.3 Data Enrichment Logic

All enrichment is gated on `existsPartialData` = `string-length(GetPartialOrderDataRes/Order/PartialOrderId) > 0`.

| # | Target | Source | Condition |
|---|--------|--------|-----------|
| 1 | `CustomerName.Identification` | `GetPartialOrderDataRes/Order/Identification` | Only if currently blank |
| 2 | `CustomerName.IdentificationType` | `GetPartialOrderDataRes/Order/IdentificationType` | Only if currently blank |
| 3 | `OrderData.ExtendedInfo[PARTIAL_ORDER_ID]` | `GetPartialOrderDataRes/Order/PartialOrderId` | If not already present |
| 4 | `OrderData.ExtendedInfo[]` | `GetPartialOrderDataRes/Order/OrderExtendedInfo[*]` | Loop; add if Name not exists |
| 5 | `Customer.ExtendedInfo[]` | `GetPartialOrderDataRes/Order/CustomerExtendedInfo[*]` | Loop; add if Name not exists |
| 6 | `Customer.Account[i].ExtendedInfo[]` | `GetPartialOrderDataRes/Order/AccountExtendedInfo[*]` | **[BUG: infinite loop — `i++` not `a++`]** |
| 7 | `ParentOU.Agreement.ExtendedInfo[]` | `GetPartialOrderDataRes/Order/AgreementExtendedInfo[*]` | Creates Agreement if null |
| 8 | `ParentOU.Subscriber[ps].ExtendedInfo[]` | `GetPartialOrderDataRes/Order/SubscriberExtendedInfo[*]` | Loop; add if not exists |
| 9 | `ChildOU.Agreement.ExtendedInfo[]` | `GetPartialOrderDataRes/Order/AgreementExtendedInfo[*]` | Creates Agreement if null |
| 10 | `ChildOU.Subscriber[cs].ExtendedInfo[]` | `GetPartialOrderDataRes/Order/SubscriberExtendedInfo[*]` | Loop; add if not exists |

### §19.4 ResponseBase Construction

```text
createObject
└── object
    ├── extId               ← OMXUtils:generateTrackingID()    [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode       [Conditional]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg        [Conditional]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus   [Conditional]
    └── ReferenceId         ← $eventResponse/RefID              [Conditional]
```

### §19.5 Response Completion Logic

| Expression | Value |
|------------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Returns "true" | All parallel subscriber requests completed with ResponseCode ending "000" |
| Returns "false" | Still waiting for one or more responses |

### §19.6 Response Audit Logging

| Field | Value |
|-------|-------|
| `PROCESS_ID` | `concat($pid,"_RES")` |
| `AUDIT_TRACE` | `"Response received for OMX_GET_PARTIAL_ORDER_DATA"` |
| `payload` | Copy of `$eventResponse` if WritePayload="true" |

> **⚠ Response audit log also unconditional** — no `AllowWriteLog` gate.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
