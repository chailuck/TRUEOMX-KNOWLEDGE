# Request_SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE

> SMS Gateway — Send SMS notification for expiry date update to COU/POU Subscribers

**Priority:** 5 | **forwardChain:** true | **Target:** SMSGATEWAY | **Scopes:** COU Subscriber + POU Subscriber | **Generated:** 2026-08-20

---

## §1 Overview & Purpose

This OMXFM rule dispatches an SMS notification via the SMS Gateway for each subscriber (COU and POU) whose expiry date has been updated. Triggered when `ActivityID == "SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE"` and activity is in WAITING status.

**Key behaviours:**
- Only **Subscriber** scopes — no Agreement scope
- Scans SubscriberOffers to extract: price plan (ServiceType=80 & CCBS), contract (TR_CONTRACT_IND=Y & FE/BRMS), RMVX contract dates
- Date formatting with Thai month-name conversion when Language=TH
- MSISDN normalization: strips leading "0" and prefixes with "66" for international format
- BILL_DESCRIPTION ExtendedInfo preferred over raw socDesc for param #2
- 12-field ParamList (numeric 1–10 + named "ppEffDate" + named "offer")
- Reuses `Events.OMConsumers.OMXFM.Request.SMSGATEWAY_SEND_SMS` event type (shared with SMSGATEWAY_SEND_SMS activity)
- AllowWriteLog gate on audit logging

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule path | `Rules.OMConsumers.OMXFM.Request.Request_SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE` |
| Priority | 5 |
| forwardChain | true |
| Activity ID | SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE |
| Target System | SMSGATEWAY (SMS Gateway service) |
| Event Type | `Events.OMConsumers.OMXFM.Request.SMSGATEWAY_SEND_SMS` (shared) |
| Response RF | `Response_SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE.rulefunction` |
| Response Concept | `Concepts.FM.Response.SMSGATEWAY_SendSMSRes` |
| Scopes | COU Subscriber, POU Subscriber (no Agreement scope) |
| Author | (not set) |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order request; source of all subscriber data, offers, accounts |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity config; provides PreExecCheck, Parameters, Response array, RequestCount |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity is the current one to execute |
| 2 | `orderCurrentActivity.ActivityID == "SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE"` | Routes to this specific FM |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE"` | Double-check on activity ID in process flow |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity must be in WAITING state |

---

## §5 Execution Flow Diagram

```
1. Determine resubmit flag: isActResub = RequestCount>0 && IsOrderResubmitted
2. Load PreExecCheck XPath from nextAct.PreExecCheck; initialize isSkipped=true
3. COU Subscriber loop: ParentOU[i] → ChildOU[k] → Subscriber[j]
   a. Resubmit guard: skip if Response[].ReferenceId==refId && CompletionStatus==2
   b. PreExecCheck: GetXMLForSubscriberInChildOU → XPath.execute
   c. If pass: scan SubscriberOffers → extract pp, socDesc, contract, contractDesc, ppEffDT, ppExpDT
   d. ppExpDT = DateTime.addDay(ppExpDT, -1); format dates; address lookup; smsInd param
   e. Build SMSGATEWAY_SEND_SMS event via XSLT → sendEventImmediate → RequestCount++ → isSkipped=false
   f. AllowWriteLog gate → audit log
4. POU Subscriber loop: ParentOU[i] → Subscriber[j] (identical logic, uses GetXMLForSubscriber)
5. if(!isSkipped) → Status="1" (PROCESSING), SendDataToDB; else → SkipActivity("4")
6. catch(Exception) → HandleActivityException
```

---

## §6 Rule Action (THEN) — Step-by-Step Logic

### Offer Scanning Logic (per subscriber)

| Variable | Source Offer Condition | Value Extracted |
|----------|------------------------|-----------------|
| `pp` (price plan name) | ServiceType=="80" AND feOrCCBs=="CCBS" | `currOffer.OfferName` |
| `socDesc` | same offer; fallback via `GetSocDescriptionFromSocProperties` | Description for SMS param #2 |
| `ppEffDT` | OfferName=="RMVX00000000001" AND GET_EFF_EXP_FROM_RMVX=="Y" AND feOrCCBs=="CCBS" | `GetDateFromOfferParamName(currOffer, "TR_ACTUAL_CONTRACT_START_DATE")` |
| `ppExpDT` | OfferName=="RMVX00000000001" AND GET_EFF_EXP_FROM_RMVX=="Y" AND feOrCCBs=="FE" | `GetDateFromOfferParamName(currOffer, "TR_ORIG_CONTRACT_EXPIRE_DATE")` |
| `contract` | SocProperties contains "TR_CONTRACT_IND=Y" AND (feOrCCBs blank OR "FE" OR "BRMS") | `currOffer.OfferName` |
| `contractDesc` | same; fallback via GetSocDescriptionFromSocProperties | Description for SMS param #7 |

### Date Processing

> **ppExpDT adjustment:** `ppExpDT = DateTime.addDay(ppExpDT, -1)` — 1 day subtracted before formatting.
> **Null guard:** `if (ppExpDT != null)` — dead code; ppExpDT always initialized to `DateTime.now()`.
> **Format:** `"dd-MMM-yyyy"`; if Language=="TH" → `ConvertMntoThaiMn(date, "-", dateFormat)`

### Address Resolution

Loop `Customer.Account[]`; match `Account[].RefId == subscriber.AccountRefId` → `GetAddressString(BillingArrangementAddress, language)`

### XSLT Variants

> Both COU-Subscriber and POU-Subscriber use **identical XSLT payloads**. The two variants differ only in what $i, $j, $refId are bound to at the BE rule level.

---

## §7 Data Extraction & Encoding

| Pattern | Field | Details |
|---------|-------|---------|
| FE_OR_CCBS ExtendedInfo | feOrCCBs | XPath.evalAsString on `$currOffer/ExtendedInfo[Name='FE_OR_CCBS']/Value` |
| Activity parameter key | GET_EFF_EXP_FROM_RMVX | Controls whether RMVX offer dates are extracted (Y/N) |
| Activity parameter key | SMS_IND | SMS indicator passed as param "offer" to gateway |
| SocProperties substring | TR_CONTRACT_IND | `String.contains(SocProperties, "TR_CONTRACT_IND=Y")` |
| Date helper | TR_ACTUAL_CONTRACT_START_DATE | From RMVX offer SocProperties |
| Date helper | TR_ORIG_CONTRACT_EXPIRE_DATE | From RMVX offer SocProperties |

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

Used in POSTPAID_UPDATE_PARAMETER at step 37. AllowWriteLog gates audit logging based on OrderType. No order-type filtering in main dispatch logic — all order types with this activity will send SMS.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Destination / Channel | Purpose |
|-----------|------------|-----------------------|---------|
| [OUTBOUND] | `SMSGATEWAY_SEND_SMS` | JMS destination from event definition | Send SMS request |
| [OUTBOUND] | `OMXESB/Logger` | Audit log topic | Request/response audit trail (AllowWriteLog-gated) |

### §8.3 Backend API Details

| System | Operation | Schema | Protocol | Correlation |
|--------|-----------|--------|----------|-------------|
| SMSGATEWAY | SendSMS | `ns:SMSRequest` (SMSService/Resources/Schema.xsd) | JMS (async) | JMSCorrelationID=OMXTrackingId; RefID=subscriber.RefId |

### §8.4 BE Working Memory Dependencies

| Field Path | Access | Purpose |
|------------|--------|---------|
| `OrderData.Customer.ParentOU[i].ChildOU[k].Subscriber[j].*` | READ | COU subscriber data |
| `OrderData.Customer.ParentOU[i].Subscriber[j].*` | READ | POU subscriber data |
| `Subscriber.SubscriberGeneralInfo.Language` | READ | Language for date/SMS formatting |
| `Subscriber.SubscriberOffers[*]` | READ | Price plan, RMVX, contract offer scanning |
| `SubscriberOffers.ExtendedInfo[Name="FE_OR_CCBS"].Value` | READ | Offer classification |
| `SubscriberOffers.ExtendedInfo[Name="BILL_DESCRIPTION"].Value` | READ | Bill description for param #2 |
| `Subscriber.AccountRefId` | READ | Match billing address from Account array |
| `Customer.Account[*].BillingArrangementAddress` | READ | Address for param #4 |
| `OrderData.Customer.CustomerTypeInfo.Type` | READ | Customer type for name logic |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-out counter |
| `orderCurrentActivity.Status` | WRITE | Set to "1" (PROCESSING) after dispatch |
| `Subscriber.ResponseCode / ResponseMsg` | WRITE (response RF) | Written from SMS gateway response |

### §8.5 ExtendedInfo Fields Required

| Name | Required/Optional | Where Used |
|------|-------------------|------------|
| FE_OR_CCBS | Optional | Offer scanning: controls pp vs contract classification |
| BILL_DESCRIPTION | Optional | SMS param #2 preferred over raw socDesc |

### §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `$globalVariables/OMX_OM/WritePayload` | Controls payload inclusion in audit log |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| XSLT Param | Bound From | Purpose |
|------------|------------|---------|
| `$i` | POU loop index | 1-based iParentOU in XSLT (number($i)+1) |
| `$j` | Subscriber loop index | 1-based iSubs in XSLT (number($j)+1) |
| `$orderRequest` | orderRequest concept | Full order data |
| `$refId` | subscriber.RefId | Correlation identifier |
| `$pp` | pp (ServiceType=80 CCBS offer name) | Price plan for ns:PricePlan |
| `$contract` | contract (TR_CONTRACT_IND=Y offer name) | Contract for ns:Proposition + param #6 |
| `$socDesc` | socDesc | Offer description fallback for param #2 |
| `$address` | address (billing arrangement) | Address for param #4 |
| `$contractDesc` | contractDesc | Contract description for param #7 |
| `$currentDate` | currentDate (formatted, possibly TH) | Current date for param #9 |
| `$ppExpDate` | ppExpDate (RMVX expiry - 1 day) | Expiry date for param #10 |
| `$ppEffDate` | ppEffDate (RMVX effective date) | Effective date for param "ppEffDate" |
| `$smsInd` | smsInd (SMS_IND activity parameter) | SMS indicator for param "offer" |

### §9.2 Event Container Construction

Event type: `Events.OMConsumers.OMXFM.Request.SMSGATEWAY_SEND_SMS`
Sent via `Event.Ext.sendEventImmediate(reqEvent)` — parallel fan-out (one per subscriber).

### §9.3 JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| JMSPriority | OrderPriority | Conditional: if OrderPriority exists |
| JMSCorrelationID | OrderData/OMXTrackingId | Conditional |
| OrderID | OrderData/OrderID | Conditional |
| RefID | $refId (subscriber.RefId) | Conditional |
| OrderType | OrderData/OrderType | Conditional |

### §9.4 Payload Root Element

`<ns:SMSRequest>` — namespace: `http://www.tibco.com/schemas/SMSService/Resources/Schema.xsd`

### §9.5 Top-Level SMS Fields

| Element | Source / Logic | Condition |
|---------|----------------|-----------|
| `ns:MSISDN` | if starts-with "0": concat("66", substring-after(MSISDN,"0")); else: raw MSISDN | Always (choose) |
| `ns:CustomerType` | CustomerTypeInfo/Type | Always |
| `ns:Language` | SubscriberGeneralInfo/Language; default "TH" | Always (choose) |
| `ns:OrderType` | OrderData/OrderType | Always |
| `ns:PricePlan` | $pp | Always |
| `ns:CompanyCode` | Subscriber/SubscriberType | Always |
| `ns:ProductType` | "" (static empty) | Always |
| `ns:Proposition` | $contract | Always |
| `ns:MessageType` | "" (static empty) | Always |
| `ns:Channel` | OrderData/Channel | Conditional: if Channel exists |

### §9.6 ParamList — 12 Parameters

| Param Name | Value Source | Notes |
|------------|-------------|-------|
| "1" | if CustomerTypeInfo/Type==73 → FirstName+" "+LastName; else OrgName | Subscriber vs corporate |
| "2" | BILL_DESCRIPTION ExtendedInfo on ServiceType=80 offer; else $socDesc | BILL_DESCRIPTION from INTX_GET_OFFER_DETAIL |
| "3" | Customer/BillCycleNo | Billing cycle |
| "4" | $address | Billing arrangement address |
| "5" | raw MSISDN (no "66" conversion) | Note: differs from ns:MSISDN |
| "6" | $contract | Contract offer name |
| "7" | $contractDesc | Contract description |
| "8" | CustomerGeneralInfo/Identification | Customer ID / ID card |
| "9" | $currentDate | Current date (formatted) |
| "10" | $ppExpDate | RMVX expiry date - 1 day |
| "ppEffDate" | $ppEffDate | Named param; RMVX effective date |
| "offer" | $smsInd | Named param; SMS_IND activity param |

> **MSISDN dual treatment:** `ns:MSISDN` uses international format (66xxx), param #5 keeps raw MSISDN (0xxx). SMS gateway may use both differently.

### §9.7 Complete Generated XML Example

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>TRK-20250101-001</JMSCorrelationID>
    <OrderID>ORD-12345</OrderID>
    <RefID>SUB-REF-001</RefID>
    <OrderType>POSTPAID_UPDATE_PARAMETER</OrderType>
    <payload>
      <ns:SMSRequest xmlns:ns="http://www.tibco.com/schemas/SMSService/Resources/Schema.xsd">
        <ns:MSISDN>66812345678</ns:MSISDN>
        <ns:CustomerType>73</ns:CustomerType>
        <ns:Language>TH</ns:Language>
        <ns:OrderType>POSTPAID_UPDATE_PARAMETER</ns:OrderType>
        <ns:PricePlan>TRUEMOVE_H_PLAN_X</ns:PricePlan>
        <ns:CompanyCode>TH</ns:CompanyCode>
        <ns:ProductType/>
        <ns:Proposition>CONTRACT_24M</ns:Proposition>
        <ns:MessageType/>
        <ns:ParamList>
          <ns:Param><ns:name>1</ns:name><ns:value>สมชาย ใจดี</ns:value></ns:Param>
          <ns:Param><ns:name>2</ns:name><ns:value>แพ็กเกจ True Move H ...</ns:value></ns:Param>
          <ns:Param><ns:name>3</ns:name><ns:value>5</ns:value></ns:Param>
          <ns:Param><ns:name>4</ns:name><ns:value>123 ถนนรัชดา กรุงเทพ</ns:value></ns:Param>
          <ns:Param><ns:name>5</ns:name><ns:value>0812345678</ns:value></ns:Param>
          <ns:Param><ns:name>6</ns:name><ns:value>CONTRACT_24M</ns:value></ns:Param>
          <ns:Param><ns:name>7</ns:name><ns:value>สัญญา 24 เดือน</ns:value></ns:Param>
          <ns:Param><ns:name>8</ns:name><ns:value>1234567890123</ns:value></ns:Param>
          <ns:Param><ns:name>9</ns:name><ns:value>20-ส.ค.-2568</ns:value></ns:Param>
          <ns:Param><ns:name>10</ns:name><ns:value>31-ธ.ค.-2569</ns:value></ns:Param>
          <ns:Param><ns:name>ppEffDate</ns:name><ns:value>01-ม.ค.-2568</ns:value></ns:Param>
          <ns:Param><ns:name>offer</ns:name><ns:value>Y</ns:value></ns:Param>
        </ns:ParamList>
        <ns:Channel>SELFCARE</ns:Channel>
      </ns:SMSRequest>
    </payload>
  </event>
</createEvent>
```

### §9.8 XSLT Stylesheet Source

> Both COU and POU subscriber variants use **identical XSLT**. Only the BE rule variables bound to $i, $j, $refId differ. Full source shown once.

```xml
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ns="http://www.tibco.com/schemas/SMSService/Resources/Schema.xsd"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:tib="http://www.tibco.com/bw/xslt/custom-functions"
    version="1.0" exclude-result-prefixes="xsl ns xsd tib">
  <xsl:output method="xml"/>
  <!-- Parameters bound from BE rule variables -->
  <xsl:param name="i"/>           <!-- POU loop index (0-based) -->
  <xsl:param name="j"/>           <!-- Subscriber loop index (0-based) -->
  <xsl:param name="orderRequest"/>
  <xsl:param name="refId"/>
  <xsl:param name="iParentOU"/>   <!-- overridden by local var -->
  <xsl:param name="iSubs"/>       <!-- overridden by local var -->
  <xsl:param name="pp"/>          <!-- price plan offer name -->
  <xsl:param name="contract"/>    <!-- contract offer name -->
  <xsl:param name="socDesc"/>     <!-- price plan description (fallback) -->
  <xsl:param name="address"/>     <!-- billing address -->
  <xsl:param name="contractDesc"/><!-- contract description -->
  <xsl:param name="currentDate"/> <!-- today formatted -->
  <xsl:param name="ppExpDate"/>   <!-- RMVX expiry - 1 day -->
  <xsl:param name="ppEffDate"/>   <!-- RMVX effective date -->
  <xsl:param name="smsInd"/>      <!-- SMS_IND activity parameter -->

  <xsl:template match="/">
    <createEvent>
      <event>
        <!-- Convert 0-based indices to 1-based for XPath -->
        <xsl:variable name="iParentOU" select="(number($i) + 1)"/>
        <xsl:variable name="iSubs" select="(number($j) + 1)"/>

        <xsl:if test="$orderRequest/OrderPriority">
          <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
          <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OrderID">
          <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        </xsl:if>
        <xsl:if test="$refId">
          <RefID><xsl:value-of select="$refId"/></RefID>
        </xsl:if>
        <xsl:if test="$orderRequest/OrderData/OrderType">
          <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        </xsl:if>
        <payload>
          <ns:SMSRequest>
            <!-- MSISDN: strip leading "0" and prefix "66" for international format -->
            <xsl:choose>
              <xsl:when test="not(starts-with(...ParentOU[$iParentOU]/Subscriber[$iSubs]/MSISDN,'0'))">
                <ns:MSISDN><xsl:value-of select="...MSISDN"/></ns:MSISDN>
              </xsl:when>
              <xsl:otherwise>
                <ns:MSISDN><xsl:value-of select="concat('66', substring-after(...MSISDN,'0'))"/></ns:MSISDN>
              </xsl:otherwise>
            </xsl:choose>
            <ns:CustomerType><xsl:value-of select="...CustomerTypeInfo/Type"/></ns:CustomerType>
            <!-- Language: subscriber preference or default TH -->
            <xsl:choose>
              <xsl:when test="exists(...SubscriberGeneralInfo/Language)">
                <ns:Language><xsl:value-of select="...Language"/></ns:Language>
              </xsl:when>
              <xsl:otherwise><ns:Language>TH</ns:Language></xsl:otherwise>
            </xsl:choose>
            <ns:OrderType><xsl:value-of select="...OrderType"/></ns:OrderType>
            <ns:PricePlan><xsl:value-of select="$pp"/></ns:PricePlan>
            <ns:CompanyCode><xsl:value-of select="...SubscriberType"/></ns:CompanyCode>
            <ns:ProductType/>  <!-- always empty -->
            <ns:Proposition><xsl:value-of select="$contract"/></ns:Proposition>
            <ns:MessageType/>  <!-- always empty -->
            <ns:ParamList>
              <!-- Param 1: subscriber name (individual) or org name (corporate) -->
              <ns:Param>
                <ns:name>1</ns:name>
                <ns:value>
                  <xsl:value-of select="if(...CustomerTypeInfo/Type=73)
                    then if(string-length(tib:trim(...LastName))>0)
                      then concat(...FirstName,' ',...LastName)
                      else ...FirstName
                    else ...OrgName"/>
                </ns:value>
              </ns:Param>
              <!-- Param 2: bill description — BILL_DESCRIPTION preferred over socDesc -->
              <ns:Param>
                <ns:name>2</ns:name>
                <xsl:choose>
                  <xsl:when test="string-length(...SubscriberOffers[ServiceType='80']/ExtendedInfo[Name='BILL_DESCRIPTION']/Value)>0">
                    <ns:value><xsl:value-of select="...BILL_DESCRIPTION.../Value"/></ns:value>
                  </xsl:when>
                  <xsl:otherwise>
                    <ns:value><xsl:value-of select="$socDesc"/></ns:value>
                  </xsl:otherwise>
                </xsl:choose>
              </ns:Param>
              <ns:Param><ns:name>3</ns:name><ns:value><xsl:value-of select="...BillCycleNo"/></ns:value></ns:Param>
              <ns:Param><ns:name>4</ns:name><ns:value><xsl:value-of select="$address"/></ns:value></ns:Param>
              <ns:Param><ns:name>5</ns:name><ns:value><xsl:value-of select="...MSISDN"/></ns:value></ns:Param>
              <ns:Param><ns:name>6</ns:name><ns:value><xsl:value-of select="$contract"/></ns:value></ns:Param>
              <ns:Param><ns:name>7</ns:name><ns:value><xsl:value-of select="$contractDesc"/></ns:value></ns:Param>
              <ns:Param><ns:name>8</ns:name><ns:value><xsl:value-of select="...Identification"/></ns:value></ns:Param>
              <ns:Param><ns:name>9</ns:name><ns:value><xsl:value-of select="$currentDate"/></ns:value></ns:Param>
              <ns:Param><ns:name>10</ns:name><ns:value><xsl:value-of select="$ppExpDate"/></ns:value></ns:Param>
              <ns:Param><ns:name>ppEffDate</ns:name><ns:value><xsl:value-of select="$ppEffDate"/></ns:value></ns:Param>
              <ns:Param><ns:name>offer</ns:name><ns:value><xsl:value-of select="$smsInd"/></ns:value></ns:Param>
            </ns:ParamList>
            <xsl:if test="...Channel">
              <ns:Channel><xsl:value-of select="...Channel"/></ns:Channel>
            </xsl:if>
          </ns:SMSRequest>
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
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority              [Conditional: if OrderPriority exists]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId   [Conditional]
    ├── OrderID              ← $orderRequest/OrderData/OrderID          [Conditional]
    ├── RefID                ← $refId (subscriber.RefId)                [Conditional]
    ├── OrderType            ← $orderRequest/OrderData/OrderType        [Conditional]
    └── payload                                                          [Always]
        └── ns:SMSRequest
            ├── ns:MSISDN    ← if starts-with "0": concat("66",…); else raw MSISDN  [Always/choose]
            ├── ns:CustomerType ← CustomerTypeInfo/Type                 [Always]
            ├── ns:Language  ← SubscriberGeneralInfo/Language; default "TH"         [Always/choose]
            ├── ns:OrderType ← OrderData/OrderType                      [Always]
            ├── ns:PricePlan ← $pp (ServiceType=80 CCBS offer name)    [Always]
            ├── ns:CompanyCode ← Subscriber/SubscriberType              [Always]
            ├── ns:ProductType ← ""                                     [Always/static empty]
            ├── ns:Proposition ← $contract                              [Always]
            ├── ns:MessageType ← ""                                     [Always/static empty]
            ├── ns:ParamList                                             [Always]
            │   ├── ns:Param[name="1"]  ← if Type=73: FirstName+" "+LastName; else OrgName  [Always/choose]
            │   ├── ns:Param[name="2"]  ← BILL_DESCRIPTION ExtendedInfo; else $socDesc      [Always/choose]
            │   ├── ns:Param[name="3"]  ← Customer/BillCycleNo          [Always]
            │   ├── ns:Param[name="4"]  ← $address                      [Always]
            │   ├── ns:Param[name="5"]  ← raw MSISDN (no 66 prefix)     [Always]
            │   ├── ns:Param[name="6"]  ← $contract                     [Always]
            │   ├── ns:Param[name="7"]  ← $contractDesc                 [Always]
            │   ├── ns:Param[name="8"]  ← CustomerGeneralInfo/Identification  [Always]
            │   ├── ns:Param[name="9"]  ← $currentDate                  [Always]
            │   ├── ns:Param[name="10"] ← $ppExpDate (RMVX expiry - 1 day)   [Always]
            │   ├── ns:Param[name="ppEffDate"] ← $ppEffDate             [Always/named param]
            │   └── ns:Param[name="offer"]     ← $smsInd                [Always/named param]
            └── ns:Channel   ← OrderData/Channel                        [Conditional: if Channel exists]
```

**Legend:** `← XPath source` green | `← "literal"` orange | `[Always]` always emitted | `[Conditional: ...]` inside xsl:if/xsl:when

---

## §11 Audit Logging

**Gate:** `RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)`

| Field | Request Log | Response Log |
|-------|-------------|--------------|
| ESBUUID | OMXTrackingId (conditional) | OMXTrackingId (conditional) |
| PROCESS_ID | concat(nanoTime, "_REQ") | concat(nanoTime, "_RES") |
| COMPONENT_NAME | `$globalVariables/.../OMX_CEP` | same |
| OPERATION_NAME | "SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE" | "SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE" |
| TARGET_SYSTEM | `$globalVariables/.../OMX_FM` | same |
| AUDIT_TRACE | concat("Request Sent for RefId ", $refId) | concat("Response received for RefId ", RefID) |
| AUDIT_TS | format-dateTime current-dateTime | same |
| payload | copy of reqEvent (WritePayload gated) | copy of eventResponse (WritePayload gated) |

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one subscriber dispatched | "1" (PROCESSING) | `GetActivityStatusString("1", false)` + SendDataToDB |
| All subscribers skipped | "4" (SKIPPED) | `SkipActivity(orderRequest, orderCurrentActivity, "4")` |
| Exception thrown | ERROR | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §13 Exception / Error Handling

Entire THEN block wrapped in `try { ... } catch (Exception ae) { ... }`.
On exception: `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` — empty fourth parameter.

---

## §14 Helper Functions Reference

| Function | Signature | Purpose |
|----------|-----------|---------|
| GetXMLForSubscriberInChildOU | (orderRequest, refId, parentOuRefId) | Serialize COU subscriber for PreExecCheck |
| GetXMLForSubscriber | (orderRequest, refId) | Serialize POU subscriber for PreExecCheck |
| GetActivityParamValueFromKey | (activity, key) | Fetch activity parameter by key |
| GetSubscriberOffersDescription | (offer, language) | Get offer description by language |
| GetSocDescriptionFromSocProperties | (socProps, language) | Parse SocProperties for description |
| GetDateFromOfferParamName | (offer, paramName) | Extract date from SocProperties param |
| ConvertMntoThaiMn | (dateStr, delimiter, format) | Convert English month abbreviation to Thai |
| GetAddressString | (billingArrangementAddress, language) | Format address to localized string |
| AllowWriteLog | (orderType) | Gate audit logging by order type |
| GetActivityStatusString | (statusCode, flag) | Translate status code to string |
| SkipActivity | (orderRequest, activity, statusCode) | Mark activity as skipped, advance process |
| SendDataToDB | (orderRequest) | Persist order state to database |
| HandleActivityException | (orderRequest, activity, exception, context) | Log error, handle failure |
| BRMS.IsBlank | (str) | True if null or empty |
| BRMS.IsBlankOrStringNull | (str) | True if null, empty, or literal "null" |

---

## §15 Function Dependency Tree

```text
Request_SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE
├── GetXMLForSubscriberInChildOU(orderRequest, refId, parentOuRefId)
├── GetXMLForSubscriber(orderRequest, refId)
├── XPath.execute(preExecCheck, sXML, ns)
├── [Per Subscriber]
│   ├── XPath.evalAsString(FE_OR_CCBS XPath)
│   ├── GetSubscriberOffersDescription(currOffer, language)
│   ├── GetSocDescriptionFromSocProperties(socProps, language)    [fallback]
│   ├── GetDateFromOfferParamName(rmvxOffer, "TR_ACTUAL_CONTRACT_START_DATE")
│   ├── GetDateFromOfferParamName(rmvxOffer, "TR_ORIG_CONTRACT_EXPIRE_DATE")
│   ├── DateTime.addDay(ppExpDT, -1)
│   ├── DateTime.format(dt, "dd-MMM-yyyy")
│   ├── ConvertMntoThaiMn(dateStr, "-", "dd-MMM-yyyy")           [if TH]
│   ├── GetAddressString(BillingArrangementAddress, language)
│   ├── GetActivityParamValueFromKey(activity, "SMS_IND")
│   ├── GetActivityParamValueFromKey(activity, "GET_EFF_EXP_FROM_RMVX")
│   ├── BRMS.IsBlank(socDesc)
│   ├── BRMS.IsBlank(contractDesc)
│   ├── BRMS.IsBlankOrStringNull(feOrCCBs)
│   ├── Event.createEvent("xslt://SMSGATEWAY_SEND_SMS ...")
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   └── AllowWriteLog(orderType)
│       └── Event.Ext.sendEventImmediate(Logger event)
├── GetActivityStatusString("1", false)
├── SendDataToDB(orderRequest)
├── SkipActivity(orderRequest, activity, "4")
└── HandleActivityException(orderRequest, activity, ae, "")
```

---

## §16 Concept Definitions Referenced

| Concept | Key Fields Used |
|---------|-----------------|
| `Concepts.OrderRequest.OrderRequest` | OrderData.*, ProcessFlow.*, IsOrderResubmitted |
| `Concepts.OM.ProcessConfig.Activity` | ActivityID, Status, PreExecCheck, Parameter[], Response[], RequestCount |
| `Concepts.OrderRequest.OrderElements.Subscriber` | RefId, MSISDN, SubscriberType, AccountRefId, SubscriberGeneralInfo.Language, SubscriberName.*, SubscriberOffers[], ResponseCode, ResponseMsg |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | OfferName, ServiceType, SocProperties, ExtendedInfo[] |
| `Concepts.FM.Response.SMSGATEWAY_SendSMSRes` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Send SMS to every subscriber (COU + POU) unless PreExecCheck fails or already successfully completed |
| R2 | Scan SubscriberOffers: (a) pp = ServiceType=80 & CCBS; (b) RMVX dates; (c) contract = TR_CONTRACT_IND=Y & FE/BRMS |
| R3 | Date formatting: dd-MMM-yyyy with Thai month names when Language=TH; ppExpDT adjusted by -1 day |
| R4 | MSISDN normalization: leading "0" → "66" prefix in ns:MSISDN; param #5 keeps raw MSISDN |
| R5 | BILL_DESCRIPTION ExtendedInfo (from INTX enrichment) preferred over raw socDesc for param #2 |
| R6 | 12-field ParamList with named params "ppEffDate" and "offer" (not numeric) |
| R7 | AllowWriteLog gate on audit trail; response RF writes sub.ResponseCode/sub.ResponseMsg |
| R8 | GET_EFF_EXP_FROM_RMVX activity parameter controls RMVX date extraction; default dates are DateTime.now() |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| ppEffDT/ppExpDT default to DateTime.now() — if no RMVX offer or GET_EFF_EXP_FROM_RMVX!='Y', SMS will contain today's date for both (ppExpDate = today-1 day) | [HIGH] | Verify RMVX offer always present when FM used; or add null guard before formatting |
| ppExpDT null guard dead code: `if(ppExpDT != null)` never false since initialized to DateTime.now() | [MEDIUM] | Remove dead guard; document -1 day always applied |
| Param #2 XSLT XPath has no positional index [$iParentOU][$iSubs] — may match wrong subscriber in multi-POU scenario | [MEDIUM] | Add positional predicates for correct subscriber selection |
| Two identical XSLT variants (COU, POU) — code duplication | [LOW] | Refactor to single XSLT callable from both scopes |
| Reuses SMSGATEWAY_SEND_SMS event type — response routing must discriminate by OPERATION_NAME | [LOW] | Verify response RF routing by OPERATION_NAME="SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE" |
| socProps and contractProps loaded but not directly used in XSLT | [LOW] | No functional impact; minor cleanup |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE {
  attribute {
    priority = 5;
    forwardChain = true;
  }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE";
    orderRequest.ProcessFlow.NextActivityID == "SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
    try {
      Concepts.OM.ProcessConfig.Activity nextAct = Instance.getByExtIdByUri(...);
      String chkXPath = nextAct.PreExecCheck;
      boolean isSkipped = true;

      /*** Begin ParentOU → ChildOU → Subscriber (COU) loop ***/
      int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
      for (int i=0; i < iPOULen; i++) {
        int iCOULen = ...ChildOU@length;
        for (int k=0; k < iCOULen; k++) {
          int iSubscriberLen = ...ChildOU[k].Subscriber@length;
          for (int j=0; j < iSubscriberLen; j++) {
            String refId = ...ChildOU[k].Subscriber[j].RefId;
            /* resubmit guard */
            if (!reqSuccess) {
              String sXML = RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, ParentOU[i].RefId);
              /* PreExecCheck gate */
              if (String.equals(chkRes, "true")) {
                /* Offer scan: pp (ServiceType=80+CCBS), RMVX dates, contract (TR_CONTRACT_IND=Y+FE/BRMS) */
                /* ppExpDT = DateTime.addDay(ppExpDT, -1) */
                /* Date formatting; address lookup; smsInd from SMS_IND param */
                Events.OMConsumers.OMXFM.Request.SMSGATEWAY_SEND_SMS reqEvent =
                  Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/SMSGATEWAY_SEND_SMS}}"
                  /* See §9.8 for full XSLT. Outputs: ns:SMSRequest with ns:MSISDN(66-prefix),
                     ns:CustomerType, ns:Language, ns:OrderType, ns:PricePlan, ns:CompanyCode,
                     ns:Proposition, ns:ParamList(12 params: 1-10 + ppEffDate + offer) */);
                Event.Ext.sendEventImmediate(reqEvent);
                if (!isActResub) orderCurrentActivity.RequestCount++;
                isSkipped = false;
                if (RuleFunctions.Helpers.AllowWriteLog(orderRequest.OrderData.OrderType)) {
                  /* Audit log: OPERATION_NAME="SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE" */
                  Event.Ext.sendEventImmediate(Event.createEvent("xslt://Logger ..."));
                }
              }
            }
          }
        }
        /*** Begin ParentOU Subscriber (POU) loop — identical logic, uses GetXMLForSubscriber ***/
        for (int j=0; j < ...ParentOU[i].Subscriber@length; j++) {
          /* Identical structure to COU loop above */
        }
      }

      if (!isSkipped) {
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
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

## §19 Response Message Rule — `Response_SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE`

### §19.1 Overview

Handles the SMS gateway response. Builds `SMSGATEWAY_SendSMSRes` ResponseBase concept, appends to activity Response array, optionally audit-logs, and additionally **writes ResponseCode/ResponseMsg back to the Subscriber concept** in working memory. Returns "true" when RequestCount == successCount.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order; AllowWriteLog + subscriber lookup |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.SMSGATEWAY_SEND_SMS` | Incoming response event |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Response[] and RequestCount |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId           ← OMXUtils:generateTrackingID()           [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode             [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg              [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus         [Conditional]
    └── ReferenceId      ← $eventResponse/RefID                   [Conditional]
```

### §19.3b Subscriber Write-back

> **Unique pattern:** After ResponseBase, looks up Subscriber by working-memory extId:
> `Instance.getByExtIdByUri("SUB:" + JMSCorrelationID + ":" + RefID, "/Concepts/OrderRequest/OrderElements/Subscriber")`
> If null, tries: `"CSUB:" + JMSCorrelationID + ":" + RefID`
> Then writes: `sub.ResponseCode = eventResponse.ResponseCode; sub.ResponseMsg = eventResponse.ResponseMsg`

### §19.4 Response Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| True result | All parallel SMS requests completed with ResponseCode suffix "000" |
| False result | Still waiting for remaining subscriber responses |

### §19.5 Response Audit Logging

Gate: `AllowWriteLog(orderRequest.OrderData.OrderType)`

| Field | Value |
|-------|-------|
| PROCESS_ID | concat(nanoTime, "_RES") |
| OPERATION_NAME | "SMSGATEWAY_SEND_SMS_UPDATE_EXPIRE" |
| AUDIT_TRACE | concat("Response received for RefId ", $eventResponse/RefID) |
| payload | copy of $eventResponse (WritePayload gated) |

### §19.6 Response XSLT Source

```xml
<xsl:stylesheet xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema" version="1.0">
  <xsl:output method="xml"/>
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId">
          <xsl:value-of select="OMXUtils:generateTrackingID()"/>
        </xsl:attribute>
        <xsl:if test="$eventResponse/ResponseCode">
          <ResponseCode><xsl:value-of select="$eventResponse/ResponseCode"/></ResponseCode>
        </xsl:if>
        <xsl:if test="$eventResponse/ResponseMsg">
          <ResponseMessage><xsl:value-of select="$eventResponse/ResponseMsg"/></ResponseMessage>
        </xsl:if>
        <xsl:if test="$eventResponse/CompletionStatus">
          <CompletionStatus><xsl:value-of select="$eventResponse/CompletionStatus"/></CompletionStatus>
        </xsl:if>
        <xsl:if test="$eventResponse/RefID">
          <ReferenceId><xsl:value-of select="$eventResponse/RefID"/></ReferenceId>
        </xsl:if>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
