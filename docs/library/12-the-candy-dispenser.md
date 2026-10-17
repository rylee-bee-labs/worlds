---
title: The candy dispenser
kind: book
order: 12
for: everyone
short: Candy finds books, music, shows and releases you might like, and learns from what you keep.
---
Candy is Worlds' finder. It looks through the places you point it at (a
library, a music service, a list of new releases) and brings back things
you might like. Each find is a piece of candy.

It's its own app, a room. Worlds shows its best finds as cards, and Candy
has its own page for browsing.

* * *

**Candy learns from you.** On each find you can Save it, say "More like
this", Hide it, or Mute where it came from. Candy remembers those choices,
per person, and the next finds lean your way.

It never finds the same thing twice: it remembers what it has already
shown you.

* * *

**It's personal.** Worlds tells Candy who is asking, so your finds are
yours and someone else's are theirs.

**It can run on its own.** Candy can check your sources on a timer and
have fresh candy waiting. It can also run only when asked.

* * *

## Words to know

- **Source:** a place Candy looks for finds.
- **Find:** one thing Candy thinks you might like. Official term: a *recommendation*.
- **Signal:** a choice you made (save, more like this, hide, mute) that teaches Candy. Official term: *feedback*.
- **Dedup:** making sure the same thing is never shown twice. Official term: *deduplication*.
- **Per-person room:** a room that gets told who is asking, so it answers for that person.

* * *

## Under the hood

Candy is a separate service (private repo) that serves `room/0`. Worlds sends `X-Worlds-Principal` with its token because its registry row has `forward_principal: true`, and caches cards and needs per person. Choices live in Candy's data directory (`people/<person>/choices.json`), and seen items in `state.json`. `CANDY_POLL_MINUTES` turns on the background poller (unset or 0 means off). Source credentials come from the environment by name only. The candy runbook is its own `docs/OPERATIONS.md`.
