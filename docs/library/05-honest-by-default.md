---
title: Honest by default
kind: book
order: 5
for: everyone
short: Worlds says "unknown" when it doesn't know, and only a receipt says something is done.
---
**"Unknown" is an answer.** When Worlds can't tell whether something is
fine, it says so. It never turns a guess into a green light.

A room that doesn't answer shows as "not answering, last seen at 9:12",
never as healthy. A room that answers in a language Worlds doesn't speak
shows as incompatible. One broken room never blanks the rest.

* * *

**Only the receipt says it's done.** When you tap Approve, the screen says
"Approving…" until the room answers. It says "Approved" only if the room's
receipt says so. If it can't reach the room, it says "Nothing changed".

* * *

**Every time is the thing's own time.** A card shows when its news happened,
not when Worlds happened to look.

This is also why Worlds has "degraded" as a state. Something can work and
still not be fully fine, and you deserve to know which.

* * *

## Words to know

- **Healthy / degraded / unhealthy / unknown:** the four honest states a thing can be in.
- **Unreachable:** didn't answer; shown with when it last did.
- **Incompatible:** answered, but not in a language Worlds speaks.
- **Receipt:** proof from the other side that something happened.

* * *

## Under the hood

Room status comes only from the room's own `GET /room`. Unreachable rows keep `last_seen`, persisted across restarts. An action's receipt is sanitized to an allow-list (`RECEIPT_FIELDS`) and returned with HTTP 200 whatever happened; its `ok` says whether anything changed. Canonical: `docs/DEGRADED-MODES.md`, `docs/HUMAN_RELIABILITY_CONTRACT.md`.
