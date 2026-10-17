# Master Surface Registry — Project Worlds

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (the code and `.project/CURRENT.md` win) · **Read this if:** you need a stable ID (`UI-001`, `API-003`, `PROV-001`, …) and a dated extraction of what existed on 2026-09-14 · **Superseded by:** the code and `.project/CURRENT.md`; current backend maps live in the sibling `docs/surfaces/` matrices

**In short:** A dated, read-only index of every meaningful surface extracted on 2026-09-14 (with a 2026-09-15 correction pass). Its **IDs are still the stable index** other docs resolve against, but the rows that cite `frontend/` describe the retired pre-flip SPA, not today's interface. Treat every "State" cell as point-in-time; verify against the code before relying on it.

**What changed since this extraction:** the product is called **Worlds** in prose; the interface is `ui/` (Bridge home, Memory, Chat, Settings, Crew, Interests — 2026-09-22 flip, Bridge 2026-09-25); the core architecture is now **rooms** (services serving the Play-Nice `room/0` contract, read from a runtime registry), with per-person **crew**, **keepers** and **doorways**; and Discovery/Candy extraction is in progress. None of those are in the tables below.

Extraction pass, 2026-09-14. Read-only index of every meaningful
surface. Baseline: branch `docs/current-product-refresh`, SHA
`2e728fd050b3a67bd7e62afeaf6a0be7fb7d645a`. Product renamed
"Project Worlds" (was "Personal World"); technical identifiers
unchanged. Source of truth is the code, not docs.

State vocabulary: ACTIVE, PARTIAL, HIDDEN, INTERNAL, STUB, ORPHAN,
SUPERSEDED, UNKNOWN.

> **Delta (2026-09-15, D1–D3 auth/authority pass).** This extraction
> predates the auth convergence. Corrections now applied below and
> verified against code at SHA `60823ae`:
>
> - **AUTH-002 / AUTH-003 / AUTH-008 are ACTIVE, not PARTIAL.** Browser
>   session and OIDC both resolve through `require_auth`
>   (`api.py:211-276`); the session step-up grant is consumed by
>   `require_step_up` (`api.py:143-175`, `auth.py:31-42`).
> - **`POST /api/discovery/sources` and `POST /api/discovery/interests`
>   now require step-up** (`api.py:1647/1673`), correcting API-050/051.
> - **`GET /api/proposals{,/{id},/approve,/reject,/execute}` exists**
>   (`api.py:936-1004`) — not in the original API-ID list. Durable store
>   `data/proposals.json`.
> - **`GET /api/source-control/rollups` no longer exists** (API-080 is
>   stale); source-control search paths are read directly from
>   `config/connections.json` in `source_control.py:283,311`.
> - **TOOL-019 no longer reads `reminders.json` directly**; the tool
>   requires a wired `Scheduler` (`tool_registry.py:1154-1168`).
> - **`/api/auth/*` (login/logout/session/oidc/step-up) routes** live in
>   `auth_routes.py`; the registry's AUTH-009 row covers them.
>
> See `docs/repo/WIRING-READINESS.md` for the consolidated assessment.

## Human / UI surfaces

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| UI-001 | screen | Today | YES | `GET /` (SPA route `/`) | `frontend/src/screens/TodayScreen.tsx` | API-003, API-004, API-030, API-032, API-066 | none | api.ts lib | NAV-001, NAV-013 | session/bearer client-side | API | ACTIVE |
| UI-002 | screen | Interests | YES | SPA route `/interests` | `frontend/src/screens/InterestsScreen.tsx` | API-051, API-052 | API-050/051 (step-up) | api.ts | NAV-001 | session/bearer | API | ACTIVE |
| UI-003 | screen | Media | YES | SPA route `/media` | `frontend/src/screens/MediaScreen.tsx` | API-053..API-057 | none | api.ts | NAV-001 | session/bearer | API (media adapters) | ACTIVE |
| UI-004 | screen | Projects | YES | SPA route `/projects` | `frontend/src/screens/ProjectsScreen.tsx` | API-033, API-036, API-037, API-067 | API-035 (approved refresh) | api.ts, `lib/project-status.ts` | NAV-001 | session/bearer | agent-sync + native git | ACTIVE |
| UI-005 | screen | Lab | YES | SPA route `/lab` | `frontend/src/screens/LabScreen.tsx` | API-037..API-048 | none | api.ts | NAV-001 | session/bearer | lab CLI / native lab | ACTIVE |
| UI-006 | screen | Journal | YES | SPA route `/journal` | `frontend/src/screens/JournalScreen.tsx` | API-005, API-008, API-009 | API-006, API-007 | api.ts, `lib/correction-draft.ts` | NAV-001 | session/bearer | journal.ndjson | ACTIVE |
| UI-007 | screen | Vault | YES | SPA route `/vault` | `frontend/src/screens/VaultScreen.tsx` | API-049 | API-050, API-051, API-052 | api.ts | NAV-001 | session/bearer | vault.enc | ACTIVE |
| UI-008 | screen | Chat | YES | SPA route `/chat` | `frontend/src/screens/ChatRoute.tsx`, `ChatScreen.tsx` | API-010, API-011, API-012, API-013, API-016, API-017, API-077 | none | api.ts | NAV-001 | session/bearer | reasoning provider + world.json | ACTIVE |
| UI-009 | screen | Settings | YES | SPA route `/settings` | `frontend/src/screens/SettingsScreen.tsx` | API-030, API-031, API-032, API-017..API-020, API-024, API-066, API-077 | API-030, API-032, API-022, API-023, API-024 | api.ts | NAV-001 | session/bearer | world.json (prefs/layout) + connections config | ACTIVE |
| UI-010 | screen | SetupWizard | YES | SPA route `/setup` | `frontend/src/screens/SetupWizard.tsx` | API-001, API-002 | API-002 (token, vault passphrase) | api.ts | NAV-002, NAV-003 | public (first-run only) | setup-complete marker | ACTIVE |
| UI-011 | screen | LoginScreen | YES | SPA route `/login` | `frontend/src/screens/LoginScreen.tsx` | API-002, API-078 | POST /api/auth/login (AUTH-009) | api.ts | NAV-003, NAV-004 | public | session store | ACTIVE |
| UI-012 | screen | World (Your World) | YES | SPA route `/world` | `frontend/src/screens/WorldScreen.tsx` | API-003, API-016 | API-075..API-077 (world quick actions) | api.ts | NAV-001 | session/bearer | world.json | ACTIVE |
| UI-013 | component | WorkshopShell | YES | wraps all non-auth routes | `frontend/src/shell/WorkshopShell.tsx` | UI-014, UI-015, UI-016 | none | DefaultEdge, SectionNav | NAV-001 | client (gate via NAV-003) | frontend | ACTIVE |
| UI-014 | component | SectionNav | YES | inside WorkshopShell | `frontend/src/shell/SectionNav.tsx` | API-032 (sections order/hidden) | none | router Links | UI-013 | client | world.json layout via API-032 | ACTIVE |
| UI-015 | component | WorldIdentity | YES | sidebar identity block | `frontend/src/shell/WorldIdentity.tsx` | API-032, API-077 | none | api.ts | UI-013 | client | API | ACTIVE |
| UI-016 | component | CompanionPresence | YES | sidebar companion slot | `frontend/src/shell/CompanionPresence.tsx` | COMPANIONS map (A11Y-011) | none | companion-context | UI-013 | client | server pref (`prefs.companion`) | ACTIVE |
| UI-017 | component | AuthLayout | YES | wraps /login, /setup | `frontend/src/shell/AuthLayout.tsx` | none | none | none | NAV-003 | public | frontend | ACTIVE |
| UI-018 | primitive | StepUpPrompt | YES | write-path 403 recovery | `frontend/src/primitives/StepUpPrompt.tsx` | API-080 (step-up) | re-sends X-PW-StepUp | api.ts withStepUp | all write paths | session + step-up | session store step_up_until | ACTIVE |
| UI-019 | primitive | StatusChip | YES | status vocabulary chip | `frontend/src/primitives/StatusChip.tsx` | status vocabulary (DOMAIN-005 status.py) | none | none | all screens | client | status.py | ACTIVE |
| UI-020 | component | ChatPanel | YES | chat composer/messages | `frontend/src/components/ChatPanel.tsx` | API-010 reply/proposal | API-006 (journal correction draft) | ChatScreen | UI-008 | client | API | ACTIVE |
| UI-021 | component | ConnectionsPanel | YES | connections management | `frontend/src/screens/ConnectionsPanel.tsx` | API-017..API-024 | API-021, API-022, API-023 | api.ts | UI-009 | client + step-up writes | connections config | ACTIVE |
| UI-022 | component | LabOperationsPanel | YES | lab ops detail | `frontend/src/screens/LabOperationsPanel.tsx` | API-037..API-044 | none | LabScreen | UI-005 | client | lab CLI packets | ACTIVE |
| UI-023 | page | SPA missing-frontend 503 page | INDIRECT | `GET /` with unbuilt dist | `src/personal_world/api.py::SPA_NOT_BUILT_HTML` | none | none | none | browser | public | none | ACTIVE |

## Navigation

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NAV-001 | route | SPA route table | YES | BrowserRouter | `frontend/src/App.tsx::AppRoutes` | location | none | all UI-* | UI-013 | client | App.tsx | ACTIVE |
| NAV-002 | route | /setup-wizard alias | INDIRECT | SPA route `/setup-wizard` | `frontend/src/App.tsx:87` | none | none | Navigate→/setup | bookmarks | public | App.tsx | ACTIVE |
| NAV-003 | route | ShellGate + AuthRoutes split | INDIRECT | App mount | `frontend/src/App.tsx::ShellGate/AuthRoutes` | location | none | UI-013, UI-010, UI-011 | App | public | App.tsx | ACTIVE |
| NAV-004 | route | 401→/login redirect | INDIRECT | api boundary 401 handler | `frontend/src/lib/api.ts::setLoginNavigation`, `App.tsx::LoginNavigationWiring` | any API 401 | clears pw_token | /login | all screens | public | api.ts | ACTIVE |
| NAV-005 | route | SPA fallback / deep links | INDIRECT | `GET /{full_path:path}` | `src/personal_world/api.py::spa_fallback` | dist allowlist | none | _spa_index | browser | public | dist dir | ACTIVE |
| NAV-006 | config | ShellModes route→mode map | INDIRECT | `getShellMode(pathname)` | `frontend/src/shell/ShellModes.ts` | route table | none | UI-013 | UI-013 | client | ShellModes.ts | ACTIVE |

## API endpoints

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| API-001 | route | GET /healthz | INDIRECT | `@app.get("/healthz")` | `api.py::healthz` | STORE-009, env PW_API_TOKEN | none | none | compose healthcheck, browser | none | process env + marker | ACTIVE |
| API-002 | route | GET /api/setup/status; POST /api/setup | INDIRECT | setup routes | `api.py::setup_status/setup` | STORE-009 | STORE-010 (data/.env), STORE-009, STORE-003 (vault init) | vault.unlock | UI-010 | public (409 after marker) | setup-complete marker | ACTIVE |
| API-003 | route | GET /api/status | INDIRECT | status route | `api.py::status` | DOMAIN-001, DOMAIN-007 | none | build_registry | UI-001, UI-008, UI-012 | require_auth | world.json | ACTIVE |
| API-004 | route | GET/POST /api/daily | INDIRECT | daily routes | `api.py::daily_view/daily_run` | DOMAIN-001 | world.json, JOURNAL-001 (POST) | DOMAIN-002 | UI-001 | require_auth | world.json/journal | ACTIVE |
| API-005 | route | GET /api/journal | INDIRECT | journal route | `api.py::journal_view` | JOURNAL-002 | none | Journal.current_events | UI-006 | require_auth + person | journal.ndjson | ACTIVE |
| API-006 | route | POST /api/journal | INDIRECT | note route | `api.py::journal_note` | — | JOURNAL-001 | record() | UI-006 | require_auth + person | journal.ndjson | ACTIVE |
| API-007 | route | POST /api/journal/supersede | INDIRECT | supersede route | `api.py::journal_supersede` | JOURNAL-002 | JOURNAL-003 | supersede() | UI-006, UI-020 (assistant draft) | require_step_up + person | journal.ndjson | ACTIVE |
| API-008 | route | GET /api/journal/history | INDIRECT | history route | `api.py::journal_history` | JOURNAL-002 | none | history_of() | UI-006 | require_auth | journal.ndjson | ACTIVE |
| API-009 | route | GET /api/journal/audit | INDIRECT | audit route | `api.py::journal_audit` | JOURNAL-005 | none | AuditRenderer | UI-006 (audit view) | require_auth | journal.ndjson | ACTIVE |
| API-010 | route | POST /api/chat | INDIRECT | chat route | `api.py::chat`, `_chat_with_tools_loop` | CHAT-004, CHAT-005, STORE-001 | JOURNAL-001 (recommendation), proposals | CHAT-006, CHAT-008 | UI-008 | require_auth + person-optional | provider response | ACTIVE |
| API-011 | route | GET /api/chat/providers | INDIRECT | providers route | `api.py::chat_providers` | DOMAIN-007 | none | impl.observe() | UI-008, UI-009 | require_auth | registry | ACTIVE |
| API-012 | route | POST /api/chat/test | INDIRECT | test route | `api.py::chat_test` | — | none | CHAT-009 | UI-009 | require_auth (was public; now gated) | provider response | ACTIVE |
| API-013 | route | GET /api/tools | INDIRECT | tools route | `api.py::tools` | TOOL-000 registry | none | build_default_tools | diagnostics | require_auth | tool_registry.py | ACTIVE |
| API-014 | route | GET /api/actors | INDIRECT | actors route | `api.py::actors` | DOMAIN-007 | none | registry.actors | UI-012 (staff view) | require_auth | registry | ACTIVE |
| API-015 | route | GET /api/manifest | INDIRECT | manifest route | `api.py::manifest` | DOMAIN-007 | none | registry.manifest | CLI-009 parity, UI | require_auth | registry | ACTIVE |
| API-016 | route | GET /api/memory/search | INDIRECT | memory search | `api.py::memory_search` | PROV-007 | none | impl.search | chat/tooling | require_auth | derived FTS index | ACTIVE |
| API-017 | route | GET /api/connections/schemas | INDIRECT | schemas route | `api.py::connection_schemas` | CONN-003 | none | get_capability_schemas | UI-021 | require_auth | provider_schemas.py | ACTIVE |
| API-018 | route | GET /api/connections/schema/{capability} | INDIRECT | schema route | `api.py::connection_schema` | CONN-003 | none | get_capability_schema | UI-021 | require_auth | provider_schemas.py | ACTIVE |
| API-019 | route | GET /api/connections/config | INDIRECT | config route | `api.py::connections_config` | CONN-002 | none | ConnectionManager | UI-021 | require_auth | connections(+local) | ACTIVE |
| API-020 | route | GET /api/connections/overview | INDIRECT | overview route | `api.py::connections_overview` | DOMAIN-007, CONN-002, STORE-017 (oidc) | none | status_map + schemas | UI-021 | require_auth | merged status/config | ACTIVE |
| API-021 | route | GET/PUT /api/connections; DELETE /api/connections/{name} | INDIRECT | list/save/delete | `api.py::connections_list/save/delete` | CONN-002 | CONN-002, STORE-015 (local) | ConnectionManager | UI-021 | GET require_auth; PUT/DELETE in-handler require_step_up | connections config | ACTIVE |
| API-022 | route | POST /api/connections/config/{key} | INDIRECT | native config save | `api.py::save_native_config` | CONN-002 | CONN-002 (calendar/notifications/updates/deployment keys) | ConnectionManager.save_native_config | UI-021 | require_auth + in-handler step-up | connections config | ACTIVE |
| API-023 | route | POST /api/connections/test | INDIRECT | adapter test | `api.py::test_connection/_test_adapter` | external endpoints | none | urllib probes | UI-021 | require_auth | live probe result | ACTIVE |
| API-024 | route | POST /api/connections/validate | INDIRECT | validate alias | `api.py::validate_connection` | external endpoints | none | _test_adapter | UI-021 | require_auth | live probe result | ACTIVE |
| API-025 | route | GET /api/exports/settings | INDIRECT | settings export | `api.py::settings_export` | DOMAIN-001 | none | export.settings_export | UI-009, CLI parity | require_auth | derived only | ACTIVE |
| API-026 | route | GET /api/exports/world | INDIRECT | world export | `api.py::world_export` | DOMAIN-001 | none | export.world_export | UI | require_auth | world.json | ACTIVE |
| API-027 | route | GET /api/exports/story | INDIRECT | story export | `api.py::story_export` | JOURNAL-002 | none | story_export | UI | require_auth | journal.ndjson | ACTIVE |
| API-028 | route | GET /api/backup | INDIRECT | backup payload | `api.py::backup` | DOMAIN-001, JOURNAL-002 | none | backup_payload | UI, ops | require_auth | world.json+journal | ACTIVE |
| API-029 | route | GET /api/updates | INDIRECT | updates view | `api.py::updates_view` | PROV-027/PROV-026, STORE-008 | none | UpdateManager.check | UI | require_auth | updates-session.json | ACTIVE |
| API-030 | route | GET /api/prefs; PUT /api/prefs | INDIRECT | prefs routes | `api.py::prefs_get/prefs_put` | A11Y-001 | world.json accessibility | prefs.get/set_prefs | UI-009 | GET auth; PUT require_step_up | world.json | ACTIVE |
| API-031 | route | GET /api/prefs/schema | INDIRECT | prefs schema | `api.py::prefs_schema` | A11Y-001 | none | PREFS specs | UI-009 | require_auth | prefs.py | ACTIVE |
| API-032 | route | GET /api/sections; PUT /api/sections | INDIRECT | sections routes | `api.py::sections_get/sections_put` | DOMAIN-008, DOMAIN-007 | world.json layout | sections_mod | UI-014, UI-009 | GET auth; PUT require_step_up | world.json layout | ACTIVE |
| API-033 | route | GET /api/source-control/status | INDIRECT | sc status | `api.py::source_control_status` | PROV-001 paths | none | status_all | UI-004, UI-012 | require_auth | external git repos | ACTIVE |
| API-034 | route | GET /api/source-control/history | INDIRECT | sc history | `api.py::source_control_history` | PROV-001 | none | repository_history | UI-004 | require_auth | external git repos | ACTIVE |
| API-035 | route | POST /api/source-control/refresh | INDIRECT | sc refresh (propose→approve→act #1) | `api.py::source_control_refresh` | PROV-001 | JOURNAL-001 (PROVIDER_ACTION) | repository_status | UI-004 | require_step_up | external git repos | ACTIVE |
| API-036 | route | GET /api/source-control/enrichment | INDIRECT | GitHub enrichment | `api.py::source_control_enrichment` | PROV-025 (gh CLI) | none | GitHubEnrichment | UI-004 | require_auth | external GitHub via gh | ACTIVE |
| API-037 | route | GET /api/lab/state | INDIRECT | lab state | `api.py::lab_state` | PROV-021 (lab CLI) | none | LabState.observe | UI-005 | require_auth | external lab CLI packet | ACTIVE |
| API-038 | route | GET /api/lab/settings | INDIRECT | lab settings | `api.py::lab_settings` | PROV-016 | none | LabSettings.observe | UI-005 | require_auth | lab CLI | ACTIVE |
| API-039 | route | GET /api/lab/settings/inspect/{service} | INDIRECT | lab settings inspect | `api.py::lab_settings_inspect` | PROV-016 | none | inspect() | UI-005 | require_auth | lab CLI | ACTIVE |
| API-040 | route | GET /api/lab/settings/diff/{service} | INDIRECT | lab settings diff | `api.py::lab_settings_diff` | PROV-016 | none | diff() | UI-005 | require_auth | lab CLI | ACTIVE |
| API-041 | route | GET /api/lab/health | INDIRECT | lab health | `api.py::lab_health` | PROV-017 | none | LabHealth.observe | UI-005 | require_auth | lab CLI | ACTIVE |
| API-042 | route | GET /api/lab/deploy | INDIRECT | lab deploy status | `api.py::lab_deploy` | PROV-018 | none | LabDeploy.observe | UI-005 | require_auth | lab CLI | ACTIVE |
| API-043 | route | GET /api/lab/secrets | INDIRECT | lab secrets (names only) | `api.py::lab_secrets` | PROV-019 | none | LabSecrets.observe | UI-005 | require_auth | lab CLI | ACTIVE |
| API-044 | route | GET /api/lab/resources | INDIRECT | lab resources | `api.py::lab_resources` | PROV-020 | none | LabResources.observe | UI-005 | require_auth | lab CLI | ACTIVE |
| API-045 | route | GET /api/native-lab/inventory | INDIRECT | native inventory | `api.py::native_lab_inventory` | PROV-012 | none | NativeLabInventory.observe | UI-005, TOOLS | require_auth | system observation | ACTIVE |
| API-046 | route | GET /api/native-lab/health | INDIRECT | native health | `api.py::native_lab_health` | PROV-012 | none | NativeLabHealth.observe | UI-005 | require_auth | derived | ACTIVE |
| API-047 | route | GET /api/native-lab/settings | INDIRECT | native lab settings | `api.py::native_lab_settings` | PROV-012 | none | NativeLabSettings.observe | UI-005 | require_auth | native lab | ACTIVE |
| API-048 | route | GET /api/native-lab/resources | INDIRECT | native resources | `api.py::native_lab_resources` | PROV-012 | none | NativeLabResources.observe | UI-005 | require_auth | system observation | ACTIVE |
| API-049 | route | GET /api/discovery/status | INDIRECT | discovery status | `api.py::discovery_status` | PROV-013 | none | NativeDiscovery.observe | UI-002 | require_auth | CFG-008 discovery.json | ACTIVE |
| API-050 | route | GET/POST /api/discovery/sources | INDIRECT | discovery sources | `api.py::discovery_sources/add_source` | PROV-013 | CFG-008 (POST) | add_source | UI-002 | require_auth; POST require_step_up | CFG-008 | ACTIVE |
| API-051 | route | GET/POST /api/discovery/interests | INDIRECT | interests | `api.py::discovery_interests/add_interest` | PROV-013 | CFG-008 (POST) | add_interest | UI-002 | require_auth; POST require_step_up | CFG-008 | ACTIVE |
| API-052 | route | GET /api/discovery/discover | INDIRECT | run discovery | `api.py::discovery_discover` | PROV-013 | CFG-008 (feedback/save) | discover() | UI-002 | require_auth | RSS/API fetch | ACTIVE |
| API-053 | route | GET /api/media/status | INDIRECT | media status | `api.py::media_status` | PROV-015 | none | engine.status() | UI-003, TOOL | require_auth | adapters | ACTIVE |
| API-054 | route | GET /api/media/library | INDIRECT | media library | `api.py::media_library` | PROV-015 | none | engine.library() | UI-003 | require_auth | adapters | ACTIVE |
| API-055 | route | GET /api/media/recent | INDIRECT | media recent | `api.py::media_recent` | PROV-015 | none | engine.recent() | UI-003 | require_auth | adapters | ACTIVE |
| API-056 | route | GET /api/media/activity | INDIRECT | media activity | `api.py::media_activity` | PROV-015 | none | engine.activity() | UI-003 | require_auth | adapters | ACTIVE |
| API-057 | route | GET /api/media/search | INDIRECT | media search | `api.py::media_search` | PROV-015 | none | engine.search() | UI-003 | require_auth | adapters | ACTIVE |
| API-058 | route | GET /api/reconciler/status | INDIRECT | reconciler status | `api.py::reconciler_status` | PROV-014 | none | observe() | UI-005 | require_auth | CFG-009 desired dir | ACTIVE |
| API-059 | route | GET /api/reconciler/diff/{service} | INDIRECT | reconciler diff | `api.py::reconciler_diff` | PROV-014 | none | diff() | UI-005 | require_auth | CFG-009 | ACTIVE |
| API-060 | route | GET /api/reconciler/propose/{service} | INDIRECT | reconciler propose | `api.py::reconciler_propose` | PROV-014 | none | propose() | UI-005 | require_auth | CFG-009 | ACTIVE |
| API-061 | route | GET /api/vault/status | INDIRECT | vault status | `api.py::vault_status` | STORE-003 | none | vault.is_unlocked | UI-007 | require_auth | vault.enc | ACTIVE |
| API-062 | route | POST /api/vault/unlock; POST /api/vault/lock | INDIRECT | unlock/lock | `api.py::vault_unlock/vault_lock` | STORE-003 | in-memory decrypt state | vault.unlock/lock | UI-007 | require_auth (not step-up) | vault.enc | ACTIVE |
| API-063 | route | GET /api/vault/names; POST /api/vault/set | INDIRECT | names/set | `api.py::vault_names/vault_set` | STORE-003 | STORE-003 (set) | vault.list_names/set | UI-007 | require_auth | vault.enc | ACTIVE |
| API-064 | route | GET /api/vault/{name}; DELETE /api/vault/{name} | INDIRECT | get/delete value | `api.py::vault_get/vault_delete` | STORE-003 | JOURNAL-001 (get name-only audit), STORE-003 (delete) | vault.get/delete | UI-007 | require_auth + loopback/private-peer for GET | vault.enc | ACTIVE |
| API-065 | route | GET /api/themes; GET /api/themes/{name} | INDIRECT | theme packs | `api.py::themes_list/themes_get` | STORE-013 | none | ThemePackRegistry | UI | require_auth | theme-pack manifests | ACTIVE |
| API-066 | route | GET /api/apps; PUT /api/apps | INDIRECT | apps registry | `api.py::apps_list/apps_put` | STORE-007 | STORE-007, JOURNAL-001 | json read/write | UI-009 | GET auth; PUT require_step_up | data/apps.json | ACTIVE |
| API-067 | route | GET/POST /api/reminders; PATCH/DELETE /api/reminders/{rid} | INDIRECT | reminders API | `api.py::reminders_*` | STORE-006 | STORE-006 | Scheduler.add/remove/toggle | UI (reminders), external | GET auth; POST/PATCH/DELETE require_step_up | reminders.json | ACTIVE |
| API-068 | route | GET /api/identity/users | INDIRECT | users list | `api.py::users_list` | STORE-005 | none | IdentityStore.list_users | admin UI (none yet) | require_auth + admin gate | users.json | ACTIVE |
| API-069 | route | POST /api/identity/users | INDIRECT | create user | `api.py::users_create` | — | STORE-005, JOURNAL-001 | create_user | admin | require_step_up + admin | users.json | ACTIVE |
| API-070 | route | DELETE /api/identity/users/{user_id} | INDIRECT | disable user | `api.py::users_disable` | — | STORE-005, JOURNAL-001 | disable_user | admin | require_step_up + admin | users.json | ACTIVE |
| API-071 | route | GET/POST /api/identity/agents | INDIRECT | agents list/create | `api.py::agents_list/agents_create` | STORE-005 | STORE-005, JOURNAL-001 | create_agent | admin/owner | GET auth (ownership-filtered); POST require_step_up | users.json | ACTIVE |
| API-072 | route | DELETE /api/identity/agents/{agent_id} | INDIRECT | disable agent | `api.py::agents_disable` | — | STORE-005, JOURNAL-001 | disable_agent (ownership) | owner | require_step_up | users.json | ACTIVE |
| API-073 | route | GET /api/identity/principal | INDIRECT | who am I | `api.py::identity_principal` | IDENT-001 | none | — | diagnostics | require_auth | token/identity store | ACTIVE |
| API-074 | route | PUT /api/identity/principal | INDIRECT | set display name | `api.py::identity_principal_update` | — | STORE-005, JOURNAL-001 | set_display_name | UI (profile) | require_step_up + person | users.json | ACTIVE |
| API-075 | route | POST /api/world/intent | INDIRECT | set intent | `api.py::set_intent` | DOMAIN-001 | STORE-001, world.set_intent | — | UI-012 | require_step_up | world.json | ACTIVE |
| API-076 | route | POST /api/world/fact; POST /api/world/policy | INDIRECT | record fact/add policy | `api.py::record_fact/add_policy` | DOMAIN-001 | STORE-001 | MutationDenied gate | UI-012 | require_step_up | world.json | ACTIVE |
| API-077 | route | GET /api/brain/templates; GET /api/brain/provenance | INDIRECT | brain templates | `api.py::brain_templates/brain_provenance` | CHAT-015 | none | TemplateRegistry | Nerd Mode | require_auth | config/prompts | ACTIVE |
| API-078 | route | GET /api/ingress/rollups | INDIRECT | Traefik rollups | `api.py::ingress_rollups` | PROV-023 | none | TraefikIngress.observe | UI-005 | require_auth | external Traefik API | ACTIVE |
| API-079 | route | GET /api/projects/status | INDIRECT | project estate | `api.py::projects_status` | PROV-026 (agent-sync) | none | observe_projects | UI-004 | require_auth | agent-sync subprocess | ACTIVE |
| API-080 | route | ~~GET /api/source-control/rollups~~ | — | REMOVED | (no such route at 60823ae) | — | — | — | — | — | — | SUPERSEDED (search paths still read connections.json directly in source_control.py:283,311) |
| API-081 | route | GET /api/tools → see API-013 | — | — | — | — | — | — | — | — | — | — |

## CLI commands

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CLI-001 | command | personal-world status | INDIRECT | `add("status")` | `cli.py::cmd_status` | STORE-001, DOMAIN-007 | none | build_registry | operators | none (local) | world.json | ACTIVE |
| CLI-002 | command | daily [--apply] | INDIRECT | `add("daily")` | `cli.py::cmd_daily` | DOMAIN-001 | STORE-001 (with --apply), JOURNAL-001 | DOMAIN-002 | operators | none | world.json | ACTIVE |
| CLI-003 | command | journal [-n] | INDIRECT | `add("journal")` | `cli.py::cmd_journal` | JOURNAL-002 | none | Journal.recent | operators | none | journal.ndjson | ACTIVE |
| CLI-004 | command | actors | INDIRECT | `add("actors")` | `cli.py::cmd_actors` | DOMAIN-007 | none | registry.actors | operators | none | registry | ACTIVE |
| CLI-005 | command | settings-export | INDIRECT | `add("settings-export")` | `cli.py::cmd_settings_export` | DOMAIN-001 | stdout | export.settings_export | operators | none | derived only | ACTIVE |
| CLI-006 | command | world-export | INDIRECT | `add("world-export")` | `cli.py::cmd_world_export` | DOMAIN-001 | stdout | export.world_export | operators | none | world.json | ACTIVE |
| CLI-007 | command | story-export | INDIRECT | `add("story-export")` | `cli.py::cmd_story_export` | JOURNAL-002 | stdout | story_export | operators | none | journal.ndjson | ACTIVE |
| CLI-008 | command | backup [--apply] | INDIRECT | `add("backup")` | `cli.py::cmd_backup` | DOMAIN-001, JOURNAL-002 | file (with --apply) | backup_payload | operators | none | world.json+journal | ACTIVE |
| CLI-009 | command | cement | INDIRECT | `add("cement")` | `cli.py::cmd_cement` | DOMAIN-001 | STORE-001, WORLD-003 | world.cement | operators | none (explicit user act) | world.json | ACTIVE |
| CLI-010 | command | init | INDIRECT | `add("init")` | `cli.py::cmd_init`, `init.py::init_world` | — | STORE-001, JOURNAL-001 | init_world | first-run, recovery | none | zero-provider init | ACTIVE |
| CLI-011 | command | manifest | INDIRECT | `add("manifest")` | `cli.py::cmd_manifest` | DOMAIN-007 | none | registry.manifest | operators | none | registry | ACTIVE |
| CLI-012 | command | prefs show/set | INDIRECT | `add("prefs")` | `cli.py::cmd_prefs` | STORE-001 | STORE-001 (set) | prefs.get/set_prefs | operators | none | world.json | ACTIVE |
| CLI-013 | command | changes | INDIRECT | `add("changes")` | `cli.py::cmd_changes` | PROV-001 | none | status_all | operators | none | git repos | ACTIVE |
| CLI-014 | command | history [--limit] | INDIRECT | `add("history")` | `cli.py::cmd_history` | PROV-001 | none | repository_history | operators | none | git repos | ACTIVE |
| CLI-015 | command | sync-status | INDIRECT | `add("sync-status")` | `cli.py::cmd_sync_status` | PROV-001 | none | ahead/behind | operators | none | git repos | ACTIVE |
| CLI-016 | command | framework validate [--json] | INDIRECT | `sub.add_parser("framework")` | `cli.py::cmd_framework_validate`, `framework.py` | STORE-014, compose, exports | none | validators | CI, agents | none | framework rules | ACTIVE |
| CLI-017 | command | framework validate-packs | INDIRECT | `fw_sub.add_parser("validate-packs")` | `cli.py::cmd_framework_validate_packs` | .project/participants/ | none | validate_participant_packs | CI | none | pack manifests | ACTIVE |
| CLI-018 | command | updates check/preview/apply/rollback/status | INDIRECT | `sub.add_parser("updates")` | `cli.py::cmd_updates_*`, `updates.py::UpdateManager` | PROV-027/026, STORE-008 | STORE-008, JOURNAL-001 (apply/rollback) | UpdateManager | operators | none (destructive gated by --yes) | updates-session.json | ACTIVE |

## Auth

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AUTH-001 | auth | require_auth (bearer) | INDIRECT | `Depends(require_auth)` | `api.py::require_auth` | env PW_API_TOKEN, STORE-005 (multi) | request.state.principal | identity.resolve_principal | all protected routes | bearer | PW_API_TOKEN env / data/.env | ACTIVE |
| AUTH-002 | auth | Session cookie (pw_session) | INDIRECT | AuthManager via auth_routes | `auth.py::AuthManager/SessionStore`, `auth_routes.py` | STORE-004 | STORE-004 | login_local/login_oidc | UI-011, OIDC | session cookie | data/sessions.json | ACTIVE (resolved by require_auth via resolve_session_principal, api.py:262-271; D1–D3) |
| AUTH-003 | auth | OIDC | INDIRECT | /api/auth/oidc/* | `auth.py::OIDCConfig`, `auth_routes.py::auth_oidc_*` | CFG-007, client_secret env | STORE-004 | token/userinfo endpoints | UI-011 | OIDC | external IdP | ACTIVE (maps to Principal; session gates API; D1–D3) |
| AUTH-004 | auth | require_step_up | INDIRECT | `Depends(require_step_up)` | `api.py::require_step_up/_step_up_authorized` | AUTH-001, request client/X-PW-StepUp | none | AUTH-001 | world writes, prefs, apps, sections, journal supersede, identity, reminders, sc refresh, connections writes | bearer + step-up | loopback/private/header logic | ACTIVE |
| AUTH-005 | auth | Loopback/private-peer elevation | INDIRECT | `_step_up_authorized` / vault GET check | `api.py` | peer address | none | ipaddress classification | AUTH-004, API-064 | internal | peer IP | ACTIVE |
| AUTH-006 | lifecycle | Boot-token reconciliation | INDIRECT | `create_app` start | `api.py::_reconcile_boot_token` | STORE-010 | process env | none | create_app | N/A | data/.env wins over compose env | ACTIVE |
| AUTH-007 | auth | Admin gate | INDIRECT | `_is_admin` | `api.py::_is_admin` | IDENT-001 | none | principal scopes | API-068..API-070 | principal admin scope | users.json + bootstrap primary | ACTIVE |
| AUTH-008 | auth | Session step-up (grant) | INDIRECT | POST /api/auth/step-up | `auth_routes.py::auth_step_up`, `auth.py::grant_step_up` | STORE-004 | STORE-004 (step_up_until) | — | UI-018 | session | sessions.json | ACTIVE (consumed by require_step_up; principal-bound; D1–D3) |

## Identity

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IDENT-001 | identity | Principal | INDIRECT | resolve_principal | `identity.py::Principal` | — | — | — | AUTH-001, API | N/A | derived per request | ACTIVE |
| IDENT-002 | identity | IdentityStore | INDIRECT | IdentityStore(data_dir) | `identity.py::IdentityStore` | STORE-005 | STORE-005 | load/save | AUTH-001, API-068..074, AUTH-007 | internal | users.json | ACTIVE |
| IDENT-003 | identity | resolve_principal (single/multi) | INDIRECT | `resolve_principal(token, store, mode, token)` | `identity.py::resolve_principal` | env PW_IDENTITY_MODE, STORE-005 | none | IdentityStore | AUTH-001 | internal | mode env + users.json | ACTIVE |
| IDENT-004 | identity | Person provisioning | INDIRECT | API-068..070 | `identity.py::create_user/attach_token/disable_user` | — | STORE-005 | — | API-069/070 | admin + step-up | users.json | ACTIVE |
| IDENT-005 | identity | Agent principals (owned agents) | INDIRECT | API-071/072 | `identity.py::create_agent/disable_agent` | — | STORE-005 | — | API-071/072 | step-up + ownership | users.json | ACTIVE |
| IDENT-006 | identity | Scopes (read/write/journal/apps) | INDIRECT | Principal.scopes | `identity.py`, `api.py::agents_create ALLOWED` | — | — | — | person-only gate (_require_person) | internal | identity.py | ACTIVE |
| IDENT-007 | identity | Per-user paths (multi mode) | INDIRECT | `User` model | `user.py::User/UserManager` | STORE-005 | per-user dirs | — | api.py::_user_paths | internal | derived per user root | PARTIAL (world/journal per-user; vault/apps/reminders remain instance-level) |

## Domain / world

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DOMAIN-001 | domain | World container | NO | load_world/save_world | `world.py::World`, `app.py::load_world/save_world` | STORE-001 | STORE-001 | mutation gates | everything | internal | world.json | ACTIVE |
| WORLD-001 | domain | Fact | NO | World.record_fact | `world.py::record_fact`, `model.py::Fact` | — | in-memory→STORE-001 | policy check | loop, API-076, TOOL-026 | internal | world.json | ACTIVE |
| WORLD-002 | domain | Intent | NO | World.set_intent | `world.py::set_intent`, `model.py::Intent` | — | in-memory→STORE-001 | policy check | API-075, TOOL-025 | internal | world.json | ACTIVE |
| WORLD-003 | domain | Policy + cement | INDIRECT | World.set_policy/cement | `world.py::set_policy/cement/check_policy`, `model.py::Policy` | — | in-memory→STORE-001 | MutationDenied | API-076, CLI-009 | explicit user act only | world.json | ACTIVE |
| WORLD-004 | domain | Lore | INDIRECT | World.add_lore/promote_lore | `world.py`, `model.py::Lore` | — | in-memory→STORE-001 | promotion gate | packs, chat context | internal (promotion = human act) | world.json | ACTIVE |
| WORLD-005 | domain | Capability | NO | registry.define_capability | `providers/registry.py::Registry.define_capability`, `app.py::STANDARD_CAPABILITIES` | — | in-memory→STORE-001 | — | build_registry | internal | app.py list | ACTIVE |
| WORLD-006 | domain | Provider registration | NO | Registry.register | `providers/registry.py::Registry.register` | connections | in-memory→STORE-001 | — | build_registry | internal | registry (derived) | ACTIVE |
| WORLD-007 | domain | Pack | INDIRECT | World.install_pack/uninstall_pack | `world.py`, `model.py::Pack` | pack manifest | in-memory→STORE-001 | policies install | CLI/init flows | explicit act | world.json | PARTIAL (install machinery, no live pack catalog UI) |
| DOMAIN-002 | domain | Daily loop | INDIRECT | daily() / POST /api/daily / CLI daily | `loop.py::daily` | DOMAIN-001, DOMAIN-007 | STORE-001, JOURNAL-001 | OBSERVE→VALIDATE→RECONCILE→DISCOVER→POLICY→JOURNAL→PRESENT | API-004, CLI-002 | require_auth (API) | world.json/journal | ACTIVE |
| DOMAIN-003 | domain | Framework validation | INDIRECT | CLI-016 | `framework.py::validate_connections/validate_compose_file/validate_settings_export/validate_participant_packs` | STORE-014, compose, exports | none | — | CI, CLI | none | rules in framework.py | ACTIVE |
| DOMAIN-004 | domain | Reconciliation engine | INDIRECT | NativeSettingsReconciler | `providers/native_reconciler.py` | CFG-009 | none (propose only) | — | API-058..060, TOOL-012/013/028 | internal | CFG-009 | ACTIVE |
| DOMAIN-005 | domain | Observation (StatusContract.observe) | NO | provider.observe() | `providers/registry.py::StatusContract` | provider targets | none | — | status_map, actors | internal | provider response | ACTIVE |
| DOMAIN-006 | domain | Policy application / MutationDenied | NO | World.check_policy | `world.py::MutationDenied` | WORLD-003 | none | — | all mutations | internal | world.json | ACTIVE |
| DOMAIN-007 | domain | Provider Registry | NO | Registry() | `providers/registry.py::Registry` | — | in-memory | observe/status | every route rebuilds | internal | derived only (per-request) | ACTIVE |
| DOMAIN-008 | domain | Sections/layout | INDIRECT | sections_mod | `sections.py::SECTIONS/resolve_sections/validate_layout_update` | world.json layout | world.json layout | — | API-032, UI-014 | step-up (write) | world.json layout | ACTIVE |
| DOMAIN-005b | — | (merged into DOMAIN-005) | — | — | — | — | — | — | — | — | — | — |

## Journal / evidence

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| JOURNAL-001 | journal | Journal append (record/append) | INDIRECT | Journal.record | `journal.py::Journal.record/append` | — | STORE-002 | — | everything | internal | journal.ndjson | ACTIVE |
| JOURNAL-002 | journal | Journal read (recent/current/by_ts/events/search) | INDIRECT | Journal.recent/by_ts/events/current_events | `journal.py` | STORE-002 | none | — | API-005/008, CLI-003, TOOLS | internal | journal.ndjson | ACTIVE |
| JOURNAL-003 | journal | Supersede (append-only correction) | INDIRECT | Journal.supersede | `journal.py::supersede/history_of/current_events` | STORE-002 | STORE-002 | — | API-007, UI-006, chat drafts | step-up | journal.ndjson | ACTIVE |
| JOURNAL-004 | journal | Story rendering | INDIRECT | StoryRenderer | `journal.py::StoryRenderer` | STORE-002 | none | — | CLI-007, API-027 | internal | derived only | ACTIVE |
| JOURNAL-005 | journal | Audit rendering | INDIRECT | AuditRenderer | `journal.py::AuditRenderer` | STORE-002 | none | — | API-009 | internal | derived only | ACTIVE |
| JOURNAL-006 | journal | Classification (JournalKind) | NO | model.JournalKind | `model.py::JournalKind` | — | — | — | record callers | internal | model.py enum | ACTIVE |
| JOURNAL-007 | journal | Provenance (source/observed_at) | NO | model.Provenance | `model.py::Provenance` | — | — | — | all events/facts | internal | model.py | ACTIVE |
| JOURNAL-008 | journal | Memory/FTS bridge | INDIRECT | NativeMemoryProvider | `providers/native_memory.py::index_journal/search` | STORE-002 | STORE-012 | — | API-016, PROV-007 | internal | derived only | ACTIVE |

## Brain / tools (registered set)

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TOOL-000 | tool | ToolRegistry (container) | NO | build_default_tools | `tool_registry.py::ToolRegistry/build_default_tools` | — | — | all TOOL-* | API-010, API-013 | internal | in-memory | ACTIVE |
| TOOL-001 | tool | inspect_world_status | INDIRECT | read tool | `tool_registry.py` (world/status) | DOMAIN-001 | none | world.summary() | chat tool loop | internal | world.json | ACTIVE |
| TOOL-002 | tool | inspect_manifest | INDIRECT | read | `tool_registry.py` | DOMAIN-007 | none | registry.manifest() | chat tool loop | internal | registry | ACTIVE |
| TOOL-003 | tool | read_journal | INDIRECT | read | `tool_registry.py::_read_journal` | JOURNAL-002 | none | journal.recent | chat tool loop | internal | journal.ndjson | ACTIVE |
| TOOL-004 | tool | search_journal | INDIRECT | read | `tool_registry.py::_search_journal` | JOURNAL-002 | none | journal.search | chat tool loop | internal | journal.ndjson | ACTIVE |
| TOOL-005 | tool | inspect_source_control | INDIRECT | read | `tool_registry.py::_source_control_status` | PROV-001 | none | status_all | chat tool loop | internal | git repos | ACTIVE |
| TOOL-006 | tool | inspect_source_control_history | INDIRECT | read | `tool_registry.py` | PROV-001 | none | repository_history | chat tool loop | internal | git repos | ACTIVE |
| TOOL-007 | tool | inspect_projects | INDIRECT | read | `tool_registry.py::_projects_status` | PROV-026 | none | AgentSyncProjectSensor | chat tool loop | internal | agent-sync | ACTIVE |
| TOOL-008 | tool | inspect_lab_inventory | INDIRECT | read | `tool_registry.py::_lab_inventory` | PROV-012 | none | NativeLabInventory | chat tool loop | internal | system | ACTIVE |
| TOOL-009 | tool | inspect_lab_health | INDIRECT | read | `tool_registry.py::_lab_health` | PROV-012 | none | NativeLabHealth | chat tool loop | internal | derived | ACTIVE |
| TOOL-010 | tool | inspect_lab_resources | INDIRECT | read | `tool_registry.py::_lab_resources` | PROV-012 | none | NativeLabResources | chat tool loop | internal | system | ACTIVE |
| TOOL-011 | tool | inspect_lab_settings | INDIRECT | read | `tool_registry.py::_lab_settings` | PROV-012 | none | NativeLabSettings | chat tool loop | internal | native lab | ACTIVE |
| TOOL-012 | tool | inspect_reconciler_status | INDIRECT | read | `tool_registry.py::_reconciler_status` | PROV-014 | none | reconciler.observe | chat tool loop | internal | CFG-009 | ACTIVE |
| TOOL-013 | tool | inspect_reconciler_diff | INDIRECT | read (desired-only fallback) | `tool_registry.py::_reconciler_diff` | PROV-014 | none | reconciler._desired | chat tool loop | internal | CFG-009 | PARTIAL (no observed-state diff) |
| TOOL-014 | tool | inspect_discovery_status | INDIRECT | read | `tool_registry.py::_discovery_status` | PROV-013 | none | discovery.observe | chat tool loop | internal | CFG-008 | ACTIVE |
| TOOL-015 | tool | list_discovery_sources | INDIRECT | read | `tool_registry.py` | PROV-013 | none | discovery.observe | chat tool loop | internal | CFG-008 | ACTIVE |
| TOOL-016 | tool | list_interests | INDIRECT | read | `tool_registry.py` | PROV-013 | none | discovery.observe | chat tool loop | internal | CFG-008 | ACTIVE |
| TOOL-017 | tool | run_discovery | INDIRECT | read-labeled fetch | `tool_registry.py::_discovery_discover` | PROV-013 | CFG-008 (saves/feedback) | discovery.discover | chat tool loop | internal | CFG-008 | ACTIVE |
| TOOL-018 | tool | inspect_vault_status | INDIRECT | read (never values) | `tool_registry.py::_vault_status` | STORE-003 lock state | none | vault.is_unlocked | chat tool loop | internal | vault.enc | ACTIVE |
| TOOL-019 | tool | inspect_reminders | INDIRECT | read (via wired Scheduler) | `tool_registry.py::_reminders` | STORE-006 | none | Scheduler.list_reminders | chat tool loop | internal | reminders.json | ACTIVE (no longer a parallel file read; D1–D3) |
| TOOL-020 | tool | inspect_media_status | INDIRECT | read | `tool_registry.py::_media_status` | PROV-015 | none | engine.status | chat tool loop | internal | media adapters | ACTIVE |
| TOOL-021 | tool | inspect_media_recent | INDIRECT | read | `tool_registry.py` | PROV-015 | none | engine.recent | chat tool loop | internal | media adapters | ACTIVE |
| TOOL-022 | tool | inspect_media_activity | INDIRECT | read | `tool_registry.py` | PROV-015 | none | engine.activity | chat tool loop | internal | media adapters | ACTIVE |
| TOOL-023 | tool | search_media | INDIRECT | read | `tool_registry.py::_media_search` | PROV-015 | none | engine.search | chat tool loop | internal | media adapters | ACTIVE |
| TOOL-024 | tool | propose_journal_entry | INDIRECT | write proposal | `tool_registry.py::_propose_journal_write` | — | durable proposal store | _proposals | chat tool loop | owner approval required | data/proposals.json | ACTIVE |
| TOOL-025 | tool | propose_world_intent | INDIRECT | write proposal | `tool_registry.py::_propose_world_intent` | — | durable proposal store | _proposals | chat tool loop | owner approval required | data/proposals.json | ACTIVE |
| TOOL-026 | tool | propose_world_fact | INDIRECT | write proposal | `tool_registry.py::_propose_world_fact` | — | durable proposal store | _proposals | chat tool loop | owner approval required | data/proposals.json | ACTIVE |
| TOOL-027 | tool | propose_reminder | INDIRECT | write proposal | `tool_registry.py::_propose_reminder` | — | durable proposal store | _proposals | chat tool loop | owner approval required | data/proposals.json | ACTIVE (executor persists via Scheduler; D1–D3) |
| TOOL-028 | tool | propose_reconciler_apply | INDIRECT | write proposal | `tool_registry.py::_propose_reconciler_apply` | PROV-014 desired | durable proposal store | reconciler.desired_state | chat tool loop | owner approval required | data/proposals.json | PARTIAL (executor returns honest unsupported; D1–D3) |
| TOOL-029 | tool | execute_approved_write | INDIRECT | write executor | `tool_registry.py::_execute_approved_write` | proposals.json | JOURNAL-001, STORE-001 (intent/fact), STORE-006 (reminder) | journal.record/save_world/Scheduler.add | step-up API only | server-held approval (`status==approved`) | data/proposals.json | ACTIVE (model cannot invoke; D1–D3) |

Note: the mission brief said 26 tools; the code registers 29 (read count above). Repository truth wins.

## Chat

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CHAT-001 | chat | /api/chat endpoint + tool loop | INDIRECT | POST /api/chat | `api.py::chat`, `_chat_with_tools_loop` | DOMAIN-001, JOURNAL-002 | JOURNAL-001, proposals | CHAT-004/005/006/008, TOOL-000 | UI-008 | require_auth | provider + world.json | ACTIVE |
| CHAT-002 | chat | chat.py provider builder | INDIRECT | `chat.py::build_chat_provider` | `chat.py:270` | connections dict | none | OllamaChat/OpenAICompatChat | none found (app.py imports chat_registry) | internal | connections | ORPHAN (superseded by CHAT-002b) |
| CHAT-002 | chat | chat_registry.py provider builder | INDIRECT | `chat_registry.py::build_chat_provider` | `chat_registry.py:463` | connections dict | none | Ollama/OpenAICompat/OpenAI/Anthropic/OpenCode | app.py build_registry | internal | connections | ACTIVE |
| CHAT-003 | chat | OllamaChat (chat.py) | INDIRECT | chat.py class | `chat.py::OllamaChat` | ollama /api | none | urllib | CHAT-002 | internal | provider response | PARTIAL (second copy) |
| CHAT-004 | chat | OllamaChat (chat_registry.py) | INDIRECT | chat_registry class | `chat_registry.py::OllamaChat` | ollama api | none | urllib | CHAT-002 | internal | provider response | ACTIVE |
| CHAT-005 | chat | OpenAICompatChat (chat.py / registry) | INDIRECT | both builders | `chat.py:181`, `chat_registry.py:81` | openai-compatible | none | urllib | CHAT-002 | internal | provider response | ACTIVE (two copies — see DUPLICATES) |
| CHAT-006 | chat | OpenAIChat | INDIRECT | `chat_registry.py::OpenAIChat` | `chat_registry.py:171` | api.openai.com | none | urllib, api_key_env | CHAT-002 | internal | provider response | ACTIVE |
| CHAT-007 | chat | AnthropicChat | INDIRECT | `chat_registry.py::AnthropicChat` | `chat_registry.py:246` | anthropic messages | none | urllib, api_key_env | CHAT-002 | internal | provider response | ACTIVE |
| CHAT-008 | chat | OpenCodeChat (CLI subprocess) | INDIRECT | `chat_registry.py::OpenCodeChat` | `chat_registry.py:358` | opencode CLI | none | subprocess opencode run | CHAT-002 | internal | subprocess | ACTIVE |
| CHAT-009 | chat | World context construction | INDIRECT | `build_world_context` | `chat_context.py::build_world_context` | DOMAIN-001, JOURNAL-002, DOMAIN-007, PROV-026, PROV-001 | none | — | API-010 | internal | derived only | ACTIVE |
| CHAT-010 | chat | UI context construction | INDIRECT | `build_ui_context` | `chat_context.py::build_ui_context` | sections spec, route | none | — | API-010 | internal | provenance only | ACTIVE |
| CHAT-011 | chat | Tool injection (schemas) | INDIRECT | `list_ollama_schemas` | `tool_registry.py`, `api.py::chat` | TOOL-000 | none | — | API-010 | internal | in-memory | ACTIVE |
| CHAT-012 | chat | History handling | INDIRECT | `build_chat_messages` (last 6) | `chat.py::build_chat_messages`, `api.py::chat` | request history | none | — | API-010 | internal | request body only (not persisted) | ACTIVE |
| CHAT-013 | chat | Proposal extraction (journal correction) | INDIRECT | `extract_proposal` | `chat.py::extract_proposal`, `api.py::chat` validation | JOURNAL-002 | proposals | by_ts validation | UI-020 | internal | validated vs journal | ACTIVE |
| CHAT-014 | chat | Provider testing (probe) | INDIRECT | POST /api/chat/test | `api.py::chat_test`, `chat.py::chat_once` | reasoning provider | none | chat_once | UI-009 | require_auth | provider response | ACTIVE |
| CHAT-015 | chat | Brain templates (TemplateRegistry) | INDIRECT | `TemplateRegistry(config_dir, data_dir)` | `template_registry.py` | CFG-011 (config/prompts), STORE-013/014 overrides | none | compose(surface) | API-010, API-077 | internal | config/prompts | ACTIVE |

## Capabilities / providers / connections

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CAP-001 | domain | source_control | NO | STANDARD_CAPABILITIES | `app.py:45` | — | — | — | registry | N/A | app.py | ACTIVE |
| CAP-002 | domain | deployment | NO | STANDARD_CAPABILITIES | `app.py:46` | — | — | — | registry | N/A | app.py | ACTIVE |
| CAP-003 | domain | secrets | NO | STANDARD_CAPABILITIES | `app.py:47` | — | — | — | registry | N/A | app.py | ACTIVE |
| CAP-004 | domain | calendar | NO | STANDARD_CAPABILITIES | `app.py:48` | — | — | — | registry | N/A | app.py | ACTIVE |
| CAP-005 | domain | discovery | NO | STANDARD_CAPABILITIES | `app.py:49` | — | — | — | registry | N/A | app.py | ACTIVE |
| CAP-006 | domain | settings_validation | NO | STANDARD_CAPABILITIES | `app.py:50` | — | — | — | registry | N/A | app.py | ACTIVE |
| CAP-007 | domain | service_validation | NO | STANDARD_CAPABILITIES | `app.py:51` | — | — | — | registry | N/A | app.py | ACTIVE |
| CAP-008 | domain | update_discovery | NO | STANDARD_CAPABILITIES | `app.py:52` | — | — | — | registry | N/A | app.py | ACTIVE |
| CAP-009 | domain | memory | NO | STANDARD_CAPABILITIES | `app.py:53` | — | — | — | registry | N/A | app.py | ACTIVE |
| CAP-010 | domain | journal | NO | STANDARD_CAPABILITIES | `app.py:54` | — | — | — | registry | N/A | app.py | ACTIVE |
| CAP-011 | domain | reasoning | NO | STANDARD_CAPABILITIES | `app.py:55` | — | — | — | registry/chat | N/A | app.py | ACTIVE |
| CAP-012 | domain | notifications | NO | STANDARD_CAPABILITIES | `app.py:56` | — | — | — | registry | N/A | app.py | ACTIVE |
| CAP-013 | domain | scheduler | NO | STANDARD_CAPABILITIES | `app.py:57` | — | — | — | registry (no provider registered) | N/A | app.py | PARTIAL |
| CAP-014 | domain | homelab_settings | NO | STANDARD_CAPABILITIES | `app.py:58` | — | — | — | lab_api connection | N/A | app.py | ACTIVE |
| CAP-015 | domain | homelab_health | NO | STANDARD_CAPABILITIES | `app.py:59` | — | — | — | lab_api/native-lab | N/A | app.py | ACTIVE |
| CAP-016 | domain | homelab_deploy | NO | STANDARD_CAPABILITIES | `app.py:60` | — | — | — | lab_api | N/A | app.py | ACTIVE |
| CAP-017 | domain | homelab_secrets | NO | STANDARD_CAPABILITIES | `app.py:61` | — | — | — | lab_api | N/A | app.py | ACTIVE |
| CAP-018 | domain | homelab_resources | NO | STANDARD_CAPABILITIES | `app.py:62` | — | — | — | lab_api/native-lab | N/A | app.py | ACTIVE |
| CAP-019 | domain | ingress | NO | build_registry traefik | `app.py:198-211` | — | — | — | API-078 | N/A | app.py | ACTIVE (not in STANDARD list) |
| CAP-020 | domain | service_inventory | NO | native_lab registration | `app.py:352-356` | — | — | — | native-lab API | N/A | app.py | ACTIVE (not in STANDARD list) |
| CAP-021 | domain | service_health | NO | native_lab registration | `app.py:357-361` | — | — | — | — | N/A | app.py | ACTIVE (not in STANDARD list) |
| CAP-022 | domain | resource_monitoring | NO | native_lab registration | `app.py:362-371` | — | — | — | — | N/A | app.py | ACTIVE (not in STANDARD list) |
| CAP-023 | domain | media | NO | provider_schemas only | `provider_schemas.py::CAPABILITY_SCHEMAS["media"]` | — | — | — | UI-003, API-053..057, TOOL-020..023 | N/A | provider_schemas | PARTIAL (bypasses main registry — dedicated engine) |
| CAP-024 | domain | auth (schema pseudo-capability) | INDIRECT | CAPABILITY_SCHEMAS["auth"] | `provider_schemas.py` | STORE-017 | none | — | UI-021 overview | N/A | provider_schemas | PARTIAL (vocabulary only) |
| PROV-001 | provider | NativeGit | INDIRECT | build_registry zero-provider boot | `source_control.py::NativeGit` | git repos | none (read-only) | git subprocess | registry, CLI-013..015, API-033/034 | internal | external repos | ACTIVE |
| PROV-002 | provider | Gitea (forge HTTP adapter) | INDIRECT | connections type=gitea | `providers/adapters.py::Gitea` | forge API, token_env | none | HTTP | registry (enrichment slot) | internal | forge | PARTIAL (substitution-proof machinery; no live default) |
| PROV-003 | provider | FakeSourceControl | INDIRECT | connections type=fake_source_control | `providers/adapters.py` | none | none | — | substitution tests | internal | deterministic fake | INTERNAL |
| PROV-004 | provider | GitHubEnrichment (gh CLI) | INDIRECT | /api/source-control/enrichment | `providers/github.py::GitHubEnrichment` | gh session | none | gh subprocess | API-036 | internal | GitHub via gh | ACTIVE |
| PROV-005 | provider | LangGraphMemory | INDIRECT | connections type=langgraph | `providers/adapters.py` | base_url, api_key_env | none | HTTP | registry memory slot | internal | external service | PARTIAL (alternate memory provider) |
| PROV-006 | provider | NativeVaultProvider | INDIRECT | build_registry (vault present) | `providers/native_vault.py` | STORE-003 | none | vault.health | registry secrets slot | internal | vault.enc | ACTIVE |
| PROV-007 | provider | NativeMemoryProvider | INDIRECT | build_registry always | `providers/native_memory.py` | STORE-002, STORE-012 | STORE-012 | sqlite fts5 | API-016, registry | internal | derived FTS | ACTIVE |
| PROV-008 | provider | NativeCalendarProvider | INDIRECT | build_registry always | `providers/native_calendar.py` | CFG-003 calendar config, ICS sources | none | HTTP | registry | internal | external ICS | ACTIVE |
| PROV-009 | provider | NativeNotificationsProvider | INDIRECT | build_registry always | `providers/native_notifications.py` | CFG-003 notifications | none | webhook/ntfy send | registry; no current send caller | internal | CFG-003 | ACTIVE (observe), send path currently uncalled |
| PROV-009a | — | (WebhookAdapter/NtfyAdapter) | — | `native_notifications.py` | — | — | send POST | — | PROV-009 | — | — | ACTIVE |
| PROV-009b | — | (GitHubReleasesAdapter/VersionUrlAdapter) | — | `providers/native_updates.py` | — | release URLs | none | HTTP | PROV-010 | — | external | ACTIVE |
| PROV-010 | provider | NativeUpdatesProvider | INDIRECT | build_registry always | `providers/native_updates.py` | CFG-004 updates config | none | adapters | registry update_discovery | internal | CFG-004 | ACTIVE |
| PROV-011 | provider | NativeDeploymentProvider | INDIRECT | build_registry always | `providers/native_deployment.py` | CFG-005 deployment config | none | compose/systemd adapters | registry deployment | internal | CFG-005 | PARTIAL (status only; no deploy caller) |
| PROV-011a | — | DockerComposeAdapter / SystemdAdapter | — | `native_deployment.py` | — | compose file / systemctl | none | subprocess | PROV-011 | — | external | PARTIAL |
| PROV-012 | provider | NativeLab (Inventory/Health/Settings/Resources) | INDIRECT | connections type=native_lab + direct instantiation | `providers/native_lab.py` | system files | none | observation | API-045..048, TOOLS | internal | system observation | ACTIVE |
| PROV-013 | provider | NativeDiscovery | INDIRECT | connections type=native_discovery + direct instantiation | `providers/native_discovery.py::NativeDiscovery` | CFG-008, RSS/API sources | CFG-008 | HTTP | API-049..052, TOOLS | internal | CFG-008 | ACTIVE |
| PROV-014 | provider | NativeSettingsReconciler | INDIRECT | direct instantiation everywhere | `providers/native_reconciler.py` | CFG-009 | none (apply is note-only) | — | API-058..060, TOOLS | internal | CFG-009 | PARTIAL (no apply path) |
| PROV-015 | provider | NativeMediaEngine + Plex/Sonarr/Radarr/Lidarr adapters | INDIRECT | `_build_media_engine` in api.py + tool_registry | `providers/native_media.py` | CONN-002 media entries | none | HTTP (X-Plex-Token / X-Api-Key) | API-053..057, TOOLS | internal | provider APIs | ACTIVE (bypasses Registry) |
| PROV-016 | provider | LabSettings (lab CLI) | INDIRECT | lab_api connection + /api/lab/settings | `providers/lab_settings.py` | lab CLI packet | none | subprocess | API-038..040 | internal | external lab | ACTIVE |
| PROV-017 | provider | LabHealth | INDIRECT | lab_api connection | `providers/lab_health.py` | lab CLI | none | subprocess | API-041 | internal | external lab | ACTIVE |
| PROV-018 | provider | LabDeploy | INDIRECT | lab_api connection | `providers/lab_deploy.py` | lab CLI | none | subprocess | API-042 | internal | external lab | ACTIVE |
| PROV-019 | provider | LabSecrets | INDIRECT | lab_api connection | `providers/lab_secrets.py` | lab CLI (names only) | none | subprocess | API-043 | internal | external lab | ACTIVE |
| PROV-020 | provider | LabResources | INDIRECT | lab_api connection | `providers/lab_resources.py` | lab CLI | none | subprocess | API-044 | internal | external lab | ACTIVE |
| PROV-021 | provider | LabState (operator packet) | INDIRECT | /api/lab/state | `providers/lab_state.py::LabState` | PW_LAB_CLI binary | none | subprocess | API-037 | internal | external lab | ACTIVE |
| PROV-022 | provider | TraefikIngress | INDIRECT | build_registry always | `providers/traefik_ingress.py` | Traefik API base_url | none | HTTP | API-078 | internal | external Traefik | ACTIVE |
| PROV-023 | provider | HttpStatus probe | INDIRECT | connections type=http_status | `providers/adapters.py::HttpStatus` | URL probe | none | HTTP | registry | internal | probe result | ACTIVE |
| PROV-024 | provider | CandyDispenser | INDIRECT | connections type=candy | `providers/adapters.py::CandyDispenser` | base_url | none | HTTP | registry (demo) | internal | external demo service | INTERNAL |
| PROV-026 | provider | AgentSyncProjectSensor | INDIRECT | /api/projects/status, TOOL-007 | `providers/agent_sync.py::AgentSyncProjectSensor` | agent-sync binary output | none | subprocess | API-079, TOOL-007 | internal | agent-sync subprocess | ACTIVE |
| PROV-027 | provider | ComposeUpdateProvider | INDIRECT | CLI-018 build_provider | `updates.py::ComposeUpdateProvider` | compose file, docker | compose file image tags | docker compose | CLI updates apply/rollback | internal | compose project | ACTIVE |
| PROV-028 | provider | FakeUpdateProvider | INDIRECT | CLI updates --provider fake | `updates.py::FakeUpdateProvider` | — | simulated | — | tests | internal | deterministic | INTERNAL |
| PROV-029 | provider | SopsBroker | INDIRECT | adapters.py | `providers/adapters.py::SopsBroker` | SOPS bundle | none | pipe-to-consumer | (no current caller) | internal | external SOPS | ORPHAN |
| PROV-030 | provider | SOPSVaultAdapter | INDIRECT | vault.py | `vault.py::SOPSVaultAdapter` | sops file | none (set/delete unsupported) | sops subprocess | no current caller | internal | external SOPS | ORPHAN |
| PROV-031 | provider | ChatProviderRegistry (runtime switching) | INDIRECT | chat_registry.py | `chat_registry.py::ChatProviderRegistry` | providers | none | — | none found | internal | in-memory | ORPHAN (class exists; API uses Registry.provider_for) |
| CONN-001 | config | Connections overview (schemas+status merge) | INDIRECT | /api/connections/overview | `api.py::connections_overview` | CONN-002, provider_schemas, registry | none | — | UI-021 | require_auth | merged | ACTIVE |
| CONN-002 | config | Connections config manager | INDIRECT | ConnectionManager | `connection_manager.py` | STORE-014, STORE-015 | STORE-015 (writes go local) | — | API-019..024 | step-up (writes) | connections.json + local | ACTIVE |
| CONN-003 | config | Capability schema registry (native configs) | INDIRECT | provider_schemas + api test/validate | `provider_schemas.py` | — | — | — | API-017..024 | internal | provider_schemas.py | ACTIVE |

## Storage

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| STORE-001 | store | data/world.json | INDIRECT | load_world/save_world | `app.py` | — | save_world, CLI init | — | everything | internal | authoritative | ACTIVE |
| STORE-002 | store | data/journal.ndjson | INDIRECT | Journal(path) | `journal.py` | — | JOURNAL-001 | — | journal+memory | internal | authoritative (append-only) | ACTIVE |
| STORE-003 | store | data/vault.enc | INDIRECT | Vault(path) | `vault.py::Vault` | — | unlock/set/delete | — | vault API | bearer + unlocked | authoritative | ACTIVE |
| STORE-004 | store | data/sessions.json | INDIRECT | SessionStore._load/_save | `auth.py::SessionStore` | — | create/invalidate/step-up | — | AUTH-002 | internal | authoritative (sessions) | ACTIVE |
| STORE-005 | store | data/users.json | INDIRECT | IdentityStore.path | `identity.py::IdentityStore` | — | create/attach/disable | — | identity admin | internal | authoritative (multi-mode) | ACTIVE |
| STORE-006 | store | data/reminders.json | INDIRECT | Scheduler path | `scheduler.py`, API-067, TOOL-019 | — | Scheduler add/remove/toggle | — | API-067, TOOL-019 | internal | authoritative | ACTIVE |
| STORE-007 | store | data/apps.json | INDIRECT | apps routes | `api.py::apps_list/apps_put` | — | PUT /api/apps | — | apps API | internal | authoritative | ACTIVE |
| STORE-008 | store | data/updates-session.json | INDIRECT | UpdateManager session_path | `updates.py::_load_session/_save_session` | — | apply/rollback journaling | — | API-029, CLI-018 | internal | authoritative (update state) | ACTIVE |
| STORE-009 | store | data/setup-complete marker | INDIRECT | healthz/setup | `api.py` | — | POST /api/setup | — | setup gate | internal | authoritative (first-run) | ACTIVE |
| STORE-010 | store | data/.env (PW_API_TOKEN) | INDIRECT | POST /api/setup, _reconcile_boot_token | `api.py` | AUTH-006 | POST /api/setup | — | boot reconciliation | internal | authoritative (setup token wins) | ACTIVE |
| STORE-012 | store | data/memory.fts5.db | INDIRECT | NativeMemoryProvider._db_path | `providers/native_memory.py` | — | index_journal | — | API-016 | internal | derived (rebuildable) | ACTIVE |
| STORE-013 | store | data/theme-packs/ | INDIRECT | ThemePackRegistry | `theme_pack.py` | — | none (read-only runtime) | — | API-065 | internal | authoritative manifests | PARTIAL (list/get only; not wired into UI theming) |
| STORE-014 | store | config/connections.json | INDIRECT | build_registry, ConnectionManager | `app.py`, `connection_manager.py` | — | manual editing | — | provider wiring | internal | authoritative (tracked, no secrets) | ACTIVE |
| STORE-015 | store | config/connections.local.json | INDIRECT | build_registry merge, ConnectionManager._write_local | `app.py:158-175`, `connection_manager.py` | — | connection writes | — | CONN-002 | internal | authoritative overrides (private) | ACTIVE (merge divergence on rollup endpoint — API-080) |
| STORE-016 | store | config/prompts (+ prompts.local) | INDIRECT | TemplateRegistry | `template_registry.py::_load_shipped/_load_overrides` | — | none | — | CHAT-015 | internal | authoritative (shipped) + overrides | ACTIVE |
| STORE-017 | store | config/oidc.json | INDIRECT | AuthManager._load_config | `auth.py` | — | manual | — | AUTH-003 | internal | authoritative (client_secret via env) | ACTIVE |
| STORE-018 | store | ~/.config/personal-world/discovery.json | INDIRECT | NativeDiscovery.config_path | `providers/native_discovery.py:122` | — | add_source/add_interest | — | PROV-013 | internal | authoritative (external home config) | ACTIVE |
| STORE-019 | store | ~/.config/personal-world/reconciler/desired/ | INDIRECT | NativeSettingsReconciler | `providers/native_reconciler.py:100` | — | none (manual YAML/JSON) | — | PROV-014 | internal | authoritative (desired state) | ACTIVE |
| STORE-020 | store | data/executions.json | INDIRECT | ExecutionStore | `execution_viewer.py::ExecutionStore` | — | append/update | — | (no current caller) | internal | derived | ORPHAN |
| STORE-021 | store | per-user dirs (multi mode) | INDIRECT | user.py::User paths | `user.py` | — | per-user world/journal | — | _user_paths | internal | derived per person | PARTIAL |

## Secrets

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SECRET-001 | auth | Native Vault | INDIRECT | Vault(path) in create_app | `vault.py::Vault` | STORE-003 | STORE-003 | — | vault API | bearer + passphrase | vault.enc | ACTIVE |
| SECRET-002 | store | vault.enc | NO | Vault._save | `vault.py` | — | — | — | SECRET-001 | internal | authoritative | ACTIVE |
| SECRET-003 | integration | Fernet/PBKDF2 crypto path | NO | `_derive_key` (cryptography extra) | `vault.py::_derive_key` | passphrase | — | — | Vault unlock | internal | optional dependency | ACTIVE (fails closed without the extra — no base64 fallback) |
| SECRET-004 | provider | SOPS scaffold (SopsBroker) | NO | adapters.py | `providers/adapters.py::SopsBroker` | sops bundle | none | sops subprocess | none | internal | external SOPS | ORPHAN |
| SECRET-005 | provider | SOPSVaultAdapter (read-through) | INDIRECT | vault.py | `vault.py::SOPSVaultAdapter` | sops file | none (write unsupported) | sops | none | internal | external SOPS | ORPHAN |
| SECRET-006 | config | Environment secret loading (api_key_env/token_env) | NO | connection entries | `chat_registry.py`, `adapters.py::Gitea/LangGraphMemory` | env vars | none | — | provider construction | internal | process env | ACTIVE |
| SECRET-007 | config | OIDC client secret env | INDIRECT | auth callback | `auth_routes.py::auth_oidc_callback` | `os.environ[client_secret_env]` | none | — | AUTH-003 | internal | env | ACTIVE |
| SECRET-008 | config | PW_API_TOKEN (instance bearer) | INDIRECT | _token() | `api.py::_token` | env, STORE-010 | STORE-010 (setup) | — | AUTH-001, AUTH-002 | internal | data/.env wins at boot | ACTIVE |

## Integrations / external

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INT-001 | integration | agent-sync subprocess | INDIRECT | AgentSyncProjectSensor | `providers/agent_sync.py::_sync_binary/_run_all` | binary stdout | none | subprocess | PROV-026 | internal | external binary | ACTIVE |
| INT-002 | integration | gh CLI subprocess | INDIRECT | GitHubEnrichment | `providers/github.py::_api` | gh auth session | none | subprocess | PROV-004 | internal | external gh | ACTIVE |
| INT-003 | integration | lab CLI subprocess | INDIRECT | LabState/Lab* providers | `providers/lab_state.py::_fetch` | PW_LAB_CLI packet | none | subprocess | API-037..044 | internal | external binary | ACTIVE |
| INT-004 | integration | opencode CLI subprocess | INDIRECT | OpenCodeChat | `chat_registry.py::OpenCodeChat` | CLI stdout | none | subprocess | CHAT-008 | internal | external binary | ACTIVE |
| INT-005 | integration | git subprocess boundary | INDIRECT | source_control._git | `source_control.py::_git` | repo state | none | subprocess | PROV-001 | internal | external git | ACTIVE |
| INT-006 | integration | OIDC token/userinfo exchange | INDIRECT | auth callback | `auth_routes.py` | IdP endpoints | none | HTTPS POST/GET | AUTH-003 | OIDC client secret | external IdP | ACTIVE |
| INT-007 | integration | RSS/API discovery fetch | INDIRECT | NativeDiscovery._discover_* | `providers/native_discovery.py` | feed URLs | none | HTTP | PROV-013 | internal | external feeds | ACTIVE |
| INT-008 | integration | Connection test probes | INDIRECT | _test_adapter | `api.py::_test_adapter` | external endpoints | none | urllib | API-023/024 | require_auth | live probe | ACTIVE |

## Lifecycle

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LIFE-001 | lifecycle | create_app | NO | uvicorn factory | `api.py::create_app` | STORE-001..017 | app.state | build_registry, AuthManager, Scheduler | deployment | internal | — | ACTIVE |
| LIFE-002 | lifecycle | build_registry | NO | create_app/_state per request | `app.py::build_registry` | STORE-014/015 | registry in-memory | all provider registrations | every route | internal | connections config | ACTIVE |
| LIFE-003 | lifecycle | lifespan (scheduler start/stop) | NO | app.router.lifespan_context | `api.py::lifespan` | — | — | Scheduler.start/stop | FastAPI | internal | — | ACTIVE |
| LIFE-004 | lifecycle | Scheduler thread | NO | _reminders.start | `scheduler.py::check_and_fire` | STORE-006 | STORE-006, JOURNAL-001 (fire) | Journal | LIFE-003 | internal | reminders.json | ACTIVE |
| LIFE-005 | lifecycle | Boot-token reconciliation | INDIRECT | create_app first | `api.py::_reconcile_boot_token` | STORE-010 | env | — | create_app | internal | data/.env | ACTIVE (=AUTH-006) |
| LIFE-006 | lifecycle | init_world (zero-provider init) | INDIRECT | CLI-010 | `init.py::init_world` | — | STORE-001, JOURNAL-001 | — | CLI init, recovery | none | zero-provider defaults | ACTIVE |
| LIFE-007 | lifecycle | Shutdown | NO | lifespan exit | `api.py::lifespan` | — | — | Scheduler.stop | uvicorn | internal | — | ACTIVE |
| LIFE-008 | lifecycle | Memory index construction | NO | NativeMemoryProvider init/index | `providers/native_memory.py::index_journal` | STORE-002 | STORE-012 | — | PROV-007 | internal | derived | ACTIVE |
| LIFE-009 | lifecycle | Per-request world load | NO | _state/_state_for | `api.py` | STORE-001 | none (world loaded fresh each request) | build_registry | all routes | internal | world.json | ACTIVE (no persistent in-process world cache) |

## Deployment

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEPLOY-001 | deployment | compose.yaml (portable appliance) | INDIRECT | docker compose up | `compose.yaml` | PW_IMAGE/PW_API_TOKEN | volumes world-data/ollama-data | core+ollama+ollama-pull | operators | env token | compose.yaml | ACTIVE |
| DEPLOY-002 | deployment | compose.dev.yaml | INDIRECT | compose override | `compose.dev.yaml` | source tree | none | build . | developers | none | source | ACTIVE |
| DEPLOY-003 | deployment | compose.homelab.yaml | INDIRECT | compose override | `compose.homelab.yaml` | /homelab, kilo auth mounts | none | PW_LAB_CLI | owner host | none | host paths (non-portable) | ACTIVE |
| DEPLOY-004 | deployment | Dockerfile | INDIRECT | docker build | `Dockerfile` | uv.lock | image | uv sync --extra crypto | DEPLOY-001/002 | none | Dockerfile | ACTIVE |
| DEPLOY-005 | deployment | GHCR image | INDIRECT | ghcr.io/rylee-bee/personal-world | `compose.yaml:86`, `.github/workflows/publish-image.yml` | — | — | — | compose default | none | GHCR | ACTIVE |
| DEPLOY-006 | deployment | Vite dev proxy | INDIRECT | npm run dev | `frontend/vite.config.ts::proxy` | — | none | /api → local server | developers | none | vite.config.ts | ACTIVE |
| DEPLOY-007 | deployment | reverse proxy assumption | INDIRECT | deployment layer (Authelia/forward-auth) | docs/OPERATIONS.md, AUTH-005 | X-PW-StepUp header | none | — | external proxy | external | deployment topology | PARTIAL |
| DEPLOY-008 | deployment | uvicorn local | INDIRECT | `uv run personal-world` server / uvicorn | `pyproject.toml` script entry | — | none | create_app | developers | none | pyproject | ACTIVE |

## Tests / contracts / docs

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TEST-001 | test | pytest backend suite | INDIRECT | `uv run pytest --timeout=30` | `tests/` | all source | tmp dirs | — | CI validate.yml | none | code | ACTIVE |
| TEST-002 | test | Vitest frontend suite | INDIRECT | `cd frontend && npx vitest` | `frontend/src/test/*.spec.*` | components | none | jsdom | CI | none | code | ACTIVE |
| TEST-003 | test | Playwright e2e | INDIRECT | `npx playwright test` | `frontend/e2e/*.spec.ts` | running app | screenshots | — | CI validate.yml | none | code | ACTIVE |
| TEST-004 | test | dist safety gate | INDIRECT | tests/test_dist_safety.py | `tests/test_dist_safety.py` | frontend dist, api.py | none | — | CI (separate step) | none | code | ACTIVE |
| TEST-005 | test | framework validation gate | INDIRECT | CLI-016/017 | `tests/test_framework.py` | config | none | — | CI | none | framework.py | ACTIVE |
| TEST-006 | test | public safety gate | INDIRECT | tests/test_public_safety.py | `tests/test_public_safety.py` | tracked files | none | secret scanning | CI | none | SECURITY.md | ACTIVE |
| TEST-007 | test | safe-commit guard | INDIRECT | scripts/safe-commit.sh | `scripts/safe-commit.sh`, `tests/test_safe_commit.py` | git status | commits | pytest | agents | none | script | ACTIVE |
| TEST-007a | — | accessibility/prefs parity tests | INDIRECT | `tests/test_prefs_schema_parity.py`, `frontend/src/test/*` | `tests/`, `frontend/src/test/` | schema | none | — | CI | none | code | ACTIVE |
| DOC-001 | documentation | AGENT_POLICY.md | INDIRECT | repo root | `AGENT_POLICY.md` | — | — | — | agents | N/A | canonical policy | ACTIVE |
| DOC-002 | documentation | AGENT_CONTRACTS.md (index) | INDIRECT | repo root | `AGENT_CONTRACTS.md` | — | — | — | agents | N/A | canonical index | ACTIVE |
| DOC-002a | documentation | .project/CURRENT.md | INDIRECT | .project/CURRENT.md | `.project/CURRENT.md` | — | — | — | agents | N/A | canonical current-state pointer | ACTIVE |
| DOC-003 | documentation | docs/ARCHITECTURE.md | INDIRECT | docs | `docs/ARCHITECTURE.md` | — | — | — | reviewers | N/A | architecture truth | ACTIVE |
| DOC-004 | documentation | docs/NATIVE-BASELINE-AND-ENRICHMENT.md | INDIRECT | docs | `docs/NATIVE-BASELINE-AND-ENRICHMENT.md` | — | — | — | CLI-016 | N/A | normative world model | ACTIVE |
| DOC-005 | documentation | docs/PERSONAL-WORLD-FINISH-LINE.md | INDIRECT | docs | `docs/PERSONAL-WORLD-FINISH-LINE.md` | — | — | — | planning | N/A | target state | ACTIVE |
| DOC-006 | documentation | docs/accessibility/ACCESSIBILITY_CONTRACT.md | INDIRECT | docs/accessibility | `docs/accessibility/` (4 canonical files) | — | — | — | UI work | N/A | a11y truth | ACTIVE |
| DOC-007 | documentation | SECURITY.md | INDIRECT | repo root | `SECURITY.md` | — | — | — | TEST-006 | N/A | security contract | ACTIVE |
| DOC-007 | documentation | Figma implementation skill | INDIRECT | .agents/skills/personal-world-implement-figma/SKILL.md | same | contracts | none | — | UI agents | N/A | skill file | ACTIVE |
| DOC-008 | documentation | design/handoff (archived Workshop v3 spec) | INDIRECT | design/handoff/ | `design/handoff/FRAME_INDEX.md` etc. | — | none (never edit) | — | design reference | N/A | archived (historical) | HIDDEN |
| DOC-008a | documentation | design/tokens.json + docs/history/DESIGN-HANDOFF.md | INDIRECT | design | `design/tokens.json` | — | — | — | frontend gen-tokens | N/A | canonical design tokens | ACTIVE |
| DOC-008b | documentation | .project/contracts/adoption.yaml (Play-Nice) | INDIRECT | .project/contracts/adoption.yaml | `.project/contracts/adoption.yaml` | — | — | — | contract loading | N/A | pinned revision (v0.6.0 @ 0cee065) | ACTIVE |

## Assets

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ASSET-001 | asset | Companion SVGs (5) | INDIRECT | /companions/{name}.svg | `api.py::companion_svg`, `src/personal_world/static/companions/` | files | none | — | UI-016, wizard | public | design/assets/companions (byte-identical copies) | ACTIVE |
| ASSET-002 | asset | Icon sprite (72 glyphs) | INDIRECT | /icons/sprite.svg | `api.py::icon_sprite`, `static/icons/sprite.svg` | file | none | — | frontend icons | public | design/assets/icons | ACTIVE |
| ASSET-003 | asset | Webfonts (Young Serif, Instrument Sans) | INDIRECT | /fonts/{name} | `api.py::webfont`, `static/fonts/` | files | none | — | tokens.css | public | Figma export (OFL) | ACTIVE |
| ASSET-004 | asset | Today art (settle-gesture, waves-ladder) | INDIRECT | /today/{name}.svg | `api.py::today_art`, `static/today/` | files | none | — | UI-001 | public | design/assets/today | ACTIVE |
| ASSET-005 | asset | Mermaid master lottie | NO | media_files/designs/personal-world/mermaid-companion-master.lottie | `design/assets/` | — | none (byte-identical by decision) | — | none (animation master, not runtime-served) | N/A | deliberate artwork | HIDDEN |
| ASSET-006 | asset | Theme packs (data/theme-packs) | INDIRECT | ThemePackRegistry | `theme_pack.py` | STORE-013 | none | — | API-065 | internal | manifests | PARTIAL |
| ASSET-007 | asset | Companion source rigs (design-owned) | INDIRECT | design/assets/companions/* | `design/assets/companions/` | — | none (deliberate artwork) | — | ASSET-001 derivation | N/A | design assets | HIDDEN |
| ASSET-007a | — | ThemePack default companion paths (/static/companions/*) | — | `theme_pack.py:58-62` | — | — | — | — | — | N/A | legacy path prefix | ORPHAN (no /static/ route in current api.py) |

## Accessibility / preferences

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A11Y-001 | config | Preferences model (PREFS: motion, contrast, text_scale, density, target_size, companion, accent) | INDIRECT | `prefs.py::PREFS` | `prefs.py:149` | STORE-001 accessibility | world.json (API-030) | — | API-030/031, CLI-012 | step-up (write) | world.json | ACTIVE |
| A11Y-002 | config | Preferences API | INDIRECT | API-030/031 | `api.py::prefs_*` | A11Y-001 | STORE-001 | — | UI-009 | step-up (write) | world.json | ACTIVE |
| A11Y-003 | config | Preferences schema floor | INDIRECT | docs/accessibility/PREFERENCES_SCHEMA.json | `docs/accessibility/PREFERENCES_SCHEMA.json`, `prefs.py` | — | — | — | TEST-007a | N/A | docs schema + prefs.py (parity tested) | ACTIVE |
| A11Y-004 | config | Prefs context (frontend) | INDIRECT | PrefsProvider | `frontend/src/lib/prefs-context.tsx` | API-030 | localStorage pw_token only (not prefs) | applyPrefsToDocument | App bootstrap | client | server prefs | ACTIVE |
| A11Y-005 | config | CSS data attributes (data-pw-*) | INDIRECT | applyPrefsToDocument | `prefs-context.tsx`, `index.css` | — | DOM attrs | — | all styles | client | prefs-context | ACTIVE |
| A11Y-006 | config | Reduced-motion handling | INDIRECT | data-pw-motion + --pw-motion-* | `prefs-context.tsx`, `index.css` | A11Y-001 | — | — | CSS | client | prefs.py (motion enum; OS prefers-reduced-motion respected in CSS) | ACTIVE |
| A11Y-007 | config | Target-size floor (44px) | INDIRECT | data-pw-target-size | `prefs-context.tsx:107` | A11Y-001 | — | — | CSS | client | Math.max floor | ACTIVE |
| A11Y-008 | config | Contrast / focus ring | INDIRECT | data-pw-contrast | `prefs-context.tsx` | A11Y-001 | — | — | CSS tokens | client | prefs.py | ACTIVE |
| A11Y-009 | config | Density / text scale | INDIRECT | data-pw-density, data-pw-text-scale | `prefs-context.tsx` | A11Y-001 | — | — | CSS | client | prefs.py | ACTIVE |
| A11Y-010 | config | Theme value (dark default) | INDIRECT | data-pw-theme | `prefs-context.tsx:92` | A11Y-001 | — | — | tokens.css | client | prefs.py | ACTIVE |
| A11Y-010a | — | StatusChip vocabulary enforcement | INDIRECT | StatusChip primitive | `frontend/src/primitives/StatusChip.tsx`, `src/personal_world/status.py` | — | — | — | all screens | client | status.py (authority) | ACTIVE |
| A11Y-011 | config | Companion vocabulary (COMPANION enum + frontend COMPANIONS map) | INDIRECT | prefs.py COMPANION / companion-context | `prefs.py:134-140`, `companion-context.tsx:61-68` | — | world.json | — | UI-010, UI-016 | step-up (pref write) | prefs.py (canonical slugs) | ACTIVE |

## Companion surface

| ID | Kind | Name | Human? | Entry point | Source location | Reads | Writes | Calls | Called by | Auth | Source of truth | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| COMP-001 | screen | World Keeper (default companion) | YES | prefs accent/companion defaults | `prefs.py::ACCENT/COMPANION`, `docs` WORLD_KEEPER spec | — | — | — | UI-016 | client | design spec | ACTIVE |
| COMP-002 | screen | Companion state machine (six semantic states) | INDIRECT | theme_pack.CompanionStates | `theme_pack.py::CompanionStates` | — | — | — | ASSET-006 | internal | theme packs | PARTIAL (state machine defined; runtime resolution limited to default pack) |