---
title: How the interface was made
kind: book
order: 17
for: everyone
short: The screens were drawn first, built from shared pieces, checked by people and robots, and handed back and forth in one shared note.
---

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

Worlds' screens were made by a design lane working alongside a backend
lane. The design lane draws and builds what you see and touch. The backend
lane builds what's underneath and ships everything. The owner decides.

Nothing reaches your screen straight from an idea. It goes through the
same five steps every time: **boards, pieces, checks, pictures,
handoff.**

* * *

**Boards first.** A board is a drawing of a screen, with its real words
in place: every state it can be in, like loading, empty, working and
"can't reach it". The owner looks at the boards and says yes or asks for
changes before anything is built. It's much cheaper to move a box on a
board than in code.

**Words before looks.** Every label is plain: a button says what it does,
and a problem says what happened and what to do next. Characters may speak
in their own voices, but the screen itself never does.

* * *

**Tokens, then themes.** Every colour, size and gap is a named token, like
"the panel surface" or "a small gap", instead of a raw number. A theme
fills in the tokens: Starfield, Daylight, Moss and the rest. Because
screens only ever use tokens, a new screen works in every theme on day
one. Some tokens belong to the core and no theme can change them: the
focus ring, the 44-pixel targets and the text sizes.

**The rules nobody bends.** Every screen works with a keyboard and a
screen reader, at phone width (390 pixels) and desktop width (1440), with
motion off, and with big text. Status is always said in words, never only
in colour. Buttons and links are at least 44 pixels tall.

* * *

**Checks, by people and robots.** Each change comes with tests. Some
check the words and the logic. Browser tests open the real app, press the
buttons, and run an accessibility checker on the page, contrast included.
Another check makes sure no private address, name or secret ever lands in
the code.

**Pictures.** A gallery of screenshots is taken of every screen, at phone
and desktop size, from a throwaway World with made-up people in it. Anyone
can see what changed without running anything.

* * *

**Handoffs.** The two lanes talk through one shared note, the handoff. It
holds only what is true now and what is still open: an ask gets written
down, and when it's done it is ticked and replaced, not piled on. The
design lane opens a pull request for each change and lists it there; the
backend lane checks it, merges it and ships it. The design lane never
ships its own work.

**Art.** Characters and pictures are painted by the owner from written
requests (one prompt per picture), then checked, sized and placed. Whimsy
is part of the job: where a small picture can make a page kinder, it
belongs there.

* * *

## In Claude's words

I'm the design lane. Most days start with the handoff: I read what
changed, pick up what's mine, and write back in a line or two. I like the
boards best, because that's where a screen is still cheap to change and
the owner can say "yes!" or "not quite" before anyone has built anything.

The rules help more than they limit. When every screen has to work at
390 pixels, with a screen reader and with motion off, a lot of clever
ideas fall away, and what's left is usually clearer. And when a page has
room for a sleepy crew member or a bee's face, I try to put one there.

* * *

## Words to know

- **Board:** a drawing of a screen, with its real words and every state. Often called a *mockup* or *wireframe*.
- **Design token:** a named value (a colour, size or gap) that screens use instead of raw numbers.
- **Theme:** a set of values for the tokens, which changes the look without changing the rules.
- **Component:** a reusable piece of screen, like a button or a card.
- **Accessibility (a11y):** making something work for everyone, including people using screen readers, keyboards or big text.
- **Pull request (PR):** a proposed change, reviewed and checked before it's merged.
- **Handoff:** the shared note where the design and backend lanes ask and answer.
- **End-to-end (e2e) test:** a test that drives the real app in a browser, like a person would.

* * *

## Under the hood

Boards live on the design canvas; tokens in `design/tokens.json`, themes in `design/themes/`, and the theme contract in `ui/THEMES.md`. Screens are React + TypeScript in `ui/src/screens/`, pieces in `ui/src/components/`, styled only through `var(--pw-...)` tokens. Unit tests: `vitest` (`ui/src/test/`). Browser tests: Playwright with axe, colour contrast on (`ui/e2e/`). The public-safety gate: `tests/test_public_safety.py`. Gallery: `docs/gallery/capture.mjs` and `capture-server.mjs`. Art requests: `docs/ART-REQUESTS.md`. Rules: `docs/accessibility/ACCESSIBILITY_CONTRACT.md` and `docs/PRODUCT-LANGUAGE.md`.

* * *

## Colophon

Made by the design lane and the owner, one handoff at a time. The covers
were painted by the owner; the words were kept plain on purpose, so anyone
can read them. If you've read all the way to here: thank you.
