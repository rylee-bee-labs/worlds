# Making The Station feel alive — research & direction

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see [`.project/CURRENT.md`](../../.project/CURRENT.md)) · **Read this if:** you need the dated 2026-09-17 research on companion/ambient behaviour · **Superseded by:** [`.project/PLAN.md`](../../.project/PLAN.md) for direction and [`docs/PRODUCT-LANGUAGE.md`](../PRODUCT-LANGUAGE.md) for the theme boundary.

**In short:** a 2026-09-17 research note on how to make the Station feel
"alive" (response, imperfection, memory — not more animation), with a
licensing reality check and anti-patterns. Since it was written, the
interface flipped to the React rebuild in `ui/` (2026-09-22, Bridge is now
home) and the server-rendered Station became a theme package; it remains a
research record, not a commitment. Truth routing: [`docs/README.md`](../README.md).

Status: **research** (2026-09-17). Not a commitment and not an implementation
claim. It exists to give a designer and an engineer a concrete direction, and to
correct several ChatGPT-suggested references that turned out to be mis-specified
or licence-incompatible.

Companion reading: [ACCESSIBILITY_CONTRACT.md](../accessibility/ACCESSIBILITY_CONTRACT.md),
[NATIVE-BASELINE-AND-ENRICHMENT.md](../NATIVE-BASELINE-AND-ENRICHMENT.md),
[../design/COMPANION_INTEGRATION.md](../../design/COMPANION_INTEGRATION.md).

---

## Part 1 — Executive summary

The Station should not become more *animated*. It should become more
*responsive, persistent, and quiet*. The difference between "animated" and
"alive" is: **response + imperfection + memory**. A looping wiggle is animated;
a companion that notices something, chooses an expression, and remembers where
it was is alive.

Three findings drive everything:

1. **Mascots are optional; materiality is not.** FigJam feels playful with no
   mascot at all — stamps land at hand-tuned angles, cursors carry presence,
   objects persist where you left them. Playfulness lives in the *objects and
   the room*. The Station should be delightful even with companions switched off.
2. **The proven pattern is provider event → normalizer → small canonical state
   → presentation.** Every serious agent-pet project (CoPet, OpenPets, Clawd on
   Desk) does exactly this, with ≤13 states and a priority merge. None runs the
   LLM for idle animation. This matches Project Worlds' own rule: machine truth
   stays structured; the expressive layer only maps `state → presentation`.
3. **Accessibility is not in tension with delight — it is the discipline that
   keeps delight from becoming noise.** Animation is never the only carrier of
   information; reduced motion *replaces* motion with a static equivalent, it
   does not delete the information. This is already the repo's contract.

**Design thesis (candidate):**

> The Station is a calm spatial scene driven by authoritative world events.
> Companions are provenance-bearing inhabitants that express a small shared
> semantic vocabulary through *activity, posture, location and objects* — never
> through text they initiate. Ambient life is deterministic and silent.
> Significant events briefly alter the scene, then it returns to quiet. Every
> visual behaviour has an equivalent accessible representation, and the scene is
> fully delightful with companions disabled.

Optimise for **maximum warmth per unit of attention**, not maximum cute.

---

## Part 2 — Licensing reality check

Several of the brief's references were ChatGPT conflations. Verified existence
and licences (checked against actual LICENSE files):

| Reference | Exists | Licence | Reuse code | Reuse art | Note |
|---|---|---|---|---|---|
| PostHog + "Hoggies" | yes | MIT app; **PolyForm Strict 1.0.0** for brand/hoggies | app yes (`ee/` excepted) | **no** | mascot "Max" is a trademark; not reusable |
| OpenHuman / Tiny Place | yes | **GPL-3.0-only** | copyleft only | caveats | two repos, one line in the brief |
| OpenPets | yes | MIT | yes | yes | clean |
| Clawd on Desk | yes | **AGPL-3.0** | strong copyleft | **no** | mascot is Anthropic IP |
| "Code Pet" | no canonical repo | — | — | — | paraphrase, not a project |
| Pet Mochi | yes | MIT | yes | yes | clean; deterministic idle, LLM salience-gated |
| Mochi LLM Pet | yes | **no licence** | **no** | **no** | all rights reserved + paid sprite pack |
| CoPet | yes | MIT | yes | yes | best normalizer to study |
| NekoAI | yes | MIT | yes | yes | good physicality reference |
| AgentPet / DesktopPet | yes (≥3 unrelated repos) | MIT | yes | caveats | umbrella name; user packs contain 3rd-party IP |
| "Claude Pet" | many, no canonical | MIT / AGPL mixed | yes (check each) | caveats | "Claude" is a trademark |
| Docusaurus "Slash" | yes | MIT code, CC-BY docs | yes | caveats | Slash is a Meta brand mark |
| Rust "Ferris" | yes | **CC0-1.0** art | n/a | **yes** | safest mascot reference |
| Bruno | yes | MIT | yes | caveats | logo is CC BY-SA; name is trademarked |
| Figma / FigJam | yes | proprietary | no | no | inspiration only |

**Safe to study and adapt (MIT):** OpenPets, CoPet, NekoAI, Pet Mochi, AgentPet.
**Do not copy:** PostHog brand, Clawd-on-Desk art, Mochi LLM Pet, any
Anthropic/Claude mascot, Figma assets. **Ferris is CC0** if a permissive mascot
reference is ever wanted. The Station already has its own artwork, so the
practical outcome is: **study patterns, do not import assets.**

---

## Part 3 — What actually makes it feel alive (behavioural)

- **Latency as acknowledgement.** React within ~100 ms of an input (a glance, a
  head-turn) *before* the real result arrives.
- **Anticipation + follow-through.** Wind up before moving; secondary motion
  (tail, glow, ring) lags the primary move by a few frames.
- **Constrained randomness.** Stamps at slightly different angles; idle cycles
  vary a little but are never chaotic or identical.
- **Idle behaviour in the periphery.** Breathing, slow blinks, gaze drift,
  self-directed activity — never demanding the centre.
- **Object permanence.** Things stay where you left them; the scene holds memory.
- **Silence as a feature.** No sound by default, no unprompted speech, no badge.
- **Presence over performance.** Co-presence (a cursor resting, a light left on)
  reads as "someone is here", not "something is performing".
- **Delight on top.** Functional → reliable → usable → pleasurable. Cute is last.

**Alive ≠ animated.** Alive = *notices · decides · remembers · settles*.

---

## Part 4 — Anti-patterns (do not build these)

- Unvalidated interruption (Clippy): showing value without a current need.
- The needy mascot: sulking, guilt, escalating when ignored.
- Forced gamification: streaks/badges that replace the goal with the metric.
- Unstoppable motion: loops with no pause/stop/hide (WCAG 2.2.2).
- Unsolicited sound; motion everywhere so nothing rests.
- Novelty that never retires (a delighter that fires every time becomes noise).
- Surprise randomness exposed to the user (the FigJam random-sticky-colour mess).
- Manufactured intimacy: first-person feelings the system does not have.
- **Motion as the only signal** — information visible only in a bounce.

---

## Part 5 — Accessibility rules for character/ambient UI

These extend the canonical contract; they do not replace it.

- **Motion is never the only information carrier.** Every companion state also
  has a text label and, where warranted, a live-region message. Urgency is
  encoded by luminance, not by movement.
- **Reduced motion replaces, not deletes.** Travel/spring/parallax become an
  opacity cross-fade, an instant pose change, or a static status glyph.
- **Two independent controls.** Honour OS `prefers-reduced-motion` *and* an
  in-app "motion" preference; the OS preference always wins.
- **Pause/stop/hide** for anything looping past ~5 s; never auto-trigger motion
  from load or scroll (WCAG 2.3.3).
- **Vestibular safety:** amplitude small, duration short, no parallax/spin/zoom,
  movement out of the periphery while reading.
- **Migraine/low-energy:** dark default, no flashing, ideally one mover at a
  time, animation capped in the low hundreds of ms.
- **Sound is opt-in** and never the sole alert.
- **`aria-hidden` decorative artwork**; actionable elements get a real label
  (already the contract's rule for the World Keeper).

---

## Part 6 — Recommended architecture for The Station

The brief's proposed pipeline is sound. Grounded in this repo, here is the
concrete shape:

```
Sources (authoritative)          Canonical model (Python)
  sections.py  SECTIONS      →     model.py: Provenance/JournalEvent
  journal.py   events        →     status.py: status vocabulary + rank
  api_manifest.py endpoints  →     world.py: mutation gates
        │
        ▼
  /api/sections (API-032), /api/status (API-003), /api/journal (API-005) ...
        │
        ▼
  world-state.js  →  WorldProjection { SectionState[], WorldSummary,
        │                                 NeedsYouState, RecentActivity[],
        │                                 Freshness, AvailableActions }
        ▼
  Expression layer (presentation only)   ← NEW, small, pure
        │   state → { companion, posture, place, object, light, motion, copy }
        ▼
  Renderer: station/ (CSS keyframes + SVG symbols in chars.svg)
            plus optional Lottie/Rive per the documented fallback chain
```

Key boundary (already a repo principle): the expression layer reads state and
never writes it. No presentation value becomes authoritative. Ambient life is
deterministic and needs no network, model, or server call.

---

## Part 7 — Semantic state vocabulary (minimal)

Do not copy the pets' lists wholesale. The Station's world is calmer than a
coding agent's; most of the time it is `quiet`. Proposed canonical vocabulary —
**two tiers**, exactly as CoPet (dwell + auto-idle) and OpenPets
(temporary vs long-running) do:

**Base states (durable):**

| State | Meaning | Trigger | Urgency |
|---|---|---|---|
| `quiet` | nothing asks for you | default | ambient |
| `resting` | dormant after long quiet | long idle | ambient |
| `alive` | ambient self-directed activity | timer | ambient |
| `working` | something is being produced | agent/tool/build running | active |
| `reading` | inspecting/reading, not changing | read/search activity | active |
| `needs_you` | blocked on your decision | permission/question/blocker | attention |
| `stale` | truth is old / unverified | freshness lapse | attention |
| `problem` | a real failure | error/failed status | attention |

**Transient reactions (overlays with a short TTL):** `arrived`, `noticed`,
`created`, `changed`, `succeeded`, `celebrating`. These decay back to the base
state. Never model them as durable states.

Accessibility mapping: `ambient` = silent; `active` = polite live region;
`attention` = assertive but throttled. Under reduced motion each state resolves
to a static pose/glyph plus the same text.

---

## Part 8 — Companion contract (matrix)

Each companion implements the *same* semantic contract and expresses it in its
own activity. Never a facial-expression system; use **activity-based posture**.

| State | Mermaid (companion) | Ratatoskr / Squirrel (VEFR) | Robot (Workshop) | Burrito (news) | World Keeper |
|---|---|---|---|---|---|
| quiet | drifting, slow breath | asleep by a quiet node | workshop lights low | truck parked, closed | slow orbit |
| resting | sleeping | curled up | powered down | canopies down | dim |
| alive | looking around | rummaging | tinkering | idling | ring breathing |
| working | reading/organising | carrying tools | welding | preparing/serving | orbit brightens |
| reading | reading | gathering | measuring | skimming | holding steady |
| needs_you | turns toward you | holds tool up | holds a part out | flags you | a node pulses |
| stale | looks away, faded | nest looks old | dust gathers | sign unlit | ring dims |
| problem | startled, small | drops a nut | spark/smoke puff | flat tyre | orbit stutters |
| succeeded | small smile | stashes nut | holds glowing object | serves a plate | a new star |

Rules: one companion per domain; a companion may *visit* another area only as a
temporary reaction, never as a permanent move; a companion never blocks a
control, never covers text, and never speaks in the first person unprompted.

---

## Part 9 — Spatial & ambient rules

- **Scene graph, not dashboard.** Every companion has a home node
  (`sections.py` `egg` mapping already provides this).
- **Movement:** short, purposeful, rare. A companion moves *toward* a thing that
  changed; it does not wander to fill time.
- **Objects:** events may briefly produce an object (a parcel, a page, a new
  star). Objects expire or are grouped; they must never accumulate into clutter.
- **Persistence:** persist *where companions are and small traces of history*
  (localStorage or server-side per `world-state.js`), not a fake growth metric.
  Reload restores the room, it does not reset it.
- **No gamification:** no XP, streaks, or points. "Lived-in over months" comes
  from traces of real use, not a number going up.

---

## Part 10 — Asset / Figma pipeline

The repo already answers most of this, and it says: **do not add a framework for
its own sake.**

- Keep `station/` framework-free (static HTML/JS/CSS). Today's animation is CSS
  keyframes + SVG symbols in `chars.svg`; that is proportionate.
- Figma stays the source for *rigs and poses* only, exported as SVG, with tokens
  from `design/tokens.json` as the single colour/typography source. Rig sources
  live in `design/assets/companions/`.
- The Mermaid master (`.lottie`) is **byte-identical by decision** and is not
  runtime-served. If richer motion is ever needed, the documented fallback chain
  is **Rive → Lottie → SVG**, with SVG as the always-available floor. Do not
  introduce a runtime player until a specific effect cannot be done in CSS/SVG.
- A per-companion `companion.json` *manifest* is only justified if/when
  companions become installable packs (theme-pack framework already sketches
  this with `animation.format="dotlottie"`). Until then it is unnecessary
  machinery.

---

## Part 11 — Prototype plan

**Prototype A — Stateful companions (no movement).**
Bind `chars.svg` pose/opacity to real `WorldProjection` state for the five
companions, with text equivalents.
*Success:* every base state renders an understandable static pose; reduced
motion yields the same information; axe + the existing Playwright gate stay green.

**Prototype B — Spatial reactions.**
Companions move toward the area that changed, carry an object, then return.
*Success:* motion is interruptible/pausable, never blocks a control, never the
sole signal, and idle cost stays near zero (no timers above ~1 Hz).

**Prototype C — Living Station.**
Deterministic ambient life + temporary objects + persisted positions.
*Success:* a 30-second watch reads as "this place is inhabited" with companions
disabled; the world settles back to quiet; no LLM call is made; CPU stays low on
a hidden tab.

---

## Part 12 — What NOT to build

- LLM-driven idle animation (cost, nondeterminism, "surprise" the user cannot
  predict) — gate any flavour behind salience + cooldown, as Pet Mochi does.
- Notification-centre behaviour and unread badges.
- Streaks, points, evolution/XP, pet growth.
- Companions that initiate text or speak in the first person.
- Parallax, spin, zoom, or anything that moves the periphery while reading.
- Motion-scaled urgency (fast = urgent); urgency is luminance + text.
- A character-pack runtime/format before there is a second consumer of it.

---

## Part 13 — Sources

- CoPet (MIT) — normalizer, dwell/auto-idle: github.com/ChanceYu/CoPet
- OpenPets (MIT) — 13 states, priority merge: github.com/alvinunreal/openpets
- Clawd on Desk (AGPL) — concurrent-session priority: github.com/rullerzhou-afk/clawd-on-desk
- Pet Mochi (MIT) — deterministic idle + LLM salience gate: github.com/cskwork/pet-mochi
- NekoAI (MIT) — physicality/presence: github.com/nucket/NekoAI
- FigJam delight (interaction language, materiality): productboard.com/blog/how-fig-jams-dedication-to-delight-helped-build-a-thriving-design-community
- WCAG 2.2.2 Pause/Stop/Hide; WCAG 2.3.3 Animation from Interactions
- prefers-reduced-motion (MDN); Tatiana Mac, "prefers-reduced-motion"
- PostHog brand licence (PolyForm Strict): github.com/PostHog/brand/blob/main/LICENSE
- Rust Ferris (CC0-1.0): rustacean.net