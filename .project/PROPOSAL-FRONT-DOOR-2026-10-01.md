# Proposal: Worlds as the universal front door (2026-10-01)

> **Status:** APPROVED 2026-10-01 with owner refinements (see HANDOFF-FRONT-DOOR-APPROVAL-2026-10-01.md). Owner: Rylee. Revision 3 (refine-only
> round, 2026-10-01). Claude drafted it from a full backend, UI and
> provider-machinery inventory, an open-source survey, three owner review rounds,
> the owner's Figma Make prototype and an interactive design lab. Nothing here is
> implemented. Production code stays untouched until this is approved. If approved,
> it supersedes `.project/PLAN.md` Step 1c onward and every decision listed in
> Superseded decisions, and it gets ADR-0008 (draft wording below) plus a
> `DECISIONS.md` entry.

## North star

The two owner-approved principles:

> "Worlds owns meaning. Providers own mechanics."
>
> "Worlds is a small personal front door that gathers a large world without
> having to contain the whole world."

You register a **provider**. A provider is any HTTP API, a service that speaks room/0,
and later MCP. You then list what it offers, query it, test it and save the request.
A mapping gives the result a human meaning, and a card presents it. Boards of cards
make up Home and any personal sections. Memory stays a core Worlds concept with a
deterministic local baseline, and providers only enrich it. Personality (Station,
crew, Sol, lore) is an optional experience pack layered over a fixed structure.

## What the UI test taught us

The Make prototype mixed two architectures in one product.

| Keep: the human-facing parts of Worlds | Relocate: provider plumbing that leaks into the product |
|---|---|
| A calm Home/Bridge orientation | Every room knows about APIs and providers |
| "What needs me?" | Rooms expose API and Learn tabs directly |
| Useful destinations | Systems owns Providers, Variables, Connections and Health |
| A dark, warm visual language with a strong sense of place | Provider configuration starts to define what Memory, Projects, Hive and Journal *are* (Memory = Supabase + Pinecone + Claude) |
| Personality without needing technical knowledge | Achievements, rank and Station terms become structural instead of optional |

This revision keeps the left column and moves everything in the right column into Connect.

## Why now: what the inventory found

| Fact | Evidence |
|---|---|
| The backend is 41.8k LOC and 228 routes; `api.py` alone is 6.1k LOC and 192 routes | wc + route grep |
| Only about 1.4k LOC of route body serves the front-door core | backend inventory |
| About 2.5k LOC of `discovery/` is dead (the old candy-dispenser engine; nothing imports it) | import graph |
| The auth stack is about 5.3k LOC: about 1.1k needed for one owner, about 2.4k multi-user, about 1.6k OIDC | backend inventory |
| There are 17 UI screens, 10 of them persona or feature screens | UI inventory |
| Connection test, save and schema hooks exist, but no screen uses them | `ui/src/data/hooks.ts` |
| Overlapping machinery: about 7 partial "generic HTTP" primitives, 2 provider registries that disagree, 3 approval models, 3 capability lists | provider inventory |
| There is no request runner, no saved requests, no OpenAPI import and no MCP client | grep |
| `rooms.py` is the one solid generic layer | provider inventory |

The core structure is sound. Most of the size comes from integrations and persona
features built into core. No rewrite is needed. The fix is one generic substrate that
replaces many domain-specific integrations.

## The model

```
Provider → Request → Mapping → Card → Board
                │
                └→ Governed Action → assistant / automation
```

| Layer | Owns | Examples | Stored as |
|---|---|---|---|
| Provider | connectivity | Project Home, Sonarr, a Gatus health API, a room/0 service, the reference provider; MCP later | `providers/<id>.yaml` |
| Request | transport mechanics | `GET /queue`, `GET /projects?status=active`, a POST action; parameters, assertions, TTL | `requests/<provider>/<id>.yaml` |
| Mapping | human interpretation; the seam between external data and Worlds' meaning | `concept: media.downloads`, fields, status rule | inside the card file, or `mappings/<id>.yaml` when shared |
| Card | human-shaped presentation | Tier-1 views: stat · list · table · status · link · markdown | `cards/<id>.yaml` |
| Board | composition | Home is a board; personal sections are boards | `boards/<id>.yaml` |
| Governed Action | executable authority | `media.downloads` (read), `downloads.pause_all` (write) | `actions/<id>.yaml` |

```yaml
request: sonarr.queue
meaning:
  concept: media.downloads
card:
  title: Downloads
  view: list
```

- `concept` is descriptive metadata. It does not come from a global capability enum,
  so a new concept needs no core code change.
- This follows ADR-0001. Worlds owns the meaning, and the vendor's data shape never
  becomes product truth. If Sonarr is swapped for another downloader, only the request
  and mapping change. The card, the board and `media.downloads` stay the same.
- Tier-1 views are fixed and accessible. Worlds owns them, so 44px targets, contrast,
  luminance-only rank and reduced motion apply everywhere. A sandboxed template is a
  later escape hatch.
- Status is data: `{path, ok, warn}`. A transport failure renders as `unavailable`, or
  as `stale` with the last-good time. One provider failing never blanks a board.
- room/0 services are a provider kind. Their cards and needs-you items arrive already
  mapped.
- Rooms remain for integrations that need their own logic.
- Recipes are data: a provider template plus requests, mappings and suggested cards.

## Governed actions

A saved request becomes an assistant or automation tool only through a governed
action binding.

```
Saved Request → optional Governed Action Binding → assistant / automation tool
```

```yaml
tool: { exposed: true, name: media.downloads, access: read,  approval: never }
tool: { exposed: true, name: service.restart, access: write, approval: always, idempotency: required }
```

- Assistants and automation discover governed actions. They never discover raw
  requests. `GET /queue`, `GET /medical-records`, `POST /restart-server` and
  `DELETE /episode/1234` are all saved requests, and they are not equivalent.
- Every caller uses one authority path.

  ```
  human UI · assistant · automation → governed action → authority / approval → request execution
  ```

  This replaces today's three approval models (rooms, `ProposalStore`, deployment).
- Defaults fail closed.
  - A request has no binding until one is created.
  - Any method other than GET/HEAD counts as `access: write`.
  - A missing `approval` field means `always`.
- Writes use single dispatch.

  ```
  approve → consume authorization → dispatch once → SUCCEEDED / FAILED / UNKNOWN
  ```

  - Dispatch uses up the approval. Worlds never replays a side effect that may have
    completed because its result was lost, and it retries nothing automatically.
  - If the result is lost after dispatch, the outcome is `UNKNOWN`, which is a
    first-class outcome. A retry is a new action that needs its own approval.
  - The pattern comes from Open Dots, an external project that is not in this repo.
  - The lab demonstrates it under Connect → Actions, with the simulation "Connection
    drops after a write is sent".

## Memory stays a core concept

Memory holds what I intentionally kept, what I need to return to, durable things
about me, and enough history to re-orient myself. It is part of Worlds core and is
not a provider.

```
Memory
├── Kept      deliberate notes / remembered things
├── Later     things to return to
├── Records   durable structured personal information (sensitive ones need step-up)
├── History   journal / what happened
└── Find      deterministic local search
```

- Core baseline (stays in Worlds): Kept, Later, Records, History and local text
  search.
- Acceptance test: turn off every model and every external provider. Memory still
  opens, saved things can be browsed, Later works, Records work, History can be
  browsed, and local search works.
- Enrichment (optional and replaceable): semantic recall, Pollen, `rylee_lore`,
  Project Home context, associations, other retrieval systems.
- The UI never presents Memory as its implementation. The prototype labelled it
  "Supabase + Pinecone + Claude". In the lab, enrichment is one line ("Models:
  off · Enrichment: none connected") that deep-links to Connect.
- The journal-gate principle stays. Agents get narrow, governed answers about private
  memory and never get arbitrary retrieval. The implementation may be removed, and
  the rule moves into governed actions. The lab's example is `memory.later.count`,
  which returns how many Later items there are and never their contents.

## Navigation: the stable skeleton

Core skeleton (owner decision, revision 3):

```
Home · Connect · Memory · Settings
```

| Landmark | Answers | Contains |
|---|---|---|
| Home | *What matters right now?* | The full state of everything in one view (owner refinement, rev 3.1). It has one sentence of state, a summary count by state (icon + word), a short Needs you action list, then Everything: one tile of the same shape per source (state · one number · one line · source · freshness). Details open in place. Discovery is one more tile, and "where you left off" is one line. Home is a board, and it must not look like an API dashboard |
| Connect | *Where does the plumbing live?* | Requests (saved requests, test/run, map, save, pin); Providers; Recipes; Actions (governed bindings); Advanced (secrets as references, connection details, raw technical state). Ordinary use never requires it |
| Memory | *What did I keep, and where was I?* | Kept · Later · Records · History · Find |
| Settings | *How does Worlds look and behave?* | Experience pack, theme, comfort/accessibility, assistant (optional, not installed by default). It contains no plumbing |

- Optional and personal content arrives as boards, cards and sections. It never adds
  permanent navigation. Boards (Media, Homelab…) are listed under the skeleton on
  desktop and reachable from Home on the phone. That list belongs to the person; the
  product landmarks are the four above.
- Raw API mechanics live only in Connect. A card or Memory may offer View source or
  Configure source, and both deep-link into Connect. No human-facing area embeds a
  mini provider console. This reverses revision 2's per-board "Sources" tab, which
  came from the prototype's per-room API tab.
- In the first version, search is Memory → Find. A global search can come later
  without a new landmark.
- Chat is not core navigation. It becomes an optional client of governed actions
  (Phase 5). Until then, the existing Chat screen stays reachable from Settings
  (replace before remove).

### Names in core and under packs

- Each concept uses one plain word in the UI, code, API and files:
  `home`, `connect`, `memory`, `settings`, `board`, `card`, `provider`, `request`,
  `mapping`, `action`, `service`.
- Retired: the area id `overview` (which renders "Bridge") and the reuse of
  "room" for external services.
- The external contract keeps its name. The upstream Play-Nice contract is still
  `room/0`. Worlds' own code calls those things **services**. The rename is one
  mechanical PR in Phase 4.
- Packs may not rename or move the four landmarks. Home is still Home under
  Station. This replaces revision 2's rule that "a pack may relabel Home as Bridge".

## Personality as the optional Station experience pack

Invariant: a person who changes theme or pack does not have to relearn Worlds.

| Moves into the Station / personality pack | Stays in the repo, never deleted |
|---|---|
| Station rank, XP, achievements, stickers, module codes, Bridge/operator terminology, lore, crew, Sol, companion mechanics, star-map navigation | The art, canon, characters, visual language, playful interactions and theme assets |

A pack may:

- have characters report status ("Bolt: the lab's steady…")
- show Sol in small moments
- add HUD treatment (eyebrows such as "Home · deck 1", corner brackets on cards)
- add a starfield backdrop
- add achievements and stickers
- add lore to empty states and transitions

A pack may not:

- move, rename, add or remove a landmark
- change card positions
- gate any function behind the pack
- lower text size or contrast

Lab evidence:

- With the pack off, no pack element is visible.
- With Station on, three pack elements appear.
- The navigation reads `Home · Connect · Memory · Settings` in both cases. A
  programmatic check confirms this.

Not yet proven: the lab uses placeholder marks instead of the protected character art.
A richer pack with the real art is a later design pass under the same invariant.

## Accessibility

Rule: a quiet design lowers emphasis and keeps everything easy to read.

Kept from the prototype:

- the dark, warm palette
- generous spacing
- restrained motion and the existing `prefers-reduced-motion` behaviour
- the low-stimulation background

Changed (the lab answers each one):

| Prototype | Lab |
|---|---|
| 9–11px monospace labels at 15–35% white | Labels ≥13px; secondary text uses the theme's `text-secondary`/`text-muted` tokens, which pass contrast; body text is 16px |
| Status by colour alone (dots, room colours) | Every state is icon + word: ✓ Healthy · ! Needs attention · ◷ Stale · ✕ Unavailable · ? Unknown |
| No visible focus states | A 3px focus ring on every control |
| Small tap targets | ≥44px controls; a 56px bottom bar on the phone |
| Animations on by default | One short fade, only under `prefers-reduced-motion: no-preference` |
| Important state buried in dense metadata | Failures state what went wrong and when it last worked, in one sentence |

Lab verification:

- axe-core (WCAG 2.0/2.1 A and AA plus best practice) reports no violations on all
  12 captured states: four screens in both packs, at 390px and 1280px.
- There is no horizontal overflow at 390px.
- A manual screen-reader walk is still UNKNOWN. It has not been done, and it is
  required before Phase 2 is called done.

## Editing in the UI, stored as files

```
normal use:   Connect → edit → test → save
power use:    YAML / git / bulk edit
```

Invariant: every configuration created in the UI round-trips through the documented
file format without loss. No hidden UI-only config database becomes canonical truth.

- The lab shows the file behind each request. Its request page has a section called
  "The files this writes", which shows the YAML for the request and its card and
  updates as the mapping is edited.
- Real configuration lives in the data/config volume, outside the public repo.
  The repo carries only the reference provider and example recipes.

## Security boundary (unchanged)

- Confinement: requests go only to a provider's registered `base_url` +
  `path_prefix`.
- Network limits:
  - no redirects
  - response size and time caps
  - SSRF protection against link-local and metadata addresses, unless a provider is
    explicitly marked LAN
- Credentials:
  - stored only as references (`env:`, `vault:`, later OpenBao per ADR-0007)
  - injected server-side, and redacted in responses and logs
  - the browser never receives a secret value
  - the lab's Secrets view shows names and set/not-set only, with write-only replace
- Step-up is required for provider and secret edits. Access is owner-only, plus
  scoped agent tokens.
- Governed actions carry receipts and follow single dispatch.
- `tests/test_public_safety.py` still gates every change.

## First recipes

| # | Recipe | Proves |
|---|---|---|
| 1 | Project Home | First-party evolving API, structured project data, richer mappings, internal ecosystem integration |
| 2 | Sonarr | Ordinary third-party REST, auth, list data, recipe portability |
| 3 | Homelab Health | Many small status values, stale/degraded/unavailable, aggregation, graceful provider failure |
| later | GitHub | Its very large API must not shape the first abstraction |

OpenAPI import comes only after these three work when built by hand.

## The reference provider (Phase 1 requirement)

A built-in synthetic provider used only for development, CI, examples and
open-source verification.

| Case | Proves |
|---|---|
| GET list / GET object | list and stat mappings |
| POST idempotent action | governed action, receipt, single dispatch |
| slow response | timeout → `unavailable` / `UNKNOWN` |
| 500 response | degraded card, board survives |
| malformed response | clear error, nothing guessed |
| secret-required request | secret-ref injection and redaction |
| stale result | stale + last-good display |
| redirect attempt | refused |
| oversized response | size cap holds |

Acceptance: the architecture works even when Rylee's infrastructure does not
exist. The whole Provider → Request → Mapping → Card → Board flow runs with no Sonarr,
no Project Home, no LAN, no personal tokens and none of the estate. The lab's
"Reference provider simulates" control previews what the user sees in five of these
cases.

## Superseded decisions

Phase 0 edits each source in place with a dated "superseded by ADR-0008" note, so
future agents do not restore the old architecture.

| # | Source | Old decision | New decision |
|---|---|---|---|
| S1 | `docs/PRODUCT-LANGUAGE.md` § Stable skeleton; `AGENTS.md` (Workbench & Node rules, "The frontend is Worlds"); `docs/TRUE-NORTH.md` scope | `Bridge · Memory · Chat · Settings` is the required stable navigation | `Home · Connect · Memory · Settings` |
| S2 | `docs/PRODUCT-LANGUAGE.md` § Overview; `AGENTS.md` ("area id `overview` renders the **Bridge**") | Bridge/Overview is the primary home landmark | Home, which is a board; `overview` and "Bridge" leave the core vocabulary |
| S3 | `docs/PRODUCT-LANGUAGE.md`, `docs/TRUE-NORTH.md` (Chat in the core four and in G-voice) | Chat is required core navigation | Chat is an optional later client of governed actions |
| S4 | `.project/PLAN.md` Step 1b | "Personality ships here, not later" | Personality ships as the optional Station/experience pack, after the front door works |
| S5 | `docs/PRODUCT-LANGUAGE.md` theme principles ("Character art, a light sci-fi feel, and visible companions stay part of Worlds") | Baseline personality is structurally embedded in core | Personality is an overlay pack. Kept: a plain layout still has a warm identity, and core keeps it through type, softness and complete themes |
| S6 | ADR-0001; `framework validate` (capability-ownership, the `status_map` equality test) | Every provider must implement a core-registered capability, which forces provider semantics into core | Meaning moves into Mapping `concept` metadata; the capability enum is retired for front-door providers; a small built-in set (Memory, vault, journal) keeps its contracts |
| S7 | `.project/PLAN.md` Steps 1c–3 | Media, calendars and inboxes are built-in sources | They arrive as providers, recipes or services |
| S8 | `docs/ARCHITECTURE.md` (API-only routes `/api/lab/*` etc. as a product contract) | Removing them is off-limits | Each is removed in Phase 4 only once a recipe or service replaces it, recorded as an owner decision |
| S9 | `docs/ROOMS.md`; `AGENTS.md` (rooms) | "Room" means an external room/0 service | Worlds code calls it a service; the upstream contract name `room/0` is unchanged |
| S10 | This proposal, revisions 1–2 | `Home · Connect · Memory · Settings` (rev 1–2), then `Home · Needs you · Search` with packs allowed to rename landmarks and a per-board Sources tab (rev 2 addenda) | Revision 3 as written above |

## ADR-0008 draft wording

**Proposed ADR-0008: the front door (meaning, mechanics, authority)**

- Status: proposed (lands in Phase 0 after owner approval).
- Amends: ADR-0001.
- Relates to: ADR-0006 (event envelope = journal entry), ADR-0007 (secrets).

Decision.

1. Worlds owns meaning. Providers own mechanics. External systems connect as
   Providers. Requests carry transport. Mappings carry meaning as descriptive
   `concept` metadata. Cards present. Boards compose. A provider's API shape never
   becomes a Worlds concept.
2. Core owns a small, named set of concepts: Home, Connect, Memory, Settings, and the
   Memory baseline (Kept, Later, Records, History, Find). They work with zero
   providers and zero models.
3. ADR-0001's capability registry is retired for front-door providers.
   Validation checks schema, secret references and confinement. It no longer checks
   membership in a capability enum.
4. Authority is explicit.
   - Assistants and automation can call only governed action bindings, and every
     caller uses one approval path.
   - Writes follow single dispatch: approve → consume → dispatch once → SUCCEEDED,
     FAILED or UNKNOWN, with no automatic replay.
   - Agents get only narrow, bound answers about private memory.
5. Configuration is files. Every configuration created in the UI round-trips through
   the documented YAML without loss. No UI-only store is canonical.
6. Presentation does not change structure. Themes and experience packs may change
   look, voice and moments. They may not move, rename, add or remove a landmark, or
   gate a function.
7. Replace before remove. A subsystem is deleted only after its replacement works,
   one removal family per change.

Consequences.

- Provider integrations become data (recipes), and Python adapters shrink.
- `framework validate` and `tests/test_framework.py` change in Phase 1.
- Room/0 integration continues unchanged as a provider kind.
- Station and character canon are preserved as a pack.

## Phases

Each phase is a vertical slice with phone and desktop screenshots. Each phase follows
replace before remove.

| # | Slice | Includes | Done when |
|---|---|---|---|
| 0 | Decide | Refine the proposal (this); ADR-0008; supersession notes S1–S10; DECISIONS entry; tag `archive/pre-front-door`; delete the dead discovery engine (no behaviour change). No production implementation | ADR merged, conflicting docs updated, gates green |
| 1 | Connect foundation | Provider, Request, Mapping; YAML store with lossless round-trip; secret refs; SSRF guard; request runner and tester; the reference provider; Connect UI; a deterministic test suite | The full flow passes in CI against the reference provider, and Rylee saves a working request from her phone |
| 2 | Human presentation | Cards, boards, Home; stale/last-good; the mapping editor; room/0 provider support; Needs you; deep links from cards to Connect | Home shows real services and pinned cards; one broken provider doesn't blank it; a manual screen-reader walk passes |
| 3 | Recipes, then import | Project Home → Sonarr → Homelab Health, then OpenAPI import | Each of the three runs from a recipe with no Python adapter |
| 4 | The cut | One PR per removal family: personality → pack, multi-user, the rename `rooms` → `services`, then each ported provider once its recipe or service works | Target size reached; all gates green; nothing removed without a working replacement |
| 5 | Memory enrichment + assistant | The Memory baseline already exists. This phase adds provider-backed enrichment, semantic recall, governed action bindings, an optional assistant/chat client, and removal of the hand-written tool registry once its replacement is proven | Memory works with models off; Chat can be entirely absent; the assistant cannot execute arbitrary saved requests; writes use the same governed path as the human UI |
| later | — | MCP provider kind; tier-2 templates; sharing recipes | — |

## What stays, shrinks, moves, goes

| Keep (core) | Shrink | Move out (provider · recipe · service · pack) | Remove |
|---|---|---|---|
| Services reader (today's `rooms.py`), connections, secret_resolver, vault, envelope, status, sections → boards, setup, healthz, manifest + `api` CLI, journal, Memory baseline, themes/tokens/kit, a11y prefs, OIDC login | Auth (owner + agent tokens + OIDC), identity (single mode), prefs, briefing (→ cards), backup, push | Provider/recipe/service: media, lab_*, reconciler, calendar, updates, deployment, source_control, github, agent_sync, project_home, traefik, discovery (live part), reminders, learning, semantic memory, chat + tool_registry. Pack: crew, voice, briefing-voice, stickers, lore, theme_pack, Sol/Keeper/star-map UI | Dead discovery engine, content_db, people/invites/helpers/roles/user, the `journal_gate` implementation (policy kept), legacy `/station` redirects |

Rough target (an estimate): backend about 12–15k LOC and about 40 routes; UI with
4 landmarks.

## Visual style: Lamplight (rev 3.2, proposed)

Lamplight's rule: healthy sources recede, and anything that needs attention is the
most visible thing on the page. It adds warmth and personality on top of the
skeleton without moving provider plumbing back into the human-facing areas.

Sources: Rylee's adopted Play-Nice contracts (library pinned at `2084747`, read in full) and these widely used dashboards and references:

- Uptime Kuma: heartbeat strips
- Glance: `show-failing-only`
- Homepage: one card shape
- Home Assistant: fixed grid with titled sections; masonry dropped for unpredictability
- Apple Weather and widgets: cached values, never spinners
- Oura and Garmin readiness: word bands
- Grafana stat: hero value
- Few and Tufte: exception-based, word-sized graphics
- Calm technology (Weiser and Brown; Case)

Anti-patterns avoided:

- Grafana-style wall of panels
- red or green everywhere
- streak and ring guilt
- masonry reflow
- tiny HUD text

### The rules

| # | Rule | Contract basis | Evidence |
|---|---|---|---|
| L1 | Brightness shows what needs attention. Anything not healthy sits on a brighter surface with a stronger edge. Healthy items recede but stay ≥4.5:1. Rank is never shown by hue alone, and tone never uses the rank channel | Luminance-only rank (`ui/THEMES.md`); tone is not priority (ROOM 46-48); no wall of green (ATTENTION_AND_QUIET 31-32) | Few, exception display; alert-fatigue analyses |
| L2 | Status uses shape, then word, then colour, in that order of reliance: ● Healthy · ▲ Needs attention · ■ Unavailable · ◌ Stale · ○ Unknown. Only the canonical words are used | Status never by colour alone (ACCESSIBILITY 38-39); canonical vocabulary (STATUS_AND_STATE 29-36) | Astro UXDS-style shape-plus-colour system |
| L3 | Home starts with one sentence: a low-drama briefing in human words, then counts by state | First screen answers "what needs me" (AQ 46-47); write for a strained reader (HUMAN_RELIABILITY 42-43) | Apple Weather context lines; Oura summaries |
| L4 | Order of information is human meaning, then state, then detail, then evidence. "Downloads can't check in right now" → ■ Unavailable → "2 were downloading the last time I heard from it" → Last good 19:42 → *Technical evidence:* GET /api/v3/queue · Sonarr returned 500 · 212 ms | Meaning → actions → safety → implementation (DEPTH_ON_DEMAND 47-48); full technical detail within two interactions (DoD 88-89); degraded shows reason + last verified (SAS 65-66) | Glance → peek → open (calm tech; HA tile → more-info) |
| L5 | Healthy states use reassuring words and never celebrate: Quietly working · All quiet · Ready when you are · Halfway through | "Nothing needed" shown explicitly, then stop (AQ 35-36); calm static confirmation (SENSORY_SAFETY 55-56) | Linear's calmer refresh; Things 3 |
| L6 | Home shows life next to machines. Order: sources that are not healthy first, then life (Interests, Memory, Reading), then healthy machines. A technically healthy Home with nothing human on it fails | What needs me / what was I working on / what's coming up (AQ 46) | HA favorites on top; the owner's Interests observation |
| L7 | Continuity has its own first-class section. "Continue where you left off" lists threads you stopped working on: a board being arranged, a half-built request, a Later item | Returning costs "no archaeology" (AQ 52-57); stopping is success (WHAT_WHY_NEXT 53-54) | — |
| L8 | Every card uses one anatomy on a fixed grid in three sizes (S = 1 column, M = 2, L = 2 and expanded). There is no masonry, and nothing reflows when data changes | Stable reading order (WAC 5); dense surfaces are still (SS 40) | Homepage, HA sections, Apple widget sizes |
| L9 | A stale card keeps its last value, with a dashed edge plus "Last good 19:42". It is not dimmed below contrast, blanked or given a spinner | Stale is a state (EVENTS_AND_CACHING 33); missing stays missing (ONE_TRUTH_TWO_VIEWS 42-44); static loaders only (SS 36-38) | Apple HIG: cached data, never a spinner |
| L10 | Density is a stored comfort preference with three values: Calm (healthy machines fold into one "Quietly working" row), Standard, Detailed (check strips plus evidence open). It is not a separate mode | Density is a stored preference (WEB_UI 45-46, TP 35); "no accessibility mode" (TP 38-39) | Glance `collapse-after`; ADHD low-density dashboard study (ACM 2025) |
| L11 | Edit Home is an explicit, separate action: size, move earlier or later, hide, show, undo. It uses keyboard buttons at 44px. Viewing Home never rearranges anything | Customization without changing structure (TP 48-49) | Homarr no-YAML editing; HA drag-and-drop sections |
| L12 | The presence mark is optional and has no function. It is a small mark beside the greeting that shows a resting pose when nothing needs you and looks up when something does. It is static, `aria-hidden`, has no actions and can be turned off. In Station it becomes Sol (placeholder in the lab) | Decoration carries no meaning (TP 40-42); nothing moves on its own (SS 39-40) | Calm tech: the periphery |
| L13 | Personality never hides facts. Station changes wording only: "Downloads missed their last check-in" in Station, "Downloads can't check in right now" in Core. Both show the same evidence and timestamps | A calm surface never hides truth (HR 44-45); human wording may translate but not change meaning (SAS 47-48) | — |
| L14 | No gamified maintenance. Station's strip counts *discoveries* (books, albums). It never counts connections, cleared warnings, visits or streaks | No streaks or guilt (AQ 41-42) | Apple ring-guilt complaints |
| L15 | Lower emphasis never reduces legibility. Body text is 16px, labels ≥13px, headings sentence case, a 2px teal focus ring, ≥44px targets, and no motion by default | PLAIN_LANGUAGE 45-46 (no all-caps headings); WAC 2.4 focus; WAC 2.1 targets; SS 18 | BDA dyslexia style guide |

### Visual directions under test (rev 3.3)

Owner feedback on Lamplight: "it feels kinda … text-y". The lab added three more visual encodings of the same facts and the same IA, each built around visual accessibility. The lab's "Visual direction" control switches between them.

| Direction | Encoding | Strongest for | Watch-outs |
|---|---|---|---|
| Lamplight | Sentences: a meaning line per card | Reading on a good day; personality | Text-heavy (owner feedback) |
| Glyph | A large pictogram with the status shape on the icon, one big number, 2–3 words; a one-row state strip under the greeting shows every source at once | Recognition without reading; the fastest glance at the whole state | The healthy status mark on the icon is small; its word is screen-reader-only, and the shape still differs from ▲ and ■ |
| Instruments | One row per source with a visual meter: health segments, download progress bars (striped when frozen at the last good value), reading progress, project marks, Later dots; numbers line up in one column | Scanning the whole state top to bottom; quantities; "how far along" | Densest of the four; best on desktop |
| Big & Bold | Two or three large cards per row, a thick status band (shape + word), 40px icons, 3rem numbers, fewest words | Low vision, 200% zoom, tired eyes, glancing from across the room | Fewer sources fit per screen |

Checks on all directions:

- axe reports 0 violations at 390px and 1280px, with and without Station, and with an opened card.
- The Core/Station invariance probe passes in every direction.
- Every meter carries a text equivalent.
- Drilling in (card → detail → Technical evidence) works the same way in all four.

Recommendation (superseded by the owner's choice of Instruments, below):

- Make Glyph the default Home.
- Use Instruments as the Detailed density, where it fits.
- Offer Big & Bold as a comfort preference ("Larger cards") and keep it out of themes.
- Keep Lamplight's *language* (human meaning lines, the healthy vocabulary) in the drill-in detail and the briefing sentence, where words help most.

### Home direction: Instruments (owner choice, 2026-10-01)

Owner reaction to the four directions: "I really enjoy instruments", with a request to make it more robust and warm. Instruments is the chosen Home direction. It keeps Lamplight's language: meaning lines, the healthy vocabulary and the briefing.

Row anatomy (one shape for every source):

```
icon · name + what it means · meter · value + unit · state + freshness
```

- Fixed groups in a fixed order:
  - Needs a look comes first. These rows have a brighter surface plus an accent edge (a coral edge when unavailable).
  - Your life comes second.
  - Quietly working comes last.
  - A row changes group when its state changes, and the groups never move. When nothing needs a look, the first group says so ("Nothing needs a look. Everything is answering.") and shows nothing else.
- Healthy rows have low emphasis. They show a plain "● Healthy" (machines) or "● Up to date" (life) with no pill. Only exceptions get a bordered badge, which avoids a wall of green.
- Every state has a meter:

  | Meter | Used for |
  |---|---|
  | Segments | Health (Homelab: a ▲ marks the broken one) |
  | Progress bars | Each download |
  | Progress | Reading |
  | Stage marks | Projects |
  | Dots | Later |
  | Day timeline | Today, with the past shaded and a "now" line; labels sit under the track so they never collide |
  | Shelf | Interests, recent finds as spines; ✦ marks the new one |

  - When a source is stale or unavailable, its meter freezes, striped, with "as of 19:42".
  - When a source is not set up, the track is dashed and empty, with a "Set up Music" button and "Optional. Nothing is missing until you want it."
  - Missing values show "—". They never show 0.
- Warmth:
  - Young Serif meaning lines ("A gentle evening", "Quietly working", "Halfway through").
  - Brass-and-teal meters.
  - Icon wells tinted with the accent.
  - Life rows (Today, Reading, Interests, Memory) carry as much visual weight as machines.
- Comfort settings:
  - Calm folds Quietly working into one line.
  - Detailed adds a 24-check strip to machine rows and opens technical evidence by default.
  - Edit Home moves, hides, shows and undoes rows.
- Drill-in: row → meaning, detail and rows → Technical evidence (two interactions) → Open in Connect.
- Checks:
  - axe reports 0 violations in 14 states: Sonarr down, all answering, Station, Calm, Detailed with stale data, drill-in and edit, each at 390px and 1280px.
  - No horizontal overflow; one timeline-label overflow was found and fixed.
  - The Core/Station invariance probe passes.

### Importance hierarchy and word layers (rev 3.5)

Owner request: "make the design show your eyes what is important"; earlier, "it feels kinda … text-y". Size, brightness and position show importance before the reader reads any word (Few's pre-attentive attributes).

Home from top to bottom, by importance:

1. Greeting, plus a one-line briefing (its length depends on the Words setting).
2. World strip. Every source appears as one segment, worst first, shown as icon + state shape. Unavailable is a dashed ■, stale a dashed ◌, needs-attention an outlined ▲, healthy a calm ●, not-set-up a dashed ◇. Tapping a segment opens that row. One glance shows how many sources are healthy and how many are not.
3. Needs you: an amber band, the brightest element on the page, with primary buttons.
4. Needs a look: tall rows (52px icon, 2.4rem value, full meter), sorted worst first (unavailable → stale → needs attention).
5. Continue, as chips.
6. Your life: medium rows.
7. Quietly working: slim one-line rows, transparent, with no meter unless Detailed is on.

Word layers (who owns which words):

| Layer | Example | Owner | Pack may change? |
|---|---|---|---|
| Facts | "Downloads", "2", "Unavailable", "Last good 19:42", "HTTP 500" | Core, fixed and generic | Never |
| Meaning | "Can't check in", "Quietly working" (≈4 words) | Core default | Re-voice only, same meaning ("Missed check-in") |
| Voice | Briefing flavour, crew lines, lore in empty states | Packs | Freely |

Words is a comfort setting that works independently of the pack:

| Setting | Shows |
|---|---|
| Minimal | Facts only: name, number, unit, state word |
| Short (default) | Adds a meaning label of at most about 3 words ("Can't check in", "Your call", "Backups late") and a terse briefing: "2 for you · Downloads down · rest quiet" |
| Full | Adds the sentence briefing, meaning on quiet rows, and freshness on every row |

Rows that need a look always show freshness.

Sparse-language pass (owner: "sparse the language some"). In Short:

- Freshness is compact: "2m ago", with "Last good 19:42" kept exact.
- Units are short: "waiting", "last known", "read", "left today".
- Needs you items are terse imperatives: "Approve Hive Works plan", "Backups 3 days old".
- Source names move to Full.
- Section and button labels: "Continue" becomes "Pick up", and "+ Add".
- Healthy life rows say "Current".
- The drill-in detail keeps full sentences. Longer text belongs in the detail view.

Checks:

- axe reports 0 violations in 16 states (three Words settings, all answering, Station, Detailed with stale data, strip-jump, edit; 390px and 1280px).
- No horizontal overflow; one Detailed-phone overflow was found and fixed.
- The Core/Station invariance probe passes.

### Owner review of the lab (2026-10-01): "yes, this could actually be my front door"

Settled: the architecture, and Instruments as the Home direction. The Home order is:

```
orient → what needs me → what deserves a look → where I left off → my life
```

The owner asked to preserve these. Treat each as a design invariant.

- The terse briefing: "2 for you · Downloads down · rest quiet".
- Needs you is a finite list of actions, and it ends.
- Needs a look is separate from Needs you. An unhealthy source does not create an obligation.
- Pick up returns you to threads you left open. It is not a task manager.
- Your life keeps Home from becoming an observability dashboard.
- Not set up yet / Optional: a missing capability is not shown as a failure and never nags.
- The four bottom landmarks stay fixed.
- Core has warmth without any pack. "Halfway", "Quiet evening", "The Dispossessed", "Call with Mum", "Ready" and "Pick up" provide it.

Refinements applied (rev 3.6):

1. Edit Home sits below the briefing and the strip, as a grey outlined button with low emphasis. Ordinary use ranks above customization.
2. The world strip uses clear tap targets:
   - Each segment shows its name under the icon and state shape, and is at least 56px tall.
   - Each has a full accessible name, e.g. "Downloads: Unavailable. Show details".
   - It wraps to a 4-column grid on the phone.
3. "+ Add" → "+ Add to Home".
4. Projects pill density: only projects waiting on you show as pills. Others collapse to "+1 more", and the full list is in the drill-down.

Watch item: pill density on Projects. If it grows, secondary states move to the drill-down.

Checks: axe reports 0 violations in 16 states, there is no horizontal overflow, and the Core/Station invariance probe passes.

### Core personality and pack personality

| Core (Experience pack: None) | Station pack adds |
|---|---|
| Warm human copy; a healthy-state vocabulary; life on Home; the continuation section; a low-emphasis presence mark; warm dark palette; Young Serif for meaning lines; the date in the eyebrow | Sol; a crew line (placed below the cards so nothing shifts); HUD eyebrow ("Home · deck 1 · evening watch"); corner brackets; a starfield; playful but exact copy; a discovery strip |

Lab result: a probe compares navigation, headings, every actionable control and card order between Core and Station on all four screens, with providers both healthy and failing. It finds no differences. The eyebrow is the same height in both, so the greeting doesn't move.

### Tensions this resolves (from the contract read)

- Same-shaped tiles vs "one attention list beats forty equal cards": a separate Needs you list, luminance ranking, not-healthy rows sorted first, and Calm density folding healthy machines.
- Stale dimming vs contrast: a dashed edge plus a timestamp replaces dimming.
- The fixed teal focus colour vs Daylight: the lab uses `#72b1b1` on dark and a darker teal on Daylight, so the ring keeps 3:1. Recommend amending WAC 2.4 to "teal at ≥3:1 per theme".
- WAC 5.2's Bridge reading order (needs-you 4th) is superseded by the Home order above. Add it to the S2 supersession.
- WAC 9.2 names the settings section "Customize", and the skeleton says Settings. Proposal: the landmark is Settings, and "Customize Home" is the Edit Home action. Record this in ADR-0008.
- No contract defines a low-capacity mode. Lamplight uses comfort preferences (Calm density) and adds no mode.

### The seven success conditions (lab status)

| Condition | Lab status |
|---|---|
| Architecture: I understand where things live | Met. Four landmarks; boards beneath; invariance probe passes |
| Low capacity: what needs me without investigating | Met in the lab. Briefing sentence, Needs you, not-healthy rows first; Calm density for bad days |
| Technical depth: drill all the way down | Met. Card → detail → Technical evidence (2 interactions) → Open in Connect |
| Continuity: return without reconstructing | Designed, with example data. Real continuation needs journal events (Phase 2) |
| Personality: it feels like my world | Designed. Needs Rylee's judgement; the lab uses placeholder art for Sol |
| Replaceability: providers disappear, concepts stay | Met. Sonarr 500 leaves `media.downloads` and the card intact, with last good shown |
| Theme boundary: Station leaves the structure unchanged | Met. The probe passes on all four screens, healthy and failing |

Known trade-off: the larger Continue section takes vertical space. On a 1280×900 desktop the life cards start at the fold in Standard density, and Calm density fits Home on one screen again. Accepted for now; revisit with real data.

UNKNOWN: a manual screen-reader walk; how Lamplight looks with the real protected companion art.

## Design evidence

### The owner's Figma Make prototype (the "before")

- File: key `eS6fzNT9NC1hjSGWf3yFO3`. It is one React file of about 2.8k lines, and
  every call in it is simulated.
- It is kept as the "before" reference. The Figma tools can read a Make file but cannot
  write one, so the experiments ran in a forked lab instead (below).
- Its mock hostnames, tokens and data are never copied into this repo.

What the lab took from it:

- the calm greeting
- "needs you" only when something is pending
- destination tiles
- the dark, warm language
- the role idea: each provider in a room carried a *role*, which became the
  Mapping's meaning

What the lab relocated:

- per-room API and Learn tabs → Connect, and the pack
- Systems' Providers/Variables/Connections/Health → Connect
- achievements and XP → the pack
- custom room types → boards (kanban deferred)

### The design lab (the "after")

- Where: https://claude.ai/artifact/Tjki6MHSBKXxijd6rNjiXg (private, interactive).
  The source is kept outside the repo.
- Built from: Worlds' real tokens (starfield dark, daylight light) and
  fonts (Atkinson Hyperlegible Next, Young Serif).
- Controls: the experience pack and the reference-provider scenario.

| Experiment | What it showed |
|---|---|
| A: Home | When Home leads with a sentence ("2 things need you. 1 source isn't answering; its card says so"), then Needs you, then cards, it reads as a personal page and does not look like a dashboard. A failing provider becomes a dashed card that says what went wrong and when it last worked, and the rest of Home is unaffected. The "View source" link is the only plumbing on Home |
| B: Connect | One request page carries the whole loop: Run → assertions → map fields → concept → Save and pin, with the YAML it writes beside it. Actions show "9 saved requests · 4 bound as actions", which shows that a saved request is not automatically a tool. The UNKNOWN receipt is plainly worded and refuses to resend |
| C: Memory | Kept · Later · Records · History · Find work as one deterministic place, and Find needs no model. Enrichment is a single line. Locked Records say "confirm it's you" |
| D: Station pack | The crew voice, HUD eyebrow, card brackets, starfield and stickers appear and disappear with the pack; navigation and layout don't move. The lab used placeholder marks instead of the protected art |

Experiment A2: Home at a glance (owner request, rev 3.1: "simpler and easier to see the full state of everything in one view"):

- Desktop (1280×900): the greeting, the state sentence, the summary counts, Needs you and every source tile all fit without scrolling.
- Phone (390px): the summary, Needs you and the first row of tiles fit on the first screen. Tiles use two columns, and an opened tile spans the full width.
- What it replaced: large mixed cards, a separate discovery section and a history section. Every source now has the same tile shape, so states can be compared at a glance. Detail is one tap away, in place.
- Checks: axe reports 0 violations in all states, including the opened tile and the Station pack.

Design observations for Phase 2:

1. Start Home with one sentence of state before any cards. In the lab this made Home
   calmer than any visual treatment did.
2. A degraded card must say what went wrong and when it last worked, and stay in its
   slot. A dashed border plus a word works better than any colour cue.
3. "View source" on every card is all the plumbing Home needs. Adding more would
   bring provider plumbing into Home.
4. On the phone, long action names and pills need room, so rows must wrap. The lab hit
   this problem and fixed it.
5. A pack's moments need reserved space in the layout. The crew line sits where a
   blank space would otherwise be, so turning the pack off never reflows the page.

## Owner answers and review

| Date | Decision |
|---|---|
| 2026-10-01 (taps) | Personality becomes an optional pack; just Rylee + scoped agent tokens; keep OIDC in Worlds; refine before building |
| 2026-10-01 (review 2) | Mapping as the semantic layer; governed actions with single dispatch; Memory stays core; doc conflicts resolved explicitly; UI-first with lossless YAML; Chat parked; recipes Project Home → Sonarr → Homelab Health; reference provider in Phase 1 |
| 2026-10-01 (naming) | Standard names in core; no themed names |
| 2026-10-01 (lab review) | Architecture and Instruments settled ("this could actually be my front door"); four refinements: Edit Home placement, named strip targets, "+ Add to Home", Projects pill density |
| 2026-10-01 (importance) | Show the eyes what is important; Words layers and setting (Minimal / Short / Full) |
| 2026-10-01 (direction) | Home direction: Instruments, made more robust and warm |
| 2026-10-01 (review 3) | Skeleton `Home · Connect · Memory · Settings`; raw mechanics live only in Connect; the Station pack is an overlay that never changes structure; quiet lowers emphasis and keeps legibility; the Make prototype is a disposable lab |

## Open owner questions

1. Approve revision 3 to start Phase 0? Phase 0 covers only docs, the ADR, an archive
   tag and dead-code deletion.
2. Information, not a decision: where Pollen and Open Dots live is UNKNOWN; neither
   is referenced in this repo. A pointer would let ADR-0008 cite them properly.

Everything else (exact Connect sub-tabs, `concept` naming such as `area.thing`, where
boards appear on the phone, card visuals) is an implementation call that Claude owns
within this direction.
