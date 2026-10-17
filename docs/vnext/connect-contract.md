# Connect contract — vnext (issue #323)

> **Status: MOCKUP.** Nothing in this document is implemented. MOCKUP ≠ PROTOTYPE ≠ APPROVED.
> It describes a *shape*, and every shape below is a proposal until an issue says otherwise.
> No route here exists in the running application, no field below is stored, and no security test
> below is written. Where this document describes today's behaviour it cites the code; where it
> describes the future it says so in the tense it is written in.
>
> **Date:** 2026-10-13 · **Issue:** #323 · **Reads with:** [ADR-0008 — the front door](../adr/0008-front-door.md),
> [C1–C9 contracts](../rebuild/CONTRACTS.md), [product direction](../../.project/PLAN.md),
> [PROVIDERS](../PROVIDERS.md), [ROOMS](../ROOMS.md).
>
> **Also:** no new backend is proposed. See §7 for why, quoting #321's fit test.

## 0. The decisions this contract obeys

Quoted, not paraphrased:

- 2026-10-13 Rylee: "I'm wanting it to have a brand new design and new api connect layer. Honestly I don't know what all we're doing with it haha. It follows our newer gated jobs."
- 2026-10-13 issue #323: "Every field/endpoint must have a named consumer, a reason to exist and a security test." "Prefer normal providers exposing their own API, not bundling a new Sonarr/GitHub/Project Home implementation in Worlds."
- 2026-10-13 issue #321: "A new backend is allowed if justified by fit, not built merely because 'new' sounds better." "Credential *references* only, scoped access and no secret value round-trip into the browser."
- 2026-10-13 issue #319: "Worlds owns meaning. Providers own mechanics." External systems keep their own authority; Project Home owns its own consequential operations; Worlds shows/links, never mints competing authority.

Two consequences run through everything below:

1. **The vocabulary is provider-neutral.** The contract knows about *capabilities, fields,
   freshness and authority*. It does not know what a Sonarr, a GitHub or a Project Home is.
   A provider that ships an OpenAPI document and a provider that speaks `room/0` arrive through
   the same six verbs (§1) and differ only in the `dialect` string on the descriptor.
2. **Worlds never becomes a second authority for an external system.** Every consequential
   operation ends in an approval that the *governing* system issued, and `revoke` deliberately
   reports `external_state_untouched: true` — Worlds can drop its own reference, never the
   external system's own token.

## 1. The six verbs

A connection is registered once and then goes through six owner-initiated steps. Each step is a
separate endpoint, each step's output is durable, and each step is independently re-runnable.

**Durable, precisely.** Each step's output that is *state* survives the process; the rest is a
return value and says so. §6.1 is the exact list: a registered connection is the C1 config
objects it compiles to, and everything a connection does not need to remember is never written
anywhere. "Durable" here never means "a new store".

```text
discover ──▶ register ──▶ describe-capabilities
                │
                ├──▶ test ──▶ transform ──▶ publish
                │
                └──▶ propose-action ──▶ approve (Worlds | Project Home) ──▶ execute
                                         │
                              disconnect ─┴─▶ revoke
```

- **discover** — one bounded, read-only probe that returns a *candidate* capability list. Writes nothing.
- **register** — persist a provider, its credential **reference** and the capabilities the owner kept,
  through the existing config store, so the YAML files stay canonical truth ([C1](../rebuild/CONTRACTS.md#c1-config-files-canonical-truth)).
- **describe-capabilities** — the stored, typed capability description. No network.
- **test** — one bounded read through the confinement seam; returns `status` and `field` values
  with `source` and `freshness`. No network for the transform half.
- **transform** — turn a tested field set into a Worlds card draft (`status | field | card`).
  Pure: no network, no persistence.
- **publish** — *selective*: choose exactly which capability field keys land on Home, on which board.
- **propose-action** — describe a consequential operation the owner wants callable; Worlds records a
  proposal and an approval link, and stops.
- **approve / execute** — the existing C3 lifecycle. Untouched by this document.
- **disconnect / revoke** — stop showing, then drop the reference.

## 2. The typed contract

Types are written in a TypeScript-flavoured notation for readability. They are MOCKUP notation;
the implementation would be Pydantic models beside `src/personal_world/worlds/models.py`, because
that is where `schema_version: 1`, `extra="forbid"` and the id patterns already live.

```ts
// ---------------------------------------------------------------- identity
type ContractVersion = "connect/v1";
type ConnectionId = string;      // the C1 provider id: ^[a-z0-9][a-z0-9-]{0,62}$
type Dialect = "http-json" | "openapi-3" | "room-0";
type Authority = "worlds" | "external";
type SourceState = "healthy" | "needs_attention" | "degraded" | "unavailable"
                 | "stale" | "unknown" | "not_configured";
type Freshness = "current" | "stale";

// ------------------------------------------------------- discover / register
interface RegisterRequest {
  contract: ContractVersion;
  connection_id: ConnectionId;
  display_name: string;                    // the owner's words; never the vendor's product name
  dialect: Dialect;
  destination: { base_url: string; path_prefix?: string; network?: { lan: boolean } };
  credential?: CredentialReference;        // a REFERENCE. never a value.
  capabilities: Capability[];              // the ones the owner kept from discover
  principal?: PrincipalBinding | null;     // only when the external system requires one
  publish_target?: { board: string; publish: string[] };   // optional; may be empty
}

interface ConnectionDescriptor {
  contract: ContractVersion;
  connection_id: ConnectionId;
  display_name: string;
  vendor_label: string | null;             // shown, never adopted as Worlds vocabulary
  dialect: Dialect;
  authority: Authority;                    // who governs consequential operations
  principal: PrincipalBinding | null;
  credential: CredentialReference | null;
  capabilities: Capability[];
  published: PublishSelection;
  etag: string;                            // sha256 of the file bytes; config_store.py:445
  updated_at: string;                      // ISO-8601
}

// ------------------------------------------------ describe-capabilities
interface Capability {
  capability_id: string;                   // ^[a-z0-9][a-z0-9-]{0,62}$ inside the connection
  label: string;                           // the owner's words for this thing
  meaning: { concept: string; short: string; full?: string };   // WORLDS owns meaning
  reads: ReadSpec[];                       // bounded, read-only
  provenance: "owner" | "discovered" | "provider_declared";
  verified: boolean;                       // a foreman checked the shapes read-only against a real service
}

interface ReadSpec {
  operation: string;                       // stable within the capability
  method: "GET" | "HEAD";                  // read-only by construction; see Ledger §4.1
  path: string;                            // relative; validated at save, never at first render
  query?: Record<string, string>;          // closed template set only
  bounds: { timeout_s: number; max_bytes: number; ttl_s: number };
}

// ------------------------------------------------------ credential reference
interface CredentialReference {
  ref: `env:${string}` | `vault:${string}` | `file:${string}`;
  auth: "none" | "bearer" | "header" | "basic" | "cookie_session" | "password_grant";
  header_name?: string;                    // may not be a framing or forwarding header
  scope: string[];                         // capability_ids this credential may be sent to — nothing else
  rotated_at?: string;                     // OWNER-SIDE ONLY: accepted and echoed, never stored (§6.1)
}

// ------------------------------------------------------------- test result
interface TestRequest {
  capability_id: string;
  operation?: string;                      // defaults to the capability's only/first read
  assertions?: { status?: number; path?: string; exists?: boolean; is_list?: boolean; equals?: Json }[];
}

interface FieldValue { key: string; text: string; raw?: Json }   // missing is {text:"unknown"}, never 0

interface TestResult {
  contract: ContractVersion;
  capability_id: string;
  source: {
    connection_id: ConnectionId;
    request_id: string;                    // the C1 request this ran as
    method: "GET" | "HEAD";
    path: string;
    status_code: number | null;
    duration_ms: number | null;
    error_class: ErrorClass | null;        // the C2 vocabulary, unchanged
    note?: string;                         // redacted, ≤300 chars, never a body
  };
  freshness: Freshness;
  state: SourceState;
  observed_at: string;                     // ISO-8601
  fetched_at: string;
  last_good_at: string | null;
  values: Record<string, FieldValue>;
  meter?: { type: string; text_equivalent: string } | null;
  truncated: boolean;
}

// -------------------------------------------------------------- transform
interface CardDraft {
  card_id: string;                       // Worlds' id grammar: ^[a-z0-9][a-z0-9-]{0,62}$ (models.py:11)
  connection_id: ConnectionId;
  capability_id: string;
  title: string;
  meaning: { concept: string; short: string; full?: string };
  fields: { key: string; label: string; format: string; unit?: string }[];
  status_map?: { path: string; healthy: Json[]; needs_attention: Json[]; mode: "first" | "all" | "any" };
  source_state: SourceState;
  freshness: Freshness;
  source: TestResult["source"];
}

// ------------------------------------------------- selective publish
interface PublishSelection {
  board: string;
  published: string[];                     // exactly the field keys that land on Home
  hidden: string[];                        // capability ids that stay in Connect and go no further
  published_at: string | null;
  published_by: "owner" | null;            // never an agent token
}

// ------------------------------------------------- independently-governed action
interface ActionProposal {
  contract: ContractVersion;
  proposal_id: string;
  connection_id: ConnectionId;
  capability_id: string;
  operation: string;
  label: string;
  effect: "write";                         // a proposal is always for a consequential operation
  scope: string;
  idempotency: "required" | "optional" | "none";
  exposed: false;                          // an agent token is never a caller of an adopted external write
  approval: ApprovalLink;
  state: "proposed" | "adopted" | "refused" | "expired";
}

type ApprovalLink =
  | { kind: "worlds"; authorization_id: string; approve_at: string }
  | { kind: "project_home"; room_url: string; action_ref: string; record_at: string };

// ------------------------------------------------------- disconnect / revoke
interface DisconnectResult {
  disconnected: true;
  published_cleared: string[];             // card ids removed from Home
  caches_dropped: string[];               // last-good snapshots and back-off
  credentials_retained: string[];         // the ref stays; nothing is sent
  pending_authorizations: string[];       // listed, never silently cancelled
}

interface RevocationResult {
  revoked: true;
  credential_ref_removed: string | null;  // the ref string, never its value
  held_credentials_purged: number;        // in-process sessions/tokens dropped
  config_deleted: string[];               // provider/request/card/action ids removed
  external_state_untouched: true;         // Worlds cannot revoke the external system's own token
}
```

## 3. Endpoints

Every endpoint is owner-only with CSRF, as a write in the front door is today
(`src/personal_world/worlds/connect_routes.py:120`). "Network" says whether the call leaves the box.

| # | Method + path | Consumer (named) | Reason to exist | Network | Security test |
|---|---|---|---|---|---|
| 1 | `POST /api/connect/v1/discover` | Connect UI, Discover step (today `/api/connect/try`, `ui/src/fd/api.ts:180`) | Return a candidate capability list before anything is saved | 1 bounded read | Untrusted document bounds (size/depth/nodes/operations); GET+HEAD only; `servers[]` ignored in favour of a synthetic placeholder (`recipes.py:163`); unmapped auth leaves `needs_auth: unknown`, never a silent `none` (`recipes.py:328`) |
| 2 | `POST /api/connect/v1/connections` | Connect UI, "Keep these"; `framework.py:126` config validation | Persist provider + credential ref + kept capabilities through `ConfigStore` so YAML stays canonical | no | Id validated *before* a path is built (`config_store.py:119`); placeholder `base_url` refused (`recipes.py:589`); `If-None-Match: *` on create, real etag on update |
| 3 | `GET /api/connect/v1/connections` | Connect UI, connection list; Connect empty state (`ui/src/fd/Connect.tsx:711`) | Show what is connected without opening each file | no | Owner-only; descriptor is a reference-only projection of C1 files, so it cannot leak more than the config already holds |
| 4 | `GET /api/connect/v1/connections/{id}` | Connect UI, connection detail | One read of the stored descriptor | no | Owner-only; `Cache-Control: no-store` |
| 5 | `GET /api/connect/v1/connections/{id}/capabilities` | Connect UI, capability list; `GET /api/boards/home` for what is published | The stored typed capability description, no network | no | Owner-only; no capability is callable from here — descriptions are not authority |
| 6 | `POST /api/connect/v1/connections/{id}/test` | Connect UI, "Test this"; the recipe `verified: false` gate (`recipes.py:69`) | One bounded read → `status`/`field` values with `source` + `freshness` | 1 bounded read | Read effect only — a write is refused 422, as `connect_routes.py:115` does; rate-limited 10/min (`connect_routes.py:34`); sample scrubbed before it is serialized (`connect_routes.py:191`); `PW_*`/`OIDC_*`/`BOOTSTRAP` refs refused (`connect_routes.py:37`) |
| 7 | `POST /api/connect/v1/connections/{id}/transform` | Connect UI, "Make a card" | Turn a `TestResult` into a `CardDraft`; pure, so the owner can iterate with no network | no | Sample size and depth caps (`connect_routes.py:36,159`); a JSONPath subset with no filters or scripts, validated at save (`models.py:26`); no write ever happens here |
| 8 | `POST /api/connect/v1/connections/{id}/publish` | Connect UI, "Show this on Home"; `production.py:91` `home_extra` | **Selective** publish: pick the exact field keys and board; everything else stays in Connect | no | `published` is an allow-list, never a default-on wildcard; a hidden capability is absent from `GET /api/boards/home` payloads entirely; an agent token is refused; publishes only a `CardDraft` the owner already saw from a `test` |
| 9 | `POST /api/connect/v1/connections/{id}/actions` | Connect UI, "Make this callable"; `actions_routes.py:60` | Propose a consequential operation and get an approval link; sends nothing | no | `exposed: false` is not settable here; `approval: never` on a write refused unless the owner's explicit waiver is in config (`config_store.py:355`); `idempotency: required` for an external write |
| 10 | `POST /api/connect/v1/connections/{id}/actions/{proposal_id}/adopt` | Connect UI, action row | Turn a proposal into a callable C1 request + action | no | Sends nothing (`room0.py:604`); the request it creates carries no body; an id a provider could not have minted is refused 400 (`room0.py:546`) |
| 11 | `POST /api/connect/v1/approvals/{authorization_id}/approve` | Home → Needs a look → approve (`production.py:82`); `actions_routes.py:71` | The one Worlds approval path, step-up required | no | Step-up inside 120 s or refused (`dispatcher.py:262`); an agent token never approves; a `project_home`-governed connection cannot be approved here at all |
| 12 | `POST /api/rooms/{provider_id}/actions/{room_action_id}/answer` — **existing path, unchanged** (`room_routes.py:52`) | Project Home, on its own approve, coming back through the room's answer route; `room0.answer` (`room0.py:581`) | Carry the approval id for an operation Project Home governs. Worlds records that approval; it never re-decides it. **There is no separate Connect endpoint for this** — the room's own route already owns it | 1 bounded read to the room, then the governed write | `project_home_approval_id` is honoured only for a provider Project Home governs (`room0.py:598`); the id is verified before it is recorded, and with no verifier supplied the route is refused 403 (`dispatcher.py:277`–`:278`, `room_routes.py:76`); a `worlds`-governed provider cannot come this way at all — its answer takes `dispatcher.approve` instead (`room0.py:600`) |
| 13 | `POST /api/connect/v1/connections/{id}/disconnect` | Connect UI, "Stop showing this" | Stop publishing and drop caches without deleting config | no | Refuses while an authorization is pending unless the owner names them; never touches the external system |
| 14 | `POST /api/connect/v1/connections/{id}/revoke` | Connect UI, "Remove this connection" | Drop the credential reference, purge held credentials, delete the config objects | no | Config deletes are refused while anything still references the object (`config_store.py:358`); held credentials purged (`confinement.py:298`); reports `external_state_untouched: true` and tells the owner to revoke at the provider |

Endpoints 11 and 12 are *the existing lifecycle*, not new machinery: both already exist
(`actions_routes.py:71` and `room_routes.py:52`) and are listed here so the Connect flow has one
place to point at. Neither is proposed under `/api/connect/v1/`: a path that already works is not
moved for tidiness, and an approval is not re-homed to sit beside a discovery form.

## 4. Field ledger

The rule from #323, applied field by field. `consumer` is a named thing in this repo or a named
screen, not "the API".

### 4.1 `ConnectionDescriptor`

| Field | Consumer | Reason to exist | Security test |
|---|---|---|---|
| `contract` | Connect UI, migration check | Says which generation of the contract wrote this | Rejects anything but `connect/v1`; never guessed from a missing value |
| `display_name` | Home board item title; Connect list | Worlds owns meaning, so the owner names it, not the vendor | Length-bounded; never rendered as markup; a name that reads as a URL is not turned into a link |
| `vendor_label` | Connect detail, for the owner's own recognition | The owner's "what is this thing called" | Shown, never used as an id, never used as a vocabulary term, never matched against |
| `dialect` | Dispatch, at the boundary only | Chooses which read adapter and which auth exchange applies | A closed enum; an unknown dialect is refused at register, not defaulted |
| `authority` | `actions_routes` approve/record split | Decides *who* may approve — the single most consequential field here | `external` on a provider whose operations the owner cannot approve in Worlds; defaults closed (`models.py:203`) |
| `principal` | The sender's identity header, for `room-0` | Some systems require Worlds to say who it speaks for | Connect's `PrincipalBinding` projects onto the string `Provider.principal_id` (`models.py:180`) — `person_ref` is the whole of it in v1, and a binding carrying any other part is refused at register rather than dropped. Pattern-validated at save and again at send (`confinement.py:606`); never taken from a request header |
| `credential` | The sender only | The provider needs a credential; the browser must never see one | Reference-only; a value anywhere in the body is refused by `extra="forbid"` because no model has a field for it |
| `capabilities` | Connect capability list; `describe-capabilities` | The typed thing a connection *has* | Every entry is read-only; a write-shaped capability cannot be expressed here (see §4.5). Ledgered field by field in §4.8 |
| `etag` | The owner's next edit | Optimistic concurrency, as C1 requires | 409 on mismatch; `If-Match: *` refused with 428 |
| `updated_at` | Connect "changed" hint | The owner can tell stale config from current | Never used to decide freshness — that comes from `fetched_at`/`last_good_at` |

### 4.2 `CredentialReference`

| Field | Consumer | Reason to exist | Security test |
|---|---|---|---|
| `ref` | `secrets.resolve_secret_ref` at send time | Names a secret without holding it | Regex-bounded at save (`models.py:15`); Worlds' own `PW_*`/`OIDC_*`/`BOOTSTRAP` names refused for unsaved providers (`connect_routes.py:101`) |
| `auth` | The sender's credential exchange | *How* to present it | Closed enum; `none` is never chosen silently for a scheme the discovery step did not understand |
| `header_name` | The sender | Names a non-standard header | May not be a framing, forwarding or `sec-` header (`models.py:53`); re-checked at send (`confinement.py:246`) |
| `scope` | The sender, before it dials | **Scoped access**: this credential may only be sent to the listed capabilities | A capability outside `scope` is `auth_failed` before any socket opens — no DNS, no bytes |
| `rotated_at` | Nowhere in Worlds — the owner's own password manager or notes | The owner's own reminder; Worlds never guesses a rotation date and keeps no copy of one | Accepted on the way in and echoed in endpoint 2's receipt; never written to any file, because `Auth` is `extra="forbid"` (`models.py:101`) and no C1 object has a field for it. Never used to decide whether a credential is still valid |

### 4.3 `TestResult`

| Field | Consumer | Reason to exist | Security test |
|---|---|---|---|
| `source.connection_id`, `request_id` | The detail view's evidence strip; `Home → needs a look` | Which request produced this | Must match a stored read request; an unsaved id is refused. No results table backs it: `worlds.db`'s `history` is an append-only audit log for memory rows (`kept`/`later`/`records`), not a store of reads, and `find_index` only mirrors those three (§6, §6.1) — so a `TestResult` lives exactly as long as the response and the in-process last-good snapshot |
| `source.method`, `path` | The detail view's evidence strip | Which call it was | Path re-validated at send (`confinement.py:201`); `..`, `%2e`, `\` and control characters refused |
| `source.status_code`, `duration_ms`, `error_class` | Needs-a-look grouping; degraded-mode copy | Why it failed, in the C2 vocabulary | Classified, never free text from the provider |
| `source.note` | The same strip | A short human reason | Scrubbed against every live secret, then cut to 300 chars (`connect_routes.py:176`) |
| `freshness`, `fetched_at`, `last_good_at` | Home freshness text; C5 accessibility copy | Availability and freshness are separate things | Last-good values are *always* labelled `stale`; a card is never shown as current on last-good data |
| `state` | Needs-a-look grouping; whole-world strip | The Play-Nice word | Bounded vocabulary; `not_configured` is never a Home row (`CONTRACTS.md` C6) |
| `values` | The card, the accessibility name, agent answers | What the person actually sees | Missing is `{text:"unknown"}`, never 0; an empty list is `none`, never unavailable; every path is the validated JSONPath subset |
| `meter` | The card's meter + `text_equivalent` | A number with a text equivalent | An unresolvable source is **omitted**, never 0; only numbers/booleans/strings survive, ≤200 items |
| `truncated` | Connect's honest-copy path | Tells the owner the sample is partial | Set whenever a cap fired; a truncated sample can never become a published field |

### 4.4 `PublishSelection`

| Field | Consumer | Reason to exist | Security test |
|---|---|---|---|
| `published` | `GET /api/boards/home` (`production.py:91`) | Exactly which field keys are shown | An allow-list of `TestResult.values` keys (`_KEY_RE`, `models.py:364`), never a default-on wildcard. Empty means nothing is published. A key no `test` produced is refused — checked at endpoint 8, which is where a `publish_target` declared at register is finally held against the result the owner actually saw |
| `hidden` | Connect detail; endpoint 8's receipt | Makes "kept but not shown" visible rather than silent | A hidden capability appears in no board payload, no agent answer and no card; the only place it is named is the receipt and Connect detail, so nothing is dropped silently |
| `board` | The home board the card joins | Where it lands | Must be an existing board; a card with no board is `not_configured` |
| `published_at`, `published_by` | Endpoint 8's publish receipt — the confirmation line Connect shows the owner; the durable record of a publish is the card file's own `etag`/`updated_at` from the config store | When the owner published, not when the provider last answered | Returned by the call that made the change and **stored nowhere**: `BoardItem` is `extra="forbid"` (`models.py:447`) with no timestamp, so nothing in C1 config could hold it (§6.1). `published_by` is always `owner`; an agent token cannot set it |

### 4.5 `ActionProposal`

| Field | Consumer | Reason to exist | Security test |
|---|---|---|---|
| `effect` | `_check_action_policy` | A proposal is always for something consequential | Literal `"write"`; it cannot be constructed as a read |
| `scope` | Agent answer filtering; the dispatcher | Which capability the action belongs to | A caller's scope is checked against this before an authorization is even requested |
| `idempotency` | The dispatcher's single-attempt rule | A retry must be safe or must not exist | A write with no idempotency key is refused, not retried |
| `exposed` | Agent visibility | An adopted external write is **not** an agent tool | Literal `false`; not settable from any endpoint in §3 |
| `approval` | Home → approve; the external room | Names *who* must approve and where they approve | An `authority: external` connection cannot be approved at endpoint 11 |
| `state` | Connect's action row | Proposed ≠ adopted ≠ executed | `adopt` sends nothing; `execute` needs a consumed authorization |

### 4.6 `Disconnect` / `Revoke`

| Field | Consumer | Reason to exist | Security test |
|---|---|---|---|
| `published_cleared` | Home | The cards leave, and the owner sees exactly which | Delete refused while another object still references the card (`config_store.py:358`) |
| `caches_dropped` | Connect detail | A disconnected connection must not keep answering from a last-good snapshot | Same lock `snapshot()` uses, so a disconnect cannot race a fetch |
| `credentials_retained` | Connect detail | Disconnect is reversible; the owner can see what stayed | Never printed as a value; a `ref` string only |
| `pending_authorizations` | Connect detail | A disconnect does not silently cancel a pending approval | Listed and named; cancelling is a separate, explicit owner act |
| `held_credentials_purged` | Connect detail; `confinement.py:298` | A revoked connection must not keep a live session in process memory | Count only; the token itself is never echoed, logged or returned |
| `external_state_untouched` | Connect detail | Worlds cannot revoke someone else's token — saying so is the honest answer | Literal `true`; the UI must tell the owner to rotate at the provider |

### 4.7 `CardDraft`

The thing that becomes a C1 `Card` on publish (§6.1), so every field here has a config object on
the other side of it. Nothing in this table is a new kind of card — it is the C1 card model,
described in Connect's vocabulary.

| Field | Consumer | Reason to exist | Security test |
|---|---|---|---|
| `card_id` | The board item (`boards/*.yaml`); Home's item id | One card per published capability, in Worlds' id grammar | A **single** segment — `ID_RE` (`models.py:11`) takes no dot — validated *before* a path is built (`config_store.py:119`); a provider-supplied id is never used as the card id |
| `connection_id`, `capability_id` | Connect's card list; the drill-down from Home back to Connect | Which connection and capability the card came from | Both must exist in the stored descriptor; a draft naming a capability the connection does not have is refused 422 — the draft is never a way to invent one |
| `title` | The Home board item title | Worlds owns meaning, so the owner names it | ≤120 characters (`models.py:425`); never rendered as markup; a title that reads as a URL is not turned into a link |
| `meaning` | The C5 accessibility name; agent answers | The plain-language statement of what this card is for | Owner/foreman words only; a provider string is never promoted into `concept` or `short`; `short` is length-bounded |
| `fields` | The card body; the publish allow-list | Exactly the field keys the owner will see | Every key exists in the `TestResult.values` it was built from; no key from a `truncated` sample; every path re-validated against the JSONPath subset at save (`models.py:26`) |
| `status_map` | The Play-Nice status word | The one explicit provider→Play-Nice table | Closed vocabulary; a provider value absent from the table reads `unknown`, never `healthy`; `mode` is the existing closed enum (`models.py:357`) |
| `source_state`, `freshness` | Card freshness copy; C5 | The sample's honesty travels with the card | A draft built from a `stale` result publishes only as `stale`; `freshness: current` is refused when `last_good_at` is set |
| `source` | The detail view's evidence strip | Which read produced this card | Copied from the `TestResult` the owner already saw, already scrubbed (`connect_routes.py:191`); no path, request id or status the test did not return |

### 4.8 `Capability` and `ReadSpec`

The capability is what a connection *has*; a `ReadSpec` is the one bounded, read-only shape a
`test` may run. Together they compile to `requests/` + `cards/` (§6.1).

| Field | Consumer | Reason to exist | Security test |
|---|---|---|---|
| `Capability.capability_id` | Card ids; `CredentialReference.scope`; `ActionProposal.scope` | The stable name a credential, a publish selection and an action all refer to | Id grammar at save; unique within a connection; a `scope` entry naming no capability is refused rather than ignored |
| `Capability.label` | The capability list; the card title before publish | The owner's words for this thing | ≤120 characters; never markup; a vendor string is shown as `vendor_label`, never as the label |
| `Capability.meaning` | `Card.meaning`; agent answers; Home | Worlds owns meaning; the provider does not | `concept`/`short` are owner- or foreman-written. A discovery document cannot set them — endpoint 1 returns candidates only, and nothing from it is saved until endpoint 2 |
| `Capability.reads` | Endpoint 6 (test); endpoint 7 (transform) | The bounded shapes a test may run | Non-empty; every entry validates as a `Request`; one entry is one request file, which is where that read's `provenance`/`verified` live (§6.1); see the `ReadSpec` table below |
| `Capability.provenance` | Connect detail ("who says this exists?") | An owner-named read and a provider-declared read are not the same claim | Stored on each of the capability's request files, defaulting to `owner` (§6.1); a capability reads its own label as the **weakest** provenance any of its requests carries — one provider-declared read in a list makes the whole capability provider-declared, so a badge can never over-claim |
| `Capability.verified` | The `verified: false` gate (`recipes.py:69`); the detail badge | "Somebody checked these shapes read-only against a real service" is a different word from "it worked once" | Stored on each request, defaulting to `false`; a capability is verified only when **all** of its reads are, because a foreman checked shapes, not intentions. Set only by a foreman's read-only check; **never** inferred from a passing `test` — merging those two words is how a status gets overstated |
| `ReadSpec.operation` | Endpoint 6's `operation` selector; the evidence strip | A stable name for which read ran, within the capability | Unique within the connection — it is half the request id, and `REQUEST_ID_RE` (`models.py:14`) allows only two segments; an unknown operation is refused 404, not silently run as the first read |
| `ReadSpec.method` | The sender | Read-only by construction | Literal `GET` or `HEAD`; refused at save *and* re-checked at send (`confinement.py:577`); a write cannot be expressed here at all |
| `ReadSpec.path` | `build_url`, at send | The read's address, relative to `path_prefix` | Relative only; `..`, `%2e`, `\`, control characters and an absolute URL refused at save, and re-validated at send (`confinement.py:201`) |
| `ReadSpec.query` | The sender | The closed template set a read may carry | Keys and values match `Request.query` (`models.py:245`); no repeated keys; nothing interpolated from live input — a value that must vary comes from a stored request |
| `ReadSpec.bounds.timeout_s` | The send deadline | A read cannot outlive the owner's patience | Written to `Request.timeout_s` (`models.py:251`) as the per-read override and must be ≤ the provider's `timeout_s` (`models.py:184`); a larger value is refused, not silently clamped |
| `ReadSpec.bounds.max_bytes` | The raw-byte cap | A read cannot flood the process | Must be ≤ the provider's `max_bytes` (`models.py:185`); raw bytes are counted and never decompressed, and an encoded body is refused outright (`confinement.py:804`–`:809`) |
| `ReadSpec.bounds.ttl_s` | The freshness decision | How long a good answer stays good | 0–86400, as `Request.ttl_s` (`models.py:250`); `ttl_s: 0` means every read is live and nothing is served from a snapshot |

## 5. Threat and authority

### 5.1 Threats

| Threat | Where it enters | Control in this contract | Already in code at | Security test to write |
|---|---|---|---|---|
| SSRF into loopback, private or link-local ranges, or DNS rebinding between resolve and dial | 1, 6, and every dispatch | One confinement seam; resolve once, classify every answer, dial a pinned IP literal | `confinement.py:136`, `:593` | "A rebinding resolver whose second answer is the cloud metadata address sends nothing" |
| Cloud metadata theft, even for a `lan: true` provider | 1, 6 | Metadata refused unconditionally | `confinement.py:82`, `:155` | "`network.lan: true` does not unblock the cloud metadata address" |
| Borrowing a Worlds secret to call an attacker's URL | 1, 2, 6 | Unsaved providers may name a ref; Worlds' own names are refused | `connect_routes.py:37`, `:101` | "`env:PW_BOOTSTRAP_TOKEN` is refused with 422 and no request is sent" |
| A secret value round-tripping into the browser | 1, 6, 7 | References only; samples redacted *before* serialization | `connect_routes.py:191`; `production.py:88` | "A response body echoing the live token has that token replaced in the sample" |
| A credential sent to a capability outside its scope | 6, dispatch | `CredentialReference.scope` checked before dialling | new (scoping is new; the send is `confinement.py:228`) | "A capability outside `scope` fails with no DNS lookup" |
| A write smuggled through test/transform | 6, 7 | Read effect only; `effect: write` refused | `connect_routes.py:115`; `confinement.py:577` | "`POST` on the test endpoint is 422 and nothing is sent" |
| Auto-approving a consequential operation | 9, 11 | `approval: always` default; the dispatcher re-checks; an agent token is never approval | `config_store.py:349`; `dispatcher.py:262` | "A hand-edited action with `approval: never` is still refused at dispatch" |
| Hostile capability document (bomb, deep nesting, remote `$ref`, operation flood) | 1 | Bounded document; local refs only; synthetic placeholder address | `recipes.py:165`–`:217` (to be moved, §7.4) | "A 3 MB / 10 000-node document is refused with a plain message" |
| Over-broad publish leaking a provider's whole surface to Home and agents | 8 | `published` is an allow-list; `hidden` is explicit | new | "A capability not in `published` appears in no `/api/boards/home` payload" |
| Stale data shown as current | 6, 7 | `freshness` + `last_good_at` on every result | `room0.py:434`; C2 | "A failing provider's card reads `freshness: stale`, never `current`" |
| Cross-origin link injection from a provider descriptor | 8, and any `link` | Links are same-origin paths or they are dropped | `room0.py:71` (rule 6) | "`https://elsewhere.example/` in a link is dropped, not rendered" |
| Action-id collision or look-alike ids | 9, 10 | A short hash of the raw external id rides along | `room0.py:540` | "`a.b` and `a:b` and `a-b` do not collide" |
| Unbounded typed input from a provider | 9 | ≤20 choices, ≤120 chars, duplicates collapse | `room0.py:210` | "A 5000-choice descriptor yields 20 and stays a valid action" |
| Redirect escape | 6, dispatch | Never followed | `confinement.py:776` | "A 302 is `redirect_refused`, and the Location target is never dialled" |
| Decompression bomb | 6 | `identity` only; raw bytes counted against the cap | `confinement.py:809` | "A 100 KB body that expands to 100 MB is `too_large`" |
| A revoked connection that keeps working | 13, 14 | Purge held credentials; delete config; drop caches | `confinement.py:286`–`:301` | "After revoke, a second call resolves no credential and sends nothing" |
| Worlds minting authority an external system already owns | 9–12 | `authority` is recorded, not assumed; approval links point outward | `models.py:203`; `dispatcher.py:284`, `:288` | "An `external`-governed connection cannot be approved at endpoint 11" |

### 5.2 Authority

Who decides what, and who never decides it. This table is the one that must survive every
future change to the contract.

| Actor | Decides | Never decides | Enforced at |
|---|---|---|---|
| **Owner** (session + step-up) | What a connection is named; which capabilities are kept; which fields are published; which actions may be adopted; whether to disconnect or revoke; approval for `worlds`-governed operations | Cannot approve on Project Home's behalf for a connection it governs; cannot bypass its own step-up | `actions_routes.py:71`; `dispatcher.py:262` |
| **Project Home** (or any external governor) | Consequential operations on connections it governs; it issues its own approval id | Does not read Worlds memory, does not become a Worlds config object, does not learn what else the owner connected | `dispatcher.py:277`–`:278`, `:288`; `room0.py:598`–`:599`; `models.py:203` |
| **Worlds** | Meaning: labels, field selection, board membership, freshness and state words, and which capabilities exist as *descriptions* | Does not execute an externally governed operation without that system's approval; does not mint a status an external system contradicts | `production.py:82`; `config_store.py:349` |
| **The provider** | Its own mechanics: its API, its auth, its rate limits, the truth of its own data, the approval of what it governs | Does not become Worlds vocabulary; a provider-declared capability is `verified: false` until a foreman checks it | `recipes.py:69`; §4.5 `verified` |
| **Agent token** | Exposed read actions within scope, nothing else | Never approves, never publishes, never adopts, never disconnects, never revokes, never proposes | `exposed: false`; `dispatcher.py:210` |
| **A discovery document** (OpenAPI or otherwise) | Candidate capability *proposals*, each labelled with `provenance` | Never capability truth; never a credential; never an address Worlds will dial | `recipes.py:146`–`:160` |

## 6. Version and migration impact

**Version rules.** A connection descriptor declares the contract that wrote it. Within
`connect/v1`, changes are additive: a new optional field, a new `dialect`, a new endpoint. A
removal, a rename, or a change to the meaning of an existing field is `connect/v2`, and a v1
descriptor keeps being read by v1 code. There is no in-place migration of a stored connection: to
move to v2 the owner re-registers, and the old config objects stay readable until they are deleted
by hand.

### 6.1 What v1 persists, and where

The rule this section replaces is the earlier blanket claim that v1 adds "no new field, file,
model or table". That claim was wrong: a contract with persisted state has to say where the state
lives, and this one does have state. The honest version is narrower and specific:

> **v1 adds no new file, no new table, no new `kind` and no new required field. It adds exactly
> four additive optional model fields, each with a default that leaves every config file in this
> repository valid and unchanged.**

**Persisted — all of it in the existing C1 config files, which stay canonical ([C1](../rebuild/CONTRACTS.md#c1-config-files-canonical-truth)):**

| Contract type | Where it lives | New state |
|---|---|---|
| `RegisterRequest` / `ConnectionDescriptor` — identity, destination, credential ref, authority | `providers/<id>.yaml` (`Provider`); `principal` is stored as `Provider.principal_id` (`models.py:180`), a string, so a `PrincipalBinding` is exactly its `person_ref` in v1. The descriptor's own `etag`/`updated_at` are the config store's, computed from the file bytes (`config_store.py:445`), not stored separately | no |
| `ReadSpec` | `requests/<connection>.<operation>.yaml` (`Request`: `method`, `path`, `query`, `ttl_s`, `timeout_s`, `assertions`; `max_bytes` is provider-only — `models.py:185`). The id is `<connection>.<operation>` because `REQUEST_ID_RE` (`models.py:14`) is exactly two segments, so a three-segment name would not validate | two optional fields: `provenance`, `verified` — stored **per request**, and a capability is verified only when *every* one of its requests is (see §4.8) |
| `Capability.meaning` | `cards/<card-id>.yaml` (`Card.meaning`) — a card id is a **single** segment (`ID_RE`, `models.py:11`), so `<connection>-<capability>`, e.g. `cards/homelab-health-check-results.yaml` | no |
| `CardDraft`, once published | the same card file — `fields`, `status_map`, `meter` | no |
| `PublishSelection` | `boards/<board>.yaml`: `Board.items` is the published set, `BoardItem.hidden` (`models.py:450`) is the kept-but-not-shown set, and the card's own `fields` list *is* the field-key allow-list. `published_at`/`published_by` are the exception — see the *not persisted* table below | no |
| `ActionProposal` | `requests/` + `actions/<id>.yaml` (`Action`: `scope`, `idempotency`, `approval`, `exposed`) | one optional field: `state` |

**The four additive optional fields, and why each is needed.** This list is exhaustive, and the
table above it is exhaustive too: every §2 field that is stored anywhere lands in one of the two
tables, and the two §2 fields that are deliberately never stored — `CredentialReference.rotated_at`
and `PublishSelection.published_at` — are in the *not persisted* table below with the reason, not
here. Nothing is left unaccounted for between "persisted" and "not persisted".

| Field | Default | Why it cannot be derived | Why it breaks nothing |
|---|---|---|---|
| `Auth.scope: list[Id] \| None` | `None` | Which capabilities may receive a credential is a decision about *meaning*; nothing in a request or a card records it | `None` is exactly today's behaviour — the credential applies to the whole provider — so every existing provider file stays valid. Endpoint 2 always writes an explicit list, so anything Connect creates is scoped, and the fail-closed check in §4.2 applies to every Connect-written connection |
| `Request.provenance: "owner" \| "discovered" \| "provider_declared"` | `"owner"` | Whether a read shape came from the owner or from a provider document is not recoverable from the file after the fact | `"owner"` is the least-claimed label: nothing is attributed to a provider that did not say it |
| `Request.verified: bool` | `False` | Same word as `Recipe.verified` (`recipes.py:69`); it only means something if it is stored | `False` is the fail-closed default and is what every shipped recipe carries today |
| `Action.state: "proposed" \| "adopted" \| "refused" \| "expired"` | `"adopted"` | An `Action` has no state today, so "proposed but not adopted" cannot be expressed — and an adopt step that reads a proposal needs it to be *somewhere* between endpoint 9 and endpoint 10 | `"adopted"` is the only behaviour the dispatcher knows, so every existing action file behaves exactly as it does now. A `proposed` action is already inert: `exposed: false`, and a write still needs a consumed authorization to dispatch |

**Not persisted in v1 — deliberately, each with the place it lives instead:**

| Type | Where it lives | Why |
|---|---|---|
| discovery candidates | nowhere; returned once by endpoint 1 | A candidate is not a capability. Only what the owner keeps is written (endpoint 2) |
| `TestResult`, last-good values | nowhere durable. Last-good values stay in process memory exactly as a room's do (`room0.py:292`, `:319`) and are labelled `stale` | There is no results table in `worlds.db` to put them in, and adding one is the migration §6.2 refuses. The `history` table there is an append-only audit log for memory rows, not a results store (§6), so it is not a home for these either. A value survives the process only as long as a last-good snapshot does — which is why `freshness` is on every result |
| `CardDraft` before publish | nowhere; an owner iteration | Endpoint 7 is pure. Publishing is what writes a card |
| `PublishSelection.published_at`, `published_by` | nowhere; returned once by endpoint 8 | The card's presence in `Board.items` is the record of *what* was published, and the card file's etag/`updated_at` (`config_store.py:445`) is the record of *when* the config last changed. `BoardItem` has no timestamp field (`models.py:447`), so a fifth additive field would be needed to keep one — which §7.1 forbids, and which would store a fact the config store already records |
| `DisconnectResult`, `RevocationResult` | nowhere; returned once | They are reports of an effect, not a record. After a revoke the provider, request, card, board-item and action files are gone, and *that absence* is the record |
| `CredentialReference.rotated_at` | nowhere — the owner's own password manager or notes | Worlds never guesses a rotation date, and there is nowhere in C1 config to put one: `Auth` is `extra="forbid"` (`models.py:101`) and has no such field. Endpoint 2 accepts the hint and echoes it in the receipt it returns; no file carries it, which is why it is **not** a fifth additive field |
| held credentials, back-off | process memory — the `_SESSIONS` map and its purge (`confinement.py:286`–`:299`) | Same as today |

**No agent writes config.** The config write routes are wired to `owner_dep`
(`production.py:68`, `:89`), and the action routes that can change an authorization take
`owner=` (`production.py:131`; `actions_routes.py:72`). So `published_by` is `owner` in v1 by
construction, not by a check the caller can fail — and a `TestResult` never carries a "who ran
this" question, because endpoint 6 takes an owner session and the evidence it returns names a
request, not a caller.

| Artefact | Today | In `connect/v1` | Impact | Who feels it |
|---|---|---|---|---|
| `schema_version: 1` in every config file | Canonical truth ([C1](../rebuild/CONTRACTS.md)) | **Unchanged** — v1 adds no config file and no required field. Four additive *optional* model fields, all specified in §6.1 | Every existing file stays valid: a file that omits the new fields reads as unscoped, owner-named, unverified and adopted | Nobody today; Connect-written files carry all four |
| Config file layout under `worlds/` | `providers/ requests/ cards/ boards/ actions/` | **Unchanged** — a connection *is* a provider plus derived requests, cards, board items and actions (§6.1) | None | Nobody |
| `Provider.kind` | `http \| room0 \| reference` | **Unchanged** — `dialect` is a Connect-level attribute, not a new kind | A third-party `kind` must not be added to make a dialect work | Owner, at register |
| `/api/connect/try`, `/api/connect/preview` | Live (`connect_routes.py:119`, `:142`) | Superseded by endpoints 6 and 7 | Kept until the UI moves; both return a `TestResult` under the new contract so the UI changes in one step, not two | Connect UI |
| Recipe install | A directory of YAML templates, installed by `recipes.install` | Replaced by endpoint 2 (register) | 16 shipped recipe directories become either importable descriptors or retired; the loader's validating half survives inside discovery (§7.4) | Owner, on the day the UI stops offering Recipes |
| OpenAPI import | `from_openapi`, a pure function with no production caller | Becomes the `openapi-3` discovery adapter | Same bounds, same refusals, same `needs_auth: unknown`; moved, not rewritten | Nobody, if the tests move with it |
| C3 action lifecycle | `request_authorization → approve → consume → dispatch` | **Unchanged** — the contract proposes, the existing lifecycle decides | None. A new backend here would be the "new because new" case #321 rules out | Nobody |
| `/api/rooms/*` | Live (`room_routes.py:16`) | **Unchanged paths**; reached in Connect through `dialect: room-0`, `authority: external` | The room flow becomes the reference implementation of an externally governed connection, not a special case | Nobody |
| `action_version` and per-file etags | Computed from action + request + provider (`config_store.py:373`) | **Unchanged** | A published edit still invalidates pending authorizations | Nobody |
| `worlds.db` tables | `sessions`, `agent_tokens`, `owner_state` (`authn.py:42`–`:49`); `authorizations`, `executions`, `leases` (`dispatcher.py:46`–`:60`); `kept`, `later`, `records` (`memory_store.py:42`–`:51`); `history` (`memory_store.py:56`–`:58`) and the `find_index` FTS table over those same three (`memory_store.py:61`); `schema_migrations` (`db.py:127`) | **Unchanged** — no table added. There is **no results table**, and that is why `TestResult` is not persisted (§6.1). The `history` table is an append-only **audit log for `kept`/`later`/`records`** — columns `id, at, actor, event, table_name, row_id, detail`, frozen by the `history_no_update` / `history_no_delete` triggers (`memory_store.py:59`–`:60`) — and `find_index` is an FTS mirror of those three tables. Neither is keyed by connection or request and neither is written by a `test`, so neither can hold a `TestResult` | None | Nobody |
| `needs_you` items | Pending authorizations + room needs (`production.py:75`) | **Unchanged** shape; a proposal with no authorization yet is not a needs-you item | A proposal is silent until someone acts on it — deliberate | Owner |
| `GET /api/boards/home` payload | Board items with display definitions, no request ids or paths | **Unchanged** — publish adds items, it does not change the payload | None | UI |

### 6.2 Migrations deliberately **not** planned, and why

- **No data migration.** `CONTRACTS.md` C1.3 fixes the rule and the owner restated it: config
  files are canonical and already round-trip. A v1 connection is readable by today's code, because
  it *is* today's config — the four optional fields in §6.1 default to today's behaviour, so
  today's files are v1 files.
- **No results store.** The tempting alternative to §6.1's "not persisted" row is a table of test
  results. That is a migration, it puts provider data in a database C1 says config files own, and
  nothing in §3 needs it: the owner sees a result in the same flow that produced it.
- **No new backend.** See §7.

## 7. Keep / adapt / replace

The calls, with the consumer evidence behind each. Evidence is `path:line` in this repository at
`786f506`.

### 7.1 `src/personal_world/worlds/config_store.py` — **KEEP**

It is the storage the new layer writes through. Changing it would be changing the canonical truth
to accommodate a design that has not been built yet.

| Consumer | Evidence |
|---|---|
| Config CRUD routes | `src/personal_world/worlds/server.py:45`, `:135`, `:291` |
| Production assembly, plus a second read-only view for redaction | `src/personal_world/worlds/production.py:86`, `:88` |
| C3 dispatcher | `src/personal_world/worlds/dispatcher.py:33`, `:154` |
| Connect workshop routes | `src/personal_world/worlds/connect_routes.py:28`, `:62` |
| Room routes | `src/personal_world/worlds/room_routes.py:11` |
| Seed config | `src/personal_world/worlds/seed.py:36`, `:46` |
| Room0 adapter | `src/personal_world/worlds/room0.py:30` |
| Recipe install | `src/personal_world/worlds/recipes.py:37`, `:567` |
| Framework validator | `src/personal_world/framework.py:44`, `:126`, `:152`, `:529` |
| Tests | `tests/worlds/test_config_store.py` (16 tests) |

**What Connect borrows, unchanged:** id validation before a path is built (`:119`), atomic writes
with `fsync` (`:425`), etag preconditions (`:276`), reference checks on save (`:326`), delete
refused while referenced (`:358`), and the computed action version (`:373`).

**What Connect must not add to it:** no new kind, no new file layout, no new table, no new
required field. The one thing it does add is specified exactly once, in §6.1: four additive
*optional* model fields (`Auth.scope`, `Request.provenance`, `Request.verified`, `Action.state`),
each defaulting
to today's behaviour. A connection that needs a fifth is a signal the design is wrong, not that
the store should grow.

### 7.2 `src/personal_world/worlds/confinement.py` — **KEEP as the only outbound seam**

Every endpoint that touches the network in §3 routes here. The fit test from #321 —
"a new backend is allowed if justified by fit, not built merely because 'new' sounds better" —
is answered by this table: the module already *is* the thing a new backend would have to be, and
it is already the tested thing.

| Consumer | Evidence |
|---|---|
| C3 dispatcher — every consequential operation | `src/personal_world/worlds/dispatcher.py:34`, `:165` |
| Connect workshop | `src/personal_world/worlds/connect_routes.py:29`, `:66` |
| Room0 client | `src/personal_world/worlds/room0.py:31`, `:289` |
| Companion | `src/personal_world/worlds/companion.py:27`, `:324`; `companion_routes.py:18`, `:26` |
| Reference provider (shares `Deadline`, `perform`) | `src/personal_world/worlds/reference_provider.py:42` |
| Runner (the C2 error vocabulary) | `src/personal_world/worlds/runner.py:35` |
| Tests | `tests/worlds/test_confinement.py` (30), `tests/worlds/test_confinement_auth.py` (40) |

**What Connect borrows, unchanged:** `classify_address` (`:136`), the metadata set (`:82`),
`build_url` (`:183`), the read-cannot-carry-a-mutating-method rule (`:577`), no redirects, no
retries, `trust_env=False` (`:770`), the raw byte cap (`:802`), the session key that includes the
whole provider identity (`:267`), and `secret_values` never reaching a note (`:554`).

**What is genuinely new, and where it goes:** `CredentialReference.scope` (§4.2) is a *decision*
before the send, so it belongs at the call sites that build a request — `dispatcher._resolve`
(`dispatcher.py:189`) and the new discover/test path — not inside the transport. A transport that
decided scope would have to know the capability graph, which is meaning, and meaning is Worlds'.

**Why not a new backend:** a replacement would have to re-prove SSRF refusal, credential
non-disclosure, the single-attempt rule and the recovery semantics, against the same tests, for no
gain in fit. That is the "new sounds better" case the owner ruled out on 2026-10-13.

### 7.3 `src/personal_world/worlds/room0.py` — **ADAPT**

The read path stays exactly as it is. What changes is that it stops being a *kind* of thing and
becomes one dialect of a provider-neutral connection.

| Consumer | Evidence |
|---|---|
| Production assembly — home items, card fallback, needs | `src/personal_world/worlds/production.py:32`, `:91`, `:93` |
| Room routes | `src/personal_world/worlds/room_routes.py:13`, `:16` |
| Tests | `tests/worlds/test_room0.py` (59 tests) |

**Keep as-is:** the last-good + back-off behaviour (`:302`, `:402`), the 2 s snapshot budget
(`:470`), same-origin link validation (`:71`), the honest `unknown` over a made-up value (`:142`),
the tone and autonomy fail-closed defaults (`:250`), the choice bounds (`:210`), the action-id
hash (`:540`), and `answer` refusing to shortcut authority (`:579`).

**Adapt, one behaviour, with a named consumer:** *selective publish*. Today every card a room
lists lands on Home (`room0.py:391` → `home_items` at `:493`). Under §4.4 the owner chooses. The
named consumer is Home itself — a room that publishes twelve cards the owner reads none of is a
"needs a look" section that never empties. Every other rule in C8 stands, and the change is
additive: an owner who wants everything keeps everything by publishing everything.

**Adapt, one authority path:** `authority` is read off the provider today through
`governed_by_project_home()` (`models.py:203`) and defaulted per kind. Under §5.2 it is an
explicit descriptor field, defaulted closed the same way. Same behaviour, one fewer inference.

**Known gap this contract exposes, not fixes:** `Dispatcher` accepts a `project_home_verifier`
(`dispatcher.py:160`) and production never supplies one (`production.py:95`). So
`record_project_home_approval` refuses on its first statement —

```python
if self._ph_verify is None:                                    # dispatcher.py:277
    raise NotPermitted("Project Home approval is not available")   # dispatcher.py:278
```

— which is **before** the write transaction opens. Nothing is stored: no row is updated, no
`authority` is written, no approval id is recorded anywhere. An externally governed action
answered through endpoint 12 today gets 403 (`room_routes.py:76`). An earlier draft of this
document said a recorded Project Home approval id is "stored but not verified"; that was wrong in
the unsafe direction — the honest statement is that the verify step has **no implementation**, so
the path fails closed end to end. Endpoint 12 is where that must be settled. Flagged here, not
silently designed around.

### 7.4 `src/personal_world/worlds/recipes.py` — **REPLACE the install path, KEEP the discipline**

The evidence for the split:

| Consumer | Evidence | Verdict |
|---|---|---|
| Framework validator, which loads every shipped recipe | `src/personal_world/framework.py:46`, `:198`, `:226` | **Keep the loader's validating half** — this is a real consumer |
| Shipped recipe directories | `config/recipes/` — 16 of them | Data, not code. Retired or converted; not a reason to keep a module |
| `install()` | **No caller anywhere in `src/`** — `grep -w install` over `src/` returns 31 hits, none of them `recipes.install` | **Replace.** An unreferenced writer with a UI stub is not a consumer |
| `list_recipes()` | No caller in `src/` | **Replace** with endpoint 3 |
| `from_openapi()` | No caller in `src/`; `tests/recipes/test_openapi_import.py:13` | **Adapt** into the `openapi-3` discovery adapter, with its tests |
| Connect UI | `ui/src/fd/Connect.tsx:711` — a stub panel that says no recipes are installed | **Replace** with endpoint 2 |
| Tests | `tests/recipes/` (29 tests), `tests/worlds/test_room_recipes.py` (2) | Move with the code they cover; do not delete a test to delete a module |

The valuable half is the *discipline*, and every item below is a security control with a test
behind it: `PLACEHOLDER_BASE_URL` so no recipe ever ships a real host (`:163`), the document bounds
(`:165`–`:217`), local-`$ref`-only (`:230`), auth schemes that map to nothing becoming a TODO with
`needs_auth: unknown` rather than a silent `none` (`:298`), `_is_placeholder` refusing an install
with the placeholder address (`:561`), and the `env:` name-only secret refs (`:255`).

**What replaces it:** endpoints 1 and 2. Registering a connection writes the same objects through
the same `ConfigStore` with the same validation, so nothing is lost — the recipes' job was to
avoid hand-writing YAML, and the Connect UI does that job better and with the same guards.

**Status words:** #320 (wiring the old recipe UI) stays parked. This document does not un-park it
and does not replace it; it says the install path has no consumer, which is the evidence a
future un-parking decision needs.

## 8. Worked integration A — a generic HTTP service (read-only)

**This is a MOCKUP walkthrough, not a verified connection.** The service is a plausible homelab
HTTP service of the shape `config/recipes/gatus/` already describes. Nothing below has been run
against a live service; `verified` stays `false` until a foreman checks the shapes read-only,
exactly as `recipes.py:69` requires.

**1. discover** — the owner points at the service. One bounded read; writes nothing.

```jsonc
// POST /api/connect/v1/discover
{ "contract": "connect/v1", "connection_id": "homelab-health",
  "destination": { "base_url": "http://gatus.lan.example:8080", "network": { "lan": true } },
  "credential": null, "dialect": "http-json" }

// → 200
{ "contract": "connect/v1", "dialect": "http-json",
  "candidates": [
    { "capability_id": "check-results", "provenance": "discovered", "verified": false,
      "reads": [{ "operation": "statuses", "method": "GET", "path": "/api/v1/endpoints/statuses",
                  "bounds": { "timeout_s": 5, "max_bytes": 1048576, "ttl_s": 60 } }] }
  ],
  "skipped": [], "notes": ["base_url is a synthetic placeholder; supply the real address at register"],
  "needs_auth": "bearer" }
```

Consumer: Connect's Discover step. If the service publishes an OpenAPI 3.x document, the
`openapi-3` dialect produces the same shape through `from_openapi`'s bounds; every method other
than GET/HEAD lands in `skipped` with `write-like: needs an approved action`, and an auth scheme
C1 cannot map leaves `needs_auth: unknown` rather than choosing `none` for you. Discovery is sent
with `"credential": null` and reports the requirement it found — `bearer` here — so the owner
supplies a *reference* at register, in step 2. Nothing in discovery ever holds a value.

**2. register** — the owner keeps one capability and names it in their own words.

```jsonc
// POST /api/connect/v1/connections
{ "contract": "connect/v1", "connection_id": "homelab-health",
  "display_name": "Homelab checks",
  "dialect": "http-json",
  "destination": { "base_url": "http://gatus.lan.example:8080", "network": { "lan": true } },
  "credential": { "ref": "env:EXAMPLE_TOKEN", "auth": "bearer", "scope": ["check-results"] },
  "capabilities": [{ "capability_id": "check-results", "label": "Are the checks passing?",
                     "meaning": { "concept": "homelab health",
                                  "short": "Are the homelab checks passing?" },
                     "provenance": "owner", "verified": false,
                     "reads": [{ "operation": "statuses", "method": "GET",
                                 "path": "/api/v1/endpoints/statuses",
                                 "bounds": { "timeout_s": 5, "max_bytes": 1048576, "ttl_s": 60 } }] }],
  "publish_target": { "board": "home", "publish": ["checks", "failing"] } }
```

`env:EXAMPLE_TOKEN` is a **name**, not a value, and an obviously synthetic one: the whole point is
that Worlds resolves it at send time and never holds or returns what it names (§4.2). It is a
well-formed ref — `SECRET_REF_RE` (`models.py:15`) requires a name after the colon, so a bare
`"env:"` is malformed and refused rather than read as "no credential" — and it is not a name
Worlds owns, which is what keeps it clear of the refusal in `connect_routes.py:37`/`:101` (§5.1).
A service that genuinely needs no credential takes `"credential": null`, as step 1 above does;
`auth: "none"` carrying a ref is not a third option.

`publish` names **field keys**, not labels: the two keys the owner's `test` below will produce
(`FieldValue.key`, §2, from endpoint 6), in the `_KEY_RE` grammar (`models.py:364`). The Play-Nice
state word is not one of them — it travels as the card's state, never as a published field.

`verified: false` survives registration on purpose. The owner has confirmed the *shapes*; nobody
has confirmed they against the live service. Merging those two words is how a status gets
overstated.

**3. test** — one read, bounded, scrubbed. `error_class` is the C2 vocabulary unchanged.

```jsonc
// POST /api/connect/v1/connections/homelab-health/test
{ "contract": "connect/v1", "capability_id": "check-results", "operation": "statuses",
  "assertions": [{ "status": 200, "path": "$.checks", "exists": true, "is_list": false }] }

// → 200
{ "contract": "connect/v1", "capability_id": "check-results",
  "source": { "connection_id": "homelab-health", "request_id": "homelab-health.statuses",
              "method": "GET", "path": "/api/v1/endpoints/statuses",
              "status_code": 200, "duration_ms": 41, "error_class": null },
  "freshness": "current", "state": "healthy",
  "observed_at": "2026-10-13T14:02:11Z", "fetched_at": "2026-10-13T14:02:11Z", "last_good_at": null,
  "values": { "checks": { "key": "checks", "text": "42" },
              "failing": { "key": "failing", "text": "0" } },
  "meter": { "type": "dots", "text_equivalent": "all 42 checks passing" },
  "truncated": false }
```

The request id is the C1 file the read ran as — one file per `ReadSpec`,
`requests/homelab-health.statuses.yaml` (§6.1) — and `provenance: "owner"` and
`verified: false` are stored on that file, so this capability reads back as owner-named and
unverified (§4.8). If the service is down, `state` becomes `unavailable`, `error_class` is
`connection`, and the `values` above come back as `last_good_at` values with `freshness: "stale"`.
Missing is `{"text": "unknown"}`, never `0`.

**4. transform** — pure, no network: `TestResult` → `CardDraft`, with the JSONPath subset paths
validated at save rather than at first render.

```jsonc
// POST /api/connect/v1/connections/homelab-health/transform   (body: the TestResult above)
// → 200
{ "contract": "connect/v1", "card_id": "homelab-health-check-results",
  "connection_id": "homelab-health", "capability_id": "check-results",
  "title": "Are the checks passing?",
  "meaning": { "concept": "homelab health", "short": "Are the homelab checks passing?" },
  "fields": [ { "key": "checks",  "label": "Checks",  "format": "count" },
              { "key": "failing", "label": "Failing", "format": "count" } ],
  "source_state": "healthy", "freshness": "current",
  "source": { "connection_id": "homelab-health", "request_id": "homelab-health.statuses",
              "method": "GET", "path": "/api/v1/endpoints/statuses",
              "status_code": 200, "duration_ms": 41, "error_class": null } }
```

Every `key` exists in the `values` the draft was built from, and each becomes a C1 `Field_` whose
`path` is the JSONPath `$.checks` / `$.failing`, so the subset is checked by `_check_path`
(`models.py:26`) when the card is saved — not when it is first rendered. This sample needs no
`status_map`: it has no provider string to translate, and the Play-Nice word comes from the
sample's own `state`. Had the service answered `$.status: "up" | "down"`, the draft would carry
`status_map: { path: "$.status", healthy: ["up"], needs_attention: ["down"], mode: "first" }`, and
an unrecognised value would read `unknown`, never `healthy` (§4.7).

**5. publish (selective)** — the owner publishes the two field keys the draft actually carries,
and *not* the per-endpoint names.

```jsonc
// POST /api/connect/v1/connections/homelab-health/publish
{ "contract": "connect/v1", "board": "home", "card": { …the CardDraft above… },
  "published": ["checks", "failing"], "hidden": [] }

// → 200
{ "board": "home", "published": ["checks", "failing"], "hidden": [],
  "published_at": "2026-10-13T14:02:44Z", "published_by": "owner" }
```

One call writes `cards/homelab-health-check-results.yaml` — whose `fields` list *is* the
allow-list (§6.1) — and adds the board item to `boards/home.yaml`. `published_at` and
`published_by` come back in the receipt and are stored nowhere (§4.4, §6.1). A key that is not
in the draft is refused; an empty `published` would write nothing to Home at all.

**Render** — what the owner then sees on Home:

```text
Homelab checks
  "Are the homelab checks passing?"
  Checks 42 · Failing 0        all 42 checks passing        healthy · current
```

The card answers "are the checks passing"; the per-endpoint drill-down stays in Connect, where it
is looked at on purpose. The C5 accessibility props come from the envelope as they do for any
card, and the state word reads `healthy` because the sample said so — not because a `test` passed
once.

**6. propose-action** — if the owner wants "re-run the checks", it is a `write`, `scope` is
`homelab-health.check-results`, `idempotency: "required"`, `exposed: false`, and the approval
link is `{ kind: "worlds", authorization_id: … }` — because this connection is `authority:
"worlds"`. Nothing is sent at propose or at adopt; only a consumed authorization dispatches, once.

## 9. Worked integration B — Project Home room/0 (read-only)

**This is a MOCKUP walkthrough.** The wiring it describes exists; the Connect-shaped path through
it does not. What follows is what §1 looks like when `dialect` is `room-0` and `authority` is
`external`.

**The descriptor is where the two worked integrations differ, and almost nowhere else.**

```jsonc
{ "contract": "connect/v1", "connection_id": "project-home",
  "display_name": "Project Home", "vendor_label": "Project Home",
  "dialect": "room-0", "authority": "external",
  "principal": { "person_ref": "your-person-id" },
  "credential": { "ref": "env:PROJECT_HOME_ROOM_TOKEN", "auth": "bearer",
                  "scope": ["room-status", "room-cards", "room-needs", "room-actions"] },
  "capabilities": [
    { "capability_id": "room-status",  "provenance": "owner",      "verified": false,
      "reads": [{ "operation": "room", "method": "GET", "path": "/room",
                  "bounds": { "timeout_s": 5, "max_bytes": 2097152, "ttl_s": 30 } }] },
    { "capability_id": "room-cards",   "provenance": "owner",      "verified": false,
      "reads": [{ "operation": "room-cards", "method": "GET", "path": "/room/cards",
                  "bounds": { "timeout_s": 5, "max_bytes": 2097152, "ttl_s": 30 } }] },
    { "capability_id": "room-needs",   "provenance": "owner",      "verified": false,
      "reads": [{ "operation": "room-needs", "method": "GET", "path": "/room/needs-you",
                  "bounds": { "timeout_s": 5, "max_bytes": 2097152, "ttl_s": 30 } }] },
    { "capability_id": "room-actions", "provenance": "discovered", "verified": false,
      "reads": [{ "operation": "room-actions", "method": "GET", "path": "/room/actions",
                  "bounds": { "timeout_s": 5, "max_bytes": 2097152, "ttl_s": 30 } }] }
  ],
  "publish_target": { "board": "home", "publish": ["status", "needs_open"] } }
```

`label` and `meaning` are elided from those four capabilities only to keep the descriptor readable:
as in integration A they are the owner's own words, filled at register and never taken from the room
(§4.8). `provenance: "discovered"` on `room-actions` is what the room's own answer earned, and it
is why that capability stays `verified: false` until a foreman checks it.

`your-person-id` is the placeholder `config/recipes/project-home/provider.yaml` ships, and it is
installed as written: Worlds speaks for one named person, validated at save and again at send
(`confinement.py:606`), and never as a free request header. The owner replaces it in their own
config; nothing in Worlds guesses it. On the way to `providers/project-home.yaml` the object form
projects onto the stored string `Provider.principal_id` (`models.py:180`) — `person_ref` is all of
a `PrincipalBinding` in v1, and any other part is refused at register, not silently dropped (§4.1).
`env:PROJECT_HOME_ROOM_TOKEN` is a **name**, never a value: Worlds resolves it at send time through
`secrets.resolve_secret_ref` and never holds or returns the secret it names (§4.2).

**1. discover** reads `/room` and the three lists, through the confinement seam, with the same
caps as any other connection. A room that does not answer `contract: room/0` is `malformed` →
`degraded`, never silently empty (`room0.py:384`).

**2. register** writes the provider only. **No request, card or action files are invented** — the
room maps its own cards through C8 (`CONTRACTS.md` C8). This is the `status: room` recipe's one
honest idea, and it survives into the contract unchanged: registration ends at
`providers/project-home.yaml`, and a card appears only when the owner explicitly publishes one in
step 5, never as a side effect of connecting.

**3–4. test / transform** map a room card to `TestResult` with `source.request_id` of the form
`<provider>.room` and `source.path` of the read that ran — `/room` for the status capability,
`/room/cards` for a card — then to a `CardDraft`. Descriptor status
maps healthy→healthy, degraded→degraded, unhealthy→needs_attention, unknown→unknown
(`room0.py:36`). An unrecognised tone reads as `update`, logged (`room0.py:157`). A card that
cannot be read honestly is `degraded` with every value `unknown` — never a made-up value. A card
past `stale_after_s` is `stale`, never `current` (`room0.py:434`).

For the `room-status` capability, the sample the room actually returns is:

```jsonc
{ "contract": "connect/v1", "capability_id": "room-status",
  "source": { "connection_id": "project-home", "request_id": "project-home.room",
              "method": "GET", "path": "/room",
              "status_code": 200, "duration_ms": 63, "error_class": null },
  "freshness": "current", "state": "needs_attention",
  "observed_at": "2026-10-13T14:06:02Z", "fetched_at": "2026-10-13T14:06:02Z", "last_good_at": null,
  "values": { "status": { "key": "status", "text": "needs attention" },
              "needs_open": { "key": "needs_open", "text": "2" } },
  "meter": null, "truncated": false }
```

`status` is the room's own descriptor run through the mapping above, so an `unhealthy` room is
`needs_attention` and never `healthy`; `needs_open` counts the room's open needs and is the only
number the card shows. The draft's fields are those two keys and nothing else — the per-card
titles the room lists are `room-cards`' business, and stay in Connect.

**5. publish (selective)** is where this connection earns the adapt in §7.3: the owner chooses
which field keys land on Home. Today every card lands (`room0.py:493`). Under §4.4 the rest stay
in Connect, and are named rather than silently dropped:

```jsonc
// POST /api/connect/v1/connections/project-home/publish
{ "contract": "connect/v1", "board": "home", "card": { …the room-status CardDraft above… },
  "published": ["status", "needs_open"],
  "hidden": ["room-cards", "room-needs", "room-actions"] }

// → 200
{ "board": "home", "published": ["status", "needs_open"],
  "hidden": ["room-cards", "room-needs", "room-actions"],
  "published_at": "2026-10-13T14:06:20Z", "published_by": "owner" }
```

A hidden capability contributes nothing to the board payload, to an agent answer or to the card
itself (§4.4); the receipt names it, which is the point of the field — "kept but not shown" is
visible rather than silent. Its own files stay written, because C8 still owns how the room maps
its cards. Links remain same-origin paths or they are dropped (`room0.py:71`).

**Render** — the one card on Home:

```text
Project Home
  "How is the room?"
  Status needs attention · Needs open 2        needs attention · current
```

Nothing about the approval path appears on the card: the room's actions are `exposed: false` and
are answered in the room, which is the next step.

**6. propose-action → approve elsewhere → execute.** The whole point of `authority: "external"`:

```text
Connect: propose "Acknowledge the build plan"
   → ActionProposal { effect: "write", exposed: false, idempotency: "required",
                      approval: { kind: "project_home",
                                  room_url: "https://project-home.lan.example",
                                  action_ref: "<the room's own action ref>" } }
   → the owner is sent to Project Home; Worlds does not render an approve button here
Project Home: approves in its own /room/actions
Project Home calls back: the owner answers the room's action with the approval id
   → POST /api/rooms/{provider_id}/actions/{room_action_id}/answer   (endpoint 12, room_routes.py:52)
   → body: { "project_home_approval_id": "<the room's own approval id>" }
   → room0.answer → dispatcher.record_project_home_approval → authority=project_home:<id> (dispatcher.py:288)
Connect: execute → request_authorization → approve(recorded, not re-decided) → consume → dispatch
```

Today the third line is where it stops: with no verifier wired, `record_project_home_approval`
raises before writing anything and the call is 403 (§7.3). The contract keeps the line and says
what is missing from it.

Worlds shows and links. It never mints a second approval for an operation Project Home already
governs, and it never approves one on the owner's behalf in Worlds. A room that offers its own
`ask_first` approval token is not supplied by Worlds: that action fails closed at the room
(`CONTRACTS.md` C8).

**Fast on a bad day is part of the contract, not an implementation detail.** A failing room is not
retried for 30 s, doubling to 5 min; a request waits at most 0.25 s behind another fetch; a room
always answers with last-good cards marked stale, or one explicit `unavailable` status card
(`room0.py:302`, `:470`, `:493`). One room being dead must never delay or blank the others — that
is a property of the contract, and it is what makes "Worlds shows" honest rather than fragile.

## 10. What this document does not decide

- Whether any of this is built. It is a MOCKUP. A PROTOTYPE would name the module and the tests;
  APPROVED would name the issue that accepted it.
- Whether the already-live `/api/connect/try` and `/preview` paths move. Default: they do not
  (§6). Moving a working path for tidiness is the same mistake as a new backend for newness.
- How endpoint 12 verifies a Project Home approval, given that no verifier is wired and the path
  currently refuses rather than records (§7.3). This document does not invent one.
- The Connect UI design. "A brand new design" is Rylee's call and it is not this document's.
- Whether the 16 shipped recipes become descriptors, imports, or retired files. Endpoint 2 can
  carry them; what happens to the directories is a separate decision with its own evidence.

## Revision 1

**Date:** 2026-10-13 · **Resolves:** the review of this document. One row per finding: what
changed and where, or a reasoned reject. Nothing in §0–§10 was weakened to make a row pass — where
a fix was not possible inside the owner's decisions, the row says so and the claim stays.

> **Finding ids.** `docs/vnext/connect-contract-review.md` was **not present** in the worktree this
> revision was made in (never committed on any reachable ref; no remote access from the clone). The
> BLOCKER and the three MAJOR findings are addressed below under the ids the brief uses, and their
> substance is quoted from the brief. The four MINOR and two NIT findings could not be read, so they
> could not be matched one-to-one: rows `MINOR-1..4` and `NIT-1..2` below are **this revision's own**
> findings, fixed opportunistically while re-verifying every citation against `786f506`. The
> original ids are unverified and the coordinator should reconcile them.

| Id | Severity | Finding | Resolution |
|---|---|---|---|
| BLOCKER-1 | BLOCKER | §6 and §7.1 asserted "no new field/file/model/table" while the contract also requires persisted state (`ConnectionDescriptor`, `Capability`/`ReadSpec`, `PublishSelection`, `ActionProposal`, last-good values) with nowhere to live | **Resolved by making the persistence story explicit and narrowing the claim, not by dropping persistence.** New **§6.1 "What v1 persists, and where"**: a table of every contract type against the C1 config file it compiles to, the four additive *optional* fields that cannot be derived (`Auth.scope`, `Request.provenance`, `Request.verified`, `Action.state`) with their defaults and why each default leaves existing files valid, and a table of what is deliberately *not* persisted (discovery candidates, `TestResult`/last-good, pre-publish `CardDraft`, disconnect/revoke reports, rotation dates, held credentials). §6's `schema_version` and file-layout rows, §6.2 ("no data migration" → also "no results store"), and §7.1's "must not add" now match §6.1 exactly. §1's "each step's output is durable" now says what durable means. No new table, file, kind or required field; persistence was not dropped, because a connection whose credential scope and publish selection vanish on restart is not a connection |
| MAJOR-a | MAJOR | The verifier-gap wording is factually wrong: it claimed a Project Home approval id "is stored but not verified" | **Resolved.** `dispatcher.record_project_home_approval` raises `NotPermitted` at `dispatcher.py:277`–`:278` on its first statement, before `self._db.write_tx()` opens — nothing is stored. §7.3 now quotes those two lines, states that nothing is written and the answer route is 403 (`room_routes.py:76`), and names the earlier wording as wrong in the unsafe direction. §5.1 (`:275` → `:284`, `:288`), §5.2 (`:275` → `:277`–`:278`, `:288`; `room0.py:598` → `:598`–`:599`), §9's Project Home flow and §10's open question all corrected to match. The gap is still flagged, not designed around: no verifier is invented here |
| MAJOR-b | MAJOR | The §4 field ledger omitted `CardDraft`, `Capability` and `ReadSpec`, so those types had no named consumer, reason or security test — a direct miss against #323's acceptance rule | **Resolved.** New **§4.7 `CardDraft`** (8 fields) and **§4.8 `Capability` and `ReadSpec`** (6 + 7 fields), each with consumer, reason and security test, all citations re-verified against `786f506`. `CardDraft`'s security tests point at the C1 card model it becomes (§6.1); `Capability.verified` is explicitly never inferred from a passing test; `ReadSpec` bounds are refused-not-clamped against the provider caps. §4.1's `capabilities` row now cross-references §4.8 |
| MAJOR-c | MAJOR | Endpoint 12, `POST /api/connect/v1/approvals/{authorization_id}/record-external`, does not exist | **Resolved by replacement, not deletion.** No new path is invented: endpoint 12 is now the **existing** `POST /api/rooms/{provider_id}/actions/{room_action_id}/answer` (`room_routes.py:52`, `:72`), with `project_home_approval_id` in the body, routed by `room0.answer` (`room0.py:581`, `:598`–`:599`) into `dispatcher.record_project_home_approval`. Consumer (Project Home's own approve, coming back), reason, and security test are stated, including the 403 today. The note beneath the table no longer claims both 11 and 12 would move under `/api/connect/v1/`; §9 step 6 shows the real call |
| MINOR-1 | MINOR (self) | ~~§6's `worlds.db` row listed a `history` table. There is none — and `worlds.db` has six table groups the row omitted~~ **Superseded by Revision 2 (NEW-1): the premise of this row was false. `history` does exist** | **Reopened.** Revision 1 removed `history` from the row on a false premise and called the absence a fix. Revision 2 restores the table with its real columns and states the true reason `TestResult` is not persisted — there is no *results* table, and `history` is an audit log for memory rows |
| MINOR-2 | MINOR (self) | §4.3 named "history rows" as a consumer of `TestResult.source`, resting on the same wrong table | **Fixed, then corrected.** Consumer is the detail view's evidence strip and `Home → needs a look`. Revision 2 (NEW-1) rewords the note inline, because the sentence it corrected ("no history table") was itself wrong — `history` exists, it is simply not a store of reads |
| MINOR-3 | MINOR (self) | Endpoint 12 cited `room_routes.py:71`/`:72` interchangeably for two different routes | **Fixed** with MAJOR-c: the cite is `:52` (the route) and `:72` (the body field), each used for what it is |
| MINOR-4 | MINOR (self) | §7.1's "no new field" was stated as a flat prohibition while §4.2/§5.1 already said credential scoping "is new" | **Fixed.** §7.1 now names the three exceptions and points at §6.1 as the single place they are specified, so the two statements can no longer disagree |
| NIT-1 | NIT (self) | §1 said each step's output "is durable" without saying durable where | **Fixed.** §1 now points at §6.1 and states that "durable" never means "a new store" |
| NIT-2 | NIT (self) | `PublishSelection.published_by`/`published_at` and §4.6's revoke claims had no stated storage | **Half-fixed, then corrected.** §6.1 settled `published` (the card's own `fields` list) and board membership (`Board.items`/`BoardItem.hidden`), and `published_by` is `owner` by construction because the config write routes take `owner_dep`; after a revoke the deleted files *are* the record. Revision 2 (NEW-4) fixes the half this row left open: `published_at` had a consumer named as "History", which had nothing behind it. It is now given a real consumer (endpoint 8's receipt) and an explicit *not persisted* row |
| MINOR/NIT (review ids unknown) | MINOR ×4, NIT ×2 | The four MINOR and two NIT findings in the review could not be read — the review file is absent from this worktree | **Unresolved by choice, not by omission.** Rather than guess at six findings and invent ids, this revision fixed the six it found while re-verifying citations and recorded them above. The coordinator holds the review and should re-run the match |

### What this revision did not touch

The provider-neutral design (one vocabulary, six verbs, `dialect` as the only difference), the
authority table in §5.2, the C3 lifecycle, and every quote in §0. No code, test or config file was
modified: this revision is one file of prose.

## Revision 2

**Date:** 2026-10-13 · **Resolves:** the independent re-review (`connect-contract-rereview.md`),
which graded Revision 1. Every citation below was re-opened in this clone at the line it names,
against the working tree, not against Revision 1's own table.

> **The earlier review is still absent.** `docs/vnext/connect-contract-review.md` is not in this
> clone and is not on any reachable ref (`git log --all -- docs/vnext/connect-contract-review.md`
> is empty), so the *original* review's four MINOR and two NIT findings still cannot be matched
> one-to-one. This revision reconciles the re-review in full and fixes the two defects Revision 1
> introduced itself. The original six remain for the coordinator to match, as in Revision 1.

| Id | Severity | Finding | Resolution |
|---|---|---|---|
| NEW-1 | MAJOR | §6's `worlds.db` row and §4.3 asserted there is "no results or history table"; `history` exists at `memory_store.py:56` with `history_no_update`/`history_no_delete` triggers and a `find_index` FTS table | **Fixed.** §6's row lists `history` and `find_index` with their citations, names the real columns (`id, at, actor, event, table_name, row_id, detail`) and states what they are: an append-only audit log for `kept`/`later`/`records` and a mirror of them. The *conclusion* was right and the *reason* was wrong, so §6.1's "no results table" row and §4.3's consumer note are reworded to the true reason: nothing in `worlds.db` is keyed by connection or request, and no `test` writes to it. A regression against `51ef662`, which listed `history` correctly, is undone |
| NEW-2 | MAJOR | §6.1 claims "exactly four additive optional model fields" while §4.2 and §6.1 said `CredentialReference.rotated_at` is stored "in the provider file, if the owner sets it" — `Auth` has no such field and is `extra="forbid"` (`models.py:78`–`:101`) | **Fixed by taking the reviewer-suggested option (a): `rotated_at` is not persisted.** §2's field is marked owner-side only, §4.2's consumer is "nowhere in Worlds — the owner's own password manager or notes", and §6.1's *not persisted* table now gives the reason a file cannot hold it. Option (b) — a fifth additive field — was rejected: it would grow `Auth` for a hint whose only consumer is the owner's own reminder, which §7.1's "a connection that needs a fifth is a signal the design is wrong" forbids. §6.1's four-field list says it is exhaustive and why |
| NEW-3 | MINOR | Capability-level `provenance`/`verified` are stored per-`Request`, so a capability with several reads has no single place for a capability-level `verified` | **Fixed by stating the projection.** A capability compiles to one request file per `ReadSpec` (§6.1), and the capability-level value is derived, fail-closed: `provenance` is the **weakest** any of its reads claims, `verified` is true only when **all** of them are. §4.8's two rows, the `reads` row and §6.1's `ReadSpec` row now say so. No new field and no new ambiguity |
| NEW-4 | MINOR | `PublishSelection.published_at`/`published_by` named "History" as consumer; §6.1 gave them no home and the *not persisted* table did not mention them | **Fixed.** The consumer is now endpoint 8's publish receipt — the confirmation Connect shows the owner — with the card file's etag/`updated_at` as the durable record of the config change; a *not persisted* row says why (`BoardItem` is `extra="forbid"` with no timestamp, `models.py:446`–`:450`) and that keeping one would be a fifth additive field |
| NEW-5 | MINOR | `ConnectionDescriptor.principal` is an object in §2/§9 but `Provider.principal_id` is a string (`models.py:180`), with no declared projection | **Fixed.** §4.1's row, §6.1's identity row and §9's walkthrough all state that `person_ref` is the whole of a `PrincipalBinding` in v1, that it lands as `principal_id`, and that any other part is **refused at register**, not silently dropped |
| NEW-6 | NIT | §4.7 cited the JSONPath save-time check as `models.py:25`; that line is blank and the function is `_check_path` at `models.py:26` | **Fixed.** §4.7 now matches §3 endpoint 7's `models.py:26`, and §8's walkthrough cites it too |
| NEW-7 | NIT | §6.1 wrote that `timeout_s` "stays on the provider", but `Request.timeout_s` exists (`models.py:251`) and §4.8 relies on the per-read override | **Fixed.** §6.1's `ReadSpec` row now lists `timeout_s` among the `Request` fields and names `max_bytes` as the only provider-only bound; §4.8's bound row names `Request.timeout_s` (`models.py:251`) against the provider cap (`models.py:184`) |
| NEW-8 | NIT | Revision 1's six rows are not a resolution of the original review's six, because that file was absent | **Not fixable here, and not hidden.** The original review file is still absent from this clone and from every reachable ref; the note above Revision 1 and this note say so twice, and the coordinator still holds the match. What *was* fixable — Revision 1's own defects — is fixed in NEW-1 and NEW-2 above |
| SAMPLE-1 | MAJOR | The worked sample registered `"credential": { "ref": "env:", "auth": "none", ... }`. `SECRET_REF_RE` (`models.py:15`) requires a name after the colon, so `env:` is malformed, and the row sat next to a threat-table entry that says Worlds refuses its own names | **Fixed.** §8 step 2 now uses `env:EXAMPLE_TOKEN` with `auth: "bearer"` — a name, not a value, and obviously synthetic — and the prose says why a bare `env:` is refused and that a service needing no credential takes `"credential": null`, as step 1 does. Discovery's `needs_auth` became `bearer` so the walkthrough is consistent end to end |
| SAMPLE-2 | MAJOR | `"publish": ["Checks", "State"]` named free labels, not the field keys §4.4 requires, so the publish could not match the `TestResult.values` or the card's `fields` | **Fixed.** §8's `TestResult.values`, the new `CardDraft` in step 4, the publish body and the Home render all use the same two keys, `checks` and `failing` (`_KEY_RE`, `models.py:364`), and the prose says the Play-Nice state word is the card's state, never a published field. §9's room/0 example got the same treatment: `publish: ["status", "needs_open"]`, `hidden` naming the three capabilities that stay in Connect, plus the `TestResult`, the publish receipt and the rendered card |

| SAMPLE-3 | MINOR | Found while fixing SAMPLE-2: §6.1 named the file `requests/<connection>.<capability>.<operation>.yaml` and `cards/<connection>.<capability>.yaml`, but `REQUEST_ID_RE` (`models.py:14`) is exactly two segments and `ID_RE` (`models.py:11`) takes no dot at all — so neither file name could be created | **Fixed.** Request files are `requests/<connection>.<operation>.yaml` (`statuses` in §8, `room`/`room-cards`/… in §9); `ReadSpec.operation` is therefore unique within the *connection*, which is what §4.8 now says. Cards are `cards/<card-id>.yaml` with a single-segment id (`homelab-health-check-results`), and §2's `card_id` and §4.7's row say so. §9's capabilities also gained their `reads`, since §4.8 requires a capability to have at least one |
| SAMPLE-4 | MINOR | §4.4 said a hidden capability appears in "no receipt", but §9's receipt names `hidden` — the field exists to make that visible | **Fixed.** "No receipt" meant no *content*; the row and §9 now say the only place a hidden capability is named is the receipt and Connect detail |

### What this revision did not touch

The provider-neutral design, the six verbs, the authority table in §5.2, the C3 lifecycle, the
§7.3 verifier gap (still flagged, still not invented), and every quote in §0. Still one file of
prose: no code, test or config file was modified, and the two review files were left as written
except for this section's cross-references.

### Status

Still **MOCKUP**. Reconciling a review is not building anything: no route in §3 exists, no field
in §2 is stored, and no security test in §4 or §5 has been written. MOCKUP ≠ PROTOTYPE ≠
APPROVED, and "reviewed" ≠ "tested" ≠ "deployed".
