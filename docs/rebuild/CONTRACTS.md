# Rebuild contracts C1–C5

> **Status:** Accepted 2026-10-01 by orchestrator · **Date:** 2026-10-01 · **Canonical for:** the five contracts the front-door rebuild lanes build against · **Read this if:** you are working on any `rebuild/*` lane. Authority: [ADR-0008](../adr/0008-front-door.md). Baseline: `.project/PROPOSAL-FRONT-DOOR-2026-10-01.md`.

**Stack (orchestrator decision):** Python 3 + FastAPI + uv; React + Vite + TypeScript + react-query. Package `personal_world`, env prefix `PW_`, image name and `/healthz` `commit` are kept. On `rebuild/front-door`, obsolete modules are deleted, not adapted.

## C1 Config files (canonical truth)

YAML, `schema_version: 1` in every file, at `$PW_CONFIG_DIR/worlds/{providers,requests/<provider>,cards,boards,actions}/<id>.yaml`. Ids match `^[a-z0-9][a-z0-9-]{0,62}$`; request ids are `<provider>.<name>`.

- **Provider:** `id, name, kind (http|room0|reference), base_url, path_prefix`; `auth {type: none|bearer|header|basic|cookie_session|password_grant, header_name?, secret_ref (env:NAME|vault:NAME)}`; `network {lan: false}`, `tls_verify` (default true), `timeout_s` (default 5, max 15), `max_bytes` (default 2 MiB, hard max 8 MiB).
- **`auth.type cookie_session` (added 2026-10-02, T9; production sender 2026-10-02):** requires `secret_ref` and `login_path` (a relative path), plus optional `username_field`/`password_field` (defaults `username`/`password`). `secret_ref` names one secret holding `username:password` (the `basic` convention), so no literal username is written to config. The sender POSTs the form-encoded credential to `login_path` and keeps the returned session cookie in memory only — never logged, persisted, cached, put in a note or evidence, and never a request header (`cookie`/`set-cookie` stay forbidden in `header_name`). The login is a normal confined request: joined and re-checked like a request path under `base_url` + `path_prefix`, the same resolved-and-pinned address, the same address policy, no redirect, one deadline and one `max_bytes` for the whole call. A `403` on a **read** re-logs-in once and replays that one request; a `403` on a **write** is never replayed (the stale session is dropped and the refusal is the result). A second refusal of a read is `auth_failed`, never swallowed and never a loop.
- **`auth.type password_grant` (added 2026-10-02, T10; production sender 2026-10-02):** requires `secret_ref` and `token_path` (a relative path), plus optional `username_field`/`password_field` (defaults `username`/`password`) and `token_field` (default `access_token`). `secret_ref` names one secret holding `username:password` (the `basic`/`cookie_session` convention), so no literal username is written to config and no second secret is introduced. The sender POSTs the form-encoded credential to `token_path` and sends the returned token as `Authorization: Bearer ...`, holding it in memory only — never logged, persisted, cached, put in a note or evidence. Same confinement as above; a `401` on a read re-fetches the token once and replays once, on a write it is never replayed, and a second refusal is `auth_failed`, never a loop.
- **Session retry rule (C1/C3, 2026-10-02):** the only automatic retry anywhere is a session refresh on a **read** — one re-login and one replay of that same read, after the stale cookie/token is dropped and a new one is obtained. Automatic side-effect retries are off everywhere else (ADR-0008, handoff §7): a refused write is returned as the refusal, and the next call logs in fresh. A failed re-login is a failure, never a swallowed success, and never a loop. The cookie/token lives in process memory in a map keyed by the whole provider identity (id, `base_url`, `path_prefix`, `secret_ref`, login/token path), so a config change can never reuse it for a new destination; the map is bounded and guarded by a lock. The test-only `reference_send` follows the same rule.
- **Request:** `id, provider, method, path` (relative; no scheme or host; no `..`), `query {}`, `headers {}` (allow-list; never Authorization or Cookie), `body` (json|null); `effect: auto|read|write` (auto: GET/HEAD read, else write; a config may raise read→write, never lower write→read without an explicit reviewed `known_safe: true`); `ttl_s, timeout_s`, `assertions [{status: 200} | {path, exists|is_list|equals}]`.
- **Card:** `id, title, icon, group (life|machine), request` (or `requests []` to aggregate), `view (stat|list|table|status|meter|link|markdown)`, `meaning {concept, short, full}`; `fields [{path, label, format (number|percent|bytes|duration|relative_time|text), unit}]` where `path` is a JSONPath subset (`$.a.b`, `[*]`, `[n]`; no filters, no scripts); `meter {type: segments|bars|progress|marks|dots|day|shelf, …}`; `status {path, healthy: [], needs_attention: [], else: unknown}`.
- **Board:** `id, title, home: bool, items [{card, size: S|M|L, hidden: false}]`.
- **Action:** `id, request, name, access (read|write), approval (never|always; missing → always; write → always unless owner-set), scope (string), idempotency (required|optional|none), exposed (bool, default false)`. `version` = sha256 of the canonicalized resolved action + request + provider destination. It is computed, never written.

**Store behaviour:** validate refs and schema; atomic write (tmp + fsync + rename); per-file etag, 409 on mismatch; an invalid edit is rejected and the last valid config stays active; reload never executes anything; a change to a provider destination or credential ref, a request or an action invalidates pending authorizations whose version no longer matches; UI writes produce the same files (round-trip test: load→save→load equal).

## C2 Result and freshness envelope

One per card fetch. The API returns only mapped data.

```
{card_id, source_state, freshness, observed_at, fetched_at, last_good_at,
 values:{field:{text, raw?}}, meter:{…, text_equivalent},
 meaning:{short, full},
 evidence:{request_id, method, path, status_code?, duration_ms?, error_class?, note?}}
```

- `source_state` (Play-Nice words only): `healthy | needs_attention | degraded | unavailable | stale | unknown | not_configured`. `freshness`: `current | stale`.
- Availability and freshness are separate. Unavailable keeps last-good values marked stale, with `last_good_at`.
- Missing is not 0. An empty list is not unavailable.
- Evidence is redacted: no secrets, no upstream body beyond 2 KB, never the Authorization header.
- `error_class`: `timeout | connection | http_4xx | http_5xx | malformed | redirect_refused | too_large | confinement_denied | auth_failed`.

### C2.1 Values and states (accepted 2026-10-01)

- **Field key** = slug(label): lowercase, non-alphanumerics become `-`, trimmed; a collision gets `-2`, `-3`.
- A **missing** value is `{"text":"unknown"}` with no `raw` key (never 0). An **empty list** is `{"text":"none","raw":[]}` and is healthy, not unavailable.
- **Failure mapping** (`error_class` → `source_state`): `timeout`, `connection`, `http_5xx`, `redirect_refused`, `too_large`, `confinement_denied` → `unavailable`; `auth_failed` (HTTP 401/403) → `needs_attention`; `http_4xx`, `malformed` → `degraded`. Missing config → `not_configured`.
- After a failure the card keeps last-good values with `freshness: stale` and `last_good_at`; with none, every field reads `unknown`.
- **Config PUT** needs the real etag in `If-Match` (update) or `If-None-Match: *` (create). `If-Match: *` is refused with 428.

### C1.1 / C2.2 Meter (accepted 2026-10-01)

- **C1 card `meter`** names its data sources: `{type, value?, max?, count?, filled?, items?}`. `value` is a field key or a `$` path; `max`, `count`, `filled` are a number, a field key or a `$` path; `items` is a `$` path to a list. A `progress` meter needs `value`; `segments` needs `count` and `filled`. Unknown keys are rejected; paths are validated at save time.
- **C2 envelope `meter`** is `{type, text_equivalent, value?, max?, count?, filled?, items?}` with the resolved numbers. A source that cannot be resolved to a finite number (missing, not a number, a boolean) is **omitted**, never 0; an explicit 0 is kept. `items` keeps only numbers, booleans and strings (strings cut at 80 characters), at most 200; an existing empty list is `[]`, a missing one is omitted. When the card is stale the numbers come from last-good data, like `values`. The UI draws nothing for an omitted number.

### C1.2 `approval: never` on writes (accepted 2026-10-01, tightened after review)

`approval` defaults to `always`. `never` is honoured only because the owner wrote it in config (config writes are owner-only; an agent token cannot change it). **For a request whose effect is `write`, `never` is refused at save unless the action carries the owner's explicit `owner_waives_approval: true` (which needs `approval: never`) and says `access: write`.** `access: read` may not point at a write request (refused at save, also when a request is edited into a write). Even with the waiver, an agent caller's write always waits for the owner. Auto-approvals record `authority: policy:never`. The dispatcher re-checks all of this, so a hand-edited file cannot smuggle an auto-approved write. A retry always needs a fresh approval. Project Home-governed operations are never auto-approved.

**Provider `governance`** (`worlds` | `project_home`, default by kind): `room0` providers default to `project_home` (fail closed); everything else defaults to `worlds`. Operations on a `project_home` provider can only be approved in Project Home and recorded as `project_home:<approval id>`.

## C3 Action, authority and receipt lifecycle

SQLite at `$PW_DATA_DIR/worlds.db`, WAL, `BEGIN IMMEDIATE`.

- **`authorizations`:** `id, action_id, action_version, caller (principal id), destination (provider id + base_url hash), params_hash, created_at, expires_at (default 10 min), state (pending|approved|denied|expired|invalidated|consumed), authority (worlds_owner | project_home:<approval id> | policy:never), approved_at, approved_by, step_up_at`.
- **`executions`:** `id, authorization_id UNIQUE, intent_at, dispatch_started_at, finished_at, state (INTENT|DISPATCHING|SUCCEEDED|FAILED|UNKNOWN), status_code, evidence_redacted, idempotency_key`.
- **Consume is one transaction:** `UPDATE authorizations SET state='consumed' WHERE id=? AND state='approved' AND expires_at>now AND action_version=current_version`; `INSERT executions(state=INTENT)`; commit. Then `UPDATE → DISPATCHING` (commit), then exactly one network attempt (client retries off), then SUCCEEDED, FAILED or UNKNOWN.
- FAILED only with evidence of non-execution (for example a 4xx validation reply). Timeout, connection reset after send, a 5xx of unclear effect, or a crash is UNKNOWN.
- Startup recovery: INTENT or DISPATCHING becomes UNKNOWN and is never re-sent.
- A retry needs a NEW authorization, with a warning that the earlier one may have run.
- **Callers:** agents see only exposed actions within their scope; a token is never approval. Approval for Project Home-governed operations goes through Project Home's `/room/actions` approve and is recorded in `authority`. For other services the owner confirms in Worlds with step-up.
- Connect test/run of a write uses this exact path. Save, preview, mapping and import never dispatch.
- **Receipt** = an execution row joined with its authorization (caller, action_id, version, authority, timestamps, state, redacted evidence).

## C4 Memory persistence boundary

- **Durable:** `worlds.db` tables `kept, later, records (sensitivity: normal|locked), history (append-only events)`, each with provenance (`owner | external_ref | suggestion`), `created_at`, `updated_at`.
- **Find** is an FTS5 index over them, queried with escaped, parameterized terms; never raw MATCH syntax.
- Locked records need step-up and are excluded from agent answers and previews unless step-up is active.
- Agent access is named, narrow, governed read actions only (for example `memory.later.count`); no generic search tool.
- **Export:** NDJSON per table. **Backup:** SQLite online backup API to a dated file.
- **Durability classes:** config files (canonical; back up with the config volume); `worlds.db` (durable: Memory, receipts, authorizations); cache dir `$PW_DATA_DIR/cache` (disposable; deleting it loses only last-good data).
- Owner decision 2026-10-01: start fresh. No import of the old journal, `world.json`, stickers or search index; no migration code.

## C5 Card accessibility props (UI ⇄ API)

Every rendered card or row exposes: accessible name; state word plus shape (● healthy, ▲ needs attention, ■ unavailable, ◌ stale, ○ unknown, ◇ not configured, ◆ degraded); value text with unit; meter `text_equivalent`; freshness text; a link to detail. Targets ≥44px; labels ≥13px; body 16px; no colour-only state; static unless `prefers-reduced-motion: no-preference`.

## C6 Home read API

Orchestrator decisions, 2026-10-01. Values come only from the per-card C2 envelope (`GET /api/cards/{id}`).

- `GET /api/boards/home` → `{id, title, items:[{card, size S|M|L, hidden, title, icon, group life|machine, view, fields:[{key, label, format, unit}], meter_type|null}]}`. The display definition is derived from the C1 card. No request ids, paths, provider URLs or JSONPaths in the payload. The primary value is `fields[0]`. `needs_you` is not a board item field.
- `GET /api/needs-you` → `[{id, text, source, created_at, action:{kind: open|approve, href?|authorization_id?}}]`. `text` is a terse imperative ("Approve Hive Works plan"). Fed by pending Project Home approvals (room/0) and pending Worlds authorizations. Needs you is never inferred from `source_state`.
- Grouping, by C2 envelope:
  - **Needs a look:** `source_state` in {unavailable, degraded, stale, needs_attention, unknown} or `freshness: stale`. Worst first: unavailable, degraded, stale, needs_attention, unknown.
  - **Your life:** healthy + `group: life`. **Quietly working:** healthy + `group: machine` (folds to one line in Calm density).
  - **not_configured:** not a row on Home. It shows as ◇ in the whole-world strip only, linking to Connect.
  - An empty Needs a look shows "Nothing needs a look. Everything is answering." Groups never reorder.
- **Pick up (reserved):** omit the section entirely when there is no data. The future source is `GET /api/pickup`, backed by Memory Later and History (L-memory).

## C7 Owner and identity

Identity is not a provider, request or card, so it is not under `worlds/`. One file, `<config dir>/owner.yaml`:

```yaml
schema_version: 1
public_origin: https://worlds.example.test   # scheme://host[:port] only; the one origin cookies, CSRF and OIDC redirects are built for
oidc:                                         # optional
  issuer: https://auth.example.test
  subject: <the stable subject the provider asserts for the owner>
bootstrap:                                    # optional local sign-in
  enabled: true
  secret_ref: env:PW_BOOTSTRAP_TOKEN
```

- **No secret values** are ever in the file: only `secret_ref` (`env:` or `vault:`).
- **Fail closed:** a missing, unreadable, mis-versioned or invalid file means nobody can sign in, there is no allowed Origin, and cookie-authenticated writes are refused. There is no development bypass.
- **OIDC:** a sign-in succeeds only when the verified `issuer` and `sub` equal the file's (constant-time compare). Any other verified identity gets 403 and no session. The redirect URI is `public_origin` + `/api/auth/oidc/callback`, never derived from the Host header.
- **Bootstrap:** the owner can sign in with the secret behind `secret_ref` (POST /api/auth/bootstrap, allowed Origin required). It also serves as step-up. Failed guesses are limited **per client address**: 3 free, then exponential back-off (5 s doubling, capped at 15 minutes); a client in back-off is refused without its secret being checked. A global ceiling (30 failures in 10 minutes) only spaces attempts 2 s apart; it never locks the owner out, and OIDC sign-in is unaffected. Bootstrap is available while `bootstrap.enabled` is true, and **switches itself off once OIDC is configured and one OIDC owner sign-in has succeeded** (sign-in and step-up both); remove or disable the block to turn it off sooner (the file is re-read on every request).
- **Session binding:** a session is bound to a hash of `public_origin` + OIDC issuer + subject (or bootstrap-only). Changing the owner identity in the file ends every existing session.
- **Step-up** (needed to approve anything): a fresh proof inside 120 seconds (OIDC re-login with `auth_time` fresh for the same subject, or the bootstrap secret) stamps the session; it counts for 5 minutes. An agent token never has step-up and never approves.
- **Who is "a client"** for the bootstrap rate limit: the peer address, or, when `PW_TRUSTED_PROXIES` (comma-separated IPs/CIDRs of your reverse proxies) is set, the right-most `X-Forwarded-For` hop (all header lines read in order; ports and brackets stripped) that is not a trusted proxy (a peer that is not a trusted proxy is never believed about that header; a garbage hop means none of it is trusted). With `PW_TRUSTED_PROXIES` unset and `X-Forwarded-For` arriving from a non-loopback peer, Worlds logs a warning once: everyone behind that proxy then shares one limit.
- **The owner can never be locked out by others, and back-off still throttles guessing:** a client key in back-off gets ONE evaluated guess per 2 seconds; guesses over that rate are refused without being compared at all, so an attacker cannot test guesses at network speed. Keys are independent, so nobody can use up another key's guess. The correct secret passes at most once per 15 minutes while in back-off. A wrong guess lengthens the back-off (5 s doubling, the exponent capped so it can never overflow, ceiling 15 minutes). OIDC sign-in is unaffected. A global ceiling (30 failures in 10 minutes) only adds spacing for wrong guesses. Comparisons are constant-time over fixed-length digests.
- **The bootstrap secret must carry at least 128 bits from a generator:** at least 32 hex characters or 22 base64url characters. Generate one with `python -c "import secrets;print(secrets.token_urlsafe(32))"`. A weaker secret stops Worlds from starting (fail closed); an unset one just leaves bootstrap unusable.

## C1.3 Card mapping and query additions

Orchestrator decisions, 2026-10-01. Small and closed; everything else in C1 is unchanged.

- **`format: count`** is the length of the list at the path (`$.records` or `$.records[*]`). A missing path, or a value that is not a list, reads `{"text":"unknown"}` with no `raw`. An existing empty list is a real `"0"` with `raw: 0`. A `unit` is appended as for `number`.
- **Query templates**, in query values only (never path, host or headers): `{today}`, `{today+Nd}`, `{today-Nd}` (N 0 to 366) as a UTC date, and `{now}` as a UTC datetime. Rendered server side when the request is built. No other substitution, no nesting; an unknown token or a stray brace fails validation at save time.
- **Status aggregation**, `status.mode: first | all | any` (default `first`, the first extracted value decides):
  - `all`: `needs_attention` if any value is in `needs_attention`; else `healthy` only if every value is in `healthy`; else `unknown` (an unrecognised value makes it unknown).
  - `any`: `needs_attention` if any value is in `needs_attention`; else `healthy` if at least one value is in `healthy` (unrecognised values are tolerated, for redundant endpoints); else `unknown`.
  - An empty match is `unknown` in every mode, never healthy. **Addition from L-recipes:** `status.empty: healthy` (default `unknown`) makes an EXISTING empty list read `healthy`, for health lists where empty means no problems. A missing path is still `unknown`.
  - **Threshold (orchestrator, 2026-10-02):** `status.above: {value: <number>, state: needs_attention|degraded}` applies when the first extracted value is a number greater than `value` (a bool or text never counts), and is checked before the `healthy` / `needs_attention` lists.
- **Last element:** `[-1]` is allowed in a path. No other negative index, no slices.

## C8 room/0 providers

A provider of `kind: room0` is a Play-Nice room (`contracts/surfaces/ROOM.md`). Worlds maps it; there are no per-card files.

- **Recipe install (added 2026-10-02):** a recipe with `status: room` in `recipe.yaml` is a room0 template. `install` writes its provider through the same `ConfigStore` path as any recipe, with the same placeholder `base_url` refusal and `secret_ref` override, and invents no request/card/action files (the room maps its own cards). `principal_id: your-person-id` is installed as written; the owner replaces it in their own config. The marker is deliberately separate from `ready`, because a `ready` recipe is the HTTP-shaped one that ships cards.

- **Settings** (room0 only): `principal_id` (`[A-Za-z0-9_-]{1,64}`: who Worlds speaks for, sent as `X-Worlds-Principal` by Worlds itself from this setting, never from a request header), `public_url` (`scheme://host[:port]`: where room links open), `group` (`life` | `machine`: the lane its cards land in). `governance` defaults to `project_home` for room0 (fail closed); a Worlds-approved room says `governance: worlds`.
- **Cards:** every `/room/cards` entry becomes a C2 envelope with id `r-<provider>-<slug>-<hash>` and appears on Home through `GET /api/boards/home` (display defs, `group` from the provider). Descriptor status maps healthy→healthy, degraded→degraded, unhealthy→needs_attention, unknown→unknown. A card past `stale_after_s` is `stale`. Links must be same-origin paths (rule 6) or they are dropped. An unknown tone reads as `update` (logged). A card that cannot be read honestly is `degraded` with every value `unknown`. An unreachable room shows its last-known cards stale with the room `unavailable`, or one `unavailable` status card when there is no history; it never blanks the other rooms.
- **Needs:** `/room/needs-you` feeds `GET /api/needs-you` as `{id, text, source, created_at, action: {kind: "open", href?}}`; `href` exists only when the room's link is a safe path and `public_url` is set.
- **Actions:** `/room/actions` are candidates, listed with `adopted`. `POST /api/rooms/{id}/actions/{room_action_id}/adopt` (owner, CSRF) creates a C1 request and action that is never exposed to agents, `approval: always`, `access: write` (the room's own `writes` claim is not trusted), `idempotency: required`. Running one goes through the C3 dispatcher; the room's receipt `{ok, summary, changed}` decides the outcome (`ok: true` → SUCCEEDED, `ok: false` with nothing changed → FAILED, `ok: false` with changes or an unreadable receipt → UNKNOWN). A room's own `ask_first` approval token is not supplied by Worlds: such an action fails closed at the room (FAILED).
- **Fast on a bad day:** a failing room is not retried for 30 s (doubling to 5 min); a request waits at most 0.25 s behind another request's fetch and then serves what is known; a card request asks only its own room; every room always answers (last-known cards stale, or one explicit `unavailable` card), so a slow or dead room never delays or removes the others. The room's own receipt is trusted for FAILED only when it says `changed` is empty (documented, accepted). Adopted action ids carry a short hash of the raw room action id so look-alike ids cannot collide.

### C8.1 Typed action choices and answering a need (added 2026-10-02)

- **Typed input:** a `/room/actions` entry may carry `choices` (a list of `{value, label?}`; a bare string is also accepted as a choice) and `allow_text` (boolean). Both are surfaced by `GET /api/rooms/{id}/actions` on top of its existing keys. Input is bounded at the boundary: at most 20 choices; a value must be a non-empty string, trimmed and cut to 120 characters; an optional label is a string, trimmed and cut to 120 characters; duplicate values collapse (first wins); junk entries are dropped. `allow_text` is true only for the literal `true` (missing/unknown is false, fail closed). A malformed descriptor degrades to no choices and no free text; an action with no usable choices stays a valid action.
- **Answering a need:** `POST /api/rooms/{id}/actions/{room_action_id}/answer` (owner, CSRF) with `{params?, idempotency_key?, project_home_approval_id?}` answers a room need by running an **already-adopted** room action through the C3 lifecycle — `request_authorization -> approve (owner authority, or Project Home authority per the provider's `governance`) -> consume -> dispatch`. It does not shortcut the authority: nothing is sent without a consumed authorization, and there is at most one network attempt. The adopted request has no body, so the answer payload becomes the body through the dispatcher's existing params mechanism. An unadopted action, an action the room no longer offers, or an unknown provider is refused with 404; an id no room action could have is refused with 400.

### C8.2 Change ping (added 2026-10-02)

- **Invalidate, never dispatch:** `POST /api/rooms/{id}/changed` (owner, CSRF) drops that room's cached snapshot so the next read refetches — it dispatches no action and sends NOTHING to the room. A provider that is not a room0 room is a 404; the answer is `{"id": ..., "invalidated": true}`. The client drops the cached snapshot, its last-good fallback and its failure back-off under the same lock `snapshot()` uses; invalidation never fetches and never fabricates data, and the last-good mechanism itself is unchanged (the next successful read repopulates it, so a later fetch failure can still show those last-known cards stale).
- **The room's own signal:** a room may expose `GET /changed` returning `{contract, provider_room_id?, changed, at?}`. It is parsed defensively: only `contract: room/0` with `changed` literally `true` counts; a malformed, non-JSON or unrecognised body is ignored (no raise, no invalidation), and an unbounded `provider_room_id` is dropped rather than trusted. The rule text in `contracts/surfaces/ROOM.md` is not in this repo.

### C6.1 first run (accepted 2026-10-01)

`GET /api/boards/home` always answers 200 with `{id, title, items, first_run}`. `first_run` is true exactly when `items` is empty (no configured or room cards): the UI shows a guided start (one "Connect your first service" card, plus Memory). It is never a 404.

## C9 Connect workshop API

Owner-only, CSRF (the same principal dependency as every other write). Saving uses the config CRUD; nothing here saves anything.

- `POST /api/connect/try {provider, request}`: `provider` is a saved id or an unsaved provider object (`secret_ref` only; the model has no raw-secret field and rejects extra keys; `env:` names belonging to Worlds itself, `PW_*`, `OIDC_*`, anything with `BOOTSTRAP`, are refused so an unsaved provider cannot send Worlds' own credentials somewhere). `request` is an unsaved request body. **Read effect only:** a write (method, `effect: write`, or a write lowered without `known_safe`) is refused with 422 `test write actions through an approved action`. One attempt through the confinement module (so loopback/private addresses need `network.lan`, metadata is always refused). Returns `{ok, status_code, duration_ms, error_class, note, content_type, sample, truncated, suggested_fields}`: `sample` is the response scrubbed (values under secret-looking keys, every known secret value, bearer strings and long token-looking strings replaced; at most 16 KB, `truncated` says so), `suggested_fields` is up to 50 scalar leaves as `{path, label, format, sample}` using only the JSONPath subset (each path verified against the mapping engine; secret-looking keys and values skipped). Rate limit 10 tries per minute (429 + Retry-After; rejected requests do not count). Every executed try is appended to History as `connect_try` with `{provider, saved, method, path, status_code, error_class}` and no bodies, query values or secrets.
- `POST /api/connect/preview {card, sample}` or `{card, request}`: an unsaved card (defaults fill id, title and meaning) is validated like a saved one; with `sample` the C2 envelope it would produce is returned with NO network call (sample at most 256 KB and 20 levels deep, else 413); with a saved read `request` id it is fetched once through the runner. A saved write request is refused (422).

**OpenAPI import** (added 2026-10-02): `from_openapi(doc)` turns an already-parsed OpenAPI 3.x document into a *skeleton* only, and is read-only: GET/HEAD operations become C1 request objects, every other method is listed as write-like and never imported, ids/paths/parameter names are validated and dropped when they do not fit, path templates are documented rather than substituted, `servers[]` is ignored in favour of a synthetic placeholder address, only local `#/` refs are followed, unmapped auth schemes leave `needs_auth: unknown` rather than a silent `none`, and the document is bounded. It writes nothing; the owner reviews the result and saves it through `ConfigStore`.
