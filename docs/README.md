# Worlds — Documentation

> **Superseded in part by [ADR-0008](adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../FRONTEND-INVENTORY.md).

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the docs map: the source-of-truth file for each subject · **Read this if:** you need to find the one file that owns a subject before reading or editing it.

**In short:** this is the router for the `docs/` tree. It names one
canonical source per subject, so a new reader (agent or human) can
navigate without archaeology. Read it first, then jump to the owner file.

The product is now **Worlds** (formerly "Personal World", then "Project
Worlds"). Technical identifiers are intentionally unchanged: package
`personal_world`, CLI `personal-world`, repo `Rylee-Bee/personal-world`,
env prefix `PW_`.

## Source-of-truth files

One authority per subject. Where a summary and its source disagree, the
source wins.

| Subject | Canonical source | Notes |
|---|---|---|
| Current state | [`.project/CURRENT.md`](../.project/CURRENT.md) | The single current-state pointer. Routes; does not duplicate. When it and a canonical file disagree, the canonical file wins. |
| Direction | [`.project/PLAN.md`](../.project/PLAN.md) | Owner-approved 2026-09-25. Supersedes [`docs/TRUE-NORTH.md`](TRUE-NORTH.md) on **scope and sequencing**; TRUE-NORTH's accuracy and accessibility principles still hold. Where a summary and its source disagree, the source wins. |
| Architecture | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) | Current structure: world model, API surface, identity/auth, Vault, daily loop, export contracts. |
| World-model invariant | [`docs/NATIVE-BASELINE-AND-ENRICHMENT.md`](NATIVE-BASELINE-AND-ENRICHMENT.md) | Normative; enforced by `personal-world framework validate`. |
| Contracts index | [`AGENT_CONTRACTS.md`](../AGENT_CONTRACTS.md) | Registry of every contract, trigger, and authority. |
| Rooms (the current architecture) | [`src/personal_world/rooms.py`](../src/personal_world/rooms.py) + [`.project/contracts/adoption.yaml`](../.project/contracts/adoption.yaml) | A **room** is any service serving the Play-Nice ROOM contract `room/0` as an independent service; Worlds renders rooms. Worlds reads the room list from Project Home's `GET /api/rooms/registry` (`PW_ROOMS_REGISTRY_URL`). |
| Crew, companions, doorways | [`docs/COMPANION-CANON.md`](COMPANION-CANON.md) + [`docs/CREW-AND-STATION-THESIS.md`](CREW-AND-STATION-THESIS.md) | Names and roles, plus the per-person crew state (`crew.json`). |
| Accessibility | [`docs/accessibility/ACCESSIBILITY_CONTRACT.md`](accessibility/ACCESSIBILITY_CONTRACT.md) | Non-negotiable. Siblings: walkthrough, responsive rules, preference schema. |
| Human reliability | [`docs/HUMAN_RELIABILITY_CONTRACT.md`](HUMAN_RELIABILITY_CONTRACT.md) | Low-stimulation defaults, accurate status, recoverability. |
| Security / public boundary | [`SECURITY.md`](../SECURITY.md) | Gate: `tests/test_public_safety.py`. |
| Provider-neutral rule | [`docs/NATIVE-BASELINE-AND-ENRICHMENT.md`](NATIVE-BASELINE-AND-ENRICHMENT.md) + [ADR 0001](adr/0001-capabilities-core-owned-providers-optional.md) | Capabilities core-owned; providers optional. |
| Providers (how to add) | [`docs/PROVIDERS.md`](PROVIDERS.md) | Plus [`docs/surfaces/PROVIDER-MATRIX.md`](surfaces/PROVIDER-MATRIX.md) for the current map. |
| Design (current) | [`.project/design/CURRENT.md`](../.project/design/CURRENT.md) | Design authority pointer. Canonical frames: [`.project/design/WORKSHOP-V3-MANIFEST.yaml`](../.project/design/WORKSHOP-V3-MANIFEST.yaml). |
| Design tokens | [`design/tokens.json`](../design/tokens.json) + [`design/themes/*.json`](../design/themes/) | `design/tokens.json` holds the token **names and immutable values** (the contract); the per-theme palettes live in `design/themes/*.json` (default: `starfield`). Both feed `ui/scripts/generate-tokens.mjs` → `ui/src/generated/tokens.{css,ts}`. Theme-pack contract: [`ui/THEMES.md`](../ui/THEMES.md). |
| Worlds kit (design language export) | [`ui/dist-kit/`](../ui/dist-kit/) | Framework-free export of the design language (`tokens.css`, `base.css`, `fonts`, `kit.json`, `preview.html`) that other estate projects vendor. Build and gates live in `ui/` (`npm run kit:build`, `kit:check`, `kit:test:e2e`). |
| V0.1 design baseline | [`docs/history/DESIGN-HANDOFF.md`](history/DESIGN-HANDOFF.md) | Dated baseline, not a current feature inventory. |
| Surfaces (UI/API/CLI/tool/storage/auth) | [`docs/surfaces/MASTER-SURFACE-REGISTRY.md`](surfaces/MASTER-SURFACE-REGISTRY.md) | Extraction index; all IDs resolve here. (The 2026-09-16 wiring map is [`docs/repo/WIRING-READINESS.md`](repo/WIRING-READINESS.md), now historical.) |
| Operations / deployment | [`docs/OPERATIONS.md`](OPERATIONS.md) | Local run, containers, health. |
| Alpha acceptance | [`docs/ALPHA-ACCEPTANCE.md`](ALPHA-ACCEPTANCE.md) | Owner runbook for declaring private technical alpha; evidence recorded outside the repo. |
| Product target | [`docs/TRUE-NORTH.md`](TRUE-NORTH.md) | What "finished enough to live in" means — the recut alpha gates. Target-experience detail where it is silent: [`docs/PERSONAL-WORLD-FINISH-LINE.md`](PERSONAL-WORLD-FINISH-LINE.md). |
| Completion plan (historical) | [`docs/history/PERSONAL-WORLD-COMPLETION-PLAN.md`](history/PERSONAL-WORLD-COMPLETION-PLAN.md) | Dated (v1, 2026-09-10) execution plan: phases and acceptance toward the finish line. A past record, not current state. |
| Decisions | [`.project/DECISIONS.md`](../.project/DECISIONS.md) + [`docs/adr/`](adr/) | Durable decisions and ADRs. |
| Repo inventory (historical) | [`docs/repo/REPOSITORY-INVENTORY.md`](repo/REPOSITORY-INVENTORY.md) | Dated (SHA `60823ae`, pre-2026-09-22 flip): what every major artifact is, and its status. |
| Wiring readiness (historical) | [`docs/repo/WIRING-READINESS.md`](repo/WIRING-READINESS.md) | Dated (SHA `60823ae`): GREEN/YELLOW/RED/GRAY per subsystem. Current state: [`.project/CURRENT.md`](../.project/CURRENT.md). |
| Historical receipts | [`docs/history/`](history/README.md) | Archived one-off merge receipts and handoffs (2026-09-13). |

## The full map

[`docs/INDEX.md`](INDEX.md) is the exhaustive document index with the
status vocabulary (Canonical / Normative / Spec / Archived).

## Repository layers

| Layer | Location | Holds |
|---|---|---|
| Product docs | `docs/` | Architecture, contracts, accessibility, product, surfaces, operations, history. |
| Durable project context | `.project/` | Current-state pointer, decisions, design authority, Play-Nice participants. |
| Contracts (shared library) | `.project/contracts/` | The one Play-Nice adoption manifest (`.project/contracts/adoption.yaml`); `.contracts/` holds only ignored session artifacts, never a second manifest. |
| Runtime | `src/personal_world/` | FastAPI app, CLI, providers, domain modules. |
| Browser gate | `ui/e2e/`, `ui/playwright.config.ts` | Playwright + axe specs against the real hub UI (`npm run preview`) and the seeded fixture API (`ui/scripts/e2e-api.mjs`). Run: `cd ui && npx playwright test`. |
| Interface (product) | `ui/` | React rebuild — the interface since the 2026-09-22 flip. Built into the image and served same-origin at `/` by the backend (`src/personal_world/station_ui.py::app_router`, named from the retired era). The server-rendered "Station" is retired, kept only as a theme package. |
| Design art | `design/` | Tokens, frames, companions, icons. `design/handoff/` is archived (do not edit). |

## Working rules

- [`AGENTS.md`](../AGENTS.md) — worktrees, staging discipline, no `git add -A`.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — how to propose changes.
- Validation: `uv run --extra test --extra crypto pytest --timeout=60 -o addopts="" -q` and
  `uv run personal-world framework validate --json`.