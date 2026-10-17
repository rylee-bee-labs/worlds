# Project Worlds — Completion Plan (historical)

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see [`.project/CURRENT.md`](../../.project/CURRENT.md)) · **Read this if:** you want the dated v1 execution plan for provenance · **Superseded by:** [`.project/PLAN.md`](../../.project/PLAN.md) for direction and [`.project/CURRENT.md`](../../.project/CURRENT.md) for state.

**In short:** the dated **v1, 2026-09-10** execution plan (with a
2026-09-14 progress note): dependency-ordered phases and acceptance
criteria toward the finish line. It is a past record, not current state.
Since it was written, the interface flipped to the React rebuild in `ui/`
(2026-09-22, Bridge is now home), the server-rendered Station became a
theme package, and the rooms/registry/crew/doorways architecture landed —
so every phase status and count below must be re-verified against the code
before it is treated as current. (Formerly "Personal World"; the filename
and cross-links keep the historical identifier — technical identifiers
are unchanged.)

> **Progress note (2026-09-14):** the architecture branch merged to main
> via PR #42 and PR #43. Several A0 findings are resolved: the reminder
> scheduler (H6) is implemented and running, and native providers cover
> all capabilities. The dated merge receipt moved to
> [history/FINAL-RECEIPT.md](FINAL-RECEIPT.md).

This plan compares the real implementation against
[`PERSONAL-WORLD-FINISH-LINE.md`](../PERSONAL-WORLD-FINISH-LINE.md) and defines
the dependency-ordered work, acceptance criteria, contracts, and model
routing needed to reach it. The finish line defines *what finished means*;
this document defines *how we get there*. [`../ROADMAP.md`](../../ROADMAP.md)
remains direction only.

Every claim below about current behavior was verified against the working
tree on 2026-09-10 (local HEAD `fd9d78a`, then fast-forwarded to `bca5a80`,
which added documentation only). Where a claim could not be verified it is
marked `UNKNOWN`. Repository truth outranks this plan: if code and plan
disagree, inspect the code, then fix the plan.

Vocabulary used throughout:

- **CURRENT** — what the code does today, with evidence.
- **TARGET** — what the finish line requires.
- **Model:** `FABLE` (architecture, contracts, security posture, UX
  judgment, review) · `GLM` (GLM-5.3-Flash or similar: bounded
  implementation against a written contract) · `DET` (deterministic
  tooling: pytest, `framework validate`, Playwright/axe, build, git).
- **Contracts:** `A11y` ([accessibility](../accessibility/ACCESSIBILITY_CONTRACT.md)),
  `HR` ([human reliability](../HUMAN_RELIABILITY_CONTRACT.md)),
  `PRB` ([public repository boundary](../../SECURITY.md)),
  `PNB` ([provider-neutral baseline](../NATIVE-BASELINE-AND-ENRICHMENT.md)).

---

## Part A — Ground truth (CURRENT)

### A0. Working-tree hazards found during planning

These exist in the uncommitted working tree or in HEAD as noted. They are
fixed in Phase 0. Credential values that were exposed are considered burned
and are rotated by the owner separately; they are never reproduced here.

| # | Finding | Where |
|---|---|---|
| H1 | Plaintext provider API keys in the **git-tracked** `config/connections.json` (uncommitted edit). `test_public_safety` fails. | working tree |
| H2 | A bearer token in `frontend-v2/.env` is inlined by Vite into `frontend-v2/dist/assets/*.js`, which the uncommitted `api.py` serves unauthenticated. | working tree |
| H3 | Uncommitted `PUT/GET /api/connections` write and return raw `api_key` values; hard-coded absolute home-directory paths; bare `except: pass`. | working tree `api.py` |
| H4 | `config/principal.json` and `frontend-v2/` sources are untracked and **not gitignored**. | working tree |
| H5 | `/login` handler builds HTML but never returns it (empty body). | HEAD `api.py` |
| H6 | Reminder scheduler calls `journal.append_raw`, which does not exist; the thread dies on first fire. | HEAD `scheduler.py` |
| H7 | `POST /api/chat/test` has no auth; `POST /api/world/policy` 500s on cemented keys; `GET /api/daily` mutates and saves the world. | HEAD `api.py` |
| H8 | `require_step_up` is not step-up: any RFC1918 client, or any client sending `X-PW-StepUp: 1`, passes. No TTL, no re-authentication. | HEAD `api.py` |

Environment note: two `tests/test_source_control.py` tests fail on hosts whose
global `init.defaultBranch` is not `master`/`main`. This is a fixture issue,
not a product bug (fixed in P0.6).

### A1. Genuinely complete (keep)

- Core world model and mutation gates: facts / intent / policy / lore,
  `MutationDenied`, cemented policies, `world/private/secret`
  classification, whitelist exports with leakage tests
  (`model.py`, `world.py`, `export.py`, `tests/test_core.py`).
- Provider-neutral framework: capability registry, `ProviderMode`, honest
  status vocabulary, `framework validate`, conformance suite,
  zero-provider boot (`framework.py`, `providers/registry.py`,
  `tests/test_framework.py`).
- Native source-control baseline: discover / status / history via read-only
  git; never raises (`source_control.py`, 23 tests).
- Built-in encrypted vault: Fernet + PBKDF2 (600k), unlock/lock/set/delete/
  names (`vault.py`).
- Presentation-preference accessibility floor: 44px targets, motion
  reduced, contrast, text scale; server rejects below-floor values with
  400, never clamps (`prefs.py`, 45 tests).
- Safe update state machine: check → preview → apply → verify → rollback
  with expiring preview hash (`updates.py`, 32 tests). **This is the seed
  of the general action/approval engine (P5).**
- Design truth: `design/tokens.json`, five companion rigs, 72-glyph icon
  sprite, self-hosted fonts, accessibility contract. The legacy dashboard
  CSS matches the tokens exactly.
- Public-safety regression gate and CI (pytest, `framework validate`,
  `docker compose config`).

### A2. Exists but incomplete

| Area | CURRENT | Gap to TARGET |
|---|---|---|
| Chat | Five adapters in `chat_registry.py`; read-only world-context block; provenance `<details>`; history in `sessionStorage` | No streaming; no tools/actions; one global provider; no per-surface context profile; **two parallel adapter modules** (`chat.py` used by `api.py`, `chat_registry.py` used by `app.py`) |
| Identity | Bearer token; multi-mode users/agents with hashed tokens; agent scopes stored | Scopes not enforced; no sessions; no OIDC; step-up is a header/LAN check (H8); no break-glass |
| Vault | Native Fernet file | `VaultContract` and `SOPSVaultAdapter` defined but unwired; separate unused `SopsBroker`; no auto-lock; value read gated only by client IP |
| Today | Health sentence, attention, changes, journal composer, Services, Lab quota under `<details>` | No "coming up" (no calendar provider); no "what was I working on" continuation; quiet-when-healthy only partial |
| Lab | Five `homelab_*` capabilities shell out to the homelab `lab` CLI; Traefik observer | No actions, no logs; CLI path candidates hard-coded; Traefik base URL hard-coded to a private address in tracked code |
| Journal | Append-only NDJSON; kind filter; provenance details | No search, no supersede/correct/redact, no "where was I", no rylee_lore adapter, no Markdown memory |
| Settings | Six prefs, companion select, reminders, read-only capability table | No section order/visibility; no provider-per-capability; no vault backend choice; no safe connections editor; no approval policies; no custom cards |
| Theme packs | Manifest model + `GET /api/themes` | Nothing applies a pack; `DEFAULT_PACK` points at a nonexistent `/static/` mount; no packs in `data/` |
| Companions | Static SVGs, `aria-hidden` correct | No state poses; no contextual-vs-personal identity |
| Setup | `/setup-wizard`, `/setup`, React `SetupWizard` | Three flows; the React one omits the vault passphrase and posts a field the API ignores |
| Scheduler | Reminder CRUD + thread | Crashes on fire (H6); daily loop never scheduled; reminder writes lack step-up |

### A3. Designed but not implemented

- Nine Chat screens (`design/screens/chat/`): contextual project identity,
  tool progress, source provenance, error-partial.
- Theme pack framework and the personal pack
  (`design/THEME_PACK_FRAMEWORK.md`, `design/RYLEE_THEME_PACK.md`).
- Confirmation dialog, provenance drawer, World Assistant drawer
  (A11y §3). No `<dialog>` exists in either frontend.
- Companion state system (six poses); contextual character per project.
- Interview/onboarding flow (PNB §14 — explicitly "do not build yet").

### A4. Missing entirely

Interests/Discovery surface (only a health probe exists) · Media capability
and adapters · Projects workspace and project model · calendar provider ·
PR/issue/CI reads · deployed-vs-source version comparison · dependency/tool
update discovery · logs capability · action/approval engine with remembered
rules · trusted automation · per-capability provider/model routing ·
context profiles · global cross-system chat · SSO · sessions · step-up with
TTL · break-glass · Markdown memory · search index · rylee_lore adapter ·
nerd-mode drawer · section registry · browser/axe tests · image build in
CI · design screens for Projects/Media/Interests/Lab/Vault.

### A5. Duplicate or obsolete machinery to retire

| Duplicate | Keep | Retire |
|---|---|---|
| `chat.py` vs `chat_registry.py` | one merged `chat/` package | the other |
| `STANDARD_CAPABILITIES` in `app.py` vs `framework.py` | `framework.py` | `app.py` copy |
| `user.py::UserManager` vs `identity.py` | `identity.py` | `UserManager` |
| `SopsBroker` vs `SOPSVaultAdapter` vs `VaultContract` | `VaultContract` wired; SOPS as one provider | the other two |
| `SETUP_HTML` vs `WIZARD_HTML` vs React `SetupWizard` | one | two |
| `LOGIN_HTML` | replaced in P2 | — |
| `DASHBOARD_HTML` (1,700-line Python string) vs React frontend | React (D1) | legacy, after parity |
| `renderQuickActions`, `DEFAULT_PACK` `/static/` paths, `X-PW-StepUp` header, host-specific compose bind mounts, hard-coded lab CLI candidates and Traefik address | — | all |
| `api.py` monolith (~3,400 lines incl. inline HTML) | routers per domain | monolith |

### A6. Do NOT build (an existing capability already owns it)

- A second scheduler → fix and generalize `scheduler.py`.
- A second approval system → generalize `UpdateManager`'s state machine.
- A second user store → `identity.py`.
- A new audit log → `journal.ndjson` remains the append-only audit truth.
- A git client / PR UI → native git baseline + forge reads + deep link.
- Gatus / Komodo / Homepage clones → health/deploy capability contracts + deep links.
- A Lab control plane → the homelab `scripts/lab` tool is the provider (D5).
- A vector-database console → `memory` capability with a rebuildable index.
- Plugin runtime / event bus / SDK → forbidden for v0 by PNB §16.
- A separate Tiny Gherkin destination → an agent principal with narrow
  scopes acting through the action engine.
- Household multi-user UX, mobile app, marketplace → allowed to wait.

---

## Part B — Decisions (approved 2026-09-10)

### D1 — Frontend foundation: React 19 + Vite

Commit the React frontend as *the* frontend. Tailwind is permitted as an
implementation helper but **is not design truth**: `design/tokens.json` and
the accessibility contracts remain canonical. Retire `DASHBOARD_HTML` only
after browser-verified parity. Requirements: built in the normal container
path; no external font or asset dependency; no credentials in the bundle;
native accessible primitives (`<dialog>`, `popover`) where appropriate;
axe in CI; no fake/demo state once connected to real APIs; progressive
disclosure and current contracts preserved.

### D2 — Authentication: Authelia OIDC is the first proof, not the architecture

Provider-neutral OIDC/identity seam; browser = secure cookie session;
agents/API = bearer tokens; severe/destructive/vault operations = real
step-up; bootstrap/break-glass remains available and documented. The daily
deployment is a container in the homelab stack behind Traefik + Authelia;
the Bazzite host runs model/runtime services, not the web host. Therefore
loopback-only break-glass is **not** sufficient recovery.

### D3 — Motion: `off | reduced | subtle`

Three values, default `reduced`. `off`: no nonessential animation, no
ambient movement, no decorative pose transitions. `reduced` (default): no
continuous/ambient animation; instant state/pose changes allowed.
`subtle` (opt-in): transitions ≤300ms; ambient movement ≤2px where
allowed; no pulse/spin/shake/flash. OS `prefers-reduced-motion` always
overrides and suppresses subtle animation. Motion is never required to
understand or operate the product. `off` is not collapsed into
`reduced`: the explicit no-motion choice is cheap and useful.
Definitions and CSS emission: `docs/p1/FOUNDATION-SPEC.md` §3.

### D4 — Memory canon

Journal/audit stream stays NDJSON. Human memory, notes, lore, and project
context use Markdown as canonical durable truth where practical. Search /
FTS / vector indexes are derived and disposable; SQLite FTS is the native
baseline; other providers may enrich or replace the acceleration layer.
rylee_lore integration may read and produce review/evidence receipts.
**Agents never promote lore to canon.** The journal itself is not Markdown.

### D5 — Lab truth source and calendar

The `lab` CLI exists in `Rylee-Bee/homelab` at `scripts/lab`; the real
deployment mounts it read-only into the container. Project Worlds owns the
human-facing Lab capability/UI; `scripts/lab` is the provider underneath.
Do not recreate the control plane. Inability to see the tool from a
development checkout is an environment condition, not evidence of absence.

Calendar: provider **undecided**. Keep a provider-neutral `calendar`
capability declared and `not_configured`; do not select or invent a provider.

### D6 — Media and Interests

Media adapters: Sonarr, Radarr, Lidarr, Plex. Jellyfin is not assumed
(treat as absent/`UNKNOWN` until observed). All sit behind native Media
concepts, not vendor-shaped pages. Interests native baseline: explicit
RSS/Atom follows; candy-dispenser as optional recommendation enrichment;
Reddit as optional enrichment when available; no Reddit dependency. The
capability is Interests/Discovery, not "Reddit".

---

## Part C — Cross-cutting invariants (apply to every phase)

### C-1. Private runtime configuration ownership (PRB)

Anything containing the owner's actual provider/model routing, project
selection, follows, personal configuration, or environment-specific state
must never become tracked repository state.

| Tracked (public repo) | Private runtime (never tracked) |
|---|---|
| `config/*.example.json`, JSON schemas, code defaults | actual values |
| `config/connections.json` — stays **zero-provider** | `config/connections.local.json` (existing pattern) |
| `config/chat-profiles.example.json` + built-in defaults | `config.local/chat-profiles.json` |
| `config/routing.example.json` | `config.local/routing.json` |
| `config/projects.example.json` | `config.local/projects.json` |
| — | `config.local/principal.json` |
| — | `data/` (world, journal, memory, conversations, index, users, vault, follows, feedback) |

Resolution order: code default → private runtime file (`config.local/` or
`PW_CONFIG_LOCAL_DIR`). Tracked `*.example.json` files are never read as
truth. Public exports (`settings-export`) list capability, provider *type*,
and mode only. `framework validate` and `tests/test_public_safety.py` gain a
rule that any tracked `config/*.json` that is not an example must be
zero-provider and free of personal values. `.gitignore` covers
`config.local/`, `config/*.local.json`, `config/principal.json`,
`frontend/.env*`, `frontend/dist/`.

### C-2. Provider contracts over filesystem details

Error and empty-state messages name the capability and the configuration
knob (for example `PW_LAB_CLI`), never a mount path or host layout.

### C-3. Disposable runtime state vs canonical truth

Sessions, rate-limit buckets, search indexes, caches, and rankings live
under `data/index/` (or another explicitly disposable path), may be deleted
at any time without losing personal truth, and are excluded from `backup`
and exports. Canonical truth is `world.json`, `journal.ndjson`,
`data/memory/**/*.md`, the vault, and private runtime config.

### C-4. Tooling discipline

A new tool must remove more complexity than it adds. Frontend verification
stack is Vitest (component) · Playwright · axe-core · token-drift test ·
bundle size and bundle secret-scan · real browser acceptance. Storybook and
related add-ons are **not** a mandatory dependency; they are removed in P1
unless a P13 design-review task demonstrates net reduction of work
(default: remove). The same rule applies to data-layer libraries: the
foundation uses a typed fetch client and ordinary React hooks; React
Query (or similar) may be added only by a bounded task whose report shows
more complexity removed than added.

### C-5. Secrets

Secret values never appear in responses, journal lines, exports, logs,
prompts, or the frontend bundle. Adapters receive values through a resolver
(env indirection or vault reference); callers receive references only.

---

## Part D — Phase plan (dependency-ordered)

```text
P0 ─► P1 shell ─► P2 auth ─► P3 secrets/vault ─► P4 chat engine ─► P5 actions
                                                     ├─► P6 Today    ├─► P7 Projects   ├─► P8 Lab
                                                     ├─► P9 Media    ├─► P10 Interests └─► P11 Memory
P12 Settings accretes controls from P2–P11
P13 Polish runs continuously from P1; final pass after P12
P14 CI/deploy opens in P1 (browser tests) and closes last
Refactor lane (api.py → routers; delete A5 duplicates) runs from P0 exit
```

P6–P11 may run in parallel worktrees (see [`../AGENTS.md`](../../AGENTS.md))
once P5 lands.

### MUST HAVE FOR FINISH LINE

---

### P0 — Stabilize the working tree and secret boundary

**Purpose.** Return to a green, publishable tree; stop credential leakage;
fix latent HEAD bugs that later phases would build on.
**Evidence.** A0 H1–H8; working-tree suite 368 pass / 11 fail;
`framework validate` unhealthy (3 violations from `type: cloud` entries
lacking `capability`).
**Depends on.** Nothing. **Model.** DET + GLM; FABLE reviews only the
gitignore and secret-scan patterns.

| ID | Task | Verify |
|---|---|---|
| P0.1 | Owner rotates the exposed provider keys and the instance token (`PW_API_TOKEN`). **No replacement client-side token is created**: anything exposed to Vite/client config can end up in the browser bundle, so the frontend bearer-token pattern is removed (P0.3), not rotated. Agents never receive values; new values go only into `.env` / `config/connections.local.json` via env indirection. | old values no longer authenticate |
| P0.2 | `git checkout -- config/connections.json`. Extend `.gitignore` per C-1. Move `config/principal.json` to `config.local/`. | `test_public_safety` PASS; no secret-bearing path unignored |
| P0.3 | Do not carry forward the working-tree `api.py` experiment: plaintext connections routes, absolute home paths, bare excepts, and unauthenticated React `dist` serving are discarded (React lands properly in P1). Re-implement `PUT /api/identity/principal` safely (display name stored in private runtime state under `data/`, never in tracked `config/`). Remove the client-side bearer-token pattern from the React prototype (`VITE_*` token env, baked `dist/`); until P2 the browser supplies its token at sign-in only. Add a tracked-tree test that no `VITE_*TOKEN|SECRET|KEY` pattern exists. | new tests + suite green |
| P0.4 | `scheduler.py`: replace `journal.append_raw` with `journal.record(...)`; add `test_scheduler_fire_journals_event`. | thread survives a firing reminder |
| P0.5 | `/login` returns HTML; `/api/chat/test` requires auth; `POST /api/world/policy` → 409 on cemented; `GET /api/daily` → `POST /api/daily`; reminder writes require step-up. Update tests. | suite green |
| P0.6 | Source-control fixtures use `git init -b master` (or `GIT_CONFIG_GLOBAL=/dev/null`). | two environmental failures gone |
| P0.7 | `test_public_safety.py`: secret-shape scan across tracked files (common key prefixes; ≥32 hex/base64 after `api_key`/`token`) plus the C-1 non-example config rule. | canary test |
| P0.8 | Reconcile `.agent/STATE.md` with this plan (done in the same commit that adds this document). | — |

**Exit.** HEAD green locally and in CI; `framework validate` healthy; no
secret material tracked or unignored.
**Contracts.** PRB (currently FAIL → PASS), HR.
**Risk.** If any push carried the keys, history contains them; rotation is
mandatory regardless.

---

### P1 — Frontend foundation and section shell (React 19 + Vite)

**Purpose.** One coherent, extensible shell hosting Today / Interests /
Media / Projects / Lab / Journal-Memory / Vault / Settings, with chat as a
layer; accessibility primitives built once.
**CURRENT.** Legacy dashboard is a 1,700-line Python string, hash-routed,
no `<dialog>`, no drawer. `frontend-v2/` is a React 19 prototype at roughly
60% parity with fabricated "Recent changes", no `aria-live`, div-based
modals, external font CDN, preference vocabulary that the API rejects, and
a call to a nonexistent upload route.
**TARGET.** D1.
**Depends on.** P0. **Model.** FABLE: sections API, primitive contracts,
cutover checklist review. GLM: each primitive/screen (one task each). DET:
axe/token/budget tests.

**Spec.** The bounded implementation contract for this phase is
[`p1/FOUNDATION-SPEC.md`](../p1/FOUNDATION-SPEC.md) (approved 2026-09-10):
sections API (`settings` is the only pinned section; `today` is
hideable; "Restore default sections" in Settings; canonical status or
`null`, never invented values; `configured` separate from `status`),
primitive contracts, parity checklist, bounded tasks T0–T16.
**Progress (2026-09-12).** T0–T9 complete: T1–T4 merged (PR #20);
T5–T9 at the second convergence checkpoint (tokens pipeline, typed API
boundary, primitives A+B, AppShell/SectionNav). Screens T10–T13 and
gates T14 follow; cutover T15 after the human zoom gate. The spec's
FABLE-review rows are superseded by the owner's 2026-09-11 policy
(GLM-autonomous; Fable only for genuine contradictions and the final
convergence audit).

**Files.** `frontend/` (tracked; renamed from `frontend-v2/`), `Dockerfile`
(stage 1 node build, stage 2 python image copying `dist/`), `api.py` SPA
mount at `/` with auth-aware HTML and public-safe static assets,
`scripts/gen-tokens` (`design/tokens.json` → `frontend/src/tokens.css`,
generated and drift-tested), `GET/PUT /api/sections` (order/visibility
stored in prefs), primitives `Dialog` (`<dialog>`), `Drawer` (non-modal),
`Popover` (native), `LiveRegion` (polite, batched), `StatusChip` (word +
luminance), `Disclosure` (Level 1 → Level 4), `CompanionSlot`
(`aria-hidden`), `StepUpPrompt` stub. Remove external fonts (self-host the
two woff2 already in `static/fonts`), fake data, hard-coded providers /
timezone / version, debugging output, template cruft, Storybook (C-4).
Align preference vocabulary with `prefs.py` (+ D3 motion).

**Standalone Chat during parity (transition, not invariant).** The existing
standalone Chat page is preserved through P1 so parity can be proven. The
finish-line architecture is contextual chat available in every section plus
a global chat mode (P4). After P4, Settings › Sections controls whether a
standalone Chat destination is shown; keeping or hiding it is a preference,
not a migration. A permanent ninth top-level section is **not** required.

**Parity checklist (gate to delete legacy HTML).** Today blocks · Services
launcher + editor · Lab table + quota · Journal filters + load-more · Vault
unlock/lock/store/delete · Settings prefs/companion/reminders/themes · Chat
send/provenance/retry/persistence · one setup wizard (with vault
passphrase) · login · server-side preference floor still enforced by API.

**Acceptance.** All eight sections reachable with honest `not_configured`
empty states; sections hide/reorder and persist; axe 0 serious/critical per
route at 1440/900/600/375; 200% zoom without horizontal scroll (automated
CSS-zoom/narrow-viewport checks are proxies; a real browser 200% zoom
check on the deployed build is a required human gate); ≥44px
targets scanned by Playwright; one visible `h1`; landmarks including
`complementary`; token-drift test: no color literal outside `tokens.css`;
bundle budget ≤350 KB gzipped; no external network requests at runtime;
nothing on screen is fabricated.

**Tests.** Vitest components; Playwright + axe in CI against the built
image; legacy HTML-string tests (`test_dashboard.py` structural,
`test_prefs.py::TestDashboardPrefsPlumbing`, `test_setup_wizard.py`
structure) retired **in the same commit that deletes the legacy HTML**,
replaced by API + browser tests. Server-side floor tests remain.
**Contracts.** A11y §1–7, HR, PNB §10–11.
**Risk.** Cutover regressions → `PW_FRONTEND=legacy` flag until the
checklist passes, then one deletion commit.

---

### P2 — Authentication: OIDC seam, sessions, step-up, break-glass

**Purpose.** Provider-neutral auth suitable for browsers now and other
clients later; real step-up; the owner can never be locked out.
**CURRENT.** Static bearer in `localStorage`; step-up = LAN or header (H8);
no OIDC code; forged `Remote-User` headers correctly ignored.
**TARGET.** D2 plus the auth addendum below.
**Depends on.** P1 (login/step-up UI). **Model.** FABLE designs and reviews
the full diff. GLM implements the OIDC client, session store, and tests
against a fake IdP fixture.

**Design.**

- `auth.py` with an `AuthProvider` contract → `OIDCProvider` (discovery,
  PKCE, `state`, `nonce`, ID-token verification via JWKS; Authelia is
  configuration, not code) and `LocalPasswordProvider` (bootstrap and
  break-glass). Bearer path retained via `identity.resolve_principal` for
  agents/API/future clients.
- **Sessions (C-3):** SQLite at `data/index/sessions.sqlite` (WAL, single
  writer, `BEGIN IMMEDIATE` per mutation). Schema: `id, principal_id,
  created_at, expires_at, auth_level, step_up_until, csrf_secret, ua_hint,
  revoked_at`. Cookie `HttpOnly; Secure; SameSite=Lax`. Session ID rotates
  on login, on step-up level change, and on revoke-others. Deleting the
  file ends all sessions and loses nothing canonical. Stale rows purged at
  startup and hourly. Excluded from `backup`/exports.
- **Step-up:** `auth_level` 1/2 with `step_up_until` on the session; level
  2 requires fresh IdP authentication (`max_age=0` / `prompt=login`) or the
  local password; TTL default 10 minutes, configurable. `require_step_up`
  checks level + TTL only — **no IP or header shortcuts.** Bearer
  principals use a `POST /auth/step-up` challenge of the same credential
  class.
- **CSRF:** double-submit token bound to `csrf_secret` on every
  state-changing cookie-authenticated route; `Origin` / `Sec-Fetch-Site`
  checked.

**Auth addendum — break-glass is a recovery mechanism, not a weaker front
door.**

- Hashing: argon2id with pinned parameters; rehash on login when
  parameters change.
- Rate limiting and backoff: per-source and per-account token buckets in
  the sessions database; exponential backoff after repeated failures;
  lockout windows journaled as `SECURITY`.
- No account enumeration: identical body, status, and timing envelope for
  unknown account vs wrong password; no "exists" signal in any flow.
- Journal: every local login attempt (success/fail/lockout), every
  break-glass use, and every credential change → `SECURITY` events with
  actor and coarse source class; never the credential.
- Visible attention: after any break-glass login, Today shows a
  `needs_attention` item ("Recovery sign-in was used") until acknowledged;
  the acknowledgement is journaled.
- Credential changes require step-up: changing or resetting the local
  credential requires `auth_level 2` within TTL. The CLI reset path
  (`personal-world auth reset --confirm` — proposed in this plan; not a
  current command) requires host shell access and is journaled.
- Local login grants `auth_level 1` only; step-up is still required for
  severe actions after break-glass.
- Loopback is a bonus recovery path, never the only one (D2).

**Deployment requirement (coordination item C1).** Project Worlds performs
its own OIDC, so its Traefik router carries **no** Authelia forward-auth
middleware; otherwise break-glass is unreachable during an IdP outage. If
homelab policy insists on forward-auth, exempt `/auth/local*` and
`/healthz` via a second router.

**Acceptance.** Browser sign-in through the real Authelia deployment
(journal evidence); step-up prompt for vault reads, policy/rule changes,
destructive proposals, expiring after TTL; `X-PW-StepUp: 1` from a private
address → 403 (regression test); simulated IdP outage → local break-glass
works and is journaled and surfaced; sessions listed/revoked in Settings;
forged proxy headers still fail; bearer agents work with scopes
**enforced** (scope enforcement lands here).
**Tests.** Session store concurrency/rotation/expiry/delete-and-restart;
OIDC flow against a fake IdP; header-bypass negatives; enumeration
timing/body equality; backoff; CSRF negatives; level-after-break-glass;
reset-requires-step-up; `test_safety` extended.
**Contracts.** PRB, HR (recovery before heroics), A11y §3.3 for the step-up
dialog.
**Risk.** Highest-security phase; must land before P5, P7, P8 expose
actions. Existing `localStorage` tokens stop working — release note.

---

### P3 — Secret boundary for provider configuration + vault provider abstraction

**Purpose.** Configure providers and keys from the UI without secrets
touching tracked files, logs, exports, or model context; swap vault backend
from Settings.
**CURRENT.** H1/H3; `VaultContract` unwired; validator already rejects
inline `api_key`.
**Depends on.** P2 (step-up). **Model.** FABLE: resolver, contract wiring,
leakage-test design. GLM: adapters and Settings UI.

**Design.** Connections reference secrets as `api_key_env` or
`api_key_ref: "vault://<name>"`; a `SecretResolver` resolves at adapter
call time and never returns values to callers. `PUT /api/connections`
(step-up) stores the secret in the active vault and writes only the
reference to `config/connections.local.json`; tracked `connections.json`
stays zero-provider. `GET /api/connections` returns references plus
`has_secret`. `POST /api/connections/{id}/probe` runs server-side. Wire
`VaultContract` with `native_fernet`, `sops`, `openbao` providers; Settings
› Vault selects the backend; vault auto-lock TTL. Delete `SopsBroker` and
the duplicate `SOPSVaultAdapter`.
**Acceptance.** Adding a cloud chat provider from Settings works
end-to-end with zero secret bytes in any response body, journal line,
export, log, or chat prompt (canary tests); tracked `connections.json`
unchanged; `framework validate` healthy; vault backend swap without code
edits.
**Tests.** Canary leakage across every GET/export/story/prompt; validator
tests for `_ref` forms; the same `VaultContract` suite passes for
`native_fernet` and a fake external vault.
**Contracts.** PRB, PNB §5, architecture security model.

---

### P4 — Chat engine: unified adapters, streaming, context profiles, routing, tools, global chat

**Purpose.** "Contextual chat everywhere" with per-capability provider and
model choice.
**CURRENT.** Two adapter modules; `stream: False` everywhere; one fixed
context block; first healthy `reasoning` provider wins; no tools by design.
**Depends on.** P3. **Model.** FABLE: design, tool policy, prompt-injection
posture. GLM: adapter merge, SSE, individual read tools, UI rendering.

**Design.**

- Merge into a `chat/` package; one `ChatContract` with `stream()`;
  `POST /api/chat/stream` (SSE).
- **Context profile** `{surface, capability, selection, tools[], policy,
  provider_ref, model, prompt_template}`. Built-in defaults for
  `today | projects | media | lab | journal | vault | interests | global`
  ship in code; a tracked `config/chat-profiles.example.json` documents the
  schema; the owner's overrides live in `config.local/chat-profiles.json`
  (C-1). The frontend sends `{profile, selection}`; the server resolves.
- **Routing table** `surface_or_capability → {connection, model}`:
  `config/routing.example.json` tracked, `config.local/routing.json`
  private; Settings edits the private file; `reasoning` is just the default
  row.
- **Tools** are capability-contract methods with JSON schemas. Read tools
  first (`status`, `journal.search`, `source_control.*`, `lab.*`,
  `media.*`, `discovery.*`). Write tools **only** emit proposals into P5.
  Journal and note content is data, never instructions.
- Global profile = union of tools the principal is authorized for. Every
  tool call journaled with provider, model, latency, and policy for nerd
  mode.
- Conversations persisted per principal under `data/conversations/`
  (private classification).
- Contextual chat surfaces as a drawer/panel on every section (A11y §3.2);
  a standalone destination is optional (see P1).

**Acceptance.** Media chat answers with Media tools and its configured
model; Projects chat sees the selected repository; Lab chat sees health;
global chat spans all when authorized; changing a surface's model in
Settings changes the model actually used (visible in the nerd drawer);
streaming visible with accessible text status; tool calls appear as steps
with provenance, matching the designed chat screens.
**Tests.** Profile resolution; routing; tool-schema conformance; SSE; no
secret in prompt; fake-provider substitution across all surfaces.
**Contracts.** PNB, A11y §3.2 and §8, HR.

---

### P5 — Action engine: propose → explain → approve → act; remembered rules; trusted automation

**Purpose.** The single path for every meaningful change, from chat or UI.
**CURRENT.** `UpdateManager` has the right shape; `Policy` exists;
`check_policy` has no callers; no approval routes.
**Depends on.** P4 (tools emit proposals), P2 (step-up). **Model.** FABLE:
design and review. GLM: implementation and tests.

**Design.** `Proposal{id, verb, target, provider, risk, preview,
explanation, expires_at, proposed_by}`; `POST /api/actions/propose |
approve | deny`, `GET /api/actions`. Risk tiers: `low` may be remembered;
`medium` remembered per target only; `high`, `destructive`, and
secret-access require step-up every time and are never rememberable.
Remembered rules stored as `Policy{mutability: remembered}` in
`world.json`, listed/edited/revoked in Settings › Approvals, every
evaluation journaled. Trusted automation = agent principal + remembered
rules within scope limits. `UpdateManager` becomes the first client. Agent
scope enforcement completes here.
**Acceptance.** Approving from chat and from a card yields identical
journal trails; "remember this" appears only for low/medium; revoking a
rule blocks immediately; a destructive action with a remembered rule still
prompts step-up; the confirmation dialog names verb, consequence, and
provider (A11y §4.4).
**Tests.** State machine (mirroring `test_updates.py`); tier matrix;
journal trail; agent-scope enforcement.
**Contracts.** HR, A11y §3.3, PRB.

---

### P6 — Today: what needs me, what was I working on, what is coming up

**CURRENT.** Health/attention/changes exist; no continuation; no upcoming;
discovery shows capability metadata.
**Depends on.** P5. **Model.** FABLE: attention/continuation heuristics.
GLM: cards.

**Design.** Attention aggregator over capability statuses, failed
proposals, stale repositories, updates, reminders, security events (P2).
Continuation ("Where was I?") derived from journal, dirty branches, open
proposals, and the last conversation per project. Upcoming = reminders +
due updates + forge milestones/due dates + `calendar` **when a provider is
configured** (stays `not_configured` per D5). Healthy capabilities collapse
to one sentence and one link. Richer actions via proposal cards.
**Acceptance.** Quiet day: ≤3 blocks, no green list; a failing service
surfaces at the top with a repair proposal; "Where was I?" names the last
project/branch/note; Level-4 detail on every block; A11y §5.2 source order.
**Tests.** Aggregator over fixture statuses; quiet-day DOM has no status
chips beyond the summary; browser test at 375px.

---

### P7 — Projects: reusable mission control

**CURRENT.** Native git status/history; Gitea commit rollups; nothing for
PRs/issues/CI/deploy/version/dependencies/logs.
**Depends on.** P5. **Model.** FABLE: project model and `forge` contract.
GLM: each adapter and panel as a bounded task.

**Design.** `Project{id, name, repo_path, forge: {type, owner, repo},
deploy_ref, docs_paths[], lore_ref, chat_profile, companion}` in
`config.local/projects.json` (schema in `config/projects.example.json`),
plus auto-discovery from source-control `search_paths`. New capabilities:
`forge` (PRs/issues/CI via Gitea and GitHub adapters, provider-neutral
shapes), `releases`, `versions` (deployed tag via Lab/updates vs source),
`dependencies` (uv/npm outdated reads), `logs` (shared with P8). Workspace
shell with project switcher; contextual companion alongside the personal
companion; Projects chat profile receives `selection=project`;
build/test/deploy as proposals; docs/lore panel renders repository Markdown
and P11 memory; deep links to the forge. VEFR, MUNR, and Burrito Journalism
load with their own context.
**Acceptance.** Switching to another project changes header, companion,
panels, and chat context; PRs/issues/CI shown for this repository;
deployed vs source version with drift status; safe actions are proposals;
keyboard-only switcher works.
**Tests.** Registry; forge adapters with fixtures plus fake substitution;
`not_configured` panel states; browser switcher test.
**Contracts.** PNB (no forge clone), A11y, HR.

---

### P8 — Lab and infrastructure

**CURRENT.** `lab_*` providers shell out to the homelab `lab` tool via a
hard-coded candidate path list; Traefik observer with a hard-coded private
address; no actions or logs.
**TARGET.** D5.
**Depends on.** P5. **Model.** GLM mostly; FABLE for the log-redaction
boundary and action tiering.

**Design.** `PW_LAB_CLI` is the single authority for the tool path, with
one deployment default matching the real container layout (confirmed from
the homelab compose during P8, under the container's `/opt` tree — not
invented here). Remove the hard-coded candidate list and the test pinning
it. Absent or non-executable → `not_configured` with a generic message
("Lab provider not configured — set `PW_LAB_CLI`"); present but failing →
`unavailable` with the error class. No mount names in code or messages
(C-2). `TraefikIngress` base URL comes from private config. Add a `logs`
capability (via `lab` verbs where available; tail-only; redaction filter);
restart/redeploy/repair as proposals invoking `lab` verbs through P5;
topology only if the tool exposes it; Gatus/Komodo as optional enrichment;
deep links.
**Acceptance.** Healthy lab = one quiet line; failing service surfaces
with logs and a restart proposal; provider absent → visible, honest
degradation with the core unaffected; a secret canary in logs never
reaches UI or model; no private address in tracked code.
**Tests.** Fixture packets; log redaction canary; PNB §12 lifecycle.

---

### P9 — Media mini-app

**CURRENT.** Nothing exists. **TARGET.** D6.
**Depends on.** P5. **Model.** GLM; FABLE for the contract shape only.

**Design.** `media` capability contract: `summary / upcoming /
recently_added / wanted / queue / search / request / remove`. Adapters:
Sonarr, Radarr, Lidarr, Plex (Jellyfin not assumed). Media chat profile;
request/remove → proposals; posters lazy with static placeholders (A11y
§1.5); `not_configured` when a tool is absent; deep links.
**Acceptance.** Upcoming, recently added, and failing downloads shown;
"add this show" from chat → proposal → appears in the media manager;
honest states when a tool is absent.
**Tests.** Fixtures from real API samples; fake substitution; proposal
integration.

---

### P10 — Interests / Discovery

**CURRENT.** Candy-dispenser health probe only. **TARGET.** D6.
**Depends on.** P5. **Model.** GLM; FABLE for the derived-vs-canonical
boundary.

**Design.** `discovery` capability: native baseline RSS/Atom with explicit
follows (private runtime state); feedback `up / down / save / mute` stored
as explicit, inspectable preferences (canonical) plus a derived ranking in
the disposable index; candy-dispenser and Reddit as optional enrichment
adapters — the capability never depends on them; Interests chat profile
authors feed rules via proposals.
**Acceptance.** Following a source in Settings or chat yields items;
mute is visible and reversible; explicit rules are inspectable and
editable; deleting and rebuilding the index restores identical ranking
inputs.
**Tests.** Feed parser fixtures; feedback persistence; rebuild determinism.

---

### P11 — Memory, journal, lore, rewind

**CURRENT.** NDJSON journal, no search, no correction, no lore routes.
**TARGET.** D4.
**Depends on.** P5. **Model.** FABLE: memory model and lore boundary. GLM:
FTS, UI, adapter.

**Design.**

- Journal stays append-only NDJSON; corrections are appended
  `supersedes:<id>` / `redacts:<id>` events; views hide superseded entries;
  the audit line remains.
- Memory: `data/memory/**/*.md` with front-matter (`id, created, updated,
  classification, tags, project, supersedes`) as canonical; editor in UI;
  exports respect classification.
- Index: SQLite FTS5 under `data/index/`; `personal-world index rebuild`
  (proposed in this plan; not a current command);
  a `memory` capability contract so vector/semantic providers can enrich or
  replace acceleration (C-3).
- Lore: `lore` capability with a `rylee_lore` adapter that reads `lore/*.md`
  and claim states and can write a review-needed receipt through that
  project's contribution contract; **never promotes**.
- UI: "What changed?", "Where was I?", timeline, provenance drawer, search,
  cleanup tools.

**Acceptance.** Search finds a journal event and a memory note;
superseding hides the bad entry while the audit line remains; deleting and
rebuilding the index yields identical results; lore claims render with
state; a chat-suggested lore change lands as a candidate receipt, not
canon.
**Tests.** Supersede/redact semantics; rebuild determinism; adapter
read-only plus receipt path; export redaction unaffected.
**Contracts.** HR, PRB (lore is private), architecture lore-promotion rule.

---

### P12 — Settings depth and extensibility

**Depends on.** P2–P11 (accretes incrementally). **Model.** GLM.

**Groups.** Sections (order/visibility) · Providers & Models (P4 routing) ·
Vault backend (P3) · Integrations (P3/P8/P9/P10) · Approvals & Trusted
Actions (P5) · Reading & Interaction (existing prefs + D3 motion) · Themes &
Companions (P13) · Chat Profiles/Templates (P4) · Notifications · Custom
Cards (capability + view + filter) · Sessions & Recovery (P2) · Nerd-mode
default level.
**Acceptance.** Every finish-line Settings bullet has a persisted,
keyboard-operable control that takes effect without restart or code edit;
the accessibility floor still returns 400 on violation; all private values
land in private runtime files (C-1).

---

### P13 — Cuteness, themes, companions, motion

**CURRENT.** Static SVG companions; no poses; theme packs never applied;
motion cannot be enabled; both frontends functional but plain.
**TARGET.** Finish-line visual and emotional requirement; D3.
**Depends on.** P1 (continuous), P12 (final pass). **Model.** FABLE: art
direction, motion rules, new screen designs, acceptance review. GLM: pack
loader, CSS, state wiring.

**Design.** Apply theme packs (accent, poses, service icons) through
`ThemePackRegistry` → CSS variables and companion slots; ship the personal
pack from `design/` and serve it; companion state poses driven by real
events (hello on load, thinking during chat, celebrate on approved action,
sleep when quiet) — decorative only, `aria-hidden`, never announced (A11y
§7). Motion tiers per D3 with a CSS-lint test (≤300ms; no `infinite`; no
spin/pulse/ping/shake; OS reduced-motion wins). Micro-interactions,
empty-state art, typography rhythm, coherent light theme; nerd drawer
styled as first-class rather than an admin console. New screen designs for
Projects/Media/Interests/Lab/Vault approved by the owner before build.
**Acceptance (judged in the browser).** Side-by-side with
`design/screens/*.svg`; contrast passes in both themes; the product feels
alive with motion reduced; the owner's want-it-open-all-day judgment is a
criterion.
**Tests.** Contrast (axe); motion-off assertion; `aria-hidden` on all
companion art; live-region silence for companion states.

---

### P14 — CI, deployment, daily-use acceptance

**CURRENT.** CI = pytest + `framework validate` + `docker compose config`;
no lint, image build, browser tests, or CodeQL; compose contains
host-specific bind mounts and no `TZ`.
**Depends on.** Opens in P1, closes after P13. **Model.** DET/GLM; FABLE
reviews the acceptance walk.

**Design.** CI adds ruff, frontend build, digest-pinned image build,
Playwright + axe against the image, CodeQL, bundle budget, token-drift and
bundle secret-scan tests. `compose.yaml` becomes portable (host-specific
mounts move to `compose.override.example.yaml`; `TZ`; homelab tool mount
documented via `PW_LAB_CLI`). `docs/OPERATIONS-AUTH.md`. A **daily-use
acceptance checklist** walked by the owner on the real deployment with
journal evidence; STATUS/INDEX pointers updated.
**Acceptance.** CI green on `main`; `docker compose up` from a clean clone
plus private runtime config reaches login → OIDC → Today; checklist signed
off.

---

### Cross-cutting refactor lane

Split `api.py` into routers per domain (`status, journal, chat, vault,
identity, auth, prefs, apps, connections, source_control, forge, lab, media,
discovery, actions, sections`); delete the A5 duplicates; a single
`STANDARD_CAPABILITIES`. GLM performs the mechanical split once P0 is
green; FABLE reviews only the auth and secret routers.

---

## Part E — POST-FINISH / OPTIONAL

Voice (first post-finish enhancement) · mobile client (P2 keeps the door
open) · household multi-user and share-records UI · plugin marketplace ·
Lottie/Rive companion animation · Traefik rollups beyond health · vector
memory provider · interview onboarding · learned ranking beyond explicit
rules and feedback weights · Jellyfin adapter (only if observed).

---

## Part F — Coordination items (cross-repository work, not decisions)

- **C1 — homelab:** Traefik router for Project Worlds without Authelia
  forward-auth (Project Worlds performs OIDC itself), or exempt
  `/auth/local*` and `/healthz`. Register Project Worlds as an OIDC client
  in Authelia (redirect URI, PKCE, ID-token signing algorithm). Owned by P2.
- **C2 — homelab:** confirm `scripts/lab` verbs for logs/restart/redeploy
  and their JSON output schema; confirm the container mount location under
  `/opt` for the `PW_LAB_CLI` default. Owned by P8.
- **C3 — rylee_lore:** confirm the contribution/receipt interface is stable
  enough to be called from an adapter. Owned by P11.

---

## Part G — Remaining open decision

**Calendar provider for the first real proof.** Undecided (D5). The
`calendar` capability stays declared and `not_configured`; nothing blocks on
it. No provider code is written until the owner selects one.

---

## Part H — How to use this plan

1. Work one bounded task at a time in its own worktree
   ([`../AGENTS.md`](../../AGENTS.md)).
2. Before each task, load the contracts it names
   ([`../AGENT_CONTRACTS.md`](../../AGENT_CONTRACTS.md)) and re-inspect the
   code it touches; this plan describes intent, the code describes truth.
3. Every task ends with the truth report from
   [`../AGENT_POLICY.md`](../../AGENT_POLICY.md) (`CHANGED / VERIFIED /
   CONTRACTS / ACCESSIBILITY / OWNERSHIP,SECURITY / UNKNOWN / DEFERRED /
   NEXT`).
4. When a phase completes, update `.agent/STATE.md` and the
   [`../CHANGELOG.md`](../../CHANGELOG.md); do not duplicate the plan into the
   roadmap.
5. If the plan and the finish line disagree, the finish line wins; if the
   plan and a contract disagree, the contract wins; then fix the plan.
