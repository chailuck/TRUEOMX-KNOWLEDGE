# Request_OMX_POPULATE_MSIM_INFO

> Pure in-memory MultiSIM population — builds Master + Minor[] array in MultiSIMInfo concept from subscriber offer SocProperties (TR_MULTISIM_IND); two modes: normal offer-based and AUTO_CANCEL replication. No external system call.

**Type:** In-memory orchestration (no JMS/backend) | **Pattern:** Synchronous → NextActivity | **forwardChain:** true | **Author:** RS33-BANDIT | **Used in step:** 39

---

## §1 Overview & Purpose

Populates `Concepts.MultiSIM.MultiSIMInfo` (Master SIM + Minor[] array) for each subscriber that has at least one offer with a `TR_MULTISIM_IND` SocProperty. The rule operates in two modes controlled by the `SPC` activity parameter:

- **Normal mode** — iterates SubscriberOffers, classifies each by `TR_MULTISIM_IND` value (RES/REE vs RCM/RCE), creates MinorSIM accordingly
- **AUTO_CANCEL mode** (`SPC="AUTO_CANCEL"`) — iterates existing `Minor[]` with `Source="PREV_MSIM"`, creates new MinorSIM entries linked to matching CCBS SOCs

> **No external system call:** Pure in-memory — manipulates BE concepts only, then calls `NextActivity`.

> **Rule namespace:** `Rules.OMConsumers.OMXOM` — internal calculation, not OMXFM.

> **[BUGS]** Two bugs in source: (1) MasterSIM IMSI reads `$msim/Master/SIM` instead of `$msim/Master/IMSI` when IMSI already exists. (2) COU block uses `if (msim == null)` instead of `if (msim.Master == null)` — Master is never created for COU subscribers when MultiSIMInfo was freshly initialised.

---

## §2 Rule Metadata & Attributes

| Attribute | Value | Notes |
|-----------|-------|-------|
| Rule file | `OMX_POPULATE_MSIM_INFO.rule` | 183 lines; no `Request_` prefix |
| Rule namespace | `Rules.OMConsumers.OMXOM` | |
| Response rulefunction | None | Synchronous — no backend |
| Author | RS33-BANDIT | |
| forwardChain | true | |
| Logger | `Log.getLogger` + `Log.log` | Also uses `System.debugOut` for debug traces |
| Activity parameter | `SPC` | If "AUTO_CANCEL" → triggers replication mode |
| External system | None | |
| Completion | `NextActivity()` if any subscriber processed; else `SkipActivity("4")` | |
| Source field (hardcoded) | `"FE"` | Applied to all MasterSIM and MinorSIM concepts created |
| Audit | [UNCONDITIONAL] | `AUDIT_TRACE = "OMX_POPULATE_MSIM_INFO Completed."` |

---

## §3 Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Activity instance match |
| 2 | `orderCurrentActivity.ActivityID == "OMX_POPULATE_MSIM_INFO"` | FM type guard |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_POPULATE_MSIM_INFO"` | Process flow alignment |
| 4 | `orderCurrentActivity.Status == "WAITING"` | WAITING state guard |

---

## §4 TR_MULTISIM_IND SocProperty Values

| Value | Meaning | isMsim gate | MinorSIM type in normal mode |
|-------|---------|-------------|------------------------------|
| `RES` | Reserve — new minor SIM being added | ✓ | isRes — from ParameterInfo (Related SIM/IMSI) |
| `REE` | Reserve Existing — existing minor SIM | ✓ | isRes — from ParameterInfo (Related SIM/IMSI) |
| `RCM` | RC Minor — master sub's own SIM becomes minor | ✓ | isRcm — from ResourceInfo (subscriber's own SIM) |
| `RCE` | RC Existing — existing RC minor | ✓ | isRcm — from ResourceInfo (subscriber's own SIM) |

> A subscriber qualifies (`isMsim=true`) if it has at least one offer with any of RES / RCM / REE / RCE in SocProperties.

---

## §5 Two Operating Modes (SPC Parameter)

### Normal Mode (SPC ≠ "AUTO_CANCEL")

Iterates each qualifying subscriber's `SubscriberOffers`. For each offer passing PreExecCheck:

- **RES/REE** (`isRes=true`) → create MinorSIM from offer ParameterInfo:
  - SIM ← `ParameterInfo["Related SIM"]/ValuesArray`
  - IMSI ← `ParameterInfo["Related IMSI"]/ValuesArray`
  - Alias ← `ParameterInfo["IMSI_Alias_Name"]/ValuesArray`
  - RCOfferIn ← 3-way: "RC Minor SOC code out" / "RC Minor SOC code In" / offer.Soc

- **RCM/RCE** (`isRcm=true`, not already cross-linked by RES) → create MinorSIM from subscriber ResourceInfo:
  - SIM ← `ResourceInfo["SIM"]/ValuesArray`
  - IMSI ← `ResourceInfo["IMSI"]/ValuesArray`
  - RCOfferIn ← offer.Soc

> **isRcm cross-link exclusion:** An RCM/RCE offer is NOT processed if there is already an RES/REE offer whose `ParameterInfo["RC Minor SOC code out"]` points to this offer's Soc — preventing duplicate MinorSIM creation.

### AUTO_CANCEL Mode (SPC = "AUTO_CANCEL")

Iterates existing `sub.MultiSIMInfo.Minor[]`. For each Minor where `Source="PREV_MSIM"`:

- Creates new MinorSIM with SIM/IMSI from the existing minor (if non-null)
- **POU RCOfferIn**: looks up `SubscriberOffers[FE_OR_CCBS=CCBS AND (RCM OR RCE)][m+1]/Soc`
- **COU RCOfferIn**: looks up `SubscriberOffers[FE_OR_CCBS=CCBS AND RCM][m+1]/Soc` (RCE not included in COU)
- Appends new MinorSIM to `sub.MultiSIMInfo.Minor[]`

---

## §6 POU vs COU Processing Differences

| Aspect | POU Subscriber | COU Subscriber |
|--------|----------------|----------------|
| PreExecCheck XML builder | `GetXMLForSubscriberOfferFilterWithExtendedInfo` | `GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo` (passes `pOuRefId`) |
| Master null guard | `if (msim.Master == null)` | `if (msim == null)` **[BUG]** — always false after MultiSIMInfo init; Master never created for COU |
| isRes condition | TR_MULTISIM_IND=RES or REE (any) | TR_MULTISIM_IND=RES or REE **AND FE_OR_CCBS="FE"** (extra gate) |
| AUTO_CANCEL RCOfferIn lookup | FE_OR_CCBS=CCBS AND (RCM OR RCE) | FE_OR_CCBS=CCBS AND RCM only (RCE excluded) |

---

## §7 MasterSIM Construction & Known Bug

For each qualifying subscriber, the rule ensures a `MultiSIMInfo` exists and then creates a `MasterSIM` if needed:

| Field | Condition | Source | Bug? |
|-------|-----------|--------|------|
| `SIM` | if `sub.MultiSIMInfo/Master/SIM` exists | `$msim/Master/SIM` | |
| `SIM` | else | `ResourceInfo[SIM]/ValuesArray` | |
| `IMSI` | if `sub.MultiSIMInfo/Master/IMSI` exists | `$msim/Master/SIM` **[BUG]** | Should be `$msim/Master/IMSI` |
| `IMSI` | else | `ResourceInfo[IMSI]/ValuesArray` | |
| `Source` | always | `"FE"` (hardcoded) | |

> **[BUG]** When `sub.MultiSIMInfo/Master/IMSI` already exists, the IMSI field is incorrectly populated with the **SIM** value (`$msim/Master/SIM`) instead of the IMSI value. This corrupts MasterSIM.IMSI in re-processing scenarios.

---

## §8 RCOfferIn 3-Way Priority (Normal Mode, RES/REE)

| Priority | Condition | Source |
|----------|-----------|--------|
| 1 | `exists(ParameterInfo[ParamName="RC Minor SOC code out"]/ValuesArray)` | `ParameterInfo["RC Minor SOC code out"]/ValuesArray` |
| 2 | `exists(ParameterInfo[ParamName="RC Minor SOC code In"]/ValuesArray)` | `ParameterInfo["RC Minor SOC code In"]/ValuesArray` |
| 3 (default) | else | `offer.Soc` |

> Priority 1 ("out") takes precedence over priority 2 ("in") — note the case difference: "SOC code out" vs "SOC code In".

---

## §9 Function Dependency Tree

```text
OMX_POPULATE_MSIM_INFO (rule)
├── Log.getLogger("Rules.OMConsumers.OMXOM.OMX_POPULATE_MSIM_INFO")
├── GetActivityParamValueFromKey(activity, "SPC")
├── [POU loop p]:
│   └── [POU Subscriber loop ps]:
│       ├── XPath.evalAsBoolean(isMsim: exists(SubscriberOffers[RES/RCM/REE/RCE]))
│       ├── [if isMsim]:
│       │   ├── [if MultiSIMInfo==null]: Instance.createInstance(MultiSIMInfo{extId})
│       │   ├── [if msim.Master==null]: Instance.createInstance(MasterSIM{SIM,IMSI,Source="FE"})
│       │   │   ← SIM: PREV or ResourceInfo[SIM]; IMSI: PREV or ResourceInfo[IMSI] [BUG: uses SIM]
│       │   ├── [if param=="AUTO_CANCEL"]:
│       │   │   └── [Minor loop m where Source=="PREV_MSIM"]:
│       │   │       └── Instance.createInstance(MinorSIM{SIM,IMSI,RCOfferIn(CCBS+RCM/RCE),Source="FE"})
│       │   └── [else — normal mode]:
│       │       └── [SubscriberOffers loop o]:
│       │           ├── FE_OR_CCBS filter → GetXMLForSubscriberOfferFilterWithExtendedInfo
│       │           ├── XPath.execute(PreExecCheck)
│       │           ├── [if chkRes=="true"]:
│       │           │   ├── XPath.evalAsBoolean(isRes: RES or REE)
│       │           │   │   → Instance.createInstance(MinorSIM{RelatedSIM,RelatedIMSI,Alias,RCOfferIn 3-way,Source="FE"})
│       │           │   └── [else] XPath.evalAsBoolean(isRcm: RCM/RCE AND not cross-linked)
│       │           │       → Instance.createInstance(MinorSIM{ResourceSIM,ResourceIMSI,RCOfferIn=Soc,Source="FE"})
│       │           └── isSkipped = false
├── [COU loop c → cs]:  [same structure as POU; differences: §6]
│   ├── [if msim==null] BUG: condition never true after MultiSIMInfo init
│   └── COU isRes adds FE_OR_CCBS="FE" gate; GetXMLForSubscriberOfferInChildOUFilterWithExtendedInfo
├── [if !isSkipped]:
│   ├── RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)
│   └── Event.Ext.sendEventImmediate(Logger: "OMX_POPULATE_MSIM_INFO Completed.")
├── [else]: SkipActivity(orderRequest, orderCurrentActivity, "4")
└── [catch] HandleActivityException
```

---

## §10 Migration Notes & Recommendations

### Functional Requirements

| Ref | Requirement |
|-----|-------------|
| R1 | Pure in-memory step — no external system integration required. |
| R2 | Subscriber is eligible only if it has at least one offer with TR_MULTISIM_IND=RES/RCM/REE/RCE. |
| R3 | Normal mode classifies offers as isRes (RES/REE) or isRcm (RCM/RCE). isRcm is suppressed if an existing RES offer already cross-links to the offer's Soc via "RC Minor SOC code out". |
| R4 | AUTO_CANCEL mode (SPC="AUTO_CANCEL") replicates existing PREV_MSIM Minor entries with updated RCOfferIn from CCBS SOCs. |
| R5 | COU isRes requires additional FE_OR_CCBS="FE" gate (POU does not). |
| R6 | RCOfferIn 3-way priority: "RC Minor SOC code out" → "RC Minor SOC code In" → offer.Soc. |
| R7 | Source="FE" is hardcoded on all created MasterSIM and MinorSIM concepts (distinguishes from "PREV_MSIM" from prior INTX lookups). |

### Known Bugs — Fix Before Migration

| Bug | Location | Severity | Fix |
|-----|----------|----------|-----|
| MasterSIM IMSI copies SIM value when existing IMSI present | POU + COU MasterSIM construction — `xsl:when test="exists($sub/MultiSIMInfo/Master/IMSI)"` | [HIGH] | Change `$msim/Master/SIM` to `$msim/Master/IMSI` in the IMSI xsl:when branch |
| COU Master never created when MultiSIMInfo is freshly initialised | COU block — `if (msim == null)` after `msim = sub.MultiSIMInfo` | [HIGH] | Change `if (msim == null)` to `if (msim.Master == null)` (matching POU logic) |

---

*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
