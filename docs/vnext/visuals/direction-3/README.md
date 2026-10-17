# Direction 3: The Daily Note

**Idea:** Worlds opens as a short, plain-language morning note about your world, with services as links inside sentences and an index beneath. It is read top to bottom like a letter, not scanned like a dashboard.

Status: **MOCKUP**. Not a prototype, not approved. Rylee picks the direction (issues #321/#322).

## Files
Open in a browser; each is one responsive page (single column at 390px, note + margin column from 56rem up).
- `quiet.html`: quiet day, five services, all Fine.
- `needs-you.html`: Backups waits on a human decision; the button links out to the owning system.
- `stale-unknown.html`: Media library is Stale, Home lights is Unknown, both said in words.
- `empty.html`: first run, no services, no AI provider; still useful and inviting.

All content is sample data. Hosts use the reserved `.example` TLD. Links and "Add a link / Connect a service" are placeholders.

## Who it suits
People who run a handful of services and want a calm answer to "do I need to do anything?", including less technical household members and anyone on a phone.

## Strengths
1. The answer comes first, in a sentence: what needs you, then what is fine. Unknown and stale are written out, never guessed.
2. One column, no widgets, no tiles: a short list reads well on a phone, with 44px rows and the same structure at every width.
3. Empty state is just a shorter note, so first run is not a different product, and nothing needs an AI provider.

## Risks
1. Prose gets long with 30+ services; it needs a grouping or "show the rest" rule.
2. A generated sentence could sound more certain than the data. Sentences must be templated from real fields, never free-written by a model.
3. Less glanceable than a tile grid for power users who want everything visible at once.

## What a later Connect API must supply
- Per service: stable id, display name, owner-system URL (deep link for the decision), and a state of `ok | needs_human | stale | unknown`. Never default to `ok`.
- `last_checked_at` and `last_changed_at` per service, so "stale" is computed from data, plus a staleness threshold.
- For `needs_human`: a title, `waiting_since`, a short reason, and the deep link to the owning system. Worlds does not act.
- A one-line factual summary per service (e.g. "2 new episodes"), supplied by the provider, with a source label.
- A priority/ordering hint, and an explicit "zero providers" response so first run is valid.
- Provider-supplied fields only: no fabricated results.

## Floors check (by design, not yet browser-tested)
AA contrast text colours, 44px rows/buttons/nav links, 3px focus outline, skip link, one h1 and h2/h3 ordering, status as word + glyph + outline style, reduced-motion media query, `overflow-wrap` and fluid columns for no horizontal scroll at 390px. No browser was available in this environment, so visual checks at 390px and desktop remain to be done by a person.
