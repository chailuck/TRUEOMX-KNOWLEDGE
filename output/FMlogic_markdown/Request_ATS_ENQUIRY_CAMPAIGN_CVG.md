# Request_ATS_ENQUIRY_CAMPAIGN_CVG

> TIBCO BusinessEvents FM — ATS Enquiry Campaign (Convergence) + TVS_NO extraction side-effect

**Priority:** 5 | **forwardChain:** true | **No author** | **Backend:** ATS

---

## §1 — Overview & Purpose

Fires when `ActivityID == "ATS_ENQUIRY_CAMPAIGN_CVG"`. Dual-loop per subscriber. Queries ATS for active campaign data with productType=TMV.

> **⚠ Important Side-Effect in Response Handler:** The response rulefunction parses campaign response for code `"ATB8V2"` with status `ACTIVE` or `SUSPEND`, then extracts `productList[productType=TVS]/productId` and writes it as `TVS_NO` ExtendedInfo on the matching subscriber. TVS_NO is subsequently used by `ICC_TVS_SUBMIT_ORDER` when `REASON=TFULL`.

**FUNCTION parameter:** from `GetActivityParameterValueFromKey("FUNCTION")`; defaults to `"ALL"` if absent.

---

## §2 — Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_ATS_ENQUIRY_CAMPAIGN_CVG` |
| Priority / forwardChain | 5 / true |
| Author | (none) |
| Loop | Dual-loop: ParentOU.Subscriber + ChildOU.Subscriber |
| Fan-in type | Classic count |

---

## §5 — Execution Flow

1. Read FUNCTION param (default "ALL")
2. Dual-loop POU + COU subscribers
3. Per subscriber: apply PreExecCheck
4. Fire `ATS_ENQUIRY_CAMPAIGN` event: requestName="EnquiryCampaign", function, activeFlag="Y", productType="TMV", accessNumber=MSISDN
5. On dispatch → status "1"; On all skip → `SkipActivity("4")`

---

## §10 — XSLT Field Mapping Tree

```text
EnquiryCampaignRequest
├── ns:channel         ← OrderData/Channel           [Always]
├── ns:requestName     ← "EnquiryCampaign"            [Always]
├── ns:function        ← FUNCTION param or "ALL"      [Always]
├── ns:activeFlag      ← "Y"                          [Always]
└── ns:product
    ├── ns:productType ← "TMV"                        [Always]
    └── ns:accessNumber ← Subscriber/MSISDN           [Always]
```

---

## §15 — Function Dependency Tree

```text
Request_ATS_ENQUIRY_CAMPAIGN_CVG
├── RuleFunctions.Helpers.GetActivityParameterValueFromKey("FUNCTION")
├── RuleFunctions.Helpers.GetXMLForSubscriber / GetXMLForSubscriberInChildOU
├── XPath.execute (PreExecCheck)
├── Event.createEvent (ATS_ENQUIRY_CAMPAIGN XSLT)
├── RuleFunctions.Helpers.ActionRequestEvent
├── Event.Ext.sendEventImmediate (audit)
├── RuleFunctions.Helpers.SendFirstRequestEvent
├── RuleFunctions.Helpers.GetActivityStatusString
├── RuleFunctions.Helpers.SendDataToDB
├── RuleFunctions.Helpers.SkipActivity
└── RuleFunctions.Helpers.HandleActivityException

Response_ATS_ENQUIRY_CAMPAIGN_CVG (side-effects)
├── XPath.evalAsString (campaignCode="ATB8V2", status ACTIVE|SUSPEND)
├── XPath.evalAsString (productList[productType=TVS]/productId → tvsNo)
└── Instance.setPropertyValue (Subscriber.ExtendedInfo[TVS_NO] = tvsNo)
```

---

## §19 — Response Message Rule

### §19.2 TVS_NO Extraction Algorithm

1. Parse `campaignInfo` array
2. Find entry where `campaignCode = "ATB8V2"`
3. Check status == `"ACTIVE"` or `"SUSPEND"`
4. Find `productList[productType="TVS"]`
5. Extract `productId` → `tvsNo`
6. Write `TVS_NO` to subscriber's ExtendedInfo in Working Memory

### §19.3 ResponseBase

```text
ResponseBase
├── extId            ← OMXUtils.generateTrackingID()   [Always]
├── ResponseCode     ← $eventResponse/ResponseCode     [Conditional]
├── ResponseMessage  ← $eventResponse/ResponseMsg      [Conditional]
├── CompletionStatus ← $eventResponse/CompletionStatus [Conditional]
└── ReferenceId      ← $eventResponse/RefID            [Conditional]
```

Fan-in: `count(Response[tib:right(tib:trim(ResponseCode),3)="000"]) == RequestCount`

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
