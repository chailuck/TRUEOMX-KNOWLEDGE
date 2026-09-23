# Request_OMX_POPULATE_SUBS_FROM_EXTENDED_INFO

## §1 Overview & Purpose

**OMX_POPULATE_SUBS_FROM_EXTENDED_INFO** reconstructs working memory — a `ParentOU` concept with `Subscriber` children — from the pipe-delimited `EXISTING_SUB` ExtInfo stored in `OrderData.ExtendedInfo`. It is a data-hydration step restoring subscriber structure serialized earlier in the order flow.

> **No backend call:** Purely in-memory. Reads ExtInfo, creates concepts, appends to order, calls `NextActivity` directly. No outbound event and no response rulefunction.

> **EXISTING_SUB format:** Pipe-delimited `MSISDN=RefId` tokens (e.g., `0810001111=REF001|0820002222=REF002`). MSISDN = `substring-before(., "=")`, RefId/SubscriberId = `substring-after(., "=")`.

> **Write-back markers:** New ParentOU gets `ExtendedInfo Name="EXISTING_OU" Value="Y"`. Each Subscriber gets `ExtendedInfo Name="EXISTING_SUB" Value="Y"`. These signal to downstream rules that this OU/subscriber is an existing subscription.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXOM.OMX_POPULATE_SUBS_FROM_EXTENDED_INFO` |
| Author | DESKTOP-995HR2V |
| Priority | 5 |
| forwardChain | true |
| Backend | None — in-memory concept creation only |
| Send pattern | None — `Instance.createInstance(XSLT)` only |
| Fan-in | No response handler — calls `NextActivity` directly |
| Iteration | Single-pass: one ParentOU, N Subscribers |
| Input key | `OrderData.ExtendedInfo[Name="EXISTING_SUB"].Value` — pipe-delimited |
| Output | New `ParentOU` appended to `orderRequest.OrderData.Customer.ParentOU[]` |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| EXISTING_SUB parsing | `XPath.evalAsString(OrderData/ExtendedInfo[Name="EXISTING_SUB"]/Value)` → `String.tokenize(existingSub, "\|")` → `String[]` |
| ParentOU creation | `Instance.createInstance("xslt://ParentOU"...)` with extId = `"OU:"+generateTrackingID()` |
| Subscriber per token | XSLT `xsl:for-each select="$subList/elements"` — one Subscriber per pipe token |
| MSISDN / RefId split | MSISDN = `substring-before(., "=")`; RefId = SubscriberId = `substring-after(., "=")` |
| Marker flags | Subscriber: `EXISTING_SUB=Y`; ParentOU: `EXISTING_OU=Y` |
| Array append | `orderRequest.OrderData.Customer.ParentOU[length] = newOU` |

---

## §10 XSLT Field Mapping

```text
createObject → object
├── @extId              ← concat("OU:", OMXUtils:generateTrackingID())    [Always]
├── Subscriber          [for-each $subList/elements — one per token]
│   ├── @extId          ← concat("SUB:", OMXUtils:generateTrackingID())   [Always]
│   ├── MSISDN          ← substring-before(., "=")                        [Always]
│   ├── RefId           ← substring-after(., "=")                         [Always]
│   ├── SubscriberId    ← substring-after(., "=")                         [Always]
│   └── ExtendedInfo
│       ├── @extId      ← generateTrackingID()
│       ├── Name        ← "EXISTING_SUB"                                  [Hardcoded]
│       └── Value       ← "Y"                                             [Hardcoded]
└── ExtendedInfo        [ParentOU level marker]
    ├── @extId          ← generateTrackingID()
    ├── Name            ← "EXISTING_OU"                                   [Hardcoded]
    └── Value           ← "Y"                                             [Hardcoded]
```

---

## §15 Function Dependency Tree

```text
OMX_POPULATE_SUBS_FROM_EXTENDED_INFO (internal, no FM pattern)
├── Instance.getByExtIdByUri(NextActivityName, Activity) → nextAct
├── [PreExecCheck if length > 0]
│   └── Instance.serializeUsingDefaults(orderRequest) → sXML → XPath.execute(chkXPath) → chkRes
├── if chkRes == "true":
│   ├── XPath.evalAsString(OrderData/ExtendedInfo[Name="EXISTING_SUB"]/Value) → existingSub
│   ├── String.tokenize(existingSub, "|") → subList
│   ├── Instance.createInstance("xslt://ParentOU", subList) → newOU
│   ├── orderRequest.OrderData.Customer.ParentOU[length] = newOU
│   ├── Event.Ext.sendEventImmediate(Logger REQ)
│   └── isSkipped = false
├── if !isSkipped: NextActivity(orderRequest, orderCurrentActivity)
└── else: SkipActivity("4")
    [catch] → HandleActivityException
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| EXISTING_SUB pipe+equals format is implicit — no schema validation | [MEDIUM] | Document write format; consider structured XML in migration |
| Downstream rules depend on EXISTING_OU / EXISTING_SUB markers | [MEDIUM] | Document all consumers of these flags |
| RefId == SubscriberId — both from `substring-after`; format change breaks silently | [LOW] | Unit-test tokenization edge cases |
| New ParentOU is minimal — no Account/Agreement sub-objects | [LOW] | Document partial OU model produced by this rule |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
