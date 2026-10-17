# How Personal World and Figma work together

Shared boundary document. Original proposal by Figma (first pass,
2026-09-12); corrected by Figma after reading the canonical resolved
bundle (same day) — her corrections applied to disk by the integration
session with provenance, because her sandbox filesystem is ephemeral.

## Best uses

- Designing screen composition, hierarchy, responsive cascades, companion
  artwork, theme packs.
- Exporting approved frames as PNG/SVG references for implementation passes.
- Answering "what does the current approved design look like for X?" via her
  help routing (see help-routing.yaml).

## Project context she works within (verified 2026-09-12)

- **Implementation framework:** React 19 + Vite + TypeScript SPA
  (`frontend/`), react-router v7, Tailwind v4 aliases, generated
  `src/tokens.css` with a `tokens:check` drift gate. Served by the Python
  backend (`PW_FRONTEND=react`; legacy default until parity).
- **Canonical viewports:** >=900px fixed left rail (72px) / 600-899px top
  banner / <=599px fixed bottom nav. No 1200px breakpoint
  (`docs/accessibility/RESPONSIVE_RULES.md`). Her 1440/900 frames map onto
  this implemented cascade.
- **Token authority:** `design/tokens.json` (repo) is canonical; her
  variable collection (4 variables, immature) derives from it, never the
  reverse. She is NOT authoritative for canonical token values.
- **Companion residents:** five canonical (Mermaid, Little Helper Robot,
  World-tree Squirrel, Tacos & the Morning Paper, Personal World); World
  Keeper frames are historical.
- **Chat screens + frame `197:902`:** status unknown — no recorded
  approval; `197:902` is agent-generated and not in repo evidence.

## What to check before asking her

- `.project/design/CURRENT.md` — the project's current design-truth answers.
- `design/handoff/FRAME_INDEX.md` — archived frame index (historical).
- `docs/accessibility/ACCESSIBILITY_CONTRACT.md` — outranks literal visual
  matching everywhere.

## How to consume her output

- Extract values; never eyeball (design-source-and-fidelity).
- Exports are derived artifacts; repo-tracked copies under `design/`.
- Frame node IDs are provenance — keep them beside implemented components.
- **Hard requirement (visual-fidelity-and-composition §9, D0-D4):**
  implementation passes must verify the right level and never claim design
  completion from D0/D1 alone:
  ```text
  D0 — TOKENS:     colors, typography primitives, spacing values
  D1 — STRUCTURE:  correct semantic elements/components
  D2 — COMPOSITION: hierarchy, grouping, density, rhythm, proportion
  D3 — BEHAVIOR:   responsive, interactions, states
  D4 — EXPERIENCE: does the actual human experience match the intended product?
  ```
  D2 requires eyes: browser-side visual comparison against her approved
  frames BEFORE composition work merges (the compare-before-code gate).
  D4 requires human acceptance. Token gates (D0) are never sufficient
  evidence of fidelity — this exact failure mode was observed in this
  project (docs/history/FIGMA-HANDOFF-LESSONS.md).

## What NOT to assume

- Do not assume she remembers anything between sessions — reload project
  context and her pack every session (her recorded limitation).
- Do not assume her file writes persist — her sandbox filesystem is
  ephemeral; content must be relayed or foreman-applied with provenance.
- Do not assume Figma variable state equals the token system (4 variables;
  repo tokens govern).
- Do not treat archived handoff statuses as current approval.
- Do not ask her about product priority, deployment, runtime health,
  authorization, security policy, code correctness, or canonical token
  values — see help-routing.yaml.

## Recorded agreements (not conflicts)

Classified from her first pass:

1. **PARTICIPANT LIMITATION** — no persistent cross-session memory; future
   sessions must reload project context and participant data. (Plus, now
   observed twice: ephemeral sandbox filesystem.)
2. **CONTRACT AGREEMENT** — token correctness does not establish visual
   fidelity; composition requires visual comparison. She cited D0-D4 from
   the canonical text — verified she read it.
3. **CONTRACT PRECEDENCE AGREEMENT** — accessibility requirements outrank
   literal visual matching; preserve visual intent within the floor.

No material contract conflicts exist between Figma and this project.