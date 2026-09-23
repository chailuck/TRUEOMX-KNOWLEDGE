# Request_SEND_SMS_MESSAGE_3CJ

> TIBCO BusinessEvents · FM Logic Documentation
> Backend: 3CJ / Whatup SMS Gateway · Operation: SendSMS (Mobile Terminated) · Author: TIT_CP-CHAYAT2

---

## §1 — Overview & Purpose

**Request_SEND_SMS_MESSAGE_3CJ** is the final FM in the `POSTPAID_REMOVE_OFFER_SUB` process. It delivers the debundle campaign SMS notification to each subscriber via the 3CJ Whatup SMS gateway. The SMS body is read from `subscriber.ExtendedInfo[SMS_MSG]` — pre-resolved and stored by the preceding FM **OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE**. Subscribers with a blank or null `SMS_MSG` are silently skipped.

The FM performs mobile number internationalisation (replaces leading `0` with `66`), resolves the subscriber language (two-step, same as the template FM), generates a Bangkok-timezone timestamp, then dispatches a fully-formed SMS payload to the Whatup gateway. The schema (`WhatupSMS.xsd`) represents the gateway-specific SMS wire format.

> **[HIGH] assetnumber hardcoded as "" — UserName header never emitted:** The local variable `assetnumber = ""` (comment: "none mobile") means the `<UserName>` field guarded by `string-length($assetnumber) > 0` is *always* suppressed. The field is dead code. The `PassWord` header is reused to carry the subscriber's language code — an unconventional field repurposing that could mislead monitoring tools.

> **[MEDIUM] No event @extId generated:** The request XSLT does not include `<xsl:attribute name="extId">`. TIBCO BE assigns an auto-generated extId. All other FMs in this process explicitly call `OMXUtils:generateTrackingID()`. This means the event cannot be cross-referenced by a caller-controlled tracking ID.

> **Note — Implicit SOURCE filter:** Unlike OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE, this FM has no multi-POU SOURCE/TARGET detection. However, only SOURCE subscribers will have a non-blank `SMS_MSG` ExtendedInfo (since the template FM only writes it for SOURCE subscribers). TARGET subscribers are therefore skipped implicitly via the blank SMS_MSG gate.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_SEND_SMS_MESSAGE_3CJ` | Full qualified path |
| Priority | `5` | Standard FM priority |
| Forward chain | `true` | Rule re-evaluates after THEN actions |
| Rule type | Request Dispatcher | Subscriber fan-out via SEND_SMS_MESSAGE_3CJ event |
| Author | `TIT_CP-CHAYAT2` | Developer identifier |
| Backend system | 3CJ / Whatup SMS Gateway | "Whatup" is the SMS platform schema name; delivers MT SMS |
| Event type (outbound) | `Events.OMConsumers.OMXFM.Request.SEND_SMS_MESSAGE_3CJ` | Distinct event type — not shared |
| Event type (response) | `Events.OMConsumers.OMXFM.Response.SEND_SMS_MESSAGE_3CJ` | Matched by response rulefunction |
| Dispatch pattern | `Event.Ext.sendEventImmediate` | Per-subscriber fan-out; resubmit-skip via SubscriberId + CompletionStatus==2 |
| Schema | `WhatupSMS.xsd` | Namespace: Schemas/ESB/Whatup/WhatupSMS.xsd |
| Position in process | Step 73 of 74 | Final SMS delivery step in POSTPAID_REMOVE_OFFER_SUB |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order; subscriber loop, SMS content, mobile number |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity; RequestCount, Response array, Status, PreExecCheck |

---

## §4 — Rule Conditions (WHEN)

| # | Condition Expression | Purpose |
|---|---------------------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Binds activity to current order's next slot |
| 2 | `orderCurrentActivity.ActivityID == "SEND_SMS_MESSAGE_3CJ"` | Restricts rule to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SEND_SMS_MESSAGE_3CJ"` | Double-checks order flow pointer |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires when activity is in WAITING state |

---

## §5 — Execution Flow Diagram

1. Compute resubmit flag: `isActResub = (RequestCount > 0 && IsOrderResubmitted)`
2. Iterate ALL ParentOU and their Subscriber entries — no SOURCE/TARGET filter
3. Resubmit-skip: check Response array for `ReferenceId == subscriber.SubscriberId && CompletionStatus == 2` (uses SubscriberId not RefId)
4. Per-subscriber PreExecCheck: if configured, `GetXMLForSubscriber(orderRequest, subscriber.RefId)` + XPath; skip if not "true"
5. SMS gate: XPath `$subscriber/ExtendedInfo[Name='SMS_MSG']/Value` → `sms_message`; if blank → skip subscriber (implicit SOURCE filter)
6. Language resolution (2-step): try `subscriber.SubscriberGeneralInfo.Language`; if blank: fallback to TARGET ParentOU subscriber with same MSISDN
7. Mobile number internationalisation: if `mobile_number.startsWith("0")`: `String.replaceFirst("0", "66")` — Thai local to international format
8. Bangkok timestamp: `DateTime.now()` → `translateTime("Asia/Bangkok")` → `format("yyyy-MM-dd'T'HH:mm:ssZ")` → `createDate`
9. Dispatch SEND_SMS_MESSAGE_3CJ event via `sendEventImmediate`; if not resubmit: `RequestCount++`; emit audit log (WritePayload-gated)
10. If any dispatch: Status → SENT + DB persist; else: SkipActivity
11. Exception: `HandleActivityException`

---

## §6 — Rule Action (THEN) — Step-by-Step Logic

**SMS gate (reads previous FM output):**

```java
String sms_message = XPath.evalAsString("$subscriber/ExtendedInfo[Name='SMS_MSG']/Value");
if(!RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(sms_message)) {
    // only dispatch if SMS content was resolved by OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE
}
```

**Language resolution (same two-step as OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE):**

```java
String language = "";
if(subscriber.SubscriberGeneralInfo != null) { language = subscriber.SubscriberGeneralInfo.Language; }
if(IsBlankOrStringNull(language)) {
    language = XPath.evalAsString(
        "$orderRequest/OrderData/Customer/ParentOU"
        + "[ExtendedInfo[Name='SOURCE_OR_TARGET' and Value='TARGET']]"
        + "/Subscriber[MSISDN=$mobile_number]/SubscriberGeneralInfo/Language");
}
```

**Mobile number internationalisation:**

```java
String mobile_number = pOu.Subscriber[subs].MSISDN;
if (String.startsWith(mobile_number, "0")) {
    mobile_number = String.replaceFirst(mobile_number, "0" , "66");
}
// Examples: "0891234567" → "66891234567"
// Note: replaces FIRST "0" occurrence; handles only Thai local format
```

**Bangkok timestamp generation:**

```java
DateTime createDateFormat = DateTime.now();
if(createDateFormat != null) {
    createDateFormat = DateTime.translateTime(createDateFormat, "Asia/Bangkok");
    createDate = DateTime.format(createDateFormat, "yyyy-MM-dd'T'HH:mm:ssZ");
}
// Output example: "2024-08-01T14:30:00+0700"
```

**Dead code — assetnumber hardcoded:**

```java
String assetnumber = ""; // none mobile
// UserName header: guarded by string-length($assetnumber) > 0 → ALWAYS FALSE → UserName never emitted
// PassWord header: guarded by string-length($language) > 0 → carries language code when set
```

> **[HIGH] Dead code:** `assetnumber` is always `""`. The XSLT guard `string-length($assetnumber) > 0` is always false, so `<UserName>` is never included in the event. `<PassWord>` is repurposed to carry the language code — an unusual semantic that should be documented for the Whatup gateway integration team.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in **POSTPAID_REMOVE_OFFER_SUB** and other flows with convergence debundle scenarios requiring SMS notifications. This is the last FM in the order flow — step 73 of 74 in POSTPAID_REMOVE_OFFER_SUB. Upstream dependency: `subscriber.ExtendedInfo[SMS_MSG]` must be populated by **OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE**.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Protocol | Purpose |
|-----------|-----------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.SEND_SMS_MESSAGE_3CJ` | JMS / TIBCO EMS | Dispatch SMS to 3CJ Whatup gateway per subscriber |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.SEND_SMS_MESSAGE_3CJ` | JMS / TIBCO EMS | Receive delivery confirmation from 3CJ gateway |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | JMS | Request/response audit trail |

### §8.3 — Backend API Details

| System | Operation | Schema | Request Element | Correlation |
|--------|-----------|--------|-----------------|-------------|
| 3CJ / Whatup SMS Gateway | SendSMS (Mobile Terminated) | `Whatup/WhatupSMS.xsd` | `ns:message/ns:sms` (`type="mt"`) | `RefID` ← `subscriber.SubscriberId` (per-subscriber; uses SubscriberId not RefId) |

> The response rulefunction also correlates on `SubscriberId` (not `RefId`). This is internally consistent but diverges from the majority of FMs in this process which use `subscriber.RefId` for correlation.

### §8.4 — BE Working Memory Dependencies

| Field | Access | Purpose |
|-------|--------|---------|
| `orderRequest.OrderData.Customer.ParentOU[i].Subscriber[subs]` | READ | Subscriber loop (ALL ParentOU, no SOURCE filter) |
| `subscriber.SubscriberId` | READ | RefID in event; resubmit-skip correlation |
| `subscriber.MSISDN` | READ | Destination mobile number (pre-internationalisation) |
| `subscriber.RefId` | READ | PreExecCheck serialisation only |
| `subscriber.SubscriberGeneralInfo.Language` | READ | Primary language; sent as PassWord header |
| `subscriber.ExtendedInfo[Name='SMS_MSG']/Value` | READ | SMS body resolved by previous FM; blank → skip |
| `orderRequest.OrderData.OMXTrackingId` | READ | JMSCorrelationID + audit ESBUUID |
| `orderRequest.OrderData.OrderID` | READ | Event header |
| `orderRequest.OrderData.OrderType` | READ | Event header |
| `orderRequest.IsOrderResubmitted` | READ | Resubmit flag |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-out counter |
| `orderCurrentActivity.Response` | WRITE (response) | Append ResponseBase records |
| `orderCurrentActivity.Status` | WRITE | Set to SENT after dispatch |

### §8.5 — ExtendedInfo Fields

| Name | Access | Source | Purpose |
|------|--------|--------|---------|
| `SMS_MSG` | READ | Subscriber.ExtendedInfo | SMS body written by OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE; blank → skip subscriber |

### §8.6 — Global Variable Dependencies

| Variable Path | Used In | Purpose |
|--------------|---------|---------|
| `$globalVariables/OMX_OM/Services/SEND_SMS_MSG_3CJ/serviceid` | Request payload | ns:service-id — Whatup gateway service identifier |
| `$globalVariables/OMX_OM/Services/SEND_SMS_MSG_3CJ/shortcodesms` | Request payload | ns:source/ns:number — abbreviated short code sender |
| `$globalVariables/OMX_OM/Services/SEND_SMS_MSG_3CJ/originate` | Request payload | ns:source/ns:originate — international origination number |
| `$globalVariables/OMX_OM/Services/SEND_SMS_MSG_3CJ/sender` | Request payload | ns:source/ns:sender — sender name/alias |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Request audit logger | COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Both loggers | TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Both loggers | LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Request audit logger | Gates payload inclusion (correct) |

> **Request logger is CORRECT:** The request logger XSLT properly gates payload on `$globalVariables/OMX_OM/WritePayload="true"` and includes the full `$reqEvent` as payload — best practice. The *response* logger does NOT have this gate (always includes payload) — same issue as OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE.

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Role |
|-----------|-----------|------|
| `$orderRequest` | BE concept `orderRequest` | Root order data; JMS headers, order identifiers |
| `$subscriber` | BE concept `subscriber` | Subscriber data; SubscriberId for RefID; ExtendedInfo[SMS_MSG] |
| `$assetnumber` | Hardcoded `""` | Dead param — UserName field never emitted (always empty) |
| `$language` | Resolved language string (2-step) | PassWord header (language code reused in this field) |
| `$globalVariables` | BE global variable store | SEND_SMS_MSG_3CJ service config: serviceid, shortcodesms, originate, sender |
| `$mobile_number` | Internationalised MSISDN | ns:destination/ns:number (66x format) |
| `$sms_message` | `subscriber.ExtendedInfo[SMS_MSG]/Value` | ns:ud (SMS body text) |
| `$createDate` | Bangkok-localised `DateTime.now()` | ns:scts (service centre timestamp) |

### §9.2 — Event Container

| Field | Source | Notes |
|-------|--------|-------|
| `event @extId` | Not set in XSLT — BE auto-generates | **[MEDIUM]** Unique from all other FMs — no `OMXUtils:generateTrackingID()` call |
| `RefID` | `$subscriber/SubscriberId` | Uses SubscriberId not RefId — consistent with resubmit-skip |

### §9.3 — JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Always |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$subscriber/SubscriberId` | Always (per-subscriber, uses SubscriberId) |
| `UserName` | `$assetnumber` (= "") | Conditional: `string-length($assetnumber) > 0` — ALWAYS FALSE, never emitted |
| `PassWord` | `$language` | Conditional: `string-length($language) > 0` — carries language code |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Always |

### §9.4 — Payload Root Element

`payload / ns:message` — namespace: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/Whatup/WhatupSMS.xsd`

### §9.5 — SMS Message Structure

| Element | Attribute | Source / Value | Purpose |
|---------|-----------|---------------|---------|
| `ns:sms` | `type="mt"` (static) | Always | Mobile Terminated — SMS sent TO subscriber |
| `ns:service-id` | — | `$globalVariables/…/serviceid` | Whatup gateway service identifier |
| `ns:destination/ns:address/ns:number` | `type="international"` (static) | `$mobile_number` (66x format) | Subscriber's international mobile number |
| `ns:source/ns:address/ns:number` | `type="abbreviated"` (static) | `$globalVariables/…/shortcodesms` | Short code sender number |
| `ns:source/ns:address/ns:originate` | `type="international"` (static) | `$globalVariables/…/originate` | International origination number |
| `ns:source/ns:address/ns:sender` | — | `$globalVariables/…/sender` | Sender name/alias displayed on handset |
| `ns:ud` | `type="text" encoding="utf-8"` (static) | `$sms_message` | User data — actual SMS body text |
| `ns:scts` | — | `$createDate` (Asia/Bangkok) | Service Centre Time Stamp |
| `ns:dro` | — | `"true"` (static) | Delivery Receipt Option — request delivery confirmation |

> `ns:destination` is conditionally emitted: only if `string-length($mobile_number) > 0`. In practice `mobile_number` is always non-empty (from MSISDN), but the guard exists.

### §9.7 — Complete Generated XML Example

```xml
<createEvent>
  <event>  <!-- @extId auto-generated by BE -- not set in XSLT [MEDIUM] -->
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20240801-001</JMSCorrelationID>
    <OrderID>ORD-9001</OrderID>
    <RefID>SUB-ID-001</RefID>  <!-- subscriber.SubscriberId, not RefId -->
    <!-- UserName: NEVER emitted (assetnumber always "") -->
    <PassWord>TH</PassWord>  <!-- language code repurposed in this field -->
    <OrderType>POSTPAID_REMOVE_OFFER_SUB</OrderType>
    <payload>
      <ns:message xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/Whatup/WhatupSMS.xsd">
        <ns:sms type="mt">
          <ns:service-id>omx-sms-svc-01</ns:service-id>
          <ns:destination>
            <ns:address>
              <ns:number type="international">66891234567</ns:number>
            </ns:address>
          </ns:destination>
          <ns:source>
            <ns:address>
              <ns:number type="abbreviated">4882</ns:number>
              <ns:originate type="international">6629999999</ns:originate>
              <ns:sender>TrueMove H</ns:sender>
            </ns:address>
          </ns:source>
          <ns:ud type="text" encoding="utf-8">Your TrueMove H debundle campaign has been processed.</ns:ud>
          <ns:scts>2024-08-01T14:30:00+0700</ns:scts>
          <ns:dro>true</ns:dro>
        </ns:sms>
      </ns:message>
    </payload>
  </event>
</createEvent>
```

### §9.8 — XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/Whatup/WhatupSMS.xsd"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
  version="1.0"
  exclude-result-prefixes="xsl ns xsd tib">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/>     <!-- root order concept -->
  <xsl:param name="subscriber"/>      <!-- subscriber BE concept -->
  <xsl:param name="assetnumber"/>     <!-- always "" — dead param -->
  <xsl:param name="language"/>        <!-- subscriber language; sent as PassWord header -->
  <xsl:param name="globalVariables"/> <!-- service config: serviceid/shortcodesms/originate/sender -->
  <xsl:param name="mobile_number"/>   <!-- internationalised MSISDN (66x) -->
  <xsl:param name="sms_message"/>     <!-- SMS body from ExtendedInfo[SMS_MSG] -->
  <xsl:param name="createDate"/>      <!-- Asia/Bangkok formatted timestamp -->
  <xsl:template match="/">
    <createEvent>
      <event>  <!-- no @extId attribute — BE auto-assigns [MEDIUM] -->
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <RefID><xsl:value-of select="$subscriber/SubscriberId"/></RefID>   <!-- SubscriberId not RefId -->
        <xsl:if test="string-length($assetnumber) > 0">   <!-- ALWAYS FALSE — dead code -->
          <UserName><xsl:value-of select="$assetnumber"/></UserName>
        </xsl:if>
        <xsl:if test="string-length($language) > 0">     <!-- language as PassWord -->
          <PassWord><xsl:value-of select="$language"/></PassWord>
        </xsl:if>
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        <payload>
          <ns:message>
            <ns:sms>
              <xsl:attribute name="type"><xsl:value-of select="'mt'"/></xsl:attribute>
              <ns:service-id><xsl:value-of select="$globalVariables/OMX_OM/Services/SEND_SMS_MSG_3CJ/serviceid"/></ns:service-id>
              <xsl:if test="string-length($mobile_number) > 0">
                <ns:destination>
                  <ns:address>
                    <ns:number>
                      <xsl:attribute name="type"><xsl:value-of select="'international'"/></xsl:attribute>
                      <xsl:value-of select="$mobile_number"/>
                    </ns:number>
                  </ns:address>
                </ns:destination>
              </xsl:if>
              <ns:source>
                <ns:address>
                  <ns:number>
                    <xsl:attribute name="type"><xsl:value-of select="'abbreviated'"/></xsl:attribute>
                    <xsl:value-of select="$globalVariables/OMX_OM/Services/SEND_SMS_MSG_3CJ/shortcodesms"/>
                  </ns:number>
                  <ns:originate>
                    <xsl:attribute name="type"><xsl:value-of select="'international'"/></xsl:attribute>
                    <xsl:value-of select="$globalVariables/OMX_OM/Services/SEND_SMS_MSG_3CJ/originate"/>
                  </ns:originate>
                  <ns:sender><xsl:value-of select="$globalVariables/OMX_OM/Services/SEND_SMS_MSG_3CJ/sender"/></ns:sender>
                </ns:address>
              </ns:source>
              <ns:ud>
                <xsl:attribute name="type"><xsl:value-of select="'text'"/></xsl:attribute>
                <xsl:attribute name="encoding"><xsl:value-of select="'utf-8'"/></xsl:attribute>
                <xsl:value-of select="$sms_message"/>
              </ns:ud>
              <ns:scts><xsl:value-of select="$createDate"/></ns:scts>
              <ns:dro><xsl:value-of select="'true'"/></ns:dro>
            </ns:sms>
          </ns:message>
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
└── event                              [no @extId — BE auto-generates [MEDIUM]]
    ├── JMSPriority                    ← $orderRequest/OrderPriority                          [Always]
    ├── JMSCorrelationID               ← $orderRequest/OrderData/OMXTrackingId                [Always]
    ├── OrderID                        ← $orderRequest/OrderData/OrderID                      [Always]
    ├── RefID                          ← $subscriber/SubscriberId  (SubscriberId not RefId)   [Always]
    ├── UserName                       ← $assetnumber (= "")                                  [NEVER emitted — dead code]
    ├── PassWord                       ← $language  (language code repurposed)                [Conditional: string-length($language) > 0]
    ├── OrderType                      ← $orderRequest/OrderData/OrderType                    [Always]
    └── payload
        └── ns:message
            └── ns:sms  @type="mt"                                                            [Always]
                ├── ns:service-id      ← $globalVariables/.../serviceid                       [Always]
                ├── ns:destination                                                            [Conditional: string-length($mobile_number) > 0]
                │   └── ns:address
                │       └── ns:number @type="international"  ← $mobile_number (66x format)
                ├── ns:source                                                                 [Always]
                │   └── ns:address
                │       ├── ns:number @type="abbreviated"  ← $globalVariables/.../shortcodesms
                │       ├── ns:originate @type="international"  ← $globalVariables/.../originate
                │       └── ns:sender  ← $globalVariables/.../sender
                ├── ns:ud @type="text" @encoding="utf-8"  ← $sms_message                     [Always]
                ├── ns:scts            ← $createDate (Asia/Bangkok yyyy-MM-dd'T'HH:mm:ssZ)   [Always]
                └── ns:dro             ← "true" (static)  delivery receipt on                [Always]
```

Legend: `[Always]` = no xsl:if guard · `[Conditional: ...]` = inside xsl:if · `[NEVER emitted]` = always-false guard (dead code) · XPath source = working memory · quoted literal = static value

---

## §11 — Audit Logging

| Phase | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE | TARGET_SYSTEM | Payload |
|-------|-----------|----------------|-------------|---------------|---------|
| REQUEST | `concat(pid, "_REQ")` | `"SEND_SMS_MESSAGE_3CJ"` | `"Request for SEND_SMS_MESSAGE_3CJ"` | `OMX_FM` | `$reqEvent` copy — **gated on WritePayload="true"** ✓ |
| RESPONSE | `concat(pid, "_RES")` | `"SEND_SMS_MESSAGE_3CJ"` | `"Response received for SEND_SMS_MESSAGE_3CJ"` | `OMX_FM` | `$eventResponse` copy — **always included, no WritePayload gate** |

> **Request logger improvement:** This FM's request logger correctly uses `$reqEvent` as the payload (the actual outbound event) and gates it on `WritePayload="true"` — a better pattern than other recent FMs. The response logger still has the same always-include issue.

---

## §12 — Activity Status Management

| Scenario | Status Code | Function | Meaning |
|----------|------------|---------|---------|
| At least one subscriber SMS dispatched | `"1"` | `GetActivityStatusString("1", false)` | SENT |
| No dispatches (all SMS_MSG blank, or PreExecCheck false) | `"4"` | `SkipActivity(…, "4")` | SKIPPED |

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

> The response rulefunction has no try/catch — any exception propagates up to the BE rule engine.

---

## §14 — Helper Functions Reference

| Function | Return Type | Purpose |
|----------|------------|---------|
| `RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(str)` | boolean | Gates SMS dispatch on non-blank SMS_MSG; language blank check |
| `RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, subscriber.RefId)` | String | Serialise per-subscriber XML for PreExecCheck |
| `DateTime.now()` | DateTime | Current system time |
| `DateTime.translateTime(dt, "Asia/Bangkok")` | DateTime | Localise to Bangkok timezone (+07:00) |
| `DateTime.format(dt, "yyyy-MM-dd'T'HH:mm:ssZ")` | String | Format as ISO 8601 with timezone offset |
| `String.startsWith(str, "0")` | boolean | Gate for Thai local number format detection |
| `String.replaceFirst(str, "0", "66")` | String | 0XXXXXXXXX → 66XXXXXXXXX internationalisation |
| `GetActivityStatusString("1", false)` | String | Status SENT |
| `SkipActivity(orderRequest, activity, "4")` | void | Skip activity |
| `SendDataToDB(orderRequest)` | void | Persist order state |
| `HandleActivityException(orderRequest, activity, ae, "")` | void | Error handler |

---

## §15 — Function Dependency Tree

```text
Request_SEND_SMS_MESSAGE_3CJ (rule)
├── XPath.evalAsString                                   [SMS_MSG; language fallback]
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull       [SMS_MSG gate; language blank check]
├── RuleFunctions.Helpers.GetXMLForSubscriber            [PreExecCheck serialisation]
├── XPath.execute                                        [PreExecCheck evaluation]
├── String.startsWith                                    [mobile number format detection]
├── String.replaceFirst                                  [0→66 internationalisation]
├── DateTime.now                                         [current time]
├── DateTime.translateTime                               [Asia/Bangkok localisation]
├── DateTime.format                                      [ISO 8601 timestamp]
├── Event.Ext.sendEventImmediate                         [x2: reqEvent + logger per subscriber]
├── RuleFunctions.Helpers.GetActivityStatusString        [status "1"]
├── RuleFunctions.Helpers.SendDataToDB                   [DB persistence]
├── RuleFunctions.Helpers.SkipActivity                   [skip path]
└── RuleFunctions.Helpers.HandleActivityException        [error handling]

Response_SEND_SMS_MESSAGE_3CJ (rulefunction)
├── OMXUtils.generateTrackingID()                        [Java variable → $extId param → ResponseBase @extId — Pattern A]
├── Instance.createInstance (ResponseBase XSLT)          [construct response record]
├── Event.Ext.sendEventImmediate                         [response audit logger]
└── XPath.evalAsInt                                      [fan-in count]
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Fields Used | Role |
|---------|----------------|------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.Customer.ParentOU[], OrderData.OMXTrackingId, OrderData.OrderID, OrderData.OrderType, OrderPriority | Root order |
| `Concepts.OrderRequest.OrderElements.Subscriber` | SubscriberId, RefId, MSISDN, SubscriberGeneralInfo.Language, ExtendedInfo[SMS_MSG] | Per-subscriber data; SMS content source |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck | Activity tracking |
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId | Normalised response record |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement | Evidence |
|----|------------|---------|
| R1 | Deliver MT SMS per subscriber via 3CJ Whatup gateway using SMS body from ExtendedInfo[SMS_MSG] | Rule: SMS gate + event dispatch |
| R2 | Transform Thai local MSISDN (0x) to international format (66x) before sending | Rule: `String.replaceFirst("0", "66")` |
| R3 | Generate Bangkok-timezone timestamp for SCTS field | Rule: `DateTime.translateTime("Asia/Bangkok")` |
| R4 | Two-step language resolution: SubscriberGeneralInfo.Language → TARGET ParentOU fallback | Rule: same pattern as OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE |
| R5 | Request delivery receipt from gateway (DRO=true) | XSLT: static `"true"` in ns:dro |
| R6 | Per-subscriber fan-out with standard resubmit-skip on SubscriberId + CompletionStatus==2 | Rule: Response array loop |

### Design Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| `assetnumber` hardcoded as "" — UserName header never emitted; PassWord header repurposed for language code | [HIGH] | Remove dead assetnumber variable; rename PassWord to LanguageCode in the Whatup event schema, or document the field repurposing in the integration spec |
| No event @extId — BE auto-assigns default extId; outbound event cannot be tracked by caller-controlled ID | [MEDIUM] | Add `<xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>` — consistent with all other FMs |
| No explicit SOURCE/TARGET ParentOU filter — implicit coupling to OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE writing only SOURCE subscribers' SMS_MSG | [MEDIUM] | Add explicit SOURCE filter (same as OMX_GET_3CJ_SMS_MESSAGE_TEMPLATE) to make the skip logic explicit and independent of the previous FM's behaviour |
| Response audit logger always includes full response payload — no WritePayload gate | [MEDIUM] | Add `$globalVariables/OMX_OM/WritePayload="true"` guard in response logger XSLT |
| Resubmit-skip uses SubscriberId while most FMs use RefId — diverges from standard correlation pattern | [MEDIUM] | Verify SubscriberId and RefId are consistently available and not null; document divergence in integration guide |
| Mobile number transform uses `String.replaceFirst` which replaces first "0" occurrence, not just leading "0" | [LOW] | Use regex anchor: `String.replaceFirst("^0", "66")` to explicitly match only leading "0" |
| createDate timestamp generated at dispatch time in BE engine — SMS timestamp reflects processing time | [LOW] | Confirm with 3CJ gateway contract whether SCTS must reflect order creation time or delivery dispatch time |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author TIT_CP-CHAYAT2
 */
rule Rules.OMConsumers.OMXFM.Request.Request_SEND_SMS_MESSAGE_3CJ {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "SEND_SMS_MESSAGE_3CJ";
        orderRequest.ProcessFlow.NextActivityID == "SEND_SMS_MESSAGE_3CJ";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            boolean isSkipped = true;
            for(int iPOU = 0; iPOU < orderRequest.OrderData.Customer.ParentOU@length; iPOU++) {
                Concepts.OrderRequest.OrderElements.ParentOU pOu = orderRequest.OrderData.Customer.ParentOU[iPOU];
                for (int subs = 0; subs < pOu.Subscriber@length; subs++) {
                    Concepts.OrderRequest.OrderElements.Subscriber subscriber =
                        orderRequest.OrderData.Customer.ParentOU[iPOU].Subscriber[subs];
                    boolean reqSuccess = false;

                    // Resubmit-skip: uses SubscriberId (not RefId)
                    if(isActResub) {
                        for(int iResp=0; iResp<orderCurrentActivity.Response@length; iResp++) {
                            if(String.equals(orderCurrentActivity.Response[iResp].ReferenceId, subscriber.SubscriberId)
                               && orderCurrentActivity.Response[iResp].CompletionStatus == 2) {
                                reqSuccess = true; break;
                            }
                        }
                    }

                    if(!reqSuccess) {
                        String chkRes = "true";
                        if(String.length(nextAct.PreExecCheck) > 0) {
                            String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, subscriber.RefId);
                            chkRes = XPath.execute("/(" + chkXPath + ")", sXML, "ns0=...");
                        }

                        if(String.equals(chkRes, "true")) {
                            String assetnumber = ""; // none mobile — always "" → UserName never emitted
                            String sms_message = XPath.evalAsString("$subscriber/ExtendedInfo[Name='SMS_MSG']/Value");

                            if(!IsBlankOrStringNull(sms_message)) {
                                String mobile_number = pOu.Subscriber[subs].MSISDN;
                                String language = "";
                                if(subscriber.SubscriberGeneralInfo != null)
                                    language = subscriber.SubscriberGeneralInfo.Language;
                                if(IsBlankOrStringNull(language))
                                    language = XPath.evalAsString("...TARGET ParentOU Subscriber/Language...");

                                // 0XXXXXXXXX → 66XXXXXXXXX
                                if(String.startsWith(mobile_number, "0")) {
                                    mobile_number = String.replaceFirst(mobile_number, "0", "66");
                                }

                                DateTime createDateFormat = DateTime.now();
                                if(createDateFormat != null) {
                                    createDateFormat = DateTime.translateTime(createDateFormat, "Asia/Bangkok");
                                    createDate = DateTime.format(createDateFormat, "yyyy-MM-dd'T'HH:mm:ssZ");
                                }

                                /* Build ns:message/ns:sms event — see §9.8 for full XSLT:
                                   params: $orderRequest, $subscriber, $assetnumber (=""), $language,
                                           $globalVariables, $mobile_number, $sms_message, $createDate
                                   No @extId on event — [MEDIUM]
                                   PassWord = $language (field repurposed)
                                   payload: service-id, destination (international), source (short code,
                                     originate, sender), ud (utf-8 SMS body), scts, dro="true" */
                                Events.OMConsumers.OMXFM.Request.SEND_SMS_MESSAGE_3CJ reqEvent =
                                    Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/SEND_SMS_MESSAGE_3CJ}}...");
                                Event.Ext.sendEventImmediate(reqEvent);
                                if(!isActResub) orderCurrentActivity.RequestCount++;
                                long pid = System.nanoTime();
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

**Response_SEND_SMS_MESSAGE_3CJ** is the simplest response handler in this process — it creates a ResponseBase record, emits the response audit log, and drives fan-in completion. There is no additional working memory enrichment: the SMS has already been delivered, and no further data needs to be written back to the order concept.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SEND_SMS_MESSAGE_3CJ` | Inbound gateway response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking |

### §19.3 — ResponseBase Concept Construction

> **Pattern A (correct):** Java `String extId = OMXUtils.generateTrackingID();` → XSLT `$extId` param → `<xsl:value-of select="$extId"/>`.

```text
createObject
└── object  @extId ← OMXUtils.generateTrackingID() (Java variable)                           [Always]
    ├── ResponseCode        ← $eventResponse/ResponseCode                                     [Always]
    ├── ResponseMessage     ← $eventResponse/ResponseMsg                                      [Always]
    ├── CompletionStatus    ← $eventResponse/CompletionStatus                                 [Always]
    └── ReferenceId         ← $eventResponse/RefID                                            [Always]
```

### §19.4 — Response Completion Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

```java
if (currActivity.RequestCount == successResponseCount) { return "true"; }
else { return "false"; }
```

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| `PROCESS_ID` | `concat(pid, "_RES")` |
| `OPERATION_NAME` | `"SEND_SMS_MESSAGE_3CJ"` |
| `TARGET_SYSTEM` | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| `AUDIT_TRACE` | `"Response received for SEND_SMS_MESSAGE_3CJ"` |
| `payload/ns:ServicePayload` | Copy of full `$eventResponse` — **always included, no WritePayload gate** |

> No try/catch in response rulefunction body — exceptions propagate to BE rule engine.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
