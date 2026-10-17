# P1 — Frontend Foundation Spec

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see `.project/CURRENT.md`) · **Read this if:** you need the approved 2026-09-10 P1 frontend-foundation contract and its task list. · **Superseded by:** `.project/CURRENT.md`.

**In short:** the approved 2026-09-10 implementation contract for the P1 frontend foundation (sections API, motion vocabulary, token generation, primitive contracts, parity gates). Kept for provenance; it describes the pre-2026-09-22 `frontend/` tree, which has since been replaced by `ui/` and the retired server-rendered Station (now a theme package).

**Parent:** [`../history/PERSONAL-WORLD-COMPLETION-PLAN.md`](../history/PERSONAL-WORLD-COMPLETION-PLAN.md) Phase P1.
**Gate:** P1 implementation does not start until the owner confirms P0.1
credential rotation, `main` is pushed, and CI is green for that exact SHA.

This is a bounded implementation contract. Tasks in §10 are sized for a
cheaper implementation model working against this document; a FABLE-class
review is required only where marked. No further design iteration is
expected unless implementation produces concrete evidence that contradicts
this spec — in that case, stop and record the evidence.

Settled decisions this spec obeys (do not reopen): React 19 + Vite ·
Tailwind may assist but never owns design truth · no client-side bearer
secret · `getAuthToken()`/`localStorage` is transitional until P2 ·
tracked repo holds examples/defaults, never the owner's runtime state ·
contextual chat is the target, standalone Chat is a parity/optional
destination · no Storybook (or React Query — §1.4) unless a bounded task
proves it removes more complexity than it adds · Vitest + Playwright + axe
+ token drift + bundle/secret checks are the baseline · no fake data
survives parity · no external fonts · accessibility contracts are
authoritative.

---

## 1. Ownership boundary

```text
design/tokens.json ──gen──► frontend/src/tokens.css   (only file where hex may appear)
docs/accessibility/*  ─────► primitive contracts (§5) ──► frontend/src/primitives/*
src/personal_world/api.py ► /api/*   truth, auth, prefs floor, sections
                          ► /        SPA index + fallback ─► frontend/dist  (React owns all pixels)
                          ► /fonts/* /companions/* /icons/sprite.svg   (existing routes, kept)
```

### 1.1 Backend owns
Truth, authentication, the preference floor (400s), the sections registry
and its persistence, serving of `dist/`, fonts, companion art, icon sprite.

### 1.2 Frontend owns
Rendering, routing, primitives, small explicit client caches. It holds
**no truth**: `localStorage["pw_prefs"]` is deleted; preferences come from
`GET /api/prefs` and are applied to `<html data-pw-*>` before content
paints.

### 1.3 Directory and serving
- `frontend-v2/` → `frontend/` (git mv of source only; `dist/`,
  `node_modules/`, `.env*` never tracked — enforced by `.gitignore` and
  `tests/test_public_safety.py`).
- `PW_FRONTEND` = `legacy` (default **during** P1) | `react`.
  `PW_FRONTEND_DIST` overrides the dist path (dev default
  `<package>/../../frontend/dist`; image default `/app/frontend/dist`).
- React mode: `GET /` and any non-`/api`, non-asset GET → `index.html`;
  `/assets/*` served with immutable cache headers. Dist missing → **503**
  HTML "Personal World's interface is not built" (honest state, not a
  crash). `index.html` never embeds a token, principal, or prefs — the
  app fetches them.
- The parity commit (T15) flips the default to `react`, deletes
  `DASHBOARD_HTML`, `SETUP_HTML`, `WIZARD_HTML`, `LOGIN_HTML`, the
  server routes `/setup`, `/setup-wizard`, `/login`, and the `legacy`
  value.
- Dockerfile: stage 1 `node:22-alpine` (`npm ci && npm run build`);
  stage 2 = existing python image, `COPY --from=frontend /build/dist
  /app/frontend/dist`, `ENV PW_FRONTEND=react` (set in T15).
- Router basename `/`; `vite.config.ts` `base: "/"`; dev proxy `/api`,
  `/healthz`, `/fonts`, `/companions`, `/icons` → `:8000`.

### 1.4 Lean dependencies (owner correction)
Foundation = React, react-dom, react-router-dom, Tailwind v4 (+vite
plugin), `clsx`. Test = Vitest, `vitest-axe`, Playwright,
`@axe-core/playwright`. **Removed:** Storybook and every `@storybook/*`,
Chromatic, `@tanstack/react-query`, `class-variance-authority`,
`tailwind-merge`, `lucide-react` (sprite is the icon system), template
cruft. `oxlint` stays only if `npm run lint` is wired into CI in T4;
otherwise removed.

Data access = one typed fetch client (§1.5) + ordinary hooks. A small
`lib/cache.ts` (`Map` keyed by URL, TTL, `invalidate(prefix)`) may be
added only where a screen demonstrably re-fetches the same resource. Any
later proposal to add React Query (or similar) must be a bounded task
whose report shows removed complexity (dedupe/invalidation/retry code
deleted) exceeding the added surface.

### 1.5 Transitional auth (until P2)
`/login` React route; token in `localStorage["pw_token"]` (legacy key, so
existing browsers keep working); one `getAuthToken()` in `lib/api.ts`;
`401` → `/login`; `503` with `auth_configured=false` → `/setup`. Writes
send `X-PW-StepUp: 1` exactly as the legacy dashboard does, through a
single `stepUp()` helper so P2 removes it in one place. **No
`import.meta.env` value may ever be a credential** — the only permitted
key is `VITE_API_URL`; P0.7's scanner and a `dist/` scan enforce it.

---

## 2. Sections

### 2.1 Registry (tracked code — defaults, never the owner's state)
`src/personal_world/sections.py`:

```python
@dataclass(frozen=True)
class SectionSpec:
    id: str
    label: str
    icon: str                         # sprite symbol id (must exist in icons/manifest.json)
    default_order: int
    default_visible: bool = True
    pinned: bool = False              # cannot be hidden; may be reordered
    kind: Literal["core", "transitional", "extension"] = "core"
    capabilities: tuple[str, ...] = ()  # informs `configured`/`status`; never hides

SECTIONS = (
  SectionSpec("today",     "Today",            "navigation--today",    0),
  SectionSpec("interests", "Interests",        "navigation--discover", 1, capabilities=("discovery",)),
  SectionSpec("media",     "Media",            "navigation--media",    2, capabilities=("media",)),
  SectionSpec("projects",  "Projects",         "navigation--projects", 3, capabilities=("source_control",)),
  SectionSpec("lab",       "Lab",              "navigation--lab",      4, capabilities=("homelab_health",)),
  SectionSpec("journal",   "Journal & Memory", "navigation--journal",  5, capabilities=("journal",)),
  SectionSpec("vault",     "Vault",            "navigation--vault",    6, capabilities=("secrets",)),
  SectionSpec("chat",      "Chat",             "navigation--chat",     7, kind="transitional",
                                                                          capabilities=("reasoning",)),
  SectionSpec("settings",  "Settings",         "navigation--settings", 8, pinned=True),
)
```

**Pinning (owner decision 1):** only `settings` is pinned — it is the
recovery/configuration surface and must always be reachable. `today` is
visible by default and strongly preferred but may be hidden or reordered
like any other user-facing section. Settings exposes a plainly labeled
**"Restore default sections"** action (`PUT {"order": [], "hidden": []}`).
Nothing may ever make every section hideable such that the recovery path
disappears; the pinned rule is enforced server-side (400).

Icon ids are checked against `design/assets/icons/manifest.json` by a
test. If a name is missing, T1 substitutes the closest existing glyph and
records the substitution in its report — no new artwork in P1.

### 2.2 Persistence (private runtime, per person)
New pydantic field `World.layout: dict[str, Any] = {}` (additive; schema
version unchanged; `init.py` untouched). Stored as
`layout["sections"] = {"schema": "personal-world/sections/1",
"order": [ids], "hidden": [ids]}` in the caller's `world.json` via the
existing `_user_paths()` (single: `data/world.json`; multi:
`data/users/<id>/world.json`). Classification `world` (in `world-export`,
never in `settings-export`). Never in tracked `config/`.

### 2.3 `GET /api/sections` — `require_auth`, persons only
```json
{"ok": true, "data": {"schema": "personal-world/sections/1", "sections": [
  {"id": "today", "label": "Today", "icon": "navigation--today", "order": 0,
   "visible": true, "pinned": false, "kind": "core",
   "configured": true, "status": null},
  {"id": "media", "label": "Media", "icon": "navigation--media", "order": 2,
   "visible": true, "pinned": false, "kind": "core",
   "configured": false, "status": "not_configured"},
  {"id": "lab", "label": "Lab", "icon": "navigation--lab", "order": 4,
   "visible": true, "pinned": false, "kind": "core",
   "configured": true, "status": "unavailable"}
]}}
```

Merge rule: start from stored `order`; drop unknown ids; append registry
ids missing from `order` in `default_order`; `visible = id not in hidden`
(pinned ⇒ always `true`; `default_visible=False` ⇒ hidden until the user
shows it).

**Status vocabulary (owner correction 1 and 2):** `status.py` owns the
closed vocabulary. For a section with **no** capability dependency,
`status` is `null` — never an invented value such as `"n/a"`. For
sections with dependencies, `status` = the worst canonical status among
their capabilities from `registry.status_map()`.
`configured = status is null or status not in {"not_configured",
"disabled"}`. `configured` answers "is something wired up?"; `status`
answers "how is it doing?". Neither affects navigability: a failing or
unconfigured provider **never** removes a section; the route renders an
honest `EmptyState`/`ErrorState`. `StatusChip` receives only canonical
statuses; a `null` status renders no chip.

### 2.4 `PUT /api/sections` — `require_step_up`, persons only
Body `{"order": [...], "hidden": [...]}` — either key optional (omitted
keeps stored). Validation errors are collected and returned together as
one `400`: unknown id; duplicate in `order`; pinned id in `hidden`;
non-list values. Journals `SETTINGS_CHANGE "sections layout updated"`.
Returns the `GET` shape. `{"order": [], "hidden": []}` resets to defaults.

### 2.5 `GET /api/prefs/schema` — `require_auth`
Read-only: `{key: {type, default, floor, allowed}}` derived from
`prefs.PREFS`, so Settings can never offer a value the server rejects.

---

## 3. Preferences: motion vocabulary (owner decision 2)

`prefs.py`: `MOTION = EnumPref(key="motion", default="reduced",
allowed=("off", "reduced", "subtle"), floor="off", ...)` — ordered most→
least restrictive so the index-based floor admits all three.

| Value | Meaning |
|---|---|
| `off` | No nonessential animation. No ambient/idle movement. No decorative pose transitions. State changes remain understandable without motion. |
| `reduced` (**default**) | No continuous/ambient animation. Immediate or effectively instant state/pose changes allowed. No motion required to understand state. |
| `subtle` | Opt-in only. Transitions ≤300ms. Ambient movement ≤2px where allowed. No pulse/spin/shake/flash. Never required for meaning. |

CSS emission (`prefs_style_block` + `tokens.css`):
`--pw-motion-duration` = `0ms` (off, reduced) / `200ms` (subtle);
`--pw-motion-ambient` = `0` (off, reduced) / `1` (subtle);
`[data-pw-motion="off"]` additionally disables pose *transitions* (poses
switch instantly, no crossfade) — the distinction from `reduced` is that
`reduced` may still snap between poses while `off` shows a single static
pose. **Unconditionally:** `@media (prefers-reduced-motion: reduce) { *
{ animation: none !important; transition: none !important } }` and
`--pw-motion-ambient: 0` — the OS setting overrides any application
preference and suppresses subtle animation.

`docs/accessibility/PREFERENCES_SCHEMA.json` is reconciled to exactly
this vocabulary and these definitions; a test asserts schema values ==
`prefs.py` allowed values. A CSS lint test over `frontend/src/**/*.css`
and `tokens.css` fails on `infinite`, `spin`, `pulse`, `ping`, `shake`,
`flash`, or any duration `> 300ms`.

---

## 4. Token generation

- `frontend/scripts/gen-tokens.mjs` (no dependencies): `design/tokens.json`
  → `frontend/src/tokens.css`. `color."surface.canvas"` →
  `--pw-color-surface-canvas`; `light.*` under `[data-pw-theme="light"]`
  and `@media (prefers-color-scheme: light)` when no explicit theme;
  `targets.*` → `--pw-target-minimum` / `--pw-target-large`; `spacing.*`,
  `typography.*`; `focus.ring` → `--pw-focus-ring`.
- **Design-truth correction (one line, cite A11y §2.4):** `tokens.json`
  `focus.ring` currently references `text.primary`; the contract and the
  legacy CSS use `accent.primary` (teal) in comfortable mode and white in
  high contrast. T3 changes `focus.ring` to `"2px solid accent.primary,
  offset 2px"` and adds `focus.ring_high_contrast: "2px solid #FFFFFF,
  offset 2px"`.
- Generated file is committed; `npm run tokens:check` regenerates to
  memory and diffs → CI fails on drift.
- Tailwind v4 `@theme` **only** aliases `--pw-*` variables; no literal
  colors in config or classes (`bg-[#…]` fails the hex test).
- Hex/`rgb(` literal test over `frontend/src/**/*.{ts,tsx,css}` and
  `index.html`: only `tokens.css` may match.
- Status tints: none exist in `tokens.json` (luminance-only rule).
  `frontend-v2`'s `--color-ok/warn/err` and saturated badge variants are
  removed. If P13 wants status tints they enter `tokens.json` first.
- Fonts: `@font-face` for Instrument Sans and Young Serif pointing at the
  existing `/fonts/*` route; Google Fonts `<link>` removed; Playwright
  asserts zero cross-origin requests.

---

## 5. Primitive contracts (`frontend/src/primitives/`)

Common rules: TypeScript strict; no hex; interactive targets
`min-height/min-width: var(--pw-target-size)`; focus ring `2px solid
var(--pw-focus-ring)`, offset 2px; each primitive ships a Vitest file with
an axe run and keyboard tests; no primitive announces companion state.

| Primitive | Semantics and behavior | Props (minimum) | Must not |
|---|---|---|---|
| **Dialog** | Native `<dialog>` via `showModal()`. Focus trapped by the platform; initial focus on the **safe** action (default Cancel); `Escape` = cancel; explicit close button named "Close <title>"; `aria-labelledby` = title `h2`, `aria-describedby` = body; focus returns to the invoker on close; background inert. `danger` variant: confirm label is the verb; body names consequence and provider (A11y §4.4). | `open, title, description?, onCancel, onConfirm?, confirmLabel, danger?, initialFocus: "cancel"\|"confirm"` | render `div` modals; use OK/Yes/Proceed; autofocus the destructive action |
| **Drawer** | Non-modal `<aside role="complementary" aria-labelledby>`; on open focus moves to its heading; `Escape` closes and focus returns to the trigger; background stays interactive. Below 600px it becomes a modal bottom sheet (composes Dialog) per A11y §3.5. Hosts provenance/detail and the World Assistant (heading "World Assistant"). | `open, title, onClose, side: "right"\|"bottom", children` | trap focus on desktop; steal focus on content refresh |
| **Popover** | Native `popover="auto"` + `popovertarget`; trigger carries `aria-expanded`; light-dismiss and `Escape`; focus returns to trigger; contents are ≥44px targets. Menus and small pickers only. | `trigger, children, placement?` | hold destructive actions; be the only path to any function |
| **LiveRegion** | One app-level `<div role="status" aria-live="polite" aria-atomic="true">`. `announce(message, {key})` batches: messages inside a 30s window merge into "N updates: …" (A11y §8.3); allow-list of kinds (health change, attention resolved, action completed, error); dedupe by key. Exposed as `useAnnounce()`. | — | announce poll ticks, timestamps, provider observations, companion states |
| **StatusChip** | `<span class="chip" data-status>` containing the **status word** (canonical `status.py` vocabulary, humanized by one map) plus optional label; rank encoded by luminance only; `title` = raw status. Receives only canonical statuses; callers pass nothing for `null`. | `status, label?, size?` | encode meaning by hue; accept invented statuses |
| **Disclosure** | `<details><summary>` with `aria-controls`; levels 1–4 (glance → technical) nest; summary is a ≥44px target. `TechnicalDetails` preset = Level 4 (provider, model, latency, raw). | `summary, level, defaultOpen?, children` | hide Level-1 truth behind a click; animate beyond the motion tier |
| **CompanionSlot** (owner correction 3) | Two **sibling** parts, never nested: (a) artwork `<span aria-hidden="true"><img alt="" src="/companions/<companion>.svg"></span>`; (b) when `asAssistantTrigger`, a separate `<button>` whose only accessible name is **"Open World assistant"** — it is **not** inside any `aria-hidden` subtree. Reads the `companion` pref; sizes `micro\|nav\|inline\|empty\|error` per COMPANION_INTEGRATION. Companion off removes part (a) only; the trigger and its function remain. Poses (P13) are decorative and unannounced. | `size, pose?, asAssistantTrigger?, onOpenAssistant?` | wrap the trigger in `aria-hidden`; carry information; be focusable itself; announce |
| **StepUpPrompt** | Dialog preset explaining *why* elevation is needed and naming the action. P1 (transitional): confirm re-sends the request with `X-PW-StepUp: 1`. P2 replaces the confirm body with password/IdP re-auth **without changing the component API**. `useStepUp()` returns `withStepUp(fn)` that catches `403 step_up_required` and opens the prompt. | `action, reason, onElevated` | store or display credentials; be bypassable by "remember" |

Shell components (P1, not primitives): `AppShell` (skip link first,
`header`, `nav aria-label="Main"` rendered as rail ≥900px / banner
600–899px / bottom bar <600px with `env(safe-area-inset-bottom)`,
`main#main-content`, Drawer mount), `SectionNav` (from `GET
/api/sections`; `aria-current="page"`), `EmptyState` (honest
`not_configured`/`unavailable`, names the capability and the
configuration knob, never a mount path), `ErrorState` (names what failed
and what still works — A11y §4.5), `Login`, `SetupWizard` (one flow:
token ≥8, optional vault passphrase, companion, world name).

---

## 6. Standalone Chat — transition rule

`chat` is `kind: transitional`, visible by default in P1 so parity is
provable (send, thinking status, provenance, retry, history, provider
info). Its screen is a component, `ChatPanel`, mounted in a route; **the
same component** is what the World Assistant Drawer hosts in P4 with a
context profile. No chat logic lives in the route file. After P4,
`default_visible` flips to `false`; showing/hiding is `PUT /api/sections`,
never a migration. Nav code may not assume Chat exists.

---

## 7. Parity checklist — gate to delete the legacy HTML

Every row is a Playwright test unless marked HUMAN.

| # | Legacy behavior | React proof | API |
|---|---|---|---|
| 1 | Today: health sentence, attention, "what changed", journal composer + recent, "More from your world" (Services, Subscription usage, Capabilities) | all from real data; a quiet day shows no green list | `/api/status`, `GET /api/daily`, `/api/journal`, `/api/apps`, `/api/lab/state` |
| 2 | Services launcher + inline add (step-up) | add → appears; keyboard only | `PUT /api/apps` |
| 3 | Lab table with per-row provenance | rows + Disclosure L4; honest `not_configured` naming `PW_LAB_CLI` when absent | `/api/lab/state` |
| 4 | Journal kind filters (`aria-pressed`), load more (`n=`), provenance | same | `/api/journal?n=` |
| 5 | Vault status, unlock, **lock**, names, set, delete | all wired; values never rendered | `/api/vault/*` |
| 6 | Settings: prefs (server-validated), companion, reminders add/toggle/delete, capability table | options from `/api/prefs/schema`; server 400 shown specifically; **Sections order/visibility + "Restore default sections"** | `/api/prefs`, `/api/prefs/schema`, `/api/themes`, `/api/reminders`, `/api/sections` |
| 7 | Chat: send, thinking text, provenance, retry/keep writing, sessionStorage history, provider info | via `ChatPanel` | `/api/chat`, `/api/chat/providers` |
| 8 | Setup: token, optional vault passphrase, companion, world-name fact, login deep-link on fresh install | one wizard | `/api/setup`, `/api/world/fact`, `/api/prefs` |
| 9 | Login token entry → `/` | `/login`; `401` anywhere → `/login` | — |
| 10 | Prefs applied without flash: `data-pw-*`, `--pw-*`, 44px floor, reduced-motion query | attrs present after load; `text_scale=1.5` visibly larger | `/api/prefs` |
| 11 | Skip link first; landmarks header/nav/main/complementary; one visible `h1`; `aria-current` | axe + DOM assertions every route | — |
| 12 | Rail ≥900 / banner 600–899 / bottom bar <600; safe-area inset | screenshots; no horizontal scroll at 1440/900/600/375 | — |
| 13 | Status never color-only | DOM assertion over all `.chip` | — |
| 14 | Companion artwork `aria-hidden`; assistant trigger labelled and **outside** the hidden subtree | DOM assertion (§5 CompanionSlot) | — |
| 15 | No fabricated content (fake "Recent Changes", hard-coded providers/timezone/version/host, `/api/icons/upload`, `console.log`) | grep test over `frontend/src`; zero console errors | — |
| 16 | No external requests; no Google Fonts | request interception | — |
| 17 | Bundle ≤350 KB gzipped; zero secret shapes in `dist/`; only `VITE_API_URL` in `import.meta.env` | size test; P0.7 patterns over `dist/**` | — |
| 18 | **200% zoom / reflow (owner acceptance correction)** | Automated **proxies**: (a) `document.documentElement.style.zoom = "2"` reflow stress; (b) viewport 720×450 at 1440-layout (what 200% browser zoom yields in CSS px). Both labelled *proxy*. **HUMAN, required:** real browser zoom 200% on the deployed React build — no page-level horizontal scroll, no clipped controls, navigation operable, dialogs/drawers reachable, no overlapping/truncated essential text. Recorded in the P1 truth report; CSS zoom alone never satisfies A11y §6.4. | — |

Retired with the deletion commit (T15): `test_dashboard.py` structural
tests, `test_prefs.py::TestDashboardPrefsPlumbing`, `test_setup_wizard.py`
structure, `test_lab_panel.py::test_dashboard_wires_the_panel`,
`test_services_notes.py::test_dashboard_has_services_and_composer`,
`test_framework.py::test_dashboard_is_repo_native` (replaced by "dist is
repo-built; tokens derive from tokens.json"). Every server-side floor and
API test stays.

---

## 8. Acceptance gates (CI from P1 onward)

- `frontend` job: `npm ci` → `npm run tokens:check` → (lint if wired) →
  `npx vitest run` (primitives + axe, hex scan, motion lint, no-fake
  strings, api error mapping) → `npm run build` → gzip size assert →
  `dist/` secret scan.
- `browser` job: build image (or `uvicorn` + `dist`), `PW_API_TOKEN=
  ci-token`, complete setup via API, Playwright over every section route
  × {1440, 900, 600, 375}; `@axe-core/playwright` 0 serious/critical;
  focusable `boundingBox ≥ 44×44`; keyboard walk of nav and Settings;
  zoom proxies (§7 row 18); cross-origin requests = 0; console errors = 0.
- Existing `test`, `framework-gates`, `security-gates`, `compose` jobs
  unchanged; `public-safety` already covers tracked `frontend/` source.
- Human gate: row 18 real-zoom check plus one walk of rows 1–9 by the
  owner on the deployed build. Owner's "feels like mine" judgment is
  recorded but is P13's criterion, not P1's.

---

## 9. Dependency order

```text
T0 spec  ─► T1 sections API ─┐
           T2 motion vocab  ─┼─► T9 shell ─► T10 Today/Journal/Vault ─┐
           T3 serving/Docker─┤              T11 Settings+Sections    ─┼─► T14 purge/limits ─► T15 cutover ─► T16 reconcile
           T4 repo/deps ─► T5 tokens ─► T6 api client ─► T7 prims A ─► T8 prims B ─┘
                                                                     T12 Chat/Login/Setup ─┤
                                                                     T13 section stubs   ─┘
```
T1–T4 are independent; T10–T13 run in parallel worktrees after T9.

---

## 10. Bounded tasks

One worktree commit each via `scripts/safe-commit.sh`; own tests; truth
report per `AGENT_POLICY.md`. FABLE review required for T1, T3, T9, T15,
T16; the rest are GLM-autonomous against this spec.

| # | Task | Depends | Acceptance |
|---|---|---|---|
| T0 | This spec persisted; INDEX row | — | `test_docs` — **done with the approval commit** |
| T1 | `sections.py` registry; `World.layout`; `GET/PUT /api/sections` per §2 (status `null` for no-capability sections, `configured`, settings-only pin, reset); `GET /api/prefs/schema`; icon-id test | — | ≥14 API tests: merge rule, unknown/dup/pinned-hidden 400, `today` hideable, `settings` not, `null` status, `configured` vs `status` matrix, per-user in multi, journal event, reset |
| T2 | Motion `off\|reduced\|subtle` in `prefs.py`; CSS emission per §3; `PREFERENCES_SCHEMA.json` reconciled; schema-equality test; motion CSS lint test (backend side for `prefs_style_block`) | — | prefs tests updated; default stays `reduced`; OS override present unconditionally |
| T3 | `PW_FRONTEND` switch + dist serving + 503 (default `legacy`); `tokens.json` focus-ring correction; Dockerfile multi-stage build (image still boots legacy) | — | tests: legacy default byte-identical; react mode serves index; 503 honest; `/api/*` untouched; image builds in CI |
| T4 | `git mv frontend-v2 frontend`; dependency diet per §1.4 (remove Storybook, Chromatic, React Query, cva, tailwind-merge, lucide, template cruft, Google Fonts); `base:"/"`; Vitest/vitest-axe/Playwright/axe deps; scripts | T3 | `npm ci && npm run build` green; `package.json` contains none of the removed packages |
| T5 | `gen-tokens.mjs`, `tokens.css`, `tokens:check`, Tailwind `@theme` aliases, hex-literal test, `@font-face` via `/fonts/*`, motion lint test | T4 | drift test; 0 hex outside `tokens.css`; lint passes |
| T6 | `lib/api.ts`: `getAuthToken()` (`pw_token`), `stepUp()` single point, typed envelopes, 401/503 routing; replace React Query hooks with plain hooks (+ `lib/cache.ts` only if a screen needs it — report must justify); delete `pw_prefs` localStorage | T4 | Vitest error mapping; grep: `import.meta.env` only `VITE_API_URL`; no `@tanstack` import |
| T7 | Primitives A: `Dialog`, `Popover`, `LiveRegion` + tests | T5 | axe 0; keyboard tests; batching test (3 → 1 merged) |
| T8 | Primitives B: `Drawer`, `Disclosure`, `StatusChip`, `CompanionSlot` (sibling artwork/trigger per §5), `StepUpPrompt` + tests | T7 | axe 0; StatusChip luminance-only; CompanionSlot: trigger is in the a11y tree, artwork is not, companion-off keeps trigger |
| T9 | `AppShell`, `SectionNav` from `/api/sections` (hidden sections omitted from nav, routes still resolve), responsive cascade, skip link, landmarks, `EmptyState`/`ErrorState`, prefs → `<html data-pw-*>` before content | T1, T8 | §8 browser gates on empty-state build of all 9 routes |
| T10 | Screens I: Today (rows 1–3), Journal (4), Vault (5) | T9 | rows 1–5 |
| T11 | Screens II: Settings — prefs from schema, companion, reminders, capability table, **Sections panel** (Move up/down, Hide/Show buttons, no drag; "Restore default sections") | T9 | row 6; reorder + hide `today` persists across reload; `settings` shows no Hide control |
| T12 | Screens III: `ChatPanel` + transitional Chat route (7); Login (9); single SetupWizard (8) | T9 | rows 7–9 |
| T13 | Section stubs: Interests, Media, Projects, Lab (Lab = real table; others honest `EmptyState` naming the capability) | T9 | axe; empty-state copy test (no mount paths) |
| T14 | Fake-data purge (15), no-external test (16), bundle size + dist secret scan (17), zoom proxies (18a/b) | T10–T13 | rows 15–18 automated parts |
| T15 | Parity run + cutover: default `react`; delete four HTML constants, `/setup*`, `/login` server routes, dead JS; retire listed tests; docs (`OPERATIONS.md`, `ARCHITECTURE.md`, `DESIGN-HANDOFF.md` scope note, `RESPONSIVE_RULES.md` if the cascade changed) | T14 + **HUMAN row 18** | full checklist green in CI; `api.py` loses the inline HTML; suite green |
| T16 | Reconcile `.agent/STATE.md`, `CHANGELOG.md`, completion plan P1 complete | T15 | `test_docs` |

---

## 11. Acceptance tests (what proves P1 done)

- Backend: `tests/test_sections.py`, updated `tests/test_prefs.py`,
  `tests/test_frontend_serving.py`, `tests/test_dist_safety.py` (skips
  locally without a build; required in CI).
- Frontend: Vitest per primitive (+axe); `tokens.spec`, `no-hex.spec`,
  `motion-lint.spec`, `no-fake-strings.spec`, `api-errors.spec`.
- Browser: `frontend/e2e/*.spec.ts` = checklist rows 1–17 and the two
  zoom proxies, across four viewports.
- Human: row 18 real 200% zoom on the deployed build; one walk of rows
  1–9 by the owner. Both recorded in T15's truth report.

## 12. Open decisions

None for P1. The only open decision in the programme remains the calendar
provider (completion plan Part G).
