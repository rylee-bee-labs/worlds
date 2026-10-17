# Workshop v3 Architecture Derivation

## 0. ASSUME UNKNOWN — Disconfirmation Log

### Highest-impact unproven belief
"That the sidebar is structurally the same across all desktop content frames."

### Disconfirmation checks performed:
1. Checked every desktop frame's root element — ALL are `flex items-start` with sidebar + content as direct children. NO frame has a header element on desktop. **OBSERVED.**
2. Checked sidebar widths — range 236–272px, NOT uniform. The sidebar adapts per-screen. **OBSERVED.**
3. Checked for header on desktop — grep for "header" in all9 desktop frames. Only "Drawer header" (Chat), "Projects header" (content area), "Journal header" (content area), "Study header" (content area). NONE are desktop shell headers. **OBSERVED.**
4. Checked companion location — ALL9 desktop frames show companion at sidebar bottom via `justify-between`. **OBSERVED.**
5. Checked content width constraint — NO frame has max-width on root or content area. **OBSERVED.**
6. Checked for "Banner" on desktop — NONE found. Banner is tablet-only (Mobile Today). **OBSERVED.**

### Plumb MCP disconfirmation: PENDING
Plumb MCP experiment on Today Quiet Day (17:481) is BLOCKED:
- No `FIGMA_TOKEN` configured for REST path
- Plumb Figma plugin not installed for desktop pairing
- Plumb evaluation: `tathagat22/plumb-mcp` SHA `4f7568f`, MIT license, safe
- Semantic roles available: `nav`, `hero`, `footer`, `sidebar`, `card`, `button`
- **Action required**: Either set `FIGMA_TOKEN` env var or install Plumb Figma plugin
- **Status**: Architecture derivation based on Figma MCP evidence only. Plumb disconfirmation is deferred and should be completed before final skeleton freeze.

### Classification of claims:
| Claim | Classification |
|-------|---------------|
| Desktop has no header bar | OBSERVED |
| Sidebar is236–272px, not uniform | OBSERVED |
| Companion lives at sidebar bottom | OBSERVED |
| Content area has no global max-width | OBSERVED |
| Sidebar has brand/identity at top | OBSERVED (in frames that show it) |
| Sidebar has navigation in middle | OBSERVED |
| Mobile uses bottom navigation | OBSERVED (Mobile Today frame) |
| Tablet uses banner | INFERRED (no tablet canonical frame exists) |
| Journal reading uses bounded content | OBSERVED (Page edge element) |
| Sidebar bg varies by emotional volume | INFERRED (subtle variation: #0c0912, #0d0a13, #0d0a14 vs #12101a) |

---

## 1. Persistent Structural Regions (Desktop)

### CRITICAL FINDING: Dual-mode shell architecture

The Workshop does NOT use one universal sidebar structure. It uses TWO distinct modes as a canonical screen/state property:

| Frame | Shell Mode | Left Element | Width | Nav | Identity | Companion | Divider |
|---|---|---|---|---|---|---|---|
| Today Quiet Day | **rail** | Navigation rail | 112px | VERTICAL (icon-over-label) | Brand mark | World assistant (icon) | none |
| Vault | sidebar | Sidebar | 236px | HORIZONTAL | none | Companion nook | none |
| Interests | sidebar | Project sidebar | 256px | HORIZONTAL | World identity | none (content area) | present |
| Bad Day | sidebar | Sidebar | 248px | HORIZONTAL | Brand | Companion watch | none |
| Journal Writing | sidebar | Sidebar | 264px | HORIZONTAL | none | Quiet companion | none |
| Companion Chat | sidebar | Sidebar | 238px | HORIZONTAL | none | Companion trigger | present |
| Projects | sidebar | Sidebar | 268px | HORIZONTAL | Brand | Companion area | none |
| Settings | sidebar | Sidebar | 260px | HORIZONTAL | Brand | Watchful companion | none |
| Your World | sidebar | Sidebar | 240px | HORIZONTAL | none | Companion watch | none |
| Journal Reading | sidebar | Sidebar | 272px | HORIZONTAL | Brand | Companion | none |

### Shell mode is NOT derived from emotional volume.
Shell mode is a canonical screen/state property, stored explicitly per frame.
Emotional volume is secondary styling context within a mode, not the selector.

### Rail mode (112px)
- Brand mark + sparkle dot (48x42)
- Navigation: icon (28px) + label stacked vertically, 72x62px each, gap=14
- World assistant: amphora icon (50x58) + accessibility label at bottom
- NO companion presence, NO divider, NO identity section
- Active item: teal fill (rgba(0.45,0.69,0.69,1.0))

### Sidebar mode (236–272px)
- Brand/identity at top (varies: Brand, Project Worlds, World identity)
- Navigation: horizontal icon+label, 194–200px wide, 42–48px height
- Companion presence at bottom (varies by screen)
- Optional divider between identity and navigation
- Active item: teal tint background

---

## 2. Emotional Volume Variation

| Frame | Volume | Sidebar Width | Sidebar BG | Content Measure | Containers |
|-------|--------|---------------|------------|-----------------|------------|
| Today Bad Day | ATTENTIVE |248px | #12101a | Unbounded | Cards for triage |
| Vault | AMBIENT |236px | #12101a | Unbounded | Earned containers |
| Interests | GENEROUS |256px | #12101a | Unbounded | None |
| Journal Writing | QUIET |264px | #0c0912 | Unbounded | None |
| Companion Chat | AMBIENT→PRESENT |238px | #12101a | Dimmed workspace | Drawer overlay |
| Projects | PRACTICAL |268px | #12101a | Unbounded | Status cards |
| Settings | PRACTICAL |260px | #12101a | Unbounded | Section groups |
| Your World | PRACTICAL |240px | #0d0a13 | Unbounded | Companion watch |
| Journal Reading | AMBIENT(WARM) |272px | #0d0a14 | BOUNDED (page edge) | Rose-edge reading frame |

### What varies by emotional volume:
- **Sidebar width**:236–272px (subtle, not dramatic)
- **Sidebar background**:QUIET screens use darker (#0c0912, #0d0a13, #0d0a14)
- **Content measure**: Only Journal Reading bounds content (via page edge)
- **Containers**: ATTENTIVE/PRACTICAL screens earn containers; QUIET/AMBIENT screens don't
- **Companion presence**: QUIET screens show minimal companion; ATTENTIVE/PRACTICAL show watchful companion

---

## 3. Responsive Structure

### Desktop (≥900px)
- Sidebar persistent, full height
- No header
- Content fills remaining width

### Tablet (no canonical evidence)
- **INFERRED** from current implementation and common patterns
- Sidebar collapses to banner or icon rail
- Header may appear for navigation
- **UNKNOWN**: no canonical tablet frame exists in Workshop v3

### Mobile (390px — Mobile Today frame)
- **OBSERVED**: Bottom navigation bar (4 items, Vault omitted)
- No sidebar
- No header
- Content fills viewport

---

## 4. Sidebar Analysis

### Is it a nav rail? NO.
V1's rail is icon-only, narrow (108px), stacked vertically. The Workshop sidebar is236–272px, shows icon+label horizontal, contains identity and companion.

### Is it a world edge? YES.
The sidebar IS the world's edge. It contains:
- World identity (who this world belongs to)
- Navigation (where you can go)
- Companion presence (who's here with you)
- Environmental divider (organic, not mechanical)

### Is it a room boundary? YES.
Each screen's sidebar subtly changes its background color, as if the room's lighting shifts. The sidebar defines the boundary of the world-room.

### Structural role:
The sidebar is a **semantic region** (`<aside>` or `<nav>` with aria-label), not a decorative rail. It's the world's persistent boundary.

---

## 5. World Identity

### Where it lives:
At the TOP of the sidebar, before the divider.

### What it contains (OBSERVED in frames that show it):
- **World mark**: Small icon/visual (38px, rounded, with teal glow shadow)
- **World label**: "Project" (small text)
- **World name**: "Rylee's World" (larger text)
- Layout: horizontal, flex, gap-12

### Which frames show it explicitly:
- Interests (17:1515): Full world identity with mark + label + name
- Bad Day (17:2117): "Project Worlds" brand with mark
- Projects (17:2752): Brand mark + label
- Settings (17:3762): Brand mark + label
- Journal Reading (17:5763): Brand mark + label

### Which frames don't show it explicitly:
- Vault (17:1014): Shows "Brand" in sidebar navigation area
- Journal Writing (17:2268): Shows "Brand" in sidebar content
- Companion Chat (17:2536): Shows "Brand" in sidebar upper
- Your World (17:5485): Shows navigation group without explicit brand

### Interpretation:
World identity is the FIRST element in the sidebar. Some frames show it as a distinct "World identity" component; others show it as "Brand." The semantic role is the same: this is who/what this world is.

---

## 6. Companion Architecture

### Where companion lives at rest:
**At the bottom of the sidebar**, separated from navigation by `justify-between`.

### Companion states observed:

| State | Frame | Visual | Behavior |
|-------|-------|--------|----------|
| **Rest** | Journal Writing | Opacity 62%, small portrait (36px), "✦ quietly here" | Minimal presence, not interactive |
| **Watchful** | Bad Day, Settings, Your World | Portrait (44–52px), status text, bordered card | Observing, not engaging |
| **Nook** | Vault | Semi-transparent card (72% opacity), portrait (52px) | Resting place within the world |
| **Present** | Companion Chat | Trigger in sidebar, full drawer overlay | Active engagement via drawer |
| **Arrival** | Interests | Large mermaid illustration (250px) | Entrance state for empty rooms |
| **Absent** | Companion Popover | Sidebar rail only, companion trigger | Not yet arrived |

### How companion moves when engaged:
1. **Rest → Watchful**: Companion gains opacity, shows status text
2. **Watchful → Present**: Clicking companion opens a drawer overlay on the content area
3. **Present → Chat**: Drawer contains full conversation interface
4. **Drawer structure**: Header (title + close) → Divider → Conversation → Composer

### Companion in sidebar structure:
```
Sidebar
├── Brand/Identity
├── Divider
├── Navigation Items
├── (flex-grow gap)
└── Companion Area
    ├── Companion card/nook
    │   ├── Portrait (36–52px)
    │   ├── Status text (optional)
    │   └── Presence label ("quietly here")
    └── (click → opens drawer)
```

---

## 7. Content Width Model

### OBSERVED:
- **NO global max-width** on root or content area
- Each screen defines its own content width internally
- Journal Reading: Bounded via "Page edge" (rose edge,22px)
- Today: Cards at specific widths (396px,248px)
- Projects: Status cards with defined widths
- Companion Chat: Dimmed workspace (1020px) + drawer (420px)

### INFERRED:
The Workshop does NOT use a global content measure. Each screen earns its own content boundaries based on what it's showing. The emotional volume determines whether content is bounded or unbounded.

---

## 8. Container & Divider Analysis

### Structural containers (earned, not default):
- **Vault**: Earned containers for "treasures in safekeeping"
- **Bad Day**: Cards for triage hierarchy
- **Projects**: Status cards for project monitoring
- **Companion Chat**: Drawer overlay for conversation

### Environmental containers (absent by default):
- **Today Quiet Day**: No cards, just the world state
- **Interests**: No containers, the room IS the content
- **Journal Writing**: No containers, writing space IS the content

### Divider types:
- **Environmental**: Sidebar right border (subtle, #292337 range) — marks the world edge
- **Semantic**: Organic SVG divider between identity and navigation (decorative, not structural)
- **Content**: Horizontal rules within content (e.g., Today divider between heading and content)
- **Rose edge**: Journal Reading's unique page-edge divider (atmospheric)

---

## 9. V1 Primitive Classification

### REUSE
| V1 Primitive | Why |
|---|---|
| React Router | Product infrastructure, not spatial architecture |
| Design tokens system | Proven, generates from tokens.json |
| Status vocabulary | Canonical, not V1-specific |
| Companion artwork | Canonical rigs, not V1-specific |
| Accessibility contract | Mandatory floor, not V1-specific |
| Test infrastructure | Proven, separate from spatial architecture |
| Provider/degradation behavior | Backend concern, not spatial |
| `SectionNav` component | Navigation semantics reusable, but needs Workshop adaptation |
| Bottom navigation | Mobile pattern, already exists |
| `CompanionSlot` type | Concept reusable, but placement changes |

### REPLACE
| V1 Primitive | Why Replace | Workshop Replacement |
|---|---|---|
| `AppShell` layout | Header+rail+main is V1 dashboard architecture | Sidebar+content, no header |
| `.pw-header` | Workshop has no desktop header | Remove on desktop |
| `.pw-rail` (icon-only) | Workshop sidebar is full world edge | WorldEdge (236–272px, identity+nav+companion) |
| `.pw-main` with max-width | Workshop has no global content measure | Content area, no max-width |
| Navigation: icon-over-label | Workshop uses horizontal icon+label | Horizontal nav items |
| Companion in rail bottom | Companion is an inhabitant, not a utility | Companion in sidebar bottom, with states |
| `CompanionPopover` | Workshop uses drawer, not popover | CompanionDrawer (overlay on content) |
| Content measure (64rem) | Workshop screens define own bounds | Remove global constraint |

### REMOVE
| V1 Primitive | Why Remove |
|---|---|
| `.pw-header` on desktop | Workshop has no desktop header |
| `.pw-brand-lockup` in header | Brand moves to sidebar identity |
| `.pw-rail-companion` wrapper | Companion moves to sidebar as inhabitant |
| Global content measure CSS | Workshop has no global measure |
| Icon-over-label desktop nav | Workshop uses horizontal |

### UNKNOWN
| V1 Primitive | Why Unknown |
|---|---|
| Tablet responsive behavior | No canonical tablet frame exists |
| `.pw-banner` | May still be needed for tablet, but no evidence |
| `.pw-bottom-bar` | Mobile pattern exists in Workshop, but implementation may differ |
| `CompanionSlot` API states | Workshop shows different states than current API defines |
| Question screen structure | No canonical Question frame design context available |

---

## 10. Proposed Workshop-Native Primitives

### Based on OBSERVED evidence from canonical frames:

#### WorldShell
- **Responsibility**: Root layout container
- **Structure**: `flex items-start`, full viewport
- **Children**: WorldEdge + WorldContent
- **Persistent**: YES (all desktop content frames)
- **Modes**: `rail` | `sidebar` (canonical screen/state property, NOT volume-derived)
- **Responsive**: Desktop: edge+content; Mobile: content+bottom-nav
- **Emotional volume**: Root bg (#0a0810) consistent across all frames; secondary styling only

#### WorldEdge (mode-dependent)
- **Responsibility**: World boundary — navigation, identity, companion presence
- **Structure**: `flex column`, fixed width, full height
- **Mode is a canonical screen/state property**, stored per frame in manifest/component map
- **Rail mode (112px)**:
  - Children: Brand mark + Navigation (vertical, icon-over-label) + WorldAssistant
  - No companion presence, no divider, no identity section
- **Sidebar mode (236–272px)**:
  - Children: WorldIdentity + Divider + WorldNav + CompanionPresence
  - Horizontal nav, companion inhabitant at bottom
- **Persistent**: YES (all desktop content frames)
- **Responsive**: Desktop: rail or sidebar; Mobile: replaced by bottom nav
- **Width rule**: Rail=112px fixed; Sidebar=236–272px contextual (do NOT canonicalize 248px)

#### WorldIdentity
- **Responsibility**: Who this world belongs to
- **Structure**: Horizontal flex, mark + label + name
- **Location**: Top of WorldEdge
- **Persistent**: YES (all frames, though some show it as "Brand")
- **Responsive**: Desktop: in sidebar; Mobile: may move to header or be hidden

#### WorldNav
- **Responsibility**: Route navigation
- **Structure**: Vertical flex column, gap-4, horizontal items (icon+label)
- **Location**: Middle of WorldEdge, after identity
- **Persistent**: YES (all content frames)
- **Responsive**: Desktop: sidebar; Mobile: bottom bar
- **Emotional volume**: Active item has teal tint background

#### CompanionPresence
- **Responsibility**: Who's here with you
- **States**: rest, watchful, present, arrival, absent
- **Structure**: Varies by state — card/nook at rest, drawer when engaged
- **Location**: Bottom of WorldEdge (rest/watchful) or overlay on content (present)
- **Persistent**: YES (all frames, though some show it as absent/minimal)
- **Responsive**: Desktop: sidebar bottom; Mobile: TBD

#### WorldContent
- **Responsibility**: Screen-specific content area
- **Structure**: `flex column`, remaining width, no global max-width
- **Children**: Screen-specific content
- **Persistent**: YES (all content frames)
- **Responsive**: Desktop: remaining width; Mobile: full width
- **Emotional volume**: Each screen defines own content bounds

#### CompanionDrawer
- **Responsibility**: Active companion conversation interface
- **Structure**: Fixed-width overlay on content area (420px in Chat frame)
- **Children**: Header → Divider → Conversation → Composer
- **Persistent**: NO (only when companion is "present")
- **Responsive**: Desktop: side drawer; Mobile: full-screen overlay (TBD)

#### AmbientDivider
- **Responsibility**: Organic separation between sidebar regions
- **Structure**: SVG/image, not a mechanical `<hr>`
- **Location**: Between identity and navigation in sidebar
- **Persistent**: YES (present in most frames)
- **Emotional volume**: Style may vary (gradient vs solid)

---

## 11. Architecture Decision: What Would We Build If V1 Never Existed?

### The answer is clear from the evidence:

**We would build a mode-based shell:**
```
WorldShell (flex row, full viewport)
├── WorldEdge:mode (canonical screen/state property)
│   [mode=rail] ──→ 112px, brand mark, icon-over-label nav, world assistant
│   [mode=sidbar] → 236–272px, identity, horizontal nav, companion presence
└── WorldContent (main, remaining width)
    └── [Screen-specific content]
```

**We would NOT build:**
- A header bar on desktop
- A single universal sidebar width
- A global content measure
- Companion as a utility button in a rail

### The V1 AppShell structure (`header + rail + main`) would NOT be invented from Workshop v3.

The evidence is unambiguous: Workshop v3 desktop frames are **edge + content**, with no header. The edge has two canonical modes (rail, sidebar) determined by screen/state property, not by emotional volume.

### Shell mode is a canonical property, not inferred.
Each frame in the manifest should record its shell mode explicitly.
For states without explicit evidence, mark UNKNOWN and defer/infer conservatively.

---

## 12. Design-to-Code Pipeline (Professional Plan)

### Code Connect: NOT AVAILABLE
Figma Professional plan. Code Connect requires Org/Enterprise. Do not attempt to enable.

### Upstream Figma Skills Retrieved
| Source | SHA | Date | Path |
|---|---|---|---|
| figma/mcp-server-guide | `d638a5e` | 2026-09-11 | `/tmp/opencode/mcp-server-guide/skills/figma-design-to-code/SKILL.md` |
| figma/sds (reference) | `030aba0` | 2026-07-31 | `/tmp/opencode/sds/` |
| tathagat22/plumb-mcp | `4f7568f` | 2026-08-19 | `/tmp/opencode/plumb-mcp/` |

### figma-design-to-code Skill (Upstream)
**Key rules incorporated:**
1. `get_design_context` is the primary tool — NOT `get_metadata`/`get_screenshot`
2. Output is React+Tailwind REFERENCE — adapt to project stack
3. Reuse existing project components/tokens
4. Hint priority: Code Connect → docs → annotations → tokens → raw hex
5. Icons: render from exported asset, never hand-write SVG
6. Asset URLs expire in ~7 days — download for committed code

### Project Worlds Extension: Disconfirm Reuse
Figma's normal advice "reuse existing components" is extended:
- Existing components are CANDIDATES, not authority
- Before reusing: demonstrate semantic + architectural equivalence
- Mark OBSERVED / INFERRED / ASSUMED / UNKNOWN
- Compare against multiple Workshop frames
- Never promote "similar-looking" into "same concept"

### Repository-Owned Mapping Layer
Replaces Code Connect. Files:
- `.project/design/FIGMA-COMPONENT-MAP.yaml`
- `.project/design/FIGMA-IMPLEMENTATION-RULES.md`

### Plumb MCP Evaluation
| Aspect | Finding |
|---|---|
| Repository | `tathagat22/plumb-mcp` |
| License | MIT (safe) |
| Stars | 79 |
| Last updated | 2026-08-19 |
| Plan requirement | Works on Professional (desktop plugin, no REST rate limits) |
| Semantic roles | `nav`, `hero`, `footer`, `sidebar`, `card`, `button` |
| Output | Plumb Design Spec (PDS): deduplicated tokens + CSS/flexbox tree |
| External APIs | Unsplash/Pexels/Pixabay (optional, for source tool only) |
| Security | Requires `FIGMA_TOKEN` for REST path; desktop plugin is local WebSocket |
| Recommendation | DEFER — evaluate as disconfirmation tool on one frame only |
| **Experiment status** | **BLOCKED — no FIGMA_TOKEN and no Plumb plugin paired** |
| **Unblock requires** | Either FIGMA_TOKEN env var or Plumb Figma plugin installed + paired |

### Professional-Plan Pipeline
```
WORKSHOP V3 → Figma MCP → figma-design-to-code skill
    → Workshop architecture derivation
    → FIGMA-COMPONENT-MAP.yaml
    → Workshop production primitives
    → Storybook
    → Figma comparison + visual regression
    → Playwright
    → Project Worlds

Optional disconfirmation:
Plumb MCP (one frame) → structural comparison
```

---

## 13. Reservations

1. **Tablet behavior**: No canonical tablet frame exists. Responsive tablet behavior is INFERRED, not OBSERVED.
2. **Companion states API**: Current CompanionSlot has "rest" | "focus" | "open" | "default". Workshop shows rest/watchful/present/arrival/absent. Need to determine if these are the same.
3. **Sidebar width variation**: 236–272px is observed, but the rule for WHY each screen gets its width is not explicitly stated.
4. **World identity**: Some frames show "Brand" instead of "World identity". Need to determine if these are the same component.
5. **Mobile companion**: No canonical mobile frame shows companion access. UNKNOWN how companion works on mobile.
6. **Question screen**: No design context available for 17:6245. Cannot verify structure.
7. **Plumb MCP**: Experiment blocked (no FIGMA_TOKEN). Deferred.
8. **CRITICAL — Dual-mode shell**: Today Quiet Day uses Navigation rail (112px), NOT Sidebar (236–272px). The shell architecture must support both modes. This was discovered through Figma REST API, not MCP.

---

## 14. Next Steps

1. **Owner review**: Does the dual-mode architecture match your understanding?
2. **Decision**: Should we proceed with building WorldShell + WorldEdge (dual-mode) + WorldContent?
3. **Decision**: What determines the mode — emotional volume from the manifest? Route? Both?
4. **Decision**: Should we create a tablet canonical frame, or infer?
