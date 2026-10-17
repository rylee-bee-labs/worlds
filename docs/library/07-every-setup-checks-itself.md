---
title: Every setup checks itself
kind: book
order: 7
for: everyone
short: Everything you set up has a screen that tests itself and tells you the next step in plain words.
---
**No one should need to edit a config file.** Everything a person sets up in
Worlds has a screen, and every screen checks its own work as you go.

Set up sign-in, and it tries to sign in. Set up notifications, and it sends
you a test. Connect a room, and it knocks on the room's doors and tells you
which ones answered.

* * *

**The same tools for everyone.** A non-technical person gets the same power
as a technical one, in plain words. Nothing important hides behind a
terminal.

Every check says what it found and what to do next: "worked", or "needs a
fix: here's the next step". Never a code or a stack trace.

* * *

Why: Worlds had no real data in it for a long time on purpose, because
setting it up wasn't easy enough yet to trust with real life. The rule
came from that.

* * *

## Words to know

- **Validation:** checking that a setting really works, not just that it was typed.
- **Self-check:** a setup that runs its own validation as you go.
- **Config file:** a text file of settings. Worlds' goal is that nobody has to edit one.

* * *

## Under the hood

Owner rule (2026-09-26): "every setup checks itself, no config file editing, non-tech users get the same tools." It is also on the Play-Nice floor. Examples in code: the notifications test send (`/api/push/test`), room probes in `rooms.py`, and the setup wizard (`setup_wizard.py`).
