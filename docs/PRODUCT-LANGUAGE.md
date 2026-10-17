# Worlds — Product Language & Interaction Contract

> **Superseded in part by [ADR-0008](adr/0008-front-door.md) (2026-10-01):** the stable skeleton is now `Home · Connect · Memory · Settings`; Bridge/`overview` leaves the core vocabulary; Chat is optional, not core navigation; personality is an optional Station pack, not structural (S1, S2, S3, S5). Rewrite pending.

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** first-release product language, vocabulary, and information architecture · **Read this if:** you are writing user-facing copy or deciding where a feature surfaces.

**In short:** the durable contract for what things are called and how the
product is laid out (`Bridge · Memory · Chat · Settings` skeleton, plus
chosen personal sections). It refines presentation and IA; it does not
replace `docs/ARCHITECTURE.md`, `SECURITY.md`, the accessibility contract,
or the human-reliability contract. Where direction conflicts,
[`.project/PLAN.md`](../.project/PLAN.md) wins on scope and sequencing.

**Owner-approval:** human (Rylee, 2026-09-21) via the owner round table.
**Kind:** the small, durable product-language and interaction contract the project aligns around.
**Authority:** refines the first-release *presentation, language, and information architecture*. It does
**not** replace `docs/ARCHITECTURE.md`, `SECURITY.md`, the accessibility contract, or the human-reliability
contract — those still govern. Where this contract and the finish line's older section vocabulary differ
(e.g. *Today → Overview*, *Journal/Notes → Memory*), **this contract is the current first-release language.**

This is the product layer. It does **not** reverse the Workbench/Node architecture direction
(`docs/adr/0003`–`0007`, `.project/DECISIONS.md` 2026-09-21).

---

## Product sentence

> Worlds is one place to reach everything that matters to you **without searching for it**,
> customizable enough to feel like yours, and usable whether you have a lot or a little energy.

> **The frontend is Worlds. Station is a theme.**

## Two principles

1. **Customizable enough to feel like yours, and usable whether you have a lot or a little energy.**
2. **Customization must never make Worlds harder to recover or navigate at low capacity.** Someone may
   customize deeply on a good day; on a migraine day, a stressful appointment, or an emergency, the basic
   landmarks stay predictable. You never have to remember how you customized Worlds to find something important.
3. **Warm in tone, exact in facts.** The product can be friendly, but a friendly tone must never make a
   statement less accurate. Concretely: never describe a failure as "looks fine", never show fake data or a
   button that does nothing, always say `unavailable`, `stale` or `not_configured` when that's the state,
   and never hide real uncertainty to keep the screen tidy. Being kind is fine; being kind by saying
   something untrue is not.

---

## Information architecture

### Stable skeleton — always easy to find (theme-proof, customization-proof)

`Bridge · Memory · Chat · Settings`

### Personal sections — chosen, pinned, ordered, hidden by the person

`Projects · Interests · Work · Music · Health · Remote · …`
*(Owner's own config: Projects pinned; Music folded into Interests.)*

The skeleton stays predictable regardless of theme or customization; the personal sections are the part of
the world the person shapes. This is what preserves **both** customization **and** low-capacity recoverability.

### Overview

The **front page / headlines surface** of the rest of Worlds — *not* a competing content section. It is
implemented today as the **Bridge** screen (`ui/src/screens/Bridge/`; the app's area id is still `overview`).
It answers **"what matters right now?"** by aggregating each enabled section's headline state:

- Projects → recent changes / something needing attention
- Interests → something new or relevant
- Memory → a pinned or important item
- Chat → recent context
- other enabled sections → their current headline

The person taps through to the deeper section. Overview is part of the accessibility model:
**one predictable place to orient yourself without searching.** Product-facing term is **Overview**; existing
`/api/daily` / `Today` implementation concepts remain underneath but must not create competing product language.

### Memory

A deterministic **place**, not an AI feature. It must:

- open instantly, with every model turned off
- have a predictable structure and preserve layout
- support browsing and ordinary search/filtering
- use **recognizable, assignable categories (icon + word together)** — icon for fast recognition, label so
  you never guess
- allow pinned/important information
- require **step-up for sensitive categories**

AI may summarize, suggest, retrieve conversationally, and connect related things — but **AI must never be the
only route to stored information.** Rule: **Chat is a shortcut, never the only way in.** The first plain release
stays fully usable with Qwen or any model completely unavailable.

### Records vs Vault — distinct concepts (do not conflate)

- **Records** = *user information*: medical info, work history, interview material, identity documents,
  emergency information, other durable structured personal records. **Records are structured information
  inside Memory; sensitive records can be locked (step-up). Records are NOT a separate top-level area.**
- **Vault** = *security/secrets infrastructure*: credentials, tokens, private keys, step-up-protected
  secrets, integration credentials. Vault rarely needs a direct user-facing presence.
- **Records is not the friendly name for Vault.** They stay separate in both architecture and language.

### Setup / Customize — structural, not polish

Customization without an approachable path is not friendly. Setup lets a person shape Worlds **without**
config files, technical knowledge, architecture vocabulary, or AI availability. It may cover: choosing
sections, what is pinned, arranging personal sections, accessibility preferences, information density,
initial integrations, optional suggestions.

- **Fully usable without a model.** AI may suggest/enrich later; it is never required, and the person can
  always configure their world directly.
- Setup is a **first-run experience** and an **always-reachable customization path** afterward. It need not
  remain a permanent top-level navigation destination.
- **Wording:** inside Settings it is labeled **Customize**. A button elsewhere may say **Customize Worlds**.

### Discovery — enrichment, never a replacement for navigation

Discovery is a real existing capability and stays. It **may** suggest ("you might want to add Music"),
surface possibilities, and enrich Overview. It **must not**:

- automatically rearrange navigation
- hide the deterministic path
- require AI to expose something the user already owns

### Accessibility — defaults, not setup-gated

Good defaults are **already accessible**; accessibility must never depend on successful first-run
configuration, and preferences stay easy to change later. Core requirements: predictable locations ·
adequate contrast · non-color-only affordances · keyboard navigation · visible focus · reduced-motion support ·
appropriate target sizes · stable layouts · low cognitive overhead · technical depth on demand, not forced.
No one should need to understand accessibility terminology before Worlds is usable.

### Detail level = progressive disclosure (not two products)

There is no "Simple Worlds" vs "Technical Worlds." One information architecture; the person chooses how deep
to go. Example:

```text
Bazzite
Online
Terminal · Desktop · Files · Services
[ Details ]   →  Agent version · Network backend · Address · Connection type · Containers · GPU · Logs · Advanced controls
```

"Detail level" means **information density / progressive-disclosure preference**, never separate navigation
or separate product modes.

---

## Vocabulary

### User-facing (product language)

`Bridge · Memory · Chat · Settings · Customize / Customize Worlds · Projects · Interests · Computer ·
Terminal · Desktop · Files · Build · Preview · Run · Output · Services · Records`

Decisions: **Run** (not Job) · **Output** (not Result) · **Services** stays · the attached-machine word is
**Computer** (never "Node" in the UI).

### Technical-depth (internal/engineering)

`Workspace · Node · Capability · NetworkOverlay · Volume · Artifact · Task · Worlds Edge · Headscale /
Tailscale · tailcat · Worlds Agent · Agent internals`

These stay out of normal UI — **but they are not forbidden everywhere**: advanced/technical views (the
`[ Details ]` layer) may expose precise technical vocabulary when useful. **Worlds Agent** remains the
technical name; **installation language is human** — e.g. *"Connect this computer to Worlds."*

---

## The default theme — a full pack, not a shell

**"Plain" means the structure, not the color.** Plain = low-stimulation, predictable, easy to take in, accessible.
It does **not** mean colorless, gray, or minimal. **Worlds ships a full, complete, multi-color theme
pack** — every token of the `--pw-*` system filled (surface ladder · the accent set · text · borders ·
warmth gradients · shadows · typography · density).

- **Use a complete existing pack as the starting default.** The theme engine already produces full packs; the
  current set all passes `lab design theme validate` (WCAG). **Do not hand-author a partial palette** (a
  shell forces the "all the other work" later). A bespoke pack is available via `lab design theme make` only
  if none of the existing full packs suits you; it is not a starting task.
- > **Updated 2026-09-25:** the first-run default is `starfield`, and `.project/PLAN.md` (owner-approved 2026-09-25) takes the Constellation star map as the starting direction. Where this section says otherwise, PLAN.md and `.project/DECISIONS.md` win.
- **The *default theme* is not Station.** What defers to a later theme is the **constellation star-map
  navigation model** and Station-as-default, **not the product's personality.** Character art, a light
  sci-fi feel, and visible companions stay part of Worlds (the README art stays). "Keep Station" means it
  becomes a selectable theme later on the same structure; the friendly feel stays.
- **Plain does not mean** sterile · gray enterprise · generic admin · featureless · a partial palette ·
  personality-free. **Low-stimulation *and* full of character are both required** (the rule: "soft by
  default, deep on demand"; plain does not mean colorless).
- **Personality:** a recognizable Worlds identity via typography, spacing, softness, interaction quality,
  character art, and a light sci-fi feeling. Only the **full Station skin** (map-as-navigation + its own room
  vocabulary) is a later theme package; it never defines the stable skeleton.

**Default theme (verified 2026-09-26):** **`starfield`** — deep-navy surfaces + warm amber accents
(a complete, WCAG-validated palette). Its `"Adapted from the constellation portfolio"` provenance line is
an internal lineage note only: the palette carries no lore, no companion, and no star-map navigation.
The other shipped themes are `doorways`, `station`, `moss`, `ocean`, and `plain`; all are switchable and
reversible at any time, and every theme meets the minimum text size (body ≥16px, labels ≥13px).
**`plain`** (warm-neutral charcoal + teal primary `#72B1B1` + amber `#D4A057` as the rare highlight +
Young Serif display headings) remains a full, WCAG-validated pack — plain means the structure, not the
color. No palette reintroduces the Station experience; the star-map/constellation *navigation* ban (above)
stands regardless of palette choice.

---

## Theme boundary — protects spatial memory

Themes **may change:** colors · art · typography (within accessibility constraints) · decorative treatment ·
companions · personality · motion (within accessibility constraints) · background/illustration treatment.

Themes **may NOT change:** core navigation names · navigation hierarchy · where important controls live · the
predictable location of information · required actions · accessibility semantics.

> **Someone switching themes must not have to relearn Worlds.**

> **The frontend is Worlds. Station is a theme.** (owner, human, 2026-09-21)

**Station is a later theme package, not the product.** The whole star-map / constellation *navigation* model
(map-as-frontend, seven constellations, drill-through, companion orbs) moves into the Station theme. **The
stable skeleton is the real navigation now**, and it is deterministic and direct — a person must never have
to navigate a map to reach something. This supersedes the 2026-09-16 structural assumption "Station map = the
frontend" (master handoff decision 11): a theme choice that other decisions had started to depend on without anyone deciding it.

Station is **kept, not deleted** — its palettes, art, and map views become selectable theme/experience packs
later. What is rejected is Station as the *default, the baseline palette, or the required vocabulary.*

---

## First-release scope — plain, not tiny

Preserve and **coherently present the existing product** — do not flatten it to a generic shell:

Bridge · Memory · Chat · Settings · Setup/Customize · Discovery · Projects · the existing world/journal
capabilities · existing auth/security behavior · existing real integrations/capabilities · accessibility ·
theme infrastructure · the Workbench thin slice (where it belongs in the roadmap).

Do **not** expand every backend capability into a new first-release page, and do **not** delete an existing
capability merely because it is not part of core navigation. **Preserve ≠ promote:** capabilities such as
source control, lab, proposals, reminders, exports, theme infrastructure, discovery, journal, and integrations
remain real without all becoming permanent top-level destinations; the IA decides how they surface.

**Deferred (not first release):** the Station experience wholesale — the star-map/constellation navigation,
companion orbs, and lore (all become the later Station theme) · the aubergine "station" pack as the default
palette · cross-platform nodes · remote desktop · file sync · overlay mesh (Headscale) · Worlds Edge VPS.

---

## Subtraction target

**Cut:** duplicate systems · competing roadmaps · abandoned terminology · unnecessary infrastructure ·
duplicate dashboards · redundant abstractions · stale design experiments · structural assumptions inherited
from themes · multiple routes to the same concept when one will do.

**Never cut:** meaningful existing capabilities · customization · Setup · Overview · Discovery · Memory ·
theme infrastructure · working integrations · accessibility features · product depth.

> **Goal: less searching, less explanation, less duplication; not fewer useful things.**

---

## Owner intent (preserved verbatim)

> We are not simplifying Worlds by removing its depth. We are making that depth easy to reach without
> requiring depth from the person using it. The user can customize the world deeply, but the important
> landmarks remain predictable when they have very little capacity to give.