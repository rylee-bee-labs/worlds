# Authelia client for Worlds (paste into YOUR homelab Authelia)

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the Authelia OIDC client configuration Worlds signs in against · **Read this if:** you are wiring Authelia as Worlds' identity provider.

**In short:** the Authelia client block to paste into your own Authelia config, plus the matching `config/oidc.json` on the Worlds side. Authelia is an **identity provider** here (Worlds owns its own auth and session); it is not a forward-auth proxy in front of Worlds. No secret value lives in this repo — `<GENERATE>` is a placeholder you fill from your own secret store.

*No secrets are stored in this repo. `<GENERATE>` means: generate a long random string
in your homelab secret store, then put the SAME value in Worlds' env as
`OIDC_CLIENT_SECRET`. Never commit either copy.*

Add this under `identity_providers.oidc.clients:` in your Authelia config
(e.g. `homelab/services/settings-reconciler/desired/authelia.yml` or
`homelab/authelia/configuration.yml`, whichever your reconciler owns):

```yaml
      - client_id: "project-worlds"
        client_name: "Worlds"
        # Confidential client: Worlds authenticates with HTTP Basic.
        client_secret: "<GENERATE>"          # Authelia-side copy (your secret store)
        authorization_policy: "two_factor"    # or one_factor if you prefer
        scopes:
          - "openid"
          - "profile"
          - "email"
        redirect_uris:
          - "https://<your-worlds-host>/api/auth/oidc/callback"
          - "http://127.0.0.1:8000/api/auth/oidc/callback"   # loopback dev only
        userinfo_signed_response_alg: "none"
```

Then, on the Worlds side:
1. `config/oidc.json` (the setup wizard can write this for you):
   ```json
   {
     "issuer": "https://auth.example.invalid",
     "client_id": "project-worlds",
     "client_secret_env": "OIDC_CLIENT_SECRET",
     "scopes": ["openid", "profile", "email"],
     "display_name": "Home SSO"
   }
   ```
2. Export the same generated secret as `OIDC_CLIENT_SECRET` in the compose env
   (or `.env`, which is git-ignored): `OIDC_CLIENT_SECRET=<GENERATE>`.
3. Restart both. Check `GET /api/auth/oidc/status` → `configured`, then sign in.

Notes:
- The issuer hostname above is YOUR private topology; it belongs in your
  homelab/private config, never in the public Worlds repo.
- PKCE is always used by Worlds; with a client secret present it also
  sends Basic auth at the token endpoint (standard base64).
- Loopback redirect is for on-box development only; drop it for LAN/public use
  and rely on TLS.
