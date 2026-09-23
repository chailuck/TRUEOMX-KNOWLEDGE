# Request_ATS_COMPLETED_CAMPAIGN

## §1 Overview & Purpose

**ATS_COMPLETED_CAMPAIGN** notifies ATS that campaign registration is complete by sending `requestName="UpdateCompletedCampaign"`. Uses the same `ATS_SUBMIT_CAMPAIGN` event as FM28 but simpler payload — no subscriber loop, no customer name fields.

> **Fire-and-forget:** `Event.Ext.sendEventImmediate` + manual `RequestCount++`. Fan-in: `count("000") == RequestCount`.

> **Depends on FM28:** Uses `ExtInfo[TRUELIFE_ID].Value` written by FM28 response. If FM28 was skipped, TRUELIFE_ID is empty and ATS may reject.

> **No write-back to order:** ResponseBase (4 fields) only. Campaign state tracked in ATS.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_ATS_COMPLETED_CAMPAIGN` |
| Author | Chayatorn P. |
| Priority | 5 |
| forwardChain | true |
| Backend | ATS |
| Event type | `Events.OMConsumers.OMXFM.Request.ATS_SUBMIT_CAMPAIGN` (shared with FM28) |
| Send pattern | `Event.Ext.sendEventImmediate(reqEvent)` — FIRE-AND-FORGET |
| RequestCount | `if(!isActResub) RequestCount++` |
| Fan-in | `count(Response[ResponseCode suffix "000"]) == RequestCount` |
| Key inputs | `ExtInfo[CAMPAIGN_CODE].Value`; `ExtInfo[TRUELIFE_ID].Value` (from FM28) |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| requestName distinction | `"UpdateCompletedCampaign"` — different from FM28's `"RegisterCampaign"` |
| truelifeId | `ExtInfo[TRUELIFE_ID].Value` — required by ATS for campaign lookup |
| oneBillFlag | Hardcoded `"N"` — always false for ACTIVATION flow |
| productList minimal | Single entry with only `productState="Active"` |
| No CES field | Unlike CCBS-family FMs; no CES header |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority/JMSCorrelationID/OrderID/RefID ← standard fields
├── UserName/PassWord                           ← [Credential-gated]
├── OrderType                                   ← OrderData.OrderType   [Conditional]
└── payload → ns2:submitCampaignReq
    ├── channel         ← "OMX"                 [Hardcoded]
    ├── requestName     ← "UpdateCompletedCampaign" [Hardcoded]
    └── campaignInfo
        ├── campaignCode← ExtInfo[CAMPAIGN_CODE].Value    [Always]
        ├── truelifeId  ← ExtInfo[TRUELIFE_ID].Value      [Always — from FM28]
        ├── state       ← "Active"                        [Hardcoded]
        ├── oneBillFlag ← "N"                             [Hardcoded]
        └── productList
            └── productState ← "Active"                  [Hardcoded]

NOTE: No subscriber loop. No applyChannel/dealerId. No CES.
```

---

## §15 Function Dependency Tree

```text
Request_ATS_COMPLETED_CAMPAIGN
├── [PreExecCheck if length > 0]
├── if chkRes == "true":
│   ├── createEvent(ATS_SUBMIT_CAMPAIGN, XSLT with CAMPAIGN_CODE + TRUELIFE_ID)
│   ├── sendEventImmediate(reqEvent)  ← FIRE-AND-FORGET
│   ├── if(!isActResub): RequestCount++
│   └── Logger REQ
└── SkipActivity("4") or GetActivityStatusString + SendDataToDB

Response_ATS_COMPLETED_CAMPAIGN
├── createInstance(ResponseBase std 4) → currActivity.Response[n]
├── [NO write-back to order]
├── Logger RES
└── count("000") == RequestCount → "true"/"false"
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| TRUELIFE_ID dependency on FM28 — empty if FM28 skipped | [MEDIUM] | Add PreExecCheck guard for TRUELIFE_ID presence |
| oneBillFlag hardcoded "N" | [LOW] | Review for TRUE ONE BILL scenarios |
| Shared event with FM28 — schema change affects both | [LOW] | Document shared event; coordinate changes |

---

## §19 Response Message Rule

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | ResponseBase (std 4) | Always |

No write-back to order data. Fan-in: `count(Response[ResponseCode suffix "000"]) == RequestCount`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
