# OMX_CAL_NEXT_BILL_DATE

> Internal OMX calculation — computes the subscriber's next bill date from the BillCycleNo, stamps qualifying SubscriberOffers with ExpirationDate and SBM_NO_PROVISIONING=Y flag, then immediately advances the orchestration.

> **⚠ No external backend call.** This rule is a pure in-memory computation. It completes synchronously via `NextActivity()` — no response rulefunction exists.

## §1 — Overview & Purpose

When the order reaches the `OMX_CAL_NEXT_BILL_DATE` activity, this rule:
1. Determines the logical date (from `LogicalDate` concept, or `DateTime.now()` as fallback)
2. Reads `BillCycleNo` from the order (day-of-month on which the customer is billed)
3. Calculates the **next bill date** using `GetNextBillDate()`
4. Iterates every `SubscriberOffers` in the order (POU + COU hierarchy)
5. For each qualifying offer (passing PreExecCheck): sets `ExpirationDate = nextBillDate` and appends `SBM_NO_PROVISIONING=Y`
6. Calls `NextActivity()` to immediately advance the orchestration (no async wait)

> **Business Purpose:** For POSTPAID_REMOVE_OFFER_SUB, determines whether a removed offer should expire at the next billing cycle rather than being terminated immediately. Setting `SBM_NO_PROVISIONING=Y` instructs downstream SBM steps to suppress immediate deactivation.

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `Rules.OMConsumers.OMXOM.OMX_CAL_NEXT_BILL_DATE` |
| Priority | 5 |
| Forward Chain | true |
| Rule Type | **Internal calculation** — no backend JMS call; self-completing via `NextActivity()` |
| Author | RS33-BANDIT |
| Activity ID | OMX_CAL_NEXT_BILL_DATE |
| Backend System | None — pure in-memory computation |
| Response Rulefunction | None (N/A — no async backend call) |

## §3 — Working Memory — Declared Objects

| Variable | Concept Type | Role |
|----------|-------------|------|
| `orderRequest` | `/Concepts/OrderRequest/OrderRequest` | Master order — source of BillCycleNo and subscriber offer data |
| `orderCurrentActivity` | `/Concepts/OM/ProcessConfig/Activity` | Current activity — provides PreExecCheck; Status updated to COMPLETE on exit |

Additional working memory accessed:

| Concept | Access | Purpose |
|---------|--------|---------|
| `Concepts.OM.LogicalDate` (extId="LogicalDate") | READ | System logical date for bill date calculation |
| `SubscriberOffers.ExpirationDate` | WRITE | Stamped with calculated nextBillDate |
| `SubscriberOffers.ExtendedInfo[]` | WRITE | Appended with SBM_NO_PROVISIONING=Y |

## §4 — Rule Conditions (WHEN)

| # | Condition | Meaning |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance matches current next activity |
| 2 | `orderCurrentActivity.ActivityID == "OMX_CAL_NEXT_BILL_DATE"` | Activity type is this rule |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_NEXT_BILL_DATE"` | Process flow pointer matches |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Activity is in WAITING state |

## §5 — Execution Flow Diagram

1. Load LogicalDate → `Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")` — if blank, fall back to `DateTime.now()`
2. Read BillCycleNo → `orderRequest.OrderData.Customer.BillCycleNo`
3. Calculate next bill date → `GetNextBillDate(logicalDate, nextBill)` → `ConvertBillCycleDate()` + month arithmetic
4. Read PreExecCheck → `orderCurrentActivity.PreExecCheck`
5. POU Offer loop → for each SubscriberOffer: read `FE_OR_CCBS` filter; build XML via `GetXMLForSubscriberOfferFilterWithExtendedInfo()`; evaluate PreExecCheck; if passes → stamp ExpirationDate + SBM_NO_PROVISIONING=Y
6. COU Offer loop → same pattern using `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo()`
7. Advance → `NextActivity()` (sets COMPLETE, advances ProcessFlow) + audit log, OR `SkipActivity("4")`
8. Exception → `HandleActivityException()`

## §6 — Rule Action (THEN) — Step-by-Step Logic

| Step | Code Action | Detail |
|------|-------------|--------|
| 1 | Resolve logical date | `Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")` → parse or fallback |
| 2 | Get bill cycle | `orderRequest.OrderData.Customer.BillCycleNo` |
| 3 | Calc next bill date | `GetNextBillDate(logicalDate, nextBill)` |
| 4 | POU offer loop | For each SubscriberOffer: read FE_OR_CCBS; PreExecCheck; stamp ExpirationDate + SBM_NO_PROVISIONING=Y |
| 5 | COU offer loop | Same — uses `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo()` |
| 6 | Advance or skip | `NextActivity()` (COMPLETE) OR `SkipActivity("4")` |
| 7 | Audit log | Logger event OPERATION_NAME=OMX_CAL_NEXT_BILL_DATE |
| 8 | Exception | `HandleActivityException(orderRequest, orderCurrentActivity, ex, "")` |

## §7 — Data Extraction & Calculation Logic

### Bill Date Calculation

```java
// Step 1: Convert BillCycleNo to day-of-month string
String billCycleDate = RuleFunctions.Helpers.ConvertBillCycleDate(billCycle); // e.g. "5" → "05"

// Step 2: Build date for current month
DateTime nextBillDate = DateTime.parseString(
    billCycleDate + "-" + (DateTime.getMonth(currentDate) + 1) + "-" + DateTime.getYear(currentDate),
    "dd-MM-yyyy");

// Step 3: If today is already past the bill date, roll forward one month
if (currentDate >= nextBillDate) {
    nextBillDate = DateTime.addMonth(nextBillDate, 1);
}
return nextBillDate;
```

**Example:** BillCycleNo="5", today=2026-08-13 → this month's bill date = 2026-08-05 (past) → next bill date = **2026-09-05**.

### Offer Qualification Filter

```java
// Read FE_OR_CCBS tag from offer's ExtendedInfo
String filter = XPath.evalAsString("$psof/ExtendedInfo[Name=\"FE_OR_CCBS\"]/Value"); // "CCP" or "CCBS"

// Build subscriber-offer XML including the filter value
String sXML = GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, psof.Soc, filter);

// Evaluate PreExecCheck XPath against the snapshot
chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=...");
```

## §8 — System & Integration Dependencies

### §8.1 Order Type Dependencies

Used in **POSTPAID_REMOVE_OFFER_SUB** and similar postpaid offer management flows where offers may be deferred to the next billing cycle.

### §8.2 ESB / JMS Channel Dependencies

**Internal only** — no JMS channel used for the calculation. Only audit Logger event sent on completion.

| Direction | Channel | Purpose |
|-----------|---------|---------|
| [OUTBOUND] | OMXESB Logger | Audit log on completion only |

### §8.4 BE Working Memory Dependencies

| Field | Access | Purpose |
|-------|--------|---------|
| `Concepts.OM.LogicalDate` (extId="LogicalDate") | READ | System logical date |
| `orderRequest.OrderData.Customer.BillCycleNo` | READ | Day-of-month billing day |
| `orderCurrentActivity.PreExecCheck` | READ | XPath to filter qualifying offers |
| `SubscriberOffers.ExtendedInfo[FE_OR_CCBS]` | READ | Offer source tag for PreExecCheck context |
| `SubscriberOffers.ExpirationDate` | WRITE | Stamped with nextBillDate |
| `SubscriberOffers.ExtendedInfo[]` | WRITE | Appended with SBM_NO_PROVISIONING=Y |
| `orderCurrentActivity.Status` | WRITE | Set to COMPLETE (2) via NextActivity() |
| `orderRequest.ProcessFlow.NextActivityName/ID` | WRITE | Advanced to next activity |

### §8.6 Global Variable Dependencies

| Global Variable Path | Used For |
|---------------------|---------|
| `OMX_COMMON/Component_Name/OMX_CEP` | COMPONENT_NAME in audit log |
| `OMX_COMMON/_SharedResources/Common/MSG_LOG_LEVEL/INFO` | LOG_LEVEL in audit log |
| `OMX_OM/ComponentName` | Response code prefix (NextActivity order completion) |
| `OMX_OM/Services/OMServices` | Service code (NextActivity) |
| `OMX_OM/Services/SubmitOrder` | Operation code (NextActivity) |
| `OMX_COMMON/Severity/Success` | Severity code (NextActivity) |
| `OMX_OM/ResponseCodes/Success` | Success code "000" (NextActivity) |

## §9 — Internal XSLT Objects Created

No outbound JMS event payloads. The only XSLT creates in-memory concept objects via `Instance.createInstance("xslt://...")`.

### SBM_NO_PROVISIONING Flag (SubscriberOffersExtendedInfo)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    version="1.0" exclude-result-prefixes="OMXUtils xsl xsd">
  <xsl:output method="xml"/>
  <xsl:template match="/">
    <createObject>
      <object>
        <xsl:attribute name="extId">
          <xsl:value-of select="concat(OMXUtils:generateTrackingID(), ':SBM_NO_PROVISIONING')"/>
        </xsl:attribute>
        <Name><xsl:value-of select="'SBM_NO_PROVISIONING'"/></Name>
        <Value><xsl:value-of select="'Y'"/></Value>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

The same XSLT is used for both POU and COU offers.

## §10 — Working Memory Modification Tree

```text
SubscriberOffers  [Conditional: qualifying offers only — those passing PreExecCheck]
├── ExpirationDate       ← nextBillDate (calculated)                    [Conditional]
└── ExtendedInfo[]       (appended)                                     [Conditional]
    └── SubscriberOffersExtendedInfo
        ├── @extId       ← concat(OMXUtils:generateTrackingID(), ':SBM_NO_PROVISIONING')
        ├── Name         ← "SBM_NO_PROVISIONING"  (static)             [Always]
        └── Value        ← "Y"  (static)                               [Always]
```

## §11 — Audit Logging

| Field | Value |
|-------|-------|
| `ESBUUID` | OMXTrackingId (conditional) |
| `PROCESS_ID` | `concat($pid, "_RES")` |
| `COMPONENT_NAME` | `OMX_COMMON/Component_Name/OMX_CEP` |
| `OPERATION_NAME` | `"OMX_CAL_NEXT_BILL_DATE"` (static) |
| `LOG_LEVEL` | INFO |
| `AUDIT_TRACE` | `"OMX_CAL_NEXT_BILL_DATE Completed."` (static) |
| `AUDIT_TS` | `tib:format-dateTime('yyyy-MM-dd HH:mm:ss.SSS', current-dateTime())` |
| `payload` | Empty element `<payload/>` — no payload written |

> Audit event sent only on successful completion (not on skip path).

## §12 — Activity Status Management

| Status | Code | Trigger |
|--------|------|---------|
| COMPLETE | `"2"` (set inside NextActivity()) | At least one offer stamped |
| SKIPPED | `"4"` | All offers failed PreExecCheck |

> `NextActivity()` advances `ProcessFlow.NextActivityName/ID` to the next activity. If all activities are complete, closes the order with success ResponseCode.

## §13 — Exception / Error Handling

```java
catch (Exception ex) {
    RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ex, "");
}
```

## §14 — Helper Functions Reference

| Function | Signature | Purpose |
|----------|-----------|---------|
| `GetNextBillDate` | `DateTime(DateTime currentDate, String billCycle)` | Calculates next bill date — ConvertBillCycleDate + month arithmetic |
| `ConvertBillCycleDate` | `String(String billCycle)` | Converts BillCycleNo to zero-padded day string |
| `GetXMLForSubscriberOfferFilterWithExtendedInfo` | `String(orderRequest, subRefId, soc, filter)` | Serialises POU subscriber-offer + FE_OR_CCBS filter for PreExecCheck |
| `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo` | `String(orderRequest, subRefId, soc, pouRefId, filter)` | Same for COU context |
| `NextActivity` | `void(orderRequest, orderCurrentActivity)` | Sets COMPLETE, advances ProcessFlow, handles FINALLY/order-complete logic |
| `SkipActivity` | `void(orderRequest, activity, code)` | Marks skipped and advances |
| `HandleActivityException` | `void(orderRequest, activity, ex, msg)` | Error handling |

## §15 — Function Dependency Tree

```text
OMX_CAL_NEXT_BILL_DATE (rule)
├── Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate")
├── DateTime.parseString(...) or DateTime.now()
├── RuleFunctions.Helpers.GetNextBillDate(logicalDate, nextBill)
│   ├── RuleFunctions.Helpers.ConvertBillCycleDate(billCycle)
│   └── DateTime.addMonth(nextBillDate, 1)                     [if date past]
├── XPath.evalAsString("$psof/ExtendedInfo[Name=\"FE_OR_CCBS\"]/Value")  [per offer]
├── RuleFunctions.Helpers.GetXMLForSubscriberOfferFilterWithExtendedInfo(...)  [POU]
├── RuleFunctions.Helpers.GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo(...)  [COU]
├── XPath.execute("/("+chkXPath+")", sXML, ...)
├── Instance.createInstance("xslt://SubscriberOffersExtendedInfo")       [per qualifying offer]
├── RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)
│   ├── RuleFunctions.Helpers.GetActivityStatusString("2", false)
│   ├── Instance.getByExtIdByUri(nextActivity, Activity)
│   ├── RuleFunctions.Helpers.BRMS.IsBlank(...)
│   ├── RuleFunctions.Helpers.GetActivityParamValueFromKey(activity, "FINALLY")
│   ├── RuleFunctions.Helpers.SkipAllActivities(...)            [if FINALLY=Y]
│   ├── RuleFunctions.Helpers.SendDataToDB(orderRequest)
│   └── System.getGlobalVariableAsString("OMX_OM/...", ...)     [order completion]
├── Event.Ext.sendEventImmediate(Event.createEvent("xslt://Logger"))
└── RuleFunctions.Helpers.SkipActivity(orderRequest, activity, "4")
    OR RuleFunctions.Helpers.HandleActivityException(...)
```

## §16 — Concept Definitions Referenced

| Concept | Path | Key Properties Used |
|---------|------|-------------------|
| `OrderRequest` | `/Concepts/OrderRequest/OrderRequest` | OrderData.Customer.BillCycleNo, ProcessFlow |
| `Activity` | `/Concepts/OM/ProcessConfig/Activity` | PreExecCheck, Status, NextActivity, Parameter[], ResubmitActivity |
| `LogicalDate` | `/Concepts/OM/LogicalDate` | LogicalDate (ISO datetime string) |
| `SubscriberOffers` | `/Concepts/OrderRequest/OrderElements/SubscriberOffers` | ExtendedInfo[], ExpirationDate, Soc |
| `SubscriberOffersExtendedInfo` | `/Concepts/OrderRequest/OrderElements/ExtendedInfos/SubscriberOffersExtendedInfo` | Name, Value — written with SBM_NO_PROVISIONING=Y |

## §17 — Migration Notes & Recommendations

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Calculate next bill date from BillCycleNo using logical date (or system date as fallback) |
| R2 | For each qualifying SubscriberOffer (POU + COU): set ExpirationDate to next bill date |
| R3 | Append SBM_NO_PROVISIONING=Y ExtendedInfo to each qualifying offer |
| R4 | Qualification driven by PreExecCheck XPath evaluated against subscriber-offer XML including FE_OR_CCBS value |
| R5 | If no offers qualify: skip this activity |
| R6 | On completion: advance orchestration immediately via NextActivity() |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Logical date concept dependency | [MEDIUM] | Falls back to system time silently — ensure LogicalDate concept always populated in production |
| Month-arithmetic at month boundaries | [MEDIUM] | `parseString("31-02-yyyy")` may throw for short months — validate BillCycleNo values |
| FE_OR_CCBS XPath on empty ExtendedInfo | [LOW] | Returns empty string — PreExecCheck may include unintended offers |
| Commented-out Parameter override | [LOW] | Removed feature that allowed BillCycleNo override via activity Parameter — document intent |

## §18 — Full Source Code

```java
rule Rules.OMConsumers.OMXOM.OMX_CAL_NEXT_BILL_DATE {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_CAL_NEXT_BILL_DATE";
    orderRequest.ProcessFlow.NextActivityID == "OMX_CAL_NEXT_BILL_DATE";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    try {
      DateTime logicalDate;
      Concepts.OM.LogicalDate logicalDateRes = Instance.getByExtIdByUri("LogicalDate", "/Concepts/OM/LogicalDate");
      if (String.length(String.trim(logicalDateRes.LogicalDate)) <= 0) {
        logicalDate = DateTime.now();
      } else {
        logicalDate = DateTime.parseString(logicalDateRes.LogicalDate, "yyyy-MM-dd'T'HH:mm:ssXXX");
      }

      String nextBill = orderRequest.OrderData.Customer.BillCycleNo;
      // (Parameter[0] override commented out in source)

      boolean isSkipped = true;
      DateTime nextBillDate = RuleFunctions.Helpers.GetNextBillDate(logicalDate, nextBill);
      String chkXPath = orderCurrentActivity.PreExecCheck;

      int pouLen = orderRequest.OrderData.Customer.ParentOU@length;
      for (int p = 0; p < pouLen; p++) {
        String pOuRefId = orderRequest.OrderData.Customer.ParentOU[p].RefId;

        // POU Subscriber → Offer loop
        for (int ps = 0; ps < pSubLen; ps++) {
          for (int o = 0; o < psofLen; o++) {
            SubscriberOffers psof = ...ParentOU[p].Subscriber[ps].SubscriberOffers[o];
            String filter = XPath.evalAsString("$psof/ExtendedInfo[Name=\"FE_OR_CCBS\"]/Value");
            String chkRes = "true";
            if (String.length(chkXPath) > 0) {
              String sXML = GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, psof.Soc, filter);
              chkRes = XPath.execute("/("+chkXPath+")", sXML, "ns0=...");
            }
            if (String.equals(chkRes, "true")) {
              SubscriberOffersExtendedInfo sbmProv = Instance.createInstance(
                /* xslt://SubscriberOffersExtendedInfo — see §9
                   Creates: Name="SBM_NO_PROVISIONING", Value="Y"
                   extId=concat(OMXUtils:generateTrackingID(), ':SBM_NO_PROVISIONING') */);
              psof.ExtendedInfo[psof.ExtendedInfo@length] = sbmProv;
              psof.ExpirationDate = nextBillDate;
              isSkipped = false;
            }
          }
        }
        // COU loop — same pattern, uses GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo
      }

      if (!isSkipped) {
        RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity);
        // + audit log event (AUDIT_TRACE="OMX_CAL_NEXT_BILL_DATE Completed.")
      } else {
        RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4");
      }
    } catch (Exception ex) {
      RuleFunctions.Helpers.HandleActivityException(orderRequest, orderCurrentActivity, ex, "");
    }
  }
}
```

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
