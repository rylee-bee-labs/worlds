# TRUE-NORTH — Worlds

> **Superseded in part by [ADR-0008](adr/0008-front-door.md) (2026-10-01):** its scope, the core-four navigation and Chat in the core are superseded (S1, S3). Accuracy and accessibility principles still hold.

> **Status:** Direction · **Verified:** 2026-09-26 · **Canonical for:** vision, the five commitments, and the accuracy and accessibility principles · **Read this if:** you need *why* Worlds is designed this way; for *what we are building now* read [`.project/PLAN.md`](../.project/PLAN.md) first

**In short:** This is the owner-approved direction: the vision, the five commitments (fast · flexible · warm · polite · accessible by default), the daily home loop, and the alpha gates. Its **scope and sequencing are superseded by `.project/PLAN.md`** (owner-approved 2026-09-25) — where they conflict on scope or order, PLAN wins. The accuracy and accessibility principles here still hold.

**Provenance:** canonical direction, owner-approved (human, Rylee) 2026-09-22 with four refinements; built from a three-round owner interview (18 taps + typed answers) after a 24-product research pass. **Supersedes as direction:** `WORLDS-DELIVERY-ORCHESTRATION-PLAN-2026-09-21.md` (historical record), `docs/PERSONAL-WORLD-FINISH-LINE.md`, `ROADMAP.md` (both remain as historical detail where this doc is silent).

**Authority boundary (owner refinement 4):** TRUE-NORTH owns **direction
only**. `.project/DECISIONS.md` remains the append-only decision history —
never rewritten. ADRs (`docs/adr/`) and the contract system (accessibility,
`SECURITY.md`, human reliability, Play-Nice adoption) **retain their own
authority** in their domains. This doc routes; it does not overrule.

---

## Vision

> Worlds is a **fast, flexible, warm, polite personal app**: one place where
> everything that matters is reachable **without searching for it**,
> **accessible from the start rather than as an add-on**, built for Rylee's
> daily life first and designed so others can use it too.

## Owner's philosophy (verbatim, 2026-09-22)

> The World Keeper is the heartbeat, not a telemetry badge. Memory works when
> AI is unavailable. The interface respects how much attention you have
> available. And the product doesn't demand that you configure everything
> before it becomes useful.
>
> Those aren't four separate features. They're the same underlying design
> philosophy.
>
> **Worlds should help you recover your place in your own life.**

## The original idea (founding anchor, 2026-09-06)

> "The companion IS the world. **'My little World lives here.'**"
> — `design/handoff/WORLD_KEEPER.md`, day one

In practice: a friendly app that is **always accurate**. The World Keeper globe
is a character, not a status indicator: it greets, celebrates and sleeps, and
it never shows telemetry or status (its founding rule stands).

## Five commitments (from the research)

| Word | Commitment | Doctrine source |
|---|---|---|
| **fast** | Felt responsiveness: skeleton screens instant, light assets, no spinners between landmarks | Linear ("never slow"), Glance |
| **flexible** | Good defaults, with more options available when wanted. No empty starting page. Customizing never removes the simple path for low-energy days | Notion/Dashy counter-proofs; the complexity-on-demand contract |
| **warm** | Remembered ritual: greet · remember · keep cadence · never interrupt · never guilt | Pi, Stardew, Replika's good half; guilt-on-exit dark patterns banned |
| **polite** | A few items at a time, at a pace the person has accepted. The person asks by default; notifications only when they opt in | Discover Weekly mixtape pattern, Are.na |
| **accessible by default** | The low-stimulation mode is the normal mode, not a setting. State shown by brightness, not color alone; motion reduced by default; safe for migraines first | Mini Metro ambient-state doctrine; the unsaturated-market finding |

## The one daily job — the daily home loop

*(Owner refinement 1: the loop is the daily homecoming, **not exclusively a
morning activity**. Any time of day, any device, under five minutes.)*

1. **Orient**: the Keeper greets; the home screen shows the real state of
   your systems and what needs you: real data, or `no source yet` /
   `unavailable` / `stale`. Never made up.
2. **Remember** — Memory surfaces what matters from where you left off.
3. **Resume** — yesterday's thread, one tap to pick back up.
4. **Discover** — one small **"brought to you"** card (interests, small
   batch, on a schedule, like a curated playlist on the home screen; shown
   as empty until a source is connected). No separate discovery surface in the first release.

**Loop before scope:** the owner experiences the actual daily loop before
any scope expansion (ruling 2026-09-22).

## Voice

- **One voice** across chat + attention surfaces, with **selectable tone
  registers** (proposed starter set; owner reacts on experience):
  `warm` (default) · `concise` · `playful` · `formal`.
- The residents and the two-voice system become an **optional personality
  pack** (switchable; on by default since 2026-09-25, owner: "turn it on"). `docs/CHARACTER-HANDBOOK.md` and
  `docs/COMPANION-CANON.md` survive as the pack's canon — kept, never deleted.
- Accuracy comes first: a friendly tone never makes a statement less exact, and
  degraded or off states are labelled as such in every voice.

## Scope: the first release

**Core, deep:** `Bridge · Memory · Chat · Settings` (the stable skeleton).

| Screen | Depth target |
|---|---|
| Overview (now the Bridge) | the daily home loop: greeting + real status + yesterday's thread + a small discovery card |
| Memory | journal + records; deterministic place; works with **all models off**; step-up for locked categories |
| Chat | the one voice + tone registers; clearly shows when it is off; aware of context |
| Settings | preferences, tone, themes (starfield default since 2026-09-25 · others optional), accessibility prefs |

**Projects ruling (owner refinement 2):** Projects stays **parked as a full
surface**, but Overview's project status must keep a **deterministic path
from source to details** — every status row links to its authoritative
source — and **agent-sync remains the authoritative feed**.

**Parked, labelled as such (not being built):** Interests (full surface), Map,
Media/Music — remain specimen / `no source yet`, never faked. Workbench
stays merged **behind `PW_WORKBENCH`, off**. Theme packs beyond plain +
starfield: Phase C.

**Continues:** the Node/Headscale limb (ADRs 0003–0007) — owner ruling
2026-09-22. Remote reach serves the hub-from-any-device promise.

**Estate infrastructure (not Worlds scope):** the Station Workshop portal —
mission, in the owner's terms: the easy place where **agents share what
they're building with Rylee, on any device, on her timeframe**. It stays
live; the daily digest lands there (see Execution).

## Alpha gates — recut (owner ruling 2026-09-22)

Alpha = all of these green **and** Rylee lives in Worlds daily for a week:

| Gate | Test |
|---|---|
| **G-ritual** | the daily home loop completes end-to-end on phone + desktop, <5 min, any time of day, from a real deployment |
| **G-fast** | unambiguous, measured budgets — *(owner refinement 3)* the measurement definition ships **as code with the gate**: named interaction set, measurement points, percentiles (proposal: p95 interaction <100ms local, first paint <2s LAN). Numbers live in the gate, not vibes |
| **G-real** | all four main screens: real data from the API, or a clear empty/unavailable state; no made-up data or alt text |
| **G-voice** | one voice across chat and attention messages; the tone switch works; model-off and degraded states are labelled |
| **G-memory** | pin + find a record with all models off; layout stable; locked categories need step-up |
| **G-safe** | step-up + true-loopback + friend-write-gated-until-approve end-to-end (backend done; the frontend half closes it) |
| **G-a11y** | automated suite green **and** a real screen-reader + keyboard-only walk of the daily home loop |
| **G-degrade** | matrix (model-off / provider-dead / node-offline / disk-full): every cell has a test; no fake green |
| **G-recover** | timed restore from a clean box: identities + world + journal + vault + apps. *(owner refinement 3)* **Precondition: the Vault-portability decision is closed and recorded in `DECISIONS.md` before this gate may be claimed green** |

**Retired from alpha, with reasons:** G-shape (done, `d3e6999`) ·
G-workbench (parked by ruling) · G-onboard + G-trial (moved to **beta**,
where they belong with the friend trial + L16 UAT). **RC** stays the R6
taste-pass — the packet re-shoots against the new hub.

## Execution — time-off pace, daily lanes, portal digests

Cadence ruling: **daily autonomous lanes; one digest per day posted to the
Workshop portal** (`/srv/workshop/inbox/worlds/daily-digest/<date>/`);
decisions batched to the owner as tap-questions, one queue at a time;
nobody commits but the orchestrator; explicit paths only.

| Wave | Lanes (disjoint files) |
|---|---|
| **1** | A: daily home loop in Overview (Keeper greeting + real status + thread + discovery card + project-status source links) · B: voice unification (one voice + tone registers; residents → pack flag) · C: Memory deep (deterministic place, records categories, models-off) · D: doctrine collapse (this doc canonical; plan/finish-line/ROADMAP → pointers; DECISIONS record) |
| **2** | G-fast measurement harness + budgets · G-a11y real AT walk · G-degrade matrix cells · G-safe frontend step-up UI · Node limb continues (own lane, ADR rules) |
| **3** | Vault-portability decision (owner tap) → G-recover timed restore drill · R6 taste-pass sitting on the new hub · owner daily-use week → **alpha** |

Lane remap from the retired plan: L4→W1 (skeleton-only scope) · L6→W1-B ·
L7→W1-C · L8→W2 · L9/L10→W2–3 · L11/L12/L16→beta · L13→W1-D · L-WB parked ·
L-CI parked · L-CONTRACT continues (contracts kept by ruling).

## Anti-sprawl rules (kill criteria)

1. A new surface must serve the daily home loop, or it doesn't ship.
2. New features are parked by default and are added back only when the daily loop needs them.
3. Every new doc collapses under TRUE-NORTH or exists as a pointer.
4. Flexibility additions must preserve the low-capacity path — configuration
   is never required to reach a landmark.
5. One ritual done beautifully beats ten features half-alive (the graveyard
   pattern: Pi, Rewind, Rabbit did everything; Stardew, Mini Metro, Are.na
   do one thing).
6. No scope expansion until the owner has lived the loop.

## Record of the ruling (owner interview, 2026-09-22)

Three rounds, 18 taps + typed answers: north star = calm hub, reach without
hunting · one voice with selectable tone; residents → optional pack · World
Keeper = the one heartbeat · skeleton-only scope + one small discovery card
("I love interests… if it's not too hard") · plain + starfield · Workbench
paused behind flag · **Node limb continues** · harness parked, contracts
kept · portal stays live as her async window into agent work · one
TRUE-NORTH doc · alpha gates recut · daily lanes + portal digest · time-off
pace, fast. Approval with four refinements: daily home loop (not
morning-only) · Projects parked with deterministic source-path in Overview ·
unambiguous perf measurement + Vault-portability precondition on G-recover ·
append-only history preserved, ADRs/contracts retain authority.
