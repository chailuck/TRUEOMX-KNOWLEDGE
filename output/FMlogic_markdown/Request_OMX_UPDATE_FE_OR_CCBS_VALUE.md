# Request_OMX_UPDATE_FE_OR_CCBS_VALUE

## §1 Overview & Purpose

**OMX_UPDATE_FE_OR_CCBS_VALUE** is an internal OMXOM rule that overwrites the `FE_OR_CCBS` ExtendedInfo value on every matching Offer and SubscriberOffer in the order. The new value is taken from `Parameter[0]` of the ProcessConfig Activity. No backend call is made — the rule mutates working memory in-memory only.

> **Mandatory parameter guard:** `Parameter@length == 0` throws `DATA_ISSUE` immediately.

> **Four iteration scopes:** ParentOU Agreement Offers, ParentOU Subscriber SubscriberOffers, ChildOU Agreement Offers, and ChildOU Subscriber SubscriberOffers — all processed in one pass.

> **Calls NextActivity directly** — no response rulefunction, no RequestCount, no fan-in. Same OMXOM pattern as FM24 and FM27.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXOM.OMX_UPDATE_FE_OR_CCBS_VALUE` |
| Author | DESKTOP-995HR2V |
| Namespace | OMXOM (internal — no backend call) |
| Priority | 5 |
| forwardChain | true |
| Backend | None — in-memory update only |
| Send pattern | None |
| RequestCount | Not used |
| Fan-in | Not used — `NextActivity` called directly |
| Mandatory guard | `Parameter@length == 0` → throw DATA_ISSUE |

---

## §7 Key Logic Patterns

| Pattern | Detail |
|---------|--------|
| Parameter as new value | `param = orderCurrentActivity.Parameter[0]` — written to all matching `FE_OR_CCBS` ExtInfo entries |
| Four iteration scopes | POU Agreement Offers → POU Subscriber SubscriberOffers → ChildOU Agreement Offers → ChildOU Subscriber SubscriberOffers |
| FE_OR_CCBS filter read | Before PreExecCheck, reads current `FE_OR_CCBS` value from each offer and passes it as `filter` to scoped XML helper |
| Scoped PreExecCheck helpers | `GetXMLForAgreementOfferFilterWithExtendedInfo`, `GetXMLForSubscriberOfferFilterWithExtendedInfo`, and ChildOU variants |
| Write-back | Inner loop finds `ExtendedInfo[Name=="FE_OR_CCBS"]`, sets `.Value = param`, then `break` |
| Skip vs NextActivity | `isSkipped=true` → `SkipActivity("4")`; `isSkipped=false` → `NextActivity` + audit log |

---

## §10 In-Memory Update Mapping

```text
For each POU[p]:
  → Agreement.Offers[o]:
      filter = XPath(pagof/ExtendedInfo[FE_OR_CCBS]/Value)
      GetXMLForAgreementOfferFilterWithExtendedInfo(orderRequest, pAgRefId, pagof.Soc, filter)
      if PreExecCheck passes:
          pagof.ExtendedInfo[FE_OR_CCBS].Value = param  ← write-back

  → Subscriber[ps].SubscriberOffers[o]:
      filter = XPath(psof/ExtendedInfo[FE_OR_CCBS]/Value)
      GetXMLForSubscriberOfferFilterWithExtendedInfo(orderRequest, pSubRefId, psof.Soc, filter)
      if PreExecCheck passes:
          psof.ExtendedInfo[FE_OR_CCBS].Value = param  ← write-back

  → ChildOU[c]:
      → Agreement.Offers[o]:
          GetXMLForAgreementOfferInChildOUFilterWithExtendedInfo
          if PreExecCheck passes: cagof.ExtendedInfo[FE_OR_CCBS].Value = param

      → Subscriber[cs].SubscriberOffers[o]:
          GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo
          if PreExecCheck passes: csof.ExtendedInfo[FE_OR_CCBS].Value = param

NOTE: No JMS event. No backend system.
```

---

## §15 Function Dependency Tree

```text
OMX_UPDATE_FE_OR_CCBS_VALUE
├── if Parameter@length == 0: throw DATA_ISSUE
├── param = Parameter[0]
├── for each ParentOU[p]:
│   ├── Agreement.Offers[o]: filter→GetXMLFor*→PreExecCheck→write FE_OR_CCBS
│   ├── Subscriber[ps].SubscriberOffers[o]: filter→GetXMLFor*→PreExecCheck→write FE_OR_CCBS
│   └── ChildOU[c]: Agreement.Offers + Subscriber.SubscriberOffers (same pattern)
├── if !isSkipped: NextActivity + Logger audit
└── else: SkipActivity("4")

No response rulefunction.
```

---

## §17 Migration Notes

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Four near-identical iteration scopes — duplication | [MEDIUM] | Consolidate into generic offer-update function |
| Only first FE_OR_CCBS ExtInfo entry updated per offer | [LOW] | Document one-entry-per-offer expectation |
| FE_OR_CCBS filter circular: reads then overwrites same field | [LOW] | Document PreExecCheck filter semantics |
| OMXOM namespace not in standard OMXFM lookup path | [LOW] | Document OMXOM rule mapping explicitly |

---

## §19 Response Message Rule

No response rulefunction. Internal OMXOM rule — `NextActivity` called directly after update. Audit Logger fires `AUDIT_TRACE="OMX_UPDATE_FE_OR_CCBS_VALUE Completed."`.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
