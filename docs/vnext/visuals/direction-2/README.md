# Worlds vNext — visual direction 2: **The Harbor**

> **One-line idea:** Worlds is a small harbor — every service you run is a boat moored at your dock, and the front page is the view from the pier: which boats are calm, which are hailing you for a human decision, and which have drifted out of sight.

**Status:** MOCKUP. A mockup is not an approval — `MOCKUP != PROTOTYPE != APPROVED`. Rylee picks the direction (issue #321/#322). This directory contains sketches for comparison only; it is not a build and nothing here ships.

---

## Who it suits

Someone running a handful of independent services at home who wants a single, calm view of the whole dock rather than a grid of unrelated widgets. It suits people who like a **place** they can point at — “that boat, third from the left” — and who want the page to say, in plain words, what is fine and what is not. It leans warm and playful, but its whole structure is built around honesty: an unknown berth is drawn as empty on purpose, and a silent boat is never drawn as calm.

## Three strengths

1. **Spatial memory.** Berths have fixed numbers and the dock keeps its shape. You learn where Media library sits the same way you learn where a tool lives on a workbench, so low-capacity days do not cost you a search.
2. **State is a first-class shape, not a colour.** Calm, needs-you, stale and unknown are four different berths with four different visible wordings and four different marks (solid dot, flag, half-moon, question mark). Strip the colour away and the page still reads correctly.
3. **A front page that can honestly be empty.** First run with zero services and zero providers is designed as a real state — an empty harbor with working notes, reminders and a short list — instead of a dead end or a fake “all systems go”.

## Three risks

1. **The metaphor can outrun the facts.** “Boat”, “harbor”, “weather” and “log” are charming but must never soften a statement. If the metaphor ever tempts a builder to write “all clear” where the truth is *stale* or *unknown*, the copy is wrong — the words win over the theme.
2. **Decorative weight at phone width.** Harbour chrome (tide strip, berth numbers, log) is a lot of furniture for 390 px. It must collapse to a clean single column with the status word leading, or it becomes noise that hides the one thing needing attention.
3. **It implies a metaphor the Connect API might not feed.** Berths, “last heard” ages and calm/stale/unknown only work if the connect layer can report *when* it last heard from each service and *whether* it has ever heard at all. If the API can only say on/off, this direction degrades into fiction.

## What a later Connect API must supply for it

The Harbor is only honest if the connect layer can answer these, per service:

- **Identity and order** — a stable id, a human name, and a person-chosen berth order, so berths do not reshuffle under you.
- **Last-heard timestamps** — when Worlds last got a real answer from each service, and the freshness window it considers “current” for that service. Without this there is no **stale**, only a guess.
- **A tri-state, not a boolean** — `ok` / `needs_you` / `stale` / `unknown` as separate signals. Crucially, **unknown must be representable** (never heard from, or unreachable), and its difference from a stale reading must survive the wire.
- **The owning system's hand-off URL** — for “needs you”, a link out to the system that owns the decision, so Worlds can hand you over and get out of the way; Worlds never resolves it itself.
- **A short, human reason** — one plain sentence for why a service is flagging, so the card can say what needs deciding without inventing detail.
- **Zero-provider mode** — a first-class empty response that returns “no services” rather than an error, so the empty-harbor state is fed by the API and not faked in the front end.
- **Provenance for every field** — each reading carries where it came from and when, so a stale value can be shown *as* stale instead of silently rendered as fresh.

Until that API exists, this directory shows sample data only. **No provider result in these pages is real**, and none of it was fetched from any service.

## Files

| File | State |
|---|---|
| [quiet-day.html](quiet-day.html) | Quiet day — several services, all calm |
| [needs-you.html](needs-you.html) | Needs you — one service wants a human decision, linking out to the owning system |
| [stale-unknown.html](stale-unknown.html) | Stale / unknown — one source stale, one unknown, both labelled in words |
| [no-services.html](no-services.html) | No services — first run, zero providers, still useful and inviting |

Each page is a single self-contained HTML file: inline CSS, a few lines of inline JavaScript for the width toggle, no external network, no build step. Open any file directly in a browser. Use the **Desktop / Phone 390 px** control in the masthead to show both widths; the layout reflows on a real narrow viewport as well.

## Floors this direction meets

- Text contrast targets WCAG AA (body ink `#11212e` on paper `#f7f3ea`; every status uses a dark ink on a light tint).
- Touch targets are at least 44 CSS px — buttons, viewer toggles and the disclosure summary.
- Keyboard focus is always visible (`:focus-visible` outline on every interactive element).
- Headings are semantic: one `h1` per page, `h2` per section, `h3` per service.
- Status is never shown by colour alone: every state also has a visible word (“Calm”, “Needs you”, “Stale”, “Unknown”) and a distinct glyph.
- `prefers-reduced-motion: reduce` disables all animation and transition, and `prefers-contrast: more` thickens borders.
- No horizontal scroll at 390 px; layout uses a container query so both the real narrow viewport and the simulated 390 px frame behave correctly.
- Every page carries a visible **MOCKUP** badge and a sample-data notice.

See the [accessibility contract](../../../accessibility/ACCESSIBILITY_CONTRACT.md) for the non-negotiables this sketch is aiming at; a mockup is not a verification result.
