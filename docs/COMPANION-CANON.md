# Companion Canon — names, roles, and the id mapping

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** companion display names, roles, and the id mapping (station id ↔ server key ↔ crew id) · **Read this if:** you are naming a companion in copy, or mapping a legacy key to a crew id.

**In short:** the human-readable name, role, and machine identifiers for each resident — and the rule that display names are canon for people while ids are canon for the code. Some historical evidence and open questions below are kept as records; the crew-id table in §2 is what the current code reads.

**Status:** Canonical for companion **display names** (owner-stated, 2026-09-17).
Not a replacement for `design/COMPANION_INTEGRATION.md` (design/art authority),
`docs/accessibility/ACCESSIBILITY_CONTRACT.md` (accessibility), or
`docs/CREW-AND-STATION-THESIS.md` (the family thesis).

**Who each resident is** — character and voice truth — is canonical in [`docs/CHARACTER-HANDBOOK.md`](CHARACTER-HANDBOOK.md); this file owns names and ids only.

> **Pack canon (TRUE-NORTH § Voice, owner ruling 2026-09-22).** The residents
> and the two-voice system are now an **optional personality pack** — on by
> default since 2026-09-25 (owner: "turn it on"; `off` gives the one voice),
> switchable via the `personality_pack` preference. This file survives as the
> pack's naming/id canon — kept, never deleted — and stays canonical for
> display names and the station-id ↔ server-key mapping regardless of the
> flag (identifiers are not renamed by a voice ruling). Nothing below is
> edited by that ruling.

> **Owner canon update (2026-09-25, stated in the Doorways design session).**
> - The smiling ringed planet is **Sol** ("her"). She is the **primary logo** and the one who pops
>   up to greet and to tell you things; the crew's commbadges are based on her. Server key and art
>   paths stay `personal-world` (display name only changes).
> - **Worlds is a place, not a companion.** A "Worlds" room has no resident.
> - The burrito truck's name is **Scoop**, from *Burrito Journalism* (the game keeps its name).
> - Ratatoskr is confirmed as the squirrel of Norse fame.
> Art for these is in `design/assets/crew/{sol,renai,portraits,doorways}` (see its README).

Two truths coexist and must not be silently merged:

- **Owner canon is authoritative for the name a human reads and hears.**
- **Repo code is authoritative for machine identifiers** (station ids, server keys,
  artwork paths). Technical identifiers are deliberately unchanged; renaming a
  display name does not rename a key or an asset.

Where this file disagrees with repo evidence, the disagreement is recorded below
(see *Remaining inconsistencies*), not hidden.

---

## 1. The residents

| Name | Role | Origin (game / repo) | Crew id | Old key (migrates) |
|---|---|---|---|---|
| **Renai** | Personal companion (the operator theme) | Owner canon 2026-09-17 (formerly labelled "Mermaid") | `renai` | `mermaid` |
| **Ratatoskr** | Worlds / lore / memory keeper: the Norse messenger squirrel | **VEFR** (owner game engine). Old design label: "World-tree Squirrel" | `ratatoskr` | `world-tree-squirrel` |
| **Bolt** | Lab / development / AI helper ("Little Helper Robot") | Repo design (`design/COMPANION_INTEGRATION.md`); personal name chosen by the owner, 2026-09-17 | `bolt` | `robot` |
| **Scoop** | Journalism / stories / city life: the **breakfast burrito truck** | **Burrito Journalism** (owner game; display name **Scoop** from 2026-09-25). Old design label: "Tacos & the Morning Paper" | `scoop` | `taco-news-truck` |
| **Hekek** | Systems: Builder · Maintainer · Steward | Owner canon 2026-09-17; starter crew since 2026-09-25 | `hekek` | *(none)* |
| **Bruma** | Records: Archivist · Keeper · Witness | Owner canon 2026-09-17; starter crew since 2026-09-25 | `bruma` | *(none)* |
| **Mira** | Interests: Observer · Note-Taker · Pattern Seeker | Owner canon 2026-09-17; starter crew since 2026-09-25 | `mira` | *(none)* |
| **Sol** | The ringed planet: Worlds' mark; greets and pops up, never speaks (display name from 2026-09-25; formerly "Personal World") | Repo product identity | *(not crew)* | `personal-world` → no companion |
| **Assistant** | The plain default voice when no companion is chosen; a computer screen with a friendly face (owner, 2026-09-25) | Worlds default | *(not crew; `companion_id: null`)* | `assistant` → no companion |

"Origin (game / repo)" says where the character comes from, not that the repo
already spells the name that way.

**These are the default crew.** The residents above ship as the default set; which
resident sits on which deck is a **setting** the user can change, including
creating their own residents (see [`docs/history/STATION-MAP.md`](history/STATION-MAP.md) §3). The
names, ids and server keys below stay canonical for the *default* crew; a
user-created resident brings its own name and pack and never renames an existing
id.

**Settings is an icon, not a resident.** The deck `Settings` has no character, no
display name beyond the deck name, and no station id or server key. It is a
stylized bed icon in the crew icon language
(see [`docs/ART-REQUESTS.md`](ART-REQUESTS.md) and
[`docs/history/STATION-MAP.md`](history/STATION-MAP.md)); do not add it as a companion.

---

## 2. Crew ids today, and the old keys they replace

**Source of truth:** `src/personal_world/crew.py` (`STARTER_CREW`,
`SYSTEM_RESIDENT`) and `src/personal_world/prefs.py` (`LEGACY_COMPANION_IDS`).

The chosen companion is a reference into the person's own crew
(preference `companion_id`; `null` means the one plain Assistant voice). Every
person starts with the same **starter crew**, which they can rename, hide or
add to:

| Crew id | Display name | Resident of (briefing system) |
|---|---|---|
| `renai` | Renai | *(none)* |
| `bolt` | Bolt | agents: **Workshop** |
| `hekek` | Hekek | estate: **Engine room** |
| `ratatoskr` | Ratatoskr | threads: **World tree** |
| `bruma` | Bruma | records: **Archive** |
| `mira` | Mira | interests: **Observatory** |
| `scoop` | Scoop | news: **Newsstand** (Burrito Journalism) |

Being a system's resident is who reports that system in the briefing. It is
not the same as being a room's **keeper**: keepers are chosen per room by
each person, and only the Workshop starts with one (Bolt).

**Old keys.** Before 2026-09-25 the preference held descriptor keys. They
migrate once, lazily, via `prefs.LEGACY_COMPANION_IDS`:

| Old key | Crew id |
|---|---|
| `mermaid` | `renai` |
| `robot` | `bolt` |
| `world-tree-squirrel` | `ratatoskr` |
| `taco-news-truck` | `scoop` |
| `assistant`, `personal-world` | *(none: the one plain voice)* |

Sol is not a crew entry and never speaks: she is Worlds' own mark. The retired
Station's browser-side companion ids are history only (tag
`archive/pre-design-cleanup-2026-09-25`).

---

## 3. Naming rules

**Which name is canonical per surface**

| Surface | Use |
|---|---|
| Human-facing copy, docs, chat, UI labels | Owner canon: **Renai**, **Ratatoskr**, **Bolt**, **Scoop** (from *Burrito Journalism*), **Sol**, **Hekek**, **Bruma**, **Mira**. **Settings** names the deck/icon, not a resident. |
| Server / preferences / API | crew ids `renai`, `bolt`, `hekek`, `ratatoskr`, `bruma`, `mira`, `scoop` (`crew.STARTER_CREW`); `companion_id: null` is the Assistant. Old keys migrate (§2). |
| Retired Station code | Its browser ids (`mermaid`, `ratatoskr`, `robot`, `burrito`) are history only (tag `archive/pre-design-cleanup-2026-09-25`). |
| Artwork / rig filenames | Keep the existing paths (`mermaid`, `robot`, `world-tree-squirrel`, `taco-news-truck`, `personal-world`). Never rename art to match a display name. |

**What each must never be confused with**

- **Renai is not the default.** The default is the plain **Assistant**
  (`companion_id: null`); Renai (crew id `renai`) is a personal companion a
  person can choose. Do not use "Mermaid" as her name in human-facing copy: it
  is the artwork form and the old key.
- **"Personal World" is retired as a name.** The product went "Personal World"
  → *Project Worlds* (2026-09-12) → **Worlds**, and the planet mark is now
  **Sol** (2026-09-25), who never speaks. Code identifiers (`personal_world`,
  `PW_`) keep the old name.
- **Ratatoskr is the squirrel, not the tree.** Do not address the character as
  "World-tree Squirrel" (repo descriptor) or as "Yggdrasil" (the world tree).
- **The truck is a breakfast burrito truck, not a taco truck.** "Tacos & the
  Morning Paper" is the repo's old display label for the same resident; reconcile
  toward **Burrito Journalism** and keep the game reference.
- **Bolt is the robot's personal name** (owner-stated 2026-09-17). Use **Bolt**
  in human-facing copy; "Little Helper Robot" is the role/descriptor, not a
  separate character.

**Artwork is reused, never regenerated.** Do not trace, recreate, or overwrite the
companion source rigs, the Mermaid master Lottie
(`media_files/designs/personal-world/mermaid-companion-master.lottie` — byte-identical by decision),
the icon library, or the screen SVGs. A display-name change is a copy change, not
an art change. The rules are in `AGENTS.md` ("Do not casually regenerate"),
`docs/CREW-AND-STATION-THESIS.md` §3.6, and
`.agents/skills/personal-world-implement-figma/SKILL.md` (L150–156).

---

## 4. OPEN and UNKNOWN

- **Renai — resolved in code.** The crew id is `renai` (`src/personal_world/crew.py`;
  the drawn companion's persona template `config/prompts/personas/mermaid.md`),
  and the legacy server key `mermaid` migrates to it lazily via
  `prefs.LEGACY_COMPANION_IDS`. The raw id `mermaid` is unchanged. Some older
  prose and design filenames still read "Mermaid". *(Earlier working draft name
  "Willow" is retired — do not reintroduce it; it was too close to personal
  information.)*
- **Bolt — resolved.** The robot's personal name is **Bolt** (owner-stated
  2026-09-17); "Little Helper Robot" remains the role/descriptor. No id changes
  (`robot` stays `robot`).
- **Personal World — Station id UNKNOWN/absent.** The Station "Your companion"
  control (`settings.html` L371–376) offers only `mermaid`, `ratatoskr`, `robot`,
  `burrito`; `personal-world` exists only as a server value (the default). Whether the
  Station should expose it is UNKNOWN.
- **"Tacos & the Morning Paper" retirement date UNKNOWN.** Reconcile to Burrito
  Journalism (display name **Scoop**, owner canon 2026-09-25); when the repo
  label is retired everywhere is not yet decided. The crew id is `scoop`, and
  the legacy server key `taco-news-truck` migrates to it.
- **Hekek, Bruma, Mira: settled.** They are starter crew with ids `hekek`,
  `bruma`, `mira` (`crew.STARTER_CREW`, 2026-09-25) and residents of the
  Engine room, Archive and Observatory systems. `Settings` has no id: it is an
  icon, not a resident.

---

## 5. Remaining inconsistencies (deliberately not silently fixed here)

Recorded by `rg -i 'renai|ratatoskr|world-tree|tacos & the morning paper|burrito journalism'`:

- `README.md` still uses the descriptor **"world-tree squirrel and the taco news
  truck"** in an image alt near the end. (The earlier `Ratataskor` typo in the
  intro was fixed.) Not otherwise rewritten.
- `CHANGELOG.md` (2026-09-07 entries) and `media_files/designs/personal-world/README.md` /
  `media_files/designs/personal-world/icons/README.md` still use **"Tacos & the Morning Paper"** and
  **"World-tree Squirrel"** descriptors. Not fixed.
- `docs/CREW-AND-STATION-THESIS.md` §2 and `design/COMPANION_INTEGRATION.md`
  still head their residents tables with the repo descriptors, not the canon
  names. Pointer added; tables not rewritten.
- `docs/history/STATION-GAP-ANALYSIS.md` already records the `ratatoskr`/`burrito` ↔
  `world-tree-squirrel`/`taco-news-truck` drift. Left as-is; this file is the mapping.
- `src/personal_world/prefs.py` and `api.py` keep the server keys and art
  filenames. Correct — identifiers are not renamed.

Names below remain **UNKNOWN** in the repo: **Renai** (absent from copy; the id
stays `mermaid`), and the new area crew **Hekek**, **Bruma**, **Mira** (owner
canon 2026-09-17; no repo copy or id yet). **Bolt** is now canon (owner-stated
2026-09-17).