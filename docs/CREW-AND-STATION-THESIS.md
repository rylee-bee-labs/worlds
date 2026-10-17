# The Crew & The Station — family thesis

> **Status:** Direction · **Verified:** 2026-09-26 · **Canonical for:** the crew/family thesis and the family rules design work obeys · **Read this if:** you are touching companion art, voice, or the crew's place in the product.

**In short:** one sentence every design task obeys — the residents are siblings in art direction with distinct silhouettes and roles, and accessibility, protected attention, and inclusion are the home itself, not add-ons. The crew, voices, and companion truths here are canonical (2026-09-17, amended in role by the 2026-09-22 rulings); the *Station as the primary experience* is superseded — Station survives as a theme package behind the stable skeleton, never deleted. It does not replace the accessibility contract; where they conflict, the contract wins and the conflict is recorded back here. Scope and sequencing for current direction are owned by `.project/PLAN.md`.

The briefs imply this thesis in three places but never state it once — this file states it and flags where the sources still disagree.

---

## 1. The one-sentence thesis

> **The five residents are siblings in art direction — shared palette, outlines, and warm rounded forms — but each keeps a completely distinct silhouette and role; *nobody has to become more like the others first*. That is the product in miniature: accessibility, protected attention, and inclusion are the home itself, not features bolted onto it.**

**Verified wording** (quote these; do not paraphrase loosely):

- `design/opendesign-exploration/station/PLAY-NICE-CONFORMANCE.md` L24–25: "The crew (a mermaid, a squirrel, a robot, a journalism truck, a living world) is the literal metaphor: **nobody has to become more like the others first.**"
- `design/COMPANION_INTEGRATION.md` L35: "They are **siblings in art direction** — shared pastel palette, aubergine outlines, friendly rounded forms, rosy cheeks, sparkle decorations — but each has a **completely distinct silhouette**."

**Why the product exists, tied to the thesis:**

- **Accessibility**: the minimum requirements are layered and nothing may go below them (`docs/accessibility/ACCESSIBILITY_CONTRACT.md` §6.1); anything above the minimum may vary, but the minimum never changes.
- **Protected attention** — the world asks only when it truly needs you, and quiet is a valid rendered state (`PLAY-NICE-CONFORMANCE.md` attention-and-focus, quiet-when-healthy). Optimise for maximum warmth per unit of attention, not maximum cute (`docs/history/STATION-ALIVE-RESEARCH.md` Part 1).
- **Inclusion** — themes, companions, and sections are user-owned and swappable; the Station is "a home people add to, not a product imposed on them" (`PLAY-NICE-CONFORMANCE.md` themes-and-personalization).

**Corrected misreading:** there is no Star Trek / Deep Space Nine framing. The crew is not a bridge crew with ranks and stations — the crew is only *together*, and that togetherness is the point. Any brief reaching for franchise roles is wrong.

---

## 2. The five residents and their roles

Source: `design/COMPANION_INTEGRATION.md` L27–33.

| Companion | Role | Strong contexts | Source rig |
|---|---|---|---|
| **Mermaid** | Personal companion (the operator Theme) | operator theme, personal presence, conversation, reassurance | `media_files/portfolio/companions/renai.svg` |
| **Little Helper Robot** | Lab / development / AI helper | Development, automation, Workshop, configuration, tooling | `media_files/portfolio/companions/bolt.svg` |
| **World-tree Squirrel** | Worlds / lore / memory keeper | VEFR, worlds, lore, memory, journal/history, worldbuilding | `media_files/portfolio/companions/ratatoskr.svg` |
| **Tacos & the Morning Paper** | Journalism / stories / city life | Burrito Journalism, reporting, news, city stories | `media_files/portfolio/companions/burrito.svg` |
| **Personal World** | Default system companion | System default, generic theme, product identity | `media_files/portfolio/companions/personal-world.svg` |

**Names:** display canon — **Renai**, **Ratatoskr**, **Bolt**, **Scoop** (the burrito truck), **Sol**, **Assistant** — and the station-id ↔ server-key ↔ crew-id mapping live in [COMPANION-CANON.md](COMPANION-CANON.md). The table above keeps the design-file descriptors on purpose; the canon names are what people read.

**Owner canon 2026-09-17 adds three area residents** — Hekek (Systems), Bruma (Records), Mira (Interests) — and makes residents **assignable to decks**: the crew above is the *starter crew*, not the only possible one. See [STATION-MAP.md](history/STATION-MAP.md) §3 and [CHARACTER-HANDBOOK.md](CHARACTER-HANDBOOK.md). The five rigs in this table remain the original companion set.

Sibling rules (same file, L35, L219–221): shared art direction, distinct silhouette; one companion per domain; a companion may *visit* another area only as a temporary reaction, never a permanent move.

**Identity model — Personal Companion vs Contextual Character** (`COMPANION_INTEGRATION.md` L61–68). Separate concepts that coexist:

- **Personal Companion** — chosen by theme or user preference, persistent across the product. Presence.
- **Contextual Character** — tied to the current world/project context. Context.

They do not both flood the screen: personal = presence, contextual = identity. Example: the mermaid (canon name **Renai**) is the personal companion; the world-tree squirrel (canon name **Ratatoskr**) appears as the VEFR contextual identity (`chat-contextual-vefr`).

---

## 3. Family rules (non-negotiable)

1. **Companions never carry critical information.** Semantic state always lives in UI text (`ACCESSIBILITY_CONTRACT.md` §1.4; `COMPANION_INTEGRATION.md` L153).
2. **Motion is never the only signal.** Every state also has a label and, where warranted, a live-region message; urgency is luminance + text, not movement (`STATION-ALIVE-RESEARCH.md` Part 5; `ACCESSIBILITY_CONTRACT.md` §1.4).
3. **Reduced motion replaces, never deletes.** `prefers-reduced-motion` → static poses / instant pose change / cross-fade; OS preference unconditionally overrides app motion (`ACCESSIBILITY_CONTRACT.md` §6.2; `COMPANION_INTEGRATION.md` L154).
4. **Companion-off removes no functionality.** The assistant and every action remain reachable through their own labeled controls (`ACCESSIBILITY_CONTRACT.md` §7.4; `PLAY-NICE-CONFORMANCE.md` L42–43).
5. **Companion art is decorative and `aria-hidden`.** The actionable control keeps its own useful label, e.g. "Open World assistant" (`ACCESSIBILITY_CONTRACT.md` §7.2–7.3).
6. **Artwork is reused, never regenerated.** Do not trace, recreate, or overwrite companion rigs, the Mermaid master Lottie (byte-identical by decision), the icon library, or screen SVGs (`AGENTS.md`; `.agents/skills/personal-world-implement-figma/SKILL.md` L153).

---

## 4. Design authority chain

Read top-down; each layer is authoritative only for what it owns.

1. **Figma — visual composition only.** Per `.project/participants/figma/participant.yaml`: authoritative for `visual-composition` (approved frames), hierarchy, spacing, frame relationships; **not** for `token-canonicality`, `canonical-token-values`, runtime/API/deployment truth, or accessibility requirements that conflict with literal visual choices.
   - Current Workshop v3 file: **`Wbg1rdt9fVCjWAXEKI1pTc`** (`.project/design/CURRENT.md` L43; `.project/CURRENT.md` L233–235). V0.1-era frames live in the older product file `VATVojyJZT9HKx0CrDS0yr` (the file named in `participant.yaml`).
   - Current vs superseded is answered by `.project/design/CURRENT.md` and `.project/design/WORKSHOP-V3-MANIFEST.yaml`.
2. **Repo tokens own the VALUES.** `design/tokens.json` is canonical; design tools derive from it and are never the source (`design/tokens.json` `_comment`; `participant.yaml` `not_authoritative_for`). The generated CSS (`ui/src/generated/tokens.css`) is derived, never hand-edited.
3. **Local vendored reference.** When the Figma bridge is unavailable, the working local reference is the vendored exports in `design/owner/` (SVG + PNG), plus the archived inventory `design/handoff/FRAME_INDEX.md` (historical — its statuses are provenance, not current approval).

**Bridge status:** the Figma desktop Dev Mode MCP server is reached via the SSH reverse tunnel documented in `.project/CURRENT.md` ("Figma bridge"). It has gone down mid-run before (`CHANGELOG.md`, 2026-09-13), and **its current online status is UNKNOWN** — verify before assuming. `get_design_context` also requires the target frame to be selected/open in Figma Dev Mode. **When the bridge is OFFLINE, `design/owner/` is the working local reference**, and work proceeds read-only mapping first, never from memory (skill L107–111).

**UNKNOWN / disagreements:**

- `design/owner/` is **gitignored** (`.gitignore` L95–96) — a local working drop, explicitly "not project truth". It is a practical local reference, not a durable canonical source; anything promoted from it must land in a tracked, curated path (e.g. `design/screens/`).
- Resident count/names disagree: `COMPANION_INTEGRATION.md` lists **five**; `docs/history/PRODUCT-VISION-HANDOFF.md` L52 lists **four** (Mermaid, Ratatoskr, Robot, Burrito) with variant names; `STATION-ALIVE-RESEARCH.md` uses "World Keeper", which is **superseded historical** (`.project/design/CURRENT.md` COMPANION STATUS). Treat `COMPANION_INTEGRATION.md` as authority; flag the rest.
- `STATION-ALIVE-RESEARCH.md`'s design thesis is a *candidate* research artifact, not a commitment. This file's thesis is the binding one.

---

## 5. How to apply this (designer · engineer · agent)

- **Start from the thesis, then the frame.** Name which resident(s) and which identity (personal vs contextual) a change touches; if it cannot say, it is not ready to design.
- **Never edit authority downward.** Composition from Figma, values from `design/tokens.json`, art from the canonical rigs — resolve gaps in canonical tokens or ask the owner, never by sampling a screenshot hex or tracing art.
- **Design for companion-off and reduced motion first**, then add the delightful layer on top. If the screen only works with motion or the mascot, it fails.
- **Reuse the five; do not invent a sixth — *amended by owner, 2026-09-17*.** A new identity is still a **pack/theme concern with provenance and install/uninstall**, never a one-off character hard-coded into a screen (`PLAY-NICE-CONFORMANCE.md`; `PRODUCT-VISION-HANDOFF.md` decision #21). The owner concept of 2026-09-17 makes that path first-class: **the shipped crew is the default crew, and which resident takes which deck is a setting** — anyone may create their own residents and assign them to any deck ([STATION-MAP.md](history/STATION-MAP.md) §3). Creating new residents is now owner-sanctioned *through the pack mechanism*; inventing throwaway characters inside screens is still wrong.
- **Record, don't silently resolve.** When a design frame and the accessibility minimum disagree, the minimum wins and the conflict is written back as an owner-facing reservation (`.project/design/WORKSHOP-V3-MANIFEST.yaml` is the pattern).

*Stated in-repo 2026-09-17. Sources cited above are authoritative within their own scope; this file is the single statement design work obeys.*