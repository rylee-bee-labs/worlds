---
title: How the screens are layered
kind: book
order: 4
for: everyone
short: Every color and size comes from a named token, and themes and your settings change the values, never the rules.
---

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

Every color, size and space on a Worlds screen comes from a **token**: a
named value like "the text color" or "the small gap", never a raw number
typed into a screen.

The names live in one file, `design/tokens.json`. The values come from the
layers below.

* * *

There are three layers, from bottom to top:

1. **The invariant core.** Surfaces, text colors, type, spacing, the focus
   ring, 44-pixel touch targets and the accessibility contract. No theme
   and no setting may break these.
2. **The theme.** Starfield (the default), Daylight, Moss, Ocean, Plain,
   Doorways, Station. A theme changes the look within the core's rules.
3. **Your own settings.** Motion, contrast, text size, density, target
   size. These sit on top of any theme.

* * *

How it's built: a small script turns the token names and each theme's values
into CSS variables (`--pw-...`), one block per theme. Your settings become
attributes on the page (`data-pw-motion`, `data-pw-contrast`...). Screens
only ever use the variables.

That's why a new theme needs no screen changes, and why "reduce motion"
works everywhere at once.

* * *

Why it matters: a screen that types its own color breaks the day someone
picks Daylight or high contrast. A screen that uses tokens gets every theme,
and every accessibility setting, for free.

* * *

## Words to know

- **Token:** a named design value, like "the text color". Official term: *design token*.
- **Theme:** a set of values for the tokens: Starfield, Daylight, Moss and others.
- **CSS variable:** how a token reaches the browser, e.g. `--pw-text-primary`. Official term: *custom property*.
- **Invariant:** something no theme or setting may change, like 44-pixel touch targets.
- **Accessibility contract:** Worlds' written promise about screen readers, focus, motion and contrast.

* * *

## Under the hood

`design/tokens.json` holds token names and immutable values. `design/themes/*.json` holds each theme's values. `ui/scripts/generate-tokens.mjs` writes `ui/src/generated/tokens.css` (Station on `:root` as the fallback, then one `[data-theme]` block per theme) and `tokens.ts`. The product default is `DEFAULT_THEME` (starfield) in `ui/src/app/prefs-dom.ts`. Preferences become `data-pw-*` attributes on `<html>`. Canonical: `design/THEME_PACK_FRAMEWORK.md`, `docs/accessibility/ACCESSIBILITY_CONTRACT.md`.
