# Worlds vNext — the full design, from V2 (brief)

Status: MOCKUP brief. The spec and prototype it produces are a design, not approved product and not deployed.

## Decisions in force (quoted)
- 2026-10-13 Rylee: "Yeah. V2 is the only one that passed. Can we now feed that back in with all the field guide info and everything to generate a full design?"
- 2026-10-13 Rylee: "comprehensive but also keep the original feeling." Clarified: protect the feel, the look, the whimsy and the love, NOT the copy. Copy is free to be rewritten for clarity per the plain-words guide (LANGUAGE.md).
- 2026-10-13 Rylee: "Go with concept 5 from here. Bring it into our design language and have it make a few variations based on the overall flow please"
- 2026-10-13 Rylee: "the more real application with whimsy and warmth laced in but make sure they have both desktop and mobile and are reactive <3"
- 2026-10-13 Rylee, Project Home decision 145: "Approve the boundaries; Sol's six conditions become pre-prototype gates" (the Connect contract, draft PR #329).
- 2026-10-12 Rylee: "Field Guide as base" (the World Tree Field Guide is the base of the shared design system; Mulberry & Mint).

## Inputs ("everything")
1. **V2 "Welcome-led"** (her pick): `docs/vnext/v2/DESIGN.md`, `docs/vnext/v2/CRITIQUE.md`, `docs/vnext/v2/index.html`, `docs/vnext/v2/checks.json`. Its ancestor **Concept 5 "The Counter"** (Dot the snail): `docs/vnext/concept5/DESIGN.md` and `index.html`.
2. **The Field Guide**: `docs/vnext/field-guide/` — the World Tree Field Guide docs (README, MAP, GLOSSARY, DESIGN-REFERENCE: "Stable meaning. Mutable form."; the skeleton Home / Explore / Needs You / Guide; Platform / Capabilities / Experience, where Worlds is Experience), the design system's WORLD-TREE.md and ART-SOURCES.md, the "Field Guide is the base" decision, the field-guide-base specimen, and Worlds' workshop manifest.
3. **The house design language**: `docs/vnext/house/` (Rylee-Bee Design System DESIGN.md + tokens.css, Mulberry & Mint, LANGUAGE.md plain words, JOY-CURIOSITY-AND-CARE.md, Worlds' Mulberry & Mint CSS).
4. **The Connect contract**: `docs/vnext/connect/connect-contract.md` (from #329) and Rylee's approved boundaries with **Sol's six pre-prototype conditions**, which the design must honour visibly: (1) Project Home approval is fail-closed: never shown as working, an approval is a link/handoff that can say "not available yet"; (2) proposed actions are inert: shown as proposals, never executable from Worlds; (3) scoped auth before any network call; legacy unscoped access labelled "unscoped"; (4)-(5) contract fixes (done in #329); (6) the read-only path is proven first: keyboard, mobile, stale and unknown.
5. **Integration requirements** from `concept-brief-v2.md` and `concept-brief-v3.md` (plug-in live through discover → credential reference → test → preview → publish; composition; embedded app frame with fallback; one fact many places; governed handoff; disconnect; live feed; two purposeful layouts) and the **Stage C proof path**: empty Worlds → connect one service → preview → publish a card → it goes stale / unknown → link out to the owning system → disconnect → Worlds still works.
6. **Data**: `docs/vnext/fixture/fixture.json` only.
7. **Rylee's preferences**: dark by default with soft contrast, reduced motion respected, full keyboard support, 44px targets, plain words (LANGUAGE.md).

## The feeling to protect (write this FIRST, at the top of the spec)
Before anything else, study V2 and Concept 5 and write a short section, **"The feeling to protect"**: what makes them look and feel the way they do — the visual style (palette use, shapes, the counter and slips, texture and depth), Dot the snail and how Dot behaves (asleep when empty, nods on change, carries the parcel on connect, never the data courier), the warmth and the love in the details, the delight moments (the "Connected" stamp, the parcel hand-off, the quiet calm when nothing needs you), the pacing of the welcome (unhurried, skippable, one thing at a time), and the motion character (gentle, within reduced-motion rules). Name 6-10 concrete things with where they appear. **Copy is NOT protected**: rewrite any wording for clarity using LANGUAGE.md's plain words. This section is a review criterion: everything added must keep that look and feel; comprehensive coverage must not turn into generic app screens.

## The full design (deliverable 1: `docs/vnext/worlds-design.md`)
A complete spec, keeping the protected look and feel, covering:
- **Information architecture**: how Worlds' destinations map onto the Field Guide skeleton (Home, Explore, Needs You, Guide) while staying Worlds (Experience layer: the counter, Dot, the slips). Name each destination and why.
- **Every screen and state across the whole flow**: first run / welcome with Dot (skippable), empty counter, home/counter with composed services, the full Connect lifecycle (discover, credential reference with secret refusal, safe test incl. failure and retries, preview, choose, publish and the Connected moment), a service's surface, the embedded app frame (loading, loaded, refused → fallback), Needs You (a handoff to Project Home that may be fail-closed: "approvals aren't connected yet"), proposals shown as inert, stale, unknown, failed/unavailable, revoked credential, disconnect (confirm, what is kept and what goes), back to empty, Memory / agent facts (who sees, who acts, scoped vs unscoped), Settings (credential references, live feed, motion, text size, theme), offline/error.
- **Layouts**: desktop 1440, tablet 768, phone 390, each designed on purpose (navigation pattern, reading order, what moves where).
- **Components and tokens**: each component, the house token names it uses (no literals outside tokens), and its states.
- **Copy**: the real strings for every state, plain and clear, using LANGUAGE.md words.
- **Motion and accessibility**: what moves, why, and its reduced-motion form; keyboard map; focus order; screen-reader structure; 44px targets; contrast in all four house modes.
- **Reactivity**: the live feed, propagation, optimistic feedback and settle, pause/resume.
- **Trust and boundaries**: where Sol's conditions appear in the UI.
- **Open questions and UNKNOWNs.**

## The prototype (deliverable 2: `docs/vnext/prototype/index.html`)
One self-contained HTML file (inline CSS and vanilla JS, no network, no external fonts/images/libraries) implementing the WHOLE flow in the spec, not a single page: welcome → counter → connect (all steps, including a failure path) → composed home → service surface → embedded app (and its refused/fallback state) → simulate change (one fact updates every view) → needs-you handoff (fail-closed) → stale/unknown via the live feed → revoke → disconnect → empty. Desktop, tablet and phone layouts. Checker ids: `#add-service`, `#disconnect` (visible on the first screen for the selected service, confirm button labelled "Disconnect"), `#simulate-change`, `#live-toggle`, plus `#skip-welcome` on the welcome. Visible MOCKUP label. House tokens only.
