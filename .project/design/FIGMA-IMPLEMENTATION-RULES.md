# Workshop v3 — Figma Implementation Rules

## Governing Principle
We are not asking an AI to become good at guessing what Figma meant.
We are building a system in which guessing becomes increasingly unnecessary.

## Critical Architecture Finding
The Workshop shell is mode-based, not single-structure:
- **Rail mode** (112px): Brand mark, icon-over-label nav, world assistant. No companion.
- **Sidebar mode** (236–272px): Identity, horizontal nav, companion presence.

Shell mode is a **canonical screen/state property**, stored per frame in the manifest.
It is NOT derived from emotional volume.
Emotional volume is secondary styling context within a mode, not the selector.

This was discovered through Figma REST API analysis of Today Quiet Day (17:481).
The earlier design-context analysis missed this because it didn't compare the TODAY frame against OTHER frames structurally.

For each canonical frame, record:
- shell mode (rail | sidebar)
- observed width
- nav orientation
- identity treatment
- companion treatment
- divider/environmental treatment

Do NOT infer one universal shell.
Do NOT assume every narrow rail is legacy V1. Today Quiet Day proves Workshop intentionally has a rail mode.

## Authority Chain
```
Canonical Workshop v3 Figma
    → figma-design-to-code skill (upstream methodology)
    → FIGMA-COMPONENT-MAP.yaml (repo component mappings)
    → Workshop architecture derivation
    → production primitives
    → Storybook (executable states)
    → visual comparison
    → Playwright
    → Project Worlds
```

## 1. Before Implementing Any Figma Node

1. **Load the figma-design-to-code skill** — mandatory prerequisite before `get_design_context`
2. **Call `get_design_context`** on the target node — primary tool, NOT metadata/screenshot
3. **Consult FIGMA-COMPONENT-MAP.yaml** — check for existing mapping before choosing production component
4. **Check mapping status** — only WORKSHOP_CANONICAL or WORKSHOP_COMPATIBLE components may be used
5. **If no mapping exists** — create one (with disconfirmation) or build new primitive

## 2. Disconfirmation Protocol (Before Reusing V1 Component)

Before choosing an inherited production component:

### Step 1: Identify the proposed equivalence
```
OBSERVED: Workshop contains [concept X]
OBSERVED: V1 contains [component Y]
INFERRED: V1 component Y might implement Workshop concept X
```

### Step 2: Ask what would show the equivalence is wrong
- What if the width is different?
- What if the semantic role is different?
- What if the responsive behavior is different?
- What if the composition is different?

### Step 3: Compare against multiple Workshop frames
- Check at least 3 canonical frames where the concept appears
- Verify structural, behavioral, and semantic consistency

### Step 4: Classify
```
REUSE — proven equivalent through disconfirmation
ADAPT — same concept, needs modification
REPLACE — different architecture, build new
UNKNOWN — insufficient evidence
```

### Step 5: Record in FIGMA-COMPONENT-MAP.yaml
Every mapping must include:
- Confidence: OBSERVED / INFERRED / ASSUMED / UNKNOWN
- Evidence: which frames were checked
- Disconfirmation: what was checked before accepting equivalence

## 3. Mapping Status Rules

| Status | May be used for implementation? | May be mapped to Figma? |
|---|---|---|
| WORKSHOP_CANONICAL | YES | YES |
| WORKSHOP_COMPATIBLE | YES | YES |
| ADAPT_CANDIDATE | MAYBE (with adaptation, not yet certified) | NO |
| HISTORICAL_V1 | NO (must be replaced) | NO |
| UNKNOWN | NO (must be investigated) | NO |

**Missing mappings are acceptable. Wrong mappings are not.**

## 4. Confidence Levels

| Level | Meaning | Action |
|---|---|---|
| OBSERVED | Verified across multiple canonical frames | May use with confidence |
| INFERRED | Consistent with evidence but not directly proven | May use with caution, flag for verification |
| ASSUMED | Based on pattern matching | Must verify before implementation |
| UNKNOWN | No evidence yet | Must investigate before any use |

## 5. Figma MCP Hint Priority

Per upstream figma-design-to-code skill:

1. **FIGMA-COMPONENT-MAP.yaml** — check repo mapping first
2. **Component documentation links** — follow for usage guidelines
3. **Design annotations** — follow designer notes
4. **Design tokens (CSS variables)** — map to project token system
5. **Raw hex / absolute positioning** — use screenshot for intent

## 6. Asset Handling

- **Icons**: Render from Figma exported asset. Never hand-write SVG.
- **Asset URLs expire in ~7 days** — download for committed code.
- **Reuse project icon only if glyph clearly matches** — name match alone is insufficient.
- **Size explicitly**: fixed container + img fills 100%.

## 7. Storybook Integration

Each mapped component should have Storybook stories showing:
- Default state
- All proven Workshop variants
- Emotional volume variations (where applicable)
- Responsive behavior (desktop + mobile minimum)

Stories are the executable proof that the production component matches the Workshop concept.

## 8. Validation Rules

When adding a mapping to FIGMA-COMPONENT-MAP.yaml:
- [ ] Source path exists in repository
- [ ] Export exists in source file
- [ ] Figma node syntax is valid (format: `NNN:NNN`)
- [ ] Mapping references canonical evidence (frame node IDs)
- [ ] Confidence level is honest
- [ ] Disconfirmation was actually performed
- [ ] No duplicate mappings for same Figma concept
- [ ] No HISTORICAL_V1 components mapped as WORKSHOP_*

## 9. Plumb MCP (Optional Disconfirmation)

Plumb MCP may be used as an independent structural interpretation for disconfirmation only:
- Use on one canonical frame only (Today Quiet Day: 17:481)
- Compare Plumb's semantic roles against Workshop derivation
- Disagreement is a disconfirmation signal, not authority
- Do not ship Plumb-generated code

## 10. The V1 Survival Pattern — What NOT to Do

```
WRONG:  "The existing component can be styled like the Figma element, therefore reuse it."
RIGHT:  "If V1 had never existed, would we invent this structure from Workshop?"
```

```
WRONG:  "Let me hide the old header with display:none."
RIGHT:  "Workshop has no header. Remove the header from the architecture."
```

```
WRONG:  "The rail can be widened to look like the sidebar."
RIGHT:  "The rail is a nav rail. The sidebar is a world edge. Different concepts."
```

## 11. Files

| File | Purpose |
|---|---|
| `.project/design/FIGMA-COMPONENT-MAP.yaml` | Maps Figma concepts to production components |
| `.project/design/FIGMA-IMPLEMENTATION-RULES.md` | This file — implementation rules |
| `.project/architecture/WORKSHOP-V3-ARCHITECTURE-DERIVATION.md` | Architecture derivation from canonical frames |
| `.project/design/WORKSHOP-V3-MANIFEST.yaml` | Canonical frame inventory |
| `.agents/skills/personal-world-implement-figma/SKILL.md` | Implementation skill (updated) |
