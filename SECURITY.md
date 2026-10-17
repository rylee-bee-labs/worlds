# Security policy

> **Status:** Reference · **Verified:** 2026-10-13 · **Canonical for:** the security policy and public-repository boundary · **Read this if:** you found a vulnerability, or you are about to add config, a hostname, or a credential to this public repo

Which doc owns which command or claim (including the gates named below):
[`docs/vnext/docs-truth.md`](docs/vnext/docs-truth.md).

**In short:** Worlds is a self-hosted app that runs one private place for one person (or a household). This page says how to report a security problem privately, and what must never be committed to this public repository. The automated gate that enforces the boundary is `tests/test_public_safety.py`.

Worlds (the product was called "Project Worlds", then "Personal World") supports
both a single-user identity mode and a multi-principal mode
(`PW_IDENTITY_MODE=multi`, per-person data scoping); security fixes target the
current `main` branch; there is no supported stable release series yet. The
browser front-end is the `ui/` React app, built into the image and served
same-origin at `/` by the backend; the older server-rendered Station and the
first Vite SPA are retired (the Station survives only as a theme package).

## Report privately

Use [GitHub private vulnerability reporting](https://github.com/rylee-bee-labs/worlds/security/advisories/new)
for vulnerabilities or suspected exposed credentials. Do not open a public issue
or pull request containing a secret, personal data, private address, or exploit
against a live deployment. Include affected paths/commit IDs and a minimal
synthetic reproduction. Never send a working token or private key.

If private reporting is temporarily unavailable, do not post sensitive details
publicly; wait for the private reporting channel to be restored.

## Public repository boundary

This repository holds the generic application, public design contracts, and
approved showcase artwork. Keep deployment inventories, private provider config,
personal journals/lore, credentials, backups, and operational logs outside Git.
Use synthetic identities and reserved example domains in tests and documentation.
Review screenshots, SVG metadata, archive contents, and every commit in a PR.
An ignore rule does not remove files already tracked or erase history.

Load `PW_API_TOKEN` from private runtime configuration. Use a unique random token,
keep it out of URLs and logs, and protect remote access with TLS. The API rejects
protected requests when authentication is missing; this is not a substitute for
network access controls. Do not expose an experimental deployment to the internet
without reviewing its deployment and authentication boundaries.

Rooms — the independent services Worlds renders — hold their own bearer tokens in
Worlds' environment, named by indirection (`PW_ROOM_*_TOKEN`, and a registry
`token_env` name); the values live only in the host's `.env` (mode 600), never in
git. Worlds never forwards the human's session token to a room; a per-person room
gets a principal header (`X-Worlds-Principal`) alongside its own room token.

## If a credential was published

Revoke or rotate it immediately with its issuer, then investigate use. Report
only its type, path and commit ID. Coordinate any history rewrite with the owner
and all active contributors; deleting the current file alone is insufficient,
and rewriting history cannot recall existing clones or copies.

## Automated gate

`tests/test_public_safety.py` runs in CI and locally. Beyond deployment
topology it scans every tracked text file for credential *shapes*
(provider key prefixes, private-key blocks, inline `api_key`/`token`/
`password` values, `VITE_*TOKEN`-style client env) and reports findings
redacted — the gate never prints the value it caught. Secrets are always
referenced by indirection (`api_key_env`, `token_env`, `secret_ref`); a
deliberate synthetic canary in a test must carry the marker
`pw-safety: synthetic` on the same line so the exception stays visible.

Nothing served to the browser may ever hold a credential: the `ui/` build is
served same-origin by the backend, and the former Vite bundle inlining
(`import.meta.env`) was removed with the 2026-09-16 SPA cutover. Worlds owns
its own authentication boundary (bearer token, sign-in, optional OIDC with
your own identity provider), so a reverse proxy in front of it is expected to
carry transport concerns — TLS, security headers — rather than to be the
authority.

**Deployment specifics do not belong in this repository.** Host names, LAN
addresses, filesystem paths, install directories and operator runbooks for a
real instance are deployment facts, not product contract: they stay in the
operator's own (private) records. This policy describes the boundary; it does
not describe any particular deployment. If a change would only be true by
rewriting the deployment, fix the deployment or the document — never the
other way around.