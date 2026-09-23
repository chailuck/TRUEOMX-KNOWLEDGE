# Request_CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO

## §1 — Overview & Purpose

Sends `CCBS_UPDATE_ACCOUNT_FIX_INFO` requests to CCBS for each account in the order, updating the collection permanent waiver indicator and waiver expiry date.

- **Waiver code logic**: "89" (waiver=Y), "78" (waiver=N or absent)
- Iterates all accounts; skips accounts already responded with CompletionStatus==2
- Per-account PreExecCheck via `GetXMLForAccount`
- Uses assertEvent + ActionRequestEvent + SendFirstRequestEvent pattern
- Fan-in uses `ActionResponseEvent` (not count-based)

> **Note:** ActivityID = "CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO" but event type = "CCBS_UPDATE_ACCOUNT_FIX_INFO" — naming asymmetry.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule File | Request_CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO.rule |
| Response File | Response_CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO.rulefunction |
| Priority | 5 |
| ForwardChain | true |
| Author | awalia-t420 |
| Target System | CCBS |
| Event Sent | Events.OMConsumers.OMXFM.Request.CCBS_UPDATE_ACCOUNT_FIX_INFO |
| Response Concept | Concepts.FM.Response.CCBS_UpdateAccountFixInfoRes |
| Iteration | Per Account (Account@length) |
| Send Pattern | assertEvent + ActionRequestEvent + SendFirstRequestEvent |
| Fan-in Type | ActionResponseEvent (IntraActivitySequencing) |

---

## §3 — Working Memory — Declared Objects

| Variable | Type Path | Role |
|----------|-----------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Master order request |
| orderCurrentActivity | Concepts.OM.ProcessConfig.Activity | Current activity |

---

## §5 — Execution Flow Diagram

1. If isActResub: PurgePendingRequestsBeforeResubmit
2. Set isSkipped = true
3. For each Account[i]:
   a. Check existing responses: if ReferenceId==refId AND CompletionStatus==2 → skip
   b. PreExecCheck: `GetXMLForAccount(orderRequest, refId)` → XPath.execute
   c. If chkRes=="true": build CCBS_UPDATE_ACCOUNT_FIX_INFO event; assertEvent → ActionRequestEvent; isSkipped=false
4. After loop: if !isSkipped → SendFirstRequestEvent; Status="1"; SendDataToDB; else SkipActivity("4")

---

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Triggered for **CHANGE_PP** when account collection fix info must be updated. Conditional per account.

### §8.2 ESB / JMS Channel Dependencies

| Direction | Event / Queue | Purpose |
|-----------|--------------|---------|
| [OUTBOUND] | CCBS_UPDATE_ACCOUNT_FIX_INFO | Update account collection waiver info |
| [INBOUND] | Response | Update confirmation per account |

### §8.3 Backend API Details

| System | Operation | Root Element | Namespace |
|--------|-----------|-------------|-----------|
| CCBS | UpdateAccountFixInfo | ns:UpdateAccountFixInfoRequest | http://services.omx.truecorp.co.th/FMServices/UpdateAccountFixInfoRequest |

### §8.4 BE Working Memory

| Concept | Fields Read |
|---------|-----------|
| OrderRequest | OrderPriority, OMXTrackingId, OrderID, OrderType, CES, Customer.Account[i].RefId, AccountID, AccountManagementInfo.collectionWaiverInd, collectionWaiverExpDate, AccountActivityInfo.UserText |
| Activity | RequestCount, Response[] (read for skip check), Status (written) |

---

## §9 — Detailed Payload Build

### §9.1 XSLT Parameter Binding

| XSLT Param | Bound From | Notes |
|-----------|-----------|-------|
| orderRequest | orderRequest concept | |
| refId | Account[i].RefId | Per-account iteration key |
| account | Account[i] concept | Current account being updated |

### §9.4 Payload Root Element

```xml
<ns:UpdateAccountFixInfoRequest>
  <ns:AccountIdInfo>
    <ns:AccountId>$account/AccountID</ns:AccountId>      <!-- conditional -->
  </ns:AccountIdInfo>
  <ns:AccountCollectionFixInfo>
    <ns:CollectionPermanentWaiveInd>78 or 89</ns:CollectionPermanentWaiveInd>
    <ns:L9CollWaiverExpDate>...</ns:L9CollWaiverExpDate>  <!-- conditional -->
  </ns:AccountCollectionFixInfo>
  <ns:ActivityInfo>
    <ns:activityReason>CREQ</ns:activityReason>           <!-- static -->
    <ns:userText>...</ns:userText>                        <!-- conditional -->
  </ns:ActivityInfo>
</ns:UpdateAccountFixInfoRequest>
```

### §9.5 CollectionPermanentWaiveInd Decision Table

| Condition | Value | Meaning |
|-----------|-------|---------|
| collectionWaiverInd absent (count=0) | `"78"` | No waiver — default |
| collectionWaiverInd = 'Y' | `"89"` | Permanent waiver granted |
| collectionWaiverInd = 'N' | `"78"` | No waiver explicitly |

### §9.8 XSLT Stylesheet Source

```xml
<xsl:stylesheet
  xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
  xmlns:ns="http://services.omx.truecorp.co.th/FMServices/UpdateAccountFixInfoRequest"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  version="1.0">
  <xsl:param name="orderRequest"/>
  <xsl:param name="refId"/>
  <xsl:param name="account"/>
  <xsl:template match="/">
    <createEvent>
      <event>
        <xsl:attribute name="extId"><xsl:value-of select="OMXUtils:generateTrackingID()"/></xsl:attribute>
        <JMSPriority><xsl:value-of select="$orderRequest/OrderPriority"/></JMSPriority>
        <JMSCorrelationID><xsl:value-of select="$orderRequest/OrderData/OMXTrackingId"/></JMSCorrelationID>
        <OrderID><xsl:value-of select="$orderRequest/OrderData/OrderID"/></OrderID>
        <RefID><xsl:value-of select="$refId"/></RefID>
        <OrderType><xsl:value-of select="$orderRequest/OrderData/OrderType"/></OrderType>
        <xsl:if test="$orderRequest/OrderData/CES">
          <CES><xsl:value-of select="$orderRequest/OrderData/CES"/></CES>
        </xsl:if>
        <payload>
          <ns:UpdateAccountFixInfoRequest>
            <ns:AccountIdInfo>
              <xsl:if test="$account/AccountID">
                <ns:AccountId><xsl:value-of select="$account/AccountID"/></ns:AccountId>
              </xsl:if>
            </ns:AccountIdInfo>
            <ns:AccountCollectionFixInfo>
              <xsl:choose>
                <xsl:when test="count($account/AccountManagementInfo/collectionWaiverInd) = 0">
                  <ns:CollectionPermanentWaiveInd>78</ns:CollectionPermanentWaiveInd>
                </xsl:when>
                <xsl:otherwise>
                  <xsl:choose>
                    <xsl:when test="$account/AccountManagementInfo/collectionWaiverInd = 'Y'">
                      <ns:CollectionPermanentWaiveInd>89</ns:CollectionPermanentWaiveInd>
                    </xsl:when>
                    <xsl:when test="$account/AccountManagementInfo/collectionWaiverInd = 'N'">
                      <ns:CollectionPermanentWaiveInd>78</ns:CollectionPermanentWaiveInd>
                    </xsl:when>
                  </xsl:choose>
                </xsl:otherwise>
              </xsl:choose>
              <xsl:if test="$account/AccountManagementInfo/collectionWaiverExpDate">
                <ns:L9CollWaiverExpDate>
                  <xsl:value-of select="$account/AccountManagementInfo/collectionWaiverExpDate"/>
                </ns:L9CollWaiverExpDate>
              </xsl:if>
            </ns:AccountCollectionFixInfo>
            <ns:ActivityInfo>
              <ns:activityReason>CREQ</ns:activityReason>
              <xsl:if test="$account/AccountActivityInfo/UserText">
                <ns:userText>
                  <xsl:value-of select="$account/AccountActivityInfo/UserText"/>
                </ns:userText>
              </xsl:if>
            </ns:ActivityInfo>
          </ns:UpdateAccountFixInfoRequest>
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
    ├── @extId               ← OMXUtils:generateTrackingID()                     [Always]
    ├── JMSPriority          ← $orderRequest/OrderPriority                       [Always]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId             [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                   [Always]
    ├── RefID                ← $refId                                             [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType                 [Always]
    ├── CES                  ← $orderRequest/OrderData/CES                       [Conditional: if CES]
    └── payload                                                                  [Always]
        └── ns:UpdateAccountFixInfoRequest
            ├── ns:AccountIdInfo
            │   └── ns:AccountId     ← $account/AccountID                       [Conditional: if AccountID]
            ├── ns:AccountCollectionFixInfo
            │   ├── ns:CollectionPermanentWaiveInd ← "89"/"78"                 [Conditional: xsl:choose]
            │   └── ns:L9CollWaiverExpDate ← collectionWaiverExpDate            [Conditional]
            └── ns:ActivityInfo
                ├── ns:activityReason ← "CREQ"                                  [Always]
                └── ns:userText      ← AccountActivityInfo/UserText             [Conditional]
```

---

## §11 — Audit Logging

| Field | Request Value | Response Value |
|-------|--------------|---------------|
| OPERATION_NAME | $orderCurrentActivity/ActivityID (dynamic) | $currActivity/ActivityID (dynamic) |
| AUDIT_TRACE | concat("Request Sent for ", ActivityID) | concat("Response received for ", ActivityID) |
| LOG_LEVEL | INFO | **ERROR** (unusual) |

> Response LOG_LEVEL is ERROR — may cause false alerts. Verify this is intentional.

---

## §12 — Activity Status Management

| Action | Value | When |
|--------|-------|------|
| Status = GetActivityStatusString("1", false) | 1 (Processing) | After any account sends |
| SkipActivity("4") | 4 (Skipped) | All accounts skipped (isSkipped=true) |

---

## §14 — Helper Functions Reference

| Function | Purpose |
|----------|---------|
| RuleFunctions.Helpers.GetXMLForAccount(orderRequest, refId) | Serialize account XML for PreExecCheck |
| IntraActivitySequencing.PurgePendingRequestsBeforeResubmit | Clear pending on resubmit |
| IntraActivitySequencing.ActionRequestEvent(reqEvent, activity) | Register request event |
| IntraActivitySequencing.SendFirstRequestEvent(activity) | Trigger first queued request |
| IntraActivitySequencing.ActionResponseEvent(currActivity) | Fan-in completion check (response) |

---

## §15 — Function Dependency Tree

```text
Request_CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO (rule)
├── IntraActivitySequencing.PurgePendingRequestsBeforeResubmit   [resubmit]
├── RuleFunctions.Helpers.GetXMLForAccount(orderRequest, refId) [per-account PreExecCheck]
├── XPath.execute(PreExecCheck, sXML, ns)
├── Event.createEvent(xslt://CCBS_UPDATE_ACCOUNT_FIX_INFO)      [per account]
├── Event.assertEvent(reqEvent)
├── IntraActivitySequencing.ActionRequestEvent(reqEvent, activity)
├── Event.Ext.sendEventImmediate(xslt://Logger)
├── IntraActivitySequencing.SendFirstRequestEvent(activity)
├── RuleFunctions.Helpers.GetActivityStatusString("1", false)
├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
├── RuleFunctions.Helpers.SkipActivity(...)
└── RuleFunctions.Helpers.HandleActivityException(...)

Response_CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO (rulefunction)
├── Instance.createInstance(xslt://CCBS_UpdateAccountFixInfoRes)
├── Event.Ext.sendEventImmediate(xslt://Logger)       [LOG_LEVEL=ERROR]
└── IntraActivitySequencing.ActionResponseEvent(currActivity)
```

---

## §17 — Migration Notes & Recommendations

**R1**: Must iterate all accounts and send UpdateAccountFixInfo per account with correct waiver code.
**R2**: Must skip accounts already responded with CompletionStatus==2.
**R3**: CollectionPermanentWaiveInd must follow Y→89 / N→78 / absent→78 mapping.
**R4**: Fan-in uses ActionResponseEvent, not count-based check.

| Risk | Severity | Mitigation |
|------|----------|-----------|
| ActivityID ≠ event name (ACCT_COLLECTION vs ACCOUNT_FIX) | [MEDIUM] | Align naming or document discrepancy |
| Response LOG_LEVEL = ERROR | [MEDIUM] | Review log alerting; change to INFO if causing false alerts |
| xsl:choose no fallback for collectionWaiverInd values other than Y/N | [LOW] | Add xsl:otherwise or validate input |

---

## §18 — Full Source Code (Request Rule)

```java
/**
 * Request_CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO.rule
 * @author awalia-t420
 */
rule Rules.OMConsumers.OMXFM.Request.Request_CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO {
  attribute { priority=5; forwardChain=true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when { /* standard OMXFM conditions for CCBS_UPDATE_ACCT_COLLECTION_FIX_INFO */ }
  then {
    boolean isActResub = (orderCurrentActivity.RequestCount > 0 && orderRequest.IsOrderResubmitted);
    try {
      Concepts.OM.ProcessConfig.Activity nextAct =
          Instance.getByExtIdByUri(orderRequest.ProcessFlow.NextActivityName, ".../Activity");
      int iAcctLen = orderRequest.OrderData.Customer.Account@length;
      if (isActResub) IntraActivitySequencing.PurgePendingRequestsBeforeResubmit(orderCurrentActivity);
      boolean isSkipped = true;
      for (int i = 0; i < iAcctLen; i++) {
        String refId = orderRequest.OrderData.Customer.Account[i].RefId;
        boolean reqSuccess = false;
        for (int iResp = 0; iResp < orderCurrentActivity.Response@length; iResp++)
          if (String.equals(Response[iResp].ReferenceId, refId) && Response[iResp].CompletionStatus == 2)
            reqSuccess = true;
        if (!reqSuccess) {
          String chkRes = "true";
          if (String.length(nextAct.PreExecCheck) > 0) {
            String sXML = RuleFunctions.Helpers.GetXMLForAccount(orderRequest, refId);
            chkRes = XPath.execute("/("+nextAct.PreExecCheck+")", sXML, "ns0=...");
          }
          if (String.equals(chkRes, "true")) {
            Concepts.OrderRequest.OrderElements.Account account = orderRequest.OrderData.Customer.Account[i];
            Events.OMConsumers.OMXFM.Request.CCBS_UPDATE_ACCOUNT_FIX_INFO reqEvent =
                Event.createEvent("xslt://{{/Events/.../CCBS_UPDATE_ACCOUNT_FIX_INFO}}"
                  /* [XSLT builds UpdateAccountFixInfoRequest — see §9.8 for payload] */
                );
            Event.assertEvent(reqEvent);
            IntraActivitySequencing.ActionRequestEvent(reqEvent, orderCurrentActivity);
            Event.Ext.sendEventImmediate(Event.createEvent("xslt://{{Logger}}..."));
            isSkipped = false;
          }
        }
      }
      if (!isSkipped) {
        IntraActivitySequencing.SendFirstRequestEvent(orderCurrentActivity);
        orderCurrentActivity.Status = GetActivityStatusString("1", false);
        SendDataToDB(orderRequest);
      } else SkipActivity(orderRequest, orderCurrentActivity, "4");
    } catch (Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §19 — Response Message Rule

### §19.1 Overview

Parses CCBS response into `CCBS_UpdateAccountFixInfoRes`, logs at ERROR level, then uses `ActionResponseEvent` for fan-in.

### §19.2 Scope Variables

| Variable | Type Path | Role |
|----------|-----------|------|
| orderRequest | Concepts.OrderRequest.OrderRequest | Master order request |
| eventResponse | Events.OMConsumers.OMXFM.Response.CCBS_UPDATE_ACCOUNT_FIX_INFO | Raw CCBS response |
| currActivity | Concepts.OM.ProcessConfig.Activity | Current activity |

### §19.3 ResponseBase Concept

```text
createObject
└── object
    ├── @extId           ← OMXUtils:generateTrackingID()       [Always]
    ├── ResponseCode     ← $eventResponse/ResponseCode          [Conditional]
    ├── ResponseMessage  ← $eventResponse/ResponseMsg           [Conditional]
    ├── CompletionStatus ← $eventResponse/CompletionStatus      [Conditional]
    └── ReferenceId      ← $eventResponse/RefID                 [Conditional]
```

### §19.4 Fan-in Completion Logic

Uses `IntraActivitySequencing.ActionResponseEvent(currActivity)` — returns "true" when all queued requests have received responses.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
