# Project Worlds — Design Handoff (V0.1)

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see `.project/CURRENT.md`) · **Read this if:** you need the V0.1 design baseline and the accessibility/architectural intent behind today's product · **Superseded by:** `.project/CURRENT.md`

**In short:** the V0.1 design-stage handoff — product purpose, information architecture, status vocabulary, accessibility contract, and design constraints as they stood at commit `7c16a61`+. It is provenance now, not current product truth.

**What changed since:** the server-rendered `DASHBOARD_HTML` SPA it describes is gone (removed in the 2026-09-16 Station-only cutover, and the 2026-09-22 React `ui/` flip replaced the Station with the **Bridge** — `ui/src/app/App.tsx`); `/` now serves the Bridge home screen, not a redirect to `/station/`; themes ship as theme packages (`ui/THEMES.md`); `design/rylee-lab/tokens.css` (§J) no longer exists; Settings-write now exists (`PUT /api/prefs`, step-up gated), so §E's "not implemented" row is stale. Current product truth: [`.project/CURRENT.md`](../../.project/CURRENT.md).

(Formerly "Personal World" — product renamed 2026-09-12; the design it
describes is unchanged. Technical identifiers unchanged.)

**V0.1 design reference** (superseded sections are marked inline). **For: the Figma design stage.** This document describes the ACTUAL implemented product as of V0.1 (commit `7c16a61`+). It is sanitized: no credentials, no tokens, no personal journal contents, no private lore, no real indexer/client names. All examples below are either real structural output or clearly synthetic.

> **Target-state note:** this document remains the canonical V0.1 design-stage
> design reference. It is not the definition of the finished product.
> [`PERSONAL-WORLD-FINISH-LINE.md`](../PERSONAL-WORLD-FINISH-LINE.md) defines
> the current target daily-use experience. When the two describe different
> horizons, use this document to understand the baseline and the Finish Line
> to understand the destination; architecture, security, accessibility, and
> human-reliability contracts continue to govern both.

> **Implementation reconciliation (2026-09-10, kept as dated provenance):** the
> inventories, endpoint examples, auth experience, and "not implemented" labels
> below are the V0.1 baseline, not today's feature inventory. For current behavior
> use [Architecture](../ARCHITECTURE.md) and the canonical
> [responsive rules](../accessibility/RESPONSIVE_RULES.md) and
> [screen-reader walkthrough](../accessibility/SCREEN_READER_WALKTHROUGH.md).
> Historical screen proposals below do not supersede those sources or the
> accessibility contract.

Give this document plus the V0.1 final report to ChatGPT to produce
the Figma implementation brief.

---

## A. Product purpose

Project Worlds is the operator's **world-centric personal dashboard and
control surface** — the front door to her lab, designed to answer
*her* questions ("what matters today?") rather than to list
installed services.

More precisely, it is a **personal appliance**: one small
understandable tool that helps her run and understand her world.
The core experience is CLI + lightweight web interface + portable
state + journal/history + capabilities + optional providers. The
web interface is a friendly visual wrapper over the same core the
CLI/API uses — not a separate application architecture.

- **Serves:** exactly one person (the operator) plus her AI agents. Not
  multi-tenant, not a public product, but built on generic open-source
  core so the design must not hard-code the operator into it.
- **Makes easy:** one-glance world health, what needs attention,
  what changed, what her world discovered for her, and safe common
  actions — with all machinery (Gitea, Traefik, Komodo, gatus,
  Plex, candy-dispenser...) appearing as supporting cast, not as the
  navigation model.
- **Operator vs personal presentation:** today they are the same
  person. The world-centric hierarchy (section A.1) is the personal
  mode. Deep specialist operations (full Git client, Plex admin,
  Traefik configurator) are **delegated** — linked out, never
  recreated. Rule: *native when the task is about the user's World;
  delegate when the task is about operating the provider itself.*
- **Design target (the desired feeling):** a **calm, cute, highly
  legible personal control desk** — not a homelab homepage, not an
  enterprise admin console, not a collection of third-party
  dashboards. It should help the person understand: what matters /
  is everything okay / what changed / what did my world find / what
  am I working on / what can I safely do / what happened before /
  where is the specialist tool if really needed.

### A.0 Workflows over products (binding for design)

Project Worlds is not primarily an integration dashboard. It is a
small personal toolkit built around **understandable workflows**.
Design every surface by first asking *"what is the person trying to
know or do?"* — provider identity is provenance, secondary.

| Present this workflow | NOT this product UI |
|---|---|
| Git-ish workflow | Gitea UI |
| Safe secrets | Vault UI |
| Identity / access | Authelia UI |
| Service availability | Traefik UI |
| Deploy / update / rollback | Komodo UI |
| Reasoning / assistance | OpenWebUI UI |

External products may provide richer implementations of these
workflows; they do not define how Project Worlds presents them.

### A.0.1 CLI first; UI as another view

Every important concept must make sense without the web UI:

```text
pw status / pw daily / pw connect / pw update / pw backup / pw rollback
```

(and their `lab` aliases) describe the same World the web interface
renders. The UI may make workflows easier and more discoverable; it
must never become the only way to understand or operate the system.

### A.0.2 Simple before enterprise

Do not visually imply enterprise-scale infrastructure is required.
Auth, secrets, Git, AI, deployment, notifications present in the
smallest human-understandable terms appropriate to their jobs.
Advanced provider details belong in disclosure/detail surfaces or
specialist external tools. Avoid language and metaphors that
require understanding infrastructure products merely to use
Project Worlds.

### A.0.3 Local-first, external-capable

All of these configurations are equally legitimate and NONE may
look like the "real" one while others look incomplete:

```text
Project Worlds only / + local model / + cloud AI / + paid service /
+ self-hosted provider stack
```

An external provider ENRICHES a capability; it does not legitimize
it.

### A.0.4 Expansion without regression

A major product objective: **adding something new must not
destabilize what already works.** Make modularity visible. Connecting
an enrichment provider should read like:

```text
Source Control
  Basic
  ✓ Local repository tracking
  Connected enrichment
  ✓ Gitea — adds reviews, PRs, remote repository status
```

NOT like the section transformed into a Gitea application. If the
provider disappears, the concept remains and the UI honestly shows
reduced capability.

### A.1 Product direction (binding for design)

Project Worlds should be designed as a coherent personal
dashboard/control surface, **not as a prettier service launcher or
collection of embedded third-party admin panels.** Do NOT design the
IA around "one installed service = one card." The desired conceptual
hierarchy (final ordering is a design decision, not this list):

```text
TODAY        — what matters to me right now?
ATTENTION    — what actually needs me?
WORLD HEALTH — is my world okay?
CHANGES      — what changed?
ACTIVE THINGS— what am I working on / using?
DISCOVERY    — what did my world find for me?
QUICK ACTIONS— what can I do from here?
JOURNAL      — what has happened over time?
APPS/SERVICES— where are the specialist tools when I need them?
```

An Apps/Services surface still exists — for launching specialist
applications and provider diagnostics — but it is the bottom of the
hierarchy, not the primary model. The existing homepage service
launcher stays until Project Worlds proves itself through
dogfooding; Project Worlds neither depends on it nor reproduces it.

### A.2 Framework contract (normative for design)

The architecture is enforced by a conformance validator
(`personal-world framework validate`; `docs/NATIVE-BASELINE-AND-
ENRICHMENT.md` is the normative doc). Implications the design MUST
honor:

- **Capabilities are core-owned; providers implement or enrich
  them.** The UI presents capability concepts ("Source Control",
  "Ingress", "Discovery"), never vendor identities as the IA.
- **Native baseline, optional enrichment.** Every capability state
  the UI shows must be honest about: native-only, enriched,
  provider unavailable, provider not configured, or replacement
  provider swapped in — WITHOUT redesigning the concept. The
  manifest contract (`GET /api/manifest`) exposes exactly this:
  capability → contract, native_baseline (true/false), active
  provider, provider mode (native/enrichment/replacement),
  replaceable, and expected behavior when the last provider is
  removed. Design component states against the manifest vocabulary,
  not against specific vendors.
- **`native_baseline: false` with no provider is a VALID state**
  (e.g. source_control before any provider is connected): the
  capability concept exists; nothing is configured. Not a failure,
  not an error — design an honest "not configured" presentation.
- **Provider-neutral status vocabulary** (section D) is canonical;
  no vendor-specific UI is needed to understand health.
- **Modularity:** the design must make sense for a basic OSS
  install (zero providers) and the operator's highly integrated homelab
  without becoming two products. Density/presence of enriched
  sections adapts; structure does not.
- **Accessibility semantics are core-owned** (world state), not
  theme-owned or design-tool-owned. Any theme the design produces
  CONSUMES the accessibility preference contract; it never replaces
  it (section H).
- **Tool neutrality:** this handoff (markdown + `design/tokens.json`
  + the dashboard as executable reference) IS the canonical design
  contract. Figma may be the immediate workflow, but nothing in the
  product may depend on Figma IDs, variables, component keys, or
  APIs. Design output should map back to the canonical tokens, not
  become the source of truth.

---

## B. Actual information architecture (implemented today)

Single-page app at `/`, hash-routed. Server: FastAPI. No JS
framework; one HTML template string in `src/personal_world/api.py`
(`DASHBOARD_HTML`). All data via the same `/api/*` the CLI uses.

> **[SUPERSEDED 2026-09-16]** — the route table below describes the
> `DASHBOARD_HTML` SPA, deleted in the Station-only cutover; "implemented
> today" is no longer true. That cutover is itself superseded: `/` now serves
> the Bridge home screen in the React `ui/` app, not `/station/`. Kept verbatim
> as V0.1 baseline.

| Route | Purpose | Status | Primary tasks | Data source |
|---|---|---|---|---|
| `#today` (default) | daily briefing | implemented | glance health, attention list, recent journal | `/api/status`, `/api/daily`, `/api/journal?n=5` |
| `#world` | world state | implemented | inspect facts/intents/lore/actors | `/api/exports/world`, `/api/actors` |
| `#journal` | full history | implemented | read event history | `/api/journal?n=20` |
| `#settings` | exportable settings | implemented | review whitelist-safe settings | `/api/exports/settings` |
| — (nav) | Apps/Services, Quick Actions, Schedules | **not implemented** | — | future surface (see Q) |

Every view renders only real API response fields. Nothing on screen
is fake.

---

## C. Actual API/state model (UI-facing shapes)

Envelope everywhere: `{ok, status, changed, warnings, actions, data}`.

**GET /api/status → data:**

```json
{
  "facts": 13, "intents": 0, "policies": 0,
  "cemented_policies": 0,
  "lore": {"confirmed": 0, "derived": 0, "suggested": 0, "ephemeral": 0},
  "providers": 0, "packs": 0,
  "capabilities": {
    "memory": {"ok": true, "status": "healthy", "warnings": []},
    "discovery": {"ok": true, "status": "healthy", "warnings": []},
    "secrets": {"ok": false, "status": "not_configured", "warnings": []}
  },
  "actors": [
    {"name": "gitea", "role": "source_control", "provider": "gitea",
     "capabilities": ["source_control"], "status": "healthy",
     "secrets": "none", "writes": "none"}
  ]
}
```

**GET /api/daily →** envelope + `data: {world, capabilities,
attention[]}` where `attention` is a list of short strings (drift
items, provider states, "available not enabled" hints). Journal
events recorded during the run are retrievable via `/api/journal`.

**GET /api/journal?n= → data: [event]:**

```json
{"ts": "...", "kind": "observation", "summary": "capability x: healthy",
 "provenance": {"source": "daily-loop", "observed_at": "...",
                "provider": null, "authority": "observed"},
 "classification": "private"}
```

Kinds: `observation, health, drift, recommendation, approval,
reconciliation, provider_action, failure, pack_change,
settings_change, security, discovery`.

**GET /api/exports/world →** full facts/intents/policies/lore with
classification field on each record.

**GET /api/exports/settings →** whitelist-safe only:
`{schema, capabilities, packs, policies, accessibility}` — private
and secret material is structurally unable to appear.

**Memory search** `GET /api/memory/search?q=...` → provider-backed
recall results (private class; results are personal context).

**World concepts, not provider internals:** where a provider
surface exists, the API exposes semantic capability health
("discovery: healthy") rather than raw provider objects. Known gaps
recorded as design dependencies (section Q): e.g. no "ingress: 14
routes healthy / 1 cert needs attention" rollup yet — Traefik data
is not yet a capability.

---

## D. Status vocabulary (semantic, never color-only)

| State | Meaning |
|---|---|
| `healthy` | observed ok right now |
| `warning` | usable, something off |
| `unknown` | no data — NOT healthy, NOT failed |
| `needs_attention` | real problem, actionable |
| `unavailable` | provider unreachable/unresponsive — not necessarily failed |
| `stale` | observation too old to trust (explicit freshness contract) |
| `disabled` | configured off by user |
| `not_configured` | no provider wired — a vacancy, not a failure |

Rank (worst wins): healthy < warning < unknown < needs_attention <
unavailable < stale < disabled < not_configured. The UI MUST show the
status word; color (any tint) is reinforcement only.

---

## E. User actions

| Action class | Today | Confirmation | Notes |
|---|---|---|---|
| Read (status/daily/journal/exports) | implemented, zero mutation | none | all views read-only |
| Memory search | implemented | none | read-only recall |
| Daily loop run | implemented (on request via GET /api/daily) | none | journals observations |
| Lore promote to confirmed | CLI `cement` | explicit UserAction flag | user-only; AI can never |
| Cemented policy change | CLI | explicit UserAction flag | user-only |
| Pack install | CLI | normal | never overwrites user policy |
| Provider writes | none enabled (writes="none" everywhere) | — | future step-up-auth candidates |
| Settings write | **[SUPERSEDED]** implemented — `PUT /api/prefs` (step-up) | step-up auth | was "not implemented / future" at V0.1 |

Future step-up-auth candidates (not built): policy changes, provider
writes, secrets-broker use.

---

## F. Authentication experience

- **Unauthenticated browser** → Authelia SSO login (302 to the
  lab's auth portal, one_factor password, group:users).
- **After SSO** → dashboard shell loads; an inner bearer-token field
  gates `/api/*` (the proxy is never the only gate). Token persists
  in the browser session only.
- **Wrong/missing inner token** → inline "Authentication failed —
  check the token." (API returns 401; unconfigured server returns
  503 with "Auth not configured on the server.")
- **Backend down** → "Project Worlds is unreachable — the core may
  be down." (network error text).
- **Session failure** → API calls begin 401-ing; shell shows the
  auth-failed message again.
- **Future elevated auth** → arrives as Authelia policy change
  (two_factor for `world.*`), not new core code. Keep the flow
  design compatible with an SSO re-prompt without page redesign.

---

## G. Empty/loading/error states (design all of these)

- First run / empty world: all capabilities `not_configured`,
  "No providers connected yet." — world counts all zero
- No journal: "No journal entries yet."
- No attention items: "Nothing needs your attention."
- No lore / no facts: "World is empty — no facts or intents recorded yet."
- Provider loading: brief fetch window; status region shows "Loading…"
- Provider unavailable: capability row shows the status word
  `unavailable` — not an error page; the rest of the dashboard stays
- Partial data: per-capability states can differ in one view
- Stale data: `stale` status (V0.1: schema + API support; the
  dashboard does not yet render a "last observed" age — design
  dependency, see Q)
- Core error: full-page shell message (unreachable text)

---

## H. Accessibility contract (NON-NEGOTIABLE — the owner has(motion sensitivity, low reading load, limited fine motor control)

Implemented today (all verified in tests):

- Landmarks: `header`/`nav aria-label`/`main`; skip-to-content link
  first in tab order; `aria-labelledby` sections; one h1, no skipped
  heading levels
- Keyboard: all interactive elements tab-reachable; visible
  `:focus-visible` 2px outline; no traps; Enter activates
- Targets ≥ 44x44 CSS px everywhere
- Status = words, never color-only
- `prefers-reduced-motion: reduce` honored globally (nothing animates
  until opted in; the canonical preference defaults to `reduced`,
  and the OS reduced-motion requirement overrides application preferences)
- No text block > 3 lines outside disclosure/list; long strings
  wrap (`overflow-wrap: anywhere`); no horizontal page scroll
  (tables scroll inside labeled regions)
- `role="status" aria-live="polite"` load/result messaging
- Dark default; low-saturation light override via
  `prefers-color-scheme`
- Useful title ("Project Worlds — Today"), meaningful error text

Design must add: reading-load shaping (tables/lists over prose),
static layouts (predictable shape/position), no ALL-CAPS headers
(dyslexic word-shape flattening), font floor ~14px, and honor the
accessibility preference schema below.

**Accessibility preference schema** (in world/settings-export; the
presentation layer is one implementation of it — a theme must not
be the only way these apply):

```json
{"motion": "reduced", "contrast": "normal", "text_scale": 1.0,
 "density": "normal", "targets": "normal"}
```

Future: a secure personal accessibility interview flow (AI
assists/asks, user confirms; preferences portable in the user's own
world export per classification rules; never leak into another
person's template).

---

## I. Responsive requirements

Today: single max-width column (~48rem), works desktop-first, wraps
at narrow widths. No mobile-specific behavior implemented. Design
for: desktop (primary), narrow desktop/tablet (secondary), mobile
(planned — do not invent unsupported mobile interactions).

---

## J. Existing lab visual context (harmonize; do not copy assets)

| Asset | Status | Reference |
|---|---|---|
| `design/rylee-lab/tokens.css` (homelab repo) | **canonical house palette** | aubergine near-black surfaces `#0a0810`/`#12101a`, warm-pale text `#f0eaff`/`#a397b8`, mermaid-teal accent `#72b1b1`, dusty-rose `#b57f8b`, mascot pastels |
| Public [design handoff](../../design/handoff/README.md) and [asset collection](../../design/assets/README.md) | **high-value visual reference** for the operator's established design language | NOT canonical product truth. Canonical design truth is repo-owned: this document, `design/tokens.json`, accessibility semantics, status vocabulary, interaction contracts, implemented API behavior. Figma/Penpot/Sketch/Framer/code-first design all CONSUME those artifacts; any tool-specific output is derived work, never a required dependency |
| `lrw-theme/` (homelab) | canonical artwork (robots/stickers), Outfit/Geist/Geist Mono type | warm charcoal + dusty pink `#b87788` |
| `web/vefr-foundation.css` (vefr repo) | canonical a11y contract | 44px floor, motion-off, Atkinson Hyperlegible Next, contrast as band 8–10:1 (above 10:1 halates), 3 user contrast themes |
| OpenDyslexic (homepage global), Atkinson Hyperlegible (VEFR body) | sanctioned type choices | pick from this set; justify additions |
| Mermaid governance (`mermaid/README.md`) | personality rules | cute = presence (headers, empty states, footers), NEVER status, never animated on dense surfaces, always aria-hidden |

Key hard rules from the house style: contrast is a BAND (8–10:1),
not a floor; blue near 480nm is demoted (photophobia); flat surfaces
(no blur/glow); radius scale 4–16px; 120ms ease-out transitions
only, gated behind no-preference; personality never carries
operational meaning.

**Generic vs the operator-specific split:** the core repo ships neutral
dark defaults; the operator's skin (mascots, accents, microcopy) arrives
as a design pack — the Figma brief should specify both the generic
foundation and where the personal layer attaches.

---

## K. Personalization boundary

| Layer | Owns | Examples |
|---|---|---|
| generic core | structure, semantics, a11y contract, status vocabulary | routes, API, schema |
| accessibility preferences | per-user presentation contract | motion, contrast, text_scale, density, targets |
| user theme | colors/type within the a11y contract | house palette |
| the operator design pack | personality | mascots, microcopy, accent choices |

Figma can make it deeply personal without hard-coding the operator into
the generic app: personality slots must be pack-provided.

---

## L. Component inventory (implied by current app)

- global navigation (hash links, aria-current)
- Today summary (overall health sentence + counts)
- attention item (list row)
- capability status row (word + neutral border)
- provider/actor card (name, role, status, writes, secrets)
- drift item (intent vs fact mismatch — via daily attention)
- journal event row (time, kind, summary)
- lore entry (value + state word)
- settings table (whitelist export)
- empty state (per section, explicit text)
- error state (inline + full-page variants)
- auth gate (token field + status message)
- status region (aria-live)

Suggested additions for Figma to design (not implemented):
quick-action button, schedule/reminder row, discovery item
(candy results surfaced as world concepts), confirmation dialog
(for future write actions), apps/services launcher grid (bottom of
hierarchy).

---

## M. Data density

| View | Density |
|---|---|
| Today | glanceable — one-screen, status words, ≤5 attention items |
| World | moderately detailed |
| Journal | moderately detailed (dense when long) |
| Settings | operator-dense (tables) |
| future Apps/Services | glanceable grid, bottom of nav |

Do not assume all users want the operator-level density; the density
preference exists in the schema.

---

## N. Design constraints (hard lines for Figma)

1. Never encode status by color alone — the word is the signal.
2. Never make hover the only way to reveal important information.
3. Preserve keyboard usability and visible focus exactly as built.
4. Respect reduced-motion; nothing animates until opted in.
5. Never expose secrets, tokens, or private lore in any view.
6. Never make dangerous actions visually casual (future write
   actions need weight).
7. Do not turn every datum into a card.
8. Do not bury Today under operational telemetry.
9. No saturated reds/greens on status; luminance-only rank encoding.
10. No ALL-CAPS headers; no walls of text (>3 lines outside
    disclosure).
11. Do not default to a Homarr/Homepage/Heimdall service grid —
    the person's World is the IA, machinery is supporting cast.
12. Design workflows, not product UIs (A.0): a surface is
    "Source Control" or "Safe secrets", never a Gitea/Vault panel.
13. CLI parity: every concept must be understandable and operable
    without the web UI; the UI is a view, never the source of truth.
14. No configuration may look like the "real" one — Project Worlds
    only, + local model, + cloud AI, + paid service, and
    + self-hosted stack are all equally legitimate presentations.
15. Expansion without regression: enrichment must present as an
    add-on to a surviving concept (A.0.4), never as a takeover; if
    a provider vanishes, the concept degrades honestly.
16. No enterprise implication: smallest human-understandable terms;
    infrastructure vocabulary stays inside disclosures.
17. Cute sits ON TOP of the accessibility contract, never competes
    with it — personality lives in decorative slots only and never
    carries operational meaning.

---

## O. Reproducing current states locally

**V0.1 recipe — no longer accurate.** There is no `docker-compose.yml` in the repo
today; run the backend and the `ui/` dev loop as described in
[CONTRIBUTING](../../CONTRIBUTING.md). Kept verbatim as V0.1 baseline.

```bash
git clone <personal-world repo> && cd personal-world
export PW_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up -d          # standalone, no lab needed
open http://localhost:8000/    # use your private token
```

States to capture for reference: first-run empty world (fresh
volume), healthy-with-providers (add config/connections.json
entries), provider-unavailable (stop a provider), unauthenticated
(SSO redirect in lab; token prompt in dev). Screenshots should be
taken by the designer against a live instance; no screenshots are
embedded here to keep this document shareable.

---

## P. Open design questions (for the operator + Figma, NOT engineering)

- Visual identity: harmonize with the operator Lab aubergine/teal, LRW
  warm charcoal/pink, or a new Project Worlds personality?
- Navigation style: top nav vs sidebar vs segmented tabs?
- Default density: comfortable vs compact?
- Personality: mascot usage (mermaid? a new world-keeper
  character?), microcopy voice?
- Motion language (within the reduced-motion-first contract)?
- Today composition: single column vs bento?
- Operator vs personal mode: one surface or a toggle?
- Accessibility presets as one-click themes?
- How the Apps/Services drawer presents without becoming the IA?

---

## Q. Design dependencies / future engineering requirements
(not yet implemented; do NOT design them as if they exist)

- "Ingress: 14 routes healthy / 1 cert needs attention" style
  rollups — needs a Traefik capability provider (semantic seam
  recorded; the API currently exposes capability health only)
- Source-control concept rollups ("3 repositories changed today")
  — gitea adapter is health-only today
- Scheduler/reminder engine (schema exists; no runner)
- Accessibility-preference → CSS wiring (schema exists; dashboard
  renders defaults)
- "Last observed" age display for stale surfacing
- Quick actions (write-path + step-up-auth groundwork)
- Apps/Services launcher (needs an apps registry concept)
- Interview wizard (onboarding; accessibility-interview flow)

---

## R. Implementation boundaries

- Frontend: server-rendered single HTML string + vanilla JS (no
  framework, no build step, no external assets). Figma output should
  be handed back as design tokens + annotated specs against this
  structure; a future template engine is acceptable, a SPA rewrite
  is not required.
- Styling: inline `<style>` in the template today; design tokens
  should land as a CSS custom-properties file derived from the
  canonical `design/tokens.json` (repo-native, semantic,
  tool-neutral — the single token source; any design-tool token
  representation is derived from it, never the reverse).
- Manifest-driven components: status/provider components should
  render from `GET /api/manifest` + `/api/status` vocabulary rather
  than hard-coded provider lists, so a replacement provider or a
  native baseline never requires UI redesign.
- What can change freely: layout, type, color (within a11y
  contract), component shapes, copy.
- What must not change: status vocabulary words, the API contract,
  classification semantics, auth flow shape, keyboard/focus
  behavior.

*Sanitized for external design tooling. Intended for public design collaboration. Personal theme names and product
references are intentional; review all additions for sensitive data.*
