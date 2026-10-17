# Personal World → Figma: Project Context You Asked For

Answers to the questions from your first pass (2026-09-12), from current
repository evidence — verified, not remembered. `UNKNOWN` is honest; nothing
here guesses. Canonical files govern; this routes.

Machine-readable design truth: `.project/design/CURRENT.md` (fuller, with
frame IDs). This file is the concise companion.

## CURRENT DESIGN AUTHORITY

- Canonical tokens: `design/tokens.json` (repo-owned). Your variable
  collection is derived, never canonical.
- Accessibility floor: `docs/accessibility/ACCESSIBILITY_CONTRACT.md` —
  outranks literal visual matching everywhere.
- Design-stage visual source: your file `VATVojyJZT9HKx0CrDS0yr`, for
  explicitly approved frames (list below).
- V0.1 baseline prose: `docs/history/DESIGN-HANDOFF.md` (partly superseded; its
  2026-09-10 reconciliation note governs).
- Composition lesson (2026-09-11): `docs/history/FIGMA-HANDOFF-LESSONS.md` — token
  checks do not verify composition; implementation passes must visually
  compare against your exports before merging.

## IMPLEMENTATION FRAMEWORK

React 19 + Vite + TypeScript SPA (`frontend/`), react-router v7, Tailwind v4
aliases, shadcn-derived primitives, Vitest/vitest-axe + Playwright,
generated `src/tokens.css` with a `tokens:check` drift gate (passing).
Served by the Python backend (`PW_FRONTEND=react`; legacy server UI remains
default until parity). `frontend-v2/` is an untracked experiment — not truth.

## CANONICAL VIEWPORTS

From `docs/accessibility/RESPONSIVE_RULES.md`: ≥900px fixed left rail
(72px) · 600–899px top banner · ≤599px fixed bottom nav. No 1200px
breakpoint. Your 1440/900 design frames map onto this implemented cascade.

## APPROVED FRAMES (V0.1 handoff status, not superseded)

`4:5` Today 1440 · `6:4` World Capability First · `3:445` Journal ·
`5:4` Settings Refined · `14:472` responsive cascade · `4:135` narrow 900 ·
today states `3:722`/`3:779`/`3:941`/`3:1044` · rules `14:5`, `14:914`,
`4:266` · patterns `5:283`/`5:449`/`5:587` · feature details `7:4`/`7:192` ·
companion `11:4`/`13:4`/`13:295` · themes `3:2005`/`3:2147` · handoff
`16:157`/`16:5`. Superseded (do not implement): `3:1438`, `7:565`, `9:5`,
`14:1147`, `7:371`. Reference only: `3:1268`, `6:230`.

**Chat frames approved?** UNKNOWN — your chat screens were exported
(2026-09-06) and are repo-tracked, but no approval is recorded in current
evidence; the archived frame index predates them. Owner decision pending
or unrecorded.

**Frame `197:902` approved?** UNKNOWN — no such frame exists in any
tracked evidence (frame index, exports, docs). Closest authoritative
detail frames: `7:4`, `7:192`. If it exists in your live file, it has no
repo-side representation or recorded approval.

## EXPERIMENTAL / UNKNOWN FRAMES

- Design Direction (`3:1268`), Reference Studies (`6:230`): reference.
- Theme boards (generic vs. rylee): reference for the theme-pack system.
- World Keeper frames: historical — superseded by the five-resident
  companion set (`design/COMPANION_INTEGRATION.md`, 2026-09-07):
  Mermaid, Little Helper Robot, World-tree Squirrel, Tacos & the Morning
  Paper, Personal World.

## IMPLEMENTED SCREENS

React routes live at `090d7d7`: `/` Today, `/interests`, `/media`,
`/projects`, `/lab`, `/chat`, `/journal`, `/vault`, `/world`, `/settings`
(+ `/login`, `/setup`). README-confirmed implemented pages: **Today, Chat,
World, Journal, Vault, Settings**. Current composition state: Today,
Journal, Vault use real h2 sections + quiet dividers (card chrome removed
2026-09-11); Settings intentionally denser/tabular; Lab renders a table.

## SEMANTIC TOKEN MAPPING

`design/tokens.json`: 14 colors (aubergine dark + light theme, teal
`#72b1b1` / dusty-rose `#b57f8b` accents), 8-word status vocabulary
(luminance-only rank), 4 spacing, 2 targets, motion `off|reduced|subtle`,
2 focus, 6 typography (~32 values). Generated layer:
`frontend/src/tokens.css` (drift-gated). **Your side: only 4 variables —
recorded as immature; repo tokens govern.** Do not manufacture a
Figma-side token completeness that does not exist.

## COMPANION STATUS

Five canonical residents (see above). Mermaid master Lottie is deliberate
artwork (byte-identical by decision); companion rigs, icon library, and
screen SVGs must not be casually regenerated. Runtime supports companion
selection + standalone Chat; contextual chat identities are Finish-Line
target work, not implemented.

## HOW TO IDENTIFY CURRENT VS SUPERSEDED

1. archived frame index status (provenance) →
2. later repo work that replaced it (CHANGELOG, design commits) →
3. `.project/design/CURRENT.md` →
4. ask the owner when still ambiguous.

## ACCESSIBILITY PRECEDENCE

Agreement, recorded: accessibility outranks literal visual matching; the
floor wins and conflicts are recorded back to you. 44px targets,
luminance-only rank encoding, motion reduced by default, OS
`prefers-reduced-motion` overrides app preferences, keyboard-complete,
real headings, 200% reflow.

## LOCAL EXPORTS AVAILABLE

Your recommended durable export set, classified against what actually
exists on disk (nothing manufactured):

| Recommended export | Status | What exists instead |
|---|---|---|
| `design/screens/today-desktop.png` | **NEEDS_FIGMA_EXPORT** | repo-tracked SVG: `design/screens/today-hybrid-desktop-1440.svg`; local PNG: `design/exports/0.1/` (today states, not desktop) |
| `design/screens/world-overview.png` | **NEEDS_FIGMA_EXPORT** | repo-tracked SVG: `design/screens/world-capability-first.svg` |
| `design/screens/journal.png` | **AVAILABLE** | repo-tracked: `design/screens/journal-screen.svg`; local PNG: `design/exports/0.1/journal-screen.png` |
| `design/screens/settings.png` | **NEEDS_FIGMA_EXPORT** | repo-tracked SVG: `design/screens/settings-refined.svg`; no PNG |
| `design/screens/chat-active.png` | **NEEDS_FIGMA_EXPORT** | repo-tracked SVGs: `design/screens/chat/chat-active-conversation.svg` + 8 more states |
| `design/screens/today-responsive.png` | **AVAILABLE** | local PNG: `design/exports/0.1/today-responsive-cascade.png`; repo SVGs: `today-hybrid-narrow-900.svg` |
| `design/frame-index.yaml` | **NEEDS_FIGMA_EXPORT** | machine-readable index does not exist; Markdown index exists: `design/handoff/FRAME_INDEX.md` (archived) |
| `design/CURRENT.md` | **AVAILABLE** | now exists at `.project/design/CURRENT.md` (project-owned answer file, 2026-09-12) |
| `design/tokens.json` | **AVAILABLE (already canonical)** | exists and IS the canonical token source; do not regenerate — your 4 variables derive from it, not the reverse. A Figma-side `tokens.json` export would be NOT_YET_MEANINGFUL until your variable set matures. |

Local (untracked) PNG exports live in `design/exports/0.1/` and
`~/figma_files/` (2026-09-11 re-exports). Repo-tracked screen references
are SVGs under `design/screens/`.