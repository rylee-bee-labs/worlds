# AUTH MATRIX — Worlds

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the authentication surface (`AUTH-*`, `API-*` rows) · **Read this if:** you need to know which credential or elevation a surface requires

**In short:** Every protected API surface and the credential it accepts — bearer token, browser session, OIDC, step-up, the loopback dev bypass, or the admin gate. The backend auth model is the single `require_auth` seam; this table maps each route onto it.

**Note (2026-09-26):** the `UI-*` IDs below name the retired 2026-09-22 SPA
(the deleted `frontend/` tree); the current interface is `ui/` (the Bridge is
home). The `AUTH-*` and `API-*` rows still resolve against the code, and the
rooms / briefing / crew / secrets rows are appended at the end of the table.

Legend: YES / NO / INDIRECT / N/A.

| Surface ID | None | Bearer | Session | OIDC | Step-up | Local/private bypass | Admin |
|---|---|---|---|---|---|---|---|
| API-001 GET /healthz | YES | NO | NO | NO | NO | N/A | NO |
| API-002 setup status/POST setup | YES (first-run only; 409 after marker) | NO | NO | NO | NO | N/A | NO |
| UI-010 SetupWizard | YES | NO | NO | NO | NO | N/A | NO |
| UI-011 LoginScreen | YES | NO (performs login) | NO (creates) | INDIRECT | NO | N/A | NO |
| AUTH-001 require_auth | NO | YES | YES (resolved via seam) | YES (via session) | NO | YES (loopback-only dev bypass) | NO |
| AUTH-002 session cookie | NO | NO | YES (feeds require_auth) | NO | NO | NO | NO |
| AUTH-003 OIDC | NO | INDIRECT (proves identity at callback) | YES (creates session) | YES (maps to Principal) | NO | NO | NO |
| AUTH-004 require_step_up | NO | YES | NO | NO | YES (session grant / header / true loopback) | YES (true loopback only) | NO |
| AUTH-005 loopback elevation | NO | YES (combined) | NO | NO | INDIRECT | YES (true loopback only) | NO |
| AUTH-006 boot-token reconciliation | NO | INDIRECT (env feeding) | NO | NO | NO | N/A | NO |
| AUTH-007 admin gate | NO | YES | NO | NO | INDIRECT (often combined) | NO | YES |
| API-003 /api/status | NO | YES | NO | NO | NO | NO | NO |
| API-004 /api/daily | NO | YES | NO | NO | NO | NO | NO |
| API-005..009 journal GET | NO | YES (+person) | NO | NO | NO | NO | NO |
| API-006 POST /api/journal | NO | YES (+person) | NO | NO | NO | NO | NO |
| API-007 supersede | NO | YES | NO | NO | YES | INDIRECT | NO |
| API-010..014 chat/tools/actors/manifest | NO | YES | NO | NO | NO | NO | NO |
| API-016 memory search | NO | YES | NO | NO | NO | NO | NO |
| API-017..020 connections reads | NO | YES | NO | NO | NO | NO | NO |
| API-021 connections writes | NO | YES | NO | NO | YES (in-handler) | INDIRECT | NO |
| API-022 native config save | NO | YES | NO | NO | YES (in-handler) | INDIRECT | NO |
| API-023/024 test/validate | NO | YES | NO | NO | NO | NO | NO |
| API-025..028 exports/backup | NO | YES | NO | NO | NO | NO | NO |
| API-029 updates read | NO | YES | NO | NO | NO | NO | NO |
| API-030 prefs GET | NO | YES (+person) | NO | NO | NO | NO | NO |
| API-030 prefs PUT | NO | YES | NO | NO | YES | INDIRECT | NO |
| API-032 sections GET/PUT | NO | YES (+person) | NO | NO | YES (PUT) | INDIRECT | NO |
| API-033/034/036 source-control reads | NO | YES | NO | NO | NO | NO | NO |
| API-035 refresh (propose→approve→act) | NO | YES | NO | NO | YES | INDIRECT | NO |
| API-037..048 lab surfaces | NO | YES | NO | NO | NO | NO | NO |
| API-053..057 media | NO | YES | NO | NO | NO | NO | NO |
| API-058..060 reconciler | NO | YES | NO | NO | NO | NO | NO |
| API-061..063 vault status/unlock/lock/names/set | NO | YES | NO | NO | NO (documented divergence — not step-up) | NO | NO |
| API-064 vault GET value | NO | YES | NO | NO | NO | YES (loopback OR private peer — doc text says loopback-only) | NO |
| API-066 apps GET/PUT | NO | YES | NO | NO | YES (PUT) | INDIRECT | NO |
| API-067 reminders GET/POST/PATCH/DELETE | NO | YES | NO | NO | YES (writes) | INDIRECT | NO |
| API-068..070 identity users | NO | YES | NO | NO | YES (writes) | INDIRECT | YES (all three) |
| API-071..072 identity agents | NO | YES (+ownership) | NO | NO | YES (writes) | INDIRECT | INDIRECT (admins see all) |
| API-073/074 principal | NO | YES (+person for PUT) | NO | NO | YES (PUT) | NO | NO |
| API-075..077 world writes | NO | YES | NO | NO | YES | INDIRECT | NO |
| API-078..079 ingress/projects | NO | YES | NO | NO | NO | NO | NO |
| AUTH-009 login/logout/session/step-up routes (`auth_routes.py`) | YES (login/logout/session) | NO | YES (session/step-up) | INDIRECT (oidc subset) | YES (POST /api/auth/step-up, credential-verified) | NO | NO |
| API-085 GET /api/briefing | NO | YES (+person) | INDIRECT (via seam) | INDIRECT | NO | NO | NO |
| API-088 GET /api/rooms; POST /api/rooms/{id}/visit | NO | YES (+person) | INDIRECT | INDIRECT | NO | NO | NO |
| API-088-keeper / API-088-doorway PUT /api/rooms/{id}/(keeper\|doorway) | NO | YES (+person) | INDIRECT | INDIRECT | NO | NO | NO |
| API-089 GET/POST /api/crew; PATCH/DELETE /api/crew/{id} | NO | YES (+person) | INDIRECT | INDIRECT | NO | NO | NO |
| API-090 GET /api/secrets/overview (Workshop room) | NO | YES | INDIRECT | INDIRECT | NO | NO | **YES (admin only; 403 for other people)** |
| (uncurated) /api/setup-wizard/{state,provision,crew,companion,…} | YES (first-run only) | NO | NO | NO | NO | NO | NO |

> Rows above with "INDIRECT (via seam)" mean the request still passes through
> `require_auth`; a browser session resolves to one `Principal` exactly as a
> bearer token does (see the key observations below). `/api/secrets/overview`
> is the only row with an in-handler **admin** gate: names and health, never a
> value, and only the bootstrap principal `primary` or a person with the `admin`
> scope at that.

Key observations (D1/D2 convergence, 2026-09-15):

- `require_auth` is the single credential seam. Bearer, browser session
  (`pw_session`, local or OIDC), and the explicit loopback development
  bypass all resolve to exactly one `Principal` on
  `request.state.principal`. Precedence is documented: dev bypass →
  explicit bearer → session cookie → fail closed (503 with no store,
  401 otherwise). A session re-resolves against the current enabled
  identity records, so disabling a user revokes their session like
  their token.
- OIDC maps through `resolve_oidc_principal`: single mode → the
  bootstrap primary person; multi mode requires an existing enabled
  local record (an unmapped IdP identity never mints an account).
- Step-up (AUTH-004) is one seam with three ordered mechanisms: a
  time-bounded, principal-bound session grant minted by
  `POST /api/auth/step-up` after re-presenting a credential
  (canonical); true loopback (documented local-owner exception, RFC1918
  LAN addresses do NOT qualify); and `X-PW-StepUp: 1` (delegated
  proxy/transitional client — honored only when the request also
  carries `X-PW-Proxy-StepUp-Secret` matching `PW_PROXY_STEPUP_SECRET`;
  fail closed when unset or wrong). Step-up is person-only: an agent
  principal is refused with `step-up is person-only`.
- The session grant (AUTH-008) is now consumed by `require_step_up` and
  bound to the authenticated principal; it cannot be spent across
  identities.
- Vault value GET (API-064) still accepts loopback OR Python-classified
  private addresses despite "loopback-only" error text (unchanged by
  this pass; recorded boundary).
- Admin gate (AUTH-007) applies only to identity user/agent
  administration routes.
- **Identity modes (2026-09-26):** `PW_IDENTITY_MODE` is `single` (default) or
  `multi`. In `single`, the API bearer token `PW_API_TOKEN` maps to the bootstrap
  principal `primary`. In `multi`, each person is a principal and per-person data
  lives under `identity.principal_scoped_path` (`data/users/<id>/…`); a person is
  an admin if they are `primary` or hold the `admin` scope. See
  `docs/IDENTITY-BOUNDARY.md`.
- **Per-person rooms (#103):** for a registry row with `forward_principal: true`
  and a token, Worlds sends `X-Worlds-Principal: <principal id>` alongside the
  room's own bearer token — cards and needs are then cached per person. Worlds
  never forwards the human's session token to a room.

Source of truth: this matrix summarises `require_auth`/`require_step_up` in
`src/personal_world/api.py` and `src/personal_world/auth_routes.py`, and the
curated rows in `src/personal_world/api_manifest.py`; the code wins.