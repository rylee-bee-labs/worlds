# The Station — gap analysis: why it doesn't feel alive / land yet

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see [`.project/CURRENT.md`](../../.project/CURRENT.md)) · **Read this if:** you need the dated 2026-09-17 source-level gap analysis for provenance · **Superseded by:** the running `ui/` interface and [`.project/CURRENT.md`](../../.project/CURRENT.md).

**In short:** a 2026-09-17 evidence-based analysis of why the served
Station felt static, with line-level citations and top fixes. Since it was
written, the interface flipped to the React rebuild in `ui/` (2026-09-22,
Bridge is now home) and the server-rendered Station — including the
`design/opendesign-exploration/station/` tree cited below — was retired to
a theme package. Read it as a record, not a current map. Truth routing:
[`docs/README.md`](../README.md).

Status: **analysis** (2026-09-17). Evidence-based, not inspiration.
Companion reading: `docs/STATION-ALIVE-RESEARCH.md`,
`.project/HANDOFF-UI-ORCHESTRATION-2026-09-17.md`, `docs/PERSONAL-WORLD-FINISH-LINE.md`.

**Provenance.** Citations are to the current **dirty working tree** of
`design/opendesign-exploration/station/` at HEAD `d4c0fb3`; line numbers may differ
from `origin/main`. Unverifiable claims are marked **UNKNOWN**.

---

## 1. What The Station is today

The Station is the **product UI**, served same-origin at `/station/` by the Python
backend from `design/opendesign-exploration/station/`
(`src/personal_world/station_ui.py:1-33`, `README.md:147-149`, `.project/CURRENT.md:21-22`).
Its landing (`index.html:64-116`) is the star-chart "systems map" rendered by
`starmap.js` (`starmap.js:218-399`).

- **Nodes come from the canonical registry.** `sections.js` boots a 5-item fallback
  immediately, then upgrades from `GET /api/sections` (`sections.js:81-128`); the
  backend builds that from `sections.py`'s `SECTIONS` tuple against live capability
  health (`api.py:1710-1721`, `sections.py:48-59,110-158`).
- **Node mood/status/attention are bound to a derived projection.** `world-state.js`
  fetches `/api/sections`, `API-003` status, `PROP-list` proposals, `API-067`
  reminders, `API-005` journal in parallel (`world-state.js:233-239`), assembles a
  read-only `WorldProjection`, and re-renders the map (`world-state.js:256-264`,
  `starmap.js:84-102,618-624`).
- **Needs-you is real and honest.** Two mounts (`index.html:82,100`) render from
  proposals + reminders via `real-data.js`, and refuse to say "all quiet" while a
  source is unchecked (`real-data.js:321-385,515-610`).
- **Region pages exist for 5 of 9 sections**: `interests.html` (real `API-051`,
  `interests-view.js`), `projects.html` (real `API-033/034`, `projects-view.js`),
  `journal.html` (real `API-005` via `real-data.js:614-675` + browser-local notes),
  `chat.html` (real `POST /api/chat`, `chat.js:148-174`), `settings.html`.
- **The rest of the chrome is device-local**: preferences, theme, companion pick,
  map positions and the map structure patch all live in `localStorage`
  (`station.js:22-46`, `starmap.js:110-172`). `real-data.js:76-154` documents, row by
  row, how far each Station control actually reaches — most are device-only.

So: labels, status words, attention counts, needs-you, journal, interests, projects
and chat are genuinely wired. The weak half is everything that would make it feel
*inhabited*.

---

## 2. The gap — real vs static, surface by surface

Legend: **REAL** = live authoritative data · **PARTIAL** = real but incomplete/mis-routed ·
**SPECIMEN** = sample content · **DEVICE** = localStorage only · **ABSENT** = not implemented.

| Visible thing | Bound to | Evidence | State |
|---|---|---|---|
| Constellation labels / icons / colours | `GET /api/sections` → `sections.py` registry | `sections.js:86-93`, `starmap.js:30-51` | REAL |
| Node status word + `mood` class, dim/scale | `SectionState.status/mood` | `world-state.js:69-90`, `starmap.js:274-282` | REAL |
| Attention ring + node size | pending proposals + enabled reminders | `world-state.js:108-150`, `starmap.js:274` | PARTIAL |
| Info strip "Map note" | unchecked sources / section state words | `starmap.js:315-324` | REAL |
| Info strip "Recently" | `recentActivity[0]` **or** `current.activity` | `starmap.js:327-332` | PARTIAL |
| Info strip "From" / "Suggests" | `current.provenance` / `current.rec` | `starmap.js:337-338` | SPECIMEN |
| Needs-you list | proposals + reminders, verified quiet | `real-data.js:321-385`, `index.html:82,100` | REAL |
| Journal / Interests / Projects pages | API-005 / API-051 / API-033+034 | `real-data.js:614`, `interests-view.js`, `projects-view.js` | REAL |
| Chat replies | `POST /api/chat` | `chat.js:60,148-174` | REAL (no streaming) |
| Companion presence | random companion, random position, once/session | `starmap.js:629-651` | SPECIMEN-ish |
| Companion **state/expression** | — nothing | `chars.svg` has 5 symbols, no pose variants; `PW_CELEBRATE` (`station.js:229-241`) has **no caller** | ABSENT |
| Ambient life (drift, breathe, twinkle) | `[data-motion="on"]`, default **off** | `station.css:769-780,851,912,1421`; `station.js:40` | MOTION-GATED |
| Map memory | positions + structure patch | `starmap.js:110-172` | REAL (device) |
| World summary counts (facts/intents/policies/lore/providers) | fetched from `API-003` | `world-state.js:93-104` | DEAD READ (never rendered) |
| Today / Media / Lab / Vault surfaces | — | `sections.js:49-55`, `world-state.js:194-206` (all `null`) | ABSENT |

### The five things that actually break "alive"

1. **The centre has no surface.** `today`, `media`, `lab`, `vault` have `null` hrefs
   (`sections.js:48-56`, `world-state.js:194-206`); `today.html` / `media.html` /
   `lab.html` / `vault.html` do not exist. Clicking them falls through to `openDive()`.
   `today` declares **no capabilities** (`sections.py:49`), so its status is `null`, so
   it renders the *generic* "This corner is quiet for now " branch (`starmap.js:526-529`)
   — not even the warm `diveStatusCopy()`. Yet `GET /api/daily` already exists
   (`api.py:667-675`) and no Station JS consumes it (grep: only a `CMD` string in
   `starmap.js:70`). The map's front door opens onto the Finish Line's #1 requirement
   (Today: what needs me / what was I working on / what's next) and finds nothing.
2. **Companions are not bound to state.** The research's whole thesis is
   `provider → normalizer → canonical state → presentation`
   (`STATION-ALIVE-RESEARCH.md:28-32,140-168`). There is no expression layer. The only
   companion behaviour is a random ambient egg: random character, random position,
   once per session, 45 s delay, auto-removed after 14 s (`starmap.js:629-651`).
   Companions do not respond to anything, because nothing maps state→presentation.
3. **Life exists only as motion, and motion is off by default.** Drift, attention
   breathe, sleep breathe, orb float and starfield twinkle are all `[data-motion="on"]`
   (`station.css:769-780,851,912,1036,1421`). Default is `off` (`station.js:40`).
   Reduced motion removes them entirely (correct per contract §6.2). The result: the
   *default* Station is a static chart. Research explicitly warns against
   "motion as the only signal" (`STATION-ALIVE-RESEARCH.md:113`) and wants delight even
   with companions/motion off (`:24-27,45-46`). Today, turning motion off makes it
   inert, not calm.
4. **The map is a one-shot snapshot.** `world-state.js` loads once on boot
   (`:326-342`); there is no poll, interval, or focus/visibility refresh (the only
   re-load is after an interests add, `interests-view.js:289-290`). A proposal or a
   status change arriving after load never appears until reload. There is no return
   state ("where you left off", "what changed since") — only the newest journal item
   (`starmap.js:327-329`). No memory ⇒ no *"remembers"* ⇒ not alive
   (research `:93,233-237`).
5. **Most regions are hollow by construction.** `buildDefaultTree()` assigns
   `activity:'', provenance:'', rec:''` to every generated node (`starmap.js:43-45`);
   only the root has hardcoded prose (`:34-36`). `real-data.js` admits the region copy
   is still specimen because no per-region endpoint exists (`real-data.js:51-54`). So
   the info strip renders literal filler — `Recently · quiet`, `From · —`
   (`starmap.js:331,337`). The screen says "here is a system" and then has nothing to
   say about it.

Two more wiring gaps: `proposalSection()` routes `world_intent`/`world_fact` to a
`'world'` node that does not exist (`world-state.js:209-215` vs `starmap.js:37-49`), so
those proposals never ring a node; and `PW_SUGGEST` / `PW_NAVIGATE` are defined with
**no consumer** (grep across `station/*.js`). Companion naming/domain also drifts from
canonical (`ratatoskr`/`burrito` in `station.js:30-35` vs `world-tree-squirrel`/
`taco-news-truck` in `design/COMPANION_INTEGRATION.md:29-33`; `sections.js:36-46` gives
Journal `egg: null` while that doc maps Journal→squirrel).

---

## 3. Top 5 concrete fixes

Effort: **S** ≤ half a day · **M** half–2 days · **L** >2 days.

### Fix 1 — Give Today a real Station surface and bind its node
- **What:** new `station/today.html` + `station/today-view.js` reading `API-004`
  `GET /api/daily` (`api.py:667`), plus `API-067` reminders and `PROP-list`
  proposals, rendered through the existing `real-data.js` honesty patterns. Add
  `today: 'today.html'` to `HREFS` (`sections.js:49-56`) and `sectionHref`
  (`world-state.js:194-206`).
- **Why it moves the needle:** removes the single worst dead-end and satisfies the
  Finish Line's "Today first" ordering (`PERSONAL-WORLD-FINISH-LINE.md:30-42`) on the
  actual product UI. The map's centre stops being a doorway to generic copy.
- **Effort:** M.
- **Accessibility risk:** Low. Copy `real-data.js` (real lists, `<time>`, text status,
  44px `Try again`, polite live region). No new motion. Watch §8 live-region restraint.

### Fix 2 — Add a small pure expression layer binding companions to `WorldProjection`
- **What:** new `station/expression.js` (presentation-only): map
  `SectionState.status/mood/attentionCount` → `{ poseClass, dim, label }`; apply it to
  the orb silhouette (`station.js:88-108`) and node eggs (`starmap.js:269-271`), with a
  text label always alongside. **Do not add new companion poses** — `chars.svg` is
  deliberate artwork and AGENTS.md forbids casually regenerating rigs; express state
  via existing symbol + opacity/scale/ring classes.
- **Why it moves the needle:** this *is* the "alive" mechanism the research specifies
  (`STATION-ALIVE-RESEARCH.md:28-32,140-168`) and it is entirely missing. It also makes
  companions meaningful instead of random.
- **Effort:** M.
- **Accessibility risk:** Low–Medium. Every state must keep a text equivalent
  (contract §1.4, §7.1-7.5); under reduced motion the pose becomes static, not deleted
  (research `:123-124`). No announcements for companion changes (§7.5).

### Fix 3 — Make the projection persistent without polling
- **What:** refresh `world-state.js` on `visibilitychange`/`focus` (and after any gated
  write) instead of only at boot (`world-state.js:326-342`); surface "where you left
  off / what changed since" from `API-005`. Prefer event-driven over `setInterval` —
  the repo treats zero polling as a property to keep
  (`HANDOFF-UI-ORCHESTRATION-2026-09-17.md:28`).
- **Why it moves the needle:** delivers object permanence + memory
  (research `:93,233-237`) — state that arrives while you are away is there when you
  return. Without it the scene can never feel inhabited.
- **Effort:** S–M.
- **Accessibility risk:** Low. Routine refresh must not announce (`ACCESSIBILITY_CONTRACT.md`
  §8.2); "what changed" is a text line, never motion.

### Fix 4 — Replace hollow region copy with real per-region data
- **What:** a small provider (extend `real-data.js` with a `regionRecent()` map, or add
  `station/region-data.js`) that resolves a section id → a real read already available
  (journal→API-005, interests→API-051, projects→API-033/034, today→API-004/067/PROP),
  and feed `starmap.js`'s info strip (`starmap.js:326-339`) instead of `''`/`'—'`.
- **Why it moves the needle:** closes the admitted specimen gap
  (`real-data.js:51-54`) and makes depth-0/1 carry truth rather than prose — the
  orchestration's own "reward = information, not animation"
  (`HANDOFF-UI-ORCHESTRATION-2026-09-17.md:50-53,108`).
- **Effort:** M.
- **Accessibility risk:** Low. Text + honest unknown/unavailable states only.

### Fix 5 — Surface the world summary and route attention correctly
- **What:** render the already-fetched `worldSummary` counts (`world-state.js:93-104`)
  as text in the galaxy info strip / technical disclosure, and fix
  `proposalSection()` (`world-state.js:209-215`) so `world_*` proposals attach to a real
  node (or a dedicated World affordance).
- **Why it moves the needle:** depth-0 currently carries only hardcoded root prose
  (`starmap.js:34-36`); this makes the whole map truthful and stops attention vanishing.
- **Effort:** S.
- **Accessibility risk:** Low. Counts are text; keep luminance-only ranking, never
  colour/size as the sole carrier (contract §1.3-1.4; tokens
  `design/tokens.json:64-86`).

---

## 4. What NOT to do (anti-patterns already visible in the code)

- **Don't keep life behind motion.** All ambient aliveness is `[data-motion="on"]`
  (`station.css:769,851,912,1421`), default off. That *is* "motion as the only signal"
  (`STATION-ALIVE-RESEARCH.md:113`) — fix by adding non-motion truth/signal, not by
  turning motion on by default.
- **Don't keep random/novelty companions.** `starmap.js:637` picks a companion with
  `Math.random()` at a random position once per session — exactly the
  "surprise randomness exposed to the user" anti-pattern (`:111`). Bind visits to real
  change.
- **Don't ship specimen code, even labelled.** `journal-view.js` says "no journal
  backend exists" (`:10-14`) yet is loaded on `journal.html:30` with `data-unused`
  (nothing reads that attribute; grep). It is dead weight that contradicts the honesty
  stance and the dual-storage risk already flagged (`HANDOFF-UI-ORCHESTRATION` C1/C2).
- **Don't let content views become a card dashboard.** `starmap.js:1-19` and
  `HANDOFF-UI-FIX.md:11-18` both insist the product is a spatial map, not a dashboard.
  Stacking list/card panels under the map drifts toward the thing the concept rejects.
- **Don't encode urgency primarily in size.** Node scale grows with attention count
  (`starmap.js:277-281`); words and `aria-label` also carry it (so it is not
  non-compliant today), but the canonical rank encoding is **luminance**
  (`design/tokens.json:64-86`, contract §1.3). Size may reinforce, never lead.
- **Don't manufacture intimacy or gamify.** First-person specimen copy ("you stopped
  mid-thought 4 days ago", `HANDOFF-UI-ORCHESTRATION` C3) is manufactured intimacy
  (`STATION-ALIVE-RESEARCH.md:112`); streaks/XP/pet-growth and unstoppable loops are
  already banned (`:105-113,285-292`).
- **Don't add a runtime animation player or regenerate art to fake state.** SVG/CSS is
  the sanctioned floor; Rive/Lottie is a last resort (`:241-258`), and companion rigs /
  `chars.svg` are deliberate artwork (AGENTS.md). No LLM-driven idle animation (`:285`).
- **Don't add polling.** The zero-`setInterval` property is deliberate
  (`HANDOFF-UI-ORCHESTRATION:28`); use focus/visibility events.

---

## 5. A 3-step small-real-prototype path

Consistent with `STATION-ALIVE-RESEARCH.md` Part 11 (`:262-279`).

1. **Prototype A — stateful companions, no movement** (= Fix 2).
   Bind existing `chars.svg` symbols + CSS state classes + a text label to real
   `WorldProjection` state for the five companions.
   *Success:* every base state renders an understandable **static** pose; reduced motion
   yields the same information; axe + the existing Playwright gate stay green.
2. **Prototype B — truth before motion** (= Fixes 1, 4, 5, and event-driven Fix 3).
   Ship Today; fill region copy from real reads; surface world summary; refresh on
   focus/visibility. *Success:* the scene carries real information at depth-0 and after
   time away; nothing new moves.
3. **Prototype C — living Station** (research Prototype C, `:275-279`).
   Deterministic ambient life + temporary objects produced by *real* change + persisted
   positions, delightful with companions **and motion** off. *Success:* a 30-second watch
   reads as inhabited; it settles back to quiet; no LLM/network per ambient tick; CPU
   stays low on a hidden tab.

---

## Appendix — UNKNOWN / not verified

- **UNKNOWN:** whether `origin/main` (vs this dirty tree) already contains partial
  fixes for the orb (the orchestration A1 describes an `<a>` orb, but the working tree
  creates a `<button>` at `station.js:94-97`); line-level differences are unverified
  against HEAD.
- **UNKNOWN:** whether any per-region activity/provenance endpoint is planned or exists
  beyond the Station's own statement that none does (`real-data.js:53`).
- **UNKNOWN:** live runtime feel on the real seeded instance was not tested in this pass
  (read-only source analysis; no browser run) — the "doesn't feel alive" judgement rests
  on code evidence, not a fresh UAT. Compression, keyboard orb, dual storage tracks and
  mobile clipping are owned by `.project/HANDOFF-UI-ORCHESTRATION-2026-09-17.md` §2-4.