# Request_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE

TIBCO BusinessEvents · FM Logic Documentation · Backend: 3CJ (SMS Template Service) · Author: TIT_CP-CHAYAT2

---

## §1 — Overview & Purpose

**Request_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE** fetches SMS message templates from the 3CJ notification service for each eligible subscriber. The template is parameterised by the subscriber's language, family type (PARENT/CHILD), order type, and the convergence debundle mode (DEBUNCAMP or DEBUNPROD).

The **response handler** performs the critical enrichment step: it iterates the returned templates, substitutes `[mobileNo2]` placeholders for PARENT subscribers in DebundleProductNumber mode, then writes the resolved SMS content to `subscriber.ExtendedInfo[SMS_MSG]`. The next FM — **SEND_SMS_MESSAGE_3CJ** — reads this ExtendedInfo to dispatch the actual SMS.

The FM dispatches one event per subscriber, but applies an additional filter for DebundleProductNumber mode: CHILD subscribers who are not the ATS-linked campaign child (matching `parent_campaign_code`) are skipped.

> **[MEDIUM] Response logger always includes payload:** The response audit logger XSLT unconditionally copies `$eventResponse` into the audit payload, regardless of the `WritePayload` global variable. Other FMs gate this behind `$globalVariables/OMX_OM/WritePayload`. This may produce large audit log entries in high-volume flows.

> **[MEDIUM] Last template wins:** If 3CJ returns multiple `omxnNotiTemplate` entries, the response loop overwrites `smsContent` on each iteration. Only the last template in the list is stored in `ExtendedInfo[SMS_MSG]`.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE` | Full qualified path |
| Priority | `5` | Standard FM priority |
| Forward chain | `true` | Rule re-evaluates after THEN actions |
| Rule type | Request Dispatcher | Subscriber fan-out via OMX_GET_3CJ_SMS_TEMPLATE event |
| Author | `TIT_CP-CHAYAT2` | Developer identifier |
| Backend system | 3CJ (SMS Template Service) | Notification template provider |
| Event type (outbound) | `Events.OMConsumers.OMXFM.Request.OMX_GET_3CJ_SMS_TEMPLATE` | "MESSAGE_" absent in event name vs. FM name |
| Event type (response) | `Events.OMConsumers.OMXFM.Response.OMX_GET_3CJ_SMS_TEMPLATE` | Matched by response rulefunction |
| Dispatch pattern | `Event.Ext.sendEventImmediate` | Per-subscriber fan-out; standard resubmit-skip |

> The event type name is `OMX_GET_3CJ_SMS_TEMPLATE` — omitting "MESSAGE_" from the FM activity name `OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE`. Naming inconsistency is cosmetic only.

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order context; source for subscriber loop, BundleInfo, language, family type |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity; holds RequestCount, Response array, Status, PreExecCheck |

---

## §4 — Rule Conditions (WHEN)

| # | Condition Expression | Purpose |
|---|---------------------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Binds activity to current order's next slot |
| 2 | `orderCurrentActivity.ActivityID == "OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE"` | Restricts rule to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE"` | Double-checks order flow pointer |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires when activity is in WAITING state |

---

## §5 — Execution Flow Diagram

1. Compute `isActResub = (RequestCount > 0 && IsOrderResubmitted)`.
2. Multi-POU detection: `count($orderRequest/OrderData/Customer/ParentOU)` → `count_ParentOU`. If > 1, set `is_ParentOU_morethan_1 = true`.
3. ParentOU loop: iterate all `ParentOU` entries. If multi-POU: skip non-SOURCE ParentOU (check `ExtendedInfo[SOURCE_OR_TARGET]="SOURCE"`).
4. Subscriber loop: for each subscriber in the current SOURCE ParentOU:
   - 4a. Resubmit-skip: if `isActResub`, check Response array for `ReferenceId == refId && CompletionStatus == 2`. If found → skip.
   - 4b. Per-subscriber PreExecCheck via `GetXMLForSubscriber`. Skip if not "true".
   - 4c. Language two-step: `SubscriberGeneralInfo.Language` → fallback TARGET ParentOU subscriber by MSISDN.
   - 4d. FamilyType extraction from `subscriber.ExtendedInfo[FamilyType]`.
   - 4e. BundleInfo code mapping: `DebundleCampaign`→"DEBUNCAMP", `DebundleProductNumber`→"DEBUNPROD". Skip if blank.
   - 4f. DEBUNPROD CHILD filter: skip CHILD not matching ATS campaign code link.
   - 4g. Dispatch `OMX_GET_3CJ_SMS_TEMPLATE` event. If not resubmit: `RequestCount++`. Audit log. `isSkipped = false`.
5. If any dispatch: Status → SENT + DB persist. Else: SkipActivity.
6. Exception: `HandleActivityException`.

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

**Multi-POU detection:**

```java
int count_ParentOU = XPath.evalAsInt("count($orderRequest/OrderData/Customer/ParentOU)");
if(count_ParentOU > 1) { is_ParentOU_morethan_1 = true; }
```

**Language two-step resolution:**

```java
String language = "";
if(subscriber.SubscriberGeneralInfo != null) {
    language = subscriber.SubscriberGeneralInfo.Language;
}
if(RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(language)) {
    // Fallback: TARGET ParentOU subscriber with same MSISDN
    language = XPath.evalAsString(
        "$orderRequest/OrderData/Customer/ParentOU"
        + "[ExtendedInfo[Name='SOURCE_OR_TARGET' and Value='TARGET']]"
        + "/Subscriber[MSISDN=$msisdn]/SubscriberGeneralInfo/Language");
}
```

**BundleInfo code mapping:**

```java
String bundleInfo = "";
for (int i=0; i<bundleInfoSize; i++) {
    if (orderRequest.OrderData.BundleInfo[i].ConvergenceAction != null) {
        if(String.equals(BundleInfo[i].ConvergenceAction, "DebundleCampaign"))    bundleInfo = "DEBUNCAMP";
        else if(String.equals(BundleInfo[i].ConvergenceAction, "DebundleProductNumber")) bundleInfo = "DEBUNPROD";
    }
}
if(RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(bundleInfo)) { continue; }  // skip — no SMS needed
```

**DEBUNPROD CHILD filter:**

```java
if(String.equals(bundleInfo, "DEBUNPROD")) {
    String parent_campaign_code = XPath.evalAsString(
        "$orderRequest/OrderData/Customer/ParentOU"
        + "/Subscriber[ExtendedInfo[Name=\"FamilyType\" and Value=\"PARENT\"]]"
        + "/ExtendedInfo[Name=\"CampaignCode\"]/Value");

    if(!IsBlankOrStringNull(familytype)
       && String.equals(familytype, "CHILD")
       && (!XPath.evalAsBoolean("FE_OR_CCBS!='ATS' or not(FE_OR_CCBS) and contains(CampaignCode, $parent_campaign_code)"))) {
        continue; // [MEDIUM] or/and precedence issue — skip CHILD who doesn't match ATS campaign link
    }
}
```

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in **POSTPAID_REMOVE_OFFER_SUB** and other convergence flows with `BundleInfo` entries requiring debundle SMS notifications. Only fires when `bundleInfo` resolves to DEBUNCAMP or DEBUNPROD.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Protocol | Purpose |
|-----------|-----------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.OMX_GET_3CJ_SMS_TEMPLATE` | JMS / TIBCO EMS | Fetch SMS template per subscriber from 3CJ service |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.OMX_GET_3CJ_SMS_TEMPLATE` | JMS / TIBCO EMS | Receive template list from 3CJ |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | JMS | Request/response audit trail |

### §8.3 — Backend API Details

| System | Operation | Schema | Request Element | Correlation |
|--------|-----------|--------|----------------|-------------|
| 3CJ | GetSmsTemplate | `3CJSmsTemplate/OMX_Sms3CJTemplate.xsd` | `ns:OMX_Sms3CJTemplateRequest` | `RefID` ← `subscriber.RefId` (per-subscriber) |

### §8.4 — BE Working Memory Dependencies

| Field | Access | Purpose |
|-------|--------|---------|
| `orderRequest.OrderData.Customer.ParentOU[i]` | READ | Outer loop; SOURCE filter |
| `pOu.Subscriber[subs].RefId` | READ | Correlation key; resubmit-skip |
| `pOu.Subscriber[subs].MSISDN` | READ | Language fallback lookup |
| `subscriber.SubscriberGeneralInfo.Language` | READ | Primary language source |
| `subscriber.ExtendedInfo[Name='FamilyType']/Value` | READ | PARENT/CHILD determination |
| `subscriber.ExtendedInfo[Name='CampaignCode']/Value` | READ | Campaign match for DEBUNPROD CHILD filter |
| `subscriber.ExtendedInfo[Name='FE_OR_CCBS']/Value` | READ | ATS identification in CHILD filter |
| `subscriber.ExtendedInfo[SMS_MSG]` | WRITE (response) | Written by response handler with resolved SMS content |
| `orderRequest.OrderData.BundleInfo[i].ConvergenceAction` | READ | BundleInfo code resolution |
| `orderRequest.OrderData.OrderID` | READ | Event header |
| `orderRequest.OrderData.OrderType` | READ | ns:orderType in payload |
| `orderRequest.OrderData.User` | READ | Event UserName header |
| `orderRequest.OrderData.Password` | READ | Event PassWord header |
| `orderRequest.OrderData.OMXTrackingId` | READ | JMSCorrelationID + audit ESBUUID |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-out counter |
| `orderCurrentActivity.Response` | WRITE (response) | Append ResponseBase records |
| `orderCurrentActivity.Status` | WRITE | Set to SENT after dispatch |

### §8.5 — ExtendedInfo Fields

| Name | Access | Source | Purpose |
|------|--------|--------|---------|
| `SOURCE_OR_TARGET` | READ | ParentOU.ExtendedInfo | Multi-POU filter: only process SOURCE |
| `FamilyType` | READ | Subscriber.ExtendedInfo | PARENT/CHILD template type |
| `CampaignCode` | READ | Subscriber.ExtendedInfo | Campaign match for DEBUNPROD filter |
| `FE_OR_CCBS` | READ | Subscriber.ExtendedInfo | ATS subscriber identification |
| `SMS_MSG` | WRITE | Subscriber.ExtendedInfo | Resolved SMS content; read by SEND_SMS_MESSAGE_3CJ |

### §8.6 — Global Variable Dependencies

| Variable Path | Used In | Purpose |
|--------------|---------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Request audit logger | COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Response audit logger | TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Both loggers | LOG_LEVEL |

> The response logger does NOT reference `$globalVariables/OMX_OM/WritePayload` — the response payload is always included regardless of configuration.

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Role |
|-----------|-----------|------|
| `$orderRequest` | BE concept `orderRequest` | Root order data |
| `$refId` | `subscriber.RefId` | Per-subscriber correlation (RefID in event header) |
| `$language` | Resolved language string (2-step) | `ns:languageCode` in request body |
| `$familytype` | `subscriber.ExtendedInfo[FamilyType]/Value` | `ns:productType` in request body |
| `$bundleInfo` | Resolved "DEBUNCAMP" or "DEBUNPROD" | `ns:messageType` in request body |

### §9.2 — Event Container

| Field | Source | Notes |
|-------|--------|-------|
| `event @extId` | `OMXUtils:generateTrackingID()` | Called directly in XSLT — Pattern C (correct) |
| `RefID` | `$refId` (= `subscriber.RefId`) | Per-subscriber — enables proper fan-in correlation |

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$refId` | Always (per-subscriber) |
| `UserName` | `$orderRequest/OrderData/User` | Always |
| `PassWord` | `$orderRequest/OrderData/Password` | Always — order submitter credentials |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Always |

### §9.4 — Payload Root Element

`payload / ns:OMX_Sms3CJTemplateRequest` — namespace: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/3CJSmsTemplate/OMX_Sms3CJTemplate.xsd`

### §9.5 — Conditional Fields

| Field | Condition | Source / Value |
|-------|-----------|----------------|
| `ns:languageCode` | Always | `$language` (resolved two-step) |
| `ns:orderType` | if `$orderRequest/OrderData/OrderType` exists | `$orderRequest/OrderData/OrderType` |
| `ns:productType` | Always | `$familytype` (subscriber's FamilyType ExtendedInfo) |
| `ns:messageType` | Always | `$bundleInfo` ("DEBUNCAMP" or "DEBUNPROD") |

### §9.7 — Complete Generated XML Example

```xml
<createEvent>
  <event extId="OMX-TRK-20240801-020">
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20240801-001</JMSCorrelationID>
    <OrderID>ORD-9001</OrderID>
    <RefID>SUB-REF-001</RefID>
    <UserName>agent01</UserName>
    <PassWord>***</PassWord>
    <OrderType>POSTPAID_REMOVE_OFFER_SUB</OrderType>
    <payload>
      <ns:OMX_Sms3CJTemplateRequest
        xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/3CJSmsTemplate/OMX_Sms3CJTemplate.xsd">
        <ns:languageCode>TH</ns:languageCode>
        <ns:orderType>POSTPAID_REMOVE_OFFER_SUB</ns:orderType>
        <ns:productType>PARENT</ns:productType>
        <ns:messageType>DEBUNPROD</ns:messageType>
      </ns:OMX_Sms3CJTemplateRequest>
    </payload>
  </event>
</createEvent>
```

### §9.8 — XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/3CJSmsTemplate/OMX_Sms3CJTemplate.xsd"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  version="1.0"
  exclude-result-prefixes="OMXUtils xsl ns xsd">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>   <!-- root order concept -->
  <xsl:param name="refId"/>          <!-- subscriber.RefId -->
  <xsl:param name="language"/>       <!-- resolved language (2-step fallback) -->
  <xsl:param name="familytype"/>     <!-- subscriber FamilyType ExtendedInfo -->
  <xsl:param name="bundleInfo"/>     <!-- "DEBUNCAMP" or "DEBUNPROD" -->
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <RefID><xsl:value-of select="$refId"/></RefID>
        <UserName><xsl:value-of select="$orderRequest/OrderData/User"/></UserName>
        <PassWord><xsl:value-of select="$orderRequest/OrderData/Password"/></PassWord>
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        <payload>
          <ns:OMX_Sms3CJTemplateRequest>
            <ns:languageCode><xsl:value-of select="$language"/></ns:languageCode>
            <xsl:if test="$orderRequest/OrderData/OrderType">
              <ns:orderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></ns:orderType>
            </xsl:if>
            <ns:productType><xsl:value-of select="$familytype"/></ns:productType>
            <ns:messageType><xsl:value-of select="$bundleInfo"/></ns:messageType>
          </ns:OMX_Sms3CJTemplateRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── @extId              ← OMXUtils:generateTrackingID() (inside XSLT)          [Always]
    ├── JMSPriority         ← $orderRequest/OrderPriority                           [Always]
    ├── JMSCorrelationID    ← $orderRequest/OrderData/OMXTrackingId                 [Always]
    ├── OrderID             ← $orderRequest/OrderData/OrderID                       [Always]
    ├── RefID               ← $refId (= subscriber.RefId, per-subscriber)           [Always]
    ├── UserName            ← $orderRequest/OrderData/User                          [Always]
    ├── PassWord            ← $orderRequest/OrderData/Password                      [Always]
    ├── OrderType           ← $orderRequest/OrderData/OrderType                     [Always]
    └── payload
        └── ns:OMX_Sms3CJTemplateRequest
            ├── ns:languageCode   ← $language (2-step resolved)                    [Always]
            ├── ns:orderType      ← $orderRequest/OrderData/OrderType               [Conditional: if OrderType exists]
            ├── ns:productType    ← $familytype ("PARENT" / "CHILD" / "")          [Always]
            └── ns:messageType    ← $bundleInfo ("DEBUNCAMP" / "DEBUNPROD")         [Always]
```

Legend: `[Always]` = no xsl:if guard · `[Conditional: ...]` = inside xsl:if · XPath in plain text = working memory source · `"quoted"` = static literal

---

## §11 — Audit Logging

| Phase | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE | Payload |
|-------|-----------|----------------|-------------|---------|
| REQUEST | `concat(pid, "_REQ")` | `"OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE"` | `"Request for OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE"` | `<payload/>` (empty — always) |
| RESPONSE | `concat(pid, "_RES")` | `"OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE"` | `"Response received for OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE"` | `<ns:ServicePayload>` + copy of `$eventResponse` — **always included** |

> [MEDIUM] Response audit always includes full event payload — no WritePayload gate. Recommend adding standard guard.

---

## §12 — Activity Status Management

| Scenario | Status Code | Function | Meaning |
|----------|------------|---------|---------|
| At least one subscriber dispatch sent | `"1"` | `GetActivityStatusString("1", false)` | SENT |
| No dispatches (bundleInfo blank, or all skipped) | `"4"` | `SkipActivity(…, "4")` | SKIPPED |

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 — Helper Functions Reference

| Function | Return Type | Purpose |
|----------|------------|---------|
| `RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(str)` | boolean | Test for blank or null string |
| `RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)` | String | Serialise per-subscriber XML for PreExecCheck |
| `GetActivityStatusString("1", false)` | String | Status SENT |
| `SkipActivity(orderRequest, activity, "4")` | void | Skip activity |
| `SendDataToDB(orderRequest)` | void | Persist order state |
| `HandleActivityException(orderRequest, activity, ae, "")` | void | Error handler |
| `String.replaceAll(src, "\\[mobileNo2]", msisdn)` | String | Substitute [mobileNo2] placeholder (PARENT+DEBUNPROD only) |

---

## §15 — Function Dependency Tree

```text
Request_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE (rule)
├── XPath.evalAsInt                                      [count ParentOU; count BundleInfo]
├── XPath.evalAsBoolean                                  [SOURCE_OR_TARGET; CHILD filter]
├── XPath.evalAsString                                   [language fallback; familytype; parent_campaign_code]
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull       [language; bundleInfo; familytype checks]
├── RuleFunctions.Helpers.GetXMLForSubscriber            [PreExecCheck serialisation]
├── XPath.execute                                        [PreExecCheck evaluation]
├── OMXUtils:generateTrackingID()                        [event @extId — inside XSLT]
├── Event.Ext.sendEventImmediate                         [x2: reqEvent + logger per subscriber]
├── RuleFunctions.Helpers.GetActivityStatusString        [status "1"]
├── RuleFunctions.Helpers.SendDataToDB                   [DB persistence]
├── RuleFunctions.Helpers.SkipActivity                   [skip path]
└── RuleFunctions.Helpers.HandleActivityException        [error handling]

Response_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE (rulefunction)
├── OMXUtils.generateTrackingID()                        [Java variable → $extId param → ResponseBase @extId — Pattern A]
├── Instance.createInstance (ResponseBase XSLT)          [construct response record]
├── System.debugOut                                      [debug log: smsContent value]
├── XPath.evalAsInt                                      [count BundleInfo; count noOfTemplate; fan-in count]
├── XPath.evalAsBoolean                                  [SOURCE_OR_TARGET check]
├── XPath.evalAsString                                   [familytype; templateContent; productType; child MSISDN]
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull       [familytype; child MSISDN blank checks]
├── String.replaceAll                                    [substitute [mobileNo2] in PARENT template]
├── Instance.createInstance (SubscriberExtendedInfo)     [write SMS_MSG ExtendedInfo]
├── Event.Ext.sendEventImmediate                         [response audit logger]
└── [return "true" / "false"]                            [fan-in completion]
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Fields Used | Role |
|---------|----------------|------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.Customer.ParentOU[], OrderData.BundleInfo[], OrderData.User, OrderData.Password, OrderData.OrderType | Root order |
| `Concepts.OrderRequest.OrderElements.ParentOU` | Subscriber[], ExtendedInfo[SOURCE_OR_TARGET] | ParentOU with SOURCE/TARGET flag |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, SubscriberGeneralInfo.Language, ExtendedInfo[FamilyType/CampaignCode/FE_OR_CCBS/SMS_MSG] | Per-subscriber data + SMS output |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck | Activity tracking |
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId | Normalised response record |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberExtendedInfo` | Name, Value | Written by response: SMS_MSG ExtendedInfo |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement | Evidence |
|----|------------|---------|
| R1 | Fetch SMS template from 3CJ per subscriber; parameterise by language, family type, order type, debundle mode | Request event: ns:OMX_Sms3CJTemplateRequest with 4 payload fields |
| R2 | Multi-POU handling: only process SOURCE ParentOU when count > 1 | Rule: `is_ParentOU_morethan_1` + SOURCE_OR_TARGET check |
| R3 | Two-step language resolution: SubscriberGeneralInfo.Language → TARGET ParentOU subscriber by MSISDN | Rule: IsBlankOrStringNull gate + XPath fallback |
| R4 | BundleInfo code mapping: DebundleCampaign→"DEBUNCAMP"; DebundleProductNumber→"DEBUNPROD" | Rule: BundleInfo scan loop |
| R5 | DEBUNPROD mode: skip CHILD subscribers not linked to PARENT's campaign code | Rule: parent_campaign_code lookup + CHILD filter |
| R6 | Response: substitute [mobileNo2] with child MSISDN for PARENT subscribers in DEBUNPROD mode | Response: `String.replaceAll(templateContent, "\\[mobileNo2]", msisdn_child_sms_to_parent)` |
| R7 | Store resolved SMS content in subscriber.ExtendedInfo[SMS_MSG] for downstream SEND_SMS_MESSAGE_3CJ | Response: `Instance.createInstance(SubscriberExtendedInfo)` with Name="SMS_MSG" |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| Response audit logger always copies full event payload — no WritePayload gate | [MEDIUM] | Add `$globalVariables/OMX_OM/WritePayload="true"` guard in response logger XSLT |
| Multiple template loop: last template overwrites smsContent — earlier templates silently discarded | [MEDIUM] | Clarify 3CJ contract; decide concatenation vs. pick-first strategy |
| XPath or/and precedence issue in CHILD filter and child MSISDN lookup predicate | [MEDIUM] | Add explicit parentheses: `(FE_OR_CCBS!='ATS' or not(FE_OR_CCBS)) and contains(CampaignCode,...)` |
| bundleInfo naming inconsistency: request uses "DEBUNCAMP"/"DEBUNPROD"; response uses "DebundleCampaign"/"DebundleProductNumber" | [MEDIUM] | Normalise to single enum; use constants in modernised service |
| Language fallback XPath may select wrong subscriber if multiple TARGET subscribers share MSISDN | [LOW] | Add `[1]` predicate: `.../Subscriber[MSISDN=$msisdn][1]/...` |
| Request audit AUDIT_TRACE "Request for…" vs. standard "Request Sent for…" | [LOW] | Standardise for monitoring dashboard consistency |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author TIT_CP-CHAYAT2
 */
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE";
        orderRequest.ProcessFlow.NextActivityID == "OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        try {
            boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
            boolean isSkipped = true;
            long pid = System.nanoTime();

            // Multi-POU detection
            boolean is_ParentOU_morethan_1 = false;
            int count_ParentOU = XPath.evalAsInt("count($orderRequest/OrderData/Customer/ParentOU)");
            if(count_ParentOU > 1) { is_ParentOU_morethan_1 = true; }

            for(int iPOU = 0; iPOU < orderRequest.OrderData.Customer.ParentOU@length; iPOU++) {
                Concepts.OrderRequest.OrderElements.ParentOU pOu = orderRequest.OrderData.Customer.ParentOU[iPOU];

                // SOURCE ParentOU filter
                if(is_ParentOU_morethan_1) {
                    boolean is_pou_source = XPath.evalAsBoolean("$pOu/ExtendedInfo[Name=\"SOURCE_OR_TARGET\"]/Value=\"SOURCE\"");
                    if(!is_pou_source) { continue; }
                }

                for (int subs = 0; subs < pOu.Subscriber@length; subs++) {
                    Concepts.OrderRequest.OrderElements.Subscriber subscriber = pOu.Subscriber[subs];
                    String refId = subscriber.RefId;
                    boolean reqSuccess = false;

                    // Resubmit-skip check
                    if(isActResub) {
                        for(int iResp=0; iResp<orderCurrentActivity.Response@length; iResp++) {
                            if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, refId)
                               && orderCurrentActivity.Response[iResp].CompletionStatus == 2) {
                                reqSuccess = true; break;
                            }
                        }
                    }

                    if (!reqSuccess) {
                        String chkRes = "true";
                        if(String.length(nextAct.PreExecCheck) > 0) {
                            String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId);
                            chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=www.tibco.com/...");
                        }
                        if(String.equals(chkRes, "true")) {
                            // Language two-step resolution
                            String language = "";
                            String msisdn = subscriber.MSISDN;
                            if(subscriber.SubscriberGeneralInfo != null) language = subscriber.SubscriberGeneralInfo.Language;
                            if(IsBlankOrStringNull(language)) language = XPath.evalAsString("...TARGET ParentOU Subscriber[MSISDN=$msisdn]/Language...");

                            String familytype = XPath.evalAsString("$subscriber/ExtendedInfo[Name=\"FamilyType\"]/Value");

                            // BundleInfo code mapping
                            String bundleInfo = "";
                            int bundleInfoSize = XPath.evalAsInt("count($orderRequest/OrderData/BundleInfo)");
                            for (int i=0; i<bundleInfoSize; i++) {
                                if(BundleInfo[i].ConvergenceAction != null) {
                                    if(String.equals(BundleInfo[i].ConvergenceAction, "DebundleCampaign"))    bundleInfo = "DEBUNCAMP";
                                    else if(String.equals(BundleInfo[i].ConvergenceAction, "DebundleProductNumber")) bundleInfo = "DEBUNPROD";
                                }
                            }

                            if(!IsBlankOrStringNull(bundleInfo)) {
                                if(String.equals(bundleInfo, "DEBUNPROD")) {
                                    String parent_campaign_code = XPath.evalAsString("...ParentOU/Subscriber[FamilyType=PARENT]/CampaignCode/Value...");
                                    // [MEDIUM] or/and precedence issue in XPath predicate below
                                    if(!IsBlankOrStringNull(familytype) && String.equals(familytype, "CHILD")
                                       && (!XPath.evalAsBoolean("FE_OR_CCBS!='ATS' or not(FE_OR_CCBS) and contains(CampaignCode, $parent_campaign_code)"))) {
                                        continue;
                                    }
                                }

                                /* Build ns:OMX_Sms3CJTemplateRequest event — see §9.8 for full XSLT:
                                   params: $orderRequest, $refId, $language, $familytype, $bundleInfo
                                   payload: languageCode, orderType (conditional), productType, messageType */
                                Events.OMConsumers.OMXFM.Request.OMX_GET_3CJ_SMS_TEMPLATE reqEvent =
                                    Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/OMX_GET_3CJ_SMS_TEMPLATE}}...");
                                Event.Ext.sendEventImmediate(reqEvent);
                                if(!isActResub) orderCurrentActivity.RequestCount++;
                                Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{/Events/OMConsumers/OMXESB/Logger}}..."));
                                isSkipped = false;
                            }
                        }
                    }
                }
            }

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

### §19.1 — Overview

**Response_OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE** processes the 3CJ template response for a specific subscriber (`eventResponse.RefID == subscriber.RefId`). It iterates the returned templates and computes the final SMS content. For PARENT subscribers in DebundleProductNumber mode, it substitutes `[mobileNo2]` with the child subscriber's MSISDN. The resolved SMS content is written to `subscriber.ExtendedInfo[SMS_MSG]` for the next FM to consume.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order; subscriber lookup |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_GET_3CJ_SMS_TEMPLATE` | Inbound 3CJ response with template list |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking; Response array |

### §19.3 — ResponseBase Concept Construction

> **Pattern A (correct):** Java `String extId = OMXUtils.generateTrackingID();` → passed as `$extId` XSLT param → `<xsl:value-of select="$extId"/>`. No null/timing issue.

```text
createObject
└── object
    ├── @extId              ← $extId (= OMXUtils.generateTrackingID() — Java variable)  [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode                                [Always]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg                                 [Always]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus                            [Always]
    └── ReferenceId         ← $eventResponse/RefID                                      [Always]
```

### §19.4 — Template Content Enrichment

For each subscriber matching `eventResponse.RefID == subscriber.RefId`:

| Condition | Action |
|-----------|--------|
| `productType=="PARENT"` AND `is_family_type_parent` AND `bundleInfo=="DebundleProductNumber"` | Find child MSISDN via XPath; if found: `String.replaceAll(templateContent, "\\[mobileNo2]", child_msisdn)`; set `smsContent = templateContent` |
| All other cases (DebundleProductNumber CHILD, or DebundleCampaign PARENT/CHILD) | `smsContent = templateContent` (no placeholder substitution) |

After template loop: `subscriber.ExtendedInfo[SMS_MSG] = smsContent`

> [MEDIUM] If 3CJ returns multiple `omxnNotiTemplate` entries, the loop overwrites `smsContent` each iteration. Only the **last** template content is stored in `ExtendedInfo[SMS_MSG]`.

### §19.5 — Response Completion Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

```java
if (currActivity.RequestCount == successResponseCount) { return "true"; }
else { return "false"; }
```

Standard correct fan-in. Per-subscriber RefID correlation is present in ResponseBase — fan-in does not rely on count-only matching.

### §19.6 — Response Audit Logging

| Field | Value |
|-------|-------|
| `PROCESS_ID` | `concat(pid, "_RES")` |
| `OPERATION_NAME` | `"OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE"` |
| `TARGET_SYSTEM` | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| `AUDIT_TRACE` | `"Response received for OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE"` |
| `payload/ns:ServicePayload` | Copy of full `$eventResponse` — **always included, no WritePayload gate** |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
