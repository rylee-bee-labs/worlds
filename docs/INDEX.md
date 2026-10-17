# Worlds: documentation index

> **Status:** Current · **Verified:** 2026-10-13 · **Canonical for:** where every doc is and what state it's in · **Read this if:** you're looking for a document, or checking whether one is still true.

**In short:** the map of every doc. Start with the pages under "Start
here". Every page carries a status line (Current, Reference, Direction or
Historical) — **that line is the authority on a page's state**, and
[`vnext/docs-truth.md`](vnext/docs-truth.md) is the authority on which file
owns which command or claim (routes, build, install, tests, backup). The
tables at the end of this page are a convenience index over those status
lines: they can lag a day or two, so if they disagree with a page's own
status line, the status line wins.

(The product was called "Personal World", then "Project Worlds"; it is
**Worlds** since 2026-09-12. Technical identifiers such as `personal_world`
are unchanged.)

## Start here

| Doc | What it is |
|---|---|
| [library/](library/README.md) | **Plain words, for anyone:** short books on how Worlds works and why: rooms, live updates, how the screens are layered, honesty, secrets, roles, notifications, shipping, and lessons learned the hard way. |
| [WHERE-WE-ARE.md](WHERE-WE-ARE.md) | **Plain words:** what Worlds is and where things stand today. Read this if you don't remember. |
| [`.project/CURRENT.md`](../.project/CURRENT.md) | **For agents:** the canonical current-state entry point; routes to the canonical files. |
| [vnext/docs-truth.md](vnext/docs-truth.md) | **The canonical pointer table:** which file owns each command or claim (routes, build, install, tests, backup) and which pages are superseded. Read it before hand-copying a list into a page. |
| [BACKLOG.md](BACKLOG.md) | Current work carried after #262/#263 closed, newest entries first. |
| [ROOMS.md](ROOMS.md) | How Worlds finds, checks and shows rooms (Workshop, Studio, Engine room, Candy), and how to add one. |
| [gallery/README.md](gallery/README.md) | Screenshots of every screen at 390 and 1440, from mock data. |
| [docs/README.md](README.md) | Where truth lives: canonical source per subject, and the repo's layers. |
| [README](../README.md) | The front door: what this is, quick start, navigation. |
| [CHANGELOG](../CHANGELOG.md) | Curated project milestones, newest first. |
| [`.project/PLAN.md`](../.project/PLAN.md) | **Current direction** (owner-approved 2026-09-25): "things come to me". Its landmarks are ADR-0008's (`Home · Connect · Memory · Settings`); the Bridge/Keeper naming is superseded. Wins over TRUE-NORTH on scope and sequencing. |
| [TRUE-NORTH](TRUE-NORTH.md) | Direction (owner-approved 2026-09-22): vision, five commitments, honesty and accessibility principles, which still hold. |
| [ROADMAP](../ROADMAP.md) | Historical horizon record — superseded as direction by TRUE-NORTH (2026-09-22). |
| [history/ROADMAP-AND-TODO.md](history/ROADMAP-AND-TODO.md) | Owner-facing alpha-status snapshot, dated; links to the canonical roadmap. |
| [PERSONAL-WORLD-FINISH-LINE.md](PERSONAL-WORLD-FINISH-LINE.md) | Target-experience detail where TRUE-NORTH is silent — superseded as direction (2026-09-22). |
| [history/PERSONAL-WORLD-COMPLETION-PLAN.md](history/PERSONAL-WORLD-COMPLETION-PLAN.md) | Dated execution plan (v1, 2026-09-10): approved decisions, dependency-ordered phases P0–P14, acceptance criteria, model routing. Phase status predates the T15 cutover / Workshop v3 — verify against code. |
| [p1/FOUNDATION-SPEC.md](p1/FOUNDATION-SPEC.md) | Historical (P1 complete) | Approved P1 implementation contract: sections API, primitive contracts, parity checklist, bounded tasks. Preserved for provenance. |
| [AGENT_POLICY.md](../AGENT_POLICY.md) | Mandatory agent preflight and decision policy. |
| [AGENT_CONTRACTS.md](../AGENT_CONTRACTS.md) | Canonical contract registry: applicability, authority, and exact entry points. |
| [STATUS.md](../STATUS.md) | Retired current-state entry point; now a pointer to [`.project/CURRENT.md`](../.project/CURRENT.md). |
| [Contributing](../CONTRIBUTING.md) | How to propose changes (humans and agents). |
| [Security](../SECURITY.md) | Reporting boundaries and the public-repo safety contract. |

## Architecture

| Doc | Status | What it is |
|---|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Canonical current | World model, current APIs/layout, identity and Vault limits, daily loop, target auth distinction. |
| [IDENTITY-BOUNDARY.md](IDENTITY-BOUNDARY.md) | Canonical current | Per-user vs instance-global state boundary (decision #13), legacy path mapping, and the sync-friendliness rule (decision #15). |
| [NATIVE-BASELINE-AND-ENRICHMENT.md](NATIVE-BASELINE-AND-ENRICHMENT.md) | Normative | The core invariant: capabilities core-owned, providers optional. Enforced by `framework validate`. |
| [adr/0001](adr/0001-capabilities-core-owned-providers-optional.md) | Accepted | Why the capability-ownership rule became test-enforced. |
| [adr/0002](adr/0002-default-brain-selection.md) | Accepted | Default brain selection (Qwen3 1.7B with an LFM2.5 fallback). |
| [adr/0008](adr/0008-front-door.md) | Accepted (canonical current) | **The front door.** Landmarks `Home · Connect · Memory · Settings`, Memory as durable state, one authority path for consequential actions. Merged to `main` in PR #277 (2026-10-06). Wins over every older navigation/product-shape document. |
| [rebuild/CONTRACTS.md](rebuild/CONTRACTS.md) | Accepted 2026-10-01 | The five contracts the front-door lanes build against. |
| [rebuild/DURABILITY.md](rebuild/DURABILITY.md) | Accepted 2026-10-01 | Durability classes, Memory export/backup/restore, the interrupted-action edge. Owns backup and restore; the measured drill is [`scripts/restore-drill.sh`](../scripts/restore-drill.sh). |
| [rebuild/FRAMEWORK-GATE.md](rebuild/FRAMEWORK-GATE.md) | Reference | `personal-world framework validate` — the framework gate's JSON envelope and exit codes. |
| [PROVIDERS.md](PROVIDERS.md) | Canonical | How to add a provider, step by step. |
| [OPERATIONS.md](OPERATIONS.md) | Canonical | Running it locally: CLI, web API, containers, health. |
| [ALPHA-ACCEPTANCE.md](ALPHA-ACCEPTANCE.md) | Runbook | Owner checklist for declaring private technical alpha; evidence stays outside the repo. |
| [history/OPERATIONS-FIRST-RUN.md](history/OPERATIONS-FIRST-RUN.md) | Operational reference | First-run procedure and dated bring-up evidence; reverify in the actual deployment. |
| [HUMAN_RELIABILITY_CONTRACT.md](HUMAN_RELIABILITY_CONTRACT.md) | Canonical | How the system stays safe and operable without demanding maximum operator attention. |
| [history/DESIGN-HANDOFF.md](history/DESIGN-HANDOFF.md) | V0.1 design baseline | Dated design-stage reference, not a current feature inventory; see README/Architecture for implemented scope. |

## Design

| Doc | Status | What it is |
|---|---|---|
| [Workshop v3 design authority](../.project/design/CURRENT.md) | Canonical current | The current implementation design authority: 16 canonical frames in `.project/design/WORKSHOP-V3-MANIFEST.yaml` (file `Wbg1rdt9fVCjWAXEKI1pTc`), the "The world knows how loudly to exist" principle, approvals, and reservations. Implementation workflow: [personal-world-implement-figma](../.agents/skills/personal-world-implement-figma/SKILL.md). |
| [tokens.json](../design/tokens.json) | Canonical | The repo-owned token file implementations consume. |
| [COMPANION_INTEGRATION.md](../design/COMPANION_INTEGRATION.md) | Canonical design + baseline/target notes | Five residents and identity design; current standalone Chat versus target contextual/global chat. |
| [CREW-AND-STATION-THESIS.md](CREW-AND-STATION-THESIS.md) | Canonical thesis (role amended 2026-09-22) | Crew/voice/companion family rules remain canonical; the *Station-as-primary-experience* role is superseded — Station is a kept theme package behind the stable skeleton. |
| [COMPANION-CANON.md](COMPANION-CANON.md) | Canonical naming | Companion display names (Renai, Ratatoskr, Bolt, Burrito Journalism, Personal World, Hekek, Bruma, Mira), the station-id ↔ server-key mapping, per-surface naming rules, and the OPEN/UNKNOWN items. Settings is an icon, not a resident. |
| [history/STATION-MAP.md](history/STATION-MAP.md) | Station-era deck plan (historical) | The retired Station's logical deck plan: eight decks, each named for its job, with its resident. The current navigation is ADR-0008's front door (`Home · Connect · Memory · Settings`); the earlier `Overview · Memory · Chat · Settings` skeleton in `docs/PRODUCT-LANGUAGE.md` is itself superseded. Station survives only as a theme package. |
| [Station design concepts](../design/concepts/README.md) | Archived 2026-09-25 | The Station concept pages (index, eight layout packets, dialect sheet, Today) now live at tag `archive/pre-design-cleanup-2026-09-25`. Their art stays in `design/concepts/assets/`. |
| [ART-REQUESTS.md](ART-REQUESTS.md) | Canonical request sheet | What to ask for when commissioning companion/crew art (style clause, per-character clauses, formats), and the current "still missing" gap list. |
| [CHARACTER-HANDBOOK.md](CHARACTER-HANDBOOK.md) | Canonical character + voice | The crew's *who*: each resident's emotional identity and voice, what they should never be, the two-voices rule, the attention voices, and Personal-vs-Contextual. Distinct from names/ids (COMPANION-CANON) and art (COMPANION_INTEGRATION). |
| [THEME_PACK_FRAMEWORK.md](../design/THEME_PACK_FRAMEWORK.md) | Spec; partial implementation | Pack invariants; manifest registry exists, full frontend pack integration remains incomplete. |
| [RYLEE_THEME_PACK.md](../design/RYLEE_THEME_PACK.md) | Spec | The personal Mermaid theme pack. |
| [LOTTIEFILES_HANDOFF.md](../design/LOTTIEFILES_HANDOFF.md) | Canonical | Production lessons for Lottie Creator workflows. |
| [Asset index](../design/assets/README.md) | Canonical | Where the design masters live (moved to the shared media library); only the icon sprite and manifest stay in this repo. |
| Companion collection (in the media library, `designs/personal-world/companions/README.md`) | Canonical | Source rigs and per-companion animation handoffs. |
| [Screen library](../design/screens/) | Canonical | Today/Journal/Settings/Chat screens, both themes, narrow + desktop. |
| [Exports (0.1)](../design/exports/0.1/) | Canonical visual source | The Figma export set the palette reconciliation targeted. |
| [handoff/](../design/handoff/README.md) | Archived | The original 0.1 spec package, preserved verbatim. Canonical accessibility docs now live under [docs/accessibility/](accessibility/ACCESSIBILITY_CONTRACT.md). |
| [history/FIGMA-HANDOFF-LESSONS.md](history/FIGMA-HANDOFF-LESSONS.md) | Canonical lessons | Composition drift is not caught by token gates; browser-side visual comparison is required before composition work merges. |
| [history/STATION-ALIVE-RESEARCH.md](history/STATION-ALIVE-RESEARCH.md) | Research (not a commitment) | Direction for making the Station feel alive: licence reality check, semantic state vocabulary, companion contract, spatial/ambient rules, prototypes, anti-patterns. |

## Accessibility

| Doc | Status | What it is |
|---|---|---|
| [ACCESSIBILITY_CONTRACT.md](accessibility/ACCESSIBILITY_CONTRACT.md) | Canonical (all 9 sections) | The non-negotiable accessibility contract. |
| [SCREEN_READER_WALKTHROUGH.md](accessibility/SCREEN_READER_WALKTHROUGH.md) | Canonical current + requirements | Source labels/order, current gaps, target overlay semantics; not a manual speech transcript. |
| [RESPONSIVE_RULES.md](accessibility/RESPONSIVE_RULES.md) | Canonical current + requirements | Actual rail/banner/phone CSS cascade, accessibility requirements, target overlays. |
| [PREFERENCES_SCHEMA.json](accessibility/PREFERENCES_SCHEMA.json) | Canonical | The preference schema with its accessibility floor. |

## Development

| Doc | What it is |
|---|---|
| [AGENTS.md](../AGENTS.md) | Working-tree rules for agents and humans (worktrees, staging discipline). |
| [vnext/docs-truth.md](vnext/docs-truth.md) | Which file owns each command or claim, and which pages are superseded — read before adding a list to a page. |
| [../scripts/route-inventory.json](../scripts/route-inventory.json) | The **generated** route contract (every `/api` route plus `/healthz`, with its auth level). Regenerate with `uv run python scripts/contract-drift-check.py --write`; check with the same script without `--write`. |
| [../scripts/gen-openapi.py](../scripts/gen-openapi.py) | The **generator** for `ui/src/generated/openapi.json` (written from the live front-door app). Never hand-edit the generated files. |
| [safe-commit.sh](../scripts/safe-commit.sh) | Stages named paths only; refuses unrelated-file sweeps. |
| [Validation commands](../AGENTS.md#checks) | `pytest`, `framework validate` — the canonical checks. |
| [DEV-ENVIRONMENT.md](DEV-ENVIRONMENT.md) | Setting up to run, test, or contribute: prerequisites, verification commands, and environment hygiene. |

## Surfaces, inventories & history

| Doc | Status | What it is |
|---|---|---|
| [repo/REPOSITORY-INVENTORY.md](repo/REPOSITORY-INVENTORY.md) | Canonical inventory | Every major artifact, its purpose, status, and canonical location. |
| [repo/WIRING-READINESS.md](repo/WIRING-READINESS.md) | Canonical assessment | GREEN/YELLOW/RED/GRAY per subsystem for the wiring pass. |
| [surfaces/MASTER-SURFACE-REGISTRY.md](surfaces/MASTER-SURFACE-REGISTRY.md) | Current reference | Extraction index of every UI/API/CLI/tool/provider/storage surface. |
| [surfaces/AUTH-MATRIX.md](surfaces/AUTH-MATRIX.md) | Current reference | Auth per surface (D1/D2/D3 convergence). |
| [surfaces/PROVIDER-MATRIX.md](surfaces/PROVIDER-MATRIX.md) | Current reference | Capability ↔ provider registration map. |
| [surfaces/STORAGE-MATRIX.md](surfaces/STORAGE-MATRIX.md) | Current reference | Storage paths, readers/writers, backup coverage. |
| [surfaces/UI-API-MATRIX.md](surfaces/UI-API-MATRIX.md) | Current reference | UI ↔ API wiring. |
| [surfaces/CLI-DOMAIN-MATRIX.md](surfaces/CLI-DOMAIN-MATRIX.md) | Current reference | CLI ↔ domain/API parity. |
| [surfaces/TOOL-DOMAIN-MATRIX.md](surfaces/TOOL-DOMAIN-MATRIX.md) | Current reference | Chat tool ↔ domain targets. |
| [surfaces/DUPLICATES.md](surfaces/DUPLICATES.md) | Current reference | Competing/duplicate systems (auth entries resolved by D1–D3). |
| [surfaces/ORPHANS.md](surfaces/ORPHANS.md) | Current reference | Orphaned/partial/superseded surfaces. |
| [surfaces/CALL-CHAINS.md](surfaces/CALL-CHAINS.md) | Current reference | Compact call chains per major flow. |
| [surfaces/COHERENCE-DECISION-PREP.md](surfaces/COHERENCE-DECISION-PREP.md) | Historical | Pre-wiring decision preparation; inputs absorbed into `repo/WIRING-READINESS.md`. |
| [history/](history/README.md) | Archived | 2026-09-13 merge receipts and handoffs. Superseded; kept for provenance. |
| [INDEX.md](INDEX.md) | This documentation index. |

## Status vocabulary used above

- **Canonical** — authoritative within its stated scope. Current descriptions,
  mandatory contracts, and target product requirements are distinct; an authoritative
  target does not prove implementation. Contradictions within scope are bugs.
- **Normative** — enforced by `personal-world framework validate` or tests.
- **Spec** — agreed direction; implementation may not exist yet.
- **Archived** — historical reference, preserved verbatim, do not edit.

## Every page, by status

Last swept from each page's status line on 2026-10-13. This table is a
convenience index, not a second source of truth: the **status line on the
page itself** decides that page's state. If a page is missing here, it has
no status line (or was added since the sweep): add one.

### Current (15)

| Page | Read this if |
|---|---|
| [../FRONTEND-INVENTORY.md](../FRONTEND-INVENTORY.md) | you are about to work on the UI and want the map before the code |
| [../README.md](../README.md) | you are new here, human or agent |
| [ARCHITECTURE.md](ARCHITECTURE.md) | you need to know where something lives before changing it |
| [INDEX.md](INDEX.md) | you're looking for a document, or checking whether one is still true |
| [QUICKSTART.md](QUICKSTART.md) | you want to run Worlds on your own machine, or you need the plain-language on-ramp |
| [library/README.md](library/README.md) | you want to understand how Worlds works and why, without reading code |
| [ROOMS.md](ROOMS.md) | you want to add a room, understand a room's status, or change how Worlds talks to rooms |
| [WHERE-WE-ARE.md](WHERE-WE-ARE.md) | you don't remember where things stand. That's okay |
| [accessibility/SCREEN_READER_WALKTHROUGH.md](accessibility/SCREEN_READER_WALKTHROUGH.md) | you use a screen reader, or you are changing labels, landmarks or focus in `ui/` |
| [accessibility/VOICEOVER_PASS.md](accessibility/VOICEOVER_PASS.md) | you are about to check Worlds with VoiceOver by hand, or you changed labels, focus or live regions |
| [gallery/README.md](gallery/README.md) | you want to see Worlds without running it, or you are refreshing the pictures after a UI change |
| [BACKLOG.md](BACKLOG.md) | you want the current work carried after #262/#263 closed |
| [rebuild/DURABILITY.md](rebuild/DURABILITY.md) | you deploy, back up or restore Worlds |
| [vnext/docs-truth.md](vnext/docs-truth.md) | a doc told you something the code no longer does, or you are about to hand-copy a command or route list |
| [adr/0008-front-door.md](adr/0008-front-door.md) | you need the accepted architecture behind today's product: landmarks, Memory, the authority path |

### Reference (48)

| Page | Read this if |
|---|---|
| [../AGENTS.md](../AGENTS.md) | you are about to edit, stage, or commit in this repo |
| [../AGENT_CONTRACTS.md](../AGENT_CONTRACTS.md) | you are an agent or human starting substantial work in this repo |
| [../AGENT_POLICY.md](../AGENT_POLICY.md) | you are an AI agent deciding what to do here, or how to say whether it worked |
| [../CHANGELOG.md](../CHANGELOG.md) | you want to know when something landed and why |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | you want to contribute a fix or a reviewable PR |
| [../SECURITY.md](../SECURITY.md) | you found a vulnerability, or you are about to add config, a hostname, or a credential to this public repo |
| [ALPHA-ACCEPTANCE.md](ALPHA-ACCEPTANCE.md) | you are deciding whether a deployment is ready for private technical alpha |
| [ART-REQUESTS.md](ART-REQUESTS.md) | you are commissioning or generating new art |
| [AUTHELIA-CLIENT-SNIPPET.md](AUTHELIA-CLIENT-SNIPPET.md) | you are wiring Authelia as Worlds' identity provider |
| [CHARACTER-HANDBOOK.md](CHARACTER-HANDBOOK.md) | you are writing copy, a persona, or a screen that speaks as a resident |
| [CI-ENVIRONMENT-NOTES.md](CI-ENVIRONMENT-NOTES.md) | your local suite passes but CI fails (or the reverse), or you are setting up a new machine |
| [CLI-REFERENCE.md](CLI-REFERENCE.md) | you want to call the API from a script or bot without thinking about routes |
| [COMPANION-CANON.md](COMPANION-CANON.md) | you are naming a companion in copy, or mapping a legacy key to a crew id |
| [DEGRADED-MODES.md](DEGRADED-MODES.md) | you are changing a fail-closed path or a degraded label and need the contract it must keep |
| [DEV-ENVIRONMENT.md](DEV-ENVIRONMENT.md) | you are about to run, test, or contribute to Worlds |
| [DEV-RESET.md](DEV-RESET.md) | you need to return a development instance to a clean first-run state |
| [HUMAN_RELIABILITY_CONTRACT.md](HUMAN_RELIABILITY_CONTRACT.md) | you are designing or reviewing any human-facing surface, agent behavior, or operational workflow |
| [IDENTITY-BOUNDARY.md](IDENTITY-BOUNDARY.md) | you are adding per-person state or working on multi-user mode |
| [INGRESS-AND-TLS.md](INGRESS-AND-TLS.md) | you are putting Worlds behind Traefik, nginx, or Caddy and need cookies and OIDC redirects to work |
| [NATIVE-BASELINE-AND-ENRICHMENT.md](NATIVE-BASELINE-AND-ENRICHMENT.md) | you are adding a capability or provider, or checking what may become a hidden dependency |
| [NOTIFICATIONS.md](NOTIFICATIONS.md) | you want notifications on your phone, or you run a World and need to switch the whole thing on |
| [OPERATIONS.md](OPERATIONS.md) | you are operating an instance — local CLI, containers, production deploy, backups, or chat providers |
| [PORTING.md](PORTING.md) | you want to move, extend, or contribute to Worlds without breaking its non-negotiables |
| [PRODUCT-LANGUAGE.md](PRODUCT-LANGUAGE.md) | you are writing user-facing copy or deciding where a feature surfaces |
| [PROVIDERS.md](PROVIDERS.md) | you are adding or replacing one real system behind a capability |
| [README.md](README.md) | you need to find the one file that owns a subject before reading or editing it |
| [RECORDS-API.md](RECORDS-API.md) | you are reading or changing the Records surface, its storage, or its gating |
| [RECOVERY-BOUNDARY.md](RECOVERY-BOUNDARY.md) | you are restoring Worlds, or writing recovery/backup docs |
| [WORLDS-BACKUP.md](WORLDS-BACKUP.md) | you need to save or move a whole Worlds instance |
| [accessibility/ACCESSIBILITY_CONTRACT.md](accessibility/ACCESSIBILITY_CONTRACT.md) | you are designing, building or reviewing anything a person perceives or operates |
| [accessibility/RESPONSIVE_RULES.md](accessibility/RESPONSIVE_RULES.md) | you are changing layout, navigation or a screen's narrow-width behaviour |
| [accessibility/FRONT-DOOR-SCREEN-READER-WALKTHROUGH.md](accessibility/FRONT-DOOR-SCREEN-READER-WALKTHROUGH.md) | you are about to sign off the front door as accessible; the manual pass it scripts has not been run yet |
| [rebuild/FRAMEWORK-GATE.md](rebuild/FRAMEWORK-GATE.md) | you are changing the framework gate, or wondering why an old ADR-0001 rule is gone |
| [adr/0001-capabilities-core-owned-providers-optional.md](adr/0001-capabilities-core-owned-providers-optional.md) | you are adding or changing a capability, a provider, or anything that could make a vendor's shape into product truth |
| [adr/0002-default-brain-selection.md](adr/0002-default-brain-selection.md) | you are changing the default brain, the fallback, or the `reasoning` provider |
| [brain-templates.md](brain-templates.md) | you are editing chat prompt text or adding a persona/surface/task template |
| [history/README.md](history/README.md) | you are looking for a dated receipt or need to know what not to trust |
| [oidc-live-test.md](oidc-live-test.md) | you need to prove the OIDC code against a real provider, not the in-process stub |
| [oidc.md](oidc.md) | you want to sign in through your own identity provider (Authelia, Keycloak, Authentik, …) |
| [surfaces/AUTH-MATRIX.md](surfaces/AUTH-MATRIX.md) | you need to know which credential or elevation a surface requires |
| [surfaces/CALL-CHAINS.md](surfaces/CALL-CHAINS.md) | you want to trace how a feature travels from surface to store |
| [surfaces/CLI-DOMAIN-MATRIX.md](surfaces/CLI-DOMAIN-MATRIX.md) | you need to know whether a CLI command has an API twin |
| [surfaces/DUPLICATES.md](surfaces/DUPLICATES.md) | two code paths look like they do the same job and you want to know which is live |
| [surfaces/ORPHANS.md](surfaces/ORPHANS.md) | you found code with no caller and want to know whether it is dead, deliberate, or already resolved |
| [surfaces/PROVIDER-MATRIX.md](surfaces/PROVIDER-MATRIX.md) | you need to know how a capability gets its provider, and whether it is live |
| [surfaces/STORAGE-MATRIX.md](surfaces/STORAGE-MATRIX.md) | you need to know where a piece of state lives and whether the backup covers it |
| [surfaces/TOOL-DOMAIN-MATRIX.md](surfaces/TOOL-DOMAIN-MATRIX.md) | you need to know what a model can inspect or propose |
| [surfaces/UI-API-MATRIX.md](surfaces/UI-API-MATRIX.md) | you need to know what a screen calls, and what gate that call passes |

### Direction (9)

| Page | Read this if |
|---|---|
| [CREW-AND-STATION-THESIS.md](CREW-AND-STATION-THESIS.md) | you are touching companion art, voice, or the crew's place in the product |
| [PERSONAL-WORLD-FINISH-LINE.md](PERSONAL-WORLD-FINISH-LINE.md) | you are planning toward "finished enough to live in every day" and need the experience-level target |
| [TRUE-NORTH.md](TRUE-NORTH.md) | you need *why* Worlds is shaped this way; for *what we are building now* read `.project/PLAN.md` first |
| [adr/0009-play-nice-semantic-kernel.md](adr/0009-play-nice-semantic-kernel.md) | you are proposing the Play-Nice semantic-kernel experiment; it is **proposed**, not built |
| [adr/0003-workbench-core-owned-capability.md](adr/0003-workbench-core-owned-capability.md) | you are touching workbench/terminal/exec/preview work |
| [adr/0004-node-agent-capability-model.md](adr/0004-node-agent-capability-model.md) | you are working on Nodes, remote machines, or the Worlds Agent |
| [adr/0005-network-overlay-netbird.md](adr/0005-network-overlay-netbird.md) | you are touching mesh networking for Nodes |
| [adr/0006-event-task-envelope.md](adr/0006-event-task-envelope.md) | you are designing how Workbench tasks and Agent operations record events |
| [adr/0007-vault-openbao-scoped-credentials.md](adr/0007-vault-openbao-scoped-credentials.md) | you are touching Vault, SOPS/OpenBao, or how tasks receive credentials |

### Historical (30)

| Page | Read this if |
|---|---|
| [../ROADMAP.md](../ROADMAP.md) | you want the dated horizon record, not current direction (superseded by `.project/PLAN.md` (current direction) and `docs/TRUE-NORTH.md` (principles; its scope is itself superseded by PLAN)) |
| [../STATUS.md](../STATUS.md) | you followed an old link and want the current-state pointer (superseded by `.project/CURRENT.md`) |
| [history/DESIGN-HANDOFF.md](history/DESIGN-HANDOFF.md) | you need the V0.1 design baseline and the accessibility/architectural intent behind today's product (superseded by `.project/CURRENT.md`) |
| [history/EXTERNAL-AGENT-HANDOFF.md](history/EXTERNAL-AGENT-HANDOFF.md) | you need the 2026-09-16 parallel-lane working plan and its file-ownership rules (superseded by `.project/CURRENT.md`.) |
| [history/FIGMA-HANDOFF-LESSONS.md](history/FIGMA-HANDOFF-LESSONS.md) | you are writing a design/implementation handoff and want the 2026-09-11 postmortem on composition drift (superseded by `.project/design/CURRENT.md`.) |
| [history/OPERATIONS-FIRST-RUN.md](history/OPERATIONS-FIRST-RUN.md) | you want the dated 2026-09-09 bring-up record (superseded by Operations.) |
| [history/PARITY-CORE-64.md](history/PARITY-CORE-64.md) | you need the 2026-09-20/21 route-adjudication record for provenance (superseded by the running code and `.project/CURRENT.md`.) |
| [history/PARITY-DIVERGENCE-2026-09-20.md](history/PARITY-DIVERGENCE-2026-09-20.md) | you need the regenerable 2026-09-21 parity checklist for provenance (superseded by the running `ui/` interface and `.project/CURRENT.md`.) |
| [history/PERSONAL-WORLD-COMPLETION-PLAN.md](history/PERSONAL-WORLD-COMPLETION-PLAN.md) | you want the dated v1 execution plan for provenance (superseded by `.project/PLAN.md` for direction and `.project/CURRENT.md` for state.) |
| [history/PRODUCT-VISION-HANDOFF.md](history/PRODUCT-VISION-HANDOFF.md) | you want the dated 2026-09-16 vision write-up and its decision list for provenance (superseded by `.project/PLAN.md` for direction and `.project/CURRENT.md` for state.) |
| [history/PROJECT-WORLDS-MASTER-HANDOFF.md](history/PROJECT-WORLDS-MASTER-HANDOFF.md) | you want the dated 2026-09-16 "everything in one file" handoff for provenance (superseded by `.project/PLAN.md` for direction and `.project/CURRENT.md` for state.) |
| [history/ROADMAP-AND-TODO.md](history/ROADMAP-AND-TODO.md) | you want the dated 2026-09-17 alpha snapshot, not current truth (superseded by `.project/PLAN.md` for direction and `.project/CURRENT.md` for state.) |
| [history/STATION-ALIVE-RESEARCH.md](history/STATION-ALIVE-RESEARCH.md) | you need the dated 2026-09-17 research on companion/ambient behaviour (superseded by `.project/PLAN.md` for direction and `docs/PRODUCT-LANGUAGE.md` for the theme boundary.) |
| [history/STATION-GAP-ANALYSIS.md](history/STATION-GAP-ANALYSIS.md) | you need the dated 2026-09-17 source-level gap analysis for provenance (superseded by the running `ui/` interface and `.project/CURRENT.md`.) |
| [history/STATION-MAP.md](history/STATION-MAP.md) | you want the dated eight-deck design record behind today's crew and doorways (superseded by `.project/PLAN.md` (current product shape); crew/room canon lives in `docs/COMPANION-CANON.md` and `docs/CHARACTER-HANDBOOK.md`) |
| [adr/WORKBENCH-SPIKE-FINDINGS.md](adr/WORKBENCH-SPIKE-FINDINGS.md) | you want to see what a spike actually found when the Workbench ADRs met the code (superseded by `docs/adr/0003-workbench-core-owned-capability.md` and `docs/adr/0006-event-task-envelope.md`) |
| [history/2026-09-22-true-north-research-brief.md](history/2026-09-22-true-north-research-brief.md) | you want the 2026-09-22 research that fed the re-focus (superseded by `docs/TRUE-NORTH.md`.) |
| [history/API-WIRING-HANDOFF.md](history/API-WIRING-HANDOFF.md) | you need the 2026-09-13 endpoint-disposition handoff (68 endpoints, 19 read tools) (superseded by `.project/CURRENT.md`.) |
| [history/CONNECTIONS-RECEIPT.md](history/CONNECTIONS-RECEIPT.md) | you need the 2026-09-13 Connections/Providers audit's own counts and test-behavior table (superseded by `.project/CURRENT.md`.) |
| [history/CONSTRUCTION-AND-EPOCH-NARRATIVE.md](history/CONSTRUCTION-AND-EPOCH-NARRATIVE.md) | you want the dated 2026-09-12→14 feature-slice narrative (superseded by `.project/CURRENT.md`.) |
| [history/FINAL-RECEIPT.md](history/FINAL-RECEIPT.md) | you need the 2026-09-14 merge receipt's own counts and claims (superseded by `.project/CURRENT.md`.) |
| [history/FULL-SYSTEM-INVENTORY.md](history/FULL-SYSTEM-INVENTORY.md) | you need the 2026-09-13 inventory's endpoint/tool/provider tables (superseded by `.project/CURRENT.md`.) |
| [history/MERGE-DOCS-RECEIPT.md](history/MERGE-DOCS-RECEIPT.md) | you need the 2026-09-13 merge/docs-refresh receipt and its screenshots manifest (superseded by `.project/CURRENT.md`.) |
| [history/RECONCILIATION-RECEIPT.md](history/RECONCILIATION-RECEIPT.md) | you need the 2026-09-13 post-Connections issue-reconciliation record (superseded by `.project/CURRENT.md`.) |
| [history/WIRING-COMPLETION-HANDOFF.md](history/WIRING-COMPLETION-HANDOFF.md) | you need the pre-merge 2026-09-13 handoff and its 10 open questions (superseded by `.project/CURRENT.md`.) |
| [p1/FOUNDATION-SPEC.md](p1/FOUNDATION-SPEC.md) | you need the approved 2026-09-10 P1 frontend-foundation contract and its task list (superseded by `.project/CURRENT.md`.) |
| [repo/REPOSITORY-INVENTORY.md](repo/REPOSITORY-INVENTORY.md) | you need the dated SHA `60823ae` inventory of the repo for provenance (superseded by the running code and `.project/CURRENT.md`.) |
| [repo/WIRING-READINESS.md](repo/WIRING-READINESS.md) | you need the dated SHA `60823ae` GREEN/YELLOW/RED assessment for provenance (superseded by the running code and `.project/CURRENT.md`.) |
| [surfaces/COHERENCE-DECISION-PREP.md](surfaces/COHERENCE-DECISION-PREP.md) | you want the dated pre-wiring decision prep behind the D1–D12 calls (superseded by `../repo/WIRING-READINESS.md` and the code) |
| [surfaces/MASTER-SURFACE-REGISTRY.md](surfaces/MASTER-SURFACE-REGISTRY.md) | you need a stable ID (`UI-001`, `API-003`, `PROV-001`, …) and a dated extraction of what existed on 2026-09-14 (superseded by the code and `.project/CURRENT.md`; current backend maps live in the sibling `docs/surfaces/` matrices) |
