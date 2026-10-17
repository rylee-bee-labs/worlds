---
title: Lessons learned the hard way
kind: book
order: 11
for: everyone
short: The mistakes that turned into Worlds' rules, and what each one taught.
---
These are the mistakes that turned into rules. Each one cost a day, or
almost cost something worse.

* * *

**A guess is not a green light.** Early screens said "healthy" when they
hadn't checked. Now "unknown" is a real state, and every status comes from
the thing itself.

**The receipt decides.** Screens that said "Done" before the other side
answered were sometimes wrong. Now only the receipt says it.

* * *

**Say where, never what.** Helpers and scripts leaked secrets in small
ways: a test word in a message, a private key in an export. The rule is now
simple enough to check, and each leak has a test.

**Review what helpers build.** Fast helpers write a lot of good code. They
also chose a password for an invite, left a people list open to guests, and
printed a key. Security gets a person's (or a careful reviewer's) own eyes,
every time.

* * *

**One path beats many.** Several ways to answer a need meant one of them
was quietly broken. One answer path, routed by the room, fixed it for good.

**Wait for the exact version.** A deploy that grabs "the newest image" can
grab yesterday's. Wait for the image of the commit you mean.

* * *

**Installed apps don't reload.** A phone kept showing an old Worlds for
days. Files were never the problem; the app just never restarted. Worlds
now notices and reloads itself at a safe moment.

**Polling is slow and blind.** Asking every minute meant a screen could be
a minute behind. A tiny "I changed" ping plus a live stream fixed it, with
polling kept underneath as a safety net.

* * *

**Setup must check itself.** Worlds held no real data for weeks because
setup wasn't trustworthy enough. Every setup now tests itself and speaks
plainly.

**Plain words win.** Codes, jargon and clever names slowed everyone down,
people and agents alike. Exact, plain words are faster for everybody.

* * *

## Words to know

- **Regression test:** a test written after a bug, so that bug can never come back quietly.
- **Fail closed:** when unsure, refuse rather than allow.
- **Single source of truth:** one place that decides, instead of many that can disagree.

* * *

## Under the hood

Each lesson has a guard in the code: `test_rooms_actions.py` and `test_rooms_live.py` (receipts, one answer path), the redaction tests in the `lab vpn` and Play-Nice tools, `StayFresh` for stale installed apps, and the room change ping with polling underneath.
