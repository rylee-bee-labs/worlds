# Worlds Architecture

> **Superseded in part by [ADR-0008](adr/0008-front-door.md) (2026-10-01):** API-only `/api/lab/*` routes are no longer an off-limits product contract (S8), and the capability registry is retired for front-door providers (S6). Rewrite pending.

> **Status:** Current · **Verified:** 2026-09-29 · **Canonical for:** how Worlds is structured — world model, rooms, API surface, identity/auth, Vault, exports · **Read this if:** you need to know where something lives before changing it.

**In short:** how Worlds is put together: one small durable core (facts, intent, policy, lore, capabilities, journal, packs) surrounded by replaceable providers, plus **rooms** — separate services Worlds renders. It also covers the API surface, identity and auth, the Vault, the daily loop, and export contracts.

(Formerly "Personal World" — product renamed 2026-09-12; technical
identifiers unchanged. Historical docs may still use the old name.)

Stable truth. Replaceable machinery.

## The one idea

A personal control plane with a small durable core — schemas, observed
facts, intent, policies, lore, capability/provider registries, journal,
packs, export contracts — surrounded by replaceable providers that do
the actual work. The core never reimplements Git, GitHub, Komodo,
systemd, Docker, SOPS, OpenBao, OpenWebUI, LiteLLM, or any existing
tool. Those are providers behind adapters.

## World model

| Concept | Meaning | Mutated by AI? |
|---|---|---|
| Fact | Observed reality, with provenance | records, never invents |
| Intent | What the user wants true | never — explicit only |
| Policy | Hard rules (deny/allow), cementable | never — explicit user action only |
| Lore | Contextual meaning: confirmed / derived / suggested / ephemeral | suggests; never silently confirms |
| Capability | What the world can do (provider-neutral) | no |
| Provider | Concrete system mapped to a capability | no |
| Journal | One append-oriented event stream | records |
| Pack | Recipe: structure, never personal data | installs defaults only |

## Rooms (the core architecture)

A **room** is any service that serves the Play-Nice **ROOM** contract
`room/0` — `GET /room`, `/room/cards`, `/room/needs-you`, `/room/actions`,
`POST /room/actions/{id}` (idempotent, with `Idempotency-Key`). Worlds
renders rooms; it never copies another tool's code. Pin:
`.project/contracts/adoption.yaml`; app-side reader: `src/personal_world/rooms.py`.

- **Runtime registry (Gap 1).** Worlds reads the room list at runtime from
  Project Home `GET /api/rooms/registry` (`PW_ROOMS_REGISTRY_URL`), cached
  60 s with last-known-good persisted. `PW_ROOMS` is only a fallback. A room
  whose contract is not in `SUPPORTED_CONTRACTS` (`{"room/0"}`) shows as
  `incompatible`; one that does not answer shows as `unreachable` with its
  last-seen time, and one failing room never blanks the rest.
- **Tokens.** Each room's token is in Worlds' environment under a name
  like `PW_ROOM_WORKSHOP_TOKEN`; a registry row names that variable in
  `token_env` (must match `^PW_ROOM_[A-Z0-9_]+_TOKEN$`). Values live only in
  the host's `.env` (mode 600), never in git.
- **Cards and needs.** A card's `tone` (`good_news` | `update` |
  `when_ready`) is a display hint, never priority. A need's `link` is a
  same-origin path on the **room's** site; Worlds opens it in a new tab at
  the room's `public_url` (falling back to `base_url`), with no proxy — a
  proxy would hand every room Worlds' cookies.
- **Per-person rooms.** For a registry row with `forward_principal: true`
  and a token, Worlds sends `X-Worlds-Principal: <principal id>` alongside
  the room's bearer token; cards and needs are then fetched and cached per
  person (15 s, ≤64 people). Health stays estate-wide; background snapshots
  send no principal. Candy is the first per-person room.
- **Visits, keepers, doorways.** Room visits, need-seen state, keepers and
  doorways are Worlds-owned and per person (`/api/rooms/{id}/…`). A doorway
  is presentation only: a closed list of 13 ids (`study`, `archive`,
  `garden`, `kitchen`, `lounge`, `music`, `observatory`, `post`, `travel`,
  `vault`, `wellness`, `hallway`, `servers`; source of truth
  `crew.DOORWAYS`) with no defaults.
- **Secrets overview.** Worlds shows a read-only secrets section in the
  Workshop room's drawer, built on `GET /api/secrets/overview` (which reads
  Project Home `GET /api/secrets/summary` with the workshop room's token).
  Names and health only, never a value; admin-only.
- **Live rooms (2026-09-26):** Workshop (Project Home) and Studio on the
  workstation, Engine room (homelab `lab room serve`), and Candy (discovery),
  all reachable in production Worlds.

## The Bridge and the briefing

`/api/briefing` (contract `worlds-briefing/1`) is built from six fixed
systems — agents/Workshop, estate/Engine room, records/Archive,
interests/Observatory, news/Newsstand, threads/World tree. A configured room
whose id names a system (e.g. `workshop`, `engine-room`) is that system;
Newsstand is a `not_configured` placeholder. The **Bridge** is the
home screen (`ui/src/screens/Bridge/`): it shows the Keeper and the briefing,
the rooms as doorway cards, and remembers where you were.

## Durable memory and retrieval

Durable, human-readable files — especially Markdown — are preferred as
the canonical memory/lore truth where practical. They remain inspectable,
portable, versionable, and recoverable without a particular database or
provider.

Semantic-search indexes, vector stores, embedding stores, response caches,
and similar retrieval machinery are acceleration layers. They may be
implemented by replaceable providers and may be rebuilt from canonical
sources; they must not silently become the only authority for durable
memory. `/api/memory/search` is therefore a retrieval capability, not a
statement that the active memory provider owns the underlying truth.

## Security classification

- `world` — portable structured state (personal data, not public)
- `private` — personal context; stricter access and export rules
- `secret` — credential material; never enters model context, never
  serialized by any export; consumed only through the broker

Classification is field metadata in the model
(`src/personal_world/classification.py`), not folder boundaries.

## Security model

- The AI is not a security boundary. The dashboard is not a security
  boundary. Packs are not trusted because installed.
- Authorization happens before sensitive retrieval or action.
- `settings-export` is a **whitelist walk**: only fields marked
  `exportable` can ever serialize. Leakage tests insert fake names,
  emails, tokens, passwords, and private lore into every record class
  and prove they cannot appear (`tests/test_core.py::TestSettingsExportSafety`).
- Cemented policies reject every non-user mutation path: API, imports,
  packs, discovery, automation (`tests/test_core.py::TestCementedPolicy`).
- Secret handling has multiple explicit boundaries, described below. The broker
  path is not the only implemented secret path.

## Secrets: current implementation and target

`src/personal_world/vault.py` owns native `Vault`, backed by `vault.enc`,
and `VaultContract` (`get`, `set`, `delete`, `list_names`, `audit`). Native
Vault provides those operations; the API instantiates it directly once per app.
The UI unlocks with a master passphrase, lists names, and stores values without
redisplaying stored values. Locking clears decrypted in-memory state.

With the optional `cryptography` dependency installed
(`uv sync --frozen --extra crypto`), storage uses Fernet and a
PBKDF2-SHA256-derived key. The Dockerfile installs that extra. **Without
that dependency the vault fails closed:** `unlock` returns `unavailable`,
no secret is stored, and both `/api/vault/status` and `inspect_vault_status`
report `encrypted: false` with the vault's own warning. There is no base64
fallback. `_vault_status()` in `tool_registry.py` and `Vault.audit()` read
real Fernet state; neither hardcodes the claim.

`providers/adapters.py::SopsBroker` is a separate pipe-to-consumer path.
`vault.py::SOPSVaultAdapter` is an implemented read-through adapter; writes and
deletes return unsupported and remain SOPS operations. No OpenBao adapter or
UI-selectable backend replacement is implemented. SOPS/OpenBao remain replaceable
provider paths in the target architecture; connecting them must preserve the
native concept and secret boundary rather than replacing it with a vendor UI.

All HTTP Vault routes require bearer authentication. Unlock requires a passphrase;
list/get require an unlocked vault. `GET /api/vault/{name}` returns a value only
after a peer-address check and records its name in the journal. Despite its
"loopback-only" error text, the check also accepts addresses Python classifies
as private. `lock` and `unlock` use bearer auth only; `set` and `delete` also require
`require_step_up` on top of bearer auth. These are
current restrictions, not proof of finish-line re-authentication or per-user
Vault isolation. Never route retrieved values into model context or ordinary
exports/logs; secure retrieval is an explicit exceptional workflow.

## Auth

**Current implementation:** `require_auth` is the one place credentials are checked:
every accepted credential — bearer token, browser session (local or
OIDC), or the explicit loopback development bypass — resolves to exactly
one `Principal` on `request.state.principal` before handler code runs.
Precedence is documented: development bypass (opt-in, true loopback only)
→ explicit `Authorization: Bearer` → `pw_session` cookie → fail closed
(503 when no credential store is configured, 401 otherwise).
`identity.py` resolves a `Principal` with identity, owner, scopes,
authentication level, and source. A session re-resolves against the
current enabled identity records, so disabling a user revokes their
browser session exactly like their token. Default
`PW_IDENTITY_MODE=single` resolves the bootstrap primary person;
optional `multi` uses local hashed user/agent token records. OIDC maps a
verified subject through the same function: single mode → the bootstrap
primary person; multi mode requires an existing enabled local record, and
an unmapped IdP identity never mints an account. Provisioning routes and
selected per-user paths exist and resolve through one function
(`identity.principal_scoped_path`): world/journal/preferences/sections,
reminders, proposals, chat history, and interests are scoped to the
calling principal in multi mode, while the single-user default keeps
the legacy instance paths (see `docs/IDENTITY-BOUNDARY.md`). Apps,
Vault, the memory FTS index, and the instance status/daily surfaces
still use instance-level state; the foundation is not a complete
household isolation or SSO product.

`require_step_up` is one check with three mechanisms, tried in order:
a canonical, time-bounded, principal-bound session grant minted by
`POST /api/auth/step-up` after the caller re-presents a credential
(the instance token as a bearer header or in the body);
true loopback (127.0.0.1/::1 — a documented local-owner exception;
RFC1918 LAN addresses do not qualify); and `X-PW-StepUp: 1` (explicit
delegated proxy/transitional-client trust — honored only when the
request also carries `X-PW-Proxy-StepUp-Secret` matching
`PW_PROXY_STEPUP_SECRET`; fail closed when unset or wrong). Step-up
is a human elevation: an agent principal is refused (`step-up is person-only`).
It gates preference, Apps registry, identity provisioning, and
world-write routes. This is an implemented extra write check, **not
verified fresh authentication/MFA**; the OIDC-session step-up path
still requires the instance credential. External forward-auth may be a
deployment layer, but it does not replace application authorization.

**Finish-line target:** authentication works with any identity provider,
at the application boundary. A real SSO/identity provider may supply normal sign-in,
while Worlds retains its own authorization/ownership rules. The
finished path must support step-up authentication for severe/destructive
changes and sensitive vault/secure-note access, plus recoverable
bootstrap/break-glass access when an external identity provider is
unavailable. The boundary must not depend on Authelia specifically and
should remain suitable for future non-browser clients. `require_auth`
remains the single entry point unless implementation evidence justifies a
narrower refactor.

## API

One core, a FastAPI HTTP surface in `src/personal_world/api.py`, and a CLI
in `cli.py` sharing core modules. The CLI does not require an HTTP server.
The interface in `ui/` uses the API; future clients can use the same
boundary. `GET /api/manifest` carries the machine-readable route table
(curated in `api_manifest.py`). The following inventory reflects implemented
routes, not deployment acceptance:

| Route | Purpose |
|---|---|
| GET /healthz | Public liveness, auth_configured, setup_needed, commit (short SHA of the running build, or null) |
| GET /api/setup/status; POST /api/setup | Public first-run state/bootstrap; setup rejects repeats after the completion marker |
| GET /api/status | world summary + capability statuses |
| GET /api/briefing | the Bridge's briefing (`worlds-briefing/1`), six fixed systems |
| GET /api/rooms | the estate's rooms: descriptor, cards, needs, reachability, last-seen, status, public_url, plus the caller's visit/keeper/doorway state (snapshot cached 15 s) |
| POST /api/rooms/{room_id}/visit, /needs/{need_id}/seen; PUT /api/rooms/{room_id}/keeper, /doorway | per-person room state (visit, need-seen, keeper, doorway) |
| GET /api/secrets/overview | read-only secrets names + health for the Workshop room's drawer (admin-only) |
| GET/POST /api/crew; PATCH/DELETE /api/crew/{companion_id}; GET/POST/DELETE /api/crew/{companion_id}/portrait | per-person crew: companions and their portraits (keepers and doorways are set per room, below) |
| GET /api/setup-wizard/state, /crew; POST /api/setup-wizard/provision, /test-oidc, /auth-choice, /comfort, /companion, /finish | First Light first-run setup (`src/personal_world/setup_wizard.py`): sign-in choice, comfort settings, crew on/off, companion choice |
| GET /api/daily | present the daily digest (read-only; never mutates) |
| POST /api/daily | run the daily loop: journal observations, record facts, save |
| GET /api/journal | recent events |
| POST /api/journal | User note append |
| GET /api/journal/audit | audit-log rendering |
| GET /api/journal/last | the newest journal event (the Bridge thread card reads this, not the list order) |
| GET/POST /api/discovery/*; GET /api/media/* | discovery (Interests) and media, on native providers — being extracted to the **Candy** room and still present in Worlds today |
| GET /api/actors | staff-directory view |
| GET /api/manifest | Core capability/provider manifest (`data`) + the machine-readable endpoint manifest (`endpoints`: id, method, path, capability, kind, gate, auth, present — curated in `api_manifest.py`, verified against the live route table) |
| GET /api/memory/search | semantic recall via the memory provider |
| POST /api/chat; GET /api/chat/providers | Read-only world-snapshot conversation and reasoning-provider status |
| POST /api/chat/test | Provider probe (changes no local state); requires authentication, no elevation |
| GET /api/prefs; PUT /api/prefs (PATCH alias) | Read/save validated presentation preferences; writes use require_step_up. `companion_id` is validated against the caller's own crew (`GET /api/crew`) — unknown or hidden id → 422 |
| GET /api/apps; PUT /api/apps | Optional services launcher registry in data/apps.json; replacement is step-up gated and journaled |
| GET /api/source-control/status, /api/source-control/history, /api/source-control/enrichment | Native repository status/history and optional forge enrichment |
| GET /api/ingress/rollups | Optional ingress summary |
| GET /api/updates | Read-only update state, not a deploy action |
| GET /api/lab/state, /api/lab/settings, /api/lab/settings/inspect/{service}, /api/lab/settings/diff/{service} | Optional Lab state and configuration inspection |
| GET /api/lab/health, /api/lab/deploy, /api/lab/secrets, /api/lab/resources | Optional Lab read surfaces; secrets metadata, not resolved values |
| GET /api/vault/status, /api/vault/names, /api/vault/{name}; POST /api/vault/unlock, /api/vault/lock, /api/vault/set; DELETE /api/vault/{name} | Native Vault operations with the distinct restrictions above |
| GET /api/themes, /api/themes/{name} | Theme manifest registry reads; not full frontend pack integration |
| GET/POST /api/identity/users, /api/identity/agents, /api/identity/viewers (read-only credentials, owner only); DELETE /api/identity/users/{user_id}, /api/identity/agents/{agent_id}; GET /api/identity/principal | Local identity/owned-agent foundations; user administration is admin-gated, agent operations use ownership, and writes use step-up |
| POST /api/auth/login, /api/auth/logout, /api/auth/step-up; GET /api/auth/session, /api/auth/oidc/config, /api/auth/oidc/login, /api/auth/oidc/callback | Provider-neutral browser sign-in; local/OIDC sessions resolve to a canonical Principal, and step-up mints a time-bounded, credential-verified grant |
| GET /api/proposals, /api/proposals/{id}; POST /api/proposals/{id}/approve, /reject, /execute | Durable brain-write proposal lifecycle; server-held approval evidence persists to data/proposals.json and execution is step-up gated |
| GET/POST /api/reminders; PATCH/DELETE /api/reminders/{rid} | Persistent reminders and scheduler controls |
| POST /api/world/intent, /api/world/fact, /api/world/policy | Explicit step-up-gated world writes, not model tools |
| GET /api/exports/settings | safe blueprint |
| GET /api/exports/world | portable personal config |
| GET /api/exports/story | human-readable journal |
| GET /api/backup | World/journal payload (encrypt externally); not a complete data-directory backup |

**API-only routes (intentional).** `/api/lab/*`, `GET /api/exports/story` and
`GET /api/reconciler/status` have no screen. They are kept as the published
API-only "Lego box" contract: other tools and agents compose against them, and
removing one is a product decision, not cleanup.

Unless explicitly labeled public above, API routes use bearer auth directly or
through `require_step_up`; individual routes may add further restrictions.
`/setup-wizard`, `/setup`, `/login`, `/`, and packaged
fonts/icons/companions are browser entry/assets. `/` serves the React
interface (`ui/`, built into `static/app/` and mounted by
`station_ui.app_router` — the module name is from the retired Station
era; the home screen is the **Bridge**, labelled "Bridge" in the navigation
though its internal area id is still `overview`): first-run redirects to `/setup`, an unauthenticated
browser redirects to `/login`, and a valid `pw_session` cookie is sufficient —
which is why its API calls need no CORS and no browser-side token.
Only web assets from an allowlist built at boot are served; internal
`.md` notes and `_legacy/` never are. The server-rendered Station was
retired on 2026-09-22: `/station/*` and `/vnext` only redirect to `/`.
The five-step wizard collects welcome/name/companion/
access-token choices and finishes bootstrap; it is not the finish-line SSO or
capability/accessibility interview. `POST /api/setup` can initialize Vault too.
Review first-run exposure separately from normal protected API access.

### Known implementation/documentation boundaries

- The design preference schema includes motion choices beyond `reduced`, while
  `prefs.py` currently accepts only `reduced`. The default agrees; the full design
  schema is not a promise that every preference is writable today.
- Accessibility contract section 1.3 lists text statuses but omits `warning`,
  which exists in `status.py`. Treat that contract as requiring explicit labels,
  not as a replacement enum; provider status authority remains `status.py`.
- The registry merges `connections.local.json`, but the source-control rollup
  endpoint reads `connections.json` directly. Private override behavior is not
  uniform across all read surfaces. Configure privately and verify each surface.
- The tracked Compose has host-specific bind mounts despite its standalone
  description. Parsing/framework success does not establish portable deployment.
- The brain-write proposal store is durable (`data/proposals.json`). In
  multi-principal mode it is stored per principal
  (`_scoped_path(principal, "proposals")` in `api.py` — verified by
  `tests/test_identity_boundary.py`); in single mode (and background
  code paths with no principal) it remains instance-global. The approval
  evidence is server-held and persisted.
- Session step-up has two paths. `POST /api/auth/step-up` re-presents an
  application credential. `GET /api/auth/oidc/step-up` ("Confirm it's you")
  sends the browser through a fresh provider sign-in (`prompt=login`,
  `max_age=0`); the callback grants the 5-minute step-up only when the same
  person signed in within the last two minutes. An OIDC-only browser session
  therefore does not need the instance token to elevate.
  (`tests/test_oidc.py`, `fresh_sign_in_grants_step_up`.)

These gaps are recorded rather than changing implementation or weakening an
adopted contract during documentation reconciliation. Manual screen-reader,
deployed SSO, strong step-up, external Vault substitution, complete multi-user
isolation, and full-instance restore acceptance require separate evidence.

## Daily loop

OBSERVE → VALIDATE → RECONCILE → DISCOVER → POLICY → JOURNAL → PRESENT.
Deterministic. Correct with zero providers and no AI. The reasoning
capability is optional and replaceable (local model, cloud, or none).

## Provider substitution proof

`source_control` has two providers through one `SourceControlContract`:
a real forge adapter over an HTTP API and a deterministic fake
reference. Tests prove the registry transparently substitutes an
unavailable real provider with the fake
(`tests/test_core.py::TestProviderSubstitution`).

The supported remote enrichment for source control today is GitHub
(`providers/github.py` via the authenticated `gh` CLI, read-only).
The generic forge adapter in `adapters.py` remains as the
substitution-proof machinery; it is no longer a supported live
provider in the default deployment.

## Export contracts

| Command | Artifact | Contains | Never contains |
|---|---|---|---|
| settings-export | shareable blueprint | capabilities, providers, packs, policy defaults | facts, intent, lore, any personal data |
| world-export | portable personal config | intents, policies, world-classified lore | secrets, private lore |
| backup | World/journal recovery payload (encrypt with your SOPS/age) | serialized world and journal, including private state | not shareable; does not include all runtime files |
| story-export | human-readable journal | narrative events, disclosure-filtered | private events unless explicitly included |

`backup_payload` does not package `vault.enc`, identities, Apps registry,
reminders, per-user directories, or runtime configuration as a full instance
archive. A recovery plan must cover those separately and verify restoration.

## Lore states and the existing epistemic vocabulary

The lab already runs a de-facto epistemic taxonomy across three
systems — rylee_lore claim states (`candidate/accepted/superseded/
rejected/unknown`), rylee-context provenance triples (`source ×
confidence × status`), and VEFR's propose-validate-apply Spark
contract. Worlds' lore states (`confirmed/derived/suggested/
ephemeral`) align with all of them, and the shared promotion rule is
identical everywhere: **agents append evidence; only an explicit human
action promotes to canon.** The core's `MutationDenied` gate enforces
that rule structurally for every caller.

## Repository layout

Mirrors the conventions proven in the homelab monorepo: hatchling +
`src/` package, optional `test` dependency group, pinned image tags,
healthchecks on every container, env-indirected secrets, dry-run by
default, verdict-in-body JSON envelopes.

```text
src/personal_world/   core package
  model.py            world model (facts/intent/policy/lore/...)
  world.py            container + mutation gates
  classification.py   world/private/secret metadata
  journal.py          append-only event stream + renderers
  export.py           the four export contracts
  app.py              core capability definitions + provider wiring
  providers/          contracts, registry, adapters.py (forge HTTP/HTTP/fake/SOPS),
                      github.py (GitHub enrichment via gh CLI),
                      optional Lab and ingress enrichment adapters
  api.py              FastAPI + bearer auth + the JSON API behind the interface
  rooms.py            ROOM contract reader: runtime registry, cards, needs, visits
  briefing.py         the Bridge briefing (worlds-briefing/1), six fixed systems
  crew.py             per-person crew: companions, keepers, doorways
  cli.py              personal-world CLI (--json envelope)
  loop.py             the daily cycle
  status.py           canonical provider/capability statuses + ranking
  prefs.py            validated presentation preferences and CSS attributes
  chat.py             provider-neutral chat transport
  chat_context.py     read-only world snapshot for model context
  chat_registry.py    chat provider configuration helpers
  vault.py            native Vault, VaultContract, read-through SOPS adapter
  identity.py         principal resolution + local hashed-token identity store
  user.py             per-user paths and ownership foundations
  source_control.py   native read-only local Git baseline
  updates.py          update planning/read state
  scheduler.py        persistent reminders + background scheduler
  theme_pack.py       manifest loading/registry (partial runtime integration)
  init.py             zero-provider initialization
  framework.py        framework validation and manifest rules
  static/             packaged companion SVGs, icons, fonts
config/connections.json   provider wiring (no secrets inline)
data/                  ignored private runtime state (never public content)
docs/                  architecture, contracts, operations, finish-line intent
design/                tokens, current design references, artwork
design/handoff/        archived design package (do not modify)
tests/                 security + safety + persistence suites
compose.yaml           the supported standalone deployment
```

Runtime files include `world.json`, `journal.ndjson`, `vault.enc`, `users.json`,
`apps.json`, `reminders.json`, setup markers, and optional theme-pack/per-user
directories. Concrete runtime locations depend on data/config configuration;
private files are not application source or public repository fixtures.
