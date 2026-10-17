# Repository Inventory — Project Worlds

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see [`.project/CURRENT.md`](../../.project/CURRENT.md)) · **Read this if:** you need the dated SHA `60823ae` inventory of the repo for provenance · **Superseded by:** the running code and [`.project/CURRENT.md`](../../.project/CURRENT.md).

**In short:** a read-only extraction of what every major artifact is and
its status, taken at SHA `60823ae` (the D1–D3 auth/authority checkpoint)
before the 2026-09-22 interface flip. Counts and per-file line references
here are a dated snapshot at that SHA; where a claim here and the code
disagree, the code wins. In particular, the React SPA (`frontend/`)
described below was removed in the Station-only cutover: `frontend/` is
now only the Playwright browser gate, the interface is the React rebuild
in `ui/`, and rows mentioning `frontend/src/**`, `PW_FRONTEND*`, or
`docs/screenshots/*` describe the pre-cutover state.

**Provenance:** branch `docs/repo-inventory-reorg`; landed on `main` via
PR #50 (merge `1701476`). No runtime behavior was changed by this pass.

## Truth-state convention

Findings that depend on branch/lane context are labelled explicitly:

- **BASE** — true on the committed inventory base (`60823ae`).
- **KNOWN UNMERGED FIX** — another worktree/lane contains a fix that is
  not yet integrated into the base.
- **CURRENT** — true in the authoritative branch being evaluated.

An unmerged lane fix does **not** make a BASE defect GREEN. The base
remains broken until the fix is integrated.

Companion docs:

- [`WIRING-READINESS.md`](WIRING-READINESS.md) — GREEN/YELLOW/RED/GRAY
  per subsystem and default-provider candidates.
- [`../surfaces/MASTER-SURFACE-REGISTRY.md`](../surfaces/MASTER-SURFACE-REGISTRY.md)
  — every surface ID.
- [`../README.md`](../README.md) — canonical source per subject.

## 1. Top-level areas

| Area | Canonical location | Status | Notes |
|---|---|---|---|
| Runtime (core) | `src/personal_world/` | Current, active | 65 files, ~15.3k LOC. FastAPI app, CLI, domain modules. |
| Providers | `src/personal_world/providers/` | Current, mixed | 30 modules; many registered, many used by direct instantiation (see §6). |
| API | `src/personal_world/api.py`, `auth_routes.py` | Current, active | 109 + 7 route decorators. |
| CLI | `src/personal_world/cli.py` | Current, active | 18 subcommands. |
| Frontend | `frontend/` | Current, active | React+Vite+TS SPA; 13 routes; 198 tracked files. |
| Tests | `tests/`, `frontend/src/test/`, `frontend/e2e/` | Current, active | ~703 backend tests + Vitest + Playwright. |
| Design art | `design/` | Current+archived | `design/tokens.json` canonical; `design/handoff/` archived (never edit). |
| Config | `config/` | Current | `connections.json` tracked (secret-free); prompts; examples. |
| Deployment | `compose.yaml`, `compose.dev.yaml`, `compose.homelab.yaml`, `Dockerfile`, `.github/workflows/` | Current | `compose.homelab.yaml` has host-specific paths (non-portable). |
| Project context | `.project/` | Current+historical | Current-state pointer, decisions, design authority, participants. |
| Contracts | `.project/contracts/adoption.yaml` | Current | One adoption manifest (v0.6.0 @ `0cee065`); `.contracts/` holds only ignored session artifacts. |
| Operator docs | `docs/` | Current + history | See [`../README.md`](../README.md). |
| Scripts | `scripts/safe-commit.sh` | Current | Staging guard; tested. |
| Generated | `frontend/src/tokens.css`, `docs/screenshots/*.png` | Generated | `tokens.css` from `design/tokens.json`; screenshots by e2e spec. |
| Historical docs | `docs/history/` | Archived | 2026-09-13 merge receipts/handoffs. |
| Local-only (untracked) | `data/`, `node_modules/`, `test-results/`, `.bcode/`, `.mimocode/`, `data.bak.*/`, `.venv/` | Ignored | `.gitignore` updated this pass (see §12). |

## 2. Cruft and historical artifacts

| Item | Classification | Action taken |
|---|---|---|
| `docs/FINAL-RECEIPT.md` | Historical (2026-09-13) | Moved → `docs/history/` |
| `docs/FULL-SYSTEM-INVENTORY.md` | Historical, contradictory counts | Moved → `docs/history/` |
| `docs/CONNECTIONS-RECEIPT.md` | Historical | Moved → `docs/history/` |
| `docs/RECONCILIATION-RECEIPT.md` | Historical | Moved → `docs/history/` |
| `docs/MERGE-DOCS-RECEIPT.md` | Historical, orphan | Moved → `docs/history/` |
| `docs/WIRING-COMPLETION-HANDOFF.md` | Historical, superseded | Moved → `docs/history/` |
| `docs/API-WIRING-HANDOFF.md` | Historical, superseded | Moved → `docs/history/` |
| `docs/p1/FOUNDATION-SPEC.md` | Historical (P1 complete) | Kept in place; reclassified in `docs/INDEX.md` |
| `docs/surfaces/COHERENCE-DECISION-PREP.md` | Historical decision prep | Kept; classified historical in index |
| `.project/HANDOFF-FRESHNESS-EVIDENCE-2026-09-12.md` | Historical evidence | Flagged; left in place (durable-context layer convention) |
| `.project/attestations/*.json` | One-time attestations | Kept (provenance) |
| `frontend/src/screens/ChatScreen.tsx` | Dead (not routed; incompatible body) | Flagged (see §9) |
| `frontend/src/screens/TodayScreen.tsx::NotificationCard` | Unused export | Flagged |
| `src/personal_world/execution_viewer.py` | Dead (constructed + discarded) | Flagged |
| Root untracked: `node_modules/`, `test-results/`, `data.bak.1789330245/`, `.bcode/`, `.mimocode/`, `frontend/test-layout.js` | Local cruft | `.gitignore` extended |

No filename copy variants (`*-copy`, `*-final-final`, `(1)`) were found.

## 3. Orphan / dead / half-wired code

| ID | Area | Finding | Severity | Next action |
|---|---|---|---|---|
| ORPH-01 | Chat | `chat.py::build_chat_provider`, `chat.py::OllamaChat`, `chat.py::OpenAICompatChat` have no production caller (tests only); `app.py` imports the `chat_registry` copy. | Medium | Remove the orphan classes/builder; keep `chat_once`/`build_chat_messages`/`extract_proposal` helpers. |
| ORPH-02 | Chat | `chat_registry.py::ChatProviderRegistry` has no caller. | Low | Delete or wire. |
| ORPH-03 | Chat | Live `chat_registry.OllamaChat`/`OpenCodeChat` lack `chat_with_tools`; the orphan `chat.py` copy has it. Tool-calling is therefore unavailable for Ollama despite the method existing elsewhere. | High | Port `chat_with_tools` onto the live classes. |
| ORPH-04 | Secrets | `providers/adapters.py::SopsBroker` and `vault.py::SOPSVaultAdapter` have no caller; adapter writes unsupported. | Medium | Decide: wire as a selected backend or archive. |
| ORPH-05 | Execution | `ExecutionStore`/`ExecutionViewer` instantiated at `app.py:454-455` and discarded; no route/tool/caller. | Low | Delete or wire into a real surface. |
| ORPH-06 | Theme | `theme_pack.py::CompanionStates` state machine defined; runtime resolution limited to the default pack; `/api/themes` has no frontend consumer; `theme_pack.py:58-62` defaults use `/static/companions/*` with no matching route. | Medium | Wire packs into UI theming or defer explicitly. |
| ORPH-07 (corrected) | Tools | **Stale finding.** At base the reminder executor writes through `Scheduler` (`tool_registry.py:799-817`) and the reconciler executor honestly returns `unsupported`, leaving the proposal pending (`:819-830`). Neither fakes success. | — | None (chat proposal UI still backend-only). |
| ORPH-08 (corrected) | Tools | **FALSE at BASE (stale finding).** Proposals are durable (`data/proposals.json`, atomic write, `tool_registry.py:574-615`); approval is server-held (`approved_by`/`approved_at`/`approval_evidence`, `:846-885`); approve/reject/execute are step-up API routes (`api.py:951-1004`); `ToolRegistry.invoke` structurally blocks execution tools from the model (`:96-127`). Remaining: no frontend proposals UI; proposals instance-global. `TOOL-017 run_discovery` is still labelled read (valid). | Low | Add proposals UI; namespace per user; relabel TOOL-017. |
| ORPH-09 | Providers | `native_notifications.send()` has no caller; `native_updates.check()`, `native_calendar.upcoming()`, `native_deployment` actions unused. | Medium | Wire or mark observe-only intentionally. |
| ORPH-10 | Providers | `native_notifications` health is `len(adapters)>0`, so a zero-target boot reports `unavailable` rather than `not_configured`. | Low | Fix health semantics. |
| ORPH-11 | Providers | `NativeVaultProvider.observe` always reports `healthy`, even when the vault is locked; `NativeLabHealth._check_health` returns a static stub; `native_discovery._discover_api` returns `[]`. | Medium | Make observation honest. |
| ORPH-12 | API | `POST /api/connections/validate` is a behavioral alias of `/test`. | Low | Collapse or document as alias. |
| ORPH-13 | API | `GET /api/reconciler/diff|propose` read a JSON body on GET. | Low | Move to POST or query params. |
| ORPH-14 | CLI | `framework validate` reads raw `connections.json` + private `registry._contracts`, ignoring `connections.local.json` merge. | Medium | Delegate to `ConnectionManager`/`build_registry`. |
| ORPH-15 | CLI | `main()` builds the registry without `vault`/`journal`/`data_dir`; CLI registry ≠ API registry (no `native-vault`; memory uses `./data`). | Medium | Unify registry construction. |
| ORPH-16 | CLI | `daily` without `--apply` still appends to the journal (`record=True` default), contradicting its dry-run contract and the read-only API GET. | High | Pass `record=False` unless `--apply`. |
| ORPH-17 | CLI | `journal` uses `Journal.recent` (includes superseded) vs API `current_events`; `prefs` writes global world, not principal-scoped. | Medium | Align CLI to canonical readers/scope. |
| ORPH-18 | Frontend | **BASE broken.** `TodayScreen.tsx:295` reads `entry.text`, but `/api/journal` returns `summary` (`api.ts:296-311` `JournalEntry` has no `text`) → render crash when any entry exists. **KNOWN UNMERGED FIX** in the `docs/current-product-refresh` worktree (`(entry.text || entry.summary || "")`), not integrated. | High | Integrate the lane fix (or apply the equivalent). |
| ORPH-19 | Frontend | **BASE broken; still broken in the frontend lane.** `ProjectsScreen.tsx:31,127` use `repo.ok`, but `SourceControlRepo` has `error`, not `ok` (`api.ts:437-449`) → always "Healthy" and wrong counts. | High | Use `error`/status fields. |
| ORPH-20 | Frontend | Base and lane: dead `ChatScreen.tsx` (unrouted), plus unused hooks/api helpers/primitives/components. | Low | Prune or wire. |
| ORPH-21 | Storage | `data/proposals.json` is instance-global; in-memory dict is source until configured. | Medium | Per-user namespacing later. |
| ORPH-22 | Auth | `GET /api/vault/{name}` accepts `ip.is_private` despite "loopback-only" text; vault unlock/lock/set/delete are bearer-only, not step-up. | High | Tighten to true loopback + step-up for secret ops. |

## 4. Duplicate sources of truth

| Subject | Canonical | Duplicate / legacy | Action |
|---|---|---|---|
| Play-Nice adoption manifest | `.project/contracts/adoption.yaml` (v0.6.0 @ `0cee065`; declared by `.project/project.yaml`) | ~~`.contracts/adoption.yaml` (@ `1c05de4`)~~ | **RESOLVED 2026-09-15.** The root duplicate was removed; `AGENT_CONTRACTS.md` now points at the declared manifest. See note below. |
| Design tokens | `design/tokens.json` | `design/handoff/DESIGN_TOKENS.json` (0.1 archive); `frontend/src/tokens.css` (generated) | No action (archive is historical; CSS is generated). |
| Capability vocabularies | `app.py::STANDARD_CAPABILITIES` (18) | `provider_schemas.py::CAPABILITY_SCHEMAS` (7); `api.py::_capability_description`; dead `framework.py::STANDARD_CAPABILITIES` (13) | Consolidate in wiring pass. |
| Chat providers | `chat_registry.py` | `chat.py` (orphan copy) | Remove orphan. |
| Updates | `updates.py::UpdateManager` (used by API+CLI) | `providers/native_updates.py` (registered, `check()` unused) | Pick one authority. |
| Media engine | `api.py::_build_media_engine` | `tool_registry.py::_build_media_engine` (env re-derivation) | Single builder through the Registry. |
| Identity stores | `users.json` (`identity.py`) | `users/<id>.json` (`user.py::UserManager`, unused in src) | Retire legacy path. |
| Reconciler desired dirs | `~/.config/personal-world/reconciler/desired/` | `~/.config/personal-world/lab/desired/` | Clarify or unify. |
| Current-state narratives | `.project/CURRENT.md` | `STATUS.md`, `.agent/STATE.md` (declared retired pointers) | No action (already pointers). |
| Accessibility doc baselines | current code | `SCREEN_READER_WALKTHROUGH.md`/`RESPONSIVE_RULES.md` cite deleted `_DASHBOARD_HTML` | Refresh stale baselines. |
| Receipt chain | — | 5 receipts with contradictory counts (663/719/725/726 tests; 19 vs 29 tools) | Archived to `docs/history/`. |
| Figma contract-return twins | `resolved-contracts.md` | `resolved-contracts.json`, `attestation.{md,json}` | Leave (machine twin is intentional). |

**Play-Nice manifest resolution (2026-09-15).** This item previously
read "split authority — needs human decision." It was resolved in favour
of `.project/contracts/adoption.yaml` because that is the layout the
Play-Nice project-context framework itself uses (the library's worked
example is `examples/project-context/.project/contracts/adoption.yaml`),
it is the path declared by `.project/project.yaml` (`contracts.manifest`)
and used by the documented session workflow in `.project/README.md`, and
it carries the verified *released* pin (`0cee065` = library VERSION
0.6.0). The root `.contracts/adoption.yaml` had been created later from
the minimal standalone quickstart and pinned `1c05de4`, ten post-release
docs/profile commits on the same 0.6.0 line; it was not referenced by
any code, test, CI, or script. The duplicate was deleted and every
document now points at the single manifest. No contract text is copied
into this repository.

## 5. Provider inventory

Legend: Reg = registered in `Registry`; Canon = used through
`Registry.provider_for`; Bypass = used by direct instantiation.

| Capability | Provider(s) | Reg | Canon | Default | Status |
|---|---|---|---|---|---|
| source_control | `NativeGit` (source_control.py:324) + `Gitea`/`FakeSourceControl` (adapters) | yes | observe only; reads bypass to module funcs | native (local `git`) | Partial: reads bypass registry |
| memory | `NativeMemoryProvider`; `LangGraphMemory` (alt) | yes | **yes** (`api.py:648/815/924`) | native (SQLite FTS5) | Active, healthy locally |
| reasoning | Ollama/OpenAICompat/OpenAI/Anthropic/OpenCode (`chat_registry`) | via connection | **yes** (`api.py:761/884/899`) | none | Active when configured; Ollama tool-calls broken (ORPH-03) |
| secrets | `NativeVaultProvider`; `Vault` object direct; SOPS orphans | yes (API only) | observe only | native `vault.enc` | Active; fails closed without `cryptography` (no base64 fallback; corrected 2026-09-15) |
| deployment | `NativeDeploymentProvider` | yes | observe only | native | Partial: no deploy caller |
| calendar | `NativeCalendarProvider` | yes | observe only | native | Active observe; `upcoming()` unused |
| notifications | `NativeNotificationsProvider` | yes | observe only | native | Partial: `send()` uncalled; health misreports |
| update_discovery | `NativeUpdatesProvider`; `updates.py::UpdateManager` | yes | observe only | native | Duplicate authority |
| scheduler | (none — core `Scheduler` direct) | no | no | core | Works, invisible to registry |
| journal | (core `Journal`, not a provider) | no | no | core | Active |
| discovery | `NativeDiscovery` (connection) | only via connection | **bypass** | none | Partial |
| settings_validation | `NativeLabSettings` (connection) / `LabSettings` / `NativeSettingsReconciler` | conditional | bypass | none | Partial |
| service_validation | (none) | no | no | none | Gap |
| homelab_* (settings/health/deploy/secrets/resources) | `Lab*` (connection) + `native_lab` | conditional | bypass | none | Active observe |
| service_inventory/health/resource_monitoring | `native_lab` | conditional | bypass | none | Active observe; health stub |
| ingress | `TraefikIngress` | conditional (env) | bypass | none | Partial; status "degraded" not in vocab |
| media | `NativeMediaEngine` + Plex/Sonarr/Radarr/Lidarr | **no** | **bypass** | none | Active via dedicated engine |
| auth | schema only (`provider_schemas`) | no | n/a | core | Implemented in `auth.py`/`auth_routes.py` |
| projects | `AgentSyncProjectSensor` | no | bypass | none | Active (external binary) |
| enrichment | `GitHubEnrichment` | no | bypass | none | Active (gh CLI) |

Bucket summary: **Defined-but-not-registered** — media, auth, reconciler,
GitHubEnrichment, AgentSyncProjectSensor, LabState, SOPS paths,
UpdateManager, ExecutionStore. **Registered-but-unused** —
native-calendar/notifications/updates/deployment/vault (observe only),
native-git (observe). **Multiple implementations** — reasoning, updates,
source_control, secrets, settings_validation, health. **Capability with
no default** — discovery, settings_validation, service_validation,
journal, reasoning, scheduler, homelab_*. **Default broken/stub** —
native_notifications (health), NativeVaultProvider (always healthy),
NativeLabHealth (static), native_discovery `_discover_api` (returns `[]`).

## 6. API wiring summary

116 route handlers total (109 in `api.py`, 7 in `auth_routes.py`).

| Class | Count | Examples |
|---|---|---|
| Fully wired (backend + frontend consumer + canonical service) | ~45 | status, daily GET, journal, prefs, sections, vault, world writes, reminders, apps, exports |
| Backend only (no frontend consumer) | ~20 | `/api/tools`, `/api/chat/test`, `/api/proposals*`, `/api/identity/users|agents`, `/api/themes/{name}`, `/api/lab/settings/diff|inspect`, `/api/reconciler/diff|propose`, `/api/auth/*` |
| Bypassing canonical service/Registry | ~35 | media (5), source-control (4), lab (8), native-lab (4), discovery (6), reconciler (3), updates (1), ingress (1), projects (1), enrichment (1), connections test/validate (2) |
| Partial | ~15 | vault secret ops (no step-up), daily POST (global world), `/api/connections/test` (inline probe stubs) |
| Duplicate/alias | 1 | `/api/connections/validate` ≈ `/test` |
| Stub | — | branches inside `_test_adapter` (webhook/systemd/compose) |
| Dead | 0 | none found |

Not in the original API-ID list: `/api/proposals*` (5) and
`/api/auth/*` (7). Stale vs code: `API-080` rollups route removed.

## 7. CLI wiring summary

18 subcommands, all ACTIVE; no dead/stub commands.

| Class | Commands |
|---|---|
| Fully wired (canonical domain) | status, daily, actors, settings/world/story-export, backup, cement, init, manifest, changes, history, sync-status, framework validate-packs, updates * |
| Bypasses canonical service | `framework validate` (raw `connections.json` + private `_contracts`), `main()` registry wiring (missing vault/journal/data_dir) |
| Divergent behavior | `daily` (dry-run still journals), `journal` (not supersede-aware), `prefs` (global, not principal-scoped) |
| CLI-only by design | `cement`, `init`, `framework validate*`, `updates apply/rollback` |

## 8. Frontend wiring summary

13 routes. No client-side auth guard; protection is server 401 only.

| Class | Screens |
|---|---|
| Fully live | Journal, Vault, World, ChatRoute/ChatPanel, Login |
| Partial | Today (crash bug ORPH-18), Interests, Settings, SetupWizard, ConnectionsPanel |
| Read-only | Media, Projects (health bug ORPH-19), Lab, LabOperationsPanel |
| Mocked / dead | ChatScreen (unrouted, incompatible body) |
| Missing | No `/api/proposals` UI, no identity-admin UI (deliberate headless) |

Step-up UX is half-wired: `api.ts` always sends `X-PW-StepUp: 1`;
interactive `useStepUp` prompt exists only in Vault/Settings/Connections.

## 9. Storage / state inventory

| Path (rel. `PW_DATA_DIR`/`PW_CONFIG_DIR`) | Format | Writers | Backup | Flags |
|---|---|---|---|---|
| `world.json` | JSON | save_world, CLI, API writes | **yes** | MULTIPLE-WRITERS (last-write-wins) |
| `journal.ndjson` | NDJSON | Journal append | **yes** | append; global + per-user |
| `users/<id>/{world,journal}` | JSON/NDJSON | per-user | **no** | PERSISTED-BUT-NOT-BACKED-UP |
| `vault.enc` | enc JSON | Vault | **no** (deliberate) | — |
| `sessions.json` | JSON | SessionStore | no | PBNBU |
| `users.json` | JSON | IdentityStore | no | PBNBU (hashed tokens) |
| `reminders.json` | JSON | Scheduler | no | PBNBU |
| `apps.json` | JSON | apps API | no | PBNBU |
| `proposals.json` | JSON | tool_registry | no | PBNBU; global |
| `updates-session.json` | JSON | UpdateManager | no | PBNBU |
| `setup-complete` | marker | setup | no | — |
| `data/.env` | dotenv | setup | no | plaintext credential |
| `memory.fts5.db` | SQLite | native_memory | no | DERIVED (rebuildable) |
| `theme-packs/`, `template-sources/` | dir | manual | no | read-only |
| `executions.json` | JSON | ExecutionStore | no | UNUSED (orphan) |
| `config/connections.json` | JSON | manual | tracked | secret-free |
| `config/connections.local.json` | JSON | ConnectionManager | no | PBNBU |
| `config/prompts{,.local}` | md | manual | no | `prompts.local` not gitignored |
| `~/.config/personal-world/{discovery.json,reconciler/desired,lab.json,lab/desired}` | JSON/YAML | API/manual | no | out-of-volume, PBNBU |
| Compose project `compose.yaml` | YAML | `updates apply/rollback` | tracked | code rewrites tracked infra |

Process-local (lost on restart): NativeDiscovery `_items`/`_feedback`
(should persist), registry health cache (rebuilt per request), vault key
(deliberate), proposal dict (when no `configure_proposal_store`),
Scheduler thread.

Backup gap: `backup_payload` covers **global world + global journal
only**. All other stores, and all per-user trees, are unbacked.

## 10. Config / environment inventory

Documented canonical: `PW_API_TOKEN`, `PW_DATA_DIR`, `PW_CONFIG_DIR`,
`PW_IDENTITY_MODE`, `PW_LAB_CLI`.

Deleted by the 2026-09-16 Station cutover (no longer canonical; kept
here only as history): `PW_FRONTEND_DIST` (removed with the SPA dist
build), `PW_FRONTEND` (deleted mode switch; a stray value is inert).

Undocumented in canonical docs: `PW_DEV_AUTH_BYPASS`,
`PW_TRAEFIK_BASE_URL`, `PW_SOURCE_CONTROL_ROOT`, `PW_PORT`,
`OLLAMA_HOST`, `OIDC_CLIENT_SECRET`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `PLEX_TOKEN`, `SONARR/RADARR/LIDARR_API_KEY`,
`NTFY_TOPIC`, `PW_UPDATES_PROJECT_DIR`.

| Flag | Detail |
|---|---|
| Unused / inert | `PW_FRONTEND_DIST`, `PW_FRONTEND` — deleted by the 2026-09-16 Station cutover (SPA/removed dist build; a stray value is inert) |
| Stale name | `PW_CONFIG_LOCAL_DIR` (docs only, no code) |
| Fallback aliases | `PLEX_TOKEN`; `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` defaults; `<data>/.env` outranks `PW_API_TOKEN` |
| Unsafe trust edges | `PW_DEV_AUTH_BYPASS` (default off, true-loopback only); step-up `X-PW-StepUp: 1` proxy trust; single-mode OIDC maps any verified subject to owner `primary` |
| Machine-specific | `compose.homelab.yaml` host paths; `config/connections.json` search path `/data/repos/personal-world`; `LAB_CANDIDATES` absolute paths |

## 11. Test coverage gaps

- Runtime modules with **no behavioral coverage**: `execution_viewer.py`,
  `theme_pack.py`, `providers/native_calendar.py`,
  `native_deployment.py`, `native_discovery.py`, `native_lab.py`,
  `native_notifications.py`, `native_updates.py`, `native_vault.py`,
  `traefik_ingress.py`, `providers/lab_{deploy,health,resources,secrets,settings}.py`.
- No CLI tests for `actors`, `cement`, `init`, `world-export`,
  `story-export`, `backup --apply`.
- `tests/templates/` is collected (45 tests) but its `fixtures.py` is
  unreachable dead helper.
- `docs/screenshots/*.png` are tracked and rewritten by
  `frontend/e2e/docs-screenshots.spec.ts`.
- Duplicate `_client`/`client`/`env`/`_git` fixtures across 7–9 files
  instead of `conftest.py`.
- Tests pinned to legacy paths/strings: `test_dockerfile.py:53` (comment),
  `test_public_safety.py:169` (`frontend-v2/` gone),
  `test_dist_safety.py:127-137` (retired UI markers), `PW_FRONTEND`
  absence guards.

## 12. `.gitignore` changes

Added this pass: `node_modules/`, `test-results/`,
`playwright-report/`, `data.bak.*/`, `.bcode/`, `.mimocode/`,
`frontend/test-layout.js`. `.dockerignore` still does not exclude
`test-results/`, `.bcode/`, `.mimocode/`, `data.bak.*/`,
`frontend/test-layout.js` — a follow-up if they exist at build time.