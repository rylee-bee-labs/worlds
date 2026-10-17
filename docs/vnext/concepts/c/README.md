# Concept C — "The Card deck" (MOCKUP)

Status: MOCKUP, one of the gallery Rylee asked for on 2026-10-16 ("Accept the architecture and …
deliver me UI mockups in the gallery"). Nothing here is approved. Open `index.html` directly; one
self-contained file, inline CSS/JS, no network, art by relative path (`../../prototype/art/…`).

## The idea, in three lines

Worlds becomes a tactile deck: one bold card per service, dealt big, one thing at a time.
The phone swipes or steps through the deck; the desktop lays the whole board out in three columns.
Connect is the deck's most deliberate hand: five cards dealt one at a time — pick, read, scope,
try, receipt — and nothing is saved until the last one.

## What is distinct (from v3.1 and from a map)

- **One card, one service, no chrome between them.** No rail, no sticky detail pane, no receipt
  station grid on Home — the card *is* the surface. Depth comes from the surface ladder and the
  state-coloured band along each card's top edge, not from panels.
- **The deck is the navigation.** Phone: stacked card edges behind the current card, swipe or
  Previous/Next, "Card 2 of 5", arrow keys; desktop: the deck fans out into a board. The same
  content, two tempos, no third layout.
- **Connect is dealt, not routed.** A left-hand step list on desktop, "Step 3 of 5" on phone, one
  card per step, Back/Cancel always, and the receipt is the fifth card — the flow the Connect
  contract and the 2026-10-16 review ask for: unverified capabilities and "Auth: unknown" at
  discover, the send scope said before any test (with an honest "Unscoped" choice, the surface
  review Q3 says is missing), a safe test that can visibly fail, each fact keeping its own state
  word, and a publish receipt that names what lands, what is kept out, when, and by whom.
- **Motion is card motion.** Cards deal in with a slight tilt and a stagger; the "Connected"
  stamp lands rotated; hover lifts a card two pixels. One easing curve, and every duration
  zeroes under `prefers-reduced-motion` or the in-page "Reduce motion always".
- **Rylee's pick, in Mulberry & Mint.** She chose C on 2026-10-16 ("I choose C for worlds vnext,
  but I'd like it in the mulberry and mint colors"), so the mockup now defaults to the dark
  Mulberry & Mint mode: deep mulberry surfaces, mint leading the primary buttons, the active tab,
  the focus rings, the "Full deck" state chip and every card's top band, with apricot and lilac
  only as secondary card accents — status still says its state in words. Light and High contrast
  stay one toggle away in Settings, `prefers-contrast: more` is honoured, and Light leads with
  the same mint/mulberry accents, not generic green.
- Dot, terse warmth and the state vocabulary are the standing rules, so this concept stays a
  costume change over the same skeleton, not a different product.

## Known gaps (deliberate, for the gallery pass)

- **No live feed.** Ages are fixed strings ("checked 24s ago"); there is no tick, no pause ladder,
  no stale-by-rule arithmetic. The "Live" toggle in Settings changes words only.
- **Connect is one scripted service.** Picking a different candidate redraws the scope step but
  the test and receipt still tell Notes Sync's story. No per-candidate facts.
- **No app frame, no rename, no Needs you screen.** Needs you is a card state here, not the
  skeleton's fourth door; the handoff is the receipt's inert proposal line, honestly labelled
  "Approvals aren't connected."
- **Type falls back.** Young Serif and Atkinson Hyperlegible Next are not embedded (no network);
  the system serif/sans stand in, so the type step is approximate.
- **Deck swipe is a hint, not a carousel.** No snap physics, no card transition between swipes —
  the next card deals in. Keyboard and buttons cover the same ground.
- **One polite live region, no assertive one**; no focus trap work, no `document.title` badge, no
  localStorage. Those belong to a prototype round, not a mockup.
- Screen-reader pass (NVDA/VoiceOver/TalkBack) not run; contrast pairs are computed, not measured
  in every theme.