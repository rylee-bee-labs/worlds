# The Station — deck map

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see `.project/PLAN.md`) · **Read this if:** you want the dated eight-deck design record behind today's crew and doorways · **Superseded by:** [`.project/PLAN.md`](../../.project/PLAN.md) (current product shape); crew/room canon lives in [`docs/COMPANION-CANON.md`](../COMPANION-CANON.md) and [`docs/CHARACTER-HANDBOOK.md`](../CHARACTER-HANDBOOK.md)

**In short:** A dated record of the eight-deck "Station" plan and its design dialects, kept for provenance. Since the 2026-09-22 flip the interface is `ui/` (the Bridge is home) and the server-rendered Station is retired as a **theme package**; the `frontend/` paths once referenced here are the deleted pre-flip tree. This is not current state.

**Owner canon.** Deck names were re-anchored to **plain job words** by owner
direction 2026-09-18 (*accessibility over cuteness when forced: the plain word is
the label, the dialect is the delight*). The logical deck plan of **The Station**
(Project Worlds): eight decks, each named for the job done there, each with a
resident — except `Settings`, which is an icon.

**What changed since:** the current architecture is **rooms** (independent services
Worlds renders) plus a per-person **crew**, **keepers** and a closed list of
**doorways** — the deck names below survive as canon, but the product shape is in
`.project/PLAN.md`, and residents/rooms in `docs/COMPANION-CANON.md`.

- **Character and voice truth** (who each resident is) →
  [`docs/CHARACTER-HANDBOOK.md`](../CHARACTER-HANDBOOK.md).
- **Names, ids, and the station-id ↔ server-key mapping** →
  [`docs/COMPANION-CANON.md`](../COMPANION-CANON.md).
- This file owns the **map** only: which deck exists, what its job is, and who is
  there.

### Naming: plain word + invented dialect (owner direction, 2026-09-18)

Every deck has **two layers**, and they never compete:

- the **name** is a plain, familiar job word — the accessible label you can act on
  without decoding anything;
- the **dialect** (§4) is the invented visual language — the personality, which is
  decorative and never load-bearing.

Ship-flavoured names were retired on 2026-09-18. **Historical documents keep the
old names** (history is not rewritten); this is the mapping:

| Retired name | Deck name | Dialect (§4) |
|---|---|---|
| Bridge | **Today** | the Transmission |
| Engineering | **Systems** | the Loop Line |
| Workshop | **Projects** | the Blueprint |
| Archives | **Journal** | the Library |
| Galley | **News** | the Food Court |
| Observatory | **Interests** | the Constellation |
| Vault | **Records** | the Bank |
| Quarters | **Settings** | the Quiet Room |

---

## 1. The eight decks

**Every name is a job, in plain words.** A deck is not a rank or a title — *Today*,
*Projects*, *Records* and the rest name the work that happens there. The deck plan
places the crew; it is not a hierarchy. This stays consistent with
[`docs/CREW-AND-STATION-THESIS.md`](../CREW-AND-STATION-THESIS.md) §1 (*no ranks and
stations, no franchise framing*): these are job names, not crew roles, and carry no
borrowed franchise vocabulary.

| Deck | Its job | Product area | Resident |
|---|---|---|---|
| **Today** | Personal presence, communications and visibility — what is coming in to you, and conversation | Chat / Companion | **Renai** |
| **Systems** | Settings, depth and the lifelines across the product; keeping the machinery healthy enough that dramatic problems never happen | Systems | **Hekek** |
| **Projects** | Making things together — building, learning by doing, checking the work | Projects / Lab | **Bolt** |
| **Journal** | Carrying knowledge between worlds; finding paths and connections across lore and memory | Journal / Memory | **Ratatoskr** |
| **News** | Bringing the outside world home — news, stories, city life, at a wander-over pace | Media | **Burrito Journalism** |
| **Interests** | Watching, note-taking, and noticing patterns before they are understood | Interests | **Mira** |
| **Records** | Careful preservation with provenance — remembering where things came from | Records | **Bruma** |
| **Settings** | Rest, privacy, safety, quiet — and where your personalization options live | Settings / rest | **icon — no character** |

The *Product area* column is a **proposed** deck → surface mapping, not owner
canon and not yet implemented; see §3.

---

## 2. Settings is an icon, not a resident

`Settings` does **not** need a character. It is a stylized bed icon in the same
visual language as the crew icon set: simple rounded silhouette; bed, pillow,
folded blanket; dark navy and warm gold; optional tiny star or crescent; no face,
no personality. It should read clearly at 16px, 32px and 48px, and must not use
colour as the only meaningful signal. It communicates **rest · privacy · safety ·
quiet** (see [`docs/ART-REQUESTS.md`](../ART-REQUESTS.md)).

Do not add `Settings` as a companion, a station id, or a server key.

---

## 3. The crew is the default — and it is a setting (owner canon, 2026-09-17)

The residents in §1 are **the default crew**: they ship in the box, and they are
also the owner's own crew. They are not the only possible crew.

- **A deck is a job; a resident is who does it.** The **eight decks are fixed** —
  they name the work (Today, Systems, …). **Residents are assignable.**
- **Which resident sits on a deck is a setting.** Anyone can create their own
  resident and assign them to any deck — including Settings, where the bed icon is
  the default when nobody is assigned.
- **A created resident is a resident pack** (name, role line, voice, art),
  installed and uninstalled with provenance — the existing "a new identity is a
  pack, not a one-off" mechanism
  ([`docs/CREW-AND-STATION-THESIS.md`](../CREW-AND-STATION-THESIS.md) §5).
- By default **one resident per deck**; a resident may still *visit* another deck
  as a temporary reaction, never a silent permanent move.
- **The setting never touches the accessibility floor.** It is a product
  preference alongside theme and companion — *not* a key in
  [`docs/accessibility/PREFERENCES_SCHEMA.json`](../accessibility/PREFERENCES_SCHEMA.json),
  which is the comfort floor. No crew choice may remove a label, a control, or a
  route to functionality; residency never carries critical information
  (thesis §3.1).

This does not weaken the thesis — *nobody has to become more like the others
first.* It extends it: nobody has to keep the shipped crew first, either.

---

## 4. One world, eight dialects (owner direction, 2026-09-18)

owner direction (2026-09-18): the rooms should feel **distinct and purposeful** —
each room may speak its own visual dialect — while **colours and theming stay
consistent**. And the surfaces being replaced are **not abandoned wholesale**: a
room should still read like the thing it replaces — a front desk is still a front
desk, a workshop is still a workshop. Familiar roles are why a room is legible on
day one.

Four rules:

1. **Familiar job, invented dialect.** Every deck keeps the plain job it already
   has (§1 *Product area*). A dialect changes *how a room arranges its content*,
   never *what the room is for*.
2. **One palette, one floor.** All dialects share the same design tokens, the same
   type ramp, the same component vocabulary, and the
   [accessibility floor](../accessibility/ACCESSIBILITY_CONTRACT.md). A dialect may
   never add a colour, a size, or a gesture the other rooms do not have.
3. **The dialect never hides the job.** Every room carries its name and a
   plain-language job line, in the same place, in every dialect. A dialect is
   dress over a legible function — never a puzzle, and never the only signal.
4. **One place.** All rooms share the same environment — the same stars outside
   every window, the same lamplight, the same deck underfoot — so the station
   reads as one hull with eight compartments, not eight unrelated screens. A
   dialect changes what a room *holds*, never where it *is*.

### The dialects (owner pass, 2026-09-18)

The owner refined every room in one sitting (2026-09-18). The dialects below are
owner-described; the right column is the essence in the owner's words.

| Deck | Familiar role (kept) | Dialect | One-line essence |
|---|---|---|---|
| Today | Communications / visibility | the **Transmission** | what is coming in to you |
| Systems | Settings / depth | the **Loop Line** | settings and depth; the lifelines across the product |
| Projects | Projects | the **Blueprint** | fun and tinkery — GitHub-flavoured, easy to manage several projects |
| Journal | Memory / lore | the **Library** | a sci-fi library — *Voyager's* astrometrics, the Jedi archive |
| News | News / hangout | the **Food Court** | where you go to eat, so the news and the neat things gather here too |
| Interests | Interests | the **Constellation** | what the universe has in store — drill down by category, and it grows or shrinks with your current interest |
| Records | Records / backups | the **Bank** | a sci-fi bank and records keeping |
| Settings | Personalization | the **Quiet Room** | where personalization options live |

The dialects are explored as concept pages in the showcase (packets 1–8, the
Transmission, the Dialect Sheet); they are **concepts, not implementation**. No
dialect is wired into `src/` yet.

---

## 5. Rooms announce themselves — and open up (owner direction, 2026-09-18)

Owner direction (2026-09-18): the station should read the way good set design
reads — you know **where** you are, and **whose** room it is, *before anyone tells
you*: the way a vault reads as a vault, and a room's colours and lines announce
its purpose. And it should always hold one more thing to look at, without ever
nagging. The owner's words: *"easy to move between things, the assistant always
available… a more interesting, calmer, more useful place… I almost want to hate to
put it down."*

**The feeling is the requirement; consistency is how it survives.** Everything
below exists to produce one felt quality — and to keep it identical from room to
room:

> **Calm, cared-for, curious, unhurried. A well-kept place where someone is home —
> competent without being cold, alive without being loud, deep without being
> heavy.** You should want to stay a while, and never feel behind.

The target is **one** feeling: the room changes, the *feel* never does — same
warmth of light, same restraint, same quiet rhythm, same voice, same density.
Moving between rooms must never cause whiplash. If a room seems to need a
different *feel* to work, the design is wrong, not the feel.

Four mechanisms, and one rule that holds them together. Each is a **rule**, not a
decoration.

1. **Signature — identify before reading.** Every room carries the *same four*
   channels, always **together**, never any one alone (colour-blind safe —
   [contract §1.3](../accessibility/ACCESSIBILITY_CONTRACT.md)):
   - **colour** — the room's one accent (§4);
   - **line** — the room's geometry (rings, a loop, a drafting grid, stacks, a
     board, a chart, a door, near-nothing);
   - **light** — the room's lighting habit (where its lamp sits, how warm);
   - **silhouette** — the room's outline at a glance.

   **Cover the name and you should still know the room.** If you cannot, the room
   is unfinished.
2. **Depth you can descend into.** Every room has a Level 1 (a glance) that is
   complete on its own, down to a Level 4 (the technical guts) that is always
   reachable *from inside the room* — a place you walk into, never a separate
   settings mode. "Opening the panel" is spatial, not a toggle. (The product
   contracts are `complexity-on-demand` and `progressive-disclosure`; this makes
   them a *place*.)
3. **Always one more thing — calmly.** Each room keeps a small, changing set worth
   a look: what is new, what is mending, the one thread that was found. Discovery
   is **bounded and opt-in**: no infinite feeds, no streaks, no red badges, no
   urgency, no guilt. The pull is depth and care, never a dopamine loop.
   *Quiet-when-healthy still wins* — "nothing needs you" is a good room.
4. **The assistant is always at hand; movement is free.** From anywhere, ask. From
   anywhere, move to any room in one step, with no dead ends and no lost place.
   Wayfinding and the assistant are one promise: *you are never lost, and never
   alone in it.*
5. **Same hand, every room.** The consistency rule that holds the other four
   together. One voice, one rhythm, one temperature, one level of restraint — in
   every room and under every theme. This is **not** "same tokens" (that is §4.2);
   it is *same feel*. A room that is louder, colder, busier, or chattier than its
   neighbours is a **bug**, even if every token is legal.

**Copy guard.** Reference the *feeling* freely, but keep franchise lexicon out of
the product: name our own things in our own words (no borrowed ship, deck or
corridor vocabulary in the UI).

> This section is the *experience* thesis; §1–§4 are the map and the dialects.
> Nothing here is wired into `src/` yet.

---

## 6. Storyteller sci-fi — everyone builds their own tools (owner direction, 2026-09-18)

Owner direction (2026-09-18): *"what if sci-fi was written by storytellers, and kept
a strong tradition of vocal and written language, instead of just tiny screen alerts
and beeps and boops?"* And: *"what would the tech be like if Renai made it and used
it every day… hers would be different than the others."*

**The thesis.** This is a literate, oral culture that went to space. Its technology
is **written and spoken before it is displayed**: language first, light second,
sound never as a beep. Nothing pings. What arrives is **told, or it is written** —
and never a chime.

**Everyone builds their own tools.** The resident of a deck doesn't just use it —
they *make* it, in the medium of their own nature. The dialect (§4) is not a
skin: it is the maker's **native language**, and the instrument is shaped by who
built it. A visitor recognises the maker by the tool.

| Deck | Resident | Their medium — the tool they'd build |
|---|---|---|
| Today | **Renai** | **letters & the telling** — correspondence, spoken aloud on request, marginalia in her hand |
| Systems | **Hekek** | **brass instruments** — engraved gauges and dials; maintenance felt as a reading, not a log |
| Projects | **Bolt** | **the bench** — chalk, jigs and pinned drawings; tinkering you can pick up |
| Journal | **Ratatoskr** | **threads & knots** — memory tied, not filed; a story is a cord you follow |
| News | **Burrito Journalism** | **the broadsheet** — printed pages and a market stall; stories traded, not fed |
| Interests | **Mira** | **field notebooks & star-charts** — sketches, observations, a thing not yet named |
| Records | **Bruma** | **the ledger & the shelf** — record slips, stamps, a place for everything |
| Settings | *(none — an icon)* | **the plain room** — deliberately unadorned; rest needs no instrument |

**Rules for a maker's instrument** (they do not override §4–§5 or the accessibility
floor — they extend them):

1. **Language first.** Every arrival has words. Voice is an *option on top of text*,
   never a replacement — a person who cannot hear loses nothing.
2. **Nothing pings.** Status is stated or written. No chimes, no beeps, no red
   badges. Urgency is carried by plain words, not by sound or colour.
3. **The maker's hand is visible.** The resident's medium shows in the form itself
   (a letter, a gauge, a thread) — so you can tell whose room you are in by the
   instrument, before you read a label.
4. **Same floor underneath.** Whatever the medium, the same 44&nbsp;px targets, same
   labels, same contrast, same motion rules hold. A handmade tool is still an
   accessible tool.

**The technical layer is also the maker's choice.** The *lived* surface stays in
the maker's medium; the **technical** layer — the overlay, the scan, the readouts —
is the instrument that maker reaches for, and it *clashes on purpose* with the
surface. **Renai's technical layer is the comm-badge Focus**: the small badge she
wears projects a Horizon-style lens (reticles, tags, wireframe readouts, scanning)
over a written world. The other makers' technical layers are **deliberately
undecided** — we find each one when we build the room.

**Alerts are about the subject, not the sender (owner direction, 2026-09-18).** A
notification names **what the user needs to know**, not who produced it: a **round
icon from one icon pack** (medicine · a system · a note · a record · an event · a
connection · an interest · news · rest) plus a **plain chip** with the detail. The
name of whoever is involved belongs **in the sentence**, not on the button. A
resident **may leave one signed line in their own voice** (*"I'll keep this safe for
you!" — Bruma*); the voice is flavour, never the organising principle. The icon is
**never the only signal** — the chip always says it in words. Concept:
`design/concepts/icon-pack.html` (archived; tag `archive/pre-design-cleanup-2026-09-25`).

**Copy guard.** The vocabulary is ours (see §5): no borrowed ship, deck or corridor
words, and no "beep".

> §1–§5 are the map, the dialects and the wayfinding rules; this section is the
> *culture* that explains why the tools look like that. Exploration only — nothing
> here is wired into `src/` yet.

---

## 7. Open / UNKNOWN

- **Deck names are owner canon; the implementation is not.** No deck plan exists
  in the Station or the server today. Whether the Station exposes decks as
  navigable areas is **UNKNOWN**.
- **Product areas are proposed.** Which product surface each deck maps to
  (Chat, Systems, Projects/Lab, Journal/Memory, Media, Interests, Records,
  Settings) is a proposal recorded above; the owner spec names decks and
  residents, not surfaces.
- **Three area residents are not in the repo.** Hekek, Bruma and Mira are owner
  canon (2026-09-17); their station ids / server keys (`hekek`, `bruma`, `mira`)
  are **proposed** and unread by any code or asset. See
  [`docs/COMPANION-CANON.md`](../COMPANION-CANON.md).
- **Settings has no id.** It is an icon, not a resident — unless someone assigns
  one to it (§3).
- **Resident creation and assignment are a concept, not an implementation.** The
  2026-09-17 concept in §3 says anyone may create residents and assign them to
  decks; no creator, pack format, or assignment model exists in the code yet.