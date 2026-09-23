# Request_CCBS_CREATE_GROUP

## §1 Overview & Purpose

**CCBS_CREATE_GROUP** creates a user group in CCBS. Group attributes come from ProcessConfig `Parameter` values. The group name is `ExtInfo[TRUELIFE_ID].Value` (written by FM28) prefixed with "TF_".

> **Mandatory parameters:** `Parameter@length == 0` throws `DATA_ISSUE` immediately — GROUP_TYPE, GROUP_DESC, GROUP_IDENTIFY required.

> **Fire-and-forget:** `Event.Ext.sendEventImmediate` + manual `RequestCount++`. Fan-in: `count("000") == RequestCount`.

> **Response write-back:** `OrderData.ExtendedInfo[Name="GROUP_ID"]` ← `createGroupRes.userGroupIdInfo.GroupId`.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXFM.Request.Request_CCBS_CREATE_GROUP` |
| Author | DESKTOP-995HR2V |
| Priority | 5 |
| forwardChain | true |
| Backend | CCBS |
| Event type | `Events.OMConsumers.OMXFM.Request.CCBS_CREATE_GROUP` |
| Send pattern | `Event.Ext.sendEventImmediate(reqEvent)` — FIRE-AND-FORGET |
| RequestCount | `if(!isActResub) RequestCount++` |
| Fan-in | `count(Response[ResponseCode suffix "000"]) == RequestCount` |
| Mandatory guard | `Parameter@length == 0` → throw DATA_ISSUE |
| CES | Yes — forwarded in event header |
| Input key | `ExtInfo[TRUELIFE_ID].Value` — from FM28 response |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| Parameter guard | Immediate throw if `Parameter@length == 0` — before any XPath |
| Parameter reads | `GetActivityParameterValueFromKey` × 3: GROUP_TYPE, GROUP_DESC, GROUP_IDENTIFY |
| groupName | `XPath.evalAsString(OrderData/ExtendedInfo[Name="TRUELIFE_ID"]/Value)` — depends on FM28 |
| GroupName construction | `concat("TF_", $groupName)` — TF_ prefix hardcoded |
| ActivityReason | `"SYSREQ"` hardcoded |

---

## §10 XSLT Field Mapping

```text
createEvent → event
├── JMSPriority/JMSCorrelationID/OrderID/RefID ← standard fields
├── UserName/PassWord                           ← [Credential-gated]
├── OrderType                                   ← OrderData.OrderType   [Conditional]
├── CES                                         ← OrderData.CES         [Conditional]
└── payload → ns2:createGroupReq
    ├── userGroupInfo
    │   ├── GroupDescription ← $groupDesc       (Parameter GROUP_DESC)  [Always]
    │   ├── GroupIdentifier  ← $groupIdentify   (Parameter GROUP_IDENTIFY) [Always]
    │   ├── GroupName        ← concat("TF_", $groupName)                [Always]
    │   └── GroupType        ← $groupType       (Parameter GROUP_TYPE)  [Always]
    └── activityInfo
        └── ActivityReason   ← "SYSREQ"                                 [Hardcoded]
```

---

## §15 Function Dependency Tree

```text
Request_CCBS_CREATE_GROUP
├── if Parameter@length == 0: throw DATA_ISSUE
├── groupType/groupDesc/groupIdentify ← GetActivityParameterValueFromKey × 3
├── groupName ← XPath.evalAsString(ExtInfo[TRUELIFE_ID].Value)
├── [PreExecCheck if length > 0]
├── if chkRes == "true":
│   ├── createEvent(CCBS_CREATE_GROUP, XSLT)
│   ├── sendEventImmediate(reqEvent)
│   ├── if(!isActResub): RequestCount++
│   └── Logger REQ
└── SkipActivity("4") or GetActivityStatusString + SendDataToDB

Response_CCBS_CREATE_GROUP
├── createInstance(ResponseBase std 4) → currActivity.Response[n]
├── createInstance(OrderDataExtendedInfo: GROUP_ID=createGroupRes.GroupId)
│   → orderRequest.OrderData.ExtendedInfo[n]
├── Logger RES
└── count("000") == RequestCount → "true"/"false"
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Depends on TRUELIFE_ID from FM28 — implicit FM ordering | [MEDIUM] | Document and validate ProcessConfig sequence |
| "TF_" prefix hardcoded | [LOW] | Externalise to global variable or parameter |
| DATA_ISSUE hard fail on missing Parameter | [LOW] | Document required ProcessConfig configuration |

---

## §19 Response Message Rule

| Write Target | Source | Condition |
|-------------|--------|-----------|
| `currActivity.Response[]` | ResponseBase (std 4) | Always |
| `OrderData.ExtendedInfo[GROUP_ID].Value` | `createGroupRes.userGroupIdInfo.GroupId` | Conditional |

Fan-in: `count(Response[ResponseCode suffix "000"]) == RequestCount`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
