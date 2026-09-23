# Request_OMX_ADD_PROV

> Submits a future SOC provisioning order (PROV) to OMX internal future-order system per OU per Agreement, scheduling new priceplan activation and current priceplan expiry for tomorrow (Bangkok TZ).

**System:** OMX Internal | **Priority:** 5 | **Author:** warawich-nb  
**orderType:** 203 (hardcoded) | **futureType:** PROV (hardcoded) | **Loop:** OU × Agreement  
**Send pattern:** Event.Ext.sendEventImmediate | **JMSCorrelationID:** OMXTrackingId (standard)

---

## §1 Overview & Purpose

Submits a **future SOC provisioning order** (futureType=PROV, orderType=203) to OMX's internal future-order system via the `OMX_ADD_FUTURE` event. Iterates over POU and COU-level Agreements and schedules:
- A **new priceplan futureSoc** (effectiveDate = tomorrow) — always sent
- A **current priceplan futureSoc** (expireDate = tomorrow) — sent only if `currentPricePlanSoc` is non-empty

"Tomorrow" is calculated in Bangkok timezone (UTC+7) by adding 1 day to the current date at midnight.

| Attribute | Value |
|-----------|-------|
| Rule File | `Request_OMX_ADD_PROV.rule` |
| Response File | `Response_OMX_ADD_PROV.rulefunction` |
| Author | warawich-nb |
| Priority | 5 |
| Target System | OMX Internal (future-order subsystem) |
| Event name | OMX_ADD_FUTURE |
| orderType | 203 (hardcoded) |
| futureType | PROV (hardcoded) |
| Loop level | OU (POU then COU), per Agreement |
| Timezone | Bangkok (+7) for "tomorrow" calculation |
| Send pattern | Event.Ext.sendEventImmediate + manual RequestCount++ |
| Audit pattern | Event.Ext.sendEventImmediate (sync) |
| JMSCorrelationID | `$orderRequest/OrderData/OMXTrackingId` (standard) |
| Fan-in | IsAllResponseSuccess(currActivity) |

---

## §4 Rule Conditions (WHEN)

| Condition | Purpose |
|-----------|---------|
| `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity pointer |
| `ActivityID == "OMX_ADD_PROV"` | FM match |
| `orderRequest.ProcessFlow.NextActivityID == "OMX_ADD_PROV"` | Flow alignment |
| `orderCurrentActivity.Status == "WAITING"` | Prevents re-firing |

---

## §5 Execution Flow

1. **Init** — If resubmit → `PurgePendingRequestsBeforeResubmit`. Compute `tomorrow` in Bangkok TZ (+7). Extract `customerType` (ASCII→text), `accountSubType`, `requestBy`. Build `userText`. Set `isSkipped=true`.
2. **POU loop** — `GetXMLForAgreement(orderRequest, pOu.Agreement.RefId)`. If CompletionStatus==2 → skip. Extract currentPricePlanSoc (CCBS) + newPricePlanSoc (FE) from Offers.
3. **POU Send** — Build OMX_ADD_FUTURE (POU variant). `sendEventImmediate`. If !resubmit → `RequestCount++`. Set `isSkipped=false`, `Status="1"` inside send block.
4. **COU loop** — `GetXMLForAgreementInChildOU(orderRequest, cAgreeRefId, pOuRef)`. CompletionStatus==2 guard (uses `cAgreeRefId` — correct). Same priceplan extraction + send (COU variant). `isSkipped=false`, `Status="1"` inside send block.
5. **Post-loop** — If `!isSkipped` → `Status="1"` again (redundant) + `SendDataToDB`. Else → `SkipActivity("4")`.
6. **Exception** → `HandleActivityException`

> **Note — Redundant Status="1":** Status is set both inside the per-OU send block and again after the outer loop. The post-loop set is redundant.

---

## §7 Data Extraction

### §7.1 Priceplan Extraction (per Agreement)

| Variable | XPath Filter | Extracted Field | Default |
|----------|-------------|-----------------|---------|
| `currentPricePlanSoc` | `ServiceType='80' and FE_OR_CCBS='CCBS'` | Offer.Soc | `""` |
| `currentPricePlanName` | Same | Offer.Name | `""` |
| `currentPricePlanInstanceId` | Same | Offer.InstanceId | `""` |
| `newPricePlanSoc` | `ServiceType='80' and FE_OR_CCBS='FE'` | Offer.Soc | `""` |
| `newPricePlanName` | Same | Offer.Name | `""` |

### §7.2 userText Construction

```java
String userText = String.format("%s;request by %s on %s;", inputUserText, requestBy, dateTimeNow);
```

### §7.3 Tomorrow Calculation

```java
// Bangkok TZ offset +7 hardcoded; adds P1D (1 day) to today's date at Bangkok midnight
String tomorrow = tib:format-dateTime(tib:add-to-dateTime(tib:current-date(), "PT7H"), "P1D");
```

> **Warning:** Bangkok TZ offset +7 is hardcoded. Executions near midnight UTC may shift "tomorrow" vs. local business day.

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

| Trigger | ProcessConfig | Purpose |
|---------|--------------|---------|
| CHANGE_PP flow, step 79 | CHANGE_PP.xml | Schedule PROV future SOC for priceplan change |

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event | Protocol | Purpose |
|-----------|-------|----------|---------|
| [OUTBOUND] | OMX_ADD_FUTURE | JMS/BE internal | Future SOC provisioning order |
| [OUTBOUND] | Logger (OMXESB) | JMS | Request/Response audit trail |

### §8.3 Backend API Details

| System | Operation | orderType | futureType | Pattern |
|--------|-----------|-----------|------------|---------|
| OMX Future Order | ADD_FUTURE | 203 | PROV | Event.Ext.sendEventImmediate (sync) |

### §8.5 ExtendedInfo Fields Required

| Name | Required? | Scope | Where used |
|------|-----------|-------|-----------|
| FE_OR_CCBS | Required | Offer.ExtendedInfo | Priceplan CCBS/FE extraction |
| POU_ID | Always emitted | futureOrder.extendedInfo | POU and COU sends |
| CUS_ID | Always emitted | futureOrder.extendedInfo | POU and COU sends |
| PAGR_ID | Always emitted | futureOrder.extendedInfo | POU and COU sends |
| OU_ID | COU only | futureOrder.extendedInfo | COU sends only |

### §8.6 Global Variable Dependencies

| Path | Used for |
|------|---------|
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | Audit COMPONENT_NAME |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | Audit TARGET_SYSTEM |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | Audit LOG_LEVEL |
| `$globalVariables/OMX_OM/WritePayload` | Conditional payload in audit |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Param | POU Binding | COU Binding |
|-------|-------------|-------------|
| `orderRequest` | OrderRequest concept | same |
| `agreeRefId` / `cAgreeRefId` | pOu.Agreement.RefId | cOu.Agreement.RefId |
| `tomorrow` | Bangkok TZ date+1 | same |
| `orderType` | "203" (hardcoded) | same |
| `nodeLeve` | "3" (hardcoded, **typo: missing 'l'**) | same |
| `nodeId` | pOuId | cOuId |
| `requestBy` | OrderRequest field | same |
| `pOu` / `cOu` | ParentOU[iPOU] | ChildOU[iCOU] |
| `pOuId` | ParentOU.OUId | ParentOU.OUId (still POU's) |
| `custId` | Customer.CustomerId | same |
| `pAgreeId` | ParentOU Agreement ID | ParentOU Agreement ID |
| `userText` | Constructed string | same |
| `customerType` | OMXUtils.asciiCodeToText(...) | same |
| `accountSubType` | Account[1].AccountSubType | same |
| `futureType` | "PROV" (hardcoded) | same |
| `newPricePlanSoc` | FE_OR_CCBS='FE' Offer.Soc | same |
| `currentPricePlanSoc` | FE_OR_CCBS='CCBS' Offer.Soc | same |
| `currentPricePlanInstanceId` | FE_OR_CCBS='CCBS' Offer.InstanceId | same |

> **Note:** `nodeLeve` is a typo in source code (should be `nodeLevel`). XSLT param name must match exactly — rename both together.

### §9.3 JMS / Event Header Fields

| Header | Source | Conditional? |
|--------|--------|-------------|
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | [Conditional: if OMXTrackingId] |
| `RefID` | `$agreeRefId` / `$cAgreeRefId` | [Conditional: if agreeRefId] |
| `UserName` | `$orderRequest/OrderData/UserName` | [Conditional] |
| `PassWord` | `$orderRequest/OrderData/PassWord` | [Conditional] |

### §9.5 Conditional Fields

| Element | Condition | Source |
|---------|-----------|--------|
| `activityReason` | if activityReason present | `$orderRequest/OrderData/activityReason` |
| `extendedInfo[OU_ID]` | COU loop only | `$cOuId` |
| `futureSoc (currentPricePlan)` | if `$currentPricePlanSoc != ''` | Soc + expireDate=tomorrow |
| `ns2:instanceId` | POU only (current priceplan futureSoc) | `$currentPricePlanInstanceId` |
| `ns2:parentInstanceId` | COU only (current priceplan futureSoc) | `$currentPricePlanInstanceId` |

### §9.8 XSLT Stylesheet Source

**POU Variant ①** — `agreeRefId`, `pOu`, `nodeId=pOuId`, no OU_ID, uses `ns2:instanceId`

```xml
<xsl:stylesheet xmlns:ns3="..." xmlns:ns="..." xmlns:ns2="..." version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="agreeRefId"/>              <!-- pOu.Agreement.RefId -->
  <xsl:param name="tomorrow"/>               <!-- Bangkok TZ date+1 -->
  <xsl:param name="orderType"/>              <!-- "203" -->
  <xsl:param name="nodeLeve"/>              <!-- "3" — typo: missing 'l' -->
  <xsl:param name="nodeId"/>               <!-- pOuId -->
  <xsl:param name="requestBy"/>
  <xsl:param name="pOu"/>                  <!-- ParentOU concept -->
  <xsl:param name="pOuId"/>
  <xsl:param name="custId"/>
  <xsl:param name="pAgreeId"/>
  <xsl:param name="userText"/>
  <xsl:param name="customerType"/>
  <xsl:param name="accountSubType"/>
  <xsl:param name="futureType"/>            <!-- "PROV" -->
  <xsl:param name="newPricePlanSoc"/>
  <xsl:param name="currentPricePlanSoc"/>
  <xsl:param name="currentPricePlanInstanceId"/>
  <xsl:template match="/">
    <createEvent><event>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      </xsl:if>
      <xsl:if test="$agreeRefId">
        <RefID><xsl:value-of select="$agreeRefId"/></RefID>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/UserName">
        <UserName><xsl:value-of select="$orderRequest/OrderData/UserName"/></UserName>
      </xsl:if>
      <xsl:if test="$orderRequest/OrderData/PassWord">
        <PassWord><xsl:value-of select="$orderRequest/OrderData/PassWord"/></PassWord>
      </xsl:if>
      <payload>
        <ns3:futureOrderWithSoc>
          <ns:futureOrder>
            <ns:effectiveDate><xsl:value-of select="$tomorrow"/></ns:effectiveDate>
            <ns:orderType><xsl:value-of select="$orderType"/></ns:orderType>       <!-- 203 -->
            <ns:nodeLevel><xsl:value-of select="$nodeLeve"/></ns:nodeLevel>        <!-- typo param -->
            <ns:nodeId><xsl:value-of select="$nodeId"/></ns:nodeId>
            <ns:requestedDate><xsl:value-of select="current-dateTime()"/></ns:requestedDate>
            <ns:requestedBy><xsl:value-of select="$requestBy"/></ns:requestedBy>
            <xsl:if test="$orderRequest/OrderData/activityReason">
              <ns:activityReason>...</ns:activityReason>
            </xsl:if>
            <ns:extendedInfo>
              <ns:info><ns:name>POU_ID</ns:name><ns:value><xsl:value-of select="$pOuId"/></ns:value></ns:info>
              <ns:info><ns:name>CUS_ID</ns:name><ns:value><xsl:value-of select="$custId"/></ns:value></ns:info>
              <ns:info><ns:name>PAGR_ID</ns:name><ns:value><xsl:value-of select="$pAgreeId"/></ns:value></ns:info>
              <!-- OU_ID: COU variant only -->
            </ns:extendedInfo>
            <ns:fromOrderId>...</ns:fromOrderId>
            <ns:userText><xsl:value-of select="$userText"/></ns:userText>
            <ns:customerType><xsl:value-of select="$customerType"/></ns:customerType>
            <ns:accountSubtype><xsl:value-of select="$accountSubType"/></ns:accountSubtype>
            <ns:futureType><xsl:value-of select="$futureType"/></ns:futureType>    <!-- PROV -->
          </ns:futureOrder>
          <ns2:futureSocs>
            <!-- futureSoc: newPricePlan (always) -->
            <ns2:futureSoc>
              <ns2:code><xsl:value-of select="$newPricePlanSoc"/></ns2:code>
              <ns2:effectiveDate><xsl:value-of select="$tomorrow"/></ns2:effectiveDate>
              <ns2:ParameterInfo>... from Agreement.Offers parameters</ns2:ParameterInfo>
              <ns2:RelatedOffersArray>
                <ns2:childSoc>... RelatedOffers loop (code, ParameterInfo, type, socName)</ns2:childSoc>
              </ns2:RelatedOffersArray>
              <ns2:type>80</ns2:type>
              <ns2:subType><xsl:value-of select="$futureType"/></ns2:subType>  <!-- PROV -->
              <ns2:socName>...</ns2:socName>
            </ns2:futureSoc>
            <!-- futureSoc: currentPricePlan (conditional) -->
            <xsl:if test="$currentPricePlanSoc != ''">
              <ns2:futureSoc>
                <ns2:code><xsl:value-of select="$currentPricePlanSoc"/></ns2:code>
                <ns2:expireDate><xsl:value-of select="$tomorrow"/></ns2:expireDate>
                <ns2:instanceId><xsl:value-of select="$currentPricePlanInstanceId"/></ns2:instanceId>
                <!-- COU variant uses ns2:parentInstanceId here -->
                <ns2:type>80</ns2:type>
                <ns2:subType><xsl:value-of select="$futureType"/></ns2:subType>
                <ns2:socName>...</ns2:socName>
              </ns2:futureSoc>
            </xsl:if>
          </ns2:futureSocs>
        </ns3:futureOrderWithSoc>
      </payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

**COU Variant ② — Differences from POU ①:**

| Difference | POU ① | COU ② |
|-----------|-------|-------|
| Agreement RefId param | `agreeRefId` | `cAgreeRefId` |
| OU concept param | `pOu` | `cOu` |
| nodeId | pOuId | cOuId |
| extendedInfo[OU_ID] | omitted | emitted with cOuId |
| currentPricePlan instance element | `ns2:instanceId` | `ns2:parentInstanceId` |

---

## §10 XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSCorrelationID   ← $orderRequest/OrderData/OMXTrackingId   [Conditional: if OMXTrackingId]
    ├── RefID              ← $agreeRefId / $cAgreeRefId               [Conditional: if agreeRefId]
    ├── UserName           ← $orderRequest/OrderData/UserName         [Conditional]
    ├── PassWord           ← $orderRequest/OrderData/PassWord         [Conditional]
    └── payload
        └── ns3:futureOrderWithSoc
            ├── ns:futureOrder
            │   ├── ns:effectiveDate      ← $tomorrow                  [Always]
            │   ├── ns:orderType          ← "203" (hardcoded)          [Always]
            │   ├── ns:nodeLevel          ← $nodeLeve ⚠typo param      [Always]
            │   ├── ns:nodeId             ← $nodeId (pOuId/cOuId)      [Always]
            │   ├── ns:requestedDate      ← current-dateTime()         [Always]
            │   ├── ns:requestedBy        ← $requestBy                 [Always]
            │   ├── ns:activityReason     ← $orderRequest/OrderData/activityReason  [Conditional]
            │   ├── ns:extendedInfo
            │   │   ├── ns:info[POU_ID]  ← $pOuId                    [Always]
            │   │   ├── ns:info[CUS_ID]  ← $custId                    [Always]
            │   │   ├── ns:info[PAGR_ID] ← $pAgreeId                  [Always]
            │   │   └── ns:info[OU_ID]   ← $cOuId                     [COU variant only]
            │   ├── ns:fromOrderId        ← $orderRequest/OrderData/OrderID  [Always]
            │   ├── ns:userText           ← $userText                  [Always]
            │   ├── ns:customerType       ← $customerType              [Always]
            │   ├── ns:accountSubtype     ← $accountSubType            [Always]
            │   └── ns:futureType         ← "PROV" (via $futureType)   [Always]
            └── ns2:futureSocs
                ├── ns2:futureSoc [newPricePlan]                       [Always]
                │   ├── ns2:code           ← $newPricePlanSoc          [Always]
                │   ├── ns2:effectiveDate  ← $tomorrow                 [Always]
                │   ├── ns2:ParameterInfo  ← Agreement.Offers params   [Conditional]
                │   ├── ns2:RelatedOffersArray/ns2:childSoc           [Conditional: if related offers]
                │   ├── ns2:type           ← "80" (hardcoded)          [Always]
                │   ├── ns2:subType        ← "PROV"                    [Always]
                │   └── ns2:socName        ← newPricePlanName          [Always]
                └── ns2:futureSoc [currentPricePlan]                   [Conditional: if currentPricePlanSoc != '']
                    ├── ns2:code           ← $currentPricePlanSoc      [Always within block]
                    ├── ns2:expireDate     ← $tomorrow                 [Always within block]
                    ├── ns2:instanceId     ← $currentPricePlanInstanceId  [POU variant only]
                    ├── ns2:parentInstanceId ← $currentPricePlanInstanceId  [COU variant only]
                    ├── ns2:type           ← "80" (hardcoded)          [Always within block]
                    ├── ns2:subType        ← "PROV"                    [Always within block]
                    └── ns2:socName        ← currentPricePlanName      [Always within block]
```

---

## §11 Audit Logging

| Direction | OPERATION_NAME | AUDIT_TRACE | Send Method |
|-----------|---------------|-------------|-------------|
| Request | `"OMX_ADD_PROV"` | `"Request Sent for OMX_ADD_PROV"` | Event.Ext.sendEventImmediate (sync) |
| Response | `"OMX_ADD_PROV"` | `"Response received for OMX_ADD_PROV"` | Event.Ext.sendEventImmediate (sync) |

---

## §12 Activity Status Management

| Condition | Status | Action |
|-----------|--------|--------|
| At least one OU send | "1" IN_PROGRESS | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| All OUs skipped | SKIPPED | `SkipActivity("4")` |

> Status="1" is set twice: once inside the per-OU send block and once in the post-loop block. The post-loop set is redundant.

---

## §15 Function Dependency Tree

```text
Request_OMX_ADD_PROV
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit  [if resubmit]
├── tib:add-to-dateTime (Bangkok TZ +7, P1D)                    [tomorrow calculation]
├── OMXUtils.asciiCodeToText(CustomerTypeInfo.Type)             [customerType]
├── String.format(userText pattern)                             [userText]
├── GetXMLForAgreement(orderRequest, agreeRefId)                [POU PreExecCheck]
├── GetXMLForAgreementInChildOU(orderRequest, cAgreeRefId, pOuRef) [COU PreExecCheck]
├── XPath.evalAsBoolean(ServiceType=80 + FE_OR_CCBS)            [priceplan extraction x2 per OU]
├── Event.createEvent("xslt://OMX_ADD_FUTURE POU variant")      [§9.8 POU ①]
├── Event.createEvent("xslt://OMX_ADD_FUTURE COU variant")      [§9.8 COU ②]
├── Event.Ext.sendEventImmediate(reqEvent)                      [per OU send]
├── RequestCount++ (if !resubmit)
├── Event.createEvent(Logger) + sendEventImmediate              [audit per send]
├── GetActivityStatusString("1", false)
├── SkipActivity("4") | SendDataToDB
└── HandleActivityException(...)

Response_OMX_ADD_PROV
├── Instance.createInstance(OMX_AddFutureRes XSLT)             [§19.3 — map response fields]
├── currActivity.Response[length] = resEvent
├── Event.createEvent(Logger) + Event.Ext.sendEventImmediate   [response audit, sync]
└── RuleFunctions.Helpers.IsAllResponseSuccess(currActivity)   [fan-in check]
```

---

## §17 Migration Notes & Recommendations

### §17.1 Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Submit future provisioning SOC orders with orderType=203 and futureType=PROV |
| R2 | Schedule new priceplan SOC effective tomorrow (Bangkok TZ midnight) |
| R3 | Schedule current priceplan SOC expiry for tomorrow if currentPricePlanSoc is present |
| R4 | Per-Agreement granularity: one send per OU per Agreement |
| R5 | POU uses ns2:instanceId; COU uses ns2:parentInstanceId for current priceplan futureSoc |
| R6 | COU adds OU_ID to extendedInfo; POU does not |

### §17.2 Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Bangkok TZ offset (+7) hardcoded — DST or TZ config changes break "tomorrow" | [MEDIUM] | Parameterize TZ offset from global variable |
| `nodeLeve` typo in param name — rename breaks XSLT without coordinated change | [MEDIUM] | Fix both BE rule and XSLT together; add test on nodeLevel output |
| Redundant Status="1" set both inside and after loop | [LOW] | Remove inner Status="1"; set only in post-loop block |
| No validation error if newPricePlanSoc is empty — empty SOC sent to OMX | [HIGH] | Add OMX_DATA_ERROR if newPricePlanSoc="" before send |
| customerType uses ASCII→text conversion via OMXUtils custom function | [LOW] | Document valid ASCII→text mapping; port OMXUtils to microservice |

---

## §18 Full Source Code

```java
/**
 * @author warawich-nb
 */
rule Rules.OMConsumers.OMXFM.Request.Request_OMX_ADD_PROV {
    attribute { priority = 5; forwardChain = true; }
    when {
        // ActivityID == "OMX_ADD_PROV" + WAITING status + flow alignment
    }
    then {
        boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
        try {
            if(isActResub) PurgePendingRequestsBeforeResubmit(...);

            // tomorrow = Bangkok TZ (UTC+7) + 1 day
            String tomorrow = tib:add-to-dateTime(tib:current-date()+offset(7,0), "P1D");
            String customerType = OMXUtils.asciiCodeToText(Customer.CustomerTypeInfo.Type);
            String accountSubType = Customer.Account[1].AccountManagementInfo.AccountSubType;
            String userText = String.format("%s;request by %s on %s;", inputUserText, requestBy, dateTimeNow);
            boolean isSkipped = true;

            // POU loop
            for(int iPOU=0; iPOU<pOULen; iPOU++) {
                agreeRefId = pOu.Agreement.RefId;
                chkRes = GetXMLForAgreement(orderRequest, agreeRefId);
                if(CompletionStatus==2) continue;  // uses agreeRefId — correct
                // Extract currentPricePlanSoc (CCBS) + newPricePlanSoc (FE) from Offers
                /* §9.8 POU Variant ①: XSLT builds ns3:futureOrderWithSoc with
                   ns:futureOrder (effectiveDate=tomorrow, orderType=203, nodeLeve=3, ...)
                   + ns2:futureSocs (newPP always, currentPP conditional if non-empty) */
                Event.Ext.sendEventImmediate(reqEvent_POU);
                if(!isActResub) orderCurrentActivity.RequestCount++;
                isSkipped = false;
                Status = "1";  // inside per-OU block
            }

            // COU loop
            for(int iCOU=0; iCOU<cOULen; iCOU++) {
                cAgreeRefId = cOu.Agreement.RefId;
                chkRes = GetXMLForAgreementInChildOU(orderRequest, cAgreeRefId, pOuRef);
                if(CompletionStatus==2) continue;  // uses cAgreeRefId — correct
                /* §9.8 COU Variant ②: agreeRefId→cAgreeRefId, pOu→cOu, adds OU_ID,
                   uses ns2:parentInstanceId (not ns2:instanceId) for currentPricePlan */
                Event.Ext.sendEventImmediate(reqEvent_COU);
                if(!isActResub) orderCurrentActivity.RequestCount++;
                isSkipped = false;
                Status = "1";  // inside per-OU block (redundant with post-loop)
            }

            if(!isSkipped) { Status="1"; SendDataToDB(); }  // Status="1" here is redundant
            else SkipActivity("4");
        } catch(Exception ae) { HandleActivityException(...); }
    }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

Parses the OMX_ADD_FUTURE response, maps 3 standard fields into an `OMX_AddFutureRes` concept, appends to `currActivity.Response`, logs response audit, and returns IsAllResponseSuccess fan-in result.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Root order data for audit + logging |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.OMX_ADD_FUTURE | Inbound response event from OMX |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Activity state — Response[] array + RequestCount |

### §19.3 OMX_AddFutureRes Concept Construction

```text
createObject
└── object
    ├── @extId            ← OMXUtils:generateTrackingID()              [Always]
    ├── ResponseCode      ← $eventResponse/ResponseCode                [Conditional: if ResponseCode]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg                 [Conditional: if ResponseMsg]
    └── CompletionStatus  ← $eventResponse/CompletionStatus            [Conditional: if CompletionStatus]
```

Note: OMX_AddFutureRes has 3 fields only (no ReferenceId, unlike CCBS responses).

### §19.4 Response Completion Logic

| Function | Return | Meaning |
|----------|--------|---------|
| `IsAllResponseSuccess(currActivity)` | "true" | All OMX_ADD_FUTURE calls succeeded; activity can advance |
| `IsAllResponseSuccess(currActivity)` | "false" | Still waiting or failure detected |

Uses shared helper `IsAllResponseSuccess` (underlying: count ResponseCode suffix "000" == RequestCount).

### §19.5 Response Audit Logging

| Field | Value |
|-------|-------|
| ESBUUID | `$orderRequest/OrderData/OMXTrackingId` |
| PROCESS_ID | `concat($pid, "_RES")` |
| COMPONENT_NAME | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| OPERATION_NAME | `"OMX_ADD_PROV"` |
| TARGET_SYSTEM | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| LOG_LEVEL | INFO |
| AUDIT_TRACE | `"Response received for OMX_ADD_PROV"` |
| AUDIT_TS | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| payload/ns:ServicePayload | [Conditional: if WritePayload="true"] — copy of $eventResponse |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
