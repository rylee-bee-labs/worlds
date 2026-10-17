# Records API — structured person data inside Memory

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the `/api/records*` contract (Records inside Memory) · **Read this if:** you are reading or changing the Records surface, its storage, or its gating.

**In short:** **Records** are a person's durable structured facts (medical
info, work history, identity documents, emergency contacts), stored inside
**Memory** as categories and served by `/api/records*`. Records are *not*
the Vault. This page is the API and storage contract; the product-language
rationale is in `PRODUCT-LANGUAGE.md` §"Records vs Vault". It sits under
[ARCHITECTURE.md](ARCHITECTURE.md), [SECURITY.md](../SECURITY.md), and the
identity boundary ([IDENTITY-BOUNDARY.md](IDENTITY-BOUNDARY.md)).

**Lane:** R-BE (backend).

---

## What Records are (and are not)

**Records = user information.** Medical info, work history, identity documents,
emergency contacts, and other durable *structured* facts a person keeps about
themselves. They live **inside Memory as categories** — Memory is the place,
Records are its structured half. They use *recognizable, assignable categories*
and require **step-up for sensitive categories**, exactly as the product
language specifies.

**Records are NOT the Vault.** The Vault is security/secrets infrastructure —
credentials, tokens, private keys. Records never import or call the Vault
(enforced by a test). The one fact that classifies a record never crosses into
secret material.

> **Memory must open with every model turned off.** Records are stored as core
> World state and served deterministically; no reasoning/chat provider is ever
> required to browse or edit them. AI may recall or suggest, but it is never
> the only way to reach them.

---

## Storage — reuse, invent nothing

A record is a **World `Fact`** (the core's existing structured key→value store)
persisted to the **caller's own `world.json`** through the per-principal storage function
(`_user_paths` → `identity.principal_scoped_path`, decision #13).

Why Facts and not a new table or a provider:

- **Shape.** `Fact = {key, value, provenance, classification}` is already a
  titled, categorized key-value entry. No new model is needed.
- **Disclosure profile.** Facts are *excluded* from shareable exports
  (`export.world_export` carries intents/policies/lore only) and appear solely
  in the encrypted backup artifact — precisely what personal records need.
  Records are additionally stored with `classification = private`.
- **Isolation.** Because they are stored in the caller's `world.json`, per-person
  isolation comes automatically: the same function that isolates prefs, layout,
  journal, reminders, and proposals (see
  [IDENTITY-BOUNDARY.md](IDENTITY-BOUNDARY.md)).
- **No new backend.** Facts, `save_world`/`load_world`, and the JSON store all
  already exist. Nothing is added to the storage layer.

Key scheme:

| What | Fact key | Value |
|---|---|---|
| a category | `records/category/<slug>` | `{slug, name, locked}` |
| a record | `records/item/<slug>/<id>` | `{id, category, category_name, title, fields, pinned, created, updated}` |

Every mutation also **appends a `JournalKind.SETTINGS_CHANGE` audit line to the
caller's own journal** — the same *state-in-the-World + audit-in-the-Journal*
split `PUT /api/sections` uses. The audit is **content-free**: it names the
category and the action (`record updated…`, `… pinned`, `… deleted`), never the
record's title or field values. The journal is append-only; the record's
*current* value is stored in the World.

The module (`src/personal_world/records.py`) holds pure functions over a
`World` — mirroring `prefs.py` / `sections.py` — so it is unit-testable without
HTTP. `api.py` adds only thin, guarded route handlers.

---

## Capabilities & gating

| Method | Path | Gate | Notes |
|---|---|---|---|
| GET | `/api/records/categories` | `require_auth` (person) | Names + counts + `locked` flag. Contents never included. |
| GET | `/api/records` | `require_auth` (person) | `?category=` lists one category; `?pinned=true` is the Overview feed; `?q=` is the deterministic find (below). |
| POST | `/api/records` | `require_step_up` (person) | Create/update a record; optional `locked` sets the category lock. |
| POST | `/api/records/pin` | `require_step_up` (person) | Pin for the Overview. |
| POST | `/api/records/unpin` | `require_step_up` (person) | Remove a pin. |
| DELETE | `/api/records` | `require_step_up` (person) | Delete a record. |

- **Writes are the step-up ACT.** Every mutation depends on `require_step_up` —
  the repo's server-side human-approval check, matching `/api/world/fact` and
  `PUT /api/sections`. The elevation is resolved by `_step_up_authorized`
  (a real session grant, true loopback, or a delegated proxy header that also
  carries a matching `X-PW-Proxy-StepUp-Secret`). **Client trust is never
  sufficient**: `X-PW-StepUp: 1` alone, with no proxy secret, is denied.
- **Locked-category reads.** Reading a locked category (`?category=<locked>`)
  returns an **HTTP 409 `status: "locked"`** envelope **unless that same
  request carries fresh step-up**, checked server-side by the same function. The
  category's name, count, and `locked` flag stay visible without elevation (so
  a person always knows what to unlock); the record titles and field values do
  not.
- **Person-only.** Agents are refused on every Records surface (`_require_person`),
  like the journal and prefs screens. `403 step-up is person-only` on writes;
  `403 person-only surface` on reads.

### Find: `?q=` (works with models off; gate G-memory)

`GET /api/records?q=<terms>` is the deterministic lexical find required by the
TRUE-NORTH **G-memory** gate ("pin + find a record with all models off"). It is
`records.search_records`: case-insensitive **substring AND-match** over each
record's title, category name, and field keys/values — **no index, no provider,
no embeddings, no model in the loop**. Ordering is total and stable (`updated`
desc, then `id` desc), so the same query over the same world always answers
byte-identically. A blank `q` is the plain browse view; a no-match `q` is the
`ok: true` empty list (a real zero). `?q=` composes with `?pinned=true`
and with `?category=` (find inside one category).

**Locking fails closed against find.** Locked-category records join `q` results
only when the request carries a server-verified step-up (`_step_up_authorized`,
the same check as the locked-category read); without elevation they are simply
absent — the query never errors, never leaks, and never reveals which locked
category would have matched. `?category=<locked>&q=` still returns the hard
**409** before any search happens.

> AI may add conversational recall on top (Chat is a shortcut), but this route
> is the base function: it never gates on, waits for, or degrades with any
> model. Proven by `tests/test_memory_models_off.py`.

### Locking

Locking is **per-principal** (stored on the caller's `world.json`) and is set
or cleared in the same step-up-gated `POST /api/records` write via the
`locked` boolean on the record's category. A locked category is never surfaced
by the browse aggregate or the pinned Overview feed.

---

## Degraded states

Records are a Memory feature, so every route first checks the **same**
`memory` provider `/api/memory/search` checks. With no memory provider
configured, the surface answers the capability-grid truth — never a fake-empty
success:

```json
{ "ok": false, "status": "unavailable", "warnings": ["no memory provider"] }
```

This holds for reads **and** writes (serving a write into an unbacked capability
would be a lie). A genuinely empty category with the provider present still
returns `ok: true` with an empty list — that is a true zero, not a mask.

---

## Errors

- `401` unauthenticated; `403` agent / person-only or missing write elevation.
- `409` locked category read without step-up; body `status: "locked"`.
- `400` malformed JSON body (or non-object).
- `422` validation: missing `title`, unusable `category`, non-scalar field
  values, non-boolean `locked`, field count/length over the caps.
- `status: "not_found"` (HTTP 200 envelope) when a pin/unpin/delete targets a
  record that isn't there — `ok: false`, state unchanged.

---

## Deferred to the owner (contract left these open — not guessed)

1. **A dedicated lock/unlock endpoint.** Lock state currently rides the record
   write (`locked` flag). If the owner wants an explicit
   `POST /api/records/categories/lock` surface, that is additive and unbuilt.
2. **How pinned records compose into the Overview.** The backend sets and
   reports `pinned` and serves `?pinned=true`; *where and how* Overview renders
   them is the frontend's call (out of this lane).
3. **Whether agent-driven record *proposals* should exist** (chat proposing a
   record through the approve→execute tree). The person-facing step-up path is
   what the contract describes; the agent proposal tool is not wired here.
4. **Category display names / icons.** `name` stores the human string as typed;
   the icon-plus-word pairing the product language asks for is a presentation
   concern for the Memory screen.
