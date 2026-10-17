# HANDOFF — Full Surface Audit, 2026-09-16

Auditor: code-trace audit (wiring-audit method), cross-checked against
`docs/surfaces/MASTER-SURFACE-REGISTRY.md` and `docs/surfaces/ORPHANS.md`.
Head: `3accaee` (main). Product: **Project Worlds** (identifiers `personal_world`).
Status vocabulary: WIRED · PARTIAL · ORPHAN · DEAD · STUB · DUP.

---

## 1. What the product actually is, right now

- Backend: FastAPI app (`src/personal_world/api.py`, factory
  `create_app`) + argparse CLI (`python -m` entry `cli.py`, plus
  decision-#19 surface `cli_dispatch.py` → `do NOUN VERB`, `api`, `api-manifest`).
- Product UI: **Station** — static HTML/JS/CSS at
  `design/opendesign-exploration/station/`, served same-origin at `/station/`
  (`station_ui.py`). Plus server-rendered `/login` and `/setup` wizard.
- React SPA: **removed 2026-09-16** (single-branch cutover). `frontend/`
  contains only the Playwright e2e gate. No SPA remnants found.
- No SQL database; state is JSON/NDJSON/SQLite-FTS files under `<data>/` + git (read-only) for source control.

---

## 2. Surface inventory

### 2.1 Station UI screens (served at `/station/`)
| Surface | File | State |
|---|---|---|
| Map/front door | `station/index.html` | WIRED (reads `/api/manifest`, `/api/auth/session`, `/api/proposals`, `/api/reminders`, `/api/journal`, `/api/prefs*` via `api.js`/`real-data.js`) |
| Talk (chat) | `station/chat.html` + `chat.js` | PARTIAL — transcripts in **localStorage**; deliberate "does NOT invent replies"; binding to API-010 is declared, not built |
| Interests / Journal / Projects views | `interests-view.js`, `journal-view.js`, `projects-view.js` | PARTIAL/specimen — localStorage-only; honest labels + documented real bindings (API-005 etc.) |
| Settings | `settings.html` | PARTIAL — read-only; prefs/sections PUT not wired ("deliberate act" note). Backup/restore panel wired |
| Onboarding | `onboarding.js` | specimen, localStorage |
| Search | `search.js` | WIRED (ARIA combobox over live map) |
| Starmap/shapemap/deeplink/prefs | `starmap.js`, `shapemap.js`, `deeplink.js`, `station.js` | WIRED internally; corner prefs in **localStorage** (documented mapping to API-030/065, not yet synced to server) |
| Dead-by-design | `station/_legacy/*` | DEAD — router refuses `_`+`.`-prefixed segments (`station_ui.py:88-89`) |

**UI→API wiring facts:** ~110 backend routes exist; the Station calls **15**.
No calls to nonexistent endpoints (client mode is manifest-verified,
`api.js:513-531`). Everything else is an API/CLI-first surface, not headphone.

### 2.2 Other user-facing routes
- `/login` (`login_page.py:44`, `static/login/index.html`) — WIRED (local login + OIDC button).
- `/setup` wizard (`setup_wizard.py:426-566`, `static/setup/wizard.js`) — WIRED, first-run-only. DUP: legacy `POST /api/setup` (`api.py:455`) coexists — two first-run paths.
- `/` redirect → `/station/` (`api.py:2786`).

### 2.3 HTTP API (curated: `/api/manifest` = 99 rows vs live table, `api_manifest.py:132-639`)
All gates: `require_auth` (`api.py:225`), `require_step_up` (`api.py:193`).
Families (all WIRED unless noted):
- Core: `/healthz`, `/api/setup*`, `/api/status`, `/api/daily`, `/api/journal*` (supersede/history/audit), `/api/memory/search`
- Chat/brain: `POST /api/chat` (`api.py:769`), `/api/chat/history|providers|test` — **never called by UI** (biggest wiring gap), plus `/api/brain/*`, `/api/templates`
- Proposals: list/get/approve/reject/execute (`api.py:1055-1109`), step-up gated
- Connections: full CRUD/simple/config/test/validate/schemas/overview (`api.py:1179-1307`; `validate` = pure alias of `test` — DUP)
- Identity: `/api/identity/users|agents|principal` (admin-gated, `_is_admin` `api.py:2338`)
- Ops: `/api/lab/*`, `/api/native-lab/*`, `/api/reconciler/*`, `/api/ingress/rollups`, `/api/updates` (read-only; apply/rollback CLI-only)
- Prefs/sections/apps/media/discovery/source_control/vault/exports/actors/reminders — WIRED
- Auth (`auth_routes.py:90-374`): login/logout/session/oidc full PKCE/step-up — WIRED. OIDC-as-step-up: STUB (documented, `auth_routes.py:385-389`)
- Worlds backup (`worlds_backup.py:688/720/739`): WIRED, step-up gated — **uncurated in manifest**
- Art: `/companions/{name}.svg`, `/today/{name}.svg`, `/icons/sprite.svg`, `/fonts/{name}` (`api.py:2806-2849`) — served; UI orphans (exists for theme/agent surfaces)

### 2.4 CLI
- Legacy (`cli.py`): `status, daily, journal, actors, settings-export, world-export, story-export, backup, cement, init, manifest, prefs, changes, history, sync-status, framework validate|validate-packs, updates check|preview|apply|rollback|status, worlds backup|restore` — all WIRED.
- Decision-#19 (`cli_dispatch.py`, registered `cli.py:841-843`): `api-manifest`, `api METHOD PATH`, `do {world,journal,reminders,proposals,prefs,interests,discovery,projects,capabilities,chat,templates,auth,oidc}` × 36 verbs — all WIRED (writes go propose→approve→execute, step-up token).
- **Deliberate DUPs** (additive, documented `cli_dispatch.py:24-31`): `status`/`actors`≈`do world status`, `journal`≈`do journal list`, `prefs`≈`do prefs get/set`, `changes`/`history`≈`do projects repos/history`. Divergence: legacy `prefs set`, `cement`, `daily --apply`, `backup --apply` mutate directly (not on proposal path).

### 2.5 Providers (`providers/registry.py`, built in `app.py:154-467`)
WIRED native baselines: source_control (NativeGit), secrets (NativeVault→Vault Fernet `vault.enc`), memory (SQLite FTS5 of journal — indexed **one-shot in setup wizard only**, no app-start reindex), notifications (webhook/ntfy, feeds scheduler `api.py:2248`), update_discovery, ingress (Traefik), discovery, lab, homelab_* externals.
Chat providers (`chat_registry.py:366-800`, built at 814): ollama, openai_compat, openai, anthropic, opencode — all implemented.
Known partials/orphans per ORPHANS.md, still true:
- `NativeCalendarProvider.upcoming` — no caller; CalDAV STUB (docstring only)
- `NativeUpdatesProvider.check` (`native_updates.py:98`) — no caller; updates run via `updates.py` CLI path
- `NativeDeploymentProvider.deploy` paths — observe-wired only, deploy ORPHAN
- `NativeLabSettings.diff` — no caller
- `MediaAdapter.item()` — STUB everywhere; reconciler `ServiceAdapter` classes DEAD
- ThemePack `/static/companions/*` default paths (ASSET-007a) — **no `/static` mount** → theme-pack assets unreachable by that path

### 2.6 Workers
- Reminder scheduler thread (60s) + per-person tick (multi mode) — WIRED (`api.py` lifespan `2316-2335`).
- Daily loop — WIRED (`POST /api/daily`, CLI `daily`).

### 2.7 Storage
`world.json`, `journal.ndjson`, `reminders.json`, `proposals.json`, `users.json`, `sessions.json`, `vault.enc`, `memory.fts5.db`, chat history ndjson, `apps.json`, `updates-session.json`, `executions.json` (**DEAD — written by nothing**), plus `config/connections.json` (+local), `oidc.json`, `prompts/*`, `~/.config/personal-world/{discovery,lab,reconciler desired}`.

### 2.8 Deploy & scripts
- `compose.yaml` (ollama qwen3:1.7b + core, port 8000), `compose.dev.yaml`, `compose.homelab.yaml`, `Dockerfile` (copies Station), `install.sh` — WIRED.
- Scripts: `dev.sh`, `safe-commit.sh` (test-gated), `reset-dev.sh` — all WIRED, no orphans.

### 2.9 Tests & gates
Tests gate public safety (`test_public_safety.py`), auth boundary/step-up/OIDC, manifest correctness, design tokens, Dockerfile, frontend serving, framework validate. UI gate: `frontend` Playwright suite (a11y/honest-states/keyboard/motion+axe) — `cd frontend && npm run test:e2e`.

### 2.10 Truth routing
`.project/CURRENT.md` (one pointer) → `.project/project.yaml`, `.project/contracts/adoption.yaml`, `.project/decisions/`, canonical docs (`docs/ARCHITECTURE.md`, `NATIVE-BASELINE-AND-ENRICHMENT.md`, `PERSONAL-WORLD-FINISH-LINE.md`, `docs/accessibility/*`, `docs/surfaces/*`, `design/tokens.json`).

---

## 3. Newly found (not yet in ORPHANS.md / REGISTRY) — verified

1. **BUG — `tool_registry.py:1346`**: `from .source_control import history as sc_history` — that function does not exist (`repository_history`, `source_control.py:199`). Tool `inspect_source_control_history` raises at invocation (fails honest as `unavailable`) but is non-functional. Fix is one rename.
2. **DUP — `POST /api/connections/validate` = alias of `test`** (`api.py:1299-1307`) — candidate for consolidation.
3. **DUP — `chat_registry.ChatProviderRegistry`** (`chat_registry.py:858`) never instantiated (ORPHANS lists it; runtime path is `Registry.provider_for`).
4. **Station `/static/companions` theme-pack paths confirmed broken first-hand** (matches ASSET-007a).
5. **Station fonts orphaned**: shipped webfonts (`instrument-sans`, `young-serif`) not referenced by any Station CSS; Station uses system stacks (`station.css:52-54`).
6. **No app-start journal reindex** for memory (FTS5 built once at provision; subsequent journal writes aren't reindexed — `memory/search` drifts stale). Severity: PARTIAL, honest but stale.

## 4. What needs wiring where — ranked gaps

1. **Companion chat → API-010..012.** `chat.js` → `POST /api/chat`, `/api/chat/history`, `/api/chat/providers`. Bigger full-backend endpoint family exists and is tested; UI never touches it. Also policy-approve `/api/chat/test` surface. This is the single biggest frontend↔backend gap.
2. **Writes from Station**: `PUT /api/prefs` (settings "deliberate act" flow), `PUT /api/sections`, reminders CRUD, `POST /api/journal` + supersede, proposal actions — all endpoints live; UI is localStorage/read-only.
3. **Themes**: `/api/themes`, theme-pack runtime, `theme_pack.py` `/static/...` path break (ASSET-007a) — needs a `/static` mount or serve-via-`/companions/` fix, and a Station consumer (theme picker or localStorage→server sync).
4. **localStorage↔API-065 prefs sync** for corner prefs (density/theme/motion/companions) — currently local-only by design.
5. **Source control in Projects view**: `/api/source-control/*` reads + `POST refresh`; fix the `tool_registry` import botch so projection/proposal tools work first.
6. **Projects status**: `/api/projects/status` (`api.py:2604`) uncalled by `projects-view.js` (specimen).
7. **Cleanup queue (safe deletions)**: `executions.json` + `execution_viewer.py`, `user.py`, `chat.py` class copies, `SOPSVaultAdapter`/`SopsBroker`, `build_media_engine_from_config`, unused provider methods — confirm each against Finish Line before deleting.
8. **Manifest hygiene**: worlds-backup + setup-wizard routes are live but uncurated (`uncurated` bucket); decide curation vs exemption.

## 5. Security note (action needed)

Subagent pass flagged **private topology (duckdns hostname + RFC1918 IP) present in `.project/CURRENT.md`** — violates the public-repo boundary contract; redact before it ships. UNVERIFIED by me directly; verify then redact under the security contract.

## 6. Verification used
- Full trace of `api.py`, `auth_routes.py`, `setup_wizard.py`, `station_ui.py`, `login_page.py`, `worlds_backup.py`, `cli.py`, `cli_dispatch.py`, `api_manifest.py`, providers, `station/*.{js,html,css}`, `theme_pack.py`.
- Cross-check against committed registries (`docs/surfaces/*`) where present.
- NOT run: pytest / framework validate / Playwright suite (audit only). UNVERIFIED claims are labeled in-text.

## 7. Next
1. Verify + redact CURRENT.md topology (§5).
2. One-line fix: `tool_registry.py:1346` import rename.
3. Decide chat wiring scope as first Finish-Line implementation target (gap 1 of §4).
4. Update `ORPHANS.md` with §3 items (mark `history` bug; fonts note).
