# OIDC sign-in (provider-neutral SSO)

> **Status:** Reference · **Verified:** 2026-09-29 · **Canonical for:** OIDC/SSO wiring — config file, routes, flow, error codes, limits · **Read this if:** you want to sign in through your own identity provider (Authelia, Keycloak, Authentik, …).

**In short:** Worlds ships local token auth by default and can also sign people in through any conformant OIDC provider. This page is the operational reference for the wiring — the `oidc.json` config, the authorization-code + PKCE flow, the status states it reports, and what is deliberately not implemented.

Worlds is self-hosted and universal: you point it at **your own**
identity provider.
[Authelia](https://www.authelia.com/) is the reference provider in the
wild, but nothing here is Authelia-specific — every endpoint is read from
the provider's own discovery document, so any conformant OIDC IdP works
(Keycloak, Authentik, Zitadel, Okta, Entra ID, a small `oauth2-proxy`,
…).

Code: [`src/personal_world/oidc.py`](../src/personal_world/oidc.py)
(discovery, PKCE, id_token verification) and
[`src/personal_world/auth_routes.py`](../src/personal_world/auth_routes.py)
(the HTTP flow). Architecture and the identity seam:
[ARCHITECTURE.md](ARCHITECTURE.md#auth).

## When OIDC is absent

Nothing changes. Local bearer/session auth is the built-in default, and
`config/oidc.json` not existing is a healthy state reported as
`not_configured` — never an error, never a degraded world.

## Configuration

Copy [`config/oidc.example.json`](../config/oidc.example.json) into your
**private** config directory (`PW_CONFIG_DIR`, e.g. `config.local/`) as
`oidc.json`. The tracked example stays generic; your issuer is your
topology.

The file is deliberately comment-free: it is parsed as strict JSON by
every reader, and an extra key would make a reader that does not know it
drop the whole file silently. The annotated version:

```jsonc
{
  // The provider's issuer URL, exactly as it publishes it in
  // `iss` — base URL only, no path, no trailing slash.
  // Authelia: the URL users sign in at, e.g. https://auth.example.com.
  "issuer": "https://auth.example.com",

  // The client id you registered in the provider for this app.
  "client_id": "project-worlds",

  // The NAME of the environment variable that holds the client secret —
  // never the secret itself. Read at request time only; never written to
  // disk, logs, exports or API responses. Omit the key entirely for a
  // public client (PKCE-only), which Authelia also supports.
  "client_secret_env": "OIDC_CLIENT_SECRET",

  // Must include "openid". "profile" and "email" only add display
  // details; they are never authorization.
  "scopes": ["openid", "profile", "email"],

  // What the sign-in button says. Cosmetic.
  "display_name": "Home SSO"
}
```

Unknown keys are ignored with a warning; keys starting with `_` are
treated as documentation and skipped silently.

### Where the secret lives

Only in the environment, under the name `client_secret_env` gives:

```bash
export OIDC_CLIENT_SECRET='…'      # shell / systemd / compose env_file
```

- The value is read on each token exchange and never cached on an object.
- It is never logged. A provider error is surfaced as the provider's own
  `error` code, not as a dump of the request that carried the secret.
- It never appears in a redirect URL (front channel) — only in the
  back-channel token POST.
- `GET /api/auth/oidc/status` reports the variable **name** and a boolean
  `client_secret_present`. It never reports the value.

### Provider-side registration

Register this redirect URI with your IdP:

```
https://<your-worlds-host>/api/auth/oidc/callback
```

Authelia example (validated against Authelia 4.39; client policy
`one_factor` or `two_factor` as you prefer):

```yaml
identity_providers:
  oidc:
    clients:
      - client_id: project-worlds
        client_name: Worlds
        # Store only a PBKDF2 hash here; the plaintext lives in Project
        # Worlds' env. Generate it with:
        #   authelia crypto hash generate pbkdf2 --variant sha512 --password '<secret>'
        client_secret: "$pbkdf2-sha512$310000$…$…"
        authorization_policy: one_factor        # a passkey satisfies this
        require_pkce: true
        pkce_challenge_method: "S256"
        authorization_signed_response_alg: "RS256"
        id_token_signed_response_alg: "RS256"
        redirect_uris:
          - "https://<your-worlds-host>/api/auth/oidc/callback"
        scopes: ["openid", "profile", "email", "groups", "offline_access"]
        grant_types: ["authorization_code", "refresh_token"]
        response_types: ["code"]
        token_endpoint_auth_method: "client_secret_post"
        consent_mode: "implicit"
```

> **Passkey-first.** With Authelia's `webauthn.enable_passkey_login: true`,
> a registered passkey is the primary credential, so this client turns into
> a one-tap sign-in and the password is only the break-glass path. Project
> Worlds offers OIDC as the primary action on `/login` whenever
> `/api/auth/oidc/status` reports `configured`.
>
> `token_endpoint_auth_method` must match what Worlds negotiates
> from the provider's discovery document — it uses `client_secret_post`
> whenever the provider advertises it (Authelia does).

Behind a reverse proxy, the callback URI is derived from the request's
own base URL, so run uvicorn with `--proxy-headers` (or set the external
URL in your proxy) — otherwise the `redirect_uri` sent to the IdP will
not match the one you registered and the provider will refuse the login.

## The flow

Authorization code + PKCE (S256), no implicit flow, no token in a URL:

1. `GET /api/auth/oidc/login` → discover the provider's
   `authorization_endpoint`, then redirect there with `response_type=code`,
   `client_id`, `scope`, `redirect_uri`, `state`, `nonce`,
   `code_challenge` (S256).
2. The in-flight attempt (`state`, PKCE verifier, `nonce`, exact
   `redirect_uri`) is stored in a **signed HttpOnly `pw_oidc_state`
   cookie** — not in the database, and it expires in ten minutes. The
   signature key is per-process, so a restart ends in-flight
   logins rather than trusting a stale cookie.
3. The person authenticates at the provider (their MFA, their policy —
   Worlds never sees a password).
4. `GET /api/auth/oidc/callback` → check `state` against the signed
   cookie → exchange the code with the PKCE verifier and client
   credentials → **verify the `id_token` signature against the provider's
   JWKS** → validate `iss`, `aud` (+`azp`), `exp`, `nbf`, `iat`, `nonce`,
   `sub` → hand the verified `sub` to
   [`identity.py`](../src/personal_world/identity.py).
5. `identity.py` maps the subject onto a local `Principal` and
   `auth.py` mints the ordinary `pw_session`. There is no second session
   model: an OIDC session and a local session are the same credential at
   the API boundary.

Identity mapping is deliberately conservative:

- **single mode** (default): the one person that install has. A verified
  external identity signs in as that owner.
- **multi mode**: the subject must already match an **existing enabled**
  local record. An unmapped IdP identity gets `403`
  (`oidc_identity_not_mapped`) — an external sign-in can never mint an
  account.

### Signature verification

RS256/RS384/RS512 verify with the standard library alone, so a minimal
install (`uv sync --extra test`) still has working SSO. With the
`cryptography` extra installed — the shipped container has it — PS*, ES*
and EdDSA also verify. An algorithm this install cannot verify is
**refused**, never accepted unverified; the reason is
`oidc_verification_unavailable` and the fix is `uv sync --extra crypto`.

No token is retained: the `id_token` and `access_token` are verified and
discarded. Sessions hold a principal id, not a credential.

## Routes

| Route | Purpose |
|---|---|
| `GET /api/auth/oidc/status` | Current state + discovery metadata, no secrets. Read-only. |
| `GET /api/auth/oidc/config` | Legacy alias of status, flattened for the login screen. |
| `GET /api/auth/oidc/login` | Start a sign-in (303 to the provider). |
| `GET /api/auth/oidc/step-up` | "Confirm it's you" by a fresh provider sign-in (for people with no sign-in key). |
| `POST /api/auth/oidc/link` | Link a provider sign-in to the signed-in person's account (multi mode). |
| `GET /api/auth/oidc/callback` | Finish a sign-in (303 to `/` on success). |
| `GET /api/auth/oidc/logout` | End the local session, then the provider session. |
| `POST /api/auth/logout` | End the local session; returns `end_session_url` for OIDC sessions. |

`status` and `config` are unauthenticated by necessity — they are read
before anyone can sign in — and therefore bounded: the provider is fixed
by the operator's own config (never by a caller), and discovery results
are cached for 5 minutes (failures for 60 seconds) so an anonymous
visitor cannot turn the endpoint into a probe loop against your IdP.

### `GET /api/auth/oidc/status`

```jsonc
{
  "ok": true,
  "status": "configured",          // the four states below
  "warnings": [],                  // human-readable, actionable
  "data": {
    "status": "configured",
    "login_available": true,
    "issuer": "https://auth.example.com",
    "client_id": "project-worlds",
    "client_secret_env": "OIDC_CLIENT_SECRET",
    "client_secret_present": true,   // name + boolean, never the value
    "client_authentication": "client_secret_post",
    "scopes": ["openid", "profile", "email"],
    "display_name": "Home SSO",
    "pkce": "S256",
    "signature_verification": {"available": true, "backend": "cryptography",
                               "algorithms": ["RS256", "…"]},
    "discovery": { "authorization_endpoint": "…", "token_endpoint": "…",
                   "jwks_uri": "…", "end_session_endpoint": "…",
                   "scopes_supported": ["…"], "checked_at": 1760000000.0 }
  }
}
```

Four states, never blended optimistically:

| `status` | Meaning | Typical cause |
|---|---|---|
| `not_configured` | No `oidc.json`. Healthy default; local auth is the whole story. | Fresh install |
| `configured` | Settings parse, the provider answered discovery, and this install can verify what it advertises. `login_available: true`. | Working SSO |
| `unreachable` | Settings parse, the provider did not answer (DNS, TLS, timeout, 5xx). Config may be fine. | IdP down, wrong network, firewall |
| `misconfigured` | Settings unusable, discovery contradicts them, or the provider needs something this install lacks. Operator action required. | See below |

`misconfigured` covers, with a specific reason each time: invalid JSON;
missing `issuer`/`client_id`; `scopes` without `openid`; a non-absolute
issuer; a 404 discovery document (wrong issuer URL); a discovery
`issuer` that does not match the configured one; a missing required
endpoint; a required client secret whose env var is unset; and a
provider that only advertises signing algorithms this install cannot
verify.

`data.detail` carries the reason; `data.discovery_stale: true` marks
metadata that came from cache after a failed re-probe, so an old answer
is never mistaken for a live one.

### Failure presentation

Browser navigations degrade to `303 /login?pw_auth_error=<code>` (the SPA
presents it; the server does not render pages). API callers that send
`Accept: application/json` get `{"ok": false, "status", "error_code",
"detail"}` with the matching HTTP status. Codes are short and secret-free:
`oidc_not_configured`, `oidc_misconfigured`, `oidc_unreachable`,
`oidc_state_mismatch`, `oidc_state_invalid`, `oidc_attempt_expired`,
`oidc_missing_state`, `oidc_provider_denied`,
`oidc_token_exchange_failed`, `oidc_no_id_token`, `oidc_bad_signature`,
`oidc_key_not_found`, `oidc_alg_unsupported`,
`oidc_verification_unavailable`, `oidc_bad_issuer`, `oidc_bad_audience`,
`oidc_token_expired`, `oidc_bad_nonce`, `oidc_identity_not_mapped`.

## Confirm it's you without a sign-in key

Some changes ask the person to confirm it's them (step-up). People who
sign in only through the provider have no sign-in key to type, so they
confirm by signing in to the provider again:
`GET /api/auth/oidc/step-up?return_to=/path` sends them to the provider
with `prompt=login` and `max_age=0`. The callback grants the usual
5-minute window only if the provider reports a sign-in in the last two
minutes (`auth_time`) by the same person, then returns to `return_to`
(a path on this site; anything else goes to `/`).
`GET /api/auth/session` lists `step_up_methods` (`key`, `sso`) so the
page offers the right button.

## Linking a sign-in to an account (multi mode)

In multi mode a provider sign-in works only for an account it is linked
to; Worlds never creates an account from a sign-in. To link one:

1. Sign in the local way and confirm it's you (step-up).
2. `POST /api/auth/oidc/link` from the Worlds page. It sends you to the
   provider.
3. Sign in there. On the way back Worlds links that provider identity
   (its `sub`) to your account, then signs you in with it.

The link is refused if you were signed out in between, or if that
provider identity is already linked to someone else. The owner links
their own sign-in this way before switching an install to multi mode.

## Logout

`GET /api/auth/oidc/logout` always invalidates the local session first,
then redirects to the provider's `end_session_endpoint` when it
advertises one (RP-initiated logout, with `post_logout_redirect_uri`).
If the provider is unreachable, or advertises no end-session endpoint,
you still get a logged-out local session and a redirect to `/login`.

Because no `id_token` is retained, no `id_token_hint` is sent; some
providers then ask the person to confirm the logout. That is the
deliberate trade for never storing a credential we do not need.

## Current limits

- **Step-up has two paths.** An OIDC sign-in does not itself mint a step-up
  grant. `POST /api/auth/step-up` re-presents an application credential that
  resolves to the session's principal. For people with no sign-in key,
  `GET /api/auth/oidc/step-up` sends the browser through a fresh provider
  sign-in, and the callback grants the 5-minute step-up only when the same
  person signed in just now.
- **No group/claim → scope mapping.** `groups` is requested only as a
  display hint; authorization stays entirely local.
- **No id_token encryption (JWE)**, no `x5c`-only JWKS keys.
- **One provider.** The config shape is a single client, not a list.
- **No automatic account provisioning** (by design; see identity
  mapping above).

## Troubleshooting

| Symptom | First thing to check |
|---|---|
| `not_configured` though you wrote the file | Is it in `PW_CONFIG_DIR`? Named exactly `oidc.json`? The file is re-read when it changes, but the *directory* is fixed at boot. |
| `unreachable` | Can the container resolve and reach the issuer? Try `curl -sS <issuer>/.well-known/openid-configuration` from the same host. |
| `misconfigured: no discovery document` | `issuer` must be the base URL with no path and no trailing slash. |
| `misconfigured: discovery issuer … does not match` | Your `issuer` differs from what the provider publishes (scheme, host, port, or a path prefix). Copy the provider's `iss` verbatim. |
| Provider says `redirect_uri` mismatch | Register `https://<host>/api/auth/oidc/callback`; behind a proxy, enable `--proxy-headers`. |
| `oidc_state_mismatch` / `oidc_missing_state` | Cookies blocked, or the login was started in another browser/profile, or the process restarted mid-login. Start again. |
| `oidc_bad_nonce` | Clock skew beyond two minutes, or a replayed id_token. Sync time. |
| `oidc_verification_unavailable` | `uv sync --extra crypto` (the container image already includes it). |
| `oidc_identity_not_mapped` (multi mode) | Create/enable the local user whose id matches the provider subject. |
