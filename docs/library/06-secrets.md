---
title: Secrets
kind: book
order: 6
for: everyone
short: Worlds tells you where a secret lives and whether it's healthy, never what it is.
---
**Say where a secret lives, never what it is.** That one rule covers code,
logs, chat, screenshots and docs.

"The notify token is in the server's private settings file" is fine.
The token itself never appears anywhere but that file.

* * *

In Worlds, the Secrets board shows **names and health only**: which secrets
exist, which are missing, which are old. Never a value.

A value is typed in only once, on the Workshop's trusted page, after
"Confirm it's you". After it's saved, nobody can see it again, including you.
To change one, you type a new one.

* * *

Learned the hard way: tools and helpers leak by accident. A check that
printed "the secret word was…", a VPN tool that exported the server's
private key, an export that included a password. Each was caught in review
and now has a test that fails if it ever comes back.

* * *

## Words to know

- **Secret:** anything that grants access: a password, a token, a key.
- **Secret store:** a locked place built to hold secrets. Official terms: *vault*, *secrets manager* (OpenBao, SOPS).
- **Redaction:** hiding a secret's value wherever it might show up.

* * *

## Under the hood

The Secrets board reads `GET /api/secrets/overview`, which reads the Workshop's `GET /api/secrets/summary` with the workshop room's token. Names and health only, and it's admin-only (`estate_secrets`). Values are typed only on the Workshop's trusted page after step-up. See also the book *The vault*. Canonical: `docs/ARCHITECTURE.md` (Secrets), `SECURITY.md`.
