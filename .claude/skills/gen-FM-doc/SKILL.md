# generate-fm-doc

Generate a detailed HTML FM Logic documentation artifact for one or more TIBCO BusinessEvents rule files.

**Usage:**
- Single rule: `/generate-fm-doc ATS_BUNDLEPRODUCT_NUMBER`
- Full path: `/generate-fm-doc TRUEOMX_20250719 - AI/OMX-OM/Rules/OMConsumers/OMXFM/Request/Request_ATS_BUNDLEPRODUCT_NUMBER.rule`
- Folder: `/generate-fm-doc TRUEOMX_20250719 - AI/OMX-OM/Rules/OMConsumers/OMXFM/Request`

---

## Workspace root

```
c:\Users\ChailucK\OneDrive - True Corporation Public Company Limited\DTAC\Source code\TRUE OMX\TRUEOMX AI
```

## Output location

For each rule, **two files** are written under the workspace root:
- HTML: `output/FMlogic/<RuleName>.html`
- Markdown: `output/FMlogic_markdown/<RuleName>.md`

Both files carry the same content and section structure; the Markdown file is plain-text renderable in GitHub, VS Code, or Obsidian.

---

## Steps

### 1. Resolve the rule file(s)

If `$ARGUMENTS` names a single  file:
- Search for it under `TRUEOMX_20250719 - AI/OMX-OM/Rules/` if a full path is not given.
- The request file will be Request_<RuleName>.rule 
- Search for it under `TRUEOMX_20250719 - AI/OMX-OM/RuleFunctions/` if a full path is not given.
- the response file will be Response_<RuleName>.rulefunction
- Process these two files

If `$ARGUMENTS` names a folder:
- Glob all `*.rule` files under that folder (non-recursive unless the user says "recursive").
- Glob all `*.rulefunction` files under that "./../RuleFunctions/" of the folder (non-recursive unless the user says "recursive").
- Process each file in sequence, generating one HTML per rule.

If `$ARGUMENTS` is empty:
- Ask the user for the rule file or folder path.

### 2. For each rule file, collect context

Read the following in parallel:

**a) The rule file itself** — parse:
  - Rule name, priority, forwardChain
  - `declare` block → variable names and concept types
  - `when` block → all condition expressions
  - `then` block → full action logic

**b) Referenced events** — for each `Event.createEvent("xslt://{{/Events/...}}")` found:
  - Glob for the `.event` file under `TRUEOMX_20250719 - AI/OMX-OM/Events/`
  - Read the event: channelURI, destinationName, payloadString, superEventPath, namespaceEntries
  - **Extract and unescape the full XSLT stylesheet** embedded in the `Event.createEvent(...)` string:
    convert `\n` → newline and `\"` → `"` to recover the raw XSLT XML. This unescaped XSLT is the
    primary source for all §9 analysis and must be rendered in full in §9.8.
  - If multiple `Event.createEvent` calls reference the same event type (e.g., ParentOU/ChildOU variants),
    document each variant separately and note what differs between them.

**c) Referenced concepts** — for each concept type in `declare` block:
  - Read the `.concept` file under `TRUEOMX_20250719 - AI/OMX-OM/Concepts/`
  - Extract all `<properties>` fields: name, type, array, conceptTypePath

**d) Referenced helper functions** — for each `RuleFunctions.*` call found in the rule:
  - Glob for the matching `.rulefunction` file under `TRUEOMX_20250719 - AI/OMX-OM/RuleFunctions/`
  - Read: signature (return type, scope variables), body logic

**e) Extended info keys** — scan the XSLT inside the rule for:
  - `ExtendedInfo[Name='...']/Value` patterns → list each unique key name
  - Whether it is inside `xsl:if` (optional) or always emitted (required)

**f) Global variable references** — scan for `System.getGlobalVariableAsString(` or `$globalVariables/` → list each path

**g) Corresponding Response Rule** — derive the response rulefunction name by replacing the `Request_` prefix with `Response_`:
  - e.g., `Request_ATS_BUNDLEPRODUCT_NUMBER.rule` → `Response_ATS_BUNDLEPRODUCT_NUMBER.rulefunction`
  - Glob for the file under `TRUEOMX_20250719 - AI/OMX-OM/RuleFunctions/OrderResponse/`
  - If found, read it and parse:
    - `scope` block → variable names and types (orderRequest, eventResponse type, currActivity)
    - `Instance.createInstance("xslt://{{/Concepts/FM/Base/ResponseBase}}...")` → unescape the embedded XSLT to extract ResponseBase field mapping
    - `Event.createEvent` for the audit logger → unescape the embedded XSLT for response audit log fields
    - `XPath.evalAsInt(...)` expression → extract the success-count XPath (`tib:right(tib:trim(ResponseCode), 3) = "000"`)
    - `if(currActivity.RequestCount == successResponseCount)` → document the fan-in completion condition and return values
  - If not found, note in warnings.

**h) Outbound API mapping** — for each `Event.createEvent` call, map the destination name prefix to the backend system:
  - ATS → ATS
  - CCBS → CCBS
  - NAS → NAS
  - etc.

**i) Consider the business rule (BRMS) context** — for each rule, document:
  - BRMS rules are in the ./Resources/BRMS/*
  - What order types / scenarios trigger this rule
  - What the rule does (purpose, payload built, backend call made)
  - What the response rulefunction does (fan-in completion, activity status update, audit logging)

**j) DB schema references** — for each `RuleFunctions.*` call, check if it reads/writes any DB tables (e.g., `OMXDBUtils:...`) and document the table names and fields.
  - DB schema references are also found in ./Resources/DBSchema/*

### 3. Analyse the collected data

Extract and document:

| Analysis | How |
|---|---|
| System & Integration Dependencies | List every `Event.createEvent` call → event file → channelURI + destinationName + schema |
| XSLT field mapping | For each field in the XSLT template: target XML element, source XPath or static value, xsl:if condition |
| GROUP / pipe-delimited parsing | Identify `String.split(..., "\\|")` + `substringAfter` patterns → document field array mapping |
| Function dependency tree | Walk every `RuleFunctions.*` call and each called function's own calls |
| PreExecCheck gate | Document skip condition logic |
| Status transitions | Document every `GetActivityStatusString` call and resulting status |
| Exception handling | Document catch block and HandleActivityException call chain |
| Outbound API | Map to backend: ATS / CCBS / NAS / etc. from destination name prefix |
| Response rule analysis | Parse ResponseBase XSLT field mapping; identify success criteria (ResponseCode suffix "000"); document fan-in completion condition (RequestCount vs successResponseCount) |

### 4. Generate the HTML

Produce a single self-contained HTML file with the following sections (adapt based on what the rule actually does — omit sections with no content):

1. Overview & Purpose
2. Rule Metadata & Attributes (priority, forwardChain, rule type)
3. Working Memory — Declared Objects
4. Rule Conditions (WHEN) — one block per condition
5. Execution Flow Diagram (numbered steps)
6. Rule Action (THEN) — step-by-step logic
7. Data Extraction — any pipe/delimited/encoding parsing
8. ★ System & Integration Dependencies
   - 8.1 Order Type Dependencies (what order types/scenarios trigger this)
   - 8.2 ESB / JMS Channel Dependencies (direction, channel, destination, protocol, purpose)
   - 8.3 Backend API Details (system name, operation, schema, protocol, correlation pattern)
   - 8.4 BE Working Memory Dependencies (read vs. written fields)
   - 8.5 ExtendedInfo Fields Required (name, required/optional, where used)
   - 8.6 Global Variable Dependencies
9. ★ Detailed Payload Build (step-by-step XSLT decomposition)
   - 9.1 XSLT Parameter Binding
   - 9.2 Event Container Construction (createEvent / extId)
   - 9.3 JMS / Event Header Fields
   - 9.4 Payload Root element
   - 9.5 Conditional Fields (xsl:if)
   - 9.6 Core Payload / product / entity block
   - 9.7 Complete Generated XML Example (illustrative, all fields populated)
   - 9.8 **XSLT Stylesheet Source** — render the full unescaped, pretty-printed XSLT
     `<xsl:stylesheet>` block for every distinct `Event.createEvent` variant.
     Use syntax highlighting (xml-tag / xml-attr colours). Label each variant by scope
     (e.g., "ParentOU Variant ①", "ChildOU Variant ②"). Add inline comments identifying
     what each `xsl:param` is bound from and the purpose of each output element.
     Where two variants differ only by parameter names, show a diff table instead of
     repeating the full stylesheet.
10. ★ XSLT Field Mapping — **Output XML Tree Hierarchy**
    Render as an **indented HTML tree** (`<ul>/<li>`) that mirrors the generated XML element
    hierarchy (`createEvent → event → [headers] → payload → ...`). For every element node show:
      - The XML tag name (xml-tag colour)
      - Source XPath arrow `←` and the source expression (green for XPath, orange for literals)
      - The `xsl:if` / `xsl:choose` condition in purple italic where applicable
      - A badge: `Always` (green) / `Conditional` (orange) / `Credential-gated` (purple)
    Nested `xsl:if` blocks must appear as indented sub-trees with a purple italic label.
    For multi-variant rules (ParentOU/ChildOU), show one tree and annotate differences inline.
    Include a legend below the tree explaining the colour/badge scheme.
    **Do NOT use a flat table for this section.**
11. Audit Logging
12. Activity Status Management
13. Exception / Error Handling
14. Helper Functions Reference (function, signature, validity, purpose)
15. ★ Function Dependency Tree (ASCII tree showing full call chain)
16. Concept Definitions Referenced
17. Migration Notes & Recommendations
    - Functional requirements (R1–Rn)
    - Design risks table (risk, severity badge, mitigation)
18. Full Source Code (syntax-highlighted)
    For every `Event.createEvent("xslt://{{...}}")` call in the BE rule source: **NEVER replace the
    XSLT with `"..."`**. Instead, replace the long escaped XSLT string with an inline structured
    comment block referencing §9.8 and summarising the output fields in one line. Full XSLT code is
    already shown in §9.8 — the source code section shows the BE rule logic, not the XSLT payload.
19. ★ Response Message Rule (omit if the corresponding `.rulefunction` was not found)
    - 19.1 **Overview** — purpose of the response handler (parses backend reply, updates activity state, drives fan-in completion)
    - 19.2 **Scope Variables** — table: variable name, type path, role (e.g., orderRequest / eventResponse / currActivity)
    - 19.3 **ResponseBase Concept Construction** — render as an **indented HTML tree** (same `.xslt-tree` CSS as §10) showing the `createObject → object` hierarchy with field sources:
      - `extId` ← `OMXUtils:generateTrackingID()` (always)
      - Each mapped field (ResponseCode, ResponseMessage, CompletionStatus, ReferenceId, …) with `← $eventResponse/<SourceField>` and `Conditional` badge where inside `xsl:if`
    - 19.4 **Response Completion Logic** — document:
      - Success XPath expression: the `XPath.evalAsInt(...)` expression (e.g., `count($currActivity/Response[tib:right(tib:trim(ResponseCode), 3) = "000"])`)
      - Fan-in condition: `currActivity.RequestCount == successResponseCount` → "true" / "false"
      - Explain what "true" signals to the caller (all parallel backend calls succeeded)
    - 19.5 **Response Audit Logging** — same XSLT tree style as §9 for the Logger event, including:
      - `PROCESS_ID` with `_RES` suffix, `OPERATION_NAME`, `TARGET_SYSTEM`, `AUDIT_TRACE`, `AUDIT_TS`
      - Conditional `payload/ns:ServicePayload` gated on `WritePayload=true`
    - 19.6 **Response XSLT Source** — render the full unescaped, pretty-printed XSLT for the `Instance.createInstance(...)` call (same style as §9.8)

### 4b. Generate the Markdown

Using **the same analysed data** from Steps 2–3 and the same 19-section structure from Step 4, produce a companion Markdown (`.md`) file. Apply these Markdown-specific rendering rules:

**Headings**
- Document title → `# <RuleName>` (basename only)
- Section headers (§1–§19) → `## §N Title`
- Sub-sections (§8.1, §9.1, §19.1, …) → `### §N.N Title`

**Text formatting**
- Bold for labels/emphasis: `**label**`
- Inline code for identifiers, paths, XPath: `` `value` ``
- Blockquotes (`> `) for warnings, notes, and callout boxes that are coloured cards in the HTML

**Tables** — use standard GFM pipe tables:
```
| Column A | Column B | Column C |
|----------|----------|----------|
| value    | value    | value    |
```

**Code blocks** — use fenced blocks with the appropriate language tag:
- XSLT source (§9.8, §19.6): ` ```xml `
- BE rule source (§18): ` ```java `
- XPath expressions: ` ```xpath `
- Generic / config: ` ```text `

**XSLT Field Mapping tree (§10) and ResponseBase tree (§19.3)** — render as an **ASCII tree** using box-drawing characters inside a ` ```text ` block. Replace HTML badges with bracketed labels:
- `[Always]` instead of the green badge
- `[Conditional: <xsl:if test="...">]` instead of the orange badge
- `[Credential-gated]` instead of the purple badge

Example tree format:
```text
createEvent
└── event
    ├── ESBUUID              ← $orderRequest/OrderData/OMXTrackingId   [Conditional: $orderRequest/OrderData/OMXTrackingId]
    ├── PROCESS_ID           ← concat($pid, "_REQ")                    [Always]
    ├── COMPONENT_NAME       ← $globalVariables/OMX_COMMON/...         [Always]
    └── payload              [Conditional: $globalVariables/.../WritePayload = "true"]
        └── ns:ServicePayload ← (copy of $orderRequest)
```

**Function Dependency Tree (§15)** — render inside a ` ```text ` fenced block (ASCII tree is already plain text).

**Execution Flow Diagram (§5)** — render as a numbered list with `→` arrows:
```
1. PreExecCheck gate → skip if already complete
2. Build JMS request event via XSLT
3. Send to ESB destination
4. Log audit trail
```

**Badges in tables** — replace HTML-coloured badges with plain text markers:
- Severity: `[HIGH]`, `[MEDIUM]`, `[LOW]`
- Status: `[SUCCESS]`, `[SKIP]`, `[ERROR]`
- Direction: `[OUTBOUND]`, `[INBOUND]`

**Full Source Code (§18)** — same rule as HTML: replace embedded XSLT strings with a one-line comment referencing §9.8, place the rest of the rule body in a ` ```java ` block.

**Response Message Rule (§19)** — omit if the response rulefunction was not found, same as the HTML.

**Footer line** — end the document with:
```
---
*TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation*
```

### 5. Apply the TRUE Corporation HTML theme

Use the following CSS design system in every generated file — do NOT change the colour scheme:

```css
:root {
  --true-red:  #CC0000;
  --true-dark: #8B0000;
  --true-deep: #5C0000;
  --true-light:#FF5252;
  --true-pale: #FFF5F5;
  --success:   #2e7d32;
  --warning:   #e65100;
  --info:      #1565c0;
  --skip:      #6a1b9a;
  --bg:        #F9F9F9;
  --card:      #FFFFFF;
  --border:    #E0E0E0;
  --code-bg:   #1e1e2e;
  --code-fg:   #cdd6f4;
}
```

- Page header: `linear-gradient(135deg, var(--true-deep), var(--true-dark), var(--true-red))`
- Card headers: `linear-gradient(90deg, var(--true-dark), var(--true-red))` + left border `var(--true-light)`
- Table `<th>`: `background: #F5E6E6; color: var(--true-dark); border-bottom: 2px solid var(--true-red)`
- Pre/code left border: `3px solid var(--true-red)`
- Syntax highlighting: keywords=`#cba6f7`, types=`#89b4fa`, strings=`#a6e3a1`, comments=`#6c7086`, numbers=`#fab387`, functions=`#f38ba8`, xml-tags=`#89dceb`, xml-attrs=`#f9e2af`
- Badges: red=`#FFE0E0/var(--true-dark)`, green=`#E8F5E9/#2e7d32`, orange=`#FFF3E0/#e65100`, blue=`#E3F0FD/#1565c0`, purple=`#F3E5F5/#6a1b9a`, teal=`#E0F2F1/#00695c`
- Integration badges: JMS=`#FFE0B2/#E65100`, DB=`#E8EAF6/#3949AB`, LOG=`#F1F8E9/#558B2F`
- Footer: `TRUE Corporation OMX · TIBCO BusinessEvents FM Logic Documentation`
- XSLT tree hierarchy CSS (required for §10):
  ```css
  .xslt-tree { list-style:none; padding:0; margin:0; font-family:'Cascadia Code','Consolas',monospace; font-size:0.83rem; }
  .xslt-tree ul { list-style:none; padding-left:22px; margin:0; border-left:2px solid #e0c0c0; }
  .xslt-tree li { position:relative; padding:3px 0 3px 14px; }
  .xslt-tree li::before { content:''; position:absolute; left:-2px; top:12px; width:12px; height:2px; background:#e0c0c0; }
  .tree-tag  { color:#89dceb; font-weight:600; }
  .tree-attr { color:#f9e2af; }
  .tree-arrow { color:#6c7086; margin:0 6px; }
  .tree-src  { color:#a6e3a1; background:rgba(166,227,161,0.1); padding:1px 6px; border-radius:4px; }
  .tree-src-static { color:#fab387; background:rgba(250,179,135,0.1); padding:1px 6px; border-radius:4px; }
  .tree-cond { color:#cba6f7; font-size:0.75rem; margin-left:6px; }
  .tree-ns   { color:#6c7086; font-size:0.78rem; }
  .tree-row  { display:flex; align-items:baseline; gap:4px; flex-wrap:wrap; line-height:1.9; }
  ```

### 6. Write the output

Write **two files** per rule, both in the same generation pass:

| File | Path |
|------|------|
| HTML | `output/FMlogic/<RuleName>.html` |
| Markdown | `output/FMlogic_markdown/<RuleName>.md` |

where `<RuleName>` is the rule file **basename** without the `.rule` extension (e.g., `Request_ATS_BUNDLEPRODUCT_NUMBER`).

**IMPORTANT — File name display rule:** Everywhere the FM file name appears in either output file (HTML `<title>` / `<h1>`, Markdown `#` heading, Overview section, Rule Metadata table, breadcrumb, etc.) use **only the basename** (e.g., `Request_ATS_BUNDLEPRODUCT_NUMBER`). Never display the full relative directory path such as `TRUEOMX_20250719 - AI/OMX-OM/Rules/OMConsumers/OMXFM/Request/Request_ATS_BUNDLEPRODUCT_NUMBER`. The same applies to the response rulefunction name displayed in §19 — use only `Response_ATS_BUNDLEPRODUCT_NUMBER`, not its full path.

### 7. Report completion

After generating each rule's pair of files, report:
- HTML output path
- Markdown output path
- Rule basename (e.g., `Request_ATS_BUNDLEPRODUCT_NUMBER`)
- Corresponding response rulefunction found: yes / no (basename only, e.g., `Response_ATS_BUNDLEPRODUCT_NUMBER`)
- Target system / backend identified
- Number of sections generated
- Any warnings (e.g., GROUP field absent, no events found, helper function file not found, response rulefunction not found)

If a folder was processed, report a summary table: one row per rule with columns — Rule basename | Response rulefunction | Target system | HTML output | Markdown output | Warnings.

---

## Reference example

The canonical examples for a correctly generated document pair are:
- HTML: `output/FMlogic/Request_ATS_BUNDLEPRODUCT_NUMBER.html`
- Markdown: `output/FMlogic_markdown/Request_ATS_BUNDLEPRODUCT_NUMBER.md`

When in doubt about content, structure, or depth, match the HTML reference. When in doubt about Markdown syntax or tree rendering, apply the rules in §4b.
