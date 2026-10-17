# Connect API contract — REVIEW (personal-world#323)

> **Status: REVIEW.** Not an approval, not a merge, not a change of canon. This document is one file of
> prose: **no code, test, config, UI or contract file was modified.** Nothing here amends
> [`docs/vnext/connect-contract.md`](../connect-contract.md) — it is written *at* it, so the contract can
> keep its own status word (**MOCKUP**) and Rylee can decide what, if anything, to change.
>
> **Date:** 2026-10-16 · **Issue:** #323 (Connect API and end-to-end integration contract) ·
> **Reviews:** [`connect-contract.md`](../connect-contract.md) (MOCKUP, rev 2, 2026-10-13) ·
> [`connect-contract-rereview.md`](../connect-contract-rereview.md) (deepseek-v4.1-flash) ·
> [`build-plan.md`](../build-plan.md) (PLAN ONLY) · [`proof/c-proof.md`](../proof/c-proof.md) and
> [`proof/c-room0.md`](../proof/c-room0.md) (DRAFT proofs)
> **Base commit reviewed:** `39beedb` (this clone, `offload/intake-b-personal-323-…`).

## 0. Why this document exists, and what it does not decide

Rylee's owner ballot of 2026-10-16 asks for **a Connect API contract review before further
implementation**, recording direction and evidence requests only. This is that review, in the shape the
brief asked for: *what the contract promises, what the code does, the gaps, and the questions.*

It decides nothing that is Rylee's to decide. It does not choose a product boundary, an identity model, a
secret policy, an authorization rule or a cross-service authority. It does not propose implementation and
asks for no merge, deploy or deletion. Where the contract and the code disagree, **both readings are
recorded and the code is cited**, so the choice is visible rather than made here.

Every claim below is one of four kinds, and the document keeps them apart on purpose:

| Word | Means |
|---|---|
| **HOLDS** | The code does what the contract says, at the cited line |
| **DRIFTED** | The code still behaves this way, but the contract's line citations no longer point at it, or its wording now understates/overstates the code |
| **NOT BUILT** | The contract proposes it; no code exists |
| **MISMATCH** | The contract's shape cannot be expressed in the C1 models as they stand, or means something different from what the code means |

## 1. How this was checked

- **Base:** `39beedb`, the working tree of this clone. The contract states its evidence is at `786f506`
  (`connect-contract.md:503`); every source file under `src/personal_world/worlds/` has moved since, so
  each citation was re-opened **at the line it names** and the construct it claims was compared. §6 lists
  the ones that no longer resolve.
- **Method:** every verdict below was reached by opening the named file and line, not by reading the
  contract's own revision tables. Where a contract row and a file disagree, the file wins.
- **Sandbox limits, stated plainly:** this environment has **no `pytest`, no `fastapi`, no `ruff` and no
  `ui/node_modules`** (`python3 -c "import fastapi"` → `ModuleNotFoundError`; `ls ui/node_modules` → no such
  file). **The repository's test suite was NOT RUN here.** `pydantic` 2.12.5 and `httpx` 0.28.1 are
  present, so the model-level claims in §4 were checked by importing the models and asserting the fields
  (§9, command C), and the route claims by parsing the route table (§9, command D). The host re-runs
  `python -m pytest -q` and `ruff check`.

## 2. Verdict at a glance

| # | What the contract promises | What the code does at `39beedb` | Verdict |
|---|---|---|---|
| 1 | 14 endpoints under `/api/connect/v1/` (§3) | **Zero** routes exist. The live Connect surface is two routes: `POST /api/connect/try` and `POST /api/connect/preview` (`connect_routes.py:119`, `:142`) | NOT BUILT (as declared) |
| 2 | Provider-neutral vocabulary: capability, field, freshness, authority (§1) | The models have no capability, no descriptor and no contract version. `Auth.scope`/`Request.provenance`/`Request.verified`/`Action.state`/`Provider.governance` exist (§6.1's four fields plus one more) | NOT BUILT |
| 3 | Credential **references** only, no value round-trip (§4.2) | Holds. No model has a field for a value; unsaved providers carry `secret_ref` only and Worlds' own names are refused (`connect_routes.py:37`, `:101`) | **HOLDS** |
| 4 | A credential may only be sent to a capability in `scope`, refused before DNS (§4.2, §5.1) | **Implemented.** `scope_allows` (`models.py:491`) → `send_scoped` (`models.py:500`) → `in_scope=False` → `auth_failed` before `resolve_within` (`confinement.py:598`–`:602`). The contract still calls scoping "new" | DRIFTED (in the safe direction) |
| 5 | `published` is an allow-list of **field keys**, and the card's `fields` list *is* that allow-list (§4.4, §6.1) | The C1 `Field_` has **no `key` field** (`models.py:314`–`:322`); envelope value keys are slugified from the field's **label** at render time (`cards.py:262`) | **MISMATCH** (§4.2) |
| 6 | `scope` lists capability ids (§4.2, §6.1) | The verdict is made on the **request id's second segment** — the *operation* (`models.py:497`). There is no capability id in the tree, and operation ids are unique per connection, not per capability | **MISMATCH** (§4.3) |
| 7 | `authority: "worlds" \| "external"`, an explicit descriptor field (§4.1, §7.3) | `Provider.governance: "worlds" \| "project_home" \| None`, already explicit, defaulting `room0` → Project Home (`models.py:180`, `:206`–`:207`) | DRIFTED (the field exists; the vocabulary differs) |
| 8 | A `proposed` action is inert; only `adopted` dispatches (§4.5, §6.1) | Holds and is stronger than the contract says: a non-adopted action is refused **for the owner too** (`dispatcher.py:223`–`:224`, `:343`–`:344`) | **HOLDS** |
| 9 | Endpoints 11 and 12 are the existing approval paths, unchanged (§3) | Both exist (`actions_routes.py:71`; `room_routes.py:52`). Endpoint 12 still returns 403: no verifier is wired (`production.py:95`), and `record_project_home_approval` raises before its transaction (`dispatcher.py:279`–`:280`) | **HOLDS** (gap still open, still correctly flagged in §7.3) |
| 10 | Recipes install is replaced; `install()`/`list_recipes()` have no caller (§7.4) | Holds. `install`/`list_recipes` are exported and unreferenced in `src/`; `from_openapi` is called only by `tests/recipes/test_openapi_import.py:13` | **HOLDS** |
| 11 | Discovery is one bounded read of a provider document (§3 endpoint 1) | `from_openapi(doc)` takes an **already-parsed** document and is pure (`recipes.py:467`); **nothing in the tree fetches an OpenAPI document**. Discovery is the one verb with no seam to reuse | NOT BUILT (§3, row 1) |

Two claims in the contract that are now **false in the unsafe direction** (they understate what the code
enforces) are recorded in §4.1 and §6; every other disagreement found is drift in citations or wording,
not behaviour.

## 3. The endpoint promise, endpoint by endpoint

Nothing in this table changes the contract. It says, for each row, what a caller would actually reach if
they called it today.

| §3 # | Contract endpoint | Reachable today? | What the code offers instead |
|---|---|---|---|
| 1 | `POST /api/connect/v1/discover` | **No** | `recipes.from_openapi` parses a document someone else fetched (`recipes.py:467`). No bounded document fetch exists. `POST /api/connect/try` probes an endpoint the owner names — it does not read a schema |
| 2 | `POST /api/connect/v1/connections` (register) | **No** | `PUT /api/config/{kind}/{obj_id}` (`server.py:229`): validates, writes atomically, returns an etag, and refuses a request with neither `If-Match` nor `If-None-Match` (428). Owner-only, per `scripts/route-inventory.json` |
| 3 | `GET /api/connect/v1/connections` | **No** | `GET /api/config/{kind}` (`server.py:194`), owner-only |
| 4 | `GET …/{id}` | **No** | `GET /api/config/{kind}/{obj_id}` (`server.py:219`) |
| 5 | `GET …/{id}/capabilities` | **No** | **Nothing.** There is no capability type, and a capability compiles to one request file per `ReadSpec` — so the nearest honest read is "the request files of this provider" |
| 6 | `POST …/{id}/test` | **No** | `POST /api/connect/try` (`connect_routes.py:119`): one read through the seam, write refused 422 (`:115`), 10/min (`:34`), scrubbed sample (`:176`, `:191`), audited into History without bodies (`production.py:135`–`:136`). 25 tests in `tests/worlds/test_connect.py` |
| 7 | `POST …/{id}/transform` | **No** | `POST /api/connect/preview` (`connect_routes.py:142`): pure, returns the C2 envelope from a sample or a saved request; sample capped and depth-limited (`:159`) |
| 8 | `POST …/{id}/publish` | **No** | Card + board writes through `PUT /api/config/{kind}/{obj_id}`; `BoardItem.hidden` exists (`models.py:456`) but is set by hand. **The consumer cited in §4.4 is `production.py:91` (`home_extra`) — that is the *room* path.** A published config card reaches `/api/boards/home` through `server.py:164`–`:172` |
| 9 | `POST …/{id}/actions` (propose) | **No** | `Action.state` can express "proposed" (`models.py:476`) and the dispatcher honours it; nothing writes it except a hand-authored config `PUT` |
| 10 | `POST …/actions/{proposal_id}/adopt` | **No** | `PUT /api/config/action/{id}` with `state: adopted` |
| 11 | `POST /api/connect/v1/approvals/{id}/approve` | **n/a by design** | The contract keeps the existing `POST /api/authorizations/{id}/approve` (`actions_routes.py:71`) — owner-only, step-up inside 120 s (`dispatcher.py:262`) |
| 12 | `POST /api/rooms/{provider_id}/actions/{room_action_id}/answer` | **Yes, and 403** | `room_routes.py:52`; the Project Home branch (`room0.py:599`–`:600`) always refuses because no verifier is supplied (`dispatcher.py:279`–`:280`) |
| 13 | `POST …/{id}/disconnect` | **No** | Delete with reference checks: a delete is refused while anything refers to the object (`config_store.py:358`) |
| 14 | `POST …/{id}/revoke` | **No** | Delete the config objects; purge held credentials in process memory (`confinement.py:298`). **No route today reports `external_state_untouched`** — that receipt is new behaviour, not a rename |

## 4. Type-level mismatches: where the shape cannot land as written

### 4.1 §6.1's four "additive optional model fields" are already in the tree — and nothing writes them

The contract says v1 *proposes* four additive optional fields and lists them as work to do. At `39beedb`
all four exist, plus a fifth the contract does not mention:

| Field | In the code | Default | Who writes it today |
|---|---|---|---|
| `Auth.scope` | `models.py:114` | `None` | Only a hand-authored `PUT /api/config/provider/{id}` |
| `Request.provenance` | `models.py:257` | `"owner"` | Same |
| `Request.verified` | `models.py:258` | `False` | Same |
| `Action.state` | `models.py:476` | `"adopted"` | Same |
| **`Provider.governance`** (not in the contract's list) | `models.py:180` | `None` → `room0` is Project Home | Same |

Two consequences, both of which the contract should absorb before anything is built on it:

1. **The contract's persistence story is out of date in the safe direction.** §6.1 says "v1 adds" these
   fields; the tree already has them, with the fail-closed defaults the contract asked for. The Stage C
   proof records the same fact from the other side (`c-proof.md`: the pins it once held as strict `xfail`
   were flipped by the implementation landing, not by a relaxed assertion).
2. **Nothing in the product writes them.** `grep` finds no producer of `provenance`, `verified`, a scoped
   `auth.scope` or a `proposed` `state` anywhere in `src/` — only the proof tests construct them. So today
   they are configuration-file features with no lifecycle: nothing in the running app can *set* a scope, so
   the fail-closed branch is only reachable by hand-editing YAML. That is a real gap between the threat
   model (which treats scoping as the live control) and the running system (where it is inert).
   `action_version` already strips these fields at their defaults (`models.py:514`–`:521`), so a hand edit
   that changes a scope *does* invalidate pending authorizations — that part is right.

### 4.2 `Field_` has no `key`, so the publish allow-list has no home (MAJOR)

The contract is specific and repeated on this point: `TestResult.values` is
`Record<string, FieldValue>` keyed by `_KEY_RE`; `CardDraft.fields[]` carries a `key`; `PublishSelection.published`
is "an allow-list of `TestResult.values` keys"; and §6.1 says "the card's own `fields` list *is* the
field-key allow-list".

In the code:

- `Field_` is `{path, label, format, unit}` — there is **no `key` field** (`models.py:314`–`:322`).
- The envelope's `values` map is keyed by a slug **derived from `field.label` at render time**, with a
  uniquifying suffix on collision (`cards.py:262`, `_unique_slug`).
- `_KEY_RE` (`models.py:370`) is not a field-key rule at all: it validates **meter sources** — a meter may
  name a number, a `$` path, or the key of one of the card's fields (`_check_ref`, `models.py:373`–`:391`).

So the key an owner publishes against is **not stored, not stable across a label edit, and not derivable
from the config file**. A selective-publish security test ("a capability not in `published` appears in no
`/api/boards/home` payload") cannot be written against the C1 card file as the contract describes it.

This is a contract-side decision, not an implementation gap: either the allow-list becomes a list of
`Field_.path` values (stored, stable, already validated by `_check_path` at save), or `Field_` grows a key —
which would be a fifth additive field and would contradict §6.1's "exactly four". **Rylee's call; see Q4.**

### 4.3 `scope` names operations in the code, capabilities in the contract

`scope_allows` compares the credential's `scope` entries against `request.id.partition(".")[2]`
(`models.py:497`) — the **operation** segment, because `Request.provenance`/`verified` also live per
request and a request file is `<connection>.<operation>` (§6.1). The contract says the same list holds
**capability ids** (§4.2: "`scope: string[]` — capability_ids this credential may be sent to"), and §6.1
persists a capability as *several* request files. With one `ReadSpec` per capability the two readings
coincide; with two, the contract's rule silently leaks — capability `X` reads `a` and `b`, only `a` is
scoped, and `b` is refused for a reason the owner cannot see.

The Stage C proof papers over this by calling the operation a capability
(`tests/vnext/test_connect_proof.py:276`–`:281`: scope `["health"]`, request `synth.other` → refused).
The contract should pick one word and say which id it means.

### 4.4 `TestResult` vs the C2 envelope: the rename is not one step

§6 promises that `/api/connect/try` and `/preview` "both return a `TestResult` under the new contract so the
UI changes in one step, not two". The live envelope (`preview` returns it at `cards.py:104`–`:110`;
`build_for` returns the same shape at `:152`–`:160`) is:

```text
card_id · source_state · freshness · observed_at · fetched_at · last_good_at
values{key: {text, raw?}} · meter · meaning{short, full} · evidence{request_id, method, path, status_code, duration_ms, error_class}
```

Differences that matter to a UI and to a contract test: the contract nests the provenance under `source`
(code: `evidence`), names the state `state` (code: `source_state`), gives each `FieldValue` a `key` member
(code: the key is the map key, the value is `{text, raw?}`), and adds `truncated` and `observed_at`
bookkeeping that `try` carries separately as `ok`/`sample`/`suggested_fields` (`connect_routes.py:172`–`:173`).
The state vocabulary itself is compatible: `SOURCE_STATE_FOR_ERROR` (`cards.py:46`–`:56`) covers exactly
`unavailable`, `needs_attention`, `degraded`, plus `not_configured` (`cards.py:133`) and `unknown`
(`:137`–`:138`) — the seven words in §2. That part of the contract is honest.

### 4.5 `board: "home"` is a flag in code, a string in the contract

`PublishSelection.board` is a board id, and the worked examples use `"board": "home"`. In the tree,
`Board` is `{schema_version, id, title, home, items}` (`models.py:459`–`:463`): the home board is whichever
board carries `home: true`, and the seed happens to call it `home` (`seed.py:249`). So "publish to `home`"
and "publish to the home board" are different requests, and the contract's example only works because of a
seeded coincidence. Low severity, but it is the kind of coupling that breaks the first time a second board
exists.

### 4.6 Smaller ones, listed so they are not rediscovered later

- **`StatusMap` is stronger than §4.7 describes.** `empty: "unknown" \| "healthy"` lets an **existing but
  empty** list read `healthy` (`models.py:365`–`:366`), and `Above` adds a numeric threshold that sets the
  card state (`models.py:334`). §4.7's status-map row covers only `path`/`healthy`/`needs_attention`/`mode`.
  A provider-neutral contract that omits `empty` and `above` is not describing the card model it compiles to.
- **`truncated` fires only for the 16 KB sample cap** (`connect_routes.py:198`–`:199`, `SAMPLE_BYTES` at
  `suggest.py:14`). The other bounds — redact depth 12, 200 keys, 100 items (`suggest.py:36`–`:52`) — replace
  content with `"[too deep]"` / `"… N more keys"` and leave `truncated` false, so "a truncated sample can
  never become a published field" (§4.3) is true for one cap and false for the others.
- **`PrincipalBinding` → `principal_id`.** §6.1 says any part of the binding other than `person_ref` is
  refused at register. In code `principal_id` is a plain string on `Provider`, room0-only, pattern-checked
  at save (`models.py:192`–`:196`) and again at send (`confinement.py:615`–`:616`). The projection is fine;
  the **object form in §2 has no model**, so "refused at register" describes a validation that a literal
  reading could not perform.

## 5. What the Gate-0 inventory does not cover

The brief asks the design to inventory the current surface and "name what can stay, adapt, replace or
retire". §7 of the contract does that for five modules under `src/personal_world/worlds/`. Four surfaces
that a Connect design must make a decision about are absent from it:

1. **A second, older connections API.** `src/personal_world/api.py:2092`–`:2223` registers
   `/api/connections/{schemas, schema/{capability}, config, overview, test, validate}` plus
   `GET/PUT/DELETE /api/connections` — a capability/adapter surface (`ConnectionManager`,
   `provider_schemas.py`, `secret_resolver.py`) with **no UI consumer found** in `ui/src` and its own tests
   (`tests/test_connections.py:312`). Its `/api/connections/test` probes **adapters for named services**
   (Plex/Sonarr/Radarr — `_test_adapter` at `api.py:2226`), which is precisely the "bundling a new
   Sonarr/GitHub/Project Home implementation in Worlds" that #323 rules out. The contract does not say
   whether this surface is superseded, adapted or retired. **This is a Gate-0 gap, not a defect in the
   design** — but it is a decision that has not been written down.
2. **`src/personal_world/providers/`** — 4 294 lines of in-Worlds provider implementations, including
   `sonarr`-style `native_media.py`, `github.py` and `project_home.py`. §7 has no keep/adapt/replace row for
   this directory, and `AGENTS.md` already carries the rule ("External `room/0` systems remain supported as
   a provider kind … do not rebuild their mechanics inside Worlds"). What happens to these adapters is a
   live product question.
3. **`api_manifest.py` (1 292 lines) with API-017…API-021 rows for the old connections routes.** The
   drift checker's docstring says the old `api_manifest` "is deleted" (`scripts/contract-drift-check.py:19`),
   but the module is present in the tree at `39beedb`. Either the checker or the module is stale; a contract
   that cites neither cannot tell.
4. **The machine-checked route gate.** `scripts/route-inventory.json` records **every** `/api` route with
   its auth level, generated from the live app, and `scripts/contract-drift-check.py` fails on any added,
   removed, renamed or **re-authenticated** route (exit 1 on drift). `ui/src/generated/openapi.json` is
   checked the same way. So **every** `/api/connect/v1/*` endpoint in §3 has a second, mechanical
   consequence — regenerate the inventory, regenerate the spec, and land them in the same change — and the
   contract's §3 never mentions the gate. `/api/connect/try` is recorded `"auth": "owner"`
   (`route-inventory.json:169`–`:173`), which is the evidence that the contract's "owner-only with CSRF"
   claim is currently true for the two live routes.

Two smaller Gate-0 items the contract does mention only in passing: **receipts** exist and work
(`/api/receipts`, `actions_routes.py:87`; every executed `try` is written to History without bodies,
`connect_routes.py:134`–`:139`, `tests/worlds/test_connect.py:246`), and the **"unscoped" label has no
surface** — the one strict `xfail` still standing in the proof is exactly that
(`tests/vnext/test_connect_proof.py:268`–`:273`). The contract's §4.2 says scope is enforced but never says
the owner can *see* whether a credential is scoped, which is the one thing that pin is asking for.

## 6. Citation drift (the citations, not the claims)

Every source file under `src/personal_world/worlds/` has moved since the contract's evidence commit
`786f506`. The drift is concentrated in `models.py` (which grew) and `confinement.py`; `connect_routes.py`,
`config_store.py`, `recipes.py`, `room0.py`, `production.py`, `authn.py`, `memory_store.py` and
`dispatcher.py`'s cited constructs still resolve. None of these rows changes a conclusion — they are listed
because a contract whose citations do not resolve cannot be used as an approval artefact, and because the
same drift will make the next review repeat this work.

| Contract cite | What it claims | What is at that line now | The construct is at |
|---|---|---|---|
| `models.py:11` | `ID_RE` | a pydantic import | `:13` |
| `models.py:180` | `principal_id` | `governance` field | `:183` |
| `models.py:184`, `:185` | `timeout_s`, `max_bytes` | `public_url`, `group` | `:187`, `:188` |
| `models.py:203` | `governed_by_project_home` | a `public_url` validator message | `:206`–`:207` |
| `models.py:245`, `:250`, `:251` | `query`, `ttl_s`, `timeout_s` | `provider`, `body`, `effect` | `:248`, `:253`, `:254` |
| `models.py:357`, `:364` | status `mode`, `_KEY_RE` | `_jsonpath`, a comment line | `:363`, `:370` |
| `models.py:425` | `Card.title` ≤120 | a `Meter` validator | `:431` |
| `models.py:447`, `:450` | `BoardItem` `extra="forbid"`, `hidden` | end of `Card`, `request_ids` | `:452`–`:456` |
| `confinement.py:606` | principal re-validated at send | `for address in addresses:` | `:615`–`:616` |
| `confinement.py:776` | redirect never followed | the `Accept-Encoding: identity` line | `:779`, `:786` |
| `confinement.py:804`, `:809` | raw-byte cap, encoded body refused | blank lines | `:811`, `:818`–`:824` |
| `dispatcher.py:277`–`:278` (quoted in §7.3) | the unconditional raise | the `def` and its docstring | `:279`–`:280` |
| `room0.py:598`–`:599` | the governed/un governed split | provider lookup, then the condition | `:599`–`:600` |

The contract's own §7.3 quote is two lines early but otherwise byte-accurate, and its conclusion — the
raise precedes `with self._db.write_tx()`, so **nothing is stored** and the answer route is 403 — I
re-checked at `dispatcher.py:279`–`:281` and it still holds.

## 7. Questions

### 7.1 Rylee's to decide (product boundary, identity, secrets, authorization, cross-service authority)

- **Q1 — Authority vocabulary.** The contract's `authority: "worlds" | "external"` is already `Provider.governance: "worlds" | "project_home" | None` in the tree (`models.py:180`). Which word is canonical, and does `None` keep meaning "a room is Project Home's" (`models.py:207`)? This is a naming and product-boundary call; nothing else can settle it.
- **Q2 — Endpoint 12.** The Project Home approval-recording path has no verifier and refuses closed end to end (`dispatcher.py:279`, `room_routes.py:76`). Does that stay refused (a gap the contract keeps flagging), or does a verifier become part of Connect's scope? The contract deliberately does not invent one; neither does this review.
- **Q3 — `exposed: false` and the "unscoped" label.** Should a Connect surface state whether a credential is scoped or unscoped? The proof's one standing pin asks for exactly that word, and today no envelope or screen emits it.
- **Q4 — The publish allow-list (Q4 = §4.2).** Keys have no persisted home. Is the allow-list a list of `Field_.path` values (no schema change), or does a stable key become a stored field (a fifth additive field, which §6.1 currently forbids)? **This is the one finding in this review that blocks a prototype step**, because endpoint 8's security test cannot be written until it is answered.
- **Q5 — Credential `scope`: capability or operation?** (§4.3) One `ReadSpec` per capability makes them the same string; more than one makes the contract's rule wrong. Which is the unit of scope?
- **Q6 — What happens to the old connections surface** (`api.py:2092`–`:2223`, `providers/`, `api_manifest.py`)? §7 does not cover them, and one of them probes named services by adapter — the shape #323 says not to grow.
- **Q7 — Secret policy.** `rotated_at` is owner-side only and stored nowhere (Revision 2, NEW-2). Is a rotation reminder genuinely out of Worlds' hands, or should it be a card?

### 7.2 The coordinator's to reconcile (process, not product)

- **Q8 — The review file's path.** Revisions 1 and 2 of the contract record that `docs/vnext/connect-contract-review.md` "was not present in the worktree" and could not be matched one-to-one (`connect-contract.md:959`–`:963`, `:993`–`:995`, NEW-8). This review is at the path Rylee's brief names, `docs/vnext/reviews/2026-10-16-connect-contract-review.md`. Someone holding the original should confirm whether it is the same artefact or a third document, so the six unmatched MINOR/NIT ids are reconciled once and only once.
- **Q9 — Does this review supersede `connect-contract-rereview.md`?** No claim is made either way; the rereview graded Revision 1 and Revision 2 answered it. This document is the review Rylee's ballot asked for, at the tree as of `39beedb`, and its MAJOR/§4.2 findings are new.
- **Q10 — Citation refresh.** §6's table is a mechanical refresh of `path:line`, not a contract amendment. Whether to apply it is a contract edit, which is Rylee's to authorise.

## 8. What this review did not touch

- **No implementation change.** No file under `src/`, `tests/`, `ui/`, `config/` or `.github/` was edited.
- **No contract change.** `docs/vnext/connect-contract.md` keeps every word and its MOCKUP status. The
  findings above are for Rylee to accept, reject or defer.
- **No canon, merge, deploy or deletion**, and no change to owner auth, CSRF, step-up, secrets policy,
  confinement or the C3 lifecycle. Every one of those is cited as *existing evidence*, never as a proposal.
- **No protected invariant was evaluated for change**: provider-neutral lifecycle, credential references
  only, capability proposals, owner approval/revocation, confinement, receipts, zero-provider behaviour and
  the existing guarantees all read as intact in the code this review checked, and none of them is
  contradicted by anything written above.

## 9. Evidence

Every command below was run in this clone at `39beedb`.

| # | Command | Result |
|---|---|---|
| A | `git log --oneline -1 && git rev-parse --short HEAD` | `39beedb` |
| B | `python3 -c "import pytest"` / `import fastapi` / `command -v ruff` / `ls ui/node_modules` | all fail — **the suite was not run here** |
| C | `python3 /tmp/rev/check.py` (pydantic 2.12.5 present) | field/route/key assertions, output below |
| D | route inventory read (`scripts/route-inventory.json`) | `/api/config/*` is `owner`; `/api/connect/try` is `owner` |
| E | `grep -rn "@app\.(get\|post\|put\|delete)" src/personal_world/worlds/*.py` | 59 routes; **no `/api/connect/v1`** |

Command C, verbatim output:

```text
1 contract field, in models.py today:
   Auth.scope: PRESENT
   Request.provenance: PRESENT
   Request.verified: PRESENT
   Action.state: PRESENT
   Provider.governance: PRESENT
   Provider.principal_id: PRESENT
2 C1 Field_ fields: ['path', 'label', 'format', 'unit']
   Field_ has a 'key' field: False
3 Board fields: ['schema_version', 'id', 'title', 'home', 'items'] | home is a flag: True
4 Action.state default: adopted | Auth.scope default: None | Request.provenance default: owner
5 scope verdict is made on the request id's second segment: False (False = out of scope)
6 /api/connect/v1 routes in the tree: NONE
   live connect routes: ['/api/connect/try', '/api/connect/preview']
7 values keys are slugified from the field label: True
8 /api/config auth level (route-inventory): [{'auth': 'owner', 'method': 'DELETE', 'path': '/api/config/{kind}/{obj_id}'}, {'auth': 'owner', 'method': 'GET', 'path': '/api/config/{kind}/{obj_id}'}, {'auth': 'owner', 'method': 'PUT', 'path': '/api/config/{kind}/{obj_id}'}]
```

Test counts cited above, read from the tree: `tests/worlds/test_connect.py` — 25 tests over the two live
Connect routes; `tests/recipes/test_openapi_import.py:13` — the only caller of `from_openapi`;
`tests/vnext/test_connect_proof.py:268` — the one strict `xfail` still standing.

## 10. Findings

| Severity | Count | Ids |
|---|---|---|
| MAJOR | 2 | §4.2 (publish allow-list has no persisted home — blocks endpoint 8's security test), §5.1 (old connections surface and `providers/` are outside the Gate-0 inventory) |
| MINOR | 5 | §4.1 (four §6.1 fields exist with no writer), §4.3 (`scope` = operation, not capability), §4.4 (envelope rename is not one UI step), §4.6 (three sub-items), §7.1 Q6/Q7 (open owner questions) |
| NIT | 3 | §4.5 (board id vs `home` flag), §4.6 `truncated`, §6 (citation drift) |

**This review recommends no implementation.** Its one blocking item is Q4 in §7.1, which is a contract
shape decision; everything else is either drift a later edit absorbs or a question with a named owner.