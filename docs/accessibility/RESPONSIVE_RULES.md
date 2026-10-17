# Worlds — Responsive Rules

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** how the interface adapts to viewport width and reflow · **Read this if:** you are changing layout, navigation or a screen's narrow-width behaviour.

**In short:** how the live interface adapts from wide desktop down to a phone — one breakpoint at 860px, a single top navigation bar that scrolls rather than widens, safe-area padding, and the reflow rules it must keep. The [Accessibility contract](ACCESSIBILITY_CONTRACT.md) governs every viewport; this page records the implementation that meets it.

Current behavior is grounded in the React interface in `ui/` (the interface since the 2026-09-22 flip) — mainly `ui/src/styles/world.css` and `ui/src/app/App.tsx`, verified 2026-09-26. Design requirements are distinguished from implemented layout rules.

## Current breakpoints and navigation

There is **one** CSS breakpoint: 860px (`ui/src/styles/world.css`). Tailwind's `sm:` (640px) is used only to show or hide small chrome (brand mark, footer label).

| Effective CSS viewport | Implemented behavior |
|---|---|
| ≥860px | The nav is a sticky top bar with a horizontally scrolling row: the fixed landmark list (`World landmarks`) then the person's own sections (`Personal sections`), separated by a divider. The Bridge switches to a three-column grid (`minmax(180px,220px) minmax(0,1fr) minmax(280px,360px)`) with named areas; `bridge-lenses` becomes a vertical column; the star map uses its wider aspect ratio (`1 / 0.86`, min-height 480px). |
| <860px | The Bridge is a single column. The `Lenses` row is hidden because the star map's own figures are the navigation; the star map grows taller (`1 / 1.32`) so the keeper's words never collide with a deck. |

Navigation is a landmark group plus the person's sections; it is always before `main` in DOM order and uses `min-w-0` + `overflow-x-auto` so the row shrinks and scrolls instead of widening the page on a phone. Screen-reader landmark names are `World navigation`, `World landmarks`, and `Personal sections`. Hidden copies use `display: none`, never a second semantic tree.

## Current content and typography

Main content padding and max width are set per screen (for example the Settings screen uses `max-w-[720px]`). The header and footer carry the safe-area insets (`--pw-safe-area-inset-top/bottom/left/right`) so chrome clears notches and the home indicator.

Type scales from tokens in `ui/src/generated/tokens.css`, generated from `design/themes/*.json`. Every theme meets the minimum text size (body ≥16px, labels ≥13px). The prefs layer (`data-pw-*` attributes and `--pw-*` variables) applies text scale, contrast, density and targets on top of the tokens.

## Accessibility requirements

- Minimum 44×44 CSS px interactive targets at every breakpoint; larger target/text preferences remain usable. Focus stays visible and DOM order stays logical.
- Browser zoom/text scaling remain available. At 200% zoom, reflow must avoid page-level horizontal scrolling, clipping, and inaccessible truncation. `overflow-x: hidden` alone does not prove successful reflow.
- No orientation lock: effective viewport width selects the layout.
- Safe areas protect controls at the top and bottom of the shell.
- Motion defaults to `reduced`. Out of the box nothing animates; the OS `prefers-reduced-motion: reduce` unconditionally disables animation on any element carrying `data-pw-motion`. `prefers-contrast: more` is also honored (`ui/src/styles/world.css`).

## Target guidance, not shipped overlays

`PERSONAL-WORLD-FINISH-LINE.md` and `docs/TRUE-NORTH.md` describe target experience; `.project/PLAN.md` (2026-09-25) owns current scope and sequencing. Neither requires keeping the current breakpoint design forever.

Future drawers and sheets must follow Accessibility contract section 3: non-modal drawers (today's `World Assistant`, `ui/src/components/WorldDrawer.tsx`) move and restore focus and leave background interaction available; modal sheets trap focus, prevent background interaction, offer explicit close, close on Escape, and restore focus. Dangerous confirmations start on the safe action. Do not label these implemented before verification.

## Verification scope

Automated gates live in `ui/`: `npx vitest run`, `npx tsc -b`, `npm run lint`, the Playwright e2e suite (`npm run test:e2e`) for accessibility / accurate-state / keyboard / motion / reflow, and the kit suite (`npm run kit:test:e2e`) which checks axe, 44px targets, focus, and no sideways scroll at 390/1440. See `ui/package.json` for the exact scripts; do not trust a test count in prose.

Source/test evidence is not a manual screen-reader or device acceptance result. Browser acceptance should still cover keyboard use, 200% zoom, safe areas, 44px targets, text scaling, and composer overlap around the 860px boundary.