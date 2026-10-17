# ORPHAN / SUPERSEDED INDEX — Worlds

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** orphan / superseded / intentional-headless surfaces · **Read this if:** you found code with no caller and want to know whether it is dead, deliberate, or already resolved

**In short:** A dated index of surfaces with no live caller (orphans), surfaces kept on purpose (internal/archived), and findings from the 2026-09-15/16 audits that were later fixed. Reality only; nothing here is a to-do list.

**Note (2026-09-26):** line numbers (`api.py:NNN`, `tool_registry.py:NNN`) are from
the 2026-09-15/16/17 passes and may have drifted — find the named symbol instead.
Rows naming the deleted `frontend/` or `station/` tree describe the retired
pre-flip UI; today's interface is `ui/`.

| ID | Surface | State | Evidence | Confidence |
|---|---|---|---|---|
| CHAT-002 (A) | chat.py::build_chat_provider | ORPHAN | app.py imports build_chat_provider from chat_registry, not chat.py; grep shows no caller of chat.py's builder | HIGH |
| PROV-031 | ChatProviderRegistry class (chat_registry.py) | ORPHAN | Defined; no import/caller found (chat flows use Registry.provider_for) | HIGH |
| PROV-029 | SopsBroker | ORPHAN | Implemented pipe-to-consumer path; no registration or caller | HIGH |
| PROV-030 | SOPSVaultAdapter | ORPHAN | Read-through adapter; set/delete unsupported; no caller found | HIGH |
| STORE-020 | data/executions.json (ExecutionViewer/ExecutionStore) | ORPHAN | Wired in build_registry but no route/tool caller found | HIGH |
| ASSET-007a | ThemePack default paths /static/companions/*.svg | ORPHAN | theme_pack.py defaults use /static/companions; api.py serves /companions/{name}.svg only (no /static route) | HIGH |
| AUTH-008 | Session step-up grant (POST /api/auth/step-up → step_up_until) | RESOLVED (D1–D3) | require_step_up consumes the principal-bound grant (api.py:143-175, auth.py:31-42) | HIGH |
| AUTH-002/003 | Session cookie + OIDC as API gate | RESOLVED (D1–D3) | require_auth resolves bearer OR session to one Principal (api.py:211-276) | HIGH |
| API-065 | Themes API | PARTIAL | GET /api/themes(/{name}) implemented; no frontend consumer found | MEDIUM |
| STORE-013 | data/theme-packs runtime integration | PARTIAL | Registry reads manifests; ARCHITECTURE.md says "not full frontend pack integration" | HIGH |
| TOOL-027 | propose_reminder executor | RESOLVED (D1–D3) | Executor persists via wired `Scheduler.add` (tool_registry.py:799-817) | HIGH |
| TOOL-028 | propose_reconciler_apply executor | PARTIAL (labelled) | Returns `unsupported`, leaves proposal `pending`, applies nothing (tool_registry.py:819-830) — no fake success | HIGH |
| TOOL-013 | inspect_reconciler_diff | PARTIAL | Returns desired state only; "Observed state not available for diff" | HIGH |
| TOOL-029 | execute_approved_write approval semantics | RESOLVED (D1–D3) | Requires durable `status == "approved"`; approval server-held via step-up API; no model-supplied boolean (tool_registry.py:722-885, api.py:979-1004) | HIGH |
| PROV-011 | NativeDeploymentProvider (compose/systemd adapters) | PARTIAL | Registered; status/observe only; no live deploy caller | MEDIUM |
| PROV-009 (send) | NativeNotificationsProvider.send (webhook/ntfy) | PARTIAL | Provider registered and observed; no current send() caller in api/cli/tools | MEDIUM |
| CAP-013 | scheduler capability (no provider registered) | PARTIAL | Capability defined; Scheduler used directly, not via capability | HIGH |
| UI-023 | "interface not built" page | INTERNAL | Deliberate, labelled missing state when the `ui/` build is absent from the image (`station_ui.py`); no legacy fallback | HIGH |
| PROV-024 | CandyDispenser | INTERNAL | Demo/reference provider behind explicit connections type=candy | HIGH |
| PROV-003 | FakeSourceControl | INTERNAL | Substitution-proof machinery for tests | HIGH |
| PROV-028 | FakeUpdateProvider | INTERNAL | Update state-machine reference for tests | HIGH |
| API-080 | source-control rollups | REMOVED | `/api/source-control/rollups` no longer exists; search paths still read connections.json directly (source_control.py:283,311) | MEDIUM |
| NAV-002 | /setup-wizard alias | ACTIVE (alias) | Intentional legacy alias Navigate→/setup (T15 cutover) | HIGH |
| DOC-008 | design/handoff package | HIDDEN | Archived spec; never edit (AGENT_CONTRACTS rule) | HIGH |
| ASSET-005 | Mermaid master .lottie | HIDDEN | Deliberate artwork, byte-identical by decision; not runtime-served | HIGH |
| PROV-002 | Gitea forge adapter | PARTIAL | Retained as substitution-proof machinery; not a supported live provider (ARCHITECTURE.md) | HIGH |
| CHAT-005 (copies) | OpenAICompatChat in both chat.py and chat_registry.py | PARTIAL | Two class copies; registry copy live | HIGH |
| TOOL-019 | inspect_reminders | RESOLVED (D1–D3) | Now reads through a wired Scheduler; no raw file scrape (tool_registry.py:1154-1168) | HIGH |
| A11Y-003 | Design preference schema (motion beyond reduced) | PARTIAL | Schema richer than prefs.py accepts; default agrees (ARCHITECTURE.md recorded boundary) | HIGH |
| API-012 | /api/chat/test | ACTIVE | Was unauthenticated per older docs; current code has require_auth | HIGH (code) |

Entries from the 2026-09-16 full surface audit
(`.project/HANDOFF-SURFACE-AUDIT-2026-09-16.md`). State vocabulary here
distinguishes **bugs** from **intentional headless surfaces** and
**archived material**; nothing below reclassifies deliberate CLI
duplication, admin APIs, archived Station material, or protected
artwork as dead.

| ID | Surface | State | Evidence | Confidence |
|---|---|---|---|---|
| TOOL-030 | inspect_source_control_history (tool_registry.py:1346) | **BUG — FIXED 2026-09-17** | Imported nonexistent `from .source_control import history`; tool raised at every invocation. Fixed to reuse `repository_history` with repo-name→path resolution (same shape as `/api/source-control/history`, api.py:1680). Regression tests: `tests/test_source_control.py::TestHistoryToolRegression` | HIGH |
| NEW-001 (bug) | Public-safety: private topology in tracked files | **BUG — FIXED 2026-09-17** | `.project/CURRENT.md` and `docs/AUTHELIA-CLIENT-SNIPPET.md` carried an operator hostname + RFC1918 IP (violates SECURITY.md; exact values not restated here). Redacted preserving meaning; `tests/test_public_safety.py` markers now pass over tracked files | HIGH |
| STATION-001 | Companion chat is localStorage-only (`station/chat.js`) | UNWIRED PRODUCT SURFACE (acknowledged in code, chat.js:9-11) | Backend `/api/chat*` + `/api/brain/templates` are live, tested, UI never calls them. From Station UI the backend exposes ~110 routes; Station calls 15. Deliberate target for a separate wiring lane | HIGH |
| STATION-002 | Station write flows absent (prefs save, sections, reminders CRUD, journal write/supersede, proposal actions) | UNWIRED PRODUCT SURFACE | Endpoints exist + step-up gated; Station is read-only/local. `chat.js` warning captions describe the intended binding | HIGH |
| STATION-003 | localStorage prefs not synced to API-065 | UNWIRED PRODUCT SURFACE (documented mapping at station.js:4-9) | Deliberate prototype seam, not dead | HIGH |
| ASSET-008 | Station shipped webfonts (`static/fonts/`: instrument-sans, young-serif) | ORPHAN (station UI) | No `@font-face` user anywhere in served Station CSS; `station.css:52-54` uses system stacks | HIGH |
| API-000a | `/api/setup` legacy vs `/api/setup-wizard/*` | DUP (deliberate coexistence) | Two first-run paths; legacy kept for older clients | HIGH |
| API-000b | `/api/connections/validate` = alias of `/test` | DUP | Pure alias (api.py:1299-1307); consolidation candidate | HIGH |
| API-000c | `/api/chat/history` missing from curated manifest table | GAP (truth) | Route live (api.py:944) but not in curated rows of api_manifest.py | HIGH |
| ~~STORE-020~~ | executions.json / ExecutionViewer | ORPHAN (as listed) | Also recorded in `.project/HANDOFF-SURFACE-AUDIT-2026-09-16.md` | HIGH |

Not listed as dead merely for lacking a frontend consumer: identity
admin APIs (API-068..074), themes API (API-065), updates API
(API-029), memory search (API-016) — these have API consumers,
CLI parity, tests, or are deliberate headless surfaces.