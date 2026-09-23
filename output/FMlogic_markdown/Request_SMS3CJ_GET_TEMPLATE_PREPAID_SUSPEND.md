# Request_SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND

> Fetches the localized SMS notification template for the PREPAID_SUSPEND order flow from the 3CJ SMS template service. Executed only when Channel=DWH_SIMBOX.

---

## §1 Overview & Purpose

Loops over all ParentOU Subscribers, evaluates the PreExecCheck gate (`Channel="DWH_SIMBOX"`), and for each qualifying subscriber sends an `OMX_GET_3CJ_SMS_TEMPLATE` request with the subscriber's language preference. The response handler extracts the returned template content and stores it as `subscriber.ExtendedInfo[SMS_MSG]` for use by the subsequent `OMX_SEND_SMS3CJ` FM.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND` |
| Priority | 5 |
| forwardChain | true |
| Author | TIT_CP-CHAYAT2 |
| ActivityID matched | `SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND` |
| Target event | `/Events/OMConsumers/OMXFM/Request/OMX_GET_3CJ_SMS_TEMPLATE` |
| Response rulefunction | `Response_SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND` |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order request context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity node |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity is the active next step |
| 2 | `orderCurrentActivity.ActivityID == "SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND"` | Correct FM selector |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND"` | Process flow confirmation |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity awaiting execution |

---

## §5 Execution Flow Diagram

```
1. Compute isActResub = (RequestCount > 0 && IsOrderResubmitted)
2. Load nextAct for PreExecCheck lookup
3. Loop ParentOU[i].Subscriber[j]
4. → Resubmit guard: skip if Response[RefId=refId, CompletionStatus=2] exists
5. → PreExecCheck gate: evaluate Channel="DWH_SIMBOX" XPath against subscriber XML slice
6. → Extract language from subscriber.SubscriberGeneralInfo.Language
7. → Build OMX_GET_3CJ_SMS_TEMPLATE event via XSLT; send
8. → Increment RequestCount (non-resubmit only)
9. → Send audit Logger event
10. Post-loop: status "1" if any sent; SkipActivity("4") if all skipped
```

---

## §6 Rule Action (THEN)

**Resubmit detection:** `isActResub = (RequestCount > 0 && IsOrderResubmitted)`

**PreExecCheck evaluation:** Uses `GetXMLForSubscriber(orderRequest, refId)` + `XPath.execute("/("+chkXPath+")", sXML, ns)`. In PREPAID_SUSPEND the gate is `/ns0:OrderRequest/OrderData/Channel/text()="DWH_SIMBOX"`.

**isSkipped flag:** Starts `true`, flipped to `false` after first successful send.

---

## §7 Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| `language` | `subscriber.SubscriberGeneralInfo.Language` | Passed as `languageCode` in payload |
| `refId` | `subscriber.RefId` | Correlation key for resubmit guard and RefID |
| `pid` | `System.nanoTime()` | Audit log correlation |

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

No order type restriction in rule. Execution gated by `Channel="DWH_SIMBOX"` PreExecCheck.

### §8.2 ESB / JMS Channel

| Direction | Event Path | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `/Events/OMConsumers/OMXFM/Request/OMX_GET_3CJ_SMS_TEMPLATE` | Request SMS template from 3CJ service |
| [OUTBOUND] | `/Events/OMConsumers/OMXESB/Logger` | Audit log |

### §8.3 Backend API Details

| System | Operation | Schema |
|--------|-----------|--------|
| 3CJ SMS Template Service | Get template by language/orderType | `ns:OMX_Sms3CJTemplateRequest` |

### §8.4 BE Working Memory

| Field | Access | Notes |
|-------|--------|-------|
| `orderCurrentActivity.RequestCount` | Read/Write | Incremented per subscriber |
| `orderCurrentActivity.Status` | Write | "1" or skipped |
| `orderCurrentActivity.PreExecCheck` | Read | XPath gate |
| `subscriber.SubscriberGeneralInfo.Language` | Read | Language selection |

### §8.5 ExtendedInfo Fields

None read by request rule. Response handler writes `SMS_MSG` to subscriber.ExtendedInfo.

### §8.6 Global Variable Dependencies

| Path | Used In |
|------|---------|
| `globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit Logger COMPONENT_NAME |
| `globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit Logger LOG_LEVEL |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Param | Bound From |
|-------|-----------|
| `orderRequest` | OrderRequest concept |
| `refId` | `subscriber.RefId` |
| `language` | `subscriber.SubscriberGeneralInfo.Language` |

### §9.2 Event Container

- Event type: `Events.OMConsumers.OMXFM.Request.OMX_GET_3CJ_SMS_TEMPLATE`
- extId: `OMXUtils:generateTrackingID()`

### §9.3 JMS/Event Header Fields

| Field | Source |
|-------|--------|
| JMSPriority | `$orderRequest/OrderPriority` |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` |
| OrderID | `$orderRequest/OrderData/OrderID` |
| RefID | `$refId` |
| UserName | `$orderRequest/OrderData/User` |
| PassWord | `$orderRequest/OrderData/Password` |
| OrderType | `$orderRequest/OrderData/OrderType` |

### §9.4 Payload Root Element

`ns:OMX_Sms3CJTemplateRequest`

### §9.5 Conditional Fields

| Field | Condition | Source |
|-------|-----------|--------|
| `ns:orderType` | `$orderRequest/OrderData/OrderType` exists | `$orderRequest/OrderData/OrderType` |

### §9.6 Core Payload Fields

| XML Element | Source | Always? |
|-------------|--------|---------|
| `ns:languageCode` | `$language` | Always |
| `ns:orderType` | `$orderRequest/OrderData/OrderType` | Conditional |

### §9.8 XSLT Stylesheet Source

```xml
<xsl:stylesheet xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/3CJSmsTemplate/OMX_Sms3CJTemplate.xsd"
  version="1.0">
  <xsl:output method="xml"/>
  <xsl:param name="orderRequest"/> <!-- full OrderRequest concept -->
  <xsl:param name="refId"/>        <!-- subscriber.RefId -->
  <xsl:param name="language"/>     <!-- subscriber.SubscriberGeneralInfo.Language -->
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
          </ns:OMX_Sms3CJTemplateRequest>
        </payload>
      </event>
    </createEvent>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event @extId ← OMXUtils:generateTrackingID()                 [Always]
    ├── JMSPriority           ← $orderRequest/OrderPriority       [Always]
    ├── JMSCorrelationID      ← $orderRequest/OrderData/OMXTrackingId  [Always]
    ├── OrderID               ← $orderRequest/OrderData/OrderID   [Always]
    ├── RefID                 ← $refId                            [Always]
    ├── UserName              ← $orderRequest/OrderData/User      [Always]
    ├── PassWord              ← $orderRequest/OrderData/Password  [Always]
    ├── OrderType             ← $orderRequest/OrderData/OrderType [Always]
    └── payload
        └── ns:OMX_Sms3CJTemplateRequest
            ├── ns:languageCode  ← $language                     [Always]
            └── ns:orderType     ← $orderRequest/OrderData/OrderType [Conditional: OrderType exists]
```

---

## §11 Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| PROCESS_ID | `concat($pid, "_REQ")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `"SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND"` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `"Request for SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND"` |
| payload | empty |

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one request sent | `"1"` IN_PROGRESS | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All subscribers skipped | `"4"` SKIPPED | `SkipActivity(orderRequest, activity, "4")` |

---

## §13 Exception / Error Handling

Outer `try/catch(Exception ae)` delegates to `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `GetXMLForSubscriber(orderRequest, refId)` | Build subscriber-scoped XML for XPath evaluation |
| `GetActivityStatusString("1", false)` | Return IN_PROGRESS status string |
| `SendDataToDB(orderRequest)` | Persist order state to DB |
| `SkipActivity(orderRequest, activity, "4")` | Mark skipped, advance flow |
| `HandleActivityException(orderRequest, activity, ae, "")` | Log and set error status |
| `OMXUtils.generateTrackingID()` | Generate UUID extId |

---

## §15 Function Dependency Tree

```text
Request_SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND
├── Instance.getByExtIdByUri(...)
├── RuleFunctions.Helpers.GetXMLForSubscriber(...)
├── XPath.execute(...)
├── Event.createEvent(xslt://OMX_GET_3CJ_SMS_TEMPLATE)
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
| `Concepts.OrderRequest.OrderRequest` | OrderData.OrderID, OMXTrackingId, OrderType, User, Password, OrderPriority, Customer.ParentOU[].Subscriber[], IsOrderResubmitted |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, PreExecCheck, Response[] |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, SubscriberGeneralInfo.Language |

---

## §17 Migration Notes & Recommendations

**Functional Requirements**

| ID | Requirement |
|----|-------------|
| R1 | Fetch localized SMS template by language and order type from 3CJ service |
| R2 | Execute only when Channel=DWH_SIMBOX |
| R3 | Support resubmit idempotency |
| R4 | Write retrieved template to subscriber ExtendedInfo.SMS_MSG (response handler) |

**Design Risks**

| Risk | Severity | Mitigation |
|------|----------|------------|
| Template content stored in subscriber ExtendedInfo — tight coupling | [MEDIUM] | Use dedicated context/order map in target |
| Event type name mismatch: rule vs. event name | [MEDIUM] | Align naming in migration |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND";
    orderRequest.ProcessFlow.NextActivityID == "SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    try {
      boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
      Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
      boolean isSkipped = true;
      long pid = System.nanoTime();

      for (int iPOU = 0; iPOU < orderRequest.OrderData.Customer.ParentOU@length; iPOU++) {
        for (int subs = 0; subs < pOu.Subscriber@length; subs++) {
          // ... resubmit guard: skip if Response[RefId + CompletionStatus=2] exists ...
          // ... PreExecCheck gate via GetXMLForSubscriber + XPath.execute ...
          if (String.equals(chkRes, "true")) {
            String language = subscriber.SubscriberGeneralInfo.Language;
            /* Build OMX_GET_3CJ_SMS_TEMPLATE request event via XSLT — see §9.8 */
            /* Payload: ns:OMX_Sms3CJTemplateRequest { languageCode, orderType(conditional) } */
            Event.Ext.sendEventImmediate(reqEvent);
            if (!isActResub) orderCurrentActivity.RequestCount++;
            /* Send audit Logger event — see §11 */
            isSkipped = false;
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

## §19 Response Message Rule

### §19.1 Overview

`Response_SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND` parses the 3CJ template service reply, extracts all `templateContent` values from the response, concatenates them as the SMS message body, and writes the result back to `subscriber.ExtendedInfo[Name='SMS_MSG']`. Also drives fan-in completion.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Subscriber lookup |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.OMX_GET_3CJ_SMS_TEMPLATE` | 3CJ template response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Activity for response appending |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object @extId ← OMXUtils.generateTrackingID()
    ├── ResponseCode       ← $eventResponse/ResponseCode      [Always]
    ├── ResponseMessage    ← $eventResponse/ResponseMsg       [Always]
    ├── CompletionStatus   ← $eventResponse/CompletionStatus  [Always]
    └── ReferenceId        ← $eventResponse/RefID             [Always]
```

**Additional post-processing:** For the matching subscriber (RefId match), reads `count(xsd2:omxnNotiTemplate)`, loops through each and concatenates `xsd2:templateContent`. Writes new `SubscriberExtendedInfo` with `Name=SMS_MSG, Value=smsContent`.

### §19.4 Response Completion Logic

- **Success XPath:** `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])`
- **Fan-in condition:** `currActivity.RequestCount == successResponseCount`
- Returns `"true"` when all requests succeeded; `"false"` otherwise. Exception returns `"false"`.

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| PROCESS_ID | `concat($pid, "_RES")` |
| OPERATION_NAME | `"SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND"` |
| AUDIT_TRACE | `"Response received for SMS3CJ_GET_TEMPLATE_PREPAID_SUSPEND"` |
| payload | `ns:ServicePayload = copy of $eventResponse` (always) |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
