# OMX_TRANSFORM_NETWORK_CMD_TO_IOT

> Internal OMX Transformation — Rewrites Downstream Network Command Parameters for IoT Routing

**Priority:** 5 | **forwardChain:** true | **Type:** Internal Transformation (OMXOM) | **No Backend Call** | **No Response Rulefunction** | **Generated:** 2026-07-27

---

## §1 — Overview & Purpose

> **Internal Transformation Rule — No backend call, no response rulefunction.**
> This rule lives under `Rules.OMConsumers.OMXOM` (not OMXFM) and performs a pure in-memory modification of the ProcessFlow before advancing via `NextActivity`.

When this activity fires, it scans all activities in `ProcessFlow.Activities[]` and, for any activity listed in the **NetworkActivity** global variable (e.g., `OMX_GET_SRV_TRX_NO`, `AA_ACTIVATE_SUBS`, `AA_CHECK_CONFIRMATION`), it looks at each activity's `Parameter[]` values. If a parameter value matches any code in the **NetworkCommand** global variable list, it is prefixed with `"I"` to convert it to its IoT variant.

**Transform examples:**
- `NAC` → `INAC` (Network Activation Command → IoT NAC)
- `DSD` → `IDSD` (Disconnect → IoT DSD)
- `SRS` → `ISRS` (Service Restoration → IoT SRS)

> **Break-on-first-match:** Only the first matching parameter per activity is transformed. The inner loop breaks immediately after the first NetworkCommand match.

---

## §2 — Rule Metadata & Attributes

| Attribute | Value |
|-----------|-------|
| Rule Name | `OMX_TRANSFORM_NETWORK_CMD_TO_IOT` |
| Rule Path | `Rules.OMConsumers.OMXOM` (internal OMX, not OMXFM) |
| Priority | 5 |
| forwardChain | true |
| Author | DESKTOP-995HR2V (machine hostname) |
| Backend call | None — pure in-memory transformation |
| Response rulefunction | None — calls `NextActivity` directly |
| Completion | `RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)` (synchronous) |
| Global var: NetworkCommand | `OMX_OM/BizRules/IOT/NetworkCommand`<br>Default: `,NAC,DSD,CCD,SRS,RSP,SSU,SUS,SSP,CCN,RCL,` |
| Global var: NetworkActivity | `OMX_OM/BizRules/IOT/NetworkActivity`<br>Default: `,OMX_GET_SRV_TRX_NO,AA_ACTIVATE_SUBS,AA_CHECK_CONFIRMATION,` |

---

## §4 — Rule Conditions (WHEN)

| # | Condition | Purpose |
|---|-----------|---------|
| 1 | `orderCurrentActivity@extId == orderRequest.ProcessFlow.NextActivityName` | Correlates activity |
| 2 | `orderCurrentActivity.ActivityID == "OMX_TRANSFORM_NETWORK_CMD_TO_IOT"` | Targets only this rule |
| 3 | `orderRequest.ProcessFlow.NextActivityID == "OMX_TRANSFORM_NETWORK_CMD_TO_IOT"` | Order-level double-check |
| 4 | `orderCurrentActivity.Status == "WAITING"` | Only fires on fresh activity |

---

## §5 — Execution Flow

```text
1. Init — isActResub; evaluate orderCurrentActivity.PreExecCheck XPath
2. Load config — read networkCmd + networkActivities from global variables
3. Scan ProcessFlow.Activities[a]:
     if networkActivities contains "," + activityId + ",":
       for each Parameter[p]:
         if networkCmd contains "," + param + ",":
           Parameter[p] = "I" + param
           break  // first match only
4. NextActivity(orderRequest, orderCurrentActivity)    // synchronous advance
5. [PreExecCheck=false] SkipActivity("4")
6. Exception → HandleActivityException
```

---

## §6 — Transformation Logic

### §6.1 — NetworkCommand List (default)

| Code | Inferred Meaning | IoT Variant |
|------|-----------------|-------------|
| NAC | Network Activation Command | INAC |
| DSD | Disconnect / Deactivate | IDSD |
| CCD | Complete Call Disconnect | ICCD |
| SRS | Service Restoration | ISRS |
| RSP | Restore Service Profile | IRSP |
| SSU | Subscriber Service Update | ISSU |
| SUS | Subscriber Service Suspend | ISUS |
| SSP | Service Suspend Profile | ISSP |
| CCN | Cancel Command / Notification | ICCN |
| RCL | Recall / Reactivation | IRCL |

### §6.2 — NetworkActivity List (default)

| Activity ID | Role in Flow |
|-------------|-------------|
| `OMX_GET_SRV_TRX_NO` | Service transaction number lookup (step 14) |
| `AA_ACTIVATE_SUBS` | AA subscriber activation (step 16) |
| `AA_CHECK_CONFIRMATION` | AA activation confirmation check (step 28) |

### §6.3 — Transform Algorithm

```java
String networkCmd = GlobalVar("OMX_OM/BizRules/IOT/NetworkCommand",
                              ",NAC,DSD,CCD,SRS,RSP,SSU,SUS,SSP,CCN,RCL,");
String networkActivities = GlobalVar("OMX_OM/BizRules/IOT/NetworkActivity",
                                     ",OMX_GET_SRV_TRX_NO,AA_ACTIVATE_SUBS,AA_CHECK_CONFIRMATION,");

for (int a = 0; a < ProcessFlow.Activities.length; a++) {
    if (networkActivities.contains("," + Activities[a].ActivityID + ",")) {
        for (int p = 0; p < Activities[a].Parameter.length; p++) {
            if (networkCmd.contains("," + Activities[a].Parameter[p] + ",")) {
                Activities[a].Parameter[p] = "I" + Activities[a].Parameter[p];
                break;   // only first match per activity
            }
        }
    }
}

// Example result:
// AA_ACTIVATE_SUBS.Parameter[0]="NAC"     →  "INAC"
// OMX_GET_SRV_TRX_NO.Parameter[0]="DSD"  →  "IDSD"
```

### §6.4 — PreExecCheck Note

> This rule reads `orderCurrentActivity.PreExecCheck` directly (not `nextAct.PreExecCheck` as used in OMXFM request rules). Since the current activity IS the one being processed here, `orderCurrentActivity` is the correct reference.

---

## §8 — Dependencies

### §8.1 — Global Variable Dependencies

| Path | Default Value | Purpose |
|------|--------------|---------|
| `OMX_OM/BizRules/IOT/NetworkCommand` | `,NAC,DSD,CCD,SRS,RSP,SSU,SUS,SSP,CCN,RCL,` | Network command codes to prefix with "I" |
| `OMX_OM/BizRules/IOT/NetworkActivity` | `,OMX_GET_SRV_TRX_NO,AA_ACTIVATE_SUBS,AA_CHECK_CONFIRMATION,` | Activity IDs whose parameters are scanned |

### §8.2 — Working Memory Read/Write

| Field | Direction | Notes |
|-------|-----------|-------|
| `orderRequest.ProcessFlow.Activities[a].ActivityID` | READ | Matched against NetworkActivity list |
| `orderRequest.ProcessFlow.Activities[a].Parameter[p]` | READ + WRITE | Prefixed with "I" if matched |
| `orderCurrentActivity.PreExecCheck` | READ | XPath condition for skip gate |

### §8.3 — No JMS / ESB / Backend Dependencies

No JMS calls, no events sent, no audit logging. Pure in-memory working memory modification.

---

## §12 — Activity Status Management

| Trigger | Code | Outcome |
|---------|------|---------|
| PreExecCheck passes | — | Transform runs; `NextActivity` advances flow synchronously |
| PreExecCheck false | 4 | SKIPPED |
| Exception | 3 | ERROR |

> No IN_PROGRESS state — completes synchronously via `NextActivity`.

---

## §15 — Function Dependency Tree

```text
OMX_TRANSFORM_NETWORK_CMD_TO_IOT (rule)
├── [if PreExecCheck non-empty]:
│   ├── Instance.serializeUsingDefaults(orderRequest)
│   └── XPath.execute("/(" + chkXPath + ")", sXML, ...)
├── System.getGlobalVariableAsString("OMX_OM/BizRules/IOT/NetworkCommand", default)
├── System.getGlobalVariableAsString("OMX_OM/BizRules/IOT/NetworkActivity", default)
├── for(a) over ProcessFlow.Activities[]:
│   ├── String.contains(networkActivities, "," + ActivityID + ",")
│   └── for(p) over Activities[a].Parameter[]:
│       ├── String.contains(networkCmd, "," + Parameter[p] + ",")
│       └── [if match] Activities[a].Parameter[p] = "I" + param; break
├── [!isSkipped] RuleFunctions.Helpers.NextActivity(orderRequest, orderCurrentActivity)
├── [isSkipped]  RuleFunctions.Helpers.SkipActivity(orderRequest, orderCurrentActivity, "4")
└── HandleActivityException(orderRequest, orderCurrentActivity, ae, "")
```

---

## §17 — Migration Notes & Recommendations

### Functional Requirements

- **R1** — Pre-processing middleware step: modifies downstream activity parameters at runtime based on globally configured lists. Both lists must be configurable per environment.
- **R2** — Transform is global within the ProcessFlow — scans ALL activities (not just current), mutating parameters of activities that haven't fired yet.
- **R3** — Break-on-first-match: only first matching parameter per activity is transformed.
- **R4** — Completes synchronously (no async response). In microservices migration, apply this logic as a synchronous pre-step before dispatching downstream calls.
- **R5** — Comma-delimited contains-matching with surrounding commas (e.g., `",NAC,"`) — substring "NAC" inside "SNAC" must NOT match.

### Design Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Mutates ProcessFlow in-memory — downstream readers get transformed value, not obvious from ProcessConfig XML | [MEDIUM] | Document as known runtime mutation; migration should apply same transform at orchestration layer |
| Break-on-first-match may silently miss second matching parameter | [LOW] | Verify whether an activity could have two IoT command parameters |
| Global variable defaults hardcoded — if global absent, fallback used silently | [LOW] | Ensure globals always present in deployment config |

---

*TRUE Corporation OMX · TIBCO BusinessEvents Internal Rule Documentation*
