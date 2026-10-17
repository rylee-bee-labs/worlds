# Companion System & Chat — Project Worlds UI Architecture

(Formerly "Personal World" — product renamed 2026-09-12; the companion
character named "Personal World" keeps its name. Technical identifiers unchanged.)

**Date:** 2026-09-07
**Status:** Companion design reference with current implementation and target distinctions
**Source:** Figma file `VATVojyJZT9HKx0CrDS0yr`
**Character/voice truth:** who each resident is (and the two voices) is canonical in [`docs/CHARACTER-HANDBOOK.md`](../docs/CHARACTER-HANDBOOK.md); this file owns design and art.

## Overview

Project Worlds has five companion residents — real characters, not placeholders.
The domain/theme mappings below describe design intent. Current runtime supports
companion selection and a standalone Chat page; it does not implement all the
contextual identities, tool workflows, or response treatments in the exported screens.

The [Finish Line](../docs/PERSONAL-WORLD-FINISH-LINE.md) governs the target:
chat is a contextual layer across sections, with global cross-system chat still
available when authorized. A permanent standalone top-level Chat destination is
not required. Preserve the useful current Chat implementation while extending
context and navigation toward that target.

This document supersedes the earlier Mermaid-centric integration pass.

## Current Residents

| Companion | Role | Strong Contexts | Source Rig |
|---|---|---|---|
| **Mermaid** | Personal companion (the operator Theme) | the operator theme, personal presence, conversation, reassurance | `media_files/portfolio/companions/renai.svg` |
| **Little Helper Robot** | Lab / development / AI helper | Development, automation, Workshop, configuration, tooling | `media_files/portfolio/companions/bolt.svg` |
| **World-tree Squirrel** | Worlds / lore / memory keeper | VEFR, worlds, lore, memory, journal/history, worldbuilding | `media_files/portfolio/companions/ratatoskr.svg` |
| **Tacos & the Morning Paper** | Journalism / stories / city life | Burrito Journalism, reporting, news, city stories | `media_files/portfolio/companions/burrito.svg` |
| **Personal World** | Default system companion | System default, generic theme, product identity | `media_files/portfolio/companions/personal-world.svg` |

They are siblings in art direction — shared pastel palette, aubergine outlines, friendly rounded forms, rosy cheeks, sparkle decorations — but each has a completely distinct silhouette.

**Naming canon:** display names and the station-id ↔ server-key mapping are canonical in [docs/COMPANION-CANON.md](../docs/COMPANION-CANON.md); the row labels above are repo descriptors, not the display names.

## Art direction (reference: the crew sheet)

**Canonical art-direction reference:** `design/screens/crew.png` — the owner's crew
character sheet (curated 2026-09-17; source drop `design/owner/crew/`). It is the
**new** direction and the target for companion artwork. The runtime companion SVGs and
source rigs (`design/assets/companions/`, `src/personal_world/static/companions/`) are
the **earlier** direction; bring them toward the crew sheet rather than regenerating
them casually (see `AGENTS.md` "Do not casually regenerate").

What the crew sheet establishes:

- **Matching uniform + combadge.** Every resident wears the same dark uniform with gold
  trim and a combadge. The uniform is what makes them a *crew*; a character is not
  redrawn without it.
- **Family resemblance, distinct silhouette.** Shared pastel-to-saturated palette, crisp
  dark outlines, large expressive eyes with highlights, rosy cheeks, sparkle accents —
  but each character's shape is unmistakably its own.
- **Warm, painterly, cosy lighting** (lanterns, stalls, night) against the deep
  navy/space canvas. Gold is the accent, never the field.
- **Cute but competent** — adventurer/astronaut energy, not infantilised.
- **Use the tracked set.** The curated companion assets live in
  `design/assets/crew/` — **true-vector SVGs** in `vector/` (five residents + planet
  emblem), transparent **cutouts** in `cutouts/`, the **app-icon set** in `icons/`,
  the three **attention-voice marks** in `marks/`, plus room art, skies and poses.
  Prefer the vector SVGs in the UI (crisp at any size, tiny).

Accessibility still wins: companion art is decorative + `aria-hidden`, motion is never
the only signal, and reduced motion shows static poses.

## Companion Architecture

```
Companion System
├── Resident (which character)
│   ├── Mermaid
│   ├── Little Helper Robot
│   ├── World-tree Squirrel
│   ├── Tacos & the Morning Paper
│   └── Personal World
│
├── Size (how large)
│   ├── Micro        16-20px  (nav/header identity, silhouette only)
│   ├── Nav/Sidebar   32px    (persistent sidebar presence)
│   ├── Inline        32-48px (loading, inline context)
│   ├── Empty State   48-64px (empty/comfort presence)
│   ├── Error/Comfort  64px   (error state companion)
│   └── Feature       96px+   (showcase, family portrait — use sparingly)
│
└── Identity Layer
    ├── Personal Companion  (theme-linked or manually selected)
    └── Contextual Character (project/world-linked identity)
```

### Personal vs Contextual Identity

These are separate concepts that can coexist:

- **Personal Companion** — selected by theme or user preference. Persistent across the product.
- **Contextual Character** — associated with the current world/project context.

Example: the operator selects Mermaid as her personal companion. When browsing VEFR, World-tree Squirrel appears as the contextual project identity. They don't both flood the screen — personal companion provides presence, contextual character provides context identity.

## Primary Navigation

Current dashboard navigation in `src/personal_world/api.py` is:

`Today → Chat → World → Journal → Vault → Settings`.

The icon rail names World as "Worlds". Companion artwork is decorative, not
another destination. The following is the historical September 7 design hierarchy,
not a mandatory finish-line navigation structure:

```
[p] Appliance Logo
[📅] Today
[💬] Chat          ← NEW: first-class surface
[🌐] World
[📓] Journal
[🧜] Companion     ← context-appropriate companion
[⚙️] Settings
```

## Screen Companion Mapping

| Screen | Companion | Rationale |
|---|---|---|
| `today-hybrid-desktop-1440` | Mermaid (32px) | the operator theme context |
| `today-hybrid-narrow-900` | Mermaid (32px) | the operator theme context |
| `today-state-empty` | Mermaid (48px) | Comfort presence, the operator theme |
| `today-state-loading` | **Robot** (32px) | Non-Mermaid demo — system/tools context |
| `today-state-attention` | Mermaid (32px) | the operator theme context |
| `today-state-partial` | **Personal World** (32px) | Non-Mermaid demo — system default |
| `today-generic-theme` | **Personal World** (32px) | Generic/non-the operator theme |
| `today-rylee-theme` | Mermaid (32px) | the operator's home theme |
| `world-capability-first` | **Personal World** (32px) | System/product context |
| `journal-screen` | **World-tree Squirrel** (32px) | Lore/memory/history context |
| `settings-refined` | **Personal World** (32px) | System settings context |

## Chat Surface

Current Chat answers from a read-only world snapshot through the optional reasoning
provider. It displays text and source disclosure; it does not execute tools or
mutate the world. The broader conversational doorway into projects, sections,
and connected tools is target design. Per-section context and model routing,
authorized actions, and global cross-system reach remain governed by the Finish Line.

### Chat Screens Produced

These are design artifacts, not evidence that each depicted workflow is implemented.

| Screen | Description |
|---|---|
| `chat-active-conversation` | Multi-turn desktop conversation with deployment logs, links, structured data |
| `chat-empty-new` | Empty state with Mermaid companion, suggestion chips ("Check on my world", "What happened today?") |
| `chat-thinking-working` | Thinking indicator with text status + capability disclosure ("Checking your connected sources...") |
| `chat-error-partial` | Calm error card with cached data fallback, Retry + Continue actions |
| `chat-contextual-vefr` | VEFR context with Squirrel contextual identity + Mermaid personal companion |
| `chat-tool-capability` | Discovery Feed scan with step-by-step progress indicators |
| `chat-source-provenance` | Inline citation pills + collapsible Sources panel with match percentages |
| `chat-long-dense` | Rich response with heading, prose, YAML code block, bulleted list, summary |
| `chat-narrow-responsive` | 900px responsive layout with collapsed sidebar, full-width composer |

### Chat Design Principles

1. Current Chat has a dedicated reading surface. Target contextual chat may use
   inline, drawer, or other accessible presentations appropriate to each section;
   global chat remains reachable. No permanent top-level destination is mandated.
2. Chat has sufficient reading width (~640-720px message column)
3. Composer is obvious, accessible, full-width
4. Target world/project context should be visible; current conversation details
   expose provider information rather than a complete project workspace
5. Working state uses text status independent of companion animation
6. Provenance/source is available without overwhelming content
7. Error recovery is explicit with clear actions
8. Companion presence is restrained — not a giant talking avatar

## Companion Component Page

The `companion-family-portrait` frame shows all 5 residents together at 96px with:
- Active/Standby state indicators
- Role labels and theme associations
- Personal Companion vs Contextual Character architecture explanation

## Accessibility & Motion

- Companions NEVER carry critical information — semantic state is always in UI text
- `prefers-reduced-motion`: static poses only, no animation
- No flashing, strobing, shaking, rapid pulsing, or repeated large bounce
- Idle motion at 48px: ≤ 2px visible excursion
- Maximum 300ms transitions
- Chat thinking/working state has proper accessible text status independent of mascot animation

## Scale System Reference

| Size | Use | Priority |
|---|---|---|
| Micro (16-20px) | Nav/header identity | Silhouette readability |
| Nav (32px) | Sidebar persistent presence | Character recognition |
| Inline (48px) | Loading, inline context | Detail visibility |
| Empty State (64px) | Empty state comfort | Expression + character |
| Error (64px) | Error state companion | Comfort + recognition |
| Feature (96px+) | Showcase, family portrait | Full detail — use sparingly |

## Asset Files

| Path | Description |
|---|---|
| `design/assets/companions/` | All 5 companion source packages |
| `media_files/designs/personal-world/companions/README.md` | Collection overview + download links |
| `media_files/designs/personal-world/companions/IMPORT_GUIDE.md` | Figma + LottieFiles import instructions |
| `media_files/designs/personal-world/companions/COMPATIBILITY_AUDIT.json` | SVG structure verification |
| `media_files/designs/personal-world/mermaid-source-rig-v2.svg` | Polished Mermaid v2 (earlier art direction pass) |
| `design/screens/chat/` | All 9 Chat screen SVG exports |
| `design/screens/` | Updated screen SVG exports with companion system |

## Exported Screens

### Chat (`design/screens/chat/`)
- `chat-active-conversation.svg`
- `chat-empty-new.svg`
- `chat-thinking-working.svg`
- `chat-error-partial.svg`
- `chat-contextual-vefr.svg`
- `chat-tool-capability.svg`
- `chat-source-provenance.svg`
- `chat-long-dense.svg`
- `chat-narrow-responsive.svg`

### Companion System
- `companion-family-portrait.svg`

### Updated Screens (`design/screens/`)
- `today-hybrid-desktop-1440.svg`
- `today-state-empty.svg`
- `today-state-loading.svg`
- `today-state-attention.svg`
- `today-state-partial.svg`
- `world-capability-first.svg`
- `journal-screen.svg`
- `settings-refined.svg`
- `today-hybrid-narrow-900.svg`
- `today-generic-theme.svg`
- `today-rylee-theme.svg`

## What Changed From Previous Pass

1. **Deleted** all old blob/ellipse/placeholder Mermaid artwork from screens
2. **Imported** all 5 approved companion SVG rigs as editable Figma vectors
3. **Placed** correct companion per screen context (not Mermaid everywhere)
4. **Added Chat** to primary navigation across all 11 screens
5. **Created 9 Chat screens** as a first-class product surface
6. **Created companion family portrait** showing all 5 residents with architecture docs
7. **Generic theme proves** the system isn't Mermaid-specific (uses Personal World planet)
8. **Loading state uses Robot** to demonstrate non-Mermaid companions in action
9. **Journal uses Squirrel** for lore/memory context
10. **VEFR Chat uses dual identity** — Mermaid personal + Squirrel contextual
