---
title: Making the UI
kind: book
order: 16
for: everyone
short: Screens are built from shared pieces and tokens, checked by people and robots, and every screen has to work for everyone.
---

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

A Worlds screen is built from **pieces** (buttons, cards, drawers) that
already exist and already follow the rules. A new screen mostly arranges
pieces; it rarely invents one.

Every color, size and gap comes from a token (see *How the screens are
layered*), so a screen works in every theme on day one.

* * *

**Words come first.** Before anything is drawn, the words are written:
plain, exact, kind. A button says what it does ("Send", "Merge"), and a
problem says what happened and what to do next.

**Everyone, always.** Every screen works with a screen reader and a
keyboard, at 390 pixels wide (a phone) and 1440 (a desktop), with motion
turned off, and with big text.

* * *

**How a screen gets made:**

1. Design draws it (the boards), with real words.
2. It's built from existing pieces and tokens.
3. Tests check what it says and does. Browser tests check it on a real page.
4. Screenshots of every screen are taken at phone and desktop size, so
   anyone can see what changed.
5. It ships through a pull request like everything else.

* * *

## Words to know

- **Component:** a reusable piece of screen, like a button. Official term used in React.
- **Design system:** the pieces plus the rules for using them.
- **Storybook:** a place to see each piece on its own, in every state.
- **Breakpoint:** a screen width where the layout changes.
- **Screen reader:** software that reads the screen aloud (VoiceOver, for example).

* * *

## Under the hood

React + TypeScript + Vite in `ui/`, Tailwind with token CSS variables (`var(--pw-...)`), never raw values. Run `npm run dev` (it generates tokens first). Unit tests: `vitest`. Browser tests: Playwright (`ui/e2e/`). Pieces: `ui/src/components/`, and Storybook (`npm run storybook`). Screenshots: `docs/gallery/` (`capture.mjs`, 390 and 1440). Rules: `docs/accessibility/ACCESSIBILITY_CONTRACT.md` and `docs/PRODUCT-LANGUAGE.md`. The design authority is `.project/design/CURRENT.md`; the handoff flow is in `docs/history/DESIGN-HANDOFF.md`.
