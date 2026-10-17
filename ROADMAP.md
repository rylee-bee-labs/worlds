# Roadmap

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see `.project/PLAN.md`) · **Read this if:** you want the dated horizon record, not current direction · **Superseded by:** [`.project/PLAN.md`](./.project/PLAN.md) (current direction) and [`docs/TRUE-NORTH.md`](./docs/TRUE-NORTH.md) (principles; its scope is itself superseded by PLAN)

**In short:** This is the old roadmap — a horizon record re-verified on 2026-09-17, before the `ui/` flip. It no longer describes how Worlds is built. Read `.project/PLAN.md` for what we are doing now.

What changed since this record was written: the interface is `ui/` (the Bridge is home, 2026-09-25), the product is called **Worlds** in prose, rooms/registry/crew/doorways are the core architecture, and Discovery/Candy extraction is in progress. The Station is a theme package, not the product UI.

Direction, not promises. Project Worlds is developed by one human with
an AI-agent workflow; items move between horizons freely and nothing
here is a delivery commitment. Dates exist only where a milestone has
already happened.

Grounding: every item below was re-verified against the code on
2026-09-17 before being kept — implemented items were removed, and
items from retired eras (the T15 React cutover, the Workshop v3
React-frame implementation) are not listed unless the gap survives in
the current tree. For the target daily-use experience,
`docs/PERSONAL-WORLD-FINISH-LINE.md` is authoritative; this roadmap
organizes direction and does not redefine "finished enough to live in
every day".

Current context: the repo is single-branch `main`; the **Station**
(same-origin at `/station/`, sourced from
`design/opendesign-exploration/station/`) is the product UI; the
superseded React SPA was removed 2026-09-16.

## Direction — the primary-viewport limb (owner D21–D24, 2026-09-21)

"Worlds as primary viewport" is a **named lighthouse on the single Road-to-1.0** (studio
`ROADMAP.md`). The Workbench/Node/Agent work is a **limb over the existing homelab estate**, not a
second platform. Canonical direction: studio `ROADMAP.md` lighthouse + `docs/adr/0003`–`0007`
(proposed) + `.project/DECISIONS.md` (2026-09-21) + the rules in `AGENTS.md` § "Workbench & Node
direction". Sequencing: **Station flip first** (foundation); the thin Workbench slice (attach the
existing `ai-distrobox` → terminal → build → stream → preview → artifacts + one host capability)
follows. **Headscale + Tailscale** (BSD-3, fully open; NetBird dropped — open-core/enterprise gate) is the
preferred Node-networking overlay; **tailcat** (BSD-3) is a complementary point-to-point tool, not the
coordinator. None is a dependency of the first slice.

The first-release **product language & interaction contract** (owner-approved 2026-09-21) lives at
[`docs/PRODUCT-LANGUAGE.md`](docs/PRODUCT-LANGUAGE.md): the stable skeleton (`Overview · Memory · Chat ·
Settings`) + personal sections, Records-vs-Vault, the default theme (Mulberry & Mint since 2026-10-12; starfield before), and the theme
boundary (restyle, never rename/relocate).

## Now

Gaps that are real and verifiable in the current tree:

- **Specimen → real data.** The Station's real-data layer
  (`station/real-data.js`) wires needs-you, journal, and preferences,
  but interests/discovery cards, projects repositories, media, and the
  map's per-region activity/provenance/suggestion copies still render
  clearly-labelled specimen panels where no endpoint or provider
  connection exists. Wire them to real data or keep honest empty
  states (per decision #3) — no fake data.
- **Chat wiring + streaming.** The Station chat surface is currently a
  local-only prototype by its own admission (`station/chat.js`: "does
  NOT invent companion replies; send binds to the real chat
  capability later"). Bind send to the real chat endpoints
  (API-010..012), conversation history, and provider streaming — every
  provider in `chat_registry.py` still posts `stream: False`.
- **Stronger step-up authentication.** Step-up today is a time-window
  trust elevation (`grant_step_up` in `src/personal_world/auth.py`),
  not fresh credential re-verification. The finish line requires
  stronger authentication for severe/destructive actions and sensitive
  vault access; harden without breaking the fail-closed bearer-token
  boundary or recoverable bootstrap.
- **Theme-pack completion.** The pack registry exists
  (`src/personal_world/theme_pack.py`) and Station settings bind
  palette/theme preferences via API-065; full frontend application of
  pack assets, state poses, and per-pack icon families from
  `design/THEME_PACK_FRAMEWORK.md` remains incomplete.
- ~~**Ingress rollup operational verification.** The provider
  (`providers/traefik_ingress.py`, `/api/ingress/rollups`) exists;
  verify configured-provider behaviour in a real deployment —
  implementation alone is not operational acceptance.~~
  Dropped 2026-10-15 (owner decision): no agent can produce this evidence.

## Next

- **Source-control enrichment breadth.** Native Git feeds
  dashboard/chat context; GitHub enrichment
  (`providers/github.py` + `/api/source-control/enrichment`) adds
  remote identity, open PRs/issues, default branch. Broader
  project/repository mission control remains finish-line work.
- **Test-contract hygiene.** The harness knows pre-existing
  environment-sensitive failures (`tests/test_updates.py`
  docker-daemon tests) and the docs/pointers test suite keeps growing
  ad hoc; consolidate gates so `pytest` CI and the Playwright Station
  suite (`frontend/e2e/`) stay the two canonical checks.

## Exploring

No commitment, preserved ideas:

- Further mobile refinement of the Station (the CSS already carries
  phone bottom navigation and larger-target adaptations).
- Capability/accessibility interview beyond the implemented five-step
  setup wizard.
- The Figma remote MCP (mcp.figma.com) rejects non-catalog clients;
  if OpenCode is ever catalog-listed, the desktop-MCP bridge could be
  simplified.

## Completed

- 2026-09-16: single-branch cutover. The superseded React SPA, its
  `/legacy-react` route, SPA fallback, and dist build pipeline were
  removed; the Station is the product UI; branches retired to
  annotated `archive/2026-09-16/*` tags.
- 2026-09-15: finish pass + integration pass merged to `main` (PR #50
  D1–D3 auth/authority convergence; PR #53 honest capability health,
  fail-closed vault reporting, corrected roadmap claims).
- 2026-09-12: trunk unification, project rename to Project Worlds,
  Play-Nice adoption, OCI image distribution via GHCR, production
  compose appliance bring-up.
- 2026-09-13: Workshop v3 design convergence recorded from Figma MCP
  evidence; first implementation frames landed during the React era
  (removed with that era on 2026-09-16; manifest preserved in
  `.project/design/WORKSHOP-V3-MANIFEST.yaml` as design provenance).
- Shipped earlier (2026-09-06..09): core world model, CLI, API,
  provider framework with zero-provider boot, secret vault
  (Fernet, fail-closed), accessibility-preference wiring, chat surface
  with provider-neutral adapters (`ollama`/`openai_compat`), quick
  actions, apps/services launcher, first-run setup wizard, multi-user
  provisioning per principal, standalone deployment, CI, security and
  public-safety gates.
