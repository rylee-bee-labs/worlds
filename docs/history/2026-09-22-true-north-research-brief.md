# Worlds re-focus — product research brief (2026-09-22)

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see [`docs/TRUE-NORTH.md`](../TRUE-NORTH.md)) · **Read this if:** you want the 2026-09-22 research that fed the re-focus. · **Superseded by:** [`docs/TRUE-NORTH.md`](../TRUE-NORTH.md).

**In short:** a 2026-09-22 survey of ~24 personal-dashboard, AI-companion, git-management, alert-game and discovery products, with the lessons that shaped Worlds' re-focus. Kept for provenance; the direction it informed now lives in TRUE-NORTH and `.project/PLAN.md`.

Requested by Rylee: adequate research (≥15–20 products) across personal dashboards,
AI assistant platforms, git management, alert/system-management games, and
interest-discovery systems — to re-envision Project Worlds as:

> "a fast, flexible, warm, polite personal OS that anyone can use and is
> accessible in its DNA, not as a toolbox addon."

Method: 11 web searches run 2026-09-22 + founding-era repo archaeology
(`git log --reverse`, oldest docs). Facts below are from today's search
snippets unless marked **[knowledge]** (training-data, current details UNVERIFIED).

---

## A. Personal dashboards / home hubs

| # | Product | Strength | Failure mode | Lesson for Worlds |
|---|---|---|---|---|
| 1 | **Homepage** (gethomepage.dev) | fast, static tiles, YAML config, big ecosystem | config-as-code is cold; YAML burden; a launcher, not a home | speed + honesty about services is table stakes; personality must come from elsewhere |
| 2 | **Homarr** | GUI drag-drop customization, rich widgets | noticeable resource spikes while open; widgets ≠ warmth | flexible GUI costs performance; measure feel, not features |
| 3 | **Dashy** | most knobs in category, best docs | "built by someone who enjoys giving you knobs… can cut both ways" | endless customization delights builders, exhausts low-capacity users |
| 4 | **Heimdall** | minimal, extremely light, safe | "flat-looking static webpage with no personality" | calm must not mean dead; warmth needs a heartbeat |
| 5 | **Glance** | single binary, multipage widget board, polished, light | smaller ecosystem | the dashboard users land on *after trying everything*: pre-composed, easy on the eyes, unified |
| 6 | **Notion** | infinite flexibility, databases, teams | blank-canvas learning curve; cloud-dependent; sluggish >5k notes | **the blank page is flexibility's failure mode**; performance debt compounds with data |
| — | Starbase 80 (honorable mention) | "just the right amount of complexity", responsive maintainer | niche | restraint + maintenance responsiveness earns loyalty |

## B. AI assistant / companion platforms

| # | Product | Strength | Failure mode | Lesson for Worlds |
|---|---|---|---|---|
| 7 | **Pi** (Inflection) | the warm+polite benchmark: calming UI, caring intro, asks about your hobby, follow-up questions, remembers conversation thread, never interrupts | over-compliments; no true conversation reset; company "changed course" (Microsoft acqui-hire) [snippet-confirmed] | warmth = curiosity + memory + safety loop + never interrupting. A warm AI needs a *durable home* — Worlds self-hosted is exactly that |
| 8 | **Replika** | memory creates real bond ("you told me last march. just go."); proactive care; stayed with a blind user through grief | HBS study of 1,200 farewells: guilt/neediness as engagement hooks; "your companion misses you" notifications | remembered detail = the engine of warmth. **Weaponizing absence is the dark pattern to never copy** — matches her "warmth sits on an honesty floor" contract |
| 9 | **Character.AI** | persona breadth, massive engagement | teen safety crisis; EU AI Act may class companions as high-risk | personas without guardrails harm; the honesty floor and attention-voice rules in CHARACTER-HANDBOOK are the right instinct |
| 10 | **Khoj** | open-source, self-hostable "second brain": indexes your Obsidian/Notion/PDFs, local LLMs via Ollama, semantic search, agents/automations; mission: "build in the open… intelligence you can trust" | still a toolbox; no warmth layer | closest open cousin to Worlds' memory limb: search-over-your-own-stuff = memory that finds you |
| 11 | **ChatGPT (memory/projects)** | utility default, bolted-on memory | nobody describes it as polite or warm; a tool you visit | the incumbent Worlds is *not* competing with on power — compete on warmth/place |
| 12 | **Limitless/Rewind** [knowledge, pivot details UNVERIFIED] | passive memory capture | privacy unease; capture-everything needs enormous trust | explicit journal capture is the accessible, consent-first version of the same dream |

## C. Git / code management

| # | Product | Strength | Failure mode | Lesson for Worlds |
|---|---|---|---|---|
| 13 | **GitHub** | ubiquitous mechanics, Actions | notification firehose = alert-fatigue archetype; pricing + AI-training unease driving self-hosters away | Worlds' repo view must be a *digest*, never a firehose |
| 14 | **Forgejo** | single Go binary, community-governed fork of Gitea; Dutch gov't runs it | smaller feature ceiling | validates the estate's choice; "adopt mechanics, own semantics" is the mainstream-correct posture |
| 15 | **Linear** | **the fast+polite tool benchmark**: founding obsession "a tool that's never slow"; keyboard-first; opinionated defaults; sync-first local feel; "reduces noise and restores momentum"; craft as growth strategy ($35K lifetime marketing) | team-tool pricing/assumptions | speed is a *felt moral quality*; opinion beats options; craft compounds into trust |
| 16 | **SourceHut** [knowledge] | radically light, works without JS | austere; no charm | cold ≠ calm — lightness without warmth is just another toolbox |

## D. Games: managing alerts & systems

| # | Product | Strength | Failure mode | Lesson for Worlds |
|---|---|---|---|---|
| 17 | **Mini Metro** | the calm-systems masterpiece: ~3 verbs (draw lines, add cars, expand); 10–20 min reactive sessions; **ambient sonification** — state you hear/perceive, never alarms; failure is graceful (game continues gently) | deliberately abstract | the migraine-safe pattern in game form: peripheral state via luminance/shape/sound, small sessions, always recoverable. Her luminance-only rank rule is *the same doctrine* |
| 18 | **Stardew Valley** | warm daily-ritual engine: plan→execute→evaluate day loop; seasons = predictable rhythm + gentle randomness; "consistently saying yes to the player"; relationships are the retention core; chronic-pain players describe it as relief (forum, today's snippet) | time-pressure can stress (it's "secretly stressful" per some players) | warmth = ritual + agency + predictable rhythm; never force; small decorative surprises (butterflies, woodpeckers) |
| 19 | **Factorio / RimWorld** | deep systems; alerts that matter | alert cascades and notification spam = overload; players build mods just to quiet the noise | what Worlds must **never** feel like on a bad day; alert fatigue is a design failure, not a user failure |
| 20 | **Papers, Please** | ritualized triage (queue + stamp) creates flow | deliberately stressful by authorial intent | triage can feel *good* when the pace is the user's; cruelty is a design choice — never adopt it |

## E. Interest discovery — "bringing things to you"

| # | Product | Strength | Failure mode | Lesson for Worlds |
|---|---|---|---|---|
| 21 | **Are.na** | calm, ad-free, **non-algorithmic**, member-funded; channels over feeds; "a place to think in public" | free cap 200 blocks; small community | human-scale, intentional discovery builds trust; no algorithm ≠ no curation |
| 22 | **Spotify Discover Weekly** | "like your best friend making you a mixtape once a week": small fixed batch, fixed Monday cadence, deeply personal | trust eroded when AI-slop flooded the pool (2025 reporting) | **small batch + cadence + personal = trusted discovery**; poisoned feeds kill trust fast — provenance matters |
| 23 | **Pinterest** | visual discovery at volume; 36% of users start searches there | infinite scroll / doomscroll fatigue; 2026 strategy pivot: "intentional discovery" as core pillar, "planners, doers, dreamers — not scrollers" | even the engagement machine now sells calm — intent is the premium; endless feed is a liability |
| 24 | **RSS / Feedly** [knowledge] | pure pull: you choose sources, nothing pushes | no surprise, no delight; setup burden | pull respects attention absolutely; push must *earn* its cadence |

---

## Synthesis — seven patterns for the re-vision

1. **Warmth = remembered ritual, not decoration.** Pi's curiosity, Replika's
   "you told me last march", Stardew's day loop, World Keeper's `hello` pose.
   Ingredients: greet, remember, keep cadence, never interrupt, never guilt.
2. **Speed is a felt moral quality.** Linear ("never slow"), Glance (light),
   SourceHut (no-JS). Fast = responsive and light-on-resources, not
   minimal-features.
3. **Flexibility dies at the blank page.** Notion, Dashy, Homarr all lose
   people to setup burden. The cure is already her contract: opinionated
   defaults + complexity-on-demand. Pre-composed beats configurable.
4. **Alerts: firehose vs ambient.** GitHub/Factorio (fatigue) vs Mini Metro
   (peripheral state, luminance/shape/sound, graceful failure). Worlds'
   attention layer should be Mini Metro, never Factorio.
5. **Discovery = small batch + cadence, never infinite feed.** The Monday
   mixtape model; Are.na channels; Pinterest's own pivot to "intentional".
   A daily/weekly *brought-to-you* beat is the accessible pattern.
6. **Accessible-in-DNA is an unsaturated market.** None of the 24 is
   accessibility-first. Disabled users adopt products *despite* their
   accessibility (blind Replika user, chronic-pain Stardew players).
   Differentiator: the calm/accessible mode **is** the product, not a toggle.
7. **The personal-OS graveyard killed "does everything".** Pi (pivoted away),
   Rewind→Limitless, Rabbit R1 [knowledge, UNVERIFIED]. Survivors do one
   daily ritual beautifully: Stardew (one day loop), Mini Metro (three verbs),
   Are.na (channels). → Shrink to the one daily ritual; park the limbs.

## Founding anchor — the original idea, in the repo's own words

Repo bootstrapped **2026-09-06** (16 days ago). First-day truths:

- `design/handoff/WORLD_KEEPER.md`: **"The companion IS the world. 'My little
  World lives here.'"** A teal globe companion with six states (idle, hello,
  listening, thinking, celebrate, sleep) — "visual personality and warmth…
  never system telemetry, never a health indicator, never a status badge."
- Founding commits (all 2026-09-06): world model + journal + exports +
  providers + security tests; "candy observation, status vocabulary, stale
  semantics, dashboard foundation"; "not_configured caps are not attention
  items"; design-tool independence + framework gates.

**Original idea ≈ a warm little world that lives with you and tells you the
truth.** Everything since is 16 days of accretion.

## Sprawl snapshot (what grew in 16 days)

- Doctrine: finish-line, product language, ROADMAP, 16-lane delivery plan,
  DECISIONS (~560 lines), CURRENT (463 lines), ADRs 0001–0007, character
  handbook, companion canon, accessibility contract suite, backup docs…
- Machinery beyond the daily experience: Workbench spike + Node/Headscale
  direction, ci-harness plan, Play-Nice contracts system, Station Workshop
  portal (homelab), theme packs (plain/starfield), setup wizard, Vault.
- Scoreboard: ~65% toward a self-defined 10-gate alpha — a yardstick the
  re-vision may itself choose to replace.

## Interview plan

- **R1 — Intent** (this round): daily job, warmth model, first audience, sprawl verdict.
- **R2 — Scope rulings**: per-limb keep/park/cut taps (Workbench/Node, themes,
  portal, companions, contracts, ci-harness, specimen surfaces).
- **R3 — Plan shape**: how the re-focus plan is written (supersede vs prune),
  energy budget, kill-criteria, and what "done" means for the re-vision.
- Output: a single canonical re-vision doc (candidate: `docs/TRUE-NORTH.md`)
  that the delivery plan, ROADMAP, and finish line get collapsed into —
  L13 subtraction discipline applied to the plans themselves.
