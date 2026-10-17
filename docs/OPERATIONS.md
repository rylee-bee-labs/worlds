# Operations guide (0.1)

> **Superseded in part by [ADR-0008](adr/0008-front-door.md) (2026-10-01):** the front-door rebuild replaced the old app. Sections below that use bearer tokens, the setup wizard, or the retired backend entrypoint describe the old install; the current app runs `uvicorn personal_world.worlds.production:app_from_env --factory` (see "Rebuild: sign-in behind a reverse proxy" at the end) and signs in through `owner.yaml` ([docs/rebuild/CONTRACTS.md](rebuild/CONTRACTS.md) C7). Backup and restore now follow [docs/rebuild/DURABILITY.md](rebuild/DURABILITY.md).

> **Status:** Reference · **Verified:** 2026-09-29 · **Canonical for:** running, deploying, updating and backing up Worlds · **Read this if:** you are operating an instance — local CLI, containers, production deploy, backups, or chat providers.

**In short:** how to run Worlds locally and in containers, sign in with your own SSO, deploy and roll back, and keep data safe. Keep private hostnames, credentials and access procedures in your own private operator docs — this repo carries the portable pattern only.

> **First run on new hardware?** See
> [`docs/history/OPERATIONS-FIRST-RUN.md`](history/OPERATIONS-FIRST-RUN.md) — the
> dated 2026-09-09 bring-up record (historical, not a current recipe).

This guide describes the public standalone application. Keep private deployment
hostnames, service inventories, credentials and access procedures in private
operator documentation.

## Local CLI, zero optional providers

From the repository root, install the locked dependencies and initialize a private
local config directory:

```bash
uv sync --frozen --extra test
uv run personal-world --config-dir config.local init
uv run personal-world --config-dir config.local daily
```

Initialization is idempotent and does not overwrite existing configuration.
`config.local/` and `data/` are ignored by Git. Add optional providers only to your
private configuration; use [provider contracts](PROVIDERS.md) as the reference.
The tracked `config/connections.json` is separate from this local configuration.

## Local web API

Export the config and data directories the app reads, then run the production entrypoint:

```bash
export PW_CONFIG_DIR="$PWD/config.local"
export PW_DATA_DIR="$PWD/data"
uv run uvicorn personal_world.worlds.production:app_from_env --factory --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. Sign-in is through `$PW_CONFIG_DIR/owner.yaml` —
OIDC, or the bootstrap secret while `bootstrap.enabled` is true — never a pasted
bearer token ([docs/rebuild/CONTRACTS.md](rebuild/CONTRACTS.md) C7). Never put
secrets in URLs, screenshots, shell transcripts or public issues.

The browser also has `/setup` and `/login` entry points.
First-run setup (`POST /api/setup`) is unauthenticated only until the
setup-complete marker exists — it is also loopback-only (a non-loopback
peer gets 403) and rejects repeats with 409 once the marker exists.
`POST /api/chat/test` requires authentication (bearer, browser session,
or the opt-in loopback dev bypass); it has no elevation gate.
See [Architecture](ARCHITECTURE.md) for the
route inventory and the limits of the current extra write check called step-up.
It is not verified SSO/MFA re-authentication.

### Token reconciliation at boot (setup-created tokens survive restarts)

The setup wizard writes the access code it generates to `<data_dir>/.env`.
At boot the app prefers that file over the compose/supplied
`PW_API_TOKEN` environment value when both exist and differ, so the
credential a human created survives a container restart. To return
authority to a rotated compose token, delete `<data_dir>/.env` and
restart — a deliberate, visible act. If the file is unreadable or
carries no `PW_API_TOKEN` line, boot leaves the environment untouched
(it fails toward the deployment token, never toward lockout).
Native Vault needs `uv sync --frozen --extra test --extra crypto` for encrypted
storage in a local install. The Dockerfile already installs the crypto extra.
Without it the vault fails closed — `unlock` reports `unavailable`, no secret is
stored, and status reports encryption unavailable. There is no base64 fallback.

### Frontend serving (rebuild-only since 2026-09-22)

The **React rebuild** is the product frontend, served same-origin at `/`
by `station_ui.app_router` from the staged build
(`src/personal_world/static/app/`, produced by the image's node stage or
`scripts/build-app.sh`). `/login` and `/setup` are server-rendered
(`login_page.py` / `setup_wizard.py`). The retired vanilla Station and
the `/vnext` side-by-side are gone: `/station*` and `/vnext*` only
redirect to `/`.

The former vanilla Station (`design/opendesign-exploration/station/`) and
its `/station` router were retired 2026-09-22: not served, not packaged,
removed from the tree (git history preserves them). Unknown document
paths serve the interface shell (client-side routing owns them); unknown
paths under reserved namespaces (`/api`, `/static`, asset routes) answer
JSON `404`. A stray `PW_FRONTEND`/`PW_STATION_DIST` value in the
environment is inert.

## Sign-in with your own SSO (OIDC)

Local token auth is the built-in default and keeps working unchanged when
OIDC is absent. To sign in through **your own** identity provider
(Authelia, Keycloak, Authentik, Zitadel, …), write `oidc.json` into your
private config directory (`PW_CONFIG_DIR`):

```bash
cp config/oidc.example.json "$PW_CONFIG_DIR/oidc.json"   # then edit it
export OIDC_CLIENT_SECRET='…'                            # never in the file
```

The file holds only non-secret wiring — `issuer`, `client_id`,
`client_secret_env`, `scopes`, `display_name`. The client secret is read
exclusively from the environment variable that `client_secret_env` names,
at request time; it is never stored, logged, or returned by an endpoint.
Register `https://<your-host>/api/auth/oidc/callback` with the provider
(and run uvicorn with `--proxy-headers` behind a reverse proxy, so the
redirect URI matches).

`GET /api/auth/oidc/status` reports the real state:
`not_configured`, `configured`, `unreachable`, or `misconfigured` — plus
provider discovery metadata and the *name* of the secret variable with a
boolean saying whether it is set. It never returns a secret value, and it
caches discovery (success and failure) so an anonymous caller cannot use
it to probe your IdP. Sign-in is authorization-code + PKCE (S256) with a
signed, expiring state cookie; the `id_token` signature is verified
against the provider's JWKS and its `iss`/`aud`/`exp`/`nonce` claims are
validated before the subject is mapped onto a local principal. Tokens are
verified and discarded, never stored.

RS256/384/512 verify with the standard library alone; other algorithms
need the `cryptography` extra (`uv sync --extra crypto`, already present
in the container image). An algorithm this install cannot verify is
refused, not accepted unverified.

Step-up is unchanged by SSO: an OIDC sign-in does not mint a step-up
grant. Full field reference, error codes, provider examples, limits and
troubleshooting: [docs/oidc.md](oidc.md).

## Containers

The provided Compose file is the portable appliance: it pulls the published
GHCR image and persists state in a Docker volume. No source tree, no homelab
checkout, no Kilo auth file, and no WSL paths are required to boot.

```bash
export PW_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose pull
docker compose up -d
docker compose ps
```

Then open `http://127.0.0.1:8000/`. A local-only setup should bind to
`127.0.0.1` instead of `0.0.0.0`; remote use needs TLS, access controls, and a
reviewed authentication setup — these are deployment choices, not defaults in
the tracked Compose.

### Image tags

| Tag | Source | Use |
| --- | --- | --- |
| `ghcr.io/rylee-bee/personal-world:latest` | Each successful main publish | Convenience tag for fresh installs |
| `ghcr.io/rylee-bee/personal-world:sha-<full SHA>` | Same publish | Immutable; preferred for reproducible deploys and rollback. Exists only for commits that built an image |

Pin `latest` for ordinary use. Pin a `sha-...` tag when you need a
reproducible deployment or want to roll back to a known-good image.

The image is built only when something that goes into it changed (docs,
tests and CI-only merges skip the build), so most commits have no `sha-...`
tag. Take the SHA from a commit that did publish: the running image reports
its commit in `GET /healthz` (`commit`, short form) and in its
`org.opencontainers.image.revision` label (full SHA); the package's tag
list on GHCR shows every `sha-...` tag that exists.

### Rollback

```bash
PW_IMAGE=ghcr.io/rylee-bee/personal-world:sha-<known-good> \
    docker compose up -d
```

Or set `PW_IMAGE` in `.env` and `docker compose up -d`. No separate rollback
machinery is needed.

### Local development (build from source)

The portable base only ever pulls. To iterate against the Dockerfile and
the live code without a GHCR push, use the dev override:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

The dev override sets `build: .`, `image: personal-world:dev`, and
`pull_policy: never` — it never reaches GHCR. Developers do not need to
edit the production Compose file.

### Production deployment (the transcode host)

Production Worlds runs on the **transcode host** (a LAN machine) as a docker compose stack at
`/opt/personal-world`, serving the owner's Worlds hostname through homelab Traefik (the `world` router: the `secure`
headers middleware, no Authelia forward-auth). The name is LAN/VPN only, never port-forwarded: that network layer
is the gate while the front door is built (Rylee, 2026-10-08).

Since the front-door rebuild (#277) the image runs the front-door app (`worlds.production:app_from_env`). It needs:

- **`/config/owner.yaml`** in the `config-data` volume: `public_origin` (the Worlds URL) plus `oidc` (issuer and
  the owner's subject) and/or `bootstrap` (`enabled: true`, `secret_ref: env:PW_BOOTSTRAP_TOKEN`). Without a valid
  file nobody can sign in, and every route answers `400 invalid host`.
- **`.env`** (mode 600), names only here:
  - `PW_API_TOKEN`: the image's boot guard still refuses an empty one.
  - `PW_BOOTSTRAP_TOKEN`: when bootstrap sign-in is on.
  - `PW_VAPID_PRIVATE_KEY` and `PW_VAPID_SUBJECT`: Web Push.
  - `PW_TRUSTED_PROXIES`: Traefik's address.
  - `PW_PORT`.
  - `PW_IMAGE`, pinned to `ghcr.io/rylee-bee/personal-world:sha-<full sha>`. The compose default is `:latest`
    with `pull_policy: always`, so an unpinned `docker compose up -d` moves production to whatever `main` is.

Images are built by the GitHub Actions `publish-image` workflow on `main`
and pushed to `ghcr.io/rylee-bee/personal-world`; production pulls them:

```bash
cd /opt/personal-world
docker compose pull && docker compose up -d
```

Updates are normally one tap: Project Home's "What's live" panel shows the
running vs latest commit and can create an ask-first deploy task. After
approval, the Project Home host deployer (runs every 2 minutes) runs the
app's deploy command — which backs up data, tags the old image
`personal-world:pre-<stamp>` for rollback, pulls, restarts, and waits for
healthy.

Secrets and env live only in `/opt/personal-world/.env` (mode 600) and the `config-data` volume. The VAPID
private key and every token are never stored in this repository or returned by an API. This repo records names
only, never values.

### Optional homelab enrichment

The portable base does not bind any host paths. On the homelab developer
host that has the kilo2/homelab checkout and a Kilo auth file, opt in
with the homelab override (read-only binds, no other changes):

```bash
docker compose -f compose.yaml -f compose.homelab.yaml up -d
```

Outside that host, do not use this override. Both bind paths in it are
machine-specific and intentionally non-portable.

### Bumping the pins

Two kinds of input are pinned by content, not by a moving name:

- **Base images** in `Dockerfile` (`node:24-slim`, `python:3.12-slim-bookworm`)
  carry an `@sha256:` digest. To bump: read the new index digest from the
  registry for the same tag (`docker buildx imagetools inspect <tag>` or the
  registry's `Docker-Content-Digest` header), replace the digest in both
  `FROM` lines, build the image, and check it starts.
- **Shared CI workflows** (`Rylee-Bee/ci-harness/...@<40-hex SHA>` in
  `validate.yml` and `uat-live.yml`). To bump: pick the new `ci-harness`
  commit (`gh api repos/Rylee-Bee/ci-harness/commits/main --jq .sha`), read its
  diff, and replace the SHA in every `uses:` line in one commit.

`tests/test_dockerfile.py` fails if a `FROM` line or a shared workflow loses its
pin. Image builds also record build provenance (`provenance: true`).

## Health, failures and state

`GET /healthz` is a public health endpoint returning
`{"ok", "auth_configured", "setup_needed", "dev_bypass", "commit"}`
(`commit` is the build's short SHA, null when unknown); successful protected API
access is a separate check. The container refuses startup with an empty token.
Docker health status alone does not restart an unhealthy running container.

Unavailable providers must report `unavailable` while core capabilities remain
usable. Missing providers are `not_configured`, not falsely healthy. The daily
loop is on request. A separate reminder scheduler now runs with the API process;
it does not turn the daily loop into a scheduled job.

Back up the config and data volumes securely before deployment changes. Durable
state is the config files and the Memory database `$PW_DATA_DIR/worlds.db`; the
cache is disposable. The in-app Memory backup is `POST /api/memory/backup` (a
dated `worlds-*.db` copy under `$PW_DATA_DIR/backups/`). See
[docs/rebuild/DURABILITY.md](rebuild/DURABILITY.md) for what to back up and how
to restore it. Do not put backups, journal exports or diagnostic dumps in this
public repo.

## Chat (optional local AI)

The Chat surface is a provider-neutral conversation over a read-only
world snapshot. With no chat provider configured the capability reports
`not_configured` and every other surface works unchanged; an unreachable
model shows an inline error, never a fake reply.

Wire a provider in your **private** runtime config
(`config.local/connections.json`). The tracked `config/connections.json`
ships only a local-ollama example; never put real endpoints or credentials
in the tracked copy:

```json
{
  "$schema": "personal-world/connections/1",
  "connections": [
    {
      "type": "ollama",
      "name": "local-qwen",
      "capability": "reasoning",
      "base_url": "http://127.0.0.1:11434",
      "model": "qwen3:8b",
      "timeout": 300
    }
  ]
}
```

`type` is `ollama` (Ollama's native `/api/chat`) or `openai_compat` (any
OpenAI-compatible `/v1/chat/completions` endpoint — llama.cpp server,
LiteLLM, vLLM). API keys for remote endpoints use env indirection:
`"api_key_env": "MY_KEY_ENV"` (see the framework secret rule; the
provider never reads the value into settings or exports). `timeout` is
seconds; generous values suit CPU-only inference where a cold 8B model
load can take minutes.

The model observes a trimmed text snapshot of your world (capability
statuses, actors, intents, policies, world-classified lore, recent
journal events, source-repository summaries) plus the last six chat
turns. Private-class lore and secret material are never included.

Read tools execute directly (inspect world status, search journal, check
lab health, etc.). Write requests create bounded proposals that require
approval before execution. Step-up auth gates consequential actions (300s
window). Execution evidence is recorded. The brain does not receive
arbitrary shell access.

## Updates and validation

Fetch and review upstream changes in a clean deployment checkout. Preserve local
config and state; do not overwrite them with repository examples. Review migrations
and take a backup before rebuilding. Never embed repository credentials in images
or remote URLs.

```bash
uv run pytest --timeout=30
uv run personal-world framework validate --json
```

These are local checks. Verify authentication, health, provider behavior and
backup recovery in the actual deployment before treating an update as accepted.

## Rebuild: sign-in behind a reverse proxy (2026-10-01)

Run the rebuilt app with `uvicorn personal_world.worlds.production:app_from_env --factory` and set `PW_CONFIG_DIR` and `PW_DATA_DIR`.
Set `PW_TRUSTED_PROXIES` to the address of your reverse proxy (an IP or CIDR; comma-separated for several) so the sign-in rate limit
sees the real client. Without it every client behind the proxy shares one limit and Worlds logs a warning. Give uvicorn the same
address with `--forwarded-allow-ips` so it does not trust `X-Forwarded-*` from anywhere else. The bootstrap secret must be at least 32 hex or 22 base64url characters
(`python -c "import secrets;print(secrets.token_urlsafe(32))"`); a weaker one stops startup. The OIDC flow key and CSRF key live in `PW_DATA_DIR` (mode 0600), so several workers share them. Details: `docs/rebuild/CONTRACTS.md` C7.
