---
title: The vault
kind: book
order: 14
for: everyone
short: A vault is a locked box for secrets that only opens for the right person, and only shows a secret when truly needed.
---
A **vault** is a locked box for secrets: passwords, keys, tokens. It keeps
them scrambled (encrypted), so a copy of the box on its own is useless.

To use it you unlock it. Locking it again makes it forget every secret it
had unscrambled.

* * *

**Worlds has a small vault of its own.** You unlock it with a passphrase.
It lists secrets by name and never shows a stored value on screen again.
If the part that does the scrambling is missing, the vault refuses to store
anything: there's no "unsafe mode".

Adding or removing a secret needs "Confirm it's you" first.

* * *

**The whole estate can share a bigger vault** (OpenBao, a server built for
this). It keeps a record of every time a secret is read. It saves locked
backups on a schedule, and only unlocks when its owner does it by hand.

Either way, the rule from the *Secrets* book holds: say where a secret
lives, never what it is. And a secret never goes into a chat, a model, or a
log.

* * *

## Words to know

- **Vault:** a locked box for secrets. Official terms: *secrets vault*, *secrets manager*.
- **Encrypted:** scrambled so only the right key can read it.
- **Passphrase:** a long password that unlocks the vault.
- **Unseal:** unlocking a server vault after it starts (OpenBao's word).
- **Audit log:** a record of every time a secret was read or changed.
- **Fail closed:** when something is wrong, refuse instead of carrying on unsafely.

* * *

## Under the hood

The native vault is `src/personal_world/vault.py` (`Vault`, `VaultContract`: get, set, delete, list_names, audit), stored in `vault.enc` with Fernet encryption and a key derived with PBKDF2-SHA256. The `cryptography` extra must be installed; without it, unlock returns `unavailable`. `set` and `delete` require step-up. A SOPS read-through adapter exists; there is no OpenBao adapter in Worlds yet. The estate's OpenBao plan lives in the homelab repo. Canonical: `docs/ARCHITECTURE.md` (Secrets) and `docs/adr/0007-vault-openbao-scoped-credentials.md`.
