# Worlds vnext — inventory: ownership, live consumers, disposition

> **Status:** survey (read-only) · **Date:** 2026-10-13 · **Packet:** s0-inventory (#312, #319, #321) · **Scope:** `src/personal_world/worlds/*`, `src/personal_world/providers/*`, `ui/src/fd/*`, `ui/src/generated/*`, `tests/`, and the route registrations with their importers/consumers. **Deliverable:** this file only — no `src/`, `ui/`, `tests/`, config or existing-doc edits.

**In short:** The tree carries **two machine models side by side**. The front door (ADR-0008) is `src/personal_world/worlds/*` served by `worlds.production:app_from_env` and rendered by `ui/src/fd/*`; it imports none of `providers/*`. The 2026-09 capability-registry application (`app.py`, `api.py`, `providers/*`, the retired UI) is still tracked and still has live consumers — but not from the front door. Every row below names its `path:line`, its live consumer, its preservation test, and a keep / adapt / replace / retire / unknown call.

---

## Decisions in force (quoted, not paraphrased)

- 2026-10-13 Rylee: "Not yet. Wanna get it cleaned up first then we design." then "Ok do add the api and visuals. Hah" — cleanup runs first; design and contract work run beside it.
- 2026-10-13 Rylee: "Queue all but offload the work you can so we can use it for benchmarks"
- 2026-10-13 issue #319: "Classify current implementation, with source-linked evidence" into FRONT_DOOR_CORE / EXPLICIT CORE EXCEPTION / PROVIDER_ADAPTER / EXTERNAL_AUTHORITY / LEGACY, and "name live consumers and preservation tests before changes."
- 2026-10-13 issue #321: "The current implementation is evidence and optional reusable code, not a mandatory design or API structure." and "Preserve legacy code until dependency/rollback evidence allows removal."

Related standing records: [ADR-0008](../adr/0008-front-door.md) (front door; the capability registry is retired for front-door providers), [ADR-0001](../adr/0001-capabilities-core-owned-providers-optional.md) (capabilities core-owned; amended by 0008), [ADR-0009](../adr/0009-play-nice-semantic-kernel.md) and the [kernel plan](../rebuild/PLAY-NICE-KERNEL-PLAN.md) (deletion-first rebuild; Phase 0 is this inventory), [CONTRACTS.md](../rebuild/CONTRACTS.md) (C1–C9).

## How the classes are used here

The five class names are the ones issue #319 names. This survey reads them as:

| Class | Meaning used below |
|---|---|
| **FRONT_DOOR_CORE** | Part of the front-door machine ADR-0008 owns: `worlds/*`, `ui/src/fd/*`, `ui/src/generated/*`. |
| **EXPLICIT CORE EXCEPTION** | Core-owned behaviour the front door depends on that deliberately lives *outside* `worlds/`, or a built-in contract ADR-0001/0008 explicitly excepts from provider retirement (identity, notifications/PWA, the framework gate, the vault). |
| **PROVIDER_ADAPTER** | Code whose job is to translate a foreign or native system into Worlds (or Worlds into it). Foreign/vendor words must stop here. |
| **EXTERNAL_AUTHORITY** | An external system is the authoritative source; Worlds observes or records, never re-derives. |
| **LEGACY** | The pre-ADR-0008 application and retired machinery. Preserved per #321 until dependency **and** rollback evidence allows removal; its live consumer must be named. |

Disposition vocabulary per row: **keep** (stays as core), **adapt** (stays but must be reworked into the vnext shape), **replace** (superseded by another module), **retire** (remove once its named consumers and preservation evidence are settled), **unknown** (no design decision yet; the owner's 2026-10-13 "design later" applies).

The kernel plan's vocabulary maps as FRONT_DOOR_CORE≈WORLDS, PROVIDER_ADAPTER≈ADAPTER, LEGACY≈HISTORICAL, `generated/*`≈DERIVED; PLAY_NICE and UNKNOWN have no exact one-to-one here and are called out where they occur.

---

## 1. Two machine models in one tree (the ownership split)

| Fact | Evidence |
|---|---|
| Production boots the **front door only** | `Dockerfile:92` → `uvicorn personal_world.worlds.production:app_from_env --factory`; assembly at `src/personal_world/worlds/production.py:55` (`create_app`) |
| The front door builds from `worlds/*` and `..oidc` + `..push` | `src/personal_world/worlds/production.py:19`–`36` (all imports); `worlds/server.py:122` (`build_app`) |
| The 2026-09 app is a **separate** FastAPI app | `src/personal_world/api.py:548` (`create_app`), `:5974` (`app.include_router(app_router(...))`); registry assembled at `src/personal_world/app.py:153` (`build_registry`) |
| The front door never imports `providers/*` | No `worlds/**` file imports `personal_world.providers` (only `..oidc`, `..push` leave the package — `worlds/production.py:19`, `worlds/production.py:20`, `worlds/push_routes.py:15`) |
| The framework gate is designed to survive deletion of the old app | `src/personal_world/framework.py:26`–`28`: "It imports only `personal_world.worlds.*` … The old `personal_world.{app,model,world,init,journal,providers,api,auth,identity,chat,vault}` modules are never imported here" |
| The old UI is deleted except a query provider | `docs/rebuild/foreman/old-ui-delete-list.txt:1` lists `ui/src/app/App.tsx` … as deleted; only `ui/src/app/QueryProvider.tsx` and `ui/src/data/queryClient.ts` remain, mounted at `ui/src/main.tsx:5` |

**Consequence for classification:** a `providers/*` module has no front-door consumer. Its live consumers are the legacy application modules and the legacy tests; that is what makes it LEGACY/PROVIDER_ADAPTER rather than FRONT_DOOR_CORE.

---

## 2. Front-door backend core — `src/personal_world/worlds/*`

31 modules (30 + `__init__`). Class is FRONT_DOOR_CORE unless the row says otherwise.

| Module (`path:line`) | What it is | Live consumer (evidence) | Preservation test | Call |
|---|---|---|---|---|
| `src/personal_world/worlds/__init__.py:1` | Package marker: "Front-door rebuild core: config files, mapping, runner, cards (contracts C1-C5)." | Implicit in every `.worlds` import; no direct importer | — | keep |
| `src/personal_world/worlds/server.py:122` | `build_app`: read front door (C6) + config CRUD (C1) + public `/healthz` (`:157`); boards `:164`, cards `:177`, needs-you `:187`, config `:194`–`:283` | `worlds/production.py:35`; `worlds/dev.py:45`; `framework.py:277` | `tests/worlds/test_api.py:8`; `tests/worlds/test_review_fixes.py:14` | keep |
| `src/personal_world/worlds/models.py:1` | C1 config models, `canonical_json`, `action_version` | `config_store.py`, `cards.py`, `dispatcher.py:36`, `confinement.py`, `recipes.py`, `connect_routes.py`, `room0.py`, `seed.py`, `framework.py:45` | `tests/worlds/test_models.py:4` | keep |
| `src/personal_world/worlds/config_store.py:1` | C1 YAML store: schema, refs, etags, atomic write | `server.py:45`; `production.py:86`; `recipes.py`; `dispatcher.py:33`; `connect_routes.py`; `room0.py`; `seed.py`; `framework.py:44` | `tests/worlds/test_config_store.py:7` | keep |
| `src/personal_world/worlds/cards.py:1` | C2 result envelope + `home_board_defs` (display only) | `server.py:44`; `connect_routes.py`; `runner.py` | `tests/worlds/test_cards.py`; `tests/worlds/test_meter.py:5` | keep |
| `src/personal_world/worlds/mapping.py:1` | Strict JSONPath subset + value formats; no code execution | `models.py`; `suggest.py:9` | `tests/worlds/test_mapping.py` | keep |
| `src/personal_world/worlds/templates.py:1` | C1.3 query templates (`{today}`, `{now}`, closed set) | `models.py`; `confinement.py` | `tests/worlds/test_templates.py:7` | keep |
| `src/personal_world/worlds/runner.py:1` | C2 fetch seam: cache, last-good, single-flight, classification, redaction | `server.py:48`; `dispatcher.py:37`; `cards.py` | `tests/worlds/test_runner.py:13` | keep |
| `src/personal_world/worlds/confinement.py:1` | The **only** outbound sender: resolve→pin, address-class deny, no redirects/retries, caps | `server.py:47`; `runner.py`; `dispatcher.py:34`; `room0.py`; `reference_provider.py`; `connect_routes.py`; `companion.py`; `dev.py` | `tests/worlds/test_confinement.py:11`; `tests/worlds/test_confinement_auth.py:21` | keep |
| `src/personal_world/worlds/secrets.py:27` | `secret_ref` resolution (`env:`/`vault:`/`file:`); `set_vault` seam at `:21` | `production.py:34`; `owner.py:30`; `connect_routes.py:31`; `companion.py` | `tests/worlds/test_confinement.py:10` (vault); `tests/worlds/test_companion.py:17` | keep — vault wiring is **unknown** (§11) |
| `src/personal_world/worlds/db.py:44` | `worlds.db` SQLite: WAL, `BEGIN IMMEDIATE` `write_tx`, ordered migrations | `production.py:26`; `dispatcher.py:35`; `memory_store.py`; `authn.py`; `framework.py:377`; `cli.py:107` | `tests/worlds/test_memory_store.py:10`; `tests/worlds/test_room0.py:16` | keep |
| `src/personal_world/worlds/dispatcher.py:150` | C3 authority: authorizations, durable single dispatch, receipts, recovery | `production.py:27`; `actions_routes.py`; `room_routes.py` | `tests/worlds/test_dispatcher.py`; `tests/worlds/test_authority_followups.py` | keep |
| `src/personal_world/worlds/authn.py:1` | Sessions, agent tokens, CSRF, fail-closed principals; "no development bypass" | `production.py:23`; every route module; `dev.py:38` | `tests/worlds/test_authn.py`; `tests/worlds/test_room0.py:13` | keep |
| `src/personal_world/worlds/owner.py:1` | `owner.yaml` policy (public_origin, OIDC, bootstrap), `strong_secret` | `production.py:30`; `auth_routes.py` | `tests/worlds/test_auth_routes.py:24` | keep |
| `src/personal_world/worlds/auth_routes.py:162` | Sign-in/sign-out/step-up/session routes; redirect URI from `public_origin` only | `production.py:22`; registered `:130` | `tests/worlds/test_auth_routes.py:9` | keep |
| `src/personal_world/worlds/actions_routes.py:39` | `/api/actions`, approvals, receipts, agent tokens over the Dispatcher | `production.py:21`; registered `:131` | `tests/worlds/test_dispatcher.py`; `tests/worlds/test_authority_followups.py` | keep |
| `src/personal_world/worlds/memory_store.py:1` | C4 Kept/Later/Records/History/Find + backup/restore (the Memory baseline) | `production.py:29`; `memory_routes.py`; `db.py:120`; `framework.py:378`; `cli.py:108`, `cli.py:138` | `tests/worlds/test_memory_store.py:11` | keep |
| `src/personal_world/worlds/memory_routes.py:23` | C4 HTTP routes (owner-only, step-up for locked, scoped agent read) | `production.py:28`; registered `:134`; `dev.py:41` | `tests/worlds/test_memory_routes.py` | keep |
| `src/personal_world/worlds/connect_routes.py:60` | C9 Connect workshop API (`/api/connect/try`, `/api/connect/preview`) | `production.py:25`; registered `:135`; `dev.py:39` | `tests/worlds/test_connect.py:12` | keep |
| `src/personal_world/worlds/suggest.py:1` | Connect sample scrubbing + field suggestion (pure) | `connect_routes.py` | `tests/worlds/test_connect.py:14` | keep |
| `src/personal_world/worlds/recipes.py:1` | Recipe templates: install, validate, `from_openapi` skeleton | `framework.py:46`; `tests/recipes/*` | `tests/worlds/test_room_recipes.py:6`; `tests/recipes/test_recipes.py:17` | keep |
| `src/personal_world/worlds/room0.py:1` | **Adapter**: a room/0 room → Worlds cards/needs/action candidates | `production.py:32`; `room_routes.py:13` | `tests/worlds/test_room0.py:20` | keep — room/0 "continues unchanged" (ADR-0008 consequences) |
| `src/personal_world/worlds/room_routes.py:16` | Owner-only room/0 routes (adopt, answer, changed) | `production.py:33`; registered `:138` | `tests/worlds/test_room0.py` | keep |
| `src/personal_world/worlds/companion.py:1` | **Adapter/connector**: confined, whitelisting proxy to the private Companion service | `companion_routes.py:17` | `tests/worlds/test_companion.py` | keep |
| `src/personal_world/worlds/companion_routes.py:25` | `/api/companion/*` owner-only proxy routes | `production.py:24`; registered `:139` | `tests/worlds/test_companion.py` | keep |
| `src/personal_world/worlds/push_routes.py:21` | Web Push + notify door + PWA routes; reuses `personal_world.push` as-is | `production.py:31`; registered `:143` | `tests/worlds/test_push_routes.py:7`; `tests/worlds/test_push_production.py` | keep |
| `src/personal_world/worlds/static_routes.py:11` | Serves the built front-door SPA and root-scoped PWA assets (registered last) | `production.py:36`; registered `:145` | `tests/worlds/test_static_routes.py:4` | keep |
| `src/personal_world/worlds/reference_provider.py:1` | In-process reference HTTP server + TEST-ONLY sender | `dev.py:43`; `seed.py` | `tests/worlds/test_reference_provider.py`; `tests/worlds/test_runner.py:12` | keep — test/dev only |
| `src/personal_world/worlds/seed.py:1` | Seeded C1 example config pointing at the reference provider | `dev.py:44` | `tests/worlds/test_meter.py:99`; `tests/worlds/test_api.py:7` | keep — dev only |
| `src/personal_world/worlds/dev.py:1` | DEV-ONLY loopback server: fake principal, test sender, seeded config | `python -m personal_world.worlds.dev` (`dev.py:198`) | `tests/worlds/test_dev.py` | keep — dev only |
| `src/personal_world/worlds/production.py:55` | The **only** production entrypoint: Database + Auth + owner policy + Dispatcher + routes | `Dockerfile:92`; `scripts/gen-openapi.py:23`; `scripts/contract-drift-check.py:1` | `tests/worlds/test_production.py:13`; `tests/worlds/test_push_production.py:12`; `tests/test_dockerfile.py`; `tests/test_compose_env.py` | keep |

## 3. Front-door UI core — `ui/src/fd/*` (34 files)

All FRONT_DOOR_CORE. Mount chain: `ui/src/main.tsx:3` (`FdApp`) inside `PrefsProvider` (`:4`) and `QueryProvider` (`:5`); `FdApp.tsx:2`–`12` imports the four landmarks, shell, decoration and the companion trio.

| Module (`path:line`) | What it is | Live consumer (evidence) | Preservation test | Call |
|---|---|---|---|---|
| `ui/src/fd/FdApp.tsx:1` | Hash routing `#home/#connect/#memory/#settings`; preference attributes; Station decoration | `ui/src/main.tsx:3` | `ui/src/test/fd-screens.test.tsx` | keep |
| `ui/src/fd/Shell.tsx:1` | Skip link, header/nav/main order, rail⇄bottom bar | `FdApp.tsx:8` | `ui/src/test/fd-shell.test.tsx:4` | keep |
| `ui/src/fd/route.ts:1` | Landmark ids + hash parse/format | `FdApp.tsx:6`; `Shell.tsx:2` | `ui/src/test/fd-shell.test.tsx:5` | keep |
| `ui/src/fd/Home.tsx:1` | Home: greeting, briefing, strip, Edit Home, Needs you/look, Your life, Quietly working | `FdApp.tsx:3` | `ui/src/test/fd-home.test.tsx:7` | keep |
| `ui/src/fd/Strip.tsx:1` | Whole-world strip tiles incl. loading tile | `Home.tsx:10` | `ui/src/test/fd-home.test.tsx` | keep |
| `ui/src/fd/Row.tsx:1` | Instrument row with drill-in | `Home.tsx:8` | `ui/src/test/fd-row.test.tsx:5` | keep |
| `ui/src/fd/Meter.tsx:1` | The seven meter types | `Row.tsx:3` | `ui/src/test/fd-row.test.tsx:4` | keep |
| `ui/src/fd/home-model.ts:1` | Grouping rules (C6), briefing, greeting (pure) | `Home.tsx:5` | `ui/src/test/fd-home-model.test.ts:2` | keep |
| `ui/src/fd/api.ts:1` | Read/fetch hooks, CSRF headers, per-request timeouts | `Home.tsx:3`; `Connect.tsx:3`; `Memory.tsx:3`; `Notifications.tsx:3` | `ui/src/test/connect.test.tsx`; `ui/src/test/fd-screens.test.tsx` | keep |
| `ui/src/fd/safe-href.ts:2` | Link allow-list (relative/http/https only) | `Home.tsx:9`; `companion/CompanionPanel.tsx:2` | `ui/src/test/fd-screens.test.tsx` | keep |
| `ui/src/fd/use-board-edit.ts:1` | Edit Home as C1 board writes (`PUT /api/config/board/{id}`, If-Match, 409/422) | `Home.tsx:7` | `ui/src/test/fd-edit-model.test.ts` | keep |
| `ui/src/fd/edit-model.ts:1` | Optimistic overlay for order/visibility/size | `Home.tsx:6`; `use-board-edit.ts:4` | `ui/src/test/fd-edit-model.test.ts:2` | keep |
| `ui/src/fd/Connect.tsx:1` | Connect landmark: providers/requests/cards, try/preview, actions/receipts | `FdApp.tsx:2` | `ui/src/test/fd-screens.test.tsx:7`; `ui/src/test/connect.test.tsx` | keep |
| `ui/src/fd/Memory.tsx:1` | Memory landmark: kept, later, records, find, history | `FdApp.tsx:4` | `ui/src/test/fd-screens.test.tsx:9`; `ui/src/test/memory.test.tsx` | keep |
| `ui/src/fd/Settings.tsx:1` | Settings landmark: preferences + notifications | `FdApp.tsx:7` | `ui/src/test/fd-screens.test.tsx` | keep |
| `ui/src/fd/Tabs.tsx:1` | Accessible tabs (roving tabindex, arrow/Home/End) | `Connect.tsx:13`; `Memory.tsx:15` | `ui/src/test/fd-screens.test.tsx` | keep |
| `ui/src/fd/prefs.tsx:1` | Preferences provider + localStorage persistence | `ui/src/main.tsx:4` | `ui/src/test/fd-screens.test.tsx` | keep |
| `ui/src/fd/prefs-core.ts:1` | Preferences context/defaults (words, density, pack, theme, text) | `FdApp.tsx:5`; `Shell`, `Row`, `PaintedIcon`, `companion/*` | `ui/src/test/fd-screens.test.tsx` | keep |
| `ui/src/fd/types.ts:1` | **Handwritten** C1/C2/C6 UI types | `api.ts:23`; `home-model.ts:2`; `Row.tsx:2`; `Connect.tsx:24`; `Memory.tsx:26`; `companion/types.ts` | `ui/src/test/fd-*.test.*` (via the consumers) | **adapt** — duplicate of the generated contract; kernel plan [PLAY-NICE-KERNEL-PLAN.md](../rebuild/PLAY-NICE-KERNEL-PLAN.md) §Phase 2 |
| `ui/src/fd/fixtures.ts:1` | Typed fixtures (Home board/cards, Memory rows, Connect) | `msw.ts`; `board-server.ts:1`; `fd-*.test.*` | `ui/src/test/fd-home.test.tsx:9` | keep — tests only |
| `ui/src/fd/board-server.ts:1` | In-memory board server with real etag rules | `msw.ts:2` | `ui/src/test/fd-home.test.tsx:8` | keep — tests only |
| `ui/src/fd/msw.ts:1` | MSW handlers for the mocked API | `ui/src/test/fd-home.test.tsx:8`; `fd-screens.test.tsx:8` | same | keep — tests only |
| `ui/src/fd/Notifications.tsx:1` | Device subscription / notify UI in Settings | `Settings.tsx:3` | `ui/src/test/fd-notifications.test.tsx:6` | keep |
| `ui/src/fd/PaintedIcon.tsx:1` | Station-only painted icon; renders nothing with the pack off | `Shell.tsx`; `Row.tsx`; `companion/CompanionButton.tsx:3` | `ui/src/test/fd-painted.test.tsx` | keep |
| `ui/src/fd/StationDecor.tsx:1` | Station decoration only; aria-hidden, layout reserved | `FdApp.tsx:9` | `ui/src/test/fd-shell.test.tsx` | keep |
| `ui/src/fd/time.ts:1` | Clock/relative formatting for rows and history | `Row.tsx:4`; `Memory.tsx:27`; `companion/CompanionPanel.tsx:3` | via consumers | keep |
| `ui/src/fd/companion/CompanionProvider.tsx:1` | Companion state/provider | `FdApp.tsx:12` | `ui/src/test/fd-companion.test.tsx` | keep |
| `ui/src/fd/companion/CompanionPanel.tsx:1` | Companion panel (turns, tiers, grants) | `FdApp.tsx:11` | `ui/src/test/fd-companion.test.tsx` | keep |
| `ui/src/fd/companion/CompanionButton.tsx:1` | Quiet header/rail companion button | `FdApp.tsx:10` | `ui/src/test/fd-companion.test.tsx` | keep |
| `ui/src/fd/companion/api.ts:1` | Companion proxy client + CSRF | `CompanionProvider.tsx:3` | `ui/src/test/fd-companion.test.tsx` | keep |
| `ui/src/fd/companion/companion-core.ts:1` | Companion context/types | `CompanionProvider.tsx:2`; `CompanionPanel.tsx:5`; `CompanionButton.tsx:1` | `ui/src/test/fd-companion.test.tsx` | keep |
| `ui/src/fd/companion/presentation.ts:1` | Worlds' own map presentation/1 → pose/mark | `CompanionProvider.tsx:4`; `CompanionPanel.tsx:6`; `CompanionButton.tsx:2` | `ui/src/test/fd-companion.test.tsx` | keep |
| `ui/src/fd/companion/types.ts:1` | Companion proxy wire types (no address/persona) | `companion/api.ts:1`; `companion/companion-core.ts:3`; `companion/presentation.ts:1` | `ui/src/test/fd-companion.test.tsx` | keep |
| `ui/src/fd/companion-server.ts:1` | Test-only stand-in for `/api/companion/*` | `msw.ts:3` | `ui/src/test/fd-companion.test.tsx` | keep — tests only |

## 4. Generated UI artifacts — `ui/src/generated/*`

**Finding:** the generated tree is produced by the build but has **no live consumer in `ui/src/fd`** — a repository search for `generated/` under `ui/src/fd` returns nothing, and `ui/src/index.css:1` imports only Tailwind; `ui/src/fd/fd.css` hand-ports its own tokens (comment `fd.css:9`). That is exactly the Phase 2 seam named in [PLAY-NICE-KERNEL-PLAN.md](../rebuild/PLAY-NICE-KERNEL-PLAN.md) (lines 59–61) and BACKLOG #267 ("the front-door UI still maintains a large handwritten `ui/src/fd/types.ts` with duplicate API shapes").

| Module (`path:line`) | What it is / generator | Live consumer (evidence) | Preservation test | Call |
|---|---|---|---|---|
| `ui/src/generated/openapi.json:1` | OpenAPI from the **live** app | `scripts/gen-openapi.py:23` writes it from `worlds.production:create_app`; read by `ui/scripts/generate-api-types.mjs:21` | `scripts/contract-drift-check.py:1` (drift watcher); `ui/package.json:8` (`tokens:check`) | keep (generated) |
| `ui/src/generated/api-types.ts:1` | openapi-typescript output | none in `ui/src` | drift via `ui/scripts/generate-api-types.mjs:1` | **adapt** — wire `ui/src/fd` onto it and shrink `types.ts` |
| `ui/src/generated/tokens.css:1` | design tokens CSS from `design/tokens.json` + themes | none in `ui/src/fd` | `ui/package.json:8` (`tokens:check` → `git diff --exit-code src/generated`) | **adapt** — make `fd.css`/app consume it |
| `ui/src/generated/tokens.ts:1` | typed token names | none in `ui/src` | `ui/package.json:8` | **adapt** |
| `ui/src/generated/icons.ts:1` | generated icon-id map (`scripts/generate-icons.mjs`) | none in `ui/src` | `ui/package.json:15` (`build` runs `icons:generate`) | **adapt** |

Note (evidence, not a call): `ui/scripts/generate-api-types.mjs:8` still says "The spec is hand-maintained from the server source", while `scripts/gen-openapi.py:1` generates it from the live app. The drift watcher `scripts/contract-drift-check.py:1` is the check that resolves the pair.

## 5. Provider adapters and external authorities — `src/personal_world/providers/*`

22 modules (21 + `__init__`). **None is imported by `worlds/*`**; all live consumers are legacy-application modules (`app.py`, `api.py`, `tool_registry.py`, `chat_context.py`, `cli_dispatch.py`, `setup_wizard.py`, `source_control.py`, `loop.py`) and legacy tests. Per ADR-0008 decision 3 the capability registry is retired for front-door providers, so the default call is retire/unknown pending the design pass.

| Module (`path:line`) | What it is | Live consumer (evidence) | Preservation test | Class | Call |
|---|---|---|---|---|---|
| `src/personal_world/providers/__init__.py:1` | Re-exports the registry contracts | `tests/templates/fixtures.py:24` (direct registry import) | `tests/templates/*` | LEGACY | retire |
| `src/personal_world/providers/registry.py:43` | The ADR-0001 capability registry (`Registry`, contracts) | `app.py:36`; `api.py:53`; `chat_context.py:13`; `cli_dispatch.py:447`; `loop.py:9`; `source_control.py:27`; `tool_registry.py` | `tests/test_core.py:30`; `tests/templates/fixtures.py:24` | LEGACY | retire (after consumers) |
| `src/personal_world/providers/adapters.py:1` | Concrete adapters: `http_status`, `forge`, `fake_source_control`, `sops_broker` | `app.py:24`; `tests/test_core.py:26`; `tests/test_candy.py:9`; `tests/test_safety.py:112` | `tests/test_core.py`; `tests/test_candy.py` | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/content_db.py:1` | Wraps agent-config `ContentMaster` into the registry | `app.py:436` | no dedicated test found | PROVIDER_ADAPTER | retire |
| `src/personal_world/providers/github.py:1` | Remote-repo enrichment via `gh` CLI | `api.py:4579` | `tests/test_github_enrichment.py:20` | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/lab_deploy.py:1` | `lab deploy status/ledger --json` | `app.py:31`; `api.py:2795` | `tests/test_lab_panel.py:18` | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/lab_health.py:1` | `lab health check --json` | `app.py:32`; `api.py:2785` | `tests/test_lab_panel.py:18` | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/lab_resources.py:1` | `lab resources --json` | `app.py:33`; `api.py:2815` | `tests/test_lab_panel.py:18` | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/lab_secrets.py:1` | `lab secret audit --json` (never exposes values) | `app.py:34`; `api.py:2805` | `tests/test_lab_panel.py:18` | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/lab_settings.py:1` | `lab settings status/inspect --json` | `app.py:35`; `api.py:2753` | `tests/test_lab_panel.py:18` | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/lab_state.py:1` | The homelab `lab lowbw --json` (schema `lab-lowbw/1`) operator packet | `api.py:51` | `tests/test_lab_panel.py:18`; `tests/test_agent_sync_sensor.py:365` | EXTERNAL_AUTHORITY | keep — the packet is canonical, "nothing in this module invents state" |
| `src/personal_world/providers/native_calendar.py:1` | Provider-neutral calendar (ICS/iCal, CalDAV) | `app.py:464` | no dedicated test found | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/native_media.py:1` | Media library (Plex/Sonarr/Radarr/Lidarr) | `api.py:3614`; `tool_registry.py:1576` | `tests/test_secret_resolver.py:90`; `tests/test_secret_ref_semantics.py:12` | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/native_memory.py:1` | FTS5 index over journal/notes | `app.py:420`; `setup_wizard.py:165`; `tests/test_brain_writes.py:31` | `tests/test_brain_writes.py:31` | LEGACY | **replace** — C4 `worlds/memory_store.py` is the Memory baseline |
| `src/personal_world/providers/native_notifications.py:1` | Outbound webhook / SMTP / ntfy | `app.py:479` | no dedicated test found | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/native_reconciler.py:1` | Generic desired-state reconciler | `api.py:3678`; `tool_registry.py:1183` | no dedicated test found | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/native_updates.py:1` | Version/update discovery | `app.py:494` | no dedicated test found | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/native_vault.py:1` | Registers the existing encrypted vault as the secrets capability | `app.py:406`; front-door seam `worlds/secrets.py:21` (`set_vault`) is called only by tests (`tests/worlds/test_confinement.py:306`) | `tests/test_vault.py` (legacy vault; indirect); `tests/worlds/test_confinement.py:306` | EXPLICIT CORE EXCEPTION | **adapt** — vault is an ADR-0001/0007 built-in, but no production caller wires it to the front door |
| `src/personal_world/providers/project_home.py:1` | Reads Project Home (`worlds-briefing/1`); CLI or HTTP | `api.py:52` | `tests/test_briefing.py:29` | EXTERNAL_AUTHORITY | keep — "Project Home's approval stays canonical" (ADR-0008) |
| `src/personal_world/providers/traefik_ingress.py:1` | Read-only Traefik router rollups | `app.py:216`; `api.py:5332` | (indirect) | PROVIDER_ADAPTER | unknown |
| `src/personal_world/providers/workbench.py:1` | Podman/distrobox workspaces; OFF by default | `app.py:37`; `tests/test_workbench_spike.py:33` | `tests/test_workbench_spike.py` | PROVIDER_ADAPTER | **unknown** — ADR-0003 is "proposed, not accepted" |
| `src/personal_world/providers/agent_sync.py:1` | agent-sync project-status sensor; "agent-sync stays AUTHORITATIVE" | `api.py:4620`; `tool_registry.py:1477`; `chat_context.py:175`; `cli_dispatch.py:1044` | `tests/test_agent_sync_sensor.py:34`; `tests/test_chat_projects_context.py:54` | EXTERNAL_AUTHORITY | keep |

## 6. Explicit core exceptions (core, but outside `worlds/`)

| Module (`path:line`) | Why it is an exception | Live consumer (evidence) | Preservation test | Call |
|---|---|---|---|---|
| `src/personal_world/oidc.py:1` | The single-owner sign-in service the front door's C7 depends on; explicitly kept, not a provider | `worlds/production.py:19` (`OIDCService`); `worlds/auth_routes.py:23` | `tests/test_oidc.py`; `tests/test_oidc_live.py`; `tests/test_auth_convergence.py` | keep |
| `src/personal_world/push.py:1` | Notifications + PWA; Rylee 2026-10-08: the new interface keeps them | `worlds/production.py:20` (`PushHub`); `worlds/push_routes.py:15` | `tests/test_push.py`; `tests/worlds/test_push_routes.py`; `tests/worlds/test_push_production.py` | keep |
| `src/personal_world/framework.py:1` | The framework gate, re-anchored on the new app; imports only `worlds.*` so it survives old-module deletion | `personal_world.cli:main` (`pyproject.toml:29`) → `cli.py:20` | `tests/test_framework.py` | keep |
| `src/personal_world/providers/native_vault.py:1` | The vault built-in ADR-0001/0007 excepts from provider retirement (also listed in §5) | `app.py:406`; seam `worlds/secrets.py:21` | `tests/test_vault.py`; `tests/worlds/test_confinement.py:306` | adapt |

## 7. Legacy application — named consumers (paths out of scope)

These are the live consumers of `providers/*` and of the retired UI. They are not the deliverable but must be named before removal (#319). Production does not mount them (`Dockerfile:92`).

| Module (`path:line`) | What it is | Consumed by (evidence) | Call |
|---|---|---|---|
| `src/personal_world/api.py:548` | Pre-ADR-0008 FastAPI app (`create_app`, `include_router` at `:5974`) | `setup_wizard.py`; `station_ui.py`; `cli_dispatch.py`; many legacy tests | retire |
| `src/personal_world/app.py:153` | Legacy `build_registry` — registers every provider | `api.py`; `tool_registry.py`; `cli_dispatch.py`; `setup_wizard.py` | retire |
| `src/personal_world/tool_registry.py:1` | Legacy tool loop / registrations | `api.py`; `cli_dispatch.py`; legacy tests | retire |
| `src/personal_world/cli_dispatch.py:1` | Retired CLI verbs (2399 lines) | **no importer** in `src/`, `tests/` or `scripts/` (search returns none) | retire |
| `src/personal_world/chat_context.py:13` | Legacy chat context; imports `providers.registry` | `api.py` | retire |
| `src/personal_world/setup_wizard.py:1` | Legacy onboarding; imports `providers.native_memory` | `api.py`; `login_page.py`; `invite_page.py` | retire |
| `src/personal_world/station_ui.py:1` | Legacy `/station` UI | `api.py` | retire |
| `src/personal_world/loop.py:9` | Legacy loop; imports `providers.registry` | `api.py` | retire |
| `src/personal_world/source_control.py:27` | Legacy source-control baseline | `app.py`; `api.py`; `tool_registry.py`; `chat_context.py`; `cli_dispatch.py` | retire |
| `src/personal_world/rooms.py:1` | Legacy rooms layer (2208 lines) | `api.py`; legacy room tests | retire (after room/0 core is confirmed independent) |
| `src/personal_world/api_manifest.py:1` | Curated route manifest; the rebuild replaces it with a generated inventory | `tests/test_api_manifest.py` | retire — `scripts/contract-drift-check.py:1` says the curated list is retired |
| `ui/src/app/QueryProvider.tsx:1` + `ui/src/data/queryClient.ts:1` | Only surviving old-UI files; TanStack Query provider | `ui/src/main.tsx:5` | adapt — fold into `ui/src/fd` ownership |

Supporting legacy vocabulary (shared by the above, no front-door consumer): `src/personal_world/envelope.py:1`, `src/personal_world/status.py:1`, `src/personal_world/model.py:1` (imported at `src/personal_world/providers/registry.py:16`–`18`). Class LEGACY; retire with the registry.

## 8. Preservation tests — `tests/`

The front door has its own suite under `tests/worlds/` (28 files) plus recipe tests; #319 requires these be named before any change. Module-level mappings are in the tables above; this is the index.

| Test file (`path:line`) | Protects | Front-door module(s) |
|---|---|---|
| `tests/worlds/test_api.py:8` | Read API C6 + config CRUD; seeds a real reference provider | `server.py`, `seed.py`, `reference_provider.py` |
| `tests/worlds/test_config_store.py:7` | C1 store behaviour, etags, last-valid | `config_store.py`, `models.py` |
| `tests/worlds/test_models.py:4` | C1 model validation + `action_version` | `models.py` |
| `tests/worlds/test_cards.py:1` / `test_meter.py:5` | C2 envelope, C5 data, meters | `cards.py`, `mapping.py` |
| `tests/worlds/test_mapping.py:1` | JSONPath subset + formats (no code execution) | `mapping.py` |
| `tests/worlds/test_templates.py:7` | C1.3 query templates | `templates.py` |
| `tests/worlds/test_runner.py:13` | C2 inputs, confinement seam, last-good | `runner.py` |
| `tests/worlds/test_confinement.py:11` / `test_confinement_auth.py:21` | SSRF guard, pinning, no redirects, session auth | `confinement.py`, `secrets.py` |
| `tests/worlds/test_dispatcher.py:1` / `test_authority_followups.py:1` | C3 authority, single dispatch, recovery, receipts | `dispatcher.py`, `actions_routes.py` |
| `tests/worlds/test_authn.py:1` / `test_auth_routes.py:9` | Sessions, tokens, CSRF, owner policy | `authn.py`, `auth_routes.py`, `owner.py` |
| `tests/worlds/test_memory_store.py:11` / `test_memory_routes.py:1` | C4 memory + route gating | `memory_store.py`, `memory_routes.py` |
| `tests/worlds/test_connect.py:12` | C9 try/preview (read-only, scrubbed, rate-limited) | `connect_routes.py`, `suggest.py` |
| `tests/worlds/test_room0.py:20` | room/0 mapping, adoption, receipts | `room0.py`, `room_routes.py` |
| `tests/worlds/test_companion.py:1` | Companion whitelist, honest failure | `companion.py`, `companion_routes.py` |
| `tests/worlds/test_push_routes.py:7` / `test_push_production.py:1` | Push + notify + PWA through the real app | `push_routes.py`, `push.py` |
| `tests/worlds/test_static_routes.py:4` | SPA/PWA serving and fallback ordering | `static_routes.py` |
| `tests/worlds/test_production.py:13` | End-to-end production assembly | `production.py` |
| `tests/worlds/test_dev.py:1` / `test_reference_provider.py:1` / `test_room_recipes.py:6` | Dev server, reference server, shipped recipes | `dev.py`, `reference_provider.py`, `recipes.py` |
| `tests/worlds/test_review_fixes.py:14` | #233 regression findings (credential headers, Host parsing) | `server.py`, `confinement.py` |
| `tests/recipes/test_recipes.py:17` / `test_recipes_module.py:8` / `test_room_install.py:12` / `test_openapi_import.py:11` | Recipe install, placeholders, OpenAPI skeleton | `recipes.py`, `config_store.py` |
| `tests/test_framework.py:1` | Zero-provider baseline, framework invariants | `framework.py`, `server.py` |
| `tests/test_docs.py:92` | Internal doc links resolve (this file included) | `docs/**` |
| `ui/src/test/fd-home.test.tsx:1` / `ui/e2e-fd/front-door.spec.ts:1` / `ui/e2e-fd-live/live.spec.ts:1` | Front-door UI unit + browser (390/1280, axe) | `ui/src/fd/*` |

## 9. Deletion map (evidence to preserve before any removal)

Per #321, nothing below is deleted by this packet; the map only records what must be kept as evidence and what must be settled first.

| Candidate | Evidence worth preserving | Removal condition | Blocking decision |
|---|---|---|---|
| `providers/registry.py` + `__init__.py` | `tests/test_core.py:30`; `tests/templates/*`; ADR-0001/0008 rationale | every named consumer in §7 removed; substitution proof migrated to recipe/room tests | vnext provider design (owner: "design later") |
| `providers/native_memory.py` | `tests/test_memory_models_off.py:84`; C4 parity | C4 `worlds/memory_store.py` covers the same behaviour with a passing equivalence test | C4 acceptance (already on `main`) |
| `providers/agent_sync.py`, `project_home.py` | `tests/test_agent_sync_sensor.py:34`; `tests/test_briefing.py:29` | never — external authorities; only their wiring into the legacy app is removed | none for keep |
| `providers/lab_*.py`, `native_*.py`, `traefik_ingress.py`, `github.py`, `adapters.py`, `content_db.py` | their tests (§5) | vnext decides which become recipes/config vs stay Python adapters | provider design pass |
| `providers/workbench.py` | `tests/test_workbench_spike.py`; ADR-0003 | ADR-0003 accepted or dropped | ADR-0003 (proposed) |
| `src/personal_world/api.py`, `app.py`, `tool_registry.py`, `setup_wizard.py`, `station_ui.py`, `loop.py`, `source_control.py`, `chat_context.py`, `rooms.py`, `api_manifest.py` | their legacy tests; `api_manifest.py` curated route history | front-door cutover complete; owner-gated (`docs/BACKLOG.md` #262/#263) | cutover approval |
| `src/personal_world/cli_dispatch.py` | git history only; **no importer** | immediate once confirmed dead (a search of `src/`, `tests/`, `scripts/` finds none) | none observed — verify in review |
| `ui/src/app/QueryProvider.tsx`, `ui/src/data/queryClient.ts` | `ui/src/main.tsx:5` mount | move the two files under `ui/src/fd` ownership | none |
| `ui/src/fd/types.ts` duplicate shapes | kernel plan §Phase 2; `api-types.ts` | fd imports generated types; `tsc -b` proves the contract | Phase 2 packet (B) |

## 10. Unknowns / decisions needed

- **Vault wiring (front-door).** `worlds/secrets.py:21` `set_vault` has no production caller (only `tests/worlds/test_confinement.py:306`); `vault:` refs therefore resolve to `None` in production today. Does the front door adopt the existing vault (ADR-0007) or keep `env:`/`file:` only?
- **Provider adapters after cleanup.** Which of `providers/*` become C1 recipes/config and which stay Python adapters is undecided; the owner's "design later" applies.
- **Workbench.** ADR-0003 is *proposed, not accepted*; `workbench.py` is OFF by default — keep as unknown.
- **Generated tree wiring.** `ui/src/generated/*` has no consumer in `ui/src/fd`; Phase 2 must connect it, and the `generate-api-types.mjs` comment vs `gen-openapi.py` divergence must be resolved by the drift watcher.
- **`cli_dispatch.py`.** Appears dead (no importer). Confirm in review before retiring; #321 says preserve until evidence allows removal.
- **room/0 and Companion Room semantics.** `room0.py`/`companion.py` are kept now; if vnext changes the Room wire contract, the adapters are the only translation point.

## 11. Method and evidence commands

Read-only survey; no source changed. Evidence produced with, from the repo root:

```
rg -l "worlds\.<module>|from \.<module> import" src tests          # per-module importers
rg -n "from \.\.|from \.\." src/personal_world/worlds/*.py         # packages the core reaches outside worlds/
rg -n "generated/" ui/src/fd ui/src/index.css                      # generated-tree consumers (none)
rg -n "^from \.providers|from \.providers" src/personal_world/*.py # legacy consumers of providers/
rg -l "personal_world\.cli_dispatch" src tests scripts             # dead-CLI check (none)
```

Acceptance for this packet (from the brief):

```
test -s docs/vnext/inventory.md
grep -q 'personal_world/worlds' docs/vnext/inventory.md
grep -qi 'consumer' docs/vnext/inventory.md
[ "$(grep -ciE 'keep|adapt|replace|retire|unknown' docs/vnext/inventory.md)" -ge 3 ]
```
