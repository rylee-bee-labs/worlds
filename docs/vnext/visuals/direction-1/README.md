# Worlds visual direction 1 — the shoreline

> **Status: MOCKUP.** Not a prototype, not approved. Rylee picks the direction
> (issues #321/#322). Nothing here is built, nothing here is wired to a
> provider, and no page in this folder was produced by a real provider result.

## The idea, in one line

**Worlds as a shoreline: your services are moored along a shore, and only what has drifted to the
waterline needs you.**

Structure, not just colour: services are sorted into three bands of **distance from the waterline**
— *At the waterline* (a person is needed), *In the shallows* (answered recently), *Out past the
point* (fine, or out of reach). The page is a vertical walk down a shore on a phone and a wide,
horizon-shaped spread on a desktop, with the depth ruler stated in words at the top. There is no
status column, no sortable grid, no "dashboard of tiles".

## What it looks like

Open [`index.html`](index.html) in a browser for all four states at both widths, or open a state on
its own:

| File | State |
| --- | --- |
| [`01-quiet-day.html`](01-quiet-day.html) | several services, all fine — the waterline is empty on purpose |
| [`02-needs-you.html`](02-needs-you.html) | one service wants a human decision, linking out to the owning system |
| [`03-stale-unknown.html`](03-stale-unknown.html) | one source stale, one unknown, both labelled in words |
| [`04-no-services.html`](04-no-services.html) | first run: zero services, zero providers, still useful |
| [`check_floors.py`](check_floors.py) | static accessibility/offline checker for the five pages |

Each page is self-contained: inline CSS, no JavaScript, no external network, no build step. They open
from the filesystem.

## Who it suits

Someone whose house is mostly fine. The direction assumes the common case is *nothing is wrong*, so
it spends its loudest place (the top of the page, at both widths) on the one thing that needs a
person, and pushes everything else down the shore. It suits a person who wants to glance once, be
told the truth, and get on with their day — and who would rather be told "I don't know" than be shown
a green tick for a service nobody has heard from.

## Three strengths

1. **The order is the argument.** Where a service sits is a claim about how close it is to needing
   you, so "what matters first?" is answered by the layout itself rather than by a sort control or a
   badge you have to learn. On a quiet day the top of the page is deliberately empty, which makes a
   quiet day readable in one glance.
2. **Uncertainty gets its own place, not a footnote.** *Stale* and *Unknown* sit in their own band
   with their own words, their own shapes, and a plain statement that unknown is not an outage —
   they are never rounded up to "broken", and they never borrow the green of a service that answered.
   Colour repeats the word; it never carries it.
3. **Authority stays visible in the copy.** The needs-you state links out to the owning system and
   says who decides ("you, in Fernway"), and the in-page note spells out the ask → approve → send
   once path. The metaphor invites calm without implying that Worlds took over anything.

## Three risks

1. **The metaphor can outrun the product.** Bands named *shallows* and *out past the point* are
   friendly, but they have to keep matching one real ordering rule. If the ordering becomes
   configurable or per-service, the shore stops being honest and becomes decoration. This is the
   risk most likely to kill the direction.
2. **Depth becomes a false ranking.** "Out past the point" reads as *further away = less important*.
   Someone whose project dashboard sits below their porch lights may correctly feel demoted. The
   pages try to answer this in words; a person may not read the words.
3. **Two widths, two layouts.** The phone walk and the desktop spread are different enough to be
   two design surfaces, which doubles review, translation and future maintenance — and the desktop
   spread wastes vertical space when only one service needs attention.

## What a later Connect API must supply

- **`checked_at` as data, per service, per source** — the bands are drawn from it, so a stale band
  needs a real timestamp, not an inferred one.
- **A status enum with an explicit `unknown`** — `healthy | needs_attention | unavailable | stale |
  unknown | disabled | not_configured`. Worlds must be able to say "never heard from" without
  inventing a reason.
- **The owning system's name and an outbound address for every service**, so the card can link out
  rather than re-implement. This is the boundary that keeps the direction honest.
- **A decision request shape** — who decides, what they are being asked, and by when — so the
  needs-you card can say *you, in Fernway* instead of a generic prompt.
- **A dispatch result vocabulary** — `sent | failed | unknown`, plus the fact that an approval is
  spent once — so the "carry your answer" note can be generated rather than written.
- **A capability list that can be empty** — the no-services page must be renderable with an empty
  service list and no providers at all, and must still be served.

## Floors

Checked statically by [`check_floors.py`](check_floors.py):

```sh
python3 docs/vnext/visuals/direction-1/check_floors.py
```

It verifies text contrast for every declared colour pair (25 pairs, WCAG AA 4.5:1 for text and 3:1
for focus rings and card borders), one `h1` per page with no skipped heading levels, a skip link as
the first focusable element, a visible `:focus-visible` outline, a `prefers-reduced-motion` rule, a
visible `MOCKUP` label, a status word inside every status pill, a 44px minimum height on every
anchor class, no external network reference, no real hostname, and no fixed element width above
390px.

It is **not** a browser. Measured tap-target pixels, 200% zoom reflow, 390px rendering, screen-reader
output and `prefers-contrast` behaviour still need a real browser pass and a manual acceptance
before this direction could ever be called a prototype.

Honesty about the content: every service name, owning system, address and value on these pages is
invented for the mockup. Nothing was fetched from a provider. Outbound links point at RFC 2606
`.invalid` addresses, which cannot resolve.

## Decisions this direction does not touch

- Worlds owns meaning; the owning system keeps its own authority. Every outbound action is a link or
  an explicit ask, never a takeover.
- Landmarks stay `Home · Connect · Memory · Settings`. Only **Home** is drawn here; the other three
  are named on screen and marked *not drawn here* rather than left as dead links.
- Status words come from the accessibility contract: healthy, needs attention, stale, unknown, not
  set up. No theme or direction may lower the contrast, target-size, focus or motion floors.