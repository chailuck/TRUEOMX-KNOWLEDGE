# Request_CCBS_L9_GET_CUGID_BY_AGREEMENTID

## §1 — Overview & Purpose

This rule fires during the **CHANGE_PP** order flow for shareplan (ParentOU) arrangements. It queries the CCBS L9 layer to retrieve the *CUG ID* (Closed User Group ID) associated with the ParentOU's Agreement, which is required for shareplan operations.

The CUG ID is stored as a `ParameterInfo` entry on AgreementOffers that are marked with `ExtendedInfo[SHARE_OFFER_DESC=CUG_ID]` and are not being removed. This populates the CUG ID needed by subsequent CCBS shareplan update steps.

> **Iteration unit:** this rule iterates over **ParentOU** (not Subscriber) — one request per ParentOU Agreement. It uses `GetXMLForAgreement` (not GetXMLForSubscriber) for PreExecCheck evaluation. The PreExecCheck condition in CHANGE_PP step 12 is: `Agreement[1]/Offers[OFFER_LEVEL='PARENT']`.

> **[NOTE]:** `ActionRequestEvent` is commented out — direct `sendEventImmediate` is used. Early response return `"false"` if `cugId < 0` (invalid/negative GroupId).

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule path | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_L9_GET_CUGID_BY_AGREEMENTID` |
| Priority | 5 |
| ForwardChain | true |
| ActivityID guard | `CCBS_L9_GET_CUGID_BY_AGREEMENTID` |
| Response event type | `Events.OMConsumers.OMXFM.Response.CCBS_L9_GET_CUGID_BY_AGREEMENTID` |
| Backend | CCBS (L9 layer — UserGroupInfo API) |

## §3 — Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order context — iterated by ParentOU (not Subscriber) |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Active process step |

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity-order pointer match |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_L9_GET_CUGID_BY_AGREEMENTID"` | Guards to specific activity |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_L9_GET_CUGID_BY_AGREEMENTID"` | Flow pointer double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Not yet dispatched |

## §5 — Execution Flow Diagram

1. Check `isActResub`
2. Loop over `ParentOU[j]` (not Subscriber)
3. Extract `refId` from `ParentOU[j].Agreement.RefId` (XPath: if present, else "")
4. Check `reqSuccess` guard vs existing responses
5. Skip if `refId == ""` (no Agreement); evaluate PreExecCheck via `GetXMLForAgreement`
6. If PreExecCheck passes: build and send `CCBS_L9_GET_CUGID_BY_AGREEMENTID` event (direct sendEventImmediate); send audit log; increment RequestCount
7. Post-loop: Status="1" if any sent, else SkipActivity "4"
8. On exception: `HandleActivityException`

## §6 — Rule Action (THEN) — Detailed Logic

### Iteration unit: ParentOU (not Subscriber)

Unlike most other OMXFM rules that iterate over Subscribers, this rule iterates over **ParentOU** elements. One request is sent per ParentOU that has a valid Agreement.

### PreExecCheck helper

Uses `GetXMLForAgreement(orderRequest, refId)` — serialises the Agreement XML for XPath evaluation. If `refId == ""` (Agreement.RefId absent): `chkRes = "false"` — activity skipped for that OU. If PreExecCheck is empty: `chkRes = "true"` — always proceed.

### CES field logic

- If `globalVariables/OMX_OM/PassToBDH = "true"` → `CES = "Y"` (static)
- Otherwise: copy `$orderRequest/OrderData/CES` (conditional on existence)

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Fires in **CHANGE_PP** step 12 when ParentOU Agreements with `OFFER_LEVEL=PARENT` offers exist. Retrieves the CCBS CUG ID needed for subsequent shareplan OU operations.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event Type | Purpose |
|-----------|-----------|---------|
| [OUTBOUND] | `Events.OMConsumers.OMXFM.Request.CCBS_L9_GET_CUGID_BY_AGREEMENTID` | Request CUG ID lookup from CCBS L9 by Agreement ID |
| [INBOUND] | `Events.OMConsumers.OMXFM.Response.CCBS_L9_GET_CUGID_BY_AGREEMENTID` | Response with UserGroupInfo.GroupId |
| [OUTBOUND] | `Events.OMConsumers.OMXESB.Logger` | Audit log |

### §8.3 Backend API Details

| System | Operation | Payload Schema | Notes |
|--------|-----------|----------------|-------|
| CCBS L9 | GetCUGIdByAgreementId | `www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.UserGroupInfo` | Returns UserGroupInfo with GroupId; negative GroupId = not found |

### §8.4 BE Working Memory Dependencies

| Field | Read/Write | Purpose |
|-------|-----------|---------|
| `orderRequest.OrderData.Customer.ParentOU[j].Agreement.RefId` | READ | RefId for reqSuccess check (must be non-empty) |
| `orderRequest.OrderData.Customer.ParentOU[j].Agreement.AgreementId` | READ | Used as RefID and GroupIdentifier/GroupName in payload |
| `orderCurrentActivity.Response[iResp]` | READ | reqSuccess guard |
| `orderCurrentActivity.RequestCount` | READ/WRITE | Fan-in counter |
| `orderCurrentActivity.Status` | WRITE | Set to "1" or skip |
| `orderRequest.OrderData.Customer.ParentOU[iPOU].Agreement.Offers[iAOffer].ParameterInfo[]` | WRITE (response) | Appends AgreementParameterInfo with ParamName="CUG ID" and the retrieved GroupId |

### §8.5 ExtendedInfo Fields

| Name | Value checked | Where |
|------|--------------|-------|
| `SHARE_OFFER_DESC` | `"CUG_ID"` | AgreementOffers — identifies which offers need the CUG ID parameter appended |
| `OFFER_LEVEL` | `"PARENT"` | Agreement.Offers — PreExecCheck condition (step 12) |

### §8.6 Global Variable Dependencies

| Variable Path | Used For |
|--------------|---------|
| `OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | Conditional UserName/Password |
| `OMX_OM/PassToBDH` | If "true" → CES field set to "Y" in payload |
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `OMX_OM/WritePayload` | Conditional payload in audit log |

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Parameter | Bound From |
|-----------|-----------|
| `$orderRequest` | `orderRequest` concept |
| `$j` | Outer loop index (0-based ParentOU position) |
| `$var` | Internal: `number($j+1)` — 1-based XPath index |
| `$globalVariables` | BE global variables |

### §9.3 JMS / Event Header Fields

| Field | Source | Condition |
|-------|--------|-----------|
| `JMSPriority` | `$orderRequest/OrderPriority` | Always |
| `JMSCorrelationID` | `$orderRequest/OrderData/OMXTrackingId` | Conditional (if present) |
| `OrderID` | `$orderRequest/OrderData/OrderID` | Always |
| `RefID` | `$orderRequest/OrderData/Customer/ParentOU[$var]/Agreement/AgreementId` | Always |
| `UserName` | `$orderRequest/OrderData/User` | If IsEnableUserPass + User present |
| `PassWord` | `$orderRequest/OrderData/Password` | If IsEnableUserPass + Password present |
| `OrderType` | `$orderRequest/OrderData/OrderType` | Always |
| `CES` | "Y" if PassToBDH="true"; else `$orderRequest/OrderData/CES` | Conditional (xsl:choose) |

### §9.6 Core Payload — UserGroupInfo

| Element | Source | Condition |
|---------|--------|-----------|
| `ns:GroupDescription` | `"CUG ID for share plan"` (static) | Always |
| `ns:GroupIdentifier` | `ParentOU[$var]/Agreement/AgreementId` | Always |
| `ns:GroupName` | `ParentOU[$var]/Agreement/AgreementId` | If AgreementId present |
| `ns:GroupType` | `"SUG"` (static) | Always |

### §9.7 Complete Generated XML Example

```xml
<event>
  <JMSPriority>5</JMSPriority>
  <JMSCorrelationID>OMX-TRK-20260914-001</JMSCorrelationID>
  <OrderID>ORD-12345</OrderID>
  <RefID>AGR-001</RefID>
  <OrderType>11001</OrderType>
  <CES>Y</CES>  <!-- if PassToBDH='true' -->
  <payload>
    <ns:UserGroupInfo
      xmlns:ns="www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.UserGroupInfo">
      <ns:GroupDescription>CUG ID for share plan</ns:GroupDescription>
      <ns:GroupIdentifier>AGR-001</ns:GroupIdentifier>
      <ns:GroupName>AGR-001</ns:GroupName>
      <ns:GroupType>SUG</ns:GroupType>
    </ns:UserGroupInfo>
  </payload>
</event>
```

### §9.8 XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:ns="www.tibco.com/plugin/java/xmlSchema/amdocs.csm3g.datatypes.UserGroupInfo"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="j"/>               <!-- 0-based ParentOU index -->
  <xsl:param name="globalVariables"/>
  <xsl:template match="/">
    <createEvent><event>
      <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
      <xsl:if test="$orderRequest/OrderData/OMXTrackingId">
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
      </xsl:if>
      <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
      <xsl:variable name="var" select="number($j+1)"/>
      <RefID><xsl:value-of select="$orderRequest/OrderData/Customer/ParentOU[$var]/Agreement/AgreementId"/></RefID>
      <xsl:if test="$globalVariables/OMX_OM/.../IsEnableUserPass='true'">
        <xsl:if test="$orderRequest/OrderData/User"><UserName>...</UserName></xsl:if>
        <xsl:if test="$orderRequest/OrderData/Password"><PassWord>...</PassWord></xsl:if>
      </xsl:if>
      <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
      <xsl:choose>
        <xsl:when test="$globalVariables/OMX_OM/PassToBDH = 'true'">
          <CES>Y</CES>
        </xsl:when>
        <xsl:otherwise>
          <xsl:if test="$orderRequest/OrderData/CES"><CES>...</CES></xsl:if>
        </xsl:otherwise>
      </xsl:choose>
      <payload><ns:UserGroupInfo>
        <ns:GroupDescription>CUG ID for share plan</ns:GroupDescription>
        <ns:GroupIdentifier><xsl:value-of select="$orderRequest/.../ParentOU[$var]/Agreement/AgreementId"/></ns:GroupIdentifier>
        <xsl:if test="$orderRequest/.../ParentOU[$var]/Agreement/AgreementId">
          <ns:GroupName><xsl:value-of select="$orderRequest/.../ParentOU[$var]/Agreement/AgreementId"/></ns:GroupName>
        </xsl:if>
        <ns:GroupType>SUG</ns:GroupType>
      </ns:UserGroupInfo></payload>
    </event></createEvent>
  </xsl:template>
</xsl:stylesheet>
```

## §10 — XSLT Field Mapping — Output XML Tree Hierarchy

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority                              [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId                   [Conditional: if OMXTrackingId present]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                          [Always]
    ├── RefID                ← ParentOU[$var]/Agreement/AgreementId                     [Always]
    ├── UserName             ← $orderRequest/OrderData/User                             [Conditional: IsEnableUserPass + User present]
    ├── PassWord             ← $orderRequest/OrderData/Password                         [Conditional: IsEnableUserPass + Password present]
    ├── OrderType            ← $orderRequest/OrderData/OrderType                        [Always]
    ├── CES                  ← "Y" (static)                                             [Conditional: PassToBDH='true']
    ├── CES                  ← $orderRequest/OrderData/CES                              [Conditional: otherwise + CES present]
    └── payload                                                                         [Always]
        └── ns:UserGroupInfo  [ns=amdocs.csm3g.datatypes.UserGroupInfo]
            ├── ns:GroupDescription  ← "CUG ID for share plan" (static)                [Always]
            ├── ns:GroupIdentifier   ← ParentOU[$var]/Agreement/AgreementId             [Always]
            ├── ns:GroupName         ← ParentOU[$var]/Agreement/AgreementId             [Conditional: if AgreementId present]
            └── ns:GroupType         ← "SUG" (static)                                  [Always]
```

## §11 — Audit Logging

| Field | Request | Response |
|-------|---------|---------|
| PROCESS_ID | `concat(pid,"_REQ")` | `concat(pid,"_RES")` |
| OPERATION_NAME | `"CCBS_L9_GET_CUGID_BY_AGREEMENTID"` | `"CCBS_L9_GET_CUGID_BY_AGREEMENTID"` |
| AUDIT_TRACE | `"Request Sent for CCBS_GET_CUGID_BY_AGREEMENT_ID"` | `"Response received for CCBS_L9_GET_CUGID_BY_AGREEMENTID"` |

## §12 — Activity Status Management

| Code | When |
|------|------|
| "1" (PROCESSING) | At least one request sent |
| "4" (SKIPPED) | No valid Agreement found, or PreExecCheck failed for all ParentOUs |
| ERROR | Exception → `HandleActivityException` |

## §13 — Exception / Error Handling

`try/catch(Exception ae)` wraps all logic. On exception: `RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "")`.

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `GetXMLForAgreement(orderRequest, refId)` | Serialises a ParentOU Agreement as XML for PreExecCheck XPath — Agreement-scoped variant |
| `GetActivityStatusString` | Maps status code to string |
| `SendDataToDB` | Persists state |
| `SkipActivity` | Advances flow on skip |
| `HandleActivityException` | Handles exceptions |

## §15 — Function Dependency Tree

```text
Request_CCBS_L9_GET_CUGID_BY_AGREEMENTID
├── RuleFunctions.Helpers.GetXMLForAgreement  [per ParentOU, if PreExecCheck present and refId != ""]
├── Event.Ext.sendEventImmediate (CCBS_L9_GET_CUGID_BY_AGREEMENTID)  [per valid ParentOU]
│   └── // ActionRequestEvent commented out
├── Event.Ext.sendEventImmediate (Logger)  [audit]
├── RuleFunctions.Helpers.GetActivityStatusString
├── RuleFunctions.Helpers.SendDataToDB
├── RuleFunctions.Helpers.SkipActivity  [if no requests sent]
└── RuleFunctions.Helpers.HandleActivityException  [on error]
```

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1:** For each ParentOU with a non-empty Agreement.RefId that passes PreExecCheck, query CCBS L9 for the CUG ID associated with the Agreement.
- **R2:** Response handler must append `AgreementParameterInfo[ParamName="CUG ID", ValuesArray=cugId]` to all Agreement.Offers with `SHARE_OFFER_DESC=CUG_ID` AND `Action != REMOVE`.
- **R3:** If the returned `GroupId < 0`, the response must be treated as failed (early return "false").
- **R4:** CES field must be set to "Y" when PassToBDH global variable is "true".

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| ActionRequestEvent commented out — direct sendEventImmediate used; response correlation relies on manual RequestCount | [MEDIUM] | Verify fan-in works for multi-ParentOU orders; test resubmit path |
| Early return "false" when cugId < 0 — bypasses normal fan-in; may cause order stall | [MEDIUM] | Confirm error handling for negative GroupId; consider adding to activity error list |
| debugOut statements left throughout rule and response | [LOW] | Remove before production |

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_L9_GET_CUGID_BY_AGREEMENTID {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CCBS_L9_GET_CUGID_BY_AGREEMENTID";
    orderRequest.ProcessFlow.NextActivityID == "CCBS_L9_GET_CUGID_BY_AGREEMENTID";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      int iPOULen = orderRequest.OrderData.Customer.ParentOU@length;
      boolean isSkipped = true;
      for (int j = 0; j < iPOULen; j++) {
        // refId = ParentOU[j].Agreement.RefId (XPath: if present else "")
        String refId = XPath.evalAsString(/* if Agreement.RefId then Agreement.RefId else "" */);
        // reqSuccess guard
        boolean reqSuccess = false;
        if(!reqSuccess) {
          String chkRes = "false";
          if(PreExecCheck.length > 0 && refId != "") {
            String sXML = RuleFunctions.Helpers.GetXMLForAgreement(orderRequest, refId);
            chkRes = XPath.execute(/* PreExecCheck */, sXML, "ns0=...");
          } else if(PreExecCheck.length <= 0) chkRes = "true";
          if(String.equals(chkRes, "true")) {
            Events.OMConsumers.OMXFM.Request.CCBS_L9_GET_CUGID_BY_AGREEMENTID reqEvent =
              Event.createEvent(/* XSLT: see §9.8 — UserGroupInfo: GroupIdentifier/GroupName=AgreementId, GroupType=SUG, CES conditional */);
            Event.Ext.sendEventImmediate(reqEvent);
            // RuleFunctions.Helpers.IntraActivitySequencing.ActionRequestEvent(reqEvent,orderCurrentActivity); // commented out
            Event.Ext.sendEventImmediate(Event.createEvent(/* Logger: OPERATION_NAME=CCBS_L9_GET_CUGID_BY_AGREEMENTID */));
            if(!isActResub) orderCurrentActivity.RequestCount++;
            isSkipped = false;
          }
        }
      }
      if(!isSkipped) {
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

## §19 — Response Message Rule

### §19.1 Overview

`Response_CCBS_L9_GET_CUGID_BY_AGREEMENTID` retrieves the CUG ID (`GroupId`) from the CCBS response and appends it as an `AgreementParameterInfo` entry on all Agreement.Offers marked with `ExtendedInfo[SHARE_OFFER_DESC=CUG_ID]` that are not being removed. If `GroupId < 0`, returns `"false"` immediately.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Mutated — AgreementParameterInfo appended to matching offers |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_L9_GET_CUGID_BY_AGREEMENTID` | Backend response with UserGroupInfo.GroupId |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | RequestCount for fan-in |

### §19.3 ResponseBase Concept Construction

```text
createObject  [Concepts.FM.Base.ResponseBase]
└── object
    ├── @extId           ← OMXUtils:generateTrackingID()   [Always]  [Note: generated ID, not $eventResponse/@extId]
    ├── ResponseCode     ← $eventResponse/ResponseCode     [Always]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg      [Always]
    ├── CompletionStatus ← $eventResponse/CompletionStatus [Always]
    └── ReferenceId      ← $eventResponse/RefID            [Always]
```

### §19.4 Response Completion Logic

**Early return "false"** if `cugId < 0` (skips all further processing).

**Success XPath:** `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])`

**Fan-in:** `currActivity.RequestCount == successResponseCount` → returns `"true"` / `"false"`

### §19.5 Response Data Write-back

For each ParentOU, iterates `Agreement.Offers[]`. For each offer where:
- `ExtendedInfo[Name="SHARE_OFFER_DESC"]/Value = "CUG_ID"`
- AND `Action != "REMOVE"`

Appends `AgreementParameterInfo` with:

| Field | Value |
|-------|-------|
| `@extId` | `OMXUtils:generateTrackingID()` |
| `ParamName` | `"CUG ID"` (static) |
| `ValuesArray` | `$cugId` (the retrieved GroupId from CCBS) |

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
