# Live-IdP (Authelia) integration test

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the opt-in live-Authelia OIDC harness (setup, env vars, teardown) · **Read this if:** you need to prove the OIDC code against a real provider, not the in-process stub.

**In short:** an opt-in harness that stands up a throwaway Authelia container and drives the real discovery → login → callback → session → logout flow through production code. It never runs in CI; without the env vars the test skips .

`tests/test_oidc.py` proves the OIDC relying party against an in-process
stub provider. This harness proves it against a **real** one: a
throwaway [Authelia](https://www.authelia.com/) container
(`compose.authelia-test.yaml`), exercised end to end — discovery →
authorize → IdP sign-in → callback → verified session → logout — through
the production code paths (real HTTP, real JWKS, real signature
verification).

It is **opt-in and never runs in CI**: without the environment below,
`tests/test_oidc_live.py` skips with an actionable reason.

## What it proves

- The provider's live discovery document parses, echoes the configured
  issuer, and advertises S256 PKCE.
- The live JWKS is fetched, and its signing algorithms are verifiable by
  this install.
- `GET /api/auth/oidc/status` reports `configured` against the real IdP,
  with the client secret represented by env-var **name** + presence
  boolean only — never its value.
- `GET /api/auth/oidc/login` redirects to the provider's real authorize
  endpoint with PKCE + state + nonce, and no credential in the URL.
- A real authorization code from a real login is exchanged, the
  `id_token` signature verifies against the live JWKS, and a
  `pw_session` with `auth_method: oidc` is minted (single mode →
  `primary`).
- Logout ends the local session and targets the provider's end-session
  endpoint.

The IdP login itself is driven headlessly over HTTP (Authelia's
first-factor API) — no browser needed. If a future IdP build stops
exposing that API, the interactive leg skips with a clear reason while
the discovery/JWKS/status/login-redirect legs still run.

## Secrets and topology

**Every secret comes from your environment. No secret is ever written to
a tracked file.** The generated Authelia config lives under
`build/authelia-test/` (gitignored, like `*.pem`) and renders the client
secret with Authelia's config templating — `{{ mustEnv
"PW_TEST_AUTHELIA_CLIENT_SECRET" }}`, enabled by
`X_AUTHELIA_CONFIG_FILTERS=template`. The compose file passes that
variable into the container from the host environment at `docker compose`
time, so even the generated config holds no client secret. (The throwaway user's password must be readable by Authelia's
file backend, so it lands in the generated, untracked, 0600 users
database — destroyed at teardown.) The container publishes on loopback
only, never the LAN. All credentials are throwaway.

| Variable | Required | Meaning |
|---|---|---|
| `PW_TEST_AUTHELIA=1` | yes | opt-in switch; without it the module skips |
| `PW_TEST_AUTHELIA_USER` | yes | login username for the throwaway IdP user |
| `PW_TEST_AUTHELIA_PASSWORD` | yes | that user's throwaway password |
| `PW_TEST_AUTHELIA_CLIENT_SECRET` | yes | OIDC client secret — env only, never in a tracked file |
| `PW_TEST_AUTHELIA_URL` | no | IdP base URL (default `http://localhost:9091`) |
| `PW_TEST_AUTHELIA_PORT` | no | host port the container publishes (default `9091`; keep consistent with `PW_TEST_AUTHELIA_URL`) |
| `PW_TEST_AUTHELIA_SESSION_SECRET` / `_STORAGE_KEY` / `_JWT_SECRET` | no | pin Authelia-internal secrets; freshly random per generation otherwise |

## Procedure

Prerequisites: Docker, `openssl`, and the repo dev environment
(`uv sync --extra test`). From the repo root:

```bash
# 1. Throwaway credentials — random, used once, destroyed at teardown.
export PW_TEST_AUTHELIA_USER=testuser
export PW_TEST_AUTHELIA_PASSWORD="$(openssl rand -hex 16)"
export PW_TEST_AUTHELIA_CLIENT_SECRET="$(openssl rand -hex 24)"

# 2. Generate the throwaway IdP config (writes build/authelia-test/config,
#    gitignored; needs the three variables above).
uv run python tests/test_oidc_live.py --write-authelia-config

# 3. Bring the IdP up (loopback only).
docker compose -f compose.authelia-test.yaml up -d --wait

# 4. Run the live harness.
PW_TEST_AUTHELIA=1 uv run pytest tests/test_oidc_live.py -q

# 5. Teardown: stop the container, delete everything it wrote.
docker compose -f compose.authelia-test.yaml down
rm -rf build/authelia-test
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Everything skips | `PW_TEST_AUTHELIA=1` and the three credential variables must be set in the *pytest* process. |
| `cannot reach the live IdP` | Container not up: `docker compose -f compose.authelia-test.yaml up -d --wait`, then `docker logs pw-authelia-test`. |
| `discovery issuer … does not match` | `PW_TEST_AUTHELIA_URL` and `PW_TEST_AUTHELIA_PORT` disagree; re-export both consistently and regenerate (step 2). |
| First-factor sign-in failed | The env credentials differ from the generated users database — re-run steps 1–3 with the same environment. |
| Port already in use | Set `PW_TEST_AUTHELIA_PORT` (and a matching `PW_TEST_AUTHELIA_URL`) before steps 2–4. |
| `oidc_identity_not_mapped` | The harness runs single mode; if you forced `PW_IDENTITY_MODE=multi`, the IdP user must match an existing enabled local user (see `docs/oidc.md`). |

Related truth: [`docs/oidc.md`](oidc.md) (provider-neutral OIDC wiring),
[`tests/test_oidc.py`](../tests/test_oidc.py) (hermetic stub suite),
[`compose.authelia-test.yaml`](../compose.authelia-test.yaml) (the
throwaway IdP), [`tests/test_oidc_live.py`](../tests/test_oidc_live.py)
(the harness and config generator).
