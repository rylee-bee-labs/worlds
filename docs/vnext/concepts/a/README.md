# Concept A — The Counter, extended

1. The v3.1 prototype Rylee called "this is great", kept whole: same tokens, same Dot, same counter-and-slip layout language.
2. The screens it lacks — Connect, Memory, Settings — added in that exact voice, so one language covers the whole product.
3. Every screen carries a mock-data switcher (first run, loading, error, full) so she can compare all four states side by side; nothing here is approved.

## The idea

The v3.1 prototype already answered "what does Worlds feel like". This mockup refuses to
re-answer it. It keeps the prototype's room, palette, type and Dot behaviour untouched, and
spends all its new effort where the prototype was silent: the Connect flow (pick a service,
what it can read, the scope the reference asks for, a safe test, what to show, a receipt),
the Memory ledger (who sees each fact, who can act), and Settings (credential references,
live feed, motion). Scope is stated everywhere a reference appears — including one honestly
"Unscoped (older connection)" connection, which the Connect contract review asked to see on a
surface. One file, `index.html`; open it in a browser, no build.

## What is distinct

- **Faithful by construction.** The token blocks, type scale and line glyphs are carried
  over from `../../prototype/index.html` rather than restyled, so the two open side by side
  and read as one design.
- **States are first-class.** A switcher above every screen (First run / Loading / Error /
  Full) keeps the empty, slow and broken paths on the same surface as the happy one, which
  is where the review's honesty tests live.
- **The flow, not a screen.** Connect is shown as six numbered beats ending in the receipt
  and the tilted "Connected" stamp, with the failure path one state-switch away.
- **Working preferences.** Theme, reduced-motion and live-feed controls in Settings
  actually work in the file; everything else announces "Mockup. Nothing changes."

## Known gaps

- No embedded owning-app frame and no Needs You handoff screen: the prototype already has
  both, and this concept only adds what it lacked.
- The reference store, live polling and the publish list are faked with one fixture's worth
  of obviously synthetic data; Disconnect here is a label, not a flow with its confirm.
- Keyboard and screen-reader behaviour were written to the rules but not audited with a
  real screen reader or a real phone; both are next steps before any of this is believed.
- The unscoped Media Shelf shows the label the review asked for, but does not model the
  review's publish-allow-list question — that needs a contract answer first.

## Files

- `index.html` — the whole mockup: Home, Connect, Memory, Settings, each with four states.
- Art is referenced from `../../prototype/art/` — nothing is copied or fetched.