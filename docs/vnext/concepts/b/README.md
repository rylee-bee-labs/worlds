# Concept B — "The Garden map"

**Status: MOCKUP.** One of several concepts for Rylee to compare side by side. Nothing here is
approved, deployed or wired to a service. All data is synthetic. No app code, and no v3.1
prototype file, was changed to make this.

## The idea in three lines

Home is a small illustrated garden, and every connected service is a spot in it.
Tapping a spot opens its card: on a phone a sheet-shaped card directly under the map, on desktop
a map on the left and a detail pane on the right.
The other three screens (Connect, Memory, Settings) keep the same house, so the whole thing can
be walked end to end and compared against v3.1.

## How the phone layout is put together

Three rules, and they are the reason nothing on the page overlaps anything else:

1. **The card is never an overlay.** Below 68rem the map and the card are one column, map then
   card, both in the normal flow. An overlay card has to be padded for, hidden from, or fought
   with the map underneath it, and the first phone render lost that fight: the card sat on the
   map with map labels showing around it. A card that is simply *below* the map cannot. It keeps
   the sheet's shape (handle, rounded top, its own border) and its open/close control, and
   selecting a spot moves focus to its title, which scrolls the card into view.
2. **Spots sit in grid cells, not at percentages.** Each spot was placed with `left`/`top`
   percentages, which collide at some widths and not at others — at 390px "Not connected ·
   nothing read" landed on "Front Porch". The spots are now cells in one grid, so no two labels
   can land on each other at any width or text size. A small bounded nudge (`--b-nudge`, under
   half the gap) keeps the garden from reading as a table without letting neighbours touch.
3. **One gutter token.** `--b-gutter` is the side padding of every screen and every band of
   chrome, 16px on a phone and 24px above it, so nothing can sit against a screen edge by
   accident. The nav is a wrapping grid, so a tab is never clipped at the right edge and never
   needs a scroll affordance to be reachable.

## What is distinct from v3.1

| | v3.1 (the counter) | B (the garden) |
|---|---|---|
| Home's shape | A vertical list of slips on a rail, with the receipt in a pane | A spatial map. Position is the navigation; the list exists only as the spots on it |
| Where a service lives | A row in a list you scroll | A place you can point at. Two of a kind ("Shelf Stack 2") reads as two places, which the counter list made hard |
| Selecting | Clicking a slip | Walking to a spot. The pane on desktop, the card under the map on a phone, is the same card either way |
| Empty | A dashed well in a list of slots | A drawn garden with nothing in it, and one dashed plot waiting to be filled |
| Empty plot for an unconnected service | Not shown until you go looking in Discover | Drawn on the map from the start ("Rain Gauge · Not connected · nothing read") |

Kept on purpose, because they are Rylee's standing rules, not this concept's invention:
Dot the snail and its warmth (`dot.webp`, `dot-asleep`, `dot-curious`, `dot-settled`, `stamp.webp`,
`empty-counter.webp`, `empty-ledger.webp`, `dot-peek.webp`, all by relative path into
`docs/vnext/prototype/art/`), the terse-warmth voice, and the house Mulberry & Mint tokens copied
verbatim from the v3.1 prototype so the two can be diffed by eye.

## The Connect screen follows the real flow

Discover → Reference → Test → Preview → Choose → Publish → receipt, in the contract's order
(`docs/vnext/connect-contract.md` §1). It shows what each candidate says it can read and marks
every capability *unverified* until a test has run; the reference scope is a visibly different
list from the publish selection; the receipt has the three stations (Source → Worlds → Agent /
Human). Honesty the brief asked for is on screen rather than implied:

- **Unscoped** is labelled unscoped, in Connect (older connection) and in Settings, with a
  "Narrow scope" way out.
- **Unknown** says Unknown. No reading is invented and no blank is dressed up as a value.
- **Auth: unknown** is said when a probe does not answer, instead of assuming "none".
- A pasted secret-shaped string is refused, cleared and not echoed.
- Approvals are not connected and nothing claims one was sent; a proposal has no Run button.

## Known gaps

1. **No live settling.** A fact going stale or unknown while you watch is not animated here, so
   the "walk out and come back" feeling of the concept is unproven.
2. **No multi-instance proof.** The map can show two spots for one kind, but nothing creates one.
3. **Connect does not write to the garden.** Publishing shows the receipt and links to Home, but
   the garden does not actually grow a new spot — the wiring is out of scope for a mockup.
4. **The map does not scroll or pan.** It is as tall as its spots and the page scrolls past it; a
   garden with 20 spots, or one you could zoom into, needs a real plan view, and that is undecided.
5. **The phone card is below the map, not over it.** That is a deliberate trade for legibility (see
   the three rules above), not a claim that an overlay sheet is wrong. A phone sheet that floats
   over the map is still worth mocking up side by side, and drag-to-dismiss is not built here.
6. **No app frame, no embedded view.** v3.1 has one; B leaves it out, which is a real difference
   to judge rather than an oversight.
7. **State switching is per screen and global to the page.** There is no single "one world, four
   screens, one state" model, because that is what v3.1 already shows.
8. **Not checked with a screen reader.** Structure, focus order, live regions and targets were
   written to the house rules; nobody has driven it with NVDA, VoiceOver or a switch device.
9. **Synthetic times are hardcoded** ("checked 24s ago"). There is no mock clock, so the age line
   never grows.

## Files

- `index.html` — the whole concept in one self-contained file: inline CSS and vanilla JS, no
  network, no CDN, no external fonts. Art is referenced by relative path only.
- `README.md` — this file.

## Checks run

See the commit message. In short: no `innerHTML` anywhere in the file, all four screens reachable
by keyboard, all four state switchers present, every referenced art path resolves, and the token
pairs used for text clear 4.5:1 in both the dark and light themes.

The phone layout is checked by modelling the stylesheet's own arithmetic at 390x844, 1280x800,
320 and 768 — gutter, spot grid columns and rows, nudge bounds and nav fit — because a spot in a
grid cell cannot collide with its neighbour at any width. That model is arithmetic over the CSS,
not a browser render: no browser was available on the machine this was written on, so the page
still wants one pass in a real browser at 390x844 before anyone judges it on that size.