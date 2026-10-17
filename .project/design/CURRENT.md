# Project Worlds — Design Context: CURRENT

> **Superseded in part by [ADR-0008](../../docs/adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

*(Renamed from "Personal World" 2026-09-12 — product identity only; the
design file, frame IDs, and companion character names below are
unaffected. See `.project/CURRENT.md` "Identity pass" for the full
classification.)*

Answers current design questions from repository evidence, verified
2026-09-12 by the integration session, and **re-verified + extended
2026-09-13 by the Figma-bridge bootstrap session** (Workshop v3 authority
below). **This file routes; canonical files govern.** When this file and a
canonical file disagree, the canonical file wins. `UNKNOWN` is an honest
answer, not a gap to fill.

> **2026-09-16 era note.** The React-SPA implementation described in
> "IMPLEMENTATION FRAMEWORK" below was the implementation truth of the
> T15 era only. That SPA, its `PW_FRONTEND` mode switch and its dist
> build pipeline were removed on 2026-09-16 (single-branch cutover).
> The current product UI is the **Station** (`/station/`, sources in
> `design/opendesign-exploration/station/`); `/login` and `/setup`
> are server-rendered. The implementation sections below are kept for
> design provenance; the Workshop v3 frame inventory remains design
> evidence, not the current frontend.

Evidence basis: git history at `090d7d7`, README "What works today",
CHANGELOG (Unreleased + 2026-09-07..09), docs/history/DESIGN-HANDOFF.md
(V0.1 baseline note), docs/accessibility/* (canonical),
design/handoff/FRAME_INDEX.md (archived), design/tokens.json,
frontend/ sources, live `npm run tokens:check` (passing); Workshop v3
evidence retrieved 2026-09-13 from the Figma desktop Dev Mode MCP server
(see WORKSHOP V3 below and
[WORKSHOP-V3-MANIFEST.yaml](WORKSHOP-V3-MANIFEST.yaml)).

## CURRENT DESIGN AUTHORITY

- **Canonical design truth:** `design/tokens.json` (repo-owned, semantic,
  implementation-neutral) + `docs/accessibility/` (the floor).
- **Current implementation design authority: Workshop v3 warmth frames**
  (approved 2026-09-12/13; convergence audit passed; all 16 explorations
  viable, 8 revised frames audited). Machine-readable frame inventory with
  exact node IDs: [`.project/design/WORKSHOP-V3-MANIFEST.yaml`](WORKSHOP-V3-MANIFEST.yaml).
  **Today — Quiet Day is implementation target #1** — node `17:481` in
  Figma file `Wbg1rdt9fVCjWAXEKI1pTc` ("Workshop v3 evidence file"),
  NOT the older `13:14` same-name iteration and NOT the V0.1 Today-empty
  frame `3:722`. `personal-world-implement-figma` retrieves design context
  + screenshot per its workflow.
- **V0.1 frames are historical provenance, not current implementation
  targets** (see APPROVED FRAMES below — kept for provenance; superseded
  for implementation by Workshop v3 where the same route exists).
- **Design-stage visual sources:** Figma file `VATVojyJZT9HKx0CrDS0yr`
  (product design file — DO NOT MODIFY per the v3 audit's canonical
  authorities) for V0.1-era frames; Figma file `Wbg1rdt9fVCjWAXEKI1pTc`
  for Workshop v3 evidence (frames, philosophy, audit, lore registry).
  MCP access: Figma desktop Dev Mode MCP server (localhost:3845 on the
  operator's Figma machine; reach via the operator's tunnel — see
  "Figma bridge" in `.project/CURRENT.md`). The remote MCP
  (mcp.figma.com) rejects non-catalog clients, including opencode.
- **`docs/history/DESIGN-HANDOFF.md`** is the canonical *V0.1 baseline* reference;
  its dated inventories are historical (per its own 2026-09-10
  reconciliation note). The Finish Line document describes the target
  horizon, not the current design.
- **Composition lessons:** `docs/history/FIGMA-HANDOFF-LESSONS.md` (2026-09-11) —
  token gates do not check composition; browser-side visual comparison
  against Figma exports is required before composition work merges.

## IMPLEMENTATION FRAMEWORK

- **React 19 + Vite + TypeScript** SPA tracked as `frontend/`
  (react-router-dom v7, Tailwind v4 `@theme` aliases, shadcn-derived
  primitives in `frontend/src/components/ui/`, oxlint, Vitest + vitest-axe,
  Playwright).
- Served by the Python backend in react mode via `PW_FRONTEND=react`
  (default stays `legacy` server-rendered mode until parity).
- Generated token layer: `frontend/src/tokens.css` from
  `design/tokens.json` (`npm run tokens:check` drift gate — passing at
  090d7d7). Self-hosted fonts/icons; no external font/icon requests.
- `frontend-v2/` (untracked) is an experiment; not implementation truth.
- The backend (`src/personal_world/api.py`) remains the legacy UI baseline.

## CANONICAL VIEWPORTS / BREAKPOINTS

From `docs/accessibility/RESPONSIVE_RULES.md` (canonical):

| Effective CSS viewport | Behavior |
|---|---|
| ≥900px | fixed left icon rail (`--rail-width: 72px`); no separate 1200px breakpoint |
| 600–899px | top banner with horizontal links; stacked shell |
| ≤599px | fixed bottom navigation (60px + safe-area inset) |

Figma's designed 1440/900 frames map onto this implemented cascade; the
implemented breakpoints govern.

## APPROVED FRAMES (V0.1 — historical provenance, superseded for implementation by Workshop v3 where the same route exists)

From the archived frame index (`design/handoff/FRAME_INDEX.md`) — V0.1
handoff status; **historical provenance as of 2026-09-13**. For routes
covered by Workshop v3 frames (Today, Vault, Login, Setup, Projects,
Chat, Notifications, Journal, Settings, World, Interests), the v3 frame in
WORKSHOP-V3-MANIFEST.yaml is the current implementation target instead.

- Handoff row: `16:157` (index), `16:5` (accessibility contract visual).
- Core screens: `4:5` Today Hybrid Desktop 1440, `6:4` World Capability
  First, `3:445` Journal, `5:4` Settings Refined.
- Responsive: `14:472` cascade, `4:135` narrow 900.
- Today states: `3:722` empty, `3:779` attention, `3:941` partial,
  `3:1044` loading.
- Rules/patterns: `14:5` responsive rules, `14:914` + `4:266` accessibility
  stress, `5:283`/`5:449`/`5:587` patterns, `7:4`/`7:192` feature details.
- Companion/themes: `11:4`, `13:4`, `13:295` (World Keeper construction —
  note: World Keeper predates the current five-resident companion set, see
  COMPANION STATUS), `3:2005` comfortable theme, `3:2147` high contrast.

**Chat frames — approved?** Chat screen SVGs (active conversation, empty,
error, thinking, tool capability, source provenance, long dense, contextual
VEFR, narrow responsive) were exported from Figma 2026-09-06 and are
repo-tracked, but **no approval status is recorded anywhere in current
evidence** — the archived frame index predates them. Approval: **UNKNOWN**
(owner decision pending or unrecorded).

**Capability detail frame `197:902` — approved?** **UNKNOWN.** No frame
`197:902` exists in tracked evidence (frame index, SVG exports, docs). The
closest authoritative detail frames are `7:4` and `7:192` (Feature Detail
1/2). If `197:902` exists in the live Figma file, it is not represented in
repo evidence and carries no recorded approval.

## WORKSHOP V3 (current implementation design authority)

Retrieved 2026-09-13 from the Figma desktop Dev Mode MCP server, file
`Wbg1rdt9fVCjWAXEKI1pTc`, single page "Workshop" (`0:1`). All values below
were read from the Figma file; the full inventory with node URLs, audit
notes, reservation attachments, and superseded-iteration mapping is
[WORKSHOP-V3-MANIFEST.yaml](WORKSHOP-V3-MANIFEST.yaml).

**16 warmth explorations, 16/16 converged** (classification map `17:9864`);
**8 revised frames audited** across 7 dimensions (audit `18:2`) — all
**CANONICAL REFERENCE — READY FOR IMPLEMENTATION**:

- **Today — Quiet Day `17:481`** (1440×1000, WARM) — **IMPLEMENTATION
  TARGET #1**. Mobile Today `17:1929` (390×844) is its responsive
  interpretation (same quiet-day state, bottom nav).
  **Implemented 2026-09-13** (slice commit on `main`; committed with
  `scripts/safe-commit.sh`, explicit paths). Implementation-state
  reservations, recorded for owner review — NOT silently resolved:
  - **mermaid-art / presence scale:** the frame's Mermaid illustration
    (~150px) normalizes to the canonical rig via `CompanionSlot`, which
    caps at the Empty-State 64px (`design/COMPANION_INTEGRATION` scale
    system; the manifest reservation names a 16→32→48→80→160→512px
    Direction A ladder, but no size tier above 64px exists in the
    component contract). Shipped at 64px with a proportionate settle
    gesture. Owner decision pending: introduce a larger Today tier or
    accept 64px.
  - **waves-ladder `17:586` (waterline):** fetched as a canonical export
    (`media_files/designs/personal-world/today/waves-ladder.svg`, served via `/today/`) but
    deliberately UNPLACED — its divider-like role overlaps the existing
    quiet-divider semantics; relationship needs owner review before it
    enters Today.
  - **no-fake-strings gate:** row 15's literal "recent changes" grep
    conflicted with the frame's panel heading; the gate was tightened to
    its actual rule (no fabricated change LISTS) and the heading now
    renders only from real `/api/daily` actions. Recorded in
    `frontend/src/test/no-fake-strings.spec.ts`.
  - **D4 (human experience) remains UNKNOWN** — pending Rylee's own
    review; commit approval is not D4 approval.
  - **UAT (2026-09-13, private local package):** 48 cases — 44 PASS,
    0 FAIL, 2 REVIEW (owner), 2 N/A — across canonical regions, all
    nine responsive boundary widths (0px overflow everywhere), zoom
    100–200% (CSS proxy), quiet-state truthfulness (real fixtures:
    quiet / activity / attention / degraded / populated journal), a11y
    visuals, and a Figma comparison sheet. No new defects; the two
    REVIEW cases are exactly the reservations above. Package:
    `~/.local/share/personal-world/uat/today-quiet-day-17-481/`
    (private; not in the repository).
- **Question `17:6245`** (1440×1000, AMBIENT → ATTENTIVE/CURIOUS) —
  **Implemented 2026-09-13** (commit `f3be17a`). Uncertainty-shaped
  attention (digest warnings whose capability status is canonical
  `unknown`, the loop.py `{capability}: {status}` shape) renders the
  frame's curious-companion question region: heading 17:6298, canonical
  framing lines 17:6300/17:6301 verbatim, evidence chip 17:6302–04 as a
  Level-4 disclosure exposing the capability's REAL warnings + honest
  observation age. Mixed attention (uncertainty + actionable) keeps the
  restrained list (importance ≠ urgency ≠ volume). The frame's sample
  DNS story is design prose, not content (row 15). Waves waterline
  dividers 17:6353/6359 UNPLACED under the waves-ladder reservation.
  D0–D3 PASS; **D4 PENDING_BUNDLED_UAT**. Implemented from preserved
  canonical evidence (complete cached `get_design_context` + reference
  screenshot retrieved from the live bridge 2026-09-13, provenance in
  the private multi-frame evidence set) — the live bridge was down at
  implementation time.
- **Mobile Today `17:1929`** (390×844, AMBIENT/WARM) — **Implemented
  2026-09-13** (commit `b88f633`). The ≤599px phone-bucket composition
  of the implemented Quiet Day: greeting band (17:1937) via
  `.pw-today-greeting-band` (phone-bucket only; desktop keeps the flat
  canvas), 28px greeting scale (17:1939), compact health pill
  (17:1944), italic avatar quiet message (17:1940–43, CompanionSlot
  micro in an aria-hidden rose circle; desktop keeps the 64px rig),
  icon-frame change rows (17:1958), rose left-border journal entries
  (17:1972). New canonical warmth tokens entered `design/tokens.json`
  first (T5 hex gate): `warmth.mobile_band_gradient`, `warmth.rose_tint`,
  `warmth.teal_tint`. The shell's shared bottom nav keeps ALL registry
  sections (≥44px); the frame's 4-item count is the **mobile-nav
  reservation**, recorded not resolved; the frame's waves decoration
  (17:2021) stays unplaced under the waves-ladder reservation.
  D0–D3 PASS; **D4 PENDING_BUNDLED_UAT**. Same preserved-evidence
  provenance as Question.
- **Vault `17:1014`**, **Login `17:1681`**, **Chat `17:2536`** —
  **Implemented 2026-09-13** (commits `600c3e4`, `02f6ee5`, `91560ff`).
  D0–D3 PASS; D4 PENDING_BUNDLED_UAT. Owner reservations: chat send
  button 36px vs 44px floor (floor won), login key icon (no canonical
  glyph), chat presence/thinking wording.
- **Projects `17:2752`**, **Setup `17:3039`**, **Notifications
  `17:6369`**, **Interests `17:1515`**, **Bad Day `17:2117`**,
  **Journal Writing `17:2268`**, **Settings `17:3762`**, **Companion
  Popover `17:4565`**, **World `17:5485`**, **Journal Reading
  `17:5763`** — **Implemented 2026-09-13** (commit `6d909cc`).
  D0–D3 PASS; D4 PENDING_BUNDLED_UAT.

**Canonical artifacts:** philosophy `17:8873` ("The world knows how loudly
to exist."), audit `18:2`, classification `17:9864`, lore registry `17:8255`,
design language `17:6852`, volume rules `17:7750` (GENEROUS → AMBIENT →
PRACTICAL → ATTENTIVE → QUIET), convergence roadmap `17:10084`.

**8 reservations** (normalization gaps, not blockers) with verbatim audit
wording live in the manifest: mermaid-art → Direction A rig `67:2`;
companion-art → canonical rigs `78:2`–`82:2`; mobile-nav item count;
chat-wrapping artifact; chat-patterns exploratory; font (Workshop uses Inter;
canonical is Young Serif + Instrument Sans); touch targets ≥44px; decoration
Unicode/aria-hidden encoding.

**Routes not in the revision pass:** Interests, Media, Lab, Journal detail,
World, Settings — these retain the V0.1/existing implementation as their
current reference until separately converged.

## EXPERIMENTAL / REFERENCE / SUPERSEDED

- Superseded Workshop iterations (do not implement): `13:14`, `13:110`,
  `13:315`, `13:410`, `13:184`, `13:658`, `16:3`, `16:2253`, `15:84`,
  `15:404`, `16:469` — see `superseded_iterations` in the manifest for the
  exact replacement node IDs.
- Reference (not implementation targets): `3:1268` Design Direction,
  `6:230` Reference Studies.
- Superseded (do not implement): `3:1438`, `7:565`, `9:5`, `14:1147`,
  `7:371` (archived "Row 10").
- Theme exploration frames (generic vs. rylee-theme boards) are reference
  material for the theme-pack system, not screen approvals.
- **How to identify current vs. superseded:** (1) archived index status;
  (2) whether later repo work replaced it (CHANGELOG/design commits);
  (3) `.project/design/CURRENT.md` — this file; (4) ask the owner when
  still ambiguous. Superseded means historical; it never means "delete
  provenance".

## IMPLEMENTED SCREENS (runtime truth)

Routes in the React frontend (`frontend/src/App.tsx` at 090d7d7):
`/` Today, `/interests`, `/media`, `/projects`, `/lab`, `/chat`, `/journal`,
`/vault`, `/world`, `/settings`, plus `/login` and `/setup` (auth routes).
README "What works today" confirms implemented pages: **Today, Chat, World,
Journal, Vault, Settings** (real data loading, explicit partial/error
states), plus the P1 composition passes (real headings, no card chrome on
Today/Journal/Vault). Legacy server UI coexists (`PW_FRONTEND` selects).

## SEMANTIC TOKEN MAPPING

- Canonical source: `design/tokens.json` (~32 leaf values):
  `color` (14: aubergine dark surfaces + light theme + accents
  `#72b1b1` teal / `#b57f8b` dusty rose), `status_vocabulary`
  (8 words, luminance-only rank encoding), `spacing` (4), `targets` (2),
  `motion` (1: off/reduced/subtle), `focus` (2), `typography` (6).
- Derived: `frontend/src/tokens.css` (generated; drift-gated, passing).
- **Figma-side variables: only four exist** (Figma's own report) — the
  Figma token representation is immature and NOT a meaningful canonical
  tokens source. Repo tokens govern; Figma derives.

## COMPANION STATUS

- **Canonical companion set:** five residents (Mermaid, Little Helper
  Robot, World-tree Squirrel, Tacos & the Morning Paper, Personal World) —
  `design/COMPANION_INTEGRATION.md` (2026-09-07) supersedes the earlier
  Mermaid-centric pass and the older **World Keeper** globe concept.
- World Keeper frames in the archived index are **historical** — kept as
  provenance, not current companion authority.
- Runtime: companion selection + standalone Chat page exist; contextual
  identities/tool workflows from the exported chat screens are target
  work (Finish Line), not implemented.
- **Crew poster (curated):** `design/screens/crew.png` — the five-resident
  character reference (front / ¾ / side / back, expressions, uniform
  details) plus the "Same Crew. Bigger Horizons." scene. Curated
  2026-09-17 from the owner's untracked drop (`design/owner/crew/crew.png`);
  the drop directory stays gitignored. Featured in the README.
- **Crew portrait (curated):** `design/screens/worlds.png` — the whole crew
  (Mermaid, Personal World, Little Helper, world-tree squirrel, taco news
  truck) under the world-tree. Curated 2026-09-17 from
  `design/owner/crew/worlds.png`; used as the closing README image in place
  of the older companion-trio preview.
- **Crew scene (curated):** `design/screens/crew-scene-sept17.png` — the wide
  "crew together" scene: Renai, Ratatoskr, Bolt, the Burrito Journalism truck,
  and Personal World in the shared uniform, among the book-leaf world-tree.
  Added 2026-09-17 from the owner's untracked drop
  (`design/owner/crew/crew-sept17.png`); the drop directory stays gitignored.
- **Crew asset set (curated):** `design/assets/crew/` — the full companion asset
  library, tracked 2026-09-17 from `design/owner/crew/newassets/` (gitignored):
  transparent **cutouts**, true-vector **SVGs** (five residents + planet emblem),
  the **app-icon/favicon set**, the three **attention-voice marks**, wide **room**
  art for People/Media/Systems/Places, **skies**, and **pose sheets**. See
  `media_files/designs/personal-world/crew/README.md`.
- Deliberate artwork — do not casually regenerate: Mermaid master Lottie
  (byte-identical by decision), companion source rigs, icon library,
  screen SVGs.

## ACCESSIBILITY PRECEDENCE

`docs/accessibility/ACCESSIBILITY_CONTRACT.md` is non-negotiable and
ouanks literal visual matching everywhere (contract agreement, recorded):
44px targets, luminance-only rank encoding, motion reduced by default,
keyboard-complete, real headings/landmarks, 200% reflow, and OS
`prefers-reduced-motion` unconditionally overriding app preferences.
When an approved frame and the floor conflict, the floor wins and the
conflict is recorded back to design.

## LOCAL EXPORTS AVAILABLE

See the export classification in
`.project/participants/figma/contract-return/project-context.md` — every
recommended export is classified AVAILABLE / NEEDS_FIGMA_EXPORT /
NOT_YET_MEANINGFUL / UNKNOWN against what actually exists on disk.