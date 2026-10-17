# Plain Default Theme — shipped default (evolve the generic, don't start a lineage)

> **Superseded in part by [ADR-0008](../docs/adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../FRONTEND-INVENTORY.md).

> **Superseded 2026-09-25:** the first-run default is now `starfield` (`.project/DECISIONS.md`, "Default theme plain → starfield"). Plain stays as an optional pack; this doc is its history.

**Status:** APPROVED + IMPLEMENTED 2026-09-22 (owner queue item 2 / D2). `design/themes/plain.json` is a
validated pack and the first-release default (`DEFAULT_THEME` in `ui/src/app/prefs-dom.ts`; first-run boot
sets `data-theme="plain"`); `starfield` is demoted to a switchable optional pack. This supersedes the
2026-09-21 starfield-default line (see `docs/PRODUCT-LANGUAGE.md`) and DECISIONS C8's "plain.json deleted"
note. The registry is `design/themes/*.json` consumed by `ui/scripts/generate-tokens.mjs` (there is no
separate `themes.json` file — the `ThemeName` union in `src/generated/tokens.ts` is the registry row).
Canonical design truth stays `design/tokens.json`; this pack layers over it — no canonical token changed.
**Owner answers to the four open questions (2026-09-22):** (1) teal `#72B1B1` primary, amber `#D4A057`
kept as the rare highlight — the draft's Q1 flip; (2) warm-neutral charcoal surfaces as proposed;
(3) keep Young Serif headings (wired via `[data-theme="plain"] h1–h6` in `world.css`, woff2 self-hosted);
(4) dark-warm only for the first release — no light variant yet.
**Owner direction (2026-09-21):** dark-warm by default · plain may carry a recognizable Worlds identity ·
lore/companions/strongly-themed illustration belong to optional packs · evolve the existing generic-theme
work, **no seventh/eighth lineage** · must pass the contrast validator.

---

## What this evolves from (grounded, not invented)

- `design/screens/today-generic-theme.svg` — the **neutral** direction (cool gray `#5C5C64`/`#8A8A94`,
  off-white `#E8E8EC`, darks `#121214`/`#1E1E22`, blue accent `#6B9EFF`, a gold `#D4A547`).
- `media_files/designs/theme-studio/index.html` `--pw-*` tokens — already **dark-warm** (warm off-white text
  `#EDE7DB`, amber `#D4A057`/gold `#C9A227`, calm teal `#5A9E9E`/`#72b1b1`, soft warm shadows, soft radii,
  serif option). This is the warmth seed.
- `design/tokens.json` (aubergine baseline) — the **teal + warm-metal** signature (`#72b1b1` teal,
  `#e4c58d` gold) and the accessibility canon (luminance-only status, 44px, reduced-motion, focus ring).

**The move:** take the generic's *neutrality* and warm it with the theme-studio's *amber + warm off-white +
soft serif* — a calm, neutral-enough dark-warm default that still reads as Worlds. Not a new lineage; the
generic direction, warmed.

---

## Proposed tokens (react to these)

### Surfaces — warm-neutral charcoal (faint umber, not blue/purple)
| Token | Value | Note |
|---|---|---|
| `surface.void` | `#0D0C0B` | deepest |
| `surface.canvas` | `#141211` | page background |
| `surface.panel` | `#1C1917` | cards |
| `surface.elevated` | `#23201D` | popovers |
| `surface.raised` | `#2C2724` | hover/active |

### Text — warm off-white
| Token | Value |
|---|---|
| `text.primary` | `#ECE7DF` |
| `text.secondary` | `#C2BBB1` |
| `text.muted` | `#98918A` |

### Accent — teal identity + amber highlight (owner flipped Q1 on 2026-09-22)
| Token | Shipped value | Role |
|---|---|---|
| `accent.primary` | `#72B1B1` | calm teal — identity, emphasis, active, focus, links |
| `accent.on_primary` | `#0C2A2A` | text on teal |
| `accent.secondary` / `accent.warm` | `#D4A057` | warm amber — the RARE highlight: primary CTAs, warm glows |
| ~~draft proposal: amber primary / teal secondary~~ | ~~`#D4A057` / `#72B1B1`~~ | flipped by owner decision 2026-09-22 (Q1) |

### Borders / focus
- `border.subtle` `rgba(236,231,223,0.10)` · `border.strong` `rgba(236,231,223,0.18)`
- `focus.ring` `2px solid #72B1B1` · `focus.ring_high_contrast` `2px solid #FFFFFF` (accessibility canon — unchanged)

### Status — luminance-only (owner accessibility rule, unchanged)
Rank encoded by **luminance + the status word/icon**, never hue alone. Colors are a muted, luminance-ordered
ramp; the word carries the signal (`healthy → warning → unknown → needs_attention → unavailable → stale →
disabled → not_configured`).

### Typography — the warm identity
- **Interface:** `"Instrument Sans", system-ui, sans-serif`
- **Expressive (headings):** `"Young Serif", Georgia, serif` ← the soft serif carries warmth/identity without lore
- **Mono:** `ui-monospace, "SF Mono", "Cascadia Code", monospace`
- base `1rem`, line-height `1.6`

### Spacing / radius / shadow / motion — calm and soft
- spacing `compact .25 · normal .5 · loose 1 · section 1.5rem` (generous, low density)
- radius `control 10px · card 14px · pill full`
- `shadow.soft` `0 10px 30px rgba(0,0,0,0.28)`; optional faint warm glow `0 0 28px rgba(212,160,87,0.06)`
- **motion: reduced by default** (respect `prefers-reduced-motion`)
- **targets:** 44px min / 56px large
- **default appearance: dark-warm**

---

## Gates it must pass — RUN 2026-09-22, all green

- `lab design theme validate design/themes/plain.json` → **PASS, fails: 0** — body AA min **7.76:1**
  (12/12), muted floor 5.21:1, accent-as-large 6.07:1, label-on-accent 6.26:1, **zero warnings**.
  (Reference: the `moss` pack validates at min_body 5.84 / fails 0.)
- `ui/scripts/contrast-audit.mjs` → 70 pairs · 0 failing (plain included automatically).
- `npx vitest run` → 168 passed · `npm run lint` → 0 · `tsc -b` → clean.
- `npm run test:e2e` (Playwright, axe with color-contrast ENABLED) → 67 passed.
- Backend `pytest --timeout=30` → 1356 passed, 7 skipped · `framework validate` → violations 0.
- Luminance-only status · visible focus · reduced-motion · 44px targets · stable layout (per
  `docs/accessibility/ACCESSIBILITY_CONTRACT.md`) — unchanged; the pack only fills color/typography slots.

## Recognizable Worlds identity (allowed) vs lore (NOT in the plain default)

- **In (identity):** the teal + amber pairing · warm off-white text · warm-neutral surfaces · the soft serif
  heading voice · softness/restraint · calm density · gentle, state-explaining motion.
- **Out (→ optional packs):** lore · companions · strongly-themed illustration · Station theming · decorative
  worlds/rooms. The plain default is calm and broadly usable; personality is a pack you add later.

---

## Open questions for the owner — ANSWERED 2026-09-22 (see Status above)

1. **Amber `#D4A057` as the identity accent** — right warmth, or too gold? (Cooler alternative: lean on teal
   `#72B1B1` as primary and keep amber as a rare highlight.) → **CHOSEN: the cooler alternative.**
2. **Surfaces** — warm-neutral charcoal (faint umber, proposed) vs keep them truly neutral gray? How warm
   should the darks feel? → **CHOSEN: warm-neutral charcoal, as proposed.**
3. **Serif headings (`Young Serif`)** in the plain default — keep for identity, or stay all-sans until packs?
   → **CHOSEN: keep Young Serif headings.**
4. **Light-warm option** — build a light variant now, or dark-warm only for the first release?
   → **CHOSEN: dark-warm only for v1.**