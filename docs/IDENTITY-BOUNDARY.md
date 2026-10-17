# Identity Boundary — per-user vs instance-global state

> **Status:** Reference · **Verified:** 2026-09-29 · **Canonical for:** the per-user vs instance-global state boundary and the `identity.principal_scoped_path` entry point · **Read this if:** you are adding per-person state or working on multi-user mode.

**In short:** one Worlds instance can serve several people, and this page says exactly which state is per-person (journal, reminders, world, crew, room visits, …) and which is instance-wide (runtime config, the shared connections registry, identity records). Every per-user file resolves through one entry point, so single-user installs keep working unchanged.

Product decision #13: **one instance can serve multiple people**
(OIDC/Authelia identities map onto local principal records). The
single-user default must keep working byte-identically — this boundary
is what makes both true at once.

The single entry point is `identity.principal_scoped_path(data_dir, principal,
kind, mode=...)` (`src/personal_world/identity.py`). Every per-user
store resolves its file through it; no handler invents its own layout.
`api.py` wraps it as `_scoped_path(principal, kind)`.

## The boundary

| Per-user (scoped to the calling Principal) | Where it lives |
|---|---|
| World (facts, intents, policies, lore) | `world` kind → `world.json` |
| Preferences (accessibility/presentation) | inside the per-user world (`accessibility`) |
| Map/constellation structure (sections layout) | inside the per-user world (`layout`) |
| Journal (notes, corrections, audit/story) | `journal` kind → `journal.ndjson` |
| Reminders | `reminders` kind → `reminders.json` |
| Brain proposals (+ approval evidence) | `proposals` kind → `proposals.json` |
| Chat history (transcript) | `chat_history` kind → `chat-history.ndjson` |
| Interests + discovery sources | `discovery` kind → `discovery.json` |
| Crew + rooms (companions, keepers, doorways, visit/seen state) | `crew` → `crew.json`; `rooms_visits` → `rooms-visits.json` |
| Continuity (journal drafts, edit pairs, last place) | `journal_draft`, `journal_edit_pairs`, `last_place` kinds |
| Personal connections / personal provider credentials | see SECURITY.md contract (shared registry stays global) |

| Instance-global (never per-user) | Why |
|---|---|
| Application/runtime config (`config/`, `.env`, setup state) | one deployment, one runtime |
| Capability definitions / catalog / manifest | the product's capability model is not personal |
| System health, status maps, lab/media/source-control observations | observations about shared infrastructure |
| Deployment config (compose/systemd adapters) | operator concern, not person concern |
| Shared connections registry (`connections.json` + local overrides) | provider wiring is instance-level; secrets stay in the vault contract |
| Identity records (`users.json`), sessions, OIDC config | the trust root itself |
| Apps registry, theme packs, brain templates | installed content available to everyone |
| Memory FTS index (`memory.fts5.db`) | currently indexes the instance journal (per-user index is future work) |
| Vault (`vault.enc`) | currently instance-level; per-user vault isolation is an open security decision, not a default |

## Which routes follow the caller

In multi mode these routes read and write the **caller's own** world and
journal (`_state_for(request)`): `GET`/`POST /api/daily`,
`GET /api/memory/search`, `GET /api/exports/world`, `GET /api/backup`, and
`POST /api/world/intent`, `/fact`, `/policy`. (`/api/memory/search` still
queries the instance-level FTS index noted above.) These stay
**instance-wide** by design: `/api/status`, `/api/chat/providers`,
`/api/chat/test`, `/api/actors`, `/api/manifest`,
`/api/connections/overview`, `/api/exports/settings`, `/api/templates`.
Single mode is unchanged: every route uses the legacy instance paths.
`tests/test_world_routes_per_user.py` pins both directions.

## Path rules (in order)

1. Unknown kind → `ValueError`. Fail closed; never a guessed path.
2. Single mode (`PW_IDENTITY_MODE=single`, the default), or no
   principal (background entry points like the scheduler tick) → the **legacy
   instance path**. A single-user install reads and writes exactly the
   files it has always used; enabling multi-user later never silently
   moves or loses data.
3. Multi mode → `data/users/<id>/<file>`, where `<id>` is the person's
   id — or an **agent's owner id**: agents act on their owner's tree, so
   an agent-proposed reminder or proposal lands where the owner will
   review it.
4. An id that is not a safe path segment → `ValueError` (no traversal).

Legacy mapping (rule 2), explicitly:

| Kind | Legacy path (single-user default) |
|---|---|
| world | `<data_dir>/world.json` |
| journal | `<data_dir>/journal.ndjson` |
| reminders | `<data_dir>/reminders.json` |
| proposals | `<data_dir>/proposals.json` |
| chat_history | `<data_dir>/chat-history.ndjson` |
| discovery | `~/.config/personal-world/discovery.json` |

In multi mode the bootstrap `primary` person gets a tree like everyone
else (`data/users/primary/…`); the instance-root files remain the
single-mode home and the scheduler's legacy tick. Switching an existing
install to multi is an explicit operator opt-in; migrating the legacy
files into `users/primary/` at that moment is a deliberate, visible
step — never a silent redirect.

## Runtime behavior

- The legacy scheduler thread keeps firing `<data_dir>/reminders.json`.
  In multi mode an additional 60s tick fires each enabled person's own
  reminders file into their own journal (trees without a reminders file
  are skipped, so a person's directory is never materialized by the
  clock alone).
- Proposal stores are per-path instances (`tool_registry.ProposalStore`,
  cached via `proposal_store_for`). Approval evidence, step-up gating,
  and the "model can never self-approve" rule are identical in every
  store; stores never see each other's proposals.
- `/api/chat` observes the caller's own world/journal, proposes into the
  caller's own store, and appends to the caller's own transcript
  (`GET /api/chat/history`).

## Sync-friendliness (decision #15)

This boundary is kept clean so **future multi-device sync stays
possible** — sync is explicitly NOT built here, and nothing in this
design may assume it. The properties that keep the door open:

- One person's state is exactly one directory tree
  (`data/users/<id>/`), with stable file names per kind — a sync unit
  can be defined per person without re-partitioning anything.
- Append-only formats where truth is temporal (journal, chat history)
  merge more safely than rewrite-in-place formats.
- Per-tree proposal ids and counters: two devices (or two people) never
  collide on a shared global counter.
- Instance-global state stays out of the per-user trees, so syncing a
  person's data never drags deployment config or credentials along.

Do not add cross-user reads, shared mutable per-user files, or
global counters to per-user kinds without revisiting this document.

## Roles and permissions

> Owner-approved 2026-09-26. Canonical for how people get admin vs
> member rights in Worlds (Project Home and Candy follow the same names).

**Code never checks a name or a role string; it asks "can this person do
X?".** The one question is `roles.can(principal, permission)` in
`src/personal_world/roles.py` (pure — no I/O, no imports from the
package). Roles are just *bundles* of permissions, so a new role is a
table entry and not a search-and-replace.

| Role | For | Gets |
|---|---|---|
| **owner** | whoever runs the install; exactly one | every permission; can't be locked out; can hand ownership to an admin |
| **admin** | trusted co-runners | manage people and rooms, approve, estate secrets, updates |
| **member** | everyone in the home | their own space; see shared rooms |
| **supervised** | kids | member, minus what a guardian limits (the limits are visible to the person) |
| **guest** | a babysitter, a visitor | only what is shared with them; expires |
| **agent** | AI and services, not people | only their token's permissions, never more than the person they act for |

**Helper is a grant layered on any account, not a role** (Jo can be a
member *and* hold a helper grant for the owner); its per-person
`see_needs_of:<person>` / `act_for:<person>` permissions are answered by
`can(..., target=..., grants=...)` from the live grants. See
"Invites, helpers, limits, guests" below.

| Permission | owner | admin | member | supervised | guest |
|---|---|---|---|---|---|
| `own_space` (journal, crew, own Candy, own secrets) | ✓ | ✓ | ✓ | ✓ (within limits) | – |
| `see_shared` (rooms, shared things) | ✓ | ✓ | ✓ | ✓ | only what's shared with them |
| `approve` (room actions that write) | ✓ | ✓ | – | – | – |
| `manage_people` (invite, roles, limits) | ✓ | ✓ (not the owner) | – | – | – |
| `manage_rooms` (registry, keepers for everyone) | ✓ | ✓ | – | – | – |
| `estate_secrets` | ✓ | ✓ | – | – | – |
| `updates` (deploy what's live) | ✓ | ✓ | – | – | – |
| `transfer_ownership` | ✓ | – | – | – | – |

`can()` fails closed: an unknown permission is `False`, never an
exception; no principal is `False`; an agent holds a permission only when
its token scopes map to it **and** the owner it acts for holds it too
(the lesser of the two). The legacy `admin` scope is still read as admin
for back-compat, but new code writes `role`.

### How a role is set

* **Local (non-SSO) accounts** keep the role an admin set for them
  (`PUT /api/people/{id}/role`). Provisioned people default to `member`;
  the bootstrap `primary` account is the `owner`.
* **SSO sign-in** reads the provider's `groups` claim and maps it through
  `PW_ROLE_GROUPS`, e.g.
  `admin=admin,users=member,kids=supervised,guests=guest`. The highest
  privilege wins when several groups match; the person's stored role is
  updated on every sign-in. **Owner is never mappable**: an entry naming
  `owner` is ignored and logged, and the owner is never demoted.
* **Agents** stay principals (`kind: "agent"`), not a role. An agent's
  reach is its token scopes intersected with its owner's permissions.

### Admins manage accounts, not content

`manage_people` is about accounts, roles and the ownership hand-off
(`GET /api/people`, `PUT /api/people/{id}/role`,
`POST /api/people/transfer-ownership`). It is **not** a key to anyone's
journal, secrets or world: nobody reads another person's data unless that
person shares it, admins included. `GET /api/me` tells the interface what
the caller may do so it can show or hide affordances; the server always
enforces the same `can()` answer.

## Read-only viewer credential

A **viewer** credential is for automation that must see the person's real
screens without holding any power: it acts as the owning person for **reads
only**. It is a separate record type (`viewers` in `users.json`), so nothing
that walks users or agents (sessions, listings, sign-in) can match one.

- **Create / list / revoke** (owner only, and creation and revocation need a
  step-up): `POST /api/identity/viewers` `{viewer_id, label?}` returns the
  token **once** (prefix `pwv_`, stored hashed like other tokens);
  `GET /api/identity/viewers` lists them without hashes or tokens;
  `DELETE /api/identity/viewers/{viewer_id}` revokes (the token answers 401
  afterwards). A viewer, an agent or a non-owner cannot do any of these.
- **Read-only, enforced in the auth layer** (`require_auth`), not per route:
  only `GET`, `HEAD` and `OPTIONS` succeed; every other method answers 403
  "read-only token", including routes added later.
- **Never elevated:** `require_step_up` refuses it, and no session grant,
  loopback peer or delegated header changes that. The token cannot be traded
  for a session, an elevation or a CLI approval (`resolve_principal` only
  accepts it on the API's bearer path).
- **Deny list** (`api.VIEWER_DENIED_PREFIXES`, tested): a viewer gets 403 on
  `/api/vault`, `/api/secrets`, `/api/lab/secrets`, `/api/lab/settings`,
  `/api/recall`, `/api/journal`, `/api/memory`
  (search), `/api/records`, `/api/learning`, `/api/backup`, `/api/worlds`,
  `/api/exports`, `/api/identity/{agents,users,viewers}`,
  `/api/people/invites`, `/api/push/subscriptions` and
  `/api/connections/config`: secret values and names, raw personal material,
  whole-instance archives, credential administration and infrastructure
  configuration. Other person-only reads (preferences, sections, briefing,
  place, lore, later) work.
- **Memory and Chat: structure yes, content no.** A viewer can read:
  `GET /api/records/categories` (category names, counts, locked flag; the one
  named exact exception, `VIEWER_ALLOWED_EXACT`) and `GET /api/chat/history`
  with each entry cut down to `ts` and `role` (when and who, plus the count;
  `VIEWER_CHAT_ENTRY_KEYS`, an allow-list, so a content field added later is
  omitted by default). A viewer cannot read what was said or remembered:
  message bodies, journal entries, record contents, memory search results and
  recall all answer 403 (or omit the field). Lore and later are still
  allowed as before and do return their text; tighten them the same way if
  that is not wanted.
- If the owner is disabled or expires, the viewer stops resolving.

## Invites, helpers, limits, guests

> Step 2 of the roles plan (owner-approved 2026-09-26). These are
> identity-level records (like `users.json`), not personal content:
> they name people and permissions, never a journal, a world or a secret.

**Invites.** A person with `manage_people` makes a one-time link
(`POST /api/people/invites`) for a role: member, supervised, guest or
admin. Only the owner may invite an admin, and the owner is never
invitable. The link token is shown once, at creation; only its hash is
stored. Accepting the link (`POST /api/invites/accept`, no sign-in)
creates the local account with that role, works once, and stops working
after the link expires (72 hours by default, at most 336).

**Guests.** A guest record carries `until`, an ISO time. After it, the
guest resolves to nothing (401) exactly like a disabled account, and
`GET /api/people` shows them as expired. A guest holds only
`see_shared`.

**Helpers.** A person can let someone help them (`POST /api/me/helpers`):
a live grant gives `see_needs_of:<person>` and, with `can_act`,
`act_for:<person>`. Grants last 7 days by default and at most 30, and an
expired grant is ignored everywhere. A helper acts for a person only on
the rooms needs list and room actions, by sending
`X-Worlds-Helping: <person>`; on any other route that header is refused
(403). Every action a helper takes is written to the person's own
"helped by" log (`GET /api/me/helped-by`). The person can revoke a grant
any time; the owner can revoke any grant in an emergency, and the
revocation is logged and stays visible to the person.

**Supervised limits.** `manage_people`, or a guardian (someone with a
live `can_act` grant from the person), can set that person's limits
(`PUT /api/people/{id}/limits`) from a closed set: quiet hours for chat,
no outside sharing, and a content boundary. Worlds records who set them
and when, and the person sees their own limits at `GET /api/me/limits`.
A guardian still cannot read the person's journal or world — helping
covers room needs and room actions only.

`GET /api/me` also reports `helpers_granted`, `helping` (the people the
caller may help, with `until`), and `limits` (when supervised) or
`guest_until` (when a guest).

**Join page, directory, names beside ids.** An invite is sent as
`/invite#<code>`: a signed-out static page served with the same
`no-store` pattern as `/login`. The code rides in the URL fragment —
fragments never reach the server — and the page posts it to
`POST /api/invites/accept`; the sign-in key that comes back is shown
**once** and never written to a URL, browser storage or a log.
`GET /api/people/directory` is the people picker: `[{id, display_name}]`
for enabled people only — no roles, no emails, no expired guests, no
agents. It is gated on `own_space`: people who live here (owner, admin,
member, supervised) can list who else does, so they can pick a helper;
guests (visitors) and agents get 403. Helper and
limit views carry names beside ids (`helper_name`, `person_name`,
`set_by_name`): display names read from the identity store, with an
unknown or deleted id giving `null` — a name is never invented.

## Tests

`tests/test_identity_boundary.py` — entry point rules, two-principal isolation
(journal, reminders, proposals, prefs, chat history, interests), and
legacy-path continuity for the single-user default. `tests/test_roles.py`
— the role/permission bundle, `can()` fail-closed and agent lesser-of,
group mapping, record migration, the people API and `/api/me`. Existing
coverage: `tests/test_multiuser_phase23.py`, `tests/test_identity.py`,
`tests/test_proposal_durability.py`.
