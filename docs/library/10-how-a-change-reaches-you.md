---
title: How a change reaches you
kind: book
order: 10
for: everyone
short: A change goes from a checked pull request, to an image, to the server, to your phone.
---

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

Every change to Worlds starts as a **pull request**: a proposed change that
checks run against. Tests, the browser checks, security scanning and
accessibility checks all have to pass.

When it's merged, the build server makes a **container image** for that
exact version, labelled with its commit (a short code like `a955167`).

* * *

Deploying means the server pulls that image and restarts Worlds with it,
after taking a backup. Worlds then reports which version it's running at
`/healthz`, so "is it live?" has a checkable answer.

Learned the hard way: sometimes the image build is skipped for a commit. So
a deploy waits for the image of **that** commit, not just the newest one.
Otherwise you "deploy" and get the old version.

* * *

**The last step is your phone.** An installed app can stay open in memory
for days and never reload. Worlds now remembers the version it opened with.
When a newer one is live, it reloads the next time you come back to it,
unless you're in the middle of typing. Then it says "Worlds was updated"
with a Reload button, and waits for you.

* * *

## Words to know

- **Pull request:** a proposed change that checks run against before it's accepted.
- **CI:** the robot that runs those checks. Official term: *continuous integration*.
- **Container image:** a packaged, ready-to-run copy of Worlds at one exact version.
- **Commit:** one saved version of the code, named by a short code like `a955167`.
- **Deploy:** putting a new version live.

* * *

## Under the hood

`publish-image.yml` builds the image for a validated `main` commit and bakes in `PW_COMMIT`. `/healthz` reports its short form. The deploy takes a backup and a rollback tag, then pulls and restarts, then waits for healthy. Wait for the publish run of the exact commit: runs can be skipped. The app's `StayFresh` (`ui/src/app/StayFresh.tsx`) compares the opening commit with `/healthz` on return and every 5 minutes. Canonical: `docs/OPERATIONS.md`, `docs/CI-ENVIRONMENT-NOTES.md`.
