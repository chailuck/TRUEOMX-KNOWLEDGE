# Request_ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN

## §1 Overview & Purpose

Sends a **RemoveCampaign** request to the ATS CampaignRule service for each `BundleInfo` entry in the order. For MobileSoftBundle cancellations, informs ATS to remove the campaign association and receives back a `CampaignRuleResponse` identifying which subscriber offers should be updated (`ATS_REMOVE` or `ATS` tags).

Used in **CANCEL_SUBSCRIBER** process — Step 25 — gated on MobileSoftBundle presence.

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule | `Rules.OMConsumers.OMXFM.Request.Request_ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN` |
| Priority | 5 |
| ForwardChain | true |
| Author | DESKTOP-995HR2V |
| Target | ATS / CampaignRule service |

## §3 Working Memory

| Variable | Type |
|----------|------|
| `orderRequest` | Concepts.OrderRequest.OrderRequest |
| `orderCurrentActivity` | Concepts.OM.ProcessConfig.Activity |

## §4 Rule Conditions (WHEN)

1. `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName`
2. `orderCurrentActivity.ActivityID == "ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN"`
3. `orderRequest.ProcessFlow.NextActivityID == "ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN"`
4. `orderCurrentActivity.Status == "WAITING"`

## §5 Execution Flow

1. Check resubmit flag
2. Evaluate PreExecCheck XPath
3. Get BundleInfo count → iterate each BundleInfo entry
4. Per bundle: create & send `ATS_CAMPAIGN_RULE` event, increment `RequestCount`
5. Send audit log (`_REQ`)
6. If requests sent: Status="1", SendDataToDB; else SkipActivity("4")

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies
CANCEL_SUBSCRIBER (types 10, 12, 14) with MobileSoftBundle BundleInfo entries present.

### §8.2 ESB / JMS Channel

| Direction | Event | Purpose |
|-----------|-------|---------|
| [OUTBOUND] | ATS_CAMPAIGN_RULE | Remove campaign per BundleInfo |
| [OUTBOUND] | Logger | Request audit (_REQ) |

### §8.3 Backend API
System: **ATS** | Operation: **RemoveCampaign** | Schema: `ns:CampaignRuleRequest`

### §8.5 ExtendedInfo Fields

| Key | Usage |
|-----|-------|
| `FE_OR_CCBS` | Determines isChange flag: ATS=N, otherwise=Y |
| `TR_CONTRACT_IND` | Gates socListInfo inclusion |
| `TR_ORIG_CONTRACT_EXPIRE_DATE` | Contract date check |

## §9 Payload Build

**Schema root:** `ns:CampaignRuleRequest`

| Field | Source | Condition |
|-------|--------|-----------|
| `ns:channel` | "OMX-Mobile" | Always |
| `ns:requestName` | "RemoveCampaign" | Always |
| `ns:function` | BundleInfo[$i+1]/ConvergenceType | Always |
| `ns:convergenceCode` | BundleInfo[$i+1]/CampaignCode | Always |
| `ns:productList` | For each Subscriber with matching CampaignCode | Loop |
| `ns:productType` | "TMV" | Always |
| `ns:accessNumber` | Subscriber/MSISDN | Always |
| `ns:familyType` | ExtendedInfo[FamilyType]/Value | If exists |
| `ns:isChange` | "N" (ATS) / "Y" (other) | Always |
| `ns:rcRate` | SubscriberOffers[ST=80,CCBS]/OfferRate | Conditional |
| `ns:socListInfo` | Offers with TR_CONTRACT_IND=Y & valid date | Conditional |

## §10 XSLT Field Mapping Tree

```text
createEvent
└── event
    ├── @extId          ← OMXUtils:generateTrackingID()           [Always]
    ├── JMSPriority     ← OrderPriority                           [Always]
    ├── JMSCorrelationID ← OMXTrackingId                         [Always]
    ├── OrderID         ← OrderData/OrderID                       [Always]
    ├── RefID           ← Customer/RefId                          [Always]
    ├── OrderType       ← OrderData/OrderType                     [Always]
    └── payload
        └── ns:CampaignRuleRequest
            ├── ns:channel          ← "OMX-Mobile"               [Always]
            ├── ns:requestName      ← "RemoveCampaign"           [Always]
            ├── ns:function         ← BundleInfo[$i+1]/ConvergenceType
            ├── ns:convergenceCode  ← BundleInfo[$i+1]/CampaignCode
            └── ns:productList [for each matching Subscriber]
                ├── ns:productType  ← "TMV"
                ├── ns:accessNumber ← MSISDN
                ├── ns:familyType   ← ExtendedInfo[FamilyType]/Value  [Conditional]
                ├── ns:isChange     ← "N"(ATS) / "Y"(other)
                └── ns:tmhProductInfo
                    ├── ns:rcRate       [Conditional: SubscriberOffers[ST=80,CCBS]]
                    ├── ns:nextRcRate   ← $nextRCnextPP (null)
                    ├── ns:pricePlan    [Conditional: OfferName exists]
                    └── ns:socListInfo  [Conditional: TR_CONTRACT_IND=Y & valid date]
```

## §11 Audit Logging

| Field | Value |
|-------|-------|
| OPERATION_NAME | ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN |
| AUDIT_TRACE | "Request Sent for ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN" |
| PROCESS_ID | concat(pid, "_REQ") |

## §12 Activity Status

| Condition | Status |
|-----------|--------|
| Requests sent | "1" (RUNNING) |
| Skipped | "4" (SKIPPED) |
| Exception | HandleActivityException |

## §17 Migration Notes

- **R1:** ATS CampaignRule service integration — verify ATS API compatibility in modern stack
- **R2:** Response updates BundleInfo.ConvergenceAction and SubscriberOffers.FE_OR_CCBS — downstream steps depend on these values
- **R3:** Complex bundle iteration — ensure modern implementation handles multi-bundle orders

**Risk:** [MEDIUM] — ATS campaign removal before CCBS cancel; order-of-operations matters.

## §19 Response Message Rule

**Overview:** Parses `CampaignRuleResponse`, extracts `convergenceAction` and `benefitCampaignList` to update `BundleInfo.ConvergenceAction` and `SubscriberOffers.FE_OR_CCBS` (ATS_REMOVE or ATS).

**Fan-in:** `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"]) == currActivity.RequestCount`

**Response audit:** OPERATION_NAME="ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN", AUDIT_TRACE="Response received for ATS_CAMPAIGN_RULE_REMOVE_CAMPAIGN"

---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
