# Request_MCS_SUBSCRIPTION_MARKUSED

Per-subscriber MCS mark-used request — reads IMEI_MLDD from prior FM; 5-level pack_code waterfall; response handles code 135 (already-used) and 200 (success) with complex write-back to working memory.

**Target:** MCS (Subscription Engine) | **Pattern:** Per-subscriber parallel fan-out | **forwardChain:** true | **Author:** Chayatorn Pan.

---

## §1 Overview & Purpose

Marks a subscriber's data pack as "used" in the MCS subscription engine. Fires per-subscriber (POU + COU) in parallel. Reads the `FLOW_ID` from subscriber SubscriberOffers (falling back to the `DEFAULT_FLOW_ID` activity parameter), resolves the MCS pack code via a 5-level ServiceType waterfall, and reads the device IMEI previously written by `MLDD_GET_SUB_DATA`. The response handler has three distinct branches: code 135 (already-marked-used), code 200 (success), and CHECK_PACK_ALLOW_FLG='N' write-back.

> **[BUG — MEDIUM] COU subscribers excluded from response processing:** The request sends events for both POU and COU subscribers. The isMarkUsed (135) and isSuccess (200) response handlers only iterate POU → Subscriber — no ChildOU loop. COU responses contribute to fan-in but do NOT get MCS_IGNORE flag, BRMS_ADD offer, or EXP_TYPE/MCS_EXP_DATE_VALUE updates.

> **[TYPO] XML root element name:** The payload root is `ns:SubscriptionMarkuesdRequest` — "Markuesd" (letters transposed from "Markused"). Preserved in schema; must be kept exactly when migrating.

> **[INCONSISTENCY] POU vs COU XSLT extra field order:** POU XSLT emits IMEI extra **before** CHECK_PACK_ALLOW_FLG; COU XSLT emits them in the **opposite order**. Content identical; ordering may matter to MCS.

> **Data dependency on MLDD_GET_SUB_DATA:** This FM reads `subscriber.ExtendedInfo[Name='IMEI_MLDD']/Value` which is only populated after MLDD_GET_SUB_DATA has run. The two FMs are sequentially coupled.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `Request_MCS_SUBSCRIPTION_MARKUSED.rule` | 130 lines |
| Response file | `Response_MCS_SUBSCRIPTION_MARKUSED.rulefunction` | 132 lines |
| Author | Chayatorn Pan. | |
| forwardChain | true | |
| Request event | `Events.OMConsumers.OMXFM.Request.MCS_SUBSCRIPTION_MARKUSED` | One per subscriber |
| Response event | `Events.OMConsumers.OMXFM.Response.MCS_SUBSCRIPTION_MARKUSED` | |
| Request schema NS (ns) | `http://www.tibco.com/schemas/OMX-COMMON/_SharedResources/Schemas/ESB/MCS/SubscriptionMarkused.xsd` | |
| Response schema NS (xsd2) | Same schema | |
| Response concept | `Concepts.FM.Base.ResponseBase` | extId passed as BE param (not in XSLT) |
| extId on request event | `OMXUtils:generateTrackingID()` (in XSLT) | Always |
| extId on ResponseBase | `OMXUtils.generateTrackingID()` (in BE, passed as $extId) | Unique pattern |
| reqSuccess dedup key | `refId` (subscriber RefId) | |
| Activity parameter | `DEFAULT_FLOW_ID` via `GetActivityParameterValueFromKey` | **First FM to use activity parameter** |
| Fan-out | Parallel — `Event.Ext.sendEventImmediate` per subscriber (POU + COU) | |
| Fan-in | Standard "000" count == RequestCount | |
| Resubmit handler | None — isActResub gates RequestCount++ only | |
| Credential gate | None | |
| Request audit gate | `AllowWriteLog(OrderData.OrderType)` | Conditional |
| Response audit gate | Unconditional | Always sent — unlike request |

---

## §3 Working Memory — Declared Objects

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | Subscribers; ExtendedInfo; write-back targets |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity | DEFAULT_FLOW_ID parameter; RequestCount++; Response[] |
| `nextAct` | Concepts.OM.ProcessConfig.Activity | Looked up live to read PreExecCheck — unusual! |

> **nextAct live lookup:** `Instance.getByExtIdByUri(ProcessFlow.NextActivityName, Activity)` — retrieves the Activity concept to read its PreExecCheck field. Unlike most FMs that use `orderCurrentActivity.PreExecCheck` directly.

---

## §4 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "MCS_SUBSCRIPTION_MARKUSED"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "MCS_SUBSCRIPTION_MARKUSED"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §5 Execution Flow

1. isActResub flag; nextAct live lookup; DEFAULT_FLOW_ID from `GetActivityParameterValueFromKey`; isSkipped=true
2. **POU Subscribers loop** — for each POU × Subscriber:
   - reqSuccess check; PreExecCheck via `GetXMLForSubscriber` + `nextAct.PreExecCheck`
   - Extract: transaction_id, flow_id, msisdn, pack_code, imei, recurringSoc, mcsCorrelationId
   - Send event immediately; conditional audit; RequestCount++; isSkipped=false
3. **COU Subscribers loop** — for each POU × COU × Subscriber:
   - Same with `GetXMLForSubscriberInChildOU`; same extraction and send pattern
4. **Status:** if !isSkipped → `GetActivityStatusString("1")` + `SendDataToDB`; else → `SkipActivity("4")`
5. **Exception:** catch → `HandleActivityException`

---

## §6 Rule Action (THEN) — Per-Subscriber Data Extraction

### §6.1 Activity Parameter: DEFAULT_FLOW_ID

```java
String defaultFlowId = RuleFunctions.Helpers.GetActivityParameterValueFromKey(orderCurrentActivity, "DEFAULT_FLOW_ID");
```

### §6.2 flow_id Resolution (subscriber-level, with fallback)

```xpath
if (exists($subscriber/SubscriberOffers/ExtendedInfo[Name='FLOW_ID']/Value))
    then $subscriber/SubscriberOffers/ExtendedInfo[Name='FLOW_ID']/Value
else $defaultFlowId
```

### §6.3 pack_code Resolution (5-level ServiceType waterfall)

| Priority | ServiceType | Source Field | FE_OR_CCBS filter |
|----------|-------------|--------------|-------------------|
| 1 | 86 | ExtendedInfo[MCS_PACKCODE]/Value | 'FE' or 'BRMS' |
| 2 | 99 | ExtendedInfo[MCS_PACKCODE]/Value | 'FE' or 'BRMS' |
| 3 | 69 | ExtendedInfo[MCS_PACKCODE]/Value | 'FE' or 'BRMS' |
| 4 | 88 | ExtendedInfo[MCS_PACKCODE]/Value | 'FE' or 'BRMS' |
| 5 (fallback) | 69 | OfferName | 'FE' only |

> Note: XPath searches across all POU subscribers, not just the current subscriber being processed. Verify this is intentional.

### §6.4 IMEI Read-back from Prior FM

```java
String imei = XPath.evalAsString("$subscriber/ExtendedInfo[Name='IMEI_MLDD']/Value");
```

Reads back the IMEI written by `MLDD_GET_SUB_DATA`. Blank if that FM was skipped.

### §6.5 recurringSoc (1-based index XPath)

```xpath
$orderRequest/OrderData/Customer/ParentOU[number($i)+1]/Subscriber[number($j)+1]
    /SubscriberOffers/ExtendedInfo[Name='RECURRING_SOC']/Value
```

### §6.6 mcsCorrelationId (Order-level)

```xpath
$orderRequest/OrderData/ExtendedInfo[Name='MCS_CORRELATION_ID']/Value
```

---

## §7 System & Integration Dependencies

### §7.1 ESB / JMS Channel Dependencies

| Direction | Channel | Destination | Purpose |
|-----------|---------|-------------|---------|
| [OUTBOUND] | FM JMS | MCS_SUBSCRIPTION_MARKUSED queue | Mark pack as used per subscriber |
| [INBOUND] | FM JMS | MCS_SUBSCRIPTION_MARKUSED response | SubscriptionMarkuesdResponse (code 135/200/other) |
| [LOG] | OMXESB Logger | Audit event | Request: AllowWriteLog gate; Response: unconditional |

### §7.2 Backend API Details

| Field | Value |
|-------|-------|
| Backend | MCS (Mobile Content Subscription engine) |
| Operation | SubscriptionMarkused |
| Request root | `ns:SubscriptionMarkuesdRequest` — **TYPO**: "Markuesd" ≠ "Markused" |
| Response root | `xsd2:SubscriptionMarkuesdResponse` |
| Success code | `200` (in payload response_code) |
| Already-marked-used code | `135` (in payload response_code) |
| Channel default | `'OMX'` — unless flow_id=FVM003 → use `OrderData.Channel` |

### §7.3 BE Working Memory Dependencies

| Concept | Field | Access | Notes |
|---------|-------|--------|-------|
| OrderRequest | OMXTrackingId, OrderPriority, OrderID, OrderType, Channel | READ | Standard headers |
| OrderRequest | OrderData.ExtendedInfo[MCS_CORRELATION_ID] | READ | Optional correlation ID |
| OrderRequest | OrderData.ExtendedInfo[CHECK_PACK_ALLOW_FLG] | READ+WRITTEN | Read for FVM003 payload; written if response='N' |
| Subscriber | ExtendedInfo[IMEI_MLDD] | READ | Set by MLDD_GET_SUB_DATA — upstream dependency |
| Subscriber | SubscriberOffers[].ExtendedInfo[FLOW_ID] | READ | flow_id resolution |
| Subscriber | SubscriberOffers[].ExtendedInfo[MCS_PACKCODE] | READ | pack_code waterfall |
| Subscriber | SubscriberOffers[].ExtendedInfo[RECURRING_SOC] | READ | Optional recurring SOC |
| Subscriber (POU only) | SubscriberOffers[].ExtendedInfo[FE_OR_CCBS] | WRITTEN | Set to 'MCS_IGNORE' on code 135 |
| Subscriber (POU only) | SubscriberOffers[] | WRITTEN | BRMS_ADD offer appended on code 135 |
| Subscriber (POU only) | SubscriberOffers[].ExtendedInfo[EXP_TYPE] | WRITTEN | Updated to 'FUT' on code 200 |
| Subscriber (POU only) | SubscriberOffers[].ExtendedInfo[MCS_EXP_DATE_VALUE] | WRITTEN | Set to package_expire_date on code 200 |
| Activity | Parameter[DEFAULT_FLOW_ID] | READ | Fallback flow_id |
| Activity | RequestCount / Response[] / Status | READ+WRITTEN | Standard |
| LogicalDate | LogicalDate | READ | For GetActivityEffectiveType on code 200 |

---

## §8 Detailed Payload Build

### §8.1 XSLT Parameters

| Parameter | Bound From | Notes |
|-----------|-----------|-------|
| `$orderRequest` | orderRequest concept | |
| `$refId` | subscriber.RefId | Correlation + header |
| `$subscriber` | subscriber concept | For FVM003 channel check |
| `$flow_id` | FLOW_ID or DEFAULT_FLOW_ID | |
| `$msisdn` | subscriber.MSISDN | No normalisation |
| `$pack_code` | 5-level ServiceType waterfall | |
| `$transaction_id` | OMXTrackingId | |
| `$imei` | subscriber.ExtendedInfo[IMEI_MLDD] | Upstream dependency |
| `$recurringSoc` | SubscriberOffers ExtendedInfo[RECURRING_SOC] | Conditional |
| `$mcsCorrelationId` | OrderData.ExtendedInfo[MCS_CORRELATION_ID] | Conditional |

### §8.2 Channel Logic

```xpath
xsl:choose:
  when: exists($subscriber/SubscriberOffers[ExtendedInfo[Name='FLOW_ID' and Value='FVM003']])
    → ns:channel ← $orderRequest/OrderData/Channel
  otherwise
    → ns:channel ← 'OMX'
```

### §8.3 Conditional Extra Fields

| Key | Condition | Value Source | POU Order | COU Order |
|-----|-----------|--------------|-----------|-----------|
| IMEI | Always | `$imei` | 1st | 2nd — swapped! |
| CHECK_PACK_ALLOW_FLG | `$flow_id = 'FVM003'` | OrderData.ExtendedInfo or '' | 2nd | 1st — swapped! |
| RECURRING_SOC | `string-length($recurringSoc) > 0` | `$recurringSoc` | 3rd | 3rd |
| MCS_CORRELATION_ID | `string-length($mcsCorrelationId) > 0` | `$mcsCorrelationId` | 4th | 4th |

### §8.4 XSLT Field Mapping Tree (POU variant)

```text
createEvent
└── event
    ├── @extId               ← OMXUtils:generateTrackingID()                     [Always]
    ├── JMSPriority          ← $orderRequest/OrderPriority                        [Always — no xsl:if]
    ├── JMSCorrelationID     ← $orderRequest/OrderData/OMXTrackingId             [Always]
    ├── OrderID              ← $orderRequest/OrderData/OrderID                   [Always]
    ├── RefID                ← $refId                                             [Always]
    ├── OrderType            ← $orderRequest/OrderData/OrderType                 [Always]
    └── payload
        └── ns:SubscriptionMarkuesdRequest  [TYPO: "Markuesd" not "Markused"]
            ├── ns:channel   ← xsl:choose                                         [Conditional: FVM003?]
            │   ├── when FVM003: $orderRequest/OrderData/Channel
            │   └── otherwise: 'OMX'
            ├── ns:flow_id   ← $flow_id                                          [Always]
            ├── ns:msisdn    ← $msisdn  (no 0→66 normalisation)                 [Always]
            ├── ns:pack_code ← $pack_code                                        [Always]
            ├── ns:transaction_id ← $transaction_id                              [Always]
            ├── ns:extra  key='IMEI', value=$imei                                [Always — POU 1st position]
            ├── ns:extra  key='CHECK_PACK_ALLOW_FLG' [Conditional: flow_id='FVM003']
            │   └── value: OrderData.ExtendedInfo[CHECK_PACK_ALLOW_FLG] or ''
            ├── ns:extra  key='RECURRING_SOC' [Conditional: string-length($recurringSoc)>0]
            └── ns:extra  key='MCS_CORRELATION_ID' [Conditional: string-length($mcsCorrelationId)>0]

COU variant difference: IMEI extra is 2nd; CHECK_PACK_ALLOW_FLG extra is 1st.
```

---

## §9 Audit Logging

| Phase | Gate | AUDIT_TRACE | PROCESS_ID |
|-------|------|-------------|------------|
| Request | `AllowWriteLog(OrderType)` | `"Request Sent for MCS_SUBSCRIPTION_MARKUSED"` | `concat($pid, "_REQ")` |
| Response | **Unconditional** | `concat("Response received for RefId ", $eventResponse/RefID)` | `concat($pid, "_RES")` |

> Request and response audit gates differ: request is conditional on `AllowWriteLog(OrderType)`; response always sends regardless.

---

## §10 Activity Status Management

| Condition | Call | Code |
|-----------|------|------|
| At least one subscriber sent | `GetActivityStatusString("1", false)` + `SendDataToDB` | "1" (RUNNING) |
| No subscribers qualify | `SkipActivity(orderRequest, orderCurrentActivity, "4")` | "4" (SKIPPED) |

---

## §11 Exception / Error Handling

```java
catch (Exception ae) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
}
```

---

## §12 Helper Functions Reference

| Function | Purpose | New in this FM? |
|----------|---------|-----------------|
| `GetActivityParameterValueFromKey(activity, "DEFAULT_FLOW_ID")` | Reads named parameter from activity config | **Yes** |
| `GetActivityEffectiveType(package_expire_date, logicalDate)` | Returns 'FUT' or 'NOW' for expire date classification | **Yes** |
| `BRMS.IsBlankOrStringNull(str)` | Null/blank string check | **Yes** |
| `AllowWriteLog(OrderType)` | Controls request audit conditional | No |
| `GetXMLForSubscriber / GetXMLForSubscriberInChildOU` | PreExecCheck XML builder | No |
| `GetActivityStatusString / SendDataToDB / SkipActivity / HandleActivityException` | Activity lifecycle | No |

---

## §13 Function Dependency Tree

```text
Request_MCS_SUBSCRIPTION_MARKUSED (rule)
├── Instance.getByExtIdByUri(NextActivityName, Activity)  [nextAct live lookup]
├── GetActivityParameterValueFromKey(activity, "DEFAULT_FLOW_ID")
├── [per POU × Subscriber]:
│   ├── Response[].ReferenceId == refId  [reqSuccess]
│   ├── GetXMLForSubscriber(req, refId) + XPath.execute(nextAct.PreExecCheck)
│   ├── XPath.evalAsString → flow_id  (FLOW_ID or defaultFlowId)
│   ├── XPath.evalAsString → pack_code  (5-level waterfall)
│   ├── XPath.evalAsString → imei  (IMEI_MLDD read-back)
│   ├── XPath.evalAsString → recurringSoc
│   ├── XPath.evalAsString → mcsCorrelationId
│   ├── Event.createEvent("xslt://MCS_SUBSCRIPTION_MARKUSED")
│   │   └── OMXUtils:generateTrackingID()
│   ├── Event.Ext.sendEventImmediate(reqEvent)
│   ├── AllowWriteLog(OrderType)
│   │   └── Event.Ext.sendEventImmediate(auditEvent)  [conditional]
│   └── orderCurrentActivity.RequestCount++
├── [per POU × COU × Subscriber]: GetXMLForSubscriberInChildOU + same pattern
├── GetActivityStatusString("1") + SendDataToDB  [or SkipActivity("4")]
└── HandleActivityException  [catch]

Response_MCS_SUBSCRIPTION_MARKUSED (rulefunction)
├── OMXUtils.generateTrackingID()  [called in BE — extId passed as $extId to XSLT]
├── Instance.createInstance("xslt://ResponseBase")  [$extId as parameter]
├── currActivity.Response[length] = activityRes
├── XPath.evalAsBoolean → isMarkUsed  (response_code = '135')
├── XPath.evalAsBoolean → isSuccess  (response_code = '200')
│
├── [if isMarkUsed (135)]:
│   └── POU subscriber loop only  ← [BUG: no COU]
│       ├── SubscriberOffers loop (MCS_PACKCODE + FLOW_ID present)
│       │   └── ExtendedInfo[FE_OR_CCBS].Value = "MCS_IGNORE"
│       ├── XPath.evalAsString → chargeCode  (extra[key='CHARGE_CODE'])
│       ├── XPath.evalAsString → price  (extra[key='PRICE'])
│       ├── BRMS.IsBlankOrStringNull(chargeCode)
│       └── Instance.createInstance("xslt://SubscriberOffers")  [BRMS_ADD]
│           OfferName=chargeCode, ServiceType='79', OfferRate=price, FE_OR_CCBS='FE'
│
├── [if isSuccess (200)]:
│   └── POU subscriber loop only  ← [BUG: no COU]
│       ├── XPath.evalAsString → str_package_expire_date
│       ├── DateTime.parseString(str, "yyyy-MM-dd HH:mm:ss")
│       ├── XPath.evalAsString → exp_type
│       ├── BRMS.IsBlankOrStringNull checks
│       ├── Instance.getByExtIdByUri("LogicalDate")
│       └── GetActivityEffectiveType(package_expire_date, logicalDate)
│           └── [if 'FUT']: update EXP_TYPE + append MCS_EXP_DATE_VALUE
│
├── XPath.evalAsBoolean → hasCheckPackAllowFlag  (CHECK_PACK_ALLOW_FLG='N')
├── [if hasCheckPackAllowFlag]:
│   └── Instance.createInstance("xslt://OrderDataExtendedInfo")
│       Name='CHECK_PACK_ALLOW_FLG', Value='N' → OrderData.ExtendedInfo[]
├── Event.Ext.sendEventImmediate(auditEvent)  [unconditional]
└── XPath.evalAsInt("count(Response[tib:right...='000'])") → fan-in
```

---

## §14 Concept Definitions Referenced

| Concept | Key Fields | Role |
|---------|-----------|------|
| `Concepts.FM.Base.ResponseBase` | ResponseCode, ResponseMessage, CompletionStatus, ReferenceId | Standard; extId via $extId BE param |
| `Concepts.OrderRequest.OrderElements.SubscriberOffers` | OfferName, ServiceType, OfferRate, ExtendedInfo[] | Created (BRMS_ADD) on code 135 |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.SubscriberOffersExtendedInfo` | Name, Value | Written: FE_OR_CCBS=MCS_IGNORE, EXP_TYPE=FUT, MCS_EXP_DATE_VALUE |
| `Concepts.OrderRequest.OrderElements.ExtendedInfos.OrderDataExtendedInfo` | Name, Value | Written: CHECK_PACK_ALLOW_FLG=N |
| `Concepts.OM.LogicalDate` | LogicalDate | Business date for expire date classification |

---

## §15 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Read `DEFAULT_FLOW_ID` from activity parameter config; per-subscriber flow_id falls back to this value. |
| R2 | pack_code: evaluate 5-level ServiceType waterfall (86→99→69→88→OfferName) against all POU subscribers. |
| R3 | Read IMEI from `subscriber.ExtendedInfo[IMEI_MLDD]`; always send as extra key='IMEI'. |
| R4 | channel: 'OMX' unless subscriber has FLOW_ID=FVM003 on any SubscriberOffer → emit OrderData.Channel. |
| R5 | CHECK_PACK_ALLOW_FLG extra: only emit when flow_id='FVM003'; RECURRING_SOC and MCS_CORRELATION_ID: emit only when non-blank. |
| R6 | Response 135: set FE_OR_CCBS='MCS_IGNORE'; if chargeCode present, create BRMS_ADD SubscriberOffers (ServiceType='79'). |
| R6a | **[BUG FIX]** Extend code-135 handler to also iterate COU subscribers. |
| R7 | Response 200: handle expire-date logic — parse package_expire_date; classify via GetActivityEffectiveType; if 'FUT', update EXP_TYPE and write MCS_EXP_DATE_VALUE. |
| R7a | **[BUG FIX]** Extend code-200 handler to also iterate COU subscribers. |
| R8 | CHECK_PACK_ALLOW_FLG='N' in response extras → write to OrderData.ExtendedInfo. |
| R9 | Response audit unconditional; request audit gated by AllowWriteLog(OrderType). |
| R10 | Fan-in: standard "000" count == RequestCount. |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| COU subscribers excluded from isMarkUsed/isSuccess handlers | [MEDIUM] | Add ChildOU loops to both response branches |
| XML element name typo `SubscriptionMarkuesdRequest/Response` | [MEDIUM] | Preserve until MCS schema corrected; flag for MCS team |
| POU/COU XSLT extra ordering difference | [LOW] | Normalise order in migration; verify MCS is order-agnostic |
| IMEI blank if MLDD_GET_SUB_DATA was skipped | [LOW] | Verify MCS behaviour with blank IMEI extra |
| pack_code XPath searches order-wide (not subscriber-scoped) | [MEDIUM] | Verify this is intentional design vs. bug; scope if per-subscriber is needed |

---

## §16 Full Source Code

```java
rule Rules.OMConsumers.OMXFM.Request.Request_MCS_SUBSCRIPTION_MARKUSED {
  attribute { priority=5; forwardChain=true; }
  declare { OrderRequest orderRequest; Activity orderCurrentActivity; }
  when { /* standard 4-condition WHEN with ActivityID=="MCS_SUBSCRIPTION_MARKUSED" */ }
  then {
    boolean isActResub = ...;
    try {
      Activity nextAct = Instance.getByExtIdByUri(ProcessFlow.NextActivityName, Activity);
      String defaultFlowId = GetActivityParameterValueFromKey(orderCurrentActivity, "DEFAULT_FLOW_ID");
      boolean isSkipped = true;

      /* POU Subscribers */
      for(int i ...) { for(int j ...) {
        // reqSuccess + PreExecCheck via nextAct.PreExecCheck
        if(!reqSuccess && chkRes=="true") {
          String transaction_id = OMXTrackingId;
          String flow_id = XPath(FLOW_ID or defaultFlowId);
          String msisdn = subscriber.MSISDN;
          String pack_code = XPath(5-level ServiceType waterfall);  // see §6.3
          String imei = XPath("subscriber/ExtendedInfo[Name='IMEI_MLDD']/Value");
          String recurringSoc = XPath(SubscriberOffers/ExtendedInfo[RECURRING_SOC]);
          String mcsCorrelationId = XPath(OrderData/ExtendedInfo[MCS_CORRELATION_ID]);
          // [MCS_SUBSCRIPTION_MARKUSED XSLT — see §8.4]
          Event.Ext.sendEventImmediate(reqEvent);
          if(AllowWriteLog(OrderType)) { sendAudit(); }
          if(!isActResub) orderCurrentActivity.RequestCount++;
          isSkipped = false;
        }
      }}
      /* COU Subscribers — identical pattern with GetXMLForSubscriberInChildOU */
      ...
      if(!isSkipped) { GetActivityStatusString("1"); SendDataToDB(); }
      else { SkipActivity("4"); }
    } catch(Exception ae) { HandleActivityException(...); }
  }
}
```

---

## §17 Response Message Rule

### §17.1 Overview

The response handler processes three MCS response outcomes: code 135 (already-marked-used) sets MCS_IGNORE on matching offers and creates a BRMS_ADD SubscriberOffer; code 200 (success) handles expire-date logic and EXP_TYPE upgrade; CHECK_PACK_ALLOW_FLG='N' in response extras is written back to OrderData. Audit is unconditional. Fan-in: standard "000" count.

### §17.2 Scope Variables

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest | READ + WRITTEN |
| `eventResponse` | Events.OMConsumers.OMXFM.Response.MCS_SUBSCRIPTION_MARKUSED | Backend response |
| `currActivity` | Concepts.OM.ProcessConfig.Activity | Response[] appended; fan-in |

### §17.3 ResponseBase Concept Construction

```text
createObject
└── object  @extId ← $extId (OMXUtils.generateTrackingID() called in BE, passed as param)
    ├── ResponseCode      ← $eventResponse/ResponseCode    [Conditional]
    ├── ResponseMessage   ← $eventResponse/ResponseMsg     [Conditional]
    ├── CompletionStatus  ← $eventResponse/CompletionStatus [Conditional]
    └── ReferenceId       ← $eventResponse/RefID           [Conditional]
```

### §17.4 Response Code 135 Handler (isMarkUsed)

```java
if (isMarkUsed) {  // xsd2:response_code = '135'
  // POU loop only — COU excluded [BUG]
  for(iPOU ...) { for(subs ...) {
    if(RefID matches subscriber.RefId) {
      // For each offer with both MCS_PACKCODE + FLOW_ID:
      ExtendedInfo[Name="FE_OR_CCBS"].Value = "MCS_IGNORE";  // flag for downstream skip
      break;

      chargeCode = XPath(extra[key='CHARGE_CODE']/value);
      price = XPath(extra[key='PRICE']/value);
      if(!IsBlankOrStringNull(chargeCode)) {
        // Create new SubscriberOffers with extId = generateTrackingID()+":BRMS_ADD"
        // OfferName=chargeCode, ServiceType='79', OfferRate=price
        // ExtendedInfo: FE_OR_CCBS='FE'
        // ExtendedInfo (if count($price)>0): AMOUNT=$price
        subscriber.SubscriberOffers[] += offerConcept;
      }
    }
  }}
}
```

### §17.5 Response Code 200 Handler (isSuccess)

```java
if (isSuccess) {  // xsd2:response_code = '200'
  // POU loop only — COU excluded [BUG]
  for(iPOU ...) { for(subs ...) {
    if(RefID matches subscriber.RefId) {
      str_package_expire_date = XPath(xsd2:package_expire_date);
      package_expire_date = DateTime.parseString(str, "yyyy-MM-dd HH:mm:ss");
      exp_type = XPath(SubscriberOffers[FE_OR_CCBS='FE']/ExtendedInfo[EXP_TYPE]/Value);

      if(package_expire_date != null && !blank(exp_type) && !"FUT".equals(exp_type)) {
        logicalDate = LogicalDate concept (or DateTime.now());
        type = GetActivityEffectiveType(package_expire_date, logicalDate);
        if("FUT".equals(type)) {
          // For each offer where FE_OR_CCBS='FE':
          //   if EXP_TYPE ExtendedInfo found: update Value=type; append MCS_EXP_DATE_VALUE
          //   else: append EXP_TYPE=type AND MCS_EXP_DATE_VALUE=package_expire_date
        }
      }
    }
  }}
}
```

### §17.6 CHECK_PACK_ALLOW_FLG Write-back

```java
boolean hasCheckPackAllowFlag = XPath.evalAsBoolean(
    "exists(xsd2:extra[xsd2:key='CHECK_PACK_ALLOW_FLG' and xsd2:value='N'])");
if (hasCheckPackAllowFlag) {
    orderRequest.OrderData.ExtendedInfo[] += OrderDataExtendedInfo {
        Name = 'CHECK_PACK_ALLOW_FLG', Value = 'N'
    };
}
```

### §17.7 Fan-in Completion Logic

```java
int successResponseCount = XPath.evalAsInt(
    "count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = '000'])");
if(currActivity.RequestCount == successResponseCount) { return "true"; }
else { return "false"; }
```

Standard "000" suffix count fan-in. Note: verify whether MCS sets JMS-level ResponseCode to "000" for response_code 135 and 200 — if ResponseCode="135" in JMS header, code-135 responses may never satisfy fan-in.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
