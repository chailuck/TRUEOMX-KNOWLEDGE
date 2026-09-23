# Request_OMX_POPULATE_OFFER

## §1 Overview & Purpose

**OMX_POPULATE_OFFER** is a pure in-memory offer injection rule that traverses the full customer hierarchy (ParentOU & ChildOU, Agreement & Subscriber levels) and injects offer concepts directly into BE working memory. It is the counterpart to `OMX_INJECT_OFFER` but uses a prefixed parameter format (`OFFER=key=value,…`) instead of bare CSV, and supports all four customer hierarchy scopes.

The rule reads an `OFFER=…` prefixed parameter string, parses the key-value pairs, and conditionally creates either `AgreementOffers` or `SubscriberOffers` concept instances at every matching node in the customer tree. Duplicate checking (controlled by `checkDup=1`) prevents double-injection of the same SOC.

No ESB call is made. The rule writes directly to BE working memory and calls `NextActivity()` upon completion.

> Found in `Rules/OMConsumers/OMXOM/` — OMX orchestration rule (not OMXFM). No response rulefunction exists.

---

## §2 Rule Metadata

| Attribute | Value |
|-----------|-------|
| Rule name | `Rules.OMConsumers.OMXOM.OMX_POPULATE_OFFER` |
| Author | DESKTOP-995HR2V |
| Priority | 5 |
| forwardChain | true |
| Backend | None — in-memory only |
| Fan-in | None — calls `NextActivity()` directly |
| Response handler | None |
| Rule file | `OMX-OM/Rules/OMConsumers/OMXOM/OMX_POPULATE_OFFER.rule` |

---

## §3 Working Memory

| Variable | Type | Role |
|----------|------|------|
| `orderRequest` | `Concepts.OrderRequest.OrderRequest` | Full order — customer hierarchy read & offer arrays written |
| `orderCurrentActivity` | `Concepts.OM.ProcessConfig.Activity` | Provides Parameter, PreExecCheck, ActivityID, and activity progression |

---

## §4 Rule Conditions (WHEN)

| # | Condition |
|---|-----------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` |
| 2 | `orderCurrentActivity.ActivityID == "OMX_POPULATE_OFFER"` |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_POPULATE_OFFER"` |
| 4 | `orderCurrentActivity.Status == "WAITING"` |

---

## §5 Execution Flow

1. Validate `Parameter@length > 0` — throw `DATA_ISSUE` if no parameters provided
2. Extract OFFER string via `GetActivityParameterValueFromKey(orderCurrentActivity, "OFFER")`
3. Split OFFER string on `","` and parse key=value pairs → populate `offerAction`, `offerName`, `soc`, `serviceType`, `offerLevel`, `checkDup`, `source`
4. Validate required fields: `soc`, `serviceType`, `offerAction`, `offerLevel` — throw `DATA_ISSUE` if any are blank
5. Traverse `ParentOU[]` loop:
   - If `offerLevel=="OU"`: evaluate per-Agreement PreExecCheck, check duplicate, create `AgreementOffers` concept and append to `pagm.Offers[]`
   - If `offerLevel=="SUB"`: evaluate per-Subscriber PreExecCheck, check duplicate, create `SubscriberOffers` concept and append to `psub.SubscriberOffers[]`
6. Traverse `ChildOU[]` loop (same OU/SUB logic for ChildOU agreements and subscribers)
7. Call `NextActivity(orderRequest, orderCurrentActivity)`
8. Send completion log event: AUDIT_TRACE = `"OMX_POPLUATE_OFFER Completed."` ⚠ (typo in source)

> **Note:** The `PreExecCheck` is evaluated per-agreement and per-subscriber (not once globally). This allows conditional offer injection per customer entity.

---

## §7 Data Extraction — OFFER= Parameter Parsing

The activity parameter is retrieved using the key `"OFFER"` — distinct from `OMX_INJECT_OFFER` which uses bare CSV. Example parameter value in ProcessConfig:

```text
OFFER=soc=16210001,action=ADD,offerName=TRUE_PACKAGE_X,serviceType=VOICE,level=SUB,checkDup=1,source=CCBS
```

| Parameter Key | Variable | Required | Description |
|---------------|----------|----------|-------------|
| `soc` | `soc` | [Required] | Service offering code for the offer to inject |
| `action` | `offerAction` | [Required] | Offer action (ADD, REMOVE, etc.) |
| `offerName` | `offerName` | [Optional] | Human-readable offer name; used in duplicate check alongside soc |
| `serviceType` | `serviceType` | [Required] | Service type (e.g., VOICE, DATA) |
| `level` | `offerLevel` | [Required] | `"OU"` → inject into Agreement.Offers; `"SUB"` → inject into SubscriberOffers |
| `checkDup` | `checkDup` | [Optional] | Default `"0"`. Set to `"1"` to skip injection if offer already exists in CCBS offers |
| `source` | `source` | [Optional] | Value written to `ExtendedInfo[Name='FE_OR_CCBS'].Value`. Defaults to `"INJECT_OFFER"` if blank |

> **Difference from OMX_INJECT_OFFER:** `OMX_INJECT_OFFER` receives the parameter as direct comma-separated CSV. `OMX_POPULATE_OFFER` wraps all fields under the key `OFFER` using `GetActivityParameterValueFromKey()`, allowing multiple named parameter groups to coexist in the same activity definition.

---

## §8 System & Integration Dependencies

### §8.1 Order Type Dependencies

Used in ACTIVATION flow at steps 3, 4, 90, and 120 — typically for injecting initial service offers, CUG offers, or post-activation supplementary offers into the customer hierarchy during new subscriber creation.

### §8.2 ESB / JMS Channel Dependencies

None. No ESB or JMS call is made. The rule manipulates BE working memory only.

### §8.3 Backend API

None — pure in-memory operation.

### §8.4 BE Working Memory Written

| Object | Field Written | Type | Condition |
|--------|---------------|------|-----------|
| `ParentOU[p].Agreement.Offers[n]` | New `AgreementOffers` appended | Concept array append | `offerLevel=="OU"` AND not duplicate |
| `ParentOU[p].Subscriber[ps].SubscriberOffers[n]` | New `SubscriberOffers` appended | Concept array append | `offerLevel=="SUB"` AND not duplicate |
| `ChildOU[c].Agreement.Offers[n]` | New `AgreementOffers` appended | Concept array append | `offerLevel=="OU"` AND not duplicate |
| `ChildOU[c].Subscriber[cs].SubscriberOffers[n]` | New `SubscriberOffers` appended | Concept array append | `offerLevel=="SUB"` AND not duplicate |

### §8.5 ExtendedInfo Fields

| Name | Value | Required | Where Used |
|------|-------|----------|------------|
| `FE_OR_CCBS` | `$source` (or `"INJECT_OFFER"` default) | Always written | Identifies the offer source system in downstream rules |

### §8.6 Audit Logger Event

| Direction | OPERATION_NAME | AUDIT_TRACE |
|-----------|----------------|-------------|
| [LOG] Completion | `"OMX_POPLUATE_OFFER"` ⚠ Typo | `"OMX_POPLUATE_OFFER Completed."` |

> **Typo in source:** `OPERATION_NAME` is hardcoded as `"OMX_POPLUATE_OFFER"` (missing 'L') — should be `"OMX_POPULATE_OFFER"`. This affects audit log queries that filter by operation name.

---

## §9 Detailed Object Construction

### §9.1 Scope Overview

The rule creates two types of concepts, both using identical XSLT templates differing only in type path:

| Scope | Concept Type | Target Array | offerLevel guard |
|-------|-------------|--------------|-----------------|
| ParentOU Agreement | `Concepts.OrderRequest.OrderElements.AgreementOffers` | `pagm.Offers[]` | `"OU"` |
| ParentOU Subscriber | `Concepts.OrderRequest.OrderElements.SubscriberOffers` | `psub.SubscriberOffers[]` | `"SUB"` |
| ChildOU Agreement | `Concepts.OrderRequest.OrderElements.AgreementOffers` | `cagm.Offers[]` | `"OU"` |
| ChildOU Subscriber | `Concepts.OrderRequest.OrderElements.SubscriberOffers` | `csub.SubscriberOffers[]` | `"SUB"` |

### §9.2 Duplicate Check Logic

Before creating a concept, the rule evaluates:

```xpath
$checkDup="1" and count($scope/Offers[(OfferName=$offerName or Soc=$soc) and ExtendedInfo[Name="FE_OR_CCBS"]/Value="CCBS"]) > 0
```

If `isDuplicate=true`, the injection is skipped for that scope. The check uses `offerName OR soc` match — either field matching an existing CCBS offer triggers skip.

### §9.3 AgreementOffers / SubscriberOffers XSLT Template

Both concept types use identical field mapping. Unescaped XSLT:

```xml
<xsl:stylesheet version="1.0" xmlns:OMXUtils="www.tibco.com/be/custom/OMXUtils"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:param name="offerName"/>
  <xsl:param name="serviceType"/>
  <xsl:param name="soc"/>
  <xsl:param name="offerAction"/>
  <xsl:param name="source"/>
  <xsl:template match="/">
    <createObject>
      <object extId="concat(OMXUtils:generateTrackingID(),':INJECT_OFFER')">
        <OfferName><xsl:value-of select="$offerName"/></OfferName>
        <ServiceType><xsl:value-of select="$serviceType"/></ServiceType>
        <Soc><xsl:value-of select="$soc"/></Soc>
        <Action><xsl:value-of select="$offerAction"/></Action>
        <ExtendedInfo extId="OMXUtils:generateTrackingID()">
          <Name>FE_OR_CCBS</Name>
          <!-- xsl:choose: if length($source)>0 use $source else 'INJECT_OFFER' -->
          <Value>[conditional: $source or 'INJECT_OFFER']</Value>
        </ExtendedInfo>
      </object>
    </createObject>
  </xsl:template>
</xsl:stylesheet>
```

---

## §10 XSLT Field Mapping Tree

```text
createObject
└── object
    ├── @extId             ← concat(OMXUtils:generateTrackingID(), ':INJECT_OFFER')  [Always]
    ├── OfferName          ← $offerName                                              [Always]
    ├── ServiceType        ← $serviceType                                            [Always]
    ├── Soc                ← $soc                                                   [Always]
    ├── Action             ← $offerAction                                            [Always]
    └── ExtendedInfo
        ├── @extId         ← OMXUtils:generateTrackingID()                          [Always]
        ├── Name           ← 'FE_OR_CCBS'                                           [Always — literal]
        ├── Value          ← $source           [Conditional: string-length($source)>0]
        └── Value          ← 'INJECT_OFFER'   [Conditional: otherwise (source is blank)]
```

---

## §11 Audit Logging

| Log | PROCESS_ID | OPERATION_NAME | AUDIT_TRACE |
|-----|-----------|----------------|-------------|
| ~~Start~~ | — | — | **Missing — no start log** |
| Complete | `concat(pid, "_RES")` | `"OMX_POPLUATE_OFFER"` ⚠ Typo | `"OMX_POPLUATE_OFFER Completed."` |

> **Issues:**
> 1. **No start log** — unlike most FM rules, this rule does NOT log a "Started" event.
> 2. **OPERATION_NAME typo** — `OMX_POPLUATE_OFFER` (missing second 'L'). Audit log queries filtered on exact operation name will miss these events.

---

## §12 Activity Status Management

| Transition | Condition | Action |
|------------|-----------|--------|
| WAITING → COMPLETED | All processing succeeds | `NextActivity(orderRequest, orderCurrentActivity)` |
| WAITING → ERROR | Exception thrown | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

> Unlike most OMXFM rules, there is no explicit SkipActivity call — the PreExecCheck is evaluated per-entity within the loops. The activity itself always completes.

---

## §13 Exception Handling

| Condition | Action |
|-----------|--------|
| `Parameter@length == 0` | `throw Exception.newException("DATA_ISSUE", "Missing require param.", null)` |
| `soc` is blank or null | `throw Exception.newException("DATA_ISSUE", "Missing require param soc", null)` |
| `serviceType` is blank or null | `throw Exception.newException("DATA_ISSUE", "Missing require param serviceType", null)` |
| `offerAction` is blank or null | `throw Exception.newException("DATA_ISSUE", "Missing require param action.", null)` |
| `offerLevel` is blank or null | `throw Exception.newException("DATA_ISSUE", "Missing require param offerLevel.", null)` |
| Any other exception | `HandleActivityException(orderRequest, orderCurrentActivity, ae, "")` |

---

## §14 Helper Functions Reference

| Function | Purpose |
|----------|---------|
| `RuleFunctions.Helpers.GetActivityParameterValueFromKey(activity, "OFFER")` | Extracts the value after key `OFFER` from the activity's Parameter list |
| `RuleFunctions.Helpers.BRMS.IsBlankOrStringNull(value)` | Returns true if string is null, empty, or whitespace-only |
| `RuleFunctions.Helpers.GetXMLForAgreement(orderRequest, refId)` | Serializes a ParentOU Agreement entity to XML for XPath evaluation |
| `RuleFunctions.Helpers.GetXMLForSubscriber(orderRequest, refId)` | Serializes a ParentOU Subscriber to XML for XPath evaluation |
| `RuleFunctions.Helpers.GetXMLForAgreementInChildOU(orderRequest, refId, pOuRefId)` | Serializes a ChildOU Agreement to XML for XPath evaluation |
| `RuleFunctions.Helpers.GetXMLForSubscriberInChildOU(orderRequest, refId, pOuRefId)` | Serializes a ChildOU Subscriber to XML for XPath evaluation |
| `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` | Advances the process flow to the next configured activity |
| `RuleFunctions.Helpers.HandleActivityException(orderRequest, activity, ae, "")` | Handles exception — updates activity status, routes to error handling |
| `OMXUtils:generateTrackingID()` | Generates a unique tracking ID for new concept extId values |

---

## §15 Function Dependency Tree

```text
OMX_POPULATE_OFFER
├── GetActivityParameterValueFromKey(orderCurrentActivity, "OFFER")  [param extraction]
├── String.split(paramString, ",")                                    [CSV parse]
├── BRMS.IsBlankOrStringNull(soc/serviceType/offerAction/offerLevel)  [validation]
├── for pOu in ParentOU[]
│   ├── [if offerLevel=="OU"] GetXMLForAgreement(orderRequest, pagm.RefId)
│   │   ├── XPath.execute("/("+chkXPath+")", sXML, ns)               [PreExecCheck]
│   │   ├── XPath.evalAsBoolean(duplicate check XPath)
│   │   └── Instance.createInstance("xslt://.../AgreementOffers", ...)
│   │       └── append to pagm.Offers[]
│   └── [if offerLevel=="SUB"] for psub in Subscriber[]
│       ├── GetXMLForSubscriber(orderRequest, psub.RefId)
│       ├── XPath.execute(chkXPath)
│       ├── XPath.evalAsBoolean(duplicate check)
│       └── Instance.createInstance("xslt://.../SubscriberOffers", ...)
│           └── append to psub.SubscriberOffers[]
├── for cou in ChildOU[]
│   ├── [offerLevel=="OU"] GetXMLForAgreementInChildOU(...)           [same OU logic]
│   └── [offerLevel=="SUB"] GetXMLForSubscriberInChildOU(...)         [same SUB logic]
├── NextActivity(orderRequest, orderCurrentActivity)                  [advance flow]
├── Event.Ext.sendEventImmediate(Logger — Completion)                 [audit log]
└── HandleActivityException(...)                                      [catch]
```

---

## §17 Migration Notes

### Functional Requirements

| ID | Requirement |
|----|-------------|
| R1 | Parse `OFFER=key=value,…` prefixed parameter format (not bare CSV) |
| R2 | Validate required params: soc, serviceType, action, level — throw DATA_ISSUE if missing |
| R3 | For `level=OU`: inject offer into Agreement.Offers for all POU and COU agreements |
| R4 | For `level=SUB`: inject offer into SubscriberOffers for all POU and COU subscribers |
| R5 | Evaluate per-entity PreExecCheck (per Agreement or per Subscriber) before injecting |
| R6 | When `checkDup=1`, skip if offer with same soc or offerName already exists with FE_OR_CCBS=CCBS |
| R7 | Write `ExtendedInfo[Name='FE_OR_CCBS'].Value` = source param (or 'INJECT_OFFER' if blank) |
| R8 | No backend call — pure in-memory operation |

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| OPERATION_NAME typo `"OMX_POPLUATE_OFFER"` in audit log | [HIGH] | Fix the hardcoded string in the XSLT; update audit log dashboards/queries |
| No start audit log — only completion log exists | [MEDIUM] | Add start log event before the traversal loop in migration target |
| Per-entity PreExecCheck evaluation — XPath executed N times | [MEDIUM] | Cache XPath result for static conditions; document expected N for capacity planning |
| Duplicate check uses offerName OR soc — partial match may prevent valid injections | [MEDIUM] | Review business intent; consider soc-only match to avoid false-duplicate detection |
| ExtendedInfo extId generated per-concept but no relationship tracking | [LOW] | Document as known OMX pattern — consistent with other offer rules |
| ChildOU loop traversal depth fixed at 1 level | [LOW] | Verify max organizational depth; extend if deeper nesting occurs |

---

## §18 Full Source Code

```java
/**
 * @description 
 * @author DESKTOP-995HR2V
 */
rule Rules.OMConsumers.OMXOM.OMX_POPULATE_OFFER {
  attribute { priority = 5; forwardChain = true; }
  declare {
    Concepts.OrderRequest.OrderRequest orderRequest;
    Concepts.OM.ProcessConfig.Activity orderCurrentActivity;
  }
  when {
    orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName;
    orderCurrentActivity.ActivityID == "OMX_POPULATE_OFFER";
    orderRequest.ProcessFlow.NextActivityID == "OMX_POPULATE_OFFER";
    orderCurrentActivity.Status == "WAITING";
  }
  then {
    try {
      // Validate parameters exist
      if(orderCurrentActivity.Parameter@length == 0)
        throw Exception.newException("DATA_ISSUE", "Missing require param.", null);

      // Extract OFFER= prefixed parameter block and parse key=value pairs
      String paramString = GetActivityParameterValueFromKey(orderCurrentActivity, "OFFER");
      String[] paramStringList = String.split(paramString, ",");
      // ... parse: action, offerName, soc, serviceType, level, checkDup, source

      // Validate required fields: soc, serviceType, offerAction, offerLevel

      // Traverse ParentOU hierarchy
      for (int p = 0; p < pOuLen; p++) {
        // POU Agreement scope (offerLevel=="OU")
        //   evaluate per-Agreement PreExecCheck
        //   check duplicate: checkDup=1 and existing offers match soc or offerName
        //   Instance.createInstance("xslt://.../AgreementOffers"
        //     [XSLT creates AgreementOffers concept — see §9.3])
        //   pagm.Offers[n] = agreeOfferConcept;

        // POU Subscriber scope (offerLevel=="SUB")
        //   evaluate per-Subscriber PreExecCheck
        //   Instance.createInstance("xslt://.../SubscriberOffers"
        //     [XSLT creates SubscriberOffers concept — see §9.3])
        //   psub.SubscriberOffers[n] = subscriberOfferConcept;

        // ChildOU Agreement scope (offerLevel=="OU") — same logic
        // ChildOU Subscriber scope (offerLevel=="SUB") — same logic
      }

      NextActivity(orderRequest, orderCurrentActivity);
      // sendEventImmediate: Logger completion
      // ⚠ OPERATION_NAME="OMX_POPLUATE_OFFER" (typo — missing 'L')
    } catch (Exception ae) {
      HandleActivityException(orderRequest, orderCurrentActivity, ae, "");
    }
  }
}
```

## §19 Response Message Rule

No response rulefunction exists for `OMX_POPULATE_OFFER`. This is an OMXOM in-memory rule — it completes synchronously, writes offer concepts to working memory, and calls `NextActivity()` directly. There is no JMS response or backend reply to wait for.

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
