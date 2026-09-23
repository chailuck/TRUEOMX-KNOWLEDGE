# Request_CCBS_CREATE_MEMO

> Creates a memo record in CCBS for Account, ParentOU Subscriber, or ChildOU Subscriber entities — triggered per order line with valid UserText.

---

## §1 Overview & Purpose

This rule fires when the next activity in the order's ProcessFlow is `CCBS_CREATE_MEMO`. It iterates over three entity types — **Accounts**, **ParentOU Subscribers**, and **ChildOU Subscribers** — and for each entity where the PreExecCheck passes and a `UserText` note is present (and not already successfully responded), it sends a JMS request to CCBS to create a memo record.

The memo captures the `UserText` from the order, appends the SOC of any active SBM DataPack offer (ServiceType=86 FE/BRMS), and tags the entry with the order channel. Entity type and entity ID selection differ between the three variants.

---

## §2 Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CREATE_MEMO` |
| Priority | 5 |
| ForwardChain | true |
| Author | sakarin-radchapunya |
| Backend system | CCBS |
| Event type | `Events.OMConsumers.OMXFM.Request.CCBS_CREATE_MEMO` |
| Channel | `/Channels/OMXFMConnectionRequest` |
| Destination | `CCBS_CREATE_MEMO` |
| Response rulefunction | `RuleFunctions.OrderResponse.Response_CCBS_CREATE_MEMO` |
| XSLT variants | 3 (Account, ParentOU Subscriber, ChildOU Subscriber) |

---

## §3 Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order request context |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Current activity node (status, RequestCount, Response array) |

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Matches the specific activity instance |
| 2 | `orderCurrentActivity.ActivityID == "CCBS_CREATE_MEMO"` | Ensures this rule handles only CREATE_MEMO |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "CCBS_CREATE_MEMO"` | Double-check flow pointer alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fire when activity is waiting |

---

## §5 Execution Flow Diagram

```
1. Load PreExecCheck XPath from nextAct
2. Account loop — for each Account[a]:
   2a. Evaluate PreExecCheck via GetXMLForAccount
   2b. Skip if already responded (CompletionStatus=2 + RefId match)
   2c. Skip if AccountActivityInfo.UserText is null
   2d. Build & send Account Variant XSLT event to CCBS
   2e. Send audit log event via Logger
   2f. Increment RequestCount (if not resubmit)
3. ParentOU Subscriber loop — for each ParentOU[i].Subscriber[j]:
   3a. Evaluate PreExecCheck via GetXMLForSubscriber
   3b. Guard: not already responded + UserText present
   3c. Extract SOC from ServiceType=86 FE/BRMS offer
   3d. Build & send ParentOU Subscriber Variant XSLT event
   3e. Audit log + increment RequestCount
4. ChildOU Subscriber loop — for each ParentOU[i].ChildOU[k].Subscriber[j]:
   4a-4e. Same pattern, using GetXMLForSubscriberInChildOU
5. If any entity sent → Status="1" + SendDataToDB
   Else → SkipActivity(..., "4")
6. On exception → HandleActivityException
```

---

## §6 Rule Action (THEN) — Step-by-Step Logic

| Step | Action | Detail |
|------|--------|--------|
| 1 | Resubmit flag | `isActResub = (RequestCount>0 && IsOrderResubmitted)` |
| 2 | Load PreExecCheck | Reads `nextAct.PreExecCheck` from Activity concept |
| 3 | Account loop | Loops `iAccountLen` times; calls `GetXMLForAccount` |
| 4 | Guard: no dup response | Checks `Response[].ReferenceId == refAccId && CompletionStatus==2` |
| 5 | Guard: UserText present | `AccountActivityInfo != null && UserText != null` |
| 6 | Send Account event | Account Variant XSLT; `Event.Ext.sendEventImmediate` |
| 7 | Audit log | Logger event per entity with RefId in AUDIT_TRACE |
| 8 | ParentOU Subscriber loop | Nested: ParentOU → Subscriber; `GetXMLForSubscriber` |
| 9 | Send POU Subscriber event | SOC extracted from ServiceType=86 FE/BRMS offer |
| 10 | ChildOU Subscriber loop | Nested: ParentOU → ChildOU → Subscriber |
| 11 | Send ChildOU event | Same as POU Sub variant but from ChildOU path |
| 12 | Activity status | If any sent: Status="1"; else SkipActivity("4") |
| 13 | Exception | `HandleActivityException(orderRequest, activity, ae, "")` |

---

## §7 Data Extraction

| Field | Source | Notes |
|-------|--------|-------|
| `entityId` (Account) | `AccountID` if ENTITY_TYPE_ID=2, else `BillingArrangementId` | xsl:choose on ENTITY_TYPE_ID=2 |
| `entityTypeId` (Account) | ExtendedInfo[ENTITY_TYPE_ID]/Value if present, else "3" | "3" = Billing Arrangement default |
| `entityId` (Subscriber) | `SubscriberId` | Always for subscriber entities |
| `entityTypeId` (Subscriber) | Static `"6"` | Subscriber entity type in CCBS |
| `soc` | `SubscriberOffers[ServiceType=86 and FE_OR_CCBS=BRMS\|FE]/OfferName` | SBM DataPack offer name |
| `memoText` | `concat(UserText, [" soc= ", soc,] " channel:[ ", Channel, " ]")` | SOC appended only when soc != '' |
| `memoTypeId` | ExtendedInfo[Name="MEMO_TYPE_ID"]/Value | Required on Account/Subscriber |

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

This FM is a utility step invoked from any order that includes the `CREATE_MEMO` process step. Common triggers: standalone CREATE_MEMO orders, and as a sub-step in SBM data pack / billing cycle change orders requiring user notes stored in CCBS.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Event type |
|-----------|---------|-------------|------------|
| [OUTBOUND] | `/Channels/OMXFMConnectionRequest` | `CCBS_CREATE_MEMO` | `Events.OMConsumers.OMXFM.Request.CCBS_CREATE_MEMO` |
| [INBOUND] | `/Channels/OMXFMConnectionResponse` | `CCBS_CREATE_MEMO` | `Events.OMConsumers.OMXFM.Response.CCBS_CREATE_MEMO` |
| [OUTBOUND] | Logger channel | Logger event | `Events.OMConsumers.OMXESB.Logger` |

### §8.3 Backend API Details

| System | Operation | Schema | Correlation |
|--------|-----------|--------|-------------|
| CCBS | createMemo | `OMX-COMMON/_SharedResources/Schemas/OMX/ESB/CreateMemo.xsd` | JMSCorrelationID = OMXTrackingId; RefID echoed in response |

### §8.4 BE Working Memory Dependencies

| Field | Read/Write | Purpose |
|-------|-----------|---------|
| `orderCurrentActivity.Status` | Write | Set to "1" (in-progress) or skip "4" |
| `orderCurrentActivity.RequestCount` | Read/Write | Incremented per entity send; fan-in denominator |
| `orderCurrentActivity.Response[]` | Read | Duplicate-response guard |
| `orderCurrentActivity.PreExecCheck` | Read | XPath gate evaluated per entity |
| `orderRequest.OrderData.Customer.Account[].AccountActivityInfo.UserText` | Read | Memo text for Account entities |
| `orderRequest.OrderData.Customer.ParentOU[].Subscriber[].SubscriberActivityInfo.UserText` | Read | Memo text for Subscriber entities |
| `orderRequest.OrderData.Customer.ResponseCode` | Write (response) | Updated in response handler |

### §8.5 ExtendedInfo Fields Required

| Name | Required? | Where used |
|------|-----------|-----------|
| `ENTITY_TYPE_ID` | [Conditional] | Account Variant: if =2 use AccountID; else BillingArrangementId |
| `MEMO_TYPE_ID` | [Required] | All variants: maps to `ns2:memoTypeId` |
| `FE_OR_CCBS` | [Conditional] | Subscriber variants: identifies BRMS/FE ServiceType=86 offer for SOC |

### §8.6 Global Variable Dependencies

| Path | Purpose |
|------|---------|
| `$globalVariables/OMX_OM/Rules/OMConsumers/OMXFM/Request/IsEnableUserPass` | If 'true' include UserName/PassWord in request |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` | TARGET_SYSTEM in audit log |
| `$globalVariables/OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL for audit |
| `$globalVariables/OMX_OM/WritePayload` | If "true" include payload in audit log |

---

## §9 Detailed Payload Build

### §9.1 XSLT Parameter Binding

| Parameter | Variant(s) | Source |
|-----------|-----------|--------|
| `$orderRequest` | All | Full OrderRequest concept |
| `$refAccId` | Account | `Account[a].RefId` |
| `$a` | Account | 0-based loop index; `$iAccount = number($a)+1` |
| `$refId` | POU Sub, COU Sub | Subscriber RefId |
| `$i`, `$j` | POU Sub | 0-based ParentOU and Subscriber indices |
| `$i`, `$k`, `$j` | COU Sub | 0-based ParentOU, ChildOU, Subscriber indices |
| `$globalVariables` | All | Global config |
| `$soc` | POU Sub, COU Sub | Pre-extracted OfferName from ServiceType=86 FE/BRMS offer |

### §9.2 Core Payload Fields

| XML Element | Account Variant | Subscriber Variants |
|-------------|----------------|---------------------|
| `ns2:entityId` | AccountID (if ENTITY_TYPE_ID=2) else BillingArrangementId | SubscriberId (always) |
| `ns2:entityTypeId` | ExtendedInfo[ENTITY_TYPE_ID]/Value else "3" | "6" (static) |
| `ns2:memoText` | `concat(UserText, "channel:[ ", Channel, " ]")` | `concat(UserText, [" soc= ", soc,] "channel:[ ", Channel, " ]")` |
| `ns2:memoTypeId` | ExtendedInfo[MEMO_TYPE_ID]/Value | ExtendedInfo[MEMO_TYPE_ID]/Value |

### §9.7 Complete Generated XML Example (Account Variant, ENTITY_TYPE_ID=2)

```xml
<createEvent>
  <event>
    <JMSPriority>5</JMSPriority>
    <JMSCorrelationID>OMX-TRK-20241001-001</JMSCorrelationID>
    <OrderID>ORD-98765</OrderID>
    <RefID>ACC-123</RefID>
    <OrderType>23</OrderType>
    <CES>PORTAL</CES>
    <payload>
      <ns1:createMemoRequest>
        <ns2:createMemo>
          <ns2:entityId>10001234</ns2:entityId>
          <ns2:entityTypeId>2</ns2:entityTypeId>
          <ns2:memoText>Customer requested plan change channel:[ PORTAL ]</ns2:memoText>
          <ns2:memoTypeId>90051</ns2:memoTypeId>
        </ns2:createMemo>
      </ns1:createMemoRequest>
    </payload>
  </event>
</createEvent>
```

### §9.8 XSLT Field Mapping — Output XML Tree

**Account Variant ①**

```text
createEvent
└── event
    ├── JMSPriority          ← $orderRequest/OrderPriority          [Conditional: if OrderPriority]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId [Conditional: if OMXTrackingId]
    ├── OrderID              ← $orderRequest/OrderData/OrderID       [Conditional: if OrderID]
    ├── RefID                ← $refAccId                             [Always]
    ├── UserName             ← $orderRequest/OrderData/User          [Credential-gated: IsEnableUserPass='true']
    ├── PassWord             ← $orderRequest/OrderData/Password      [Credential-gated: IsEnableUserPass='true']
    ├── OrderType            ← $orderRequest/OrderData/OrderType     [Conditional: if OrderType]
    ├── CES                  ← $orderRequest/OrderData/CES           [Conditional: if CES]
    └── payload
        └── ns1:createMemoRequest
            └── ns2:createMemo
                ├── ns2:entityId  ← Account[$iAccount]/AccountID           [Conditional: ENTITY_TYPE_ID='2']
                ├── ns2:entityId  ← Account[$iAccount]/BillingArrangementId [Conditional: otherwise]
                ├── ns2:entityTypeId ← ExtendedInfo[ENTITY_TYPE_ID]/Value  [Conditional: ENTITY_TYPE_ID present]
                ├── ns2:entityTypeId ← "3"                                 [Conditional: otherwise]
                ├── ns2:memoText  ← concat(UserText, "channel:[ ", Channel, " ]") [Always]
                └── ns2:memoTypeId ← ExtendedInfo[MEMO_TYPE_ID]/Value     [Always]
```

**Subscriber Variants ②③ — Differences from Account Variant**

```text
createEvent
└── event
    ├── RefID                ← $refId (Subscriber RefId)             [Always]
    └── payload
        └── ns1:createMemoRequest
            └── ns2:createMemo
                ├── ns2:entityId     ← Subscriber/SubscriberId               [Always]
                ├── ns2:entityTypeId ← "6" (static)                          [Always]
                ├── ns2:memoText     ← concat(UserText," soc= ",soc," channel:[ ",Channel," ]") [Conditional: soc!='']
                ├── ns2:memoText     ← concat(UserText," channel:[ ",Channel," ]")              [Conditional: otherwise]
                └── ns2:memoTypeId   ← ExtendedInfo[MEMO_TYPE_ID]/Value      [Always]
```

**ChildOU Subscriber Variant ③ additional variables:**
```text
$i/$k/$j → $iPOU=(number($i)+1), $kCOU=(number($k)+1), $kCSUB=(number($j)+1)
Path: ParentOU[$iPOU]/ChildOU[$kCOU]/Subscriber[$kCSUB]/...
```

---

## §11 Audit Logging

| Audit Field | Value |
|-------------|-------|
| `ESBUUID` | `$orderRequest/OrderData/OMXTrackingId` (conditional) |
| `PROCESS_ID` | `concat($pid, "_REQ")` |
| `COMPONENT_NAME` | `$globalVariables/OMX_COMMON/Component_Name/OMX_CEP` |
| `OPERATION_NAME` | `"CCBS_CREATE_MEMO"` (static) |
| `TARGET_SYSTEM` | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| `LOG_LEVEL` | INFO |
| `AUDIT_TRACE` | `concat("Request Sent for RefId: ", $refAccId/$refId)` |
| `AUDIT_TS` | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| `payload/ns:ServicePayload` | Copy of `$reqEvent` — conditional on WritePayload="true" |

---

## §12 Activity Status Management

| Condition | Status | Function |
|-----------|--------|----------|
| At least one entity sent | `"1"` (In-Progress) | `GetActivityStatusString("1", false)` + `SendDataToDB` |
| No entity matched (all skipped) | Skipped (`"4"`) | `SkipActivity(orderRequest, activity, "4")` |
| Response: all requests succeeded | Completed | `return "true"` from response rulefunction |
| Response: some failed/pending | Pending | `return "false"` from response rulefunction |

---

## §13 Exception / Error Handling

The entire THEN block is wrapped in `try { ... } catch(Exception ae)`. On exception:

```java
RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
```

---

## §14 Helper Functions Reference

| Function | Signature | Purpose |
|----------|-----------|---------|
| `GetXMLForAccount` | `String(orderRequest, refAccId)` | Serializes Account context to XML for XPath evaluation |
| `GetXMLForSubscriber` | `String(orderRequest, refId)` | Serializes ParentOU Subscriber context to XML |
| `GetXMLForSubscriberInChildOU` | `String(orderRequest, refId, pouRefId)` | Serializes ChildOU Subscriber context |
| `AllowWriteLog` | `boolean(orderType)` | Gate for audit logging by order type |
| `GetActivityStatusString` | `String(statusCode, isError)` | Returns status string from code |
| `SendDataToDB` | `void(orderRequest)` | Persists order state to DB |
| `SkipActivity` | `void(orderRequest, activity, code)` | Marks activity skipped and advances flow |
| `HandleActivityException` | `void(orderRequest, activity, exception, msg)` | Standard exception handler |

---

## §15 Function Dependency Tree

```text
Request_CCBS_CREATE_MEMO
├── RuleFunctions.Helpers.GetXMLForAccount(orderRequest, refAccId)
├── RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)
├── RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, pouRefId)
├── XPath.execute(chkXPath, sXML, ...)           [PreExecCheck evaluation]
├── Event.createEvent("xslt://CCBS_CREATE_MEMO") [×3 variants]
│   └── Event.Ext.sendEventImmediate(reqEvent)
├── RuleFunctions.Helpers.AllowWriteLog(orderType)
│   └── Event.createEvent("xslt://Logger")
│       └── Event.Ext.sendEventImmediate(logEvent)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")
└── RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")
```

---

## §16 Concept Definitions Referenced

| Concept | Key fields used |
|---------|----------------|
| `Concepts.OrderRequest.OrderRequest` | Account[].AccountID, BillingArrangementId, AccountActivityInfo.UserText, ExtendedInfo[ENTITY_TYPE_ID/MEMO_TYPE_ID/FE_OR_CCBS]; ParentOU[].Subscriber[].SubscriberId, SubscriberActivityInfo.UserText, SubscriberOffers[ServiceType=86] |
| `Concepts.OM.ProcessConfig.Activity` | extId, ActivityID, Status, RequestCount, Response[], PreExecCheck |
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId |

---

## §17 Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|------------|
| R1 | Must support three entity types: Account, ParentOU Subscriber, ChildOU Subscriber — each with independent PreExecCheck evaluation |
| R2 | Entity type ID must be dynamic: ENTITY_TYPE_ID=2 → AccountID; else BillingArrangementId; subscribers always "6" |
| R3 | Memo text must append SOC of active SBM DataPack (ServiceType=86 FE/BRMS) when present for subscriber entities |
| R4 | Duplicate suppression: skip if CompletionStatus=2 + RefId already in Response[] |
| R5 | Fan-in: all RequestCount sends must return ResponseCode ending "000" |
| R6 | Audit logging must capture RefId per entity |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Three separate XSLT variants increase maintenance burden | [MEDIUM] | Consolidate into single parameterized template in microservice |
| 0-based index arithmetic `(number($a)+1)` is error-prone | [MEDIUM] | Use 1-based indices or list APIs in target platform |
| No guard on MEMO_TYPE_ID being absent — sends blank memoTypeId | [HIGH] | Add validation; return early if MEMO_TYPE_ID missing |
| SOC extraction uses first match of ServiceType=86 FE/BRMS — multiple could exist | [MEDIUM] | Clarify: should all matching SOCs be appended or only first? |
| Fan-in race on resubmit — `isActResub` guard preserves count | [MEDIUM] | Verify resubmit handling in target platform |

---

## §18 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_CREATE_MEMO {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "CCBS_CREATE_MEMO";
    orderRequest.ProcessFlow.NextActivityID == "CCBS_CREATE_MEMO";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount>0 && orderRequest.IsOrderResubmitted);
    try {
      String sXML = "";
      boolean isSkipped = true;
      Activity nextAct = Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, "/Concepts/OM/ProcessConfig/Activity");
      String chkXPath = nextAct.PreExecCheck;
      int iAccountLen = orderRequest.OrderData.Customer.Account@length;

      // Account loop
      for(int a=0; a < iAccountLen; a++) {
        String refAccId = orderRequest.OrderData.Customer.Account[a].RefId;
        if(String.length(nextAct.PreExecCheck) > 0) {
          sXML = RuleFunctions.Helpers.GetXMLForAccount(orderRequest, refAccId);
          chkRes = XPath.execute("/("+chkXPath+")", sXML, ...);
        }
        if(String.equals(chkRes, "true")) {
          // duplicate-response guard...
          if(!reqSuccess && AccountActivityInfo != null && UserText != null) {
            /* Account Variant XSLT — see §9.8 Variant ①
               Builds ns2:createMemo with entityId=AccountID|BillingArrangementId,
               entityTypeId from ENTITY_TYPE_ID|"3", memoText=UserText+channel */
            Event.Ext.sendEventImmediate(reqEvent);
            // Audit log (§11)
            if(!isActResub) orderCurrentActivity.RequestCount++;
            isSkipped = false;
          }
        }
      }

      // ParentOU Subscriber loop
      for(int i=0; i < iPOULen; i++) {
        for(int j=0; j < iSubscriberLen; j++) {
          if(String.equals(chkRes, "true") && !reqSuccess && UserText != null) {
            /* ParentOU Subscriber Variant XSLT — see §9.8 Variant ②
               entityId=SubscriberId, entityTypeId="6",
               memoText=UserText[+soc]+channel */
            Event.Ext.sendEventImmediate(reqEvent);
            if(!isActResub) orderCurrentActivity.RequestCount++;
            isSkipped = false;
          }
        }
        // ChildOU Subscriber loop
        for(int k=0; k < iCOULen; k++) {
          for(int j=0; j < iCSubscriberLen; j++) {
            if(String.equals(chkRes, "true") && !reqSuccess && UserText != null) {
              /* ChildOU Subscriber Variant XSLT — see §9.8 Variant ③
                 Path: ParentOU[$iPOU]/ChildOU[$kCOU]/Subscriber[$kCSUB] */
              Event.Ext.sendEventImmediate(reqEvent);
              if(!isActResub) orderCurrentActivity.RequestCount++;
              isSkipped = false;
            }
          }
        }
      }

      if(!isSkipped) {
        orderCurrentActivity.Status = RuleFunctions.Helpers.GetActivityStatusString("1", false);
        RuleFunctions.Helpers.SendDataToDB(orderRequest);
      } else
        RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
    } catch(Exception ae) {
      RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

---

## §19 Response Message Rule

### §19.1 Overview

`Response_CCBS_CREATE_MEMO` handles the CCBS reply for each entity's memo creation. It builds a `ResponseBase` concept, appends it to the activity's response array, updates the order's ResponseCode/ResponseMsg, emits a response audit log, then evaluates fan-in completion.

### §19.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Order context for status updates |
| `eventResponse` | `Events.OMConsumers.OMXFM.Response.CCBS_CREATE_MEMO` | CCBS response (ResponseCode, ResponseMsg, CompletionStatus, RefID) |
| `currActivity` | `Concepts.OM.ProcessConfig.Activity` | Fan-in denominator (RequestCount) |

### §19.3 ResponseBase Concept Construction

```text
createObject
└── object
    ├── @extId           ← OMXUtils:generateTrackingID()     [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode       [Conditional: if ResponseCode]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg        [Conditional: if ResponseMsg]
    ├── CompletionStatus ← $eventResponse/CompletionStatus   [Conditional: if CompletionStatus]
    └── ReferenceId      ← $eventResponse/RefID              [Conditional: if RefID]
```

After construction, appended to `currActivity.Response[]`; order's `ResponseCode`/`ResponseMsg` updated.

### §19.4 Response Completion Logic

| Field | Value |
|-------|-------|
| Success XPath | `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])` |
| Fan-in condition | `currActivity.RequestCount == successResponseCount` |
| Return "true" | All RequestCount parallel sends returned ResponseCode ending "000" |
| Return "false" | Some responses not yet received or failed |

### §19.5 Response Audit Logging

| Audit Field | Value |
|-------------|-------|
| `PROCESS_ID` | `concat($pid, "_RES")` |
| `OPERATION_NAME` | `"CCBS_CREATE_MEMO"` (static) |
| `TARGET_SYSTEM` | `$globalVariables/OMX_COMMON/Component_Name/OMX_FM` |
| `AUDIT_TRACE` | `"Response received for CCBS_CREATE_MEMO"` (static) |
| `AUDIT_TS` | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| `payload/ns:ServicePayload` | Copy of `$eventResponse` — conditional on WritePayload="true" |

### §19.6 Response XSLT Source (ResponseBase)

```xml
<xsl:stylesheet xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:param name="eventResponse"/>
  <xsl:template match="/">
    <createObject>
      <object extId="{OMXUtils:generateTrackingID()}">
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
