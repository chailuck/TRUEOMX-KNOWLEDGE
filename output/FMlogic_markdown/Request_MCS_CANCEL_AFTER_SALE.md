# Request_MCS_CANCEL_AFTER_SALE

> TIBCO BusinessEvents · FM Logic Documentation · Backend: MCS (Subscription Management)

---

## §1 — Overview & Purpose

**Request_MCS_CANCEL_AFTER_SALE** cancels an after-sale (AFS) contract with the MCS subscription management system. It is invoked after **MCS_GET_PACKCODE** confirms that a subscriber holds an active after-sale subscription (`MCS_CANCEL_AFS=Y` flag).

This FM is notably more complex than typical MCS FMs: it accepts ten XSLT parameters, applies multi-branch logic for MSISDN selection (old-MSISDN swap), offer name selection (Priceplan vs. contract offer), offer activity date selection (three-way), and subscriber ID mapping (three-way). Activity-level parameters allow the same FM to be reused across different cancellation scenarios.

> **[MEDIUM]** `ParamName="TR_ORIG_CONTRACT_EXPIRE_DATE "` — trailing space may prevent `offer_expire_date` from being sent even when `MAP_PP_EXPIRE=Y`. Verify against actual stored parameter names.

> **[MEDIUM]** `ns:account_id` is always emitted with an empty string — placeholder field never wired to actual data.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_MCS_CANCEL_AFTER_SALE` | Full qualified path |
| Priority | `5` | Standard FM priority |
| Forward chain | `true` | Rule re-evaluates after THEN actions |
| Rule type | Request Dispatcher | Sends outbound event to MCS; awaits response via separate rulefunction |
| Author | Chayatorn Pan. | From file header comment |
| Backend system | MCS | Subscription management — CancelAftersale operation |
| Dispatch pattern | `Event.Ext.sendEventImmediate` | Parallel fan-out |

---

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity; holds RequestCount, Response array, Status, Parameters |

---

## §4 — Rule Conditions (WHEN)

| # | Condition Expression | Purpose |
|---|---------------------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Binds activity to current order's next activity slot |
| 2 | `orderCurrentActivity.ActivityID == "MCS_CANCEL_AFTER_SALE"` | Restricts rule to this FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "MCS_CANCEL_AFTER_SALE"` | Double-checks order flow pointer |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires when activity is in WAITING state |

---

## §5 — Execution Flow Diagram

```
1. Compute isActResub = (RequestCount > 0 && IsOrderResubmitted)
2. Resolve nextAct by extId to access PreExecCheck XPath string
3. ParentOU subscriber loop:
   ├── 3a. Check resubmit-skip (Response[].ReferenceId == refId && CompletionStatus==2)
   ├── 3b. Evaluate PreExecCheck (GetXMLForSubscriber + XPath.execute)
   ├── 3c. Compute 8 activity-level parameters (see §6)
   ├── 3d. Build and dispatch MCS_CANCEL_AFTER_SALE event (sendEventImmediate)
   ├── 3e. Send audit logger event (_REQ suffix)
   └── 3f. Increment RequestCount if !isActResub
4. ChildOU subscriber loop → identical; isShareplanMainNumber XPath uses i,p,q indices
5. If any dispatch: Status = GetActivityStatusString("1", false); SendDataToDB
   Else: SkipActivity(…, "4")
6. catch: HandleActivityException
```

---

## §6 — Rule Action (THEN) — Activity Parameter Computation

```java
// Note: singular vs plural helper function names — different reading paths
String oldMsisdnFlag    = RuleFunctions.Helpers.GetActivityParamValueFromKey(orderCurrentActivity, "oldMsisdnFlag");
boolean isShareplanMainNumber = XPath.evalAsBoolean(
    "not(exists(subscriber/ExtendedInfo[Name='SHAREPLAN_MAIN_NUMBER' and Value!='']))");
String paramOfferName   = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "OFFER_NAME");
String useRowIdCrmParam = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "USE_ROWID_CRM");
String subIdCrm         = RuleFunctions.Helpers.MapSubscriberIdFromCRM(subscriber, useRowIdCrmParam);
String mapPPExpire      = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "MAP_PP_EXPIRE");
String mapOldSub        = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "MAP_OLD_SUB");
String msisdn           = subscriber.MSISDN;
```

> **[MEDIUM]** `GetActivityParamValueFromKey` (singular) vs `GetActivityParameterValueFromKey` (plural) — these read from different elements in the ProcessConfig. Only `oldMsisdnFlag` uses the singular form; all others use plural. Verify both source structures before migration.

---

## §8 — System & Integration Dependencies

### §8.1 — Order Type Dependencies

Used in **POSTPAID_REMOVE_OFFER_SUB** and similar offer-removal / number-change / Shareplan flows requiring after-sale contract cancellation. Gated on `MCS_CANCEL_AFS=Y` ExtendedInfo flag set by the preceding MCS_GET_PACKCODE FM.

### §8.2 — ESB / JMS Channel Dependencies

| Direction | Event Type | Channel / Destination | Protocol | Purpose |
|-----------|-----------|----------------------|----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.MCS_CANCEL_AFTER_SALE` | MCS JMS channel | JMS / TIBCO EMS | Dispatch CancelAftersale request |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.MCS_CANCEL_AFTER_SALE` | MCS response channel | JMS / TIBCO EMS | Receive CancelAftersale response |
| [LOG] | `Events.OMConsumers.OMXESB.Logger` | Audit log channel | JMS | Request/response audit trail |

### §8.3 — Backend API Details

| System | Operation | Schema | Request Element | Correlation |
|--------|-----------|--------|-----------------|-------------|
| MCS | CancelAftersale | `MCS/CancelAftersale.xsd` | `ns:CancelAftersaleRequest` | `RefID` ← `subscriber.RefId` |

### §8.4 — BE Working Memory Dependencies

| Field | Access | Purpose |
|-------|--------|---------|
| `orderRequest.OrderData.OMXTrackingId` | READ | transaction_id + audit UUID |
| `orderRequest.OrderData.OrderID` | READ | Event header OrderID |
| `orderRequest.OrderData.OrderType` | READ | ns:order_type + event header |
| `orderRequest.OrderData.EffectiveDate` | READ | offer_activity_date when CANCEL_TYPE=endbill |
| `orderRequest.OrderData.ExtendedInfo[CANCEL_TYPE]` | READ | Gates endbill branch |
| `orderRequest.ProcessConfigExtID` | READ | ns:order_type_name |
| `orderRequest.OrderPriority` | READ | JMSPriority |
| `subscriber.RefId` | READ | Correlation key / RefID |
| `subscriber.MSISDN` | READ | ns:msisdn (or old-MSISDN swap) |
| `subscriber.SubscriberId` | READ | ns:old_subscriber_id (SOURCE/TARGET mode) |
| `subscriber.RawSubscriberId` | READ | ns:old_subscriber_id (RAW_SUB mode) |
| `subscriber.SubscriberActivityInfo.ActivityReason` | READ | ns:activity_reason |
| `subscriber.ExtendedInfo[SHAREPLAN_MAIN_NUMBER]` | READ | isShareplanMainNumber |
| `subscriber.SubscriberOffers[FE_OR_CCBS=FE and ServiceType=80]` | READ | Priceplan offer name + date |
| `subscriber.SubscriberOffers[TR_CONTRACT_IND=Y and FE_OR_CCBS=FE]` | READ | Contract offer name |
| `subscriber.SubscriberOffers[OfferName=RMVX00000000001]/ParameterInfo` | READ | offer_expire_date |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-out counter |
| `orderCurrentActivity.Response` | READ/WRITE (response) | Response array |
| `orderCurrentActivity.Status` | WRITE | Set to SENT |

### §8.5 — Activity Parameters Read

| Parameter Key | Helper Function | Used As | Effect |
|--------------|----------------|---------|--------|
| `oldMsisdnFlag` | `GetActivityParamValueFromKey` (singular) | `$oldMsisdnFlag` | If "Y": use TARGET MSISDN, emit old_msisdn |
| `OFFER_NAME` | `GetActivityParameterValueFromKey` | `$paramOfferName` | "Priceplan" → ServiceType=80; else → TR_CONTRACT_IND=Y |
| `USE_ROWID_CRM` | `GetActivityParameterValueFromKey` | passed to MapSubscriberIdFromCRM | Controls subscriber_id field |
| `MAP_PP_EXPIRE` | `GetActivityParameterValueFromKey` | `$mapPPExpire` | "Y" → look up offer_expire_date |
| `MAP_OLD_SUB` | `GetActivityParameterValueFromKey` | `$mapOldSub` | SOURCE_SUB / TARGET_SUB / RAW_SUB |

---

## §9 — Detailed Payload Build

### §9.1 — XSLT Parameter Binding

| XSLT Param | Bound From | Role |
|-----------|-----------|------|
| `$orderRequest` | BE concept `orderRequest` | Root order data |
| `$refId` | `subscriber.RefId` | Correlation key |
| `$oldMsisdnFlag` | Activity param "oldMsisdnFlag" | Controls MSISDN swap |
| `$subscriber` | BE concept `subscriber` | Subscriber data |
| `$subIdCrm` | `MapSubscriberIdFromCRM(subscriber, useRowIdCrmParam)` | CRM subscriber ID |
| `$isShareplanMainNumber` | XPath boolean | true if NOT a Shareplan main number |
| `$mapOldSub` | Activity param "MAP_OLD_SUB" | old_subscriber_id source mode |
| `$msisdn` | `subscriber.MSISDN` | Used in old_subscriber_id lookup |
| `$paramOfferName` | Activity param "OFFER_NAME" | offer_name filter mode |
| `$mapPPExpire` | Activity param "MAP_PP_EXPIRE" | offer_expire_date gate |

### §9.4 — Payload Root Element

`payload / ns:CancelAftersaleRequest` — namespace: `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/CancelAftersale.xsd`

### §9.5 — Conditional Fields

| Field | Condition | Source |
|-------|-----------|--------|
| `ns:transaction_id` | if `$orderRequest/OrderData/OMXTrackingId` | `OMXTrackingId` |
| `ns:old_msisdn` | if `$oldMsisdnFlag = 'Y'` | `ResourceInfo[OLD_MSISDN]/ValuesArray` |
| `ns:subscriber_id` | if `$subIdCrm != ""` | `$subIdCrm` |
| `ns:old_subscriber_id` | xsl:choose on `$mapOldSub` | SOURCE_SUB / TARGET_SUB / RAW_SUB |
| `ns:offer_name` | xsl:choose on `$paramOfferName` | Priceplan vs TR_CONTRACT_IND=Y |
| `ns:offer_activity_date` | xsl:choose (3-way priority) | OfferOriginalEffectiveDate / endbill / today |
| `ns:order_type` | if `$orderRequest/OrderData/OrderType` | `OrderType` |
| `ns:order_type_name` | if `$orderRequest/ProcessConfigExtID` | `ProcessConfigExtID` |
| `ns:offer_expire_date` | if `$mapPPExpire="Y"` AND ParamName match | trailing-space risk |

### §9.6 — Multi-Branch Logic Detail

**ns:msisdn — Old-MSISDN swap (XPath if-then-else, always emitted):**

```xpath
if ($oldMsisdnFlag = 'Y') then
  $orderRequest/OrderData/Customer/ParentOU[ExtendedInfo[Name="SOURCE_OR_TARGET" and Value="TARGET"]]/Subscriber/MSISDN
else
  $subscriber/MSISDN
```

**ns:old_subscriber_id — Three-way xsl:choose on $mapOldSub:**

| $mapOldSub | Source XPath | Condition |
|-----------|-------------|-----------|
| `SOURCE_SUB` | `ParentOU/Subscriber[$msisdn=MSISDN and SOURCE]/SubscriberId` | Conditional |
| `TARGET_SUB` | `ParentOU/Subscriber[$msisdn=MSISDN and TARGET]/SubscriberId` | Conditional |
| `RAW_SUB` | `$subscriber/RawSubscriberId` | Conditional |
| other | nothing emitted | No xsl:otherwise |

**ns:offer_name — Two-way xsl:choose on $paramOfferName:**

| $paramOfferName | Offer Filter | Condition |
|----------------|-------------|-----------|
| `Priceplan` | `SubscriberOffers[FE_OR_CCBS=FE and ServiceType='80']/OfferName` | Conditional |
| otherwise | `SubscriberOffers[contains(SocProperties,'TR_CONTRACT_IND=Y') and FE_OR_CCBS=FE]/OfferName` | Conditional |

**ns:offer_activity_date — Three-way priority xsl:choose:**

| Priority | Condition | Value |
|----------|-----------|-------|
| 1 (highest) | `exists(SubscriberOffers[FE_OR_CCBS=FE and ServiceType=80 and OfferOriginalEffectiveDate/Value])` | `concat(tib:parse-date("yyyy-MM-dd", OfferOriginalEffectiveDate), ' 00:00:00')` |
| 2 | `exists(OrderData[ExtendedInfo[CANCEL_TYPE='endbill']])` | `concat(tib:parse-date("yyyy-MM-dd", EffectiveDate), ' 00:00:00')` |
| 3 (default) | otherwise | `concat(tib:format-date('yyyy-MM-dd', current-date()), ' 00:00:00')` |

> **Note:** Priority 1 checks `ServiceType=80` (Priceplan) regardless of `paramOfferName` setting — verify with business.

**ns:offer_expire_date — Double conditional (trailing-space risk):**

```xpath
if ($mapPPExpire = "Y")
  SubscriberOffers[OfferName="RMVX00000000001" and ExtendedInfo[FE_OR_CCBS=FE]]
    /ParameterInfo[ParamName="TR_ORIG_CONTRACT_EXPIRE_DATE "]   <- trailing space [MEDIUM]
    /ValuesArray
```

### §9.7 — Complete Generated XML Example

```xml
<createEvent>
  <event extId="OMX-TRK-20240801-002">
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20240801-001</JMSCorrelationID>
    <OrderID>ORD-9001</OrderID>
    <RefID>SUB-REF-001</RefID>
    <OrderType>POSTPAID_REMOVE_OFFER_SUB</OrderType>
    <payload>
      <ns:CancelAftersaleRequest
        xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/CancelAftersale.xsd">
        <ns:transaction_id>OMX-TRK-20240801-001</ns:transaction_id>
        <ns:subscribers>
          <ns:msisdn>0812345678</ns:msisdn>
          <ns:subscriber_id>CRM-SUB-9001</ns:subscriber_id>
          <ns:activity_reason>RM</ns:activity_reason>
          <ns:account_id></ns:account_id>   <!-- always empty [MEDIUM] -->
          <ns:isShareplanMainNumber>true</ns:isShareplanMainNumber>
          <ns:old_subscriber_id>12345</ns:old_subscriber_id>
        </ns:subscribers>
        <ns:offer_name>OFFER-CONTRACT-001</ns:offer_name>
        <ns:offer_activity_date>2024-01-15 00:00:00</ns:offer_activity_date>
        <ns:order_type>POSTPAID_REMOVE_OFFER_SUB</ns:order_type>
        <ns:order_type_name>POSTPAID_REMOVE_OFFER_SUB</ns:order_type_name>
      </ns:CancelAftersaleRequest>
    </payload>
  </event>
</createEvent>
```

### §9.8 — XSLT Stylesheet Source

**Variant ① — ParentOU & ChildOU (identical XSLT)**

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:ns="http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/CancelAftersale.xsd"
  xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="refId"/>
  <xsl:param name="oldMsisdnFlag"/>
  <xsl:param name="subscriber"/>
  <xsl:param name="subIdCrm"/>
  <xsl:param name="isShareplanMainNumber"/>
  <xsl:param name="mapOldSub"/>
  <xsl:param name="msisdn"/>
  <xsl:param name="paramOfferName"/>
  <xsl:param name="mapPPExpire"/>
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <RefID><xsl:value-of select="$refId"/></RefID>
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        <payload>
          <ns:CancelAftersaleRequest>
            <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
              <ns:transaction_id><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></ns:transaction_id>
            </xsl:if>
            <ns:subscribers>
              <!-- ns:msisdn: if-then-else for old-MSISDN swap -->
              <ns:msisdn>
                <xsl:value-of select="if ($oldMsisdnFlag = 'Y') then
                  $orderRequest/OrderData/Customer/ParentOU[ExtendedInfo[Name=&quot;SOURCE_OR_TARGET&quot; and Value=&quot;TARGET&quot;]]/Subscriber/MSISDN
                  else $subscriber/MSISDN"/>
              </ns:msisdn>
              <xsl:if test="$oldMsisdnFlag = 'Y'">
                <ns:old_msisdn>
                  <xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU/Subscriber/ResourceInfo[ResourceName=&quot;OLD_MSISDN&quot;]/ValuesArray"/>
                </ns:old_msisdn>
              </xsl:if>
              <xsl:if test="$subIdCrm!=&quot;&quot;">
                <ns:subscriber_id><xsl:value-of select="$subIdCrm"/></ns:subscriber_id>
              </xsl:if>
              <ns:activity_reason><xsl:value-of select="$subscriber/SubscriberActivityInfo/ActivityReason"/></ns:activity_reason>
              <ns:account_id><xsl:value-of select="''"/></ns:account_id>  <!-- always empty [MEDIUM] -->
              <ns:isShareplanMainNumber><xsl:value-of select="$isShareplanMainNumber"/></ns:isShareplanMainNumber>
              <!-- ns:old_subscriber_id: 3-way choose -->
              <xsl:choose>
                <xsl:when test="$mapOldSub=&quot;SOURCE_SUB&quot;">
                  <xsl:if test="$orderRequest/.../Subscriber[$msisdn=MSISDN and SOURCE]/SubscriberId">
                    <ns:old_subscriber_id>...</ns:old_subscriber_id>
                  </xsl:if>
                </xsl:when>
                <xsl:when test="$mapOldSub=&quot;TARGET_SUB&quot;">
                  <xsl:if test="$orderRequest/.../Subscriber[$msisdn=MSISDN and TARGET]/SubscriberId">
                    <ns:old_subscriber_id>...</ns:old_subscriber_id>
                  </xsl:if>
                </xsl:when>
                <xsl:when test="$mapOldSub=&quot;RAW_SUB&quot;">
                  <xsl:if test="$subscriber/RawSubscriberId">
                    <ns:old_subscriber_id><xsl:value-of select="$subscriber/RawSubscriberId"/></ns:old_subscriber_id>
                  </xsl:if>
                </xsl:when>
                <!-- no xsl:otherwise -->
              </xsl:choose>
            </ns:subscribers>
            <!-- ns:offer_name: Priceplan vs TR_CONTRACT_IND=Y -->
            <xsl:choose>
              <xsl:when test="$paramOfferName=&quot;Priceplan&quot;">
                <xsl:if test="$subscriber/SubscriberOffers[ExtendedInfo[Name='FE_OR_CCBS' and Value='FE'] and ServiceType='80']/OfferName">
                  <ns:offer_name><xsl:value-of select="..."/></ns:offer_name>
                </xsl:if>
              </xsl:when>
              <xsl:otherwise>
                <xsl:if test="$subscriber/SubscriberOffers[contains(SocProperties,'TR_CONTRACT_IND=Y') and ExtendedInfo[FE_OR_CCBS=FE]]/OfferName">
                  <ns:offer_name><xsl:value-of select="..."/></ns:offer_name>
                </xsl:if>
              </xsl:otherwise>
            </xsl:choose>
            <!-- ns:offer_activity_date: 3-way priority -->
            <xsl:choose>
              <xsl:when test="exists($subscriber/SubscriberOffers[FE_OR_CCBS=FE and ServiceType=80 and ExtendedInfo[Name=&quot;OfferOriginalEffectiveDate&quot;]/Value])">
                <ns:offer_activity_date><xsl:value-of select="concat(tib:parse-date(&quot;yyyy-MM-dd&quot;, ...), ' 00:00:00')"/></ns:offer_activity_date>
              </xsl:when>
              <xsl:when test="exists($orderRequest/OrderData[ExtendedInfo[Name='CANCEL_TYPE' and Value='endbill']])">
                <ns:offer_activity_date><xsl:value-of select="concat(tib:parse-date(&quot;yyyy-MM-dd&quot;, $orderRequest/OrderData/EffectiveDate), ' 00:00:00')"/></ns:offer_activity_date>
              </xsl:when>
              <xsl:otherwise>
                <ns:offer_activity_date><xsl:value-of select="concat(tib:format-date('yyyy-MM-dd', current-date()), ' 00:00:00')"/></ns:offer_activity_date>
              </xsl:otherwise>
            </xsl:choose>
            <xsl:if test="$orderRequest/OrderData/OrderType">
              <ns:order_type><xsl:value-of select="$orderRequest/OrderData/OrderType"/></ns:order_type>
            </xsl:if>
            <xsl:if test="$orderRequest/ProcessConfigExtID">
              <ns:order_type_name><xsl:value-of select="$orderRequest/ProcessConfigExtID"/></ns:order_type_name>
            </xsl:if>
            <xsl:if test="$mapPPExpire=&quot;Y&quot;">
              <!-- ParamName has trailing space — potential silent failure [MEDIUM] -->
              <xsl:if test="$subscriber/SubscriberOffers[OfferName=&quot;RMVX00000000001&quot; and ExtendedInfo[FE_OR_CCBS=FE]]/ParameterInfo[ParamName=&quot;TR_ORIG_CONTRACT_EXPIRE_DATE &quot;]/ValuesArray">
                <ns:offer_expire_date>...</ns:offer_expire_date>
              </xsl:if>
            </xsl:if>
          </ns:CancelAftersaleRequest>
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
└── event @extId ← OMXUtils:generateTrackingID()                              [Always]
    ├── JMSPriority       ← $orderRequest/OrderPriority                       [Always]
    ├── JMSCorrelationID  ← $orderRequest/OrderData/OMXTrackingId             [Always]
    ├── OrderID           ← $orderRequest/OrderData/OrderID                   [Always]
    ├── RefID             ← $refId (= subscriber.RefId)                       [Always]
    ├── OrderType         ← $orderRequest/OrderData/OrderType                 [Always]
    └── payload
        └── ns:CancelAftersaleRequest
            ├── ns:transaction_id    ← OMXTrackingId                         [Conditional: if OMXTrackingId]
            ├── ns:subscribers
            │   ├── ns:msisdn        ← if(oldMsisdnFlag=Y) TARGET else MSISDN [Always]
            │   ├── ns:old_msisdn    ← ResourceInfo[OLD_MSISDN]/ValuesArray   [Conditional: if oldMsisdnFlag=Y]
            │   ├── ns:subscriber_id ← $subIdCrm                              [Conditional: if subIdCrm!=""]
            │   ├── ns:activity_reason ← SubscriberActivityInfo/ActivityReason [Always]
            │   ├── ns:account_id    ← '' (empty)                             [Always — MEDIUM: never wired]
            │   ├── ns:isShareplanMainNumber ← $isShareplanMainNumber         [Always]
            │   └── ns:old_subscriber_id [xsl:choose on $mapOldSub]
            │       ├── SOURCE_SUB → ParentOU/Subscriber[SOURCE]/SubscriberId [Conditional]
            │       ├── TARGET_SUB → ParentOU/Subscriber[TARGET]/SubscriberId [Conditional]
            │       ├── RAW_SUB    → $subscriber/RawSubscriberId              [Conditional]
            │       └── (no otherwise → nothing emitted)
            ├── ns:offer_name [xsl:choose on $paramOfferName]
            │   ├── Priceplan  → SubscriberOffers[FE_OR_CCBS=FE, ServiceType=80]/OfferName [Conditional]
            │   └── otherwise  → SubscriberOffers[TR_CONTRACT_IND=Y, FE_OR_CCBS=FE]/OfferName [Conditional]
            ├── ns:offer_activity_date [xsl:choose, 3-way priority]
            │   ├── P1: Priceplan offer has OfferOriginalEffectiveDate → parse-date + ' 00:00:00'
            │   ├── P2: CANCEL_TYPE=endbill                           → parse-date(EffectiveDate) + ' 00:00:00'
            │   └── P3: otherwise                                     → format-date(current-date()) + ' 00:00:00'
            ├── ns:order_type      ← $orderRequest/OrderData/OrderType        [Conditional]
            ├── ns:order_type_name ← $orderRequest/ProcessConfigExtID         [Conditional]
            └── ns:offer_expire_date ← ParameterInfo[ParamName="TR_ORIG_CONTRACT_EXPIRE_DATE "]/ValuesArray
                                       [Conditional: MAP_PP_EXPIRE=Y — MEDIUM: trailing space in ParamName]
```

---

## §11 — Audit Logging

| Phase | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE |
|-------|-----------|----------------|-------------|
| [REQUEST] | `concat(nanoTime(), "_REQ")` | `"MCS_CANCEL_AFTER_SALE"` | `"Request Sent for MCS_CANCEL_AFTER_SALE"` |
| [RESPONSE] | `concat(nanoTime(), "_RES")` | `"MCS_CANCEL_AFTER_SALE"` | `concat("Response received for RefId ", $eventResponse/RefID)` |

---

## §12 — Activity Status Management

| Scenario | Status Code | Function | Meaning |
|----------|-------------|---------|---------|
| Dispatch sent | `"1"` | `GetActivityStatusString("1", false)` | SENT |
| All skipped | `"4"` | `SkipActivity(…, "4")` | SKIPPED |

---

## §13 — Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §14 — Helper Functions Reference

| Function | Return | Purpose |
|---------|--------|---------|
| `GetXMLForSubscriber(orderRequest, refId)` | String | POU PreExecCheck serialisation |
| `GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)` | String | COU PreExecCheck serialisation |
| `GetActivityParamValueFromKey(activity, "oldMsisdnFlag")` | String | Read Param (singular element) by key |
| `GetActivityParameterValueFromKey(activity, key)` | String | Read Parameter (plural element) by key |
| `MapSubscriberIdFromCRM(subscriber, useRowIdCrmParam)` | String | CRM subscriber ID mapping |
| `GetActivityStatusString("1", false)` | String | Status code for SENT |
| `SkipActivity(orderRequest, activity, "4")` | void | Skip and advance flow |
| `SendDataToDB(orderRequest)` | void | Persist order state |
| `HandleActivityException(orderRequest, activity, ae, "")` | void | Error handler |

---

## §15 — Function Dependency Tree

```text
Request_MCS_CANCEL_AFTER_SALE (rule)
├── RuleFunctions.Helpers.GetXMLForSubscriber               [POU PreExecCheck]
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU      [COU PreExecCheck]
├── XPath.execute                                            [PreExecCheck evaluation]
├── XPath.evalAsBoolean                                      [isShareplanMainNumber]
├── RuleFunctions.Helpers.GetActivityParamValueFromKey      [oldMsisdnFlag — Param/singular]
├── RuleFunctions.Helpers.GetActivityParameterValueFromKey  [OFFER_NAME, USE_ROWID_CRM, MAP_PP_EXPIRE, MAP_OLD_SUB]
├── RuleFunctions.Helpers.MapSubscriberIdFromCRM            [subIdCrm]
├── OMXUtils:generateTrackingID()                           [event @extId — inside XSLT]
├── Event.Ext.sendEventImmediate                            [x2: reqEvent + logger per subscriber]
├── RuleFunctions.Helpers.GetActivityStatusString           [status "1"]
├── RuleFunctions.Helpers.SendDataToDB                      [DB persistence]
├── RuleFunctions.Helpers.SkipActivity                      [skip path]
└── RuleFunctions.Helpers.HandleActivityException           [error handling]

Response_MCS_CANCEL_AFTER_SALE (rulefunction)
├── OMXUtils.generateTrackingID()                           [ResponseBase extId]
├── Instance.createInstance (ResponseBase XSLT)             [construct response record]
├── XPath.evalAsInt                                         [fan-in count]
├── Event.Ext.sendEventImmediate                            [response audit logger]
└── [return "true" / "false"]                               [fan-in completion signal]
```

---

## §16 — Concept Definitions Referenced

| Concept | Key Fields Used | Role |
|---------|----------------|------|
| `Concepts.OrderRequest.OrderRequest` | OrderData, OrderPriority, ProcessConfigExtID, IsOrderResubmitted | Root order |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, RequestCount, Response[], PreExecCheck, Params, Parameters | Activity state + config |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, SubscriberId, RawSubscriberId, SubscriberActivityInfo, ExtendedInfo[], SubscriberOffers[] | Subscriber data |
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId | Normalised response |

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement | Evidence |
|----|------------|---------|
| R1 | Call MCS CancelAftersale API per subscriber with MSISDN, transaction_id, subscriber metadata | XSLT: `ns:CancelAftersaleRequest` |
| R2 | Support old-MSISDN swap (number-change): when `oldMsisdnFlag=Y`, use TARGET MSISDN and emit old_msisdn | XSLT: if-then-else on `$oldMsisdnFlag` |
| R3 | CRM subscriber ID mapping via USE_ROWID_CRM flag | Rule: `MapSubscriberIdFromCRM` |
| R4 | Shareplan detection: compute `isShareplanMainNumber` per subscriber | Rule: XPath on `ExtendedInfo[SHAREPLAN_MAIN_NUMBER]` |
| R5 | Two-mode offer name selection: Priceplan (ServiceType=80) or contract (TR_CONTRACT_IND=Y) | XSLT: xsl:choose on `$paramOfferName` |
| R6 | Three-way offer_activity_date priority: OfferOriginalEffectiveDate / endbill / today | XSLT: three-way xsl:choose |
| R7 | Three-way old_subscriber_id mapping: SOURCE_SUB / TARGET_SUB / RAW_SUB | XSLT: xsl:choose on `$mapOldSub` |
| R8 | Conditional offer_expire_date from OfferName=RMVX00000000001 when MAP_PP_EXPIRE=Y | XSLT: double-conditional |
| R9 | Support both POU and COU subscriber structures | Rule: dual loops |
| R10 | Standard resubmit-skip and fan-in patterns | Rule + Response rulefunction |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Trailing space in `ParamName="TR_ORIG_CONTRACT_EXPIRE_DATE "` — silently prevents `offer_expire_date` from being sent when `MAP_PP_EXPIRE=Y` | [MEDIUM] | Verify against CCBS data; use `normalize-space()` in migration |
| `ns:account_id` always empty — MCS receives blank field; may cause validation issues | [MEDIUM] | Confirm with MCS team; wire to real data or remove from contract |
| `GetActivityParamValueFromKey` (singular) vs `GetActivityParameterValueFromKey` (plural) — reads from different config elements; inconsistency may cause `oldMsisdnFlag` to be empty | [MEDIUM] | Standardise to single parameter-reading mechanism in modernised service |
| offer_activity_date Priority 1 checks Priceplan offer (ServiceType=80) regardless of `paramOfferName` mode | [LOW] | Confirm with business; align date priority with offer mode |
| No `xsl:otherwise` in `old_subscriber_id` choose — unrecognised values silently emit nothing | [LOW] | Add explicit validation/default in modernised service |

---

## §18 — Full Source Code

```java
/**
 * @description
 * @author Chayatorn Pan.
 */
rule Rules.OMConsumers.OMXFM.Request.Request_MCS_CANCEL_AFTER_SALE {
    attribute { priority = 5; forwardChain = true; }
    declare {
        Concepts.OrderRequest.OrderRequest orderRequest;
        Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
    }
    when {
        orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
        orderCurrentActivity.ActivityID == "MCS_CANCEL_AFTER_SALE";
        orderRequest.ProcessFlow.NextActivityID == "MCS_CANCEL_AFTER_SALE";
        orderCurrentActivity.Status == "WAITING";
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
            int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
            String pouRefId = "";
            boolean isSkipped = true;
            for (int i=0; i<iPOULen; i++) {  // ParentOU loop
                pouRefId = orderRequest.OrderData.Customer.ParentOU[i].RefId;
                int iSubscriberLen = orderRequest.OrderData.Customer.ParentOU[i].Subscriber@length;
                for (int j=0; j<iSubscriberLen; j++) {
                    Concepts.OrderRequest.OrderElements.Subscriber subscriber = ...;
                    String refId = subscriber.RefId;
                    boolean reqSuccess = false;
                    for (int iResp=0; iResp<orderCurrentActivity.Response@length; iResp++)
                        if (String.equals(Response[iResp].ReferenceId, refId) && Response[iResp].CompletionStatus==2)
                            reqSuccess = true;
                    if (!reqSuccess) {
                        String chkRes = "true";
                        if (String.length(nextAct.PreExecCheck) > 0) {
                            String sXML = RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId);
                            chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
                        }
                        if (String.equals(chkRes, "true")) {
                            // Note: singular vs plural helper — different parameter sources
                            String oldMsisdnFlag    = RuleFunctions.Helpers.GetActivityParamValueFromKey(orderCurrentActivity, "oldMsisdnFlag");
                            boolean isShareplanMainNumber = XPath.evalAsBoolean("not(exists(...ExtendedInfo[SHAREPLAN_MAIN_NUMBER]))");
                            String paramOfferName   = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "OFFER_NAME");
                            String useRowIdCrmParam = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "USE_ROWID_CRM");
                            String subIdCrm         = RuleFunctions.Helpers.MapSubscriberIdFromCRM(subscriber, useRowIdCrmParam);
                            String mapPPExpire      = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "MAP_PP_EXPIRE");
                            String mapOldSub        = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "MAP_OLD_SUB");
                            String msisdn           = subscriber.MSISDN;

                            /* Build ns:CancelAftersaleRequest event — see §9.8 for full XSLT:
                               10 params: oldMsisdnFlag swap, subIdCrm, isShareplanMainNumber,
                               mapOldSub (3-way old_subscriber_id), paramOfferName (2-way offer_name),
                               3-way offer_activity_date, mapPPExpire (offer_expire_date trailing-space risk),
                               ns:account_id always empty [MEDIUM] */
                            Events.OMConsumers.OMXFM.Request.MCS_CANCEL_AFTER_SALE reqEvent =
                                Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/MCS_CANCEL_AFTER_SALE}}...");
                            Event.Ext.sendEventImmediate(reqEvent);
                            long pid = System.nanoTime();
                            /* Audit logger: OPERATION_NAME="MCS_CANCEL_AFTER_SALE", PROCESS_ID=pid+"_REQ" */
                            Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{/Events/OMConsumers/OMXESB/Logger}}..."));
                            if (!isActResub) orderCurrentActivity.RequestCount++;
                            isSkipped = false;
                        }
                    }
                }
                // ChildOU loop — identical; isShareplanMainNumber XPath uses i,p,q indices
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

**Response_MCS_CANCEL_AFTER_SALE** handles the MCS CancelAftersale response. It creates a `ResponseBase` record, appends it, emits a response audit log, and evaluates fan-in completion. No subscriber state enrichment — simpler than MCS_GET_PACKCODE response handler.

### §19.2 — Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Root order |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.MCS_CANCEL_AFTER_SALE` | Inbound response |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in tracking |

### §19.3 — ResponseBase Concept Construction

> **Correct pattern:** `String extId = OMXUtils.generateTrackingID()` passed as `$extId` XSLT param — no dead-variable bug.

```text
createObject
└── object @extId ← $extId (= OMXUtils.generateTrackingID())   [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode         [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg          [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus     [Conditional]
    └── ReferenceId       ← $eventResponse/RefID                [Conditional]
```

### §19.4 — Response Completion Logic

```xpath
count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])
```

```java
if (currActivity.RequestCount == successResponseCount) { return "true"; }
else { return "false"; }
```

Standard correct fan-in pattern. No subscriber enrichment.

### §19.5 — Response Audit Logging

| Field | Value |
|-------|-------|
| `PROCESS_ID` | `concat(nanoTime(), "_RES")` |
| `OPERATION_NAME` | `"MCS_CANCEL_AFTER_SALE"` |
| `AUDIT_TRACE` | `concat("Response received for RefId ", $eventResponse/RefID)` |
| `payload` | Copy of `$eventResponse` — gated on `WritePayload="true"` |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
