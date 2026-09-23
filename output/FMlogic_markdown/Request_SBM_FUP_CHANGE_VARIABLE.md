# Request_SBM_FUP_CHANGE_VARIABLE

## §1 Overview & Purpose

**SBM_FUP_CHANGE_VARIABLE** adds or removes a variable SOC on SBM's Fair-Use Policy (FUP) service. One `SBM_FUP_DO_SERVICE` event is sent per OU (ParentOU or ChildOU) that has matching Agreement Offers with `FE_OR_CCBS=="FE"` and a qualifying `SPECIAL_OFFER_INDICATOR`.

> **Mandatory parameter guard:** `Parameter[0]` must be `"ADD"` or `"REMOVE"` — any other value throws `DATA_ISSUE`. function_id dispatch: ADD→`104300008`; REMOVE→`104300009`.

> **Hard fail on no FUP offer:** If an OU passes PreExecCheck but has no matching offers, throws `OMX_DATA_ERROR: "There is no FUP offer. OU: <OUId>"`.

> **Fire-and-forget per OU:** `Event.Ext.sendEventImmediate` + manual `RequestCount++`. Fan-in: `count("000") == RequestCount`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_SBM_FUP_CHANGE_VARIABLE` |
| Author | RS33-BANDIT |
| Priority | 5 |
| forwardChain | true |
| Backend | SBM (FUP doService) |
| Event type (Request) | `Events.OMConsumers.OMXFM.Request.SBM_FUP_DO_SERVICE` |
| Event type (Response) | `Events.OMConsumers.OMXFM.Response.SBM_FUP_DO_SERVICE` |
| Send pattern | `Event.Ext.sendEventImmediate(reqEvent)` — FIRE-AND-FORGET per OU |
| RequestCount | `if(!isActResub) RequestCount++` per OU sent |
| Fan-in | `count(Response[ResponseCode suffix "000"]) == RequestCount` |
| Iteration scope | Agreement Offers per ParentOU AND per ChildOU |
| Mandatory parameter | `Parameter[0]` must be `"ADD"` or `"REMOVE"` |
| Resubmit | `PurgePendingRequestsBeforeResubmit` + isActResub RequestCount skip |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| ADD/REMOVE dispatch | `"ADD"` → function_id `"104300008"`; `"REMOVE"` → `"104300009"` |
| FE_OR_CCBS filter | Offer must have `FE_OR_CCBS=="FE"` to qualify |
| SPECIAL_OFFER_INDICATOR + BRMS | Must be non-empty AND in global `FUPAddVariableOfferInd` list (via `BRMS.AnyIn`) |
| fupElement accumulation | Matching OfferNames comma-joined: `fupElement = fupElement + "," + OfferName` |
| Hard fail on empty fupElement | If no matching offers in qualifying OU → throws `OMX_DATA_ERROR` |
| subAmount | `count($currPOU/Subscriber)` or `count($currCOU/Subscriber)` — subscriber count within OU |
| service_no | Set to `OUId` (same as fupID) |

---

## §10 XSLT Field Mapping (ParentOU; ChildOU uses $cOURefId/$cOUId/$currCOU)

```text
createEvent → event
├── JMSPriority/JMSCorrelationID/OrderID ← standard fields    [Conditional]
├── RefID           ← $pOURefId                                [Always]
├── OrderType       ← OrderData.OrderType                      [Conditional]
└── payload → ns:doServiceRequest
    └── ns:req
        ├── ns:function_id
        │   ├── param=="ADD"    → "104300008"                  [Dispatch]
        │   └── param=="REMOVE" → "104300009"                  [Dispatch]
        ├── ns:parameters
        │   ├── item [1]: key="fupID",       value=$pOUId      [Always]
        │   ├── item [2]: key="variableSOC", value=$fupElement [Always]
        │   └── item [3]: key="subAmount",   value=count(Subscriber) [Always]
        └── ns:service_no ← $pOUId                            [Always]

NOTE: No UserName/PassWord. No CES field.
```

---

## §15 Function Dependency Tree

```text
Request_SBM_FUP_CHANGE_VARIABLE
├── if isActResub: PurgePendingRequestsBeforeResubmit
├── if !(param=="ADD" || param=="REMOVE"): throw DATA_ISSUE
├── for each ParentOU[iPOU]:
│   ├── GetXMLForOU → PreExecCheck → chkRes
│   └── if chkRes=="true":
│       ├── scan Offers: filter FE_OR_CCBS=="FE" AND BRMS.AnyIn(FUPAddVariableOfferInd, specialOfferInd)
│       ├── fupElement = comma-join matching OfferNames
│       ├── if fupElement=="": throw OMX_DATA_ERROR
│       ├── createEvent(SBM_FUP_DO_SERVICE XSLT) + sendEventImmediate
│       ├── if(!isActResub): RequestCount++
│       └── Logger REQ
│   └── for each ChildOU[iCOU]: [same with cOU variants]
├── if !isSkipped: GetActivityStatusString + SendDataToDB
└── else: SkipActivity("4")

Response_SBM_FUP_CHANGE_VARIABLE
├── createInstance(SBM_FUP_DoServiceRes: std 4 + SBM fields) → currActivity.Response[n]
│   Extra fields: extra_xml, req_transaction_id, response_message, result_code, result_desc, result_namespace, transaction_id
├── Logger RES
└── count("000") == RequestCount → "true"/"false"
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Hard fail if no FUP offer found — entire order aborts | [HIGH] | Pre-validate offer data; document required SPECIAL_OFFER_INDICATOR |
| BRMS.AnyIn references `FUPAddVariableOfferInd` global variable | [MEDIUM] | Include in deployment validation; externalize to config |
| fupElement comma-delimited — SBM variableSOC multi-value handling | [LOW] | Verify SBM API spec; document delimiter |
| SBM_FUP_DoServiceRes non-standard concept (not ResponseBase) | [LOW] | Document SBM result fields; map to canonical model |

---

## §19 Response Message Rule

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | `SBM_FUP_DoServiceRes` (std 4 + SBM fields) | Always |
| `extra_xml`, `result_code`, `result_desc` | SBM doServiceReturn response | Conditional |
| `transaction_id`, `req_transaction_id` | SBM transaction identifiers | Conditional |

No write-back to order ExtendedInfo. Fan-in: `count(Response[ResponseCode suffix "000"]) == RequestCount`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
