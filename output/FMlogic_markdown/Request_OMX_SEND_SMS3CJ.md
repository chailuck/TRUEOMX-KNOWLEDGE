# Request_OMX_SEND_SMS3CJ

> Sends an SMS notification to prepaid subscribers via the 3CJ SMS gateway using the pre-fetched template content. Conditional on SMS_MSG presence.

---

## §1 Overview & Purpose

Loops over ParentOU Subscribers, evaluates a PreExecCheck gate (`count(SMS_MSG non-empty) > 0`), and for each qualifying subscriber formats the mobile number to international format, retrieves Bangkok timezone timestamp, builds Basic auth from `SMS_AUTHEN` ExtendedInfo, and dispatches the SMS through the 3CJ gateway (`OMX_SEND_SMS3CJ` event) using a WhatupSMS schema payload.

There is a commented-out WHATUP_SEND_SMS variant — the active path uses the 3CJ gateway.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_OMX_SEND_SMS3CJ` |
| Priority | 5 |
| forwardChain | true |
| Author | TIT_CP-CHAYAT2 |
| ActivityID matched | `OMX_SEND_SMS3CJ` |
| Target event | `/Events/OMConsumers/OMXFM/Request/OMX_SEND_SMS3CJ` |
| Response rulefunction | `Response_OMX_SEND_SMS3CJ` |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity node |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Active next step |
| 2 | `orderCurrentActivity.ActivityID == "OMX_SEND_SMS3CJ"` | FM selector |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_SEND_SMS3CJ"` | Process flow confirmation |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Awaiting execution |

---

## §5 Execution Flow Diagram

```
1. Load nextAct; compute isActResub
2. Loop ParentOU[i].Subscriber[j]
3. → Resubmit guard: skip if Response[SubscriberId + CompletionStatus=2] exists
4. → PreExecCheck gate: count(SMS_MSG non-empty) > 0
5. → Extract sms_message from subscriber.ExtendedInfo[SMS_MSG]/Value
6. → Format mobile_number: replace leading "0" with "66"
7. → Get createDate in Asia/Bangkok timezone
8. → Extract basicAuthen = "Basic " + ExtendedInfo[SMS_AUTHEN]/Value
9. → Build and send OMX_SEND_SMS3CJ event (WhatupSMS)
10. → Increment RequestCount (non-resubmit only)
11. → Send audit Logger event
12. Post-loop: status "1" if any sent; SkipActivity("4") otherwise
```

---

## §6 Rule Action (THEN)

- **Resubmit detection:** `isActResub = (RequestCount > 0 && IsOrderResubmitted)` — checked against Response by `SubscriberId`
- **PreExecCheck:** `count(//Subscriber//ExtendedInfo[Name/text()='SMS_MSG' and Value/text()!='']) > 0`
- **Mobile number formatting:** `if startsWith(MSISDN,"0") → replaceFirst("0","66")`
- **Authentication:** `basicAuthen = "Basic " + SMS_AUTHEN` (blank-checked via `IsBlankOrStringNull`)
- **Service-id logic:** uses `ExtendedInfo[SMS_SERVICEID]` if present, else falls back to `globalVars/.../serviceid`
- **Originate omission:** omit `<ns:originate>` when serviceid starts-with "72", "21", or "22"

---

## §7 Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| `sms_message` | `subscriber.ExtendedInfo[Name='SMS_MSG']/Value` | XPath eval |
| `mobile_number` | `Subscriber.MSISDN` | Leading "0" → "66" |
| `createDate` | `DateTime.now()` → Bangkok TZ | `yyyy-MM-dd'T'HH:mm:ssZ` |
| `basicAuthen` | `orderRequest.OrderData.ExtendedInfo[SMS_AUTHEN]/Value` | Prefixed "Basic " |

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

No order type restriction. Execution gated by `SMS_MSG` presence.

### §8.2 ESB / JMS Channels

| Direction | Event Path | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `/Events/OMConsumers/OMXFM/Request/OMX_SEND_SMS3CJ` | Send SMS via 3CJ gateway |
| [OUTBOUND] | `/Events/OMConsumers/OMXESB/Logger` | Audit log |

### §8.3 Backend API Details

| System | Operation | Schema |
|--------|-----------|--------|
| 3CJ SMS Gateway | Send SMS MT | WhatupSMS schema |

### §8.4 BE Working Memory

| Field | Access |
|-------|--------|
| `orderCurrentActivity.RequestCount` | Read/Write |
| `orderCurrentActivity.Status` | Write |
| `subscriber.MSISDN` | Read |
| `subscriber.SubscriberId` | Read (resubmit guard) |

### §8.5 ExtendedInfo Fields

| Name | Required? | Source | Purpose |
|------|-----------|--------|---------|
| `SMS_MSG` | Required (gate) | subscriber.ExtendedInfo | SMS body (from template-fetch step) |
| `SMS_AUTHEN` | Optional | orderRequest.ExtendedInfo | Basic auth credential |
| `SMS_SERVICEID` | Optional | orderRequest.ExtendedInfo | Override service-id; affects originate logic |

### §8.6 Global Variable Dependencies

| Path | Used For |
|------|---------|
| `OMX_OM/Services/OMX_SEND_SMS_3CJ/serviceid` | Default service-id |
| `OMX_OM/Services/OMX_SEND_SMS_3CJ/shortcodesms` | SMS source short code |
| `OMX_OM/Services/OMX_SEND_SMS_3CJ/originate` | Originate number (conditional) |
| `OMX_OM/Services/OMX_SEND_SMS_3CJ/sender` | Sender name |
| `OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `OMX_OM/WritePayload` | Payload logging gate |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Param | Bound From |
|-------|-----------|
| `orderRequest` | OrderRequest concept |
| `subscriber` | `ParentOU[i].Subscriber[j]` |
| `basicAuthen` | `"Basic " + SMS_AUTHEN` |
| `globalVariables` | Global variable tree |
| `mobile_number` | Formatted MSISDN |
| `sms_message` | `ExtendedInfo[SMS_MSG]/Value` |
| `createDate` | Bangkok ISO timestamp |

### §9.2 Event Container

Event type: `Events.OMConsumers.OMXFM.Request.OMX_SEND_SMS3CJ`

### §9.3 JMS/Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| JMSPriority | `$orderRequest/OrderPriority` | Always |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` | Always |
| OrderID | `$orderRequest/OrderData/OrderID` | Always |
| RefID | `$subscriber/SubscriberId` | if SubscriberId exists |
| OrderType | `$orderRequest/OrderData/OrderType` | Always |
| SMS_AUTHEN | `$basicAuthen` | Always (may be empty) |

### §9.4 Payload Root Element

`ns:message/ns:sms @type="mt"` (mobile terminated)

### §9.5 Conditional Fields

| Field | Condition | Source |
|-------|-----------|--------|
| `ns:destination/ns:address/ns:number` | `mobile_number` non-empty | formatted MSISDN |
| `ns:originate` | serviceid NOT starting-with "72", "21", "22" | `globalVars/.../originate` |

### §9.6 Core Payload Fields

| Element | Source | Notes |
|---------|--------|-------|
| `ns:service-id` | `SMS_SERVICEID` ExtendedInfo or globalVars default | Conditional select |
| `ns:number @type="abbreviated"` | `globalVars/.../shortcodesms` | Always |
| `ns:originate @type="international"` | `globalVars/.../originate` | Conditional |
| `ns:sender` | `globalVars/.../sender` | Always |
| `ns:ud @type="text" @encoding="unicode"` | `$sms_message` | Always |
| `ns:scts` | `$createDate` | Always |
| `ns:dro` | `"true"` (static) | Always |

### §9.8 XSLT Stylesheet Source

```xml
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/Whatup/WhatupSMS.xsd"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="subscriber"/>
  <xsl:param name="basicAuthen"/>    <!-- "Basic " + SMS_AUTHEN ExtendedInfo -->
  <xsl:param name="globalVariables"/>
  <xsl:param name="mobile_number"/>  <!-- MSISDN with 0→66 prefix -->
  <xsl:param name="sms_message"/>    <!-- from ExtendedInfo[SMS_MSG] -->
  <xsl:param name="createDate"/>     <!-- Bangkok ISO timestamp -->
  <xsl:template match="/">
    <createEvent><event>
      <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      <xsl:if test="$subscriber/SubscriberId">
        <RefID><xsl:value-of select="$subscriber/SubscriberId"/></RefID>
      </xsl:if>
      <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      <SMS_AUTHEN><xsl:value-of select="$basicAuthen"/></SMS_AUTHEN>
      <payload><ns:message>
        <ns:sms type="mt">
          <!-- service-id: use SMS_SERVICEID if present, else globalVar -->
          <ns:service-id><!-- see §9.6 conditional select --></ns:service-id>
          <xsl:if test="string-length($mobile_number) > 0">
            <ns:destination><ns:address>
              <ns:number type="international"><xsl:value-of select="$mobile_number"/></ns:number>
            </ns:address></ns:destination>
          </xsl:if>
          <ns:source><ns:address>
            <ns:number type="abbreviated"><xsl:value-of select="globalVars/.../shortcodesms"/></ns:number>
            <!-- originate: conditional on serviceid prefix -->
            <xsl:if test="not(starts-with(serviceid,'72') or starts-with(serviceid,'21') or starts-with(serviceid,'22'))">
              <ns:originate type="international"><xsl:value-of select="globalVars/.../originate"/></ns:originate>
            </xsl:if>
            <ns:sender><xsl:value-of select="globalVars/.../sender"/></ns:sender>
          </ns:address></ns:source>
          <ns:ud type="text" encoding="unicode"><xsl:value-of select="$sms_message"/></ns:ud>
          <ns:scts><xsl:value-of select="$createDate"/></ns:scts>
          <ns:dro>true</ns:dro>
        </ns:sms>
      </ns:message></payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority       ← $orderRequest/OrderPriority         [Always]
    ├── JMSCorrelationID  ← $orderRequest/OrderData/OMXTrackingId [Always]
    ├── OrderID           ← $orderRequest/OrderData/OrderID     [Always]
    ├── RefID             ← $subscriber/SubscriberId            [Conditional: SubscriberId exists]
    ├── OrderType         ← $orderRequest/OrderData/OrderType   [Always]
    ├── SMS_AUTHEN        ← $basicAuthen                        [Always]
    └── payload
        └── ns:message
            └── ns:sms @type="mt"
                ├── ns:service-id   ← SMS_SERVICEID or globalVars/serviceid  [Always, conditional select]
                ├── ns:destination → ns:number @type="international" ← $mobile_number  [Conditional: non-empty]
                ├── ns:source → ns:address
                │   ├── ns:number @type="abbreviated" ← globalVars/shortcodesms  [Always]
                │   ├── ns:originate @type="international" ← globalVars/originate  [Conditional: serviceid not starts-with 72/21/22]
                │   └── ns:sender ← globalVars/sender  [Always]
                ├── ns:ud @type="text" @encoding="unicode" ← $sms_message  [Always]
                ├── ns:scts ← $createDate  [Always]
                └── ns:dro ← "true" (static)  [Always]
```

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_REQ")` |
| OPERATION_NAME | `"OMX_SEND_SMS3CJ"` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `"Request for OMX_SEND_SMS3CJ"` |
| payload | `ns:ServicePayload = copy of $reqEvent` [Conditional: WritePayload=true] |

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one SMS sent | `"1"` IN_PROGRESS | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All skipped | `"4"` SKIPPED | `SkipActivity(...)` |

---

## §13 Exception / Error Handling

Outer `try/catch(Exception ae)` → `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `GetXMLForSubscriber(orderRequest, refId)` | Subscriber-scoped XML for PreExecCheck |
| `XPath.evalAsString(SMS_MSG)` | Extract SMS body |
| `XPath.evalAsString(SMS_AUTHEN)` | Extract auth credential |
| `BRMS.IsBlankOrStringNull(basicAuthen)` | Blank check |
| `DateTime.now/translateTime/format` | Bangkok timestamp |
| `String.startsWith/replaceFirst` | Mobile number formatting |
| Standard lifecycle helpers | `GetActivityStatusString`, `SendDataToDB`, `SkipActivity`, `HandleActivityException` |

---

## §15 Function Dependency Tree

```text
Request_OMX_SEND_SMS3CJ
├── Instance.getByExtIdByUri(...)
├── RuleFunctions.Helpers.GetXMLForSubscriber(...)
├── XPath.execute(...)                       [PreExecCheck]
├── XPath.evalAsString(... SMS_MSG ...)
├── String.startsWith / replaceFirst         [number format]
├── DateTime.now / translateTime / format    [Bangkok timestamp]
├── XPath.evalAsString(... SMS_AUTHEN ...)
├── RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(...)
├── Event.createEvent(xslt://OMX_SEND_SMS3CJ)
├── Event.Ext.sendEventImmediate(reqEvent)
├── Event.createEvent(xslt://Logger)
├── Event.Ext.sendEventImmediate(logEvent)
├── RuleFunctions.Helpers.GetActivityStatusString("1")
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)
└── RuleFunctions.Helpers.HandleActivityException(...)
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields |
|---------|-----------|
| `Concepts.OrderRequest.OrderRequest` | OrderData, ExtendedInfo[SMS_AUTHEN/SMS_SERVICEID], Customer.ParentOU[].Subscriber[] |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, PreExecCheck, Response[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, SubscriberId, MSISDN, ExtendedInfo[SMS_MSG] |

---

## §17 Migration Notes & Recommendations

**Functional Requirements**

| ID | Requirement |
|----|-------------|
| R1 | Send SMS via 3CJ gateway using pre-fetched template |
| R2 | Format MSISDN to international format (66-prefix) |
| R3 | Use BasicAuth from ExtendedInfo[SMS_AUTHEN] |
| R4 | Skip if no SMS_MSG content |
| R5 | Support resubmit idempotency |
| R6 | Conditional originate based on service-id prefix |

**Design Risks**

| Risk | Severity | Mitigation |
|------|----------|------------|
| Auth credential in event body — credential leakage risk | [HIGH] | Use vault/credential store in target |
| Commented-out WHATUP variant creates confusion | [MEDIUM] | Remove dead code |
| originate logic depends on serviceid prefix — brittle | [MEDIUM] | Externalize as configurable rule |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_SEND_SMS3CJ {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_SEND_SMS3CJ";
    orderRequest.ProcessFlow.NextActivityID == "OMX_SEND_SMS3CJ";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      boolean isSkipped = true;
      for (...ParentOU[iPOU].Subscriber[subs]...) {
        // Resubmit guard: skip if Response[SubscriberId + CompletionStatus=2]
        // PreExecCheck gate: count(SMS_MSG non-empty) > 0
        if (String.equals(chkRes, "true")) {
          String sms_message = XPath.evalAsString(/* ExtendedInfo[SMS_MSG]/Value */);
          String mobile_number = /* format 0→66 */;
          DateTime createDate = /* Bangkok TZ */;
          String basicAuthen = XPath.evalAsString(/* SMS_AUTHEN */);
          if (!IsBlankOrStringNull(basicAuthen)) basicAuthen = "Basic " + basicAuthen;
          /* Build OMX_SEND_SMS3CJ event via XSLT — see §9.8 */
          /* WhatupSMS payload: service-id, destination (mobile), source, ud (unicode), scts, dro */
          Event.Ext.sendEventImmediate(reqEvent);
          if (!isActResub) orderCurrentActivity.RequestCount++;
          /* Send audit Logger event — see §11 */
          isSkipped = false;
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

## §19 Response Message Rule

### §19.1 Overview

`Response_OMX_SEND_SMS3CJ` appends a standard `ResponseBase` to the activity, sends an audit Logger event (always, not gated by WritePayload), and drives fan-in completion.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_SEND_SMS3CJ` | Gateway response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity |

### §19.3 ResponseBase Construction

```text
createObject
└── object @extId ← OMXUtils.generateTrackingID()
    ├── ResponseCode       ← $eventResponse/ResponseCode     [Always]
    ├── ResponseMessage    ← $eventResponse/ResponseMsg      [Always]
    ├── CompletionStatus   ← $eventResponse/CompletionStatus [Always]
    └── ReferenceId        ← $eventResponse/RefID            [Always]
```

### §19.4 Response Completion Logic

- **Success XPath:** `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])`
- **Fan-in:** `currActivity.RequestCount == successResponseCount` → `"true"` / `"false"`

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"OMX_SEND_SMS_3CJ"` |
| AUDIT_TRACE | `"Response received for OMX_SEND_SMS_3CJ"` |
| payload | `ns:ServicePayload = copy of $eventResponse` (always) |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
